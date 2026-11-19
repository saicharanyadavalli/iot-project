/**
 * TypeScript Interfaces for FastAPI Backend REST & WebSocket API
 */

export interface StageInfo {
  name: string;
  is_active: boolean;
  readiness: "ACTIVE" | "COLLECTING" | "MONITORING" | "WARMING_UP" | "STANDBY";
  description: string;
  sample_count?: Record<string, number>;
  medians?: Record<string, number>;
  warmup_progress?: string;
}

export interface StageReadiness {
  stage_1_thresholds: StageInfo;
  stage_2_rate_of_change: StageInfo;
  stage_3_statistical_baseline: StageInfo;
  stage_4_robust_zscore: StageInfo;
  stage_5_half_space_trees: StageInfo;
  installation_id: string;
  total_observations: number;
  observations_learned: number;
  anomalies_rejected: number;
}

export interface SamplingIntervalState {
  active_interval_seconds: number;
  pending_interval_seconds: number | null;
  last_cmd_id: string | null;
  status: "IDLE" | "PENDING" | "APPLIED" | "DEVICE_OFFLINE" | "FAILED" | "TIMEOUT";
  last_ack_time: string | null;
  esp32_connected: boolean;
}

export interface SystemStatus {
  model_state: string;
  serial_connected: boolean;
  simulation_enabled: boolean;
  total_observations: number;
  warmup_count: number;
  warmup_target: number;
  observations_learned: number;
  total_anomalies: number;
  last_detection_time: string | null;
  sampling_interval: SamplingIntervalState;
  wireless_profile: string;
  stage_readiness: StageReadiness;
}

export interface ParameterReading {
  value: number;
  timestamp: string;
  data_source: string;
  is_stale: boolean;
  age_seconds: number;
}

export interface LatestEvent {
  classification: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "NORMAL" | "NONE";
  is_anomaly: boolean;
  primary_score: number;
  adaptive_threshold: number;
}

export interface LatestReadings {
  temperature: ParameterReading | null;
  ph: ParameterReading | null;
  tds: ParameterReading | null;
  is_three_variable_synced: boolean;
  latest_event: LatestEvent | null;
}

export interface ThresholdConfig {
  id?: number;
  version: number;
  installation_id: string;
  temp_min: number;
  temp_max: number;
  ph_min: number;
  ph_max: number;
  tds_min: number;
  tds_max: number;
  timestamp?: string;
  notes?: string;
}

export interface Point3D {
  x: number; // Temperature (°C)
  y: number; // pH
  z: number; // TDS (ppm)
  is_anomaly: number;
  classification: string;
  severity: string;
  primary_score: number;
  timestamp: string;
}

export interface Multivariate3DResponse {
  total: number;
  points: Point3D[];
}

export interface AnomalyEventRecord {
  id: number;
  timestamp: string;
  temperature: number | null;
  ph: number | null;
  tds: number | null;
  classification: string;
  severity: string;
  primary_score: number;
  adaptive_threshold: number;
  model_state: string;
  details?: string;
}

export interface ProfileSpec {
  name: string;
  pa_level: string;
  data_rate: string;
  channel: number;
  retry_delay_us: number;
  retry_count: number;
  description: string;
}

export interface WirelessStatus {
  active_profile: string;
  profiles: Record<string, ProfileSpec>;
  devices: {
    esp32: any;
    nano: any;
  };
}

export interface TimeSeriesPoint {
  id: number;
  timestamp: string;
  temperature: number | null;
  ph: number | null;
  tds: number | null;
  is_anomaly: number;
  classification: string;
  severity: string;
  primary_score: number;
}

export interface PortScanItem {
  device: string;
  description: string;
  hwid: string;
  manufacturer?: string | null;
  suggested_role: "nano" | "esp32" | "bluetooth" | "unknown";
  is_active_nano: boolean;
  is_active_esp32: boolean;
  is_open: boolean;
}

export interface PortScanResponse {
  available_ports: PortScanItem[];
  active_nano_port: string;
  active_esp32_port: string;
  nano_connected: boolean;
  esp32_connected: boolean;
}

