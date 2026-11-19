"""SQLite database initialization and connection management.
Creates tables, sets up indexes, and manages SQLite connections with WAL mode.
"""

from __future__ import annotations
import os
import sqlite3
import logging

logger = logging.getLogger(__name__)


def get_connection(db_path: str = "data/iot_monitoring.db") -> sqlite3.Connection:
    """Return a sqlite3 connection configured for thread safety and row access."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: str = "data/iot_monitoring.db") -> None:
    """Initialize SQLite tables and indexes."""
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = get_connection(db_path)
    cur = conn.cursor()

    # 1. Raw temperature readings
    cur.execute("""
    CREATE TABLE IF NOT EXISTS raw_temperature_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        temperature REAL NOT NULL,
        packet_counter INTEGER,
        data_source TEXT NOT NULL,
        raw_text TEXT
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_raw_temp_ts ON raw_temperature_readings(timestamp);")

    # 2. Manual pH readings
    cur.execute("""
    CREATE TABLE IF NOT EXISTS manual_ph_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        ph REAL NOT NULL,
        data_source TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_ph_ts ON manual_ph_readings(timestamp);")

    # 3. Manual TDS readings
    cur.execute("""
    CREATE TABLE IF NOT EXISTS manual_tds_readings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        tds REAL NOT NULL,
        data_source TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_manual_tds_ts ON manual_tds_readings(timestamp);")

    # 4. Synchronized combined observations
    cur.execute("""
    CREATE TABLE IF NOT EXISTS synchronized_observations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        temperature REAL,
        ph REAL,
        tds REAL,
        is_three_var_synced INTEGER NOT NULL,
        data_sources TEXT
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_sync_obs_ts ON synchronized_observations(timestamp);")

    # 5. Anomaly events
    cur.execute("""
    CREATE TABLE IF NOT EXISTS anomaly_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        temperature REAL,
        ph REAL,
        tds REAL,
        classification TEXT NOT NULL,
        severity TEXT NOT NULL,
        primary_score REAL NOT NULL,
        adaptive_threshold REAL NOT NULL,
        is_anomaly INTEGER NOT NULL,
        model_state TEXT NOT NULL,
        details TEXT
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_anom_ts ON anomaly_events(timestamp);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_anom_class ON anomaly_events(classification);")

    # 6. Drift events
    cur.execute("""
    CREATE TABLE IF NOT EXISTS drift_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        drifted_features TEXT NOT NULL,
        details TEXT,
        status TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_drift_ts ON drift_events(timestamp);")

    # 7. Application config table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS application_config (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # 8. Model checkpoints metadata
    cur.execute("""
    CREATE TABLE IF NOT EXISTS model_checkpoints (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        filepath TEXT NOT NULL,
        total_observations INTEGER NOT NULL,
        warmup_count INTEGER NOT NULL,
        learned_count INTEGER NOT NULL,
        state TEXT NOT NULL
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_ts ON model_checkpoints(timestamp);")

    # 9. Configurable threshold audit history
    cur.execute("""
    CREATE TABLE IF NOT EXISTS threshold_configurations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        version INTEGER NOT NULL,
        installation_id TEXT NOT NULL DEFAULT 'default',
        temp_min REAL NOT NULL,
        temp_max REAL NOT NULL,
        ph_min REAL NOT NULL,
        ph_max REAL NOT NULL,
        tds_min REAL NOT NULL,
        tds_max REAL NOT NULL,
        notes TEXT
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_thresh_ts ON threshold_configurations(timestamp);")

    # 10. Sampling interval command lifecycle tracking
    cur.execute("""
    CREATE TABLE IF NOT EXISTS sampling_interval_configurations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        cmd_id TEXT NOT NULL,
        requested_interval INTEGER NOT NULL,
        applied_interval INTEGER,
        status TEXT NOT NULL,
        device_ack TEXT,
        error_message TEXT
    );
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_interval_cmd ON sampling_interval_configurations(cmd_id);")

    conn.commit()
    conn.close()
    logger.info("Database initialized successfully at %s", db_path)
