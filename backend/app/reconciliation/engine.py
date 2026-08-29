from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from rapidfuzz import fuzz
from sqlalchemy.orm import Session

from app.config.policy import policy
from app.core.money import money, pct
from app.models import Invoice, Transaction, Vendor
from app.providers import get_matching_model
from app.reconciliation.normalize import canonical_vendor, normalize_ref, normalize_text


@dataclass
class Candidate:
    invoice: Invoice
    score: float
    level: str
    features: dict = field(default_factory=dict)
    checks: dict = field(default_factory=dict)


def _date_diff(a: date | None, b: date | None) -> int:
    if not a or not b:
        return 30
    return abs((a - b).days)


def _amount_features(tx: Transaction, inv: Invoice) -> dict:
    diff = abs(money(tx.amount) - money(inv.total_amount))
    return {
        "amount_difference": float(diff),
        "amount_difference_percentage": float(diff / money(inv.total_amount) if inv.total_amount else 1),
    }


def _vendor_sim(tx: Transaction, inv: Invoice, vendor: Vendor | None) -> float:
    a = canonical_vendor(tx.vendor_name_raw)
    b = canonical_vendor(inv.vendor_name_raw)
    if a and a == b:
        return 1.0
    if vendor:
        aliases = [canonical_vendor(vendor.legal_name), *[canonical_vendor(x) for x in (vendor.aliases or [])]]
        if a in aliases and b in aliases:
            return 0.97
    return fuzz.token_set_ratio(a, b) / 100.0


def score_pair(tx: Transaction, inv: Invoice, vendor: Vendor | None, hist_rate: float) -> Candidate:
    checks = {
        "invoice_id": bool(tx.payment_reference and normalize_ref(tx.payment_reference) == normalize_ref(inv.invoice_number)),
        "payment_reference": bool(
            tx.payment_reference
            and inv.payment_reference
            and normalize_ref(tx.payment_reference) == normalize_ref(inv.payment_reference)
        ),
        "exact_amount": money(tx.amount) == money(inv.total_amount),
        "exact_currency": tx.currency == inv.currency,
        "vendor": _vendor_sim(tx, inv, vendor) >= 0.9,
        "date_within_tolerance": _date_diff(tx.txn_date, inv.invoice_date) <= policy.date_days,
    }
    amt = _amount_features(tx, inv)
    features = {
        "vendor_similarity": _vendor_sim(tx, inv, vendor),
        **amt,
        "date_difference": float(_date_diff(tx.txn_date, inv.invoice_date)),
        "invoice_reference_similarity": fuzz.ratio(
            normalize_ref(tx.payment_reference), normalize_ref(inv.invoice_number) or normalize_ref(inv.payment_reference)
        )
        / 100.0,
        "currency_match": 1.0 if tx.currency == inv.currency else 0.0,
        "bank_reference_similarity": fuzz.ratio(normalize_ref(tx.bank_reference), normalize_ref(inv.bank_account)) / 100.0,
        "historical_vendor_match_rate": hist_rate,
    }

    if checks["invoice_id"] and checks["exact_amount"] and checks["exact_currency"]:
        return Candidate(inv, 0.999, "L0", features, checks)
    if checks["payment_reference"] and checks["exact_amount"] and checks["exact_currency"]:
        return Candidate(inv, 0.995, "L0", features, checks)
    # L1: vendor + exact amount + currency + date AND at least one reference signal
    # to prevent same-vendor/same-amount collisions from false-matching
    ref_signal = checks["invoice_id"] or checks["payment_reference"] or features["invoice_reference_similarity"] >= 0.7
    if checks["vendor"] and checks["exact_amount"] and checks["exact_currency"] and checks["date_within_tolerance"] and ref_signal:
        return Candidate(inv, 0.985, "L1", features, checks)
    # L1 without reference: demote to 0.965 so gate can separate from ambiguous
    if checks["vendor"] and checks["exact_amount"] and checks["exact_currency"] and checks["date_within_tolerance"]:
        return Candidate(inv, 0.965, "L1", features, checks)

    # L2: tighter amount tolerance (2% not 5%) and higher fuzzy floor (0.94)
    fuzzy = (
        0.35 * features["vendor_similarity"]
        + 0.30 * (1 - min(1.0, features["amount_difference_percentage"] / 0.02))
        + 0.20 * features["invoice_reference_similarity"]
        + 0.15 * (1 - min(1.0, features["date_difference"] / 14))
    )
    if fuzzy >= 0.94 and features["currency_match"] == 1.0:
        return Candidate(inv, min(0.97, fuzzy), "L2", features, checks)

    ml = get_matching_model().predict_proba(features)
    return Candidate(inv, ml, "L3", features, checks)


def shortlist(tx: Transaction, invoices: list[Invoice], by_ref: dict[str, list[Invoice]], by_vendor: dict[str, list[Invoice]]) -> list[Invoice]:
    picked: dict[str, Invoice] = {}
    ref = normalize_ref(tx.payment_reference)
    for inv in by_ref.get(ref, []):
        picked[inv.id] = inv
    if tx.vendor_id:
        for inv in by_vendor.get(tx.vendor_id, [])[:40]:
            picked[inv.id] = inv
    if len(picked) < 8:
        for inv in invoices[:80]:
            if abs(float(inv.total_amount - tx.amount)) / float(inv.total_amount or 1) < 0.15:
                picked[inv.id] = inv
            if len(picked) >= 40:
                break
    return list(picked.values()) or invoices[:20]


def build_indexes(invoices: list[Invoice]) -> tuple[dict[str, list[Invoice]], dict[str, list[Invoice]]]:
    by_ref: dict[str, list[Invoice]] = {}
    by_vendor: dict[str, list[Invoice]] = {}
    for inv in invoices:
        by_ref.setdefault(normalize_ref(inv.invoice_number), []).append(inv)
        by_ref.setdefault(normalize_ref(inv.payment_reference), []).append(inv)
        if inv.vendor_id:
            by_vendor.setdefault(inv.vendor_id, []).append(inv)
    return by_ref, by_vendor


def match_transaction(
    db: Session,
    tx: Transaction,
    invoices: list[Invoice],
    vendors: dict[str, Vendor],
    by_ref: dict[str, list[Invoice]] | None = None,
    by_vendor: dict[str, list[Invoice]] | None = None,
) -> list[Candidate]:
    hist = 0.7
    pool = invoices
    if by_ref is not None and by_vendor is not None:
        pool = shortlist(tx, invoices, by_ref, by_vendor)
    scored = []
    for inv in pool:
        vendor = vendors.get(inv.vendor_id) if inv.vendor_id else vendors.get(tx.vendor_id)
        scored.append(score_pair(tx, inv, vendor, hist))
    scored.sort(key=lambda c: c.score, reverse=True)
    # Ambiguity guard: if top-2 are both above investigate threshold and
    # separated by less than 0.02, demote top to the ambiguous band
    # so the exception handler catches it rather than auto-matching.
    if len(scored) >= 2:
        gap = scored[0].score - scored[1].score
        if scored[0].score >= 0.94 and scored[1].score >= 0.80 and gap < 0.02:
            scored[0] = Candidate(
                scored[0].invoice,
                min(scored[0].score, 0.84),  # push below auto_match (0.98) & investigate (0.85)
                scored[0].level + "*",
                scored[0].features,
                scored[0].checks,
            )
    return scored[:5]
