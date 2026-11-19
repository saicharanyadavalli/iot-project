"use client";

import React from "react";
import {
  LayoutDashboard,
  LineChart,
  Box,
  AlertTriangle,
  PenTool,
  Sliders,
  Radio,
  FlaskConical,
} from "lucide-react";

export type TabKey =
  | "overview"
  | "live"
  | "multivariate"
  | "anomalies"
  | "manual"
  | "thresholds"
  | "hardware"
  | "simulation";

interface SidebarProps {
  activeTab: TabKey;
  onTabChange: (tab: TabKey) => void;
  anomalyCount: number;
}

export const Sidebar: React.FC<SidebarProps> = ({
  activeTab,
  onTabChange,
  anomalyCount,
}) => {
  const navItems = [
    {
      id: "overview" as TabKey,
      label: "System Overview",
      icon: LayoutDashboard,
      badge: null,
    },
    {
      id: "live" as TabKey,
      label: "Live Telemetry",
      icon: LineChart,
      badge: null,
    },
    {
      id: "multivariate" as TabKey,
      label: "3D State Space",
      icon: Box,
      badge: "HST",
    },
    {
      id: "anomalies" as TabKey,
      label: "Anomaly Events",
      icon: AlertTriangle,
      badge: anomalyCount > 0 ? anomalyCount : null,
      badgeVariant: "danger",
    },
    {
      id: "manual" as TabKey,
      label: "Manual Input",
      icon: PenTool,
      badge: null,
    },
    {
      id: "thresholds" as TabKey,
      label: "Safety Thresholds",
      icon: Sliders,
      badge: null,
    },
    {
      id: "hardware" as TabKey,
      label: "Hardware & Ports",
      icon: Radio,
      badge: null,
    },
    {
      id: "simulation" as TabKey,
      label: "Scenario Lab",
      icon: FlaskConical,
      badge: "1–12",
    },
  ];

  return (
    <aside className="w-64 border-r border-zinc-200 dark:border-zinc-800 bg-zinc-50/60 dark:bg-zinc-900/40 flex flex-col justify-between p-4">
      <div className="space-y-1">
        <div className="px-3 py-2 text-[10px] font-mono uppercase tracking-wider text-zinc-400">
          Navigation
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg font-medium text-xs transition ${
                isActive
                  ? "bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900 shadow-xs"
                  : "text-zinc-600 hover:text-zinc-900 hover:bg-zinc-200/50 dark:text-zinc-400 dark:hover:text-zinc-200 dark:hover:bg-zinc-800/50"
              }`}
            >
              <div className="flex items-center gap-2.5">
                <Icon className={`w-4 h-4 ${isActive ? "text-white dark:text-zinc-900" : "text-zinc-400"}`} />
                <span>{item.label}</span>
              </div>
              {item.badge !== null && (
                <span
                  className={`text-[10px] font-mono font-semibold px-1.5 py-0.5 rounded ${
                    isActive
                      ? "bg-zinc-700 text-white dark:bg-zinc-300 dark:text-zinc-900"
                      : item.badgeVariant === "danger"
                      ? "bg-rose-100 text-rose-700 dark:bg-rose-950/80 dark:text-rose-300"
                      : "bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300"
                  }`}
                >
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Footer Info */}
      <div className="pt-4 border-t border-zinc-200 dark:border-zinc-800 text-[11px] font-mono text-zinc-400 space-y-1">
        <div className="flex justify-between">
          <span>Engine:</span>
          <span className="font-semibold text-zinc-600 dark:text-zinc-300">River ML</span>
        </div>
        <div className="flex justify-between">
          <span>Radio:</span>
          <span className="font-semibold text-zinc-600 dark:text-zinc-300">nRF24L01+</span>
        </div>
        <div className="flex justify-between">
          <span>Database:</span>
          <span className="font-semibold text-zinc-600 dark:text-zinc-300">SQLite WAL</span>
        </div>
      </div>
    </aside>
  );
};
