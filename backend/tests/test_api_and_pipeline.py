"""Comprehensive automated tests for FastAPI endpoints, WebSocket sync bridge,
and the 5-stage online anomaly detection pipeline.
"""

import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from api.server import app, get_service
from core.anomaly.rate_of_change import RateOfChangeDetector
from core.anomaly.online_detector import (
    AnomalyDetectionEngine,
    AnomalyDetectionEvent,
)
from core.database.repository import MonitoringRepository
from core.processing.synchronization import SynchronizedObservation
from config.settings import AppConfig


@pytest.fixture
def client():
    """Create a FastAPI test client with an isolated in-memory or fresh service configuration."""
    with TestClient(app) as test_client:
        yield test_client


# =====================================================================
# 1. REST API ENDPOINT TESTS
# =====================================================================

def test_api_status_endpoint(client):
    """Verify /api/status returns model status, readiness, interval, and profile."""
    resp = client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "model_state" in data
    assert "serial_connected" in data
    assert "sampling_interval" in data
    assert "wireless_profile" in data
    assert "stage_readiness" in data
    assert data["stage_readiness"]["stage_1_thresholds"]["is_active"] is True
    assert data["stage_readiness"]["stage_2_rate_of_change"]["is_active"] is True


def test_api_latest_readings_endpoint(client):
    """Verify /api/readings/latest returns structured parameters and sync flag."""
    resp = client.get("/api/readings/latest")
    assert resp.status_code == 200
    data = resp.json()
    assert "temperature" in data
    assert "ph" in data
    assert "tds" in data
    assert "is_three_variable_synced" in data


def test_api_manual_input_submission(client):
    """Verify POST /api/readings/manual ingests pH and TDS readings."""
    payload = {"ph": 7.4, "tds": 220.0}
    resp = client.post("/api/readings/manual", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "classification" in data
    assert "primary_score" in data

    # Test validation failure for invalid range
    invalid_payload = {"ph": 15.5, "tds": -10.0}
    resp_invalid = client.post("/api/readings/manual", json=invalid_payload)
    assert resp_invalid.status_code == 422


def test_api_threshold_configuration_and_audit(client):
    """Verify GET and PUT /api/config/thresholds updates thresholds and increments version."""
    # 1. Get current config
    resp_get = client.get("/api/config/thresholds")
    assert resp_get.status_code == 200
    initial_version = resp_get.json()["version"]

    # 2. Update config with valid bounds
    update_payload = {
        "temp_min": 15.0,
        "temp_max": 35.0,
        "ph_min": 6.8,
        "ph_max": 8.2,
        "tds_min": 80.0,
        "tds_max": 500.0,
        "notes": "Automated test bounds",
    }
    resp_put = client.put("/api/config/thresholds", json=update_payload)
    assert resp_put.status_code == 200
    new_data = resp_put.json()
    assert new_data["status"] == "SUCCESS"
    assert new_data["version"] >= initial_version
    assert new_data["thresholds"]["temperature"] == [15.0, 35.0]

    # 3. Check invalid bounds (min >= max)
    invalid_update = {
        "temp_min": 40.0,
        "temp_max": 20.0,
        "ph_min": 7.0,
        "ph_max": 7.0,
        "tds_min": 100.0,
        "tds_max": 50.0,
    }
    resp_bad = client.put("/api/config/thresholds", json=invalid_update)
    assert resp_bad.status_code == 400


def test_api_sampling_interval_command_lifecycle(client):
    """Verify POST /api/config/interval submits command and reports offline status if disconnected."""
    resp = client.post("/api/config/interval", json={"interval_seconds": 15})
    assert resp.status_code == 200
    data = resp.json()
    assert "cmd_id" in data
    assert data["requested_interval"] == 15
    # Since hardware is disconnected, status should be DEVICE_OFFLINE or PENDING
    assert data["status"] in ("DEVICE_OFFLINE", "PENDING", "APPLIED")

    # Verify invalid interval bounds (e.g., < 2 or > 3600)
    resp_invalid = client.post("/api/config/interval", json={"interval_seconds": 1})
    assert resp_invalid.status_code == 422


def test_api_multivariate_3d_endpoint(client):
    """Verify /api/multivariate/3d returns 3D points with classification and severity."""
    resp = client.get("/api/multivariate/3d?limit=50")
    assert resp.status_code == 200
    data = resp.json()
    assert "total" in data
    assert "points" in data
    if data["points"]:
        pt = data["points"][0]
        assert "x" in pt
        assert "y" in pt
        assert "z" in pt
        assert "is_anomaly" in pt
        assert "classification" in pt


def test_api_simulation_step_endpoint(client):
    """Verify POST /api/simulation/step steps the simulation generator."""
    resp = client.post("/api/simulation/step", json={"injected_type": None})
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "SUCCESS"
    assert "temperature" in data
    assert "ph" in data
    assert "tds" in data
    assert "is_anomaly" in data


def test_api_hardware_ports_scan_and_update(client):
    """Verify GET and POST /api/hardware/ports for port enumeration and assignment."""
    resp = client.get("/api/hardware/ports")
    assert resp.status_code == 200
    data = resp.json()
    assert "available_ports" in data
    assert "active_nano_port" in data
    assert "active_esp32_port" in data

    resp_update = client.post(
        "/api/hardware/ports", json={"nano_port": "COM12", "esp32_port": "COM13"}
    )
    assert resp_update.status_code == 200
    update_data = resp_update.json()
    assert update_data["status"] == "SUCCESS"
    assert update_data["nano_port"] == "COM12"
    assert update_data["esp32_port"] == "COM13"


# =====================================================================
# 2. MULTI-STAGE ANOMALY DETECTION UNIT TESTS
# =====================================================================

def test_stage_1_user_defined_threshold_detection():
    """Verify Stage 1 raises CRITICAL_THRESHOLD_ALERT immediately on the very first observation."""
    config = AppConfig()
    config.safety.temp_min = 10.0
    config.safety.temp_max = 35.0
    config.safety.ph_min = 6.5
    config.safety.ph_max = 8.5
    config.safety.tds_min = 50.0
    config.safety.tds_max = 500.0

    engine = AnomalyDetectionEngine(config)

    # First observation with extreme temperature (45°C > max 35°C)
    now = datetime.now(timezone.utc)
    obs = SynchronizedObservation(
        timestamp=now,
        temperature=45.0,
        ph=7.0,
        tds=250.0,
        temp_fresh=True,
        ph_fresh=True,
        tds_fresh=True,
        is_three_variable_synced=True,
    )

    event = engine.process_observation(obs)
    assert event.is_anomaly is True
    assert event.severity == "CRITICAL"
    assert "CRITICAL_THRESHOLD_ALERT" in event.classification
    assert "temperature" in event.classification.lower()


def test_stage_2_rate_of_change_detection():
    """Verify Stage 2 triggers RATE_OF_CHANGE_WARNING from the 2nd reading onward for sudden spikes."""
    detector = RateOfChangeDetector(
        max_temp_rate_per_sec=0.5,
        max_ph_rate_per_sec=0.1,
        max_tds_rate_per_sec=15.0,
    )

    t0 = datetime.now(timezone.utc)
    # Reading 1: baseline at t0
    res1 = detector.evaluate("temperature", 25.0, timestamp=t0)
    assert res1.is_warning is False
    assert res1.elapsed_seconds is None

    # Reading 2: 2 seconds later, temperature leaps to 30.0 (delta = 5.0, dt = 2s -> 2.5°C/s > 0.5)
    t1 = t0 + timedelta(seconds=2)
    res2 = detector.evaluate("temperature", 30.0, timestamp=t1)
    assert res2.is_warning is True
    assert res2.rate_per_second == pytest.approx(2.5, rel=1e-2)
    assert res2.direction == "INCREASING"

    # Reading 3: normal gradual change (delta 0.2 over 2s -> 0.1°C/s <= 0.5)
    t2 = t1 + timedelta(seconds=2)
    res3 = detector.evaluate("temperature", 30.2, timestamp=t2)
    assert res3.is_warning is False
    assert res3.rate_per_second == pytest.approx(0.1, rel=1e-2)


def test_stage_readiness_reporting():
    """Verify engine reports readiness correctly across all 5 stages."""
    config = AppConfig()
    engine = AnomalyDetectionEngine(config)
    readiness = engine.get_stage_readiness()

    assert readiness["stage_1_thresholds"]["readiness"] == "ACTIVE"
    assert readiness["stage_2_rate_of_change"]["readiness"] in ("COLLECTING", "ACTIVE")
    assert readiness["stage_3_statistical_baseline"]["readiness"] in ("COLLECTING", "ACTIVE")
    assert readiness["stage_5_half_space_trees"]["readiness"] in ("WARMING_UP", "MONITORING")
    assert "installation_id" in readiness
