"""Pydantic schemas and API contracts for REST and WebSocket interfaces."""

from __future__ import annotations
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class ManualReadingRequest(BaseModel):
    ph: float = Field(..., ge=0.0, le=14.0, description="pH acidity measurement [0.0 - 14.0]")
    tds: float = Field(..., ge=0.0, le=5000.0, description="Total Dissolved Solids in ppm [0 - 5000]")
    timestamp: Optional[str] = Field(None, description="ISO-8601 timestamp string")


class ThresholdConfigRequest(BaseModel):
    temp_min: float = Field(..., ge=-40.0, le=125.0, description="Lower temperature threshold in °C")
    temp_max: float = Field(..., ge=-40.0, le=125.0, description="Upper temperature threshold in °C")
    ph_min: float = Field(..., ge=0.0, le=14.0, description="Lower pH threshold")
    ph_max: float = Field(..., ge=0.0, le=14.0, description="Upper pH threshold")
    tds_min: float = Field(..., ge=0.0, le=5000.0, description="Lower TDS threshold in ppm")
    tds_max: float = Field(..., ge=0.0, le=5000.0, description="Upper TDS threshold in ppm")
    installation_id: Optional[str] = Field("default", description="Environment / deployment profile ID")
    notes: Optional[str] = Field(None, description="Optional audit notes or rationale")


class SamplingIntervalRequest(BaseModel):
    interval_seconds: int = Field(..., ge=2, le=3600, description="Sampling interval in seconds [2 - 3600]")
    cmd_id: Optional[str] = Field(None, description="Optional client-generated tracking command ID")


class WirelessProfileRequest(BaseModel):
    profile: str = Field(..., description="Target radio transmission profile: SHORT, BALANCED, or LONG")


class SimulationStepRequest(BaseModel):
    injected_type: Optional[str] = Field(None, description="Fault injection category: temp_only, ph_only, tds_only, temp_ph, temp_tds, ph_tds, three_param, safety_violation")


class SimulationDriftRequest(BaseModel):
    action: str = Field(..., description="'start' to initiate environmental drift, 'reset' to return to baseline")


class SimulationToggleRequest(BaseModel):
    enabled: bool = Field(..., description="True to enable simulation mode, False for physical hardware")


class PortScanItem(BaseModel):
    device: str
    description: str
    hwid: str
    manufacturer: Optional[str] = None
    suggested_role: str = "unknown"  # "nano" | "esp32" | "bluetooth" | "unknown"
    is_active_nano: bool = False
    is_active_esp32: bool = False
    is_open: bool = False


class PortScanResponse(BaseModel):
    available_ports: List[PortScanItem]
    active_nano_port: str
    active_esp32_port: str
    nano_connected: bool
    esp32_connected: bool


class PortConfigRequest(BaseModel):
    nano_port: Optional[str] = Field(None, description="COM port assigned to Arduino Nano receiver")
    esp32_port: Optional[str] = Field(None, description="COM port assigned to ESP32 transmitter")
