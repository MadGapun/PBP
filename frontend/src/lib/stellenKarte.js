/**
 * Die Stellenkarte in einem Satz — G62 (#1087 C2, C3).
 *
 * Bis v1.7.133 trug eine Karte bis zu neun Abzeichen in Scoring-Sprache
 * (Kennung, Quellenschluessel, Fachwert-Daumen, Rahmen-Daumen, Pruefstand,
 * "Ungeprüft: 2", "Kein Pflichttreffer", "Punkte unsicher" ...). Jedes
 * davon stimmte, zusammen sagten sie nichts. Jetzt:
 *
 *   * EINE Kernaussage — wie gut passt die Stelle fachlich. Liegt ein
 *     gelesenes Urteil vor (#1007), ist es das Urteil; sonst der
 *     Fach-Daumen aus dem eigenen Bestand (#1052).
 *   * EIN Grund — das Wichtigste, was die Kernaussage einschraenkt,
 *     in Klartext.
 *   * der Rahmen-Daumen bleibt daneben (eigene Frage, eigene Farbe).
 *
 * Alles andere steht in den Details. Es wird nichts gerechnet: Daumen,
 * Urteil, Pruefstand und Datenguete kommen fertig vom Server.
 */

import { FACH, etikett as daumenEtikett, ton as daumenTon, titel as daumenTitel } from "./daumen.js";

export const URTEIL_TEXT = {
  EMPFOHLEN: "Empfohlen",
  BEDINGT: "Bedingt",
  NICHT_EMPFOHLEN: "Nicht empfohlen",
  NICHT_BEURTEILBAR: "Nicht beurteilt",
};

const URTEIL_TON = {
  EMPFOHLEN: "success",
  BEDINGT: "amber",
  NICHT_EMPFOHLEN: "danger",
};

// Klartext fuer die Dimensionen, die der Datenguete-Befund als
// ungeprueft meldet (#989). Die Beschreibung hat ihren eigenen Grund.
const DIMENSION_TEXT = {
  entfernung: "Entfernung",
  gehalt: "Gehalt",
  remote: "Remote-Anteil",
  stellenart: "Stellenart",
};

/**
 * Die Kernaussage der Karte: `{ text, ton, titel, urteil }`.
 * `urteil` ist wahr, wenn ein gelesenes Urteil dahintersteht — dann
 * fuehrt ein Klick zum Ergebnis (#948 AK 5).
 */
export function kernaussage(job) {
  const stand = job?.pruefstand;
  const urteil = job?.analyse?.urteil;
  if (stand?.art === "beurteilt" && urteil) {
    const text = `${URTEIL_TEXT[urteil] || "Beurteilt"}${stand.ueberholt ? " ⚠ überholt" : ""}`;
    return { text, ton: URTEIL_TON[urteil] || "neutral", titel: stand.text || "", urteil: true };
  }
  const marke = job?.fach_daumen;
  if (marke) {
    const angesehen = stand?.art === "gesichtet" ? " · schon angesehen" : "";
    return {
      text: daumenEtikett(marke, FACH),
      ton: daumenTon(marke),
      titel: `${daumenTitel(marke, FACH)}${angesehen}`,
      urteil: false,
      richtung: marke.richtung,
    };
  }
  return { text: "Fachlich noch nicht eingeordnet", ton: "neutral", titel: "", urteil: false };
}

/**
 * Der eine Grund daneben — in dieser Rangfolge, weil der erste jeden
 * weiteren entwertet: ohne Anzeigentext sagt keine Zahl etwas.
 * `datenguete` ist die Kurzmarke aus `lib/datenguete.js`.
 */
export function kartenGrund(job, datenguete = null) {
  const beschreibung = String(job?.description || "").trim();
  if (beschreibung.length < 50) {
    return Number(job?.score || 0) > 0
      ? "Beschreibung fehlt — Punkte unsicher"
      : "Ohne Beschreibung — noch nicht bewertet";
  }
  if (job?.muss_tor) return "Keiner deiner Pflichtbegriffe kommt vor";
  if (job?.pruefstand?.art === "beurteilt" && job?.pruefstand?.ueberholt) {
    return "Das Urteil ist älter als Profil oder Anzeige";
  }
  const offen = (datenguete?.ungeprueft || [])
    .filter((d) => d !== "beschreibung")
    .map((d) => DIMENSION_TEXT[d] || d);
  const eindeutig = [...new Set(offen)];
  if (eindeutig.length) return `Nicht angegeben: ${eindeutig.join(", ")}`;
  return "";
}

// Was die Anzeige ueber Arbeitsort und Vertrag sagt — Angaben, keine
// Bewertung. Eine Zeile statt fuenf Abzeichen.
const REMOTE_TEXT = { remote: "Remote", hybrid: "Hybrid", vor_ort: "Vor Ort" };

export function kartenFakten(job, { entfernung = "", form = "", umfang = "" } = {}) {
  const teile = [];
  if (entfernung) teile.push(entfernung);
  const remote = String(job?.remote_level || "");
  if (remote && remote !== "unbekannt") teile.push(REMOTE_TEXT[remote] || remote);
  if (form) teile.push(form);
  if (umfang) teile.push(umfang);
  if (job?.befristet) teile.push("Befristet");
  return teile.join(" · ");
}
