import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite serves everything in app/public/ at the site root, so the exported
// JSON in app/public/data/ is reachable at /data/*.json in dev and prod.
export default defineConfig({
  plugins: [react()],
});
