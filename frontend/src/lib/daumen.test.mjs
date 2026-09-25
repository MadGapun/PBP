// #1052: Kipp-Test fuer die Anzeige der beiden Daumen. Framework-frei,
// laeuft mit dem blanken Node der CI-Runner:
//   node src/lib/daumen.test.mjs
//
// Geprueft wird die TRENNUNG der beiden Kanaele: grau schlaegt die
// Richtung, und "ungeprueft" darf nie aussehen wie "passt nicht" (#989).
// Dazu die Toene — `rose` oder `red` erzeugen in dieser
// Tailwind-Konfiguration keine Regel UND keinen Fehler (#964).
import {
  BELEGT,
  FACH,
  GRAU,
  HOCH,
  MITTEL,
  RAHMEN,
  RUNTER,
  etikett,
  maximumText,
  ohneGrundlage,
  symbol,
  titel,
  ton,
} from "./daumen.js";

let failed = 0;
function check(name, actual, expected) {
  const ok = JSON.stringify(actual) === JSON.stringify(expected);
  if (!ok) {
    failed++;
    console.error(`  FAIL  ${name}: erwartet ${JSON.stringify(expected)}, war ${JSON.stringify(actual)}`);
  } else {
    console.log(`  ok    ${name}`);
  }
}

// ── Die Toene sind Projekt-Tokens ──────────────────────────────────
check("hoch und belegt ist gruen", ton({ richtung: HOCH, farbe: BELEGT }), "success");
// Der Ton heisst `danger` — er FAERBT coral, aber `coral` als Ton
// erzeugt keine Regel und keinen Fehler (#964).
check("runter und belegt ist danger", ton({ richtung: RUNTER, farbe: BELEGT }), "danger");
check("mittel und belegt ist amber", ton({ richtung: MITTEL, farbe: BELEGT }), "amber");
// Der eigentliche Fall: dieselbe Richtung, ungeprueft — der Ton muss
// sich unterscheiden, sonst behauptet die Karte eine Sicherheit, die
// die Angaben nicht hergeben.
check("runter und grau ist neutral", ton({ richtung: RUNTER, farbe: GRAU }), "neutral");
check("hoch und grau ist neutral", ton({ richtung: HOCH, farbe: GRAU }), "neutral");
check("ohne Marke steht nichts Farbiges da", ton(null), "neutral");

// ── Das Symbol folgt der RICHTUNG, nicht der Farbe ─────────────────
// Sonst waere die Trennung der beiden Kanaele wieder aufgehoben: ein
// grauer Daumen nach unten heisst "sieht schlecht aus, aber
// ungeprueft" — die Richtung bleibt also sichtbar.
check("grau behaelt die Richtung", symbol({ richtung: RUNTER, farbe: GRAU }), "runter");
check("hoch zeigt nach oben", symbol({ richtung: HOCH, farbe: BELEGT }), "hoch");
check("ohne Marke bleibt es mittig", symbol(null), "mittel");

// ── Die Beschriftung nennt die Frage, die der Daumen beantwortet ───
check("Fachwert hoch", etikett({ richtung: HOCH, farbe: BELEGT }, FACH), "passt fachlich gut");
check("Rahmen runter", etikett({ richtung: RUNTER, farbe: BELEGT }, RAHMEN), "Rahmen passt nicht");
// "ungeprueft" steht DA und fehlt nicht — eine fehlende Auskunft ist
// von einer negativen nicht zu unterscheiden (#989).
check("grau sagt es", etikett({ richtung: RUNTER, farbe: GRAU }, RAHMEN),
      "Rahmen passt nicht (ungeprüft)");
check("ohne Marke kein Etikett", etikett(null, FACH), "");
// C97 (#1087 C8): der Grund steht an der Karte, nicht erst im Tooltip.
check("grau nennt den Grund",
      etikett({ richtung: RUNTER, farbe: GRAU, ungeprueft_weil: "Entfernung unbekannt" }, RAHMEN),
      "Rahmen passt nicht (ungeprüft: Entfernung unbekannt)");

// ── Der Titel traegt die Begruendung des Servers ───────────────────
check("Begruendung wandert mit",
      titel({ richtung: HOCH, farbe: BELEGT, grund: "31 Punkte — im oberen Viertel." }, FACH),
      "Fachlich: passt fachlich gut — 31 Punkte — im oberen Viertel.");
check("ohne Begruendung bleibt der Kopf",
      titel({ richtung: MITTEL, farbe: BELEGT }, RAHMEN), "Rahmen: Rahmen mit Abstrichen");

// ── Ohne Grundlage ────────────────────────────────────────────────
check("mittel und grau heisst: keine Grundlage",
      ohneGrundlage({ richtung: MITTEL, farbe: GRAU }), true);
check("grau mit Richtung ist etwas anderes",
      ohneGrundlage({ richtung: RUNTER, farbe: GRAU }), false);

// ── Das Fachmaximum steht als Zahl da, nie als Prozentsatz ────────
check("Maximum als Detail", maximumText({ fach_maximum: 42.25 }), "fachlich erreichbar: 42.3");
check("ohne Maximum kein Text", maximumText({}), "");
check("0 heisst unbekannt und wird nicht behauptet", maximumText({ fach_maximum: 0 }), "");
// Und ausdruecklich KEIN Prozentzeichen — der Nutzer hat das Kriterium
// am 16.09.2026 zurueckgezogen, weil es weder Ober- noch Untergrenze
// gibt: die besten Stellen koennen sogar im Minus liegen.
check("kein Prozent", maximumText({ fach_maximum: 42 }).includes("%"), false);

if (failed) {
  console.error(`\n${failed} Fehler`);
  process.exit(1);
}
console.log("\nalle Faelle gruen");
