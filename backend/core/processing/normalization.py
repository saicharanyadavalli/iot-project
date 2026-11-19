"""Feature normalization for online anomaly detection models.
Transforms raw values into [0, 1] interval based on physical domain bounds.
Crucially, flags out-of-bounds inputs rather than silently clipping them.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from config.settings import NormalizationBounds


@dataclass
class NormalizationResult:
    """Outcome of feature normalization."""
    scaled_dict: Dict[str, float]
    is_in_bounds: bool
    out_of_bounds_features: list[str]


class FeatureNormalizer:
    """Normalizes temperature, pH, and TDS values for Half-Space Trees."""

    def __init__(self, bounds: NormalizationBounds):
        self.bounds = bounds

    def normalize_value(self, feature_name: str, raw_value: float) -> Tuple[float, bool]:
        """Normalize a single feature value into [0.0, 1.0].
        Returns (scaled_value, is_in_bounds).
        Does NOT silently clamp or mask values outside boundaries.
        """
        if feature_name == "temperature":
            min_v, max_v = self.bounds.temp_min, self.bounds.temp_max
        elif feature_name == "ph":
            min_v, max_v = self.bounds.ph_min, self.bounds.ph_max
        elif feature_name == "tds":
            min_v, max_v = self.bounds.tds_min, self.bounds.tds_max
        else:
            raise ValueError(f"Unknown feature name: {feature_name}")

        denom = max_v - min_v
        if denom == 0:
            return 0.5, True

        scaled = (raw_value - min_v) / denom
        in_bounds = 0.0 <= scaled <= 1.0
        return scaled, in_bounds

    def normalize_dict(self, raw_features: Dict[str, Optional[float]]) -> NormalizationResult:
        """Normalize a dictionary of raw features (e.g. {'temperature': 25.0, 'ph': 7.2})."""
        scaled: Dict[str, float] = {}
        oob: list[str] = []

        for feat, val in raw_features.items():
            if val is None:
                continue
            s_val, in_bounds = self.normalize_value(feat, val)
            scaled[feat] = s_val
            if not in_bounds:
                oob.append(feat)

        return NormalizationResult(
            scaled_dict=scaled,
            is_in_bounds=len(oob) == 0,
            out_of_bounds_features=oob,
        )
