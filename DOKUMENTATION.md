# PBP — Persoenliches Bewerbungs-Portal
## Komplette Projektdokumentation | Stand: 2026-03-10 | v0.14.0

---

## 1. Was ist PBP?

PBP ist ein **KI-gestuetzter Bewerbungs-Assistent**, der als Plugin in **Claude Desktop** laeuft.
Er hilft Menschen bei der Jobsuche — egal ob Berufseinsteiger, erfahrene Fachkraft,
Freelancer, Wiedereinsteigerin oder Karrierewechsler. Kein Coaching noetig, kein
Computerwissen vorausgesetzt.

Der Assistent kann:

- Ein strukturiertes Profil aufbauen (wie ein lockeres Gespraech, nicht wie ein Formular)
- Stellenangebote automatisch aus **9 Jobportalen** sammeln
- Stellen per Scoring-System bewerten (passt/passt nicht)
- Bewerbungen verwalten und den Status tracken
- **Lebenslaeufe und Anschreiben als PDF/DOCX exportieren**
- Sich auf Vorstellungsgespraeche vorzubereiten

Der User spricht mit Claude in natuerlicher Sprache. Claude nutzt im Hintergrund
die PBP-Tools, um Daten zu speichern, Jobs zu suchen und Dokumente zu erstellen.

**Zusaetzlich** gibt es ein **Web-Dashboard** (Browser-Oberflaeche auf Port 8200),
ueber das der User seine Daten auch visuell verwalten kann.

---

## 2. Was kann es? — Feature-Uebersicht

### 2.1 Profilverwaltung ✓ vollstaendig

| Feature | Beschreibung | Wie |
|---------|-------------|-----|
| **Profil erstellen** | Name, Kontakt, Adresse, Gehaltsvorstellungen, Arbeitsmodell | Claude-Dialog oder Dashboard |
| **Dialog-Ersterfassung** | 4-Phasen Interview: lockerer Einstieg → strukturierte Erfassung → CV-basierte Praeferenzen → Review | Claude-Dialog ("Ersterfassung starten") |
| **Profil-Review** | Zusammenfassung mit Vollstaendigkeits-Check, gezielte Korrekturen | Claude-Dialog ("Profil ueberpruefen") |
| **Berufserfahrung** | Positionen mit Firma, Titel, Zeitraum, Technologien | Claude-Dialog oder Dashboard |
| **STAR-Projekte** | Situation → Task → Action → Result pro Position | Claude-Dialog oder Dashboard |
| **Ausbildung** | Studium, Zertifikate, Weiterbildungen | Claude-Dialog oder Dashboard |
| **Skills** | Kompetenzen mit Kategorie und Level (1-10) | Claude-Dialog oder Dashboard |
| **Dokumente** | Upload von PDF, DOCX, TXT mit automatischer Textextraktion | Dashboard (max 50MB) |
| **Ordner-Import** | Ganzen Ordner auf einmal importieren | Dashboard |
| **Informelle Notizen** | Persoenliche Motivation, Wuensche, Vorlieben | Claude-Dialog |
| **Praeferenzen** | Stellentyp, Arbeitsmodell, Gehalt, Reisebereitschaft, Umzug | Claude-Dialog |

**Besonderheit**: Der Dialog ist fuer ALLE Lebenssituationen ausgelegt:
- Studenten und Berufseinsteiger (wenig Erfahrung ist ok)
- Langjaehrige Mitarbeiter (20 Jahre in einer Firma = wertvolle Tiefe)
- Haeufige Wechsler (Vielfalt = breite Kompetenz)
- Freelancer und Selbstaendige (Projektvielfalt = Flexibilitaet)
- Wiedereinsteigerinnen nach Familienpause (Lebenserfahrung zaehlt)
- Menschen mit ungewoehnlichen Karrierewegen
- Alle, die kein Geld fuer teures Karriere-Coaching haben

---

### 2.2 Jobsuche ✓ vollstaendig (9 Quellen)

| Quelle | Methode | Login | Status |
|--------|---------|-------|--------|
| **Bundesagentur fuer Arbeit** | REST API | Nein | ✓ |
| **StepStone** | Browser-Automation (Playwright) | Nein | ✓ |
| **Hays** | Sitemap + JSON-LD | Nein | ✓ |
| **Freelancermap** | httpx + Playwright Fallback | Nein | ✓ |
| **Freelance.de** | HTML-Scraping | Nein | ✓ |
| **Indeed** | Browser-Automation (Playwright) | Nein | ✓ |
| **Monster** | Browser-Automation (Playwright) | Nein | ✓ |
| **LinkedIn** | Browser-Automation (Playwright) | Ja | ✓ |
| **XING** | Browser-Automation (Playwright) | Ja | ✓ |

**Quellenverwaltung**: Im Dashboard unter Einstellungen kann jede Quelle
einzeln aktiviert/deaktiviert werden. Alle Quellen sind standardmaessig
deaktiviert — der User waehlt, welche er nutzen moechte.

**Dynamische Keywords**: Suchbegriffe kommen aus den Suchkriterien in der
Datenbank, nicht mehr aus dem Code. Jeder Scraper bekommt quellenspezifisch
formatierte Keywords (URL-Slugs fuer StepStone, Query-Parameter fuer
Freelancermap, etc.).

**Scoring-System** (konfigurierbare Gewichtungen):
- MUSS-Keywords: Je 2 Punkte (Standard). Kein MUSS-Treffer → Score = 0
- PLUS-Keywords: Je 1 Punkt (Standard)
- AUSSCHLUSS-Keywords: Stelle wird komplett ausgeblendet
- Remote/Hybrid: +2 Bonus
- Naehe (<80km): +2 Bonus
- Ferne (>200km): -3 Malus

---

### 2.3 Bewerbungsmanagement ✓ vollstaendig

| Feature | Beschreibung |
|---------|-------------|
| **3 Bewerbungsarten** | Mit Dokumenten, Elektronisch, Ueber Portal |
| **Dynamische Felder** | Je nach Art: Lebenslauf-Variante, Portal-Name, Kontaktperson |
| **Status-Tracking** | offen → beworben → eingangsbestaetigung → interview → zweitgespraech → angebot / abgelehnt / zurueckgezogen |
| **Timeline** | Jeder Statuswechsel mit Datum + Notizen |
| **Follow-up-Alerts** | Dashboard zeigt Bewerbungen >7 Tage ohne Reaktion |
| **Statistiken** | Interview-Rate, Angebot-Rate, nach Status |

---

### 2.4 PDF/DOCX-Export ✓ vollstaendig

| Export | Format | Beschreibung |
|--------|--------|-------------|
| **Lebenslauf** | PDF | Professionelles Layout mit DejaVu/Helvetica Font, Sektionen, Footer |
| **Lebenslauf** | DOCX | Word-Dokument mit Calibri, Heading-Styles, Bullet-Listen |
| **Anschreiben** | PDF | Formatierter Brief mit Absender, Datum, Betreff |
| **Anschreiben** | DOCX | Word-Brief mit rechtsbuendigem Absender |

**Technologie**: fpdf2 fuer PDF (reines Python, keine System-Dependencies wie
Cairo/Pango — wichtig fuer Windows!), python-docx fuer DOCX.

---

### 2.5 Dashboard (Browser-UI) ✓ vollstaendig

Das Dashboard hat **5 Tabs** und laeuft auf `http://localhost:8200`:

**Tab 1 — Dashboard (Uebersicht)**
- Statistik-Kacheln: Aktive Stellen, Bewerbungen, Interview-Rate, Angebot-Rate
- Letzte Bewerbungen + letzte Stellenfunde
- Follow-up-Alerts
- Status-Balkendiagramm

**Tab 2 — Profil**
- Persoenliche Daten (bearbeitbar)
- Berufserfahrung mit STAR-Projekten
- Ausbildung + Zertifikate
- Skills nach Kategorie
- Dokumentenbibliothek

**Tab 3 — Stellen**
- Suchfilter (Freitext, Festanstellung/Freelance, Quelle)
- Job-Karten mit Score-Balken, Remote-Badge, Entfernungs-Badge
- Fit-Analyse-Button pro Stelle

**Tab 4 — Bewerbungen**
- Status-Filter
- Bewerbungstabelle mit Timeline
- CV-Export als PDF/DOCX
- Bewerbungsformular mit 3 Bewerbungsarten

**Tab 5 — Einstellungen**
- MUSS/PLUS/AUSSCHLUSS-Keywords
- Regionale Praeferenzen
- Gewichtungs-Regler
- Blacklist-Verwaltung
- **Quellenverwaltung** (9 Quellen an/aus mit Info-Badges)

**Frontend-Qualitaet**:
- Toast-Benachrichtigungen (Erfolg/Fehler/Info) statt alert()
- Form-Validierung mit roten Rahmen + Fehlertexte
- Spinner-Animationen waehrend API-Aufrufen

---

### 2.6 Installer ✓ vollstaendig

| Datei | Plattform | Zweck |
|-------|-----------|-------|
| **INSTALLIEREN.bat** | Windows 10/11 | Zero-Knowledge Doppelklick-Installer |
| **installer/install.sh** | Linux | Kommandozeilen-Installer |
| **installer/install.ps1** | Windows (PowerShell) | Ausfuehrliche Version |

**INSTALLIEREN.bat — Zero-Knowledge Installer:**
- Versucht Python automatisch via `winget` zu installieren
- Falls winget nicht verfuegbar: Oeffnet python.org mit genauer Anleitung
- Prueft Claude Desktop an 5 verschiedenen Installationspfaden
- Falls Claude fehlt: winget-Versuch, dann manuelle Anleitung mit Fallback-Suche
- Installiert venv + Pakete + Playwright Chromium
- Funktionstest (Module + Datenbank + Scoring)
- Konfiguriert Claude Desktop automatisch
- Jeder Schritt erklaert WAS installiert wird und WARUM
- Bei Fehlern: konkrete Loesungsvorschlaege in einfacher Sprache
- Falls Download-Links veraltet: Suchbegriffe fuer manuelle Suche

---

## 3. MCP-Schnittstelle (fuer Claude Desktop)

### 3.1 Tools (44 Aktionen)

| Tool | Beschreibung |
|------|-------------|
| **Profil-Grundlagen (8)** | |
| `profil_status()` | Prueft ob ein Profil existiert — immer als erstes aufrufen |
| `profil_erstellen()` | Profil erstellen/aktualisieren |
| `profil_zusammenfassung()` | Formatierte Profil-Uebersicht mit Vollstaendigkeits-Check |
| `profil_bearbeiten()` | Gezielte Korrekturen an Profilbereichen (Aliase, Bulk-Import) |
| `position_hinzufuegen()` | Berufserfahrung hinzufuegen |
| `projekt_hinzufuegen()` | STAR-Projekt einer Position zuordnen |
| `ausbildung_hinzufuegen()` | Ausbildung hinzufuegen |
| `skill_hinzufuegen()` | Kompetenz hinzufuegen |
| **Multi-Profil (4)** | |
| `profile_auflisten()` | Alle Profile mit Aktivstatus anzeigen |
| `profil_wechseln()` | Zu anderem Profil wechseln |
| `neues_profil_erstellen()` | Neues Profil anlegen |
| `profil_loeschen()` | Profil mit allen Daten loeschen (CASCADE) |
| **Erfassungsfortschritt (2)** | |
| `erfassung_fortschritt_lesen()` | Dialog-Fortschritt der Ersterfassung lesen |
| `erfassung_fortschritt_speichern()` | Dialog-Fortschritt speichern |
| **Dokument-Analyse (6)** | |
| `dokument_profil_extrahieren()` | Dokument-Text extrahieren |
| `dokumente_zur_analyse()` | Alle Dokumente mit Analysestatus auflisten |
| `extraktion_starten()` | KI-gestuetzte Datenextraktion starten |
| `extraktion_ergebnis_speichern()` | Extraktionsergebnis speichern |
| `extraktion_anwenden()` | Extrahierte Daten ins Profil uebernehmen (auto_apply) |
| `extraktions_verlauf()` | Extraktions-Historie anzeigen |
| **Profil Export/Import (2)** | |
| `profil_exportieren()` | Profil als JSON exportieren (Backup) |
| `profil_importieren()` | Profil aus JSON importieren |
| **Jobsuche (3)** | |
| `jobsuche_starten()` | Jobsuche auf konfigurierten Quellen (9 Portale) |
| `jobsuche_status()` | Fortschritt der Suche pruefen |
| `stelle_bewerten()` | Stelle bewerten/aussortieren |
| **Stellen & Bewerbungen (3)** | |
| `stellen_anzeigen()` | Gefundene Stellen anzeigen (Filter, Score, Quelle) |
| `fit_analyse()` | Detaillierte Passungsanalyse einer Stelle |
| `bewerbungen_anzeigen()` | Alle Bewerbungen mit Status und Statistik |
| **Bewerbungs-Management (3)** | |
| `bewerbung_erstellen()` | Bewerbung anlegen (3 Arten) |
| `bewerbung_status_aendern()` | Status aktualisieren mit Timeline |
| `statistiken_abrufen()` | Conversion-Rates, Bewerbungszahlen |
| **Export (2)** | |
| `lebenslauf_exportieren()` | CV als PDF/DOCX generieren und speichern |
| `anschreiben_exportieren()` | Anschreiben als PDF/DOCX generieren |
| **Konfiguration (2)** | |
| `suchkriterien_setzen()` | Keywords und Regionen konfigurieren |
| `blacklist_verwalten()` | Ausschlussliste verwalten |
| **Erweiterte KI-Features (9)** | |
| `gehalt_extrahieren()` | Gehaltsdaten aus Stellenanzeigen extrahieren |
| `gehalt_marktanalyse()` | Marktanalyse fuer Gehaltsverhandlung |
| `firmen_recherche()` | Unternehmensinformationen sammeln |
| `branchen_trends()` | Branchentrends und Marktentwicklung |
| `skill_gap_analyse()` | Fehlende Skills identifizieren |
| `ablehnungs_muster()` | Muster in Ablehnungen erkennen |
| `nachfass_planen()` | Follow-up Erinnerung erstellen |
| `nachfass_anzeigen()` | Anstehende Follow-ups anzeigen |
| `bewerbung_stil_tracken()` | Bewerbungsstil und Erfolgsrate tracken |

### 3.2 Resources (6 Datenquellen)

| URI | Inhalt |
|-----|--------|
| `profil://aktuell` | Gesamtes Profil als JSON |
| `jobs://aktiv` | Alle aktiven Stellen, sortiert nach Score |
| `jobs://aussortiert` | Aussortierte Stellen mit Gruenden |
| `bewerbungen://alle` | Alle Bewerbungen mit Events/Timeline |
| `bewerbungen://statistik` | Statistiken und Conversion-Rates |
| `config://suchkriterien` | Aktuelle Suchkonfiguration |

### 3.3 Prompts (12 KI-Vorlagen)

| Prompt | Zweck |
|--------|-------|
| `willkommen()` | Willkommensbildschirm mit Status-Uebersicht und Handlungsoptionen |
| `ersterfassung()` | 4-Phasen Dialog: Lockerer Einstieg → Strukturierte Erfassung → CV-basierte Praeferenzen → Review |
| `profil_ueberpruefen()` | Standalone Profil-Review mit Korrekturmoeglichkeit |
| `profil_analyse()` | Staerken, Luecken, Marktposition, Optimierungstipps |
| `profil_erweiterung()` | Dokument-basierte Profilerweiterung (Upload → Extraktion → Uebernahme) |
| `jobsuche_workflow()` | Gefuehrter Workflow: Kriterien → Quellen → Suche → Sichten → Bewerben |
| `bewerbung_schreiben(stelle, firma)` | Individuelles Anschreiben + Export als PDF/DOCX + Bewerbungs-Tracking |
| `interview_vorbereitung(stelle, firma)` | 10 Fragen, STAR-Antworten, Gehaltsstrategie, Quick-Reference |
| `interview_simulation(stelle, firma)` | Interaktive Interview-Simulation mit Feedback |
| `gehaltsverhandlung(stelle, firma)` | Gehaltsstrategie mit Marktdaten und Verhandlungstipps |
| `netzwerk_strategie()` | Networking-Plan fuer die Jobsuche |
| `bewerbungs_uebersicht()` | Komplette Uebersicht: Profil + Stellen + Bewerbungen + naechste Schritte |

---

## 4. Technische Architektur

```
┌──────────────────────────────────────────────────────────┐
│                    Claude Desktop (Windows)                │
│                                                           │
│  User: "Suche nach Python-Jobs in Hamburg"                │
│         ↓ (MCP Protocol / stdio)                          │
├──────────────────────────────────────────────────────────┤
│  server.py (Composition Root, ~140 Zeilen)                │
│    ├── tools/ (7 Module, 44 Tools)                        │
│    ├── prompts.py (12 Prompts)                            │
│    ├── resources.py (6 Resources)                         │
│    └── services/ (gemeinsamer Service-Layer)              │
│         ├── profile_service.py                            │
│         ├── search_service.py                             │
│         └── workspace_service.py                          │
│         ↓                                                  │
│  database.py (SQLite + WAL, Schema v8)                    │
│    └── 15 Kern-Tabellen + user_preferences, FK + CASCADE  │
│    └── Daten: %LOCALAPPDATA%\BewerbungsAssistent\pbp.db   │
│         ↓                                                  │
│  ┌──────────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ dashboard.py      │  │ job_scraper/ │  │ export.py  │  │
│  │ (FastAPI :8200)   │  │ 9 Quellen    │  │ PDF/DOCX   │  │
│  │ 56 API-Endpunkte  │  │ dynamische   │  │ fpdf2 +    │  │
│  │  ↕ JSON           │  │ Keywords     │  │ python-docx│  │
│  │ dashboard.html    │  │              │  │            │  │
│  │ (Browser SPA)     │  │              │  │            │  │
│  └──────────────────┘  └──────────────┘  └────────────┘  │
└──────────────────────────────────────────────────────────┘
```

---

## 5. Wie benutzt man PBP?

### 5.1 Erstinstallation (Windows)

1. `INSTALLIEREN.bat` doppelklicken
2. Anweisungen folgen (Python + Claude Desktop werden automatisch geprueft/installiert)
3. Claude Desktop neu starten
4. In Claude eintippen: **"Ersterfassung starten"**

### 5.2 Taegliche Nutzung

**Neue Stellen suchen:**
> "Suche nach neuen Stellen fuer mich"

**Stelle bewerten:**
> "Zeige mir die besten Stellen" → "Die zweite Stelle passt nicht, zu weit weg"

**Bewerbung schreiben:**
> "Schreibe ein Anschreiben fuer die Python-Stelle bei TechStart"

**Lebenslauf exportieren:**
> "Exportiere meinen Lebenslauf als PDF"

**Interview vorbereiten:**
> "Bereite mich auf das Interview bei CloudCorp vor"

**Profil ergaenzen:**
> "Ich habe ein neues AWS-Zertifikat bekommen"

**Profil ueberpruefen:**
> "Zeige mir mein Profil" oder "Profil ueberpruefen"

**Dashboard ansehen:**
> Browser oeffnen: http://localhost:8200

### 5.3 Demo-Modus

```bash
python test_demo.py
# Oeffnet Dashboard mit Beispieldaten auf http://localhost:8200
```

---

## 6. Automatische Tests

```bash
# Alle Tests ausfuehren:
pytest tests/ -v

# Einzelne Testdateien:
pytest tests/test_database.py -v          # 33 Tests
pytest tests/test_scoring.py -v           # 24 Tests
pytest tests/test_export.py -v            #  8 Tests
pytest tests/test_v010.py -v              # 43 Tests
pytest tests/test_dashboard.py -v         # 44 Tests
pytest tests/test_v013.py -v              # 14 Tests
pytest tests/test_mcp_registry.py -v      #  3 Tests
pytest tests/test_scrapers.py -v          #  3 Tests
pytest tests/test_profile_service.py -v   #  5 Tests
pytest tests/test_search_service.py -v    #  5 Tests
pytest tests/test_workspace_service.py -v #  5 Tests
pytest tests/test_dashboard_browser.py -v #  3 Tests
```

Ergebnis: **190 Tests, alle gruen**

---

## 7. Fazit v0.14.0

### Was funktioniert:
- ✓ Dialog-basierte Profilerstellung (lockeres Interview, nicht steifes Formular)
- ✓ Unterstuetzung fuer diverse Lebenslaeufe (Studenten bis Wiedereinsteiger)
- ✓ Multi-Source Jobsuche (9 Portale) mit dynamischen Keywords
- ✓ Quellenverwaltung (an/aus pro Quelle)
- ✓ Scoring + Fit-Analyse (konfigurierbar)
- ✓ Multi-Profil-System mit Daten-Isolation
- ✓ Bewerbungs-Tracking mit Timeline (3 Bewerbungsarten)
- ✓ PDF/DOCX-Export (Lebenslauf + Anschreiben)
- ✓ KI-gestuetzte Texterstellung (Anschreiben, Interview-Prep, Simulation)
- ✓ Dokument-Upload mit automatischer Text-Extraktion
- ✓ Gehalts-Schaetzungs-Engine (7 Regex-Patterns + Lookup)
- ✓ Web-Dashboard mit 5 Tabs + Toast + Validierung + Spinner + Paginierung
- ✓ Onboarding-Wizard + Bewerbungs-Wizard
- ✓ Zero-Knowledge Windows-Installer (Doppelklick, winget-Support)
- ✓ 190 Tests im aktuellen Repo-Stand
- ✓ Cross-Platform (Windows + Linux)

### Moegliche zukuenftige Erweiterungen:
- Dark Mode
- E-Mail-Benachrichtigungen bei neuen passenden Stellen
- Bewerbungs-Templates
- weiterer Ausbau des Service-Layers (siehe docs/VERBESSERUNGSPLAN.md)
