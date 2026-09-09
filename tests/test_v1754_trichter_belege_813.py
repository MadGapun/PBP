"""Tests fuer v1.7.54 — #813 Rest: der Trichter zaehlt, aber belegt nichts.

#813 wurde in mehreren Wellen abgearbeitet:

* **v1.7.22 (#940)** — die Filterkaskade zaehlt und landet im Ergebnis
  statt nur im Log (AK 1, AK 2).
* **v1.7.26** — die 0-Treffer-Meldung nennt den Trichter zuerst und warnt,
  wenn weniger als die Haelfte der konfigurierten Quellen gelaufen ist
  (AK 5). Vorher beruhigte sie bei einem Befund, der eine Warnung war.
* **v1.7.44** — Quellenpflege: der Zwischenzustand "aktiv konfiguriert,
  aber nie geliefert" ist aufgeloest (AK 8).
* **v1.7.51 (#995)** — "liefert nichts" und "liefert nichts Passendes"
  sind unterscheidbar; eine Quelle ohne fachliche Passung wird benannt
  statt abgeschaltet (AK 7).

Hier kommt der Rest: **AK 3, 4 und 6.**

Der Trichter sagt "37 unter der Schwelle" — und laesst offen, ob die
Schwelle zu hoch steht. Er sagt "12 wegen Ausschluss-Keyword" — und
laesst offen, ob ein einzelnes zu breites Wort den halben Lauf kostet.
Beide Fragen beantwortet erst ein BELEG.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.job_scraper import _trichter_belege  # noqa: E402


def _stelle(titel, score, **rest):
    return dict({"title": titel, "company": "Musterwerk", "score": score},
                **rest)


# ── AK 3: die knapp Gescheiterten ─────────────────────────────────────

def test_813_knapp_gescheiterte_werden_belegt():
    """Fuenf Stellen bei Score 4 gegen eine Schwelle von 5 sind ein
    anderer Befund als fuenf Stellen bei Score 0 — die blosse Zahl
    unterscheidet das nicht."""
    knapp, _ = _trichter_belege(
        [_stelle("PLM Consultant", 4.0), _stelle("PDM Berater", 3.0)], 5)
    assert knapp["anzahl"] == 2
    assert knapp["schwelle"] == 5
    assert knapp["beispiele"][0]["fehlt_zur_schwelle"] == 1.0


def test_813_ohne_fachlichen_anker_ist_nicht_knapp():
    """Eine Stelle ohne MUSS-Treffer ist nicht knapp gescheitert,
    sondern gar nicht gemeint (#940). Sie hier mitzuzaehlen wuerde die
    Stichprobe mit Rauschen fuellen."""
    knapp, _ = _trichter_belege(
        [_stelle("Voellig anderes Fach", 0, _ko_kein_muss=True)], 5)
    assert knapp == {}


def test_813_erreichte_schwelle_ist_nicht_knapp():
    """Gegenprobe: wer durchkommt, taucht nicht als Beleg auf."""
    knapp, _ = _trichter_belege([_stelle("PLM Consultant", 9.0)], 5)
    assert knapp == {}


def test_813_die_stichprobe_ist_begrenzt_und_sortiert():
    """Die knappsten zuerst — sie tragen die Aussage. Und eine
    Stichprobe ohne Grenze ist auch eine Datenmenge (#991)."""
    stellen = [_stelle(f"Stelle {i}", float(i)) for i in range(1, 12)]
    knapp, _ = _trichter_belege(stellen, 20, stichprobe=5)
    assert knapp["anzahl"] == 11
    assert len(knapp["beispiele"]) == 5
    assert [b["score"] for b in knapp["beispiele"]] == [11.0, 10.0, 9.0, 8.0, 7.0]


# ── AK 4: die ausloesenden Ausschluss-Keywords ────────────────────────

def test_813_ausloesende_keywords_mit_haeufigkeit():
    """Ein einzelnes zu breites Wort ist im Trichter unsichtbar — in
    dieser Liste steht es oben."""
    _, ausloeser = _trichter_belege([
        _stelle("A", 0, _ko_ausschluss="Werkstudent"),
        _stelle("B", 0, _ko_ausschluss="Werkstudent"),
        _stelle("C", 0, _ko_ausschluss="Junior"),
    ], 5)
    assert ausloeser["begriffe"][0] == {"keyword": "werkstudent", "treffer": 2}
    assert "zu breit" in ausloeser["hinweis"]


def test_813_ohne_ausschluss_keine_liste():
    """Ein Pruefer, der bei sauberem Zustand etwas meldet, wird
    ignoriert (DoD-9-Lehre)."""
    _, ausloeser = _trichter_belege([_stelle("A", 9.0)], 5)
    assert ausloeser == {}


def test_813_belege_stuerzen_bei_luecken_nicht_ab():
    """Sie entstehen in JEDEM Suchlauf — ein Absturz waere teurer als
    der fehlende Beleg."""
    for stellen in (None, [], [{}], [{"score": None}], [{"score": "viel"}]):
        try:
            _trichter_belege(stellen, 5)
        except (TypeError, ValueError):
            pytest.fail(f"Absturz bei {stellen!r}")


def test_813_die_belege_entstehen_vor_dem_filtern():
    """Guard gegen den Rueckfall: nach dem Filtern sind die verworfenen
    Stellen weg, und der Beleg waere leer — ohne dass es auffiele."""
    quelle = (Path(__file__).resolve().parents[1] / "src"
              / "bewerbungs_assistent" / "job_scraper"
              / "__init__.py").read_text(encoding="utf-8")
    vor = quelle.index("_knapp, _ausloeser = _trichter_belege(")
    nach = quelle.index("unique, verworfen_schwelle = _filter_nach_schwelle(")
    assert vor < nach, "Die Belege muessen VOR dem Filtern eingesammelt werden"


# ── AK 6: der wirkungslose Doppel-Eintrag ─────────────────────────────

def test_813_doppeltes_kriterium_wird_benannt():
    """`min_gehalt` hat ein eigenes Feld (#544). Ein gleichnamiger
    Eintrag in `custom_kriterien` wird beim Bewerten nie gelesen — und
    sieht doch aus, als wirke er. Dieselbe Klasse wie der zweite
    Schwellenwert-Regler aus #988: **benannt statt still umgedeutet.**
    """
    from bewerbungs_assistent.tools.suche import _custom_widerspruch
    hinweis = _custom_widerspruch(
        {"custom_kriterien": {"min_gehalt": 70000, "homeoffice": 9}})
    assert hinweis and "min_gehalt" in hinweis
    assert "wirkungslos" in hinweis


def test_813_eigene_custom_kriterien_bleiben_unbeanstandet():
    """Die wichtigste Gegenprobe: `custom_kriterien` ist ein legitimes
    Sammelbecken. Nur Namenskollisionen mit eigenen Feldern zaehlen."""
    from bewerbungs_assistent.tools.suche import _custom_widerspruch
    assert _custom_widerspruch(
        {"custom_kriterien": {"homeoffice": 9, "senior_level": 8}}) is None
    assert _custom_widerspruch({}) is None
    assert _custom_widerspruch({"custom_kriterien": "kaputt"}) is None
