# PBP — Persönliches Bewerbungs-Portal

> Dein KI-gestützter Bewerbungsassistent für Claude Desktop — von der Profilerstellung bis zum Traumjob.

[![Python 3.11+](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/MCP-Claude_Desktop-orange.svg)](https://modelcontextprotocol.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/Tests-190%20passing-brightgreen.svg)](#tests)
[![Tools](https://img.shields.io/badge/MCP_Tools-54-blueviolet.svg)](#mcp-schnittstelle)

---

## Warum PBP?

Jobsuche ist zeitfressend. Du schreibst Lebensläufe um, googelst Stellenbörsen, copy-pastest zwischen Tabs, verlierst den Überblick über Bewerbungen und fragst dich, ob du die richtige Stelle überhaupt findest.

**PBP nimmt dir das ab.** Du redest einfach mit Claude — in natürlicher Sprache — und PBP erledigt den Rest:

| Problem | PBP-Lösung |
|---------|-----------|
| 😩 Lebenslauf für jede Stelle umschreiben | ✅ **Angepasster Lebenslauf** — PBP erstellt für jede Stelle einen maßgeschneiderten CV (DOCX), sortiert Skills und Erfahrung nach Relevanz |
| 😩 10 Jobportale einzeln durchsuchen | ✅ **9 Portale gleichzeitig** — eine Suche, alle Ergebnisse: StepStone, LinkedIn, Indeed, Hays, XING, Monster, Bundesagentur, Freelancermap, Freelance.de |
| 😩 Hunderte Stellen manuell durchlesen | ✅ **Intelligentes Scoring** — Stellen werden automatisch nach deinem Profil bewertet und sortiert (Entfernung, Skills, Gehalt) |
| 😩 Anschreiben von Null anfangen | ✅ **Personalisierte Anschreiben** — basierend auf deinem Profil und der Stellenbeschreibung |
| 😩 Überblick über Bewerbungen verlieren | ✅ **Bewerbungs-Tracking** — Pipeline von "offen" bis "Angebot" mit Timeline und Statistiken |
| 😩 Interviewvorbereitung improvisieren | ✅ **Interview-Simulation** — Claude spielt den Interviewer und gibt Feedback |
| 😩 Gehalt falsch verhandeln | ✅ **Gehaltsverhandlung** — Markdaten-basierte Strategie und Argumentationshilfe |

### Das Besondere

- **Kein Formular-Ausfüllen.** Du unterhältst dich mit Claude. PBP baut dein Profil aus dem Gespräch auf.
- **Deine Daten bleiben lokal.** SQLite auf deinem Rechner — nichts geht in die Cloud (außer an Claude für die KI-Verarbeitung).
- **Festanstellung & Freelance.** Egal ob du einen festen Job oder Projektaufträge suchst — PBP unterstützt beides mit getrennter Darstellung.
- **STAR-Methode für Projekte.** PBP strukturiert deine Berufserfahrung nach Situation-Task-Action-Result — das Format, das Recruiter lieben.

---

## Was PBP kann — Feature-Übersicht

### 🗣️ Profilerstellung im Gespräch
Claude führt ein lockeres Interview und erfasst alles:
- Persönliche Daten, Kontakt, Standort
- Berufserfahrung mit Projekten (STAR-Methode)
- Ausbildung, Zertifikate, Sprachen
- Skills mit Level (1-5) und Aktualität
- Gehaltsvorstellungen und Arbeitspräferenzen (Remote, Teilzeit, Reisebereitschaft)

**Oder:** Lade einfach deinen bestehenden Lebenslauf hoch (PDF/DOCX) — PBP extrahiert die Daten automatisch.

### 🔍 Stellensuche über 9 Portale
Eine Suche — alle relevanten Portale gleichzeitig:

| Portal | Methode | Account nötig? |
|--------|---------|---------------|
| Bundesagentur für Arbeit | REST API | ❌ Nein |
| StepStone | Playwright | ❌ Nein |
| Hays | Sitemap + JSON-LD | ❌ Nein |
| Monster | Playwright | ❌ Nein |
| Indeed | Playwright | ❌ Nein |
| Freelancermap | httpx + Fallback | ❌ Nein |
| Freelance.de | HTML Scraping | ❌ Nein |
| **LinkedIn** | **Playwright** | **✅ Ja — eigener Account** |
| **XING** | **Playwright** | **✅ Ja — eigener Account** |

> 💡 Du kannst in den Einstellungen frei wählen, welche Quellen aktiv sein sollen. LinkedIn und XING sind optional.

### 📊 Intelligentes Scoring & Fit-Analyse
Jede Stelle bekommt einen Score basierend auf:
- **Entfernung** — Stellen unter 30 km werden bevorzugt
- **Keywords** — MUSS/PLUS/AUSSCHLUSS-Kriterien
- **Gehalt** — Vergleich mit deiner Gehaltsvorstellung
- **Remote-Level** — Remote/Hybrid-Erkennung
- **Kompetenzen-Match** — Deine Skills vs. Stellenbeschreibung

Im Dashboard werden Stellen nach Typ getrennt dargestellt:
- **Linke Spalte:** Festanstellung
- **Rechte Spalte:** Freelance/Projekt
- Umschaltbar auf Listen-Ansicht per Knopfdruck

### 📝 Stellenspezifische Dokumente
- **Angepasster Lebenslauf (DOCX)** — Skills und Positionen werden nach Relevanz für die Stelle umsortiert
- **Personalisiertes Anschreiben (PDF/DOCX)** — basierend auf Profil + Stellenbeschreibung
- **Standard-Lebenslauf (PDF/DOCX)** — für Initiativbewerbungen

> 📌 Immer DOCX beim angepassten CV — weil die letzten Feinschliffe ein Mensch machen sollte.

### 📈 Bewerbungs-Tracking
- Status-Pipeline: offen → beworben → Interview → Angebot → angenommen/abgelehnt
- Timeline mit allen Ereignissen
- Conversion-Rates und Statistiken
- Follow-up-Erinnerungen (automatisch geplant)
- A/B-Tracking für Anschreiben-Stile
- Ablehnungs-Muster-Analyse

### 🎯 KI-Coaching
- **Interview-Simulation** — Claude spielt den Interviewer (auf Basis der echten Stelle)
- **Gehaltsverhandlung** — Markdaten, Strategie, Argumente
- **Skill-Gap-Analyse** — Was dir für die Wunschstelle fehlt
- **Profil-Analyse** — Stärken, Potenziale, Marktposition
- **Netzwerk-Strategie** — Networking-Plan für eine Zielfirma
- **Branchen-Trends** — Welche Skills gerade gefragt sind

### 🌐 Web-Dashboard
Browser-Oberfläche auf `localhost:8200` mit 5 Tabs:

| Tab | Funktion |
|-----|----------|
| **Dashboard** | Übersicht, Workspace-Guidance, nächste Schritte |
| **Profil** | Alles bearbeiten — Positionen, Skills, Ausbildung, Projekte |
| **Stellen** | Jobs mit Score, Split-View (Fest/Freelance), Sortierung |
| **Bewerbungen** | Pipeline, Timeline, Statistiken |
| **Einstellungen** | Quellen, Suchkriterien, Blacklist, Gehaltsfilter |

---

## Schnellstart

### 1. Installation (Windows)

1. **Lade die [neueste Version](https://github.com/MadGapun/PBP/releases/latest) herunter** (ZIP-Datei)
2. **Entpacke** das ZIP in einen Ordner (z.B. `C:\PBP`)
3. **Doppelklicke `INSTALLIEREN.bat`** — fertig!

Der Installer:
- Lädt Python herunter und richtet es ein
- Installiert alle Pakete
- Konfiguriert Claude Desktop automatisch
- Erstellt eine Desktop-Verknüpfung

> **Voraussetzungen:** Windows 10/11 (64-Bit), Internetverbindung, [Claude Desktop](https://claude.ai/download)

### 2. Profil erstellen

Öffne Claude Desktop und sage:

> **"Starte die Ersterfassung"**

Claude führt dich durch ein lockeres Gespräch (ca. 10-15 Minuten):

1. **Persönliche Daten** — Name, Kontakt, Standort
2. **Berufserfahrung** — Positionen und Projekte (STAR-Methode)
3. **Ausbildung & Skills** — mit Levels und Aktualität
4. **Präferenzen** — Gehalt, Remote, Teilzeit, Reisebereitschaft

**Schneller geht's mit Dokumenten:** Lade deinen Lebenslauf als PDF oder DOCX hoch — PBP extrahiert die Daten automatisch und fragt nur noch nach, was fehlt.

### 3. Suchkriterien festlegen

> **"Starte den Jobsuche-Workflow"**

Claude hilft dir bei:
- MUSS-Keywords (z.B. "PLM", "Python")
- PLUS-Keywords (z.B. "Remote", "Teamleitung")
- AUSSCHLUSS-Keywords (z.B. "SAP", "Zeitarbeit")
- Standort und Entfernungsradius
- Gehaltsvorstellungen
- Aktive Jobportale auswählen

### 4. Jobs finden

> **"Suche nach Stellen"**

PBP durchsucht alle aktiven Portale, dedupliziert die Ergebnisse und bewertet jede Stelle. Im Dashboard siehst du die Ergebnisse sofort — sortiert nach Entfernung, Score oder Gehalt.

### 5. Bewerben

> **"Schreibe eine Bewerbung für die Stelle bei [Firma]"**

PBP erstellt:
1. Einen **angepassten Lebenslauf** (Skills und Erfahrung nach Relevanz sortiert)
2. Ein **personalisiertes Anschreiben** (optional — manchmal reicht der CV)

Beide Dokumente als DOCX zum Feinschliff.

### 6. Nachverfolgen

> **"Zeige meine Bewerbungen"**

Behalte den Überblick: Status aktualisieren, Follow-ups planen, Statistiken auswerten.

---

## Bedienungsanleitung

### Wie spreche ich mit PBP?

PBP wird komplett über natürliche Sprache gesteuert. Du tippst (oder sagst) Claude einfach, was du willst:

| Was du sagen kannst | Was PBP tut |
|--------------------|------------|
| "Starte die Ersterfassung" | Profilerstellung im Gespräch |
| "Lade meinen Lebenslauf" | Dokument-Upload und automatische Extraktion |
| "Suche nach Python-Entwickler-Stellen in Hamburg" | Multi-Portal-Jobsuche |
| "Zeige mir die besten Stellen" | Stellen nach Score sortiert |
| "Mach eine Fit-Analyse für Stelle #3" | Detaillierter Vergleich Profil vs. Stelle |
| "Schreibe ein Anschreiben für die Hays-Stelle" | Personalisiertes Anschreiben |
| "Erstelle einen angepassten Lebenslauf für Firma XY" | Stellenspezifischer CV |
| "Exportiere meinen Lebenslauf als DOCX" | Standard-CV-Export |
| "Bereite mich auf das Interview bei Firma XY vor" | Interview-Simulation |
| "Wie sollte ich beim Gehalt verhandeln?" | Gehaltsverhandlungs-Coaching |
| "Welche Skills fehlen mir für die Stelle?" | Skill-Gap-Analyse |
| "Zeige meine Bewerbungsstatistiken" | Conversion-Rates und Übersicht |
| "Plane einen Follow-up für die Bewerbung bei Firma XY" | Erinnerung in X Tagen |

### Die 12 Workflows

PBP bietet 12 geführte Workflows. Du kannst sie entweder als Slash-Command (`/name`) oder als natürliche Anweisung starten:

| Workflow | Slash-Command | Was er tut |
|----------|--------------|-----------|
| **Ersterfassung** | `/ersterfassung` | Komplettes Profil im Gespräch aufbauen |
| **Profil-Erweiterung** | `/profil_erweiterung` | Profil aus Dokumenten erweitern |
| **Profil überprüfen** | `/profil_ueberpruefen` | Fehler und Lücken finden |
| **Profil-Analyse** | `/profil_analyse` | Stärken, Potenziale, Marktposition |
| **Jobsuche** | `/jobsuche_workflow` | Geführte 5-Schritte Stellensuche |
| **Bewerbung schreiben** | `/bewerbung_schreiben` | CV + Anschreiben für eine Stelle |
| **Bewerbungsübersicht** | `/bewerbungs_uebersicht` | Komplettübersicht aller Aktivitäten |
| **Interview-Vorbereitung** | `/interview_vorbereitung` | STAR-Antworten vorbereiten |
| **Interview-Simulation** | `/interview_simulation` | Claude spielt den Interviewer |
| **Gehaltsverhandlung** | `/gehaltsverhandlung` | Strategie und Argumente |
| **Netzwerk-Strategie** | `/netzwerk_strategie` | Networking-Plan für Zielfirma |
| **Willkommen** | `/willkommen` | Statusübersicht und Einstiegshilfe |

> 💡 **Tipp:** In **claude.ai** (Web) gibt es keine Slash-Commands. Sage einfach: *"Starte den Workflow: /jobsuche_workflow"* — PBP erkennt das automatisch.

### Das Web-Dashboard

Das Dashboard startet automatisch auf [http://localhost:8200](http://localhost:8200) wenn PBP läuft.

**Dashboard-Tab:**
- Workspace-Guidance zeigt dir den nächsten sinnvollen Schritt
- Next-Steps-Banner mit kontextbezogenen Aktionen
- Statistiken auf einen Blick

**Profil-Tab:**
- Alle Daten bearbeiten (Klick auf ✏️)
- Skills mit Level und Kategorie
- Projekte im STAR-Format
- Jobtitel-Vorschläge

**Stellen-Tab:**
- Split-View: Festanstellung links, Freelance rechts (umschaltbar)
- Sortierung: Entfernung (Standard), Score, Gehalt, Datum
- Fit-Analyse per Klick
- Bewerbungs-Wizard direkt aus der Stellenanzeige

**Bewerbungen-Tab:**
- Pipeline-Ansicht mit Drag & Drop
- Timeline pro Bewerbung
- Follow-up-Erinnerungen
- Statistiken und Conversion-Rates

**Einstellungen-Tab:**
- Aktive Jobportale auswählen
- MUSS/PLUS/AUSSCHLUSS-Keywords
- Firmen-Blacklist
- Gehaltsfilter

### Multi-Profil

Mehrere Benutzer auf einem PC? Kein Problem:

> **"Zeige alle Profile"** — Profile auflisten
> **"Wechsle zu Profil XY"** — Aktives Profil wechseln
> **"Erstelle ein neues Profil für Anna"** — Neues Profil anlegen

Im Dashboard steht der Profil-Wechsler direkt in der Navigationsleiste.

---

## Jobportale — Accounts und rechtliche Hinweise

### Welche Portale brauchen einen Account?

| Portal | Account nötig? | Details |
|--------|---------------|---------|
| Bundesagentur | Nein | Öffentliche REST API |
| StepStone | Nein | Öffentlich einsehbare Stellenanzeigen |
| Hays | Nein | Öffentliche Sitemap + strukturierte Daten |
| Monster | Nein | Öffentlich einsehbare Stellenanzeigen |
| Indeed | Nein | Öffentlich einsehbare Stellenanzeigen |
| Freelancermap | Nein | Öffentlich einsehbare Stellenanzeigen |
| Freelance.de | Nein | Öffentlich einsehbare Stellenanzeigen |
| **LinkedIn** | **Ja** | Kostenloser Account reicht. Du musst dich **einmalig** im Browser einloggen — PBP speichert die Session lokal. |
| **XING** | **Ja** | Kostenloser Account reicht. Gleicher Ansatz wie LinkedIn — einmaliger Login. |

### LinkedIn und XING einrichten

Beide Portale erfordern einen einmaligen Login:

1. **Aktiviere** LinkedIn/XING in den PBP-Einstellungen (Dashboard → Einstellungen → Quellen)
2. **Starte eine Jobsuche** — PBP erkennt, dass noch kein Login vorliegt
3. **Ein Browser-Fenster öffnet sich** — logge dich ganz normal ein
4. **Session wird gespeichert** — alle weiteren Suchen laufen automatisch (headless)

Die Session wird lokal gespeichert unter:
- LinkedIn: `~/.bewerbungs-assistent/linkedin-session/` (bzw. `%LOCALAPPDATA%\BewerbungsAssistent\linkedin-session\`)
- XING: `~/.bewerbungs-assistent/xing-session/`

> ⚠️ Wenn die Session abläuft (nach Wochen/Monaten), öffnet sich der Browser erneut zum Login.

### Rechtliche Einordnung

PBP ist ein **persönliches Werkzeug**, das in deinem Namen und mit deinen Accounts auf Jobportale zugreift — vergleichbar damit, dass du selbst im Browser suchst.

**Was PBP tut:**
- Durchsucht öffentlich zugängliche Stellenanzeigen
- Greift auf LinkedIn/XING nur mit **deinem persönlichen Account** und **deiner aktiven Session** zu
- Speichert Stellendaten **nur lokal** auf deinem Rechner
- Macht keine Massenanfragen — menschliche Verzögerungen zwischen Anfragen

**Was PBP NICHT tut:**
- Keine Daten anderer Nutzer scrapen (nur Stellenanzeigen)
- Keine Accounts anlegen oder Passwörter speichern
- Keine Daten an Dritte weitergeben
- Kein Umgehen von Zugangsschranken (du bist selbst eingeloggt)

**Deine Verantwortung:**
- Du nutzt PBP mit **deinen eigenen Accounts** und bist für die Einhaltung der jeweiligen Nutzungsbedingungen verantwortlich.
- LinkedIn und XING verbieten in ihren AGB die Nutzung automatisierter Tools. In der Praxis tolerieren die meisten Plattformen persönliche Nutzung mit normaler Frequenz — PBP simuliert menschliches Suchverhalten mit Verzögerungen. Trotzdem besteht theoretisch das Risiko einer Account-Sperre.
- Die Bundesagentur für Arbeit stellt eine **offizielle REST API** bereit, die zur Nutzung vorgesehen ist.
- StepStone, Hays, Monster, Indeed, Freelancermap und Freelance.de werden über öffentlich zugängliche Seiten durchsucht.

> 💡 **Empfehlung:** Wenn du auf Nummer sicher gehen willst, deaktiviere LinkedIn und XING in den Einstellungen und nutze die 7 anderen Quellen. Die liefern bereits eine sehr gute Abdeckung des deutschen Stellenmarkts.

---

## Installation im Detail

### Windows (Empfohlen)

1. **Lade die [neueste Version](https://github.com/MadGapun/PBP/releases/latest) herunter** (ZIP-Datei)
2. **Entpacke** das ZIP in einen Ordner deiner Wahl (z.B. `C:\PBP`)
3. **Doppelklicke `INSTALLIEREN.bat`** — der Rest passiert automatisch:
   - Python wird heruntergeladen und eingerichtet
   - Alle Pakete werden installiert
   - Claude Desktop wird konfiguriert
   - Eine Desktop-Verknüpfung wird erstellt

> **Voraussetzungen:** Windows 10/11 (64-Bit), Internetverbindung, [Claude Desktop](https://claude.ai/download)

### Linux / Manuell

```bash
# Repository klonen
git clone https://github.com/MadGapun/PBP.git
cd PBP

# Virtual Environment erstellen
python3 -m venv venv
source venv/bin/activate

# Installieren (Kern + Docs)
pip install -e ".[docs]"

# Optional: Scraper mit Playwright
pip install -e ".[all]"
playwright install chromium
```

### Claude Desktop konfigurieren

Die `INSTALLIEREN.bat` macht das automatisch. Für manuelle Konfiguration, füge in `%APPDATA%\Claude\claude_desktop_config.json` hinzu:

```json
{
  "mcpServers": {
    "bewerbungs-assistent": {
      "command": "python",
      "args": ["-m", "bewerbungs_assistent"],
      "env": {
        "BA_DATA_DIR": "C:\\Users\\DEIN_NAME\\AppData\\Local\\BewerbungsAssistent"
      }
    }
  }
}
```

### Nach der Installation

```
%LOCALAPPDATA%\BewerbungsAssistent\
├── python\          ← Embedded Python (vom Installer)
├── src\             ← PBP Source Code (vom Installer)
├── pbp.db           ← Deine Datenbank (Profil, Jobs, Bewerbungen)
├── dokumente\       ← Hochgeladene Dokumente
├── export\          ← Generierte Lebensläufe und Anschreiben
└── logs\            ← Protokolle
```

---

## Architektur

```
Claude Desktop / claude.ai
    │
    │ stdio (MCP Protocol)
    ▼
server.py (FastMCP, Composition Root)
    │
    ├──► tools/            ◄── 54 Tools in 8 Modulen
    ├──► prompts.py        ◄── 12 Prompts (Workflows)
    ├──► resources.py      ◄── 6 Resources
    │
    ├──► services/         ◄── Service-Layer (Profil, Suche, Workspace)
    ├──► database.py       ◄── SQLite (16 Kern-Tabellen, WAL, Schema v9)
    ├──► dashboard.py      ◄── FastAPI :8200, 60+ API-Endpoints
    ├──► export.py         ◄── Lebenslauf + Anschreiben (PDF/DOCX)
    └──► job_scraper/      ◄── 9 Quellen
              ├── bundesagentur.py   (REST API)
              ├── stepstone.py       (Playwright)
              ├── hays.py            (Sitemap + JSON-LD)
              ├── freelancermap.py   (httpx + Playwright Fallback)
              ├── freelance_de.py    (HTML Scraping)
              ├── linkedin.py        (Playwright + Persistent Session)
              ├── indeed.py          (Playwright)
              ├── xing.py            (Playwright + Persistent Session)
              └── monster.py         (Playwright)
```

---

## MCP-Schnittstelle

### 54 Tools in 8 Modulen

<details>
<summary><strong>Profilverwaltung</strong> (14 Tools) — Profil, Multi-Profil, Erfassung</summary>

| Tool | Beschreibung |
|------|-------------|
| `profil_status` | Profilstatus und Übersicht |
| `profil_zusammenfassung` | Vollständige Profilzusammenfassung |
| `profil_erstellen` | Profil anlegen oder aktualisieren |
| `profil_bearbeiten` | Einzelne Bereiche bearbeiten (hinzufügen, ändern, löschen) |
| `position_hinzufuegen` | Berufserfahrung hinzufügen |
| `projekt_hinzufuegen` | STAR-Projekt zu einer Position |
| `ausbildung_hinzufuegen` | Ausbildungseintrag anlegen |
| `skill_hinzufuegen` | Kompetenz mit Level und Kategorie |
| `profile_auflisten` | Alle Profile auflisten |
| `profil_wechseln` | Aktives Profil wechseln |
| `neues_profil_erstellen` | Neues leeres Profil anlegen |
| `profil_loeschen` | Profil löschen (mit Auto-Switch) |
| `erfassung_fortschritt_lesen` | Ersterfassungs-Fortschritt |
| `erfassung_fortschritt_speichern` | Fortschritt pro Bereich speichern |

</details>

<details>
<summary><strong>Dokumente</strong> (10 Tools) — Upload, Extraktion, Import/Export</summary>

| Tool | Beschreibung |
|------|-------------|
| `dokument_profil_extrahieren` | Profildaten aus Dokument extrahieren |
| `dokumente_zur_analyse` | Analysierbare Dokumente auflisten |
| `extraktion_starten` | Dokument-Analyse starten |
| `extraktion_ergebnis_speichern` | Ergebnis zwischenspeichern |
| `extraktion_anwenden` | Daten auf Profil anwenden |
| `extraktions_verlauf` | Historie aller Extraktionen |
| `analyse_plan_erstellen` | Vorab-Plan für Batch-Analyse |
| `dokumente_batch_analysieren` | Effiziente Batch-Analyse |
| `dokumente_bulk_markieren` | Bulk-Markierung als analysiert |
| `bewerbungs_dokumente_erkennen` | Firmen aus Dateinamen erkennen |

</details>

<details>
<summary><strong>Jobsuche</strong> (5 Tools) — Suche, Bewertung, Analyse</summary>

| Tool | Beschreibung |
|------|-------------|
| `jobsuche_starten` | Multi-Quellen Stellensuche |
| `jobsuche_status` | Suchfortschritt abfragen |
| `stellen_anzeigen` | Jobs mit Filter und Scoring |
| `stelle_bewerten` | Job als passend/unpassend markieren |
| `fit_analyse` | Detaillierte Fit-Analyse |

</details>

<details>
<summary><strong>Bewerbungen</strong> (4 Tools) — Tracking und Statistiken</summary>

| Tool | Beschreibung |
|------|-------------|
| `bewerbung_erstellen` | Neue Bewerbung anlegen |
| `bewerbung_status_aendern` | Status aktualisieren |
| `bewerbungen_anzeigen` | Alle Bewerbungen mit Statistiken |
| `statistiken_abrufen` | Conversion Rates und Übersicht |

</details>

<details>
<summary><strong>Analyse</strong> (9 Tools) — Gehalt, Trends, Skill-Gap, Follow-ups</summary>

| Tool | Beschreibung |
|------|-------------|
| `gehalt_extrahieren` | Gehalt aus Stellenbeschreibung |
| `gehalt_marktanalyse` | Gehaltsstatistiken über alle Stellen |
| `firmen_recherche` | Firmendaten aggregieren |
| `branchen_trends` | Gefragte Skills und Technologien |
| `nachfass_planen` | Follow-up-Erinnerung planen |
| `nachfass_anzeigen` | Alle Follow-ups zeigen |
| `bewerbung_stil_tracken` | A/B-Tracking für Anschreiben |
| `skill_gap_analyse` | Skill-Gap zwischen Profil und Stelle |
| `ablehnungs_muster` | Ablehnungs-Analyse und Empfehlungen |

</details>

<details>
<summary><strong>Export</strong> (3 Tools) — Lebenslauf und Anschreiben</summary>

| Tool | Beschreibung |
|------|-------------|
| `lebenslauf_exportieren` | Standard-CV als PDF/DOCX |
| `lebenslauf_angepasst_exportieren` | Stellenspezifischer CV (immer DOCX) |
| `anschreiben_exportieren` | Anschreiben als PDF/DOCX |

</details>

<details>
<summary><strong>Suche & Einstellungen</strong> (2 Tools)</summary>

| Tool | Beschreibung |
|------|-------------|
| `suchkriterien_setzen` | Keywords und Filter konfigurieren |
| `blacklist_verwalten` | Firmen/Keywords ausschließen |

</details>

<details>
<summary><strong>Workflows</strong> (5 Tools) — Import/Export und Workflow-Starter</summary>

| Tool | Beschreibung |
|------|-------------|
| `profil_exportieren` | Profil als JSON-Backup |
| `profil_importieren` | Profil aus JSON-Backup |
| `workflow_starten` | Universeller Workflow-Starter |
| `jobsuche_workflow_starten` | Direkter Einstieg Jobsuche |
| `ersterfassung_starten` | Direkter Einstieg Ersterfassung |

</details>

<details>
<summary><strong>Jobtitel</strong> (2 Tools)</summary>

| Tool | Beschreibung |
|------|-------------|
| `jobtitel_vorschlagen` | Passende Jobtitel aus Profil ableiten |
| `jobtitel_verwalten` | Jobtitel bearbeiten/löschen/deaktivieren |

</details>

### 6 Resources

| URI | Beschreibung |
|-----|-------------|
| `profil://aktuell` | Vollständiges Bewerberprofil |
| `jobs://aktiv` | Aktive Stellenangebote (nach Score) |
| `jobs://aussortiert` | Aussortierte Jobs mit Begründung |
| `bewerbungen://alle` | Alle Bewerbungen mit Status |
| `bewerbungen://statistik` | Bewerbungsstatistiken |
| `config://suchkriterien` | Aktuelle Sucheinstellungen |

---

## Datenbank

SQLite mit WAL-Mode, 16 Kern-Tabellen + `user_preferences`, Schema v9:

| Tabelle | Beschreibung |
|---------|-------------|
| `profile` | Bewerberprofil + Präferenzen |
| `positions` | Berufserfahrung |
| `projects` | STAR-Projekte (→ positions) |
| `education` | Ausbildung |
| `skills` | Kompetenzen (5 Kategorien, Level, Aktualität) |
| `documents` | Hochgeladene Dokumente |
| `extraction_history` | Extraktions-Verlauf |
| `jobs` | Stellenangebote (9 Quellen) |
| `applications` | Bewerbungen (6 Status-Stufen) |
| `application_events` | Bewerbungs-Timeline |
| `search_criteria` | Suchfilter |
| `blacklist` | Ausschlussliste |
| `background_jobs` | Async-Tasks |
| `follow_ups` | Nachfass-Erinnerungen |
| `user_preferences` | Benutzereinstellungen |
| `suggested_job_titles` | Vorgeschlagene Jobtitel |
| `settings` | Konfiguration |

**Datenspeicherung:**
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\`
- Linux: `~/.bewerbungs-assistent/`

---

## Tests

```bash
# Setup
pip install -e ".[all,dev]"
playwright install chromium

# Alle Tests ausführen
python -m pytest tests/ -v

# 190 Tests, ~10 Sekunden
```

---

## Technologie-Stack

| Komponente | Technologie |
|-----------|-------------|
| **MCP Framework** | [FastMCP](https://github.com/jlowin/fastmcp) ≥2.0 |
| **Web Framework** | [FastAPI](https://fastapi.tiangolo.com/) ≥0.115 |
| **ASGI Server** | [Uvicorn](https://www.uvicorn.org/) ≥0.30 |
| **Datenbank** | SQLite (WAL Mode) |
| **PDF Export** | [fpdf2](https://github.com/py-pdf/fpdf2) ≥2.7 |
| **Word Export** | [python-docx](https://python-docx.readthedocs.io/) ≥1.1 |
| **PDF Import** | [pypdf](https://github.com/py-pdf/pypdf) ≥4.0 |
| **HTTP Client** | [httpx](https://www.python-httpx.org/) ≥0.27 |
| **HTML Parsing** | [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) ≥4.12 |
| **Browser Automation** | [Playwright](https://playwright.dev/python/) ≥1.40 |
| **Laufzeit** | Python ≥3.11 |

---

## Screenshots

### Dashboard — Übersicht mit Workspace-Guidance
![Dashboard](docs/screenshots/01_dashboard.png)

### Profil — Berufserfahrung, Skills, Ausbildung
![Profil](docs/screenshots/02_profil.png)

### Stellen — Scoring, Split-View und Fit-Analyse
![Stellen](docs/screenshots/03_stellen.png)

### Bewerbungen — Pipeline mit Timeline
![Bewerbungen](docs/screenshots/04_bewerbungen.png)

### Einstellungen — Suchkriterien und Quellen
![Einstellungen](docs/screenshots/05_einstellungen.png)

---

## Changelog

> Vollständiges Changelog: [CHANGELOG.md](CHANGELOG.md)

### v0.17.0 — Split-Layout, Distance-Scoring, Tailored CV (2026-03-12)
- **Dashboard Split-Layout**: Festanstellung | Freelance in zwei Spalten, umschaltbar
- **Angepasster Lebenslauf**: Neues Tool — Skills und Positionen nach Stellenrelevanz sortiert (DOCX)
- **Entfernung <30km bevorzugt**, Gehalts-Scoring, Kompetenzen-Match in Fit-Analyse
- **Next-Steps-Banner**, Skill-Navigation, profil_bearbeiten erweitert
- **GitHub Issues**: 42→11 offen — 31 Issues geschlossen
- 54 Tools, 190 Tests

### v0.16.0 — Skill-Aktualität & Jobtitel-Vorschläge (2026-03-12)
- Skills tracken `last_used_year` — veraltete Skills werden erkannt
- Automatische Jobtitel-Vorschläge aus Profil und Dokumenten
- Schema v9, 53 Tools

### v0.15.0 — Batch-Analyse & Bewerbungs-Erkennung (2026-03-12)
- Batch-Analyse für viele Dokumente, automatische Bewerbungs-Erkennung
- Summary-Bug behoben, Workflows als Tools
- 51 Tools, 190 Tests

---

## FAQ

**Brauche ich einen Claude Pro Account?**
Nein — PBP funktioniert mit jedem Claude Desktop Account. Ein Pro-Account hat höhere Nutzungslimits, was bei vielen Jobsuchen hilfreich sein kann.

**Werden meine Daten in die Cloud geschickt?**
Deine Profildaten, Bewerbungen und Dokumente bleiben lokal auf deinem Rechner (SQLite). Wenn du Claude nutzt (Gespräch, Anschreiben, Fit-Analyse), werden die relevanten Daten an Claude gesendet — wie bei jeder normalen Claude-Konversation.

**Kann ich PBP ohne Jobportale nutzen?**
Ja! Du kannst PBP auch nur für Profilerstellung, Lebenslauf-Export und Bewerbungstracking nutzen, ganz ohne Stellensuche.

**Was passiert, wenn ein Portal sich ändert?**
Scraper können brechen wenn Portale ihr Layout ändern. PBP fängt Fehler ab und überspringt defekte Quellen — die anderen laufen weiter. Updates werden über neue Releases bereitgestellt.

**Unterstützt PBP mehrere Sprachen?**
Die Oberfläche und Workflows sind auf Deutsch. Jobtitel werden auf Deutsch und Englisch vorgeschlagen. Claude selbst kann in jeder Sprache kommunizieren.

---

## Lizenz

[MIT License](LICENSE) — Markus Birzite

---

## Autor

**Markus Birzite** — PLM/PDM Systemarchitekt
