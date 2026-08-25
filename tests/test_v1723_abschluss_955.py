"""Tests fuer v1.7.23 — #955: Abschluss-Erkennung, beide Richtungen.

Die Mustersammlung kannte nur FORDERNDE Wendungen. Belegter Fall aus
#952: "Dein akademischer Hintergrund: Dein Studium bildet die
Ausgangsbasis fuer dein fundiertes Know-how" — eine klare Anforderung,
die auch mit vollstaendigem Text nicht erkannt wurde.

Die Richtung des Fehlers ist die unangenehme: nicht erkannt heisst
`false`, also "nicht gefordert". Und `hochschulabschluss_gefordert` ist
kein Anzeigefeld, sondern ein k.o.-Kriterium — `kein_hochschulabschluss`
steht in der Liste der Ablehnungsgruende.
"""
import pytest

from bewerbungs_assistent.job_scraper import _detect_degree_required


# ── Erkannt werden muss ──────────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Dein akademischer Hintergrund: Dein Studium bildet die Ausgangsbasis "
    "fuer dein fundiertes Know-how.",
    "Ihr Studium der Elektrotechnik ist die Grundlage.",
    "Your academic background in engineering is the foundation.",
    "Abgeschlossenes Studium der Informatik vorausgesetzt.",
    "Wir erwarten einen Hochschulabschluss.",
])
def test_955_beschreibende_und_fordernde_wendungen_werden_erkannt(text):
    assert _detect_degree_required(text) is True, text


# ── NICHT erkannt werden darf ────────────────────────────────────────

@pytest.mark.parametrize("text", [
    "Wir suchen Werkstudenten. Du bist im Studium der Informatik "
    "eingeschrieben.",
    "Praktikum fuer Studierende: Du absolvierst gerade dein Studium.",
    "Working student position: your studies in computer science.",
    "Duales Studium Maschinenbau — Start im Herbst.",
    "Abschlussarbeit im Bereich Datenanalyse: dein Studium der Mathematik "
    "passt dazu.",
])
def test_955_zielgruppe_studierende_ist_keine_anforderung(text):
    """Werkstudenten- und Praktikumsanzeigen nennen 'Studium' als
    Zielgruppe. Eine Wortliste ohne diesen Kontext verwechselt beides —
    genau davor warnt das Issue."""
    assert _detect_degree_required(text) is False, text


@pytest.mark.parametrize("text", [
    "Wir suchen einen Mechaniker mit mehrjaehriger Berufserfahrung.",
    "Erfahrung in der Fertigung ist wichtiger als Zeugnisse.",
])
def test_955_ohne_abschlussbezug_bleibt_es_bei_nein(text):
    assert _detect_degree_required(text) is False, text


def test_955_quereinsteiger_klausel_schlaegt_die_beschreibung(text=None):
    """Die Abschwaechung aus #536 gilt auch fuer die neuen Muster."""
    assert _detect_degree_required(
        "Quereinsteiger willkommen. Dein Studium bildet die Basis.") is False


def test_955_abgeschlossenes_studium_zaehlt_auch_bei_studierenden_bezug():
    """Ein Trainee-Programm, das ausdruecklich einen ABGESCHLOSSENEN
    Abschluss verlangt, bleibt eine Anforderung — auch wenn das Wort
    'Praktikum' irgendwo im Text steht."""
    assert _detect_degree_required(
        "Trainee-Programm: abgeschlossenes Studium erforderlich, "
        "vorheriges Praktikum von Vorteil.") is True


def test_955_bewerberstatistik_loest_weiterhin_nichts_aus():
    """Regression zu #918 Defekt 2: Zeilen ueber ANDERE Bewerber."""
    assert _detect_degree_required(
        "21 % der Bewerber haben den Abschluss Master, 17 % Bachelor der "
        "Ingenieurswissenschaften.") is False
