# Architecture Specification: Adaptive IoT Water Quality Monitoring & Anomaly Detection

## 1. System Topology Overview

The platform is designed as an end-to-end, decoupled IoT monitoring architecture combining low-power edge telemetry, 2.4GHz RF wireless communication, streaming online machine learning, persistent SQLite storage, an asynchronous FastAPI backend, and a modern Next.js 16 (React 19) web dashboard.

```
+---------------------------------------------------------------------------------------------------------+
|                                           PHYSICAL EDGE SENSORS                                         |
|                                                                                                         |
|   +-----------------------+                         +-----------------------+                           |
|   | Dallas DS18B20 1-Wire |                         | Handheld Probes / Lab |                           |
|   | (Temp Sensor, GPIO15) |                         | (Manual pH & TDS)     |                           |
|   +-----------+-----------+                         +-----------+-----------+                           |
|               |                                                 |                                       |
|               v                                                 |                                       |
|   +-----------------------+                                     |                                       |
|   | ESP32 Transmitter     |                                     |                                       |
|   | - Non-blocking millis |                                     |                                       |
|   | - Dynamic Interval NVS|                                     |                                       |
|   +-----------+-----------+                                     |                                       |
|               |                                                 |                                       |
|   (2.4GHz nRF24L01 RF)                                          |                                       |
|   (Address: 00001, Ch 108)                                      |                                       |
|               |                                                 |                                       |
|               v                                                 |                                       |
|   +-----------------------+                                     |                                       |
|   | Arduino Nano Receiver |                                     |                                       |
|   | - SPI + CE:9, CSN:10  |                                     |                                       |
|   +-----------+-----------+                                     |                                       |
+---------------|-------------------------------------------------|---------------------------------------+
                | USB Serial (115200 baud)                        | REST API (POST /api/readings/manual)
                v                                                 v
+---------------------------------------------------------------------------------------------------------+
|                                         PYTHON BACKEND CORE & ML                                        |
|                                                                                                         |
|   +------------------------------------+          +------------------------------------+                |
|   | Serial Reader / Simulation Source  |          | Manual Reading Ingestion Handler   |                |
|   +-----------------+------------------+          +-----------------+------------------+                |
|                     |                                               |                                   |
|                     +-----------------------+-----------------------+                                   |
|                                             |                                                           |
|                                             v                                                           |
|                       +-------------------------------------------+                                     |
|                       | Timestamp Synchronizer & Freshness Engine |                                     |
|                       | - Assembles (Temp, pH, TDS) Tuple         |                                     |
|                       | - Enforces Skew Tolerance & Max Staleness |                                     |
|                       +---------------------+---------------------+                                     |
|                                             |                                                           |
|                                             v                                                           |
|         +-----------------------------------------------------------------------+                       |
|         |          5-STAGE MULTI-STAGE ONLINE ANOMALY DETECTION PIPELINE        |                       |
|         |                                                                       |                       |
|         |  [Stage 1] User-Defined Operating Thresholds (Reading 1 immediate)    |                       |
|         |  [Stage 2] Temporal Rate of Change Detection (Δv/Δt from Reading 2)   |                       |
|         |  [Stage 3] Statistical Baseline Collection (30 normal samples)        |                       |
|         |  [Stage 4] Rolling Median + MAD Robust Online Z-Score                 |                       |
|         |  [Stage 5] River Half-Space Trees (3D + Pairwise) with QuantileFilter |                       |
|         +-----------------------------------+-----------------------------------+                       |
|                                             |                                                           |
|                     +-----------------------+-----------------------+                                   |
|                     |                                               |                                   |
|                     v                                               v                                   |
|   +------------------------------------+          +------------------------------------+                |
|   | SQLite Persistent Database         |          | WebSocket Sync Bridge              |                |
|   | - WAL mode enabled                 |          | - Connection Pool                  |                |
|   | - Time-series, anomalies, audit    |          | - Heartbeat Ping/Pong              |                |
|   +------------------------------------+          +-----------------+------------------+                |
+---------------------------------------------------------------------|-----------------------------------+
                                                                      | WebSocket (ws://localhost:8000/ws/live)
                                                                      | & REST API (http://localhost:8000)
                                                                      v
+---------------------------------------------------------------------------------------------------------+
|                                    NEXT.JS 16 REACT DASHBOARD (FRONTEND)                                |
|                                                                                                         |
|   - Real-Time Parameter Telemetry Charts (Safety Threshold Bands)                                       |
|   - Interactive Plotly 3D State-Space Scatter Plot (X=Temp, Y=pH, Z=TDS)                                |
|   - ESP32 Dynamic Sampling Interval Selector (5s, 10s, 30s, 60s, 300s, Custom)                          |
|   - nRF24L01 RF Transmission Profile Controller (SHORT, BALANCED, LONG)                                 |
|   - Operating Safety Threshold Editor with Audit Trail Versions                                         |
|   - Manual pH & TDS Acquisition Form with Immediate Ingestion Feedback                                  |
|   - Simulation Laboratory (Scenarios 1–12 & Gradual Environmental Drift)                                |
+---------------------------------------------------------------------------------------------------------+
```

---

## 2. Decoupled Architecture

The architecture separates embedded sensing, stream processing, persistent storage, API serving, and user interaction into distinct layers:

### 2.1 Edge Sensing & Radio Layer
- **Transmitter (ESP32):** Reads water temperature from a Dallas DS18B20 1-Wire sensor on GPIO15. Operates on a non-blocking `millis()` timer driven by `samplingIntervalSec`. Dynamically reconfigurable via USB serial commands without reflashing. Persists settings across reboots in non-volatile flash storage using `<Preferences.h>`.
- **Radio (nRF24L01+):** 2.4GHz ISM band RF transceiver. Operates on Channel 108 with address `"00001"`. Supports 3 runtime profiles:
  - `SHORT`: 2 Mbps, low power (`RF24_PA_LOW`)
  - `BALANCED`: 1 Mbps, high power (`RF24_PA_HIGH`)
  - `LONG`: 250 kbps, maximum power (`RF24_PA_MAX`)
- **Receiver (Arduino Nano):** Dedicated hardware SPI interface (`D11` MOSI, `D12` MISO, `D13` SCK) with `D9` (CE) and `D10` (CSN). Listens continuously for 32-byte radio packets, verifies CRC, and streams valid readings over USB Serial at 115200 baud formatted as JSON: `{"temperature": 24.50, "device": "esp32", "seq": 102}`.

### 2.2 Data Ingestion & Synchronization Layer
- **Timestamp Synchronizer (`core/processing/synchronization.py`):** Sensor readings arrive asynchronously (temperature streams continuously via RF; pH and TDS are submitted manually or synthetically). The synchronizer pairs readings using freshness thresholds:
  - Default maximum age: 300 seconds (configurable).
  - Skew tolerance: 60 seconds between parameters.
  - Returns a `SynchronizedObservation` containing individual values, freshness booleans, and pairwise/3-variable synchronization status flags.

### 2.3 5-Stage Multi-Stage Online Anomaly Detection Pipeline
- **Stage 1: User-Defined Operating Thresholds:**
  - Evaluated immediately starting from the very first observation ($N \ge 1$).
  - Evaluates user-configured upper and lower safety boundaries for Temperature, pH, and TDS.
  - Breaches trigger `CRITICAL_THRESHOLD_ALERT` with `CRITICAL` severity and reject the observation from machine learning baseline updates.
- **Stage 2: Temporal Rate of Change Monitoring:**
  - Evaluated from the second observation onward ($N \ge 2$).
  - Calculates time derivative: $\Delta v / \Delta t$ per second for all active parameters.
  - Protects against rapid physical spikes (e.g. thermal shock, chemical dumping) before absolute bounds are breached. Triggers `RATE_OF_CHANGE_WARNING`.
- **Stage 3: Statistical Baseline Collection:**
  - Requires 30 valid non-anomalous samples per parameter.
  - Computes running medians and standard deviations to establish environmental baseline.
- **Stage 4: Rolling Median + MAD Robust Online Z-Score:**
  - Uses Median Absolute Deviation: $\text{MAD} = \text{median}(|x_i - \tilde{x}|)$.
  - Calculates robust Z-score: $Z_{\text{robust}} = \frac{0.6745 \cdot (x - \tilde{x})}{\text{MAD}}$.
  - Detects single-variable outliers without being skewed by extreme contaminated values.
- **Stage 5: River Half-Space Trees (Multivariate 3D + Pairwise):**
  - Continuous streaming online anomaly detector (`river.anomaly.HalfSpaceTrees`).
  - Warmup period: 40 synchronized observations.
  - 3D model monitors $(X=\text{Temp}, Y=\text{pH}, Z=\text{TDS})$.
  - 3 pairwise models monitor $(X=\text{Temp}, Y=\text{pH})$, $(X=\text{Temp}, Y=\text{TDS})$, and $(X=\text{pH}, Y=\text{TDS})$.
  - QuantileFilter dynamic scoring threshold adapts to ambient water fluctuations.
  - Model learning rejection: When an anomaly is detected, the model skips updating its tree counters, preventing contaminated observations from polluting normal state definition.
  - Drift monitoring: ADWIN detects seasonal environmental shifts.

### 2.4 Persistent Database Layer (`core/database/`)
- SQLite database configured in Write-Ahead Logging (`WAL`) mode for high-concurrency read/write operations without table locking.
- Tables:
  - `sensor_readings`: Raw parameter inputs with timestamps and sources.
  - `anomaly_events`: Ingestion audit log with severity, classification, score, adaptive threshold, and model state.
  - `threshold_configurations`: Versioned physical safety boundary configurations.
  - `sampling_interval_configurations`: Audit log tracking dynamic interval commands (`cmd_id`, status, applied interval, ACK).
  - `model_checkpoints`: Atomic metadata records tracking pickled model state checkpoints.

### 2.5 FastAPI REST & WebSocket Backend (`api/`)
- High-performance asynchronous backend running on port 8000.
- Exposes complete REST interface for system status, time-series telemetry, manual input, 3D state space coordinates, threshold updates, dynamic interval commands, and simulation control.
- WebSocket `/ws/live` connection pooling with heartbeat ping/pong and broadcast bridge for real-time telemetry streaming to frontend clients.

### 2.6 Next.js 16 React Dashboard (`frontend/`)
- Next.js App Router, React 19, TypeScript, Tailwind CSS.
- Real-time WebSocket connection to `ws://localhost:8000/ws/live` with automatic backoff reconnection.
- Interactive Plotly 3D scatter chart displaying the multivariate state space ($X=\text{Temp}, Y=\text{pH}, Z=\text{TDS}$) with normal (blue) and anomaly (crimson diamond) markers.
- Parameter streaming charts with threshold boundary bands.
- Dynamic hardware sampling interval control and nRF24L01 RF profile switcher.
- Water domain safety threshold presets with configuration audit history.
- Scenario laboratory for testing Scenarios 1–12 and synthetic environmental drift.
