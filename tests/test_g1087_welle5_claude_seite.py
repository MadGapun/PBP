"""Welle 5 aus #1087 — die Claude-Seite (H21, H22, H25, H28-H32).

* H21 (G1, G14): Werkzeugkatalog mit Tags, Kurzbeschreibungen ohne
  Geschichte, Parametertexten im Eingabeschema und einem Expertenmodus,
  der Wartungs- und Entwicklerwerkzeuge ausblendet.
"""
import ast
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
PAKET = _repo() / "src" / "bewerbungs_assistent"


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_g1087w5_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def ohne_expertenmodus(monkeypatch):
    """Der Server, wie ihn ein Mensch ohne Einstellung startet."""
    monkeypatch.delenv("BA_EXPERTENMODUS", raising=False)
    tmpdir = tempfile.mkdtemp(prefix="pbp_g1087w5x_")
    monkeypatch.setenv("BA_DATA_DIR", tmpdir)
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    if isinstance(erg, dict) and set(erg) == {"result"}:
        return erg["result"]
    return erg


def _werkzeuge(mcp):
    return asyncio.run(mcp.list_tools())


# ══ H21 — Werkzeugkatalog ═══════════════════════════════════════════════

def test_h21_jedes_werkzeug_hat_genau_einen_tag(umgebung):
    from bewerbungs_assistent.services import werkzeug_katalog as k
    _db, mcp = umgebung
    werkzeuge = _werkzeuge(mcp)
    assert len(werkzeuge) > 200
    for w in werkzeuge:
        tags = set(w.tags) & set(k.TAGS)
        assert len(tags) == 1, (w.name, w.tags)


def test_h21_listen_nennen_nur_registrierte_werkzeuge(umgebung):
    from bewerbungs_assistent.services import werkzeug_katalog as k
    _db, mcp = umgebung
    namen = {w.name for w in _werkzeuge(mcp)}
    for liste in (k.WARTUNG, k.ENTWICKLER, k.EINSTELLUNG, set(k.KURZ)):
        fremd = set(liste) - namen
        assert not fremd, f"nicht registriert: {fremd}"


def test_h21_beschreibungen_kurz_und_ohne_geschichte(umgebung):
    _db, mcp = umgebung
    werkzeuge = _werkzeuge(mcp)
    zu_lang = [(w.name, len(w.description)) for w in werkzeuge if len(w.description or "") > 600]
    assert not zu_lang, zu_lang
    geschichte = [w.name for w in werkzeuge
                  if re.search(r"#\d{3,4}|\bv1\.\d|beta\.\d", w.description or "")]
    assert not geschichte, geschichte
    leer = [w.name for w in werkzeuge if len(w.description or "") < 20]
    assert not leer, leer
    gesamt = sum(len(w.description or "") for w in werkzeuge)
    assert gesamt < 100_000, gesamt


def test_h21_kernweg_hat_zweck_und_einsatz_in_300_bis_600_zeichen():
    from bewerbungs_assistent.services import werkzeug_katalog as k
    for name, text in k.KURZ.items():
        assert 300 <= len(text) <= 600, (name, len(text))
        assert not re.search(r"#\d{3}|\bv1\.\d", text), name


def test_h21_parametertexte_stehen_im_eingabeschema(umgebung):
    _db, mcp = umgebung

    async def _tool():
        return await mcp.get_tool("stellen_anzeigen")
    t = asyncio.run(_tool())
    props = t.parameters["properties"]
    assert "aussortiert" in props["filter"].get("description", "")
    assert not re.search(r"#\d{3}", props["nur_beurteilt"].get("description", ""))


def test_h21_generator_nimmt_die_geschichte_heraus():
    from bewerbungs_assistent.services import werkzeug_katalog as k
    doc = ("Zeigt die Stellen an.\n\nSeit v1.7.12 (#827) sinken k.o.-Stellen ans Ende. "
           "Nutze stelle_bewerten fuer einzelne Stellen.\n\nArgs:\n"
           "    filter: 'aktiv' oder 'alle' (#671)\n")
    text = k.beschreibung("irgendwas", doc)
    assert "Zeigt die Stellen an." in text
    assert "stelle_bewerten" in text
    assert "#827" not in text and "v1.7" not in text
    assert k.parameter_texte(doc) == {"filter": "'aktiv' oder 'alle'"}


def test_h21_ohne_expertenmodus_sind_wartung_und_entwickler_ausgeblendet(ohne_expertenmodus):
    from bewerbungs_assistent.services import werkzeug_katalog as k
    _db, mcp = ohne_expertenmodus
    namen = {w.name for w in _werkzeuge(mcp)}
    assert not (k.WARTUNG | k.ENTWICKLER) & namen
    assert {"stellen_anzeigen", "expertenmodus_setzen", "suchkriterien_setzen"} <= namen


def test_h21_expertenmodus_zeigt_sie_wieder(ohne_expertenmodus):
    from bewerbungs_assistent.services import werkzeug_katalog as k
    db, mcp = ohne_expertenmodus
    erg = _call(mcp, "expertenmodus_setzen", {"an": True})
    assert erg["expertenmodus"] is True
    assert db.get_setting("expertenmodus") is True
    namen = {w.name for w in _werkzeuge(mcp)}
    assert (k.WARTUNG | k.ENTWICKLER) <= namen
    _call(mcp, "expertenmodus_setzen", {"an": False})
    namen = {w.name for w in _werkzeuge(mcp)}
    assert not (k.WARTUNG | k.ENTWICKLER) & namen


def test_h21_server_wendet_die_sichtbarkeit_nach_dem_registrieren_an():
    """DoD 8c: der Ausblender wird im Server wirklich aufgerufen."""
    quelle = (PAKET / "server.py").read_text(encoding="utf-8")
    reg = quelle.index("register_all(mcp, db, logger)")
    anw = quelle.index("sichtbarkeit_anwenden(mcp, _werkzeug_katalog.beim_start_sichtbar(db))")
    assert reg < anw


def test_h21_register_all_setzt_tag_und_beschreibung():
    quelle = (PAKET / "tools" / "__init__.py").read_text(encoding="utf-8")
    rumpf = quelle[quelle.index("def registrieren(fn):"):quelle.index("def register_all(")]
    assert 'kwargs.setdefault("tags", {_katalog.tag(name)})' in rumpf
    assert 'kwargs.setdefault("description", _katalog.beschreibung(name, doc))' in rumpf
    assert "_parameter_beschreiben(fn, _katalog.parameter_texte(doc))" in rumpf


def _versteckte_verweise():
    from bewerbungs_assistent.services import werkzeug_katalog as k
    versteckt = k.WARTUNG | k.ENTWICKLER
    funde = []
    for p in sorted(PAKET.rglob("*.py")):
        if p.name in ("werkzeug_katalog.py", "werkzeug_schutz.py"):
            continue
        baum = ast.parse(p.read_text(encoding="utf-8-sig"))
        ueberspringen = set()
        for n in ast.walk(baum):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                if (n.body and isinstance(n.body[0], ast.Expr)
                        and isinstance(getattr(n.body[0], "value", None), ast.Constant)):
                    ueberspringen.add(id(n.body[0].value))
            if isinstance(n, ast.FunctionDef) and n.name in versteckt:
                ueberspringen.update(id(x) for x in ast.walk(n))
        for n in ast.walk(baum):
            if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and id(n) not in ueberspringen):
                for z in versteckt:
                    if (re.search(r"(?<![A-Za-z_])" + z + r"(?![A-Za-z_])", n.value)
                            and "Expertenmodus" not in n.value):
                        funde.append(f"{p.name}:{n.lineno}: {z}")
    return funde


def test_h21_kein_sichtbarer_text_verweist_stumm_auf_ausgeblendetes():
    """Ein ausgeblendetes Werkzeug kann Claude nicht aufrufen. Wer es nennt,
    sagt dazu, dass es den Expertenmodus braucht."""
    assert not _versteckte_verweise()


def test_h21_der_verweis_guard_sieht_etwas(monkeypatch):
    """DoD 8c: ohne die Ausnahme fuer 'Expertenmodus' findet er Verweise."""
    from bewerbungs_assistent.services import werkzeug_katalog as k
    monkeypatch.setattr(k, "WARTUNG", k.WARTUNG | {"stelle_bewerten"})
    assert _versteckte_verweise()


def test_h21_capabilities_kennt_wartung_und_kostenklasse(umgebung):
    from bewerbungs_assistent.services import werkzeug_katalog as k
    _db, mcp = umgebung
    erg = _call(mcp, "pbp_capabilities", {"kategorie": "wartung"})
    text = str(erg)
    for name in k.WARTUNG | k.ENTWICKLER:
        assert name in text
    quelle = (PAKET / "tools" / "analyse.py").read_text(encoding="utf-8-sig")
    teuer = quelle[quelle.index('"claude_teuer_bulk": {'):]
    teuer = teuer[:teuer.index("},")]
    assert "stellen_bulk_bewerten" not in teuer
    gratis = quelle[quelle.index('"gratis_db": {'):quelle.index('"lokal_guenstig": {')]
    assert "stellen_bulk_bewerten" in gratis


def test_h21_endpunkt_nimmt_nur_wahrheitswerte(umgebung):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    db, _mcp = umgebung
    dash._db = db
    c = TestClient(dash.app)
    assert c.get("/api/expertenmodus").json()["expertenmodus"] is False
    assert c.put("/api/expertenmodus", json={"an": "ja"}).status_code == 400
    assert c.put("/api/expertenmodus", json={"an": True}).json()["expertenmodus"] is True
    assert db.get_setting("expertenmodus") is True


def test_h21_schalter_im_dashboard():
    seite = (_repo() / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    assert '<ExpertenmodusCard pushToast={pushToast} />' in seite
    assert 'putJson("/api/expertenmodus"' in seite
