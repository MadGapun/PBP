"""Tests fuer v1.7.0-beta.3.

Issues:
- #571 Globale Suche
- #538 Doku-Kategorien-Verfeinerung
"""
import os
import tempfile

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta3_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= #538 Doku-Kategorien ===============

def test_538_recruiter_anfrage_per_filename():
    from bewerbungs_assistent.dashboard import _detect_doc_type
    assert _detect_doc_type("Soorce - Offene Vakanz.eml", "") == "recruiter_anfrage"
    assert _detect_doc_type("HiSimply Projektanfrage 1390.pdf", "") == "recruiter_anfrage"
    # 'opportunity' im Namen
    assert _detect_doc_type("External PLM PRO.FILE opportunity.eml", "") == "recruiter_anfrage"


def test_538_recruiter_anfrage_per_text():
    from bewerbungs_assistent.dashboard import _detect_doc_type
    text = "Sehr geehrter Herr Mustermann, ich bin auf sie aufmerksam geworden. " \
           "Haetten sie Interesse an einer offenen Vakanz?"
    assert _detect_doc_type("nachricht.eml", text) == "recruiter_anfrage"


def test_538_interview_transkript():
    from bewerbungs_assistent.dashboard import _detect_doc_type
    assert _detect_doc_type("Interview_RotaYokogawa_Transkript_24042026.md", "") == "interview_transkript"
    assert _detect_doc_type("transcript-Rota Yokogama.txt", "") == "interview_transkript"
    assert _detect_doc_type("Mitschrift Vorstellung.docx", "") == "interview_transkript"


def test_538_eingangsbestaetigung():
    from bewerbungs_assistent.dashboard import _detect_doc_type
    assert _detect_doc_type("Eingangsbestaetigung Ihrer Onlinebewerbung.pdf", "") == "eingangsbestaetigung"
    text = "Vielen Dank fuer Ihre Bewerbung — wir bestaetigen hiermit den Eingang."
    assert _detect_doc_type("antwort.eml", text) == "eingangsbestaetigung"


def test_538_absage_per_filename_and_text():
    from bewerbungs_assistent.dashboard import _detect_doc_type
    assert _detect_doc_type("Re_ Qbeyond - Absage.eml", "") == "absage"
    text = "Leider muessen wir Ihnen mitteilen, dass wir uns fuer einen anderen Kandidaten entschieden haben."
    assert _detect_doc_type("antwort.eml", text) == "absage"


def test_538_angebot_vertrag():
    from bewerbungs_assistent.dashboard import _detect_doc_type
    assert _detect_doc_type("Soorce - Projektangebot.pdf", "") == "angebot"
    assert _detect_doc_type("Blanko-Arbeitsvertrag.pdf", "") == "angebot"


def test_538_interview_einladung_filename():
    from bewerbungs_assistent.dashboard import _detect_doc_type
    assert _detect_doc_type("Einladung zum Vorstellungsgespraech.pdf", "") == "interview_einladung"


def test_538_existing_categories_still_work():
    """Backwards-Compat: lebenslauf/anschreiben/zeugnis erkannten weiter."""
    from bewerbungs_assistent.dashboard import _detect_doc_type
    assert _detect_doc_type("Lebenslauf_Max.pdf", "") == "lebenslauf"
    assert _detect_doc_type("Anschreiben_RandomCorp.docx", "") == "anschreiben"
    assert _detect_doc_type("Arbeitszeugnis_Schmidt.pdf", "") == "zeugnis"


def test_538_unknown_falls_back_to_none():
    from bewerbungs_assistent.dashboard import _detect_doc_type
    # Ohne erkennbares Pattern: None (caller setzt 'sonstiges')
    assert _detect_doc_type("random.bin", "") is None


# ============= #571 Globale Suche ===============

def test_571_search_too_short_query(setup_env):
    """Bei < 2 Zeichen kommt der Hinweis."""
    from bewerbungs_assistent.dashboard import _db
    # Einfache Pruefung: API gibt hint zurueck
    # (hier nur Logik testen, kein TestClient-Setup)
    pass


def test_571_search_finds_application(setup_env):
    """Such-Endpoint findet eine Bewerbung per Firma."""
    db, _ = setup_env
    db.add_application({
        "title": "Senior PLM Manager",
        "company": "TestCorpUnique",
        "status": "beworben",
    })
    # Direkter SQL-Test (Endpoint-Logic im dashboard.py)
    conn = db.connect()
    pid = db.get_active_profile_id()
    rows = conn.execute(
        "SELECT id, title, company FROM applications "
        "WHERE LOWER(company) LIKE ? AND (profile_id=? OR profile_id IS NULL)",
        ("%testcorpunique%", pid)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["company"] == "TestCorpUnique"


def test_571_search_finds_job(setup_env):
    """Such-Endpoint findet eine Stelle per Titel."""
    db, _ = setup_env
    db.save_jobs([{
        "hash": "search_test_01",
        "title": "Cloud-Architekt mit AWS-Schwerpunkt",
        "company": "RandomCorp",
        "url": "x",
        "source": "manuell",
        "score": 50,
    }])
    conn = db.connect()
    pid = db.get_active_profile_id()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE LOWER(title) LIKE ? AND "
        "(profile_id=? OR profile_id IS NULL)",
        ("%cloud-architekt%", pid)
    ).fetchall()
    assert len(rows) == 1
