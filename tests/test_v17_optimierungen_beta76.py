"""Tests fuer beta.76-Optimierungen.

Issues:
- #650 (D15): Nachfass-Trigger bei Status ohne Update >7d
- #651 (E12): Auto-Tiefenanalyse-Step fuer basis_analysiert-Docs
- #652 (G11): Onboarding-Hints fuer ungenutzte Features (Backend)
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


# ── #651 (E12) Auto-Tiefenanalyse ──────────────────────────────────────


def test_run_auto_deep_analysis_skipt_ohne_ollama(tmp_db, monkeypatch):
    """#651: Wenn Lokale AI nicht aktiv, sofort skip ohne DB-Zugriff."""
    tmp_db.create_profile("Test User", "test@example.com")

    # Ollama nicht verfuegbar mocken
    from bewerbungs_assistent.services import llm_service

    class _Status:
        ollama_available = False
        available_models = []
        user_state = "off"
        selected_model = None

    class _Svc:
        def get_status(self, force_refresh=False):
            return _Status()

    monkeypatch.setattr(
        llm_service, "get_llm_service", lambda db=None: _Svc()
    )

    from bewerbungs_assistent import dashboard
    monkeypatch.setattr(dashboard, "_db", tmp_db)

    result = dashboard._run_auto_deep_analysis("2026-06-01T12:00:00")
    assert result["skipped"] is True
    assert "Lokale AI" in result["reason"]
    assert result["processed"] == 0


def test_run_auto_deep_analysis_verarbeitet_basis_docs(tmp_db, monkeypatch):
    """#651/#658: Wenn Lokale AI an und Docs in basis_analysiert: bis zu N
    werden verarbeitet. extraction_status wird auf 'angewendet' gesetzt
    (beta.78 #658: vorher 'analysiert' — Halbschritt, fuehrte zum Stuck-
    Bug bei Korrespondenz-Docs)."""
    tmp_db.create_profile("Test User", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    conn = tmp_db.connect()
    # 5 Docs mit Status basis_analysiert + ausreichend Text einfuegen
    for i in range(5):
        doc_id = tmp_db.add_document({
            "filename": f"doc_{i}.eml",
            "doc_type": "sonstiges",
            "extracted_text": f"Beispiel-Text mit ausreichend Inhalt fuer die Analyse. " * 10,
        })
        tmp_db.update_document_extraction_status(doc_id, "basis_analysiert")
    # Stelle sicher dass alle 5 wirklich da sind
    count_before = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE extraction_status='basis_analysiert' "
        "AND (profile_id=? OR profile_id IS NULL)", (pid,)
    ).fetchone()["n"]
    assert count_before >= 5

    # Mock Ollama: liefert eine 'andere' Klasse, damit beide Branches getestet werden
    from bewerbungs_assistent.services import llm_service

    class _Status:
        ollama_available = True
        available_models = ["mock:7b"]
        user_state = "active"
        selected_model = "mock:7b"

    call_count = {"n": 0}

    class _Svc:
        def get_status(self, force_refresh=False):
            return _Status()
        def run(self, task, payload):
            from bewerbungs_assistent.services.llm_service import TaskResult, Backend
            call_count["n"] += 1
            # Erste 2 Calls: liefert andere Kategorie -> umklassifiziert
            # Restliche: liefert sonstiges -> nur Status-Update
            category = "recruiter_anfrage" if call_count["n"] <= 2 else "sonstiges"
            return TaskResult(
                backend=Backend.LOCAL,
                success=True,
                payload={"category": category, "confidence": 0.85},
            )

    monkeypatch.setattr(llm_service, "get_llm_service", lambda db=None: _Svc())

    from bewerbungs_assistent import dashboard
    monkeypatch.setattr(dashboard, "_db", tmp_db)

    # Standard: max_docs=3
    result = dashboard._run_auto_deep_analysis("2026-06-01T12:00:00", max_docs=3)
    assert result["skipped"] is False
    assert result["processed"] == 3
    assert result["classified_anders"] == 2  # erste 2 Calls
    # beta.78 (#658): Status ist jetzt 'angewendet' statt 'analysiert' —
    # Korrespondenz braucht keinen weiteren Schritt mehr.
    angewendet = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE extraction_status='angewendet' "
        "AND (profile_id=? OR profile_id IS NULL)", (pid,)
    ).fetchone()["n"]
    assert angewendet >= 3


def test_run_auto_deep_analysis_backoff_nach_3_fehlern(tmp_db, monkeypatch):
    """#651: Backoff-Setting >=3 skippt das Doku."""
    tmp_db.create_profile("Test User", "test@example.com")
    doc_id = tmp_db.add_document({
        "filename": "broken.eml",
        "doc_type": "sonstiges",
        "extracted_text": "Test " * 100,
    })
    tmp_db.update_document_extraction_status(doc_id, "basis_analysiert")
    tmp_db.set_setting(f"deep_analysis_fail:{doc_id}", "3")

    from bewerbungs_assistent.services import llm_service

    class _Status:
        ollama_available = True
        available_models = ["mock:7b"]
        user_state = "active"
        selected_model = "mock:7b"

    call_count = {"n": 0}

    class _Svc:
        def get_status(self, force_refresh=False):
            return _Status()
        def run(self, task, payload):
            call_count["n"] += 1
            raise RuntimeError("should not be called")

    monkeypatch.setattr(llm_service, "get_llm_service", lambda db=None: _Svc())

    from bewerbungs_assistent import dashboard
    monkeypatch.setattr(dashboard, "_db", tmp_db)

    result = dashboard._run_auto_deep_analysis("2026-06-01T12:00:00", max_docs=3)
    # LLM-Run wurde nicht aufgerufen
    assert call_count["n"] == 0
    assert result["skipped_backoff"] >= 1
    assert result["processed"] == 0


# ── #650 (D15) Nachfass-Trigger ────────────────────────────────────────


def _add_test_application_with_event(tmp_db, app_id: str, status: str,
                                      last_event_days_ago: int):
    """Helper: legt Bewerbung mit einem alten Event an."""
    conn = tmp_db.connect()
    last_event_dt = datetime.now(timezone.utc) - timedelta(days=last_event_days_ago)
    conn.execute(
        "INSERT INTO applications (id, title, company, status, profile_id, "
        "applied_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (app_id, f"Test Job {app_id}", f"TestFirma-{app_id}", status,
         tmp_db.get_active_profile_id(),
         last_event_dt.isoformat(), last_event_dt.isoformat(),
         last_event_dt.isoformat())
    )
    conn.execute(
        "INSERT INTO application_events (application_id, status, event_date, notes) "
        "VALUES (?, ?, ?, ?)",
        (app_id, status, last_event_dt.isoformat(), "Test event")
    )
    conn.commit()


def test_run_check_stale_applications_findet_7d_und_14d(tmp_db, monkeypatch):
    """#650: Bewerbungen >=7d kommen in stale_7d, >=14d in stale_14d."""
    tmp_db.create_profile("Test User", "test@example.com")
    # Eine frisch (2 Tage), eine 8d, eine 15d, eine terminal
    _add_test_application_with_event(tmp_db, "fresh-1", "interview", 2)
    _add_test_application_with_event(tmp_db, "stale7-1", "interview", 8)
    _add_test_application_with_event(tmp_db, "stale14-1", "zweitgespraech", 15)
    _add_test_application_with_event(tmp_db, "terminal-1", "abgelehnt", 20)

    from bewerbungs_assistent import dashboard
    monkeypatch.setattr(dashboard, "_db", tmp_db)
    # Elwosa-Trigger stillmachen
    monkeypatch.setattr(dashboard, "_elwosa_speak_safe", lambda *a, **kw: None)

    result = dashboard._run_check_stale_applications("2026-06-01T12:00:00")

    # terminal-1 ist nicht in den aktiven Statuses
    assert result["checked"] == 3
    assert result["stale_7d"] == 1
    assert result["stale_14d"] == 1
    assert result["stale_7d_details"][0]["id"] == "stale7-1"
    assert result["stale_14d_details"][0]["id"] == "stale14-1"


def test_run_check_stale_applications_idempotent(tmp_db, monkeypatch):
    """#650: Zweiter Lauf innerhalb von 5d wirft die Bewerbung nicht erneut raus."""
    tmp_db.create_profile("Test User", "test@example.com")
    _add_test_application_with_event(tmp_db, "stale-app", "interview", 10)

    from bewerbungs_assistent import dashboard
    monkeypatch.setattr(dashboard, "_db", tmp_db)
    monkeypatch.setattr(dashboard, "_elwosa_speak_safe", lambda *a, **kw: None)

    res1 = dashboard._run_check_stale_applications("2026-06-01T12:00:00")
    assert res1["stale_7d"] == 1

    # Zweiter Lauf sofort danach: Re-Notify-Window hat noch nicht abgelaufen
    res2 = dashboard._run_check_stale_applications("2026-06-01T12:30:00")
    assert res2["stale_7d"] == 0  # bereits notified, skip
    assert res2["stale_14d"] == 0


# ── #652 (G11) Onboarding-Hints ────────────────────────────────────────


def test_onboarding_hints_keine_bei_leerem_profil(tmp_db):
    """#652: Frisches Profil hat 0 Bewerbungen, 0 Termine, 0 Interviews ->
    keiner der Aktivitaets-Hints feuert. Seit v1.7.5 (#652-Rest, G17-
    Anschluss) erscheint fuer genau diesen Zustand aber BEWUSST der
    Naechster-Schritt-Hint g11_erste_suche_starten (Profil da, keine
    Suchbegriffe) — Leitlinie: der User sieht immer den naechsten Schritt."""
    tmp_db.create_profile("Test User", "test@example.com")
    from bewerbungs_assistent.services.onboarding_hints import list_active_hints
    hints = list_active_hints(tmp_db)
    assert [h["id"] for h in hints] == ["g11_erste_suche_starten"]

    # Mit gesetzten Suchbegriffen verschwindet auch dieser Hint -> 0 Hints
    tmp_db.set_search_criteria("keywords_muss", ["PLM"])
    assert list_active_hints(tmp_db) == []


def test_onboarding_hint_suchprofile_triggert_bei_3_bewerbungen(tmp_db):
    """#652 Hint #1: 0 Suchprofile + 3+ Bewerbungen -> suchprofile-Hint sichtbar."""
    tmp_db.create_profile("Test User", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    conn = tmp_db.connect()
    # 3 Bewerbungen anlegen
    for i in range(3):
        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO applications (id, title, company, status, profile_id, "
            "applied_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"app-{i}", f"Job {i}", f"Firma {i}", "beworben", pid,
             now_iso, now_iso, now_iso)
        )
    conn.commit()

    from bewerbungs_assistent.services.onboarding_hints import list_active_hints
    hints = list_active_hints(tmp_db)
    ids = [h["id"] for h in hints]
    assert "g11_suchprofile_anlegen" in ids


def test_onboarding_hint_dismiss_persistiert(tmp_db):
    """#652: dismiss_hint speichert die ID, list zeigt sie nicht mehr."""
    tmp_db.create_profile("Test User", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    conn = tmp_db.connect()
    # Bedingung erfuellen damit der Hint kommt
    for i in range(3):
        now_iso = datetime.now(timezone.utc).isoformat()
        conn.execute(
            "INSERT INTO applications (id, title, company, status, profile_id, "
            "applied_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"app-d-{i}", f"Job D{i}", f"FirmaD{i}", "beworben", pid,
             now_iso, now_iso, now_iso)
        )
    conn.commit()

    from bewerbungs_assistent.services.onboarding_hints import (
        list_active_hints, dismiss_hint
    )
    # Vor dismiss
    before = list_active_hints(tmp_db)
    assert any(h["id"] == "g11_suchprofile_anlegen" for h in before)

    # Dismiss
    res = dismiss_hint(tmp_db, "g11_suchprofile_anlegen")
    assert res["dismissed"] is True
    assert res["total_dismissed"] == 1

    # Danach taucht der Hint nicht mehr auf
    after = list_active_hints(tmp_db)
    assert not any(h["id"] == "g11_suchprofile_anlegen" for h in after)


def test_onboarding_hint_dismiss_unbekannte_id_error(tmp_db):
    """#652: dismiss_hint mit ungueltiger ID liefert error + bekannte_ids."""
    tmp_db.create_profile("Test User", "test@example.com")
    from bewerbungs_assistent.services.onboarding_hints import dismiss_hint
    res = dismiss_hint(tmp_db, "nonsense_id")
    assert "error" in res
    assert "bekannte_ids" in res
    assert isinstance(res["bekannte_ids"], list)
    assert len(res["bekannte_ids"]) >= 3


def test_onboarding_hint_mcp_tool_anzeigen(tmp_db):
    """#652: MCP-Tool onboarding_hints_anzeigen funktioniert mit FakeMCP."""
    tmp_db.create_profile("Test User", "test@example.com")
    fake_mcp = FakeMCP()
    from bewerbungs_assistent.tools import analyse as analyse_mod
    analyse_mod.register(fake_mcp, tmp_db, logging.getLogger("test"))

    res = fake_mcp.tools["onboarding_hints_anzeigen"]()
    assert "hints" in res
    assert "anzahl" in res
    assert isinstance(res["hints"], list)
