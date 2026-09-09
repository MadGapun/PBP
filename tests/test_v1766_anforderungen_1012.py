"""Tests fuer v1.7.66 — #1012: Schreibvarianten zaehlen mehrfach.

Der Fachscore ist eine Summe ueber getroffene MUSS-Begriffe, und die
Summanden sind nicht unabhaengig. Gemessen beim Abschluss von #1003:

    Anzeige nennt den Sachverhalt einmal          ->  7,0 Punkte
    Anzeige nennt DENSELBEN in drei Schreibweisen -> 21,0 Punkte

Faktor 3 fuer eine blosse Umformulierung — das verschiebt die
SORTIERUNG und, ueber `min_score_schwelle`, was ueberhaupt gespeichert
wird.

Zur Abgrenzung ebenfalls gemessen und hier festgehalten: eine
WIEDERHOLUNG blaeht nicht (20x = 1x). Der Fehler sitzt allein in der
Mehrfach-Vertretung eines Sachverhalts in der KRITERIEN-Liste.

**Die gefaehrlichste Stelle ist der Hoechstwert.** `score_maximum`
rechnet ueber dieselbe Liste; gruppierte er nicht mit, waere er nicht
mehr erreichbar und die in #999 gepruefte Eigenschaft gebrochen — eine
Anzeige, die alles trifft, muss exakt 100 % ergeben.
"""
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.job_scraper import (  # noqa: E402
    calculate_score, fit_analyse, score_maximum,
)
from bewerbungs_assistent.services import anforderungen as anf  # noqa: E402


def _stelle(text, titel="Consultant"):
    return {"title": titel, "company": "Musterwerk GmbH",
            "location": "Hamburg", "description": text}


_KRIT = {
    "keywords_muss": ["plm", "product lifecycle management", "plm-system"],
    "gewichtung": {"muss": 7},
}


# ══ Die Beziehungen sind belegt, nicht geraten ══════════════════════

def test_1012_wortmengen_enthaltensein_ist_dieselbe_anforderung():
    """"plm" steckt in "plm system" — wer beides schreibt, meint eines."""
    assert anf.dieselbe_anforderung("plm", "plm system")
    assert anf.dieselbe_anforderung("PLM-System", "plm")


def test_1012_abkuerzung_und_ausschreibung_gehoeren_zusammen():
    """Die Anfangsbuchstaben ergeben die Abkuerzung."""
    assert anf.dieselbe_anforderung("plm", "product lifecycle management")
    assert anf.dieselbe_anforderung("Product Lifecycle Management", "PLM")


def test_1012_verschiedene_faecher_bleiben_getrennt():
    """Die Gegenrichtung — und die wichtigere.

    Ein falsch zusammengefasster Begriff kostet Punkte, die der Mensch
    gemeint hat. Lieber eine Blaehung uebrig lassen als eine
    Anforderung schlucken.
    """
    assert not anf.dieselbe_anforderung("plm", "buchhaltung")
    assert not anf.dieselbe_anforderung("cad", "erp")
    assert not anf.dieselbe_anforderung("qualitaetsmanagement", "projektmanagement")


def test_1012_echte_synonyme_ohne_beleg_werden_nicht_geraten():
    """Bewusste Grenze, damit sie niemand fuer einen Fehler haelt.

    "PDM" und "Teilestammpflege" meinen dasselbe und stehen in keiner
    der beiden beweisbaren Beziehungen. PBP fasst sie NICHT zusammen —
    eine Aehnlichkeitsrechnung waere geraten.
    """
    assert not anf.dieselbe_anforderung("pdm", "teilestammpflege")


def test_1012_gruppen_sind_transitiv():
    """Haengt A an B und B an C, sind alle drei eine Anforderung."""
    g = anf.gruppen(["plm", "plm system", "product lifecycle management"])
    assert len(g) == 1
    assert len(g[0]) == 3


def test_1012_die_gruppe_zaehlt_mit_ihrem_staerksten_mitglied():
    """Nicht der Durchschnitt und nicht der erste Eintrag.

    Der Mensch kann einem Begriff ein hoeheres Einzelgewicht gegeben
    haben (#778); die Gruppe ist so viel wert wie ihr wertvollstes
    Mitglied — nie mehr, nie weniger.
    """
    punkte = {"plm": 2.0, "plm system": 9.0, "buchhaltung": 3.0}
    erg = anf.zaehlbare_punkte(list(punkte), lambda kw: punkte[kw])
    assert sorted(erg) == [3.0, 9.0]


# ══ Der belegte Fall ════════════════════════════════════════════════

def test_1012_dreifache_nennung_blaeht_nicht_mehr():
    """Der gemeldete Fall: 21,0 gegen 7,0 fuer eine Umformulierung."""
    einmal = calculate_score(
        _stelle("Betreuung unserer PLM-Landschaft im Maschinenbau."), dict(_KRIT))
    dreifach = calculate_score(
        _stelle("Betreuung unserer PLM-Landschaft. Product Lifecycle "
                "Management ist unser Kern, das PLM-System betreuen Sie "
                "eigenverantwortlich."), dict(_KRIT))
    assert einmal == dreifach, (
        f"Umformulierung bringt weiterhin Punkte: {einmal} gegen {dreifach}")


def test_1012_wiederholung_blaehte_noch_nie():
    """Zur Abgrenzung — als Test festgehalten, damit es niemand nachmisst.

    Jeder Begriff zaehlt ohnehin einmal. Der Fehler sass in der
    Kriterien-Liste, nicht im Anzeigentext.
    """
    k = {"keywords_muss": ["plm", "buchhaltung"], "gewichtung": {"muss": 7}}
    einmal = calculate_score(
        _stelle("Wir suchen jemanden fuer PLM und Buchhaltung."), k)
    zwanzig = calculate_score(_stelle("PLM " * 20 + "Buchhaltung " * 20), k)
    assert einmal == zwanzig == 14.0


def test_1012_verschiedene_faecher_zaehlen_weiterhin_getrennt():
    """Die Zusammenfassung darf keine Fachbreite kosten.

    Bewusst NICHT mit "plm"/"teamcenter" geprueft — mein erster Entwurf
    tat das und schlug fehl: PBPs eigene Synonym-Karte fuehrt die beiden
    als dasselbe, ein Text mit "PLM" gilt also schon als
    Teamcenter-Treffer. Der Test haette damit eine Fachbreite behauptet,
    die es im Matcher gar nicht gibt.
    """
    k = {"keywords_muss": ["plm", "buchhaltung"], "gewichtung": {"muss": 7}}
    eins = calculate_score(_stelle("Betreuung unserer PLM-Landschaft."), k)
    zwei = calculate_score(
        _stelle("PLM-Landschaft und Buchhaltung gehoeren dazu."), k)
    assert zwei > eins, "Zwei verschiedene Faecher muessen mehr wiegen als eines."


def test_1012_pbps_eigene_synonyme_sind_eine_anforderung():
    """Die dritte belegte Beziehung — und eine zweite Blaehungsquelle.

    `_SYNONYM_MAP` fuehrt `plm -> teamcenter`. Der Matcher zaehlt eine
    Anzeige mit "PLM" damit bereits als Teamcenter-Treffer: der zweite
    Punkt entsteht OHNE jeden zusaetzlichen Inhalt. Zwei MUSS-Begriffe,
    die PBP selbst als dasselbe behandelt, sind dasselbe.
    """
    assert anf.dieselbe_anforderung("plm", "teamcenter")
    assert anf.dieselbe_anforderung("projektleiter", "projektmanager")
    assert not anf.dieselbe_anforderung("plm", "buchhaltung")


def test_1012_die_synonym_karte_wird_wirklich_gelesen():
    """Guard gegen die stille Null.

    Mein erster Entwurf baute die Mengen mit `list | set` — ein
    TypeError, den ein weitgefasstes `except Exception` verschluckte.
    Die Regel war damit still abgeschaltet, und der Probelauf meldete
    nur "False". Ein Guard, der die GRUNDLAGE nachzaehlt, faengt genau
    das (#995).
    """
    assert len(anf._synonym_gruppen()) > 0,         "Die Synonym-Karte kommt nicht an — die dritte Regel ist tot."


# ══ Der Hoechstwert muss mitgruppieren (#999) ═══════════════════════

def test_1012_hoechstwert_gruppiert_mit():
    """Sonst waere er nicht mehr erreichbar.

    Der staerkste Test der Welle: gruppierte `score_maximum` nicht mit,
    ergaebe eine Anzeige, die ALLES trifft, nur noch einen Bruchteil des
    ausgewiesenen Hoechstwerts — und die in #999 gepruefte
    100-Prozent-Eigenschaft waere still gebrochen.
    """
    volltreffer = _stelle(
        "PLM, Product Lifecycle Management und das PLM-System sind unser "
        "taeglich Brot. Remote moeglich, Standort Hamburg.")
    befund = fit_analyse(volltreffer, dict(_KRIT))
    assert befund["total_score_max"] > 0
    anteil = befund["total_score"] / befund["total_score_max"]
    assert anteil <= 1.0 + 1e-9, (
        f"Score {befund['total_score']} ueber dem Hoechstwert "
        f"{befund['total_score_max']} — der Hoechstwert gruppiert nicht mit.")


def test_1012_beide_rechenwege_sind_einig():
    """#963 zum wievielten Mal auch immer.

    Liefe nur einer der beiden Wege ueber das Nadeloehr, haetten Liste
    und Fit-Analyse wieder verschiedene Zahlen fuer dieselbe Anzeige.
    """
    stelle = _stelle("PLM, Product Lifecycle Management und PLM-System.")
    aus_liste = calculate_score(dict(stelle), dict(_KRIT))
    aus_fit = fit_analyse(dict(stelle), dict(_KRIT))["fachscore"]
    assert abs(aus_liste - aus_fit) < 0.05, (
        f"Liste {aus_liste} gegen Fit-Analyse {aus_fit}")


# ══ AK 4: die Zusammenfassung wird benannt ══════════════════════════

def test_1012_fit_analyse_nennt_die_zusammengefassten_begriffe():
    """Eine stille Score-Aenderung ist in diesem Projekt zweimal teuer
    geworden (#987, #988)."""
    befund = fit_analyse(
        _stelle("PLM, Product Lifecycle Management und PLM-System."),
        dict(_KRIT))
    gruppen = befund["muss_zusammengefasst"]
    assert gruppen, "Die Zusammenfassung muss ausgewiesen werden."
    assert len(gruppen[0]["begriffe"]) == 3


def test_1012_ohne_zusammenfassung_bleibt_die_auskunft_leer():
    """Ein Hinweis, der immer kommt, wird nicht gelesen (#929)."""
    k = {"keywords_muss": ["plm", "buchhaltung"], "gewichtung": {"muss": 7}}
    befund = fit_analyse(_stelle("PLM-Landschaft und Buchhaltung."), k)
    assert befund["muss_zusammengefasst"] == []


def test_1012_die_suche_bleibt_unberuehrt():
    """Wichtige Abgrenzung, die auch im Hinweistext steht.

    Fuer die SUCHE zaehlen weiterhin alle Begriffe einzeln — jede
    Schreibweise ist ein eigener Portal-Suchbegriff. Zusammengefasst
    wird nur beim BEWERTEN. Stuende die Gruppierung auch im Suchpfad,
    verloere PBP Treffer.
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent").rglob("*.py")
    fundstellen = []
    for pfad in quelle:
        if pfad.name == "anforderungen.py":
            continue
        text = pfad.read_text(encoding="utf-8", errors="replace")
        for nr, zeile in enumerate(text.split("\n"), 1):
            if "zaehlbare_punkte(" in zeile.split("#")[0]:
                fundstellen.append(f"{pfad.name}:{nr}")
    # calculate_score, fit_analyse, score_maximum — je ein Aufruf plus
    # die drei Importe.
    dateien = {f.split(":")[0] for f in fundstellen}
    assert dateien == {"__init__.py"}, (
        f"Die Gruppierung darf nur im Scoring stehen: {sorted(dateien)}")
