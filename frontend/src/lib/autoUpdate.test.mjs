// node frontend/src/lib/autoUpdate.test.mjs
// Auto-Update (#1093): die Stufen, der Hinweis auf dem Dashboard, Fortschritt und Größen.
import assert from "node:assert/strict";
import {
  ANTWORTEN, AUTOMATISCHE_STUFEN, INSTALLER_AUFRAEUMEN, STUFEN, groesseText, laeuft, naechsteFrageMs, prozent,
  NEUSTART_SCHRITTE, fassungsSchluessel, istNeuer, istSchonInstalliert, neustartText, seitenleisteFuehrtZuEinstellungen, seitenleisteText, stufeLabel, zeigeAktuell,
  updateHinweis, claudeFassung, verbindungsAbweichung,
} from "./autoUpdate.js";

// ── Die vier Stufen und die Antworten auf die Rückfrage ───────────────────────────────
assert.deepEqual(STUFEN.map((s) => s.id), ["aus", "hinweis", "auto_meldung", "auto_still"]);
assert.ok(STUFEN.every((s) => s.kurz && s.text.endsWith(".")));
assert.deepEqual(AUTOMATISCHE_STUFEN, ["auto_meldung", "auto_still"]);
assert.deepEqual(ANTWORTEN.map((a) => a.id), ["automatisch", "klick", "nein", "spaeter"]);
assert.deepEqual(INSTALLER_AUFRAEUMEN.map((a) => a.id), ["fragen", "immer", "nie"]);
assert.equal(stufeLabel("auto_still"), "Automatisch, still");
assert.equal(stufeLabel("gibts-nicht"), "Nur Hinweis", "unbekannt gilt als aus");

// ── Fortschritt und Größe ────────────────────────────────────────────────────────────
assert.equal(prozent({ anteil: 0.456 }), 46);
assert.equal(prozent({ anteil: 2 }), 100);
assert.equal(prozent({ anteil: -1 }), 0);
assert.equal(prozent(null), 0);
assert.equal(prozent({ anteil: "x" }), 0);
assert.equal(groesseText(2_500_000), "2,4 MB");
assert.equal(groesseText(150 * 1024 * 1024), "150 MB");
assert.equal(groesseText(3 * 1024 ** 3), "3,0 GB");
assert.equal(groesseText(1000), "< 0,1 MB");
assert.equal(groesseText(0), "0 MB");
assert.equal(groesseText(undefined), "0 MB");

// ── Wann fragt die Oberfläche wieder? ─────────────────────────────────────────────────
assert.equal(naechsteFrageMs({ job: { status: "laeuft" } }), 1500);
assert.equal(naechsteFrageMs({ job: { status: "fehler" } }), 20000);
assert.equal(naechsteFrageMs({ neustart_noetig: true }), 20000);
assert.equal(naechsteFrageMs({}), 60000);
assert.equal(naechsteFrageMs(null), 60000);
assert.equal(laeuft({ job: { status: "laeuft" } }), true);
assert.equal(laeuft({ job: { status: "fertig" } }), false);

// ── Der Hinweis ───────────────────────────────────────────────────────────────────────
const basis = { verfuegbar: true, stufe: "aus", laufend: "1.8.0", aktuell: "1.8.0", neustart_noetig: false,
  neu: null, job: null, rueckgang: null, blockiert: null };
const neu = { version: "1.8.1", status: "neu", auszug: ["Der Stellen-Tab blendet nichts mehr still aus."], frage_faellig: false,
  zurueckgenommen: false };

// Ohne Installer-Layout gibt es keinen Hinweis von hier (dann gilt der alte).
assert.equal(updateHinweis(null), null);
assert.equal(updateHinweis({ ...basis, verfuegbar: false }), null);
assert.equal(updateHinweis(basis), null, "nichts Neues, nichts zu sagen");

// Stufe aus: Hinweis mit Anleitung und Optionen — nie ein Installieren-Knopf.
let h = updateHinweis({ ...basis, neu }, { releaseUrl: "https://github.com/MadGapun/PBP/releases/tag/v1.8.1" });
assert.equal(h.id, "update");
assert.equal(h.dringend, false);
assert.match(h.titel, /Neue Version verfügbar: v1\.8\.1/);
assert.deepEqual(h.aktionen.map((a) => a.art), ["link", "update-optionen"]);
assert.equal(h.aktionen[0].url, "https://github.com/MadGapun/PBP/releases/tag/v1.8.1");
assert.ok(!h.aktionen.some((a) => a.art === "update-installieren"), "in der Stufe aus installiert PBP nichts per Knopf im Hinweis");
// ohne Adresse aus dem Update-Check führt die Anleitung zur Veröffentlichungsseite
assert.match(updateHinweis({ ...basis, neu }).aktionen[0].url, /^https:\/\/github\.com\/MadGapun\/PBP\/releases/);

// Stufe hinweis: Ein-Klick-Update.
h = updateHinweis({ ...basis, stufe: "hinweis", neu });
assert.equal(h.aktionen[0].art, "update-installieren");
assert.equal(h.aktionen[0].label, "Jetzt aktualisieren");
assert.equal(h.aktionen[0].version, "1.8.1");
assert.match(h.text, /Ein Klick installiert sie/);
assert.match(h.text, /nächsten Neustart/);

// Automatische Stufen: PBP macht es selbst; der Knopf bleibt für Ungeduldige.
for (const stufe of ["auto_meldung", "auto_still"]) {
  h = updateHinweis({ ...basis, stufe, neu });
  assert.match(h.titel, /wird automatisch installiert/, stufe);
  assert.equal(h.aktionen[0].art, "update-installieren");
}

// Die Rückfrage kommt zusammen mit der Meldung über die neue Version, hat vier Antworten und ist dringend.
h = updateHinweis({ ...basis, neu: { ...neu, frage_faellig: true } });
assert.equal(h.id, "update-frage");
assert.equal(h.dringend, true);
assert.deepEqual(h.aktionen.map((a) => a.antwort), ["automatisch", "klick", "nein", "spaeter"]);
assert.ok(h.aktionen.every((a) => a.art === "update-antwort" && a.version === "1.8.1"));
assert.match(h.text, /Ohne Antwort bleibt alles beim Alten/);
assert.match(h.text, /Einstellungen › Updates/);
assert.match(h.text, /Der Stellen-Tab blendet nichts mehr still aus\./, "der Grund, warum sich das Update lohnt, steht im Hinweis");

// Ein Update, dessen Dateien noch fehlen: ehrlich sagen, von Hand installieren.
h = updateHinweis({ ...basis, neu: { version: "1.8.1", status: "unvollstaendig", text: "Version 1.8.1 ist erschienen. Das automatische Update dafür ist noch nicht bereit; du kannst sie von Hand installieren." } });
assert.equal(h.aktionen.length, 1);
assert.equal(h.aktionen[0].art, "link");

// Eine zurückgenommene Version wird nicht aufgedrängt.
h = updateHinweis({ ...basis, stufe: "auto_still", neu: { ...neu, zurueckgenommen: true } });
assert.match(h.titel, /bleibst bewusst bei der älteren/);
assert.equal(h.aktionen[0].label, "Trotzdem installieren");

// Ein dauerhafter Fehler bleibt sichtbar, auch nach einem Neustart (er steht in der Datenbank, nicht im Speicher).
h = updateHinweis({ ...basis, stufe: "auto_still", neu, blockiert: { dauerhaft: true, code: "pruefsumme", text: "Die Prüfsumme stimmt nicht." } });
assert.equal(h.ton, "amber");
assert.match(h.text, /Die Prüfsumme stimmt nicht\./);
assert.equal(h.aktionen[0].label, "Erneut versuchen");
// ein vorübergehender Fehler (Netz) ist kein Hinweis: PBP versucht es später von selbst
assert.equal(updateHinweis({ ...basis, stufe: "auto_still", neu, blockiert: { dauerhaft: false } }).id, "update");

// Etwas, das gerade passiert, geht vor dem Rest und ist dringend.
h = updateHinweis({ ...basis, neu, job: { status: "laeuft", version: "1.8.1", anteil: 0.5, text: "Lade pbp-update-1.8.1.zip …" } });
assert.equal(h.id, "update-laeuft");
assert.equal(h.fortschritt, 50);
assert.equal(h.dringend, true);
assert.deepEqual(h.aktionen, []);

h = updateHinweis({ ...basis, neu, job: { status: "fehler", version: "1.8.1", text: "Die Prüfsumme stimmt nicht." } });
assert.equal(h.id, "update-fehler");
assert.equal(h.ton, "amber");
assert.match(h.text, /Die bisherige Version läuft unverändert weiter/);
assert.deepEqual(h.aktionen.map((a) => a.art), ["update-installieren", "link", "update-optionen"]);
// ein alter Fehler einer ANDEREN Version ist keiner für diese
assert.equal(updateHinweis({ ...basis, neu, job: { status: "fehler", version: "1.8.0", text: "x" } }).id, "update");

// Neustart nötig — außer in der stillen Stufe.
h = updateHinweis({ ...basis, aktuell: "1.8.1", neustart_noetig: true, stufe: "auto_meldung" });
assert.equal(h.id, "update-neustart");
assert.match(h.text, /Claude Desktop ganz/);
assert.match(h.text, /schwarze Fenster/, "sagt, was „PBP beenden“ konkret heißt");
assert.match(h.text, /1\. .*2\. .*3\. /, "drei Schritte, nummeriert");
assert.equal(h.dringend, true);
assert.equal(updateHinweis({ ...basis, aktuell: "1.8.1", neustart_noetig: true, stufe: "auto_still" }), null);

// Ein Rückfall geht allem vor.
h = updateHinweis({ ...basis, neu, neustart_noetig: true, aktuell: "1.8.0", job: { status: "laeuft" }, rueckgang: { von: "1.8.1", nach: "1.8.0" } });
assert.equal(h.id, "update-rueckgang");
assert.equal(h.ton, "amber");
assert.match(h.titel, /Version 1\.8\.1 ließ sich nicht starten/);
assert.match(h.text, /läuft wieder mit Version 1\.8\.0/);
assert.deepEqual(h.aktionen.map((a) => a.art), ["update-gesehen", "update-optionen"]);

// ── Seitenleiste ──────────────────────────────────────────────────────────────────────
assert.equal(seitenleisteText({ verfuegbar: true, neustart_noetig: true, laufend: "1.8.0", aktuell: "1.8.1" }), "Neustart nötig für v1.8.1");
assert.equal(seitenleisteText({ verfuegbar: true, neustart_noetig: false }), "");
assert.equal(seitenleisteText({ verfuegbar: false, neustart_noetig: true }), "");
assert.equal(seitenleisteText(null), "");
assert.equal(seitenleisteFuehrtZuEinstellungen({ verfuegbar: true }), true);
assert.equal(seitenleisteFuehrtZuEinstellungen({ verfuegbar: false }), false);
assert.equal(seitenleisteFuehrtZuEinstellungen(null), false);

// ── Versionen vergleichen (wie im Programm) ────────────────────────────────────────────
assert.deepEqual(fassungsSchluessel("1.8.0"), [1, 8, 0, 9, 0]);
assert.deepEqual(fassungsSchluessel("1.8.0-beta.15"), [1, 8, 0, 2, 15]);
for (const kaputt of ["", null, undefined, "v1.8.0", "1.8", "1.8.0.1", "1.8.0-nightly.1", "1.8.0\n", 5, "../1.8.0"]) {
  assert.equal(fassungsSchluessel(kaputt), null, String(kaputt));
}
assert.equal(istNeuer("1.8.1", "1.8.0"), true);
assert.equal(istNeuer("1.8.0", "1.8.0"), false);
assert.equal(istNeuer("1.8.0", "1.8.0-beta.15"), true, "die fertige Fassung ist neuer als ihre Beta");
assert.equal(istNeuer("1.10.0", "1.9.9"), true, "Zahlen, nicht Zeichenketten");
assert.equal(istNeuer("kaputt", "1.8.0"), false);
assert.equal(istNeuer("1.8.1", "kaputt"), false);
// installiert, aber noch nicht gestartet: kein „Update verfügbar“ mehr
assert.equal(istSchonInstalliert({ verfuegbar: true, aktuell: "1.8.1" }, "1.8.1"), true);
assert.equal(istSchonInstalliert({ verfuegbar: true, aktuell: "1.8.1" }, "1.8.2"), false);
assert.equal(istSchonInstalliert({ verfuegbar: true, aktuell: "1.8.1" }, "1.8.0"), true);
assert.equal(istSchonInstalliert({ verfuegbar: false, aktuell: "1.8.1" }, "1.8.1"), false);
assert.equal(istSchonInstalliert(null, "1.8.1"), false);

// ── Claude und das Dashboard mit verschiedenen Fassungen ─────────────────────────────────
const verbunden = (version) => ({ status: "connected", version });
assert.equal(claudeFassung(verbunden("1.8.0")), "1.8.0");
assert.equal(claudeFassung({ status: "disconnected", version: "1.8.0" }), "", "ein toter Herzschlag zählt nicht");
assert.equal(claudeFassung({ status: "unknown", version: "1.8.0" }), "");
assert.equal(claudeFassung(verbunden(null)), "", "ältere Programme schreiben keine Fassung: dann weiß PBP es nicht");
assert.equal(claudeFassung(verbunden("kaputt")), "");
assert.equal(claudeFassung(null), "");

assert.equal(verbindungsAbweichung(basis, verbunden("1.8.0")), null, "gleiche Fassung: nichts zu sagen");
assert.equal(verbindungsAbweichung({ ...basis, verfuegbar: false }, verbunden("1.7.0")), null, "ohne Installer-Layout kein Hinweis");
assert.equal(verbindungsAbweichung(basis, verbunden(null)), null);
assert.deepEqual(verbindungsAbweichung({ ...basis, laufend: "1.8.1", aktuell: "1.8.1" }, verbunden("1.8.0")),
  { claude: "1.8.0", dashboard: "1.8.1", claudeAelter: true });
assert.deepEqual(verbindungsAbweichung(basis, verbunden("1.8.1")), { claude: "1.8.1", dashboard: "1.8.0", claudeAelter: false });

const neuerAlsClaude = { ...basis, laufend: "1.8.1", aktuell: "1.8.1" };
h = updateHinweis(neuerAlsClaude, { mcp: verbunden("1.8.0") });
assert.equal(h.id, "update-verbindung");
assert.equal(h.dringend, true);
assert.match(h.titel, /Claude arbeitet noch mit Version 1\.8\.0/);
assert.match(h.text, /Version 1\.8\.1/);
assert.match(h.text, /Claude Desktop komplett/);
assert.deepEqual(h.aktionen.map((a) => a.art), ["update-optionen"]);

h = updateHinweis(basis, { mcp: verbunden("1.8.1") });
assert.equal(h.id, "update-verbindung");
assert.match(h.titel, /Dieses Fenster läuft noch mit Version 1\.8\.0/);
assert.match(h.text, /PBP Bewerbungs-Portal/);

// Rangfolge: was gerade passiert oder gefragt wird, geht vor; „Neustart nötig“ nennt beides schon
assert.equal(updateHinweis({ ...neuerAlsClaude, neustart_noetig: true }, { mcp: verbunden("1.8.0") }).id, "update-neustart");
assert.equal(updateHinweis({ ...neuerAlsClaude, rueckgang: { von: "1.8.2", nach: "1.8.1" } }, { mcp: verbunden("1.8.0") }).id, "update-rueckgang");
assert.equal(updateHinweis({ ...neuerAlsClaude, job: { status: "laeuft", version: "1.8.2", anteil: 0.3 } }, { mcp: verbunden("1.8.0") }).id, "update-laeuft");
// vor dem Hinweis „neue Version“: der Zustand jetzt zählt mehr als eine Nachricht von draußen
assert.equal(updateHinweis({ ...neuerAlsClaude, neu }, { mcp: verbunden("1.8.0") }).id, "update-verbindung");
// wer „automatisch, still“ gewählt hat, bekommt keine Meldung
assert.equal(updateHinweis({ ...neuerAlsClaude, stufe: "auto_still" }, { mcp: verbunden("1.8.0") }), null);
// ohne Angabe über Claude bleibt alles wie vorher
assert.equal(updateHinweis(neuerAlsClaude), null);
assert.equal(updateHinweis({ ...neuerAlsClaude, neu }).id, "update");

// ── #1170 U4: Neustart und „Aktuell“ ──────────────────────────────────────────────────
assert.equal(NEUSTART_SCHRITTE.length, 3);
assert.ok(neustartText().startsWith("1. ") && neustartText().includes(" 3. "));
// „Aktuell“ nur, wenn weder eine neuere Version noch ein Neustart aussteht.
assert.equal(zeigeAktuell({ verfuegbar: true, neu: null, neustart_noetig: false }), true);
assert.equal(zeigeAktuell({ verfuegbar: true, neu: null, neustart_noetig: true }), false, "nach der Installation nicht „Aktuell“ neben „Ab dem nächsten Neustart“");
assert.equal(zeigeAktuell({ verfuegbar: true, neu: { version: "1.8.2" }, neustart_noetig: false }), false);
assert.equal(zeigeAktuell(null), false);

console.log("autoUpdate: ok");
