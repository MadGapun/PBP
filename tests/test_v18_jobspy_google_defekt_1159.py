"""#1159: Google Jobs über JobSpy liefert mit python-jobspy 1.2.0 nichts mehr — die Quelle sagt es und taugt nicht als Auswahl.

Gemessen am 02.10. und 12.10.2026: „Google returned no job data“, null Zeilen. Entschieden (Nutzerauftrag 12.10.2026: alles
umsetzen): kennzeichnen statt herausnehmen. Die Quelle wird als defekt geführt; damit greift der Weg, den #1039 ohnehin für
defekte Quellen gebaut hat (fällt aus der gespeicherten Auswahl, wird beim Speichern abgelehnt, in keinem Lauf eingeplant, die
Karte nennt Grund und Ersatzweg). Neu hier: die Browser-Schwester behauptet nicht mehr, die automatische deckte Google ab, und die
Browser-Liste nennt dieselbe Quelle nicht zweimal.
"""
from __future__ import annotations

import pytest

from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY


@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


def test_die_quelle_ist_als_defekt_gefuehrt_mit_grund_und_weg():
    q = SOURCE_REGISTRY["jobspy_google"]
    assert q["defekt"] is True
    assert "1.2.0" in q["defekt_grund"] and "Google returned no job data" in q["defekt_grund"]
    assert "„Google Jobs (im Browser)“" in q["defekt_grund"], "der Grund nennt den Weg, der funktioniert"
    assert q["manueller_fallback"].startswith("https://www.google.com/search?"), \
        "die Karte macht aus dem ersten Wort einen Link (SourceSelectionList)"
    assert q["ersatz_quelle"] == "google_jobs" and q["ersatz_quelle"] in SOURCE_REGISTRY


def test_die_alte_warnung_vor_nullen_steht_nicht_mehr_da():
    """Sie war die Vorstufe: 'wenn 0 Treffer, im Browser suchen'. Jetzt steht der Befund selbst da."""
    assert "warnung" not in SOURCE_REGISTRY["jobspy_google"] or \
        "0 Treffer" not in SOURCE_REGISTRY["jobspy_google"]["warnung"]


def test_die_browser_schwester_behauptet_keine_automatische_abdeckung():
    q = SOURCE_REGISTRY["google_jobs"]
    assert "doppelt_mit" not in q
    assert "automatisch ab" not in q.get("warnung", ""), q.get("warnung")
    assert SOURCE_REGISTRY["jobspy_google"]["name"] not in q.get("warnung", "")


def test_eine_gespeicherte_auswahl_verliert_die_quelle():
    from bewerbungs_assistent.services.search_service import ohne_defekte
    assert ohne_defekte(["bundesagentur", "jobspy_google", "jobspy_indeed"], SOURCE_REGISTRY) == \
        ["bundesagentur", "jobspy_indeed"]


def test_beim_speichern_wird_sie_abgelehnt(tmp_db):
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    alt = dash._db
    dash._db = tmp_db
    try:
        antwort = TestClient(dash.app).post(
            "/api/sources", json={"active_sources": ["bundesagentur", "jobspy_google"]}).json()
    finally:
        dash._db = alt
    assert antwort["active_sources"] == ["bundesagentur"]
    assert antwort["abgelehnt_defekt"] == ["jobspy_google"]


def test_der_ersatzweg_ueber_den_browser_steht_in_der_liste_nicht_doppelt(tmp_db):
    from bewerbungs_assistent.services import browser_handoff
    eintraege = browser_handoff.browser_quellen(tmp_db, auswahl=["google_jobs", "jobspy_google"])
    schluessel = [e["key"] for e in eintraege]
    assert "google_jobs" in schluessel, "die gewaehlte Browser-Quelle bleibt in der Liste"
    assert "jobspy_google" not in schluessel, "die defekte Schwester wird nicht noch einmal genannt"
    text = browser_handoff.prompt(eintraege)
    assert "Google Jobs (im Browser)" in text and "Google Jobs (via JobSpy)" not in text


def test_andere_defekte_browserquellen_bleiben_in_der_optionalen_liste(tmp_db):
    """Die Ausnahme gilt nur fuer Quellen mit eigener Browser-Schwester (ersatz_quelle)."""
    from bewerbungs_assistent.services import browser_handoff
    eintraege = browser_handoff.browser_quellen(tmp_db, auswahl=[])
    arten = {e["key"]: e["art"] for e in eintraege}
    assert arten.get("heise_jobs") == browser_handoff.DEFEKT_NUR_BROWSER


def test_nur_quellen_mit_gueltiger_schwester_tragen_ersatz_quelle():
    for key, q in SOURCE_REGISTRY.items():
        if "ersatz_quelle" in q:
            assert q.get("defekt"), f"{key}: ersatz_quelle ohne defekt ist ohne Wirkung und verwirrt"
            assert q["ersatz_quelle"] in SOURCE_REGISTRY, key
