import { Activity, Download, Eye, HardDrive, Package, ShieldAlert, TerminalSquare, Trash2 } from "lucide-react";
import { startTransition, useEffect, useEffectEvent, useRef, useState } from "react";

import { api, deleteRequest, postJson } from "@/api";
import { useApp } from "@/app-context";
import SourceSelectionList from "@/components/SourceSelectionList";
import {
  Badge,
  Button,
  Card,
  Field,
  LoadingPanel,
  SectionHeading,
  TextInput,
} from "@/components/ui";

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function SettingsPage() {
  const { reloadKey, refreshChrome, pushToast } = useApp();
  const [loading, setLoading] = useState(true);
  const [sources, setSources] = useState([]);
  const [logs, setLogs] = useState([]);
  const [resetConfirm, setResetConfirm] = useState("");
  const [loginJobs, setLoginJobs] = useState({});
  const [impulseEnabled, setImpulseEnabled] = useState(true);
  const [health, setHealth] = useState(null);
  const [privacy, setPrivacy] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState("");
  const [exporting, setExporting] = useState(false);
  const [settingsTab, setSettingsTab] = useState("quellen");
  const loginPollersRef = useRef(new Map());

  const loadPage = useEffectEvent(async () => {
    try {
      const [sourceRows, logsData, impulseData, healthData, privacyData] = await Promise.all([
        api("/api/sources"),
        api("/api/logs?lines=100"),
        api("/api/daily-impulse").catch(() => null),
        api("/api/health").catch(() => null),
        api("/api/privacy-info").catch(() => null),
      ]);
      startTransition(() => {
        setSources(sourceRows || []);
        setLogs(logsData?.lines || []);
        if (impulseData) setImpulseEnabled(impulseData.enabled !== false);
        setHealth(healthData);
        setPrivacy(privacyData);
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

  async function exportData() {
    setExporting(true);
    try {
      const resp = await fetch("/api/export-package");
      if (!resp.ok) throw new Error("Export fehlgeschlagen");
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `pbp_export_${new Date().toISOString().slice(0, 10)}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      pushToast("Export heruntergeladen.", "success");
    } catch (error) {
      pushToast(`Export fehlgeschlagen: ${error.message}`, "danger");
    } finally {
      setExporting(false);
    }
  }

  async function deleteAllData() {
    try {
      await deleteRequest("/api/privacy-delete-all", { confirm: "ALLES_LOESCHEN" });
      pushToast("Alle Daten geloescht. Seite wird neu geladen.", "success");
      window.setTimeout(() => window.location.reload(), 1500);
    } catch (error) {
      pushToast(`Loeschen fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  if (loading) return <LoadingPanel label="Einstellungen werden geladen..." />;

  const tabs = [
    { id: "quellen", label: "Quellen" },
    { id: "system", label: "System" },
    { id: "datenschutz", label: "Datenschutz" },
    { id: "logs", label: "Logs" },
    { id: "gefahrenzone", label: "Gefahrenzone" },
  ];

  return (
    <div id="page-einstellungen" className="page active">
      <div className="mb-6 flex items-baseline justify-between gap-4">
        <h1 className="font-display text-xl font-semibold text-ink">Einstellungen</h1>
      </div>

      {/* #399: Horizontal tabs below header — consistent with other pages */}
      <div className="flex flex-wrap gap-1 mb-6">
        {tabs.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setSettingsTab(t.id)}
            className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors whitespace-nowrap ${
              settingsTab === t.id
                ? "bg-sky/15 text-sky"
                : "text-muted/50 hover:text-muted hover:bg-white/5"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="grid gap-6">
        {/* ── Quellen Tab ── */}
        {settingsTab === "quellen" && (
          <>
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
              <SectionHeading title="Dashboard" description="Allgemeine Dashboard-Einstellungen." />
              <label className="flex cursor-pointer items-center gap-3 text-sm text-muted">
                <input
                  type="checkbox"
                  checked={impulseEnabled}
                  onChange={async () => {
                    try {
                      const res = await postJson("/api/daily-impulse/toggle");
                      setImpulseEnabled(res.enabled);
                    } catch (error) {
                      pushToast(`Fehler: ${error.message}`, "danger");
                    }
                  }}
                  className="h-4 w-4 accent-sky-500"
                />
                Tagesimpuls im Dashboard anzeigen
              </label>
            </Card>
          </>
        )}

        {/* ── System / Health Tab (#290) ── */}
        {settingsTab === "system" && health && (
          <Card className="rounded-2xl">
            <SectionHeading title="System-Info" description="Technische Details fuer Fehlerdiagnose." />
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="glass-card p-3 space-y-1.5">
                <div className="flex items-center gap-2 text-sm font-medium text-ink">
                  <Activity size={14} className="text-sky" />
                  Versionen
                </div>
                <p className="text-xs text-muted/60">PBP: <span className="text-ink">v{health.pbp_version}</span></p>
                <p className="text-xs text-muted/60">Python: <span className="text-ink">{health.python_version}</span></p>
                <p className="text-xs text-muted/60">Plattform: <span className="text-ink">{health.platform_detail}</span></p>
              </div>
              <div className="glass-card p-3 space-y-1.5">
                <div className="flex items-center gap-2 text-sm font-medium text-ink">
                  <HardDrive size={14} className="text-teal" />
                  Speicher
                </div>
                <p className="text-xs text-muted/60">Datenbank: <span className="text-ink">{health.db_size_mb} MB</span></p>
                <p className="text-xs text-muted/60">Dokumente: <span className="text-ink">{health.document_count} Dateien</span></p>
                <p className="text-xs text-muted/60 break-all">Pfad: <span className="text-ink">{health.data_dir}</span></p>
              </div>
            </div>
            <div className="mt-4 glass-card p-3">
              <div className="flex items-center gap-2 text-sm font-medium text-ink mb-2">
                <Package size={14} className="text-amber" />
                Module
              </div>
              <div className="flex flex-wrap gap-2">
                {health.modules && Object.entries(health.modules).map(([mod, ver]) => (
                  <Badge key={mod} tone={ver ? "success" : "neutral"}>
                    {mod} {ver || "—"}
                  </Badge>
                ))}
              </div>
            </div>
            {health.mcp_connection && (
              <div className="mt-4 glass-card p-3">
                <p className="text-xs text-muted/60">
                  MCP-Verbindung: <span className={`font-medium ${
                    health.mcp_connection.status === "connected" ? "text-teal" :
                    health.mcp_connection.status === "unknown" ? "text-amber" : "text-red-400"
                  }`}>{health.mcp_connection.status}</span>
                  {health.mcp_connection.last_tool && <> — Letztes Tool: <span className="text-ink">{health.mcp_connection.last_tool}</span></>}
                </p>
              </div>
            )}
          </Card>
        )}

        {/* ── Datenschutz Tab (#287) ── */}
        {settingsTab === "datenschutz" && (
          <>
            <Card className="rounded-2xl">
              <SectionHeading title="Datenschutz" description="Wo liegen deine Daten und was wird wohin gesendet." />
              {privacy && (
                <div className="space-y-4">
                  <div className="glass-card p-3">
                    <h3 className="text-sm font-medium text-ink mb-2 flex items-center gap-2">
                      <Eye size={14} className="text-sky" />
                      Datenfluss
                    </h3>
                    <div className="space-y-2 text-xs">
                      <div>
                        <span className="text-teal font-medium">Nur lokal gespeichert:</span>
                        <p className="text-muted/60 mt-0.5">{privacy.data_flow.local_only.join(", ")}</p>
                      </div>
                      <div>
                        <span className="text-amber font-medium">An Claude Desktop (du kontrollierst):</span>
                        <p className="text-muted/60 mt-0.5">{privacy.data_flow.sent_to_claude.join(", ")}</p>
                      </div>
                      <div>
                        <span className="text-sky font-medium">Externe Anfragen:</span>
                        <p className="text-muted/60 mt-0.5">{privacy.data_flow.external_requests.join(", ")}</p>
                      </div>
                    </div>
                  </div>

                  <div className="glass-card p-3">
                    <h3 className="text-sm font-medium text-ink mb-2">Gespeicherte Daten</h3>
                    <div className="grid grid-cols-2 gap-2 text-xs text-muted/60">
                      <p>Profile: <span className="text-ink">{privacy.counts.profiles}</span></p>
                      <p>Stellen: <span className="text-ink">{privacy.counts.jobs}</span></p>
                      <p>Bewerbungen: <span className="text-ink">{privacy.counts.applications}</span></p>
                      <p>Dokumente: <span className="text-ink">{privacy.counts.documents}</span></p>
                    </div>
                    <p className="text-[11px] text-muted/40 mt-2 break-all">Speicherort: {privacy.storage.data_dir}</p>
                  </div>
                </div>
              )}
            </Card>

            <Card className="rounded-2xl">
              <SectionHeading title="Daten exportieren" description="Alle Daten als ZIP herunterladen (Backup / Portabilitaet)." />
              <Button variant="secondary" onClick={exportData} disabled={exporting}>
                <Download size={15} />
                {exporting ? "Wird erstellt..." : "Export-Paket herunterladen"}
              </Button>
            </Card>

            <Card className="rounded-2xl border border-amber/20 bg-amber/5">
              <p className="text-xs text-muted">
                Moechtest du Daten loeschen? Alle Optionen findest du im Tab{" "}
                <button type="button" className="text-sky underline" onClick={() => setSettingsTab("gefahrenzone")}>Gefahrenzone</button>.
              </p>
            </Card>
          </>
        )}

        {/* ── Logs Tab ── */}
        {settingsTab === "logs" && (
          <Card className="rounded-2xl">
            <SectionHeading title="Runtime-Logs" description="Die letzten Zeilen aus dem Dashboard-Log fuer schnelle Diagnose." />
            <div className="soft-scrollbar glass-log max-h-[28rem] overflow-y-auto p-4">
              {logs.length ? logs.map((line, index) => <p key={`${index}-${line.slice(0, 20)}`}>{line}</p>) : <p>Keine Logs gefunden.</p>}
            </div>
          </Card>
        )}

        {/* ── Gefahrenzone Tab (#378: konsolidiert) ── */}
        {settingsTab === "gefahrenzone" && (
          <div className="grid gap-6">
            <Card className="glass-banner glass-banner-danger rounded-2xl">
              <SectionHeading title="Alle Daten loeschen (DSGVO)" description="Loescht Datenbank und Dokumente unwiderruflich. Das wird geloescht: Profil, Bewerbungen, Stellen, Dokumente, Einstellungen." />
              <div className="flex flex-col items-center gap-4">
                <div className="flex items-center gap-3">
                  <div className="glass-icon glass-icon-danger h-10 w-10 shrink-0">
                    <Trash2 size={16} />
                  </div>
                  <p className="text-sm text-muted">
                    Gib <strong className="text-ink">ALLES_LOESCHEN</strong> ein, um alle Daten unwiderruflich zu entfernen.
                  </p>
                </div>
                <div className="flex items-end gap-3">
                  <Field label="Bestaetigung">
                    <TextInput className="!w-56" value={deleteConfirm} onChange={(e) => setDeleteConfirm(e.target.value)} placeholder="ALLES_LOESCHEN" />
                  </Field>
                  <Button variant="danger" disabled={deleteConfirm !== "ALLES_LOESCHEN"} onClick={deleteAllData}>
                    <Trash2 size={15} />
                    Endgueltig loeschen
                  </Button>
                </div>
              </div>
            </Card>

            <Card className="glass-banner glass-banner-danger rounded-2xl">
              <SectionHeading title="Factory Reset" description="Setzt die App in einen sauberen Zustand zurueck. Das wird geloescht: Alle Profile, Stellen, Bewerbungen, Dokumente — die App wird wie neu." />
              <div className="flex flex-col items-center gap-4">
                <div className="flex items-center gap-3">
                  <div className="glass-icon glass-icon-danger h-10 w-10 shrink-0">
                    <ShieldAlert size={16} />
                  </div>
                  <p className="text-sm text-muted">
                    Gib <strong className="text-ink">RESET</strong> ein, wenn du wirklich alles zuruecksetzen willst.
                  </p>
                </div>
                <div className="flex items-end gap-3">
                  <Field label="Bestaetigung">
                    <TextInput className="!w-48" value={resetConfirm} onChange={(event) => setResetConfirm(event.target.value)} placeholder="RESET" />
                  </Field>
                  <Button variant="danger" disabled={resetConfirm !== "RESET"} onClick={performReset}>
                    <TerminalSquare size={15} />
                    Factory Reset
                  </Button>
                </div>
              </div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
