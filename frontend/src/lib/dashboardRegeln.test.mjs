// #974/#984: Kipp-Test fuer die Dashboard-Regeln. Framework-frei, laeuft
// mit dem blanken Node der CI-Runner:
//   node src/lib/dashboardRegeln.test.mjs
//
// Die sieben Stufen unten sind die aus `workspace_service.py::build_workspace`.
// Waechst dort eine Stufe dazu, gehoert sie hier hinein — sonst entscheidet
// die neue Stufe wieder selbst, ob sie Onboarding-Information zeigt.
import {
  NICHTS_OFFEN,
  ONBOARDING_STUFEN,
  beschreibungWiederholtWoertlich,
  labelWiederholtHeadline,
  readinessWirdVomBlockGetragen,
  zeigeProfilKpi,
} from "./dashboardRegeln.js";

let failed = 0;
function check(name, actual, expected) {
  const ok = actual === expected;
  if (!ok) {
    failed++;
    console.error(`  FAIL  ${name}: erwartet ${JSON.stringify(expected)}, war ${JSON.stringify(actual)}`);
  } else {
    console.log(`  ok    ${name}`);
  }
}

console.log("Dashboard-Regeln (#974 G26, #984 G32)");

// --- #974: Onboarding-KPI nur im Onboarding ---
// Der gemeldete Fall: vollstaendiges Profil, Stufe `nachfassen`, und daneben
// steht dauerhaft "100% Profil vollstaendig".
const AUSSERHALB = ["quellen_aktivieren", "jobsuche_erneuern", "bewerben", "nachfassen", "im_fluss"];
for (const stage of AUSSERHALB) {
  check(`100 % + ${stage} zeigt die KPI nicht`, zeigeProfilKpi(stage, 100), false);
}
for (const stage of ONBOARDING_STUFEN) {
  check(`100 % + ${stage} zeigt die KPI`, zeigeProfilKpi(stage, 100), true);
}
// Unvollstaendig ist immer eine Aufgabe, egal in welcher Stufe.
for (const stage of [...AUSSERHALB, ...ONBOARDING_STUFEN]) {
  check(`60 % + ${stage} zeigt die KPI`, zeigeProfilKpi(stage, 60), true);
}
check("unbekannte Stufe bei 100 % zeigt nichts", zeigeProfilKpi("gibt_es_nicht", 100), false);
check("fehlender Wert bleibt sichtbar", zeigeProfilKpi("nachfassen", undefined), true);

// --- #984: Beschreibungssatz wiederholt die Ueberschrift ---
// Die Grenze offen benannt: der Review-Fall selbst teilt kein Wort mit der
// Headline und ist trotzdem dieselbe Aussage. Ihn loest G27 (das Feld
// entfaellt), nicht dieser Waechter. Hier steht, was der Waechter kann.
check(
  "woertliche Wiederholung",
  beschreibungWiederholtWoertlich("Dein Profil ist noch nicht vollstaendig.", "Dein Profil ist noch nicht vollstaendig."),
  true
);
check(
  "Headline steckt in der laengeren Beschreibung",
  beschreibungWiederholtWoertlich("Es gibt ueberfaellige Nachfassaktionen", "Es gibt ueberfaellige Nachfassaktionen, schau kurz rein"),
  true
);
check(
  "echte Ergaenzung bleibt erlaubt",
  beschreibungWiederholtWoertlich("Die Jobsuche ist noch nicht startbereit.", "Es fehlen aktive Quellen und Suchbegriffe."),
  false
);
check("leere Beschreibung", beschreibungWiederholtWoertlich("Alles bereit.", ""), false);

// --- #984: Etikett wiederholt die Ueberschrift ---
check(
  "Review-Fall: Badge Nachfassen ueber Nachfassaktionen",
  labelWiederholtHeadline("Nachfassen", "Es gibt ueberfaellige Nachfassaktionen."),
  true
);
check(
  "Etikett mit eigener Aussage",
  labelWiederholtHeadline("Im Fluss", "Alles bereit - du kannst loslegen."),
  false
);
check(
  "Etikett Quellen aktivieren ueber startbereiter Jobsuche",
  labelWiederholtHeadline("Quellen aktivieren", "Die Jobsuche ist noch nicht startbereit."),
  false
);
check(
  "Etikett Profil ausbauen ueber unvollstaendigem Profil",
  labelWiederholtHeadline("Profil ausbauen", "Dein Profil ist noch nicht vollstaendig."),
  true
);

// --- Nutzerhinweis 07.09.2026: die Karte wiederholt den Block ---
// Der Block "Offen" listete zwei faellige Nachfassungen mit Firma und
// Datum, und direkt darunter stand "Es gibt ueberfaellige
// Nachfassaktionen". #976 verlangte, keine ZAEHLUNGEN zu wiederholen —
// das war zu eng gelesen. Eine Wiederholung ohne Zahl ist immer noch
// eine Wiederholung.
check(
  "Nachfassen mit gefuelltem Block: Karte entfaellt",
  readinessWirdVomBlockGetragen("nachfassen", 2),
  true
);
check(
  "Nachfassen mit leerem Block: Karte traegt die Aussage",
  readinessWirdVomBlockGetragen("nachfassen", 0),
  false
);
check(
  "andere Stufe: Karte bleibt, der Block sagt dazu nichts",
  readinessWirdVomBlockGetragen("bewerben", 5),
  false
);

// --- #984: leerer Zustand ---
check("leerer Zustand ist eine Zeile", NICHTS_OFFEN, "Nichts offen");
check("und traegt keine Erklaerung", NICHTS_OFFEN.includes("."), false);

if (failed) {
  console.error(`\n${failed} Fehler`);
  process.exit(1);
}
console.log("\nalle Faelle gruen");
