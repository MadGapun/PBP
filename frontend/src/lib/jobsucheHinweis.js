// #1033: der Hinweis in der Navigation nach einer Jobsuche.
//
// Bis v1.7.90 stand dort nach JEDEM Lauf "Fertig — 0 neue Stellen": der
// Server las einen Schluessel, den kein Suchlauf schreibt. Die Regeln hier
// sind bewusst ein eigenes Modul mit eigenem Test, weil vier Zustaende
// auseinandergehalten werden muessen, die im Kaestchen alle gleich
// aussahen:
//
//   fertig mit Funden     -> die Anzahl
//   fertig ohne Funde     -> "keine neuen Stellen"
//   fehlgeschlagen        -> ein Hinweis darauf, NICHT "0 neue Stellen"
//   nicht gestartet       -> der Grund (keine Suchbegriffe, #967)
//
// Einzelne Timeouts faerben NICHT als Warnung: laufen 14 von 15 Quellen
// durch, ist der Lauf gelungen, und eine Quelle mit Dauer-Timeout wuerde
// das Kaestchen sonst bei jedem Lauf gelb machen. Sie stehen im Tooltip.

/** "32 von 44 ohne Volltext — PBP lädt ihn nach, die Bewertung folgt". */
export function volltextText(ohne, gesamt) {
  if (!ohne) return "";
  const von = typeof gesamt === "number" && gesamt >= ohne ? ` von ${gesamt}` : "";
  return `${ohne}${von} ohne Volltext — PBP lädt ihn nach, die Bewertung folgt`;
}

/** #1038: "12 Anzeigentexte nachgeladen, 3 folgen mit der Automatik". */
export function nachgeladenText(nachgeladen) {
  if (!nachgeladen) return "";
  const geholt = Number(nachgeladen.geholt) || 0;
  const offen = Number(nachgeladen.offen) || 0;
  const teile = [];
  if (geholt) teile.push(`${geholt} ${geholt === 1 ? "Anzeigentext" : "Anzeigentexte"} nachgeladen`);
  if (offen) teile.push(`${offen} folgen mit der Automatik`);
  return teile.join(", ");
}

export function jobsucheHinweis(last) {
  if (!last || !last.vorhanden) return null;

  const quellen = last.quellen || {};
  const quellenText = [
    quellen.ok ? `${quellen.ok} Quellen ok` : null,
    quellen.timeout ? `${quellen.timeout} im Timeout` : null,
    quellen.fehler ? `${quellen.fehler} mit Fehler` : null,
    quellen.uebersprungen ? `${quellen.uebersprungen} übersprungen` : null,
    // #1049: die Browser-Quellen zaehlt der interne Lauf gar nicht mit.
    // "14 Quellen ok" ohne sie ist dieselbe Klasse Fehler wie eine
    // Trefferzahl ohne Rohtrefferzahl (#813, #989).
    quellen.nur_browser
      ? `${quellen.nur_browser} übersprungen, nur über den Browser erreichbar`
      : null,
  ].filter(Boolean).join(", ");
  // #1096/#906: eine Stellenart, fuer die im Lauf keine Quelle lief
  const ohneQuelle = (last.stellentyp_ohne_quelle || []).length
    ? `für ${last.stellentyp_ohne_quelle.join(", ")} lief keine Quelle`
    : "";

  if (last.ergebnis === "fehlgeschlagen") {
    return {
      ton: "fehler",
      text: "Jobsuche fehlgeschlagen",
      titel: last.meldung || "Der letzte Suchlauf wurde abgebrochen.",
    };
  }
  if (last.ergebnis === "nicht_gestartet") {
    return {
      ton: "hinweis",
      text: "Jobsuche nicht gestartet",
      titel: last.meldung || "Es fehlen Suchbegriffe.",
    };
  }

  const neue = typeof last.neue_stellen === "number" ? last.neue_stellen : null;
  if (neue === null) {
    // Ein Lauf ohne Zahl ist "nicht bekannt", nicht "null gefunden".
    return { ton: "ok", text: "Jobsuche fertig", titel: last.meldung || "" };
  }
  // #1092 AK 6: was die lokale KI nach dem Lauf aussortiert hat — mit
  // dem Weg dorthin, damit sich ein Fehlurteil zurückholen lässt.
  const weg = typeof last.auto_aussortiert === "number" ? last.auto_aussortiert : 0;
  const wegText = weg > 0
    ? `${weg} von der lokalen KI aussortiert (zurückholen unter Stellen › Ausgeblendet)`
    : "";
  if (neue === 0) {
    return {
      ton: "ok",
      text: `Fertig — keine neuen Stellen${weg > 0 ? `, ${weg} aussortiert` : ""}`,
      titel: [wegText, quellenText, ohneQuelle].filter(Boolean).join(" · ")
        || "Der Suchlauf hat keine neuen Stellen gefunden.",
    };
  }

  const aktiv = typeof last.neu_aktiv === "number" ? last.neu_aktiv : null;
  const teile = [];
  // C97 (#1087 C8): die erste Liste wirkt fertig, fuellt sich aber erst
  // durch das Nachladen. Das steht jetzt im Hinweis selbst.
  const ohne = typeof last.ohne_volltext === "number" ? last.ohne_volltext : 0;
  if (ohne > 0) teile.push(volltextText(ohne, neue));
  const nach = nachgeladenText(last.nachgeladen);
  if (nach) teile.push(nach);
  if (aktiv !== null && aktiv !== neue) {
    teile.push(`${aktiv} davon in der Liste, ${neue - aktiv} sofort ausgeblendet`);
  }
  if (wegText) teile.push(wegText);
  if (quellenText) teile.push(quellenText);
  if (ohneQuelle) teile.push(ohneQuelle);
  return {
    ton: "ok",
    text: `Fertig — ${neue} ${neue === 1 ? "neue Stelle" : "neue Stellen"}${ohne > 0 ? `, ${ohne} ohne Volltext` : ""}${weg > 0 ? `, ${weg} aussortiert` : ""}`,
    titel: teile.join(" · "),
  };
}
