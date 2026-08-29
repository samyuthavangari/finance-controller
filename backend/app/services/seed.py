from datetime import date
from decimal import Decimal
from pathlib import Path
import json
import sys

from sqlalchemy.orm import Session

from app.config.settings import settings
from app.db import Base, engine
from app.models import (
    Document,
    GroundTruth,
    HistoricalCase,
    Invoice,
    InvoiceLineItem,
    LedgerEntry,
    Settlement,
    Transaction,
    User,
    Vendor,
)

ROOT = Path(__file__).resolve().parents[3]


def generate_if_needed(n: int) -> tuple[dict, list]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from generate_dataset import generate

    path = ROOT / "data" / "synthetic" / "dataset.json"
    meta = ROOT / "data" / "synthetic" / "meta.json"
    need = True
    if path.exists() and meta.exists():
        m = json.loads(meta.read_text(encoding="utf-8"))
        if m.get("n_transactions") == n:
            need = False
    if need:
        generate(n, settings.dataset_seed)
    data = json.loads(path.read_text(encoding="utf-8"))
    gt = json.loads((ROOT / "data" / "synthetic" / "ground_truth" / "labels.json").read_text(encoding="utf-8"))
    return data, gt


def seed_from_bundle(db: Session, data: dict, gt: list, wipe: bool = True) -> None:
    if wipe:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        db.expunge_all()
    db.add(User(id="USER_DEMO", email="controller@local", role="controller"))
    for v in data["vendors"]:
        db.add(
            Vendor(
                id=v["id"],
                legal_name=v["legal_name"],
                aliases=v["aliases"],
                country=v["country"],
                tax_id=v["tax_id"],
                bank_account=v["bank_account"],
                payment_terms_days=v["payment_terms_days"],
                allowed_variance_pct=Decimal(v["allowed_variance_pct"]),
            )
        )
    db.flush()
    for inv in data["invoices"]:
        db.add(
            Invoice(
                id=inv["id"],
                invoice_number=inv["invoice_number"],
                vendor_id=inv["vendor_id"],
                vendor_name_raw=inv["vendor_name_raw"],
                invoice_date=date.fromisoformat(inv["invoice_date"]),
                due_date=date.fromisoformat(inv["due_date"]) if inv.get("due_date") else None,
                currency=inv["currency"],
                subtotal=Decimal(inv["subtotal"]),
                tax_amount=Decimal(inv["tax_amount"]),
                total_amount=Decimal(inv["total_amount"]),
                payment_reference=inv.get("payment_reference"),
                bank_account=inv.get("bank_account"),
                status=inv.get("status", "open"),
            )
        )
    for li in data["invoice_line_items"]:
        db.add(
            InvoiceLineItem(
                id=li["id"],
                invoice_id=li["invoice_id"],
                description=li["description"],
                quantity=Decimal(li["quantity"]),
                unit_price=Decimal(li["unit_price"]),
                amount=Decimal(li["amount"]),
            )
        )
    for tx in data["transactions"]:
        db.add(
            Transaction(
                id=tx["id"],
                vendor_id=tx.get("vendor_id"),
                vendor_name_raw=tx["vendor_name_raw"],
                amount=Decimal(tx["amount"]),
                currency=tx["currency"],
                txn_date=date.fromisoformat(tx["txn_date"]),
                payment_reference=tx.get("payment_reference"),
                bank_reference=tx.get("bank_reference"),
                source=tx.get("source", "ledger"),
                status=tx.get("status", "pending"),
                description=tx.get("description"),
                extra=tx.get("extra") or {},
            )
        )
    for st in data["settlements"]:
        db.add(
            Settlement(
                id=st["id"],
                vendor_id=st.get("vendor_id"),
                amount=Decimal(st["amount"]),
                currency=st["currency"],
                settlement_date=date.fromisoformat(st["settlement_date"]),
                payment_reference=st.get("payment_reference"),
                invoice_id=st.get("invoice_id"),
                transaction_id=st.get("transaction_id"),
                status=st.get("status", "posted"),
            )
        )
    for le in data["ledger_entries"]:
        db.add(
            LedgerEntry(
                id=le["id"],
                account=le["account"],
                vendor_id=le.get("vendor_id"),
                amount=Decimal(le["amount"]),
                currency=le["currency"],
                entry_date=date.fromisoformat(le["entry_date"]),
                direction=le["direction"],
                reference=le.get("reference"),
                description=le.get("description"),
                status=le.get("status", "posted"),
            )
        )
    for hc in data["historical_cases"]:
        db.add(
            HistoricalCase(
                id=hc["id"],
                exception_type=hc["exception_type"],
                vendor_id=hc.get("vendor_id"),
                decision=hc["decision"],
                reason=hc["reason"],
                evidence=hc.get("evidence") or [],
                calculations=hc.get("calculations") or {},
                narrative=hc["narrative"],
            )
        )
    for g in gt:
        db.add(
            GroundTruth(
                id=g["id"],
                transaction_id=g["transaction_id"],
                expected_invoice_id=g.get("expected_invoice_id"),
                expected_status=g["expected_status"],
                expected_exception_type=g.get("expected_exception_type"),
            )
        )
    for p in data["policies"]:
        db.add(
            Document(
                id=p["id"],
                document_type=p["document_type"],
                filename=f"{p['id']}.txt",
                path=str(ROOT / "data" / "policies" / f"{p['id']}.txt"),
                mime_type="text/plain",
                country=p.get("country", "IN"),
                effective_date=date.fromisoformat(p["effective_date"]) if p.get("effective_date") else None,
            )
        )
    for c in data["contracts"]:
        db.add(
            Document(
                id=c["id"],
                document_type=c["document_type"],
                vendor_id=c.get("vendor_id"),
                filename=f"{c['id']}.txt",
                path=str(ROOT / "data" / "documents" / f"{c['id']}.txt"),
                mime_type="text/plain",
                country=c.get("country", "IN"),
                effective_date=date.fromisoformat(c["effective_date"]) if c.get("effective_date") else None,
            )
        )
    db.flush()


def index_qdrant(data: dict) -> None:
    from app.rag.qdrant_store import upsert_chunks

    points = []
    i = 1
    for doc in data["contracts"] + data["policies"] + data["historical_cases"]:
        points.append(
            {
                "id": i,
                "text": doc["text"],
                "metadata": {
                    "document_type": doc["document_type"],
                    "vendor_id": doc.get("vendor_id"),
                    "document_id": doc.get("document_id") or doc["id"],
                    "effective_date": doc.get("effective_date"),
                    "country": doc.get("country", "IN"),
                    "category": doc.get("category"),
                    "exception_type": doc.get("exception_type"),
                },
            }
        )
        i += 1
    try:
        upsert_chunks(points)
    except Exception:
        # Qdrant optional in unit tests
        pass
