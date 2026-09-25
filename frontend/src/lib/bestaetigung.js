// G67 (#1087 H5): ein Bestaetigungsdialog fuer das ganze Dashboard.
//
// Bis v1.7.135 fragten 22 Stellen ueber window.confirm — ein
// Browserfenster, das je Browser anders aussieht und sich nicht gestalten
// laesst. Die App registriert beim Start die Funktion, die ihren Dialog
// oeffnet; jede Stelle ruft `bestaetigen(...)` und wartet auf die Antwort.
// Ohne registrierten Dialog lautet die Antwort "nein" — lieber nicht
// loeschen als ungefragt.

let anzeigen = null;

export function dialogRegistrieren(fn) {
  anzeigen = fn;
  return () => {
    if (anzeigen === fn) anzeigen = null;
  };
}

export function bestaetigen(optionen = {}) {
  const o = typeof optionen === "string" ? { text: optionen } : optionen;
  return anzeigen ? anzeigen(o) : Promise.resolve(false);
}
