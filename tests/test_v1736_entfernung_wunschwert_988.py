"""Tests fuer v1.7.36 — #988: der Wunschwert wirkte nicht, 87 km = 577 km.

In den Suchkriterien stand `max_entfernung: {"festanstellung": 30}`. Die
Bewertung lief trotzdem gegen die Reglerstufe 999 km, und weil diese
Stufe ein Deckel ist, kostete eine Stelle in Ulm (577 km) genau so viel
wie eine in Kiel (87 km). Auf einer Skala, auf der ein einzelner
MUSS-Treffer 7 Punkte bringt, ist das kein Unterschied.

Zwei Einstellungen fuer dieselbe Sache, von denen nur eine wirkt, sind
eine Fehlerquelle — und beim Randbefund war es sogar eine Einstellung,
die GAR NICHTS tut: unter der Dimension `schwellenwert` stand neben dem
gelesenen `auto_ignore` ein zweiter Regler `schwellenwert` mit 35. Er
war ueber `scoring_konfigurieren('setzen', ...)` ungeprueft angelegt
worden. Der Nutzer glaubte, seine Schwelle liege bei 35; sie lag bei 0.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.services import scoring_vokabular as vok  # noqa: E402
from bewerbungs_assistent.services.scoring_service import (  # noqa: E402
    MAX_ENTFERNUNGS_ZUSCHLAG, _entfernungs_zuschlag, apply_scoring_adjustments,
)


class _DB:
    """Attrappe mit genau den zwei Auskuenften, die der Regler braucht."""

    def __init__(self, wunsch=None, config=None):
        self._wunsch = wunsch
        self._config = config or []

    def get_search_criteria(self):
        if self._wunsch is None:
            return {}
        return {"max_entfernung": {"festanstellung": self._wunsch}}

    def get_scoring_config(self):
        return list(self._config)


STUFEN = [
    {"dimension": "entfernung_fest", "sub_key": "30", "value": 0, "ignore_flag": 0},
    {"dimension": "entfernung_fest", "sub_key": "50", "value": -2, "ignore_flag": 0},
    {"dimension": "entfernung_fest", "sub_key": "80", "value": -3, "ignore_flag": 0},
    {"dimension": "entfernung_fest", "sub_key": "999", "value": -4, "ignore_flag": 0},
]


def _bewerte(km: float, wunsch=30) -> dict:
    job = {"employment_type": "festanstellung", "distance_km": km}
    return apply_scoring_adjustments(job, 50, _DB(wunsch, STUFEN))


def _entfernungs_punkte(ergebnis: dict) -> float:
    for a in ergebnis["adjustments"]:
        if a["dimension"] == "Entfernung":
            return a["punkte"]
    raise AssertionError(f"Keine Entfernungs-Anpassung in {ergebnis}")


# ── AK 4: die Kernaussage des Issues ──────────────────────────────────

def test_988_weiter_weg_kostet_mehr():
    """577 km muessen schlechter dastehen als 87 km."""
    nah = _entfernungs_punkte(_bewerte(87))
    fern = _entfernungs_punkte(_bewerte(577))
    assert fern < nah, f"87 km: {nah}, 577 km: {fern}"


def test_988_der_alte_deckel_ist_weg():
    """Vorher trugen beide exakt -4."""
    assert _entfernungs_punkte(_bewerte(87)) != _entfernungs_punkte(_bewerte(577))


@pytest.mark.parametrize("km", [82, 87, 392, 577, 1200])
def test_988_malus_waechst_monoton(km):
    """AK 2: der Preis waechst ueber die oberste Stufe hinaus weiter."""
    assert _entfernungs_punkte(_bewerte(km)) <= _entfernungs_punkte(_bewerte(80))


def test_988_jenseits_der_obersten_stufe_greift_die_oberste_stufe():
    """Beim Schreiben dieser Tests gefunden, nicht im Issue gemeldet.

    Die Schleife suchte die erste Stufe mit `distance_km <= bracket_km`.
    Fuer 1200 km traf keine — und eine Stelle am anderen Ende Europas
    kostete damit NICHTS, waehrend dieselbe Stelle in 577 km vier Punkte
    kostete. Die oberste Stufe ist ein Auffangbecken, kein Fenster.
    """
    assert _entfernungs_punkte(_bewerte(1200)) < 0


# ── AK 1 und 3: der Wunschwert wirkt und wird genannt ─────────────────

def test_988_wunschwert_wirkt():
    """Dieselbe Stelle, zwei Wunschwerte, zwei Bewertungen."""
    eng = _entfernungs_punkte(_bewerte(300, wunsch=30))
    weit = _entfernungs_punkte(_bewerte(300, wunsch=300))
    assert eng < weit


def test_988_detail_nennt_den_wunschwert():
    """AK 3: nicht mehr nur "Grenze: 999km"."""
    ergebnis = _bewerte(87)
    detail = next(a["detail"] for a in ergebnis["adjustments"]
                  if a["dimension"] == "Entfernung")
    assert "Wunsch: 30km" in detail
    assert "Stufe: 999km" in detail


def test_988_innerhalb_des_wunsches_kein_zuschlag():
    """Wer im Rahmen bleibt, zahlt nichts extra."""
    assert _entfernungs_zuschlag(25, "festanstellung", _DB(30)) == (0, 30)
    assert _entfernungs_zuschlag(30, "festanstellung", _DB(30)) == (0, 30)


def test_988_zuschlag_ist_gedeckelt():
    """Entfernung ist ein Preis, kein Ausschluss (#910)."""
    zuschlag, _ = _entfernungs_zuschlag(100_000, "festanstellung", _DB(30))
    assert zuschlag == MAX_ENTFERNUNGS_ZUSCHLAG


def test_988_ohne_wunschwert_gilt_der_standard():
    """Ein leeres Kriterium darf nicht in eine Division durch Null laufen."""
    zuschlag, wunsch = _entfernungs_zuschlag(500, "festanstellung", _DB(None))
    assert wunsch == 50
    assert zuschlag > 0


def test_988_kaputte_datenbank_stoppt_den_regler_nicht():
    class _Kaputt(_DB):
        def get_search_criteria(self):
            raise RuntimeError("Kriterien weg")

    zuschlag, wunsch = _entfernungs_zuschlag(500, "festanstellung", _Kaputt())
    assert wunsch == 50 and zuschlag > 0


def test_988_boni_bleiben_unberuehrt():
    """Der Zuschlag gilt nur fuer MALUS-Zweige."""
    stufen = [{"dimension": "entfernung_fest", "sub_key": "999",
               "value": 3, "ignore_flag": 0}]
    ergebnis = apply_scoring_adjustments(
        {"employment_type": "festanstellung", "distance_km": 500}, 50,
        _DB(30, stufen))
    assert _entfernungs_punkte(ergebnis) == 3


# ── Randbefund: Regler, die niemand liest ─────────────────────────────

def test_988_unbekannter_regler_wird_abgewiesen():
    """Der Fall, der die zweite Schwellenwert-Zeile erzeugt hat."""
    assert vok.pruefe("schwellenwert", "schwellenwert")
    assert vok.pruefe("schwellenwert", "auto_ignore") == ""


def test_988_absage_nennt_die_moeglichen_werte():
    grund = vok.pruefe("remote", "teilweise")
    assert "hybrid" in grund and "vor_ort" in grund


def test_988_km_stufen_bleiben_frei():
    """Wer eine eigene Entfernungsstufe braucht, darf sie anlegen."""
    assert vok.pruefe("entfernung_fest", "120") == ""
    assert vok.pruefe("entfernung_freelance", "350") == ""
    # ... aber nicht als "50km" (#661/#917).
    assert vok.pruefe("entfernung_fest", "50km")


def test_988_stillgelegter_regler_wird_benannt():
    """hochschulabschluss/fehlt steht im Bestand und tut seit #972 nichts."""
    grund = vok.wirkungslos("hochschulabschluss", "fehlt")
    assert "972" in grund


def test_988_wirkende_regler_gelten_als_wirkend():
    for dim, sub in (("stellentyp", "freelance"), ("gehalt", "pro_10_prozent"),
                     ("entfernung_gehalt_kompensation", "spanne"),
                     ("entfernung_fest", "999")):
        assert vok.wirkungslos(dim, sub) == "", (dim, sub)
