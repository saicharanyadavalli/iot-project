"use client";

import React from "react";
import {
  Thermometer,
  Droplet,
  Zap,
  Activity,
  Layers,
  ShieldCheck,
  ArrowRight,
} from "lucide-react";
import { SystemStatus, LatestReadings } from "@/types/api";

interface OverviewTabProps {
  systemStatus: SystemStatus | null;
  latestReadings: LatestReadings | null;
  onNavigate: (tab: any) => void;
}

export const OverviewTab: React.FC<OverviewTabProps> = ({
  systemStatus,
  latestReadings,
  onNavigate,
}) => {
  const stageReadiness = systemStatus?.stage_readiness;

  const getStageBadge = (readiness?: string) => {
    switch (readiness) {
      case "ACTIVE":
      case "MONITORING":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
            ACTIVE
          </span>
        );
      case "COLLECTING":
      case "WARMING_UP":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-50 text-amber-700 dark:bg-amber-950/50 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
            WARMING UP
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700">
            STANDBY
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Banner: Model State & Diagnostics */}
      <div className="p-5 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-700">
            <Layers className="w-5 h-5" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500">
                Pipeline Status
              </span>
              <span className="text-xs font-mono font-bold px-2 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 border border-zinc-200 dark:border-zinc-700">
                {systemStatus?.model_state ?? "INITIALIZING"}
              </span>
            </div>
            <p className="text-xs font-medium text-zinc-600 dark:text-zinc-300 mt-0.5">
              River Half-Space Trees with QuantileFilter Dynamic Threshold &amp; ADWIN Drift Protection
            </p>
          </div>
        </div>

        <div className="flex items-center gap-6 text-xs text-zinc-600 dark:text-zinc-400">
          <div>
            <span className="text-zinc-400 block text-[10px] font-mono uppercase">Warmup Target</span>
            <span className="font-mono font-bold text-zinc-800 dark:text-zinc-200 text-sm">
              {systemStatus ? `${systemStatus.warmup_count} / ${systemStatus.warmup_target}` : "--"}
            </span>
          </div>
          <div className="border-l border-zinc-200 dark:border-zinc-800 pl-6">
            <span className="text-zinc-400 block text-[10px] font-mono uppercase">Obs. Learned</span>
            <span className="font-mono font-bold text-zinc-800 dark:text-zinc-200 text-sm">
              {systemStatus?.observations_learned ?? "--"}
            </span>
          </div>
          <div className="border-l border-zinc-200 dark:border-zinc-800 pl-6">
            <span className="text-zinc-400 block text-[10px] font-mono uppercase">Anomalies Rejected</span>
            <span className="font-mono font-bold text-rose-600 dark:text-rose-400 text-sm">
              {stageReadiness?.anomalies_rejected ?? systemStatus?.total_anomalies ?? 0}
            </span>
          </div>
        </div>
      </div>

      {/* 3 Core Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
        {/* Temperature Card */}
        <div className="p-5 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500">
              Temperature
            </span>
            <div className="p-1.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
              <Thermometer className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-mono font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              {latestReadings?.temperature?.value != null
                ? `${latestReadings.temperature.value.toFixed(1)}°C`
                : "--"}
            </span>
            {latestReadings?.temperature?.is_stale && (
              <span className="text-xs text-amber-600 font-medium">(Stale)</span>
            )}
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-zinc-500 border-t border-zinc-100 dark:border-zinc-800/80 pt-2.5">
            <span>Source: {latestReadings?.temperature?.data_source ?? "ESP32 (DS18B20)"}</span>
            <span className="font-mono">{latestReadings?.temperature ? `${latestReadings.temperature.age_seconds}s ago` : "--"}</span>
          </div>
        </div>

        {/* pH Card */}
        <div className="p-5 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500">
              pH Acidity
            </span>
            <div className="p-1.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
              <Droplet className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-mono font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              {latestReadings?.ph?.value != null ? latestReadings.ph.value.toFixed(2) : "--"}
            </span>
            {latestReadings?.ph?.is_stale && (
              <span className="text-xs text-amber-600 font-medium">(Stale)</span>
            )}
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-zinc-500 border-t border-zinc-100 dark:border-zinc-800/80 pt-2.5">
            <span>Source: {latestReadings?.ph?.data_source ?? "Manual Input"}</span>
            <span className="font-mono">{latestReadings?.ph ? `${latestReadings.ph.age_seconds}s ago` : "--"}</span>
          </div>
        </div>

        {/* TDS Card */}
        <div className="p-5 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-mono uppercase tracking-wider text-zinc-500">
              TDS Solids
            </span>
            <div className="p-1.5 rounded-md bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300">
              <Zap className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-3 flex items-baseline gap-2">
            <span className="text-3xl font-mono font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
              {latestReadings?.tds?.value != null ? `${latestReadings.tds.value.toFixed(0)} ppm` : "--"}
            </span>
            {latestReadings?.tds?.is_stale && (
              <span className="text-xs text-amber-600 font-medium">(Stale)</span>
            )}
          </div>
          <div className="mt-3 flex items-center justify-between text-[11px] text-zinc-500 border-t border-zinc-100 dark:border-zinc-800/80 pt-2.5">
            <span>Source: {latestReadings?.tds?.data_source ?? "Manual Input"}</span>
            <span className="font-mono">{latestReadings?.tds ? `${latestReadings.tds.age_seconds}s ago` : "--"}</span>
          </div>
        </div>
      </div>

      {/* 5-Stage Multi-Stage Anomaly Detection Pipeline Architecture */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl p-6 shadow-xs">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-zinc-700 dark:text-zinc-300" />
              5-Stage Multi-Tier Online Anomaly Detection Pipeline
            </h2>
            <p className="text-xs text-zinc-500">
              Immediate physical boundary checking from Reading 1, temporal rate tracking from Reading 2, to 3D Half-Space Trees.
            </p>
          </div>
          <button
            onClick={() => onNavigate("thresholds")}
            className="text-xs font-medium text-zinc-700 dark:text-zinc-300 hover:text-zinc-900 dark:hover:text-zinc-100 flex items-center gap-1 transition"
          >
            Configure Thresholds <ArrowRight className="w-3.5 h-3.5" />
          </button>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-5 gap-3.5">
          {/* Stage 1 */}
          <div className="p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono uppercase text-zinc-400">Stage 1</span>
              {getStageBadge(stageReadiness?.stage_1_thresholds.readiness)}
            </div>
            <h3 className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
              Operating Bounds
            </h3>
            <p className="text-[11px] text-zinc-500 mt-1 leading-snug">
              Immediate evaluation of physical boundaries from 1st reading.
            </p>
          </div>

          {/* Stage 2 */}
          <div className="p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono uppercase text-zinc-400">Stage 2</span>
              {getStageBadge(stageReadiness?.stage_2_rate_of_change.readiness)}
            </div>
            <h3 className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
              Rate of Change
            </h3>
            <p className="text-[11px] text-zinc-500 mt-1 leading-snug">
              Calculates &Delta;v/&Delta;t per second from 2nd reading onward.
            </p>
          </div>

          {/* Stage 3 */}
          <div className="p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono uppercase text-zinc-400">Stage 3</span>
              {getStageBadge(stageReadiness?.stage_3_statistical_baseline.readiness)}
            </div>
            <h3 className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
              Statistical Baseline
            </h3>
            <p className="text-[11px] text-zinc-500 mt-1 leading-snug">
              Accumulates normal baseline medians (30 valid samples).
            </p>
          </div>

          {/* Stage 4 */}
          <div className="p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono uppercase text-zinc-400">Stage 4</span>
              {getStageBadge(stageReadiness?.stage_4_robust_zscore.readiness)}
            </div>
            <h3 className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
              Median + MAD
            </h3>
            <p className="text-[11px] text-zinc-500 mt-1 leading-snug">
              Robust online Z-score without distortion from outliers.
            </p>
          </div>

          {/* Stage 5 */}
          <div className="p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800 bg-zinc-50/50 dark:bg-zinc-800/30">
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] font-mono uppercase text-zinc-400">Stage 5</span>
              {getStageBadge(stageReadiness?.stage_5_half_space_trees.readiness)}
            </div>
            <h3 className="text-xs font-semibold text-zinc-800 dark:text-zinc-200">
              Multivariate HST
            </h3>
            <p className="text-[11px] text-zinc-500 mt-1 leading-snug">
              3D + pairwise space partitioning with QuantileFilter learning.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
