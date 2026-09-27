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

/** Bytes lesbar: KB bis GB, eine Nachkommastelle ab MB. */
export function groesseText(bytes) {
  const b = Number(bytes) || 0;
  if (b < 1024 * 1024) return `${Math.max(1, Math.round(b / 1024))} KB`;
  if (b < 1024 * 1024 * 1024) return `${(b / (1024 * 1024)).toFixed(1).replace(".", ",")} MB`;
  return `${(b / (1024 * 1024 * 1024)).toFixed(1).replace(".", ",")} GB`;
}
