"""Tests fuer v1.7.11 — #804 (D30): Termin-Dubletten.

Belegter Fall 06.08.2026: zwei Eintraege fuer denselben Slot einer
Bewerbung. Sie ergaenzten sich sogar — einer trug den Teams-Link, der
andere Dauer und Gespraechskontext. Keiner allein war vollstaendig, und
jede Auswertung zaehlte den Termin doppelt.

Bei Stellen (#670) und Nachfassungen (#665) gibt es die Pruefung laengst;
bei Terminen fehlte sie, weil die urspruenglich nur von Hand entstanden.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1711_804_")
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


@pytest.fixture
def bewerbung(setup_env):
    db, _ = setup_env
    aid = db.add_application({
        "company": "Firma S", "title": "PLM Deployment Lead",
        "status": "interview", "applied_at": "2026-07-01"})
    return db, aid


def test_804_zweiter_termin_wird_gemeldet_nicht_angelegt(bewerbung):
    db, aid = bewerbung
    from bewerbungs_assistent.server import mcp
    erst = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:00:00",
        "typ": "interview", "platform": "teams"}))
    assert erst["status"] == "angelegt"

    zweit = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:00",
        "typ": "zweitgespraech", "platform": "MS Teams"}))
    assert zweit["status"] == "dublette_moeglich", zweit
    assert zweit["nicht_angelegt"] is True
    assert zweit["bestehender_termin"]["id"] == erst["meeting_id"]
    assert "optionen" in zweit

    n = db.connect().execute(
        "SELECT COUNT(*) FROM application_meetings WHERE application_id=?",
        (aid,)).fetchone()[0]
    assert n == 1, "Es darf kein zweiter Termin entstanden sein"


def test_804_zusammenfuehren_fuellt_nur_leere_felder(bewerbung):
    """Der belegte Fall: einer hat den Link, der andere den Kontext."""
    db, aid = bewerbung
    from bewerbungs_assistent.server import mcp
    erst = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:00:00",
        "typ": "interview", "platform": "teams",
        "titel": "16 Uhr Zweites Gespraech"}))

    zweit = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:00",
        "typ": "zweitgespraech", "platform": "MS Teams",
        "titel": "Zweites Online-Interview",
        "notizen": "Besprechungs-ID und Teilnehmer aus dem Erstgespraech",
        "dauer_minuten": 60,
        "wenn_dublette": "zusammenfuehren"}))
    assert zweit["status"] == "zusammengefuehrt", zweit
    assert zweit["meeting_id"] == erst["meeting_id"]
    # Leere Felder wurden gefuellt ...
    assert "notes" in zweit["ergaenzte_felder"]
    assert "duration_minutes" in zweit["ergaenzte_felder"]
    # ... gefuellte NICHT ueberschrieben
    assert "title" in zweit["unveraendert"]

    row = db.connect().execute(
        "SELECT title, notes, duration_minutes, platform "
        "FROM application_meetings WHERE id=?",
        (erst["meeting_id"],)).fetchone()
    assert row["title"] == "16 Uhr Zweites Gespraech", "Titel blieb erhalten"
    assert "Besprechungs-ID" in (row["notes"] or "")
    assert row["duration_minutes"] == 60
    assert row["platform"] == "teams", "gefuelltes Feld bleibt"

    n = db.connect().execute(
        "SELECT COUNT(*) FROM application_meetings WHERE application_id=?",
        (aid,)).fetchone()[0]
    assert n == 1


def test_804_trotzdem_neu_legt_an_und_meldet(bewerbung):
    db, aid = bewerbung
    from bewerbungs_assistent.server import mcp
    _call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:00:00", "typ": "interview"})
    zweit = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:10:00",
        "typ": "interview", "wenn_dublette": "trotzdem_neu"}))
    assert zweit["status"] == "angelegt"
    assert "dublette_uebersteuert" in zweit
    n = db.connect().execute(
        "SELECT COUNT(*) FROM application_meetings WHERE application_id=?",
        (aid,)).fetchone()[0]
    assert n == 2


def test_804_echte_doppeltermine_am_selben_tag_sind_keine_dublette(bewerbung):
    """Erst- und Zweitgespraech am selben Tag muessen beide durchgehen."""
    db, aid = bewerbung
    from bewerbungs_assistent.server import mcp
    a = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T10:00:00", "typ": "interview"}))
    b = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:00:00",
        "typ": "zweitgespraech"}))
    assert a["status"] == "angelegt"
    assert b["status"] == "angelegt", b


def test_804_abgesagter_termin_blockiert_nicht(bewerbung):
    """Wer umplant, soll den neuen Termin ohne Umweg anlegen koennen."""
    db, aid = bewerbung
    from bewerbungs_assistent.server import mcp
    erst = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:00:00",
        "typ": "interview", "status": "abgesagt"}))
    zweit = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:00:00", "typ": "interview"}))
    assert zweit["status"] == "angelegt", zweit


def test_804_andere_bewerbung_ist_keine_dublette(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    a1 = db.add_application({"company": "Firma A", "title": "X",
                             "status": "interview"})
    a2 = db.add_application({"company": "Firma B", "title": "Y",
                             "status": "interview"})
    _call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": a1, "datum": "2026-08-06T16:00:00", "typ": "interview"})
    zweit = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": a2, "datum": "2026-08-06T16:00:00", "typ": "interview"}))
    assert zweit["status"] == "angelegt"


def test_804_bestands_report_und_merge(bewerbung):
    """Bereits entstandene Dubletten aufraeumen — ohne sie im Kalender
    von Hand suchen zu muessen."""
    db, aid = bewerbung
    from bewerbungs_assistent.server import mcp
    reich = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:00:00",
        "typ": "zweitgespraech", "titel": "Zweites Online-Interview",
        "notizen": "Kontext aus dem Erstgespraech", "dauer_minuten": 60}))
    arm = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:00:00",
        "typ": "interview", "platform": "teams",
        "wenn_dublette": "trotzdem_neu"}))

    report = _result(_call(mcp, "termin_dubletten_bereinigen", {}))
    assert report["status"] == "report"
    assert report["anzahl"] == 1, report
    paar = report["dubletten"][0]
    # Der inhaltsreichere Termin wird als Master vorgeschlagen
    assert paar["master_id"] == reich["meeting_id"]
    assert paar["duplikat_id"] == arm["meeting_id"]

    vorschau = _result(_call(mcp, "termin_dubletten_bereinigen", {
        "master_id": str(paar["master_id"]),
        "duplikat_id": str(paar["duplikat_id"])}))
    assert vorschau["status"] == "vorschau"
    assert "platform" in vorschau["wuerde_uebernehmen"]
    assert db.connect().execute(
        "SELECT COUNT(*) FROM application_meetings").fetchone()[0] == 2, \
        "dry_run darf nichts loeschen"

    res = _result(_call(mcp, "termin_dubletten_bereinigen", {
        "master_id": str(paar["master_id"]),
        "duplikat_id": str(paar["duplikat_id"]), "dry_run": False}))
    assert res["status"] == "zusammengefuehrt"
    assert res["duplikat_geloescht"] is True
    assert "platform" in res["ergaenzte_felder"]

    zeile = db.connect().execute(
        "SELECT title, platform, notes, duration_minutes "
        "FROM application_meetings").fetchall()
    assert len(zeile) == 1, "Aus zwei Terminen wurde einer"
    assert zeile[0]["platform"] == "teams", "Link/Plattform uebernommen"
    assert "Kontext" in (zeile[0]["notes"] or ""), "Kontext erhalten"

    # Idempotent: der Report findet nichts mehr
    nachher = _result(_call(mcp, "termin_dubletten_bereinigen", {}))
    assert nachher["anzahl"] == 0


def test_804_merge_ueber_bewerbungsgrenze_wird_abgelehnt(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    a1 = db.add_application({"company": "A", "title": "X", "status": "interview"})
    a2 = db.add_application({"company": "B", "title": "Y", "status": "interview"})
    m1 = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": a1, "datum": "2026-08-06T16:00:00", "typ": "interview"}))
    m2 = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": a2, "datum": "2026-08-06T16:00:00", "typ": "interview"}))
    res = _result(_call(mcp, "termin_dubletten_bereinigen", {
        "master_id": str(m1["meeting_id"]),
        "duplikat_id": str(m2["meeting_id"]), "dry_run": False}))
    assert "fehler" in res
