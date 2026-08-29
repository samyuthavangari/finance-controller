from datetime import date
from decimal import Decimal

from app.config.policy import policy
from app.core.money import money, pct
from app.extraction.pipeline import parse_invoice_from_text
from app.reconciliation.gate import authorize
from app.reconciliation.normalize import canonical_vendor, normalize_ref
from app.schemas.finance import AgentDecision, EvidenceItem
from app.agents.tools import calculate_tax, calculate_variance, check_duplicate


def test_money_decimal_not_float():
    assert money("10.1") + money("0.2") == money("10.30")
    assert pct(Decimal("2"), Decimal("200")) == Decimal("1.00")


def test_tax_calculation():
    r = calculate_tax(Decimal("100.00"), Decimal("18.00"), Decimal("118.00"))
    assert r["consistent"] is True
    r2 = calculate_tax(Decimal("100.00"), Decimal("18.00"), Decimal("150.00"))
    assert r2["consistent"] is False


def test_variance():
    v = calculate_variance(Decimal("106200.00"), Decimal("107500.00"))
    assert v["difference"] == "1300.00"
    assert v["variance_percentage"] == "1.22"


def test_invoice_extraction_inconsistent_raises():
    text = """
Invoice Number: INV-1
Vendor: Acme
Invoice Date: 2026-01-01
Currency: INR
Subtotal: 100.00
Tax: 18.00
Total: 999.00
ITEM | Widget | 1 | 100.00
"""
    try:
        parse_invoice_from_text(text, 0.9)
        assert False, "should raise"
    except ValueError as e:
        assert "EXTRACTION_ERROR" in str(e)


def test_invoice_extraction_ok():
    text = """
Invoice Number: INV-1
Vendor: Acme
Invoice Date: 2026-01-01
Currency: INR
Subtotal: 100.00
Tax: 18.00
Total: 118.00
ITEM | Widget | 1 | 100.00
"""
    inv = parse_invoice_from_text(text, 0.9)
    assert inv.invoice_number == "INV-1"
    assert inv.total_amount == money("118.00")


def test_vendor_aliases():
    assert canonical_vendor("AWS") == canonical_vendor("Amazon Web Services")
    assert canonical_vendor("AMAZON WEB SERVICES INDIA PVT LTD") == canonical_vendor("Amazon Web Services")


def test_normalize_ref():
    assert normalize_ref("INV-0001") == normalize_ref("inv0001")


def test_policy_bands():
    assert policy.band_for_score(0.99) == "AUTO_MATCH"
    assert policy.band_for_score(0.90) == "INVESTIGATE"
    assert policy.band_for_score(0.70) == "AMBIGUOUS"
    assert policy.band_for_score(0.2) == "UNMATCHED"


def test_decision_gate_rejects_invented_evidence():
    proposed = AgentDecision(
        decision="AUTO_RESOLVE",
        confidence=0.99,
        reason_code="CONTRACTUAL_VARIANCE",
        reason="ok",
        evidence=[EvidenceItem(source="contract", id="FAKE")],
        calculations={"invoice_amount": "100.00", "settlement_amount": "101.00", "difference": "1.00", "variance_percentage": "1.00"},
    )
    gated, authorized, notes = authorize(proposed, {("invoice", "INV_1")})
    assert gated.decision == "HUMAN_REVIEW"
    assert authorized is False


def test_decision_gate_rejects_bad_math():
    proposed = AgentDecision(
        decision="AUTO_RESOLVE",
        confidence=0.99,
        reason_code="CONTRACTUAL_VARIANCE",
        reason="ok",
        evidence=[EvidenceItem(source="invoice", id="INV_1")],
        calculations={"invoice_amount": "100.00", "settlement_amount": "101.00", "difference": "50.00", "variance_percentage": "1.00"},
    )
    gated, authorized, _ = authorize(proposed, {("invoice", "INV_1")})
    assert gated.decision == "HUMAN_REVIEW"
    assert authorized is False


def test_gate_rejects_hallucinated_contract_and_bad_math():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.db import Base
    from app.evaluation.gate_proof import reject_hallucinated_proposal

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    out = reject_hallucinated_proposal(db, "RUN_TEST")
    assert out["authorized"] is False
    assert out["gated_decision"] == "HUMAN_REVIEW"
    assert "unknown evidence" in out["gate_notes"]
