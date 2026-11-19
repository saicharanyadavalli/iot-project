"""Central monitoring orchestrator and coordination service.
Bridges serial acquisition, manual sensor entry, time synchronization,
anomaly detection, SQLite persistence, and periodic model checkpointing.
Designed as a thread-safe singleton to survive Streamlit page refreshes.

Dual serial architecture (new phase):
  - COM13 (ESP32): Config command channel only. ESP32 is now a transmitter;
                   its USB serial is used for config ACK exchange.
  - COM12 (Nano):  Primary temperature data channel. Nano receives DS18B20
                   readings wirelessly from ESP32 and forwards them here in
                   the format: [ESP32 RX] Received Packet #N: "Temp: 24.50 C"
"""

from __future__ import annotations
import threading
import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from config.settings import AppConfig
from core.acquisition.serial_reader import SerialReader, ParsedReading
from core.acquisition.data_parser import DataParser
from core.processing.synchronization import TimestampSynchronizer, SynchronizedObservation
from core.anomaly.online_detector import AnomalyDetectionEngine, ModelState, AnomalyDetectionEvent
from core.database.database import init_db
from core.database.repository import MonitoringRepository
from core.services.model_manager import ModelManager
from core.services.wireless_config_service import WirelessConfigService, ConfigChangeResult
from core.simulation.simulator import DataSimulator

logger = logging.getLogger(__name__)


class MonitoringService:
    """Master monitoring coordinator managing the lifecycle of background workers and models."""

    _instance: Optional[MonitoringService] = None
    _singleton_lock = threading.Lock()

    def __init__(self, config: Optional[AppConfig] = None):
        self.config = config or AppConfig.load_from_file()
        init_db(self.config.db_path)

        self.repository = MonitoringRepository(self.config.db_path)
        self.model_manager = ModelManager(self.config.checkpoint_path, self.repository)

        # Restore learned model or initialize fresh engine
        restored = self.model_manager.load_checkpoint()
        self.engine: AnomalyDetectionEngine = restored if restored is not None else AnomalyDetectionEngine(self.config)

        self.synchronizer = TimestampSynchronizer(self.config.sync)
        self.simulator = DataSimulator(seed=42)

        # Restore latest values from DB into synchronizer
        latest_t = self.repository.get_latest_temperature()
        if latest_t:
            ts_t = datetime.fromisoformat(latest_t["timestamp"])
            self.synchronizer.update_temperature(latest_t["temperature"], ts_t, latest_t["data_source"])

        latest_p = self.repository.get_latest_ph()
        if latest_p:
            ts_p = datetime.fromisoformat(latest_p["timestamp"])
            self.synchronizer.update_manual_ph(latest_p["ph"], ts_p, latest_p["data_source"])

        latest_d = self.repository.get_latest_tds()
        if latest_d:
            ts_d = datetime.fromisoformat(latest_d["timestamp"])
            self.synchronizer.update_manual_tds(latest_d["tds"], ts_d, latest_d["data_source"])

        # Data parser (reads from Nano / COM12 temperature output)
        self.parser = DataParser(
            parse_mode=self.config.serial.parse_mode,
            ping_demo_baseline=24.5
        )

        # Primary temperature serial reader — now points to Nano (COM12) which outputs
        # the "[ESP32 RX] Received Packet #N: "Temp: X C"" format after wireless receipt.
        # config.serial.port should be set to COM12 for the Nano receiver.
        self.serial_reader: Optional[SerialReader] = None

        # Wireless config service — manages ESP32 (COM13) and Nano (COM12) profile config
        self.wireless_service: Optional[WirelessConfigService] = None

        self._processing_lock = threading.RLock()
        self.total_anomalies_detected = len(self.repository.get_anomaly_history(limit=5000))
        self.latest_event: Optional[AnomalyDetectionEvent] = None
        self._last_checkpoint_count = self.engine.total_observations

        # Evaluate initial state from DB
        if latest_t or latest_p or latest_d:
            try:
                obs = self.synchronizer.get_synchronized_observation()
                self.latest_event = self.engine.process_observation(obs)
            except Exception:
                pass

        # Start serial acquisition and wireless service if not in simulation mode
        if not self.config.simulation_enabled:
            self._start_serial()
            self._start_wireless_service()

    @classmethod
    def get_instance(cls, config: Optional[AppConfig] = None) -> MonitoringService:
        """Singleton accessor to ensure one persistent service instance across Streamlit reruns."""
        with cls._singleton_lock:
            if cls._instance is None:
                cls._instance = cls(config)
            return cls._instance

    def _start_serial(self) -> None:
        """Initialize and launch background serial reader.
        If enable_dual_serial is True, wireless_service manages the port to avoid contention."""
        if self.config.wireless.enable_dual_serial:
            return
        if self.serial_reader is not None:
            return
        self.serial_reader = SerialReader(
            config=self.config.serial,
            parser=self.parser,
            on_reading_callback=self._on_serial_reading,
        )
        self.serial_reader.start()

    def _start_wireless_service(self) -> None:
        """Initialize and start the wireless configuration service."""
        if self.wireless_service is not None:
            return
        try:
            wc = self.config.wireless
            self.wireless_service = WirelessConfigService(
                esp32_port=wc.esp32_port,
                nano_port=wc.nano_port,
                baud=wc.baud_rate,
                on_packet_callback=self._on_wireless_raw_line,
            )
            self.wireless_service.start()
            logger.info("WirelessConfigService started (ESP32=%s, Nano=%s)", wc.esp32_port, wc.nano_port)
        except Exception as e:
            logger.warning("WirelessConfigService failed to start: %s", e)
            self.wireless_service = None

    def _on_wireless_raw_line(self, line: str) -> None:
        """Process incoming raw lines from Arduino Nano over USB serial."""
        reading = self.parser.parse_line(line)
        if reading.is_valid and reading.temperature is not None:
            self._on_serial_reading(reading)

    def _on_serial_reading(self, reading: ParsedReading) -> None:
        """Callback invoked when serial reader parses an incoming packet."""
        if reading.is_valid and reading.temperature is not None:
            # Store raw reading in SQLite
            self.repository.insert_raw_temperature(
                temperature=reading.temperature,
                timestamp=reading.timestamp,
                packet_counter=reading.packet_counter,
                data_source=reading.data_source,
                raw_text=reading.raw_text,
            )
            # Update synchronizer
            self.synchronizer.update_temperature(
                value=reading.temperature,
                timestamp=reading.timestamp,
                data_source=reading.data_source,
            )
            # Process combined step
            self.process_latest_pipeline()

    def submit_manual_readings(
        self, ph: float, tds: float, timestamp: Optional[datetime] = None
    ) -> AnomalyDetectionEvent:
        """Submit a manual pH and TDS measurement pair from the dashboard form."""
        ts = timestamp or datetime.now(timezone.utc)
        with self._processing_lock:
            # Store in database
            self.repository.insert_manual_ph(ph, ts, data_source="manual_input")
            self.repository.insert_manual_tds(tds, ts, data_source="manual_input")

            # Update synchronizer
            self.synchronizer.update_manual_pair(ph, tds, ts, data_source="manual_input")

            # Evaluate pipeline immediately
            return self.process_latest_pipeline()

    def process_simulation_step(self, injected_type: Optional[str] = None, timestamp: Optional[datetime] = None) -> AnomalyDetectionEvent:
        """Run a single simulated observation step through the identical pipeline."""
        with self._processing_lock:
            if injected_type:
                self.simulator.inject_anomaly(injected_type)

            sample = self.simulator.generate_sample(timestamp=timestamp)

            # Store raw records
            self.repository.insert_raw_temperature(
                temperature=sample.temperature,
                timestamp=sample.timestamp,
                data_source="simulated",
                raw_text=f"Simulated sample: T={sample.temperature}, pH={sample.ph}, TDS={sample.tds}",
            )
            self.repository.insert_manual_ph(sample.ph, sample.timestamp, data_source="simulated")
            self.repository.insert_manual_tds(sample.tds, sample.timestamp, data_source="simulated")

            # Feed to synchronizer
            self.synchronizer.update_temperature(sample.temperature, sample.timestamp, data_source="simulated")
            self.synchronizer.update_manual_pair(sample.ph, sample.tds, sample.timestamp, data_source="simulated")

            return self.process_latest_pipeline(current_time=sample.timestamp)

    def process_latest_pipeline(self, current_time: Optional[datetime] = None) -> AnomalyDetectionEvent:
        """Run the synchronized state through the online anomaly detection engine."""
        with self._processing_lock:
            obs = self.synchronizer.get_synchronized_observation(current_time=current_time)

            # Store synchronized observation in DB
            self.repository.insert_synchronized_observation(
                timestamp=obs.timestamp,
                temperature=obs.temperature,
                ph=obs.ph,
                tds=obs.tds,
                is_three_var_synced=obs.is_three_variable_synced,
                data_sources=obs.data_sources,
            )

            # Evaluate through online ML engine
            event = self.engine.process_observation(obs)
            self.latest_event = event

            if event.is_anomaly:
                self.total_anomalies_detected += 1

            # Save anomaly event to DB
            self.repository.insert_anomaly_event(event)

            # Record drift event if newly triggered
            if event.drift_status.drift_detected_now:
                self.repository.insert_drift_event(
                    timestamp=event.timestamp,
                    drifted_features=event.drift_status.drifted_features,
                    details=event.drift_status.details,
                    status="DRIFT_SUSPECTED",
                )

            # Checkpoint model state periodically
            if (self.engine.total_observations - self._last_checkpoint_count) >= self.config.model.checkpoint_interval_samples:
                self.model_manager.save_checkpoint(self.engine)
                self._last_checkpoint_count = self.engine.total_observations

            return event

    def apply_wireless_profile(self, profile: str) -> ConfigChangeResult:
        """Apply a wireless transmission profile to both ESP32 and Nano.
        Blocks until two-phase commit completes or times out (~15s max).
        """
        if self.wireless_service is None:
            self._start_wireless_service()
        if self.wireless_service is None:
            from core.services.wireless_config_service import ConfigChangeResult, ConfigResult
            return ConfigChangeResult(result=ConfigResult.NO_HARDWARE, profile=profile,
                                      error_message="WirelessConfigService not available")
        result = self.wireless_service.apply_profile(profile)
        if result.result.value == "SUCCESS":
            self.config.wireless.active_profile = profile
            self.config.save_to_file()
        return result

    def apply_sampling_interval(self, interval_seconds: int, cmd_id: Optional[str] = None) -> Dict[str, Any]:
        """Apply a dynamic sensor sampling interval to the ESP32 transmitter.
        Persists request to database audit log and coordinates with WirelessConfigService.
        """
        import uuid
        cid = cmd_id or f"req-{uuid.uuid4().hex[:8]}"

        # Record initial request in database
        self.repository.record_sampling_interval_request(
            cmd_id=cid,
            requested_interval=interval_seconds,
            status="PENDING",
        )

        if self.wireless_service is None:
            self._start_wireless_service()

        if self.wireless_service is None:
            self.repository.update_sampling_interval_status(
                cmd_id=cid,
                status="DEVICE_OFFLINE",
                error_message="WirelessConfigService unavailable; setting saved as PENDING",
            )
            return {
                "status": "DEVICE_OFFLINE",
                "requested_interval": interval_seconds,
                "cmd_id": cid,
                "error": "Device offline. Interval saved as pending.",
            }

        result = self.wireless_service.apply_sampling_interval(interval_seconds, cmd_id=cid)
        status = result.get("status", "FAILED")
        applied = result.get("applied_interval")
        ack = result.get("device_ack")
        err = result.get("error")

        self.repository.update_sampling_interval_status(
            cmd_id=cid,
            status=status,
            applied_interval=applied,
            device_ack=ack,
            error_message=err,
        )
        return result

    def update_thresholds(
        self,
        temp_min: float,
        temp_max: float,
        ph_min: float,
        ph_max: float,
        tds_min: float,
        tds_max: float,
        installation_id: str = "default",
        notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Update and persist physical operating safety thresholds with strict validation."""
        # Validation: lower < upper
        if temp_min >= temp_max:
            return {"status": "ERROR", "error": "Temperature min must be strictly less than max"}
        if ph_min >= ph_max:
            return {"status": "ERROR", "error": "pH min must be strictly less than max"}
        if tds_min >= tds_max:
            return {"status": "ERROR", "error": "TDS min must be strictly less than max"}

        # Validation: physical domain reasonableness
        if temp_min < -40.0 or temp_max > 125.0:
            return {"status": "ERROR", "error": "Temperature bounds must lie within [-40°C, 125°C]"}
        if ph_min < 0.0 or ph_max > 14.0:
            return {"status": "ERROR", "error": "pH bounds must lie within [0.0, 14.0]"}
        if tds_min < 0.0 or tds_max > 5000.0:
            return {"status": "ERROR", "error": "TDS bounds must lie within [0, 5000 ppm]"}

        with self._processing_lock:
            # Update active config
            self.config.safety.temp_min = float(temp_min)
            self.config.safety.temp_max = float(temp_max)
            self.config.safety.ph_min = float(ph_min)
            self.config.safety.ph_max = float(ph_max)
            self.config.safety.tds_min = float(tds_min)
            self.config.safety.tds_max = float(tds_max)
            self.config.save_to_file()

            # Update validator object in engine
            self.engine.validator.safety = self.config.safety

            # Persist in DB audit table
            row_id = self.repository.save_threshold_config(
                temp_min=temp_min,
                temp_max=temp_max,
                ph_min=ph_min,
                ph_max=ph_max,
                tds_min=tds_min,
                tds_max=tds_max,
                installation_id=installation_id,
                notes=notes,
            )
            latest = self.repository.get_latest_threshold_config(installation_id)

            return {
                "status": "SUCCESS",
                "version": latest.get("version", 1) if latest else 1,
                "thresholds": {
                    "temperature": [temp_min, temp_max],
                    "ph": [ph_min, ph_max],
                    "tds": [tds_min, tds_max],
                },
                "installation_id": installation_id,
            }

    def get_stage_readiness(self) -> Dict[str, Any]:
        """Expose multi-stage anomaly detection readiness status."""
        return self.engine.get_stage_readiness()

    def save_checkpoint_now(self) -> bool:
        """Trigger an immediate atomic model checkpoint save."""
        return self.model_manager.save_checkpoint(self.engine)

    def scan_ports(self) -> List[Dict[str, Any]]:
        """Scan system COM ports and determine probable device roles."""
        import serial.tools.list_ports
        results = []
        try:
            com_ports = list(serial.tools.list_ports.comports())
        except Exception as e:
            logger.warning("Error enumerating serial ports: %s", e)
            return results

        nano_p = (self.config.wireless.nano_port or "").upper()
        esp_p = (self.config.wireless.esp32_port or "").upper()

        esp_connected = False
        nano_connected = False
        if self.wireless_service:
            st = self.wireless_service.get_device_statuses()
            if st.get("esp32"):
                esp_connected = bool(getattr(st["esp32"], "is_connected", False))
            if st.get("nano"):
                nano_connected = bool(getattr(st["nano"], "is_connected", False))

        for p in com_ports:
            dev = p.device
            desc = p.description or ""
            hwid = p.hwid or ""
            mfg = p.manufacturer or ""

            upper_str = f"{desc} {hwid} {mfg}".upper()

            role = "unknown"
            if any(k in upper_str for k in ["CH340", "NANO", "FT232", "ATMEGA", "ARDUINO", "USB-SERIAL"]):
                role = "nano"
            elif any(k in upper_str for k in ["CP210", "ESP32", "SILICON LABS", "CH9102", "JTAG/SERIAL"]):
                role = "esp32"
            elif any(k in upper_str for k in ["BTHENUM", "BLUETOOTH"]):
                role = "bluetooth"

            is_nano = (dev.upper() == nano_p)
            is_esp = (dev.upper() == esp_p)
            is_open = (is_nano and nano_connected) or (is_esp and esp_connected)

            results.append({
                "device": dev,
                "description": desc,
                "hwid": hwid,
                "manufacturer": mfg,
                "suggested_role": role,
                "is_active_nano": is_nano,
                "is_active_esp32": is_esp,
                "is_open": is_open,
            })
        return results

    def reconfigure_ports(
        self, nano_port: Optional[str] = None, esp32_port: Optional[str] = None
    ) -> Dict[str, Any]:
        """Dynamically update Nano and/or ESP32 serial COM ports, persist config, and reconnect."""
        with self._processing_lock:
            if nano_port:
                self.config.wireless.nano_port = nano_port.strip()
                self.config.serial.port = nano_port.strip()
            if esp32_port:
                self.config.wireless.esp32_port = esp32_port.strip()

            self.config.save_to_file()

            # Stop existing wireless service if running
            if self.wireless_service:
                try:
                    self.wireless_service.stop()
                except Exception as e:
                    logger.warning("Error stopping wireless service: %s", e)
                self.wireless_service = None

            # Re-initialize and start wireless service
            self._start_wireless_service()

            esp_conn = False
            nano_conn = False
            if self.wireless_service:
                st = self.wireless_service.get_device_statuses()
                if st.get("esp32"):
                    esp_conn = bool(getattr(st["esp32"], "is_connected", False))
                if st.get("nano"):
                    nano_conn = bool(getattr(st["nano"], "is_connected", False))

            return {
                "status": "SUCCESS",
                "nano_port": self.config.wireless.nano_port,
                "esp32_port": self.config.wireless.esp32_port,
                "nano_connected": nano_conn,
                "esp32_connected": esp_conn,
            }

    def shutdown(self) -> None:
        """Clean shutdown of background readers and model persistence."""
        if self.serial_reader:
            self.serial_reader.stop()
            self.serial_reader = None
        if self.wireless_service:
            self.wireless_service.stop()
            self.wireless_service = None
        self.save_checkpoint_now()
        logger.info("MonitoringService shutdown complete.")
