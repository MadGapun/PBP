/**
 * Der Elwosa-Strom in der Seitenleiste: was ist NEU? - #1256 (F58).
 *
 * Die Seitenleiste holt nur die letzten zehn Nachrichten. Ob eine Nachricht neu ist, darf darum nicht an der ZAHL der Nachrichten haengen:
 * bei voller Liste bleibt sie bei zehn (eine neue schiebt die aelteste hinaus), und nach dem Ausblenden einer Nachricht ruecken AELTERE ins
 * Fenster (die Zahl steigt, ohne dass etwas neu waere). Entscheidend ist die Kennung: `elwosa_messages.id` steigt mit jeder Nachricht
 * (AUTOINCREMENT), und eine ausgeblendete Zeile bleibt in der Tabelle und gibt ihre Nummer nie wieder her. Neu ist, was eine groessere Kennung
 * traegt als die groesste, die der Mensch schon gesehen hat.
 *
 * Kein Framework, damit der Node-Test es prueft (`elwosaStrom.test.mjs`).
 */

/** Die Kennung einer Nachricht als Zahl; 0, wenn sie keine gueltige hat (so eine Zeile zaehlt nie als neu). */
function kennung(nachricht) {
  const n = Number(nachricht?.id);
  return Number.isFinite(n) && n > 0 ? n : 0;
}

/** Die groesste Kennung der Liste; 0 bei leerer Liste. */
export function hoechsteKennung(nachrichten) {
  let hoechste = 0;
  for (const nachricht of nachrichten || []) hoechste = Math.max(hoechste, kennung(nachricht));
  return hoechste;
}

/**
 * Wie viele Nachrichten der Liste sind seit dem letzten Blick dazugekommen?
 * `gesehen`: die groesste Kennung, die schon gesehen wurde; `null`, solange noch nichts geladen war - das erste Laden ist nichts Neues.
 * Rueckgabe: { anzahl, hoechste }. `hoechste` ist die neue groesste gesehene Kennung und sinkt nie: wer die neueste Nachricht ausblendet, macht
 * eine kleinere nicht "neu", und die naechste wirklich neue traegt eine groessere.
 */
export function neueNachrichten(gesehen, nachrichten) {
  const hoechste = hoechsteKennung(nachrichten);
  if (gesehen === null || gesehen === undefined) return { anzahl: 0, hoechste };
  let anzahl = 0;
  for (const nachricht of nachrichten || []) {
    if (kennung(nachricht) > gesehen) anzahl += 1;
  }
  return { anzahl, hoechste: Math.max(gesehen, hoechste) };
}
