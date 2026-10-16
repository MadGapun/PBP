"""#1234 - ein Wiedergaenger-k.o. aus Gruenden, die kein Urteil sind, und aus einem Rollenwort.

Gemeldet am 16.10.2026 beim Abgleich der aktiven Stellen: zwei Stellen derselben
Firma standen in `stellen_anzeigen` auf NICHT_EMPFOHLEN ("Firma wurde bereits 2x mit
Grund 'bewerbung_erstellt' aussortiert"), obwohl beide gelesen und als EMPFOHLEN bzw.
BEDINGT beurteilt waren. `bewerbung_erstellt` ist kein Aussortiergrund, sondern das
Gegenteil: die Stelle ging aus der Liste, weil sich der Mensch beworben hat. Die beiden
"Belege" waren zwei Fassungen derselben frueheren Bewerbung.

Drei Ursachen, drei Gegenproben:

1. `find_wiedergaenger_pattern` zaehlte JEDEN Grund. Jetzt zaehlen nur Urteile
   (`ablehnungsgruende.KEIN_URTEIL_GRUENDE`: bewerbung_erstellt, bereits_beworben,
   duplikat, veraltet_url).
2. Die Stellenliste machte aus JEDEM Muster ein NICHT_EMPFOHLEN, die Analyse nur aus
   einem fachlichen. Jetzt fragen beide `wiedergaenger.ist_fachlicher_ko`.
3. "head" stand nicht in `_TITLE_STOPS`: zwei Head-of-Stellen derselben Firma waren
   Wiedergaenger, nur weil beide "head" heissen.
"""
from __future__ import annotations

import logging

import pytest


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None, **_kwargs):
        def decorator(fn):
            self.tools[name or fn.__name__] = fn
            return fn
        return decorator


def _liste(db):
    from bewerbungs_assistent.tools.jobs import register
    mcp = FakeMCP()
    register(mcp, db, logging.getLogger("test"))
    return mcp.tools["stellen_anzeigen"]


def _anzeige(titel):
    return (f"{titel}. Aufgaben: Verantwortung fuer das Programm, Abstimmung mit den "
            "Fachbereichen, Steuerung externer Dienstleister, Berichte an die "
            "Geschaeftsleitung. Anforderungen: abgeschlossenes Studium, mehrjaehrige "
            "Berufserfahrung, sichere Kommunikation in Deutsch und Englisch.")


def _stelle(db, kurz, titel, firma, *, grund=None, score=30):
    """Legt eine Stelle an; mit `grund` (String oder Liste) wird sie aussortiert."""
    pid = db.get_active_profile_id() or ""
    voll = f"{pid}:{kurz}"
    db.save_jobs([{
        "hash": voll, "title": titel, "company": firma, "location": "Hamburg",
        "url": f"https://beispiel.example/{kurz}", "source": "manuell",
        "score": score, "description": _anzeige(titel),
    }])
    if grund is not None:
        assert db.dismiss_job(voll, grund)
    return voll


FIRMA = "Musterwerk Nord GmbH"


@pytest.fixture
def db(tmp_db):
    tmp_db.create_profile("Test", "test@example.com")
    return tmp_db


# -- 1. Was ein Urteil ist ------------------------------------------------


def test_1234_die_liste_der_nicht_urteile():
    from bewerbungs_assistent.services.ablehnungsgruende import (
        KEIN_URTEIL_GRUENDE, STANDARD_GRUENDE, SYSTEM_GRUENDE, ist_urteil)
    assert KEIN_URTEIL_GRUENDE == {
        "bewerbung_erstellt", "bereits_beworben", "duplikat", "veraltet_url"}
    # Jeder Eintrag ist ein BEKANNTER Wert: ein Tippfehler hier wuerde still nichts tun.
    assert KEIN_URTEIL_GRUENDE <= set(STANDARD_GRUENDE) | SYSTEM_GRUENDE
    for g in KEIN_URTEIL_GRUENDE:
        assert not ist_urteil(g)
        assert not ist_urteil(f"auto:{g}")
        assert not ist_urteil(f"auto:{g}:wiedergaenger")
        assert not ist_urteil(g.upper())


def test_1234_ein_urteil_bleibt_ein_urteil():
    from bewerbungs_assistent.services.ablehnungsgruende import (
        STANDARD_GRUENDE, ist_urteil)
    from bewerbungs_assistent.services.ablehnungsgruende import KEIN_URTEIL_GRUENDE
    for g in STANDARD_GRUENDE:
        assert ist_urteil(g) == (g not in KEIN_URTEIL_GRUENDE), g
    assert ist_urteil("auto:falsches_fachgebiet:wiedergaenger")
    assert ist_urteil("zeitarbeit")
    # Leer ist keine Aussage.
    assert not ist_urteil("")
    assert not ist_urteil(None)


# -- 2. Der gemeldete Fall ------------------------------------------------


@pytest.mark.parametrize("grund", [
    "bewerbung_erstellt", "bereits_beworben", "duplikat", "veraltet_url"])
def test_1234_zwei_nicht_urteile_machen_keinen_wiedergaenger(db, grund):
    """Der Fall aus der Meldung: zwei frueher aussortierte Stellen derselben Firma und
    Domaene, beide aus einem Grund, der kein Urteil ist."""
    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    _stelle(db, "a1", "PMO-Leitung Transformation", FIRMA, grund=grund)
    _stelle(db, "a2", "PMO-Leitung Transformation Programm", FIRMA, grund=grund)
    muster = find_wiedergaenger_pattern(
        db, FIRMA, "Data & Digital Transformation PMO", schwellwert=2)
    assert muster is None


def test_1234_zwei_urteile_bleiben_ein_wiedergaenger(db):
    """Gegenprobe: derselbe Aufbau mit einem echten Grund bleibt ein Muster (#671)."""
    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    _stelle(db, "b1", "PMO-Leitung Transformation", FIRMA, grund="falsches_fachgebiet")
    _stelle(db, "b2", "PMO-Leitung Transformation Programm", FIRMA,
            grund="falsches_fachgebiet")
    muster = find_wiedergaenger_pattern(
        db, FIRMA, "Data & Digital Transformation PMO", schwellwert=2)
    assert muster is not None
    assert muster["top_grund"] == "falsches_fachgebiet"
    assert muster["anzahl"] == 2


def test_1234_ein_urteil_und_eine_bewerbung_sind_nur_ein_beleg(db):
    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    _stelle(db, "c1", "PMO-Leitung Transformation", FIRMA, grund="falsches_fachgebiet")
    _stelle(db, "c2", "PMO-Leitung Transformation Programm", FIRMA,
            grund="bewerbung_erstellt")
    muster = find_wiedergaenger_pattern(
        db, FIRMA, "Data & Digital Transformation PMO", schwellwert=2)
    assert muster is None


def test_1234_die_bewerbung_taucht_in_den_gruenden_nicht_auf(db):
    """Mit zwei Urteilen UND einer Bewerbung zaehlen zwei; `alle_gruende` nennt die
    Bewerbung nicht."""
    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    _stelle(db, "d1", "PMO-Leitung Transformation", FIRMA, grund="falsches_fachgebiet")
    _stelle(db, "d2", "PMO-Leitung Transformation Programm", FIRMA,
            grund="falsches_fachgebiet")
    _stelle(db, "d3", "PMO Transformation Office", FIRMA, grund="bewerbung_erstellt")
    muster = find_wiedergaenger_pattern(
        db, FIRMA, "Data & Digital Transformation PMO", schwellwert=2)
    assert muster["anzahl"] == 2
    assert muster["alle_gruende"] == {"falsches_fachgebiet": 2}
    assert "bewerbung_erstellt" not in muster["hinweis"]


def test_1234_mehrere_gruende_an_einer_stelle_zaehlen_nur_das_urteil(db):
    """Eine Stelle mit [bewerbung_erstellt, falsches_fachgebiet] ist ein Beleg fuer das
    Fachgebiet und keiner fuer die Bewerbung."""
    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    _stelle(db, "e1", "PMO-Leitung Transformation", FIRMA,
            grund=["bewerbung_erstellt", "falsches_fachgebiet"])
    _stelle(db, "e2", "PMO-Leitung Transformation Programm", FIRMA,
            grund=["bewerbung_erstellt", "falsches_fachgebiet"])
    muster = find_wiedergaenger_pattern(
        db, FIRMA, "Data & Digital Transformation PMO", schwellwert=2)
    assert muster["alle_gruende"] == {"falsches_fachgebiet": 2}


def test_1234_die_automatik_sortiert_nach_einer_bewerbung_nichts_aus(db):
    """Stufe 1 der Automatik benutzt dieselbe Funktion: zwei Bewerbungen derselben Firma
    und Domaene duerfen eine neue Stelle nicht still aussortieren."""
    from bewerbungs_assistent.services import stellen_automatik
    _stelle(db, "f1", "PMO-Leitung Transformation", FIRMA, grund="bewerbung_erstellt")
    _stelle(db, "f2", "PMO-Leitung Transformation Programm", FIRMA,
            grund="bewerbung_erstellt")
    neu = {"hash": "neu1", "title": "Data & Digital Transformation PMO",
           "company": FIRMA, "location": "Hamburg"}
    e = stellen_automatik.entscheide(db, neu)
    assert e["aktion"] == "anlegen", e


def test_1234_firmen_historie_nennt_keine_bewerbung_als_aussortiert(db):
    from bewerbungs_assistent.services.wiedergaenger import firmen_historie
    _stelle(db, "g1", "Fruehere Stelle eins", FIRMA, grund="bewerbung_erstellt")
    _stelle(db, "g2", "Fruehere Stelle zwei", FIRMA, grund="duplikat")
    assert firmen_historie(db, FIRMA) is None
    _stelle(db, "g3", "Fruehere Stelle drei", FIRMA, grund="zeitarbeit")
    fh = firmen_historie(db, FIRMA)
    assert fh["aussortiert_anzahl"] == 1
    assert fh["gruende"] == {"zeitarbeit": 1}


# -- 3. Ein Rollenwort ist kein Fachgebiet --------------------------------


def test_1234_head_chief_director_sind_rollenwoerter():
    from bewerbungs_assistent.services.wiedergaenger import _domain_tokens
    assert _domain_tokens("Head of Guidelines, Processes & Tools") == {
        "guidelines", "processes", "tools"}
    assert _domain_tokens("Chief Information Officer") == {"information"}
    assert _domain_tokens("Director Quality Engineering") == {"quality", "engineering"}
    assert _domain_tokens("Direktor Vertrieb") == {"vertrieb"}


def test_1234_zwei_head_of_stellen_sind_kein_wiedergaenger(db):
    """Die einzige Ueberlappung war "head"."""
    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    _stelle(db, "h1", "Head of Repair Mechanical Workshop", FIRMA,
            grund="falsches_fachgebiet")
    _stelle(db, "h2", "Head of Repair Mechanical Workshop Services", FIRMA,
            grund="falsches_fachgebiet")
    muster = find_wiedergaenger_pattern(
        db, FIRMA, "Head of Guidelines, Processes & Tools", schwellwert=2)
    assert muster is None


def test_1234_ein_gemeinsames_fachwort_bleibt_ein_signal(db):
    """Gegenprobe: ein echtes Fachgebiet neben dem Rollenwort traegt weiter."""
    from bewerbungs_assistent.services.wiedergaenger import find_wiedergaenger_pattern
    _stelle(db, "i1", "Head of PLM", FIRMA, grund="falsches_fachgebiet")
    _stelle(db, "i2", "Director PLM Strategy", FIRMA, grund="falsches_fachgebiet")
    muster = find_wiedergaenger_pattern(
        db, FIRMA, "Head of PLM Transformation", schwellwert=2)
    assert muster is not None
    assert "plm" in muster["domain_tokens"]


# -- 4. Eine Frage, eine Funktion -----------------------------------------


def test_1234_wann_ist_ein_muster_ein_ko():
    from bewerbungs_assistent.services.wiedergaenger import (
        FACHLICHE_KO_GRUENDE, ist_fachlicher_ko)
    assert not ist_fachlicher_ko(None)
    assert not ist_fachlicher_ko({})
    assert not ist_fachlicher_ko({"anzahl": 1, "top_grund": "falsches_fachgebiet"})
    # Gehalt und Entfernung koennen sich aendern: kein k.o.
    assert not ist_fachlicher_ko({"anzahl": 5, "top_grund": "gehalt_zu_niedrig"})
    assert not ist_fachlicher_ko({"anzahl": 5, "top_grund": "zu_weit_entfernt"})
    assert not ist_fachlicher_ko({"anzahl": 5, "top_grund": "bewerbung_erstellt"})
    for g in FACHLICHE_KO_GRUENDE:
        assert ist_fachlicher_ko({"anzahl": 2, "top_grund": g}), g


def test_1234_analyse_und_liste_stellen_dieselbe_frage():
    """Beide gehen durch `ist_fachlicher_ko`; die Analyse hat keine eigene Liste mehr."""
    import inspect
    from bewerbungs_assistent.tools import jobs
    quelle = inspect.getsource(jobs)
    assert "_FACHLICHE_KO_GRUENDE" not in quelle
    assert quelle.count("ist_fachlicher_ko(") >= 2


@pytest.mark.parametrize("grund, kategorie", [
    ("falsches_fachgebiet", "NICHT_EMPFOHLEN"),
    ("gehalt_zu_niedrig", "NICHT_BEURTEILBAR"),
    ("bewerbung_erstellt", "NICHT_BEURTEILBAR"),
])
def test_1234_die_analyse_urteilt_wie_vorher(grund, kategorie):
    from bewerbungs_assistent.tools.jobs import _build_empfehlung
    fit = {"total_score": 10, "total_score_max": 30,
           "beschreibung_vorhanden": True, "muss_hits": ["a"], "missing_muss": [],
           "wiedergaenger": {"firma": "F", "anzahl": 2, "top_grund": grund}}
    befund = _build_empfehlung(fit, {"title": "T"}, profil_kompetenzen=5)
    assert befund["kategorie"] == kategorie


# -- 5. Die Stellenliste --------------------------------------------------


def _eintrag(res, kurz):
    return next(s for s in res["stellen"] if s["hash"].endswith(f":{kurz}")
                or s["hash"] == kurz or s["hash"].endswith(kurz))


def test_1234_liste_eine_bewerbung_macht_kein_ko(db):
    """Der gemeldete Fall in der Liste: keine Empfehlung, die Stelle bleibt bei
    `nur_empfohlen`."""
    _stelle(db, "j1", "PMO-Leitung Transformation", FIRMA, grund="bewerbung_erstellt")
    _stelle(db, "j2", "PMO-Leitung Transformation Programm", FIRMA,
            grund="bewerbung_erstellt")
    _stelle(db, "j3", "Data & Digital Transformation PMO", FIRMA)
    liste = _liste(db)
    res = liste()
    e = _eintrag(res, "j3")
    assert "empfehlung" not in e
    nur = liste(nur_empfohlen=True)
    assert any(s["hash"].endswith("j3") for s in nur["stellen"])


def test_1234_liste_ein_fachliches_ko_bleibt_ein_ko(db):
    _stelle(db, "k1", "PMO-Leitung Transformation", FIRMA, grund="falsches_fachgebiet")
    _stelle(db, "k2", "PMO-Leitung Transformation Programm", FIRMA,
            grund="falsches_fachgebiet")
    _stelle(db, "k3", "Data & Digital Transformation PMO", FIRMA, score=40)
    _stelle(db, "k4", "Sachbearbeitung Einkauf", "Musterbetrieb Süd GmbH", score=20)
    liste = _liste(db)
    res = liste()
    e = _eintrag(res, "k3")
    assert e["empfehlung"]["kategorie"] == "NICHT_EMPFOHLEN"
    assert "falsches_fachgebiet" in e["empfehlung"]["ko_grund"]
    # Trotz hoeherem Score unter der anderen Stelle (#827).
    ids = [s["hash"] for s in res["stellen"]]
    assert ids.index(_eintrag(res, "k4")["hash"]) < ids.index(e["hash"])
    nur = liste(nur_empfohlen=True)
    assert not any(s["hash"].endswith("k3") for s in nur["stellen"])


def test_1234_liste_ein_gehalts_muster_ist_ein_hinweis_kein_ko(db):
    _stelle(db, "l1", "PMO-Leitung Transformation", FIRMA, grund="gehalt_zu_niedrig")
    _stelle(db, "l2", "PMO-Leitung Transformation Programm", FIRMA,
            grund="gehalt_zu_niedrig")
    _stelle(db, "l3", "Data & Digital Transformation PMO", FIRMA)
    liste = _liste(db)
    e = _eintrag(liste(), "l3")
    assert "empfehlung" not in e
    assert "gehalt_zu_niedrig" in e["wiedergaenger_hinweis"]
    assert "kein k.o." in e["wiedergaenger_hinweis"]
    assert any(s["hash"].endswith("l3") for s in liste(nur_empfohlen=True)["stellen"])


def test_1234_liste_gelesene_analyse_und_ko_stehen_beide_da(db):
    """AK 3: liegt ein gelesenes Urteil vor, wird es neben dem k.o. gezeigt. Das k.o.
    schlaegt es weiter (#671), aber beides ist sichtbar."""
    _stelle(db, "m1", "PMO-Leitung Transformation", FIRMA, grund="falsches_fachgebiet")
    _stelle(db, "m2", "PMO-Leitung Transformation Programm", FIRMA,
            grund="falsches_fachgebiet")
    voll = _stelle(db, "m3", "Data & Digital Transformation PMO", FIRMA)
    assert db.set_job_analysis(voll, "EMPFOHLEN", "passt zu meinem Profil")
    e = _eintrag(_liste(db)(), "m3")
    assert e["analyse"]["urteil"] == "EMPFOHLEN"
    assert e["empfehlung"]["kategorie"] == "NICHT_EMPFOHLEN"
    assert e["empfehlung"]["gelesene_analyse"] == "EMPFOHLEN"
    assert "gelesene Analyse sagt EMPFOHLEN" in e["empfehlung"]["hinweis"]


def test_1234_liste_ohne_gelesene_analyse_kein_hinweis_darauf(db):
    _stelle(db, "n1", "PMO-Leitung Transformation", FIRMA, grund="falsches_fachgebiet")
    _stelle(db, "n2", "PMO-Leitung Transformation Programm", FIRMA,
            grund="falsches_fachgebiet")
    _stelle(db, "n3", "Data & Digital Transformation PMO", FIRMA)
    e = _eintrag(_liste(db)(), "n3")
    assert "gelesene_analyse" not in e["empfehlung"]
    assert "hinweis" not in e["empfehlung"]
