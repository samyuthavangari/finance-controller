"""Run a reproducible batch, freeze match-rate numbers, and extract worked exception examples."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["DATABASE_URL"] = f"sqlite:///{(ROOT / 'data' / 'synthetic' / 'prove.db').as_posix()}"
os.environ["PROVE_SKIP_QDRANT"] = "1"
print("using", os.environ["DATABASE_URL"], flush=True)
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

from sqlalchemy import select  # noqa: E402

from app.db import SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    AuditLog,
    BenchmarkRun,
    Decision,
    ExceptionRecord,
    ReconciliationResult,
    ReconciliationRun,
    Transaction,
)
from app.services.seed import generate_if_needed, seed_from_bundle  # noqa: E402
from app.core.ids import new_id  # noqa: E402
from app.models import ReconciliationRun as RR  # noqa: E402
from app.services.pipeline import close_books  # noqa: E402


def main(n: int = 200) -> dict:
    data, gt = generate_if_needed(n)
    print("generated", n, "transactions", flush=True)
    from app.config.settings import settings

    print("engine url", settings.database_url, flush=True)
    db = SessionLocal()
    try:
        seed_from_bundle(db, data, gt, wipe=True)
        print("seeded", flush=True)
        if os.environ.get("PROVE_SKIP_QDRANT") != "1":
            try:
                from app.services.seed import index_qdrant

                index_qdrant(data)
                print("indexed qdrant", flush=True)
            except Exception as exc:
                print("qdrant skip", exc, flush=True)
        run = RR(id=new_id("RUN"), job_id=new_id("JOB"), request_id=new_id("REQ"), status="queued")
        db.add(run)
        db.flush()
        print("closing books", flush=True)
        close_books(db, run, investigate_exceptions=True)
        print("closed", run.status, run.duration_ms, flush=True)
        db.commit()

        bm = db.execute(select(BenchmarkRun).where(BenchmarkRun.run_id == run.id)).scalar_one()
        results = list(db.execute(select(ReconciliationResult).where(ReconciliationResult.run_id == run.id)).scalars())
        exceptions = list(db.execute(select(ExceptionRecord).where(ExceptionRecord.run_id == run.id)).scalars())
        decisions = list(db.execute(select(Decision).where(Decision.run_id == run.id)).scalars())

        resolved = next((d for d in decisions if d.decision == "AUTO_RESOLVE"), None)
        refused = next(
            (
                d
                for d in decisions
                if d.decision in {"HUMAN_REVIEW", "UNRESOLVED"}
                and d.reason_code in {"AMBIGUOUS_CANDIDATES", "INSUFFICIENT_EVIDENCE", "DUPLICATE_DETECTED"}
            ),
            None,
        )
        gate_audit = next((a for a in db.execute(select(AuditLog).where(AuditLog.event == "GATE_REJECTED_HALLUCINATION")).scalars()), None)

        def pack_decision(d: Decision | None):
            if not d:
                return None
            tx = db.get(Transaction, d.transaction_id)
            return {
                "transaction_id": d.transaction_id,
                "vendor": tx.vendor_name_raw if tx else None,
                "amount": f"{tx.amount:.2f}" if tx else None,
                "decision": d.decision,
                "reason_code": d.reason_code,
                "reason": d.reason,
                "confidence": float(d.confidence),
                "authorized": d.authorized,
                "gate_notes": d.gate_notes,
                "evidence": d.evidence,
                "calculations": d.calculations,
            }

        payload = {
            "seed": 42,
            "records": n,
            "run_id": run.id,
            "job_id": run.job_id,
            "duration_ms": run.duration_ms,
            "counters": run.counters,
            "cost": run.cost,
            "metrics": bm.metrics,
            "calibration": bm.calibration,
            "by_exception_type": bm.by_exception_type,
            "worked_auto_resolve": pack_decision(resolved),
            "worked_human_review": pack_decision(refused),
            "gate_rejected_hallucination": {
                "event": gate_audit.event if gate_audit else None,
                "detail": gate_audit.detail if gate_audit else None,
                "extra": gate_audit.extra if gate_audit else None,
            },
            "exception_sample": [
                {
                    "id": e.id,
                    "transaction_id": e.transaction_id,
                    "type": e.exception_type,
                    "amount": f"{e.amount:.2f}",
                    "decision": e.final_decision,
                    "reason": e.reason,
                    "candidates": e.candidate_invoice_ids,
                }
                for e in exceptions[:8]
            ],
        }
        out = ROOT / "data" / "synthetic" / "last_benchmark.json"
        out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        proof = ROOT / "docs" / "TRACK_PROOF.md"
        proof.parent.mkdir(parents=True, exist_ok=True)
        m = bm.metrics
        proof.write_text(_markdown(payload, m), encoding="utf-8")
        print(json.dumps({"records": n, "f1": m.get("f1"), "match_accuracy": m.get("match_accuracy"), "path": str(out)}, indent=2))
        return payload
    finally:
        db.close()


def _markdown(payload: dict, m: dict) -> str:
    wr = payload.get("worked_auto_resolve") or {}
    hu = payload.get("worked_human_review") or {}
    gate = payload.get("gate_rejected_hallucination") or {}
    c = payload.get("counters") or {}
    return f"""# Track proof — frozen run (seed 42)

These numbers were produced by `python scripts/prove_track.py`, not typed by hand.

| Metric | Value |
|---|---|
| Records | {payload.get("records")} |
| Match accuracy | {100 * (m.get("match_accuracy") or 0):.1f}% |
| Precision | {100 * (m.get("precision") or 0):.1f}% |
| Recall | {100 * (m.get("recall") or 0):.1f}% |
| F1 | {100 * (m.get("f1") or 0):.1f}% |
| Auto-resolution rate | {100 * (m.get("auto_resolution_rate") or 0):.1f}% |
| Human-review rate | {100 * (m.get("human_review_rate") or 0):.1f}% |
| Unresolved rate | {100 * (m.get("unresolved_rate") or 0):.1f}% |
| False positive rate | {100 * (m.get("false_positive_rate") or 0):.1f}% |
| Throughput | {(m.get("throughput_rps") or 0):.1f} records/sec |
| Duration | {payload.get("duration_ms")} ms |

Counters: exact {c.get("exact_matches")} · normalized {c.get("normalized_matches")} · ML {c.get("ml_matches")} · RAG-resolved {c.get("rag_resolved")} · human review {c.get("human_review")} · unresolved {c.get("unresolved")} · exceptions {c.get("exceptions")}.

## Worked case A — authorized (contractual variance)

Transaction `{wr.get("transaction_id")}` · ₹{wr.get("amount")} · {wr.get("vendor")}

- Decision: **{wr.get("decision")}** (`{wr.get("reason_code")}`)
- Authorized: `{wr.get("authorized")}`
- Confidence: {wr.get("confidence")}
- Calculations: `{wr.get("calculations")}`
- Evidence: `{wr.get("evidence")}`
- Reason: {wr.get("reason")}

## Worked case B — refused (honest exception)

Transaction `{hu.get("transaction_id")}` · ₹{hu.get("amount")} · {hu.get("vendor")}

- Decision: **{hu.get("decision")}** (`{hu.get("reason_code")}`)
- Authorized: `{hu.get("authorized")}`
- Reason: {hu.get("reason")}
- Evidence: `{hu.get("evidence")}`

## Worked case C — LLM hallucination rejected by the gate

A proposal of AUTO_RESOLVE with invented `CONTRACT_HALLUCINATED_99` and inconsistent Decimal math was submitted to the same gate.

- Gated extra: `{gate.get("extra")}`
- Notes: {gate.get("detail")}

The model is allowed to propose. It is not allowed to close the books.
"""


if __name__ == "__main__":
    n = 200
    if len(sys.argv) > 1:
        n = int(sys.argv[1])
    main(n)
