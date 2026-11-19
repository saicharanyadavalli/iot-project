"""Automated tests for serial data parsing.
Covers:
- TEST 1: Valid temperature serial reading is parsed correctly.
- TEST 2: Malformed serial data is rejected safely.
"""

import pytest
from core.acquisition.data_parser import DataParser, ParsedReading


def test_valid_serial_reading_parsed_correctly():
    """TEST 1: Valid temperature serial reading is parsed correctly."""
    parser = DataParser(parse_mode="strict")

    # Format 1: ESP32 RX packet format with labeled temperature
    line1 = '[ESP32 RX] Received Packet #42: "Temp: 24.50 C"'
    res1 = parser.parse_line(line1)
    assert res1.is_valid is True
    assert res1.temperature == 24.50
    assert res1.packet_counter == 42
    assert res1.error_message is None

    # Format 2: ESP32 RX packet with bare float
    line2 = '[ESP32 RX] Received Packet #99: "25.75"'
    res2 = parser.parse_line(line2)
    assert res2.is_valid is True
    assert res2.temperature == 25.75
    assert res2.packet_counter == 99

    # Format 3: JSON payload
    line3 = '{"temperature": 23.4, "counter": 105}'
    res3 = parser.parse_line(line3)
    assert res3.is_valid is True
    assert res3.temperature == 23.4
    assert res3.packet_counter == 105

    # Format 4: Standalone direct string
    line4 = "Temp: 22.1 C"
    res4 = parser.parse_line(line4)
    assert res4.is_valid is True
    assert res4.temperature == 22.10


def test_malformed_serial_data_rejected_safely():
    """TEST 2: Malformed serial data is rejected safely without exceptions."""
    parser = DataParser(parse_mode="strict")

    malformed_cases = [
        "",
        "   ",
        "rst:0x1 (POWERON_RESET),boot:0x13",
        "Listening for incoming wireless packets from Arduino Nano...",
        '[ESP32 RX] Received Packet #10: "Corrupted!@#$%"',
        "Invalid non-numeric string here",
        '{"invalid": json',
        None,
    ]

    for raw in malformed_cases:
        res = parser.parse_line(raw)
        assert res.is_valid is False
        assert res.temperature is None
        assert res.error_message is not None


def test_ping_demo_mode_handling():
    """Verify ping_demo mode derives valid temp for hardware demonstration without sensor."""
    parser_strict = DataParser(parse_mode="strict")
    ping_line = '[ESP32 RX] Received Packet #76: "Ping from Nano #76"'
    res_strict = parser_strict.parse_line(ping_line)
    assert res_strict.is_valid is False
    assert "no temperature payload" in res_strict.error_message

    parser_demo = DataParser(parse_mode="ping_demo", ping_demo_baseline=24.5)
    res_demo = parser_demo.parse_line(ping_line)
    assert res_demo.is_valid is True
    assert res_demo.temperature is not None
    assert 23.0 <= res_demo.temperature <= 26.0
