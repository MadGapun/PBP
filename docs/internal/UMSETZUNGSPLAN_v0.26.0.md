# Umsetzungsplan v0.26.0 — Filtering, Scoring, UX

**Erstellt:** 2026-03-20 (Prompt 056, Testprotokoll v0.25.2)
**Issues:** #114, #115, #116, #118, #119, #120, #121, #122, #103, #105, #106, #108, #111, #112
**Roadmap (nicht in v0.26.0):** #28, #104, #107, #109, #117

---

## Uebersicht

| Phase | Issues | Kern-Idee | Abhaengigkeiten |
|-------|--------|-----------|-----------------|
| **1** | #121, #118, #114 | Filtering reparieren | Keine — muss zuerst |
| **2** | #120, #108, #112, #105 | Bewertung + Scoring | Braucht Phase 1 |
| **3** | #116, #119, #111, #106 | Quick Wins UX | Unabhaengig, parallel moeglich |
| **4** | #122, #115, #103 | UX + Compliance | Unabhaengig |

---

## Phase 1: Bug-Cluster "Filtering"

**Ziel:** Stellen-Anzeige zeigt nur was relevant ist.

### 1a — Blacklist-Filter (#121)
- **Datei:** `database.py` (`get_active_jobs()`)
- **Aenderung:** JOIN auf `blacklist` WHERE type='firma', Stellen von geblacklisteten Firmen ausschliessen
- **Aufwand:** Klein

### 1b — Bereits bearbeitete Stellen ausfiltern (#118)
- **Dateien:** `dashboard.py` (API), `jobs.py` (`stellen_anzeigen()`)
- **Aenderung:** API-Endpoint `/api/jobs` muss filtern: bereits beworbene + "passt_nicht" Stellen nicht in aktiver Liste
- **Hinweis:** `stellen_anzeigen()` filtert teilweise schon (jobs.py:200-205), aber der Dashboard-API-Endpoint tut es nicht
- **Aufwand:** Mittel

### 1c — Zaehler korrigieren (#114)
- **Dateien:** `dashboard.py`, `JobsPage.jsx`
- **Aenderung:** `anzahl_gesamt` muss NACH dem Filtern berechnet werden, nicht vorher
- **Aufwand:** Klein

### Architektur-Entscheidung
Zentrale Filter-Funktion in `database.py`, die von `stellen_anzeigen()` UND Dashboard-API genutzt wird.
Parameter: `exclude_blacklisted=True, exclude_applied=True, exclude_dismissed=True`.
Verhindert, dass MCP-Tools und Frontend unterschiedlich filtern.

### Tests Phase 1
- [ ] Stelle anlegen → Firma blacklisten → Stelle verschwindet (API + Tool)
- [ ] Stelle "passt_nicht" → verschwindet aus aktiver Liste, Zaehler aktualisiert
- [ ] Auf Stelle bewerben → verschwindet aus Stellen-Uebersicht
- [ ] Zaehler oben == Anzahl sichtbarer Stellen in Liste

---

## Phase 2: "Passt nicht"-Begruendung + Scoring

### 2a — Begruendung als Pflicht (#120)
- **Dateien:** `JobsPage.jsx`, `jobs.py`, `dashboard.py`
- **Aenderung:** Frontend: Modal mit Ablehnungsgruenden. Backend: `grund` als Pflichtfeld bei "passt_nicht"
- **Aufwand:** Mittel

### 2b — Ablehnungsgruende Multi-Select (#108)
- **Dateien:** `database.py`, `jobs.py`, `JobsPage.jsx`
- **Aenderung:** Von Single-Select auf Multi-Select. Neue `dismiss_reasons`-Tabelle (Schema v13)
- **Aufwand:** Mittel

### 2c — Entfernungs-Malus Freelance (#112)
- **Datei:** `job_scraper/__init__.py` (`calculate_score()`)
- **Aenderung:** Freelance → Malus aufheben/stark reduzieren, Festanstellung → wie bisher
- **Aufwand:** Klein

### 2d — Score-Anpassung nach Fit-Analyse (#105)
- **Dateien:** `job_scraper/__init__.py`, `jobs.py`
- **Aenderung:** Wenn Fit-Analyse gelaufen, Score-Komponenten nachjustieren
- **Aufwand:** Mittel

### Schema-Migration v13
Neue Tabelle `dismiss_reasons`:
```sql
CREATE TABLE dismiss_reasons (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    is_custom INTEGER DEFAULT 0,
    usage_count INTEGER DEFAULT 0,
    profile_id TEXT,
    created_at TEXT
);
```
Vorbefuellt mit bestehenden Gruenden. `jobs.dismiss_reason` bleibt TEXT, speichert JSON-Array.

### Tests Phase 2
- [ ] "Passt nicht" ohne Grund → wird abgelehnt (Frontend + Backend)
- [ ] Mehrere Gruende auswaehlbar, korrekt gespeichert
- [ ] Freelance 300km → kein/kaum Entfernungs-Malus
- [ ] Festanstellung 300km → voller Malus
- [ ] Benutzerdefinierter Grund anlegen → erscheint bei naechster Bewertung

---

## Phase 3: Quick Wins (UX)

### 3a — Jobsuche-Button in Stellen (#116)
- **Datei:** `JobsPage.jsx`
- **Aenderung:** "Jobsuche starten"-Button, prominent wenn Liste leer
- **Aufwand:** Klein

### 3b — Quell-Link + Beschreibungspflicht (#119)
- **Dateien:** `ApplicationsPage.jsx`, `bewerbungen.py`, `dashboard.py`
- **Aenderung:** URL als klickbarer Link in Bewerbungsliste. `bewerbung_erstellen()` prueft Beschreibung
- **Aufwand:** Klein-Mittel

### 3c — Farbliche Unterscheidung (#111)
- **Dateien:** `JobsPage.jsx`, `ApplicationsPage.jsx`
- **Aenderung:** Farbiges Badge: blau=Festanstellung, gruen=Freelance
- **Aufwand:** Klein

### 3d — Vorsortierung ohne Bewertung (#106)
- **Dateien:** `jobs.py`, `JobsPage.jsx`
- **Aenderung:** Score anzeigen, aber keine automatische passt/passt-nicht-Empfehlung
- **Aufwand:** Klein

### Tests Phase 3
- [ ] Jobsuche-Button sichtbar und funktional
- [ ] Bewerbungsliste zeigt klickbare Quell-Links
- [ ] Bewerbung ohne Beschreibung → Fehlermeldung
- [ ] Freelance-Badge gruen, Festanstellung blau
- [ ] Stellen ohne automatische Bewertung praesentiert

---

## Phase 4: UX & Compliance

### 4a — Sticky Sidebar Profil (#122)
- **Datei:** `ProfilePage.jsx`, CSS
- **Aenderung:** Linke Navigation mit Anker-Links, `position: sticky`
- **Aufwand:** Mittel

### 4b — Rechtlicher Hinweis + Hilfe (#115)
- **Dateien:** `HelpDialog.jsx` o.ae., Credits-Section
- **Aenderung:** Disclaimer zu Scraping, Link zur GitHub-Doku
- **Aufwand:** Klein-Mittel

### 4c — Unanalysierte Dokumente anbieten (#103)
- **Datei:** `tools/profil.py`
- **Aenderung:** Bei `/profil_erweiterung` pruefen und automatisch anbieten
- **Aufwand:** Klein

### Tests Phase 4
- [ ] Profil-Sidebar bleibt sticky, Links springen korrekt
- [ ] Credits zeigen Disclaimer
- [ ] Hilfe enthaelt Link zur GitHub-Doku
- [ ] Profil-Erweiterung mit unanalysierten Docs → Hinweis erscheint
