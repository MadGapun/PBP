// node frontend/src/lib/stellenFilter.test.mjs — #1158
import assert from "node:assert/strict";
import {
  FILTER_SERVERNAMEN,
  SPEICHER_SCHLUESSEL,
  filterAusSpeicher,
  filterAusVoreinstellung,
  filterFuerSpeicher,
  filterFuerVoreinstellung,
  mehrereFilter,
  minScoreGesetzt,
  minScoreParameter,
  mitZahlen,
  voreinstellungGilt,
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

// ── #1158 Punkt 5: die ausdrücklich gesetzte Voreinstellung ─────────────────────────────────────────────────────────
const VOR_STANDARD = {
  query: "", source: "", minScore: "", remote: "", salaryOnly: false, sort: "score_desc", view: "active",
  employmentType: "", arbeitsumfang: "", hideApplied: true, missingDescriptionOnly: false, pruefstand: "",
  rahmenAusblenden: false, schwelleAusblenden: false,
};

// Was zum Server geht: alle Filter bis auf Suchtext und Ansicht, als Objekt (der Server prüft Schlüssel und Typen streng).
const vorEin = filterFuerVoreinstellung({ ...VOR_STANDARD, query: "Planer", view: "dismissed", minScore: "-50", hideApplied: false });
assert.equal(typeof vorEin, "object");
assert.equal("query" in vorEin, false, "der Suchtext wird nie festgehalten");
assert.equal("view" in vorEin, false, "die Ansicht auch nicht");
assert.equal(vorEin.minScore, "-50");
assert.equal(vorEin.hideApplied, false);

// Zurück in ein Filterobjekt: nur bekannte Felder und Typen; Suchtext und Ansicht bleiben, wie sie jetzt sind.
const jetzt = { ...VOR_STANDARD, query: "Elektro", view: "dismissed" };
const angewandt = filterAusVoreinstellung({ minScore: "100", hideApplied: false, rahmenAusblenden: true }, VOR_STANDARD, jetzt);
assert.equal(angewandt.minScore, "100");
assert.equal(angewandt.hideApplied, false);
assert.equal(angewandt.rahmenAusblenden, true);
assert.equal(angewandt.query, "Elektro");
assert.equal(angewandt.view, "dismissed");
assert.equal(angewandt.sort, "score_desc", "was die Voreinstellung nicht nennt, bleibt die Vorgabe");
// falsche Typen und fremde Felder (etwa aus einer anderen Fassung) fallen auf die Vorgabe zurück
const kaputt = filterAusVoreinstellung({ minScore: 5, hideApplied: "ja", fremd: 1, query: "x", view: "dismissed" }, VOR_STANDARD, jetzt);
assert.equal(kaputt.minScore, "");
assert.equal(kaputt.hideApplied, true);
assert.equal("fremd" in kaputt, false);
assert.equal(kaputt.query, "Elektro", "der Suchtext kommt nie aus der Voreinstellung");
assert.equal(kaputt.view, "dismissed", "die Ansicht auch nicht");
assert.deepEqual(filterAusVoreinstellung(null, VOR_STANDARD, jetzt), { ...VOR_STANDARD, query: "Elektro", view: "dismissed" });

// Gilt gerade genau die Voreinstellung? Ohne Voreinstellung: nein.
const v = { hideApplied: true, minScore: "-5" };
assert.equal(voreinstellungGilt({ ...VOR_STANDARD, minScore: "-5" }, v, VOR_STANDARD), true);
assert.equal(voreinstellungGilt({ ...VOR_STANDARD, minScore: "-5", query: "egal", view: "dismissed" }, v, VOR_STANDARD), true,
  "Suchtext und Ansicht gehören nicht zur Voreinstellung");
assert.equal(voreinstellungGilt({ ...VOR_STANDARD, minScore: "0" }, v, VOR_STANDARD), false);
assert.equal(voreinstellungGilt({ ...VOR_STANDARD, minScore: "-5", rahmenAusblenden: true }, v, VOR_STANDARD), false);
assert.equal(voreinstellungGilt(VOR_STANDARD, null, VOR_STANDARD), false);
assert.equal(voreinstellungGilt(VOR_STANDARD, undefined, VOR_STANDARD), false);
// ein Feld, das die Voreinstellung nicht nennt, gilt mit seiner Vorgabe: die Voreinstellung „Beworbene aus“ trifft
// keinen Zustand, in dem noch etwas anderes verändert ist
assert.equal(voreinstellungGilt({ ...VOR_STANDARD, hideApplied: false }, { hideApplied: false }, VOR_STANDARD), true);
assert.equal(voreinstellungGilt({ ...VOR_STANDARD, hideApplied: false, remote: "remote" }, { hideApplied: false }, VOR_STANDARD), false);

console.log("stellenFilter: ok");
