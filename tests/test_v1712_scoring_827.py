"""Tests fuer v1.7.12 — #827 (C32): Scoring-Fixes.

Belegter Fall 11.08.2026: Eine fachfremde Servicetechniker-Stelle
erreichte Score 36 und stand ueber einer Zielprofil-Rolle — alle acht
Keyword-Treffer sassen im Selbstdarstellungs-Absatz des Dienstleisters
("allen voran PLM und ERP"), keiner in der Aufgabenbeschreibung. Dazu
wurden Begriffe, die in MUSS UND PLUS stehen, doppelt gewertet, und die
Liste sortierte rein nach Score, obwohl das Wiedergaenger-k.o. bekannt war.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


# Nachgebaute Anzeige nach dem Muster des Belegfalls: Fachbegriffe NUR im
# Firmenabsatz, die Aufgaben sind fachfremd. Fiktive Firma.
BOILERPLATE_ANZEIGE = """\
Systemhaus Nord ist einer der fuehrenden IT-Dienstleister in Europa.
Wir gestalten zukunftsfaehige IT-Architekturen und zaehlen mit unseren
Tochterunternehmen zu den fuehrenden Spezialisten fuer Business
Applications, allen voran PLM und ERP. Unsere Multichannel-Strategie
verbindet Vertrieb und Product Lifecycle Beratung.

Deine Aufgaben:
- Notebooks und Desktops reparieren
- Ersatzteile bestellen und defekte Teile versenden
- First-Level-Support fuer Anwender

Dein Profil:
- Abgeschlossene technische Ausbildung
- Fuehrerschein Klasse B
"""

# Gegenprobe: dieselben Begriffe in der AUFGABENBESCHREIBUNG.
FACH_ANZEIGE = """\
Systemhaus Nord ist ein wachsendes Unternehmen im Maschinenbau.

Deine Aufgaben:
- PLM-Strategie fuer den Konzern entwickeln
- Product Lifecycle Prozesse harmonisieren
- PLM-Rollout in drei Werken leiten

Dein Profil:
- Mehrjaehrige PLM-Erfahrung
"""

CRITERIA = {
    "keywords_muss": ["PLM", "Product Lifecycle"],
    "keywords_plus": ["PLM", "Strategie", "Architektur"],
    "keywords_ausschluss": [],
    "keywords_minus": [],
}


def _job(description, title="IT Servicetechniker Onsite (w/m/d)"):
    return {"title": title, "description": description,
            "employment_type": "festanstellung"}


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1712_827_")
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


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _result(raw):
    if isinstance(raw, tuple):
        raw = raw[1] if len(raw) > 1 else raw[0]
    if hasattr(raw, "structured_content"):
        raw = raw.structured_content
    if isinstance(raw, list):
        raw = raw[0] if raw else {}
    return raw


# ---------------------------------------------- Firmenabsatz-Erkennung

def test_827_firmenabsatz_wird_erkannt():
    from bewerbungs_assistent.job_scraper import _firmenabsatz_ende
    grenze = _firmenabsatz_ende(BOILERPLATE_ANZEIGE)
    assert grenze > 0, "Aufgaben-Ueberschrift muss die Zone abgrenzen"
    assert "PLM und ERP" in BOILERPLATE_ANZEIGE[:grenze]
    assert "Notebooks" in BOILERPLATE_ANZEIGE[grenze:]


def test_827_anzeige_ohne_intro_bleibt_unangetastet():
    from bewerbungs_assistent.job_scraper import _firmenabsatz_ende
    direkt = "Deine Aufgaben:\n- PLM-Strategie entwickeln\n- Rollout leiten"
    assert _firmenabsatz_ende(direkt) == 0, \
        "Anzeige, die mit den Aufgaben beginnt, hat keine Firmenzone"


def test_827_boilerplate_treffer_werden_abgewertet():
    """DER Belegfall: gleiche Begriffe, einmal im Werbeabsatz, einmal in
    der Aufgabe — der Fach-Score muss deutlich hoeher liegen."""
    from bewerbungs_assistent.job_scraper import calculate_score
    boiler_job = _job(BOILERPLATE_ANZEIGE)
    fach_job = _job(FACH_ANZEIGE, title="PLM Project Team Lead (m/w/d)")
    boiler = calculate_score(boiler_job, dict(CRITERIA))
    fach = calculate_score(fach_job, dict(CRITERIA))
    assert fach > boiler, (
        f"Fachrolle ({fach}) muss ueber der Boilerplate-Rolle ({boiler}) "
        "liegen — genau andersherum war der Bug")
    assert boiler_job.get("_treffer_nur_firmenabsatz") is True
    assert "_treffer_nur_firmenabsatz" not in fach_job


def test_827_gate_bleibt_bestanden():
    """Treffer nur im Firmenabsatz duerfen NICHT zum 0-Score fuehren —
    ein falscher Ausschluss ist teurer als ein zu hoher Score."""
    from bewerbungs_assistent.job_scraper import calculate_score
    job = _job(BOILERPLATE_ANZEIGE)
    score = calculate_score(job, dict(CRITERIA))
    assert score > 0, "Gate muss bestanden bleiben (abgewertet, nicht genullt)"
    assert not job.get("_ko_kein_muss")


# ---------------------------------------------- MUSS/PLUS-Doppelzaehlung

def test_827_muss_plus_doppelt_zaehlt_nur_einmal():
    from bewerbungs_assistent.job_scraper import calculate_score
    text = "Deine Aufgaben:\n- PLM Systeme betreuen und PLM Prozesse pflegen"
    mit_doppel = calculate_score(
        _job(text, title="PLM Admin"),
        {"keywords_muss": ["PLM"], "keywords_plus": ["PLM"],
         "keywords_ausschluss": [], "keywords_minus": []})
    ohne_doppel = calculate_score(
        _job(text, title="PLM Admin"),
        {"keywords_muss": ["PLM"], "keywords_plus": [],
         "keywords_ausschluss": [], "keywords_minus": []})
    assert mit_doppel == ohne_doppel, \
        "PLM in MUSS und PLUS darf nur einmal gewertet werden"


def test_827_fit_analyse_konsistent_zur_liste():
    """fit_analyse muss dieselbe Dedup-/Firmenabsatz-Logik anwenden."""
    from bewerbungs_assistent.job_scraper import fit_analyse
    res = fit_analyse(_job(BOILERPLATE_ANZEIGE), dict(CRITERIA))
    assert any("FIRMENABSATZ" in r.upper() for r in res["risks"]), \
        f"Risiko-Hinweis fehlt: {res['risks']}"
    # PLM steht in MUSS und PLUS — in plus_hits darf es nicht auftauchen
    assert "PLM" not in res["plus_hits"]


def test_827_suchkriterien_setzen_warnt_bei_ueberschneidung(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "suchkriterien_setzen", {
        "keywords_muss": ["PLM", "PDM"],
        "keywords_plus": ["PLM", "Cloud"]}))
    assert "hinweis_ueberschneidung" in res
    assert "PLM" in res["hinweis_ueberschneidung"]


# ---------------------------------------------- Empfehlung in der Liste

def _stelle(db, h, title, company, score=30):
    db.save_jobs([{
        "hash": h, "title": title, "company": company, "location": "HH",
        "url": f"https://e.example/{h}", "source": "demo",
        "description": "Beschreibung. " * 20, "employment_type":
        "festanstellung", "score": score}])
    db.update_job(h, {"score": score})


def test_827_ko_stelle_sinkt_und_ist_markiert(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    pid = db.get_active_profile_id()
    conn = db.connect()
    # Neun aussortierte PLM-Onsite-Stellen derselben Firma -> Muster
    for i in range(9):
        conn.execute(
            "INSERT INTO jobs (hash, title, company, location, url, source, "
            "description, is_active, dismiss_reason, profile_id, found_at, "
            "updated_at, score) VALUES (?,?,?,?,?,?,?,0,'falsches_fachgebiet'"
            ",?,'2026-06-01','2026-06-01',5)",
            (f"alt{i}", f"IT Servicetechniker Onsite {i}",
             "Systemhaus Nord AG", "HH", f"https://a.example/{i}",
             "demo", "Text. " * 30, pid))
    conn.commit()
    # Hoher Score, aber k.o.-Firma — und eine passende Rolle mit weniger Score
    _stelle(db, "ko1", "IT Servicetechniker Onsite (w/m/d)",
            "Systemhaus Nord AG", score=36)
    _stelle(db, "gut1", "Project Team Lead SAP PLM",
            "Halbleiterwerk Nord GmbH", score=34)

    res = _result(_call(mcp, "stellen_anzeigen", {}))
    stellen = res["stellen"]
    ids = [s["hash"] for s in stellen]
    assert ids.index("gut1") < ids.index("ko1"), \
        "NICHT_EMPFOHLEN muss trotz hoeherem Score unter die Fachrolle"
    ko = next(s for s in stellen if s["hash"] == "ko1")
    assert ko.get("empfehlung", {}).get("kategorie") == "NICHT_EMPFOHLEN"
    assert "falsches_fachgebiet" in ko["empfehlung"]["ko_grund"]

    nur = _result(_call(mcp, "stellen_anzeigen", {"nur_empfohlen": True}))
    assert all(s["hash"] != "ko1" for s in nur["stellen"]), \
        "nur_empfohlen muss die k.o.-Stelle ausblenden"


# ---------------------------------------------- Geschaetzte Gehaelter

def test_827_geschaetztes_gehalt_ist_neutral(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services.scoring_service import (
        apply_scoring_adjustments)
    db.set_search_criteria("min_gehalt", 80000.0)
    # Dimension aktivieren (Default-Konfiguration laden)
    job_geschaetzt = {"hash": "g1", "title": "X", "company": "Y",
                      "salary_min": 54000, "salary_estimated": True,
                      "employment_type": "festanstellung"}
    res = apply_scoring_adjustments(job_geschaetzt, 20, db)
    gehalt_adj = [a for a in res.get("adjustments", [])
                  if a.get("dimension") == "Gehalt/Rate"]
    assert all(a["punkte"] == 0 for a in gehalt_adj), \
        f"Schaetzung darf nicht beitragen: {gehalt_adj}"

    job_echt = {"hash": "g2", "title": "X", "company": "Y",
                "salary_min": 54000, "salary_estimated": False,
                "employment_type": "festanstellung"}
    res2 = apply_scoring_adjustments(job_echt, 20, db)
    gehalt_echt = [a for a in res2.get("adjustments", [])
                   if a.get("dimension") == "Gehalt/Rate"]
    assert any(a["punkte"] != 0 for a in gehalt_echt), \
        "echte Angabe muss weiterhin wirken"
