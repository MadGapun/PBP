"""#1236 Stufe 1 -- die Anfrage an die API: Form, Fehlerbild, Wiederholung, Pause, Budget, Rueckfall.

Alles ueber ein Testdoppel am Transport (`_api_hilfen.FakeTransport`); die echte `urllib`-Strecke prueft der
letzte Abschnitt gegen einen Server auf `127.0.0.1`. Kein Test erreicht das Netz (Netzsperre in `conftest.py`),
und keiner nutzt einen echten Schluessel.
"""
from __future__ import annotations

import json
import os
import re
import socket
import ssl
import sys
import threading
import urllib.error
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _api_hilfen import FakeTransport, Schlafen, TESTSCHLUESSEL, antwort, fehlerantwort  # noqa: E402

from bewerbungs_assistent.services import api_backend  # noqa: E402
from bewerbungs_assistent.services.api_backend import ApiFehler  # noqa: E402
from bewerbungs_assistent.services.llm_service import (  # noqa: E402
    _PROMPT_BUILDERS, Backend, LLMService, TaskKind, TaskResult, _datums_kontext,
)

PAYLOAD_MATCH = {
    "profile_skills": ["Python", "Konstruktion"],
    "profile_position": "Konstrukteur",
    "profile_seniority": "Senior (12 Jahre Erfahrung)",
    "job_title": "Werkstudent Zeichnen",
    "job_company": "Beispiel AG",
    "job_description": "Wir suchen Unterstützung beim Zeichnen von Bauteilen. " * 10,
    "dismiss_reasons_top": [{"reason": "zu_junior", "count": 4}],
    "recent_dismissals": [{"title": "Praktikant bei Muster GmbH", "company": "Muster GmbH",
                           "dismiss_reason": "zu_junior"}],
    "profile_email": "SENTINEL-ausserhalb-der-feldliste",
}
PAYLOAD_VALIDATE = {"title": "Konstrukteur", "company": "Beispiel AG", "location": "Hamburg", "source": "test",
                    "url": "https://example.com/stelle/1", "description": "Aufgaben: Zeichnen. " * 20}


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database

    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "API-Test"})
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def schluessel(monkeypatch):
    monkeypatch.setenv(api_backend.ENV_SCHLUESSEL, TESTSCHLUESSEL)
    return TESTSCHLUESSEL


@pytest.fixture
def schlafen():
    return Schlafen()


def freigeben(db, *aufgaben, budget_usd="1", modelle=None):
    erg = api_backend.einstellungen_setzen(db, aufgaben=list(aufgaben), budget_usd=budget_usd, modelle=modelle,
                                           bestaetigt=True)
    assert erg["status"] == "gespeichert", erg


def dienst(db, ollama=False):
    svc = LLMService(db)
    svc._status.ollama_available = ollama
    svc._status.available_models = ["modell:1b"] if ollama else []
    svc._status.user_state = "active" if ollama else "off"
    svc._status.selected_model = "modell:1b" if ollama else None
    svc._status.last_check_at = 9999999999
    return svc


def einsatzbereit(db, transport, *aufgaben, **kw):
    freigeben(db, *(aufgaben or ("match_job_to_skills",)), **kw)
    api_backend.transport_setzen(transport)


# ============================================================ Die Form der Anfrage

def test_die_anfrage_hat_die_dokumentierte_form(db, schluessel):
    t = FakeTransport(antwort())
    einsatzbereit(db, t)
    dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    a = t.aufrufe[0]
    assert a["url"] == "https://api.anthropic.com/v1/messages"
    kopf = {k.lower(): v for k, v in a["kopf"].items()}
    assert kopf["x-api-key"] == schluessel
    assert kopf["anthropic-version"] == "2023-06-01"
    assert kopf["content-type"] == "application/json"
    assert kopf["user-agent"].startswith("PBP/")
    body = a["body"]
    assert body["model"] == "claude-haiku-5-5"
    assert body["max_tokens"] == api_backend.AUFGABEN["match_job_to_skills"].max_tokens
    assert len(body["messages"]) == 1 and body["messages"][0]["role"] == "user", (
        "Die Unterhaltung muss mit einem user-Beitrag enden: ein angefangener Antwortbeitrag wird abgewiesen")
    assert a["zeitlimit"] == api_backend.ZEITLIMIT_SEK


def test_keine_stichproben_parameter_die_neuen_modelle_weisen_sie_ab(db, schluessel):
    """Haiku 5.5 und die uebrigen 5er-Modelle antworten auf temperature, top_p und top_k mit einem Fehler 400."""
    t = FakeTransport(antwort())
    einsatzbereit(db, t)
    dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    for verboten in ("temperature", "top_p", "top_k"):
        assert verboten not in t.aufrufe[0]["body"]
        assert verboten not in t.aufrufe[0]["roh"].decode("utf-8")


@pytest.mark.parametrize("modell,thinking", [("claude-haiku-5-5", {"type": "disabled"}),
                                             ("claude-sonnet-5-5", {"type": "between_tools"})])
def test_das_denken_wird_je_modell_so_abgeschaltet_wie_es_dokumentiert_ist(db, schluessel, modell, thinking):
    t = FakeTransport(antwort())
    einsatzbereit(db, t, modelle={"match_job_to_skills": modell})
    dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert t.aufrufe[0]["body"]["model"] == modell
    assert t.aufrufe[0]["body"]["thinking"] == thinking


def test_denkbloecke_in_der_antwort_zaehlen_nicht_als_text(db, schluessel):
    t = FakeTransport(antwort("PASST_NICHT | Zu junge Stelle.", extra_bloecke=[
        {"type": "thinking", "thinking": "", "signature": "abc"}]))
    einsatzbereit(db, t)
    erg = dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert erg.success and erg.payload["decision"] == "PASST_NICHT" and "Zu junge Stelle" in erg.payload["reason"]


def test_der_prompt_traegt_den_datumskontext_und_ist_der_prompt_der_lokalen_ki(db, schluessel):
    """Gleichwertiger Schutz wie bei Ollama: heute ist heute, nicht das Trainingsdatum des Modells."""
    t = FakeTransport(antwort())
    einsatzbereit(db, t)
    dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    prompt = t.prompt
    heute = datetime.now().strftime("%d.%m.%Y")
    assert prompt.startswith("WICHTIG") and f"Heute ist der {heute}" in prompt
    assert re.match(r"WICHTIG — aktueller Zeitbezug: Heute ist der \d\d\.\d\d\.\d{4} \(Jahr \d{4}\)", prompt)
    sicher = api_backend.nutzlast_fuer_api("match_job_to_skills", PAYLOAD_MATCH)
    assert prompt.endswith(_PROMPT_BUILDERS[TaskKind.MATCH_JOB_TO_SKILLS](sicher)), (
        "Derselbe Bauer wie lokal: nur der Transport ist neu")


def test_nur_die_felder_der_feldliste_verlassen_den_rechner(db, schluessel):
    t = FakeTransport(antwort())
    einsatzbereit(db, t)
    dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    gesendet = t.aufrufe[0]["roh"].decode("utf-8")
    assert "SENTINEL" not in gesendet
    assert "Muster GmbH" not in gesendet and "[Firma]" in gesendet, "Firmennamen der Beispiele bleiben zu Hause"
    assert "Beispiel AG" in gesendet, "Die Firma der geprueften Stelle steht in der Feldliste"
    assert schluessel not in gesendet, "Der Schluessel gehoert in den Kopf, nie in den Inhalt"


def test_die_pruefung_der_anzeige_sendet_nichts_aus_dem_profil(db, schluessel):
    t = FakeTransport(antwort('{"vollstaendig": true, "score": 7, "claude_action": "keine"}'))
    einsatzbereit(db, t, "validate_job_quality")
    erg = dienst(db).run(TaskKind.VALIDATE_JOB_QUALITY, {**PAYLOAD_VALIDATE, "profile_position": "SENTINEL-profil"})
    assert erg.success and erg.payload["vollstaendig"] is True and erg.payload["score"] == 7
    assert "SENTINEL" not in t.aufrufe[0]["roh"].decode("utf-8")
    assert t.aufrufe[0]["body"]["max_tokens"] == api_backend.AUFGABEN["validate_job_quality"].max_tokens


def test_eine_zu_lange_eingabe_wird_nicht_gesendet(db, schluessel):
    t = FakeTransport(antwort())
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "x" * 100_000)
    assert info.value.code == "eingabe_zu_gross" and "Nicht gesendet" in info.value.text
    assert t.anzahl == 0


def test_der_erfolg_nennt_modell_tokens_und_kosten_in_den_metriken(db, schluessel):
    einsatzbereit(db, FakeTransport(antwort(ein=1000, aus=200)))
    erg = dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert erg.backend == Backend.API and erg.success
    m = erg.metrics
    assert (m["backend"], m["model"]) == ("anthropic_api", "claude-haiku-5-5")
    assert (m["eingabe_tokens"], m["ausgabe_tokens"], m["kosten_mikro_usd"]) == (1000, 200, 200)
    assert m["kosten_geschaetzt"] is False and m["duration_ms"] >= 0
    assert erg.payload["decision"] == "PASST" and "Titel und Profil" in erg.payload["reason"]


# ============================================================ Das Fehlerbild: je ein eigener Grund

@pytest.mark.parametrize("status,art,meldung,code,aufrufe", [
    (401, "authentication_error", "invalid x-api-key", "schluessel_ungueltig", 1),
    (402, "billing_error", "Billing problem", "guthaben_leer", 1),
    (400, "invalid_request_error", "Your credit balance is too low to access the Anthropic API.", "guthaben_leer", 1),
    (400, "invalid_request_error", "You have reached your workspace spend limit.", "guthaben_leer", 1),
    (400, "invalid_request_error", "messages: Field required", "anfrage_abgelehnt", 1),
    (403, "permission_error", "Not allowed", "kein_zugriff", 1),
    (404, "not_found_error", "model: claude-haiku-5-5", "modell_nicht_gefunden", 1),
    (413, "request_too_large", "Too big", "eingabe_zu_gross", 1),
    (429, "rate_limit_error", "Rate limit", "limit_erreicht", 2),
    (500, "api_error", "Internal", "ueberlastet", 2),
    (529, "overloaded_error", "Overloaded", "ueberlastet", 2),
    (504, "timeout_error", "Timeout", "zeitueberschreitung", 1),
    (418, "teapot", "Ich bin eine Teekanne", "unerwartet", 1),
])
def test_jeder_fehler_der_api_hat_einen_eigenen_grund_und_hoechstens_eine_wiederholung(
        db, schluessel, schlafen, status, art, meldung, code, aufrufe):
    t = FakeTransport(fehlerantwort(status, art, meldung))
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt", transport=t, schlafen=schlafen)
    assert info.value.code == code and info.value.http_status == status
    assert t.anzahl == aufrufe, "Hoechstens EINE Wiederholung, keine Schleife"
    assert info.value.request_id == "req_fehler"
    assert info.value.text, "Jeder Grund hat einen Satz fuer Menschen"
    if code in ("anfrage_abgelehnt", "unerwartet", "kein_zugriff", "guthaben_leer", "limit_erreicht"):
        assert meldung in info.value.text, "Was die API selbst sagt, steht dabei"


def test_eine_wiederholung_bei_429_wartet_die_angegebene_zeit_gedeckelt(db, schluessel, schlafen):
    t = FakeTransport(fehlerantwort(429, "rate_limit_error", "x", kopf={"retry-after": "3"}), antwort())
    einsatzbereit(db, t)
    erg = api_backend.senden(db, "match_job_to_skills", "Prompt", transport=t, schlafen=schlafen)
    assert erg.text and t.anzahl == 2 and schlafen.zeiten == [3.0]


@pytest.mark.parametrize("kopf,erwartet", [({"retry-after": "999"}, api_backend.WARTEZEIT_MAX_SEK),
                                           ({}, api_backend.WARTEZEIT_SEK), ({"retry-after": "bald"}, api_backend.WARTEZEIT_SEK),
                                           ({"Retry-After": "0"}, 0.0)])
def test_die_wartezeit_ist_gedeckelt_und_hat_eine_vorgabe(db, schluessel, schlafen, kopf, erwartet):
    t = FakeTransport(fehlerantwort(429, "rate_limit_error", "x", kopf=kopf), antwort())
    einsatzbereit(db, t)
    api_backend.senden(db, "match_job_to_skills", "Prompt", transport=t, schlafen=schlafen)
    assert schlafen.zeiten == [erwartet]


def test_zwei_fehler_hintereinander_geben_auf_ohne_dritten_versuch(db, schluessel, schlafen):
    t = FakeTransport(fehlerantwort(500, "api_error", "a"), fehlerantwort(529, "overloaded_error", "b"), antwort())
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt", transport=t, schlafen=schlafen)
    assert info.value.code == "ueberlastet" and info.value.http_status == 529
    assert t.anzahl == 2 and len(schlafen.zeiten) == 1


@pytest.mark.parametrize("fehler,code", [
    (TimeoutError("zu langsam"), "zeitueberschreitung"),
    (socket.timeout("zu langsam"), "zeitueberschreitung"),
    (urllib.error.URLError(TimeoutError("timed out")), "zeitueberschreitung"),
    (ConnectionRefusedError("abgelehnt"), "kein_netz"),
    (urllib.error.URLError("Name or service not known"), "kein_netz"),
    (OSError("Network is unreachable"), "kein_netz"),
    (ssl.SSLError("CERTIFICATE_VERIFY_FAILED"), "kein_netz"),
])
def test_netzfehler_haben_je_einen_grund_und_werden_nicht_wiederholt(db, schluessel, schlafen, fehler, code):
    t = FakeTransport(fehler)
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt", transport=t, schlafen=schlafen)
    assert info.value.code == code
    assert t.anzahl == 1 and schlafen.zeiten == [], "Eine Zeitueberschreitung kann schon abgerechnet sein: nie wiederholen"


def test_ein_netzfehler_gibt_den_text_des_fehlers_nicht_weiter(db, schluessel):
    """Die Meldung einer Ausnahme kann alles enthalten, auch den Kopf der Anfrage: nur der Typ geht weiter."""
    t = FakeTransport(OSError(f"Verbindung abgebrochen, x-api-key: {TESTSCHLUESSEL}"))
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt", transport=t)
    assert TESTSCHLUESSEL not in info.value.text and "OSError" in info.value.text


def test_ein_echo_des_schluessels_in_der_antwort_der_api_wird_geschwaerzt(db, schluessel):
    t = FakeTransport(fehlerantwort(401, "authentication_error", f"invalid x-api-key: {TESTSCHLUESSEL}"))
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt", transport=t)
    assert TESTSCHLUESSEL not in info.value.text and "***" in info.value.text
    assert TESTSCHLUESSEL not in str(info.value) and TESTSCHLUESSEL not in repr(info.value.args)


def test_ein_zwischenhaendler_der_den_schluessel_in_die_antwort_spiegelt_traegt_ihn_nicht_in_die_ergebnisse(db, schluessel):
    """Auch was HEREINkommt geht durch `schwaerzen`: die Antwort fliesst in Notizen der Stellen und in Berichte."""
    einsatzbereit(db, FakeTransport(antwort(f"PASST | Der Schlüssel lautet {TESTSCHLUESSEL}.")))
    erg = dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert erg.success and TESTSCHLUESSEL not in json.dumps(erg.payload) and "***" in erg.payload["reason"]
    assert TESTSCHLUESSEL not in erg.payload["raw"]


def test_ein_fremder_schluessel_im_text_wird_auch_geschwaerzt(schluessel):
    fremd = "sk-" + "ant-api03-" + "ANDERER" + "-Wert-" + "9876543210"
    assert api_backend.schwaerzen(f"vorher {fremd} nachher") == "vorher *** nachher"
    assert TESTSCHLUESSEL not in api_backend.schwaerzen(f"x {TESTSCHLUESSEL} y")
    assert api_backend.schwaerzen("ganz normaler Satz") == "ganz normaler Satz"


# ------------------------------------------------------------ Antworten, die ankommen und trotzdem nichts taugen

def test_eine_unlesbare_antwort_ist_ein_grund_und_wird_als_geschaetzt_gebucht(db, schluessel):
    t = FakeTransport((200, {}, b"<html>Gateway</html>"))
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt", transport=t)
    assert info.value.code == "antwort_unlesbar"
    z = api_backend.zaehler_lesen(db)
    assert z["aufrufe"] == 1 and z["geschaetzt"] == 1 and z["mikro_usd"] > 0, (
        "Die API hat geantwortet, vermutlich abgerechnet: der schlimmste Fall wird gebucht, nicht Null")


def test_eine_antwort_ohne_text_ist_ein_grund_aber_die_tokens_sind_gebucht(db, schluessel):
    daten = {"content": [], "stop_reason": "end_turn", "usage": {"input_tokens": 50, "output_tokens": 5}}
    t = FakeTransport((200, {}, json.dumps(daten).encode()))
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt", transport=t)
    assert info.value.code == "antwort_leer"
    z = api_backend.zaehler_lesen(db)
    assert (z["aufrufe"], z["eingabe_tokens"], z["ausgabe_tokens"], z["geschaetzt"]) == (1, 50, 5, 0)


def test_abgeschnitten_vor_dem_text_wird_benannt(db, schluessel):
    daten = {"content": [{"type": "thinking", "thinking": "", "signature": "s"}], "stop_reason": "max_tokens",
             "usage": {"input_tokens": 50, "output_tokens": 300}}
    t = FakeTransport((200, {}, json.dumps(daten).encode()))
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt", transport=t)
    assert info.value.code == "antwort_leer" and "abgeschnitten" in info.value.text


def test_eine_verweigerung_des_modells_ist_ein_grund_und_pausiert_nicht(db, schluessel):
    t = FakeTransport(antwort("", stop="refusal"))
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt", transport=t)
    assert info.value.code == "antwort_abgelehnt"
    assert api_backend.pause_aktiv() is None, "Das betrifft nur diese Eingabe, nicht den ganzen Weg"
    assert api_backend.zaehler_lesen(db)["aufrufe"] == 1


# ============================================================ Der Rueckfall: lokal, dann Claude, mit Grund

def test_faellt_die_api_aus_und_ist_ollama_da_geht_derselbe_aufruf_lokal_weiter(db, schluessel):
    t = FakeTransport(fehlerantwort(402, "billing_error", "x"))
    einsatzbereit(db, t)
    svc = dienst(db, ollama=True)
    lokal = TaskResult(backend=Backend.LOCAL, success=True, payload={"decision": "PASST", "reason": "lokal"},
                       metrics={"backend": "ollama"})
    with patch.object(svc, "_run_local", return_value=lokal):
        erg = svc.run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert erg.backend == Backend.LOCAL and erg.success
    assert erg.metrics["api_abgebrochen"] == "guthaben_leer" and "Guthaben" in erg.metrics["api_grund"]
    assert t.anzahl == 1


def test_ohne_ollama_landet_es_bei_claude_und_die_meldung_nennt_den_grund(db, schluessel):
    einsatzbereit(db, FakeTransport(fehlerantwort(401, "authentication_error", "invalid x-api-key")))
    erg = dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert erg.backend == Backend.CLAUDE and not erg.success
    assert "API-Weg:" in erg.fallback_message and "Schlüssel" in erg.fallback_message
    assert erg.metrics["api_abgebrochen"] == "schluessel_ungueltig"


def test_ein_programmfehler_im_api_weg_wird_zum_grund_und_nennt_nur_den_typ(db, schluessel):
    einsatzbereit(db, FakeTransport(antwort()))
    svc = dienst(db)
    with patch.object(api_backend, "senden", side_effect=KeyError(TESTSCHLUESSEL)):
        erg = svc.run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert erg.backend == Backend.CLAUDE
    assert erg.metrics["api_abgebrochen"] == "unerwartet"
    assert "KeyError" in erg.metrics["api_grund"] and TESTSCHLUESSEL not in erg.metrics["api_grund"]
    assert TESTSCHLUESSEL not in erg.fallback_message


def test_dieselbe_aufgabe_ohne_freigabe_bekommt_keine_api_metrik(db, schluessel):
    api_backend.transport_setzen(FakeTransport(antwort()))
    erg = dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert not any(k.startswith("api_") for k in erg.metrics)
    assert "API" not in (erg.fallback_message or "")


def test_ist_der_weg_freigegeben_aber_nicht_nutzbar_steht_der_grund_in_den_metriken(db, schluessel, monkeypatch):
    t = FakeTransport(antwort())
    einsatzbereit(db, t)
    monkeypatch.delenv(api_backend.ENV_SCHLUESSEL)
    erg = dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert erg.metrics["api_ausgelassen"] == "kein_schluessel" and "api_abgebrochen" not in erg.metrics
    assert t.anzahl == 0


# ============================================================ Der Schutzschalter: keine Schleife

def test_nach_einem_harten_fehler_ruht_der_weg_und_nicht_jede_stelle_fragt_erneut(db, schluessel):
    t = FakeTransport(fehlerantwort(401, "authentication_error", "invalid x-api-key"))
    einsatzbereit(db, t)
    svc = dienst(db)
    for _ in range(6):
        svc.run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert t.anzahl == 1, "Sechs Stellen, ein einziger Abruf: danach ruht der Weg"
    z = api_backend.zustand(db, "match_job_to_skills")
    assert not z.erlaubt and z.grund == "schluessel_ungueltig" and "ruht" in z.text
    letzter = svc.run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert letzter.metrics["api_ausgelassen"] == "schluessel_ungueltig"


def test_die_pause_endet_von_selbst(db, schluessel):
    einsatzbereit(db, FakeTransport(fehlerantwort(529, "overloaded_error", "x")))
    dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert api_backend.pause_aktiv()["code"] == "ueberlastet"
    with patch.object(api_backend.time, "monotonic", return_value=api_backend.time.monotonic() + 10_000):
        assert api_backend.pause_aktiv() is None
        assert api_backend.zustand(db, "match_job_to_skills").erlaubt


def test_weiche_fehler_ruhen_kuerzer_als_harte():
    assert api_backend.PAUSE_WEICH_SEK < api_backend.PAUSE_HART_SEK
    api_backend.pause_setzen("kein_netz", "x")
    weich = api_backend.pause_aktiv()["rest_sekunden"]
    api_backend.pause_setzen("guthaben_leer", "x")
    assert api_backend.pause_aktiv()["rest_sekunden"] > weich


@pytest.mark.parametrize("code", ["antwort_leer", "antwort_unlesbar", "antwort_abgelehnt", "eingabe_zu_gross",
                                  "budget_erreicht", "kein_budget", "aufgabe_nicht_vorgesehen"])
def test_fehler_die_nur_diese_eingabe_betreffen_pausieren_nicht(code):
    api_backend.pause_setzen(code, "x")
    assert api_backend.pause_aktiv() is None


def test_eine_aenderung_der_einstellung_hebt_die_pause_auf(db, schluessel):
    einsatzbereit(db, FakeTransport(fehlerantwort(401, "authentication_error", "x")))
    dienst(db).run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert api_backend.pause_aktiv()
    api_backend.einstellungen_setzen(db, budget_usd=2)
    assert api_backend.pause_aktiv() is None


# ============================================================ Das Budget

def test_der_zaehler_stimmt_mit_den_usage_angaben_der_antworten_ueberein(db, schluessel):
    einsatzbereit(db, FakeTransport(antwort(ein=100, aus=20), antwort(ein=250, aus=40), antwort(ein=5, aus=1)))
    for _ in range(3):
        api_backend.senden(db, "match_job_to_skills", "Prompt")
    z = api_backend.zaehler_lesen(db)
    assert (z["aufrufe"], z["eingabe_tokens"], z["ausgabe_tokens"]) == (3, 355, 61)
    # 100*0,10+20*0,50 = 20 | 250*0,10+40*0,50 = 45 | 5*0,10+1*0,50 = 1 (genau)
    assert z["mikro_usd"] == 20 + 45 + 1 == 66
    assert z["geschaetzt"] == 0 and z["seit"]
    erg = api_backend.uebersicht(db)["verbrauch"]
    assert erg["aufrufe"] == 3 and erg["eingabe_tokens"] == 355 and erg["usd"] == 66 / 1_000_000


def test_zwischenspeicher_tokens_zaehlen_zur_eingabe(db, schluessel):
    daten = {"content": [{"type": "text", "text": "PASST | ok"}], "stop_reason": "end_turn",
             "usage": {"input_tokens": 10, "output_tokens": 2, "cache_creation_input_tokens": 100,
                       "cache_read_input_tokens": 1000}}
    einsatzbereit(db, FakeTransport((200, {}, json.dumps(daten).encode())))
    erg = api_backend.senden(db, "match_job_to_skills", "Prompt")
    assert erg.eingabe_tokens == 1110, "Das ueberschaetzt hoechstens: nie weniger buchen als verbraucht wurde"


def test_ohne_usage_in_der_antwort_wird_der_schlimmste_fall_gebucht_und_gezeigt(db, schluessel):
    einsatzbereit(db, FakeTransport(antwort(nutzung=False)))
    erg = api_backend.senden(db, "match_job_to_skills", "Prompt " * 100)
    assert erg.geschaetzt and erg.kosten_mikro > 0
    z = api_backend.zaehler_lesen(db)
    assert z["geschaetzt"] == 1 and z["mikro_usd"] == erg.kosten_mikro and z["aufrufe"] == 1
    hinweise = api_backend.uebersicht(db)["hinweise"]
    assert any("ungünstigsten Fall" in h for h in hinweise), "Unbekannt ist ein eigener Zustand: es wird gezeigt"


def test_das_budget_stoppt_vor_dem_ueberschreiten(db, schluessel):
    """Zwei Aufrufe fuellen das Budget exakt; der dritte wird nicht mehr gesendet."""
    gross = antwort(ein=40_000, aus=2_000)  # 40.000*0,10 + 2.000*0,50 = 5.000 Mikro-Dollar
    t = FakeTransport(gross)
    einsatzbereit(db, t, budget_usd="0.01")  # 10.000 Mikro-Dollar
    svc = dienst(db)
    for _ in range(2):
        assert svc.run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH).backend == Backend.API
        assert api_backend.zaehler_lesen(db)["mikro_usd"] <= 10_000
    assert api_backend.zaehler_lesen(db)["mikro_usd"] == 10_000
    erg = svc.run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)
    assert erg.backend != Backend.API and t.anzahl == 2
    assert erg.metrics["api_ausgelassen"] == "budget_erreicht" and "aufgebraucht" in erg.metrics["api_grund"]


def test_das_budget_rechnet_den_schlimmsten_fall_des_naechsten_aufrufs_mit(db, schluessel):
    """Noch Luft, aber nicht genug fuer einen Aufruf im ungünstigsten Fall: nicht senden."""
    t = FakeTransport(antwort(ein=90_000, aus=1_800))  # 9.000 + 900 = 9.900 Mikro-Dollar
    einsatzbereit(db, t, budget_usd="0.01")
    api_backend.senden(db, "match_job_to_skills", "Prompt")
    assert api_backend.zaehler_lesen(db)["mikro_usd"] == 9_900
    assert api_backend.zustand(db, "match_job_to_skills").erlaubt, "Die Grenze selbst ist noch nicht erreicht"
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt")
    assert info.value.code == "budget_erreicht" and "reicht für diesen Aufruf nicht mehr" in info.value.text
    assert "0,0099 US-Dollar" in info.value.text and "0,01 US-Dollar" in info.value.text
    assert t.anzahl == 1


def test_laufende_aufrufe_zaehlen_gegen_das_budget(db, schluessel):
    """Zwei Aufrufe gleichzeitig duerfen zusammen nicht ueber die Grenze: der laufende haelt seine Reserve."""
    einsatzbereit(db, None, modelle={"match_job_to_skills": "claude-sonnet-5-5"}, budget_usd="0.01")
    prompt = "x" * 5_000  # geschaetzt 2.050 Tokens * 2 + 300 * 10 = 7.100 Mikro-Dollar im schlimmsten Fall
    verschachtelt: list = []

    def transport(url, kopf, body, zeitlimit):
        try:
            api_backend.senden(db, "match_job_to_skills", prompt, transport=FakeTransport(antwort()))
        except ApiFehler as exc:
            verschachtelt.append(exc)
        return antwort()

    api_backend.senden(db, "match_job_to_skills", prompt, transport=transport)
    assert len(verschachtelt) == 1 and verschachtelt[0].code == "budget_erreicht"
    assert api_backend._IN_FLIGHT == 0, "Die Reserve wird am Ende immer freigegeben"


def test_die_reserve_wird_auch_nach_einem_fehler_freigegeben(db, schluessel):
    einsatzbereit(db, FakeTransport(fehlerantwort(500, "api_error", "x")))
    with pytest.raises(ApiFehler):
        api_backend.senden(db, "match_job_to_skills", "Prompt", schlafen=Schlafen())
    assert api_backend._IN_FLIGHT == 0


def test_vor_dem_senden_wird_alles_noch_einmal_geprueft(db, schluessel):
    """Zwischen der Wahl des Weges und dem Senden kann jemand den Schalter umlegen."""
    t = FakeTransport(antwort())
    einsatzbereit(db, t)
    assert dienst(db).select_backend(TaskKind.MATCH_JOB_TO_SKILLS) == Backend.API
    db.set_ki_features(master=False)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt")
    assert info.value.code == "ki_schalter_aus" and t.anzahl == 0


def test_eine_nicht_vorgesehene_aufgabe_wird_nie_gesendet(db, schluessel):
    t = FakeTransport(antwort())
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "extract_contacts", "Prompt")
    assert info.value.code == "aufgabe_nicht_vorgesehen" and t.anzahl == 0


# ============================================================ „Schluessel gueltig“ erst nach einer echten Probe

def test_gueltig_steht_erst_nach_einer_echten_probe(db, schluessel):
    assert api_backend.pruefung_lesen(db)["ergebnis"] == "nicht_geprueft"
    assert api_backend.uebersicht(db)["pruefung"]["ergebnis"] == "nicht_geprueft"
    t = FakeTransport(antwort("ok", ein=12, aus=1))
    erg = api_backend.schluessel_pruefen(db, transport=t)
    assert erg["ergebnis"] == "gueltig" and t.anzahl == 1
    body = t.aufrufe[0]["body"]
    assert body["max_tokens"] == 16, "Die kleinste Antwortlaenge: die Probe soll fast nichts kosten"
    assert "ok" in body["messages"][0]["content"]
    assert api_backend.pruefung_lesen(db)["ergebnis"] == "gueltig"
    assert api_backend.zaehler_lesen(db)["aufrufe"] == 1, "Auch die Probe steht im Zaehler"


def test_die_pruefung_gilt_nur_fuer_den_geprueften_schluessel(db, schluessel, monkeypatch):
    api_backend.schluessel_pruefen(db, transport=FakeTransport(antwort("ok")))
    assert api_backend.pruefung_lesen(db)["ergebnis"] == "gueltig"
    monkeypatch.setenv(api_backend.ENV_SCHLUESSEL, "sk-" + "ant-api03-" + "ANDERER" + "-Wert-" + "1111111111")
    assert api_backend.pruefung_lesen(db)["ergebnis"] == "nicht_geprueft", (
        "Ein anderer Schluessel erbt kein 'gueltig'")
    monkeypatch.delenv(api_backend.ENV_SCHLUESSEL)
    assert api_backend.pruefung_lesen(db)["ergebnis"] == "nicht_geprueft"


def test_die_pruefung_speichert_den_schluessel_nicht(db, schluessel):
    api_backend.schluessel_pruefen(db, transport=FakeTransport(antwort("ok")))
    roh = json.dumps(api_backend._global(db, api_backend.S_PRUEFUNG))
    assert schluessel not in roh and schluessel[:20] not in roh
    assert api_backend._global(db, api_backend.S_PRUEFUNG)["kennung"] == api_backend.schluessel_kennung()
    assert len(api_backend.schluessel_kennung()) == 12


@pytest.mark.parametrize("antwort_,ergebnis,code", [
    (fehlerantwort(401, "authentication_error", "invalid x-api-key"), "ungueltig", "schluessel_ungueltig"),
    (fehlerantwort(402, "billing_error", "x"), "unklar", "guthaben_leer"),
    (fehlerantwort(429, "rate_limit_error", "x"), "unklar", "limit_erreicht"),
    (fehlerantwort(500, "api_error", "x"), "unklar", "ueberlastet"),
    (ConnectionRefusedError("x"), "unklar", "kein_netz"),
    (TimeoutError("x"), "unklar", "zeitueberschreitung"),
])
def test_eine_misslungene_probe_sagt_nie_gueltig(db, schluessel, antwort_, ergebnis, code):
    erg = api_backend.schluessel_pruefen(db, transport=FakeTransport(antwort_), schlafen=Schlafen())
    assert erg["ergebnis"] == ergebnis and erg["code"] == code
    assert api_backend.pruefung_lesen(db)["ergebnis"] == ergebnis
    assert api_backend.pruefung_lesen(db)["ergebnis"] != "gueltig"


def test_ohne_schluessel_gibt_es_nichts_zu_pruefen(db):
    t = FakeTransport(antwort("ok"))
    erg = api_backend.schluessel_pruefen(db, transport=t)
    assert erg["ergebnis"] == "nicht_geprueft" and erg["code"] == "kein_schluessel" and t.anzahl == 0


def test_ein_spaeteres_401_kippt_ein_gueltig_zurueck(db, schluessel):
    api_backend.schluessel_pruefen(db, transport=FakeTransport(antwort("ok")))
    einsatzbereit(db, FakeTransport(fehlerantwort(401, "authentication_error", "x")))
    with pytest.raises(ApiFehler):
        api_backend.senden(db, "match_job_to_skills", "Prompt")
    assert api_backend.pruefung_lesen(db)["ergebnis"] == "ungueltig"


def test_die_probe_hebt_eine_pause_auf_und_beachtet_ein_aufgebrauchtes_budget(db, schluessel):
    api_backend.pause_setzen("guthaben_leer", "x")
    api_backend.schluessel_pruefen(db, transport=FakeTransport(antwort("ok")))
    assert api_backend.pause_aktiv() is None
    api_backend.einstellungen_setzen(db, budget_usd="0.01")
    api_backend.verbuchen(db, 0, 0, 10_000)
    t = FakeTransport(antwort("ok"))
    erg = api_backend.schluessel_pruefen(db, transport=t)
    assert erg["code"] == "budget_erreicht" and t.anzahl == 0


# ============================================================ Die letzte Auskunft fuer die Anzeige

def test_der_letzte_aufruf_merkt_sich_den_fehler_mit_grund_ohne_schluessel(db, schluessel):
    einsatzbereit(db, FakeTransport(fehlerantwort(402, "billing_error", f"x {TESTSCHLUESSEL}")))
    with pytest.raises(ApiFehler):
        api_backend.senden(db, "match_job_to_skills", "Prompt")
    letzter = api_backend.letzten_aufruf_lesen(db)
    assert letzter["ok"] is False and letzter["code"] == "guthaben_leer" and letzter["aufgabe"] == "match_job_to_skills"
    assert TESTSCHLUESSEL not in json.dumps(letzter)


def test_ein_erfolg_schreibt_hoechstens_alle_dreissig_sekunden(db, schluessel):
    einsatzbereit(db, FakeTransport(antwort()))
    api_backend.senden(db, "match_job_to_skills", "Prompt")
    erste = api_backend.letzten_aufruf_lesen(db)
    assert erste["ok"] is True
    db.set_setting(api_backend.S_LETZTER, {"ok": True, "zeit": "marker"})
    api_backend.senden(db, "match_job_to_skills", "Prompt")
    assert api_backend.letzten_aufruf_lesen(db)["zeit"] == "marker", "Erfolge in Folge schreiben nicht jedes Mal"


# ============================================================ Die echte urllib-Strecke gegen einen lokalen Server

class _Server:
    def __init__(self, antworten):
        gesehen: list = []
        warteschlange = list(antworten)

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                laenge = int(self.headers.get("content-length", 0))
                gesehen.append({"pfad": self.path, "kopf": {k.lower(): v for k, v in self.headers.items()},
                                "body": json.loads(self.rfile.read(laenge).decode("utf-8"))})
                status, kopf, koerper, verzoegerung = (warteschlange.pop(0) if len(warteschlange) > 1
                                                       else warteschlange[0])
                if verzoegerung:
                    import time
                    time.sleep(verzoegerung)
                try:
                    self.send_response(status)
                    for k, v in kopf.items():
                        self.send_header(k, v)
                    self.send_header("content-length", str(len(koerper)))
                    self.end_headers()
                    self.wfile.write(koerper)
                except OSError:
                    pass

            def log_message(self, *a):  # still
                pass

        self.gesehen = gesehen
        self.http = HTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, name="test-http-1236", daemon=True)
        self.thread.start()
        self.adresse = f"http://127.0.0.1:{self.http.server_address[1]}/v1/messages"

    def stoppen(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=5)


@pytest.fixture
def lokaler_server(monkeypatch):
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    erzeugt: list = []

    def bauen(*antworten):
        # eine Antwort ist (status, kopf, koerper) oder (status, kopf, koerper, verzoegerung_sek)
        s = _Server([tuple(a) + (0,) * (4 - len(a)) for a in antworten])
        monkeypatch.setattr(api_backend, "ADRESSE", s.adresse)
        erzeugt.append(s)
        return s

    yield bauen
    for s in erzeugt:
        s.stoppen()


def test_die_echte_strecke_sendet_kopf_und_body_und_liest_die_antwort(db, schluessel, lokaler_server):
    server = lokaler_server(antwort(ein=100, aus=20))
    freigeben(db, "match_job_to_skills")
    erg = api_backend.senden(db, "match_job_to_skills", "Prompt")  # kein Testdoppel: urllib gegen 127.0.0.1
    assert erg.text.startswith("PASST") and erg.eingabe_tokens == 100 and erg.request_id == "req_test"
    gesehen = server.gesehen[0]
    assert gesehen["pfad"] == "/v1/messages"
    assert gesehen["kopf"]["x-api-key"] == schluessel and gesehen["kopf"]["anthropic-version"] == "2023-06-01"
    assert gesehen["kopf"]["content-type"] == "application/json"
    assert gesehen["body"]["model"] == "claude-haiku-5-5"


def test_die_echte_strecke_macht_aus_einem_http_fehler_einen_grund(db, schluessel, lokaler_server):
    lokaler_server(fehlerantwort(401, "authentication_error", "invalid x-api-key"))
    freigeben(db, "match_job_to_skills")
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt")
    assert info.value.code == "schluessel_ungueltig" and info.value.http_status == 401
    assert info.value.request_id == "req_fehler"


def test_die_echte_strecke_wiederholt_nach_429_genau_einmal(db, schluessel, lokaler_server, monkeypatch):
    server = lokaler_server(fehlerantwort(429, "rate_limit_error", "x", kopf={"retry-after": "0"}), antwort())
    monkeypatch.setattr(api_backend, "_schlafen", lambda s: None)
    freigeben(db, "match_job_to_skills")
    assert api_backend.senden(db, "match_job_to_skills", "Prompt").text
    assert len(server.gesehen) == 2


def test_die_echte_strecke_kennt_eine_geschlossene_tuer(db, schluessel, monkeypatch):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    monkeypatch.setattr(api_backend, "ADRESSE", f"http://127.0.0.1:{port}/v1/messages")
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    freigeben(db, "match_job_to_skills")
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt")
    assert info.value.code == "kein_netz"


def test_die_echte_strecke_kennt_eine_zeitueberschreitung(db, schluessel, lokaler_server, monkeypatch):
    lokaler_server((200, {}, b"{}", 1.5))
    monkeypatch.setattr(api_backend, "ZEITLIMIT_SEK", 0.3)
    freigeben(db, "match_job_to_skills")
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Prompt")
    assert info.value.code == "zeitueberschreitung"
    assert api_backend.zaehler_lesen(db)["geschaetzt"] == 1, "Die Anfrage war raus: der schlimmste Fall ist gebucht"


# ============================================================ Funde der unabhaengigen Pruefung (16.10.2026)

def test_scheitert_das_speichern_des_verbrauchs_geht_der_betrag_nicht_verloren(db, schluessel, monkeypatch):
    """Die Antwort ist da und bezahlt. Liesse man den Fehler beim Buchen hochlaufen, waere der Betrag weg, das Budget nie
    angerechnet, und jeder weitere Aufruf wuerde bezahlt, solange das Schreiben scheitert."""
    import sqlite3
    t = FakeTransport(antwort(ein=90_000, aus=1_800))  # 9.900 Mikro-Dollar
    einsatzbereit(db, t, budget_usd="0.01")
    echt = api_backend.verbuchen

    def gesperrt(*_a, **_k):
        raise sqlite3.OperationalError("database is locked")

    monkeypatch.setattr(api_backend, "verbuchen", gesperrt)
    a = api_backend.senden(db, "match_job_to_skills", "Frage")
    assert a.text and a.kosten_mikro == 9_900, "Die Antwort geht trotzdem an den Aufrufer: sie ist bezahlt"
    assert api_backend._UNGEBUCHT == 9_900 and api_backend.zaehler_lesen(db)["mikro_usd"] == 0
    pause = api_backend.pause_aktiv()
    assert pause and pause["code"] == "buchung_fehlgeschlagen"
    z = api_backend.zustand(db, "match_job_to_skills")
    assert not z.erlaubt and z.grund == "buchung_fehlgeschlagen"
    # Die Pause ist vorbei, das Schreiben scheitert weiter: der Betrag zaehlt gegen das Budget, es wird nicht gesendet.
    api_backend.pause_aufheben()
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Frage")
    assert info.value.code == "budget_erreicht" and t.anzahl == 1
    # Das Schreiben geht wieder: der naechste Aufruf holt den Betrag nach.
    monkeypatch.setattr(api_backend, "verbuchen", echt)
    api_backend.einstellungen_setzen(db, budget_usd="1")
    api_backend.pause_aufheben()
    api_backend.senden(db, "match_job_to_skills", "Frage")
    assert api_backend.zaehler_lesen(db)["mikro_usd"] == 2 * 9_900 and api_backend._UNGEBUCHT == 0


def test_verbuchen_ist_alles_oder_nichts(db, monkeypatch):
    """Scheitert ein Schritt, bleibt kein halber Aufruf in der offenen Transaktion der Verbindung liegen, der beim
    naechsten fremden Commit mitgeschrieben wuerde."""
    import sqlite3
    echt = api_backend._addieren
    gesehen = []

    def kaputt(db_, schluessel_, delta):
        gesehen.append(schluessel_)
        if len(gesehen) == 3:
            raise sqlite3.OperationalError("database is locked")
        echt(db_, schluessel_, delta)

    monkeypatch.setattr(api_backend, "_addieren", kaputt)
    with pytest.raises(sqlite3.OperationalError):
        api_backend.verbuchen(db, 10, 5, 100)
    monkeypatch.setattr(api_backend, "_addieren", echt)
    z = api_backend.zaehler_lesen(db)
    assert (z["aufrufe"], z["eingabe_tokens"], z["ausgabe_tokens"], z["mikro_usd"]) == (0, 0, 0, 0)
    assert db.connect().in_transaction is False


def test_ein_zeitablauf_nach_dem_senden_wird_als_geschaetzt_gebucht_einer_beim_verbinden_nicht(db, schluessel):
    """Bleibt die Antwort aus, hat die API die Anfrage trotzdem bekommen und kann gerechnet haben: unbekannt ist ein eigener
    Zustand, gebucht wird der schlimmste Fall. Ein Zeitablauf beim VERBINDEN (urllib packt ihn in eine URLError) heisst:
    nichts gesendet, nichts gebucht."""
    import urllib.error
    t = FakeTransport(TimeoutError())
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Frage")
    assert info.value.code == "zeitueberschreitung"
    z = api_backend.zaehler_lesen(db)
    assert z["geschaetzt"] == 1 and z["aufrufe"] == 1 and z["mikro_usd"] > 0
    vorher = z["mikro_usd"]
    api_backend.pause_aufheben()
    api_backend.transport_setzen(FakeTransport(urllib.error.URLError(TimeoutError("timed out"))))
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Frage")
    assert info.value.code == "zeitueberschreitung"
    assert api_backend.zaehler_lesen(db)["mikro_usd"] == vorher, "Beim Verbinden wurde nichts gesendet"


def test_drei_bezahlte_fehlschlaege_in_folge_lassen_den_weg_ruhen(db, schluessel):
    """Eine leere Antwort ist ein Fehler dieser Eingabe. Drei in Folge sind ein Fehler des Weges (Sperrseite eines Proxys
    mit Status 200, geaendertes Antwortformat): jede weitere Stelle wuerde dasselbe bezahlen und wegwerfen."""
    t = FakeTransport(antwort(text="", ein=100, aus=1))
    einsatzbereit(db, t)
    for _ in range(2):
        with pytest.raises(ApiFehler) as info:
            api_backend.senden(db, "match_job_to_skills", "Frage")
        assert info.value.code == "antwort_leer"
    assert api_backend.pause_aktiv() is None, "Zwei sind noch ein Fehler dieser Eingaben"
    api_backend.antwort_brauchbar()  # eine brauchbare Antwort dazwischen: die Serie beginnt von vorn
    for _ in range(2):
        with pytest.raises(ApiFehler):
            api_backend.senden(db, "match_job_to_skills", "Frage")
    assert api_backend.pause_aktiv() is None
    with pytest.raises(ApiFehler):
        api_backend.senden(db, "match_job_to_skills", "Frage")
    pause = api_backend.pause_aktiv()
    assert pause and pause["code"] == "wiederholt_unbrauchbar" and t.anzahl == 5
    z = api_backend.zustand(db, "match_job_to_skills")
    assert not z.erlaubt and z.grund == "wiederholt_unbrauchbar"
    assert api_backend.zaehler_lesen(db)["aufrufe"] == 5, "Jeder dieser Aufrufe war bezahlt"


def test_ein_parser_der_dreimal_hintereinander_scheitert_laesst_den_weg_ruhen(db, schluessel, monkeypatch):
    from bewerbungs_assistent.services import llm_service
    echt_parser = llm_service._RESPONSE_PARSERS[TaskKind.MATCH_JOB_TO_SKILLS]
    modus = {"kaputt": True}

    def parser(text):
        if modus["kaputt"]:
            raise ValueError("kein Urteil")
        return echt_parser(text)

    monkeypatch.setitem(llm_service._RESPONSE_PARSERS, TaskKind.MATCH_JOB_TO_SKILLS, parser)
    t = FakeTransport(antwort())
    einsatzbereit(db, t)
    svc = dienst(db)

    def lauf():
        return svc.run(TaskKind.MATCH_JOB_TO_SKILLS, PAYLOAD_MATCH)

    for _ in range(2):
        r = lauf()
        assert r.backend != Backend.API and r.metrics["api_abgebrochen"] == "unerwartet"
    assert api_backend.pause_aktiv() is None, "Zwei sind noch ein Fehler dieser Eingaben"
    modus["kaputt"] = False
    assert lauf().backend == Backend.API, "Ein brauchbares Urteil beendet die Serie"
    modus["kaputt"] = True
    for _ in range(2):
        lauf()
    assert api_backend.pause_aktiv() is None, "Die Serie begann nach dem brauchbaren Urteil von vorn"
    lauf()
    pause = api_backend.pause_aktiv()
    assert pause and pause["code"] == "wiederholt_unbrauchbar" and t.anzahl == 6
    r = lauf()
    assert t.anzahl == 6, "Danach ruht der Weg: keine siebte Anfrage"
    assert r.metrics["api_ausgelassen"] == "wiederholt_unbrauchbar"


@pytest.mark.parametrize("wert", ["sk-ant-api03-abc“def", "sk-ant-api03-ab\ncd", "sk-ant-api03 ab", "sk-ant-api03-äöü"])
def test_ein_schluessel_mit_sonderzeichen_wird_benannt_und_nie_gesendet(db, monkeypatch, wert):
    """Anfuehrungszeichen aus dem Textverarbeiter oder ein Zeilenumbruch in der Mitte scheitern im Kopf der Anfrage; das
    wuerde als "kein Netz" gemeldet, und die Ausnahme der HTTP-Schicht trueg den ganzen Schluessel."""
    monkeypatch.setattr(api_backend, "_schluessel", lambda: wert)
    t = FakeTransport(antwort())
    einsatzbereit(db, t)
    with pytest.raises(ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Frage")
    assert info.value.code == "schluessel_ungueltig" and t.anzahl == 0
    assert "Zeichen" in info.value.text and wert not in info.value.text
    assert info.value.__context__ is None
    assert api_backend.pause_aktiv()["code"] == "schluessel_ungueltig"


def test_unplausible_tokenangaben_zaehlen_als_fehlend_und_der_schlimmste_fall_wird_gebucht(db, schluessel):
    t = FakeTransport(antwort(ein=2 ** 62, aus=5))
    einsatzbereit(db, t)
    a = api_backend.senden(db, "match_job_to_skills", "Frage")
    z = api_backend.zaehler_lesen(db)
    assert a.geschaetzt and z["geschaetzt"] == 1 and z["mikro_usd"] == a.kosten_mikro > 0
    assert z["eingabe_tokens"] < 100_000, "Die falsche Angabe steht nicht in den Summen"


def test_ein_zaehler_der_als_gleitkommazahl_gelesen_wird_gilt_nicht_als_null(db, schluessel):
    """SQLite macht aus einer Summe ueber 2^63 eine Gleitkommazahl; als "nichts verbraucht" gelesen, stuende das Budget wieder offen."""
    db.set_setting(api_backend.Z_KOSTEN, 9.2e18)
    assert api_backend.zaehler_lesen(db)["mikro_usd"] == int(9.2e18)
    freigeben(db, "match_job_to_skills")
    z = api_backend.zustand(db, "match_job_to_skills")
    assert not z.erlaubt and z.grund == "budget_erreicht"


def test_die_schluesselprobe_beachtet_den_ki_hauptschalter(db, schluessel):
    """Auch die Probe ist eine Anfrage an Anthropic (ohne Angaben aus dem Profil, aber eine Anfrage)."""
    db.set_ki_features(master=False)
    t = FakeTransport(antwort("ok"))
    erg = api_backend.schluessel_pruefen(db, transport=t)
    assert erg["ergebnis"] == "nicht_geprueft" and erg["code"] == "ki_schalter_aus" and t.anzahl == 0
    assert "Hauptschalter" in erg["text"]
    db.set_ki_features(master=True)
    assert api_backend.schluessel_pruefen(db, transport=t)["ergebnis"] == "gueltig" and t.anzahl == 1
