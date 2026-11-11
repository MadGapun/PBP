"""#1375: ein ausdruecklich gespeichertes `abgeschlossen=False` haelt den
Bereich offen, auch wenn er Daten hat (Setter braucht einen Leser); der
Weg zurueck ist `abgeschlossen=True`."""
from __future__ import annotations

import asyncio
import logging
import os

import pytest

from bewerbungs_assistent.services import ersterfassung_phasen as phasen


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _werkzeug(db, name, args):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1375")
    register_all(mcp, db, logging.getLogger("test.1375"))

    async def lauf():
        t = await mcp.get_tool(name)
        return (await t.run(args)).structured_content
    return asyncio.run(lauf())


@pytest.fixture
def importiert(db):
    """Profil wie nach einem Lebenslauf-Import: Daten in allen Bereichen."""
    _werkzeug(db, "profil_erstellen", {"name": "Musterfrau", "email": "m@example.com",
                                       "stellentyp": "festanstellung"})
    _werkzeug(db, "position_hinzufuegen", {"company": "Beispiel GmbH", "title": "Fachkraft",
                                           "start_date": "2020-01"})
    _werkzeug(db, "ausbildung_hinzufuegen", {"institution": "Uni Beispiel", "degree": "BSc"})
    db.add_skill({"name": "Excel", "category": "fachlich", "level": 3})
    assert all(phasen.stand(db.get_profile())[b] for b in phasen.BEREICHE if b != "review_abgeschlossen")
    return db


def _phase(db):
    return phasen.anleitung(phasen.stand(db.get_profile()))[0]


def test_nach_import_ist_die_phase_review(importiert):
    assert _phase(importiert) == "review"


def test_false_haelt_den_bereich_offen(importiert):
    erg = _werkzeug(importiert, "erfassung_fortschritt_speichern",
                    {"bereich": "berufserfahrung", "abgeschlossen": False})
    assert erg["phase"] == "erfassung", erg
    assert phasen.stand(importiert.get_profile())["berufserfahrung"] is False
    assert "bleibt offen" in erg["hinweis"]
    assert "abgeschlossen=True" in erg["hinweis"]   # der Weg zurueck


def test_true_danach_macht_ihn_wieder_erledigt(importiert):
    _werkzeug(importiert, "erfassung_fortschritt_speichern",
              {"bereich": "praeferenzen", "abgeschlossen": False})
    assert _phase(importiert) == "erfassung"
    erg = _werkzeug(importiert, "erfassung_fortschritt_speichern",
                    {"bereich": "praeferenzen", "abgeschlossen": True})
    assert erg["phase"] == "review" and "hinweis" not in erg


def test_true_antwort_hat_keinen_offen_hinweis(importiert):
    erg = _werkzeug(importiert, "erfassung_fortschritt_speichern", {"bereich": "ausbildung"})
    assert "hinweis" not in erg


def test_profilvollstaendigkeit_faellt_nicht_wegen_false(importiert):
    """Die Vollstaendigkeit fragt, ob Angaben da sind, nicht ob die Erfassung weitergeht."""
    from bewerbungs_assistent.services.profile_service import get_profile_completeness
    vorher = get_profile_completeness(importiert.get_profile())["completeness"]
    _werkzeug(importiert, "erfassung_fortschritt_speichern",
              {"bereich": "berufserfahrung", "abgeschlossen": False})
    assert get_profile_completeness(importiert.get_profile())["completeness"] == vorher


def test_gegenprobe_ohne_den_fix_wird_der_test_rot(importiert, monkeypatch):
    """Ohne die Regel (alter Stand) wuerde False nichts bewirken."""
    monkeypatch.setattr(phasen, "_ausdruecklich_offen", lambda f, b: False)
    _werkzeug(importiert, "erfassung_fortschritt_speichern",
              {"bereich": "berufserfahrung", "abgeschlossen": False})
    assert phasen.stand(importiert.get_profile())["berufserfahrung"] is True  # der alte Fehler
    assert _phase(importiert) == "review"
