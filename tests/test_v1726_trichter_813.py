"""Tests fuer v1.7.26 — #813 Problem 3: die 0-Treffer-Meldung beruhigte.

Belegter Lauf vom 06.08.2026: 389 Rohtreffer aus sieben Quellen, davon
kamen NULL durch den Kriterienfilter; zwei Stellen waren bereits
bekannt. Gemeldet wurde:

    "Die Quellen lieferten Treffer, aber alle 2 waren schon bekannt,
    bewertet oder geblacklistet — es gibt gerade nichts Neues. Bei
    haeufigen Suchen ist das normal."

Die Meldung war nicht falsch. Sie war der kleinste wahre Teil: 2 von
389. Welcher Teil genannt wurde, entschied allein die Reihenfolge der
Verzweigungen — die Bereinigungs-Meldung stand vor allem anderen.

Und sie beruhigte ("bei haeufigen Suchen ist das normal") bei einem
Befund, der eine Warnung gewesen waere: 17 von 32 konfigurierten
Quellen liefen gar nicht mehr.
"""
import pytest

from bewerbungs_assistent.job_scraper import zero_treffer_diagnose

# Der Lauf aus dem Issue, Zahl fuer Zahl.
QUELLEN_LAUF = {
    "greenhouse": {"status": "ok", "count": 225},
    "hays": {"status": "ok", "count": 50},
    "remotive": {"status": "ok", "count": 31},
    "arbeitnow": {"status": "ok", "count": 29},
    "remoteok": {"status": "ok", "count": 28},
    "stellenanzeigen_de": {"status": "ok", "count": 25},
    "jobware": {"status": "ok", "count": 1},
    "bundesagentur": {"status": "ok", "count": 0},
    "kimeta": {"status": "skipped", "count": 0},
}
FILTER = {"kein_muss_keyword": 312, "unter_schwelle": 75}


def _belegter_fall():
    return zero_treffer_diagnose(
        {"duplikate_db": 2}, QUELLEN_LAUF, 8, 0, 0,
        filterstufen=FILTER, quellen_konfiguriert=32)


# ── Der Trichter wird genannt ────────────────────────────────────────

def test_813_rohtrefferzahl_steht_in_der_meldung():
    """2 zu nennen und 389 zu verschweigen war die eigentliche
    Irrefuehrung."""
    assert "389" in _belegter_fall()


def test_813_filterstufen_werden_aufgeschluesselt():
    text = _belegter_fall()
    assert "312" in text and "MUSS" in text
    assert "75" in text and "Schwelle" in text


def test_813_stufen_stehen_in_klartext():
    """`kein_muss_keyword` ist kein Satz."""
    text = _belegter_fall()
    assert "kein_muss_keyword" not in text
    assert "unter_schwelle" not in text


def test_813_meldung_beruhigt_nicht_mehr():
    """Der Kern: kein 'das ist normal', wenn der Filter alles frisst."""
    text = _belegter_fall()
    assert "ist das normal" not in text
    assert "KEIN leerer Markt" in text


def test_813_meldung_nennt_den_naechsten_schritt():
    """Ohne Weg nach vorn ist eine Diagnose nur eine Feststellung."""
    text = _belegter_fall()
    assert "scoring_konfigurieren" in text or "suchkriterien_anzeigen" in text


# ── Warnung bei totem Portfolio ──────────────────────────────────────

def test_813_warnt_wenn_mehr_als_die_haelfte_der_quellen_fehlt():
    """17 von 32 liefen nicht — das verschwand vollstaendig."""
    text = _belegter_fall()
    assert "ACHTUNG" in text
    assert "32" in text
    assert "scraper_diagnose" in text


def test_813_keine_warnung_wenn_das_portfolio_laeuft():
    """Eine Warnung, die immer kommt, wird nicht gelesen."""
    laufend = {f"q{i}": {"status": "ok", "count": 3} for i in range(8)}
    text = zero_treffer_diagnose(
        {"duplikate_db": 24}, laufend, 8, 0, 0,
        filterstufen={}, quellen_konfiguriert=8)
    assert "ACHTUNG" not in text


# ── Die Gegenrichtung: harmlose Faelle bleiben harmlos ───────────────

def test_813_wirklich_nur_bekanntes_bleibt_beruhigend():
    """Wenn tatsaechlich nur Bekanntes kam, ist 'das ist normal' die
    richtige Auskunft — die Haertung darf sie nicht verdraengen."""
    text = zero_treffer_diagnose(
        {"duplikate_db": 5}, {"hays": {"status": "ok", "count": 5}},
        1, 0, 0, filterstufen={}, quellen_konfiguriert=2)
    assert "ist das normal" in text
    assert "Rohtreffer" not in text


def test_813_alte_aufrufform_bleibt_gueltig():
    """Die neuen Argumente sind optional — sonst braeche jeder
    bestehende Aufrufer."""
    text = zero_treffer_diagnose(
        {"duplikate_db": 3}, {"hays": {"status": "ok", "count": 3}}, 1, 0, 0)
    assert text and isinstance(text, str)


def test_813_ohne_quellen_bleibt_die_alte_diagnose():
    text = zero_treffer_diagnose({}, {}, 0, 0, 0,
                                 filterstufen={}, quellen_konfiguriert=5)
    assert "Keine Quelle" in text


def test_813_alle_quellen_mit_fehler():
    text = zero_treffer_diagnose(
        {}, {"a": {"status": "error", "count": 0},
             "b": {"status": "timeout", "count": 0}}, 0, 1, 1,
        filterstufen={}, quellen_konfiguriert=2)
    assert "Fehler" in text or "Timeout" in text


# ── Verdrahtung ──────────────────────────────────────────────────────

def test_813_aufrufer_uebergibt_die_neuen_zahlen():
    """Der beste Trichter nuetzt nichts, wenn ihn niemand fuellt
    (DoD 8c)."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "job_scraper" /
              "__init__.py").read_text(encoding="utf-8")
    assert "filterstufen=filterstufen" in quelle
    assert "quellen_konfiguriert=len(quellen)" in quelle
