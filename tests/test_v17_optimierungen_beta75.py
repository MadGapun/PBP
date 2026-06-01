"""Tests fuer beta.75-Optimierungen aus Reality-Check vom 2026-06-01.

Issues:
- #647 (H12): pbp_capabilities Tool-Count-Sync (gesamt vs. kuratiert)
- #648 (C17): Outcome-Signal in fit_analyse (Warnung bei Pattern in aussortierten Aehnlichen)
- #649 (E13): Few-Shot fuer Recruiter-Anfrage-Klassifikator
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


# ── #647 (H12) pbp_capabilities Tool-Count-Sync ────────────────────────


def test_pbp_capabilities_liefert_getrennte_counts(tmp_db):
    """#647: gesamt + kuratiert sind sichtbar; bei Diskrepanz Hinweis-Text."""
    tmp_db.create_profile("Test User", "test@example.com")
    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import analyse as analyse_mod
    analyse_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    res = fake_mcp.tools["pbp_capabilities"]()
    # tools_kuratiert ist deterministisch (Catalog im Code)
    assert "tools_kuratiert" in res
    assert isinstance(res["tools_kuratiert"], int)
    assert res["tools_kuratiert"] > 0
    # tools_gesamt kann None sein (wenn FastMCP-Registry-Introspection fehlt),
    # darf aber explizit gesetzt sein
    assert "tools_gesamt" in res


def test_pbp_capabilities_ueberblick_text_passt_zu_counts(tmp_db):
    """#647: Der ueberblick-Text spiegelt die echten Counts, nicht das alte '95'."""
    tmp_db.create_profile("Test User", "test@example.com")
    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import analyse as analyse_mod
    analyse_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    res = fake_mcp.tools["pbp_capabilities"]()
    ueberblick = res["ueberblick"]
    kuratiert = res["tools_kuratiert"]
    # Mindestens eine der beiden Zahlen muss im Text vorkommen
    assert (
        str(kuratiert) in ueberblick
        or (res.get("tools_gesamt") is not None and str(res["tools_gesamt"]) in ueberblick)
        or "~152" in ueberblick  # Fallback wenn gesamt nicht ermittelbar
    )
    # Die magische alte 95 darf nicht mehr hardcoded sein (ausser wenn
    # tools_kuratiert wirklich 95 ist — dann ist das OK)
    if kuratiert != 95:
        assert "95 Tools in 10 Kategorien" not in ueberblick


# ── #648 (C17) Outcome-Signal in fit_analyse ──────────────────────────


def test_outcome_pattern_helper_triggert_bei_3_gleichen_gruenden(tmp_db):
    """#648: 3 aussortierte Aehnliche mit gleichem Grund -> Pattern erkannt."""
    tmp_db.create_profile("Test User", "test@example.com")
    # Target: PLM-Stelle aktiv
    tmp_db.save_jobs([
        {
            "hash": "target-plm-1",
            "title": "Senior PLM Consultant Architecture",
            "company": "TestFirma-Z",
            "source": "stepstone",
            "description": (
                "Wir suchen einen erfahrenen PLM Consultant fuer Architecture "
                "und Solution Design. Aufgaben: PLM-Beratung, Architecture, "
                "Solution Design, Senior Level."
            ),
            "score": 30,
            "employment_type": "festanstellung",
        },
    ])
    # 4 aehnliche Stellen aussortieren mit gleichem Grund
    for i in range(4):
        tmp_db.save_jobs([
            {
                "hash": f"dismissed-plm-{i}",
                "title": f"PLM Consultant Architecture Variante {i}",
                "company": f"TestFirma-{i}",
                "source": "stepstone",
                "description": (
                    "PLM Architecture und Solution Design fuer Senior Consultant. "
                    "Beratung, Architecture, Solution Design."
                ),
                "score": 25,
                "employment_type": "festanstellung",
            },
        ])
        tmp_db.dismiss_job(f"dismissed-plm-{i}", "falsches_fachgebiet")

    from bewerbungs_assistent.tools.jobs import _aehnliche_outcome_pattern
    target_job = tmp_db.get_job("target-plm-1")
    result = _aehnliche_outcome_pattern(tmp_db, target_job, schwellwert=3)

    assert result is not None
    assert result["top_grund"] == "falsches_fachgebiet"
    assert result["anzahl"] >= 3
    assert "Aufmerksamkeit" in result["risk_text"]
    assert "falsches_fachgebiet" in result["risk_text"]
    assert len(result["beispiele"]) <= 3


def test_outcome_pattern_helper_kein_treffer_bei_2_aehnlichen(tmp_db):
    """#648: <3 aussortierte Aehnliche -> None (kein Pattern)."""
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs([
        {
            "hash": "target-plm-2",
            "title": "Senior PLM Consultant",
            "company": "TestFirma-A",
            "source": "stepstone",
            "description": "PLM Consultant Architecture Solution Design Senior",
            "score": 30,
            "employment_type": "festanstellung",
        },
    ])
    # Nur 2 aussortierte
    for i in range(2):
        tmp_db.save_jobs([{
            "hash": f"dismissed-only-{i}",
            "title": f"PLM Consultant Variante {i}",
            "company": f"TestFirma-{i}",
            "source": "stepstone",
            "description": "PLM Consultant Architecture",
            "score": 20,
            "employment_type": "festanstellung",
        }])
        tmp_db.dismiss_job(f"dismissed-only-{i}", "falsches_fachgebiet")

    from bewerbungs_assistent.tools.jobs import _aehnliche_outcome_pattern
    target = tmp_db.get_job("target-plm-2")
    result = _aehnliche_outcome_pattern(tmp_db, target, schwellwert=3)
    assert result is None


def test_outcome_pattern_helper_kein_treffer_bei_verschiedenen_gruenden(tmp_db):
    """#648: 3 aussortierte aber MIT VERSCHIEDENEN Gruenden -> kein Pattern."""
    tmp_db.create_profile("Test User", "test@example.com")
    tmp_db.save_jobs([{
        "hash": "target-plm-3",
        "title": "Senior PLM Consultant",
        "company": "TestFirma-X",
        "source": "stepstone",
        "description": "PLM Consultant Architecture Solution Design Senior",
        "score": 30,
        "employment_type": "festanstellung",
    }])
    gruende = ["falsches_fachgebiet", "zu_weit_entfernt", "gehalt_zu_niedrig"]
    for i, grund in enumerate(gruende):
        tmp_db.save_jobs([{
            "hash": f"dismissed-mixed-{i}",
            "title": f"PLM Consultant Variante {i}",
            "company": f"TestFirma-{i}",
            "source": "stepstone",
            "description": "PLM Consultant Architecture",
            "score": 20,
            "employment_type": "festanstellung",
        }])
        tmp_db.dismiss_job(f"dismissed-mixed-{i}", grund)

    from bewerbungs_assistent.tools.jobs import _aehnliche_outcome_pattern
    target = tmp_db.get_job("target-plm-3")
    result = _aehnliche_outcome_pattern(tmp_db, target, schwellwert=3)
    # Kein einzelner Grund hat 3+ Stimmen → None
    assert result is None


# ── #649 (E13) Recruiter-Anfrage-Klassifikator ─────────────────────────


def test_detect_doc_type_erkennt_linkedin_outreach_filename(tmp_path):
    """#649: 'X hat Ihnen eine Nachricht gesendet.eml' -> recruiter_anfrage."""
    from bewerbungs_assistent.dashboard import _detect_doc_type as _detect_document_type
    assert _detect_document_type(
        "Raja Karunanithi hat Ihnen eine Nachricht gesendet.eml", ""
    ) == "recruiter_anfrage"
    assert _detect_document_type(
        "Neue Recruiting-Nachricht.eml", ""
    ) == "recruiter_anfrage"


def test_detect_doc_type_erkennt_englische_outreach_filename():
    """#649: englische Outreach-Subjects -> recruiter_anfrage."""
    from bewerbungs_assistent.dashboard import _detect_doc_type as _detect_document_type
    assert _detect_document_type(
        "Live German Solution Architect Roles.. Interested_.eml", ""
    ) == "recruiter_anfrage"
    assert _detect_document_type(
        "Consulting opportunity on Recycling & Sorting Technology.eml", ""
    ) == "recruiter_anfrage"
    assert _detect_document_type(
        "Follow-up on my last email. Project_ Recycling.eml", ""
    ) == "recruiter_anfrage"


def test_detect_doc_type_erkennt_deutsche_outreach_filename():
    """#649: 'Wir suchen ...' und 'Sie sind der richtige Kandidat' -> recruiter_anfrage."""
    from bewerbungs_assistent.dashboard import _detect_doc_type as _detect_document_type
    assert _detect_document_type(
        "Wir suchen einen Qt-Entwickler (m_w_d) - Bremen.eml", ""
    ) == "recruiter_anfrage"
    assert _detect_document_type(
        "Sie sind der richtige Kandidat fuer Executive Headhunter.eml", ""
    ) == "recruiter_anfrage"
    assert _detect_document_type(
        "Neuer Job fuer Dich_ Du gehoerst zu den Top-Kandidat-innen.eml", ""
    ) == "recruiter_anfrage"


def test_detect_doc_type_erkennt_content_outreach_phrases():
    """#649: Content-basiert: LinkedIn-typische Outreach-Phrasen treffen."""
    from bewerbungs_assistent.dashboard import _detect_doc_type as _detect_document_type
    # Subject ohne Keywords, aber Body-Phrase
    body = (
        "Hallo Herr Schmidt, ich habe ihr profil bei LinkedIn gefunden "
        "und finde Ihre Erfahrung sehr interessant. Ich freue mich auf "
        "ihre rueckmeldung. Beste Gruesse, Anna."
    )
    # Generischer Filename ohne triggernde Keywords
    assert _detect_document_type("Mail.eml", body) == "recruiter_anfrage"


def test_detect_doc_type_recall_war_vorher_problem():
    """#649: Regression-Schutz — diese 6 Subjects landeten vorher in 'sonstiges'.

    Aus dem 2026-06-01 Reality-Check: dokumente_zur_analyse zeigte ~16
    Recruiter-Mails als 'sonstiges'. Test deckt repraesentative Faelle ab.
    """
    from bewerbungs_assistent.dashboard import _detect_doc_type as _detect_document_type
    fname_examples = [
        "Raja Karunanithi hat Ihnen eine Nachricht gesendet.eml",
        "Shruti Naik hat Ihnen eine Nachricht gesendet.eml",
        "Wir suchen einen Qt-Entwickler (m_w_d) - Bremen.eml",
        "Sie sind der richtige Kandidat fuer Executive Headhunter.eml",
        "Live German Solution Architect Roles.. Interested_.eml",
        "Consulting opportunity on Recycling & Sorting Technology.eml",
    ]
    for fname in fname_examples:
        result = _detect_document_type(fname, "")
        assert result == "recruiter_anfrage", (
            f"#649 Regression: '{fname}' wurde als '{result}' "
            "klassifiziert statt 'recruiter_anfrage'"
        )


def test_detect_doc_type_precision_eingangsbestaetigung_bleibt_eigenstaendig():
    """#649: Precision-Check — 'Ihre Bewerbung in unserem Hause' darf NICHT
    als recruiter_anfrage klassifiziert werden (ist eine Bestaetigung)."""
    from bewerbungs_assistent.dashboard import _detect_doc_type as _detect_document_type
    # Eingangsbestaetigung — sollte NICHT recruiter_anfrage werden
    result = _detect_document_type(
        "Ihre Bewerbung in unserem Hause - Projekt-Nr 104810 - Methoden.eml",
        "vielen dank fuer ihre bewerbung. Wir bestaetigen den Eingang Ihrer Unterlagen."
    )
    assert result != "recruiter_anfrage"
    # Sollte als eingangsbestaetigung erkannt werden (content_keyword greift)
    assert result == "eingangsbestaetigung"
