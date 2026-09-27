"""#1098: Sicherung taeglich, vor dem Leeren, manuell — ein Ordner, eine
Rotation, mit Dokumenten, und ein Weg zurueck."""
from __future__ import annotations

import os
import threading
from collections import namedtuple
from datetime import datetime, timedelta
from pathlib import Path

import pytest


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "pbp.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Sicherung"})
    (tmp_path / "dokumente").mkdir()
    (tmp_path / "dokumente" / "lebenslauf.txt").write_text("Lebenslauf", encoding="utf-8")
    import bewerbungs_assistent.dashboard as dash
    dash._db = d
    yield d
    for t in threading.enumerate():
        if t.name.startswith("pbp-sicherung"):
            t.join(timeout=10)
    try:
        d.close()
    except Exception:
        pass
    os.environ.pop("BA_DATA_DIR", None)


def _client():
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    return TestClient(dash.app)


def _bewerbung(db, firma):
    return db.add_application({"title": "Sachbearbeitung", "company": firma,
                               "status": "beworben"})


def _firmen(db):
    return sorted(r[0] for r in db.connect().execute("SELECT company FROM applications"))


# ── Sicherung und Liste ─────────────────────────────────────────────

def test_sicherung_mit_dokumenten(db):
    from bewerbungs_assistent.services import sicherung
    erg = sicherung.sichern(db, "manuell")
    assert erg["status"] == "gesichert" and erg["dokumente"]
    eintrag = sicherung.liste(db)[0]
    assert eintrag["anlass"] == "manuell" and eintrag["dokumente"]
    assert (Path(db.db_path).parent / "backups" / erg["name"]).is_file()


def test_ohne_dokumente_benannt(db):
    from bewerbungs_assistent.services import sicherung
    sicherung.sichern(db, "vor_zusammenfuehren", mit_dokumenten=False)
    assert sicherung.liste(db)[0]["dokumente"] is False


# ── AK 1: taeglich und Rotation ─────────────────────────────────────

def test_taeglich_einmal_am_tag(db):
    from bewerbungs_assistent.services import sicherung
    assert sicherung.taeglich_faellig(db)
    sicherung.sichern(db, "taeglich")
    assert not sicherung.taeglich_faellig(db)
    assert sicherung.taeglich(db)["status"] == "schon_gesichert"


def test_rotation_sieben_tage_vier_wochen(db):
    from bewerbungs_assistent.services import sicherung
    jetzt = datetime(2026, 9, 27, 12, 0, 0)
    for tage in range(60):
        sicherung.sichern(db, "taeglich", mit_dokumenten=False,
                          jetzt=jetzt - timedelta(days=tage))
    sicherung.rotieren(db, jetzt=jetzt)
    alle = sicherung.liste(db)
    juengste = [e for e in alle if datetime.fromisoformat(e["zeit"]) >= jetzt - timedelta(days=7)]
    aeltere = [e for e in alle if datetime.fromisoformat(e["zeit"]) < jetzt - timedelta(days=7)]
    assert len(juengste) == 8  # heute + 7 Tage zurueck (Grenze eingeschlossen)
    assert len(aeltere) == 4
    wochen = {tuple(datetime.fromisoformat(e["zeit"]).isocalendar())[:2] for e in aeltere}
    assert len(wochen) == 4


def test_je_tag_eine_taegliche(db):
    from bewerbungs_assistent.services import sicherung
    jetzt = datetime(2026, 9, 27, 12, 0, 0)
    sicherung.sichern(db, "taeglich", mit_dokumenten=False, jetzt=jetzt - timedelta(hours=3))
    sicherung.sichern(db, "taeglich", mit_dokumenten=False, jetzt=jetzt)
    alle = sicherung.liste(db)
    assert len(alle) == 1 and alle[0]["zeit"].endswith("12:00:00")


def test_ereignisse_je_tag_begrenzt(db):
    from bewerbungs_assistent.services import sicherung
    jetzt = datetime(2026, 9, 27, 12, 0, 0)
    for i in range(9):
        sicherung.sichern(db, "vor_leeren", mit_dokumenten=False,
                          jetzt=jetzt + timedelta(minutes=i))
    assert len(sicherung.liste(db)) == sicherung.EREIGNISSE_JE_TAG


def test_update_sicherung_raeumt_keine_taegliche_weg(db):
    from bewerbungs_assistent.database import create_backup
    from bewerbungs_assistent.services import sicherung
    for tage in range(6):
        sicherung.sichern(db, "taeglich", mit_dokumenten=False,
                          jetzt=datetime.now() - timedelta(days=tage))
    create_backup(Path(db.db_path), Path(db.db_path).parent / "backups", max_backups=1)
    arten = [e["anlass"] for e in sicherung.liste(db)]
    assert arten.count("taeglich") == 6 and arten.count("vor_update") == 1


def test_automatik_sichert_im_hintergrund(db):
    from bewerbungs_assistent.services import automatik_scheduler, sicherung
    automatik_scheduler._tick(db)
    for t in threading.enumerate():
        if t.name.startswith("pbp-sicherung"):
            t.join(timeout=10)
    assert not sicherung.taeglich_faellig(db)
    jobs = db.connect().execute(
        "SELECT status FROM background_jobs WHERE job_type='sicherung'").fetchall()
    assert [j[0] for j in jobs] == ["fertig"]


# ── AK 2: vor dem Leeren ja, vor der DSGVO-Loeschung nicht ──────────

def test_leeren_sichert_vorher(db):
    from bewerbungs_assistent.services import sicherung
    _bewerbung(db, "Musterbetrieb GmbH")
    r = _client().post("/api/danger/leeren",
                       json={"confirm": "LOESCHEN", "modus": "bereiche", "bereiche": ["bewerbungen"]})
    assert r.status_code == 200, r.text
    assert r.json()["sicherung"]
    assert [e["anlass"] for e in sicherung.liste(db)] == ["vor_leeren"]


def test_leeren_ohne_platz_loescht_nichts(db, monkeypatch):
    from bewerbungs_assistent.services import sicherung
    _bewerbung(db, "Musterbetrieb GmbH")
    Platz = namedtuple("Platz", "total used free")
    monkeypatch.setattr(sicherung.shutil, "disk_usage", lambda _p: Platz(10, 10, 1000))
    r = _client().post("/api/danger/leeren",
                       json={"confirm": "LOESCHEN", "modus": "bereiche", "bereiche": ["bewerbungen"]})
    assert r.status_code == 507 and "Speicherplatz" in r.json()["error"]
    assert _firmen(db) == ["Musterbetrieb GmbH"]


def test_factory_reset_und_profilloeschen_sichern_nicht(db):
    from bewerbungs_assistent.services import sicherung
    db.reset_all_data()
    assert sicherung.liste(db) == []


def test_dsgvo_loeschung_legt_keine_sicherung_an(db, monkeypatch):
    from bewerbungs_assistent.services import sicherung
    aufrufe = []
    monkeypatch.setattr(sicherung, "sichern", lambda *a, **k: aufrufe.append(a) or {"status": "gesichert"})
    r = _client().post("/api/danger/leeren", json={"confirm": "LOESCHEN", "modus": "dsgvo"})
    assert r.status_code == 200, r.text  # die Loeschung lief wirklich
    assert aufrufe == []


def test_werkzeug_bereiche_leeren_sichert(db):
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.services import sicherung
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1098")
    register_all(mcp, db, logging.getLogger("test.1098"))

    async def lauf():
        t = await mcp.get_tool("daten_bereiche_leeren")
        return (await t.run({"bereiche": ["bewerbungen"], "bestaetigung": "LOESCHEN"})).structured_content
    erg = asyncio.run(lauf())
    assert erg.get("sicherung"), erg
    assert sicherung.liste(db)[0]["anlass"] == "vor_leeren"


# ── AK 3: manuell im selben Ordner, alter Ordner uebernommen ────────

def test_manuell_im_selben_ordner(db):
    from bewerbungs_assistent.services import sicherung
    alt = Path(db.db_path).parent / "backup"
    alt.mkdir()
    (alt / "pbp_backup_20260901_101500.db").write_bytes(b"alt")
    r = _client().get("/api/backup")
    assert r.status_code == 200
    anlaesse = [e["anlass"] for e in sicherung.liste(db)]
    assert anlaesse.count("manuell") == 2
    assert not alt.exists()


# ── AK 4: wiederherstellen ──────────────────────────────────────────

def test_wiederherstellen_beim_naechsten_start(db, tmp_path):
    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.services import sicherung
    _bewerbung(db, "Stand A GmbH")
    a = sicherung.sichern(db, "manuell")["name"]
    _bewerbung(db, "Stand B GmbH")
    (tmp_path / "dokumente" / "neu.txt").write_text("neu", encoding="utf-8")

    c = _client()
    assert c.post("/api/sicherungen/wiederherstellen", json={"name": a}).status_code == 400
    r = c.post("/api/sicherungen/wiederherstellen", json={"name": a, "confirm": "WIEDERHERSTELLEN"})
    assert r.status_code == 200, r.text
    assert "Claude Desktop" in r.json()["naechster_schritt"]
    assert c.get("/api/sicherungen").json()["vorgemerkt"] == a

    db.close()
    neu = Database(db_path=tmp_path / "pbp.db")
    neu.initialize()
    try:
        assert _firmen(neu) == ["Stand A GmbH"]
        assert not (tmp_path / "dokumente" / "neu.txt").exists()
        assert (tmp_path / "dokumente" / "lebenslauf.txt").exists()
        vorher = [e for e in sicherung.liste(neu) if e["anlass"] == "vor_wiederherstellen"]
        assert len(vorher) == 1
        assert sicherung.vormerkung(neu) is None
    finally:
        neu.close()


def test_wal_des_alten_stands_faellt_weg(tmp_path):
    from bewerbungs_assistent.services import sicherung
    (tmp_path / "backups").mkdir()
    name = "pbp-backup-2026-09-01_10-00-00-manuell.db"
    (tmp_path / "backups" / name).write_bytes(b"x")
    (tmp_path / "pbp.db").write_bytes(b"y")
    (tmp_path / "pbp.db-wal").write_bytes(b"alt")
    (tmp_path / sicherung.VORMERKUNG).write_text(name, encoding="utf-8")
    erg = sicherung.vorgemerkt_einspielen(tmp_path / "pbp.db")
    assert erg["status"] == "eingespielt"
    assert not (tmp_path / "pbp.db-wal").exists()
    assert (tmp_path / "pbp.db").read_bytes() == b"x"


def test_unbekannte_sicherung_wird_nicht_vorgemerkt(db):
    from bewerbungs_assistent.services import sicherung
    sicherung.sichern(db, "manuell", mit_dokumenten=False)  # Ordner existiert
    r = _client().post("/api/sicherungen/wiederherstellen",
                       json={"name": "../pbp.db", "confirm": "WIEDERHERSTELLEN"})
    assert r.status_code == 400


# ── Zusammenfuehren, Hinweis, Datenordner ───────────────────────────

def test_zusammenfuehren_sichert_vorher(db):
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.services import sicherung
    from bewerbungs_assistent.tools import register_all
    db.save_jobs([{"hash": f"m1098{i}", "title": f"Stelle {i}", "company": "Firma GmbH",
                   "url": f"https://example.com/m{i}", "source": "manuell",
                   "description": "Text " * 20} for i in range(2)])
    mcp = FastMCP("PBP #1098")
    register_all(mcp, db, logging.getLogger("test.1098"))

    async def lauf(dry):
        t = await mcp.get_tool("stelle_mergen")
        return (await t.run({"master_hash": "m10980", "duplikat_hash": "m10981",
                             "dry_run": dry})).structured_content
    asyncio.run(lauf(True))
    assert sicherung.liste(db) == []
    erg = asyncio.run(lauf(False))
    assert erg.get("sicherung"), erg
    assert sicherung.liste(db)[0]["anlass"] == "vor_zusammenfuehren"


def test_hinweis_bei_alter_sicherung(db):
    from bewerbungs_assistent.services import onboarding_hints, sicherung
    _bewerbung(db, "Musterbetrieb GmbH")
    assert onboarding_hints._condition_sicherung_alt(db)
    sicherung.sichern(db, "manuell")
    assert not onboarding_hints._condition_sicherung_alt(db)
    sicherung.sichern(db, "manuell", jetzt=datetime.now() - timedelta(days=10))
    alle = sicherung.liste(db)
    for e in alle[:-1]:
        (Path(db.db_path).parent / "backups" / e["name"]).unlink()
    assert onboarding_hints._condition_sicherung_alt(db)


def test_frisches_profil_ohne_hinweis(db):
    from bewerbungs_assistent.services import onboarding_hints
    assert not onboarding_hints._condition_sicherung_alt(db)


def test_vormerkung_steht_in_der_datenordner_liste():
    from bewerbungs_assistent.services import datenordner, sicherung
    assert sicherung.VORMERKUNG in datenordner.NAMEN
    assert sicherung.ORDNER in datenordner.NAMEN


def test_werkzeuge_fuer_claude(db):
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1098")
    register_all(mcp, db, logging.getLogger("test.1098"))

    async def lauf(name):
        t = await mcp.get_tool(name)
        return (await t.run({})).structured_content
    leer = asyncio.run(lauf("sicherungen_anzeigen"))
    assert leer["anzahl"] == 0 and "sicherung_anlegen" in leer["hinweis"]
    assert asyncio.run(lauf("sicherung_anlegen"))["status"] == "gestartet"
    for t in threading.enumerate():
        if t.name.startswith("pbp-sicherung"):
            t.join(timeout=10)
    danach = asyncio.run(lauf("sicherungen_anzeigen"))
    assert danach["anzahl"] == 1 and danach["sicherungen"][0]["dokumente"]
