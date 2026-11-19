"""River QuantileFilter wrapper and adaptive threshold management.
Ensures strict score-before-learn sequencing and protection of underlying detectors.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Any, Optional
import math
from river import anomaly


@dataclass
class AdaptiveScoreResult:
    """Outcome of an adaptive threshold evaluation."""
    score: float
    threshold: float
    is_anomaly: bool
    q: float
    samples_seen: int


class AdaptiveThresholdFilter:
    """Wraps an anomaly detector with River QuantileFilter for continuous quantile thresholding."""

    def __init__(self, detector: Any, q: float = 0.99, protect_anomaly_detector: bool = True):
        self.filter = anomaly.QuantileFilter(
            anomaly_detector=detector,
            q=q,
            protect_anomaly_detector=protect_anomaly_detector,
        )
        self.samples_seen = 0
        self.anomalies_rejected = 0

    @property
    def q(self) -> float:
        return self.filter.q

    @property
    def current_threshold(self) -> float:
        val = self.filter.quantile.get()
        return val if val is not None else 0.0

    def score_one(self, x: Dict[str, float]) -> float:
        """Compute the continuous anomaly score for an observation."""
        return float(self.filter.score_one(x))

    def classify_score(self, score: float) -> bool:
        """Classify whether a continuous score exceeds the adaptive threshold."""
        return bool(self.filter.classify(score))

    def evaluate_score_before_learn(
        self, x: Dict[str, float], allow_learning: bool = True
    ) -> AdaptiveScoreResult:
        """Strict score-before-learn pipeline:
        1. Calculate anomaly score.
        2. Compare against current adaptive threshold.
        3. If allow_learning is True, update detector via QuantileFilter
           (which respects protect_anomaly_detector).
        """
        score = self.score_one(x)
        thresh = self.current_threshold
        is_anom = self.classify_score(score)

        if allow_learning:
            self.samples_seen += 1
            if is_anom and self.filter.protect_anomaly_detector:
                self.anomalies_rejected += 1
            self.filter.learn_one(x)

        return AdaptiveScoreResult(
            score=round(score, 4),
            threshold=round(thresh, 4),
            is_anomaly=is_anom,
            q=self.q,
            samples_seen=self.samples_seen,
        )
