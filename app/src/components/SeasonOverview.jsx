import { useMemo } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from "recharts";
import { PL_SOURCE, TEAM, COLORS } from "../lib/constants.js";

// Colour for each result chip in the timeline.
const RESULT_STYLE = {
  W: "bg-emerald-500/90 text-white",
  D: "bg-slate-500/80 text-white",
  L: "bg-lfc text-white",
};

export default function SeasonOverview({ season }) {
  // Keep only the 38 Premier League games for the cumulative story.
  const games = useMemo(
    () =>
      season
        .filter((m) => m.source === PL_SOURCE)
        .sort((a, b) => a.date.localeCompare(b.date)),
    [season]
  );

  // Build a cumulative series: running total of our xG vs actual goals as the
  // season progresses. This is the headline "are we creating what we score?"
  // chart.
  const series = useMemo(() => {
    let cumXg = 0;
    let cumGoals = 0;
    return games.map((m, i) => {
      cumXg += m.team_xg;
      cumGoals += m.team_goals;
      return {
        gw: i + 1,
        opponent: m.opponent,
        cumXg: Number(cumXg.toFixed(2)),
        cumGoals,
      };
    });
  }, [games]);

  // Season totals for the stat cards.
  const totals = useMemo(() => {
    const xg = games.reduce((s, m) => s + m.team_xg, 0);
    const goals = games.reduce((s, m) => s + m.team_goals, 0);
    const record = games.reduce(
      (acc, m) => ({ ...acc, [m.result]: acc[m.result] + 1 }),
      { W: 0, D: 0, L: 0 }
    );
    return { xg, goals, record };
  }, [games]);

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-lg font-bold">
          {TEAM} 2015/16 — Premier League
        </h2>
        <p className="text-sm text-slate-400">
          Cumulative expected goals (my model) versus goals actually scored,
          across all 38 league games.
        </p>
      </div>

      {/* Stat cards. */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat label="Goals scored" value={totals.goals} />
        <Stat label="My xG (total)" value={totals.xg.toFixed(1)} />
        <Stat
          label="xG difference"
          value={`${totals.goals - totals.xg >= 0 ? "+" : ""}${(
            totals.goals - totals.xg
          ).toFixed(1)}`}
          hint="goals − xG"
        />
        <Stat
          label="W / D / L"
          value={`${totals.record.W}-${totals.record.D}-${totals.record.L}`}
        />
      </div>

      {/* Cumulative line chart. */}
      <div className="card">
        <ResponsiveContainer width="100%" height={340}>
          <LineChart data={series} margin={{ top: 10, right: 20, bottom: 5, left: -10 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
            <XAxis
              dataKey="gw"
              stroke="#64748b"
              tick={{ fontSize: 12 }}
              label={{ value: "Gameweek", position: "insideBottom", offset: -2, fill: "#64748b", fontSize: 12 }}
            />
            <YAxis stroke="#64748b" tick={{ fontSize: 12 }} />
            <Tooltip
              contentStyle={{
                background: "#0f172a",
                border: "1px solid #334155",
                borderRadius: 8,
              }}
              labelFormatter={(gw) => {
                const row = series[gw - 1];
                return `GW ${gw} · vs ${row ? row.opponent : ""}`;
              }}
            />
            <Legend />
            <Line
              type="monotone"
              dataKey="cumGoals"
              name="Goals scored"
              stroke={COLORS.lfc}
              strokeWidth={2.5}
              dot={false}
              isAnimationActive={false}
            />
            <Line
              type="monotone"
              dataKey="cumXg"
              name="My xG"
              stroke={COLORS.opponent}
              strokeWidth={2.5}
              strokeDasharray="5 4"
              dot={false}
              isAnimationActive={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      {/* Results timeline. */}
      <div className="card">
        <h3 className="mb-3 text-sm font-semibold text-slate-300">
          Results timeline
        </h3>
        <div className="flex flex-wrap gap-1.5">
          {games.map((m) => (
            <div
              key={m.match_id}
              title={`GW vs ${m.opponent} — ${m.team_goals}-${m.opponent_goals} (${m.result})`}
              className={`flex h-7 w-7 items-center justify-center rounded text-xs font-bold ${RESULT_STYLE[m.result]}`}
            >
              {m.result}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value, hint }) {
  return (
    <div className="card">
      <div className="stat-label">{label}</div>
      <div className="stat-value">{value}</div>
      {hint && <div className="mt-1 text-xs text-slate-500">{hint}</div>}
    </div>
  );
}
