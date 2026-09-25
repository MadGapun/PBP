"""Welle 3 aus #1087 — Einstieg und Hinweiszone (G59, G60, G63, B69, I15).

Server- und Quelltext-Seite. Die Oberflaeche belegt
`test_g1087_welle3_oberflaeche.py` im gerenderten Dashboard.
"""
import asyncio
import importlib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))
FRONTEND = _repo() / "frontend" / "src"
PAKET = _repo() / "src" / "bewerbungs_assistent"


def _lesen(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8-sig")


# ══ I15 — Installer-Abschluss ═══════════════════════════════════════════

BAT = _repo() / "INSTALLIEREN.bat"


def test_i15_gruen_nur_wenn_claude_und_dashboard_ok():
    t = _lesen(BAT)
    assert 'set "CLAUDE_OK=0"' in t and 'set "CLAUDE_OK=1"' in t
    # CLAUDE_OK=1 steht NACH dem erfolgreichen Aufruf, nicht davor.
    assert t.index('set "CLAUDE_OK=0"') < t.index("_setup_claude.py\" >>") < t.index('set "CLAUDE_OK=1"')
    assert 'if not "!CLAUDE_OK!"=="1" set "AMPEL=GELB"' in t
    assert 'if not "!DASH_OK!"=="1" set "AMPEL=GELB"' in t


def test_i15_kein_unbedingtes_erfolgreich():
    t = _lesen(BAT)
    # Die Sprungmarken am Zeilenanfang, nicht die goto-Zeilen davor.
    gruen = re.search(r"^:ampel_gruen\s*$", t, re.M).start()
    gelb = re.search(r"^:ampel_gelb\s*$", t, re.M).start()
    erfolg = t.index("E R F O L G R E I C H")
    assert gruen < erfolg < gelb, "ERFOLGREICH steht nur im gruenen Zweig"
    assert "[GELB]" in t


def test_i15_verweist_auf_den_gruenen_punkt_und_den_startsatz():
    t = _lesen(BAT)
    teil = t[t.index("ERSTE SCHRITTE"):]
    assert "Claude Desktop: verbunden" in teil
    assert "Starte die Ersterfassung" in teil
    assert "Ersterfassung starten" not in t


# ══ G59 — ein Startsatz, kein Overlay, "laeuft" erst nach dem Werkzeug ══

STARTSATZ_ORTE = [
    FRONTEND / "App.jsx", FRONTEND / "pages" / "DashboardPage.jsx",
    FRONTEND / "lib" / "hilfe.js", FRONTEND / "components" / "HilfeInhalt.jsx",
    FRONTEND / "components" / "ProfileOnboarding.jsx",
    PAKET / "prompts.py", _repo() / "README.md",
    _repo() / "installer" / "install.ps1", _repo() / "installer" / "setup_gui.py", BAT,
]


def test_g59_nur_ein_startsatz():
    befunde = []
    for pfad in STARTSATZ_ORTE:
        text = _lesen(pfad)
        for alt in ("Ersterfassung starten", "Kennlerngespräch starten", "/ersterfassung kopieren"):
            for m in re.finditer(re.escape(alt), text):
                # "ersterfassung_starten" ist ein Werkzeugname, kein Satz.
                befunde.append(f"{pfad.name}: {alt}")
    assert not befunde, befunde


def test_g59_startsatz_ist_ueberall_derselbe():
    from bewerbungs_assistent.services.nutzerfuehrung import STARTSATZ
    js = _lesen(FRONTEND / "lib" / "startsatz.js")
    assert f'export const STARTSATZ = "{STARTSATZ}";' in js


def test_g59_kein_overlay_mehr():
    app = _lesen(FRONTEND / "App.jsx")
    assert 'id="wizard-overlay"' not in app
    dash = _lesen(FRONTEND / "pages" / "DashboardPage.jsx")
    assert "data-erklaerkasten" in dash and "So arbeiten Dashboard und Claude zusammen" in dash
    assert 'copyPrompt("/ersterfassung")' in dash


def test_g59_kopieren_setzt_nicht_laeuft():
    app = _lesen(FRONTEND / "App.jsx")
    rumpf = app[app.index("async function copyPrompt("):]
    rumpf = rumpf[:rumpf.index("\n  }\n") if "\n  }\n" in rumpf else 4000]
    assert "profile_onboarding_started_" not in rumpf
    onb = _lesen(FRONTEND / "components" / "ProfileOnboarding.jsx")
    kopieren = onb[onb.index("async function copyConversationCommand"):]
    kopieren = kopieren[:kopieren.index("\n  }\n")]
    assert "copyPrompt(CONVERSATION_COMMAND)" in kopieren
    assert "profile_onboarding_started_" not in kopieren
    assert "copyToClipboard" not in kopieren


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_g1087w3_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    import bewerbungs_assistent.dashboard as dash
    alt = dash._db
    dash._db = db
    yield db, _srv_mod.mcp, dash
    dash._db = alt
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        return await tool.run(args or {})
    return asyncio.run(_run())


def test_g59_laeuft_erst_wenn_claude_das_werkzeug_aufruft(umgebung):
    db, mcp, _ = umgebung
    pid = db.save_profile({"name": "Erika Musterfrau"})
    key = f"profile_onboarding_conversation_{pid}"
    assert db.get_user_preference(key) in (None, "", "idle")
    _call(mcp, "ersterfassung_starten")
    assert db.get_user_preference(key) == "active"
    assert db.get_user_preference(f"profile_onboarding_started_{pid}") is True


# ══ G60 — Hinweiszone ═══════════════════════════════════════════════════

def test_g60_globale_banner_sind_weg():
    app = _lesen(FRONTEND / "App.jsx")
    assert "<strong>Stand unbekannt</strong>" not in app
    assert 'id="source-banner"' not in app
    assert "Neue Version verfuegbar: <strong>" not in app
    strip = app[app.index("const showWorkspaceStrip ="):]
    strip = strip[:strip.index(";")]
    assert 'page === "dashboard"' in strip


def test_g60_dashboard_nutzt_die_zone():
    dash = _lesen(FRONTEND / "pages" / "DashboardPage.jsx")
    assert "hinweisFuer(" in dash and "<HinweisZone hinweis={hinweis} />" in dash
    # Zone ODER Folgehinweis, nie beides: der Folgehinweis steht im
    # else-Zweig derselben Bedingung, und jeder zeigt hoechstens einen.
    flach = dash.replace("\r\n", "\n")
    assert "{hinweis ? (\n        <HinweisZone hinweis={hinweis} />\n      ) : (" in flach
    assert '<OnboardingHintBanner tab="dashboard" limit={1}' in dash
    assert '<AdaptiveHintBanner page="dashboard" limit={1}' in dash
    assert "sichtbarePublic.slice(0, 1)" in dash
    assert 'id: "jobsuche",\n      title: "Neue Jobsuche starten"' not in dash.replace("\r\n", "\n")
    # Ollama-Angebot erst nach dem Einstieg.
    assert "einstiegFertig && <LocalAiAutoDetectBanner" in dash


def test_g60_hinweiszone_node_test_in_der_ci():
    ci = _lesen(_repo() / ".github" / "workflows" / "tests.yml")
    assert "node frontend/src/lib/hinweisZone.test.mjs" in ci


def test_g60_seitenleiste_optional_grau():
    sb = _lesen(FRONTEND / "components" / "Sidebar.jsx")
    assert "Lokale KI: nicht eingerichtet (optional)" in sb
    zeile = next(z for z in sb.splitlines() if "not_installed:" in z)
    assert "coral" not in zeile
    assert "Claude Desktop: nicht verbunden" in sb
    assert "brand.hasProfile" in sb


# ══ G63 — Leerzustaende nach Stufe ══════════════════════════════════════

def test_g63_ohne_profil_zuerst_das_profil():
    for datei in ("JobsPage.jsx", "ApplicationsPage.jsx"):
        text = _lesen(FRONTEND / "pages" / datei)
        assert "if (!chrome.status?.has_profile) return ZUERST_PROFIL_STATUS;" in text, datei
        assert "<ZuerstProfil bereich=" in text, datei


# ══ B69 — Erstauswahl der Quellen ═══════════════════════════════════════

def test_b69_erstauswahl_ist_die_empfehlung(umgebung):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    from bewerbungs_assistent.services.search_service import (
        erstauswahl, get_default_active_source_keys)
    db, _mcp, dash = umgebung
    db.save_profile({"name": "Erika Musterfrau", "summary": "Industriekauffrau, Einkauf"})
    c = TestClient(dash.app)
    rows = c.get("/api/sources").json()
    aktiv = sorted(r["key"] for r in rows if r.get("active"))
    erwartet = sorted(erstauswahl(db, SOURCE_REGISTRY)["quellen"])
    assert aktiv == erwartet
    assert len(aktiv) < len(get_default_active_source_keys(SOURCE_REGISTRY)), \
        "Die Erstauswahl darf nicht mehr 'alles ohne Login' sein"
    info = c.get("/api/sources/erstauswahl").json()
    assert info["offen"] is True and info["namen"]


def test_b69_eigene_auswahl_bestaetigt(umgebung):
    from fastapi.testclient import TestClient
    db, _mcp, dash = umgebung
    db.save_profile({"name": "Erika Musterfrau"})
    c = TestClient(dash.app)
    c.get("/api/sources")
    assert c.get("/api/sources/erstauswahl").json()["offen"] is True
    c.post("/api/sources", json={"active_sources": ["bundesagentur"]})
    assert c.get("/api/sources/erstauswahl").json()["offen"] is False


def test_b69_bestaetigen_schliesst_den_hinweis(umgebung):
    from fastapi.testclient import TestClient
    db, _mcp, dash = umgebung
    db.save_profile({"name": "Erika Musterfrau"})
    c = TestClient(dash.app)
    c.get("/api/sources")
    c.post("/api/sources/erstauswahl/bestaetigen")
    assert c.get("/api/sources/erstauswahl").json()["offen"] is False


def test_b69_ohne_empfehlung_die_startquellen(umgebung, monkeypatch):
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    from bewerbungs_assistent.services import search_service, profile_classifier
    db, _mcp, _dash = umgebung
    db.save_profile({"name": "Erika Musterfrau"})
    monkeypatch.setattr(profile_classifier, "recommend_sources", lambda *a, **k: {"recommended": []})
    erg = search_service.erstauswahl(db, SOURCE_REGISTRY)
    assert erg["grundlage"] == "start"
    assert set(erg["quellen"]) <= set(search_service.START_QUELLEN)
