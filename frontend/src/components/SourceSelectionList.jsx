import { Fragment, useState } from "react";
import { AlertTriangle, Ban, CheckCircle2, Clock, ExternalLink, LoaderCircle, VolumeX, XCircle, Zap } from "lucide-react";

import { Badge, Button, Card, CheckboxInput } from "@/components/ui";
import { WEG_BROWSER, quellenBadges } from "@/lib/quellenBadges";

function healthBadge(health) {
  if (!health || !health.last_run) return null;
  const count = health.last_count ?? 0;
  const time = health.avg_time_s ? ` / ${health.avg_time_s.toFixed(1)}s` : "";
  switch (health.badge) {
    case "ok":
      return (
        <Badge tone="success" className="gap-1" title={`Letzter Lauf: ${count} Treffer${time}`}>
          <CheckCircle2 size={10} />
          {count} Treffer{time}
        </Badge>
      );
    case "stumm":
      return (
        <Badge tone="amber" className="gap-1" title={`Stumm seit ${health.consecutive_silent} Lauf(en)${health.last_status_detail ? ` — ${health.last_status_detail}` : ""}`}>
          <VolumeX size={10} />
          0 Treffer{time}
        </Badge>
      );
    case "leer":
      return (
        <Badge tone="neutral" className="gap-1" title="Letzter Lauf brachte keine Treffer">
          0 Treffer{time}
        </Badge>
      );
    case "fehler":
      return (
        <Badge tone="danger" className="gap-1" title={`${health.consecutive_failures} Fehler in Folge`}>
          <XCircle size={10} />
          Fehler
        </Badge>
      );
    case "deaktiviert":
      return (
        <Badge tone="neutral" className="gap-1" title="Automatisch deaktiviert nach mehreren stillen Läufen">
          Auto-Aus
        </Badge>
      );
    case "pausiert":
      return (
        <Badge tone="amber" className="gap-1" title={`Temporär pausiert (${health.error_class || "stumm"}) — Probe-Run geplant, kommt automatisch zurück${health.last_status_detail ? ` — ${health.last_status_detail}` : ""}`}>
          <Clock size={10} />
          Pausiert
        </Badge>
      );
    case "blockiert":
      return (
        <Badge tone="amber" className="gap-1" title={`Geblockt (403/429)${health.last_status_detail ? ` — ${health.last_status_detail}` : ""}`}>
          <AlertTriangle size={10} />
          Blockiert
        </Badge>
      );
    case "tot":
      return (
        <Badge tone="danger" className="gap-1" title={`Endpoint weg (404/410)${health.last_status_detail ? ` — ${health.last_status_detail}` : ""}`}>
          <Ban size={10} />
          Tot
        </Badge>
      );
    case "kaputt":
      return (
        <Badge tone="danger" className="gap-1" title={`Adapter/Parser defekt — Code-Fix nötig${health.last_status_detail ? ` — ${health.last_status_detail}` : ""}`}>
          <XCircle size={10} />
          Kaputt
        </Badge>
      );
    default:
      return null;
  }
}

// #1039: Ansichten der Quellenliste. "alle" heisst alle NUTZBAREN — die
// defekten haben eine eigene Ansicht, sonst verschwinden sie nicht aus dem
// Blick, sondern nur aus der Zaehlung.
const ANSICHTEN = [
  ["alle", "Alle"],
  ["aktiv", "Aktiv"],
  ["inaktiv", "Inaktiv"],
];

export function quellenAnsicht(sources, ansicht) {
  const sortiert = [...(sources || [])].sort((a, b) =>
    String(a.name || a.key).localeCompare(String(b.name || b.key), "de", { sensitivity: "base" })
  );
  const nutzbar = sortiert.filter((s) => !s.defekt);
  const defekt = sortiert.filter((s) => s.defekt);
  const anzahl = {
    alle: nutzbar.length,
    aktiv: nutzbar.filter((s) => s.active).length,
    inaktiv: nutzbar.filter((s) => !s.active).length,
    defekt: defekt.length,
  };
  const sichtbar =
    ansicht === "defekt" ? defekt
      : ansicht === "aktiv" ? nutzbar.filter((s) => s.active)
        : ansicht === "inaktiv" ? nutzbar.filter((s) => !s.active)
          : ansicht === "alle" ? nutzbar
            : sortiert;
  return { sichtbar, anzahl };
}

export default function SourceSelectionList({
  sources,
  loginJobs = {},
  onToggle,
  onStartLogin,
  filterbar = false,
}) {
  const [ansicht, setAnsicht] = useState("alle");
  const { sichtbar, anzahl } = quellenAnsicht(sources, filterbar ? ansicht : "sortiert");

  return (
    <div className="grid gap-3">
      {/* #509: Erweiterter Tipp-Text — vier Wege bei Quell-Problemen */}
      <details className="rounded-xl border border-sky/20 bg-sky/5 px-4 py-3 mb-1 group">
        <summary className="cursor-pointer text-xs text-muted list-none flex items-center justify-between">
          <span>
            <strong className="text-ink">Tipp:</strong> Vier Wege, eine Stelle ins PBP zu bekommen — auf Pfeil klicken zum Ausklappen.
          </span>
          <span className="text-muted/60 group-open:rotate-90 transition-transform">▶</span>
        </summary>
        <div className="mt-3 space-y-2 text-xs text-muted">
          <p>
            <strong className="text-ink">1. Eingebauter Scraper</strong> — Default-Weg.{" "}
            <Badge tone="success" className="gap-1 inline-flex"><Zap size={9} />Schnell</Badge>{" "}
            Quellen laufen parallel und liefern in Sekunden.{" "}
            <Badge tone="sky" className="gap-1 inline-flex">{WEG_BROWSER}</Badge>{" "}
            heisst: die Quelle laeuft nicht von selbst, sondern ueber die Claude-Erweiterung
            in deinem Browser (Chrome, Brave, Edge oder Vivaldi).
          </p>
          <p>
            <strong className="text-ink">2. Claude-Erweiterung im Browser</strong> — wenn der eingebaute
            Scraper streikt (Login, dynamische Seiten, Captcha), kann die Claude-Erweiterung die
            Seite direkt im Browser durchgehen und Stellen ins PBP übernehmen. Funktioniert
            besonders gut bei XING und LinkedIn.
          </p>
          <p>
            <strong className="text-ink">3. URL kopieren und in den Claude-Chat einfügen</strong> —
            schnellster Weg für Einzel-Stellen. Anzeige im Browser öffnen, URL kopieren,
            Claude im Chat schicken: <em>„Leg diese Stelle bitte an: &lt;url&gt;"</em>. Claude liest
            die Anzeige selbst aus und legt sie inklusive Beschreibung, Firma und
            Anforderungen an.
          </p>
          <p>
            <strong className="text-ink">4. Von Hand über Claude</strong> —
            wenn keiner der oberen Wege funktioniert (Stelle nur als PDF/Mail/Screenshot
            vorhanden). Claude bittest du dann, eine Stelle aus den Eckdaten anzulegen.
          </p>
          <p className="pt-2 text-muted/70 border-t border-sky/10">
            Claude kann übrigens auch dein Profil auf Jobportalen wie XING oder StepStone
            aktualisieren — frag einfach danach!
          </p>
        </div>
      </details>

      {filterbar ? (
        <div className="flex flex-wrap items-center justify-between gap-2" data-testid="quellen-filter">
          <div role="group" aria-label="Quellen filtern" className="flex flex-wrap items-center gap-1 text-xs">
            {ANSICHTEN.map(([id, label], index) => (
              <Fragment key={id}>
                {index > 0 ? <span aria-hidden="true" className="text-muted/40">·</span> : null}
                <button
                  type="button"
                  aria-pressed={ansicht === id}
                  onClick={() => setAnsicht(id)}
                  className={`rounded-lg px-2.5 py-1 font-medium transition-colors ${
                    ansicht === id ? "bg-sky/15 text-sky" : "text-muted hover:bg-white/5 hover:text-ink"
                  }`}
                >
                  {label} ({anzahl[id]})
                </button>
              </Fragment>
            ))}
          </div>
          <button
            type="button"
            aria-pressed={ansicht === "defekt"}
            onClick={() => setAnsicht(ansicht === "defekt" ? "alle" : "defekt")}
            className={`inline-flex items-center gap-1.5 rounded-lg px-2.5 py-1 text-xs font-medium transition-colors ${
              ansicht === "defekt" ? "bg-coral/15 text-coral" : "text-muted hover:bg-white/5 hover:text-ink"
            }`}
          >
            <Ban size={11} />
            Defekte Quellen ({anzahl.defekt})
          </button>
        </div>
      ) : null}
      {filterbar && sichtbar.length === 0 ? (
        <p className="text-xs text-muted">Keine Quelle in dieser Ansicht.</p>
      ) : null}

      {sichtbar.map((source) => {
        const loginJob = loginJobs[source.key];
        const loginRunning = loginJob?.status === "running";
        const loginReady = loginJob?.status === "fertig";
        const isDefekt = Boolean(source.defekt);

        return (
          <Card
            key={source.key}
            data-source-key={source.key}
            className={`glass-card-soft rounded-xl shadow-none ${isDefekt ? "opacity-60" : ""}`}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className={`text-sm font-semibold ${isDefekt ? "text-muted line-through decoration-muted/40" : "text-ink"}`}>
                    {source.name}
                  </span>
                  {/* v1.7.120 (#1059): die Etiketten kommen aus
                      lib/quellenBadges — Weg, Tempo, Eigenschaft und Zustand
                      getrennt, jeder Text hoechstens einmal. #1039 gilt
                      weiter: das erste Etikett folgt dem Haken. #906 auch:
                      eine aktive Browser-Quelle "wartet auf dich". */}
                  {quellenBadges(source, loginJob?.status || null).map((b) => (
                    <Fragment key={b.text}>
                      <Badge tone={b.tone} title={b.titel || undefined} className="gap-1">
                        {b.symbol === "ban" ? <Ban size={10} /> : null}
                        {b.symbol === "zap" ? <Zap size={10} /> : null}
                        {b.symbol === "clock" ? <Clock size={10} /> : null}
                        {b.text}
                      </Badge>
                      {/* Der Gesundheitszustand steht direkt hinter dem Status. */}
                      {b.art === "status" ? healthBadge(source.health) : null}
                    </Fragment>
                  ))}
                </div>
                <p className="text-sm text-muted">{source.beschreibung}</p>
                {isDefekt ? (
                  <div className="mt-1 rounded-lg border border-coral/30 bg-coral/5 px-3 py-2 space-y-1.5">
                    <div className="flex items-center gap-1.5">
                      <Ban size={13} className="shrink-0 text-coral" />
                      <span className="text-xs font-semibold text-coral">
                        Automatische Suche aktuell nicht möglich
                      </span>
                    </div>
                    {source.defekt_grund ? (
                      <p className="text-xs text-muted">{source.defekt_grund}</p>
                    ) : null}
                    {source.manueller_fallback ? (
                      <p className="text-xs text-muted">
                        <strong className="text-ink">Workaround:</strong> Über die Claude-Erweiterung im Browser
                        <a
                          href={String(source.manueller_fallback).split(" ")[0]}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="ml-1 inline-flex items-center gap-1 text-sky underline"
                        >
                          {(String(source.manueller_fallback).split(" ")[0] || "").replace(/^https?:\/\//, "").slice(0, 50)}
                          <ExternalLink size={10} />
                        </a>
                        {" "}öffnen und passende Stellen von Claude in PBP anlegen lassen.
                      </p>
                    ) : null}
                  </div>
                ) : null}
                {!isDefekt && source.login_erforderlich && !source.beta ? (
                  <p className="text-xs text-amber">
                    Beim ersten Start öffnet sich ein Browser-Fenster zur Anmeldung. Danach läuft
                    die Suche mit gespeicherter Session weiter.
                  </p>
                ) : null}
                {!isDefekt && source.warnung ? (
                  <div className="mt-1 rounded-lg border border-amber/30 bg-amber/10 px-3 py-2">
                    <div className="mb-1 flex items-center gap-1.5">
                      <AlertTriangle size={13} className="shrink-0 text-amber" />
                      <span className="text-xs font-semibold text-amber">
                        {source.beta ? "Beta-Feature" : "Hinweis"}
                      </span>
                    </div>
                    {source.warnung.split("\n").filter(Boolean).map((line, i) => (
                      <p key={i} className="text-xs text-muted">{line}</p>
                    ))}
                  </div>
                ) : null}
                {loginJob?.message ? (
                  <p className="text-xs text-muted">{loginJob.message}</p>
                ) : null}
                {!isDefekt && source.active && source.profil_optimierung ? (
                  <div className="mt-1 rounded-lg border border-amber/15 bg-amber/5 px-3 py-2">
                    <p className="text-xs text-amber">{source.profil_optimierung}</p>
                  </div>
                ) : null}
              </div>

              <div className="flex shrink-0 self-center items-center gap-3">
                {!isDefekt && source.login_erforderlich && !loginReady ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={loginRunning}
                    onClick={() => onStartLogin?.(source)}
                  >
                    {loginRunning ? <LoaderCircle className="animate-spin" size={14} /> : null}
                  {loginRunning ? "Login läuft" : "Login starten"}
                  </Button>
                ) : null}
                <CheckboxInput
                  className="shrink-0 flex-none self-center"
                  checked={Boolean(source.active) && !isDefekt}
                  disabled={isDefekt}
                  title={isDefekt ? "Quelle ist als defekt markiert. Bis zur Reparatur nur über die Claude-Erweiterung im Browser nutzbar." : undefined}
                  onChange={(event) => {
                    if (isDefekt) return;
                    const checked = event.target.checked;
                    // v1.7.17 (#906): browser_login-Quellen nur nach
                    // bestaetigtem Hinweis aktivieren — sonst entstehen
                    // "aktive" Quellen, die faktisch nie laufen und ein
                    // Konto brauchen, von dem niemand weiss.
                    if (checked && source.zugriffsart === "browser_login") {
                      const zeilen = [
                        `${source.name} läuft nicht automatisch, sondern über die Claude-Erweiterung in deinem eigenen Browser.`,
                      ];
                      if (source.login_hinweis) zeilen.push(source.login_hinweis);
                      if (source.konto_url) zeilen.push(`Konto anlegen: ${source.konto_url}`);
                      zeilen.push("Treffer übernimmt Claude mit stelle_manuell_anlegen().");
                      if (!window.confirm(`${zeilen.join("\n\n")}\n\nVerstanden — Quelle aktivieren?`)) {
                        event.target.checked = false;
                        return;
                      }
                    }
                    onToggle?.(source, checked, {
                      trigger: "checkbox",
                      autoStartLogin: checked && Boolean(source.login_erforderlich) && !loginReady,
                    });
                  }}
                />
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}
