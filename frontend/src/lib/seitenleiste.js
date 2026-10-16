// Die Seitenleiste in schmalen Fenstern (#1170 U15).
//
// Befund der Bedienungsprüfung: das Dashboard neben Claude Desktop (halbe Bildschirmbreite, rund 680 px) behielt die
// 240 px breite Seitenleiste, der Inhalt bekam etwa 380 px; bei 420 px blieb nur ein Streifen. Unter 900 px ist die
// Leiste jetzt ohne eigene Wahl eingeklappt.
//
// Die Wahl des Menschen wird je Breitenklasse gemerkt: wer die Leiste im breiten Fenster einklappt, will sie im
// schmalen nicht ebenso; wer sie im schmalen Fenster ausklappt, behält das für schmale Fenster. Ohne gemerkte Wahl
// gilt: breit ausgeklappt (wie bisher), schmal eingeklappt.

export const SCHMAL_BIS_PX = 900;
export const SCHLUESSEL_BREIT = "pbp-sidebar-collapsed";
export const SCHLUESSEL_SCHMAL = "pbp-sidebar-collapsed-schmal";

/** Ist das Fenster schmaler als `SCHMAL_BIS_PX`? Ohne brauchbare Breite (kein Fenster, 0) gilt es als breit. */
export function istSchmal(breite) {
  const b = Number(breite);
  return Number.isFinite(b) && b > 0 && b < SCHMAL_BIS_PX;
}

/** Aus dem gemerkten Text: "1" eingeklappt, "0" ausgeklappt, alles andere keine Wahl (null). */
export function wahlAusText(text) {
  if (text === "1") return true;
  if (text === "0") return false;
  return null;
}

/**
 * Ist die Seitenleiste eingeklappt? `wahlBreit` und `wahlSchmal` sind die gemerkten Entscheidungen (true, false oder null =
 * keine). Im breiten Fenster zählt nur eine ausdrückliche Wahl „eingeklappt“; im schmalen ist „eingeklappt“ die Vorgabe.
 */
export function eingeklappt(schmal, wahlBreit, wahlSchmal) {
  if (schmal) return wahlSchmal === null || wahlSchmal === undefined ? true : Boolean(wahlSchmal);
  return Boolean(wahlBreit);
}
