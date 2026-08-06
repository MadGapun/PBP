"""Tests fuer v1.7.11 — #790 (C31) Blacklist-Ausnahmen + #807 (B29) BA-API v6.

#790: Ein Firmen-Block wirkt pauschal, seine Begruendung stammt aber fast
immer aus der Bewertung EINER Stelle. Bei Personaldienstleistern, die quer
durch alle Fachgebiete ausschreiben, wirft das die passenden Treffer mit
weg — belegt am 25.07.2026: ein Block mit der Begruendung "kein PLM-Fit"
blockte eine PLM-Stelle.

#807: Die Bundesagentur-Suche lief auf API v4 — die liefert seit Sommer
2026 HTTP 404. Damit war die produktivste Quelle still tot. Hier nur der
Regressionstest auf Endpunkt und Feld-Mapping (kein Netzzugriff).
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1711_790_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _result(raw):
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if hasattr(raw, "structured_content"):
        raw = raw.structured_content
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return raw


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


# ------------------------------------------------------------ #790

def test_790_ausnahme_laesst_fachrolle_durch(setup_env):
    """Der belegte Fall: Dienstleister geblockt, PLM-Rolle passt trotzdem."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma",
        "wert": "Dienstleister Nord",
        "grund": "Zeitarbeit/Consulting — falsche Technologie-Stacks",
        "ausser_wenn_titel_enthaelt": ["PLM", "PDM"]}))
    assert res["status"] == "hinzugefuegt"
    assert res["ausser_wenn_titel_enthaelt"] == ["PLM", "PDM"]

    # Fachlich passende Rolle: kommt durch
    passt = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "PLM Dokumentenmanager & Prozessmanager (m/w/d)",
        "firma": "Dienstleister Nord GmbH", "ort": "Hamburg",
        "url": "https://example.com/plm-1"}))
    assert passt["status"] == "angelegt", passt
    assert passt["blacklist_ausnahme"]["begriff"] == "PLM"

    # Beliebige andere Rolle: bleibt geblockt
    blockt = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "SPS-Programmierer (m/w/d)",
        "firma": "Dienstleister Nord GmbH", "ort": "Hamburg",
        "url": "https://example.com/sps-1"}))
    assert "fehler" in blockt
    assert "Blacklist" in blockt["fehler"]


def test_790_ohne_ausnahme_unveraendert(setup_env):
    """Bestehende Eintraege verhalten sich exakt wie bisher."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Ganz Geblockt AG"})
    res = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "PLM Manager (m/w/d)", "firma": "Ganz Geblockt AG",
        "url": "https://example.com/x"}))
    assert "fehler" in res, "ohne Ausnahme muss alles blocken"


def test_790_hinweis_statt_force(setup_env):
    """Die Fehlermeldung soll den sauberen Weg zeigen, nicht nur force."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Vermittler X"})
    res = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "PLM Berater", "firma": "Vermittler X", "url": "https://e.example/1"}))
    assert "hinweis_ausnahme" in res
    assert "ausser_wenn_titel_enthaelt" in res["hinweis_ausnahme"]


def test_790_sofort_deaktivierung_verschont_ausnahme(setup_env):
    """Beim Anlegen des Blocks duerfen Ausnahme-Stellen nicht mitsterben."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    db.save_jobs([
        {"hash": "keep1", "title": "PLM Projektleiter", "company": "Dienst AG",
         "location": "HH", "url": "https://e.example/k", "source": "demo",
         "description": "PLM. " * 30, "employment_type": "festanstellung"},
        {"hash": "kill1", "title": "Elektriker", "company": "Dienst AG",
         "location": "HH", "url": "https://e.example/t", "source": "demo",
         "description": "Elektro. " * 30, "employment_type": "festanstellung"},
    ])
    _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Dienst AG",
        "ausser_wenn_titel_enthaelt": ["PLM"]})
    assert db.get_job("keep1")["is_active"] == 1, "PLM-Stelle muss bleiben"
    assert db.get_job("kill1")["is_active"] == 0


def test_790_retroaktiv_verschont_ausnahme(setup_env):
    """blacklist_anwenden darf nicht wieder wegraeumen, was die Ausnahme
    gerade durchgelassen hat."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Spaet AG",
        "ausser_wenn_titel_enthaelt": ["PDM"]})
    db.save_jobs([
        {"hash": "spaet1", "title": "PDM Spezialist", "company": "Spaet AG",
         "location": "HH", "url": "https://e.example/p", "source": "demo",
         "description": "PDM. " * 30, "employment_type": "festanstellung"},
        {"hash": "spaet2", "title": "Lagerist", "company": "Spaet AG",
         "location": "HH", "url": "https://e.example/l", "source": "demo",
         "description": "Lager. " * 30, "employment_type": "festanstellung"},
    ])
    res = _result(_call(mcp, "blacklist_anwenden", {"dry_run": False}))
    assert db.get_job("spaet1")["is_active"] == 1, res
    assert db.get_job("spaet2")["is_active"] == 0


def test_790_anzeigen_listet_ausnahmen(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Mit Ausnahme AG",
        "ausser_wenn_titel_enthaelt": ["PLM"]})
    res = _result(_call(mcp, "blacklist_verwalten", {"aktion": "anzeigen"}))
    assert "mit_titel_ausnahme" in res
    assert res["mit_titel_ausnahme"][0]["ausser_wenn_titel_enthaelt"] == ["PLM"]


# ------------------------------------------------------------ #807

def test_806_suche_nutzt_v6_details_bleiben_v4():
    """Regression: die Endpunkte duerfen nicht wieder auseinanderlaufen.

    Live geprueft am 06.08.2026: Suche v4/v5 -> 404, v6 -> 200;
    Details v4 -> 200, v5/v6 -> 403.
    """
    from bewerbungs_assistent.job_scraper import bundesagentur as ba
    assert "/pc/v6/jobs" in ba.API_URL, ba.API_URL
    assert "/pc/v4/jobdetails/" in ba.DETAIL_URL, ba.DETAIL_URL


def test_806_health_probe_zeigt_auf_denselben_endpunkt():
    """Sonst prueft der Health-Check etwas anderes als die Suche nutzt —
    genau so blieb der Ausfall wochenlang unbemerkt."""
    from bewerbungs_assistent.job_scraper import bundesagentur as ba
    from bewerbungs_assistent.job_scraper.health import _PROBES
    probe_url = _PROBES["bundesagentur"][1]
    assert "/pc/v6/jobs" in probe_url, probe_url
    assert ba.API_URL.split("?")[0] in probe_url


def test_806_v6_feldnamen_werden_gelesen(monkeypatch):
    """Das v6-Schema hat alle Felder umbenannt — ohne Mapping kaeme eine
    Liste leerer Stellen zurueck (schlimmer als ein Fehler)."""
    from bewerbungs_assistent.job_scraper import bundesagentur as ba

    v6_antwort = {
        "maxErgebnisse": 1,
        "ergebnisliste": [{
            "stellenangebotsTitel": "PLM Project Manager (m/w/d)",
            "firma": "Beispiel GmbH",
            "hauptberuf": "Projektleiter/in",
            "referenznummer": "11937-32939_58530-1-S",
            "stellenlokationen": [
                {"adresse": {"plz": "22297", "ort": "Hamburg"}}],
        }],
    }

    class _Resp:
        status_code = 200
        def json(self):
            return v6_antwort

    monkeypatch.setattr(ba, "_request_with_retry",
                        lambda *a, **k: _Resp())
    monkeypatch.setattr(ba, "_fetch_ba_detail", lambda *a, **k: "")
    jobs = ba.search_bundesagentur({"keywords": ["PLM"], "criteria": {}})
    assert len(jobs) == 1
    j = jobs[0]
    assert j["title"] == "PLM Project Manager (m/w/d)"
    assert j["company"] == "Beispiel GmbH"
    assert j["location"] == "Hamburg"
    assert "11937-32939_58530-1-S" in j["url"]


def test_806_v4_format_bleibt_lesbar(monkeypatch):
    """Fallback: falls ein Server doch wieder v4-Namen liefert, darf der
    Adapter nicht stumm nichts finden."""
    from bewerbungs_assistent.job_scraper import bundesagentur as ba

    class _Resp:
        status_code = 200
        def json(self):
            return {"stellenangebote": [{
                "titel": "Alt-Format Rolle", "arbeitgeber": "Alt GmbH",
                "arbeitsort": {"ort": "Bremen"}, "refnr": "X-1",
                "beruf": "Ingenieur/in"}]}

    monkeypatch.setattr(ba, "_request_with_retry", lambda *a, **k: _Resp())
    monkeypatch.setattr(ba, "_fetch_ba_detail", lambda *a, **k: "")
    jobs = ba.search_bundesagentur({"keywords": ["X"], "criteria": {}})
    assert len(jobs) == 1
    assert jobs[0]["title"] == "Alt-Format Rolle"
    assert jobs[0]["location"] == "Bremen"
