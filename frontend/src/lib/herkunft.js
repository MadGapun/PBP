// Woher die Angaben einer Stelle kommen (#954).
//
// Der Server liefert je Feld `guete` (belegt / geschaetzt / unbekannt),
// `methode` und einen Satz. Gezeigt werden nur die drei Alltagswoerter,
// und nur, was NICHT belegt ist — belegt ist der Normalfall (P3 aus #953).
// Gerechnet wird hier nichts; die Regeln stehen in services/wahrheit.py.

export const HERKUNFT_NAMEN = {
  beschreibung: "Anzeigentext",
  anforderungen: "Anforderungen",
  entfernung: "Entfernung",
  gehalt: "Gehalt",
  veroeffentlicht: "Veröffentlicht",
  score: "Punkte",
};

export const HERKUNFT_WORT = {
  belegt: "belegt",
  geschaetzt: "geschätzt",
  unbekannt: "unbekannt",
};

export function nichtBelegt(job) {
  const felder = job?.herkunft;
  if (!felder || typeof felder !== "object") return [];
  return Object.keys(HERKUNFT_NAMEN)
    .filter((feld) => felder[feld] && felder[feld].guete !== "belegt")
    .map((feld) => ({
      feld,
      name: HERKUNFT_NAMEN[feld],
      wort: HERKUNFT_WORT[felder[feld].guete] || felder[feld].guete,
      text: felder[feld].text || "",
    }));
}
