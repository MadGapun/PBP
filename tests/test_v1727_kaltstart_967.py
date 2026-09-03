"""Tests fuer v1.7.27 — #967: der Kaltstart darf keine leere Liste sein.

Gemessen am 02.09.2026 mit sechs Lebenslaeufen quer durch den
Arbeitsmarkt: nach `profil_erstellen()` liefert `get_search_criteria()`
ein leeres Objekt. Ohne Keywords vergibt `calculate_score` jeder Stelle
eine Null, und der Schwellenfilter verwirft alles — 7 von 7, unabhaengig
vom Beruf.

`run_search` erwaehnte `keywords_muss` dabei null Mal: keine Pruefung,
keine Warnung. Die Suche lief durch, holte Stellen von allen Quellen und
warf sie am Ende geschlossen weg.

Das ist der erste Eindruck des Werkzeugs, und er trifft jeden neuen
Menschen — nicht nur ein Berufsfeld.
"""
import pytest

from bewerbungs_assistent.services.suchbereitschaft import (
    MAX_ABGELEITET,
    ableiten,
    pruefe,
)

BERUFE = [
    ("Pflegefachkraft (m/w/d) Intensivstation", "Intensivpflege"),
    ("Erzieher / Erzieherin (m/w/d)", "Krippenpaedagogik"),
    ("Elektroniker fuer Betriebstechnik (m/w/d)", "Schaltanlagen"),
    ("Koch / Koechin (m/w/d)", "HACCP"),
    ("Senior Grafikdesigner (m/w/d) Brand Design", "Typografie"),
    ("Finanzbuchhalter (m/w/d)", "DATEV"),
]


# ── Ableiten funktioniert berufsunabhaengig ──────────────────────────

@pytest.mark.parametrize("titel,skill", BERUFE, ids=[b[0][:20] for b in BERUFE])
def test_967_ableitung_funktioniert_in_jedem_berufsfeld(titel, skill):
    """Der Kern der Sache: keine Fachwortliste, sondern das, was der
    Mensch selbst aufgeschrieben hat."""
    begriffe = ableiten({
        "positions": [{"title": titel}],
        "skills": [{"name": skill}],
    })
    assert begriffe, f"Nichts abgeleitet aus {titel!r}"
    assert skill in begriffe


def test_967_zusaetze_werden_entfernt():
    """'(m/w/d)' und 'Senior' sagen nichts ueber den Beruf."""
    begriffe = ableiten({
        "positions": [{"title": "Senior Grafikdesigner (m/w/d) Brand Design"}]})
    assert begriffe == ["Grafikdesigner Brand Design"], begriffe


def test_967_doppelte_begriffe_fallen_weg():
    begriffe = ableiten({
        "positions": [{"title": "Pflegefachkraft"}, {"title": "Pflegefachkraft"}],
        "skills": [{"name": "pflegefachkraft"}]})
    assert len(begriffe) == 1


def test_967_ableitung_bleibt_ueberschaubar():
    """Zwanzig Begriffe wuerden die Quellen in Einzelabfragen ertraenken."""
    profil = {"skills": [{"name": f"Faehigkeit {i}"} for i in range(30)]}
    assert len(ableiten(profil)) == MAX_ABGELEITET


def test_967_leeres_profil_ergibt_nichts():
    assert ableiten({}) == []
    assert ableiten(None) == []


# ── Die vier Zustaende der Vorab-Pruefung ────────────────────────────

def test_967_ohne_profil_nicht_bereit(tmp_db):
    stand = pruefe(tmp_db)
    assert stand["bereit"] is False
    assert stand["quelle"] == "leer"
    assert "Profil" in stand["grund"]
    assert stand["naechster_schritt"]


def test_967_leeres_profil_nicht_bereit(tmp_db):
    tmp_db.create_profile("Neue Nutzerin", "neu@example.com")
    stand = pruefe(tmp_db)
    assert stand["bereit"] is False
    assert stand["naechster_schritt"], "Ohne Weg nach vorn ist es nur ein Nein"


def test_967_profil_mit_station_wird_abgeleitet(tmp_db):
    tmp_db.create_profile("Neue Nutzerin", "neu@example.com")
    tmp_db.add_position({"title": "Pflegefachkraft (m/w/d)",
                         "company": "Musterklinik", "start_date": "2014-01-01"})
    tmp_db.add_skill({"name": "Intensivpflege"})
    stand = pruefe(tmp_db)
    assert stand["bereit"] is True
    assert stand["quelle"] == "profil"
    assert "Pflegefachkraft" in stand["keywords_plus"]
    assert stand["hinweis"], "Die Ableitung muss benannt werden"
    assert "suchkriterien_setzen" in stand["hinweis"]


def test_967_abgeleitet_wird_nur_plus_nie_muss(tmp_db):
    """Ein MUSS-Begriff ist ein Ausschlusskriterium. Ihn zu erraten
    wuerde genau die Stellen unsichtbar machen, die der Mensch noch
    nicht benennen konnte."""
    tmp_db.create_profile("Neue Nutzerin", "neu@example.com")
    tmp_db.add_position({"title": "Erzieherin", "company": "Musterkita",
                         "start_date": "2018-01-01"})
    stand = pruefe(tmp_db)
    assert stand["keywords_muss"] == []


def test_967_gesetzte_kriterien_bleiben_unangetastet(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    tmp_db.add_position({"title": "Erzieherin", "company": "Musterkita",
                         "start_date": "2018-01-01"})
    tmp_db.set_search_criteria("keywords_muss", ["Kita"])
    stand = pruefe(tmp_db)
    assert stand["quelle"] == "kriterien"
    assert stand["keywords_muss"] == ["Kita"]
    assert "hinweis" not in stand


def test_967_leerstrings_zaehlen_nicht_als_kriterien(tmp_db):
    """Sonst gilt eine versehentlich leere Liste als gesetzt."""
    tmp_db.create_profile("Nutzerin", "n@example.com")
    tmp_db.set_search_criteria("keywords_muss", ["", "  "])
    stand = pruefe(tmp_db)
    assert stand["quelle"] != "kriterien"


# ── Verdrahtung in run_search ────────────────────────────────────────

def _quelle() -> str:
    from pathlib import Path
    return (Path(__file__).resolve().parents[1] / "src" /
            "bewerbungs_assistent" / "job_scraper" /
            "__init__.py").read_text(encoding="utf-8")


def test_967_run_search_prueft_vor_dem_lauf():
    """Der beste Baustein nuetzt nichts, wenn ihn niemand aufruft
    (DoD 8c)."""
    quelle = _quelle()
    assert "suchbereitschaft as _bereit" in quelle
    assert "_bereit.pruefe(db)" in quelle


def test_967_pruefung_steht_vor_dem_ersten_quellenaufruf():
    """Nach dem Lauf zu pruefen haette die Quellen belastet und dem
    Menschen trotzdem eine leere Liste gezeigt."""
    quelle = _quelle()
    i_pruef = quelle.index("_bereit.pruefe(db)")
    i_keywords = quelle.index("params[\"keywords\"] = build_search_keywords(db)")
    assert i_pruef < i_keywords


def test_967_abbruch_nennt_den_naechsten_schritt():
    quelle = _quelle()
    assert "nicht_gestartet" in quelle
    assert "naechster_schritt" in quelle


def test_967_ohne_muss_wird_nicht_aussortiert():
    """Die Leitlinie 'lieber ein Job zu viel', angewendet auf den
    Kaltstart: ohne MUSS-Begriffe hat jede Stelle Score 0, die Schwelle
    wuerde also den kompletten Lauf verwerfen."""
    quelle = _quelle()
    assert "ungefiltert_ohne_muss" in quelle
    assert "ohne_muss_ungefiltert" in quelle


def test_967_ableitung_wird_im_ergebnis_benannt():
    """Still andere Begriffe zu verwenden waere derselbe Fehlertyp wie
    ein stiller Score-Ueberschrieb (#963)."""
    assert "suchbegriffe_abgeleitet" in _quelle()


def test_967_expliziter_aufruf_wird_nicht_abgewiesen():
    """Wer Suchbegriffe ausdruecklich mitgibt, hat eine Grundlage — die
    Pruefung gilt dem leeren Kaltstart, nicht dem gezielten Aufruf.

    Aufgefallen an zwei Alt-Tests (`test_scraper_adapter_v2`), die
    `run_search` mit `keywords` im Parameter aufrufen, ohne Kriterien in
    der DB zu setzen. Meine erste Fassung brach dort ab.
    """
    quelle = _quelle()
    assert '_explizit = bool(params.get("keywords"))' in quelle
    assert 'if not _stand["bereit"] and not _explizit:' in quelle
