"""
Comprehensive test suite covering:
- Gate rejection of hallucinated evidence
- Duplicate detection (no LLM path)
- Ambiguity gap guard in matching engine
- Cash forecaster Decimal correctness
- DATE_MISMATCH deterministic rule
- TAX_MISMATCH deterministic rule
"""

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import (
    Invoice,
    InvoiceLineItem,
    ReconciliationRun,
    Transaction,
    Vendor,
)


# ── helpers ────────────────────────────────────────────────────────────────────

def _make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def _vendor(db, vid="V1"):
    v = Vendor(id=vid, legal_name="Amazon Web Services", aliases=["AWS"], allowed_variance_pct=Decimal("2.00"))
    db.add(v)
    return v


def _invoice(db, inv_id, vendor_id, amount, date_, ref, currency="INR", tax=None):
    subtotal = amount - (tax or Decimal("0"))
    inv = Invoice(
        id=inv_id,
        invoice_number=inv_id,
        vendor_id=vendor_id,
        vendor_name_raw="Amazon Web Services",
        invoice_date=date_,
        currency=currency,
        subtotal=subtotal,
        tax_amount=tax or Decimal("0"),
        total_amount=amount,
        payment_reference=ref,
    )
    db.add(inv)
    db.add(InvoiceLineItem(id=f"LI_{inv_id}", invoice_id=inv_id, description="svc",
                           quantity=Decimal("1"), unit_price=subtotal, amount=subtotal))
    return inv


def _transaction(db, tx_id, vendor_id, amount, date_, ref, currency="INR"):
    tx = Transaction(id=tx_id, vendor_id=vendor_id, vendor_name_raw="AWS",
                     amount=amount, currency=currency, txn_date=date_, payment_reference=ref)
    db.add(tx)
    return tx


# ── 1. Gate: reject hallucinated evidence ──────────────────────────────────────

def test_gate_rejects_hallucinated_evidence():
    from app.reconciliation.gate import authorize
    from app.schemas.finance import AgentDecision, EvidenceItem

    proposed = AgentDecision(
        decision="AUTO_RESOLVE",
        confidence=0.95,
        reason_code="CONTRACTUAL_VARIANCE",
        reason="Variance ok.",
        evidence=[EvidenceItem(source="contract", id="CONTRACT_HALLUCINATED_99")],
        calculations={"invoice_amount": "100.00", "settlement_amount": "101.00", "difference": "1.00"},
    )
    known_ids = {("transaction", "TX_001"), ("invoice", "INV_001")}
    gated, authorized, notes = authorize(proposed, known_ids)
    assert not authorized, "Gate should reject hallucinated contract reference"
    assert gated.decision == "HUMAN_REVIEW"
    assert "CONTRACT_HALLUCINATED_99" in notes


# ── 2. Gate: passes valid evidence ────────────────────────────────────────────

def test_gate_passes_valid_decision():
    from app.reconciliation.gate import authorize
    from app.schemas.finance import AgentDecision, EvidenceItem

    proposed = AgentDecision(
        decision="AUTO_RESOLVE",
        confidence=0.95,
        reason_code="CONTRACTUAL_VARIANCE",
        reason="Within tolerance.",
        evidence=[
            EvidenceItem(source="invoice", id="INV_001"),
            EvidenceItem(source="transaction", id="TX_001"),
        ],
        calculations={"invoice_amount": "100.00", "settlement_amount": "101.00", "difference": "1.00"},
    )
    known_ids = {("invoice", "INV_001"), ("transaction", "TX_001")}
    gated, authorized, notes = authorize(proposed, known_ids)
    assert authorized
    assert gated.decision == "AUTO_RESOLVE"


# ── 3. Gate: rejects bad math ─────────────────────────────────────────────────

def test_gate_rejects_wrong_calculations():
    from app.reconciliation.gate import authorize
    from app.schemas.finance import AgentDecision, EvidenceItem

    proposed = AgentDecision(
        decision="AUTO_RESOLVE",
        confidence=0.95,
        reason_code="CONTRACTUAL_VARIANCE",
        reason="Fine.",
        evidence=[EvidenceItem(source="invoice", id="INV_001"), EvidenceItem(source="transaction", id="TX_001")],
        # Wrong: 101 - 100 = 1, not 5
        calculations={"invoice_amount": "100.00", "settlement_amount": "101.00", "difference": "5.00"},
    )
    known_ids = {("invoice", "INV_001"), ("transaction", "TX_001")}
    gated, authorized, notes = authorize(proposed, known_ids)
    assert not authorized
    assert "difference" in notes


# ── 4. Duplicate detection (no LLM) ───────────────────────────────────────────

def test_duplicate_detection():
    from app.agents.tools import check_duplicate

    db = _make_db()
    _vendor(db)
    _invoice(db, "INV_1", "V1", Decimal("118.00"), date(2026, 1, 1), "PAY-1")
    t1 = _transaction(db, "TX_1", "V1", Decimal("118.00"), date(2026, 1, 1), "PAY-DUPE")
    t2 = _transaction(db, "TX_2", "V1", Decimal("118.00"), date(2026, 1, 2), "PAY-DUPE")
    db.commit()

    dupes = check_duplicate(db, t1)
    assert "TX_2" in dupes


# ── 5. No duplicate when reference differs ────────────────────────────────────

def test_no_false_duplicate():
    from app.agents.tools import check_duplicate

    db = _make_db()
    _vendor(db)
    t1 = _transaction(db, "TX_1", "V1", Decimal("118.00"), date(2026, 1, 1), "REF-AAA")
    _transaction(db, "TX_2", "V1", Decimal("118.00"), date(2026, 1, 2), "REF-BBB")
    db.commit()

    dupes = check_duplicate(db, t1)
    assert "TX_2" not in dupes


# ── 6. Ambiguity gap guard ────────────────────────────────────────────────────

def test_ambiguity_gap_guard_demotes_close_scores():
    from app.reconciliation.engine import match_transaction, build_indexes

    db = _make_db()
    _vendor(db)
    inv1 = _invoice(db, "INV_A", "V1", Decimal("500.00"), date(2026, 1, 1), "REF-X")
    inv2 = _invoice(db, "INV_B", "V1", Decimal("500.00"), date(2026, 1, 2), "REF-Y")
    tx = _transaction(db, "TX_AMB", "V1", Decimal("500.00"), date(2026, 1, 1), "REF-X")
    db.commit()

    vendors = {"V1": db.get(Vendor, "V1")}
    invoices = [inv1, inv2]
    by_ref, by_vendor = build_indexes(invoices)
    scored = match_transaction(db, tx, invoices, vendors, by_ref, by_vendor)

    assert scored[0].score < 0.98, (
        f"Ambiguity guard should demote top score when candidates are close; got {scored[0].score}"
    )


# ── 7. Cash forecaster: Decimal correctness ───────────────────────────────────

def test_cash_forecast_series_length_and_parseable():
    from app.forecasting.cash import forecast

    db = _make_db()
    db.commit()
    result = forecast(db, run_id=None, scenario="base", horizon=7)

    assert result is not None
    assert len(result.series) == 8  # 0..7 inclusive
    for entry in result.series:
        Decimal(entry["cash"])  # must not raise


# ── 8. Cash forecaster: uniform daily deduction (no duplicate branch bug) ────

def test_cash_forecast_uniform_daily_deduction():
    from app.forecasting.cash import forecast

    db = _make_db()
    db.commit()
    r = forecast(db, run_id=None, scenario="base", horizon=3)
    drops = [
        Decimal(r.series[i]["cash"]) - Decimal(r.series[i + 1]["cash"])
        for i in range(3)
    ]
    # All drops should be the same within floating-point rounding
    assert abs(drops[0] - drops[1]) < Decimal("0.01"), (
        f"Expense deduction should be uniform: {drops}"
    )
    assert abs(drops[1] - drops[2]) < Decimal("0.01")


# ── 9. DATE_MISMATCH: within grace → AUTO_RESOLVE ────────────────────────────

def test_date_mismatch_within_grace_resolves():
    from app.agents.investigator import _rule_or_llm
    from app.models import ExceptionRecord

    db = _make_db()
    _vendor(db)
    inv = _invoice(db, "INV_D1", "V1", Decimal("200.00"), date(2026, 1, 1), "REF-D")
    tx = _transaction(db, "TX_D1", "V1", Decimal("200.00"), date(2026, 1, 5), "REF-D")
    db.commit()

    exc = ExceptionRecord(
        id="EX_D1", run_id="R1", transaction_id="TX_D1",
        exception_type="DATE_MISMATCH", amount=Decimal("200.00"), currency="INR",
        candidate_invoice_ids=["INV_D1"], confidence=0.7,
        reason="Date differs", recommended_action="HUMAN_REVIEW", final_decision="OPEN", evidence=[],
    )

    facts = {
        "transaction": [{"id": "TX_D1", "amount": "200.00", "currency": "INR", "date": "2026-01-05"}],
        "invoices": [[{"id": "INV_D1", "total_amount": "200.00", "tax_amount": "0.00",
                       "currency": "INR", "date": "2026-01-01"}]],
        "vendor": [{"id": "V1", "legal_name": "AWS", "aliases": [], "allowed_variance_pct": "2.00"}],
        "settlements": [], "ledger": [], "duplicates": [],
    }

    result = _rule_or_llm(exc, tx, facts, [], {}, {("transaction", "TX_D1"), ("invoice", "INV_D1")})
    assert result.decision == "AUTO_RESOLVE", f"4-day gap should auto-resolve: got {result.decision}"
    assert result.reason_code == "CONTRACTUAL_VARIANCE"
    assert "date_gap_days" in result.calculations


# ── 10. DATE_MISMATCH: exceeds grace → HUMAN_REVIEW ─────────────────────────

def test_date_mismatch_exceeds_grace_escalates():
    from app.agents.investigator import _rule_or_llm
    from app.models import ExceptionRecord

    db = _make_db()
    _vendor(db)
    inv = _invoice(db, "INV_D2", "V1", Decimal("200.00"), date(2026, 1, 1), "REF-D2")
    tx = _transaction(db, "TX_D2", "V1", Decimal("200.00"), date(2026, 1, 20), "REF-D2")
    db.commit()

    exc = ExceptionRecord(
        id="EX_D2", run_id="R1", transaction_id="TX_D2",
        exception_type="DATE_MISMATCH", amount=Decimal("200.00"), currency="INR",
        candidate_invoice_ids=["INV_D2"], confidence=0.6,
        reason="Date differs", recommended_action="HUMAN_REVIEW", final_decision="OPEN", evidence=[],
    )

    facts = {
        "transaction": [{"id": "TX_D2", "amount": "200.00", "currency": "INR", "date": "2026-01-20"}],
        "invoices": [[{"id": "INV_D2", "total_amount": "200.00", "tax_amount": "0.00",
                       "currency": "INR", "date": "2026-01-01"}]],
        "vendor": [], "settlements": [], "ledger": [], "duplicates": [],
    }

    result = _rule_or_llm(exc, tx, facts, [], {}, {("transaction", "TX_D2"), ("invoice", "INV_D2")})
    assert result.decision == "HUMAN_REVIEW", f"19-day gap should escalate: got {result.decision}"


# ── 11. TAX_MISMATCH: consistent → AUTO_RESOLVE ──────────────────────────────

def test_tax_mismatch_consistent_resolves():
    from app.agents.investigator import _rule_or_llm
    from app.models import ExceptionRecord

    db = _make_db()
    _vendor(db)
    inv = _invoice(db, "INV_T1", "V1", Decimal("118.00"), date(2026, 1, 1), "REF-T", tax=Decimal("18.00"))
    tx = _transaction(db, "TX_T1", "V1", Decimal("100.00"), date(2026, 1, 1), "REF-T")
    db.commit()

    exc = ExceptionRecord(
        id="EX_T1", run_id="R1", transaction_id="TX_T1",
        exception_type="TAX_MISMATCH", amount=Decimal("100.00"), currency="INR",
        candidate_invoice_ids=["INV_T1"], confidence=0.6,
        reason="Tax mismatch", recommended_action="HUMAN_REVIEW", final_decision="OPEN", evidence=[],
    )

    facts = {
        "transaction": [{"id": "TX_T1", "amount": "100.00", "currency": "INR", "date": "2026-01-01"}],
        "invoices": [[{"id": "INV_T1", "total_amount": "118.00", "tax_amount": "18.00",
                       "currency": "INR", "date": "2026-01-01"}]],
        "vendor": [], "settlements": [], "ledger": [], "duplicates": [],
    }

    result = _rule_or_llm(exc, tx, facts, [], {}, {("transaction", "TX_T1"), ("invoice", "INV_T1")})
    assert result.decision == "AUTO_RESOLVE", f"Consistent tax should auto-resolve: got {result.decision}"
    assert result.reason_code == "TAX_POLICY_MATCH"
    assert "is_internally_consistent" in result.calculations


# ── 12. TAX_MISMATCH: inconsistent → HUMAN_REVIEW ───────────────────────────

def test_tax_mismatch_inconsistent_escalates():
    from app.agents.investigator import _rule_or_llm
    from app.models import ExceptionRecord

    db = _make_db()
    _vendor(db)
    # subtotal=100 + tax=18 = 118, but total stated as 150 — broken
    inv = Invoice(
        id="INV_T2", invoice_number="INV_T2", vendor_id="V1",
        vendor_name_raw="AWS", invoice_date=date(2026, 1, 1),
        currency="INR", subtotal=Decimal("100.00"), tax_amount=Decimal("18.00"),
        total_amount=Decimal("150.00"), payment_reference="REF-T2",
    )
    db.add(inv)
    tx = _transaction(db, "TX_T2", "V1", Decimal("150.00"), date(2026, 1, 1), "REF-T2")
    db.commit()

    exc = ExceptionRecord(
        id="EX_T2", run_id="R1", transaction_id="TX_T2",
        exception_type="TAX_MISMATCH", amount=Decimal("150.00"), currency="INR",
        candidate_invoice_ids=["INV_T2"], confidence=0.5,
        reason="Tax mismatch", recommended_action="HUMAN_REVIEW", final_decision="OPEN", evidence=[],
    )

    facts = {
        "transaction": [{"id": "TX_T2", "amount": "150.00", "currency": "INR", "date": "2026-01-01"}],
        "invoices": [[{"id": "INV_T2", "total_amount": "150.00", "tax_amount": "18.00",
                       "currency": "INR", "date": "2026-01-01"}]],
        "vendor": [], "settlements": [], "ledger": [], "duplicates": [],
    }

    result = _rule_or_llm(exc, tx, facts, [], {}, {("transaction", "TX_T2"), ("invoice", "INV_T2")})
    assert result.decision == "HUMAN_REVIEW", f"Broken tax should escalate: got {result.decision}"
    assert result.reason_code == "EXTRACTION_INCONSISTENT"
