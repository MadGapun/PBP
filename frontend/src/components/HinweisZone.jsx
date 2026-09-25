/**
 * Hinweiszone — G60 (#1087 B1, B5, A5).
 *
 * Höchstens EIN Banner, nur auf dem Dashboard. Welcher, entscheidet
 * `lib/hinweisZone.js` (Reihenfolge mit Node-Test). Diese Komponente
 * zeichnet ihn nur und führt die Aktion aus.
 */
import { AlertCircle, Info } from "lucide-react";

import { Button, Card } from "@/components/ui";
import { useApp } from "@/app-context";

export default function HinweisZone({ hinweis }) {
  const { navigateTo, startJobsuche, refreshChrome } = useApp();
  if (!hinweis) return null;

  function ausfuehren() {
    const a = hinweis.aktion || {};
    if (a.art === "jobsuche") return startJobsuche();
    if (a.art === "navigieren") return navigateTo(a.ziel, a.tab ? { tab: a.tab } : undefined);
    if (a.art === "link" && a.url) return window.open(a.url, "_blank", "noopener,noreferrer");
    if (a.art === "anleitung") return refreshChrome();
    return undefined;
  }

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
        <div className="min-w-0">
          <p className={`text-sm font-semibold ${amber ? "text-amber" : "text-ink"}`}>{hinweis.titel}</p>
          <p className="mt-0.5 text-[13px] text-muted">{hinweis.text}</p>
        </div>
      </div>
      {hinweis.aktion ? (
        <Button size="sm" variant={amber ? "primary" : "secondary"} onClick={ausfuehren}>
          {hinweis.aktion.art === "anleitung" ? "Verbindung prüfen" : hinweis.aktion.label}
        </Button>
      ) : null}
    </Card>
  );
}
