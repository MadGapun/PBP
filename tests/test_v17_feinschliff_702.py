"""Regression #702 (beta.102): Feinschliff-Welle aus der Dashboard-Tour.

- pick_line ueberspringt Linien mit ungefuellten Text-Platzhaltern
  (vorher: "{firma} will dich sehen." -> " will dich sehen.")
- hints.json ist nicht mehr auf v1.6.2 eingefroren
- Wiki-Snippets: keine stale "130 Werkzeuge" / kein "durch ist" mehr
"""
import json
import os
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).parent.parent


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17_702_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


def test_702_pick_line_skippt_leere_platzhalter(setup_env):
    db = setup_env
    from bewerbungs_assistent.services.elwosa import pick_line
    pool = ["{firma} will dich sehen.", "Neutrale Linie ohne Platzhalter."]
    # Ohne firma-Kontext darf NIE die kaputte Variante kommen
    for _ in range(10):
        chosen = pick_line(db, list(pool), ctx={})
        assert chosen is not None
        assert "will dich sehen" not in chosen, chosen
    # Nur-Platzhalter-Pool ohne Kontext -> None statt kaputtem Text
    assert pick_line(db, ["{firma} will dich sehen."], ctx={}) is None


def test_702_pick_line_fuellt_mit_kontext(setup_env):
    db = setup_env
    from bewerbungs_assistent.services.elwosa import pick_line
    chosen = pick_line(db, ["{firma} will dich sehen."], ctx={"firma": "Beispiel AG"})
    assert chosen == "Beispiel AG will dich sehen."


def test_702_hints_json_nicht_mehr_v162():
    data = json.loads((REPO / "hints.json").read_text(encoding="utf-8"))
    titles = " ".join(h.get("title", "") for h in data["hints"])
    assert "v1.6.2" not in titles, "hints.json haengt noch auf v1.6.2"
    assert data["hints"], "hints.json darf nicht leer sein"


def test_702_wiki_snippets_aktuell():
    snippets = (REPO / "docs" / "wiki-snippets")
    blob = " ".join(p.read_text(encoding="utf-8") for p in snippets.glob("*.md"))
    assert "130 Werkzeuge" not in blob
    assert "noch nicht durch ist" not in blob
