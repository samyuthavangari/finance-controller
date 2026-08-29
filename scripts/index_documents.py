from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.db import SessionLocal
from app.services.seed import generate_if_needed, index_qdrant, seed_from_bundle


def main():
    data, gt = generate_if_needed(1000)
    db = SessionLocal()
    try:
        seed_from_bundle(db, data, gt)
        db.commit()
    finally:
        db.close()
    index_qdrant(data)
    print("indexed", len(data["contracts"]) + len(data["policies"]) + len(data["historical_cases"]), "chunks")


if __name__ == "__main__":
    main()
