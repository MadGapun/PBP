import { ShieldAlert, TerminalSquare } from "lucide-react";
import { startTransition, useEffect, useEffectEvent, useRef, useState } from "react";

import { api, postJson } from "@/api";
import { useApp } from "@/app-context";
import SourceSelectionList from "@/components/SourceSelectionList";
import {
  Button,
  Card,
  Field,
  LoadingPanel,
  SectionHeading,
  TextInput,
} from "@/components/ui";

export default function SettingsPage() {
  const { reloadKey, refreshChrome, pushToast } = useApp();
  const [loading, setLoading] = useState(true);
  const [sources, setSources] = useState([]);
  const [logs, setLogs] = useState([]);
  const [resetConfirm, setResetConfirm] = useState("");
  const [loginJobs, setLoginJobs] = useState({});
  const loginPollersRef = useRef(new Map());

  const loadPage = useEffectEvent(async () => {
    try {
      const [sourceRows, logsData] = await Promise.all([
        api("/api/sources"),
        api("/api/logs?lines=100"),
      ]);
      startTransition(() => {
        setSources(sourceRows || []);
        setLogs(logsData?.lines || []);
        setLoading(false);
      });
    } catch (error) {
      pushToast(`Einstellungen konnten nicht geladen werden: ${error.message}`, "danger");
      startTransition(() => setLoading(false));
    }
  });

  useEffect(() => {
    setLoading(true);
    loadPage();
  }, [reloadKey]);

  useEffect(() => {
    return () => {
      loginPollersRef.current.forEach((handle) => window.clearInterval(handle));
      loginPollersRef.current.clear();
    };
  }, []);

  function trackLoginJob(sourceKey, jobId) {
    const previous = loginPollersRef.current.get(sourceKey);
    if (previous) {
      window.clearInterval(previous);
    }

    const handle = window.setInterval(async () => {
      try {
        const job = await api(`/api/background-jobs/${jobId}`);
        startTransition(() => {
          setLoginJobs((current) => ({
            ...current,
            [sourceKey]: {
              status: job.status,
              message: job.message || "",
              jobId,
            },
          }));
        });

        if (job.status !== "running") {
          window.clearInterval(handle);
          loginPollersRef.current.delete(sourceKey);
          if (job.status === "fertig") {
            pushToast(job.message || "Login abgeschlossen.", "success");
          } else if (job.status === "fehler") {
            pushToast(job.message || "Login konnte nicht abgeschlossen werden.", "danger");
          }
        }
      } catch (error) {
        window.clearInterval(handle);
        loginPollersRef.current.delete(sourceKey);
        pushToast(`Login-Status konnte nicht geladen werden: ${error.message}`, "danger");
      }
    }, 1500);

    loginPollersRef.current.set(sourceKey, handle);
  }

  async function startSourceLogin(source) {
    try {
      const response = await postJson(`/api/sources/${source.key}/login`, {});
      startTransition(() => {
        setLoginJobs((current) => ({
          ...current,
          [source.key]: {
            status: "running",
            message: response.nachricht || "",
            jobId: response.job_id,
          },
        }));
      });
      pushToast(response.nachricht || `${source.name}: Login wird gestartet.`, "sky");
      trackLoginJob(source.key, response.job_id);
    } catch (error) {
      pushToast(`Login konnte nicht gestartet werden: ${error.message}`, "danger");
    }
  }

  async function toggleSource(source, checked) {
    const previousSources = sources;
    const nextSources = sources.map((item) =>
      item.key === source.key ? { ...item, active: checked } : item
    );

    startTransition(() => setSources(nextSources));

    try {
      await postJson("/api/sources", {
        active_sources: nextSources.filter((item) => item.active).map((item) => item.key),
      });
      await refreshChrome({ quiet: true });

      if (checked && source.login_erforderlich) {
        await startSourceLogin(source);
      }
    } catch (error) {
      startTransition(() => setSources(previousSources));
      pushToast(`Quelle konnte nicht aktualisiert werden: ${error.message}`, "danger");
    }
  }

  async function performReset() {
    try {
      await postJson("/api/reset", { confirm: "RESET" });
      pushToast("Factory Reset ausgeführt. Seite wird neu geladen.", "success");
      window.setTimeout(() => window.location.reload(), 1200);
    } catch (error) {
      pushToast(`Reset fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  if (loading) return <LoadingPanel label="Einstellungen werden geladen..." />;

  return (
    <div id="page-einstellungen" className="page active">
      <div className="mb-6 flex items-baseline justify-between gap-4">
        <h1 className="font-display text-xl font-semibold text-ink">Einstellungen</h1>
      </div>

      <div className="grid gap-6">
        <Card className="rounded-2xl">
          <SectionHeading title="Quellen" description="Welche Jobportale aktiv durchsucht werden." />
          <SourceSelectionList
            sources={sources}
            loginJobs={loginJobs}
            onToggle={toggleSource}
            onStartLogin={startSourceLogin}
          />
        </Card>

        <Card className="rounded-2xl">
          <SectionHeading title="Runtime-Logs" description="Die letzten Zeilen aus dem Dashboard-Log für schnelle Diagnose." />
          <div className="soft-scrollbar glass-log max-h-[28rem] overflow-y-auto p-4">
            {logs.length ? logs.map((line, index) => <p key={`${index}-${line.slice(0, 20)}`}>{line}</p>) : <p>Keine Logs gefunden.</p>}
          </div>
        </Card>

        <Card className="glass-banner glass-banner-danger rounded-2xl">
          <SectionHeading title="Factory Reset" description="Löscht alle Daten und setzt die App in einen sauberen Zustand zurück." />
          <div className="flex flex-col items-center gap-4">
            <div className="flex items-center gap-3">
              <div className="glass-icon glass-icon-danger h-10 w-10 shrink-0">
                <ShieldAlert size={16} />
              </div>
              <p className="text-sm text-muted">
                Gib <strong className="text-ink">RESET</strong> ein, wenn du wirklich alle Profile, Stellen, Dokumente und Bewerbungen löschen willst.
              </p>
            </div>
            <div className="flex items-end gap-3">
              <Field label="Bestätigung">
                <TextInput className="!w-48" value={resetConfirm} onChange={(event) => setResetConfirm(event.target.value)} placeholder="RESET" />
              </Field>
              <Button variant="danger" disabled={resetConfirm !== "RESET"} onClick={performReset}>
                <TerminalSquare size={15} />
                Alles löschen
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
