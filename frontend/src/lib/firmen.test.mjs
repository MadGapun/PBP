// node frontend/src/lib/firmen.test.mjs
// Firmen-Ansicht (#1080): Datum, Filter, Sprünge, Hash und die Optionen der Auswahlfelder.
import assert from "node:assert/strict";
import {
  ansichtAusKennung, artName, datumText, filterKnoepfe, filterZeitleiste, hashFuerFirma, kannAnlegen, mutterOptionen,
  schreibweisen, sicherheitText, sprung, sprungText, statusText, statusTon, vorschlagText, zaehlungsZeile, zusammenfuehrenOptionen,
  fehlerText, ART_REIHENFOLGE,
} from "./firmen.js";

// ── Datum ─────────────────────────────────────────────────────────────────────────────
assert.equal(datumText("2026-09-10"), "10.09.2026");
assert.equal(datumText("2021-03"), "03.2021");
assert.equal(datumText("2021"), "2021");
assert.equal(datumText(""), "ohne Datum");
assert.equal(datumText(null), "ohne Datum");
assert.equal(datumText("neulich"), "neulich", "was kein Datum ist, bleibt stehen, wie es ist");

// ── Arten, Zählung, Filter ────────────────────────────────────────────────────────────
assert.equal(artName("bewerbung", 1), "Bewerbung");
assert.equal(artName("bewerbung", 2), "Bewerbungen");
assert.equal(artName("lebenslauf", 3), "Stationen im Lebenslauf");
assert.equal(artName("gibtsnicht", 2), "gibtsnicht");
const z = { bewerbung: 2, stelle: 1, kontakt: 0, lebenslauf: 3, korrespondenz: 0, recherche: 0, blacklist: 0, erwaehnt: 0 };
assert.deepEqual(filterKnoepfe(z).map((k) => k.art), ["bewerbung", "stelle", "lebenslauf"], "nur, wozu es etwas gibt, in fester Reihenfolge");
assert.equal(zaehlungsZeile(z, { anzahl: 12 }), "2 Bewerbungen · 1 Stelle · 3 Stationen im Lebenslauf · 12 aussortierte Stellen");
assert.equal(zaehlungsZeile(z, { anzahl: 1 }).endsWith("1 aussortierte Stelle"), true);
assert.equal(zaehlungsZeile({}, null), "");
assert.deepEqual(ART_REIHENFOLGE.slice(0, 3), ["bewerbung", "stelle", "kontakt"]);
const zeit = [{ art: "bewerbung", titel: "A" }, { art: "stelle", titel: "B" }, { art: "bewerbung", titel: "C" }];
assert.deepEqual(filterZeitleiste(zeit, "bewerbung").map((e) => e.titel), ["A", "C"]);
assert.equal(filterZeitleiste(zeit, "").length, 3);
assert.deepEqual(filterZeitleiste(null, "bewerbung"), []);

// ── Sprünge ───────────────────────────────────────────────────────────────────────────
assert.deepEqual(sprung({ seite: "bewerbungen", bewerbung_id: "ab12cd34" }), { seite: "bewerbungen", intent: { applicationId: "ab12cd34", focus: "timeline" } });
assert.deepEqual(sprung({ seite: "bewerbungen" }), { seite: "bewerbungen", intent: null });
assert.deepEqual(sprung({ seite: "stellen", job_hash: "h1" }), { seite: "stellen", intent: { focus: "job", jobHash: "h1" } });
assert.deepEqual(sprung({ seite: "kontakte", suche: "Kim" }), { seite: "kontakte", intent: { ansicht: "kontakte", suche: "Kim" } });
assert.deepEqual(sprung({ seite: "profil" }), { seite: "profil", intent: null });
assert.equal(sprung({ seite: "irgendwo" }), null, "eine unbekannte Seite führt nirgends hin");
assert.equal(sprung(null), null);
assert.equal(sprung({}), null);
assert.equal(sprungText({ seite: "bewerbungen" }), "Bewerbung öffnen");
assert.equal(sprungText({ seite: "suche" }), "Blacklist ansehen");
assert.equal(sprungText({ seite: "x" }), "");

// ── Hash ──────────────────────────────────────────────────────────────────────────────
assert.deepEqual(ansichtAusKennung("fi_abc123"), { ansicht: "firmen", firmaId: "fi_abc123" });
assert.deepEqual(ansichtAusKennung("firma:Neu GmbH"), { ansicht: "firmen", firmaName: "Neu GmbH" });
assert.equal(ansichtAusKennung("firma:"), null);
assert.equal(ansichtAusKennung("abc12345"), null, "die Kennung eines Kontakts ist keine Firma");
assert.equal(ansichtAusKennung(""), null);
assert.equal(hashFuerFirma("fi_abc"), "#kontakte/fi_abc");
assert.equal(hashFuerFirma("Neu GmbH"), "#kontakte/firma%3ANeu%20GmbH");
assert.equal(hashFuerFirma(""), "#kontakte");
// der Hash trägt zurück: parseHashZiel dekodiert, ansichtAusKennung liest
assert.deepEqual(ansichtAusKennung(decodeURIComponent(hashFuerFirma("Müller & Söhne").split("/")[1])), { ansicht: "firmen", firmaName: "Müller & Söhne" });

// ── Status ────────────────────────────────────────────────────────────────────────────
assert.equal(statusTon("abgelehnt"), "danger");
assert.equal(statusTon("angebot"), "success");
assert.equal(statusTon("interview"), "sky");
assert.equal(statusTon("beworben"), "neutral");
assert.equal(statusText("interview", [{ value: "interview", label: "Interview" }]), "Interview");
assert.equal(statusText("neu_erfunden", []), "neu_erfunden");
assert.equal(statusText(null, []), "");

// ── Schreibweisen, Optionen ───────────────────────────────────────────────────────────
assert.deepEqual(schreibweisen({ aliase: [{ id: 1, alias: "Alt AG", art: "frueherer_name", art_text: "Früherer Name" }, { id: 2, alias: "alt ag" }, { id: 3, alias: "" }] }),
  [{ id: 1, alias: "Alt AG", art: "frueherer_name", art_text: "Früherer Name" }], "Doppelte und leere fallen weg");
assert.deepEqual(schreibweisen(null), []);
const firmen = [{ id: "fi_1", name: "A" }, { id: "fi_2", name: "B" }, { id: "fi_3", name: "C" }];
assert.deepEqual(mutterOptionen(firmen, { id: "fi_1", tochterfirmen: [{ id: "fi_2" }] }).map((f) => f.id), ["fi_3"], "nicht sie selbst, nicht ihre Töchter (Kreis)");
assert.deepEqual(mutterOptionen(firmen, null), []);
assert.deepEqual(zusammenfuehrenOptionen(firmen, { id: "fi_2" }).map((f) => f.id), ["fi_1", "fi_3"]);

// ── Vorschläge, Anlegen, Fehler ───────────────────────────────────────────────────────
assert.equal(vorschlagText({ name: "Neu GmbH", art: "neu", schreibweisen: ["Neu GmbH", "Neu"], vorkommen: 4 }), "Neu GmbH: 2 Schreibweisen, 4 Vorkommen");
assert.equal(vorschlagText({ name: "Neu GmbH", art: "ergaenzung", ergaenzt_firma: { name: "Neu" }, neue_schreibweisen: ["Neu AG"] }), "Neu GmbH: ergänzt „Neu“ um 1 Schreibweise");
assert.equal(vorschlagText({ name: "X", art: "ergaenzung", ergaenzt_firma: { name: "Y" }, neue_schreibweisen: ["a", "b"] }), "X: ergänzt „Y“ um 2 Schreibweisen");
assert.equal(vorschlagText(null), "");
assert.match(sicherheitText("mittel"), /prüfen/);
assert.doesNotMatch(sicherheitText("hoch"), /prüfen/);
assert.equal(fehlerText({ error: "Zu kurz." }), "Zu kurz.");
assert.equal(fehlerText({ text: "Anders." }), "Anders.");
assert.equal(fehlerText(null), "Das hat nicht geklappt.");
assert.equal(kannAnlegen({ status: "ok", stammsatz: null, mehrdeutig: [], name: "Neu GmbH" }), true);
assert.equal(kannAnlegen({ status: "ok", stammsatz: { id: "fi_1" }, mehrdeutig: [], name: "Neu GmbH" }), false, "es gibt schon einen Eintrag");
assert.equal(kannAnlegen({ status: "ok", stammsatz: null, mehrdeutig: ["A", "B"], name: "Muster" }), false, "mehrdeutig: PBP rät nicht");
assert.equal(kannAnlegen(null), false);

console.log("firmen.test.mjs: ok");
