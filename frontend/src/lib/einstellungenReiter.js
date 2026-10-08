// Die Reiter der Einstellungen an einer Stelle (G70, #1087 F1).
// SettingsPage zeichnet sie, die Seitenleiste listet sie, und
// services/menue.py nennt ihre Namen in Antworten — ein Test haelt alle
// drei zusammen. "Grundlagen" reicht fuer den Anfang; "Erweitert" ist
// eingeklappt.
export const SETTINGS_REITER = [
  { id: "quellen", label: "Quellen", gruppe: "grundlagen" },
  { id: "erscheinungsbild", label: "Erscheinungsbild", gruppe: "grundlagen" },
  { id: "datenschutz", label: "Datenschutz", gruppe: "grundlagen" },
  { id: "ordner", label: "Ordner", gruppe: "grundlagen" },
  // H25 (#1087 G5): was an Anthropic geht.
  { id: "claude", label: "Claude (Cloud)", gruppe: "grundlagen" },
  // v1.8 (#1093): Auto-Update. Bewusst unter "Erweitert": "Grundlagen sind wenige" (G70); wer ein Update bekommt,
  // wird vom Hinweis direkt hierher gefuehrt.
  { id: "updates", label: "Updates", gruppe: "erweitert" },
  // v1.8 (#1131): wohin PBP schreibt und laedt, und Bereinigen in zwei Schritten.
  { id: "speicher", label: "Speicher & Downloads", gruppe: "erweitert" },
  { id: "quellen_details", label: "Quellen im Detail", gruppe: "erweitert" },
  { id: "ai", label: "Lokale KI", gruppe: "erweitert" },
  { id: "automatik", label: "Automatik", gruppe: "erweitert" },
  // #663 C20; G69: hiess "Bewertung", enthaelt aber die Ablehnungsgruende.
  { id: "bewerten", label: "Ablehnungsgründe", gruppe: "erweitert" },
  { id: "bericht", label: "Bewerbungsbericht", gruppe: "erweitert" },
  { id: "erweiterungen", label: "Erweiterungen", gruppe: "erweitert" },
  { id: "system", label: "System", gruppe: "erweitert" },
  { id: "logs", label: "Logs", gruppe: "erweitert" },
  { id: "gefahrenzone", label: "Gefahrenzone", gruppe: "erweitert" },
];
