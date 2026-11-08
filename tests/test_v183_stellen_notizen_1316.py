"""#1316: eigene Notizen an Stellen, getrennt vom Anzeigentext.

Bis 1.8.2 gab es fuer eine Stelle ohne Bewerbung nur die Konvention aus #603: Notizen hinter eine Zeile `---` an die
Beschreibung haengen. Original und Notiz lagen im selben Feld, jeder Nachtrag verlangte den ganzen Anzeigentext, das
Nachladen konnte die Notizen ueberschreiben, und beim Anlegen einer Bewerbung gingen sie nicht mit.

Die Abnahme aus dem Issue, je eine Pruefung:

* Notiz an eine Stelle ohne Bewerbung, ohne die Beschreibung zu senden
* Nachladen der Beschreibung laesst die Notizen unberuehrt
* eine Notiz "Rentenversicherung, PLM, Materialstamm" aendert die Punkte nicht
* `fit_analyse` zeigt die Notizen in einem eigenen Feld, nicht in `stellenbeschreibung`
* nach `bewerbung_erstellen(job_hash=...)` stehen sie in der Timeline der Bewerbung
* alte `---`-Notizen: erkannt und nur auf Wunsch je Stelle verschoben (nie still)

Testdaten fiktiv (Musterfirma GmbH). Die Datenbank liegt in einem eigenen Temp-Ordner (BA_DATA_DIR).
"""
from __future__ import annotations

import asyncio
import logging
import os

import pytest

ANZEIGE = ("Wir suchen eine erfahrene Projektleitung fuer die Einfuehrung eines neuen Systems. "
           "Aufgaben: Planung, Steuerung, Abstimmung mit Fachbereichen und Dienstleistern. ") * 3
NOTIZ = "Rentenversicherung, PLM, Materialstamm"


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test"})
    # PLM und Materialstamm als Suchbegriffe: traefe die Notiz das Scoring, stiegen die Punkte.
    d.set_search_criteria("keywords_muss", ["projektleitung"])
    d.set_search_criteria("keywords_plus", ["plm", "materialstamm", "rentenversicherung"])
    import bewerbungs_assistent.dashboard as dash
    dash._db = d
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _mcp(db):
    from fastmcp import FastMCP
    mcp = FastMCP("PBP #1316")
    from bewerbungs_assistent.tools import register_all
    register_all(mcp, db, logging.getLogger("test.1316"))
    return mcp


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _stelle(mcp, beschreibung=ANZEIGE, titel="Projektleitung Systemeinfuehrung"):
    res = _call(mcp, "stelle_manuell_anlegen", {
        "titel": titel, "firma": "Musterfirma GmbH", "url": f"https://example.com/stelle/{abs(hash(titel))}",
        "ort": "Musterstadt", "beschreibung": beschreibung})
    h = res.get("hash") or res.get("job_hash") or res.get("stellen_hash")
    assert h, res
    return h


def _punkte(db, h):
    from bewerbungs_assistent.job_scraper import calculate_score
    from bewerbungs_assistent.services.scoring_kriterien import fuer_scoring
    return calculate_score(db.get_job(h), fuer_scoring(db))


# ── Abnahme 1: Notiz ohne Beschreibung ─────────────────────────────

def test_notiz_ohne_beschreibung(db):
    mcp = _mcp(db)
    h = _stelle(mcp)
    vorher = db.get_job(h)
    res = _call(mcp, "stelle_bearbeiten", {"job_hash": h, "notiz": NOTIZ})
    assert "fehler" not in res, res
    assert res["notiz"]["text"] == NOTIZ and res["notiz"]["von"] == "von Claude", res
    assert res["notizen_anzahl"] == 1
    nachher = db.get_job(h)
    assert nachher["description"] == vorher["description"], "die Beschreibung darf sich durch eine Notiz nicht aendern"
    from bewerbungs_assistent.services import stellen_notizen as sn
    eintraege = sn.liste(db, h)
    assert [e["herkunft"] for e in eintraege] == ["ki"]
    # gespeichert mit dem Profilbezug und der gespeicherten Hash-Form
    zeile = db.connect().execute("SELECT * FROM job_notes").fetchone()
    assert zeile["job_hash"] == db.resolve_job_hash(h) and zeile["profile_id"] == db.get_active_profile_id()


def test_notiz_und_feld_zugleich(db):
    mcp = _mcp(db)
    h = _stelle(mcp)
    res = _call(mcp, "stelle_bearbeiten", {"job_hash": h, "ort": "Beispielstadt", "notiz": "Ort laut Telefonat"})
    assert "location" in res.get("geaenderte_felder", []) and res["notiz"]["text"] == "Ort laut Telefonat", sorted(res)


def test_leere_notiz_wird_abgelehnt(db):
    from bewerbungs_assistent.services import stellen_notizen as sn
    mcp = _mcp(db)
    h = _stelle(mcp)
    assert sn.anlegen(db, h, "   ")["grund"] == "text"
    assert sn.anlegen(db, "gibtsnicht", "x")["grund"] == "nicht_gefunden"
    assert sn.anlegen(db, h, "x", herkunft="erfunden")["grund"] == "herkunft"


# ── Abnahme 2: Nachladen laesst Notizen unberuehrt ─────────────────

def test_nachladen_laesst_notizen_stehen(db):
    from bewerbungs_assistent.services import nachladen, stellen_notizen as sn
    mcp = _mcp(db)
    h = _stelle(mcp)
    sn.anlegen(db, h, NOTIZ, herkunft="mensch")
    neu = "Ganz neuer Anzeigentext aus der Quelle. " * 5
    nachladen.text_uebernehmen(db, db.resolve_job_hash(h), neu)
    assert db.get_job(h)["description"].startswith("Ganz neuer Anzeigentext")
    assert [e["text"] for e in sn.liste(db, h)] == [NOTIZ]


# ── Abnahme 3: dieselben Punkte mit und ohne Notiz ─────────────────

def test_notiz_aendert_die_punkte_nicht(db):
    mcp = _mcp(db)
    h = _stelle(mcp)
    ohne = _punkte(db, h)
    gespeichert_ohne = db.get_job(h)["score"]
    _call(mcp, "stelle_bearbeiten", {"job_hash": h, "notiz": NOTIZ})
    assert _punkte(db, h) == ohne
    assert db.get_job(h)["score"] == gespeichert_ohne
    fa = _call(mcp, "fit_analyse", {"job_hash": h})
    assert not any(k in str(fa.get("plus_hits")).lower() for k in ("plm", "materialstamm", "rentenversicherung")), fa


# ── Abnahme 4: fit_analyse mit eigenem Feld ────────────────────────

def test_fit_analyse_zeigt_notizen_getrennt(db):
    mcp = _mcp(db)
    h = _stelle(mcp)
    _call(mcp, "stelle_bearbeiten", {"job_hash": h, "notiz": NOTIZ})
    fa = _call(mcp, "fit_analyse", {"job_hash": h})
    assert [n["text"] for n in fa["notizen"]] == [NOTIZ], fa.get("notizen")
    assert NOTIZ not in fa["stellenbeschreibung"]


def test_stellen_anzeigen_zaehlt_notizen(db):
    mcp = _mcp(db)
    h = _stelle(mcp)
    andere = _stelle(mcp, titel="Projektleitung Zweitsystem")
    _call(mcp, "stelle_bearbeiten", {"job_hash": h, "notiz": "eins"})
    _call(mcp, "stelle_bearbeiten", {"job_hash": h, "notiz": "zwei"})
    res = _call(mcp, "stellen_anzeigen", {"ohne_schwelle": True})
    zeilen = {s["hash"]: s for s in res["stellen"]}
    assert zeilen[h].get("notizen") == 2, zeilen[h]
    assert "notizen" not in zeilen[andere]


# ── Abnahme 5: Bewerbung aus der Stelle ────────────────────────────

def test_bewerbung_uebernimmt_die_notizen(db):
    from bewerbungs_assistent.services import stellen_notizen as sn
    mcp = _mcp(db)
    h = _stelle(mcp)
    sn.anlegen(db, h, "Rechnung: 40 und 50 Prozent", herkunft="mensch")
    _call(mcp, "stelle_bearbeiten", {"job_hash": h, "notiz": NOTIZ})
    res = _call(mcp, "bewerbung_erstellen", {"title": "Projektleitung Systemeinfuehrung", "company": "Musterfirma GmbH",
                                             "job_hash": h, "status": "in_vorbereitung"})
    assert res.get("stellen_notizen_uebernommen") == 2, res
    events = db.connect().execute(
        "SELECT notes FROM application_events WHERE application_id=? AND status='notiz' ORDER BY id",
        (res["bewerbung_id_voll"],)).fetchall()
    texte = [e["notes"] for e in events]
    assert any("von dir" in t and "40 und 50 Prozent" in t for t in texte), texte
    assert any("von Claude" in t and NOTIZ in t for t in texte), texte
    # an der Stelle bleiben sie stehen
    assert len(sn.liste(db, h)) == 2


def test_bewerbung_ohne_stelle_bleibt_ohne_notizen(db):
    mcp = _mcp(db)
    res = _call(mcp, "bewerbung_erstellen", {"title": "Freie Bewerbung", "company": "Beispiel AG",
                                             "status": "in_vorbereitung"})
    assert "stellen_notizen_uebernommen" not in res, res


# ── Altbestand: Notizen hinter '---' ───────────────────────────────

def test_notizteil_erkennen():
    from bewerbungs_assistent.services import stellen_notizen as sn
    t = sn.notizteil_erkennen(ANZEIGE + "\n---\nMeine Rechnung\nZeile 2")
    assert t == {"anzeige": ANZEIGE.strip(), "notizen": "Meine Rechnung\nZeile 2"}
    assert sn.notizteil_erkennen(ANZEIGE) is None
    assert sn.notizteil_erkennen(ANZEIGE + "\n---\n") is None, "eine leere Trennzeile ist kein Notizteil"
    assert sn.notizteil_erkennen("\n---\nnur Notiz") is None, "ohne Anzeigenteil wird nichts geteilt"
    # Ueberschriften-Marker aus #603 bleiben in der Notiz stehen
    t = sn.notizteil_erkennen(ANZEIGE + "\n## Analyse\nPasst gut")
    assert t["notizen"].startswith("## Analyse")


def test_altbestand_wird_nur_auf_wunsch_verschoben(db):
    from bewerbungs_assistent.services import stellen_notizen as sn
    mcp = _mcp(db)
    h = _stelle(mcp, beschreibung=ANZEIGE + "\n---\nRentenversicherung pruefen")
    punkte_vorher = _punkte(db, h)
    # Lesen erkennt, aendert aber nichts
    fa = _call(mcp, "fit_analyse", {"job_hash": h})
    assert "notizteil_in_beschreibung" in fa
    assert "Rentenversicherung pruefen" in db.get_job(h)["description"]
    assert sn.liste(db, h) == []
    # erst der ausdrueckliche Aufruf verschiebt
    res = _call(mcp, "stelle_bearbeiten", {"job_hash": h, "notiz_aus_beschreibung": True})
    assert res["notiz_aus_beschreibung"]["text"] == "Rentenversicherung pruefen", res
    assert db.get_job(h)["description"] == ANZEIGE.strip()
    assert [e["herkunft"] for e in sn.liste(db, h)] == ["migriert"]
    assert _punkte(db, h) == punkte_vorher, "der Anzeigenteil ist derselbe, den das Scoring schon bisher gewertet hat"
    # ein zweiter Aufruf findet nichts mehr
    res = _call(mcp, "stelle_bearbeiten", {"job_hash": h, "notiz_aus_beschreibung": True})
    assert "fehler" in res


# ── Profilbezug, Loeschbereich, Zusammenfuehren ────────────────────

def test_notizen_gehoeren_zum_profil(db):
    from bewerbungs_assistent.services import stellen_notizen as sn
    mcp = _mcp(db)
    h = _stelle(mcp)
    sn.anlegen(db, h, "nur im ersten Profil")
    zweites = db.create_profile("Zweit", "")
    db.switch_profile(zweites)
    assert sn.liste(db, h) == []
    assert sn.anzahl_je_stelle(db) == {}


def test_loeschbereich_stellen_nimmt_die_notizen_mit(db):
    from bewerbungs_assistent.services import loeschbereiche as lb, stellen_notizen as sn
    assert "job_notes" in lb.BEREICHE["stellen"]
    assert "job_notes" not in lb.unzugeordnet(db)["fehlt_im_bereich"]
    mcp = _mcp(db)
    h = _stelle(mcp)
    sn.anlegen(db, h, "weg damit")
    lb.leeren(db, ["stellen"], profil_id=db.get_active_profile_id(), dry_run=False)
    assert db.connect().execute("SELECT COUNT(*) FROM job_notes").fetchone()[0] == 0


# ── Dashboard ──────────────────────────────────────────────────────

def test_rest_endpunkte(db):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    mcp = _mcp(db)
    h = _stelle(mcp, beschreibung=ANZEIGE + "\n---\nalter Teil")
    client = TestClient(dash.app)
    r = client.get(f"/api/jobs/{h}/notizen").json()
    assert r["notizen"] == [] and r["notizteil_in_beschreibung"]["notizen"] == "alter Teil"
    r = client.post(f"/api/jobs/{h}/notizen", json={"text": "Zeile 1\nZeile 2"})
    assert r.status_code == 200 and r.json()["notiz"]["von"] == "von dir"
    nid = r.json()["notiz"]["id"]
    assert client.post(f"/api/jobs/{h}/notizen", json={"text": " "}).status_code == 400
    assert client.post("/api/jobs/gibtsnicht/notizen", json={"text": "x"}).status_code == 404
    r = client.put(f"/api/jobs/{h}/notizen/{nid}", json={"text": "geaendert"})
    assert r.status_code == 200 and r.json()["notiz"]["text"] == "geaendert"
    assert client.post(f"/api/jobs/{h}/notizen/aus-beschreibung").status_code == 200
    r = client.get(f"/api/jobs/{h}/notizen").json()
    assert [n["text"] for n in r["notizen"]] == ["geaendert", "alter Teil"]
    assert r["notizteil_in_beschreibung"] is None
    assert client.delete(f"/api/jobs/{h}/notizen/{nid}").status_code == 200
    assert client.delete(f"/api/jobs/{h}/notizen/{nid}").status_code == 404
    assert len(client.get(f"/api/jobs/{h}/notizen").json()["notizen"]) == 1


def test_schema_schutz_haelt_die_neuen_schreibwege(db, monkeypatch):
    """Ist die Datenbank neuer als das Programm, weist der Schema-Schutz die schreibenden Notiz-Aufrufe ab (503)."""
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    from bewerbungs_assistent.services import schema_schutz
    mcp = _mcp(db)
    h = _stelle(mcp)
    monkeypatch.setattr(schema_schutz, "zu_neu", lambda *_a, **_k: {"datenbank": 99, "programm": 1, "text": "zu neu"})
    client = TestClient(dash.app)
    assert client.post(f"/api/jobs/{h}/notizen", json={"text": "x"}).status_code == 503
    assert client.delete(f"/api/jobs/{h}/notizen/1").status_code == 503
    assert client.get(f"/api/jobs/{h}/notizen").status_code == 200


def test_notizen_bleiben_an_ihrer_stelle(db):
    from bewerbungs_assistent.services import stellen_notizen as sn
    mcp = _mcp(db)
    h = _stelle(mcp)
    andere = _stelle(mcp, titel="Projektleitung Zweitsystem")
    sn.anlegen(db, h, "gehoert zur ersten")
    assert sn.liste(db, andere) == []
    nid = sn.liste(db, h)[0]["id"]
    assert sn.loeschen(db, andere, nid)["grund"] == "nicht_gefunden", "eine Notiz laesst sich nur ueber ihre Stelle loeschen"
    assert sn.aendern(db, andere, nid, "x")["grund"] == "nicht_gefunden"


def test_verschieben_scheitert_ohne_verlust(db, monkeypatch):
    """Laesst sich die Beschreibung nicht kuerzen, wird die schon angelegte Notiz wieder entfernt - nichts doppelt, nichts weg."""
    from bewerbungs_assistent.services import stelle_aendern, stellen_notizen as sn
    mcp = _mcp(db)
    h = _stelle(mcp, beschreibung=ANZEIGE + "\n---\nalter Teil")
    monkeypatch.setattr(stelle_aendern, "aendern", lambda *_a, **_k: {"ok": False, "fehler": "gesperrt"})
    erg = sn.aus_beschreibung_uebernehmen(db, h)
    assert not erg["ok"] and erg["grund"] == "beschreibung"
    assert sn.liste(db, h) == []
    assert "alter Teil" in db.get_job(h)["description"]
