from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.money import money, pct
from app.models import HistoricalCase, Invoice, LedgerEntry, Settlement, Transaction, Vendor
from app.rag import qdrant_store


def search_transactions(db: Session, **kwargs) -> list[dict]:
    q = select(Transaction)
    if kwargs.get("vendor_id"):
        q = q.where(Transaction.vendor_id == kwargs["vendor_id"])
    if kwargs.get("payment_reference"):
        q = q.where(Transaction.payment_reference == kwargs["payment_reference"])
    if kwargs.get("id"):
        q = q.where(Transaction.id == kwargs["id"])
    rows = db.execute(q.limit(20)).scalars().all()
    return [_tx(r) for r in rows]


def search_invoice(db: Session, **kwargs) -> list[dict]:
    q = select(Invoice)
    if kwargs.get("id"):
        q = q.where(Invoice.id == kwargs["id"])
    if kwargs.get("invoice_number"):
        q = q.where(Invoice.invoice_number == kwargs["invoice_number"])
    if kwargs.get("vendor_id"):
        q = q.where(Invoice.vendor_id == kwargs["vendor_id"])
    rows = db.execute(q.limit(20)).scalars().all()
    return [_inv(r) for r in rows]


def search_vendor(db: Session, vendor_id: str | None = None, name: str | None = None) -> list[dict]:
    q = select(Vendor)
    if vendor_id:
        q = q.where(Vendor.id == vendor_id)
    rows = db.execute(q.limit(20)).scalars().all()
    out = [_vendor(r) for r in rows]
    if name:
        n = name.lower()
        out = [v for v in out if n in v["legal_name"].lower() or any(n in a.lower() for a in v["aliases"])]
    return out


def search_settlement(db: Session, **kwargs) -> list[dict]:
    q = select(Settlement)
    if kwargs.get("vendor_id"):
        q = q.where(Settlement.vendor_id == kwargs["vendor_id"])
    if kwargs.get("payment_reference"):
        q = q.where(Settlement.payment_reference == kwargs["payment_reference"])
    rows = db.execute(q.limit(20)).scalars().all()
    return [
        {
            "id": r.id,
            "amount": str(r.amount),
            "currency": r.currency,
            "date": r.settlement_date.isoformat(),
            "payment_reference": r.payment_reference,
            "invoice_id": r.invoice_id,
        }
        for r in rows
    ]


def search_ledger(db: Session, reference: str | None = None) -> list[dict]:
    q = select(LedgerEntry)
    if reference:
        q = q.where(LedgerEntry.reference == reference)
    rows = db.execute(q.limit(20)).scalars().all()
    return [
        {
            "id": r.id,
            "account": r.account,
            "amount": str(r.amount),
            "direction": r.direction,
            "date": r.entry_date.isoformat(),
            "reference": r.reference,
        }
        for r in rows
    ]


def search_policy(query: str, country: str = "IN") -> list[dict]:
    return qdrant_store.search(query, {"document_type": "payment_policy", "country": country}, limit=4)


def search_contract(query: str, vendor_id: str | None = None) -> list[dict]:
    filt = {"document_type": "vendor_contract"}
    if vendor_id:
        filt["vendor_id"] = vendor_id
    return qdrant_store.search(query, filt, limit=4)


def search_historical_exception(query: str, exception_type: str | None = None) -> list[dict]:
    filt = {"document_type": "historical_case"}
    if exception_type:
        filt["exception_type"] = exception_type
    return qdrant_store.search(query, filt, limit=4)


def calculate_variance(invoice_amount: Decimal, settlement_amount: Decimal) -> dict:
    inv = money(invoice_amount)
    stl = money(settlement_amount)
    diff = money(stl - inv)
    return {
        "invoice_amount": f"{inv:.2f}",
        "settlement_amount": f"{stl:.2f}",
        "difference": f"{diff:.2f}",
        "variance_percentage": str(pct(abs(diff), inv)),
    }


def check_duplicate(db: Session, tx: Transaction) -> list[str]:
    q = select(Transaction).where(
        Transaction.id != tx.id,
        Transaction.amount == tx.amount,
        Transaction.currency == tx.currency,
        Transaction.payment_reference == tx.payment_reference,
    )
    return [r.id for r in db.execute(q.limit(10)).scalars().all()]


def calculate_tax(subtotal: Decimal, tax: Decimal, total: Decimal) -> dict:
    expected = money(subtotal + tax)
    return {
        "expected_total": f"{expected:.2f}",
        "stated_total": f"{money(total):.2f}",
        "consistent": abs(expected - money(total)) <= money("0.50"),
    }


def compare_candidates(cands: list[dict]) -> dict:
    return {"count": len(cands), "ids": [c.get("id") for c in cands]}


def _tx(r: Transaction) -> dict:
    return {
        "id": r.id,
        "vendor_name_raw": r.vendor_name_raw,
        "amount": str(r.amount),
        "currency": r.currency,
        "date": r.txn_date.isoformat(),
        "payment_reference": r.payment_reference,
        "status": r.status,
    }


def _inv(r: Invoice) -> dict:
    return {
        "id": r.id,
        "invoice_number": r.invoice_number,
        "vendor_name_raw": r.vendor_name_raw,
        "total_amount": str(r.total_amount),
        "tax_amount": str(r.tax_amount),
        "currency": r.currency,
        "date": r.invoice_date.isoformat(),
        "payment_reference": r.payment_reference,
    }


def _vendor(r: Vendor) -> dict:
    return {
        "id": r.id,
        "legal_name": r.legal_name,
        "aliases": r.aliases or [],
        "allowed_variance_pct": str(r.allowed_variance_pct),
        "country": r.country,
        "tax_id": r.tax_id,
    }
