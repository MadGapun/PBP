"""Tests fuer v1.7.41 — #992: die Blacklist blockte unsichtbar.

Befund vom 07.09.2026. Beim Anlegen einer fachlich passenden Stelle
(MUSS-Begriff zweimal im Titel) kam:

    "Firma X steht auf der Blacklist (Zeitarbeit/Consulting — falsche
    Technologie-Stacks, kein PLM-Fit). Stelle nicht angelegt."

Zwei getrennte Probleme, beide im Issue benannt:

**1. Die Begruendung ist ein Gattungsurteil.** "Kein PLM-Fit" beschreibt
keine Firma, sondern eine Annahme ueber Personaldienstleister. Fuer genau
diesen Fall gibt es seit C31/#790 die Titel-Ausnahme.

**2. Die Blockade ist unsichtbar.** Wer die Stelle nicht zufaellig selbst
findet, erfaehrt nie, dass sie existiert hat.

Beim Nachsehen kam ein drittes dazu, und es ist das schwerste: **die
Entscheidung "blockt die Blacklist das" lag VIERMAL im Code, und die
Ausnahme aus #790 kannten nur zwei der vier Fassungen.**

* `is_company_blacklisted` — Substring, MIT Ausnahme
* `blacklist_anwenden` — Substring, MIT Ausnahme
* `_post_search_cleanup` (der SUCHLAUF) — Substring, OHNE Ausnahme
* `get_active_jobs(exclude_blacklisted=True)` (die LISTE) — Gleichheit
  statt Substring, OHNE Ausnahme

Wer die Ausnahme setzte, bekam die Stelle von Hand durch — und der
naechste Suchlauf warf sie wieder weg, ohne Spur. Die Tests unten pruefen
deshalb JEDEN der vier Wege einzeln gegen dieselbe Frage.
"""
import asyncio
import importlib
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1741_992_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    datenbank = _db_mod.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.save_profile({"name": "Test Person"})
    datenbank.set_search_criteria("keywords_muss", ["PLM", "PDM"])
    yield datenbank
    datenbank.close()
    os.environ.pop("BA_DATA_DIR", None)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import suche
    server = FastMCP("test")
    suche.register(server, db, logging.getLogger("test"))
    return server


def _call(server, name, args=None):
    async def _run():
        tool = await server.get_tool(name)
        res = await tool.run(args or {})
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _sperre(db, wert="Musterdienst", grund="Zeitarbeit/Consulting, kein Fit",
            ausnahmen=None):
    return db.add_to_blacklist("firma", wert, grund,
                               ausser_wenn_titel_enthaelt=ausnahmen or [])


def _stelle(titel="Senior PLM Architect", firma="Musterdienst GmbH", h="h1"):
    return {"hash": h, "title": titel, "company": firma,
            "url": "https://example.org/1", "source": "testquelle"}


# ── Der Kern: dieselbe Frage, vier Wege, EIN Ergebnis ─────────────────

def _vier_wege(db, titel, firma):
    """Beantwortet die Blacklist-Frage auf allen vier Wegen des Codes."""
    from bewerbungs_assistent.job_scraper import _post_search_cleanup
    job = _stelle(titel, firma)

    einzeln = db.is_company_blacklisted(firma, titel) is not None

    lauf = _post_search_cleanup(db, [dict(job)])
    suchlauf = lauf["stats"]["blacklist"] == 1

    db.save_jobs([dict(job)])
    sichtbar = [j for j in db.get_active_jobs(exclude_blacklisted=True)
                if j.get("title") == titel]
    liste = not sichtbar

    return {"einzeln": einzeln, "suchlauf": suchlauf, "liste": liste}


def test_992_ohne_ausnahme_blocken_alle_wege(db):
    _sperre(db)
    assert _vier_wege(db, "Senior PLM Architect", "Musterdienst GmbH") == {
        "einzeln": True, "suchlauf": True, "liste": True}


def test_992_mit_ausnahme_laesst_jeder_weg_durch(db):
    """Der eigentliche Fehler: der Suchlauf und die Liste kannten die
    Ausnahme aus #790 nicht. Vor dem Fix waren hier zwei von drei True."""
    _sperre(db, ausnahmen=["PLM"])
    assert _vier_wege(db, "Senior PLM Architect", "Musterdienst GmbH") == {
        "einzeln": False, "suchlauf": False, "liste": False}


def test_992_ausnahme_gilt_nur_fuer_den_passenden_titel(db):
    """Gegenprobe: die Firma bleibt geblockt, nur die Fachrolle kommt durch."""
    _sperre(db, ausnahmen=["PLM"])
    assert _vier_wege(db, "Naval Architect", "Musterdienst GmbH") == {
        "einzeln": True, "suchlauf": True, "liste": True}


def test_992_liste_matcht_jetzt_als_substring(db):
    """`get_active_jobs` verglich Firmen auf GLEICHHEIT statt als
    Substring — als einzige der vier Fassungen. Ein Eintrag 'Musterdienst'
    liess damit 'Musterdienst GmbH' in der Liste stehen, obwohl jeder
    andere Weg sie wegwarf."""
    _sperre(db, wert="Musterdienst")
    db.save_jobs([_stelle("Naval Architect", "Musterdienst GmbH")])
    sichtbar = db.get_active_jobs(exclude_blacklisted=True)
    assert not [j for j in sichtbar if j.get("company") == "Musterdienst GmbH"]


def test_992_blacklist_anwenden_verschont_die_ausnahme(db):
    from bewerbungs_assistent.tools import suche as suche_mod
    from fastmcp import FastMCP
    srv = FastMCP("t")
    suche_mod.register(srv, db, logging.getLogger("t"))
    _sperre(db, ausnahmen=["PLM"])
    db.save_jobs([_stelle("Senior PLM Architect", "Musterdienst GmbH", "hA"),
                  _stelle("Naval Architect", "Musterdienst GmbH", "hB")])
    res = _call(srv, "blacklist_anwenden", {"dry_run": True})
    betroffen = [v["titel"] for v in res.get("vorschau", [])]
    assert "Naval Architect" in str(betroffen) or res.get("betroffen") == 1
    assert [v["titel"] for v in res.get("durch_ausnahme_verschont", [])] == [
        "Senior PLM Architect"]


def test_992_zweiter_eintrag_hebelt_die_ausnahme_nicht_aus(db):
    """Sonst haengt das Ergebnis an der Reihenfolge der Eintraege."""
    _sperre(db, wert="Musterdienst", ausnahmen=["PLM"])
    _sperre(db, wert="Musterdienst GmbH", grund="Dublette ohne Ausnahme")
    assert db.is_company_blacklisted("Musterdienst GmbH",
                                     "Senior PLM Architect") is None


# ── Das Protokoll: die Blockade wird sichtbar ─────────────────────────

def test_992_suchlauf_protokolliert_die_blockade(db):
    from bewerbungs_assistent.job_scraper import _post_search_cleanup
    _sperre(db)
    _post_search_cleanup(db, [_stelle()])
    protokoll = db.get_blacklist_blocks()
    assert len(protokoll) == 1
    eintrag = protokoll[0]
    assert eintrag["titel"] == "Senior PLM Architect"
    assert eintrag["firma"] == "Musterdienst GmbH"
    assert eintrag["eintrag_wert"] == "Musterdienst"
    assert eintrag["kontext"] == "suchlauf"
    assert eintrag["grund"]


def test_992_abweisung_von_hand_wird_protokolliert(db):
    """Gerade die selbst gefundenen Stellen duerfen nicht fehlen — der
    gemeldete Fall war genau einer davon."""
    from bewerbungs_assistent.tools import jobs as jobs_mod
    from fastmcp import FastMCP
    srv = FastMCP("t")
    jobs_mod.register(srv, db, logging.getLogger("t"))
    _sperre(db)
    res = _call(srv, "stelle_manuell_anlegen", {
        "titel": "Senior PLM Architect", "firma": "Musterdienst GmbH",
        "url": "https://example.org/1"})
    assert "Blacklist" in res.get("fehler", "")
    protokoll = db.get_blacklist_blocks()
    assert [p["kontext"] for p in protokoll] == ["manuell_abgewiesen"]


def test_992_protokoll_bleibt_gekappt(db):
    """Ein Vorschlag ohne Grenze ist auch eine Datenmenge (#991)."""
    from bewerbungs_assistent.services.blacklist_regel import PROTOKOLL_MAX
    hit = {"typ": "firma", "wert": "Musterdienst", "eintrag_id": 1, "grund": "x"}
    for i in range(PROTOKOLL_MAX + 25):
        db.record_blacklist_block({"title": f"Stelle {i}",
                                   "company": "Musterdienst GmbH"}, hit)
    assert len(db.get_blacklist_blocks(limit=5000)) == PROTOKOLL_MAX


def test_992_protokoll_bricht_den_suchlauf_nie_ab(db, monkeypatch):
    """Ein Protokoll ist Beiwerk — es darf keine Suche kosten."""
    from bewerbungs_assistent.job_scraper import _post_search_cleanup
    _sperre(db)
    monkeypatch.setattr(db, "connect",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("kaputt")))
    # Der Aufruf darf nicht werfen; das Ergebnis bleibt korrekt.
    db.record_blacklist_block({"title": "x", "company": "y"}, {"typ": "firma"})


# ── blacklist_wirkung: die Auskunft ───────────────────────────────────

def test_992_wirkung_ohne_blacklist_ist_keine_sackgasse(db, mcp):
    res = _call(mcp, "blacklist_wirkung")
    assert res["status"] == "leer"
    assert "blacklist_verwalten" in res["hinweis"]


def test_992_wirkung_nennt_die_geblockten_stellen(db, mcp):
    from bewerbungs_assistent.job_scraper import _post_search_cleanup
    _sperre(db)
    _post_search_cleanup(db, [_stelle()])
    res = _call(mcp, "blacklist_wirkung")
    assert res["geblockt_protokolliert"] == 1
    assert res["letzte_blockaden"][0]["titel"] == "Senior PLM Architect"
    assert res["letzte_blockaden"][0]["muss_begriffe"] == ["PLM"]


def test_992_wirkung_warnt_bei_muss_kollision(db, mcp):
    from bewerbungs_assistent.job_scraper import _post_search_cleanup
    _sperre(db)
    _post_search_cleanup(db, [_stelle()])
    res = _call(mcp, "blacklist_wirkung")
    assert res["muss_kollisionen_offen"] == 1
    assert "MUSS-Begriff" in res["warnung"]
    treffer = [e for e in res["eintraege"] if e["muss_kollisionen"]]
    assert treffer and "ausser_wenn_titel_enthaelt" in treffer[0]["empfehlung"]


def test_992_gesetzte_ausnahme_beendet_die_ermahnung(db, mcp):
    """Das Protokoll ist Vergangenheit, das Urteil ist Gegenwart.

    Wer die Ausnahme gesetzt hat, soll nicht weiter fuer ein Problem
    ermahnt werden, das er geloest hat — sonst wird die Auskunft
    ignoriert (die Fehlalarm-Lehre aus DoD-9).
    """
    from bewerbungs_assistent.job_scraper import _post_search_cleanup
    eid = _sperre(db)
    _post_search_cleanup(db, [_stelle()])
    db.update_blacklist_entry(eid, ausser_wenn_titel_enthaelt=["PLM"])
    res = _call(mcp, "blacklist_wirkung")
    assert res["muss_kollisionen_offen"] == 0
    assert "warnung" not in res
    assert "kaemen inzwischen durch" in res["hinweis_behoben"]


def test_992_wirkung_nennt_gattungsurteil_und_alter(db, mcp):
    _sperre(db)
    res = _call(mcp, "blacklist_wirkung")
    eintrag = res["eintraege"][0]
    assert sorted(eintrag["gattungswoerter"]) == ["consulting", "zeitarbeit"]
    assert eintrag["alter_tage"] == 0
    assert "ausser_wenn_titel_enthaelt" in eintrag["empfehlung"]


def test_992_eintrag_ohne_begruendung_wird_benannt(db, mcp):
    """Fuenf der 24 Firmen-Eintraege im Praxisbestand hatten gar keinen
    Grund — die kann auch der Mensch selbst nie mehr pruefen."""
    _sperre(db, wert="Namenlos", grund="")
    res = _call(mcp, "blacklist_wirkung")
    eintrag = [e for e in res["eintraege"] if e["wert"] == "Namenlos"][0]
    assert "Ohne Begruendung" in eintrag["empfehlung"]


def test_992_nur_auffaellige_filtert(db, mcp):
    _sperre(db, wert="Sauber",
            grund="Zweimal beworben, nie eine Antwort bekommen")
    _sperre(db, wert="Musterdienst")
    res = _call(mcp, "blacklist_wirkung", {"nur_auffaellige": True})
    assert [e["wert"] for e in res["eintraege"]] == ["Musterdienst"]
    assert res["eintraege_gesamt"] == 2


def test_992_leeres_protokoll_erklaert_sich(db, mcp):
    _sperre(db)
    res = _call(mcp, "blacklist_wirkung")
    assert "v1.7.41" in res["hinweis_protokoll"]


# ── Der Hinweis beim Anlegen ──────────────────────────────────────────

def test_992_anlegen_nennt_die_ausnahme_als_ausweg(db, mcp):
    """Der Hinweis auf `ausser_wenn_titel_enthaelt` kam bisher erst, wenn
    eine Stelle schon abgewiesen war — im schlechtestmoeglichen Moment."""
    res = _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Musterdienst",
        "grund": "Zeitarbeit/Consulting, kein Fit"})
    assert "ausser_wenn_titel_enthaelt" in res["hinweis_grund"]


def test_992_anlegen_warnt_vor_muss_kollision(db, mcp):
    """Der maschinell erkennbare Widerspruch, im richtigen Moment."""
    db.save_jobs([_stelle("PLM Consultant", "Musterdienst GmbH")])
    res = _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Musterdienst",
        "grund": "Zeitarbeit"})
    assert res["muss_kollisionen"][0]["muss_begriffe"] == ["PLM"]
    assert "PLM" in res["warnung_muss"]
    assert f"entry_id={res['entry_id']}" in res["warnung_muss"]


def test_992_warnung_entfaellt_wenn_die_ausnahme_gleich_mitkommt(db, mcp):
    db.save_jobs([_stelle("PLM Consultant", "Musterdienst GmbH")])
    res = _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Musterdienst",
        "grund": "Zeitarbeit", "ausser_wenn_titel_enthaelt": ["PLM"]})
    assert "warnung_muss" not in res


def test_992_keine_warnung_ohne_kollision(db, mcp):
    """Gegenprobe — sonst warnt PBP bei jedem Eintrag und wird ignoriert."""
    db.save_jobs([_stelle("Naval Architect", "Musterdienst GmbH")])
    res = _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Musterdienst",
        "grund": "Zweimal beworben, nie eine Antwort"})
    assert "warnung_muss" not in res
    assert "hinweis_grund" not in res


def test_992_auch_aussortierte_stellen_zaehlen_fuer_die_kollision(db, mcp):
    """Gerade die aussortierten sind der Anlass fuer den Eintrag."""
    db.save_jobs([_stelle("PLM Consultant", "Musterdienst GmbH", "hX")])
    treffer = [j for j in db.get_active_jobs()
               if j.get("title") == "PLM Consultant"][0]
    db.dismiss_job(treffer["hash"], "falsches_fachgebiet")
    res = _call(mcp, "blacklist_verwalten", {
        "aktion": "hinzufuegen", "typ": "firma", "wert": "Musterdienst",
        "grund": "Zeitarbeit"})
    assert res["muss_kollisionen"][0]["titel"] == "PLM Consultant"


# ── Regel-Modul direkt ────────────────────────────────────────────────

def test_992_alter_tage_rechnet_aus_created_at():
    from bewerbungs_assistent.services import blacklist_regel
    vor = (datetime.now(timezone.utc) - timedelta(days=200)).isoformat()
    assert blacklist_regel.alter_tage({"created_at": vor}) == 200
    assert blacklist_regel.alter_tage({"created_at": ""}) is None
    assert blacklist_regel.alter_tage({"created_at": "kein datum"}) is None


def test_992_altes_gattungsurteil_wird_zur_pruefung_vorgeschlagen():
    from bewerbungs_assistent.services import blacklist_regel as br
    vor = (datetime.now(timezone.utc)
           - timedelta(days=br.PRUEF_INTERVALL_TAGE + 5)).isoformat()
    eintraege = [{"id": 1, "type": "firma", "value": "Musterdienst",
                  "reason": "Zeitarbeit", "created_at": vor,
                  "ausser_wenn_titel_enthaelt": ["PLM"]}]
    befund = br.befund(eintraege, {"keywords_muss": ["PLM"]})
    assert "Gegenprobe" in befund[0]["empfehlung"]


def test_992_keyword_eintraege_greifen_nur_wo_sie_sollen():
    from bewerbungs_assistent.services import blacklist_regel as br
    eintraege = [{"id": 2, "type": "keyword", "value": "Holzbau",
                  "reason": "", "ausser_wenn_titel_enthaelt": []}]
    assert br.treffer(eintraege, "Andere AG", "Bauleiter Holzbau")["typ"] == "keyword"
    # Beim Anlegen EINER Stelle entscheidet der Mensch — ein Keyword darf
    # dort nicht stillschweigend mitblocken.
    assert br.treffer(eintraege, "Andere AG", "Bauleiter Holzbau",
                      typen=("firma",)) is None


def test_992_befund_sortiert_das_dringendste_nach_oben():
    from bewerbungs_assistent.services import blacklist_regel as br
    eintraege = [
        {"id": 1, "type": "firma", "value": "Sauber", "reason": "Nie Antwort",
         "created_at": "", "ausser_wenn_titel_enthaelt": []},
        {"id": 2, "type": "firma", "value": "Ohnegrund", "reason": "",
         "created_at": "", "ausser_wenn_titel_enthaelt": []},
        {"id": 3, "type": "firma", "value": "Gattung", "reason": "Zeitarbeit",
         "created_at": "", "ausser_wenn_titel_enthaelt": []},
        {"id": 4, "type": "firma", "value": "Kollision", "reason": "Zeitarbeit",
         "created_at": "", "ausser_wenn_titel_enthaelt": []},
    ]
    blockaden = [{"eintrag_wert": "Kollision", "titel": "PLM Architect",
                  "firma": "Kollision", "blockiert_am": "2026-09-07"}]
    befund = br.befund(eintraege, {"keywords_muss": ["PLM"]}, blockaden)
    assert [e["wert"] for e in befund] == ["Kollision", "Gattung",
                                           "Ohnegrund", "Sauber"]


# ── pbp_diagnose (AK 4) ───────────────────────────────────────────────

def _diagnose(db):
    from bewerbungs_assistent.tools import analyse
    from fastmcp import FastMCP
    srv = FastMCP("d")
    analyse.register(srv, db, logging.getLogger("d"))
    return _call(srv, "pbp_diagnose")


def test_992_diagnose_weist_die_geblockten_stellen_aus(db):
    """AK 4 des Issues — die Zahl gehoert dorthin, wo man sie ohne
    Vorwissen findet."""
    from bewerbungs_assistent.job_scraper import _post_search_cleanup
    _sperre(db)
    _post_search_cleanup(db, [_stelle()])
    res = _diagnose(db)
    text = str(res)
    assert "von der Blacklist" in text and "blacklist_wirkung" in text


def test_992_diagnose_warnt_bei_muss_kollision(db):
    from bewerbungs_assistent.job_scraper import _post_search_cleanup
    _sperre(db)
    _post_search_cleanup(db, [_stelle()])
    res = _diagnose(db)
    treffer = [w for w in res.get("warnungen", [])
               if w.get("bereich") == "Blacklist"
               and "MUSS-Begriff" in w.get("problem", "")]
    assert treffer, res.get("warnungen")


def test_992_diagnose_nennt_eintraege_ohne_begruendung(db):
    _sperre(db, wert="Namenlos", grund="")
    res = _diagnose(db)
    treffer = [w for w in res.get("warnungen", [])
               if w.get("bereich") == "Blacklist"
               and "ohne Begruendung" in w.get("problem", "")]
    assert treffer, res.get("warnungen")


def test_992_diagnose_bleibt_still_ohne_befund(db):
    """Ein Pruefer, der bei korrektem Zustand Alarm gibt, wird ignoriert."""
    _sperre(db, wert="Sauber", grund="Zweimal beworben, nie eine Antwort")
    res = _diagnose(db)
    assert not [w for w in res.get("warnungen", [])
                if w.get("bereich") == "Blacklist"]
