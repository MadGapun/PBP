"""Globale Suche: ein Klick auf einen Treffer OEFFNET das Objekt (#1177, G88).

Der Nutzer (07.10.2026, Beta 17): „Wenn ich in PBP was suche, kommt schon mal eine ganze Reihe Vorschlaege. Aber wenn ich da auf
was klicke, passiert nichts. Ich erwarte eigentlich, dass sich das Objekt dann auch oeffnet.“

Ursache: `/api/search` lieferte die Zieladresse im Format `#bewerbungen?id=<id>`; das Dashboard liest seit H31 (#1087 G13) nur
`#seite/kennung` und faellt bei allem anderen auf das Dashboard zurueck. Dazu setzte der Klick nur `window.location.hash`
(bei gleicher Adresse passiert dann nichts), und Dokumente, Kalender und Profil nahmen keinen Sprung mit Kennung entgegen.

Geprueft wird hier der ganze Weg, nicht nur ein Teil: die Adressen im Server, und im Browser gegen das gebaute Bundle jede
Trefferart mit echtem Klick (`cd frontend && pnpm exec vite build`, wenn sich das Frontend aendert). Die Zuordnung Treffer → Ziel
(`lib/wege.js`) hat ihren eigenen Node-Test (`wege.test.mjs`).
"""
from __future__ import annotations

import os
import re
import socket
import threading
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

import pytest
import uvicorn

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend" / "src"
WORT = "Zebrafink"          # kommt in jeder Trefferart genau einmal mit eigenem Titel vor
TEXT = ("Wir suchen eine Sachbearbeitung im Einkauf. Aufgaben: Disposition, Bestellabwicklung mit SAP MM, "
        "Lieferantenkommunikation. Anforderungen: kaufmaennische Ausbildung, Englisch. ") * 3


def _tag(tage: int) -> str:
    return (date.today() + timedelta(days=tage)).isoformat()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("suche1177")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp / "test.db")
    db.initialize()
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    db.save_jobs([{"hash": "zf1", "title": f"Sachbearbeitung {WORT}", "company": "Musterbetrieb GmbH",
                   "url": "https://example.com/zf1", "source": "manuell", "description": TEXT, "remote_level": "hybrid",
                   "location": "Hamburg", "score": 8}])
    db.save_jobs([{"hash": "zf2", "title": f"Disponent {WORT} aussortiert", "company": "Beispiel AG", "url": "https://example.com/zf2",
                   "source": "manuell", "description": TEXT, "remote_level": "onsite", "location": "Hannover", "score": 4}])
    db.dismiss_job("zf2", "sonstiges")           # wie in der Trefferliste des Nutzers: „(aussortiert)“
    app = db.add_application({"title": f"Konstrukteur {WORT}", "company": "Beispiel AG", "status": "beworben",
                              "applied_at": _tag(-10)})
    ohne_app = db.add_meeting({"title": f"Termin {WORT} privat", "meeting_date": f"{_tag(9)}T14:00"})
    mit_app = db.add_meeting({"application_id": app, "title": f"Gespräch {WORT}", "meeting_date": f"{_tag(5)}T10:00"})
    mail_mit = db.add_email({"application_id": app, "filename": "m1.eml", "subject": f"Einladung {WORT}",
                             "sender": "hr@example.com", "body_text": "Wir freuen uns auf das Gespraech"})
    mail_ohne = db.add_email({"application_id": None, "filename": "m2.eml", "subject": f"Anfrage {WORT}",
                              "sender": "info@example.com", "body_text": "Eine Anfrage ohne Bewerbung"})
    # das Dokument entsteht ZUERST: mit 30 neueren davor steht es auf Seite 2 der Dokumente-Liste (25 je Seite)
    dokument = db.add_document({"filename": f"{WORT}-Lebenslauf.docx", "filepath": "x.docx", "doc_type": "lebenslauf",
                                "extracted_text": "Lebenslauf von Erika Musterfrau"})
    for i in range(30):
        db.add_document({"filename": f"Allerlei {i:02d}.docx", "filepath": "x.docx", "doc_type": "sonstiges"})
    # sieben Skills dazu: ab sieben zeigt die Profil-Seite ihr Filterfeld
    for i in range(7):
        db.add_skill({"name": f"Fertigkeit {i}", "category": "technical", "level": 3})
    db.add_skill({"name": f"{WORT}-Zucht", "category": "technical", "level": 4})
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
    yield {"url": f"http://127.0.0.1:{port}", "db": db, "app": app, "mit_app": mit_app, "ohne_app": ohne_app,
           "mail_mit": mail_mit, "mail_ohne": mail_ohne, "dokument": dokument}
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


# ── Server: die Adressen ────────────────────────────────────────────────────────────────

def _treffer(umgebung) -> dict:
    """Alle Treffer zu WORT, nach Art. Ruft den Server wirklich auf (kein Blick in den Quelltext)."""
    antwort = urllib.request.urlopen(f"{umgebung['url']}/api/search?q={WORT.lower()}&limit=20", timeout=10).read()
    import json
    daten = json.loads(antwort)
    assert daten["nicht_lesbar"] == [], daten
    return {g["kind"]: g["items"] for g in daten["groups"]}


def test_jede_trefferart_ist_da(umgebung):
    t = _treffer(umgebung)
    assert set(t) == {"application", "job", "skill", "document", "email", "meeting"}, sorted(t)
    assert len(t["email"]) == 2 and len(t["meeting"]) == 2 and len(t["job"]) == 2


def test_die_adressen_haben_die_form_die_das_dashboard_liest(umgebung):
    """`#seite/kennung` — die Form, die `parseHashZiel` liest. Das fruehere `#bewerbungen?id=…` war keine Seite."""
    from bewerbungs_assistent.services import dashboard_link
    muster = re.compile(r"^#([a-z]+)/([^/?#]+)$")
    for art, eintraege in _treffer(umgebung).items():
        for e in eintraege:
            if not e["url"]:
                assert art == "email", e   # eine Mail hat ihr Fenster, aber keine Adresse im Hash: sie oeffnet sich ueber Art und Kennung
                continue
            m = muster.match(e["url"])
            assert m, f"{art}: {e['url']!r} ist nicht von der Form #seite/kennung"
            assert m.group(1) in dashboard_link.REITER, e["url"]
            assert "?" not in e["url"]


def test_die_adressen_zeigen_auf_das_richtige_objekt(umgebung):
    u = umgebung
    t = _treffer(u)
    assert t["application"][0]["url"] == f"#bewerbungen/{u['app']}"
    # die Stelle traegt die OEFFENTLICHE Kennung — die der Stellenliste, ohne Profil-Praefix
    stelle = next(j for j in t["job"] if j["id"] == "zf1")
    assert ":" not in stelle["id"] and stelle["url"] == "#stellen/zf1"
    assert all(":" not in j["id"] for j in t["job"]), "auch die aussortierte Stelle traegt die oeffentliche Kennung"
    assert t["document"][0]["url"] == f"#dokumente/{u['dokument']}"
    assert t["skill"][0]["url"] == "#profil/skills"
    mit = next(m for m in t["meeting"] if m["id"] == u["mit_app"])
    ohne = next(m for m in t["meeting"] if m["id"] == u["ohne_app"])
    assert mit["application_id"] == u["app"] and mit["url"] == f"#bewerbungen/{u['app']}"
    assert ohne["application_id"] == "" and ohne["url"] == f"#kalender/{u['ohne_app']}"
    assert {m["id"] for m in t["email"]} == {u["mail_mit"], u["mail_ohne"]}, "beide Mails, mit und ohne Bewerbung"
    assert all(m["url"] == "" for m in t["email"])


def test_hash_ziel_ist_die_eine_form_fuer_links_und_treffer():
    from bewerbungs_assistent.services import dashboard_link as dl
    assert dl.hash_ziel("bewerbungen", "abc123") == "#bewerbungen/abc123"
    assert dl.hash_ziel("stellen", "profil1:hash9") == "#stellen/hash9", "das Profil-Praefix faellt weg"
    assert dl.hash_ziel("kalender") == "#kalender"
    assert dl.hash_ziel("dokumente", "a/b") == "#dokumente/a%2Fb", "ein Schraegstrich in der Kennung wird kodiert, sonst waere es ein zweiter Teil"
    with pytest.raises(ValueError):
        dl.hash_ziel("gibtsnicht", "x")
    # der Link fuer Claude ist derselbe Hash mit Rechner davor
    assert dl.dashboard_link("bewerbungen", "abc123") == dl.basis() + "/" + dl.hash_ziel("bewerbungen", "abc123")


def test_ein_dokument_laesst_sich_per_kennung_holen(umgebung):
    import json
    u = umgebung
    eins = json.loads(urllib.request.urlopen(f"{u['url']}/api/documents?doc_id={u['dokument']}&per_page=1", timeout=10).read())
    assert [d["id"] for d in eins["documents"]] == [u["dokument"]]
    assert eins["documents"][0]["filename"] == f"{WORT}-Lebenslauf.docx"
    keins = json.loads(urllib.request.urlopen(f"{u['url']}/api/documents?doc_id=gibt-es-nicht", timeout=10).read())
    assert keins["documents"] == []


# ── Browser: jede Trefferart mit echtem Klick ───────────────────────────────────────────

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


def _seite(browser, url, hash_):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.goto(f"{url}/#{hash_}", wait_until="load", timeout=30000)
    page.wait_for_function("t => !document.body.innerText.includes(t)", arg="wird vorbereitet", timeout=20000)
    return page


def _suche_oeffnen(page, wort=WORT):
    feld = page.locator("[data-globale-suche] input[type=search]")
    feld.fill(wort)
    page.locator("[data-suchergebnisse]").wait_for(timeout=15000)
    return feld


def _klick_auf_treffer(page, titel):
    _suche_oeffnen(page)
    page.locator("[data-suchergebnisse] button", has_text=titel).first.click()


def _dialog_titel(page, erwartet, frist=15000):
    page.wait_for_function(
        """erwartet => { const d = [...document.querySelectorAll('[role=dialog]')]; if (!d.length) return false;
           const t = d[d.length - 1].querySelector('h2,h3'); return !!t && t.innerText.startsWith(erwartet); }""",
        arg=erwartet, timeout=frist)
    return page.evaluate("""() => { const d = [...document.querySelectorAll('[role=dialog]')]; return d[d.length - 1].querySelector('h2,h3').innerText; }""")


def _dialog_zeigt(page, text, frist=15000):
    page.wait_for_function(
        """t => { const d = [...document.querySelectorAll('[role=dialog]')]; return d.length > 0 && d[d.length - 1].innerText.includes(t); }""",
        arg=text, timeout=frist)


def _im_dialogkoerper(page, abschnitt, frist=15000):
    """Der Abschnitt der Timeline liegt im SICHTBAREN Teil des Dialoginhalts, und der Inhalt wurde dafuer gescrollt."""
    page.wait_for_function(
        """k => { const a = document.querySelector(`[data-abschnitt="${k}"]`); const b = document.querySelector('[data-modal-koerper]');
           if (!a || !b) return false; const r = a.getBoundingClientRect(), s = b.getBoundingClientRect();
           return b.scrollTop > 100 && r.top >= s.top - 1 && r.top < s.bottom - 40; }""",
        arg=abschnitt, timeout=frist)


def test_nach_dem_klick_ist_die_liste_zu_und_das_feld_leer(browser, umgebung):
    page = _seite(browser, umgebung["url"], "dashboard")
    try:
        feld = _suche_oeffnen(page)
        page.locator("[data-suchergebnisse] button", has_text=f"Konstrukteur {WORT}").first.click()
        _dialog_titel(page, "Timeline")
        assert page.locator("[data-suchergebnisse]").count() == 0, "die Trefferliste bleibt nicht stehen"
        assert feld.input_value() == ""
    finally:
        page.close()


def test_bewerbung_oeffnet_ihre_timeline(browser, umgebung):
    page = _seite(browser, umgebung["url"], "dashboard")
    try:
        _klick_auf_treffer(page, f"Konstrukteur {WORT}")
        assert _dialog_titel(page, "Timeline").endswith(f"Konstrukteur {WORT}")
    finally:
        page.close()


def test_auch_auf_der_zielseite_oeffnet_sich_das_objekt_jedes_mal(browser, umgebung):
    """Die Adresse stand schon so da — vorher passierte dann gar nichts. Zweimal hintereinander, auf der Seite selbst."""
    page = _seite(browser, umgebung["url"], "bewerbungen")
    try:
        for _ in range(2):
            _klick_auf_treffer(page, f"Konstrukteur {WORT}")
            assert _dialog_titel(page, "Timeline").endswith(f"Konstrukteur {WORT}")
            page.get_by_role("dialog").get_by_role("button", name="Schließen").last.click()
            page.wait_for_function("() => document.querySelectorAll('[role=dialog]').length === 0", timeout=10000)
    finally:
        page.close()


def test_stelle_oeffnet_ihre_details(browser, umgebung):
    page = _seite(browser, umgebung["url"], "dashboard")
    try:
        _klick_auf_treffer(page, f"Sachbearbeitung {WORT}")
        assert _dialog_titel(page, "Stellendetails") == "Stellendetails"
        _dialog_zeigt(page, f"Sachbearbeitung {WORT}")
    finally:
        page.close()


def test_aussortierte_stelle_oeffnet_ebenfalls_ihre_details(browser, umgebung):
    """Die Trefferliste des Nutzers war voll von Stellen „(aussortiert)“ — sie stehen nicht in der aktiven Liste und muessen
    sich trotzdem oeffnen."""
    page = _seite(browser, umgebung["url"], "dashboard")
    try:
        _klick_auf_treffer(page, f"Disponent {WORT} aussortiert")
        assert _dialog_titel(page, "Stellendetails") == "Stellendetails"
        _dialog_zeigt(page, f"Disponent {WORT} aussortiert")
    finally:
        page.close()


def test_dokument_steht_aufgeklappt_im_bild_auch_von_der_zweiten_seite(browser, umgebung):
    u = umgebung
    page = _seite(browser, u["url"], "dashboard")
    try:
        _klick_auf_treffer(page, f"{WORT}-Lebenslauf.docx")
        karte = page.locator(f"#dokument-{u['dokument']}")
        karte.wait_for(timeout=15000)
        assert "Erstellt:" in karte.inner_text(), "das Dokument ist nicht aufgeklappt"
        # das Scrollen ist weich: gewartet wird auf den Zustand (Karte im Bild), nicht auf eine Zeit
        page.wait_for_function("id => { const r = document.getElementById(id).getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight; }",
                               arg=f"dokument-{u['dokument']}", timeout=15000)
        assert page.locator("input[placeholder*='Dateiname']").input_value() == f"{WORT}-Lebenslauf.docx", "das Suchfeld der Seite ist der Weg zurueck"
    finally:
        page.close()


def test_ein_aktiver_filter_verbirgt_das_dokument_nicht(browser, umgebung):
    """Wer auf der Dokumente-Seite nach Typ gefiltert hat, sieht trotzdem das Dokument, das er in der Suche angeklickt hat."""
    u = umgebung
    page = _seite(browser, u["url"], "dokumente")
    try:
        # „Alle Typen“: das Auswahlfeld ist eine eigene Liste, kein <select> (das erste Feld der Seite ist der Typ fuer den Upload)
        page.locator("button[role=combobox]", has_text="Alle Typen").click()
        page.get_by_role("option", name="Sonstiges").click()          # blendet den Lebenslauf aus
        page.wait_for_function("() => !document.body.innerText.includes('Zebrafink-Lebenslauf')", timeout=15000)
        _klick_auf_treffer(page, f"{WORT}-Lebenslauf.docx")
        page.locator(f"#dokument-{u['dokument']}").wait_for(timeout=15000)
        assert page.locator("button[role=combobox]", has_text="Alle Typen").count() == 1, "der Typ-Filter ist zurueckgesetzt"
    finally:
        page.close()


def test_termin_mit_bewerbung_oeffnet_die_timeline_am_abschnitt_termine(browser, umgebung):
    page = _seite(browser, umgebung["url"], "dashboard")
    try:
        _klick_auf_treffer(page, f"Gespräch {WORT}")
        assert _dialog_titel(page, "Timeline").endswith(f"Konstrukteur {WORT}")
        _im_dialogkoerper(page, "termine")
    finally:
        page.close()


def test_mail_oeffnet_ihr_fenster_auch_mit_bewerbung(browser, umgebung):
    page = _seite(browser, umgebung["url"], "dashboard")
    try:
        _klick_auf_treffer(page, f"Einladung {WORT}")
        assert _dialog_titel(page, f"Einladung {WORT}").startswith("Einladung")
        _dialog_zeigt(page, "hr@example.com")
        _dialog_zeigt(page, "Wir freuen uns auf das Gespraech")
        assert page.evaluate("location.hash") == "#dokumente", "die Mail liegt auf der Dokumente-Seite"
    finally:
        page.close()


def test_mail_ohne_bewerbung_oeffnet_ebenfalls_ihr_fenster(browser, umgebung):
    """Eine Mail ohne Bewerbung hat kein Ziel in einer Timeline — ihr Fenster ist trotzdem da (mit dem Weg, eine Bewerbung anzulegen)."""
    page = _seite(browser, umgebung["url"], "dashboard")
    try:
        _klick_auf_treffer(page, f"Anfrage {WORT}")
        assert _dialog_titel(page, f"Anfrage {WORT}").startswith("Anfrage")
        _dialog_zeigt(page, "Bewerbung aus dieser Mail anlegen")
    finally:
        page.close()


def test_termin_ohne_bewerbung_oeffnet_sich_im_kalender(browser, umgebung):
    page = _seite(browser, umgebung["url"], "dashboard")
    try:
        _klick_auf_treffer(page, f"Termin {WORT} privat")
        assert _dialog_titel(page, "Termin bearbeiten") == "Termin bearbeiten"
        page.wait_for_function(
            """v => { const i = document.querySelector('[role=dialog] input'); return !!i && i.value === v; }""",
            arg=f"Termin {WORT} privat", timeout=15000)
    finally:
        page.close()


def test_termin_ohne_bewerbung_in_der_liste_der_bewerbungen_oeffnet_sich_im_kalender(browser, umgebung):
    """Dieselbe Klasse wie die Suche: der Klick fuehrte in den Kalender, ohne den Termin zu oeffnen."""
    page = _seite(browser, umgebung["url"], "bewerbungen")
    try:
        page.locator("#offene-aktionen").get_by_text(f"Termin {WORT} privat").click(timeout=15000)
        assert _dialog_titel(page, "Termin bearbeiten") == "Termin bearbeiten"
        page.wait_for_function(
            """v => { const i = document.querySelector('[role=dialog] input'); return !!i && i.value === v; }""",
            arg=f"Termin {WORT} privat", timeout=15000)
    finally:
        page.close()


def test_skill_fuehrt_zu_den_skills_im_profil(browser, umgebung):
    page = _seite(browser, umgebung["url"], "dashboard")
    try:
        _klick_auf_treffer(page, f"{WORT}-Zucht")
        filter_ = page.locator("input[aria-label='Skill-Filter']")
        filter_.wait_for(timeout=15000)
        assert filter_.input_value() == f"{WORT}-Zucht", "ab sieben Skills filtert die Liste auf den Treffer"
        page.wait_for_function(
            """() => { const r = document.getElementById('profil-skills').getBoundingClientRect(); return r.top >= 0 && r.top < innerHeight / 2; }""",
            timeout=15000)
    finally:
        page.close()


def test_links_aus_claude_oeffnen_dasselbe(browser, umgebung):
    """`#dokumente/<id>` und `#kalender/<id>` — die Adressen, die Claude nennen kann — gehen denselben Weg wie die Treffer."""
    u = umgebung
    page = _seite(browser, u["url"], f"dokumente/{u['dokument']}")
    try:
        page.locator(f"#dokument-{u['dokument']}").wait_for(timeout=15000)
        assert "Erstellt:" in page.locator(f"#dokument-{u['dokument']}").inner_text()
    finally:
        page.close()
    page = _seite(browser, u["url"], f"kalender/{u['ohne_app']}")
    try:
        assert _dialog_titel(page, "Termin bearbeiten") == "Termin bearbeiten"
    finally:
        page.close()


# ── Quelltext: der Weg ist nicht still wieder weg ───────────────────────────────────────

def test_der_klick_geht_ueber_navigateTo_und_nicht_mehr_nur_ueber_den_hash():
    q = (FRONTEND / "App.jsx").read_text(encoding="utf-8-sig")
    teil = q[q.index("function GlobalSearch("):q.index("// v1.6.7 (#562): Prompts-Tab")]
    teil = re.sub(r"(?m)^\s*//.*$", "", teil)
    assert "zuSuchtreffer(item)" in teil and "navigateTo(ziel.seite, ziel.intent)" in teil
    assert "window.location.hash" not in teil, "ein Klick, der nur den Hash setzt, tat bei gleicher Adresse nichts (#1177)"


def test_jede_absicht_hat_einen_leser_auf_einer_seite():
    """Die Klasse hinter #1177: `wege.js` baute Absichten (`dokumentId`, `terminId`), die keine Seite las — „Zum Dokument“ aus der
    Firmen-Zeitleiste endete auf der Dokumente-Seite, ohne etwas zu zeigen. Zu jedem Schluessel, den ein Weg erzeugt, muss es eine
    Stelle geben, die `intent.<Schluessel>` liest. Wer einen neuen Weg baut, baut den Leser mit — oder nennt die Luecke hier."""
    wege = (FRONTEND / "lib" / "wege.js").read_text(encoding="utf-8-sig")
    erzeugt = set()
    for block in re.findall(r"intent:\s*\{([^{}]*)\}", wege):
        erzeugt.update(re.findall(r"(?:^|[{,])\s*([A-Za-z_]+)\s*:", "{" + block))     # Schluessel vor dem Doppelpunkt, nicht die Werte
    assert {"jobHash", "applicationId", "dokumentId", "terminId", "mailId", "abschnitt"} <= erzeugt, erzeugt
    gelesen = ""
    for seite in (FRONTEND / "pages").glob("*.jsx"):
        gelesen += seite.read_text(encoding="utf-8-sig")
    gelesen += (FRONTEND / "App.jsx").read_text(encoding="utf-8-sig")
    BEKANNTE_LUECKEN = {
        "focus": "wird gesetzt, aber von keiner Seite gebraucht (seit G57 zielt jede Kennung ohnehin auf das Objekt)",
        "aufgabeId": "zuAufgabe(id) wird nirgends mit einer Kennung aufgerufen; die Aufgaben-Seite oeffnet keine einzelne Aufgabe",
    }
    ohne_leser = sorted(k for k in erzeugt if not re.search(rf"intent\??\.{k}\b", gelesen) and k not in BEKANNTE_LUECKEN)
    assert not ohne_leser, f"Absichten ohne Leser auf einer Seite: {ohne_leser} — den Leser bauen oder die Luecke in BEKANNTE_LUECKEN nennen"
    # die Ausnahmen duerfen nicht still veralten: gibt es fuer sie inzwischen einen Leser, gehoeren sie hier raus
    for k in BEKANNTE_LUECKEN:
        assert not re.search(rf"intent\??\.{k}\b", gelesen), f"{k} hat jetzt einen Leser — aus BEKANNTE_LUECKEN entfernen"
