"""#1179 Tester-Schalter, Oberfläche: der Schalter, die Ein-Klick-Karte und die Rückfrage — im Browser gegen das gebaute Bundle.

Die Regeln stehen in `lib/autoUpdate.js` (Node-Test); hier: dass die Oberfläche sie BENUTZT (DoD 8c) und dass nichts ohne Rückfrage
und ohne `vorabversion: true` zum Server geht. Die Antworten des Servers kommen aus Attrappen wie im ersten Teil (`test_v18_update_
vorabversion_1179.py`, dessen Fixtures und Attrappen hier mitbenutzt werden); GitHub selbst wird nie erreicht.

Gebaut wird mit `cd frontend && pnpm exec vite build`, wenn sich das Frontend ändert.
"""
from __future__ import annotations

import json

import pytest

pytest.importorskip("playwright.sync_api")

# Fixtures (umgebung, browser) und Attrappen des ersten Teils: nur die Hilfen, keine Testfunktionen (sonst liefen sie doppelt)
from test_v18_update_vorabversion_1179 import _au, _info, _seite, _zu_den_updates, browser, umgebung  # noqa: E402,F401

VORAB = "1.8.1-beta.1"
RELEASE_URL = f"https://github.com/MadGapun/PBP/releases/tag/v{VORAB}"
ZIP_URL = f"https://github.com/MadGapun/PBP/archive/refs/tags/v{VORAB}.zip"


def _au_vorab(*, schalter=True, bereit=True, neu=None, laufend="1.8.0"):
    """`GET /api/auto-update` einer stabilen Installation, mit oder ohne Tester-Schalter."""
    au = _au(laufend=laufend, neu=neu)
    au["vorabversionen"] = schalter
    au["vorab"] = ({"version": VORAB, "titel": f"PBP {VORAB}", "veroeffentlicht": "2026-10-12T08:00:00Z",
                    "auszug": ["Etwas wurde besser."], "groesse": 2_500_000, "bereit": bereit,
                    "url": RELEASE_URL, "zip": ZIP_URL, "blockiert": None} if schalter else None)
    return au


def _posts(page):
    """Alle POST-Aufrufe der Seite mit ihrem Inhalt — damit geprüft werden kann, WAS zum Server geht."""
    gesammelt = []

    def merken(anfrage):
        if anfrage.method == "POST":
            try:
                inhalt = json.loads(anfrage.post_data or "null")
            except ValueError:
                inhalt = anfrage.post_data
            gesammelt.append((anfrage.url.split("/api/", 1)[-1], inhalt))

    page.on("request", merken)
    return gesammelt


def _warten_auf(page, bedingung, versuche=75):
    for _ in range(versuche):
        if bedingung():
            return True
        page.wait_for_timeout(200)
    return bedingung()


def _dialog_text(page):
    dialog = page.get_by_role("dialog")
    dialog.wait_for(timeout=10000)
    return dialog.inner_text()


# ── der Schalter ──────────────────────────────────────────────────────────────────────────────────────────────

def test_der_schalter_steht_auf_der_update_seite_ist_aus_und_zeigt_keinen_installieren_knopf(browser, umgebung):
    ctx, page = _seite(browser, umgebung, _au_vorab(schalter=False), _info(None, laufend="1.8.0"))
    try:
        tab = _zu_den_updates(page)
        karte = tab.locator("[data-updates-vorabschalter]")
        karte.wait_for(timeout=10000)
        text = karte.inner_text()
        assert "Für Tester: Vorabversionen" in text and "(Vorgabe: aus)" in text
        assert "nie, auch nicht in den automatischen Stufen" in text and "Zurückschalten" in text
        assert karte.locator("input[data-vorab-schalter]").is_checked() is False
        assert page.get_by_role("button", name="Vorabversion installieren").count() == 0
    finally:
        ctx.close()


def test_einschalten_fragt_nach_und_schickt_dann_ein_echtes_ja(browser, umgebung):
    ctx, page = _seite(browser, umgebung, _au_vorab(schalter=False), _info(None, laufend="1.8.0"))
    try:
        posts = _posts(page)
        tab = _zu_den_updates(page)
        schalter = tab.locator("input[data-vorab-schalter]")
        schalter.click()
        text = _dialog_text(page)
        assert "von selbst installiert es sie nie" in text
        page.get_by_role("button", name="Abbrechen").click()
        page.wait_for_timeout(500)
        assert [p for p in posts if p[0] == "auto-update/einstellungen"] == [], "abgebrochen: nichts geht zum Server"
        schalter.click()
        _dialog_text(page)
        page.get_by_role("button", name="Einschalten", exact=True).click()
        assert _warten_auf(page, lambda: any(p[0] == "auto-update/einstellungen" for p in posts)), posts
        assert [p[1] for p in posts if p[0] == "auto-update/einstellungen"] == [{"vorabversionen": True}]
    finally:
        ctx.close()


def test_ausschalten_geht_ohne_rueckfrage(browser, umgebung):
    ctx, page = _seite(browser, umgebung, _au_vorab(schalter=True, bereit=False), _info(VORAB, laufend="1.8.0"))
    try:
        posts = _posts(page)
        tab = _zu_den_updates(page)
        schalter = tab.locator("input[data-vorab-schalter]")
        assert schalter.is_checked() is True
        schalter.click()
        assert _warten_auf(page, lambda: any(p[0] == "auto-update/einstellungen" for p in posts)), posts
        assert [p[1] for p in posts if p[0] == "auto-update/einstellungen"] == [{"vorabversionen": False}]
        assert page.get_by_role("dialog").count() == 0
    finally:
        ctx.close()


# ── die Ein-Klick-Karte ──────────────────────────────────────────────────────────────────────────────────────

def test_mit_schalter_und_paket_steht_ein_knopf_statt_der_zip_karte(browser, umgebung):
    ctx, page = _seite(browser, umgebung, _au_vorab(), _info(VORAB, laufend="1.8.0"))
    try:
        tab = _zu_den_updates(page)
        karte = tab.locator("[data-updates-vorab-klick]")
        karte.wait_for(timeout=10000)
        text = karte.inner_text()
        assert f"Vorabversion {VORAB}" in text and "Zum Ausprobieren" in text and "Etwas wurde besser." in text
        assert karte.get_by_role("button", name="Vorabversion installieren").count() == 1
        assert karte.get_by_role("button", name="Veröffentlichung ansehen").count() == 1
        assert tab.locator("[data-updates-vorab]").count() == 0, "der Klick-Weg ersetzt die ZIP-Karte, er steht nicht zusätzlich da"
        assert tab.get_by_text(f"Neue Vorabversion: v{VORAB}", exact=True).count() == 1
    finally:
        ctx.close()


def test_der_knopf_fragt_nach_und_schickt_vorabversion_true_mit(browser, umgebung):
    ctx, page = _seite(browser, umgebung, _au_vorab(), _info(VORAB, laufend="1.8.0"))
    try:
        posts = _posts(page)
        tab = _zu_den_updates(page)
        knopf = tab.locator("[data-updates-vorab-klick]").get_by_role("button", name="Vorabversion installieren")
        knopf.click()
        text = _dialog_text(page)
        assert VORAB in text and "Vorabversion zum Ausprobieren" in text and "Prüfsumme und Signatur" in text
        assert "Zurückschalten" in text
        page.get_by_role("button", name="Abbrechen").click()
        page.wait_for_timeout(500)
        assert [p for p in posts if p[0] == "auto-update/installieren"] == [], "ohne Ja geht nichts zum Server"
        knopf.click()
        _dialog_text(page)
        page.get_by_role("button", name="Installieren", exact=True).click()
        assert _warten_auf(page, lambda: any(p[0] == "auto-update/installieren" for p in posts)), posts
        assert [p[1] for p in posts if p[0] == "auto-update/installieren"] == [{"version": VORAB, "vorabversion": True}]
    finally:
        ctx.close()


def test_ohne_paket_bleibt_es_beim_zip_und_es_gibt_keinen_installieren_knopf(browser, umgebung):
    ctx, page = _seite(browser, umgebung, _au_vorab(bereit=False), _info(VORAB, laufend="1.8.0"))
    try:
        tab = _zu_den_updates(page)
        tab.locator("[data-updates-vorab]").wait_for(timeout=10000)
        assert tab.locator("[data-updates-vorab-klick]").count() == 0
        assert page.get_by_role("button", name="Vorabversion installieren").count() == 0
        assert tab.locator("[data-updates-vorab]").get_by_role("button", name="ZIP herunterladen").count() == 1
    finally:
        ctx.close()


def test_ohne_schalter_nennt_die_allgemeine_pruefung_nur_den_zip_weg(browser, umgebung):
    """Auch wenn die allgemeine Prüfung eine Vorabversion nennt (etwa, weil dies selbst eine Beta ist): ohne den Schalter
    gibt es keinen Installieren-Knopf."""
    ctx, page = _seite(browser, umgebung, _au_vorab(schalter=False, laufend="1.8.0-beta.17"),
                       _info(VORAB, laufend="1.8.0-beta.17"))
    try:
        tab = _zu_den_updates(page)
        tab.locator("[data-updates-vorab]").wait_for(timeout=10000)
        assert page.get_by_role("button", name="Vorabversion installieren").count() == 0
    finally:
        ctx.close()


def test_eine_fertige_version_geht_vor_und_die_vorabversion_steht_daneben(browser, umgebung):
    neu = {"version": "1.8.2", "status": "neu", "auszug": ["Ein Fehler wurde behoben."], "groesse": 2_400_000,
           "frage_faellig": False, "zurueckgenommen": False, "zeit": "2026-10-12T08:00:00+00:00", "text": ""}
    ctx, page = _seite(browser, umgebung, _au_vorab(neu=neu), _info("1.8.2", laufend="1.8.0"), ruhiges_dashboard=True)
    try:
        zone = page.locator("[data-hinweiszone]")
        zone.wait_for(timeout=15000)
        assert zone.get_attribute("data-hinweiszone") == "update", "auf dem Dashboard die fertige Version"
        tab = _zu_den_updates(page)
        assert tab.get_by_role("button", name="Jetzt installieren").count() == 1
        assert tab.get_by_role("button", name="Vorabversion installieren").count() == 1
    finally:
        ctx.close()


# ── Dashboard ──────────────────────────────────────────────────────────────────────────────────────────────────

def test_das_dashboard_bietet_die_vorabversion_mit_dem_knopf_an(browser, umgebung):
    ctx, page = _seite(browser, umgebung, _au_vorab(), _info(VORAB, laufend="1.8.0"), ruhiges_dashboard=True)
    try:
        posts = _posts(page)
        zone = page.locator('[data-hinweiszone="update-vorab-klick"]')
        zone.wait_for(timeout=15000)
        text = zone.inner_text()
        assert f"Neue Vorabversion verfügbar: v{VORAB}" in text and "Zum Ausprobieren" in text
        assert page.locator("[data-hinweiszone]").count() == 1, "höchstens EIN Hinweis"
        zone.get_by_role("button", name="Vorabversion installieren").click()
        _dialog_text(page)
        page.get_by_role("button", name="Installieren", exact=True).click()
        assert _warten_auf(page, lambda: any(p[0] == "auto-update/installieren" for p in posts)), posts
        assert [p[1] for p in posts if p[0] == "auto-update/installieren"] == [{"version": VORAB, "vorabversion": True}]
    finally:
        ctx.close()


def test_das_dashboard_zeigt_ohne_schalter_nie_einen_installieren_knopf(browser, umgebung):
    ctx, page = _seite(browser, umgebung, _au_vorab(schalter=False, laufend="1.8.0-beta.17"),
                       _info(VORAB, laufend="1.8.0-beta.17"), ruhiges_dashboard=True)
    try:
        zone = page.locator('[data-hinweiszone="update-vorab"]')
        zone.wait_for(timeout=15000)
        assert page.get_by_role("button", name="Vorabversion installieren").count() == 0
    finally:
        ctx.close()


# ── Verdrahtung ─────────────────────────────────────────────────────────────────────────────────────────────────

def _lesen(*teile):
    from pathlib import Path
    return (Path(__file__).resolve().parents[1] / "frontend" / "src").joinpath(*teile).read_text(encoding="utf-8-sig")


def test_die_oberflaeche_benutzt_den_klick_weg_und_fragt_vor_dem_installieren_nach():
    seite = _lesen("components", "UpdatesTab.jsx")
    assert "vorabKlick(au)" in seite and "data-updates-vorab-klick" in seite and "data-vorab-schalter" in seite
    assert "VORAB_EINSCHALTEN_FRAGE" in seite and "vorabversionen: an" in seite
    app = _lesen("App.jsx")
    assert "vorabInstallierenFrage(a.version)" in app and "vorabversion: true" in app
    assert app.index("vorabInstallierenFrage(a.version)") < app.index("vorabversion: true"), "erst fragen, dann senden"
    hilfe = _lesen("lib", "hilfe.js")
    eintrag = hilfe[hilfe.index('q: "PBP bietet kein Update an"'):]
    eintrag = eintrag[:eintrag.index("},")]
    assert "Vorabversionen anbieten" in eintrag and "von selbst installiert PBP sie auch dann nie" in eintrag
