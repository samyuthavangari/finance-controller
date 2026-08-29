from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.models import BenchmarkRun, ExceptionRecord, GroundTruth, ReconciliationResult, ReconciliationRun


CAL_BUCKETS = [
    (0.95, 1.01, "95-100"),
    (0.90, 0.95, "90-95"),
    (0.80, 0.90, "80-90"),
    (0.70, 0.80, "70-80"),
    (0.0, 0.70, "<70"),
]


def evaluate_run(db: Session, run: ReconciliationRun) -> BenchmarkRun:
    gt_rows = {g.transaction_id: g for g in db.execute(select(GroundTruth)).scalars().all()}
    results = db.execute(select(ReconciliationResult).where(ReconciliationResult.run_id == run.id)).scalars().all()
    exceptions = db.execute(select(ExceptionRecord).where(ExceptionRecord.run_id == run.id)).scalars().all()
    exc_by_tx = {e.transaction_id: e for e in exceptions}

    tp = fp = fn = tn = 0
    match_correct = 0
    compared = 0
    auto = human = unresolved = extraction_fail = 0
    by_type = defaultdict(lambda: {"n": 0, "correct": 0})
    buckets = {label: {"n": 0, "correct": 0} for _, _, label in CAL_BUCKETS}

    matched_decisions = {"AUTO_MATCH", "AUTO_RESOLVE"}
    for r in results:
        compared += 1
        gt = gt_rows.get(r.transaction_id)
        predicted_match = r.decision in matched_decisions
        expected_match = bool(gt and gt.expected_status == "MATCH")
        if predicted_match and expected_match:
            tp += 1
        elif predicted_match and not expected_match:
            fp += 1
        elif (not predicted_match) and expected_match:
            fn += 1
        else:
            tn += 1
        if gt:
            inv_ok = (r.invoice_id == gt.expected_invoice_id) if gt.expected_invoice_id else r.invoice_id is None
            status_ok = (r.decision in matched_decisions) == (gt.expected_status == "MATCH")
            if gt.expected_status == "MATCH":
                correct = inv_ok
            else:
                correct = status_ok and r.decision not in matched_decisions
            if correct:
                match_correct += 1
            et = gt.expected_exception_type or "MATCH"
            by_type[et]["n"] += 1
            if correct:
                by_type[et]["correct"] += 1
        if r.decision in matched_decisions:
            auto += 1
        elif r.decision == "HUMAN_REVIEW":
            human += 1
        elif r.decision == "EXTRACTION_ERROR":
            extraction_fail += 1
        else:
            unresolved += 1
        conf = float(r.confidence)
        actual_ok = False
        if gt:
            if gt.expected_status == "MATCH":
                actual_ok = r.invoice_id == gt.expected_invoice_id and r.decision in matched_decisions
            else:
                actual_ok = r.decision not in matched_decisions
        for lo, hi, label in CAL_BUCKETS:
            if lo <= conf < hi:
                buckets[label]["n"] += 1
                if actual_ok:
                    buckets[label]["correct"] += 1
                break

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    n = max(compared, 1)
    duration_s = (run.duration_ms or 1) / 1000.0
    throughput = compared / duration_s if duration_s else 0.0

    exc_tp = exc_fp = exc_fn = 0
    for r in results:
        gt = gt_rows.get(r.transaction_id)
        has_exc = r.transaction_id in exc_by_tx
        expect_exc = bool(gt and gt.expected_exception_type)
        if has_exc and expect_exc:
            exc_tp += 1
        elif has_exc and not expect_exc:
            exc_fp += 1
        elif (not has_exc) and expect_exc:
            exc_fn += 1
    exc_precision = exc_tp / (exc_tp + exc_fp) if (exc_tp + exc_fp) else 0.0
    exc_recall = exc_tp / (exc_tp + exc_fn) if (exc_tp + exc_fn) else 0.0

    calibration = []
    for _, _, label in CAL_BUCKETS:
        b = buckets[label]
        acc = b["correct"] / b["n"] if b["n"] else None
        calibration.append({"bucket": label, "n": b["n"], "accuracy": acc})

    by_exc = {
        k: {"n": v["n"], "accuracy": (v["correct"] / v["n"] if v["n"] else 0.0)} for k, v in by_type.items()
    }

    cost = run.cost or {}
    metrics = {
        "records": compared,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "match_accuracy": match_correct / n,
        "false_positive_rate": fp / n,
        "false_negative_rate": fn / n,
        "auto_resolution_rate": auto / n,
        "human_review_rate": human / n,
        "unresolved_rate": unresolved / n,
        "extraction_error_rate": extraction_fail / n,
        "exception_precision": exc_precision,
        "exception_recall": exc_recall,
        "throughput_rps": throughput,
        "duration_ms": run.duration_ms,
        "llm_calls": cost.get("llm_calls", 0),
        "rag_calls": cost.get("rag_calls", 0),
        "deterministic_pct": cost.get("deterministic_pct", 0),
        "ai_assisted_pct": cost.get("ai_assisted_pct", 0),
        "llm_calls_saved_pct": cost.get("llm_calls_saved_pct", 0),
        "ocr_extraction_accuracy": cost.get("ocr_extraction_accuracy"),
        "avg_investigation_ms": cost.get("avg_investigation_ms"),
        "avg_llm_calls_per_exception": cost.get("avg_llm_calls_per_exception"),
        "avg_retrieval_latency_ms": cost.get("avg_retrieval_latency_ms"),
    }
    row = BenchmarkRun(
        id=new_id("BM"),
        run_id=run.id,
        metrics=metrics,
        calibration=calibration,
        by_exception_type=by_exc,
    )
    db.add(row)
    db.flush()
    return row
