// #1412 D5
import { uploadMeldung } from "./mailErkannt.js";

let fehler = 0;
function check(name, ist, soll) {
  if (ist !== soll) { fehler += 1; console.error(`FEHLER ${name}: ${ist} != ${soll}`); }
}
check("normale Datei", uploadMeldung("cv.pdf", {}).text, "'cv.pdf' hochgeladen und verknüpft.");
check("Duplikat", uploadMeldung("a.pdf", { duplicate_of: "x" }).text, "'a.pdf' verknüpft (war schon vorhanden).");
const einladung = uploadMeldung("m.eml", {
  meetings: [{ start: "2026-12-01T10:00:00" }],
  mail_erkannt: { termine: 1, angebot: { status: "interview", name: "Interview" } },
});
check("Einladung", einladung.text,
  "'m.eml' hochgeladen und verknüpft · Termin 01.12., 10:00 Uhr angelegt · Status erkannt: Interview.");
check("Angebot", einladung.angebot.status, "interview");
const absage = uploadMeldung("a.eml", { mail_erkannt: { termine: 0, angebot: { status: "abgelehnt", name: "Absage" } } });
check("Absage", absage.text, "'a.eml' hochgeladen und verknüpft · Status erkannt: Absage.");
check("Mail ohne Befund", uploadMeldung("n.eml", { mail_erkannt: { termine: 0, angebot: null } }).text,
  "'n.eml' hochgeladen und verknüpft.");
if (fehler) process.exit(1);
console.log("mailErkannt: ok");
