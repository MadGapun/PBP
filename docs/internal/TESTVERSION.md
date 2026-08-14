# PBP Bewerbungs-Assistent — Testversion

## Voraussetzungen

### Windows (Zielplattform)
```
Python >= 3.11 (python.org oder Microsoft Store)
pip (kommt mit Python)
Claude Desktop (claude.ai/download)
```

### Linux (Entwicklung)
```
Python >= 3.11
pip
```

---

## Installation

### Option A: Windows Installer (empfohlen)
1. [Neueste Version](https://github.com/MadGapun/PBP/releases/latest) als ZIP herunterladen
2. ZIP entpacken (z.B. nach `C:\PBP`)
3. `INSTALLIEREN.bat` doppelklicken — der Rest passiert automatisch

### Option B: Schnell (nur Core + Dashboard)
```bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
pip install -e .
```

### Option C: Mit Scraper + Dokument-Import
```bash
pip install -e ".[all]"
playwright install chromium
```

### Option D: Entwicklung
```bash
pip install -e ".[all,dev]"
playwright install chromium
python -m pytest tests/ -v    # 187 Tests
```

---

## Testversion starten

### Dashboard starten:
```bash
python start_dashboard.py
# Oeffne: http://localhost:5173
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
      "env": {
        "BA_DATA_DIR": "C:\\Users\\DEIN_NAME\\AppData\\Local\\BewerbungsAssistent"
      }
    }
  }
}
```

---

## Was die Testversion zeigt

### 5 Dashboard-Tabs:
1. **Dashboard** — Uebersicht mit Workspace-Guidance und Statistiken
2. **Profil** — Profilbearbeitung mit Positionen, STAR-Projekten, Skills, Ausbildung
3. **Stellen** — Stellenangebote mit Scoring und Fit-Analyse
4. **Bewerbungen** — Pipeline-Ansicht mit Timeline und Follow-ups
5. **Einstellungen** — Suchkriterien, Blacklist, Quellen, Expertenmodus

### Aktionen zum Testen:
- Profil bearbeiten und vervollstaendigen
- Position/Skill/Ausbildung hinzufuegen
- Stelle aussortieren + wiederherstellen
- Fit-Analyse einer Stelle ansehen (Score-Aufschluesselung)
- Bewerbungsstatus aendern
- CV-Generator testen (PDF/DOCX)
- Suchkriterien anpassen (Keywords, Gewichtung)
- Dokumente hochladen und extrahieren lassen
- Factory Reset in den Einstellungen

---

## Datenspeicherung

| Plattform | Pfad |
|-----------|------|
| Windows | `%LOCALAPPDATA%\BewerbungsAssistent\` |
| Linux | `~/.bewerbungs-assistent/` |
| Alternativ | Umgebungsvariable `BA_DATA_DIR` |

Unterverzeichnisse: `dokumente/`, `export/`, `logs/`

---

## Bekannte Einschraenkungen
- Job-Scraper braucht `beautifulsoup4`, `lxml` und `playwright` (optionale Pakete)
- Kein Auth (localhost-only, kein Sicherheitsrisiko)
- LinkedIn-Scraper braucht manuellen Erstlogin
- MCP-Registry-Tests (`test_mcp_registry.py`) benoetigen `fastmcp`
