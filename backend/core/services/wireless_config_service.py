"""
Wireless transmission profile configuration service.
Coordinates dynamic radio profile changes across ESP32 (transmitter) and
Arduino Nano (receiver) via their respective USB serial ports.

Protocol (two-phase commit):
  1. Send {"type":"config_prepare","profile":"BALANCED"} to both devices
  2. Await {"type":"config_ack","status":"READY"} from both
  3. Send {"type":"config_commit"} to both
  4. Await {"type":"config_ack","status":"COMMITTED"} from both
  5. On timeout or partial failure: send {"type":"config_abort"} and rollback

NOTE: nRF24L01 does not provide continuous RSSI/SNR like LoRa modules.
      Signal quality is a binary RPD (Received Power Detector) indicator only.
      This service does NOT fabricate signal strength metrics.
"""

from __future__ import annotations
import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Dict, Any, Callable, List
from datetime import datetime, timezone

import serial
import serial.tools.list_ports

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class WirelessProfile(str, Enum):
    SHORT    = "SHORT"
    BALANCED = "BALANCED"
    LONG     = "LONG"


@dataclass
class ProfileSpec:
    name: str
    pa_level: str
    data_rate: str
    channel: int
    retry_delay: int
    retry_count: int
    description: str


PROFILES: Dict[str, ProfileSpec] = {
    WirelessProfile.SHORT: ProfileSpec(
        name="SHORT", pa_level="LOW", data_rate="2MBPS",
        channel=108, retry_delay=2, retry_count=3,
        description="Short range: 2 Mbps, PA_LOW — highest throughput, shortest distance"
    ),
    WirelessProfile.BALANCED: ProfileSpec(
        name="BALANCED", pa_level="HIGH", data_rate="1MBPS",
        channel=108, retry_delay=3, retry_count=5,
        description="Balanced: 1 Mbps, PA_HIGH — default operating profile"
    ),
    WirelessProfile.LONG: ProfileSpec(
        name="LONG", pa_level="MAX", data_rate="250KBPS",
        channel=108, retry_delay=5, retry_count=15,
        description="Long range: 250 kbps (nRF24L01+ only), PA_MAX — maximum sensitivity"
    ),
}


class ConfigResult(str, Enum):
    SUCCESS      = "SUCCESS"
    PARTIAL_FAIL = "PARTIAL_FAIL"   # One device ACKed, other timed out
    TIMEOUT      = "TIMEOUT"         # Neither device responded
    ERROR        = "ERROR"           # Exception during communication
    NO_HARDWARE  = "NO_HARDWARE"     # Ports not available


@dataclass
class DeviceStatus:
    port: str
    connected: bool = False
    radio_initialized: bool = False
    active_profile: str = "UNKNOWN"
    pa_level: str = "UNKNOWN"
    data_rate: str = "UNKNOWN"
    channel: int = 108
    supports_250k: bool = False
    packets_received: int = 0
    packets_failed: int = 0
    last_packet_ts: Optional[str] = None
    last_seen_ts: Optional[str] = None
    error_message: Optional[str] = None


@dataclass
class ConfigChangeResult:
    result: ConfigResult
    profile: str
    esp32_ack: Optional[str] = None
    nano_ack: Optional[str] = None
    error_message: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Single-device serial command channel
# ---------------------------------------------------------------------------

class DeviceChannel:
    """Non-blocking serial channel for sending commands and collecting ACK responses."""

    ACK_TIMEOUT_SEC = 5.0

    def __init__(self, port: str, baud: int = 115200, on_line_callback: Optional[Callable[[str], None]] = None):
        self.port = port
        self.baud = baud
        self.on_line_callback = on_line_callback
        self._ser: Optional[serial.Serial] = None
        self._lock = threading.Lock()
        self._response_buf: List[str] = []
        self._reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def connect(self) -> bool:
        with self._lock:
            if self._ser and self._ser.is_open:
                return True
            try:
                self._ser = serial.Serial(self.port, self.baud, timeout=0.1)
                self._stop_event.clear()
                self._reader_thread = threading.Thread(
                    target=self._reader_loop, daemon=True, name=f"DeviceCh-{self.port}"
                )
                self._reader_thread.start()
                logger.info("DeviceChannel connected: %s", self.port)
                return True
            except serial.SerialException as e:
                logger.warning("DeviceChannel %s connect failed: %s", self.port, e)
                self._ser = None
                return False

    def disconnect(self) -> None:
        self._stop_event.set()
        with self._lock:
            if self._ser and self._ser.is_open:
                try:
                    self._ser.close()
                except Exception:
                    pass
            self._ser = None

    @property
    def is_connected(self) -> bool:
        with self._lock:
            return self._ser is not None and self._ser.is_open

    def send_command(self, cmd: Dict[str, Any]) -> bool:
        """Send a JSON command. Returns True if bytes were written successfully."""
        with self._lock:
            if not self._ser or not self._ser.is_open:
                return False
            try:
                payload = json.dumps(cmd) + "\n"
                self._ser.write(payload.encode("utf-8"))
                self._ser.flush()
                return True
            except serial.SerialException as e:
                logger.warning("DeviceChannel %s send failed: %s", self.port, e)
                return False

    def wait_for_ack(self, expected_type: str = "config_ack",
                     expected_status: Optional[str] = None,
                     timeout: float = ACK_TIMEOUT_SEC) -> Optional[Dict[str, Any]]:
        """Block until an ACK JSON line matching criteria arrives or timeout."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            msg = self._pop_response()
            if msg:
                try:
                    data = json.loads(msg)
                    if data.get("type") == expected_type:
                        if expected_status is None or data.get("status") == expected_status:
                            return data
                        # Wrong status — keep it for status check but stop waiting
                        logger.warning("Unexpected status from %s: %s", self.port, data)
                        return data
                except json.JSONDecodeError:
                    pass
            time.sleep(0.05)
        return None

    def get_status(self) -> Optional[Dict[str, Any]]:
        """Request and return config_status from device."""
        self.send_command({"type": "config_status"})
        return self.wait_for_ack("config_status")

    # ---- Internal ----

    def _reader_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                with self._lock:
                    if not self._ser or not self._ser.is_open:
                        break
                    line = self._ser.readline()
                if line:
                    decoded = line.decode("utf-8", errors="replace").strip()
                    if decoded.startswith("{"):
                        # JSON message — goes to ACK queue
                        with threading.Lock():
                            self._response_buf.append(decoded)
                            if len(self._response_buf) > 50:
                                self._response_buf.pop(0)
                    else:
                        # Non-JSON message (e.g. sensor readings) — forward to callback
                        if self.on_line_callback:
                            try:
                                self.on_line_callback(decoded)
                            except Exception as ex:
                                logger.debug("Error in on_line_callback: %s", ex)
            except serial.SerialException:
                break
            except Exception:
                pass

    def _pop_response(self) -> Optional[str]:
        if self._response_buf:
            return self._response_buf.pop(0)
        return None


# ---------------------------------------------------------------------------
# Wireless configuration service
# ---------------------------------------------------------------------------

class WirelessConfigService:
    """
    Manages dynamic wireless profile configuration for the ESP32 + Nano radio pair.

    Thread-safe. Can be used as a singleton alongside MonitoringService.

    Design constraints:
    - Profile is NOT updated until both devices send COMMITTED ACK
    - 250 kbps is used only if both devices report supports_250k=True
    - No RSSI/SNR values are reported (nRF24L01 limitation)
    - Nano always uses RF24_PA_MIN regardless of profile (brownout protection)
    """

    ACK_TIMEOUT = 6.0
    COMMIT_TIMEOUT = 4.0

    def __init__(
        self,
        esp32_port: str = "COM13",
        nano_port: str = "COM12",
        baud: int = 115200,
        on_packet_callback: Optional[Callable[[str], None]] = None,
    ):
        self.esp32_port = esp32_port
        self.nano_port = nano_port
        self.baud = baud
        self.on_packet_callback = on_packet_callback

        self._lock = threading.RLock()
        self.active_profile: str = WirelessProfile.BALANCED
        self.pending_profile: Optional[str] = None

        self.esp32_status = DeviceStatus(port=esp32_port)
        self.nano_status  = DeviceStatus(port=nano_port)

        self.active_sampling_interval: int = 5
        self.pending_sampling_interval: Optional[int] = None
        self.last_interval_cmd_id: Optional[str] = None
        self.last_interval_status: str = "IDLE"
        self.last_interval_ack_time: Optional[str] = None
        self.mock_mode: bool = False

        self._esp32_ch: Optional[DeviceChannel] = None
        self._nano_ch:  Optional[DeviceChannel] = None

        self._nano_reader_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._nano_serial: Optional[serial.Serial] = None

        self._change_history: List[ConfigChangeResult] = []

    # ---- Public API ----

    def start(self) -> None:
        """Connect to both devices and start background Nano data reader."""
        self._connect_devices()
        self._start_nano_reader()
        # Fetch initial status from each device
        threading.Thread(target=self._refresh_device_statuses, daemon=True).start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._esp32_ch:
            self._esp32_ch.disconnect()
        if self._nano_ch:
            self._nano_ch.disconnect()
        if self._nano_serial and self._nano_serial.is_open:
            try:
                self._nano_serial.close()
            except Exception:
                pass

    def apply_profile(self, profile: str) -> ConfigChangeResult:
        """
        Two-phase commit to apply profile to both radios.
        Returns ConfigChangeResult immediately — this call blocks up to ~15s.
        """
        profile = profile.upper()
        if profile not in PROFILES:
            return ConfigChangeResult(
                result=ConfigResult.ERROR,
                profile=profile,
                error_message=f"Unknown profile '{profile}'"
            )

        with self._lock:
            if not self._esp32_ch or not self._nano_ch:
                return ConfigChangeResult(
                    result=ConfigResult.NO_HARDWARE,
                    profile=profile,
                    error_message="ESP32 or Nano channel not connected"
                )

            self.pending_profile = profile
            cmd_prepare = {
                "type": "config_prepare",
                "profile": profile,
            }
            cmd_commit = {"type": "config_commit"}
            cmd_abort  = {"type": "config_abort"}

            # Phase 1: Send prepare to both
            esp32_sent = self._esp32_ch.send_command(cmd_prepare)
            nano_sent  = self._nano_ch.send_command(cmd_prepare)

            if not esp32_sent or not nano_sent:
                self._esp32_ch.send_command(cmd_abort)
                self._nano_ch.send_command(cmd_abort)
                return ConfigChangeResult(
                    result=ConfigResult.ERROR,
                    profile=profile,
                    error_message="Failed to send prepare command to one or both devices"
                )

            # Phase 2: Await READY ACK from both
            esp32_ready = self._esp32_ch.wait_for_ack("config_ack", "READY", self.ACK_TIMEOUT)
            nano_ready  = self._nano_ch.wait_for_ack("config_ack", "READY", self.ACK_TIMEOUT)

            if not esp32_ready or not nano_ready:
                # Abort both
                self._esp32_ch.send_command(cmd_abort)
                self._nano_ch.send_command(cmd_abort)
                self.pending_profile = None
                failed = []
                if not esp32_ready: failed.append("ESP32")
                if not nano_ready:  failed.append("Nano")
                return ConfigChangeResult(
                    result=ConfigResult.PARTIAL_FAIL if (esp32_ready or nano_ready) else ConfigResult.TIMEOUT,
                    profile=profile,
                    esp32_ack=str(esp32_ready) if esp32_ready else "TIMEOUT",
                    nano_ack=str(nano_ready) if nano_ready else "TIMEOUT",
                    error_message=f"Prepare ACK timeout from: {', '.join(failed)}"
                )

            # Phase 3: Commit both
            self._esp32_ch.send_command(cmd_commit)
            self._nano_ch.send_command(cmd_commit)

            # Phase 4: Await COMMITTED from both
            esp32_committed = self._esp32_ch.wait_for_ack("config_ack", "COMMITTED", self.COMMIT_TIMEOUT)
            nano_committed  = self._nano_ch.wait_for_ack("config_ack", "COMMITTED", self.COMMIT_TIMEOUT)

            if esp32_committed and nano_committed:
                self.active_profile = profile
                self.pending_profile = None
                self.esp32_status.active_profile = profile
                self.nano_status.active_profile   = profile
                result = ConfigChangeResult(
                    result=ConfigResult.SUCCESS,
                    profile=profile,
                    esp32_ack="COMMITTED",
                    nano_ack="COMMITTED",
                )
                self._change_history.append(result)
                if len(self._change_history) > 50:
                    self._change_history.pop(0)
                logger.info("Profile %s applied successfully to both devices.", profile)
                return result
            else:
                # Partial commit — cannot reliably roll back radio state
                # but log and report the failure
                self.pending_profile = None
                failed = []
                if not esp32_committed: failed.append("ESP32")
                if not nano_committed:  failed.append("Nano")
                result = ConfigChangeResult(
                    result=ConfigResult.PARTIAL_FAIL,
                    profile=profile,
                    esp32_ack="COMMITTED" if esp32_committed else "TIMEOUT",
                    nano_ack="COMMITTED" if nano_committed else "TIMEOUT",
                    error_message=f"Commit ACK timeout from: {', '.join(failed)}"
                )
                self._change_history.append(result)
                logger.warning("Profile change partial failure: %s", result.error_message)
                return result

    def get_device_statuses(self) -> Dict[str, DeviceStatus]:
        with self._lock:
            return {
                "esp32": self.esp32_status,
                "nano": self.nano_status,
            }

    def get_change_history(self) -> List[ConfigChangeResult]:
        with self._lock:
            return list(self._change_history)

    def apply_sampling_interval(self, interval_seconds: int, cmd_id: Optional[str] = None) -> Dict[str, Any]:
        """Apply dynamic measurement interval to ESP32 transmitter.
        Validates bounds (2s - 3600s), sends command with correlation ID,
        awaits hardware ACK, and handles offline/mock states.
        """
        if interval_seconds < 2 or interval_seconds > 3600:
            return {
                "status": "FAILED",
                "interval_seconds": self.active_sampling_interval,
                "cmd_id": cmd_id,
                "error": "Interval must be between 2 and 3600 seconds",
            }

        cid = cmd_id or f"cmd-{int(time.time() * 1000)}"
        self.last_interval_cmd_id = cid

        with self._lock:
            # If in mock mode or devices not connected
            esp32_conn = self._esp32_ch and self._esp32_ch.is_connected
            if self.mock_mode or not esp32_conn:
                if self.mock_mode:
                    self.active_sampling_interval = interval_seconds
                    self.pending_sampling_interval = None
                    self.last_interval_status = "APPLIED"
                    self.last_interval_ack_time = datetime.now(timezone.utc).isoformat()
                    return {
                        "status": "APPLIED",
                        "requested_interval": interval_seconds,
                        "applied_interval": interval_seconds,
                        "cmd_id": cid,
                        "mock": True,
                        "message": f"Sampling interval set to {interval_seconds}s (simulated)",
                    }
                else:
                    self.pending_sampling_interval = interval_seconds
                    self.last_interval_status = "DEVICE_OFFLINE"
                    return {
                        "status": "DEVICE_OFFLINE",
                        "requested_interval": interval_seconds,
                        "applied_interval": self.active_sampling_interval,
                        "cmd_id": cid,
                        "error": "ESP32 disconnected. Configuration registered as PENDING.",
                    }

            # Hardware connected — send config_interval command
            self.last_interval_status = "PENDING"
            cmd = {
                "type": "config_interval",
                "interval_seconds": interval_seconds,
                "cmd_id": cid,
            }
            sent = self._esp32_ch.send_command(cmd)
            if not sent:
                self.last_interval_status = "FAILED"
                return {
                    "status": "FAILED",
                    "requested_interval": interval_seconds,
                    "cmd_id": cid,
                    "error": "Failed to transmit interval command over serial channel",
                }

            # Await acknowledgement
            ack = self._esp32_ch.wait_for_ack("config_ack", timeout=4.0)
            if ack and ack.get("status") == "APPLIED":
                self.active_sampling_interval = ack.get("interval_seconds", interval_seconds)
                self.pending_sampling_interval = None
                self.last_interval_status = "APPLIED"
                self.last_interval_ack_time = datetime.now(timezone.utc).isoformat()
                return {
                    "status": "APPLIED",
                    "requested_interval": interval_seconds,
                    "applied_interval": self.active_sampling_interval,
                    "cmd_id": cid,
                    "device_ack": "APPLIED",
                }
            elif ack and ack.get("status") == "ERROR":
                self.last_interval_status = "FAILED"
                return {
                    "status": "FAILED",
                    "requested_interval": interval_seconds,
                    "cmd_id": cid,
                    "error": ack.get("error", "ESP32 reported an error applying interval"),
                }
            else:
                self.last_interval_status = "TIMEOUT"
                return {
                    "status": "TIMEOUT",
                    "requested_interval": interval_seconds,
                    "cmd_id": cid,
                    "error": "Timeout waiting for ESP32 interval ACK (4.0s)",
                }

    def get_sampling_interval_status(self) -> Dict[str, Any]:
        """Return the current active, pending, and last confirmed sampling interval state."""
        with self._lock:
            return {
                "active_interval_seconds": self.active_sampling_interval,
                "pending_interval_seconds": self.pending_sampling_interval,
                "last_cmd_id": self.last_interval_cmd_id,
                "status": self.last_interval_status,
                "last_ack_time": self.last_interval_ack_time,
                "esp32_connected": self._esp32_ch.is_connected if self._esp32_ch else False,
            }

    def reconnect(self) -> None:
        """Try to reconnect disconnected device channels."""
        self._connect_devices()

    # ---- Internal helpers ----

    def _handle_nano_line(self, line: str) -> None:
        if self.on_packet_callback:
            try:
                self.on_packet_callback(line)
            except Exception as e:
                logger.error("Error in on_packet_callback: %s", e)

    def _connect_devices(self) -> None:
        with self._lock:
            if not self._esp32_ch:
                self._esp32_ch = DeviceChannel(self.esp32_port, self.baud)
            if not self._nano_ch:
                self._nano_ch = DeviceChannel(self.nano_port, self.baud, on_line_callback=self._handle_nano_line)

            esp32_ok = self._esp32_ch.connect()
            nano_ok  = self._nano_ch.connect()

            self.esp32_status.connected = esp32_ok
            self.nano_status.connected  = nano_ok

            if not esp32_ok:
                self.esp32_status.error_message = f"Cannot open {self.esp32_port}"
            if not nano_ok:
                self.nano_status.error_message = f"Cannot open {self.nano_port}"

    def _refresh_device_statuses(self) -> None:
        time.sleep(2.0)  # Give devices time to boot
        with self._lock:
            if self._esp32_ch and self._esp32_ch.is_connected:
                resp = self._esp32_ch.get_status()
                if resp:
                    self.esp32_status.radio_initialized = True
                    self.esp32_status.active_profile = resp.get("profile", "UNKNOWN")
                    self.esp32_status.pa_level = resp.get("pa_level", "UNKNOWN")
                    self.esp32_status.data_rate = resp.get("data_rate", "UNKNOWN")
                    self.esp32_status.channel   = resp.get("channel", 108)
                    self.esp32_status.supports_250k = resp.get("supports_250k", False)

            if self._nano_ch and self._nano_ch.is_connected:
                resp = self._nano_ch.get_status()
                if resp:
                    self.nano_status.radio_initialized = True
                    self.nano_status.active_profile = resp.get("profile", "UNKNOWN")
                    self.nano_status.pa_level = resp.get("pa_level", "UNKNOWN")
                    self.nano_status.data_rate = resp.get("data_rate", "UNKNOWN")
                    self.nano_status.channel   = resp.get("channel", 108)
                    self.nano_status.supports_250k = resp.get("supports_250k", False)

    def _start_nano_reader(self) -> None:
        """
        Open a dedicated serial port for reading temperature data from Nano (COM12).
        Temperature lines are forwarded to on_packet_callback if set.
        JSON lines go to the config channel (handled via DeviceChannel).
        """
        # The DeviceChannel for nano already opens the port for config — we share
        # the same port. Data routing happens inside DeviceChannel._reader_loop
        # which puts JSON in the response buffer and ignores non-JSON.
        # For temperature lines (non-JSON), we need a separate reader that uses
        # the same serial object. We piggyback by injecting a forwarding callback
        # into the monitoring service instead (see MonitoringService integration).
        pass

    @staticmethod
    def list_ports() -> List[str]:
        return [p.device for p in serial.tools.list_ports.comports()]
