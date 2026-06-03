import { useMemo, useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  Cell,
} from "recharts";
import { TEAM, COLORS } from "../lib/constants.js";

const MIN_SHOTS = 3; // filter out tiny samples that produce noisy ratios
const TOP_N = 15;

export default function Players({ players }) {
  // Toggle between just our team and everyone in the dataset.
  const [teamOnly, setTeamOnly] = useState(true);

  const ranked = useMemo(() => {
    return players
      .filter((p) => p.shots >= MIN_SHOTS && (!teamOnly || p.team === TEAM))
      .sort((a, b) => b.my_xg - a.my_xg)
      .slice(0, TOP_N)
      .map((p) => ({ ...p, shortName: shorten(p.player) }));
  }, [players, teamOnly]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-lg font-bold">Top performers by xG</h2>
          <p className="text-sm text-slate-400">
            Players ranked by total expected goals. Over/under-performance is
            goals minus xG — positive means a clinical finisher.
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-slate-300">
          <input
            type="checkbox"
            checked={teamOnly}
            onChange={(e) => setTeamOnly(e.target.checked)}
            className="accent-lfc"
          />
          {TEAM} only
        </label>
      </div>

      {/* Goals vs xG bar chart. */}
      <div className="card">
        <ResponsiveContainer width="100%" height={Math.max(320, ranked.length * 34)}>
          <BarChart
            data={ranked}
            layout="vertical"
            margin={{ top: 5, right: 20, bottom: 5, left: 40 }}
          >
            <XAxis type="number" stroke="#64748b" tick={{ fontSize: 12 }} />
            <YAxis
              type="category"
              dataKey="shortName"
              width={110}
              stroke="#64748b"
              tick={{ fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
              formatter={(v, name) => [Number(v).toFixed(2), name]}
            />
            <Legend />
            <Bar dataKey="my_xg" name="My xG" fill={COLORS.opponent} radius={[0, 3, 3, 0]} isAnimationActive={false} />
            <Bar dataKey="goals" name="Goals" fill={COLORS.lfc} radius={[0, 3, 3, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Over/under-performance table. */}
      <div className="card overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs uppercase tracking-wider text-slate-400">
              <th className="pb-2 pr-4">Player</th>
              {!teamOnly && <th className="pb-2 pr-4">Team</th>}
              <th className="pb-2 pr-4 text-right">Shots</th>
              <th className="pb-2 pr-4 text-right">Goals</th>
              <th className="pb-2 pr-4 text-right">xG</th>
              <th className="pb-2 text-right">Goals − xG</th>
            </tr>
          </thead>
          <tbody>
            {ranked.map((p) => (
              <tr key={p.player} className="border-t border-slate-800">
                <td className="py-2 pr-4 font-medium">{p.shortName}</td>
                {!teamOnly && <td className="py-2 pr-4 text-slate-400">{p.team}</td>}
                <td className="py-2 pr-4 text-right text-slate-400">{p.shots}</td>
                <td className="py-2 pr-4 text-right">{p.goals}</td>
                <td className="py-2 pr-4 text-right">{p.my_xg.toFixed(2)}</td>
                <td className="py-2 text-right">
                  <PerfBadge value={p.performance} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Colour-coded over/under-performance badge. */
function PerfBadge({ value }) {
  const positive = value >= 0;
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${
        positive ? "bg-emerald-500/20 text-emerald-300" : "bg-lfc/20 text-lfc-light"
      }`}
    >
      {positive ? "+" : ""}
      {value.toFixed(2)}
    </span>
  );
}

// StatsBomb stores full legal names; show a shorter, readable form.
function shorten(name) {
  const parts = name.split(" ");
  return parts.length > 2 ? `${parts[0]} ${parts[parts.length - 1]}` : name;
}
