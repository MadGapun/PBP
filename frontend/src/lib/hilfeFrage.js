/**
 * Die Hilfe zum Fragen — #1233 (F51).
 *
 * Der Server (`/api/hilfe/frage`) antwortet mit Karten: Titel, Kurztext, Quelle und hoechstens drei Wegen weiter — ein Sprung in die App,
 * die Wiki-Seite, der Prompt zum Kopieren. Dieses Modul macht daraus, was die Oberflaeche zeigt, ohne Framework: der Node-Test prueft es
 * (`hilfeFrage.test.mjs`).
 *
 * Nichts davon kommt aus einem Sprachmodell: Sprungziele und Prompts stehen in geprueften Listen des Servers. Hier wird zusaetzlich geprueft,
 * dass ein Sprung nur auf eine bekannte Seite oder einen bekannten Reiter geht und ein Link nur in das Wiki des Projekts.
 *
 * Fragen werden nicht gespeichert: der Verlauf lebt nur im Arbeitsspeicher der Seite.
 */
import { istWebAdresse } from "./webAdresse.js";

export const MAX_FRAGE = 400;
export const MAX_VERLAUF = 5;
export const WIKI_BASIS = "https://github.com/MadGapun/PBP/wiki/";

/**
 * Fragen zum Anklicken, solange im Hilfe-Dialog noch nichts gefragt wurde: wer nicht weiss, was er fragen soll, bekommt Anhaltspunkte.
 * Jede ist getestet (`tests/test_v18_hilfe_suche_1233.py`): der Server antwortet sicher, und die erste Karte fuehrt weiter.
 */
export const BEISPIELFRAGEN = [
  "Wie aktualisiere ich PBP?",
  "Wie lege ich eine Bewerbung an?",
  "Wo liegen meine Daten auf dem Rechner?",
  "Wie melde ich einen Fehler?",
];

/** Die Frage, wie sie an den Server geht: Leerraum geglaettet, auf die erlaubte Laenge gekuerzt. */
export function bereinigeFrage(text) {
  return String(text ?? "").replace(/\s+/g, " ").trim().slice(0, MAX_FRAGE);
}

/** Ist das eine Frage, die man abschicken kann? */
export function kannFragen(text) {
  return bereinigeFrage(text).length >= 2;
}

/**
 * Wohin ein "Oeffnen" fuehrt: { page, intent } fuer `navigateTo`, oder null, wenn das Ziel nichts Bekanntes ist.
 * `seiten` und `reiter` sind die Listen, die der Server mitgeschickt hat (PAGE_IDS, SETTINGS_REITER) — ohne sie wird nichts geoeffnet.
 */
export function navigationFuer(oeffnen, seiten = [], reiter = []) {
  if (!oeffnen || typeof oeffnen !== "object") return null;
  if (oeffnen.art === "seite" && seiten.includes(oeffnen.id)) return { page: oeffnen.id, intent: null };
  if (oeffnen.art === "einstellung" && reiter.includes(oeffnen.id)) return { page: "einstellungen", intent: { tab: oeffnen.id } };
  return null;
}

/** Eine Wiki-Adresse, nur wenn sie ins Wiki des Projekts zeigt. */
export function wikiAdresse(wiki) {
  if (!wiki || !istWebAdresse(wiki.url)) return null;
  return wiki.url.startsWith(WIKI_BASIS) ? wiki.url : null;
}

/** Die Wege weiter einer Karte, in fester Reihenfolge: oeffnen, Wiki, Prompt. Leer, wenn die Karte keinen hat. */
export function aktionen(karte, seiten = [], reiter = []) {
  const aus = [];
  if (!karte) return aus;
  const nav = navigationFuer(karte.oeffnen, seiten, reiter);
  if (nav) aus.push({ art: "oeffnen", label: karte.oeffnen.label, page: nav.page, intent: nav.intent });
  const wiki = wikiAdresse(karte.wiki);
  if (wiki) aus.push({ art: "wiki", label: "Mehr im Wiki", url: wiki });
  if (karte.prompt && typeof karte.prompt.kopieren === "string" && karte.prompt.kopieren.startsWith("/") && karte.prompt.titel) {
    aus.push({ art: "prompt", label: karte.prompt.titel, text: karte.prompt.kopieren });
  }
  return aus;
}

/** Die Zeile ueber den Karten. */
export function kopfzeile(antwort) {
  if (!antwort) return "";
  if (antwort.status === "gefunden") return "Das habe ich dazu gefunden";
  return antwort.hinweis || "";
}

/** Zeigt die Antwort Karten? Bei "ausserhalb" und "nichts gefunden" gibt es keine, nur den Hinweis und den Satz fuer Claude. */
export function hatKarten(antwort) {
  return Boolean(antwort && Array.isArray(antwort.karten) && antwort.karten.length > 0);
}

/** Der kopierfertige Satz fuer Claude (leer, wenn der Server keinen mitgegeben hat — dann gibt es auch keinen Knopf). */
export function satzFuerClaude(antwort) {
  const satz = antwort?.claude?.satz;
  return typeof satz === "string" ? satz : "";
}

/**
 * Der Satz ueber dem Knopf "Frage kopieren mit Claude": nach Karten die Frage, ob es passt (bei einem unsicheren Treffer: ob einer davon passt);
 * bei einer Frage ausserhalb von PBP sagt der Hinweis schon, dass Claude dafuer da ist; sonst der Verweis auf Claude.
 */
export function claudeVorsatz(antwort) {
  if (!antwort) return "";
  if (hatKarten(antwort)) return antwort.status === "unsicher" ? "Passt keiner davon?" : "Passt das nicht?";
  if (antwort.status === "ausserhalb") return "";
  return "Dafür ist Claude da.";
}

/**
 * Was zur kurzen Antwort der lokalen KI zu zeigen ist.
 * `ki` ist das Feld der Antwort ({status: "aus"|"laeuft", job?}) und `stand` das Ergebnis von `/api/hilfe/ki/<job>`.
 * Rueckgabe: { zeigen, wartet, text, quellen }. Eine verworfene oder fehlgeschlagene Kurzantwort zeigt NICHTS: die Karten stehen da.
 */
export function kiAnzeige(ki, stand) {
  if (!ki || ki.status !== "laeuft") return { zeigen: false, wartet: false, text: "", quellen: [] };
  if (!stand || stand.status === "laeuft") return { zeigen: true, wartet: true, text: "", quellen: [] };
  if (stand.status === "fertig" && typeof stand.text === "string" && stand.text.trim()) {
    return { zeigen: true, wartet: false, text: stand.text.trim(), quellen: Array.isArray(stand.quellen) ? stand.quellen : [] };
  }
  return { zeigen: false, wartet: false, text: "", quellen: [] };
}

/** Ist der Auftrag der Kurzantwort noch offen (dann wird weiter gefragt)? */
export function kiOffen(ki, stand) {
  return Boolean(ki && ki.status === "laeuft" && ki.job && (!stand || stand.status === "laeuft"));
}

/** Der Verlauf mit der neuen Antwort, hoechstens `MAX_VERLAUF` Eintraege (die neuesten). */
export function verlaufMit(verlauf, eintrag) {
  return [...(verlauf || []), eintrag].slice(-MAX_VERLAUF);
}

/** Die vorige Frage fuer eine Nachfrage ("und wo finde ich das?") — nur die letzte, und nur wenn es eine gab. */
export function vorigeFrage(verlauf) {
  const letzter = (verlauf || [])[(verlauf || []).length - 1];
  return letzter?.frage || "";
}

const KI_GRUND = {
  ollama_nicht_erreichbar: "Die lokale KI (Ollama) ist gerade nicht erreichbar.",
  ki_off: "Die lokale KI ist abgeschaltet.",
  ki_paused: "Die lokale KI ist pausiert.",
  kein_modell: "Es ist noch kein Modell gewählt.",
  unbekannt: "Der Zustand der lokalen KI ist nicht lesbar.",
};

/** Ein Satz zum Zustand der lokalen KI neben dem Schalter fuer die Kurzantwort (Einstellungen > Lokale KI). */
export function kiGrundText(zustand) {
  if (!zustand) return "";
  if (zustand.aktiv) return "Die lokale KI ist bereit.";
  return KI_GRUND[zustand.grund] || "Die lokale KI ist gerade nicht bereit.";
}

/** Das Eingabefeld der Seitenleiste erscheint nur, wenn die lokale KI laeuft (Nutzerwunsch 16.10.2026). */
export function seitenleisteFragt(status) {
  return Boolean(status) && status.ai_state === "active";
}
