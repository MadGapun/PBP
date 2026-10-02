// node frontend/src/lib/modellDownload.test.mjs — #1154
import assert from "node:assert/strict";
import {
  ABFRAGE_MS,
  FEHLVERSUCHE_BIS_AUFGABE,
  anzeigeText,
  istEnde,
  prozent,
  verfolgen,
} from "./modellDownload.js";

// Die Abfrage ist weder eine Dauerbelastung für den Server noch so selten, dass die Anzeige stockt.
assert.ok(ABFRAGE_MS >= 500 && ABFRAGE_MS <= 5000, "Abfrageabstand " + ABFRAGE_MS);

// Ende: gelungen, fehlgeschlagen oder abgebrochen — alles andere läuft noch.
assert.equal(istEnde(null), false);
assert.equal(istEnde({ status: "running" }), false);
assert.equal(istEnde({ status: "pending" }), false);
for (const s of ["fertig", "fehler", "abgebrochen"]) assert.equal(istEnde({ status: s }), true, s);

// Die Prozentzahl bleibt zwischen 0 und 100, auch bei Unsinn.
assert.equal(prozent(null), 0);
assert.equal(prozent({}), 0);
assert.equal(prozent({ progress: "abc" }), 0);
assert.equal(prozent({ progress: -5 }), 0);
assert.equal(prozent({ progress: 250 }), 100);
assert.equal(prozent({ progress: 42.6 }), 43);

// Der Satz: vorher, unterwegs, fertig, Fehler, abgebrochen.
assert.match(anzeigeText(null, "qwen:7b"), /Starte den Download von qwen:7b/);
assert.equal(anzeigeText({ status: "running", message: "Lade 1.0 von 4.0 GB (25 %)" }, "m"), "Lade 1.0 von 4.0 GB (25 %)");
assert.equal(anzeigeText({ status: "running", message: "" }, "m"), "Lade ...");
assert.equal(anzeigeText({ status: "fertig" }, "qwen:7b"), "qwen:7b ist installiert.");
assert.match(anzeigeText({ status: "fehler", error: "Platte voll" }, "m"), /Download fehlgeschlagen: Platte voll/);
assert.match(anzeigeText({ status: "fehler", message: "nur Meldung" }, "m"), /nur Meldung/);
assert.match(anzeigeText({ status: "fehler" }, "m"), /unbekannter Fehler/);
assert.match(anzeigeText({ status: "abgebrochen" }, "m"), /bereits geladene Teile bleiben erhalten/);

// Eine Pause, die nach 50 Aufrufen scheitert: ein Fehler in der Schleife wird so zum
// fehlgeschlagenen Test statt zu einem, der ewig läuft.
function begrenzt(aufzeichnen = () => {}) {
  let n = 0;
  return async (ms) => {
    n += 1;
    if (n > 50) throw new Error("Endlosschleife in verfolgen()");
    aufzeichnen(ms);
  };
}

// Verfolgen: jeder Stand geht an die Seite, am Ende kommt der letzte zurück.
{
  const staende = [
    { status: "running", progress: 10 },
    { status: "running", progress: 60 },
    { status: "fertig", progress: 100 },
  ];
  const gesehen = [];
  const pausen = [];
  const ende = await verfolgen(async () => staende.shift(), "j1", {
    beiStand: (j) => gesehen.push(j.progress),
    warten: begrenzt((ms) => pausen.push(ms)),
  });
  assert.equal(ende.status, "fertig");
  assert.deepEqual(gesehen, [10, 60, 100]);
  assert.deepEqual(pausen, [ABFRAGE_MS, ABFRAGE_MS], "zwischen den Abfragen, nicht nach der letzten");
}

// Ein Fehlschlag der Abfrage allein bricht nichts ab ...
{
  let n = 0;
  const ende = await verfolgen(async () => {
    n += 1;
    if (n === 1) throw new Error("kurz weg");
    return { status: "fertig", progress: 100 };
  }, "j2", { warten: begrenzt() });
  assert.equal(ende.status, "fertig");
}

// ... aber der Zähler beginnt nach einer Antwort wieder bei null.
{
  let n = 0;
  const ende = await verfolgen(async () => {
    n += 1;
    if (n % 2 === 1 && n < 20) throw new Error("wechselnd");
    return n < 20 ? { status: "running", progress: n } : { status: "fertig", progress: 100 };
  }, "j3", { warten: begrenzt() });
  assert.equal(ende.status, "fertig", "abwechselnd Fehler und Antwort darf nicht aufgeben");
}

// Antwortet der Server mehrmals hintereinander nicht, gibt die Anzeige auf — mit ehrlichem Satz.
{
  let n = 0;
  const ende = await verfolgen(async () => { n += 1; throw new Error("weg"); }, "j4", { warten: begrenzt() });
  assert.equal(n, FEHLVERSUCHE_BIS_AUFGABE);
  assert.equal(ende.status, "fehler");
  assert.match(ende.error, /läuft in Ollama vielleicht weiter/);
}

// Wird die Seite verlassen, endet die Schleife ohne Ergebnis und fragt nicht weiter.
{
  let n = 0;
  let aus = false;
  const ende = await verfolgen(async () => { n += 1; aus = true; return { status: "running", progress: 1 }; }, "j5", {
    warten: begrenzt(),
    abgebrochen: () => aus,
  });
  assert.equal(ende, null);
  assert.equal(n, 1);
}

console.log("modellDownload: ok");
