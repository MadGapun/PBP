/**
 * Nur einen Erfolg merken — #1144.
 *
 * Die Kontakt-Kategorien wurden einmal je Sitzung geladen und gemerkt. Schlug
 * das Laden fehl (der Server startete gerade, das Netz hakte), galt "keine
 * Kategorien" bis zum Neuladen der Seite: jede Rolle erschien als nackter
 * Schlüsselname, und niemand sagte warum. Ein Fehlschlag ist keine Auskunft.
 *
 * `laden` liefert die Daten oder wirft. Gemerkt wird nur, was ankam; wer
 * gleichzeitig fragt, teilt sich eine Anfrage; `verwerfen()` gilt auch für
 * eine Anfrage, die gerade unterwegs ist (sie brächte den alten Stand).
 *
 * Framework-frei, damit der Node-Test sie prüfen kann.
 */

const NICHTS = Symbol("nichts");

export function nurErfolgeMerken(laden, ersatz) {
  let wert = NICHTS;
  let laufend = null;
  let generation = 0;

  return {
    /** Der gemerkte Wert, oder `ersatz`, solange nichts gemerkt ist. */
    stand() {
      return wert === NICHTS ? ersatz : wert;
    },
    /** Ist ein Erfolg gemerkt? */
    gemerkt() {
      return wert !== NICHTS;
    },
    /** Der gemerkte Wert; sonst laden. Scheitert das Laden, kommt `ersatz`
     *  zurück und nichts wird gemerkt — die nächste Frage versucht es neu. */
    async holen() {
      if (wert !== NICHTS) return wert;
      if (!laufend) {
        const meine = generation;
        laufend = Promise.resolve()
          .then(laden)
          .then((daten) => {
            if (meine === generation) wert = daten;
            return daten;
          })
          .catch(() => ersatz)
          .finally(() => {
            if (meine === generation) laufend = null;
          });
      }
      return laufend;
    },
    /** Der Stand ist veraltet (etwas wurde geändert): beim nächsten Mal neu laden. */
    verwerfen() {
      generation += 1;
      wert = NICHTS;
      laufend = null;
    },
  };
}
