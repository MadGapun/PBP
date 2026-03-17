import http from "node:http";
import { spawn } from "node:child_process";

const API_HOST = process.env.BA_API_HOST || "127.0.0.1";
const API_PORT = Number(process.env.BA_DASHBOARD_PORT || process.env.BA_API_PORT || "8200");
const API_STATUS_PATH = process.env.BA_API_STATUS_PATH || "/api/status";
const API_WAIT_TIMEOUT_MS = Number(process.env.BA_API_WAIT_TIMEOUT_MS || "30000");
const API_WAIT_INTERVAL_MS = Number(process.env.BA_API_WAIT_INTERVAL_MS || "400");
const API_CHECK_TIMEOUT_MS = Number(process.env.BA_API_CHECK_TIMEOUT_MS || "1200");
const WEB_HOST = process.env.BA_WEB_HOST || "127.0.0.1";
const WEB_PORT = Number(process.env.BA_WEB_PORT || "5173");
const WEB_HEALTH_PATH = process.env.BA_WEB_HEALTH_PATH || "/static/dashboard/";
const START_WITHOUT_API = ["1", "true", "yes", "on"].includes(
  String(process.env.BA_WEB_START_WITHOUT_API || "").trim().toLowerCase(),
);

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function holdProcessOpen() {
  const keepAlive = setInterval(() => {}, 60_000);
  if (process.stdin?.readable) {
    process.stdin.resume();
  }
  const exit = () => {
    clearInterval(keepAlive);
    process.exit(0);
  };
  process.on("SIGINT", exit);
  process.on("SIGTERM", exit);
}

function checkApiReachable() {
  return new Promise((resolve) => {
    const req = http.request(
      {
        host: API_HOST,
        port: API_PORT,
        path: API_STATUS_PATH,
        method: "GET",
        timeout: API_CHECK_TIMEOUT_MS,
      },
      (res) => {
        res.resume();
        resolve(res.statusCode >= 100);
      },
    );

    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
    req.on("error", () => resolve(false));
    req.end();
  });
}

function checkWebReachable() {
  return new Promise((resolve) => {
    const req = http.request(
      {
        host: WEB_HOST,
        port: WEB_PORT,
        path: WEB_HEALTH_PATH,
        method: "GET",
        timeout: API_CHECK_TIMEOUT_MS,
      },
      (res) => {
        res.resume();
        resolve(res.statusCode >= 100);
      },
    );

    req.on("timeout", () => {
      req.destroy();
      resolve(false);
    });
    req.on("error", () => resolve(false));
    req.end();
  });
}

async function waitForApi() {
  const deadline = Date.now() + API_WAIT_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (await checkApiReachable()) {
      return true;
    }
    await sleep(API_WAIT_INTERVAL_MS);
  }
  return false;
}

async function main() {
  const webAlreadyRunning = await checkWebReachable();
  if (webAlreadyRunning) {
    console.log(
      `[dev:web] WEB already reachable on http://${WEB_HOST}:${WEB_PORT}${WEB_HEALTH_PATH}. Using existing instance.`,
    );
    holdProcessOpen();
    return;
  }

  const ready = await waitForApi();
  if (!ready) {
    if (!START_WITHOUT_API) {
      console.error(
        `[dev:web] API not reachable on http://${API_HOST}:${API_PORT} after ${API_WAIT_TIMEOUT_MS}ms.`,
      );
      console.error(
        "[dev:web] Start abgebrochen, um Proxy-Fehlerloops zu vermeiden. Fuer WEB-only: `pnpm run dev:web:raw` oder `BA_WEB_START_WITHOUT_API=1 pnpm run dev:web`.",
      );
      process.exit(1);
      return;
    }
    console.warn(
      `[dev:web] API not reachable on http://${API_HOST}:${API_PORT} after ${API_WAIT_TIMEOUT_MS}ms. Continuing because BA_WEB_START_WITHOUT_API is enabled.`,
    );
  }

  const child = spawn("pnpm", ["run", "dev:web:raw"], {
    stdio: "inherit",
    shell: process.platform === "win32",
    env: process.env,
  });

  const forwardSignal = (signal) => {
    if (!child.killed) {
      child.kill(signal);
    }
  };

  process.on("SIGINT", () => forwardSignal("SIGINT"));
  process.on("SIGTERM", () => forwardSignal("SIGTERM"));
  child.on("exit", async (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }

    if ((code ?? 0) !== 0) {
      const webBecameReachable = await checkWebReachable();
      if (webBecameReachable) {
        console.warn(
          `[dev:web] Child WEB process exited with code ${code}, but WEB is reachable on http://${WEB_HOST}:${WEB_PORT}. Continuing with existing instance.`,
        );
        holdProcessOpen();
        return;
      }
    }

    process.exit(code ?? 0);
  });
}

main().catch((error) => {
  console.error("[dev:web] Failed to bootstrap WEB:", error);
  process.exit(1);
});
