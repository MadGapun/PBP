// Wege durch PBP (#1171, G85): wohin ein Klick auf eine Stelle, Bewerbung, Firma, Person, ein Dokument, einen Termin
// oder eine Aufgabe führt — an EINER Stelle. Vorher kannte jede Seite ihre eigenen Sprünge (36 Aufrufe von `navigateTo`
// mit je eigenem Zuschnitt), und was ein Sprung brauchte, stand nur dort: eine Firma führte nur auf die Liste, ein
// Kontakt nur auf eine Suche, eine Stelle nur zu einem Scrollen. Hier steht, was ein Klick MEINT: das Objekt öffnen.
//
// Alles Reine, nichts Gezeichnetes: die Seiten rufen `zuBewerbung(id)` usw. und reichen das Ergebnis an
// `navigateTo(ziel.seite, ziel.intent)` der App. `null` heißt: ohne Kennung kein Sprung (der Aufrufer zeigt dann
// keinen Knopf, statt einen toten zu zeichnen).

function kennung(wert) {
  const s = String(wert ?? "").trim();
  return s || "";
}

/** Eine Stelle öffnen — ihre Details, nicht nur die Liste (der Sprung scrollt und hebt hervor, `oeffnen` öffnet). */
export function zuStelle(jobHash) {
  const h = kennung(jobHash);
  return h ? { seite: "stellen", intent: { focus: "job", jobHash: h, oeffnen: true } } : null;
}

/** Eine Bewerbung öffnen — ihre Timeline. */
export function zuBewerbung(bewerbungId) {
  const id = kennung(bewerbungId);
  return id ? { seite: "bewerbungen", intent: { applicationId: id, focus: "timeline" } } : null;
}

/** Eine Person öffnen — ihre Karte, nicht nur die Liste. */
export function zuKontakt(kontaktId) {
  const id = kennung(kontaktId);
  return id ? { seite: "kontakte", intent: { ansicht: "kontakte", kontaktId: id } } : null;
}

/** Eine Firma öffnen: mit Kennung eines Firmen-Eintrags (fi_…) oder mit dem Namen. */
export function zuFirma({ firmaId = "", firmaName = "" } = {}) {
  const id = kennung(firmaId);
  if (id) return { seite: "kontakte", intent: { ansicht: "firmen", firmaId: id } };
  const name = kennung(firmaName);
  return name ? { seite: "kontakte", intent: { ansicht: "firmen", firmaName: name } } : null;
}

/** Ein Dokument ansehen: die Dokumente-Seite, das Dokument ist hervorgehoben. */
export function zuDokument(dokumentId) {
  const id = kennung(dokumentId);
  return id ? { seite: "dokumente", intent: { dokumentId: id } } : null;
}

/** Ein Termin: gehört er zu einer Bewerbung, ist deren Timeline die Antwort (dort stehen Termine samt Nachbereitung). */
export function zuTermin({ id = "", application_id = "", bewerbung_id = "" } = {}) {
  const bew = zuBewerbung(application_id || bewerbung_id);
  if (bew) return bew;
  const t = kennung(id);
  return t ? { seite: "kalender", intent: { terminId: t } } : { seite: "kalender", intent: null };
}

/** Eine Aufgabe oder Nachfassung: gehört sie zu einer Bewerbung, ist deren Timeline der nächste Schritt. */
export function zuAufgabe({ id = "", bewerbung_id = "" } = {}) {
  const bew = zuBewerbung(bewerbung_id);
  if (bew) return bew;
  const a = kennung(id);
  return { seite: "aufgaben", intent: a ? { aufgabeId: a } : null };
}

/** Eine Mail öffnen: ihr Fenster auf der Dokumente-Seite (Absender, Text, „Bewerbung zuordnen“) — gleich, ob sie zu einer Bewerbung gehört. */
export function zuMail(mailId) {
  const id = kennung(mailId);
  return id ? { seite: "dokumente", intent: { mailId: id } } : null;
}

/** Ein Abschnitt der Profil-Seite (Skills …); `suche` ist der Name, den die Liste dort zeigen soll (nur wo sie filtern kann). */
export function zuProfil(abschnitt, suche = "") {
  const intent = { abschnitt: kennung(abschnitt) };
  if (kennung(suche)) intent.suche = kennung(suche);
  return { seite: "profil", intent };
}

/**
 * Was ein Klick auf einen Treffer der Suche oben im Dashboard meint (#1177, G88): das Objekt öffnen. Gebaut aus denselben
 * Wegen wie jeder andere Klick im Dashboard — kein eigener Zuschnitt für die Suche (bis v1.7.154 tat der Klick nichts).
 * Ein Treffer ohne Ziel (eine Art, die es nicht gibt, oder ohne Kennung) liefert eine `meldung`: der Mensch erfährt, dass
 * nichts aufgeht, statt vor einer Stille zu stehen.
 */
export function zuSuchtreffer(treffer) {
  const art = String(treffer?.kind || "");
  let ziel = null;
  if (art === "application") ziel = zuBewerbung(treffer.id);
  else if (art === "job") ziel = zuStelle(treffer.id);
  else if (art === "document") ziel = zuDokument(treffer.id);
  else if (art === "meeting") {
    ziel = zuTermin({ id: treffer.id, application_id: treffer.application_id });
    // ein Termin mit Bewerbung öffnet deren Timeline — am Abschnitt „Termine“, nicht oben
    if (ziel?.seite === "bewerbungen") ziel = { ...ziel, intent: { ...ziel.intent, abschnitt: "termine" } };
  } else if (art === "email") ziel = zuMail(treffer.id);
  else if (art === "skill") ziel = zuProfil("skills", treffer.title);
  return ziel || { meldung: "Zu diesem Treffer gibt es keine Ansicht, die sich öffnen ließe." };
}

/**
 * Wohin eine Zeile des Blocks „Offen“ im Dashboard führt: eine Nachfassung, ein Termin oder eine Aufgabe, die eine
 * Bewerbung kennt, öffnet DIESE Bewerbung (bis v1.8.0-beta.16 führte jede Zeile nur auf die Aufgaben-Seite).
 * Ein Termin ohne Bewerbung führt in den Kalender, eine Aufgabe ohne Bewerbung auf die Aufgaben-Seite.
 */
export function offenZeileZiel(eintrag) {
  if (!eintrag) return null;
  if (eintrag.herkunft === "termin") return zuTermin({ id: eintrag.id, bewerbung_id: eintrag.bewerbung_id });
  const bew = zuBewerbung(eintrag.bewerbung_id);
  return bew || { seite: "aufgaben", intent: null };
}

const ART_WORT = { application: "Bewerbung", job: "Stelle", meeting: "Termin", company: "Firma" };

/**
 * Eine Verknüpfung eines Kontakts (Zeile aus `contact_links`, vom Server um `ziel_*` ergänzt) als Satz und Ziel:
 * „Bewerbung: Leiter Fertigung bei Muster GmbH“ statt des rohen „application“. Ohne Ziel (das Ding gibt es nicht mehr)
 * bleibt es Text.
 */
export function verknuepfungZeile(link) {
  const art = String(link?.target_kind || "");
  const wort = ART_WORT[art] || art || "Verknüpfung";
  const titel = kennung(link?.ziel_titel);
  const firma = kennung(link?.ziel_firma);
  const rolle = kennung(link?.role);
  let text = wort;
  if (titel) text += `: ${titel}`;
  if (firma && art !== "company") text += ` bei ${firma}`;
  let ziel = null;
  if (link?.ziel_gefunden !== false) {
    if (art === "application") ziel = zuBewerbung(link.target_id);
    else if (art === "job") ziel = zuStelle(link.target_id);
    else if (art === "meeting") ziel = zuTermin({ id: link.target_id, application_id: link.ziel_bewerbung_id });
    else if (art === "company") ziel = zuFirma({ firmaName: titel });
  }
  const sprungWort = SPRUNG_WORT[{ application: "bewerbung", job: "stelle", meeting: "termin", company: "firma" }[art]] || "";
  return { text, rolle, ziel, art, sprungWort, vorhanden: link?.ziel_gefunden !== false };
}

/** Die Wörter der Sprünge, überall gleich: „Zur Stelle“, „Zur Bewerbung“ … */
export const SPRUNG_WORT = {
  stelle: "Zur Stelle",
  bewerbung: "Zur Bewerbung",
  firma: "Zur Firma",
  kontakt: "Zum Kontakt",
  dokument: "Zum Dokument",
  termin: "Zum Termin",
  aufgabe: "Zur Aufgabe",
};

/**
 * Die Abschnitte des Dialogs „Timeline“ für die Sprungleiste, in der Reihenfolge, in der sie im Dialog stehen.
 * `kennung` ist das `data-abschnitt` im Dialog; Abschnitte, die es nicht gibt, lässt die Leiste weg.
 */
export const TIMELINE_ABSCHNITTE = [
  { kennung: "status", label: "Status" },
  { kennung: "stelle", label: "Stelle" },
  { kennung: "dokumente", label: "Dokumente" },
  { kennung: "personen", label: "Personen" },
  { kennung: "aufgaben", label: "Aufgaben" },
  { kennung: "termine", label: "Termine" },
  { kennung: "verlauf", label: "Verlauf" },
];

/** Aus den vorhandenen Abschnitten (Kennungen im Dialog) die Einträge der Leiste, in fester Reihenfolge. */
export function sprungleiste(vorhanden) {
  const da = new Set(vorhanden || []);
  return TIMELINE_ABSCHNITTE.filter((a) => da.has(a.kennung));
}
