"""#1436: Browser-Quellen-Karte einklappbar, Suchbegriffe je Quelle in den Einstellungen pflegbar.

Datenbank isoliert (BA_DATA_DIR), keine Netzabrufe, Testdaten fiktiv. Der Browser-Teil laeuft gegen das GEBAUTE Bundle.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import re
import socket
import threading
import time
import urllib.request

import pytest

from bewerbungs_assistent.services import browser_handoff as bh

AUSWAHL = ["linkedin", "kimeta", "indeed", "jobspy_indeed", "bundesagentur"]
MUSS = ["Arbeitsvorbereitung", "CNC", "Fertigungsplanung"]


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database

    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Erika Musterfrau"})
    d.set_search_criteria("keywords_muss", MUSS)
    d.set_profile_setting("active_sources", AUSWAHL)
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _keys(eintraege):
    return {e["key"]: e for e in eintraege}


# ── Liste der Karte ──────────────────────────────────────────────────

def test_abgekuendigte_gewaehlte_quelle_steht_als_browser_quelle_mit_ersatzbegriffen(db):
    e = _keys(bh.browser_quellen(db, auswahl=AUSWAHL))["kimeta"]
    assert e["art"] == bh.UEBERSPRUNGEN, e
    assert e["suchbegriffe_herkunft"] == "suchkriterien" and e["suchbegriffe"] == MUSS, e
    assert e["werkzeug"].startswith("quelle_handoff('kimeta'"), e


def test_abgekuendigte_nicht_gewaehlte_quelle_fehlt(db):
    assert "kimeta" not in _keys(bh.browser_quellen(db, auswahl=["linkedin"]))


def test_von_hand_abgeschaltet_ist_nicht_ausgefallen(db):
    """Vorher stand eine abgeschaltete Quelle (is_active=0 ohne Fehlerserie) dauerhaft als "ausgefallen" in der Karte."""
    db.update_scraper_health("freelancermap", "ok", 3, 1.0)
    db.toggle_scraper("freelancermap", False)
    assert "freelancermap" not in bh.intern_ausgefallen(db, ["freelancermap"])
    db.update_scraper_health("freelancermap", "timeout", 0, 90.0)
    assert "freelancermap" in bh.intern_ausgefallen(db, ["freelancermap"])


# ── Pflegbare Quellen ────────────────────────────────────────────────

def test_pflegbar_sind_nur_quellen_mit_leser(db):
    q = _keys(bh.pflegbare_quellen(db, auswahl=AUSWAHL))
    assert {"linkedin", "kimeta", "indeed"} <= set(q), q.keys()
    # Die Bundesagentur liest kein Suchprofil: dort waere eine Einstellung ohne Wirkung (L11). Ebenso die optionalen,
    # als defekt gefuehrten Quellen: der Auftrag nennt sie nur mit Namen.
    assert "bundesagentur" not in q
    optional = {e["key"] for e in bh.browser_quellen(db, auswahl=AUSWAHL) if e["art"] == bh.DEFEKT_NUR_BROWSER}
    assert optional and not optional & set(q), optional & set(q)
    # Gegenstueck: haette eine optionale Quelle Begriffe, setzte der Auftrag sie trotzdem nicht ein (kein Leser).
    mit_begriff = [{**e, "suchbegriffe": ["Probebegriff-1436"]} for e in bh.browser_quellen(db, auswahl=AUSWAHL)
                   if e["art"] == bh.DEFEKT_NUR_BROWSER]
    assert "Probebegriff-1436" not in bh.prompt(mit_begriff)
    assert q["indeed"]["wirkung"] == "interner Suchlauf und Auftrag „Browser-Quellen mit Claude“"
    assert q["indeed"]["ersatz_suchkriterien"] == len(MUSS)
    assert q["kimeta"]["ersatz_suchkriterien"] == len(MUSS)
    assert q["linkedin"]["ersatz_suchkriterien"] == 0


def test_leser_im_lauf_deckt_jedes_portal_mit_suchprofil_im_lauf():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    assert set(bh.LESER_IM_LAUF) == set(bh.PORTALE_MIT_SUCHPROFIL_IM_LAUF)
    assert all(leser in SOURCE_REGISTRY for leser in bh.LESER_IM_LAUF.values())


def test_nur_interner_leser_gewaehlt(db):
    q = _keys(bh.pflegbare_quellen(db, auswahl=["jobspy_indeed"]))
    assert q["indeed"]["wirkung"] == "interner Suchlauf", q


def test_gespeichertes_profil_einer_abgewaehlten_quelle_bleibt_sichtbar(db):
    db.update_portal_search_profile("xing", primaere_suchen=[{"keywords": "Arbeitsplaner"}])
    q = _keys(bh.pflegbare_quellen(db, auswahl=AUSWAHL))
    assert q["xing"]["primaere_suchen"] == ["Arbeitsplaner"]
    assert q["xing"]["wirkung"].startswith("zurzeit nicht genutzt")


def test_speichern_behaelt_filter_und_notiz_bestehender_eintraege(db):
    db.update_portal_search_profile("linkedin", primaere_suchen=[
        {"keywords": "Arbeitsvorbereiter", "filter": {"ort": "Hannover"}, "notiz": "treffsicher"}],
        nicht_verwenden=[{"wert": "AV", "grund": "nur Versicherungen"}])
    bh.profil_speichern(db, "linkedin", ["Arbeitsvorbereiter", " CNC   Planer "], ["Fertigung"], ["AV", "Logistik"])
    p = db.find_portal_search_profile("linkedin")
    assert p["primaere_suchen"][0] == {"keywords": "Arbeitsvorbereiter", "filter": {"ort": "Hannover"},
                                       "notiz": "treffsicher"}
    assert p["primaere_suchen"][1] == {"keywords": "CNC Planer"}
    assert p["sekundaere_suchen"] == [{"keywords": "Fertigung"}]
    assert p["nicht_verwenden"] == [{"wert": "AV", "grund": "nur Versicherungen"}, {"wert": "Logistik", "grund": ""}]
    # Der Leser sieht die gespeicherten Begriffe: der Auftrag an Claude nutzt sie.
    e = _keys(bh.browser_quellen(db, auswahl=AUSWAHL))["linkedin"]
    assert e["suchbegriffe"] == ["Arbeitsvorbereiter", "CNC Planer", "Fertigung"], e


def test_pflege_prompt_nennt_quellen_ohne_begriffe_zuerst(db):
    db.update_portal_search_profile("linkedin", primaere_suchen=["Arbeitsvorbereiter"])
    text = bh.pflege_prompt(bh.pflegbare_quellen(db, auswahl=AUSWAHL))
    assert text.index("('kimeta')") < text.index("('linkedin')"), text
    assert "Ändere nichts ohne meine Zustimmung." in text
    assert bh.pflege_prompt([]) == ""


def test_pflege_prompt_nennt_nur_vorhandene_werkzeuge(db, tmp_path):
    """Ein Auftrag, der auf ein Werkzeug zeigt, das es nicht gibt, fuehrt ins Leere (#1000)."""
    import bewerbungs_assistent.server as srv
    importlib.reload(srv)

    async def _namen():
        if hasattr(srv.mcp, "list_tools"):
            return {t.name for t in await srv.mcp.list_tools()}
        return set((await srv.mcp.get_tools()).keys())
    vorhanden = asyncio.run(_namen())
    text = bh.pflege_prompt(bh.pflegbare_quellen(db, auswahl=AUSWAHL))
    genannt = set(re.findall(r"\b([a-z]+(?:_[a-z]+)+)\(", text))
    assert {"suchprofil_lesen", "suchprofil_aktualisieren", "suchkriterien_anzeigen"} <= genannt, genannt
    assert not genannt - vorhanden, genannt - vorhanden


# ── Endpunkte ────────────────────────────────────────────────────────

@pytest.fixture
def client(db):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash

    dash._db = db
    yield TestClient(dash.app)
    dash._db = None


def test_karte_ist_zu_und_merkt_sich_den_zustand(client):
    antwort = client.get("/api/jobsuche/browser-quellen").json()
    assert antwort["offen"] is False and antwort["pflege_prompt"], antwort
    assert client.put("/api/jobsuche/browser-quellen/offen", json={"offen": True}).json()["offen"] is True
    assert client.get("/api/jobsuche/browser-quellen").json()["offen"] is True
    assert client.put("/api/jobsuche/browser-quellen/offen", json={"offen": "ja"}).status_code == 400


def test_suchprofil_speichern_nur_fuer_quellen_mit_leser(client, db):
    assert client.put("/api/suchprofile/bundesagentur", json={"primaere_suchen": ["X"]}).status_code == 400
    assert client.put("/api/suchprofile/linkedin", json={"primaere_suchen": "X"}).status_code == 400
    r = client.put("/api/suchprofile/linkedin", json={"primaere_suchen": ["Arbeitsvorbereiter"],
                                                      "sekundaere_suchen": [], "nicht_verwenden": []})
    assert r.status_code == 200 and r.json()["quelle"]["primaere_suchen"] == ["Arbeitsvorbereiter"], r.json()
    assert db.find_portal_search_profile("linkedin")["primaere_suchen"] == [{"keywords": "Arbeitsvorbereiter"}]


# ── Oberflaeche (gebautes Bundle) ────────────────────────────────────

@pytest.fixture
def server(db):
    import uvicorn
    import bewerbungs_assistent.dashboard as dash

    dash._db = db
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
    yield f"http://127.0.0.1:{port}"
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None


@pytest.fixture(scope="module")
def browser():
    pw_api = pytest.importorskip("playwright.sync_api")
    try:
        with pw_api.sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            yield b
            b.close()
    except pw_api.Error as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


def test_karte_einklappen_und_begriffe_pflegen(server, browser):
    from playwright.sync_api import expect

    ctx = browser.new_context(viewport={"width": 1280, "height": 900}, locale="de-DE")
    page = ctx.new_page()
    try:
        page.goto(f"{server}/#stellen", wait_until="domcontentloaded")
        karte = page.get_by_test_id("browser-quellen-karte")
        expect(karte).to_contain_text("Quellen", timeout=20000)
        # Zu: keine Liste, keine Begriffe; der Knopf fuer den Browserlauf bleibt.
        expect(page.get_by_test_id("browser-quellen-liste")).to_have_count(0)
        expect(karte.get_by_role("button", name=re.compile("Browser-Quellen mit Claude"))).to_be_visible()

        karte.get_by_role("button", name=re.compile("Diese Quellen laufen nur über den Browser")).click()
        liste = page.get_by_test_id("browser-quellen-liste")
        expect(liste).to_contain_text("3 Begriffe aus deinen Suchkriterien")
        assert "Fertigungsplanung" not in liste.inner_text()
        expect(karte.get_by_role("button", name=re.compile("Suche pflegen mit Claude"))).to_be_visible()

        # Der Zustand liegt im Profil: nach dem Neuladen ist die Karte noch offen.
        page.reload(wait_until="domcontentloaded")
        expect(page.get_by_test_id("browser-quellen-liste")).to_be_visible(timeout=20000)

        page.get_by_test_id("browser-quellen-liste").locator("li", has_text="LinkedIn") \
            .get_by_role("button", name="Begriffe pflegen").click()
        bereich = page.get_by_test_id("suchbegriffe-linkedin")
        expect(bereich).to_have_attribute("open", "", timeout=20000)
        feld = bereich.locator("input").first
        feld.fill("Arbeitsvorbereiter")
        feld.press("Enter")
        bereich.get_by_role("button", name="Speichern").click()
        expect(page.get_by_test_id("suchbegriffe-linkedin")).to_contain_text("1 eigener Begriff", timeout=20000)
    finally:
        ctx.close()
