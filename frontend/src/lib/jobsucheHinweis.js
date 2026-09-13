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

export function jobsucheHinweis(last) {
  if (!last || !last.vorhanden) return null;

  const quellen = last.quellen || {};
  const quellenText = [
    quellen.ok ? `${quellen.ok} Quellen ok` : null,
    quellen.timeout ? `${quellen.timeout} im Timeout` : null,
    quellen.fehler ? `${quellen.fehler} mit Fehler` : null,
    quellen.uebersprungen ? `${quellen.uebersprungen} übersprungen` : null,
  ].filter(Boolean).join(", ");

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
  if (neue === 0) {
    return {
      ton: "ok",
      text: "Fertig — keine neuen Stellen",
      titel: quellenText || "Der Suchlauf hat keine neuen Stellen gefunden.",
    };
  }

  const aktiv = typeof last.neu_aktiv === "number" ? last.neu_aktiv : null;
  const teile = [];
  if (aktiv !== null && aktiv !== neue) {
    teile.push(`${aktiv} davon in der Liste, ${neue - aktiv} sofort ausgeblendet`);
  }
  if (quellenText) teile.push(quellenText);
  return {
    ton: "ok",
    text: `Fertig — ${neue} ${neue === 1 ? "neue Stelle" : "neue Stellen"}`,
    titel: teile.join(" · "),
  };
}
