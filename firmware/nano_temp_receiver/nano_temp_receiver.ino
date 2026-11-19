/**
 * Arduino Nano nRF24L01 Temperature Receiver
 * ============================================
 * Hardware:
 *   - nRF24L01: CE=9, CSN=10, SCK=13, MISO=12, MOSI=11 (hardware SPI)
 *
 * Roles:
 *   - Receives TempPacket wirelessly from ESP32 transmitter
 *   - Validates temperature (DS18B20 range: -55 to 125 C)
 *   - Forwards to laptop over USB Serial in format parseable by existing DataParser:
 *       [ESP32 RX] Received Packet #N: "Temp: 24.50 C"
 *   - Listens for JSON config commands from laptop on Serial
 *   - Applies matching PA level and data rate (must match ESP32!)
 *   - Responds with JSON ACK to config commands
 *
 * Serial command format (from Python backend):
 *   {"type":"config_prepare","profile":"BALANCED","pa_level":"HIGH","data_rate":"1MBPS","channel":108}
 *   {"type":"config_commit"}
 *   {"type":"config_abort"}
 *   {"type":"config_status"}
 *
 * Serial response format (to laptop):
 *   {"type":"config_ack","device":"NANO","status":"READY","profile":"BALANCED"}
 */

#include <SPI.h>
#include <RF24.h>
#include <nRF24L01.h>
#include <ArduinoJson.h>

// ---- Pin definitions ----
#define CE_PIN  9
#define CSN_PIN 10

// ---- Radio object ----
RF24 radio(CE_PIN, CSN_PIN);

// ---- RF pipe address (must match ESP32 transmitter) ----
const byte PIPE_ADDRESS[6] = "00001";

// ---- Packet structure (must match ESP32 transmitter exactly) ----
struct TempPacket {
  uint32_t counter;
  float    temperature;
  char     profile[12];
};

// ---- Profile enum ----
enum RadioProfile { SHORT_RANGE = 0, BALANCED = 1, LONG_RANGE = 2 };

// ---- Active configuration ----
struct RadioConfig {
  RadioProfile    profile    = BALANCED;
  rf24_pa_dbm_e   pa_level   = RF24_PA_MIN;   // Nano: use MIN to avoid brownout
  rf24_datarate_e data_rate  = RF24_1MBPS;
  uint8_t         channel    = 108;
  uint8_t         retry_delay = 3;
  uint8_t         retry_count = 5;
  bool            supports_250k = false;
};

RadioConfig activeConfig;
RadioConfig pendingConfig;
bool hasPending = false;

// ---- Helpers ----
const char* profileName(RadioProfile p) {
  switch (p) {
    case SHORT_RANGE: return "SHORT";
    case BALANCED:    return "BALANCED";
    case LONG_RANGE:  return "LONG";
    default:          return "BALANCED";
  }
}

const char* dataRateName(rf24_datarate_e dr) {
  switch (dr) {
    case RF24_250KBPS: return "250KBPS";
    case RF24_1MBPS:   return "1MBPS";
    case RF24_2MBPS:   return "2MBPS";
    default:           return "1MBPS";
  }
}

const char* paLevelName(rf24_pa_dbm_e pa) {
  switch (pa) {
    case RF24_PA_MIN:  return "MIN";
    case RF24_PA_LOW:  return "LOW";
    case RF24_PA_HIGH: return "HIGH";
    case RF24_PA_MAX:  return "MAX";
    default:           return "MIN";
  }
}

// NOTE: Nano uses RF24_PA_MIN regardless of profile to prevent brownout on 3.3V rail.
// The ESP32 uses the full requested PA level. This asymmetry is intentional and normal.
rf24_pa_dbm_e getNanoPAForProfile(RadioProfile p) {
  // Keep Nano at MIN always to protect the 3.3V LDO
  (void)p;
  return RF24_PA_MIN;
}

void applyConfig(const RadioConfig& cfg) {
  radio.stopListening();
  radio.setPALevel(cfg.pa_level);
  radio.setDataRate(cfg.data_rate);
  radio.setChannel(cfg.channel);
  radio.setRetries(cfg.retry_delay, cfg.retry_count);
  radio.openReadingPipe(1, PIPE_ADDRESS);
  radio.startListening();
}

bool parseProfile(const char* profileStr, RadioConfig& cfg) {
  String p = String(profileStr);
  p.toUpperCase();
  if (p == "SHORT") {
    cfg.profile    = SHORT_RANGE;
    cfg.pa_level   = getNanoPAForProfile(SHORT_RANGE);
    cfg.data_rate  = RF24_2MBPS;
    cfg.channel    = 108;
    cfg.retry_delay = 2;
    cfg.retry_count = 3;
    return true;
  }
  if (p == "BALANCED") {
    cfg.profile    = BALANCED;
    cfg.pa_level   = getNanoPAForProfile(BALANCED);
    cfg.data_rate  = RF24_1MBPS;
    cfg.channel    = 108;
    cfg.retry_delay = 3;
    cfg.retry_count = 5;
    return true;
  }
  if (p == "LONG") {
    cfg.profile    = LONG_RANGE;
    cfg.pa_level   = getNanoPAForProfile(LONG_RANGE);
    bool ok = radio.setDataRate(RF24_250KBPS);
    cfg.data_rate  = ok ? RF24_250KBPS : RF24_1MBPS;
    cfg.channel    = 108;
    cfg.retry_delay = 5;
    cfg.retry_count = 15;
    return true;
  }
  return false;
}

void sendAck(const char* status, const RadioConfig& cfg) {
  StaticJsonDocument<256> doc;
  doc["type"]      = "config_ack";
  doc["device"]    = "NANO";
  doc["status"]    = status;
  doc["profile"]   = profileName(cfg.profile);
  doc["pa_level"]  = paLevelName(cfg.pa_level);
  doc["data_rate"] = dataRateName(cfg.data_rate);
  doc["channel"]   = cfg.channel;
  serializeJson(doc, Serial);
  Serial.println();
}

void sendStatus(const RadioConfig& cfg) {
  StaticJsonDocument<256> doc;
  doc["type"]      = "config_status";
  doc["device"]    = "NANO";
  doc["profile"]   = profileName(cfg.profile);
  doc["pa_level"]  = paLevelName(cfg.pa_level);
  doc["data_rate"] = dataRateName(cfg.data_rate);
  doc["channel"]   = cfg.channel;
  doc["supports_250k"] = cfg.supports_250k;
  serializeJson(doc, Serial);
  Serial.println();
}

void handleSerialCommand(const String& line) {
  StaticJsonDocument<256> doc;
  DeserializationError err = deserializeJson(doc, line);
  if (err) return;

  const char* type = doc["type"] | "";

  if (strcmp(type, "config_prepare") == 0) {
    const char* profileStr = doc["profile"] | "BALANCED";
    RadioConfig candidate = activeConfig;
    if (parseProfile(profileStr, candidate)) {
      pendingConfig = candidate;
      hasPending = true;
      sendAck("READY", pendingConfig);
    } else {
      sendAck("ERROR", activeConfig);
    }

  } else if (strcmp(type, "config_commit") == 0) {
    if (hasPending) {
      activeConfig = pendingConfig;
      hasPending = false;
      applyConfig(activeConfig);
      sendAck("COMMITTED", activeConfig);
    } else {
      sendAck("NO_PENDING", activeConfig);
    }

  } else if (strcmp(type, "config_abort") == 0) {
    hasPending = false;
    sendAck("ABORTED", activeConfig);

  } else if (strcmp(type, "config_status") == 0) {
    sendStatus(activeConfig);
  }
}

// ---- Setup ----
void setup() {
  Serial.begin(115200);
  while (!Serial) delay(10);
  pinMode(LED_BUILTIN, OUTPUT);

  Serial.println(F("\n=========================================="));
  Serial.println(F("   Arduino Nano NRF24L01 Receiver        "));
  Serial.println(F("=========================================="));

  if (!radio.begin()) {
    Serial.println(F("ERROR: radio.begin() failed! Check SPI wiring (CE=9, CSN=10)."));
    while (1) delay(100);
  }

  // Check 250kbps support
  activeConfig.supports_250k = radio.setDataRate(RF24_250KBPS);

  // Apply default BALANCED profile
  activeConfig.profile    = BALANCED;
  activeConfig.pa_level   = RF24_PA_MIN;   // Always MIN on Nano
  activeConfig.data_rate  = RF24_1MBPS;
  activeConfig.channel    = 108;
  activeConfig.retry_delay = 3;
  activeConfig.retry_count = 5;

  applyConfig(activeConfig);

  Serial.print(F("Radio initialized. 250kbps support: "));
  Serial.println(activeConfig.supports_250k ? F("YES") : F("NO"));
  Serial.println(F("Active profile: BALANCED (1Mbps, PA_MIN, CH108)"));
  Serial.println(F("Listening for wireless packets from ESP32...\n"));
}

// ---- Main loop ----
String serialBuf = "";

void loop() {
  // --- Process incoming serial config commands from laptop ---
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (serialBuf.length() > 0) {
        handleSerialCommand(serialBuf);
        serialBuf = "";
      }
    } else {
      serialBuf += c;
      if (serialBuf.length() > 512) serialBuf = "";
    }
  }

  // --- Check for wireless packet from ESP32 ---
  if (radio.available()) {
    TempPacket pkt;
    radio.read(&pkt, sizeof(pkt));

    // Flash LED on receive
    digitalWrite(LED_BUILTIN, HIGH);

    float temp = pkt.temperature;

    // Validate temperature range (DS18B20 physical range: -55 to 125 C)
    if (temp < -55.0 || temp > 125.0) {
      Serial.print(F("[NANO RX] #"));
      Serial.print(pkt.counter);
      Serial.print(F(" -> Invalid temperature: "));
      Serial.print(temp, 2);
      Serial.println(F(" C (out of DS18B20 range). Discarding."));
      digitalWrite(LED_BUILTIN, LOW);
      return;
    }

    // Forward to laptop in format expected by DataParser:
    // [ESP32 RX] Received Packet #N: "Temp: 24.50 C"
    Serial.print(F("[ESP32 RX] Received Packet #"));
    Serial.print(pkt.counter);
    Serial.print(F(": \"Temp: "));
    Serial.print(temp, 2);
    Serial.println(F(" C\""));

    delay(10);
    digitalWrite(LED_BUILTIN, LOW);
  }
}
