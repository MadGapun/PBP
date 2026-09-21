"""Tests fuer v1.7.29 — #970: die Profil-Erkennung kannte halbe Berufsfelder.

Gemessen mit sechs Lebenslaeufen quer durch den Arbeitsmarkt: vier von
sechs wurden falsch oder gar nicht eingeordnet. Die Zuordnung steuert,
welche Jobboersen jemand ueberhaupt empfohlen bekommt — ein Handwerker
mit fuenfzehn Jahren Erfahrung bekam vier Quellen, weil das System ihn
nicht einordnen konnte, und erfuhr nicht, dass die Zahl aus Ratlosigkeit
stammt.

Der lehrreichste Einzelbefund: **"Kita" enthaelt "ki"**. Das
Tech-Kuerzel fuer kuenstliche Intelligenz matchte per Teilstring, und
eine Erzieherin mit acht Jahren Berufserfahrung galt damit als
Tech-Seniorin mit Confidence 0,85 — mit neun internationalen
Tech-Boards als Empfehlung.
"""
import pytest

from bewerbungs_assistent.services import berufsfeld
from bewerbungs_assistent.services import profile_classifier as pc


def _profil(titel, beschreibung, skill, start_jahr):
    return {
        "positions": [{"title": titel, "description": beschreibung,
                       "start_date": f"{start_jahr}-01-01"}],
        "skills": [{"name": skill}],
        "education": [],
    }


# Elf Lebenslaeufe quer durch den Arbeitsmarkt. Die vier technischen
# stehen bewusst mit dabei: eine Erweiterung fuer andere Berufsfelder
# darf sie nicht kippen.
FAELLE = [
    ("Pflegefachkraft", "Pflegefachkraft", "Intensivstation",
     "Intensivpflege", 2013, "health"),
    ("Erzieherin", "Erzieherin", "Kita, Krippe",
     "Krippenpaedagogik", 2017, "education"),
    ("Elektroniker", "Elektroniker Betriebstechnik", "Instandhaltung",
     "Schaltanlagen", 2010, "trade"),
    ("Grafikerin", "Grafikdesignerin", "Brand Design",
     "Adobe Creative Suite", 2019, "creative"),
    ("Buchhalterin", "Finanzbuchhalterin", "Monatsabschluesse",
     "DATEV", 2015, "admin_finance"),
    ("Koch", "Chef de Partie", "Gehobene Gastronomie",
     "HACCP", 2005, "hospitality"),
    ("Lagerist", "Lagerist", "Kommissionierung",
     "Gabelstapler", 2018, "retail_logistics"),
    # #1070: der Verkauf hat ein eigenes Feld bekommen. "service" war
    # bis v1.7.124 ein Sammelbecken fuer Handel, Reinigung, Pflege und
    # Gastronomie; die ABSICHT des Falls — eine Verkaeuferin bekommt die
    # deutschen Regionalportale und kein Tech-Board — ist unveraendert.
    ("Verkaeuferin", "Verkaeuferin", "Einzelhandel", "Kasse", 2020,
     "retail_logistics"),
    ("Softwareentwickler", "Softwareentwickler", "Backend, KI",
     "Python", 2016, "tech_senior"),
    ("PLM-Berater", "PLM Consultant", "Teamcenter Migration",
     "PLM", 2013, "engineering_senior"),
    ("Physiotherapeutin", "Physiotherapeutin", "Praxis",
     "Manuelle Therapie", 2016, "health"),
]


@pytest.mark.parametrize(
    "name,titel,beschreibung,skill,jahr,erwartet", FAELLE,
    ids=[f[0] for f in FAELLE])
def test_970_berufsfeld_wird_erkannt(name, titel, beschreibung, skill,
                                     jahr, erwartet):
    erg = pc.detect_profile_type(_profil(titel, beschreibung, skill, jahr))
    assert erg["type"] == erwartet, (name, erg["type"], erg["reasons"])
    assert erg["confidence"] >= 0.7


# ── Der Teilstring-Befund ────────────────────────────────────────────

def _begriffe(feld):
    """Die Indikatoren eines Feldes.

    #1070: sie standen bis v1.7.124 als `_TECH_KEYWORDS` und
    Geschwister in `profile_classifier` und liegen jetzt in
    `berufsfeld.FELDER`. Der Matcher heisst `treffer()` und gibt die
    gefundenen Begriffe zurueck statt nur True — die ABSICHT dieser
    Faelle ist unveraendert.
    """
    return berufsfeld.FELDER[feld]["begriffe"]


def test_970_kita_ist_kein_ki():
    """Der lehrreichste Einzelfall: "Kita" enthaelt "ki".

    Kurze Kuerzel brauchen Wortgrenzen. Laengere Indikatoren muessen
    weiter als Teilstring matchen — im Deutschen steckt "pflege" in
    "Intensivpflege".
    """
    assert not berufsfeld.treffer("Kita, Krippe", _begriffe("it"))


def test_970_echtes_kuerzel_trifft_weiterhin():
    """Die Gegenrichtung. Ein Matcher, der nach der Haertung nichts mehr
    findet, waere schlimmer als einer, der zu viel findet."""
    assert berufsfeld.treffer("Erfahrung mit KI und ML", _begriffe("it"))
    assert berufsfeld.treffer("Schwerpunkt AI", _begriffe("it"))


@pytest.mark.parametrize("text,feld", [
    ("Intensivpflege", "gesundheit"),
    ("Finanzbuchhalterin", "verwaltung"),
    ("Sozialpaedagogin", "bildung"),
    ("Servicetechniker", "handwerk"),
])
def test_970_komposita_treffen_weiterhin(text, feld):
    """Ohne Teilstring-Match fuer laengere Begriffe traefe die Erkennung
    an deutschen Komposita durchgehend daneben."""
    assert berufsfeld.treffer(text, _begriffe(feld))


def test_970_kurzes_kuerzel_nicht_in_beliebigem_wort():
    assert not berufsfeld.treffer("Detailarbeit", _begriffe("it"))


# ── Unsicher heisst unsicher, nicht "irgendwas" ──────────────────────

def test_970_nicht_einzuordnen_wird_als_solches_ausgewiesen():
    """Eine Confidence von 0,30 ist kein Ergebnis, sondern ein
    Achselzucken — dieselbe Haltung wie bei der unbekannten Entfernung
    (#965)."""
    erg = pc.detect_profile_type(
        _profil("Mitarbeiter", "Diverse Taetigkeiten", "Teamarbeit", 2015))
    assert erg["type"] == "mixed"
    assert erg.get("unsicher") is True
    assert erg.get("hinweis"), "Die Unsicherheit muss benannt werden"


def test_970_unsicher_empfiehlt_breit_nicht_schmal():
    """Der eigentliche Schaden: das nicht eingeordnete Profil bekam die
    KLEINSTE Quellenliste — ausgerechnet im Fall, in dem PBP am
    wenigsten weiss.

    #1070: verglichen wird jetzt mit den FELD-Listen; die Tabelle je
    Alt-Schluessel gibt es nicht mehr, weil die Empfehlung aus der
    Kombination von Feld, Form und Niveau entsteht.
    """
    erg = pc.recommend_sources(
        _profil("Mitarbeiter", "Diverse Taetigkeiten", "Teamarbeit", 2015))
    assert len(erg["recommended"]) >= 6, erg["recommended"]
    for eindeutig in ("gesundheit", "bildung", "gastgewerbe"):
        assert len(erg["recommended"]) >= len(
            berufsfeld.FELD_QUELLEN[eindeutig])


def test_970_unsicherheit_steht_in_der_begruendung():
    erg = pc.recommend_sources(
        _profil("Mitarbeiter", "Diverse Taetigkeiten", "Teamarbeit", 2015))
    assert "nicht sicher" in erg["rationale"]
    assert "BREIT" in erg["rationale"] or "breit" in erg["rationale"]


def test_970_erkanntes_profil_bleibt_ohne_unsicher_flag():
    erg = pc.recommend_sources(
        _profil("Pflegefachkraft", "Intensivstation", "Intensivpflege", 2013))
    assert not erg.get("unsicher")
    assert "nicht sicher" not in erg["rationale"]


# ── Struktur ─────────────────────────────────────────────────────────

def test_970_jedes_feld_hat_quellen():
    """Ein Feld ohne Quellen waere eine leere Empfehlung.

    #1070: geprueft wird das FELD statt des Alt-Schluessels — an ihm
    haengt die Empfehlung seither.
    """
    for feld in berufsfeld.FELDER:
        assert feld in berufsfeld.FELD_QUELLEN, feld
        assert berufsfeld.FELD_QUELLEN[feld], feld


def test_970_alle_empfohlenen_quellen_existieren():
    """Eine Empfehlung, die auf eine unbekannte Quelle zeigt, laesst
    sich nicht befolgen."""
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    for feld, quellen in berufsfeld.FELD_QUELLEN.items():
        unbekannt = [q for q in quellen if q not in SOURCE_REGISTRY]
        assert not unbekannt, (feld, unbekannt)


def test_970_kein_profil_bleibt_unveraendert():
    erg = pc.detect_profile_type(None)
    assert erg["type"] == "mixed"
    assert erg["confidence"] == 0.0
