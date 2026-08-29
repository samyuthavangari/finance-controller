from sqlalchemy.orm import Session

from app.core.ids import new_id
from app.models import ReconciliationRun
from app.services.pipeline import close_books
from app.services.seed import generate_if_needed, index_qdrant, seed_from_bundle


def reset_and_seed(db: Session, n_transactions: int = 1000, investigate: bool = True) -> dict:
    data, gt = generate_if_needed(n_transactions)
    seed_from_bundle(db, data, gt, wipe=True)
    index_qdrant(data)
    run = ReconciliationRun(
        id=new_id("RUN"),
        job_id=new_id("JOB"),
        request_id=new_id("REQ"),
        status="queued",
    )
    db.add(run)
    db.flush()
    close_books(db, run, investigate_exceptions=investigate)
    db.commit()
    return {
        "run_id": run.id,
        "job_id": run.job_id,
        "status": run.status,
        "counters": run.counters,
        "duration_ms": run.duration_ms,
        "records": run.records_total,
        "cost": run.cost,
    }
