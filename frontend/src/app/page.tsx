"use client";

import React, { useState, useEffect, useCallback } from "react";
import { Navbar } from "@/components/layout/Navbar";
import { Sidebar, TabKey } from "@/components/layout/Sidebar";
import { OverviewTab } from "@/components/overview/OverviewTab";
import { LiveMonitoringTab } from "@/components/live/LiveMonitoringTab";
import { Multivariate3DTab } from "@/components/multivariate/Multivariate3DTab";
import { AnomalyTab } from "@/components/anomalies/AnomalyTab";
import { ManualInputTab } from "@/components/manual/ManualInputTab";
import { ThresholdTab } from "@/components/thresholds/ThresholdTab";
import { HardwareTab } from "@/components/hardware/HardwareTab";
import { SimulationTab } from "@/components/simulation/SimulationTab";

import { useWebSocket, WebSocketMessage } from "@/lib/useWebSocket";
import { api } from "@/lib/api";
import { SystemStatus, LatestReadings, ThresholdConfig } from "@/types/api";

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [systemStatus, setSystemStatus] = useState<SystemStatus | null>(null);
  const [latestReadings, setLatestReadings] = useState<LatestReadings | null>(null);
  const [thresholds, setThresholds] = useState<ThresholdConfig | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Initial Data Fetch
  const loadInitialData = useCallback(async () => {
    try {
      setIsRefreshing(true);
      const [st, rd, th] = await Promise.all([
        api.getStatus().catch(() => null),
        api.getLatestReadings().catch(() => null),
        api.getThresholds().catch(() => null),
      ]);
      if (st) setSystemStatus(st);
      if (rd) setLatestReadings(rd);
      if (th) setThresholds(th);
    } catch (err) {
      console.error("Initial data load error:", err);
    } finally {
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // Periodic auto-refresh synchronized with active hardware sampling interval
  useEffect(() => {
    // Interval in ms, minimum 2s, maximum 60s, default 5s
    const activeSec = systemStatus?.sampling_interval?.active_interval_seconds ?? 5;
    const intervalMs = Math.max(2, Math.min(activeSec, 60)) * 1000;

    const timer = setInterval(() => {
      // Background poll to ensure system status & readings remain synchronized
      loadInitialData();
    }, intervalMs);

    return () => clearInterval(timer);
  }, [systemStatus?.sampling_interval?.active_interval_seconds, loadInitialData]);

  // Handle incoming live WebSocket broadcasts
  const handleWebSocketMessage = useCallback((msg: WebSocketMessage) => {
    const eventType = msg.event || msg.type;
    switch (eventType) {
      case "system_snapshot":
        if (msg.data?.status) setSystemStatus(msg.data.status);
        if (msg.data?.latest_readings) setLatestReadings(msg.data.latest_readings);
        break;

      case "sensor_reading":
      case "new_reading":
        setLatestReadings((prev) => {
          if (!prev) return prev;
          const updated = { ...prev };
          const d = msg.data;
          if (d.temperature !== undefined) {
            updated.temperature = {
              value: d.temperature,
              timestamp: d.timestamp || msg.timestamp,
              data_source: d.data_source || (d.data_sources?.temperature) || "physical_serial",
              is_stale: false,
              age_seconds: 0,
            };
          }
          if (d.ph !== undefined) {
            updated.ph = {
              value: d.ph,
              timestamp: d.timestamp || msg.timestamp,
              data_source: d.data_source || (d.data_sources?.ph) || "manual_input",
              is_stale: false,
              age_seconds: 0,
            };
          }
          if (d.tds !== undefined) {
            updated.tds = {
              value: d.tds,
              timestamp: d.timestamp || msg.timestamp,
              data_source: d.data_source || (d.data_sources?.tds) || "manual_input",
              is_stale: false,
              age_seconds: 0,
            };
          }
          if (d.is_anomaly !== undefined) {
            updated.latest_event = {
              classification: d.classification || "NORMAL",
              severity: d.severity || "NONE",
              is_anomaly: d.is_anomaly,
              primary_score: d.primary_score || 0,
              adaptive_threshold: d.adaptive_threshold || 0,
            };
          }
          return updated;
        });
        break;

      case "anomaly_detected":
        setSystemStatus((prev) =>
          prev ? { ...prev, total_anomalies: prev.total_anomalies + 1 } : prev
        );
        break;

      case "sampling_interval_status":
        setSystemStatus((prev) =>
          prev
            ? {
                ...prev,
                sampling_interval: {
                  ...prev.sampling_interval,
                  status: msg.data.status,
                  pending_interval_seconds: msg.data.requested_interval,
                  active_interval_seconds:
                    msg.data.applied_interval ?? prev.sampling_interval.active_interval_seconds,
                  last_cmd_id: msg.data.cmd_id,
                },
              }
            : prev
        );
        break;

      case "configuration_updated":
        if (msg.data.config_type === "thresholds") {
          loadInitialData();
        }
        break;

      case "port_configuration_updated":
        loadInitialData();
        break;

      case "system_status":
        if (msg.data) setSystemStatus(msg.data);
        break;

      default:
        break;
    }
  }, [loadInitialData]);

  const { status: wsStatus } = useWebSocket(handleWebSocketMessage);

  return (
    <div className="min-h-screen bg-zinc-50 dark:bg-zinc-950 text-zinc-900 dark:text-zinc-100 flex flex-col font-sans">
      <Navbar
        wsStatus={wsStatus}
        systemStatus={systemStatus}
        onRefresh={loadInitialData}
        isRefreshing={isRefreshing}
      />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar
          activeTab={activeTab}
          onTabChange={setActiveTab}
          anomalyCount={systemStatus?.total_anomalies ?? 0}
        />

        <main className="flex-1 overflow-y-auto p-6 md:p-8">
          <div className="max-w-7xl mx-auto">
            {activeTab === "overview" && (
              <OverviewTab
                systemStatus={systemStatus}
                latestReadings={latestReadings}
                onNavigate={setActiveTab}
              />
            )}

            {activeTab === "live" && (
              <LiveMonitoringTab
                thresholds={thresholds}
                refreshIntervalSeconds={systemStatus?.sampling_interval?.active_interval_seconds ?? 5}
              />
            )}

            {activeTab === "multivariate" && (
              <Multivariate3DTab
                refreshIntervalSeconds={systemStatus?.sampling_interval?.active_interval_seconds ?? 5}
              />
            )}

            {activeTab === "anomalies" && (
              <AnomalyTab
                refreshIntervalSeconds={systemStatus?.sampling_interval?.active_interval_seconds ?? 5}
              />
            )}

            {activeTab === "manual" && <ManualInputTab onSubmitted={loadInitialData} />}

            {activeTab === "thresholds" && (
              <ThresholdTab currentConfig={thresholds} onSaved={loadInitialData} />
            )}

            {activeTab === "hardware" && (
              <HardwareTab
                samplingInterval={systemStatus?.sampling_interval ?? null}
                wirelessProfile={systemStatus?.wireless_profile ?? null}
                onUpdated={loadInitialData}
              />
            )}

            {activeTab === "simulation" && (
              <SimulationTab onStepProcessed={loadInitialData} />
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
