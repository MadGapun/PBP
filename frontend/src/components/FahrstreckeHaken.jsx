import { useEffect, useState } from "react";

import { api, putJson } from "@/api";

/**
 * Der Haken "Echte Fahrstrecke und Fahrzeit verwenden (nur Auto)" (#1037).
 *
 * Bis v1.7.139 war der Routing-Schlüssel zugleich der Schalter. Jetzt
 * liegt der Schlüssel in den Einstellungen und die Entscheidung hier, bei
 * den Entfernungen, auf die sie wirkt. Ohne Haken gilt überall die
 * Luftlinie — auch dort, wo schon eine Fahrstrecke gespeichert ist.
 */
export default function FahrstreckeHaken({ navigateTo, pushToast }) {
  const [stand, setStand] = useState(null);
  const [laeuft, setLaeuft] = useState(false);

  useEffect(() => {
    api("/api/routing").then(setStand).catch(() => setStand(null));
  }, []);

  if (!stand) return null;
  const schluessel = Boolean(stand.konfiguriert);

  async function umschalten(an) {
    setLaeuft(true);
    try {
      const erg = await putJson("/api/routing/aktiv", { aktiv: an });
      setStand(erg);
      pushToast(erg.hinweis, "success", { duration: 9000 });
    } catch (error) {
      pushToast(error.message, "danger");
    } finally {
      setLaeuft(false);
    }
  }

  return (
    <div className="mt-3 grid gap-1" data-testid="fahrstrecke-haken">
      <label className={`flex items-start gap-2 text-sm ${schluessel ? "text-ink" : "text-muted"}`}>
        <input
          type="checkbox"
          className="mt-0.5 h-4 w-4 accent-sky"
          checked={Boolean(stand.haken) && schluessel}
          disabled={!schluessel || laeuft}
          onChange={(event) => umschalten(event.target.checked)}
        />
        <span>Echte Fahrstrecke und Fahrzeit verwenden (nur Auto)</span>
      </label>
      <p className="text-xs text-muted">
        Die Berechnung gilt fürs Auto, nicht für Bus und Bahn. Ohne Haken
        rechnet PBP mit der Luftlinie — so, wie auch die Jobbörsen sie angeben.{" "}
        {schluessel ? (
          <span data-testid="fahrstrecke-schluessel-da">Routing-Schlüssel ist hinterlegt.</span>
        ) : (
          <>
            Dafür braucht es einen kostenlosen Routing-Schlüssel:{" "}
            <button
              type="button"
              className="text-sky underline"
              data-testid="fahrstrecke-zum-schluessel"
              onClick={() => navigateTo("einstellungen", { tab: "quellen_details" })}
            >
              Schlüssel in den Einstellungen hinterlegen
            </button>
          </>
        )}
      </p>
    </div>
  );
}
