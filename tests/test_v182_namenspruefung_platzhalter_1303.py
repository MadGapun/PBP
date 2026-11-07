"""#1303: ein Kontakt ohne echten Namen macht keine Markdown-Tabelle zum Personenfund.

Im Bestand stand ein Kontakt namens "---" (Platzhalter aus einem Import). `issue_text_pruefen`
fand diesen "Namen" in jeder Trennzeile `|---|---|` und sagte "NICHT veroeffentlichen".
Alle Namen hier sind erfunden. Gegenrichtung: ein echter Name in einer Tabelle wird weiter gefunden.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest

from bewerbungs_assistent.services import pii_bestand

TABELLE = "| Ortsangabe | berechnet |\n|---|---|\n| Musterstadt | 12 km |\n"


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v182_1303_")
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


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


@pytest.mark.parametrize("platzhalter", ["---", "-----", "...", "123", "- - -", "#1"])
def test_tabelle_ist_sauber_trotz_platzhalter_kontakt(tmp_db, platzhalter):
    tmp_db.add_contact({"full_name": platzhalter})
    bericht = pii_bestand.pruefe_text(tmp_db, TABELLE + "Kontakt #1, Version 123 ...\n")
    assert bericht["sauber"] and bericht["anzahl"] == 0, bericht


def test_echter_name_in_einer_tabelle_wird_weiter_gefunden(tmp_db):
    tmp_db.add_contact({"full_name": "---"})
    tmp_db.add_contact({"full_name": "Fridolin Quastenberg"})
    bericht = pii_bestand.pruefe_text(tmp_db, TABELLE + "| Fridolin Quastenberg | 3 km |\n")
    assert not bericht["sauber"]
    assert [t["name"] for t in bericht["treffer"]] == ["Fridolin Quastenberg"]


def test_name_mit_ziffern_bleibt_ein_name(tmp_db):
    """Gegenrichtung: nur Werte OHNE Buchstaben fallen heraus."""
    tmp_db.add_application({"company": "Werk 4 Anlagen", "title": "CAD", "position": "CAD",
                            "status": "beworben"})
    assert not pii_bestand.pruefe_text(tmp_db, "Absage von Werk 4 Anlagen.")["sauber"]


@pytest.mark.parametrize("wert,erwartet", [
    ("---", True), ("123", True), ("", True), ("Name", True), ("Ansprechpartner", True),
    ("unbekannt", True), ("Fridolin Quastenberg", False), ("Ida", False), ("Ö", False)])
def test_platzhalter_erkennung(wert, erwartet):
    assert pii_bestand.ist_platzhalter_name(wert) is erwartet


def test_platzhalter_kontakte_sind_auffindbar(umgebung):
    db, mcp = umgebung
    db.add_contact({"full_name": "---"})
    db.add_contact({"full_name": "Name"})
    db.add_contact({"full_name": "Fridolin Quastenberg"})
    alle = _call(mcp, "kontakte_auflisten", {})
    assert alle["anzahl"] == 3
    assert "2 Kontakt(e) ohne echten Namen" in alle["hinweis_platzhalter"]
    nur = _call(mcp, "kontakte_auflisten", {"nur_platzhalter": True})
    assert sorted(k["full_name"] for k in nur["kontakte"]) == ["---", "Name"]
    assert "kontakt_bearbeiten" in nur["hinweis"]


def test_ohne_platzhalter_kein_hinweis(umgebung):
    db, mcp = umgebung
    db.add_contact({"full_name": "Fridolin Quastenberg"})
    assert "hinweis_platzhalter" not in _call(mcp, "kontakte_auflisten", {})
    assert _call(mcp, "kontakte_auflisten", {"nur_platzhalter": True})["anzahl"] == 0
