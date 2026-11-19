"""Model lifecycle management, atomic checkpointing, and safe restoration.
Ensures incremental learned weights, adaptive thresholds, and drift states persist
across Streamlit refreshes and application restarts without data corruption.
"""

from __future__ import annotations
import os
import pickle
import logging
from datetime import datetime, timezone
from typing import Optional

from core.anomaly.online_detector import AnomalyDetectionEngine
from core.database.repository import MonitoringRepository

logger = logging.getLogger(__name__)


class ModelManager:
    """Manages atomic saving and restoration of online anomaly detection models."""

    def __init__(self, checkpoint_path: str = "data/model_checkpoint.pkl", repository: Optional[MonitoringRepository] = None):
        self.checkpoint_path = checkpoint_path
        self.repository = repository
        self.last_save_time: Optional[datetime] = None

    def save_checkpoint(self, engine: AnomalyDetectionEngine) -> bool:
        """Atomically persist engine state to disk and log to database."""
        tmp_path = f"{self.checkpoint_path}.tmp"
        try:
            os.makedirs(os.path.dirname(self.checkpoint_path), exist_ok=True)
            with open(tmp_path, "wb") as f:
                pickle.dump(engine, f, protocol=pickle.HIGHEST_PROTOCOL)
                f.flush()
                os.fsync(f.fileno())

            # Atomic replace prevents corrupted state on unexpected termination
            os.replace(tmp_path, self.checkpoint_path)
            self.last_save_time = datetime.now(timezone.utc)

            if self.repository:
                self.repository.record_checkpoint(
                    filepath=self.checkpoint_path,
                    total_obs=engine.total_observations,
                    warmup_cnt=engine.warmup_count,
                    learned_cnt=engine.observations_learned,
                    state=engine.state.value,
                    timestamp=self.last_save_time,
                )

            logger.info("Saved atomic model checkpoint at %s", self.checkpoint_path)
            return True
        except Exception as e:
            logger.error("Failed to save model checkpoint: %s", e)
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            return False

    def load_checkpoint(self) -> Optional[AnomalyDetectionEngine]:
        """Safely restore learned engine from trusted local checkpoint file."""
        if not os.path.exists(self.checkpoint_path):
            logger.info("No existing model checkpoint found at %s. Starting fresh.", self.checkpoint_path)
            return None

        try:
            with open(self.checkpoint_path, "rb") as f:
                engine = pickle.load(f)
            logger.info(
                "Restored model checkpoint: %d observations, %d learned, state=%s",
                engine.total_observations,
                engine.observations_learned,
                engine.state.value,
            )
            return engine
        except Exception as e:
            logger.error("Failed to load model checkpoint from %s: %s", self.checkpoint_path, e)
            return None
