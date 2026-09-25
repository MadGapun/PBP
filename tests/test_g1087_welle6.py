"""Welle 6 aus #1087 — Einstellungen, Profil, Rueckweg, Hilfe, Kennzahlen.

* G61 (B2-B4, B6): Kennzahlen mit fester Bedeutung.
"""
import re
from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


FRONTEND = _repo() / "frontend" / "src"


def _lesen(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8-sig")


# ══ G61 — Kennzahlen mit fester Bedeutung ═══════════════════════════════

def test_g61_keine_zufaellige_perspektive():
    seite = _lesen(FRONTEND / "pages" / "DashboardPage.jsx")
    assert "Math.random" not in seite
    assert "bewerbungenProWoche(applicationTimestamps, wochenAnsicht)" in seite
    assert "WOCHEN_ANSICHTEN.map" in seite
    assert 'label="Bewerbungen pro Woche"' in seite


def test_g61_top_stellen_nach_den_regeln_des_stellen_tabs():
    seite = _lesen(FRONTEND / "pages" / "DashboardPage.jsx")
    assert 'listenParameter(FILTER_STANDARD, "", "", "active")' in seite
    assert "topStellen(data.topJobs || [])" in seite


def test_g61_kein_null_gehalt():
    seite = _lesen(FRONTEND / "pages" / "DashboardPage.jsx")
    assert "gehaltsWert(salaryMetrics.averageMin)" in seite
    assert "gehaltsWert(salaryMetrics.bandMin)" in seite
    assert '"Keine Angabe"' not in seite[seite.index("const salaryMetrics"):seite.index("const lastSearchAt")]


def test_g61_seitenleiste_zaehlt_nur_was_aufmerksamkeit_braucht():
    import sys
    sys.path.insert(0, str(_repo() / "src"))
    from bewerbungs_assistent.services.workspace_service import build_workspace_summary
    daten = build_workspace_summary(
        profile={"name": "Test", "positions": [], "education": [], "skills": [], "documents": []},
        jobs=[{"hash": "a"}, {"hash": "b"}],
        applications=[{"id": "1", "status": "beworben"}, {"id": "2", "status": "beworben"},
                      {"id": "3", "status": "interview"}],
        source_summary={"active": 0, "total": 9, "active_keys": []},
        search_status={"last_search": None, "days_ago": None, "status": "nie"},
        follow_up_summary={"total": 2, "due": 1},
    )
    nav = daten["navigation"]
    # Drei laufende Bewerbungen, eine faellige Nachfassung: die Zahl ist 1.
    assert nav["applications_badge"] == "1"
    assert nav["titel"]["bewerbungen"] == "1 Nachfassung ist fällig"
    assert nav["titel"]["stellen"] == "2 Stellen warten auf deine Entscheidung"
    assert nav["titel"]["einstellungen"] == "Keine Jobbörse ausgewählt"
    assert nav["titel"]["profil"].startswith("Im Profil fehlt noch:")


def test_g61_seitenleiste_zeigt_den_titel():
    leiste = _lesen(FRONTEND / "components" / "Sidebar.jsx")
    assert "title={badgeTitles[tab.id] || undefined}" in leiste
    app = _lesen(FRONTEND / "App.jsx")
    assert "badgeTitles={chrome.workspace?.navigation?.titel || {}}" in app


# ══ G67 — Rueckweg und Loeschmuster ═════════════════════════════════════

import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, str(_repo() / "src"))


@pytest.fixture
def db():
    import importlib
    tmpdir = tempfile.mkdtemp(prefix="pbp_g1087w6_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    d = _db_mod.Database()
    d.initialize()
    assert str(tmpdir) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test Person"})
    yield d
    d.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_g67_statuswechsel_laesst_sich_zuruecknehmen(db):
    from bewerbungs_assistent.services import status_rueckweg as rw
    aid = db.add_application({"title": "A", "company": "Musterbetrieb GmbH", "status": "beworben"})
    fid = db.add_follow_up(aid, "2026-10-01")
    events_vorher = len(db.get_application(aid)["events"])
    weg = rw.wechseln(db, aid, "abgelehnt", profile_id=db.get_active_profile_id())
    assert weg["vorher"] == "beworben" and weg["archiviert"] is True
    assert fid in weg["geschlossen"]
    assert rw.zuruecknehmen(db, aid, weg, profile_id=db.get_active_profile_id())
    app = db.get_application(aid)
    assert app["status"] == "beworben"
    assert len(app["events"]) == events_vorher
    assert fid in {fu["id"] for fu in db.get_pending_follow_ups()}


def test_g67_zuruecknehmen_raeumt_die_interview_markierung(db):
    from bewerbungs_assistent.services import status_rueckweg as rw
    aid = db.add_application({"title": "A", "company": "Musterbetrieb GmbH", "status": "beworben"})
    weg = rw.wechseln(db, aid, "interview_abgeschlossen", profile_id=db.get_active_profile_id())
    assert weg["angelegt"], "der Wechsel legt eine Nachfrage an"
    rw.zuruecknehmen(db, aid, weg, profile_id=db.get_active_profile_id())
    zeile = db.connect().execute("SELECT has_reached_interview FROM applications WHERE id=?", (aid,)).fetchone()
    assert zeile["has_reached_interview"] == 0
    assert not {fu["id"] for fu in db.get_pending_follow_ups()} & set(weg["angelegt"])


def test_g67_papierkorb_legt_die_notiz_genau_wieder_an(db):
    from bewerbungs_assistent.services import papierkorb
    aid = db.add_application({"title": "A", "company": "Musterbetrieb GmbH", "status": "beworben"})
    db.add_application_note(aid, "Wichtig: Ansprechpartnerin anrufen")
    note = [e for e in db.get_application(aid)["events"] if e["status"] == "notiz"][0]
    zeile = papierkorb.aufheben(db, "notiz", note["id"])
    db.delete_application_event(note["id"], aid)
    assert papierkorb.wiederherstellen(db, "notiz", zeile)
    wieder = [e for e in db.get_application(aid)["events"] if e["status"] == "notiz"][0]
    assert wieder["id"] == note["id"] and wieder["event_date"] == note["event_date"]
    # Nicht ueber eine bestehende Zeile, nicht fuer fremde Arten.
    assert not papierkorb.wiederherstellen(db, "notiz", zeile)
    assert not papierkorb.wiederherstellen(db, "bewerbung", {"id": "x"})
    falsch = dict(zeile, id=zeile["id"] + 1000, status="abgelehnt")
    assert not papierkorb.wiederherstellen(db, "notiz", falsch)


def test_g67_endpunkte_liefern_den_rueckweg(db):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    c = TestClient(dash.app)
    aid = db.add_application({"title": "A", "company": "Musterbetrieb GmbH", "status": "beworben"})
    r = c.put(f"/api/applications/{aid}/status", json={"status": "zurueckgezogen"}).json()
    assert r["rueckweg"]["vorher"] == "beworben"
    assert c.post(f"/api/applications/{aid}/status/rueckgaengig", json={"rueckweg": r["rueckweg"]}).status_code == 200
    assert db.get_application(aid)["status"] == "beworben"
    task = c.post("/api/tasks", json={"titel": "Unterlagen", "application_id": aid}).json()
    tid = task.get("id") or task.get("task_id") or task.get("task", {}).get("id")
    weg = c.delete(f"/api/tasks/{tid}").json()["rueckweg"]
    assert weg["art"] == "aufgabe"
    assert c.post("/api/wiederherstellen", json=weg).status_code == 200


def _jsx_und_js():
    for p in sorted(FRONTEND.rglob("*")):
        if p.suffix in (".jsx", ".js") and "node_modules" not in p.parts:
            yield p


def test_g67_kein_browser_confirm_mehr():
    funde = [p.name for p in _jsx_und_js()
             if re.search(r"(?<![\w.])(?:window\.)?confirm\(", _lesen(p))]
    assert not funde, funde


def test_g67_dialog_hat_kreuz_und_fragt_vor_dem_verwerfen():
    ui = _lesen(FRONTEND / "components" / "ui.jsx")
    modal = ui[ui.index("export function Modal("):ui.index("export function ToastViewport")]
    assert 'aria-label="Schließen"' in modal and "onClick={schliessenVersuchen}" in modal
    assert "onInputCapture={() => setGeaendert(true)}" in modal
    assert "if (schutz && geaendert)" in modal
    assert "data-verwerfen-frage" in modal


def test_g67_kleines_mit_rueckweg():
    app = _lesen(FRONTEND / "pages" / "ApplicationsPage.jsx")
    assert 'geloeschtMitRueckweg(antwort, "Notiz gelöscht."' in app
    assert 'geloeschtMitRueckweg(antwort, "Aufgabe gelöscht."' in app
    tasks = _lesen(FRONTEND / "pages" / "TasksPage.jsx")
    assert 'geloeschtMitRueckweg(antwort, "Aufgabe gelöscht."' in tasks
    assert "Aufgabe wirklich löschen" not in tasks
    kontakte = _lesen(FRONTEND / "pages" / "ContactsPage.jsx")
    assert kontakte.count('geloeschtMitRueckweg(antwort, "Referenz entfernt."') == 2
