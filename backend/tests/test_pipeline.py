from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Invoice, InvoiceLineItem, Transaction, Vendor
from app.services.pipeline import close_books
from app.models import ReconciliationRun


def test_close_books_small_batch():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(Vendor(id="V1", legal_name="Amazon Web Services", aliases=["AWS"], allowed_variance_pct=Decimal("2.00")))
    db.add(
        Invoice(
            id="INV_1",
            invoice_number="INV-1",
            vendor_id="V1",
            vendor_name_raw="Amazon Web Services",
            invoice_date=date(2026, 1, 1),
            currency="INR",
            subtotal=Decimal("100.00"),
            tax_amount=Decimal("18.00"),
            total_amount=Decimal("118.00"),
            payment_reference="PAY-1",
        )
    )
    db.add(
        InvoiceLineItem(
            id="LI1",
            invoice_id="INV_1",
            description="svc",
            quantity=Decimal("1"),
            unit_price=Decimal("100"),
            amount=Decimal("100"),
        )
    )
    db.add(
        Transaction(
            id="TX_1",
            vendor_id="V1",
            vendor_name_raw="AWS",
            amount=Decimal("118.00"),
            currency="INR",
            txn_date=date(2026, 1, 1),
            payment_reference="INV-1",
        )
    )
    db.add(
        Transaction(
            id="TX_2",
            vendor_id="V1",
            vendor_name_raw="AWS",
            amount=Decimal("99999.00"),
            currency="INR",
            txn_date=date(2026, 1, 1),
            payment_reference="NOPE",
        )
    )
    db.commit()
    run = ReconciliationRun(id="RUNX", job_id="JOBX", request_id="REQX", status="queued")
    db.add(run)
    db.commit()
    close_books(db, run, investigate_exceptions=False)
    assert run.status == "completed"
    assert run.counters["exact_matches"] + run.counters["normalized_matches"] >= 1
    assert run.counters["exceptions"] >= 1
