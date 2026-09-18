"""v1.7.120 — ein Knopf, der eine Anleitung verspricht, liefert sie auch.

Gemeldet am 18.09.2026 mit zwei Bildschirmfotos: der Knopf "Dokumente
verarbeiten" zeigte drei Meldungen uebereinander ("konnte nicht geladen
werden", "Anleitung kopiert!", "Verarbeitungs-Prompt kopiert"), und in
Claude Desktop kam "/dokumente_verarbeiten" an — als unbekannter Skill.

Ursache: es gibt DREI Listen von Prompts — die registrierten MCP-Prompts
(`prompts.py`), den Katalog (`prompt_katalog.py`) und die Registry, gegen
die das Dashboard aufloest (`tools/workflows._prompt_registry`). Der Guard
aus #979 haelt die ersten beiden gegeneinander. Die dritte — die einzige,
die der Knopf tatsaechlich fragt — pruefte niemand, und ihr fehlten
`dokumente_verarbeiten` und `problem_melden`. Dritter Fall nach #560.
"""
import asyncio
import importlib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

FRONTEND = _repo() / "frontend" / "src"


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17120_prompts_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _katalog_prompts() -> set[str]:
    from bewerbungs_assistent.services import prompt_katalog
    return {e["prompt"] for e in prompt_katalog.alle()}


def ohne_kommentare(quelle: str) -> str:
    quelle = re.sub(r"/\*.*?\*/", "", quelle, flags=re.S)
    return "\n".join(z for z in quelle.splitlines() if not z.strip().startswith("//"))


# ══ Die dritte Liste ════════════════════════════════════════════════

def test_jeder_katalogeintrag_laesst_sich_im_dashboard_aufloesen(umgebung):
    """Der Guard, der gefehlt hat: Katalog gegen die Registry, die der
    Knopf fragt."""
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    db, _ = umgebung
    registry = _prompt_registry(db)
    fehlt = sorted(_katalog_prompts() - set(registry))
    assert not fehlt, (
        f"Im Katalog, aber nicht aufloesbar: {fehlt}. Der Knopf dazu bekaeme "
        "ein 404 — in tools/workflows._prompt_registry eintragen.")


def test_die_beiden_gemeldeten_luecken_sind_zu(umgebung):
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    db, _ = umgebung
    registry = _prompt_registry(db)
    assert "dokumente_verarbeiten" in registry
    # Ausgerechnet der Weg, auf dem man so etwas meldet, fehlte ebenfalls.
    assert "problem_melden" in registry


def test_jeder_registry_eintrag_liefert_wirklich_text(umgebung):
    """Aufrufen, nicht nur nachsehen: ein Eintrag, der beim Aufruf
    umfaellt, waere dieselbe Sackgasse mit anderem Statuscode."""
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    db, _ = umgebung
    for name, fn in _prompt_registry(db).items():
        text = fn()
        assert isinstance(text, str) and len(text) > 200, name


def test_dashboard_und_mcp_liefern_denselben_text(umgebung):
    """Eine Quelle, zwei Wege — sonst laeuft der Knopf-Text vom
    MCP-Prompt weg (#979: `bewerbung_schreiben` war schon einmal
    abgewichen)."""
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    db, mcp = umgebung

    async def _mcp_text():
        prompt = await mcp.get_prompt("dokumente_verarbeiten")
        ergebnis = await prompt.render({})
        return "".join(getattr(m.content, "text", str(m.content)) for m in ergebnis)

    assert _prompt_registry(db)["dokumente_verarbeiten"]() == asyncio.run(_mcp_text())


def test_jeder_mcp_prompt_laesst_sich_mit_profil_und_daten_rendern(umgebung):
    """`dokumente_verarbeiten` fragte seit beta.58 (#634) die Spalte
    `application_id` ab, die `linked_application_id` heisst — und stuerzte
    damit fuer JEDEN ab, der ein Profil hat. Aufgefallen ist es ueber ein
    Jahr nicht, weil kein Test einen Prompt MIT Profil gerendert hat: ohne
    Profil wird die Abfrage uebersprungen.

    Deshalb hier: Profil, ein Dokument, eine Bewerbung, eine Stelle — und
    dann JEDER registrierte Prompt, nicht nur der gemeldete."""
    db, mcp = umgebung
    app_id = db.add_application({"title": "Stammdaten Migration",
                                 "company": "Musterfirma GmbH", "status": "beworben"})
    db.add_document({"filename": "absage.eml", "doc_type": "korrespondenz",
                     "extracted_text": "Sehr geehrte Damen und Herren, leider ...",
                     "extraction_status": "nicht_extrahiert",
                     "linked_application_id": app_id})

    async def _alle():
        namen = list((await mcp.get_prompts()).keys()) if hasattr(mcp, "get_prompts") \
            else [p.name for p in await mcp.list_prompts()]
        ergebnis = {}
        for name in namen:
            prompt = await mcp.get_prompt(name)
            try:
                gerendert = await prompt.render({})
                ergebnis[name] = "".join(
                    getattr(m.content, "text", str(m.content)) for m in gerendert)
            except Exception as exc:  # der Befund, nicht der Abbruch
                ergebnis[name] = exc
        return ergebnis

    ergebnis = asyncio.run(_alle())
    assert len(ergebnis) >= 20, sorted(ergebnis)
    kaputt = {n: repr(e) for n, e in ergebnis.items() if isinstance(e, Exception)}
    assert not kaputt, kaputt
    # Das offene Dokument steht im gemeldeten Prompt — samt Verknuepfung.
    text = ergebnis["dokumente_verarbeiten"]
    assert "absage.eml" in text and "verknuepft" in text


def test_der_endpunkt_antwortet_fuer_jeden_katalogeintrag():
    """Der ganze Weg, den der Knopf nimmt."""
    from fastapi.testclient import TestClient

    tmpdir = tempfile.mkdtemp(prefix="pbp_v17120_api_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.dashboard as dash
    importlib.reload(dash)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path)
    db.save_profile({"name": "Test"})
    dash._db = db
    try:
        client = TestClient(dash.app)
        for name in sorted(_katalog_prompts()):
            r = client.get(f"/api/workflow-prompt/{name}")
            assert r.status_code == 200, f"{name}: HTTP {r.status_code}"
            assert len(r.json()["prompt"]) > 200, name
        # Ein Werkzeugname ist KEIN Workflow — und das ist richtig so.
        assert client.get("/api/workflow-prompt/firmen_recherche").status_code == 404
        # Argumente kommen an (#706) — der Kalender-Knopf verlor sie bisher.
        r = client.get("/api/workflow-prompt/interview_vorbereitung",
                       params={"stelle": "Pruefstelle Stammdaten", "firma": "Musterfirma GmbH"})
        assert "Pruefstelle Stammdaten" in r.json()["prompt"]
    finally:
        db.close()
        shutil.rmtree(tmpdir, ignore_errors=True)


# ══ Die Oberflaeche ═════════════════════════════════════════════════

def test_jeder_schraegstrich_verweis_der_oberflaeche_ist_ein_workflow(umgebung):
    """Ein "/name" in der Oberflaeche ist ein Workflow oder ein Fehler.
    `/firmen_recherche` war ein Werkzeugname und lief in dasselbe 404."""
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    db, _ = umgebung
    bekannt = set(_prompt_registry(db))
    gefunden = set()
    for datei in FRONTEND.rglob("*.jsx"):
        quelle = ohne_kommentare(datei.read_text(encoding="utf-8"))
        for treffer in re.finditer(r"copyPrompt\(\s*[`\"]/([a-z_]+)", quelle):
            gefunden.add(treffer.group(1))
    assert gefunden, "kein einziger Verweis gefunden — der Test sieht nichts"
    assert gefunden <= bekannt, f"Kein Workflow: {sorted(gefunden - bekannt)}"


def test_copyprompt_kopiert_nichts_wenn_die_anleitung_fehlt():
    """Der rohe Schraegstrich-Befehl ist kein Ersatz: in Claude Desktop
    ist er ein unbekannter Skill. Und "Anleitung kopiert!" darueber war
    eine Erfolgsmeldung ueber nichts (#994/#997)."""
    app = ohne_kommentare((FRONTEND / "App.jsx").read_text(encoding="utf-8"))
    rumpf = app[app.index("async function copyPrompt("):app.index("async function refreshChrome(")]
    assert "Originaltext wurde kopiert" not in rumpf
    assert "zerlegePrompt(" in rumpf and "workflowPfad(" in rumpf
    fehlerzweig = rumpf[rumpf.index("if (!resolved?.prompt)"):]
    assert fehlerzweig.index("return false") < fehlerzweig.index("copyToClipboard("), (
        "im Fehlerfall wird vor dem Kopieren ausgestiegen")
    assert "return true" in rumpf


def test_der_dokumente_knopf_meldet_nicht_doppelt():
    seite = ohne_kommentare((FRONTEND / "pages" / "DocumentsPage.jsx").read_text(encoding="utf-8"))
    assert "Verarbeitungs-Prompt kopiert" not in seite
    assert 'copyPrompt("/dokumente_verarbeiten")' in seite


def test_die_firmen_recherche_geht_als_satz_hinaus():
    seite = ohne_kommentare((FRONTEND / "pages" / "ApplicationsPage.jsx").read_text(encoding="utf-8"))
    assert "`/firmen_recherche" not in seite
    assert 'werkzeugAufruf(' in seite and '"firmen_recherche"' in seite
    assert "bewerbung_id: bid" in seite


def test_der_node_test_laeuft_in_der_ci():
    ci = (_repo() / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "frontend/src/lib/promptAufloesung.test.mjs" in ci
