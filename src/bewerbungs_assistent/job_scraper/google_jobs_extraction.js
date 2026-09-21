(() => {
  // Google Jobs (udm=8) — Stellen aus der Ergebnisseite lesen (#1067).
  //
  // Bis v1.7.121 stand hier eine Liste von Klassennamen (Stand Mai 2026).
  // Google rotiert sie, und am 21.09.2026 traf der Selektor nur noch die
  // Suchreiter: 13 "Stellen" namens KI-Modus, Alle, Bilder, News, Videos,
  // Jobs, Homeoffice, Jobtyp, Veroeffentlicht. Die Funktion scheiterte
  // STILL — sie lieferte eine plausible Liste falscher Karten.
  //
  // Deshalb jetzt am sichtbaren TEXT verankert statt an Klassennamen: die
  // Zeile "<Ort> • über <Portal>" steht unter jeder Karte, und darueber
  // stehen Firma und Titel. Das Portal ist ein Zugewinn — es sagt, ueber
  // welche Quelle die Stelle laeuft, und taugt damit fuer den
  // Dublettenabgleich gegen Stellen, die PBP schon direkt hat.

  const NAV = [
    'KI-Modus', 'Alle', 'Bilder', 'News', 'Videos', 'Jobs', 'Kurze Videos',
    'Web', 'Finanzen', 'Shopping', 'Maps', 'Buecher', 'Bücher',
    'Jobwebsites', 'Homeoffice', 'Jobtyp', 'Veroeffentlicht',
    'Veröffentlicht', 'Suchfilter', 'Tools',
  ];
  const ANKER = ['Offene Stellen', 'Stellenangebote', 'Jobs in der Naehe',
                 'Jobs in der Nähe'];

  const text = (document.body && document.body.innerText) || '';
  let start = -1;
  let anker = '';
  for (const a of ANKER) {
    const i = text.indexOf(a);
    if (i >= 0 && (start < 0 || i < start)) { start = i; anker = a; }
  }
  if (start < 0) {
    return {
      fehler: 'kein_stellenblock',
      hinweis: 'Auf dieser Seite ist kein Stellenblock sichtbar. Ist udm=8 '
             + 'in der URL, und hat Google Treffer geliefert?',
      geprueft: ANKER,
    };
  }

  const zeilen = text.slice(start).split('\n').map((z) => z.trim());
  const jobs = [];
  // Alle Anker EINMAL einsammeln, damit der Link-Abgleich nicht je
  // Karte das ganze Dokument durchsucht.
  const anker_liste = Array.from(document.querySelectorAll('a[href]'))
    .map((a) => ({
      href: a.href,
      txt: ((a.innerText || a.textContent || '') + ' '
            + (a.getAttribute('aria-label') || '')).trim(),
    }))
    .filter((a) => a.txt);

  zeilen.forEach((zeile, k) => {
    // "Hamburg • über XING" — der Trenner steht in jeder Karte.
    const m = zeile.match(/^(.*?)\s+•\s+(?:über|ueber)\s+(.+)$/);
    if (!m || k < 2) return;
    const titel = zeilen[k - 2];
    const firma = zeilen[k - 1];
    if (!titel || !firma) return;
    const treffer = anker_liste.find((a) => a.txt.indexOf(titel) >= 0);
    jobs.push({
      titel,
      firma,
      ort: m[1].trim(),
      portal: m[2].trim(),
      link: treffer ? treffer.href : '',
    });
  });

  // Selbsttest: lieber ein Fehler als eine plausible falsche Liste.
  // Genau das war der gemeldete Zustand.
  const nav_treffer = jobs.filter((j) => NAV.indexOf(j.titel) >= 0);
  if (jobs.length && nav_treffer.length) {
    return {
      fehler: 'navigation_statt_stellen',
      hinweis: 'Die Auswertung hat Navigationselemente erwischt — die '
             + 'Seitenstruktur hat sich geaendert. Bitte als Issue melden '
             + 'statt die Liste zu uebernehmen.',
      beispiele: nav_treffer.slice(0, 5).map((j) => j.titel),
    };
  }
  if (!jobs.length) {
    return {
      fehler: 'keine_stellen_erkannt',
      hinweis: 'Der Stellenblock ist da, aber keine Karte hat die Form '
             + '"<Ort> • über <Portal>". Entweder ist die Seite noch nicht '
             + 'fertig geladen, oder die Struktur hat sich geaendert.',
      anker,
      zeilen_gesehen: zeilen.length,
    };
  }
  return {
    count: jobs.length,
    jobs,
    anker,
    ohne_link: jobs.filter((j) => !j.link).length,
    hinweis: 'Google laedt weitere Karten erst beim Scrollen nach. Fuer '
           + 'mehr als die sichtbaren Treffer: scrollen und erneut '
           + 'ausfuehren.',
  };
})()
