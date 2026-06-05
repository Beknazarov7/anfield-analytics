import { useMemo } from "react";
import { scaleLinear, scaleSqrt } from "d3-scale";
import { TEAM, COLORS, displayName } from "../lib/constants.js";

/**
 * A custom D3-driven shot map drawn on a football pitch.
 *
 * StatsBomb normalises coordinates so the attacking team always shoots toward
 * x = 120, so every shot (both teams') can be plotted on a single goal. We draw
 * the attacking THIRD as a vertical half-pitch with the goal at the top — the
 * classic shot-map look.
 *
 * Encodings:
 *   position → where the shot was taken (StatsBomb x, y)
 *   size     → xG (area-proportional, via a sqrt scale)
 *   colour   → which team took it (our team red, opponent blue)
 *   fill     → goals are solid with a white ring; other shots are hollow
 *
 * We use d3 for the maths (scales) and render the SVG with React, so React
 * stays in control of the DOM.
 */

// We show from the halfway-ish line (x = 60) up to the goal line (x = 120).
const X_MIN = 60;
const X_MAX = 120;
const Y_MIN = 0;
const Y_MAX = 80;
const PAD = 4; // viewBox padding around the pitch

// viewBox dimensions: pitch width (80) maps to horizontal, pitch length (60)
// to vertical. 1 pitch unit ≈ 1 viewBox unit keeps the geometry honest.
const VB_W = (Y_MAX - Y_MIN) + PAD * 2; // 88
const VB_H = (X_MAX - X_MIN) + PAD * 2; // 68

export default function ShotMap({ shots, opponent }) {
  // StatsBomb y → horizontal screen position.
  const sx = useMemo(
    () => scaleLinear().domain([Y_MIN, Y_MAX]).range([PAD, VB_W - PAD]),
    []
  );
  // StatsBomb x → vertical screen position, inverted so x = 120 sits at the top.
  const sy = useMemo(
    () => scaleLinear().domain([X_MIN, X_MAX]).range([VB_H - PAD, PAD]),
    []
  );

  // Area-proportional radius for xG. Empty domain guard for safety.
  const maxXg = Math.max(0.4, ...shots.map((s) => s.my_xg));
  const r = useMemo(
    () => scaleSqrt().domain([0, maxXg]).range([0.6, 5]),
    [maxXg]
  );

  // Draw goals last so they sit on top of the cloud of misses.
  const ordered = useMemo(
    () => [...shots].sort((a, b) => a.is_goal - b.is_goal),
    [shots]
  );

  return (
    <div className="w-full">
      <svg
        viewBox={`0 0 ${VB_W} ${VB_H}`}
        className="h-auto w-full rounded-lg"
        style={{ background: COLORS.pitch }}
      >
        <PitchLines sx={sx} sy={sy} />

        {ordered.map((s, i) => {
          const isTeam = s.team === TEAM;
          const color = isTeam ? COLORS.lfc : COLORS.opponent;
          return (
            <circle
              key={i}
              cx={sx(s.y)}
              cy={sy(s.x)}
              r={r(s.my_xg)}
              fill={s.is_goal ? color : "none"}
              fillOpacity={s.is_goal ? 0.95 : 0}
              stroke={color}
              strokeWidth={s.is_goal ? 0.7 : 0.5}
              strokeOpacity={s.is_goal ? 1 : 0.85}
            >
              <title>
                {`${displayName(s.player)} (${s.team}) — ${s.minute}'  xG ${s.my_xg.toFixed(
                  2
                )}${s.is_goal ? "  ⚽ GOAL" : `  ${s.outcome}`}`}
              </title>
            </circle>
          );
        })}
      </svg>

      <Legend opponent={opponent} maxXg={maxXg} r={r} />
    </div>
  );
}

/** Static pitch markings, drawn in pitch coordinates via the shared scales. */
function PitchLines({ sx, sy }) {
  const line = {
    fill: "none",
    stroke: COLORS.pitchLine,
    strokeWidth: 0.4,
  };
  // Helper to build a rectangle from pitch coords (x is length, y is width).
  const rect = (x0, x1, y0, y1) => ({
    x: sx(y0),
    y: sy(x1),
    width: sx(y1) - sx(y0),
    height: sy(x0) - sy(x1),
  });

  const box = rect(102, 120, 18, 62); // 18-yard penalty area
  const sixYard = rect(114, 120, 30, 50); // 6-yard box
  const goal = rect(120, 121, 36, 44); // goal (drawn just above the line)

  // Penalty arc: part of a 10-unit-radius circle around the penalty spot
  // (108, 40) that sits outside the box (x < 102). Endpoints at (102, 32/48).
  const arcStart = `${sx(32)},${sy(102)}`;
  const arcEnd = `${sx(48)},${sy(102)}`;
  const arcPath = `M ${arcStart} A 10 10 0 0 1 ${arcEnd}`;

  // Centre circle arc at the bottom edge (only the top half is visible).
  const ccStart = `${sx(30)},${sy(60)}`;
  const ccEnd = `${sx(50)},${sy(60)}`;
  const ccPath = `M ${ccStart} A 10 10 0 0 1 ${ccEnd}`;

  return (
    <g>
      {/* Outer boundary of the shown half. */}
      <rect
        x={sx(0)}
        y={sy(120)}
        width={sx(80) - sx(0)}
        height={sy(60) - sy(120)}
        {...line}
      />
      <rect {...box} {...line} />
      <rect {...sixYard} {...line} />
      <rect {...goal} {...line} fill={COLORS.pitchLine} fillOpacity={0.25} />
      <circle cx={sx(40)} cy={sy(108)} r={0.5} fill={COLORS.pitchLine} />
      <path d={arcPath} {...line} />
      <path d={ccPath} {...line} />
    </g>
  );
}

/** Legend explaining colour, fill, and size encodings. */
function Legend({ opponent, maxXg, r }) {
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-300">
      <LegendDot color={COLORS.lfc} label={TEAM} />
      <LegendDot color={COLORS.opponent} label={opponent || "Opponent"} />
      <span className="flex items-center gap-1.5">
        <svg width="14" height="14" viewBox="0 0 14 14">
          <circle cx="7" cy="7" r="5" fill={COLORS.lfc} />
        </svg>
        goal
      </span>
      <span className="flex items-center gap-1.5">
        <svg width="14" height="14" viewBox="0 0 14 14">
          <circle cx="7" cy="7" r="5" fill="none" stroke={COLORS.miss} strokeWidth="1.3" />
        </svg>
        no goal
      </span>
      <span className="text-slate-500">circle size = xG (max {maxXg.toFixed(2)})</span>
    </div>
  );
}

function LegendDot({ color, label }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className="inline-block h-3 w-3 rounded-full" style={{ background: color }} />
      {label}
    </span>
  );
}
