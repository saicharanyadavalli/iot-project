"""FastAPI Application Server for IoT Water Quality Monitoring.
Exposes RESTful endpoints and real-time WebSocket event streaming.
Bridges Next.js frontend with central MonitoringService and River ML engine.
"""

from __future__ import annotations
import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from config.settings import AppConfig
from core.services.monitoring_service import MonitoringService
from core.services.wireless_config_service import PROFILES
from api.websocket_manager import ws_manager
from api.schemas import (
    ManualReadingRequest,
    ThresholdConfigRequest,
    SamplingIntervalRequest,
    WirelessProfileRequest,
    SimulationStepRequest,
    SimulationDriftRequest,
    SimulationToggleRequest,
    PortScanResponse,
    PortConfigRequest,
    PortScanItem,
)

logger = logging.getLogger(__name__)

# Initialize FastAPI App
app = FastAPI(
    title="Adaptive IoT Water Quality Monitoring Platform API",
    description="REST and WebSocket API for Multivariate Anomaly Detection and Dynamic ESP32 Control",
    version="2.0.0",
)

# Enable CORS for Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Shared Service Singleton
_service: Optional[MonitoringService] = None
_main_loop: Optional[asyncio.AbstractEventLoop] = None


def get_service() -> MonitoringService:
    global _service
    if _service is None:
        cfg = AppConfig.load_from_file()
        _service = MonitoringService.get_instance(cfg)
    return _service


@app.on_event("startup")
async def startup_event():
    global _main_loop
    _main_loop = asyncio.get_running_loop()
    service = get_service()

    # Hook monitoring service processing pipeline to broadcast via WebSocket
    orig_process = service.process_latest_pipeline

    def hooked_process(current_time=None):
        event = orig_process(current_time=current_time)
        try:
            # Broadcast live sensor reading
            reading_data = {
                "timestamp": event.timestamp.isoformat(),
                "temperature": event.temperature,
                "ph": event.ph,
                "tds": event.tds,
                "data_sources": event.data_sources,
                "model_state": event.model_state.value,
                "is_anomaly": event.is_anomaly,
                "classification": event.classification,
                "severity": event.severity,
                "primary_score": event.primary_score,
                "adaptive_threshold": event.adaptive_threshold,
            }
            ws_manager.broadcast_sync("sensor_reading", reading_data, loop=_main_loop)

            if event.is_anomaly or event.classification.startswith("SAFETY"):
                ws_manager.broadcast_sync("anomaly_detected", reading_data, loop=_main_loop)

            if event.drift_status.drift_detected_now:
                ws_manager.broadcast_sync("drift_detected", {
                    "timestamp": event.timestamp.isoformat(),
                    "features": event.drift_status.drifted_features,
                    "details": event.drift_status.details,
                }, loop=_main_loop)
        except Exception as ex:
            logger.debug("Error in hooked_process broadcast: %s", ex)
        return event

    service.process_latest_pipeline = hooked_process
    logger.info("FastAPI IoT Platform initialized. Hooked WebSocket event dispatcher.")


@app.on_event("shutdown")
async def shutdown_event():
    service = get_service()
    service.shutdown()
    logger.info("FastAPI IoT Platform shutdown complete.")


# ---------------------------------------------------------------------------
# WebSocket Endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws/live")
async def websocket_live_endpoint(websocket: WebSocket):
    """Real-time bidirectional WebSocket connection.
    Immediately streams a system snapshot on connection, then pushes continuous sensor events.
    """
    await ws_manager.connect(websocket)
    service = get_service()

    # Send initial snapshot
    try:
        snapshot = {
            "type": "system_snapshot",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": {
                "status": _build_status_payload(service),
                "latest_readings": _build_latest_readings_payload(service),
            },
        }
        await websocket.send_json(snapshot)

        # Keep alive loop
        while True:
            # Client messages (heartbeat pings or query triggers)
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as e:
        logger.debug("WebSocket client error: %s", e)
        await ws_manager.disconnect(websocket)


# ---------------------------------------------------------------------------
# REST Endpoints: System Status & Metrics
# ---------------------------------------------------------------------------

@app.get("/api/status")
def get_system_status():
    """Retrieve full platform status, model state, readiness across stages, and hardware connectivity."""
    service = get_service()
    return _build_status_payload(service)


@app.get("/api/readings/latest")
def get_latest_readings():
    """Retrieve the latest individual and synchronized water quality observations."""
    service = get_service()
    return _build_latest_readings_payload(service)


@app.get("/api/readings/history")
def get_readings_history(
    window_minutes: Optional[int] = Query(None, description="Time window in minutes"),
    limit: int = Query(500, le=2000, description="Max observations to return"),
):
    """Retrieve historical observations for time-series charts."""
    service = get_service()
    data = service.repository.get_time_series_data(window_minutes=window_minutes)
    return {"total": len(data), "data": data[-limit:]}


@app.post("/api/readings/manual", status_code=status.HTTP_201_CREATED)
def submit_manual_reading(req: ManualReadingRequest):
    """Submit manual pH and TDS measurements.
    Instantly feeds timestamp synchronizer and evaluates multi-stage anomaly pipeline.
    """
    service = get_service()
    ts = datetime.fromisoformat(req.timestamp) if req.timestamp else datetime.now(timezone.utc)
    event = service.submit_manual_readings(ph=req.ph, tds=req.tds, timestamp=ts)

    return {
        "status": "SUCCESS",
        "timestamp": event.timestamp.isoformat(),
        "is_anomaly": event.is_anomaly,
        "classification": event.classification,
        "severity": event.severity,
        "primary_score": event.primary_score,
        "adaptive_threshold": event.adaptive_threshold,
    }


# ---------------------------------------------------------------------------
# REST Endpoints: Threshold Configuration
# ---------------------------------------------------------------------------

@app.get("/api/config/thresholds")
def get_threshold_config(installation_id: str = Query("default")):
    """Get active operating safety thresholds and version."""
    service = get_service()
    latest = service.repository.get_latest_threshold_config(installation_id=installation_id)
    if not latest:
        # Fall back to active memory config
        s = service.config.safety
        return {
            "version": 1,
            "installation_id": installation_id,
            "temp_min": s.temp_min,
            "temp_max": s.temp_max,
            "ph_min": s.ph_min,
            "ph_max": s.ph_max,
            "tds_min": s.tds_min,
            "tds_max": s.tds_max,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "notes": "Default operating boundaries",
        }
    return latest


@app.put("/api/config/thresholds")
def update_threshold_config(req: ThresholdConfigRequest):
    """Update user-defined sensor thresholds with strict validation and audit logging."""
    service = get_service()
    res = service.update_thresholds(
        temp_min=req.temp_min,
        temp_max=req.temp_max,
        ph_min=req.ph_min,
        ph_max=req.ph_max,
        tds_min=req.tds_min,
        tds_max=req.tds_max,
        installation_id=req.installation_id or "default",
        notes=req.notes,
    )
    if res.get("status") == "ERROR":
        raise HTTPException(status_code=400, detail=res.get("error"))

    # Broadcast configuration update over WebSocket
    ws_manager.broadcast_sync("configuration_updated", {
        "config_type": "thresholds",
        "version": res.get("version"),
        "thresholds": res.get("thresholds"),
    }, loop=_main_loop)

    return res


@app.get("/api/config/thresholds/history")
def get_threshold_history(
    installation_id: str = Query("default"),
    limit: int = Query(50, le=100),
):
    """Retrieve audit history of threshold configurations."""
    service = get_service()
    return service.repository.get_threshold_history(installation_id=installation_id, limit=limit)


# ---------------------------------------------------------------------------
# REST Endpoints: Sampling Interval Control
# ---------------------------------------------------------------------------

@app.get("/api/config/interval")
def get_sampling_interval_status():
    """Get current active, pending, and confirmed ESP32 sampling interval state."""
    service = get_service()
    if service.wireless_service:
        st = service.wireless_service.get_sampling_interval_status()
    else:
        st = {
            "active_interval_seconds": 5,
            "pending_interval_seconds": None,
            "last_cmd_id": None,
            "status": "IDLE",
            "last_ack_time": None,
            "esp32_connected": False,
        }
    return st


@app.post("/api/config/interval")
def set_sampling_interval(req: SamplingIntervalRequest):
    """Submit a dynamic sampling interval update to the ESP32 transmitter.
    Dispatches asynchronous command, validates ACK, and tracks status.
    """
    service = get_service()
    res = service.apply_sampling_interval(req.interval_seconds, cmd_id=req.cmd_id)

    # Broadcast event
    ws_manager.broadcast_sync("sampling_interval_status", res, loop=_main_loop)
    return res


@app.get("/api/config/interval/history")
def get_sampling_interval_history(limit: int = Query(50, le=100)):
    """Retrieve audit history of sampling interval configuration requests."""
    service = get_service()
    return service.repository.get_sampling_interval_history(limit=limit)


# ---------------------------------------------------------------------------
# REST Endpoints: Wireless Radio Profiles
# ---------------------------------------------------------------------------

@app.get("/api/config/wireless")
def get_wireless_status():
    """Retrieve nRF24L01 radio transmission profile status."""
    service = get_service()
    wservice = service.wireless_service
    profiles_dict = {
        name: {
            "name": spec.name,
            "pa_level": spec.pa_level,
            "data_rate": spec.data_rate,
            "channel": spec.channel,
            "retry_delay_us": spec.retry_delay * 250,
            "retry_count": spec.retry_count,
            "description": spec.description,
        }
        for name, spec in PROFILES.items()
    }

    if wservice:
        dev_st = wservice.get_device_statuses()
        active = wservice.active_profile
    else:
        dev_st = {"esp32": None, "nano": None}
        active = service.config.wireless.active_profile

    return {
        "active_profile": active,
        "profiles": profiles_dict,
        "devices": dev_st,
    }


@app.post("/api/config/wireless")
def set_wireless_profile(req: WirelessProfileRequest):
    """Apply an nRF24L01 radio transmission profile via two-phase commit."""
    service = get_service()
    res = service.apply_wireless_profile(req.profile)
    return {
        "result": res.result.value,
        "profile": res.profile,
        "esp32_ack": res.esp32_ack,
        "nano_ack": res.nano_ack,
        "error_message": res.error_message,
        "timestamp": res.timestamp,
    }


# ---------------------------------------------------------------------------
# REST Endpoints: Hardware Port Auto-Detection & Assignment
# ---------------------------------------------------------------------------

@app.get("/api/hardware/ports", response_model=PortScanResponse)
def scan_hardware_ports():
    """Scan and enumerate system COM ports with automatic device role heuristics."""
    service = get_service()
    ports_list = service.scan_ports()

    nano_conn = False
    esp_conn = False
    if service.wireless_service:
        st = service.wireless_service.get_device_statuses()
        if st.get("nano"):
            nano_conn = bool(getattr(st["nano"], "is_connected", False))
        if st.get("esp32"):
            esp_conn = bool(getattr(st["esp32"], "is_connected", False))

    return {
        "available_ports": ports_list,
        "active_nano_port": service.config.wireless.nano_port,
        "active_esp32_port": service.config.wireless.esp32_port,
        "nano_connected": nano_conn,
        "esp32_connected": esp_conn,
    }


@app.post("/api/hardware/ports")
def update_hardware_ports(req: PortConfigRequest):
    """Assign Arduino Nano (receiver) and/or ESP32 (transmitter) ports and reconnect."""
    service = get_service()
    res = service.reconfigure_ports(nano_port=req.nano_port, esp32_port=req.esp32_port)

    # Broadcast event
    ws_manager.broadcast_sync("port_configuration_updated", res, loop=_main_loop)
    return res


# ---------------------------------------------------------------------------
# REST Endpoints: Anomaly History & 3D Visualization Payload
# ---------------------------------------------------------------------------

@app.get("/api/anomalies/history")
def get_anomaly_history(limit: int = Query(100, le=500)):
    """Retrieve detected anomaly events with classifications, severity, and scores."""
    service = get_service()
    return service.repository.get_anomaly_history(limit=limit)


@app.get("/api/multivariate/3d")
def get_3d_state_space_data(limit: int = Query(500, le=2000)):
    """Retrieve full 3D coordinate space data (Temperature, pH, TDS)
    preserving normal vs anomalous markers, exact values, and classifications.
    """
    service = get_service()
    raw = service.repository.get_time_series_data()
    # Filter points where all 3 parameters are present
    points = []
    for r in raw:
        if r.get("temperature") is not None and r.get("ph") is not None and r.get("tds") is not None:
            points.append({
                "x": round(float(r["temperature"]), 2),
                "y": round(float(r["ph"]), 2),
                "z": round(float(r["tds"]), 1),
                "is_anomaly": int(r.get("is_anomaly", 0)),
                "classification": r.get("classification", "NORMAL"),
                "severity": r.get("severity", "NONE"),
                "primary_score": round(float(r.get("primary_score", 0.0)), 4),
                "timestamp": r.get("timestamp"),
            })
    return {"total": len(points), "points": points[-limit:]}


# ---------------------------------------------------------------------------
# REST Endpoints: Simulation & Checkpoint Operations
# ---------------------------------------------------------------------------

@app.post("/api/simulation/step")
def trigger_simulation_step(req: SimulationStepRequest):
    """Execute a single simulated observation step through the pipeline."""
    service = get_service()
    event = service.process_simulation_step(injected_type=req.injected_type)
    return {
        "status": "SUCCESS",
        "timestamp": event.timestamp.isoformat(),
        "temperature": event.temperature,
        "ph": event.ph,
        "tds": event.tds,
        "is_anomaly": event.is_anomaly,
        "classification": event.classification,
        "primary_score": event.primary_score,
    }


@app.post("/api/simulation/drift")
def trigger_simulation_drift(req: SimulationDriftRequest):
    """Initiate or reset gradual environmental drift."""
    service = get_service()
    if req.action.lower() == "start":
        service.simulator.start_gradual_drift()
        return {"status": "SUCCESS", "drift_active": True, "message": "Gradual environmental drift initiated"}
    else:
        service.simulator.reset_drift()
        return {"status": "SUCCESS", "drift_active": False, "message": "Environmental drift reset to baseline"}


@app.post("/api/simulation/toggle")
def toggle_simulation_mode(req: SimulationToggleRequest):
    """Switch between physical serial acquisition and simulated environment."""
    service = get_service()
    service.config.simulation_enabled = req.enabled
    service.config.save_to_file()
    if req.enabled:
        if service.serial_reader:
            service.serial_reader.stop()
            service.serial_reader = None
        if service.wireless_service:
            service.wireless_service.stop()
            service.wireless_service = None
    else:
        service._start_serial()
        service._start_wireless_service()
    return {"status": "SUCCESS", "simulation_enabled": req.enabled}


@app.post("/api/checkpoint/save")
def save_model_checkpoint():
    """Trigger an atomic model checkpoint save."""
    service = get_service()
    ok = service.save_checkpoint_now()
    return {"status": "SUCCESS" if ok else "FAILED", "checkpoint_path": service.config.checkpoint_path}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_status_payload(service: MonitoringService) -> Dict[str, Any]:
    engine = service.engine
    serial_conn = False
    if service.serial_reader and service.serial_reader.is_connected:
        serial_conn = True
    elif service.wireless_service and service.wireless_service.nano_status.connected:
        serial_conn = True

    stage_readiness = service.get_stage_readiness()
    interval_st = (
        service.wireless_service.get_sampling_interval_status()
        if service.wireless_service
        else {"active_interval_seconds": 5, "status": "IDLE"}
    )

    return {
        "model_state": engine.state.value,
        "serial_connected": serial_conn,
        "simulation_enabled": service.config.simulation_enabled,
        "total_observations": engine.total_observations,
        "warmup_count": engine.warmup_count,
        "warmup_target": service.config.model.warmup_samples,
        "observations_learned": engine.observations_learned,
        "total_anomalies": service.total_anomalies_detected,
        "last_detection_time": engine.last_detection_time.isoformat() if engine.last_detection_time else None,
        "sampling_interval": interval_st,
        "wireless_profile": service.config.wireless.active_profile,
        "stage_readiness": stage_readiness,
    }


def _build_latest_readings_payload(service: MonitoringService) -> Dict[str, Any]:
    sync = service.synchronizer
    now = datetime.now(timezone.utc)

    def format_item(item, max_age):
        if not item:
            return {"value": None, "timestamp": None, "data_source": "none", "is_stale": True}
        age = (now - item.timestamp).total_seconds()
        return {
            "value": round(item.value, 2),
            "timestamp": item.timestamp.isoformat(),
            "data_source": item.data_source,
            "is_stale": age > max_age,
            "age_seconds": round(age, 1),
        }

    obs = sync.get_synchronized_observation()
    return {
        "temperature": format_item(sync.latest_temp, service.config.sync.max_measurement_age_sec),
        "ph": format_item(sync.latest_ph, service.config.sync.max_measurement_age_sec),
        "tds": format_item(sync.latest_tds, service.config.sync.max_measurement_age_sec),
        "is_three_variable_synced": obs.is_three_variable_synced,
        "latest_event": {
            "classification": service.latest_event.classification,
            "severity": service.latest_event.severity,
            "is_anomaly": service.latest_event.is_anomaly,
            "primary_score": service.latest_event.primary_score,
            "adaptive_threshold": service.latest_event.adaptive_threshold,
        } if service.latest_event else None,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.server:app", host="0.0.0.0", port=8000, reload=False)
