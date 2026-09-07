/**
 * OffenBlock — v1.7.31 (#976 G27, #982 G30, #983 G31)
 *
 * Der eine Block "Offen" auf dem Dashboard.
 *
 * Vorher stand dieselbe Lage dreimal auf einem Bildschirm, in drei
 * Zaehlweisen: eine rote Karte "2 Aufgaben ueberfaellig", darunter die
 * Headline "Es gibt ueberfaellige Nachfassaktionen", und darunter die
 * Zeile "Prioritaet 3 — Bei 2 Bewerbung(en) solltest du nachhaken".
 * Fachlich sind das zwei Toepfe, fuer den Menschen ist es eine Frage:
 * was muss ich tun. Er sah dreimal eine Zwei und musste selbst
 * herausfinden, dass es nicht dieselbe Zwei ist.
 *
 * Quelle ist /api/dashboard/offen und damit `services/aufgaben_sicht.py`
 * — dasselbe Nadeloehr wie der Aufgaben-Tab und das MCP-Tool
 * `aufgaben_uebersicht`. Nicht "dieselbe Logik wie", sondern dieselbe.
 *
 * Zeilenregel (#984): Titel, Datum oder Zahl, Herkunft. Kein
 * Beschreibungssatz, der den Titel in anderen Worten wiederholt. Der
 * leere Zustand ist eine Zeile, kein Rahmen.
 *
 * K17/#700 bleibt in der Sache: eine Nachfassung ist kein Termin. Die
 * Unterscheidung leistet die Herkunft an jeder Zeile — und nur Termine
 * tragen eine Uhrzeit.
 */
import { useCallback, useEffect, useState } from "react";
import { AlarmClock, BellRing, Calendar, Check, ClipboardList, Sparkles } from "lucide-react";

import { Button, Card } from "@/components/ui";
import { NICHTS_OFFEN } from "@/lib/dashboardRegeln";

const HERKUNFT = {
  todo: { label: "Aufgabe", icon: ClipboardList, ton: "text-teal" },
  nachfass: { label: "Nachfassen", icon: BellRing, ton: "text-amber" },
  termin: { label: "Termin", icon: Calendar, ton: "text-sky" },
  // G24/#964: nur deklarierte Tokens. `text-violet` gibt es nicht —
  // Tailwind erzeugt dafuer keine Regel UND keinen Fehler.
  vorbereitung: { label: "Vorbereitung", icon: Sparkles, ton: "text-amber" },
};

const GRUPPEN = [
  { key: "ueberfaellig", label: "Überfällig", ton: "text-coral" },
  { key: "heute", label: "Heute", ton: "text-ink" },
  { key: "diese_woche", label: "Diese Woche", ton: "text-muted" },
];

function datumsLabel(eintrag) {
  const roh = String(eintrag.faellig_am || "");
  if (!roh) return "";
  const [jahr, monat, tag] = roh.split("-");
  if (!tag) return roh;
  const datum = `${tag}.${monat}.${jahr}`;
  // Nur Termine tragen eine Uhrzeit (K17/#700, Folgefehler K19 waren
  // Nachfassungen "um 02:00 Uhr").
  return eintrag.uhrzeit ? `${datum}, ${eintrag.uhrzeit} Uhr` : datum;
}

export default function OffenBlock({ navigateTo, refreshChrome, onPrompt }) {
  const [block, setBlock] = useState(null);

  const laden = useCallback(() => {
    fetch("/api/dashboard/offen")
      .then((r) => (r.ok ? r.json() : null))
      .then((d) => d && setBlock(d))
      .catch(() => {});
  }, []);

  useEffect(() => {
    laden();
  }, [laden]);

  async function abhaken(eintrag) {
    const pfade = {
      todo: `/api/tasks/${eintrag.id}/complete`,
      nachfass: `/api/follow-ups/${eintrag.id}/complete`,
    };
    const pfad = pfade[eintrag.herkunft];
    if (!pfad) return;
    try {
      await fetch(pfad, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
      laden();
      refreshChrome?.();
    } catch {
      /* still — die Liste laedt beim naechsten Mal neu */
    }
  }

  function oeffnen(eintrag) {
    if (eintrag.herkunft === "termin") return navigateTo?.("kalender");
    if (eintrag.herkunft === "vorbereitung" && eintrag.prompt) {
      return onPrompt?.(eintrag.prompt, eintrag);
    }
    return navigateTo?.("aufgaben");
  }

  if (!block) return null;

  if (block.leer) {
    return (
      <Card className="rounded-2xl">
        <div className="flex items-center justify-between gap-3">
          <p className="text-sm text-muted">{NICHTS_OFFEN}</p>
          <Button size="sm" variant="ghost" onClick={() => navigateTo?.("aufgaben")}>
            Aufgaben
          </Button>
        </div>
      </Card>
    );
  }

  const dringend = block.ueberfaellig_anzahl > 0;

  return (
    <Card className={dringend ? "rounded-2xl border border-coral/40 bg-coral/[0.06]" : "rounded-2xl"}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <AlarmClock size={16} className={dringend ? "text-coral" : "text-muted/60"} />
          <h2 className="text-sm font-semibold text-ink">Offen</h2>
        </div>
        <Button size="sm" variant="ghost" onClick={() => navigateTo?.("aufgaben")}>
          {block.spaeter_anzahl > 0 ? `Alle Aufgaben (${block.spaeter_anzahl} später)` : "Alle Aufgaben"}
        </Button>
      </div>

      <div className="mt-3 grid gap-3">
        {GRUPPEN.map(({ key, label, ton }) => {
          const zeilen = block.gruppen?.[key] || [];
          if (!zeilen.length) return null;
          return (
            <div key={key}>
              <p className={`text-[11px] font-semibold uppercase tracking-[0.14em] ${ton}`}>
                {label}
              </p>
              <ul className="mt-1.5 space-y-1">
                {zeilen.map((e) => {
                  const meta = HERKUNFT[e.herkunft] || HERKUNFT.todo;
                  const Icon = meta.icon;
                  const abhakbar = e.herkunft === "todo" || e.herkunft === "nachfass";
                  return (
                    <li
                      key={`${e.herkunft}-${e.id}`}
                      className="flex items-center gap-2 text-sm text-ink"
                    >
                      {abhakbar ? (
                        <button
                          type="button"
                          title="Erledigt"
                          onClick={() => abhaken(e)}
                          className="shrink-0 rounded-md border border-teal/40 bg-teal/10 p-0.5 text-teal hover:bg-teal/25"
                        >
                          <Check size={12} />
                        </button>
                      ) : (
                        <Icon size={13} className={`shrink-0 ${meta.ton}`} />
                      )}
                      <button
                        type="button"
                        onClick={() => oeffnen(e)}
                        className="min-w-0 flex-1 truncate text-left hover:text-sky"
                      >
                        <span className="font-medium">{e.titel}</span>
                        {e.firma ? <span className="text-muted/60"> — {e.firma}</span> : null}
                      </button>
                      <span className="shrink-0 text-xs text-muted/70">{datumsLabel(e)}</span>
                      <span className="shrink-0 text-[11px] uppercase tracking-[0.1em] text-muted/45">
                        {meta.label}
                      </span>
                    </li>
                  );
                })}
              </ul>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
