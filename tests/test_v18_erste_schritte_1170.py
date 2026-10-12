"""Bedienungsprüfung 1.8 (#1170, G83): die Welle „Erste Schritte“ — was ein Mensch ohne Profil sieht und anklickt.

Der Rundgang vom 04.10.2026 (leere Installation) fand U5 bis U9 und U13, U14, U18:

* U5  „Suche & Bewertung“ trug ohne Profil die Überschrift „Profil“ und den Text der Profilseite.
* U6  „Zuerst dein Profil“ war eine Karte ohne Knopf, auf Stellen und Bewerbungen umgeben von Kennzahlen aus Nullen, Filtern, einer
      Quellenkarte und Knöpfen, die ohne Profil nichts tun können.
* U7  „Profil anlegen“ öffnete „Neues Profil anlegen — Lege ein weiteres Profil … an“ (auch beim allerersten) und fragte nach einem
      „Profilname (z. B. IT Consulting)“.
* U8  Aufgaben und Statistiken erklärten sich nicht.
* U9  Die Gefahrenzone zählte mitgelieferte Vorgaben als Daten („Bewerbungen: 7 Datensätze … Enthält Namen und Mailadressen Dritter“).
* U13 Sichtbare Texte in Umschrift (fuer, einfuegen, Datensaetze …) — und der Prüfer sah Text neben einem Ausdruck nie an.
* U14 „AUSSORTIERT“ lief in der Statistik in die Nachbarkachel.

Geprüft wird im Browser gegen das gebaute Bundle (`cd frontend && pnpm exec vite build`, wenn sich das Frontend ändert); alle Namen sind
Platzhalter, GitHub wird nie erreicht.
"""
from __future__ import annotations

import importlib.util
import os
import socket
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend" / "src"


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def umgebung(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("erste1170")
    os.environ["BA_DATA_DIR"] = str(tmp)
    from bewerbungs_assistent.database import Database
    import bewerbungs_assistent.dashboard as dash

    db = Database(db_path=tmp / "test.db")
    db.initialize()
    assert str(tmp) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
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
        pytest.skip(f"Chromium nicht verfügbar: {exc}")


def _seite(browser, url, route, breite=1400):
    page = browser.new_context(viewport={"width": breite, "height": 950}).new_page()
    page.goto(f"{url}/#{route}")
    page.wait_for_load_state("networkidle")
    return page


def _ohne_profil(umgebung):
    db = umgebung["db"]
    assert not db.get_profile(), "dieser Block läuft vor dem ersten Profil"


# ══ U5, U6: ohne Profil EINE Karte mit EINEM Knopf ════════════════════════════════════════════════════════════

@pytest.mark.parametrize("route,bereich", [("stellen", "Stellen"), ("bewerbungen", "Bewerbungen")])
def test_u6_ohne_profil_ist_die_karte_der_ganze_inhalt(browser, umgebung, route, bereich):
    _ohne_profil(umgebung)
    page = _seite(browser, umgebung["url"], route)
    try:
        page.locator(f'[data-zuerst-profil="{bereich}"]').wait_for(timeout=10000)
        text = page.inner_text("main") if page.locator("main").count() else page.inner_text("body")
        assert text.count("Zuerst dein Profil") == 1, text[:600]
        # kein Kennzahlen-Gerüst aus Nullen, keine Filter, keine Quellenkarte, keine Knöpfe ohne Wirkung
        for weg in ("AKTIVE STELLEN", "Aktive Bewerbungen", "GEHALTSDURCHSCHNITT", "0 EUR", "Browser-Quellen mit Claude",
                    "CV als DOCX", "Bewerbung anlegen", "Filter", "Auf Kurs"):
            assert weg not in text, f"{weg!r} steht ohne Profil auf der Seite {route}"
        # und der eine Knopf ist da
        assert page.get_by_role("button", name="Lebenslauf hochladen").count() == 1
    finally:
        page.context.close()


def test_u5_die_suchseite_ohne_profil_heisst_nicht_profil(browser, umgebung):
    _ohne_profil(umgebung)
    page = _seite(browser, umgebung["url"], "suche")
    try:
        page.locator('[data-zuerst-profil]').wait_for(timeout=10000)
        # NUR die Seite: „Suche & Bewertung“ steht auch in der Seitenleiste und täuschte den Test (Gegenprobe es03)
        text = page.locator("#page-profil").inner_text()
        assert "Suche & Bewertung" in text
        assert "Suchbegriffe, Schwellen und Blacklist stellst du ein, sobald dein Profil steht." in text
        assert "Lege dein erstes Profil an" not in text
        assert "Noch kein aktives Profil" not in text
        assert page.get_by_role("button", name="Lebenslauf hochladen").count() == 1
    finally:
        page.context.close()


def test_u5_die_profilseite_ohne_profil_nennt_denselben_schritt(browser, umgebung):
    _ohne_profil(umgebung)
    page = _seite(browser, umgebung["url"], "profil")
    try:
        page.locator('[data-zuerst-profil]').wait_for(timeout=10000)
        text = page.locator("#page-profil").inner_text()
        assert "Zuerst dein Profil" in text
        assert "Dein Lebenslauf ist die Grundlage für alles andere." in text
        assert "Noch kein aktives Profil" not in text
        assert page.get_by_role("button", name="Lebenslauf hochladen").count() == 1
    finally:
        page.context.close()


# ══ U7: ein Weg, und der erste Dialog sagt, was er ist ═════════════════════════════════════════════════════════

@pytest.mark.parametrize("route", ["stellen", "bewerbungen", "suche", "profil", "dashboard"])
def test_u7_lebenslauf_hochladen_oeffnet_denselben_ersten_dialog(browser, umgebung, route):
    _ohne_profil(umgebung)
    page = _seite(browser, umgebung["url"], route)
    try:
        page.get_by_role("button", name="Lebenslauf hochladen").first.click()
        dialog = page.locator("[role=dialog]").first
        dialog.wait_for(timeout=10000)
        text = dialog.inner_text()
        assert "Dein Profil anlegen" in text
        assert "Dein Name" in text
        assert "weiteres Profil" not in text and "Karrierepfad" not in text and "IT Consulting" not in text
        assert page.get_by_role("button", name="Weiter zum Lebenslauf").count() == 1
        # die Adresse bleibt: es ging kein Umweg über die Profilseite
        assert page.url.rstrip("/").endswith(f"#{route}"), page.url
    finally:
        page.context.close()


def test_u7_mit_vorhandenem_profil_bleibt_der_dialog_der_fuer_ein_weiteres(browser, umgebung):
    umgebung["db"].create_profile("Erika Probe", "erika@example.com")
    page = _seite(browser, umgebung["url"], "dashboard")
    try:
        # der Dialog wird über die Oberfläche geöffnet, nicht über eine Route: hier genügt der Quelltext der Verzweigung
        quelle = (FRONTEND / "App.jsx").read_text(encoding="utf-8-sig")
        assert 'chrome.status?.has_profile ? "Neues Profil anlegen" : "Dein Profil anlegen"' in quelle
        assert 'chrome.status?.has_profile ? "Profilname" : "Dein Name"' in quelle
    finally:
        page.context.close()


# Der Anfangszustand des Dashboards ist „kein Profil“ (`status: { has_profile: false }`), nicht „unbekannt“. Der unabhängige Prüfer
# des Kandidaten hat es mit einem Profil und einem um 1,5 s verzögerten /api/status gemessen: Stellen, Bewerbungen, Suche und Profil
# zeigten vollflächig „Zuerst dein Profil … Lebenslauf hochladen“ — bei jedem Start, auch bei einem Menschen mit Profil.
VERZOEGERN = r"""
(() => {
  const echt = window.fetch.bind(window);
  window.fetch = (eingabe, optionen) => {
    const url = typeof eingabe === "string" ? eingabe : ((eingabe && eingabe.url) || "");
    const antwort = echt(eingabe, optionen);
    if (!/\/api\/status(\?|$)/.test(url)) return antwort;
    return antwort.then((r) => new Promise((fertig) => setTimeout(() => fertig(r), 1800)));
  };
})();
"""


@pytest.mark.parametrize("route,wurzel", [
    ("stellen", "#page-stellen"), ("bewerbungen", "#page-bewerbungen"), ("suche", "#page-profil"), ("profil", "#page-profil"),
])
def test_u6_waehrend_der_status_laedt_steht_keine_behauptung_ueber_das_profil(browser, umgebung, route, wurzel):
    assert umgebung["db"].get_profile(), "dieser Block läuft nach dem ersten Profil"
    ctx = browser.new_context(viewport={"width": 1400, "height": 950})
    page = ctx.new_page()
    page.add_init_script(VERZOEGERN)
    try:
        page.goto(f"{umgebung['url']}/#{route}")
        page.wait_for_timeout(700)  # der Status ist noch unterwegs
        assert page.locator("[data-zuerst-profil]").count() == 0, "während des Ladens steht keine Aussage über das Profil da"
        assert "Zuerst dein Profil" not in page.inner_text("body")
        page.locator(wurzel).wait_for(timeout=15000)  # danach kommt die richtige Seite
        assert page.locator("[data-zuerst-profil]").count() == 0
    finally:
        ctx.close()


# ══ U8, U14: leere Seiten erklären sich ════════════════════════════════════════════════════════════════════════

def test_u8_aufgaben_ohne_eintrag_sagen_woher_aufgaben_kommen(browser, umgebung):
    page = _seite(browser, umgebung["url"], "aufgaben")
    try:
        leer = page.locator("[data-aufgaben-leer]")
        leer.wait_for(timeout=10000)
        assert "Aufgaben entstehen aus deinen Bewerbungen" in leer.inner_text()
        assert "Neue Aufgabe" in leer.inner_text()
        # der Knopf sieht nicht mehr deaktiviert aus (kein blasses „bg-teal/20“)
        klasse = page.get_by_role("button", name="Neue Aufgabe").first.get_attribute("class") or ""
        assert "bg-teal/20" not in klasse, klasse
    finally:
        page.context.close()


def test_u8_statistiken_ohne_daten_erklaeren_sich_statt_nullen_zu_zeigen(browser, umgebung):
    page = _seite(browser, umgebung["url"], "statistiken")
    try:
        page.get_by_text("Noch keine Zahlen").wait_for(timeout=10000)
        text = page.inner_text("body")
        assert "Die Statistik füllt sich, sobald PBP Stellen gefunden hat und du Bewerbungen angelegt hast" in text
        # keine Wand aus Nullen: weder die Kacheln „Heute“ und „Gesamt“ noch die Quoten
        klein = text.lower()
        assert "aussortiert" not in klein and "antwortzeit" not in klein and "outcome-quoten" not in klein, text[:500]
    finally:
        page.context.close()


def test_u14_die_beschriftung_der_kacheln_laeuft_nicht_in_die_nachbarkachel():
    quelle = (FRONTEND / "pages" / "StatsPage.jsx").read_text(encoding="utf-8-sig")
    assert 'className="break-words text-xs uppercase tracking-[0.06em] text-muted">{label}</p>' in quelle
    assert 'className="grid gap-6 lg:grid-cols-2 2xl:grid-cols-3"' in quelle


# ══ U9: mitgelieferte Vorgaben sind keine Daten des Menschen ═══════════════════════════════════════════════════

@pytest.fixture
def frische_db(tmp_path):
    """Eine eigene, frisch angelegte Datenbank (nicht die des Browser-Teils: dort schreiben die Seiten Vermerke)."""
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "frisch.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


def test_u9_eine_frische_installation_zaehlt_ihre_vorgaben_nicht_als_daten(frische_db):
    from bewerbungs_assistent.services import loeschbereiche as lb
    db = frische_db
    db.list_contact_categories()          # die mitgelieferten Kategorien entstehen beim ersten Ansehen der Kontakte
    v = lb.vorschau(db)
    bew = v["bereiche"]["bewerbungen"]
    assert bew["zeilen_gesamt"] == 0, bew
    assert bew["vorgaben"] >= 1, "die mitgelieferten Kontaktkategorien stehen als Vorgaben da"
    assert "contact_categories" not in bew["je_tabelle"]
    assert v["bereiche"]["einstellungen"]["zeilen_gesamt"] == 0, v["bereiche"]["einstellungen"]
    assert v["bereiche"]["einstellungen"]["vorgaben"] >= 1


def test_u9_eigene_eintraege_zaehlen_und_gehen_mit_den_vorgaben(frische_db):
    from bewerbungs_assistent.services import loeschbereiche as lb
    db = frische_db
    db.list_contact_categories()
    con = db.connect()
    con.execute("INSERT INTO contact_categories (name, slug, color, sort_order, is_system, created_at, updated_at) "
                "VALUES ('Eigene Gruppe', 'eigene-gruppe', '#123456', 99, 0, '2026-10-11', '2026-10-11')")
    con.commit()
    v = lb.vorschau(db, ["bewerbungen"])
    assert v["bereiche"]["bewerbungen"]["zeilen_gesamt"] == 1
    assert v["bereiche"]["bewerbungen"]["je_tabelle"].get("contact_categories") == 1
    erg = lb.leeren(db, ["bewerbungen"], dry_run=False, dateien_loeschen=False)
    assert erg["status"] == "geloescht"
    # Ergebnis und Vorschau zählen gleich ...
    assert erg["zeilen_gesamt"] == v["bereiche"]["bewerbungen"]["zeilen_gesamt"]
    # ... und die Vorgaben sind trotzdem weg (geleert wird alles, nur die Zahl nennt, was der Mensch angelegt hat)
    assert db.connect().execute("SELECT COUNT(*) FROM contact_categories").fetchone()[0] == 0
    assert erg["vorgaben"] >= 1


def test_u9_die_oberflaeche_nennt_die_vorgaben_und_schreibt_datensaetze_mit_umlaut():
    quelle = (FRONTEND / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    assert "Datensätze" in quelle and "Datensaetze" not in quelle
    assert "mitgelieferte Vorgaben" in quelle


# ══ U13: der Prüfer sieht Text neben einem Ausdruck ════════════════════════════════════════════════════════════

def _pruefer():
    spec = importlib.util.spec_from_file_location("ui_texte_pruefen_u13", REPO / "scripts" / "ui_texte_pruefen.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_u13_text_hinter_einem_ausdruck_wird_geprueft(tmp_path):
    ui = _pruefer()
    datei = tmp_path / "Probe.jsx"
    datei.write_text(
        "export default function P({ n, liste }) {\n"
        "  return (\n"
        "    <div>\n"
        "      <Badge>\n"
        "        {n} Datensaetze\n"
        "      </Badge>\n"
        "      <span>\n"
        "        Gilt fuer alle Profile: {liste.join(', ')}\n"
        "      </span>\n"
        "    </div>\n"
        "  );\n"
        "}\n", encoding="utf-8")
    gefunden = " ".join(t for _z, t in ui.texte(datei))
    assert "Datensaetze" in gefunden and "Gilt fuer alle Profile" in gefunden
    assert any("Datensaetze" in w for w in ui.umlaut_funde(gefunden))


def test_u13_ein_verirrtes_zeichen_verschiebt_die_paarung_nicht(tmp_path):
    """Ein einzelnes Gravis-Zeichen im JSX-Text paarte sich mit dem Anfang des nächsten Template-Literals und verschob die Paarung
    bis zum Dateiende: alle Zeichenketten danach blieben ungelesen (ElwosaSidebarChat.jsx: „fuer“, „einfuegen“, „oeffnen“)."""
    ui = _pruefer()
    datei = tmp_path / "Probe.jsx"
    datei.write_text(
        "export default function P({ n }) {\n"
        "  return <p>Das Zeichen ` steht hier einzeln</p>;\n"
        "}\n"
        "const A = `Elwosa fuer ${n} Minuten pausieren`;\n"
        'const B = "Danach in Claude einfuegen";\n', encoding="utf-8")
    texte = [t for _z, t in ui.texte(datei)]
    assert any("Elwosa fuer" in t for t in texte), texte
    assert any("einfuegen" in t for t in texte), texte


def test_u13_jedes_textstueck_steht_nur_einmal_da(tmp_path):
    """Die Suchlaeufe ueberlappen: ein Textknoten `>Text<` passt auf zwei Muster, ein einzeiliges Literal auf zwei. Ohne
    Zusammenfuehren stand jeder Fund doppelt da (CI-Lauf von PR 1193: die Probe des Absturz-Tests lieferte sechs statt drei)."""
    ui = _pruefer()
    datei = tmp_path / "Probe.jsx"
    datei.write_text(
        "export default function P({ n }) {\n"
        "  return <p>Das ist eine Uebung fuer Staerken</p>;\n"
        "}\n"
        'const B = "Danach in Claude einfuegen";\n', encoding="utf-8")
    texte = [t for _z, t in ui.texte(datei)]
    assert texte.count("Das ist eine Uebung fuer Staerken") == 1, texte
    assert texte.count("Danach in Claude einfuegen") == 1, texte


def test_u13_die_oberflaeche_hat_keine_umschrift_mehr():
    ui = _pruefer()
    funde = ui.pruefen()
    assert funde == [], "\n".join(funde)


# ══ U18: Kleinigkeiten ═════════════════════════════════════════════════════════════════════════════════════════════

def test_u18_die_kopfzeile_der_kontakte_nennt_im_reiter_firmen_die_firmen(browser, umgebung):
    umgebung["db"].create_profile("Erika Probe", "erika@example.com") if not umgebung["db"].get_profile() else None
    page = _seite(browser, umgebung["url"], "kontakte")
    try:
        page.get_by_role("tab", name="Firmen").click()
        page.locator("h2", has_text="Firmen").first.wait_for(timeout=10000)
        assert page.get_by_role("button", name="Neuer Kontakt").count() == 0
        assert page.get_by_role("button", name="Importieren").count() == 0
        page.get_by_role("tab", name="Kontakte").click()
        page.get_by_role("button", name="Neuer Kontakt").wait_for(timeout=10000)
    finally:
        page.context.close()


def test_u18_aufraeumen_ist_dort_nicht_klickbar_wo_nichts_liegt():
    quelle = (FRONTEND / "components" / "SpeicherTab.jsx").read_text(encoding="utf-8-sig")
    assert "const nichtsDa = Boolean(ort.nichts_vorhanden) || Number(ort.bytes) === 0;" in quelle
    assert "|| nichtsDa}" in quelle


def test_u18_die_firmenkarte_zeigt_keinen_platzhaltersatz():
    quelle = (FRONTEND / "components" / "FirmenAnsicht.jsx").read_text(encoding="utf-8-sig")
    assert "Noch keine Schreibweisen eingetragen." not in quelle


def test_u18_ein_roher_fehlertext_der_erkennung_steht_nicht_im_dashboard():
    quelle = (FRONTEND / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    assert "Erkennungs-Fehler: {status.error}" not in quelle
    assert "Ollama ließ sich gerade nicht erkennen." in quelle


# ══ #1147 Punkt 3: der Satz zu den KI-Schaltern sagt, was sie tun ══════════════════════════════════════════════

def test_1147_die_ki_schalter_versprechen_nicht_mehr_als_sie_tun():
    """Die Schalter sperren die Funktionen, mit denen Claude etwas AUSLÖST (elf Werkzeuge). Lesende Werkzeuge liefern weiter, solange
    PBP in Claude Desktop eingetragen ist. Der Satz „… gibt PBP für diesen Bereich nichts an Claude weiter“ war deshalb falsch."""
    quelle = (FRONTEND / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    assert "gibt PBP für diesen Bereich nichts an Claude weiter" not in quelle
    assert "führt PBP diese Funktion nicht aus und sagt das" in quelle
    assert "Claude kann Daten dennoch lesen, solange PBP in Claude Desktop eingetragen ist" in quelle


# ══ #1139: die Oberfläche verspricht keine Automatik, die nur auf Knopfdruck läuft ═══════════════════════════════

def test_1139_die_automatik_texte_sagen_was_wirklich_geschieht():
    """Bis v1.7.157 hatte die Aufräum-Runde keinen automatischen Auslöser, und die Texte sagten ehrlich „nur über Jetzt prüfen“.
    Ab 1.8.0 läuft sie einmal am Tag von selbst (Variante A, #1139); das Abschließen ist ein eigener Schalter, Vorgabe aus.
    Die Texte nennen beides: den täglichen Lauf, den Schalter und den Knopf."""
    einstellungen = (FRONTEND / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    ein = " ".join(einstellungen.split())
    assert "einmal am Tag von selbst" in ein
    assert "Das geschieht, wenn du unten „Jetzt prüfen“ drückst" not in ein, "die ehrliche Fassung von v1.7.157 ist überholt"
    assert "tut es von selbst nur, wenn du das unten einschaltest" in ein
    assert "Beim täglichen Lauf von selbst abschließen" in ein and "Aus: PBP schließt nur ab, wenn du unten „Jetzt prüfen“ drückst" in ein
    assert "kommt die nächste beim nächsten Prüfen (täglich von selbst oder per „Jetzt prüfen“)" in ein
    hilfe = (FRONTEND / "lib" / "hilfe.js").read_text(encoding="utf-8-sig")
    assert "der Rest folgt mit der Automatik" not in hilfe
    assert "holt die tägliche Prüfung nach" in hilfe
    hinweis = (FRONTEND / "lib" / "jobsucheHinweis.js").read_text(encoding="utf-8-sig")
    assert "folgen mit der Automatik`" not in hinweis
    assert "weitere holt die nächste Prüfung nach" in hinweis
