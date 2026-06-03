"""
Feature engineering for the xG model.

Reads data/processed/shots.parquet (from src/ingest.py), derives the geometric
and contextual features an expected-goals model needs, and writes
data/processed/features.parquet.

The core intuition of xG: the chance a shot becomes a goal depends mostly on
WHERE it was taken from (how far, and how wide an angle of goal the shooter
can see) and HOW it was taken (foot vs head, open play vs set piece, under
defensive pressure or not). We turn each of those into a number here.

Design note (multi-league extension): this module only depends on the tidy
columns produced by ingest.py, never on Liverpool or a specific competition.
Point ingest.py at another league and these same features apply unchanged.

Run:
    python -m src.features
"""

from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

# StatsBomb pitch geometry. The attacking goal mouth is the 8-yard segment of
# the goal line (x=120) between the two posts. StatsBomb's y runs 0..80, and
# the goal sits centred on y=40, so the posts are at y=36 and y=44.
GOAL_X = 120.0
GOAL_CENTRE_Y = 40.0
LEFT_POST = (120.0, 36.0)
RIGHT_POST = (120.0, 44.0)

# The columns that actually feed the model. Keeping this list explicit (rather
# than "everything numeric") documents the model's inputs and makes it easy to
# add/remove a feature later.
FEATURE_COLUMNS = [
    "distance_to_goal",
    "angle_to_goal",
    "is_header",
    "is_open_play",
    "under_pressure",
]
TARGET_COLUMN = "is_goal"

# Metadata we carry through (not model inputs) so the dashboard export later can
# label each shot without re-joining to the raw data.
META_COLUMNS = [
    "match_id", "minute", "second", "team", "player",
    "shot_outcome", "shot_statsbomb_xg", "x", "y",
]


def add_distance_to_goal(shots: pd.DataFrame) -> pd.DataFrame:
    """Straight-line (Euclidean) distance from the shot to the goal centre.

    Closer shots are easier, so distance is the single strongest xG feature.
    """
    dx = GOAL_X - shots["x"]
    dy = GOAL_CENTRE_Y - shots["y"]
    shots["distance_to_goal"] = np.sqrt(dx**2 + dy**2)
    return shots


def add_angle_to_goal(shots: pd.DataFrame) -> pd.DataFrame:
    """The angle (in radians) the goal mouth subtends at the shot location.

    Picture standing where the shot was taken and looking at the goal: the two
    posts span a certain angle of your vision. A shot straight in front of an
    open goal sees a wide angle (easy); a shot from a tight position near the
    byline sees a sliver of goal (hard). This captures "how much goal can the
    shooter actually aim at", which pure distance misses.

    Trig: form the two vectors from the shot to each post, then the angle
    between those vectors is  arccos( (a . b) / (|a| |b|) ).
    """
    # Vector from each shot to the left post.
    ax = LEFT_POST[0] - shots["x"]
    ay = LEFT_POST[1] - shots["y"]
    # Vector from each shot to the right post.
    bx = RIGHT_POST[0] - shots["x"]
    by = RIGHT_POST[1] - shots["y"]

    # Dot product of the two vectors, and the product of their magnitudes.
    dot = ax * bx + ay * by
    mag = np.sqrt(ax**2 + ay**2) * np.sqrt(bx**2 + by**2)

    # arccos gives the angle between them. Clip the ratio into [-1, 1] to guard
    # against tiny floating-point overshoots that would make arccos return NaN.
    cos_angle = np.clip(dot / mag, -1.0, 1.0)
    shots["angle_to_goal"] = np.arccos(cos_angle)
    return shots


def add_is_header(shots: pd.DataFrame) -> pd.DataFrame:
    """1 if the shot was a header, else 0. Headers convert worse than feet."""
    shots["is_header"] = (shots["shot_body_part"] == "Head").astype(int)
    return shots


def add_is_open_play(shots: pd.DataFrame) -> pd.DataFrame:
    """1 for open-play shots, 0 for set pieces (free kicks, penalties).

    StatsBomb's shot_type cleanly separates 'Open Play' from 'Free Kick' and
    'Penalty'. Set pieces have very different scoring profiles (a penalty is
    ~0.78 xG; a direct free kick is low), so the model benefits from knowing
    which regime a shot belongs to.
    """
    shots["is_open_play"] = (shots["shot_type"] == "Open Play").astype(int)
    return shots


def clean_under_pressure(shots: pd.DataFrame) -> pd.DataFrame:
    """Turn under_pressure into a clean 0/1 integer.

    StatsBomb only sets this flag to True when a defender was pressuring the
    shooter; otherwise it's null. So a missing value genuinely means "not under
    pressure" -> 0, and True -> 1.
    """
    shots["under_pressure"] = (
        shots["under_pressure"].fillna(False).astype(bool).astype(int)
    )
    return shots


def build_features(shots: pd.DataFrame) -> pd.DataFrame:
    """Run every feature step and return the metadata + features + target."""
    shots = shots.copy()
    shots = add_distance_to_goal(shots)
    shots = add_angle_to_goal(shots)
    shots = add_is_header(shots)
    shots = add_is_open_play(shots)
    shots = clean_under_pressure(shots)

    # Keep metadata (for the dashboard), the model features, and the target.
    keep = META_COLUMNS + FEATURE_COLUMNS + [TARGET_COLUMN]
    return shots[keep]


def summarise(features: pd.DataFrame) -> None:
    """Print summary statistics for the engineered features."""
    print("\n" + "=" * 60)
    print("PHASE 2 SUMMARY — engineered features")
    print("=" * 60)
    print(f"Rows: {len(features)}    Features: {len(FEATURE_COLUMNS)}")

    print("\nFeature summary stats:")
    with pd.option_context("display.width", 120, "display.float_format", "{:.3f}".format):
        print(features[FEATURE_COLUMNS].describe().to_string())

    # For binary features, .describe() means are just prevalence rates, but it
    # helps to call them out plainly.
    print("\nBinary feature prevalence (share of shots = 1):")
    for col in ["is_header", "is_open_play", "under_pressure"]:
        print(f"  {col:15s}: {features[col].mean():.3f}")

    # Quick directional sanity check: goals should sit closer and at wider
    # angles than non-goals on average.
    print("\nMean feature value by outcome (goal vs no-goal):")
    by_outcome = features.groupby(TARGET_COLUMN)[
        ["distance_to_goal", "angle_to_goal"]
    ].mean()
    with pd.option_context("display.float_format", "{:.3f}".format):
        print(by_outcome.to_string())


def run() -> pd.DataFrame:
    shots = pd.read_parquet(PROCESSED_DIR / "shots.parquet")
    features = build_features(shots)

    out_path = PROCESSED_DIR / "features.parquet"
    features.to_parquet(out_path, index=False)
    return features


def main() -> None:
    features = run()
    summarise(features)
    print("\nFirst 5 rows (features + target):")
    with pd.option_context("display.width", 120, "display.float_format", "{:.3f}".format):
        print(features[FEATURE_COLUMNS + [TARGET_COLUMN]].head().to_string(index=False))
    print(f"\nSaved -> {PROCESSED_DIR / 'features.parquet'}")


if __name__ == "__main__":
    main()
