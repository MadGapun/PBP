"""Der BELEG zur abgeleiteten Betriebsart (#968, v1.7.69).

v1.7.69 leitet die Betriebsart des MUSS-Tors daraus ab, ob die
Pflichtbegriffe einen BERUF oder eine TECHNIK nennen. Gemessen wurde das
gegen das echte Berufe-Register — die Messung lag danach aber nur in
einem Sitzungsprotokoll und im CHANGELOG. **Damit war sie behauptet,
nicht belegt:** niemand sonst konnte sie nachvollziehen, und ein
kuenftiger Umbau haette sie still brechen koennen.

Diese Datei ist der Beleg. Sie prueft die Ableitung gegen
**aufgezeichnete Antworten des echten Registers**
(`tests/fixtures/berufe_facetten.json`, erzeugt von
`scripts/berufe_facetten_aufzeichnen.py`) — dasselbe Muster wie die
aufgezeichneten LinkedIn- und Ferchau-Antworten (#919, #925): der
Parser laeuft gegen gespeicherte Antworten, also faellt ein Feldumbau
im Test auf statt im Feld.

**Warum keine erfundenen Zahlen.** Ein Test mit selbst ausgedachten
Facetten-Zaehlern haette nur bewiesen, dass die Funktion rechnet, was
ich ihr vorgebe. Die eigentliche Behauptung ist aber eine ueber die
WIRKLICHKEIT: dass Berufe und Techniken sich in dieser Facette
tatsaechlich trennen. Das laesst sich nur an echten Daten zeigen.

**Die Begriffe sind bewusst quer durch den Arbeitsmarkt gewaehlt** und
nicht nach einem einzelnen Lebenslauf — genau der Einwand, der diese
Arbeit ausgeloest hat.
"""
import json
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import berufsbezeichnungen as bb  # noqa: E402
from bewerbungs_assistent.services import muss_tor  # noqa: E402

FIXTURE = _repo() / "tests" / "fixtures" / "berufe_facetten.json"


def _aufzeichnung() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class _Aufgezeichnet:
    """Ein Client, der die aufgezeichnete Antwort zurueckgibt.

    `begriffsart` bekommt damit exakt das, was das echte Register am
    Aufzeichnungstag geliefert hat — kein Netz, keine erfundenen Zahlen.
    """

    def __init__(self, counts: dict):
        self._counts = counts

    def get(self, *args, **kwargs):
        counts = self._counts

        class _Antwort:
            status_code = 200

            @staticmethod
            def json():
                return {"facetten": {"beruf": {"counts": counts}}}

        return _Antwort()


def _faelle(art: str):
    return sorted(k for k, v in _aufzeichnung().items()
                  if v["erwartet"] == art)


# ------------------------------------------------------- Der eigentliche Beleg


@pytest.mark.parametrize("begriff", _faelle("beruf"))
def test_968_echte_berufe_werden_als_beruf_erkannt(begriff):
    """Sechs Berufe quer durch den Arbeitsmarkt, echte Registerdaten."""
    eintrag = _aufzeichnung()[begriff]
    bb.cache_leeren()
    try:
        assert bb.begriffsart(
            begriff, client=_Aufgezeichnet(eintrag["counts"])) == bb.BERUF, (
            f"{begriff} hat einen Spitzenanteil von "
            f"{eintrag['spitzenanteil']:.1%}")
    finally:
        bb.cache_leeren()


@pytest.mark.parametrize("begriff", _faelle("technik"))
def test_968_echte_techniken_werden_als_technik_erkannt(begriff):
    """Fuenf Techniken, echte Registerdaten."""
    eintrag = _aufzeichnung()[begriff]
    bb.cache_leeren()
    try:
        assert bb.begriffsart(
            begriff, client=_Aufgezeichnet(eintrag["counts"])) == bb.TECHNIK, (
            f"{begriff} hat einen Spitzenanteil von "
            f"{eintrag['spitzenanteil']:.1%}")
    finally:
        bb.cache_leeren()


def test_968_die_beiden_gruppen_ueberlappen_nicht():
    """Die Behauptung, auf der die ganze Ableitung steht.

    Gemessen am 10.09.2026 gegen das echte Register:

    * Berufe      18,5 % – 68,7 %  (Elektroniker … Physiotherapeut)
    * Techniken    9,6 % – 14,1 %  (Materialstammdaten … Kubernetes)

    Zwischen beiden liegt eine Luecke von rund vier Prozentpunkten, und
    die Schwelle liegt darin. **Waeren die Gruppen ueberlappend, waere
    die Ableitung nicht haltbar** — dann muesste die Vorgabe zurueck zu
    einer Nutzerentscheidung. Genau das prueft dieser Test.
    """
    daten = _aufzeichnung()
    berufe = [v["spitzenanteil"] for v in daten.values()
              if v["erwartet"] == "beruf"]
    techniken = [v["spitzenanteil"] for v in daten.values()
                 if v["erwartet"] == "technik"]
    assert len(berufe) >= 5 and len(techniken) >= 4, (
        "Zu wenige Belege — eine Trennung an drei Punkten ist keine.")
    assert max(techniken) < bb.MIN_SPITZENANTEIL < min(berufe), (
        f"Keine Trennung: Techniken bis {max(techniken):.1%}, "
        f"Berufe ab {min(berufe):.1%}, Schwelle "
        f"{bb.MIN_SPITZENANTEIL:.1%}")


def test_968_der_knappste_fall_ist_benannt():
    """Ehrlichkeit ueber die Reserve, nicht nur ueber das Ergebnis.

    Die Trennung ist am oberen Ende der Techniken duenn: der hoechste
    gemessene Technik-Wert liegt knapp unter der Schwelle. Das gehoert
    gesagt, statt eine komfortable Trennung zu behaupten — und es ist
    der Grund, warum `unbekannt` NICHT als Technik gilt: bei so wenig
    Reserve waere ein geratener Wert riskant.
    """
    daten = _aufzeichnung()
    techniken = {k: v["spitzenanteil"] for k, v in daten.items()
                 if v["erwartet"] == "technik"}
    knappster = max(techniken, key=techniken.get)
    reserve = bb.MIN_SPITZENANTEIL - techniken[knappster]
    assert 0 < reserve < 0.05, (
        f"Die Reserve zu {knappster} betraegt {reserve:.1%} — wenn sie "
        "sich deutlich veraendert hat, gehoert die Schwelle neu "
        "gemessen statt der Test angepasst.")


# ------------------------------------------- Vom Beleg zur Betriebsart


@pytest.mark.parametrize("begriffe,erwartet", [
    (["Pflegefachkraft"], muss_tor.GEWICHTET),
    (["Erzieherin", "Elektroniker"], muss_tor.GEWICHTET),
    (["PLM", "PDM", "Materialstammdaten"], muss_tor.HART),
    (["Python", "Kubernetes"], muss_tor.HART),
    # Gemischt: ein Beruf genuegt, weil genau er umbenannt sein kann.
    (["Erzieherin", "Python"], muss_tor.GEWICHTET),
])
def test_968_die_betriebsart_folgt_den_echten_begriffsarten(begriffe, erwartet):
    """Die Kette vom Registerbefund bis zur Betriebsart, an echten Daten.

    Das ist der Beleg fuer die Tabelle im CHANGELOG — bis hierher war
    sie eine Behauptung aus einem Sitzungsprotokoll.
    """
    daten = _aufzeichnung()
    arten = {}
    for begriff in begriffe:
        bb.cache_leeren()
        arten[begriff] = bb.begriffsart(
            begriff, client=_Aufgezeichnet(daten[begriff]["counts"]))
    bb.cache_leeren()
    assert muss_tor.abgeleitet(arten)[0] == erwartet, arten


def test_968_die_aufzeichnung_traegt_keine_stellendaten():
    """Nur die Facette, nie die Trefferliste (DoD 9).

    Die Antwort des Registers enthaelt auch Stellenanzeigen samt
    Arbeitgebern. In einem oeffentlichen Repo haben die nichts zu
    suchen — das Aufzeichnungs-Skript schneidet sie deshalb weg, und
    dieser Test haelt fest, dass das so bleibt.
    """
    for eintrag in _aufzeichnung().values():
        assert set(eintrag) == {"erwartet", "spitzenanteil", "counts"}, (
            "Die Aufzeichnung traegt mehr als die Facette.")


def test_968_das_aufzeichnungs_skript_bleibt_nachvollziehbar():
    """Ein Beleg ohne Weg zu seiner Entstehung ist wieder eine Behauptung."""
    skript = _repo() / "scripts" / "berufe_facetten_aufzeichnen.py"
    assert skript.exists(), (
        "Ohne das Skript laesst sich die Aufzeichnung nicht erneuern.")
