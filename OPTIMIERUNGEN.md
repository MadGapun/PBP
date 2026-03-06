# PBP — Optimierungsplan
## Stand: 2026-03-06 (aktualisiert)

---

## v0.10.2 — Guided Experience (2026-03-06)

### Benutzerf&uuml;hrung
- **Smart Next-Steps**: Kontextabhaengige naechste Schritte basierend auf Profil-Vollstaendigkeit und Aktivitaet
  - Erkennt: fehlende Zusammenfassung, Positionen, Skills, Ausbildung, Dokumente, Quellen, Suche, Bewerbungen
  - Zwei Action-Typen: `dashboard` (direkter Button) und `prompt` (Claude Desktop Befehl)
  - Spezial-Hinweise bei 3+ Ablehnungen (Muster-Analyse) und anstehenden Interviews (Vorbereitung)
- **Onboarding Dokument-Upload**: Lebenslauf hochladen als 3. Option im Wizard (neben KI-gefuehrt und manuell)
- **Actionable Empty States**: Alle leeren Zustaende haben jetzt Aktions-Buttons statt nur Text-Hinweise
  - Stellen: "Jobsuche starten" + "Quellen einrichten"
  - Bewerbungen: "Passende Stellen finden" + "Bewerbung manuell erfassen"
  - Profil-Bereiche: Direkte Bearbeitungs-Buttons

### Technisch
- **Sauberes Beenden**: atexit/signal-Handler fuer SIGTERM, SIGINT, SIGBREAK (Windows)
  - uvicorn.Server direkt gemanaged (statt uvicorn.run()) fuer kontrollierten Shutdown
  - Datenbank-Verbindung wird sauber geschlossen

### Tests
- 7 neue Tests fuer Smart Next-Steps (Profil-Erstellung, Quellen, Ablehnungen, Interview, Action-Types)
- 92 Tests total, alle bestanden

---

## v0.10.1 — Profil-Isolation & Bugfixes (2026-03-06)

### Kritische Bugfixes
- **Profil loeschen repariert**: Aktives Profil kann jetzt geloescht werden (wechselt automatisch zu anderem Profil)
- **Profil-Switcher repariert**: Dropdown wird jetzt immer angezeigt (auch bei nur 1 Profil)
- **Delete-Modal repariert**: Name-Vergleich funktioniert jetzt (String-Escaping-Bug behoben)
- **Daten-Isolation zwischen Profilen**: Jobs und Bewerbungen sind jetzt per `profile_id` getrennt

### Neue Features
- **Factory Reset**: "Kompletter Reset" Button in Gefahrenzone fuer saubere Neuinstallation
- **Extraktions-Historie leeren**: Button zum Bereinigen veralteter Extraktions-Eintraege
- **Runtime-Log Viewer**: Betriebslog direkt im Dashboard einsehbar (Einstellungen-Tab)
- **Cascade-Delete**: Profil-Loeschung entfernt alle zugehoerigen Daten (Positionen, Skills, Dokumente, Bewerbungen, Jobs)

### Schema & API
- Schema v7 → v8: `profile_id` Spalte auf `applications` und `jobs` Tabellen
- Neue API-Endpoints: `/api/reset`, `/api/extraction-history`, `/api/logs`
- Alle Job-/Bewerbungs-Queries filtern jetzt nach aktivem Profil

### Tests
- 30 Tests fuer v0.10.x (Schema v8, Profil-Isolation, Cascade-Delete, Factory-Reset)
- 85 Tests total, alle bestanden (8 Export-Tests uebersprungen wegen fehlender Abhaengigkeiten)

---

## v0.10.0 — UX & Scraper Overhaul (2026-03-05)

### Neue Features
- **Onboarding-Wizard**: 4-Schritt Wizard fuer neue User (Profil, Quellen, Suche, Ergebnisse)
- **Bewerbungs-Wizard**: 5-Schritt Wizard pro Stelle (Fit-Analyse, CV, Anschreiben, Interview, Erfassung)
- **Gehalt auf Stellenkarten**: Immer sichtbar — gelb fuer echte Daten, grau fuer Schaetzung
- **Gehalts-Schaetzungs-Engine**: Automatische Extraktion (7 Regex-Patterns) + Schaetzung via Lookup-Tabellen
- **Quellen-Banner**: Persistenter Hinweis wenn keine Quellen aktiv
- **Such-Reminder**: Farbcodierte Anzeige der letzten Suche (gruen/gelb/rot)
- **Hint-System**: Per-Hint dismissbar + globaler Expertenmodus
- **Profil loeschen**: Gefahrenzone mit Namens-Bestaetigung
- **Gehaltsfilter**: Dropdown im Stellen-Tab (ab 50k/65k/80k/100k)
- **Tooltips**: Alle KI-Befehle mit Erklaerung was passiert

### Scraper-Reparatur
- **StepStone**: Komplett auf Playwright umgestellt (war httpx+BS4)
- **Indeed**: Komplett auf Playwright umgestellt mit Anti-Bot-Massnahmen
- **Monster**: Komplett auf Playwright umgestellt
- **XING**: Selektoren repariert, nutzt jetzt link-basierte Extraktion
- **Freelancermap**: Playwright-Fallback wenn httpx leer zurueckkommt
- **LinkedIn**: Bestehende Implementierung verifiziert

### Schema & API
- Schema v6 → v7: `salary_estimated` Spalte, `user_preferences` Tabelle
- 3 neue API-Endpoints: `/api/user-preferences/{key}`, `/api/search-status`
- `gehalt_extrahieren()` nutzt jetzt shared Engine mit Schaetzungs-Fallback
- `jobsuche_workflow` Prompt mit Schritt-Erklaerungen und Wiederholungshinweis

### Intelligente Dokumenten-Erkennung
- **Auto-Typ-Erkennung**: Dateiname + Textinhalt → Lebenslauf/Anschreiben/Zeugnis/Zertifikat
- **Firmen-Erkennung**: Aus Dateiname extrahiert (z.B. "Anschreiben_Siemens_2026-03.pdf")
- **Bewerbungs-Matching**: Automatische Zuordnung zu bestehenden Bewerbungen
- **Auto-Create**: Neue Bewerbung direkt beim Upload erstellen

### Tests
- 22 neue Tests fuer v0.10.0 (Schema v7, Salary-Extraction, User-Preferences)
- 79 Tests total, alle bestanden

---

## Prioritaet 1: Kritisch (vor Produktiveinsatz)

### OPT-001: Path Traversal absichern ✓ ERLEDIGT
**Datei**: dashboard.py (Ordner-Import)
**Problem**: `folder_path` wird nicht validiert → beliebige Dateien lesbar
**Loesung**: Blockierte Systempfade + Path.resolve()
**Status**: Implementiert (Prompt 041)

### OPT-002: Scoring-Logik vereinheitlichen ✓ ERLEDIGT
**Dateien**: job_scraper/__init__.py + dashboard.py
**Problem**: calculate_score() und Fit-Analyse duplizieren Logik
**Loesung**: Gemeinsame fit_analyse() + _parse_weights() in job_scraper/__init__.py
**Status**: Implementiert (Prompt 041) — 60 Zeilen → 5 Zeilen in dashboard.py

### OPT-003: Error-Handling im Frontend
**Datei**: dashboard.html
**Problem**: API-Fehler werden verschluckt, kein Feedback an User
**Loesung**: Toast-Notifications + try/catch bei allen api() Calls
**Aufwand**: 2 Std
**Status**: offen

### OPT-004: Form-Validierung
**Dateien**: dashboard.html + dashboard.py
**Problem**: Keine Client- oder Server-Validierung (leere Pflichtfelder moeglich)
**Loesung**: Required-Felder pruefen, Datumsformat validieren
**Aufwand**: 2 Std
**Status**: offen

---

## Prioritaet 2: Wichtig (Qualitaet)

### OPT-005: Unbenutzte Dependencies entfernen ✓ ERLEDIGT
**Datei**: pyproject.toml
**Problem**: aiosqlite, jinja2, pydantic deklariert aber nicht verwendet
**Loesung**: Aus core dependencies entfernt, optionale Gruppen [scraper]/[docs]/[all]
**Status**: Implementiert (Prompt 041)

### OPT-006: Cascading Deletes ✓ ERLEDIGT
**Datei**: database.py
**Problem**: Position loeschen laesst verwaiste Projects zurueck
**Loesung**: ON DELETE CASCADE fuer projects→positions, application_events→applications
           ON DELETE SET NULL fuer documents→positions
**Status**: Implementiert (Prompt 042)

### OPT-007: UUID-Helper ✓ ERLEDIGT
**Datei**: database.py
**Problem**: `import uuid; str(uuid.uuid4())[:8]` 5x wiederholt
**Loesung**: `_gen_id()` Hilfsfunktion, 7 Stellen ersetzt
**Status**: Implementiert (Prompt 041)

### OPT-008: Scraper-Keywords konfigurierbar
**Dateien**: alle Scraper
**Problem**: DEFAULT_SEARCHES/KEYWORDS hardcoded (PLM-spezifisch)
**Loesung**: Keywords aus search_criteria DB lesen
**Aufwand**: 2 Std
**Status**: offen

### OPT-009: Ladeanimationen
**Datei**: dashboard.html
**Problem**: Kein visuelles Feedback bei API-Calls
**Loesung**: Spinner/Skeleton bei Laden, Disabled-Buttons bei Submit
**Aufwand**: 1 Std
**Status**: offen

---

## Prioritaet 3: Nice-to-have

### OPT-010: Paginierung fuer Applications
**Dateien**: dashboard.py + dashboard.html
**Problem**: Alle Bewerbungen auf einmal geladen
**Loesung**: limit/offset Parameter + "Mehr laden" Button
**Aufwand**: 2 Std
**Status**: offen

### OPT-011: Test-Suite erstellen
**Neue Dateien**: tests/test_database.py, tests/test_scoring.py
**Problem**: Null Test-Coverage
**Loesung**: Basis-Tests fuer DB-CRUD und Scoring
**Aufwand**: 3 Std
**Status**: offen

### OPT-012: Dashboard Port konfigurierbar ✓ ERLEDIGT
**Dateien**: dashboard.py
**Problem**: Port 8200 hardcoded
**Loesung**: BA_DASHBOARD_PORT Umgebungsvariable + Parameter in start_dashboard()
**Status**: Implementiert (Prompt 042)

### OPT-013: File-Size Limit bei Upload ✓ ERLEDIGT
**Datei**: dashboard.py
**Problem**: Kein Limit, theoretisch unbegrenzte Dateien hochladbar
**Loesung**: Max 50MB, Pruefung vor Speicherung, HTTP 413 bei Ueberschreitung
**Status**: Implementiert (Prompt 042)

---

## Zusaetzliche Fixes (Prompt 041-042)

### FIX-001: get_data_dir() — BA_DATA_DIR auf allen Plattformen
**Problem**: Windows ignorierte BA_DATA_DIR Umgebungsvariable
**Loesung**: BA_DATA_DIR wird auf allen Plattformen zuerst geprueft

### FIX-002: pyproject.toml readme Feld
**Problem**: readme = "README.md" — Datei existierte nicht
**Loesung**: Inline text statt Dateiverweis

### FIX-003: FastMCP Constructor
**Problem**: fastmcp neueste Version akzeptiert kein description/version kwarg
**Loesung**: Ueberfluessige kwargs entfernt

### FIX-004: CV-Generator "Ort: None Hamburg"
**Problem**: PLZ=None wurde als String "None" angezeigt
**Loesung**: `or ''` Pattern fuer optionale Felder

### FIX-005: test_demo.py Windows-Kompatibilitaet
**Problem**: Hardcoded Linux-Pfad, nicht plattformuebergreifend
**Loesung**: Relative Pfade, tempfile.gettempdir(), anonymisierte Demodaten

---

## Zusammenfassung

| Status | Anzahl | Tickets |
|--------|--------|---------|
| ✓ Erledigt | 8 | OPT-001, 002, 005, 006, 007, 012, 013 + 5 Fixes |
| Offen | 5 | OPT-003, 004, 008, 009, 010, 011 |
| Releases | 11 | v0.1.0 bis v0.10.2 |

**Naechste Empfehlung**:
1. OPT-003 (Error-Handling) — direkte User-Auswirkung
2. OPT-011 (Tests) — Qualitaetssicherung
3. OPT-008 (Scraper-Keywords) — Flexibilitaet
