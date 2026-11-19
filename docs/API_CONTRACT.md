# API Contract: REST Endpoints & WebSocket Events

## 1. Overview
The platform exposes a dual interface:
- **REST API:** High-throughput JSON endpoints for state retrieval, configuration changes, manual measurement submissions, and simulation triggers (`http://localhost:8000`).
- **WebSocket Stream:** Real-time push notifications for live telemetry, anomaly alerts, and hardware state broadcasts (`ws://localhost:8000/ws/live`).

---

## 2. REST Endpoints Specification

### 2.1 System Diagnostics & Health
#### `GET /api/status`
Returns high-level status of the anomaly detection engine, hardware connections, sampling interval, active wireless profile, and 5-stage readiness.
- **Request:** None
- **Response (200 OK):**
```json
{
  "model_state": "MONITORING",
  "serial_connected": false,
  "simulation_enabled": false,
  "total_observations": 163,
  "warmup_count": 40,
  "warmup_target": 40,
  "observations_learned": 73,
  "total_anomalies": 91,
  "last_detection_time": "2026-11-19T07:15:37.412712+00:00",
  "sampling_interval": {
    "active_interval_seconds": 5,
    "pending_interval_seconds": null,
    "last_cmd_id": null,
    "status": "IDLE",
    "last_ack_time": null,
    "esp32_connected": false
  },
  "wireless_profile": "BALANCED",
  "stage_readiness": {
    "stage_1_thresholds": {
      "name": "User-Defined Operating Thresholds",
      "is_active": true,
      "readiness": "ACTIVE",
      "description": "Evaluates operating bounds immediately from the first reading."
    },
    "stage_2_rate_of_change": {
      "name": "Rate of Change Monitoring",
      "is_active": true,
      "readiness": "ACTIVE",
      "description": "Calculates temporal derivative (change/sec) from the second observation onward."
    },
    "stage_3_statistical_baseline": {
      "name": "Statistical Baseline Collection",
      "is_active": true,
      "readiness": "ACTIVE",
      "sample_count": { "temperature": 30, "ph": 30, "tds": 30 }
    },
    "stage_4_robust_zscore": {
      "name": "Rolling Median + MAD",
      "is_active": true,
      "readiness": "ACTIVE"
    },
    "stage_5_half_space_trees": {
      "name": "Multivariate Half-Space Trees",
      "is_active": true,
      "readiness": "MONITORING",
      "warmup_progress": "40/40"
    },
    "installation_id": "default",
    "total_observations": 163,
    "observations_learned": 73,
    "anomalies_rejected": 90
  }
}
```

---

### 2.2 Telemetry & Sensor Readings
#### `GET /api/readings/latest`
Returns the most recent reading for each sensor parameter, freshness flags, age, and latest event evaluation.
- **Request:** None
- **Response (200 OK):**
```json
{
  "temperature": {
    "value": 24.50,
    "timestamp": "2026-11-19T07:20:00.000000+00:00",
    "data_source": "physical_serial",
    "is_stale": false,
    "age_seconds": 3.2
  },
  "ph": {
    "value": 7.25,
    "timestamp": "2026-11-19T07:19:45.000000+00:00",
    "data_source": "manual_input",
    "is_stale": false,
    "age_seconds": 18.2
  },
  "tds": {
    "value": 280.0,
    "timestamp": "2026-11-19T07:19:45.000000+00:00",
    "data_source": "manual_input",
    "is_stale": false,
    "age_seconds": 18.2
  },
  "is_three_variable_synced": true,
  "latest_event": {
    "classification": "NORMAL",
    "severity": "NORMAL",
    "is_anomaly": false,
    "primary_score": 0.0412,
    "adaptive_threshold": 0.6500
  }
}
```

#### `POST /api/readings/manual`
Submit manual pH and TDS measurements. Immediately feeds the Timestamp Synchronizer and evaluates the 5-stage anomaly detection pipeline.
- **Request Body (JSON):**
```json
{
  "ph": 7.40,
  "tds": 220.0,
  "timestamp": "2026-11-19T07:25:00.000000+00:00"
}
```
- **Response (201 Created):**
```json
{
  "status": "SUCCESS",
  "timestamp": "2026-11-19T07:25:00.000000+00:00",
  "is_anomaly": false,
  "classification": "NORMAL",
  "severity": "NORMAL",
  "primary_score": 0.0385,
  "adaptive_threshold": 0.6500
}
```

#### `GET /api/readings/history`
Query paginated time-series observations.
- **Query Params:** `limit` (default: 100, max: 2000), `window_minutes` (optional)
- **Response (200 OK):**
```json
{
  "total": 100,
  "data": [
    {
      "id": 1,
      "timestamp": "2026-11-19T07:00:00.000000+00:00",
      "temperature": 24.1,
      "ph": 7.2,
      "tds": 240.0,
      "is_anomaly": 0,
      "classification": "NORMAL",
      "severity": "NONE",
      "primary_score": 0.02
    }
  ]
}
```

---

### 2.3 Multivariate 3D Coordinates
#### `GET /api/multivariate/3d`
Returns 3D state-space coordinate points $(X=\text{Temperature}, Y=\text{pH}, Z=\text{TDS})$ with classification, severity, and anomaly flags for Plotly rendering.
- **Query Params:** `limit` (default: 500, max: 2000)
- **Response (200 OK):**
```json
{
  "total": 79,
  "points": [
    {
      "x": 25.64,
      "y": 7.43,
      "z": 276.0,
      "is_anomaly": 0,
      "classification": "NORMAL",
      "severity": "NONE",
      "primary_score": 0.0415,
      "timestamp": "2026-11-19T07:15:37+00:00"
    }
  ]
}
```

---

### 2.4 Safety Thresholds Configuration
#### `GET /api/config/thresholds`
Retrieve active operating safety thresholds and configuration version.
- **Query Params:** `installation_id` (default: "default")
- **Response (200 OK):**
```json
{
  "version": 2,
  "installation_id": "default",
  "temp_min": 10.0,
  "temp_max": 38.0,
  "ph_min": 6.5,
  "ph_max": 8.5,
  "tds_min": 50.0,
  "tds_max": 600.0,
  "timestamp": "2026-11-19T07:20:11.749855+00:00",
  "notes": "Potable water safety profile"
}
```

#### `PUT /api/config/thresholds`
Update operating thresholds with strict validation ($Min < Max$). Automatically increments audit log version.
- **Request Body (JSON):**
```json
{
  "temp_min": 15.0,
  "temp_max": 35.0,
  "ph_min": 6.8,
  "ph_max": 8.2,
  "tds_min": 80.0,
  "tds_max": 500.0,
  "installation_id": "default",
  "notes": "Aquaculture safety threshold update"
}
```
- **Response (200 OK):**
```json
{
  "status": "SUCCESS",
  "version": 3,
  "thresholds": {
    "temperature": [15.0, 35.0],
    "ph": [6.8, 8.2],
    "tds": [80.0, 500.0]
  },
  "installation_id": "default"
}
```

---

### 2.5 Hardware & Dynamic Sampling Interval
#### `GET /api/config/interval`
Retrieve current active, pending, and confirmed ESP32 sampling interval state.
- **Response (200 OK):**
```json
{
  "active_interval_seconds": 5,
  "pending_interval_seconds": null,
  "last_cmd_id": "cmd-1732000000",
  "status": "APPLIED",
  "last_ack_time": "2026-11-19T07:15:37+00:00",
  "esp32_connected": false
}
```

#### `POST /api/config/interval`
Dispatch dynamic interval command to the ESP32 transmitter.
- **Request Body (JSON):**
```json
{
  "interval_seconds": 10,
  "cmd_id": "custom-cmd-001"
}
```
- **Response (200 OK):**
```json
{
  "status": "DEVICE_OFFLINE",
  "requested_interval": 10,
  "applied_interval": 5,
  "cmd_id": "custom-cmd-001",
  "error": "ESP32 disconnected. Configuration registered as PENDING."
}
```

#### `GET /api/config/wireless` & `POST /api/config/wireless`
Get or set nRF24L01 radio transmission profile (`SHORT`, `BALANCED`, `LONG`) via Two-Phase Commit protocol.

---

### 2.6 Hardware Serial COM Port Auto-Detection & Mapping
#### `GET /api/hardware/ports`
Enumerate system serial COM interfaces and predict device roles (Arduino Nano vs ESP32) using USB hardware heuristics.
- **Request:** None
- **Response (200 OK):**
```json
{
  "available_ports": [
    {
      "device": "COM12",
      "description": "USB-SERIAL CH340 (COM12)",
      "hwid": "USB VID:PID=1A86:7523",
      "manufacturer": "wch.cn",
      "suggested_role": "nano",
      "is_active_nano": true,
      "is_active_esp32": false,
      "is_open": false
    },
    {
      "device": "COM13",
      "description": "Silicon Labs CP210x USB to UART Bridge (COM13)",
      "hwid": "USB VID:PID=10C4:EA60",
      "manufacturer": "Silicon Labs",
      "suggested_role": "esp32",
      "is_active_nano": false,
      "is_active_esp32": true,
      "is_open": false
    }
  ],
  "active_nano_port": "COM12",
  "active_esp32_port": "COM13",
  "nano_connected": false,
  "esp32_connected": false
}
```

#### `POST /api/hardware/ports`
Assign custom or detected serial COM ports to the Arduino Nano receiver and ESP32 transmitter, persist configuration, and trigger background reconnection.
- **Request Body (JSON):**
```json
{
  "nano_port": "COM12",
  "esp32_port": "COM13"
}
```
- **Response (200 OK):**
```json
{
  "status": "SUCCESS",
  "nano_port": "COM12",
  "esp32_port": "COM13",
  "nano_connected": false,
  "esp32_connected": false
}
```

---

### 2.7 Simulation Controls
#### `POST /api/simulation/step`
Execute a single simulated observation step through the pipeline.
- **Request Body (JSON):**
```json
{
  "injected_type": "extreme_temp"
}
```
- **Response (200 OK):**
```json
{
  "status": "SUCCESS",
  "timestamp": "2026-11-19T07:25:30.123456+00:00",
  "temperature": 42.5,
  "ph": 7.2,
  "tds": 250.0,
  "is_anomaly": true,
  "classification": "SAFETY VIOLATION (CRITICAL_THRESHOLD_ALERT): Temperature (42.50°C) exceeds safety limit (38.0°C)",
  "primary_score": 0.8500
}
```

---

## 3. WebSocket Real-Time Specification (`/ws/live`)

### 3.1 Client & Server Heartbeat
Clients send periodic ping frames:
```json
{ "type": "ping", "timestamp": 1732000000000 }
```
Server responds with pong:
```json
{ "type": "pong", "timestamp": "2026-11-19T07:25:00.000000+00:00" }
```

### 3.2 Broadcast Event Types
1. **`new_reading`**: Pushed whenever a sensor reading is ingested.
```json
{
  "event": "new_reading",
  "data": {
    "temperature": 24.50,
    "ph": 7.20,
    "tds": 250.0,
    "data_source": "physical_serial",
    "is_anomaly": false,
    "classification": "NORMAL",
    "primary_score": 0.04
  },
  "timestamp": "2026-11-19T07:25:00.000000+00:00"
}
```
2. **`anomaly_detected`**: Pushed when any stage detects an anomaly.
```json
{
  "event": "anomaly_detected",
  "data": {
    "severity": "CRITICAL",
    "classification": "CRITICAL_THRESHOLD_ALERT",
    "temperature": 42.5,
    "score": 0.95
  },
  "timestamp": "2026-11-19T07:25:00.000000+00:00"
}
```
3. **`sampling_interval_status`**: Broadcast when sampling interval state updates.
4. **`configuration_updated`**: Broadcast when threshold or wireless profile changes.
5. **`system_status`**: Periodic diagnostics broadcast.
