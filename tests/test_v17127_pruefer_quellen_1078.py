"""#1078 — der PII-Pruefer meldet Quellen im Quellen-Zusammenhang nicht mehr.

Der woechentliche Sweep meldete vier Fehlalarme: einen Quellennamen in
Grossschreibung (in einer Aufzaehlung mit anderen Quellen, als
technischer Begriff) und eine aufsteigende Platzhalter-Rufnummer. Ein
Pruefer, der jede Woche denselben Fehlalarm meldet, wird ignoriert
(#929). Jede Regel ist deshalb in BEIDE Richtungen getestet: was Rede
ueber die Quelle ist, bleibt still; was Bewerbungshistorie ist, bleibt
ein Fund.

Der Quellenname entsteht zur Laufzeit aus dem Key, damit keine
Firmenschreibweise im Repository steht (v1.7.109 MERKE 6).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scrub_pii import find_pii  # noqa: E402

QUELLE = "hays".capitalize()
VERMITTLER = "ferchau".upper()


def _firmen(text):
    return [h for h in find_pii(text) if h.startswith(("FIRMA:", "CORP:"))]


# --- Quellen-Zusammenhang: still ---------------------------------------


def test_aufzaehlung_mit_anderen_quellen_ist_kein_fund():
    text = f"Aus GULP, freelance.de und {QUELLE} stehen bei mir 11 Stellen aktiv."
    assert _firmen(text) == []


def test_technisches_kompositum_ist_kein_fund():
    text = f"3. #1048 {QUELLE}-Kappung bei 500 Zeichen"
    assert _firmen(text) == []


def test_quellenwort_davor_ist_kein_fund():
    text = f"Die Quelle {QUELLE} liefert gekappte Anzeigentexte."
    assert _firmen(text) == []


def test_kleinschreibung_bleibt_wie_bisher_still():
    assert _firmen("Die Quelle hays kappt bei 500 Zeichen.") == []


# --- Bewerbungshistorie: weiter ein Fund --------------------------------


def test_allein_stehend_bleibt_ein_fund():
    text = f"Gestern hat {QUELLE} angerufen."
    assert _firmen(text) == [f"FIRMA: {QUELLE}"]


def test_bewerbungsbezug_schlaegt_die_aufzaehlung():
    text = f"Ich habe mich ueber {QUELLE} beworben, GULP hat nichts geliefert."
    assert _firmen(text) == [f"FIRMA: {QUELLE}"]


def test_recruiterin_schlaegt_das_kompositum():
    text = f"Die Recruiterin meldet sich zur {QUELLE}-Stellen Auswahl."
    assert _firmen(text) == [f"FIRMA: {QUELLE}"]


def test_ein_vorkommen_ausserhalb_genuegt_fuer_den_fund():
    text = (f"Aus GULP und {QUELLE} kamen Treffer.\n\n"
            f"Morgen ist das Gespraech bei {QUELLE}.")
    assert _firmen(text) == [f"FIRMA: {QUELLE}"]


def test_firma_mit_rechtsform_bleibt_ein_fund():
    """Mit Rechtsform ist es eine Firmen-Nennung, kein Quellenname."""
    text = f"Aus GULP und {VERMITTLER} GmbH kamen Treffer."
    assert any(VERMITTLER in h for h in _firmen(text))


def test_fremde_firma_neben_quellen_bleibt_ein_fund():
    """Die Ausnahme gilt nur fuer Quellen, nicht fuer jede Firma daneben."""
    text = "Aus GULP, freelance.de und Randstad kamen Treffer."
    assert _firmen(text) == ["FIRMA: Randstad"]


# --- Platzhalter-Rufnummer ----------------------------------------------


def _telefon(text):
    return [h for h in find_pii(text) if h.startswith("PHONE:")]


def test_aufsteigende_platzhalter_nummer_ist_kein_fund():
    text = 'Reproduktion:\n```\n"Telefon 01234-56789-10  Europastr. 1"\n```'
    assert _telefon(text) == []


def test_aufsteigende_nummer_mit_leerzeichen_ist_kein_fund():
    assert _telefon("Telefon 0123 456789") == []


def test_echte_form_ohne_aufsteigende_folge_bleibt_ein_fund():
    """0100 ist eine Verbindungsnetz-Vorwahl, keine echte Anschlussnummer."""
    assert _telefon("Telefon 0100 7381922") != []


def test_kurze_aufsteigende_folge_macht_keine_nummer_fiktiv():
    """12345 kommt in echten Nummern vor — erst acht in Folge gelten."""
    assert _telefon("Telefon 0100 1234597") != []
