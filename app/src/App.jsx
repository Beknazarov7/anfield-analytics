import { useState } from "react";
import { useJson } from "./hooks/useJson.js";
import { dataUrl } from "./lib/constants.js";
import SeasonOverview from "./components/SeasonOverview.jsx";
import MatchView from "./components/MatchView.jsx";
import Players from "./components/Players.jsx";

const VIEWS = [
  { id: "season", label: "Season Overview" },
  { id: "match", label: "Match View" },
  { id: "players", label: "Players" },
];

// Read the initial view from the URL hash (e.g. #match) so views are
// deep-linkable and shareable.
const viewFromHash = () => {
  const id = window.location.hash.replace("#", "");
  return VIEWS.some((v) => v.id === id) ? id : "season";
};

export default function App() {
  const [view, setViewState] = useState(viewFromHash);

  // Keep the URL hash in sync with the active view.
  const setView = (id) => {
    setViewState(id);
    window.location.hash = id;
  };

  // Load all three datasets once at the top and pass them down. They're small
  // and static, so there's no benefit to lazy-loading per view.
  const season = useJson(dataUrl("season_summary.json"));
  const shots = useJson(dataUrl("shots.json"));
  const players = useJson(dataUrl("players.json"));

  const loading = season.loading || shots.loading || players.loading;
  const error = season.error || shots.error || players.error;

  return (
    <div className="min-h-screen">
      {/* Header with the LFC-red accent bar. */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-5 py-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="inline-block h-8 w-1.5 rounded-full bg-lfc" />
            <div>
              <h1 className="text-xl font-extrabold tracking-tight">
                Anfield Analytics
              </h1>
              <p className="text-xs text-slate-400">
                A from-scratch expected-goals model · Liverpool FC
              </p>
            </div>
          </div>

          <nav className="flex gap-1 rounded-lg bg-slate-800/60 p-1">
            {VIEWS.map((v) => (
              <button
                key={v.id}
                onClick={() => setView(v.id)}
                className={`rounded-md px-3 py-1.5 text-sm font-medium transition ${
                  view === v.id
                    ? "bg-lfc text-white shadow"
                    : "text-slate-300 hover:bg-slate-700/60"
                }`}
              >
                {v.label}
              </button>
            ))}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-5 py-8">
        {loading && <p className="text-slate-400">Loading data…</p>}
        {error && (
          <p className="text-lfc-light">
            Failed to load data: {String(error.message || error)}
          </p>
        )}

        {!loading && !error && (
          <>
            {view === "season" && <SeasonOverview season={season.data} />}
            {view === "match" && (
              <MatchView season={season.data} shots={shots.data} />
            )}
            {view === "players" && <Players players={players.data} />}
          </>
        )}
      </main>

      <footer className="mx-auto max-w-6xl px-5 py-8 text-xs text-slate-500">
        Built on StatsBomb open data. xG values are from a model trained
        from scratch for this project — not StatsBomb's own xG.
      </footer>
    </div>
  );
}
