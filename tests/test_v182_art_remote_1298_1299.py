"""#1298 und #1299: Anstellungsart und Remote-Stufe - bei der Uebernahme richtig, von Hand aenderbar.

#1298: `browser_treffer_uebernehmen` und `linkedin_treffer_uebernehmen` speicherten `str(remote)`; aus
`remote: true` wurde "True", und der Rahmen (prueft auf "remote") setzte voll remote Stellen unter die
40-km-Grenze. Ohne `anstellungsart` stand jede Stelle als `festanstellung` da, auch ein Freelance-Projekt.

#1299: Anstellungsform, Umfang und Remote liessen sich weder per MCP noch im Dashboard korrigieren.

Testdaten fiktiv (Musterfirma GmbH & Co.). Die Datenbank liegt in einem eigenen Temp-Ordner (BA_DATA_DIR).
"""
from __future__ import annotations

import asyncio
import logging
import os

import pytest

TEXT = ("Wir suchen eine erfahrene Projektleitung fuer die Einfuehrung eines neuen Systems. "
        "Aufgaben: Planung, Steuerung, Abstimmung mit Fachbereichen und Dienstleistern. ") * 3


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test"})
    import bewerbungs_assistent.dashboard as dash
    dash._db = d
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1298")
    register_all(mcp, db, logging.getLogger("test.1298"))
    return mcp


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _schema(mcp, name):
    async def _run():
        return (await mcp.get_tool(name)).parameters
    return asyncio.run(_run())


def _zeile(db, h):
    r = db.connect().execute("SELECT * FROM jobs WHERE hash=?", (db.resolve_job_hash(h),)).fetchone()
    return dict(r)


def _browser(db, mcp, treffer, quelle="stepstone"):
    res = _call(mcp, "browser_treffer_uebernehmen",
                {"quelle": quelle, "treffer": treffer, "dry_run": False})
    assert res.get("status") == "uebernommen", res
    return res


def _treffer(titel="Projektleitung Systemeinfuehrung", **extra):
    t = {"titel": titel, "firma": "Musterfirma GmbH", "url": f"https://example.com/stelle/{abs(hash(titel))}",
         "beschreibung": TEXT, "ort": "Musterstadt"}
    t.update(extra)
    return t


def _daumen_entfernung(db, h, km):
    from bewerbungs_assistent.services import rahmen
    from bewerbungs_assistent.services.scoring_kriterien import fuer_scoring
    job = db.get_job(h)
    job["distance_km"] = km
    return rahmen._entfernungs_befund(job, fuer_scoring(db))


# ── Die eine Normalisierung (remote_jobspy.normalisieren) ───────────

@pytest.mark.parametrize("wert,stufe", [
    (True, "remote"), (False, "vor_ort"), ("True", "remote"), ("false", "vor_ort"),
    ("100 % remote", "remote"), ("100 % remote (Agentur)", "remote"), ("voll remote", "remote"),
    ("fully remote", "remote"), ("hybrid", "hybrid"), ("vor Ort", "vor_ort"), ("nicht remote", "vor_ort"),
    ("unbekannt", "unbekannt"), (None, "unbekannt"), ("", "unbekannt"),
])
def test_remote_normalisieren(wert, stufe):
    from bewerbungs_assistent.services import remote_jobspy
    assert remote_jobspy.normalisieren(wert) == (stufe, None)


def test_remote_unverstaendlich_gibt_hinweis():
    from bewerbungs_assistent.services import remote_jobspy
    stufe, hinweis = remote_jobspy.normalisieren("Mondbasis")
    assert stufe == "unbekannt" and "Mondbasis" in hinweis and "vor_ort" in hinweis


def test_detect_erkennt_voll_remote_vor_hybrid():
    from bewerbungs_assistent.job_scraper import detect_remote_level
    assert detect_remote_level("Voll remote, Kickoff hybrid in Musterstadt") == "remote"
    assert detect_remote_level("100 % remote, Hybrid-Team") == "remote"
    assert detect_remote_level("Fully remote") == "remote"


def test_form_bestimmen_rangfolge():
    from bewerbungs_assistent.services import stellenart
    assert stellenart.form_bestimmen("freiberuflich")["form"] == "freelance"
    assert stellenart.form_bestimmen("interim")["form"] == "freelance"
    assert stellenart.form_bestimmen("", titel="Berater", quelle="freelancermap") == {
        "form": "freelance", "herkunft": "quelle", "hinweis": None}
    assert stellenart.form_bestimmen(None, titel="Berater",
                                     url="https://www.gulp.de/gulp2/g/projekte/1")["form"] == "freelance"
    assert stellenart.form_bestimmen(None, titel="Praktikum Marketing")["form"] == "praktikum"
    assert stellenart.form_bestimmen(None, titel="Sachbearbeitung")["herkunft"] == "vorgabe"
    falsch = stellenart.form_bestimmen("Mondvertrag", titel="Sachbearbeitung")
    assert falsch["form"] == "festanstellung" and "Mondvertrag" in falsch["hinweis"]


# ── #1298: Uebernahme ────────────────────────────────────────────────

def test_schema_nennt_beide_felder_mit_werten(db):
    mcp = _mcp(db)
    for name in ("browser_treffer_uebernehmen", "linkedin_treffer_uebernehmen"):
        text = _schema(mcp, name)["properties"]["treffer"].get("description", "")
        assert "anstellungsart" in text and "freelance" in text and "festanstellung" in text, (name, text)
        assert "remote" in text and "vor_ort" in text and "hybrid" in text, (name, text)
        assert "…" not in text, f"abgeschnitten: {text}"


def test_remote_true_wird_remote_und_hebt_die_grenze_auf(db):
    mcp = _mcp(db)
    res = _browser(db, mcp, [_treffer(remote=True)])
    h = res["angelegt"][0]["hash"]
    assert _zeile(db, h)["remote_level"] == "remote"
    befund = _daumen_entfernung(db, h, 300)
    assert not befund.get("ausschluss"), befund


def test_ungueltiger_wert_steht_als_hinweis_in_der_antwort(db):
    mcp = _mcp(db)
    res = _browser(db, mcp, [_treffer(remote="Mondbasis", anstellungsart="Mondvertrag")])
    eintrag = res["angelegt"][0]
    assert _zeile(db, eintrag["hash"])["remote_level"] == "unbekannt"
    hinweise = " ".join(eintrag.get("angaben_hinweise") or [])
    assert "Mondbasis" in hinweise and "Mondvertrag" in hinweise, eintrag


def test_freelance_gilt_mit_freelance_grenze_und_tagessatz(db):
    from bewerbungs_assistent.services import rahmen
    from bewerbungs_assistent.services.entfernung import grenze_km
    from bewerbungs_assistent.services.scoring_kriterien import fuer_scoring
    mcp = _mcp(db)
    res = _browser(db, mcp, [_treffer(anstellungsart="freelance")])
    h = res["angelegt"][0]["hash"]
    job = db.get_job(h)
    assert job["employment_type"] == "freelance"
    assert rahmen.ist_freiberuflich(job)
    krit = fuer_scoring(db)
    befund = _daumen_entfernung(db, h, 300)
    assert befund["grenze_km"] == grenze_km(krit, "freelance") > grenze_km(krit, "festanstellung")


def test_ohne_angabe_entscheiden_portal_und_titel(db):
    mcp = _mcp(db)
    portal = _browser(db, mcp, [_treffer("Berater Prozesse")], quelle="freelancermap")
    titel = _browser(db, mcp, [_treffer("Praktikum Projektsteuerung")])
    sonst = _browser(db, mcp, [_treffer("Sachbearbeitung Einkauf")])
    assert _zeile(db, portal["angelegt"][0]["hash"])["employment_type"] == "freelance"
    assert _zeile(db, titel["angelegt"][0]["hash"])["employment_type"] == "praktikum"
    assert _zeile(db, sonst["angelegt"][0]["hash"])["employment_type"] == "festanstellung"


def test_linkedin_remote_true(db):
    from bewerbungs_assistent.job_scraper import linkedin_voyager as lv
    mcp = _mcp(db)
    text = (TEXT * 3)[: max(lv.MIN_BESCHREIBUNG + 50, len(TEXT))]
    res = _call(mcp, "linkedin_treffer_uebernehmen", {"treffer": [
        {"job_id": "4000000001", "titel": "Projektleitung Musterprojekt", "firma": "Musterfirma GmbH",
         "beschreibung": text, "remote": True, "anstellungsart": "contract"}], "dry_run": False})
    h = res["angelegt"][0]["hash"]
    zeile = _zeile(db, h)
    assert (zeile["remote_level"], zeile["employment_type"]) == ("remote", "freelance")


def test_altbestand_true_false_wird_bereinigt(db):
    from bewerbungs_assistent.services import remote_jobspy
    db.save_jobs([{"hash": f"alt1298x{i}", "title": f"Sachbearbeitung {i}", "company": "Musterfirma GmbH",
                   "url": f"https://example.com/alt/{i}", "source": "stepstone", "description": text,
                   "location": "Musterstadt"}
                  for i, text in enumerate([TEXT, TEXT, TEXT + " Hybrides Arbeiten moeglich."])])
    con = db.connect()
    for h, alt in (("alt1298x0", "True"), ("alt1298x1", "False"), ("alt1298x2", "Quark")):
        con.execute("UPDATE jobs SET remote_level=? WHERE hash=?", (alt, db.resolve_job_hash(h)))
    con.commit()
    erg = remote_jobspy.ungueltige_bereinigen(db)
    assert erg["status"] == "bereinigt" and erg["neu_bewertet"] == 3, erg
    assert [_zeile(db, f"alt1298x{i}")["remote_level"] for i in range(3)] == ["remote", "vor_ort", "hybrid"]
    assert remote_jobspy.ungueltige_bereinigen(db)["status"] == "nichts_zu_tun"


def test_altbestand_wird_beim_start_bereinigt(db, tmp_path):
    db.save_jobs([{"hash": "alt1298start", "title": "Sachbearbeitung", "company": "Musterfirma GmbH",
                   "url": "https://example.com/alt/start", "source": "stepstone", "description": TEXT,
                   "location": "Musterstadt"}])
    con = db.connect()
    con.execute("UPDATE jobs SET remote_level='True' WHERE hash=?", (db.resolve_job_hash("alt1298start"),))
    con.commit()
    from bewerbungs_assistent.database import Database
    zweite = Database(db_path=tmp_path / "test.db")
    zweite.initialize()
    assert str(tmp_path) in str(zweite.db_path)
    assert _zeile(zweite, "alt1298start")["remote_level"] == "remote"
    zweite.close()


# ── #1299: Handkorrektur ────────────────────────────────────────────

def _anlegen(db, h="hand1299", employment_type="festanstellung", remote_level="unbekannt", ort="Musterstadt"):
    db.save_jobs([{"hash": h, "title": "Projektleitung Systemeinfuehrung", "company": "Musterfirma GmbH",
                   "url": f"https://example.com/{h}", "source": "stepstone", "description": TEXT,
                   "location": ort, "employment_type": employment_type, "remote_level": remote_level}])
    return db.resolve_job_hash(h)


def test_mcp_setzt_art_umfang_remote(db):
    mcp = _mcp(db)
    _anlegen(db)
    res = _call(mcp, "stelle_bearbeiten", {"job_hash": "hand1299", "anstellungsart": "freiberuflich",
                                            "umfang": "teilzeit", "remote": "remote"})
    assert res.get("status") == "aktualisiert", res
    z = _zeile(db, "hand1299")
    assert (z["employment_type"], z["arbeitsumfang"], z["remote_level"]) == ("freelance", "teilzeit", "remote")
    assert (z["art_quelle"], z["umfang_quelle"], z["remote_quelle"]) == ("mensch",) * 3
    assert "score_neu_berechnet" in res and res.get("merkmale_hinweis")


@pytest.mark.parametrize("feld,wert", [("anstellungsart", "Mondvertrag"), ("umfang", "halbtags-ish"),
                                       ("remote", "Mondbasis"), ("anstellungsart", "teilzeit")])
def test_ungueltige_werte_werden_abgelehnt(db, feld, wert):
    mcp = _mcp(db)
    _anlegen(db)
    res = _call(mcp, "stelle_bearbeiten", {"job_hash": "hand1299", feld: wert})
    assert "fehler" in res, res
    z = _zeile(db, "hand1299")
    assert (z["employment_type"], z["remote_level"], z["art_quelle"]) == ("festanstellung", "unbekannt", None)


def test_handkorrektur_ueberlebt_suchlauf_und_nachzieh_lauf(db):
    mcp = _mcp(db)
    _anlegen(db)
    _call(mcp, "stelle_bearbeiten", {"job_hash": "hand1299", "anstellungsart": "freelance",
                                     "umfang": "unbekannt", "remote": "remote"})
    # Derselbe Treffer kommt im naechsten Suchlauf mit den Angaben der Quelle zurueck.
    _anlegen(db, employment_type="festanstellung", remote_level="vor_ort")
    z = _zeile(db, "hand1299")
    assert (z["employment_type"], z["remote_level"], z["art_quelle"], z["remote_quelle"]) == (
        "freelance", "remote", "mensch", "mensch")
    _call(mcp, "stellen_merkmale_nachziehen", {"dry_run": False})
    assert _zeile(db, "hand1299")["employment_type"] == "freelance"
    # Automatik und Neubewertung fassen die Remote-Stufe nicht an.
    assert not db.set_job_remote_level("hand1299", "vor_ort")
    _call(mcp, "stelle_bearbeiten", {"job_hash": "hand1299", "ort": "Hybrid in Musterstadt"})
    assert _zeile(db, "hand1299")["remote_level"] == "remote"
    assert {"art_quelle", "umfang_quelle", "remote_quelle"} <= set(db._BEWAHREN)


def test_unbekannt_gibt_remote_an_die_automatik_zurueck(db):
    mcp = _mcp(db)
    _anlegen(db)
    _call(mcp, "stelle_bearbeiten", {"job_hash": "hand1299", "remote": "remote"})
    _call(mcp, "stelle_bearbeiten", {"job_hash": "hand1299", "remote": "unbekannt"})
    z = _zeile(db, "hand1299")
    assert (z["remote_level"], z["remote_quelle"]) == ("unbekannt", None)


def test_nach_der_aenderung_gilt_der_neue_rahmen(db):
    from bewerbungs_assistent.services import rahmen
    mcp = _mcp(db)
    _anlegen(db)
    assert _daumen_entfernung(db, "hand1299", 300).get("ausschluss") == "entfernung"
    _call(mcp, "stelle_bearbeiten", {"job_hash": "hand1299", "anstellungsart": "freelance"})
    job = db.get_job("hand1299")
    assert rahmen.ist_freiberuflich(job)
    assert _daumen_entfernung(db, "hand1299", 300)["grenze_km"] > 40
    _call(mcp, "stelle_bearbeiten", {"job_hash": "hand1299", "remote": "remote"})
    assert not _daumen_entfernung(db, "hand1299", 3000).get("ausschluss")


def test_ort_100_prozent_remote_ersetzt_altwert(db):
    mcp = _mcp(db)
    _anlegen(db)
    con = db.connect()
    con.execute("UPDATE jobs SET remote_level='True' WHERE hash=?", (db.resolve_job_hash("hand1299"),))
    con.commit()
    res = _call(mcp, "stelle_bearbeiten", {"job_hash": "hand1299",
                                            "ort": "100 % remote (Agentur in Musterstadt)"})
    assert _zeile(db, "hand1299")["remote_level"] == "remote", res
    assert res.get("remote_neu") == {"vorher": "True", "jetzt": "remote"}


def test_ort_fuellt_unbekannt_aber_ueberschreibt_keine_gueltige_angabe(db):
    mcp = _mcp(db)
    _anlegen(db)
    _call(mcp, "stelle_bearbeiten", {"job_hash": "hand1299", "ort": "Voll remote (Sitz Musterstadt)"})
    assert _zeile(db, "hand1299")["remote_level"] == "remote"
    _anlegen(db, h="quelle1299", remote_level="vor_ort")
    _call(mcp, "stelle_bearbeiten", {"job_hash": "quelle1299", "ort": "100 % remote"})
    assert _zeile(db, "quelle1299")["remote_level"] == "vor_ort"   # #1184: die Angabe der Quelle bleibt


def test_dashboard_aendert_und_lehnt_ab(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    _anlegen(db)
    client = TestClient(dash.app)
    r = client.put("/api/jobs/hand1299", json={"employment_type": "freelance", "remote_level": "hybrid",
                                               "arbeitsumfang": "vollzeit"})
    assert r.status_code == 200, r.text
    assert set(r.json()["geaendert"]) >= {"employment_type", "remote_level", "arbeitsumfang"}
    z = _zeile(db, "hand1299")
    assert (z["employment_type"], z["remote_level"], z["arbeitsumfang"]) == ("freelance", "hybrid", "vollzeit")
    assert client.put("/api/jobs/hand1299", json={"remote_level": "Mondbasis"}).status_code == 400
    assert _zeile(db, "hand1299")["remote_level"] == "hybrid"
