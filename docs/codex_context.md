# PBP Codex Context

Dieses Dokument gibt KI-Assistenten den noetigen Kontext fuer PBP.

---

## Was ist PBP?

PBP (Persoenliches Bewerbungs-Portal) ist ein MCP-Server fuer Claude Desktop.
Er unterstuetzt den gesamten Bewerbungsprozess: Profil-Erstellung,
Jobsuche (8 Portale), Bewertung, Dokument-Export und Bewerbungs-Tracking.

**Version:** 0.11.0 (alle Features und Optimierungen abgeschlossen)

---

## Quelldateien

| Datei | Zeilen | Beschreibung |
|-------|--------|-------------|
| `src/bewerbungs_assistent/server.py` | 3261 | MCP-Server: 44 Tools, 6 Resources, 12 Prompts |
| `src/bewerbungs_assistent/database.py` | 1635 | SQLite-Datenbankschicht (15 Tabellen, Schema v8) |
| `src/bewerbungs_assistent/dashboard.py` | 1029 | Web-Dashboard (FastAPI, Port 8200) |
| `src/bewerbungs_assistent/export.py` | 365 | PDF/DOCX-Export (Lebenslauf, Anschreiben) |
| `src/bewerbungs_assistent/job_scraper/__init__.py` | 600 | Scraper-Framework (8 Portale) |
| `src/bewerbungs_assistent/job_scraper/*.py` | ~350ea | Einzelne Portal-Scraper |
| `src/bewerbungs_assistent/templates/dashboard.html` | — | Dashboard-Template |
| `tests/` | ~1400 | 100 Tests (pytest) |

## Wichtige Dateien im Root

| Datei | Beschreibung |
|-------|-------------|
| `pyproject.toml` | Package-Definition, Dependencies, Build-Config |
| `INSTALLIEREN.bat` | Windows Zero-Knowledge Installer |
| `Dashboard starten.bat` | Dashboard-Starter fuer Windows |
| `README.md` | Hauptdokumentation |
| `DOKUMENTATION.md` | Detaillierte Nutzerdokumentation |
| `CHANGELOG.md` | Aenderungshistorie (v0.1.0 bis v0.11.0) |
| `OPTIMIERUNGEN.md` | Optimierungs-Tracking |
| `ZUSTAND.md` | Aktueller Projektzustand |
| `TESTVERSION.md` | Testversions-Info |

---

## Abhaengigkeiten

### Pflicht (in pyproject.toml)
```
fastmcp>=2.0
uvicorn>=0.30
fastapi>=0.115
python-multipart>=0.0.9
httpx>=0.27
```

### Optional
```
# Scraper
playwright>=1.40
beautifulsoup4>=4.12
lxml>=5.0

# Dokument-Export
python-docx>=1.1
pypdf>=4.0
fpdf2>=2.7

# Entwicklung
pytest>=8.0
pytest-asyncio>=0.23
```

---

## Projekt-Status

**Komplett abgeschlossen.** Alle 18 Tasks und 13 Optimierungen sind done.

### Letzte Aenderungen (v0.11.0)
- Form-Validierung (Client + Server, Pflichtfelder, E-Mail-Check)
- Ladeanimationen (Spinner + Loading-Buttons)
- Paginierung Bewerbungen (20er Seiten + "Mehr laden")
- Bugfix: extraktion_anwenden mit auto_apply=True Standard
- Bugfix: Profilname bei Extraktion nicht mehr ueberschrieben
- Bugfix: Projekte bei doppelten Positionen + standalone Projekte

### Bekannte Einschraenkungen
- Kein Multi-User-System (einzelne SQLite-DB)
- Scraper abhaengig von Portal-Struktur (kann brechen)
- Playwright-Installation unter Windows manchmal umstaendlich

---

## Build & Test

```bash
# Installation
pip install -e ".[all,dev]"

# Tests ausfuehren
pytest tests/ -v

# MCP-Server starten (fuer Claude Desktop)
bewerbungs-assistent
# oder
python -m bewerbungs_assistent

# Dashboard separat starten
python start_dashboard.py
```

---

## Beziehung zu ELWOSA

PBP ist ein **eigenstaendiges Projekt**. Es wurde auf dem ELWOSA-Server
entwickelt und die Release-ZIPs werden ueber den ELWOSA Voice Backend
Static-Server ausgeliefert, aber es gibt keine Code-Abhaengigkeit.

Siehe [docs/dependency_on_elwosa.md](dependency_on_elwosa.md) fuer Details.

---

*Stand: 06.03.2026*
