"""#1070 — Feld, Niveau und Form statt eines Schluessels.

Der Melder hat drei Faelle genannt, in denen der erste Treffer gewinnt
und alles andere verlorengeht. Gemessen am 21.09.2026 vor der
Aenderung:

    Freiberuflicher Senior-Entwickler  -> freelance   (Tech-Signal weg)
    Pflegedienstleitung, 12 Jahre      -> executive   (Pflege-Signal weg)
    Dualer Student im Handwerk         -> student     (Handwerk-Signal weg)

Beim Nachmessen kamen vier Befunde dazu, die nicht im Bericht standen:

    Schulbegleiterin, 11 Jahre         -> executive   (`leiter` in `Begleiter`)
    Landwirt / Betriebsleiter          -> executive   (dasselbe)
    Sicherheitsmitarbeiter             -> mixed       (Feld fehlte)
    Rechtsanwalt                       -> mixed       (Feld fehlte)

Der Cluster steuert die Quellen-Empfehlung. Eine falsche Einordnung
kostet nicht ein Etikett, sondern die halbe Trefferliste.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import berufsfeld  # noqa: E402
from bewerbungs_assistent.services import profile_classifier as pc  # noqa: E402


def _profil(titel, start="2015-01-01", skills=(), education=()):
    return {
        "positions": [{"title": titel, "start_date": start}],
        "skills": [{"name": s} for s in skills],
        "education": list(education),
    }


# ===== Scheibe 1: ALLE Treffer, nicht nur der erste ======================

def test_1070_freiberuflicher_entwickler_behaelt_sein_fachfeld():
    """Der Kernfall des Melders: beides, nicht entweder oder."""
    ein = berufsfeld.einordnen(_profil(
        "Freelance Senior Software Developer", "2012-01-01",
        skills=("Python", "Kubernetes")))
    assert ein["feld"] == "it"
    assert "freiberuflich" in ein["formen"]
    assert ein["niveau"] == "spezialist"


def test_1070_er_bekommt_freelance_UND_tech_quellen():
    """Die Wirkung, um die es geht — nicht das Etikett."""
    out = pc.recommend_sources(_profil(
        "Freelance Senior Software Developer", "2012-01-01",
        skills=("Python",)))
    q = set(out["recommended"])
    assert "freelance_de" in q, "Freelance-Boerse fehlt"
    assert "himalayas" in q or "remotive" in q, "Tech-Quellen fehlen"
    # Und es ist nachvollziehbar, welche Angabe welche Quelle bringt.
    assert "freelance_de" in out["quellen_herkunft"]["form"]
    assert "himalayas" in out["quellen_herkunft"]["feld"]


def test_1070_pflegedienstleitung_behaelt_das_gesundheitsfeld():
    ein = berufsfeld.einordnen(_profil("Leitung Pflegedienst", "2012-01-01"))
    assert ein["feld"] == "gesundheit"
    assert ein["niveau"] == "experte"
    q = pc.recommend_sources(_profil("Leitung Pflegedienst", "2012-01-01"))
    assert "bundesagentur" in q["recommended"], "Gesundheits-Quellen fehlen"


def test_1070_dualer_student_behaelt_das_handwerk():
    ein = berufsfeld.einordnen(_profil(
        "Auszubildender Elektroniker", "2024-01-01",
        education=({"degree": "Bachelor Elektrotechnik",
                    "end_year": "2099"},)))
    assert ein["feld"] == "handwerk"
    assert ein["formen"], "Die Form muss erkannt sein"


def test_1070_mehrfachtreffer_werden_ausgewiesen():
    """Dass es weitere Treffer gab, stand vorher nirgends."""
    ein = berufsfeld.einordnen(_profil(
        "Freelance Senior Software Developer", "2012-01-01",
        skills=("Python",)))
    assert ein["mehrfach"] is False or len(ein["alle_felder"]) > 1
    mehr = berufsfeld.einordnen(_profil("Produktionsmitarbeiter Montage"))
    assert mehr["mehrfach"] is True
    assert [f["feld"] for f in mehr["alle_felder"]][:1] == ["produktion"]
    assert mehr["alle_felder"][0]["gewicht"] >= 1


def test_1070_das_staerkste_feld_gewinnt_nicht_das_erste():
    """Gewicht vor Reihenfolge: zwei Handels-Begriffe schlagen einen."""
    ein = berufsfeld.einordnen({
        "positions": [{"title": "Verkaeuferin im Einzelhandel",
                       "start_date": "2020-01-01"}],
        "skills": [{"name": "Kundenservice"}],
    })
    assert ein["feld"] == "handel"
    felder = [f["feld"] for f in ein["alle_felder"]]
    assert "dienstleistung" in felder, "Der schwaechere Treffer faellt nicht weg"


def test_1070_servicetechniker_im_aussendienst_ist_handwerk():
    """Gleichstand-Fall, der die Rangfolge korrigiert hat.

    Je ein Treffer fuer `aussendienst` (Handel), `servicetechniker`
    (Handwerk) und `techniker` (Ingenieurwesen) — die erste Fassung gab
    ihn dem Handel.
    """
    ein = berufsfeld.einordnen(_profil("Servicetechniker Aussendienst"))
    assert ein["feld"] == "handwerk"


# ===== Der Teilstring-Befund =============================================

def test_1070_schulbegleiterin_ist_keine_fuehrungskraft():
    """`leiter` matcht als Teilstring in `Begleiter` (#970-Klasse).

    Vor der Aenderung: Typ `executive`, Confidence 0,8, neun
    Konzern-Boards — fuer eine Schulbegleiterin.
    """
    out = pc.detect_profile_type(_profil("Schulbegleiterin", "2013-01-01"))
    assert out["type"] != "executive"
    assert out["niveau"] != "experte"
    assert out["feld"] == "bildung"


def test_1070_weitere_begleitberufe_ebenso():
    for titel in ("Alltagsbegleiterin", "Integrationsbegleiter",
                  "Reisebegleiter", "Studienbegleiter"):
        ein = berufsfeld.einordnen(_profil(titel, "2010-01-01"))
        assert ein["niveau"] != "experte", f"{titel} gilt als Fuehrungskraft"


def test_1070_echte_leitung_bleibt_fuehrungskraft():
    """Die Gegenrichtung — sonst haette die Haertung den Mechanismus
    abgeschaltet statt geschaerft (#966)."""
    for titel in ("Abteilungsleiter Einkauf", "Teamleitung Vertrieb",
                  "Geschaeftsfuehrer Operations"):
        ein = berufsfeld.einordnen(_profil(titel, "2008-01-01"))
        assert ein["niveau"] == "experte", f"{titel} verliert die Stufe"


# ===== Die fehlenden Berufsbereiche ======================================

def test_1070_neue_felder_landen_nicht_mehr_in_mixed():
    faelle = {
        "Sicherheitsmitarbeiter Werkschutz": "sicherheit",
        "Rechtsanwalt Arbeitsrecht": "recht",
        "Wissenschaftliche Mitarbeiterin Biologie": "wissenschaft",
        "Landwirt Ackerbau": "landwirtschaft",
        "Produktionsmitarbeiter Montage": "produktion",
        "Berufskraftfahrer CE": "logistik",
    }
    for titel, feld in faelle.items():
        ein = berufsfeld.einordnen(_profil(titel))
        assert ein["feld"] == feld, f"{titel} -> {ein['feld']}"
        assert not ein["unsicher"]


def test_1070_jedes_feld_nennt_seinen_berufsbereich():
    """Die Herkunft der Einteilung gehoert an das Feld, nicht in eine
    Fussnote — sonst waechst die Liste beliebig weiter (#1004/#1005)."""
    bereiche = set()
    for schluessel, eintrag in berufsfeld.FELDER.items():
        assert eintrag.get("bereich"), f"{schluessel} ohne Berufsbereich"
        assert eintrag.get("name"), f"{schluessel} ohne Namen"
        assert eintrag.get("begriffe"), f"{schluessel} ohne Begriffe"
        bereiche.add(eintrag["bereich"])
    # Die KldB 2010 kennt zehn Bereiche; PBP deckt heute neun davon ab
    # (das Militaer fehlt bewusst).
    assert len(bereiche) >= 8, bereiche


def test_1070_jedes_feld_hat_eine_quellenliste_und_einen_rang():
    for schluessel in berufsfeld.FELDER:
        assert schluessel in berufsfeld.FELD_QUELLEN, schluessel
        assert schluessel in berufsfeld.FELD_RANG, schluessel
    assert set(berufsfeld.FELD_RANG) == set(berufsfeld.FELDER)


# ===== Niveau: der Wert UND seine Grundlage ==============================

def test_1070_berufsjahre_allein_machen_keinen_spezialisten():
    """Der Deckel, den die Messung erzwungen hat.

    Ohne ihn wurde jedes Profil ab sieben Berufsjahren `spezialist`,
    und `NIVEAU_QUELLEN` legte Konzern-Boards auf die Empfehlung —
    gemessen bei Sicherheitsmitarbeiter, Berufskraftfahrer und
    Produktionsmitarbeiter. Das ist derselbe Schaden, den #1070
    meldet, nur durch eine andere Tuer.
    """
    for titel in ("Sicherheitsmitarbeiter Werkschutz",
                  "Berufskraftfahrer CE",
                  "Produktionsmitarbeiter Montage"):
        out = pc.recommend_sources(_profil(titel, "2005-01-01"))
        assert out["niveau"] == "fachkraft", titel
        assert out["niveau_beleg"] == "berufsjahre"
        assert not out["quellen_herkunft"]["niveau"], (
            f"{titel} bekommt Konzern-Quellen")
        assert "workday_dax" not in out["recommended"]


def test_1070_niveau_nennt_seine_grundlage():
    aus_titel = berufsfeld.einordnen(_profil("Senior Software Architect",
                                             "2010-01-01"))
    assert aus_titel["niveau"] == "spezialist"
    assert aus_titel["niveau_beleg"] == "titel"
    assert aus_titel["niveau_begriffe"], "Der Beleg nennt keinen Begriff"

    ohne = berufsfeld.einordnen(_profil("Mitarbeiterin", "2018-01-01"))
    assert ohne["niveau_beleg"] == "berufsjahre"


def test_1070_ohne_jede_grundlage_bleibt_das_niveau_unbekannt():
    """Eine Luecke wird benannt, nicht gefuellt (#989)."""
    ein = berufsfeld.einordnen({"positions": [], "skills": [],
                                "education": []})
    assert ein["niveau"] == "unbekannt"
    assert ein["niveau_beleg"] == "keiner"
    assert ein["form"] == "unbekannt"


def test_1070_zu_breite_spezialisten_begriffe_sind_raus():
    """Drei Begriffe aus dem ersten Entwurf trafen zu breit."""
    for titel in ("Servicetechniker Aussendienst", "Kundenberaterin Filiale"):
        ein = berufsfeld.einordnen(_profil(titel))
        assert ein["niveau"] == "fachkraft", titel


# ===== Form ==============================================================

def test_1070_form_kennt_mehrere_auspraegungen():
    ein = berufsfeld.einordnen(_profil("Werkstudent Softwareentwicklung",
                                       "2024-01-01"))
    assert "werkstudent" in ein["formen"]
    assert ein["feld"] == "it", "Das Feld faellt nicht weg"


def test_1070_form_schaltet_quellen_DAZU_statt_zu_ersetzen():
    ohne = pc.recommend_sources(_profil("Senior Software Developer",
                                        "2012-01-01", skills=("Python",)))
    mit = pc.recommend_sources(_profil("Freelance Senior Software Developer",
                                       "2012-01-01", skills=("Python",)))
    assert set(ohne["recommended"]) <= set(mit["recommended"]), (
        "Die Freiberuflichkeit hat Fachquellen VERDRAENGT")
    assert len(mit["recommended"]) > len(ohne["recommended"])


# ===== Konfidenz =========================================================

def test_1070_konfidenz_meint_den_schluessel_nicht_nur_das_feld():
    """Ein Geschaeftsfuehrer ohne erkennbares Fachfeld ist trotzdem
    sicher eine Fuehrungskraft."""
    gf = pc.detect_profile_type(_profil("Geschaeftsfuehrer Operations",
                                        "2010-01-01"))
    assert gf["type"] == "executive"
    assert gf["confidence"] >= 0.8

    stud = pc.detect_profile_type({
        "education": [{"degree": "Bachelor Informatik", "end_year": "2099"}],
        "positions": [], "skills": [],
    })
    assert stud["type"] == "student"
    assert stud["confidence"] >= 0.8


def test_1070_ohne_jeden_befund_bleibt_es_bei_030():
    out = pc.detect_profile_type({"positions": [], "skills": [],
                                  "education": []})
    assert out["type"] == "mixed"
    assert out["confidence"] == 0.3
    assert out["unsicher"] is True


def test_1070_der_hinweis_nennt_was_erkannt_wurde():
    """Sonst liest er sich wie ein Totalausfall, obwohl die Stufe
    feststeht."""
    gf = pc.detect_profile_type(_profil("Geschaeftsfuehrer Operations",
                                        "2010-01-01"))
    assert gf.get("unsicher") is True, "Das FELD ist unbekannt"
    assert "BERUFSFELD" in gf["hinweis"]
    assert "Erkannt wurde" in gf["hinweis"]


# ===== Abwaertskompatibilitaet ===========================================

def test_1070_der_alte_schluessel_bleibt_gueltig():
    """Elwosa-Linien, Tests und die Wiki-Seite zeigen seit #590 darauf."""
    for titel, erwartet in (
            ("Senior Backend Developer", "tech_senior"),
            ("Junior Frontend Engineer", "tech_junior"),
            ("Geselle Schreiner", "trade"),
            ("Senior PLM-Architekt", "engineering_senior"),
            ("Geschaeftsfuehrer Operations", "executive"),
    ):
        start = "2010-01-01" if "Junior" not in titel else "2025-01-01"
        out = pc.detect_profile_type(_profil(titel, start,
                                             skills=("Python", "PLM")))
        assert out["type"] == erwartet, f"{titel} -> {out['type']}"


def test_1070_jeder_abgeleitete_typ_hat_ein_label():
    from bewerbungs_assistent.services.profile_classifier import (
        PROFILE_TYPE_LABELS, _FELD_ZU_TYP,
    )
    for typ in set(_FELD_ZU_TYP.values()) | {
            "student", "freelance", "executive", "mixed", "tech_junior"}:
        assert typ in PROFILE_TYPE_LABELS, typ


def test_1070_kein_label_ohne_erreichbaren_typ():
    """Die Gegenrichtung: ein Label, das nie entsteht, ist eine
    Karteileiche (#993)."""
    from bewerbungs_assistent.services.profile_classifier import (
        PROFILE_TYPE_LABELS, _FELD_ZU_TYP,
    )
    erreichbar = set(_FELD_ZU_TYP.values()) | {
        "student", "freelance", "executive", "mixed", "tech_junior"}
    assert set(PROFILE_TYPE_LABELS) == erreichbar, (
        set(PROFILE_TYPE_LABELS) ^ erreichbar)


def test_1070_es_gibt_keine_zweite_quellen_tabelle_mehr():
    """`PROFILE_TYPE_CLUSTERS` wurde entfernt, nicht danebengestellt.

    Eine Liste je Schluessel NEBEN der Kombination waere die Bauform,
    die dieses Projekt vierzehnmal gekostet hat (#963).
    """
    import bewerbungs_assistent.services.profile_classifier as mod
    assert not hasattr(mod, "PROFILE_TYPE_CLUSTERS")
    quelltext = Path(mod.__file__).read_text(encoding="utf-8")
    assert "FELD_QUELLEN" not in quelltext.split('"""')[2], (
        "Die Quellenlisten gehoeren in berufsfeld.py")


def test_1070_die_begriffslisten_stehen_nur_an_einer_stelle():
    """Nach dem Umzug darf keine zweite Fassung zurueckbleiben."""
    import bewerbungs_assistent.services.profile_classifier as mod
    for name in ("_TECH_KEYWORDS", "_HEALTH_KEYWORDS", "_TRADE_KEYWORDS",
                 "_EXECUTIVE_KEYWORDS", "_FREELANCE_KEYWORDS"):
        assert not hasattr(mod, name), f"{name} steht noch doppelt da"


# ===== Nachtraege aus der Gegenprobe =====================================
#
# Vier Mechanismen blieben im ersten Durchgang stumm. Jeder bekommt hier
# den Fall, der ihn ISOLIERT — ein Test, der nie rot war, ist keine
# Zusicherung.

def test_1070_fuehrungstitel_ohne_zehn_jahre_ist_kein_experte():
    """Die Zehn-Jahres-Grenze stand seit #590 da und hatte keinen Fall.

    Eine frisch befoerderte Teamleiterin ist Spezialistin, nicht
    Expertin — und bekommt damit keine Konzern-Boards auf die
    Empfehlung, die eine Fuehrungskraft rechtfertigen wuerde.
    """
    jung = berufsfeld.einordnen(_profil("Teamleiterin Kundenservice",
                                        "2024-01-01"))
    assert jung["niveau"] != "experte"
    alt = berufsfeld.einordnen(_profil("Teamleiterin Kundenservice",
                                       "2008-01-01"))
    assert alt["niveau"] == "experte"


def test_1070_das_niveau_schaltet_konzern_quellen_DAZU():
    """Die Gegenrichtung zum Deckel-Test.

    Ohne diesen Fall belegt nichts, dass `NIVEAU_QUELLEN` ueberhaupt
    wirkt — der Deckel-Test prueft nur, dass es NICHT passiert.
    """
    out = pc.recommend_sources(_profil("Senior Software Architect",
                                       "2010-01-01", skills=("Python",)))
    assert out["niveau"] == "spezialist"
    assert out["quellen_herkunft"]["niveau"], "Keine Quelle aus der Stufe"
    assert "greenhouse" in out["recommended"]


def test_1070_ohne_feld_wird_BREIT_empfohlen_nicht_schmal():
    """Nicht eingeordnet heisst breit (#970/#989).

    Vor #970 bekam ausgerechnet der Fall, in dem PBP am wenigsten
    weiss, die KLEINSTE Quellenliste.
    """
    out = pc.recommend_sources(_profil("Mitarbeiterin", "2018-01-01"))
    assert out["feld"] is None and out["unsicher"] is True
    assert len(out["recommended"]) >= 6, out["recommended"]
    assert "bundesagentur" in out["recommended"]


def test_1070_kurze_kuerzel_brauchen_wortgrenzen():
    """Der Gruendungsfall von #970: "Kita" enthaelt "ki".

    Er darf beim Umzug der Listen nicht verlorengehen — das Kuerzel
    steht weiter in der IT-Liste, und ohne Wortgrenze traefe es jede
    Erzieherin.
    """
    assert berufsfeld.treffer("Erzieherin in einer Kita",
                              berufsfeld.FELDER["it"]["begriffe"]) == []
    ein = berufsfeld.einordnen(_profil("Erzieherin Kita Sonnenschein",
                                       "2016-01-01"))
    assert ein["feld"] == "bildung"
    assert "it" not in [f["feld"] for f in ein["alle_felder"]]
    # Und die Gegenrichtung: ein echter KI-Treffer bleibt einer.
    assert berufsfeld.treffer("Entwickler KI-Systeme",
                              berufsfeld.FELDER["it"]["begriffe"])


def test_1070_senioritaet_kommt_aus_den_BERUFSJAHREN_nicht_aus_dem_niveau():
    """Eigener Fehler beim Umbau, gefunden von der vollen Suite.

    Das `niveau` ist ohne Bezeichnung im Titel auf `fachkraft`
    gedeckelt — richtig, weil es die Komplexitaet der Taetigkeit meint.
    Der Junior/Senior-Schnitt der ALTEN Schluessel lief dagegen schon
    immer ueber die Berufsjahre. Beides zu vermischen machte aus einem
    Softwareentwickler mit zehn Jahren einen `tech_junior` und aus
    einem PLM-Berater sogar `trade`.
    """
    alt = pc.detect_profile_type({
        "positions": [{"title": "Softwareentwickler",
                       "description": "Backend", "start_date": "2016-01-01"}],
        "skills": [{"name": "Python"}], "education": [],
    })
    assert alt["type"] == "tech_senior"
    assert alt["niveau"] == "fachkraft", "Das Niveau bleibt konservativ"

    jung = pc.detect_profile_type(_profil("Softwareentwickler", "2025-01-01",
                                          skills=("Python",)))
    assert jung["type"] == "tech_junior"

    plm = pc.detect_profile_type({
        "positions": [{"title": "PLM Consultant",
                       "description": "Teamcenter",
                       "start_date": "2013-01-01"}],
        "skills": [{"name": "PLM"}], "education": [],
    })
    assert plm["type"] == "engineering_senior"


def test_1070_ein_einzelner_klarer_begriff_traegt_schon():
    """Die Konfidenz-Basis, ebenfalls von der vollen Suite gefunden.

    "Grafikdesignerin" ist EIN Treffer und trotzdem ein klares Signal —
    mit einer Basis von 0,60 waere die Einordnung unter die Schwelle
    gefallen, ab der die Empfehlungs-Karte ueberhaupt erscheint.
    """
    ein = pc.detect_profile_type(_profil("Grafikdesignerin", "2019-01-01"))
    assert ein["feld"] == "medien"
    assert ein["confidence"] >= 0.7
