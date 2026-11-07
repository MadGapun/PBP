"""1.8.2: "Kann ich PBP auf Englisch benutzen?" bekommt die FAQ-Antwort, nicht den Abschnitt zur Sprache der Anzeige.

Mit dem neuen Wiki-Abschnitt "Sprache der Anzeige" (#1308) beantwortete die Hilfe diese Frage sicher - mit dem falschen
Abschnitt. Die Frage stand bis dahin unter "ohne Antwort"; seit 1.8.2 beantwortet die FAQ sie.
"""
from bewerbungs_assistent.services import hilfe_suche as hs


def test_frage_nach_englischer_oberflaeche_trifft_die_faq():
    erg = hs.suche("Kann ich PBP in englischer Sprache benutzen?")
    assert erg.status == "gefunden"
    assert erg.treffer[0].abschnitt["id"] == "wiki:FAQ:kann_ich_pbp_auf_englisch_benutzen"


def test_frage_nach_englischen_anzeigen_nennt_den_stellen_abschnitt():
    erg = hs.suche("Wie blende ich englische Stellenanzeigen aus?")
    ids = [t.abschnitt["id"] for t in erg.treffer[:3]]
    assert "wiki:Tab-Stellen:sprache_der_anzeige_ab_1_8_2" in ids
