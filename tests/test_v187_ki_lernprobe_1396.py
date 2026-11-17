"""#1396 - das Messskript `scripts/ki_lernprobe.py` (nie gegen die echte KI in der Suite)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO = Path(__file__).resolve().parents[1]
TEXT = "Aufgaben: Konstruktion von Maschinen und Anlagen. Anforderungen: Erfahrung. " * 2


def _skript():
    spec = importlib.util.spec_from_file_location("ki_lernprobe", REPO / "scripts" / "ki_lernprobe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def quelle(tmp_path):
    """Eine 'echte' Datenbank in einem eigenen Ordner - die Probe darf sie nie beschreiben."""
    ordner = tmp_path / "echt"
    ordner.mkdir()
    os.environ["BA_DATA_DIR"] = str(ordner)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=ordner / "pbp.db")
    d.initialize()
    d.save_profile({"name": "Test Probe"})
    for i in range(8):
        d.save_jobs([{"hash": f"q{i}", "title": f"Konstrukteur Variante {i}", "company": "Musterwerk Nord GmbH",
                      "url": f"https://example.com/probe/{i}", "source": "stepstone",
                      "description": TEXT, "score": 10}])
        voll = d.resolve_job_hash(f"q{i}")
        if i % 2:
            d.dismiss_job(voll, "falsche_branche", herkunft="ich")
        else:
            d.set_job_analysis(voll, "EMPFOHLEN", "Passt gut.")
    d.connect().execute("PRAGMA wal_checkpoint(TRUNCATE)")
    d.close()
    os.environ.pop("BA_DATA_DIR", None)
    yield ordner / "pbp.db"
    os.environ.pop("BA_DATA_DIR", None)


def _pruefsumme(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def test_trockenlauf_ruft_keine_ki_und_laesst_die_quelle_unberuehrt(quelle, tmp_path, monkeypatch, capsys):
    from bewerbungs_assistent.services import llm_service

    def verboten(*a, **k):
        raise AssertionError("Der Trockenlauf darf die KI nicht ansprechen.")
    monkeypatch.setattr(llm_service, "LLMService", verboten)
    vorher = _pruefsumme(quelle)
    arbeit = tmp_path / "arbeit"
    bericht = tmp_path / "bericht.json"
    assert _skript().main(["--quelle", str(quelle), "--arbeitsordner", str(arbeit),
                           "--bericht", str(bericht), "--anzahl", "6"]) == 0
    assert _pruefsumme(quelle) == vorher, "Die echte Datenbank wurde veraendert."
    assert (arbeit / "pbp.db").is_file() and os.environ["BA_DATA_DIR"] == str(arbeit)
    rep = json.loads(bericht.read_text(encoding="utf-8"))
    assert rep["modus"] == "trockenlauf" and "messung" not in rep
    assert rep["trockenlauf"]["marker"].get("mensch") == 4
    assert rep["trockenlauf"]["marker"].get("claude") == 4


def test_messung_vergleicht_alten_und_neuen_prompt_und_den_lernlauf(quelle, tmp_path):
    from bewerbungs_assistent.database import Database
    arbeit = tmp_path / "arbeit2"
    arbeit.mkdir()
    os.environ["BA_DATA_DIR"] = str(arbeit)
    s = _skript()
    s.kopieren(quelle, arbeit / "pbp.db")
    db = Database(db_path=arbeit / "pbp.db")
    db.initialize()
    assert str(arbeit) in str(db.db_path)

    class KI:
        def __init__(self):
            self.n = 0

        def run(self, kind, payload):
            self.n += 1
            # Prompt A (alt) hat keine lern_beispiele und rät PASST; neu: kennt die Variante
            neu = "lern_beispiele" in payload
            nummer = int(payload["job_title"].split()[-1])
            urteil = ("PASST_NICHT" if nummer % 2 else "PASST") if neu else "PASST"
            return SimpleNamespace(success=True, payload={"decision": urteil})

    erg = s.lauf(db, KI(), anzahl=8)
    db.close()
    assert erg["stellen"] == 8
    assert erg["A"]["quote_prozent"] == 50.0       # der alte Prompt rät immer PASST
    assert erg["B"]["quote_prozent"] == 100.0 and erg["C"]["quote_prozent"] == 100.0
    assert erg["B_nach_C"]["schlechter"] == 0 and erg["anders_bewertet"] == 0


def test_ohne_schalter_gibt_es_keinen_echten_aufruf_im_quelltext():
    """Die KI wird nur auf den Zweig `--mit-ki` hin angesprochen (Waechter gegen eine stille Aenderung)."""
    text = (REPO / "scripts" / "ki_lernprobe.py").read_text(encoding="utf-8")
    kopf, rest = text.split("if not a.mit_ki:", 1)
    assert "LLMService(" not in kopf
    trocken, mit = rest.split("else:", 1)
    assert "LLMService(" not in trocken and "LLMService(" in mit
