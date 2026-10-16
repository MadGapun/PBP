"""#1231: der PII-Pruefer kennt einen Platzhalter in jeder Schreibweise.

`FIKTIVE_FIRMEN` fuehrt "vermittler sued"; ein Beitrag schrieb denselben Platzhalter mit Umlaut ("ü")
und bekam einen Firmentreffer. Die Liste fand nur ihre eigene Schreibweise (L5-L6). Beide Richtungen
gehoeren in den Test: was als fiktiv gelten MUSS (Umlaut gegen Umschrift, Umschrift gegen Umlaut,
zerlegtes Trema) und was NICHT (eine echte Firma, die dem Platzhalter nur aehnelt).
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import scrub_pii  # noqa: E402
from scrub_pii import _ist_fiktiv, _umschrift, find_pii  # noqa: E402


def _firmen(text: str) -> list:
    return [h for h in find_pii(text) if h.startswith("CORP")]


# ----------------------------------------------------------- Umschrift

@pytest.mark.parametrize("roh, erwartet", [
    ("Süd", "sued"),
    ("SÜD", "sued"),
    ("Mühlenberg", "muehlenberg"),
    ("Pleiße", "pleisse"),
    ("Größe", "groesse"),
    ("Märkte", "maerkte"),
    ("Nord", "nord"),
    ("über", "ueber"),          # zerlegtes Trema (u + U+0308)
])
def test_umschrift_ersetzt_umlaute_und_sz(roh, erwartet):
    assert _umschrift(roh) == erwartet


# ----------------------------------------------------------- was als fiktiv gelten MUSS

@pytest.mark.parametrize("label", [
    "Vermittler Süd GmbH",              # der Fall aus dem Beitrag: Umlaut gegen die Umschrift der Liste
    "Vermittler Sued GmbH",             # die Schreibweise der Liste
    "VERMITTLER SÜD GmbH",
    "Anlagenbau Süd",
    "Mühlenberg Werkzeugbau GmbH",      # beide Schreibweisen stehen in der Liste
    "Muehlenberg Werkzeugbau GmbH",
])
def test_platzhalter_gilt_in_jeder_schreibweise(label):
    assert _ist_fiktiv(label), f"als echte Firma gewertet: {label!r}"


@pytest.mark.parametrize("liste, label", [
    (("testfirma süd",), "Testfirma Sued GmbH"),      # Liste mit Umlaut, Text in Umschrift
    (("testfirma sued",), "Testfirma Süd GmbH"),      # Liste in Umschrift, Text mit Umlaut
    (("weißwerk nord",), "Weisswerk Nord GmbH"),      # ß gegen ss
    (("weisswerk nord",), "Weißwerk Nord GmbH"),
])
def test_beide_richtungen_mit_eigener_liste(monkeypatch, liste, label):
    monkeypatch.setattr(scrub_pii, "FIKTIVE_FIRMEN", liste)
    assert _ist_fiktiv(label), f"{label!r} gegen {liste!r}"


def test_der_fall_aus_dem_beitrag_ist_kein_firmentreffer_mehr():
    # Wortlaut des Testfalls aus PR #1230 (frei erfundener Platzhalter).
    text = 'bewerbung_id=aid, vermittler="Vermittler Süd GmbH")\nassert "Vermittler Süd GmbH" in warnung'
    assert _firmen(text) == [], _firmen(text)


# ----------------------------------------------------------- was NICHT als fiktiv gelten darf

@pytest.mark.parametrize("label", [
    "Vermittler GmbH",                  # nur das Wort, ohne Himmelsrichtung
    "Süd Vermittler GmbH",              # andere Reihenfolge: nicht der Platzhalter
    "Sued Anlagen GmbH",
    "Kuestenwerk GmbH",                 # keine Liste kennt es
    "Südwerk Maschinenbau GmbH",
])
def test_aehnliche_echte_firma_bleibt_ein_treffer(label):
    assert not _ist_fiktiv(label), f"als Platzhalter gewertet: {label!r}"


def test_aehnliche_firma_bleibt_ein_firmentreffer():
    # Die Gegenrichtung zum Fall aus dem Beitrag: eine Firma, die nur ein Teil des Platzhalters ist.
    assert _firmen("Die Südwerk Maschinenbau GmbH hat sich gemeldet.")
