// #1049 (G50): Quellen, die nur im Browser liefern — und der Weg zu Claude.
//
// Der Knopf "Interne Jobsuche starten" laeuft nur intern; Quellen mit
// eingeloggtem Konto ueberspringt er bewusst (#488). Bis v1.7.113 fuehrte
// von dort kein Weg zum Lauf ueber die Chrome-Erweiterung, und sechs aktive
// Quellen trugen monatelang nichts bei, ohne dass es irgendwo stand.
//
// Liste UND Prompt kommen vom Server (`services/browser_handoff.py`). Eine
// zweite Fassung des Prompts hier waere das Muster aus #963 im Frontend —
// und der Prompt setzt die Suchbegriffe je Portal ein, die nur der Server
// kennt.

import { useEffect, useState } from "react";
import { ClipboardCopy, Globe } from "lucide-react";

import { optionalApi } from "@/api";
import { useApp } from "@/app-context";
import { Badge, Button, Card } from "@/components/ui";

export default function BrowserHandoffKarte({ anlass = 0 }) {
  const { copyPrompt } = useApp();
  const [daten, setDaten] = useState(null);

  // `anlass` zaehlt der Aufrufer hoch, wenn ein Suchlauf gestartet wurde —
  // dann gilt die neue Auswahl.
  useEffect(() => {
    let abgebrochen = false;
    optionalApi("/api/jobsuche/browser-quellen")
      .then((antwort) => { if (!abgebrochen) setDaten(antwort || null); })
      .catch(() => { if (!abgebrochen) setDaten(null); });
    return () => { abgebrochen = true; };
  }, [anlass]);

  const quellen = Array.isArray(daten?.quellen) ? daten.quellen : [];
  const uebersprungen = quellen.filter((q) => q.art === "uebersprungen");
  const optional = quellen.filter((q) => q.art === "defekt_nur_browser");
  if (!daten?.prompt || (!uebersprungen.length && !optional.length)) return null;

  return (
    <Card className="glass-card-soft mb-4 rounded-xl">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="flex items-center gap-2 text-sm font-medium text-ink">
            <Globe size={15} />
            Diese Quellen laufen nur über den Browser
          </p>
          <p className="mt-1 text-xs text-muted/60">
            Die interne Jobsuche überspringt sie. Claude kann sie mit der
            Chrome-Erweiterung abarbeiten — der Prompt enthält deine
            Suchbegriffe je Portal.
          </p>
        </div>
        <Button variant="secondary" onClick={() => copyPrompt(daten.prompt)}>
          <ClipboardCopy size={15} />
          Prompt für Claude kopieren
        </Button>
      </div>
      {uebersprungen.length ? (
        <ul className="mt-3 grid gap-1.5">
          {uebersprungen.map((q) => (
            <li key={q.key} className="flex flex-wrap items-center gap-2 text-[13px] text-muted/80">
              <span className="font-medium text-ink">{q.name}</span>
              {q.suchprofil_vorhanden ? (
                <span className="text-muted/60">{q.suchbegriffe.join(", ")}</span>
              ) : (
                // AK 6: ohne Suchprofil ein Hinweis, keine erfundenen Begriffe.
                <Badge>kein Suchprofil hinterlegt</Badge>
              )}
            </li>
          ))}
        </ul>
      ) : null}
      {optional.length ? (
        <p className="mt-3 text-xs text-muted/50">
          Optional, als defekt geführt, im Browser erreichbar:{" "}
          {optional.map((q) => q.name).join(", ")}
        </p>
      ) : null}
    </Card>
  );
}
