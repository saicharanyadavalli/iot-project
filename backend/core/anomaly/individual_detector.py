"""Individual parameter statistical anomaly detector.
Uses online rolling median and Median Absolute Deviation (MAD) for robust Z-score detection.
Protects baseline distribution from contamination by anomalous observations.
"""

from __future__ import annotations
import math
from collections import deque
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class IndividualAnomalyResult:
    """Result of an individual parameter anomaly evaluation."""
    feature_name: str
    value: float
    is_anomaly: bool
    score: float       # Robust Z-score: |x - median| / (1.4826 * MAD)
    threshold: float   # Cutoff threshold (e.g. 3.5)
    rolling_median: Optional[float]
    mad: Optional[float]
    sample_count: int


class RobustZScoreDetector:
    """Rolling Median and MAD-based robust online anomaly detector for a single feature."""

    def __init__(self, feature_name: str, window_size: int = 30, threshold: float = 3.5):
        self.feature_name = feature_name
        self.window_size = window_size
        self.threshold = threshold
        self.window: deque[float] = deque(maxlen=window_size)
        self.total_observed = 0

        # Physical dispersion floors to prevent microscopic variance lockup
        if feature_name == "temperature":
            self.min_sigma = 0.5   # °C
        elif feature_name == "ph":
            self.min_sigma = 0.1   # pH units
        elif feature_name == "tds":
            self.min_sigma = 8.0   # ppm
        else:
            self.min_sigma = 0.1

    def score_one(self, value: float) -> tuple[float, Optional[float], Optional[float]]:
        """Calculate the robust z-score without updating the baseline window.
        Returns (z_score, rolling_median, mad).
        """
        if len(self.window) < 5:
            return 0.0, None, None

        sorted_vals = sorted(self.window)
        n = len(sorted_vals)
        mid = n // 2
        median = (sorted_vals[mid] if n % 2 != 0 else (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0)

        deviations = sorted(abs(x - median) for x in self.window)
        mad = (deviations[mid] if n % 2 != 0 else (deviations[mid - 1] + deviations[mid]) / 2.0)

        # Scale factor 1.4826 makes MAD an asymptotically normal estimator for standard deviation
        sigma_est = max(1.4826 * mad, self.min_sigma)

        z_score = abs(value - median) / sigma_est
        return z_score, median, mad

    def evaluate(self, value: float, in_warmup: bool = False) -> IndividualAnomalyResult:
        """Score the observation, determine anomaly classification, and conditionally update window."""
        self.total_observed += 1
        z_score, median, mad = self.score_one(value)

        # During warmup or before window has sufficient samples, do not classify as anomaly
        is_anomaly = (not in_warmup) and (len(self.window) >= 5) and (z_score >= self.threshold)

        # Protect detector baseline: incorporate during warmup or when not anomalous
        if in_warmup or not is_anomaly:
            self.window.append(value)

        return IndividualAnomalyResult(
            feature_name=self.feature_name,
            value=value,
            is_anomaly=is_anomaly,
            score=round(z_score, 3),
            threshold=self.threshold,
            rolling_median=round(median, 3) if median is not None else None,
            mad=round(mad, 3) if mad is not None else None,
            sample_count=len(self.window),
        )

    def reset(self) -> None:
        """Reset the detector state."""
        self.window.clear()
        self.total_observed = 0
