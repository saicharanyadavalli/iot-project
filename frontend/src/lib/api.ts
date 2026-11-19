/**
 * API Client Functions for FastAPI Backend
 */

import {
  SystemStatus,
  LatestReadings,
  ThresholdConfig,
  Multivariate3DResponse,
  AnomalyEventRecord,
  WirelessStatus,
  TimeSeriesPoint,
  PortScanResponse,
} from "@/types/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function fetchJson<T>(endpoint: string, options?: RequestInit): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const res = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers || {}),
    },
  });

  if (!res.ok) {
    let errorDetail = "API request failed";
    try {
      const err = await res.json();
      errorDetail = err.detail || err.error || JSON.stringify(err);
    } catch {
      errorDetail = res.statusText;
    }
    throw new Error(`[${res.status}] ${errorDetail}`);
  }

  return res.json();
}

export const api = {
  // System Status
  getStatus: () => fetchJson<SystemStatus>("/api/status"),

  // Readings
  getLatestReadings: () => fetchJson<LatestReadings>("/api/readings/latest"),
  getTimeSeries: (windowMinutes?: number, limit = 100) =>
    fetchJson<{ total: number; data: TimeSeriesPoint[] }>(
      `/api/readings/history?limit=${limit}${windowMinutes ? `&window_minutes=${windowMinutes}` : ""}`
    ),

  // Manual Input
  submitManualReading: (ph: number, tds: number, timestamp?: string) =>
    fetchJson<{
      status: string;
      timestamp: string;
      is_anomaly: boolean;
      classification: string;
      severity: string;
      primary_score: number;
      adaptive_threshold: number;
    }>("/api/readings/manual", {
      method: "POST",
      body: JSON.stringify({ ph, tds, timestamp }),
    }),

  // Thresholds
  getThresholds: (installationId = "default") =>
    fetchJson<ThresholdConfig>(`/api/config/thresholds?installation_id=${installationId}`),
  updateThresholds: (config: {
    temp_min: number;
    temp_max: number;
    ph_min: number;
    ph_max: number;
    tds_min: number;
    tds_max: number;
    installation_id?: string;
    notes?: string;
  }) =>
    fetchJson<{
      status: string;
      version: number;
      thresholds: Record<string, [number, number]>;
      installation_id: string;
    }>("/api/config/thresholds", {
      method: "PUT",
      body: JSON.stringify(config),
    }),
  getThresholdHistory: (installationId = "default", limit = 20) =>
    fetchJson<ThresholdConfig[]>(
      `/api/config/thresholds/history?installation_id=${installationId}&limit=${limit}`
    ),

  // Dynamic Sampling Interval
  getSamplingInterval: () =>
    fetchJson<{
      active_interval_seconds: number;
      pending_interval_seconds: number | null;
      last_cmd_id: string | null;
      status: string;
      last_ack_time: string | null;
      esp32_connected: boolean;
    }>("/api/config/interval"),
  setSamplingInterval: (interval_seconds: number, cmd_id?: string) =>
    fetchJson<{
      status: string;
      requested_interval: number;
      applied_interval?: number;
      cmd_id: string;
      error?: string;
      message?: string;
    }>("/api/config/interval", {
      method: "POST",
      body: JSON.stringify({ interval_seconds, cmd_id }),
    }),
  getIntervalHistory: (limit = 20) =>
    fetchJson<any[]>(`/api/config/interval/history?limit=${limit}`),

  // Wireless nRF24L01 Profile
  getWirelessConfig: () => fetchJson<WirelessStatus>("/api/config/wireless"),
  setWirelessProfile: (profile: "SHORT" | "BALANCED" | "LONG") =>
    fetchJson<{
      result: string;
      profile: string;
      esp32_ack: string | null;
      nano_ack: string | null;
      error_message: string | null;
      timestamp: string;
    }>("/api/config/wireless", {
      method: "POST",
      body: JSON.stringify({ profile }),
    }),

  // 3D Multivariate Coordinates
  get3DPoints: (limit = 500) =>
    fetchJson<Multivariate3DResponse>(`/api/multivariate/3d?limit=${limit}`),

  // Anomaly History
  getAnomalyHistory: (limit = 100) =>
    fetchJson<AnomalyEventRecord[]>(`/api/anomalies/history?limit=${limit}`),

  // Simulation Controls
  triggerSimulationStep: (injected_type?: string) =>
    fetchJson<{
      status: string;
      timestamp: string;
      temperature: number;
      ph: number;
      tds: number;
      is_anomaly: boolean;
      classification: string;
      primary_score: number;
    }>("/api/simulation/step", {
      method: "POST",
      body: JSON.stringify({ injected_type }),
    }),
  triggerDrift: (action: "start" | "reset") =>
    fetchJson<{ status: string; drift_active: boolean; message: string }>("/api/simulation/drift", {
      method: "POST",
      body: JSON.stringify({ action }),
    }),
  toggleSimulation: (enabled: boolean) =>
    fetchJson<{ status: string; simulation_enabled: boolean }>("/api/simulation/toggle", {
      method: "POST",
      body: JSON.stringify({ enabled }),
    }),

  // Hardware Port Auto-Detection & Selection
  scanPorts: () => fetchJson<PortScanResponse>("/api/hardware/ports"),
  updatePorts: (nano_port?: string, esp32_port?: string) =>
    fetchJson<{
      status: string;
      nano_port: string;
      esp32_port: string;
      nano_connected: boolean;
      esp32_connected: boolean;
    }>("/api/hardware/ports", {
      method: "POST",
      body: JSON.stringify({ nano_port, esp32_port }),
    }),
};
