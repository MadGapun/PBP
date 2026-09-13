"""Tests fuer #1036 (C80): zwei Entfernungs-Fehler, unabhaengig von der Richtungsfrage.

(a) Die Wiedergaenger-Automatik uebertrug "zu weit entfernt" ueber Firma
    und Titel, ohne den Ort zu vergleichen — Stufe 2 verwarf die nahe
    Filiale sogar still.
(b) Die Grenze einer Anstellungsform ohne eigenes Feld stand zweimal
    verschieden im Code.

Die Ortsregel greift nur bei zwei BEKANNTEN, verschiedenen Orten. Fehlt
eine Angabe, bleibt es beim bisherigen Verhalten — dieselbe Linie wie
bei der fehlenden Entfernung in #1020 ("Unbekannt ist nicht innerhalb").

Alle Firmen und Orte sind Platzhalter.
"""
import importlib
import inspect
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

# Lang genug, damit ein fachliches Urteil als belegt zaehlt (#966/#989) —
# an einem Anzeigen-Rumpf zaehlt es bewusst gar nicht.
TEXT = "Ausfuehrliche Stellenbeschreibung mit Aufgaben und Anforderungen. " * 25


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "entfernung.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.switch_profile(datenbank.create_profile("Entfernung"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _aussortiert(nr, ort, grund="zu_weit_entfernt", firma="Filialkette Musterfirma",
                 titel="Crew Mitglied Gastronomie"):
    return {"hash": f"alt{nr}", "title": titel, "company": firma, "location": ort,
            "is_active": 0, "dismiss_reason": grund, "description": TEXT}


def _neu(ort, titel="Crew Mitglied Gastronomie", firma="Filialkette Musterfirma"):
    return {"hash": "neu1", "title": titel, "company": firma, "location": ort,
            "description": TEXT, "employment_type": "festanstellung"}


# ====================================================== (a) Stufe 2


def test_stufe2_verwirft_die_nahe_filiale_nicht(db):
    """Meldefall: mehrfach weit weg aussortiert, dieselbe Stelle in der Naehe."""
    from bewerbungs_assistent.services import stellen_automatik as sa

    dismissed = [_aussortiert(1, "Karlsruhe"), _aussortiert(2, "Muenchen"),
                 _aussortiert(3, "Berlin")]
    e = sa.entscheide(db, _neu("Fellbach"), dismissed=dismissed)
    assert e["aktion"] == "anlegen", e


def test_stufe2_gilt_weiter_fuer_denselben_ort(db):
    from bewerbungs_assistent.services import stellen_automatik as sa

    dismissed = [_aussortiert(1, "Karlsruhe")]
    e = sa.entscheide(db, _neu("Karlsruhe"), dismissed=dismissed)
    assert e["aktion"] == "ignorieren", e


def test_stufe2_ortsvergleich_ueber_den_normalisierer(db):
    """Quellen-Zusaetze am Ort machen keinen anderen Ort (#965)."""
    from bewerbungs_assistent.services import stellen_automatik as sa

    dismissed = [_aussortiert(1, "Karlsruhe (Hybrid)")]
    e = sa.entscheide(db, _neu("karlsruhe"), dismissed=dismissed)
    assert e["aktion"] == "ignorieren", e


def test_stufe2_fuer_andere_gruende_unveraendert(db):
    """Ein fachliches Urteil haengt nicht am Ort — #1020 bleibt."""
    from bewerbungs_assistent.services import stellen_automatik as sa

    dismissed = [_aussortiert(1, "Karlsruhe", grund="falsches_fachgebiet")]
    e = sa.entscheide(db, _neu("Fellbach"), dismissed=dismissed)
    assert e["aktion"] == "ignorieren", e


@pytest.mark.parametrize("ort_alt, ort_neu", [("", "Karlsruhe"), ("Karlsruhe", "")])
def test_stufe2_unbekannter_ort_bleibt_beim_bisherigen_verhalten(db, ort_alt, ort_neu):
    """Ein fehlender Ort ist nicht "anderswo" (#989) — nur zwei bekannte,
    verschiedene Orte heben das Urteil auf."""
    from bewerbungs_assistent.services import stellen_automatik as sa

    dismissed = [_aussortiert(1, ort_alt)]
    e = sa.entscheide(db, _neu(ort_neu), dismissed=dismissed)
    assert e["aktion"] == "ignorieren", e


# ====================================================== (a) Stufe 1


_TITEL_ALT = ["Crew Mitglied Kueche", "Crew Mitglied Service"]


def test_stufe1_uebertraegt_zu_weit_nicht_an_einen_anderen_ort(db):
    from bewerbungs_assistent.services import stellen_automatik as sa

    dismissed = [_aussortiert(i, "Muenchen", titel=t) for i, t in enumerate(_TITEL_ALT)]
    e = sa.entscheide(db, _neu("Fellbach", titel="Crew Mitglied Kasse"),
                      dismissed=dismissed)
    assert e["aktion"] == "anlegen", e


def test_stufe1_uebertraegt_zu_weit_an_denselben_ort(db):
    """Die Begruendung aus #1020 — jetzt tatsaechlich geprueft."""
    from bewerbungs_assistent.services import stellen_automatik as sa

    dismissed = [_aussortiert(i, "Muenchen", titel=t) for i, t in enumerate(_TITEL_ALT)]
    e = sa.entscheide(db, _neu("Muenchen", titel="Crew Mitglied Kasse"),
                      dismissed=dismissed)
    assert e["aktion"] == "aussortieren", e
    assert e["grund"] == "zu_weit_entfernt"


def test_stufe1_unbekannter_ort_bleibt_beim_bisherigen_verhalten(db):
    from bewerbungs_assistent.services import stellen_automatik as sa

    dismissed = [_aussortiert(i, "Muenchen", titel=t) for i, t in enumerate(_TITEL_ALT)]
    e = sa.entscheide(db, _neu("", titel="Crew Mitglied Kasse"), dismissed=dismissed)
    assert e["aktion"] == "aussortieren", e
    assert e["grund"] == "zu_weit_entfernt"


def test_stufe1_ein_beleg_am_selben_ort_reicht_nicht_fuer_die_schwelle(db):
    """Zwei Belege, einer davon anderswo: die Schwelle zaehlt nur, was fuer
    diesen Ort spricht."""
    from bewerbungs_assistent.services import stellen_automatik as sa

    dismissed = [_aussortiert(0, "Muenchen", titel=_TITEL_ALT[0]),
                 _aussortiert(1, "Berlin", titel=_TITEL_ALT[1])]
    e = sa.entscheide(db, _neu("Muenchen", titel="Crew Mitglied Kasse"),
                      dismissed=dismissed)
    assert e["aktion"] == "anlegen", e


def test_stufe1_gemischte_gruende_an_anderem_ort_uebertragen_die_entfernung_nicht(db):
    """Doppelter Boden: Belege mit zwei Gruenden bleiben im Muster. Steht
    die Entfernung dort oben, darf sie trotzdem nicht an einen anderen Ort
    wandern.

    Gegenprobe v1.7.99: die erste Fassung dieses Tests hatte zwei Gruende
    gleich oft — oben stand dann der andere, und ohne den doppelten Boden
    blieb der Test gruen. Jetzt steht die Entfernung eindeutig oben."""
    from bewerbungs_assistent.services import stellen_automatik as sa

    def _mehrere(nr, gruende, titel):
        # Mehrere Gruende stehen als Liste in `dismiss_reasons` (#108/#913),
        # nicht als JSON-Zeichenkette im Einzelfeld — die erste Fassung
        # dieses Tests baute genau das falsch und pruefte damit nichts.
        job = _aussortiert(nr, "Muenchen", grund=gruende[0], titel=titel)
        job["dismiss_reasons"] = list(gruende)
        return job

    dismissed = [
        _mehrere(0, ["zu_weit_entfernt", "zeitarbeit"], "Crew Mitglied Kueche"),
        _mehrere(1, ["zu_weit_entfernt", "zeitarbeit"], "Crew Mitglied Service"),
        _mehrere(2, ["zu_weit_entfernt", "befristet"], "Crew Mitglied Lager"),
    ]
    e = sa.entscheide(db, _neu("Fellbach", titel="Crew Mitglied Kasse"),
                      dismissed=dismissed)
    assert e["aktion"] == "anlegen", e
    assert e.get("grund") != "zu_weit_entfernt", e


def test_stufe1_entfernung_anderswo_verdraengt_keinen_fachlichen_grund(db):
    """Der Filter sitzt VOR dem Muster: Entfernungs-Urteile an anderen Orten
    duerfen nicht zum haeufigsten Grund werden und damit ein echtes
    fachliches Urteil verdraengen.

    Gegenprobe v1.7.99: ohne diesen Fall blieb das Ausbauen des Filters
    stumm — der doppelte Boden verhinderte dann zwar die falsche
    Entfernung, aber auch das richtige Fachgebiet."""
    from bewerbungs_assistent.services import stellen_automatik as sa

    dismissed = [
        _aussortiert(0, "Berlin", titel="Crew Mitglied Kueche"),
        _aussortiert(1, "Hamburg", titel="Crew Mitglied Service"),
        _aussortiert(2, "Bremen", titel="Crew Mitglied Lager"),
        _aussortiert(3, "Muenchen", grund="falsches_fachgebiet",
                     titel="Crew Mitglied Theke"),
        _aussortiert(4, "Muenchen", grund="falsches_fachgebiet",
                     titel="Crew Mitglied Kiosk"),
    ]
    e = sa.entscheide(db, _neu("Muenchen", titel="Crew Mitglied Kasse"),
                      dismissed=dismissed)
    assert e["aktion"] == "aussortieren", e
    assert e["grund"] == "falsches_fachgebiet"


def test_stufe1_fachliche_gruende_wandern_weiter_ortsunabhaengig(db):
    from bewerbungs_assistent.services import stellen_automatik as sa

    dismissed = [_aussortiert(i, "Muenchen", grund="falsches_fachgebiet", titel=t)
                 for i, t in enumerate(_TITEL_ALT)]
    e = sa.entscheide(db, _neu("Fellbach", titel="Crew Mitglied Kasse"),
                      dismissed=dismissed)
    assert e["aktion"] == "aussortieren", e
    assert e["grund"] == "falsches_fachgebiet"


# ====================================================== (b) eine Grenze


@pytest.mark.parametrize("kriterien, art, erwartet", [
    ({"max_entfernung": {"festanstellung": 20}}, "festanstellung", 20),
    # Meldefall: NICHT der groesste Profilwert
    ({"max_entfernung": {"festanstellung": 20, "teilzeit": 20, "freelance": 200}},
     "ausbildung", 50),
    # #1000: ein Altwert neben der Karte wird benannt, nicht umgedeutet
    ({"max_entfernung": {"freelance": 200}, "max_entfernung_km": 25}, "ausbildung", 50),
    ({}, "zeitarbeit", 50),
    ({}, "freelance", 200),
    ({}, "teilzeit", 30),
    ({}, "gibtesnicht", 50),
    ({"max_entfernung": {"festanstellung": "abc"}}, "festanstellung", 50),
    ({"max_entfernung": {"festanstellung": 0}}, "festanstellung", 50),
    (None, None, 50),
])
def test_grenze_km(kriterien, art, erwartet):
    from bewerbungs_assistent.services import entfernung

    assert entfernung.grenze_km(kriterien, art) == erwartet


def test_automatik_nimmt_nicht_den_groessten_profilwert(db):
    """Meldefall b: Ausbildung in 120 km, Freelance-Grenze 200 km. Vorher
    widersprach die Zahl dem Urteil (120 <= 200), jetzt nicht (50 km)."""
    from bewerbungs_assistent.services import stellen_automatik as sa

    db.set_search_criteria("max_entfernung", {"festanstellung": 20, "freelance": 200})
    job = {"title": "Ausbildung", "company": "Musterfirma", "distance_km": 120,
           "employment_type": "ausbildung"}
    assert sa._zahl_widerspricht(db, job, "zu_weit_entfernt") == ""


def test_score_fit_und_automatik_fragen_dieselbe_grenze():
    """Guard: keine eigene Vorgabe-Tabelle mehr in den Rechenwegen."""
    from bewerbungs_assistent import job_scraper
    from bewerbungs_assistent.services import stellen_automatik

    for funktion in (job_scraper.calculate_score, job_scraper.fit_analyse,
                     stellen_automatik._zahl_widerspricht):
        code = inspect.getsource(funktion)
        assert "grenze_km(" in code, funktion.__name__
        assert "default_max" not in code, funktion.__name__
    assert "karte.values()" not in inspect.getsource(stellen_automatik._zahl_widerspricht)
