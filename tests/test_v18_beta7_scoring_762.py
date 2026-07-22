"""Regression #762: harter Ausschluss-K.o. darf nicht fuzzy feuern.

Belegter Fall aus der Session 2026-07-22: Nach dem Nachpflegen eines echten
Anzeigen-Volltexts fiel der Score von 45 auf 0. Ursache war NICHT der
Recompute-Pfad in `stelle_bearbeiten` (der ist korrekt), sondern das
Fuzzy-Matching der AUSSCHLUSS-Keywords: bei einem Mehrwort-Keyword genuegte
es, dass die Einzelwoerter irgendwo im Text vorkamen (Multi-Word-Split in
`_fuzzy_keyword_match`). Je laenger der Text, desto wahrscheinlicher der
Fehlalarm — also ausgerechnet beim empfohlenen Volltext-Nachpflegen.

Fix: AUSSCHLUSS matcht strikt (`_strict_keyword_match`), wie MINUS seit #755.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_b7_762_")
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


# Realistischer Volltext: 'product' (in "product lifecycle") und 'manager'
# (in "manager der fachabteilung") stehen getrennt — die Rolle
# "Product Manager" kommt NICHT vor.
VOLLTEXT = (
    "Als PLM Consultant verantwortest du Change Management und die Integration "
    "nach SAP. Du steuerst Change-Prozesse ueber den gesamten product "
    "lifecycle. Ansprechpartner ist der manager der Fachabteilung. "
    "Teamcenter-Kenntnisse von Vorteil. Wir bieten hybrides Arbeiten in Hamburg."
)
KURZTEXT = "PLM Rolle mit Change Management Schwerpunkt."


def _criteria(db, ausschluss):
    db.set_search_criteria("keywords_muss", ["plm", "change management"])
    db.set_search_criteria("keywords_plus", ["teamcenter", "sap"])
    db.set_search_criteria("keywords_ausschluss", ausschluss)
    return db.get_search_criteria()


def test_762_mehrwort_ausschluss_feuert_nicht_im_volltext(setup_env):
    """'Product Manager' darf nicht feuern, nur weil die Woerter getrennt vorkommen."""
    db, _ = setup_env
    from bewerbungs_assistent.job_scraper import calculate_score
    crit = _criteria(db, ["Product Manager"])
    job = {"title": "PLM Consultant (m/w/d)", "description": VOLLTEXT,
           "employment_type": "festanstellung", "remote_level": "hybrid"}
    score = calculate_score(job, crit)
    assert score > 0, (
        "Fehlalarm: Mehrwort-Ausschluss feuerte auf getrennten Einzelwoertern "
        f"(Score {score}). Erwartet: kein K.o."
    )
    assert "_ko_ausschluss" not in job


def test_762_echter_ausschluss_treffer_bleibt_ko(setup_env):
    """Ein echter, zusammenhaengender Treffer muss weiterhin hart auf 0 setzen."""
    db, _ = setup_env
    from bewerbungs_assistent.job_scraper import calculate_score
    crit = _criteria(db, ["Zeitarbeit"])
    job = {"title": "PLM Consultant (m/w/d)",
           "description": VOLLTEXT + " Die Stelle wird ueber Zeitarbeit besetzt.",
           "employment_type": "festanstellung"}
    assert calculate_score(job, crit) == 0
    assert job.get("_ko_ausschluss") == "Zeitarbeit"


def test_762_volltext_nachpflegen_zerstoert_score_nicht(setup_env):
    """End-to-End: stelle_bearbeiten mit reicherem Volltext -> Score faellt nicht auf 0."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    from bewerbungs_assistent.job_scraper import stelle_hash, calculate_score
    crit = _criteria(db, ["Product Manager"])

    job = {
        "hash": stelle_hash("demo", "TestCo PLM Consultant"),
        "title": "PLM Consultant (m/w/d)", "company": "TestCo",
        "location": "Hamburg", "url": "https://example.de/job/1",
        "source": "demo", "description": KURZTEXT,
        "employment_type": "festanstellung", "remote_level": "hybrid",
    }
    job["score"] = calculate_score(job, crit)
    assert job["score"] > 0
    db.save_jobs([job])
    pub = db.get_job(job["hash"])

    res = _result(_call(mcp, "stelle_bearbeiten", {
        "job_hash": pub["hash"], "beschreibung": VOLLTEXT,
    }))
    recomputed = res.get("score_neu_berechnet") or {}
    assert recomputed.get("neuer_score", 0) > 0, (
        f"Volltext-Nachpflege hat den Score zerstoert: {res}"
    )


def test_762_kurztext_ist_keine_fachliche_absage(setup_env):
    """#762.2: Kurztext -> Score unzuverlaessig, kein 'Gap zu gross'-Urteil."""
    db, _ = setup_env
    from bewerbungs_assistent.job_scraper import fit_analyse
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    crit = _criteria(db, [])
    # Typische Notiz nach stelle_manuell_anlegen: vorhanden (>50 Zeichen),
    # aber weit von einer echten Anzeige entfernt (<400).
    notiz = ("PLM Rolle mit Change Management Schwerpunkt, Standort Hamburg. "
             "Aus dem Suchtreffer uebernommen, Volltext noch nicht geladen.")
    job = {"title": "Projektleiter PLM (m/w/d)", "description": notiz,
           "employment_type": "festanstellung"}
    fit = fit_analyse(job, crit)
    assert fit.get("beschreibung_kurz") is True
    emp = _build_empfehlung(fit, job)
    assert emp.get("score_zuverlaessig") is False
    grund = " ".join(emp.get("ko_gruende") or [])
    assert "Kurztext" in grund and "keine fachliche Absage" in grund, grund


def test_762_manuell_ohne_url_warnt(setup_env):
    """#762.4: Ohne URL ist stellenbeschreibung_nachladen blockiert -> Hinweis."""
    from bewerbungs_assistent.server import mcp
    res = _result(_call(mcp, "stelle_manuell_anlegen", {
        "titel": "PLM Architekt", "firma": "OhneUrlCo",
    }))
    assert res.get("status") == "angelegt"
    assert "url_hinweis" in res, res
    assert "score_hinweis" in res, "Kurztext-Score sollte gekennzeichnet sein"


def test_762_health_check_budget_liefert_teilergebnis(setup_env, monkeypatch):
    """#762.3/#761: Budget statt MCP-Timeout -> Teilergebnis mit offenen Quellen."""
    import time as _t
    import bewerbungs_assistent.job_scraper.health as health
    from bewerbungs_assistent.server import mcp

    def _slow(src):
        _t.sleep(8)
        return {"source": src, "reachable": True}

    monkeypatch.setattr(health, "check_source", _slow)
    monkeypatch.setattr(health, "get_probable_sources",
                        lambda: ["q1", "q2", "q3"])

    started = _t.monotonic()
    res = _result(_call(mcp, "quellen_health_check", {"budget_sekunden": 5}))
    dauer = _t.monotonic() - started

    assert res.get("abgebrochen") is True, res
    assert res.get("nicht_geprueft"), "offene Quellen muessen benannt sein"
    assert dauer < 7, f"Budget nicht eingehalten ({dauer:.1f}s)"
    assert "TEILERGEBNIS" in (res.get("hinweis") or "")


def test_762_ko_grund_wird_gemeldet(setup_env):
    """Faellt der Score doch auf 0, muss der Grund transparent zurueckkommen."""
    db, _ = setup_env
    from bewerbungs_assistent.server import mcp
    from bewerbungs_assistent.job_scraper import stelle_hash, calculate_score
    crit = _criteria(db, ["Zeitarbeit"])

    job = {
        "hash": stelle_hash("demo", "TestCo PLM Zeitarbeit"),
        "title": "PLM Consultant (m/w/d)", "company": "TestCo",
        "location": "Hamburg", "url": "https://example.de/job/2",
        "source": "demo", "description": KURZTEXT,
        "employment_type": "festanstellung",
    }
    job["score"] = calculate_score(job, crit)
    db.save_jobs([job])
    pub = db.get_job(job["hash"])

    res = _result(_call(mcp, "stelle_bearbeiten", {
        "job_hash": pub["hash"],
        "beschreibung": VOLLTEXT + " Die Stelle wird ueber Zeitarbeit besetzt.",
    }))
    recomputed = res.get("score_neu_berechnet") or {}
    assert recomputed.get("neuer_score") == 0
    assert "Zeitarbeit" in (recomputed.get("grund") or ""), (
        f"K.o.-Grund fehlt oder nennt das Keyword nicht: {recomputed}"
    )
