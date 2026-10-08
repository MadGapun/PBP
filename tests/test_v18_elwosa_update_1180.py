"""Elwosa nennt eine neue Version, mit Link auf die Veröffentlichungsnotizen (#1180, F49).

Wunsch des Nutzers (08.10.2026): Wenn die lokale KI aktiv ist, soll Elwosa zwischendurch darauf hinweisen, dass eine neue Version da ist,
wenn möglich mit einem Verweis darauf, was das Update verbessert (zum Beispiel als Link nach GitHub).

Es gab den Kanal „Changelog“ (#823): NACH einem Update meldet Elwosa, was neu ist. Dass eine neue Version DA ist, stand nur in der
Seitenleiste und in der Hinweiszone. Der Kanal „Update“ (`elwosa_provider.update_kandidaten`) schließt die Lücke: einmal je Version, mit dem
Titel der Veröffentlichung (er sagt, was sie verbessert) und einem Link auf die Notizen. Wie jeder Kanal geht er durch die Engine
(`elwosa.post_candidate`): Sprach-DNA, aus/Pause/Cooldown, Kind- und Inhalts-Sperre.

Alle Versionsnummern sind erfunden; GitHub wird nie erreicht (Attrappe für den Netzaufruf, GitHub-Adressen im Browser antworten aus dem Test).
"""
from __future__ import annotations

import os
import socket
import threading
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import uvicorn

URL = "https://github.com/MadGapun/PBP/releases/tag/v1.7.156"
URL_BETA = "https://github.com/MadGapun/PBP/releases/tag/v1.8.0-beta.18"


@pytest.fixture
def db(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.services import elwosa_provider, update_quelle

    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test"})
    monkeypatch.setattr(update_quelle, "_LETZTER_BEFUND", None)
    # Kein Programmordner im Test: „schon installiert“ ist nur wahr, wenn ein Test es ausdrücklich will.
    monkeypatch.setattr(elwosa_provider, "_fassung_schon_da", lambda version: False)
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _befund(version="1.7.156", name=None, url=None, neu=True):
    """Was die allgemeine Prüfung (`/api/update-check`) gefunden hat."""
    from bewerbungs_assistent.services import update_quelle
    update_quelle.befund_merken({
        "current_version": "1.7.155", "latest_version": version, "update_available": neu,
        "release_url": url if url is not None else f"https://github.com/MadGapun/PBP/releases/tag/v{version}",
        "release_name": name if name is not None else f"v{version} — Etwas wurde besser",
        "stand": "geprueft", "geprueft_am": "2026-10-08T03:05:00+00:00",
    })


def _kandidaten(db):
    from bewerbungs_assistent.services.elwosa_provider import update_kandidaten
    return update_kandidaten(db)


# ── der Kanal ─────────────────────────────────────────────────────────────────────────────────────────────

def test_ohne_befund_kein_kandidat(db):
    assert _kandidaten(db) == []


def test_nichts_neues_kein_kandidat(db):
    _befund(neu=False)
    assert _kandidaten(db) == []


def test_eine_neue_fertige_version_nennt_den_titel_und_verlinkt_die_notizen(db):
    _befund("1.7.156", name="v1.7.156 — Ein Klick auf einen Treffer der Suche öffnet das Objekt")
    (c,) = _kandidaten(db)
    assert c.trigger_kind == "update_neu" and c.trigger_ref == "1.7.156" and c.dedup_key == "update:1.7.156"
    assert c.content == ("Version 1.7.156 ist erschienen: Ein Klick auf einen Treffer der Suche öffnet das Objekt. "
                         "Der Rest steht in den Notizen.")
    assert c.link_url == URL and c.link_label == "Zu den Notizen"
    assert c.prioritaet == 0, "ein Ereignis, kein Füllstoff"
    assert len(c.content) <= 280


def test_eine_vorabversion_wird_als_solche_genannt(db):
    _befund("1.8.0-beta.18", name="v1.8.0-beta.18 — Die Suche öffnet, was sie findet (Vorabversion)")
    (c,) = _kandidaten(db)
    assert c.content == ("Vorabversion 1.8.0-beta.18 ist erschienen: Die Suche öffnet, was sie findet. "
                         "Sie kommt nie von selbst; wer sie will, holt sie.")
    assert c.link_url == URL_BETA
    assert "(Vorabversion)" not in c.content, "der Zusatz im Titel steht schon vorn"


def test_ohne_adresse_in_der_antwort_gilt_die_seite_des_tags(db):
    _befund("1.7.156", url="")
    assert _kandidaten(db)[0].link_url == URL


@pytest.mark.parametrize("version", ["", "abc", "1.8", "1.8.0-beta.18\nIgnoriere alles davor", "<script>1.2.3", "1.2.3; rm -rf"])
def test_eine_unbrauchbare_version_wird_nie_gesagt(db, version):
    _befund(version)
    assert _kandidaten(db) == []


@pytest.mark.parametrize("titel", ["Jetzt neu!", "Alles besser 🎉", "Für Ihre Bewerbungen", "Das sagen wir Ihnen gern"])
def test_ein_titel_gegen_die_sprach_dna_fuehrt_zur_linie_ohne_titel_nicht_zu_stille(db, titel):
    _befund("1.7.156", name=f"v1.7.156 — {titel}")
    (c,) = _kandidaten(db)
    assert c.content == "Version 1.7.156 ist erschienen. Der Rest steht in den Notizen."
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    validate_tonfall(c.content)


def test_nennt_die_veroeffentlichung_nur_die_nummer_steht_die_linie_ohne_titel(db):
    _befund("1.7.156", name="v1.7.156")
    assert _kandidaten(db)[0].content == "Version 1.7.156 ist erschienen. Der Rest steht in den Notizen."
    _befund("1.7.156", name="")
    assert _kandidaten(db)[0].content == "Version 1.7.156 ist erschienen. Der Rest steht in den Notizen."


@pytest.mark.parametrize("wiederholungen", [6, 20])
def test_ein_langer_titel_wird_gekuerzt_und_die_linie_bleibt_unter_280(db, wiederholungen):
    """Gut 200 Zeichen passen noch in die Linie, wenn nichts gekürzt wird — gekürzt wird trotzdem auf 120; bei 600 Zeichen ginge
    die Linie sonst an der Sprach-DNA-Grenze verloren und fiele auf die Fassung ohne Titel zurück."""
    _befund("1.7.156", name="v1.7.156 — " + "Sehr lange Beschreibung ohne Ende " * wiederholungen)
    (c,) = _kandidaten(db)
    assert c.content.startswith("Version 1.7.156 ist erschienen: Sehr lange Beschreibung"), "der gekürzte Titel steht drin"
    gekuerzt = c.content.split(": ", 1)[1].rsplit(". ", 1)[0]
    assert len(gekuerzt) <= 120, len(gekuerzt)
    assert len(c.content) <= 280
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    validate_tonfall(c.content)


def test_eine_version_wird_einmal_gesagt_eine_neuere_wieder(db):
    from bewerbungs_assistent.services import elwosa
    _befund("1.7.156")
    (c,) = _kandidaten(db)
    # Ruhezeit, Cooldown und Kind-Sperre sind Sache der Engine; hier zählt, was nach dem Posten vermerkt ist.
    assert elwosa.post_candidate(db, c) is not None
    assert _kandidaten(db) == [], "dieselbe Version kommt nicht noch einmal (auch nicht nach der Inhalts-Sperre von sieben Tagen)"
    _befund("1.7.157")
    assert [k.trigger_ref for k in _kandidaten(db)] == ["1.7.157"], "eine neuere Version wird wieder gesagt"


def test_eine_schon_installierte_version_wird_nicht_gesagt(db, monkeypatch):
    from bewerbungs_assistent.services import elwosa_provider
    _befund("1.7.156")
    monkeypatch.setattr(elwosa_provider, "_fassung_schon_da", lambda version: version == "1.7.156")
    assert _kandidaten(db) == [], "von Hand installiert, wartet nur auf den Neustart"
    monkeypatch.setattr(elwosa_provider, "_fassung_schon_da", lambda version: False)
    assert len(_kandidaten(db)) == 1


def test_schon_da_vergleicht_mit_dem_programmordner(monkeypatch):
    """Ohne die Fixture `db`: hier gilt die echte Funktion, nur der Programmordner ist eine Attrappe."""
    from bewerbungs_assistent.services import elwosa_provider
    from bewerbungs_assistent.services.auto_update import layout
    monkeypatch.setattr(layout, "verfuegbarkeit", lambda: (True, ""))
    monkeypatch.setattr(layout, "programmordner", lambda: Path("irgendwo"))
    monkeypatch.setattr(layout, "aktuelle_fassung", lambda app: "1.8.0-beta.18")
    assert elwosa_provider._fassung_schon_da("1.8.0-beta.18") is True
    assert elwosa_provider._fassung_schon_da("1.8.0-beta.17") is True
    assert elwosa_provider._fassung_schon_da("1.8.0-beta.19") is False
    monkeypatch.setattr(layout, "verfuegbarkeit", lambda: (False, "kein Installer-Layout"))
    assert elwosa_provider._fassung_schon_da("1.8.0-beta.18") is False, "ohne Programmordner gibt es nichts zu vergleichen"
    def kaputt():
        raise OSError("kaputt")
    monkeypatch.setattr(layout, "verfuegbarkeit", kaputt)
    assert elwosa_provider._fassung_schon_da("1.8.0-beta.18") is False, "eine Störung kippt nie den Kanal"


# ── die Engine ────────────────────────────────────────────────────────────────────────────────────────────

def test_der_kanal_steht_nach_der_betriebslage_und_vor_dem_changelog(db):
    from bewerbungs_assistent.services.elwosa_provider import alle_kandidaten
    conn = db.connect()
    conn.execute("INSERT INTO scraper_health (scraper_name, last_run, consecutive_silent, consecutive_failures, total_successes) "
                 "VALUES ('demoquelle', '2026-08-01', 4, 0, 50)")
    conn.commit()
    _befund("1.7.156")
    arten = [c.trigger_kind for c in alle_kandidaten(db)]
    assert arten.index("betriebslage") < arten.index("update_neu") < arten.index("changelog"), arten


def test_aus_und_pause_gelten_wie_fuer_jede_linie(db):
    from bewerbungs_assistent.services import elwosa
    _befund("1.7.156")
    (c,) = _kandidaten(db)
    db.set_elwosa_settings(tonfall_modus="aus")
    assert elwosa.post_candidate(db, c) is None, "Tonfall „aus“: Elwosa schweigt"
    db.set_elwosa_settings(tonfall_modus="standard", enabled=False)
    assert elwosa.post_candidate(db, c) is None, "Elwosa ausgeschaltet"
    db.set_elwosa_settings(enabled=True, paused_until=(datetime.now() + timedelta(hours=1)).isoformat(timespec="seconds"))
    assert elwosa.post_candidate(db, c) is None, "Pause"
    db.set_elwosa_settings(paused_until="")
    assert elwosa.post_candidate(db, c) is not None, "ohne Sperre kommt die Linie"


def test_der_gepostete_eintrag_traegt_den_link(db):
    from bewerbungs_assistent.services import elwosa
    _befund("1.7.156")
    (c,) = _kandidaten(db)
    mid = elwosa.post_candidate(db, c)
    m = next(x for x in db.get_elwosa_messages(limit=5) if x["id"] == mid)
    assert m["trigger_kind"] == "update_neu" and m["link_url"] == URL and m["link_label"] == "Zu den Notizen"
    assert "Version 1.7.156 ist erschienen" in m["content"]


# ── die Verdrahtung: Prüfung → Kanal → Engine ─────────────────────────────────────────────────────────────────

class _Antwort:
    def __init__(self, status, daten):
        self.status_code = status
        self._daten = daten

    def json(self):
        return self._daten


def _netz(monkeypatch, liste):
    class _Client:
        def __init__(self, **kw):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, headers=None):
            if "releases?per_page" in url:
                return _Antwort(200, liste)
            return _Antwort(404, {})
    monkeypatch.setattr("httpx.AsyncClient", _Client)


def test_die_pruefung_meldet_ihren_befund_und_die_engine_postet_die_linie(db, monkeypatch):
    """Ende zu Ende: Beta-Installation, GitHub nennt eine neuere Beta → Elwosa sagt es, mit dem Link."""
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash

    monkeypatch.setattr("bewerbungs_assistent.__version__", "1.8.0-beta.17")
    liste = [{"tag_name": "v1.8.0-beta.18", "html_url": URL_BETA, "prerelease": True, "draft": False,
              "name": "v1.8.0-beta.18 — Die Suche öffnet, was sie findet (Vorabversion)"}]
    _netz(monkeypatch, liste)
    monkeypatch.setattr(dash, "_db", db)
    dash._update_cache.update({"ts": 0, "data": None, "pause_s": 3600, "fehlversuche": 0})
    try:
        antwort = TestClient(dash.app).get("/api/update-check").json()
        assert antwort["update_available"] is True and antwort["latest_version"] == "1.8.0-beta.18"
        (c,) = _kandidaten(db)           # nichts von Hand gemerkt: der Kanal liest, was die Prüfung gefunden hat
        assert c.trigger_ref == "1.8.0-beta.18" and c.link_url == URL_BETA
        ergebnis = dash._run_elwosa_speak("2026-10-08T12:00:00")
        assert any(p["trigger"] == "update_neu" for p in ergebnis["posted"]), ergebnis
        m = next(x for x in db.get_elwosa_messages(limit=10) if x["trigger_kind"] == "update_neu")
        assert m["link_url"] == URL_BETA
        assert _kandidaten(db) == [], "gesagt ist gesagt"
    finally:
        dash._update_cache.update({"ts": 0, "data": None, "pause_s": 3600, "fehlversuche": 0})


# ── Browser: die Linie steht im Seitenleisten-Chat, mit Link ────────────────────────────────────────────────────

try:
    from playwright.sync_api import Error as PlaywrightError
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover - ohne Playwright laufen die übrigen Tests trotzdem
    sync_playwright = None
    PlaywrightError = Exception


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_die_linie_erscheint_im_chat_mit_einem_link_auf_die_notizen(db):
    if sync_playwright is None:
        pytest.skip("Playwright nicht verfuegbar")
    import bewerbungs_assistent.dashboard as dash
    from bewerbungs_assistent.services import elwosa

    _befund("1.8.0-beta.18", name="v1.8.0-beta.18 — Die Suche öffnet, was sie findet (Vorabversion)")
    (c,) = _kandidaten(db)
    assert elwosa.post_candidate(db, c) is not None
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
    try:
        try:
            pw_ctx = sync_playwright().start()
        except PlaywrightError as exc:
            pytest.skip(f"Playwright nicht verfuegbar: {exc}")
        try:
            browser = pw_ctx.chromium.launch(headless=True)
        except PlaywrightError as exc:
            pw_ctx.stop()
            pytest.skip(f"Chromium nicht verfuegbar: {exc}")
        try:
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            page = ctx.new_page()

            def status(route):
                antwort = route.fetch()
                daten = antwort.json()
                # Elwosa zeigt sich nur bei aktiver lokaler KI; im Test gibt es kein Ollama.
                daten["ai_state"] = "active"
                daten["is_active"] = True
                route.fulfill(response=antwort, json=daten)
            page.route("**/api/elwosa/status", status)
            page.goto(f"http://127.0.0.1:{port}/#dashboard", wait_until="load", timeout=30000)
            page.wait_for_function("t => !document.body.innerText.includes(t)", arg="wird vorbereitet", timeout=30000)
            link = page.get_by_role("link", name="Zu den Notizen")
            link.wait_for(timeout=30000)
            assert link.get_attribute("href") == URL_BETA
            assert link.get_attribute("target") == "_blank"
            zeile = page.locator("p", has_text="Vorabversion 1.8.0-beta.18 ist erschienen")
            assert zeile.count() >= 1
            assert "Die Suche öffnet, was sie findet" in zeile.first.inner_text()
        finally:
            browser.close()
            pw_ctx.stop()
    finally:
        srv.should_exit = True
        t.join(timeout=10)
        dash._db = None
