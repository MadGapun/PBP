"""Tests fuer #785: Modell-Katalog mit Stand, Nachfolgern und Denkmodus.

Der Katalog stand seit Ende 2024 unveraendert im Endpunkt. Hier geprueft:
die aktuelle Generation mit nachgemessenen Groessen, der Stand, der
Nachfolger-Hinweis ohne Automatik, die Warnung im Release-Check — und
dass der Denkmodus der Qwen3-Reihe PBPs Auswertungen nicht bricht.
"""
import importlib
import json
import os
import subprocess
import sys
import urllib.request
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import modell_katalog as mk  # noqa: E402


# ============================================================ Katalog


def test_ak1_der_katalog_steht_auf_der_aktuellen_generation():
    ids = [m["id"] for m in mk.KATALOG]
    assert ids == ["qwen3:4b", "qwen3:8b", "qwen3:14b"]
    assert sum(1 for m in mk.KATALOG if m.get("recommended")) == 1


def test_ak1_der_stand_ist_lesbar():
    jahr, monat = mk.STAND.split("-")
    assert mk.stand_text() == f"Stand {monat}/{jahr}"


@pytest.mark.parametrize("modell, erwartet", [
    ("qwen2.5:7b", "qwen3:8b"),
    ("qwen2.5:latest", "qwen3:8b"),
    ("qwen2.5", "qwen3:8b"),
    ("qwen2.5:7b-instruct-q4_K_M", "qwen3:8b"),
    ("llama3.2:3b", "qwen3:4b"),
    ("QWEN2.5:14B", "qwen3:14b"),
])
def test_ak2_vorgaenger_bekommen_ihren_nachfolger(modell, erwartet):
    befund = mk.nachfolger_fuer(modell)
    assert befund["nachfolger"] == erwartet
    assert "Nichts wird automatisch" in befund["hinweis"]


@pytest.mark.parametrize("modell", ["qwen3:8b", "mistral:7b", "", None, "qwen2.5:32b"])
def test_ak2_ohne_bekannten_vorgaenger_kein_hinweis(modell):
    assert mk.nachfolger_fuer(modell) is None


def _plus_monate(jahr, monat, n):
    gesamt = monat - 1 + n
    return jahr + gesamt // 12, gesamt % 12 + 1


def test_ak3_veraltet_erst_nach_sechs_monaten():
    jahr, monat = (int(t) for t in mk.STAND.split("-"))
    assert not mk.veraltet(date(jahr, monat, 28))
    assert not mk.veraltet(date(*_plus_monate(jahr, monat, 6), 1))
    assert mk.veraltet(date(*_plus_monate(jahr, monat, 7), 1))


# ======================================================== Denkmodus


@pytest.mark.parametrize("roh, erwartet", [
    ("<think>ich ueberlege</think>\n{\"a\": 1}", "{\"a\": 1}"),
    ("  <THINK>x</THINK>Antwort", "Antwort"),
    ("{\"a\": 1}", "{\"a\": 1}"),
    ("Antwort mit <think> mittendrin", "Antwort mit <think> mittendrin"),
    # Ein geschlossener Block mitten im Text ist Inhalt — ohne die
    # Anfangspruefung ginge der vordere Teil der Antwort verloren.
    ("{\"a\": \"<think>x</think>\"} Rest", "{\"a\": \"<think>x</think>\"} Rest"),
    ("<think>nie geschlossen", "<think>nie geschlossen"),
    ("", ""),
])
def test_der_denkblock_wird_nur_am_anfang_entfernt(roh, erwartet):
    assert mk.ohne_denkblock(roh) == erwartet


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    d = database.Database(db_path=tmp_path / "katalog.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.switch_profile(d.create_profile("Katalog"))
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


class _Antwort:
    def __init__(self, daten):
        self._daten = daten

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return json.dumps(self._daten).encode("utf-8")


def _abfangen(antwort=None):
    gesendet = []

    def fake(req, timeout=None):
        gesendet.append(json.loads(req.data))
        return _Antwort(antwort if antwort is not None else {"response": "ok"})

    return gesendet, fake


def _service(db):
    from bewerbungs_assistent.services.llm_service import LLMService

    svc = LLMService(db)
    svc._status.ollama_endpoint = "http://fake:11434"
    return svc


def test_der_aufruf_schaltet_den_denkmodus_ab(db):
    gesendet, fake = _abfangen()
    with patch.object(urllib.request, "urlopen", fake):
        _service(db)._ollama_generate("qwen3:8b", "kurzer prompt")
    assert gesendet[0]["think"] is False


def test_der_warmup_schaltet_den_denkmodus_ebenfalls_ab(db):
    """Sonst waere der Warmup ein anderer Aufruf als der echte (#638, #787)."""
    svc = _service(db)
    svc._status.ollama_available = True
    svc._status.selected_model = "qwen3:8b"
    gesendet, fake = _abfangen()
    with patch.object(svc, "get_status", return_value=svc._status), \
            patch.object(urllib.request, "urlopen", fake):
        svc.warmup()
    assert gesendet[0]["think"] is False


def test_ein_trotzdem_gelieferter_denkblock_erreicht_den_parser_nicht(db):
    """Aeltere Ollama-Versionen kennen `think` nicht und liefern den Block."""
    gesendet, fake = _abfangen({"response": "<think>hmm</think>\n{\"urteil\": \"passt\"}"})
    with patch.object(urllib.request, "urlopen", fake):
        antwort = _service(db)._ollama_generate("qwen3:8b", "kurzer prompt")
    assert antwort == "{\"urteil\": \"passt\"}"


# ======================================================= Endpunkt


def test_der_endpunkt_liefert_katalog_und_stand():
    from fastapi.testclient import TestClient

    from bewerbungs_assistent.dashboard import app

    j = TestClient(app).get("/api/llm/recommended-models").json()
    assert [m["id"] for m in j["models"]] == [m["id"] for m in mk.KATALOG]
    assert j["stand"] == mk.STAND
    assert j["stand_text"] == mk.stand_text()


def test_der_status_nennt_den_nachfolger_des_aktiven_modells(db, monkeypatch):
    from fastapi.testclient import TestClient

    import bewerbungs_assistent.dashboard as dash
    from bewerbungs_assistent.services import llm_service

    svc = _service(db)
    svc._status.ollama_available = True
    svc._status.available_models = ["qwen2.5:7b"]
    svc._status.selected_model = "qwen2.5:7b"
    svc._status.user_state = "active"
    monkeypatch.setattr(svc, "get_status", lambda force_refresh=False: svc._status)
    monkeypatch.setattr(llm_service, "get_llm_service", lambda _db: svc)
    vorher = dash._db
    dash._db = db
    try:
        j = TestClient(dash.app).get("/api/llm/status").json()
    finally:
        dash._db = vorher
    assert j["nachfolger"]["nachfolger"] == "qwen3:8b"
    assert j["selected_model"] == "qwen2.5:7b", "nichts wird umgestellt"


def test_der_tab_zeigt_den_nachfolger_mit_ladeknopf_und_ohne_automatik():
    """AK 2 in der Oberflaeche. Ein Browser-Test ginge hier nur mit einer
    laufenden Ollama-Instanz — ohne sie zeigt der Tab die Variante
    "nicht erreichbar", und die Modell-Liste mit dem Hinweis rendert gar
    nicht. Deshalb pruefen wir den Quelltext: der Hinweis haengt am
    Status-Feld, der Knopf laedt genau den Nachfolger, und nirgends wird
    beim Anzeigen etwas geladen oder umgestellt."""
    jsx = (_repo() / "frontend/src/pages/SettingsPage.jsx").read_text(encoding="utf-8")
    liste = jsx[jsx.index("function ModelDetailList("):]
    liste = liste[:liste.index("\nfunction ", 10)]
    assert "status.nachfolger" in liste
    assert 'data-testid="modell-nachfolger"' in liste
    assert "onClick={() => onPull(nachfolger.nachfolger)}" in liste
    assert "useEffect" not in liste, "beim Anzeigen darf nichts passieren"
    assert "{katalogStand ?" in jsx, "der Stand steht in der Oberflaeche"


# ================================================== Release-Check


def test_ak3_der_release_check_warnt_bei_altem_katalog(monkeypatch):
    sys.path.insert(0, str(_repo()))
    import release_check

    monkeypatch.setattr(mk, "veraltet", lambda heute=None: True)
    fehler_vorher = len(release_check.ERRORS)
    warnungen_vorher = len(release_check.WARNINGS)
    release_check.check_modell_katalog()
    assert len(release_check.WARNINGS) == warnungen_vorher + 1
    assert len(release_check.ERRORS) == fehler_vorher, \
        "ein alter Katalog ist eine Warnung, kein Release-Stopp"
