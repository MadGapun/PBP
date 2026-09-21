/**
 * #1067 — das Auswerte-Skript fuer Google Jobs, gegen eine nachgebaute
 * Ergebnisseite.
 *
 * Gelesen wird die DATEI, die auch ausgeliefert wird
 * (job_scraper/google_jobs_extraction.js) — nicht eine Kopie. Ein Test
 * gegen eine zweite Fassung haette den gemeldeten Fall nicht gefunden.
 *
 * Der gemeldete Zustand am 21.09.2026: die alten Klassen-Selektoren
 * trafen nur noch die Suchreiter und lieferten 13 "Stellen" namens
 * KI-Modus, Alle, Bilder, News. Ohne Fehler.
 */
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import test from 'node:test';

const HIER = dirname(fileURLToPath(import.meta.url));
const SKRIPT = readFileSync(
  join(HIER, '../../../src/bewerbungs_assistent/job_scraper/google_jobs_extraction.js'),
  'utf-8',
);

/** Fuehrt das ausgelieferte Skript gegen eine gestellte Seite aus. */
function auswerten(seitentext, anker = []) {
  const document = {
    body: { innerText: seitentext },
    querySelectorAll: () => anker.map((a) => ({
      href: a.href,
      innerText: a.text,
      textContent: a.text,
      getAttribute: () => a.ariaLabel || '',
    })),
  };
  // Die Klammern sind noetig: das Skript beginnt mit Kommentarzeilen,
  // und `return` + Zeilenumbruch beendet die Anweisung (ASI) — ohne sie
  // kommt still `undefined` zurueck.
  // eslint-disable-next-line no-new-func
  return new Function('document', `return (\n${SKRIPT}\n);`)(document);
}

const SEITE = [
  'Google', 'Alle', 'Bilder', 'Jobs',
  'Offene Stellen',
  '(Senior) PLM Consultant (m/w/d) Schwerpunkt Teamcenter',
  'Musterbetrieb Nord GmbH',
  'Hamburg • über XING',
  'Senior Consultant - Product Lifecycle Management (m/w/d)',
  'Musterbetrieb Sued AG',
  'Hamburg • über LinkedIn',
  'Solution Architect PLM (m/w/d)',
  'Musterwerk West GmbH',
  'Hamburg • über Beispiel-Jobboard',
].join('\n');

test('liest Titel, Firma, Ort und Portal', () => {
  const r = auswerten(SEITE);
  assert.strictEqual(r.count, 3);
  assert.strictEqual(r.jobs[0].titel,
    '(Senior) PLM Consultant (m/w/d) Schwerpunkt Teamcenter');
  assert.strictEqual(r.jobs[0].firma, 'Musterbetrieb Nord GmbH');
  assert.strictEqual(r.jobs[0].ort, 'Hamburg');
  assert.strictEqual(r.jobs[0].portal, 'XING');
  assert.strictEqual(r.jobs[1].portal, 'LinkedIn');
});

test('nimmt auch die Schreibweise ohne Umlaut', () => {
  const r = auswerten('Offene Stellen\nTitel\nFirma\nHamburg • ueber XING');
  assert.strictEqual(r.count, 1);
  assert.strictEqual(r.jobs[0].portal, 'XING');
});

test('haengt den Link an, wenn ein Anker den Titel traegt', () => {
  const r = auswerten(SEITE, [
    { href: 'https://example.com/a', text: 'Solution Architect PLM (m/w/d)' },
  ]);
  const treffer = r.jobs.find((j) => j.titel.startsWith('Solution Architect'));
  assert.strictEqual(treffer.link, 'https://example.com/a');
  assert.strictEqual(r.ohne_link, 2);
});

test('ohne Anker bleibt der Link leer statt falsch', () => {
  const r = auswerten(SEITE);
  assert.ok(r.jobs.every((j) => j.link === ''));
  assert.strictEqual(r.ohne_link, 3);
});

test('ueberspringt die gesponserten Ergebnisse vor dem Stellenblock', () => {
  // Anzeigen stehen UEBER "Offene Stellen" und duerfen nicht mitkommen.
  const mitAnzeigen = [
    'Anzeige', 'PLM-Software vom Anbieter',
    'Beispiel Software GmbH',
    'Deutschland • über Anzeige',
    SEITE,
  ].join('\n');
  const r = auswerten(mitAnzeigen);
  assert.strictEqual(r.count, 3);
  assert.ok(r.jobs.every((j) => j.portal !== 'Anzeige'));
});

// ── Der gemeldete Fall: lieber ein Fehler als eine falsche Liste ────

test('meldet einen Fehler, wenn nur Navigation gefunden wird', () => {
  const nav = ['Offene Stellen', 'Suchfilter', 'Tools', 'Bilder • über Google']
    .join('\n');
  const r = auswerten(nav);
  assert.strictEqual(r.fehler, 'navigation_statt_stellen');
  assert.ok(r.hinweis.includes('Issue'));
});

test('meldet einen Fehler, wenn es gar keinen Stellenblock gibt', () => {
  const r = auswerten('Google\nAlle\nBilder\nKeine Ergebnisse');
  assert.strictEqual(r.fehler, 'kein_stellenblock');
});

test('meldet einen Fehler, wenn der Block da ist aber keine Karte passt', () => {
  const r = auswerten('Offene Stellen\nirgendein Text\nnoch einer');
  assert.strictEqual(r.fehler, 'keine_stellen_erkannt');
  assert.ok(r.zeilen_gesehen >= 3);
});

test('nennt den Nachlade-Hinweis, weil nur die ersten Karten da sind', () => {
  const r = auswerten(SEITE);
  assert.ok(r.hinweis.toLowerCase().includes('scrollen'));
});
