/**
 * Adressen von außen sind Text von außen — v1.7.145.
 *
 * Eine Adresse in einer Stelle, einer Bewerbung oder einem Termin stammt aus
 * einem Portal, einer Mail, einer Einladung oder einem Plugin. Als Link
 * geöffnet, führt `javascript:` im Ursprung des Dashboards Code aus (voller
 * Zugriff auf die lokale API); `file:` liest lokale Dateien. Erlaubt sind nur
 * http und https.
 *
 * Dieselbe Regel gilt im Server (services/web_adresse.py). Beide Fassungen
 * laufen gegen dieselbe Fallliste tests/fixtures/web_adresse_faelle.json.
 *
 * Framework-frei, damit der Node-Test sie prüfen kann.
 */

/** Eine absolute http(s)-Adresse mit Rechnernamen, ohne Steuerzeichen. */
export function istWebAdresse(url) {
  if (typeof url !== "string") return false;
  const s = url.trim();
  // Steuerzeichen mitten im Schema ("java\tscript:") überspringt der Browser
  // beim Lesen; so etwas ist nie eine Adresse.
  if (!s || /[\u0000-\u001f\u007f]/.test(s)) return false;
  let u;
  try {
    u = new URL(s);
  } catch {
    return false;
  }
  return (u.protocol === "http:" || u.protocol === "https:") && Boolean(u.host);
}

/**
 * Die Adresse, wenn sie http(s) ist, sonst `undefined`. Für `href={...}`:
 * ohne href ist ein Anker nicht klickbar, statt auf die eigene Seite zu
 * zeigen (ein leerer href würde sie neu laden).
 */
export function sichereAdresse(url) {
  return istWebAdresse(url) ? url.trim() : undefined;
}

/** `window.open` nur für http(s); sonst passiert nichts. */
export function oeffneAdresse(url, ziel = "_blank", merkmale = "noopener,noreferrer") {
  const adresse = sichereAdresse(url);
  return adresse ? window.open(adresse, ziel, merkmale) : null;
}
