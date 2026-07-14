"""Tests fuer v1.8.0-beta.0 — I10 Komponenten-Framework (#751) + E19 Auto-OCR (#750-T2).

Alles ohne echtes Tesseract und ohne Netz: Detection/Downloads werden
gemockt. Der echte Install-Pfad ist Beta-Exit-Kriterium (frische Win11-
24H2-Maschine), nicht CI-Aufgabe.
"""
from __future__ import annotations

import logging
from pathlib import Path
from types import SimpleNamespace

import pytest


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


def _kein_binary(monkeypatch):
    """Detection hart auf 'nicht vorhanden' — unabhaengig von der Dev-Maschine."""
    from bewerbungs_assistent.services import components
    monkeypatch.setattr(components, "find_component_binary",
                        lambda db, name: None)
    # ocr_service importiert die Funktion direkt — auch dort patchen
    from bewerbungs_assistent.services import ocr_service
    monkeypatch.setattr(ocr_service, "find_component_binary",
                        lambda db, name: None)


# ── Schema v49 + DB-Helper ───────────────────────────────────────────────


def test_schema_v49_components_tabelle(tmp_db):
    conn = tmp_db.connect()
    cols = {r["name"] for r in conn.execute("PRAGMA table_info(components)")}
    assert {"name", "status", "version", "install_path",
            "installed_at", "last_error", "updated_at"} <= cols


def test_component_state_upsert(tmp_db):
    assert tmp_db.get_component_state("tesseract") is None
    tmp_db.set_component_state("tesseract", "wird_installiert")
    state = tmp_db.get_component_state("tesseract")
    assert state["status"] == "wird_installiert"
    assert not state["installed_at"]
    tmp_db.set_component_state("tesseract", "installiert",
                               install_path="C:/x/tesseract.exe",
                               version="5.4.0")
    state = tmp_db.get_component_state("tesseract")
    assert state["status"] == "installiert"
    assert state["install_path"] == "C:/x/tesseract.exe"
    assert state["version"] == "5.4.0"
    assert state["installed_at"]
    # None-Felder bleiben unveraendert
    tmp_db.set_component_state("tesseract", "fehler", last_error="kaputt")
    state = tmp_db.get_component_state("tesseract")
    assert state["install_path"] == "C:/x/tesseract.exe"
    assert state["last_error"] == "kaputt"


# ── components-Service ───────────────────────────────────────────────────


def test_status_nicht_installiert(tmp_db, monkeypatch):
    _kein_binary(monkeypatch)
    from bewerbungs_assistent.services import components
    status = components.get_component_status(tmp_db, "tesseract")
    assert status["verfuegbar"] is False
    assert status["status"] == "nicht_installiert"
    assert status["groesse_mb"] > 0
    assert status["lizenz"] == "Apache-2.0"


def test_status_extern_erkannt(tmp_db, tmp_path, monkeypatch):
    """PATH-Fund wird als 'extern' ausgewiesen — PBP fasst ihn nie an."""
    from bewerbungs_assistent.services import components
    fake = tmp_path / "tesseract.exe"
    fake.write_text("x")
    monkeypatch.setattr(components.shutil, "which",
                        lambda name: str(fake) if name == "tesseract" else None)
    monkeypatch.setattr(components, "_binary_version", lambda b: "5.4.0")
    status = components.get_component_status(tmp_db, "tesseract")
    assert status["verfuegbar"] is True
    assert status["quelle"] == "extern"
    assert status["version"] == "5.4.0"


def test_set_manual_path_validiert(tmp_db, tmp_path, monkeypatch):
    from bewerbungs_assistent.services import components
    result = components.set_manual_path(tmp_db, "tesseract",
                                        str(tmp_path / "gibtsnicht"))
    assert result["status"] == "fehler"

    # binary_name ist plattformabhaengig (tesseract.exe vs tesseract) —
    # der Ordner-Zweig unten sucht danach (CI-Fund: Linux-Runner)
    fake = tmp_path / components.COMPONENT_DEFS["tesseract"]["binary_name"]
    fake.write_text("x")
    # Datei existiert, antwortet aber nicht auf --version -> Fehler
    monkeypatch.setattr(components, "_binary_version", lambda b: "")
    assert components.set_manual_path(tmp_db, "tesseract", str(fake))["status"] == "fehler"

    monkeypatch.setattr(components, "_binary_version", lambda b: "5.3.1")
    result = components.set_manual_path(tmp_db, "tesseract", str(fake))
    assert result["status"] == "installiert"
    assert tmp_db.get_component_state("tesseract")["install_path"] == str(fake)
    # Ordner-Angabe funktioniert auch
    result = components.set_manual_path(tmp_db, "tesseract", str(tmp_path))
    assert result["status"] == "installiert"


def test_uninstall_entfernt_nur_pbp_installation(tmp_db, tmp_path, monkeypatch):
    from bewerbungs_assistent.services import components
    comp_dir = tmp_path / "components"
    monkeypatch.setattr(components, "components_dir", lambda: comp_dir)
    target = comp_dir / "tesseract"
    target.mkdir(parents=True)
    (target / "tesseract.exe").write_text("x")
    tmp_db.set_component_state("tesseract", "installiert",
                               install_path=str(target / "tesseract.exe"))
    monkeypatch.setattr(components, "find_component_binary",
                        lambda db, name: None)
    result = components.uninstall_component(tmp_db, "tesseract")
    assert result["status"] == "entfernt"
    assert result["pbp_installation_geloescht"] is True
    assert not target.exists()
    assert tmp_db.get_component_state("tesseract")["status"] == "nicht_installiert"


def test_install_component_erkennt_vorhandenes(tmp_db, tmp_path, monkeypatch):
    """Existierendes Binary -> kein Download, Zustand wird registriert."""
    from bewerbungs_assistent.services import components
    fake = tmp_path / "tesseract.exe"
    fake.write_text("x")
    monkeypatch.setattr(components, "find_component_binary",
                        lambda db, name: str(fake))
    monkeypatch.setattr(components, "_binary_version", lambda b: "5.4.0")
    result = components.install_component(tmp_db, "tesseract")
    assert result["status"] == "installiert"
    assert "heruntergeladen" in result["hinweis"]
    assert tmp_db.get_component_state("tesseract")["status"] == "installiert"


def test_install_component_fehlerpfad_setzt_status(tmp_db, monkeypatch):
    """Download-Fehler -> Status 'fehler' + last_error, kein Crash."""
    from bewerbungs_assistent.services import components
    monkeypatch.setattr(components, "find_component_binary",
                        lambda db, name: None)
    monkeypatch.setattr(components, "_download",
                        lambda *a, **kw: (_ for _ in ()).throw(
                            RuntimeError("kein Netz")))
    monkeypatch.setattr(components.sys, "platform", "win32")
    result = components.install_component(tmp_db, "tesseract")
    assert result["status"] == "fehler"
    assert "kein Netz" in result["fehler"]
    state = tmp_db.get_component_state("tesseract")
    assert state["status"] == "fehler"
    assert "kein Netz" in state["last_error"]


def test_start_install_job_verhindert_doppelstart(tmp_db, monkeypatch):
    """Deterministisch via Gate — und der Job-Thread wird VOR dem Fixture-
    Teardown zu Ende gewartet. Ohne das racet der Daemon-Thread mit
    db.close(): SQLite-Use-after-close segfaultete auf dem Linux-CI
    (exit 139, Fund 2026-07-14). ensure_language ebenfalls stubben —
    sonst macht der Thread echte DB-/Netz-Zugriffe."""
    import threading
    import time
    from bewerbungs_assistent.services import components

    gate = threading.Event()

    def blocked_install(db, name, progress=None):
        gate.wait(timeout=5)
        return {"status": "installiert"}

    monkeypatch.setattr(components, "install_component", blocked_install)
    monkeypatch.setattr(components, "ensure_language",
                        lambda db, lang="deu", progress=None: {"status": "vorhanden"})

    first = components.start_install_job(tmp_db, "tesseract")
    assert first["status"] == "gestartet"
    # Job haengt im Gate -> zweiter Start MUSS blocken
    second = components.start_install_job(tmp_db, "tesseract")
    assert second["status"] == "laeuft_bereits"
    assert second["job_id"] == first["job_id"]

    gate.set()
    for _ in range(200):  # max ~10s
        job = tmp_db.get_background_job(first["job_id"])
        if job and job.get("status") in ("fertig", "fehler"):
            break
        time.sleep(0.05)
    else:
        pytest.fail("Install-Job wurde nicht fertig — Thread wuerde ins Teardown racen")
    assert job["status"] == "fertig"

    assert components.start_install_job(tmp_db, "unbekannt")["status"] == "fehler"


# ── ocr_service ──────────────────────────────────────────────────────────


def _text_pdf(path: Path, text: str = "Echter Text " * 20):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 10, text)
    pdf.output(str(path))


def _scan_pdf(path: Path, seiten: int = 2):
    """PDF ohne Text-Ebene (nur Grafik) — wie ein Scan."""
    from fpdf import FPDF
    pdf = FPDF()
    for _ in range(seiten):
        pdf.add_page()
        pdf.rect(20, 20, 100, 80)
    pdf.output(str(path))


def test_is_scanned_pdf(tmp_path):
    from bewerbungs_assistent.services.ocr_service import is_scanned_pdf
    text_pdf = tmp_path / "text.pdf"
    _text_pdf(text_pdf)
    scan_pdf = tmp_path / "scan.pdf"
    _scan_pdf(scan_pdf)
    assert is_scanned_pdf(text_pdf) is False
    assert is_scanned_pdf(scan_pdf) is True
    assert is_scanned_pdf(tmp_path / "fehlt.pdf") is False
    assert is_scanned_pdf(__file__) is False  # kein PDF


def test_ocr_pdf_ohne_komponente_liefert_angebot(tmp_db, tmp_path, monkeypatch):
    _kein_binary(monkeypatch)
    from bewerbungs_assistent.services import ocr_service
    scan = tmp_path / "scan.pdf"
    _scan_pdf(scan)
    result = ocr_service.ocr_pdf(tmp_db, scan)
    assert result["status"] == "komponente_fehlt"
    angebot = result["angebot"]
    assert angebot["komponente"] == "tesseract"
    assert angebot["groesse_mb"] > 0
    assert "bestaetigt=True" in angebot["naechster_schritt_mcp"]
    assert "nie ungefragt" in angebot["naechster_schritt_mcp"]


def test_ocr_pdf_mit_fake_tesseract(tmp_db, tmp_path, monkeypatch):
    """Rendering echt (pypdfium2), Tesseract-Aufruf gemockt."""
    from bewerbungs_assistent.services import ocr_service
    scan = tmp_path / "scan.pdf"
    _scan_pdf(scan, seiten=3)

    monkeypatch.setattr(ocr_service, "find_component_binary",
                        lambda db, name: "C:/fake/tesseract.exe")
    monkeypatch.setattr(ocr_service, "_pick_langs",
                        lambda db: ("deu+eng", ""))
    from bewerbungs_assistent.services import components
    monkeypatch.setattr(components, "get_component_status",
                        lambda db, name: {"version": "5.4.0"})
    monkeypatch.setattr(ocr_service, "get_component_status",
                        lambda db, name: {"version": "5.4.0"})

    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        assert cmd[0] == "C:/fake/tesseract.exe"
        assert cmd[2] == "stdout"
        assert "-l" in cmd and "deu+eng" in cmd
        n = len(calls)
        return SimpleNamespace(returncode=0, stdout=f"Seite {n} Inhalt", stderr="")

    monkeypatch.setattr(ocr_service.subprocess, "run", fake_run)
    result = ocr_service.ocr_pdf(tmp_db, scan, max_seiten=2)
    assert result["status"] == "ok"
    assert result["seiten"] == 2
    assert result["seiten_gesamt"] == 3
    assert "Seite 1 Inhalt" in result["text"]
    assert "Seite 2 Inhalt" in result["text"]
    assert "hinweis_seiten" in result  # Cap griff
    assert len(calls) == 2  # eine OCR pro Seite, kein Retry noetig

    header = ocr_service.provenienz_header(result)
    assert header.startswith("[OCR via Tesseract 5.4.0")
    assert "deu+eng" in header


# ── MCP-Tools ────────────────────────────────────────────────────────────


def _tools(tmp_db, modul):
    mcp = FakeMCP()
    modul.register(mcp, tmp_db, logging.getLogger("test"))
    return mcp.tools


def test_tool_komponenten_status(tmp_db, monkeypatch):
    _kein_binary(monkeypatch)
    from bewerbungs_assistent.tools import komponenten
    tools = _tools(tmp_db, komponenten)
    result = tools["komponenten_status"]()
    namen = [k["name"] for k in result["komponenten"]]
    assert "tesseract" in namen
    assert "ollama" in result  # mit-angezeigt, eigenstaendig verwaltet
    assert "Lokale KI" in result["ollama"]["verwaltung"]


def test_tool_installieren_verlangt_zustimmung(tmp_db, monkeypatch):
    """Ohne bestaetigt=True gibt es NUR das Angebot — kein Job, kein Download."""
    _kein_binary(monkeypatch)
    from bewerbungs_assistent.tools import komponenten
    from bewerbungs_assistent.services import components
    gestartet = []
    monkeypatch.setattr(components, "start_install_job",
                        lambda db, name: gestartet.append(name) or
                        {"status": "gestartet", "job_id": "j1"})
    tools = _tools(tmp_db, komponenten)

    result = tools["komponente_installieren"](name="tesseract")
    assert result["status"] == "zustimmung_erforderlich"
    assert result["angebot"]["download_groesse_mb"] > 0
    assert result["angebot"]["lizenz"] == "Apache-2.0"
    assert gestartet == []  # NICHTS gestartet

    result = tools["komponente_installieren"](name="tesseract", bestaetigt=True)
    assert result["status"] == "gestartet"
    assert gestartet == ["tesseract"]


def test_tool_installieren_bereits_vorhanden(tmp_db, tmp_path, monkeypatch):
    from bewerbungs_assistent.tools import komponenten
    from bewerbungs_assistent.services import components
    fake = tmp_path / "tesseract.exe"
    fake.write_text("x")
    monkeypatch.setattr(components, "find_component_binary",
                        lambda db, name: str(fake))
    monkeypatch.setattr(components, "_binary_version", lambda b: "5.4.0")
    tools = _tools(tmp_db, komponenten)
    result = tools["komponente_installieren"](name="tesseract", bestaetigt=True)
    assert result["status"] == "bereits_vorhanden"


def test_tool_dokument_ocr_ohne_komponente(tmp_db, tmp_path, monkeypatch):
    _kein_binary(monkeypatch)
    from bewerbungs_assistent.tools import dokumente
    scan = tmp_path / "zeugnis_scan.pdf"
    _scan_pdf(scan)
    doc_id = tmp_db.add_document({
        "filename": "zeugnis_scan.pdf", "filepath": str(scan),
        "doc_type": "zeugnis",
    })
    tools = _tools(tmp_db, dokumente)
    result = tools["dokument_ocr_ausfuehren"](dokument_id=doc_id)
    assert result["status"] == "komponente_fehlt"
    assert "bestaetigt=True" in result["hinweis"]


def test_tool_dokument_ocr_speichert_mit_provenienz(tmp_db, tmp_path, monkeypatch):
    from bewerbungs_assistent.tools import dokumente
    from bewerbungs_assistent.services import ocr_service
    scan = tmp_path / "zeugnis_scan.pdf"
    _scan_pdf(scan)
    doc_id = tmp_db.add_document({
        "filename": "zeugnis_scan.pdf", "filepath": str(scan),
        "doc_type": "zeugnis", "extracted_text": "",
    })
    monkeypatch.setattr(
        ocr_service, "ocr_pdf",
        lambda db, fp, max_seiten=15: {
            "status": "ok", "text": "Staatlich geprüfter Techniker",
            "seiten": 1, "seiten_gesamt": 1, "sprachen": "deu+eng",
            "version": "5.4.0", "dauer_s": 1.2,
        })
    tools = _tools(tmp_db, dokumente)
    result = tools["dokument_ocr_ausfuehren"](dokument_id=doc_id)
    assert result["status"] == "ocr_gespeichert"
    doc = tmp_db.get_document(doc_id)
    assert doc["extracted_text"].startswith("[OCR via Tesseract 5.4.0")
    assert "Techniker" in doc["extracted_text"]
    assert "dokument_profil_extrahieren" in result["hinweis"]


def test_tool_dokument_ocr_nur_pdf(tmp_db):
    from bewerbungs_assistent.tools import dokumente
    doc_id = tmp_db.add_document({
        "filename": "notiz.txt", "filepath": "/x/notiz.txt",
        "doc_type": "sonstiges",
    })
    tools = _tools(tmp_db, dokumente)
    result = tools["dokument_ocr_ausfuehren"](dokument_id=doc_id)
    assert "fehler" in result


# ── Upload-Integration (Dashboard) ───────────────────────────────────────


def test_extract_document_text_liefert_ocr_angebot(tmp_db, tmp_path, monkeypatch):
    """Scan-PDF ohne Komponente -> 3-Tupel mit ocr_info='erforderlich'."""
    _kein_binary(monkeypatch)
    from bewerbungs_assistent import dashboard
    monkeypatch.setattr(dashboard, "_db", tmp_db)
    scan = tmp_path / "scan.pdf"
    _scan_pdf(scan)
    extracted, email_ctx, ocr_info = dashboard._extract_document_text(scan)
    assert extracted.strip() == ""
    assert email_ctx is None
    assert ocr_info["ocr"] == "erforderlich"
    assert ocr_info["angebot"]["komponente"] == "tesseract"


def test_extract_document_text_normales_pdf_ohne_ocr_info(tmp_db, tmp_path, monkeypatch):
    from bewerbungs_assistent import dashboard
    monkeypatch.setattr(dashboard, "_db", tmp_db)
    pdf = tmp_path / "text.pdf"
    _text_pdf(pdf)
    extracted, email_ctx, ocr_info = dashboard._extract_document_text(pdf)
    assert "Echter Text" in extracted
    assert ocr_info is None
