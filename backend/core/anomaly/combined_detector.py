"""Three-parameter multivariate anomaly detection using River Half-Space Trees.
Evaluates joint patterns across Temperature, pH, and TDS simultaneously.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Any
from river import anomaly

from .adaptive_threshold import AdaptiveThresholdFilter, AdaptiveScoreResult
from config.settings import ModelConfig


@dataclass
class CombinedEvaluation:
    """Outcome of the three-parameter multivariate model."""
    evaluated: bool
    is_anomaly: bool
    score: float
    threshold: float
    features: Dict[str, float]


class CombinedAnomalyDetector:
    """Three-variable anomaly detector for (Temperature, pH, TDS)."""

    def __init__(self, config: ModelConfig, seed: int = 100):
        self.config = config
        self.seed = seed
        self.detector: AdaptiveThresholdFilter = self._init_model()

    def _init_model(self) -> AdaptiveThresholdFilter:
        limits = {
            "temperature": (0.0, 1.0),
            "ph": (0.0, 1.0),
            "tds": (0.0, 1.0),
        }
        hst = anomaly.HalfSpaceTrees(
            n_trees=self.config.hst_n_trees,
            height=self.config.hst_height,
            window_size=self.config.hst_window_size,
            limits=limits,
            seed=self.seed,
        )
        return AdaptiveThresholdFilter(
            detector=hst,
            q=self.config.anomaly_quantile,
            protect_anomaly_detector=True,
        )

    def evaluate_and_learn(
        self,
        normalized_features: Dict[str, float],
        is_synced: bool,
        allow_learning: bool = True,
    ) -> CombinedEvaluation:
        """Evaluate the 3D model if all three parameters are available and synchronized."""
        req_features = ["temperature", "ph", "tds"]
        has_all = all(k in normalized_features for k in req_features)

        if is_synced and has_all:
            features_3d = {k: normalized_features[k] for k in req_features}
            score_res = self.detector.evaluate_score_before_learn(
                features_3d, allow_learning=allow_learning
            )
            return CombinedEvaluation(
                evaluated=True,
                is_anomaly=score_res.is_anomaly,
                score=score_res.score,
                threshold=score_res.threshold,
                features=features_3d,
            )

        return CombinedEvaluation(
            evaluated=False,
            is_anomaly=False,
            score=0.0,
            threshold=self.detector.current_threshold,
            features={},
        )
