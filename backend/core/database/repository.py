"""Data Access Object (DAO) repository for IoT persistence.
Uses parameterized queries to prevent SQL injection and provides structured
querying for real-time dashboard visualizations and analytics.
"""

from __future__ import annotations
import json
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any

from .database import get_connection
from core.anomaly.online_detector import AnomalyDetectionEvent


class MonitoringRepository:
    """Repository handling all CRUD database operations."""

    def __init__(self, db_path: str = "data/iot_monitoring.db"):
        self.db_path = db_path

    def insert_raw_temperature(
        self,
        temperature: float,
        timestamp: datetime,
        packet_counter: Optional[int] = None,
        data_source: str = "physical_serial",
        raw_text: Optional[str] = None,
    ) -> int:
        ts_str = timestamp.astimezone(timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO raw_temperature_readings (timestamp, temperature, packet_counter, data_source, raw_text)
            VALUES (?, ?, ?, ?, ?);
            """,
            (ts_str, float(temperature), packet_counter, data_source, raw_text),
        )
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def insert_manual_ph(
        self, ph: float, timestamp: datetime, data_source: str = "manual_input"
    ) -> int:
        ts_str = timestamp.astimezone(timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO manual_ph_readings (timestamp, ph, data_source)
            VALUES (?, ?, ?);
            """,
            (ts_str, float(ph), data_source),
        )
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def insert_manual_tds(
        self, tds: float, timestamp: datetime, data_source: str = "manual_input"
    ) -> int:
        ts_str = timestamp.astimezone(timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO manual_tds_readings (timestamp, tds, data_source)
            VALUES (?, ?, ?);
            """,
            (ts_str, float(tds), data_source),
        )
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def insert_synchronized_observation(
        self,
        timestamp: datetime,
        temperature: Optional[float],
        ph: Optional[float],
        tds: Optional[float],
        is_three_var_synced: bool,
        data_sources: Dict[str, str],
    ) -> int:
        ts_str = timestamp.astimezone(timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO synchronized_observations 
            (timestamp, temperature, ph, tds, is_three_var_synced, data_sources)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (
                ts_str,
                temperature,
                ph,
                tds,
                1 if is_three_var_synced else 0,
                json.dumps(data_sources),
            ),
        )
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def insert_anomaly_event(self, event: AnomalyDetectionEvent) -> int:
        ts_str = event.timestamp.astimezone(timezone.utc).isoformat()
        details_dict = {
            "rejection_reason": event.rejection_reason,
            "drift_suspected": event.drift_status.is_drift_suspected,
            "drifted_features": event.drift_status.drifted_features,
            "validation_errors": event.validation_result.errors,
            "safety_violations": event.validation_result.safety_violations,
        }
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO anomaly_events 
            (timestamp, temperature, ph, tds, classification, severity, primary_score,
             adaptive_threshold, is_anomaly, model_state, details)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                ts_str,
                event.temperature,
                event.ph,
                event.tds,
                event.classification,
                event.severity,
                event.primary_score,
                event.adaptive_threshold,
                1 if event.is_anomaly else 0,
                event.model_state.value,
                json.dumps(details_dict),
            ),
        )
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def insert_drift_event(
        self,
        timestamp: datetime,
        drifted_features: List[str],
        details: str,
        status: str = "DRIFT_SUSPECTED",
    ) -> int:
        ts_str = timestamp.astimezone(timezone.utc).isoformat()
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO drift_events (timestamp, drifted_features, details, status)
            VALUES (?, ?, ?, ?);
            """,
            (ts_str, json.dumps(drifted_features), details, status),
        )
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def get_latest_temperature(self) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM raw_temperature_readings ORDER BY timestamp DESC LIMIT 1;"
        )
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_latest_ph(self) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM manual_ph_readings ORDER BY timestamp DESC LIMIT 1;")
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_latest_tds(self) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM manual_tds_readings ORDER BY timestamp DESC LIMIT 1;")
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_time_series_data(
        self, window_minutes: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Fetch synchronized and anomaly records for chart visualizations."""
        conn = get_connection(self.db_path)
        cur = conn.cursor()

        if window_minutes is not None and window_minutes > 0:
            cutoff = (datetime.now(timezone.utc) - timedelta(minutes=window_minutes)).isoformat()
            query = """
            SELECT a.id, a.timestamp, a.temperature, a.ph, a.tds, a.classification,
                   a.severity, a.primary_score, a.adaptive_threshold, a.is_anomaly, a.model_state
            FROM anomaly_events a
            WHERE a.timestamp >= ?
            ORDER BY a.timestamp ASC;
            """
            cur.execute(query, (cutoff,))
        else:
            query = """
            SELECT a.id, a.timestamp, a.temperature, a.ph, a.tds, a.classification,
                   a.severity, a.primary_score, a.adaptive_threshold, a.is_anomaly, a.model_state
            FROM anomaly_events a
            ORDER BY a.timestamp ASC
            LIMIT 2000;
            """
            cur.execute(query)

        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def get_anomaly_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Fetch anomaly events (excluding NORMAL) for the history table."""
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, timestamp, temperature, ph, tds, classification, severity,
                   primary_score, adaptive_threshold, model_state, details
            FROM anomaly_events
            WHERE is_anomaly = 1
            ORDER BY timestamp DESC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def record_checkpoint(
        self,
        filepath: str,
        total_obs: int,
        warmup_cnt: int,
        learned_cnt: int,
        state: str,
        timestamp: Optional[datetime] = None,
    ) -> int:
        ts_str = (timestamp or datetime.now(timezone.utc)).isoformat()
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO model_checkpoints (timestamp, filepath, total_observations, warmup_count, learned_count, state)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (ts_str, filepath, total_obs, warmup_cnt, learned_cnt, state),
        )
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def get_latest_checkpoint(self) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM model_checkpoints ORDER BY timestamp DESC LIMIT 1;")
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    # ---- Threshold Configurations ----

    def save_threshold_config(
        self,
        temp_min: float,
        temp_max: float,
        ph_min: float,
        ph_max: float,
        tds_min: float,
        tds_max: float,
        installation_id: str = "default",
        notes: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> int:
        ts_str = (timestamp or datetime.now(timezone.utc)).isoformat()
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT COALESCE(MAX(version), 0) + 1 FROM threshold_configurations WHERE installation_id = ?;",
            (installation_id,),
        )
        next_ver = cur.fetchone()[0]

        cur.execute(
            """
            INSERT INTO threshold_configurations
            (timestamp, version, installation_id, temp_min, temp_max, ph_min, ph_max, tds_min, tds_max, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (ts_str, next_ver, installation_id, temp_min, temp_max, ph_min, ph_max, tds_min, tds_max, notes),
        )
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def get_latest_threshold_config(self, installation_id: str = "default") -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM threshold_configurations
            WHERE installation_id = ?
            ORDER BY version DESC LIMIT 1;
            """,
            (installation_id,),
        )
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_threshold_history(self, installation_id: str = "default", limit: int = 50) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            SELECT * FROM threshold_configurations
            WHERE installation_id = ?
            ORDER BY version DESC LIMIT ?;
            """,
            (installation_id, limit),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    # ---- Sampling Interval Configurations ----

    def record_sampling_interval_request(
        self,
        cmd_id: str,
        requested_interval: int,
        status: str = "PENDING",
        timestamp: Optional[datetime] = None,
    ) -> int:
        ts_str = (timestamp or datetime.now(timezone.utc)).isoformat()
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO sampling_interval_configurations
            (timestamp, cmd_id, requested_interval, status)
            VALUES (?, ?, ?, ?);
            """,
            (ts_str, cmd_id, requested_interval, status),
        )
        row_id = cur.lastrowid
        conn.commit()
        conn.close()
        return row_id

    def update_sampling_interval_status(
        self,
        cmd_id: str,
        status: str,
        applied_interval: Optional[int] = None,
        device_ack: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> bool:
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            """
            UPDATE sampling_interval_configurations
            SET status = ?, applied_interval = COALESCE(?, applied_interval),
                device_ack = ?, error_message = ?
            WHERE cmd_id = ?;
            """,
            (status, applied_interval, device_ack, error_message, cmd_id),
        )
        updated = cur.rowcount > 0
        conn.commit()
        conn.close()
        return updated

    def get_latest_sampling_interval_status(self) -> Optional[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute("SELECT * FROM sampling_interval_configurations ORDER BY id DESC LIMIT 1;")
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None

    def get_sampling_interval_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = get_connection(self.db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM sampling_interval_configurations ORDER BY id DESC LIMIT ?;",
            (limit,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows
