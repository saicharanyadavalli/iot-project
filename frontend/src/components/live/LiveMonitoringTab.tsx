"use client";

import React, { useEffect, useState } from "react";
import { LineChart as LineChartIcon, RefreshCw, AlertCircle } from "lucide-react";
import { api } from "@/lib/api";
import { TimeSeriesPoint, ThresholdConfig } from "@/types/api";

interface LiveMonitoringTabProps {
  thresholds: ThresholdConfig | null;
}

export const LiveMonitoringTab: React.FC<LiveMonitoringTabProps> = ({ thresholds }) => {
  const [data, setData] = useState<TimeSeriesPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [windowMinutes, setWindowMinutes] = useState<number>(60);

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await api.getTimeSeries(windowMinutes, 200);
      setData(res.data || []);
    } catch (err) {
      console.error("Failed to load time series:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [windowMinutes]);

  const recentTemps = data.filter((d) => d.temperature !== null).slice(-30);
  const recentPhs = data.filter((d) => d.ph !== null).slice(-30);
  const recentTds = data.filter((d) => d.tds !== null).slice(-30);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-blue-500/10 text-blue-600">
              <LineChartIcon className="w-5 h-5" />
            </div>
            <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Real-Time Parameter Telemetry
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Streaming sensor observations with active physical safety boundary bands.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <select
            value={windowMinutes}
            onChange={(e) => setWindowMinutes(Number(e.target.value))}
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700 focus:outline-none"
          >
            <option value={15}>Last 15 minutes</option>
            <option value={30}>Last 30 minutes</option>
            <option value={60}>Last 1 hour</option>
            <option value={360}>Last 6 hours</option>
            <option value={1440}>Last 24 hours</option>
          </select>

          <button
            onClick={loadData}
            disabled={loading}
            className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* 3 Parameter Charts */}
      <div className="grid grid-cols-1 gap-6">
        {/* Temperature Stream */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-orange-600">
                Temperature (°C)
              </span>
              <span className="text-xs text-slate-400 ml-2">
                Safety Band: [{thresholds?.temp_min ?? 10}°C &ndash; {thresholds?.temp_max ?? 38}°C]
              </span>
            </div>
            <span className="text-sm font-extrabold text-slate-800 dark:text-slate-200">
              {recentTemps.length > 0
                ? `${recentTemps[recentTemps.length - 1].temperature?.toFixed(1)} °C`
                : "--"}
            </span>
          </div>

          <div className="h-40 flex items-end gap-1.5 pt-4 border-b border-l border-slate-200 dark:border-slate-700 px-2 relative">
            {/* Upper limit line */}
            <div className="absolute top-4 left-0 right-0 border-b border-dashed border-rose-400/60 flex justify-end pr-2 text-[10px] text-rose-500 font-bold">
              Max {thresholds?.temp_max ?? 38}°C
            </div>
            {/* Lower limit line */}
            <div className="absolute bottom-6 left-0 right-0 border-b border-dashed border-rose-400/60 flex justify-end pr-2 text-[10px] text-rose-500 font-bold">
              Min {thresholds?.temp_min ?? 10}°C
            </div>

            {recentTemps.map((pt, i) => {
              const val = pt.temperature || 0;
              const heightPct = Math.min(Math.max(((val - 5) / 45) * 100, 5), 100);
              const isViolating =
                thresholds && (val < thresholds.temp_min || val > thresholds.temp_max);

              return (
                <div
                  key={i}
                  className="flex-1 flex flex-col items-center group relative h-full justify-end"
                >
                  <div
                    style={{ height: `${heightPct}%` }}
                    className={`w-full rounded-t transition-all ${
                      isViolating
                        ? "bg-rose-500 shadow-sm shadow-rose-500/50"
                        : pt.is_anomaly
                        ? "bg-amber-500"
                        : "bg-orange-400/80 hover:bg-orange-500"
                    }`}
                  />
                  {/* Tooltip */}
                  <div className="absolute -top-8 bg-slate-900 text-white text-[10px] py-0.5 px-1.5 rounded opacity-0 group-hover:opacity-100 pointer-events-none transition whitespace-nowrap z-10">
                    {val.toFixed(1)}°C {pt.is_anomaly ? "(Anomaly)" : ""}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex justify-between text-[11px] text-slate-400 mt-2">
            <span>Oldest (Window)</span>
            <span>Latest Reading</span>
          </div>
        </div>

        {/* pH Stream */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-cyan-600">
                pH Level
              </span>
              <span className="text-xs text-slate-400 ml-2">
                Safety Band: [{thresholds?.ph_min ?? 6.5} &ndash; {thresholds?.ph_max ?? 8.5}]
              </span>
            </div>
            <span className="text-sm font-extrabold text-slate-800 dark:text-slate-200">
              {recentPhs.length > 0
                ? recentPhs[recentPhs.length - 1].ph?.toFixed(2)
                : "--"}
            </span>
          </div>

          <div className="h-40 flex items-end gap-1.5 pt-4 border-b border-l border-slate-200 dark:border-slate-700 px-2 relative">
            <div className="absolute top-4 left-0 right-0 border-b border-dashed border-rose-400/60 flex justify-end pr-2 text-[10px] text-rose-500 font-bold">
              Max {thresholds?.ph_max ?? 8.5}
            </div>
            <div className="absolute bottom-6 left-0 right-0 border-b border-dashed border-rose-400/60 flex justify-end pr-2 text-[10px] text-rose-500 font-bold">
              Min {thresholds?.ph_min ?? 6.5}
            </div>

            {recentPhs.map((pt, i) => {
              const val = pt.ph || 7;
              const heightPct = Math.min(Math.max((val / 14) * 100, 5), 100);
              const isViolating =
                thresholds && (val < thresholds.ph_min || val > thresholds.ph_max);

              return (
                <div
                  key={i}
                  className="flex-1 flex flex-col items-center group relative h-full justify-end"
                >
                  <div
                    style={{ height: `${heightPct}%` }}
                    className={`w-full rounded-t transition-all ${
                      isViolating
                        ? "bg-rose-500 shadow-sm shadow-rose-500/50"
                        : pt.is_anomaly
                        ? "bg-amber-500"
                        : "bg-cyan-500/80 hover:bg-cyan-600"
                    }`}
                  />
                  <div className="absolute -top-8 bg-slate-900 text-white text-[10px] py-0.5 px-1.5 rounded opacity-0 group-hover:opacity-100 pointer-events-none transition whitespace-nowrap z-10">
                    pH {val.toFixed(2)} {pt.is_anomaly ? "(Anomaly)" : ""}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex justify-between text-[11px] text-slate-400 mt-2">
            <span>Oldest (Window)</span>
            <span>Latest Reading</span>
          </div>
        </div>

        {/* TDS Stream */}
        <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm">
          <div className="flex items-center justify-between mb-3">
            <div>
              <span className="text-xs font-bold uppercase tracking-wider text-blue-600">
                TDS (ppm)
              </span>
              <span className="text-xs text-slate-400 ml-2">
                Safety Band: [{thresholds?.tds_min ?? 50} &ndash; {thresholds?.tds_max ?? 600} ppm]
              </span>
            </div>
            <span className="text-sm font-extrabold text-slate-800 dark:text-slate-200">
              {recentTds.length > 0
                ? `${recentTds[recentTds.length - 1].tds?.toFixed(0)} ppm`
                : "--"}
            </span>
          </div>

          <div className="h-40 flex items-end gap-1.5 pt-4 border-b border-l border-slate-200 dark:border-slate-700 px-2 relative">
            <div className="absolute top-4 left-0 right-0 border-b border-dashed border-rose-400/60 flex justify-end pr-2 text-[10px] text-rose-500 font-bold">
              Max {thresholds?.tds_max ?? 600} ppm
            </div>
            <div className="absolute bottom-6 left-0 right-0 border-b border-dashed border-rose-400/60 flex justify-end pr-2 text-[10px] text-rose-500 font-bold">
              Min {thresholds?.tds_min ?? 50} ppm
            </div>

            {recentTds.map((pt, i) => {
              const val = pt.tds || 250;
              const heightPct = Math.min(Math.max((val / 1000) * 100, 5), 100);
              const isViolating =
                thresholds && (val < thresholds.tds_min || val > thresholds.tds_max);

              return (
                <div
                  key={i}
                  className="flex-1 flex flex-col items-center group relative h-full justify-end"
                >
                  <div
                    style={{ height: `${heightPct}%` }}
                    className={`w-full rounded-t transition-all ${
                      isViolating
                        ? "bg-rose-500 shadow-sm shadow-rose-500/50"
                        : pt.is_anomaly
                        ? "bg-amber-500"
                        : "bg-blue-500/80 hover:bg-blue-600"
                    }`}
                  />
                  <div className="absolute -top-8 bg-slate-900 text-white text-[10px] py-0.5 px-1.5 rounded opacity-0 group-hover:opacity-100 pointer-events-none transition whitespace-nowrap z-10">
                    {val.toFixed(0)} ppm {pt.is_anomaly ? "(Anomaly)" : ""}
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex justify-between text-[11px] text-slate-400 mt-2">
            <span>Oldest (Window)</span>
            <span>Latest Reading</span>
          </div>
        </div>
      </div>
    </div>
  );
};
