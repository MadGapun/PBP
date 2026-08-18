"""Tests fuer v1.7.18 — #925: JSON-Daten aus dem SSR-Hydration-Payload.

Die Quelle `ferchau` stand als deprecated und lieferte 0 Stellen —
obwohl die Seite 25 Stellen pro Abruf ausliefert. Der Parser suchte
`<script type="application/ld+json">` im DOM; dort steht nur ein
Organization-Block. Die Stellendaten liegen escaped im
Hydration-Payload.

Fixture aus dem echten Abruf vom 18.08.2026 (zwei Offers, gekuerzt) —
kein Netzzugriff im Test.
"""
from pathlib import Path

import pytest

from bewerbungs_assistent.job_scraper.hydration import (
    entweiche_trennzeichen, liste_aus_hydration)

FIXTURE = Path(__file__).parent / "fixtures" / "ferchau_offers.html"


@pytest.fixture
def html():
    return FIXTURE.read_text(encoding="utf-8")


def test_925_offers_array_wird_gelesen(html):
    offers = liste_aus_hydration(html, "Offers")
    assert len(offers) == 2, f"Fixture traegt zwei Offers, gelesen: {len(offers)}"
    assert all(isinstance(o, dict) for o in offers)


def test_925_leerer_input_ist_harmlos():
    assert liste_aus_hydration("", "Offers") == []
    assert liste_aus_hydration("<html></html>", "Offers") == []
    assert liste_aus_hydration('{"Offers":[kaputt', "Offers") == []


def test_925_soft_hyphens_werden_entfernt():
    """DER stille Killer: die Plattform setzt Trennhinweise MITTEN ins
    Wort. Ohne Bereinigung matcht kein Keyword — der Titel sieht nur
    fuer das Auge normal aus."""
    roh = "Syste\u00adm\u00adadmi\u00adnis\u00adtrator Windows (m/w/d)"
    assert "\u00ad" in roh
    sauber = entweiche_trennzeichen(roh)
    assert sauber == "Systemadministrator Windows (m/w/d)"
    assert "administrator" in sauber.lower()


def test_925_adapter_liefert_vollstaendige_stellen(html, monkeypatch):
    """Anker-Pflicht (#766) und echtes Gehalt (#827) muessen mitkommen."""
    from bewerbungs_assistent.job_scraper import ferchau

    stellen = ferchau._aus_offers(html, keywords=[])
    assert stellen, "Fixture muss Stellen ergeben"
    for s in stellen:
        assert s["title"] and "\u00ad" not in s["title"]
        assert s["url"].startswith("https://touch.ferchau.com/de/de/job/"), s["url"]
        assert s["source"] == "ferchau"
        assert s["location"]
        # Die Plattform liefert eine ECHTE Spanne — nie als Schaetzung
        # markieren (sonst zaehlt sie im Scoring gar nicht, #918).
        if s.get("salary_min"):
            assert s["salary_estimated"] is False
            assert s["salary_type"] == "jaehrlich"


def test_925_keyword_filter_arbeitet_clientseitig(html):
    """Der search-Parameter der Plattform wirkt nicht mehr — gefiltert
    wird hier, nicht per Query."""
    from bewerbungs_assistent.job_scraper import ferchau

    alle = ferchau._aus_offers(html, keywords=[])
    treffer = ferchau._aus_offers(html, keywords=["Systemadministrator"])
    assert len(alle) >= len(treffer)
    assert all("systemadministrator" in s["title"].lower()
               or "systemadministrator" in s["description"].lower()
               for s in treffer)
    # unpassendes Keyword filtert alles weg
    assert ferchau._aus_offers(html, keywords=["Zahnarzthelferin"]) == []
