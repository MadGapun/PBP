"""Tests fuer #951 — eine Stelle, mehrere Fundstellen.

Der Nutzer sortiert Duplikate seit Monaten von Hand aus; belegt sind
**44 Aussortierungen**, die keine fachliche Entscheidung waren. Das
Issue ist eine Neuauflage von #59/#67 (15.03.2026), die beide am
Anlagetag geschlossen wurden, ohne dass die Funktion entstand.

Der eigentliche Fund kam beim Messen: **dieselbe Frage wurde an zwei
Stellen mit verschiedenen Regeln beantwortet, und die schwaechere lief
im Suchlauf.** Ueber 2.491 Stellen nachgerechnet — 53 Paare gegen 116
sichere Zweitfunde.

Jedes der acht Akzeptanzkriterien steht hier einzeln (DoD 8a).
"""
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import stellen_dublette as sd  # noqa: E402
from bewerbungs_assistent.services import stellen_quellen as sq  # noqa: E402


@pytest.fixture
def db(tmp_path):
    """Isolierte Datenbank — BA_DATA_DIR, sonst trifft es die echte."""
    import importlib

    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _stelle(hash_, titel, firma="Halbleiterwerk Nord GmbH", url="", quelle="stepstone"):
    return {
        "hash": hash_,
        "title": titel,
        "company": firma,
        "url": url or f"https://{quelle}.example/stellen/{hash_}",
        "source": quelle,
        "description": "Ein Anzeigentext mit genug Inhalt fuer die Pruefung. " * 6,
        "score": 12,
    }


# ------------------------------------------- AK 3: URL ohne Tracking


def test_951_dieselbe_url_mit_anderen_kampagnenparametern(db):
    """AK 3: die Erkennung greift nach Tracking-Bereinigung.

    Zwei Portale verlinken dieselbe Anzeige regelmaessig mit
    unterschiedlichen Kampagnen-Parametern.
    """
    a = "https://portal.example/job/7788?utm_source=news&utm_medium=mail"
    b = "https://portal.example/job/7788?trk=abc&refId=xyz"
    assert sd.url_schluessel(a) == sd.url_schluessel(b)


def test_951_echte_parameter_bleiben_stehen():
    """Die Bereinigung darf die Anzeige nicht verwechselbar machen.

    `?id=7` und `?id=8` sind verschiedene Stellen. Wuerde die
    Bereinigung alle Parameter entfernen, waeren sie identisch — das
    ist die Gegenrichtung des Fehlers (#966).
    """
    a = sd.url_schluessel("https://x.example/job?id=7&utm_campaign=z")
    b = sd.url_schluessel("https://x.example/job?id=8&utm_campaign=z")
    assert a != b
    assert "id=7" in a


# ---------------------------- AK 4: Titel-Normalisierung, beide Richtungen


@pytest.mark.parametrize("a,b", [
    ("Senior Consultant (m/w/d)", "Senior Consultant"),
    ("PLM Consultant (all genders)", "PLM Consultant"),
    ("Sr. Solution Architect", "Senior Solution Architect"),
    ("IT Consultant R&D und Product Lifecycle",
     "IT Consultant R&D and Product Lifecycle"),
    ("Prozess–Manager (m/w/d)", "Prozess-Manager"),
    ("Teamleiter (gn)", "Teamleiter"),
])
def test_951_schreibvarianten_meinen_dieselbe_stelle(a, b):
    """AK 4: die Regressionsfaelle aus dem Issue, einzeln."""
    assert sd.titel_schluessel(a) == sd.titel_schluessel(b), (
        f"{a!r} und {b!r} werden nicht zusammengefuehrt.")


@pytest.mark.parametrize("a,b", [
    ("Senior Consultant PLM", "Junior Consultant PLM"),
    ("PLM Consultant", "PDM Consultant"),
    ("Teamleiter Konstruktion", "Teamleiter Fertigung"),
    ("Entwickler Frontend", "Entwickler Backend"),
])
def test_951_verschiedene_stellen_bleiben_verschieden(a, b):
    """Die Gegenrichtung — beim Haerten IMMER beide messen (#966).

    Eine zu waschende Normalisierung zoege verschiedene Stellen
    zusammen, und das ist der teurere Fehler: dabei verschwindet
    Information.
    """
    assert sd.titel_schluessel(a) != sd.titel_schluessel(b)


# --------------------------------- AK 1/2: Quellenliste statt Neueintrag


def test_951_der_zweitfund_landet_am_original(db):
    """AK 1 + 2: kein neuer aktiver Eintrag, sondern eine Quellenzeile."""
    db.save_jobs([_stelle("q951a", "PLM Consultant (m/w/d)", quelle="stepstone")])
    voll = db.resolve_job_hash("q951a")

    # Dieselbe Anzeige, anderes Portal, Titelvariante.
    db.save_jobs([_stelle("q951b", "PLM Consultant", quelle="xing")])

    quellen = [e["source"] for e in sq.lesen(db, voll)]
    assert "stepstone" in quellen and "xing" in quellen, (
        f"Der Zweitfund haengt nicht am Original: {quellen}")

    # Und es gibt genau EINE aktive Stelle.
    aktive = db.connect().execute(
        "SELECT COUNT(*) FROM jobs WHERE is_active=1").fetchone()[0]
    assert aktive == 1


def test_951_die_uebersicht_schweigt_bei_einer_quelle(db):
    """Eine Liste mit einem Eintrag ist keine Information.

    Sie waere die Wiederholung des `source`-Feldes — und ein Hinweis,
    der immer dasteht, wird nach dem zweiten Mal ignoriert (#929).
    """
    db.save_jobs([_stelle("q951c", "Einzelstelle Quintus")])
    job = db.get_job(db.resolve_job_hash("q951c"))
    assert sq.uebersicht(db, job) is None


def test_951_die_uebersicht_nennt_die_portale(db):
    """AK 6: die Quellenliste steht zum Anzeigen bereit."""
    db.save_jobs([_stelle("q951d", "Doppelrolle Quintus", quelle="stepstone")])
    voll = db.resolve_job_hash("q951d")
    db.save_jobs([_stelle("q951e", "Doppelrolle Quintus", quelle="indeed")])

    job = db.get_job(voll)
    uebersicht = sq.uebersicht(db, job)
    assert uebersicht is not None
    assert set(uebersicht["quellen"]) >= {"stepstone", "indeed"}
    assert uebersicht["anzahl"] >= 2
    assert "Portalen" in uebersicht["text"]


# --------------------------------------------- AK 8: kein Score-Bonus


def test_951_ein_mehrfachfund_veraendert_den_score_nicht(db):
    """AK 8: Streuung ist nicht Passung.

    #59 hatte einen Score-Bonus je Duplikat vorgeschlagen. Eine breit
    gestreute Stelle ist aber oft eine schwer besetzbare, nicht eine
    bessere — der Bonus wuerde Streuung mit Passung verwechseln.
    """
    db.save_jobs([_stelle("q951f", "Breitstelle Quintus", quelle="stepstone")])
    voll = db.resolve_job_hash("q951f")
    vorher = db.get_job(voll)["score"]

    for quelle in ("indeed", "xing", "linkedin"):
        db.save_jobs([_stelle(f"q951f{quelle}", "Breitstelle Quintus",
                              quelle=quelle)])

    job = db.get_job(voll)
    assert job["score"] == vorher, "Der Mehrfachfund hat den Score veraendert."
    assert sq.uebersicht(db, job)["wirkt_auf_score"] is False


# ----------------------------------- AK 5: unsicher heisst MARKIEREN


def test_951_aehnlichkeit_fuehrt_nicht_zusammen(db):
    """AK 5: der unsichere Fall wird markiert, nicht verschmolzen.

    Nutzervorgabe: "zwei getrennte Eintraege sind aergerlich, eine
    faelschlich verschmolzene Stelle ist schlimmer, weil dabei
    Information verschwindet."
    """
    treffer = sd.finde(
        {"title": "Solution-Architect fuer PLM- und IoT-Softwareloesungen",
         "company": "Halbleiterwerk Nord GmbH", "url": "https://a.example/1"},
        [{"hash": "x",
          "title": "Solution-Architect fuer PLM- und IoT-Loesungen",
          "company": "Halbleiterwerk Nord GmbH", "url": "https://b.example/2"}],
    )
    assert treffer is not None
    assert treffer["sicherheit"] == sd.VERDACHT
    assert "pruefen" in treffer["text"].lower()


def test_951_die_aehnlichkeitsschwelle_aus_670_bleibt_stehen():
    """Ein Alt-Entscheid, der NICHT zurueckgedreht wird.

    Bei verschiedenen URLs verlangt `find_duplicate_job` eine
    Titel-Aehnlichkeit von 0.85 statt 0.5. Das ist kein Versehen,
    sondern die Lehre aus #670: ein einzelnes geteiltes Fachwort machte
    verschiedene Stellen derselben Firma unsichtbar ("PLM Project
    Manager" gegen "PLM Product Owner").

    Mein erster Test hier erwartete, dass "(Senior) Solution Architect
    Cloud" und "Solution Architect" zusammenfinden — die Aehnlichkeit
    liegt bei 0,67 und damit bewusst darunter. Der Alt-Entscheid ist die
    Spezifikation, nicht der Fehler (v1.7.31 MERKE 2).
    """
    assert sd.finde(
        {"title": "Solution Architect", "company": "Halbleiterwerk Nord GmbH",
         "url": "https://a.example/1"},
        [{"hash": "x", "title": "(Senior) Solution Architect Cloud",
          "company": "Halbleiterwerk Nord GmbH", "url": "https://b.example/2"}],
    ) is None


def test_951_sicher_und_verdacht_sind_zwei_verschiedene_dinge():
    """Nachgerechnet ist etwas anderes als vermutet.

    Wuerden beide gleich behandelt, entschiede eine Aehnlichkeit
    darueber, ob eine Stelle sichtbar bleibt.
    """
    gleich = sd.finde(
        {"title": "Consultant (m/w/d)", "company": "Halbleiterwerk Nord GmbH",
         "url": "https://a.example/1"},
        [{"hash": "y", "title": "Consultant",
          "company": "Halbleiterwerk Nord GmbH", "url": "https://b.example/2"}],
    )
    assert gleich["sicherheit"] == sd.SICHER
    assert gleich["grund"] == "titel_firma"


# --------------------------------------- AK 7: Diagnoselauf ohne Schreiben


def test_951_der_bestandslauf_schreibt_nichts(db):
    """AK 7: er schlaegt vor, er handelt nicht."""
    db.save_jobs([_stelle("q951g", "Altbestand Quintus", quelle="stepstone")])
    db.save_jobs([_stelle("q951h", "Altbestand Quintus (m/w/d)", quelle="indeed")])

    vorher = db.connect().execute("SELECT hash, is_active, dismiss_reason "
                                  "FROM jobs ORDER BY hash").fetchall()
    bericht = sd.bestand_pruefen(db)
    nachher = db.connect().execute("SELECT hash, is_active, dismiss_reason "
                                   "FROM jobs ORDER BY hash").fetchall()

    assert [tuple(r) for r in vorher] == [tuple(r) for r in nachher], (
        "Der Diagnoselauf hat den Bestand veraendert.")
    assert bericht["status"] == "vorschau"
    assert bericht["gruppen"] >= 1


def test_951_der_bericht_traegt_keine_firmennamen(db):
    """Er soll in einem Issue landen koennen (DoD 9)."""
    db.save_jobs([_stelle("q951i", "Bericht Quintus", firma="Halbleiterwerk Nord GmbH")])
    db.save_jobs([_stelle("q951j", "Bericht Quintus (m/w/d)",
                          firma="Halbleiterwerk Nord GmbH", quelle="xing")])
    bericht = sd.bestand_pruefen(db)
    text = repr(bericht)
    assert "Halbleiterwerk" not in text
    assert "Bericht Quintus" not in text, "Der Titel steht im Bericht."


# ------------------------------------------- Das Nadeloehr und sein Guard


def test_951_der_suchlauf_geht_durch_das_nadeloehr():
    """Die Identitaetsfrage hat EINE Antwort.

    Bis v1.7.71 verglich `save_jobs` exakt und `stelle_manuell_anlegen`
    mit Aehnlichkeit — dieselbe Frage, zwei Regeln, und die schwaechere
    lief auf dem Weg, ueber den fast alles hereinkommt.
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent"
              / "database.py").read_text(encoding="utf-8")
    start = quelle.index("def save_jobs")
    block = quelle[start:start + 14000]
    assert "stellen_dublette.finde(" in block, (
        "save_jobs baut die Erkennung wieder selbst.")
    # Der alte Weg darf nicht danebenstehen.
    assert "self._dedup_key(" not in block, (
        "Der alte exakte Vergleich laeuft noch daneben — zwei Regeln "
        "fuer eine Frage sind der Anlass dieses Issues.")


def test_951_der_duplikat_vermerk_landet_nicht_im_notizblock(db):
    """Nebenbefund, beim Bauen gefunden und hier festgehalten.

    Bis v1.7.71 schrieb der Duplikat-Vermerk nach
    `jobs.research_notes` — den Notizblock der Firmen-Recherche. Die
    Zusammenfuehrung aus #956 haette ihn deshalb als RECHERCHE gewertet
    und in die Liste des Menschen gelegt. Gemessen am Bestand: 9 von
    107 Altzeilen sind in Wahrheit Duplikat-Protokoll.
    """
    db.save_jobs([_stelle("q951k", "Vermerk Quintus", quelle="stepstone")])
    db.save_jobs([_stelle("q951l", "Vermerk Quintus (m/w/d)", quelle="indeed")])

    zweit = db.get_job(db.resolve_job_hash("q951l"))
    assert zweit["is_active"] == 0
    assert not (zweit.get("research_notes") or "").strip(), (
        "Der Vermerk steht im Recherche-Notizblock.")
    assert "Duplikat von" in (zweit.get("dismiss_note") or "")


def test_951_der_vermerk_wird_als_protokoll_erkannt(db):
    """Sonst wandert er bei der Zusammenfuehrung in die Recherche."""
    from bewerbungs_assistent.services import recherche_ablage

    db.save_jobs([_stelle("q951m", "Protokoll Quintus", quelle="stepstone")])
    db.save_jobs([_stelle("q951n", "Protokoll Quintus (m/w/d)", quelle="indeed")])
    notiz = db.get_job(db.resolve_job_hash("q951n"))["dismiss_note"]
    assert recherche_ablage.ist_protokoll(notiz), (
        "Der Duplikat-Vermerk gilt als Recherche.")


def test_951_beide_listen_liefern_die_quellen():
    """AK 6 auf beiden Wegen, aus derselben Quelle."""
    for datei in ("src/bewerbungs_assistent/tools/jobs.py",
                  "src/bewerbungs_assistent/dashboard.py"):
        quelle = (_repo() / datei).read_text(encoding="utf-8-sig")
        assert "stellen_quellen" in quelle, f"{datei} zeigt keine Quellenliste."


def test_951_duplikate_innerhalb_eines_laufs_werden_erkannt(db):
    """Ein Suchlauf ueber mehrere Portale liefert sie im selben Rutsch.

    Wuerde nur gegen den BESTAND geprueft, kaemen zwei Funde desselben
    Laufs beide als neu herein — und genau so laeuft eine Jobsuche.
    """
    db.save_jobs([
        _stelle("q951o", "Gleichlauf Quintus", quelle="stepstone"),
        _stelle("q951p", "Gleichlauf Quintus (m/w/d)", quelle="indeed"),
    ])
    aktive = db.connect().execute(
        "SELECT COUNT(*) FROM jobs WHERE is_active=1").fetchone()[0]
    assert aktive == 1, "Beide Funde desselben Laufs sind aktiv geblieben."
