/**
 * Die beiden Daumen an einer Stelle (#1052, v1.7.117)
 *
 * Der Fachwert sagt etwas ueber die Anzeige, der Rahmen ueber die
 * Lebensumstaende. Beide kommen fertig vom Server
 * (`services/indikatoren.py`) — hier steht NUR, wie sie AUSSEHEN.
 *
 * **Es wird nichts gerechnet.** Richtung und Farbe entstehen aus der
 * Bewerbungshistorie und aus den Rahmen-Kriterien; eine zweite Fassung
 * dieser Regeln im Browser waere #963 zum x-ten Mal — zuletzt in genau
 * dieser Liste (#1030: zehn Filter in Python UND in JavaScript).
 *
 * **Zwei Kanaele, nicht einer.** Die RICHTUNG (hoch/mittel/runter) kommt
 * aus den Angaben, die FARBE (belegt/grau) sagt, wie gut diese Angaben
 * belegt sind. Ein grauer Daumen nach unten heisst: sieht schlecht aus,
 * aber ungeprueft. Sie in ein Symbol zusammenzuziehen haette "ungeprueft"
 * wieder wie "passt nicht" aussehen lassen — das ist #989, und genau
 * deshalb gibt es diese Trennung.
 *
 * **Keine Summe.** Fachwert und Rahmen werden nirgends addiert; dass sie
 * unter EINEM Namen "Score" zusammengerechnet wurden, war der Anlass des
 * Issues (#1045 AK 4).
 */

export const HOCH = "hoch";
export const MITTEL = "mittel";
export const RUNTER = "runter";
export const BELEGT = "belegt";
export const GRAU = "grau";

export const FACH = "fach";
export const RAHMEN = "rahmen";

/** Wofuer der Daumen steht — je Art eine eigene Frage. */
export const UEBERSCHRIFT = {
  [FACH]: "Fachlich",
  [RAHMEN]: "Rahmen",
};

const RICHTUNG_TEXT = {
  [FACH]: {
    [HOCH]: "passt fachlich gut",
    [MITTEL]: "fachlich im Mittelfeld",
    [RUNTER]: "fachlich schwach",
  },
  [RAHMEN]: {
    [HOCH]: "Rahmen passt",
    [MITTEL]: "Rahmen mit Abstrichen",
    [RUNTER]: "Rahmen passt nicht",
  },
};

/**
 * Der Ton des Abzeichens.
 *
 * Grau schlaegt die Richtung: eine ungeprueste Angabe darf nicht
 * aussehen wie eine geprueste.
 *
 * Die Namen sind die TOENE von `Badge`, nicht die Farben dahinter. Der
 * Gefahren-Ton dieses Projekts heisst `danger` (und faerbt coral);
 * `rose`, `red` oder `coral` erzeugen weder eine Regel noch einen
 * Fehler (#964, #1022) — beim Schreiben dieses Moduls stand hier
 * zuerst `coral`, und genau das haette still nichts gefaerbt.
 */
export function ton(marke) {
  if (!marke) return "neutral";
  if (marke.farbe === GRAU) return "neutral";
  if (marke.richtung === HOCH) return "success";
  if (marke.richtung === RUNTER) return "danger";
  return "amber";
}

/** Das Symbol als NAME — die Komponente waehlt das Icon. */
export function symbol(marke) {
  if (marke?.richtung === HOCH) return "hoch";
  if (marke?.richtung === RUNTER) return "runter";
  return "mittel";
}

/**
 * Die Beschriftung am Abzeichen.
 *
 * Ohne Grundlage steht "ungeprüft" da und nicht etwa nichts: eine
 * fehlende Auskunft, die gar nicht erscheint, ist von einer negativen
 * nicht zu unterscheiden (#989).
 */
export function etikett(marke, art) {
  if (!marke) return "";
  const texte = RICHTUNG_TEXT[art] || RICHTUNG_TEXT[FACH];
  const text = texte[marke.richtung] || texte[MITTEL];
  return marke.farbe === GRAU ? `${text} (ungeprüft)` : text;
}

/**
 * Der Text beim Ueberfahren — die BEGRUENDUNG, die der Server mitgibt.
 *
 * Sie nennt die Zahlen, aus denen die Richtung entstanden ist (die
 * eigene Bewerbungsverteilung, die Entfernungsgrenze, das Minimum).
 * Ohne sie waere der Daumen ein Urteil ohne Herkunft.
 */
export function titel(marke, art) {
  if (!marke) return "";
  const kopf = `${UEBERSCHRIFT[art] || ""}: ${etikett(marke, art)}`.trim();
  const grund = String(marke.grund || "").trim();
  return grund ? `${kopf} — ${grund}` : kopf;
}

/**
 * Steht der Fachwert ohne Grundlage da?
 *
 * Dann sagt der Daumen nichts ueber die Stelle, sondern ueber den
 * Bestand: unter zwanzig Bewerbungen traegt die Verteilung keine
 * Schwelle. Der Hinweis gehoert an den Daumen, nicht in die Zahl.
 */
export function ohneGrundlage(marke) {
  return Boolean(marke) && marke.farbe === GRAU && marke.richtung === MITTEL;
}

/**
 * Das erreichbare Fachmaximum als DETAIL — nie als Prozentsatz.
 *
 * Der Nutzer hat das Prozent-Kriterium am 16.09.2026 zurueckgezogen: es
 * gibt weder eine Ober- noch eine Untergrenze, und je nach gepflegten
 * PLUS- und MINUS-Begriffen kann die beste Stelle sogar im Minus
 * liegen. Ein Anteil haette beide Grenzen behauptet.
 */
export function maximumText(job) {
  const max = Number(job?.fach_maximum || 0);
  if (!max) return "";
  return `fachlich erreichbar: ${Math.round(max * 10) / 10}`;
}
