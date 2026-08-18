"""Tests fuer Issue #671 (beta.86) — Wiedergaenger-Erkenner, KI-frei.

Architektur-Leitplanke: PBP-Kernfunktion darf lokale KI NIE voraussetzen.
Diese Tests laufen komplett ohne Ollama (Ebene 0 + Ebene 2):
  - services/wiedergaenger.find_wiedergaenger_pattern (Ebene 0)
  - MCP-Tool stelle_wiedergaenger_pruefen
  - fit_analyse-Integration (Ebene 2)
"""
from __future__ import annotations

import logging

import pytest


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _register_jobs(tmp_db):
    from bewerbungs_assistent.tools.jobs import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def _add_dismissed(tmp_db, hash_short, title, company, reason):
    pid = tmp_db.get_active_profile_id() or ""
    full = f"{pid}:{hash_short}"
    tmp_db.save_jobs([{
        "hash": full, "title": title, "company": company,
        "location": "Hamburg", "url": f"https://x/{hash_short}",
        "source": "manuell", "score": 50, "description": title,
    }])
    tmp_db.dismiss_job(full, reason)
    return full


# ── Ebene 0: normalize_company ───────────────────────────────────────────


def test_normalize_company_strippt_rechtsform():
    from bewerbungs_assistent.services.wiedergaenger import normalize_company
    assert normalize_company("Konsumgueter GmbH") == "konsumgueter"
    assert normalize_company("Beispiel AG & Co. KG") == "beispiel"
    assert normalize_company("Konsumgueter") == "konsumgueter"
    # Gleichheit ueber Rechtsform hinweg
    assert normalize_company("Konsumgueter GmbH") == normalize_company("Konsumgueter")


def test_normalize_company_leer():
    from bewerbungs_assistent.services.wiedergaenger import normalize_company
    assert normalize_company("") == ""
    assert normalize_company(None) == ""


# ── Ebene 0: find_wiedergaenger_pattern ──────────────────────────────────


def test_wiedergaenger_erkannt_bei_2x_gleicher_grund(tmp_db):
    """Konsumgueter PLM 2x als falsches_fachgebiet -> Wiedergaenger."""
    tmp_db.create_profile("Test", "test@example.com")
    _add_dismissed(tmp_db, "aaa1", "PLM Project Manager (m/w/d)", "Konsumgueter GmbH", "falsches_fachgebiet")
    _add_dismissed(tmp_db, "bbb2", "PLM Product Owner (m/w/d)", "Konsumgueter GmbH", "falsches_fachgebiet")

    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    pattern = find_wiedergaenger_pattern(
        tmp_db, "Konsumgueter GmbH", "PLM Architect (m/w/d)", schwellwert=2,
    )
    assert pattern is not None
    assert pattern["top_grund"] == "falsches_fachgebiet"
    assert pattern["anzahl"] == 2
    assert "plm" in pattern["domain_tokens"]


def test_wiedergaenger_unter_schwellwert_kein_treffer(tmp_db):
    """Nur 1x aussortiert -> bei schwellwert=2 kein Wiedergaenger."""
    tmp_db.create_profile("Test", "test@example.com")
    _add_dismissed(tmp_db, "aaa1", "PLM Project Manager", "Konsumgueter GmbH", "falsches_fachgebiet")

    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    pattern = find_wiedergaenger_pattern(
        tmp_db, "Konsumgueter GmbH", "PLM Architect", schwellwert=2,
    )
    assert pattern is None


def test_wiedergaenger_andere_firma_kein_treffer(tmp_db):
    """Gleiche Domaene, aber andere Firma -> kein Wiedergaenger."""
    tmp_db.create_profile("Test", "test@example.com")
    _add_dismissed(tmp_db, "aaa1", "PLM Manager", "Konsumgueter GmbH", "falsches_fachgebiet")
    _add_dismissed(tmp_db, "bbb2", "PLM Manager", "Konsumgueter GmbH", "falsches_fachgebiet")

    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    pattern = find_wiedergaenger_pattern(
        tmp_db, "Andere Firma AG", "PLM Architect", schwellwert=2,
    )
    assert pattern is None


def test_wiedergaenger_keine_domain_ueberlappung_kein_treffer(tmp_db):
    """Gleiche Firma, aber voellig andere Domaene -> kein Wiedergaenger.
    Guard gegen 'Grossfirma, ganz andere Rolle' (#670-Abgrenzung)."""
    tmp_db.create_profile("Test", "test@example.com")
    _add_dismissed(tmp_db, "aaa1", "PLM Manager", "Konsumgueter GmbH", "falsches_fachgebiet")
    _add_dismissed(tmp_db, "bbb2", "PLM Manager", "Konsumgueter GmbH", "falsches_fachgebiet")

    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    # Neue Stelle: Marketing — teilt kein Domaenen-Token mit PLM
    pattern = find_wiedergaenger_pattern(
        tmp_db, "Konsumgueter GmbH", "Marketing Brand Strategist", schwellwert=2,
    )
    assert pattern is None


def test_wiedergaenger_auto_prefix_normalisiert(tmp_db):
    """'auto:falsches_fachgebiet' und 'falsches_fachgebiet' fallen zusammen."""
    tmp_db.create_profile("Test", "test@example.com")
    _add_dismissed(tmp_db, "aaa1", "PLM Manager", "Konsumgueter GmbH", "auto:falsches_fachgebiet")
    _add_dismissed(tmp_db, "bbb2", "PLM Owner", "Konsumgueter GmbH", "falsches_fachgebiet")

    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    pattern = find_wiedergaenger_pattern(
        tmp_db, "Konsumgueter GmbH", "PLM Architect", schwellwert=2,
    )
    assert pattern is not None
    assert pattern["top_grund"] == "falsches_fachgebiet"
    assert pattern["anzahl"] == 2


# ── MCP-Tool stelle_wiedergaenger_pruefen ────────────────────────────────


def test_tool_wiedergaenger_meldung(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    _add_dismissed(tmp_db, "aaa1", "PLM Manager", "Konsumgueter GmbH", "falsches_fachgebiet")
    _add_dismissed(tmp_db, "bbb2", "PLM Owner", "Konsumgueter GmbH", "falsches_fachgebiet")

    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_wiedergaenger_pruefen"]
    result = fn(firma="Konsumgueter GmbH", titel="PLM Architect")
    assert result["status"] == "wiedergaenger"
    assert result["top_grund"] == "falsches_fachgebiet"
    assert result["aktion"] == "nur_gemeldet"


def test_tool_kein_wiedergaenger(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_wiedergaenger_pruefen"]
    result = fn(firma="Neue Firma", titel="Irgendwas")
    assert result["status"] == "kein_wiedergaenger"


def test_tool_auto_aussortieren(tmp_db):
    """Mit job_hash + auto_aussortieren=True wird die Stelle dismissed."""
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id() or ""
    _add_dismissed(tmp_db, "aaa1", "PLM Manager", "Konsumgueter GmbH", "falsches_fachgebiet")
    _add_dismissed(tmp_db, "bbb2", "PLM Owner", "Konsumgueter GmbH", "falsches_fachgebiet")
    # Neue aktive Stelle
    new_hash = f"{pid}:ccc3"
    tmp_db.save_jobs([{
        "hash": new_hash, "title": "PLM Architect (m/w/d)", "company": "Konsumgueter GmbH",
        "location": "Hamburg", "url": "https://x/ccc3", "source": "xing",
        "score": 50, "description": "PLM Architect",
    }])

    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_wiedergaenger_pruefen"]
    result = fn(job_hash=new_hash, auto_aussortieren=True)
    assert result["status"] == "wiedergaenger"
    assert result["aktion"] == "auto_aussortiert"
    assert result["dismiss_reason"] == "wiedergaenger:falsches_fachgebiet"

    job = tmp_db.get_job(new_hash)
    assert job["is_active"] == 0


def test_tool_fehler_ohne_firma(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_wiedergaenger_pruefen"]
    result = fn()
    assert "fehler" in result


# ── Ebene 2: fit_analyse-Integration ─────────────────────────────────────


def test_fit_analyse_liefert_wiedergaenger_feld(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id() or ""
    _add_dismissed(tmp_db, "aaa1", "PLM Project Manager", "Konsumgueter GmbH", "falsches_fachgebiet")
    _add_dismissed(tmp_db, "bbb2", "PLM Product Owner", "Konsumgueter GmbH", "falsches_fachgebiet")
    new_hash = f"{pid}:ddd4"
    tmp_db.save_jobs([{
        "hash": new_hash, "title": "PLM Architect (m/w/d)", "company": "Konsumgueter GmbH",
        "location": "Hamburg", "url": "https://x/ddd4", "source": "xing",
        "score": 50,
        "description": "Wir suchen einen PLM Architect fuer unser Team. "
                       "Centric PLM Erfahrung gewuenscht. " * 5,
    }])

    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["fit_analyse"]
    result = fn(job_hash=new_hash)
    assert "wiedergaenger" in result
    assert result["wiedergaenger"]["top_grund"] == "falsches_fachgebiet"
    # Empfehlung sollte NICHT_EMPFOHLEN sein (fachlicher k.o.-Wiedergaenger)
    assert result["empfehlung"]["kategorie"] == "NICHT_EMPFOHLEN"
    assert any("Wiedergaenger" in g for g in result["empfehlung"].get("ko_gruende", []))


def test_fit_analyse_ohne_historie_kein_wiedergaenger(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id() or ""
    new_hash = f"{pid}:eee5"
    tmp_db.save_jobs([{
        "hash": new_hash, "title": "Python Developer", "company": "Frische Firma GmbH",
        "location": "Bremen", "url": "https://x/eee5", "source": "xing",
        "score": 50, "description": "Python Entwickler gesucht. " * 10,
    }])

    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["fit_analyse"]
    result = fn(job_hash=new_hash)
    assert "wiedergaenger" not in result
