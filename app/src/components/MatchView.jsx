import { useMemo, useState } from "react";
import { TEAM } from "../lib/constants.js";
import ShotMap from "./ShotMap.jsx";
import XgRaceChart from "./XgRaceChart.jsx";

export default function MatchView({ season, shots }) {
  // Matches sorted newest-first for the picker.
  const matches = useMemo(
    () => [...season].sort((a, b) => b.date.localeCompare(a.date)),
    [season]
  );

  const [matchId, setMatchId] = useState(matches[0]?.match_id);
  const match = matches.find((m) => m.match_id === matchId) ?? matches[0];

  // Shots belonging to the selected match.
  const matchShots = useMemo(
    () => shots.filter((s) => s.match_id === match.match_id),
    [shots, match.match_id]
  );

  return (
    <div className="space-y-6">
      {/* Match picker + scoreline. */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <label className="stat-label mb-1 block">Select match</label>
          <select
            value={match.match_id}
            onChange={(e) => setMatchId(Number(e.target.value))}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-2 text-sm focus:border-lfc focus:outline-none"
          >
            {matches.map((m) => (
              <option key={m.match_id} value={m.match_id}>
                {m.date} · {m.home_team} {m.home_score}–{m.away_score} {m.away_team}
              </option>
            ))}
          </select>
        </div>

        <Scoreline match={match} />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* The shot map — the centrepiece. */}
        <div className="card">
          <h3 className="mb-3 text-sm font-semibold text-slate-300">Shot map</h3>
          <ShotMap shots={matchShots} opponent={match.opponent} />
        </div>

        {/* Cumulative-xG race. */}
        <div className="card">
          <h3 className="mb-3 text-sm font-semibold text-slate-300">
            Cumulative xG race
          </h3>
          <XgRaceChart shots={matchShots} opponent={match.opponent} />
          <p className="mt-2 text-xs text-slate-500">
            Running expected-goals total for each team. Dots mark goals.
          </p>
        </div>
      </div>
    </div>
  );
}

/** Scoreline panel showing actual score vs each team's xG. */
function Scoreline({ match }) {
  const teamIsHome = match.team_is_home;
  // Orient home/away xG from the stored team/opponent values.
  const homeXg = teamIsHome ? match.team_xg : match.opponent_xg;
  const awayXg = teamIsHome ? match.opponent_xg : match.team_xg;

  return (
    <div className="card flex items-center gap-4 py-3">
      <Side name={match.home_team} score={match.home_score} xg={homeXg} highlight={match.home_team === TEAM} />
      <span className="text-slate-500">vs</span>
      <Side name={match.away_team} score={match.away_score} xg={awayXg} highlight={match.away_team === TEAM} align="right" />
    </div>
  );
}

function Side({ name, score, xg, highlight, align = "left" }) {
  return (
    <div className={align === "right" ? "text-right" : ""}>
      <div className={`text-sm font-semibold ${highlight ? "text-lfc-light" : "text-slate-300"}`}>
        {name}
      </div>
      <div className="flex items-baseline gap-2" style={{ justifyContent: align === "right" ? "flex-end" : "flex-start" }}>
        <span className="text-2xl font-extrabold">{score}</span>
        <span className="text-xs text-slate-400">{xg.toFixed(2)} xG</span>
      </div>
    </div>
  );
}
