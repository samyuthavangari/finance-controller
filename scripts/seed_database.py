from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal
from app.services.seed import generate_if_needed, seed_from_bundle


if __name__ == "__main__":
    data, gt = generate_if_needed(1000)
    db = SessionLocal()
    try:
        seed_from_bundle(db, data, gt)
        db.commit()
        print("seeded", len(data["transactions"]), "transactions")
    finally:
        db.close()
