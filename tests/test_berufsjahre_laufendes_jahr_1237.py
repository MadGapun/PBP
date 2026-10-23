"""#1237: "bis heute" rechnet mit der Uhr, nie mit einer Jahreszahl im Code.

Bis v1.7.158 setzte PBP an drei Stellen fuer ein offenes Ende eine feste
2026 ein:

* `services/auto_aussortierung.py` - die Karrierestufe, die die lokale KI
  beim Aussortieren bekommt ("Mid-Level (8 Jahre Erfahrung)");
* `export._score_recruiter` - die Jahre Berufserfahrung der Recruiter-Wertung;
* `export._detect_career_gaps` - das Ende einer laufenden Station.

Ab dem 01.01.2027 fehlte damit bei jeder laufenden Position ein Jahr, ab 2028
zwei; die Stufe kippte an den Grenzen 4/5 und 9/10 Jahre zu spaet. Jetzt kommt
das Jahr aus `services/uhr.heute()`, und EINE Rechnung
(`berufsfeld.berufsjahre`) bedient Einordnung und Auto-Aussortierung.

Die Tests setzen die Uhr auf feste Tage vor, in und nach 2026 - in BEIDE
Richtungen: eine feste Zahl rechnet davor zu viel und danach zu wenig. Ein
Test mit dem Datum von heute wuerde den Fehler bis zum 31.12.2026 nie zeigen.

Der Waechter (`festjahre_finden`) haelt Jahreszahlen als Festwert aus dem
Quelltext; seine Gegenproben stehen darunter (er findet die drei alten
Fundstellen und laesst Harmloses in Ruhe).
"""
from __future__ import annotations

import ast
import logging
import tomllib
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from bewerbungs_assistent.services import berufsfeld, uhr

WURZEL = Path(__file__).resolve().parent.parent
SRC = WURZEL / "src"

# Vor 2026, in 2026, nach dem Jahreswechsel, weit danach.
VOR, IN, NACH, WEIT = date(2025, 12, 31), date(2026, 10, 17), date(2027, 1, 1), date(2030, 6, 15)


def _uhr_auf(monkeypatch, tag: date) -> None:
    monkeypatch.setattr(uhr, "heute", lambda: tag)


# ===== Die Uhr ==============================================================

def test_uhr_liest_die_echte_uhr():
    vorher = date.today()
    erg = uhr.heute()
    nachher = date.today()
    assert type(erg) is date, "ein date, kein datetime"
    assert vorher <= erg <= nachher


# ===== berufsjahre: ein offenes Ende zaehlt bis zum Tag der Uhr =============

@pytest.mark.parametrize("tag, erwartet", [
    (VOR, 7),    # eine feste 2026 rechnete hier 8 (zu viel)
    (IN, 8),
    (NACH, 9),   # eine feste 2026 rechnet hier 8 (zu wenig)
    (WEIT, 12),
])
@pytest.mark.parametrize("ende", [None, ""])
def test_offene_position_zaehlt_bis_zum_jahr_der_uhr(monkeypatch, tag, erwartet, ende):
    _uhr_auf(monkeypatch, tag)
    assert berufsfeld.berufsjahre([{"start_date": "2018-03", "end_date": ende}]) == erwartet


def test_fehlender_schluessel_end_date_zaehlt_als_offen(monkeypatch):
    _uhr_auf(monkeypatch, NACH)
    assert berufsfeld.berufsjahre([{"start_date": "2018-03"}]) == 9


def test_beendete_position_haengt_nicht_vom_tag_ab(monkeypatch):
    pos = [{"start_date": "2010-01", "end_date": "2015-06"}]
    for tag in (VOR, IN, NACH, WEIT):
        _uhr_auf(monkeypatch, tag)
        assert berufsfeld.berufsjahre(pos) == 5, tag


def test_summe_mehrerer_stationen_mit_platzhaltern(monkeypatch):
    _uhr_auf(monkeypatch, date(2027, 3, 1))
    pos = [
        {"start_date": "2010-01", "end_date": "2014-12"},   # 4
        {"start_date": "2015", "end_date": ""},             # 12 (offen, bis 2027)
        {"start_date": None, "end_date": None},             # Platzhalter: zaehlt nicht
        {"start_date": "0000", "end_date": "2020"},         # Platzhalter: zaehlt nicht
        {"start_date": "2030-01", "end_date": ""},          # beginnt spaeter: nie negativ
    ]
    assert berufsfeld.berufsjahre(pos) == 16


def _alte_schleife(positions: list, offen_jahr: int) -> int:
    """Die Rechnung aus `services/auto_aussortierung.py` bis v1.7.158 - mit dem
    Jahr fuer das offene Ende als Parameter statt der festen 2026."""
    years = 0
    for p in positions:
        try:
            start = int((p.get("start_date") or "0000")[:4])
            end_raw = (p.get("end_date") or "")[:4]
            end = int(end_raw) if end_raw.isdigit() else offen_jahr
            if start > 1900:
                years += max(0, end - start)
        except Exception:
            pass
    return years


def test_eine_rechnung_gleicher_wert_wie_die_alte_schleife(monkeypatch):
    """Die Auto-Aussortierung rechnet jetzt mit `berufsjahre`. Auf allen Werten,
    die die Datenbank liefern kann (Text oder NULL), kommt dasselbe heraus wie
    mit der alten Schleife - nur das Jahr des offenen Endes ist ein anderes.
    (1900 als Anfang ist ein Platzhalter und kommt nicht vor.)"""
    anfaenge = ["2018-03", "2018", "1999-12-31", "2005-07", "0000", "", None,
                "abcd", "03.2019", "1899-05", "2030-01", "2026-01"]
    enden = [None, "", "2020-05", "2017", "xx", "2030", "2026-12", "2027"]
    for tag in (VOR, IN, NACH, date(2031, 5, 5)):
        _uhr_auf(monkeypatch, tag)
        for a in anfaenge:
            for e in enden:
                pos = [{"start_date": a, "end_date": e}]
                assert berufsfeld.berufsjahre(pos) == _alte_schleife(pos, tag.year), (tag, a, e)
        mehrere = [{"start_date": a, "end_date": e} for a in anfaenge[:5] for e in enden[:5]]
        assert berufsfeld.berufsjahre(mehrere) == _alte_schleife(mehrere, tag.year), tag


# ===== Auto-Aussortierung: die Stufe im Prompt der KI folgt der Uhr =========

class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None, **_kwargs):
        def decorator(fn):
            self.tools[name or fn.__name__] = fn
            return fn
        return decorator


class _FakeLLM:
    """Lokale KI, die alles als PASST_NICHT einstuft und den Auftrag mitschreibt."""

    def __init__(self):
        self.auftraege = []

    def get_status(self, force_refresh=False):
        return SimpleNamespace(ollama_available=True, available_models=["mock-modell"],
                               user_state="active", selected_model="mock-modell")

    def warmup(self):
        return {"status": "warm", "duration_sec": 0.01}

    def run(self, kind, payload):
        self.auftraege.append(payload)
        return SimpleNamespace(success=True, payload={"decision": "PASST_NICHT", "reason": "Mock"},
                               fallback_message="")


def _stufe_im_prompt(tmp_db, tmp_path, monkeypatch, anfang: str, tag: date) -> str:
    """Profil mit EINER laufenden Position seit `anfang`; liefert die Stufe, die die KI bekommt."""
    assert str(tmp_path) in str(tmp_db.db_path), f"DB nicht isoliert: {tmp_db.db_path}"
    tmp_db.create_profile("Test", "test@example.com")
    tmp_db.add_position({"company": "Beispiel AG", "title": "Entwickler", "start_date": anfang,
                         "end_date": None, "is_current": True})
    pid = tmp_db.get_active_profile_id() or ""
    tmp_db.save_jobs([{
        "hash": f"{pid}:stufe1", "title": "Softwareentwickler", "company": "Testfirma GmbH",
        "location": "Hamburg", "url": "https://x/stufe1", "source": "manuell", "score": 40,
        "description": "Wir suchen Verstaerkung fuer unser Team. " * 5,
    }])
    fake = _FakeLLM()
    monkeypatch.setattr("bewerbungs_assistent.services.llm_service.get_llm_service", lambda db: fake)
    _uhr_auf(monkeypatch, tag)
    from bewerbungs_assistent.tools.jobs import register
    mcp = _FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    ergebnis = mcp.tools["stellen_auto_aussortieren"](max_stellen=10)
    assert ergebnis["status"] == "ok", ergebnis
    assert len(fake.auftraege) == 1
    return fake.auftraege[0]["profile_seniority"]


@pytest.mark.parametrize("anfang, tag, erwartet", [
    # davor: eine feste 2026 hob die Stufe zu frueh
    ("2021-06", VOR, "Junior (4 Jahre Erfahrung)"),
    # die Grenze 4 -> 5 Jahre
    ("2022-01", IN, "Junior (4 Jahre Erfahrung)"),
    ("2022-01", NACH, "Mid-Level (5 Jahre Erfahrung)"),
    # die Grenze 9 -> 10 Jahre
    ("2017-05", IN, "Mid-Level (9 Jahre Erfahrung)"),
    ("2017-05", NACH, "Senior (10 Jahre Erfahrung)"),
    # die Grenze 0 -> 1 Jahr
    ("2026-02", IN, "Berufseinsteiger / Berufsanfänger"),
    ("2026-02", NACH, "Junior (1 Jahre Erfahrung)"),
])
def test_stufe_der_auto_aussortierung_folgt_der_uhr(tmp_db, tmp_path, monkeypatch, anfang, tag, erwartet):
    assert _stufe_im_prompt(tmp_db, tmp_path, monkeypatch, anfang, tag) == erwartet


# ===== Lebenslauf-Wertung und Luecken-Erkennung (export.py) =================

@pytest.mark.parametrize("tag, jahre, punkte", [
    (VOR, 8, 8),     # eine feste 2026 rechnete 9
    (IN, 9, 8),
    (NACH, 10, 12),  # eine feste 2026 bleibt bei 9 (8 Punkte)
    (WEIT, 13, 12),
])
def test_recruiter_wertung_zaehlt_die_laufende_station_bis_heute(monkeypatch, tag, jahre, punkte):
    from bewerbungs_assistent.export import _score_recruiter
    _uhr_auf(monkeypatch, tag)
    pos = [{"start_date": "2017-05", "end_date": None, "is_current": True}]
    erg = _score_recruiter({}, [], pos, "", set())
    assert f"~{jahre} Jahre Berufserfahrung" in erg["faktoren"], erg["faktoren"]
    # ohne weitere Angaben tragen nur die Berufsjahre Punkte bei
    assert erg["score"] == punkte


def test_beendete_station_in_der_recruiter_wertung_haengt_nicht_vom_tag_ab(monkeypatch):
    from bewerbungs_assistent.export import _score_recruiter
    pos = [{"start_date": "2010-01", "end_date": "2016-06", "is_current": False}]
    for tag in (VOR, NACH):
        _uhr_auf(monkeypatch, tag)
        assert "~6 Jahre Berufserfahrung" in _score_recruiter({}, [], pos, "", set())["faktoren"]


def test_luecke_nach_laufender_station_rechnet_bis_heute(monkeypatch):
    from bewerbungs_assistent.export import _detect_career_gaps
    pos = [
        {"start_date": "2015-01", "end_date": None, "is_current": True},  # laeuft: endet "heute"
        {"start_date": "2026-11", "end_date": "2027-06"},                 # beginnt spaeter
    ]
    # Dezember 2026: beide Stationen laufen nebeneinander, keine Luecke.
    # (Eine feste Zahl 2026-03 meldete hier acht Monate Luecke.)
    _uhr_auf(monkeypatch, date(2026, 12, 20))
    assert _detect_career_gaps(pos) == []
    # Juni 2025: die laufende Station endet "heute", bis November 2026 sind es 17 Monate.
    # (Eine feste Zahl 2026-03 meldete acht.)
    _uhr_auf(monkeypatch, date(2025, 6, 15))
    luecken = _detect_career_gaps(pos)
    assert len(luecken) == 1 and luecken[0]["months"] == 17, luecken


# ===== Der Waechter: keine Jahreszahl als Festwert im Quelltext =============

#: Jahre, in denen PBP geschrieben wird oder bald gelesen: eine Zahl in diesem
#: Fenster ist im Code fast immer "das laufende Jahr", einmal von Hand getippt.
#: Runde Grenzen (2000) und Groessen (2048) liegen ausserhalb.
JAHR_VON, JAHR_BIS = 2020, 2039

#: Wo eine Jahreszahl im Code einen Grund hat (ein Stichtag, eine Studie), steht
#: am Ende der Zeile `# jahreszahl-ok: <Grund>`. Ohne Grund zaehlt die Marke nicht.
MARKE = "jahreszahl-ok:"


def _ist_jahr(wert) -> bool:
    if isinstance(wert, int):  # auch True/False sind int, liegen aber nie im Fenster
        return JAHR_VON <= wert <= JAHR_BIS
    if isinstance(wert, str):
        return len(wert) == 4 and wert.isdigit() and JAHR_VON <= int(wert) <= JAHR_BIS
    return False


def festjahre_finden(quelltext: str) -> list[tuple[int, str]]:
    """(Zeile, Text) jeder Jahreszahl, die als Zahl oder reine Jahres-Zeichenkette im Code steht.

    Arbeitet auf dem Syntaxbaum: Kommentare, Docstrings und Datumstexte
    ("2026-05-01") zaehlen nicht, `else 2026` und `datetime(2027, 1, 1)` schon.
    """
    zeilen = quelltext.splitlines()
    funde = []
    for knoten in ast.walk(ast.parse(quelltext)):
        if not isinstance(knoten, ast.Constant) or not _ist_jahr(knoten.value):
            continue
        zeile = zeilen[knoten.lineno - 1]
        kommentar = zeile.partition("#")[2]
        if MARKE in kommentar and kommentar.partition(MARKE)[2].strip():
            continue  # die Zahl hat einen genannten Grund
        funde.append((knoten.lineno, zeile.strip()))
    return sorted(funde)


def _quelldateien() -> list[Path]:
    return sorted(p for p in SRC.rglob("*.py") if "static" not in p.parts)


def test_waechter_quelltext_hat_keine_festen_jahreszahlen():
    funde = []
    for pfad in _quelldateien():
        for zeile, text in festjahre_finden(pfad.read_text(encoding="utf-8-sig")):
            funde.append(f"{pfad.relative_to(SRC).as_posix()}:{zeile}: {text}")
    assert not funde, (
        "Feste Jahreszahl im Code (#1237) - ein 'bis heute' rechnet mit der Uhr, "
        "`uhr.heute()`. Hat die Zahl einen Grund, steht am Zeilenende "
        "`# jahreszahl-ok: <Grund>`:\n" + "\n".join(funde))


@pytest.mark.parametrize("code", [
    # die drei Fundstellen aus v1.7.158
    "end = int(end_raw) if end_raw.isdigit() else 2026",
    "e_year, e_month = 2026, 3  # current",
    "end_year = 2026",
    # weitere Schreibweisen derselben Krankheit
    "d = datetime(2027, 1, 1)",
    "alter = date.today().year - 2026",
    "for j in range(2020, 2027): pass",
    "jahr = '2026'",
    "print(f'{2026}')",
    "x = 2026  # jahreszahl-ok:",          # eine Marke ohne Grund zaehlt nicht
    "x = 2026  # jahreszahl-ok:   ",
    # die Raender des Fensters gehoeren dazu
    "x = 2020",
    "x = 2039",
    "x = '2020'",
    "x = '2039'",
])
def test_waechter_erkennt_feste_jahreszahlen(code):
    assert festjahre_finden(code), code


@pytest.mark.parametrize("code", [
    "# ende = 2026",                                   # Kommentar
    '"""Stand 2026: so war es."""\nx = 1',            # Docstring
    "datum = '2026-05-01'",                            # Datumstext
    "text = 'seit 2026'",
    "grenze = 2000",                                   # runde Grenze
    "kontext = 2048",                                  # Groesse
    "alt = 1999",
    "seit_2026 = 5",                                   # nur im Namen
    "bits = 20260",
    "wahr = True",
    "x = 2026  # jahreszahl-ok: Stichtag der Studie, bleibt",
    # knapp ausserhalb des Fensters
    "x = 2019",
    "x = 2040",
    "x = '2019'",
    "x = '2040'",
])
def test_waechter_laesst_harmloses_in_ruhe(code):
    assert festjahre_finden(code) == [], code


def test_waechter_liest_die_dateien_mit_den_fundstellen():
    """Ein Waechter, der nichts liest, ist immer gruen."""
    dateien = {p.relative_to(SRC).as_posix() for p in _quelldateien()}
    assert {"bewerbungs_assistent/export.py",
            "bewerbungs_assistent/services/auto_aussortierung.py",
            "bewerbungs_assistent/services/berufsfeld.py",
            "bewerbungs_assistent/database.py"} <= dateien
    assert len(dateien) > 100, len(dateien)


def test_waechter_wird_von_pytest_eingesammelt():
    """Ein Schutz zaehlt erst, wenn er aufgerufen wird: pytest sammelt `tests/`
    ein, und die CI ruft es ohne Auswahl auf."""
    cfg = tomllib.loads((WURZEL / "pyproject.toml").read_text(encoding="utf-8"))
    pfade = cfg["tool"]["pytest"]["ini_options"]["testpaths"]
    assert any((WURZEL / p).resolve() in Path(__file__).resolve().parents for p in pfade), pfade
    assert Path(__file__).name.startswith("test_")
    ci = (WURZEL / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "--ignore" not in ci and "--deselect" not in ci
