/**
 * Modell-Download der lokalen KI — #1154 Punkt 1.
 *
 * Vorher wartete ein einziger Aufruf auf das Ende des Downloads: die Seite zeigte
 * nur "Lädt ...", und bei einem großen Modell oder einer langsamen Leitung stand
 * nach zehn Minuten "Download fehlgeschlagen", obwohl Ollama weiterlud. Jetzt
 * startet der Aufruf einen Job und antwortet sofort; die Seite fragt den Stand
 * alle anderthalb Sekunden ab und zeigt Prozent und einen Satz.
 *
 * Framework-frei, damit der Node-Test sie prüfen kann.
 */

/** Wie oft die Seite den Stand abfragt (Millisekunden). */
export const ABFRAGE_MS = 1500;
/** So viele Abfragen hintereinander ohne Antwort, bevor die Anzeige aufgibt. */
export const FEHLVERSUCHE_BIS_AUFGABE = 4;

const ENDE = ["fertig", "fehler", "abgebrochen"];

/** Ist der Download vorbei (gelungen oder nicht)? */
export function istEnde(job) {
  return !!job && ENDE.includes(job.status);
}

/** Die Prozentzahl, immer zwischen 0 und 100. */
export function prozent(job) {
  const p = Number(job && job.progress);
  if (!Number.isFinite(p)) return 0;
  return Math.max(0, Math.min(100, Math.round(p)));
}

/** Der Satz unter dem Balken. */
export function anzeigeText(job, modell) {
  if (!job) return `Starte den Download von ${modell} ...`;
  if (job.status === "fehler") {
    return `Download fehlgeschlagen: ${job.error || job.message || "unbekannter Fehler"}`;
  }
  if (job.status === "abgebrochen") {
    return "Der Download wurde abgebrochen, weil PBP zwischendurch beendet wurde. Starte ihn noch einmal; bereits geladene Teile bleiben erhalten.";
  }
  if (job.status === "fertig") return `${modell} ist installiert.`;
  return job.message || "Lade ...";
}

/**
 * Verfolgt einen Download bis zum Ende.
 *
 * `holen(jobId)` liefert den Stand (oder wirft), `beiStand(job)` bekommt jeden Stand,
 * `warten(ms)` pausiert, `abgebrochen()` beendet die Schleife, ohne einen Stand zu
 * liefern (die Seite wurde verlassen). Antwortet der Server `FEHLVERSUCHE_BIS_AUFGABE`
 * Mal hintereinander nicht, endet die Schleife mit einem Fehlerstand — der Download
 * kann in Ollama trotzdem weiterlaufen, und der Text sagt das.
 */
export async function verfolgen(holen, jobId, optionen = {}) {
  const beiStand = optionen.beiStand || (() => {});
  const warten = optionen.warten || ((ms) => new Promise((r) => setTimeout(r, ms)));
  const abgebrochen = optionen.abgebrochen || (() => false);
  let fehlversuche = 0;
  for (;;) {
    if (abgebrochen()) return null;
    try {
      const job = await holen(jobId);
      fehlversuche = 0;
      beiStand(job);
      if (istEnde(job)) return job;
    } catch (err) {
      fehlversuche += 1;
      if (fehlversuche >= FEHLVERSUCHE_BIS_AUFGABE) {
        return {
          job_id: jobId,
          status: "fehler",
          progress: 0,
          message: "",
          error: "PBP antwortet nicht mehr. Der Download läuft in Ollama vielleicht weiter; schau später im Tab Lokale KI nach.",
        };
      }
    }
    await warten(ABFRAGE_MS);
  }
}
