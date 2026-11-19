"use client";

import React, { useState } from "react";
import { PenTool, CheckCircle, AlertCircle, Droplet, Zap, Send } from "lucide-react";
import { api } from "@/lib/api";

interface ManualInputTabProps {
  onSubmitted?: () => void;
}

export const ManualInputTab: React.FC<ManualInputTabProps> = ({ onSubmitted }) => {
  const [ph, setPh] = useState<string>("7.20");
  const [tds, setTds] = useState<string>("250.0");
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setFeedback(null);

    const phNum = parseFloat(ph);
    const tdsNum = parseFloat(tds);

    if (isNaN(phNum) || phNum < 0 || phNum > 14) {
      setError("pH must be a valid number between 0.00 and 14.00");
      return;
    }

    if (isNaN(tdsNum) || tdsNum < 0 || tdsNum > 5000) {
      setError("TDS must be a valid number between 0 and 5,000 ppm");
      return;
    }

    try {
      setSubmitting(true);
      const res = await api.submitManualReading(phNum, tdsNum);
      setFeedback(res);
      if (onSubmitted) onSubmitted();
    } catch (err: any) {
      setError(err.message || "Failed to submit manual reading");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      {/* Header Card */}
      <div className="p-5 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs">
        <div className="flex items-center gap-3">
          <div className="p-2.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-700">
            <PenTool className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Manual Sensor Ingestion (pH &amp; TDS)
            </h2>
            <p className="text-xs text-zinc-500">
              Submit laboratory probe measurements. Ingested readings pair directly with the latest live ESP32
              temperature in the Timestamp Synchronizer.
            </p>
          </div>
        </div>
      </div>

      {/* Form */}
      <div className="p-6 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs space-y-5">
        {error && (
          <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 flex items-center gap-2 text-xs text-rose-700 dark:text-rose-300">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-5">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {/* pH Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 flex items-center gap-1.5">
                <Droplet className="w-3.5 h-3.5 text-zinc-500" />
                pH Measurement (0.00 &ndash; 14.00)
              </label>
              <input
                type="number"
                step="0.01"
                min="0"
                max="14"
                value={ph}
                onChange={(e) => setPh(e.target.value)}
                required
                className="w-full px-3.5 py-2.5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-zinc-900"
                placeholder="7.20"
              />
              <span className="text-[11px] text-zinc-400">
                Neutral: 7.00. Potable range: 6.50 &ndash; 8.50.
              </span>
            </div>

            {/* TDS Input */}
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-zinc-500" />
                TDS Measurement (ppm / mg/L)
              </label>
              <input
                type="number"
                step="1"
                min="0"
                max="5000"
                value={tds}
                onChange={(e) => setTds(e.target.value)}
                required
                className="w-full px-3.5 py-2.5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-zinc-900"
                placeholder="250"
              />
              <span className="text-[11px] text-zinc-400">
                Freshwater: 50 &ndash; 300 ppm. WHO acceptable limit: &le; 600 ppm.
              </span>
            </div>
          </div>

          <div className="pt-2 flex justify-end">
            <button
              type="submit"
              disabled={submitting}
              className="px-5 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 font-medium text-xs shadow-xs flex items-center gap-2 transition disabled:opacity-50"
            >
              <Send className="w-3.5 h-3.5" />
              {submitting ? "Ingesting & Evaluating..." : "Submit to Pipeline"}
            </button>
          </div>
        </form>
      </div>

      {/* Immediate Evaluation Result */}
      {feedback && (
        <div className="p-5 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs space-y-3">
          <div className="flex items-center gap-2 text-emerald-600 font-semibold text-xs">
            <CheckCircle className="w-4 h-4" />
            <span>Measurement Synchronized &amp; Processed</span>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs bg-zinc-50 dark:bg-zinc-800/40 p-3.5 rounded-lg border border-zinc-200 dark:border-zinc-800">
            <div>
              <span className="text-zinc-400 block text-[10px] font-mono uppercase">Anomaly Status</span>
              <span
                className={`font-bold ${
                  feedback.is_anomaly ? "text-rose-600" : "text-emerald-600"
                }`}
              >
                {feedback.is_anomaly ? "ANOMALY DETECTED" : "NORMAL"}
              </span>
            </div>

            <div>
              <span className="text-zinc-400 block text-[10px] font-mono uppercase">Severity</span>
              <span className="font-semibold text-zinc-800 dark:text-zinc-200">
                {feedback.severity}
              </span>
            </div>

            <div>
              <span className="text-zinc-400 block text-[10px] font-mono uppercase">ML Primary Score</span>
              <span className="font-mono font-bold text-zinc-800 dark:text-zinc-200">
                {feedback.primary_score?.toFixed(4) ?? "0.0000"}
              </span>
            </div>

            <div>
              <span className="text-zinc-400 block text-[10px] font-mono uppercase">Adaptive Threshold</span>
              <span className="font-mono text-zinc-600 dark:text-zinc-400">
                {feedback.adaptive_threshold?.toFixed(4) ?? "0.0000"}
              </span>
            </div>
          </div>

          <div className="text-xs text-zinc-600 dark:text-zinc-400">
            <span className="font-semibold">Classification:</span> {feedback.classification}
          </div>
        </div>
      )}
    </div>
  );
};
