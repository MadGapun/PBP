// #487: Global sichtbare Status-Badge fuer die Jobsuche.
// Sitzt in der Sidebar direkt unter der MCP-Verbindung, damit der User
// auf allen Seiten sieht, ob im Hintergrund gerade gescraped wird.
// Quelle: existierender /api/jobsuche/running-Endpoint — siehe
// dashboard.py (api_jobsuche_running).
//
// #1033: Beschriftung und Ton kommen aus lib/jobsucheHinweis.js — dort
// stehen die vier Zustaende samt Test. Bis v1.7.90 zeigte das Kaestchen
// nach jedem Lauf "0 neue Stellen", auch nach Abbruch.

import { useEffect, useRef, useState } from "react";
import { Loader2, CheckCircle2, AlertTriangle, Info } from "lucide-react";

import { jobsucheHinweis } from "@/lib/jobsucheHinweis";

const POLL_RUNNING_MS = 3000;
const POLL_IDLE_MS = 30000;

const TON = {
  ok: { Icon: CheckCircle2, klassen: "bg-teal/15 text-teal hover:bg-teal/25" },
  hinweis: { Icon: Info, klassen: "bg-sky/15 text-sky hover:bg-sky/25" },
  fehler: { Icon: AlertTriangle, klassen: "bg-coral/15 text-coral hover:bg-coral/25" },
};

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
  const [lastFinished, setLastFinished] = useState(null);  // Hinweis bis der User zu den Stellen wechselt
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
        // Uebergang running → fertig: letzten Stand aus /api/jobsuche/last holen
        if (wasRunningRef.current) {
          wasRunningRef.current = false;
          try {
            const res = await fetch("/api/jobsuche/last");
            if (res.ok) {
              const hinweis = jobsucheHinweis(await res.json());
              if (hinweis) setLastFinished(hinweis);
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
        className="flex items-center gap-1.5 rounded-lg bg-sky/15 px-2 py-1.5 text-[11px] font-medium text-sky"
        title={state.message || "Jobsuche läuft im Hintergrund"}
      >
        <Loader2 className="h-3 w-3 animate-spin" />
        <span>
          Jobsuche {state.progress > 0 ? `${state.progress}%` : "laeuft…"}
        </span>
      </div>
    );
  }

  if (lastFinished) {
    const { Icon, klassen } = TON[lastFinished.ton] || TON.ok;
    return (
      <button
        type="button"
        onClick={() => {
          setLastFinished(null);
          onNavigateToJobs?.();
        }}
        className={`flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] font-medium cursor-pointer transition-colors ${klassen}`}
        title={[lastFinished.titel, "Klicken: zu Stellen wechseln"].filter(Boolean).join(" — ")}
      >
        <Icon className="h-3 w-3" />
        <span>{lastFinished.text}</span>
      </button>
    );
  }

  // Idle — dezenter Hinweis auf letzte Suche (optional, nur wenn vorhanden)
  return null;
}
