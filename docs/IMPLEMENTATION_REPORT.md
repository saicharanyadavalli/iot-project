# Master Engineering Implementation Report

**Project:** Adaptive IoT-Based Multivariate Anomaly Detection, Real-Time Monitoring Dashboard, ESP32 Configuration Control, and Next.js Frontend Migration  
**Date:** November 19, 2026  
**Status:** Software, Firmware Compilation, Backend API, and Next.js Frontend Complete; Physical Hardware Flashing Marked as **PENDING**

---

## 1. Executive Summary

This engineering effort successfully refactored, extended, tested, and modernized the existing IoT water quality monitoring repository. Key outcomes achieved:

1. **Clean Decoupled Architecture:** Replaced the legacy monolithic Streamlit frontend with a high-performance decoupled architecture:
   - **Backend:** FastAPI REST & WebSocket server (`api/server.py`) running on port 8000 with asynchronous WebSocket connection pooling and heartbeat ping/pong.
   - **Frontend:** Modern Next.js 16 (App Router, React 19, TypeScript, Tailwind CSS) web application (`frontend/`) communicating over REST and WebSocket (`ws://localhost:8000/ws/live`).
2. **5-Stage Multi-Stage Online Anomaly Detection Pipeline:**
   - **Stage 1 (Reading 1):** User-Defined Operating Safety Thresholds with strict physical bounds; raises `CRITICAL_THRESHOLD_ALERT` and rejects observation from learning.
   - **Stage 2 (Reading 2+):** Temporal Rate of Change ($\Delta v / \Delta t$ per sec) for thermal shock and chemical surges; raises `RATE_OF_CHANGE_WARNING`.
   - **Stage 3 (Reading 30+):** Statistical Baseline Collection (running medians).
   - **Stage 4:** Rolling Median + MAD robust online Z-score.
   - **Stage 5 (Reading 40+):** River Half-Space Trees 3D + pairwise space partitioning with QuantileFilter adaptive scoring and ADWIN drift protection.
3. **Interactive 3D Multivariate State-Space Visualization:**
   - Client-side Plotly 3D scatter plot ($X=\text{Temperature}, Y=\text{pH}, Z=\text{TDS}$).
   - Normal observations rendered as blue circles (`#2563eb`), anomalies rendered as crimson diamonds (`#dc2626`), and latest reading highlighted with crosshairs.
   - Interactive orbit, pan, zoom, camera presets (Isometric, Top T-pH, Front T-TDS), point limit filter, and anomaly-only mode.
4. **ESP32 Dynamic Sampling Interval Firmware:**
   - Non-blocking `millis()` sampling scheduler (2s to 3600s, default 5s).
   - Flash non-volatile storage persistence using `<Preferences.h>` (`namespace: "sensor_cfg"`).
   - Dynamic JSON command parsing over USB serial with correlation IDs (`cmd_id`).
   - Verified compilation with `arduino-cli`: **0 errors, exit status 0**.
5. **nRF24L01 RF Transmission Profile Management:**
   - Coordinated Two-Phase Commit protocol between ESP32 and Arduino Nano across `SHORT`, `BALANCED`, and `LONG` profiles on 2.4GHz ISM RF Channel 108.
6. **Comprehensive Automated Test Suite:**
   - **35 tests passing** (100% pass rate) across unit, integration, pipeline, REST API, and wireless configuration tests.
7. **Safe Repository Cleanup:**
   - Removed 18 obsolete chat/test scripts and 4 dead folders with zero functional regressions.

---

## 2. Phase-by-Phase Implementation Detail

### Phase 1 & 2: Repository Inspection & Safe Cleanup
- Identified core modules (`core/anomaly`, `core/acquisition`, `core/database`, `core/processing`, `core/services`, `core/simulation`).
- Preserved existing SQLite database (`data/iot_monitoring.db`) with 81 historical observations and WAL mode.
- Safely removed legacy test/chat scripts (`blink_led.py`, `chat_app.py`, `chat_bridge.py`, `Start_Chat.bat`, `esp32_chat_package.zip`, `inbox.txt`, `test_chat_exchange.py`, `read_nano.py`, `read_nano_simple.py`, `read_serial.py`, `stream_test.py`, `test_ch340.py`, `test_com12.py`, `listen_loop.py`, `listen_nano.py`, `monitor_exchange.py`, `create_package.py`, `test_led.py`) and obsolete directories (`esp32_chat/`, `nano_chat/`, `esp32_spi_probe/`, `miso_monitor/`).
- Verified baseline tests passed (25 passing).

### Phase 3 & 4: Firmware Engineering & Dynamic Sampling Interval
- Modified `esp32_temp_transmitter/esp32_temp_transmitter.ino`:
  - Implemented dynamic `samplingIntervalSec` variable initialized from NVS.
  - Implemented non-blocking `millis()` scheduling loop without deep/light sleep.
  - Implemented serial command listener expecting `{"type":"config_interval","interval_seconds":N,"cmd_id":"..."}`.
  - Implemented JSON ACK responses: `{"type":"config_interval_ack","status":"APPLIED","interval_seconds":N,"cmd_id":"..."}`.
  - Verified compilation using `arduino-cli compile --fqbn esp32:esp32:esp32`:
    `Sketch uses 312,373 bytes (23%). Global variables use 22,968 bytes (7%). Exit code 0.`
- Verified Nano receiver firmware compilation using `arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328`:
  `Sketch uses 17,146 bytes (55%). Global variables use 1,008 bytes (49%). Exit code 0.`

### Phase 5 & 6: Multi-Stage Online Anomaly Detection & Safety Thresholds
- Created `core/anomaly/rate_of_change.py`:
  - Calculates temporal derivatives: $\Delta v / \Delta t$ per second for Temp, pH, and TDS.
  - Detects rapid fluctuations starting from the 2nd valid observation onward.
- Enhanced `core/anomaly/online_detector.py`:
  - Added Stage 1 user-defined threshold checking (`CRITICAL_THRESHOLD_ALERT`).
  - Added Stage 2 rate of change detector integration (`RATE_OF_CHANGE_WARNING`).
  - Added `get_stage_readiness()` returning comprehensive status for all 5 stages.
  - Added `installation_id` support for environment-specific profiles.
  - Added `__setstate__` backwards-compatibility to deserialize legacy pickle files without attribute errors.
- Enhanced SQLite database (`core/database/database.py`, `core/database/repository.py`):
  - Created table `threshold_configurations` with auto-incrementing versions and notes for full audit tracking.
  - Created table `sampling_interval_configurations` tracking command lifecycle (`PENDING`, `APPLIED`, `DEVICE_OFFLINE`, `FAILED`).
- Enhanced `core/services/wireless_config_service.py` & `core/services/monitoring_service.py`:
  - Added `apply_sampling_interval()` with correlation IDs and offline/mock handling.
  - Added `update_thresholds()` with strict lower < upper validation and audit persistence.

### Phase 7 & 8: Plotly 3D Multivariate Visualization & UI/UX
- Designed client-side 3D scatter chart displaying the 3D space $(X=\text{Temperature}, Y=\text{pH}, Z=\text{TDS})$.
- Color-coded normal points in blue (`#2563eb`), anomalies in crimson diamonds (`#dc2626`), and latest live ingestion with golden crosshairs.
- Added camera view presets (Isometric, Top T-pH, Front T-TDS), point limits (100, 250, 500, 1000), and anomalies-only toggle.

### Phase 9 & 10: FastAPI Backend & Next.js 16 Migration
- Implemented FastAPI backend (`api/server.py`, `api/schemas.py`, `api/websocket_manager.py`):
  - REST endpoints for system status, time-series, manual ingestion, thresholds, interval control, RF profiles, 3D coordinates, and simulation.
  - WebSocket `/ws/live` connection pooling with heartbeat ping/pong.
- Scaffolded Next.js 16 (App Router, React 19, Tailwind CSS 4) in `frontend/`:
  - Types: `frontend/src/types/api.ts`
  - REST client: `frontend/src/lib/api.ts`
  - WebSocket hook: `frontend/src/lib/useWebSocket.ts`
  - Components: `Navbar`, `Sidebar`, `OverviewTab`, `LiveMonitoringTab`, `Multivariate3DTab`, `AnomalyTab`, `ManualInputTab`, `ThresholdTab`, `HardwareTab`, `SimulationTab`.
  - Verified production build: `npm run build` completed with **exit status 0**.

### Phase 11 & 12: Automated Test Suite
- Created `tests/test_api_and_pipeline.py` with 10 comprehensive tests covering:
  - `GET /api/status`
  - `GET /api/readings/latest`
  - `POST /api/readings/manual`
  - `GET /api/config/thresholds` and `PUT /api/config/thresholds` (version increment audit)
  - `POST /api/config/interval` (command lifecycle & offline handling)
  - `GET /api/multivariate/3d` (3D points coordinate structure)
  - `POST /api/simulation/step` (single step execution)
  - Stage 1 immediate threshold breach (`CRITICAL_THRESHOLD_ALERT` on Reading 1)
  - Stage 2 rate of change detection (`RATE_OF_CHANGE_WARNING` on Reading 2)
  - 5-stage readiness reporting
- Total test results: **35 passed in 5.50s**.

---

## 3. Test Results Summary

```
============================= test session starts =============================
platform win32 -- Python 3.12.10, pytest-9.1.0, pluggy-1.6.0
rootdir: C:\Users\yadav\Desktop\iot project
configfile: pytest.ini
collected 35 items

tests\test_anomaly_detection.py .........                                [ 25%]
tests\test_api_and_pipeline.py ..........                                [ 54%]
tests\test_data_parser.py ...                                            [ 62%]
tests\test_drift_and_persistence.py ..                                   [ 68%]
tests\test_serial_and_simulation.py ...                                  [ 77%]
tests\test_synchronization_and_validation.py ....                        [ 88%]
tests\test_wireless_config.py ....                                       [100%]

======================= 35 passed, 5 warnings in 5.50s ========================
```

---

## 4. Hardware Status & Next Actions

- **Physical Hardware Status:** Marked as **PENDING**. The physical ESP32 and Arduino Nano boards were not connected to USB during this development session.
- **Verification Performed:**
  - Both sketches compile cleanly with `arduino-cli` (0 errors).
  - Serial command protocols and mock channels tested and verified in Python test suite.
  - Complete wiring tables, decoupling capacitor guidelines, and upload commands provided in `HARDWARE_SETUP.md`.
