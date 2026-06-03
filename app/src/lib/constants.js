// The club this dashboard is themed around. Kept in one place so the app could
// later be re-pointed at another team without hunting through components — the
// same single-source-of-truth idea as TEAM_FILTER in the Python pipeline.
export const TEAM = "Liverpool";

// The Premier League data source string used in season_summary.json. The
// season overview filters to this so the two cup finals don't pollute the
// 38-game cumulative view.
export const PL_SOURCE = "Liverpool 2015/16 Premier League";

// Shared colours (mirror the Tailwind theme for use in SVG / Recharts, which
// can't read Tailwind class names).
export const COLORS = {
  lfc: "#C8102E",
  opponent: "#38bdf8", // sky-400, clearly distinct from red
  goal: "#C8102E",
  miss: "#94a3b8", // slate-400
  pitch: "#1f7a4d",
  pitchLine: "rgba(255,255,255,0.7)",
};

// Base path for fetching the static JSON, so it works whether the app is
// served at "/" (Vercel) or a sub-path.
export const dataUrl = (file) => `${import.meta.env.BASE_URL}data/${file}`;
