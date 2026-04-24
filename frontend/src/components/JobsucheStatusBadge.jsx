// #487: Global sichtbare Status-Badge fuer die Jobsuche.
// Sitzt in der Sidebar direkt unter der MCP-Verbindung, damit der User
// auf allen Seiten sieht, ob im Hintergrund gerade gescraped wird.
// Quelle: existierender /api/jobsuche/running-Endpoint — siehe
// dashboard.py (api_jobsuche_running).

import { useEffect, useRef, useState } from "react";
import { Loader2, CheckCircle2, AlertTriangle, Clock } from "lucide-react";

const POLL_RUNNING_MS = 3000;
const POLL_IDLE_MS = 30000;

async function fetchRunning() {
  try {
    const res = await fetch("/api/jobsuche/running");
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export default function JobsucheStatusBadge({ onNavigateToJobs }) {
  const [state, setState] = useState({ running: false, progress: 0, message: "" });
  const [lastFinished, setLastFinished] = useState(null);  // {count, at} bis der User zu den Stellen wechselt
  const wasRunningRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    let timer = null;

    const tick = async () => {
      if (cancelled) return;
      const data = await fetchRunning();
      if (cancelled) return;
      if (data?.running) {
        setState({
          running: true,
          progress: data.progress || 0,
          message: data.message || "",
          jobId: data.job_id,
        });
        wasRunningRef.current = true;
      } else {
        // Uebergang running → fertig: letzten Zaehlstand aus /api/jobsuche/last holen
        if (wasRunningRef.current) {
          wasRunningRef.current = false;
          try {
            const res = await fetch("/api/jobsuche/last");
            if (res.ok) {
              const last = await res.json();
              if (last?.neue_stellen !== undefined) {
                setLastFinished({
                  count: last.neue_stellen,
                  timeoutQuellen: last.timeout_quellen || 0,
                  at: Date.now(),
                });
              }
            }
          } catch { /* ignore */ }
        }
        setState({ running: false, progress: 0, message: "" });
      }
      const nextDelay = data?.running ? POLL_RUNNING_MS : POLL_IDLE_MS;
      timer = window.setTimeout(tick, nextDelay);
    };
    tick();

    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, []);

  if (state.running) {
    return (
      <div
        className="flex items-center gap-1.5 rounded-lg bg-iris/15 px-2 py-1.5 text-[11px] font-medium text-iris"
        title={state.message || "Jobsuche laeuft im Hintergrund"}
      >
        <Loader2 className="h-3 w-3 animate-spin" />
        <span>
          Jobsuche {state.progress > 0 ? `${state.progress}%` : "laeuft…"}
        </span>
      </div>
    );
  }

  if (lastFinished) {
    const hasWarning = lastFinished.timeoutQuellen > 0;
    const Icon = hasWarning ? AlertTriangle : CheckCircle2;
    const tone = hasWarning
      ? "bg-amber/15 text-amber hover:bg-amber/25"
      : "bg-teal/15 text-teal hover:bg-teal/25";
    const label = hasWarning
      ? `Fertig — ${lastFinished.count} neu, ${lastFinished.timeoutQuellen} Timeout`
      : `Fertig — ${lastFinished.count} neue Stellen`;
    return (
      <button
        type="button"
        onClick={() => {
          setLastFinished(null);
          onNavigateToJobs?.();
        }}
        className={`flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] font-medium cursor-pointer transition-colors ${tone}`}
        title="Klicken: zu Stellen wechseln (Badge zuruecksetzen)"
      >
        <Icon className="h-3 w-3" />
        <span>{label}</span>
      </button>
    );
  }

  // Idle — dezenter Hinweis auf letzte Suche (optional, nur wenn vorhanden)
  return null;
}
