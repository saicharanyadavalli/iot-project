"""Timestamp synchronization for asynchronous sensor streams.
Synchronizes live temperature with manual pH and TDS inputs based on configurable
freshness windows and maximum permitted inter-measurement skew.
Prevents stale value reuse and duplicate synthetic observation generation.
"""

from __future__ import annotations
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Optional, Dict, List

from config.settings import SyncConfig


@dataclass
class TimestampedValue:
    """A single sensor measurement with timestamp and origin metadata."""
    value: float
    timestamp: datetime
    data_source: str = "physical_serial"  # 'physical_serial', 'manual_input', 'simulated'
    consumed_for_multivariate: bool = False


@dataclass
class SynchronizedObservation:
    """A synchronized multi-sensor observation snapshot."""
    timestamp: datetime
    temperature: Optional[float]
    ph: Optional[float]
    tds: Optional[float]

    temp_fresh: bool = False
    ph_fresh: bool = False
    tds_fresh: bool = False

    is_pairwise_temp_ph_synced: bool = False
    is_pairwise_temp_tds_synced: bool = False
    is_pairwise_ph_tds_synced: bool = False
    is_three_variable_synced: bool = False

    data_sources: Dict[str, str] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    is_new_sample: bool = True


class TimestampSynchronizer:
    """Synchronizes temperature, pH, and TDS readings according to freshness and skew rules."""

    def __init__(self, config: SyncConfig):
        self.config = config
        self.latest_temp: Optional[TimestampedValue] = None
        self.latest_ph: Optional[TimestampedValue] = None
        self.latest_tds: Optional[TimestampedValue] = None
        self._last_combined_hash: Optional[str] = None

    def update_temperature(
        self, value: float, timestamp: Optional[datetime] = None, data_source: str = "physical_serial"
    ) -> None:
        ts = timestamp or datetime.now(timezone.utc)
        self.latest_temp = TimestampedValue(value=value, timestamp=ts, data_source=data_source)

    def update_manual_ph(
        self, value: float, timestamp: Optional[datetime] = None, data_source: str = "manual_input"
    ) -> None:
        ts = timestamp or datetime.now(timezone.utc)
        self.latest_ph = TimestampedValue(value=value, timestamp=ts, data_source=data_source)

    def update_manual_tds(
        self, value: float, timestamp: Optional[datetime] = None, data_source: str = "manual_input"
    ) -> None:
        ts = timestamp or datetime.now(timezone.utc)
        self.latest_tds = TimestampedValue(value=value, timestamp=ts, data_source=data_source)

    def update_manual_pair(
        self,
        ph_val: float,
        tds_val: float,
        timestamp: Optional[datetime] = None,
        data_source: str = "manual_input",
    ) -> None:
        """Submit pH and TDS together as one timestamped measurement."""
        ts = timestamp or datetime.now(timezone.utc)
        self.update_manual_ph(ph_val, ts, data_source)
        self.update_manual_tds(tds_val, ts, data_source)

    def get_synchronized_observation(
        self, current_time: Optional[datetime] = None
    ) -> SynchronizedObservation:
        """Evaluate current measurements and assemble a synchronized observation with synchronization flags."""
        now = current_time or datetime.now(timezone.utc)
        warnings: List[str] = []
        data_sources: Dict[str, str] = {}

        # 1. Freshness evaluation
        temp_val: Optional[float] = None
        temp_fresh = False
        if self.latest_temp is not None:
            age = (now - self.latest_temp.timestamp).total_seconds()
            if age <= self.config.max_measurement_age_sec:
                temp_val = self.latest_temp.value
                temp_fresh = True
                data_sources["temperature"] = self.latest_temp.data_source
            else:
                warnings.append(f"Temperature reading is stale ({age:.0f}s old > {self.config.max_measurement_age_sec:.0f}s)")
        else:
            warnings.append("No temperature reading available")

        ph_val: Optional[float] = None
        ph_fresh = False
        if self.latest_ph is not None:
            age = (now - self.latest_ph.timestamp).total_seconds()
            if age <= self.config.max_measurement_age_sec:
                ph_val = self.latest_ph.value
                ph_fresh = True
                data_sources["ph"] = self.latest_ph.data_source
            else:
                warnings.append(f"Manual pH reading is stale ({age:.0f}s old > {self.config.max_measurement_age_sec:.0f}s)")
        else:
            warnings.append("No manual pH reading available")

        tds_val: Optional[float] = None
        tds_fresh = False
        if self.latest_tds is not None:
            age = (now - self.latest_tds.timestamp).total_seconds()
            if age <= self.config.max_measurement_age_sec:
                tds_val = self.latest_tds.value
                tds_fresh = True
                data_sources["tds"] = self.latest_tds.data_source
            else:
                warnings.append(f"Manual TDS reading is stale ({age:.0f}s old > {self.config.max_measurement_age_sec:.0f}s)")
        else:
            warnings.append("No manual TDS reading available")

        # 2. Inter-measurement skew checks
        t_ph_synced = False
        if temp_fresh and ph_fresh and self.latest_temp and self.latest_ph:
            diff = abs((self.latest_temp.timestamp - self.latest_ph.timestamp).total_seconds())
            if diff <= self.config.max_sync_diff_sec:
                t_ph_synced = True
            else:
                warnings.append(f"Temp and pH skew exceeds limit ({diff:.0f}s > {self.config.max_sync_diff_sec:.0f}s)")

        t_tds_synced = False
        if temp_fresh and tds_fresh and self.latest_temp and self.latest_tds:
            diff = abs((self.latest_temp.timestamp - self.latest_tds.timestamp).total_seconds())
            if diff <= self.config.max_sync_diff_sec:
                t_tds_synced = True
            else:
                warnings.append(f"Temp and TDS skew exceeds limit ({diff:.0f}s > {self.config.max_sync_diff_sec:.0f}s)")

        ph_tds_synced = False
        if ph_fresh and tds_fresh and self.latest_ph and self.latest_tds:
            diff = abs((self.latest_ph.timestamp - self.latest_tds.timestamp).total_seconds())
            if diff <= self.config.max_sync_diff_sec:
                ph_tds_synced = True
            else:
                warnings.append(f"pH and TDS skew exceeds limit ({diff:.0f}s > {self.config.max_sync_diff_sec:.0f}s)")

        three_synced = t_ph_synced and t_tds_synced and ph_tds_synced

        # 3. Detect duplicate/reused observations
        # Use measurement timestamps to determine if any new data was introduced
        sample_hash = (
            f"T:{self.latest_temp.timestamp.isoformat() if self.latest_temp else 'none'}-"
            f"P:{self.latest_ph.timestamp.isoformat() if self.latest_ph else 'none'}-"
            f"D:{self.latest_tds.timestamp.isoformat() if self.latest_tds else 'none'}"
        )
        is_new = sample_hash != self._last_combined_hash
        self._last_combined_hash = sample_hash

        return SynchronizedObservation(
            timestamp=now,
            temperature=temp_val,
            ph=ph_val,
            tds=tds_val,
            temp_fresh=temp_fresh,
            ph_fresh=ph_fresh,
            tds_fresh=tds_fresh,
            is_pairwise_temp_ph_synced=t_ph_synced,
            is_pairwise_temp_tds_synced=t_tds_synced,
            is_pairwise_ph_tds_synced=ph_tds_synced,
            is_three_variable_synced=three_synced,
            data_sources=data_sources,
            warnings=warnings,
            is_new_sample=is_new,
        )
