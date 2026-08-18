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


# ── beta.92: Umbenennen mit Cascade + Loeschen mit Neuzuordnung ───────────


def _job_with_reason(tmp_db, hash_suffix: str, reason: str):
    """Helper: legt eine aussortierte Stelle mit gegebenem dismiss_reason an."""
    pid = tmp_db.get_active_profile_id() or ""
    full_hash = f"{pid}:{hash_suffix}"
    tmp_db.save_jobs([{
        "hash": full_hash, "title": "x", "company": "y",
        "location": "", "url": "", "source": "manuell", "score": 50,
        "description": "x",
    }])
    conn = tmp_db.connect()
    conn.execute(
        "UPDATE jobs SET is_active=0, dismiss_reason=? WHERE hash=?",
        (reason, full_hash),
    )
    conn.commit()
    return full_hash


def _reason_of(tmp_db, full_hash: str) -> str:
    conn = tmp_db.connect()
    row = conn.execute(
        "SELECT dismiss_reason FROM jobs WHERE hash=?", (full_hash,)
    ).fetchone()
    return row["dismiss_reason"] if row else None


def test_rename_zieht_jobs_mit(tmp_db):
    """Tippfehler-Korrektur: jobs.dismiss_reason wird mit umgeschrieben."""
    tmp_db.create_profile("Test", "test@example.com")
    # v1.7.17 (#913): 'falsches_system' ist jetzt ein Standard-Grund —
    # das alte Beispiel wuerde in eine Merge-Kollision laufen. Der
    # Testzweck (Tippfehler-Korrektur zieht jobs.dismiss_reason mit)
    # bleibt mit einem Custom-Grund identisch.
    rid = tmp_db.add_dismiss_reason("falsche_platform")  # Tippfehler
    h = _job_with_reason(tmp_db, "t0001aaa", "falsche_platform")

    res = tmp_db.rename_dismiss_reason(rid, "falsche_plattform")
    assert res["status"] == "umbenannt"
    assert res["reassigned_jobs"] == 1
    assert _reason_of(tmp_db, h) == "falsche_plattform"
    labels = [r["label"] for r in tmp_db.get_dismiss_reasons()]
    assert "falsche_plattform" in labels
    assert "falsche_platform" not in labels


def test_rename_kollision_merged(tmp_db):
    """Umbenennen auf ein bereits existierendes Label fuehrt zusammen."""
    tmp_db.create_profile("Test", "test@example.com")
    keep = tmp_db.add_dismiss_reason("zielgrund")
    dup = tmp_db.add_dismiss_reason("quellgrund")
    h = _job_with_reason(tmp_db, "t0002bbb", "quellgrund")

    res = tmp_db.rename_dismiss_reason(dup, "zielgrund")
    assert res["status"] == "zusammengefuehrt"
    assert res["merged_into"] == keep
    assert _reason_of(tmp_db, h) == "zielgrund"
    labels = [r["label"] for r in tmp_db.get_dismiss_reasons()]
    assert labels.count("zielgrund") == 1  # nur noch eine Zeile


def test_delete_ohne_verwendung(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    rid = tmp_db.add_dismiss_reason("ungenutzt")
    res = tmp_db.delete_dismiss_reason(rid)
    assert res["status"] == "geloescht"
    assert "ungenutzt" not in [r["label"] for r in tmp_db.get_dismiss_reasons()]


def test_delete_mit_verwendung_braucht_neuzuordnung(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    rid = tmp_db.add_dismiss_reason("wird_genutzt")
    _job_with_reason(tmp_db, "t0003ccc", "wird_genutzt")

    import pytest
    with pytest.raises(ValueError):
        tmp_db.delete_dismiss_reason(rid)  # ohne reassign_to -> Fehler


def test_delete_mit_neuzuordnung_haengt_jobs_um(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    rid = tmp_db.add_dismiss_reason("alt_grund")
    h = _job_with_reason(tmp_db, "t0004ddd", "alt_grund")

    res = tmp_db.delete_dismiss_reason(rid, reassign_to="sonstiges")
    assert res["status"] == "geloescht"
    assert res["reassigned_jobs"] == 1
    assert res["reassigned_to"] == "sonstiges"
    assert _reason_of(tmp_db, h) == "sonstiges"
    assert "alt_grund" not in [r["label"] for r in tmp_db.get_dismiss_reasons()]


def test_mcp_ablehnungsgrund_loeschen(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_suche(tmp_db)
    anlegen = mcp.tools["ablehnungsgrund_anlegen"]
    loeschen = mcp.tools["ablehnungsgrund_loeschen"]

    r = anlegen(label="weg_damit")
    h = _job_with_reason(tmp_db, "t0005eee", "weg_damit")

    # Ohne Neuzuordnung -> Fehler-Hinweis
    fehler = loeschen(grund_id=r["id"])
    assert "fehler" in fehler

    ok = loeschen(grund_id=r["id"], neu_zuordnen_zu="sonstiges")
    assert ok["status"] == "geloescht"
    assert ok["stellen_umgezogen"] == 1
    assert _reason_of(tmp_db, h) == "sonstiges"
