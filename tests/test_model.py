"""
Sanity tests for the trained xG model.

These load the promoted model (models/xg_model.pkl) and check it behaves like a
sensible expected-goals model. They are skipped automatically if the model has
not been trained yet, so a fresh clone still passes `pytest` before running the
pipeline.
"""

import joblib
import pandas as pd
import pytest

from src.features import FEATURE_COLUMNS
from src.xg_model import MODELS_DIR

MODEL_PATH = MODELS_DIR / "xg_model.pkl"

pytestmark = pytest.mark.skipif(
    not MODEL_PATH.exists(),
    reason="xg_model.pkl not found — run `python -m src.xg_model && python -m src.evaluate` first",
)


@pytest.fixture(scope="module")
def model():
    return joblib.load(MODEL_PATH)


def _shot(distance, angle, is_header, is_open_play, under_pressure):
    """Build a one-row feature frame in the exact FEATURE_COLUMNS order."""
    return pd.DataFrame(
        [[distance, angle, is_header, is_open_play, under_pressure]],
        columns=FEATURE_COLUMNS,
    )


def test_predictions_are_valid_probabilities(model):
    great = _shot(6.0, 0.9, 0, 1, 0)
    poor = _shot(30.0, 0.1, 1, 1, 1)
    for shot in (great, poor):
        p = model.predict_proba(shot)[0, 1]
        assert 0.0 <= p <= 1.0


def test_better_chance_has_higher_xg(model):
    # A close, central, open-play shot off the foot with no pressure should be
    # worth clearly more xG than a long-range header under pressure.
    great_xg = model.predict_proba(_shot(6.0, 0.9, 0, 1, 0))[0, 1]
    poor_xg = model.predict_proba(_shot(30.0, 0.1, 1, 1, 1))[0, 1]
    assert great_xg > poor_xg


def test_closer_is_never_worse(model):
    # Holding everything else equal, moving the shot closer to goal (shorter
    # distance, wider angle) should not lower its xG.
    near = model.predict_proba(_shot(8.0, 0.7, 0, 1, 0))[0, 1]
    far = model.predict_proba(_shot(25.0, 0.2, 0, 1, 0))[0, 1]
    assert near >= far
