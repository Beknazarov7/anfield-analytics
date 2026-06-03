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
  ReferenceDot,
} from "recharts";
import { TEAM, COLORS } from "../lib/constants.js";

/**
 * Cumulative-xG "race": for a single match, each team's running xG total over
 * the 90+ minutes, as a step line. Goals are marked with a dot so you can see
 * whether they came from big chances or against the run of play.
 */
export default function XgRaceChart({ shots, opponent }) {
  const { data, teams, goals } = useMemo(() => {
    // Distinct teams in this match (our team first for stable colours).
    const teamNames = Array.from(new Set(shots.map((s) => s.team))).sort((a) =>
      a === TEAM ? -1 : 1
    );

    // Sort shots chronologically.
    const ordered = [...shots].sort(
      (a, b) => a.minute - b.minute || a.second - b.second
    );

    // Walk the timeline, accumulating each team's xG. Emit one data point per
    // shot carrying both teams' running totals (so Recharts can draw two lines).
    const running = Object.fromEntries(teamNames.map((t) => [t, 0]));
    const points = [{ minute: 0, [teamNames[0]]: 0, [teamNames[1]]: 0 }];
    const goalMarks = [];
    for (const s of ordered) {
      running[s.team] += s.my_xg;
      points.push({ minute: s.minute, ...running });
      if (s.is_goal) {
        goalMarks.push({ minute: s.minute, value: running[s.team], team: s.team });
      }
    }
    return { data: points, teams: teamNames, goals: goalMarks };
  }, [shots]);

  const colorFor = (team) => (team === TEAM ? COLORS.lfc : COLORS.opponent);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={data} margin={{ top: 10, right: 20, bottom: 5, left: -10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
        <XAxis
          dataKey="minute"
          type="number"
          domain={[0, "dataMax"]}
          stroke="#64748b"
          tick={{ fontSize: 12 }}
          label={{ value: "Minute", position: "insideBottom", offset: -2, fill: "#64748b", fontSize: 12 }}
        />
        <YAxis stroke="#64748b" tick={{ fontSize: 12 }} />
        <Tooltip
          contentStyle={{ background: "#0f172a", border: "1px solid #334155", borderRadius: 8 }}
          labelFormatter={(m) => `${m}'`}
          formatter={(v, name) => [Number(v).toFixed(2), name]}
        />
        <Legend />
        {teams.map((t) => (
          <Line
            key={t}
            type="stepAfter"
            dataKey={t}
            name={t}
            stroke={colorFor(t)}
            strokeWidth={2.5}
            dot={false}
            isAnimationActive={false}
          />
        ))}
        {/* Mark each goal on its team's line. */}
        {goals.map((g, i) => (
          <ReferenceDot
            key={i}
            x={g.minute}
            y={g.value}
            r={4}
            fill={colorFor(g.team)}
            stroke="#fff"
            strokeWidth={1}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
