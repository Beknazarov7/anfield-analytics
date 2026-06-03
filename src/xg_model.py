"""
xG model training.

Trains TWO expected-goals models on data/processed/features.parquet:

  1. Logistic regression — a simple, fully interpretable baseline. Its
     coefficients tell a clear story about which features push the chance of
     scoring up or down, which is exactly what we want for the README.
  2. XGBoost — a gradient-boosted tree model that can capture non-linear
     interactions a linear model can't, usually at the cost of interpretability.

This module is the "training" half. It fits both models and saves them to
models/logreg.pkl and models/xgboost.pkl. The "judging" half lives in
evaluate.py, which scores both, plots their calibration, picks the
better-calibrated one, and promotes it to models/xg_model.pkl.

The train/test split uses a fixed RANDOM_STATE so the split is identical here
and in evaluate.py (and reproducible between runs).

Run:
    python -m src.xg_model
"""

import math
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from src.features import FEATURE_COLUMNS, TARGET_COLUMN

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
MODELS_DIR = PROJECT_ROOT / "models"

# Fixed seed + test fraction so results are reproducible and the split matches
# across xg_model.py and evaluate.py.
RANDOM_STATE = 42
TEST_SIZE = 0.25

# Human-friendly descriptions used when printing logistic-regression effects.
FEATURE_MEANING = {
    "distance_to_goal": "shot taken farther from goal",
    "angle_to_goal": "wider angle of goal visible",
    "is_header": "shot is a header",
    "is_open_play": "shot is open play (vs set piece)",
    "under_pressure": "shooter under defensive pressure",
}


def load_features() -> pd.DataFrame:
    """Load the engineered feature table produced by src/features.py."""
    return pd.read_parquet(PROCESSED_DIR / "features.parquet")


def get_train_test_split(df: pd.DataFrame):
    """Stratified train/test split on the goal label.

    Goals are rare (~11% of shots), so we stratify on is_goal to keep the same
    goal proportion in both the train and test sets — otherwise a random split
    could leave the small test set with too few goals to evaluate fairly.
    """
    X = df[FEATURE_COLUMNS]
    y = df[TARGET_COLUMN]
    return train_test_split(
        X, y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
        stratify=y,
    )


def build_logreg() -> Pipeline:
    """Logistic regression wrapped in a scaler.

    We standardise features first so that (a) the optimiser converges cleanly
    and (b) the fitted coefficients are directly comparable to each other — each
    one is then "effect per one standard deviation of that feature".
    """
    return Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=1000, random_state=RANDOM_STATE)),
    ])


def build_xgboost() -> XGBClassifier:
    """A deliberately modest XGBoost.

    With only ~1100 shots, a deep/large forest would overfit badly. Shallow
    trees, a low learning rate, and row/column subsampling keep it honest.
    """
    return XGBClassifier(
        n_estimators=150,
        max_depth=3,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        eval_metric="logloss",
        random_state=RANDOM_STATE,
    )


def train_models(X_train, y_train) -> dict:
    """Fit both models and return them in a name -> fitted-model dict."""
    models = {
        "logreg": build_logreg(),
        "xgboost": build_xgboost(),
    }
    for model in models.values():
        model.fit(X_train, y_train)
    return models


def describe_logreg_coefficients(logreg: Pipeline) -> None:
    """Print the logistic-regression coefficients in plain English.

    Because features are standardised, each coefficient is the change in the
    log-odds of scoring for a one-standard-deviation increase in that feature.
    We convert to an odds ratio (exp of the coefficient) and describe direction:
    > 1 means the feature RAISES the chance of scoring, < 1 means it LOWERS it.
    """
    clf = logreg.named_steps["clf"]
    coefs = clf.coef_[0]

    rows = []
    for feature, coef in zip(FEATURE_COLUMNS, coefs):
        odds_ratio = math.exp(coef)
        direction = "raises" if coef > 0 else "lowers"
        rows.append((feature, coef, odds_ratio, direction))

    # Sort by absolute effect so the strongest drivers come first.
    rows.sort(key=lambda r: abs(r[1]), reverse=True)

    print("\nLogistic-regression coefficients (plain terms)")
    print("-" * 60)
    print("Each effect is per +1 standard deviation of the feature.\n")
    for feature, coef, odds_ratio, direction in rows:
        meaning = FEATURE_MEANING.get(feature, feature)
        print(
            f"  {feature:17s} coef={coef:+.3f}  odds x{odds_ratio:.2f}  "
            f"-> {direction} xG  ({meaning})"
        )
    print(
        f"\n  Intercept: {clf.intercept_[0]:+.3f} "
        "(baseline log-odds for an average shot)"
    )


def save_model(model, filename: str) -> Path:
    path = MODELS_DIR / filename
    joblib.dump(model, path)
    return path


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    df = load_features()
    X_train, X_test, y_train, y_test = get_train_test_split(df)
    print(
        f"Train: {len(X_train)} shots ({int(y_train.sum())} goals)   "
        f"Test: {len(X_test)} shots ({int(y_test.sum())} goals)"
    )

    models = train_models(X_train, y_train)
    save_model(models["logreg"], "logreg.pkl")
    save_model(models["xgboost"], "xgboost.pkl")
    print(f"\nSaved -> {MODELS_DIR / 'logreg.pkl'}")
    print(f"Saved -> {MODELS_DIR / 'xgboost.pkl'}")

    # The interpretability payoff: explain what the linear model learned.
    describe_logreg_coefficients(models["logreg"])


if __name__ == "__main__":
    main()
