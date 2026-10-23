// #1187 (Stufe 3): nach einem Browserlauf ist der naechste Schritt in PBP, nicht im Chat.
//
// Zeigt, wie viele Stellen noch auf das Urteil des Menschen warten (dieselbe Regel wie der Filter "Prüfstand: nur ungeprüfte"),
// und was Claude nach dem Lesen aussortiert hat. Letzteres ist die Zahl, bei der man hinschauen soll: aussortiert wird nur,
// was offensichtlich fachfremd oder geschlossen ist - ob das stimmt, entscheidet der Mensch. Deshalb steht der Rückweg
// HIER: die neuesten Einträge mit Grund und je ein Klick auf "Zurückholen", ohne die Karte zu verlassen.
// Nichts zu tun: keine Karte. Die Zahlen kommen vom Server (`services/stellen_zu_pruefen`).

import { useCallback, useEffect, useState } from "react";
import { ClipboardCheck, EyeOff, RotateCcw } from "lucide-react";

import { optionalApi, postJson } from "@/api";
import { Button, Card } from "@/components/ui";
import { grundText } from "@/lib/anzeige";
import { zuAusgeblendetenStellen, zuUngeprueftenStellen } from "@/lib/wege";

export default function StellenZuPruefen({ navigateTo, anlass = 0 }) {
  const [daten, setDaten] = useState(null);
  const [offen, setOffen] = useState(false);
  const [beschaeftigt, setBeschaeftigt] = useState("");

  const laden = useCallback(
    () => optionalApi("/api/stellen/zu-pruefen").then((antwort) => antwort || null).catch(() => null),
    [],
  );

  useEffect(() => {
    let abgebrochen = false;
    laden().then((antwort) => { if (!abgebrochen) setDaten(antwort); });
    return () => { abgebrochen = true; };
  }, [anlass, laden]);

  const zurueckholen = async (hash) => {
    setBeschaeftigt(hash);
    try {
      await postJson("/api/jobs/restore", { hash });
      setDaten(await laden());
    } catch {
      // Die Karte bleibt, wie sie ist; die Liste unter Stellen › Ausgeblendet zeigt den Stand und holt ebenfalls zurück.
    } finally {
      setBeschaeftigt("");
    }
  };

  // Die Wege stehen in lib/wege.js: eine Karte, die selbst `navigateTo("stellen", {...})` zuschneidet, waere die
  // zweite Fassung desselben Sprungs (#1171).
  const oeffne = (ziel) => navigateTo(ziel.seite, ziel.intent);

  const neu = Number(daten?.neu) || 0;
  const claude = Number(daten?.von_claude_aussortiert) || 0;
  const liste = Array.isArray(daten?.aussortiert) ? daten.aussortiert : [];
  if (!neu && !claude) return null;

  return (
    <Card className="mt-3 rounded-2xl" data-stellen-zu-pruefen>
      <div className="space-y-3">
        {neu > 0 && (
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="flex items-center gap-2 text-sm text-ink" data-zu-pruefen-neu>
              <ClipboardCheck size={16} className="text-teal" aria-hidden="true" />
              <span>
                <strong>{neu}</strong> {neu === 1 ? "neue Stelle wartet" : "neue Stellen warten"} auf dein Urteil
                <span className="text-muted"> (insgesamt {daten.ungeprueft} ungeprüft)</span>
              </span>
            </p>
            <Button size="sm" onClick={() => oeffne(zuUngeprueftenStellen())}>
              Stellen prüfen
            </Button>
          </div>
        )}
        {claude > 0 && (
          <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <p className="flex items-center gap-2 text-sm text-ink" data-zu-pruefen-claude>
                <EyeOff size={16} className="text-amber" aria-hidden="true" />
                <span>
                  <strong>{claude}</strong> {claude === 1 ? "Stelle hat" : "Stellen hat"} Claude nach dem Lesen aussortiert
                  <span className="text-muted"> — stimmt das? Du kannst sie zurückholen</span>
                </span>
              </p>
              <Button size="sm" variant="secondary" aria-expanded={offen} onClick={() => setOffen((v) => !v)}>
                {offen ? "Einklappen" : "Ansehen"}
              </Button>
            </div>
            {offen && (
              <div className="space-y-2" data-zu-pruefen-liste>
                <ul className="divide-y divide-white/5 rounded-xl border border-white/5">
                  {liste.map((stelle) => (
                    <li key={stelle.hash} className="flex flex-wrap items-center justify-between gap-2 px-3 py-2" data-zu-pruefen-zeile>
                      <span className="min-w-0 text-sm text-ink">
                        <strong className="font-medium">{stelle.titel || "Ohne Titel"}</strong>
                        {stelle.firma ? <span className="text-muted"> · {stelle.firma}</span> : null}
                        {stelle.grund ? <span className="text-muted"> — {grundText(stelle.grund)}</span> : null}
                      </span>
                      <Button
                        size="sm"
                        variant="ghost"
                        disabled={beschaeftigt === stelle.hash}
                        onClick={() => zurueckholen(stelle.hash)}
                      >
                        <RotateCcw size={14} aria-hidden="true" />
                        Zurückholen
                      </Button>
                    </li>
                  ))}
                </ul>
                <div className="flex flex-wrap items-center justify-between gap-2 text-[13px] text-muted">
                  <span>
                    {claude > liste.length
                      ? `Die neuesten ${liste.length} von ${claude}. Alle stehen unter Stellen › Aussortiert, Herkunft „von Claude“.`
                      : "Das sind alle."}
                  </span>
                  <Button size="sm" variant="ghost" onClick={() => oeffne(zuAusgeblendetenStellen())}>
                    In der Liste öffnen
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </Card>
  );
}
