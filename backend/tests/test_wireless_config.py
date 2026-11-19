"""Unit tests for wireless communication and dynamic range profile management."""

import pytest
import json
from unittest.mock import MagicMock, patch
from config.settings import AppConfig, WirelessConfig
from core.services.wireless_config_service import (
    WirelessConfigService,
    WirelessProfile,
    PROFILES,
    ConfigResult,
    DeviceChannel,
)

def test_wireless_profiles_definition():
    """Verify all 3 required profiles are properly defined with physical RF settings."""
    assert "SHORT" in PROFILES
    assert "BALANCED" in PROFILES
    assert "LONG" in PROFILES

    short = PROFILES["SHORT"]
    assert short.data_rate == "2MBPS"
    assert short.pa_level == "LOW"

    balanced = PROFILES["BALANCED"]
    assert balanced.data_rate == "1MBPS"
    assert balanced.pa_level == "HIGH"

    long_p = PROFILES["LONG"]
    assert long_p.data_rate == "250KBPS"
    assert long_p.pa_level == "MAX"

def test_wireless_config_serialization(tmp_path):
    """Verify AppConfig correctly persists and loads WirelessConfig."""
    cfg_file = tmp_path / "app_config.json"
    cfg = AppConfig()
    cfg.wireless.active_profile = "LONG"
    cfg.wireless.esp32_port = "COM13"
    cfg.wireless.nano_port = "COM12"
    cfg.save_to_file(str(cfg_file))

    loaded = AppConfig.load_from_file(str(cfg_file))
    assert loaded.wireless.active_profile == "LONG"
    assert loaded.wireless.esp32_port == "COM13"
    assert loaded.wireless.nano_port == "COM12"

def test_two_phase_commit_success():
    """Verify two-phase commit succeeds when both devices ACK properly."""
    svc = WirelessConfigService(esp32_port="COM13", nano_port="COM12")
    
    mock_esp = MagicMock(spec=DeviceChannel)
    mock_nano = MagicMock(spec=DeviceChannel)
    
    mock_esp.send_command.return_value = True
    mock_nano.send_command.return_value = True
    
    # Phase 2 READY acks
    mock_esp.wait_for_ack.side_effect = [
        {"type": "config_ack", "status": "READY"},       # prepare
        {"type": "config_ack", "status": "COMMITTED"},   # commit
    ]
    mock_nano.wait_for_ack.side_effect = [
        {"type": "config_ack", "status": "READY"},       # prepare
        {"type": "config_ack", "status": "COMMITTED"},   # commit
    ]
    
    svc._esp32_ch = mock_esp
    svc._nano_ch = mock_nano
    
    res = svc.apply_profile("SHORT")
    assert res.result == ConfigResult.SUCCESS
    assert svc.active_profile == "SHORT"
    assert mock_esp.send_command.call_count == 2
    assert mock_nano.send_command.call_count == 2

def test_two_phase_commit_abort_on_timeout():
    """Verify two-phase commit aborts when one device fails to ACK prepare."""
    svc = WirelessConfigService(esp32_port="COM13", nano_port="COM12")
    
    mock_esp = MagicMock(spec=DeviceChannel)
    mock_nano = MagicMock(spec=DeviceChannel)
    
    mock_esp.send_command.return_value = True
    mock_nano.send_command.return_value = True
    
    # ESP32 ready, but Nano times out
    mock_esp.wait_for_ack.return_value = {"type": "config_ack", "status": "READY"}
    mock_nano.wait_for_ack.return_value = None
    
    svc._esp32_ch = mock_esp
    svc._nano_ch = mock_nano
    
    res = svc.apply_profile("LONG")
    assert res.result in (ConfigResult.PARTIAL_FAIL, ConfigResult.TIMEOUT)
    assert svc.active_profile == "BALANCED" # Should NOT change
    
    # Verify abort was sent to both
    calls = [c[0][0]["type"] for c in mock_esp.send_command.call_args_list]
    assert "config_abort" in calls
