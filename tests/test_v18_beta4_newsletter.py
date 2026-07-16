"""Tests fuer v1.8.0-beta.4 — J5 Newsletter-Ingest (#525).

Leitplanke: Ebene 0 (Link-Extraktion) traegt allein, KI-frei. Ollama ist
strikt optionaler Fallback und wird hier gemockt bzw. als abwesend
behandelt.
"""
from __future__ import annotations

import logging
import os
import sys
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


NEWSLETTER_HTML = """
<html><body>
<h1>Neue Jobs fuer dich</h1>
<a href="https://www.stepstone.de/stellenangebote--PLM-Consultant-Hamburg-Acme-Solutions-GmbH--9876543-inline.html?utm_source=email&utm_campaign=alert">
  PLM Consultant (m/w/d) bei Acme Solutions GmbH</a>
<a href="https://www.linkedin.com/comm/jobs/view/4012345678?trk=email&refId=abc123">
  Senior <b>Projektmanager</b> Digitalisierung</a>
<a href="https://www.arbeitsagentur.de/jobsuche/jobdetail/12345-999-S">Jetzt ansehen</a>
<a href="https://www.stepstone.de/stellenangebote--PLM-Consultant-Hamburg-Acme-Solutions-GmbH--9876543-inline.html?utm_source=other">
  PLM Consultant (m/w/d) bei Acme Solutions GmbH</a>
<a href="https://www.stepstone.de/ueber-uns">Karriere bei StepStone</a>
<a href="https://example.com/unsubscribe">Abmelden</a>
</body></html>
"""


def _eml(tmp_path, sender, subject, html="", text="") -> Path:
    if html:
        msg = MIMEMultipart("alternative")
        if text:
            msg.attach(MIMEText(text, "plain", "utf-8"))
        msg.attach(MIMEText(html, "html", "utf-8"))
    else:
        msg = MIMEText(text, "plain", "utf-8")
    msg["From"] = sender
    msg["To"] = "kandidat@example.com"
    msg["Subject"] = subject
    p = tmp_path / "newsletter.eml"
    p.write_bytes(msg.as_bytes())
    return p


# ── Erkennung (J5.1/J5.2) ────────────────────────────────────────────────


def test_erkennung_builtin_portale(tmp_db):
    from bewerbungs_assistent.services.newsletter_service import erkennung
    q = erkennung({"sender": "StepStone <noreply@stepstone.de>",
                   "subject": "12 neue Jobs"}, tmp_db)
    assert q and q["label"] == "StepStone" and q["erkannt_ueber"] == "portal"
    q = erkennung({"sender": "jobs-noreply@linkedin.com",
                   "subject": "Dein Job-Alert"}, tmp_db)
    assert q and "LinkedIn" in q["label"]
    # Normale Korrespondenz ist KEIN Newsletter
    assert erkennung({"sender": "hr@acme-solutions.de",
                      "subject": "Ihre Bewerbung"}, tmp_db) is None


def test_erkennung_betreff_konservativ(tmp_db):
    from bewerbungs_assistent.services.newsletter_service import erkennung
    q = erkennung({"sender": "alerts@nischenboerse.de",
                   "subject": "Neue Jobs fuer dich: 5 Treffer"}, tmp_db)
    assert q and q["erkannt_ueber"] == "betreff"
    assert erkennung({"sender": "alerts@nischenboerse.de",
                      "subject": "Rechnung Mai"}, tmp_db) is None


def test_erkennung_gelernte_quelle(tmp_db):
    from bewerbungs_assistent.services.newsletter_service import erkennung
    tmp_db.add_newsletter_source("Nischenboerse", "nischenboerse.de",
                                 "wochenupdate")
    q = erkennung({"sender": "news@nischenboerse.de",
                   "subject": "Wochenupdate: Projekte KW29"}, tmp_db)
    assert q and q["erkannt_ueber"] == "gelernt"
    # Betreff-Muster grenzt ein: anderer Betreff -> kein Match
    assert erkennung({"sender": "news@nischenboerse.de",
                      "subject": "AGB-Aenderung"}, tmp_db) is None


# ── Ebene 0: Link-Extraktion ─────────────────────────────────────────────


def test_extract_job_links_portale_dedup_boilerplate():
    from bewerbungs_assistent.services.newsletter_service import extract_job_links
    links = extract_job_links(NEWSLETTER_HTML)
    urls = [l["url"] for l in links]
    # 3 echte Job-Links: StepStone (dedupliziert trotz anderem utm),
    # LinkedIn, Arbeitsagentur. Footer/Ueber-uns/Abmelden fliegen raus.
    assert len(links) == 3
    assert sum("stepstone.de/stellenangebote" in u for u in urls) == 1
    assert any("linkedin.com/comm/jobs/view" in u for u in urls)
    assert any("arbeitsagentur.de/jobsuche/jobdetail" in u for u in urls)

    stepstone = next(l for l in links if "stepstone" in l["url"])
    assert stepstone["titel"] == "PLM Consultant (m/w/d)"
    assert stepstone["firma"] == "Acme Solutions GmbH"
    linkedin = next(l for l in links if "linkedin" in l["url"])
    assert linkedin["titel"] == "Senior Projektmanager Digitalisierung"
    # "Jetzt ansehen" ist Boilerplate -> kein Titel
    agentur = next(l for l in links if "arbeitsagentur" in l["url"])
    assert agentur["titel"] == ""


def test_extract_job_links_plaintext():
    from bewerbungs_assistent.services.newsletter_service import extract_job_links
    text = ("Neue Projekte:\n"
            "https://www.freelance.de/Projekte/Projekt-12345-PLM-Rollout\n"
            "https://www.xing.com/jobs/hamburg-plm-consultant-98765432\n")
    links = extract_job_links("", text)
    assert len(links) == 2
    assert {l["portal"] for l in links} == {"freelance.de", "xing"}


# ── Verarbeitung + Ingest ────────────────────────────────────────────────


def test_verarbeite_newsletter_ingest(tmp_db, monkeypatch):
    from bewerbungs_assistent.services import newsletter_service
    parsed = {"body_html": NEWSLETTER_HTML, "body_text": "",
              "sender": "noreply@stepstone.de", "subject": "Neue Jobs"}
    result = newsletter_service.verarbeite_newsletter(tmp_db, parsed, "StepStone")
    assert result["status"] == "uebernommen"
    assert result["ebene"] == "link-extraktion"
    assert result["gefunden"] == 3
    assert result["neu"] == 3

    jobs = tmp_db.get_active_jobs()
    assert len(jobs) == 3
    assert all(j["source"] == "newsletter:StepStone" for j in jobs)
    plm = next(j for j in jobs if "PLM Consultant" in (j.get("title") or ""))
    assert plm["company"] == "Acme Solutions GmbH"
    # Titel-loser Link bekommt einen sprechenden Platzhalter
    assert any("Stelle aus StepStone-Newsletter" in (j.get("title") or "")
               for j in jobs)
    # Idempotent: gleicher Newsletter nochmal -> keine neuen
    result2 = newsletter_service.verarbeite_newsletter(tmp_db, parsed, "StepStone")
    assert result2["neu"] == 0
    assert len(tmp_db.get_active_jobs()) == 3


def test_verarbeite_ohne_links_ohne_ollama(tmp_db, monkeypatch):
    from bewerbungs_assistent.services import newsletter_service
    monkeypatch.setattr(newsletter_service, "_ollama_fallback",
                        lambda db, parsed: [])
    result = newsletter_service.verarbeite_newsletter(
        tmp_db, {"body_html": "<p>Nur Text ohne Job-Links</p>",
                 "body_text": "nichts"}, "Unbekannt")
    assert result["status"] == "keine_stellen"
    assert tmp_db.get_active_jobs() == []


def test_ollama_fallback_wird_genutzt_wenn_ebene0_leer(tmp_db, monkeypatch):
    from bewerbungs_assistent.services import newsletter_service
    monkeypatch.setattr(
        newsletter_service, "_ollama_fallback",
        lambda db, parsed: [{"titel": "PLM Berater", "firma": "Acme",
                             "url": "https://karriere.acme.example/job/1",
                             "portal": "ollama"}])
    result = newsletter_service.verarbeite_newsletter(
        tmp_db, {"body_html": "", "body_text": "unstrukturierter text"},
        "Nische")
    assert result["status"] == "uebernommen"
    assert result["ebene"] == "ollama"
    assert len(tmp_db.get_active_jobs()) == 1


def test_llm_parser_extract_newsletter_jobs():
    from bewerbungs_assistent.services.llm_service import (
        _parse_extract_newsletter_jobs)
    out = _parse_extract_newsletter_jobs(
        'Hier: [{"titel": "Dev", "firma": "X", "url": "https://a/1"},'
        ' {"title": "Ops", "company": "Y", "url": "https://a/2"}] Ende')
    assert len(out["jobs"]) == 2
    assert out["jobs"][1]["titel"] == "Ops"
    assert _parse_extract_newsletter_jobs("kein json")["jobs"] == []


# ── Upload-Integration + MCP-Tools ───────────────────────────────────────


def test_upload_erkennt_newsletter_und_uebernimmt(tmp_db, tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    try:
        import bewerbungs_assistent.dashboard as dash
        monkeypatch.setattr(dash, "_db", tmp_db)
        from fastapi.testclient import TestClient
        client = TestClient(dash.app)
        eml = _eml(tmp_path, "StepStone <noreply@stepstone.de>",
                   "5 neue Jobs fuer dich", html=NEWSLETTER_HTML)
        resp = client.post("/api/documents/upload",
                           files={"file": ("alert.eml", eml.read_bytes(),
                                           "message/rfc822")})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        nl = data.get("newsletter")
        assert nl and nl["status"] == "uebernommen"
        assert nl["label"] == "StepStone"
        assert nl["gefunden"] == 3
        assert nl["dokument"] == "archiviert"
        assert len(tmp_db.get_active_jobs()) == 3
        doc = tmp_db.get_document(data["id"])
        assert doc.get("lifecycle") == "archiviert"
    finally:
        os.environ.pop("BA_DATA_DIR", None)


def test_tool_newsletter_quelle_markieren_und_verarbeiten(tmp_db, tmp_path):
    from bewerbungs_assistent.tools import dokumente
    eml = _eml(tmp_path, "News <news@nischenboerse.de>",
               "Wochenupdate: neue Projekte",
               text="https://www.freelance.de/Projekte/Projekt-777-PLM\n")
    doc_id = tmp_db.add_document({
        "filename": "wochenupdate.eml", "filepath": str(eml),
        "doc_type": "sonstiges",
    })
    mcp = FakeMCP()
    dokumente.register(mcp, tmp_db, logging.getLogger("test"))

    result = mcp.tools["newsletter_quelle_markieren"](dokument_id=doc_id)
    assert result["status"] == "quelle_gelernt"
    assert result["sender_muster"] == "nischenboerse.de"
    assert result["betreff_muster"] == "wochenupdate"
    assert result["verarbeitung"]["status"] == "uebernommen"
    assert len(tmp_db.get_active_jobs()) == 1

    # Quelle ist gelernt -> Erkennung greift jetzt
    from bewerbungs_assistent.services.newsletter_service import erkennung
    assert erkennung({"sender": "news@nischenboerse.de",
                      "subject": "Wochenupdate: KW30"}, tmp_db) is not None


def test_tool_newsletter_verarbeiten_fehlerbilder(tmp_db):
    from bewerbungs_assistent.tools import dokumente
    mcp = FakeMCP()
    dokumente.register(mcp, tmp_db, logging.getLogger("test"))
    assert "fehler" in mcp.tools["newsletter_verarbeiten"](dokument_id="nix")
    doc_id = tmp_db.add_document({
        "filename": "cv.pdf", "filepath": "/x/cv.pdf", "doc_type": "lebenslauf"})
    assert "fehler" in mcp.tools["newsletter_verarbeiten"](dokument_id=doc_id)
