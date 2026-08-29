from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


POLICY_PATH = Path(__file__).with_name("policy.yaml")


class Policy:
    def __init__(self, raw: dict[str, Any]):
        self.raw = raw
        mt = raw["match_thresholds"]
        self.auto_match = float(mt["auto_match"])
        self.investigate = float(mt["investigate"])
        self.ambiguous = float(mt["ambiguous"])
        tol = raw["tolerances"]
        self.amount_tolerance = Decimal(str(tol["amount"]))
        self.amount_pct = Decimal(str(tol["amount_pct"]))
        self.contractual_variance_pct = Decimal(str(tol["contractual_variance_pct"]))
        self.tax_tolerance = Decimal(str(tol["tax"]))
        self.date_days = int(tol["date_days"])
        ext = raw["extraction"]
        self.min_text_chars = int(ext["min_text_chars"])
        self.ocr_confidence_floor = float(ext["ocr_confidence_floor"])
        self.vision_fallback_confidence = float(ext["vision_fallback_confidence"])
        self.line_item_tolerance = Decimal(str(ext["amount_line_item_tolerance"]))
        up = raw["uploads"]
        self.max_upload_bytes = int(up["max_bytes"])
        self.allowed_mime = set(up["allowed_mime"])
        self.allowed_ext = set(e.lower() for e in up["allowed_ext"])
        dg = raw["decision_gate"]
        self.min_confidence_auto_resolve = float(dg["min_confidence_auto_resolve"])
        self.require_evidence = bool(dg["require_evidence"])
        self.allowed_reason_codes = set(dg["allowed_reason_codes"])
        cash = raw["cash"]
        self.current_cash = Decimal(str(cash["current_cash"]))
        self.currency = cash["currency"]
        self.scheduled_monthly_expenses = Decimal(str(cash["scheduled_monthly_expenses"]))
        self.skip_llm_below_investigate = bool(raw["cost"]["skip_llm_below_investigate"])

    def band_for_score(self, score: float) -> str:
        if score >= self.auto_match:
            return "AUTO_MATCH"
        if score >= self.investigate:
            return "INVESTIGATE"
        if score >= self.ambiguous:
            return "AMBIGUOUS"
        return "UNMATCHED"


@lru_cache(maxsize=1)
def load_policy() -> Policy:
    with POLICY_PATH.open("r", encoding="utf-8") as f:
        return Policy(yaml.safe_load(f))


policy = load_policy()
