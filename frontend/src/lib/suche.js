// Treffer der Suche oben im Dashboard (#1177): wohin ein Klick auf einen Treffer führt — an EINER Stelle.
//
// Bis v1.7.154 tat der Klick nichts: die Suche lieferte Adressen im Format `#bewerbungen?id=…`, die das Dashboard nicht
// liest (es liest `#seite/kennung`), und der Klick setzte nur die Adresse. Jetzt gibt es zu jeder Trefferart ein Ziel:
// eine Seite und eine Absicht (`intent`), die die Seite liest und in das geöffnete Objekt verwandelt.
//
// Jeder Schlüssel einer Absicht (`dokumentId`, `terminId`, `mailId`, `abschnitt`, …) braucht einen LESER auf einer Seite
// (`intent.<schluessel>`); `test_jede_absicht_hat_einen_leser_auf_einer_seite` prüft das.
//
// Alles Reine, nichts Gezeichnet: `navigateTo(ziel.seite, ziel.intent)` der App führt es aus. Ein Treffer ohne Ziel liefert
// eine `meldung`: der Mensch erfährt, dass nichts aufgeht, statt vor einer Stille zu stehen.

function kennung(wert) {
  const s = String(wert ?? "").trim();
  return s || "";
}

/** Eine Bewerbung öffnen — ihre Timeline. */
export function zuBewerbung(bewerbungId) {
  const id = kennung(bewerbungId);
  return id ? { seite: "bewerbungen", intent: { applicationId: id, focus: "timeline" } } : null;
}

/** Eine Stelle öffnen — ihre Details, nicht nur die Liste (der Sprung scrollt und hebt hervor, `oeffnen` öffnet). */
export function zuStelle(jobHash) {
  const h = kennung(jobHash);
  return h ? { seite: "stellen", intent: { focus: "job", jobHash: h, oeffnen: true } } : null;
}

/** Ein Dokument ansehen: die Dokumente-Seite, das Dokument ist aufgeklappt. */
export function zuDokument(dokumentId) {
  const id = kennung(dokumentId);
  return id ? { seite: "dokumente", intent: { dokumentId: id } } : null;
}

/** Eine Mail öffnen: ihr Fenster auf der Dokumente-Seite (Absender, Text, „Bewerbung zuordnen“) — gleich, ob sie zu einer Bewerbung gehört. */
export function zuMail(mailId) {
  const id = kennung(mailId);
  return id ? { seite: "dokumente", intent: { mailId: id } } : null;
}

/** Ein Termin: gehört er zu einer Bewerbung, ist deren Timeline die Antwort; sonst öffnet er sich im Kalender. */
export function zuTermin({ id = "", application_id = "", bewerbung_id = "" } = {}) {
  const bew = zuBewerbung(application_id || bewerbung_id);
  if (bew) return bew;
  const t = kennung(id);
  return t ? { seite: "kalender", intent: { terminId: t } } : null;
}

/** Ein Abschnitt der Profil-Seite (Skills …); `suche` ist der Name, den die Liste dort zeigen soll (nur wo sie filtern kann). */
export function zuProfil(abschnitt, suche = "") {
  const intent = { abschnitt: kennung(abschnitt) };
  if (kennung(suche)) intent.suche = kennung(suche);
  return { seite: "profil", intent };
}

/**
 * Was ein Klick auf einen Treffer der Suche oben im Dashboard meint: das Objekt öffnen.
 * `treffer` ist eine Zeile aus `/api/search` (`kind`, `id`, `title`, `application_id` …).
 */
export function zuSuchtreffer(treffer) {
  const art = String(treffer?.kind || "");
  let ziel = null;
  if (art === "application") ziel = zuBewerbung(treffer.id);
  else if (art === "job") ziel = zuStelle(treffer.id);
  else if (art === "document") ziel = zuDokument(treffer.id);
  else if (art === "meeting") ziel = zuTermin({ id: treffer.id, application_id: treffer.application_id });
  else if (art === "email") ziel = zuMail(treffer.id);
  else if (art === "skill") ziel = zuProfil("skills", treffer.title);
  return ziel || { meldung: "Zu diesem Treffer gibt es keine Ansicht, die sich öffnen ließe." };
}
