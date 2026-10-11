/**
 * #1189 — das Auswerte-Skript fuer die Projektsuche von jobtic, gegen eine nachgebaute Ergebnisseite.
 *
 * Gelesen wird die DATEI, die auch ausgeliefert wird (job_scraper/jobtic_extraction.js), nicht eine Kopie.
 *
 * Das Skript liest nur die Liste, die die Seite selbst mitliefert (JSON-Block und Karten als Datenattribute).
 * Es oeffnet keine Detailseite und kennt keine Ansprechpartner: ein Test unten stellt sicher, dass auch dann nichts
 * davon im Ergebnis steht, wenn die Seite es neben der Liste zeigt.
 *
 * Alle Titel, Orte und Adressen sind erfunden.
 */
import assert from 'node:assert';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import test from 'node:test';

const HIER = dirname(fileURLToPath(import.meta.url));
const SKRIPT = readFileSync(
  join(HIER, '../../../src/bewerbungs_assistent/job_scraper/jobtic_extraction.js'),
  'utf-8',
);

/** Fuehrt das ausgelieferte Skript gegen eine gestellte Seite aus. */
function auswerten({ block = null, karten = [], weiter = null } = {}) {
  const element = (daten) => ({
    textContent: daten.text,
    innerText: daten.text,
    href: daten.href,
    closest: (sel) => (sel === 'a[href]' && daten.anker ? { href: daten.anker } : null),
  });
  const document = {
    querySelector: (sel) => {
      if (sel === 'script[data-search-bulk-visible]') return block === null ? null : { textContent: block };
      if (sel === 'a[rel="next"]') return weiter ? { href: weiter } : null;
      return null;
    },
    querySelectorAll: (sel) => (sel === '[data-search-result-card]' ? karten.map(element) : []),
  };
  // Die Klammern sind noetig: das Skript beginnt mit Kommentarzeilen, und `return` + Zeilenumbruch beendet die
  // Anweisung (ASI) - ohne sie kommt still `undefined` zurueck.
  // eslint-disable-next-line no-new-func
  return new Function('document', `return (\n${SKRIPT}\n);`)(document);
}

const LISTE = JSON.stringify([
  { title: 'Keycloak Consultant (m/w/d) Remote / ZXXX1', url: 'https://jobtic.com/project/aaaaaaaaa1', itemable_type: 'App\\Models\\Project', itemable_id: 1 },
  { title: 'Cisco Netzwerkadministrator (m/w/d) in Musterstadt', url: 'https://jobtic.com/project/bbbbbbbbb2', itemable_type: 'App\\Models\\Project', itemable_id: 2 },
]);

const KARTEN = [
  { text: 'Keycloak Consultant (m/w/d) SKILLS Java Keycloak Hannover, DE ab sofort · Teilzeit · ca. 50% 95 % Remote',
    anker: 'https://jobtic.com/project/aaaaaaaaa1' },
  { text: 'Cisco Netzwerkadministrator (m/w/d) SKILLS Cisco LAN Musterstadt, DE ab sofort · Vollzeit Kein Remote gewünscht',
    anker: 'https://jobtic.com/project/bbbbbbbbb2' },
];

test('liest Titel und Adresse aus der Liste der Seite und haengt den Kartentext an', () => {
  const r = auswerten({ block: LISTE, karten: KARTEN });
  assert.strictEqual(r.count, 2);
  assert.strictEqual(r.quelle, 'jobtic');
  assert.strictEqual(r.jobs[0].titel, 'Keycloak Consultant (m/w/d) Remote / ZXXX1');
  assert.strictEqual(r.jobs[0].link, 'https://jobtic.com/project/aaaaaaaaa1');
  assert.ok(r.jobs[0].karte.includes('95 % Remote'));
  assert.ok(r.jobs[1].karte.includes('Kein Remote'));
  assert.strictEqual(r.naechste_seite, null);
});

test('nennt die naechste Seite, damit der Aufrufer sie zaehlen kann (Auflage: hoechstens zwei)', () => {
  const r = auswerten({ block: LISTE, karten: KARTEN, weiter: 'https://jobtic.com/search?type=projects&page=2' });
  assert.strictEqual(r.naechste_seite, 'https://jobtic.com/search?type=projects&page=2');
});

test('ohne Liste meldet es einen Fehler und uebernimmt nichts', () => {
  const r = auswerten({ block: null, karten: KARTEN });
  assert.strictEqual(r.count, 0);
  assert.deepStrictEqual(r.jobs, []);
  assert.ok(r.fehler && r.fehler.includes('Seitenstruktur'));
});

test('kaputter JSON-Block ist ein Fehler, kein Absturz', () => {
  const r = auswerten({ block: '{nicht json', karten: KARTEN });
  assert.strictEqual(r.count, 0);
  assert.ok(r.fehler);
});

test('nur Projektadressen zaehlen - Profile und Navigation nicht', () => {
  const block = JSON.stringify([
    { title: 'Erika Beispiel PHP Entwicklerin', url: 'https://jobtic.com/profile/erika-beispiel' },
    { title: 'Skill-Uebersicht', url: 'https://jobtic.com/skills/Python' },
    { title: 'Ein echtes Projekt (m/w/d)', url: 'https://jobtic.com/project/ccccccccc3' },
  ]);
  const r = auswerten({ block });
  assert.strictEqual(r.count, 1);
  assert.strictEqual(r.jobs[0].link, 'https://jobtic.com/project/ccccccccc3');
});

test('Kontaktdaten stehen nie im Ergebnis, auch wenn eine Karte sie zeigt', () => {
  // Das Skript liest den Kartentext - es darf aber keine Kontaktfelder erzeugen. Hier steht nichts davon in der
  // Struktur des Ergebnisses: nur titel, link und karte.
  const r = auswerten({ block: LISTE, karten: KARTEN });
  for (const job of r.jobs) {
    assert.deepStrictEqual(Object.keys(job).sort(), ['karte', 'link', 'titel']);
  }
  assert.ok(!('kontakt' in r) && !('ansprechpartner' in r));
});

test('E-Mail-Adressen und Telefonnummern im Kartentext werden entfernt', () => {
  const karte = { text: 'Projekt SKILLS Java Kontakt kontakt@example.com oder +49 (0) 123 4567890 Hannover',
    anker: 'https://jobtic.com/project/aaaaaaaaa1' };
  const r = auswerten({ block: LISTE, karten: [karte] });
  assert.ok(!r.jobs[0].karte.includes('@'));
  assert.ok(!/\d{3}\s*4567890/.test(r.jobs[0].karte));
  assert.ok(r.jobs[0].karte.includes('SKILLS Java'));
});

test('ein Startdatum mit Punkten bleibt im Kartentext', () => {
  const karte = { text: 'Projekt Start ab 01.06.2026 · 133 Std/Monat Bonn',
    anker: 'https://jobtic.com/project/aaaaaaaaa1' };
  const r = auswerten({ block: LISTE, karten: [karte] });
  assert.ok(r.jobs[0].karte.includes('01.06.2026'));
});

test('der Kartentext ist begrenzt', () => {
  const lang = { text: 'x'.repeat(5000), anker: 'https://jobtic.com/project/aaaaaaaaa1' };
  const r = auswerten({ block: LISTE, karten: [lang] });
  assert.ok(r.jobs[0].karte.length <= 600);
});
