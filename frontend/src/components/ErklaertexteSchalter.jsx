// Der Schalter „Erklärtexte“ unter Einstellungen › Erscheinungsbild (#1170 U11).
//
// Die langen Erklärabsätze der Seiten (`ErklaerText`) stehen standardmäßig aufgeklappt, wie bisher. Wer PBP kennt, klappt sie hier
// für alle ein; eine Wahl je Erklärtext geht dem Schalter vor, und der Schalter setzt die Einzelwahlen zurück (lib/erklaertexte.js).

import { useEffect, useState } from "react";

import { Card, SectionHeading } from "@/components/ui";
import { EREIGNIS, leseAlle, schreibeAlle } from "@/lib/erklaertexte";

export default function ErklaertexteSchalter() {
  const [zeigen, setZeigen] = useState(leseAlle);

  useEffect(() => {
    const neuLesen = () => setZeigen(leseAlle());
    window.addEventListener(EREIGNIS, neuLesen);
    return () => window.removeEventListener(EREIGNIS, neuLesen);
  }, []);

  return (
    <Card className="rounded-2xl" data-erklaertexte-schalter>
      <SectionHeading title="Erklärtexte" description="Die langen Erklärabsätze auf den Seiten." />
      <label className="flex cursor-pointer items-start gap-3 text-sm text-muted">
        <input
          type="checkbox"
          checked={zeigen}
          onChange={(event) => schreibeAlle(event.target.checked)}
          className="mt-0.5 h-4 w-4 accent-sky"
          data-erklaertexte-haken
        />
        <span>
          Erklärtexte aufgeklappt zeigen
          <span className="mt-0.5 block text-xs">
            Ohne Haken stehen sie eingeklappt da; ein Klick auf ihre Überschrift öffnet sie. Das gilt für diesen Browser.
          </span>
        </span>
      </label>
    </Card>
  );
}
