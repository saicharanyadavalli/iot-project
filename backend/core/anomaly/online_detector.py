"""Master online anomaly detection engine.
Orchestrates individual statistical detectors, pairwise Half-Space Trees,
combined three-variable Half-Space Trees, and environmental drift tracking.
Implements the full score-before-learn loop, model state machine, and Cases 1-7 classification.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Optional, List, Any

from config.settings import AppConfig, ModelConfig
from .individual_detector import RobustZScoreDetector, IndividualAnomalyResult
from .rate_of_change import RateOfChangeDetector, RateOfChangeResult
from .pairwise_detector import PairwiseAnomalyDetector, PairwiseResult
from .combined_detector import CombinedAnomalyDetector, CombinedEvaluation
from .drift_detector import EnvironmentalDriftMonitor, DriftStatus
from core.processing.normalization import FeatureNormalizer
from core.processing.validation import SensorValidator, ValidationResult
from core.processing.synchronization import SynchronizedObservation


class ModelState(str, Enum):
    INITIALIZING = "INITIALIZING"
    WARMING_UP = "WARMING_UP"
    MONITORING = "MONITORING"
    ANOMALY_DETECTED = "ANOMALY_DETECTED"
    DRIFT_SUSPECTED = "DRIFT_SUSPECTED"
    SENSOR_DATA_STALE = "SENSOR_DATA_STALE"
    ERROR = "ERROR"


@dataclass
class AnomalyDetectionEvent:
    """Consolidated record of an anomaly detection evaluation."""
    timestamp: datetime
    temperature: Optional[float]
    ph: Optional[float]
    tds: Optional[float]
    data_sources: Dict[str, str]

    model_state: ModelState
    is_anomaly: bool
    classification: str       # e.g. "CRITICAL_THRESHOLD_ALERT", "STATISTICAL_ANOMALY", "NORMAL"
    severity: str             # "NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL"
    primary_score: float      # Primary numeric score for chart plotting
    adaptive_threshold: float

    individual_results: Dict[str, IndividualAnomalyResult]
    rate_results: Dict[str, RateOfChangeResult] = field(default_factory=dict)
    pairwise_result: Optional[PairwiseResult] = None
    combined_result: Optional[CombinedEvaluation] = None
    drift_status: DriftStatus = field(default_factory=lambda: DriftStatus())
    validation_result: ValidationResult = field(default_factory=lambda: ValidationResult(True, True, False, [], [], []))
    learned_this_step: bool = False
    rejection_reason: Optional[str] = None
    installation_id: str = "default"


class AnomalyDetectionEngine:
    """Core ML engine coordinating all detectors, states, and learning cycles."""

    def __init__(self, config: AppConfig):
        self.config = config
        self.normalizer = FeatureNormalizer(config.normalization)
        self.validator = SensorValidator(config.safety, config.normalization)

        # 1. Individual detectors
        self.temp_detector = RobustZScoreDetector("temperature", config.model.individual_window_size, config.model.individual_mad_multiplier)
        self.ph_detector = RobustZScoreDetector("ph", config.model.individual_window_size, config.model.individual_mad_multiplier)
        self.tds_detector = RobustZScoreDetector("tds", config.model.individual_window_size, config.model.individual_mad_multiplier)

        # 1b. Rate of change detector (Stage 2)
        self.rate_detector = RateOfChangeDetector()

        # 2. Pairwise and Combined HST detectors
        self.pairwise_detector = PairwiseAnomalyDetector(config.model, seed=42)
        self.combined_detector = CombinedAnomalyDetector(config.model, seed=100)

        # 3. Shadow candidate models for drift adaptation
        self.shadow_pairwise: Optional[PairwiseAnomalyDetector] = None
        self.shadow_combined: Optional[CombinedAnomalyDetector] = None

        # 4. Drift monitor
        self.drift_monitor = EnvironmentalDriftMonitor(config.model)

        # 5. Engine State
        self.state = ModelState.INITIALIZING
        self.total_observations = 0
        self.warmup_count = 0
        self.observations_learned = 0
        self.anomalies_rejected = 0
        self.last_detection_time: Optional[datetime] = None
        self.installation_id: str = "default"

    def process_observation(self, obs: SynchronizedObservation) -> AnomalyDetectionEvent:
        """Process a synchronized observation through validation, scoring, classification, and learning."""
        if not hasattr(self, "rate_detector"):
            self.rate_detector = RateOfChangeDetector()
        if not hasattr(self, "installation_id"):
            self.installation_id = "default"
        now = obs.timestamp or datetime.now(timezone.utc)
        self.total_observations += 1
        self.last_detection_time = now

        # Step 1: Input Validation and Safety Check
        val_res = self.validator.validate_observation(obs.temperature, obs.ph, obs.tds)

        # Step 2: Individual Parameter Scoring
        in_warmup = self.warmup_count < self.config.model.warmup_samples
        ind_results: Dict[str, IndividualAnomalyResult] = {}
        if obs.temperature is not None and val_res.is_valid:
            ind_results["temperature"] = self.temp_detector.evaluate(obs.temperature, in_warmup=in_warmup)
        if obs.ph is not None and val_res.is_valid:
            ind_results["ph"] = self.ph_detector.evaluate(obs.ph, in_warmup=in_warmup)
        if obs.tds is not None and val_res.is_valid:
            ind_results["tds"] = self.tds_detector.evaluate(obs.tds, in_warmup=in_warmup)

        # Step 2b: Rate of Change Evaluation (Stage 2)
        rate_results: Dict[str, RateOfChangeResult] = {}
        if obs.temperature is not None and val_res.is_valid:
            rate_results["temperature"] = self.rate_detector.evaluate("temperature", obs.temperature, now)
        if obs.ph is not None and val_res.is_valid:
            rate_results["ph"] = self.rate_detector.evaluate("ph", obs.ph, now)
        if obs.tds is not None and val_res.is_valid:
            rate_results["tds"] = self.rate_detector.evaluate("tds", obs.tds, now)

        # Step 3: Feature Normalization for Multivariate HST
        norm_res = self.normalizer.normalize_dict({
            "temperature": obs.temperature,
            "ph": obs.ph,
            "tds": obs.tds,
        })

        # Step 4: Pairwise and Three-Variable Scoring
        synced_pairs = {
            PairwiseAnomalyDetector.PAIR_TEMP_PH: obs.is_pairwise_temp_ph_synced,
            PairwiseAnomalyDetector.PAIR_TEMP_TDS: obs.is_pairwise_temp_tds_synced,
            PairwiseAnomalyDetector.PAIR_PH_TDS: obs.is_pairwise_ph_tds_synced,
        }

        # Check learning eligibility
        in_warmup = self.warmup_count < self.config.model.warmup_samples
        allow_learning = val_res.is_valid and norm_res.is_in_bounds and not val_res.is_safety_violation

        # Perform scoring on active models
        pair_res = self.pairwise_detector.evaluate_and_learn(
            norm_res.scaled_dict,
            synced_pairs,
            allow_learning=allow_learning and in_warmup, # During warmup, learn baseline
        )
        comb_res = self.combined_detector.evaluate_and_learn(
            norm_res.scaled_dict,
            obs.is_three_variable_synced,
            allow_learning=allow_learning and in_warmup,
        )

        # Step 5: Concept and Environmental Drift Monitoring
        drift_status = self.drift_monitor.update(
            features={"temperature": obs.temperature, "ph": obs.ph, "tds": obs.tds},
            multivariate_score=comb_res.score if comb_res.evaluated else None,
            is_safe_and_valid=allow_learning,
            on_promote_callback=self._promote_shadow_models,
        )

        # Initialize shadow models if newly started
        if drift_status.shadow_active and self.shadow_pairwise is None:
            self._init_shadow_models()

        # Update shadow models during drift regime
        if self.shadow_pairwise and drift_status.shadow_active and allow_learning:
            self.shadow_pairwise.evaluate_and_learn(norm_res.scaled_dict, synced_pairs, allow_learning=True)
            if self.shadow_combined:
                self.shadow_combined.evaluate_and_learn(norm_res.scaled_dict, obs.is_three_variable_synced, allow_learning=True)

        # Step 6: Anomaly Classification Logic (Cases 1 - 7 + Safety + Normal)
        classification, severity, is_anomaly = self._classify_event(
            val_res=val_res,
            ind_results=ind_results,
            rate_results=rate_results,
            pair_res=pair_res,
            comb_res=comb_res,
            drift_status=drift_status,
        )

        # Step 7: Update Learned Counters & Protected Incremental Updates
        learned_this_step = False
        rejection_reason = None

        if in_warmup:
            if allow_learning:
                self.warmup_count += 1
                self.observations_learned += 1
                learned_this_step = True
            else:
                rejection_reason = "Excluded during warmup: invalid, out of bounds, or safety violation"
        else:
            if allow_learning and not is_anomaly:
                # Normal eligible observation outside warmup: learn incremental update!
                self.pairwise_detector.evaluate_and_learn(norm_res.scaled_dict, synced_pairs, allow_learning=True)
                self.combined_detector.evaluate_and_learn(norm_res.scaled_dict, obs.is_three_variable_synced, allow_learning=True)
                self.observations_learned += 1
                learned_this_step = True
            else:
                self.anomalies_rejected += 1
                if not allow_learning:
                    rejection_reason = "Rejected: invalid, out of domain bounds, or physical safety violation"
                else:
                    rejection_reason = f"Protected: observation flagged as {classification}"

        # Step 8: Update Engine State
        if (obs.temperature is None and obs.ph is None and obs.tds is None) or (not obs.temp_fresh and not obs.ph_fresh and not obs.tds_fresh):
            self.state = ModelState.SENSOR_DATA_STALE
        elif not val_res.is_valid:
            self.state = ModelState.ERROR
        elif in_warmup:
            self.state = ModelState.WARMING_UP
        elif drift_status.is_drift_suspected:
            self.state = ModelState.DRIFT_SUSPECTED
        elif is_anomaly:
            self.state = ModelState.ANOMALY_DETECTED
        else:
            self.state = ModelState.MONITORING

        # Primary score for summary graphs
        primary_score = 0.0
        primary_thresh = 0.0
        if comb_res.evaluated:
            primary_score = comb_res.score
            primary_thresh = comb_res.threshold
        elif pair_res.has_any_anomaly:
            max_p = max(pair_res.evaluations.values(), key=lambda e: e.score)
            primary_score = max_p.score
            primary_thresh = max_p.threshold
        elif ind_results:
            max_i = max(ind_results.values(), key=lambda e: e.score)
            primary_score = max_i.score
            primary_thresh = max_i.threshold

        return AnomalyDetectionEvent(
            timestamp=now,
            temperature=obs.temperature,
            ph=obs.ph,
            tds=obs.tds,
            data_sources=obs.data_sources,
            model_state=self.state,
            is_anomaly=is_anomaly,
            classification=classification,
            severity=severity,
            primary_score=round(primary_score, 4),
            adaptive_threshold=round(primary_thresh, 4),
            individual_results=ind_results,
            rate_results=rate_results,
            pairwise_result=pair_res,
            combined_result=comb_res,
            drift_status=drift_status,
            validation_result=val_res,
            learned_this_step=learned_this_step,
            rejection_reason=rejection_reason,
            installation_id=self.installation_id,
        )

    def _classify_event(
        self,
        val_res: ValidationResult,
        ind_results: Dict[str, IndividualAnomalyResult],
        rate_results: Dict[str, RateOfChangeResult],
        pair_res: PairwiseResult,
        comb_res: CombinedEvaluation,
        drift_status: DriftStatus,
    ) -> tuple[str, str, bool]:
        """Aggregate anomaly flags into specific physical/multivariate classifications."""
        # 1. Physical safety limit / threshold violation takes highest priority
        if val_res.is_safety_violation:
            return f"SAFETY VIOLATION (CRITICAL_THRESHOLD_ALERT): {'; '.join(val_res.safety_violations)}", "CRITICAL", True

        # Check individual anomaly flags (Stage 4)
        t_ind = ind_results.get("temperature", None)
        p_ind = ind_results.get("ph", None)
        d_ind = ind_results.get("tds", None)

        t_anom = t_ind.is_anomaly if t_ind else False
        p_anom = p_ind.is_anomaly if p_ind else False
        d_anom = d_ind.is_anomaly if d_ind else False

        # Check rate of change warnings (Stage 2)
        rate_warnings = [r.message for r in rate_results.values() if r.is_warning and r.message]

        # Check pairwise flags (Stage 5)
        ev_t_p = pair_res.evaluations.get(PairwiseAnomalyDetector.PAIR_TEMP_PH)
        ev_t_d = pair_res.evaluations.get(PairwiseAnomalyDetector.PAIR_TEMP_TDS)
        ev_p_d = pair_res.evaluations.get(PairwiseAnomalyDetector.PAIR_PH_TDS)

        pair_tp_anom = ev_t_p.is_anomaly if (ev_t_p and ev_t_p.evaluated) else False
        pair_td_anom = ev_t_d.is_anomaly if (ev_t_d and ev_t_d.evaluated) else False
        pair_pd_anom = ev_p_d.is_anomaly if (ev_p_d and ev_p_d.evaluated) else False

        # Check 3D combined flag (Stage 5)
        comb_anom = comb_res.is_anomaly if comb_res.evaluated else False

        # Case 7: All three parameters form an unusual combination
        if comb_anom:
            return "MULTIVARIATE ANOMALY (3-PARAMETER)", "HIGH", True

        # Case 4: Temperature + pH combination is unusual
        if pair_tp_anom and not pair_td_anom and not pair_pd_anom:
            return "TEMPERATURE + PH COMBINED ANOMALY", "MEDIUM", True

        # Case 5: Temperature + TDS combination is unusual
        if pair_td_anom and not pair_tp_anom and not pair_pd_anom:
            return "TEMPERATURE + TDS COMBINED ANOMALY", "MEDIUM", True

        # Case 6: pH + TDS combination is unusual
        if pair_pd_anom and not pair_tp_anom and not pair_td_anom:
            return "PH + TDS COMBINED ANOMALY", "MEDIUM", True

        # Multiple pairwise anomalies
        if sum([pair_tp_anom, pair_td_anom, pair_pd_anom]) > 1:
            return "MULTIPLE PAIRWISE ANOMALY", "HIGH", True

        # Case 1: Temperature is unusual independently
        if t_anom and not p_anom and not d_anom:
            return "TEMPERATURE ANOMALY", "MEDIUM", True

        # Case 2: pH is unusual independently
        if p_anom and not t_anom and not d_anom:
            return "PH ANOMALY", "MEDIUM", True

        # Case 3: TDS is unusual independently
        if d_anom and not t_anom and not p_anom:
            return "TDS ANOMALY", "MEDIUM", True

        # Multiple individual anomalies
        if sum([t_anom, p_anom, d_anom]) > 1:
            return "MULTIPLE INDIVIDUAL ANOMALIES", "HIGH", True

        # Rate of change warning (Stage 2)
        if rate_warnings:
            return f"RATE_OF_CHANGE_WARNING: {'; '.join(rate_warnings)}", "MEDIUM", True

        if drift_status.is_drift_suspected:
            return f"DRIFT SUSPECTED ({', '.join(drift_status.drifted_features)})", "LOW", False

        return "NORMAL", "NONE", False

    def _init_shadow_models(self) -> None:
        """Instantiate shadow candidate models to adapt to a newly detected environmental drift."""
        self.shadow_pairwise = PairwiseAnomalyDetector(self.config.model, seed=999)
        self.shadow_combined = CombinedAnomalyDetector(self.config.model, seed=1000)

    def _promote_shadow_models(self) -> None:
        """Promote candidate shadow models to become the active production models."""
        if self.shadow_pairwise is not None:
            self.pairwise_detector = self.shadow_pairwise
            self.shadow_pairwise = None
        if self.shadow_combined is not None:
            self.combined_detector = self.shadow_combined
            self.shadow_combined = None

    def __setstate__(self, state):
        """Restore unpickled state with backward compatibility defaults."""
        self.__dict__.update(state)
        if not hasattr(self, "installation_id"):
            self.installation_id = "default"
        if not hasattr(self, "rate_detector"):
            self.rate_detector = RateOfChangeDetector()

    def get_stage_readiness(self) -> Dict[str, Any]:
        """Return readiness status and statistics across all detection stages."""
        in_warmup = self.warmup_count < self.config.model.warmup_samples
        return {
            "stage_1_thresholds": {
                "name": "User-Defined Operating Thresholds",
                "is_active": True,
                "readiness": "ACTIVE",
                "description": "Evaluates operating bounds immediately from the first reading.",
            },
            "stage_2_rate_of_change": {
                "name": "Rate of Change Monitoring",
                "is_active": self.total_observations >= 2,
                "readiness": "ACTIVE" if self.total_observations >= 2 else "COLLECTING",
                "description": "Calculates temporal derivative (change/sec) from the second observation onward.",
            },
            "stage_3_statistical_baseline": {
                "name": "Statistical Baseline Collection",
                "is_active": True,
                "sample_count": {
                    "temperature": len(self.temp_detector.window),
                    "ph": len(self.ph_detector.window),
                    "tds": len(self.tds_detector.window),
                },
                "readiness": "ACTIVE" if len(self.temp_detector.window) >= 10 else "COLLECTING",
                "medians": {
                    "temperature": self.temp_detector.score_one(self.temp_detector.window[-1])[1] if len(self.temp_detector.window) >= 5 else None,
                    "ph": self.ph_detector.score_one(self.ph_detector.window[-1])[1] if len(self.ph_detector.window) >= 5 else None,
                    "tds": self.tds_detector.score_one(self.tds_detector.window[-1])[1] if len(self.tds_detector.window) >= 5 else None,
                },
            },
            "stage_4_robust_zscore": {
                "name": "Rolling Median + MAD",
                "is_active": len(self.temp_detector.window) >= 10,
                "readiness": "ACTIVE" if len(self.temp_detector.window) >= 10 else "WARMING_UP",
                "description": "Online robust Z-score detection using Median Absolute Deviation.",
            },
            "stage_5_half_space_trees": {
                "name": "Multivariate Half-Space Trees",
                "is_active": not in_warmup,
                "readiness": "MONITORING" if not in_warmup else "WARMING_UP",
                "warmup_progress": f"{min(self.warmup_count, self.config.model.warmup_samples)}/{self.config.model.warmup_samples}",
                "description": "Streaming multivariate online anomaly detection with QuantileFilter.",
            },
            "installation_id": getattr(self, "installation_id", "default"),
            "total_observations": self.total_observations,
            "observations_learned": self.observations_learned,
            "anomalies_rejected": self.anomalies_rejected,
        }
