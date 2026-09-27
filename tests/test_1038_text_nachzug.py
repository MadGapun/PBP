"""#1038 Punkt 4: Anzeigentexte nach dem Suchlauf nachladen — nur fuer
Treffer, die den Filter passiert haben, im Hintergrund, mit Grenze.

Kein Test fragt das Netz: `nachladen.beschreibung_holen` ist ersetzt.
Alle Firmen sind Platzhalter.
"""
from __future__ import annotations

import ast
import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

TEXT = ("Wir suchen eine Fachkraft fuer den Einkauf. Aufgaben: Bestellungen, "
        "Lieferantenpflege, Rechnungspruefung. Anforderungen: Ausbildung.")


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database
    importlib.reload(database)
    d = database.Database(db_path=tmp_path / "nachzug.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.switch_profile(d.create_profile("Nachzug"))
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def abrufe(monkeypatch):
    """Ersetzt den Abruf; zaehlt, welche Adressen gefragt wurden."""
    from bewerbungs_assistent.services import nachladen
    gefragt = []
    antworten = {}

    def holen(url, client, timeout=15):
        gefragt.append(url)
        return SimpleNamespace(text=antworten.get(url, TEXT), kopf={})

    monkeypatch.setattr(nachladen, "beschreibung_holen", holen)
    return SimpleNamespace(gefragt=gefragt, antworten=antworten)


def _stellen(db, n, text=""):
    jobs = [{"hash": f"h1038{i:03d}", "title": f"Einkauf {i}", "company": "Musterfirma",
             "url": f"https://jobs.example.org/stelle/{i}", "source": "jobspy_linkedin",
             "description": text} for i in range(n)]
    db.save_jobs(jobs)
    return [j["hash"] for j in jobs]


def _suchlauf(db, hashes):
    jid = db.create_background_job("jobsuche", {})
    db.update_background_job(jid, "fertig", progress=100, message="ok",
                             result={"total": len(hashes), "ohne_anzeigentext": hashes})
    return jid


def _text(db, h):
    return db.get_job(db.resolve_job_hash(h)).get("description") or ""


# ========================================================== der Weg


def test_nur_die_treffer_des_laufs_werden_geholt(db, abrufe):
    """AK 2: was der Filter verworfen hat (hier: nicht in der Liste),
    loest keinen Abruf aus."""
    from bewerbungs_assistent.services import text_nachzug
    alle = _stellen(db, 5)
    jid = _suchlauf(db, alle[:2])
    erg = text_nachzug.nach_suche(db, jid, client=object(), pause=0)
    assert erg["geholt"] == 2
    assert len(abrufe.gefragt) == 2
    assert _text(db, alle[0]).startswith("Wir suchen")
    assert _text(db, alle[4]) == ""


def test_ergebnis_steht_am_suchlauf_und_im_eigenen_job(db, abrufe):
    from bewerbungs_assistent.services import text_nachzug
    jid = _suchlauf(db, _stellen(db, 3))
    text_nachzug.nach_suche(db, jid, client=object(), pause=0)
    such = db.get_background_job(jid)
    assert such["status"] == "fertig"
    assert such["result"]["nachgeladen"] == {"geholt": 3, "fehlgeschlagen": 0, "offen": 0}
    assert such["result"]["total"] == 3, "das uebrige Ergebnis bleibt"
    eigene = db.connect().execute(
        "SELECT status, result FROM background_jobs WHERE job_type=?",
        (text_nachzug.JOB_TYP,)).fetchall()
    assert len(eigene) == 1 and eigene[0]["status"] == "fertig"


def test_hoechstens_die_grenze_je_lauf(db, abrufe, monkeypatch):
    from bewerbungs_assistent.services import text_nachzug
    monkeypatch.setattr(text_nachzug, "MAX_JE_LAUF", 3)
    jid = _suchlauf(db, _stellen(db, 5))
    erg = text_nachzug.nach_suche(db, jid, client=object(), pause=0)
    assert erg["versucht"] == 3 and erg["offen"] == 2
    assert len(abrufe.gefragt) == 3


def test_stelle_mit_text_wird_nicht_gefragt(db, abrufe):
    from bewerbungs_assistent.services import text_nachzug
    mit = _stellen(db, 1, text=TEXT)
    jid = _suchlauf(db, mit)
    assert text_nachzug.nach_suche(db, jid, client=object(), pause=0)["kandidaten"] == 0
    assert abrufe.gefragt == []


def test_fehlschlag_zaehlt_und_drei_sind_genug(db, abrufe):
    from bewerbungs_assistent.services import text_nachzug
    h = _stellen(db, 1)
    abrufe.antworten["https://jobs.example.org/stelle/0"] = ""
    for _ in range(3):
        erg = text_nachzug.holen(db, h, max_jobs=5, client=object())
        assert erg["fehlgeschlagen"] == 1
    erg = text_nachzug.holen(db, h, max_jobs=5, client=object())
    assert erg["backoff"] == 1 and erg["versucht"] == 0
    assert len(abrufe.gefragt) == 3


def test_ohne_liste_und_bei_unfertigem_lauf_nichts(db, abrufe):
    from bewerbungs_assistent.services import text_nachzug
    jid = _suchlauf(db, [])
    assert text_nachzug.nach_suche(db, jid, client=object(), pause=0) is None
    laufend = db.create_background_job("jobsuche", {})
    db.update_background_job(laufend, "running", progress=50,
                             result={"ohne_anzeigentext": _stellen(db, 1)})
    assert text_nachzug.nach_suche(db, laufend, client=object(), pause=0) is None
    assert abrufe.gefragt == []


def test_andere_profile_bleiben_unberuehrt(db, abrufe):
    from bewerbungs_assistent.services import text_nachzug
    # die gespeicherte (profilgebundene) Kennung — so steht sie im Bestand
    fremd = [db.resolve_job_hash(h) for h in _stellen(db, 1)]
    assert ":" in fremd[0]
    db.switch_profile(db.create_profile("Anderes"))
    jid = _suchlauf(db, fremd)
    erg = text_nachzug.nach_suche(db, jid, client=object(), pause=0)
    assert erg["kandidaten"] == 0 and abrufe.gefragt == []


def test_auto_nachzug_nimmt_dieselbe_schleife(db, abrufe):
    import bewerbungs_assistent.dashboard as dash
    vorher = dash._db
    dash._db = db
    try:
        _stellen(db, 4)
        erg = dash._run_auto_refetch_descriptions("2026-10-01T00:00:00", max_jobs=2)
    finally:
        dash._db = vorher
    assert erg["successes"] == 2 and erg["processed"] == 2
    assert len(abrufe.gefragt) == 2


# ============================================================ Verdrahtung


def _quelle(teil):
    return (_repo() / "src" / "bewerbungs_assistent" / teil).read_text(encoding="utf-8-sig")


def test_erst_texte_dann_aussortierung():
    q = _quelle("services/jobsuche_start.py")
    assert q.index("text_nachzug.nach_suche(db, job_id)") < q.index(
        "auto_aussortierung.nach_suche(db, job_id)")


def test_suchlauf_merkt_sich_die_treffer_aus_unique():
    """Nur was den Filter passiert hat (`unique`), nicht die Rohtreffer."""
    q = _quelle("job_scraper/__init__.py")
    baum = ast.parse(q)
    gefunden = False
    for k in ast.walk(baum):
        if (isinstance(k, ast.Assign) and len(k.targets) == 1
                and isinstance(k.targets[0], ast.Subscript)
                and ast.unparse(k.targets[0]) == "result_data['ohne_anzeigentext']"):
            text = ast.unparse(k.value)
            assert " in unique" in text and "_min_text" in text
            gefunden = True
    assert gefunden


def test_lauf_hinweis_bekommt_die_zahl(db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    jid = db.create_background_job("jobsuche", {})
    db.update_background_job(jid, "fertig", progress=100, message="ok",
                             result={"total": 3, "nachgeladen": {"geholt": 2, "fehlgeschlagen": 0, "offen": 1}})
    vorher = dash._db
    dash._db = db
    try:
        last = TestClient(dash.app).get("/api/jobsuche/last").json()
    finally:
        dash._db = vorher
    assert last["nachgeladen"] == {"geholt": 2, "fehlgeschlagen": 0, "offen": 1}
