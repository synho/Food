"use client";

import { useState } from "react";

interface TrendPoint {
  date: string;
  nodes: number;
  relationships: number;
}

export function TrendChart({ data }: { data: TrendPoint[] }) {
  const [hover, setHover] = useState<number | null>(null);

  if (data.length < 2) return null;

  const W = 500;
  const H = 220;
  const PAD = { top: 24, right: 20, bottom: 32, left: 55 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const maxNodes = Math.max(...data.map((d) => d.nodes ?? 0), 1);
  const maxRels = Math.max(...data.map((d) => d.relationships ?? 0), 1);
  const maxY = Math.max(maxNodes, maxRels);

  const xScale = (i: number) => PAD.left + (i / (data.length - 1)) * innerW;
  const yScale = (v: number) => PAD.top + innerH - (v / maxY) * innerH;

  function polyline(key: "nodes" | "relationships"): string {
    return data.map((d, i) => `${xScale(i)},${yScale(d[key] ?? 0)}`).join(" ");
  }

  function areaPath(key: "nodes" | "relationships"): string {
    const baseline = PAD.top + innerH;
    const points = data.map((d, i) => `${xScale(i)},${yScale(d[key] ?? 0)}`);
    return `M${xScale(0)},${baseline} L${points.join(" L")} L${xScale(data.length - 1)},${baseline} Z`;
  }

  // Y-axis ticks (5 ticks)
  const yTicks = Array.from({ length: 5 }, (_, i) => Math.round((maxY / 4) * i));

  // Detect if data spans less than 2 days (intra-day mode)
  const firstDate = new Date(data[0].date);
  const lastDate = new Date(data[data.length - 1].date);
  const spanMs = lastDate.getTime() - firstDate.getTime();
  const isIntraDay = spanMs < 2 * 86_400_000;

  const fmt = (d: string) => {
    const dt = new Date(d);
    if (isIntraDay) {
      return dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    }
    return `${dt.getMonth() + 1}/${dt.getDate()}`;
  };

  const fmtTooltip = (d: string) => {
    const dt = new Date(d);
    return dt.toLocaleDateString([], { month: "short", day: "numeric" }) +
      " " + dt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  };

  // X-axis labels
  const xLabels: { i: number; label: string }[] = [];
  if (data.length <= 6) {
    data.forEach((d, i) => xLabels.push({ i, label: fmt(d.date) }));
  } else {
    const step = Math.max(1, Math.floor(data.length / 5));
    for (let i = 0; i < data.length; i += step) {
      xLabels.push({ i, label: fmt(data[i].date) });
    }
    // Always include the last point
    if (xLabels[xLabels.length - 1]?.i !== data.length - 1) {
      xLabels.push({ i: data.length - 1, label: fmt(data[data.length - 1].date) });
    }
  }

  // Latest values for annotation
  const latest = data[data.length - 1];
  const prev = data.length >= 2 ? data[data.length - 2] : null;
  const nodeDelta = prev ? (latest.nodes ?? 0) - (prev.nodes ?? 0) : 0;
  const relDelta = prev ? (latest.relationships ?? 0) - (prev.relationships ?? 0) : 0;

  const hd = hover != null ? data[hover] : null;

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full"
        preserveAspectRatio="xMidYMid meet"
        onMouseLeave={() => setHover(null)}
      >
        {/* Grid lines */}
        {yTicks.map((v) => (
          <line
            key={v}
            x1={PAD.left}
            y1={yScale(v)}
            x2={W - PAD.right}
            y2={yScale(v)}
            className="stroke-slate-200 dark:stroke-gray-700"
            strokeWidth={0.5}
          />
        ))}

        {/* Y-axis labels */}
        {yTicks.map((v) => (
          <text
            key={`yl-${v}`}
            x={PAD.left - 6}
            y={yScale(v) + 3}
            textAnchor="end"
            className="fill-slate-400 dark:fill-gray-500"
            style={{ fontSize: "9px" }}
          >
            {v >= 1000 ? `${(v / 1000).toFixed(v >= 10000 ? 0 : 1)}k` : v.toLocaleString()}
          </text>
        ))}

        {/* X-axis labels */}
        {xLabels.map(({ i, label }) => (
          <text
            key={`xl-${i}`}
            x={xScale(i)}
            y={H - 5}
            textAnchor="middle"
            className="fill-slate-400 dark:fill-gray-500"
            style={{ fontSize: "8px" }}
          >
            {label}
          </text>
        ))}

        {/* Area fills */}
        <path d={areaPath("relationships")} fill="#22c55e" opacity={0.08} />
        <path d={areaPath("nodes")} fill="#3b82f6" opacity={0.08} />

        {/* Lines */}
        <polyline
          points={polyline("relationships")}
          fill="none"
          stroke="#22c55e"
          strokeWidth={1.5}
          strokeLinejoin="round"
        />
        <polyline
          points={polyline("nodes")}
          fill="none"
          stroke="#3b82f6"
          strokeWidth={2}
          strokeLinejoin="round"
        />

        {/* Dots — only first, last, and hover */}
        {[0, data.length - 1].map((i) => (
          <g key={`dots-${i}`}>
            <circle cx={xScale(i)} cy={yScale(data[i].nodes ?? 0)} r={3} fill="#3b82f6" />
            <circle cx={xScale(i)} cy={yScale(data[i].relationships ?? 0)} r={3} fill="#22c55e" />
          </g>
        ))}

        {/* Latest value annotations */}
        <text
          x={xScale(data.length - 1) + 4}
          y={yScale(latest.nodes ?? 0) - 6}
          className="fill-blue-600 dark:fill-blue-400 font-semibold"
          style={{ fontSize: "9px" }}
        >
          {(latest.nodes ?? 0).toLocaleString()}
          {nodeDelta !== 0 && (
            <tspan className={nodeDelta > 0 ? "fill-emerald-500" : "fill-red-400"}>
              {" "}{nodeDelta > 0 ? "+" : ""}{nodeDelta.toLocaleString()}
            </tspan>
          )}
        </text>
        <text
          x={xScale(data.length - 1) + 4}
          y={yScale(latest.relationships ?? 0) + 12}
          className="fill-emerald-600 dark:fill-emerald-400 font-semibold"
          style={{ fontSize: "9px" }}
        >
          {(latest.relationships ?? 0).toLocaleString()}
          {relDelta !== 0 && (
            <tspan className={relDelta > 0 ? "fill-emerald-500" : "fill-red-400"}>
              {" "}{relDelta > 0 ? "+" : ""}{relDelta.toLocaleString()}
            </tspan>
          )}
        </text>

        {/* Hover interaction zones */}
        {data.map((_, i) => (
          <rect
            key={`hit-${i}`}
            x={xScale(i) - innerW / data.length / 2}
            y={PAD.top}
            width={innerW / data.length}
            height={innerH}
            fill="transparent"
            onMouseEnter={() => setHover(i)}
          />
        ))}

        {/* Hover vertical line + dots */}
        {hover != null && (
          <g>
            <line
              x1={xScale(hover)}
              y1={PAD.top}
              x2={xScale(hover)}
              y2={PAD.top + innerH}
              className="stroke-slate-300 dark:stroke-gray-600"
              strokeWidth={1}
              strokeDasharray="3,3"
            />
            <circle cx={xScale(hover)} cy={yScale(data[hover].nodes ?? 0)} r={4} fill="#3b82f6" stroke="white" strokeWidth={1.5} />
            <circle cx={xScale(hover)} cy={yScale(data[hover].relationships ?? 0)} r={4} fill="#22c55e" stroke="white" strokeWidth={1.5} />
          </g>
        )}
      </svg>

      {/* Hover tooltip */}
      {hd && hover != null && (
        <div
          className="absolute pointer-events-none bg-white/95 dark:bg-gray-800/95 border border-slate-200 dark:border-gray-600 rounded-lg shadow-lg px-3 py-2 text-xs"
          style={{
            left: `${(xScale(hover) / W) * 100}%`,
            top: "8px",
            transform: hover > data.length / 2 ? "translateX(-110%)" : "translateX(10%)",
          }}
        >
          <div className="font-medium text-slate-600 dark:text-gray-300 mb-1">{fmtTooltip(hd.date)}</div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-blue-500" />
            <span className="text-slate-800 dark:text-gray-100 tabular-nums font-semibold">{(hd.nodes ?? 0).toLocaleString()}</span>
            <span className="text-slate-400 dark:text-gray-500">nodes</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="inline-block h-2 w-2 rounded-full bg-green-500" />
            <span className="text-slate-800 dark:text-gray-100 tabular-nums font-semibold">{(hd.relationships ?? 0).toLocaleString()}</span>
            <span className="text-slate-400 dark:text-gray-500">rels</span>
          </div>
        </div>
      )}
    </div>
  );
}
