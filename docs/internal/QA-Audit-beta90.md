# QA-Audit beta.90 — Selbsttest, Wiki-Drift, Workflow-Lücken

> Stand: 2026-06-02 · Auditor: Claude (autonomer 8h-QA-Lauf)
> Ground-Truth (aus Code geladen): **171 Tools, 24 Prompts, Schema v45,
> 1612 Tests collected (1611 passed + 1 skipped)**, Frontend beta.90.

Dieses Dokument hält den Stand des Selbsttests fest: was getestet wurde,
was funktioniert, welche Doku veraltet war und welche Features
undokumentiert blieben. Es ist der technische Beleg hinter dem
beta.91-Doku-Sync.

---

## 1. Was wurde getestet (und funktioniert)

### QA-A — Volle Test-Suite + Migration auf Real-DB-Kopie
- `pytest` komplett: **1611 passed, 1 skipped** (collect: 1612).
- Migration v43→v45 auf einer **Kopie** der echten User-DB
  (`C:\Temp\claude\qa`, NIE das Original unter AppData):
  - 202 Dokumente / 92 Bewerbungen / 1616 Stellen erhalten.
  - `documents.lifecycle` korrekt auf `aktiv` defaultet.
  - `tasks`-Tabelle + `dismiss_reasons.is_active` angelegt.
  - Automatisches Backup vor Migration in `data/backups/` erzeugt.
  - Idempotent: zweiter Lauf ohne Änderung, keine Fehler.

### QA-B — REST-Endpoints (FastAPI TestClient, In-Process)
`tools/qa_rest_smoke.py` gegen die migrierte Kopie: **10 OK, 0 FAIL**.
- `GET/POST /api/dismiss-reasons`, `PATCH /api/dismiss-reasons/{id}`
  (deaktivieren + umbenennen) — #663 C20.
- `GET/POST /api/applications/{id}/tasks`,
  `POST /api/tasks/{id}/complete|reopen`, `DELETE /api/tasks/{id}`,
  `GET /api/tasks` — #666 D19.
- `POST /api/follow-ups/{id}/complete` Routing vorhanden (404 auf
  Fake-ID beweist Endpoint) — #665 D18.

### QA-C — MCP-Registry
- Server lädt sauber, `mcp.get_tools()` → **171**, `get_prompts()` → **24**.
- `test_mcp_registry.py` grün (harter Count-Assert als Sync-Forcer).

**Fazit Selbsttest:** Backend, Migration und REST-Schicht der
beta.78–90-Welle funktionieren auf echten Daten. Render-Level-Test des
Frontends bleibt dem User-Test vorbehalten (bewusst akzeptiert).

---

## 2. Wiki-Drift — „funktioniert das, was dokumentiert ist?"

Das Wiki war auf dem Stand **beta.74** eingefroren, während der Code bei
**beta.90** steht. Gefundene veraltete Zahlen (alle im selben Sync
korrigiert):

| Stelle | Wiki (alt) | Wahrheit | Status |
|---|---|---|---|
| Tool-Count | 139 / 152 | **171** | gefixt |
| Prompt-Count | 23 | **24** | gefixt |
| Schema-Version | v42 (teils v43/v44) | **v45** | gefixt |
| Pre-Release-Stamp | beta.74 | **beta.90** | gefixt |
| Test-Count | 1441 | **1611** | gefixt |

Betroffene Seiten: `Home`, `Architektur`, `MCP-Tools`, `Master-Plan`,
`Plan-MCP-Layer`, `Plan-Datenbasis`, `Workflows`,
`Master-Plan-Optimierung`. Historische Anker („seit beta.74", „in
beta.74 eingeführt") bleiben bewusst stehen — nur **Status**-Angaben
(„aktuell", „Stand", „Pre-Release") wurden nachgezogen.

`CLAUDE.md` selbst war ebenfalls stale (Header „zuletzt beta.74",
„Schema v42, MCP-Tools 138") → Header + neuer Stand-Block aktualisiert.

---

## 3. Undokumentierte Features (beta.78–90)

Die komplette Feature-Welle nach beta.74 fehlte user-seitig. Nachgezogen:

| Feature | Issue | Beta | Wiki-Seite (neu/ergänzt) |
|---|---|---|---|
| Dokument-Lifecycle (aktiv/archiviert/veraltet) | #657/#658 | 79–80 | Tab-Dokumente |
| Dokument-Routing-Plan + Korrespondenz-Abschluss | #643 | 80 | Tab-Dokumente, MCP-Tools |
| TODOs/Tasks pro Bewerbung | #666 | 85/90 | Tab-Bewerbungen, MCP-Tools |
| Ablehnungsgründe-Editor (Bewertung-Tab) | #663 | 85/90 | Tab-Einstellungen |
| MINUS-Keywords (weiche Abwertung) | #667 | 84/89 | Suchkriterien, Tab-Profil |
| Wiedergänger-Erkenner (KI-frei Ebene 0) | #671 | 86 | Tab-Stellen, MCP-Tools |
| `stelle_reaktivieren` | #664 | 82 | Tab-Stellen, MCP-Tools |
| Follow-up-Direkt-Abhaken | #665 | 85/90 | Tab-Bewerbungen |
| Duplikat-Erkennung verfeinert (Titel-Sim + force) | #670 | 87 | Stellen-Qualitaet |
| Elwosa KI-freies Safety-Net | #669 | 88 | Elwosa |

Neue MCP-Tools seit beta.74 (Auszug, jetzt in MCP-Tools dokumentiert):
`dokument_archivieren`, `dokument_reaktivieren`, `dokument_status_setzen`,
`dokumente_bulk_archivieren`, `dokumente_korrespondenz_abschliessen`,
`dokumente_routing_plan_erstellen`, `dokument_aktion_ausfuehren`,
`todo_anlegen`, `todo_erledigen`, `todo_reaktivieren`, `todos_anzeigen`,
`stelle_reaktivieren`, `stelle_wiedergaenger_pruefen`.

---

## 4. Workflow-Analyse (Jobsuche → Bewerbung → Doku → Nachfass)

Durchgespielt am Code + Tool-Inventar. Befunde:

**Funktioniert durchgängig:**
- Jobsuche → Score → `fit_analyse` (mit Verdict EMPFOHLEN/BEDINGT/
  NICHT_EMPFOHLEN, Minus-Hits, Wiedergänger-Kontext) → `stelle_bewerten`.
- Bewerbung anlegen → Status-Lifecycle → Auto-Veralten verknüpfter Docs.
- Doku-Upload → Auto-Klassifikation → Routing-Plan → Profil/Verknüpfung.
- Nachfass-Planung (mit Dubletten-Check #665) → Direkt-Abhaken.

**Raue Kanten (als Verbesserungs-Kandidaten notiert, nicht blind
umgesetzt):**
1. Whitelist der Ablehnungsgründe lebt an zwei Orten (CLAUDE.md-Liste +
   `ABLEHNUNGSGRUENDE` im Code + dynamische User-Gründe). Single Source
   of Truth via `verfuegbare_gruende`-Response ist dokumentiert, aber
   Claude-seitige Disziplin bleibt manuell.
2. Wiedergänger Ebene 1 (Ollama) ist bewusst deferred — Ebene 0 (DB) +
   Ebene 2 (fit_analyse) sind live. In Tab-Stellen als „KI-frei" klar
   markiert, damit keine falsche Erwartung entsteht.
3. Tasks (#666) und Follow-ups (#665) sind zwei getrennte Konzepte mit
   ähnlicher UI — in Tab-Bewerbungen jetzt klar abgegrenzt (Task =
   freie ToDo, Follow-up = terminierte Nachfass-Aktion).

---

## 5. Nächste Schritte

- [x] Stale Zahlen Wiki-weit korrigieren (QA-E).
- [x] beta.78–90-Features user-seitig dokumentieren (QA-E).
- [x] CLAUDE.md Header + Stand-Block aktualisieren.
- [x] Master-Plan: beta.78–90-Items auf ✅, QA-Block ergänzen.
- [ ] Release beta.91 (reiner Doku-/Sync-Release, additiv, kein Code-Risiko).
