"""Tests fuer Issue #665 (beta.83) — nachfass_planen Dubletten-Check.

Bisher hat nachfass_planen still einen zweiten Follow-up angelegt,
wenn fuer dieselbe Bewerbung bereits ein offener Nachfass existierte.
Jetzt: 4 Verhalten via `wenn_dublette`-Parameter:
  melden (Default)         -> liefert dublette_offen-Hinweis, kein Insert
  vorhandenen_erledigen    -> alten auf 'gesendet' + neuen anlegen
  vorhandenen_verschieben  -> alten auf neues Datum + KEIN neuer Insert
  trotzdem_neu             -> alten lassen + neuen anlegen (Legacy)
"""
from __future__ import annotations

import logging


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _register(tmp_db):
    from bewerbungs_assistent.tools.analyse import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def _make_app(tmp_db):
    return tmp_db.add_application({
        "title": "Stelle X",
        "company": "Firma X",
        "url": "",
        "job_hash": None,
        "status": "beworben",
        "applied_at": "2026-05-01",
        "notes": "",
        "bewerbungsart": "mit_dokumenten",
        "lebenslauf_variante": "standard",
        "profile_id": tmp_db.get_active_profile_id(),
    })


# ── Default-Verhalten: melden ────────────────────────────────────────────


def test_default_melden_legt_keine_dublette_an(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    fn = mcp.tools["nachfass_planen"]

    first = fn(bewerbung_id=aid, tage=7)
    assert first["status"] == "geplant"
    fid1 = first["follow_up_id"]

    # Zweiter Aufruf mit Default (melden) -> Dublette gemeldet, nicht eingefuegt
    second = fn(bewerbung_id=aid, tage=14)
    assert second["status"] == "dublette_offen"
    assert second["bestehender_nachfass"]["follow_up_id"] == fid1
    assert "optionen" in second
    # Es ist immer noch nur EIN Follow-up offen
    assert len(tmp_db.get_pending_follow_ups()) == 1


def test_vorhandenen_erledigen_legt_neuen_an(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    fn = mcp.tools["nachfass_planen"]

    first = fn(bewerbung_id=aid, tage=7)
    fid1 = first["follow_up_id"]

    second = fn(
        bewerbung_id=aid, tage=14,
        wenn_dublette="vorhandenen_erledigen",
    )
    assert second["status"] == "geplant"
    assert second["follow_up_id"] != fid1
    assert second["dublette_behandelt"]["alter_follow_up_id"] == fid1
    assert second["dublette_behandelt"]["aktion"] == "erledigt_markiert"

    # Pending: nur noch der neue
    pending_ids = [fu["id"] for fu in tmp_db.get_pending_follow_ups()]
    assert second["follow_up_id"] in pending_ids
    assert fid1 not in pending_ids


def test_vorhandenen_verschieben_aendert_datum_kein_neuer(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    fn = mcp.tools["nachfass_planen"]

    first = fn(bewerbung_id=aid, tage=7)
    fid1 = first["follow_up_id"]
    alt_datum = first["geplant_fuer"]

    second = fn(
        bewerbung_id=aid, tage=21,
        wenn_dublette="vorhandenen_verschieben",
    )
    assert second["status"] == "verschoben"
    assert second["follow_up_id"] == fid1
    assert second["alter_termin"] == alt_datum
    assert second["neuer_termin"] != alt_datum

    # Pending: nur einer
    assert len(tmp_db.get_pending_follow_ups()) == 1


def test_trotzdem_neu_legt_zweite_dublette_bewusst_an(tmp_db):
    """Legacy-Verhalten: User will bewusst zwei parallele Nachfasse."""
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    fn = mcp.tools["nachfass_planen"]

    first = fn(bewerbung_id=aid, tage=7)
    second = fn(bewerbung_id=aid, tage=14, wenn_dublette="trotzdem_neu")

    assert second["status"] == "geplant"
    assert "dublette_behandelt" not in second
    assert len(tmp_db.get_pending_follow_ups()) == 2


def test_anderer_typ_triggert_keine_dublette(tmp_db):
    """Nur typ='nachfass' wird gegen Dubletten geprueft. danke/info nicht."""
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    fn = mcp.tools["nachfass_planen"]

    fn(bewerbung_id=aid, tage=7, typ="nachfass")
    danke = fn(bewerbung_id=aid, tage=3, typ="danke")
    assert danke["status"] == "geplant"
    # Beide pending
    assert len(tmp_db.get_pending_follow_ups()) == 2


def test_keine_existierende_dublette_normaler_pfad(tmp_db):
    """Ohne existierenden offenen Nachfass: ganz normaler Insert."""
    tmp_db.create_profile("Test", "test@example.com")
    aid = _make_app(tmp_db)
    mcp = _register(tmp_db)
    fn = mcp.tools["nachfass_planen"]

    result = fn(bewerbung_id=aid, tage=7)
    assert result["status"] == "geplant"
    assert "dublette_behandelt" not in result
