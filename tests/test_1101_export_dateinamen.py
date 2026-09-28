"""#1101: Exporte mit Sonderzeichen im Namen und ohne stilles Ueberschreiben."""
from __future__ import annotations

import ast
import asyncio
import logging
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / "src" / "bewerbungs_assistent"


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Erika Beispiel"})
    ausgabe = tmp_path / "ausgabe"
    ausgabe.mkdir()
    from bewerbungs_assistent.services import ablage
    assert ablage.ordner_setzen(d, "ausgabe", str(ausgabe)).get("status") != "fehler"
    d.ausgabe = ausgabe
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.mark.parametrize("zeichen", list('/:?*"<>|\\'))
def test_verbotene_zeichen(zeichen, tmp_path):
    from bewerbungs_assistent.services.ablage import dateiname_teil, freier_pfad
    teil = dateiname_teil(f"Muster{zeichen}Beispiel GmbH", "firma")
    assert zeichen not in teil
    assert teil.startswith("muster") and teil.endswith("beispiel_gmbh")
    ziel = freier_pfad(tmp_path, f"anschreiben_{teil}.txt")
    ziel.write_text("x", encoding="utf-8")
    assert ziel.parent == tmp_path and ziel.is_file()
    assert [p.name for p in tmp_path.iterdir()] == [ziel.name]


def test_umlaute_bleiben_und_reservierte_namen():
    from bewerbungs_assistent.services.ablage import dateiname_teil
    assert dateiname_teil("Müller & Söhne") == "müller_&_söhne"
    assert dateiname_teil("CON") == "_con"
    assert dateiname_teil("   ") == "export"
    assert len(dateiname_teil("x" * 300)) <= 60


def test_nie_ueberschreiben(tmp_path):
    from bewerbungs_assistent.services.ablage import freier_pfad
    erster = freier_pfad(tmp_path, "anschreiben_firma.docx")
    erster.write_text("erste Fassung", encoding="utf-8")
    zweiter = freier_pfad(tmp_path, "anschreiben_firma.docx")
    zweiter.write_text("zweite", encoding="utf-8")
    dritter = freier_pfad(tmp_path, "anschreiben_firma.docx")
    assert len({erster, zweiter, dritter}) == 3
    assert erster.read_text(encoding="utf-8") == "erste Fassung"


def _werkzeug(db, name, args):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP #1101")
    register_all(mcp, db, logging.getLogger("test.1101"))

    async def lauf():
        t = await mcp.get_tool(name)
        return (await t.run(args)).structured_content
    return asyncio.run(lauf())


def test_zwei_anschreiben_fuer_dieselbe_firma(db):
    args = {"text": "Sehr geehrte Damen und Herren,\n\nerste Fassung.\n\nMit freundlichen Grüßen",
            "stelle": "Sachbearbeitung", "firma": "Muster/Beispiel: GmbH"}
    erg1 = _werkzeug(db, "anschreiben_exportieren", args)
    args2 = dict(args, text=args["text"].replace("erste", "zweite"))
    erg2 = _werkzeug(db, "anschreiben_exportieren", args2)
    dateien = sorted(p for p in db.ausgabe.rglob("*") if p.is_file())
    assert len(dateien) == 2, (erg1, erg2, dateien)
    assert all(p.parent == db.ausgabe for p in dateien), "Unterordner aus dem Firmennamen"
    assert all(":" not in p.name and "/" not in p.name for p in dateien)


def test_kein_ungefilterter_name_mehr():
    funde = []
    for p in [SRC / "tools" / "export_tools.py", SRC / "dashboard.py", SRC / "tools" / "dokumente.py"]:
        text = p.read_text(encoding="utf-8-sig")
        if '.replace(" ", "_").lower()' in text:
            funde.append(p.name)
    assert not funde, funde


def test_jeder_exportpfad_ueber_freier_pfad():
    """Jede Zuweisung `path = export_dir / f"..."` ist verboten — sie
    ueberschreibt still. Ausnahme: der Kalender-Feed, der bewusst ersetzt
    wird (ein Abo liest immer dieselbe Datei)."""
    funde = []
    for p in [SRC / "tools" / "export_tools.py", SRC / "dashboard.py"]:
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8-sig"))):
            if (isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)
                    and isinstance(n.left, ast.Name) and n.left.id == "export_dir"):
                rechts = n.right
                if isinstance(rechts, ast.Constant) and rechts.value == "pbp-termine.ics":
                    continue
                funde.append(f"{p.name}:{n.lineno}")
    assert not funde, funde
