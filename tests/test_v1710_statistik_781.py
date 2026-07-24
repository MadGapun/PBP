"""Tests fuer v1.7.10 — #781 (D29): Statistik-Erweiterung.

Zeitliche Kennzahlen, Kanal-Erfolg, Ablehnungs-Kategorien plus der
Notizfeld-Gespraeche-Check. Realfall-Hintergrund: 3 Gespraeche standen nur
im Notizfeld, die Timeline kannte nur 'abgelehnt' — Statistik zaehlte 0
Interviews. Und: die rohe Ablehnungsquote enthielt extern bedingte Faelle
(Stelle gestrichen, Insolvenz), die keine Ablehnung des Bewerbers sind.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1710_781_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _result(raw):
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if hasattr(raw, "structured_content"):
        raw = raw.structured_content
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return raw


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _app_mit_events(db, firma, status, events, **extra):
    """Bewerbung mit definierter Event-Kette anlegen."""
    daten = {"company": firma, "title": f"Rolle {firma}", "status": status,
             "applied_at": events[0][1][:10] if events else ""}
    aid = db.add_application(daten)
    if extra:
        # source/vermittler/endkunde laufen ueber die Update-Whitelist
        db.update_application(aid, extra)
    conn = db.connect()
    conn.execute("DELETE FROM application_events WHERE application_id=?", (aid,))
    for ev_status, datum in events:
        conn.execute(
            "INSERT INTO application_events (application_id, status, event_date, notes) "
            "VALUES (?,?,?,'')", (aid, ev_status, datum))
    if any(s in ("interview", "zweitgespraech") for s, _ in events):
        conn.execute("UPDATE applications SET has_reached_interview=1 "
                     "WHERE id=?", (aid,))
    conn.commit()
    return aid


def test_781_zeitliche_kennzahlen(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.statistik_erweitert import (
        zeitliche_kennzahlen)
    # Schneller Prozess: beworben -> abgelehnt nach 2 Tagen
    _app_mit_events(db, "Schnell GmbH", "abgelehnt", [
        ("beworben", "2026-05-01T09:00:00"),
        ("abgelehnt", "2026-05-03T09:00:00")])
    # Langer Prozess: 90 Tage bis Absage nach Interview
    _app_mit_events(db, "Lang AG", "abgelehnt", [
        ("beworben", "2026-03-01T09:00:00"),
        ("eingangsbestaetigung", "2026-03-08T09:00:00"),
        ("interview", "2026-03-20T09:00:00"),
        ("abgelehnt", "2026-05-30T09:00:00")])

    zk = zeitliche_kennzahlen(db)
    dauer = zk["prozessdauer_nach_ausgang"]["abgelehnt"]
    assert dauer["anzahl"] == 2
    assert dauer["min_tage"] == 2.0
    assert dauer["max_tage"] == 90.0
    assert dauer["median_tage"] == 46.0  # Median trennt die Welten
    assert zk["zeit_bis_erste_reaktion"]["anzahl"] == 2
    assert zk["zeit_bis_interview"]["anzahl"] == 1
    assert zk["zeit_bis_absage"]["vor_interview"]["anzahl"] == 1
    assert zk["zeit_bis_absage"]["nach_interview"]["anzahl"] == 1


def test_781_kanal_auswertung(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.statistik_erweitert import (
        kanal_auswertung)
    _app_mit_events(db, "Portal-Fund", "abgelehnt",
                    [("beworben", "2026-04-01T09:00:00")],
                    source="stepstone")
    _app_mit_events(db, "Vermittelt", "interview",
                    [("beworben", "2026-04-01T09:00:00"),
                     ("interview", "2026-04-10T09:00:00")],
                    vermittler="Vermittler A")
    _app_mit_events(db, "Netz", "angebot",
                    [("beworben", "2026-04-01T09:00:00"),
                     ("interview", "2026-04-05T09:00:00"),
                     ("angebot", "2026-05-01T09:00:00")],
                    source="netzwerk")

    ka = kanal_auswertung(db)
    assert ka["kanaele"]["portal"]["bewerbungen"] == 1
    assert ka["kanaele"]["portal"]["interview_quote"] == 0
    assert ka["kanaele"]["vermittler_recruiter"]["interview_quote"] == 100.0
    assert ka["kanaele"]["netzwerk"]["angebote"] == 1
    assert ka["ranking_nach_interview_quote"][0] in (
        "vermittler_recruiter", "netzwerk")


def test_781_ablehnungs_kategorien_bereinigt(setup_env):
    """Extern bedingte Faelle druecken die bereinigte Quote."""
    db, _ = setup_env
    from bewerbungs_assistent.services.statistik_erweitert import (
        ablehnungs_kategorien)
    # Echte Absage nach Interview
    _app_mit_events(db, "Echte Absage", "abgelehnt", [
        ("beworben", "2026-04-01T09:00:00"),
        ("interview", "2026-04-10T09:00:00"),
        ("abgelehnt", "2026-05-01T09:00:00")])
    # Automatische Ablehnung binnen 48h
    _app_mit_events(db, "ATS-Filter", "abgelehnt", [
        ("beworben", "2026-04-01T09:00:00"),
        ("abgelehnt", "2026-04-02T09:00:00")])
    # Extern: Projekt gestrichen (Freitext-Grund)
    aid = _app_mit_events(db, "Externer Fall", "abgelehnt", [
        ("beworben", "2026-04-01T09:00:00"),
        ("abgelehnt", "2026-06-01T09:00:00")])
    db.connect().execute(
        "UPDATE applications SET rejection_reason="
        "'Geschaeftsfuehrung hat das Vorprojekt gestrichen' WHERE id=?", (aid,))
    # Arbeitgeber-Ausfall (#779) zaehlt ebenfalls extern
    _app_mit_events(db, "Insolvenzfall", "arbeitgeber_ausgefallen", [
        ("beworben", "2026-04-01T09:00:00"),
        ("angebot", "2026-06-01T09:00:00")])
    db.connect().commit()

    ak = ablehnungs_kategorien(db)
    kat = ak["kategorien"]
    assert kat["nach_interview"]["anzahl"] == 1
    assert kat["automatische_ablehnung"]["anzahl"] == 1
    assert kat["extern_bedingt"]["anzahl"] == 2
    assert ak["ablehnungsquote_roh"] > ak["ablehnungsquote_bereinigt"]
    # Freitext bleibt erhalten
    assert "gestrichen" in kat["extern_bedingt"]["faelle"][0]["grund_freitext"] \
        or "gestrichen" in kat["extern_bedingt"]["faelle"][1]["grund_freitext"]


def test_781_statistiken_abrufen_liefert_bloecke(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _app_mit_events(db, "X GmbH", "abgelehnt", [
        ("beworben", "2026-04-01T09:00:00"),
        ("abgelehnt", "2026-04-20T09:00:00")], source="stepstone")
    stats = _result(_call(mcp, "statistiken_abrufen", {}))
    assert "zeitliche_kennzahlen" in stats
    assert "kanal_auswertung" in stats
    assert "ablehnungs_kategorien" in stats
    assert "fussnote" in stats.get("quoten", {}), (
        "Vor-PBP-Untergrenze muss ausgewiesen sein")


def test_781_notizfeld_gespraeche_check(setup_env):
    """Der Realfall: drei Gespraeche in den Notizen, Timeline kennt nur
    'abgelehnt' — die Diagnose muss das melden, aber NICHTS anlegen."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    aid = _app_mit_events(db, "Nur-Notiz GmbH", "abgelehnt", [
        ("beworben", "2026-04-01T09:00:00"),
        ("abgelehnt", "2026-06-20T09:00:00")])
    conn = db.connect()
    conn.execute(
        "UPDATE applications SET notes=? WHERE id=?",
        ("Erstes Gespraech am 15.04.2026 mit dem Fachbereich (45 Min), "
         "zweites Interview am 03.05.2026, Telefonat mit HR am 20.05.2026.",
         aid))
    conn.commit()

    diag = _result(_call(mcp, "pbp_diagnose", {}))
    treffer = [w for w in diag.get("warnungen", [])
               if "Notizfeld" in str(w.get("problem", ""))]
    assert treffer, "Gespraeche nur im Notizfeld muessen gemeldet werden"
    assert treffer[0]["bewerbungen"][0]["firma"] == "Nur-Notiz GmbH"

    # Kein Auto-Anlegen — auch nicht mit auto_fix
    _result(_call(mcp, "pbp_diagnose", {"auto_fix": True}))
    n_events = conn.execute(
        "SELECT COUNT(*) AS n FROM application_events WHERE application_id=?",
        (aid,)).fetchone()["n"]
    assert n_events == 2, "auto_fix darf KEINE Gespraechs-Events erfinden"


def test_781_bericht_rendert_neue_bloecke(setup_env, tmp_path):
    db, _ = setup_env
    from bewerbungs_assistent.services import statistik_erweitert as se
    from bewerbungs_assistent.export_report import generate_application_report
    _app_mit_events(db, "Bericht GmbH", "abgelehnt", [
        ("beworben", "2026-04-01T09:00:00"),
        ("interview", "2026-04-10T09:00:00"),
        ("abgelehnt", "2026-05-01T09:00:00")], source="stepstone")
    report_data = db.get_report_data()
    report_data["prozess_kennzahlen"] = se.zeitliche_kennzahlen(db)
    report_data["kanal_auswertung"] = se.kanal_auswertung(db)
    report_data["ablehnungs_kategorien"] = se.ablehnungs_kategorien(db)
    report_data["aufwand"] = db.get_aufwand_summary()
    out = tmp_path / "bericht.pdf"
    generate_application_report(report_data, db.get_profile(), out)
    assert out.exists() and out.stat().st_size > 1000
