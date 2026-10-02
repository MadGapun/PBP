// node frontend/src/lib/nurErfolge.test.mjs — #1144
import assert from "node:assert/strict";
import { nurErfolgeMerken } from "./nurErfolge.js";

// Ein Erfolg wird gemerkt: die zweite Frage braucht keinen Aufruf mehr.
{
  let aufrufe = 0;
  const k = nurErfolgeMerken(async () => { aufrufe += 1; return ["a", "b"]; }, []);
  assert.deepEqual(k.stand(), []);          // vor dem ersten Laden: der Ersatz
  assert.equal(k.gemerkt(), false);
  assert.deepEqual(await k.holen(), ["a", "b"]);
  assert.deepEqual(await k.holen(), ["a", "b"]);
  assert.equal(aufrufe, 1);
  assert.equal(k.gemerkt(), true);
  assert.deepEqual(k.stand(), ["a", "b"]);
}

// Ein Fehlschlag wird NICHT gemerkt: die nächste Frage versucht es neu und
// bekommt dann die echten Daten (vorher: "keine Kategorien" für die ganze Sitzung).
{
  let aufrufe = 0;
  let netzDa = false;
  const k = nurErfolgeMerken(async () => {
    aufrufe += 1;
    if (!netzDa) throw new Error("keine Verbindung");
    return ["x"];
  }, []);
  assert.deepEqual(await k.holen(), []);    // Fehlschlag: der Ersatz, ohne Wurf
  assert.equal(k.gemerkt(), false);
  assert.deepEqual(k.stand(), []);
  netzDa = true;
  assert.deepEqual(await k.holen(), ["x"]);
  assert.equal(aufrufe, 2);
  assert.equal(k.gemerkt(), true);
}

// Auch ein Fehlschlag, der synchron wirft, wird abgefangen.
{
  const k = nurErfolgeMerken(() => { throw new Error("sofort"); }, "leer");
  assert.equal(await k.holen(), "leer");
  assert.equal(k.gemerkt(), false);
}

// Wer gleichzeitig fragt, teilt sich eine Anfrage (jede Rollen-Marke fragt).
{
  let aufrufe = 0;
  const k = nurErfolgeMerken(async () => {
    aufrufe += 1;
    await new Promise((r) => setTimeout(r, 10));
    return [1];
  }, []);
  const alle = await Promise.all([k.holen(), k.holen(), k.holen(), k.holen()]);
  assert.equal(aufrufe, 1);
  for (const a of alle) assert.deepEqual(a, [1]);
}

// Nach einem Fehlschlag fragen gleichzeitige Aufrufer wieder gemeinsam neu.
{
  let aufrufe = 0;
  let netzDa = false;
  const k = nurErfolgeMerken(async () => {
    aufrufe += 1;
    await new Promise((r) => setTimeout(r, 5));
    if (!netzDa) throw new Error("aus");
    return ["ok"];
  }, []);
  await Promise.all([k.holen(), k.holen()]);
  assert.equal(aufrufe, 1);
  netzDa = true;
  const zweite = await Promise.all([k.holen(), k.holen()]);
  assert.equal(aufrufe, 2);
  for (const z of zweite) assert.deepEqual(z, ["ok"]);
}

// verwerfen(): der nächste Aufruf lädt neu.
{
  let stand = 1;
  let aufrufe = 0;
  const k = nurErfolgeMerken(async () => { aufrufe += 1; return stand; }, 0);
  assert.equal(await k.holen(), 1);
  stand = 2;
  assert.equal(await k.holen(), 1);         // gemerkt
  k.verwerfen();
  assert.equal(k.gemerkt(), false);
  assert.equal(await k.holen(), 2);
  assert.equal(aufrufe, 2);
}

// verwerfen() gilt auch für eine Anfrage, die gerade unterwegs ist: ihr
// (alter) Stand wird nicht gemerkt, und der nächste Aufruf fragt neu.
{
  let stand = "alt";
  let aufrufe = 0;
  const k = nurErfolgeMerken(async () => {
    aufrufe += 1;
    const gelesen = stand;
    await new Promise((r) => setTimeout(r, 15));
    return gelesen;
  }, "");
  const unterwegs = k.holen();              // liest "alt"
  await new Promise((r) => setTimeout(r, 1));  // die Anfrage ist wirklich unterwegs
  stand = "neu";
  k.verwerfen();                            // etwas wurde geändert
  assert.equal(await unterwegs, "alt");     // der Aufrufer von vorhin bekommt, was er fragte
  assert.equal(k.gemerkt(), false);         // ... aber der alte Stand wird nicht gemerkt
  assert.equal(await k.holen(), "neu");
  assert.equal(aufrufe, 2);
}

console.log("nurErfolge.test.mjs: ok");
