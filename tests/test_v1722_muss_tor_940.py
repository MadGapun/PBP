"""Tests fuer v1.7.22 — #940: MUSS-Keywords als praezises Tor.

Der Filter fehlte NIE. `calculate_score` bricht bei null MUSS-Treffern
ab und gibt 0 zurueck, und die Schwelle wird vor dem Speichern angewandt.
Ueberlistet wurde er eine Ebene tiefer, im Matcher: `_fuzzy_keyword_match`
ist fuer Recall gebaut (richtig fuer PLUS) und war unveraendert als
Torwaechter im Einsatz.

Gemessen am Live-Bestand vom 19.08.2026: mit dem alten Tor wurde von 19
aktiven Stellen KEINE abgewiesen, mit dem neuen sieben — und die Scores
aller uebrigen blieben unveraendert.
"""
import pytest

from bewerbungs_assistent.job_scraper import (
    _fuzzy_keyword_match,
    _muss_tor_match,
    calculate_score,
)

KRITERIEN = {
    "keywords_muss": ["PLM", "Product Lifecycle", "Engineering Data Management",
                      "Engineering Change Management"],
    "keywords_plus": ["Senior", "Remote", "Hamburg", "Festanstellung"],
    "keywords_minus": [],
    "keywords_ausschluss": [],
    "gewichtung": {"muss": 7, "plus": 3, "minus": 6},
    "min_score_schwelle": 15,
}


def _stelle(titel: str, beschreibung: str) -> dict:
    return {"title": titel, "description": beschreibung, "company": "Musterfirma GmbH"}


# ── Die Fehltreffer, die den Bestand geflutet haben ──────────────────

def test_940_mehrwort_split_qualifiziert_nicht_mehr():
    """Regressionsfall `d519906a` / `eecde8bc` / `c14b81f6`.

    'Engineering Data Management' passte, weil die drei Woerter irgendwo
    einzeln vorkamen — in fast jeder technischen Anzeige.
    """
    text = ("Wir suchen einen Senior Manager Data Analytics in Hamburg. "
            "Du arbeitest mit unserem Engineering-Team, verantwortest die "
            "Data Governance und das Management der Reporting-Strecke.")
    stelle = _stelle("Senior Manager Data Analytics (w/m/d)", text)

    # Der alte Matcher haelt es weiterhin fuer einen Treffer ...
    assert _fuzzy_keyword_match("Engineering Data Management", text)
    # ... das Tor nicht mehr.
    assert not _muss_tor_match("Engineering Data Management", text)
    assert calculate_score(stelle, KRITERIEN) == 0
    assert stelle.get("_ko_kein_muss") is True


def test_940_generische_synonym_phrase_qualifiziert_nicht_mehr():
    """Regressionsfall `ebd3539d`: 'plm' kommt null Mal vor.

    Ueber das Synonym 'product lifecycle' wurde aus einer
    Produktmanager-Anzeige eine PLM-Stelle.
    """
    text = ("Product Management Specialist for ICP-MS. You validate current "
            "and future technologies, manage product lifecycles, gather "
            "market intelligence and drive commercial success.")
    assert "plm" not in text.lower()
    assert _fuzzy_keyword_match("PLM", text)      # altes Verhalten
    assert not _muss_tor_match("PLM", text)       # neues Tor
    assert calculate_score(_stelle("Product Management Specialist", text),
                           KRITERIEN) == 0


def test_940_pluraler_wortanhang_qualifiziert_nicht():
    """'product lifecycles' ist nicht 'Product Lifecycle'."""
    text = "Sie steuern product lifecycles im Konsumgueterbereich."
    assert not _muss_tor_match("Product Lifecycle", text)


def test_940_nur_plus_keywords_ergeben_score_null():
    """Eine Hamburger Senior-Remote-Stelle ohne Fachbezug faellt durch."""
    text = ("Senior Software Engineer, Backend. Festanstellung, Remote, "
            "Standort Hamburg. Du baust skalierbare Dienste in Go.")
    stelle = _stelle("Senior Software Engineer, Backend", text)
    assert calculate_score(stelle, KRITERIEN) == 0


# ── Was weiterhin durchkommen MUSS ───────────────────────────────────

def test_940_echte_nennung_qualifiziert_weiterhin():
    text = ("Als PLM-Consultant betreust du die Einfuehrung unseres "
            "PLM-Systems im Maschinenbau.")
    assert _muss_tor_match("PLM", text)
    assert calculate_score(_stelle("PLM Consultant (m/w/d)", text),
                           KRITERIEN) > 0


def test_940_produktname_als_synonym_qualifiziert_weiterhin():
    """Eine Teamcenter-Stelle IST eine PLM-Stelle, auch ohne das Kuerzel.

    Genau deshalb duerfen die Synonyme nicht pauschal wegfallen — nur
    die generischen Mehrwort-Phrasen.
    """
    for produkt in ("Teamcenter", "Windchill", "Enovia", "Aras"):
        text = f"Administration und Customizing von {produkt} im Konzernumfeld."
        assert _muss_tor_match("PLM", text), produkt
        assert calculate_score(_stelle(f"{produkt} Administrator", text),
                               KRITERIEN) > 0, produkt


def test_940_zusammenhaengende_phrase_qualifiziert_weiterhin():
    text = ("Verantwortung fuer Product Lifecycle Management und die "
            "Ablaeufe im Engineering Change Management.")
    assert _muss_tor_match("Product Lifecycle", text)
    assert _muss_tor_match("Engineering Change Management", text)


def test_940_bindestrich_schreibweise_qualifiziert_weiterhin():
    """'PLM-System' und 'Product-Lifecycle' duerfen nicht durchfallen."""
    assert _muss_tor_match("PLM", "Betreuung des PLM-Systems")
    assert _muss_tor_match("Product Lifecycle", "Product-Lifecycle-Prozesse")


# ── Schwelle und Bestandsschutz ──────────────────────────────────────

def test_940_schwelle_wird_beim_anlegen_angewandt(tmp_db):
    """Unterhalb `min_score_schwelle` wird nicht als aktive Stelle angelegt.

    Der Filter sitzt im Suchpfad vor `save_jobs`. Bewusst NICHT daran
    gebunden sind manuelle Anlage, Plugin-Ingest und Newsletter — dort
    ist die Aufnahme eine Entscheidung des Nutzers.
    """
    from bewerbungs_assistent.job_scraper import _filter_nach_schwelle

    stellen = [
        {"hash": "s940a", "title": "PLM Consultant", "score": 40},
        {"hash": "s940b", "title": "Randlage", "score": 13},
        {"hash": "s940c", "title": "Genau Schwelle", "score": 15},
    ]
    behalten, verworfen = _filter_nach_schwelle(stellen, 15)
    assert [s["hash"] for s in behalten] == ["s940a", "s940c"]
    assert verworfen == 1


def test_940_qualifizierte_stellen_behalten_ihren_score():
    """Das Tor aendert die Punktevergabe NICHT (#942 macht das).

    Sonst verschieben sich alle Scores und die Wirkung des Tors waere
    nicht mehr isoliert messbar.
    """
    text = ("PLM Architect gesucht. Erfahrung mit Product Lifecycle "
            "Management, Senior-Level, Remote aus Hamburg moeglich.")
    stelle = _stelle("PLM Architect", text)
    mit_tor = calculate_score(dict(stelle), KRITERIEN)

    import bewerbungs_assistent.job_scraper as js
    echt = js._muss_tor_match
    try:
        js._muss_tor_match = js._fuzzy_keyword_match   # altes Verhalten
        ohne_tor = calculate_score(dict(stelle), KRITERIEN)
    finally:
        js._muss_tor_match = echt
    assert mit_tor == ohne_tor, (mit_tor, ohne_tor)
