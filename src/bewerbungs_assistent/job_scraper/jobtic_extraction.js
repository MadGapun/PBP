// jobtic: Ergebnisseite der Projektsuche (#1189, B78). Gelesen wird, was die Seite selbst als Liste mitliefert.
//
// Die Seite traegt die sichtbaren Projekte als JSON-Block (`script[data-search-bulk-visible]`: Titel und Adresse) und
// jede Karte als `[data-search-result-card]` (Ort, Remote-Anteil, Auslastung, Skills als Text). Beides sind
// Datenattribute der Seite, keine Gestaltungsklassen. Fehlt der Block, meldet das Skript einen `fehler`, statt aus
// Navigation Stellen zu machen (wie google_jobs_extraction.js).
//
// Gelesen wird NUR die Liste: keine Detailseite, keine Ansprechpartner, keine Profile. Die Auflagen der Quelle
// (Handstart, hoechstens zwei Seiten je Begriff, Pausen) stehen in `quelle_handoff('jobtic', ...)`.
(() => {
  const leer = (fehler) => ({ quelle: 'jobtic', count: 0, jobs: [], naechste_seite: null, fehler });
  const text = (el) => ((el && (el.innerText || el.textContent)) || '').replace(/\s+/g, ' ').trim();
  // Kontaktdaten gehoeren nicht ins Ergebnis, auch wenn ein Kartentext sie je zeigen sollte (AGB § 5.3).
  const ohneKontakt = (s) => s
    .replace(/[\w.+-]+@[\w-]+(?:\.[\w-]+)+/g, '[Adresse entfernt]')
    .replace(/(?:\+|\b0)\d[\d\s()\/-]{7,}\d/g, '[Nummer entfernt]');  // Datum mit Punkten bleibt stehen

  let liste = [];
  const block = document.querySelector('script[data-search-bulk-visible]');
  if (block) {
    try { liste = JSON.parse(block.textContent || '[]'); } catch (e) { liste = []; }
  }
  if (!Array.isArray(liste)) liste = [];

  // Die Karte gehoert zu der Adresse ihres umschliessenden Ankers - Reihenfolge und Titel werden nicht geraten.
  const karten = {};
  for (const karte of Array.from(document.querySelectorAll('[data-search-result-card]'))) {
    const anker = karte.closest ? karte.closest('a[href]') : null;
    const href = anker ? String(anker.href || '') : '';
    if (href) karten[href.split('?')[0]] = ohneKontakt(text(karte)).slice(0, 600);
  }

  const jobs = [];
  for (const eintrag of liste) {
    const link = String((eintrag && eintrag.url) || '');
    const titel = String((eintrag && eintrag.title) || '').replace(/\s+/g, ' ').trim();
    if (!/\/project\/[a-z0-9]+/i.test(link) || !titel) continue;
    jobs.push({ titel, link, karte: karten[link.split('?')[0]] || '' });
  }
  if (!jobs.length) {
    return leer(liste.length
      ? 'Keine Projektadressen in der Liste der Seite - nichts übernehmen.'
      : 'Die Seite liefert keine Projektliste (Seitenstruktur geändert?) - nichts übernehmen, als Issue melden.');
  }
  const weiter = document.querySelector('a[rel="next"]');
  return { quelle: 'jobtic', count: jobs.length, jobs, naechste_seite: weiter ? String(weiter.href || '') || null : null };
})()
