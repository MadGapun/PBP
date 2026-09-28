"""#1095: Aussortieren und Bearbeiten im Dashboard wirken wie ueber Claude."""
from __future__ import annotations

import asyncio
import logging
import os

import pytest


def _neue_db(pfad):
    os.environ["BA_DATA_DIR"] = str(pfad)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=pfad / "test.db")
    d.initialize()
    assert str(pfad) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Stellen"})
    d.set_search_criteria("keywords_muss", ["einkauf"])
    return d


@pytest.fixture
def db(tmp_path):
    d = _neue_db(tmp_path)
    import bewerbungs_assistent.dashboard as dash
    dash._db = d
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _client():
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    return TestClient(dash.app)


def _werkzeug(db, name, args):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1095")
    register_all(mcp, db, logging.getLogger("test.1095"))

    async def lauf():
        t = await mcp.get_tool(name)
        return (await t.run(args)).structured_content
    return asyncio.run(lauf())


def _stellen(db, n, text="Wir suchen Unterstützung im Lager. " * 5):
    hashes = [f"s1095x{i}" for i in range(n)]
    db.save_jobs([{"hash": h, "title": f"Sachbearbeitung {i}", "company": f"Firma {i} GmbH",
                   "url": f"https://example.com/1095/{i}", "source": "manuell",
                   "description": text, "location": "Hamburg"}
                  for i, h in enumerate(hashes)])
    return hashes


def _regler(db, dim, sub):
    zeile = db.connect().execute(
        "SELECT value FROM scoring_config WHERE dimension=? AND sub_key=? "
        "ORDER BY CASE WHEN profile_id='' THEN 1 ELSE 0 END LIMIT 1", (dim, sub)).fetchone()
    return zeile["value"] if zeile else None


def _nutzung(db, label):
    zeile = db.connect().execute("SELECT usage_count FROM dismiss_reasons WHERE label=?",
                                 (label,)).fetchone()
    return zeile["usage_count"] if zeile else 0


# ── AK 1 und 2: beide Wege lernen gleich ────────────────────────────

def test_beide_wege_zaehlen_und_lernen_gleich(tmp_path):
    import bewerbungs_assistent.dashboard as dash
    stand = {}
    for weg in ("dashboard", "mcp"):
        pfad = tmp_path / weg
        pfad.mkdir()
        d = _neue_db(pfad)
        # Regler auf -2: die erste Verschaerfung (-2.5) kommt nach der
        # Formel aus #908 mit der 12. Nennung (Vorgabe -5 erst mit der 80.).
        d.connect().execute("UPDATE scoring_config SET value=-2 "
                            "WHERE dimension='stellentyp' AND sub_key='zeitarbeit'")
        d.connect().commit()
        dash._db = d
        try:
            gelernt = []
            for h in _stellen(d, 13):
                if weg == "dashboard":
                    r = _client().post("/api/jobs/dismiss", json={"hash": h, "reasons": ["zeitarbeit"]})
                    assert r.status_code == 200, r.text
                    gelernt += r.json()["lerneffekt"]
                else:
                    _werkzeug(d, "stelle_einordnen", {"job_hash": h, "bewertung": "passt_nicht",
                                                      "gruende": ["zeitarbeit"]})
            stand[weg] = (d.get_setting("dismiss_counts", {}),
                          _regler(d, "stellentyp", "zeitarbeit"),
                          _nutzung(d, "zeitarbeit"))
            if weg == "dashboard":
                assert gelernt and "Zeitarbeit" in gelernt[0], gelernt
        finally:
            d.close()
            dash._db = None
    assert stand["dashboard"] == stand["mcp"], stand
    assert stand["dashboard"][0]["zeitarbeit"] == 13
    assert stand["dashboard"][1] is not None and stand["dashboard"][1] < -2


def test_ohne_lerneffekt_kein_lernsatz(db):
    h = _stellen(db, 1)[0]
    r = _client().post("/api/jobs/dismiss", json={"hash": h, "reasons": ["falsches_fachgebiet"]})
    assert r.json()["lerneffekt"] == []


def test_nutzerregler_bleibt_unangetastet(db):
    zeile = db.connect().execute(
        "SELECT id FROM scoring_config WHERE dimension='stellentyp' AND sub_key='zeitarbeit'").fetchall()
    for z in zeile:
        db.connect().execute("UPDATE scoring_config SET set_by_user=1, value=-1 WHERE id=?", (z["id"],))
    db.connect().commit()
    for h in _stellen(db, 6):
        _client().post("/api/jobs/dismiss", json={"hash": h, "reasons": ["zeitarbeit"]})
    assert _regler(db, "stellentyp", "zeitarbeit") == -1


# ── AK 3: Bearbeiten rechnet neu ────────────────────────────────────

def test_bearbeiten_im_dashboard_rechnet_neu(db):
    h = _stellen(db, 1)[0]
    vorher = db.get_job(h)["score"]
    neu_text = "Wir suchen Unterstützung im Einkauf: Bestellungen, Lieferanten, Einkauf. " * 3
    r = _client().put(f"/api/jobs/{h}", json={"description": neu_text, "title": "Sachbearbeitung 0"})
    assert r.status_code == 200, r.text
    assert "description" in r.json()["geaendert"]
    job = db.get_job(h)
    from bewerbungs_assistent.job_scraper import calculate_score
    from bewerbungs_assistent.services import scoring_kriterien
    frisch = dict(job)
    assert job["score"] == calculate_score(frisch, scoring_kriterien.fuer_scoring(db))
    assert job["score"] != vorher and job["fachscore"] == frisch["_fachscore"]


def test_bearbeiten_gleich_auf_beiden_wegen(db):
    a, b = _stellen(db, 2)
    text = "Wir suchen Unterstützung im Einkauf und in der Disposition. " * 3
    _client().put(f"/api/jobs/{a}", json={"description": text})
    _werkzeug(db, "stelle_bearbeiten", {"job_hash": b, "beschreibung": text})
    ja, jb = db.get_job(a), db.get_job(b)
    assert (ja["score"], ja["fachscore"]) == (jb["score"], jb["fachscore"])


def test_neuer_ort_unbekannt_statt_alter_entfernung(db):
    h = _stellen(db, 1)[0]
    db.connect().execute("UPDATE jobs SET distance_km=12.5 WHERE hash LIKE ?", (f"%{h}",))
    db.connect().commit()
    r = _client().put(f"/api/jobs/{h}", json={"location": "Nirgendwo-am-See"})
    assert db.get_job(h)["distance_km"] is None
    assert "unbekannt" in r.json()["entfernung_hinweis"]
    assert "entfernung_km" not in r.json()["entfernung_hinweis"], "Werkzeugsprache im Dashboard"


def test_neuer_ort_bekannt_rechnet_entfernung(db, monkeypatch):
    from bewerbungs_assistent.services import geocoding_service, eigener_standort
    eigener_standort._setzen(db, "Hamburg", "eigener", (53.55, 9.99))
    monkeypatch.setattr(geocoding_service, "geocode_location",
                        lambda ort: (53.87, 10.69) if ort == "Lübeck" else None)
    h = _stellen(db, 1)[0]
    r = _werkzeug(db, "stelle_bearbeiten", {"job_hash": h, "ort": "Lübeck"})
    km = db.get_job(h)["distance_km"]
    assert km is not None and 50 < km < 80, km
    assert "neuen Ort" in r["entfernung_hinweis"]


def test_handentfernung_bleibt_beim_ortswechsel(db):
    h = _stellen(db, 1)[0]
    db.set_job_entfernung(h, 5)
    _client().put(f"/api/jobs/{h}", json={"location": "Anderswo"})
    assert db.get_job(h)["distance_km"] == 5


# ── AK 4: keine alte Notiz ──────────────────────────────────────────

def test_zurueckholen_und_neu_aussortieren_ohne_alte_notiz(db):
    h = _stellen(db, 1)[0]
    db.dismiss_job(h, "sonstiges", notiz="alter Grund: Firma kannte ich schon")
    assert db.get_job(h)["dismiss_note"]
    c = _client()
    assert c.post("/api/jobs/restore", json={"hash": h}).status_code == 200
    assert not db.get_job(h).get("dismiss_note")
    db.dismiss_job(h, "sonstiges", notiz="alter Grund")
    db.dismiss_job(h, "zu_weit_entfernt")  # erneut, ohne Freitext
    assert not db.get_job(h).get("dismiss_note")


# ── AK 5: unbekannte Kennung ────────────────────────────────────────

def test_unbekannte_kennung_404(db):
    c = _client()
    assert c.post("/api/jobs/dismiss", json={"hash": "gibtsnicht", "reasons": ["sonstiges"]}).status_code == 404
    assert c.post("/api/jobs/restore", json={"hash": "gibtsnicht"}).status_code == 404
    assert c.put("/api/jobs/gibtsnicht", json={"title": "x"}).status_code == 404
    assert db.dismiss_job("gibtsnicht", "sonstiges") is False
    assert db.restore_job("gibtsnicht") is False


def test_bearbeiten_rechnet_ueber_das_nadeloehr(db):
    """Eine gespeicherte Alternativbezeichnung (#969) zaehlt nur, wenn die
    Kriterien ueber `fuer_scoring` kommen (#987) — roh bliebe es bei 0."""
    from bewerbungs_assistent.services import scoring_kriterien
    db.set_profile_setting(scoring_kriterien.EINSTELLUNG, {"einkauf": ["Beschaffung"]})
    h = _stellen(db, 1)[0]
    text = "Wir suchen Unterstützung in der Beschaffung: Bestellungen, Lieferanten. " * 3
    _client().put(f"/api/jobs/{h}", json={"description": text})
    assert db.get_job(h)["score"] > 0
