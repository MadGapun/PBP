import { AlertTriangle, Clock, LoaderCircle, Zap } from "lucide-react";

import { Badge, Button, Card, CheckboxInput } from "@/components/ui";

function loginTone(status) {
  if (status === "fehler") return "danger";
  if (status === "fertig") return "success";
  return "sky";
}

function speedBadge(geschwindigkeit) {
  if (geschwindigkeit === "schnell") {
    return (
      <Badge tone="success" className="gap-1">
        <Zap size={10} />
        Schnell
      </Badge>
    );
  }
  if (geschwindigkeit === "langsam") {
    return (
      <Badge tone="amber" className="gap-1">
        <Clock size={10} />
        Browser
      </Badge>
    );
  }
  if (geschwindigkeit === "manuell") {
    return (
      <Badge tone="neutral" className="gap-1">
        Manuell
      </Badge>
    );
  }
  return null;
}

export default function SourceSelectionList({
  sources,
  loginJobs = {},
  onToggle,
  onStartLogin,
}) {
  return (
    <div className="grid gap-3">
      {/* Hinweis fuer Nutzer */}
      <div className="rounded-xl border border-sky/20 bg-sky/5 px-4 py-3 mb-1">
        <p className="text-xs text-muted">
          <strong className="text-ink">Tipp:</strong> Quellen mit
          {" "}<Badge tone="success" className="gap-1 inline-flex"><Zap size={9} />Schnell</Badge>{" "}
          laufen parallel und liefern in Sekunden Ergebnisse.
          {" "}<Badge tone="amber" className="gap-1 inline-flex"><Clock size={9} />Browser</Badge>{" "}
          Quellen benoetigen Google Chrome und koennen 1-3 Minuten dauern. Noch kein Chrome? <a href="https://www.google.com/chrome/" target="_blank" rel="noopener noreferrer" class="text-sky underline">Hier herunterladen</a>.
          Wenn eine Browser-Quelle nicht funktioniert, kannst du Claude bitten, direkt auf dem Portal zu suchen und Stellen manuell zu uebernehmen.
        </p>
      </div>

      {sources.map((source) => {
        const loginJob = loginJobs[source.key];
        const loginRunning = loginJob?.status === "running";
        const loginReady = loginJob?.status === "fertig";

        return (
          <Card
            key={source.key}
            data-source-key={source.key}
            className="glass-card-soft rounded-xl shadow-none"
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0 space-y-2">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold text-ink">{source.name}</span>
                  <Badge tone={source.active ? "success" : "neutral"}>
                    {source.veraltet ? "Manuell" : source.active ? "Aktiv" : "Inaktiv"}
                  </Badge>
                  {speedBadge(source.geschwindigkeit)}
                  {source.beta ? (
                    <Badge tone="amber">Beta</Badge>
                  ) : null}
                  {source.login_erforderlich ? (
                    <Badge tone="amber">Login noetig</Badge>
                  ) : null}
                  {loginJob?.status ? (
                    <Badge tone={loginTone(loginJob.status)}>
                      {loginJob.status === "running"
                    ? "Login laeuft"
                        : loginJob.status === "fertig"
                          ? "Session bereit"
                          : "Login offen"}
                    </Badge>
                  ) : null}
                </div>
                <p className="text-sm text-muted">{source.beschreibung}</p>
                {source.login_erforderlich && !source.beta ? (
                  <p className="text-xs text-amber">
                    Beim ersten Start oeffnet sich ein Browser-Fenster zur Anmeldung. Danach laeuft
                    die Suche mit gespeicherter Session weiter.
                  </p>
                ) : null}
                {source.warnung ? (
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
                {source.active && source.profil_optimierung ? (
                  <div className="mt-1 rounded-lg border border-amber/15 bg-amber/5 px-3 py-2">
                    <p className="text-xs text-amber">{source.profil_optimierung}</p>
                  </div>
                ) : null}
              </div>

              <div className="flex shrink-0 self-center items-center gap-3">
                {source.login_erforderlich && !loginReady ? (
                  <Button
                    size="sm"
                    variant="ghost"
                    disabled={loginRunning}
                    onClick={() => onStartLogin?.(source)}
                  >
                    {loginRunning ? <LoaderCircle className="animate-spin" size={14} /> : null}
                  {loginRunning ? "Login laeuft" : "Login starten"}
                  </Button>
                ) : null}
                <CheckboxInput
                  className="shrink-0 flex-none self-center"
                  checked={Boolean(source.active)}
                  onChange={(event) => {
                    const checked = event.target.checked;
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
