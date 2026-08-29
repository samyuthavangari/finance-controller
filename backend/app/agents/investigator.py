import json
from time import perf_counter

from sqlalchemy.orm import Session

from app.agents import tools
from app.audit import audit
from app.config.policy import policy
from app.core.ids import new_id
from app.core.money import money
from app.models import ExceptionRecord, HistoricalCase, Investigation, InvestigationAction, Invoice, Transaction, Vendor
from app.providers import get_llm
from app.reconciliation.gate import authorize
from app.schemas.finance import AgentDecision, EvidenceItem

SYSTEM = """You are an investigation assistant for a finance controller.
You PROPOSE a decision. You do not calculate authoritative totals (they are provided).
You must not invent invoices, contracts, policies, or evidence IDs.
If evidence is insufficient, decision must be HUMAN_REVIEW.
Return JSON only matching the schema:
decision, confidence, reason_code, reason, evidence[{source,id,section,snippet}], calculations{string amounts}.
Allowed decisions: AUTO_RESOLVE, HUMAN_REVIEW, UNRESOLVED, REJECT.
"""


EVIDENCE_PLAN = {
    "AMOUNT_MISMATCH": ["invoice", "settlement", "contract", "payment_policy", "historical_case"],
    "TAX_MISMATCH": ["invoice", "tax_policy", "vendor", "historical_case"],
    "VENDOR_MISMATCH": ["vendor", "contract", "historical_case"],
    "DUPLICATE_PAYMENT": ["transaction", "settlement", "invoice"],
    "AMBIGUOUS_MATCH": ["invoice", "transaction", "historical_case"],
    "CURRENCY_MISMATCH": ["invoice", "payment_policy"],
    "MISSING_INVOICE": ["invoice", "vendor"],
    "OCR_CORRUPTION": ["invoice", "document"],
    "PARTIAL_PAYMENT": ["invoice", "settlement", "contract"],
}


def classify_exception(tx: Transaction, candidates: list, top_score: float) -> str:
    if len(candidates) >= 2 and abs(candidates[0].score - candidates[1].score) < 0.04:
        return "AMBIGUOUS_MATCH"
    if candidates and candidates[0].features.get("currency_match", 1) == 0:
        return "CURRENCY_MISMATCH"
    if candidates and candidates[0].features.get("amount_difference_percentage", 0) > float(policy.amount_pct):
        return "AMOUNT_MISMATCH"
    if candidates and candidates[0].features.get("vendor_similarity", 1) < 0.7:
        return "VENDOR_MISMATCH"
    if not candidates:
        return "MISSING_INVOICE"
    if top_score < policy.ambiguous:
        return "UNMATCHED"
    return "AMBIGUOUS_MATCH"


def investigate(db: Session, run_id: str, exc: ExceptionRecord, tx: Transaction, invoices: dict[str, Invoice]) -> AgentDecision:
    started = perf_counter()
    inv_row = Investigation(
        id=new_id("INVST"),
        exception_id=exc.id,
        run_id=run_id,
        status="running",
    )
    db.add(inv_row)
    db.flush()
    audit(db, "INVESTIGATION_STARTED", exc.id, run_id)

    actions = []
    facts = {
        "transaction": tools.search_transactions(db, id=tx.id),
        "invoices": [tools.search_invoice(db, id=i) for i in exc.candidate_invoice_ids[:3]],
        "vendor": tools.search_vendor(db, vendor_id=tx.vendor_id) if tx.vendor_id else [],
        "settlements": tools.search_settlement(db, vendor_id=tx.vendor_id, payment_reference=tx.payment_reference),
        "ledger": tools.search_ledger(db, reference=tx.payment_reference),
        "duplicates": tools.check_duplicate(db, tx),
    }
    _log(db, inv_row.id, "search_transactions", {"id": tx.id}, facts["transaction"])

    # Duplicates are a structural finding (same amount + currency + payment_reference).
    # There is nothing semantic to investigate — Gemini is reserved for judgment, not classification.
    if facts.get("duplicates"):
        proposed = AgentDecision(
            decision="HUMAN_REVIEW",
            confidence=0.9,
            reason_code="DUPLICATE_DETECTED",
            reason=(
                "Duplicate payment: identical amount, currency, and payment reference on "
                f"{facts['duplicates']}. Escalated without an LLM call."
            ),
            evidence=[EvidenceItem(source="transaction", id=tx.id)],
            calculations={},
        )
        known_ids = {("transaction", tx.id)}
        gated, authorized, notes = authorize(proposed, known_ids)
        inv_row.proposed = proposed.model_dump()
        inv_row.summary = gated.reason
        inv_row.llm_calls = 0
        inv_row.rag_calls = 0
        inv_row.duration_ms = int((perf_counter() - started) * 1000)
        inv_row.status = "done"
        audit(db, "DUPLICATE_SKIPPED_LLM", gated.reason, run_id)
        audit(db, "DECISION_VALIDATED", notes, run_id)
        return gated

    rag = []
    needed = EVIDENCE_PLAN.get(exc.exception_type, ["invoice", "payment_policy"])
    query = f"{exc.exception_type} {tx.vendor_name_raw} {tx.payment_reference or ''} amount {tx.amount}"
    if "contract" in needed or "vendor_contract" in needed:
        hits = tools.search_contract(query, tx.vendor_id)
        rag.extend(hits)
        _log(db, inv_row.id, "search_contract", {"vendor_id": tx.vendor_id}, hits)
        audit(db, "RETRIEVED_CONTRACT", str(len(hits)), run_id)
    if "payment_policy" in needed or "tax_policy" in needed:
        hits = tools.search_policy(query)
        rag.extend(hits)
        _log(db, inv_row.id, "search_policy", {}, hits)
        audit(db, "RETRIEVED_POLICY", str(len(hits)), run_id)
    if "historical_case" in needed:
        hits = tools.search_historical_exception(query, exc.exception_type)
        rag.extend(hits)
        _log(db, inv_row.id, "search_historical_exception", {"type": exc.exception_type}, hits)
        audit(db, "RETRIEVED_HISTORICAL_CASE", str(len(hits)), run_id)

    calcs = {}
    if facts["settlements"] and facts["invoices"] and facts["invoices"][0]:
        inv0 = facts["invoices"][0][0] if facts["invoices"][0] else None
        if inv0:
            calcs = tools.calculate_variance(money(inv0["total_amount"]), money(facts["settlements"][0]["amount"]))
            audit(db, "CALCULATED_VARIANCE", calcs.get("variance_percentage", ""), run_id)
            _log(db, inv_row.id, "calculate_variance", {}, calcs)

    known_ids: set[tuple[str, str]] = {("transaction", tx.id)}
    for iid in exc.candidate_invoice_ids:
        known_ids.add(("invoice", iid))
    for s in facts["settlements"]:
        known_ids.add(("settlement", s["id"]))
    for v in facts["vendor"]:
        known_ids.add(("vendor", v["id"]))
    known_ids.add(("policy", "SETTLEMENT_POLICY_02"))
    for h in rag:
        payload = h.get("payload") or {}
        known_ids.add((payload.get("document_type") or "document", payload.get("document_id") or h["id"]))
        if payload.get("document_type") == "vendor_contract":
            known_ids.add(("contract", payload.get("document_id") or h["id"]))
        if payload.get("document_type") == "payment_policy":
            known_ids.add(("policy", payload.get("document_id") or h["id"]))
        if payload.get("document_type") == "historical_case":
            known_ids.add(("historical_case", payload.get("document_id") or h["id"]))

    proposed = _rule_or_llm(exc, tx, facts, rag, calcs, known_ids)
    gated, authorized, notes = authorize(proposed, known_ids)
    inv_row.proposed = proposed.model_dump()
    inv_row.summary = gated.reason
    inv_row.llm_calls = 1 if proposed.reason_code not in {"CONTRACTUAL_VARIANCE", "DUPLICATE_DETECTED", "INSUFFICIENT_EVIDENCE"} and facts.get("_used_llm") else int(bool(facts.get("_used_llm")))
    inv_row.rag_calls = len([a for a in ["search_contract", "search_policy", "search_historical_exception"]])
    inv_row.duration_ms = int((perf_counter() - started) * 1000)
    inv_row.status = "done"
    audit(db, "DECISION", gated.decision, run_id, {"notes": notes, "authorized": authorized})
    audit(db, "DECISION_VALIDATED", notes, run_id)

    if authorized and gated.decision == "AUTO_RESOLVE":
        db.add(
            HistoricalCase(
                id=new_id("HC"),
                exception_type=exc.exception_type,
                vendor_id=tx.vendor_id,
                decision=gated.decision,
                reason=gated.reason,
                evidence=[e.model_dump() for e in gated.evidence],
                calculations=gated.calculations,
                narrative=f"Exception: {exc.exception_type}. Resolution: {gated.decision}. Reason: {gated.reason}",
            )
        )
        try:
            from app.rag.qdrant_store import upsert_chunks

            upsert_chunks(
                [
                    {
                        "id": abs(hash(exc.id)) % (10**9),
                        "text": f"{exc.exception_type} {gated.reason} {gated.calculations}",
                        "metadata": {
                            "document_type": "historical_case",
                            "document_id": exc.id,
                            "vendor_id": tx.vendor_id,
                            "exception_type": exc.exception_type,
                            "country": "IN",
                        },
                    }
                ]
            )
        except Exception:
            pass
    return gated


def _log(db, investigation_id, tool, args, result) -> None:
    preview = json.dumps(result, default=str)[:1500]
    db.add(
        InvestigationAction(
            id=new_id("ACT"),
            investigation_id=investigation_id,
            tool=tool,
            arguments=args,
            result_preview=preview,
        )
    )


def _rule_or_llm(exc, tx, facts, rag, calcs, known_ids) -> AgentDecision:
    # Deterministic contractual variance: never ask LLM
    if calcs and "variance_percentage" in calcs:
        var = money(calcs["variance_percentage"])
        vendor = facts["vendor"][0] if facts["vendor"] else None
        allowed = money(vendor["allowed_variance_pct"]) if vendor else money("2.00")
        contract_hit = next((h for h in rag if (h.get("payload") or {}).get("document_type") == "vendor_contract"), None)
        if var <= allowed and tx.currency == (facts["settlements"][0]["currency"] if facts["settlements"] else tx.currency):
            evidence = []
            if exc.candidate_invoice_ids:
                evidence.append(EvidenceItem(source="invoice", id=exc.candidate_invoice_ids[0]))
            evidence.append(EvidenceItem(source="transaction", id=tx.id))
            if vendor:
                evidence.append(EvidenceItem(source="vendor", id=vendor["id"], snippet=f"allowed_variance_pct={allowed}"))
            if contract_hit:
                payload = contract_hit["payload"]
                evidence.append(
                    EvidenceItem(
                        source="contract",
                        id=payload.get("document_id") or str(contract_hit["id"]),
                        section="4.2",
                        snippet=(payload.get("text") or "")[:240],
                    )
                )
            evidence.append(EvidenceItem(source="policy", id="SETTLEMENT_POLICY_02", section="auto-resolve variance"))
            return AgentDecision(
                decision="AUTO_RESOLVE",
                confidence=0.94 if contract_hit else 0.88,
                reason_code="CONTRACTUAL_VARIANCE",
                reason="Settlement variance is within contractual / vendor master tolerance.",
                evidence=evidence,
                calculations={**calcs, "allowed_variance_percentage": f"{allowed:.2f}"},
            )
    if facts.get("duplicates"):
        return AgentDecision(
            decision="HUMAN_REVIEW",
            confidence=0.9,
            reason_code="DUPLICATE_DETECTED",
            reason="Possible duplicate payment with same amount and reference.",
            evidence=[EvidenceItem(source="transaction", id=tx.id)],
            calculations={},
        )
    # Ambiguous / missing evidence: do not hallucinate
    if exc.exception_type in {"AMBIGUOUS_MATCH", "MISSING_INVOICE"} or len(exc.candidate_invoice_ids) > 1:
        evidence = [EvidenceItem(source="transaction", id=tx.id)]
        for iid in exc.candidate_invoice_ids[:3]:
            evidence.append(EvidenceItem(source="invoice", id=iid))
        return AgentDecision(
            decision="HUMAN_REVIEW",
            confidence=0.55,
            reason_code="AMBIGUOUS_CANDIDATES" if len(exc.candidate_invoice_ids) > 1 else "INSUFFICIENT_EVIDENCE",
            reason="Insufficient unique evidence to authorize a match.",
            evidence=evidence,
            calculations=calcs,
        )

    # Last resort: LLM proposes only; gate still authorizes
    try:
        llm = get_llm()
        prompt = json.dumps(
            {
                "exception": {"id": exc.id, "type": exc.exception_type, "reason": exc.reason},
                "facts": facts,
                "rag": rag,
                "calculations": calcs,
                "known_evidence_ids": [f"{a}:{b}" for a, b in list(known_ids)[:40]],
            },
            default=str,
        )
        facts["_used_llm"] = True
        raw = llm.generate(prompt, SYSTEM, json_mode=True)
        data = json.loads(raw)
        return AgentDecision.model_validate(data)
    except Exception:
        return AgentDecision(
            decision="HUMAN_REVIEW",
            confidence=0.4,
            reason_code="INSUFFICIENT_EVIDENCE",
            reason="Agent could not obtain sufficient verified evidence.",
            evidence=[EvidenceItem(source="transaction", id=tx.id)],
            calculations=calcs,
        )
