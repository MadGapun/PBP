"""Tests fuer v1.7.56 — #986: Score-Verteilung der beworbenen Stellen.

Frage des Nutzers am 07.09.2026:

    "Wie hoch war der Score bei den Stellen, auf die ich mich beworben
    habe, als Spanne und Durchschnitt? Vielleicht kann man daraus
    lernen, auf welche Stellen ich mich bewerbe."

Die Zahlen existierten, aber nur als Nebenprodukt von
`kalibrierung_backtest` (#778) — gebaut fuer die Schwellenkalibrierung.
Als Statistik waren sie nirgends sichtbar.

**Warum das eine eigene Kennzahl ist.** Der Score ist eine
EINSCHAETZUNG der Passung; entschieden hat der Mensch. Die Verteilung
ueber die tatsaechlich abgeschickten Bewerbungen zeigt, **wie weit das
eigene Urteil vom Modell abweicht** — das beantwortet keine andere
Kennzahl.

Zwei Regeln, die den Unterschied zu einer belanglosen Zahl ausmachen:

* **Score 0 ist keine Bewertung**, sondern "kein MUSS-Keyword
  getroffen". Ihn in den Mittelwert zu geben waere der stille Nulltarif
  aus #989, nur in der Statistik.
* **Eine Bewerbung ohne verknuepfte Stelle ist eine Datenluecke**, kein
  Wert. Wer sie weglaesst, rechnet mit einer Auswahl und nennt sie
  Gesamtheit.
"""
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.services import score_verteilung as sv  # noqa: E402


@pytest.fixture
def db():
    """QA-Isolation (HART): eigenes Temp-Verzeichnis, hart geprueft."""
    tmpdir = tempfile.mkdtemp(prefix="pbp_986_")
    alt = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = tmpdir
    from bewerbungs_assistent import database as _database
    importlib.reload(_database)
    datenbank = _database.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.save_profile({"name": "Muster Person"})
    try:
        yield datenbank
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt
        shutil.rmtree(tmpdir, ignore_errors=True)


def _bewerbung(db, titel, score=None, status="beworben"):
    """Eine Bewerbung, optional mit verknuepfter, bewerteter Stelle."""
    hash_ = None
    if score is not None:
        db.save_jobs([{
            "hash": f"h{abs(hash(titel)) % 10**10:010d}",
            "title": titel, "company": "Musterwerk", "score": score,
            "url": f"https://example.org/{abs(hash(titel)) % 10**6}",
            "source": "manuell", "description": "x" * 80,
        }])
        hash_ = [j["hash"].split(":")[-1] for j in db.get_active_jobs()
                 if j.get("title") == titel][0]
    return db.add_application({"title": titel, "company": "Musterwerk",
                               "status": status, "job_hash": hash_})


# ── Die Kennzahlen ────────────────────────────────────────────────────

def test_986_spanne_mittel_und_median(db):
    """Genau die Frage des Nutzers: Spanne und Durchschnitt."""
    for i, punkte in enumerate((10, 20, 30, 40, 50)):
        _bewerbung(db, f"Rolle {i}", punkte)
    b = sv.verteilung(db)["beworben"]
    assert b["anzahl"] == 5
    assert (b["min"], b["max"]) == (10.0, 50.0)
    assert b["mittel"] == 30.0
    assert b["median"] == 30.0
    assert b["q25"] == 20.0 and b["q75"] == 40.0


def test_986_wenige_werte_bekommen_keine_quartile(db):
    """Ein Median aus drei Werten ist die Verkleidung eines
    Einzelfalls. Lieber die Grenze nennen als eine Genauigkeit
    vortaeuschen."""
    for i, punkte in enumerate((10, 20, 30)):
        _bewerbung(db, f"Rolle {i}", punkte)
    b = sv.verteilung(db)["beworben"]
    assert "q25" not in b
    assert "hinweis_wenig_daten" in b


# ── Score 0 ist keine Bewertung ───────────────────────────────────────

def test_986_score_null_zaehlt_nicht_in_den_mittelwert(db):
    """Der Kern. Score 0 heisst "kein MUSS-Keyword getroffen" — die
    Stelle wurde nicht schlecht bewertet, sondern gar nicht beurteilt.
    Ihn einzurechnen wuerde den Mittelwert nach unten ziehen und eine
    Aussage ueber Passung vortaeuschen, die es nicht gibt (#989)."""
    for i, punkte in enumerate((30, 40, 50)):
        _bewerbung(db, f"Passend {i}", punkte)
    for i in range(2):
        _bewerbung(db, f"Ohne Anker {i}", 0)
    ergebnis = sv.verteilung(db)
    assert ergebnis["beworben"]["anzahl"] == 3
    assert ergebnis["beworben"]["mittel"] == 40.0
    assert ergebnis["score_null"]["anzahl"] == 2
    assert "nicht inhaltlich schlecht bewertet" in \
        ergebnis["score_null"]["bedeutung"]


def test_986_bewerbung_ohne_stelle_ist_eine_datenluecke(db):
    """Stillschweigend weglassen hiesse, mit einer Auswahl zu rechnen
    und sie Gesamtheit zu nennen."""
    _bewerbung(db, "Mit Stelle", 30)
    _bewerbung(db, "Ohne Stelle")
    ergebnis = sv.verteilung(db)
    assert ergebnis["beworben"]["anzahl"] == 1
    assert ergebnis["ohne_verknuepfte_stelle"]["anzahl"] == 1
    assert "Datenluecke" in ergebnis["ohne_verknuepfte_stelle"]["bedeutung"]


# ── Segmentierung und Schwelle ────────────────────────────────────────

def test_986_segmentierung_nach_ausgang(db):
    """Zeigt, ob hohe Scores auch zu Gespraechen fuehren."""
    _bewerbung(db, "Abgelehnt A", 20, status="abgelehnt")
    _bewerbung(db, "Abgelehnt B", 30, status="abgelehnt")
    _bewerbung(db, "Interview", 60, status="interview")
    nach = sv.verteilung(db)["nach_ausgang"]
    assert nach["abgelehnt"]["anzahl"] == 2
    assert nach["interview"]["mittel"] == 60.0


def test_986_bewerbungen_unter_der_schwelle_sind_abrufbar(db):
    """"Du hast dich gegen die Einschaetzung beworben" ist der
    interessanteste Teil der Kennzahl."""
    _bewerbung(db, "Ueber Schwelle", 40)
    _bewerbung(db, "Unter Schwelle", 8)
    ergebnis = sv.verteilung(db, schwelle=15)
    assert ergebnis["schwelle"] == 15.0
    assert ergebnis["unter_schwelle"]["anzahl"] == 1
    assert ergebnis["unter_schwelle"]["beispiele"][0]["score"] == 8


def test_986_ohne_schwelle_wird_keine_erfunden(db):
    """Sie wird uebergeben, nicht geraten — sonst stuende in der
    Statistik eine Grenze, die der Nutzer nie gesetzt hat."""
    _bewerbung(db, "Rolle", 40)
    ergebnis = sv.verteilung(db)
    assert "schwelle" not in ergebnis
    assert "unter_schwelle" not in ergebnis


# ── Robustheit und Nebenwirkungsfreiheit ──────────────────────────────

def test_986_leerer_bestand_meldet_nichts(db):
    """Kein leeres Geruest in der Statistik."""
    assert sv.verteilung(db) == {}


def test_986_nur_unverknuepfte_bewerbungen_sagen_das(db):
    """Der gemessene Zustand im echten Bestand: viele Bewerbungen ohne
    verknuepfte Stelle. Dann gibt es nichts zu verteilen — und PBP sagt,
    womit sich das beheben laesst."""
    _bewerbung(db, "Ohne Stelle A")
    _bewerbung(db, "Ohne Stelle B")
    ergebnis = sv.verteilung(db)
    assert ergebnis["beworben"] == {}
    assert "bewerbungs_stellen_abgleichen" in ergebnis["nachricht"]
    assert ergebnis["ohne_verknuepfte_stelle"]["anzahl"] == 2


def test_986_die_kennzahl_veraendert_keinen_score(db):
    """Ein Lesewerkzeug hat keine Nebenwirkung (#963)."""
    _bewerbung(db, "Rolle", 42)
    vorher = [j["score"] for j in db.get_active_jobs()]
    sv.verteilung(db, schwelle=15)
    assert [j["score"] for j in db.get_active_jobs()] == vorher


def test_986_beide_wege_liefern_dieselbe_quelle(db):
    """Dashboard und MCP-Werkzeug duerfen nicht auseinanderlaufen —
    das Muster aus #963/#976/#991. Beide rufen denselben Dienst."""
    for datei, name in (("database.py", "get_statistics"),
                        ("tools/bewerbungen.py", "statistiken_abrufen")):
        quelle = (Path(__file__).resolve().parents[1] / "src"
                  / "bewerbungs_assistent" / datei).read_text(encoding="utf-8")
        assert "score_verteilung" in quelle, name
        assert "_sv.verteilung(" in quelle, name


def test_986_das_dashboard_zeigt_die_schwellenmarkierung():
    """AK: Darstellung im Dashboard mit Schwellenmarkierung. Ohne sie
    ist die Verteilung eine Zahlenreihe ohne Bezugspunkt."""
    quelle = (Path(__file__).resolve().parents[1] / "frontend" / "src"
              / "pages" / "StatsPage.jsx").read_text(encoding="utf-8")
    assert "score_verteilung" in quelle
    assert "v.schwelle" in quelle
    assert "unter_schwelle" in quelle
