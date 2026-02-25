"use client";

import type { MechanismChain } from "@/lib/types";

/** SVG flow diagram: [Food] → [Mechanism] → [Disease] */
export function MechanismChainSVG({ chain }: { chain: MechanismChain }) {
  const W = 600;
  const H = 80;
  const BOX_H = 36;
  const BOX_R = 8;
  const Y = (H - BOX_H) / 2;

  // Three boxes evenly spaced
  const boxes = [
    { label: chain.food, type: chain.food_type, x: 10,  w: 150, color: "#22c55e", bg: "#f0fdf4" },
    { label: chain.mechanism, type: "Mechanism",  x: 225, w: 150, color: "#f43f5e", bg: "#fff1f2" },
    { label: chain.disease,   type: "Disease",    x: 440, w: 150, color: "#ef4444", bg: "#fef2f2" },
  ];

  const arrows = [
    { x1: 160, x2: 225, label: chain.mechanism_relationship || "affects" },
    { x1: 375, x2: 440, label: "targets" },
  ];

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" preserveAspectRatio="xMidYMid meet">
      <defs>
        <marker id="arrowhead" markerWidth="8" markerHeight="6" refX="8" refY="3" orient="auto">
          <polygon points="0 0, 8 3, 0 6" fill="#94a3b8" />
        </marker>
      </defs>

      {/* Arrows */}
      {arrows.map((a, i) => {
        const midY = H / 2;
        return (
          <g key={i}>
            <line
              x1={a.x1}
              y1={midY}
              x2={a.x2 - 4}
              y2={midY}
              stroke="#94a3b8"
              strokeWidth={1.5}
              markerEnd="url(#arrowhead)"
            />
            <text
              x={(a.x1 + a.x2) / 2}
              y={midY - 8}
              textAnchor="middle"
              style={{ fontSize: "8px", fill: "#94a3b8", textTransform: "uppercase", letterSpacing: "0.05em" }}
            >
              {a.label}
            </text>
          </g>
        );
      })}

      {/* Boxes */}
      {boxes.map((b) => (
        <g key={b.label}>
          <rect
            x={b.x}
            y={Y}
            width={b.w}
            height={BOX_H}
            rx={BOX_R}
            fill={b.bg}
            stroke={b.color}
            strokeWidth={1.5}
          />
          <text
            x={b.x + b.w / 2}
            y={Y + 15}
            textAnchor="middle"
            style={{ fontSize: "10px", fontWeight: "600", fill: "#0f172a" }}
          >
            {b.label.length > 20 ? b.label.slice(0, 18) + "…" : b.label}
          </text>
          <text
            x={b.x + b.w / 2}
            y={Y + 28}
            textAnchor="middle"
            style={{ fontSize: "7px", fill: "#64748b", textTransform: "uppercase", letterSpacing: "0.06em" }}
          >
            {b.type}
          </text>
        </g>
      ))}
    </svg>
  );
}
