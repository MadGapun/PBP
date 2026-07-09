import { Activity, Bell, Database, Download, Eye, HardDrive, Monitor, Moon, Package, Palette, Pencil, RotateCcw, ShieldAlert, Sun, TerminalSquare, Trash2, Upload } from "lucide-react";
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
  Modal,
  SectionHeading,
  SelectInput,
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
    themePreset,
    setThemePreset,
    themePresets,
    pushToast,
  } = useApp();
  const [expanded, setExpanded] = useState(null); // "light" | "dark" | null

  const modeButtons = [
    { id: "system", label: "System", Icon: Monitor, hint: "Folge OS-Einstellung" },
    { id: "light", label: "Hell", Icon: Sun, hint: "Immer helles Theme" },
    { id: "dark", label: "Dunkel", Icon: Moon, hint: "Immer dunkles Theme" },
  ];

  function renderPaletteEditor(mode) {
    // v1.7.0-beta.57 (#626): Aktiver Preset ist die Basis fuer "current"
    // und fuer die Color-Picker-Vorbelegung. Bei "default" greifen die
    // klassischen DEFAULT_PALETTE-Werte.
    const presetObj = themePresets.find((p) => p.id === themePreset);
    const defaults = (presetObj && presetObj.id !== "default")
      ? (presetObj.palette[mode] || defaultPalette[mode])
      : defaultPalette[mode];
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

      {/* v1.7.0-beta.57 (#626): Vorbelegte Farb-Schemen */}
      <div className="mb-4">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-muted/70">
          Farb-Schema
        </p>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {themePresets.map((preset) => {
            const active = themePreset === preset.id;
            return (
              <button
                key={preset.id}
                type="button"
                onClick={() => {
                  setThemePreset(preset.id);
                  pushToast(`Farb-Schema: ${preset.label}`, "success",
                    { duration: 2200 });
                }}
                className={`rounded-xl border p-3 text-left transition-colors ${
                  active
                    ? "border-teal/40 bg-teal/10 text-ink"
                    : "border-line/40 bg-shell/40 text-muted hover:text-ink hover:border-line/60"
                }`}
                title={preset.description}
              >
                <div className="mb-1.5 flex items-center gap-1.5">
                  {/* Mini-Palette als Vorschau */}
                  {["teal", "amber", "coral", "sky"].map((tk) => (
                    <span
                      key={tk}
                      className="h-3 w-3 rounded-full border border-white/10"
                      style={{ background: `rgb(${preset.palette.dark[tk]})` }}
                    />
                  ))}
                </div>
                <p className="text-sm font-medium leading-tight">{preset.label}</p>
                <p className="mt-0.5 text-[11px] leading-snug text-muted/60">
                  {preset.description}
                </p>
              </button>
            );
          })}
        </div>
        <p className="mt-2 text-[11px] text-muted/60">
          Ein Schema setzt alle Farben fuer Hell + Dunkel auf einmal.
          Einzelne Tokens lassen sich darunter weiter individuell anpassen
          (Custom-Override pro Token).
        </p>
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

// v1.7.0 (#583, #512): Settings-Bereich „Lokale KI".
// Vor Installation: Erklaerung + Modell-Auswahl + Einrichten-Button.
// Nach Installation: Status, Aktiv/Pausiert/Aus, Modell wechseln, Statistik.
// v1.7.0-beta.26 (#594 Stufe 1): Lern-System-Privacy
// Default On, klare Erklaerung was lokal gesammelt wird, jederzeit aus.
function LearningPrivacyCard({ pushToast }) {
  const [stats, setStats] = useState(null);
  const [setting, setSetting] = useState(null);
  const [busy, setBusy] = useState(false);

  async function reload() {
    try {
      const [s, cfg] = await Promise.all([
        api("/api/activity/stats"),
        api("/api/settings/learning"),
      ]);
      setStats(s);
      setSetting(cfg);
    } catch (err) {
      pushToast(`Lern-System-Status laden: ${err.message}`, "danger");
    }
  }

  useEffect(() => { reload(); }, []);

  async function toggleLearning(e) {
    const flag = e.target.checked;
    setBusy(true);
    try {
      await putJson("/api/settings/learning", { learning_enabled: flag });
      // Frontend-Hook synchron updaten
      const mod = await import("@/activity-tracking");
      mod.setLearningEnabled(flag);
      await reload();
      pushToast(
        flag
          ? "Lern-Modus aktiviert. Daten bleiben lokal."
          : "Lern-Modus deaktiviert. Bestehende Daten bleiben — du kannst sie unten loeschen.",
        "success"
      );
    } catch (err) {
      pushToast(`Aenderung fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  async function clearData() {
    if (!confirm("Wirklich ALLE gesammelten Lern-Daten loeschen? Domain-Daten (Bewerbungen, Stellen, etc.) bleiben unangetastet.")) return;
    setBusy(true);
    try {
      const res = await deleteRequest("/api/activity/clear");
      pushToast(`${res?.deleted || 0} Lern-Events geloescht.`, "success");
      await reload();
    } catch (err) {
      pushToast(`Loeschen fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  if (!stats || !setting) return null;

  return (
    <Card className="rounded-2xl">
      <SectionHeading
        title="Lern-System (Privatsphaere)"
        description="PBP kann aus deinem Verhalten lernen, um sich anzupassen — alle Daten bleiben LOKAL."
      />
      <div className="space-y-3">
        <label className="flex items-start gap-3 cursor-pointer p-3 glass-card border-sky/15">
          <input
            type="checkbox"
            checked={!!setting.learning_enabled}
            onChange={toggleLearning}
            disabled={busy}
            className="mt-1 h-4 w-4 cursor-pointer"
          />
          <div className="flex-1">
            <p className="text-sm font-medium text-ink">
              Lern-Modus aktiv (empfohlen)
            </p>
            <p className="text-[12px] text-muted/70 mt-1 leading-snug">
              Wenn aktiv, sammelt PBP <strong>lokal</strong> Klicks, Scroll-
              und Verweildauer-Daten in der eigenen DB. Diese Daten <strong>verlassen
              deinen Rechner NICHT</strong>. Sie helfen PBP, sich an deinen Workflow
              anzupassen — z.B. haeufig genutzte Filter als Default zu lernen,
              ueberfluessige Klicks zu erkennen, oder mit der lokalen AI Muster
              auszuwerten. Du kannst es jederzeit ausschalten.
            </p>
            <p className="text-[11px] text-muted/50 mt-2">
              <strong>Vorteil:</strong> PBP wird mit der Zeit treffsicherer in
              Auto-Aussortierung, Filter-Vorschlaegen und passt UI an dein
              Verhalten an. Ohne Lern-Modus bleibt PBP statisch wie heute.
            </p>
          </div>
        </label>
        <div className="glass-card p-3 text-[12px] text-muted/70">
          <p><strong className="text-ink">{stats.total_events}</strong> Events insgesamt erfasst</p>
          {stats.oldest_event_at && (
            <p>Aeltester Eintrag: {new Date(stats.oldest_event_at).toLocaleDateString("de-DE")}</p>
          )}
          {stats.by_type?.length > 0 && (
            <details className="mt-2">
              <summary className="cursor-pointer text-[11px] text-muted/60">
                Verteilung nach Event-Typ ({stats.by_type.length})
              </summary>
              <ul className="mt-1 space-y-0.5 text-[11px]">
                {stats.by_type.map((t) => (
                  <li key={t.type} className="font-mono">
                    {t.type}: {t.count}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
        {stats.total_events > 0 && (
          <Button variant="secondary" size="sm" onClick={clearData} disabled={busy}>
            Alle Lern-Daten loeschen
          </Button>
        )}
      </div>
    </Card>
  );
}


// v1.7.0-beta.30 (#594 Stufe 5): Telemetrie-Sharing.
// User-Vorgabe: Default OFF, wochenweise (nicht taeglich), abschaltbar.
// Empfaenger: PBP-Service@Elwosa.de. Nichts geht automatisch raus —
// User klickt mailto:-Link, sieht Vorschau, kann selbst pruefen.
function TelemetrySharingCard({ pushToast }) {
  const [settings, setSettings] = useState(null);
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  async function reload() {
    try {
      const s = await api("/api/telemetry/settings");
      setSettings(s);
    } catch (err) {
      pushToast(`Telemetrie-Settings laden: ${err.message}`, "danger");
    }
  }
  useEffect(() => { reload(); }, []);

  async function loadPreview() {
    setBusy(true);
    try {
      const p = await api("/api/telemetry/preview");
      setPreview(p);
      setShowPreview(true);
    } catch (err) {
      pushToast(`Vorschau laden: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  async function toggleEnabled(e) {
    const enabled = e.target.checked;
    setBusy(true);
    try {
      await putJson("/api/telemetry/settings", { enabled });
      await reload();
      pushToast(
        enabled
          ? "Telemetrie-Sharing aktiviert. Du wirst nur wochenweise gefragt."
          : "Telemetrie-Sharing deaktiviert. Es geht nichts raus.",
        "success"
      );
    } catch (err) {
      pushToast(`Aenderung fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  async function changeInterval(e) {
    const v = parseInt(e.target.value, 10);
    setBusy(true);
    try {
      await putJson("/api/telemetry/settings", { interval_days: v });
      await reload();
      pushToast(
        v === 0 ? "Auto-Trigger deaktiviert" : `Intervall: alle ${v} Tage`,
        "success"
      );
    } catch (err) {
      pushToast(`Aenderung fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  function openMail() {
    if (!preview) return;
    const url =
      `mailto:${encodeURIComponent(preview.recipient)}` +
      `?subject=${encodeURIComponent(preview.mail.subject)}` +
      `&body=${encodeURIComponent(preview.mail.body)}`;
    window.open(url, "_blank");
    // Server-seitig den Share markieren — verhindert Doppel-Sendung
    // im Intervall.
    postJson("/api/telemetry/mark-shared", {})
      .then(() => reload())
      .catch(() => {});
  }

  if (!settings) return null;

  const trigger = preview?.trigger || {};

  return (
    <Card className="rounded-2xl">
      <SectionHeading
        title="Telemetrie-Sharing (optional)"
        description={`Hilf das Lern-System fuer alle PBP-Nutzer zu verbessern, indem du anonymisierte Erkenntnisse an ${settings.recipient} schickst — wochenweise (nicht taeglich), opt-in, jederzeit abschaltbar.`}
      />
      <div className="space-y-3">
        <label className="flex items-start gap-3 cursor-pointer p-3 glass-card border-sky/15">
          <input
            type="checkbox"
            checked={!!settings.enabled}
            onChange={toggleEnabled}
            disabled={busy}
            className="mt-1 h-4 w-4 cursor-pointer"
          />
          <div className="flex-1">
            <p className="text-sm font-medium text-ink">
              Telemetrie-Sharing aktiv
            </p>
            <p className="text-[12px] text-muted/70 mt-1 leading-snug">
              Wenn aktiv: PBP zeigt dir <strong>wochenweise</strong> (nicht
              taeglich) eine Vorschau, was geteilt werden koennte. Du
              entscheidest jedes Mal selbst, ob du die Mail tatsaechlich
              abschickst.
            </p>
            <p className="text-[11px] text-muted/50 mt-2">
              <strong>Was wird geteilt:</strong> nur signifikante Insights
              (≥ 5x beobachtet ODER score ≥ 0.8), aggregierte Zahlen,
              anonymisierte Workflow-Stats. <strong>Was NICHT:</strong>
              Profildaten, Job-Titel, Firmen, Anschreiben, Mails.
            </p>
          </div>
        </label>

        {settings.enabled && (
          <div className="glass-card p-3 border-sky/15 border space-y-2">
            <label className="flex items-center justify-between gap-3">
              <span className="text-sm text-ink">Frage mich…</span>
              <SelectInput
                value={String(settings.interval_days)}
                onChange={changeInterval}
                disabled={busy}
              >
                <option value="0">Nie automatisch (nur manuell)</option>
                <option value="7">Wochenweise (Standard)</option>
                <option value="14">Alle 2 Wochen</option>
                <option value="30">Monatlich</option>
              </SelectInput>
            </label>
            {settings.last_share_at && (
              <p className="text-[11px] text-muted/50">
                Letzter Share: {new Date(settings.last_share_at).toLocaleString("de-DE")}
              </p>
            )}
          </div>
        )}

        <div className="flex items-center gap-2 flex-wrap">
          <Button variant="secondary" size="sm" onClick={loadPreview} disabled={busy}>
            Jetzt Vorschau anzeigen
          </Button>
          {trigger.due === false && trigger.reason && (
            <span className="text-[11px] text-muted/50">{trigger.reason}</span>
          )}
        </div>

        {showPreview && preview && (
          <div className="glass-card p-3 border-teal/20 border space-y-2">
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-ink">Vorschau-Mail</p>
              <button
                type="button"
                onClick={() => setShowPreview(false)}
                className="text-[11px] text-muted/40 hover:text-ink"
              >
                schliessen
              </button>
            </div>
            <p className="text-[11px] text-muted/50">
              Empfaenger: <span className="font-mono text-ink">{preview.recipient}</span>
            </p>
            <p className="text-[11px] text-muted/50">
              Betreff: <span className="text-ink">{preview.mail.subject}</span>
            </p>
            <pre className="text-[11px] font-mono text-muted/80 bg-black/20 p-2 rounded max-h-64 overflow-auto whitespace-pre-wrap">
              {preview.mail.body}
            </pre>
            <div className="flex items-center gap-2">
              <Button size="sm" onClick={openMail}>
                In Mail-Client oeffnen
              </Button>
              <span className="text-[11px] text-muted/50">
                Du kannst die Mail noch bearbeiten oder verwerfen — nichts geht automatisch raus.
              </span>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}


// v1.7.0-beta.36 (#590 Aufgabe B): Profil-basierte Quellen-Empfehlung.
// Zeigt den erkannten Profil-Typ + die empfohlenen Quellen + einen
// "Empfohlene Quellen aktivieren"-Button. User-Vorgabe: PBP fuer alle
// Profil-Typen, nicht nur High-Performer.
function RecommendedSourcesCard({ sources, onToggle, pushToast }) {
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api("/api/profile/recommended-sources")
      .then((d) => { if (!cancelled) setData(d); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (!data) return null;
  if (data.type === "mixed" && data.confidence < 0.5) {
    // Wenig Datengrundlage — Card ausblenden statt Halb-Wahres zu zeigen
    return null;
  }

  const recommended = data.recommended || [];
  const sourceByKey = new Map(
    (sources || []).map((s) => [s.key, s])
  );
  const enabledIds = new Set(
    (sources || [])
      .filter((s) => s.active)
      .map((s) => s.key)
  );
  const missing = recommended.filter((id) => !enabledIds.has(id));

  async function activateAll() {
    setBusy(true);
    let activated = 0;
    for (const id of missing) {
      const src = sourceByKey.get(id);
      if (!src) continue;
      try {
        await onToggle(src, true);
        activated += 1;
      } catch {}
    }
    pushToast(
      activated > 0
        ? `${activated} Quelle${activated === 1 ? "" : "n"} aktiviert.`
        : "Bereits alles aktiv.",
      "success"
    );
    setBusy(false);
  }

  return (
    <Card className="rounded-2xl">
      <button
        type="button"
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center justify-between"
      >
        <div className="text-left">
          <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted/60">
            Empfohlene Quellen fuer dein Profil
          </p>
          <p className="text-sm text-ink mt-1">
            {data.label}
            {missing.length > 0 && (
              <span className="ml-2 text-amber/80">
                · {missing.length} noch nicht aktiv
              </span>
            )}
          </p>
        </div>
        <span className="text-muted/40 text-xs">{collapsed ? "▼" : "▲"}</span>
      </button>

      {!collapsed && (
        <div className="mt-3 space-y-3">
          <p className="text-[12px] text-muted/70">{data.rationale}</p>

          {data.reasons?.length > 0 && (
            <details>
              <summary className="cursor-pointer text-[11px] uppercase tracking-wider text-muted/50">
                Wie PBP das erkannt hat
              </summary>
              <ul className="mt-1.5 ml-4 list-disc text-[11px] text-muted/60">
                {data.reasons.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </details>
          )}

          <div>
            <p className="text-[11px] font-semibold text-muted/70 uppercase mb-2">
              Empfohlen ({recommended.length})
            </p>
            <div className="flex flex-wrap gap-1.5">
              {recommended.map((id) => {
                const isEnabled = enabledIds.has(id);
                const cls = isEnabled
                  ? "bg-teal/15 border-teal/30 text-teal"
                  : "bg-amber/[0.04] border-amber/20 text-amber/80";
                return (
                  <span
                    key={id}
                    className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] ${cls}`}
                  >
                    {isEnabled ? "✓" : "+"}
                    {id}
                  </span>
                );
              })}
            </div>
          </div>

          {missing.length > 0 && (
            <div className="flex items-center gap-2">
              <Button onClick={activateAll} disabled={busy} size="sm">
                {missing.length} fehlende empfohlene Quelle{missing.length === 1 ? "" : "n"} aktivieren
              </Button>
              <span className="text-[11px] text-muted/50">
                Du kannst jede Quelle einzeln auch wieder abschalten.
              </span>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}


// v1.7.0-beta.33 (#590-C): Health-Score-Tab im Quellen-Bereich.
// Zeigt pro Scraper Erfolgsquote, Fehlerstatus, Auto-Reactivate-Plan
// (mit Countdown bis Probe-Run) und Reaktivieren-Button.
function ScraperHealthCard({ pushToast }) {
  const [scrapers, setScrapers] = useState([]);
  const [busy, setBusy] = useState(false);

  async function reload() {
    try {
      const r = await api("/api/scraper-health");
      setScrapers(r?.scrapers || []);
    } catch {}
  }
  useEffect(() => { reload(); }, []);

  function statusOf(s) {
    if (!s.is_active) {
      // #722: Fehlerklasse differenziert das frueher pauschale "Aus".
      if (s.error_class === "tot") return "tot";
      if (s.error_class === "kaputt") return "kaputt";
      if (s.error_class === "blockiert") return "blockiert";
      if (s.reactivate_at) return "probing";  // server_weg ODER stumm-Auto
      return "off";
    }
    if (s.consecutive_failures >= 3) return "warn";
    if (s.consecutive_silent >= 2) return "silent";
    if (s.total_runs > 0 && s.total_successes / s.total_runs >= 0.7) return "ok";
    if (s.total_runs > 0) return "warn";
    return "unknown";
  }

  const STATUS_CONFIG = {
    ok:        { color: "bg-teal/80",   label: "OK" },
    warn:      { color: "bg-amber/80",  label: "Warnung" },
    silent:    { color: "bg-amber/80",  label: "Stumm" },
    probing:   { color: "bg-amber/40",  label: "Pausiert (Probe geplant)" },
    blockiert: { color: "bg-amber/70",  label: "Blockiert (403/429)" },
    tot:       { color: "bg-coral/80",  label: "Tot (404)" },
    kaputt:    { color: "bg-coral/80",  label: "Kaputt (Code-Fix)" },
    off:       { color: "bg-coral/70",  label: "Aus" },
    unknown:   { color: "bg-muted/40",  label: "Unbekannt" },
  };

  // #722: Fehlerklasse im Klartext.
  const ERROR_CLASS_LABEL = {
    tot: "Endpoint/Seite weg (404/410)",
    blockiert: "Geblockt / rate-limited (403/429)",
    server_weg: "Server kurz weg (Timeout/5xx/Verbindung)",
    kaputt: "Adapter/Parser defekt — Code-Fix noetig",
  };

  function relativeTime(iso) {
    if (!iso) return "—";
    try {
      const ts = new Date(iso);
      const now = new Date();
      const diffH = Math.round((ts - now) / 3600000);
      if (Math.abs(diffH) < 1) return "in <1h";
      if (diffH < 0) return `vor ${Math.abs(diffH)}h`;
      if (diffH < 24) return `in ${diffH}h`;
      return `in ${Math.round(diffH / 24)}d`;
    } catch {
      return iso.slice(0, 10);
    }
  }

  async function reactivate(name) {
    setBusy(true);
    try {
      await postJson(`/api/scraper-health/${name}/probe-result`, { success: true });
      pushToast(`${name} reaktiviert`, "success");
      await reload();
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  async function deactivate(name) {
    setBusy(true);
    try {
      await postJson(`/api/scraper-health/${name}/toggle`, { active: false });
      pushToast(`${name} deaktiviert`, "success");
      await reload();
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  if (scrapers.length === 0) {
    return null;
  }

  return (
    <Card className="rounded-2xl">
      <SectionHeading
        title="Quellen-Health"
        description="Erfolgsquote pro Scraper, Auto-Reactivate-Plan und Reaktivieren-Buttons."
      />
      <div className="space-y-2">
        {scrapers.map((s) => {
          const status = statusOf(s);
          const cfg = STATUS_CONFIG[status];
          const successRate = s.total_runs > 0
            ? Math.round((s.total_successes / s.total_runs) * 100)
            : 0;
          return (
            <div key={s.scraper_name} className="glass-card p-3 text-[12px]">
              <div className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2 min-w-0 flex-1">
                  <span className={`inline-block h-2 w-2 rounded-full ${cfg.color} shrink-0`} />
                  <span className="font-medium text-ink truncate">{s.scraper_name}</span>
                  <span className="text-[10px] text-muted/50">[{cfg.label}]</span>
                </div>
                <div className="flex items-center gap-2 text-[11px] text-muted/60 shrink-0">
                  <span>{successRate}% Quote</span>
                  <span>·</span>
                  <span>{s.total_successes}/{s.total_runs}</span>
                </div>
              </div>
              <div className="mt-1.5 grid grid-cols-2 gap-2 text-[10px] text-muted/50">
                <div>
                  Letzter Lauf: {s.last_run ? new Date(s.last_run).toLocaleString("de-DE") : "—"}
                </div>
                <div>
                  Letzter Erfolg: {s.last_success ? new Date(s.last_success).toLocaleDateString("de-DE") : "—"}
                  {typeof s.last_count === "number" ? ` · ${s.last_count} Treffer` : ""}
                </div>
                {s.error_class && ERROR_CLASS_LABEL[s.error_class] && (
                  <div className="col-span-2 text-muted/70">
                    Fehlerklasse: <span className="text-ink/80">{ERROR_CLASS_LABEL[s.error_class]}</span>
                  </div>
                )}
                {s.consecutive_failures > 0 && (
                  <div className="text-coral/80">
                    {s.consecutive_failures} Fehler in Folge
                  </div>
                )}
                {s.consecutive_silent > 0 && (
                  <div className="text-amber/80">
                    {s.consecutive_silent} Mal stumm
                  </div>
                )}
                {s.reactivate_at && (
                  <div className="text-amber/80">
                    Probe-Run {relativeTime(s.reactivate_at)} (Versuch {s.reactivate_attempt})
                  </div>
                )}
                {s.retry_after && (
                  <div className="text-coral/80">
                    Retry-After {relativeTime(s.retry_after)}
                  </div>
                )}
              </div>
              <div className="mt-2 flex gap-2">
                {!s.is_active && (
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={() => reactivate(s.scraper_name)}
                    disabled={busy}
                  >
                    Jetzt reaktivieren
                  </Button>
                )}
                {s.is_active && (
                  <Button
                    size="xs"
                    variant="secondary"
                    onClick={() => deactivate(s.scraper_name)}
                    disabled={busy}
                  >
                    Deaktivieren
                  </Button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}


// v1.7.0-beta.22: PBP-Start-Datum-Feld im Bericht-Tab.
// Daten vor diesem Datum werden im Bewerbungsbericht grau markiert und
// als „nachtraeglich erfasst, moeglicherweise unvollstaendig" gekennzeichnet.
// Auto-Detect aus application_events ist Default; User kann ueberschreiben.
function PbpStartDateField({ pushToast }) {
  const [data, setData] = useState(null);
  const [editing, setEditing] = useState("");
  const [saving, setSaving] = useState(false);

  async function reload() {
    try {
      const d = await api("/api/settings/pbp-start-date");
      setData(d);
      setEditing(d.override || "");
    } catch (err) {
      pushToast(`PBP-Start-Datum laden fehlgeschlagen: ${err.message}`, "danger");
    }
  }

  useEffect(() => { reload(); }, []);

  async function save() {
    setSaving(true);
    try {
      await putJson("/api/settings/pbp-start-date", { date: editing || "" });
      await reload();
      pushToast(editing ? "PBP-Start-Datum gesetzt" : "Auf Auto-Detect zurueckgesetzt", "success");
    } catch (err) {
      pushToast(`Speichern fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setSaving(false);
    }
  }

  if (!data) return null;

  return (
    <div className="mt-5 glass-card p-3 border-sky/15 border">
      <p className="text-sm font-medium text-ink mb-1">PBP-Nutzung gestartet am</p>
      <p className="text-[11px] text-muted/70 mb-3">
        Steuert, ab welchem Datum die Bewerbungen im Bericht als „mit PBP erfasst" gelten.
        Daten davor werden im PDF grau markiert (nachtraeglich erfasst, ggf. unvollstaendig).
        Default: Auto-Detect aus dem ersten Bewerbungs-Ereignis (<strong className="text-ink">{data.auto_detect || "noch keine Daten"}</strong>).
      </p>
      <div className="flex items-center gap-2 flex-wrap">
        <input
          type="date"
          value={editing}
          onChange={(e) => setEditing(e.target.value)}
          disabled={saving}
          className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-1.5 text-[13px] text-ink"
        />
        <Button size="sm" onClick={save} disabled={saving}>
          {saving ? "..." : "Speichern"}
        </Button>
        {data.override && (
          <Button size="sm" variant="secondary" onClick={() => { setEditing(""); save(); }} disabled={saving}>
            Auf Auto-Detect zuruecksetzen
          </Button>
        )}
      </div>
      <p className="text-[11px] text-muted/50 mt-2">
        Aktuell wirksam: <strong className="text-ink">{data.effective || "—"}</strong>
        {data.override ? " (User-Override)" : " (Auto-Detect)"}
      </p>
    </div>
  );
}


// v1.7.0-beta.20: Auto-Aktionen-Tab
// Schwellwerte fuer Auto-Expire (Bewerbung -> abgelaufen) und
// Auto-Followup-Reconciler. Manueller Trigger fuer Sofort-Lauf.
// v1.7.0-beta.94 (#677/#678): Hintergrund-Automatik — interne Jobsuche +
// Ollama-Lernen nach Zeitplan.
const AUTOMATIK_INTERVALS = [
  { v: 0, l: "Aus" },
  { v: 1, l: "Taeglich" },
  { v: 3, l: "Alle 3 Tage" },
  { v: 7, l: "Woechentlich" },
  { v: 14, l: "Alle 2 Wochen" },
  { v: 30, l: "Monatlich" },
];

function AutomatikSchedulerCard({ pushToast }) {
  const [status, setStatus] = useState(null);
  const [busy, setBusy] = useState(false);

  async function reload() {
    try {
      setStatus(await api("/api/automatik/settings"));
    } catch {
      /* still */
    }
  }
  useEffect(() => { reload(); }, []);

  async function saveInterval(field, value) {
    setBusy(true);
    try {
      await putJson("/api/automatik/settings", { [field]: Number(value) });
      await reload();
      pushToast("Automatik gespeichert.", "success");
    } catch (err) {
      pushToast(err?.message || "Speichern fehlgeschlagen.", "danger");
    } finally {
      setBusy(false);
    }
  }

  async function runNow(kind) {
    setBusy(true);
    try {
      const r = await postJson("/api/automatik/run-now", { kind });
      await reload();
      let msg = "Angestossen.";
      if (kind === "lernen") {
        msg = "Lern-Lauf angestossen.";
      } else if (r.status === "gestartet") {
        msg = "Interne Jobsuche gestartet.";
      } else if (r.status === "keine_internen_quellen") {
        msg = "Keine internen Quellen aktiv — nichts zu suchen.";
      } else if (r.status === "laeuft_bereits") {
        msg = "Eine Jobsuche laeuft bereits.";
      }
      pushToast(msg, "success");
    } catch (err) {
      pushToast(err?.message || "Lauf fehlgeschlagen.", "danger");
    } finally {
      setBusy(false);
    }
  }

  if (!status) return null;

  const fmt = (iso) => {
    if (!iso) return "noch nie";
    if (iso === "faellig") return "faellig";
    try {
      return new Date(iso).toLocaleString("de-DE");
    } catch {
      return iso;
    }
  };

  const renderTask = (key, titel, beschreibung, buttonLabel) => (
    <div className="glass-card p-4 space-y-2">
      <h3 className="font-medium text-ink text-sm">{titel}</h3>
      <p className="text-[12px] text-muted/60">{beschreibung}</p>
      <div className="flex items-center justify-between gap-3">
        <SelectInput
          value={String(status[key].intervall_tage)}
          onChange={(e) => saveInterval(`${key}_intervall_tage`, e.target.value)}
          disabled={busy}
        >
          {AUTOMATIK_INTERVALS.map((o) => (
            <option key={o.v} value={o.v}>{o.l}</option>
          ))}
        </SelectInput>
        <Button variant="secondary" size="sm" onClick={() => runNow(key)} disabled={busy}>
          {buttonLabel}
        </Button>
      </div>
      <p className="text-[11px] text-muted/50">
        Letzter Lauf: {fmt(status[key].letzter_lauf)} · Naechster: {fmt(status[key].naechster_lauf)}
      </p>
    </div>
  );

  return (
    <Card className="rounded-2xl">
      <SectionHeading
        title="Automatik im Hintergrund"
        description="PBP kann die interne Jobsuche und das Lernen aus deinem Verhalten/Dokumenten selbststaendig nach Zeitplan ausfuehren — solange Claude Desktop laeuft."
      />
      <div className="space-y-4">
        {renderTask(
          "jobsuche",
          "Interne Jobsuche",
          "Nur die internen Scraper-Quellen. Login-/Browser-Quellen (LinkedIn, StepStone, XING, ...) laufen weiter manuell ueber die Chrome-Extension.",
          "Jetzt suchen",
        )}
        {renderTask(
          "lernen",
          "Ollama lernt aus Verhalten + Dokumenten",
          "Analysiert regelmaessig deine Aktivitaet und Dokumente, damit Vorschlaege treffsicherer werden. Greift nur, wenn der Lern-Modus (Datenschutz-Tab) an ist.",
          "Jetzt lernen",
        )}
        <p className="text-[11px] text-muted/40">{status.hinweis}</p>
      </div>
    </Card>
  );
}

function AutoActionsTab({ pushToast }) {
  const [status, setStatus] = useState(null);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [lastResult, setLastResult] = useState(null);

  async function reload() {
    try {
      const data = await api("/api/auto-actions/status");
      setStatus(data);
    } catch (err) {
      pushToast(`Status laden fehlgeschlagen: ${err.message}`, "danger");
    }
  }

  useEffect(() => { reload(); }, []);

  async function saveSetting(key, value) {
    setSaving(true);
    try {
      await putJson("/api/auto-actions/settings", { [key]: value });
      await reload();
      pushToast("Gespeichert", "success");
    } catch (err) {
      pushToast(`Speichern fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setSaving(false);
    }
  }

  async function runNow() {
    setRunning(true);
    try {
      const r = await postJson("/api/auto-actions/run", {});
      setLastResult(r);
      await reload();
      const e = r.expire?.expired_count || 0;
      const f = r.followup_reconciler?.created_count || 0;
      pushToast(
        e + f === 0
          ? "Auto-Aktionen liefen — nichts zu tun."
          : `${e} abgelaufen, ${f} neue Follow-ups`,
        "success"
      );
    } catch (err) {
      pushToast(`Lauf fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setRunning(false);
    }
  }

  if (!status) {
    return <Card className="rounded-2xl"><p className="text-sm text-muted/60">Lade...</p></Card>;
  }

  const s = status.settings;

  return (
    <Card className="rounded-2xl">
      <SectionHeading
        title="Automatik fuer Bewerbungs-Lifecycle"
        description="PBP setzt Bewerbungen ohne Aktivitaet automatisch auf 'abgelaufen' und legt fehlende Nachfass-Erinnerungen an."
      />

      <div className="space-y-5">
        <div className="glass-card p-4 space-y-3">
          <h3 className="font-medium text-ink text-sm">Auto-Ablauf (Status -&gt; abgelaufen)</h3>
          <p className="text-[12px] text-muted/60">
            Bewerbungen werden auf <strong>abgelaufen</strong> gesetzt wenn seit
            der letzten Aktivitaet die folgende Zahl an Tagen ohne Antwort
            verstrichen ist. Sie sind dann nicht weg — falls doch noch was
            kommt, kannst du sie jederzeit zurueckholen.
          </p>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Status 'beworben' nach (Tage)">
              <input
                type="number" min={7} max={365}
                defaultValue={s.expire_default_days}
                onBlur={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (v && v !== s.expire_default_days) saveSetting("expire_default_days", v);
                }}
                disabled={saving}
                className="w-full rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-[13px] text-ink"
              />
            </Field>
            <Field label="Status 'eingangsbestaetigung' nach (Tage)">
              <input
                type="number" min={7} max={180}
                defaultValue={s.expire_eingangsbestaetigung_days}
                onBlur={(e) => {
                  const v = parseInt(e.target.value, 10);
                  if (v && v !== s.expire_eingangsbestaetigung_days) saveSetting("expire_eingangsbestaetigung_days", v);
                }}
                disabled={saving}
                className="w-full rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-[13px] text-ink"
              />
            </Field>
          </div>
        </div>

        <div className="glass-card p-4 space-y-3">
          <h3 className="font-medium text-ink text-sm">Auto-Followup (Nachfass-Erinnerungen)</h3>
          <p className="text-[12px] text-muted/60">
            Wenn eine aktive Bewerbung keinen offenen Nachfass-Follow-up hat,
            wird automatisch einer angelegt — N Tage nach der letzten Aktivitaet.
            Der Faden reisst nicht mehr ab wenn du den ersten Follow-up als
            erledigt markierst.
          </p>
          <Field label="Nachfass-Erinnerung nach (Tage seit letzter Aktivitaet)">
            <input
              type="number" min={1} max={60}
              defaultValue={s.followup_default_days}
              onBlur={(e) => {
                const v = parseInt(e.target.value, 10);
                if (v && v !== s.followup_default_days) saveSetting("followup_default_days", v);
              }}
              disabled={saving}
              className="w-full max-w-xs rounded-lg border border-white/8 bg-white/[0.03] px-3 py-2 text-[13px] text-ink"
            />
          </Field>
        </div>

        <div className="glass-card p-4 space-y-3">
          <h3 className="font-medium text-ink text-sm">Sofort-Lauf</h3>
          <p className="text-[12px] text-muted/60">
            Letzter Lauf: <strong>{status.last_run_at || "noch nie"}</strong>
          </p>
          <Button size="sm" onClick={runNow} disabled={running}>
            {running ? "Laeuft..." : "Jetzt durchlaufen"}
          </Button>
          {lastResult && (
            <div className="text-[12px] text-muted/60 space-y-1">
              <p>Letzter Lauf: <strong className="text-ink">{lastResult.expire?.expired_count || 0}</strong> abgelaufen, <strong className="text-ink">{lastResult.followup_reconciler?.created_count || 0}</strong> Follow-ups neu angelegt.</p>
            </div>
          )}
        </div>
      </div>
    </Card>
  );
}


// v1.7.0-beta.56 (#425): Granulare KI-Steuerung — Master + 7 Feature-Toggles.
// Greift fuer Claude-getriebene Tools (Jobsuche, Fit-Analyse, CV-Anpassung,
// Anschreiben, Doku-Analyse, Coaching, Ersterfassung, Hinweise).
const KI_FEATURE_DEFS = [
  { id: "jobsuche", label: "Jobsuche via Claude",
    desc: "Erlaubt Claude, jobsuche_starten() aufzurufen. Dashboard-Button bleibt unabhaengig nutzbar." },
  { id: "dokumentenanalyse", label: "Dokumentenanalyse",
    desc: "Profil-Daten aus hochgeladenen Lebenslaeufen, Zeugnissen und Anschreiben extrahieren." },
  { id: "stellenanalyse", label: "Stellenanalyse / Fit-Bewertung",
    desc: "Fit-Analyse, Skill-Gap-Analyse und Score-Verfeinerung fuer einzelne Stellen." },
  { id: "bewerbungserstellung", label: "Bewerbungs-Erstellung",
    desc: "Angepasste Lebenslaeufe, Fachprofile und Anschreiben generieren." },
  { id: "coaching", label: "Interview- und Verhandlungs-Coaching",
    desc: "Interview-Vorbereitung, Gehaltsverhandlung, Ablehnungs-Analyse." },
  { id: "ersterfassung", label: "Profil-Ersterfassung via Claude",
    desc: "Gefuehrtes Profil-Interview. Profil bleibt manuell pflegbar wenn aus." },
  { id: "guidance", label: "KI-Hinweise im Dashboard",
    desc: "Hinweise und Empfehlungen die explizit auf Claude verweisen." },
];

function KIFeaturesCard({ pushToast }) {
  const [features, setFeatures] = useState(null);
  const [busy, setBusy] = useState(false);

  async function reload() {
    try {
      const data = await api("/api/settings/ki-features");
      setFeatures(data?.features || null);
    } catch (err) {
      pushToast(`KI-Steuerung laden: ${err.message}`, "danger");
    }
  }

  useEffect(() => { reload(); }, []);

  async function patch(field, value) {
    setBusy(true);
    try {
      const res = await putJson("/api/settings/ki-features",
        { features: { [field]: value } });
      if (res?.features) setFeatures(res.features);
      pushToast(value
        ? `${field} aktiviert.`
        : `${field} deaktiviert.`, "success");
    } catch (err) {
      pushToast(`Aenderung fehlgeschlagen: ${err.message}`, "danger");
      await reload();
    } finally {
      setBusy(false);
    }
  }

  if (!features) {
    return (
      <Card className="rounded-2xl">
        <p className="text-sm text-muted/60">Lade KI-Steuerung...</p>
      </Card>
    );
  }

  const masterOff = !features.master;

  return (
    <Card className="rounded-2xl">
      <SectionHeading
        title="KI-Unterstuetzung (Claude)"
        description="Welche KI-Funktionen Claude in PBP nutzen darf. Default: alles aktiv. Aenderungen wirken sofort."
      />

      <label className="flex items-start gap-3 cursor-pointer p-3 glass-card border-sky/15 mb-4">
        <input
          type="checkbox"
          checked={!!features.master}
          onChange={(e) => patch("master", e.target.checked)}
          disabled={busy}
          className="mt-1 h-4 w-4 cursor-pointer"
        />
        <div className="flex-1">
          <p className="text-sm font-semibold text-ink">Master-Schalter</p>
          <p className="text-[12px] text-muted/70 mt-1 leading-snug">
            Wenn aus: Claude blockt ALLE KI-Operationen mit einem Hinweis,
            wo du das wieder anschaltest. Manuelle Tools (Profil pflegen,
            Bewerbungen tracken, Standard-CV exportieren) und der
            Dashboard-Button "Jetzt suchen" bleiben unabhaengig nutzbar.
          </p>
        </div>
      </label>

      <div className={`space-y-2 ${masterOff ? "opacity-50" : ""}`}>
        {KI_FEATURE_DEFS.map((f) => (
          <label
            key={f.id}
            className="flex items-start gap-3 cursor-pointer p-3 glass-card"
          >
            <input
              type="checkbox"
              checked={!!features[f.id]}
              onChange={(e) => patch(f.id, e.target.checked)}
              disabled={busy || masterOff}
              className="mt-1 h-4 w-4 cursor-pointer"
            />
            <div className="flex-1">
              <p className="text-sm font-medium text-ink">{f.label}</p>
              <p className="text-[12px] text-muted/70 mt-1 leading-snug">
                {f.desc}
              </p>
            </div>
          </label>
        ))}
      </div>

      {masterOff && (
        <p className="mt-3 text-[12px] text-amber/80">
          Master-Schalter ist aus — die einzelnen Toggles sind ohne Wirkung,
          bis der Master wieder aktiv ist.
        </p>
      )}
    </Card>
  );
}

// v1.7.0-beta.67 (#638 Stufe 5): Feedback-Loop-Anzeige.
// beta.104 (#689 / F21): Liste der Auto-Aussortierungen mit KI-Begruendung
// und Zurueckholen-Aktion — vorher zeigte nur die Kachel "N automatisch
// aussortiert", ohne dass man sah WELCHE Stellen es traf.
function AutoDismissedSection() {
  const [data, setData] = useState(null);
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState("");
  const load = () => api("/api/local-ai/auto-dismissed?limit=50").then(setData).catch(() => {});
  useEffect(() => { load(); }, []);
  if (!data || !data.count) return null;
  const restore = async (hash) => {
    setBusy(hash);
    try {
      await postJson("/api/jobs/restore", { hash });
      await load();
    } catch {} finally { setBusy(""); }
  };
  return (
    <div className="glass-card p-3 mb-4">
      <button type="button" className="w-full flex items-center justify-between text-left"
        onClick={() => setOpen(!open)}>
        <p className="text-[11px] font-semibold text-muted/70 uppercase tracking-wide">
          Was wurde aussortiert? ({data.count})
        </p>
        <span className="text-muted/50 text-xs">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="mt-2 space-y-1.5 max-h-72 overflow-y-auto pr-1">
          {data.items.map((j) => (
            <div key={j.hash} className="flex items-start justify-between gap-2 rounded-lg border border-white/[0.04] px-2.5 py-1.5">
              <div className="min-w-0 flex-1">
                <p className="text-[12px] text-ink truncate">{j.title} <span className="text-muted/50">— {j.company}</span></p>
                {j.begruendung && <p className="text-[11px] text-muted/50 truncate" title={j.begruendung}>{j.begruendung}</p>}
              </div>
              <button type="button" disabled={busy === j.hash}
                onClick={() => restore(j.hash)}
                className="shrink-0 rounded-lg bg-teal/15 px-2 py-1 text-[11px] font-semibold text-teal hover:bg-teal/25 disabled:opacity-50">
                {busy === j.hash ? "..." : "Zurueckholen"}
              </button>
            </div>
          ))}
          <p className="text-[10px] text-muted/40 pt-1">
            Zurueckgeholte Stellen erscheinen wieder im Stellen-Tab — Ollama lernt aus jeder Korrektur (Few-Shot).
          </p>
        </div>
      )}
    </div>
  );
}

// beta.104 (#689 / F21): Lernprotokoll — was die lokale KI gelernt hat,
// dauerhaft einsehbar. v1.7.6 (#689-Rest): Eintraege einzeln stummschalten
// und komplett zuruecksetzen — der User behaelt die Kontrolle darueber,
// was Ollama gelernt hat.
function LernprotokollSection() {
  const [items, setItems] = useState(null);
  const [open, setOpen] = useState(false);
  const [confirmReset, setConfirmReset] = useState(false);
  useEffect(() => {
    api("/api/learning/insights?only_active=0&limit=20")
      .then((r) => setItems(r?.items || r?.insights || []))
      .catch(() => setItems([]));
  }, []);
  if (!items || !items.length) return null;

  async function stummschalten(id) {
    try {
      await deleteRequest(`/api/learning/insights/${id}`);
    } catch {}
    setItems((cur) => cur.map((it) =>
      it.id === id ? { ...it, is_active: 0 } : it));
  }

  async function alleZuruecksetzen() {
    if (!confirmReset) {
      setConfirmReset(true);
      window.setTimeout(() => setConfirmReset(false), 5000);
      return;
    }
    try {
      await postJson("/api/learning/insights/reset", {});
    } catch {}
    setItems([]);
    setConfirmReset(false);
  }

  return (
    <div className="glass-card p-3 mb-4">
      <button type="button" className="w-full flex items-center justify-between text-left"
        onClick={() => setOpen(!open)}>
        <p className="text-[11px] font-semibold text-muted/70 uppercase tracking-wide">
          Lernprotokoll — was Ollama gelernt hat ({items.length})
        </p>
        <span className="text-muted/50 text-xs">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="mt-2 space-y-1.5 max-h-72 overflow-y-auto pr-1">
          {items.map((it, i) => (
            <div key={it.id || i}
              className={`flex items-start gap-2 rounded-lg border border-white/[0.04] px-2.5 py-1.5 ${it.is_active === 0 ? "opacity-45" : ""}`}>
              <div className="flex-1 min-w-0">
                <p className="text-[12px] text-ink">
                  {it.title || it.titel || it.insight_type}
                  {it.is_active === 0 && (
                    <span className="ml-2 text-[10px] text-muted/40">stummgeschaltet</span>
                  )}
                </p>
                {(it.recommendation || it.empfehlung) && (
                  <p className="text-[11px] text-muted/50">{it.recommendation || it.empfehlung}</p>
                )}
              </div>
              {it.id != null && it.is_active !== 0 && (
                <button type="button" onClick={() => stummschalten(it.id)}
                  className="text-[11px] text-muted/40 hover:text-coral shrink-0"
                  title="Diesen Lern-Eintrag stummschalten — er beeinflusst Hinweise und Vorschlaege nicht mehr">
                  stumm
                </button>
              )}
            </div>
          ))}
          <div className="flex items-center justify-between pt-1">
            <p className="text-[10px] text-muted/40">
              Basis: deine Aussortier-Entscheidungen + Nutzungsmuster (#594).
            </p>
            <button type="button" onClick={alleZuruecksetzen}
              className={`text-[10px] ${confirmReset ? "text-coral font-semibold" : "text-muted/40 hover:text-coral"}`}
              title="Loescht das komplette Lernprotokoll — Ollama lernt danach von vorn. Deine Stellen und Bewerbungen sind nicht betroffen.">
              {confirmReset ? "Wirklich alles loeschen? (nochmal klicken)" : "Alles zuruecksetzen"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

// Zeigt wie viele Stellen Ollama automatisch aussortiert hat und — sobald
// genug Datenbasis (>= 5) — wie treffsicher die Auto-Entscheidungen waren
// (gemessen daran wie oft der User sie korrigiert hat).
function OllamaAccuracyCard() {
  const [acc, setAcc] = useState(null);
  useEffect(() => {
    api("/api/llm/accuracy").then(setAcc).catch(() => {});
  }, []);
  if (!acc || !acc.auto_aussortiert_gesamt) {
    return null; // Noch keine Auto-Aussortierungen → Card ausblenden
  }
  const genau = acc.genauigkeit_prozent;
  const genauColor = genau == null ? "text-muted/50"
    : genau >= 85 ? "text-teal"
    : genau >= 65 ? "text-amber" : "text-coral";
  return (
    <div className="glass-card p-3 mb-4 border-teal/15">
      <p className="text-[11px] font-semibold text-muted/70 uppercase tracking-wide mb-2">
        Ollama-Leistung (Auto-Aussortierung)
      </p>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div>
          <p className="text-lg font-bold text-ink">{acc.auto_aussortiert_gesamt}</p>
          <p className="text-[10px] text-muted/60">automatisch<br/>aussortiert</p>
        </div>
        <div>
          <p className="text-lg font-bold text-amber">{acc.reaktiviert}</p>
          <p className="text-[10px] text-muted/60">von dir<br/>zurueckgeholt</p>
        </div>
        <div>
          <p className={`text-lg font-bold ${genauColor}`}>
            {genau == null ? "—" : `${genau}%`}
          </p>
          <p className="text-[10px] text-muted/60">Treffer-<br/>genauigkeit</p>
        </div>
      </div>
      <p className="text-[11px] text-muted/50 mt-2">
        {acc.datenbasis_ausreichend
          ? "Genauigkeit = Anteil der Auto-Entscheidungen, die du NICHT korrigiert hast. Je mehr du selbst aussortierst, desto besser lernt Ollama (Few-Shot)."
          : "Genauigkeit wird ab 5 Auto-Entscheidungen angezeigt — noch zu wenig Datenbasis."}
      </p>
    </div>
  );
}

function LocalAITab({ pushToast }) {
  const [status, setStatus] = useState(null);
  const [recommended, setRecommended] = useState([]);
  const [pulling, setPulling] = useState(false);
  const [pullModel, setPullModel] = useState(null);

  const reloadStatus = useEffectEvent(async (force = false) => {
    try {
      // v1.7.0-beta.62 (#638): force=true bypasst den 30s-Cache und liefert
      // immer einen frischen Status. Wichtig beim Tab-Mount damit User
      // nicht 30s lang den Status vor seiner Aktion sieht.
      const url = force ? "/api/llm/status?refresh=1" : "/api/llm/status";
      const data = await api(url);
      setStatus(data);
    } catch (err) {
      pushToast(`Lokale-KI-Status: ${err.message}`, "danger");
    }
  });

  useEffect(() => {
    // v1.7.0-beta.62: beim Tab-Mount IMMER force-refresh — User sieht
    // den echten Status, nicht den 30s-Cache.
    reloadStatus(true);
    api("/api/llm/recommended-models")
      .then((d) => setRecommended(d?.models || []))
      .catch(() => {});
  }, []);

  if (!status) {
    return <Card className="rounded-2xl"><p className="text-sm text-muted/60">Lade Lokale-KI-Status...</p></Card>;
  }

  async function setState(state) {
    try {
      await putJson("/api/llm/state", { state });
      await reloadStatus();
      pushToast(`Status gesetzt: ${state}`, "success");
    } catch (err) {
      pushToast(`Konnte Status nicht setzen: ${err.message}`, "danger");
    }
  }

  async function selectModel(modelId) {
    try {
      await putJson("/api/llm/model", { model: modelId });
      await reloadStatus();
      pushToast(`Modell gesetzt: ${modelId}`, "success");
    } catch (err) {
      pushToast(`Konnte Modell nicht setzen: ${err.message}`, "danger");
    }
  }

  async function pullModelTrigger(modelId) {
    setPulling(true);
    setPullModel(modelId);
    try {
      pushToast(`Lade ${modelId}... das kann einige Minuten dauern.`, "amber", { duration: 10000 });
      const result = await postJson("/api/llm/pull", { model: modelId });
      if (result?.status === "error") {
        pushToast(`Download fehlgeschlagen: ${result.error}`, "danger");
      } else {
        pushToast(`${modelId} ist installiert.`, "success");
        await selectModel(modelId);
        await setState("active");
      }
    } catch (err) {
      pushToast(`Download fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setPulling(false);
      setPullModel(null);
      await reloadStatus();
    }
  }

  // ── Variante A: nicht installiert / nicht erreichbar ──────────────
  if (status.ui_state === "not_installed") {
    return (
      <Card className="rounded-2xl">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-ink">Lokale KI</h2>
          <p className="text-xs text-muted">Status: Nicht erreichbar</p>
        </div>

        {/* v1.7.0-beta.60 (#637): Versuch Ollama zu starten — wenn nur
            gestoppt (Taskmanager/Reboot), startet das Backend Ollama als
            Detached-Subprocess. Wenn nicht installiert, kommt eine klare
            Fehlermeldung mit Download-Link. */}
        <div className="glass-card p-4 mb-4 border-sky/20">
          <h3 className="font-medium text-ink mb-2">Vielleicht nur gestoppt?</h3>
          <p className="text-sm text-muted/80 mb-3">
            Wenn Ollama vorher schonmal lief (z.B. nach Reboot oder Taskmanager-Stop),
            kann PBP versuchen es erneut zu starten — kein manueller Start in der
            Konsole noetig.
          </p>
          <Button
            type="button"
            size="sm"
            onClick={async () => {
              pushToast("Ollama wird gestartet...", "neutral", { duration: 2000 });
              try {
                const r = await postJson("/api/llm/start", {});
                if (r.status === "already_running") {
                  pushToast("Ollama lief bereits — Status wird neu geladen.", "success");
                  await reloadStatus();
                  return;
                }
                if (r.status === "starting") {
                  pushToast("Ollama startet — Status wird in 10-30s aktualisiert.", "success", { duration: 4000 });
                  // Polling: alle 2s, max 15 Versuche (= 30s)
                  let attempt = 0;
                  const poll = setInterval(async () => {
                    attempt += 1;
                    await reloadStatus();
                    const fresh = await api("/api/llm/status");
                    if (fresh?.ollama_available) {
                      clearInterval(poll);
                      pushToast("Ollama ist verbunden.", "success");
                    } else if (attempt >= 15) {
                      clearInterval(poll);
                      pushToast("Status nach 30s noch nicht verbunden — pruefe Logs.", "amber");
                    }
                  }, 2000);
                }
              } catch (err) {
                // Backend-Antwort mit not_installed-status hat error-Body
                const msg = err?.message || String(err);
                if (msg.includes("not_installed") || msg.includes("404")) {
                  pushToast("Ollama-Binary nicht gefunden — bitte herunterladen.", "danger", { duration: 5000 });
                } else {
                  pushToast(`Start fehlgeschlagen: ${msg}`, "danger");
                }
              }
            }}
          >
            Ollama starten
          </Button>
        </div>

        <div className="glass-card p-4 mb-4 border-coral/15">
          <h3 className="font-medium text-ink mb-2">Noch nicht installiert?</h3>
          <p className="text-sm text-muted/80 mb-3">
            Eine lokale KI auf deinem Rechner uebernimmt Routine-Aufgaben fuer PBP — z.B.
            Dokumente klassifizieren, Skills extrahieren, Stellen vorsortieren.
          </p>
          <div className="grid gap-3 sm:grid-cols-2 text-sm">
            <div>
              <p className="font-medium text-teal mb-1.5">✅ Vorteile</p>
              <ul className="space-y-0.5 text-[13px] text-muted/70">
                <li>Spart Claude-Tokens UND ist kostenlos</li>
                <li>Funktioniert auch ohne Internet</li>
                <li>Daten verlassen das Geraet nie</li>
                <li>Schneller bei Standard-Aufgaben</li>
              </ul>
            </div>
            <div>
              <p className="font-medium text-amber mb-1.5">⚠️ Nachteile</p>
              <ul className="space-y-0.5 text-[13px] text-muted/70">
                <li>Einmalig 4–5 GB Modell herunterladen</li>
                <li>Braucht 8–16 GB freien RAM</li>
                <li>Kreatives bleibt bei Claude</li>
              </ul>
            </div>
          </div>
        </div>

        <div className="glass-card p-4 mb-4">
          <h3 className="font-medium text-ink mb-2">Voraussetzung: Ollama</h3>
          <p className="text-sm text-muted/80 mb-2">
            Du brauchst Ollama auf deinem Rechner — der Sidecar, der die lokale KI laeuft.
          </p>
          <a
            href="https://ollama.com/download"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1.5 text-sky text-sm hover:underline"
          >
            Ollama herunterladen → ollama.com/download
          </a>
          <p className="text-[12px] text-muted/60 mt-2">
            Nach der Installation startet Ollama automatisch. PBP erkennt es dann hier
            und du kannst sie kuenftig auch ueber den "Ollama starten"-Button oben re-starten.
          </p>
        </div>

        <button
          type="button"
          onClick={reloadStatus}
          className="px-3 py-1.5 rounded-lg bg-white/[0.04] text-sm text-ink hover:bg-white/[0.08]"
        >
          Status neu pruefen
        </button>

        {status.error && (
          <p className="mt-3 text-[11px] text-coral/70 font-mono">
            Erkennungs-Fehler: {status.error}
          </p>
        )}
      </Card>
    );
  }

  // ── Variante B: Ollama da, kein Modell ────────────────────────────
  if (status.ui_state === "no_model") {
    return (
      <Card className="rounded-2xl">
        <div className="mb-4">
          <h2 className="text-base font-semibold text-ink">Lokale KI — Modell auswaehlen</h2>
          <p className="text-xs text-muted">Ollama erkannt. Jetzt ein Modell laden.</p>
        </div>
        <div className="space-y-2">
          {recommended.map((m) => (
            <div key={m.id} className="glass-card p-3 flex items-center justify-between gap-3">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <p className="font-medium text-ink">{m.name}</p>
                  {m.recommended && <span className="rounded bg-teal/15 px-1.5 py-0.5 text-[10px] font-bold text-teal">EMPFOHLEN</span>}
                </div>
                <p className="text-[12px] text-muted/70">
                  {m.size_gb} GB · braucht {m.ram_gb} GB RAM · {m.description}
                </p>
              </div>
              <button
                type="button"
                disabled={pulling}
                onClick={() => pullModelTrigger(m.id)}
                className="shrink-0 px-3 py-1.5 rounded-lg bg-sky/15 text-sky text-sm font-medium hover:bg-sky/25 disabled:opacity-50"
              >
                {pulling && pullModel === m.id ? "Laedt..." : `${m.size_gb} GB laden`}
              </button>
            </div>
          ))}
        </div>
        <p className="mt-3 text-[11px] text-muted/60">
          Empfehlung: Standard (Qwen 2.5 7B) — gutes Deutsch, vernuenftiger Speicher-Bedarf.
          Du kannst spaeter jederzeit das Modell wechseln.
        </p>
      </Card>
    );
  }

  // ── Variante C: Modell installiert (off / paused / active) ────────
  return (
    <Card className="rounded-2xl">
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h2 className="text-base font-semibold text-ink">Lokale KI</h2>
          <p className="text-xs text-muted">
            Modell: <span className="font-mono">{status.selected_model || "—"}</span>
            {" · "}
            Status: <span className={
              status.ui_state === "active" ? "text-teal" :
              status.ui_state === "paused" ? "text-amber" : "text-muted/50"
            }>
              {status.ui_state}
            </span>
          </p>
        </div>
      </div>

      <div className="grid gap-2 sm:grid-cols-3 mb-4">
        {[
          { value: "active", label: "Aktiv",
            desc: "PBP nutzt das lokale Modell wo moeglich" },
          { value: "paused", label: "Pausiert",
            desc: "Wie 'Aus' — alle Tasks gehen an Claude" },
          { value: "off", label: "Aus",
            desc: "Wie nicht installiert" },
        ].map((opt) => (
          <button
            key={opt.value}
            type="button"
            onClick={() => setState(opt.value)}
            className={`glass-card p-3 text-left rounded-lg transition ${
              status.ui_state === opt.value
                ? "border-teal/40 bg-teal/[0.06]"
                : "border-white/5 hover:bg-white/[0.04]"
            }`}
          >
            <p className="text-sm font-medium text-ink">{opt.label}</p>
            <p className="text-[11px] text-muted/60">{opt.desc}</p>
          </button>
        ))}
      </div>

      {/* v1.7.0-beta.25 (#591/#592): Modell-Detail-Liste mit Groesse +
          „Weitere installieren"-Block immer sichtbar */}
      <ModelDetailList
        status={status}
        recommended={recommended}
        onSelect={selectModel}
        onPull={pullModelTrigger}
        pulling={pulling}
        pullModel={pullModel}
      />

      {/* v1.7.0-beta.25 (#591): Tasks-Erklaerbox — was laeuft eigentlich lokal */}
      <div className="glass-card p-3 mb-4 border-sky/10">
        <p className="text-[11px] font-semibold text-muted/70 uppercase tracking-wide mb-2">
          Was laeuft lokal?
        </p>
        <ul className="text-[12px] text-muted/80 space-y-1 list-disc list-inside">
          <li><strong>Doku-Klassifikation</strong> — neue Uploads werden eingeordnet (Lebenslauf, Anschreiben, Mail, ...)</li>
          <li><strong>Skill-Extraktion</strong> — Skills aus Lebenslauf-Text ziehen</li>
          <li><strong>Stellen-Profil-Match</strong> — `stellen_auto_aussortieren` filtert profilbasiert</li>
          <li><strong>Mail-Klassifikation</strong> — eingehende Mails werden kategorisiert</li>
        </ul>
        <p className="text-[11px] text-muted/50 mt-2">
          Kreatives (Anschreiben, Coaching) bleibt bei Claude.
        </p>
      </div>

      {/* v1.7.0-beta.67 (#638 Stufe 5): Feedback-Loop — Ollama-Leistung */}
      <OllamaAccuracyCard />

      {/* beta.104 (#689 / F21): Transparenz — was wurde aussortiert, was gelernt */}
      <AutoDismissedSection />
      <LernprotokollSection />

      {/* v1.7.0-beta.24 (#584): Test-Verbindung-Button */}
      <TestConnectionBlock />

      <div className="border-t border-white/5 pt-3 mt-3">
        <p className="text-[11px] text-muted/60">
          Endpoint: <span className="font-mono">{status.ollama_endpoint}</span>
          {" · "}
          {status.available_models?.length || 0} Modell(e) installiert
        </p>
      </div>

      {/* v1.7.0-beta.37 (#599): Elwosa-Konfiguration */}
      <ElwosaSettingsSection pushToast={pushToast} />
    </Card>
  );
}

// v1.7.0-beta.37 (#599): Elwosa-Settings-Section im Lokale-KI-Tab.
function ElwosaSettingsSection({ pushToast }) {
  const [settings, setSettings] = useState(null);
  const [pending, setPending] = useState([]);
  const [busy, setBusy] = useState(false);

  async function reload() {
    try {
      const [s, p] = await Promise.all([
        api("/api/elwosa/settings"),
        api("/api/elwosa/pending-lines"),
      ]);
      setSettings(s);
      setPending(p?.pending || []);
    } catch {}
  }
  useEffect(() => { reload(); }, []);

  async function update(patch) {
    setBusy(true);
    try {
      const next = await putJson("/api/elwosa/settings", patch);
      setSettings(next);
      // v1.7.0-beta.41 (#612): Selbst-Reflektion. Pro geaendertem Feld
      // einen User-Action-Hook feuern — Backend mappt auf eine
      // Reflektions-Linie. Throttle: nur Reflektion fuer das prominenteste
      // Feld im Patch (sonst spammt der Slider).
      const target = pickReflectionTarget(patch);
      if (target) {
        try {
          await postJson("/api/elwosa/user-action", {
            action: "settings_change",
            target,
            payload: buildPayload(target, patch),
          });
        } catch {}
      }
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  function pickReflectionTarget(patch) {
    // Reihenfolge nach Aussagekraft — wir picken nur EINS pro Update-Call,
    // damit nicht 4 Reflektions-Linien in 2 Sekunden landen
    for (const k of [
      "tonfall_modus", "frequency", "comment_user_actions",
      "triggers_disabled", "cooldown_seconds", "enabled", "paused_until",
    ]) {
      if (k in patch && patch[k] !== undefined) return k;
    }
    return null;
  }

  function buildPayload(target, patch) {
    if (target === "triggers_disabled") {
      const prev = settings?.triggers_disabled || [];
      const next = patch.triggers_disabled || [];
      const added = next.filter((x) => !prev.includes(x));
      const removed = prev.filter((x) => !next.includes(x));
      return { value: next, added, removed };
    }
    return { value: patch[target] };
  }

  async function approveLine(id) {
    try {
      await postJson(`/api/elwosa/pending-lines/${id}/approve`, {});
      pushToast("Linie aktiviert", "success");
      reload();
    } catch (err) { pushToast(`Fehler: ${err.message}`, "danger"); }
  }

  async function rejectLine(id) {
    try {
      await deleteRequest(`/api/elwosa/pending-lines/${id}`);
      pushToast("Linie verworfen", "success");
      reload();
    } catch (err) { pushToast(`Fehler: ${err.message}`, "danger"); }
  }

  if (!settings) return null;

  return (
    <div className="border-t border-white/5 pt-4 mt-4">
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-6 w-6 items-center justify-center rounded-full bg-teal/15 text-[11px] font-semibold text-teal">E</span>
        <h3 className="text-sm font-semibold text-ink">Elwosa</h3>
      </div>
      <p className="mb-3 text-[12px] text-muted/70">
        Live-Statusanzeige der lokalen AI in der Sidebar. Kommentiert was im Hintergrund passiert, gibt gelegentlich Tipps zu Claude und PBP.
      </p>

      <label className="flex cursor-pointer items-start gap-3 mb-3">
        <input
          type="checkbox"
          checked={!!settings.enabled}
          onChange={(e) => update({ enabled: e.target.checked })}
          disabled={busy}
          className="mt-1 h-4 w-4 cursor-pointer"
        />
        <span className="text-sm text-ink">Elwosa aktiv (wenn lokale AI laeuft)</span>
      </label>

      {settings.enabled && (
        <div className="space-y-3">
          <div>
            <p className="text-[11px] font-medium text-muted/70 mb-1">Frequenz (fuer Idle/Welt/Tipp — Status-Linien sind unbegrenzt)</p>
            <div className="flex flex-wrap gap-2">
              {[
                { id: "ruhig", label: "Ruhig (3/Tag)" },
                { id: "standard", label: "Standard (8)" },
                { id: "aktiv", label: "Aktiv (15)" },
                { id: "unbegrenzt", label: "Unbegrenzt" },
              ].map((f) => (
                <button
                  key={f.id}
                  type="button"
                  onClick={() => update({ frequency: f.id })}
                  disabled={busy}
                  className={`px-3 py-1 text-[11px] rounded-md border ${settings.frequency === f.id
                    ? "border-teal bg-teal/15 text-teal"
                    : "border-white/10 text-muted hover:border-white/30"}`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* v1.7.0-beta.38 (#601): Power-User-Block */}
          <details className="border-t border-white/5 pt-3">
            <summary className="cursor-pointer text-[11px] uppercase tracking-wider text-muted/50 mb-2">
              Power-User-Optionen
            </summary>

            <div className="mt-3 space-y-3">
              <div>
                <p className="text-[11px] font-medium text-muted/70 mb-1">
                  Cooldown zwischen Nachrichten ({settings.cooldown_seconds || 90}s)
                </p>
                <input
                  type="range"
                  min={10}
                  max={300}
                  step={10}
                  value={settings.cooldown_seconds || 90}
                  onChange={(e) => update({ cooldown_seconds: parseInt(e.target.value, 10) })}
                  disabled={busy}
                  className="w-full"
                />
                <p className="text-[10px] text-muted/50">
                  Niedriger = schneller (10s minimum). Standard 90s.
                </p>
              </div>

              <label className="flex cursor-pointer items-start gap-2">
                <input
                  type="checkbox"
                  checked={!!settings.comment_user_actions}
                  onChange={(e) => update({ comment_user_actions: e.target.checked })}
                  disabled={busy}
                  className="mt-0.5 h-3.5 w-3.5"
                />
                <span className="text-[11px] text-muted">
                  Auch manuelle User-Aktionen kommentieren (klicken, sortieren, oeffnen)
                </span>
              </label>

              <div>
                <p className="text-[11px] font-medium text-muted/70 mb-1">Trigger-Klassen ausschalten</p>
                <div className="space-y-1">
                  {[
                    { id: "idle", label: "Idle (Stille-Linien)" },
                    { id: "world", label: "Welt-Bezug (Tageszeit, Feiertage)" },
                    { id: "tip", label: "Tipps & Tricks" },
                    { id: "easter_egg", label: "Easter Eggs" },
                  ].map((t) => {
                    const disabled = (settings.triggers_disabled || []).includes(t.id);
                    return (
                      <label key={t.id} className="flex cursor-pointer items-center gap-2">
                        <input
                          type="checkbox"
                          checked={disabled}
                          onChange={(e) => {
                            const cur = settings.triggers_disabled || [];
                            const next = e.target.checked
                              ? [...cur, t.id]
                              : cur.filter((x) => x !== t.id);
                            update({ triggers_disabled: next });
                          }}
                          disabled={busy}
                          className="h-3 w-3"
                        />
                        <span className="text-[11px] text-muted">
                          {t.label} {disabled && <span className="text-coral/70">(aus)</span>}
                        </span>
                      </label>
                    );
                  })}
                </div>
              </div>
            </div>
          </details>

          <div>
            <p className="text-[11px] font-medium text-muted/70 mb-1">Tonfall</p>
            <div className="flex gap-2 flex-wrap">
              {[
                { id: "standard", label: "Standard" },
                { id: "sachlich", label: "Sachlicher" },
                { id: "humorvoll", label: "Mehr Humor" },
                { id: "minimal", label: "Minimal (1/Tag)" },
              ].map((m) => (
                <button
                  key={m.id}
                  type="button"
                  onClick={() => update({ tonfall_modus: m.id })}
                  disabled={busy}
                  className={`px-3 py-1 text-[11px] rounded-md border ${settings.tonfall_modus === m.id
                    ? "border-teal bg-teal/15 text-teal"
                    : "border-white/10 text-muted hover:border-white/30"}`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {pending.length > 0 && (
            <div className="border-t border-white/5 pt-3">
              <p className="text-[11px] font-medium text-muted/70 mb-2">
                Vorgeschlagene Linien (von Claude) — {pending.length}
              </p>
              <div className="space-y-2">
                {pending.map((p) => (
                  <div key={p.id} className="rounded-md border border-white/10 bg-white/[0.02] p-2 text-[11px]">
                    <p className="text-muted/85 italic">„{p.content}"</p>
                    <p className="mt-1 text-[9px] text-muted/40">
                      {p.cluster} · {p.trigger_kind}
                    </p>
                    <div className="mt-2 flex gap-2">
                      <Button size="xs" onClick={() => approveLine(p.id)}>Akzeptieren</Button>
                      <Button size="xs" variant="secondary" onClick={() => rejectLine(p.id)}>Verwerfen</Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {settings.paused_until && new Date(settings.paused_until) > new Date() && (
            <div className="rounded-md border border-amber/20 bg-amber/[0.04] p-2 text-[11px] text-amber/80">
              Pausiert bis {new Date(settings.paused_until).toLocaleString("de-DE")}.{" "}
              <button
                type="button"
                onClick={() => update({ paused_until: "" })}
                className="underline hover:text-amber"
              >
                Zurueckholen
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// v1.7.0-beta.25 (#591/#592): Modell-Liste mit Groesse + Pull-Buttons
// fuer weitere Modelle (auch im 'active'-Zustand sichtbar).
function ModelDetailList({ status, recommended, onSelect, onPull, pulling, pullModel }) {
  const installed = status.models_detail || [];
  const installedNames = new Set((status.available_models || []));
  const moreToInstall = (recommended || []).filter((m) => !installedNames.has(m.id));

  return (
    <div className="mb-4">
      <p className="text-[11px] text-muted/60 mb-1.5">Installierte Modelle:</p>
      <div className="space-y-1.5 mb-3">
        {installed.length === 0 && status.available_models?.length > 0 && (
          /* Fallback wenn models_detail noch nicht in der Antwort ist */
          status.available_models.map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => onSelect(m)}
              className={`w-full glass-card p-2 flex items-center justify-between text-left ${
                status.selected_model === m
                  ? "border-sky/40 bg-sky/[0.05]"
                  : "border-white/5 hover:bg-white/[0.04]"
              }`}
            >
              <span className="text-[13px] font-mono text-ink">{m}</span>
              {status.selected_model === m && (
                <span className="text-[10px] font-bold text-sky uppercase">aktiv</span>
              )}
            </button>
          ))
        )}
        {installed.map((m) => (
          <button
            key={m.name}
            type="button"
            onClick={() => onSelect(m.name)}
            className={`w-full glass-card p-2 flex items-center justify-between text-left ${
              status.selected_model === m.name
                ? "border-sky/40 bg-sky/[0.05]"
                : "border-white/5 hover:bg-white/[0.04]"
            }`}
          >
            <div className="flex-1 min-w-0">
              <span className="text-[13px] font-mono text-ink">{m.name}</span>
              {m.parameter_size && (
                <span className="ml-2 text-[10px] text-muted/50">{m.parameter_size}</span>
              )}
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <span className="text-[11px] text-muted/50">{formatBytes(m.size_bytes)}</span>
              {status.selected_model === m.name && (
                <span className="text-[10px] font-bold text-sky uppercase">aktiv</span>
              )}
            </div>
          </button>
        ))}
      </div>

      {moreToInstall.length > 0 && (
        <details className="glass-card p-2">
          <summary className="text-[12px] cursor-pointer text-sky">
            + Weiteres Modell installieren ({moreToInstall.length} Vorschlaege)
          </summary>
          <div className="space-y-1.5 mt-2">
            {moreToInstall.map((m) => (
              <div key={m.id} className="flex items-center justify-between gap-2 p-2 rounded bg-white/[0.02]">
                <div className="min-w-0 flex-1">
                  <p className="text-[12px] font-medium text-ink">
                    {m.name}
                    {m.recommended && (
                      <span className="ml-2 rounded bg-teal/15 px-1 py-0.5 text-[9px] font-bold text-teal">EMPFOHLEN</span>
                    )}
                  </p>
                  <p className="text-[10px] text-muted/50">
                    {m.size_gb} GB · braucht {m.ram_gb} GB RAM
                  </p>
                </div>
                <button
                  type="button"
                  disabled={pulling}
                  onClick={() => onPull(m.id)}
                  className="shrink-0 px-2 py-1 rounded text-[11px] bg-sky/15 text-sky hover:bg-sky/25 disabled:opacity-50"
                >
                  {pulling && pullModel === m.id ? "Laedt..." : "Laden"}
                </button>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}


// v1.7.0-beta.24 (#584): Test-Verbindung-Diagnose
function TestConnectionBlock() {
  const { pushToast } = useApp();
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);

  async function runTest() {
    setRunning(true);
    setResult(null);
    try {
      const r = await postJson("/api/llm/test-connection", {});
      setResult(r);
    } catch (err) {
      pushToast(`Test fehlgeschlagen: ${err.message}`, "danger");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="border-t border-white/5 pt-3 mt-3">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[11px] font-semibold text-muted/70 uppercase tracking-wide">
          Test-Verbindung
        </p>
        <Button size="sm" onClick={runTest} disabled={running}>
          {running ? "Teste..." : "Jetzt testen"}
        </Button>
      </div>

      {!result && !running && (
        <p className="text-[11px] text-muted/40">
          Schickt einen Klassifizierungs-Task an Ollama und misst die Antwortzeit.
        </p>
      )}

      {result && (
        <div className="space-y-2 text-[12px]">
          <div className="grid gap-1">
            <p>
              Ollama:{" "}
              <span className={result.ollama_available ? "text-teal" : "text-coral"}>
                {result.ollama_available ? "erreichbar" : "nicht erreichbar"}
              </span>
            </p>
            <p>
              Endpoint:{" "}
              <span className="font-mono text-muted/70">{result.ollama_endpoint}</span>
            </p>
            <p>
              Installierte Modelle:{" "}
              <span className="text-ink">
                {(result.available_models || []).join(", ") || "—"}
              </span>
            </p>
            <p>
              Aktives Modell:{" "}
              <span className="font-mono text-sky">{result.selected_model || "—"}</span>
            </p>
            <p>
              State:{" "}
              <span className={
                result.user_state === "active" ? "text-teal" :
                result.user_state === "paused" ? "text-amber" : "text-muted/50"
              }>{result.user_state}</span>
            </p>
          </div>
          {result.test_roundtrip?.skipped ? (
            <div className="glass-card p-2 text-amber">
              ⚠ Test-Roundtrip skipped: {result.test_roundtrip.reason}
            </div>
          ) : result.test_roundtrip?.success ? (
            <div className="glass-card p-2 text-teal">
              ✓ Test-Roundtrip erfolgreich — Backend:{" "}
              <strong>{result.test_roundtrip.backend}</strong>, Latenz:{" "}
              <strong>{result.test_roundtrip.duration_ms} ms</strong>
              {result.test_roundtrip.result_payload?.category && (
                <>
                  {" · "}Klassifikation:{" "}
                  <strong>{result.test_roundtrip.result_payload.category}</strong>
                </>
              )}
            </div>
          ) : result.test_roundtrip?.error ? (
            <div className="glass-card p-2 text-coral">
              ✗ Test-Roundtrip fehlgeschlagen: {result.test_roundtrip.error}
            </div>
          ) : null}
        </div>
      )}
    </div>
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
  // v1.6.6 (#540): Bewerbungsbericht-Einstellungen — Arbeitsamt-Block + Beraterkommentar
  const [reportSettings, setReportSettings] = useState({
    arbeitsamt_block_enabled: false,
    ba_vermittlungsnummer: "",
    ba_aktenzeichen: "",
    ba_berater_name: "",
    ba_berater_stelle: "",
    berater_kommentar_block: false,
    // v1.7.0-beta.12 (#582): Taetigkeitsbericht-Modus
    taetigkeitsbericht_mode: false,
  });
  const [reportSaving, setReportSaving] = useState(false);
  // #663 (C20): Ablehnungsgruende-Editor
  const [dismissReasons, setDismissReasons] = useState([]);
  const [newReason, setNewReason] = useState("");
  const [reasonBusy, setReasonBusy] = useState(false);
  const [editReasonId, setEditReasonId] = useState(null);
  const [editReasonLabel, setEditReasonLabel] = useState("");
  const [deleteReasonDialog, setDeleteReasonDialog] = useState({ open: false, reason: null, reassignTo: "" });
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
      const [sourceRows, logsData, impulseData, healthData, privacyData, followupData, reportData, reasonsData] = await Promise.all([
        api("/api/sources"),
        api("/api/logs?lines=100"),
        api("/api/daily-impulse").catch(() => null),
        api("/api/health").catch(() => null),
        api("/api/privacy-info").catch(() => null),
        api("/api/settings/followup").catch(() => null),
        api("/api/settings/report").catch(() => null),
        api("/api/dismiss-reasons").catch(() => []),
      ]);
      startTransition(() => {
        setSources(sourceRows || []);
        setLogs(logsData?.lines || []);
        if (impulseData) setImpulseEnabled(impulseData.enabled !== false);
        setHealth(healthData);
        setPrivacy(privacyData);
        if (followupData) setFollowupSettings(followupData);
        if (reportData) setReportSettings((prev) => ({ ...prev, ...reportData }));
        setDismissReasons(Array.isArray(reasonsData) ? reasonsData : []);
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

  // v1.6.6 (#540): Bericht-Einstellungen speichern
  async function saveReportSettings(next) {
    setReportSaving(true);
    try {
      const saved = await putJson("/api/settings/report", next);
      if (saved?.gespeichert) {
        setReportSettings((prev) => ({ ...prev, ...saved.gespeichert }));
      }
      pushToast("Bericht-Einstellungen gespeichert", "success");
    } catch (error) {
      pushToast(`Speichern fehlgeschlagen: ${error.message}`, "danger");
    } finally {
      setReportSaving(false);
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

  // #663 (C20): Ablehnungsgruende-Editor-Handler
  async function reloadDismissReasons() {
    try {
      const data = await api("/api/dismiss-reasons");
      setDismissReasons(Array.isArray(data) ? data : []);
    } catch {
      /* still */
    }
  }

  async function handleAddReason() {
    const label = (newReason || "").trim();
    if (!label) return;
    setReasonBusy(true);
    try {
      await postJson("/api/dismiss-reasons", { label });
      setNewReason("");
      await reloadDismissReasons();
      pushToast(`Ablehnungsgrund "${label}" angelegt.`, "success");
    } catch (error) {
      pushToast(error?.message || "Konnte Grund nicht anlegen.", "danger");
    } finally {
      setReasonBusy(false);
    }
  }

  async function handleToggleReason(reason) {
    const willDeactivate = Boolean(reason.is_active);
    try {
      await api(`/api/dismiss-reasons/${reason.id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active: willDeactivate ? 0 : 1 }),
      });
      await reloadDismissReasons();
      pushToast(
        `"${reason.label}" ${willDeactivate ? "deaktiviert" : "aktiviert"}.`,
        "success",
      );
    } catch (error) {
      pushToast(error?.message || "Konnte Status nicht aendern.", "danger");
    }
  }

  function startRenameReason(reason) {
    setEditReasonId(reason.id);
    setEditReasonLabel(reason.label || "");
  }

  function cancelRenameReason() {
    setEditReasonId(null);
    setEditReasonLabel("");
  }

  async function saveRenameReason(reason) {
    const label = (editReasonLabel || "").trim();
    if (!label || label === reason.label) {
      cancelRenameReason();
      return;
    }
    setReasonBusy(true);
    try {
      const res = await api(`/api/dismiss-reasons/${reason.id}`, {
        method: "PATCH",
        body: JSON.stringify({ label }),
      });
      const moved = res?.rename?.reassigned_jobs || 0;
      const merged = res?.rename?.status === "zusammengefuehrt";
      cancelRenameReason();
      await reloadDismissReasons();
      pushToast(
        merged
          ? `Mit "${label}" zusammengefuehrt${moved ? ` (${moved} Stellen umgezogen)` : ""}.`
          : `Umbenannt in "${label}"${moved ? ` (${moved} Stellen mitgezogen)` : ""}.`,
        "success",
      );
    } catch (error) {
      pushToast(error?.message || "Konnte nicht umbenennen.", "danger");
    } finally {
      setReasonBusy(false);
    }
  }

  function askDeleteReason(reason) {
    // Default-Ziel fuer die Neuzuordnung: 'sonstiges', sonst der erste andere
    // aktive Grund.
    const others = dismissReasons.filter(
      (r) => r.id !== reason.id && (r.is_active === undefined || r.is_active),
    );
    const fallback =
      others.find((r) => r.label === "sonstiges")?.label ||
      others[0]?.label ||
      "sonstiges";
    setDeleteReasonDialog({ open: true, reason, reassignTo: fallback });
  }

  async function confirmDeleteReason() {
    const { reason, reassignTo } = deleteReasonDialog;
    if (!reason) return;
    const used = Number(reason.usage_count || 0) > 0;
    setReasonBusy(true);
    try {
      await deleteRequest(
        `/api/dismiss-reasons/${reason.id}`,
        { reassign_to: reassignTo || "" },
      );
      setDeleteReasonDialog({ open: false, reason: null, reassignTo: "" });
      await reloadDismissReasons();
      pushToast(
        used
          ? `"${reason.label}" geloescht, Stellen auf "${reassignTo}" umgezogen.`
          : `"${reason.label}" geloescht.`,
        "success",
      );
    } catch (error) {
      pushToast(error?.message || "Konnte nicht loeschen.", "danger");
    } finally {
      setReasonBusy(false);
    }
  }

  if (loading) return <LoadingPanel label="Einstellungen werden geladen..." />;

  const tabs = [
    { id: "quellen", label: "Quellen" },
    { id: "ai", label: "Lokale KI" },
    { id: "automatik", label: "Automatik" },  // v1.7.0-beta.20
    { id: "bewerten", label: "Bewertung" },  // #663 C20
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
            {/* v1.7.0-beta.36 (#590 Aufgabe B): Profil-basierte Quellen-Empfehlung */}
            <RecommendedSourcesCard
              sources={sources}
              onToggle={toggleSource}
              pushToast={pushToast}
            />

            <Card className="rounded-2xl">
              <SectionHeading title="Quellen" description="Welche Jobportale aktiv durchsucht werden." />
              <SourceSelectionList
                sources={sources}
                loginJobs={loginJobs}
                onToggle={toggleSource}
                onStartLogin={startSourceLogin}
              />
            </Card>

            {/* v1.7.0-beta.33 (#590-C): Health-Score-Tab */}
            <ScraperHealthCard pushToast={pushToast} />

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

        {/* ── v1.7.0 (#583): Lokale KI Tab ── */}
        {settingsTab === "ai" && (
          <>
            <KIFeaturesCard pushToast={pushToast} />
            <LocalAITab pushToast={pushToast} />
          </>
        )}

        {settingsTab === "automatik" && (
          <>
            <AutomatikSchedulerCard pushToast={pushToast} />
            <AutoActionsTab pushToast={pushToast} />
          </>
        )}

        {/* ── Bewertung Tab: Ablehnungsgruende-Editor (#663 C20) ── */}
        {settingsTab === "bewerten" && (
          <>
          <Card className="rounded-2xl">
            <SectionHeading
              title="Ablehnungsgruende"
              description="Eigene Gruende fuer 'passt nicht' anlegen, umbenennen (Tippfehler-Korrektur zieht bestehende Stellen mit), deaktivieren oder loeschen. Aktive Gruende stehen Claude bei stelle_bewerten zur Verfuegung."
            />
            <div className="mt-4 grid gap-2">
              {dismissReasons.length === 0 && (
                <p className="text-sm text-muted/60">Noch keine Ablehnungsgruende vorhanden.</p>
              )}
              {dismissReasons
                .slice()
                .sort((a, b) => (b.usage_count || 0) - (a.usage_count || 0))
                .map((reason) => {
                  const active = reason.is_active === undefined ? true : Boolean(reason.is_active);
                  const isEditing = editReasonId === reason.id;
                  return (
                    <div
                      key={reason.id ?? reason.label}
                      className="flex items-center justify-between gap-3 rounded-lg border border-white/5 px-3 py-2"
                    >
                      {isEditing ? (
                        <div className="flex flex-1 items-center gap-2">
                          <TextInput
                            value={editReasonLabel}
                            onChange={(event) => setEditReasonLabel(event.target.value)}
                            autoFocus
                            onKeyDown={(event) => {
                              if (event.key === "Enter") {
                                event.preventDefault();
                                saveRenameReason(reason);
                              } else if (event.key === "Escape") {
                                cancelRenameReason();
                              }
                            }}
                          />
                          <Button type="button" onClick={() => saveRenameReason(reason)} disabled={reasonBusy}>
                            Speichern
                          </Button>
                          <Button type="button" variant="ghost" onClick={cancelRenameReason}>
                            Abbrechen
                          </Button>
                        </div>
                      ) : (
                        <>
                          <div className="flex items-center gap-2 min-w-0">
                            <span className={`text-sm ${active ? "text-ink" : "text-muted/40 line-through"}`}>
                              {reason.label}
                            </span>
                            {reason.is_custom ? <Badge tone="sky">eigen</Badge> : null}
                            {reason.usage_count ? (
                              <span className="text-xs text-muted/50">{reason.usage_count}x</span>
                            ) : null}
                          </div>
                          <div className="flex shrink-0 items-center gap-1">
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => startRenameReason(reason)}
                              title="Umbenennen (Tippfehler korrigieren)"
                            >
                              <Pencil size={15} />
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => handleToggleReason(reason)}
                            >
                              {active ? "Deaktivieren" : "Aktivieren"}
                            </Button>
                            <Button
                              type="button"
                              variant="danger"
                              size="sm"
                              onClick={() => askDeleteReason(reason)}
                              title="Loeschen"
                            >
                              <Trash2 size={15} />
                            </Button>
                          </div>
                        </>
                      )}
                    </div>
                  );
                })}
            </div>
            <div className="mt-4 flex items-end gap-2">
              <Field label="Neuer Grund (z.B. kein_homeoffice)" className="flex-1">
                <TextInput
                  value={newReason}
                  onChange={(event) => setNewReason(event.target.value)}
                  placeholder="snake_case empfohlen"
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      handleAddReason();
                    }
                  }}
                />
              </Field>
              <Button type="button" onClick={handleAddReason} disabled={reasonBusy || !newReason.trim()}>
                Hinzufuegen
              </Button>
            </div>
          </Card>

          <Modal
            open={deleteReasonDialog.open}
            onClose={() => setDeleteReasonDialog({ open: false, reason: null, reassignTo: "" })}
            title="Ablehnungsgrund loeschen"
            size="sm"
            footer={
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setDeleteReasonDialog({ open: false, reason: null, reassignTo: "" })}
                >
                  Abbrechen
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  onClick={confirmDeleteReason}
                  disabled={reasonBusy}
                >
                  Endgueltig loeschen
                </Button>
              </div>
            }
          >
            {deleteReasonDialog.reason && (
              <div className="space-y-3 text-sm text-muted/80">
                <p>
                  Grund{" "}
                  <span className="font-semibold text-ink">"{deleteReasonDialog.reason.label}"</span>{" "}
                  wirklich loeschen?
                </p>
                {Number(deleteReasonDialog.reason.usage_count || 0) > 0 ? (
                  <Field
                    label={`Die ${deleteReasonDialog.reason.usage_count} bisher so aussortierten Stellen neu zuordnen zu:`}
                  >
                    <SelectInput
                      value={deleteReasonDialog.reassignTo}
                      onChange={(event) =>
                        setDeleteReasonDialog((d) => ({ ...d, reassignTo: event.target.value }))
                      }
                    >
                      {dismissReasons
                        .filter((r) => r.id !== deleteReasonDialog.reason.id)
                        .map((r) => (
                          <option key={r.id} value={r.label}>
                            {r.label}
                          </option>
                        ))}
                    </SelectInput>
                  </Field>
                ) : (
                  <p className="text-muted/60">
                    Dieser Grund wird von keiner Stelle verwendet und kann gefahrlos geloescht werden.
                  </p>
                )}
              </div>
            )}
          </Modal>
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

        {/* ── v1.6.6 (#540): Bewerbungsbericht-Einstellungen ── */}
        {settingsTab === "system" && (
          <Card className="rounded-2xl">
            <div className="mb-4 flex items-center gap-3">
              <div className="glass-icon glass-icon-sky h-10 w-10">
                <Activity size={18} />
              </div>
              <div>
                <h2 className="text-base font-semibold text-ink">Bewerbungsbericht</h2>
                <p className="text-xs text-muted">
                  Optionale Felder fuer den PDF-/Excel-Bericht. Nuetzlich fuer Anwender, die ihren
                  Bericht beim Arbeitsamt vorlegen — sonst einfach den Haken weglassen.
                </p>
              </div>
            </div>

            {/* Master-Toggle: Arbeitsamt-Block ein/aus */}
            <label className="flex items-center gap-3 cursor-pointer mb-4">
              <input
                type="checkbox"
                checked={!!reportSettings.arbeitsamt_block_enabled}
                onChange={(e) => {
                  const flag = e.target.checked;
                  setReportSettings((prev) => ({ ...prev, arbeitsamt_block_enabled: flag }));
                  saveReportSettings({ arbeitsamt_block_enabled: flag });
                }}
                disabled={reportSaving}
                className="h-4 w-4 cursor-pointer"
              />
              <div>
                <p className="text-sm font-medium text-ink">Arbeitsamt-Vorlagenblock im Bericht anzeigen</p>
                <p className="text-[11px] text-muted/70">
                  Wenn aktiv, wird auf der Cover-Page ein Block mit Vermittlungsnummer, Aktenzeichen und Berater-Daten gerendert.
                  Ohne Haken werden die Felder ignoriert — du musst sie nicht loeschen.
                </p>
              </div>
            </label>

            <div className={`grid gap-3 sm:grid-cols-2 ${reportSettings.arbeitsamt_block_enabled ? "" : "opacity-50 pointer-events-none"}`}>
              <Field label="Vermittlungsnummer">
                <TextInput
                  type="text"
                  maxLength={200}
                  value={reportSettings.ba_vermittlungsnummer}
                  onChange={(e) => setReportSettings((prev) => ({ ...prev, ba_vermittlungsnummer: e.target.value }))}
                  onBlur={(e) => saveReportSettings({ ba_vermittlungsnummer: e.target.value })}
                  disabled={reportSaving || !reportSettings.arbeitsamt_block_enabled}
                  placeholder="z.B. 123ABC456"
                />
              </Field>
              <Field label="Aktenzeichen">
                <TextInput
                  type="text"
                  maxLength={200}
                  value={reportSettings.ba_aktenzeichen}
                  onChange={(e) => setReportSettings((prev) => ({ ...prev, ba_aktenzeichen: e.target.value }))}
                  onBlur={(e) => saveReportSettings({ ba_aktenzeichen: e.target.value })}
                  disabled={reportSaving || !reportSettings.arbeitsamt_block_enabled}
                  placeholder="z.B. 12345/2026"
                />
              </Field>
              <Field label="Berater(in)">
                <TextInput
                  type="text"
                  maxLength={200}
                  value={reportSettings.ba_berater_name}
                  onChange={(e) => setReportSettings((prev) => ({ ...prev, ba_berater_name: e.target.value }))}
                  onBlur={(e) => saveReportSettings({ ba_berater_name: e.target.value })}
                  disabled={reportSaving || !reportSettings.arbeitsamt_block_enabled}
                  placeholder="Name der Beratungsperson"
                />
              </Field>
              <Field label="Beratungsstelle">
                <TextInput
                  type="text"
                  maxLength={200}
                  value={reportSettings.ba_berater_stelle}
                  onChange={(e) => setReportSettings((prev) => ({ ...prev, ba_berater_stelle: e.target.value }))}
                  onBlur={(e) => saveReportSettings({ ba_berater_stelle: e.target.value })}
                  disabled={reportSaving || !reportSettings.arbeitsamt_block_enabled}
                  placeholder="z.B. Agentur fuer Arbeit Bremen"
                />
              </Field>
            </div>

            {/* Sub-Toggle: Beraterkommentar-Block am Berichtende */}
            <label className="mt-5 flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={!!reportSettings.berater_kommentar_block}
                onChange={(e) => {
                  const flag = e.target.checked;
                  setReportSettings((prev) => ({ ...prev, berater_kommentar_block: flag }));
                  saveReportSettings({ berater_kommentar_block: flag });
                }}
                disabled={reportSaving}
                className="h-4 w-4 cursor-pointer"
              />
              <div>
                <p className="text-sm font-medium text-ink">Beraterkommentar-Block am Berichtende</p>
                <p className="text-[11px] text-muted/70">
                  Fuegt am Ende des Berichts leere Linien fuer handschriftliche Anmerkungen ein.
                </p>
              </div>
            </label>

            {/* v1.7.0-beta.12 (#582): Taetigkeitsbericht-Modus */}
            <label className="mt-3 flex items-center gap-3 cursor-pointer">
              <input
                type="checkbox"
                checked={!!reportSettings.taetigkeitsbericht_mode}
                onChange={(e) => {
                  const flag = e.target.checked;
                  setReportSettings((prev) => ({ ...prev, taetigkeitsbericht_mode: flag }));
                  saveReportSettings({ taetigkeitsbericht_mode: flag });
                }}
                disabled={reportSaving}
                className="h-4 w-4 cursor-pointer"
              />
              <div>
                <p className="text-sm font-medium text-ink">Taetigkeitsbericht-Modus</p>
                <p className="text-[11px] text-muted/70">
                  Fokus auf taegliche Aktivitaet als Nachweis fuer Vermittler/Berater.
                  Cover-Titel wird zu „Taetigkeitsbericht" und der Bericht enthaelt eine
                  zusaetzliche tagesgruppierte Uebersicht aller Bewerbungs-Ereignisse.
                </p>
              </div>
            </label>

            {/* v1.7.0-beta.22: PBP-Start-Datum konfigurierbar */}
            <PbpStartDateField pushToast={pushToast} />
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

            {/* v1.7.0-beta.26 (#594 Stufe 1): Lern-System-Privacy */}
            <LearningPrivacyCard pushToast={pushToast} />

            {/* v1.7.0-beta.30 (#594 Stufe 5): Telemetrie-Sharing */}
            <TelemetrySharingCard pushToast={pushToast} />

            {/* v1.7.0-beta.17 (#581): DSGVO Art. 15 — Selbstauskunft als PDF */}
            <Card className="rounded-2xl">
              <SectionHeading
                title="Datenauskunft (DSGVO Art. 15)"
                description="PDF-Bericht: Welche Daten hat PBP gespeichert, wo liegen sie, seit wann."
              />
              <div className="glass-card p-3 flex items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-medium text-ink">Selbstauskunft als PDF erstellen</p>
                  <p className="text-xs text-muted/50">
                    Strukturierter Bericht: Profil, Skills, Berufserfahrung, Dokumenten-/Bewerbungs-/
                    Stellen-/Termine-Anzahlen, Speicherort. Inhalte deiner Dokumente und E-Mails sind
                    NICHT enthalten — nur die Meta-Information dass sie existieren.
                  </p>
                </div>
                <a
                  href={apiUrl("/api/privacy/self-disclosure.pdf")}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-sm font-medium text-ink hover:bg-white/[0.08]"
                >
                  <Download size={14} />
                  PDF
                </a>
              </div>
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

            {/* v1.7.0-beta.43 (#621): Komplett-Deinstallation aus der Gefahrenzone */}
            <UninstallSection pushToast={pushToast} />
          </div>
        )}
      </div>
    </div>
  );
}

// v1.7.0-beta.43 (#621): Komplett-Deinstallation aus der Gefahrenzone.
// Startet DEINSTALLIEREN.bat als detached cmd-Fenster — der User klickt
// sich dann durch die Deinstaller-Prompts (Backup, Daten loeschen, ...).
// Hinweis: Claude Desktop und Ollama werden NICHT mit-deinstalliert.
function UninstallSection({ pushToast }) {
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);

  async function launch() {
    setBusy(true);
    try {
      const result = await postJson("/api/danger/launch-uninstaller", {
        confirm: "DEINSTALLIEREN",
      });
      pushToast(
        result?.hint || "Deinstaller gestartet — folge dem neuen Konsolen-Fenster",
        "success"
      );
      setConfirm("");
    } catch (err) {
      pushToast(`Fehler: ${err.message}`, "danger");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="glass-banner glass-banner-danger rounded-2xl">
      <SectionHeading
        title="PBP komplett deinstallieren"
        description="Entfernt PBP von diesem Rechner: Programmdateien, Registry-Eintrag, Desktop-Verknuepfung und MCP-Eintrag in Claude Desktop. Im Deinstaller wirst du gefragt ob du auch deine Bewerbungsdaten loeschen willst."
      />
      <div className="flex flex-col gap-4">
        <div className="rounded-xl border border-amber/30 bg-amber/[0.05] p-3 text-[12px] text-amber/90">
          <strong className="text-amber">Wichtig — was NICHT mit deinstalliert wird:</strong>
          <ul className="mt-1.5 ml-4 list-disc space-y-0.5">
            <li>
              <strong>Claude Desktop</strong> — Anthropics App. Bleibt installiert.
              Manuell ueber <em>Windows Apps &amp; Features</em> entfernen wenn gewuenscht.
            </li>
            <li>
              <strong>Ollama</strong> — falls du es fuer die lokale AI installiert hast.
              Bleibt installiert. Manuell ueber <em>Windows Apps &amp; Features</em> entfernen.
            </li>
            <li>
              <strong>Python</strong> — falls du eine eigene Installation neben PBP nutzt.
              PBPs eigenes Python (im AppData) wird komplett entfernt.
            </li>
          </ul>
        </div>

        <div className="flex items-center gap-3">
          <div className="glass-icon glass-icon-danger h-10 w-10 shrink-0">
            <Trash2 size={16} />
          </div>
          <p className="text-sm text-muted">
            Gib <strong className="text-ink">DEINSTALLIEREN</strong> ein, um die
            Komplett-Deinstallation zu starten. Es oeffnet sich ein neues
            Konsolen-Fenster mit den Deinstaller-Prompts.
          </p>
        </div>
        <div className="flex items-end gap-3">
          <Field label="Bestaetigung">
            <TextInput
              className="!w-56"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              placeholder="DEINSTALLIEREN"
            />
          </Field>
          <Button
            variant="danger"
            disabled={confirm !== "DEINSTALLIEREN" || busy}
            onClick={launch}
          >
            <Trash2 size={15} />
            Deinstaller starten
          </Button>
        </div>
      </div>
    </Card>
  );
}
