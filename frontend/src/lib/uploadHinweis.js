// Was nach dem Hochladen eines Dokuments zu sagen ist (#1170 U12).
//
// Der Server liest beim Hochladen eines PDFs ohne Text-Ebene (ein Scan) per Texterkennung (E19, #750), wenn die Komponente da ist, und
// meldet das Ergebnis im Feld `ocr` der Antwort: `durchgefuehrt`, `erforderlich` (Scan erkannt, Komponente fehlt — mit Angebot) oder
// `fehlgeschlagen`. Die Seite „Dokumente“ las dieses Feld nie: wer sein erstes eingescanntes Zeugnis hochlud, bekam ein Dokument
// ohne Text und keinen Hinweis, dass es dafür einen Weg gibt. Hier steht, was daraus gesagt wird; das Zeichnen macht die Seite.

/** @returns {{art: string, text: string, aktion?: string} | null} */
export function ocrHinweis(antwort, dateiname = "") {
  const ocr = antwort?.ocr;
  if (!ocr || typeof ocr !== "object") return null;
  const name = String(dateiname || antwort?.filename || "").trim() || "Das Dokument";
  if (ocr.ocr === "erforderlich") {
    return {
      art: "erforderlich",
      text: `„${name}“ ist ein Scan ohne Text. Mit der Texterkennung liest PBP solche Dokumente selbst — einmal einrichten unter Einstellungen › Erweiterungen.`,
      aktion: "texterkennung",
    };
  }
  if (ocr.ocr === "fehlgeschlagen") {
    return {
      art: "fehlgeschlagen",
      text: `Die Texterkennung hat bei „${name}“ nichts geliefert. Das Dokument ist trotzdem gespeichert; sein Text lässt sich mit Claude nachtragen.`,
    };
  }
  return null;
}

/** Die Hinweise zu mehreren Antworten, ohne Wiederholung (derselbe Satz für zwei Scans wäre nur Lärm). */
export function ocrHinweise(antworten) {
  const gesehen = new Set();
  const aus = [];
  for (const { antwort, name } of antworten || []) {
    const h = ocrHinweis(antwort, name);
    if (!h) continue;
    if (h.art === "erforderlich") {
      if (gesehen.has("erforderlich")) continue;
      gesehen.add("erforderlich");
    }
    aus.push(h);
  }
  return aus;
}
