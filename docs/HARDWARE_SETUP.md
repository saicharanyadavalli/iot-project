# Hardware Setup & Deployment Guide

> **IMPORTANT NOTICE:**
> Physical hardware testing and firmware flashing are currently marked as **PENDING**.
> The ESP32 and Arduino Nano boards were disconnected from the host system during this development phase.
> All firmware sketches have been fully written, updated with dynamic interval control and NVS flash persistence, and **successfully compiled with 0 errors**.
> Follow the instructions below to flash the boards once they are connected to USB.

---

## 1. Physical Hardware Wiring Specification

### 1.1 ESP32 Transmitter + Dallas DS18B20 Temperature Sensor
| DS18B20 Wire / Pin | ESP32 GPIO / Pin | Notes |
| :--- | :--- | :--- |
| **VCC** (Red Wire) | `3V3` | 3.3V Power Supply |
| **GND** (Black Wire) | `GND` | Common Ground Reference |
| **DATA** (Yellow Wire) | `GPIO15` (or `D15`) | Digital 1-Wire Data Line |
| **Pull-up Resistor** | Between `DATA` and `3V3` | **4.7kΩ Resistor Required** for stable 1-Wire bus signals |

### 1.2 ESP32 Transmitter + nRF24L01+ Transceiver Module
| nRF24L01 Pin | ESP32 GPIO / Pin | Function |
| :--- | :--- | :--- |
| **VCC** (Pin 2) | `3V3` | **DO NOT connect to 5V** (nRF24L01 is 3.3V only) |
| **GND** (Pin 1) | `GND` | Ground Reference |
| **CE** (Pin 3) | `GPIO4` | Chip Enable (Transmit / Receive Mode) |
| **CSN** (Pin 4) | `GPIO5` | SPI Chip Select Not |
| **SCK** (Pin 5) | `GPIO18` | Hardware SPI Clock |
| **MOSI** (Pin 6) | `GPIO23` | Hardware SPI Master Out Slave In |
| **MISO** (Pin 7) | `GPIO19` | Hardware SPI Master In Slave Out |
| **Decoupling Capacitor** | Across `VCC` & `GND` | **10µF to 100µF capacitor directly across pins** |

---

### 1.3 Arduino Nano Receiver + nRF24L01+ Transceiver Module
| nRF24L01 Pin | Arduino Nano Pin | Function |
| :--- | :--- | :--- |
| **VCC** (Pin 2) | `3V3` | 3.3V Power (Use 3.3V adapter if Nano regulator is weak) |
| **GND** (Pin 1) | `GND` | Common Ground |
| **CE** (Pin 3) | `D9` | Chip Enable |
| **CSN** (Pin 4) | `D10` | SPI Chip Select Not |
| **MOSI** (Pin 6) | `D11` | Hardware SPI MOSI |
| **MISO** (Pin 7) | `D12` | Hardware SPI MISO |
| **SCK** (Pin 5) | `D13` | Hardware SPI Clock |
| **Decoupling Capacitor** | Across `VCC` & `GND` | **10µF to 47µF capacitor soldered directly across pins** |

---

## 2. Firmware Compilation Verification

Both sketches have been compiled using `arduino-cli`:

### 2.1 ESP32 Transmitter Firmware
- **Source:** `firmware/esp32_temp_transmitter/esp32_temp_transmitter.ino`
- **Features:**
  - Non-blocking `millis()` sampling scheduler
  - Dynamic sampling interval variable (`samplingIntervalSec`, 2s to 3600s, default 5s)
  - Persistent flash storage with `<Preferences.h>` (`sensor_cfg` namespace)
  - Bidirectional JSON command parser on USB serial
  - Non-blocking ACK replies with correlation IDs (`cmd_id`)
  - No ESP32 sleep modes (ensures continuous USB serial availability)
- **Compile Command:**
  ```powershell
  arduino-cli compile --fqbn esp32:esp32:esp32 firmware/esp32_temp_transmitter
  ```
- **Result:**
  ```
  Sketch uses 312,373 bytes (23%) of program storage space.
  Global variables use 22,968 bytes (7%) of dynamic memory.
  Exit status 0 (Compilation Success)
  ```

### 2.2 Arduino Nano Receiver Firmware
- **Source:** `firmware/nano_temp_receiver/nano_temp_receiver.ino`
- **Features:**
  - Continuous nRF24L01 packet listener
  - Packet unpacker and CRC verification
  - USB serial stream formatting: `{"temperature": 24.50, "device": "esp32", "seq": 102}`
- **Compile Command:**
  ```powershell
  arduino-cli compile --fqbn arduino:avr:nano:cpu=atmega328 firmware/nano_temp_receiver
  ```
- **Result:**
  ```
  Sketch uses 17,146 bytes (55%) of program storage space.
  Global variables use 1,008 bytes (49%) of dynamic memory.
  Exit status 0 (Compilation Success)
  ```

---

## 3. Firmware Flashing Commands (Run Once Hardware Connected)

When the ESP32 and Arduino Nano are connected to your laptop via USB:

1. **Identify the COM Ports:**
   ```powershell
   arduino-cli board list
   ```
   *Expected:*
   - ESP32: Typically `COM12` (or `COM13`)
   - Arduino Nano: Typically `COM13` (or `COM12`)

2. **Upload to ESP32:**
   ```powershell
   arduino-cli upload -p <ESP32_PORT> --fqbn esp32:esp32:esp32 firmware/esp32_temp_transmitter
   ```

3. **Upload to Arduino Nano:**
   ```powershell
   # If ATmega328P (Standard):
   arduino-cli upload -p <NANO_PORT> --fqbn arduino:avr:nano:cpu=atmega328 firmware/nano_temp_receiver

   # If Old Bootloader (CH340 Clones):
   arduino-cli upload -p <NANO_PORT> --fqbn arduino:avr:nano:cpu=atmega328old firmware/nano_temp_receiver
   ```

---

## 4. Hardware Verification Checklist (Pending Physical Connect)
- [ ] Connect ESP32 to USB port.
- [ ] Connect Arduino Nano to USB port.
- [ ] Confirm 4.7kΩ pull-up between DS18B20 Data (GPIO15) and 3.3V.
- [ ] Confirm electrolytic capacitor across nRF24L01 VCC/GND pins.
- [ ] Run `arduino-cli upload` for both boards.
- [ ] Open serial monitor at 115200 baud on Nano port and observe valid JSON packets.
- [ ] Dispatch dynamic sampling interval command (e.g. 10s) from Next.js dashboard and verify ACK response.
