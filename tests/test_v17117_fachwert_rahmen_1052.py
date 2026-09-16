"""Tests fuer #1052 Schritt 2 — Fachwert und Rahmendaumen.

Die Bausteine, bevor sie verdrahtet sind: der Fachwert als ROHE
Punktzahl (das Prozent-Kriterium hat der Nutzer am 16.09.2026
zurueckgezogen), der Rahmendaumen mit Richtung und Farbe als
getrennten Kanaelen, und das Signal aus dem eigenen Verhalten.

Grundlage sind die verbindlichen Nutzerantworten vom 15.09.2026 im
Issue; sie gehen dem Issue-Text vor, wo sie ihm widersprechen. Vor allem:
**der Rahmen ist ein Indikator, kein Tor.** Er sortiert nichts um und
schliesst nichts aus — was mit seiner Auskunft geschieht, entscheidet
ein Filter, den der Mensch bedient.

Jede Haertung wird in BEIDE Richtungen geprueft (#966): neben dem Fall,
der "runter" ergeben MUSS, steht der, der es nicht darf.
"""
import pytest

from bewerbungs_assistent.job_scraper import calculate_score, fach_maximum
from pathlib import Path

from bewerbungs_assistent.services import fachwert, neigung, rahmen


# --------------------------------------------------------------------
# Fachmaximum: nur MUSS und PLUS, gruppiert
# --------------------------------------------------------------------

def test_fachmaximum_zaehlt_nur_muss_und_plus():
    """Entfernung, Remote und Gehalt gehoeren nicht ins Fachmaximum.

    Das ist die ganze Trennung aus #1052: der Fachwert sagt etwas ueber
    die Anzeige, der Rahmen ueber die Lebensumstaende. Der Vorgaenger
    `score_maximum` rechnete die Rahmen-Boni mit — mit ihm als Bezug
    waere der Nenner groesser als das, was fachlich erreichbar ist.

    Geprueft wird deshalb an der Sache und nicht an zwei Funktionen: die
    Anzeige trifft beide Pflichtbegriffe, ist remote, nah und zahlt ueber
    Wunsch. Ihr Fachwert erreicht das Fachmaximum GENAU — die Rahmen-Boni
    heben ihn nicht darueber, obwohl sie alle anfallen.
    """
    krit = {"keywords_muss": ["Stammdaten", "Migration"], "keywords_plus": [],
            "min_gehalt": 60000, "max_entfernung": {"festanstellung": 15}}
    job = {"title": "Stammdaten Migration",
           "description": ("Stammdaten und Migration, 100% remote, "
                           "Gehalt 80.000 EUR/Jahr. ") * 8,
           "company": "Musterfirma GmbH", "distance_km": 3.0,
           "employment_type": "festanstellung", "remote_level": "remote",
           "salary_min": 80000, "salary_type": "jaehrlich",
           "location": "Hamburg"}
    assert calculate_score(job, krit) == fach_maximum(krit)
    assert job["_rahmenscore"] > 0


def test_fachmaximum_gruppiert_wie_die_rechnung():
    """Schreibvarianten derselben Anforderung zaehlen einmal (#1012).

    Ohne Gruppierung laege der Hoechstwert ueber allem, was eine Anzeige
    erreichen kann — und der Anteil koennte die 100 nie erreichen.
    """
    einzeln = fach_maximum({"keywords_muss": ["PLM"]})
    varianten = fach_maximum({"keywords_muss": ["PLM", "PLM-Rollout",
                                                "PLM Migration"]})
    assert einzeln == varianten


def test_fachmaximum_ohne_kriterien_ist_null():
    """0 heisst "nicht bestimmbar", nicht "nichts erreichbar" (#989).

    Der Wert steht im Detail als Zusatzangabe neben dem Fachwert ("17,5
    von 42 moeglichen"). Ohne Kriterien gibt es ihn nicht — dann bleibt
    die Zusatzangabe weg, statt eine 0 zu behaupten.
    """
    assert fach_maximum({}) == 0.0
    assert fach_maximum(None) == 0.0


# --------------------------------------------------------------------
# Fachdaumen: rohe Punkte, Schwellen aus dem eigenen Bestand
# --------------------------------------------------------------------

def test_fachdaumen_richtungen_folgen_den_beiden_schwellen():
    """Zwei Schwellen, zwei verschiedene Aussagen (Nutzerantwort 16.09.).

    Die Trennschwelle sagt, ab wo sich das Hinsehen ueberhaupt lohnt;
    das obere Viertel, ab wo es sich besonders lohnt.
    """
    sch = {"trennschwelle": 4.0, "oberes_viertel": 12.0}
    assert fachwert.daumen(30, sch)["richtung"] == fachwert.HOCH
    assert fachwert.daumen(12.0, sch)["richtung"] == fachwert.HOCH
    assert fachwert.daumen(11.9, sch)["richtung"] == fachwert.MITTEL
    assert fachwert.daumen(4.0, sch)["richtung"] == fachwert.MITTEL
    assert fachwert.daumen(3.9, sch)["richtung"] == fachwert.RUNTER


def test_negative_fachwerte_bleiben_negativ_und_unterscheidbar():
    """Nutzerwort 16.09.2026: "es gibt keine ober oder untergrenze".

    Die erste Fassung kappte bei 0. Damit saehen eine Stelle bei -8 und
    eine bei 0 gleich aus — genau die Sorte Zahl, die etwas anderes
    bedeutet als sie sagt, und der Grund, aus dem #1052 entstanden ist.
    Der Daumen muss sie deshalb beide lesen koennen, ohne zu stolpern.
    """
    sch = {"trennschwelle": 4.0, "oberes_viertel": 12.0}
    minus = fachwert.daumen(-8, sch)
    null = fachwert.daumen(0, sch)
    assert minus["richtung"] == null["richtung"] == fachwert.RUNTER
    # Und die Begruendung nennt die Zahl, die wirklich dasteht.
    assert "-8" in minus["grund"] and "-8" not in null["grund"]


def test_fachwert_wird_nirgends_in_prozent_umgerechnet():
    """Das Akzeptanzkriterium dazu ist zurueckgezogen.

    Ein Prozentwert setzt eine Obergrenze voraus, und die gibt es nicht:
    wieviele PLUS- und MINUS-Begriffe jemand pflegt und wie er sie
    gewichtet, ist individuell. Dieser Test haelt die Entscheidung fest,
    damit sie niemand "nur schnell" zurueckdreht.
    """
    assert not hasattr(fachwert, "anteil"), (
        "Die Prozent-Umrechnung ist zurueckgezogen — siehe Modulkopf.")


def test_fachdaumen_bleibt_grau_wenn_die_grundlage_fehlt():
    """Keine Ersatzschwelle erfinden (Nutzerantwort Punkt 5)."""
    d = fachwert.daumen(80, {"grundlage_fehlt": "Nur 3 Bewerbungen"})
    assert d["farbe"] == fachwert.GRAU
    assert "3" in d["grund"]


def test_fachdaumen_farbe_ist_ein_eigener_kanal():
    """Ein grauer Daumen nach oben heisst: sieht gut aus, ungeprueft."""
    sch = {"trennschwelle": 4.0, "oberes_viertel": 12.0}
    belegt = fachwert.daumen(30, sch, belegt=True)
    grau = fachwert.daumen(30, sch, belegt=False)
    assert belegt["richtung"] == grau["richtung"] == fachwert.HOCH
    assert belegt["farbe"] == fachwert.BELEGT
    assert grau["farbe"] == fachwert.GRAU


class _DB:
    """Ein Bestand aus gespeicherten Fachwerten."""

    def __init__(self, beworben, aussortiert=()):
        self._b = list(beworben)
        self._a = list(aussortiert)

    def get_applications(self):
        return [{"job_hash": f"h{i}"} for i in range(len(self._b))]

    def get_job(self, h):
        return {"score": self._b[int(str(h)[1:])]}

    def get_dismissed_jobs(self):
        return [{"score": w, "dismiss_reason": "falsches_fachgebiet"}
                for w in self._a]


def test_schwellen_verlangen_genug_bewerbungen():
    """Die Zahl steht im Modul, nicht im Test — sonst pruefte der Test
    seine eigene Kopie der Regel."""
    wenig = fachwert.schwellen(_DB(range(fachwert.MIN_BEWERBUNGEN - 1)))
    assert "grundlage_fehlt" in wenig
    genug = fachwert.schwellen(_DB(range(fachwert.MIN_BEWERBUNGEN)))
    assert "grundlage_fehlt" not in genug
    assert genug["trennschwelle"] is not None
    assert genug["oberes_viertel"] is not None


def test_die_trennschwelle_traegt_die_toleranz_aus_778():
    """Dieselbe Rechnung wie der Schwellenvorschlag im Backtest.

    Zwei Fassungen derselben Schwelle waeren das Muster aus #963 — und
    der Backtest schluege einen Wert vor, den der Daumen nicht benutzt.
    """
    werte = list(range(20, 60))
    sch = fachwert.schwellen(_DB(werte))
    # Dasselbe Quantil wie das Modul — ein eigenes im Test waere die
    # zweite Fassung derselben Rechnung, und der Test pruefte dann seine
    # eigene Kopie statt den Code.
    from bewerbungs_assistent.services.score_verteilung import _quantil
    q25 = _quantil(sorted(werte), 0.25)
    assert sch["trennschwelle"] == round(q25 * fachwert.TRENN_TOLERANZ, 1)


def test_die_schwelle_sagt_wieviele_aussortierte_darueber_liegen():
    """Eine Schwelle, die den halben Bestand durchlaesst, trennt nichts.

    Die Zahl entscheidet nichts — sie macht die Schwelle pruefbar.
    """
    sch = fachwert.schwellen(_DB(range(20, 40), aussortiert=[1, 2, 3, 99]))
    assert sch["aussortierte"] == 4
    assert sch["aussortierte_darueber"] == 1


def test_beworbene_stellen_zaehlen_nicht_als_aussortiert():
    """`bewerbung_erstellt` ist das Gegenteil eines Ablehnungsgrunds (#941).

    Solche Zeilen in die Negativ-Menge zu nehmen hiesse, die eigenen
    Bewerbungen gegen sich selbst zu stellen.
    """
    class _MitBewerbung(_DB):
        def get_dismissed_jobs(self):
            return [{"score": 99, "dismiss_reason": "auto:bewerbung_erstellt"},
                    {"score": 1, "dismiss_reason": "falsches_fachgebiet"}]

    sch = _MitBewerbung(range(20, 40)).get_dismissed_jobs()
    assert len(sch) == 2  # beide stehen im Bestand
    ergebnis = fachwert.schwellen(_MitBewerbung(range(20, 40)))
    assert ergebnis["aussortierte"] == 1, "die Bewerbung wurde mitgezaehlt"


# --------------------------------------------------------------------
# Das Signal aus dem eigenen Verhalten (#1052, Antwort auf Frage 3)
# --------------------------------------------------------------------

def _stelle_mit(titel, text=""):
    return {"title": titel, "description": text}


def _hintergrund(n=40):
    """Der Bestand, an dem gemessen wird, wie gewoehnlich ein Begriff ist.

    Ohne die beworbenen Stellen — genau das hat die Gegenprobe
    erzwungen: nimmt man sie mit hinein und sind sie in der Ueberzahl,
    gelten IHRE Begriffe als gewoehnlich und fallen aus dem Profil.
    """
    muster = [
        ("Sachbearbeitung Einkauf", "Bestellungen, Lieferanten, Rechnungen"),
        ("Pflegefachkraft Intensivstation", "Pflege, Station, Patienten"),
        ("Bilanzbuchhalter", "Abschluss, Buchungen, Debitoren"),
        ("Elektroniker Betriebstechnik", "Schaltschrank, Montage, Wartung"),
    ]
    return [_stelle_mit(t, d) for t, d in muster] * (n // len(muster) + 1)


def _neigungsprofil(anzahl=12, aussortiert=None, hintergrund=None):
    beworben = [
        _stelle_mit("Multiprojektleiter Transformation",
                    "Portfolio, Transformation, Steuerung, Stakeholder"),
        _stelle_mit("Transformation Manager",
                    "Transformation, Portfolio, Steuerung, Stakeholder"),
        _stelle_mit("Programmleiter Portfolio",
                    "Portfolio, Steuerung, Transformation, Stakeholder"),
    ] * (anzahl // 3 + 1)
    beworben = beworben[:anzahl]
    if aussortiert is None:
        aussortiert = [
            _stelle_mit("Pflegefachkraft Intensivstation",
                        "Pflege, Station, Patienten"),
            _stelle_mit("Bilanzbuchhalter", "Abschluss, Buchungen, Debitoren"),
        ] * 5
    if hintergrund is None:
        hintergrund = _hintergrund()
    return neigung.profil_bauen(beworben, aussortiert, hintergrund)


def test_das_signal_hebt_eine_stelle_die_die_wortlisten_uebersehen():
    """Der gemeldete Fall: ein Multiprojektleiter bei Fachwert 0,0 — und
    der Mensch hat sich beworben."""
    p = _neigungsprofil()
    s = neigung.signal(
        _stelle_mit("Multiprojektleiter",
                    "Portfolio und Transformation steuern, Stakeholder"),
        p, muss_gewicht=3.5)
    assert s["punkte"] > 0
    assert s["aehnliche"] > 0
    assert "beworben" in s["grund"]


def test_das_signal_hebt_nur_und_senkt_nie():
    """Nutzervorgabe, und sie ist der Kern: es soll nichts unterschlagen
    werden und nicht bevormunden.

    Eine Stelle, die KEINER frueheren aehnelt, bekommt 0 — keinen Abzug.
    Sonst drueckte das Verfahren jede ungewoehnliche Stelle weg, nur
    weil sie neu ist, und naegelte den Menschen auf sein bisheriges
    Berufsleben fest.
    """
    p = _neigungsprofil()
    fremd = neigung.signal(
        _stelle_mit("Pflegefachkraft", "Station, Patienten, Pflege"),
        p, muss_gewicht=3.5)
    assert fremd["punkte"] == 0.0
    assert fremd["punkte"] >= 0


def test_ohne_mindestbasis_bleibt_das_signal_aus():
    """Aus vier Faellen ein Muster zu lesen heisst, einen Einzelfall zu
    verkleiden."""
    p = _neigungsprofil(anzahl=neigung.MIN_BEWORBEN - 1)
    assert p.get("grundlage_fehlt")
    s = neigung.signal(_stelle_mit("Multiprojektleiter", "Portfolio"),
                       p, muss_gewicht=3.5)
    assert s["punkte"] == 0.0


def test_das_signal_nennt_seinen_beleg():
    """Nachvollziehbar: wer sieht, dass die Aehnlichkeit an einem
    unerwuenschten Wort haengt, kann gegensteuern."""
    p = _neigungsprofil()
    s = neigung.signal(
        _stelle_mit("Multiprojektleiter", "Portfolio, Transformation"),
        p, muss_gewicht=3.5)
    assert s["begriffe"], "ohne die gemeinsamen Begriffe ist es eine Behauptung"
    for begriff in s["begriffe"]:
        assert begriff in (p.get("begriffe") or [])


def test_das_signal_ueberstimmt_keinen_pflichttreffer():
    """Es macht sichtbar, es entscheidet nicht.

    Gedeckelt auf den Wert EINES Pflichttreffers — relativ und nicht
    absolut, aus demselben Grund wie in `muss_tor`: bei einer kurzen
    MUSS-Liste ist jeder absolute Wert daneben zu gross.
    """
    p = _neigungsprofil(anzahl=60)
    s = neigung.signal(
        _stelle_mit("Multiprojektleiter Transformation Portfolio",
                    "Portfolio, Transformation, Steuerung, Stakeholder"),
        p, muss_gewicht=3.5)
    assert s["punkte"] <= 3.5 * neigung.ANTEIL_EINES_TREFFERS


def test_ohne_muss_gewicht_gibt_es_kein_signal():
    """Ohne Pflichtbegriffe gibt es keinen Massstab, an dem sich das
    Signal relativieren liesse — dann bleibt es aus statt zu raten."""
    p = _neigungsprofil()
    s = neigung.signal(_stelle_mit("Multiprojektleiter", "Portfolio"),
                       p, muss_gewicht=0)
    assert s["punkte"] == 0.0


def test_ein_begriff_der_auch_in_den_absagen_steht_kommt_nicht_ins_profil():
    """Gesucht ist der UNTERSCHIED, nicht die Haeufigkeit.

    Steht ein Wort genauso oft in den aussortierten Stellen, sagt es
    nichts ueber die Neigung — es ist nur ein haeufiges Wort. Ohne diese
    Pruefung waere das Profil eine Liste der gewoehnlichsten Begriffe
    der eigenen Branche.
    """
    # "Portfolio" steht jetzt auch in den Absagen, und zwar oefter.
    absagen = [_stelle_mit("Sachbearbeitung Portfolio",
                           "Portfolio, Ablage, Vorgaenge")] * 40
    p = _neigungsprofil(aussortiert=absagen)
    assert "portfolio" not in (p.get("begriffe") or [])
    # Die Gegenrichtung: was NUR in den Bewerbungen steht, bleibt drin.
    assert "transformation" in (p.get("begriffe") or [])


def test_ein_einziger_gemeinsamer_begriff_traegt_kein_signal():
    """Ein Wort ist kein Muster.

    Dieselbe Lehre wie #1028, wo "fuer" als gemeinsames Fachgebiet
    galt: ein einzelnes geteiltes Wort genuegt nicht, sonst aehnelt
    jede Stelle jeder.
    """
    p = _neigungsprofil()
    eins = neigung.signal(
        _stelle_mit("Sachbearbeitung Transformation", "Ablage, Vorgaenge"),
        p, muss_gewicht=3.5)
    assert eins["punkte"] == 0.0, "ein gemeinsamer Begriff hat schon getragen"
    zwei = neigung.signal(
        _stelle_mit("Sachbearbeitung Transformation", "Portfolio, Ablage"),
        p, muss_gewicht=3.5)
    assert zwei["punkte"] > 0


def test_ein_begriff_der_fast_ueberall_steht_kommt_nicht_ins_profil():
    """Ein Wort in jeder zweiten Anzeige unterscheidet nichts.

    Der Filter misst das am HINTERGRUND ohne die beworbenen Stellen —
    sonst gelten die eigenen Begriffe als gewoehnlich.
    """
    # "Transformation" steht in fast jeder Stelle des Bestands.
    ueberall = [_stelle_mit("Sachbearbeitung", "Transformation, Ablage")] * 40
    p = _neigungsprofil(hintergrund=ueberall)
    assert "transformation" not in (p.get("begriffe") or [])
    assert "portfolio" in (p.get("begriffe") or [])


def test_ablehnungsgruende_und_detailurteile_gehen_nicht_ein():
    """Ausdruecklich ausgeschlossen (Nutzerantwort auf Frage 3).

    Die Ablehnungsgruende sind ueberwiegend Rahmenaussagen und wuerden
    im Fachwert wieder vermischen, was #1052 trennt. Die Detailurteile
    stehen bereits neben dem Score; sie in die Zahl zu ziehen hiesse,
    dasselbe zweimal zu zaehlen.
    """
    quelle = (Path(neigung.__file__).read_text(encoding="utf-8")
              .split('"""', 2)[2])
    # `dismiss_reason` steht im Modul und darf es: damit werden die
    # EIGENEN Bewerbungen aus der Negativ-Menge gehalten (#941). Der
    # erste Entwurf dieses Guards verbot es pauschal und schlug damit an
    # einer korrekten Stelle an — ein Guard, der bei richtigem Zustand
    # Alarm gibt, wird nach dem zweiten Mal ignoriert (#929).
    verboten = (
        # Ablehnungs-VOKABULAR als Signal: das waere die Vermischung,
        # die #1052 gerade aufloest.
        "falsches_fachgebiet", "zu_weit_entfernt", "gehalt_zu_niedrig",
        "ablehnungsgrund", "dismiss_counts",
        # Die Detailurteile stehen neben dem Score, nicht darin.
        "analyse_urteil", "get_job_analysis", "passung",
    )
    for wort in verboten:
        assert wort not in quelle, (
            f"{wort} darf nicht in die Rechnung eingehen")
    assert "bewerbung_erstellt" in quelle, (
        "Die eigenen Bewerbungen muessen aus der Negativ-Menge fallen.")


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


def test_die_stoppwoerter_stehen_an_genau_einer_stelle():
    """#963 an einer neuen Stelle.

    `keyword_vorschlaege` und das Neigungssignal beantworten dieselbe
    Frage — welche Woerter eines Anzeigentextes tragen Inhalt. Solange
    beide ihre eigene Liste haben, laufen sie beim ersten neuen
    Fuellwort auseinander, und niemand merkt es: die eine Seite haelt
    "Qualifikation" fuer einen Fachbegriff, die andere nicht.

    Geprueft wird nicht die Zahl der Fundstellen, sondern die BAUFORM —
    eine Aufzaehlung findet nur, was man beim Schreiben kannte
    (v1.7.100 MERKE 3).
    """
    from bewerbungs_assistent.tools import analyse
    quelle = Path(analyse.__file__).read_text(encoding="utf-8")
    assert "_stopwords = {" not in quelle, (
        "Das Werkzeug haelt wieder eine eigene Stoppwortliste — sie "
        "gehoert in services/neigung.py.")
    assert "from ..services.neigung import begriffe" in quelle
