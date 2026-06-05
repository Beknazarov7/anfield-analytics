# Project Instructions

Anfield Analytics — a from-scratch expected-goals (xG) model on StatsBomb open
data, plus a React dashboard. See [README.md](README.md) for the full overview.

## Architecture

Offline Python pipeline → static JSON → React dashboard (no backend). Run order:

```
src/ingest.py → src/features.py → src/xg_model.py → src/evaluate.py → src/export_json.py
```

- `src/ingest.py` — downloads StatsBomb shots, caches raw events to `data/raw/{match_id}.parquet`, writes `data/processed/shots.parquet`.
- `src/features.py` — engineers the 5 model features → `data/processed/features.parquet`.
- `src/xg_model.py` — trains logistic regression + XGBoost → `models/{logreg,xgboost}.pkl`.
- `src/evaluate.py` — scores both on a held-out set, picks the best-**calibrated** (lowest ECE), promotes it to `models/xg_model.pkl`.
- `src/export_json.py` — scores every shot, writes `app/public/data/{season_summary,shots,players}.json`.
- `app/` — Vite + React + Tailwind dashboard reading that JSON.

## Commands

```bash
source .venv/bin/activate          # Python env (already created)
python -m src.<stage>              # run a pipeline stage (see order above)
pytest                             # run sanity tests

cd app && npm run dev              # dashboard at http://localhost:5173
cd app && npm run build            # production build (base = /anfield-analytics/)
```

## Conventions & gotchas

- **Single source of truth for retargeting:** `DATA_SOURCES` / `TEAM_FILTER` in `src/ingest.py`, `TEAM` in `app/src/lib/constants.js`. Don't hardcode "Liverpool" elsewhere.
- **Train/test split** uses a fixed `RANDOM_STATE` shared between `xg_model.py` and `evaluate.py` — keep them in sync.
- **Model selection metric is ECE (calibration), not accuracy/AUC** — calibration is what matters for season-level xG sums.
- **Player names:** StatsBomb stores full legal names; the dashboard maps known players to common names via `KNOWN_NAMES` / `displayName` in `app/src/lib/constants.js` (English players → last name, many Brazilian/Iberian players → middle name, so a curated override is needed).
- **`location` column** can be a Python list (fresh download) or numpy array (Parquet cache) — `ingest.tidy_shots` tolerates both; keep that when editing.
- **Vite `base`** is `/anfield-analytics/` for builds (GitHub Pages sub-path) and `/` for dev — see `app/vite.config.js`.
- Git-ignored (re-generatable): `data/raw/*`, `models/*.pkl`, `models/*.json`, `app/dist/`.

## Commit style

Keep commit messages to a single concise line.
