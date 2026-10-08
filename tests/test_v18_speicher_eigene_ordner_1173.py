"""Speicher & Downloads: der eigene Ordner fuer Lebenslaeufe und Anschreiben laesst sich DORT aendern (#1173, G86).

Der Nutzer (07.10.2026), auf der Seite der Beta: „Bei Speicher & Downloads wuerde ich auch gerne, da wo es Sinn macht, die Pfade
anpassen wollen — vor allem der eigene Ordner, wo ich meine Lebenslaeufe und Bewerbungen speichere (oder ein Link dahin).“

Zwei Dinge standen dem im Weg:

1. **Ein Lesefehler.** Die Karte „Deine eigenen Ordner“ und die Zeile „Bleibt: Ablageordner …“ in der Gefahrenzone lasen die Ordner mit
   `db.get_setting(<Schluessel>)` — dem Schluessel OHNE Profil. Gespeichert wird aber je Profil (`ablage.ordner_setzen`), unter
   `<Profil>:<Schluessel>`. Die Liste war darum immer leer, die Karte nannte den Ordner des Nutzers nie. Zwei Wege zum selben Wert,
   nur einer davon mit Test — der Lehre aus #799 und #1007 entsprechend lesen jetzt beide ueber `ablage.ordner_lesen`.
2. **Kein Weg zum Aendern.** Die Karte zeigte nur an. Jetzt traegt sie die beiden Eingabefelder selbst (dieselbe Komponente und
   dieselbe Pruefung wie unter Einstellungen › Ordner), steht immer da und sagt, wohin erzeugte Dateien gerade gehen.

Das gebaute Bundle wird getestet (nach JSX-Aenderungen neu bauen: `cd frontend && pnpm exec vite build`).
"""
from __future__ import annotations

import os
import re
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

from bewerbungs_assistent.services import ablage, datenordner, speicher

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend" / "src"


# ── Server-Seite ────────────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_db):
    tmp_db.save_profile({"name": "Erika Musterfrau"})
    assert tmp_db.get_active_profile_id(), "ohne aktives Profil prueft dieser Test nichts (die Einstellung ist je Profil)"
    return tmp_db


def _eigene(db) -> dict:
    return {o["id"]: o for o in speicher.uebersicht(db, frist_s=2.0)["orte"]}["eigene"]


def test_die_liste_der_eigenen_ordner_findet_die_je_profil_gespeicherten(db, tmp_path):
    """Der Lesefehler: gespeichert wird je Profil, gelesen wurde ohne Profil — die Liste blieb leer."""
    ausgabe = tmp_path / "bewerbungen"
    vorlagen = tmp_path / "vorlagen"
    ausgabe.mkdir()
    vorlagen.mkdir()
    assert ablage.ordner_setzen(db, "ausgabe", str(ausgabe))["gespeichert"]
    assert ablage.ordner_setzen(db, "vorlagen", str(vorlagen))["gespeichert"]
    assert datenordner.ausserhalb(db) == [
        {"was": "Ablageordner", "pfad": str(ausgabe)},
        {"was": "Vorlagenordner", "pfad": str(vorlagen)},
    ]


def test_ohne_gesetzte_ordner_ist_die_liste_leer(db):
    assert datenordner.ausserhalb(db) == []
    assert datenordner.ausserhalb(None) == []


def test_die_karte_steht_auch_ohne_ordner_da_und_nennt_den_standard(db):
    ort = _eigene(db)
    assert ort["id"] == "eigene" and ort["urheber"] == "du" and ort["aktionen"] == []
    assert ort["pfad"] == "" and ort["oeffnen"] is False
    assert "noch kein eigener Ordner gewählt" in ort["hinweis"]
    assert str(ablage.ausgabe_ordner(db)) in ort["hinweis"], "der Hinweis nennt den Ort, an dem die Dateien WIRKLICH landen"
    assert "ändern" in ort["was"] and "Ausgabe-Ordner" in ort["was"] and "Vorlagen-Ordner" in ort["was"]


def test_mit_eigenem_ordner_zeigt_die_karte_pfad_groesse_und_oeffnen(db, tmp_path):
    ausgabe = tmp_path / "bewerbungen"
    ausgabe.mkdir()
    (ausgabe / "lebenslauf_erika.docx").write_bytes(b"x" * 1234)
    assert ablage.ordner_setzen(db, "ausgabe", str(ausgabe))["gespeichert"]
    ort = _eigene(db)
    assert ort["pfad"] == str(ausgabe), "„Ordner öffnen“ muss den Ordner treffen, in dem die Unterlagen landen"
    assert ort["oeffnen"] is True and ort.get("hinweis") is None
    assert [e["name"] for e in ort["eintraege"]] == ["Ablageordner"]
    assert ort["eintraege"][0]["bytes"] == 1234 and ort["bytes"] == 1234


def test_ein_verschwundener_ordner_wird_benannt_statt_still_ersetzt(db, tmp_path):
    ausgabe = tmp_path / "externe_platte"
    ausgabe.mkdir()
    assert ablage.ordner_setzen(db, "ausgabe", str(ausgabe))["gespeichert"]
    ausgabe.rmdir()
    ort = _eigene(db)
    assert ort["pfad"] == "" and ort["oeffnen"] is False
    assert "nicht beschreibbar" in ort["hinweis"] and str(ausgabe) in ort["hinweis"]


@pytest.fixture
def klient(db):
    """Das Dashboard gegen die isolierte Datenbank (TestClient), danach wieder abgehaengt."""
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient

    assert str(db.db_path) != "", "die Datenbank muss die isolierte sein"
    alt = dash._db
    dash._db = db
    try:
        with TestClient(dash.app) as k:
            yield k
    finally:
        dash._db = alt


def test_rest_leer_und_minus_setzen_den_ordner_zurueck(db, klient, tmp_path):
    """Zuruecksetzen endete im Dashboard seit v1.7.59 mit 400: die Oberflaeche schickte „-“, nur das MCP-Werkzeug kannte es."""
    ordner = tmp_path / "bewerbungen"
    ordner.mkdir()
    for zeichen in ("", "-", "  -  "):
        assert klient.put("/api/settings/ablage", json={"art": "ausgabe", "pfad": str(ordner)}).status_code == 200
        assert ablage.ordner_lesen(db, "ausgabe") == ordner
        antwort = klient.put("/api/settings/ablage", json={"art": "ausgabe", "pfad": zeichen})
        assert antwort.status_code == 200, f"{zeichen!r} muss zuruecksetzen, kam {antwort.status_code}: {antwort.text}"
        assert antwort.json()["gespeichert"] is True and antwort.json()["ausgabe_befund"] == "standard"
        assert ablage.ordner_lesen(db, "ausgabe") is None


def test_rest_nennt_den_grund_unter_error_und_hinweis(db, klient, tmp_path):
    """Die Oberflaeche liest `error`; der Grund stand nur unter `hinweis` — am Feld blieb „HTTP 400“."""
    antwort = klient.put("/api/settings/ablage", json={"art": "ausgabe", "pfad": str(tmp_path / "nichtda")})
    assert antwort.status_code == 400
    koerper = antwort.json()
    assert koerper["gespeichert"] is False and koerper["grund"] == "fehlt"
    assert koerper["error"] == koerper["hinweis"] and "Diesen Ordner gibt es nicht" in koerper["error"]
    assert ablage.ordner_lesen(db, "ausgabe") is None


def test_ordner_setzen_kennt_das_minus_selbst(db, tmp_path):
    """Die Regel steht in `ablage.ordner_setzen` und nicht in jedem Aufrufer (MCP, REST, Oberflaeche)."""
    ordner = tmp_path / "vorlagen"
    ordner.mkdir()
    assert ablage.ordner_setzen(db, "vorlagen", str(ordner))["gespeichert"]
    assert ablage.ordner_setzen(db, "vorlagen", "-")["gespeichert"] is True
    assert ablage.ordner_lesen(db, "vorlagen") is None


def test_nur_die_eigene_karte_nimmt_aenderungen_an():
    """Die anderen Orte sind durch die Installation bedingt: kein Editor, keine Eingabe — im Quelltext der Seite."""
    q = (FRONTEND / "components" / "SpeicherTab.jsx").read_text(encoding="utf-8")
    q = re.sub(r"/\*.*?\*/", "", q, flags=re.S)         # Kommentare zaehlen nicht
    q = re.sub(r"(?m)^\s*//.*$", "", q)
    assert 'ort.id === "eigene" && ordnerEditor' in q
    assert q.count("ordnerEditor(") == 1, "genau eine Stelle ruft den Editor auf"
    assert "<input" not in q.replace('<input type="checkbox"', ""), "Eingabefelder gehoeren in den Editor, nicht in die Seite"


def test_die_komponente_steht_an_zwei_orten_und_ist_dieselbe():
    q = (FRONTEND / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    assert q.count("function AblageOrdnerCard") == 1, "keine zweite Fassung der Pruefung (#963)"
    assert q.count("<AblageOrdnerCard") == 2
    assert "eingebettet onGespeichert={neuMessen}" in q


def test_die_komponente_zeigt_den_grund_und_schickt_zum_zuruecksetzen_leer():
    q = (FRONTEND / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8")
    teil = q[q.index("function AblageOrdnerCard"):q.index("function OllamaAutostartBlock")]
    teil = re.sub(r"(?m)^\s*//.*$", "", teil)                    # Kommentare zaehlen nicht
    assert "err?.payload?.hinweis" in teil, "der Grund des Servers gehoert an das Feld"
    assert "pfad: pfad.trim() }" in teil and '"-"' not in teil, "leer heisst zuruecksetzen, ohne Platzhalter"


# ── Browser: gegen das gebaute Bundle ───────────────────────────────────────────────────

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Error as PlaywrightError  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Erika Musterfrau"})
    dash._db = d
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
    yield {"url": f"http://127.0.0.1:{port}", "db": d, "tmp": tmp_path}
    srv.should_exit = True
    t.join(timeout=10)
    dash._db = None
    d.close()
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


def _speicher_seite(browser, url):
    """Einstellungen › Erweitert › Speicher & Downloads, bis die Karte „Deine eigenen Ordner“ steht (Zustand, nicht Zeit)."""
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    page.goto(f"{url}/#einstellungen", wait_until="load", timeout=30000)
    page.locator("[data-erweitert-schalter]").click(timeout=20000)
    page.locator("[data-erweitert-reiter]").get_by_role("button", name="Speicher & Downloads").click()
    page.locator("[data-speicher-ort='eigene']").wait_for(timeout=30000)
    return page


def _eigene_karte(page):
    return page.locator("[data-speicher-ort='eigene']")


def test_die_karte_traegt_die_eingabefelder_und_sagt_wohin_die_dateien_gehen(browser, server):
    page = _speicher_seite(browser, server["url"])
    try:
        karte = _eigene_karte(page)
        editor = karte.locator("[data-ablage-eingebettet]")
        editor.wait_for(timeout=15000)
        assert editor.locator("input").count() == 2, "Ausgabe-Ordner und Vorlagen-Ordner"
        text = karte.inner_text()
        assert "noch kein eigener Ordner gewählt" in text and "export" in text
        assert "Ausgabe-Ordner" in text and "Vorlagen-Ordner" in text
        assert "Aktuell:" not in text, "der Ort steht schon im Hinweis darueber — nicht ein zweites Mal"
        assert karte.get_by_role("button", name="Ordner öffnen").count() == 0, "ohne eigenen Ordner gibt es nichts Eigenes zu öffnen"
        # die anderen Orte nehmen keine Eingaben an
        assert page.locator("[data-speicher-ort='daten'] input, [data-speicher-ort='programm'] input").count() == 0
    finally:
        page.close()


def test_den_eigenen_ordner_auf_der_speicher_seite_aendern_und_wieder_zuruecksetzen(browser, server):
    ordner = server["tmp"] / "meine_bewerbungen"
    ordner.mkdir()
    (ordner / "lebenslauf_erika.docx").write_bytes(b"x" * 500)
    page = _speicher_seite(browser, server["url"])
    try:
        karte = _eigene_karte(page)
        editor = karte.locator("[data-ablage-eingebettet]")
        editor.wait_for(timeout=15000)
        feld = editor.locator("input").first
        feld.fill(str(ordner))
        editor.get_by_role("button", name="Speichern").first.click()
        # die Seite misst neu: Pfad und „Ordner öffnen“ erscheinen, ohne dass jemand die Seite wechselt
        karte.locator("[data-speicher-pfad]").wait_for(timeout=15000)
        assert karte.locator("[data-speicher-pfad]").inner_text() == str(ordner)
        karte.get_by_role("button", name="Ordner öffnen").wait_for(timeout=5000)
        assert "noch kein eigener Ordner gewählt" not in karte.inner_text()
        assert "Aktuell:" not in karte.inner_text(), "der Pfad steht schon darueber, in der Karte"
        assert ablage.ordner_lesen(server["db"], "ausgabe") == ordner, "wirklich gespeichert, nicht nur angezeigt"
        # und wieder zurueck: ein leeres Feld heisst „wie bisher“ (seit v1.7.59 endete das im Dashboard mit „HTTP 400“)
        feld.fill("")
        editor.get_by_role("button", name="Speichern").first.click()
        page.wait_for_function(
            "() => document.querySelector(\"[data-speicher-ort='eigene']\").innerText.includes('noch kein eigener Ordner gewählt')",
            timeout=15000)
        assert karte.locator("[data-speicher-pfad]").count() == 0
        assert ablage.ordner_lesen(server["db"], "ausgabe") is None
        assert "HTTP 400" not in editor.inner_text(), "das Zuruecksetzen darf nicht abgewiesen werden"
    finally:
        page.close()


def test_ein_ungueltiger_pfad_wird_am_feld_abgewiesen_und_nicht_gespeichert(browser, server):
    page = _speicher_seite(browser, server["url"])
    try:
        karte = _eigene_karte(page)
        editor = karte.locator("[data-ablage-eingebettet]")
        editor.wait_for(timeout=15000)
        editor.locator("input").first.fill("bewerbungen")           # relativ: wird abgewiesen
        editor.get_by_role("button", name="Speichern").first.click()
        editor.get_by_text("vollständigen Pfad", exact=False).wait_for(timeout=10000)
        assert ablage.ordner_lesen(server["db"], "ausgabe") is None
        assert karte.locator("[data-speicher-pfad]").count() == 0
        editor.locator("input").first.fill(str(server["tmp"] / "gibt_es_nicht"))   # absolut, aber nicht vorhanden
        editor.get_by_role("button", name="Speichern").first.click()
        editor.get_by_text("Diesen Ordner gibt es nicht", exact=False).wait_for(timeout=10000)
        assert ablage.ordner_lesen(server["db"], "ausgabe") is None
        # die Begruendung steht am Feld — frueher stand dort nur „HTTP 400“, und niemand erfuhr, WARUM
        assert "HTTP 400" not in editor.inner_text()
    finally:
        page.close()


def test_der_vorlagen_ordner_laesst_sich_dort_auch_setzen(browser, server):
    vorlagen = server["tmp"] / "vorlagen"
    vorlagen.mkdir()
    page = _speicher_seite(browser, server["url"])
    try:
        karte = _eigene_karte(page)
        editor = karte.locator("[data-ablage-eingebettet]")
        editor.wait_for(timeout=15000)
        editor.locator("input").nth(1).fill(str(vorlagen))
        editor.get_by_role("button", name="Speichern").nth(1).click()
        # die Seite misst neu: der Vorlagen-Ordner steht jetzt unter den Einzelheiten der Karte (zugeklappt zaehlt nur die Anzahl)
        karte.get_by_role("button", name="Einzelheiten (1)").click(timeout=15000)
        karte.locator("[data-speicher-eintraege]").get_by_text("Vorlagenordner").wait_for(timeout=5000)
        assert ablage.ordner_lesen(server["db"], "vorlagen") == vorlagen
        assert ablage.ordner_lesen(server["db"], "ausgabe") is None, "der andere Ordner bleibt, wie er war"
        # und er bleibt ehrlich: fuer erzeugte Dateien ist weiter nichts gewaehlt, auch wenn ein Vorlagen-Ordner da ist
        assert "noch kein eigener Ordner gewählt" in karte.inner_text()
    finally:
        page.close()


def test_ein_verschwundener_ordner_wird_in_der_karte_nur_einmal_genannt(browser, server):
    """Externe Platte weg: der Satz stand zweimal da (oben in der Karte und nochmal amber unter dem Feld)."""
    ordner = server["tmp"] / "externe_platte"
    ordner.mkdir()
    assert ablage.ordner_setzen(server["db"], "ausgabe", str(ordner))["gespeichert"]
    ordner.rmdir()
    page = _speicher_seite(browser, server["url"])
    try:
        karte = _eigene_karte(page)
        karte.locator("[data-ablage-eingebettet]").wait_for(timeout=15000)
        text = karte.inner_text()
        assert text.count("gerade nicht beschreibbar") == 1
        assert "Aktuell:" in text, "der Hinweis nennt den Ersatz-Ort nicht, deshalb bleibt hier die Zeile mit dem Pfad"
        assert str(ordner) in karte.locator("input").first.input_value(), "das Feld zeigt weiter, was der Mensch eingestellt hat"
    finally:
        page.close()


def test_unter_einstellungen_ordner_gibt_es_die_karte_weiter_als_eigene_karte(browser, server):
    page = browser.new_page(viewport={"width": 1440, "height": 1000})
    try:
        page.goto(f"{server['url']}/#einstellungen", wait_until="load", timeout=30000)
        page.locator("[data-settings-reiter]").get_by_role("button", name="Ordner", exact=True).click(timeout=20000)
        page.get_by_text("Ordner für Dokumente und Vorlagen").wait_for(timeout=15000)
        assert page.locator("[data-ablage-eingebettet]").count() == 0, "dort steht sie mit eigener Überschrift, nicht eingebettet"
        assert page.locator("input[placeholder*='Bewerbungen']").count() >= 1
        assert page.get_by_text("Aktuell:").count() == 1, "dort ist die Zeile mit dem Ort weiter die einzige Auskunft"
    finally:
        page.close()
