"""Tests fuer v1.7.24 — #963: ein Score, ein Rechenweg.

Gemeldet am 28.08.2026: dieselbe Stelle, zwei Tools, zwei Zahlen.
`scoring_vorschau` meldete 3,0, `fit_analyse` unmittelbar danach 20,8 —
und schrieb die 20 in die Datenbank. Welcher Wert in der Trefferliste
stand, hing davon ab, welches Tool zuletzt lief.

Die Ursachen, gemessen statt vermutet:

* `fit_analyse` kannte das MUSS-Tor aus #940 nicht. Eine Stelle ohne
  einen einzigen Pflichttreffer wurde allein aus PLUS-Keywords
  hochgerechnet — das erklaert den gemeldeten Sprung von 0 auf 20,8.
* `fit_analyse` kannte den Rahmen-Deckel aus #942 nicht (bis zu 6 Punkte
  auf 21 gemessen). Beides war MEIN Fehler: eine Regel in einen von zwei
  parallelen Rechenwegen einzubauen verschiebt die Divergenz nur.
* Der Remote-Zuschlag war um einen Punkt kleiner.

`fit_analyse` trug ausserdem die Kommentare "dieselbe Logik wie
calculate_score" gleich fuenfmal (#762, #778, #827, #910, #917) — jedes
Mal hatte ein Issue einen Zweig nachtraeglich wieder angeglichen. Ein
Kommentar haelt nichts zusammen. Dieser Test tut es.
"""
import pytest

from bewerbungs_assistent.job_scraper import calculate_score, fit_analyse

KRITERIEN = {
    "keywords_muss": ["PLM", "Teamcenter"],
    "keywords_plus": ["Senior", "Remote", "CAD", "Consultant"],
    "keywords_minus": ["Vertrieb", "Aussendienst"],
    "keywords_ausschluss": ["Werkstudent"],
    "gewichtung": {"muss": 7, "plus": 3, "minus": 6},
    "max_entfernung": {"festanstellung": 50, "freelance": 200},
}

# Bewusst breit gestreut: mit und ohne MUSS-Treffer, alle
# Arbeitsmodelle, nah und fern, mit und ohne Gehalt, Minus-Treffer,
# Ausschluss. Genau die Achsen, an denen die Wege auseinanderliefen.
FAELLE = [
    ("MUSS + viel Rahmen", dict(
        title="Senior PLM Consultant", company="Musterfirma GmbH",
        description="Teamcenter und PLM, Remote moeglich, CAD Kenntnisse.",
        remote_level="hybrid", distance_km=30)),
    ("MUSS + Minus + remote fern", dict(
        title="PLM Berater", company="Musterfirma GmbH",
        description="PLM Einfuehrung, Vertrieb gehoert dazu.",
        remote_level="remote", distance_km=250)),
    ("MUSS nuechtern", dict(
        title="Teamcenter Entwickler", company="Musterfirma GmbH",
        description="Teamcenter Customizing, Senior Rolle.", distance_km=92)),
    ("MUSS ohne Entfernung", dict(
        title="PLM Architekt", company="Musterfirma GmbH",
        description="PLM und Teamcenter, CAD Schnittstellen, Senior.",
        remote_level="hybrid")),
    ("KEIN MUSS, viel PLUS", dict(
        title="Senior CAD Consultant", company="Musterfirma GmbH",
        description="Senior Rolle mit CAD und Remote-Anteil, Consultant.",
        remote_level="remote", distance_km=10)),
    ("Ausschluss-Keyword", dict(
        title="Werkstudent PLM", company="Musterfirma GmbH",
        description="PLM Werkstudent gesucht, Teamcenter.")),
    ("voll remote weit weg", dict(
        title="Remote PLM", company="Musterfirma GmbH",
        description="PLM Rolle, komplett remote, Teamcenter.",
        remote_level="remote", distance_km=400)),
    ("Freelance weit", dict(
        title="PLM Interim", company="Musterfirma GmbH",
        description="Teamcenter Projekt, PLM Migration.",
        employment_type="freelance", distance_km=180)),
    ("mit Gehalt ueber Wunsch", dict(
        title="PLM Lead", company="Musterfirma GmbH",
        description="PLM und Teamcenter Fuehrung.",
        salary_min=95000, salary_max=120000, distance_km=40)),
    ("nur Titel, keine Beschreibung", dict(
        title="PLM Consultant", company="Musterfirma GmbH", description="")),
]


@pytest.mark.parametrize("name,job", FAELLE, ids=[f[0] for f in FAELLE])
def test_963_beide_rechenwege_stimmen_ueberein(name, job):
    """AK 1: es gibt genau einen Rechenweg fuer den Stellen-Score.

    Der Guard, der bisher fehlte. Wer kuenftig eine Scoring-Regel
    einbaut, muss sie in BEIDE Wege einbauen — oder dieser Test wird
    rot, statt dass die Divergenz Monate spaeter im Feld auffaellt.
    """
    a = calculate_score(dict(job), KRITERIEN)
    b = fit_analyse(dict(job), KRITERIEN)["total_score"]
    assert abs(float(a) - float(b)) < 0.05, (
        f"{name}: calculate_score={a}, fit_analyse={b}")


def test_963_ohne_muss_treffer_gibt_es_keinen_score():
    """Der gemeldete Fall: 0 in der Liste, 20,8 in der Analyse.

    PLUS-Keywords allein tragen keinen Score (#940). Das galt nur im
    Listen-Pfad — und der Analyse-Pfad schrieb seinen Wert anschliessend
    darueber.
    """
    job = dict(title="Senior CAD Consultant", company="Musterfirma GmbH",
               description="Senior Rolle mit CAD, Consultant, Remote.",
               remote_level="remote", distance_km=5)
    erg = fit_analyse(dict(job), KRITERIEN)
    assert erg["total_score"] == 0, erg["factors"]
    assert erg["empfehlung"]["kategorie"] == "NICHT_EMPFOHLEN"
    assert any("MUSS" in r for r in erg["risks"]), erg["risks"]


def test_963_fachscore_und_rahmenscore_werden_ausgewiesen():
    """AK 1: dieselben Teilbetraege, nicht nur dieselbe Summe.

    Sonst stimmt die Zahl zufaellig ueberein, waehrend die Erklaerung
    eine andere ist.
    """
    job = dict(title="Senior PLM Consultant", company="Musterfirma GmbH",
               description="Teamcenter und PLM, Remote, CAD.",
               remote_level="hybrid", distance_km=30)
    erg = fit_analyse(dict(job), KRITERIEN)
    assert "fachscore" in erg and "rahmenscore" in erg
    kopie = dict(job)
    calculate_score(kopie, KRITERIEN)
    assert abs(erg["fachscore"] - kopie["_fachscore"]) < 0.05, (
        erg["fachscore"], kopie["_fachscore"])
    assert abs(erg["rahmenscore"] - kopie["_rahmenscore"]) < 0.05, (
        erg["rahmenscore"], kopie["_rahmenscore"])


def test_963_rahmen_deckel_wirkt_auch_in_der_analyse():
    """Der groesste gemessene Einzelbeitrag zur Divergenz (6 von 21)."""
    job = dict(title="Senior PLM Consultant Remote CAD",
               company="Musterfirma GmbH",
               description="PLM. Senior, Remote, CAD, Consultant.",
               remote_level="remote", distance_km=5)
    erg = fit_analyse(dict(job), KRITERIEN)
    # Der Rahmen darf den Fachanteil nicht ueberholen.
    assert erg["rahmenscore"] <= erg["fachscore"], erg


def test_963_analyse_veraendert_die_stelle_nicht(tmp_db):
    """AK 3: ein Lesewerkzeug hat keine Nebenwirkung.

    Wer sich eine Stelle nur genauer ansieht, darf ihre Position in der
    Trefferliste nicht verschieben.
    """
    from bewerbungs_assistent.server import mcp  # noqa: F401  (Registry)
    tmp_db.save_jobs([{
        "hash": "s963", "title": "PLM Consultant",
        "company": "Musterfirma GmbH", "url": "https://example.com/963",
        "source": "manuell", "score": 5,
        "description": "PLM und Teamcenter, Senior Rolle, CAD.",
    }])
    vorher = tmp_db.get_job("s963")
    fit_analyse(dict(vorher), KRITERIEN)
    nachher = tmp_db.get_job("s963")
    assert nachher.get("score") == vorher.get("score")


# ══ Befund 2: skill_gap_analyse lieferte Stoppwoerter als Kompetenzen ══

ANZEIGE = """Wir suchen einen Senior Systems Engineer.

Ihre Aufgaben: Requirements Engineering fuer Medizinprodukte nach
IEC 62304 und ISO 13485. Sie arbeiten mit Polarion und DOORS, kennen
Systems Engineering und Engineering Change Management. Kein Muss, aber
von Vorteil sind Python und Matlab.

Ihre Benefits: 30 Tage Urlaub, Work-Life-Balance, frische Impulse,
Jobrad und Gleitzeit. Start ab Okt moeglich.

---
Mail von Kerstin, Recruiterin, am 28.08.2026
"""


def test_963_stoppwoerter_sind_keine_kompetenzen():
    """Der belegte Fall, woertlich.

    Gemeldet wurden unter anderem: sie, kein, aufgaben, urlaub, okt,
    start, balance, impulse.
    """
    from bewerbungs_assistent.services.stellen_skills import extrahiere_skills
    erg = [b.lower() for b in extrahiere_skills(ANZEIGE)]
    for muell in ("sie", "kein", "aufgaben", "urlaub", "okt", "start",
                  "balance", "impulse", "profil", "benefits", "ihre"):
        assert muell not in erg, f"'{muell}' ist keine Kompetenz: {erg}"


def test_963_echte_anforderungen_werden_gefunden():
    """Die Gegenprobe. Ein Filter, der nur wegnimmt, ist wertlos —
    genau diese Begriffe fehlten im gemeldeten Ergebnis."""
    from bewerbungs_assistent.services.stellen_skills import extrahiere_skills
    erg = [b.lower() for b in extrahiere_skills(ANZEIGE)]
    for pflicht in ("systems engineering", "requirements engineering",
                    "iec 62304", "iso 13485", "polarion", "doors",
                    "python", "matlab"):
        assert pflicht in erg, f"'{pflicht}' fehlt: {erg}"


def test_963_mehrwortbegriffe_bleiben_zusammen():
    """AK 5: 'requirements' allein ist keine Kompetenz."""
    from bewerbungs_assistent.services.stellen_skills import extrahiere_skills
    erg = [b.lower() for b in extrahiere_skills(ANZEIGE)]
    assert "requirements" not in erg
    assert "requirements engineering" in erg


def test_963_teilphrase_wird_nicht_doppelt_gezaehlt():
    """'engineering change management' macht 'change management' als
    eigenen Eintrag ueberfluessig — sonst blaeht sich der Nenner."""
    from bewerbungs_assistent.services.stellen_skills import extrahiere_skills
    erg = [b.lower() for b in extrahiere_skills(ANZEIGE)]
    assert "engineering change management" in erg
    assert "change management" not in erg


def test_963_notizteil_fliesst_nicht_ein():
    """AK 6: im belegten Fall stammte der Vorname genau von dort."""
    from bewerbungs_assistent.services.stellen_skills import extrahiere_skills
    erg = [b.lower() for b in extrahiere_skills(ANZEIGE)]
    assert not any("kerstin" in b for b in erg), erg
    assert not any("recruiterin" in b for b in erg), erg


def test_963_normen_nicht_in_praefix_und_zahl_zerlegt():
    from bewerbungs_assistent.services.stellen_skills import extrahiere_skills
    erg = [b.lower() for b in extrahiere_skills(ANZEIGE)]
    assert "iec" not in erg and "iso" not in erg, erg


def test_963_quote_entfaellt_ohne_grundlage():
    """AK 7: eine ehrliche Fehlanzeige statt einer gerechneten Zahl."""
    from bewerbungs_assistent.services.stellen_skills import (
        MINDEST_BEGRIFFE, quote_belastbar)
    assert quote_belastbar(MINDEST_BEGRIFFE) is True
    assert quote_belastbar(MINDEST_BEGRIFFE - 1) is False
    assert quote_belastbar(0) is False


def test_963_leere_beschreibung_gibt_keine_begriffe():
    from bewerbungs_assistent.services.stellen_skills import extrahiere_skills
    assert extrahiere_skills("") == []
    assert extrahiere_skills(None) == []
    assert extrahiere_skills("   \n  ") == []
