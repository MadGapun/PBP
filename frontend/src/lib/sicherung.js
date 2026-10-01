// #1098: Texte der Sicherungs-Karte. Eigenes Modul mit Node-Test, weil
// "vor 3 Stunden" und "vor 9 Tagen" dieselbe Zahl in zwei Einheiten sind
// und eine zu alte Sicherung anders klingen soll als eine frische.

/** Das Alter einer Sicherung in Worten; `alt` ab 7 Tagen. */
export function alterText(tage) {
  if (tage === null || tage === undefined) {
    return { text: "Noch keine Sicherung vorhanden", alt: true };
  }
  const stunden = Math.round(tage * 24);
  let text;
  if (stunden < 1) text = "Letzte Sicherung: gerade eben";
  else if (stunden < 24) text = `Letzte Sicherung: vor ${stunden} ${stunden === 1 ? "Stunde" : "Stunden"}`;
  else {
    const t = Math.floor(tage);
    text = `Letzte Sicherung: vor ${t} ${t === 1 ? "Tag" : "Tagen"}`;
  }
  return { text, alt: tage >= 7 };
}

/**
 * Was die Karte zum juengsten Sicherungsversuch sagt (v1.7.146, #1142).
 * `null`, wenn nichts zu melden ist: der Versuch ist durch eine neuere
 * Sicherung ueberholt (`aktuell` falsch), laeuft noch oder ist glatt
 * gelungen. `art`: "fehler" oder "hinweis" (gesichert, aber nicht alles).
 */
export function versuchText(versuch) {
  if (!versuch || versuch.aktuell === false) return null;
  const nachricht = String(versuch.nachricht || "").trim();
  if (versuch.status === "fehler") {
    return {
      art: "fehler",
      text: nachricht
        ? `Die letzte Sicherung ist fehlgeschlagen: ${nachricht}`
        : "Die letzte Sicherung ist fehlgeschlagen.",
    };
  }
  if (versuch.status === "fertig" && nachricht && nachricht !== "Sicherung angelegt") {
    return { art: "hinweis", text: `Die letzte Sicherung ist angelegt, aber nicht vollständig: ${nachricht}` };
  }
  return null;
}

/** Bytes lesbar: KB bis GB, eine Nachkommastelle ab MB. */
export function groesseText(bytes) {
  const b = Number(bytes) || 0;
  if (b < 1024 * 1024) return `${Math.max(1, Math.round(b / 1024))} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
  return `${(b / (1024 * 1024 * 1024)).toFixed(1).replace(".", ",")} GB`;
}
