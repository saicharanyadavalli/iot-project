"""Concept and environmental drift detection using River ADWIN.
Implements a controlled shadow-model architecture to distinguish sporadic spikes
from sustained shifts and promote candidate models safely without blind resets.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Callable, Any
from river import drift

from config.settings import ModelConfig


@dataclass
class DriftStatus:
    """Current state of environmental drift monitoring."""
    drift_detected_now: bool
    is_drift_suspected: bool
    drifted_features: List[str]
    shadow_active: bool
    shadow_sample_count: int
    shadow_target_samples: int
    promoted_now: bool
    details: str = ""


class EnvironmentalDriftMonitor:
    """Monitors incoming sensor streams for distribution shifts using River ADWIN.
    Manages shadow candidate models during drift regimes.
    """

    def __init__(self, config: ModelConfig):
        self.config = config
        self.adwin_detectors: Dict[str, drift.ADWIN] = {
            "temperature": drift.ADWIN(
                delta=config.adwin_delta,
                clock=config.adwin_clock,
                grace_period=config.adwin_grace_period,
            ),
            "ph": drift.ADWIN(
                delta=config.adwin_delta,
                clock=config.adwin_clock,
                grace_period=config.adwin_grace_period,
            ),
            "tds": drift.ADWIN(
                delta=config.adwin_delta,
                clock=config.adwin_clock,
                grace_period=config.adwin_grace_period,
            ),
            "multivariate_score": drift.ADWIN(
                delta=config.adwin_delta,
                clock=config.adwin_clock,
                grace_period=config.adwin_grace_period,
            ),
        }

        self.is_drift_suspected = False
        self.drifted_features: List[str] = []
        self.shadow_active = False
        self.shadow_samples = 0
        self.last_drift_event: Optional[Dict[str, Any]] = None

    def update(
        self,
        features: Dict[str, Optional[float]],
        multivariate_score: Optional[float] = None,
        is_safe_and_valid: bool = True,
        on_promote_callback: Optional[Callable[[], None]] = None,
    ) -> DriftStatus:
        """Feed current measurements into ADWIN detectors and advance shadow adaptation."""
        drift_now = False
        newly_drifted: List[str] = []

        # 1. Update ADWIN for each measurement
        for feat_name, val in features.items():
            if val is not None and feat_name in self.adwin_detectors:
                detector = self.adwin_detectors[feat_name]
                detector.update(val)
                if detector.drift_detected:
                    drift_now = True
                    newly_drifted.append(feat_name)

        # 2. Update ADWIN on multivariate anomaly score if available
        if multivariate_score is not None:
            m_det = self.adwin_detectors["multivariate_score"]
            m_det.update(multivariate_score)
            if m_det.drift_detected:
                drift_now = True
                newly_drifted.append("multivariate_score")

        promoted = False
        details = ""

        # 3. Handle newly triggered drift
        if drift_now:
            self.is_drift_suspected = True
            self.drifted_features = list(set(self.drifted_features + newly_drifted))
            self.shadow_active = True
            self.shadow_samples = 0
            details = f"Environmental drift detected in: {', '.join(newly_drifted)}"

        # 4. Shadow model progression
        if self.shadow_active:
            if is_safe_and_valid:
                self.shadow_samples += 1
                if self.shadow_samples >= self.config.shadow_model_stable_samples:
                    # Candidate model has received sufficient stable observations; promote it!
                    promoted = True
                    self.shadow_active = False
                    self.is_drift_suspected = False
                    self.drifted_features.clear()
                    details = f"Promoted shadow model after {self.shadow_samples} stable samples."
                    if on_promote_callback:
                        on_promote_callback()

        return DriftStatus(
            drift_detected_now=drift_now,
            is_drift_suspected=self.is_drift_suspected,
            drifted_features=list(self.drifted_features),
            shadow_active=self.shadow_active,
            shadow_sample_count=self.shadow_samples,
            shadow_target_samples=self.config.shadow_model_stable_samples,
            promoted_now=promoted,
            details=details,
        )

    def reset(self) -> None:
        """Reset drift monitor and ADWIN states."""
        for det in self.adwin_detectors.values():
            det._reset()
        self.is_drift_suspected = False
        self.drifted_features.clear()
        self.shadow_active = False
        self.shadow_samples = 0
