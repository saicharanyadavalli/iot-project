"""Application configuration and default settings.
Provides editable normalization bounds, physical safety limits,
serial communication settings, and model tuning parameters.
"""

from __future__ import annotations
import json
import os
from dataclasses import dataclass, field, asdict
from typing import Dict, Tuple, Optional, List


@dataclass
class NormalizationBounds:
    """Normalization bounds for scaling features to [0, 1] for Half-Space Trees.
    These represent expected physical operating domains, kept separate from safety limits.
    """
    temp_min: float = 0.0
    temp_max: float = 50.0   # °C
    ph_min: float = 0.0
    ph_max: float = 14.0     # pH scale
    tds_min: float = 0.0
    tds_max: float = 2000.0  # ppm

    def to_dict(self) -> Dict[str, Tuple[float, float]]:
        return {
            "temperature": (self.temp_min, self.temp_max),
            "ph": (self.ph_min, self.ph_max),
            "tds": (self.tds_min, self.tds_max),
        }


@dataclass
class SafetyThresholds:
    """Physical safety limits.
    Any reading outside these boundaries triggers a SAFETY_VIOLATION alert,
    independent of statistical ML anomaly scores.
    Configurable for specific water systems (e.g. drinking, aquaculture, cooling tower).
    """
    temp_min: float = 10.0   # °C
    temp_max: float = 38.0   # °C
    ph_min: float = 6.5      # standard neutral/potable range
    ph_max: float = 8.5
    tds_min: float = 50.0    # ppm
    tds_max: float = 600.0   # ppm (WHO palatable limit ~600ppm)


@dataclass
class SerialConfig:
    """Serial communication parameters for ESP32 receiver."""
    port: str = "COM13"
    baud_rate: int = 115200
    timeout: float = 1.0
    reconnect_interval_sec: float = 3.0
    mock_mode: bool = False
    parse_mode: str = "auto"  # 'auto', 'strict', or 'ping_demo'


@dataclass
class ModelConfig:
    """Online machine learning configuration parameters."""
    warmup_samples: int = 40        # Number of samples required before switching to MONITORING
    anomaly_quantile: float = 0.99  # QuantileFilter q threshold
    hst_n_trees: int = 15           # Number of half-space trees
    hst_height: int = 8             # Height of each tree
    hst_window_size: int = 250      # Tree sliding window size
    
    # Statistical individual anomaly parameters (Rolling Median + MAD)
    individual_window_size: int = 30
    individual_mad_multiplier: float = 3.5  # Z-score cutoff based on MAD
    
    # ADWIN Drift detector parameters
    adwin_delta: float = 0.002
    adwin_clock: int = 16
    adwin_grace_period: int = 15
    shadow_model_stable_samples: int = 25  # Samples required before promoting candidate shadow model
    
    # Checkpoint settings
    checkpoint_interval_samples: int = 20


@dataclass
class SyncConfig:
    """Timestamp synchronization settings between asynchronous sensors."""
    max_measurement_age_sec: float = 300.0   # 5 minutes freshness limit for manual values
    max_sync_diff_sec: float = 180.0         # Maximum time difference between temp and manual entries


@dataclass
class WirelessConfig:
    """nRF24L01 wireless communication and transmission profile configuration.

    NOTE: nRF24L01 does not provide continuous RSSI/SNR like LoRa modules.
    Signal detection is binary (RPD) only. No signal strength metrics are reported.
    Nano is always configured at RF24_PA_MIN regardless of profile (brownout protection).
    """
    active_profile: str = "BALANCED"            # SHORT / BALANCED / LONG
    esp32_port: str = "COM13"                   # ESP32 transmitter USB serial port
    nano_port: str = "COM12"                    # Arduino Nano receiver USB serial port
    baud_rate: int = 115200
    rf_channel: int = 108
    enable_dual_serial: bool = True              # Read temperature from Nano (COM12)


@dataclass
class AppConfig:
    """Global unified application configuration."""
    normalization: NormalizationBounds = field(default_factory=NormalizationBounds)
    safety: SafetyThresholds = field(default_factory=SafetyThresholds)
    serial: SerialConfig = field(default_factory=SerialConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    sync: SyncConfig = field(default_factory=SyncConfig)
    wireless: WirelessConfig = field(default_factory=WirelessConfig)
    db_path: str = "data/iot_monitoring.db"
    checkpoint_path: str = "data/model_checkpoint.pkl"
    simulation_enabled: bool = False

    def save_to_file(self, filepath: str = "config/app_config.json") -> None:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        data = asdict(self)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load_from_file(cls, filepath: str = "config/app_config.json") -> AppConfig:
        if not os.path.exists(filepath):
            config = cls()
            config.save_to_file(filepath)
            return config
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            return cls(
                normalization=NormalizationBounds(**data.get("normalization", {})),
                safety=SafetyThresholds(**data.get("safety", {})),
                serial=SerialConfig(**data.get("serial", {})),
                model=ModelConfig(**data.get("model", {})),
                sync=SyncConfig(**data.get("sync", {})),
                wireless=WirelessConfig(**data.get("wireless", {})),
                db_path=data.get("db_path", "data/iot_monitoring.db"),
                checkpoint_path=data.get("checkpoint_path", "data/model_checkpoint.pkl"),
                simulation_enabled=data.get("simulation_enabled", False),
            )
        except Exception:
            return cls()
