"""
Unit tests for the data ingest + feature-engineering maths.

These are fast, deterministic, and need no network or trained model: they
construct tiny in-memory DataFrames and check the geometry/target logic that the
xG model depends on. Run with:  pytest
"""

import math

import numpy as np
import pandas as pd
import pytest

from src.ingest import tidy_shots
from src.features import (
    add_distance_to_goal,
    add_angle_to_goal,
    add_is_header,
    add_is_open_play,
    clean_under_pressure,
    build_features,
    FEATURE_COLUMNS,
    TARGET_COLUMN,
)


# ---------------------------------------------------------------------------
# ingest.tidy_shots — splitting 'location' and deriving the goal target.
# ---------------------------------------------------------------------------

def test_tidy_shots_splits_location_and_marks_goals():
    shots = pd.DataFrame({
        "shot_outcome": ["Goal", "Saved", "Off T"],
        # location arrives as a Python list when fresh from StatsBomb...
        "location": [[114.0, 40.0], [100.0, 30.0], [90.0, 50.0]],
    })
    out = tidy_shots(shots)

    assert list(out["x"]) == [114.0, 100.0, 90.0]
    assert list(out["y"]) == [40.0, 30.0, 50.0]
    # Only the "Goal" outcome is the positive class.
    assert list(out["is_goal"]) == [1, 0, 0]
    # The raw list column is dropped after splitting.
    assert "location" not in out.columns


def test_tidy_shots_handles_numpy_array_and_missing_locations():
    # When read back from the Parquet cache, 'location' comes as a numpy array;
    # some events can also have a missing location. Both must be tolerated.
    shots = pd.DataFrame({
        "shot_outcome": ["Goal", "Saved"],
        "location": [np.array([110.0, 44.0]), None],
    })
    out = tidy_shots(shots)

    assert out["x"].iloc[0] == 110.0
    assert out["y"].iloc[0] == 44.0
    # Missing location -> NaN coordinates, not a crash.
    assert math.isnan(out["x"].iloc[1])
    assert math.isnan(out["y"].iloc[1])


# ---------------------------------------------------------------------------
# features.add_distance_to_goal — Euclidean distance to the goal centre.
# ---------------------------------------------------------------------------

def test_distance_to_goal_known_points():
    # Goal centre is (120, 40). On the goal line centre -> 0; penalty spot
    # (108, 40) -> 12; (114, 40) -> 6.
    shots = pd.DataFrame({"x": [120.0, 108.0, 114.0], "y": [40.0, 40.0, 40.0]})
    out = add_distance_to_goal(shots)
    assert out["distance_to_goal"].tolist() == [0.0, 12.0, 6.0]


def test_distance_to_goal_diagonal():
    # (117, 36): dx=3, dy=4 -> 5-12-13 triangle -> distance 5.
    shots = pd.DataFrame({"x": [117.0], "y": [36.0]})
    out = add_distance_to_goal(shots)
    assert out["distance_to_goal"].iloc[0] == 5.0


# ---------------------------------------------------------------------------
# features.add_angle_to_goal — angle the goal mouth subtends at the shot.
# ---------------------------------------------------------------------------

def test_angle_to_goal_penalty_spot():
    # From the penalty spot (108, 40) the posts are at (120, 36) and (120, 44).
    # Vectors (12, -4) and (12, 4): cos = (144-16)/160 = 0.8 -> arccos(0.8).
    shots = pd.DataFrame({"x": [108.0], "y": [40.0]})
    out = add_angle_to_goal(shots)
    assert out["angle_to_goal"].iloc[0] == pytest.approx(math.acos(0.8))


def test_angle_wider_when_closer_and_central():
    # A close central shot should "see" a wider goal angle than a far one.
    shots = pd.DataFrame({"x": [118.0, 84.0], "y": [40.0, 40.0]})
    out = add_angle_to_goal(shots)
    close_angle, far_angle = out["angle_to_goal"].iloc[0], out["angle_to_goal"].iloc[1]
    assert close_angle > far_angle


# ---------------------------------------------------------------------------
# Binary feature helpers.
# ---------------------------------------------------------------------------

def test_is_header():
    shots = pd.DataFrame({"shot_body_part": ["Head", "Right Foot", "Left Foot"]})
    assert add_is_header(shots)["is_header"].tolist() == [1, 0, 0]


def test_is_open_play():
    shots = pd.DataFrame({"shot_type": ["Open Play", "Free Kick", "Penalty"]})
    assert add_is_open_play(shots)["is_open_play"].tolist() == [1, 0, 0]


def test_under_pressure_nulls_become_zero():
    # StatsBomb only sets under_pressure when True; null genuinely means "no".
    shots = pd.DataFrame({"under_pressure": [True, None, False]})
    assert clean_under_pressure(shots)["under_pressure"].tolist() == [1, 0, 0]


# ---------------------------------------------------------------------------
# build_features — end-to-end shape of the engineered table.
# ---------------------------------------------------------------------------

def test_build_features_outputs_expected_columns():
    shots = pd.DataFrame({
        "match_id": [1], "minute": [10], "second": [5],
        "team": ["Liverpool"], "player": ["A. Player"],
        "shot_outcome": ["Goal"], "shot_statsbomb_xg": [0.2],
        "x": [114.0], "y": [40.0],
        "shot_body_part": ["Right Foot"], "shot_type": ["Open Play"],
        "under_pressure": [None], "is_goal": [1],
    })
    out = build_features(shots)
    # Every model feature and the target must be present.
    for col in FEATURE_COLUMNS + [TARGET_COLUMN]:
        assert col in out.columns
    # Derived values for this single open-play, right-footed, no-pressure shot.
    assert out["is_open_play"].iloc[0] == 1
    assert out["is_header"].iloc[0] == 0
    assert out["under_pressure"].iloc[0] == 0
    assert out["distance_to_goal"].iloc[0] == 6.0
