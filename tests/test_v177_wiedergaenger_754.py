"""Tests fuer #754 + #757 Stufe 1 (v1.7.7) — Wiedergaenger rollen-sensitiv.

Praxis-Fund vom 13.07.: 3x aussortierte Halbleiter-Fachrollen (Quality/
Reliability/Wafertest Engineer) setzten einen "(Sr.) Project Manager"
derselben Firma per Wiedergaenger-k.o. auf NICHT_EMPFOHLEN — der Match kam
ueber generische Tokens ("sr", "project") statt ueber Fach- oder
Rollen-Aehnlichkeit. Regelwerk seitdem:

  1. Fach-Domaenen-Ueberlappung traegt allein (#671 bleibt: PLM Owner +
     PLM Manager -> PLM Architect ist Wiedergaenger).
  2. Ohne Fach-Signal zaehlt nur dieselbe ROLLEN-FAMILIE.
  3. Historie anderer Rollen kommt als neutrale firmen_historie mit —
     Gruende gelten je STELLE, nicht firmenweit (#757).
"""
from __future__ import annotations

import logging


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


def _halbleiter_bestand(tmp_db):
    """3 aussortierte Halbleiter-Fachrollen — der Original-Fall aus #754."""
    _add_dismissed(tmp_db, "nx1", "Senior Quality & Reliability Engineer (m/f/d)",
                   "Halbleiterwerk Nord GmbH", "falsches_fachgebiet")
    _add_dismissed(tmp_db, "nx2", "Wafertest Engineer Automotive",
                   "Halbleiterwerk Nord GmbH", "falsches_fachgebiet")
    _add_dismissed(tmp_db, "nx3", "Equipment Engineer Wafer Fab (m/w/d)",
                   "Halbleiterwerk Nord GmbH", "falsches_fachgebiet")


# ── Token- und Rollen-Extraktion ─────────────────────────────────────────


def test_domain_tokens_ohne_generik_und_seniority():
    from bewerbungs_assistent.services.wiedergaenger import _domain_tokens
    # "sr" und "project" hatten den Praxis-Fehlmatch vom 13.07. getragen
    assert _domain_tokens("(Sr.) Project Manager (m/f/d)") == set()
    assert _domain_tokens("PLM Project Manager (m/w/d)") == {"plm"}
    # Fach-Signal bleibt erhalten
    assert "wafertest" in _domain_tokens("Wafertest Engineer Automotive")
    assert "quality" in _domain_tokens("Senior Quality Engineer")


def test_role_families_zuordnung():
    from bewerbungs_assistent.services.wiedergaenger import _role_families
    assert _role_families("(Sr.) Project Manager (m/f/d)") == {
        "management", "projektrolle"}
    assert _role_families("Senior Quality & Reliability Engineer") == {
        "engineering"}
    # Deutsche Komposita liefern beide Anteile
    assert _role_families("Projektleiter Anlagenbau") >= {
        "management", "projektrolle"}
    assert "entwicklung" in _role_families("Softwareentwickler")
    # Reines Fach-Kuerzel hat keine Rollen-Familie
    assert _role_families("PLM") == set()
    assert _role_families("") == set()


# ── Kern-Regression: Rollen-Veto ohne Fach-Signal ────────────────────────


def test_halbleiter_regression_projektmanager_kein_wiedergaenger(tmp_db):
    """3x Engineer-Fachrollen aussortiert -> Project Manager ist KEIN
    Wiedergaenger derselben Firma (#754, Original-Fall)."""
    tmp_db.create_profile("Test", "test@example.com")
    _halbleiter_bestand(tmp_db)

    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    pattern = find_wiedergaenger_pattern(
        tmp_db, "Halbleiterwerk Nord GmbH", "(Sr.) Project Manager (m/f/d)",
        schwellwert=2,
    )
    assert pattern is None


def test_gleiche_rollen_familie_bleibt_wiedergaenger(tmp_db):
    """2x Projektmanagement-Rollen aussortiert -> ein weiterer Project
    Manager derselben Firma IST Wiedergaenger (Rollen-Fallback)."""
    tmp_db.create_profile("Test", "test@example.com")
    _add_dismissed(tmp_db, "pm1", "Project Manager Infrastructure",
                   "Halbleiterwerk Nord GmbH", "zu_senior")
    _add_dismissed(tmp_db, "pm2", "Program Manager Automotive (m/w/d)",
                   "Halbleiterwerk Nord GmbH", "zu_senior")

    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    pattern = find_wiedergaenger_pattern(
        tmp_db, "Halbleiterwerk Nord GmbH", "(Sr.) Project Manager (m/f/d)",
        schwellwert=2,
    )
    assert pattern is not None
    assert pattern["top_grund"] == "zu_senior"
    assert pattern["anzahl"] == 2
    assert "management" in pattern.get("rollen_familien", [])
    assert "gleiche Rolle" in pattern["hinweis"]


def test_domaene_schlaegt_rolle_671_bleibt(tmp_db):
    """#671-Semantik unveraendert: Fach-Ueberlappung traegt allein, auch
    wenn die Rollen verschieden sind (Owner/Manager -> Architect)."""
    tmp_db.create_profile("Test", "test@example.com")
    _add_dismissed(tmp_db, "tc1", "PLM Product Owner (m/w/d)",
                   "Konsumgueter GmbH", "falsches_fachgebiet")
    _add_dismissed(tmp_db, "tc2", "PLM Manager", "Konsumgueter GmbH",
                   "falsches_fachgebiet")

    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    pattern = find_wiedergaenger_pattern(
        tmp_db, "Konsumgueter GmbH", "PLM Architect (m/w/d)", schwellwert=2,
    )
    assert pattern is not None
    assert "plm" in pattern["domain_tokens"]


def test_leerer_titel_bleibt_firmen_pruef_modus(tmp_db):
    """stelle_wiedergaenger_pruefen(firma=..., titel='') prueft bewusst
    die ganze Firma — dieser Modus bleibt erhalten."""
    tmp_db.create_profile("Test", "test@example.com")
    _halbleiter_bestand(tmp_db)

    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    pattern = find_wiedergaenger_pattern(
        tmp_db, "Halbleiterwerk Nord GmbH", "", schwellwert=2,
    )
    assert pattern is not None
    assert pattern["anzahl"] == 3


# ── firmen_historie: neutrale Einordnung (#757) ──────────────────────────


def test_firmen_historie_liefert_kontext(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    _halbleiter_bestand(tmp_db)

    from bewerbungs_assistent.services.wiedergaenger import firmen_historie
    fh = firmen_historie(tmp_db, "Halbleiterwerk Nord GmbH")
    assert fh is not None
    assert fh["aussortiert_anzahl"] == 3
    assert fh["gruende"] == {"falsches_fachgebiet": 3}
    assert len(fh["beispiel_titel"]) == 3
    assert "je STELLE" in fh["hinweis"]


def test_firmen_historie_none_ohne_bestand(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    from bewerbungs_assistent.services.wiedergaenger import firmen_historie
    assert firmen_historie(tmp_db, "Unbekannte Firma AG") is None
    assert firmen_historie(tmp_db, "") is None


# ── fit_analyse: kein k.o., aber neutrale Historie ───────────────────────


def test_fit_analyse_projektmanager_ohne_wiedergaenger_ko(tmp_db):
    """Der Original-Schaden aus #754: fit_analyse darf den Project Manager
    nicht mehr per Wiedergaenger-k.o. auf NICHT_EMPFOHLEN setzen."""
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id() or ""
    _halbleiter_bestand(tmp_db)
    new_hash = f"{pid}:nxpm"
    tmp_db.save_jobs([{
        "hash": new_hash, "title": "(Sr.) Project Manager (m/f/d)",
        "company": "Halbleiterwerk Nord GmbH", "location": "Hamburg",
        "url": "https://x/nxpm", "source": "xing", "score": 50,
        "description": "Projektmanagement fuer ERP-Transformation. "
                       "Stakeholder, Budget, Timeline. " * 5,
    }])

    mcp = _register_jobs(tmp_db)
    result = mcp.tools["fit_analyse"](job_hash=new_hash)
    assert "wiedergaenger" not in result
    assert not any(
        isinstance(r, str) and r.startswith("WIEDERGAENGER")
        for r in result.get("risks", [])
    )
    assert not any(
        "Wiedergaenger" in g
        for g in result["empfehlung"].get("ko_gruende", [])
    )
    # Die Historie kommt trotzdem als neutrale Einordnung mit
    assert result["firmen_historie"]["aussortiert_anzahl"] == 3
    assert "je STELLE" in result["firmen_historie"]["hinweis"]


# ── MCP-Tool: kein_wiedergaenger + Historie-Feld ─────────────────────────


def test_tool_meldet_historie_anderer_rollen(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    _halbleiter_bestand(tmp_db)

    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_wiedergaenger_pruefen"]
    result = fn(firma="Halbleiterwerk Nord GmbH",
                titel="(Sr.) Project Manager (m/f/d)")
    assert result["status"] == "kein_wiedergaenger"
    assert result["firmen_historie"]["aussortiert_anzahl"] == 3
    assert "andere Rollen" in result["hinweis"]


def test_tool_ohne_historie_ohne_feld(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    mcp = _register_jobs(tmp_db)
    fn = mcp.tools["stelle_wiedergaenger_pruefen"]
    result = fn(firma="Frische Firma GmbH", titel="Irgendwas")
    assert result["status"] == "kein_wiedergaenger"
    assert "firmen_historie" not in result
