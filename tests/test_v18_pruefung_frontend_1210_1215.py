"""#1210-#1215 und #1208 (Funde der unabhängigen Prüfung des Release-Zweigs, 14.10.2026): Dialog, Verlauf, Weg-Leiste, Pfad.

* #1210 — die Zurück-Taste bei geänderter Eingabe in einem Dialog fror die Seite ein (Endlosschleife in `nachPopstate`).
* #1211 — die Stellen-Seite kannte nur die 30 jüngsten Bewerbungen: „Zur Bewerbung“ fehlte für ältere.
* #1212 — der Stellen-Dialog aus einer Bewerbung bot „Bewerbung anlegen“ an und schloss nur den Dialog.
* #1213 — Escape bei offenem Menü der Weg-Leiste schloss den ganzen Dialog.
* #1214 — der Pfad oben verlor den Reiter der Einstellungen beim erneuten Klick auf die Seitenleiste.
* #1215 — nach einem Sprung aus einem Dialog blieb dessen Verlaufseintrag als toter Schritt liegen.

Im Browser, gegen das gebaute Bundle, bei 1366 × 768. Alle Firmen, Personen und Adressen sind erfunden. Die Daten kommen aus der
Umgebung von `test_v18_weg_leiste_1171` (eine Bewerbung mit Stelle und zwei Personen).
"""
from __future__ import annotations

import time

import pytest

pytest.importorskip("playwright.sync_api")

from test_v18_weg_leiste_1171 import (  # noqa: E402,F401  (die Fixtures kommen mit)
    FIRMA, KLEIN, TEXT, TITEL, _timeline, _warte, browser, umgebung,
)


def _bewerbungen(browser, umgebung):
    ctx = browser.new_context(viewport=KLEIN)
    page = ctx.new_page()
    page.set_default_timeout(15000)
    page.goto("about:blank")
    page.goto(f"{umgebung['url']}/#bewerbungen", wait_until="load", timeout=30000)
    page.locator("#page-bewerbungen").wait_for(timeout=20000)
    page.get_by_role("button", name="Timeline").first.wait_for(timeout=15000)
    return ctx, page


def _lebt(page) -> bool:
    """Antwortet die Seite noch? Eine Endlosschleife im Hauptthread laesst auch ein `1 + 1` nicht mehr durch."""
    try:
        return page.evaluate("1 + 1") == 2
    except Exception:
        return False


# ══ #1210 ════════════════════════════════════════════════════════════════════════════════════════

def test_1210_die_zurueck_taste_mit_geaenderter_eingabe_fragt_nach_und_haengt_nicht(browser, umgebung):
    ctx, page = _bewerbungen(browser, umgebung)
    try:
        page.get_by_role("button", name="Timeline").first.click()
        page.locator("[role=dialog]").wait_for(timeout=15000)
        page.get_by_placeholder("Notiz hinzufügen...").fill("Eine Notiz, die noch nicht gespeichert ist")
        page.go_back()
        assert _warte(lambda: page.locator("[data-verwerfen-frage]").count() == 1, sekunden=10), "die Rückfrage erscheint"
        assert _lebt(page), "die Seite antwortet noch"
        assert page.locator("[role=dialog]").count() == 1, "der Dialog bleibt offen"
        assert page.get_by_placeholder("Notiz hinzufügen...").input_value().startswith("Eine Notiz"), "die Eingabe ist noch da"
        # ein zweites Zurueck bei stehender Rueckfrage aendert nichts und haengt nicht
        page.go_back()
        page.wait_for_timeout(400)
        assert _lebt(page) and page.locator("[data-verwerfen-frage]").count() == 1 and page.locator("[role=dialog]").count() == 1
    finally:
        ctx.close()


def test_1210_verwerfen_schliesst_den_dialog_und_laesst_keinen_toten_schritt(browser, umgebung):
    ctx, page = _bewerbungen(browser, umgebung)
    try:
        page.get_by_role("button", name="Timeline").first.click()
        page.locator("[role=dialog]").wait_for(timeout=15000)
        page.get_by_placeholder("Notiz hinzufügen...").fill("Entwurf")
        page.go_back()
        page.locator("[data-verwerfen-frage]").wait_for(timeout=10000)
        page.locator("[data-verwerfen-frage]").get_by_role("button", name="Verwerfen").click()
        assert _warte(lambda: page.locator("[role=dialog]").count() == 0)
        page.wait_for_timeout(400)            # der Eintrag wird zeitversetzt zurückgenommen
        assert page.url.endswith("#bewerbungen") and _lebt(page)
        page.go_back()
        assert _warte(lambda: page.url == "about:blank"), f"der naechste Zurück-Schritt verlässt die Seite: {page.url}"
    finally:
        ctx.close()


def test_1210_weiter_bearbeiten_behaelt_dialog_und_eingabe_und_der_naechste_zurueck_fragt_wieder(browser, umgebung):
    ctx, page = _bewerbungen(browser, umgebung)
    try:
        page.get_by_role("button", name="Timeline").first.click()
        page.locator("[role=dialog]").wait_for(timeout=15000)
        page.get_by_placeholder("Notiz hinzufügen...").fill("Entwurf")
        page.go_back()
        page.locator("[data-verwerfen-frage]").wait_for(timeout=10000)
        page.locator("[data-verwerfen-frage]").get_by_role("button", name="Weiter bearbeiten").click()
        assert _warte(lambda: page.locator("[data-verwerfen-frage]").count() == 0)
        assert page.get_by_placeholder("Notiz hinzufügen...").input_value() == "Entwurf"
        page.go_back()
        assert _warte(lambda: page.locator("[data-verwerfen-frage]").count() == 1), "die Rückfrage kommt beim nächsten Zurück wieder"
        assert _lebt(page)
    finally:
        ctx.close()


def test_1210_ohne_eingabe_schliesst_zurueck_den_dialog_wie_vorher(browser, umgebung):
    ctx, page = _bewerbungen(browser, umgebung)
    try:
        page.get_by_role("button", name="Timeline").first.click()
        page.locator("[role=dialog]").wait_for(timeout=15000)
        page.go_back()
        assert _warte(lambda: page.locator("[role=dialog]").count() == 0)
        assert page.locator("[data-verwerfen-frage]").count() == 0
    finally:
        ctx.close()


# ══ #1211 ════════════════════════════════════════════════════════════════════════════════════════

def _viele_bewerbungen(umgebung):
    """35 Bewerbungen: die ÄLTESTE gehört zu `wlOLD`. `GET /api/applications` ohne Parameter lieferte die 30 jüngsten."""
    db = umgebung["db"]
    if umgebung.get("viele"):
        return
    jobs = [{"hash": "wlOLD", "title": "Konstrukteur Sondermaschinen (m/w/d)", "company": "Altwerk GmbH", "location": "Musterstadt",
             "url": "https://karriere.altwerk.example/jobs/1", "source": "manuell", "description": TEXT, "score": 12}]
    db.save_jobs(jobs)
    db.add_application({"title": "Konstrukteur Sondermaschinen (m/w/d)", "company": "Altwerk GmbH", "status": "beworben",
                        "job_hash": "wlOLD", "applied_at": "2026-01-05"})
    for i in range(34):
        db.add_application({"title": f"Projektleiter Anlagenbau {i} (m/w/d)", "company": f"Firma Nr. {i} GmbH", "status": "beworben",
                            "applied_at": f"2026-09-{1 + i % 28:02d}"})
    umgebung["viele"] = True


def test_1211_auch_eine_aeltere_bewerbung_zeigt_zur_bewerbung_in_der_leiste(browser, umgebung):
    _viele_bewerbungen(umgebung)
    import json
    import urllib.request
    erste = json.loads(urllib.request.urlopen(f"{umgebung['url']}/api/applications", timeout=15).read())
    assert erste["total"] >= 35 and len(erste["applications"]) == 30, "Vorbedingung: der Endpunkt ohne Parameter liefert nur 30"
    ctx = browser.new_context(viewport=KLEIN)
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#stellen/wlOLD", wait_until="load", timeout=30000)
        leiste = page.locator("[data-weg-leiste='stelle']")
        leiste.wait_for(timeout=20000)
        assert _warte(lambda: "Zur Bewerbung" in leiste.locator("[data-weg-haupt]").inner_text()), \
            leiste.locator("[data-weg-haupt]").inner_text()
        assert leiste.locator("[data-weg-fall='bewerbung']").count() == 1
        assert "Stelle bewerten" not in leiste.inner_text()
    finally:
        ctx.close()


# ══ #1212 ════════════════════════════════════════════════════════════════════════════════════════

def test_1212_die_stelle_aus_der_bewerbung_bietet_zur_bewerbung_an_und_fuehrt_dorthin_zurueck(browser, umgebung):
    ctx, page = _bewerbungen(browser, umgebung)
    try:
        page.locator("[data-karte-zur-stelle]").first.click()
        leiste = page.locator("[data-weg-leiste='stelle']")
        leiste.wait_for(timeout=15000)
        haupt = leiste.locator("[data-weg-haupt]")
        assert _warte(lambda: "Zur Bewerbung" in haupt.inner_text()), haupt.inner_text()
        assert "Bewerbung anlegen" not in leiste.inner_text(), "die Bewerbung gibt es: aus ihr ist der Dialog aufgegangen"
        haupt.click()
        assert _warte(lambda: page.locator("[role=dialog]").count() == 0), "der Dialog schliesst"
        assert page.locator("#page-bewerbungen").is_visible() and page.url.endswith("#bewerbungen")
    finally:
        ctx.close()


# ══ #1213 ════════════════════════════════════════════════════════════════════════════════════════

def test_1213_escape_schliesst_zuerst_das_menue_der_leiste_dann_den_dialog(browser, umgebung):
    ctx, page = _timeline(browser, umgebung)
    try:
        page.set_default_timeout(15000)
        schalter = page.locator("[data-weg-fall='kontakte'] button")
        schalter.click()
        menue = page.locator("[data-weg-menue='kontakte']")
        menue.wait_for(timeout=10000)
        page.keyboard.press("Escape")
        assert _warte(lambda: menue.count() == 0), "das Menü schliesst"
        assert page.locator("[role=dialog]").count() == 1, "der Dialog bleibt"
        assert schalter.evaluate("el => el === document.activeElement"), "der Fokus kehrt zum Auslöser zurück"
        page.keyboard.press("Escape")
        assert _warte(lambda: page.locator("[role=dialog]").count() == 0), "das zweite Escape schliesst den Dialog"
    finally:
        ctx.close()


def test_1213_weitere_wege_schliesst_ebenfalls_zuerst(browser, umgebung):
    """In Vorbereitung ohne Lebenslauf: Hauptknopf „Lebenslauf“, dahinter „Anschreiben“ unter „Weitere Wege“."""
    db, aid = umgebung["db"], umgebung["aid"]
    db.connect().execute("UPDATE applications SET status='in_vorbereitung' WHERE id=?", (aid,))
    db.connect().commit()
    try:
        ctx, page = _timeline(browser, umgebung)
        try:
            weitere = page.locator("[data-weg-weitere]")
            assert _warte(lambda: weitere.count() == 1), "die Lage hat weitere Wege"
            weitere.click()
            menue = page.locator("[data-weg-schritt] ul[role=menu]")
            menue.wait_for(timeout=10000)
            page.keyboard.press("Escape")
            assert _warte(lambda: menue.count() == 0), "das Menü schliesst"
            assert page.locator("[role=dialog]").count() == 1, "der Dialog bleibt"
            page.keyboard.press("Escape")
            assert _warte(lambda: page.locator("[role=dialog]").count() == 0)
        finally:
            ctx.close()
    finally:
        db.connect().execute("UPDATE applications SET status='interview' WHERE id=?", (aid,))
        db.connect().commit()


# ══ #1214 ════════════════════════════════════════════════════════════════════════════════════════

def test_1214_der_pfad_behaelt_den_reiter_beim_erneuten_klick_auf_die_seitenleiste(browser, umgebung):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#einstellungen", wait_until="load", timeout=30000)
        page.locator("[data-settings-reiter]").wait_for(timeout=20000)
        page.locator("[data-erweitert-schalter]").click()
        page.locator("[data-erweitert-reiter]").get_by_role("button", name="Updates", exact=True).click()
        assert _warte(lambda: "/Einstellungen/Updates" in page.locator("header").inner_text()), page.locator("header").inner_text()
        # derselbe Menüpunkt noch einmal
        page.locator("aside[aria-label='Hauptnavigation'] nav").get_by_role("link", name="Einstellungen").or_(
            page.locator("aside[aria-label='Hauptnavigation'] nav").get_by_role("button", name="Einstellungen")).first.click()
        page.wait_for_timeout(500)
        assert "/Einstellungen/Updates" in page.locator("header").inner_text(), page.locator("header").inner_text()
        assert page.locator("[data-erweitert-reiter]").get_by_role("button", name="Updates", exact=True) \
            .get_attribute("aria-pressed") == "true", "der Reiter selbst bleibt offen"
    finally:
        ctx.close()


def test_1214_ein_seitenwechsel_setzt_den_pfad_wie_bisher_zurueck(browser, umgebung):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    try:
        page.goto(f"{umgebung['url']}/#einstellungen", wait_until="load", timeout=30000)
        page.locator("[data-settings-reiter]").wait_for(timeout=20000)
        page.locator("[data-erweitert-schalter]").click()
        page.locator("[data-erweitert-reiter]").get_by_role("button", name="Updates", exact=True).click()
        assert _warte(lambda: "/Einstellungen/Updates" in page.locator("header").inner_text())
        nav = page.locator("aside[aria-label='Hauptnavigation'] nav")
        nav.get_by_role("link", name="Bewerbungen").or_(nav.get_by_role("button", name="Bewerbungen")).first.click()
        assert _warte(lambda: "/Bewerbungen" in page.locator("header").inner_text())
        assert "Updates" not in page.locator("header").inner_text()
    finally:
        ctx.close()


# ══ #1215 ════════════════════════════════════════════════════════════════════════════════════════

def test_1215_nach_einem_sprung_aus_dem_dialog_bleibt_kein_toter_schritt_im_verlauf(browser, umgebung):
    """Verlauf: leere Seite › Bewerbungen › (Timeline) › Stellen › Stellen-Dialog. Jeder Zurück-Schritt aendert etwas Sichtbares."""
    ctx, page = _bewerbungen(browser, umgebung)
    try:
        page.get_by_role("button", name="Timeline").first.click()
        page.locator("[role=dialog]").wait_for(timeout=15000)
        page.locator("[data-weg-fall='stelle'] button").first.click()
        assert _warte(lambda: "#stellen" in page.url and page.locator("[role=dialog]").count() == 1)
        page.wait_for_timeout(500)
        # 1: der Stellen-Dialog schliesst, die Stellen-Seite bleibt
        page.go_back()
        assert _warte(lambda: page.locator("[role=dialog]").count() == 0)
        assert "#stellen" in page.url and page.locator("#page-stellen").is_visible()
        # 2: die Bewerbungen - ohne Zwischenschritt (der Eintrag der Timeline ist zum Eintrag der Stellen geworden)
        page.go_back()
        assert _warte(lambda: page.url.endswith("#bewerbungen") and page.locator("#page-bewerbungen").is_visible())
        assert page.locator("[role=dialog]").count() == 0
        # 3: die leere Seite davor
        page.go_back()
        assert _warte(lambda: page.url == "about:blank"), f"ein toter Schritt: {page.url}"
    finally:
        ctx.close()


def test_1215_ein_dialog_ohne_sprung_nimmt_seinen_eintrag_weiter_selbst_zurueck(browser, umgebung):
    ctx, page = _bewerbungen(browser, umgebung)
    try:
        page.get_by_role("button", name="Timeline").first.click()
        page.locator("[role=dialog]").wait_for(timeout=15000)
        page.locator("[data-modal-schliessen]").click()
        assert _warte(lambda: page.locator("[role=dialog]").count() == 0)
        page.wait_for_timeout(400)
        page.go_back()
        assert _warte(lambda: page.url == "about:blank")
    finally:
        ctx.close()
