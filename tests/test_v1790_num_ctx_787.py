"""Tests fuer #787 (F32, erster Teil): das Kontextfenster der lokalen KI.

`_ollama_generate` setzte kein `num_ctx`. Ollama nahm sein Vorgabefenster
und schnitt einen laengeren Prompt STILL ab — die Antwort sah aus wie
jede andere. Die Tests halten fest:

- das Fenster wird mitgeschickt, und zwar derselbe Wert im Warmup (sonst
  laedt Ollama das Modell beim ersten echten Aufruf neu, #638);
- ein Prompt, der nicht passt, wird BENANNT statt still gekuerzt — vorher
  geschaetzt, nachher gemessen, und beide Pruefungen tragen je einen
  eigenen Test;
- jeder Prompt-Builder passt mit realistischen Hoechstwerten in die
  Vorgabe. Waechst ein Builder, faellt es hier auf und nicht im Feld.

Kein Test ruft ein echtes Ollama: `urllib.request.urlopen` wird ersetzt,
nicht der Parser (v1.7.70 MERKE 4).
"""
from __future__ import annotations

import asyncio
import importlib
import json
import os
import re
import sys
import urllib.request
from pathlib import Path
from unittest.mock import patch

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    d = database.Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.switch_profile(d.create_profile("Testprofil"))
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


# ----------------------------------------------- das Fenster geht mit


def test_der_aufruf_schickt_das_kontextfenster_mit(db):
    from bewerbungs_assistent.services import ollama_kontext

    gesendet, fake = _abfangen()
    with patch.object(urllib.request, "urlopen", fake):
        _service(db)._ollama_generate("modell", "kurzer prompt")
    assert gesendet[0]["options"]["num_ctx"] == ollama_kontext.VORGABE == 8192


def test_ein_gesetzter_wert_wirkt_im_aufruf(db):
    from bewerbungs_assistent.services import ollama_kontext

    assert "fehler" not in ollama_kontext.setzen(db, 16384)
    gesendet, fake = _abfangen()
    with patch.object(urllib.request, "urlopen", fake):
        _service(db)._ollama_generate("modell", "kurzer prompt")
    assert gesendet[0]["options"]["num_ctx"] == 16384


def test_der_warmup_schickt_dasselbe_fenster(db):
    """Ein anderes Fenster im Warmup hiesse: Ollama laedt beim ersten
    echten Aufruf neu, und der Warmup aus #638 haette nichts gewaermt."""
    from bewerbungs_assistent.services import ollama_kontext

    ollama_kontext.setzen(db, 12288)
    svc = _service(db)
    svc._status.ollama_available = True
    svc._status.selected_model = "modell"
    gesendet, fake = _abfangen()
    with patch.object(svc, "get_status", return_value=svc._status), \
            patch.object(urllib.request, "urlopen", fake):
        svc.warmup()
        svc._ollama_generate("modell", "kurzer prompt")
    assert [g["options"]["num_ctx"] for g in gesendet] == [12288, 12288]


def test_jeder_generate_aufruf_im_code_setzt_num_ctx():
    """Guard: kein zweiter Weg an `/api/generate` vorbei.

    Eine dritte Stelle, die Ollama direkt anspricht, bekaeme wieder das
    Vorgabefenster — also die stille Kuerzung, um die es hier geht.
    """
    src = _repo() / "src" / "bewerbungs_assistent"
    fundstellen = [p for p in src.rglob("*.py")
                   if "/api/generate" in p.read_text(encoding="utf-8")]
    assert [p.name for p in fundstellen] == ["llm_service.py"]
    quelle = fundstellen[0].read_text(encoding="utf-8")
    # Gezaehlt wird `num_ctx` INNERHALB der `options` eines Request-Bodys.
    # Meine erste Fassung zaehlte jedes `"num_ctx":` der Datei und traf
    # damit auch den Merkzettel `letzter_aufruf` — eine zu breite Messung
    # meldet einen Fehler im Code, wo einer im Test steckt (v1.7.83 MERKE 8).
    optionen_mit_fenster = re.findall(r'"options":\s*\{[^}]*"num_ctx"', quelle)
    assert quelle.count("/api/generate\"") == len(optionen_mit_fenster) == 2


# ------------------------------------ nicht passend -> benannt, nicht gekuerzt


def test_ein_zu_langer_prompt_wird_gar_nicht_erst_abgeschickt(db):
    from bewerbungs_assistent.services import ollama_kontext

    ollama_kontext.setzen(db, 2048)
    gesendet, fake = _abfangen()
    with patch.object(urllib.request, "urlopen", fake):
        with pytest.raises(ollama_kontext.KontextZuKlein) as info:
            _service(db)._ollama_generate("modell", "x" * 6000)
    assert gesendet == [], "Der Prompt ist trotzdem an Ollama gegangen"
    assert "2048" in str(info.value)
    assert "ollama_kontext" in str(info.value), "Der Weg hinaus fehlt"


def test_eine_antwort_am_fensterrand_wird_verworfen(db):
    """Die Schaetzung kann danebenliegen — die Messung des Modells nicht.

    Isolierender Fall: der Prompt ist KURZ (die Vorabpruefung laesst ihn
    durch), aber Ollama meldet einen vollen Kontext. Ohne die
    Nachher-Pruefung kaeme die Antwort als gueltig zurueck.
    """
    from bewerbungs_assistent.services import ollama_kontext

    gesendet, fake = _abfangen({"response": "PASST | alles gut",
                                "prompt_eval_count": 7900})
    with patch.object(urllib.request, "urlopen", fake):
        with pytest.raises(ollama_kontext.KontextZuKlein) as info:
            _service(db)._ollama_generate("modell", "kurzer prompt")
    assert len(gesendet) == 1
    assert "7900" in str(info.value)


def test_eine_antwort_mit_platz_kommt_durch_und_nennt_die_zahlen(db):
    gesendet, fake = _abfangen({"response": "lebenslauf", "prompt_eval_count": 900})
    svc = _service(db)
    with patch.object(urllib.request, "urlopen", fake):
        assert svc._ollama_generate("modell", "kurzer prompt") == "lebenslauf"
    assert svc.letzter_aufruf["prompt_tokens"] == 900
    assert svc.letzter_aufruf["num_ctx"] == 8192


def test_ohne_zaehler_in_der_antwort_bleibt_es_beim_bisherigen_verhalten(db):
    """Alte Ollama-Fassungen melden `prompt_eval_count` nicht. Das ist
    `unbekannt`, nicht `am Rand` (#989)."""
    gesendet, fake = _abfangen({"response": "ok"})
    with patch.object(urllib.request, "urlopen", fake):
        assert _service(db)._ollama_generate("modell", "kurz") == "ok"


def test_run_faellt_zurueck_und_nennt_den_grund(db):
    from bewerbungs_assistent.services.llm_service import Backend, TaskKind
    from bewerbungs_assistent.services.ollama_kontext import KontextZuKlein

    svc = _service(db)
    svc._status.selected_model = "modell"
    with patch.object(svc, "select_backend", return_value=Backend.LOCAL), \
            patch.object(svc, "get_status", return_value=svc._status), \
            patch.object(svc, "_ollama_generate", side_effect=KontextZuKlein("zu lang")):
        erg = svc.run(TaskKind.CLASSIFY_DOCUMENT, {"text": "x"})
    assert erg.backend == Backend.CLAUDE
    assert "zu lang" in (erg.fallback_message or "")
    assert erg.metrics.get("lokal_abgebrochen") == "kontext_zu_klein"


def test_ein_anderer_lokaler_fehler_behauptet_keinen_kontextgrund(db):
    from bewerbungs_assistent.services.llm_service import Backend, TaskKind

    svc = _service(db)
    svc._status.selected_model = "modell"
    with patch.object(svc, "select_backend", return_value=Backend.LOCAL), \
            patch.object(svc, "get_status", return_value=svc._status), \
            patch.object(svc, "_ollama_generate", side_effect=ConnectionResetError("weg")):
        erg = svc.run(TaskKind.CLASSIFY_DOCUMENT, {"text": "x"})
    assert "lokal_abgebrochen" not in erg.metrics
    assert "Grund" not in (erg.fallback_message or "")


# --------------------------------------------------- die Einstellung


@pytest.mark.parametrize("wert", ["acht", "8k", "8192.5", 1024, 262144, True, None, ""])
def test_ein_ungueltiger_wert_wird_abgewiesen_und_nichts_gespeichert(db, wert):
    from bewerbungs_assistent.services import ollama_kontext

    ollama_kontext.setzen(db, 16384)
    antwort = ollama_kontext.setzen(db, wert)
    assert "fehler" in antwort
    assert ollama_kontext.num_ctx_lesen(db) == 16384


def test_zuruecksetzen_fuehrt_zur_vorgabe(db):
    from bewerbungs_assistent.services import ollama_kontext

    ollama_kontext.setzen(db, 32768)
    assert ollama_kontext.zuruecksetzen(db)["num_ctx"] == 8192


def test_ein_kaputter_gespeicherter_wert_wird_benannt(db):
    """Er rechnet nicht mit, und das steht da — eine Einstellung ohne
    Wirkung, der man glaubt, ist #988."""
    from bewerbungs_assistent.services import ollama_kontext

    db.set_profile_setting(ollama_kontext.SCHLUESSEL, "riesig")
    antwort = ollama_kontext.lesen(db)
    assert antwort["num_ctx"] == 8192
    assert antwort["gespeicherter_wert_ungueltig"] == "riesig"
    assert antwort["eigener_wert"] is False


def test_die_antwort_nennt_den_speicherhinweis():
    """AK 4: KV-Cache und Flash-Attention stehen dort, wo man das Fenster
    einstellt — nicht nur in der Doku."""
    from bewerbungs_assistent.services import ollama_kontext

    antwort = ollama_kontext.lesen(None)
    assert "OLLAMA_KV_CACHE_TYPE=q8_0" in antwort["speicher"]
    assert "OLLAMA_FLASH_ATTENTION=1" in antwort["speicher"]


def test_das_mcp_werkzeug_setzt_liest_und_weist_ab(db):
    """Der Weg ueber Claude — echter Aufruf, kein Blick auf die Signatur."""
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all

    mcp = FastMCP("PBP Test 787")
    register_all(mcp, db, logging.getLogger("test.787"))

    def rufen(**args):
        async def _run():
            werkzeug = await mcp.get_tool("ollama_kontext")
            res = await werkzeug.run(args)
            return getattr(res, "structured_content", None) or res
        return asyncio.run(_run())

    assert rufen()["num_ctx"] == 8192
    assert rufen(aktion="setzen", wert=16384)["num_ctx"] == 16384
    abgewiesen = rufen(aktion="setzen", wert=100)
    assert "fehler" in abgewiesen
    assert abgewiesen["aktueller_stand"]["num_ctx"] == 16384
    assert rufen(aktion="zuruecksetzen")["num_ctx"] == 8192
    assert "fehler" in rufen(aktion="unsinn")


# ------------------------------------ passt jeder Builder in die Vorgabe?


# Deutlich laenger als jede Kappung eines Builders. Die erste Fassung war
# 22.000 Zeichen lang und die Textfelder 20.000 — eine auf 30.000
# angehobene Kappung blieb damit unter der Vorgabe, und der Guard blieb in
# der Gegenprobe gruen: er konnte genau den Fall nicht sehen, fuer den er
# da ist (v1.7.79 MERKE 9).
_TEXT = ("Verantwortung fuer Anforderungsmanagement und Prozessgestaltung in "
         "komplexen Projekten mit internationalen Teams. ") * 700


def _t(n):
    return _TEXT[:n]


def _realistische_hoechstwerte():
    """Je Aufgabe ein Payload mit den Laengen, die im Alltag vorkommen
    koennen: Textfelder bis zur Kappung des Builders und darueber,
    Titel/Firmen/Namen grosszuegig. Ein Feld auf 44.000 Zeichen zu
    setzen, das nie laenger als eine Zeile ist, misst die Messung."""
    return {
        "classify_document": {"text": _t(60000), "filename": _t(255)},
        "extract_skills": {"text": _t(60000)},
        "match_job_to_skills": {
            "profile_skills": [_t(60)] * 30,
            "profile_position": _t(200), "profile_seniority": _t(40),
            "job_title": _t(300), "job_company": _t(200),
            "job_description": _t(60000),
            "dismiss_reasons_top": [{"reason": _t(60), "count": 99}] * 5,
            "recent_dismissals": [{"title": _t(300), "company": _t(200),
                                   "dismiss_reason": _t(60)}] * 8,
        },
        "analyze_user_patterns": {"aggregate": {"window_days": 30,
                                                "daten": [_t(200)] * 200}},
        "classify_email": {"sender": _t(300), "subject": _t(500), "body": _t(60000)},
        "extract_contacts": {"text": _t(60000), "context_company": _t(200)},
        "validate_job_quality": {"title": _t(500), "company": _t(300),
                                 "location": _t(300), "source": _t(80),
                                 "url": _t(600), "description": _t(60000)},
        "extract_keywords": {"profil_text": _t(60000), "vorhandene": [_t(60)] * 40},
        "suggest_job_titles": {"profil_text": _t(60000)},
        "extract_newsletter_jobs": {"newsletter_text": _t(60000)},
    }


def test_jeder_prompt_builder_passt_mit_realistischen_hoechstwerten():
    """Gemessen am 12.09.2026: der groesste fertige Prompt liegt bei rund
    5.000 Zeichen. Waechst ein Builder (eine Kappung wird angehoben, ein
    Feld kommt ungekuerzt dazu), schlaegt dieser Test an — bevor Ollama
    im Feld still kuerzt.

    Ein NEUER Builder ohne Messfall schlaegt ebenfalls an: sonst waere er
    der eine, fuer den niemand gerechnet hat.
    """
    from bewerbungs_assistent.services import llm_service as L
    from bewerbungs_assistent.services import ollama_kontext

    faelle = _realistische_hoechstwerte()
    ohne_fall = sorted(t.value for t in L._PROMPT_BUILDERS if t.value not in faelle)
    assert not ohne_fall, f"Builder ohne Messfall: {ohne_fall}"

    zu_gross = {}
    for task, builder in L._PROMPT_BUILDERS.items():
        prompt = L._datums_kontext() + builder(faelle[task.value])
        benoetigt = ollama_kontext.schaetze_tokens(prompt) + 800
        if benoetigt > ollama_kontext.VORGABE:
            zu_gross[task.value] = benoetigt
    assert not zu_gross, f"Passen nicht in {ollama_kontext.VORGABE}: {zu_gross}"


def test_der_elwosa_dialog_teilt_dieselbe_pruefung(db):
    """Elwosa ruft `_ollama_generate` direkt und hat keinen Ausweichweg —
    dort muss der Grund in der Fehlermeldung ankommen, nicht verschluckt."""
    from bewerbungs_assistent.services import elwosa_dialog, ollama_kontext
    from bewerbungs_assistent.services.llm_service import LLMService

    ollama_kontext.setzen(db, 2048)

    def status(self, force_refresh=False):
        self._status.ollama_available = True
        self._status.selected_model = "modell"
        return self._status

    gesendet, fake = _abfangen()
    with patch.object(LLMService, "get_status", status), \
            patch.object(elwosa_dialog, "baue_prompt",
                         return_value=("x" * 9000, [], 0)), \
            patch.object(urllib.request, "urlopen", fake):
        erg = elwosa_dialog.frage_stellen(db, "Wie laeuft es?")
    assert erg["status"] == "fehler"
    assert "Kontextfenster" in erg["fehler"]
    assert gesendet == []
