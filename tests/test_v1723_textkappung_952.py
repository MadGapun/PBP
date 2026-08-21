"""Tests fuer v1.7.23 — #952: Anzeigentext wurde bei 2000 Zeichen gekappt.

Bis v1.7.22 kappte JEDER Quellen-Adapter den Text, bevor er gespeichert
wurde — 38 Stellen in 26 Adaptern. Die Begrenzung sass in der Ablage
statt in der Ausgabe.

Stellenanzeigen sind fast durchgaengig gleich aufgebaut: Vorstellung,
Aufgaben, Anforderungen, Benefits. Der laengste und informationsaermste
Teil steht vorn — eine Kappung nach 2000 Zeichen trifft deshalb
bevorzugt genau das, was ueber die Passung entscheidet.

Der Fehler war stumm: `stellenbeschreibung_nachladen` meldete
`status: ok`, und eine nie angelegte Stelle taucht in keiner Statistik
auf.
"""
import pytest

from bewerbungs_assistent.job_scraper import calculate_score, fit_analyse
from bewerbungs_assistent.job_scraper.textgrenzen import (
    ALTE_KAPPUNG,
    AUSGABE_MAX,
    SPEICHER_MAX,
    fuer_ausgabe,
    fuer_speicher,
    ist_gekappt,
)

KRITERIEN = {
    "keywords_muss": ["PLM", "Product Lifecycle"],
    "keywords_plus": ["Senior", "Remote"],
    "keywords_minus": [],
    "keywords_ausschluss": ["Werkstudent"],
    "gewichtung": {"muss": 7, "plus": 3, "minus": 6},
}


def _lange_anzeige(schluss: str) -> str:
    """Eine realistisch aufgebaute Anzeige: Prosa vorn, Anforderungen hinten."""
    vorspann = ("Unser Unternehmen ist ein weltweit taetiger Anbieter von "
                "Loesungen fuer die Industrie. Wir beschaeftigen tausende "
                "Menschen und legen Wert auf Vielfalt, Nachhaltigkeit und "
                "eine offene Kultur. ")
    # ueber die alte Grenze hinaus auffuellen
    text = vorspann * 40
    assert len(text) > ALTE_KAPPUNG
    return text + "\n\nDeine Anforderungen:\n" + schluss


# ── Die Grenze gehoert in die Ausgabe, nicht in die Ablage ───────────

def test_952_ablage_behaelt_den_vollen_text():
    text = _lange_anzeige("Erfahrung mit PLM-Systemen erforderlich.")
    gespeichert = fuer_speicher(text)
    assert gespeichert == text
    assert len(gespeichert) > ALTE_KAPPUNG


def test_952_ausgabe_kuerzt_weiterhin():
    """Eine Begrenzung von Antworten ist berechtigt und bleibt."""
    text = _lange_anzeige("Egal.")
    assert len(fuer_ausgabe(text)) == AUSGABE_MAX


def test_952_notbremse_greift_erst_bei_entarteten_seiten():
    riesig = "x" * (SPEICHER_MAX + 5000)
    assert len(fuer_speicher(riesig)) == SPEICHER_MAX
    # Eine ausfuehrliche echte Anzeige liegt weit darunter.
    assert len(fuer_speicher("y" * 8000)) == 8000


# ── Regressionsfall aus dem Issue (AK 7) ─────────────────────────────

def test_952_muss_keyword_hinter_zeichen_2000_wird_gefunden():
    """Der teuerste Fall: die Stelle waere nie angelegt worden.

    Steht das einzige belastbare MUSS-Signal im Anforderungsteil, also
    hinter Zeichen 2000, fiel die Stelle ungesehen heraus — und das ist
    der einzige Schadensfall der Kette, der in keiner Statistik
    auftaucht.
    """
    voll = _lange_anzeige("Mehrjaehrige Erfahrung mit PLM-Systemen.")
    gekappt = voll[:ALTE_KAPPUNG]

    stelle_voll = {"title": "Consultant (m/w/d)", "description": voll,
                   "company": "Musterfirma GmbH"}
    stelle_gekappt = {"title": "Consultant (m/w/d)", "description": gekappt,
                      "company": "Musterfirma GmbH"}

    assert calculate_score(stelle_gekappt, KRITERIEN) == 0, (
        "Belegt den alten Schaden: ohne Anforderungsteil kein MUSS-Treffer")
    assert calculate_score(stelle_voll, KRITERIEN) > 0, (
        "Mit vollem Text wird die Stelle korrekt angelegt und bewertet")


def test_952_ausschluss_keyword_hinter_zeichen_2000_wirkt():
    """Auch die Gegenrichtung: Ausschluss-Begriffe stehen oft hinten."""
    voll = _lange_anzeige("Diese Stelle richtet sich an Werkstudent:innen. "
                          "Kenntnisse in PLM sind von Vorteil.")
    stelle = {"title": "Aushilfe PLM", "description": voll,
              "company": "Musterfirma GmbH"}
    assert calculate_score(stelle, KRITERIEN) == 0


# ── Kappung sichtbar machen (AK 3, AK 5) ─────────────────────────────

def test_952_gekappter_text_wird_erkannt():
    assert ist_gekappt("x" * ALTE_KAPPUNG)
    assert not ist_gekappt("x" * (ALTE_KAPPUNG - 1))
    assert not ist_gekappt("x" * (ALTE_KAPPUNG + 1))
    assert not ist_gekappt("")
    assert not ist_gekappt(None)


def test_952_qualitaetspruefung_kennt_die_kategorie():
    """Ohne diese Kategorie war die Tragweite nur per Direkt-SQL messbar."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "tools" / "jobs.py").read_text(encoding="utf-8")
    assert "beschreibung_gekappt" in quelle
    assert "beschreibung_gekappt_gesamt" in quelle


# ── Ehrlich bleiben statt falsch behaupten (AK 4) ────────────────────

def test_952_hochschulabschluss_ist_unbekannt_statt_false():
    """Regressionsfall aus dem Issue.

    Die Erkennung arbeitete korrekt — ihr fehlte nur der Satz. Ein
    falsches `false` ist schlechter als ein eingestandenes "weiss nicht".
    """
    # Formulierung bewusst aus der erkannten Mustersammlung — die
    # Erkennung selbst ist hier nicht Gegenstand des Tests, nur die
    # Frage, ob sie den Satz ueberhaupt zu sehen bekommt.
    voll = _lange_anzeige("Abgeschlossenes Studium der Informatik "
                          "vorausgesetzt. PLM-Kenntnisse noetig.")
    gekappt = voll[:ALTE_KAPPUNG]

    a_gekappt = fit_analyse({"title": "Consultant", "description": gekappt,
                             "company": "Musterfirma GmbH"}, KRITERIEN)
    assert a_gekappt["hochschulabschluss_gefordert"] == "unbekannt", a_gekappt
    assert a_gekappt["beschreibung_unvollstaendig"] is True

    a_voll = fit_analyse({"title": "Consultant", "description": voll,
                          "company": "Musterfirma GmbH"}, KRITERIEN)
    assert a_voll["hochschulabschluss_gefordert"] is True
    assert a_voll["beschreibung_unvollstaendig"] is False


def test_952_positive_erkennung_bleibt_auch_bei_kappung_erhalten():
    """Nur die NEGATIV-Aussage ist unsicher, nicht die positive.

    Steht die Anforderung noch im sichtbaren Teil, ist `True` belegt und
    darf nicht zu "unbekannt" verwaessert werden.
    """
    text = ("Abgeschlossenes Studium erforderlich. " + "Fuelltext. " * 200)
    gekappt = text[:ALTE_KAPPUNG]
    assert len(gekappt) == ALTE_KAPPUNG
    a = fit_analyse({"title": "Consultant", "description": gekappt,
                     "company": "Musterfirma GmbH"}, KRITERIEN)
    assert a["hochschulabschluss_gefordert"] is True


# ── Der Refetch darf nicht selbst kappen (AK 2) ──────────────────────

def test_952_refetch_kappt_nicht_mehr_per_default():
    """Die Kette aus #622 und #756 lief ins Leere: sie holte
    zuverlaessig immer wieder denselben halben Text."""
    import inspect

    from bewerbungs_assistent.job_scraper import fetch_description_from_detail
    sig = inspect.signature(fetch_description_from_detail)
    assert sig.parameters["max_chars"].default is None, (
        "Default 2000 war die Ursache — jetzt greift die Notbremse")
    quelle = inspect.getsource(fetch_description_from_detail)
    assert "SPEICHER_MAX" in quelle


def test_952_adapter_kappen_nicht_mehr_in_die_ablage():
    """Guard gegen Rueckfall: kein Adapter darf wieder auf 2000 kappen."""
    from pathlib import Path
    ordner = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "job_scraper")
    rueckfaelle = []
    for datei in ordner.glob("*.py"):
        inhalt = datei.read_text(encoding="utf-8")
        if "[:2000]" in inhalt or "substring(0, 2000)" in inhalt:
            rueckfaelle.append(datei.name)
    assert rueckfaelle == [], (
        f"Diese Adapter kappen wieder in die Ablage: {rueckfaelle}")
