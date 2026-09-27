"""#1094: Dashboard und Claude legen Bewerbungen nach denselben Regeln an
und wechseln ihren Status nach denselben Regeln."""
from __future__ import annotations

import ast
import asyncio
import logging
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "bewerbungs_assistent"


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Lebenszyklus"})
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
    mcp = FastMCP("PBP #1094")
    register_all(mcp, db, logging.getLogger("test.1094"))

    async def lauf():
        t = await mcp.get_tool(name)
        return (await t.run(args)).structured_content
    return asyncio.run(lauf())


def _stelle(db, nr):
    h = f"stelle1094x{nr}"
    db.save_jobs([{"hash": h, "title": f"Sachbearbeitung {nr}",
                   "company": f"Musterbetrieb {nr} GmbH",
                   "url": f"https://example.com/1094/{nr}", "source": "manuell",
                   "description": "Wir suchen Unterstützung in der Sachbearbeitung. " * 5}])
    return h


def _bewerbung(db, nr, status="in_vorbereitung", mit_stelle=True):
    h = _stelle(db, nr) if mit_stelle else None
    return db.add_application({"title": f"Sachbearbeitung {nr}",
                               "company": f"Musterbetrieb {nr} GmbH",
                               "job_hash": h, "status": status, "applied_at": ""})


def _zustand(db, aid):
    app = db.get_application(aid)
    job = db.get_job(app["job_hash"]) if app.get("job_hash") else None
    offen = [fu for fu in db.get_pending_follow_ups() if fu["application_id"] == aid]
    return {
        "status": app["status"],
        "applied_at": bool((app.get("applied_at") or "").strip()),
        "stelle_aktiv": bool(job and job.get("is_active")),
        "erinnerungen": len(offen),
        "erinnerung_hat_text": all((fu.get("template") or "").strip() for fu in offen),
        "ereignisse": sorted(e["status"] for e in app.get("events", [])),
    }


def _dashboard_status(aid, status):
    return _client().put(f"/api/applications/{aid}/status", json={"status": status})


def _mcp_status(db, aid, status):
    return _werkzeug(db, "bewerbung_status_aendern",
                     {"bewerbung_id": aid, "neuer_status": status})


# ── AK 1: beide Wege, derselbe Zustand ──────────────────────────────

def test_beworben_auf_beiden_wegen_gleich(db):
    a = _bewerbung(db, 1)
    b = _bewerbung(db, 2)
    assert _dashboard_status(a, "beworben").status_code == 200
    assert _mcp_status(db, b, "beworben")["status"] == "aktualisiert"
    za, zb = _zustand(db, a), _zustand(db, b)
    assert za == zb, (za, zb)
    assert za["applied_at"] and not za["stelle_aktiv"]
    assert za["erinnerungen"] == 1 and za["erinnerung_hat_text"]


# ── AK 2: uebersprungenes "beworben" ────────────────────────────────

def test_uebersprungen_traegt_datum_nach(db):
    a = _bewerbung(db, 1)
    b = _bewerbung(db, 2)
    antwort = _dashboard_status(a, "interview").json()
    assert antwort["lifecycle"]["applied_at"]
    assert _mcp_status(db, b, "interview").get("applied_at_nachgetragen")
    assert _zustand(db, a) == _zustand(db, b)
    assert _zustand(db, a)["applied_at"]


# ── AK 3: Endstatus laesst Dokumente veralten ───────────────────────

def _dokument(db, aid, nr):
    did = db.add_document({"filename": f"anschreiben{nr}.pdf", "doc_type": "anschreiben",
                           "filepath": f"/tmp/x{nr}.pdf", "extracted_text": "Text"})
    db.connect().execute("UPDATE documents SET linked_application_id=? WHERE id=?", (aid, did))
    db.connect().commit()
    return did


def _lifecycle(db, did):
    return db.connect().execute("SELECT lifecycle FROM documents WHERE id=?",
                                (did,)).fetchone()["lifecycle"]


def test_endstatus_dokumente_auf_beiden_wegen(db):
    a, b = _bewerbung(db, 1, "beworben"), _bewerbung(db, 2, "beworben")
    da, dbb = _dokument(db, a, 1), _dokument(db, b, 2)
    assert _dashboard_status(a, "abgelehnt").json()["lifecycle"]["dokumente_veraltet"] == 1
    _mcp_status(db, b, "abgelehnt")
    assert _lifecycle(db, da) == _lifecycle(db, dbb) == "veraltet"


# ── AK 4: Rueckgaengig nimmt alles zurueck ──────────────────────────

def test_rueckgaengig_nach_beworben(db):
    a = _bewerbung(db, 1)
    vorher = _zustand(db, a)
    weg = _dashboard_status(a, "beworben").json()["rueckweg"]
    r = _client().post(f"/api/applications/{a}/status/rueckgaengig", json={"rueckweg": weg})
    assert r.status_code == 200, r.text
    assert _zustand(db, a) == vorher


def test_rueckgaengig_nach_absage_holt_dokument_zurueck(db):
    a = _bewerbung(db, 1, "beworben")
    did = _dokument(db, a, 1)
    weg = _dashboard_status(a, "abgelehnt").json()["rueckweg"]
    _client().post(f"/api/applications/{a}/status/rueckgaengig", json={"rueckweg": weg})
    assert _lifecycle(db, did) == "aktiv"


def test_rueckgaengig_holt_keine_frueher_aussortierte_stelle(db):
    """Nur was der Wechsel weggelegt hat, kommt zurueck."""
    a = _bewerbung(db, 1)
    h = db.get_application(a)["job_hash"]
    db.dismiss_job(h, reason="zu_weit_entfernt")
    weg = _dashboard_status(a, "beworben").json()["rueckweg"]
    assert not weg["stelle_aussortiert"]
    _client().post(f"/api/applications/{a}/status/rueckgaengig", json={"rueckweg": weg})
    job = db.get_job(h)
    assert not job["is_active"] and job["dismiss_reason"] == "zu_weit_entfernt"


# ── AK 5: Anlage im Dashboard wie bewerbung_erstellen ───────────────

def test_anlage_im_dashboard(db):
    h = _stelle(db, 1)
    r = _client().post("/api/applications", json={
        "title": "Sachbearbeitung 1", "company": "Musterbetrieb 1 GmbH",
        "job_hash": h, "status": "beworben",
        "ansprechpartner": "Erika Beispiel", "kontakt_email": "erika@example.com"})
    assert r.status_code == 200, r.text
    aid = r.json()["id"]
    assert r.json()["nachfass_in_tagen"] == 7 and r.json()["stelle_aussortiert"]
    app = db.get_application(aid)
    assert "Sachbearbeitung" in (app.get("description_snapshot") or "")
    assert not db.get_job(h)["is_active"]
    kontakte = [k for k in db.list_contacts() if k.get("email") == "erika@example.com"]
    assert len(kontakte) == 1


def test_anlage_gleich_auf_beiden_wegen(db):
    ha, hb = _stelle(db, 1), _stelle(db, 2)
    a = _client().post("/api/applications", json={
        "title": "Sachbearbeitung 1", "company": "Musterbetrieb 1 GmbH",
        "job_hash": ha, "status": "beworben"}).json()["id"]
    b = _werkzeug(db, "bewerbung_erstellen", {
        "title": "Sachbearbeitung 2", "company": "Musterbetrieb 2 GmbH",
        "job_hash": hb, "status": "beworben"})["bewerbung_id_voll"]
    assert _zustand(db, a) == _zustand(db, b)


def test_zweite_anlage_wird_genannt(db):
    h = _stelle(db, 1)
    daten = {"title": "Sachbearbeitung 1", "company": "Musterbetrieb 1 GmbH",
             "job_hash": h, "status": "in_vorbereitung"}
    erste = _client().post("/api/applications", json=daten).json()["id"]
    r = _client().post("/api/applications", json=daten)
    assert r.status_code == 409
    assert r.json()["duplikat"]["bestehende_bewerbung_id_voll"] == erste
    assert "Trotzdem" in r.json()["error"]
    assert _client().post("/api/applications", json={**daten, "force": True}).status_code == 200


def test_mcp_meldet_dublette_weiter(db):
    args = {"title": "Sachbearbeitung 1", "company": "Musterbetrieb 1 GmbH"}
    _werkzeug(db, "bewerbung_erstellen", args)
    erg = _werkzeug(db, "bewerbung_erstellen", args)
    assert erg["status"] == "duplikat" and erg["match_typ"] == "exakt"


# ── AK 6: Status aus einer Mail — ein Ereignis ──────────────────────

def test_mailstatus_ein_ereignis(db):
    a = _bewerbung(db, 1, "beworben")
    mid = db.add_email({"subject": "Einladung", "sender": "hr@example.com",
                        "body_text": "Wir laden Sie ein.", "application_id": a})
    r = _client().post(f"/api/emails/{mid}/apply-status", json={"status": "interview"})
    assert r.status_code == 200, r.text
    ereignisse = [e for e in db.get_application(a)["events"] if e["status"] == "interview"]
    assert len(ereignisse) == 1
    assert "Status aus E-Mail" in (ereignisse[0].get("notes") or "")


# ── AK 7: unbekannte Status ueberall abgewiesen ─────────────────────

def test_unbekannter_status_ueberall(db):
    a = _bewerbung(db, 1)
    assert _dashboard_status(a, "entwurf").status_code == 400
    assert "fehler" in _mcp_status(db, a, "entwurf")
    mid = db.add_email({"subject": "x", "sender": "x@example.com", "body_text": "x",
                        "application_id": a})
    assert _client().post(f"/api/emails/{mid}/apply-status",
                          json={"status": "entwurf"}).status_code == 400
    assert _client().post("/api/applications", json={
        "title": "A", "company": "B GmbH", "status": "entwurf"}).status_code == 400
    assert db.get_application(a)["status"] == "in_vorbereitung"


def test_alter_status_nennt_den_neuen(db):
    a = _bewerbung(db, 1)
    r = _dashboard_status(a, "warte_auf_rueckmeldung")
    assert r.status_code == 400 and "eingangsbestaetigung" in r.json()["error"]


# ── Nachfassungen (Kommentar im Issue) ──────────────────────────────

def test_nachfassung_doppelklick(db):
    a = _bewerbung(db, 1, "beworben")
    fid = db.add_follow_up(a, "2027-01-01", template="Nachfassen")
    c = _client()
    assert c.post(f"/api/follow-ups/{fid}/complete", json={"notiz": "angerufen"}).status_code == 200
    zweiter = c.post(f"/api/follow-ups/{fid}/complete", json={"notiz": "angerufen"})
    assert zweiter.status_code == 409 and "schon erledigt" in zweiter.json()["error"]
    notizen = [e for e in db.get_application(a)["events"] if "angerufen" in (e.get("notes") or "")]
    assert len(notizen) == 1


def test_hinfaellig_nicht_nachtraeglich_erledigt(db):
    a = _bewerbung(db, 1, "beworben")
    fid = db.add_follow_up(a, "2027-01-01", template="Nachfassen")
    c = _client()
    assert c.post(f"/api/follow-ups/{fid}/dismiss", json={}).status_code == 200
    assert c.post(f"/api/follow-ups/{fid}/complete", json={}).status_code == 409
    assert db.get_follow_up(fid)["status"] == "hinfaellig"
    assert "fehler" in _werkzeug(db, "follow_up_erledigen", {"follow_up_id": fid})


def test_leerer_erinnerungstext_abgewiesen(db):
    a = _bewerbung(db, 1, "beworben")
    fid = db.add_follow_up(a, "2027-01-01", template="Nachfassen")
    r = _client().put(f"/api/follow-ups/{fid}", json={"template": "   "})
    assert r.status_code == 400
    assert db.get_follow_up(fid)["template"] == "Nachfassen"
    assert _client().put(f"/api/follow-ups/{fid}",
                         json={"scheduled_date": "2027-02-01"}).status_code == 200


# ── AK 8: Guard ─────────────────────────────────────────────────────

#: Wer ausserhalb des Dienstes schreiben darf — mit Grund.
ERLAUBT = {
    ("dashboard.py", "api_import_folder"):
        "Import alter Bewerbungen aus Ordnern: keine Erinnerung, keine Stelle",
    ("dashboard.py", "api_upload_document"):
        "rekonstruiert eine Bewerbung aus einem hochgeladenen Dokument",
    ("dashboard.py", "api_create_application_from_email"):
        "Anfrage aus einer Mail, Status offen — keine Bewerbung im engeren Sinn",
    ("tools/dokumente.py", "bewerbungs_dokumente_erkennen"):
        "rekonstruiert Altbewerbungen aus Dokumenten mit ihrem alten Datum",
}


def _aufrufer():
    """(Datei, innerste umschliessende Funktion) je Aufruf."""
    for p in SRC.rglob("*.py"):
        rel = str(p.relative_to(SRC))
        if rel in ("services/bewerbung_lebenszyklus.py", "database.py"):
            continue

        def gehe(knoten, funktion):
            for kind in ast.iter_child_nodes(knoten):
                f = kind.name if isinstance(kind, (ast.FunctionDef, ast.AsyncFunctionDef)) else funktion
                if (isinstance(kind, ast.Call) and isinstance(kind.func, ast.Attribute)
                        and kind.func.attr in ("update_application_status", "add_application")):
                    yield rel, funktion
                yield from gehe(kind, f)
        yield from gehe(ast.parse(p.read_text(encoding="utf-8-sig")), None)


def test_nur_begruendete_aufrufer():
    innerste = {}
    for rel, name in _aufrufer():
        innerste.setdefault(rel, set()).add(name)
    funde = [f"{rel}:{n}" for rel, namen in innerste.items() for n in namen
             if (rel, n) not in ERLAUBT]
    assert not funde, funde
    assert all(len(g) > 20 for g in ERLAUBT.values())


def test_fremdes_profil_bleibt_unberuehrt(db):
    """Datum und Stelle werden VOR dem Wechsel gesetzt — also muss die
    Profilpruefung davor stehen."""
    fremd = _bewerbung(db, 1)
    h = db.get_application(fremd)["job_hash"]
    db.switch_profile(db.create_profile("Anderes Profil"))
    assert _dashboard_status(fremd, "beworben").status_code == 404
    roh = db.connect().execute("SELECT status, applied_at FROM applications WHERE id=?",
                               (fremd,)).fetchone()
    assert roh["status"] == "in_vorbereitung" and not (roh["applied_at"] or "")
    assert db.connect().execute("SELECT is_active FROM jobs WHERE hash LIKE ?",
                                (f"%{h}",)).fetchone()["is_active"] == 1


def test_dokumentaktion_legt_gueltigen_status_an(db):
    """Die Routing-Aktion schrieb den Status 'anfrage', den es nicht gibt."""
    did = db.add_document({"filename": "anfrage.eml", "doc_type": "recruiter_anfrage",
                           "filepath": "/tmp/a.eml", "extracted_text": "Interessante Stelle"})
    erg = _werkzeug(db, "dokument_aktion_ausfuehren", {
        "dokument_id": did, "aktion": "bewerbung_erfassen",
        "args": {"firma": "Musterbetrieb GmbH", "titel": "Sachbearbeitung"}})
    assert erg["status"] == "umgesetzt", erg
    status = db.connect().execute("SELECT status FROM applications WHERE company=?",
                                  ("Musterbetrieb GmbH",)).fetchone()["status"]
    from bewerbungs_assistent.services.bewerbung_status import ALLE
    assert status in ALLE


def test_dokumentaktion_bei_dublette_bleibt_dokument_im_plan(db):
    _werkzeug(db, "bewerbung_erstellen", {"title": "Sachbearbeitung",
                                          "company": "Musterbetrieb GmbH"})
    did = db.add_document({"filename": "anfrage.eml", "doc_type": "recruiter_anfrage",
                           "filepath": "/tmp/a.eml", "extracted_text": "Interessante Stelle"})
    erg = _werkzeug(db, "dokument_aktion_ausfuehren", {
        "dokument_id": did, "aktion": "bewerbung_erfassen",
        "args": {"firma": "Musterbetrieb GmbH", "titel": "Sachbearbeitung"}})
    assert erg["status"] == "nicht_umgesetzt", erg
    stand = db.connect().execute("SELECT extraction_status FROM documents WHERE id=?",
                                 (did,)).fetchone()["extraction_status"]
    assert stand != "angewendet"
