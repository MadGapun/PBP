// #1015 AK 4: die Durchschnittskennzahl muss ausweisen, wie viele der
// zugrunde liegenden Werte GESCHAETZT sind. Framework-frei, laeuft mit
// dem blanken Node der CI-Runner:
//   node frontend/src/lib/gehaltsKennzahl.test.mjs
//
// Gemeldeter Anlass: eine Kennzahl von 92.375 EUR ueber acht Stellen, in
// die zwei geschaetzte Praktikumsgehaelter von 80.000 bis 120.000 EUR
// eingeflossen sind. "Auf Basis von 8 Stellen" verschwieg, dass sieben
// davon geraten waren.

import assert from "node:assert/strict";

import {
  buildAnnualSalaryMetrics,
  grundlagenText,
} from "./gehaltsKennzahl.js";

const echt = (min, max) => ({
  salary_min: min, salary_max: max,
  salary_type: "jaehrlich", salary_estimated: 0,
});
const geschaetzt = (min, max) => ({
  salary_min: min, salary_max: max,
  salary_type: "jaehrlich", salary_estimated: 1,
});

// --- Der Schaetzanteil wird gezaehlt, nicht nur als ja/nein gemeldet ---

{
  const m = buildAnnualSalaryMetrics([
    echt(60000, 80000), geschaetzt(81000, 118800), geschaetzt(50000, 70000),
  ]);
  assert.equal(m.annualBasisCount, 3);
  assert.equal(m.estimatedBasisCount, 2);
  assert.equal(m.allEstimated, false,
    "Eine echte Angabe genuegt, damit nicht alles als geschaetzt gilt.");
  assert.match(grundlagenText(m), /davon 2 gesch/);
}

{
  const m = buildAnnualSalaryMetrics([echt(60000, 80000), echt(70000, 90000)]);
  assert.equal(m.estimatedBasisCount, 0);
  assert.match(grundlagenText(m), /alle belegt/);
}

{
  const m = buildAnnualSalaryMetrics([geschaetzt(81000, 118800)]);
  assert.equal(m.allEstimated, true);
  assert.match(grundlagenText(m), /alle gesch/);
  assert.match(grundlagenText(m), /wenig Datenbasis/,
    "Unter drei Stellen gehoert der Vorbehalt dazu.");
}

{
  assert.equal(grundlagenText(buildAnnualSalaryMetrics([])),
    "Noch keine Gehaltsdaten");
  assert.equal(grundlagenText(null), "Noch keine Gehaltsdaten");
}

// --- Die Regeln der beiden Alt-Fassungen bleiben unveraendert ---

{
  // beta.26: ein Tagessatz mit faelschlich salary_type=jaehrlich faellt
  // aus der Jahresrechnung, zaehlt aber weiter als Stelle mit Gehalt.
  const m = buildAnnualSalaryMetrics([
    { salary_min: 800, salary_max: 900, salary_type: "jaehrlich",
      salary_estimated: 0 },
    echt(60000, 80000),
  ]);
  assert.equal(m.annualBasisCount, 1);
  assert.equal(m.jobsWithSalary, 2);
}

{
  // v1.6.2: geschaetzte Zeilen werden NICHT verworfen, sobald eine echte
  // existiert — sonst schrumpft die Bandbreite auf einen Datenpunkt.
  const m = buildAnnualSalaryMetrics([
    echt(60000, 60000), geschaetzt(40000, 40000), geschaetzt(100000, 100000),
  ]);
  assert.equal(m.annualBasisCount, 3);
  assert.equal(m.bandMin, 40000);
  assert.equal(m.bandMax, 100000);
}

{
  // Nur ein Wert vorhanden: min und max ziehen gleich.
  const m = buildAnnualSalaryMetrics([
    { salary_min: null, salary_max: 70000, salary_type: "jaehrlich",
      salary_estimated: 0 },
  ]);
  assert.equal(m.averageMin, 70000);
  assert.equal(m.averageMax, 70000);
}

console.log("gehaltsKennzahl.test.mjs: alle Faelle gruen");
