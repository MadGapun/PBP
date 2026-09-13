// #1032: Fund- und Veroeffentlichungsdatum einer Stelle — EINE Beschriftung
// fuer Karte und Detail-Dialog. Zwei Stellen, die dasselbe Datum verschieden
// formulieren, waeren der naechste Bericht.
//
// Zwei Regeln, beide aus dem Issue:
// - Fehlt ein Datum, entfaellt der Teil GANZ. `formatDate` aus utils.js
//   liefert fuer leer "Keine Angabe" — das waere ein Ersatztext an einer
//   Stelle, an der nichts stehen soll (AK 5).
// - Das Veroeffentlichungsdatum ist ein reines Datum ("2026-09-01", nur die
//   Bundesagentur liefert es). `new Date("2026-09-01")` liest das als
//   Mitternacht UTC; westlich von UTC wird daraus der Vortag. Deshalb wird
//   ein reines Datum als ORTSDATUM gebaut.

const DATUM = new Intl.DateTimeFormat("de-DE", {
  day: "2-digit", month: "2-digit", year: "numeric",
});
const DATUM_ZEIT = new Intl.DateTimeFormat("de-DE", {
  day: "2-digit", month: "2-digit", year: "numeric",
  hour: "2-digit", minute: "2-digit",
});

const NUR_DATUM = /^(\d{4})-(\d{2})-(\d{2})$/;

export function alsDatum(wert) {
  const text = String(wert ?? "").trim();
  if (!text) return null;
  const nurDatum = NUR_DATUM.exec(text);
  const datum = nurDatum
    ? new Date(Number(nurDatum[1]), Number(nurDatum[2]) - 1, Number(nurDatum[3]))
    : new Date(text);
  return Number.isNaN(datum.getTime()) ? null : datum;
}

export function stellenDaten(job) {
  const gefunden = alsDatum(job?.found_at);
  const veroeffentlicht = alsDatum(job?.veroeffentlicht_am);
  const teile = [];
  if (gefunden) teile.push(`Gefunden: ${DATUM_ZEIT.format(gefunden)}`);
  if (veroeffentlicht) teile.push(`Veröffentlicht: ${DATUM.format(veroeffentlicht)}`);
  return {
    gefunden: gefunden ? DATUM_ZEIT.format(gefunden) : "",
    veroeffentlicht: veroeffentlicht ? DATUM.format(veroeffentlicht) : "",
    text: teile.join(" · "),
  };
}
