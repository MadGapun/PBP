"""#1148 — MCP-Werkzeuge: Sammelposten (Durchsicht vom 01.10.2026).

Jeder Punkt wurde auf einer isolierten Datenbank nachgestellt, bevor er
behoben wurde; die Zahlen stehen an den Tests. Umgesetzt sind die Punkte 1,
2, 3, 5 (Annotation `ollama_kontext`, lesendes `suchprofil_lesen`), 6, 7, 8,
10 und 11. Offen bleiben 4 (Zählerstände in Wiki und Dokumenten), 9
(typisierte IDs), 12 (Antwortgrößen) und 13 (veraltete Weiterleitungen) —
sie stehen im Issue.

Alle Firmen, Orte und Namen sind Platzhalter.
"""
import ast
import asyncio
import importlib
import os
import re
import shutil
import sys
import tempfile
import threading
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17148_1148_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp, _srv_mod
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


# ══ Punkt 1: Zeitüberschreitung auf Deutsch, keine zweite Rechnung ═══════════

@pytest.fixture
def langsamer_server(umgebung, monkeypatch):
    """Ein FastMCP-Server mit der Middleware des echten Servers und einem
    Werkzeug, das rechnet, bis es fertig ist (nicht abbrechbar)."""
    db, _mcp, srv = umgebung
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import laufende_aufrufe, mit_katalog

    monkeypatch.setattr(srv.HeartbeatMiddleware, "DEFAULT_TIMEOUT", 1)
    srv.HeartbeatMiddleware._abgelaufen.clear()
    mcp = FastMCP("zeit")
    mcp.add_middleware(srv.HeartbeatMiddleware())
    zustand = {"fertig": threading.Event(), "aufrufe": 0}

    @mit_katalog(mcp, db).tool()
    def pbp_test_langsam(wer: str = "a") -> dict:
        """Rechnet lange, wenn man es ihm sagt."""
        zustand["aufrufe"] += 1
        if wer == "lange":
            time.sleep(2.5)
        return {"ok": True, "wer": wer}

    yield mcp, zustand, laufende_aufrufe
    # Der Arbeits-Thread muss fertig sein, bevor die Datenbank schliesst.
    ende = time.monotonic() + 10
    while laufende_aufrufe("pbp_test_langsam") and time.monotonic() < ende:
        time.sleep(0.05)
    srv.HeartbeatMiddleware._abgelaufen.clear()


def _client_aufruf(mcp, name, args):
    from fastmcp import Client

    async def _run():
        async with Client(mcp) as c:
            return await c.call_tool(name, args, raise_on_error=False)
    return asyncio.run(_run())


def _text(res) -> str:
    return " ".join(getattr(t, "text", str(t)) for t in res.content)


def test_1148_die_zeitueberschreitung_kommt_auf_deutsch(langsamer_server):
    """Gemessen: is_error=True mit 'Output validation error: outputSchema defined
    but no structured output returned' statt der deutschen Meldung."""
    mcp, zustand, laufende = langsamer_server
    res = _client_aufruf(mcp, "pbp_test_langsam", {"wer": "lange"})
    assert res.is_error is True
    text = _text(res)
    assert "Output validation error" not in text
    assert "hat nach 1 Sekunden nicht geantwortet" in text
    assert "timeout" in text
    # Ehrlich: die Rechnung kann noch laufen.
    assert "im Hintergrund noch laufen" in text


def test_1148_eine_sofortige_wiederholung_startet_die_rechnung_nicht_noch_einmal(langsamer_server):
    """Gemessen: der Arbeits-Thread rechnete weiter, und ein Wiederholen startete
    eine zweite Rechnung (257 -> 1.210 Aufrufe)."""
    mcp, zustand, laufende = langsamer_server
    _client_aufruf(mcp, "pbp_test_langsam", {"wer": "lange"})
    assert zustand["aufrufe"] == 1
    assert laufende("pbp_test_langsam") == 1, "die erste Rechnung laeuft noch"
    t0 = time.monotonic()
    zweite = _client_aufruf(mcp, "pbp_test_langsam", {"wer": "lange"})
    assert time.monotonic() - t0 < 0.9, "die Wiederholung wartete selbst auf die Zeit"
    assert zweite.is_error is True
    assert "laeuft_noch" in _text(zweite)
    assert "zweites Mal" in _text(zweite)
    assert zustand["aufrufe"] == 1, "die Rechnung wurde ein zweites Mal gestartet"


def test_1148_ein_anderer_aufruf_wird_nicht_blockiert(langsamer_server):
    mcp, zustand, laufende = langsamer_server
    _client_aufruf(mcp, "pbp_test_langsam", {"wer": "lange"})
    anderer = _client_aufruf(mcp, "pbp_test_langsam", {"wer": "schnell"})
    assert anderer.is_error is False
    assert anderer.structured_content["wer"] == "schnell"


def test_1148_nach_dem_ende_der_rechnung_laeuft_dieselbe_anfrage_wieder(langsamer_server):
    mcp, zustand, laufende = langsamer_server
    _client_aufruf(mcp, "pbp_test_langsam", {"wer": "lange"})
    ende = time.monotonic() + 10
    while laufende("pbp_test_langsam") and time.monotonic() < ende:
        time.sleep(0.05)
    assert laufende("pbp_test_langsam") == 0
    # Dieselbe Anfrage, jetzt ohne laufende Rechnung: kein "laeuft noch" mehr
    # (sie braucht wieder 2,5 s und laeuft deshalb erneut in die Zeit).
    wieder = _client_aufruf(mcp, "pbp_test_langsam", {"wer": "lange"})
    assert "laeuft_noch" not in _text(wieder)
    assert "hat nach 1 Sekunden nicht geantwortet" in _text(wieder)


def test_1148_die_zaehlung_laufender_aufrufe_geht_nach_einem_fehler_zurueck(umgebung):
    db, mcp, srv = umgebung
    from bewerbungs_assistent.tools import laufende_aufrufe, mit_katalog
    from fastmcp import FastMCP
    kleiner = FastMCP("z")

    @mit_katalog(kleiner, db).tool()
    def pbp_test_wirft_zaehlung() -> dict:
        """Wirft."""
        raise ValueError("nein")

    for _ in range(3):
        with pytest.raises(Exception):
            _call(kleiner, "pbp_test_wirft_zaehlung")
    assert laufende_aufrufe("pbp_test_wirft_zaehlung") == 0


# ══ Punkt 2: Skill-IDs und ehrliches "bereits vorhanden" ═══════════════════

def _skill(db, name="Python", level=9):
    sid, grund = db.add_skill_mit_befund({"name": name, "level": level,
                                          "category": "fachlich"}, quelle="eingabe")
    assert sid, grund
    return sid


def test_1148_die_profilzusammenfassung_nennt_die_skill_ids(umgebung):
    """Der Wegweiser sagte 'profil_zusammenfassung() nennt die Skill-IDs' —
    und sie standen nicht darin."""
    db, mcp, _ = umgebung
    sid = _skill(db)
    erg = _call(mcp, "profil_zusammenfassung")
    assert f"[{sid}]" in erg["zusammenfassung"]
    ids = [s["id"] for s in erg["skills_liste"]]
    assert sid in ids
    eintrag = next(s for s in erg["skills_liste"] if s["id"] == sid)
    assert eintrag["name"] == "Python" and eintrag["level"] == 9


def test_1148_die_genannte_skill_id_fuehrt_zum_aendern(umgebung):
    db, mcp, _ = umgebung
    sid = _skill(db)
    erg = _call(mcp, "profil_zusammenfassung")
    genannt = erg["skills_liste"][0]["id"]
    antwort = _call(mcp, "profil_bearbeiten", {
        "bereich": "skill", "aktion": "aendern", "element_id": genannt,
        "daten": {"level": 4}})
    assert antwort["status"] == "aktualisiert"
    assert db.find_skill("Python")["level"] == 4


def test_1148_ein_vorhandener_skill_wird_nicht_als_gespeichert_gemeldet(umgebung):
    """Gemessen: Python Level 9; erneutes Hinzufuegen mit Level 1 und
    last_used_year=2008 -> gleiche ID, Level bleibt 9, Antwort 'gespeichert'."""
    db, mcp, _ = umgebung
    sid = _skill(db, level=9)
    erg = _call(mcp, "skill_hinzufuegen", {"name": "python", "level": 1,
                                           "last_used_year": 2008})
    assert erg["status"] == "bereits_vorhanden"
    assert erg["skill_id"] == sid
    assert erg["vorhanden"]["level"] == 9
    assert "NICHTS geändert" in erg["hinweis"]
    assert sid in erg["hinweis"], "der Weg zum Aendern nennt die ID"
    assert db.find_skill("Python")["level"] == 9


def test_1148_ein_neuer_skill_wird_weiter_gespeichert(umgebung):
    db, mcp, _ = umgebung
    erg = _call(mcp, "skill_hinzufuegen", {"name": "Linux", "level": 3})
    assert erg["status"] == "gespeichert"


def test_1148_profil_bearbeiten_meldet_einen_vorhandenen_skill_ebenso(umgebung):
    db, mcp, _ = umgebung
    sid = _skill(db, level=9)
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "skill", "aktion": "hinzufuegen",
        "daten": {"name": "Python", "level": 1}})
    assert erg["status"] == "bereits_vorhanden"
    assert erg["id"] == sid


def test_1148_der_sammelweg_nennt_vorhandene_skills_getrennt(umgebung):
    db, mcp, _ = umgebung
    _skill(db, "Python", 9)
    erg = _call(mcp, "profil_bearbeiten", {
        "bereich": "skill", "aktion": "hinzufuegen_bulk",
        "daten": [{"name": "Python"}, {"name": "Rust"}]})
    assert erg["anzahl"] == 1
    assert [s["name"] for s in erg["schon_vorhanden"]] == ["Python"]
    nur_alte = _call(mcp, "profil_bearbeiten", {
        "bereich": "skill", "aktion": "hinzufuegen_bulk",
        "daten": [{"name": "Python"}, {"name": "Rust"}]})
    assert nur_alte["anzahl"] == 0
    assert nur_alte["status"] == "bereits_vorhanden"


# ══ Punkt 3: Seitenwerte ═══════════════════════════════════════════════

def _eine_stelle(db):
    db.set_search_criteria("keywords_muss", ["Stammdaten"])
    db.save_jobs([{
        "hash": "s1", "title": "Stammdaten Migration", "company": "Musterfirma GmbH",
        "location": "Musterstadt", "url": "https://example.com/1148/s1",
        "source": "manuell", "_manual_entry": True,
        "description": "Stammdaten und Migration im Bestand. " * 12,
        "employment_type": "festanstellung", "score": 5.0}])


@pytest.mark.parametrize("pro_seite", [0, -3])
def test_1148_pro_seite_unter_eins_gibt_keine_python_meldung(umgebung, pro_seite):
    """Gemessen: stellen_anzeigen(pro_seite=0) -> 'integer division or modulo by zero'."""
    db, mcp, _ = umgebung
    _eine_stelle(db)
    erg = _call(mcp, "stellen_anzeigen", {"pro_seite": pro_seite})
    assert "fehler" not in erg and "error" not in erg, erg
    assert erg["pro_seite"] == 20
    assert erg["seiten_gesamt"] == 1
    assert any("pro_seite" in k for k in erg["eingabe_korrigiert"])


def test_1148_seite_unter_eins_wird_seite_eins(umgebung):
    db, mcp, _ = umgebung
    _eine_stelle(db)
    erg = _call(mcp, "stellen_anzeigen", {"seite": 0})
    assert erg["seite"] == 1 and erg["angezeigt"] == 1
    assert any("seite" in k for k in erg["eingabe_korrigiert"])


def test_1148_zu_viel_pro_seite_wird_benannt_nicht_still_gekappt(umgebung):
    db, mcp, _ = umgebung
    _eine_stelle(db)
    erg = _call(mcp, "stellen_anzeigen", {"pro_seite": 1000})
    assert erg["pro_seite"] == 50
    assert any("zu gross" in k for k in erg["eingabe_korrigiert"])


def test_1148_eine_normale_anfrage_traegt_keine_korrekturmeldung(umgebung):
    db, mcp, _ = umgebung
    _eine_stelle(db)
    erg = _call(mcp, "stellen_anzeigen", {})
    assert "eingabe_korrigiert" not in erg


# ══ Punkt 5: Annotation und lesendes Werkzeug ═════════════════════════════

def test_1148_ollama_kontext_traegt_kein_readonly(umgebung):
    """`aktion='setzen'` schreibt den Kontext der lokalen KI."""
    from bewerbungs_assistent.services.werkzeug_schutz import annotations_fuer
    assert annotations_fuer("ollama_kontext").get("readOnlyHint") is not True


def test_1148_die_haeufig_gerufenen_lesewerkzeuge_bleiben_lesend(umgebung):
    """Ohne readOnlyHint fragte Claude Desktop bei jedem Aufruf um Erlaubnis."""
    from bewerbungs_assistent.services.werkzeug_schutz import annotations_fuer
    for name in ("profil_status", "stellen_anzeigen", "bewerbungen_anzeigen",
                 "profil_zusammenfassung"):
        a = annotations_fuer(name)
        assert a.get("readOnlyHint") is True or name == "profil_zusammenfassung", name


def test_1148_suchprofil_lesen_legt_nichts_an(umgebung):
    db, mcp, _ = umgebung
    assert db.list_portal_search_profiles() == []
    erg = _call(mcp, "suchprofil_lesen", {"portal": "linkedin"})
    assert erg["gespeichert"] is False
    assert erg["primaere_suchen"] == [] and erg["portal"] == "linkedin"
    assert db.list_portal_search_profiles() == [], "Lesen hat eine Zeile angelegt"
    assert db.find_portal_search_profile("linkedin") is None


def test_1148_suchprofil_lesen_zeigt_das_gespeicherte(umgebung):
    db, mcp, _ = umgebung
    _call(mcp, "suchprofil_aktualisieren", {
        "portal": "xing", "primaere_suchen": [{"keywords": "Pflegefachkraft"}]})
    erg = _call(mcp, "suchprofil_lesen", {"portal": "xing"})
    assert [s["keywords"] for s in erg["primaere_suchen"]] == ["Pflegefachkraft"]
    assert "gespeichert" not in erg or erg["gespeichert"] is not False


# ══ Punkt 6: nicht erreichbare Adressen zaehlen nicht als ok ══════════════

def test_1148_eine_nicht_erreichbare_adresse_zaehlt_nicht_als_ok(umgebung, monkeypatch):
    """Gemessen ohne Netz: 'geprueft 5, ok 1' — der Rest fiel durch alle Zweige."""
    db, mcp, _ = umgebung
    from bewerbungs_assistent.services import url_health
    monkeypatch.setattr(
        url_health, "check_job_url_health",
        lambda url, title, client=None: url_health.HealthResult(
            status=url_health.HealthStatus.UNKNOWN, note="ConnectError"))
    db.save_jobs([{
        "hash": "q1", "title": "Stammdaten Migration", "company": "Musterfirma GmbH",
        "location": "Musterstadt", "url": "https://example.com/1148/q1",
        "source": "stepstone",
        "description": "Stammdaten und Migration im Bestand. " * 12,
        "employment_type": "festanstellung", "score": 5.0}])
    erg = _call(mcp, "stellen_qualitaet_pruefen", {})
    assert erg["befunde"].get("url_nicht_erreichbar") == 1, erg["befunde"]
    assert erg["befunde"].get("ok", 0) == 0


def test_1148_eine_erreichbare_adresse_bleibt_ok(umgebung, monkeypatch):
    db, mcp, _ = umgebung
    from bewerbungs_assistent.services import url_health
    monkeypatch.setattr(
        url_health, "check_job_url_health",
        lambda url, title, client=None: url_health.HealthResult(
            status=url_health.HealthStatus.OK, http_code=200))
    db.save_jobs([{
        "hash": "q2", "title": "Stammdaten Migration", "company": "Musterfirma GmbH",
        "location": "Musterstadt", "url": "https://example.com/1148/q2",
        "source": "stepstone",
        "description": "Stammdaten und Migration im Bestand. " * 12,
        "employment_type": "festanstellung", "score": 5.0}])
    erg = _call(mcp, "stellen_qualitaet_pruefen", {})
    assert erg["befunde"].get("url_nicht_erreichbar", 0) == 0


# ══ Punkt 7: tote Verweise und Eingaben ═══════════════════════════════════

# Namen in Texten, die wie ein Werkzeug aussehen und keines sind: Tabellen,
# Funktionen der Dienste. Jeder Eintrag traegt seinen Grund; ein NEUER
# Treffer ist ein toter Verweis.
_KEIN_WERKZEUG = {
    "blacklist_blocks": "Tabelle",
    "elwosa_messages": "Tabelle",
    "elwosa_pending_lines": "Tabelle",
    "follow_ups": "Tabelle",
    "interview_reflections": "Tabelle",
    "scoring_config": "Tabelle",
    "scraper_runs": "Tabelle (Schema v52, Beta-Linie)",
    "skill_periods": "Tabelle",
    "firmen_historie": "Funktion in services/wiedergaenger.py",
    "ollama_starten": "Funktion in services/ollama_start.py",
}


def _alle_werkzeugnamen(tmp_path):
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.tools import register_all
    db = Database(db_path=tmp_path / "scan.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path)
    mcp = FastMCP("scan")
    register_all(mcp, db, logging.getLogger("scan"))

    async def _namen():
        return {t.name for t in await mcp.list_tools()}
    try:
        return asyncio.run(_namen())
    finally:
        db.close()


def test_1148_kein_text_verweist_auf_ein_werkzeug_das_es_nicht_gibt(umgebung, tmp_path):
    """`services/suchbereitschaft.py` nannte `dokument_hochladen()`. Das gibt es
    nicht — Dokumente laedt man im Dashboard hoch."""
    namen = _alle_werkzeugnamen(Path(tempfile.mkdtemp(prefix="pbp_scan1148_")))
    erste = {n.split("_")[0] for n in namen}
    muster = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\(")
    funde = {}
    for p in (_repo() / "src" / "bewerbungs_assistent").rglob("*.py"):
        if "static" in p.parts:
            continue
        try:
            baum = ast.parse(p.read_text(encoding="utf-8-sig"))
        except SyntaxError:
            continue
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
                for m in muster.finditer(knoten.value):
                    n = m.group(1)
                    if n.split("_")[0] in erste and n not in namen and n not in _KEIN_WERKZEUG:
                        funde.setdefault(n, set()).add(f"{p.name}:{knoten.lineno}")
    assert not funde, f"Texte nennen Werkzeuge, die es nicht gibt: {funde}"


def test_1148_suchbereitschaft_nennt_den_echten_upload_weg(umgebung):
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "services" /
              "suchbereitschaft.py").read_text(encoding="utf-8-sig")
    assert "dokument_hochladen" not in quelle
    assert "im Dashboard" in quelle and "dokument_profil_extrahieren" in quelle


def test_1148_eine_leere_liste_gilt_nicht_als_gespeichert(umgebung):
    """`suchkriterien_setzen` mit leerer Liste aenderte nichts, meldete aber 'gespeichert'."""
    db, mcp, _ = umgebung
    db.set_search_criteria("keywords_muss", ["Stammdaten"])
    erg = _call(mcp, "suchkriterien_setzen", {"keywords_muss": []})
    assert erg["status"] == "nichts_geaendert"
    assert erg["ignoriert"] == ["keywords_muss"]
    assert "leere Liste" in erg["hinweis"]
    assert db.get_search_criteria()["keywords_muss"] == ["Stammdaten"]


def test_1148_eine_leere_liste_neben_einer_aenderung_wird_benannt(umgebung):
    db, mcp, _ = umgebung
    db.set_search_criteria("keywords_muss", ["Stammdaten"])
    erg = _call(mcp, "suchkriterien_setzen", {"keywords_muss": [],
                                              "keywords_plus": ["Migration"]})
    assert erg["status"] == "gespeichert"
    assert erg["ignoriert"] == ["keywords_muss"]
    assert "Migration" in db.get_search_criteria()["keywords_plus"]
    assert db.get_search_criteria()["keywords_muss"] == ["Stammdaten"]


def test_1148_ein_leerer_aufruf_ohne_listen_ist_ebenfalls_nichts_geaendert(umgebung):
    db, mcp, _ = umgebung
    erg = _call(mcp, "suchkriterien_setzen", {})
    assert erg["status"] == "nichts_geaendert"


def test_1148_eine_gesetzte_zahl_ist_weiter_gespeichert(umgebung):
    db, mcp, _ = umgebung
    erg = _call(mcp, "suchkriterien_setzen", {"min_gehalt": 60000})
    assert erg["status"] == "gespeichert"
    assert "ignoriert" not in erg


def test_1148_ein_erfundener_befund_wird_nicht_abgewiesen_gemeldet(umgebung):
    db, mcp, _ = umgebung
    erg = _call(mcp, "diagnose_befund_abweisen", {"befund_id": "gibt-es-nicht"})
    assert "fehler" in erg
    assert "gibt es nicht" in erg["fehler"]
    from bewerbungs_assistent.services import interview_vollstaendigkeit as iv
    assert iv.befund_stand(db, "gibt-es-nicht") == "unbekannt"
    assert "gibt-es-nicht" not in iv._abgewiesen(db), "die erfundene ID wurde gemerkt"


def test_1148_ein_echter_befund_laesst_sich_abweisen(umgebung, monkeypatch):
    db, mcp, _ = umgebung
    from bewerbungs_assistent.services import interview_vollstaendigkeit as iv
    monkeypatch.setattr(iv, "pruefe_interview_vollstaendigkeit",
                        lambda d: [{"id": "iv-echt"}])
    assert iv.befund_stand(db, "iv-echt") == "offen"
    erg = _call(mcp, "diagnose_befund_abweisen", {"befund_id": "iv-echt"})
    assert erg["status"] == "abgewiesen"
    monkeypatch.setattr(iv, "pruefe_interview_vollstaendigkeit", lambda d: [])
    again = _call(mcp, "diagnose_befund_abweisen", {"befund_id": "iv-echt"})
    assert again["status"] == "war_bereits_abgewiesen"


# ══ Punkt 8: Doppelanlage ═════════════════════════════════════════════

def _positionen(db):
    return (db.get_profile() or {}).get("positions", [])


def test_1148_dieselbe_position_wird_nicht_zweimal_angelegt(umgebung):
    db, mcp, _ = umgebung
    args = {"company": "Musterfirma GmbH", "title": "Fachkraft", "start_date": "2020-03"}
    erst = _call(mcp, "position_hinzufuegen", args)
    zweit = _call(mcp, "position_hinzufuegen", args)
    assert erst["status"] == "gespeichert"
    assert zweit["status"] == "bereits_vorhanden"
    assert zweit["position_id"] == erst["position_id"]
    assert len(_positionen(db)) == 1


def test_1148_gleiche_position_andere_schreibweise_ist_dieselbe(umgebung):
    db, mcp, _ = umgebung
    _call(mcp, "position_hinzufuegen", {"company": "Musterfirma GmbH",
                                        "title": "Fachkraft", "start_date": "2020-03"})
    zweit = _call(mcp, "position_hinzufuegen", {"company": " musterfirma gmbh ",
                                                "title": "FACHKRAFT",
                                                "start_date": "2020-03-01"})
    assert zweit["status"] == "bereits_vorhanden"


def test_1148_eine_andere_position_wird_angelegt(umgebung):
    db, mcp, _ = umgebung
    _call(mcp, "position_hinzufuegen", {"company": "Musterfirma GmbH",
                                        "title": "Fachkraft", "start_date": "2020-03"})
    for abweichung in ({"title": "Teamleitung"}, {"company": "Beispielwerk AG"},
                       {"start_date": "2022-01"}):
        args = {"company": "Musterfirma GmbH", "title": "Fachkraft",
                "start_date": "2020-03", **abweichung}
        assert _call(mcp, "position_hinzufuegen", args)["status"] == "gespeichert"
    assert len(_positionen(db)) == 4


def test_1148_profil_bearbeiten_verdoppelt_eine_position_ebenso_nicht(umgebung):
    db, mcp, _ = umgebung
    daten = {"company": "Musterfirma GmbH", "title": "Fachkraft", "start_date": "2020-03"}
    _call(mcp, "profil_bearbeiten", {"bereich": "position", "aktion": "hinzufuegen",
                                     "daten": daten})
    zweit = _call(mcp, "profil_bearbeiten", {"bereich": "position",
                                             "aktion": "hinzufuegen", "daten": daten})
    assert zweit["status"] == "bereits_vorhanden"
    assert len(_positionen(db)) == 1


def test_1148_der_sammelweg_legt_vorhandene_positionen_nicht_noch_einmal_an(umgebung):
    db, mcp, _ = umgebung
    daten = [{"company": "Musterfirma GmbH", "title": "Fachkraft", "start_date": "2020-03"},
             {"company": "Beispielwerk AG", "title": "Leitung", "start_date": "2018-01"}]
    erst = _call(mcp, "profil_bearbeiten", {"bereich": "position",
                                            "aktion": "hinzufuegen_bulk", "daten": daten})
    assert erst["anzahl"] == 2
    zweit = _call(mcp, "profil_bearbeiten", {"bereich": "position",
                                             "aktion": "hinzufuegen_bulk", "daten": daten})
    assert zweit["anzahl"] == 0 and len(zweit["schon_vorhanden"]) == 2
    assert zweit["status"] == "bereits_vorhanden"
    assert len(_positionen(db)) == 2


def test_1148_dieselbe_ausbildung_wird_nicht_zweimal_angelegt(umgebung):
    db, mcp, _ = umgebung
    args = {"institution": "Musterhochschule", "degree": "Bachelor",
            "field_of_study": "Verwaltung", "start_date": "2012-10"}
    erst = _call(mcp, "ausbildung_hinzufuegen", args)
    zweit = _call(mcp, "ausbildung_hinzufuegen", args)
    assert erst["status"] == "gespeichert"
    assert zweit["status"] == "bereits_vorhanden"
    assert zweit["ausbildung_id"] == erst["ausbildung_id"]
    assert len((db.get_profile() or {}).get("education", [])) == 1
    anderer = _call(mcp, "ausbildung_hinzufuegen", {**args, "degree": "Master"})
    assert anderer["status"] == "gespeichert"


def test_1148_dasselbe_projekt_nicht_zweimal_in_dieselbe_position(umgebung):
    db, mcp, _ = umgebung
    p1 = _call(mcp, "position_hinzufuegen", {"company": "Musterfirma GmbH",
                                             "title": "Fachkraft", "start_date": "2020-03"})
    p2 = _call(mcp, "position_hinzufuegen", {"company": "Beispielwerk AG",
                                             "title": "Leitung", "start_date": "2018-01"})
    erst = _call(mcp, "projekt_hinzufuegen", {"position_id": p1["position_id"],
                                              "name": "Umstellung"})
    zweit = _call(mcp, "projekt_hinzufuegen", {"position_id": p1["position_id"],
                                               "name": "umstellung"})
    assert erst["status"] == "gespeichert"
    assert zweit["status"] == "bereits_vorhanden"
    assert zweit["projekt_id"] == erst["projekt_id"]
    # In einer ANDEREN Position ist dasselbe Wort ein anderes Projekt.
    dritt = _call(mcp, "projekt_hinzufuegen", {"position_id": p2["position_id"],
                                               "name": "Umstellung"})
    assert dritt["status"] == "gespeichert"


def test_1148_dieselbe_offene_aufgabe_wird_nicht_zweimal_angelegt(umgebung):
    db, mcp, _ = umgebung
    args = {"titel": "Zeugnisse sortieren", "faellig_am": "2026-11-01"}
    erst = _call(mcp, "todo_anlegen", args)
    zweit = _call(mcp, "todo_anlegen", args)
    assert erst["status"] == "angelegt"
    assert zweit["status"] == "bereits_vorhanden"
    assert zweit["task_id"] == erst["task_id"]
    assert len(db.list_tasks()) == 1


def test_1148_eine_erledigte_aufgabe_darf_wiederkehren(umgebung):
    db, mcp, _ = umgebung
    args = {"titel": "Zeugnisse sortieren", "faellig_am": "2026-11-01"}
    erst = _call(mcp, "todo_anlegen", args)
    _call(mcp, "todo_erledigen", {"todo_id": erst["task_id"]})
    zweit = _call(mcp, "todo_anlegen", args)
    assert zweit["status"] == "angelegt"
    assert zweit["task_id"] != erst["task_id"]


def test_1148_eine_aufgabe_mit_anderem_datum_ist_eine_andere(umgebung):
    db, mcp, _ = umgebung
    _call(mcp, "todo_anlegen", {"titel": "Zeugnisse sortieren", "faellig_am": "2026-11-01"})
    zweit = _call(mcp, "todo_anlegen", {"titel": "Zeugnisse sortieren",
                                        "faellig_am": "2026-11-15"})
    assert zweit["status"] == "angelegt"


def test_1148_derselbe_kontakt_wird_nicht_zweimal_angelegt(umgebung):
    db, mcp, _ = umgebung
    args = {"name": "Erika Beispiel", "email": "erika@example.com", "firma": "Musterfirma GmbH"}
    erst = _call(mcp, "kontakt_anlegen", args)
    zweit = _call(mcp, "kontakt_anlegen", args)
    assert erst["status"] == "angelegt"
    assert zweit["status"] == "bereits_vorhanden"
    assert zweit["id"] == erst["id"]
    assert len(db.list_contacts()) == 1


def test_1148_zwei_menschen_gleichen_namens_sind_zwei_kontakte(umgebung):
    db, mcp, _ = umgebung
    _call(mcp, "kontakt_anlegen", {"name": "Erika Beispiel", "email": "erika@example.com",
                                   "firma": "Musterfirma GmbH"})
    # andere Firma: eine andere Person
    anderer = _call(mcp, "kontakt_anlegen", {"name": "Erika Beispiel",
                                             "firma": "Beispielwerk AG"})
    assert anderer["status"] == "angelegt"
    # gleiche Firma, aber eine ANDERE E-Mail: eine andere Person
    anderer_mail = _call(mcp, "kontakt_anlegen", {"name": "Erika Beispiel",
                                                  "email": "andere@example.com",
                                                  "firma": "Musterfirma GmbH"})
    assert anderer_mail["status"] == "angelegt"
    assert len(db.list_contacts()) == 3


def test_1148_gleiche_firma_und_name_mit_neuer_mail_ist_derselbe_kontakt(umgebung):
    """Fehlt dem vorhandenen Kontakt nur die E-Mail, ist es dieselbe Person —
    die Antwort nennt, wie man sie ergaenzt."""
    db, mcp, _ = umgebung
    erst = _call(mcp, "kontakt_anlegen", {"name": "Erika Beispiel",
                                          "firma": "Musterfirma GmbH"})
    zweit = _call(mcp, "kontakt_anlegen", {"name": "Erika Beispiel",
                                           "email": "erika@example.com",
                                           "firma": "Musterfirma GmbH"})
    assert zweit["status"] == "bereits_vorhanden"
    assert zweit["id"] == erst["id"]
    assert "kontakt_bearbeiten" in zweit["hinweis"]


def test_1148_ein_kontakt_nur_mit_namen_wird_bei_wiederholung_erkannt(umgebung):
    db, mcp, _ = umgebung
    erst = _call(mcp, "kontakt_anlegen", {"name": "Erika Beispiel"})
    zweit = _call(mcp, "kontakt_anlegen", {"name": "erika beispiel"})
    assert zweit["status"] == "bereits_vorhanden"
    assert zweit["id"] == erst["id"]


def _bewerbung(db):
    return db.add_application({"title": "Fachkraft", "company": "Musterfirma GmbH",
                               "status": "beworben"})


def test_1148_kosten_mit_erfundener_bewerbung_legen_keine_verwaiste_zeile_an(umgebung):
    """Gemessen auf Datenbank-Ebene: eine verwaiste Zeile."""
    db, mcp, _ = umgebung
    erg = _call(mcp, "kosten_erfassen", {"kategorie": "reise", "betrag_eur": 12.5,
                                         "bewerbung_id": "gibt-es-nicht"})
    assert "fehler" in erg and "nicht gefunden" in erg["fehler"]
    assert db.list_application_costs() == []


def test_1148_dieselbe_zahlung_eben_erst_ist_eine_wiederholung(umgebung):
    db, mcp, _ = umgebung
    aid = _bewerbung(db)
    args = {"kategorie": "reise", "betrag_eur": 12.5, "beschreibung": "Fahrkarte",
            "bewerbung_id": aid}
    erst = _call(mcp, "kosten_erfassen", args)
    zweit = _call(mcp, "kosten_erfassen", args)
    assert erst["status"] == "gespeichert"
    assert zweit["status"] == "bereits_vorhanden"
    assert zweit["kosten_id"] == erst["kosten_id"]
    assert len(db.list_application_costs()) == 1


def test_1148_eine_andere_beschreibung_ist_eine_neue_zahlung(umgebung):
    db, mcp, _ = umgebung
    aid = _bewerbung(db)
    base = {"kategorie": "reise", "betrag_eur": 12.5, "bewerbung_id": aid}
    _call(mcp, "kosten_erfassen", {**base, "beschreibung": "Hinfahrt"})
    zweit = _call(mcp, "kosten_erfassen", {**base, "beschreibung": "Rueckfahrt"})
    assert zweit["status"] == "gespeichert"
    assert len(db.list_application_costs()) == 2


def test_1148_dieselbe_zahlung_nach_dem_fenster_ist_eine_neue(umgebung):
    db, mcp, _ = umgebung
    from bewerbungs_assistent.services import doppelanlage as da
    aid = _bewerbung(db)
    erst = _call(mcp, "kosten_erfassen", {"kategorie": "reise", "betrag_eur": 12.5,
                                          "beschreibung": "Fahrkarte", "bewerbung_id": aid})
    heute = date.today().isoformat()
    spaeter = datetime.now(timezone.utc) + timedelta(minutes=da.KOSTEN_FENSTER_MIN + 1)
    assert da.kosten_wiederholung(db, aid, "reise", 12.5, "Fahrkarte", heute,
                                  jetzt=datetime.now(timezone.utc)) == erst["kosten_id"]
    assert da.kosten_wiederholung(db, aid, "reise", 12.5, "Fahrkarte", heute,
                                  jetzt=spaeter) is None


# ══ Punkt 10: Firmensuche ═════════════════════════════════════════════

def test_1148_und_und_und_zeichen_sind_dieselbe_firma(umgebung):
    """Gemessen: 'und' fand eine mit '&' gespeicherte Firma nicht."""
    db, mcp, _ = umgebung
    db.add_application({"title": "Fachkraft", "company": "Beispiel & Söhne GmbH",
                        "status": "beworben"})
    erg = _call(mcp, "firma_kontext", {"firmenname": "Beispiel und Söhne"})
    assert erg["gefunden"] is True
    assert len(erg["bewerbungen"]) == 1


def test_1148_umgekehrt_findet_das_zeichen_die_firma_mit_und(umgebung):
    db, mcp, _ = umgebung
    db.add_application({"title": "Fachkraft", "company": "Söhne und Beispiel GmbH",
                        "status": "beworben"})
    erg = _call(mcp, "firma_kontext", {"firmenname": "Söhne & Beispiel"})
    assert erg["gefunden"] is True


def test_1148_ein_wortanfang_nennt_kandidaten_aber_keinen_status(umgebung):
    """Gemessen: 'Personal' fand 'Personalservice ...' nicht und sagte 'Kein
    dokumentierter Kontakt'. Kandidaten zum Nachfragen — nie Treffer."""
    db, mcp, _ = umgebung
    db.add_application({"title": "Fachkraft", "company": "Personalservice Beispiel GmbH",
                        "status": "beworben"})
    erg = _call(mcp, "firma_kontext", {"firmenname": "Personal"})
    assert erg["gefunden"] is False, "ein Wortanfang ist kein Treffer"
    assert erg["bewerbungen"] == [] and erg["warnungen"] == []
    assert erg["aehnliche_firmen"] == ["Personalservice Beispiel GmbH"]
    assert "BEGINNEN" in erg["aehnliche_hinweis"]


def test_1148_ein_kurzer_wortanfang_nennt_nichts(umgebung):
    """'ki' darf nicht jede Firma finden, die so beginnt (Kita, Kiel, ...)."""
    db, mcp, _ = umgebung
    db.add_application({"title": "Fachkraft", "company": "Kita Sonnenschein e.V.",
                        "status": "beworben"})
    erg = _call(mcp, "firma_kontext", {"firmenname": "ki"})
    assert "aehnliche_firmen" not in erg


def test_1148_ein_ganzes_wort_ist_ein_treffer_und_kein_kandidat(umgebung):
    """`aehnliche_namen` nennt Namen, die mit der Suche BEGINNEN und NICHT ganz
    passen. Was als ganzes Wort passt, ist ein Treffer und steht dort — als
    Kandidat daneben hiesse es "keine Firma dieses Namens, aber diese beginnen
    so" und nennte dabei genau die Firma, die gefunden wurde."""
    db, mcp, _ = umgebung
    from bewerbungs_assistent.services import firmen_bezuege as fb
    db.add_application({"title": "Fachkraft", "company": "Personal Beispiel GmbH",
                        "status": "beworben"})
    db.add_application({"title": "Fachkraft", "company": "Personalservice Beispiel GmbH",
                        "status": "beworben"})
    assert fb.aehnliche_namen(db, "Personal") == ["Personalservice Beispiel GmbH"]


def test_1148_ein_echter_treffer_bekommt_keine_kandidatenliste(umgebung):
    db, mcp, _ = umgebung
    db.add_application({"title": "Fachkraft", "company": "Beispielwerk AG",
                        "status": "beworben"})
    db.add_application({"title": "Leitung", "company": "Beispielwerke Nord GmbH",
                        "status": "beworben"})
    erg = _call(mcp, "firma_kontext", {"firmenname": "Beispielwerk"})
    assert erg["gefunden"] is True
    assert "aehnliche_firmen" not in erg


# ══ Punkt 11: Loeschvorschauen mit Inhalt ═════════════════════════════════

def test_1148_die_kontakt_vorschau_nennt_den_kontakt_und_die_folgen(umgebung):
    db, mcp, _ = umgebung
    aid = _bewerbung(db)
    cid = db.add_contact({"full_name": "Erika Beispiel", "company": "Musterfirma GmbH",
                          "email": "erika@example.com"})
    db.link_contact(cid, "application", aid, role="recruiter")
    erg = _call(mcp, "kontakt_loeschen", {"kontakt_id": cid})
    assert erg["status"] == "bestaetigung_erforderlich"
    assert erg["kontakt"]["name"] == "Erika Beispiel"
    assert erg["kontakt"]["firma"] == "Musterfirma GmbH"
    assert "Kontakt-Verknüpfungen" in erg["folgen"]
    assert db.get_contact(cid) is not None, "die Vorschau hat geloescht"


def test_1148_der_kontakt_wird_mit_bestaetigung_geloescht(umgebung):
    db, mcp, _ = umgebung
    cid = db.add_contact({"full_name": "Erika Beispiel"})
    erg = _call(mcp, "kontakt_loeschen", {"kontakt_id": cid, "bestaetigung": True})
    assert erg["status"] == "geloescht"
    assert db.get_contact(cid) is None


def test_1148_ein_unbekannter_kontakt_wird_als_solcher_gemeldet(umgebung):
    db, mcp, _ = umgebung
    erg = _call(mcp, "kontakt_loeschen", {"kontakt_id": "nichtda1"})
    assert erg.get("fehler") == "Kontakt nicht gefunden."


def test_1148_die_termin_vorschau_nennt_den_termin(umgebung):
    db, mcp, _ = umgebung
    aid = _bewerbung(db)
    mid = db.add_meeting({"application_id": aid, "title": "Erstgespräch",
                          "meeting_date": "2026-10-20T10:00:00",
                          "meeting_type": "interview", "location": "Musterstadt"})
    erg = _call(mcp, "meeting_loeschen", {"meeting_id": mid})
    assert erg["status"] == "bestaetigung_erforderlich"
    assert erg["termin"]["titel"] == "Erstgespräch"
    assert erg["termin"]["datum"].startswith("2026-10-20")
    assert "Musterfirma GmbH" in erg["bewerbung"]
    assert "Termine" in erg["folgen"]


def test_1148_ein_unbekannter_termin_wird_als_solcher_gemeldet(umgebung):
    db, mcp, _ = umgebung
    erg = _call(mcp, "meeting_loeschen", {"meeting_id": "gibtsnicht"})
    assert "fehler" in erg


# ══ Punkt 4 (Code-Seite): die Werkzeugzahl wird gezaehlt, nicht geraten ═══════

def test_1148_pbp_capabilities_nennt_die_echte_werkzeugzahl(umgebung):
    """Gemessen: 'PBP-MCP bietet 109 Tools' bei 257 registrierten; `tools_gesamt`
    war null, weil es in FastMCP 3 keinen `_tool_manager` mehr gibt — und der Text
    nannte dann die kuratierte Zahl als Gesamtzahl."""
    db, mcp, _ = umgebung

    async def _alle():
        return len(await mcp.local_provider.list_tools())

    echt = asyncio.run(_alle())
    erg = _call(mcp, "pbp_capabilities")
    assert erg["tools_gesamt"] == echt and echt > 200
    assert erg["tools_sichtbar"] is not None and erg["tools_sichtbar"] <= erg["tools_gesamt"]
    assert erg["tools_kuratiert"] < erg["tools_gesamt"]
    assert f"{echt} Werkzeuge" in erg["ueberblick"]
    assert f"{erg['tools_kuratiert']} Tools in 11 Kategorien" not in erg["ueberblick"]


def test_1148_die_zaehlung_geht_auch_aus_einer_laufenden_schleife(umgebung):
    """`asyncio.run` gibt es nur ohne laufende Schleife; sonst zaehlt ein eigener Thread."""
    db, mcp, _ = umgebung
    from bewerbungs_assistent.tools.analyse import _werkzeugzahlen

    async def _innen():
        return _werkzeugzahlen(mcp)

    alle, sichtbar = asyncio.run(_innen())
    assert alle and sichtbar and sichtbar <= alle
