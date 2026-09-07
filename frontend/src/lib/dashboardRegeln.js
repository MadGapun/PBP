/**
 * Regeln fuer das Dashboard (#974 G26, #984 G32).
 *
 * Zwei Befunde aus dem externen Design-Review vom 05./06.09.2026 haben
 * dieselbe Wurzel: es gab keine Regel, nur Gewohnheit. Jede neue Ansicht
 * entschied erneut, ob eine Onboarding-Kennzahl noch dazugehoert und ob
 * unter die Ueberschrift noch ein Erklaersatz muss — und entschied es
 * jedes Mal mit "ja".
 *
 * Deshalb stehen die Entscheidungen hier als pruefbare Funktionen und
 * nicht als Bedingung mitten im JSX. Muster wie `jobLink.js` (#765):
 * eigenstaendiges Modul, Test daneben, CI-Schritt.
 *
 * Die Regeln in Worten (auch in AGENTS.md):
 *
 *   1. Onboarding-Fortschritt gehoert auf die Profilseite und in die
 *      Onboarding-Stufen. Sonst ist er Wiederholung. (#974)
 *   2. Eine Dashboard-Zeile besteht aus Titel, Datum oder Zahl und
 *      Herkunft. Ein Beschreibungssatz nur, wenn er etwas traegt, das
 *      im Titel nicht steht. (#984)
 */

/** Stufen, in denen die Profil-Vollstaendigkeit handlungsleitend ist. */
export const ONBOARDING_STUFEN = ["onboarding", "profil_aufbauen"];

/**
 * Darf die KPI "% Profil vollstaendig" ausserhalb der Profilseite stehen?
 *
 * Ja, solange sie etwas zu tun gibt: in den Onboarding-Stufen, oder wenn
 * das Profil unvollstaendig ist (dann ist die Zahl unabhaengig von der
 * Stufe eine Aufgabe). Bei 100 % und stage `nachfassen` ist sie Deko —
 * genau der Fall aus dem Review.
 */
export function zeigeProfilKpi(stage, completeness) {
  const wert = Number(completeness);
  if (!Number.isFinite(wert)) return true;
  if (wert < 100) return true;
  return ONBOARDING_STUFEN.includes(String(stage || ""));
}

function normalisiere(text) {
  return String(text || "")
    .toLowerCase()
    .replace(/[–—]/g, "-")
    .replace(/[.,;:!?"'()„“’]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

/**
 * Wiederholt der Beschreibungssatz die Ueberschrift woertlich?
 *
 * Bewusst nur Enthaltensein in beide Richtungen. Die ehrliche Grenze:
 * der Fall, der das Issue ausgeloest hat — "Es gibt ueberfaellige
 * Nachfassaktionen." ueber "Einige Bewerbungen warten auf deine
 * Rueckmeldung" — teilt kein einziges Wort und ist trotzdem dieselbe
 * Aussage. Kein Wortvergleich findet das; ein Versuch damit hat hier
 * genau diesen Fall durchgewunken.
 *
 * Deshalb loest den Fall nicht der Waechter, sondern G27/#976: das Feld
 * `description` verschwindet aus der Readiness-Karte. Dieser Waechter
 * haelt danach nur noch die grobe Wiederholung fern, damit der Stapel
 * "Kicker + Headline + Beschreibung" nicht als Vorlage zurueckkommt.
 */
export function beschreibungWiederholtWoertlich(headline, description) {
  const h = normalisiere(headline);
  const d = normalisiere(description);
  if (!h || !d) return false;
  return h.includes(d) || d.includes(h);
}

/** Wortstamm fuer den Etikett-Vergleich (deutsche Endungen fallen weg). */
function stamm(wort) {
  return wort.replace(/(?:ungen|ung|aktionen|aktion|en|er|es|e|n|s)$/u, "");
}

/**
 * Wiederholt das Etikett nur das, was die Ueberschrift ohnehin sagt?
 *
 * "Nachfassen" ueber "Es gibt ueberfaellige Nachfassaktionen." ist keine
 * zweite Information, sondern dieselbe in Versalien. Als reiner
 * Teilstring-Vergleich (so stand es im Issue) waere genau dieser Fall
 * durchgerutscht: "nachfassen" steckt nicht in "nachfassaktionen".
 * Deshalb ueber den Wortstamm, mindestens sechs Zeichen.
 */
export function labelWiederholtHeadline(label, headline) {
  const l = normalisiere(label);
  const h = normalisiere(headline);
  if (!l || !h) return false;
  if (h.includes(l)) return true;
  const kopf = h.split(" ").map(stamm);
  return l
    .split(" ")
    .map(stamm)
    .some((w) => w.length >= 6 && kopf.some((k) => k.startsWith(w) || w.startsWith(k)));
}

/** Readiness-Stufen, deren Aussage der Block "Offen" bereits traegt. */
export const VOM_BLOCK_GETRAGEN = ["nachfassen"];

/**
 * Sagt die Readiness-Karte nur noch einmal, was der Block schon zeigt?
 *
 * Nutzerhinweis vom 07.09.2026: der Block "Offen" listet die faelligen
 * Nachfassungen mit Firma und Datum, und direkt darunter stand "Es gibt
 * ueberfaellige Nachfassaktionen." Dieselbe Aussage, nur unschaerfer.
 *
 * #976 verlangte, dass die Karte keine ZAEHLUNGEN aus dem Block
 * wiederholt. Das war zu eng gelesen: eine Wiederholung ohne Zahl ist
 * immer noch eine Wiederholung. Wo der Block die Sache konkret zeigt,
 * hat die Karte nichts hinzuzufuegen.
 *
 * Nur wenn der Block LEER ist, traegt die Karte die Aussage — dann ist
 * sie die einzige Stelle, an der sie steht.
 */
export function readinessWirdVomBlockGetragen(stage, blockAnzahl) {
  if (!Number(blockAnzahl)) return false;
  return VOM_BLOCK_GETRAGEN.includes(String(stage || ""));
}

/** Der leere Zustand des Blocks "Offen": eine Zeile, kein Rahmen. (#984) */
export const NICHTS_OFFEN = "Nichts offen";
