"""beta.96 (#681): Junk-Skills aus der Extraktion ausfiltern + bereinigen.

Die Skill-Extraktion erzeugt manchmal Satzfragmente ("in Systemen wie Creo",
"Programmierung in CATIA.", "SAP oder vergleichbar)") statt echter Skills.
Die verschaerfte Garbage-Heuristik haelt sie beim Anlegen raus und findet
Altbestand fuer die Bereinigung.
"""
from __future__ import annotations

import logging
import uuid


JUNK = [
    "in Systemen wie Creo",
    "Sehr gute Englischkenntnisse",
    "in einem dynamischen Umfeld.",
    "Programmierung in CATIA.",
    "SAP oder vergleichbar)",
    "CAD-Integration)",
    "in ERP-Systemen (Infor",
]
LEGIT = [
    "Python", "CATIA V5", "SAP MM", "Projektmanagement", "3DEXPERIENCE",
    ".NET", "C#", "Node.js", "Microsoft Office", "Englisch",
]


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn
        return deco


def _insert_raw_skill(tmp_db, name, pid):
    """Fuegt einen Skill direkt ein (umgeht den add_skill-Filter -> Altbestand)."""
    conn = tmp_db.connect()
    conn.execute(
        "INSERT INTO skills (id, name, category, level, profile_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (uuid.uuid4().hex, name, "fachlich", 3, pid),
    )
    conn.commit()


def test_garbage_heuristik_faengt_junk(tmp_db):
    for j in JUNK:
        assert tmp_db._is_garbage_skill(j) is True, f"nicht erkannt: {j!r}"


def test_garbage_heuristik_laesst_echte_skills_durch(tmp_db):
    for s in LEGIT:
        assert tmp_db._is_garbage_skill(s) is False, f"faelschlich Junk: {s!r}"


def test_add_skill_lehnt_junk_ab(tmp_db):
    tmp_db.create_profile("Test", "t@e.de")
    assert tmp_db.add_skill({"name": "in Systemen wie Creo"}) == ""
    assert tmp_db.add_skill({"name": "Python"}) != ""


def test_find_junk_skills_faengt_altbestand(tmp_db):
    tmp_db.create_profile("Test", "t@e.de")
    pid = tmp_db.get_active_profile_id()
    _insert_raw_skill(tmp_db, "in Systemen wie Creo", pid)
    _insert_raw_skill(tmp_db, "Programmierung in CATIA.", pid)
    tmp_db.add_skill({"name": "Python"})  # legit

    namen = [j["name"] for j in tmp_db.find_junk_skills()]
    assert "in Systemen wie Creo" in namen
    assert "Programmierung in CATIA." in namen
    assert "Python" not in namen


def test_mcp_skills_bereinigen_vorschau_und_anwenden(tmp_db):
    tmp_db.create_profile("Test", "t@e.de")
    pid = tmp_db.get_active_profile_id()
    _insert_raw_skill(tmp_db, "in einem dynamischen Umfeld.", pid)
    tmp_db.add_skill({"name": "Python"})

    from bewerbungs_assistent.tools.profil import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    bereinigen = mcp.tools["skills_bereinigen"]

    vor = bereinigen()
    assert vor["status"] == "vorschau"
    assert vor["anzahl"] >= 1

    res = bereinigen(anwenden=True)
    assert res["status"] == "bereinigt"
    assert res["geloescht"] >= 1
    assert tmp_db.find_junk_skills() == []
