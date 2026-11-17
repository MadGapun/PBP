"""#1395: Die Automatik belegt sich nicht selbst, sortiert ohne Text nicht aus, und kein Firmen-k.o. aus bedeutungslosen Woertern."""
import pytest

from bewerbungs_assistent.services import stellen_automatik, wiedergaenger
from bewerbungs_assistent.services.wiedergaenger import (
    find_wiedergaenger_pattern, ist_beleg, ist_fachlicher_ko)

TEXT = "Aufgaben und Profil dieser Anzeige. " * 20


def _beleg(nr, titel, *, von="ich", grund="falsches_fachgebiet", firma="Musterdienst Personal GmbH"):
    return {"hash": f"h{nr}", "company": firma, "title": titel, "location": "Hamburg",
            "dismiss_reason": grund, "dismissed_by": von, "description": TEXT, "is_active": 0}


def _muster(belege, titel="PLM Projektleiter (m/w/d)"):
    return find_wiedergaenger_pattern(None, "Musterdienst Personal GmbH", titel,
                                      dismissed=belege, ort="Hamburg")


@pytest.mark.parametrize("von,grund,erwartet", [
    ("ich", "falsches_fachgebiet", True),
    ("claude", "falsches_fachgebiet", True),
    ("automatik", "falsches_fachgebiet", False),
    (None, "auto:falsches_fachgebiet", False),   # Altbestand mit Praefix
    (None, "falsches_fachgebiet", True),         # Herkunft unbekannt: zaehlt (dokumentiert)
])
def test_ist_beleg(von, grund, erwartet):
    assert ist_beleg({"dismissed_by": von, "dismiss_reason": grund}) is erwartet


def test_automatische_entscheidungen_sind_kein_beleg():
    auto = [_beleg(i, "PLM Berater", von="automatik") for i in range(3)]
    assert _muster(auto) is None
    mensch = [_beleg(i, "PLM Berater", von="ich") for i in range(2)]
    assert _muster(mensch)["top_grund"] == "falsches_fachgebiet"


def test_ein_mensch_und_ein_automat_sind_nur_ein_beleg():
    gemischt = [_beleg(1, "PLM Berater", von="ich"), _beleg(2, "PLM Berater", von="automatik")]
    assert _muster(gemischt) is None


def test_claude_zaehlt_als_beleg():
    assert _muster([_beleg(1, "PLM Berater", von="claude"), _beleg(2, "PLM Berater", von="ich")])


def test_gender_ist_kein_fachwort():
    belege = [_beleg(1, "Sachbearbeiter Einkauf (all gender)"), _beleg(2, "Buchhalter (all gender)")]
    assert _muster(belege, titel="Konstrukteur Maschinenbau (all gender)") is None


def test_firmen_ko_faellt_bei_offenem_pflichttor():
    muster = {"anzahl": 3, "top_grund": "falsches_fachgebiet"}
    assert ist_fachlicher_ko(muster) is True
    assert ist_fachlicher_ko(muster, tor_offen=True) is False
    # andere fachliche Gruende bleiben k.o. (das Tor widerlegt nur das Fachgebiet)
    assert ist_fachlicher_ko({"anzahl": 3, "top_grund": "zu_junior"}, tor_offen=True) is True


@pytest.fixture
def kein_zahlenwiderspruch(monkeypatch):
    monkeypatch.setattr(stellen_automatik, "_zahl_widerspricht", lambda *a, **k: "")
    monkeypatch.setattr(stellen_automatik, "_tor_widerspricht", lambda *a, **k: "")


def _neu(text):
    return {"hash": "neu", "company": "Musterdienst Personal GmbH", "title": "PLM Berater (m/w/d)",
            "location": "Hamburg", "description": text}


def test_stufe1_nur_automatische_belege_sortieren_nichts_aus(tmp_db, kein_zahlenwiderspruch):
    belege = [_beleg(i, "PLM Berater Automotive", von="automatik") for i in range(3)]
    erg = stellen_automatik.entscheide(tmp_db, _neu(TEXT), dismissed=belege, kriterien={})
    assert erg["aktion"] != "aussortieren"


def test_stufe1_menschliche_belege_sortieren_mit_text_aus(tmp_db, kein_zahlenwiderspruch):
    belege = [_beleg(i, "PLM Berater Automotive", von="ich") for i in range(2)]
    assert stellen_automatik.entscheide(tmp_db, _neu(TEXT), dismissed=belege, kriterien={})["aktion"] == "aussortieren"


@pytest.mark.parametrize("text", ["", "   ", "kurz"])
def test_ohne_anzeigentext_keine_fachliche_aussortierung(tmp_db, kein_zahlenwiderspruch, text):
    belege = [_beleg(i, "PLM Berater Automotive", von="ich") for i in range(2)]
    erg = stellen_automatik.entscheide(tmp_db, _neu(text), dismissed=belege, kriterien={})
    assert erg["aktion"] == "anlegen"


def test_stufe2_automatische_belege_zaehlen_nicht(tmp_db, kein_zahlenwiderspruch):
    belege = [_beleg(1, "PLM Berater (m/w/d)", von="automatik")]
    erg = stellen_automatik.entscheide(tmp_db, _neu(TEXT), dismissed=belege, kriterien={})
    assert erg["aktion"] != "ignorieren"
