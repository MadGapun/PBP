"""#1162: „Typ ändern“ in der Dokumentenansicht — im Browser gegen das gebaute Bundle, mit echtem Server und echter Datenbank.

Das Dokument wird ECHT umgestellt (`PUT /api/document/{id}/doc-type`); danach stimmen Anzeige und Datenbank. Die Auswahl der Typen
kommt vom Server (`GET /api/document-types`), die Namen sind deutsch, und die Verknüpfung mit der Bewerbung bleibt.

Gebaut wird mit `cd frontend && pnpm exec vite build`, wenn sich das Frontend ändert.
"""
from __future__ import annotations

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

REPO = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("doktyp1162")
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
    yield {"url": f"http://127.0.0.1:{port}", "db": db}
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


def _seite(browser, umgebung):
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    page = ctx.new_page()
    page.goto(f"{umgebung['url']}/#dokumente", wait_until="load", timeout=30000)
    page.get_by_text("Dokumente", exact=False).first.wait_for(timeout=20000)
    return ctx, page


def _neues_dokument(db, name, typ="sonstiges", app=None):
    return db.add_document({"filename": name, "doc_type": typ, "extracted_text": "Text des Dokuments.",
                            "linked_application_id": app})


def _aufklappen(page, name):
    karte = page.locator("[id^=dokument-]").filter(has_text=name).first
    karte.wait_for(timeout=15000)
    karte.get_by_text(name).first.click()
    return karte


def test_der_typ_laesst_sich_in_der_ansicht_aendern_und_die_verknuepfung_bleibt(browser, umgebung):
    db = umgebung["db"]
    bew = db.add_application({"company": "Musterfirma GmbH", "title": "Planer", "status": "beworben"})
    did = _neues_dokument(db, "antwort-1162.pdf", app=bew)
    ctx, page = _seite(browser, umgebung)
    try:
        karte = _aufklappen(page, "antwort-1162.pdf")
        feld = karte.locator("[data-doc-typ]")
        feld.wait_for(timeout=10000)
        assert "Falsch eingeordnet?" in feld.inner_text() and "Verknüpfung" in feld.inner_text()
        auswahl = feld.locator("button[role=combobox]")
        assert auswahl.inner_text().strip() == "Sonstiges"
        auswahl.click()
        optionen = page.get_by_role("option")
        optionen.first.wait_for(timeout=5000)
        namen = [o.strip() for o in optionen.all_inner_texts()]
        assert "Absage" in namen and "Lebenslauf-Vorlage" in namen, namen
        assert "vermittler_korrespondenz" not in namen, "deutsche Namen statt der Schluessel"
        page.get_by_role("option", name="Absage", exact=True).click()
        # echt umgestellt: die Datenbank sagt es, und die Anzeige folgt
        for _ in range(50):
            if db.get_document(did)["doc_type"] == "absage":
                break
            page.wait_for_timeout(200)
        doc = db.get_document(did)
        assert doc["doc_type"] == "absage"
        assert doc["linked_application_id"] == bew, "die Verknuepfung bleibt"
        page.get_by_text("Typ geändert: Absage").first.wait_for(timeout=10000)
        karte = page.locator("[id^=dokument-]").filter(has_text="antwort-1162.pdf").first
        karte.locator("[data-doc-typ] button[role=combobox]").wait_for(timeout=10000)
        assert karte.locator("[data-doc-typ] button[role=combobox]").inner_text().strip() == "Absage"
    finally:
        ctx.close()


def test_ein_alter_typ_ausserhalb_der_liste_bleibt_sichtbar(browser, umgebung):
    """Ein Bestandsdokument mit einem Typ, den die Auswahl nicht kennt (etwa `email`), zeigt ihn weiter — und laesst sich umstellen."""
    db = umgebung["db"]
    did = _neues_dokument(db, "altlast-1162.eml", typ="email")
    ctx, page = _seite(browser, umgebung)
    try:
        karte = _aufklappen(page, "altlast-1162.eml")
        auswahl = karte.locator("[data-doc-typ] button[role=combobox]")
        auswahl.wait_for(timeout=10000)
        assert auswahl.inner_text().strip() in ("email", "E-Mail (Eingang)", "E-Mail"), auswahl.inner_text()
        auswahl.click()
        page.get_by_role("option", name="Anfrage eines Recruiters", exact=True).click()
        for _ in range(50):
            if db.get_document(did)["doc_type"] == "recruiter_anfrage":
                break
            page.wait_for_timeout(200)
        assert db.get_document(did)["doc_type"] == "recruiter_anfrage"
    finally:
        ctx.close()


def test_die_ansicht_benutzt_den_dienst_und_die_namen_vom_server():
    seite = (REPO / "frontend" / "src" / "pages" / "DocumentsPage.jsx").read_text(encoding="utf-8-sig")
    assert '"/api/document-types"' in seite and "`/api/document/${doc.id}/doc-type`" in seite
    assert "data-doc-typ" in seite and "typName(doc.doc_type)" in seite
