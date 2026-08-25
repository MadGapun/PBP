"""Tests fuer v1.7.23 — #808: Health-Check meldete falsch-gruen.

`scraper_diagnose` zeigte Erfolgsraten von 93-98 % fuer Quellen, die
zum Teil seit Wochen nichts lieferten. Solange die Zahl nicht misst,
was sie behauptet, ist sie schlimmer als keine Zahl — man verlaesst
sich darauf.

Drei belegte Muster, alle mit HTTP 200.
"""
import json

import pytest

from bewerbungs_assistent.job_scraper.health import bewerte_inhalt


class _Antwort:
    """Minimale httpx-Response-Attrappe."""

    def __init__(self, content_type, payload=None, roh=None):
        self.headers = {"content-type": content_type}
        self._payload = payload
        self._roh = roh

    def json(self):
        if self._payload is None:
            raise ValueError("kein JSON")
        return self._payload


# ── Muster 2: SPA antwortet mit HTML statt JSON ──────────────────────

def test_808_html_auf_json_endpunkt_ist_verdaechtig():
    """Eine zu einem Konzern migrierte Boerse antwortet auf /api/... mit
    HTTP 200 und der Angular-Fallback-Route."""
    status, treffer, grund = bewerte_inhalt(
        _Antwort("text/html; charset=utf-8"), "json")
    assert status == "verdaechtig"
    assert "HTML" in grund


def test_808_kaputtes_json_ist_verdaechtig():
    status, _, grund = bewerte_inhalt(_Antwort("application/json"), "json")
    assert status == "verdaechtig"
    assert "JSON" in grund


# ── Muster 3: leere ATS-Liste ist auch 200 ───────────────────────────

def test_808_leere_ergebnisliste_ist_nicht_ok():
    """Ein falscher Firmen-Slug liefert gueltiges JSON mit 0 Treffern.
    Technisch einwandfrei, fachlich tot."""
    status, treffer, grund = bewerte_inhalt(
        _Antwort("application/json", {"jobs": []}), "json")
    assert status == "leer"
    assert treffer == 0
    assert "Firmen-Slug" in grund


def test_808_totalfound_null_ist_nicht_ok():
    status, treffer, _ = bewerte_inhalt(
        _Antwort("application/json", {"totalFound": 0}), "json")
    assert status == "leer"
    assert treffer == 0


# ── Gegenrichtung: echte Treffer bleiben gruen ───────────────────────

@pytest.mark.parametrize("nutzlast,erwartet", [
    ({"stellenangebote": [{"a": 1}, {"a": 2}]}, 2),
    ({"ergebnisliste": [{"a": 1}]}, 1),
    ([{"a": 1}, {"a": 2}, {"a": 3}], 3),
    ({"data": {"items": [{"a": 1}]}}, 1),
    ({"totalFound": 42}, 42),
])
def test_808_echte_treffer_bleiben_ok(nutzlast, erwartet):
    status, treffer, _ = bewerte_inhalt(
        _Antwort("application/json", nutzlast), "json")
    assert status == "ok"
    assert treffer == erwartet


def test_808_unbekannte_struktur_wird_nicht_faelschlich_verurteilt():
    """Wenn keine Liste erkennbar ist, ist das kein Beweis fuer einen
    Ausfall — dann sagt der Status ehrlich nur, dass der Endpunkt lebt."""
    status, treffer, grund = bewerte_inhalt(
        _Antwort("application/json", {"status": "ok", "version": "3"}), "json")
    assert status == "ok"
    assert treffer is None
    assert "nicht erkennbar" in grund


def test_808_nicht_json_quellen_werden_nicht_geprueft():
    """HTML-Quellen sind als solche gefuehrt — dort ist HTML richtig."""
    status, _, _ = bewerte_inhalt(_Antwort("text/html"), "html")
    assert status == "ok"


def test_808_probe_liefert_den_inhaltsstatus_mit():
    """Der Aufrufer muss die Unterscheidung sehen koennen."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "job_scraper" / "health.py").read_text(
                  encoding="utf-8")
    assert '"inhalt": inhalt if erreichbar else "fehler"' in quelle
    assert "inhalt_hinweis" in quelle
