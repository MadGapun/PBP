"""#1066 — Monster war seit #653 als `deprecated` markiert und wurde
trotzdem weiter angeboten.

Gemeldet am 21.09.2026, nachgemessen vom Melder: monster.de antwortet
mit 302 auf monster.com/de/, dort steht nur noch Werbung fuer einen
Lebenslauf-Generator, und das Onboarding fragt nach einer
US-Arbeitserlaubnis. Der Melder hat sein Konto geloescht.

`deprecated` hat nicht gereicht. Die Quelle stand weiter mit
`zugriffsart: browser_login` und Konto-Link in der Quellenliste, bekam
ein eigenes Zeitbudget, eine Prioritaet, einen Platz in der
Playwright-Liste und im Claude-Handoff (#1049) — und mit #1060 sogar
noch einen neuen Kartentext. Der Mensch bekam also einen kopierbaren
Prompt, mit dem Claude auf einer Seite ohne Stellen suchen soll.

Deshalb generisch geloest (`ENTFERNTE_QUELLEN`) statt als Sonderfall:
dieselbe Frage kommt bei StepStone wieder.
"""
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.job_scraper import (  # noqa: E402
    ENTFERNTE_QUELLEN, SOURCE_REGISTRY)


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17122_1066_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    d = _db_mod.Database()
    d.initialize()
    assert str(tmpdir) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test"})
    yield d
    d.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


# ══ Die Quelle ist weg ══════════════════════════════════════════════

def test_1066_monster_ist_keine_waehlbare_quelle():
    """AK 1: nicht mehr in der Registry — damit auch nicht in
    Quellenkarten, Handoff und Suchlauf."""
    assert "monster" not in SOURCE_REGISTRY


def test_1066_keine_spur_im_laufwerk():
    """AK 1: Dispatch, Zeitbudget, Playwright-Liste, Prioritaet."""
    quelle = (ROOT / "src/bewerbungs_assistent/job_scraper/__init__.py").read_text(
        encoding="utf-8-sig")
    for stelle in ('"monster": ("monster"', '"monster": 120',
                   '"monster": 13', '"indeed", "monster"',
                   '"monster_queries"'):
        assert stelle not in quelle, stelle


def test_1066_der_scraper_ist_nicht_mehr_im_import_pfad():
    """AK 2."""
    assert not (ROOT / "src/bewerbungs_assistent/job_scraper/monster.py").exists()


#: Wo "Monster" stehen DARF — je Datei mit Begruendung. Eine
#: Ausnahmeliste ohne Grund waechst beliebig (#1004/#1005, #1025).
ERLAUBT = {
    "url_to_source.py": "Altbestand: monster-URLs brauchen weiter eine Quelle (AK 4).",
    "job_scraper/__init__.py": "ENTFERNTE_QUELLEN — die Erinnerung, warum die Quelle weg ist.",
    "services/onboarding_hints.py": "Docstring, der den einmaligen Hinweis begruendet.",
}


def test_1066_grep_trifft_nur_noch_die_url_erkennung():
    """AK 6 woertlich: `grep -ri monster src/` trifft nur noch das,
    was den Altbestand traegt oder den Wegfall erklaert."""
    treffer = []
    for f in (ROOT / "src" / "bewerbungs_assistent").rglob("*.py"):
        rel = f.relative_to(ROOT / "src" / "bewerbungs_assistent").as_posix()
        if any(rel.endswith(e) for e in ERLAUBT):
            continue
        if "monster" in f.read_text(encoding="utf-8-sig").lower():
            treffer.append(rel)
    assert not treffer, treffer


def test_1066_jede_ausnahme_traegt_ihren_grund():
    for datei, grund in ERLAUBT.items():
        assert len(grund) > 25, datei


def test_1066_altbestand_behaelt_seine_quelle(db):
    """AK 4: gespeicherte Stellen bleiben lesbar und behalten die Quelle."""
    from bewerbungs_assistent.services.url_to_source import detect_source_from_url
    assert detect_source_from_url("https://www.monster.de/job/xyz") == "monster"
    db.save_jobs([{
        "hash": "k1066alt", "title": "Alte Stelle", "company": "Musterbetrieb",
        "url": "https://www.monster.de/job/xyz", "source": "monster",
        "description": "Ein Anzeigentext. " * 10,
    }])
    stellen = [j for j in db.get_active_jobs() if j["hash"].endswith("k1066alt")]
    assert len(stellen) == 1
    assert stellen[0]["source"] == "monster"


# ══ Was mit einer gewaehlten Quelle passiert ════════════════════════

def test_1066_gewaehlte_quelle_faellt_aus_der_auswahl(db):
    """AK 3: der Haken verschwindet — und zwar im SPEICHER, nicht nur in
    der Anzeige. Ein Schluessel, den die Registry nicht kennt, waere
    sonst unsichtbar stehen geblieben (#1039/#1008)."""
    from bewerbungs_assistent.services import search_service
    db.set_profile_setting("active_sources", ["bundesagentur", "monster", "hays"])
    bereinigt = search_service.aktive_quellen(db)
    assert bereinigt == ["bundesagentur", "hays"]
    assert db.get_profile_setting("active_sources", None) == ["bundesagentur", "hays"]


def test_1066_der_wegfall_wird_einmal_benannt(db):
    """AK 3: kein stiller Wegfall (#211). Der Hinweis nennt Grund und
    Ersatz."""
    from bewerbungs_assistent.services import onboarding_hints, search_service
    db.set_profile_setting("active_sources", ["bundesagentur", "monster"])
    search_service.aktive_quellen(db)
    hints = {h["id"]: h for h in onboarding_hints.list_active_hints(db)}
    hinweis = hints.get("b59_quelle_entfernt")
    assert hinweis is not None
    assert "Monster" in hinweis["detail"]
    assert "keine deutschen Stellenanzeigen" in hinweis["detail"]
    # Der Ersatz wird beim Namen genannt, nicht als Schluessel.
    assert SOURCE_REGISTRY["jobspy_indeed"]["name"] in hinweis["detail"]


def test_1066_ohne_entfernte_quelle_kein_hinweis(db):
    """Die Gegenrichtung: ein Hinweis, der immer steht, wird Tapete
    (#929)."""
    from bewerbungs_assistent.services import onboarding_hints, search_service
    db.set_profile_setting("active_sources", ["bundesagentur", "hays"])
    search_service.aktive_quellen(db)
    ids = {h["id"] for h in onboarding_hints.list_active_hints(db)}
    assert "b59_quelle_entfernt" not in ids


# ══ Der generische Mechanismus ══════════════════════════════════════

def test_1066_entfernte_quellen_tragen_ihren_grund():
    """AK 6 des Berichts: generisch loesen, nicht als Sonderfall — bei
    StepStone kommt dieselbe Frage. Eine Liste ohne Aufnahmekriterium
    waechst beliebig (#1004/#1005)."""
    assert ENTFERNTE_QUELLEN, "Die Liste ist der Ort fuer das Warum."
    for schluessel, eintrag in ENTFERNTE_QUELLEN.items():
        assert schluessel not in SOURCE_REGISTRY, schluessel
        assert eintrag["name"]
        assert eintrag["entfernt_am"]
        assert len(eintrag["grund"]) > 30, schluessel
