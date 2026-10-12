// Die feste Weg-Leiste (#1171, G85, Baustein 3): was von einer Ansicht aus als Nächstes geht — an EINEM Ort, mit EINEN Wörtern.
//
// Eine Ansicht eines Falls (Stelle, Bewerbung, Kontakt, Firma) trägt oben eine Leiste, die beim Scrollen stehen bleibt:
//
//     ‹ Zurück zu …   |   Stelle · Firma · Kontakte 2 · Dokumente 1 · Termine 1   |   ▸ nächster Schritt ▾
//
// * links der Rückweg (dorthin, woher man kam; sonst die Liste),
// * in der Mitte die anderen Ansichten desselben Falls — nur was es gibt, mit Anzahl; ein Klick öffnet das OBJEKT, bei mehreren
//   steht eine kurze Auswahl,
// * rechts der wahrscheinlichste nächste Schritt (der Hauptknopf) und dahinter die anderen Wege.
//
// Hier steht nur die Rechnung: aus dem Zustand eines Falls die Einträge der Leiste. Gezeichnet wird in
// components/WegLeiste.jsx; was ein Eintrag TUT, hängt die Seite an (`aktion` ist eine Kennung, kein Aufruf). Die Wörter
// sind überall dieselben („Zur Stelle“, „Zur Bewerbung“, „Zur Firma“, „Zum Kontakt“; Frage 8 aus #1171).

import { zuBewerbung, zuDokument, zuFirma, zuKontakt, zuStelle, zuTermin } from "./wege.js";

/** Die Wörter für die Ziele, einmal. */
export const WEG_WORT = {
  stelle: "Zur Stelle",
  bewerbung: "Zur Bewerbung",
  firma: "Zur Firma",
  kontakt: "Zum Kontakt",
};

function text(wert) {
  return String(wert ?? "").trim();
}

/**
 * Ein Fall in der Mitte der Leiste: `eintraege` sind die Objekte, die es gibt. Mit einem Eintrag öffnet der Klick es, mit
 * mehreren zeigt die Leiste eine kurze Auswahl. Ohne Eintrag gibt es den Fall nicht (und keinen Knopf).
 */
function fall(id, label, eintraege) {
  const liste = (eintraege || []).filter((e) => e && e.ziel);
  if (!liste.length) return null;
  return { id, label, anzahl: liste.length, eintraege: liste };
}

function ziel(z) {
  return z ? { seite: z.seite, intent: z.intent } : null;
}

// ── Der nächste Schritt je Zustand ───────────────────────────────────────────────────────────────────

const NACHFASSEN = new Set(["beworben", "eingangsbestaetigung", "interview_abgeschlossen"]);
const GESPRAECH = new Set(["interview", "zweitgespraech"]);
const ENDE = new Set(["angenommen", "zurueckgezogen", "abgelaufen", "arbeitgeber_ausgefallen"]);

/**
 * Der Hauptknopf einer BEWERBUNG und die Wege dahinter, nach Status (die Tabelle aus #1171). Gibt es keinen sinnvollen
 * nächsten Schritt (die Bewerbung ist zu Ende), ist `haupt` null.
 */
export function bewerbungSchritt({ status, hatLebenslauf = false, hatAnschreiben = false, nachfassenFaellig = false } = {}) {
  const s = text(status);
  const weitere = [];
  let haupt = null;
  if (s === "in_vorbereitung") {
    if (!hatLebenslauf) {
      haupt = { aktion: "lebenslauf", label: "Lebenslauf", mitClaude: true };
      if (!hatAnschreiben) weitere.push({ aktion: "anschreiben", label: "Anschreiben", mitClaude: true });
    } else if (!hatAnschreiben) {
      haupt = { aktion: "anschreiben", label: "Anschreiben", mitClaude: true };
    } else {
      haupt = { aktion: "beworben_eintragen", label: "Als beworben eintragen", mitClaude: false };
    }
  } else if (GESPRAECH.has(s)) {
    haupt = { aktion: "gespraech_vorbereiten", label: "Gespräch vorbereiten", mitClaude: true };
  } else if (s === "angebot") {
    haupt = { aktion: "angebot_pruefen", label: "Angebot prüfen", mitClaude: true };
  } else if (s === "abgelehnt") {
    haupt = { aktion: "aus_absage_lernen", label: "Aus der Absage lernen", mitClaude: true };
  } else if (NACHFASSEN.has(s) || (nachfassenFaellig && !ENDE.has(s))) {
    haupt = { aktion: "nachfassen", label: "Nachfassen", mitClaude: true };
  }
  // Ist die Bewerbung zu Ende (angenommen, zurückgezogen, abgelaufen, Arbeitgeber ausgefallen), gibt es keinen
  // nächsten Schritt - und die Leiste erfindet keinen.
  return { haupt, weitere };
}

/** Der Hauptknopf einer STELLE. `bewerbungId` gesetzt = es gibt schon eine Bewerbung dazu. */
export function stelleSchritt({ bewerbungId = "", beurteilt = false, hatAnzeige = false } = {}) {
  const weitere = [];
  let haupt;
  if (text(bewerbungId)) {
    haupt = { aktion: "zur_bewerbung", label: WEG_WORT.bewerbung, mitClaude: false };
  } else if (!beurteilt) {
    haupt = { aktion: "bewerten", label: "Stelle bewerten", mitClaude: true };
    weitere.push({ aktion: "bewerbung_anlegen", label: "Bewerbung anlegen", mitClaude: false });
  } else {
    haupt = { aktion: "bewerbung_anlegen", label: "Bewerbung anlegen", mitClaude: false };
  }
  if (hatAnzeige) weitere.push({ aktion: "anzeige_oeffnen", label: "Anzeige öffnen", mitClaude: false });
  return { haupt, weitere };
}

/** Der Hauptknopf eines KONTAKTS: nachfassen, wenn eine laufende Bewerbung dranhängt. */
export function kontaktSchritt({ name = "", laufendeBewerbung = false } = {}) {
  const wer = text(name);
  if (!laufendeBewerbung) return { haupt: null, weitere: [] };
  return {
    haupt: { aktion: "nachfassen_bei", label: wer ? `Nachfassen bei ${wer}` : "Nachfassen", mitClaude: true },
    weitere: [],
  };
}

// ── Die Leisten ──────────────────────────────────────────────────────────────────────────────────────

/**
 * @param {object} p
 * @param {string} p.zurueckLabel  z. B. „Stellen“ (die Liste) oder „Bewerbung: Titel“ (woher man kam)
 * @param {Array}  p.faelle        Ergebnis von `fall()` je Fall
 * @param {object} p.schritt       Ergebnis von `*Schritt()`
 */
function leiste({ art, zurueckLabel, faelle, schritt }) {
  return {
    art,
    zurueck: { label: `Zurück zu ${zurueckLabel}` },
    faelle: faelle.filter(Boolean),
    haupt: schritt?.haupt || null,
    weitere: schritt?.weitere || [],
  };
}

/** Die Leiste einer BEWERBUNG (Timeline). Alles optional; es erscheint, was es gibt. */
export function bewerbungLeiste({
  zurueckLabel = "Bewerbungen", jobHash = "", firma = "", kontakte = [], dokumente = [], termine = [],
  bewerbungId = "", status = "", hatLebenslauf = false, hatAnschreiben = false, nachfassenFaellig = false,
} = {}) {
  const faelle = [
    jobHash ? fall("stelle", "Stelle", [{ label: WEG_WORT.stelle, ziel: ziel(zuStelle(jobHash)) }]) : null,
    text(firma) ? fall("firma", "Firma", [{ label: text(firma), ziel: ziel(zuFirma({ firmaName: firma })) }]) : null,
    fall("kontakte", "Kontakte", (kontakte || []).map((k) => ({
      label: text(k.full_name || k.name) || "Person", ziel: ziel(zuKontakt(k.id || k.contact_id)),
    }))),
    fall("dokumente", "Dokumente", (dokumente || []).map((d) => ({
      label: text(d.filename || d.title) || "Dokument", ziel: ziel(zuDokument(d.id)),
    }))),
    fall("termine", "Termine", (termine || []).map((t) => ({
      label: [text(t.title) || "Termin", text(t.meeting_date).slice(0, 10)].filter(Boolean).join(" · "),
      ziel: ziel(zuTermin({ id: t.id, application_id: bewerbungId })),
    }))),
  ];
  return leiste({
    art: "bewerbung", zurueckLabel, faelle,
    schritt: bewerbungSchritt({ status, hatLebenslauf, hatAnschreiben, nachfassenFaellig }),
  });
}

/** Die Leiste einer STELLE. */
export function stelleLeiste({
  zurueckLabel = "Stellen", firma = "", bewerbungId = "", kontakte = [], beurteilt = false, hatAnzeige = false,
} = {}) {
  const faelle = [
    text(bewerbungId) ? fall("bewerbung", "Bewerbung", [{ label: WEG_WORT.bewerbung, ziel: ziel(zuBewerbung(bewerbungId)) }]) : null,
    text(firma) ? fall("firma", "Firma", [{ label: text(firma), ziel: ziel(zuFirma({ firmaName: firma })) }]) : null,
    fall("kontakte", "Kontakte", (kontakte || []).map((k) => ({
      label: text(k.full_name || k.name) || "Person", ziel: ziel(zuKontakt(k.id || k.contact_id)),
    }))),
  ];
  return leiste({ art: "stelle", zurueckLabel, faelle, schritt: stelleSchritt({ bewerbungId, beurteilt, hatAnzeige }) });
}

/** Die Leiste eines KONTAKTS. `bewerbungen` und `stellen` sind die Verknüpfungen (Kennung und Beschriftung). */
export function kontaktLeiste({
  zurueckLabel = "Kontakte", name = "", firma = "", bewerbungen = [], stellen = [], laufendeBewerbung = false,
} = {}) {
  const faelle = [
    fall("bewerbungen", "Bewerbungen", (bewerbungen || []).map((b) => ({
      label: text(b.label || b.title) || WEG_WORT.bewerbung, ziel: ziel(zuBewerbung(b.id)),
    }))),
    fall("stellen", "Stellen", (stellen || []).map((s) => ({
      label: text(s.label || s.title) || WEG_WORT.stelle, ziel: ziel(zuStelle(s.id || s.hash)),
    }))),
    text(firma) ? fall("firma", "Firma", [{ label: text(firma), ziel: ziel(zuFirma({ firmaName: firma })) }]) : null,
  ];
  return leiste({ art: "kontakt", zurueckLabel, faelle, schritt: kontaktSchritt({ name, laufendeBewerbung }) });
}

/**
 * Wie viele Klicks von der Leiste aus zu einem Fall: 1 mit einem Objekt, 2 mit Auswahl (Fall, dann Eintrag). Der
 * Wächter-Test (#1171, Baustein 6) zählt damit.
 */
export function klicksZu(leisteWert, fallId) {
  const f = (leisteWert?.faelle || []).find((x) => x.id === fallId);
  if (!f) return null;
  return f.anzahl === 1 ? 1 : 2;
}
