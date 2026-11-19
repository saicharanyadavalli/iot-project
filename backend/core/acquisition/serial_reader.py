"""Thread-safe background serial reader for ESP32 receiver.
Handles connection, automatic reconnection, thread-safe queuing,
graceful shutdown, and hardware mock/test modes.
"""

from __future__ import annotations
import threading
import queue
import time
import logging
from typing import Optional, Callable
import serial
import serial.tools.list_ports

from .data_parser import DataParser, ParsedReading
from config.settings import SerialConfig

logger = logging.getLogger(__name__)


class SerialReader:
    """Asynchronous serial reader running in a dedicated thread."""

    def __init__(
        self,
        config: SerialConfig,
        parser: Optional[DataParser] = None,
        on_reading_callback: Optional[Callable[[ParsedReading], None]] = None,
    ):
        self.config = config
        self.parser = parser or DataParser(parse_mode=config.parse_mode)
        self.on_reading_callback = on_reading_callback

        self.reading_queue: queue.Queue[ParsedReading] = queue.Queue(maxsize=1000)
        self.raw_line_queue: queue.Queue[str] = queue.Queue(maxsize=500)

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()

        self._is_connected = False
        self._last_error: Optional[str] = None
        self._packets_received = 0
        self._last_packet_time: Optional[float] = None
        self._ser: Optional[serial.Serial] = None

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    @property
    def packets_received(self) -> int:
        return self._packets_received

    @property
    def last_packet_time(self) -> Optional[float]:
        return self._last_packet_time

    @staticmethod
    def list_available_ports() -> list[str]:
        """List active hardware COM ports on the system."""
        try:
            ports = serial.tools.list_ports.comports()
            return [p.device for p in ports]
        except Exception as e:
            logger.error("Failed to list COM ports: %s", e)
            return []

    def start(self) -> None:
        """Start the background serial worker thread."""
        with self._lock:
            if self._thread and self._thread.is_alive():
                logger.info("SerialReader thread is already running.")
                return

            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="SerialReaderThread",
                daemon=True,
            )
            self._thread.start()
            logger.info("SerialReader background thread started.")

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the background reader thread and close the serial port."""
        self._stop_event.set()
        with self._lock:
            if self._ser and self._ser.is_open:
                try:
                    self._ser.close()
                except Exception as e:
                    logger.warning("Error closing serial port: %s", e)
                finally:
                    self._ser = None
                    self._is_connected = False

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
            self._thread = None
        logger.info("SerialReader stopped.")

    def _run_loop(self) -> None:
        """Main background reading and auto-reconnect loop."""
        while not self._stop_event.is_set():
            if self.config.mock_mode:
                self._mock_loop()
                return

            try:
                self._connect_and_read()
            except Exception as e:
                self._is_connected = False
                self._last_error = str(e)
                logger.warning("Serial connection error on %s: %s", self.config.port, e)
                # Wait before attempting reconnection
                self._stop_event.wait(self.config.reconnect_interval_sec)

    def _connect_and_read(self) -> None:
        """Open port, initialize DTR/RTS, and stream incoming lines."""
        with self._lock:
            logger.info("Opening serial port %s at %d baud...", self.config.port, self.config.baud_rate)
            self._ser = serial.Serial(
                port=self.config.port,
                baudrate=self.config.baud_rate,
                timeout=self.config.timeout,
            )
            # ESP32 auto-reset toggle
            self._ser.setDTR(False)
            self._ser.setRTS(True)
            time.sleep(0.1)
            self._ser.setRTS(False)
            self._is_connected = True
            self._last_error = None
            logger.info("Connected to serial port %s.", self.config.port)

        while not self._stop_event.is_set():
            if not self._ser or not self._ser.is_open:
                break

            if self._ser.in_waiting:
                raw_bytes = self._ser.readline()
                try:
                    line = raw_bytes.decode("utf-8", errors="replace").strip()
                except Exception:
                    line = ""

                if line:
                    self._process_line(line)
            else:
                time.sleep(0.02)

        # Cleanup if disconnected
        with self._lock:
            if self._ser and self._ser.is_open:
                self._ser.close()
            self._is_connected = False

    def _process_line(self, line: str) -> None:
        """Parse incoming line and enqueue result."""
        # Keep raw line in buffer for diagnostics
        if not self.raw_line_queue.full():
            self.raw_line_queue.put_nowait(line)

        parsed = self.parser.parse_line(line)
        self._packets_received += 1
        self._last_packet_time = time.time()

        try:
            self.reading_queue.put(parsed, block=False)
        except queue.Full:
            # Drop oldest item to prevent memory exhaustion
            try:
                self.reading_queue.get_nowait()
                self.reading_queue.put_nowait(parsed)
            except Exception:
                pass

        if self.on_reading_callback:
            try:
                self.on_reading_callback(parsed)
            except Exception as e:
                logger.exception("Error in serial reading callback: %s", e)

    def _mock_loop(self) -> None:
        """Simulated serial stream for testing without hardware."""
        self._is_connected = True
        counter = 0
        while not self._stop_event.is_set():
            counter += 1
            mock_temp = 24.0 + (counter % 5) * 0.2
            mock_line = f'[ESP32 RX] Received Packet #{counter}: "Temp: {mock_temp:.2f} C"'
            self._process_line(mock_line)
            self._stop_event.wait(1.0)
        self._is_connected = False

    def inject_mock_line(self, line: str) -> ParsedReading:
        """Directly inject a serial line for automated unit testing."""
        parsed = self.parser.parse_line(line)
        self._packets_received += 1
        self._last_packet_time = time.time()
        self.reading_queue.put(parsed)
        return parsed
