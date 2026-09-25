// #1050 (G51): der Weg zur Detailbewertung — auf der Karte, nicht nur im Chat.
//
// Seit #1003 sagt PBP ohne gelesene Analyse ehrlich NICHT_BEURTEILBAR, und
// #1007 hat den Speicherweg gebaut (`stelle_analyse_speichern`). Auf der
// Karte gab es keinen Knopf dafuer: das Feld, das die eigentliche Aussage
// traegt, blieb leer, waehrend der Score, der ausdruecklich KEINE Aussage
// ueber Passung ist, prominent dastand.
//
// Ein Modul fuer Karte UND Fit-Dialog. Der Prompt stand bis hierher als
// Literal im Dialog — eine zweite Fassung auf der Karte waere #963 im
// Frontend gewesen, und die alte verlangte das Speichern nicht einmal.

// Dieselben vier Kategorien wie `services/passung.py::KATEGORIEN`. Ein
// Python-Test haelt beide Listen gegeneinander.
export const URTEILE = ["EMPFOHLEN", "BEDINGT", "NICHT_EMPFOHLEN", "NICHT_BEURTEILBAR"];

function titelVon(job) {
  return String(job?.title || job?.titel || "").trim();
}

export function detailbewertungPrompt(job) {
  const hash = String(job?.hash || "");
  const titel = titelVon(job);
  const firma = String(job?.company || "").trim();
  const bezeichnung = firma ? `"${titel}" bei ${firma}` : `"${titel}"`;
  const zeilen = [
    `Bewerte die Stelle ${bezeichnung} (Hash: ${hash}) detailliert gegen mein Profil.`,
    "Rufe die Stellenbeschreibung ab (fit_analyse), lies sie vollständig und "
      + "vergleiche sie mit meinem Profil: Stärken, Lücken, Risiken, und ob sich "
      + "eine Bewerbung lohnt.",
    `Speichere das Ergebnis danach mit stelle_analyse_speichern(job_hash="${hash}", `
      + `urteil=..., begründung=...) — urteil ist eines von ${URTEILE.join(", ")}. `
      + "Antworte nicht nur im Chat: ohne diesen Aufruf bleibt die Stelle als "
      + "nicht beurteilt stehen.",
  ];
  const vorhanden = job?.analyse?.urteil;
  if (vorhanden) {
    const am = job.analyse.am ? `, vom ${String(job.analyse.am).slice(0, 10)}` : "";
    zeilen.push(
      `Es liegt bereits ein Befund vor (${vorhanden}${am}). Bewerte neu und `
        + "überschreibe ihn nur, wenn du die Anzeige erneut gelesen hast.",
    );
  }
  return zeilen.join("\n");
}

// AK 3: liegt ein Befund vor, sagt der Knopf das — und bietet Neubewerten an.
export function detailbewertungKnopf(job) {
  const vorhanden = job?.analyse?.urteil;
  if (!vorhanden) {
    return {
      text: "Detailbewertung",
      titel: "Prompt für Claude kopieren: Stelle gegen dein Profil lesen und das Urteil speichern",
      befund: "",
    };
  }
  return {
    text: "Neu bewerten",
    titel: `Befund liegt vor (${vorhanden}) — Prompt zum Neubewerten kopieren`,
    befund: vorhanden,
  };
}
