"""#1277: der Bestands-Pruefer findet einen Namen in jeder Schreibweise.

Bis hier verglich `issue_text_pruefen` nur die gespeicherte Zeichenkette (mit
re.IGNORECASE). Ein Name mit "ö" im Bestand kam in Umschrift und Grossbuchstaben
("OE") als "sauber" durch und stand drei Wochen in einem oeffentlichen Issue.
Lehre 3: eine Liste findet nur ihre Schreibweise - beide Richtungen testen.

Alle Namen hier sind erfunden. Gegenrichtung: was NICHT treffen darf
(ein anderer Name, ein Platzhalter aus FIKTIVE_FIRMEN in fremder Schreibweise).
"""
import pytest

from bewerbungs_assistent.services import pii_bestand


@pytest.fixture
def bestand(tmp_db):
    db = tmp_db
    # Bestand mit Umlaut / ß / Bindestrich
    db.add_application({"company": "Hügelwerk Pumpentechnik", "title": "PLM",
                        "position": "PLM", "status": "beworben"})
    db.add_application({"company": "Kranbau-Lönsfeld", "title": "PDM",
                        "position": "PDM", "status": "beworben"})
    db.add_application({"company": "Weißmoor Fördertechnik", "title": "CAD",
                        "position": "CAD", "status": "beworben"})
    # Bestand in Umschrift
    db.add_application({"company": "Taelerhof Systemtechnik", "title": "CAD",
                        "position": "CAD", "status": "beworben"})
    db.add_application({"company": "Gruensattel Messbau", "title": "CAD",
                        "position": "CAD", "status": "beworben"})
    # Platzhalter aus FIKTIVE_FIRMEN ("anlagenbau sued"), hier mit Umlaut gespeichert
    db.add_application({"company": "Anlagenbau Süd", "title": "CAD",
                        "position": "CAD", "status": "beworben"})
    return db


def _treffer(db, text):
    return [t for t in pii_bestand.pruefe_text(db, text)["treffer"] if not t["unsicher"]]


# ------------------------------------------------ Bestand mit Umlaut, Text anders

@pytest.mark.parametrize("text", [
    "Bei Hügelwerk Pumpentechnik gab es Ärger.",          # wie gespeichert
    "Bei HUEGELWERK PUMPENTECHNIK gab es Ärger.",         # der Fall aus #1277
    "Bei Huegelwerk Pumpentechnik gab es Ärger.",
    "Bei HÜGELWERK PUMPENTECHNIK gab es Ärger.",
    "Bei Hügelwerk Pumpentechnik gab es Ärger.",    # zerlegtes Trema
    "Bei Hügelwerk-Pumpentechnik gab es Ärger.",          # Bindestrich statt Leerzeichen
    "Absage von Kranbau Lönsfeld.",                        # Leerzeichen statt Bindestrich
    "Absage von KRANBAU-LOENSFELD.",
    "Termin bei Weissmoor Foerdertechnik.",                # ß und ö in Umschrift
    "Termin bei WEISSMOOR FÖRDERTECHNIK.",
])
def test_bestand_mit_umlaut_trifft_jede_schreibweise(bestand, text):
    assert _treffer(bestand, text), f"nicht erkannt: {text!r}"


# ------------------------------------------------ Bestand in Umschrift, Text mit Umlaut

@pytest.mark.parametrize("text", [
    "Rückmeldung von Tälerhof Systemtechnik.",
    "Rückmeldung von TÄLERHOF SYSTEMTECHNIK.",
    "Rückmeldung von Taelerhof Systemtechnik.",
    "Gespräch bei Grünsattel Meßbau.",
    "Gespräch bei Grünsattel-Messbau.",
])
def test_bestand_in_umschrift_trifft_umlaut(bestand, text):
    assert _treffer(bestand, text), f"nicht erkannt: {text!r}"


# ------------------------------------------------ Anonymisieren ersetzt jede Schreibweise

def test_anonymisieren_ersetzt_umschrift(bestand):
    text = "HUEGELWERK PUMPENTECHNIK und Hügelwerk-Pumpentechnik sagten ab."
    erg = pii_bestand.anonymisiere_text(bestand, text)
    assert "huegel" not in erg["text"].lower() and "hügel" not in erg["text"].lower(), erg
    # beide Schreibweisen bekommen denselben Platzhalter
    assert erg["text"].count(erg["ersetzt"][0]["platzhalter"]) == 2, erg


# ------------------------------------------------ Gegenrichtung: was NICHT treffen darf

@pytest.mark.parametrize("text", [
    "Anlagenbau Süd ist ein Platzhalter.",
    "ANLAGENBAU SUED ist ein Platzhalter.",
    "Anlagenbau-Sued ist ein Platzhalter.",
    "Hügelwerk allein ist kein ganzer Name.",               # Teilwort eines Mehrwort-Namens
    "Hügelwerkstatt Pumpentechnik",                          # anderes Wort, Wortgrenze
    "Ein Tälerhofer Systemtechniker",                        # anderes Wort, Wortgrenze
])
def test_platzhalter_und_fremde_woerter_bleiben_sauber(bestand, text):
    assert not _treffer(bestand, text), pii_bestand.pruefe_text(bestand, text)


@pytest.mark.parametrize("a, b", [
    ("Anlagenbau Süd", "ANLAGENBAU SUED"),
    ("Kranbau-Lönsfeld", "kranbau loensfeld"),
    ("Weißmoor", "WEISSMOOR"),
    ("Grün_Feld", "gruen feld"),
])
def test_vergleichsform_gleich(a, b):
    assert pii_bestand.vergleichsform(a) == pii_bestand.vergleichsform(b)


def test_vergleichsform_unterscheidet_andere_namen():
    assert pii_bestand.vergleichsform("Hügelwerk") != pii_bestand.vergleichsform("Hagelwerk")
