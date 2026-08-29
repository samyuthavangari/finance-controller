from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.db import Base
from app.models import Invoice, Transaction, Vendor
from app.reconciliation.engine import match_transaction
from app.evaluation.engine import evaluate_run
from app.core.ids import new_id
from app.models import GroundTruth, ReconciliationResult, ReconciliationRun


def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_l0_exact_match():
    db = session()
    v = Vendor(id="V1", legal_name="Acme", aliases=["ACME"])
    db.add(v)
    inv = Invoice(
        id="INV_1",
        invoice_number="INV-1",
        vendor_id="V1",
        vendor_name_raw="Acme",
        invoice_date=date(2026, 1, 1),
        currency="INR",
        subtotal=Decimal("100.00"),
        tax_amount=Decimal("18.00"),
        total_amount=Decimal("118.00"),
        payment_reference="PAY-1",
    )
    tx = Transaction(
        id="TX_1",
        vendor_id="V1",
        vendor_name_raw="Acme",
        amount=Decimal("118.00"),
        currency="INR",
        txn_date=date(2026, 1, 2),
        payment_reference="INV-1",
        source="bank",
    )
    db.add_all([inv, tx])
    db.commit()
    cands = match_transaction(db, tx, [inv], {"V1": v})
    assert cands[0].level == "L0"
    assert cands[0].score >= 0.99


def test_evaluation_against_ground_truth():
    db = session()
    run = ReconciliationRun(id="RUN1", job_id="JOB1", request_id="REQ1", status="completed", duration_ms=1000, records_total=2)
    db.add(run)
    db.add(Transaction(id="T1", vendor_name_raw="A", amount=Decimal("10"), currency="INR", txn_date=date(2026, 1, 1)))
    db.add(Transaction(id="T2", vendor_name_raw="B", amount=Decimal("10"), currency="INR", txn_date=date(2026, 1, 1)))
    db.add(GroundTruth(id="G1", transaction_id="T1", expected_invoice_id="I1", expected_status="MATCH", expected_exception_type=None))
    db.add(GroundTruth(id="G2", transaction_id="T2", expected_invoice_id=None, expected_status="EXCEPTION", expected_exception_type="AMBIGUOUS_MATCH"))
    db.add(
        ReconciliationResult(
            id="R1",
            run_id="RUN1",
            transaction_id="T1",
            invoice_id="I1",
            match_level="L0",
            match_score=0.99,
            decision="AUTO_MATCH",
            confidence=0.99,
            reason_code="EXACT_MATCH",
            why={},
        )
    )
    db.add(
        ReconciliationResult(
            id="R2",
            run_id="RUN1",
            transaction_id="T2",
            invoice_id=None,
            match_level="NONE",
            match_score=0.4,
            decision="HUMAN_REVIEW",
            confidence=0.4,
            reason_code="INSUFFICIENT_EVIDENCE",
            why={},
        )
    )
    db.commit()
    bm = evaluate_run(db, run)
    assert bm.metrics["match_accuracy"] == 1.0
    assert bm.metrics["precision"] == 1.0
    assert 0.9 <= bm.metrics["recall"] <= 1.0
