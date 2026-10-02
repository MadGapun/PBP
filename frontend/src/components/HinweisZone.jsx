/**
 * Hinweiszone — G60 (#1087 B1, B5, A5).
 *
 * Höchstens EIN Banner, nur auf dem Dashboard. Welcher, entscheidet
 * `lib/hinweisZone.js` (Reihenfolge mit Node-Test). Diese Komponente
 * zeichnet ihn nur und führt die Aktion aus.
 *
 * Auto-Update (#1093): ein Hinweis kann mehrere Aktionen tragen (`aktionen`) und einen Fortschritt
 * (`fortschritt`). Die Regeln dafür stehen in `lib/autoUpdate.js`.
 */
import { oeffneAdresse } from "@/lib/webAdresse";
import { AlertCircle, Info } from "lucide-react";

import { Button, Card } from "@/components/ui";
import { useApp } from "@/app-context";

export default function HinweisZone({ hinweis }) {
  const { navigateTo, startJobsuche, refreshChrome, autoUpdateAktion } = useApp();
  if (!hinweis) return null;

  function ausfuehren(a) {
    if (!a) return undefined;
    if (a.art === "jobsuche") return startJobsuche();
    if (a.art === "navigieren") return navigateTo(a.ziel, a.tab ? { tab: a.tab } : undefined);
    if (a.art === "update-optionen") return navigateTo("einstellungen", { tab: "updates" });
    if (typeof a.art === "string" && a.art.startsWith("update-")) return autoUpdateAktion(a);
    if (a.art === "link" && a.url) return oeffneAdresse(a.url);
    if (a.art === "anleitung") return refreshChrome();
    return undefined;
  }

  const aktionen = hinweis.aktionen || (hinweis.aktion ? [hinweis.aktion] : []);
  const amber = hinweis.ton === "amber";
  const Icon = amber ? AlertCircle : Info;
  return (
    <Card
      data-hinweiszone={hinweis.id}
      role="status"
      className={`mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl ${amber ? "glass-banner glass-banner-amber" : "glass-card-soft"}`}
    >
      <div className="flex min-w-0 flex-1 items-start gap-3">
        <Icon size={18} className={amber ? "mt-0.5 shrink-0 text-amber" : "mt-0.5 shrink-0 text-sky"} aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className={`text-sm font-semibold ${amber ? "text-amber" : "text-ink"}`}>{hinweis.titel}</p>
          <p className="mt-0.5 text-[13px] text-muted">{hinweis.text}</p>
          {typeof hinweis.fortschritt === "number" ? (
            <div className="mt-2" data-hinweis-fortschritt={hinweis.fortschritt}>
              <div className="h-2 w-full max-w-md overflow-hidden rounded-full bg-white/10" role="progressbar"
                aria-valuemin={0} aria-valuemax={100} aria-valuenow={hinweis.fortschritt}>
                <div className="h-full rounded-full bg-sky transition-all" style={{ width: `${hinweis.fortschritt}%` }} />
              </div>
            </div>
          ) : null}
        </div>
      </div>
      {aktionen.length ? (
        <div className="flex flex-wrap items-center gap-2">
          {aktionen.map((a, i) => (
            <Button key={`${a.art}-${a.antwort || a.label}`} size="sm" title={a.titel}
              variant={i === 0 ? (amber ? "primary" : "secondary") : "ghost"}
              data-hinweis-aktion={a.antwort || a.art}
              onClick={() => ausfuehren(a)}>
              {a.art === "anleitung" ? "Verbindung prüfen" : a.label}
            </Button>
          ))}
        </div>
      ) : null}
    </Card>
  );
}
