# Adaptive IoT-Based Multivariate Anomaly Detection & Monitoring Platform

An end-to-end industrial-grade adaptive water quality monitoring, streaming multivariate anomaly detection, and dynamic RF control platform. Integrates physical ESP32 sensor telemetry, Dallas DS18B20 1-Wire sensing, 2.4 GHz nRF24L01 wireless radio, manual pH and TDS laboratory inputs, real-time timestamp synchronization, streaming online machine learning with **River ML (Half-Space Trees, QuantileFilter, ADWIN)**, SQLite persistence (WAL mode), a **FastAPI REST + WebSocket** backend, and a modern **Next.js 16 (React 19)** web dashboard.

---

## 1. Documentation Index

- **[System Architecture](docs/ARCHITECTURE.md):** Complete architectural topology, edge layer, 5-stage anomaly pipeline, synchronizer, and database schema.
- **[API Contract](docs/API_CONTRACT.md):** Specification of all REST endpoints and WebSocket `/ws/live` events.
- **[Hardware Setup & Flashing Guide](docs/HARDWARE_SETUP.md):** Pinouts (DS18B20 to GPIO15, nRF24L01 SPI pins), power decoupling, and `arduino-cli` compile & upload commands.
- **[Implementation Report](docs/IMPLEMENTATION_REPORT.md):** Engineering record of all implementation phases, verification, and automated test results.

---

## 2. System Architecture & Capabilities

```
+---------------------------------------------------------------------------------+
|                                 EDGE HARDWARE                                   |
|                                                                                 |
|  [ Dallas DS18B20 ]                                                             |
|         │ (1-Wire GPIO15, 4.7kΩ pullup)                                         |
|         ▼                                                                       |
|  [ ESP32 Transmitter ] ──(SPI: CE=4, CSN=5)──► [ nRF24L01 Radio ]              |
|                                                        │                        |
|                                         2.4 GHz RF     │ (SHORT / BALANCED /    |
|                                                        ▼  LONG Profiles)        |
|  [ Arduino Nano Gateway ] ◄──(SPI: CE=9, CSN=10)── [ nRF24L01 Radio ]           |
|         │                                                                       |
|         ▼ (USB Serial / COM Port @ 115200 baud)                                 |
+---------┼-----------------------------------------------------------------------+
          │
          ▼
+---------------------------------------------------------------------------------+
|                                FASTAPI BACKEND                                  |
|                                                                                 |
|  • Serial Reader & Auto-Port Scanner (Detects ESP32 / Arduino Nano COM ports)   |
|  • Sensor Data Synchronizer & Freshness Validator                               |
|  • 5-Stage Online Anomaly Detection Pipeline:                                   |
|      1. Safety Threshold Boundaries (Immediate alert & quarantine)              |
|      2. Temporal Rate-of-Change Analysis (Δv/Δt surge warnings)                  |
|      3. Statistical Baseline Collector (Running medians)                        |
|      4. Rolling Median & Robust MAD Z-Score                                     |
|      5. River Online ML: Half-Space Trees 3D + QuantileFilter + ADWIN Drift     |
|  • Dynamic ESP32 Sampling Interval Manager (Flash persistence via NVS)          |
|  • Two-Phase Commit nRF24L01 Range/Power Profile Controller                     |
|  • SQLite Storage (WAL Mode, Indexed Telemetry & Anomaly Log)                   |
|  • WebSocket Broadcast Pool (/ws/live) & REST API                               |
+---------┼-----------------------------------------------------------------------+
          │
          ▼ (HTTP REST on :8000 & WebSocket /ws/live)
+---------------------------------------------------------------------------------+
|                              NEXT.JS 16 FRONTEND                                |
|                                                                                 |
|  • Real-Time Telemetry Dashboard (Live Temperature, pH, TDS, Anomaly Score)     |
|  • 3D Multivariate State-Space Visualizer (Interactive Plotly WebGL)            |
|  • Historical Anomaly Table & Log Explorer                                      |
|  • Hardware & Ports Management Panel (Scan, Assign & Verify Device Ports)       |
|  • ESP32 Dynamic Sampling Interval Dispatcher                                   |
|  • Wireless Transmission Range Selector (SHORT, BALANCED, LONG)                 |
|  • Operating Safety Thresholds Configuration & Lab Manual Data Ingestion        |
+---------------------------------------------------------------------------------+
```

---

## 3. Directory Structure

```
iot-project/
├── backend/                  # FastAPI REST & WebSocket server, River ML pipeline
│   ├── api/                  # FastAPI routers, endpoints, and WebSocket pool
│   │   ├── routes.py
│   │   └── server.py
│   ├── config/               # Pydantic configuration settings
│   │   └── settings.py
│   ├── core/                 # Core engine services
│   │   ├── acquisition/      # Serial reader, data parsers, and hardware scanning
│   │   ├── anomaly/          # River ML Half-Space Trees, ADWIN, MAD, thresholds
│   │   ├── database/         # SQLite database schema, connection pool & repositories
│   │   ├── processing/       # Normalization, synchronization, and range validators
│   │   ├── services/         # MonitoringService, WirelessConfigService, ModelManager
│   │   └── simulation/       # Synthetic hardware sensor telemetry generator
│   ├── data/                 # SQLite storage (iot_monitoring.db) & checkpoints
│   ├── tests/                # 36 automated pytest suites (100% pass)
│   ├── main.py               # Backend entrypoint (`python main.py`)
│   ├── pytest.ini            # Pytest configuration
│   └── requirements.txt      # Python dependencies (FastAPI, River, PySerial, etc.)
├── docs/                     # Detailed technical architecture & guides
│   ├── API_CONTRACT.md
│   ├── ARCHITECTURE.md
│   ├── HARDWARE_SETUP.md
│   └── IMPLEMENTATION_REPORT.md
├── firmware/                 # Microcontroller C++ firmware sketches
│   ├── esp32_temp_transmitter/
│   │   └── esp32_temp_transmitter.ino # ESP32 1-Wire & nRF24L01 transmitter
│   └── nano_temp_receiver/
│       └── nano_temp_receiver.ino     # Arduino Nano nRF24L01 to USB serial gateway
├── frontend/                 # Modern Next.js 16 web dashboard
│   ├── public/
│   ├── src/
│   │   ├── app/              # App router pages & root layouts
│   │   ├── components/       # Telemetry cards, 3D Plotly state space, settings
│   │   ├── lib/              # API clients, WebSocket hook, TypeScript types
│   │   └── ...
│   ├── package.json
│   ├── tsconfig.json
│   └── tailwind.config.ts
├── .gitignore
└── README.md
```

---

## 4. Quickstart Guide

### 4.1 Prerequisites
- **Python:** 3.12 or newer
- **Node.js:** 20.x or newer (with `npm 10+`)
- **Git**
- *(Optional for firmware upload)*: `arduino-cli` or Arduino IDE 2.x

---

### 4.2 Backend Setup & Execution

1. Navigate to the `backend/` directory:
   ```bash
   cd backend
   ```

2. Create and activate a virtual environment:
   ```bash
   # Windows (PowerShell)
   python -m venv venv
   .\venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv venv
   source venv/bin/activate
   ```

3. Install required Python packages:
   ```bash
   pip install -r requirements.txt
   ```

4. Launch the FastAPI server:
   ```bash
   python main.py
   # Or using uvicorn directly:
   uvicorn api.server:app --host 0.0.0.0 --port 8000 --reload
   ```

The backend starts at `http://localhost:8000`:
- **Interactive OpenAPI Documentation:** `http://localhost:8000/docs`
- **System Health Status:** `http://localhost:8000/api/status`
- **Hardware COM Ports:** `http://localhost:8000/api/hardware/ports`
- **Live WebSocket Stream:** `ws://localhost:8000/ws/live`

---

### 4.3 Frontend Setup & Execution

1. Open a new terminal and navigate to `frontend/`:
   ```bash
   cd frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the Next.js development server:
   ```bash
   npm run dev
   ```

4. Access the web dashboard at `http://localhost:3000`.

---

### 4.4 Running Automated Verification Tests

The backend includes a comprehensive 36-test suite covering data parsing, River ML online anomaly detection, MAD robust statistics, temporal rate of change, timestamp synchronization, and serial communication.

To run the test suite:
```bash
cd backend
pytest -v
```
*Expected Result: 36 passed, 0 failures.*

---

## 5. Hardware Wiring & Firmware Flashing

> **Notice:** Physical hardware testing is marked as **PENDING** until the boards are physically plugged into USB. The firmware has been pre-compiled and verified.

### 5.1 ESP32 Transmitter Wiring
- **Dallas DS18B20 Temperature Sensor:**
  - `VCC` (Red Wire) &rarr; `3V3`
  - `GND` (Black Wire) &rarr; `GND`
  - `DATA` (Yellow Wire) &rarr; `GPIO15` (Requires a **4.7kΩ pull-up resistor** between `DATA` and `3V3`)
- **nRF24L01+ Transceiver:**
  - `VCC` &rarr; `3V3` (**Never connect to 5V**)
  - `GND` &rarr; `GND`
  - `CE` &rarr; `GPIO4`
  - `CSN` &rarr; `GPIO5`
  - `SCK` &rarr; `GPIO18`
  - `MOSI` &rarr; `GPIO23`
  - `MISO` &rarr; `GPIO19`
  - *Recommendation:* Place a 10µF to 100µF electrolytic capacitor across `VCC` and `GND`.

### 5.2 Arduino Nano Receiver Wiring
- **nRF24L01+ Transceiver:**
  - `VCC` &rarr; `3V3`
  - `GND` &rarr; `GND`
  - `CE` &rarr; `D9`
  - `CSN` &rarr; `D10`
  - `MOSI` &rarr; `D11`
  - `MISO` &rarr; `D12`
  - `SCK` &rarr; `D13`
  - *Recommendation:* Place a 10µF to 47µF capacitor across `VCC` and `GND`.

### 5.3 Firmware Compilation & Flashing Commands

1. **Verify Connected Ports:**
   ```bash
   arduino-cli board list
   ```

2. **Upload ESP32 Transmitter Firmware:**
   ```bash
   arduino-cli compile --fqbn esp32:esp32:esp32 firmware/esp32_temp_transmitter
   arduino-cli upload -p <ESP32_PORT> --fqbn esp32:esp32:esp32 firmware/esp32_temp_transmitter
   ```

3. **Upload Arduino Nano Receiver Firmware:**
   ```bash
   arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328 firmware/nano_temp_receiver
   arduino-cli upload -p <NANO_PORT> --fqbn arduino:avr:nano:cpu=atmega328 firmware/nano_temp_receiver
   ```
   *(For clone boards with the old bootloader, use `--fqbn arduino:avr:nano:cpu=atmega328old`)*.

---

## 6. Frontend Features & Usage

1. **Live Overview:**
   - Real-time telemetry cards for Temperature (°C), pH, TDS (ppm), and River ML Anomaly Score.
   - Status indicators showing sensor freshness and live anomaly classifications (`NORMAL`, `RATE_OF_CHANGE_WARNING`, `CRITICAL_THRESHOLD_ALERT`, `ANOMALOUS`).
2. **Interactive 3D State Space:**
   - 3D scatter plot powered by Plotly WebGL.
   - Normal points rendered in steel blue, anomalies highlighted in crimson diamonds.
   - Camera quick-buttons (Isometric, Top T-pH, Front T-TDS).
3. **Manual Lab Data Ingestion:**
   - Instant input form for pH (0–14) and TDS (0–5000 ppm) measurements with timestamp association.
4. **Hardware & Ports Configuration:**
   - Click **Scan Ports** to auto-detect attached USB serial devices (ESP32 / Arduino Nano).
   - Assign ports dynamically without restarting services.
5. **Dynamic ESP32 Sampling Rate Control:**
   - Adjust sampling frequency (2s to 3600s) from the web UI. Dispatches serial commands and stores the new rate into the ESP32's non-volatile NVS flash memory.
6. **Wireless Transmission Range:**
   - Switch between **SHORT** (2 Mbps, LOW power), **BALANCED** (1 Mbps, HIGH power), and **LONG** (250 kbps, MAX power) profiles using a two-phase commit protocol.

---
