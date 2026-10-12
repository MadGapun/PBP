/**
 * ListenUebersicht — #1171 (G85, Baustein 5: „Listen zuerst“)
 *
 * Vor der ersten Zeile einer Liste standen Kennzahlkacheln, ein Hinweiskasten und Filter: bis zur ersten Stelle lagen rund
 * 900 Pixel, und der Hauptknopf der ersten Zeile lag unter der Falz. Jetzt steht oben EINE Zeile: was die Liste ist (die
 * Zahlen in einem Satz), der eine Hinweis mit seinem Knopf — und ein Schalter, der Kacheln und Erklärung aufklappt. Die Liste
 * beginnt im ersten Bildschirm.
 *
 * Der aufgeklappte Zustand wird je Liste im Browser gemerkt (eine Bequemlichkeit je Gerät). Vorgabe: zu.
 */
import { ChevronDown } from "lucide-react";
import { useState } from "react";

import { Card } from "@/components/ui";
import { cn } from "@/utils";

const PRAEFIX = "pbp-listenkopf-";

function lesen(id) {
  try {
    return window.localStorage.getItem(PRAEFIX + id) === "auf";
  } catch {
    return false;
  }
}

function schreiben(id, offen) {
  try {
    window.localStorage.setItem(PRAEFIX + id, offen ? "auf" : "zu");
  } catch {
    // ohne Browserspeicher gilt die Wahl nur fuer diese Ansicht
  }
}

export default function ListenUebersicht({ id, zusammenfassung, badge = null, titel = "", aktion = null, children, className }) {
  const [offen, setOffen] = useState(() => lesen(id));

  return (
    <Card className={cn("rounded-2xl !py-3", className)} data-listen-uebersicht={id} data-offen={offen ? "ja" : "nein"}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <button
          type="button"
          aria-expanded={offen}
          data-listen-uebersicht-schalter
          onClick={() => { setOffen(!offen); schreiben(id, !offen); }}
          title={offen ? "Kennzahlen und Erklärung einklappen" : "Kennzahlen und Erklärung zeigen"}
          className="inline-flex items-center gap-1.5 rounded-lg px-1.5 py-1 text-[13px] font-medium text-ink transition-colors hover:bg-white/[0.06]"
        >
          <ChevronDown size={14} aria-hidden="true" className={cn("shrink-0 text-muted transition-transform", offen && "rotate-180")} />
          <span data-listen-uebersicht-zeile>{zusammenfassung}</span>
        </button>
        {badge}
        {titel ? <span className="min-w-0 flex-1 text-[13px] text-muted" data-listen-uebersicht-titel>{titel}</span> : <span className="flex-1" />}
        {aktion}
      </div>
      {offen ? <div className="mt-4 grid gap-4" data-listen-uebersicht-inhalt>{children}</div> : null}
    </Card>
  );
}
