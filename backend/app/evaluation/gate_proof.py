"""Record what happens when an LLM proposes AUTO_RESOLVE without verifiable evidence."""

from app.audit import audit
from app.reconciliation.gate import authorize
from app.schemas.finance import AgentDecision, EvidenceItem


def reject_hallucinated_proposal(db, run_id: str) -> dict:
    """
    Simulates a model proposing AUTO_RESOLVE with a fabricated contract clause
    and internally inconsistent math. The gate must refuse. This is the proof
    that authorization is not the LLM's confidence score.
    """
    proposed = AgentDecision(
        decision="AUTO_RESOLVE",
        confidence=0.99,
        reason_code="CONTRACTUAL_VARIANCE",
        reason="Contract §99.1 allows unlimited settlement variance.",
        evidence=[
            EvidenceItem(source="contract", id="CONTRACT_HALLUCINATED_99", section="99.1", snippet="unlimited variance"),
            EvidenceItem(source="invoice", id="INV_0001"),
        ],
        calculations={
            "invoice_amount": "100000.00",
            "settlement_amount": "108000.00",
            "difference": "1000.00",
            "variance_percentage": "1.00",
        },
    )
    known = {("invoice", "INV_0001"), ("transaction", "TX_0001"), ("policy", "SETTLEMENT_POLICY_02")}
    gated, authorized, notes = authorize(proposed, known)
    audit(
        db,
        "GATE_REJECTED_HALLUCINATION",
        notes,
        run_id,
        extra={
            "proposed_decision": proposed.decision,
            "gated_decision": gated.decision,
            "authorized": authorized,
            "invented_evidence": "contract:CONTRACT_HALLUCINATED_99",
        },
    )
    return {
        "proposed": proposed.model_dump(),
        "gated_decision": gated.decision,
        "authorized": authorized,
        "gate_notes": notes,
    }
