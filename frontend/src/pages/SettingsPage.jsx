import { Activity, Bell, Database, Download, Eye, HardDrive, Monitor, Moon, Package, Palette, RotateCcw, ShieldAlert, Sun, TerminalSquare, Trash2, Upload } from "lucide-react";
import { startTransition, useEffect, useEffectEvent, useRef, useState } from "react";

import { api, apiUrl, deleteRequest, postJson, putJson } from "@/api";
import { useApp } from "@/app-context";
import SourceSelectionList from "@/components/SourceSelectionList";
import { hexToRgb, rgbToHex, THEME_TOKENS } from "@/theme";
import {
  Badge,
  Button,
  Card,
  Field,
  LoadingPanel,
  SectionHeading,
  TextInput,
} from "@/components/ui";

function ThemeEditor() {
  const {
    themeMode,
    themeCustom,
    setThemeMode,
    setThemeColor,
    resetThemeMode,
    resetAllTheme,
    defaultPalette,
    pushToast,
  } = useApp();
  const [expanded, setExpanded] = useState(null); // "light" | "dark" | null

  const modeButtons = [
    { id: "system", label: "System", Icon: Monitor, hint: "Folge OS-Einstellung" },
    { id: "light", label: "Hell", Icon: Sun, hint: "Immer helles Theme" },
    { id: "dark", label: "Dunkel", Icon: Moon, hint: "Immer dunkles Theme" },
  ];

  function renderPaletteEditor(mode) {
    const defaults = defaultPalette[mode];
    const overrides = (themeCustom && themeCustom[mode]) || {};
    return (
      <div className="mt-3 grid gap-3 rounded-xl border border-line/40 bg-shell/40 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-muted">
            Aenderungen werden lokal in deinem Browser gespeichert und sofort angewendet.
          </p>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => {
              resetThemeMode(mode);
              pushToast(`${mode === "light" ? "Helles" : "Dunkles"} Theme auf Standard zurueckgesetzt`, "success");
            }}
          >
            <RotateCcw size={14} /> Standard wiederherstellen
          </Button>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {THEME_TOKENS.map(({ key, label, hint }) => {
            const current = overrides[key] || defaults[key];
            const isOverride = Boolean(overrides[key]);
            const hex = rgbToHex(current);
            return (
              <div
                key={key}
                className="flex items-center gap-3 rounded-lg border border-line/30 bg-panel/40 p-2.5"
              >
                <input
                  type="color"
                  value={hex}
                  onChange={(e) => {
                    const rgb = hexToRgb(e.target.value);
                    if (rgb) setThemeColor(mode, key, rgb);
                  }}
                  className="h-9 w-10 cursor-pointer rounded-md border border-line/40 bg-transparent"
                  aria-label={`Farbe ${label}`}
                />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] font-medium text-ink">
                    {label}
                    {isOverride && (
                      <span className="ml-2 text-[10px] uppercase tracking-wider text-amber">Angepasst</span>
                    )}
                  </p>
                  <p className="truncate text-[11px] text-muted">{hint}</p>
                </div>
                {isOverride && (
                  <button
                    type="button"
                    onClick={() => setThemeColor(mode, key, null)}
                    className="rounded-md p-1 text-muted hover:text-ink"
                    title="Auf Standard zuruecksetzen"
                  >
                    <RotateCcw size={13} />
                  </button>
                )}
              </div>
            );
          })}
        </div>
      </div>
    );
  }

  return (
    <Card>
      <div className="mb-4 flex items-center gap-3">
        <div className="glass-icon glass-icon-sky h-10 w-10">
          <Palette size={18} />
        </div>
        <div>
          <h2 className="text-base font-semibold text-ink">Erscheinungsbild</h2>
          <p className="text-xs text-muted">Theme-Modus waehlen und Farben individuell anpassen.</p>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-2">
        {modeButtons.map(({ id, label, Icon, hint }) => {
          const active = themeMode === id;
          return (
            <button
              key={id}
              type="button"
              onClick={() => setThemeMode(id)}
              className={`flex flex-col items-center gap-1.5 rounded-xl border p-3 transition-colors ${
                active
                  ? "border-sky/40 bg-sky/10 text-sky"
                  : "border-line/40 bg-shell/40 text-muted hover:text-ink hover:border-line/60"
              }`}
              title={hint}
            >
              <Icon size={18} />
              <span className="text-sm font-medium">{label}</span>
            </button>
          );
        })}
      </div>

      <div className="grid gap-2">
        {["light", "dark"].map((mode) => {
          const isOpen = expanded === mode;
          const overrideCount = Object.keys((themeCustom && themeCustom[mode]) || {}).length;
          return (
            <div key={mode} className="rounded-xl border border-line/40">
              <button
                type="button"
                onClick={() => setExpanded(isOpen ? null : mode)}
                className="flex w-full items-center justify-between gap-3 p-3 text-left hover:bg-white/[0.03]"
              >
                <span className="flex items-center gap-2 text-sm font-medium text-ink">
                  {mode === "light" ? <Sun size={15} /> : <Moon size={15} />}
                  {mode === "light" ? "Helles Theme anpassen" : "Dunkles Theme anpassen"}
                  {overrideCount > 0 && (
                    <Badge tone="amber">{overrideCount} angepasst</Badge>
                  )}
                </span>
                <span className="text-xs text-muted">{isOpen ? "Schliessen" : "Oeffnen"}</span>
              </button>
              {isOpen && <div className="px-3 pb-3">{renderPaletteEditor(mode)}</div>}
            </div>
          );
        })}
      </div>

      <div className="mt-4 flex justify-end">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            resetAllTheme();
            pushToast("Theme komplett auf Standard zurueckgesetzt", "success");
          }}
        >
          <RotateCcw size={14} /> Alles zuruecksetzen
        </Button>
      </div>
    </Card>
  );
}

function formatBytes(bytes) {
  if (!bytes) return "0 B";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export default function SettingsPage() {
  const { chrome, reloadKey, refreshChrome, pushToast, intent, clearIntent } = useApp();
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
  const [profileDeleteConfirm, setProfileDeleteConfirm] = useState("");
  const [settingsTab, setSettingsTab] = useState("quellen");
  const [followupSettings, setFollowupSettings] = useState({ followup_default_days: 7, followup_interview_delay_days: 14 });
  const [followupSaving, setFollowupSaving] = useState(false);
  const loginPollersRef = useRef(new Map());

  // Handle incoming tab intent from navigateTo (#420)
  useEffect(() => {
    if (intent?.page === "einstellungen" && intent?.tab) {
      setSettingsTab(intent.tab);
      clearIntent();
    }
  }, [intent]);

  // beta.32: Sidebar-Sub-Nav fuer Einstellungen schickt CustomEvent
  useEffect(() => {
    const handler = (e) => {
      const tab = e.detail?.tab;
      if (tab) setSettingsTab(tab);
    };
    document.addEventListener("settings-nav", handler);
    return () => document.removeEventListener("settings-nav", handler);
  }, []);

  const loadPage = useEffectEvent(async () => {
    try {
      const [sourceRows, logsData, impulseData, healthData, privacyData, followupData] = await Promise.all([
        api("/api/sources"),
        api("/api/logs?lines=100"),
        api("/api/daily-impulse").catch(() => null),
        api("/api/health").catch(() => null),
        api("/api/privacy-info").catch(() => null),
        api("/api/settings/followup").catch(() => null),
      ]);
      startTransition(() => {
        setSources(sourceRows || []);
        setLogs(logsData?.lines || []);
        if (impulseData) setImpulseEnabled(impulseData.enabled !== false);
        setHealth(healthData);
        setPrivacy(privacyData);
        if (followupData) setFollowupSettings(followupData);
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

  async function saveFollowupSettings(next) {
    setFollowupSaving(true);
    try {
      const saved = await putJson("/api/settings/followup", next);
      if (saved?.gespeichert) {
        setFollowupSettings((prev) => ({ ...prev, ...saved.gespeichert }));
      }
      pushToast("Follow-up-Einstellungen gespeichert", "success");
    } catch (error) {
      pushToast(`Speichern fehlgeschlagen: ${error.message}`, "danger");
    } finally {
      setFollowupSaving(false);
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

  const importRef = useRef(null);

  async function exportProfile() {
    try {
      const res = await api("/api/profile/export");
      const blob = new Blob([JSON.stringify(res, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `profil_export_${new Date().toISOString().slice(0, 10)}.json`; a.click();
      URL.revokeObjectURL(url);
      pushToast("Profil exportiert", "success");
    } catch (error) {
      pushToast(`Export fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function downloadBackup() {
    try {
      const resp = await fetch(apiUrl("/api/backup"));
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `pbp_backup_${new Date().toISOString().slice(0, 10)}.db`; a.click();
      URL.revokeObjectURL(url);
      pushToast("Datenbank-Backup heruntergeladen", "success");
    } catch (error) {
      pushToast(`Backup fehlgeschlagen: ${error.message}`, "danger");
    }
  }

  async function importProfile(event) {
    const file = event.target.files?.[0];
    if (!file) return;
    try {
      const body = new FormData();
      body.append("file", file);
      await api("/api/profile/import", { method: "POST", body });
      await refreshChrome({ quiet: false });
      pushToast("Profil importiert.", "success");
    } catch (error) {
      pushToast(`Profilimport fehlgeschlagen: ${error.message}`, "danger");
    } finally {
      event.target.value = "";
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
    { id: "erscheinungsbild", label: "Erscheinungsbild" },
    { id: "datenschutz", label: "Datenschutz" },
    { id: "logs", label: "Logs" },
    { id: "gefahrenzone", label: "Gefahrenzone" },
  ];

  return (
    <div id="page-einstellungen" className="page active">
      {/* beta.35: h1 visuell weg, Top-Bar zeigt Breadcrumb. Sr-only fuer
          Tests + Screenreader. */}
      <h1 className="sr-only">Einstellungen</h1>

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

        {/* ── System / Health Tab (#290) + Follow-up-Automation (#493/#494) ── */}
        {settingsTab === "system" && (
          <Card className="rounded-2xl">
            <div className="mb-4 flex items-center gap-3">
              <div className="glass-icon glass-icon-amber h-10 w-10">
                <Bell size={18} />
              </div>
              <div>
                <h2 className="text-base font-semibold text-ink">Follow-up-Automation</h2>
                <p className="text-xs text-muted">
                  Zeitraeume fuer automatisch erzeugte Follow-ups. 0 deaktiviert das jeweilige Auto-Follow-up.
                </p>
              </div>
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Nachfrage nach Bewerbung (Tage)">
                <div className="flex items-center gap-2">
                  <TextInput
                    type="number"
                    min="0"
                    max="365"
                    value={followupSettings.followup_default_days}
                    onChange={(e) => setFollowupSettings((prev) => ({ ...prev, followup_default_days: e.target.value }))}
                    onBlur={(e) => {
                      const val = Math.max(0, Math.min(365, parseInt(e.target.value, 10) || 0));
                      saveFollowupSettings({ followup_default_days: val });
                    }}
                    disabled={followupSaving}
                  />
                  <span className="text-sm text-muted">Tage</span>
                </div>
                <p className="mt-1 text-[11px] text-muted/70">Standard: 7. Wird beim Wechsel auf „beworben" angelegt, sofern keines offen ist.</p>
              </Field>
              <Field label="Nachfrage nach Interview (Tage)">
                <div className="flex items-center gap-2">
                  <TextInput
                    type="number"
                    min="0"
                    max="365"
                    value={followupSettings.followup_interview_delay_days}
                    onChange={(e) => setFollowupSettings((prev) => ({ ...prev, followup_interview_delay_days: e.target.value }))}
                    onBlur={(e) => {
                      const val = Math.max(0, Math.min(365, parseInt(e.target.value, 10) || 0));
                      saveFollowupSettings({ followup_interview_delay_days: val });
                    }}
                    disabled={followupSaving}
                  />
                  <span className="text-sm text-muted">Tage</span>
                </div>
                <p className="mt-1 text-[11px] text-muted/70">Standard: 14. Wird nach „interview_abgeschlossen" automatisch erzeugt; alte Follow-ups dieser Bewerbung werden hinfaellig.</p>
              </Field>
            </div>
          </Card>
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

        {/* ── Erscheinungsbild Tab (#475) ── */}
        {settingsTab === "erscheinungsbild" && <ThemeEditor />}

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
              <SectionHeading title="Daten & Backup" description="Daten exportieren, sichern oder aus einer Datei importieren." />
              <div className="grid gap-3">
                <div className="glass-card p-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-ink">Komplett-Export (ZIP)</p>
                    <p className="text-xs text-muted/50">Alle Profile, Bewerbungen, Dokumente und Einstellungen als ZIP-Paket.</p>
                  </div>
                  <Button variant="secondary" size="sm" onClick={exportData} disabled={exporting}>
                    <Package size={14} />
                    {exporting ? "Erstelle..." : "Herunterladen"}
                  </Button>
                </div>
                <div className="glass-card p-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-ink">Datenbank-Backup (SQLite)</p>
                    <p className="text-xs text-muted/50">Rohe Datenbankdatei — fuer technische Wiederherstellung.</p>
                  </div>
                  <Button variant="secondary" size="sm" onClick={downloadBackup}>
                    <Database size={14} /> Herunterladen
                  </Button>
                </div>
                <div className="glass-card p-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-ink">Profil exportieren (JSON)</p>
                    <p className="text-xs text-muted/50">Nur das aktive Profil als JSON — fuer Uebertragung zwischen Installationen.</p>
                  </div>
                  <Button variant="secondary" size="sm" onClick={exportProfile}>
                    <Download size={14} /> Exportieren
                  </Button>
                </div>
                <div className="glass-card p-3 flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium text-ink">Profil importieren (JSON)</p>
                    <p className="text-xs text-muted/50">Ein zuvor exportiertes Profil wiederherstellen.</p>
                  </div>
                  <input ref={importRef} type="file" accept=".json" className="hidden" onChange={importProfile} />
                  <Button variant="secondary" size="sm" onClick={() => importRef.current?.click()}>
                    <Upload size={14} /> Importieren
                  </Button>
                </div>
              </div>
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
          <div className="grid gap-4">
            {/* v1.6.5 (#542): Bug-Report-Card mit Log-Download */}
            <Card className="rounded-2xl border-sky/20 bg-sky/[0.03]">
              <SectionHeading
                title="Bug gefunden? Log mitsenden."
                description="Der Download enthaelt die letzten Eintraege des Runtime-Logs. Beim Issue auf GitHub bitte als Anhang mitsenden — beschleunigt die Analyse drastisch."
              />
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={async () => {
                    try {
                      const resp = await fetch(apiUrl("/api/system/logs/download"));
                      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
                      const blob = await resp.blob();
                      const url = window.URL.createObjectURL(blob);
                      const a = document.createElement("a");
                      const ts = new Date().toISOString().replace(/[:T]/g, "-").slice(0, 19);
                      a.href = url;
                      a.download = `pbp-log-${ts}.log`;
                      document.body.appendChild(a);
                      a.click();
                      document.body.removeChild(a);
                      window.URL.revokeObjectURL(url);
                      pushToast("Log heruntergeladen — bei Bug-Report als Anhang mitsenden", "success", { duration: 4000 });
                    } catch (error) {
                      pushToast(`Log-Download fehlgeschlagen: ${error.message}`, "danger");
                    }
                  }}
                >
                  Log-Datei herunterladen
                </Button>
                <a
                  href="https://github.com/MadGapun/PBP/issues/new"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-xs text-sky hover:underline"
                >
                  Issue auf GitHub aufmachen →
                </a>
              </div>
              <p className="mt-3 text-[11px] text-muted/60">
                <strong className="text-amber/80">Datenschutz-Hinweis:</strong> Das Logfile kann persoenliche Daten enthalten (Firmennamen, Pfade, Job-Hashes). Pruefe es kurz vor dem Hochladen oder schwaerze sensible Stellen.
              </p>
            </Card>

            <Card className="rounded-2xl">
              <SectionHeading title="Runtime-Logs (Live-Vorschau)" description="Die letzten Zeilen aus dem Dashboard-Log fuer schnelle Diagnose." />
              <div className="soft-scrollbar glass-log max-h-[28rem] overflow-y-auto p-4">
                {logs.length ? logs.map((line, index) => <p key={`${index}-${line.slice(0, 20)}`}>{line}</p>) : <p>Keine Logs gefunden.</p>}
              </div>
            </Card>
          </div>
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

            {/* #420: Profile delete in danger zone */}
            {chrome?.profile?.name && (
              <Card className="glass-banner glass-banner-danger rounded-2xl">
                <SectionHeading title="Profil loeschen" description={`Loescht das aktive Profil "${chrome.profile.name}" inkl. aller Positionen, Skills, Bewerbungen und Dokumente unwiderruflich.`} />
                <div className="flex flex-col items-center gap-4">
                  <div className="flex items-center gap-3">
                    <div className="glass-icon glass-icon-danger h-10 w-10 shrink-0">
                      <Trash2 size={16} />
                    </div>
                    <p className="text-sm text-muted">
                      Gib den Profilnamen <strong className="text-ink">{chrome.profile.name}</strong> exakt ein, um das Profil zu loeschen.
                    </p>
                  </div>
                  <div className="flex items-end gap-3">
                    <Field label="Profilname bestaetigen">
                      <TextInput className="!w-56" value={profileDeleteConfirm} onChange={(e) => setProfileDeleteConfirm(e.target.value)} placeholder={chrome.profile.name} />
                    </Field>
                    <Button variant="danger" disabled={profileDeleteConfirm !== chrome.profile.name} onClick={async () => {
                      try {
                        await deleteRequest(`/api/profiles/${chrome.profile.id}`);
                        setProfileDeleteConfirm("");
                        pushToast("Profil geloescht.", "success");
                        refreshChrome();
                      } catch (err) {
                        pushToast(`Loeschen fehlgeschlagen: ${err.message}`, "danger");
                      }
                    }}>
                      <Trash2 size={15} />
                      Profil loeschen
                    </Button>
                  </div>
                </div>
              </Card>
            )}

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
