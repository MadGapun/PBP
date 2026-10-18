# Entwurf: CHANGELOG-Einträge zu #1238 (Installer behalten die eigenen Einstellungen)

> **Kein Teil des CHANGELOG.** Der Text gehört in den Eintrag der Version, die die Korrektur ausliefert. 1.8-Linie: dieser Zweig auf `release/v1.8.0`
> (Eintrag `[1.8.0]`, Abschnitt „Fixed“). Stable: Zweig `fix/installer-env-erhalten-1238-v17` vom Tag v1.7.158 (ein Commit, für `hotfix/v1.7.159`
> oder einen späteren Hotfix). Nummer und Datum beim Release einsetzen, danach diese Datei löschen. Der Text für Stable liegt in der Übergabenotiz
> der Sitzung (`changelog-eintrag-1238-stable.md`); er nennt zusätzlich `install.ps1`, das es in dieser Linie nur noch als Stub gibt (#1149).
>
> Belegt: `tests/test_1238_installer_env_erhalten.py` (53 Tests; 35 laufen in dieser Linie, 18 überspringen sich, weil `install.ps1` hier ein Stub
> ist), Gegenprobe Katalog `claude_konfig` (14 von 14 erkannt, `scripts/mutationstest_auto_update.py --katalog claude_konfig`).

---

## Eintrag (Titelvorschlag)

**Eigene Einstellungen im PBP-Eintrag von Claude Desktop bleiben beim Überinstallieren erhalten**

<!-- anwender -->
Was du in der Konfiguration von Claude Desktop beim Eintrag von PBP selbst ergänzt hast, etwa einen verlegten Datenordner oder einen eigenen Port, bleibt beim Überinstallieren erhalten, auch wenn du PBP mit dem Setup mit Fenster installierst. Bisher galt das nur für `INSTALLIEREN.bat`, `INSTALLIEREN.command` und `install.sh`.
<!-- /anwender -->

Wer unter `env` des Eintrags `bewerbungs-assistent` etwas ergänzt hatte (ein verlegter Datenordner, ein Port, der Schlüssel des optionalen API-Wegs,
#1236), verlor es beim Überinstallieren ohne Hinweis. Die Installer `INSTALLIEREN.bat`, `INSTALLIEREN.command` und `installer/install.sh` gehen über
`_setup_claude.py` und gaben das `env` seit v1.7.145 weiter (#1136); zwei andere Schreiber der Konfiguration bauten den Eintrag jedes Mal neu.

**Wichtig zu wissen:**

- **Eine Regel für alle Schreiber** (wie `_setup_claude.eintrag_bauen`): Was im bisherigen `env` steht, bleibt. `BA_DATA_DIR` wird nur gesetzt,
  wenn keiner da ist; `PYTHONPATH` folgt immer der Installation. Das Setup mit Fenster nimmt einen alten `PYTHONPATH` heraus (es installiert
  editierbar und braucht keinen; ein alter würde den alten Programmstand laden).
- **`install.ps1` ist in dieser Linie ein Stub** (#1149) und fasst die Konfiguration nicht an; die Korrektur dort gibt es nur in der Stable-Linie
  (v1.7.x), wo der PowerShell-Installer noch läuft. Ein Test hält beides fest: der volle Installer führt die Funktionstests aus, der Stub darf
  die Konfiguration nicht nennen.
- **Im Programm selbst kommt die Konfiguration von Claude Desktop nicht vor**, auch nicht im Weg des Auto-Updates (er schaltet `aktuell.txt` um und
  fasst die Konfiguration nicht an): ein Test sucht in `src/` danach.
- **Eine neue Stelle, die den Eintrag schreibt, fällt auf:** ein Test listet alle Dateien, die den Server-Block der Konfiguration anfassen, und
  schlägt bei jeder unbekannten an.

### Fixed

- **`installer/setup_gui.py` (Setup mit Fenster) baute den Eintrag neu und verwarf das `env`** (#1238). Jetzt bleibt es, und die Datei wird BOM-fest
  gelesen (Windows PowerShell 5.1 schreibt ein BOM; ohne das galt die Datei als nicht lesbar und der bisherige Eintrag als unbekannt). Ein alter
  `PYTHONPATH` fällt weg.
- **`switch_mode.py` (Entwicklerwerkzeug, nicht im ZIP) verwarf das `env`** (#1238): nimmt jetzt `_setup_claude.eintrag_bauen`, liest BOM-fest.
  Nebenwirkung zum Guten: ein verlegter Datenordner wird beim Umschalten nicht mehr auf den Standardordner zurückgesetzt.

### Tests

- `tests/test_1238_installer_env_erhalten.py` (53 Tests, davon 35 in dieser Linie). Jedem der Schreiber (`_setup_claude.config_schreiben`, der echte
  Aufruf von `_setup_claude.py`, `switch_mode`, `setup_gui`; `install.ps1` nur, wo es noch der volle Installer ist) wird dieselbe Beispielkonfiguration
  gereicht (fremder Server mit Umlaut und `ł` im Pfad, fremde Einstellungen, PBP-Eintrag mit zusätzlichem `env`): `env` bleibt, mit und ohne BOM,
  ein zweiter Lauf ändert nichts, ohne alten Eintrag gelten die Vorgaben, ohne Datei und ohne `mcpServers` steht der Eintrag danach drin. Dazu: die
  Aufrufe von `_setup_claude.py` in `install.sh`, `INSTALLIEREN.command` und `INSTALLIEREN.bat` (auch in der Befehlsersetzung der 1.8-Linie), die
  Liste aller Dateien mit `mcpServers`, der Stub von `install.ps1`.
- Gegenprobe Katalog `claude_konfig`: 14 Eingriffe, alle erkannt.

### Bekannt, nicht Teil dieser Änderung

- `setup_gui.py` ersetzt eine **kaputte** (nicht lesbare) Konfiguration weiter ohne Sicherungskopie; `_setup_claude.py` legt seit v1.7.145 eine
  `.pbp-defekt-…`-Kopie daneben.
