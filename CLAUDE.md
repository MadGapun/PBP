# PBP — Claude-Code-Memory

Persoenliches Bewerbungs-Portal (PBP). MCP-Server (Python/FastMCP) +
React-Frontend + SQLite. v1.6.5 ist Latest auf GitHub.

## Release-Workflow (Pflicht-Checkliste)

Bevor ein neuer Release gebaut wird:

1. **Versionen bumpen** an drei Stellen:
   - `pyproject.toml`
   - `src/bewerbungs_assistent/__init__.py`
   - `frontend/package.json`
2. **Schema-Migration** ALTER-only (keine Daten-Migrationen). `SCHEMA_VERSION` in
   `database.py` hochziehen, neue Spalten in `_migrate` UND in `SCHEMA_SQL`
   (CREATE TABLE) ergaenzen.
3. **Tests gruen:** mindestens
   `pytest tests/test_v16*_*.py tests/test_database.py tests/test_mcp_registry.py`.
4. **Frontend rebuild:** `cd frontend && pnpm exec vite build`. Built-Assets unter
   `src/bewerbungs_assistent/static/dashboard/assets/` mit committen, alte
   Hash-Dateien `git rm`-en.
5. **CHANGELOG.md** erweitern: neuer Eintrag GANZ OBEN (vor v1.6.4),
   Sektionen Added/Changed/Fixed nach Keep-a-Changelog. Am ENDE des Eintrags
   IMMER die volle Installationsanleitung (siehe Pflicht-Block unten).
6. **Pre-Release-Pause:** vor `git commit` einmal kurz reflektieren (Risiko-
   Tabelle pro Issue, was kann brechen, was ist nur additiv) und nochmal
   testen. User hat das explizit eingefordert.
7. **Erst nach OK** committen, taggen, pushen, GH-Release erstellen.

## GitHub-Release-Notes — Pflicht-Block

**Jeder GitHub-Release MUSS die volle Installationsanleitung in den
Release-Notes selbst enthalten — NICHT nur als Link aufs CHANGELOG.**

Hintergrund: Viele Anwender klicken auf den Release, sehen "Source code
(zip/tar.gz)" und wissen nicht, was sie damit anfangen sollen. Die
Anleitung muss dort stehen, wo der User landet.

Template (am Ende der Release-Notes einfuegen, Versionsnummer ersetzen):

```markdown
---

## 📦 Wie installiere oder aktualisiere ich PBP?

Du brauchst **kein Git, kein Python, kein Vorwissen** — nur einen ZIP-Download und einen Doppelklick. Voraussetzung: [Claude Desktop](https://claude.ai/download) ist installiert.

### Windows (empfohlen, bequemster Weg)

1. **ZIP herunterladen:** [PBP-X.Y.Z.zip](https://github.com/MadGapun/PBP/archive/refs/tags/vX.Y.Z.zip)
2. **Entpacken:** Rechtsklick auf die ZIP → *„Alle extrahieren..."* → Zielordner waehlen (z.B. `C:\PBP`)
3. **Installieren:** Im entpackten Ordner Doppelklick auf **`INSTALLIEREN.bat`**
4. Das Setup laedt Python, alle Pakete und Chromium herunter (~3–5 Minuten) und konfiguriert Claude Desktop.
5. Auf dem Desktop liegt jetzt eine Verknuepfung **„PBP Bewerbungs-Portal"** — Doppelklick startet das Dashboard.

### macOS

1. **ZIP herunterladen** (siehe Windows-Link)
2. **Entpacken** (Doppelklick reicht)
3. **Doppelklick auf `INSTALLIEREN.command`**
4. Falls macOS warnt: Rechtsklick auf die Datei → *„Oeffnen"*

### Linux

\`\`\`bash
git clone https://github.com/MadGapun/PBP.git
cd PBP
bash installer/install.sh
\`\`\`

### Update von einer aelteren Version

**Einfach drueberinstallieren** — deine Daten bleiben erhalten:
- Windows: `%LOCALAPPDATA%\BewerbungsAssistent\data\pbp.db`
- macOS/Linux: `~/.bewerbungs-assistent/pbp.db`

Schema-Upgrade laeuft automatisch beim ersten Start, ein Backup wird vorher erstellt (Ordner `data\backups\`).

### Detaillierte Anleitung & Troubleshooting

📖 [Wiki → Installation](https://github.com/MadGapun/PBP/wiki/Installation) · [FAQ](https://github.com/MadGapun/PBP/wiki/FAQ)
```

Derselbe Block gehoert auch ans Ende des CHANGELOG-Eintrags (Pflicht ab v1.6.4).

## GitHub CLI — Token-Falle

`gh` nutzt sonst den `GITHUB_TOKEN` aus dem Env mit eingeschraenkten Scopes.
Vor `gh`-Aufrufen IMMER `unset GITHUB_TOKEN` setzen, damit der Keyring-
Token mit Repo-Scope greift:

```bash
unset GITHUB_TOKEN; gh release create vX.Y.Z --title "..." --notes-file ... --latest
unset GITHUB_TOKEN; gh issue close 123 --comment "..."
```

## Tag-Lock-Falle (immutable releases)

GitHub Releases sind tag-gelocked: ein Release zu einem existierenden Tag
laesst sich NICHT mehr neu erstellen, nur editieren. v1.6.0/v1.6.1 wurden
durch das verbrannt. Konsequenzen:

- Vor `git tag` SICHER sein, dass alles drin ist (Frontend gebaut, Tests
  gruen, CHANGELOG aktuell).
- Bei kaputtem Release: NICHT taglock loesen — neue Patch-Version (vX.Y.Z+1)
  veroeffentlichen.

## Bericht-Designprinzip (v1.6.8)

**Kennzahlen, deren Datenbasis nicht zuverlaessig ist, kommen nicht in den
Bewerbungsbericht.** Lieber eine Sektion weglassen als eine irrefuehrende
Zahl drucken. Konkrete Faelle aus v1.6.8:

- „Aktive Filter-Arbeit" suggerierte „nur 1 wuerdig" — vergass dass viele
  Bewerbungen ueber Direct-Add aus dem Chat kommen, nicht ueber
  `stelle_bewerten('passt')`. Raus.
- „Geschaetzter Zeitaufwand" mit 30min/Bewerbung war Groessenordnungen
  unter Realwert (Stunden bis Tage pro Stelle inkl. Anschreiben-Iteration,
  Format-/Umlaut-Korrekturen, Interview-Vorbereitung). Raus.
- „Bewerbungs-Trichter" stufte aussortiert+beworben in sich
  widerspruechlich, weil Bewerbungen auch von ausserhalb des gesichteten
  Pools kommen. Raus.

Bevor eine neue Kennzahl in den Bericht eingebaut wird: pruefen, ob die
Datenbasis ALLE Pfade abdeckt, die zu dem Wert beitragen. Wenn nein:
weglassen.

## Anti-DB-Bypass-Pattern (#514)

Claude darf NICHT direkt in die SQLite schreiben. Alle Mutationen laufen
ueber MCP-Tools (`stelle_bewerten`, `stellen_bulk_bewerten`, `bewerbung_*`)
damit Lifecycle (Audit, dismiss_counts, Lerneffekt, Statistik) konsistent
durchlaeuft.

Server-Instructions in `server.py` machen das transparent. `pbp_capabilities`
und `pbp_grenze_melden` decken Edge-Cases ab.

## Kritische DB-Helfer

- `db.dismiss_job(hash, reason)` — nutzt `resolve_job_hash` intern, scoped Hash
  korrekt. NICHT roh `UPDATE jobs SET is_active=0 WHERE hash=?` ausfuehren —
  Hash ist mit `{profile_id}:` praefixed, das matcht sonst nicht.
- `db.update_job(hash, fields)` — Whitelist-Filter im Inneren. Wenn ein neues
  Feld nicht durchkommt, `_ALLOWED_UPDATE_FIELDS` erweitern.

## Mojibake-Repair

Doppelt-kodiertes UTF-8 als Latin-1 reparieren:
`s.encode('latin-1').decode('utf-8')`. Trat in `dashboard.py` an 47 Stellen
auf (v1.6.4-Fix).

## Test-Helper fuer FastMCP 2.12+

`mcp.call_tool` existiert in 2.12 nicht mehr. Stattdessen:

```python
def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())
```

(In `tests/test_v164_bugfixes.py`, `tests/test_v165_drift_fixes.py`,
`tests/test_v165_quickfixes.py` jeweils dupliziert — bei Bedarf zentralisieren.)
