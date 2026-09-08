"""Tests fuer v1.7.46 — #997: Erfolgsmeldung fuer IDs, die es nicht gibt.

Gemeldet am 08.09.2026 vom selben Anwender wie #990, #994 und #1000:

    profil_bearbeiten(bereich="position", aktion="aendern",
                      element_id="unbekannt", daten={"titel": "X"})
    -> {"status": "aktualisiert", "bereich": "position",
        "id": "unbekannt", "geaenderte_felder": ["title"]}

Geaendert wurde nichts. Weder der Mensch noch Claude hatten eine
Moeglichkeit, das zu bemerken.

Die Datenbankebene arbeitet korrekt — `update_position` und ihre sechs
Geschwister melden den Fehlschlag als `cur.rowcount > 0`. Die Auskunft
war also da und wurde eine Ebene hoeher an SIEBEN Stellen weggeworfen.

Zwei Dinge, die diesen Fall lehrreich machen:

1. **Genau ein Zweig machte es richtig** (`delete_skill`) — und der
   REST-Weg im Dashboard ebenfalls (HTTP 404). Dieselbe Frage lag also
   zweimal im Code, und der schwaechere Weg war der, den Claude nimmt.
   Das ist #991 in einem anderen Modul. Deshalb steht die Auswertung
   jetzt in `_schreibbefund` und nicht siebenmal als kopierte if-Zeile.

2. **`False` heisst auf DB-Ebene ZWEI Dinge**: "diese ID gibt es nicht"
   und "kein schreibbares Feld dabei". Eine Antwort, die sich fuer eines
   von beiden entscheidet, ohne nachzusehen, schickt den Aufrufer im
   halben Fall in die falsche Richtung (#987 MERKE 5).

Der wichtigste Test hier ist `test_997_jede_verzweigung_...`: er zaehlt
die Zweige nicht ab, sondern ruft sie auf. Eine achte Verzweigung, die
jemand spaeter hinzufuegt, faellt damit auf.
"""
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def db():
    """QA-Isolation (HART): eigenes Temp-Verzeichnis, hart geprueft."""
    tmpdir = tempfile.mkdtemp(prefix="pbp_997_")
    alt = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = tmpdir
    from bewerbungs_assistent import database as _database
    importlib.reload(_database)
    datenbank = _database.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.save_profile({"name": "Muster Person", "email": "m@example.org"})
    try:
        yield datenbank
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt
        shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def bearbeiten(db):
    """`profil_bearbeiten` als gewoehnliche Funktion.

    FastMCP macht aus dem dekorierten Objekt ein `FunctionTool`, das sich
    nicht direkt aufrufen laesst — hier wird die Registrierung
    abgefangen, damit der Test die echte Funktion bekommt.
    """
    from bewerbungs_assistent.tools import profil as profil_tools

    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

    import logging
    profil_tools.register(_Sammler(), db, logging.getLogger("test"))
    return gesammelt["profil_bearbeiten"]


def _bestand(db):
    """Ein Datensatz je Bereich, damit es echte IDs zu treffen gibt."""
    pos = db.add_position({"company": "Musterbetrieb", "title": "Rolle",
                           "start_date": "2020-01-01"})
    proj = db.add_project(pos, {"name": "Projekt"})
    edu = db.add_education({"institution": "Muster-Hochschule",
                            "degree": "Diplom"})
    skill = db.add_skill({"name": "Teamcenter", "category": "fachlich"})
    return {"position": pos, "projekt": proj, "ausbildung": edu,
            "skill": skill}


# ── Der gemeldete Fall ────────────────────────────────────────────────

def test_997_unbekannte_position_meldet_keinen_erfolg(bearbeiten):
    """Wortlaut des Reports, nachgestellt."""
    antwort = bearbeiten(bereich="position", aktion="aendern",
                         element_id="unbekannt", daten={"titel": "X"})
    assert antwort["status"] == "nicht_gefunden"
    assert antwort["id"] == "unbekannt"
    assert "geaenderte_felder" not in antwort
    assert "positionen_anzeigen" in antwort["hinweis"]


def test_997_erfolg_bleibt_erfolg(bearbeiten, db):
    """Die Gegenprobe. Ein Guard, der den Normalfall abwuergt, ist
    schlimmer als der Fehler, den er verhindern soll."""
    ids = _bestand(db)
    antwort = bearbeiten(bereich="position", aktion="aendern",
                         element_id=ids["position"], daten={"titel": "Neu"})
    assert antwort["status"] == "aktualisiert"
    assert antwort["geaenderte_felder"] == ["title"]
    assert db.get_profile()["positions"][0]["title"] == "Neu"


# ── Alle vier Bereiche, beide Aktionen ────────────────────────────────

@pytest.mark.parametrize("bereich", ["position", "projekt", "ausbildung",
                                     "skill"])
@pytest.mark.parametrize("aktion", ["aendern", "loeschen"])
def test_997_jede_verzweigung_meldet_unbekannte_id(bearbeiten, db,
                                                   bereich, aktion):
    """Der Guard gegen den Rueckfall — und gegen die achte Verzweigung.

    Es waren sieben Fundstellen; sie einzeln nachzupruefen wuerde eine
    kuenftige achte uebersehen. Deshalb wird hier ueber die Bereiche und
    Aktionen iteriert statt ueber die bekannten Zeilennummern.
    """
    _bestand(db)  # es gibt Daten — die ID passt trotzdem auf keine
    antwort = bearbeiten(bereich=bereich, aktion=aktion,
                         element_id="gibt-es-nicht",
                         daten={"beschreibung": "X"} if aktion == "aendern"
                         else {})
    assert antwort["status"] == "nicht_gefunden", f"{bereich}/{aktion}"
    assert antwort["bereich"] == bereich
    assert "nicht" in antwort["hinweis"].lower()


@pytest.mark.parametrize("bereich", ["position", "projekt", "ausbildung",
                                     "skill"])
def test_997_loeschen_wirkt_und_meldet_es(bearbeiten, db, bereich):
    """Gegenprobe zur Iteration oben: mit der richtigen ID kommt
    "geloescht", und der Datensatz ist wirklich weg."""
    ids = _bestand(db)
    antwort = bearbeiten(bereich=bereich, aktion="loeschen",
                         element_id=ids[bereich])
    assert antwort["status"] == "geloescht", bereich
    from bewerbungs_assistent.tools.profil import _kennt_id
    assert not _kennt_id(db, bereich, ids[bereich])


def test_997_zweimal_loeschen_meldet_beim_zweiten_mal_nichts_mehr(
        bearbeiten, db):
    """Der praktische Fall: wer denselben Aufruf wiederholt, soll den
    Unterschied sehen. Vorher waren beide Antworten identisch."""
    ids = _bestand(db)
    erst = bearbeiten(bereich="position", aktion="loeschen",
                      element_id=ids["position"])
    zweit = bearbeiten(bereich="position", aktion="loeschen",
                       element_id=ids["position"])
    assert erst["status"] == "geloescht"
    assert zweit["status"] == "nicht_gefunden"


# ── "False" heisst zwei Dinge ─────────────────────────────────────────

def test_997_falscher_feldname_ist_nicht_falsche_id(bearbeiten, db):
    """Der Punkt, an dem eine geratene Antwort schaedlich waere.

    Die ID stimmt, nur der Feldname nicht. Waere die Absage pauschal
    "nicht_gefunden", suchte der Aufrufer an der falschen Stelle — genau
    der Fehler, den #987 MERKE (5) beschreibt: ein Hinweis, der die
    Ursache aktiv wegerklaert.
    """
    ids = _bestand(db)
    antwort = bearbeiten(bereich="position", aktion="aendern",
                         element_id=ids["position"],
                         daten={"voellig_unbekanntes_feld": "X"})
    assert antwort["status"] == "nichts_geaendert"
    assert antwort["ignorierte_felder"] == ["voellig_unbekanntes_feld"]
    assert "title" in antwort["moegliche_felder"]


def test_997_beides_falsch_nennt_zuerst_die_id(bearbeiten, db):
    """Wenn ID UND Feldname falsch sind, wiegt die ID schwerer.

    Vorher meldete PBP nur den Feldnamen. Wer den korrigiert haette,
    waere beim zweiten Versuch weiterhin ins Leere gelaufen — der
    eigentliche Fehler zeigt sich erst eine Runde spaeter. Der Fall ist
    beim Schreiben dieses Tests aufgefallen, nicht beim Melden.
    """
    _bestand(db)
    antwort = bearbeiten(bereich="skill", aktion="aendern",
                         element_id="gibt-es-nicht",
                         daten={"voellig_unbekanntes_feld": "X"})
    assert antwort["status"] == "nicht_gefunden"
    # Der zweite Befund geht dabei nicht verloren.
    assert antwort["ignorierte_felder"] == ["voellig_unbekanntes_feld"]


def test_997_schreibbefund_unterscheidet_die_beiden_faelle(db):
    """Dasselbe eine Ebene tiefer, direkt am Nadeloehr."""
    from bewerbungs_assistent.tools.profil import _schreibbefund
    ids = _bestand(db)
    erfolg = {"status": "aktualisiert"}

    assert _schreibbefund(db, "position", ids["position"], True,
                          erfolg) == erfolg
    fehlt = _schreibbefund(db, "position", "nichts-davon", False, erfolg)
    assert fehlt["status"] == "nicht_gefunden"
    vorhanden = _schreibbefund(db, "position", ids["position"], False, erfolg)
    assert vorhanden["status"] == "nichts_geaendert"


# ── Deutsche Feldnamen fuer skill (die vierte Ecke aus #994) ──────────

def test_997_skill_kennt_jetzt_auch_deutsche_feldnamen(bearbeiten, db):
    """#994 hat die Uebersetzung fuer drei von vier Datentypen gebaut.
    Ohne die vierte haette `update_skill` fuer einen deutschen Feldnamen
    `False` gemeldet — und die neue Absage waere "nicht_gefunden"
    gewesen, obwohl die ID stimmt."""
    ids = _bestand(db)
    antwort = bearbeiten(bereich="skill", aktion="aendern",
                         element_id=ids["skill"],
                         daten={"niveau": 4, "kategorie": "fachlich"})
    assert antwort["status"] == "aktualisiert"
    assert set(antwort["geaenderte_felder"]) == {"level", "category"}
    skill = [s for s in db.get_profile()["skills"]
             if s["id"] == ids["skill"]][0]
    assert skill["level"] == 4


def test_997_jeder_ausgabename_ist_ein_gueltiger_eingabename_skill(db):
    """Dasselbe Guard-Muster wie in #994, jetzt fuer den vierten
    Bereich: was PBP ueber eine Skill AUSGIBT, muss sich auch
    zurueckschreiben lassen."""
    from bewerbungs_assistent.tools.profil import _felder_uebersetzen
    _bestand(db)
    skill = db.get_profile()["skills"][0]
    lesbar = {k: v for k, v in skill.items()
              if k not in ("id", "profile_id", "created_at", "updated_at")}
    _, ignoriert = _felder_uebersetzen("skill", lesbar)
    assert ignoriert == [], f"nicht zurueckschreibbar: {ignoriert}"


# ── Nebenbefund: add_skill gibt bei Muell eine leere ID zurueck ───────

def test_997_abgewiesene_skill_meldet_keinen_erfolg(bearbeiten, db):
    """Vom eigenen Test gefunden. `add_skill` weist Extraktions-Muell
    ab (#43/#129) und gibt eine LEERE ID zurueck — die Antwort lautete
    trotzdem "hinzugefuegt", mit `id: ""`. Derselbe stille Fehlschlag
    mit Erfolgsmeldung, nur beim Anlegen."""
    antwort = bearbeiten(bereich="skill", aktion="hinzufuegen",
                         daten={"name": "-", "category": "fachlich"})
    assert antwort["status"] == "nicht_angelegt"
    assert "id" not in antwort


def test_997_gueltige_skill_wird_weiterhin_angelegt(bearbeiten, db):
    """Gegenprobe zum Nebenbefund."""
    antwort = bearbeiten(bereich="skill", aktion="hinzufuegen",
                         daten={"bezeichnung": "Windchill",
                                "kategorie": "fachlich"})
    assert antwort["status"] == "hinzugefuegt"
    assert antwort["id"]
    assert any(s["name"] == "Windchill" for s in db.get_profile()["skills"])


# ── Der REST-Weg machte es schon richtig ──────────────────────────────

def test_997_rest_weg_und_mcp_weg_sagen_jetzt_dasselbe():
    """Die eigentliche Lehre des Issues.

    `dashboard.py` beantwortet dieselbe Frage seit jeher mit HTTP 404;
    der MCP-Weg meldete Erfolg. Zwei Wege fuer eine Frage, und der
    schwaechere war der, den Claude nimmt (#991). Der Test haelt fest,
    dass der REST-Weg den Rueckgabewert weiterhin auswertet — er ist ab
    jetzt der Vergleichsmassstab und darf nicht still verschwinden.
    """
    quelle = (Path(__file__).resolve().parents[1] / "src"
              / "bewerbungs_assistent" / "dashboard.py").read_text(
                  encoding="utf-8")
    for name in ("update_position", "delete_position", "update_education",
                 "delete_education", "update_project", "delete_project",
                 "update_skill", "delete_skill"):
        assert f"not _db.{name}(" in quelle, name
