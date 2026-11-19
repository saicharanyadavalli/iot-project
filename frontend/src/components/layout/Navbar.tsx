"use client";

import React from "react";
import { Activity, Cpu, RefreshCw, Radio } from "lucide-react";
import { WebSocketStatus } from "@/lib/useWebSocket";
import { SystemStatus } from "@/types/api";

interface NavbarProps {
  wsStatus: WebSocketStatus;
  systemStatus: SystemStatus | null;
  onRefresh: () => void;
  isRefreshing: boolean;
}

export const Navbar: React.FC<NavbarProps> = ({
  wsStatus,
  systemStatus,
  onRefresh,
  isRefreshing,
}) => {
  const getStatusBadge = () => {
    switch (wsStatus) {
      case "CONNECTED":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-emerald-50 text-emerald-700 dark:bg-emerald-950/40 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800/60">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Live WS Connected
          </span>
        );
      case "CONNECTING":
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-amber-50 text-amber-700 dark:bg-amber-950/40 dark:text-amber-400 border border-amber-200 dark:border-amber-800/60">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping" />
            Connecting...
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium bg-rose-50 text-rose-700 dark:bg-rose-950/40 dark:text-rose-400 border border-rose-200 dark:border-rose-800/60">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
            Disconnected
          </span>
        );
    }
  };

  return (
    <header className="h-16 border-b border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900 sticky top-0 z-40 px-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <div className="w-9 h-9 rounded-lg bg-zinc-900 text-zinc-100 dark:bg-zinc-100 dark:text-zinc-900 flex items-center justify-center font-bold shadow-xs">
          <Activity className="w-4 h-4" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="font-semibold text-zinc-900 dark:text-zinc-100 text-base leading-tight">
              Adaptive IoT Water Quality Monitor
            </h1>
            <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700">
              River HST
            </span>
          </div>
          <p className="text-xs text-zinc-500 dark:text-zinc-400">
            Multivariate Online Anomaly Detection &amp; Dynamic Hardware Telemetry
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3">
        {/* Hardware Status */}
        <div className="hidden md:flex items-center gap-2 text-xs text-zinc-600 dark:text-zinc-300 bg-zinc-100 dark:bg-zinc-800/70 px-3 py-1.5 rounded-lg border border-zinc-200 dark:border-zinc-700/80">
          <Cpu className="w-3.5 h-3.5 text-zinc-500" />
          <span>Interval:</span>
          <span className="font-mono font-semibold text-zinc-800 dark:text-zinc-200">
            {systemStatus?.sampling_interval.active_interval_seconds ?? 5}s
          </span>
          <span className="text-zinc-300 dark:text-zinc-600">|</span>
          <Radio className="w-3.5 h-3.5 text-zinc-500" />
          <span>RF:</span>
          <span className="font-mono font-semibold text-zinc-800 dark:text-zinc-200">
            {systemStatus?.wireless_profile ?? "BALANCED"}
          </span>
        </div>

        {/* Live WS Badge */}
        {getStatusBadge()}

        {/* Refresh button */}
        <button
          onClick={onRefresh}
          disabled={isRefreshing}
          className="p-2 text-zinc-500 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800 transition"
          title="Refresh telemetry"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? "animate-spin" : ""}`} />
        </button>
      </div>
    </header>
  );
};
