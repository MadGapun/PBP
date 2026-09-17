"""Tests fuer #1057 — Geocoding lief ueber die Rohtreffer.

Gemeldet am 15.09.2026 als BEOBACHTUNG mit offener Frage, nicht als
Diagnose: die Laufkarte zeigte "Geocoding: 3540/4536 Standorte",
waehrend der ganze Bestand des Profils 2692 Stellen umfasste. Es wurden
in EINEM Lauf mehr Standorte gemeldet, als es Stellen gibt.

Am Code bestaetigt: der Schritt lief ueber die deduplizierten
Rohtreffer, also vor Altersfilter, Schwelle und Ausschluss-Begriffen.

**Die Reihenfolge ist zur Haelfte Absicht.** Seit #1034 rechnet der
Suchlauf den Score NACH dem Geocoding, weil der Score die Entfernung
liest — vorher trug der gespeicherte Wert eine Entfernung, die er nicht
kannte. Was daran nicht Absicht war, ist die MENGE: eine Stelle mit
Ausschluss-Treffer oder ausserhalb des Rechtsraums bekommt einen harten
k.o., und der liest die Entfernung nie.

Der dritte Teil des Berichts ist eine Anzeigefrage: gezaehlt wurden
STELLEN, gefragt wird der Dienst je ORT. Auf einer Bestandskopie
gemessen tragen 2458 Stellen mit Ort nur 501 verschiedene Ortsstrings,
der haeufigste 918-mal.

Alle Firmen und Orte sind Platzhalter.
"""
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.job_scraper import (  # noqa: E402
    calculate_score, geocoding_auswahl, harter_ausschluss,
)

FUELLTEXT = ("Wir bieten ein modernes Arbeitsumfeld mit flachen "
             "Hierarchien und viel Gestaltungsspielraum. ") * 4


def _krit(**extra):
    k = {"keywords_muss": ["Stammdaten"],
         "keywords_ausschluss": ["Zeitarbeit"],
         "max_entfernung": {"festanstellung": 50}}
    k.update(extra)
    return k


def _stelle(**extra):
    job = {"title": "Stammdaten Migration", "company": "Musterfirma GmbH",
           "location": "Musterstadt",
           "description": "Stammdaten und Migration. " + FUELLTEXT,
           "employment_type": "festanstellung"}
    job.update(extra)
    return job


# ══ Das Nadeloehr ═══════════════════════════════════════════════════

def test_ein_ausschluss_begriff_ist_ein_harter_ausschluss():
    """Der Grund kommt mit heraus, nicht nur ein Ja.

    Ohne ihn muesste der Aufrufer die Marken am Job nachschlagen — und
    ein Trichter, der nur zaehlen kann, belegt nichts (#813).
    """
    job = _stelle(description="Einsatz ueber Zeitarbeit. " + FUELLTEXT)
    befund = harter_ausschluss(job, _krit())
    assert befund["grund"] == "ausschluss_keyword"
    assert befund["keyword"] == "Zeitarbeit"
    assert job["_ko_ausschluss"] == "Zeitarbeit"


def test_ein_ort_ausserhalb_des_rechtsraums_ebenso():
    """#996: nur bei Positivbeleg, und dann hart."""
    job = _stelle(location="Remote (United States)")
    befund = harter_ausschluss(job, _krit())
    assert befund["grund"] == "ausserhalb_rechtsraum"
    assert job["_ko_ausserhalb"]


def test_eine_passende_stelle_faellt_nicht_durch():
    """Die Gegenrichtung (#966): eine Haertung, die nur in eine Richtung
    gemessen ist, kann den ganzen Lauf leeren."""
    assert harter_ausschluss(_stelle(), _krit()) is None
    # Auch ein unbekannter Ort ist kein Ausschluss — unbekannt ist nicht
    # "ausserhalb" (#989).
    assert harter_ausschluss(_stelle(location="Bedford"), _krit()) is None
    assert harter_ausschluss(_stelle(), None) is None


def test_der_ausschluss_liest_keine_pbp_notiz():
    """#917 Defekt D, an einer neuen Stelle.

    Redaktionelle Notizen stehen hinter dem `---`-Trenner im
    Anzeigentext. Ein k.o. aus der eigenen Notiz waere ein Eigentor: in
    #917 setzte eine LinkedIn-Bewerberstatistik eine 49er-Stelle auf 0.

    Der Weg ohne uebergebenen Text baut ihn selbst — er muss dieselbe
    Bereinigung machen wie `calculate_score`, sonst entscheidet die
    Reihenfolge der Aufrufer ueber das Ergebnis.
    """
    job = _stelle(description=(
        "Stammdaten und Migration. " + FUELLTEXT +
        "\n---\nPBP-Notiz: Verdacht auf Zeitarbeit, bitte pruefen."))
    assert harter_ausschluss(job, _krit()) is None
    assert calculate_score(dict(job), _krit()) > 0


def test_calculate_score_und_das_nadeloehr_sind_sich_einig():
    """Zwei Fassungen derselben Frage waeren #963.

    Geprueft wird die Aequivalenz an beiden k.o.-Gruenden und an der
    Gegenrichtung — der Score ist genau dann 0, wenn das Nadeloehr
    anschlaegt.
    """
    faelle = [
        _stelle(description="Einsatz ueber Zeitarbeit. " + FUELLTEXT),
        _stelle(location="Remote (United States)"),
        _stelle(),
        _stelle(title="Sachbearbeitung Einkauf", description=FUELLTEXT),
    ]
    for job in faelle:
        ko = harter_ausschluss(dict(job), _krit())
        punkte = calculate_score(dict(job), _krit())
        if ko:
            assert punkte == 0, (ko, job["title"])
        # Die Umkehrung gilt NICHT: eine Stelle ohne Pflichttreffer hat
        # ebenfalls 0, ist aber kein harter Ausschluss (#968). Genau
        # deshalb darf der Suchlauf nicht am Score entscheiden, wen er
        # geocodiert — er hat ihn an dieser Stelle noch gar nicht.


# ══ Die Reihenfolge im Suchlauf ═════════════════════════════════════

def _quelltext() -> str:
    pfad = _repo() / "src" / "bewerbungs_assistent" / "job_scraper" / "__init__.py"
    return pfad.read_text(encoding="utf-8")


def test_der_altersfilter_steht_vor_dem_geocoding():
    """Er braucht weder Score noch Entfernung.

    Bis v1.7.117 stand er dahinter — eine Anzeige von vor drei Monaten
    wurde also erst geocodiert und danach verworfen. Seine Stellung VOR
    der Schwelle bleibt, damit sich an der Filterkaskade nichts aendert.
    """
    text = _quelltext()
    alter = text.index("Stellenalter automatisch begrenzen")
    geo = text.index("# Geocoding: calculate distance for jobs with location")
    schwelle = text.index("# Filter out zero-score jobs (#53)")
    assert alter < geo < schwelle, (alter, geo, schwelle)


def test_der_score_bleibt_nach_dem_geocoding():
    """#1034 gilt weiter — und das ist der Grund, warum #1057 NICHT
    dadurch geloest wird, dass man das Geocoding einfach nach hinten
    schiebt. Der Score liest die Entfernung."""
    text = _quelltext()
    geo = text.index("# Geocoding: calculate distance for jobs with location")
    score = text.index('job["score"] = calculate_score(job, criteria)')
    assert geo < score


def test_die_auswahl_ueberspringt_die_k_o_stellen():
    """Der eigentliche Mechanismus, am Verhalten geprueft.

    Als Inline-Block in `run_search` war er von aussen nicht pruefbar —
    dieselbe Lage wie bei `quellen_einteilen` (v1.7.44 MERKE 2), und ein
    Guard auf eine Zeichenkette belegt nichts (v1.7.115 MERKE 6).
    """
    stellen = [
        _stelle(location="Musterstadt"),
        _stelle(location="Musterberg",
                description="Einsatz ueber Zeitarbeit. " + FUELLTEXT),
        _stelle(location="Remote (United States)"),
        _stelle(location="Musterstadt", distance_km=12.0),   # schon bekannt
        _stelle(location=""),                                # ohne Ort
    ]
    auswahl, orte, ko = geocoding_auswahl(stellen, _krit())
    assert [j["location"] for j in auswahl] == ["Musterstadt"]
    assert orte == 1
    assert ko == 2, "Ausschluss-Begriff und fremder Rechtsraum"


def test_die_k_o_marken_bleiben_am_job():
    """Gespart wird die Netzabfrage, nicht die Buchfuehrung.

    Der Trichter zaehlt diese Stellen weiter — waeren die Marken weg,
    meldete er weniger Verwerfungen als stattfinden (#940, #813).
    """
    job = _stelle(description="Einsatz ueber Zeitarbeit. " + FUELLTEXT)
    geocoding_auswahl([job], _krit())
    assert job["_ko_ausschluss"] == "Zeitarbeit"
    assert calculate_score(dict(job), _krit()) == 0


def test_ohne_kriterien_wird_nichts_uebersprungen():
    """Die Gegenrichtung: ohne Ausschlussliste faellt niemand heraus.

    Sonst haette ein leerer Kriterien-Satz still das halbe Geocoding
    abgeschaltet — und die Entfernung fehlte danach im Score.
    """
    stellen = [_stelle(location="Musterstadt"), _stelle(location="Musterberg")]
    auswahl, orte, ko = geocoding_auswahl(stellen, {})
    assert len(auswahl) == 2 and orte == 2 and ko == 0


def test_die_laufkarte_nennt_die_verschiedenen_orte():
    """Gezaehlt wurden STELLEN, gefragt wird je ORT.

    Der Zwischenspeicher in `geocoding_service` beantwortet jeden
    weiteren Treffer desselben Orts ohne Netz — die gemeldete Zahl war
    also nicht die Zahl der Abfragen. Eine Zahl, die etwas anderes
    bedeutet als sie sagt, ist genau die Klasse aus #1022 und #813.
    """
    # Die Zaehlung selbst, am Verhalten: dreimal derselbe Ort ist EINE
    # Abfrage, und die Schreibweise entscheidet nicht mit.
    stellen = [_stelle(location="Musterstadt"),
               _stelle(location="musterstadt "),
               _stelle(location="MUSTERSTADT"),
               _stelle(location="Musterberg")]
    auswahl, orte, _ = geocoding_auswahl(stellen, _krit())
    assert len(auswahl) == 4 and orte == 2

    text = _quelltext()
    # Die Schaetzung rechnet ueber die Orte, nicht ueber die Stellen —
    # mit der alten Rechnung sagte die Karte fuer einen Lauf 75 Minuten
    # voraus und war damit der Anlass fuer dieses Issue.
    assert "est_seconds = orte_verschieden" in text
    assert "est_seconds = total_geocode" not in text
    # Und beide Zahlen stehen in der MELDUNG — angesteuert ueber den
    # f-String selbst, nicht ueber den ersten Treffer des Wortes:
    # "verschiedene Orte" steht inzwischen auch im Docstring, und ein
    # Anker, der an zwei Stellen passt, prueft die falsche (v1.7.115
    # MERKE 6).
    assert 'f"Geocoding: {orte_verschieden} verschiedene Orte "' in text
    assert 'f"aus {total_geocode} Stellen' in text


@pytest.mark.parametrize("ort, erwartet", [
    ("Musterstadt", 1),
    ("musterstadt ", 1),   # dieselbe Abfrage, andere Schreibweise
    ("Musterberg", 2),
])
def test_dieselbe_schreibweise_zaehlt_einmal(ort, erwartet):
    """Die Zaehlung normalisiert wie der Zwischenspeicher des Dienstes.

    `geocode_location` schluesselt auf `location.strip().lower()`. Eine
    Zaehlung mit einer anderen Normalisierung wuerde eine Zahl anzeigen,
    die zur Zahl der Abfragen nicht passt — und damit denselben Fehler
    machen, den dieses Issue meldet.
    """
    stellen = [_stelle(location="Musterstadt"), _stelle(location=ort)]
    verschieden = len({str(j.get("location") or "").strip().lower()
                       for j in stellen})
    assert verschieden == erwartet
