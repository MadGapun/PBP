/**
 * Datenguete — was PBP ueber eine Stelle WEISS (#989, v1.7.39)
 *
 * Spiegelt `services/datenguete.py`. Dieselbe Frage muss auf beiden
 * Seiten dieselbe Antwort bekommen, sonst sortiert die Liste im Browser
 * anders als die Liste im Chat — genau die Divergenz, gegen die #987
 * angetreten ist, nur eine Etage hoeher.
 *
 * `datenguete.test.mjs` prueft beide Seiten an denselben Faellen; der
 * CI-Schritt laeuft wie bei `jobLink.js` (#765) und `dashboardRegeln.js`
 * (#974) mit.
 *
 * Der Befund dahinter: wo eine Information fehlt, setzt ein Punktesystem
 * einen neutralen Wert ein — und neutral heisst dort nicht "unbekannt",
 * sondern "kostet nichts". Was nichts kostet, steigt in der Sortierung.
 * Gemessen: eine vollstaendig beschriebene, fachlich passende Stelle
 * bekam 32 Punkte, ein inhaltsleerer Titel 101.
 */

/** Ab dieser Laenge traegt ein Anzeigentext eine Bewertung. */
export const MIN_BESCHREIBUNG = 50;

export const MITMISCHEN = "mitmischen";
export const NACHRANGIG = "nachrangig";
export const STRENG = "streng";

export function hatBewertungsgrundlage(job) {
  return String(job?.description || "").trim().length >= MIN_BESCHREIBUNG;
}

/**
 * 0 = mit Bewertungsgrundlage, 1 = ohne. Kleiner steht weiter oben.
 *
 * Bewusst nur die Beschreibung und nicht die Zahl der ungeprueften
 * Dimensionen: der Anzeigentext traegt fast den ganzen Score, die
 * anderen sind einzelne Zu- und Abschlaege. Eine Stelle ohne bekannte
 * Entfernung ist ungenau bewertet; eine ohne Text ist GAR nicht
 * bewertet. Nur das rechtfertigt eine eigene Gruppe — sonst landet fast
 * alles in Gruppe 1 und die Trennung sagt nichts mehr.
 */
export function guetRang(job) {
  return hatBewertungsgrundlage(job) ? 0 : 1;
}

/** Der Rang, wie ihn die Liste anwendet — abhaengig von der Einstellung. */
export function sortierRang(job, umgang = NACHRANGIG) {
  return umgang === MITMISCHEN ? 0 : guetRang(job);
}

/**
 * Vergleichsfunktion fuer die Liste: erst Datenguete, dann das
 * gewaehlte Kriterium. Der Score selbst bleibt unangetastet — er misst,
 * was in der Anzeige steht. Die Reihenfolge ist eine Darstellung, und
 * dort gehoert die Unterscheidung hin.
 */
export function vergleicheMitGuete(a, b, weiter, umgang = NACHRANGIG) {
  const rang = sortierRang(a, umgang) - sortierRang(b, umgang);
  if (rang !== 0) return rang;
  return weiter(a, b);
}

/**
 * Was an der Zeile steht — oder null, wenn nichts fehlt.
 *
 * Die Liste bekommt den Befund seit v1.7.39 vom Server mit
 * (`job.datenguete`); diese Funktion ist der Rueckfall fuer Bestaende,
 * die noch ohne kommen, und deckt dort das tragende Feld ab.
 */
export function kurzmarke(job) {
  if (job?.datenguete?.text) return job.datenguete;
  if (hatBewertungsgrundlage(job)) return null;
  return {
    ungeprueft: ["beschreibung"],
    text: "Ungeprüft: Anzeigentext",
    ohne_bewertungsgrundlage: true,
  };
}
