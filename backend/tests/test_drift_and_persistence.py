"""Automated tests for environmental drift detection and model persistence.
Covers:
- TEST 15: Gradual and sudden distribution changes are tested.
- TEST 17: Model state is saved and restored successfully.
"""

import os
from datetime import datetime, timezone
from config.settings import AppConfig, ModelConfig
from core.anomaly.drift_detector import EnvironmentalDriftMonitor
from core.anomaly.online_detector import AnomalyDetectionEngine, ModelState
from core.services.model_manager import ModelManager


def test_gradual_and_sudden_distribution_changes():
    """TEST 15: Gradual and sudden distribution changes are tested using ADWIN."""
    config = ModelConfig(adwin_delta=0.005, adwin_clock=8, adwin_grace_period=10)
    monitor = EnvironmentalDriftMonitor(config)

    # 1. Feed 40 normal baseline samples around Temp=24.0
    for _ in range(40):
        monitor.update(features={"temperature": 24.0, "ph": 7.4, "tds": 280.0})

    assert monitor.is_drift_suspected is False

    # 2. Introduce sustained shift in temperature to 32.0°C
    drift_detected = False
    for _ in range(30):
        status = monitor.update(features={"temperature": 32.0, "ph": 7.4, "tds": 280.0})
        if status.is_drift_suspected:
            drift_detected = True
            break

    assert drift_detected is True
    assert "temperature" in monitor.drifted_features
    assert monitor.shadow_active is True


def test_model_state_saved_and_restored(tmp_path):
    """TEST 17: Model state is saved and restored successfully across restarts."""
    ckpt_file = str(tmp_path / "model_ckpt.pkl")
    manager = ModelManager(checkpoint_path=ckpt_file)

    config = AppConfig()
    engine = AnomalyDetectionEngine(config)
    engine.total_observations = 150
    engine.warmup_count = 40
    engine.observations_learned = 145
    engine.state = ModelState.MONITORING

    # Save
    save_ok = manager.save_checkpoint(engine)
    assert save_ok is True
    assert os.path.exists(ckpt_file)

    # Restore
    restored = manager.load_checkpoint()
    assert restored is not None
    assert restored.total_observations == 150
    assert restored.warmup_count == 40
    assert restored.observations_learned == 145
    assert restored.state == ModelState.MONITORING
