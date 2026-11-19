"""Continuous streaming sensor data simulator and anomaly injector.
Generates realistic water-quality parameter streams and enables deterministic
injection of individual (Cases 1-3), pairwise (Cases 4-6), three-parameter (Case 7),
safety violations, and environmental drift for demonstrations and test suites.
"""

from __future__ import annotations
import math
import random
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class SimulatedSample:
    """A generated multi-parameter measurement snapshot."""
    temperature: float
    ph: float
    tds: float
    timestamp: datetime
    injected_type: Optional[str] = None
    data_source: str = "simulated"


class DataSimulator:
    """Generates continuous streaming data with normal water dynamics, drift, and fault injection."""

    def __init__(self, seed: Optional[int] = 42):
        self.rng = random.Random(seed)
        self.step_count = 0

        # Baselines
        self.base_temp = 24.5
        self.base_ph = 7.35
        self.base_tds = 280.0

        # Environmental drift state
        self.drift_active = False
        self.drift_rate_temp = 0.0
        self.drift_rate_ph = 0.0
        self.drift_rate_tds = 0.0
        self.accumulated_drift_temp = 0.0
        self.accumulated_drift_ph = 0.0
        self.accumulated_drift_tds = 0.0

        # Queued one-shot anomaly injection
        self.queued_anomaly: Optional[str] = None

    def inject_anomaly(self, anomaly_type: str) -> None:
        """Queue an anomaly injection for the next generated sample.
        Supported types:
        - 'temp_only' (Case 1)
        - 'ph_only' (Case 2)
        - 'tds_only' (Case 3)
        - 'temp_ph' (Case 4)
        - 'temp_tds' (Case 5)
        - 'ph_tds' (Case 6)
        - 'three_param' (Case 7)
        - 'safety_violation'
        - 'sudden_shift'
        """
        self.queued_anomaly = anomaly_type

    def start_gradual_drift(self, rate_temp: float = 0.08, rate_ph: float = 0.015, rate_tds: float = 2.5) -> None:
        """Begin continuous environmental drift."""
        self.drift_active = True
        self.drift_rate_temp = rate_temp
        self.drift_rate_ph = rate_ph
        self.drift_rate_tds = rate_tds

    def reset_drift(self) -> None:
        """Reset environmental drift back to baseline."""
        self.drift_active = False
        self.accumulated_drift_temp = 0.0
        self.accumulated_drift_ph = 0.0
        self.accumulated_drift_tds = 0.0

    def generate_sample(self, timestamp: Optional[datetime] = None) -> SimulatedSample:
        """Produce the next streaming sample in chronological sequence."""
        self.step_count += 1
        ts = timestamp or datetime.now(timezone.utc)

        # Apply gradual drift if active
        if self.drift_active:
            self.accumulated_drift_temp += self.drift_rate_temp
            self.accumulated_drift_ph += self.drift_rate_ph
            self.accumulated_drift_tds += self.drift_rate_tds

        # Normal natural dynamics: subtle sinusoidal oscillation + Gaussian noise
        # Daily cycle simulated with period of 100 steps
        cycle_phase = (self.step_count % 100) / 100.0 * 2.0 * math.pi
        t_osc = 1.2 * math.sin(cycle_phase)
        p_osc = 0.1 * math.sin(cycle_phase + 0.5)
        d_osc = 15.0 * math.cos(cycle_phase)

        t_noise = self.rng.gauss(0, 0.25)
        p_noise = self.rng.gauss(0, 0.04)
        d_noise = self.rng.gauss(0, 4.0)

        temp = self.base_temp + t_osc + t_noise + self.accumulated_drift_temp
        ph = self.base_ph + p_osc + p_noise + self.accumulated_drift_ph
        tds = self.base_tds + d_osc + d_noise + self.accumulated_drift_tds

        injected_type = self.queued_anomaly
        self.queued_anomaly = None

        if injected_type == "temp_only":
            # Case 1: Temperature anomaly (within safety bounds but statistically distant)
            temp += self.rng.choice([+8.5, -7.0])
        elif injected_type == "ph_only":
            # Case 2: pH anomaly
            ph += self.rng.choice([+0.95, -0.75])
        elif injected_type == "tds_only":
            # Case 3: TDS anomaly
            tds += self.rng.choice([+190.0, -140.0])
        elif injected_type == "temp_ph":
            # Case 4: Joint unusual combination of Temp and pH
            temp += 7.5
            ph -= 0.65
        elif injected_type == "temp_tds":
            # Case 5: Joint unusual combination of Temp and TDS
            temp += 7.0
            tds += 170.0
        elif injected_type == "ph_tds":
            # Case 6: Joint unusual combination of pH and TDS
            ph += 0.8
            tds += 160.0
        elif injected_type == "three_param":
            # Case 7: Joint three-parameter anomaly
            temp += 6.5
            ph -= 0.6
            tds += 180.0
        elif injected_type == "safety_violation":
            # Severe physical safety violation
            temp = 43.5  # Exceeds max safety limit (38°C)
            ph = 9.2     # Exceeds max safety limit (8.5)
            tds = 750.0  # Exceeds max safety limit (600 ppm)
        elif injected_type == "sudden_shift":
            # Sudden environmental shift
            self.base_temp += 5.0
            self.base_ph += 0.5
            self.base_tds += 80.0

        return SimulatedSample(
            temperature=round(temp, 2),
            ph=round(ph, 2),
            tds=round(tds, 1),
            timestamp=ts,
            injected_type=injected_type,
            data_source="simulated",
        )
