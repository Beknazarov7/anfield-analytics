"""
xG model evaluation and selection.

Loads the two models trained by src/xg_model.py, scores them on the held-out
test set, and decides which is the better xG model. For expected goals,
CALIBRATION matters more than raw discrimination: if the model says a set of
shots are worth 0.30 xG each, about 30% of them should actually go in. An xG
model that ranks shots well but is mis-scaled is wrong for our purpose (summing
xG over a season), so we choose the model with the lowest calibration error.

Outputs:
  - models/calibration_logreg.png, models/calibration_xgboost.png
  - models/xg_model.pkl  (a copy of the winning model)

Metrics reported per model:
  - log-loss   : penalises confident wrong probabilities (lower is better)
  - ROC-AUC    : ranking ability — can it tell goals from non-goals? (higher)
  - Brier      : mean squared error of the probabilities (lower is better)
  - ECE        : expected calibration error — our selection metric (lower)

Run (after python -m src.xg_model):
    python -m src.evaluate
"""

from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")  # headless backend: write PNGs, never open a window
import matplotlib.pyplot as plt  # noqa: E402

from sklearn.metrics import log_loss, roc_auc_score, brier_score_loss  # noqa: E402

from src.features import FEATURE_COLUMNS, TARGET_COLUMN  # noqa: E402
from src.xg_model import (  # noqa: E402
    MODELS_DIR,
    get_train_test_split,
    load_features,
    train_models,
    save_model,
)

# Number of bins for the calibration curve / ECE. Quantile binning (equal shot
# counts per bin) is steadier than equal-width bins when goals are sparse.
N_BINS = 10


def load_or_train_models(X_train, y_train) -> dict:
    """Load the saved models if present, otherwise train (and save) them.

    Lets evaluate.py run standalone, but reuses src.xg_model's training so the
    two scripts never drift apart.
    """
    paths = {"logreg": MODELS_DIR / "logreg.pkl", "xgboost": MODELS_DIR / "xgboost.pkl"}
    if all(p.exists() for p in paths.values()):
        return {name: joblib.load(p) for name, p in paths.items()}

    models = train_models(X_train, y_train)
    save_model(models["logreg"], "logreg.pkl")
    save_model(models["xgboost"], "xgboost.pkl")
    return models


def quantile_calibration(y_true, y_prob, n_bins=N_BINS):
    """Bin shots by predicted probability and return (pred_mean, actual_rate).

    For each quantile bin we compute the mean predicted xG and the actual goal
    rate. A perfectly calibrated model puts these on the diagonal y = x.
    """
    # Rank shots into equal-sized quantile bins by predicted probability.
    bins = pd.qcut(y_prob, q=n_bins, duplicates="drop")
    frame = pd.DataFrame({"prob": y_prob, "actual": np.asarray(y_true), "bin": bins})
    grouped = frame.groupby("bin", observed=True)
    pred_mean = grouped["prob"].mean().to_numpy()
    actual_rate = grouped["actual"].mean().to_numpy()
    weight = grouped.size().to_numpy()  # shots per bin, for weighting ECE
    return pred_mean, actual_rate, weight


def expected_calibration_error(y_true, y_prob, n_bins=N_BINS) -> float:
    """Weighted average gap between predicted xG and actual goal rate per bin.

    This is our headline calibration number and the metric we select on.
    """
    pred_mean, actual_rate, weight = quantile_calibration(y_true, y_prob, n_bins)
    gaps = np.abs(pred_mean - actual_rate)
    return float(np.average(gaps, weights=weight))


def evaluate_model(name, model, X_test, y_test) -> dict:
    """Compute all metrics for one model on the test set."""
    # Probability of the positive class (a goal).
    y_prob = model.predict_proba(X_test)[:, 1]
    return {
        "name": name,
        "log_loss": log_loss(y_test, y_prob),
        "roc_auc": roc_auc_score(y_test, y_prob),
        "brier": brier_score_loss(y_test, y_prob),
        "ece": expected_calibration_error(y_test, y_prob),
        "y_prob": y_prob,
    }


def plot_calibration(name, y_true, y_prob) -> Path:
    """Save a calibration plot (predicted xG vs actual goal rate, binned)."""
    pred_mean, actual_rate, _ = quantile_calibration(y_true, y_prob)

    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    # Diagonal = perfect calibration reference line.
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey", label="perfect calibration")
    # Our model's binned reliability curve.
    ax.plot(pred_mean, actual_rate, marker="o", color="#C8102E", label=name)  # LFC red

    # Zoom to the region shots actually live in (most xG is well under 0.6).
    upper = max(0.6, float(np.nanmax([pred_mean.max(), actual_rate.max()])) * 1.1)
    ax.set_xlim(0, upper)
    ax.set_ylim(0, upper)
    ax.set_xlabel("Mean predicted xG (per bin)")
    ax.set_ylabel("Actual goal rate (per bin)")
    ax.set_title(f"Calibration — {name}")
    ax.legend(loc="upper left")
    ax.set_aspect("equal", adjustable="box")
    fig.tight_layout()

    path = MODELS_DIR / f"calibration_{name}.png"
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path


def statsbomb_sanity_check(df: pd.DataFrame, model) -> None:
    """Compare our xG totals against StatsBomb's and the actual goal count.

    Predicts on EVERY shot (a ballpark aggregate check, so train/test overlap is
    fine here). Our season-level xG total should land close to both StatsBomb's
    total and the real number of goals.
    """
    my_xg = model.predict_proba(df[FEATURE_COLUMNS])[:, 1]
    my_total = float(my_xg.sum())
    sb_total = float(df["shot_statsbomb_xg"].sum())
    actual_goals = int(df[TARGET_COLUMN].sum())

    print("\nStatsBomb sanity check (all shots)")
    print("-" * 60)
    print(f"  Actual goals scored : {actual_goals}")
    print(f"  My xG total         : {my_total:.1f}")
    print(f"  StatsBomb xG total  : {sb_total:.1f}")
    print(f"  My total vs StatsBomb: {my_total / sb_total:.2f}x")


def main() -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    df = load_features()
    X_train, X_test, y_train, y_test = get_train_test_split(df)
    models = load_or_train_models(X_train, y_train)

    # Score every model on the held-out test set.
    results = [evaluate_model(name, m, X_test, y_test) for name, m in models.items()]

    print("\n" + "=" * 60)
    print("PHASE 3 — model evaluation (held-out test set)")
    print("=" * 60)
    header = f"{'model':10s} {'log_loss':>10s} {'roc_auc':>10s} {'brier':>10s} {'ece':>10s}"
    print(header)
    print("-" * len(header))
    for r in results:
        print(
            f"{r['name']:10s} {r['log_loss']:>10.4f} {r['roc_auc']:>10.4f} "
            f"{r['brier']:>10.4f} {r['ece']:>10.4f}"
        )

    # Calibration plots for each model.
    print()
    for r in results:
        path = plot_calibration(r["name"], y_test, r["y_prob"])
        print(f"  saved calibration plot -> {path}")

    # Select the better-CALIBRATED model (lowest expected calibration error).
    best = min(results, key=lambda r: r["ece"])
    print(
        f"\nBest-calibrated model: {best['name']} "
        f"(ECE={best['ece']:.4f}) -> saving as xg_model.pkl"
    )
    save_model(models[best["name"]], "xg_model.pkl")

    # Finally, sanity-check the winner's season xG totals against StatsBomb.
    statsbomb_sanity_check(df, models[best["name"]])


if __name__ == "__main__":
    main()
