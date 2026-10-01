// node frontend/src/lib/lokaleZeit.test.mjs — v1.7.146 (#1140)
import assert from "node:assert/strict";
import { lokalesDatum, lokaleDatumZeit, terminEnde } from "./lokaleZeit.js";

// Dieselbe Rechnung in mehreren Zeitzonen: das Ergebnis darf nicht von der
// Zone des Rechners abhängen. Node übernimmt `process.env.TZ` zur Laufzeit.
const ZONEN = ["Europe/Berlin", "UTC", "America/Los_Angeles", "Asia/Kolkata", "Pacific/Auckland"];

for (const zone of ZONEN) {
  process.env.TZ = zone;
  const hier = (text) => `${zone}: ${text}`;

  // Der gemeldete Fall: 14:00 und 60 Minuten ergibt 15:00, im Sommer wie im Winter.
  assert.equal(terminEnde("2026-10-01T14:00", 60), "2026-10-01T15:00", hier("Sommer"));
  assert.equal(terminEnde("2026-12-01T14:00", 60), "2026-12-01T15:00", hier("Winter"));
  // Über Mitternacht und mit krummer Dauer.
  assert.equal(terminEnde("2026-10-01T23:30", 60), "2026-10-02T00:30", hier("Mitternacht"));
  assert.equal(terminEnde("2026-10-01T09:15", 45), "2026-10-01T10:00", hier("45 Minuten"));
  assert.equal(terminEnde("2026-10-01T09:15", "90"), "2026-10-01T10:45", hier("Dauer als Text"));

  // Kein Ende, wo keines zu berechnen ist.
  assert.equal(terminEnde("2026-10-01", 60), null, hier("ganztägig"));
  assert.equal(terminEnde("2026-10-01T14:00", 0), null, hier("Dauer 0"));
  assert.equal(terminEnde("2026-10-01T14:00", null), null, hier("ohne Dauer"));
  assert.equal(terminEnde("", 60), null, hier("ohne Beginn"));
  assert.equal(terminEnde("kein Datum", 60), null, hier("unlesbar"));

  // Das lokale Datum: 00:30 Ortszeit bleibt der Tag, an dem es ist (UTC wäre der Vortag
  // in Zonen östlich von Greenwich).
  const halbEins = new Date(2026, 9, 1, 0, 30);
  assert.equal(lokalesDatum(halbEins), "2026-10-01", hier("00:30"));
  assert.equal(lokaleDatumZeit(halbEins), "2026-10-01T00:30", hier("00:30 mit Zeit"));
  const spaet = new Date(2026, 9, 1, 23, 59);
  assert.equal(lokalesDatum(spaet), "2026-10-01", hier("23:59"));
  assert.equal(lokaleDatumZeit(new Date(2026, 0, 5, 7, 5)), "2026-01-05T07:05", hier("Auffüllen"));
}

console.log("lokaleZeit: ok");
