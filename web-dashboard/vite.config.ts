import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { execSync } from "node:child_process";

// Build stamp: date + short git SHA, baked in at build time (PRD 6.1). If the
// footer shows an old stamp, the dist/ being served is stale.
function gitSha(): string {
  try {
    return execSync("git rev-parse --short HEAD").toString().trim();
  } catch {
    return "nogit";
  }
}
const BUILD_STAMP = `${new Date().toISOString().slice(0, 10)} ${gitSha()}`;

// The Python server (state_server.py :8000) serves the built dist/, so in
// production the API is same-origin. The dev proxy maps the same API paths to
// :8000 so fetch code uses relative paths identically in dev and prod.
const API = ["/health", "/state", "/history", "/metrics", "/frame.jpg", "/trials"];

export default defineConfig({
  base: "./", // relative asset paths so dist/ works when served from Python
  plugins: [react()],
  define: {
    __BUILD_STAMP__: JSON.stringify(BUILD_STAMP),
  },
  build: {
    outDir: "dist",
  },
  server: {
    proxy: Object.fromEntries(
      API.map((p) => [p, { target: "http://localhost:8000", changeOrigin: true }]),
    ),
  },
});
