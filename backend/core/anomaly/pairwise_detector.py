"""Pairwise multivariate anomaly detection using River Half-Space Trees.
Maintains three independent pairwise models:
- Temperature + pH
- Temperature + TDS
- pH + TDS
Enables the system to diagnose which specific two-parameter interactions are unusual.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple, Any
from river import anomaly

from .adaptive_threshold import AdaptiveThresholdFilter, AdaptiveScoreResult
from config.settings import ModelConfig


@dataclass
class PairwiseEvaluation:
    """Outcome for a single feature pair."""
    pair_name: str
    evaluated: bool
    is_anomaly: bool
    score: float
    threshold: float
    features: Dict[str, float]


@dataclass
class PairwiseResult:
    """Consolidated outcome of pairwise evaluations."""
    evaluations: Dict[str, PairwiseEvaluation] = field(default_factory=dict)

    @property
    def has_any_anomaly(self) -> bool:
        return any(ev.is_anomaly for ev in self.evaluations.values() if ev.evaluated)

    @property
    def anomalous_pairs(self) -> list[str]:
        return [name for name, ev in self.evaluations.items() if ev.evaluated and ev.is_anomaly]


class PairwiseAnomalyDetector:
    """Manages independent Half-Space Trees detectors for each pair of parameters."""

    PAIR_TEMP_PH = "temp_ph"
    PAIR_TEMP_TDS = "temp_tds"
    PAIR_PH_TDS = "ph_tds"

    def __init__(self, config: ModelConfig, seed: int = 42):
        self.config = config
        self.seed = seed
        self.detectors: Dict[str, AdaptiveThresholdFilter] = {}
        self._init_models()

    def _init_models(self) -> None:
        """Instantiate River Half-Space Trees with [0, 1] limits for normalized pairs."""
        pairs = [
            (self.PAIR_TEMP_PH, ["temperature", "ph"]),
            (self.PAIR_TEMP_TDS, ["temperature", "tds"]),
            (self.PAIR_PH_TDS, ["ph", "tds"]),
        ]
        for idx, (name, features) in enumerate(pairs):
            limits = {feat: (0.0, 1.0) for feat in features}
            hst = anomaly.HalfSpaceTrees(
                n_trees=self.config.hst_n_trees,
                height=self.config.hst_height,
                window_size=self.config.hst_window_size,
                limits=limits,
                seed=self.seed + idx,
            )
            self.detectors[name] = AdaptiveThresholdFilter(
                detector=hst,
                q=self.config.anomaly_quantile,
                protect_anomaly_detector=True,
            )

    def evaluate_and_learn(
        self,
        normalized_features: Dict[str, float],
        synced_pairs: Dict[str, bool],
        allow_learning: bool = True,
    ) -> PairwiseResult:
        """Evaluate each pairwise model where measurements are synchronized and available."""
        result = PairwiseResult()

        configs = [
            (self.PAIR_TEMP_PH, ("temperature", "ph")),
            (self.PAIR_TEMP_TDS, ("temperature", "tds")),
            (self.PAIR_PH_TDS, ("ph", "tds")),
        ]

        for pair_name, (f1, f2) in configs:
            is_synced = synced_pairs.get(pair_name, False)
            has_features = (f1 in normalized_features) and (f2 in normalized_features)

            if is_synced and has_features:
                pair_dict = {f1: normalized_features[f1], f2: normalized_features[f2]}
                detector = self.detectors[pair_name]
                score_res = detector.evaluate_score_before_learn(pair_dict, allow_learning=allow_learning)
                result.evaluations[pair_name] = PairwiseEvaluation(
                    pair_name=pair_name,
                    evaluated=True,
                    is_anomaly=score_res.is_anomaly,
                    score=score_res.score,
                    threshold=score_res.threshold,
                    features=pair_dict,
                )
            else:
                result.evaluations[pair_name] = PairwiseEvaluation(
                    pair_name=pair_name,
                    evaluated=False,
                    is_anomaly=False,
                    score=0.0,
                    threshold=self.detectors[pair_name].current_threshold,
                    features={},
                )

        return result
