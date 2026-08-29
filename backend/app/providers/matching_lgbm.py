from pathlib import Path

import numpy as np

from app.config.settings import settings
from app.providers.base import MatchingModel

FEATURE_ORDER = [
    "vendor_similarity",
    "amount_difference",
    "amount_difference_percentage",
    "date_difference",
    "invoice_reference_similarity",
    "currency_match",
    "bank_reference_similarity",
    "historical_vendor_match_rate",
]


# L3 ranks candidate pairs. It never posts to the ledger.
# The booster is trained on synthetic (vendor, amount, date, ref) noise with labels
# from the generator; hidden ground-truth eval is the check against overfitting.
# If the model file is missing, a transparent linear heuristic is used instead.
# AUTO_MATCH still requires policy.yaml thresholds; AUTO_RESOLVE still requires the gate.


class LightGBMMatchingModel(MatchingModel):
    def __init__(self) -> None:
        self._booster = None
        path = Path(settings.matching_model_path)
        if path.exists():
            import lightgbm as lgb

            self._booster = lgb.Booster(model_file=str(path))

    def predict_proba(self, features: dict[str, float]) -> float:
        x = np.array([[float(features.get(k, 0.0)) for k in FEATURE_ORDER]], dtype=float)
        if self._booster is not None:
            pred = self._booster.predict(x)
            return float(pred[0])
        return self._heuristic(features)

    def _heuristic(self, f: dict[str, float]) -> float:
        score = (
            0.28 * f.get("vendor_similarity", 0)
            + 0.22 * (1.0 - min(1.0, f.get("amount_difference_percentage", 1)))
            + 0.12 * (1.0 - min(1.0, f.get("date_difference", 30) / 30.0))
            + 0.22 * f.get("invoice_reference_similarity", 0)
            + 0.08 * f.get("currency_match", 0)
            + 0.05 * f.get("bank_reference_similarity", 0)
            + 0.03 * f.get("historical_vendor_match_rate", 0)
        )
        return max(0.0, min(1.0, score))
