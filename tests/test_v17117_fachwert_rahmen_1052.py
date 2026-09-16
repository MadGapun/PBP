"""Tests fuer #1052 Schritt 2 — Fachwert und Rahmendaumen.

Die Bausteine, bevor sie verdrahtet sind: der Fachwert als Prozent des
erreichbaren Fachmaximums, und der Rahmendaumen mit Richtung und Farbe
als getrennten Kanaelen.

Grundlage sind die verbindlichen Nutzerantworten vom 15.09.2026 im
Issue; sie gehen dem Issue-Text vor, wo sie ihm widersprechen. Vor allem:
**der Rahmen ist ein Indikator, kein Tor.** Er sortiert nichts um und
schliesst nichts aus — was mit seiner Auskunft geschieht, entscheidet
ein Filter, den der Mensch bedient.

Jede Haertung wird in BEIDE Richtungen geprueft (#966): neben dem Fall,
der "runter" ergeben MUSS, steht der, der es nicht darf.
"""
import pytest

from bewerbungs_assistent.job_scraper import fach_maximum, score_maximum
from bewerbungs_assistent.services import fachwert, rahmen


# --------------------------------------------------------------------
# Fachmaximum: nur MUSS und PLUS, gruppiert
# --------------------------------------------------------------------

def test_fachmaximum_zaehlt_nur_muss_und_plus():
    """Entfernung, Remote und Gehalt gehoeren nicht ins Fachmaximum.

    Das ist die ganze Trennung aus #1052: der Fachwert sagt etwas ueber
    die Anzeige, der Rahmen ueber die Lebensumstaende. `score_maximum`
    rechnet die Rahmen-Boni mit, `fach_maximum` nicht — sonst waere der
    Nenner groesser als das, was fachlich erreichbar ist, und 100
    Prozent nie erreichbar.
    """
    krit = {"keywords_muss": ["Stammdaten", "Migration"], "keywords_plus": []}
    assert fach_maximum(krit) < score_maximum(krit)


def test_fachmaximum_gruppiert_wie_die_rechnung():
    """Schreibvarianten derselben Anforderung zaehlen einmal (#1012).

    Ohne Gruppierung laege der Hoechstwert ueber allem, was eine Anzeige
    erreichen kann — und der Anteil koennte die 100 nie erreichen.
    """
    einzeln = fach_maximum({"keywords_muss": ["PLM"]})
    varianten = fach_maximum({"keywords_muss": ["PLM", "PLM-Rollout",
                                                "PLM Migration"]})
    assert einzeln == varianten


def test_fachmaximum_ohne_kriterien_ist_null_und_das_heisst_unbekannt():
    """0 heisst "nicht bestimmbar", nicht "nichts erreichbar" (#989).

    Deshalb prueft `anteil` genau darauf und liefert None statt einer
    Division — eine Zahl ohne Skala war der Fehler aus #999.
    """
    assert fach_maximum({}) == 0.0
    assert fach_maximum(None) == 0.0
    assert fachwert.anteil(5, fach_maximum({})) is None


# --------------------------------------------------------------------
# Fachwert als Anteil
# --------------------------------------------------------------------

@pytest.mark.parametrize("punkte,maximum,erwartet", [
    (5, 10, 50.0),
    (10, 10, 100.0),
    (0, 10, 0.0),
    # Mehr als alles gibt es nicht: die Abzuege koennen den Wert nicht
    # ueber das Erreichbare heben.
    (15, 10, 100.0),
    # Ein negativer Anteil waere keine Passungsaussage, sondern ein
    # Rechenrest aus den MINUS-Punkten.
    (-4, 10, 0.0),
])
def test_anteil_rechnet_und_deckelt(punkte, maximum, erwartet):
    assert fachwert.anteil(punkte, maximum) == erwartet


@pytest.mark.parametrize("punkte,maximum", [
    (5, 0), (5, None), (None, 10), ("viel", 10), (5, "keins"),
])
def test_anteil_ohne_skala_ist_none(punkte, maximum):
    """Ohne Hoechstwert keine Prozentzahl — und keine erfundene Null."""
    assert fachwert.anteil(punkte, maximum) is None


# --------------------------------------------------------------------
# Fachdaumen: Schwellen aus dem eigenen Bestand
# --------------------------------------------------------------------

def test_fachdaumen_richtungen_folgen_den_quartilen():
    schwellen = {"q25": 20.0, "q75": 60.0}
    assert fachwert.daumen(80, schwellen)["richtung"] == fachwert.HOCH
    assert fachwert.daumen(60, schwellen)["richtung"] == fachwert.HOCH
    assert fachwert.daumen(40, schwellen)["richtung"] == fachwert.MITTEL
    assert fachwert.daumen(20, schwellen)["richtung"] == fachwert.MITTEL
    assert fachwert.daumen(19, schwellen)["richtung"] == fachwert.RUNTER


def test_fachdaumen_bleibt_grau_wenn_die_grundlage_fehlt():
    """Keine Ersatzschwelle erfinden (Nutzerantwort Punkt 5).

    Unter 20 bewertbaren Bewerbungen traegt die Verteilung nichts. Ein
    Daumen, der trotzdem in eine Richtung zeigt, behauptet eine
    Grundlage, die es nicht gibt.
    """
    d = fachwert.daumen(80, {"grundlage_fehlt": "Nur 3 Bewerbungen"})
    assert d["farbe"] == fachwert.GRAU
    assert "3" in d["grund"]


def test_fachdaumen_farbe_ist_ein_eigener_kanal():
    """Richtung und Farbe sind getrennt — das ist der Kern der Loesung.

    Ein grauer Daumen nach oben heisst: sieht gut aus, aber ungeprueft.
    Die Richtung bleibt dieselbe, nur die Farbe sagt es.
    """
    schwellen = {"q25": 20.0, "q75": 60.0}
    belegt = fachwert.daumen(80, schwellen, belegt=True)
    grau = fachwert.daumen(80, schwellen, belegt=False)
    assert belegt["richtung"] == grau["richtung"] == fachwert.HOCH
    assert belegt["farbe"] == fachwert.BELEGT
    assert grau["farbe"] == fachwert.GRAU


def test_schwellen_verlangen_zwanzig_bewerbungen():
    """Die Zahl steht nicht im Test, sondern im Modul — sonst pruefte
    der Test seine eigene Kopie der Regel."""
    class _DB:
        def __init__(self, n):
            self._n = n

        def get_applications(self):
            return [{"job_hash": f"h{i}"} for i in range(self._n)]

        def get_job(self, h):
            return {"fachscore": 5.0}

    krit = {"keywords_muss": ["Stammdaten", "Migration", "Datenqualitaet"]}
    wenig = fachwert.schwellen(_DB(fachwert.MIN_BEWERBUNGEN - 1), krit)
    assert "grundlage_fehlt" in wenig
    genug = fachwert.schwellen(_DB(fachwert.MIN_BEWERBUNGEN), krit)
    assert "grundlage_fehlt" not in genug
    assert genug["q25"] is not None and genug["q75"] is not None


# --------------------------------------------------------------------
# Rahmendaumen
# --------------------------------------------------------------------

def _krit(**extra):
    k = {
        "max_entfernung": {"festanstellung": 30, "freelance": 200},
        "min_gehalt": 70000,
        "wunsch_gehalt": 85000,
        "stellentypen": ["festanstellung", "freelance"],
    }
    k.update(extra)
    return k


def _stelle(**extra):
    j = {
        "title": "Berater Stammdaten",
        "company": "Musterbetrieb GmbH",
        "location": "Hamburg",
        "employment_type": "festanstellung",
        "distance_km": 12.0,
        "salary_min": 90000,
        "salary_type": "jaehrlich",
        "salary_estimated": 0,
        "remote_level": "hybrid",
    }
    j.update(extra)
    return j


def test_alles_im_wunsch_ergibt_hoch_und_belegt():
    d = rahmen.daumen(_stelle(), _krit())
    assert d["richtung"] == rahmen.HOCH
    assert d["farbe"] == rahmen.BELEGT
    assert d["ausschluesse"] == []


def test_entfernung_ueber_der_grenze_ergibt_runter():
    d = rahmen.daumen(_stelle(distance_km=120.0), _krit())
    assert d["richtung"] == rahmen.RUNTER
    assert "entfernung" in d["ausschluesse"]


def test_volles_remote_hebt_die_entfernung_auf_auch_bei_bekannter_zahl():
    """Der Fall, den die Probe gefunden hat.

    `entfernungs_guete` beantwortet, wie belastbar die ZAHL ist, und
    meldet bei bekannter Entfernung sofort "belegt" — der Remote-Zweig
    kommt dann nie dran. Fuer den Rahmendaumen zaehlt die andere Frage:
    ob die Entfernung ueberhaupt gilt. Sonst waere eine vollstaendig
    remote ausgeschriebene Stelle mit gemessenen 120 km ein Ausschluss,
    obwohl niemand die 120 km faehrt.
    """
    d = rahmen.daumen(_stelle(distance_km=120.0, remote_level="remote"),
                      _krit())
    assert d["richtung"] == rahmen.HOCH
    assert d["ausschluesse"] == []


def test_hybrid_hebt_die_entfernung_nicht_auf():
    """Die Gegenrichtung (#966): ein Buerotag in der Woche ist ein
    Buerotag. Nur 100 Prozent remote loest die Grenze."""
    d = rahmen.daumen(_stelle(distance_km=120.0, remote_level="hybrid"),
                      _krit())
    assert d["richtung"] == rahmen.RUNTER


def test_ausserhalb_des_rechtsraums_bleibt_runter_auch_remote():
    """#996: eine US-Stelle ist nicht weit weg, sondern nicht bewerbbar.

    Der Rechtsraum wird VOR Remote geprueft — sonst wuerde "remote" ihn
    stillschweigend aufheben, und das war genau der Fehler aus #996.
    """
    d = rahmen.daumen(
        _stelle(location="Remote (United States)", distance_km=None,
                remote_level="remote"),
        _krit())
    assert d["richtung"] == rahmen.RUNTER
    assert "entfernung" in d["ausschluesse"]


def test_gehalt_unter_minimum_ergibt_runter_nur_wenn_belegt():
    """#827: aus einer Schaetzung folgt kein Ausschluss.

    Beide Richtungen in einem Fall: derselbe Betrag, einmal belegt und
    einmal geschaetzt.
    """
    belegt = rahmen.daumen(_stelle(salary_min=40000), _krit())
    assert belegt["richtung"] == rahmen.RUNTER
    assert "gehalt" in belegt["ausschluesse"]

    geschaetzt = rahmen.daumen(
        _stelle(salary_min=40000, salary_estimated=1), _krit())
    assert geschaetzt["ausschluesse"] == []
    assert geschaetzt["farbe"] == rahmen.GRAU


def test_gehalt_zwischen_minimum_und_wunsch_ergibt_mittel():
    d = rahmen.daumen(_stelle(salary_min=75000), _krit())
    assert d["richtung"] == rahmen.MITTEL
    assert d["ausschluesse"] == []


def test_vertragsform_ausserhalb_der_stellentypen_ergibt_runter():
    d = rahmen.daumen(_stelle(employment_type="zeitarbeit"), _krit())
    assert d["richtung"] == rahmen.RUNTER
    assert "vertragsform" in d["ausschluesse"]


def test_ohne_gewaehlte_stellentypen_schliesst_die_vertragsform_nichts_aus():
    """Die Gegenrichtung: wer nichts eingrenzt, bekommt keinen
    Ausschluss untergeschoben."""
    d = rahmen.daumen(_stelle(employment_type="zeitarbeit"),
                      _krit(stellentypen=[]))
    assert "vertragsform" not in d["ausschluesse"]


# --------------------------------------------------------------------
# Toleranz: eine MESStoleranz, kein Bewertungsband
# --------------------------------------------------------------------

def test_toleranz_hat_eine_vorgabe_und_ist_einstellbar():
    assert rahmen.toleranz_km({}) == rahmen.VORGABE_TOLERANZ_KM
    assert rahmen.toleranz_km({"entfernung_toleranz_km": 4}) == 4.0
    # Unsinn faellt auf die Vorgabe zurueck statt die Grenze aufzuheben.
    assert rahmen.toleranz_km({"entfernung_toleranz_km": -5}) == \
        rahmen.VORGABE_TOLERANZ_KM
    assert rahmen.toleranz_km({"entfernung_toleranz_km": "weit"}) == \
        rahmen.VORGABE_TOLERANZ_KM


def test_im_toleranzband_bleibt_die_richtung_und_die_farbe_wird_grau():
    """Nutzerantwort Punkt 6: das Band ist eine Aussage ueber die
    MESSUNG, nicht ueber die Stelle.

    34 km bei einer Grenze von 30 und einer Toleranz von 10: die
    Richtung kommt weiter aus dem Messwert (also runter), aber der
    Daumen behauptet keine Sicherheit, die die Messung nicht hergibt.
    """
    d = rahmen.daumen(_stelle(distance_km=34.0), _krit())
    assert d["richtung"] == rahmen.RUNTER
    assert d["farbe"] == rahmen.GRAU


def test_knapp_unter_der_grenze_ergibt_nie_hoch():
    """Nah an der Grenze heisst nicht "innerhalb der Wunschwerte"."""
    d = rahmen.daumen(_stelle(distance_km=26.0), _krit())
    assert d["richtung"] == rahmen.MITTEL
    assert d["farbe"] == rahmen.GRAU


def test_ausserhalb_des_bandes_ist_die_aussage_wieder_belegt():
    """Die Gegenrichtung: das Band faerbt nur sich selbst grau."""
    assert rahmen.daumen(_stelle(distance_km=12.0),
                         _krit())["farbe"] == rahmen.BELEGT
    assert rahmen.daumen(_stelle(distance_km=120.0),
                         _krit())["farbe"] == rahmen.BELEGT


# --------------------------------------------------------------------
# Zweitwohnsitz: der einzige Ausweg, und er steht leer
# --------------------------------------------------------------------

def _mit_zweitwohnsitz(**extra):
    return _krit(zweitwohnsitz_aufschlag_prozent=15,
                 zweitwohnsitz_kosten_pro_monat=700,
                 heimfahrten_pro_monat=4,
                 kosten_je_km=0.30, **extra)


def test_ohne_eintraege_gibt_es_keinen_ausweg():
    """Leer heisst: kein Ausweg — nicht "Ausweg zum Nulltarif" (#989).

    Keine Vorgabewerte im Code: die Zahlen aus dem Entwurfsgespraech
    sind die EINES Profils (v1.7.69).
    """
    assert rahmen.zweitwohnsitz_schwelle(_krit(), 120) is None
    d = rahmen.daumen(_stelle(distance_km=120.0, salary_min=200000), _krit())
    assert d["richtung"] == rahmen.RUNTER


def test_ein_fehlender_wert_genuegt_um_den_ausweg_zu_schliessen():
    """Eine halbe Formel rechnet nicht — sie raet."""
    for feld in rahmen.ZWEITWOHNSITZ_FELDER:
        krit = _mit_zweitwohnsitz()
        krit[feld] = None
        assert rahmen.zweitwohnsitz_schwelle(krit, 120) is None, feld


def test_die_heimfahrten_wachsen_mit_der_entfernung():
    """Nutzervorgabe: die Kosten gehoeren an die Entfernung gekoppelt,
    nicht als Konstante gesetzt."""
    nah = rahmen.zweitwohnsitz_schwelle(_mit_zweitwohnsitz(), 100)
    weit = rahmen.zweitwohnsitz_schwelle(_mit_zweitwohnsitz(), 400)
    assert weit > nah
    # Hin UND Rueckfahrt: 300 km mehr, 4 Fahrten im Monat, 12 Monate,
    # 0,30 EUR je km, mal zwei.
    assert round(weit - nah, 2) == round(4 * 12 * 2 * 300 * 0.30, 2)


def test_der_ausweg_greift_nur_bei_belegtem_gehalt():
    """Sonst entsteht aus einer erfundenen Zahl eine Umzugsempfehlung."""
    belegt = rahmen.daumen(
        _stelle(distance_km=120.0, salary_min=200000), _mit_zweitwohnsitz())
    assert belegt["richtung"] == rahmen.MITTEL

    geschaetzt = rahmen.daumen(
        _stelle(distance_km=120.0, salary_min=200000, salary_estimated=1),
        _mit_zweitwohnsitz())
    assert geschaetzt["richtung"] == rahmen.RUNTER


def test_der_ausweg_hebt_auf_mittel_und_nie_auf_hoch():
    """Ein Zweitwohnsitz bleibt ein Preis (Nutzerantwort Punkt 7)."""
    d = rahmen.daumen(_stelle(distance_km=120.0, salary_min=500000),
                      _mit_zweitwohnsitz())
    assert d["richtung"] == rahmen.MITTEL


def test_unter_der_schwelle_bleibt_es_runter():
    """Die Gegenrichtung: der Ausweg ist keine Generalamnestie fuer
    weite Stellen."""
    schwelle = rahmen.zweitwohnsitz_schwelle(_mit_zweitwohnsitz(), 120)
    d = rahmen.daumen(_stelle(distance_km=120.0, salary_min=schwelle - 1000),
                      _mit_zweitwohnsitz())
    assert d["richtung"] == rahmen.RUNTER


def test_der_aufschlag_darf_als_prozentzahl_oder_als_anteil_dastehen():
    """15 und 0.15 meinen dasselbe.

    Wer "15" eintraegt und 1500 Prozent bekommt, merkt es erst an einer
    Schwelle, die nie erreicht wird — und haelt den Ausweg fuer kaputt.
    """
    als_zahl = rahmen.zweitwohnsitz_schwelle(_mit_zweitwohnsitz(), 100)
    krit = _mit_zweitwohnsitz()
    krit["zweitwohnsitz_aufschlag_prozent"] = 0.15
    assert rahmen.zweitwohnsitz_schwelle(krit, 100) == als_zahl


# --------------------------------------------------------------------
# Freiberuflich
# --------------------------------------------------------------------

def test_freiberuflich_gilt_die_eigene_grenze_und_kein_zweitwohnsitz():
    """Nutzerantwort Punkt 8: dort entscheidet der Kunde ueber Reisekosten
    und Reisezeit, die bestehenden Regler bleiben.

    120 km sind fuer eine Festanstellung ein Ausschluss und fuer ein
    Projekt nicht — dieselbe Stelle, dieselbe Entfernung.
    """
    fest = rahmen.daumen(_stelle(distance_km=120.0), _krit())
    frei = rahmen.daumen(
        _stelle(distance_km=120.0, employment_type="freelance"), _krit())
    assert fest["richtung"] == rahmen.RUNTER
    assert frei["richtung"] == rahmen.HOCH
    assert frei["freiberuflich"] is True


def test_freiberuflich_hat_trotzdem_eine_obergrenze():
    """Die Gegenrichtung: "keine 30-km-Regel" heisst nicht "beliebig
    weit". Die bestehende Grenze aus den Reglern gilt."""
    d = rahmen.daumen(
        _stelle(distance_km=900.0, employment_type="freelance"), _krit())
    assert d["richtung"] == rahmen.RUNTER


def test_freiberuflich_bekommt_keinen_zweitwohnsitz_ausweg():
    d = rahmen.daumen(
        _stelle(distance_km=900.0, employment_type="freelance",
                salary_min=500000),
        _mit_zweitwohnsitz())
    assert d["richtung"] == rahmen.RUNTER
    assert "ausweg" not in d["teile"]["entfernung"]


# --------------------------------------------------------------------
# Der Daumen faellt kein Urteil ueber die Stelle
# --------------------------------------------------------------------

def test_der_rahmen_liefert_eine_auskunft_und_keine_entscheidung():
    """Indikator, kein Tor (Nutzerkorrektur 15.09.2026).

    Das Modul darf nichts aussortieren, nichts umsortieren und nichts
    ausblenden — es beschreibt nur. Wer hier spaeter eine Entscheidung
    einbaut, faellt hinter die Korrektur zurueck.
    """
    d = rahmen.daumen(_stelle(distance_km=900.0), _krit())
    assert set(d) == {"richtung", "farbe", "ausschluesse", "freiberuflich",
                      "teile", "grund"}
    assert "aussortieren" not in d and "sortierung" not in d
    # Der Grund steht da, damit der Mensch die Auskunft pruefen kann.
    assert d["grund"]


def test_jeder_teil_nennt_seinen_grund():
    """Eine Richtung ohne Begruendung ist eine Behauptung."""
    d = rahmen.daumen(_stelle(distance_km=120.0, salary_min=40000,
                              employment_type="zeitarbeit"), _krit())
    assert set(d["teile"]) == {"entfernung", "gehalt", "vertragsform"}
    for name, teil in d["teile"].items():
        assert teil["grund"], name
        assert teil["stufe"] in (rahmen.HOCH, rahmen.MITTEL, rahmen.RUNTER)
