"use client";

import React, { useState, useEffect } from "react";
import { Sliders, Save, CheckCircle2, History, AlertCircle, Sparkles } from "lucide-react";
import { api } from "@/lib/api";
import { ThresholdConfig } from "@/types/api";

interface ThresholdTabProps {
  currentConfig: ThresholdConfig | null;
  onSaved?: () => void;
}

export const ThresholdTab: React.FC<ThresholdTabProps> = ({ currentConfig, onSaved }) => {
  const [tempMin, setTempMin] = useState<number>(currentConfig?.temp_min ?? 10.0);
  const [tempMax, setTempMax] = useState<number>(currentConfig?.temp_max ?? 38.0);
  const [phMin, setPhMin] = useState<number>(currentConfig?.ph_min ?? 6.5);
  const [phMax, setPhMax] = useState<number>(currentConfig?.ph_max ?? 8.5);
  const [tdsMin, setTdsMin] = useState<number>(currentConfig?.tds_min ?? 50.0);
  const [tdsMax, setTdsMax] = useState<number>(currentConfig?.tds_max ?? 600.0);
  const [notes, setNotes] = useState<string>("");

  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [history, setHistory] = useState<ThresholdConfig[]>([]);

  useEffect(() => {
    if (currentConfig) {
      setTempMin(currentConfig.temp_min);
      setTempMax(currentConfig.temp_max);
      setPhMin(currentConfig.ph_min);
      setPhMax(currentConfig.ph_max);
      setTdsMin(currentConfig.tds_min);
      setTdsMax(currentConfig.tds_max);
    }
  }, [currentConfig]);

  const loadHistory = async () => {
    try {
      const h = await api.getThresholdHistory("default", 15);
      setHistory(h || []);
    } catch (e) {
      console.error("Failed to load threshold history:", e);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  const applyPreset = (preset: {
    tempMin: number;
    tempMax: number;
    phMin: number;
    phMax: number;
    tdsMin: number;
    tdsMax: number;
    name: string;
  }) => {
    setTempMin(preset.tempMin);
    setTempMax(preset.tempMax);
    setPhMin(preset.phMin);
    setPhMax(preset.phMax);
    setTdsMin(preset.tdsMin);
    setTdsMax(preset.tdsMax);
    setNotes(`Applied ${preset.name} preset`);
    setSuccessMsg(`Preset applied: ${preset.name}`);
    setTimeout(() => setSuccessMsg(null), 3000);
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setSuccessMsg(null);

    if (tempMin >= tempMax) {
      setErrorMsg("Temperature Min must be strictly less than Max");
      return;
    }
    if (phMin >= phMax) {
      setErrorMsg("pH Min must be strictly less than Max");
      return;
    }
    if (tdsMin >= tdsMax) {
      setErrorMsg("TDS Min must be strictly less than Max");
      return;
    }

    try {
      setSaving(true);
      const res = await api.updateThresholds({
        temp_min: tempMin,
        temp_max: tempMax,
        ph_min: phMin,
        ph_max: phMax,
        tds_min: tdsMin,
        tds_max: tdsMax,
        installation_id: "default",
        notes: notes || "User configured safety boundaries",
      });

      setSuccessMsg(`Threshold configuration version v${res.version} activated successfully!`);
      loadHistory();
      if (onSaved) onSaved();
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to update thresholds");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="p-5 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-700">
            <Sliders className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              User-Defined Operating Safety Thresholds (Stage 1)
            </h2>
            <p className="text-xs text-zinc-500">
              Strict physical safety limits evaluated immediately on Reading 1. Triggers CRITICAL_THRESHOLD_ALERT
              and rejects observation from polluting machine learning baseline.
            </p>
          </div>
        </div>
        <div className="text-xs font-mono font-semibold px-2.5 py-1 rounded-md bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-700">
          Active: v{currentConfig?.version ?? 1}
        </div>
      </div>

      {/* Presets Bar */}
      <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-800">
        <div className="flex items-center gap-2 text-xs font-semibold text-zinc-700 dark:text-zinc-300 mb-2.5">
          <Sparkles className="w-3.5 h-3.5 text-zinc-500" />
          Water Application Presets:
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() =>
              applyPreset({
                tempMin: 10,
                tempMax: 30,
                phMin: 6.5,
                phMax: 8.5,
                tdsMin: 50,
                tdsMax: 500,
                name: "Potable / Drinking Water",
              })
            }
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 hover:border-zinc-900 dark:hover:border-zinc-100 transition"
          >
            Potable / Drinking Water
          </button>
          <button
            type="button"
            onClick={() =>
              applyPreset({
                tempMin: 18,
                tempMax: 28,
                phMin: 6.8,
                phMax: 8.2,
                tdsMin: 100,
                tdsMax: 800,
                name: "Aquaponics / Fisheries",
              })
            }
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 hover:border-zinc-900 dark:hover:border-zinc-100 transition"
          >
            Aquaponics / Fisheries
          </button>
          <button
            type="button"
            onClick={() =>
              applyPreset({
                tempMin: 15,
                tempMax: 45,
                phMin: 7.0,
                phMax: 9.0,
                tdsMin: 200,
                tdsMax: 1200,
                name: "Industrial Cooling Tower",
              })
            }
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 hover:border-zinc-900 dark:hover:border-zinc-100 transition"
          >
            Industrial Cooling
          </button>
          <button
            type="button"
            onClick={() =>
              applyPreset({
                tempMin: 20,
                tempMax: 25,
                phMin: 6.9,
                phMax: 7.1,
                tdsMin: 50,
                tdsMax: 200,
                name: "Strict Laboratory Standard",
              })
            }
            className="px-3 py-1.5 rounded-lg text-xs font-medium bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-700 hover:border-zinc-900 dark:hover:border-zinc-100 transition"
          >
            Strict Laboratory
          </button>
        </div>
      </div>

      {/* Main Form */}
      <form onSubmit={handleSave} className="p-6 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs space-y-6">
        {errorMsg && (
          <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 flex items-center gap-2 text-xs text-rose-700 dark:text-rose-300">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{errorMsg}</span>
          </div>
        )}
        {successMsg && (
          <div className="p-3 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 flex items-center gap-2 text-xs text-emerald-700 dark:text-emerald-300">
            <CheckCircle2 className="w-4 h-4 shrink-0" />
            <span>{successMsg}</span>
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Temperature Bounds */}
          <div className="p-4 rounded-lg border border-zinc-200 dark:border-zinc-800 space-y-3">
            <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-500">
              Temperature Limits (°C)
            </h3>
            <div className="space-y-2">
              <div>
                <label className="text-[11px] font-medium text-zinc-500">Lower Bound (Min)</label>
                <input
                  type="number"
                  step="0.5"
                  value={tempMin}
                  onChange={(e) => setTempMin(Number(e.target.value))}
                  required
                  className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-zinc-900"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-zinc-500">Upper Bound (Max)</label>
                <input
                  type="number"
                  step="0.5"
                  value={tempMax}
                  onChange={(e) => setTempMax(Number(e.target.value))}
                  required
                  className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-zinc-900"
                />
              </div>
            </div>
          </div>

          {/* pH Bounds */}
          <div className="p-4 rounded-lg border border-zinc-200 dark:border-zinc-800 space-y-3">
            <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-500">
              pH Limits (0 &ndash; 14)
            </h3>
            <div className="space-y-2">
              <div>
                <label className="text-[11px] font-medium text-zinc-500">Lower Bound (Min)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="14"
                  value={phMin}
                  onChange={(e) => setPhMin(Number(e.target.value))}
                  required
                  className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-zinc-900"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-zinc-500">Upper Bound (Max)</label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  max="14"
                  value={phMax}
                  onChange={(e) => setPhMax(Number(e.target.value))}
                  required
                  className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-zinc-900"
                />
              </div>
            </div>
          </div>

          {/* TDS Bounds */}
          <div className="p-4 rounded-lg border border-zinc-200 dark:border-zinc-800 space-y-3">
            <h3 className="text-xs font-mono uppercase tracking-wider text-zinc-500">
              TDS Limits (ppm)
            </h3>
            <div className="space-y-2">
              <div>
                <label className="text-[11px] font-medium text-zinc-500">Lower Bound (Min)</label>
                <input
                  type="number"
                  step="10"
                  value={tdsMin}
                  onChange={(e) => setTdsMin(Number(e.target.value))}
                  required
                  className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-zinc-900"
                />
              </div>
              <div>
                <label className="text-[11px] font-medium text-zinc-500">Upper Bound (Max)</label>
                <input
                  type="number"
                  step="10"
                  value={tdsMax}
                  onChange={(e) => setTdsMax(Number(e.target.value))}
                  required
                  className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-zinc-900"
                />
              </div>
            </div>
          </div>
        </div>

        <div>
          <label className="text-xs font-medium text-zinc-500 block mb-1">Configuration Change Notes / Audit Reason</label>
          <input
            type="text"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="e.g., Seasonal aquaculture threshold adjustment"
            className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs focus:outline-none focus:ring-1 focus:ring-zinc-900"
          />
        </div>

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={saving}
            className="px-5 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium text-xs shadow-xs flex items-center gap-2 transition disabled:opacity-50"
          >
            <Save className="w-3.5 h-3.5" />
            {saving ? "Saving Configuration..." : "Save Operating Thresholds"}
          </button>
        </div>
      </form>

      {/* Audit History Table */}
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-xl shadow-xs p-5 space-y-3">
        <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 text-xs flex items-center gap-2">
          <History className="w-3.5 h-3.5 text-zinc-500" />
          Configuration Audit History
        </h3>

        {history.length === 0 ? (
          <p className="text-xs text-zinc-400">No previous threshold version records logged yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead className="bg-zinc-50 dark:bg-zinc-800/50 border-b border-zinc-200 dark:border-zinc-800 text-zinc-500 font-mono uppercase">
                <tr>
                  <th className="py-2.5 px-3">Ver</th>
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Temp Range</th>
                  <th className="py-2.5 px-3">pH Range</th>
                  <th className="py-2.5 px-3">TDS Range</th>
                  <th className="py-2.5 px-3">Notes</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-100 dark:divide-zinc-800">
                {history.map((h) => (
                  <tr key={h.id || h.version} className="hover:bg-zinc-50 dark:hover:bg-zinc-800/30">
                    <td className="py-2.5 px-3 font-mono font-bold text-zinc-900 dark:text-zinc-100">v{h.version}</td>
                    <td className="py-2.5 px-3 text-zinc-500 font-mono text-[11px]">
                      {h.timestamp ? new Date(h.timestamp).toLocaleString() : "--"}
                    </td>
                    <td className="py-2.5 px-3 font-mono">
                      {h.temp_min}°C &ndash; {h.temp_max}°C
                    </td>
                    <td className="py-2.5 px-3 font-mono">
                      {h.ph_min} &ndash; {h.ph_max}
                    </td>
                    <td className="py-2.5 px-3 font-mono">
                      {h.tds_min} &ndash; {h.tds_max} ppm
                    </td>
                    <td className="py-2.5 px-3 text-zinc-600 dark:text-zinc-400 italic">
                      {h.notes || "Standard configuration"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
