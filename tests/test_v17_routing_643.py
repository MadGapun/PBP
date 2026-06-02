"""Tests fuer Issue #643 (E11, beta.80) — Dokument-Routing Phase 3.

Phase 3 deckt drei Bausteine ab:

1. `dokumente_routing_plan_erstellen` — gruppiert Docs nach abgeleiteter
   Aktion (Profil-Extraktion, Termin, Status-Wechsel, ...).
2. `dokumente_batch_analysieren(routing_modus=True)` sendet pro Doku
   einen `routing`-Hint mit der konkreten Aktion mit.
3. `dokument_aktion_ausfuehren(dokument_id, aktion, args)` als Wrapper
   um die bestehenden MCP-Tools (meeting_hinzufuegen,
   bewerbung_status_aendern, bewerbung_erstellen).
4. Rauschen-Heuristik `is_pure_notification(sender, subject)` erkennt
   LinkedIn-/XING-Digest-Mails.
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


def _register(tmp_db):
    from bewerbungs_assistent.tools.dokumente import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


# ── 1) dokumente_routing_plan_erstellen ──────────────────────────────────


def test_routing_plan_gruppiert_nach_aktion(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register(tmp_db)
    fn = mcp.tools["dokumente_routing_plan_erstellen"]

    # Eine Mischung: 2 Lebenslaeufe, 1 Absage, 1 Einladung, 2 sonstige
    for i in range(2):
        did = tmp_db.add_document({
            "filename": f"cv_{i}.pdf", "doc_type": "lebenslauf",
            "extracted_text": "Profil", "profile_id": pid,
        })
        tmp_db.update_document_extraction_status(did, "basis_analysiert")
    did_abs = tmp_db.add_document({
        "filename": "absage.eml", "doc_type": "absage",
        "extracted_text": "Leider keine Beruecksichtigung.", "profile_id": pid,
    })
    tmp_db.update_document_extraction_status(did_abs, "basis_analysiert")
    did_ein = tmp_db.add_document({
        "filename": "einladung.eml", "doc_type": "einladung",
        "extracted_text": "Wir laden Sie ein.", "profile_id": pid,
    })
    tmp_db.update_document_extraction_status(did_ein, "basis_analysiert")
    for i in range(2):
        did = tmp_db.add_document({
            "filename": f"misc_{i}.eml", "doc_type": "sonstiges",
            "extracted_text": "irgendwas", "profile_id": pid,
        })
        tmp_db.update_document_extraction_status(did, "basis_analysiert")

    result = fn()
    assert result["status"] == "ok"
    assert result["dokumente_gesamt"] == 6

    aktionen_lookup = {a["aktion"]: a for a in result["aktionen"]}
    assert aktionen_lookup["profil_extraktion"]["anzahl"] == 2
    assert aktionen_lookup["bewerbung_status_setzen"]["anzahl"] == 1
    assert aktionen_lookup["termin_anlegen"]["anzahl"] == 1
    assert aktionen_lookup["noop_korrespondenz_abschliessen"]["anzahl"] == 2


def test_routing_plan_blendet_archivierte_aus(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register(tmp_db)
    fn = mcp.tools["dokumente_routing_plan_erstellen"]

    aktiv = tmp_db.add_document({
        "filename": "a.eml", "doc_type": "sonstiges",
        "extracted_text": "x", "profile_id": pid,
    })
    tmp_db.update_document_extraction_status(aktiv, "basis_analysiert")
    archiv = tmp_db.add_document({
        "filename": "b.eml", "doc_type": "sonstiges",
        "extracted_text": "x", "profile_id": pid,
    })
    tmp_db.update_document_extraction_status(archiv, "basis_analysiert")
    tmp_db.update_document_lifecycle(archiv, "archiviert")

    default = fn()
    assert default["dokumente_gesamt"] == 1
    alle = fn(archiv=True)
    assert alle["dokumente_gesamt"] == 2


def test_routing_plan_blendet_angewendete_aus(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register(tmp_db)
    fn = mcp.tools["dokumente_routing_plan_erstellen"]

    did = tmp_db.add_document({
        "filename": "done.eml", "doc_type": "absage",
        "extracted_text": "x", "profile_id": pid,
    })
    tmp_db.update_document_extraction_status(did, "angewendet")

    result = fn()
    assert result["dokumente_gesamt"] == 0


# ── 2) dokumente_batch_analysieren(routing_modus=True) ───────────────────


def test_batch_routing_modus_liefert_aktion_pro_doc(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register(tmp_db)
    fn = mcp.tools["dokumente_batch_analysieren"]

    did_cv = tmp_db.add_document({
        "filename": "cv.pdf", "doc_type": "lebenslauf",
        "extracted_text": "Profil " * 100, "profile_id": pid,
    })
    tmp_db.update_document_extraction_status(did_cv, "basis_analysiert")
    did_abs = tmp_db.add_document({
        "filename": "absage.eml", "doc_type": "absage",
        "extracted_text": "Leider " * 100, "profile_id": pid,
    })
    tmp_db.update_document_extraction_status(did_abs, "basis_analysiert")

    result = fn(batch_nr=1, routing_modus=True)
    assert result["routing_modus"] is True

    aktionen_by_id = {d["id"]: d["routing"]["aktion"] for d in result["dokumente"]}
    assert aktionen_by_id[did_cv] == "profil_extraktion"
    assert aktionen_by_id[did_abs] == "bewerbung_status_setzen"


def test_batch_routing_modus_off_haelt_alte_struktur(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register(tmp_db)
    fn = mcp.tools["dokumente_batch_analysieren"]

    did = tmp_db.add_document({
        "filename": "cv.pdf", "doc_type": "lebenslauf",
        "extracted_text": "Profil " * 100, "profile_id": pid,
    })
    tmp_db.update_document_extraction_status(did, "basis_analysiert")

    result = fn(batch_nr=1)
    # routing_modus Default False -> keine routing-Felder
    for d in result["dokumente"]:
        assert "routing" not in d


# ── 3) dokument_aktion_ausfuehren ────────────────────────────────────────


def _make_bewerbung(tmp_db, profile_id):
    return tmp_db.add_application({
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


def test_aktion_noop_korrespondenz_setzt_angewendet(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    mcp = _register(tmp_db)
    fn = mcp.tools["dokument_aktion_ausfuehren"]

    did = tmp_db.add_document({
        "filename": "rauschen.eml", "doc_type": "sonstiges",
        "extracted_text": "x", "profile_id": pid,
    })
    tmp_db.update_document_extraction_status(did, "basis_analysiert")

    result = fn(dokument_id=did, aktion="noop_korrespondenz_abschliessen")
    assert result["status"] == "umgesetzt"
    assert result["extraction_status_nachher"] == "angewendet"

    conn = tmp_db.connect()
    row = conn.execute(
        "SELECT extraction_status FROM documents WHERE id=?", (did,)
    ).fetchone()
    assert row["extraction_status"] == "angewendet"


def test_aktion_bewerbung_status_setzen_delegiert(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    aid = _make_bewerbung(tmp_db, pid)
    did = tmp_db.add_document({
        "filename": "absage.eml", "doc_type": "absage",
        "extracted_text": "Leider", "profile_id": pid,
        "linked_application_id": aid,
    })
    tmp_db.update_document_extraction_status(did, "basis_analysiert")

    mcp = _register(tmp_db)
    fn = mcp.tools["dokument_aktion_ausfuehren"]

    result = fn(
        dokument_id=did,
        aktion="bewerbung_status_setzen",
        args={"bewerbung_id": aid, "neuer_status": "abgelehnt"},
    )
    assert result["status"] == "umgesetzt"
    assert result["extraction_status_nachher"] == "angewendet"

    # Bewerbung ist auf abgelehnt
    conn = tmp_db.connect()
    bw = conn.execute(
        "SELECT status FROM applications WHERE id=?", (aid,)
    ).fetchone()
    assert bw["status"] == "abgelehnt"
    # Auto-Veralten-Hook (#657) hat das Doku auf veraltet gesetzt
    doc_row = conn.execute(
        "SELECT lifecycle FROM documents WHERE id=?", (did,)
    ).fetchone()
    assert doc_row["lifecycle"] == "veraltet"


def test_aktion_eingangsbestaetigung(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    aid = _make_bewerbung(tmp_db, pid)
    did = tmp_db.add_document({
        "filename": "ack.eml", "doc_type": "eingangsbestaetigung",
        "extracted_text": "Eingang bestaetigt", "profile_id": pid,
        "linked_application_id": aid,
    })
    tmp_db.update_document_extraction_status(did, "basis_analysiert")

    mcp = _register(tmp_db)
    fn = mcp.tools["dokument_aktion_ausfuehren"]

    result = fn(
        dokument_id=did,
        aktion="eingangsbestaetigung",
        args={"bewerbung_id": aid},
    )
    assert result["status"] == "umgesetzt"
    conn = tmp_db.connect()
    bw = conn.execute(
        "SELECT status FROM applications WHERE id=?", (aid,)
    ).fetchone()
    assert bw["status"] == "eingangsbestaetigung"


def test_aktion_bewerbung_erfassen_legt_an(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    did = tmp_db.add_document({
        "filename": "anfrage.eml", "doc_type": "recruiter_anfrage",
        "extracted_text": "Interessante Stelle", "profile_id": pid,
    })
    tmp_db.update_document_extraction_status(did, "basis_analysiert")

    mcp = _register(tmp_db)
    fn = mcp.tools["dokument_aktion_ausfuehren"]

    result = fn(
        dokument_id=did,
        aktion="bewerbung_erfassen",
        args={"firma": "Beispiel GmbH", "titel": "Architekt"},
    )
    assert result["status"] == "umgesetzt"

    # Neue Bewerbung wurde angelegt
    conn = tmp_db.connect()
    bw = conn.execute(
        "SELECT title, company FROM applications WHERE company=?",
        ("Beispiel GmbH",),
    ).fetchone()
    assert bw is not None
    assert bw["title"] == "Architekt"


def test_aktion_unbekannt_meldet_fehler(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    did = tmp_db.add_document({
        "filename": "x.eml", "doc_type": "sonstiges",
        "extracted_text": "x", "profile_id": pid,
    })

    mcp = _register(tmp_db)
    fn = mcp.tools["dokument_aktion_ausfuehren"]

    result = fn(dokument_id=did, aktion="erfunden")
    assert "fehler" in result
    assert "bekannte_aktionen" in result


def test_aktion_profil_extraktion_liefert_anleitung(tmp_db):
    """Fuer profil_extraktion delegieren wir nicht — User-Bestaetigung
    notwendig. Tool gibt nur Anleitung zurueck."""
    tmp_db.create_profile("Test", "test@example.com")
    pid = tmp_db.get_active_profile_id()
    did = tmp_db.add_document({
        "filename": "cv.pdf", "doc_type": "lebenslauf",
        "extracted_text": "Profil", "profile_id": pid,
    })

    mcp = _register(tmp_db)
    fn = mcp.tools["dokument_aktion_ausfuehren"]

    result = fn(dokument_id=did, aktion="profil_extraktion")
    assert result["status"] == "anleitung"
    assert "extraktion_starten" in result["anleitung"]


# ── 4) Rauschen-Heuristik ────────────────────────────────────────────────


def test_is_pure_notification_linkedin_digest():
    from bewerbungs_assistent.services.document_handlers import is_pure_notification
    assert is_pure_notification(
        sender="messaging-digest-noreply@linkedin.com",
        subject="Anna hat dir eine Nachricht gesendet",
    ) is True
    assert is_pure_notification(
        sender="Notifications <noreply@linkedin.com>",
        subject="Jobs you may be interested in",
    ) is True


def test_is_pure_notification_xing_robot():
    from bewerbungs_assistent.services.document_handlers import is_pure_notification
    assert is_pure_notification(
        sender="mailrobot@mail.xing.com",
        subject="Neue Recruiting-Nachricht",
    ) is True


def test_is_pure_notification_echte_mail_false():
    from bewerbungs_assistent.services.document_handlers import is_pure_notification
    assert is_pure_notification(
        sender="recruiter@beispielfirma.de",
        subject="Ihre Bewerbung — Einladung zum Gespraech",
    ) is False
    assert is_pure_notification(
        sender="hr@beispielfirma.de",
        subject="Eingangsbestaetigung",
    ) is False


def test_is_pure_notification_umlaute_normalized():
    from bewerbungs_assistent.services.document_handlers import is_pure_notification
    # Mit echten Umlauten muss der Match weiterhin greifen
    assert is_pure_notification(
        sender="recruiter@example.com",
        subject="Neue Empfehlung für Dich",
    ) is True


def test_is_pure_notification_leere_werte():
    from bewerbungs_assistent.services.document_handlers import is_pure_notification
    assert is_pure_notification(sender=None, subject=None) is False
    assert is_pure_notification(sender="", subject="") is False
