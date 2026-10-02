// node frontend/src/lib/stellenFilter.test.mjs — #1158
import assert from "node:assert/strict";
import {
  FILTER_SERVERNAMEN,
  SPEICHER_SCHLUESSEL,
  filterAusSpeicher,
  filterFuerSpeicher,
  mehrereFilter,
  minScoreGesetzt,
  minScoreParameter,
  mitZahlen,
} from "./stellenFilter.js";

// Eine Untergrenze gilt, sobald etwas Zahlenartiges drinsteht — auch 0 und negative Werte.
for (const wert of ["0", "-1", "-100", "5", " 7 ", "12.5", 0, -3, 42]) {
  assert.equal(minScoreGesetzt(wert), true, String(wert));
}
for (const wert of ["", "  ", null, undefined, "abc", "-", "1,5x", NaN]) {
  assert.equal(minScoreGesetzt(wert), false, String(wert));
}

// Der Server-Parameter: der Zahlenwert als Text, sonst nichts.
assert.equal(minScoreParameter("0"), "0");
assert.equal(minScoreParameter("-100"), "-100");
assert.equal(minScoreParameter(" 5 "), "5");
assert.equal(minScoreParameter(-3), "-3");
assert.equal(minScoreParameter(""), null);
assert.equal(minScoreParameter(null), null);
assert.equal(minScoreParameter("abc"), null);

// Alle zwölf Filter der Seite haben einen Namen beim Server.
assert.equal(Object.keys(FILTER_SERVERNAMEN).length, 12);

const STANDARD = {
  query: "", source: "", minScore: "", remote: "", salaryOnly: false, sort: "score_desc", view: "active",
  employmentType: "", arbeitsumfang: "", hideApplied: true, missingDescriptionOnly: false, pruefstand: "",
  rahmenAusblenden: false, schwelleAusblenden: false,
};

// Speichern lässt Suchtext und Ansicht weg und behält den Rest.
{
  const text = filterFuerSpeicher({ ...STANDARD, query: "buchhaltung", view: "dismissed", minScore: "-5", remote: "remote" });
  const roh = JSON.parse(text);
  assert.equal("query" in roh, false);
  assert.equal("view" in roh, false);
  assert.equal(roh.minScore, "-5");
  assert.equal(roh.remote, "remote");
}

// Laden: gemerkte Werte kommen zurück, Suchtext und Ansicht nicht.
{
  const gemerkt = filterFuerSpeicher({ ...STANDARD, minScore: "-5", hideApplied: false, rahmenAusblenden: true, sort: "company" });
  const geladen = filterAusSpeicher(gemerkt, STANDARD);
  assert.equal(geladen.minScore, "-5");
  assert.equal(geladen.hideApplied, false);
  assert.equal(geladen.rahmenAusblenden, true);
  assert.equal(geladen.sort, "company");
  assert.equal(geladen.query, "");
  assert.equal(geladen.view, "active");
}

// Ein Suchtext oder eine Ansicht im gemerkten Text wird ignoriert, auch wenn jemand sie hineinschreibt.
{
  const geladen = filterAusSpeicher(JSON.stringify({ query: "gefaehrlich", view: "dismissed" }), STANDARD);
  assert.deepEqual(geladen, STANDARD);
}

// Kaputtes oder Fremdes fällt auf die Vorgabe zurück.
for (const text of ["", "kein json", "null", "[]", "42", '"x"', null, undefined]) {
  assert.deepEqual(filterAusSpeicher(text, STANDARD), STANDARD, String(text));
}

// Ein Wert vom falschen Typ wird einzeln verworfen, die übrigen bleiben.
{
  const geladen = filterAusSpeicher(JSON.stringify({ minScore: 5, hideApplied: "ja", remote: "remote" }), STANDARD);
  assert.equal(geladen.minScore, "", "Zahl statt Text");
  assert.equal(geladen.hideApplied, true, "Text statt Ja/Nein");
  assert.equal(geladen.remote, "remote");
}

// Unbekannte Felder (aus einer älteren oder jüngeren Fassung) kommen nicht ins Objekt.
{
  const geladen = filterAusSpeicher(JSON.stringify({ gibtesnicht: true, minScore: "3" }), STANDARD);
  assert.equal("gibtesnicht" in geladen, false);
  assert.equal(geladen.minScore, "3");
}

assert.equal(typeof SPEICHER_SCHLUESSEL, "string");
assert.ok(SPEICHER_SCHLUESSEL.length > 5);

// Der Streifen: jeder wirksame Filter bekommt seine Zahl, wenn er etwas verbirgt.
{
  const aktiv = [
    { schluessel: "minScore", text: "Punkte ab 0" },
    { schluessel: "hideApplied", text: "beworbene ausgeblendet" },
    { schluessel: "rahmenAusblenden", text: "Rahmen passt nicht ausgeblendet" },
    { schluessel: "remote", text: "Remote remote" },
  ];
  const mit = mitZahlen(aktiv, { min_score: 2, beworbene_ausblenden: 3, rahmen_ausblenden: 0 });
  assert.equal(mit[0].text, "Punkte ab 0 (2)");
  assert.equal(mit[1].text, "beworbene ausgeblendet (3)");
  assert.equal(mit[2].text, "Rahmen passt nicht ausgeblendet", "ohne verborgene Stellen keine Zahl");
  assert.equal(mit[3].text, "Remote remote", "ohne Eintrag vom Server keine Zahl");
  assert.deepEqual(mit.map((f) => f.anzahl), [2, 3, 0, 0]);
  assert.equal(mitZahlen(aktiv, null)[0].text, "Punkte ab 0");
  assert.equal(mitZahlen(aktiv, undefined).length, 4);
  // Das Original bleibt unverändert.
  assert.equal(aktiv[0].text, "Punkte ab 0");
}

// Stellen, die mehrere Filter zugleich verbergen, stehen bei keinem einzelnen: die Differenz wird benannt.
assert.equal(mehrereFilter(5, { min_score: 2, rahmen_ausblenden: 1 }), 2);
assert.equal(mehrereFilter(3, { min_score: 2, rahmen_ausblenden: 1 }), 0);
assert.equal(mehrereFilter(2, { min_score: 2, rahmen_ausblenden: 1 }), 0, "nie negativ");
assert.equal(mehrereFilter(4, {}), 4);
assert.equal(mehrereFilter(4, null), 4);
assert.equal(mehrereFilter(0, { min_score: 2 }), 0);
// Beworbene sind keine offenen Stellen und gehen in diese Rechnung nicht ein.
assert.equal(mehrereFilter(5, { min_score: 2, beworbene_ausblenden: 9 }), 3);

console.log("stellenFilter: ok");
