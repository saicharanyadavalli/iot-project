"""Rate of Change Anomaly & Advisory Detector.
Calculates time-derivative change (rate per second) between consecutive sensor readings.
Operates from the second valid reading onward to provide immediate temporal dynamics monitoring.
"""

from __future__ import annotations
import math
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, Dict, Tuple


@dataclass
class RateOfChangeResult:
    """Evaluation result for rate of change on a single parameter."""
    feature_name: str
    current_value: float
    previous_value: Optional[float]
    elapsed_seconds: Optional[float]
    rate_per_second: Optional[float]
    is_warning: bool
    threshold_rate_per_sec: Optional[float]
    direction: str  # "STABLE", "INCREASING", "DECREASING"
    message: Optional[str] = None


class RateOfChangeDetector:
    """Tracks consecutive observations and calculates rates of change per second."""

    def __init__(
        self,
        max_temp_rate_per_sec: float = 1.5,   # °C / sec
        max_ph_rate_per_sec: float = 0.5,     # pH units / sec
        max_tds_rate_per_sec: float = 50.0,   # ppm / sec
    ):
        self.thresholds: Dict[str, float] = {
            "temperature": max_temp_rate_per_sec,
            "ph": max_ph_rate_per_sec,
            "tds": max_tds_rate_per_sec,
        }
        self.last_readings: Dict[str, Tuple[float, datetime]] = {}

    def evaluate(
        self,
        feature_name: str,
        value: float,
        timestamp: Optional[datetime] = None,
    ) -> RateOfChangeResult:
        """Evaluate rate of change for a parameter against its previous observation."""
        ts = timestamp or datetime.now(timezone.utc)
        prev = self.last_readings.get(feature_name)

        if prev is None:
            # First reading for this parameter — record state, cannot compute rate yet
            self.last_readings[feature_name] = (value, ts)
            return RateOfChangeResult(
                feature_name=feature_name,
                current_value=value,
                previous_value=None,
                elapsed_seconds=None,
                rate_per_second=None,
                is_warning=False,
                threshold_rate_per_sec=self.thresholds.get(feature_name),
                direction="STABLE",
                message="Initial reading recorded for rate baseline",
            )

        prev_val, prev_ts = prev
        elapsed = (ts - prev_ts).total_seconds()

        # Reject duplicate or non-positive elapsed times
        if elapsed <= 0.001:
            return RateOfChangeResult(
                feature_name=feature_name,
                current_value=value,
                previous_value=prev_val,
                elapsed_seconds=elapsed,
                rate_per_second=0.0,
                is_warning=False,
                threshold_rate_per_sec=self.thresholds.get(feature_name),
                direction="STABLE",
                message="Sub-millisecond or duplicate timestamp; rate suppressed",
            )

        diff = value - prev_val
        rate = diff / elapsed
        abs_rate = abs(rate)
        threshold = self.thresholds.get(feature_name, 1.0)
        is_warning = abs_rate > threshold

        direction = "STABLE"
        if diff > 0.001:
            direction = "INCREASING"
        elif diff < -0.001:
            direction = "DECREASING"

        # Update last reading
        self.last_readings[feature_name] = (value, ts)

        msg = None
        if is_warning:
            unit = "°C/s" if feature_name == "temperature" else ("/s" if feature_name == "ph" else "ppm/s")
            msg = (
                f"Rapid {feature_name} change: {rate:+.2f} {unit} "
                f"(exceeds threshold {threshold:.2f} {unit} over {elapsed:.1f}s)"
            )

        return RateOfChangeResult(
            feature_name=feature_name,
            current_value=value,
            previous_value=prev_val,
            elapsed_seconds=round(elapsed, 2),
            rate_per_second=round(rate, 4),
            is_warning=is_warning,
            threshold_rate_per_sec=threshold,
            direction=direction,
            message=msg,
        )

    def reset(self) -> None:
        """Clear historical tracking."""
        self.last_readings.clear()
