"""#1148 Punkt 9 (Rest): zwei Schreibweisen desselben Parameters nimmt jedes Werkzeug an.

`firma`/`company`, `titel`/`title`, `dokument_id`/`document_id`, `job_hash`/`stellen_hash` und `bewerbung_id`/`application_id` stehen
in den Signaturen nebeneinander. Die Middleware übersetzt einen unbekannten Namen in den bekannten derselben Gruppe
(`services/parameter_aliase`). Hier: die Regel allein, ein Wächter über ALLE Schemas (kein Werkzeug trägt zwei Namen einer Gruppe, jede
Zeile der Tabelle wird gebraucht) und der ganze Weg durch die Middleware.

Alle Firmen und Namen sind Platzhalter.
"""
import asyncio
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services.parameter_aliase import GRUPPEN, uebersetzen  # noqa: E402


# ══ Die Regel allein ═════════════════════════════════════════════════════════════════

def test_ein_unbekannter_name_wird_in_den_bekannten_derselben_gruppe_uebersetzt():
    neu = uebersetzen({"company": "Beispiel GmbH", "titel": "Planer"}, {"firma", "titel"})
    assert neu == {"firma": "Beispiel GmbH", "titel": "Planer"}


def test_beide_richtungen():
    assert uebersetzen({"firma": "A"}, {"company"}) == {"company": "A"}
    assert uebersetzen({"company": "A"}, {"firma"}) == {"firma": "A"}


def test_ein_bekannter_name_bleibt_wie_er_ist():
    assert uebersetzen({"company": "A"}, {"company", "title"}) is None
    assert uebersetzen({"firma": "A", "titel": "B"}, {"firma", "titel"}) is None


def test_kennt_das_werkzeug_beide_namen_bleibt_jeder_wie_er_ist():
    """Heute traegt kein Werkzeug zwei Namen einer Gruppe (Waechter unten); kaeme eines dazu, gaelte jeder Name fuer sich."""
    assert uebersetzen({"company": "A"}, {"company", "firma"}) is None
    assert uebersetzen({"firma": "A"}, {"company", "firma"}) is None


def test_das_uebergebene_dict_bleibt_unveraendert():
    ein = {"document_id": "abc"}
    aus = uebersetzen(ein, {"dokument_id"})
    assert ein == {"document_id": "abc"} and aus == {"dokument_id": "abc"}


def test_ist_der_zielname_schon_uebergeben_wird_nichts_ueberschrieben():
    assert uebersetzen({"company": "A", "firma": "B"}, {"firma"}) is None


def test_ein_name_ausserhalb_der_tabelle_bleibt_unberuehrt():
    assert uebersetzen({"unbekannt": 1, "hash_a": "x"}, {"firma", "hash_b"}) is None
    assert uebersetzen({"master_hash": "x"}, {"job_hash"}) is None, "master_hash ist etwas anderes als job_hash"


@pytest.mark.parametrize("arguments,bekannte", [(None, {"firma"}), ({}, {"firma"}), ("firma", {"firma"}), ({"company": 1}, set())])
def test_unbrauchbare_eingaben_aendern_nichts(arguments, bekannte):
    assert uebersetzen(arguments, bekannte) is None


def test_werte_werden_nicht_angefasst():
    neu = uebersetzen({"company": ["a", "b"], "title": None}, {"firma", "titel"})
    assert neu == {"firma": ["a", "b"], "titel": None}


# ══ Wächter über alle Werkzeuge ════════════════════════════════════════════════════════

@pytest.fixture(scope="module")
def schemas(tmp_path_factory):
    import test_mcp_registry as reg
    tmp = tmp_path_factory.mktemp("alias1148")
    mcp, db = reg._build_test_server(tmp)

    async def _alle():
        return await mcp.list_tools() if hasattr(mcp, "list_tools") else list((await mcp.get_tools()).values())

    ergebnis = {t.name: set((getattr(t, "parameters", None) or {}).get("properties", {})) for t in asyncio.run(_alle())}
    db.close()
    os.environ.pop("BA_DATA_DIR", None)
    return ergebnis


def test_kein_werkzeug_traegt_zwei_namen_einer_gruppe(schemas):
    """Sonst waere eine Uebersetzung mehrdeutig: welcher der beiden war gemeint?"""
    doppelt = [(name, g) for name, props in schemas.items() for g in GRUPPEN if len(set(g) & props) > 1]
    assert not doppelt, doppelt


def test_jeder_name_der_tabelle_kommt_in_einem_werkzeug_vor(schemas):
    """Eine Zeile, die kein Werkzeug braucht, ist tot und taeuscht eine Zusage vor."""
    alle = set().union(*schemas.values())
    for gruppe in GRUPPEN:
        for name in gruppe:
            assert name in alle, f"{name} steht in der Tabelle, aber in keinem Werkzeug"


def test_jedes_werkzeug_mit_einem_gruppenname_versteht_den_anderen(schemas):
    for name, props in schemas.items():
        for gruppe in GRUPPEN:
            vorhanden = set(gruppe) & props
            if len(vorhanden) != 1:
                continue
            (bekannt,) = vorhanden
            for anderer in set(gruppe) - {bekannt}:
                assert uebersetzen({anderer: "x"}, props) == {bekannt: "x"}, (name, anderer)


# ══ Der ganze Weg durch die Middleware ═════════════════════════════════════════════════

@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v18_alias_1148_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test", "city": "Hamburg"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _aufruf(mcp, name, args):
    from fastmcp import Client

    async def _run():
        async with Client(mcp) as c:
            return await c.call_tool(name, args, raise_on_error=False)
    return asyncio.run(_run())


def _text(res) -> str:
    return " ".join(getattr(t, "text", str(t)) for t in res.content)


def test_ein_werkzeug_mit_firma_und_titel_nimmt_company_und_title(umgebung):
    db, mcp = umgebung
    res = _aufruf(mcp, "stelle_manuell_anlegen",
                  {"company": "Aliasbetrieb GmbH", "title": "Konstrukteurin", "beschreibung": "Aufgaben und Anforderungen. " * 8,
                   "url": "https://example.com/alias-1148"})
    assert not getattr(res, "is_error", False), _text(res)
    zeile = db.connect().execute("SELECT title, company FROM jobs WHERE company=?", ("Aliasbetrieb GmbH",)).fetchone()
    assert zeile is not None and zeile["title"] == "Konstrukteurin"


def test_ein_werkzeug_mit_company_und_title_nimmt_firma_und_titel(umgebung):
    db, mcp = umgebung
    res = _aufruf(mcp, "bewerbung_erstellen", {"firma": "Zweitbetrieb GmbH", "titel": "Planer", "status": "beworben"})
    assert not getattr(res, "is_error", False), _text(res)
    zeile = db.connect().execute("SELECT title, company FROM applications WHERE company=?", ("Zweitbetrieb GmbH",)).fetchone()
    assert zeile is not None and zeile["title"] == "Planer"


def test_document_id_wird_zusammen_mit_dem_typpraefix_verstanden(umgebung):
    db, mcp = umgebung
    did = db.add_document({"filename": "alias.txt", "doc_type": "sonstiges", "extracted_text": "Ein Text im Dokument."})
    res = _aufruf(mcp, "dokument_lesen", {"document_id": f"DOC-{did}"})
    assert not getattr(res, "is_error", False), _text(res)
    assert "Ein Text im Dokument." in _text(res)


def test_ein_unbekannter_name_ausserhalb_der_tabelle_wird_weiter_abgewiesen(umgebung):
    db, mcp = umgebung
    res = _aufruf(mcp, "bewerbung_erstellen", {"unfug": "x", "firma": "Dritt GmbH", "titel": "T"})
    assert getattr(res, "is_error", False), "ein Name, den niemand kennt, bleibt ein Fehler"


def test_die_middleware_ruft_die_uebersetzung_auf():
    quelle = (ROOT / "src" / "bewerbungs_assistent" / "server.py").read_text(encoding="utf-8-sig")
    assert "parameter_aliase" in quelle and "_alias_uebersetzen" in quelle
    assert quelle.index("_alias_uebersetzen(") < quelle.index("normalisiere_argumente("), "erst die Namen, dann die Kennungen"
