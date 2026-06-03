"""
Static JSON export for the React dashboard.

This is the bridge between the offline Python pipeline and the frontend. It
scores every shot with our trained xG model and writes three static JSON files
into app/public/data/, which the React app reads directly (no backend):

  season_summary.json  one row per match: our xG for & against, the actual
                       score, and the result (from the configured team's view).
  shots.json           every shot: x, y, my_xg, statsbomb_xg, outcome, player,
                       minute, match_id (the raw material for the shot map).
  players.json         per-player totals: my xG, goals, shots, and
                       over/under-performance (goals minus xG).

Run (after the model exists in models/xg_model.pkl):
    python -m src.export_json
"""

import json
from pathlib import Path

import joblib
import pandas as pd

from src.features import FEATURE_COLUMNS, TARGET_COLUMN
from src.ingest import TEAM_FILTER, get_matches
from src.xg_model import MODELS_DIR, PROCESSED_DIR

PROJECT_ROOT = Path(__file__).resolve().parent.parent
# The React app serves everything under app/public/ as static files.
EXPORT_DIR = PROJECT_ROOT / "app" / "public" / "data"


def load_scored_shots() -> pd.DataFrame:
    """Load the feature table and attach our model's xG to every shot."""
    shots = pd.read_parquet(PROCESSED_DIR / "features.parquet")
    model = joblib.load(MODELS_DIR / "xg_model.pkl")

    # Probability of a goal = our expected-goals value for that shot.
    shots["my_xg"] = model.predict_proba(shots[FEATURE_COLUMNS])[:, 1]
    return shots


def load_match_metadata() -> pd.DataFrame:
    """One row per match with teams, score, date, and competition.

    Reuses ingest.get_matches so the same TEAM_FILTER and DATA_SOURCES apply.
    """
    matches = get_matches(TEAM_FILTER)
    cols = [
        "match_id", "match_date", "home_team", "away_team",
        "home_score", "away_score", "competition_name", "source",
    ]
    # Guard against any column a particular source might lack.
    cols = [c for c in cols if c in matches.columns]
    return matches[cols].drop_duplicates("match_id").reset_index(drop=True)


def build_season_summary(shots: pd.DataFrame, matches: pd.DataFrame) -> list[dict]:
    """Per-match summary from the configured team's point of view.

    "for" = our team's xG, "against" = the opponents' xG. We also carry the
    actual scoreline and a W/D/L result so the dashboard can draw both the
    cumulative-xG line and a results timeline.
    """
    # Sum our model's xG per team within each match.
    xg_by_match_team = (
        shots.groupby(["match_id", "team"])["my_xg"].sum().reset_index()
    )

    summary = []
    for _, m in matches.iterrows():
        match_id = int(m["match_id"])
        home, away = m["home_team"], m["away_team"]
        team_is_home = home == TEAM_FILTER
        opponent = away if team_is_home else home

        # Pull this match's per-team xG totals into a quick lookup.
        match_xg = xg_by_match_team[xg_by_match_team["match_id"] == match_id]
        xg_lookup = dict(zip(match_xg["team"], match_xg["my_xg"]))
        team_xg = float(xg_lookup.get(TEAM_FILTER, 0.0))
        # "against" is every other team's xG in the match (almost always one
        # opponent, but summing is robust).
        opp_xg = float(sum(v for k, v in xg_lookup.items() if k != TEAM_FILTER))

        # Actual goals from the scoreline, oriented to our team.
        home_score, away_score = int(m["home_score"]), int(m["away_score"])
        team_goals = home_score if team_is_home else away_score
        opp_goals = away_score if team_is_home else home_score

        if team_goals > opp_goals:
            result = "W"
        elif team_goals < opp_goals:
            result = "L"
        else:
            result = "D"

        summary.append({
            "match_id": match_id,
            "date": str(m.get("match_date", "")),
            "competition": m.get("competition_name", ""),
            "source": m.get("source", ""),
            "home_team": home,
            "away_team": away,
            "team_is_home": bool(team_is_home),
            "opponent": opponent,
            "team_goals": team_goals,
            "opponent_goals": opp_goals,
            "team_xg": round(team_xg, 3),
            "opponent_xg": round(opp_xg, 3),
            "result": result,
        })

    # Order chronologically so cumulative charts read left-to-right.
    summary.sort(key=lambda r: r["date"])
    return summary


def build_shots(shots: pd.DataFrame) -> list[dict]:
    """Every shot, with the fields the D3 shot map and race chart need."""
    records = []
    for _, s in shots.iterrows():
        records.append({
            "match_id": int(s["match_id"]),
            "minute": int(s["minute"]),
            "second": int(s["second"]),
            "team": s["team"],
            "player": s["player"],
            "x": round(float(s["x"]), 2),
            "y": round(float(s["y"]), 2),
            "my_xg": round(float(s["my_xg"]), 4),
            # StatsBomb's own xG, for side-by-side comparison on the map.
            "statsbomb_xg": round(float(s["shot_statsbomb_xg"]), 4)
            if pd.notna(s["shot_statsbomb_xg"]) else None,
            "outcome": s["shot_outcome"],
            "is_goal": int(s[TARGET_COLUMN]),
        })
    return records


def build_players(shots: pd.DataFrame) -> list[dict]:
    """Per-player totals and over/under-performance (goals minus xG).

    A positive (goals - xG) means the player scored more than an average
    finisher would from those chances — a clinical finisher or a hot streak.
    Negative means underperformance.
    """
    grouped = shots.groupby("player")
    players = []
    for player, g in grouped:
        total_xg = float(g["my_xg"].sum())
        goals = int(g[TARGET_COLUMN].sum())
        players.append({
            "player": player,
            "team": g["team"].iloc[0],
            "shots": int(len(g)),
            "goals": goals,
            "my_xg": round(total_xg, 3),
            # The headline number: did they out- or under-score their chances?
            "performance": round(goals - total_xg, 3),
        })

    # Most chance creation first (highest total xG at the top).
    players.sort(key=lambda r: r["my_xg"], reverse=True)
    return players


def write_json(obj, filename: str) -> Path:
    path = EXPORT_DIR / filename
    with open(path, "w") as f:
        json.dump(obj, f, indent=2)
    return path


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    shots = load_scored_shots()
    matches = load_match_metadata()

    season = build_season_summary(shots, matches)
    shot_records = build_shots(shots)
    players = build_players(shots)

    write_json(season, "season_summary.json")
    write_json(shot_records, "shots.json")
    write_json(players, "players.json")

    print("\n" + "=" * 60)
    print("PHASE 4 — JSON export")
    print("=" * 60)
    print(f"season_summary.json : {len(season)} matches  -> {EXPORT_DIR/'season_summary.json'}")
    print(f"shots.json          : {len(shot_records)} shots    -> {EXPORT_DIR/'shots.json'}")
    print(f"players.json        : {len(players)} players  -> {EXPORT_DIR/'players.json'}")

    # Quick peek so we can eyeball the output without opening the files.
    print("\nFirst match in season_summary.json:")
    print(json.dumps(season[0], indent=2))
    print("\nTop 5 players by xG:")
    for p in players[:5]:
        print(
            f"  {p['player']:30s} xG={p['my_xg']:5.2f}  goals={p['goals']:2d}  "
            f"perf={p['performance']:+.2f}"
        )


if __name__ == "__main__":
    main()
