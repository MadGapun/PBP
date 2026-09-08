"""Tests fuer v1.7.45 — #996: 'remote' schaltete die Ortspruefung ab.

Vom Nutzer am 08.09.2026 bemerkt:

    "Was habe ich mit US zu tun? Denke das ist ein Fehler, zumal wir nur
    deutsche bzw. Quellen fuer den deutschsprachigen Raum durchsuchen."

Er hatte recht. In den Suchkriterien standen `regionen: [Hamburg, Wedel,
Schleswig-Holstein, Remote, Deutschland, DACH]` und 30 km
Maximalentfernung — und trotzdem konnten Stellen im Bestand landen, auf
die man sich von Deutschland aus gar nicht bewerben kann.

Die Kette hatte drei Stufen, aber nur die letzte ist die Ursache:

1. `remoteok`, `remotive` und `himalayas` werten `regionen` gar nicht
   aus — sie holen den globalen Feed.
2. Sie setzen pauschal `location: "Remote"`.
3. **`entfernungs_guete` gab fuer `remote_level == "remote"` pauschal
   `entfaellt` zurueck — also KEINEN Abzug, egal wo die Stelle liegt.**

Gemessen am 08.09. ueber alle drei Adapter ohne Keyword-Filter:
eine Boerse 20 von 20 Treffern ausserhalb DACH (0 %!), die zweite 90 von
100, die dritte 3 von 17.

**"Remote" heisst nicht "von ueberall", sondern "ohne festen Buerositz
INNERHALB eines Rechtsraums".** Eine US-gebundene Rolle ist von Hamburg
aus nicht weit weg, sondern gar nicht bewerbbar.

Die Regel ist bewusst ein POSITIVBELEG: ausgeschlossen wird nur, wo ein
Nicht-DACH-Land ausdruecklich dasteht. Die Tests unten pruefen beide
Richtungen — gerade die Gegenproben, weil ein falscher Ausschluss teurer
ist als ein zu hoher Score (#827).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.services import arbeitsregion as ar  # noqa: E402
from bewerbungs_assistent.job_scraper import (  # noqa: E402
    calculate_score, entfernungs_guete, fit_analyse,
)

KRITERIEN = {"keywords_muss": ["PLM"], "keywords_ausschluss": [],
             "gewichtung": {}}


def _stelle(ort, remote="remote"):
    return {"title": "PLM Consultant", "description": "PLM " * 40,
            "location": ort, "remote_level": remote}


# ── Die Einordnung ────────────────────────────────────────────────────

def test_996_explizit_genanntes_land_ist_ausserhalb():
    """Die Ortsangaben, die am 08.09. tatsaechlich geliefert wurden."""
    for ort, land in (("Remote (United States)", "united states"),
                      ("Remote (Romania)", "romania"),
                      ("Remote (New Zealand)", "new zealand")):
        lage, belege = ar.einordnen(ort)
        assert lage == ar.AUSSERHALB, ort
        assert land in belege, ort


def test_996_mehrere_laender_ohne_dach_bleiben_ausserhalb():
    lage, belege = ar.einordnen("Remote (Argentina Belize Colombia)")
    assert lage == ar.AUSSERHALB
    assert set(belege) == {"argentina", "belize", "colombia"}


def test_996_dach_gewinnt_auch_neben_fremden_laendern():
    """"Germany, France" ist bewerbbar — die Nennung des eigenen
    Rechtsraums schlaegt alles andere."""
    assert ar.einordnen("Remote (Germany)")[0] == ar.DACH
    assert ar.einordnen("Germany, France, Spain")[0] == ar.DACH
    assert ar.einordnen("Berlin, Deutschland")[0] == ar.DACH
    assert ar.einordnen("Wien, Oesterreich")[0] == ar.DACH


def test_996_umfassende_angaben_schliessen_dach_ein():
    """"Europe" oder "Worldwide" umfasst Deutschland — auch wenn
    daneben andere Regionen stehen."""
    for ort in ("Worldwide", "Anywhere", "Europe",
                "LATAM, Europe, USA, Canada, APAC", "EMEA"):
        assert ar.einordnen(ort)[0] == ar.DACH, ort


def test_996_kein_ausschluss_auf_verdacht():
    """Der wichtigste Test. Orte, die fremd KLINGEN, aber nichts
    beweisen, bleiben unbekannt — es gibt deutsche Orte mit solchen
    Namen, und ein falscher Ausschluss ist teurer als ein zu hoher
    Score (#827)."""
    for ort in ("Bedford", "Nassau", "Remote", "", "Hamburg",
                "Visakhapatnam Rural mandal"):
        assert ar.einordnen(ort)[0] == ar.UNBEKANNT, ort


def test_996_kurze_laenderkuerzel_erzeugen_keine_fehlalarme():
    """"us" steckt in "Kundenservice" und "Industrie", "eu" in "Europa"
    — ohne Wortgrenzen waere die Regel unbenutzbar (#929)."""
    for text in ("Kundenservice Industrie", "Gehaeusebau",
                 "Statusmeldung", "Aussendienst"):
        assert ar.einordnen(text)[0] == ar.UNBEKANNT, text


def test_996_berechnete_entfernung_schlaegt_jede_textdeutung():
    """Wer Koordinaten hat, ist im Inland — das Geocoding hat den Ort
    ja aufgeloest."""
    job = _stelle("Remote (United States)")
    job["distance_km"] = 12.4
    assert ar.ausserhalb(job) == (False, [])


def test_996_hinweis_nennt_das_land_statt_zu_kategorisieren():
    text = ar.hinweis(["united states"])
    assert "United States" in text
    assert "nicht bewerbbar" in text


# ── Die Wirkung im Score ──────────────────────────────────────────────

def test_996_us_gebundene_stelle_ist_ein_ko():
    """Vorher: voller Score, weil 'remote' die Entfernung entfallen
    liess. Jetzt: 0."""
    job = _stelle("Remote (United States)")
    assert calculate_score(job, KRITERIEN) == 0
    assert job["_ko_ausserhalb"] == ["united states"]
    assert "nicht bewerbbar" in job["_ko_ausserhalb_hinweis"]


def test_996_deutsche_remote_stelle_bleibt_unangetastet():
    """Die Gegenprobe: der Fix darf die eigentliche Zielgruppe nicht
    treffen."""
    assert calculate_score(_stelle("Remote (Germany)"), KRITERIEN) > 0
    assert calculate_score(_stelle("Remote"), KRITERIEN) > 0
    assert calculate_score(_stelle("Worldwide"), KRITERIEN) > 0


def test_996_entfernungs_guete_sagt_verletzt_statt_entfaellt():
    """Der Kern des Issues, an der Stelle, an der er sass."""
    guete, grund = entfernungs_guete(_stelle("Remote (United States)"))
    assert guete == "verletzt"
    assert "United States" in grund

    guete, grund = entfernungs_guete(_stelle("Remote (Germany)"))
    assert guete == "entfaellt"

    # Ohne Ortsangabe bleibt es beim alten Verhalten.
    guete, _ = entfernungs_guete(_stelle("Remote"))
    assert guete == "entfaellt"


def test_996_beide_rechenwege_sind_sich_einig():
    """Die Lehre aus #963 und sechs Wiederholungen: eine Regel in nur
    EINEN von zwei parallelen Rechenwegen zu bauen verschiebt die
    Divergenz bloss."""
    for ort in ("Remote (United States)", "Remote (Germany)", "Remote",
                "Remote (Romania)", "Worldwide"):
        job = _stelle(ort)
        score = float(calculate_score(dict(job), KRITERIEN))
        fit = float(fit_analyse(dict(job), KRITERIEN)["total_score"])
        assert score == fit, f"{ort}: Score {score} gegen Fit {fit}"


def test_996_fit_analyse_nennt_den_grund():
    ergebnis = fit_analyse(_stelle("Remote (United States)"), KRITERIEN)
    assert ergebnis["total_score"] == 0
    assert ergebnis["ko_ausserhalb"] == ["united states"]
    assert any("nicht bewerbbar" in r for r in ergebnis["risks"])


def test_996_vor_ort_stelle_im_ausland_faellt_auch_heraus():
    """Der Fall ist nicht auf Remote beschraenkt — eine Vor-Ort-Stelle
    in den USA ist genauso wenig bewerbbar."""
    job = _stelle("Austin, United States", remote="vor_ort")
    assert calculate_score(job, KRITERIEN) == 0
