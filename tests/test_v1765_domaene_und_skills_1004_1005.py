"""Tests fuer v1.7.65 — #1004 und #1005.

Beide Issues treffen dieselbe Frage aus zwei Richtungen: **was ist
eigentlich ein Fachgebiet?**

**#1004:** Die Wiedergaenger-Pruefung gruppiert ueber Firma plus
Titel-Token. Bei einem breit aufgestellten Softwarehersteller ist dessen
NAME als Domaenenmerkmal bedeutungslos — er deckt Personalwesen und
Produktdaten gleichermassen ab. Belegter Fall: drei aussortierte
Personalwesen-Rollen machten eine Produktdaten-Stelle zum
"Wiedergaenger". Die Warnung wiegt schwer (sie steht unter `risks`,
sinkt in der Sortierung ans Ende und sagt "wahrscheinlich erneut nicht
passend") — **und das ist die teurere Fehlerrichtung: eine uebersehene
unpassende Stelle kostet einen Klick, eine faelschlich abgewertete
passende eine Bewerbungschance.**

**#1005:** `skill_gap_analyse` zaehlte Wort-Tokens als Kompetenzen.
`system`, `systeme` und `systemen` standen als drei Eintraege in
derselben Auswertung, `qualifikation` und `informatik` als "fehlende
Skills" — daraus 36 Prozent Uebereinstimmung. Die Zahl sah aus wie eine
Kennzahl und trug keine Aussage.

Die Gegenrichtung ist bei beiden mitgeprueft: der Gruendungsfall #671
(Fach-Domaene traegt allein) und echte Fachbegriffe duerfen nicht
mitgerissen werden — die Lehre aus #966 und #991.
"""
import importlib
import logging
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


@pytest.fixture
def db(tmp_path):
    """QA-Isolation (HART): eigenes Temp-Verzeichnis, hart geprueft."""
    alt = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = str(tmp_path / "daten")
    from bewerbungs_assistent import database as _database
    importlib.reload(_database)
    datenbank = _database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.save_profile({"name": "Muster Person"})
    try:
        yield datenbank
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt


def _aussortiert(db, hash_, titel, firma, grund):
    db.save_jobs([{
        "hash": hash_, "title": titel, "company": firma,
        "location": "Hamburg", "score": 15,
        "url": f"https://example.org/{hash_}", "source": "manuell",
        "description": "Eine ausfuehrliche Stellenbeschreibung. " * 8,
    }])
    db.dismiss_job(hash_, grund)


# ══ #1004: der Herstellername ist kein Fachgebiet ═══════════════════

def test_1004_herstellername_allein_traegt_keinen_wiedergaenger(db):
    """Der belegte Fall.

    Drei Personalwesen-Rollen desselben Herstellers gegen eine
    Produktdaten-Stelle. Gemeinsam ist ausschliesslich der Name des
    Softwareherstellers — fachlich haben sie nichts miteinander zu tun.
    """
    from bewerbungs_assistent.services.wiedergaenger import (
        find_wiedergaenger_pattern,
    )
    for i, titel in enumerate([
        "SAP SuccessFactors Learning Consultant (m/w/d)",
        "SAP SuccessFactors Payroll Consultant",
        "Projektmanagement SAP SuccessFactors",
    ]):
        _aussortiert(db, f"hers{i}", titel, "Musterberatung GmbH",
                     "falsches_fachgebiet")

    muster = find_wiedergaenger_pattern(
        db, "Musterberatung GmbH",
        "SAP PLM Consultant Produktdaten und Aenderungsprozesse",
        schwellwert=2,
    )
    assert muster is None, (
        "Nur der Herstellername ist gemeinsam — das ist kein Fachgebiet.")


def test_1004_hersteller_plus_fach_traegt_weiterhin(db):
    """Die Gegenrichtung: mit echtem Fachbezug bleibt es ein Wiedergaenger.

    Sonst waere aus der Haertung ein Abschalten geworden (#966: beim
    Haerten beide Richtungen messen).
    """
    from bewerbungs_assistent.services.wiedergaenger import (
        find_wiedergaenger_pattern,
    )
    _aussortiert(db, "fach1", "SAP PLM Consultant", "Musterberatung GmbH",
                 "falsches_fachgebiet")
    _aussortiert(db, "fach2", "SAP PLM Projektleitung", "Musterberatung GmbH",
                 "falsches_fachgebiet")

    muster = find_wiedergaenger_pattern(
        db, "Musterberatung GmbH", "SAP PLM Architect (m/w/d)", schwellwert=2)
    assert muster is not None
    assert "plm" in muster["domain_tokens"]
    assert "sap" not in muster["domain_tokens"], \
        "Der Herstellername gehoert nicht in die ausgewiesene Domaene."


def test_1004_gruendungsfall_671_bleibt_unberuehrt(db):
    """Die Haertung darf ihren Gruendungsfall nicht mitnehmen (#991).

    #671: PLM Owner + PLM Manager machen einen PLM Architect zum
    Wiedergaenger — ueber EIN gemeinsames Token. Eine pauschale Regel
    "ein Token reicht nicht" haette genau das getoetet; deshalb trennt
    die Loesung Hersteller von Fachgebiet, statt zu zaehlen.
    """
    from bewerbungs_assistent.services.wiedergaenger import (
        find_wiedergaenger_pattern,
    )
    _aussortiert(db, "plm1", "PLM Product Owner (m/w/d)", "Konsumgueter GmbH",
                 "falsches_fachgebiet")
    _aussortiert(db, "plm2", "PLM Manager", "Konsumgueter GmbH",
                 "falsches_fachgebiet")

    muster = find_wiedergaenger_pattern(
        db, "Konsumgueter GmbH", "PLM Architect (m/w/d)", schwellwert=2)
    assert muster is not None
    assert "plm" in muster["domain_tokens"]


def test_1004_der_hinweis_nennt_einen_alttitel(db):
    """AK 2: ein Fehlalarm faellt nur auf, wenn dabeisteht, worauf er
    sich stuetzt.

    Die Alttitel standen unter `beispiele`; gelesen wird zuerst der
    Hinweis-Satz.
    """
    from bewerbungs_assistent.services.wiedergaenger import (
        find_wiedergaenger_pattern,
    )
    _aussortiert(db, "hin1", "PLM Product Owner (m/w/d)", "Konsumgueter GmbH",
                 "falsches_fachgebiet")
    _aussortiert(db, "hin2", "PLM Manager", "Konsumgueter GmbH",
                 "falsches_fachgebiet")

    muster = find_wiedergaenger_pattern(
        db, "Konsumgueter GmbH", "PLM Architect (m/w/d)", schwellwert=2)
    titel = [b["title"] for b in muster["beispiele"]]
    assert any(t and t in muster["hinweis"] for t in titel), (
        f"Kein Alttitel im Hinweis: {muster['hinweis']}")


def test_1004_das_aufnahmekriterium_steht_im_code():
    """Eine kuratierte Liste ohne Kriterium waechst beliebig.

    Der naechste Mensch muss entscheiden koennen, ob ein Name
    hineingehoert — sonst landet dort irgendwann ein Spezialanbieter,
    dessen Name sehr wohl ein Fachgebiet benennt.
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "services"
              / "wiedergaenger.py").read_text(encoding="utf-8")
    block = quelle[quelle.index("_BREITE_ANBIETER") - 1600:
                   quelle.index("_BREITE_ANBIETER")]
    assert "Aufnahmekriterium" in block
    assert "UNVERWANDTE" in block or "unverwandte" in block


# ══ #1005: Wort-Tokens sind keine Kompetenzen ═══════════════════════

def _werkzeuge(db):
    from bewerbungs_assistent.tools import analyse as analyse_tools

    gesammelt = {}

    class _Sammler:
        def tool(self, *a, **kw):
            def deko(fn):
                gesammelt[fn.__name__] = fn
                return fn
            return deko

        def prompt(self, *a, **kw):
            def deko(fn):
                return fn
            return deko

    analyse_tools.register(_Sammler(), db, logging.getLogger("test"))
    return gesammelt


_ANZEIGE = (
    "Zur Verstaerkung suchen wir einen Consultant. Aufgaben: Betreuung und "
    "Umsetzung von Projekten im Bereich PLM und Teamcenter. Analyse "
    "bestehender Systeme, Konzeption neuer Prozesse, Entwicklung von "
    "Loesungen an der Schnittstelle zur Fertigung. Sie betreuen Systeme "
    "und System-Prozesse. Qualifikation: abgeschlossenes Studium der "
    "Informatik. Kenntnisse in CAD und Aenderungsmanagement."
)


def _gap(db, beschreibung=_ANZEIGE):
    db.add_skill({"name": "PLM", "level": "experte"})
    db.add_skill({"name": "Teamcenter", "level": "fortgeschritten"})
    db.save_jobs([{
        "hash": "gap1", "title": "PLM Consultant (m/w/d)",
        "company": "Musterwerk GmbH", "location": "Hamburg", "score": 20,
        "url": "https://example.org/gap1", "source": "manuell",
        "description": beschreibung,
    }])
    voll = next(j["hash"] for j in db.get_active_jobs())
    return _werkzeuge(db)["skill_gap_analyse"](job_hash=voll.split(":")[-1])


def test_1005_keine_flexionsvarianten_als_getrennte_skills(db):
    """AK 1: `system`, `systeme`, `systemen` sind EIN Begriff."""
    befund = _gap(db)
    genannt = [s["skill"] for s in befund.get("vorhandene_skills", [])
               + befund.get("fehlende_skills", [])]
    from bewerbungs_assistent.services.stellen_skills import grundform
    schluessel = [grundform(s) for s in genannt]
    assert len(schluessel) == len(set(schluessel)), \
        f"Flexionsvarianten desselben Wortes: {genannt}"


def test_1005_keine_allerweltswoerter_in_der_auswertung(db):
    """AK 2: `qualifikation` als Luecke auszuweisen ist irrefuehrend.

    Es legt nahe, dem Menschen fehle etwas, das gar keine Kompetenz ist.
    """
    befund = _gap(db)
    genannt = {s["skill"].lower() for s in befund.get("vorhandene_skills", [])
               + befund.get("fehlende_skills", [])}
    floskeln = {"qualifikation", "informatik", "loesungen", "projekten",
                "umsetzung", "entwicklung", "konzeption", "schnittstelle",
                "systeme", "system", "systemen", "prozesse", "analyse",
                "management", "beratung", "betreuung"}
    assert not (genannt & floskeln), f"Floskeln in der Auswertung: {genannt & floskeln}"


def test_1005_die_echten_fachbegriffe_bleiben(db):
    """Die Gegenrichtung — sonst waere aus dem Aussieben ein Abschalten
    geworden."""
    befund = _gap(db)
    genannt = {s["skill"].lower() for s in befund.get("vorhandene_skills", [])
               + befund.get("fehlende_skills", [])}
    assert "plm" in genannt
    assert "teamcenter" in genannt


def test_1005_einzelbefund_wird_als_solcher_benannt(db):
    """AK 3: eine Zahl aus EINER Anzeige ist kein Trend."""
    befund = _gap(db)
    assert befund["analysierte_stellen"] == 1
    assert "Einzelbefund" in befund["grundlage"]


def test_1005_keine_quote_ohne_grundlage(db):
    """AK 4 — und der eigentliche Fund.

    `quote_belastbar` gibt es seit v1.7.30. Sie wurde IMPORTIERT und nie
    aufgerufen: eine Regel, die nicht laeuft, ist keine Regel (DoD 8c).
    Genau deshalb konnte aus wenigen Rauschbegriffen eine Prozentzahl
    entstehen, die wie eine Kennzahl aussieht.
    """
    befund = _gap(db)
    assert befund["match_prozent"] is None
    assert "Keine Quote" in befund["quote_hinweis"]


def test_1005_mit_genug_begriffen_gibt_es_wieder_eine_quote(db):
    """Und sie kommt zurueck, sobald die Grundlage traegt."""
    reich = (_ANZEIGE + " Erwartet werden ausserdem Windchill, CATIA, "
             "SolidWorks, Python und SQL.")
    befund = _gap(db, beschreibung=reich)
    assert befund["match_prozent"] is not None
    assert "quote_hinweis" not in befund


def test_1005_quote_belastbar_wird_wirklich_aufgerufen():
    """Guard gegen den Rueckfall: importiert ist nicht aufgerufen.

    Der Fund dieses Issues war nicht die fehlende Regel, sondern die
    vorhandene, die niemand rief.
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "tools"
              / "analyse.py").read_text(encoding="utf-8")
    assert "quote_belastbar(" in quelle.replace("quote_belastbar,", ""), \
        "quote_belastbar wird nur importiert, nicht aufgerufen."


def test_1005_sprachen_bleiben_eine_anforderung():
    """Bewusst NICHT ausgesiebt.

    Eine Sprachanforderung ist eine echte Anforderung; sie mitzutilgen
    waere die Gegenrichtung desselben Fehlers (#966).
    """
    from bewerbungs_assistent.services.stellen_skills import (
        _FLOSKEL_TAETIGKEIT,
    )
    assert "deutsch" not in _FLOSKEL_TAETIGKEIT
    assert "englisch" not in _FLOSKEL_TAETIGKEIT


def test_1005_grundform_ist_ein_schluessel_kein_wort():
    """Die Grenze steht im Docstring — und hier als Test.

    Angezeigt wird immer eine tatsaechlich vorkommende Form. Ein
    erfundenes Wort in einer Auswertung waere dieselbe Klasse Fehler wie
    ein erfundener Zeitpunkt (#987).
    """
    from bewerbungs_assistent.services.stellen_skills import grundform
    assert grundform("systemen") == grundform("systeme") == grundform("system")
    # Doppelkonsonant: vom eigenen Probelauf gefunden.
    assert grundform("prozess") == grundform("prozesse")
    # Mehrwortbegriffe bleiben unangetastet.
    assert grundform("change management") == "change management"
