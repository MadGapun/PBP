"""Tests fuer Issue #658 (E15, beta.78) — Dokument-Lifecycle Phase 1.

Bug: Korrespondenz-Dokumente (Absagen, Einladungen, Recruiter-Anfragen,
Benachrichtigungen) blieben dauerhaft auf `extraction_status='basis_analysiert'`
haengen, weil `extraktion_anwenden()` nur den Profildaten-Pfad bedient.

Phase 1 (dieser Test-File) deckt ab:

1. Neues Repair-Tool `dokumente_korrespondenz_abschliessen()` faengt
   bestehende Korrespondenz im basis_analysiert/analysiert-Bucket ab
   und setzt sie auf `angewendet`. DB-only.
2. `_run_auto_deep_analysis` setzt nicht mehr `analysiert`, sondern
   direkt `angewendet` (verhindert das Wieder-Auftauchen).
3. `dokument_status_setzen()` akzeptiert jetzt `basis_analysiert`,
   `analysiert`, `analysiert_leer`, `duplikat`, `verworfen` zusaetzlich
   zu den bisherigen 4 Stati.
"""
from __future__ import annotations

import asyncio
import logging


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _register(tmp_db):
    from bewerbungs_assistent.tools.dokumente import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def _set_status(tmp_db, doc_id: str, status: str) -> None:
    """Direkter Setter — bewusst ohne die MCP-Whitelist, damit auch
    `basis_analysiert` & Co. fuer den Test-Setup erlaubt sind."""
    tmp_db.update_document_extraction_status(doc_id, status)


# ── #658 / E15 — Repair-Tool ─────────────────────────────────────────────


def test_korrespondenz_abschliessen_dry_run_zeigt_treffer(tmp_db):
    """dry_run=True (Default) zeigt nur Vorschau, schreibt nichts."""
    tmp_db.create_profile("Test User", "test@example.com")
    mcp = _register(tmp_db)
    fn = mcp.tools["dokumente_korrespondenz_abschliessen"]

    # 3 Korrespondenz-Docs auf basis_analysiert
    ids = []
    for i, dtype in enumerate(("sonstiges", "recruiter_anfrage", "absage")):
        did = tmp_db.add_document({
            "filename": f"mail_{i}.eml",
            "doc_type": dtype,
            "extracted_text": "Sehr geehrte Damen und Herren ...",
        })
        _set_status(tmp_db, did, "basis_analysiert")
        ids.append(did)

    # Ein Lebenslauf (kein Korrespondenz-Typ) — darf NICHT mit angefasst werden
    cv_id = tmp_db.add_document({
        "filename": "Lebenslauf.pdf",
        "doc_type": "lebenslauf",
        "extracted_text": "Profil",
    })
    _set_status(tmp_db, cv_id, "basis_analysiert")

    result = fn()  # dry_run defaults True

    assert result["dry_run"] is True
    assert result["status"] == "vorschau"
    assert result["kandidaten_anzahl"] == 3
    # Lebenslauf bleibt aussen vor
    cand_ids = {c["id"] for c in result["kandidaten"]}
    assert cv_id not in cand_ids
    assert set(ids) == cand_ids

    # Nichts wurde geaendert
    conn = tmp_db.connect()
    still_basis = conn.execute(
        "SELECT COUNT(*) AS n FROM documents "
        "WHERE extraction_status='basis_analysiert'"
    ).fetchone()["n"]
    assert still_basis == 4


def test_korrespondenz_abschliessen_wendet_an(tmp_db):
    """dry_run=False setzt Korrespondenz-Docs tatsaechlich auf angewendet."""
    tmp_db.create_profile("Test User", "test@example.com")
    mcp = _register(tmp_db)
    fn = mcp.tools["dokumente_korrespondenz_abschliessen"]

    ids = []
    for i in range(4):
        did = tmp_db.add_document({
            "filename": f"absage_{i}.eml",
            "doc_type": "sonstiges",
            "extracted_text": "Leider muessen wir Ihnen absagen.",
        })
        _set_status(tmp_db, did, "basis_analysiert")
        ids.append(did)

    result = fn(dry_run=False)

    assert result["dry_run"] is False
    assert result["status"] == "abgeschlossen"
    assert result["umgesetzt_anzahl"] == 4

    conn = tmp_db.connect()
    angewendet = conn.execute(
        "SELECT COUNT(*) AS n FROM documents "
        "WHERE extraction_status='angewendet'"
    ).fetchone()["n"]
    assert angewendet == 4


def test_korrespondenz_abschliessen_laesst_profil_docs_in_ruhe(tmp_db):
    """Lebenslauf/Anschreiben/Projektliste werden NIE angefasst — die
    brauchen extraktion_anwenden()."""
    tmp_db.create_profile("Test User", "test@example.com")
    mcp = _register(tmp_db)
    fn = mcp.tools["dokumente_korrespondenz_abschliessen"]

    schutz_ids = []
    for dtype in ("lebenslauf", "anschreiben", "projektliste", "zeugnis"):
        did = tmp_db.add_document({
            "filename": f"{dtype}.pdf",
            "doc_type": dtype,
            "extracted_text": "Inhalt",
        })
        _set_status(tmp_db, did, "basis_analysiert")
        schutz_ids.append(did)

    result = fn(dry_run=False)

    assert result["umgesetzt_anzahl"] == 0
    assert result["kandidaten_anzahl"] == 0

    conn = tmp_db.connect()
    for did in schutz_ids:
        row = conn.execute(
            "SELECT extraction_status FROM documents WHERE id=?", (did,)
        ).fetchone()
        assert row["extraction_status"] == "basis_analysiert", (
            f"Profil-Doku {did} wurde unerlaubt angefasst!"
        )


def test_korrespondenz_abschliessen_zusaetzliche_typen(tmp_db):
    """zusaetzliche_doc_types erlaubt projekt-spezifische Typen mit aufzunehmen."""
    tmp_db.create_profile("Test User", "test@example.com")
    mcp = _register(tmp_db)
    fn = mcp.tools["dokumente_korrespondenz_abschliessen"]

    did = tmp_db.add_document({
        "filename": "newsletter.eml",
        "doc_type": "newsletter_digest",  # nicht in Default-Whitelist
        "extracted_text": "Wochen-Update",
    })
    _set_status(tmp_db, did, "basis_analysiert")

    # Ohne Erweiterung: 0 Treffer
    result_default = fn()
    assert result_default["kandidaten_anzahl"] == 0

    # Mit Erweiterung: 1 Treffer
    result_ext = fn(dry_run=False, zusaetzliche_doc_types=["newsletter_digest"])
    assert result_ext["umgesetzt_anzahl"] == 1


def test_korrespondenz_abschliessen_keine_kandidaten(tmp_db):
    """Wenn nichts zu tun ist: status bleibt 'vorschau' bei dry_run, klare Nachricht."""
    tmp_db.create_profile("Test User", "test@example.com")
    mcp = _register(tmp_db)
    fn = mcp.tools["dokumente_korrespondenz_abschliessen"]

    result = fn(dry_run=False)
    assert result["kandidaten_anzahl"] == 0
    assert "nichts zu tun" in result["nachricht"].lower()


# ── #658 / E15 — Auto-Deep-Status auf `angewendet` ───────────────────────


def test_auto_deep_analysis_setzt_angewendet_nicht_analysiert(tmp_db, monkeypatch):
    """Regression-Test fuer #658: _run_auto_deep_analysis muss
    'angewendet' setzen, nicht 'analysiert'."""
    tmp_db.create_profile("Test User", "test@example.com")
    pid = tmp_db.get_active_profile_id()

    for i in range(3):
        did = tmp_db.add_document({
            "filename": f"d_{i}.eml",
            "doc_type": "sonstiges",
            "extracted_text": "Ausreichend Text fuer die Analyse. " * 20,
        })
        _set_status(tmp_db, did, "basis_analysiert")

    from bewerbungs_assistent.services import llm_service

    class _Status:
        ollama_available = True
        available_models = ["mock"]
        user_state = "active"
        selected_model = "mock"

    class _Result:
        success = True
        payload = {"category": "sonstiges", "confidence": 0.9}

    class _Svc:
        def get_status(self, force_refresh=False):
            return _Status()
        def run(self, task, payload):
            return _Result()

    monkeypatch.setattr(llm_service, "get_llm_service", lambda db=None: _Svc())

    from bewerbungs_assistent import dashboard
    monkeypatch.setattr(dashboard, "_db", tmp_db)

    dashboard._run_auto_deep_analysis("2026-06-02T12:00:00", max_docs=3)

    conn = tmp_db.connect()
    n_angewendet = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE extraction_status='angewendet' "
        "AND (profile_id=? OR profile_id IS NULL)", (pid,)
    ).fetchone()["n"]
    n_analysiert = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE extraction_status='analysiert' "
        "AND (profile_id=? OR profile_id IS NULL)", (pid,)
    ).fetchone()["n"]

    assert n_angewendet >= 3, "_run_auto_deep_analysis sollte angewendet setzen (#658)"
    assert n_analysiert == 0, "Kein Doku darf mehr im Halbschritt 'analysiert' landen (#658)"


# ── #658 / E15 — dokument_status_setzen-Whitelist erweitert ──────────────


def test_dokument_status_setzen_akzeptiert_basis_analysiert(tmp_db):
    """Vorher schlug `dokument_status_setzen(.., 'basis_analysiert')`
    mit 'Ungueltiger Status' fehl — die Whitelist enthielt nur 4 Werte.
    beta.78 (#658) erweitert sie um die tatsaechlich vergebenen Stati."""
    tmp_db.create_profile("Test User", "test@example.com")
    mcp = _register(tmp_db)
    fn = mcp.tools["dokument_status_setzen"]

    did = tmp_db.add_document({
        "filename": "irgendwas.pdf",
        "doc_type": "sonstiges",
        "extracted_text": "x",
    })
    # Doku startet auf `angewendet` (manuell)
    _set_status(tmp_db, did, "angewendet")

    # Manuelles Zuruecksetzen auf basis_analysiert muss jetzt klappen
    for status in (
        "basis_analysiert", "analysiert", "analysiert_leer",
        "duplikat", "verworfen", "nicht_extrahiert", "angewendet",
    ):
        result = fn(dokument_id=did, status=status)
        assert "fehler" not in result, (
            f"Status '{status}' wurde unerwartet abgelehnt: {result}"
        )
        assert result["extraction_status"] == status


def test_dokument_status_setzen_lehnt_unbekannten_status_ab(tmp_db):
    """Defensive: voellig fremde Werte werden weiterhin abgelehnt."""
    tmp_db.create_profile("Test User", "test@example.com")
    mcp = _register(tmp_db)
    fn = mcp.tools["dokument_status_setzen"]

    did = tmp_db.add_document({
        "filename": "irgendwas.pdf",
        "doc_type": "sonstiges",
        "extracted_text": "x",
    })

    result = fn(dokument_id=did, status="erfunden")
    assert "fehler" in result
    assert "erlaubte_status" in result
