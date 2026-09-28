/**
 * Bewerbungs-Formular — G58 (#1087 C6, D7).
 *
 * Beide Dialoge ("Neue Bewerbung" im Bewerbungen-Tab und "Bewerbung aus
 * Stelle anlegen" im Stellen-Tab) beschrifteten ihre Felder mit den
 * Datenbank-Schluesseln `title`, `company`, `url`, `applied_at`. Das ist
 * das zentrale Eingabeformular des Produkts. Die Beschriftungen stehen
 * jetzt hier, damit beide Dialoge dieselben Woerter tragen.
 *
 * Die Vorgabe ist "Ich will mich bewerben" (`in_vorbereitung`): wer nur
 * vorbereiten will und versehentlich "beworben" anlegt, startet den
 * Auto-Nachfass. Umgekehrt kostet ein vergessenes Umstellen nur einen
 * Klick (#981).
 */

export const BEWERBUNG_ANLEGEN = "Bewerbung anlegen";

export const BEWERBUNG_FELDER = [
  { key: "title", label: "Stellentitel", placeholder: "z. B. Sachbearbeiter/in Einkauf" },
  { key: "company", label: "Firma", placeholder: "z. B. Musterbetrieb GmbH" },
  { key: "url", label: "Link zur Anzeige", placeholder: "https://…" },
];

export const BEWORBEN_AM_LABEL = "Beworben am";

export const VORGABE_STATUS = "in_vorbereitung";

/** Heutiges Datum als JJJJ-MM-TT in Ortszeit (nicht UTC, #1032). */
export function heuteIso(jetzt = new Date()) {
  const j = jetzt.getFullYear();
  const m = String(jetzt.getMonth() + 1).padStart(2, "0");
  const t = String(jetzt.getDate()).padStart(2, "0");
  return `${j}-${m}-${t}`;
}

/**
 * Das Datumsfeld zeigt sich erst, wenn die Bewerbung raus ist — eine
 * Bewerbung in Vorbereitung hat kein Bewerbungsdatum.
 */
export function brauchtBewerbungsdatum(status) {
  return Boolean(status) && status !== "in_vorbereitung";
}

/**
 * Nutzlast fuer POST /api/applications. Eine Bewerbung in Vorbereitung
 * traegt kein Datum (wie bisher im Stellen-Dialog, #981). Fehlt bei einer
 * abgeschickten Bewerbung das Datum, entfaellt der Schluessel, damit der
 * Server "jetzt" setzt statt eine leere Zeichenkette zu speichern.
 */
export function bewerbungNutzlast(entwurf) {
  const daten = { ...entwurf };
  if (!brauchtBewerbungsdatum(daten.status)) {
    daten.applied_at = "";
  } else if (!daten.applied_at) {
    delete daten.applied_at;
  }
  return daten;
}

/**
 * #1094: Was nach dem Anlegen passiert ist, in einem Satz — der Server
 * setzt jetzt dieselben Folgen wie Claude (Stelle aussortiert, Erinnerung).
 * Wer das nicht liest, sucht die Stelle danach in der Liste.
 */
export function angelegtMeldung(antwort) {
  const teile = ["Bewerbung angelegt."];
  if (antwort?.stelle_aussortiert) teile.push("Die Stelle ist aus der aktiven Liste genommen.");
  if (antwort?.nachfass_in_tagen) {
    teile.push(`Erinnerung zum Nachfassen in ${antwort.nachfass_in_tagen} Tagen.`);
  }
  return teile.join(" ");
}

/**
 * #1094: Eine vermutete Dublette kommt als 409 mit der vorhandenen
 * Bewerbung. Liefert den Satz fuer den Hinweis — oder null, wenn der
 * Fehler keine Dublette ist.
 */
export function dublettenHinweis(fehler) {
  const d = fehler?.status === 409 ? fehler?.payload?.duplikat : null;
  if (!d) return null;
  const was = [d.bestehend_titel, d.bestehend_firma].filter(Boolean).join(" bei ");
  return `Diese Bewerbung gibt es vermutlich schon${was ? `: „${was}“` : ""}. `
    + "Nur anlegen, wenn es wirklich eine eigene, neue Bewerbung ist.";
}
