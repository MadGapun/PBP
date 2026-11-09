"""#1297: Standardgruende sind vom Menschen abschaltbar (und "loeschbar").

Ausloeser (Praxis-Fall 04.11.2026): Claude sortierte eine Stelle mit
`kein_hochschulabschluss` aus - fuer diesen Nutzer nie ein Ausschluss. Der Grund
war kein Eintrag der Tabelle, der erste Gebrauch legte ihn still als eigenen Grund
an; abgeschaltet stand er weiter in `verfuegbare_gruende`, geloescht entstand er
beim naechsten Gebrauch neu.

Abnahme (Issue):
* abgeschaltet -> in keiner `verfuegbare_gruende`-Liste und keiner Werkzeugbeschreibung
* `stelle_einordnen` mit abgeschaltetem Grund -> Fehler mit den aktiven Gruenden,
  keine neue Zeile in der Tabelle
* geloeschter Standardgrund ist nach einem Neustart nicht wieder da
* Freitext "Zertifikats-Nachweis fehlt" wird nicht zu `kein_hochschulabschluss`
* die Automatik sortiert auf einem abgeschalteten Grund nicht aus (Stufe 1, 1b, 2)
"""
from __future__ import annotations

import asyncio
import importlib
import json
import logging
import os

import pytest


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.create_profile("Test", "test@example.com")
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None, **_kw):
        def deco(fn):
            self.tools[name or fn.__name__] = fn
            return fn
        return deco


def _werkzeuge(db):
    from bewerbungs_assistent.tools import jobs, suche
    mcp = _FakeMCP()
    jobs.register(mcp, db, logging.getLogger("test"))
    suche.register(mcp, db, logging.getLogger("test"))
    return mcp.tools


def _id(db, label):
    return next(r["id"] for r in db.get_dismiss_reasons() if r["label"] == label)


def _zeilen(db, label):
    return db.connect().execute(
        "SELECT COUNT(*) FROM dismiss_reasons WHERE LOWER(label)=?", (label,)).fetchone()[0]


def _stelle(db, kennung, titel="PLM Berater (m/w/d)", firma="Musterfirma GmbH", grund=None, **extra):
    job = {"hash": kennung, "title": titel, "company": firma,
           "url": f"https://example.com/1297/{kennung}", "source": "manuell",
           "_manual_entry": True, "description": "Beschreibungstext. " * 20, "score": 5}
    job.update(extra)
    db.save_jobs([job])
    voll = db.resolve_job_hash(kennung)
    if grund:
        db.dismiss_job(voll, grund)
    return voll


def _abschalten(db, label):
    assert _werkzeuge(db)["ablehnungsgrund_aktivieren_setzen"](
        grund_id=_id(db, label), aktiv=False)["is_active"] is False


# ------------------------------------------------------------ Grundlage

def test_alle_standardgruende_haben_eine_zeile(db):
    """Ohne Zeile kein Schalter: alte Bestaende hatten keine fuer
    kein_hochschulabschluss, bereits_beworben, duplikat."""
    from bewerbungs_assistent.services.ablehnungsgruende import STANDARD_GRUENDE
    labels = {r["label"] for r in db.get_dismiss_reasons()}
    assert set(STANDARD_GRUENDE) <= labels


def test_abgeschaltet_in_keiner_liste(db):
    from bewerbungs_assistent.services import ablehnungsgruende as ag
    from bewerbungs_assistent.services import gespeicherte_filter
    _abschalten(db, "kein_hochschulabschluss")
    assert "kein_hochschulabschluss" not in ag.waehlbare_gruende(db)
    assert "kein_hochschulabschluss" not in gespeicherte_filter.erlaubte_gruende(db)
    # Erfolgreiche Antwort von stelle_einordnen
    h = _stelle(db, "a1")
    erg = _werkzeuge(db)["stelle_einordnen"](job_hash=h, bewertung="passt_nicht",
                                             gruende=["zu_junior"])
    assert erg["status"] == "aussortiert"
    assert "kein_hochschulabschluss" not in erg["verfuegbare_gruende"]
    assert "zu_junior" in erg["verfuegbare_gruende"]


def test_stelle_einordnen_weist_abgeschalteten_grund_ab_ohne_neue_zeile(db):
    _abschalten(db, "kein_hochschulabschluss")
    vorher = _zeilen(db, "kein_hochschulabschluss")
    h = _stelle(db, "a2")
    w = _werkzeuge(db)
    for werte in (["kein_hochschulabschluss"], ["zu_junior", "Kein_Hochschulabschluss."]):
        erg = w["stelle_einordnen"](job_hash=h, bewertung="passt_nicht", gruende=werte)
        assert "fehler" in erg and "abgeschaltet" in erg["fehler"], erg
        assert "kein_hochschulabschluss" not in erg["verfuegbare_gruende"]
        assert "sonstiges" in erg["verfuegbare_gruende"]
    assert db.get_job(h)["is_active"], "nichts aussortiert - auch nicht still als 'sonstiges'"
    assert _zeilen(db, "kein_hochschulabschluss") == vorher
    bulk = w["stellen_bulk_bewerten"](bewertung="passt_nicht",
                                      gruende=["kein_hochschulabschluss"], dry_run=False)
    assert "fehler" in bulk and db.get_job(h)["is_active"]


def test_unbekannter_grund_wird_abgewiesen_und_nicht_angelegt(db):
    h = _stelle(db, "a3")
    erg = _werkzeuge(db)["stelle_einordnen"](job_hash=h, bewertung="passt_nicht",
                                             gruende=["windchill_fehlt"])
    assert "fehler" in erg and "windchill_fehlt" in erg["fehler"]
    assert _zeilen(db, "windchill_fehlt") == 0
    assert db.get_job(h)["is_active"]


def test_alte_schreibweise_eines_eingeschalteten_grunds_gilt(db):
    h = _stelle(db, "a4")
    erg = _werkzeuge(db)["stelle_einordnen"](job_hash=h, bewertung="passt_nicht",
                                             gruende=["Dublikat", "Zu_Junior."])
    assert erg["status"] == "aussortiert"
    assert erg["gruende"] == ["duplikat", "zu_junior"]


def test_zaehler_legt_keinen_grund_an(db):
    db.increment_dismiss_reason_usage(["gibt_es_nicht"])
    assert _zeilen(db, "gibt_es_nicht") == 0


def test_werkzeugbeschreibung_nennt_keine_feste_liste():
    from bewerbungs_assistent.server import mcp

    async def _lesen():
        return await mcp.get_tool("stelle_einordnen")

    tool = asyncio.run(_lesen())
    text = json.dumps({"d": tool.description, "p": tool.parameters}, ensure_ascii=False)
    assert "kein_hochschulabschluss" not in text
    assert "verfuegbare_gruende" in text


# ------------------------------------------------------ Loeschen, Neustart

def test_geloeschter_standardgrund_bleibt_nach_neustart_weg(db):
    w = _werkzeuge(db)
    rid = _id(db, "kein_hochschulabschluss")
    vorschau = w["ablehnungsgrund_loeschen"](grund_id=rid)
    assert vorschau["status"] == "vorschau" and "abgeschaltet" in vorschau["hinweis"]
    erg = w["ablehnungsgrund_loeschen"](grund_id=rid, bestaetigung=True)
    assert erg["status"] == "abgeschaltet"
    db.initialize()  # Neustart: Seed und Heilung laufen erneut
    from bewerbungs_assistent.services import ablehnungsgruende as ag
    assert "kein_hochschulabschluss" not in ag.waehlbare_gruende(db)
    assert _zeilen(db, "kein_hochschulabschluss") == 1


def test_sonstiges_und_systemgruende_bleiben_an(db):
    w = _werkzeuge(db)
    erg = w["ablehnungsgrund_aktivieren_setzen"](grund_id=_id(db, "sonstiges"), aktiv=False)
    assert "fehler" in erg
    assert "sonstiges" in __import__(
        "bewerbungs_assistent.services.ablehnungsgruende", fromlist=["x"]).waehlbare_gruende(db)
    with pytest.raises(ValueError):
        db.delete_dismiss_reason(_id(db, "sonstiges"))


def test_eigener_grund_wird_weiter_geloescht(db):
    rid = db.add_dismiss_reason("kein_homeoffice")
    res = db.delete_dismiss_reason(rid)
    assert res["status"] == "geloescht" and _zeilen(db, "kein_homeoffice") == 0


# ------------------------------------------------------------- Bestand

def test_bestand_bleibt_beim_abschalten_und_neustart(db):
    h = _stelle(db, "b1", grund="kein_hochschulabschluss")
    eigen = db.add_dismiss_reason("kein_homeoffice")
    h2 = _stelle(db, "b2", grund="kein_homeoffice")
    _abschalten(db, "kein_hochschulabschluss")
    db.set_dismiss_reason_active(eigen, False)
    db.initialize()
    assert db.get_job(h)["dismiss_reason"] == "kein_hochschulabschluss"
    # bis 1.8.2 machte die Heilung beim Start einen abgeschalteten eigenen Grund zu 'sonstiges'
    assert db.get_job(h2)["dismiss_reason"] == "kein_homeoffice"


def test_abschalten_nennt_den_bestand(db):
    _stelle(db, "b3", grund="kein_hochschulabschluss")
    erg = _werkzeuge(db)["ablehnungsgrund_aktivieren_setzen"](
        grund_id=_id(db, "kein_hochschulabschluss"), aktiv=False)
    assert erg["bestand"]["stellen"] == 1


# ------------------------------------------------------------- Freitext

@pytest.mark.parametrize("text", [
    "Zertifikats-Nachweis fehlt", "Projektabschluss unklar", "Formats passt nicht",
    "Aufsichtsrats-Vorlage", "unbefristet, aber zu weit weg?"])
def test_freitext_trifft_kein_teilwort(text):
    from bewerbungs_assistent.services.ablehnungsgruende import normalisiere_dismiss_wert
    wert, texte = normalisiere_dismiss_wert(text)
    assert wert not in ("kein_hochschulabschluss", "befristet"), (text, wert)


def test_freitext_erzeugt_keinen_abgeschalteten_grund():
    from bewerbungs_assistent.services.ablehnungsgruende import normalisiere_dismiss_wert
    assert normalisiere_dismiss_wert("Hochschulabschluss fehlt")[0] == "kein_hochschulabschluss"
    wert, texte = normalisiere_dismiss_wert(
        "Hochschulabschluss fehlt", abgeschaltet={"kein_hochschulabschluss"})
    assert wert == "sonstiges" and texte == ["Hochschulabschluss fehlt"]
    wert, _ = normalisiere_dismiss_wert(
        "kein_hochschulabschluss", abgeschaltet={"kein_hochschulabschluss"})
    assert wert == "sonstiges"


def test_dismiss_job_schreibt_keinen_abgeschalteten_grund(db):
    _abschalten(db, "kein_hochschulabschluss")
    h = _stelle(db, "f1")
    db.dismiss_job(h, "Hochschulabschluss fehlt")
    job = db.get_job(h)
    assert job["dismiss_reason"] == "sonstiges"
    assert "Hochschulabschluss" in (job.get("dismiss_note") or "")


# ------------------------------------------------------------- Automatik

def test_automatik_stufe2_nicht_auf_abgeschaltetem_grund(db):
    from bewerbungs_assistent.services import stellen_automatik as sa
    _stelle(db, "s2a", titel="PLM Berater Teamcenter (m/w/d)", grund="kein_hochschulabschluss")
    neu = {"hash": "s2neu", "title": "PLM Berater Teamcenter (m/w/d)",
           "company": "Musterfirma GmbH", "description": "Beschreibungstext. " * 20}
    assert sa.entscheide(db, dict(neu))["aktion"] == "ignorieren"
    _abschalten(db, "kein_hochschulabschluss")
    assert sa.entscheide(db, dict(neu))["aktion"] == "anlegen"


def test_automatik_stufe1_nicht_auf_abgeschaltetem_grund(db):
    from bewerbungs_assistent.services import stellen_automatik as sa
    _stelle(db, "s1a", titel="PLM Berater CAD (m/w/d)", grund="kein_hochschulabschluss")
    _stelle(db, "s1b", titel="PLM Berater Windchill (m/w/d)", grund="kein_hochschulabschluss")
    neu = {"hash": "s1neu", "title": "PLM Architect Teamcenter (m/w/d)",
           "company": "Musterfirma GmbH", "description": "Beschreibungstext. " * 20}
    vorher = sa.entscheide(db, dict(neu))
    assert vorher["aktion"] == "aussortieren" and vorher["grund"] == "kein_hochschulabschluss", vorher
    _abschalten(db, "kein_hochschulabschluss")
    assert sa.entscheide(db, dict(neu))["aktion"] == "anlegen"
    # Ueber `anwenden` (der Weg des Suchlaufs) ebenso
    erg = sa.anwenden(db, [dict(neu)])
    assert erg["zaehler"]["automatisch_aussortiert"] == 0


def test_automatik_stufe1b_nicht_auf_abgeschaltetem_grund(db):
    from bewerbungs_assistent.services import stellen_automatik as sa
    for i, firma in enumerate(("Alpha GmbH", "Beta GmbH", "Gamma GmbH")):
        _stelle(db, f"t{i}", titel="CRM Manager Vertrieb (m/w/d)", firma=firma,
                grund="falsches_fachgebiet")
    neu = {"hash": "tneu", "title": "CRM Manager Vertrieb (m/w/d)", "company": "Delta GmbH",
           "description": "Beschreibungstext. " * 20}
    assert sa.entscheide(db, dict(neu))["aktion"] == "aussortieren"
    _abschalten(db, "falsches_fachgebiet")
    assert sa.find_titel_muster(db, neu["title"]) is None
    assert sa.entscheide(db, dict(neu))["aktion"] == "anlegen"


def test_beleg_mit_weiterem_grund_bleibt_mit_diesem(db):
    from bewerbungs_assistent.services.ablehnungsgruende import belege_ohne_abgeschaltete
    jobs = [{"dismiss_reason": '["kein_hochschulabschluss", "zu_junior"]',
             "dismiss_reasons": ["kein_hochschulabschluss", "zu_junior"]},
            {"dismiss_reason": "auto:kein_hochschulabschluss:wiedergaenger"},
            {"dismiss_reason": "zu_senior"}]
    rest = belege_ohne_abgeschaltete(jobs, {"kein_hochschulabschluss"})
    assert [j["dismiss_reasons"] if "dismiss_reasons" in j else j["dismiss_reason"] for j in rest] \
        == [["zu_junior"], "zu_senior"]
    assert jobs[0]["dismiss_reasons"] == ["kein_hochschulabschluss", "zu_junior"], "Eingang unveraendert"


def test_regel_mit_abgeschaltetem_grund_sortiert_nichts_aus(db):
    from bewerbungs_assistent.services import gespeicherte_filter as gf
    h = _stelle(db, "r1")
    _abschalten(db, "kein_hochschulabschluss")
    regel = {"id": 1, "name": "Abschluss", "gruende": ["kein_hochschulabschluss"]}
    assert gf._aussortieren(db, regel, [db.get_job(h)]) == 0
    assert db.get_job(h)["is_active"]


def test_ki_beispiele_ohne_abgeschalteten_grund(db):
    h = _stelle(db, "k1")
    db.dismiss_job(h, "kein_hochschulabschluss", herkunft="ich")
    assert db.get_recent_user_dismissals()
    _abschalten(db, "kein_hochschulabschluss")
    assert db.get_recent_user_dismissals() == []


# ------------------------------------------------------------- Dashboard

def test_dashboard_kennzeichnet_und_weist_ab(db):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent import dashboard
    dashboard._db = db
    c = TestClient(dashboard.app)
    zeilen = c.get("/api/dismiss-reasons").json()
    nach = {z["label"]: z for z in zeilen}
    assert nach["kein_hochschulabschluss"]["ist_standard"] is True
    assert nach["kein_hochschulabschluss"]["abschaltbar"] is True
    assert nach["sonstiges"]["abschaltbar"] is False
    rid = nach["kein_hochschulabschluss"]["id"]
    assert c.patch(f"/api/dismiss-reasons/{rid}", json={"is_active": 0}).status_code == 200
    assert c.patch(f"/api/dismiss-reasons/{nach['sonstiges']['id']}",
                   json={"is_active": 0}).status_code == 400
    h = _stelle(db, "d1")
    r = c.post("/api/jobs/dismiss", json={"hash": h, "reasons": ["kein_hochschulabschluss"]})
    assert r.status_code == 400 and db.get_job(h)["is_active"]
    # Ein getippter neuer Grund ist die Entscheidung des Menschen: er wird angelegt.
    r = c.post("/api/jobs/dismiss", json={"hash": h, "reasons": ["zu_junior", "kein Home-Office"]})
    assert r.status_code == 200 and _zeilen(db, "kein home-office") == 1
    # Loeschen eines Standardgrunds schaltet ab
    rid2 = nach["befristet"]["id"]
    assert c.request("DELETE", f"/api/dismiss-reasons/{rid2}", json={}).json()["status"] == "abgeschaltet"


# ------------------------------------------------- Dashboard im Browser

def test_einstellungen_schalten_standardgrund_ab_im_browser(tmp_path):
    """Gegen das GEBAUTE Bundle: Standardgrund gekennzeichnet, Abschalten ohne Claude,
    danach fehlt er im Aussortier-Dialog. Gewartet wird auf Zustaende, nicht auf Zeit."""
    pytest.importorskip("playwright.sync_api")
    import socket
    import threading
    import time
    import urllib.request

    import uvicorn
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import expect, sync_playwright

    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Erika Musterfrau"})
    d.save_jobs([{"hash": "w1", "title": "Konstrukteur", "company": "Musterfirma GmbH", "source": "manuell",
                  "url": "https://example.com/w1", "description": "Text. " * 40, "score": 5}])
    dash._db = d
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(dash.app, host="127.0.0.1", port=port, log_level="warning"))
    srv.install_signal_handlers = lambda: None
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    for _ in range(100):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/api/status", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    url = f"http://127.0.0.1:{port}"
    try:
        try:
            pw = sync_playwright().start()
            b = pw.chromium.launch(headless=True)
        except PlaywrightError as exc:
            pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")
        try:
            page = b.new_page()
            page.goto(f"{url}/#einstellungen", wait_until="domcontentloaded", timeout=30000)
            reiter = page.locator("[data-settings-reiter]")
            reiter.wait_for(timeout=15000)
            ziel = reiter.get_by_role("button", name="Ablehnungsgründe", exact=True)
            if not ziel.is_visible():
                reiter.get_by_role("button", name="Erweitert").first.click()
            ziel.click()
            schalter = page.locator('[data-grund-schalter="kein_hochschulabschluss"]')
            expect(schalter).to_have_text("Abschalten", timeout=15000)
            zeile = schalter.locator("xpath=ancestor::div[contains(@class,'justify-between')][1]")
            expect(zeile.get_by_text("Standard", exact=True)).to_be_visible()
            expect(page.locator('[data-grund-schalter="sonstiges"]')).to_have_count(0)
            schalter.click()
            expect(schalter).to_have_text("Einschalten", timeout=15000)
            from bewerbungs_assistent.services.ablehnungsgruende import waehlbare_gruende
            assert "kein_hochschulabschluss" not in waehlbare_gruende(d)
            # Aussortier-Dialog der Stellen: der abgeschaltete Grund steht nicht zur Wahl
            page.goto(f"{url}/#stellen", wait_until="load", timeout=30000)
            page.get_by_text("Konstrukteur").first.wait_for(timeout=15000)
            page.get_by_role("button", name="Passt nicht").first.click()
            dialog = page.get_by_role("dialog")
            expect(dialog.get_by_role("button", name="Zu junior")).to_be_visible(timeout=15000)
            expect(dialog.get_by_role("button", name="Kein Hochschulabschluss")).to_have_count(0)
        finally:
            b.close()
            pw.stop()
    finally:
        srv.should_exit = True
        t.join(timeout=10)
        dash._db = None
        d.close()
        os.environ.pop("BA_DATA_DIR", None)
