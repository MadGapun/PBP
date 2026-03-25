import { AlertTriangle, LoaderCircle } from "lucide-react";

import { Badge, Button, Card, CheckboxInput } from "@/components/ui";

function loginTone(status) {
  if (status === "fehler") return "danger";
  if (status === "fertig") return "success";
  return "sky";
}

export default function SourceSelectionList({
  sources,
  loginJobs = {},
  onToggle,
  onStartLogin,
}) {
  return (
    <div className="grid gap-3">
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
                    {source.active ? "Aktiv" : "Inaktiv"}
                  </Badge>
                  {source.beta ? (
                    <Badge tone="amber">Beta</Badge>
                  ) : null}
                  {source.login_erforderlich ? (
                    <Badge tone="amber">Login nötig</Badge>
                  ) : null}
                  {loginJob?.status ? (
                    <Badge tone={loginTone(loginJob.status)}>
                      {loginJob.status === "running"
                    ? "Login läuft"
                        : loginJob.status === "fertig"
                          ? "Session bereit"
                          : "Login offen"}
                    </Badge>
                  ) : null}
                </div>
                <p className="text-sm text-muted">{source.beschreibung}</p>
                {source.login_erforderlich && !source.beta ? (
                  <p className="text-xs text-amber">
                    Beim ersten Start öffnet sich ein Browser-Fenster zur Anmeldung. Danach läuft
                    die Suche mit gespeicherter Session weiter.
                  </p>
                ) : null}
                {source.beta && source.warnung ? (
                  <div className="mt-1 rounded-lg border border-amber/30 bg-amber/10 px-3 py-2">
                    <div className="mb-1 flex items-center gap-1.5">
                      <AlertTriangle size={13} className="shrink-0 text-amber" />
                      <span className="text-xs font-semibold text-amber">Beta-Feature</span>
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
                  {loginRunning ? "Login läuft" : "Login starten"}
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

