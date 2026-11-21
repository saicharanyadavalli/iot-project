"use client";

import React, { useEffect, useState } from "react";
import { AlertTriangle, ShieldAlert, RefreshCw, Filter, Clock } from "lucide-react";
import { api } from "@/lib/api";
import { AnomalyEventRecord } from "@/types/api";

interface AnomalyTabProps {
  refreshIntervalSeconds?: number;
}

export const AnomalyTab: React.FC<AnomalyTabProps> = ({ refreshIntervalSeconds = 5 }) => {
  const [events, setEvents] = useState<AnomalyEventRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [severityFilter, setSeverityFilter] = useState<string>("ALL");
  const [selectedEvent, setSelectedEvent] = useState<AnomalyEventRecord | null>(null);

  const loadAnomalies = async () => {
    try {
      setLoading(true);
      const res = await api.getAnomalyHistory(100);
      setEvents(res || []);
    } catch (err) {
      console.error("Failed to load anomaly history:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadAnomalies();
    const intervalMs = Math.max(2, Math.min(refreshIntervalSeconds, 60)) * 1000;
    const timer = setInterval(loadAnomalies, intervalMs);
    return () => clearInterval(timer);
  }, [refreshIntervalSeconds]);

  const filteredEvents =
    severityFilter === "ALL"
      ? events
      : events.filter((e) => e.severity === severityFilter);

  const getSeverityBadge = (severity: string) => {
    switch (severity) {
      case "CRITICAL":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-extrabold bg-rose-100 text-rose-800 dark:bg-rose-950/80 dark:text-rose-300 border border-rose-300 dark:border-rose-800">
            CRITICAL
          </span>
        );
      case "HIGH":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-orange-100 text-orange-800 dark:bg-orange-950/80 dark:text-orange-300 border border-orange-300 dark:border-orange-800">
            HIGH
          </span>
        );
      case "MEDIUM":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-amber-100 text-amber-800 dark:bg-amber-950/80 dark:text-amber-300 border border-amber-300 dark:border-amber-800">
            MEDIUM
          </span>
        );
      case "LOW":
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-100 text-blue-800 dark:bg-blue-950/80 dark:text-blue-300 border border-blue-300 dark:border-blue-800">
            LOW
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[11px] font-medium bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300">
            {severity}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-5 rounded-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-sm flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-rose-500/10 text-rose-600">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
              Detected Anomaly Events &amp; Audit Trail
            </h2>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Historical record of all rejected anomalous observations across the 5 detection stages.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5 bg-slate-100 dark:bg-slate-800 px-3 py-1.5 rounded-lg border border-slate-200 dark:border-slate-700 text-xs">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <select
              value={severityFilter}
              onChange={(e) => setSeverityFilter(e.target.value)}
              className="bg-transparent text-slate-700 dark:text-slate-300 font-medium focus:outline-none"
            >
              <option value="ALL">All Severities</option>
              <option value="CRITICAL">Critical Only</option>
              <option value="HIGH">High Only</option>
              <option value="MEDIUM">Medium Only</option>
              <option value="LOW">Low Only</option>
            </select>
          </div>

          <button
            onClick={loadAnomalies}
            disabled={loading}
            className="p-2 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 text-slate-600 dark:text-slate-300"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Main Table */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl shadow-sm overflow-hidden">
        {loading && events.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <RefreshCw className="w-6 h-6 animate-spin mx-auto text-blue-500 mb-2" />
            Loading anomaly events...
          </div>
        ) : filteredEvents.length === 0 ? (
          <div className="p-12 text-center text-slate-400">
            <AlertTriangle className="w-8 h-8 text-slate-300 dark:text-slate-600 mx-auto mb-2" />
            No anomaly events found matching current criteria.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-slate-50 dark:bg-slate-800/50 border-b border-slate-200 dark:border-slate-800 text-slate-500 font-semibold uppercase tracking-wider">
                <tr>
                  <th className="py-3 px-4">Timestamp</th>
                  <th className="py-3 px-4">Severity</th>
                  <th className="py-3 px-4">Classification</th>
                  <th className="py-3 px-4">Temp (°C)</th>
                  <th className="py-3 px-4">pH</th>
                  <th className="py-3 px-4">TDS (ppm)</th>
                  <th className="py-3 px-4">Score / Threshold</th>
                  <th className="py-3 px-4">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-800 text-slate-700 dark:text-slate-300">
                {filteredEvents.map((evt) => (
                  <tr
                    key={evt.id}
                    className="hover:bg-slate-50 dark:hover:bg-slate-800/40 transition"
                  >
                    <td className="py-3 px-4 font-mono text-[11px] text-slate-500 whitespace-nowrap">
                      {new Date(evt.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      {getSeverityBadge(evt.severity)}
                    </td>
                    <td className="py-3 px-4 font-medium max-w-xs truncate" title={evt.classification}>
                      {evt.classification}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold">
                      {evt.temperature != null ? `${evt.temperature.toFixed(1)}°C` : "--"}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold">
                      {evt.ph != null ? evt.ph.toFixed(2) : "--"}
                    </td>
                    <td className="py-3 px-4 font-mono font-semibold">
                      {evt.tds != null ? `${evt.tds.toFixed(0)}` : "--"}
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap font-mono text-[11px]">
                      <span className="font-bold text-rose-600 dark:text-rose-400">
                        {evt.primary_score.toFixed(4)}
                      </span>
                      <span className="text-slate-400 mx-1">/</span>
                      <span className="text-slate-500">
                        {evt.adaptive_threshold.toFixed(4)}
                      </span>
                    </td>
                    <td className="py-3 px-4 whitespace-nowrap">
                      <button
                        onClick={() => setSelectedEvent(evt)}
                        className="text-blue-600 hover:text-blue-800 dark:text-blue-400 font-semibold underline text-[11px]"
                      >
                        Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Modal Inspector for Details */}
      {selectedEvent && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-3">
              <h3 className="font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-rose-500" />
                Event #{selectedEvent.id} Breakdown
              </h3>
              <button
                onClick={() => setSelectedEvent(null)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-lg leading-none"
              >
                &times;
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500">Classification:</span>
                <span className="font-semibold text-slate-800 dark:text-slate-200 text-right">
                  {selectedEvent.classification}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500">Severity Level:</span>
                <div>{getSeverityBadge(selectedEvent.severity)}</div>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500">Timestamp:</span>
                <span className="font-mono text-slate-700 dark:text-slate-300">
                  {new Date(selectedEvent.timestamp).toISOString()}
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500">Coordinates:</span>
                <span className="font-mono font-semibold text-slate-800 dark:text-slate-200">
                  Temp: {selectedEvent.temperature ?? "--"}°C | pH: {selectedEvent.ph ?? "--"} | TDS:{" "}
                  {selectedEvent.tds ?? "--"} ppm
                </span>
              </div>
              <div className="flex justify-between py-1 border-b border-slate-100 dark:border-slate-800">
                <span className="text-slate-500">ML Primary Score:</span>
                <span className="font-mono font-bold text-rose-600">
                  {selectedEvent.primary_score} (Threshold: {selectedEvent.adaptive_threshold})
                </span>
              </div>
              {selectedEvent.details && (
                <div className="mt-2">
                  <span className="text-slate-500 block mb-1">Raw Payload Details:</span>
                  <pre className="p-3 rounded-lg bg-slate-100 dark:bg-slate-800 text-[10px] font-mono overflow-x-auto text-slate-700 dark:text-slate-300">
                    {selectedEvent.details}
                  </pre>
                </div>
              )}
            </div>

            <div className="pt-2 flex justify-end">
              <button
                onClick={() => setSelectedEvent(null)}
                className="px-4 py-2 bg-slate-100 dark:bg-slate-800 hover:bg-slate-200 dark:hover:bg-slate-700 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-300"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
