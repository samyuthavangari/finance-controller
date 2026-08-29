import ssl

from celery import Celery

from app.config.settings import settings

celery_app = Celery(
    "finance_controller",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    broker_connection_retry_on_startup=True,
)
if settings.celery_broker_url.startswith("rediss://"):
    celery_app.conf.broker_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
    celery_app.conf.redis_backend_use_ssl = {"ssl_cert_reqs": ssl.CERT_REQUIRED}


@celery_app.task(name="reconciliation.run")
def run_reconciliation_task(run_id: str, investigate: bool = True) -> str:
    from app.db import SessionLocal
    from app.models import ReconciliationRun
    from app.services.pipeline import close_books

    db = SessionLocal()
    try:
        run = db.get(ReconciliationRun, run_id)
        if not run:
            return "missing"
        close_books(db, run, investigate_exceptions=investigate)
        db.commit()
        return run.status
    except Exception as exc:
        db.rollback()
        run = db.get(ReconciliationRun, run_id)
        if run:
            run.status = "failed"
            run.error = str(exc)
            db.commit()
        raise
    finally:
        db.close()
