import http from "node:http";
import { spawn } from "node:child_process";

const API_HOST = process.env.BA_API_HOST || "127.0.0.1";
const API_PORT = Number(process.env.BA_DASHBOARD_PORT || process.env.BA_API_PORT || "8200");
const API_STATUS_PATH = process.env.BA_API_STATUS_PATH || "/api/status";
const API_COMPAT_PATH =
  process.env.BA_API_COMPAT_PATH || "/api/document/__route_probe__/extraction";
const API_CHECK_TIMEOUT_MS = Number(process.env.BA_API_CHECK_TIMEOUT_MS || "1200");
const API_REACHABILITY_ATTEMPTS = Number(process.env.BA_API_REACHABILITY_ATTEMPTS || "4");
const API_REACHABILITY_INTERVAL_MS = Number(process.env.BA_API_REACHABILITY_INTERVAL_MS || "500");

function requestStatus(pathname) {
  return new Promise((resolve) => {
    const req = http.request(
      {
        host: API_HOST,
        port: API_PORT,
        path: pathname,
        method: "GET",
        timeout: API_CHECK_TIMEOUT_MS,
      },
      (res) => {
        res.resume();
        resolve(res.statusCode || 0);
      },
    );

    req.on("timeout", () => {
      req.destroy();
      resolve(0);
    });
    req.on("error", () => resolve(0));
    req.end();
  });
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function requestStatusWithRetries(pathname, attempts = API_REACHABILITY_ATTEMPTS) {
  const maxAttempts = Math.max(1, attempts);
  for (let i = 0; i < maxAttempts; i += 1) {
    const statusCode = await requestStatus(pathname);
    if (statusCode >= 100) {
      return statusCode;
    }
    if (i < maxAttempts - 1) {
      await sleep(API_REACHABILITY_INTERVAL_MS);
    }
  }
  return 0;
}

function holdProcessOpen() {
  // Keep process alive so `concurrently -k` does not stop WEB immediately.
  // `stdin.resume()` alone is not reliable in non-interactive shells.
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

async function useRunningApi() {
  const compatStatus = await requestStatusWithRetries(API_COMPAT_PATH, 2);
  if (compatStatus === 404) {
    console.error(
      `[dev:api] API on http://${API_HOST}:${API_PORT} is reachable but outdated (missing ${API_COMPAT_PATH}).`,
    );
    console.error(
      "[dev:api] Bitte alte API-Prozesse beenden und `pnpm run dev` neu starten.",
    );
    return false;
  }

  console.log(
    `[dev:api] API already reachable on http://${API_HOST}:${API_PORT}. Using existing instance.`,
  );
  holdProcessOpen();
  return true;
}

async function main() {
  const statusCode = await requestStatusWithRetries(API_STATUS_PATH);
  const reachable = statusCode >= 100;
  if (reachable) {
    const compatible = await useRunningApi();
    if (!compatible) {
      process.exit(1);
    }
    return;
  }

  const child = spawn("pnpm", ["run", "dev:api:raw"], {
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
      // Defensive fallback: another process may have claimed the port while we were spawning.
      const postStatus = await requestStatusWithRetries(
        API_STATUS_PATH,
        Math.max(API_REACHABILITY_ATTEMPTS, 8),
      );
      if (postStatus >= 100) {
        const compatible = await useRunningApi();
        if (compatible) {
          console.warn(
            `[dev:api] Child API process exited with code ${code}, but API became reachable. Continuing with existing instance.`,
          );
          return;
        }
      }
    }

    process.exit(code ?? 0);
  });
}

main().catch((error) => {
  console.error("[dev:api] Failed to bootstrap API:", error);
  process.exit(1);
});
