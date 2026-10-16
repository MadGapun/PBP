import { useEffect, useState } from "react";

import { api, putJson } from "@/api";
import { Button, Card, SectionHeading, TextInput } from "@/components/ui";
import { standortSatz } from "@/lib/standort";

/**
 * Von wo aus PBP Entfernungen rechnet (#1090).
 *
 * Bis v1.7.139 gab es im Dashboard kein Feld dafür: gesetzt wurde der
 * Standort nur über Claude, und der Wohnort aus dem Profil zählte nicht.
 * Die Karte zeigt, welcher Ort gilt und woher er kommt, und lässt einen
 * eigenen Ort setzen. Leer heißt: zurück zum Wohnort aus dem Profil.
 * Der Satz dazu steht in `lib/standort.js` (#1235), damit er ohne Browser prüfbar ist.
 */
export default function StandortKarte({ pushToast }) {
  const [befund, setBefund] = useState(null);
  const [eingabe, setEingabe] = useState("");
  const [laeuft, setLaeuft] = useState(false);

  useEffect(() => {
    let aktiv = true;
    api("/api/standort")
      .then((b) => {
        if (!aktiv) return;
        setBefund(b);
        setEingabe(b.quelle === "eigene" ? b.ort || "" : "");
      })
      .catch(() => {});
    return () => {
      aktiv = false;
    };
  }, []);

  async function speichern(ort) {
    setLaeuft(true);
    try {
      const erg = await putJson("/api/standort", { ort });
      setBefund(erg.befund);
      setEingabe(erg.befund?.quelle === "eigene" ? erg.befund.ort || "" : "");
      pushToast?.(
        ort
          ? "Standort gespeichert. Entfernungen und Nähe-Punkte werden im Hintergrund neu gerechnet."
          : "Es gilt wieder dein Wohnort aus dem Profil.",
        "success",
      );
    } catch (error) {
      pushToast?.(error.message, "danger");
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <Card id="suche-standort" className="rounded-2xl" data-testid="standort-karte">
      <SectionHeading
        title="Standort"
        description="Von wo aus PBP Entfernungen zu Stellen rechnet."
      />
      <p className="text-sm text-ink" data-testid="standort-satz">
        {standortSatz(befund)}
      </p>
      <form
        className="mt-3 flex flex-col gap-2 sm:flex-row"
        onSubmit={(e) => {
          e.preventDefault();
          speichern(eingabe.trim());
        }}
      >
        <TextInput
          aria-label="Eigener Standort"
          placeholder={befund?.profil_wohnort || "PLZ und Ort"}
          value={eingabe}
          onChange={(e) => setEingabe(e.target.value)}
          className="sm:flex-1"
        />
        <Button type="submit" disabled={laeuft || !eingabe.trim()}>
          Standort setzen
        </Button>
        {befund?.quelle === "eigene" ? (
          <Button variant="secondary" disabled={laeuft} onClick={() => speichern("")}>
            Wohnort aus dem Profil nehmen
          </Button>
        ) : null}
      </form>
    </Card>
  );
}
