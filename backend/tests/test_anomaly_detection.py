"""Automated tests for online anomaly detection across all feature combinations.
Covers:
- TEST 6: Individual temperature anomaly is detected (Case 1).
- TEST 7: Individual pH anomaly is detected (Case 2).
- TEST 8: Individual TDS anomaly is detected (Case 3).
- TEST 9: Temperature + pH unusual combination is tested (Case 4).
- TEST 10: Temperature + TDS unusual combination is tested (Case 5).
- TEST 11: pH + TDS unusual combination is tested (Case 6).
- TEST 12: Three-parameter unusual combination is tested (Case 7).
- TEST 13: Normal incoming stream does not continuously trigger excessive false alerts.
- TEST 14: Anomalous observation does not incorrectly update the protected detector.
"""

import pytest
import random
from datetime import datetime, timezone
from config.settings import AppConfig, ModelConfig
from core.anomaly.online_detector import AnomalyDetectionEngine, ModelState
from core.processing.synchronization import SynchronizedObservation


def create_warm_engine(n_warmup: int = 45) -> AnomalyDetectionEngine:
    """Helper to instantiate an engine and warm it up with baseline observations."""
    config = AppConfig()
    config.model.warmup_samples = 40
    engine = AnomalyDetectionEngine(config)

    rng = random.Random(42)
    now = datetime.now(timezone.utc)

    for i in range(n_warmup):
        obs = SynchronizedObservation(
            timestamp=now,
            temperature=round(24.0 + rng.gauss(0, 0.2), 2),
            ph=round(7.4 + rng.gauss(0, 0.03), 2),
            tds=round(280.0 + rng.gauss(0, 3.0), 1),
            temp_fresh=True,
            ph_fresh=True,
            tds_fresh=True,
            is_pairwise_temp_ph_synced=True,
            is_pairwise_temp_tds_synced=True,
            is_pairwise_ph_tds_synced=True,
            is_three_variable_synced=True,
            data_sources={"temperature": "test", "ph": "test", "tds": "test"},
        )
        engine.process_observation(obs)

    assert engine.state == ModelState.MONITORING
    return engine


def test_individual_temperature_anomaly():
    """TEST 6: Individual temperature anomaly is detected (Case 1)."""
    engine = create_warm_engine()
    now = datetime.now(timezone.utc)

    # Spike temperature to 35.5°C while pH (7.4) and TDS (280) remain baseline normal
    obs = SynchronizedObservation(
        timestamp=now,
        temperature=35.5,
        ph=7.4,
        tds=280.0,
        temp_fresh=True,
        ph_fresh=True,
        tds_fresh=True,
        is_pairwise_temp_ph_synced=True,
        is_pairwise_temp_tds_synced=True,
        is_pairwise_ph_tds_synced=True,
        is_three_variable_synced=True,
    )
    event = engine.process_observation(obs)
    assert event.is_anomaly is True
    assert "TEMPERATURE" in event.classification


def test_individual_ph_anomaly():
    """TEST 7: Individual pH anomaly is detected (Case 2)."""
    engine = create_warm_engine()
    now = datetime.now(timezone.utc)

    # Spike pH to 8.45 while temperature (24.0) and TDS (280) remain baseline normal
    obs = SynchronizedObservation(
        timestamp=now,
        temperature=24.0,
        ph=8.45,
        tds=280.0,
        temp_fresh=True,
        ph_fresh=True,
        tds_fresh=True,
        is_pairwise_temp_ph_synced=True,
        is_pairwise_temp_tds_synced=True,
        is_pairwise_ph_tds_synced=True,
        is_three_variable_synced=True,
    )
    event = engine.process_observation(obs)
    assert event.is_anomaly is True
    assert "PH" in event.classification


def test_individual_tds_anomaly():
    """TEST 8: Individual TDS anomaly is detected (Case 3)."""
    engine = create_warm_engine()
    now = datetime.now(timezone.utc)

    # Spike TDS to 520.0 ppm while temperature (24.0) and pH (7.4) remain baseline normal
    obs = SynchronizedObservation(
        timestamp=now,
        temperature=24.0,
        ph=7.4,
        tds=520.0,
        temp_fresh=True,
        ph_fresh=True,
        tds_fresh=True,
        is_pairwise_temp_ph_synced=True,
        is_pairwise_temp_tds_synced=True,
        is_pairwise_ph_tds_synced=True,
        is_three_variable_synced=True,
    )
    event = engine.process_observation(obs)
    assert event.is_anomaly is True
    assert "TDS" in event.classification


def test_temperature_ph_combination_anomaly():
    """TEST 9: Temperature + pH unusual combination is tested (Case 4)."""
    engine = create_warm_engine()
    now = datetime.now(timezone.utc)

    # Simultaneous unusual shift in Temp and pH
    obs = SynchronizedObservation(
        timestamp=now,
        temperature=34.0,
        ph=6.7,
        tds=280.0,
        temp_fresh=True,
        ph_fresh=True,
        tds_fresh=True,
        is_pairwise_temp_ph_synced=True,
        is_pairwise_temp_tds_synced=True,
        is_pairwise_ph_tds_synced=True,
        is_three_variable_synced=True,
    )
    event = engine.process_observation(obs)
    assert event.is_anomaly is True


def test_temperature_tds_combination_anomaly():
    """TEST 10: Temperature + TDS unusual combination is tested (Case 5)."""
    engine = create_warm_engine()
    now = datetime.now(timezone.utc)

    # Unusual shift in Temp and TDS together
    obs = SynchronizedObservation(
        timestamp=now,
        temperature=33.5,
        ph=7.4,
        tds=480.0,
        temp_fresh=True,
        ph_fresh=True,
        tds_fresh=True,
        is_pairwise_temp_ph_synced=True,
        is_pairwise_temp_tds_synced=True,
        is_pairwise_ph_tds_synced=True,
        is_three_variable_synced=True,
    )
    event = engine.process_observation(obs)
    assert event.is_anomaly is True


def test_ph_tds_combination_anomaly():
    """TEST 11: pH + TDS unusual combination is tested (Case 6)."""
    engine = create_warm_engine()
    now = datetime.now(timezone.utc)

    # Unusual shift in pH and TDS together
    obs = SynchronizedObservation(
        timestamp=now,
        temperature=24.0,
        ph=8.2,
        tds=490.0,
        temp_fresh=True,
        ph_fresh=True,
        tds_fresh=True,
        is_pairwise_temp_ph_synced=True,
        is_pairwise_temp_tds_synced=True,
        is_pairwise_ph_tds_synced=True,
        is_three_variable_synced=True,
    )
    event = engine.process_observation(obs)
    assert event.is_anomaly is True


def test_three_parameter_combination_anomaly():
    """TEST 12: Three-parameter unusual combination is tested (Case 7)."""
    engine = create_warm_engine()
    now = datetime.now(timezone.utc)

    # Joint shift across all three parameters
    obs = SynchronizedObservation(
        timestamp=now,
        temperature=32.0,
        ph=8.2,
        tds=470.0,
        temp_fresh=True,
        ph_fresh=True,
        tds_fresh=True,
        is_pairwise_temp_ph_synced=True,
        is_pairwise_temp_tds_synced=True,
        is_pairwise_ph_tds_synced=True,
        is_three_variable_synced=True,
    )
    event = engine.process_observation(obs)
    assert event.is_anomaly is True


def test_normal_stream_low_false_positive_rate():
    """TEST 13: A normal incoming stream does not continuously trigger excessive false alerts."""
    engine = create_warm_engine(n_warmup=50)
    rng = random.Random(99)
    now = datetime.now(timezone.utc)

    n_samples = 30
    anomalies_count = 0

    for _ in range(n_samples):
        obs = SynchronizedObservation(
            timestamp=now,
            temperature=round(24.0 + rng.gauss(0, 0.15), 2),
            ph=round(7.4 + rng.gauss(0, 0.02), 2),
            tds=round(280.0 + rng.gauss(0, 2.5), 1),
            temp_fresh=True,
            ph_fresh=True,
            tds_fresh=True,
            is_pairwise_temp_ph_synced=True,
            is_pairwise_temp_tds_synced=True,
            is_pairwise_ph_tds_synced=True,
            is_three_variable_synced=True,
        )
        event = engine.process_observation(obs)
        if event.is_anomaly:
            anomalies_count += 1

    # False positive rate should be <= 10% on normal data with q=0.99
    assert anomalies_count <= 3


def test_anomalous_observation_does_not_update_protected_detector():
    """TEST 14: An anomalous observation does not incorrectly update the protected detector."""
    engine = create_warm_engine()
    initial_learned = engine.observations_learned
    initial_rejected = engine.anomalies_rejected

    now = datetime.now(timezone.utc)
    # Severe anomalous spike
    obs = SynchronizedObservation(
        timestamp=now,
        temperature=36.0,
        ph=7.4,
        tds=280.0,
        temp_fresh=True,
        ph_fresh=True,
        tds_fresh=True,
        is_pairwise_temp_ph_synced=True,
        is_pairwise_temp_tds_synced=True,
        is_pairwise_ph_tds_synced=True,
        is_three_variable_synced=True,
    )
    event = engine.process_observation(obs)
    assert event.is_anomaly is True
    assert event.learned_this_step is False
    assert engine.observations_learned == initial_learned
    assert engine.anomalies_rejected == initial_rejected + 1
    assert "Protected" in event.rejection_reason
