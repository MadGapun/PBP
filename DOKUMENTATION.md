# PBP — Persoenliches Bewerbungs-Portal
## Komplette Projektdokumentation | Stand: 2026-02-26 | V1.0

---

## 1. Was ist PBP?

PBP ist ein **KI-gestuetzter Bewerbungs-Assistent**, der als Plugin in **Claude Desktop** laeuft.
Er hilft Menschen bei der Jobsuche — egal ob Berufseinsteiger, erfahrene Fachkraft,
Freelancer, Wiedereinsteigerin oder Karrierewechsler. Kein Coaching noetig, kein
Computerwissen vorausgesetzt.

Der Assistent kann:

- Ein strukturiertes Profil aufbauen (wie ein lockeres Gespraech, nicht wie ein Formular)
- Stellenangebote automatisch aus **8 Jobportalen** sammeln
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

### 2.2 Jobsuche ✓ vollstaendig (8 Quellen)

| Quelle | Methode | Login | Status |
|--------|---------|-------|--------|
| **Bundesagentur fuer Arbeit** | REST API | Nein | ✓ |
| **StepStone** | HTML-Scraping (BS4) | Nein | ✓ |
| **Hays** | Sitemap + JSON-LD | Nein | ✓ |
| **Freelancermap** | JavaScript-State | Nein | ✓ |
| **Indeed** | HTML-Scraping (BS4) | Nein | ✓ |
| **Monster** | HTML-Scraping (BS4) | Nein | ✓ |
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
- **Quellenverwaltung** (8 Quellen an/aus mit Info-Badges)

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

### 3.1 Tools (21 Aktionen)

| Tool | Beschreibung |
|------|-------------|
| **Profil** | |
| `profil_status()` | Prueft ob ein Profil existiert — immer als erstes aufrufen |
| `profil_erstellen()` | Profil erstellen/aktualisieren |
| `profil_zusammenfassung()` | Formatierte Profil-Uebersicht mit Vollstaendigkeits-Check |
| `profil_bearbeiten()` | Gezielte Korrekturen an Profilbereichen |
| `position_hinzufuegen()` | Berufserfahrung hinzufuegen |
| `projekt_hinzufuegen()` | STAR-Projekt einer Position zuordnen |
| `ausbildung_hinzufuegen()` | Ausbildung hinzufuegen |
| `skill_hinzufuegen()` | Kompetenz hinzufuegen |
| **Jobsuche** | |
| `jobsuche_starten()` | Jobsuche auf konfigurierten Quellen |
| `jobsuche_status()` | Fortschritt der Suche pruefen |
| `stellen_anzeigen()` | Gefundene Stellen anzeigen (mit Filter nach Score, Quelle) |
| `fit_analyse()` | Detaillierte Passungsanalyse einer Stelle |
| `stelle_bewerten()` | Stelle bewerten/aussortieren |
| **Bewerbungen** | |
| `bewerbung_erstellen()` | Bewerbung anlegen (3 Arten) |
| `bewerbung_status_aendern()` | Status aktualisieren |
| `bewerbungen_anzeigen()` | Alle Bewerbungen mit Status und Statistik anzeigen |
| `statistiken_abrufen()` | Conversion-Rates, Bewerbungszahlen |
| **Export** | |
| `lebenslauf_exportieren()` | CV als PDF/DOCX generieren und speichern |
| `anschreiben_exportieren()` | Anschreiben als PDF/DOCX generieren |
| **Konfiguration** | |
| `suchkriterien_setzen()` | Keywords und Regionen konfigurieren |
| `blacklist_verwalten()` | Ausschlussliste verwalten |

### 3.2 Resources (6 Datenquellen)

| URI | Inhalt |
|-----|--------|
| `profil://aktuell` | Gesamtes Profil als JSON |
| `jobs://aktiv` | Alle aktiven Stellen, sortiert nach Score |
| `jobs://aussortiert` | Aussortierte Stellen mit Gruenden |
| `bewerbungen://alle` | Alle Bewerbungen mit Events/Timeline |
| `bewerbungen://statistik` | Statistiken und Conversion-Rates |
| `config://suchkriterien` | Aktuelle Suchkonfiguration |

### 3.3 Prompts (8 KI-Vorlagen)

| Prompt | Zweck |
|--------|-------|
| `willkommen()` | Willkommensbildschirm mit Status-Uebersicht und Handlungsoptionen |
| `ersterfassung()` | 4-Phasen Dialog: Lockerer Einstieg → Strukturierte Erfassung → CV-basierte Praeferenzen → Review |
| `profil_ueberpruefen()` | Standalone Profil-Review mit Korrekturmoeglichkeit |
| `profil_analyse()` | Staerken, Luecken, Marktposition, Optimierungstipps |
| `jobsuche_workflow()` | Gefuehrter Workflow: Kriterien → Quellen → Suche → Sichten → Bewerben |
| `bewerbung_schreiben(stelle, firma)` | Individuelles Anschreiben + Export als PDF/DOCX + Bewerbungs-Tracking |
| `interview_vorbereitung(stelle, firma)` | 10 Fragen, STAR-Antworten, Gehaltsstrategie, Quick-Reference |
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
│  server.py (FastMCP)                                      │
│    ├── 21 Tools (profil, jobs, export, bewerbungen...)    │
│    ├── 6 Resources (profil://aktuell, jobs://aktiv...)    │
│    └── 8 Prompts (ersterfassung, willkommen, workflow...) │
│         ↓                                                  │
│  database.py (SQLite + WAL, Schema v2)                    │
│    └── 13 Tabellen, Foreign Keys, CASCADE Deletes         │
│    └── Daten: %LOCALAPPDATA%\BewerbungsAssistent\pbp.db   │
│         ↓                                                  │
│  ┌──────────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ dashboard.py      │  │ job_scraper/ │  │ export.py  │  │
│  │ (FastAPI :8200)   │  │ 8 Quellen    │  │ PDF/DOCX   │  │
│  │ 28 Endpoints      │  │ dynamische   │  │ fpdf2 +    │  │
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
pytest tests/test_database.py -v    # 34 Tests
pytest tests/test_scoring.py -v     # 19 Tests
pytest tests/test_export.py -v      # 8 Tests
```

Ergebnis: **65 Tests, alle gruen, 1.96 Sekunden**

---

## 7. Fazit V1.0

### Was funktioniert:
- ✓ Dialog-basierte Profilerstellung (lockeres Interview, nicht steifes Formular)
- ✓ Unterstuetzung fuer diverse Lebenslaeufe (Studenten bis Wiedereinsteiger)
- ✓ Multi-Source Jobsuche (8 Portale) mit dynamischen Keywords
- ✓ Quellenverwaltung (an/aus pro Quelle)
- ✓ Scoring + Fit-Analyse (konfigurierbar)
- ✓ Bewerbungs-Tracking mit Timeline (3 Bewerbungsarten)
- ✓ PDF/DOCX-Export (Lebenslauf + Anschreiben)
- ✓ KI-gestuetzte Texterstellung (Anschreiben, Interview-Prep)
- ✓ Web-Dashboard mit 5 Tabs + Toast + Validierung + Spinner
- ✓ Zero-Knowledge Windows-Installer (Doppelklick, winget-Support)
- ✓ 65 automatische Tests (100% gruen)
- ✓ Cross-Platform (Windows + Linux)

### Post-V1.0 Ideen:
- Profil-Bearbeitung direkt im Dashboard (nicht nur hinzufuegen)
- Paginierung bei vielen Jobs/Bewerbungen
- Automatische Backups der Datenbank
- Dark Mode
- E-Mail-Benachrichtigungen bei neuen passenden Stellen
- Multi-Profil (verschiedene CVs fuer verschiedene Branchen)
- Bewerbungs-Templates
- Trend-Analyse (Erfolgsrate ueber Zeit)
