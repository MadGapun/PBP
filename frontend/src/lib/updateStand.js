/**
 * Update-Stand in der Seitenleiste — #1134.
 *
 * Vorher fragte die Oberfläche genau einmal beim Laden der Seite, und der
 * Server merkte sich auch einen Fehlschlag eine Stunde lang: ein Netz, das
 * beim Start noch nicht bereit war, ließ "Update-Stand unbekannt" so lange
 * stehen. Jetzt sagt der Server, wann erneut gefragt werden darf
 * (`wieder_fragen_nach_s`), und die Oberfläche richtet sich danach.
 *
 * Framework-frei, damit der Node-Test sie prüfen kann.
 */

/** Nie dichter als alle 30 Sekunden fragen, egal was der Server sagt. */
export const FRAGE_MIN_MS = 30 * 1000;
/** Spätestens nach einer Stunde fragen (bei erfolgreicher Prüfung der Regelfall). */
export const FRAGE_MAX_MS = 60 * 60 * 1000;
/** Antwortet der Dashboard-Server selbst nicht, in fünf Minuten noch einmal. */
export const FRAGE_OHNE_ANTWORT_MS = 5 * 60 * 1000;

/** Wann die Oberfläche erneut fragt, in Millisekunden. */
export function naechsteFrageMs(daten) {
  if (!daten) return FRAGE_OHNE_ANTWORT_MS;
  const s = Number(daten.wieder_fragen_nach_s);
  if (!Number.isFinite(s) || s <= 0) return FRAGE_MAX_MS;
  return Math.min(FRAGE_MAX_MS, Math.max(FRAGE_MIN_MS, Math.round(s * 1000)));
}

/** Kurzer Grund aus `quellen_versucht`, fürs Tooltip. */
export function grundText(daten) {
  const versuche = Array.isArray(daten?.quellen_versucht) ? daten.quellen_versucht : [];
  if (!versuche.length) return "Keine Update-Quelle hat geantwortet.";
  const teile = versuche.map((v) => {
    const name = v?.name || "Quelle";
    if (v?.status && v.status !== 200) return `${name}: Antwort ${v.status}`;
    if (v?.fehler) return `${name}: keine Verbindung`;
    if (v?.ergebnis === "nichts_passendes") return `${name}: keine passende Version`;
    return `${name}: keine Antwort`;
  });
  return `Keine Update-Quelle hat geantwortet (${teile.join(", ")}).`;
}

/** Tooltip für "Update-Stand unbekannt": Grund und wann PBP erneut fragt. */
export function unbekanntTitel(daten) {
  const s = Number(daten?.wieder_fragen_nach_s);
  const minuten = Number.isFinite(s) && s > 0 ? Math.max(1, Math.round(s / 60)) : null;
  const spaeter = minuten
    ? ` PBP fragt in etwa ${minuten} ${minuten === 1 ? "Minute" : "Minuten"} erneut.`
    : "";
  return `${grundText(daten)} Ob es eine neue Version gibt, weiß PBP gerade nicht.${spaeter}`;
}
