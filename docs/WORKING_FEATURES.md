# WORKING FEATURES

Dieser Ist-Stand ist die Referenz fuer `scripts/smoke_test.py` und die
Regression-Kontrolle vor jedem Release (#498). Vor einem neuen Release
wird diese Liste abgeglichen — was von `[x]` auf `[ ]` wandert, ist
eine Regression und blockt den Release bzw. bekommt ein Issue.

**Konvention:**
- `[x]` = funktioniert bestaetigt (manuell getestet oder Smoke-Test gruen)
- `[ ]` = bekannt kaputt (mit Issue-Referenz)
- `[-]` = deprecated / nicht mehr Bestandteil

---

## v1.5.8 (Stand 21.04.2026, eingefroren als Baseline fuer v1.6.0)

### Installation / Setup
- [x] `INSTALLIEREN.bat` / `INSTALLIEREN.command` richten PBP ein
- [x] `_selftest.py` laeuft durch
- [x] `release_check.py` verifiziert Versions-Konsistenz

### Datenbank / Profil
- [x] SQLite-DB wird unter `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db` angelegt
- [x] Profile anlegen, wechseln, loeschen
- [x] Profil-Isolation (Kalender-Kategorien pro Profil, Fix #451)
- [x] Profil-Export/-Import als JSON

### Bewerbungen
- [x] `add_application` → Event-Log initial
- [x] `update_application_status` → neues Event
- [x] `get_applications(status=...)` mit Filter
- [x] `count_applications` fuer Dashboard-Widgets
- [x] `delete_application` loescht Events + Follow-ups + Bewerbung

### Dokumente
- [x] Drag-and-Drop Upload im Dashboard
- [x] Duplikat-Pruefung beim `.eml`-Import (409 Conflict, Fix #476)
- [x] `add_document` + `get_document` + `delete_document`
- [x] Auto-Link ueber Firmennamen (`_auto_link_documents`)
- [x] DOCX-Export fuer Lebenslauf und Anschreiben als Default (#473)

### Jobs / Stellen
- [x] `save_jobs` / `get_active_jobs` funktionieren
- [x] Hays-Scraper liefert Treffer (Beispiel „PLM Hamburg")
- [x] Manueller Stellen-Import via `stelle_manuell_anlegen`
- [ ] Bundesagentur-Scraper: Timeout-Probleme (#489)
- [ ] LinkedIn-Scraper: deprecated, haendischer Workflow (#488, #490)
- [ ] StepStone-Scraper: Bot-Detection, haendischer Workflow (#488, #501)
- [ ] Google Jobs: ueber JobSpy broken (#490), Alternative via Chrome (#501)

### Termine / Kalender
- [x] `add_meeting` + `get_upcoming_meetings`
- [x] Kalender-Filter-Chips (Kategorien, Fix #451)
- [x] Kollisionserkennung + ICS-Export (v1.5.0)
- [ ] Termin-spezifischer Prep-Vorschlag bei Interview-Termin (#457)
- [ ] An Thunderbird/Outlook-Kalender senden (#481 — neu in v1.6.0)

### Follow-Ups
- [x] `add_follow_up` / `get_pending_follow_ups`
- [x] `complete_follow_up` / `dismiss_open_followups_for_application`
- [ ] Auto-Hinfaellig bei Ablehnung/Absage (#493 — neu in v1.6.0)
- [ ] Auto-Nachfrage nach Interview (#494 — neu in v1.6.0)

### Dashboard
- [x] Bewerbungen-Liste laedt
- [x] Status-Filter greift
- [x] Heartbeat-Anzeige
- [x] Tagesimpulse aus `content/tagesimpulse.json`
- [x] mailto-Antworten-Button in Bewerbungs-Timeline (#477)
- [ ] Filter-Zaehler inkonsistent bei Dokumenten (#492)
- [ ] „Analysieren"-Button kopiert keinen Prompt (#491)
- [ ] Zweitgespraech-Termin im Follow-up-Widget fehlt (#495)
- [ ] Dashboard-Filter-Links „Lange keine Antwort" / „Nachfragen" / „Interview vorbereiten" (#483, #484, #485)
- [ ] Dark/Light-Mode (#475)

### E-Mails
- [x] `.eml`-Import, Pattern-Matching fuer Recruiter-Antworten
- [x] `body_text` aus HTML-Mails ableiten (Fix #476)
- [x] Duplikat-Schutz 5-Minuten-Fenster
- [ ] Posteingang fuer unzugeordnete E-Mails (#459)

### Export / Berichte
- [x] Profil-Report exportieren
- [x] Lebenslauf-Export (DOCX default, PDF optional)
- [x] Anschreiben-Export (DOCX default)
- [x] Bewerbungsbericht-Export

### MCP / Server
- [x] FastMCP-Server startet, registriert Tools
- [x] MCP-Registry Test grün (`test_mcp_registry.py`)

### Smoke-Test
- [x] `scripts/smoke_test.py` 12/12 gruen (Beta.1)

### Test-Harness (pytest)
- [x] 412 Tests gruen
- [ ] 28 Tests rot in `test_v154_writeback.py` / `test_v157_flow_completion.py`
      (FastMCP-API-Upgrade: `call_tool` → `add_tool`, pre-existing auf main)

---

## Update-Konvention

1. Vor einem neuen Release: Abschnitt fuer die neue Version *kopieren*, nicht ueberschreiben.
2. Pro geaenderte Zeile: wenn `[ ]` → `[x]`, das Issue verlinken.
3. Wenn `[x]` → `[ ]`: **Release blockieren oder Issue anlegen**, niemals stillschweigend.
4. Deprecated (`[-]`) nur setzen, wenn ein CHANGELOG-Eintrag im „Removed"-Abschnitt steht.
