"""Wege durch PBP (#1171, G85): jeder naechste Schritt ist einen Klick entfernt.

Der Nutzer (06.10.2026): „Wenn du testest, dann alle Ablaeufe von A nach B — eine Stelle ansehen, bewerten lassen, eine
Bewerbung dazu schreiben; bei einer Bewerbung nachfassen, die Timeline ansehen, wer der Ansprechpartner ist, wie die Stelle
beschrieben war, wie der Lebenslauf aussah. Jeder Schritt hoechstens einen Mausklick vom naechsten entfernt, mit Links und
Querverbindungen, und ohne zum Klicken scrollen zu muessen.“

Die Ist-Aufnahme (290 Elemente, 12 Ansichten) steht im Issue #1171. Dieses Modul prueft die Wege aus Baustein 1 und 2:

* Dashboard „Offen“: eine Nachfassung oeffnet IHRE Bewerbung (war: nur die Aufgabenliste).
* Nach „Bewerbung speichern“ liegt die neue Bewerbung offen da, mit den Unterlagen als naechstem Schritt.
* Bewerbung ↔ Person: der Name fuehrt zur Karte, die Karte nennt die Bewerbung und fuehrt zurueck.
* Firma → „Stelle oeffnen“ / „Kontakt oeffnen“ oeffnen das Objekt (waren: nur die Liste).
* Dashboard-Top-Stelle, Aufgabe und Bewerbungskarte fuehren in einem Klick zur Stelle bzw. Bewerbung.
* Die Timeline hat eine Sprungleiste, die stehen bleibt und den Abschnitt unter sie legt.

Das gebaute Bundle wird getestet (nach JSX-Aenderungen neu bauen: `cd frontend && pnpm exec vite build`).
"""
from __future__ import annotations

import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pytest
import uvicorn

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend" / "src"
TEXT = ("Wir suchen eine Sachbearbeitung im Einkauf. Aufgaben: Disposition, Bestellabwicklung mit SAP MM, "
        "Lieferantenkommunikation. Anforderungen: kaufmaennische Ausbildung, Englisch. ") * 3


def _tag(tage: int) -> str:
    return (date.today() + timedelta(days=tage)).isoformat()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    db.save_jobs([
        {"hash": "wg1", "title": "Sachbearbeitung Einkauf", "company": "Musterbetrieb GmbH", "url": "https://example.com/wg1",
         "source": "manuell", "description": TEXT, "remote_level": "hybrid", "location": "Hamburg", "score": 8},
        {"hash": "wg2", "title": "Disponent Lager", "company": "Beispiel AG", "url": "https://example.com/wg2",
         "source": "manuell", "description": TEXT, "remote_level": "onsite", "location": "Hannover", "score": 6},
    ])
    con = db.connect()
    h1 = con.execute("SELECT hash FROM jobs WHERE hash LIKE '%wg1'").fetchone()["hash"]
    h2 = con.execute("SELECT hash FROM jobs WHERE hash LIKE '%wg2'").fetchone()["hash"]
    app = db.add_application({"title": "Disponent Lager", "company": "Beispiel AG", "status": "beworben",
                              "applied_at": _tag(-20), "job_hash": h2})
    kontakt = db.add_contact({"full_name": "Kim Beispiel", "company": "Beispiel AG", "position": "Personalreferentin"})
    db.link_contact(kontakt, "application", app, role="Personalabteilung")
    db.add_follow_up(app, _tag(-2), "nachfass")
    db.add_task({"titel": "Zeugnis anfordern", "typ": "custom", "faellig_am": _tag(-1), "application_id": app})
    dash._db = db
    port = _free_port()
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
    yield {"url": f"http://127.0.0.1:{port}", "db": db, "app": app, "kontakt": kontakt, "h1": h1, "h2": h2}
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


def _seite(browser, url, hash_):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(f"{url}/#{hash_}", wait_until="load", timeout=30000)
    page.wait_for_function("t => !document.body.innerText.includes(t)", arg="wird vorbereitet", timeout=20000)
    return page


def _dialog_titel(page, erwartet, frist=10000):
    """Wartet auf den Zustand, nicht auf Zeit: der oberste Dialog traegt den erwarteten Titel."""
    page.wait_for_function(
        """erwartet => { const d = [...document.querySelectorAll('[role=dialog]')]; if (!d.length) return false;
           const t = d[d.length - 1].querySelector('h2,h3'); return !!t && t.innerText.startsWith(erwartet); }""",
        arg=erwartet, timeout=frist)
    return page.evaluate("""() => { const d = [...document.querySelectorAll('[role=dialog]')]; return d[d.length - 1].querySelector('h2,h3').innerText; }""")


def _ruhig(page):
    """Wartet, bis der Dialoginhalt aufgehoert hat zu scrollen (fuenf Bilder lang dieselbe Position) — Zustand, nicht Zeit."""
    page.evaluate("""() => new Promise((fertig) => { const k = document.querySelector('[data-modal-koerper]'); let letzte = -1, gleich = 0;
        const schritt = () => { if (k.scrollTop === letzte) gleich += 1; else { gleich = 0; letzte = k.scrollTop; }
          if (gleich >= 5) fertig(true); else requestAnimationFrame(schritt); }; schritt(); })""")


def _im_fenster(page, locator) -> bool:
    box = locator.bounding_box()
    return bool(box) and box["y"] >= 0 and box["y"] + box["height"] <= page.evaluate("innerHeight")


# ── Dashboard ───────────────────────────────────────────────────────────────────────────

def test_dashboard_nachfassen_oeffnet_die_bewerbung(browser, server):
    page = _seite(browser, server["url"], "dashboard")
    try:
        zeile = page.locator("[data-offen-zeile='nachfass']").first
        zeile.wait_for(timeout=15000)
        assert _im_fenster(page, zeile), "die Nachfass-Zeile liegt nicht ohne Scrollen im Fenster"
        zeile.click()
        assert _dialog_titel(page, "Timeline").endswith("Disponent Lager")
    finally:
        page.close()


def test_dashboard_top_stelle_oeffnet_die_stelle(browser, server):
    page = _seite(browser, server["url"], "dashboard")
    try:
        page.locator("[data-top-stelle]").first.click(timeout=15000)
        assert _dialog_titel(page, "Stellendetails") == "Stellendetails"
        assert "Sachbearbeitung Einkauf" in page.locator("[role=dialog]").inner_text()
    finally:
        page.close()


# ── Bewerbung, Stelle, Person ───────────────────────────────────────────────────────────

def test_bewerbungskarte_fuehrt_zur_stelle(browser, server):
    page = _seite(browser, server["url"], "bewerbungen")
    try:
        page.locator("[data-karte-zur-stelle]").first.click(timeout=15000)
        assert _dialog_titel(page, "Stellendetails") == "Stellendetails"
        assert "Disponent Lager" in page.locator("[role=dialog]").inner_text()
    finally:
        page.close()


def test_aufgabe_fuehrt_in_einem_klick_zur_bewerbung(browser, server):
    page = _seite(browser, server["url"], "aufgaben")
    try:
        knopf = page.locator("[data-aufgabe-zur-bewerbung]").first
        knopf.wait_for(timeout=15000)
        assert _im_fenster(page, knopf)
        knopf.click()
        assert _dialog_titel(page, "Timeline").endswith("Disponent Lager")
    finally:
        page.close()


def test_person_in_der_bewerbung_fuehrt_zur_karte_und_die_karte_zurueck(browser, server):
    page = _seite(browser, server["url"], f"bewerbungen/{server['app']}")
    try:
        _dialog_titel(page, "Timeline")
        page.locator("[data-person-sprung]").first.click(timeout=15000)
        assert _dialog_titel(page, "Kontakt") == "Kontakt bearbeiten"
        assert page.locator("[role=dialog] input").first.input_value() == "Kim Beispiel"
        verknuepfung = page.locator("[data-kontakt-verknuepfungen] button[data-verknuepfung-sprung='application']").first
        text = verknuepfung.inner_text()
        assert text.startswith("Bewerbung:") and "Disponent Lager" in text and "Beispiel AG" in text, text
        assert "application" not in text, "kein rohes englisches Wort mehr"
        assert _im_fenster(page, verknuepfung), "die Verknuepfung liegt nicht ohne Scrollen im Fenster"
        verknuepfung.click()
        assert _dialog_titel(page, "Timeline").endswith("Disponent Lager")
    finally:
        page.close()


def test_firma_oeffnet_stelle_und_person_selbst(browser, server):
    url = server["url"]
    firma = "kontakte/firma%3ABeispiel%20AG"
    page = _seite(browser, url, firma)
    try:
        page.get_by_role("button", name="Kontakt öffnen").first.click(timeout=15000)
        assert _dialog_titel(page, "Kontakt") == "Kontakt bearbeiten"
        assert page.locator("[role=dialog] input").first.input_value() == "Kim Beispiel"
    finally:
        page.close()
    page = _seite(browser, url, firma)
    try:
        page.get_by_role("button", name="Stelle öffnen").first.click(timeout=15000)
        assert _dialog_titel(page, "Stellendetails") == "Stellendetails"
        assert "Disponent Lager" in page.locator("[role=dialog]").inner_text()
    finally:
        page.close()


# ── Adresse: der Link aus Claude ────────────────────────────────────────────────────────

def test_link_aus_claude_oeffnet_die_stelle(browser, server):
    """`#stellen/<Kennung>` fuehrt „direkt zur Stelle“ (so beschreibt es die Anleitung an Claude) — wie `#bewerbungen/<id>` die
    Timeline oeffnet. Vorher blaetterte er nur in der Liste und markierte die Zeile."""
    page = _seite(browser, server["url"], "stellen/wg1")
    try:
        assert _dialog_titel(page, "Stellendetails") == "Stellendetails"
        assert "Sachbearbeitung Einkauf" in page.locator("[role=dialog]").inner_text()
    finally:
        page.close()


def test_link_aus_claude_oeffnet_auch_eine_stelle_hinter_der_ersten_seite(browser, server):
    """Die Liste laedt 20 Stellen auf einmal. Eine Stelle dahinter steht nicht in der geladenen Liste — der Sprung holt sie
    einzeln, statt still ins Leere zu laufen."""
    server["db"].save_jobs(
        [{"hash": f"wgfuell{n:02d}", "title": f"Fuellstelle {n:02d}", "company": "Fuell GmbH", "url": f"https://example.com/f{n}",
          "source": "manuell", "description": TEXT, "score": 60 - n} for n in range(26)]
        + [{"hash": "wgende", "title": "Letzte Stelle im Bestand", "company": "Ende GmbH", "url": "https://example.com/ende",
            "source": "manuell", "description": TEXT, "score": 1}])
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    abgefragt = []
    page.on("request", lambda r: abgefragt.append(r.url))
    try:
        page.goto(f"{server['url']}/#stellen/wgende", wait_until="load", timeout=30000)
        assert _dialog_titel(page, "Stellendetails") == "Stellendetails"
        assert "Letzte Stelle im Bestand" in page.locator("[role=dialog]").inner_text()
        assert any(u.endswith("/api/jobs/wgende") for u in abgefragt), "die Stelle kam nicht ueber die Einzelabfrage"
    finally:
        page.close()


def test_nach_bewerbung_speichern_liegt_die_neue_bewerbung_offen_da(browser, server):
    page = _seite(browser, server["url"], "stellen")
    try:
        page.get_by_text("Sachbearbeitung Einkauf", exact=False).first.click(timeout=15000)
        _dialog_titel(page, "Stellendetails")
        page.get_by_role("dialog").get_by_role("button", name="Bewerbung anlegen").click()
        _dialog_titel(page, "Bewerbung anlegen")
        page.get_by_role("dialog").get_by_role("button", name="Bewerbung speichern").click()
        titel = _dialog_titel(page, "Timeline", frist=15000)
        assert "Sachbearbeitung Einkauf" in titel, titel
        weiter = page.locator("[data-weiter-unterlagen]")
        assert weiter.count() == 2, "Lebenslauf und Anschreiben sind der naechste Schritt, solange die Bewerbung vorbereitet wird"
        assert all(_im_fenster(page, w) for w in weiter.all()), "die Knoepfe liegen nicht ohne Scrollen im Fenster"
        assert page.locator("[role=dialog]").inner_text().count("In Vorbereitung") >= 1
    finally:
        page.close()


# ── Sprungleiste ────────────────────────────────────────────────────────────────────────

def test_sprungleiste_legt_den_abschnitt_unter_die_stehende_leiste(browser, server):
    page = _seite(browser, server["url"], f"bewerbungen/{server['app']}")
    try:
        _dialog_titel(page, "Timeline")
        leiste = page.locator("[data-sprungleiste]")
        leiste.wait_for(timeout=15000)
        namen = [e.inner_text() for e in page.locator("[data-sprung-abschnitt]").all()]
        assert {"Status", "Stelle", "Dokumente", "Personen", "Aufgaben", "Verlauf"} <= set(namen), namen
        assert namen == [n for n in ["Status", "Stelle", "Dokumente", "Personen", "Aufgaben", "Termine", "Verlauf"] if n in namen], "feste Reihenfolge"
        # ein Abschnitt in der Mitte landet direkt unter der Leiste
        page.locator("[data-sprung-abschnitt='personen']").click()
        page.wait_for_function("() => document.querySelector('[data-modal-koerper]').scrollTop > 50", timeout=10000)
        _ruhig(page)
        box_leiste = leiste.bounding_box()
        box_ziel = page.locator("[data-abschnitt='personen']").bounding_box()
        koerper = page.locator("[data-modal-koerper]").bounding_box()
        assert abs(box_leiste["y"] - koerper["y"]) <= 1, "die Leiste steht buendig am oberen Rand des Dialoginhalts (kein Streifen darueber)"
        assert 0 <= box_ziel["y"] - (box_leiste["y"] + box_leiste["height"]) < 30, (box_ziel, box_leiste)
        assert _im_fenster(page, leiste), "die Leiste bleibt beim Scrollen sichtbar"
        assert page.locator("[data-sprung-abschnitt='personen']").get_attribute("aria-current") == "true"
        # der letzte Abschnitt kann nicht mehr nach oben scrollen: er ist im Bild und der Eintrag ist markiert
        page.locator("[data-sprung-abschnitt='verlauf']").click()
        page.wait_for_function("() => document.querySelector('[data-sprung-abschnitt=verlauf]').getAttribute('aria-current') === 'true'", timeout=10000)
        _ruhig(page)
        ziel = page.locator("[data-abschnitt='verlauf']").bounding_box()
        koerper = page.locator("[data-modal-koerper]").bounding_box()
        assert koerper["y"] <= ziel["y"] < koerper["y"] + koerper["height"], (ziel, koerper)
        assert page.locator("[data-sprung-abschnitt='personen']").get_attribute("aria-current") is None
    finally:
        page.close()


def test_timeline_oeffnet_sich_einmal_und_bleibt(browser, server):
    """Ein Sprung in die Timeline oeffnete den Dialog, schloss ihn nach rund 70 ms wieder und oeffnete ihn erneut (die ganze
    Seite wurde bei jedem Nachladen durch die Ladeanzeige ersetzt, auch mit offenem Dialog). Gemessen schon in Beta 16 —
    und ein Dialog, der kurz verschwindet, ist ein Weg, der nicht verlaesslich ankommt."""
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    try:
        page.goto(f"{server['url']}/#bewerbungen/{server['app']}", wait_until="load", timeout=30000)
        page.evaluate("""() => { window.__zahlen = []; const z = () => window.__zahlen.push(document.querySelectorAll('[role=dialog]').length);
            new MutationObserver(z).observe(document.body, {childList: true, subtree: true}); z(); }""")
        _dialog_titel(page, "Timeline")
        # den Beobachter laufen lassen: das Nachladen der Seite kommt Sekundenbruchteile nach dem Oeffnen
        page.wait_for_function("() => window.__zahlen.length > 3", timeout=10000)
        page.evaluate("() => new Promise((fertig) => setTimeout(fertig, 2500))")
        zahlen = page.evaluate("window.__zahlen")
        erste = zahlen.index(1)
        assert 0 not in zahlen[erste:], f"der Dialog verschwand nach dem Oeffnen wieder: {zahlen}"
    finally:
        page.close()


# ── Server: Verknuepfungen mit lesbarem Ziel, einzelner Kontakt, Routenreihenfolge ─────────

def test_kontakt_verknuepfungen_nennen_das_ziel(server):
    db = server["db"]
    links = {l["target_kind"]: l for l in db.get_contact_links_mit_ziel(server["kontakt"])}
    assert set(links) == {"application"}
    l = links["application"]
    assert (l["ziel_titel"], l["ziel_firma"], l["ziel_status"], l["ziel_gefunden"]) == ("Disponent Lager", "Beispiel AG", "beworben", True)
    # eine Stelle und ein Termin dazu
    db.link_contact(server["kontakt"], "job", server["h1"], role="Ansprechpartner")
    meeting = db.add_meeting({"application_id": server["app"], "title": "Erstgespräch", "meeting_date": _tag(3) + "T10:00:00"})
    db.link_contact(server["kontakt"], "meeting", meeting, role="Gast")
    nach = {l["target_kind"]: l for l in db.get_contact_links_mit_ziel(server["kontakt"])}
    assert nach["job"]["ziel_titel"] == "Sachbearbeitung Einkauf" and nach["job"]["ziel_firma"] == "Musterbetrieb GmbH"
    assert nach["meeting"]["ziel_titel"] == "Erstgespräch" and nach["meeting"]["ziel_bewerbung_id"] == server["app"]
    # ein verschwundenes Ziel bleibt eine Zeile, ohne dass die Liste kippt
    db.connect().execute("DELETE FROM applications WHERE id=?", (server["app"],))
    db.connect().commit()
    weg = {l["target_kind"]: l for l in db.get_contact_links_mit_ziel(server["kontakt"])}
    assert weg["application"]["ziel_gefunden"] is False and weg["application"]["ziel_titel"] == ""
    assert weg["job"]["ziel_gefunden"] is True


def test_rest_einzelner_kontakt_und_feste_pfade_bleiben_erreichbar(server):
    import json
    url = server["url"]

    def holen(pfad):
        try:
            with urllib.request.urlopen(url + pfad, timeout=10) as r:
                return r.status, r.read().decode("utf-8", "replace"), r.headers.get("content-type", "")
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode("utf-8", "replace"), e.headers.get("content-type", "")

    status, body, _ = holen(f"/api/contacts/{server['kontakt']}")
    assert status == 200 and json.loads(body)["full_name"] == "Kim Beispiel"
    assert holen("/api/contacts/gibtsnicht")[0] == 404
    # Die Kennung darf die festen Pfade darunter nicht verschlucken (FastAPI nimmt sonst „export.csv“ als Kennung).
    status, body, typ = holen("/api/contacts/export.csv")
    assert status == 200 and "text/csv" in typ and "Kim Beispiel" in body, (status, typ, body[:80])
    assert holen("/api/contacts/categories")[0] == 200
    assert holen("/api/contacts/pending")[0] == 200
    links = json.loads(holen(f"/api/contacts/{server['kontakt']}/links")[1])["links"]
    assert links[0]["ziel_titel"] == "Disponent Lager"


def test_einzelne_stelle_traegt_dieselben_felder_wie_die_liste(server):
    """Der Sprung „Zur Stelle“ holt die Stelle einzeln. Sie sieht aus jedem Weg gleich aus (#1087 C1: ein Wert je Stelle) —
    vorher kam sie von hier mit dem rohen Wert und ohne Daumen und Datenguete."""
    import json
    url = server["url"]
    liste = json.loads(urllib.request.urlopen(url + "/api/jobs?active=true&limit=20", timeout=10).read())["jobs"]
    drin = next(j for j in liste if j["hash"] == "wg1")  # die Liste nennt die oeffentliche Kennung ohne Profilpraefix
    einzeln = json.loads(urllib.request.urlopen(f"{url}/api/jobs/wg1", timeout=10).read())
    assert "punkte" in drin, "die Liste liefert die Punkte (Ausgangslage)"
    for feld in ("punkte", "fach_score", "score", "unter_schwelle"):
        assert einzeln.get(feld) == drin.get(feld), feld
    assert "datenguete" in einzeln, "der Datenguete-Befund fehlte in der Einzelantwort"


# ── Quelltext-Waechter: die alten Sackgassen kommen nicht zurueck ───────────────────────

def _quelle(pfad: str) -> str:
    return (FRONTEND / pfad).read_text(encoding="utf-8")


def test_offen_zeile_nimmt_den_weg_aus_wege_js():
    q = _quelle("components/OffenBlock.jsx")
    assert "offenZeileZiel" in q
    assert 'return navigateTo?.("aufgaben");' not in q, "jede Zeile fuehrte nur auf die Aufgaben-Seite"


def test_nach_dem_speichern_wird_die_neue_bewerbung_geoeffnet():
    q = _quelle("pages/JobsPage.jsx")
    assert "zuBewerbung(erg?.id)" in q


def test_kontakt_dialog_zeigt_kein_rohes_ziel_mehr():
    q = _quelle("pages/ContactsPage.jsx")
    assert "{l.target_kind}" not in q, "die Verknuepfung zeigte „application“ roh"
    assert "data-kontakt-verknuepfungen" in q and "verknuepfungZeile" in q


def test_der_knoten_test_steht_in_der_ci():
    ci = (REPO / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "node frontend/src/lib/wege.test.mjs" in ci
    assert (FRONTEND / "lib" / "wege.test.mjs").is_file()


def test_jede_seite_mit_sprungzielen_versteht_die_neuen_absichten():
    """Ein Sprung, den die Zielseite nicht liest, landet still oben in der Liste (#1087 D6). Jede Absicht aus wege.js
    hat deshalb eine Seite, die sie auswertet."""
    absichten = {
        "oeffnen": "pages/JobsPage.jsx",
        "kontaktId": "pages/ContactsPage.jsx",
        "applicationId": "pages/ApplicationsPage.jsx",
        "firmaName": "pages/ContactsPage.jsx",
    }
    for absicht, seite in absichten.items():
        assert re.search(rf"intent\??\.{absicht}\b", _quelle(seite)), f"{seite} liest `{absicht}` nicht"
