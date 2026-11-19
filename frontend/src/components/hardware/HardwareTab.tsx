"use client";

import React, { useState, useEffect } from "react";
import {
  Radio,
  Cpu,
  Clock,
  CheckCircle2,
  AlertTriangle,
  Send,
  RefreshCw,
  Cable,
  Check,
  Search,
} from "lucide-react";
import { api } from "@/lib/api";
import { WirelessStatus, SamplingIntervalState, PortScanResponse, PortScanItem } from "@/types/api";

interface HardwareTabProps {
  samplingInterval: SamplingIntervalState | null;
  wirelessProfile: string | null;
  onUpdated?: () => void;
}

export const HardwareTab: React.FC<HardwareTabProps> = ({
  samplingInterval,
  wirelessProfile,
  onUpdated,
}) => {
  // Sampling Interval State
  const [activeInterval, setActiveInterval] = useState<number>(
    samplingInterval?.active_interval_seconds ?? 5
  );
  const [customInterval, setCustomInterval] = useState<string>("10");
  const [submittingInterval, setSubmittingInterval] = useState(false);
  const [intervalStatus, setIntervalStatus] = useState<any | null>(null);

  // Wireless RF State
  const [wirelessConfig, setWirelessConfig] = useState<WirelessStatus | null>(null);
  const [submittingProfile, setSubmittingProfile] = useState(false);
  const [profileResult, setProfileResult] = useState<any | null>(null);

  // Serial Port Auto-Detection State
  const [portData, setPortData] = useState<PortScanResponse | null>(null);
  const [scanningPorts, setScanningPorts] = useState(false);
  const [selectedNanoPort, setSelectedNanoPort] = useState<string>("COM12");
  const [selectedEsp32Port, setSelectedEsp32Port] = useState<string>("COM13");
  const [savingPorts, setSavingPorts] = useState(false);
  const [portSaveFeedback, setPortSaveFeedback] = useState<string | null>(null);

  useEffect(() => {
    if (samplingInterval) {
      setActiveInterval(samplingInterval.active_interval_seconds);
    }
  }, [samplingInterval]);

  const loadHardwareState = async () => {
    try {
      const [wCfg, pScan] = await Promise.all([
        api.getWirelessConfig().catch(() => null),
        api.scanPorts().catch(() => null),
      ]);
      if (wCfg) setWirelessConfig(wCfg);
      if (pScan) {
        setPortData(pScan);
        setSelectedNanoPort(pScan.active_nano_port);
        setSelectedEsp32Port(pScan.active_esp32_port);
      }
    } catch (e) {
      console.error("Failed to load hardware state:", e);
    }
  };

  useEffect(() => {
    loadHardwareState();
  }, []);

  const handleScanPorts = async () => {
    try {
      setScanningPorts(true);
      const res = await api.scanPorts();
      setPortData(res);
      setSelectedNanoPort(res.active_nano_port);
      setSelectedEsp32Port(res.active_esp32_port);
    } catch (err) {
      console.error("Port scan failed:", err);
    } finally {
      setScanningPorts(false);
    }
  };

  const handleSavePorts = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setSavingPorts(true);
      setPortSaveFeedback(null);
      const res = await api.updatePorts(selectedNanoPort, selectedEsp32Port);
      setPortSaveFeedback(
        `Ports updated: Nano (${res.nano_port}) [${res.nano_connected ? "Connected" : "Offline"}], ESP32 (${res.esp32_port}) [${res.esp32_connected ? "Connected" : "Offline"}]`
      );
      handleScanPorts();
      if (onUpdated) onUpdated();
    } catch (err: any) {
      setPortSaveFeedback(`Error: ${err.message || "Failed to update ports"}`);
    } finally {
      setSavingPorts(false);
    }
  };

  const handleApplyInterval = async (intervalSec: number) => {
    try {
      setSubmittingInterval(true);
      const res = await api.setSamplingInterval(intervalSec);
      setIntervalStatus(res);
      setActiveInterval(intervalSec);
      if (onUpdated) onUpdated();
    } catch (err: any) {
      setIntervalStatus({ error: err.message || "Failed to submit command" });
    } finally {
      setSubmittingInterval(false);
    }
  };

  const handleApplyProfile = async (profile: "SHORT" | "BALANCED" | "LONG") => {
    try {
      setSubmittingProfile(true);
      const res = await api.setWirelessProfile(profile);
      setProfileResult(res);
      const wCfg = await api.getWirelessConfig();
      setWirelessConfig(wCfg);
      if (onUpdated) onUpdated();
    } catch (err: any) {
      setProfileResult({ error_message: err.message || "Profile change failed" });
    } finally {
      setSubmittingProfile(false);
    }
  };

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case "APPLIED":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-emerald-50 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
            APPLIED &amp; CONFIRMED
          </span>
        );
      case "PENDING":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-bold bg-amber-50 text-amber-700 dark:bg-amber-950/60 dark:text-amber-400 border border-amber-200 dark:border-amber-800">
            PENDING DELIVERY
          </span>
        );
      case "DEVICE_OFFLINE":
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700">
            DEVICE OFFLINE (PENDING)
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] font-mono font-medium bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700">
            {status ?? "IDLE"}
          </span>
        );
    }
  };

  return (
    <div className="space-y-6">
      {/* 1. COM Port Auto-Detection & Assignment Panel */}
      <div className="p-6 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs space-y-5">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-700">
              <Cable className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                Serial COM Port Auto-Detection &amp; Device Mapping
              </h2>
              <p className="text-xs text-zinc-500">
                Detects connected USB serial hardware (Arduino Nano receiver and ESP32 transmitter) with automatic chip heuristics.
              </p>
            </div>
          </div>

          <button
            onClick={handleScanPorts}
            disabled={scanningPorts}
            className="px-3.5 py-1.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-800 dark:text-zinc-200 text-xs font-medium border border-zinc-200 dark:border-zinc-700 flex items-center gap-2 transition"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${scanningPorts ? "animate-spin" : ""}`} />
            {scanningPorts ? "Scanning Ports..." : "Scan COM Ports"}
          </button>
        </div>

        {/* Detected Ports Table */}
        <div className="border border-zinc-200 dark:border-zinc-800 rounded-lg overflow-hidden">
          <div className="bg-zinc-50 dark:bg-zinc-800/50 px-4 py-2 border-b border-zinc-200 dark:border-zinc-800 text-[11px] font-mono uppercase text-zinc-500 flex justify-between">
            <span>Detected System Serial Interfaces</span>
            <span>Total: {portData?.available_ports.length ?? 0} Ports</span>
          </div>

          {portData?.available_ports && portData.available_ports.length > 0 ? (
            <div className="divide-y divide-zinc-100 dark:divide-zinc-800 text-xs">
              {portData.available_ports.map((p) => (
                <div
                  key={p.device}
                  className="px-4 py-2.5 flex flex-col md:flex-row md:items-center justify-between gap-2 hover:bg-zinc-50 dark:hover:bg-zinc-800/40 transition"
                >
                  <div className="space-y-0.5">
                    <div className="flex items-center gap-2">
                      <span className="font-mono font-bold text-zinc-900 dark:text-zinc-100">
                        {p.device}
                      </span>
                      <span className="text-zinc-600 dark:text-zinc-400">{p.description}</span>
                      {p.is_active_nano && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900">
                          Active Nano (Rx)
                        </span>
                      )}
                      {p.is_active_esp32 && (
                        <span className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-zinc-900 text-white dark:bg-zinc-100 dark:text-zinc-900">
                          Active ESP32 (Tx)
                        </span>
                      )}
                    </div>
                    <div className="text-[10px] font-mono text-zinc-400 truncate max-w-xl">
                      HWID: {p.hwid}
                    </div>
                  </div>

                  <div className="flex items-center gap-2">
                    {p.suggested_role === "nano" && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-400 border border-emerald-200 dark:border-emerald-800">
                        Suggested: Arduino Nano
                      </span>
                    )}
                    {p.suggested_role === "esp32" && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700">
                        Suggested: ESP32
                      </span>
                    )}
                    {p.suggested_role === "bluetooth" && (
                      <span className="px-2 py-0.5 rounded text-[10px] font-mono text-zinc-400 bg-zinc-50 dark:bg-zinc-800/20">
                        Bluetooth Link
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-6 text-center text-xs text-zinc-400">
              No physical or virtual serial COM ports currently discovered. Connect boards via USB and click Scan.
            </div>
          )}
        </div>

        {/* Port Mapping Form */}
        <form onSubmit={handleSavePorts} className="pt-2 border-t border-zinc-100 dark:border-zinc-800 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 block mb-1.5">
                Arduino Nano Receiver Port (Telemetry Ingestion)
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={selectedNanoPort}
                  onChange={(e) => setSelectedNanoPort(e.target.value)}
                  placeholder="e.g., COM12"
                  className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-zinc-900 dark:focus:ring-zinc-100"
                />
                {portData?.available_ports && (
                  <select
                    onChange={(e) => e.target.value && setSelectedNanoPort(e.target.value)}
                    className="px-2 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-600 dark:text-zinc-300"
                    defaultValue=""
                  >
                    <option value="" disabled>Select Port</option>
                    {portData.available_ports.map((p) => (
                      <option key={p.device} value={p.device}>
                        {p.device} ({p.suggested_role})
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <span className="text-[10px] text-zinc-400 mt-1 block">
                Reads wireless RF packets forwarded by Nano over USB serial (115200 baud).
              </span>
            </div>

            <div>
              <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300 block mb-1.5">
                ESP32 Transmitter Port (Command Configuration &amp; Interval Control)
              </label>
              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={selectedEsp32Port}
                  onChange={(e) => setSelectedEsp32Port(e.target.value)}
                  placeholder="e.g., COM13"
                  className="w-full px-3 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-zinc-900 dark:focus:ring-zinc-100"
                />
                {portData?.available_ports && (
                  <select
                    onChange={(e) => e.target.value && setSelectedEsp32Port(e.target.value)}
                    className="px-2 py-2 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs text-zinc-600 dark:text-zinc-300"
                    defaultValue=""
                  >
                    <option value="" disabled>Select Port</option>
                    {portData.available_ports.map((p) => (
                      <option key={p.device} value={p.device}>
                        {p.device} ({p.suggested_role})
                      </option>
                    ))}
                  </select>
                )}
              </div>
              <span className="text-[10px] text-zinc-400 mt-1 block">
                Sends dynamic sampling intervals and Two-Phase Commit RF configuration.
              </span>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <div>
              {portSaveFeedback && (
                <span className="text-xs font-mono font-medium text-zinc-600 dark:text-zinc-300">
                  {portSaveFeedback}
                </span>
              )}
            </div>

            <button
              type="submit"
              disabled={savingPorts}
              className="px-5 py-2 rounded-lg bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 text-xs font-medium shadow-xs transition"
            >
              {savingPorts ? "Reconfiguring & Connecting..." : "Save & Reconnect Ports"}
            </button>
          </div>
        </form>
      </div>

      {/* 2. Dynamic Sampling Interval Section */}
      <div className="p-6 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-700">
              <Clock className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                ESP32 Dynamic Sampling Interval Control
              </h2>
              <p className="text-xs text-zinc-500">
                Adjust sensor measurement frequency (2s &ndash; 3600s). Saved to ESP32 Flash NVS
                (&lt;Preferences.h&gt;) across reboots. Non-blocking <code className="bg-zinc-100 dark:bg-zinc-800 px-1 py-0.5 rounded font-mono">millis()</code>.
              </p>
            </div>
          </div>
          <div>{getStatusBadge(intervalStatus?.status ?? samplingInterval?.status)}</div>
        </div>

        {/* Preset Interval Buttons */}
        <div className="space-y-2">
          <label className="text-xs font-semibold text-zinc-700 dark:text-zinc-300">
            Select Measurement Cadence:
          </label>
          <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
            {[5, 10, 30, 60, 300].map((sec) => (
              <button
                key={sec}
                type="button"
                onClick={() => handleApplyInterval(sec)}
                disabled={submittingInterval}
                className={`py-2.5 px-3 rounded-lg border text-center font-mono font-bold text-xs transition ${
                  activeInterval === sec
                    ? "bg-zinc-900 border-zinc-900 text-white dark:bg-zinc-100 dark:border-zinc-100 dark:text-zinc-900 shadow-xs"
                    : "bg-zinc-50 dark:bg-zinc-800 border-zinc-200 dark:border-zinc-700 hover:border-zinc-400 text-zinc-700 dark:text-zinc-300"
                }`}
              >
                {sec < 60 ? `${sec}s` : `${sec / 60}m`}
                <span className="block text-[10px] font-sans font-normal text-zinc-400 mt-0.5">
                  {sec === 5 ? "Default" : sec === 10 ? "Standard" : sec === 60 ? "Power Save" : "Long Term"}
                </span>
              </button>
            ))}

            {/* Custom Interval Option */}
            <div className="flex items-center gap-1.5">
              <input
                type="number"
                min="2"
                max="3600"
                value={customInterval}
                onChange={(e) => setCustomInterval(e.target.value)}
                placeholder="Sec"
                className="w-20 px-2.5 py-2.5 rounded-lg border border-zinc-200 dark:border-zinc-700 bg-zinc-50 dark:bg-zinc-800 text-xs font-mono font-semibold focus:outline-none focus:ring-1 focus:ring-zinc-900"
              />
              <button
                type="button"
                onClick={() => handleApplyInterval(Number(customInterval))}
                disabled={submittingInterval || !customInterval}
                className="p-2.5 bg-zinc-900 hover:bg-zinc-800 dark:bg-zinc-100 dark:hover:bg-zinc-200 text-white dark:text-zinc-900 rounded-lg transition"
                title="Send custom interval"
              >
                <Send className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>

        {/* Command Feedback */}
        {intervalStatus && (
          <div className="p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 text-xs flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-zinc-400 font-mono">Correlation ID:</span>
              <span className="font-mono font-semibold text-zinc-700 dark:text-zinc-300">
                {intervalStatus.cmd_id}
              </span>
            </div>
            <div>
              {intervalStatus.error ? (
                <span className="text-rose-600 font-medium">{intervalStatus.error}</span>
              ) : (
                <span className="text-emerald-600 dark:text-emerald-400 font-medium">
                  {intervalStatus.message || "Command logged in database audit trail"}
                </span>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 3. Wireless nRF24L01 Profile Selector */}
      <div className="p-6 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs space-y-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2.5 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-700">
              <Radio className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
                nRF24L01 Wireless Range &amp; Power Profile
              </h2>
              <p className="text-xs text-zinc-500">
                Two-Phase Commit (Prepare &rarr; Commit) coordinated between ESP32 transmitter and Arduino Nano receiver on Channel 108.
              </p>
            </div>
          </div>

          <div className="text-xs font-mono font-semibold px-2.5 py-1 rounded-md bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-700">
            Active: {wirelessConfig?.active_profile ?? wirelessProfile ?? "BALANCED"}
          </div>
        </div>

        {/* 3 Profile Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3.5">
          {/* SHORT */}
          <div
            className={`p-4 rounded-lg border transition ${
              (wirelessConfig?.active_profile ?? wirelessProfile) === "SHORT"
                ? "border-zinc-900 dark:border-zinc-100 bg-zinc-50 dark:bg-zinc-800/60 ring-1 ring-zinc-900 dark:ring-zinc-100"
                : "border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900"
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <h3 className="font-semibold text-xs text-zinc-800 dark:text-zinc-200">SHORT RANGE</h3>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">
                2 Mbps
              </span>
            </div>
            <p className="text-[11px] text-zinc-500 mb-3 leading-snug">
              Low power (RF24_PA_LOW). High speed, low latency, reduced battery consumption.
            </p>
            <button
              onClick={() => handleApplyProfile("SHORT")}
              disabled={submittingProfile}
              className="w-full py-1.5 rounded-md bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-xs font-medium text-zinc-800 dark:text-zinc-200 transition"
            >
              Activate SHORT
            </button>
          </div>

          {/* BALANCED */}
          <div
            className={`p-4 rounded-lg border transition ${
              (wirelessConfig?.active_profile ?? wirelessProfile) === "BALANCED"
                ? "border-zinc-900 dark:border-zinc-100 bg-zinc-50 dark:bg-zinc-800/60 ring-1 ring-zinc-900 dark:ring-zinc-100"
                : "border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900"
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <h3 className="font-semibold text-xs text-zinc-800 dark:text-zinc-200">BALANCED</h3>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">
                1 Mbps
              </span>
            </div>
            <p className="text-[11px] text-zinc-500 mb-3 leading-snug">
              High power (RF24_PA_HIGH). General indoor/outdoor water facility monitoring.
            </p>
            <button
              onClick={() => handleApplyProfile("BALANCED")}
              disabled={submittingProfile}
              className="w-full py-1.5 rounded-md bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-xs font-medium text-zinc-800 dark:text-zinc-200 transition"
            >
              Activate BALANCED
            </button>
          </div>

          {/* LONG */}
          <div
            className={`p-4 rounded-lg border transition ${
              (wirelessConfig?.active_profile ?? wirelessProfile) === "LONG"
                ? "border-zinc-900 dark:border-zinc-100 bg-zinc-50 dark:bg-zinc-800/60 ring-1 ring-zinc-900 dark:ring-zinc-100"
                : "border-zinc-200 dark:border-zinc-800 bg-white dark:bg-zinc-900"
            }`}
          >
            <div className="flex items-center justify-between mb-1.5">
              <h3 className="font-semibold text-xs text-zinc-800 dark:text-zinc-200">LONG RANGE</h3>
              <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-zinc-100 dark:bg-zinc-800 text-zinc-600 dark:text-zinc-300">
                250 kbps
              </span>
            </div>
            <p className="text-[11px] text-zinc-500 mb-3 leading-snug">
              Maximum power (RF24_PA_MAX). Maximum obstacle penetration through concrete and soil.
            </p>
            <button
              onClick={() => handleApplyProfile("LONG")}
              disabled={submittingProfile}
              className="w-full py-1.5 rounded-md bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-xs font-medium text-zinc-800 dark:text-zinc-200 transition"
            >
              Activate LONG
            </button>
          </div>
        </div>

        {profileResult && (
          <div className="p-3 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 border border-zinc-200 dark:border-zinc-700 text-xs">
            {profileResult.error_message ? (
              <span className="text-rose-600">{profileResult.error_message}</span>
            ) : (
              <span className="text-emerald-600 dark:text-emerald-400">
                Profile {profileResult.profile} configuration status: {profileResult.result}
              </span>
            )}
          </div>
        )}
      </div>
    </div>
  );
};
