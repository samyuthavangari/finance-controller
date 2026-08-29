from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal
from app.models import BenchmarkRun, ReconciliationRun
from sqlalchemy import select
from app.services.demo import reset_and_seed


def main():
    db = SessionLocal()
    try:
        out = reset_and_seed(db, 1000, True)
        db.commit()
        bm = db.execute(select(BenchmarkRun).order_by(BenchmarkRun.created_at.desc())).scalars().first()
        payload = {"run": out, "metrics": bm.metrics if bm else None, "calibration": bm.calibration if bm else None}
        dest = ROOT / "data" / "synthetic" / "last_benchmark.json"
        dest.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        print(json.dumps(payload, indent=2, default=str))
    finally:
        db.close()


if __name__ == "__main__":
    main()
