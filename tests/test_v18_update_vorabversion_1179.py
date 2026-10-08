"""Update-Hinweis für Vorabversionen: ein Weg statt „Aktuell“ und kein Knopf (#1179, G89).

Der Nutzer (08.10.2026, Beta 17): „Funktioniert das Auto-Update schon? Ich habe auf ‚Mit einem Klick‘ gestellt, aber ich bekomme nichts zum
Klicken. Ich erwarte, dass ich im Dashboard oder in den Einstellungen irgendwo ‚Update‘ oder ‚installieren‘ sagen kann.“ Die Seitenleiste
nannte „Neue Version verfügbar: v1.8.0-beta.18“; die Update-Seite zeigte „Aktuell“ und keinen Knopf.

Ursache: zwei Auskünfte zur selben Frage. Die allgemeine Prüfung (`GET /api/update-check`) nennt einer Beta-Installation auch neuere Betas; die
feste Quelle des Auto-Updates (`GET /api/auto-update`) kennt nie eine Vorabversion — Vorabversionen werden nie von selbst installiert, und an einer
Beta hängt kein Update-Paket. Die Seitenleiste folgte der ersten, die Update-Seite der zweiten, und die Hinweiszone des Dashboards beiden nicht.

Geprüft wird im Browser gegen das gebaute Bundle (`cd frontend && pnpm exec vite build`, wenn sich das Frontend ändert). Die beiden Auskünfte
kommen aus Attrappen: eine echte GitHub-Veröffentlichung gibt es dafür nicht, und gefragt ist ja, was die Oberfläche aus den zwei Antworten
macht. GitHub selbst wird nie erreicht (die Knöpfe öffnen Adressen dorthin, die Attrappe antwortet). Die Regeln stehen in `lib/autoUpdate.js`
(Node-Test `autoUpdate.test.mjs`); hier: dass die Oberfläche sie auch BENUTZT (DoD 8c).
"""
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import threading
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import uvicorn

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend" / "src"

BETA = "1.8.0-beta.17"
NEUERE_BETA = "1.8.0-beta.18"
RELEASE_URL = f"https://github.com/MadGapun/PBP/releases/tag/v{NEUERE_BETA}"
ZIP_URL = f"https://github.com/MadGapun/PBP/archive/refs/tags/v{NEUERE_BETA}.zip"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("vorab1179")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp / "test.db")
    db.initialize()
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
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
    yield {"url": f"http://127.0.0.1:{port}"}
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


# ── Attrappen der beiden Auskünfte ────────────────────────────────────────────────────────────────────────────

def _au(laufend=BETA, aktuell=None, neu=None, neustart=False, stufe="hinweis"):
    """So sieht `GET /api/auto-update` einer installierten Fassung aus (Felder wie `lauf.uebersicht`)."""
    aktuell = aktuell or laufend
    return {
        "verfuegbar": True, "grund": "", "laufend": laufend, "stufe": stufe,
        "stufen": ["aus", "hinweis", "auto_meldung", "auto_still"], "vorgaenger_behalten": 3, "installer_aufraeumen": "fragen",
        "gefragt": True, "verlauf": [], "signatur": {"erforderlich": True, "schluessel": ["haupt", "notfall"]},
        "pruefung": {"status": "neu" if neu else "aktuell", "zeit": "2026-10-08T03:05:00+00:00", "text": ""},
        "job": None, "aktuell": aktuell, "installiert": [laufend], "neustart_noetig": neustart, "neu": neu,
        "blockiert": None, "rueckgang": None,
        "fassungen": [{"version": laufend, "bytes": 1_500_000, "laeuft": True, "aktuell": aktuell == laufend, "vorherige": False}],
    }


def _info(neueste=None, laufend=BETA, name=""):
    """So sieht `GET /api/update-check` aus; `neueste=None` heißt: nichts Neues."""
    daten = {
        "current_version": laufend, "latest_version": neueste or laufend, "update_available": bool(neueste),
        "release_url": f"https://github.com/MadGapun/PBP/releases/tag/v{neueste}" if neueste else None,
        "linie": "1.8", "stand": "geprueft", "quelle": "github-liste", "neue_linie": None, "wieder_fragen_nach_s": 3600,
        "geprueft_am": "2026-10-08T03:05:00+00:00", "quellen_versucht": [],
    }
    if neueste:
        daten["release_name"] = name or f"v{neueste}"
    return daten


# ── Browser ──────────────────────────────────────────────────────────────────────────────────────────────────

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


@pytest.fixture(scope="module")
def browser():
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(headless=True)
            yield b
            b.close()
    except PlaywrightError as exc:
        pytest.skip(f"Playwright/Chromium nicht verfuegbar: {exc}")


def _patchen(page, muster, aender):
    """Die echte Antwort holen und nur ändern, was die Lage braucht — der Rest bleibt, wie der Server ihn liefert."""
    def handler(route):
        antwort = route.fetch()
        daten = antwort.json()
        aender(daten)
        route.fulfill(response=antwort, json=daten)
    page.route(muster, handler)


def _seite(browser, umgebung, au, info, *, hash_="dashboard", ruhiges_dashboard=False, anfragen=None):
    """Öffnet das Dashboard mit den beiden Auskünften aus Attrappen. Gibt (Kontext, Seite) zurück."""
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    # Nie das echte GitHub erreichen: die Knöpfe öffnen Adressen dorthin.
    ctx.route("https://github.com/**", lambda r: r.fulfill(status=200, content_type="text/html", body="<title>Attrappe</title>"))
    page = ctx.new_page()

    def auto_update(route):
        if anfragen is not None:
            anfragen.append((route.request.method, route.request.url))
        if route.request.method == "GET":
            route.fulfill(json=au)
        else:
            route.fulfill(json=au)   # POST …/pruefen und …/einstellungen: die Antwort ist wieder die Übersicht
    page.route("**/api/auto-update", auto_update)
    page.route("**/api/auto-update/**", auto_update)

    def update_check(route):
        if anfragen is not None:
            anfragen.append((route.request.method, route.request.url))
        route.fulfill(json=info)
    page.route("**/api/update-check*", update_check)

    def status(d):
        d["version"] = au["laufend"]
        d["mcp_connection"] = {**(d.get("mcp_connection") or {}), "status": "connected", "version": au["laufend"]}
    _patchen(page, "**/api/status", status)
    if ruhiges_dashboard:
        # Damit vor dem Update-Hinweis nichts anderes steht: Quellen aktiv, die letzte Suche gestern.
        def workspace(d):
            d["sources"] = {**(d.get("sources") or {}), "active": 3}
        _patchen(page, "**/api/workspace-summary", workspace)

        def suche(d):
            d["last_search"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(timespec="seconds")
            d["status"] = "heute"
        _patchen(page, "**/api/search-status", suche)
    page.goto(f"{umgebung['url']}/#{hash_}", wait_until="load", timeout=30000)
    page.wait_for_function("t => !document.body.innerText.includes(t)", arg="wird vorbereitet", timeout=20000)
    return ctx, page


def _zu_den_updates(page):
    """Wie ein Mensch ohne die Meldung der Seitenleiste: Einstellungen, dann „Updates“ im Untermenü."""
    page.locator("button[data-page=einstellungen]").click()
    page.locator("nav").get_by_role("button", name="Updates", exact=True).click()
    page.locator("[data-updates-tab]").wait_for(timeout=15000)
    return page.locator("[data-updates-tab]")


def _neue_seite_nach(ctx, knopf):
    """Klickt `knopf` und gibt die Adresse der Seite zurück, die dadurch aufgeht."""
    with ctx.expect_page(timeout=15000) as neu:
        knopf.click()
    seite = neu.value
    seite.wait_for_load_state("domcontentloaded", timeout=15000)
    adresse = seite.url
    seite.close()
    return adresse


# ── der Fall des Nutzers: Beta 17, und Beta 18 ist erschienen ────────────────────────────────────────────────

def test_seitenleiste_und_update_seite_sagen_bei_einer_neueren_beta_dasselbe(browser, umgebung):
    ctx, page = _seite(browser, umgebung, _au(), _info(NEUERE_BETA))
    try:
        notiz = page.locator('[data-update-stand="neu"]')
        notiz.wait_for(timeout=15000)
        assert notiz.inner_text().strip() == f"Neue Vorabversion verfügbar: v{NEUERE_BETA}", "die Seitenleiste nennt es eine Vorabversion"
        notiz.click()
        tab = page.locator("[data-updates-tab]")
        tab.wait_for(timeout=45000)
        assert tab.get_by_text(f"Neue Vorabversion: v{NEUERE_BETA}", exact=True).count() == 1
        assert tab.get_by_text("Aktuell", exact=True).count() == 0, "„Aktuell“ widerspricht der Meldung der Seitenleiste"
        karte = page.locator("[data-updates-vorab]")
        karte.wait_for(timeout=5000)
        text = karte.inner_text()
        assert f"Vorabversion {NEUERE_BETA}" in text
        assert "nie von selbst" in text and "Mit einem Klick" in text, "sie sagt, warum es keinen Installieren-Knopf gibt"
        assert "INSTALLIEREN.bat" in text, "und nennt den Weg"
        assert karte.get_by_role("button", name="ZIP herunterladen").count() == 1
        assert karte.get_by_role("button", name="Veröffentlichung ansehen").count() == 1
        assert page.get_by_role("button", name="Jetzt installieren").count() == 0, "installiert wird eine Vorabversion nie von selbst"
    finally:
        ctx.close()


def test_die_knoepfe_fuehren_zum_zip_und_zur_veroeffentlichung(browser, umgebung):
    ctx, page = _seite(browser, umgebung, _au(), _info(NEUERE_BETA))
    try:
        page.locator('[data-update-stand="neu"]').click()
        karte = page.locator("[data-updates-vorab]")
        karte.wait_for(timeout=15000)
        assert _neue_seite_nach(ctx, karte.get_by_role("button", name="ZIP herunterladen")) == ZIP_URL
        assert _neue_seite_nach(ctx, karte.get_by_role("button", name="Veröffentlichung ansehen")) == RELEASE_URL
    finally:
        ctx.close()


def test_das_dashboard_nennt_die_vorabversion_in_der_hinweiszone(browser, umgebung):
    ctx, page = _seite(browser, umgebung, _au(), _info(NEUERE_BETA), ruhiges_dashboard=True)
    try:
        zone = page.locator('[data-hinweiszone="update-vorab"]')
        zone.wait_for(timeout=15000)
        text = zone.inner_text()
        assert f"Neue Vorabversion verfügbar: v{NEUERE_BETA}" in text
        assert "nie von selbst" in text and "INSTALLIEREN.bat" in text
        assert page.locator("[data-hinweiszone]").count() == 1, "höchstens EIN Hinweis"
        assert _neue_seite_nach(ctx, zone.get_by_role("button", name="ZIP herunterladen")) == ZIP_URL
        assert _neue_seite_nach(ctx, zone.get_by_role("button", name="Veröffentlichung ansehen")) == RELEASE_URL
    finally:
        ctx.close()


def test_dringenderes_steht_vor_der_vorabversion(browser, umgebung):
    """Ohne aktive Quellen steht der Hinweis zu den Quellen vorn — die Vorabversion drängt sich nicht vor."""
    ctx, page = _seite(browser, umgebung, _au(), _info(NEUERE_BETA), ruhiges_dashboard=False)
    try:
        page.locator("[data-hinweiszone]").first.wait_for(timeout=15000)
        assert page.locator('[data-hinweiszone="update-vorab"]').count() == 0
        assert page.locator("[data-hinweiszone]").count() == 1
    finally:
        ctx.close()


# ── nichts Neues, die fertige Version, schon installiert ────────────────────────────────────────────────────────

def test_ohne_neuere_version_steht_aktuell_und_nirgends_eine_meldung(browser, umgebung):
    ctx, page = _seite(browser, umgebung, _au(), _info(None), ruhiges_dashboard=True)
    try:
        page.locator("button[data-page=einstellungen]").wait_for(timeout=15000)
        assert page.locator('[data-update-stand="neu"]').count() == 0
        assert page.locator('[data-hinweiszone="update-vorab"]').count() == 0
        tab = _zu_den_updates(page)
        assert tab.get_by_text("Aktuell", exact=True).count() == 1
        assert page.locator("[data-updates-vorab]").count() == 0
    finally:
        ctx.close()


def test_eine_fertige_neue_version_wird_wie_bisher_angeboten(browser, umgebung):
    neu = {"version": "1.8.1", "status": "neu", "auszug": ["Etwas wurde besser."], "groesse": 2_500_000, "frage_faellig": False,
           "zurueckgenommen": False, "zeit": "2026-10-08T03:05:00+00:00", "text": ""}
    ctx, page = _seite(browser, umgebung, _au(laufend="1.8.0", neu=neu), _info("1.8.1", laufend="1.8.0"))
    try:
        notiz = page.locator('[data-update-stand="neu"]')
        notiz.wait_for(timeout=15000)
        assert notiz.inner_text().strip() == "Neue Version verfügbar: v1.8.1", "eine fertige Version ist keine Vorabversion"
        notiz.click()
        tab = page.locator("[data-updates-tab]")
        tab.wait_for(timeout=15000)
        assert tab.get_by_role("button", name="Jetzt installieren").count() == 1
        assert page.locator("[data-updates-vorab]").count() == 0
    finally:
        ctx.close()


def test_eine_von_hand_installierte_vorabversion_ist_kein_neues_update_mehr(browser, umgebung):
    """beta.18 ist per INSTALLIEREN.bat da und wartet nur auf den Neustart: nichts mehr zum Holen."""
    au = _au(laufend=BETA, aktuell=NEUERE_BETA, neustart=True)
    ctx, page = _seite(browser, umgebung, au, _info(NEUERE_BETA))
    try:
        page.locator("button[data-page=einstellungen]").wait_for(timeout=15000)
        assert page.locator('[data-update-stand="neu"]').count() == 0
        assert f"Neustart nötig für v{NEUERE_BETA}" in page.locator("[data-update-neustart]").inner_text()
        _zu_den_updates(page)
        assert page.locator("[data-updates-vorab]").count() == 0
    finally:
        ctx.close()


# ── „Jetzt prüfen“ fragt beide Auskünfte ───────────────────────────────────────────────────────────────────────

def test_jetzt_pruefen_fragt_die_feste_quelle_und_die_allgemeine_pruefung(browser, umgebung):
    anfragen: list = []
    ctx, page = _seite(browser, umgebung, _au(), _info(NEUERE_BETA), anfragen=anfragen)
    try:
        page.locator('[data-update-stand="neu"]').click()
        page.locator("[data-updates-tab]").wait_for(timeout=15000)
        anfragen.clear()
        page.get_by_role("button", name="Jetzt prüfen").click()
        # Die Attrappen laufen als Ereignisse der Seite: warten darf nur ÜBER die Seite (page.wait_for_timeout), nie mit
        # time.sleep — sonst bleiben ihre Anfragen unbeantwortet, und die Prüfung sähe nur, dass nichts ankam.
        for _ in range(75):
            if any(m == "POST" and u.endswith("/api/auto-update/pruefen") for m, u in anfragen) \
                    and any("/api/update-check" in u and "frisch=1" in u for _, u in anfragen):
                break
            page.wait_for_timeout(200)
        assert any(m == "POST" and u.endswith("/api/auto-update/pruefen") for m, u in anfragen), anfragen
        assert any("/api/update-check" in u and "frisch=1" in u for _, u in anfragen), \
            "sonst widersprechen sich die beiden Auskünfte bis zur nächsten Abfrage"
    finally:
        ctx.close()


# ── die Verdrahtung (ein Schutz zählt erst, wenn er aufgerufen wird) ──────────────────────────────────────────────

def _lesen(*teile):
    return FRONTEND.joinpath(*teile).read_text(encoding="utf-8-sig")


def test_die_oberflaeche_benutzt_die_regeln_an_allen_drei_orten():
    seite = _lesen("components", "UpdatesTab.jsx")
    assert "vorabNeu(au, updateInfo)" in seite and "data-updates-vorab" in seite
    assert "VORAB_ERKLAERUNG" in seite and "VORAB_SCHRITTE.map(" in seite, "Erklärung und Weg werden auch ausgegeben"
    assert 'refreshUpdateInfo?.()' in seite, "„Jetzt prüfen“ fragt auch die allgemeine Prüfung"
    leiste = _lesen("components", "Sidebar.jsx")
    assert leiste.count("istVorabversion(brand.updateVersion)") == 2, "beide Fassungen der Meldung (Knopf und Link)"
    dashboard = _lesen("pages", "DashboardPage.jsx")
    assert "vorab: vorabNeu(autoUpdate, updateInfo)" in dashboard
    zone = _lesen("lib", "hinweisZone.js")
    assert "vorab: lage.vorab" in zone and "vorabHinweis(lage.vorab)" in zone
    app = _lesen("App.jsx")
    assert "refreshUpdateInfo: () => setUpdateFrageNr(" in app


def test_die_regeln_gelten_auch_im_node_test():
    """`lib/autoUpdate.js` und `lib/hinweisZone.js` haben je einen Node-Test (in der CI ein eigener Schritt); er läuft hier mit, damit
    auch die Gegenprobe ihn kennt und eine Regel nicht unbemerkt kippt, weil keine Browser-Szene sie berührt."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node nicht verfuegbar")
    for datei in ("autoUpdate.test.mjs", "hinweisZone.test.mjs"):
        r = subprocess.run([node, str(FRONTEND / "lib" / datei)], capture_output=True, text=True, timeout=120,
                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        assert r.returncode == 0, (datei, r.stdout[-600:], r.stderr[-600:])


def test_die_hilfe_nennt_vorabversionen():
    hilfe = _lesen("lib", "hilfe.js")
    eintrag = hilfe[hilfe.index('q: "PBP bietet kein Update an"'):]
    eintrag = eintrag[:eintrag.index("},")]
    assert "Vorabversion" in eintrag and "nie von selbst" in eintrag and "INSTALLIEREN.bat" in eintrag
