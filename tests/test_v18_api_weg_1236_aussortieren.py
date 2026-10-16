"""#1236 Stufe 2 -- die beiden Aufgaben, die ueber die API laufen koennen, in ihren Werkzeugen.

* `stellen_auto_aussortieren` (`services/auto_aussortierung.aussortieren`): braucht ohne API-Weg Ollama; mit freigegebenem,
  nutzbarem API-Weg nicht. Alles andere bleibt, wie es war.
* `stellen_qualitaet_pruefen(mit_ollama_validierung=True)`: dieselbe Validierung, die Antwort kommt aus der API und heisst `api`
  statt `ollama`.

Plus die beiden Funktionen, die der Betrieb und die Messprobe teilen (`profil_kontext`, `gruende_top`): EINE Quelle fuer
"dasselbe", damit die Probe nichts anderes misst als der echte Lauf.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _api_hilfen import FakeTransport, TESTSCHLUESSEL, antwort, fehlerantwort  # noqa: E402

from bewerbungs_assistent.services import api_backend, auto_aussortierung, llm_service  # noqa: E402
from bewerbungs_assistent.services.llm_service import LLMService  # noqa: E402


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None, **_kwargs):
        def decorator(fn):
            self.tools[name or fn.__name__] = fn
            return fn
        return decorator


class OfflineDienst(LLMService):
    def _check_ollama(self):
        self._status.ollama_available = False
        self._status.available_models = []


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database

    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Erika Musterfrau"})
    d.add_position({"company": "Beispiel Maschinenbau GmbH", "title": "Konstruktionsingenieurin",
                    "start_date": "2012-01", "end_date": ""})
    d.add_skill({"name": "Konstruktion", "category": "tech"})
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


@pytest.fixture
def dienst(db, monkeypatch):
    svc = OfflineDienst(db)
    svc._status.user_state = "off"
    svc._status.last_check_at = 9999999999
    monkeypatch.setattr(llm_service, "get_llm_service", lambda _db=None: svc)
    return svc


@pytest.fixture
def schluessel(monkeypatch):
    monkeypatch.setenv(api_backend.ENV_SCHLUESSEL, TESTSCHLUESSEL)


def _stellen(db, n=4):
    text = "Aufgaben: Konstruktion und Auslegung von Baugruppen. Anforderungen: Studium. " * 5
    for i in range(n):
        db.save_jobs([{"hash": f"aus{i}", "title": f"Zeichner {i}" if i % 2 else f"Konstrukteur {i}",
                       "company": f"Beispiel AG {i}", "url": f"https://example.com/aus/{i}", "source": "manuell",
                       "description": text, "score": 10 - i}])


def _nach_titel(aufruf):
    prompt = aufruf["body"]["messages"][0]["content"]
    return antwort("PASST_NICHT | Zeichner ist eine Stufe zu klein." if "Titel: Zeichner" in prompt else "PASST | passt zum Profil.")


def freigeben(db, *aufgaben):
    erg = api_backend.einstellungen_setzen(db, aufgaben=list(aufgaben), budget_usd=1, bestaetigt=True)
    assert erg["status"] == "gespeichert", erg


# ============================================================ stellen_auto_aussortieren

def test_ohne_freigabe_braucht_der_lauf_weiter_ollama_auch_mit_schluessel(db, dienst, schluessel):
    _stellen(db)
    transport = FakeTransport(entscheider=_nach_titel)
    api_backend.transport_setzen(transport)
    erg = auto_aussortierung.aussortieren(db, max_stellen=4)
    assert erg["status"] == "fehler" and erg["fehler"] == "Lokale AI nicht verfügbar." and transport.anzahl == 0
    assert "ki_weg" not in erg and "api" not in erg and "api_hinweis" not in erg, "Die Antwort bleibt, wie sie war"


def test_mit_freigegebenem_api_weg_laeuft_der_lauf_ohne_ollama(db, dienst, schluessel):
    _stellen(db)
    freigeben(db, "match_job_to_skills")
    transport = FakeTransport(entscheider=_nach_titel)
    api_backend.transport_setzen(transport)
    erg = auto_aussortierung.aussortieren(db, max_stellen=4)
    assert erg["status"] == "ok" and erg["geprueft"] == 4 and transport.anzahl == 4
    assert erg["passt_nicht"] == 2 and erg["passt"] == 2
    assert erg["ki_weg"] == "api" and erg["modell"] == "claude-haiku-5-5"
    assert erg["api"]["aufrufe"] == 4 and erg["api"]["modell"] == "claude-haiku-5-5"
    assert erg["api"]["kosten"] == api_backend.usd_text(4 * api_backend.kosten_mikro(
        api_backend.modell_finden("claude-haiku-5-5"), 100, 20))
    zu = db.get_dismissed_jobs()
    assert len(zu) == 2 and all(j["dismissed_by"] == "automatik" and j["dismiss_reason"] == "profil_match_negativ" for j in zu), (
        "Das Urteil ist das der KI, nicht das des Menschen (#1010): auch ueber die API")
    assert all(j["title"].startswith("Zeichner") for j in zu)


def test_ein_trockenlauf_ueber_die_api_aussortiert_nichts(db, dienst, schluessel):
    _stellen(db)
    freigeben(db, "match_job_to_skills")
    api_backend.transport_setzen(FakeTransport(entscheider=_nach_titel))
    erg = auto_aussortierung.aussortieren(db, max_stellen=4, dry_run=True)
    assert erg["status"] == "ok" and erg["passt_nicht"] == 2 and db.get_dismissed_jobs() == []


def test_die_firma_der_gepruefte_stelle_geht_mit_die_namen_der_beispiele_nicht(db, dienst, schluessel):
    _stellen(db, 2)
    db.save_jobs([{"hash": "frueher", "title": "Praktikant Zeichnen", "company": "Alt Beispiel GmbH",
                   "url": "https://example.com/frueher", "source": "manuell", "description": "Text. " * 30, "score": 1}])
    db.dismiss_job("frueher", "zu_junior")
    freigeben(db, "match_job_to_skills")
    transport = FakeTransport(antwort())
    api_backend.transport_setzen(transport)
    auto_aussortierung.aussortieren(db, max_stellen=2, dry_run=True)
    body = transport.aufrufe[0]["roh"].decode("utf-8")
    assert "Alt Beispiel GmbH" not in body, "Die Firma einer FRUEHER aussortierten Stelle verlaesst den Rechner nicht"
    assert "[Firma]" in body and "Praktikant Zeichnen" in body
    assert "Firma: Beispiel AG" in body, "Die Firma der gepruefte Stelle steht in der Feldliste"


def test_faellt_die_api_aus_und_ist_ollama_nicht_da_steht_der_grund_im_ergebnis(db, dienst, schluessel):
    _stellen(db)
    freigeben(db, "match_job_to_skills")
    transport = FakeTransport(fehlerantwort(402, "billing_error", "Billing"))
    api_backend.transport_setzen(transport)
    erg = auto_aussortierung.aussortieren(db, max_stellen=4)
    assert erg["status"] == "ok" and erg["errors_count"] == 4 and erg["geprueft"] == 4
    assert erg["ki_weg"] == "keiner" and "Guthaben" in erg["api_hinweis"]
    assert transport.anzahl == 1, "Nach einem harten Fehler ruht der Weg: nicht jede Stelle fragt erneut"
    assert "API-Weg:" in erg["errors"][0]["error"] and "api" not in erg
    assert db.get_dismissed_jobs() == []


def test_ein_gesperrter_ki_bereich_macht_den_lauf_wieder_zum_ollama_lauf(db, dienst, schluessel):
    _stellen(db)
    freigeben(db, "match_job_to_skills")
    db.set_ki_features(master=False)
    transport = FakeTransport(entscheider=_nach_titel)
    api_backend.transport_setzen(transport)
    erg = auto_aussortierung.aussortieren(db, max_stellen=4)
    assert erg["status"] == "fehler" and erg["fehler"] == "Lokale AI nicht verfügbar." and transport.anzahl == 0


def test_das_budget_stoppt_den_lauf_und_der_rest_kommt_als_fehler_mit_grund(db, dienst, schluessel):
    _stellen(db)
    freigeben(db, "match_job_to_skills")
    api_backend.einstellungen_setzen(db, budget_usd="0.01")
    transport = FakeTransport(antwort(ein=90_000, aus=1_800))  # 9.900 Mikro-Dollar: der zweite Aufruf passt nicht mehr
    api_backend.transport_setzen(transport)
    erg = auto_aussortierung.aussortieren(db, max_stellen=4, dry_run=True)
    assert transport.anzahl == 1
    assert erg["api"]["aufrufe"] == 1 and erg["ki_weg"] == "api"
    assert erg["errors_count"] == 3 and "Budget" in erg["api_hinweis"]


def test_das_werkzeug_reicht_den_api_weg_durch(db, dienst, schluessel):
    _stellen(db)
    freigeben(db, "match_job_to_skills")
    api_backend.transport_setzen(FakeTransport(entscheider=_nach_titel))
    mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs
    jobs.register(mcp, db, logging.getLogger("test"))
    erg = mcp.tools["stellen_auto_aussortieren"](max_stellen=4, dry_run=True)
    assert erg["ki_weg"] == "api" and erg["geprueft"] == 4


# ============================================================ stellen_qualitaet_pruefen

def _ohne_url_stelle(db):
    db.save_jobs([{"hash": "qual1", "title": "Konstrukteur", "company": "Beispiel AG", "url": "", "source": "manuell",
                   "_manual_entry": True, "description": "kurz", "score": 3}])


def test_die_validierung_laeuft_ueber_die_api_und_heisst_api(db, dienst, schluessel):
    _ohne_url_stelle(db)
    freigeben(db, "validate_job_quality")
    transport = FakeTransport(antwort('{"vollstaendig": false, "score": 2, "claude_action": "nachladen", '
                                      '"begruendung": "zu kurz"}', ein=300, aus=40))
    api_backend.transport_setzen(transport)
    mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs
    jobs.register(mcp, db, logging.getLogger("test"))
    erg = mcp.tools["stellen_qualitaet_pruefen"](max_stellen=5, nur_problematische=False, mit_ollama_validierung=True)
    assert transport.anzahl == 1
    detail = erg["details"][0]
    assert detail["api"]["claude_action"] == "nachladen" and "ollama" not in detail, "Eine API-Antwort steht nicht als lokale KI da"
    assert "ollama_action_nachladen" in detail["kategorien"]
    assert api_backend.zaehler_lesen(db)["aufrufe"] == 1
    # und nur die Anzeige geht hinaus
    body = transport.aufrufe[0]["roh"].decode("utf-8")
    assert "Erika Musterfrau" not in body and "Konstruktionsingenieurin" not in body


def test_ohne_freigabe_bleibt_die_validierung_beim_bisherigen_weg(db, dienst, schluessel):
    _ohne_url_stelle(db)
    transport = FakeTransport(antwort())
    api_backend.transport_setzen(transport)
    mcp = FakeMCP()
    from bewerbungs_assistent.tools import jobs
    jobs.register(mcp, db, logging.getLogger("test"))
    erg = mcp.tools["stellen_qualitaet_pruefen"](max_stellen=5, nur_problematische=False, mit_ollama_validierung=True)
    assert transport.anzahl == 0
    assert "api" not in erg["details"][0] and "ollama" not in erg["details"][0], "Kein Ollama, keine API: wie bisher keine Antwort"


# ============================================================ Die geteilten Funktionen

@pytest.mark.parametrize("positionen,erwartet", [
    ([], "Berufseinsteiger / Berufsanfänger"),
    ([{"title": "A", "start_date": "2025-01", "end_date": "2025-06"}], "Berufseinsteiger / Berufsanfänger"),
    ([{"title": "A", "start_date": "2024-01", "end_date": "2026-01"}], "Junior (2 Jahre Erfahrung)"),
    ([{"title": "A", "start_date": "2019-01", "end_date": "2024-01"}], "Mid-Level (5 Jahre Erfahrung)"),
    ([{"title": "A", "start_date": "2012-01", "end_date": ""}], "Senior (14 Jahre Erfahrung)"),
    ([{"title": "A", "start_date": "2000-01", "end_date": "2005-01"}, {"title": "B", "start_date": "2010-01", "end_date": "2015-01"}],
     "Senior (10 Jahre Erfahrung)"),
    ([{"title": "A", "start_date": "kaputt", "end_date": "x"}], "Berufseinsteiger / Berufsanfänger"),
])
def test_profil_kontext_rechnet_die_stufe_wie_bisher(positionen, erwartet):
    k = auto_aussortierung.profil_kontext({"positions": positionen, "skills": []})
    assert k["profile_seniority"] == erwartet
    assert k["profile_position"] == (positionen[0]["title"] if positionen else "")


def test_profil_kontext_nimmt_die_ersten_fuenfzehn_skills_und_vertraegt_leere_profile():
    k = auto_aussortierung.profil_kontext({"skills": [{"name": f"S{i}"} for i in range(30)]})
    assert k["profile_skills"] == [f"S{i}" for i in range(15)]
    assert auto_aussortierung.profil_kontext({})["profile_skills"] == []
    assert auto_aussortierung.profil_kontext(None)["profile_position"] == ""


def test_der_lauf_und_die_probe_nehmen_dieselben_funktionen():
    quelle_lauf = (Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent" / "services" / "auto_aussortierung.py"
                   ).read_text(encoding="utf-8-sig")
    quelle_probe = (Path(__file__).resolve().parents[1] / "scripts" / "api_probe.py").read_text(encoding="utf-8-sig")
    assert "kontext = profil_kontext(profile)" in quelle_lauf and "dismiss_reasons_top = gruende_top(db)" in quelle_lauf
    assert "profil_kontext" in quelle_probe and "gruende_top" in quelle_probe
    assert quelle_probe.count("Senior (") == 0, "Die Probe rechnet die Karrierestufe nicht ein zweites Mal"


def test_gruende_top_nennt_drei_gruende_mit_anzahl_und_ist_bei_fehlern_leer(db):
    for i, grund in enumerate(["zu_junior"] * 3 + ["zeitarbeit"] * 2 + ["befristet", "zu_senior"]):
        db.save_jobs([{"hash": f"g{i}", "title": f"T{i}", "company": "Beispiel AG", "url": f"https://example.com/g{i}",
                       "source": "manuell", "description": "Text. " * 30, "score": 1}])
        db.dismiss_job(f"g{i}", grund)
    top = auto_aussortierung.gruende_top(db)
    assert top[0] == {"reason": "zu_junior", "count": 3} and top[1] == {"reason": "zeitarbeit", "count": 2} and len(top) == 3

    class Kaputt:
        def connect(self):
            raise RuntimeError("weg")

    assert auto_aussortierung.gruende_top(Kaputt()) == []
