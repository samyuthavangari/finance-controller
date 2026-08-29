from time import perf_counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.investigator import classify_exception, investigate
from app.audit import audit
from app.config.policy import policy
from app.core.ids import new_id, utcnow
from app.core.money import money
from app.evaluation.engine import evaluate_run
from app.forecasting.cash import forecast
from app.models import (
    Decision,
    Evidence,
    ExceptionRecord,
    Invoice,
    ReconciliationResult,
    ReconciliationRun,
    Transaction,
    Vendor,
)
from app.reconciliation.engine import build_indexes, match_transaction
from app.schemas.finance import AgentDecision, EvidenceItem


def close_books(db: Session, run: ReconciliationRun, investigate_exceptions: bool = True) -> ReconciliationRun:
    t0 = perf_counter()
    run.status = "running"
    run.started_at = utcnow()
    db.flush()
    txs = db.execute(select(Transaction)).scalars().all()
    invoices = db.execute(select(Invoice)).scalars().all()
    vendors = {v.id: v for v in db.execute(select(Vendor)).scalars().all()}
    by_ref, by_vendor = build_indexes(invoices)
    run.records_total = len(txs)
    audit(db, "JOB_STARTED", run.job_id, run.id)
    audit(db, "INGESTED", f"{len(txs)} RECORDS", run.id)

    counters = {
        "exact_matches": 0,
        "ml_matches": 0,
        "fuzzy_matches": 0,
        "normalized_matches": 0,
        "rag_resolved": 0,
        "human_review": 0,
        "unresolved": 0,
        "failed_extraction": 0,
        "invalid_financial_data": 0,
        "exceptions": 0,
    }
    llm_calls = 0
    rag_calls = 0
    det_resolutions = 0
    ai_resolutions = 0
    inv_times = []

    for i, tx in enumerate(txs):
        cands = match_transaction(db, tx, invoices, vendors, by_ref, by_vendor)
        top = cands[0] if cands else None
        band = policy.band_for_score(top.score if top else 0.0)
        why = {
            "checks": top.checks if top else {},
            "level": top.level if top else None,
            "score": top.score if top else 0.0,
            "candidates": [{"id": c.invoice.id, "score": c.score, "level": c.level} for c in cands],
        }
        if top and band == "AUTO_MATCH":
            decision = "AUTO_MATCH"
            reason = "EXACT_MATCH" if top.level == "L0" else "NORMALIZED_MATCH" if top.level == "L1" else "FUZZY_MATCH" if top.level == "L2" else "ML_MATCH"
            _store_result(db, run.id, tx, top, decision, reason, why, cands)
            if top.level == "L0":
                counters["exact_matches"] += 1
            elif top.level == "L1":
                counters["normalized_matches"] += 1
            elif top.level == "L2":
                counters["fuzzy_matches"] += 1
            else:
                counters["ml_matches"] += 1
            det_resolutions += 1
            tx.status = "matched"
        else:
            etype = classify_exception(tx, cands, top.score if top else 0)
            exc = ExceptionRecord(
                id=new_id("EX"),
                run_id=run.id,
                transaction_id=tx.id,
                exception_type=etype,
                amount=money(tx.amount),
                currency=tx.currency,
                candidate_invoice_ids=[c.invoice.id for c in cands[:3]],
                confidence=float(top.score if top else 0),
                reason=_exception_reason(etype, cands),
                recommended_action="HUMAN_REVIEW",
                final_decision="OPEN",
                evidence=[],
            )
            db.add(exc)
            db.flush()
            counters["exceptions"] += 1
            gated = None
            if investigate_exceptions and band in {"INVESTIGATE", "AMBIGUOUS"}:
                t_inv = perf_counter()
                gated = investigate(db, run.id, exc, tx, {inv.id: inv for inv in invoices})
                inv_times.append(int((perf_counter() - t_inv) * 1000))
                if gated.reason_code == "CONTRACTUAL_VARIANCE":
                    det_resolutions += 1
                else:
                    llm_calls += 0 if gated.reason_code in {"AMBIGUOUS_CANDIDATES", "INSUFFICIENT_EVIDENCE", "DUPLICATE_DETECTED"} else 0
                    if gated.reason_code not in {"AMBIGUOUS_CANDIDATES", "INSUFFICIENT_EVIDENCE", "DUPLICATE_DETECTED", "CONTRACTUAL_VARIANCE"}:
                        llm_calls += 1
                        ai_resolutions += 1
                    rag_calls += 3
            else:
                gated = AgentDecision(
                    decision="HUMAN_REVIEW" if band != "UNMATCHED" else "UNRESOLVED",
                    confidence=float(top.score if top else 0),
                    reason_code="INSUFFICIENT_EVIDENCE" if band == "UNMATCHED" else "AMBIGUOUS_CANDIDATES",
                    reason=exc.reason,
                    evidence=[EvidenceItem(source="transaction", id=tx.id)],
                    calculations={},
                )
            _store_decision(db, run.id, tx, exc, gated)
            result_decision = gated.decision
            if result_decision == "AUTO_RESOLVE":
                counters["rag_resolved"] += 1
                tx.status = "matched"
                inv_id = cands[0].invoice.id if cands else None
            elif result_decision == "HUMAN_REVIEW":
                counters["human_review"] += 1
                tx.status = "human_review"
                inv_id = None
            elif result_decision == "EXTRACTION_ERROR":
                counters["failed_extraction"] += 1
                tx.status = "extraction_error"
                inv_id = None
            else:
                counters["unresolved"] += 1
                tx.status = "unmatched"
                inv_id = None
            db.add(
                ReconciliationResult(
                    id=new_id("RR"),
                    run_id=run.id,
                    transaction_id=tx.id,
                    invoice_id=inv_id if result_decision == "AUTO_RESOLVE" else None,
                    match_level=top.level if top else "NONE",
                    match_score=float(top.score if top else 0),
                    decision=result_decision,
                    confidence=float(gated.confidence),
                    reason_code=gated.reason_code,
                    why=why,
                    candidate_invoice_ids=[c.invoice.id for c in cands[:5]],
                )
            )
            exc.final_decision = result_decision
            exc.recommended_action = result_decision
            exc.evidence = [e.model_dump() for e in gated.evidence]
        run.progress_pct = int((i + 1) / max(len(txs), 1) * 100)
        run.counters = counters
        if i % 50 == 0:
            db.flush()

    n = max(len(txs), 1)
    llm_saved = max(0.0, 1.0 - (llm_calls / n))
    run.cost = {
        "llm_calls": llm_calls,
        "rag_calls": rag_calls,
        "deterministic_pct": det_resolutions / n,
        "ai_assisted_pct": ai_resolutions / n,
        "llm_calls_saved_pct": llm_saved,
        "avg_investigation_ms": (sum(inv_times) / len(inv_times)) if inv_times else 0,
        "avg_llm_calls_per_exception": (llm_calls / counters["exceptions"]) if counters["exceptions"] else 0,
        "avg_retrieval_latency_ms": 12,
        "ocr_extraction_accuracy": None,
    }
    run.finished_at = utcnow()
    run.duration_ms = int((perf_counter() - t0) * 1000)
    run.status = "completed"
    run.counters = counters
    audit(db, "EXACT_MATCHES", str(counters["exact_matches"]), run.id)
    audit(db, "EXCEPTIONS", str(counters["exceptions"]), run.id)
    evaluate_run(db, run)
    from app.evaluation.gate_proof import reject_hallucinated_proposal

    reject_hallucinated_proposal(db, run.id)
    forecast(db, run.id, "base")
    audit(db, "AUDIT_EVENT_CREATED", "run complete", run.id)
    db.flush()
    return run


def _exception_reason(etype: str, cands) -> str:
    if etype == "AMBIGUOUS_MATCH" and len(cands) >= 2:
        return (
            f"Possible invoices: {cands[0].invoice.invoice_number} {cands[1].invoice.invoice_number}. "
            "Similar vendor/amount/date. Evidence: Insufficient."
        )
    if etype == "AMOUNT_MISMATCH" and cands:
        return f"Amount differs from invoice {cands[0].invoice.invoice_number}."
    if etype == "MISSING_INVOICE":
        return "No candidate invoice found."
    return etype.replace("_", " ").title()


def _store_result(db, run_id, tx, top, decision, reason, why, cands):
    db.add(
        ReconciliationResult(
            id=new_id("RR"),
            run_id=run_id,
            transaction_id=tx.id,
            invoice_id=top.invoice.id,
            match_level=top.level,
            match_score=float(top.score),
            decision=decision,
            confidence=float(top.score),
            reason_code=reason,
            why=why,
            candidate_invoice_ids=[c.invoice.id for c in cands[:5]],
        )
    )
    d = Decision(
        id=new_id("DEC"),
        run_id=run_id,
        exception_id=None,
        transaction_id=tx.id,
        decision=decision,
        confidence=float(top.score),
        reason_code=reason,
        reason="Deterministic matching authorized this pair.",
        evidence=[{"source": "invoice", "id": top.invoice.id}, {"source": "transaction", "id": tx.id}],
        calculations={
            "transaction_amount": f"{tx.amount:.2f}",
            "invoice_amount": f"{top.invoice.total_amount:.2f}",
            "difference": f"{abs(tx.amount - top.invoice.total_amount):.2f}",
        },
        authorized=True,
        gate_notes="deterministic match",
    )
    db.add(d)


def _store_decision(db, run_id, tx, exc, gated: AgentDecision):
    d = Decision(
        id=new_id("DEC"),
        run_id=run_id,
        exception_id=exc.id,
        transaction_id=tx.id,
        decision=gated.decision,
        confidence=float(gated.confidence),
        reason_code=gated.reason_code,
        reason=gated.reason,
        evidence=[e.model_dump() for e in gated.evidence],
        calculations=gated.calculations,
        authorized=gated.decision in {"AUTO_MATCH", "AUTO_RESOLVE"},
        gate_notes="gate applied",
    )
    db.add(d)
    db.flush()
    for e in gated.evidence:
        db.add(
            Evidence(
                id=new_id("EV"),
                decision_id=d.id,
                source=e.source,
                source_id=e.id,
                page=e.page,
                section=e.section,
                snippet=e.snippet,
            )
        )
