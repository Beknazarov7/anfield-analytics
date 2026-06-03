"""
Data pipeline for Anfield Analytics.

Pulls shot events from StatsBomb open data via `statsbombpy`, caches each
match's raw events to data/raw/{match_id}.parquet, filters to shots, tidies
the columns we care about, and writes a single combined table to
data/processed/shots.parquet.

The pipeline runs OFFLINE: it is meant to be run on your machine to produce
static data files. The React dashboard later reads exported JSON, so there is
no live backend.

Design note (for a future "find undervalued players in another league"
extension): the data sources live in the DATA_SOURCES list below and the team
filter is a parameter, NOT hardcoded deep in the logic. To point this pipeline
at a different competition/season, or a different club, you only edit
DATA_SOURCES and TEAM_FILTER — the rest of the code is generic.

Run:
    python -m src.ingest            # uses cached raw events if present
    python -m src.ingest --refresh  # re-downloads everything from StatsBomb
"""

import argparse
import warnings
from pathlib import Path

import pandas as pd

# statsbombpy emits a NoAuthWarning on every call telling us we're using the
# free open data (which is exactly what we want). Suppress it so the console
# output stays readable.
from statsbombpy.api_client import NoAuthWarning

warnings.simplefilter("ignore", NoAuthWarning)

from statsbombpy import sb  # noqa: E402  (import after the warning filter)


# ---------------------------------------------------------------------------
# Configuration — change these to retarget the pipeline at a different dataset.
# ---------------------------------------------------------------------------

# Each source is one (competition, season) slice of StatsBomb open data.
# These three are verified to exist in the free open-data repo.
DATA_SOURCES = [
    {"name": "Liverpool 2015/16 Premier League", "competition_id": 2, "season_id": 27},
    {"name": "2005 Champions League final (Liverpool 3-3 Milan)", "competition_id": 16, "season_id": 37},
    {"name": "2019 Champions League final (Liverpool 2-0 Spurs)", "competition_id": 16, "season_id": 4},
]

# Only keep matches where this team played (as home OR away). Set to None to
# keep every match in the sources above (useful for the future multi-league
# extension, where you won't want to filter to a single club).
TEAM_FILTER = "Liverpool"

# Columns we keep from each shot event. StatsBomb gives ~100 columns per event;
# these are the ones the xG model and dashboard need.
SHOT_COLUMNS = [
    "match_id",
    "minute",
    "second",
    "team",
    "player",
    "shot_outcome",
    "shot_statsbomb_xg",
    "shot_body_part",
    "play_pattern",
    "shot_type",
    "under_pressure",
    "location",
]

# Project paths. Resolve relative to this file so the script works regardless
# of the working directory it's launched from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"


# ---------------------------------------------------------------------------
# Step 1 — find the matches we want across all configured sources.
# ---------------------------------------------------------------------------

def get_matches(team_filter: str | None) -> pd.DataFrame:
    """Return a DataFrame of matches across all DATA_SOURCES.

    If `team_filter` is given, keep only matches where that team is home or
    away. Returns one row per match with the columns we need downstream.
    """
    frames = []
    for source in DATA_SOURCES:
        # sb.matches returns one row per match in that competition+season,
        # including home_team / away_team names and the final score.
        matches = sb.matches(
            competition_id=source["competition_id"],
            season_id=source["season_id"],
        )

        if team_filter is not None:
            # Keep matches where our team appears on either side.
            is_our_match = (
                (matches["home_team"] == team_filter)
                | (matches["away_team"] == team_filter)
            )
            matches = matches[is_our_match]

        # Tag each match with which source it came from, for readable logging.
        matches = matches.copy()
        matches["source"] = source["name"]
        frames.append(matches)

        print(f"  {source['name']}: {len(matches)} match(es) after filter")

    all_matches = pd.concat(frames, ignore_index=True)
    return all_matches


# ---------------------------------------------------------------------------
# Step 2 — fetch (or load cached) raw events for a single match.
# ---------------------------------------------------------------------------

def load_match_events(match_id: int, refresh: bool) -> pd.DataFrame:
    """Return all events for one match, using a local Parquet cache.

    On the first run (or with --refresh) we download from StatsBomb and write
    the raw events to data/raw/{match_id}.parquet. On later runs we read that
    file instead, which is much faster and works offline.
    """
    cache_path = RAW_DIR / f"{match_id}.parquet"

    if cache_path.exists() and not refresh:
        return pd.read_parquet(cache_path)

    # Cache miss (or forced refresh): download from StatsBomb.
    events = sb.events(match_id=match_id)

    # We cache the FULL events table (not just shots) so a future feature can
    # use more columns without re-downloading. pyarrow stores the list-valued
    # 'location' column fine as a list of numbers.
    events.to_parquet(cache_path, index=False)
    return events


# ---------------------------------------------------------------------------
# Step 3 — turn one match's events into a tidy shots table.
# ---------------------------------------------------------------------------

def extract_shots(events: pd.DataFrame) -> pd.DataFrame:
    """Filter events to shots and keep only the columns we care about."""
    shots = events[events["type"] == "Shot"].copy()

    # Some early-season or final datasets may be missing an occasional column;
    # guard against that so the pipeline doesn't crash on a single source.
    for col in SHOT_COLUMNS:
        if col not in shots.columns:
            shots[col] = pd.NA

    return shots[SHOT_COLUMNS]


# ---------------------------------------------------------------------------
# Step 4 — derive the geometric and outcome columns the model needs.
# ---------------------------------------------------------------------------

def tidy_shots(shots: pd.DataFrame) -> pd.DataFrame:
    """Split 'location' into x/y and add the is_goal target.

    StatsBomb pitch coordinates: 120 long x 80 wide. The goal a team attacks is
    at x=120, y=40 (centre of the goal mouth). Each shot's 'location' is a
    [x, y] list, so we split it into two numeric columns for the model.
    """
    shots = shots.copy()

    # 'location' is an [x, y] pair per shot. Pull out each component. The pair
    # is a Python list when freshly downloaded from StatsBomb, but comes back as
    # a numpy array when read from the Parquet cache — so we accept any indexable
    # sequence and tolerate missing/empty locations (returns NaN) rather than
    # checking for a specific type.
    def coord(loc, idx):
        if loc is None:
            return float("nan")
        try:
            if len(loc) > idx:
                return loc[idx]
        except TypeError:
            pass  # scalar/NaN with no len(): treat as missing
        return float("nan")

    shots["x"] = shots["location"].apply(lambda loc: coord(loc, 0))
    shots["y"] = shots["location"].apply(lambda loc: coord(loc, 1))

    # Ensure numeric dtype (apply can leave object dtype if there were NaNs).
    shots["x"] = pd.to_numeric(shots["x"], errors="coerce")
    shots["y"] = pd.to_numeric(shots["y"], errors="coerce")

    # Binary target: did this shot result in a goal? StatsBomb records the
    # outcome as a string; 'Goal' is the positive class.
    shots["is_goal"] = (shots["shot_outcome"] == "Goal").astype(int)

    # Drop the now-redundant raw location list to keep the table tidy.
    shots = shots.drop(columns=["location"])

    return shots


# ---------------------------------------------------------------------------
# Orchestration.
# ---------------------------------------------------------------------------

def run(refresh: bool) -> pd.DataFrame:
    """Run the full Phase 1 pipeline and return the combined shots table."""
    # Make sure the output directories exist.
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print("Finding matches across configured data sources...")
    matches = get_matches(TEAM_FILTER)
    print(f"Total matches to ingest: {len(matches)}\n")

    all_shots = []
    for _, match in matches.iterrows():
        match_id = int(match["match_id"])
        # Note whether this will be a cache hit BEFORE we load (load may create
        # the file), so the log line is accurate.
        cached = (RAW_DIR / f"{match_id}.parquet").exists() and not refresh
        events = load_match_events(match_id, refresh)
        shots = extract_shots(events)
        all_shots.append(shots)
        tag = "cached" if cached else "downloaded"
        print(
            f"  match {match_id} "
            f"({match['home_team']} vs {match['away_team']}): "
            f"{len(shots)} shots [{tag}]"
        )

    # Combine every match's shots into one table, then derive x/y and is_goal.
    shots = pd.concat(all_shots, ignore_index=True)
    shots = tidy_shots(shots)

    # Persist the processed table for Phase 2 (feature engineering).
    out_path = PROCESSED_DIR / "shots.parquet"
    shots.to_parquet(out_path, index=False)

    return shots


def summarise(shots: pd.DataFrame) -> None:
    """Print the sanity-check summary asked for in Phase 1."""
    total_shots = len(shots)
    total_goals = int(shots["is_goal"].sum())
    goal_rate = total_goals / total_shots if total_shots else 0.0

    print("\n" + "=" * 60)
    print("PHASE 1 SUMMARY")
    print("=" * 60)
    print(f"Total shots: {total_shots}")
    print(f"Total goals: {total_goals}")
    print(f"Goal rate:   {goal_rate:.3f}  (sanity check: expect ~0.10-0.12)")
    print("\nFirst 5 rows:")
    # Show the most informative columns rather than the full width.
    preview_cols = [
        "match_id", "minute", "team", "player",
        "shot_outcome", "shot_statsbomb_xg", "x", "y", "is_goal",
    ]
    with pd.option_context("display.max_columns", None, "display.width", 120):
        print(shots[preview_cols].head().to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest StatsBomb shot data.")
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="Re-download raw events from StatsBomb instead of using the cache.",
    )
    args = parser.parse_args()

    shots = run(refresh=args.refresh)
    summarise(shots)
    print(f"\nSaved -> {PROCESSED_DIR / 'shots.parquet'}")


if __name__ == "__main__":
    main()
