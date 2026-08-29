from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import serialize_audit
from app.config.policy import policy
from app.config.settings import settings
from app.core.ids import new_id, utcnow
from app.core.security import require_auth, validate_upload
from app.db import get_db
from app.forecasting.cash import forecast
from app.models import (
    AuditLog,
    BenchmarkRun,
    CashForecast,
    Decision,
    Document,
    Evidence,
    ExceptionRecord,
    HistoricalCase,
    Investigation,
    InvestigationAction,
    Invoice,
    ReconciliationResult,
    ReconciliationRun,
    Settlement,
    Transaction,
    Vendor,
)
from app.services.pipeline import close_books

router = APIRouter()


def _latest_run(db: Session) -> ReconciliationRun | None:
    return db.execute(select(ReconciliationRun).order_by(ReconciliationRun.started_at.desc().nullslast())).scalars().first()


@router.post("/datasets/upload")
def upload_dataset(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    data = file.file.read()
    validate_upload(file.filename or "upload.bin", file.content_type, len(data))
    dest_dir = Path(settings.upload_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "upload.bin").name
    path = dest_dir / f"{new_id('UP')}_{safe_name}"
    path.write_bytes(data)
    doc = Document(
        id=new_id("DOC"),
        document_type="upload",
        filename=safe_name,
        path=str(path),
        mime_type=file.content_type or "application/octet-stream",
    )
    db.add(doc)
    if safe_name.endswith(".json"):
        payload = json.loads(data.decode("utf-8"))
        return {"document_id": doc.id, "parsed_keys": list(payload)[:20] if isinstance(payload, dict) else "list"}
    return {"document_id": doc.id, "bytes": len(data)}


@router.post("/reconciliation/run")
def start_run(
    body: dict | None = None,
    db: Session = Depends(get_db),
    _: str = Depends(require_auth),
):
    body = body or {}
    investigate = bool(body.get("investigate", True))
    async_job = bool(body.get("async_job", False))
    run = ReconciliationRun(
        id=new_id("RUN"),
        job_id=new_id("JOB"),
        request_id=new_id("REQ"),
        status="queued",
    )
    db.add(run)
    db.flush()
    if async_job:
        from app.workers import run_reconciliation_task

        run_reconciliation_task.delay(run.id, investigate)
        return {"job_id": run.job_id, "run_id": run.id, "status": run.status, "request_id": run.request_id}
    close_books(db, run, investigate_exceptions=investigate)
    return {"job_id": run.job_id, "run_id": run.id, "status": run.status, "request_id": run.request_id, "counters": run.counters}


@router.get("/reconciliation/{job_id}")
def get_run(job_id: str, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    run = db.execute(select(ReconciliationRun).where(ReconciliationRun.job_id == job_id)).scalar_one_or_none()
    if not run:
        run = db.get(ReconciliationRun, job_id)
    if not run:
        raise HTTPException(404, "run not found")
    return _run_out(run)


@router.get("/reconciliation/{job_id}/results")
def get_results(job_id: str, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    run = _run_by_job(db, job_id)
    rows = db.execute(select(ReconciliationResult).where(ReconciliationResult.run_id == run.id)).scalars().all()
    return [_result_out(db, r) for r in rows]


@router.get("/exceptions")
def list_exceptions(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    rows = db.execute(select(ExceptionRecord).order_by(ExceptionRecord.id)).scalars().all()
    return [_exc_out(db, e) for e in rows]


@router.get("/exceptions/{exc_id}")
def get_exception(exc_id: str, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    e = db.get(ExceptionRecord, exc_id)
    if not e:
        raise HTTPException(404, "not found")
    inv = db.execute(select(Investigation).where(Investigation.exception_id == e.id)).scalars().first()
    actions = []
    if inv:
        actions = list(db.execute(select(InvestigationAction).where(InvestigationAction.investigation_id == inv.id)).scalars())
    tx = db.get(Transaction, e.transaction_id)
    invoices = [db.get(Invoice, i) for i in e.candidate_invoice_ids]
    decision = db.execute(select(Decision).where(Decision.exception_id == e.id)).scalars().first()
    return {
        **_exc_out(db, e),
        "transaction": _tx_out(tx) if tx else None,
        "invoices": [_inv_out(i) for i in invoices if i],
        "investigation": {
            "id": inv.id if inv else None,
            "summary": inv.summary if inv else None,
            "llm_calls": inv.llm_calls if inv else 0,
            "rag_calls": inv.rag_calls if inv else 0,
            "proposed": inv.proposed if inv else None,
            "actions": [
                {"tool": a.tool, "arguments": a.arguments, "result_preview": a.result_preview} for a in actions
            ],
        },
        "decision": _dec_out(decision) if decision else None,
    }


@router.post("/exceptions/{exc_id}/review")
def review_exception(exc_id: str, body: dict, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    e = db.get(ExceptionRecord, exc_id)
    if not e:
        raise HTTPException(404, "not found")
    decision = body.get("decision", "HUMAN_OVERRIDE")
    e.final_decision = decision
    e.recommended_action = decision
    return {"id": e.id, "final_decision": e.final_decision}


@router.get("/evidence/{ev_id}")
def get_evidence(ev_id: str, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    ev = db.get(Evidence, ev_id)
    if not ev:
        raise HTTPException(404, "not found")
    return {
        "id": ev.id,
        "source": ev.source,
        "source_id": ev.source_id,
        "page": ev.page,
        "section": ev.section,
        "snippet": ev.snippet,
    }


@router.get("/metrics")
def metrics(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    run = _latest_run(db)
    bm = None
    if run:
        bm = db.execute(select(BenchmarkRun).where(BenchmarkRun.run_id == run.id)).scalars().first()
    cash = db.execute(select(CashForecast).order_by(CashForecast.created_at.desc())).scalars().first()
    return {
        "run": _run_out(run) if run else None,
        "benchmark": bm.metrics if bm else None,
        "cash": cash.summary if cash else None,
        "cost": run.cost if run else None,
    }


@router.get("/benchmark")
def benchmark(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    bm = db.execute(select(BenchmarkRun).order_by(BenchmarkRun.created_at.desc())).scalars().first()
    if not bm:
        return {"metrics": None}
    return {
        "id": bm.id,
        "run_id": bm.run_id,
        "metrics": bm.metrics,
        "calibration": bm.calibration,
        "by_exception_type": bm.by_exception_type,
    }


@router.post("/stress-test")
def stress_test(body: dict, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    size = int(body.get("records", 500))
    if size not in {100, 500, 1000, 5000, 10000}:
        raise HTTPException(400, "records must be 100, 500, 1000, 5000, or 10000")
    from app.services.demo import reset_and_seed

    reset_and_seed(db, n_transactions=size, investigate=size <= 1000)
    run = _latest_run(db)
    bm = db.execute(select(BenchmarkRun).where(BenchmarkRun.run_id == run.id)).scalars().first() if run else None
    from app.core.memory import process_memory_kb

    return {
        "records": size,
        "run": _run_out(run) if run else None,
        "metrics": bm.metrics if bm else None,
        "memory_kb": process_memory_kb(),
    }


@router.get("/cash-position")
def cash_position(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    row = db.execute(select(CashForecast).order_by(CashForecast.created_at.desc())).scalars().first()
    if not row:
        return {
            "summary": None,
            "series": [],
            "scenario": "none",
            "hint": "Run DEMO or CLOSE BOOKS first — cash is computed after reconciliation.",
        }
    return {"summary": row.summary, "series": row.series, "scenario": row.scenario}


@router.post("/cash-position/simulate")
def simulate(body: dict, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    from decimal import Decimal

    run = _latest_run(db)
    row = forecast(
        db,
        run.id if run else None,
        scenario=body.get("scenario", "custom"),
        delay_receivables_days=int(body.get("delay_receivables_days", 0)),
        delay_settlement_days=int(body.get("delay_settlement_days", 0)),
        expense_increase_pct=Decimal(str(body.get("expense_increase_pct", 0))),
        early_collect=Decimal(str(body.get("early_collect", 0))),
    )
    return {"summary": row.summary, "series": row.series, "scenario": row.scenario}


@router.post("/demo/run")
def run_demo(db: Session = Depends(get_db), _: str = Depends(require_auth)):
    from app.services.demo import reset_and_seed

    result = reset_and_seed(db, n_transactions=200, investigate=True)
    return result


@router.post("/settlement/ask")
def settlement_ask(body: dict, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    from app.agents.settlement_qa import ask

    q = (body or {}).get("question") or ""
    if not str(q).strip():
        raise HTTPException(400, "question required")
    return ask(db, str(q))


@router.get("/transactions")
def list_tx(decision: str | None = None, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    q = select(ReconciliationResult)
    if decision:
        q = q.where(ReconciliationResult.decision == decision)
    rows = db.execute(q.limit(2000)).scalars().all()
    return [_result_out(db, r) for r in rows]


@router.get("/audit")
def list_audit(run_id: str | None = None, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    q = select(AuditLog).order_by(AuditLog.id)
    if run_id:
        q = q.where(AuditLog.run_id == run_id)
    return [serialize_audit(a) for a in db.execute(q.limit(2000)).scalars().all()]


@router.get("/graph/{transaction_id}")
def evidence_graph(transaction_id: str, db: Session = Depends(get_db), _: str = Depends(require_auth)):
    tx = db.get(Transaction, transaction_id)
    if not tx:
        raise HTTPException(404, "not found")
    result = db.execute(select(ReconciliationResult).where(ReconciliationResult.transaction_id == tx.id)).scalars().first()
    inv = db.get(Invoice, result.invoice_id) if result and result.invoice_id else None
    vendor = db.get(Vendor, tx.vendor_id) if tx.vendor_id else None
    stl = db.execute(select(Settlement).where(Settlement.transaction_id == tx.id)).scalars().first()
    decision = db.execute(select(Decision).where(Decision.transaction_id == tx.id)).scalars().first()
    hist = db.execute(select(HistoricalCase).where(HistoricalCase.vendor_id == tx.vendor_id)).scalars().first()
    nodes = [
        {"id": tx.id, "type": "bank_transaction", "label": tx.id, "data": _tx_out(tx)},
    ]
    edges = []
    if stl:
        nodes.append({"id": stl.id, "type": "settlement", "label": stl.id, "data": {"amount": str(stl.amount), "date": stl.settlement_date.isoformat()}})
        edges.append({"from": tx.id, "to": stl.id})
    if inv:
        nodes.append({"id": inv.id, "type": "invoice", "label": inv.invoice_number, "data": _inv_out(inv)})
        edges.append({"from": stl.id if stl else tx.id, "to": inv.id})
    if vendor:
        nodes.append({"id": vendor.id, "type": "vendor", "label": vendor.legal_name, "data": {"aliases": vendor.aliases}})
        if inv:
            edges.append({"from": inv.id, "to": vendor.id})
        nodes.append({"id": f"CONTRACT_{vendor.id}", "type": "contract", "label": f"Contract {vendor.id}", "data": {}})
        edges.append({"from": vendor.id, "to": f"CONTRACT_{vendor.id}"})
    nodes.append({"id": "SETTLEMENT_POLICY_02", "type": "policy", "label": "Settlement policy", "data": {}})
    if vendor:
        edges.append({"from": f"CONTRACT_{vendor.id}", "to": "SETTLEMENT_POLICY_02"})
    if hist:
        nodes.append({"id": hist.id, "type": "historical_exception", "label": hist.id, "data": {"reason": hist.reason}})
        edges.append({"from": "SETTLEMENT_POLICY_02", "to": hist.id})
    if decision:
        nodes.append({"id": decision.id, "type": "decision", "label": decision.decision, "data": _dec_out(decision)})
        edges.append({"from": hist.id if hist else "SETTLEMENT_POLICY_02", "to": decision.id})
    return {"nodes": nodes, "edges": edges}


def _run_by_job(db, job_id) -> ReconciliationRun:
    run = db.execute(select(ReconciliationRun).where(ReconciliationRun.job_id == job_id)).scalar_one_or_none()
    if not run:
        run = db.get(ReconciliationRun, job_id)
    if not run:
        raise HTTPException(404, "run not found")
    return run


def _run_out(run: ReconciliationRun) -> dict:
    return {
        "id": run.id,
        "job_id": run.job_id,
        "request_id": run.request_id,
        "status": run.status,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "duration_ms": run.duration_ms,
        "records_total": run.records_total,
        "progress_pct": run.progress_pct,
        "counters": run.counters,
        "error": run.error,
        "cost": run.cost,
    }


def _tx_out(tx: Transaction) -> dict:
    return {
        "id": tx.id,
        "vendor_id": tx.vendor_id,
        "vendor_name_raw": tx.vendor_name_raw,
        "amount": f"{tx.amount:.2f}",
        "currency": tx.currency,
        "date": tx.txn_date.isoformat(),
        "payment_reference": tx.payment_reference,
        "status": tx.status,
        "description": tx.description,
    }


def _inv_out(inv: Invoice) -> dict:
    return {
        "id": inv.id,
        "invoice_number": inv.invoice_number,
        "vendor_name_raw": inv.vendor_name_raw,
        "total_amount": f"{inv.total_amount:.2f}",
        "tax_amount": f"{inv.tax_amount:.2f}",
        "subtotal": f"{inv.subtotal:.2f}",
        "currency": inv.currency,
        "date": inv.invoice_date.isoformat(),
        "due_date": inv.due_date.isoformat() if inv.due_date else None,
        "payment_reference": inv.payment_reference,
    }


def _result_out(db: Session, r: ReconciliationResult) -> dict:
    tx = db.get(Transaction, r.transaction_id)
    inv = db.get(Invoice, r.invoice_id) if r.invoice_id else None
    return {
        "id": r.id,
        "transaction": _tx_out(tx) if tx else {"id": r.transaction_id},
        "invoice": _inv_out(inv) if inv else None,
        "vendor": tx.vendor_name_raw if tx else None,
        "amount": f"{tx.amount:.2f}" if tx else None,
        "date": tx.txn_date.isoformat() if tx else None,
        "match_level": r.match_level,
        "match_score": float(r.match_score),
        "decision": r.decision,
        "confidence": float(r.confidence),
        "reason_code": r.reason_code,
        "why": r.why,
        "candidate_invoice_ids": r.candidate_invoice_ids,
    }


def _exc_out(db: Session, e: ExceptionRecord) -> dict:
    tx = db.get(Transaction, e.transaction_id)
    return {
        "id": e.id,
        "transaction_id": e.transaction_id,
        "exception_type": e.exception_type,
        "amount": f"{e.amount:.2f}",
        "currency": e.currency,
        "candidate_invoice_ids": e.candidate_invoice_ids,
        "confidence": float(e.confidence),
        "reason": e.reason,
        "recommended_action": e.recommended_action,
        "final_decision": e.final_decision,
        "evidence": e.evidence,
        "vendor": tx.vendor_name_raw if tx else None,
        "date": tx.txn_date.isoformat() if tx else None,
    }


def _dec_out(d: Decision) -> dict:
    return {
        "id": d.id,
        "decision": d.decision,
        "confidence": float(d.confidence),
        "reason_code": d.reason_code,
        "reason": d.reason,
        "evidence": d.evidence,
        "calculations": d.calculations,
        "authorized": d.authorized,
        "gate_notes": d.gate_notes,
        "created_at": d.created_at.isoformat() if d.created_at else None,
    }
