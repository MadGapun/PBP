# PBP Bewerbungs-Assistent — Testversion

## Voraussetzungen

### Windows (Zielplattform)
```
Python >= 3.11 (python.org oder Microsoft Store)
pip (kommt mit Python)
```

### Linux / ELWOSA Server (Entwicklung)
```
Python >= 3.11
pip
```

---

## Installation

### Option A: Schnell (nur Core + Dashboard)
```bash
cd /home/chatgpt/pbp/bewerbungs-assistent
pip install -e .
```

### Option B: Mit Scraper + Dokument-Import
```bash
pip install -e ".[all]"
# Fuer LinkedIn-Scraping zusaetzlich:
playwright install chromium
```

### Option C: Entwicklung
```bash
pip install -e ".[all,dev]"
playwright install chromium
```

### Einzelne optionale Pakete
```bash
# Job-Scraper (StepStone, Hays, etc.)
pip install beautifulsoup4 lxml playwright

# Dokument-Import (PDF/DOCX)
pip install pypdf python-docx
```

---

## Testversion starten

### Dashboard mit Demo-Daten:
```bash
python /tmp/pbp_testrun.py
# Oeffne: http://localhost:8200
```

### MCP Server (fuer Claude Desktop):
```bash
bewerbungs-assistent
# Oder: python -m bewerbungs_assistent
```

### Claude Desktop Konfiguration (Windows):
In `%APPDATA%\Claude\claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "bewerbungs-assistent": {
      "command": "python",
      "args": ["-m", "bewerbungs_assistent"],
      "env": {}
    }
  }
}
```

---

## Was die Testversion zeigt

### 5 Dashboard-Tabs:
1. **Dashboard** — Uebersicht (3 Stellen, 1 Bewerbung, Statistiken)
2. **Profil** — Demo-Profil mit Positionen, STAR-Projekt, Skills, Ausbildung
3. **Stellen** — 3 Demo-Stellenangebote mit Scores und Fit-Analyse
4. **Bewerbungen** — 1 Demo-Bewerbung mit Timeline
5. **Einstellungen** — Suchkriterien und Gewichtungen

### Aktionen zum Testen:
- Profil bearbeiten (Klick auf "Bearbeiten")
- Position/Skill/Ausbildung hinzufuegen
- Stelle aussortieren + wiederherstellen
- Fit-Analyse einer Stelle ansehen (Score-Aufschluesselung)
- Bewerbungsstatus aendern
- CV-Generator testen
- Suchkriterien anpassen (Keywords, Gewichtung)

---

## Daten

| Pfad | Inhalt |
|------|--------|
| Linux: `~/.bewerbungs-assistent/` | SQLite DB + Dokumente |
| Windows: `%LOCALAPPDATA%\BewerbungsAssistent\` | SQLite DB + Dokumente |
| Testversion: `/tmp/pbp_testversion/` | Temporaere Demo-Daten |

---

## Bekannte Einschraenkungen
- Job-Scraper nicht getestet auf Server (braucht bs4/playwright)
- Kein Auth (localhost-only, kein Sicherheitsrisiko)
- LinkedIn-Scraper braucht manuellen Erstlogin
