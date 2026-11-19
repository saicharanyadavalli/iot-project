"use client";

import React, { useState } from "react";
import { FlaskConical, Play, TrendingUp, Activity, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api";

interface SimulationTabProps {
  onStepProcessed?: () => void;
}

export const SimulationTab: React.FC<SimulationTabProps> = ({ onStepProcessed }) => {
  const [selectedScenario, setSelectedScenario] = useState<string>("extreme_temp");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [lastResult, setLastResult] = useState<any | null>(null);
  const [driftActive, setDriftActive] = useState<boolean>(false);

  const scenarios = [
    {
      id: "normal",
      title: "Scenario 1: Normal Baseline Telemetry",
      desc: "Simulates clean potable water (24°C, pH 7.2, 250 ppm) within normal operating bounds.",
    },
    {
      id: "extreme_temp",
      title: "Scenario 2: Thermal Discharge (Temp Spike)",
      desc: "Sudden temperature surge to 42°C. Triggers Stage 1 boundary breach & Stage 2 rate of change alert.",
    },
    {
      id: "acid_contamination",
      title: "Scenario 3: Acid Influx (pH Drop)",
      desc: "Severe chemical contamination dropping pH to 4.2. Triggers Stage 1 safety threshold alert.",
    },
    {
      id: "high_tds",
      title: "Scenario 4: High Dissolved Solids",
      desc: "Industrial runoff surging TDS to 850 ppm. Breaches potable thresholds.",
    },
    {
      id: "multivariate_subtle",
      title: "Scenario 5: Subtle 3-Var Multivariate Anomaly",
      desc: "Temp 28°C, pH 6.9, TDS 420 ppm — normal individually, but anomalous in 3D Half-Space Trees.",
    },
    {
      id: "sensor_drift",
      title: "Scenario 6: Gradual Calibration Drift",
      desc: "Slow progressive bias over time. Monitored by online ADWIN drift detector.",
    },
  ];

  const handleExecuteStep = async () => {
    try {
      setIsProcessing(true);
      const res = await api.triggerSimulationStep(
        selectedScenario === "normal" ? undefined : selectedScenario
      );
      setLastResult(res);
      if (onStepProcessed) onStepProcessed();
    } catch (err: any) {
      console.error("Simulation step failed:", err);
    } finally {
      setIsProcessing(false);
    }
  };

  const handleToggleDrift = async () => {
    try {
      const nextState = !driftActive;
      const res = await api.triggerDrift(nextState ? "start" : "reset");
      setDriftActive(res.drift_active);
    } catch (err: any) {
      console.error("Failed to toggle drift:", err);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-5 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-700">
            <FlaskConical className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Simulation Scenario Laboratory
            </h2>
            <p className="text-xs text-zinc-500">
              Inject synthetic environmental anomalies to verify multi-stage detection,
              threshold alerts, and 3D Half-Space Trees rejection logic.
            </p>
          </div>
        </div>

        <button
          onClick={handleToggleDrift}
          className={`px-3.5 py-1.5 rounded-lg text-xs font-medium flex items-center gap-2 border transition ${
            driftActive
              ? "bg-amber-50 text-amber-800 border-amber-300 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800 font-semibold"
              : "bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-700 dark:text-zinc-300 border-zinc-200 dark:border-zinc-700"
          }`}
        >
          <TrendingUp className="w-3.5 h-3.5" />
          {driftActive ? "Drift Active (Stop)" : "Simulate Environmental Drift"}
        </button>
      </div>

      {/* Scenario Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3.5">
        {scenarios.map((sc) => (
          <div
            key={sc.id}
            onClick={() => setSelectedScenario(sc.id)}
            className={`p-4 rounded-xl border cursor-pointer transition ${
              selectedScenario === sc.id
                ? "border-zinc-900 dark:border-zinc-100 bg-zinc-50 dark:bg-zinc-800/60 ring-1 ring-zinc-900 dark:ring-zinc-100 shadow-xs"
                : "border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 hover:border-zinc-300"
            }`}
          >
            <div className="flex items-center justify-between mb-1">
              <h3 className="font-semibold text-xs text-zinc-800 dark:text-zinc-200">{sc.title}</h3>
              {selectedScenario === sc.id && (
                <span className="w-2 h-2 rounded-full bg-zinc-900 dark:bg-zinc-100" />
              )}
            </div>
            <p className="text-[11px] text-zinc-500 leading-snug">{sc.desc}</p>
          </div>
        ))}
      </div>

      {/* Action Bar */}
      <div className="p-4 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs flex items-center justify-between">
        <div className="text-xs text-zinc-500">
          Selected Scenario:{" "}
          <span className="font-mono font-bold text-zinc-800 dark:text-zinc-200 uppercase">
            {selectedScenario}
          </span>
        </div>

        <button
          onClick={handleExecuteStep}
          disabled={isProcessing}
          className="px-5 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium text-xs shadow-xs flex items-center gap-2 transition disabled:opacity-50"
        >
          <Play className="w-3.5 h-3.5 fill-current" />
          {isProcessing ? "Processing Step..." : "Inject Scenario Sample"}
        </button>
      </div>

      {/* Response Preview */}
      {lastResult && (
        <div className="p-5 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs space-y-3">
          <div className="flex items-center gap-2 text-xs font-semibold text-zinc-800 dark:text-zinc-200">
            <Activity className="w-4 h-4 text-zinc-500" />
            <span>Scenario Ingestion Pipeline Output</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs bg-zinc-50 dark:bg-zinc-800/40 p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800">
            <div>
              <span className="text-zinc-400 block text-[10px] font-mono uppercase">Coordinates</span>
              <span className="font-mono font-semibold text-zinc-800 dark:text-zinc-200">
                {lastResult.temperature?.toFixed(1)}°C | {lastResult.ph?.toFixed(2)} | {lastResult.tds?.toFixed(0)} ppm
              </span>
            </div>

            <div>
              <span className="text-zinc-400 block text-[10px] font-mono uppercase">Anomaly Status</span>
              <span
                className={`font-bold ${
                  lastResult.is_anomaly ? "text-rose-600" : "text-emerald-600"
                }`}
              >
                {lastResult.is_anomaly ? "ANOMALY DETECTED" : "NORMAL"}
              </span>
            </div>

            <div>
              <span className="text-zinc-400 block text-[10px] font-mono uppercase">ML Primary Score</span>
              <span className="font-mono font-bold text-zinc-800 dark:text-zinc-200">
                {lastResult.primary_score?.toFixed(4) ?? "0.0000"}
              </span>
            </div>

            <div>
              <span className="text-zinc-400 block text-[10px] font-mono uppercase">Classification</span>
              <span className="font-semibold text-zinc-700 dark:text-zinc-300 truncate block">
                {lastResult.classification}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
