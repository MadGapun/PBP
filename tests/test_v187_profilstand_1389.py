"""#1389: jeder Schreibweg ins Profil macht eine gespeicherte Bewertung veraltet."""
import ast
import asyncio
import importlib
import os
import shutil
import tempfile
from pathlib import Path

import pytest

DATENBANK = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent" / "database.py"

#: Schreibmethoden fuer Profil-Inhalt, die den Stand stempeln MUESSEN.
SCHREIBER = (
    "add_position", "update_position", "delete_position",
    "add_project", "update_project", "delete_project",
    "add_education", "update_education", "delete_education",
    "add_skill_mit_befund", "update_skill", "delete_skill",
    "add_skill_period", "delete_skill_period",
)
#: Methoden, die nur an eine gestempelte weiterleiten.
LEITET_WEITER = {"add_skill": "add_skill_mit_befund"}


def test_registrierung_keine_schreibmethode_fehlt():
    """Jede add_/update_/delete_-Methode fuer Kompetenz, Zeitraum, Station,
    Projekt und Ausbildung ist gestempelt - eine neue faellt hier auf."""
    baum = ast.parse(DATENBANK.read_text(encoding="utf-8-sig"))
    klasse = next(n for n in baum.body if isinstance(n, ast.ClassDef) and n.name == "Database")
    gefunden = {}
    for f in klasse.body:
        if not isinstance(f, ast.FunctionDef):
            continue
        name = f.name
        if any(name.startswith(p) for p in ("add_", "update_", "delete_")) and any(
                k in name for k in ("skill", "position", "project", "education")):
            gefunden[name] = any(
                isinstance(d, ast.Name) and d.id == "_stempelt_profil" for d in f.decorator_list)
    # Fremde Treffer (Namen mit 'position'/'skill', die nicht ins Profil schreiben)
    fremd = {n for n in gefunden if n not in SCHREIBER and n not in LEITET_WEITER}
    ungestempelt = {n for n in SCHREIBER if not gefunden.get(n)}
    assert not ungestempelt, f"ohne _stempelt_profil: {ungestempelt}"
    assert not fremd, (f"neue Schreibmethode? In SCHREIBER eintragen und stempeln, oder in diesem Test "
                       f"begruenden: {sorted(fremd)}")


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1389_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test Person"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _stelle_mit_bewertung(db, mcp):
    db.save_jobs([{"hash": "v1389", "title": "Planer", "company": "Musterbetrieb GmbH",
                   "url": "https://example.com/v1389", "source": "manuell",
                   "description": "Planung Einkauf SAP " * 30, "score": 3}])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE '%v1389'").fetchone()["hash"]
    kurz = voll.split(":", 1)[-1]
    erg = _call(mcp, "stelle_urteil_speichern", {
        "job_hash": kurz, "urteil": "BEDINGT", "begruendung": "Lücke X"})
    assert "fehler" not in erg, erg
    return kurz


def _veraltet(mcp, kurz):
    erg = _call(mcp, "fit_analyse", {"job_hash": kurz})
    return bool((erg.get("gespeicherte_analyse") or {}).get("veraltet")
                or (erg.get("empfehlung") or {}).get("veraltet"))


def test_ausgangslage_bewertung_ist_aktuell(umgebung):
    db, mcp = umgebung
    kurz = _stelle_mit_bewertung(db, mcp)
    assert not _veraltet(mcp, kurz)


def test_zeitraum_hinzufuegen_und_loeschen_macht_veraltet(umgebung):
    db, mcp = umgebung
    sid = db.add_skill({"name": "SAP PP", "category": "fachlich", "level": 3})
    kurz = _stelle_mit_bewertung(db, mcp)
    assert not _veraltet(mcp, kurz)
    erg = _call(mcp, "skill_zeitraum_hinzufuegen", {"skill_id": sid, "start_jahr": 2015, "end_jahr": 2018})
    assert "fehler" not in erg, erg
    assert _veraltet(mcp, kurz), "skill_zeitraum_hinzufuegen: Bewertung gilt noch als aktuell"


def test_jede_registrierte_schreibmethode_stempelt(umgebung):
    """Pro Methode: Bewertung speichern, Methode ausfuehren, Stand hat sich geaendert."""
    db, mcp = umgebung
    pos = db.add_position({"company": "Musterbetrieb GmbH", "title": "Planer", "start_date": "2015-01"})
    sk = db.add_skill({"name": "Excel", "category": "tool", "level": 3})
    pr = db.add_project(pos, {"name": "Projekt A"})
    ed = db.add_education({"institution": "Musterschule", "degree": "Meister"})
    per = db.add_skill_period(sk, 2010, 2012)
    aufrufe = {
        "add_position": lambda: db.add_position({"company": "Neu GmbH", "title": "X"}),
        "update_position": lambda: db.update_position(pos, {"title": "Planer Neu"}),
        "add_project": lambda: db.add_project(pos, {"name": "Projekt B"}),
        "update_project": lambda: db.update_project(pr, {"name": "Projekt A2"}),
        "delete_project": lambda: db.delete_project(pr),
        "add_education": lambda: db.add_education({"institution": "Zwei", "degree": "Dr"}),
        "update_education": lambda: db.update_education(ed, {"degree": "Dipl"}),
        "delete_education": lambda: db.delete_education(ed),
        "add_skill_mit_befund": lambda: db.add_skill_mit_befund({"name": "Lean", "category": "methodisch", "level": 2}),
        "update_skill": lambda: db.update_skill(sk, {"level": 4}),
        "add_skill_period": lambda: db.add_skill_period(sk, 2019, 2020),
        "delete_skill_period": lambda: db.delete_skill_period(per),
        "delete_skill": lambda: db.delete_skill(sk),
        "delete_position": lambda: db.delete_position(pos),
    }
    assert set(aufrufe) == set(SCHREIBER)
    from bewerbungs_assistent.services import passung
    for name, aufruf in aufrufe.items():
        vorher = passung.profil_stand(db.get_profile())
        assert aufruf(), f"{name}: Aufruf hat nichts getan"
        nachher = passung.profil_stand(db.get_profile())
        assert nachher != vorher, f"{name}: Profilstand unveraendert"


def test_abgewiesener_aufruf_stempelt_nicht(umgebung):
    db, mcp = umgebung
    vorher = (db.get_profile() or {}).get("stand_nr") or 0
    assert not db.update_position("gibt-es-nicht", {"title": "x"})
    assert not db.delete_skill("gibt-es-nicht")
    assert ((db.get_profile() or {}).get("stand_nr") or 0) == vorher
