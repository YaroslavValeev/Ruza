import path from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../..");

const apiProxy = {
  target: "http://127.0.0.1:8000",
  changeOrigin: true,
} as const;

export default defineConfig({
  envDir: repoRoot,
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    proxy: {
      "/health": apiProxy,
      "/auth": apiProxy,
      "/availability": apiProxy,
      "/boats": apiProxy,
      "/bookings": apiProxy,
      "/clients": apiProxy,
      "/pilot": apiProxy,
      "/kpi": apiProxy,
      "/preflight": apiProxy,
      "/smoke": apiProxy,
      "/checkins": apiProxy,
      "/analytics": apiProxy,
      "/leads": apiProxy,
      "/marketing": apiProxy,
      "/utm-events": apiProxy,
    },
  },
});
