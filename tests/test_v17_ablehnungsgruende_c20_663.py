"""Tests fuer Issue #663 Teil 1 (C20, beta.85) — Ablehnungsgruende editierbar.

Schema v45: dismiss_reasons.is_active. Backend-Tools:
  ablehnungsgruende_anzeigen, ablehnungsgrund_anlegen,
  ablehnungsgrund_umbenennen, ablehnungsgrund_aktivieren_setzen.

Plus: stelle_bewerten akzeptiert jetzt aktive Custom-Gruende
zusaetzlich zur hardcoded Whitelist.
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


def _register_suche(tmp_db):
    from bewerbungs_assistent.tools.suche import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def _register_jobs(tmp_db):
    from bewerbungs_assistent.tools.jobs import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


# ── Schema-Check ─────────────────────────────────────────────────────────


def test_dismiss_reasons_is_active_column_exists(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    conn = tmp_db.connect()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(dismiss_reasons)").fetchall()]
    assert "is_active" in cols


def test_standard_reasons_sind_aktiv_by_default(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    rows = tmp_db.get_dismiss_reasons()
    assert any(r.get("is_active", 1) for r in rows)


# ── ablehnungsgrund_anlegen ──────────────────────────────────────────────


def test_ablehnungsgrund_anlegen_neu(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_suche(tmp_db)
    fn = mcp.tools["ablehnungsgrund_anlegen"]

    result = fn(label="kein_homeoffice")
    assert result["status"] == "angelegt"
    assert result["is_custom"] is True
    assert result["is_active"] is True


def test_ablehnungsgrund_anlegen_bereits_vorhanden(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_suche(tmp_db)
    fn = mcp.tools["ablehnungsgrund_anlegen"]

    fn(label="windchill_fehlt")
    again = fn(label="windchill_fehlt")
    assert again["status"] == "bereits_vorhanden"


def test_ablehnungsgrund_anlegen_leerer_label(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_suche(tmp_db)
    fn = mcp.tools["ablehnungsgrund_anlegen"]

    result = fn(label="   ")
    assert "fehler" in result


# ── ablehnungsgrund_umbenennen ───────────────────────────────────────────


def test_ablehnungsgrund_umbenennen(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_suche(tmp_db)
    anlegen = mcp.tools["ablehnungsgrund_anlegen"]
    umbenennen = mcp.tools["ablehnungsgrund_umbenennen"]

    r = anlegen(label="alt_name")
    result = umbenennen(grund_id=r["id"], neues_label="neu_name")
    assert result["status"] == "umbenannt"

    rows = tmp_db.get_dismiss_reasons()
    labels = [x.get("label") for x in rows]
    assert "neu_name" in labels


# ── ablehnungsgrund_aktivieren_setzen ────────────────────────────────────


def test_ablehnungsgrund_deaktivieren_dann_aktivieren(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_suche(tmp_db)
    anlegen = mcp.tools["ablehnungsgrund_anlegen"]
    setzen = mcp.tools["ablehnungsgrund_aktivieren_setzen"]

    r = anlegen(label="kandidat_x")
    deact = setzen(grund_id=r["id"], aktiv=False)
    assert deact["is_active"] is False

    act = setzen(grund_id=r["id"], aktiv=True)
    assert act["is_active"] is True


# ── Dynamische Whitelist in stelle_bewerten ──────────────────────────────


def test_custom_grund_in_stelle_bewerten_akzeptiert(tmp_db):
    """Ein aktiver Custom-Grund darf in stelle_bewerten verwendet werden."""
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id() or ""

    # Custom-Grund anlegen via DB-Helper
    tmp_db.add_dismiss_reason("kein_homeoffice")

    # Stelle anlegen
    full_hash = f"{pid}:t1234abc"
    tmp_db.save_jobs([{
        "hash": full_hash, "title": "x", "company": "y",
        "location": "", "url": "", "source": "manuell", "score": 50,
        "description": "x",
    }])

    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_bewerten"]

    result = fn(job_hash=full_hash, bewertung="passt_nicht",
                gruende=["kein_homeoffice"])
    assert result.get("status") == "aussortiert"
    # kein_homeoffice darf nicht zu 'sonstiges' normalisiert werden
    assert "kein_homeoffice" in result.get("gruende", [])


def test_deaktivierter_custom_grund_faellt_auf_sonstiges_zurueck(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id() or ""
    rid = tmp_db.add_dismiss_reason("temporaerer_grund")
    tmp_db.set_dismiss_reason_active(rid, False)

    full_hash = f"{pid}:t5678def"
    tmp_db.save_jobs([{
        "hash": full_hash, "title": "x", "company": "y",
        "location": "", "url": "", "source": "manuell", "score": 50,
        "description": "x",
    }])

    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_bewerten"]

    result = fn(job_hash=full_hash, bewertung="passt_nicht",
                gruende=["temporaerer_grund"])
    assert result.get("status") == "aussortiert"
    # Deaktiviert -> 'sonstiges'
    assert "temporaerer_grund" not in result.get("gruende", [])
    assert "sonstiges" in result.get("gruende", [])


# ── ablehnungsgruende_anzeigen ───────────────────────────────────────────


def test_ablehnungsgruende_anzeigen_default_zeigt_alle(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_suche(tmp_db)
    setzen = mcp.tools["ablehnungsgrund_aktivieren_setzen"]
    anzeigen = mcp.tools["ablehnungsgruende_anzeigen"]

    # Einen Standard-Grund deaktivieren
    rows_vorher = tmp_db.get_dismiss_reasons()
    first_id = rows_vorher[0]["id"]
    setzen(grund_id=first_id, aktiv=False)

    alle = anzeigen()
    nur_aktiv = anzeigen(nur_aktiv=True)
    assert alle["anzahl"] > nur_aktiv["anzahl"]
