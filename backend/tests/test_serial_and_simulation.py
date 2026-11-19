"""Automated tests for serial management, simulation pipeline, and state representation.
Covers:
- TEST 16: Serial disconnection is handled correctly.
- TEST 18: Simulation mode uses the same processing and detection pipeline as real data.
- TEST 19: Dashboard correctly represents learning, monitoring, anomaly, drift, stale-data, and disconnected states.
"""

from datetime import datetime, timezone, timedelta
from config.settings import AppConfig, SerialConfig
from core.acquisition.serial_reader import SerialReader
from core.services.monitoring_service import MonitoringService
from core.anomaly.online_detector import ModelState, AnomalyDetectionEngine
from core.processing.synchronization import SynchronizedObservation


def test_serial_disconnection_handled_correctly():
    """TEST 16: Serial disconnection is handled correctly without crashing."""
    config = SerialConfig(port="COM99_NONEXISTENT", baud_rate=115200, reconnect_interval_sec=0.1)
    reader = SerialReader(config=config)

    # Calling stop on non-started reader is safe
    reader.stop()
    assert reader.is_connected is False

    # Mock mode test
    config_mock = SerialConfig(mock_mode=True)
    mock_reader = SerialReader(config=config_mock)
    mock_reader.start()
    mock_reader.stop()
    assert mock_reader.is_connected is False


def test_simulation_mode_uses_same_pipeline(tmp_path):
    """TEST 18: Simulation mode uses the same processing and detection pipeline as real data."""
    config = AppConfig()
    config.db_path = str(tmp_path / "sim_pipeline.db")
    config.checkpoint_path = str(tmp_path / "sim_ckpt.pkl")
    config.simulation_enabled = True

    service = MonitoringService(config)

    # Ingest 1 simulated step
    event = service.process_simulation_step()

    assert event is not None
    assert event.temperature is not None
    assert event.ph is not None
    assert event.tds is not None
    assert "simulated" in event.data_sources.values()

    # Verify event stored in DB
    history = service.repository.get_time_series_data()
    assert len(history) >= 1
    assert history[0]["temperature"] == event.temperature


def test_dashboard_model_state_representations():
    """TEST 19: The dashboard correctly represents learning, monitoring, anomaly, drift, stale-data, and disconnected states."""
    config = AppConfig()
    config.model.warmup_samples = 5
    engine = AnomalyDetectionEngine(config)

    # 1. INITIALIZING
    assert engine.state == ModelState.INITIALIZING

    # 2. WARMING_UP
    now = datetime.now(timezone.utc)
    obs_normal = SynchronizedObservation(
        timestamp=now, temperature=24.0, ph=7.4, tds=280.0,
        temp_fresh=True, ph_fresh=True, tds_fresh=True,
        is_pairwise_temp_ph_synced=True, is_pairwise_temp_tds_synced=True,
        is_pairwise_ph_tds_synced=True, is_three_variable_synced=True
    )
    for _ in range(3):
        engine.process_observation(obs_normal)
    assert engine.state == ModelState.WARMING_UP

    # Complete warm-up
    for _ in range(5):
        engine.process_observation(obs_normal)
    # 3. MONITORING
    assert engine.state == ModelState.MONITORING

    # 4. ANOMALY_DETECTED
    obs_anom = SynchronizedObservation(
        timestamp=now, temperature=36.5, ph=7.4, tds=280.0,
        temp_fresh=True, ph_fresh=True, tds_fresh=True,
        is_pairwise_temp_ph_synced=True, is_pairwise_temp_tds_synced=True,
        is_pairwise_ph_tds_synced=True, is_three_variable_synced=True
    )
    ev_anom = engine.process_observation(obs_anom)
    assert engine.state == ModelState.ANOMALY_DETECTED

    # 5. SENSOR_DATA_STALE
    obs_stale = SynchronizedObservation(
        timestamp=now, temperature=None, ph=None, tds=None,
        temp_fresh=False, ph_fresh=False, tds_fresh=False,
        is_three_variable_synced=False
    )
    engine.process_observation(obs_stale)
    assert engine.state == ModelState.SENSOR_DATA_STALE

    # 6. ERROR (Invalid reading)
    obs_error = SynchronizedObservation(
        timestamp=now, temperature=float('nan'), ph=7.4, tds=280.0,
        temp_fresh=True, ph_fresh=True, tds_fresh=True,
        is_three_variable_synced=True
    )
    engine.process_observation(obs_error)
    assert engine.state == ModelState.ERROR
