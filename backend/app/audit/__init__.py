from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.ids import utcnow
from app.models import AuditLog


def audit(db: Session, event: str, detail: str, run_id: str | None = None, extra: dict | None = None) -> None:
    db.add(AuditLog(run_id=run_id, event=event, detail=detail, extra=extra or {}, ts=utcnow()))
    db.flush()


def serialize_audit(row: AuditLog) -> dict:
    ts: datetime = row.ts
    return {
        "id": row.id,
        "ts": ts.isoformat(),
        "run_id": row.run_id,
        "event": row.event,
        "detail": row.detail,
        "extra": row.extra or {},
    }


def money_str(v: Decimal) -> str:
    return f"{v:.2f}"
