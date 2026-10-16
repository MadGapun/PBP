// Einstellungen > Lokale KI: der Schalter fuer die Kurzantwort der interaktiven Hilfe (#1233, F51, Beta).
//
// Die Hilfe zeigt immer Karten mit Quelle (Suche ohne KI). Mit diesem Schalter formuliert die lokale KI zusaetzlich eine kurze Antwort aus den
// gefundenen Abschnitten. Standardmaessig AUS: gemessen an ungesehenen Fragen findet die Suche den richtigen Abschnitt in rund drei von vier
// Faellen unter den ersten drei, und ein Modell, das aus einem falschen Abschnitt eine glatte Antwort baut, waere schlimmer als eine Karte.
import { useEffect, useState } from "react";

import { api, putJson } from "@/api";
import { Badge, Card, CheckboxInput, SectionHeading } from "@/components/ui";
import { kiGrundText } from "@/lib/hilfeFrage";

export default function HilfeKiKarte({ pushToast }) {
  const [stand, setStand] = useState(null);
  const [speichert, setSpeichert] = useState(false);

  useEffect(() => {
    let aktiv = true;
    api("/api/hilfe/ki").then((d) => { if (aktiv) setStand(d); }).catch(() => {});
    return () => { aktiv = false; };
  }, []);

  async function umschalten(an) {
    setSpeichert(true);
    try {
      const antwort = await putJson("/api/hilfe/ki", { formulieren: an });
      setStand((s) => ({ ...(s || {}), formulieren: antwort.formulieren }));
      pushToast?.(an ? "Die Hilfe formuliert jetzt Kurzantworten (Beta)." : "Die Hilfe zeigt wieder nur Karten.", "success");
    } catch (error) {
      pushToast?.(error?.message || "Das ließ sich nicht speichern.", "danger");
    } finally {
      setSpeichert(false);
    }
  }

  if (!stand) return null;
  return (
    <Card className="rounded-2xl" data-hilfe-ki-karte>
      <SectionHeading
        title="Fragen zur Bedienung: Kurzantwort"
        description="Die Hilfe zeigt zu jeder Frage Karten mit Quelle. Wenn du magst, formuliert die lokale KI zusätzlich eine kurze Antwort aus den gefundenen Abschnitten. Frage und Text bleiben auf diesem Rechner, und nichts wird gespeichert."
        action={<Badge tone="amber">Beta</Badge>}
      />
      <div className="mt-4 flex items-start gap-3 text-sm text-ink">
        <CheckboxInput
          checked={Boolean(stand.formulieren)}
          disabled={speichert}
          onChange={(e) => umschalten(e.target.checked)}
          data-hilfe-ki-schalter
          aria-labelledby="hilfe-ki-schalter-text"
        />
        <div id="hilfe-ki-schalter-text">
          Kurzantwort von der lokalen KI formulieren lassen
          <span className="mt-0.5 block text-xs text-muted">
            Aus, solange nichts anderes gewählt ist: ein Modell kann sich irren. Deshalb steht die Quelle immer dabei, und die Antwort erscheint
            nur, wenn sie eine der Quellen nennt und nichts erfindet.
          </span>
        </div>
      </div>
      <p className="mt-3 text-xs text-muted" data-hilfe-ki-zustand>{kiGrundText(stand.zustand)}</p>
    </Card>
  );
}
