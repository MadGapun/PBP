// node frontend/src/lib/promptAufloesung.test.mjs
import assert from "node:assert/strict";
import { fehlerText, werkzeugAufruf, workflowPfad, zerlegePrompt } from "./promptAufloesung.js";

// Ein Schraegstrich-Text ist ein Workflow, alles andere ist Klartext.
assert.deepEqual(zerlegePrompt("/dokumente_verarbeiten"), {
  istWorkflow: true, name: "dokumente_verarbeiten", argumente: {}, text: "/dokumente_verarbeiten",
});
assert.equal(zerlegePrompt("Bewerte die Stelle ...").istWorkflow, false);
assert.equal(zerlegePrompt("").istWorkflow, false);
assert.equal(zerlegePrompt("/").istWorkflow, false);

// Argumente gehen nicht mehr verloren — der Kalender-Knopf (#457) gab
// Stelle und Firma mit, und beim Aufloesen fielen sie weg.
const termin = zerlegePrompt('/interview_vorbereitung stelle="PLM Berater (m/w/d)" firma="Musterfirma GmbH"');
assert.equal(termin.name, "interview_vorbereitung");
assert.deepEqual(termin.argumente, { stelle: "PLM Berater (m/w/d)", firma: "Musterfirma GmbH" });
assert.equal(
  workflowPfad(termin),
  "/api/workflow-prompt/interview_vorbereitung?stelle=PLM%20Berater%20(m%2Fw%2Fd)&firma=Musterfirma%20GmbH",
);
assert.equal(workflowPfad(zerlegePrompt("/faq")), "/api/workflow-prompt/faq");
// Ein leeres Argument ist keine Angabe.
assert.equal(workflowPfad(zerlegePrompt('/interview_vorbereitung stelle=""')),
  "/api/workflow-prompt/interview_vorbereitung");
// Sonderzeichen im Namen zerlegen den Pfad nicht.
assert.equal(workflowPfad(zerlegePrompt("/a/b")), "/api/workflow-prompt/a%2Fb");

// Ein Werkzeug ist kein Workflow: Satz statt Schraegstrich-Befehl.
const satz = werkzeugAufruf("firmen_recherche", { firma: 'Muster "Nord" GmbH', bewerbung_id: "" });
assert.ok(!satz.startsWith("/"), "ein Werkzeugaufruf beginnt nie mit /");
assert.ok(satz.includes('firmen_recherche(firma="Muster \'Nord\' GmbH")'), satz);
assert.ok(!satz.includes("bewerbung_id"), "leere Angabe faellt weg");
assert.ok(werkzeugAufruf("firmen_recherche", { firma: "X", bewerbung_id: "ab12" }, "Speichere das Ergebnis.")
  .endsWith("Speichere das Ergebnis."));
assert.equal(zerlegePrompt(satz).istWorkflow, false);

// Die Fehlermeldung sagt, dass NICHTS kopiert wurde — und nennt den Namen.
assert.ok(fehlerText("dokumente_verarbeiten").includes("NICHTS kopiert"));
assert.ok(fehlerText("dokumente_verarbeiten").includes("dokumente_verarbeiten"));

console.log("promptAufloesung: ok");
