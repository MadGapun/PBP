import path from "node:path";
import { Agent as HttpAgent } from "node:http";
import { fileURLToPath } from "node:url";

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const apiPort = process.env.BA_DASHBOARD_PORT || process.env.BA_API_PORT || "8200";
const webPort = Number(process.env.BA_WEB_PORT || "5173");
const apiProxyTarget = process.env.PBP_API_PROXY_TARGET || `http://127.0.0.1:${apiPort}`;
const apiProxyAgent = new HttpAgent({
  keepAlive: true,
  maxSockets: 64,
  keepAliveMsecs: 15_000,
});

export default defineConfig({
  plugins: [react()],
  base: "/static/dashboard/",
  server: {
    host: "127.0.0.1",
    port: webPort,
    strictPort: true,
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: true,
        agent: apiProxyAgent,
      },
    },
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../src/bewerbungs_assistent/static/dashboard"),
    emptyOutDir: true,
  },
});
