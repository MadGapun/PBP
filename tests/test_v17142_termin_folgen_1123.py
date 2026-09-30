"""#1123 — Termin verschoben, Aufgaben bleiben stehen; Nachfassung trotz Kontakt offen.

Der Fall (29.09.2026): Ein Interview wurde vom 30.09. auf den 07.10.
verschoben. Der Termin war richtig, die Vorbereitungs-Aufgabe stand als
„überfällig“, und eine Routine-Nachfassung blieb offen, obwohl die
Bewerbung längst im Interview war.

Nutzerentscheidung: automatisch hinfällig — nach JEDEM gemeldeten Kontakt
mit dem Arbeitgeber, nicht nur beim Interview.

Alle Daten sind relativ zu heute (L28: Tests mit festen Daten verfallen).
"""
import asyncio
import importlib
import logging
import os
import shutil
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _tag(tage: int) -> str:
    return (date.today() + timedelta(days=tage)).isoformat()


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1123_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    d = _db_mod.Database()
    d.initialize()
    assert str(tmpdir) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test"})
    yield d
    d.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _bewerbung(db, status="beworben"):
    return db.add_application({
        "title": "PLM Dokumentenmanager (m/w/d)", "company": "Musterfirma",
        "status": status, "applied_at": _tag(-20)})


def _termin(db, app_id, tage=10, uhr="11:00:00", status="geplant"):
    return db.add_meeting({
        "application_id": app_id, "title": "Interview Musterfirma",
        "meeting_date": f"{_tag(tage)}T{uhr}", "meeting_type": "interview",
        "status": status})


def _vorbereitung(db, app_id, tage_bis_faellig=8, titel="Interview vorbereiten", **plus):
    return db.add_task({
        "application_id": app_id, "typ": "vorbereitung", "titel": titel,
        "faellig_am": _tag(tage_bis_faellig), **plus})


def _nachfassung(db, app_id, typ="nachfass", angelegt=None):
    fid = db.add_follow_up(app_id, _tag(1), typ, template="Nachfassen")
    if angelegt:
        db.connect().execute("UPDATE follow_ups SET created_at=? WHERE id=?",
                             (angelegt, fid))
        db.connect().commit()
    return fid


def _offene_nachfassungen(db, app_id):
    return [f["id"] for f in db.get_pending_follow_ups()
            if f["application_id"] == app_id]


def _aufgabe(db, task_id):
    return db.get_task(task_id)


# ══ Vorbereitung zieht mit ═════════════════════════════════════════════

def test_1123_verschieben_zieht_die_einzige_vorbereitung_mit(db):
    """Der Praxisfall: Termin +7 Tage, Vorbereitung 2 Tage davor."""
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    mid = _termin(db, app, tage=10)
    tid = _vorbereitung(db, app, tage_bis_faellig=8,
                        beschreibung=f"Termin: {_tag(10)}")

    erg = termin_folgen.aendern(
        db, mid, {"meeting_date": f"{_tag(17)}T11:00:00", "status": "bestaetigt"})

    assert erg["geaendert"] is True
    angepasst = erg["vorbereitung_angepasst"]
    assert angepasst["todo_id"] == tid
    assert angepasst["faellig_alt"] == _tag(8)
    assert angepasst["faellig_neu"] == _tag(15)
    todo = _aufgabe(db, tid)
    assert todo["faellig_am"][:10] == _tag(15)
    assert "Termin verschoben von" in todo["beschreibung"]
    assert todo["beschreibung"].startswith(f"Termin: {_tag(10)}")   # nichts überschrieben
    assert todo["titel"] == "Interview vorbereiten"                    # Titel unangetastet


def test_1123_mehrere_vorbereitungen_werden_nicht_geraten(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    mid = _termin(db, app, tage=10)
    t1 = _vorbereitung(db, app, 8, titel="Vorbereitung A")
    t2 = _vorbereitung(db, app, 9, titel="Vorbereitung B")

    erg = termin_folgen.aendern(db, mid, {"meeting_date": f"{_tag(17)}T11:00:00"})

    assert "vorbereitung_angepasst" not in erg
    ids = {p["todo_id"] for p in erg["vorbereitung_pruefen"]}
    assert ids == {t1, t2}
    assert _aufgabe(db, t1)["faellig_am"][:10] == _tag(8)      # unverändert
    assert _aufgabe(db, t2)["faellig_am"][:10] == _tag(9)


def test_1123_ohne_vorbereitung_kommt_nichts_dazu(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    mid = _termin(db, app, tage=10)
    erg = termin_folgen.aendern(db, mid, {"meeting_date": f"{_tag(17)}T11:00:00"})
    assert erg == {"geaendert": True}


def test_1123_nur_die_uhrzeit_aendert_die_faelligkeit_nicht(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    mid = _termin(db, app, tage=10, uhr="11:00:00")
    tid = _vorbereitung(db, app, 8)
    erg = termin_folgen.aendern(db, mid, {"meeting_date": f"{_tag(10)}T15:30:00"})
    assert "vorbereitung_angepasst" not in erg and "vorbereitung_pruefen" not in erg
    assert _aufgabe(db, tid)["faellig_am"][:10] == _tag(8)


def test_1123_frueher_gelegter_termin_erzeugt_keine_faelligkeit_in_der_vergangenheit(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    mid = _termin(db, app, tage=10)
    # Termin 8 Tage früher: 3 - 8 = -5 läge in der Vergangenheit.
    tid = _vorbereitung(db, app, tage_bis_faellig=3)
    termin_folgen.aendern(db, mid, {"meeting_date": f"{_tag(2)}T11:00:00"})
    faellig = _aufgabe(db, tid)["faellig_am"][:10]
    assert _tag(0) <= faellig <= _tag(2), faellig


def test_1123_die_vorbereitung_ist_nie_nach_dem_neuen_termin_faellig(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    mid = _termin(db, app, tage=10)
    # Ungewöhnlich, aber möglich: eine Aufgabe, die erst nach dem Termin
    # fällig war. Mit demselben Abstand läge sie nach dem neuen Termin.
    tid = _vorbereitung(db, app, tage_bis_faellig=11)
    termin_folgen.aendern(db, mid, {"meeting_date": f"{_tag(1)}T11:00:00"})
    assert _aufgabe(db, tid)["faellig_am"][:10] == _tag(1)


def test_1123_der_titel_mit_altem_datum_wird_gemeldet(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    alt = date.today() + timedelta(days=10)
    mid = _termin(db, app, tage=10)
    _vorbereitung(db, app, 8, titel=f"Interview vorbereiten am {alt.strftime('%d.%m.')}, 11:00 Uhr")
    erg = termin_folgen.aendern(db, mid, {"meeting_date": f"{_tag(17)}T11:00:00"})
    assert erg["vorbereitung_angepasst"]["titel_nennt_altes_datum"] is True


def test_1123_die_faelligkeit_liegt_danach_nicht_mehr_im_rueckstand(db):
    """Das Akzeptanzkriterium: nach dem Verschieben nicht „überfällig“."""
    from bewerbungs_assistent.services import aufgaben_sicht, termin_folgen
    app = _bewerbung(db)
    mid = _termin(db, app, tage=3)
    _vorbereitung(db, app, tage_bis_faellig=-1)      # gestern fällig, Termin noch 3 Tage
    termin_folgen.aendern(db, mid, {"meeting_date": f"{_tag(10)}T11:00:00"})
    sicht = aufgaben_sicht.uebersicht(db)
    assert sicht["ueberfaellig_anzahl"] == 0


def test_1123_absage_schlaegt_hinfaellig_vor_und_aendert_nichts(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    mid = _termin(db, app, tage=10)
    tid = _vorbereitung(db, app, 8)
    erg = termin_folgen.aendern(db, mid, {"status": "abgesagt"})
    assert erg["vorbereitung_pruefen"][0]["todo_id"] == tid
    assert erg["vorbereitung_pruefen"][0]["hinfaellig_mit"] == f"todo_hinfaellig('{tid}')"
    assert _aufgabe(db, tid)["status"] == "offen"


def test_1123_loeschen_schlaegt_hinfaellig_vor(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    mid = _termin(db, app, tage=10)
    tid = _vorbereitung(db, app, 8)
    erg = termin_folgen.loeschen(db, mid)
    assert erg["geloescht"] is True
    assert erg["vorbereitung_pruefen"][0]["todo_id"] == tid
    assert _aufgabe(db, tid)["status"] == "offen"


def test_1123_eine_fremde_bewerbung_bleibt_unberuehrt(db):
    from bewerbungs_assistent.services import termin_folgen
    a1, a2 = _bewerbung(db), _bewerbung(db)
    mid = _termin(db, a1, tage=10)
    fremd = _vorbereitung(db, a2, 8)
    termin_folgen.aendern(db, mid, {"meeting_date": f"{_tag(17)}T11:00:00"})
    assert _aufgabe(db, fremd)["faellig_am"][:10] == _tag(8)


# ══ Nachfassung erledigt sich durch Kontakt ═════════════════════════════

def test_1123_interview_schliesst_die_routine_nachfrage(db):
    """Der Praxisfall: Erinnerung offen, Bewerbung wechselt ins Interview."""
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    assert _offene_nachfassungen(db, app) == [fid]

    db.update_application_status(app, "interview")

    assert _offene_nachfassungen(db, app) == []
    zeile = db.get_follow_up(fid)
    assert zeile["status"] == "hinfaellig" and zeile["completed_at"]      # nicht gelöscht
    notizen = [e["notes"] for e in db.get_application(app)["events"]
               if e.get("status") == "notiz"]
    assert any("Nachfrage erledigt" in (n or "") for n in notizen)         # im Verlauf


@pytest.mark.parametrize("status", ["eingangsbestaetigung", "zweitgespraech", "angebot"])
def test_1123_jede_antwort_des_arbeitgebers_schliesst(db, status):
    app = _bewerbung(db)
    _nachfassung(db, app)
    db.update_application_status(app, status)
    assert _offene_nachfassungen(db, app) == []


def test_1123_beworben_schliesst_nichts(db):
    """Der eigene Versand ist kein Kontakt."""
    app = _bewerbung(db, status="in_vorbereitung")
    fid = _nachfassung(db, app)
    db.update_application_status(app, "beworben")
    assert _offene_nachfassungen(db, app) == [fid]


def test_1123_ein_termin_schliesst(db):
    app = _bewerbung(db)
    _nachfassung(db, app)
    _termin(db, app, tage=5)
    assert _offene_nachfassungen(db, app) == []


def test_1123_ein_abgesagter_termin_ist_kein_kontakt(db):
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    _termin(db, app, tage=5, status="abgesagt")
    assert _offene_nachfassungen(db, app) == [fid]


def test_1123_eine_gesprächsnotiz_schliesst_und_meldet_es(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import bewerbungen, mit_katalog
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    mcp = FastMCP("test")
    bewerbungen.register(mit_katalog(mcp, db), db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("bewerbung_notiz")
        r = await tool.run({"bewerbung_id": app, "notiz": "Telefonat mit der Personalabteilung"})
        return getattr(r, "structured_content", r)
    erg = asyncio.run(_run())
    erg = erg.get("result", erg) if set(erg) == {"result"} else erg
    assert erg["nachfassung_erledigt"][0]["id"] == fid
    assert _offene_nachfassungen(db, app) == []


def test_1123_eine_zugeordnete_mail_schliesst(db):
    app = _bewerbung(db)
    _nachfassung(db, app)
    db.add_email({"application_id": app, "subject": "Ihre Bewerbung",
                  "sender": "personal@example.com",
                  "sent_date": datetime.now().isoformat()})
    assert _offene_nachfassungen(db, app) == []


def test_1123_eine_alte_mail_beantwortet_keine_spaetere_nachfrage(db):
    """Gemessen am Datum der Mail, nicht am Import."""
    app = _bewerbung(db)
    fid = _nachfassung(db, app)
    db.add_email({"application_id": app, "subject": "Alt", "sender": "x@example.com",
                  "sent_date": "2020-01-15T10:00:00"})
    assert _offene_nachfassungen(db, app) == [fid]


def test_1123_eine_erinnerung_nach_dem_kontakt_bleibt(db):
    """Wer nach dem Gespräch bewusst „in zwei Wochen nachfragen“ plant, will
    genau diese Erinnerung behalten."""
    from bewerbungs_assistent.services import nachfass_abgleich
    app = _bewerbung(db)
    spaeter = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    fid = _nachfassung(db, app, angelegt=spaeter)
    assert nachfass_abgleich.kontakt_gemeldet(db, app, "Test") == []
    assert _offene_nachfassungen(db, app) == [fid]


def test_1123_nur_nachfragen_schliessen_keine_danke_mail(db):
    app = _bewerbung(db)
    danke = _nachfassung(db, app, typ="danke")
    nach = _nachfassung(db, app)
    db.update_application_status(app, "interview")
    assert _offene_nachfassungen(db, app) == [danke]
    assert nach not in _offene_nachfassungen(db, app)


def _stale_nachfrage(db):
    """Der Bestand vor #1123: Status kam an den Hooks vorbei (Import)."""
    app = _bewerbung(db)
    db.connect().execute("UPDATE applications SET status='interview' WHERE id=?", (app,))
    db.connect().commit()
    return app, db.add_follow_up(app, _tag(-3), "nachfass", template="Nachfassen")


def test_1123_das_lesen_der_aufgabenliste_veraendert_nichts(db):
    """#945: „eine Liste abzurufen darf nichts verändern“ — die frühere
    Entscheidung gilt weiter. Geschlossen wird über Ereignisse und die
    Automatik, nie beim Lesen."""
    from bewerbungs_assistent.services import aufgaben_sicht
    app, fid = _stale_nachfrage(db)
    sicht = aufgaben_sicht.uebersicht(db)
    assert fid in _offene_nachfassungen(db, app)                      # unverändert
    zeile = next(e for g in sicht["gruppen"].values() for e in g
                 if e["herkunft"] == "nachfass")
    assert zeile["ueberholt"] is True                                 # weiter markiert


def test_1123_die_automatik_schliesst_den_stehengebliebenen_bestand(db):
    """Der Aufräumer des Dashboards ist dasselbe Netz wie der Start."""
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    app, fid = _stale_nachfrage(db)
    erg = dash._run_followup_ueberholt(datetime.now().isoformat())
    assert erg["hinfaellig"] == 1
    assert _offene_nachfassungen(db, app) == []
    from bewerbungs_assistent.services import aufgaben_sicht
    assert aufgaben_sicht.uebersicht(db)["ueberfaellig_anzahl"] == 0


def test_1123_der_aufraeumer_schliesst_nur_nachfragen(db):
    """Die alte Fassung schloss auch eine Interview-Erinnerung, sobald der
    Stand „Interview“ hieß."""
    from bewerbungs_assistent.services import nachfass_abgleich
    app, fid = _stale_nachfrage(db)
    erinnerung = db.add_follow_up(app, _tag(-1), "interview_erinnerung", template="Termin")
    geschlossen = nachfass_abgleich.ueberholte_schliessen(db)
    assert [g["id"] for g in geschlossen] == [fid]
    assert _offene_nachfassungen(db, app) == [erinnerung]


def test_1123_der_aufraeumer_laesst_eine_laufende_bewerbung_in_ruhe(db):
    """Das Urteil bleibt `ist_ueberholt`: bei „beworben“ ist nichts überholt."""
    from bewerbungs_assistent.services import nachfass_abgleich
    app = _bewerbung(db)          # Stand: beworben
    fid = db.add_follow_up(app, _tag(-3), "nachfass", template="Nachfassen")
    assert nachfass_abgleich.ueberholte_schliessen(db) == []
    assert _offene_nachfassungen(db, app) == [fid]


def test_1123_die_automatik_ruft_die_eine_funktion():
    """Eine Frage, eine Funktion (L1): kein zweites Urteil im Dashboard."""
    quelle = (ROOT / "src" / "bewerbungs_assistent" / "dashboard.py").read_text(encoding="utf-8")
    start = quelle.index("def _run_followup_ueberholt")
    block = quelle[start:quelle.index("def _run_auto_followup_reconciler")]
    assert "nachfass_abgleich.ueberholte_schliessen(" in block
    assert "ist_ueberholt(" not in block


def test_1123_der_start_heilt_den_bestand(db):
    app = _bewerbung(db)
    db.connect().execute("UPDATE applications SET status='zweitgespraech' WHERE id=?", (app,))
    db.connect().commit()
    db.add_follow_up(app, _tag(-3), "nachfass", template="Nachfassen")
    db.initialize()
    assert _offene_nachfassungen(db, app) == []


def test_1123_die_erinnerung_nach_dem_abgeschlossenen_interview_bleibt(db):
    """Der bestehende Weg (#494): alte schließen, EINE neue anlegen."""
    app = _bewerbung(db)
    _nachfassung(db, app)
    db.update_application_status(app, "interview_abgeschlossen")
    offen = _offene_nachfassungen(db, app)
    assert len(offen) == 1
    assert "Nachfrage nach dem Gesprächsergebnis" in db.get_follow_up(offen[0])["template"]


# ══ Beide Wege dieselbe Regel ═══════════════════════════════════════════

def test_1123_das_werkzeug_meldet_die_folgen(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import bewerbungen, mit_katalog
    app = _bewerbung(db)
    mid = _termin(db, app, tage=10)
    tid = _vorbereitung(db, app, 8)
    mcp = FastMCP("test")
    bewerbungen.register(mit_katalog(mcp, db), db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("meeting_bearbeiten")
        r = await tool.run({"meeting_id": mid, "datum": f"{_tag(17)}T11:00:00",
                            "status": "bestaetigt"})
        return getattr(r, "structured_content", r)
    erg = asyncio.run(_run())
    erg = erg.get("result", erg) if set(erg) == {"result"} else erg
    assert erg["status"] == "aktualisiert"
    assert erg["vorbereitung_angepasst"]["todo_id"] == tid
    assert _aufgabe(db, tid)["faellig_am"][:10] == _tag(15)


def test_1123_das_dashboard_zieht_dieselbe_regel(db):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    app = _bewerbung(db)
    mid = _termin(db, app, tage=10)
    tid = _vorbereitung(db, app, 8)
    r = TestClient(dash.app).put(
        f"/api/meetings/{mid}", json={"meeting_date": f"{_tag(17)}T11:00:00"})
    assert r.status_code == 200, r.text
    assert r.json()["vorbereitung_angepasst"]["todo_id"] == tid
    assert _aufgabe(db, tid)["faellig_am"][:10] == _tag(15)
    # Löschen über den Dashboard-Weg schlägt hinfällig vor.
    r = TestClient(dash.app).delete(f"/api/meetings/{mid}")
    assert r.status_code == 200 and r.json()["vorbereitung_pruefen"][0]["todo_id"] == tid


# ══ pbp_diagnose: Befund, kein auto_fix ═══════════════════════════════════

def _kurz(tage: int) -> str:
    return (date.today() + timedelta(days=tage)).strftime("%d.%m.")


def test_1123_diagnose_meldet_ein_altes_datum_im_titel(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    _termin(db, app, tage=17)
    tid = _vorbereitung(db, app, 15, titel=f"Interview vorbereiten am {_kurz(10)}, 11:00 Uhr")
    befunde = termin_folgen.abweichende_vorbereitungen(db)
    assert [b["todo_id"] for b in befunde] == [tid]
    assert befunde[0]["genannt"] == [_kurz(10)]
    assert _aufgabe(db, tid)["titel"].startswith("Interview vorbereiten am")   # schreibt nichts


def test_1123_diagnose_schweigt_bei_passendem_datum(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    _termin(db, app, tage=10)
    _vorbereitung(db, app, 8, titel=f"Interview vorbereiten am {_kurz(10)}")
    assert termin_folgen.abweichende_vorbereitungen(db) == []


def test_1123_diagnose_liest_nur_titel_und_die_termin_zeile(db):
    """Ein Bewerbungsdatum oder ein Datum aus einer Mail in der Beschreibung
    ist kein Fehlalarm wert."""
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    _termin(db, app, tage=10)
    _vorbereitung(db, app, 8, titel="Interview vorbereiten",
                  beschreibung=f"Beworben am {_kurz(-20)}.\nMail vom {_kurz(-3)}.\n"
                               f"Termin verschoben von {_kurz(4)} auf {_kurz(10)}.")
    assert termin_folgen.abweichende_vorbereitungen(db) == []


def test_1123_diagnose_meldet_die_alte_termin_zeile(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    _termin(db, app, tage=10)
    tid = _vorbereitung(db, app, 8, titel="Interview vorbereiten",
                        beschreibung=f"Termin: {_kurz(4)}")
    assert [b["todo_id"] for b in termin_folgen.abweichende_vorbereitungen(db)] == [tid]


def test_1123_diagnose_ohne_kommenden_termin_gibt_es_nichts_zu_vergleichen(db):
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    _vorbereitung(db, app, 8, titel=f"Interview vorbereiten am {_kurz(4)}")
    assert termin_folgen.abweichende_vorbereitungen(db) == []


def test_1123_pbp_diagnose_nennt_den_befund(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import analyse, mit_katalog
    app = _bewerbung(db)
    _termin(db, app, tage=17)
    tid = _vorbereitung(db, app, 15, titel=f"Interview vorbereiten am {_kurz(10)}")
    mcp = FastMCP("test")
    analyse.register(mit_katalog(mcp, db), db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("pbp_diagnose")
        r = await tool.run({})
        return getattr(r, "structured_content", r)
    erg = asyncio.run(_run())
    erg = erg.get("result", erg) if set(erg) == {"result"} else erg
    treffer = [w for w in erg.get("warnungen", []) if w.get("bereich") == "Vorbereitung"]
    assert treffer and tid in treffer[0]["loesung"]
    assert _aufgabe(db, tid)["titel"].startswith("Interview vorbereiten am")


def test_1123_diagnose_ein_abgesagter_termin_macht_das_datum_nicht_gueltig(db):
    """Der Titel nennt das Datum des ABGESAGTEN Termins; der neue steht
    später. Sonst bliebe das alte Datum gültig, obwohl es abgesagt ist."""
    from bewerbungs_assistent.services import termin_folgen
    app = _bewerbung(db)
    _termin(db, app, tage=5, status="abgesagt")
    _termin(db, app, tage=12)
    tid = _vorbereitung(db, app, 4, titel=f"Interview vorbereiten am {_kurz(5)}")
    assert [b["todo_id"] for b in termin_folgen.abweichende_vorbereitungen(db)] == [tid]
