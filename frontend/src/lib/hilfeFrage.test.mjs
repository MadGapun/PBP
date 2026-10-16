// #1233 (F51): was die Oberflaeche aus der Antwort der Hilfe macht. Kein Framework, kein Server.
import {
  BEISPIELFRAGEN, MAX_FRAGE, MAX_VERLAUF, WIKI_BASIS, aktionen, bereinigeFrage, hatKarten, kannFragen, kiAnzeige, kiGrundText, kiOffen, kopfzeile,
  navigationFuer, satzFuerClaude, seitenleisteFragt, verlaufMit, vorigeFrage, wikiAdresse,
} from "./hilfeFrage.js";

let fehler = 0;
function check(name, ist, soll) {
  const a = JSON.stringify(ist);
  const b = JSON.stringify(soll);
  if (a !== b) { fehler += 1; console.error(`FEHLER ${name}: ${a} != ${b}`); }
}

const SEITEN = ["dashboard", "profil", "stellen", "einstellungen"];
const REITER = ["updates", "ai", "quellen"];

// ── die Beispielfragen ──
check("drei bis fuenf Beispielfragen", BEISPIELFRAGEN.length >= 3 && BEISPIELFRAGEN.length <= 5, true);
check("jedes Beispiel ist eine abschickbare, bereinigte Frage", BEISPIELFRAGEN.every((f) => kannFragen(f) && bereinigeFrage(f) === f && f.length <= 80), true);
check("keine Beispielfrage doppelt", new Set(BEISPIELFRAGEN).size, BEISPIELFRAGEN.length);

// ── die Frage ──
check("Leerraum geglaettet", bereinigeFrage("  Wie   aktualisiere\n ich\tPBP?  "), "Wie aktualisiere ich PBP?");
check("auf die Laenge gekuerzt", bereinigeFrage("a ".repeat(500)).length, MAX_FRAGE);
check("kein Text", bereinigeFrage(null), "");
check("keine Zahl als Frage", bereinigeFrage(undefined), "");
check("zu kurz", kannFragen("a"), false);
check("leer", kannFragen("   "), false);
check("genug", kannFragen("Hi"), true);

// ── Sprungziele nur aus der geprueften Liste ──
check("Seite", navigationFuer({ art: "seite", id: "stellen" }, SEITEN, REITER), { page: "stellen", intent: null });
check("Reiter", navigationFuer({ art: "einstellung", id: "updates" }, SEITEN, REITER), { page: "einstellungen", intent: { tab: "updates" } });
check("unbekannte Seite", navigationFuer({ art: "seite", id: "gibt_es_nicht" }, SEITEN, REITER), null);
check("unbekannter Reiter", navigationFuer({ art: "einstellung", id: "gibt_es_nicht" }, SEITEN, REITER), null);
check("Adresse als Ziel", navigationFuer({ art: "url", id: "https://boese.example" }, SEITEN, REITER), null);
check("ohne Listen wird nichts geoeffnet", navigationFuer({ art: "seite", id: "stellen" }), null);
check("kein Ziel", navigationFuer(null, SEITEN, REITER), null);
check("falsche Form", navigationFuer("stellen", SEITEN, REITER), null);

// ── Wiki-Link nur ins Wiki des Projekts ──
check("Wiki", wikiAdresse({ seite: "Updates", url: `${WIKI_BASIS}Updates#die-vier-stufen` }), `${WIKI_BASIS}Updates#die-vier-stufen`);
check("fremde Adresse", wikiAdresse({ seite: "X", url: "https://boese.example/wiki/X" }), null);
check("javascript", wikiAdresse({ seite: "X", url: "javascript:alert(1)" }), null);
check("andere Seite auf GitHub", wikiAdresse({ seite: "X", url: "https://github.com/anderer/repo/wiki/X" }), null);
check("ohne Wiki", wikiAdresse(null), null);

// ── die Wege weiter einer Karte ──
const karte = {
  id: "hilfe:einstellungen:updates", titel: "Updates", kurz: "Unter Erweitert › Updates …", quelle: "Hilfe › Einstellungen",
  oeffnen: { art: "einstellung", id: "updates", label: "Öffnen: Einstellungen › Updates" },
  wiki: { seite: "Updates", url: `${WIKI_BASIS}Updates` },
  prompt: { id: "tipps_und_tricks", titel: "Tipps & Tricks", kopieren: "/tipps_und_tricks" },
  sicher: true,
};
check("alle drei, in fester Reihenfolge", aktionen(karte, SEITEN, REITER).map((a) => a.art), ["oeffnen", "wiki", "prompt"]);
check("oeffnen traegt Seite und Reiter", aktionen(karte, SEITEN, REITER)[0], {
  art: "oeffnen", label: "Öffnen: Einstellungen › Updates", page: "einstellungen", intent: { tab: "updates" },
});
check("Prompt traegt den Text zum Kopieren", aktionen(karte, SEITEN, REITER)[2], { art: "prompt", label: "Tipps & Tricks", text: "/tipps_und_tricks" });
check("Karte ohne Wege", aktionen({ id: "x", titel: "T", kurz: "k", quelle: "q", oeffnen: null, wiki: null, prompt: null }, SEITEN, REITER), []);
check("ein Prompt ohne Schraegstrich wird nicht angeboten", aktionen({ ...karte, oeffnen: null, wiki: null, prompt: { titel: "X", kopieren: "rm -rf" } }, SEITEN, REITER), []);
check("ein Ziel ausserhalb der Liste entfaellt, der Rest bleibt",
  aktionen({ ...karte, oeffnen: { art: "seite", id: "weg", label: "Öffnen: Weg" } }, SEITEN, REITER).map((a) => a.art), ["wiki", "prompt"]);
check("keine Karte", aktionen(null), []);

// ── die Antwort ──
check("sichere Antwort", kopfzeile({ status: "gefunden", hinweis: "" }), "Das habe ich dazu gefunden");
check("unsichere Antwort sagt es", kopfzeile({ status: "unsicher", hinweis: "Ich bin nicht sicher, ob das passt." }), "Ich bin nicht sicher, ob das passt.");
check("ausserhalb", kopfzeile({ status: "ausserhalb", hinweis: "Dazu kann ich nur zur Bedienung von PBP etwas sagen." }), "Dazu kann ich nur zur Bedienung von PBP etwas sagen.");
check("keine Antwort", kopfzeile(null), "");
check("Karten da", hatKarten({ karten: [{ id: "a" }] }), true);
check("keine Karten", hatKarten({ karten: [] }), false);
check("kein Feld", hatKarten({}), false);
check("Satz fuer Claude", satzFuerClaude({ claude: { satz: "Ich habe eine Frage zu PBP" } }), "Ich habe eine Frage zu PBP");
check("kein Satz", satzFuerClaude({ claude: null }), "");
check("kein Text als Satz", satzFuerClaude({ claude: { satz: 5 } }), "");

// ── die Kurzantwort der lokalen KI ──
check("aus: nichts zu zeigen", kiAnzeige({ status: "aus", grund: "schalter_aus" }, null), { zeigen: false, wartet: false, text: "", quellen: [] });
check("laeuft: Warteanzeige", kiAnzeige({ status: "laeuft", job: "j" }, null), { zeigen: true, wartet: true, text: "", quellen: [] });
check("laeuft noch laut Stand", kiAnzeige({ status: "laeuft", job: "j" }, { status: "laeuft" }), { zeigen: true, wartet: true, text: "", quellen: [] });
check("fertig", kiAnzeige({ status: "laeuft", job: "j" }, { status: "fertig", text: " Unter Updates. ", quellen: ["a"] }),
  { zeigen: true, wartet: false, text: "Unter Updates.", quellen: ["a"] });
check("verworfen zeigt nichts", kiAnzeige({ status: "laeuft", job: "j" }, { status: "verworfen", grund: "ohne_quelle" }),
  { zeigen: false, wartet: false, text: "", quellen: [] });
check("Fehler zeigt nichts", kiAnzeige({ status: "laeuft", job: "j" }, { status: "fehler" }), { zeigen: false, wartet: false, text: "", quellen: [] });
check("fertig ohne Text zeigt nichts", kiAnzeige({ status: "laeuft", job: "j" }, { status: "fertig", text: "  " }), { zeigen: false, wartet: false, text: "", quellen: [] });
check("unbekannter Auftrag zeigt nichts", kiAnzeige({ status: "laeuft", job: "j" }, { status: "unbekannt" }), { zeigen: false, wartet: false, text: "", quellen: [] });
check("kein ki-Feld", kiAnzeige(undefined, null), { zeigen: false, wartet: false, text: "", quellen: [] });
check("offen", kiOffen({ status: "laeuft", job: "j" }, null), true);
check("offen laut Stand", kiOffen({ status: "laeuft", job: "j" }, { status: "laeuft" }), true);
check("nicht mehr offen", kiOffen({ status: "laeuft", job: "j" }, { status: "fertig" }), false);
check("aus ist nie offen", kiOffen({ status: "aus" }, null), false);
check("ohne Auftrag nie offen", kiOffen({ status: "laeuft" }, null), false);

// ── der Verlauf (nur im Arbeitsspeicher) ──
let v = [];
for (let i = 1; i <= MAX_VERLAUF + 3; i += 1) v = verlaufMit(v, { frage: `Frage ${i}` });
check("hoechstens fuenf, die neuesten", v.map((e) => e.frage), ["Frage 4", "Frage 5", "Frage 6", "Frage 7", "Frage 8"]);
check("vorige Frage", vorigeFrage(v), "Frage 8");
check("keine vorige Frage", vorigeFrage([]), "");
check("kein Verlauf", vorigeFrage(undefined), "");

// ── der Zustand neben dem Schalter ──
check("bereit", kiGrundText({ aktiv: true, grund: "" }), "Die lokale KI ist bereit.");
check("nicht erreichbar", kiGrundText({ aktiv: false, grund: "ollama_nicht_erreichbar" }), "Die lokale KI (Ollama) ist gerade nicht erreichbar.");
check("abgeschaltet", kiGrundText({ aktiv: false, grund: "ki_off" }), "Die lokale KI ist abgeschaltet.");
check("pausiert", kiGrundText({ aktiv: false, grund: "ki_paused" }), "Die lokale KI ist pausiert.");
check("kein Modell", kiGrundText({ aktiv: false, grund: "kein_modell" }), "Es ist noch kein Modell gewählt.");
check("unbekannter Grund", kiGrundText({ aktiv: false, grund: "etwas_neues" }), "Die lokale KI ist gerade nicht bereit.");
check("kein Zustand", kiGrundText(null), "");

// ── die Seitenleiste ──
check("Eingabe nur bei laufender KI", seitenleisteFragt({ ai_state: "active" }), true);
check("nicht bei pausierter KI", seitenleisteFragt({ ai_state: "paused" }), false);
check("nicht bei abgeschalteter KI", seitenleisteFragt({ ai_state: "off" }), false);
check("nicht ohne Status", seitenleisteFragt(null), false);

if (fehler) { console.error(`${fehler} Fehler`); process.exit(1); }
console.log("hilfeFrage: alle Faelle gruen");
