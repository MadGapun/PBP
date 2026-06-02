"""Tests fuer Issue #657 (E16, beta.79) — Dokument-Lifecycle Phase 2.

Schema v44 fuehrt die orthogonale Spalte `documents.lifecycle` ein:
  aktiv      = Default
  archiviert = manuell ausgeblendet
  veraltet   = auto-gesetzt beim Bewerbungs-Statuswechsel auf
               abgelehnt/abgelaufen/zurueckgezogen

Phase 2 deckt ab:

1. Migration v43->v44: Spalte vorhanden, Default aktiv, Index angelegt
2. dokument_archivieren / dokument_reaktivieren (idempotent, DB-only)
3. dokumente_bulk_archivieren mit dry_run + Hard-Cap
4. Default-Filter lifecycle=aktiv in analyse_plan_erstellen,
   dokumente_batch_analysieren, dokumente_zur_analyse — und archiv=True
   zeigt wieder alles
5. Auto-Veralten beim Bewerbungs-Statuswechsel (Trigger-Stati abgelehnt/
   abgelaufen/zurueckgezogen, kein Trigger bei anderen Stati)
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


def _register_docs(tmp_db):
    from bewerbungs_assistent.tools.dokumente import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def _register_bewerbungen(tmp_db):
    from bewerbungs_assistent.tools.bewerbungen import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


# ── 1) Migration / Schema ────────────────────────────────────────────────


def test_lifecycle_spalte_existiert_default_aktiv(tmp_db):
    """Nach Schema-Init (tmp_db ist frisch) ist documents.lifecycle da
    und Default ist 'aktiv'."""
    tmp_db.create_profile("Test", "test@example.com")
    conn = tmp_db.connect()
    cols = [r["name"] for r in conn.execute("PRAGMA table_info(documents)").fetchall()]
    assert "lifecycle" in cols

    did = tmp_db.add_document({
        "filename": "x.pdf",
        "doc_type": "lebenslauf",
        "extracted_text": "x",
    })
    row = conn.execute(
        "SELECT lifecycle FROM documents WHERE id=?", (did,)
    ).fetchone()
    assert row["lifecycle"] == "aktiv"


def test_lifecycle_index_angelegt(tmp_db):
    """Index idx_documents_lifecycle muss existieren."""
    tmp_db.create_profile("Test", "test@example.com")
    conn = tmp_db.connect()
    indexes = [
        r["name"] for r in
        conn.execute("PRAGMA index_list(documents)").fetchall()
    ]
    assert "idx_documents_lifecycle" in indexes


def test_update_document_lifecycle_validiert(tmp_db):
    """DB-Helfer lehnt ungueltige lifecycle-Werte ab."""
    tmp_db.create_profile("Test", "test@example.com")
    did = tmp_db.add_document({"filename": "x.pdf", "doc_type": "lebenslauf"})

    assert tmp_db.update_document_lifecycle(did, "archiviert")
    with pytest.raises(ValueError):
        tmp_db.update_document_lifecycle(did, "erfunden")


# ── 2) dokument_archivieren / dokument_reaktivieren ──────────────────────


def test_dokument_archivieren_flippt_spalte(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register_docs(tmp_db)
    archivieren = mcp.tools["dokument_archivieren"]

    did = tmp_db.add_document({
        "filename": "rauschen.eml",
        "doc_type": "sonstiges",
        "extracted_text": "x",
        "profile_id": pid,
    })

    result = archivieren(dokument_id=did, grund="reines Rauschen")
    assert result["status"] == "archiviert"
    assert result["lifecycle_nachher"] == "archiviert"

    conn = tmp_db.connect()
    row = conn.execute(
        "SELECT lifecycle FROM documents WHERE id=?", (did,)
    ).fetchone()
    assert row["lifecycle"] == "archiviert"


def test_dokument_archivieren_idempotent(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register_docs(tmp_db)
    archivieren = mcp.tools["dokument_archivieren"]

    did = tmp_db.add_document({
        "filename": "x.eml", "doc_type": "sonstiges",
        "extracted_text": "x", "profile_id": pid,
    })
    archivieren(dokument_id=did)
    result_zweimal = archivieren(dokument_id=did)
    assert result_zweimal["status"] == "bereits_archiviert"


def test_dokument_reaktivieren_zurueck_auf_aktiv(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register_docs(tmp_db)
    archivieren = mcp.tools["dokument_archivieren"]
    reaktivieren = mcp.tools["dokument_reaktivieren"]

    did = tmp_db.add_document({
        "filename": "x.eml", "doc_type": "sonstiges",
        "extracted_text": "x", "profile_id": pid,
    })
    archivieren(dokument_id=did)
    result = reaktivieren(dokument_id=did)
    assert result["status"] == "aktiv"

    conn = tmp_db.connect()
    row = conn.execute(
        "SELECT lifecycle FROM documents WHERE id=?", (did,)
    ).fetchone()
    assert row["lifecycle"] == "aktiv"


def test_dokument_reaktivieren_auch_aus_veraltet(tmp_db):
    """Reaktivieren funktioniert auch aus veraltet (Auto-Veralten-Hook)."""
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register_docs(tmp_db)
    reaktivieren = mcp.tools["dokument_reaktivieren"]

    did = tmp_db.add_document({
        "filename": "x.eml", "doc_type": "sonstiges",
        "extracted_text": "x", "profile_id": pid,
    })
    tmp_db.update_document_lifecycle(did, "veraltet")
    result = reaktivieren(dokument_id=did)
    assert result["status"] == "aktiv"
    assert result["lifecycle_vorher"] == "veraltet"


# ── 3) dokumente_bulk_archivieren ────────────────────────────────────────


def test_bulk_archivieren_dry_run_aendert_nichts(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register_docs(tmp_db)
    bulk = mcp.tools["dokumente_bulk_archivieren"]

    for i in range(3):
        tmp_db.add_document({
            "filename": f"d{i}.eml", "doc_type": "sonstiges",
            "extracted_text": "x", "profile_id": pid,
        })

    result = bulk(filter_doc_type=["sonstiges"])
    assert result["dry_run"] is True
    assert result["kandidaten_anzahl"] == 3

    conn = tmp_db.connect()
    n_archiviert = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE lifecycle='archiviert'"
    ).fetchone()["n"]
    assert n_archiviert == 0


def test_bulk_archivieren_apply(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register_docs(tmp_db)
    bulk = mcp.tools["dokumente_bulk_archivieren"]

    for i in range(3):
        tmp_db.add_document({
            "filename": f"d{i}.eml", "doc_type": "sonstiges",
            "extracted_text": "x", "profile_id": pid,
        })

    result = bulk(filter_doc_type=["sonstiges"], dry_run=False)
    assert result["umgesetzt_anzahl"] == 3

    conn = tmp_db.connect()
    n_archiviert = conn.execute(
        "SELECT COUNT(*) AS n FROM documents WHERE lifecycle='archiviert'"
    ).fetchone()["n"]
    assert n_archiviert == 3


def test_bulk_archivieren_hard_cap(tmp_db):
    """max_treffer schuetzt vor riesigen Operationen."""
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register_docs(tmp_db)
    bulk = mcp.tools["dokumente_bulk_archivieren"]

    for i in range(10):
        tmp_db.add_document({
            "filename": f"d{i}.eml", "doc_type": "sonstiges",
            "extracted_text": "x", "profile_id": pid,
        })

    result = bulk(filter_doc_type=["sonstiges"], max_treffer=5)
    assert result["kandidaten_anzahl"] == 5
    assert result["max_treffer_erreicht"] is True


# ── 4) Default-Filter lifecycle='aktiv' in Read-Tools ────────────────────


def test_default_filter_analyse_plan_erstellen_blendet_archivierte_aus(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register_docs(tmp_db)
    plan = mcp.tools["analyse_plan_erstellen"]

    # 2 aktive, 1 archivierter Doc
    for i in range(2):
        tmp_db.add_document({
            "filename": f"aktiv{i}.pdf", "doc_type": "lebenslauf",
            "extracted_text": "x" * 100, "profile_id": pid,
        })
    archived_id = tmp_db.add_document({
        "filename": "alt.pdf", "doc_type": "lebenslauf",
        "extracted_text": "x" * 100, "profile_id": pid,
    })
    tmp_db.update_document_lifecycle(archived_id, "archiviert")

    # Default: nur aktiv
    result = plan()
    assert result["dokumente_gesamt"] == 2

    # archiv=True: alle
    result_all = plan(archiv=True)
    assert result_all["dokumente_gesamt"] == 3


def test_default_filter_batch_analysieren(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register_docs(tmp_db)
    batch = mcp.tools["dokumente_batch_analysieren"]

    aktiv = tmp_db.add_document({
        "filename": "a.eml", "doc_type": "sonstiges",
        "extracted_text": "x" * 500, "profile_id": pid,
    })
    archiv = tmp_db.add_document({
        "filename": "b.eml", "doc_type": "sonstiges",
        "extracted_text": "x" * 500, "profile_id": pid,
    })
    tmp_db.update_document_extraction_status(aktiv, "basis_analysiert")
    tmp_db.update_document_extraction_status(archiv, "basis_analysiert")
    tmp_db.update_document_lifecycle(archiv, "archiviert")

    # Default: nur aktiv -> 1 Doc
    result = batch(batch_nr=1)
    assert result["dokumente_in_batch"] == 1

    # archiv=True -> 2 Docs
    result_all = batch(batch_nr=1, archiv=True)
    assert result_all["dokumente_in_batch"] == 2


def test_default_filter_dokumente_zur_analyse(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register_docs(tmp_db)
    zur_analyse = mcp.tools["dokumente_zur_analyse"]

    a = tmp_db.add_document({
        "filename": "a.pdf", "doc_type": "lebenslauf",
        "extracted_text": "x" * 50, "profile_id": pid,
    })
    b = tmp_db.add_document({
        "filename": "b.pdf", "doc_type": "lebenslauf",
        "extracted_text": "x" * 50, "profile_id": pid,
    })
    tmp_db.update_document_lifecycle(b, "veraltet")

    default = zur_analyse()
    assert default["dokumente_gesamt"] == 1
    assert default["dokumente"][0]["id"] == a

    alle = zur_analyse(archiv=True)
    assert alle["dokumente_gesamt"] == 2


# ── 5) Auto-Veralten beim Bewerbungs-Statuswechsel ───────────────────────


def _make_application_with_doc(tmp_db, profile_id):
    """Helper: legt Bewerbung + verknuepftes Dokument an."""
    aid = tmp_db.add_application({
        "title": "Stelle X",
        "company": "Firma X",
        "url": "",
        "job_hash": None,
        "status": "beworben",
        "applied_at": "2026-05-01",
        "notes": "",
        "bewerbungsart": "mit_dokumenten",
        "lebenslauf_variante": "standard",
        "profile_id": profile_id,
    })
    did = tmp_db.add_document({
        "filename": "anschreiben.pdf",
        "doc_type": "anschreiben",
        "extracted_text": "Sehr geehrte ...",
        "linked_application_id": aid,
        "profile_id": profile_id,
    })
    return aid, did


def test_auto_veralten_bei_abgelehnt(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    aid, did = _make_application_with_doc(tmp_db, pid)

    mcp = _register_bewerbungen(tmp_db)
    status_aendern = mcp.tools["bewerbung_status_aendern"]
    result = status_aendern(bewerbung_id=aid, neuer_status="abgelehnt")

    assert "dokumente_veraltet" in result
    assert result["dokumente_veraltet"]["anzahl"] == 1
    assert did in result["dokumente_veraltet"]["ids"]

    conn = tmp_db.connect()
    row = conn.execute(
        "SELECT lifecycle FROM documents WHERE id=?", (did,)
    ).fetchone()
    assert row["lifecycle"] == "veraltet"


def test_auto_veralten_bei_abgelaufen(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    aid, did = _make_application_with_doc(tmp_db, pid)

    mcp = _register_bewerbungen(tmp_db)
    status_aendern = mcp.tools["bewerbung_status_aendern"]
    status_aendern(bewerbung_id=aid, neuer_status="abgelaufen")

    conn = tmp_db.connect()
    assert conn.execute(
        "SELECT lifecycle FROM documents WHERE id=?", (did,)
    ).fetchone()["lifecycle"] == "veraltet"


def test_auto_veralten_bei_zurueckgezogen(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    aid, did = _make_application_with_doc(tmp_db, pid)

    mcp = _register_bewerbungen(tmp_db)
    status_aendern = mcp.tools["bewerbung_status_aendern"]
    status_aendern(bewerbung_id=aid, neuer_status="zurueckgezogen")

    conn = tmp_db.connect()
    assert conn.execute(
        "SELECT lifecycle FROM documents WHERE id=?", (did,)
    ).fetchone()["lifecycle"] == "veraltet"


def test_kein_auto_veralten_bei_interview(tmp_db):
    """Status-Wechsel zu nicht-End-Stati triggert KEIN Auto-Veralten."""
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    aid, did = _make_application_with_doc(tmp_db, pid)

    mcp = _register_bewerbungen(tmp_db)
    status_aendern = mcp.tools["bewerbung_status_aendern"]
    result = status_aendern(bewerbung_id=aid, neuer_status="interview")

    assert "dokumente_veraltet" not in result

    conn = tmp_db.connect()
    assert conn.execute(
        "SELECT lifecycle FROM documents WHERE id=?", (did,)
    ).fetchone()["lifecycle"] == "aktiv"


def test_auto_veralten_betrifft_nicht_andere_bewerbungen(tmp_db):
    """Dokumente einer anderen Bewerbung bleiben aktiv, auch wenn diese
    Bewerbung in einen End-Status geht."""
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()

    aid_a, did_a = _make_application_with_doc(tmp_db, pid)
    aid_b, did_b = _make_application_with_doc(tmp_db, pid)

    mcp = _register_bewerbungen(tmp_db)
    status_aendern = mcp.tools["bewerbung_status_aendern"]
    status_aendern(bewerbung_id=aid_a, neuer_status="abgelehnt")

    conn = tmp_db.connect()
    assert conn.execute(
        "SELECT lifecycle FROM documents WHERE id=?", (did_a,)
    ).fetchone()["lifecycle"] == "veraltet"
    assert conn.execute(
        "SELECT lifecycle FROM documents WHERE id=?", (did_b,)
    ).fetchone()["lifecycle"] == "aktiv"
