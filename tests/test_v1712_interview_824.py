"""Tests fuer v1.7.12 — #824 (D31): Interview-Nachbereitung vollwertig.

Belegte Befunde 11.08.2026: (1) Die 1:1-Bindung sass in der Upsert-Logik
— die Nachbereitung des Zweitgespraechs ueberschrieb die des ersten.
(2) Teilnehmer standen nur im Fliesstext; bei einem Verfahren mit zwei
Interviews war einzig der Vermittler als Kontakt erfasst. (3) Reflexionen
waren Write-Only — keinerlei Auswertung quer darueber.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1712_824_")
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
        "company": "Halbleiterwerk Nord GmbH", "title": "PLM Lead",
        "status": "interview", "applied_at": "2026-07-01"})
    return db, aid


def test_824_zweite_reflexion_ueberschreibt_nicht(bewerbung):
    """DER Kern-Befund: bei zweistufigen Verfahren ging Runde 1 verloren."""
    db, aid = bewerbung
    from bewerbungs_assistent.server import mcp
    r1 = _result(_call(mcp, "interview_reflexion_speichern", {
        "bewerbung_id": aid, "was_lief_gut": "Fachlicher Teil sass.",
        "gefuehl": 4}))
    assert r1["status"] == "gespeichert"
    r2 = _result(_call(mcp, "interview_reflexion_speichern", {
        "bewerbung_id": aid,
        "was_lief_gut": "Endrunde: Chemie mit dem Team stimmte.",
        "gefuehl": 5}))
    assert r2["status"] == "gespeichert"
    assert r2["reflexion_id"] != r1["reflexion_id"], \
        "zweiter Aufruf muss eine NEUE Reflexion anlegen"
    alle = _result(_call(mcp, "interview_reflexion_lesen",
                         {"bewerbung_id": aid}))
    assert alle["anzahl"] == 2
    texte = [r["was_lief_gut"] for r in alle["reflexionen"]]
    assert "Fachlicher Teil sass." in texte, "Runde 1 bleibt erhalten"


def test_824_nachbearbeiten_per_reflexion_id(bewerbung):
    db, aid = bewerbung
    from bewerbungs_assistent.server import mcp
    r1 = _result(_call(mcp, "interview_reflexion_speichern", {
        "bewerbung_id": aid, "was_lief_gut": "Erster Eindruck."}))
    upd = _result(_call(mcp, "interview_reflexion_speichern", {
        "bewerbung_id": aid, "reflexion_id": str(r1["reflexion_id"]),
        "next_steps": "Arbeitsprobe bis Freitag."}))
    assert upd["status"] == "aktualisiert"
    alle = _result(_call(mcp, "interview_reflexion_lesen",
                         {"bewerbung_id": aid}))
    assert alle["anzahl"] == 1, "Nachbearbeitung darf keine neue anlegen"
    r = alle["reflexion"]
    assert r["was_lief_gut"] == "Erster Eindruck.", "Feld bleibt"
    assert r["next_steps"] == "Arbeitsprobe bis Freitag."


def test_824_meeting_bezug(bewerbung):
    db, aid = bewerbung
    from bewerbungs_assistent.server import mcp
    m = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:00:00",
        "typ": "interview"}))
    r = _result(_call(mcp, "interview_reflexion_speichern", {
        "bewerbung_id": aid, "was_lief_gut": "x",
        "meeting_id": str(m["meeting_id"])}))
    alle = db.get_interview_reflections(aid)
    assert alle[0]["meeting_id"] == str(m["meeting_id"])


def test_824_loeschen(bewerbung):
    db, aid = bewerbung
    from bewerbungs_assistent.server import mcp
    r = _result(_call(mcp, "interview_reflexion_speichern", {
        "bewerbung_id": aid, "was_lief_gut": "versehentlich"}))
    res = _result(_call(mcp, "interview_reflexion_loeschen", {
        "reflexion_id": str(r["reflexion_id"])}))
    assert res["status"] == "geloescht"
    assert db.get_interview_reflections(aid) == []


def test_824_teilnehmer_am_termin_via_contact_links(bewerbung):
    """Die n:m-Struktur existierte seit #563 — Teilnehmer mit Rolle."""
    db, aid = bewerbung
    from bewerbungs_assistent.server import mcp
    m = _result(_call(mcp, "meeting_hinzufuegen", {
        "bewerbung_id": aid, "datum": "2026-08-06T16:00:00",
        "typ": "interview"}))
    k = _result(_call(mcp, "kontakt_anlegen", {
        "name": "Fachbereichsleitung, Name unbekannt",
        "firma": "Halbleiterwerk Nord GmbH"}))
    kid = k.get("kontakt_id") or k.get("id")
    res = _result(_call(mcp, "kontakt_verknuepfen", {
        "kontakt_id": str(kid), "ziel_typ": "meeting",
        "ziel_id": str(m["meeting_id"]),
        "rolle": "fachlicher Gegenpart"}))
    assert "fehler" not in res, res
    links = db.connect().execute(
        "SELECT * FROM contact_links WHERE target_kind='meeting' "
        "AND target_id=?", (str(m["meeting_id"]),)).fetchall()
    assert len(links) == 1
    assert links[0]["role"] == "fachlicher Gegenpart"


def test_824_lehren_unter_mindestzahl_keine_muster(bewerbung):
    db, aid = bewerbung
    from bewerbungs_assistent.server import mcp
    for i in range(3):
        _call(mcp, "interview_reflexion_speichern", {
            "bewerbung_id": aid,
            "was_lief_schlecht": "zu weit ausgeholt bei der Vorstellung"})
    res = _result(_call(mcp, "interview_lehren_auswerten", {}))
    assert res["anzahl_reflexionen"] == 3
    assert res["muster"] is None, "unter 4 Reflexionen keine Muster"
    assert "muster_hinweis" in res


def test_824_lehren_muster_und_antwortarchiv(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    for i in range(5):
        aid = db.add_application({
            "company": f"Firma {i}", "title": "PLM Rolle",
            "status": "abgelehnt" if i < 3 else "interview",
            "applied_at": "2026-06-01"})
        _call(mcp, "interview_reflexion_speichern", {
            "bewerbung_id": aid,
            "was_lief_schlecht": "beim Gehaltsthema ausgewichen",
            "was_war_ueberraschend": "Frage nach Fuehrungserfahrung kam",
            "wiederverwendbare_antwort": f"Meine Antwort {i} zur Migration.",
            "gefuehl": 4,
            "next_steps": "Nachfassen naechste Woche"})
    res = _result(_call(mcp, "interview_lehren_auswerten", {}))
    assert res["anzahl_reflexionen"] == 5
    assert len(res["antwortarchiv"]) == 5
    assert res["antwortarchiv"][0]["firma"], "Herkunft muss dran sein"
    muster = res["muster"]
    assert muster, "ab 4 Reflexionen gibt es Muster"
    sk = muster.get("wiederkehrende_selbstkritik") or []
    assert any("gehaltsthema" in e["begriff"] for e in sk), sk
    # Beobachtung mit Fallzahl, kein Urteil
    assert all("von" in e["in_n_von_m"] for e in sk)
    ue = muster.get("wiederkehrende_ueberraschungen") or []
    assert any("fuehrungserfahrung" in e["begriff"] for e in ue), ue
    # Offene naechste Schritte nur aus laufenden Verfahren (2 von 5)
    assert len(res["offene_naechste_schritte"]) == 2


def test_824_gefuehl_gegen_ausgang(setup_env):
    """Hohes Bauchgefuehl, schlechter Ausgang -> Beobachtung, kein Urteil."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    for i in range(5):
        aid = db.add_application({
            "company": f"F{i}", "title": "Rolle",
            "status": "abgelehnt", "applied_at": "2026-06-01"})
        _call(mcp, "interview_reflexion_speichern", {
            "bewerbung_id": aid, "gefuehl": 5, "was_lief_gut": "lief super"})
    res = _result(_call(mcp, "interview_lehren_auswerten", {}))
    blick = (res["muster"] or {}).get("gefuehl_gegen_ausgang")
    assert blick, "5 abgeschlossene Faelle muessen den Vergleich liefern"
    assert blick["gefuehl_schnitt"] == 5.0
    assert blick["positiver_ausgang_quote"] == 0
    assert "unzuverlaessiger Prognostiker" in blick.get("beobachtung", "")


def test_824_rest_endpunkte(setup_env):
    """Frontend-Pfad: anlegen, aendern, loeschen ueber REST."""
    db, _ = setup_env
    aid = db.add_application({
        "company": "Werft Nord", "title": "Lead", "status": "interview"})
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    dash._db = db  # Muster aus test_v18_beta2_plugins: DB injizieren
    client = TestClient(dash.app)

    r = client.post(f"/api/applications/{aid}/reflexionen",
                    json={"was_lief_gut": "REST-Weg funktioniert",
                          "gefuehl": 3})
    assert r.status_code == 200, r.text
    rid = r.json()["reflexion_id"]

    r2 = client.put(f"/api/reflexionen/{rid}",
                    json={"next_steps": "Feedbackbogen senden"})
    assert r2.status_code == 200
    r3 = client.get(f"/api/applications/{aid}/reflexionen")
    daten = r3.json()["reflexionen"]
    assert daten[0]["next_steps"] == "Feedbackbogen senden"

    r4 = client.delete(f"/api/reflexionen/{rid}")
    assert r4.status_code == 200
    assert client.get(
        f"/api/applications/{aid}/reflexionen").json()["reflexionen"] == []
