import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite serves everything in app/public/ at the site root, so the exported
// JSON in app/public/data/ is reachable at /data/*.json in dev and prod.
//
// `base` only matters for the production build: GitHub Pages serves this repo
// from the "/anfield-analytics/" sub-path, so the built asset + data URLs must
// be prefixed with it. The dev server stays at "/" for a clean local URL.
// (constants.js builds data URLs from import.meta.env.BASE_URL, so the JSON
// fetches follow this base automatically.)
export default defineConfig(({ command }) => ({
  plugins: [react()],
  base: command === "build" ? "/anfield-analytics/" : "/",
}));
