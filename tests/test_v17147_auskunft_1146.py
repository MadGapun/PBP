"""v1.7.147 — Falsche Auskunft (#1146): "unbekannt" ist keine Absage, und
ein Filter ohne Treffer ist kein leerer Bestand.

Zwei Befunde vom 01.10.2026:

1. `fit_analyse` urteilte NICHT_EMPFOHLEN, wenn die Stellenbeschreibung
   fehlte oder nur ein Kurztext war. Der Zweig `keine_beschreibung` in
   `passung.urteil` war damit unerreichbar, und die Begruendung widersprach
   sich selbst ("ausdruecklich keine fachliche Absage" unter einer Absage).
2. `bewerbungen_anzeigen(status_filter="Interview")` lieferte "Noch keine
   Bewerbungen erfasst. Erstelle eine neue ..." — bei drei vorhandenen
   Bewerbungen. Dasselbe bei `stellen_anzeigen(quelle=...)`.

Jeder Test hat eine Gegenprobe (scratchpad/n144/gegenprobe_1146.py): der
Mechanismus wird ausgebaut, und mindestens ein Test muss rot werden.
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


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_auskunft1146_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv
    importlib.reload(_srv)
    db = _srv.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Beispiel Person"})
    yield db, _srv.mcp
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


def _empfehlung(**fit):
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    profil = fit.pop("profil_kompetenzen", 12)
    analyse = fit.pop("gespeicherte_analyse", None)
    basis = {"total_score": 40, "total_score_max": 100, "risks": [],
             "muss_hits": [], "missing_muss": [], "beschreibung_vorhanden": True}
    basis.update(fit)
    return _build_empfehlung(basis, {}, profil_kompetenzen=profil,
                             gespeicherte_analyse=analyse)


# ══ Befund 1: fehlende oder kurze Beschreibung ═════════════════════

def test_leere_beschreibung_ist_nicht_beurteilbar_und_kein_ko():
    # der schlimmste Fall: kein Text UND keine MUSS-Treffer — frueher gleich
    # zwei k.o.-Gruende
    v = _empfehlung(beschreibung_vorhanden=False, muss_hits=[],
                    missing_muss=["python", "sql"])
    assert v["kategorie"] == "NICHT_BEURTEILBAR", v
    assert v["warum"] == "keine_beschreibung"
    assert v["grundlage"] == "keine_grundlage"
    assert "ko_gruende" not in v
    assert "nachladen" in v["datenlage_hinweis"]
    assert v["kurz"] == "Noch nicht beurteilt"
    assert v["score_zuverlaessig"] is False


def test_kurztext_ist_nicht_beurteilbar_auch_mit_allen_muss_treffern():
    # der gemessene Fall aus dem Issue: 67 Zeichen, 2 von 2 MUSS getroffen
    v = _empfehlung(beschreibung_kurz=True, muss_hits=["a", "b"], missing_muss=[])
    assert v["kategorie"] == "NICHT_BEURTEILBAR", v
    assert "ko_gruende" not in v
    assert "Kurztext" in v["datenlage_hinweis"]
    assert "keine fachliche Absage" in v["datenlage_hinweis"]


def test_kurztext_ohne_muss_treffer_wird_nicht_ueber_den_umweg_zum_ko():
    # Ein Kurztext enthaelt kaum Begriffe. "Kein MUSS-Treffer" waere derselbe
    # Fehler ueber den Umweg.
    v = _empfehlung(beschreibung_kurz=True, muss_hits=[], missing_muss=["x", "y"])
    assert v["kategorie"] == "NICHT_BEURTEILBAR", v
    assert "ko_gruende" not in v


def test_lesbare_anzeige_ohne_muss_treffer_bleibt_ko():
    # die Gegenrichtung: wo man lesen kann, gilt das k.o. weiter
    v = _empfehlung(muss_hits=[], missing_muss=["python", "sql", "go"])
    assert v["kategorie"] == "NICHT_EMPFOHLEN", v
    assert any("MUSS-Keyword" in g for g in v["ko_gruende"])
    assert "datenlage_hinweis" not in v


def test_lesbare_anzeige_mit_treffern_ist_nicht_gelesen_und_ohne_hinweis():
    v = _empfehlung(muss_hits=["python"], missing_muss=[])
    assert v["kategorie"] == "NICHT_BEURTEILBAR"
    assert v["warum"] == "nicht_gelesen"
    assert "datenlage_hinweis" not in v


def test_wiedergaenger_ko_gilt_auch_ohne_beschreibung():
    # echte k.o.-Gruende (dokumentierte Entscheidungen) bleiben — und der
    # Hinweis auf die fehlende Datenlage kommt dazu
    v = _empfehlung(beschreibung_vorhanden=False,
                    wiedergaenger={"anzahl": 2, "firma": "Beispiel GmbH",
                                   "top_grund": "falsches_fachgebiet"})
    assert v["kategorie"] == "NICHT_EMPFOHLEN", v
    assert v["grundlage"] == "ko_kriterium"
    assert "Wiedergaenger" in v["ko_gruende"][0]
    assert not any("Beschreibung" in g for g in v["ko_gruende"])
    assert "nachladen" in v["datenlage_hinweis"]


def test_gelesenes_urteil_bleibt_auch_bei_kurzer_beschreibung():
    # Wer Anzeige und Profil gelesen und das Urteil gespeichert hat, behaelt es
    v = _empfehlung(beschreibung_kurz=True, gespeicherte_analyse={
        "urteil": "BEDINGT", "begruendung": "Methoden uebertragbar.",
        "grundlage": "detailanalyse", "am": "2026-10-01T10:00:00"})
    assert v["kategorie"] == "BEDINGT"
    assert v["grundlage"] == "detailanalyse"
    assert "datenlage_hinweis" in v


def test_fit_analyse_werkzeug_ohne_text_ist_nicht_beurteilbar(umgebung):
    db, mcp = umgebung
    db.set_search_criteria("keywords_muss", ["python", "sql"])
    db.save_jobs([{
        "hash": "ohne_text_1146", "title": "Sachbearbeitung Einkauf",
        "company": "Musterbetrieb GmbH", "url": "https://example.com/stelle/1146",
        "source": "manuell", "description": "", "score": 0,
        "found_at": "2026-10-01T00:00:00",
    }])
    erg = _call(mcp, "fit_analyse", {"job_hash": "ohne_text_1146"})
    emp = erg.get("empfehlung") or {}
    assert emp.get("kategorie") == "NICHT_BEURTEILBAR", erg
    assert emp.get("warum") == "keine_beschreibung"
    assert "ko_gruende" not in emp
    assert "nachladen" in emp.get("datenlage_hinweis", "")


# ══ Befund 2: ein Filter ohne Treffer ist kein leerer Bestand ══════

def _drei_bewerbungen(db):
    a = db.add_application({"title": "Planung", "company": "Alpha AG", "status": "interview"})
    b = db.add_application({"title": "Einkauf", "company": "Beta GmbH", "status": "beworben"})
    c = db.add_application({"title": "Vertrieb", "company": "Gamma KG", "status": "abgelehnt"})
    return a, b, c


@pytest.mark.parametrize("schreibweise", [
    "interview", "Interview", "INTERVIEW", "  interview  ",
])
def test_status_filter_ignoriert_gross_und_kleinschreibung(umgebung, schreibweise):
    db, mcp = umgebung
    a, _b, _c = _drei_bewerbungen(db)
    erg = _call(mcp, "bewerbungen_anzeigen", {"status_filter": schreibweise})
    assert erg["anzahl"] == 1, erg
    assert erg["bewerbungen"][0]["id_voll"] == a


@pytest.mark.parametrize("schreibweise", [
    "Zweitgespräch", "zweitgespraech", "ZWEITGESPRÄCH",
])
def test_status_filter_nimmt_umlaute_statt_umschrift(umgebung, schreibweise):
    db, mcp = umgebung
    a = db.add_application({"title": "Planung", "company": "Alpha AG",
                            "status": "zweitgespraech"})
    erg = _call(mcp, "bewerbungen_anzeigen", {"status_filter": schreibweise})
    assert erg["anzahl"] == 1, erg
    assert erg["bewerbungen"][0]["id_voll"] == a


def test_status_filter_nimmt_leerzeichen_statt_unterstrich(umgebung):
    db, mcp = umgebung
    db.add_application({"title": "Planung", "company": "Alpha AG", "status": "in_vorbereitung"})
    for text in ("in Vorbereitung", "in-vorbereitung", "In_Vorbereitung"):
        erg = _call(mcp, "bewerbungen_anzeigen", {"status_filter": text})
        assert erg["anzahl"] == 1, (text, erg)


def test_unbekannter_status_nennt_die_gueltigen_und_sagt_nicht_noch_keine(umgebung):
    db, mcp = umgebung
    _drei_bewerbungen(db)
    from bewerbungs_assistent.services import bewerbung_status
    erg = _call(mcp, "bewerbungen_anzeigen", {"status_filter": "Wunschliste"})
    assert "fehler" in erg
    assert erg["gueltige_status"] == list(bewerbung_status.ALLE)
    assert "Wunschliste" in erg["fehler"]
    text = str(erg)
    assert "Noch keine Bewerbungen" not in text
    assert "bewerbungen" not in erg      # es wurde nichts gefiltert und nichts geraten


@pytest.mark.parametrize("wort, status", [
    ("Absage", "abgelehnt"), ("eingeladen", "interview"),
    ("Vorstellungsgespräch", "interview"), ("Zusage", "angebot"),
])
def test_umgangssprache_wird_vorgeschlagen_aber_nicht_angewandt(umgebung, wort, status):
    db, mcp = umgebung
    _drei_bewerbungen(db)
    erg = _call(mcp, "bewerbungen_anzeigen", {"status_filter": wort})
    assert erg.get("vorschlag_status") == status, erg
    assert status in erg["hinweis"]
    assert "bewerbungen" not in erg      # geraten wird nicht


def test_gueltiger_filter_ohne_treffer_nennt_den_bestand(umgebung):
    db, mcp = umgebung
    _drei_bewerbungen(db)
    erg = _call(mcp, "bewerbungen_anzeigen", {"status_filter": "angebot"})
    assert erg["anzahl"] == 0
    assert erg["gesamt"] == 3
    assert "Keine Bewerbung für diesen Filter" in erg["nachricht"]
    assert "angebot" in erg["nachricht"]
    assert "Noch keine Bewerbungen" not in erg["nachricht"]
    assert "naechster_schritt" in erg


def test_ohne_jede_bewerbung_bleibt_noch_keine_die_ehrliche_antwort(umgebung):
    # die Gegenrichtung: gibt es wirklich keine, ist "noch keine" wahr
    _db, mcp = umgebung
    erg = _call(mcp, "bewerbungen_anzeigen", {"status_filter": "interview"})
    assert erg["anzahl"] == 0
    assert "Noch keine Bewerbungen erfasst" in erg["nachricht"]
    erg = _call(mcp, "bewerbungen_anzeigen", {})
    assert "Noch keine Bewerbungen erfasst" in erg["nachricht"]


def test_stellenart_ohne_treffer_nennt_die_vorhandenen(umgebung):
    db, mcp = umgebung
    a, _b, _c = _drei_bewerbungen(db)
    db.update_application(a, {"employment_type": "festanstellung"})
    erg = _call(mcp, "bewerbungen_anzeigen", {"stellenart": "freelance"})
    assert erg["anzahl"] == 0
    assert erg["gesamt"] == 3
    assert "Keine Bewerbung für diesen Filter" in erg["nachricht"]
    assert "Noch keine Bewerbungen" not in erg["nachricht"]
    assert erg["stellenarten_im_bestand"] == ["festanstellung"]


def test_filter_ohne_treffer_nennt_ausgeblendete_abgeschlossene(umgebung):
    db, mcp = umgebung
    _drei_bewerbungen(db)
    erg = _call(mcp, "bewerbungen_anzeigen", {"stellenart": "freelance"})
    assert "archiv=True" in erg["archiv_hinweis"]


def test_gueltiger_filter_mit_treffer_zeigt_auch_archivierte(umgebung):
    # unveraendert: wer nach "abgelehnt" fragt, bekommt sie
    db, mcp = umgebung
    _a, _b, c = _drei_bewerbungen(db)
    erg = _call(mcp, "bewerbungen_anzeigen", {"status_filter": "Abgelehnt"})
    assert erg["anzahl"] == 1
    assert erg["bewerbungen"][0]["id_voll"] == c


def _stellen(db):
    db.save_jobs([
        {"hash": f"stelle_1146_{i}", "title": f"Sachbearbeitung {i}",
         "company": f"Musterbetrieb {i} GmbH", "url": f"https://example.com/s/{i}",
         "source": quelle, "description": "Beschreibung. " * 40, "score": 30,
         "found_at": "2026-10-01T00:00:00"}
        for i, quelle in enumerate(["bundesagentur", "arbeitnow", "bundesagentur"])
    ])


def test_stellen_quelle_ohne_treffer_sagt_nicht_starte_eine_jobsuche(umgebung):
    db, mcp = umgebung
    _stellen(db)
    erg = _call(mcp, "stellen_anzeigen", {"quelle": "StepStone", "ohne_schwelle": True})
    assert erg["anzahl"] == 0
    assert erg["aktive_stellen_gesamt"] == 3
    assert erg["quellen_im_bestand"] == ["arbeitnow", "bundesagentur"]
    assert "Keine Stelle für diesen Filter" in erg["nachricht"]
    assert "StepStone" in erg["nachricht"]
    assert "Starte eine Jobsuche" not in str(erg)


def test_stellen_anderer_filter_ohne_treffer_nennt_den_filter(umgebung):
    db, mcp = umgebung
    _stellen(db)
    erg = _call(mcp, "stellen_anzeigen", {"min_score": 99, "ohne_schwelle": True})
    assert erg["anzahl"] == 0
    assert "mindestens 99 Punkte" in erg["nachricht"]
    assert erg["aktive_stellen_gesamt"] == 3


def test_stellen_ohne_jeden_bestand_bleibt_starte_eine_jobsuche(umgebung):
    # die Gegenrichtung: gibt es wirklich keine Stelle, ist der Hinweis richtig
    _db, mcp = umgebung
    for args in ({}, {"quelle": "StepStone"}):
        erg = _call(mcp, "stellen_anzeigen", args)
        assert erg["anzahl"] == 0
        assert "Keine Stellen gefunden" in erg["nachricht"], (args, erg)
        assert "jobsuche_starten" in erg["nachricht"]


# ══ Die Statuswörter: eine Quelle, überall dieselbe ═════════════════

@pytest.mark.parametrize("text, erwartet", [
    ("interview", "interview"), ("Interview", "interview"),
    ("Zweitgespräch", "zweitgespraech"), ("zurückgezogen", "zurueckgezogen"),
    ("Eingangsbestätigung", "eingangsbestaetigung"),
    ("in Vorbereitung", "in_vorbereitung"),
    ("Arbeitgeber ausgefallen", "arbeitgeber_ausgefallen"),
    ("Absage", None), ("eingeladen", None), ("abgesagt", None),
    ("warte_auf_rueckmeldung", None), ("interview!", None), ("", None), (None, None),
])
def test_status_aus_text(text, erwartet):
    from bewerbungs_assistent.services import bewerbung_status as bs
    assert bs.status_aus_text(text) == erwartet


def test_jeder_status_erkennt_sich_selbst():
    from bewerbungs_assistent.services import bewerbung_status as bs
    for status in bs.ALLE:
        assert bs.status_aus_text(status) == status
        assert bs.status_aus_text(status.upper()) == status


def test_umgangssprache_zeigt_nur_auf_echte_status():
    from bewerbungs_assistent.services import bewerbung_status as bs
    for wort, status in bs.UMGANGSSPRACHE.items():
        assert status in bs.ALLE, (wort, status)
        # und ein Wort der Umgangssprache ist selbst kein Status
        assert bs.status_aus_text(wort) is None, wort


def test_katalog_nennt_die_echten_statuswoerter(umgebung):
    # Die Kurzbeschreibung schrieb "Interview" und "Zweitgespraech" gross —
    # ein Modell gibt das Wort so weiter, wie es dort steht.
    _db, mcp = umgebung
    from bewerbungs_assistent.services import bewerbung_status as bs
    from bewerbungs_assistent.services import werkzeug_katalog as k

    async def _beschreibung(name):
        return (await mcp.get_tool(name)).description

    text = asyncio.run(_beschreibung("bewerbung_status_aendern"))
    for wort in bs.ALLE:
        assert wort in text, wort
    assert "Interview" not in text and "Zweitgespraech" not in text
    assert k.KURZ["bewerbung_status_aendern"] == text

    anzeigen = asyncio.run(_beschreibung("bewerbungen_anzeigen"))
    assert "bewerbung_status_aendern" in anzeigen


def test_parametertext_des_filters_nennt_alle_status(umgebung):
    _db, mcp = umgebung
    from bewerbungs_assistent.services import bewerbung_status as bs

    async def _tool():
        return await mcp.get_tool("bewerbungen_anzeigen")
    beschreibung = asyncio.run(_tool()).parameters["properties"]["status_filter"].get("description", "")
    for wort in bs.ALLE:
        assert wort in beschreibung, wort
