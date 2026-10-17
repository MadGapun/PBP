# Entwurf: CHANGELOG-Einträge zu #1237 (eine laufende Stelle zählt bis heute)

> **Kein Teil des CHANGELOG.** Der Text gehört in den Eintrag der Version, die die Korrektur ausliefert. 1.8-Linie: dieser Zweig auf `release/v1.8.0`
> (Eintrag `[1.8.0]`, Abschnitt „Fixed“). Stable: Zweig `fix/1237-berufsjahre-laufendes-jahr` vom Tag v1.7.158 (zwei Commits, `c5c43095` und
> `63777c17`, für `hotfix/v1.7.159`); der Text gilt dort unverändert. Nummer und Datum beim Release einsetzen, danach diese Datei löschen.
>
> Belegt: `tests/test_berufsjahre_laufendes_jahr_1237.py` (58 Tests, auf v1.7.158 rot: 18), Gegenprobe Katalog `berufsjahre1237`
> (19 von 19 erkannt, `scripts/mutationstest_auto_update.py --katalog berufsjahre1237`; in Stable gibt es das Skript nicht, dort lief es mit
> dem Skript dieses Zweigs gegen den Stable-Zweig).

---

## Eintrag (Titelvorschlag)

**Eine laufende Stelle zählt bis heute, nicht bis 2026**

<!-- anwender -->
Wenn du eine Stelle hast, die noch läuft, zählt PBP sie jetzt bis heute und nicht mehr bis zu einem festen Jahr.
Das betrifft die Einschätzung deiner Berufserfahrung bei der Auto-Aussortierung und die Wertung deines Lebenslaufs; ab dem Jahreswechsel hätte sonst bei jeder laufenden Stelle ein Jahr gefehlt.
<!-- /anwender -->

PBP rechnete bei einer laufenden Stelle (ohne Enddatum) bis zu einer festen Jahreszahl: an drei Stellen stand `2026` im Quelltext. Bis zum 31.12.2026
fiel das nicht auf, weil die Uhr 2026 zeigte. Ab dem 01.01.2027 hätte bei jeder laufenden Stelle ein Jahr gefehlt, ab 2028 zwei: die Karrierestufe, die
die lokale KI beim Aussortieren bekommt, wäre an den Grenzen 4/5 und 9/10 Jahre zu spät gekippt (Mid-Level erst nach sechs statt fünf Jahren, Senior
erst nach elf statt zehn), und die Jahre Berufserfahrung in der Recruiter-Wertung deines Lebenslaufs wären zu kurz ausgefallen. Die richtige Rechnung gab
es schon (`berufsfeld.berufsjahre`, sie liest die Uhr); die Auto-Aussortierung hatte eine eigene Kopie.

**Wichtig zu wissen:**

- **Die Berufsjahre zählen bis heute.** Eine laufende Stelle zählt bis zum Jahr, das die Uhr deines Rechners zeigt. Bis zum 31.12.2026 ändert sich
  dadurch nichts; ab dem 01.01.2027 zählt jede laufende Stelle ein Jahr mehr als mit der festen Zahl.
- **Eine Rechnung statt zwei.** Die Auto-Aussortierung rechnet mit `berufsfeld.berufsjahre`, derselben Funktion wie die Einordnung des Profils. Auf allen
  Eingaben, die die Datenbank liefern kann, kommt dasselbe heraus wie mit der bisherigen Schleife (Test). Einziger Unterschied: ein Anfangsjahr von genau
  1900 zählt jetzt mit (bisher übersprungen), ein Platzhalter, den es nicht gibt.
- **Die Lücken-Erkennung ändert sich schon heute in einem Sonderfall.** Eine zweite Station, die neben einer laufenden ab Oktober 2026 beginnt, wurde als
  „Lücke“ von mehr als sechs Monaten gemeldet, weil das Ende der laufenden Station fest auf März 2026 stand. Jetzt endet sie heute.
- **Ein Wächter hält feste Jahreszahlen aus dem Quelltext.** Der Test liest alle Python-Dateien unter `src/` (Syntaxbaum) und schlägt bei einer Zahl oder
  einer vierstelligen Zeichenkette zwischen 2020 und 2039 an. Kommentare, Docstrings und Datumstexte zählen nicht; hat eine Zahl einen Grund, steht am
  Zeilenende `# jahreszahl-ok: <Grund>`. Beim ersten Lauf fand er zwei Stellen, die das Issue nicht nannte (beide in `export.py`).
- **Die Uhr ist eine Funktion.** `services/uhr.heute()`; die Aufrufer gehen über das Modul, damit ein Test sie auf einen festen Tag stellen kann. Zeitstempel
  für die Datenbank und die Ortszeit eines Termins lesen ihre eigene Uhr und bleiben dort.

### Fixed

- **Offene Positionen rechneten mit einer festen `2026`** (#1237): `services/auto_aussortierung.py` (die Stufe, die die lokale KI bekommt),
  `export._score_recruiter` (Jahre Berufserfahrung der Recruiter-Wertung) und `export._detect_career_gaps` (Ende einer laufenden Station, fest `2026-03`).
  Alle drei lesen das Jahr jetzt aus `uhr.heute()`.

### Changed

- `services/uhr.py` (neu): `heute()`.
- `services/berufsfeld.py` (`berufsjahre` liest das Jahr von dort), `services/auto_aussortierung.py` (ruft `berufsjahre` statt der eigenen Schleife),
  `export.py` (zwei Stellen).

### Gemessen

58 neue Tests in `tests/test_berufsjahre_laufendes_jahr_1237.py` (auf v1.7.158 rot: 18): die Uhr auf dem 31.12.2025, 17.10.2026, 01.01.2027 und
15.06.2030, also in beide Richtungen (eine feste Zahl rechnet davor zu viel und danach zu wenig); die Stufe der Auto-Aussortierung an den Grenzen 0/1,
4/5 und 9/10 Jahre auf dem echten Weg (`stellen_auto_aussortieren` mit einer unechten KI, die den Auftrag mitschreibt); Recruiter-Wertung und
Lücken-Erkennung; der Vergleich mit der bisherigen Schleife; der Wächter mit seinen Gegenproben. Gegenprobe (`--katalog berufsjahre1237`): 19 von 19
Eingriffen erkannt, sieben davon im Wächter selbst.

### Bekannt, nicht Teil dieser Änderung

- `berufsfeld.laeuft_studium`, `berufsfeld.aktuelle_positionen` und `export.detect_position_overlaps` lesen die Uhr richtig, aber an `uhr.heute()` vorbei
  (die Übersicht der Überschneidungen ruft `datetime.now()` zweimal auf, für Jahr und Monat). Umstellen und mit festem Tag testen: kleines Folge-Issue
  nach 1.8.0.
