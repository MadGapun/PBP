"""#1236 Stufe 1 -- der Baustein `services/api_backend.py`: Modellliste und Preise, Einstellungen, Zustand.

Der API-Weg ist ein optionaler Weg der KI-Schicht: Anthropic-API mit eigenem Schluessel, je Aufgabe einzeln
freigegeben, Vorgabe AUS. Diese Datei prueft, was ohne Netz geprueft werden kann: die Konfiguration (Modelle,
Preise), die Rechnung, die Einstellungen (Setzer UND Leser) und die eine Frage, ob eine Aufgabe JETZT ueber die API
laufen darf. Die Anfrage selbst und ihre Fehler stehen in `test_v18_api_weg_1236_aufruf.py`.
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from _api_hilfen import FakeTransport, TESTSCHLUESSEL, antwort  # noqa: E402

from bewerbungs_assistent.services import api_backend  # noqa: E402
from bewerbungs_assistent.services.llm_service import (  # noqa: E402
    _PROMPT_BUILDERS, _RESPONSE_PARSERS, ROUTING_TABLE, Backend, LLMService, TaskKind,
)


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


def freigeben(db, *aufgaben, budget_usd="1", modelle=None):
    erg = api_backend.einstellungen_setzen(db, aufgaben=list(aufgaben), budget_usd=budget_usd, modelle=modelle,
                                           bestaetigt=True)
    assert erg["status"] == "gespeichert", erg
    return erg


def dienst(db, ollama=False):
    """Ein LLMService mit festem Status: nie ein Blick auf ein echtes Ollama auf diesem Rechner."""
    svc = LLMService(db)
    svc._status.ollama_available = ollama
    svc._status.available_models = ["modell:1b"] if ollama else []
    svc._status.user_state = "active" if ollama else "off"
    svc._status.selected_model = "modell:1b" if ollama else None
    svc._status.last_check_at = 9999999999  # Zwischenspeicher: kein HTTP-Aufruf
    return svc


# ============================================================ Modelle und Preise

def test_die_modellliste_ist_konfiguration_und_hat_preise():
    kat = api_backend.katalog()
    assert kat["modelle"], "Die Modellliste ist leer oder unlesbar"
    assert kat["stand"] and kat["quelle"].startswith("https://")
    for m in kat["modelle"]:
        assert m.id and m.name
        assert isinstance(m.eingabe_usd_je_mtok, Decimal) and isinstance(m.ausgabe_usd_je_mtok, Decimal)


def test_die_vorgabe_ist_das_guenstigste_modell_mit_bekanntem_preis():
    modelle = [m for m in api_backend.katalog()["modelle"] if m.preis_bekannt]
    guenstigstes = min(modelle, key=lambda m: m.eingabe_usd_je_mtok + m.ausgabe_usd_je_mtok)
    assert api_backend.vorgabe_modell().id == guenstigstes.id
    assert api_backend.vorgabe_modell().id == "claude-haiku-5-5"


def test_kosten_sind_exakt_und_werden_aufgerundet():
    haiku = api_backend.modell_finden("claude-haiku-5-5")
    # 1 US-Dollar je Million Tokens = 1 Mikro-Dollar je Token: 1000 * 0,10 + 200 * 0,50
    assert api_backend.kosten_mikro(haiku, 1000, 200) == 200
    assert api_backend.kosten_mikro(haiku, 3, 0) == 1, "0,3 Mikro-Dollar werden aufgerundet, nicht verschluckt"
    assert api_backend.kosten_mikro(haiku, 0, 0) == 0
    sonnet = api_backend.modell_finden("claude-sonnet-5-5")
    assert api_backend.kosten_mikro(sonnet, 1000, 200) == 2000 + 2000


def test_ein_modell_ohne_preis_hat_keine_kosten_und_ist_nicht_die_vorgabe(monkeypatch, tmp_path):
    datei = tmp_path / "modelle.json"
    datei.write_text('{"stand":"x","quelle":"https://example.org","modelle":['
                     '{"id":"neu-ohne-preis","name":"Neu","eingabe_usd_je_mtok":null,"ausgabe_usd_je_mtok":null},'
                     '{"id":"mit-preis","name":"Mit","eingabe_usd_je_mtok":"1","ausgabe_usd_je_mtok":"2"}]}',
                     encoding="utf-8")
    monkeypatch.setattr(api_backend, "_KATALOG_PFAD", datei)
    api_backend.katalog(neu_laden=True)
    ohne = api_backend.modell_finden("neu-ohne-preis")
    assert not ohne.preis_bekannt
    assert api_backend.kosten_mikro(ohne, 100, 100) is None, "Unbekannt ist ein eigener Zustand, keine Null"
    assert api_backend.vorgabe_modell().id == "mit-preis"


def test_eine_unlesbare_modellliste_heisst_leer_und_kippt_nichts(monkeypatch, tmp_path):
    datei = tmp_path / "kaputt.json"
    datei.write_text("{nicht json", encoding="utf-8")
    monkeypatch.setattr(api_backend, "_KATALOG_PFAD", datei)
    assert api_backend.katalog(neu_laden=True)["modelle"] == []
    assert api_backend.vorgabe_modell() is None


def test_ein_preis_der_kein_betrag_ist_gilt_als_unbekannt(monkeypatch, tmp_path):
    datei = tmp_path / "preise.json"
    datei.write_text('{"modelle":[{"id":"a","name":"A","eingabe_usd_je_mtok":"abc","ausgabe_usd_je_mtok":"-1"},'
                     '{"id":"b","name":"B","eingabe_usd_je_mtok":true,"ausgabe_usd_je_mtok":"NaN"}]}', encoding="utf-8")
    monkeypatch.setattr(api_backend, "_KATALOG_PFAD", datei)
    api_backend.katalog(neu_laden=True)
    assert not api_backend.modell_finden("a").preis_bekannt
    assert not api_backend.modell_finden("b").preis_bekannt


# ============================================================ Die Aufgaben und ihre Feldliste

def test_nur_die_ersten_beiden_aufgaben_laufen_ueber_die_api():
    """Entscheidung zu Frage 3: Anzeigentext und Profilabgleich; Mails, Kontakte und Stichworte nicht (Namen Dritter)."""
    assert set(api_backend.AUFGABEN) == {"match_job_to_skills", "validate_job_quality"}


def test_jede_api_aufgabe_hat_baustein_parser_und_einen_ki_bereich():
    for kennung, a in api_backend.AUFGABEN.items():
        kind = TaskKind(kennung)
        assert kind in _PROMPT_BUILDERS and kind in _RESPONSE_PARSERS
        assert a.ki_bereich in __import__("bewerbungs_assistent.database", fromlist=["Database"]).Database.KI_FEATURES
        assert a.max_tokens > 0 and a.felder and a.nicht_gesendet


def test_die_api_steht_nicht_in_der_routing_tabelle():
    """Der API-Weg ist eine Freigabe, keine Voreinstellung: die Tabelle bleibt, wie sie war."""
    for kind, kette in ROUTING_TABLE.items():
        assert Backend.API not in kette, kind


def test_jedes_feld_der_feldliste_erreicht_den_prompt_und_nichts_anderes():
    """Die Liste, die der Mensch VOR der Freigabe sieht, ist die Wirklichkeit: jedes genannte Feld steht im
    Prompt (kein Phantomfeld), und ein Feld ausserhalb der Liste kommt nie hinein."""
    for kennung, a in api_backend.AUFGABEN.items():
        payload = {f.schluessel: f"MARKE-{f.schluessel}" for f in a.felder}
        marke = {f.schluessel: f"MARKE-{f.schluessel}" for f in a.felder}
        # Listen- und Beispielfelder brauchen ihre Form
        if "profile_skills" in payload:
            payload["profile_skills"] = ["MARKE-profile_skills"]
        if "dismiss_reasons_top" in payload:
            # Ein Grund geht nur als Kennung hinaus (Kleinbuchstaben und Unterstriche): die Marke ist eine
            marke["dismiss_reasons_top"] = "marke_dismiss_reasons_top"
            payload["dismiss_reasons_top"] = [{"reason": marke["dismiss_reasons_top"], "count": 3}]
        if "recent_dismissals" in payload:
            payload["recent_dismissals"] = [{"title": "MARKE-recent_dismissals", "company": "Beispiel AG",
                                             "dismiss_reason": "zu_junior"}]
        payload["AUSSERHALB"] = "MARKE-ausserhalb-der-feldliste"
        sicher = api_backend.nutzlast_fuer_api(kennung, payload)
        prompt = _PROMPT_BUILDERS[TaskKind(kennung)](sicher)
        for f in a.felder:
            assert marke[f.schluessel] in prompt, f"{kennung}: das Feld {f.schluessel} erreicht den Prompt nicht"
        assert "MARKE-ausserhalb" not in prompt
        assert "AUSSERHALB" not in sicher


def test_die_firmennamen_der_beispiele_werden_geschwaerzt_der_titel_bleibt():
    sicher = api_backend.nutzlast_fuer_api("match_job_to_skills", {
        "recent_dismissals": [
            {"title": "Berater bei Muster GmbH (m/w/d)", "company": "Muster GmbH", "dismiss_reason": "zu_junior"},
            {"title": "SAP Berater", "company": "", "dismiss_reason": "falsches_system"},
        ]})
    text = str(sicher["recent_dismissals"])
    assert "Muster" not in text, "Der Firmenname hat den Rechner verlassen"
    assert api_backend.PLATZHALTER_FIRMA in text
    assert sicher["recent_dismissals"][0]["title"] == f"Berater bei {api_backend.PLATZHALTER_FIRMA} (m/w/d)"
    assert sicher["recent_dismissals"][1]["title"] == "SAP Berater"
    assert sicher["recent_dismissals"][1]["company"] == ""
    assert sicher["recent_dismissals"][0]["dismiss_reason"] == "zu_junior"


def test_ein_kurzer_firmenname_bleibt_im_titel_stehen_ein_dreibuchstabiger_nicht():
    """Ab drei Zeichen nimmt PBP den Firmennamen aus dem Titel. Ein Name aus ein oder zwei Buchstaben ist meist ein
    Wort des Titels („IT“, „KI“); schwaerzte man es, machte das aus dem Beispiel Unsinn. Das Feld „Firma“ wird
    in jedem Fall ersetzt. Beide Seiten der Grenze, denn ein Pruefer, der nur eine kennt, haelt die andere nicht."""
    sicher = api_backend.nutzlast_fuer_api("match_job_to_skills", {
        "recent_dismissals": [
            {"title": "Data Engineer", "company": "AG", "dismiss_reason": "x"},
            {"title": "Leiter IT Betrieb", "company": "IT", "dismiss_reason": "x"},
            {"title": "SAP Berater (m/w/d)", "company": "SAP", "dismiss_reason": "x"},
        ]})
    beispiele = sicher["recent_dismissals"]
    assert beispiele[0]["title"] == "Data Engineer"
    assert beispiele[1]["title"] == "Leiter IT Betrieb", "zwei Buchstaben sind ein Wort des Titels, kein Firmenname"
    assert beispiele[2]["title"] == f"{api_backend.PLATZHALTER_FIRMA} Berater (m/w/d)", \
        "drei Buchstaben gehoeren schon zum Namen und duerfen den Rechner nicht verlassen"
    assert all(e["company"] == api_backend.PLATZHALTER_FIRMA for e in beispiele)


@pytest.mark.parametrize("firma, titel, erwartet", [
    ("Musterfirma AG", "Berater bei Musterfirma (m/w/d)", f"Berater bei {api_backend.PLATZHALTER_FIRMA} (m/w/d)"),
    ("Musterfirma AG", "Musterfirma AG sucht Berater", f"{api_backend.PLATZHALTER_FIRMA} sucht Berater"),
    ("Muster GmbH &amp; Co. KG", "Ingenieur bei Muster", f"Ingenieur bei {api_backend.PLATZHALTER_FIRMA}"),
    ("Müller &amp; Söhne GmbH", "Monteur Müller & Söhne", f"Monteur {api_backend.PLATZHALTER_FIRMA}"),
    ("Beispiel Software", "Beispiel Softwareentwickler", "Beispiel Softwareentwickler"),  # ganzes Wort, kein Teil eines Worts
    ("ZF", "Entwickler bei ZF", "Entwickler bei ZF"),  # zwei Buchstaben: meist ein Wort des Titels
    ("GmbH", "Leiter GmbH-Recht", "Leiter GmbH-Recht"),  # nur eine Rechtsform ist kein Name
])
def test_der_firmenkern_ohne_rechtsform_wird_auch_als_wort_im_titel_ersetzt(firma, titel, erwartet):
    """Eine Anzeige schreibt "Berater bei Musterfirma", die Datenbank fuehrt "Musterfirma AG": nur der volle Name haette den Titel
    unveraendert gelassen und die Firma einer frueher aussortierten Stelle mitgeschickt."""
    sicher = api_backend.nutzlast_fuer_api("match_job_to_skills", {
        "recent_dismissals": [{"title": titel, "company": firma, "dismiss_reason": "zu_junior"}]})
    assert sicher["recent_dismissals"][0]["title"] == erwartet


def test_ein_aussortier_grund_geht_nur_als_kennung_hinaus_eigener_text_wird_sonstiges():
    """Freitext ("Firma Muster ist zu klein") kann einen Namen tragen, und die API braucht ihn nicht: die Standardgruende
    tragen das Lernen. Die App selbst macht aus Unbekanntem ebenfalls `sonstiges`."""
    sicher = api_backend.nutzlast_fuer_api("match_job_to_skills", {
        "recent_dismissals": [
            {"title": "A", "company": "", "dismiss_reason": "zu_junior"},
            {"title": "B", "company": "", "dismiss_reason": "Firma Muster ist zu klein"},
            {"title": "C", "company": "", "dismiss_reason": "Gehalt-zu_niedrig"},
            {"title": "D", "company": "", "dismiss_reason": ""},
            {"title": "E", "company": "", "dismiss_reason": None},
        ],
        "dismiss_reasons_top": [
            {"reason": "zu_junior", "count": 4},
            {"reason": "Firma Muster ist zu klein", "count": 2},
            {"reason": "Noch ein Satz mit Namen", "count": 1},
            {"reason": "", "count": 9},
        ]})
    assert [e["dismiss_reason"] for e in sicher["recent_dismissals"]] == ["zu_junior", "sonstiges", "sonstiges", "", ""]
    assert sicher["dismiss_reasons_top"] == [{"reason": "zu_junior", "count": 4}, {"reason": "sonstiges", "count": 3}]
    assert "Muster" not in str(sicher)


def test_eine_unbekannte_aufgabe_hat_keine_nutzlast():
    with pytest.raises(api_backend.ApiFehler) as info:
        api_backend.nutzlast_fuer_api("extract_contacts", {"text": "Name Dritter"})
    assert info.value.code == "aufgabe_nicht_vorgesehen"


# ============================================================ Einstellungen: Setzer und Leser

def test_vorgabe_ist_alles_aus(db, schluessel):
    assert api_backend.freigaben_lesen(db) == {}
    assert api_backend.budget_lesen(db) is None
    z = api_backend.zustand(db, "match_job_to_skills")
    assert (z.freigegeben, z.erlaubt, z.grund) == (False, False, "nicht_freigegeben")


def test_freigeben_braucht_einen_schluessel(db):
    erg = api_backend.einstellungen_setzen(db, aufgaben=["match_job_to_skills"], bestaetigt=True)
    assert erg["status"] == "fehler" and erg["code"] == "kein_schluessel"
    assert api_backend.freigaben_lesen(db) == {}


def test_freigeben_zeigt_erst_die_feldliste_und_speichert_nichts(db, schluessel):
    erg = api_backend.einstellungen_setzen(db, aufgaben=["match_job_to_skills"], budget_usd="2")
    assert erg["status"] == "bestaetigung_noetig"
    feld = erg["aufgaben"][0]
    assert feld["id"] == "match_job_to_skills" and feld["gesendet"] and feld["nicht_gesendet"]
    assert "verlassen" in erg["text"] and "Anthropic" in erg["text"]
    assert api_backend.freigaben_lesen(db) == {}, "Ohne Bestaetigung darf nichts gespeichert sein"
    assert api_backend.budget_lesen(db) is None, "Auch das Budget wartet auf die Bestaetigung"


def test_nach_der_bestaetigung_ist_die_aufgabe_freigegeben_und_der_leser_sieht_es(db, schluessel):
    freigeben(db, "match_job_to_skills", budget_usd="2,50")
    assert set(api_backend.freigaben_lesen(db)) == {"match_job_to_skills"}
    assert api_backend.budget_lesen(db) == 2_500_000
    z = api_backend.zustand(db, "match_job_to_skills")
    assert z.erlaubt and z.modell == "claude-haiku-5-5", "Vorgabe ist das guenstigste Modell"
    assert not api_backend.zustand(db, "validate_job_quality").freigegeben, "Jede Aufgabe einzeln"


def test_wegnehmen_wirkt_sofort_und_braucht_keine_bestaetigung(db, schluessel):
    freigeben(db, "match_job_to_skills", "validate_job_quality")
    erg = api_backend.einstellungen_setzen(db, aufgaben=["validate_job_quality"])
    assert erg["status"] == "gespeichert" and erg["gesperrt"] == ["match_job_to_skills"]
    assert set(api_backend.freigaben_lesen(db)) == {"validate_job_quality"}
    api_backend.einstellungen_setzen(db, aufgaben=[])
    assert api_backend.freigaben_lesen(db) == {}


def test_die_freigabe_gehoert_zum_profil(db, schluessel):
    freigeben(db, "match_job_to_skills")
    zweites = db.create_profile("Zweites Profil")
    db.switch_profile(zweites)
    assert api_backend.freigaben_lesen(db) == {}, "Ein anderes Profil hat nichts freigegeben"
    assert api_backend.budget_lesen(db) == 1_000_000, "Das Budget gilt je Schluessel, nicht je Profil"


@pytest.mark.parametrize("aufgaben", ["extract_contacts", ["extract_contacts"], ["classify_email"], [""], "x"])
def test_unbekannte_aufgaben_werden_abgewiesen(db, schluessel, aufgaben):
    erg = api_backend.einstellungen_setzen(db, aufgaben=aufgaben, bestaetigt=True)
    assert erg["status"] == "fehler" and erg["erlaubt"] == list(api_backend.AUFGABEN)
    assert api_backend.freigaben_lesen(db) == {}


@pytest.mark.parametrize("budget", ["abc", "-1", -5, "1e999", float("nan"), float("inf"), True, 10_001, "10001"])
def test_ein_ungueltiges_budget_wird_abgewiesen_und_nichts_gespeichert(db, schluessel, budget):
    freigeben(db, "match_job_to_skills", budget_usd="3")
    erg = api_backend.einstellungen_setzen(db, budget_usd=budget)
    assert erg["status"] == "fehler", erg
    assert api_backend.budget_lesen(db) == 3_000_000


@pytest.mark.parametrize("eingabe,mikro", [("5", 5_000_000), ("5,50", 5_500_000), (0.25, 250_000), ("0,004", 0),
                                           ("1234.56", 1_234_560_000)])
def test_das_budget_wird_auf_cent_gerundet_gespeichert(db, schluessel, eingabe, mikro):
    api_backend.einstellungen_setzen(db, budget_usd=eingabe)
    assert api_backend._global(db, api_backend.S_BUDGET) == mikro


def test_budget_null_heisst_nichts_darf_ausgegeben_werden(db, schluessel):
    freigeben(db, "match_job_to_skills")
    api_backend.einstellungen_setzen(db, budget_usd=0)
    assert api_backend.budget_lesen(db) is None
    assert api_backend.zustand(db, "match_job_to_skills").grund == "kein_budget"


def test_modell_waehlbar_nur_aus_der_liste_und_nur_mit_preis(db, schluessel):
    freigeben(db, "match_job_to_skills")
    ok = api_backend.einstellungen_setzen(db, modelle={"match_job_to_skills": "claude-sonnet-5-5"})
    assert ok["status"] == "gespeichert"
    assert api_backend.zustand(db, "match_job_to_skills").modell == "claude-sonnet-5-5"
    unbekannt = api_backend.einstellungen_setzen(db, modelle={"match_job_to_skills": "gibt-es-nicht"})
    assert unbekannt["status"] == "fehler" and "claude-haiku-5-5" in unbekannt["text"]
    assert api_backend.zustand(db, "match_job_to_skills").modell == "claude-sonnet-5-5", "Der alte Wert bleibt"
    zurueck = api_backend.einstellungen_setzen(db, modelle={"match_job_to_skills": None})
    assert zurueck["status"] == "gespeichert"
    assert api_backend.zustand(db, "match_job_to_skills").modell == "claude-haiku-5-5"


def test_ein_modell_braucht_eine_freigegebene_aufgabe(db, schluessel):
    erg = api_backend.einstellungen_setzen(db, modelle={"validate_job_quality": "claude-sonnet-5-5"})
    assert erg["status"] == "fehler"
    assert api_backend.freigaben_lesen(db) == {}


def test_nichts_angegeben_heisst_nichts_geaendert(db, schluessel):
    assert api_backend.einstellungen_setzen(db)["status"] == "unveraendert"


def test_ein_unlesbarer_gespeicherter_wert_gilt_als_nicht_freigegeben(db, schluessel):
    """Im Zweifel der restriktivere Zustand: Muell in der Einstellung ist keine Freigabe."""
    for roh in ("ja", ["match_job_to_skills"], {"match_job_to_skills": "an"}, {"unbekannt": {}}, 5, None):
        db.set_profile_setting(api_backend.S_AUFGABEN, roh)
        assert api_backend.freigaben_lesen(db) == {}, roh
    db.set_setting(api_backend.S_BUDGET, "viel")
    assert api_backend.budget_lesen(db) is None
    db.set_setting(api_backend.S_BUDGET, -5)
    assert api_backend.budget_lesen(db) is None


# ============================================================ Darf die Aufgabe jetzt?

def test_reihenfolge_der_gruende(db, schluessel, monkeypatch):
    freigeben(db, "match_job_to_skills")
    assert api_backend.zustand(db, "match_job_to_skills").erlaubt
    # Budget weg
    api_backend.einstellungen_setzen(db, budget_usd=0)
    assert api_backend.zustand(db, "match_job_to_skills").grund == "kein_budget"
    api_backend.einstellungen_setzen(db, budget_usd=1)
    # Schluessel weg
    monkeypatch.delenv(api_backend.ENV_SCHLUESSEL)
    z = api_backend.zustand(db, "match_job_to_skills")
    assert (z.freigegeben, z.erlaubt, z.grund) == (True, False, "kein_schluessel")
    assert api_backend.ENV_SCHLUESSEL in z.text, "Der Weg hinaus steht im Text"


@pytest.mark.parametrize("schalter,erwartung", [({"master": False}, "Hauptschalter"),
                                                ({"stellenanalyse": False}, "stellenanalyse")])
def test_die_ki_schalter_sperren_auch_den_api_weg(db, schluessel, schalter, erwartung):
    """master=False sperrt alles; der Bereich der Aufgabe sperrt sie. Der Weg hinaus steht im Text."""
    freigeben(db, "match_job_to_skills", "validate_job_quality")
    assert api_backend.zustand(db, "match_job_to_skills").erlaubt
    db.set_ki_features(**schalter)
    for aufgabe in api_backend.AUFGABEN:
        z = api_backend.zustand(db, aufgabe)
        assert not z.erlaubt and z.grund == "ki_schalter_aus", (aufgabe, z)
        assert erwartung in z.text and "Claude (Cloud)" in z.text
        assert dienst(db).select_backend(TaskKind(aufgabe)) != Backend.API
    db.set_ki_features(master=True, stellenanalyse=True)
    assert api_backend.zustand(db, "match_job_to_skills").erlaubt


def test_ein_anderer_ki_bereich_sperrt_diese_aufgaben_nicht(db, schluessel):
    freigeben(db, "match_job_to_skills")
    db.set_ki_features(coaching=False, jobsuche=False, dokumentenanalyse=False)
    assert api_backend.zustand(db, "match_job_to_skills").erlaubt


def test_ein_gespeichertes_modell_das_es_nicht_mehr_gibt_haelt_den_weg_an(db, schluessel):
    freigeben(db, "match_job_to_skills")
    freigaben = api_backend.freigaben_lesen(db)
    freigaben["match_job_to_skills"]["modell"] = "claude-aelter-als-die-liste"
    db.set_profile_setting(api_backend.S_AUFGABEN, freigaben)
    z = api_backend.zustand(db, "match_job_to_skills")
    assert not z.erlaubt and z.grund == "modell_unbekannt"


def test_ein_preisloses_modell_wird_nicht_benutzt(db, schluessel, monkeypatch, tmp_path):
    datei = tmp_path / "modelle.json"
    datei.write_text('{"modelle":[{"id":"claude-haiku-5-5","name":"Haiku","eingabe_usd_je_mtok":null,'
                     '"ausgabe_usd_je_mtok":null}]}', encoding="utf-8")
    monkeypatch.setattr(api_backend, "_KATALOG_PFAD", datei)
    api_backend.katalog(neu_laden=True)
    freigeben_ = api_backend.einstellungen_setzen(db, aufgaben=["match_job_to_skills"], bestaetigt=True)
    assert freigeben_["status"] == "gespeichert"
    z = api_backend.zustand(db, "match_job_to_skills")
    assert not z.erlaubt and z.grund == "preis_unbekannt"
    assert "Budget" in z.text


def test_ein_gewaehltes_modell_dessen_preis_aus_der_liste_fiel_wird_nicht_benutzt(db, schluessel, monkeypatch, tmp_path):
    """Gewaehlt wurde ein Modell MIT Preis (so laesst es `einstellungen_setzen` allein zu). Eine neuere Fassung der
    Liste kennt den Preis nicht mehr: der gespeicherte Wunsch bleibt, aber ohne Preis laesst sich das Budget nicht
    halten, also ruht der Weg. Er weicht nicht still auf ein anderes Modell aus und rechnet nicht mit null."""
    freigeben(db, "match_job_to_skills", modelle={"match_job_to_skills": "claude-sonnet-5-5"})
    assert api_backend.zustand(db, "match_job_to_skills").erlaubt, "Vorbedingung: mit Preis ist der Weg offen"
    datei = tmp_path / "modelle.json"
    datei.write_text('{"modelle":[{"id":"claude-sonnet-5-5","name":"Sonnet","eingabe_usd_je_mtok":null,'
                     '"ausgabe_usd_je_mtok":null},'
                     '{"id":"claude-haiku-5-5","name":"Haiku","eingabe_usd_je_mtok":"0.10","ausgabe_usd_je_mtok":"0.50"}]}',
                     encoding="utf-8")
    monkeypatch.setattr(api_backend, "_KATALOG_PFAD", datei)
    api_backend.katalog(neu_laden=True)
    z = api_backend.zustand(db, "match_job_to_skills")
    assert not z.erlaubt and z.grund == "preis_unbekannt"
    assert z.modell == "claude-sonnet-5-5", "gezeigt wird das gewaehlte Modell, nicht ein anderes"
    assert "Sonnet" in z.text
    t = FakeTransport()
    with pytest.raises(api_backend.ApiFehler) as info:
        api_backend.senden(db, "match_job_to_skills", "Frage", transport=t)
    assert info.value.code == "preis_unbekannt" and t.anzahl == 0, "ohne Preis wird nichts gesendet"


def test_ohne_datenbank_ist_nie_etwas_erlaubt(schluessel):
    assert api_backend.zustand(None, "match_job_to_skills").grund == "nicht_freigegeben"
    assert api_backend.sichtbar(None) is True  # ein Schluessel ist da; die Karte zeigt, dass nichts freigegeben ist
    assert api_backend.freigaben_lesen(None) == {}


# ============================================================ Sichtbarkeit: ohne Schluessel und Einstellung nichts

def test_ohne_schluessel_und_einstellung_gibt_es_nichts_zu_zeigen(db):
    assert api_backend.sichtbar(db) is False
    assert api_backend.uebersicht(db) == {"sichtbar": False, "schluessel_gesetzt": False}
    assert api_backend.datenfluss_zeilen(db) == []


def test_mit_schluessel_ist_der_weg_sichtbar_und_zeigt_den_schluessel_nie(db, schluessel):
    erg = api_backend.uebersicht(db)
    assert erg["sichtbar"] and erg["schluessel_gesetzt"] and erg["variable"] == api_backend.ENV_SCHLUESSEL
    assert schluessel not in str(erg) and schluessel[:12] not in str(erg)
    assert erg["pruefung"]["ergebnis"] == "nicht_geprueft", "Das blosse Vorhandensein ist keine Pruefung"
    assert all(not a["freigegeben"] and not a["bereit"] for a in erg["aufgaben"])
    assert [m["id"] for m in erg["modelle"] if m["vorgabe"]] == ["claude-haiku-5-5"]


def test_eine_freigabe_ohne_schluessel_bleibt_sichtbar_und_sagt_dass_der_weg_ruht(db, monkeypatch):
    monkeypatch.setenv(api_backend.ENV_SCHLUESSEL, TESTSCHLUESSEL)
    freigeben(db, "match_job_to_skills")
    monkeypatch.delenv(api_backend.ENV_SCHLUESSEL)
    erg = api_backend.uebersicht(db)
    assert erg["sichtbar"] and not erg["schluessel_gesetzt"]
    assert any("ruht" in h for h in erg["hinweise"])
    aufgabe = next(a for a in erg["aufgaben"] if a["id"] == "match_job_to_skills")
    assert aufgabe["freigegeben"] and not aufgabe["bereit"] and aufgabe["grund"] == "kein_schluessel"


def test_die_datenschutz_zeilen_nennen_nur_freigegebene_aufgaben(db, schluessel):
    assert api_backend.datenfluss_zeilen(db) == []
    freigeben(db, "validate_job_quality")
    zeilen = api_backend.datenfluss_zeilen(db)
    assert len(zeilen) == 1 and "Anthropic-API" in zeilen[0] and "Anzeigentext" in zeilen[0]
    assert "Berufsbezeichnung" not in zeilen[0], "Diese Aufgabe sendet nichts aus dem Profil"


# ============================================================ Routing im Dienst

def test_ohne_freigabe_geht_nichts_an_die_api_auch_mit_schluessel(db, schluessel):
    transport = FakeTransport()
    api_backend.transport_setzen(transport)
    svc = dienst(db)
    for kind in TaskKind:
        assert svc.select_backend(kind) != Backend.API, kind
    ergebnis = svc.run(TaskKind.MATCH_JOB_TO_SKILLS, {"job_title": "x"})
    assert ergebnis.backend == Backend.CLAUDE and not ergebnis.success
    assert transport.anzahl == 0
    assert not any(k.startswith("api_") for k in ergebnis.metrics), "Im Normalfall bleibt die Metrik, wie sie war"


def test_freigegebene_aufgaben_waehlen_die_api_alle_anderen_nie(db, schluessel):
    freigeben(db, "match_job_to_skills", "validate_job_quality")
    svc = dienst(db, ollama=True)
    for kind in TaskKind:
        erwartet = Backend.API if kind.value in api_backend.AUFGABEN else None
        if erwartet:
            assert svc.select_backend(kind) == Backend.API, kind
        else:
            assert svc.select_backend(kind) != Backend.API, kind
    assert svc.select_backend(TaskKind.MATCH_JOB_TO_SKILLS, mit_api=False) == Backend.LOCAL


def test_die_freigabe_einer_aufgabe_oeffnet_nicht_die_andere(db, schluessel):
    freigeben(db, "validate_job_quality")
    svc = dienst(db)
    assert svc.select_backend(TaskKind.VALIDATE_JOB_QUALITY) == Backend.API
    assert svc.select_backend(TaskKind.MATCH_JOB_TO_SKILLS) != Backend.API


def test_hat_der_dienst_keine_datenbank_gibt_es_keinen_api_weg(schluessel):
    assert LLMService(None).select_backend(TaskKind.MATCH_JOB_TO_SKILLS) != Backend.API


def test_der_pfad_der_antwort_kommt_aus_dem_transport_und_nicht_aus_dem_netz(db, schluessel):
    """Gegenprobe zur Netzsperre: der Weg lief hier ueber das Testdoppel, kein einziger Verbindungsversuch."""
    import _netzsperre
    freigeben(db, "validate_job_quality")
    transport = FakeTransport(antwort('{"vollstaendig": true, "score": 8}'))
    api_backend.transport_setzen(transport)
    ergebnis = dienst(db).run(TaskKind.VALIDATE_JOB_QUALITY, {"title": "t", "description": "d" * 80})
    assert ergebnis.backend == Backend.API and ergebnis.success
    assert transport.anzahl == 1 and _netzsperre.VERSUCHE == []
