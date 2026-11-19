"use client";

import React, { useEffect, useRef, useState } from "react";
import { Box, RefreshCw, Eye, EyeOff, Camera, HelpCircle } from "lucide-react";
import { api } from "@/lib/api";
import { Point3D } from "@/types/api";

export const Multivariate3DTab: React.FC = () => {
  const containerRef = useRef<HTMLDivElement>(null);
  const [points, setPoints] = useState<Point3D[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [limit, setLimit] = useState<number>(500);
  const [showOnlyAnomalies, setShowOnlyAnomalies] = useState<boolean>(false);
  const [lastUpdated, setLastUpdated] = useState<string>("");

  const loadData = async () => {
    try {
      setLoading(true);
      const res = await api.get3DPoints(limit);
      setPoints(res.points || []);
      setLastUpdated(new Date().toLocaleTimeString());
    } catch (err) {
      console.error("Failed to load 3D points:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [limit]);

  useEffect(() => {
    if (!containerRef.current || points.length === 0) return;

    let isMounted = true;

    // Dynamically import plotly on client side
    import("plotly.js-dist-min").then((Plotly) => {
      if (!isMounted || !containerRef.current) return;

      const filtered = showOnlyAnomalies ? points.filter((p) => p.is_anomaly === 1) : points;

      const normalPoints = filtered.filter((p) => p.is_anomaly === 0);
      const anomalyPoints = filtered.filter((p) => p.is_anomaly === 1);
      const latestPoint = points[points.length - 1];

      const traces: any[] = [];

      // 1. Normal Observations (Blue Circles)
      if (normalPoints.length > 0) {
        traces.push({
          x: normalPoints.map((p) => p.x),
          y: normalPoints.map((p) => p.y),
          z: normalPoints.map((p) => p.z),
          mode: "markers",
          type: "scatter3d",
          name: "Normal Operating",
          marker: {
            size: 4,
            color: "#2563eb", // blue-600
            opacity: 0.65,
            symbol: "circle",
          },
          text: normalPoints.map(
            (p) =>
              `<b>NORMAL</b><br>Temp: ${p.x.toFixed(2)} °C<br>pH: ${p.y.toFixed(2)}<br>TDS: ${p.z.toFixed(0)} ppm<br>Score: ${p.primary_score}<br>Time: ${p.timestamp}`
          ),
          hoverinfo: "text",
        });
      }

      // 2. Anomaly Observations (Crimson Diamonds)
      if (anomalyPoints.length > 0) {
        traces.push({
          x: anomalyPoints.map((p) => p.x),
          y: anomalyPoints.map((p) => p.y),
          z: anomalyPoints.map((p) => p.z),
          mode: "markers",
          type: "scatter3d",
          name: "Anomalous Points",
          marker: {
            size: 7,
            color: "#dc2626", // red-600
            symbol: "diamond",
            opacity: 0.95,
            line: {
              color: "#ffffff",
              width: 1,
            },
          },
          text: anomalyPoints.map(
            (p) =>
              `<b>ANOMALY [${p.severity}]</b><br>${p.classification}<br>Temp: ${p.x.toFixed(2)} °C<br>pH: ${p.y.toFixed(2)}<br>TDS: ${p.z.toFixed(0)} ppm<br>Score: ${p.primary_score}<br>Time: ${p.timestamp}`
          ),
          hoverinfo: "text",
        });
      }

      // 3. Current Live Point (Large Golden Target)
      if (latestPoint) {
        traces.push({
          x: [latestPoint.x],
          y: [latestPoint.y],
          z: [latestPoint.z],
          mode: "markers",
          type: "scatter3d",
          name: "Latest Ingestion",
          marker: {
            size: 11,
            color: latestPoint.is_anomaly ? "#e11d48" : "#10b981",
            symbol: "cross",
            line: {
              color: "#f59e0b",
              width: 2,
            },
          },
          text: [
            `<b>LATEST OBSERVATION</b><br>Temp: ${latestPoint.x.toFixed(2)} °C<br>pH: ${latestPoint.y.toFixed(2)}<br>TDS: ${latestPoint.z.toFixed(0)} ppm<br>Classification: ${latestPoint.classification}`
          ],
          hoverinfo: "text",
        });
      }

      const layout: any = {
        title: {
          text: "Multivariate State-Space Coordinates (Temperature &times; pH &times; TDS)",
          font: { size: 14, color: "#475569" },
        },
        scene: {
          xaxis: {
            title: "Temperature (°C)",
            gridcolor: "#e2e8f0",
            zerolinecolor: "#cbd5e1",
          },
          yaxis: {
            title: "pH Level",
            gridcolor: "#e2e8f0",
            zerolinecolor: "#cbd5e1",
          },
          zaxis: {
            title: "TDS (ppm)",
            gridcolor: "#e2e8f0",
            zerolinecolor: "#cbd5e1",
          },
          camera: {
            eye: { x: 1.5, y: 1.5, z: 1.2 },
          },
        },
        margin: { l: 0, r: 0, b: 0, t: 40 },
        paper_bgcolor: "transparent",
        plot_bgcolor: "transparent",
        legend: {
          x: 0.02,
          y: 0.98,
          bgcolor: "rgba(255, 255, 255, 0.7)",
          bordercolor: "#e2e8f0",
          borderwidth: 1,
        },
        autosize: true,
      };

      const config: any = {
        responsive: true,
        displayModeBar: true,
        modeBarButtonsToRemove: ["lasso2d", "select2d"],
      };

      Plotly.react(containerRef.current, traces, layout, config);
    });

    return () => {
      isMounted = false;
    };
  }, [points, showOnlyAnomalies]);

  const setCameraView = (type: "isometric" | "top" | "front" | "side") => {
    const el = containerRef.current;
    if (!el) return;
    import("plotly.js-dist-min").then((Plotly) => {
      const currentEl = containerRef.current;
      if (!currentEl) return;
      let eye = { x: 1.5, y: 1.5, z: 1.2 };
      if (type === "top") eye = { x: 0, y: 0, z: 2.5 };
      if (type === "front") eye = { x: 0, y: 2.5, z: 0 };
      if (type === "side") eye = { x: 2.5, y: 0, z: 0 };

      Plotly.relayout(currentEl, {
        "scene.camera.eye": eye,
      });
    });
  };

  return (
    <div className="space-y-6">
      {/* Header & Controls Card */}
      <div className="p-5 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-lg bg-zinc-100 dark:bg-zinc-800 text-zinc-800 dark:text-zinc-200 border border-zinc-200 dark:border-zinc-700">
              <Box className="w-4 h-4" />
            </div>
            <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              Interactive 3D Multivariate State-Space Plot
            </h2>
          </div>
          <p className="text-xs text-zinc-500 mt-1">
            Visualizes all synchronized 3-parameter observations (Temp, pH, TDS) evaluated by River Half-Space Trees.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-2.5">
          {/* Show Anomalies Only Toggle */}
          <button
            onClick={() => setShowOnlyAnomalies(!showOnlyAnomalies)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium flex items-center gap-1.5 transition ${
              showOnlyAnomalies
                ? "bg-rose-600 text-white shadow-xs"
                : "bg-zinc-100 hover:bg-zinc-200 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700"
            }`}
          >
            {showOnlyAnomalies ? <Eye className="w-3.5 h-3.5" /> : <EyeOff className="w-3.5 h-3.5" />}
            {showOnlyAnomalies ? "Anomalies Only" : "Show All"}
          </button>

          {/* Point Limit Selector */}
          <select
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value))}
            className="px-2.5 py-1.5 rounded-lg text-xs font-mono font-medium bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700 focus:outline-none"
          >
            <option value={100}>Last 100 pts</option>
            <option value={250}>Last 250 pts</option>
            <option value={500}>Last 500 pts</option>
            <option value={1000}>Last 1,000 pts</option>
          </select>

          {/* Camera Buttons */}
          <div className="flex items-center rounded-lg border border-zinc-200 dark:border-zinc-700 overflow-hidden text-xs font-mono">
            <button
              onClick={() => setCameraView("isometric")}
              className="px-2.5 py-1.5 bg-zinc-50 hover:bg-zinc-100 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-600 dark:text-zinc-300 border-r border-zinc-200 dark:border-zinc-700 font-medium"
              title="Isometric 3D View"
            >
              Iso
            </button>
            <button
              onClick={() => setCameraView("top")}
              className="px-2.5 py-1.5 bg-zinc-50 hover:bg-zinc-100 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-600 dark:text-zinc-300 border-r border-zinc-200 dark:border-zinc-700 font-medium"
              title="Top View (Temp vs pH)"
            >
              Top (T-pH)
            </button>
            <button
              onClick={() => setCameraView("front")}
              className="px-2.5 py-1.5 bg-zinc-50 hover:bg-zinc-100 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-600 dark:text-zinc-300 font-medium"
              title="Front View (Temp vs TDS)"
            >
              Front (T-TDS)
            </button>
          </div>

          {/* Refresh */}
          <button
            onClick={loadData}
            disabled={loading}
            className="p-1.5 rounded-lg bg-zinc-100 hover:bg-zinc-200 dark:bg-zinc-800 dark:hover:bg-zinc-700 text-zinc-600 dark:text-zinc-300 border border-zinc-200 dark:border-zinc-700"
            title="Reload 3D points"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* 3D Canvas Container */}
      <div className="p-4 rounded-xl bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 shadow-xs relative">
        {loading && points.length === 0 ? (
          <div className="h-[580px] flex items-center justify-center flex-col gap-3 text-zinc-400">
            <RefreshCw className="w-6 h-6 animate-spin text-zinc-500" />
            <span className="text-xs font-mono">Loading 3D state-space observations...</span>
          </div>
        ) : (
          <div
            ref={containerRef}
            className="w-full h-[580px] rounded-lg overflow-hidden"
          />
        )}
      </div>

      {/* Model & Architecture Explanatory Callout */}
      <div className="p-4 rounded-xl bg-zinc-50 dark:bg-zinc-800/40 border border-zinc-200 dark:border-zinc-800 flex items-start gap-3">
        <HelpCircle className="w-4 h-4 text-zinc-500 shrink-0 mt-0.5" />
        <div className="text-xs text-zinc-600 dark:text-zinc-400 leading-relaxed">
          <span className="font-semibold text-zinc-800 dark:text-zinc-200">
            How Multivariate Anomaly Detection Works in 3D:
          </span>{" "}
          Water quality cannot be validated by 1D thresholds alone. A temperature of 25°C, pH of 7.2, and TDS of 250 ppm
          may each look normal individually, but unusual combinations represent subtle contamination or chemical imbalance.
          Our streaming <b>River Half-Space Trees (HST)</b> model projects points into this 3D coordinate space, recursively
          partitioning the bounding hyper-cube. Points isolated in sparse regions trigger anomaly scores ($0.0 \to 1.0$)
          and are rejected from model updates to prevent learning bad data as normal.
        </div>
      </div>
    </div>
  );
};
