"""Guard: liest das Frontend `chrome`-Felder, die es gibt? (#993)

Gefunden am 07.09.2026 bei der Arbeit an #989:

    const persistentMinScore =
        Number(chrome?.search_criteria?.min_score_schwelle ?? 0);

`search_criteria` ist **kein Schluessel des `chrome`-Objekts**. Der
optionale Zugriff fiel still auf 0 zurueck: der Mindest-Score-Filter im
Stellen-Tab startete seit beta.27 immer bei 0, die persistente Schwelle
aus den Suchkriterien wirkte in der Anzeige nie.

Kein Datenschaden — serverseitig greift die Schwelle weiter. Aber es ist
dieselbe Klasse wie der zweite Schwellenwert-Regler aus #988 und der
Status ausserhalb der Whitelist aus #981: **eine Einstellung, die
aussieht, als wirke sie.** Ein Tippfehler mit optionaler Verkettung
erzeugt keinen Fehler, sondern einen falschen Vorgabewert.

**Zwei Ebenen, zwei Guards.** Beim ersten Entwurf hat dieser Test sieben
Fehlalarme gemeldet, weil er `chrome` fuer die Server-Antwort hielt. Das
ist es nicht: `chrome` ist ein im Client zusammengesetztes Objekt
(`App.jsx`), und nur sein Teil `workspace` kommt vom Server. Erst diese
Unterscheidung macht den Guard brauchbar — Muster wie bei der
Routen-Paritaet (#980, v1.7.31 MERKE 4: zuerst die Fehlalarme klaeren).
"""
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

_CHROME = re.compile(r"chrome\s*\??\.\s*([A-Za-z_][A-Za-z0-9_]*)")
_WORKSPACE = re.compile(
    r"chrome\s*\??\.\s*workspace\s*\??\.\s*([A-Za-z_][A-Za-z0-9_]*)")


def _jsx_dateien():
    return sorted((_repo() / "frontend" / "src").rglob("*.jsx"))


def ohne_kommentare(quelltext: str) -> str:
    """Zeilen- und Blockkommentare entfernen.

    **Ohne das prueft der Guard die Erklaerung mit, warum eine
    Schreibweise falsch ist — und schlaegt an ihr an.** Genau das ist
    heute dreimal passiert (v1.7.31 MERKE 6, dann #998, dann hier), und
    es wird jedes Mal wieder passieren, weil eine gute Begruendung den
    verbotenen Ausdruck nun einmal nennen muss. Deshalb steht die
    Bereinigung hier als Helfer und nicht als Einzelfall im Test.
    """
    ohne_block = re.sub(r"/\*.*?\*/", "", quelltext, flags=re.S)
    return "\n".join(z for z in ohne_block.split("\n")
                     if not z.strip().startswith("//"))


def _zugriffe(muster) -> dict:
    """Welche Felder liest das Frontend, und in welchen Dateien?"""
    treffer: dict[str, set] = {}
    for datei in _jsx_dateien():
        text = ohne_kommentare(datei.read_text(encoding="utf-8"))
        for name in muster.findall(text):
            treffer.setdefault(name, set()).add(datei.name)
    return treffer


def _chrome_schluessel() -> set:
    """Die Schluessel, die `App.jsx` beim Anlegen von `chrome` setzt.

    Aus dem Quelltext gelesen statt hier aufgezaehlt: eine Liste im Test
    haelt denselben Stand nur an einer zweiten Stelle fest.
    """
    text = (_repo() / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    start = text.index("const [chrome, setChrome] = useState({")
    block = text[start:text.index("\n  });", start)]
    return set(re.findall(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*):", block, re.M))


@pytest.fixture
def summary(tmp_path):
    """Die echte Workspace-Antwort auf einer isolierten DB.

    QA-Isolation (HART): eigenes Temp-Verzeichnis, hart geprueft.
    """
    import importlib
    import os
    alt = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    try:
        from bewerbungs_assistent import database as _database
        importlib.reload(_database)
        db = _database.Database()
        db.initialize()
        assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
        db.save_profile({"name": "Muster Person"})

        from bewerbungs_assistent import dashboard as _dashboard
        importlib.reload(_dashboard)
        _dashboard._db = db
        yield _dashboard
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt


# ── Ebene 1: chrome ist ein Client-Objekt ─────────────────────────────

def test_993_kein_zugriff_auf_einen_erfundenen_chrome_schluessel():
    """Der gemeldete Fehler, allgemein gefasst.

    Gezaehlt wird nicht die bekannte Fundstelle, sondern JEDER Zugriff
    im JSX gegen die Schluessel, die `App.jsx` tatsaechlich setzt.
    """
    erlaubt = _chrome_schluessel()
    fehlend = {name: sorted(dateien)
               for name, dateien in _zugriffe(_CHROME).items()
               if name not in erlaubt}
    assert not fehlend, (
        f"Zugriff auf chrome-Schluessel, die App.jsx nicht setzt: {fehlend}. "
        f"Vorhanden sind: {sorted(erlaubt)}. Optionale Verkettung macht "
        "daraus lautlos einen Vorgabewert statt eines Fehlers.")


def test_993_der_guard_sieht_die_echten_schluessel():
    """Ein Guard, der nichts findet, ist gruen und wertlos (DoD 8c)."""
    schluessel = _chrome_schluessel()
    assert {"workspace", "status", "profiles"} <= schluessel
    assert "search_criteria" not in schluessel, \
        "Wenn es den Schluessel jetzt gibt, gehoert dieser Test angepasst"
    assert len(_zugriffe(_CHROME)) >= 5


# ── Ebene 2: chrome.workspace kommt vom Server ────────────────────────

def test_993_jedes_gelesene_workspace_feld_wird_geliefert(summary):
    """Hier liegt die echte Server/Client-Grenze.

    Alles unter `chrome.workspace` stammt aus `/api/workspace-summary` —
    ein Feld, das dort fehlt, ist derselbe stille Vorgabewert eine Ebene
    tiefer.
    """
    antwort = summary._build_workspace_summary()
    fehlend = {name: sorted(dateien)
               for name, dateien in _zugriffe(_WORKSPACE).items()
               if name not in antwort}
    assert not fehlend, (
        "Das Frontend liest workspace-Felder, die die Antwort nicht "
        f"liefert: {fehlend}")


def test_993_die_speicherschwelle_wird_nicht_mehr_ausgeliefert(summary):
    """Korrektur an #993 selbst, nachgezogen mit #1008.

    v1.7.50 hat `search_criteria.min_score_schwelle` in die
    Workspace-Antwort gelegt, weil der Stellen-Tab den Wert als Vorgabe
    seines Anzeige-Filters las. Der falsche ZUGRIFFSPFAD war damals der
    Fund; die Frage, ob diese Schwelle die Anzeige ueberhaupt filtern
    darf, blieb ungestellt.

    Sie darf nicht: `min_score_schwelle` wirkt waehrend der SUCHE (ab
    wann eine Stelle ueberhaupt gespeichert wird), der Anzeige-Filter
    heisst `schwellenwert/auto_ignore` und wirkt serverseitig. Weil
    #993 den toten Zugriff repariert hat, wurde aus einem seit beta.27
    schlafenden Filter ein wirksamer — und sieben von acht Stellen
    verschwanden aus der Liste, ohne dass jemand einen Filter gesetzt
    haette (#1008).

    Mit dem Leser faellt der Lieferant. Ein Feld, das niemand liest, ist
    keine Auskunft, sondern die naechste Fehlerquelle.
    """
    antwort = summary._build_workspace_summary()
    assert "search_criteria" not in antwort, (
        "Feld ohne Leser — entweder es hat einen Zweck, oder es gehoert weg.")


def test_993_der_stellen_tab_erfindet_keine_chrome_schluessel():
    """Der bleibende Kern von #993.

    Die urspruengliche Fassung forderte einen BESTIMMTEN Zugriff. Das
    war zu eng: sie haette die Korrektur aus #1008 blockiert, obwohl
    der Zugriff selbst der Fehler war. Geblieben ist, worum es ging —
    `chrome.search_criteria` gibt es nicht, und eine optionale
    Verkettung darauf faellt lautlos auf 0.
    """
    code = ohne_kommentare((_repo() / "frontend" / "src" / "pages"
                            / "JobsPage.jsx").read_text(encoding="utf-8"))
    assert "chrome?.search_criteria" not in code
    assert "chrome.search_criteria" not in code
