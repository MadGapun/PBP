"""Tests fuer v1.7.143 - #1124: der PII-Pruefer haelt Staedtenamen nicht mehr
fuer sichere Firmentreffer.

Gefunden beim PII-Sweep zu #1120 (29.09.2026): `issue_text_pruefen` meldete
den Namen einer Grossstadt mit `unsicher: false` - in einem Fixture, in dem
die Stadt nur als Ort steht ("PLM <Stadt>"). Wer den Hinweis "NICHT
veroeffentlichen" zum dritten Mal fuer einen Ortsnamen sieht, uebergeht ihn
auch beim echten Treffer (L25).

Die Messung am echten Bestand (Kopie, 2.200 Pruefnamen): genau EIN Name war
ein reiner Ortsname, und er stammt aus `jobs.company`, nicht aus
Firmenrecherchen - die Recherchetabelle liefert dem Pruefer keine Namen.
Deshalb gibt es nur die Haelfte des Vorschlags im Issue: den Ortsnamen als
`unsicher` melden. Alle Firmen und Orte sind hier erfunden oder allgemein.
"""
import pytest

from bewerbungs_assistent.services import pii_bestand
from bewerbungs_assistent.services.geocoding_service import ist_ortsname


def _stelle(db, hash_, firma):
    db.save_jobs([{
        "hash": hash_, "title": "PLM Manager", "company": firma,
        "location": "Hamburg", "url": f"https://beispiel.example/{hash_}",
        "source": "stepstone", "description": "Ein Text. " * 20,
        "score": 10, "employment_type": "festanstellung"}])


def _treffer(erg, name):
    return next((t for t in erg["treffer"] if t["name"].lower() == name), None)


def test_1124_ein_ortsname_allein_ist_unsicher(tmp_db):
    """AK 1: Ortsname allein wird `unsicher`, der Text gilt als veroeffentlichbar."""
    _stelle(tmp_db, "o1", "Hamburg")
    erg = pii_bestand.pruefe_text(tmp_db, "Suche nach PLM Hamburg mit Filter.")
    treffer = _treffer(erg, "hamburg")
    assert treffer is not None, "der Name wird weiter GEMELDET, nicht verschwiegen"
    assert treffer["unsicher"] is True
    assert "Ortsname" in treffer["unsicher_grund"]
    assert erg["sauber"] is True
    assert erg["davon_unsicher"] == 1


def test_1124_eine_firma_mit_ort_im_namen_bleibt_ein_sicherer_treffer(tmp_db):
    """AK 2: die Gegenrichtung - sonst wuerde der Pruefer schweigen, wo er
    warnen muss."""
    _stelle(tmp_db, "o2", "Hamburg Beispielwerk GmbH")
    erg = pii_bestand.pruefe_text(tmp_db, "Hamburg Beispielwerk GmbH hat abgesagt.")
    treffer = _treffer(erg, "hamburg beispielwerk gmbh")
    assert treffer is not None and treffer["unsicher"] is False
    assert erg["sauber"] is False
    # Auch die Kurzform ohne Rechtsform (Mehrwort) bleibt sicher.
    kurz = pii_bestand.pruefe_text(tmp_db, "Bei Hamburg Beispielwerk lief das so.")
    treffer = _treffer(kurz, "hamburg beispielwerk")
    assert treffer is not None and treffer["unsicher"] is False


def test_1124_ein_ort_mit_rechtsform_ist_eine_firma(tmp_db):
    """"Hamburg Holding" ist eine Firma - die Rechtsform direkt dahinter
    schlaegt das Ortsargument."""
    _stelle(tmp_db, "o3", "Hamburg")
    erg = pii_bestand.pruefe_text(tmp_db, "Die Hamburg Holding schrieb zurueck.")
    treffer = _treffer(erg, "hamburg")
    assert treffer is not None and treffer["unsicher"] is False


def test_1124_das_anonymisieren_ersetzt_einen_ortsnamen_nicht(tmp_db):
    """Unsichere Treffer werden nicht ersetzt, sondern zur Entscheidung
    vorgelegt - eine Stadt durch "<FIRMA>" zu ersetzen entstellt den Satz."""
    _stelle(tmp_db, "o4", "Hamburg")
    erg = pii_bestand.anonymisiere_text(tmp_db, "Suche nach PLM Hamburg mit Filter.")
    assert "Hamburg" in erg["text"]
    assert erg["zur_entscheidung"][0]["grund"] == "Der Name ist zugleich ein Ortsname."


@pytest.mark.parametrize("name,erwartet", [
    ("Hamburg", True), ("MÜNCHEN", True), ("muenchen", True), ("Wien", True),
    ("  Zürich ", True), ("Deutschland", True),
    ("Beispielwerk", False), ("Hamburg Wasser", False), ("", False),
    (None, False),
])
def test_1124_die_ortsliste_kommt_aus_der_standort_erkennung(name, erwartet):
    """Eine Liste, kein Nachbau (#963): der Test haelt die Schnittstelle zur
    Standort-Erkennung fest. Verglichen wird der GANZE Name."""
    assert ist_ortsname(name) is erwartet
