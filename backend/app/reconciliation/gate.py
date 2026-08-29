from decimal import Decimal, InvalidOperation

from app.config.policy import policy
from app.core.money import money
from app.schemas.finance import AgentDecision


ALLOWED_DECISIONS = {
    "AUTO_MATCH",
    "AUTO_RESOLVE",
    "HUMAN_REVIEW",
    "UNRESOLVED",
    "REJECT",
    "EXTRACTION_ERROR",
}


def _calc_ok(claimed: dict[str, str]) -> tuple[bool, str]:
    try:
        keys = set(claimed)
        if {"invoice_amount", "settlement_amount", "difference"} <= keys:
            inv = money(claimed["invoice_amount"])
            stl = money(claimed["settlement_amount"])
            diff = money(claimed["difference"])
            if abs((stl - inv) - diff) > policy.amount_tolerance and abs((inv - stl) - diff) > policy.amount_tolerance:
                return False, "difference does not match invoice vs settlement"
        if {"invoice_amount", "settlement_amount", "variance_percentage"} <= keys:
            inv = money(claimed["invoice_amount"])
            stl = money(claimed["settlement_amount"])
            if inv == 0:
                return False, "invoice amount zero"
            actual = (abs(stl - inv) / inv) * Decimal("100")
            claimed_pct = Decimal(str(claimed["variance_percentage"]))
            if abs(actual - claimed_pct) > Decimal("0.05"):
                return False, "variance_percentage recomputed mismatch"
        return True, "ok"
    except (InvalidOperation, KeyError, ValueError) as exc:
        return False, f"calculation parse error: {exc}"


def authorize(proposed: AgentDecision, known_ids: set[tuple[str, str]]) -> tuple[AgentDecision, bool, str]:
    notes = []
    decision = proposed.decision
    if decision not in ALLOWED_DECISIONS:
        notes.append("unknown decision forced to HUMAN_REVIEW")
        decision = "HUMAN_REVIEW"
    if proposed.reason_code not in policy.allowed_reason_codes:
        notes.append("invalid reason_code")
        decision = "HUMAN_REVIEW"
    missing = []
    for ev in proposed.evidence:
        if (ev.source, ev.id) not in known_ids:
            missing.append(f"{ev.source}:{ev.id}")
    if policy.require_evidence and decision in {"AUTO_RESOLVE", "AUTO_MATCH"} and not proposed.evidence:
        notes.append("no evidence")
        decision = "HUMAN_REVIEW"
    if missing:
        notes.append("unknown evidence " + ",".join(missing))
        decision = "HUMAN_REVIEW"
    ok, calc_note = _calc_ok(proposed.calculations)
    if not ok:
        notes.append(calc_note)
        decision = "HUMAN_REVIEW"
    if decision in {"AUTO_RESOLVE", "AUTO_MATCH"} and proposed.confidence < policy.min_confidence_auto_resolve:
        notes.append("confidence below gate")
        decision = "HUMAN_REVIEW"
    authorized = decision in {"AUTO_MATCH", "AUTO_RESOLVE"}
    gated = proposed.model_copy(update={"decision": decision})
    return gated, authorized, "; ".join(notes) or "passed"
