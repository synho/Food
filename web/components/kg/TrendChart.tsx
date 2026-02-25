"use client";

interface TrendPoint {
  date: string;
  nodes: number;
  relationships: number;
}

export function TrendChart({ data }: { data: TrendPoint[] }) {
  if (data.length < 2) return null;

  const W = 500;
  const H = 200;
  const PAD = { top: 20, right: 20, bottom: 30, left: 50 };
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const maxNodes = Math.max(...data.map((d) => d.nodes), 1);
  const maxRels = Math.max(...data.map((d) => d.relationships), 1);
  const maxY = Math.max(maxNodes, maxRels);

  const xScale = (i: number) => PAD.left + (i / (data.length - 1)) * innerW;
  const yScale = (v: number) => PAD.top + innerH - (v / maxY) * innerH;

  function polyline(key: "nodes" | "relationships"): string {
    return data.map((d, i) => `${xScale(i)},${yScale(d[key])}`).join(" ");
  }

  function areaPath(key: "nodes" | "relationships"): string {
    const baseline = PAD.top + innerH;
    const points = data.map((d, i) => `${xScale(i)},${yScale(d[key])}`);
    return `M${xScale(0)},${baseline} L${points.join(" L")} L${xScale(data.length - 1)},${baseline} Z`;
  }

  // Y-axis ticks (5 ticks)
  const yTicks = Array.from({ length: 5 }, (_, i) => Math.round((maxY / 4) * i));

  // X-axis labels (show first, middle, last)
  const xLabels: { i: number; label: string }[] = [];
  const fmt = (d: string) => {
    const dt = new Date(d);
    return `${dt.getMonth() + 1}/${dt.getDate()}`;
  };
  if (data.length <= 5) {
    data.forEach((d, i) => xLabels.push({ i, label: fmt(d.date) }));
  } else {
    xLabels.push({ i: 0, label: fmt(data[0].date) });
    const mid = Math.floor(data.length / 2);
    xLabels.push({ i: mid, label: fmt(data[mid].date) });
    xLabels.push({ i: data.length - 1, label: fmt(data[data.length - 1].date) });
  }

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      {/* Grid lines */}
      {yTicks.map((v) => (
        <line
          key={v}
          x1={PAD.left}
          y1={yScale(v)}
          x2={W - PAD.right}
          y2={yScale(v)}
          stroke="#e2e8f0"
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
          style={{ fontSize: "9px", fill: "#94a3b8" }}
        >
          {v.toLocaleString()}
        </text>
      ))}

      {/* X-axis labels */}
      {xLabels.map(({ i, label }) => (
        <text
          key={`xl-${i}`}
          x={xScale(i)}
          y={H - 5}
          textAnchor="middle"
          style={{ fontSize: "9px", fill: "#94a3b8" }}
        >
          {label}
        </text>
      ))}

      {/* Area fills */}
      <path d={areaPath("nodes")} fill="#3b82f6" opacity={0.1} />
      <path d={areaPath("relationships")} fill="#22c55e" opacity={0.1} />

      {/* Lines */}
      <polyline
        points={polyline("nodes")}
        fill="none"
        stroke="#3b82f6"
        strokeWidth={2}
        strokeLinejoin="round"
      />
      <polyline
        points={polyline("relationships")}
        fill="none"
        stroke="#22c55e"
        strokeWidth={2}
        strokeLinejoin="round"
      />

      {/* Dots */}
      {data.map((d, i) => (
        <circle key={`n-${i}`} cx={xScale(i)} cy={yScale(d.nodes)} r={2.5} fill="#3b82f6" />
      ))}
      {data.map((d, i) => (
        <circle key={`r-${i}`} cx={xScale(i)} cy={yScale(d.relationships)} r={2.5} fill="#22c55e" />
      ))}
    </svg>
  );
}
