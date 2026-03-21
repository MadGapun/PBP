# PBP v1.0.0 — Release-Entwurf

> Dieses Dokument ist der vorbereitete Release-Text für den GitHub-Release am 22. März 2026.

---

## Release-Text (für `gh release create`)

```
# PBP v1.0.0 — Persönliches Bewerbungs-Portal

Der erste offizielle Release. PBP verwaltet deine Bewerbungen, durchsucht diverse
Stellenportale und gibt dir ehrliches Feedback zu deinen Unterlagen — mit konkreten
Vorschlägen, wie es besser geht. Läuft lokal, kostet nichts, deine Daten bleiben bei dir.

## Was steckt drin

- **66 MCP-Tools** in 8 Modulen (Profil, Dokumente, Jobs, Bewerbungen, Analyse, Export, Suche, Workflows)
- **14 MCP-Prompts** — von Ersterfassung über Interview-Simulation bis Gehaltsverhandlung
- **17 Jobquellen** — Bundesagentur, StepStone, LinkedIn, XING, Indeed, Monster, Hays und 10 weitere
- **E-Mail-Integration** — .eml/.msg Import, automatisches Matching, Meeting-Extraktion mit Kalender-Widget
- **React 19 Dashboard** — 7 Bereiche mit Drag & Drop, Live-Updates, Statistik-Charts (Recharts)
- **PDF/DOCX-Export** — Lebenslauf und Anschreiben in professionellem Layout
- **Multi-Profil** — Mehrere Profile mit vollständiger Daten-Isolation
- **317 Tests** — alle grün
- **Zero-Knowledge Installer** — `INSTALLIEREN.bat` doppelklicken und loslegen

## Schnellstart

```bat
:: Windows — Doppelklick auf:
INSTALLIEREN.bat

:: Oder manuell:
pip install -e ".[all]"
playwright install chromium
```

Danach in Claude Desktop: **"Ersterfassung starten"**

## Versionshistorie

PBP wurde seit März 2026 in 30+ inkrementellen Releases entwickelt (v0.1.0 → v0.30.0).
Ein früherer `v1.0.0`-Tag vom 2. März 2026 wurde entfernt — er zeigte auf einen frühen
Prototyp-Stand (21 Tools) und entsprach nicht dem Reifegrad eines 1.0-Produkts.

## Credits

- **Markus Birzite** — Konzept, Architektur, Projektleitung
- **Claude (Anthropic)** — Hauptentwickler seit v0.1.0
- **Codex (OpenAI)** — Code-Analyse, Recovery, Bugfixes
- **Toms (@Koala280)** — React 19 Frontend, UX-Issues
- **ELWOSA** — Projektrahmen und Infrastruktur
```

---

## Release-Checkliste für Markus (22. März 2026)

### Voraussetzungen (✅ bereits erledigt)
- [x] PR #150 gemergt (Versions-Metadaten synchron)
- [x] ZUSTAND.md auf v0.30.0 aktualisiert
- [x] architecture.md auf v0.30.0 aktualisiert
- [x] codex_context.md auf v0.30.0 aktualisiert
- [x] DOKUMENTATION.md: Port, Quellen, Tools, Schema korrigiert
- [x] CHANGELOG.md: v1.0.0 Eintrag vorbereitet
- [x] Security-Audit: Keine API-Keys/Passwörter/private Daten
- [x] 317 Tests grün
- [x] Frontend-Build verifiziert
- [x] Issue #148 (Doku-Drift) → durch Doku-Updates adressiert
- [x] Issue #149 (v1.0.0 Historie) → Entscheidung: Option A (löschen + neu)

### Morgen auszuführen (in dieser Reihenfolge)

**Schritt 1: Altes v1.0.0 entfernen**
```bash
cd /home/chatgpt/PBP

# GitHub Release löschen
gh release delete v1.0.0 --repo MadGapun/PBP --yes

# Git-Tag lokal und remote löschen
git tag -d v1.0.0
git push origin :refs/tags/v1.0.0
```

**Schritt 2: Version bumpen (0.30.0 → 1.0.0)**
```bash
# pyproject.toml
sed -i 's/version = "0.30.0"/version = "1.0.0"/' pyproject.toml

# __init__.py
sed -i 's/__version__ = "0.30.0"/__version__ = "1.0.0"/' src/bewerbungs_assistent/__init__.py

# AGENTS.md
sed -i 's/Version:** 0.30.0/Version:** 1.0.0/' AGENTS.md
```

**Schritt 3: Frontend neu bauen**
```bash
sudo rm -rf src/bewerbungs_assistent/static/dashboard/assets
cd frontend && pnpm run build:web && cd ..
sudo chown -R chatgpt:chatgpt src/bewerbungs_assistent/static/
```

**Schritt 4: Tests**
```bash
python -m pytest tests/ -q
```

**Schritt 5: Commit + Tag**
```bash
git add -A
git commit -m "release: PBP v1.0.0 — Erster offizieller Release

66 Tools, 14 Prompts, 17 Jobquellen, E-Mail-Integration,
React 19 Dashboard, Multi-Profil, Schema v15, 317 Tests.

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>"

git tag -a v1.0.0 -m "PBP v1.0.0 — Persönliches Bewerbungs-Portal"
git push origin main --tags
```

**Schritt 6: GitHub Release erstellen**
```bash
gh release create v1.0.0 \
  --repo MadGapun/PBP \
  --title "PBP v1.0.0 — Persönliches Bewerbungs-Portal" \
  --notes-file docs/RELEASE_v1.0.0_DRAFT.md \
  --latest
```

**Schritt 7: Issues schließen**
```bash
gh issue close 148 --repo MadGapun/PBP --comment "Dokumentation auf v0.30.0/1.0.0 synchronisiert."
gh issue close 149 --repo MadGapun/PBP --comment "Historisches v1.0.0 entfernt. Neues v1.0.0 veröffentlicht."
```

### Risiken

| Risiko | Einschätzung | Mitigation |
|--------|-------------|------------|
| Altes v1.0.0 löschen bricht Links | **Gering** — Privates Repo, keine externen Nutzer | Links zeigen auf neues v1.0.0 |
| Frontend-Build schlägt fehl | **Gering** — Build heute erfolgreich getestet | Backup: statische Assets vom letzten Build |
| Tests schlagen fehl nach Version-Bump | **Sehr gering** — Version ist nur in Metadaten | test_dashboard.py prüft Version-Feld |

### Nach dem Release

- [ ] README Badge-Version auf 1.0.0 prüfen
- [ ] ELWOSA PM aktualisieren (PBP-053 Task anlegen)
- [ ] MEMORY.md aktualisieren
- [ ] Repo ggf. auf public stellen (falls gewünscht)
