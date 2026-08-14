#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generiert Dashboard-Screenshots mit den Musterprofilen für die Doku.

Die Demo-Daten kommen vollständig aus dem Seed-Modul `musterprofile.py`
(Baustelle 7, #840) — Bob Mustermann und Anna Beispiel, beide rein fiktiv.
Die Screenshots zeigen das aktive Profil (Bob).

Verwendung:
    python docs/screenshots/generate_screenshots.py

Voraussetzungen:
    pip install playwright pillow
    playwright install chromium

Harte Regeln (Baustelle 2, #841):
    - Dateinamen/Pfade unter docs/screenshots/ bleiben stabil — sie werden
      extern per raw-URL eingebunden. Neue Ansichten bekommen NEUE Dateien.
    - Heller Modus, 1280 px Breite, keine Browser-Chrome-Leiste.
    - Alle PNGs unter 200 KB (Palette-Optimierung unten).
    - Nur Musterdaten; die Temp-DB liegt nie im echten Datenverzeichnis.
"""

import os
import sys
import time
import threading
import tempfile
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bewerbungs_assistent.database import Database

import musterprofile


SCREENSHOT_DIR = Path(__file__).resolve().parent
WEB_DIR = SCREENSHOT_DIR.parent / "assets" / "web"
PORT = 8299  # Separate port to avoid conflicts
MAX_KB = 200
WEB_WIDTH = 800


def _start_dashboard(db_path: str, port: int):
    """Startet das Dashboard als Hintergrund-Thread.

    start_dashboard() ruft selbst uvicorn.run() auf und blockiert — deshalb
    laeuft dieser Aufruf im Daemon-Thread.
    """
    os.environ["BA_DATA_DIR"] = str(Path(db_path).parent)
    os.environ["BA_DASHBOARD_PORT"] = str(port)
    # Hints aus lokalem Repo laden statt von GitHub-main, damit Screenshots
    # immer den Stand der aktuellen Branch zeigen.
    os.environ["PBP_HINTS_URL"] = str(
        Path(__file__).resolve().parent.parent.parent / "hints.json"
    )

    from bewerbungs_assistent.dashboard import start_dashboard
    start_dashboard(Database(db_path=db_path), port=port)


def _dismiss_toasts(page):
    """Entfernt Toast-Benachrichtigungen vor dem Screenshot."""
    for _ in range(5):
        try:
            close_btns = page.locator("[class*='toast'] button, [class*='Toast'] button, [role='alert'] button")
            if close_btns.count() > 0:
                for i in range(close_btns.count()):
                    close_btns.nth(i).click(timeout=500)
                time.sleep(0.3)
        except Exception:
            pass
    page.evaluate("""
        document.querySelectorAll('[class*="toast"], [class*="Toast"], [role="alert"], [role="status"]')
            .forEach(el => el.remove());
    """)
    time.sleep(0.3)


def _screenshot(page, url, output_path, desc):
    """Navigiert zu URL und macht einen Screenshot."""
    page.goto(url)
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    _dismiss_toasts(page)
    page.screenshot(path=str(output_path), full_page=False)
    print(f"  Screenshot: {output_path.name} ({desc})")


def _new_page(browser):
    """Einheitliches Fenster: 1280x900, heller Modus erzwungen."""
    return browser.new_page(
        viewport={"width": 1280, "height": 900},
        color_scheme="light",
    )


def _open_aufgaben_tab(page, base):
    """Oeffnet den Aufgaben-Tab ueber die Sidebar.

    Hintergrund: `#aufgaben` fehlt in PAGE_IDS (frontend/src/utils.js),
    ein Deep-Link faellt deshalb aufs Dashboard zurueck (siehe Issue zur
    PAGE_IDS-Luecke). Der Sidebar-Klick nutzt den internen navigateTo-Pfad
    und funktioniert.
    """
    page.goto(f"{base}#dashboard")
    page.wait_for_load_state("networkidle")
    time.sleep(2)
    _dismiss_toasts(page)

    def _auf_aufgaben_seite():
        text = page.evaluate("document.body.innerText")
        return "Gehaltsdurchschnitt" not in text and "Aufgaben" in text

    versuche = [
        lambda: page.locator("text=Zu den Aufgaben").first.click(timeout=2000),
        lambda: page.get_by_role("button", name="Aufgaben", exact=True).first.click(timeout=2000),
        lambda: page.get_by_role("link", name="Aufgaben", exact=True).first.click(timeout=2000),
        lambda: page.locator("aside").first.get_by_text("Aufgaben", exact=True).first.click(timeout=2000),
    ]
    for versuch in versuche:
        try:
            # 2-Klick-Bug (PAGE_IDS ohne 'aufgaben', vgl. beta.21-Kommentar in
            # utils.js): der erste Klick setzt den Hash, der hashchange-Listener
            # verwirft 'aufgaben' und faellt aufs Dashboard zurueck; erst der
            # zweite Klick bleibt stabil. Deshalb bewusst zweimal klicken.
            versuch()
            time.sleep(1)
            try:
                versuch()
            except Exception:
                pass
            time.sleep(2)
            if _auf_aufgaben_seite():
                return True
        except Exception:
            continue
    return False


def _take_screenshots(port: int, output_dir: Path):
    """Nimmt Screenshots aller Dashboard-Tabs (aktives Profil: Bob)."""
    from playwright.sync_api import sync_playwright

    base = f"http://127.0.0.1:{port}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = _new_page(browser)

        tabs = [
            ("dashboard", "01_dashboard.png", "Dashboard-Übersicht"),
            ("profil", "02_profil.png", "Profil-Tab"),
            ("stellen", "03_stellen.png", "Stellen-Tab"),
            ("bewerbungen", "04_bewerbungen.png", "Bewerbungen-Tab"),
            ("kontakte", "04c_kontakte.png", "Kontakte-Tab"),
            ("dokumente", "05_dokumente.png", "Dokumente-Tab"),
            ("kalender", "06_kalender.png", "Kalender-Tab"),
            ("statistiken", "07_statistiken.png", "Statistiken-Tab"),
            ("einstellungen", "08_einstellungen.png", "Einstellungen-Tab"),
        ]

        for hash_id, filename, desc in tabs:
            _screenshot(page, f"{base}#{hash_id}", output_dir / filename, desc)

        # Aufgaben-Tab (v1.7.12) — NEUE Datei, Navigation per Sidebar-Klick.
        print("  Erstelle Aufgaben-Screenshot...")
        if _open_aufgaben_tab(page, base):
            _dismiss_toasts(page)
            page.screenshot(path=str(output_dir / "05b_aufgaben.png"), full_page=False)
            print("  Screenshot: 05b_aufgaben.png (Aufgaben-Tab)")
        else:
            print("  WARNUNG: Aufgaben-Tab nicht erreichbar — Screenshot uebersprungen.")

        # Dossier-Screenshot: Klick auf Bewerbungstitel oeffnet Timeline-Modal
        print("  Erstelle Dossier-Screenshot...")
        page.goto(f"{base}#bewerbungen")
        page.wait_for_load_state("networkidle")
        time.sleep(2)
        _dismiss_toasts(page)
        titles = page.locator("h3.cursor-pointer").all()
        if titles:
            titles[0].click()
            time.sleep(3)
            _dismiss_toasts(page)
        page.screenshot(path=str(output_dir / "04b_dossier.png"), full_page=False)
        print("  Screenshot: 04b_dossier.png (Bewerbungs-Dossier)")

        # Einstellungen Datenschutz-Tab Screenshot
        print("  Erstelle Datenschutz-Screenshot...")
        page.goto(f"{base}#einstellungen")
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        tabs_btns = page.locator("button").all()
        for btn in tabs_btns:
            if "Datenschutz" in (btn.text_content() or ""):
                btn.click()
                break
        time.sleep(1)
        _dismiss_toasts(page)
        page.screenshot(path=str(output_dir / "08b_datenschutz.png"), full_page=False)
        print("  Screenshot: 08b_datenschutz.png (Einstellungen-Datenschutz)")

        browser.close()


def _take_onboarding_screenshots(port: int, output_dir: Path, db_path: str):
    """Nimmt Screenshots fuer die Onboarding-Zustaende."""
    from playwright.sync_api import sync_playwright

    base = f"http://127.0.0.1:{port}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = _new_page(browser)

        # --- Phase 1: Leere DB = Willkommensbildschirm ---
        print("\n  Phase 1: Neuer User (kein Profil)")
        _screenshot(page, f"{base}#dashboard",
                    output_dir / "00_willkommen.png",
                    "Willkommen — erster Start")

        # --- Phase 2: Profil unvollstaendig (nur Name, keine Skills/Positionen) ---
        print("  Phase 2: Profil unvollstaendig")
        db = Database(db_path=db_path)
        db.initialize()
        minimal_pid = db.create_profile("Anna Beispiel", "anna.beispiel@example.org")
        db.save_profile({"name": "Anna Beispiel",
                         "email": "anna.beispiel@example.org", "summary": ""})
        db.close()
        time.sleep(0.5)

        _screenshot(page, f"{base}#dashboard",
                    output_dir / "00b_profil_unvollstaendig.png",
                    "Dashboard — Profil unvollständig")

        # --- Phase 3: Musterprofile in voller Tiefe (aktiv: Bob) ---
        print("  Phase 3: Musterprofile Bob + Anna (Seed-Modul)")
        db = Database(db_path=db_path)
        db.initialize()
        db.delete_profile(minimal_pid)      # Platzhalter-Anna raus
        musterprofile.seed_all(db)          # Anna komplett + Bob komplett (aktiv)
        db.close()
        time.sleep(0.5)

        _screenshot(page, f"{base}#dashboard",
                    output_dir / "00c_dashboard_vollstaendig.png",
                    "Dashboard — Profil vollständig, aktive Bewerbungen")

        browser.close()


def _optimize_png(path: Path, max_kb: int = MAX_KB):
    """Drueckt ein PNG per Palette-Quantisierung unter max_kb."""
    from PIL import Image

    size_kb = path.stat().st_size / 1024
    if size_kb <= max_kb:
        return size_kb, size_kb
    img = Image.open(path).convert("RGB")
    for colors in (256, 192, 128, 96, 64):
        quant = img.quantize(colors=colors, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG)
        quant.save(path, optimize=True)
        new_kb = path.stat().st_size / 1024
        if new_kb <= max_kb:
            return size_kb, new_kb
    return size_kb, path.stat().st_size / 1024


def _export_web_copy(path: Path, web_dir: Path = WEB_DIR, width: int = WEB_WIDTH):
    """Legt eine webtaugliche Kopie (Baustelle 6) unter docs/assets/web/ ab."""
    from PIL import Image

    web_dir.mkdir(parents=True, exist_ok=True)
    img = Image.open(path).convert("RGB")
    ratio = width / img.width
    small = img.resize((width, int(img.height * ratio)), Image.LANCZOS)
    target = web_dir / path.name
    small.quantize(colors=256, method=Image.MEDIANCUT, dither=Image.FLOYDSTEINBERG).save(
        target, optimize=True
    )
    return target


def main():
    print("PBP Screenshot-Generator (Musterprofile Bob & Anna)")
    print("=" * 52)

    # Temp-DB — startet LEER fuer Onboarding-Screenshots
    tmp_dir = tempfile.mkdtemp(prefix="pbp_screenshots_")
    db_path = os.path.join(tmp_dir, "pbp.db")

    print(f"1. Erstelle leere Datenbank: {db_path}")
    db = Database(db_path=db_path)
    db.initialize()
    # QA-Isolations-Regel: niemals gegen die echte User-DB arbeiten.
    assert tmp_dir in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    musterprofile.assert_isolated(db)
    db.close()

    # Dashboard starten
    print(f"2. Starte Dashboard auf Port {PORT}...")
    server_thread = threading.Thread(
        target=_start_dashboard,
        args=(db_path, PORT),
        daemon=True,
    )
    server_thread.start()
    time.sleep(3)  # Wait for server startup

    # Onboarding-Screenshots (leer -> unvollstaendig -> vollstaendig)
    print("3. Erstelle Onboarding-Screenshots (3 Zustaende)...")
    _take_onboarding_screenshots(PORT, SCREENSHOT_DIR, db_path)

    # Vollstaendige Tab-Screenshots (aktives Profil: Bob)
    print("4. Erstelle Tab-Screenshots...")
    _take_screenshots(PORT, SCREENSHOT_DIR)

    # Groessen-Optimierung + webtaugliche Kopien
    print(f"5. Optimiere PNGs (< {MAX_KB} KB) und lege Web-Kopien ab...")
    for f in sorted(SCREENSHOT_DIR.glob("*.png")):
        vorher, nachher = _optimize_png(f)
        _export_web_copy(f)
        marker = "" if nachher <= MAX_KB else "  << NOCH ZU GROSS"
        print(f"  {f.name}: {vorher:.0f} KB -> {nachher:.0f} KB{marker}")

    print(f"\nFertig! Screenshots in: {SCREENSHOT_DIR}")
    print(f"Web-Kopien in: {WEB_DIR}")


if __name__ == "__main__":
    main()
