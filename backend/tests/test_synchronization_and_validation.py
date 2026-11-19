"""Automated tests for timestamp synchronization and sensor validation.
Covers:
- TEST 3: Manual pH and TDS readings are stored correctly.
- TEST 4: Stale manual readings are not used for combined detection.
- TEST 5: Incomplete measurements do not enter the multivariate model.
- TEST 20: Physical safety-limit violations are detected independently of the ML model.
"""

import os
from datetime import datetime, timezone, timedelta
from config.settings import AppConfig, SyncConfig, SafetyThresholds, NormalizationBounds
from core.processing.synchronization import TimestampSynchronizer
from core.processing.validation import SensorValidator
from core.database.database import init_db
from core.database.repository import MonitoringRepository


def test_manual_ph_tds_stored_correctly(tmp_path):
    """TEST 3: Manual pH and TDS readings are stored correctly in SQLite."""
    test_db = str(tmp_path / "test_iot.db")
    init_db(test_db)
    repo = MonitoringRepository(test_db)

    now = datetime.now(timezone.utc)
    id_p = repo.insert_manual_ph(7.35, now, "manual_input")
    id_d = repo.insert_manual_tds(290.0, now, "manual_input")

    assert id_p > 0
    assert id_d > 0

    latest_p = repo.get_latest_ph()
    latest_d = repo.get_latest_tds()

    assert latest_p is not None
    assert latest_p["ph"] == 7.35
    assert latest_p["data_source"] == "manual_input"

    assert latest_d is not None
    assert latest_d["tds"] == 290.0
    assert latest_d["data_source"] == "manual_input"


def test_stale_manual_readings_not_used_for_combined_detection():
    """TEST 4: Stale manual readings are not used for combined detection."""
    sync_config = SyncConfig(max_measurement_age_sec=60.0, max_sync_diff_sec=30.0)
    synchronizer = TimestampSynchronizer(sync_config)

    now = datetime.now(timezone.utc)
    stale_time = now - timedelta(seconds=120)  # 2 minutes ago (> 60s limit)

    # Fresh temperature, but stale manual readings
    synchronizer.update_temperature(24.5, timestamp=now)
    synchronizer.update_manual_pair(ph_val=7.4, tds_val=280.0, timestamp=stale_time)

    obs = synchronizer.get_synchronized_observation(current_time=now)

    assert obs.temp_fresh is True
    assert obs.ph_fresh is False
    assert obs.tds_fresh is False
    assert obs.is_three_variable_synced is False
    assert any("stale" in w.lower() for w in obs.warnings)


def test_incomplete_measurements_do_not_enter_multivariate():
    """TEST 5: Incomplete measurements do not enter the multivariate model."""
    sync_config = SyncConfig(max_measurement_age_sec=300.0, max_sync_diff_sec=180.0)
    synchronizer = TimestampSynchronizer(sync_config)

    now = datetime.now(timezone.utc)
    # Only temperature is provided
    synchronizer.update_temperature(25.0, timestamp=now)
    obs = synchronizer.get_synchronized_observation(current_time=now)

    assert obs.temperature == 25.0
    assert obs.ph is None
    assert obs.tds is None
    assert obs.is_three_variable_synced is False
    assert obs.is_pairwise_temp_ph_synced is False


def test_physical_safety_violations_detected_independently():
    """TEST 20: Physical safety-limit violations are detected independently of the ML model."""
    safety = SafetyThresholds(
        temp_min=10.0, temp_max=38.0,
        ph_min=6.5, ph_max=8.5,
        tds_min=50.0, tds_max=600.0
    )
    norm = NormalizationBounds()
    validator = SensorValidator(safety, norm)

    # Test extreme temperature
    res_high_temp = validator.validate_observation(temperature=45.0, ph=7.2, tds=250.0)
    assert res_high_temp.is_safety_violation is True
    assert any("Temperature" in v for v in res_high_temp.safety_violations)

    # Test extreme pH
    res_acidic = validator.validate_observation(temperature=24.0, ph=3.5, tds=250.0)
    assert res_acidic.is_safety_violation is True
    assert any("pH" in v for v in res_acidic.safety_violations)

    # Test extreme TDS
    res_high_tds = validator.validate_observation(temperature=24.0, ph=7.2, tds=950.0)
    assert res_high_tds.is_safety_violation is True
    assert any("TDS" in v for v in res_high_tds.safety_violations)

    # Test completely normal readings
    res_normal = validator.validate_observation(temperature=24.0, ph=7.2, tds=250.0)
    assert res_normal.is_safety_violation is False
    assert len(res_normal.safety_violations) == 0
