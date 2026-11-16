"""#1383: Dokumenttyp aus dem Dateinamen nur an Wortgrenzen."""
import pytest

from bewerbungs_assistent.dashboard import _detect_doc_type as typ


@pytest.mark.parametrize("name, erwartet", [
    # der gemeldete Fall und seine Geschwister: Teilstring ist KEIN Treffer
    ("Lebenslauf_Bob_Mustermann.docx", "lebenslauf"),
    ("Anschreiben_Bob_Mustermann.docx", "anschreiben"),
    ("Mustermann_Zeugnis.pdf", "zeugnis"),
    ("Attest_Hausarzt.pdf", None),            # 'test' steckt in 'Attest'
    ("Testzentrum_Bescheinigung.pdf", "zertifikat"),
    ("Wissenschaftler_Zeugnis.pdf", "zeugnis"),   # 'wissen' steckt darin
    ("Standardlebenslauf_2026.docx", "lebenslauf"),
    ("Bildungsnachweis.pdf", None),          # 'bild' ist kein Foto
    ("Vitamin_Liste.txt", None),             # 'vita' steckt in 'Vitamin'
    ("Discoverer_Notiz.docx", None),         # 'cover' steckt in 'Discoverer'
    ("Offerte_Haus.pdf", None),
    # die echten Treffer bleiben (andere Richtung)
    ("Lebenslauf-Vorlage.docx", "vorlage"),
    ("CV_Template.docx", "vorlage"),
    ("Muster_Bewerbung.docx", "vorlage"),
    ("Generic_Anschreiben.docx", "vorlage"),
    ("Standard Anschreiben.docx", "vorlage"),
    ("Test_Datei.docx", "sonstiges"),
    ("Lebenslauf_Entwurf.docx", "sonstiges"),
    ("tmp_123.docx", "sonstiges"),
    ("Master-Wissen.md", "referenz"),
    ("Wissen_Notizen.docx", "referenz"),
    ("Absage_Firma.pdf", "absage"),
    ("Arbeitszeugnis_2020.pdf", "zeugnis"),
    ("Zeugnisse_Sammlung.pdf", "zeugnis"),
    ("Bewerbungsfoto.jpg", "foto"),
    ("Bild_1.jpg", "foto"),
    ("CV_2026.pdf", "lebenslauf"),
    ("Resume.docx", "lebenslauf"),
    ("Arbeitsvertrag.pdf", "angebot"),
    ("Einladung_Interview.pdf", "interview_einladung"),
    ("Interview confirmation - 24_05.eml", "interview_bestaetigung"),
])
def test_dateiname_schluesselwoerter_an_wortgrenzen(name, erwartet):
    assert typ(name, "") == erwartet, name
