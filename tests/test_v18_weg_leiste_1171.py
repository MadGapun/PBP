"""#1171 (G85) Baustein 3 und 4: die feste Weg-Leiste und der Rückweg — im Browser, gegen das gebaute Bundle.

Der Auftrag (Nutzerwort 06.10.2026): jeder Schritt höchstens einen Klick vom nächsten entfernt; die Wege zum nächsten Schritt, vor
und zurück, liegen überall am selben Ort; nie scrollen müssen, um zu klicken.

Hier die Wegetabelle als Test: von einer Ansicht eines Falls (Bewerbung, Stelle, Kontakt) führt EIN Klick zu jeder anderen Ansicht
desselben Falls, die es gibt (bei mehreren Einträgen zwei: Fall, dann Eintrag); die Leiste bleibt beim Scrollen stehen; der Rückweg
führt dorthin zurück, woher man kam; die Zurück-Taste des Browsers schließt den obersten Dialog.

Alle Firmen, Personen und Adressen sind erfunden. Gemessen wird bei 1366 × 768 — der kleinsten Größe, die der Auftrag nennt.
"""
from __future__ import annotations

import json
import os
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

TEXT = ("Ihre Aufgaben: Sie betreuen die Engineering-Systeme unseres Werks, pflegen Stuecklisten und Freigabeprozesse "
        "und begleiten die Einfuehrung eines neuen PLM-Systems. Ihr Profil: abgeschlossenes Studium, mehrjaehrige Erfahrung. ") * 4
TITEL = "PLM Systemadministrator (m/w/d)"
FIRMA = "Beispielwerk GmbH"
KLEIN = {"width": 1366, "height": 768}


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post(url, pfad, daten):
    r = urllib.request.Request(f"{url}{pfad}", data=json.dumps(daten).encode(),
                               headers={"Content-Type": "application/json"}, method="POST")
    return json.loads(urllib.request.urlopen(r, timeout=15).read())


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("weg1171")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp / "test.db")
    db.initialize()
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    db.save_jobs([{"hash": "wl001", "title": TITEL, "company": FIRMA, "location": "Musterstadt",
                   "url": "https://karriere.beispielwerk.example/jobs/1", "source": "stepstone", "description": TEXT, "score": 14}])
    aid = db.add_application({"title": TITEL, "company": FIRMA, "status": "interview", "job_hash": "wl001"})
    dash._db = db
    port = _free_port()
    srv = uvicorn.Server(uvicorn.Config(dash.app, host="127.0.0.1", port=port, log_level="warning"))
    srv.install_signal_handlers = lambda: None
    t = threading.Thread(target=srv.run, daemon=True)
    t.start()
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(f"{url}/api/status", timeout=1)
            break
        except Exception:
            time.sleep(0.1)
    # zwei Personen an der Bewerbung (-> Auswahl), eine an keiner
    k1 = _post(url, "/api/contacts", {"full_name": "Erika Beispiel", "company": FIRMA, "tags": ["recruiter"]})
    k2 = _post(url, "/api/contacts", {"full_name": "Max Muster", "company": FIRMA, "tags": ["hr"]})
    for k in (k1, k2):
        _post(url, f"/api/contacts/{k['id']}/links", {"target_kind": "application", "target_id": aid, "role": "recruiter"})
    yield {"url": url, "db": db, "aid": aid, "k1": k1["id"], "k2": k2["id"]}
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture(scope="module")
def browser():
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            yield b
            b.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


def _warte(bedingung, sekunden=10):
    ende = time.time() + sekunden
    while time.time() < ende:
        try:
            if bedingung():
                return True
        except Exception:
            pass
        time.sleep(0.1)
    return False


def _timeline(browser, umgebung):
    ctx = browser.new_context(viewport=KLEIN)
    page = ctx.new_page()
    page.goto(f"{umgebung['url']}/#bewerbungen/{umgebung['aid']}", wait_until="load", timeout=30000)
    page.locator("[data-weg-leiste='bewerbung']").wait_for(timeout=20000)
    # die Leiste zeichnet sich erst mit den Daten (Personen, Dokumente) vollstaendig
    assert _warte(lambda: page.locator("[data-weg-fall='kontakte']").count() == 1)
    return ctx, page


def _leiste_sichtbar(page, art) -> dict:
    """Die Lage der Leiste im Dialog (relativ zu dessen Oberkante: der Dialog steigt beim Oeffnen mit einer kurzen Animation
    auf) und im Fenster."""
    box = page.locator(f"[data-weg-leiste='{art}']").bounding_box()
    dialog = page.locator("[role=dialog]").last.bounding_box()
    ansicht = page.viewport_size
    return {"oben": box["y"] - dialog["y"], "unten": box["y"] + box["height"], "hoehe_fenster": ansicht["height"]}


# ══ Baustein 3: die Leiste ═══════════════════════════════════════════════════════════════════════════════

def test_die_leiste_nennt_rueckweg_faelle_und_den_naechsten_schritt(browser, umgebung):
    ctx, page = _timeline(browser, umgebung)
    try:
        leiste = page.locator("[data-weg-leiste='bewerbung']")
        assert "Zurück zu Bewerbungen" in leiste.locator("[data-weg-zurueck]").inner_text()
        faelle = [x.get_attribute("data-weg-fall") for x in leiste.locator("[data-weg-fall]").all()]
        assert faelle == ["stelle", "firma", "kontakte"], faelle
        assert "2" in leiste.locator("[data-weg-fall='kontakte']").inner_text(), "die Zahl der Personen steht dabei"
        haupt = leiste.locator("[data-weg-haupt]")
        assert "Gespräch vorbereiten" in haupt.inner_text() and "mit Claude" in haupt.inner_text()
    finally:
        ctx.close()


def test_die_leiste_bleibt_beim_scrollen_sichtbar(browser, umgebung):
    ctx, page = _timeline(browser, umgebung)
    try:
        vorher = _leiste_sichtbar(page, "bewerbung")
        page.evaluate("document.querySelector('[data-modal-koerper]').scrollTo(0, 99999)")
        page.wait_for_timeout(300)
        nachher = _leiste_sichtbar(page, "bewerbung")
        assert abs(nachher["oben"] - vorher["oben"]) < 1.5, (vorher, nachher)
        assert nachher["unten"] < nachher["hoehe_fenster"], "die Leiste steht im Fenster, ohne zu scrollen"
        # und ihr Hauptknopf ist dabei klickbar (sichtbar, nicht verdeckt)
        assert page.locator("[data-weg-haupt]").is_visible()
    finally:
        ctx.close()


# ══ Die Wegetabelle: ein Klick zu jedem anderen Fall ═══════════════════════════════════════════════════════

def test_ein_klick_von_der_bewerbung_zur_stelle_und_zurueck(browser, umgebung):
    ctx, page = _timeline(browser, umgebung)
    try:
        page.locator("[data-weg-fall='stelle'] button").click()                    # EIN Klick
        page.locator("[data-weg-leiste='stelle']").wait_for(timeout=15000)
        assert "Stellendetails" in page.locator("[role=dialog]").inner_text()
        # der Rueckweg nennt, woher man kam - und fuehrt dorthin
        zurueck = page.locator("[data-weg-leiste='stelle'] [data-weg-zurueck]")
        assert f"Zurück zu Bewerbung: {TITEL}" in zurueck.inner_text()
        zurueck.click()                                                            # EIN Klick
        page.locator("[data-weg-leiste='bewerbung']").wait_for(timeout=15000)
        assert "Timeline" in page.locator("[role=dialog]").first.inner_text()
    finally:
        ctx.close()


def test_mit_mehreren_personen_steht_eine_auswahl_und_ein_klick_oeffnet_die_person(browser, umgebung):
    ctx, page = _timeline(browser, umgebung)
    try:
        page.locator("[data-weg-fall='kontakte'] > button").click()                # Klick 1: der Fall
        menue = page.locator("[data-weg-menue='kontakte']")
        menue.wait_for(timeout=5000)
        namen = sorted(" ".join(e.inner_text().split()) for e in menue.locator("[data-weg-eintrag]").all())
        assert namen == ["Erika Beispiel", "Max Muster"], namen
        menue.get_by_role("menuitem", name="Max Muster").click()                   # Klick 2: der Eintrag
        dialog = page.locator("[role=dialog]").filter(has_text="Kontakt bearbeiten")
        dialog.wait_for(timeout=15000)
        assert dialog.get_by_role("textbox").first.input_value() == "Max Muster"
        # der Rueckweg der Person nennt die Bewerbung
        zurueck = page.locator("[data-weg-leiste='kontakt'] [data-weg-zurueck]")
        assert f"Zurück zu Bewerbung: {TITEL}" in zurueck.inner_text()
    finally:
        ctx.close()


def test_von_der_stelle_fuehrt_ein_klick_zur_bewerbung(browser, umgebung):
    ctx = browser.new_context(viewport=KLEIN)
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#stellen/wl001", wait_until="load", timeout=30000)
        leiste = page.locator("[data-weg-leiste='stelle']")
        leiste.wait_for(timeout=20000)
        assert _warte(lambda: leiste.locator("[data-weg-fall='bewerbung']").count() == 1), "die Bewerbung ist ein Fall der Stelle"
        assert "Zur Bewerbung" in leiste.locator("[data-weg-haupt]").inner_text()
        leiste.locator("[data-weg-haupt]").click()                                 # EIN Klick
        page.locator("[data-weg-leiste='bewerbung']").wait_for(timeout=15000)
        assert f"Zurück zu Stelle: {TITEL}" in page.locator("[data-weg-leiste='bewerbung'] [data-weg-zurueck]").inner_text()
    finally:
        ctx.close()


def test_der_hauptknopf_folgt_dem_status(browser, umgebung):
    db, aid = umgebung["db"], umgebung["aid"]
    try:
        for status, erwartet in (("beworben", "Nachfassen"), ("angebot", "Angebot prüfen"),
                                 ("abgelehnt", "Aus der Absage lernen"), ("in_vorbereitung", "Lebenslauf")):
            db.connect().execute("UPDATE applications SET status=? WHERE id=?", (status, aid))
            db.connect().commit()
            ctx, page = _timeline(browser, umgebung)
            try:
                assert erwartet in page.locator("[data-weg-haupt]").inner_text(), (status, page.locator("[data-weg-haupt]").inner_text())
            finally:
                ctx.close()
        # zu Ende: kein erfundener Schritt
        db.connect().execute("UPDATE applications SET status='angenommen' WHERE id=?", (aid,))
        db.connect().commit()
        ctx, page = _timeline(browser, umgebung)
        try:
            assert page.locator("[data-weg-haupt]").count() == 0
        finally:
            ctx.close()
    finally:
        db.connect().execute("UPDATE applications SET status='interview' WHERE id=?", (aid,))
        db.connect().commit()


# ══ Baustein 4: die Zurück-Taste ═══════════════════════════════════════════════════════════════════════════

def test_die_zurueck_taste_schliesst_den_dialog_statt_die_seite_zu_verlassen(browser, umgebung):
    ctx = browser.new_context(viewport=KLEIN)
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#bewerbungen", wait_until="load", timeout=30000)
        page.locator("#page-bewerbungen").wait_for(timeout=20000)
        page.get_by_role("button", name="Timeline").first.wait_for(timeout=15000)
        page.get_by_role("button", name="Timeline").first.click()
        page.locator("[role=dialog]").wait_for(timeout=15000)
        page.go_back()
        assert _warte(lambda: page.locator("[role=dialog]").count() == 0), "die Zurück-Taste schließt den Dialog"
        assert page.url.endswith("#bewerbungen"), "und die Seite bleibt"
        assert page.locator("#page-bewerbungen").is_visible()
    finally:
        ctx.close()


def test_das_schliessen_ueber_die_oberflaeche_laesst_keinen_toten_schritt_im_verlauf(browser, umgebung):
    """Ein Dialog legt beim Öffnen einen Verlaufseintrag an und nimmt ihn beim Schließen zurück. Sonst brauchte die
    Zurück-Taste danach einen Druck, der nichts tut."""
    ctx = browser.new_context(viewport=KLEIN)
    page = ctx.new_page()
    try:
        page.goto("about:blank")
        page.goto(f"{umgebung['url']}/#bewerbungen", wait_until="load", timeout=30000)
        page.locator("#page-bewerbungen").wait_for(timeout=20000)
        page.get_by_role("button", name="Timeline").first.wait_for(timeout=15000)
        page.get_by_role("button", name="Timeline").first.click()
        page.locator("[role=dialog]").wait_for(timeout=15000)
        page.locator("[data-modal-schliessen]").click()
        assert _warte(lambda: page.locator("[role=dialog]").count() == 0)
        page.wait_for_timeout(300)           # der Eintrag wird zeitversetzt zurueckgenommen
        page.go_back()
        assert _warte(lambda: page.url == "about:blank"), f"die Zurück-Taste hat die Seite nicht verlassen: {page.url}"
    finally:
        ctx.close()


def test_mit_zwei_dialogen_schliesst_die_zurueck_taste_nur_den_obersten(browser, umgebung):
    ctx, page = _timeline(browser, umgebung)
    try:
        # die Stelle als Dialog UEBER der Timeline: die Bewerbung kennt "Stelle: <Kennung>" im Kopf der Karte
        page.get_by_role("button", name="Stelle:", exact=False).first.click()
        assert _warte(lambda: page.locator("[role=dialog]").count() == 2)
        page.go_back()
        assert _warte(lambda: page.locator("[role=dialog]").count() == 1), "nur der oberste Dialog schließt"
        assert "Timeline" in page.locator("[role=dialog]").first.inner_text()
        page.go_back()
        assert _warte(lambda: page.locator("[role=dialog]").count() == 0)
    finally:
        ctx.close()


# ══ Die Firma: dieselbe Leiste, in der Seitenansicht ═══════════════════════════════════════════════════════

LANGE_FIRMA = "Langwerk AG"


def _firma(browser, umgebung, name=FIRMA, faelle=2):
    from urllib.parse import quote
    ctx = browser.new_context(viewport=KLEIN)
    page = ctx.new_page()
    page.goto(f"{umgebung['url']}/#kontakte/{quote('firma:' + name, safe='')}", wait_until="load", timeout=30000)
    page.locator("[data-weg-leiste='firma']").wait_for(timeout=20000)
    # die Faelle kommen mit der Historie der Firma
    assert _warte(lambda: page.locator("[data-weg-leiste='firma'] [data-weg-fall]").count() >= faelle), "die Fälle der Firma fehlen"
    return ctx, page


def test_die_firma_traegt_dieselbe_leiste_mit_ihren_faellen(browser, umgebung):
    ctx, page = _firma(browser, umgebung)
    try:
        leiste = page.locator("[data-weg-leiste='firma']")
        assert "Zurück zu Firmen" in leiste.locator("[data-weg-zurueck]").inner_text()
        faelle = [x.get_attribute("data-weg-fall") for x in leiste.locator("[data-weg-fall]").all()]
        assert {"bewerbungen", "stellen", "kontakte"} <= set(faelle), faelle
        assert "2" in leiste.locator("[data-weg-fall='kontakte']").inner_text(), "die Zahl der Personen steht dabei"
        # die Firma erfindet keinen Hauptknopf: ihre Pflege steht im Kopf der Ansicht
        assert leiste.locator("[data-weg-haupt]").count() == 0
    finally:
        ctx.close()


def test_ein_klick_von_der_firma_zur_bewerbung_und_zurueck(browser, umgebung):
    ctx, page = _firma(browser, umgebung)
    try:
        page.locator("[data-weg-leiste='firma'] [data-weg-fall='bewerbungen'] > button").click()   # EIN Klick
        page.locator("[data-weg-leiste='bewerbung']").wait_for(timeout=15000)
        zurueck = page.locator("[data-weg-leiste='bewerbung'] [data-weg-zurueck]")
        assert f"Zurück zu Firma: {FIRMA}" in zurueck.inner_text(), zurueck.inner_text()
        zurueck.click()                                                                           # EIN Klick
        page.locator("[data-weg-leiste='firma']").wait_for(timeout=15000)
        assert _warte(lambda: page.locator("[role=dialog]").count() == 0)
        assert FIRMA in page.locator("[data-firma-name]").inner_text()
    finally:
        ctx.close()


def test_von_der_stelle_zur_firma_und_zurueck(browser, umgebung):
    ctx = browser.new_context(viewport=KLEIN)
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#stellen/wl001", wait_until="load", timeout=30000)
        leiste = page.locator("[data-weg-leiste='stelle']")
        leiste.wait_for(timeout=20000)
        assert _warte(lambda: leiste.locator("[data-weg-fall='firma']").count() == 1)
        leiste.locator("[data-weg-fall='firma'] > button").click()                                # EIN Klick
        page.locator("[data-weg-leiste='firma']").wait_for(timeout=15000)
        zurueck = page.locator("[data-weg-leiste='firma'] [data-weg-zurueck]")
        assert f"Zurück zu Stelle: {TITEL}" in zurueck.inner_text(), zurueck.inner_text()
        zurueck.click()                                                                           # EIN Klick
        page.locator("[data-weg-leiste='stelle']").wait_for(timeout=15000)
    finally:
        ctx.close()


def test_die_leiste_der_firma_bleibt_beim_scrollen_der_historie_stehen(browser, umgebung):
    db = umgebung["db"]
    if not umgebung.get("lange_firma"):
        for i in range(16):
            db.add_application({"title": f"Konstruktionsleiter {i}", "company": LANGE_FIRMA, "status": "beworben"})
        umgebung["lange_firma"] = True
    ctx, page = _firma(browser, umgebung, LANGE_FIRMA, faelle=1)
    try:
        page.locator("[data-firma-zeitleiste] li").nth(10).wait_for(timeout=15000)
        # die Seite selbst scrollt (html: overflow-y scroll); `instant`, weil die Seite sonst weich scrollt und der Wert noch 0 ist
        scrollte = page.evaluate("""() => {
            window.scrollTo({ top: 99999, behavior: "instant" });
            return document.scrollingElement.scrollTop;
        }""")
        assert scrollte > 200, "die Historie ist lang genug, um zu scrollen"
        page.wait_for_timeout(300)
        box = page.locator("[data-weg-leiste='firma']").bounding_box()
        assert box["y"] >= 0 and box["y"] + box["height"] <= KLEIN["height"], f"die Leiste steht nicht im Fenster: {box}"
        # und der Rueckweg ist dabei klickbar: ein Klick fuehrt in die Liste aller Firmen
        page.locator("[data-weg-leiste='firma'] [data-weg-zurueck]").click()
        page.locator("[data-firmen-liste]").wait_for(timeout=10000)
    finally:
        ctx.close()


def test_eine_einzeln_geholte_beurteilte_stelle_bietet_die_bewerbung_an(browser, umgebung):
    """Der Hauptknopf der Stelle liest den Pruefstand VOM SERVER (#948): auch wenn die Stelle nicht in der Liste steht und einzeln
    geholt wird. Ohne `pruefstand` in der Einzelantwort galt sie als unbeurteilt und bot „Stelle bewerten“ an."""
    db = umgebung["db"]
    db.save_jobs([{"hash": "wl900", "title": "Einzeln geholte Stelle", "company": "Beispielwerk GmbH",
                   "url": "https://karriere.beispielwerk.example/jobs/900", "source": "manuell", "description": TEXT, "score": 9}])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE '%wl900'").fetchone()["hash"]
    assert db.set_job_analysis(voll, "EMPFOHLEN", "Passt: die Aufgaben stehen im Profil.", "detailanalyse")
    # aus der aktiven Liste nehmen: dann geht der Weg ueber die Einzelantwort
    db.connect().execute("UPDATE jobs SET is_active=0 WHERE hash=?", (voll,))
    db.connect().commit()
    ctx = browser.new_context(viewport=KLEIN)
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#stellen/wl900", wait_until="load", timeout=30000)
        leiste = page.locator("[data-weg-leiste='stelle']")
        leiste.wait_for(timeout=20000)
        assert _warte(lambda: "Bewerbung anlegen" in leiste.locator("[data-weg-haupt]").inner_text()), \
            leiste.locator("[data-weg-haupt]").inner_text()
        assert "Stelle bewerten" not in leiste.inner_text()
    finally:
        ctx.close()
