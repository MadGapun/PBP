"""Tests fuer v1.7.67 — #1011: Kontakt bei der Interaktion.

Nutzerregel vom 09.09.2026:

    "Sobald mit einer Stelle mehr geschieht als eine Analyse, also sobald
    ein Austausch stattfindet, soll der zugehoerige Kontakt angelegt
    werden. Denn ab diesem Moment gibt es eine Historie, und eine
    Historie braucht jemanden, an dem sie haengt."

Gemessen: an einem Arbeitstag kamen 14 Stellen herein — 11 ueber eine
Sammeluebernahme, 3 einzeln. Das Einzel-Werkzeug nahm Kontaktdaten
entgegen, das Sammel-Werkzeug hatte keine Kontaktfelder. Bei den 11
entstand kein einziger Ansprechpartner, obwohl in mindestens einem
Anzeigentext eine namentlich stand.

**Ob ein Kontakt entsteht, hing am Anlageweg** — dieselbe Frage an zwei
Stellen, verschieden beantwortet.

Die Abgrenzung ist dabei die eigentliche Regel und wird hier in BEIDE
Richtungen geprueft: reine Lesevorgaenge (sichten, bewerten,
aussortieren) erzeugen weiterhin nichts.
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


def _werkzeuge(db, modul):
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

    modul.register(_Sammler(), db, logging.getLogger("test"))
    return gesammelt


def _bewerbungen(db):
    from bewerbungs_assistent.tools import bewerbungen as bt
    return _werkzeuge(db, bt)


def _jobs(db):
    from bewerbungs_assistent.tools import jobs as jt
    return _werkzeuge(db, jt)


# ══ AK 1: nach einer Bewerbung gibt es einen Kontakt ════════════════

def test_1011_bewerbung_legt_den_ansprechpartner_als_kontakt_an(db):
    """Der Kern.

    `ansprechpartner` und `kontakt_email` lagen bisher NUR als Freitext
    an der Bewerbung — ein Name, den keine Auswertung kennt und den kein
    Kontakt-Werkzeug findet.
    """
    antwort = _bewerbungen(db)["bewerbung_erstellen"](
        title="PLM Consultant", company="Musterwerk GmbH",
        ansprechpartner="Alex Muster", kontakt_email="alex@example.org")
    assert antwort["kontakt"]["status"] == "angelegt"

    kontakte = db.list_contacts()
    assert len(kontakte) == 1
    assert kontakte[0]["full_name"] == "Alex Muster"
    assert kontakte[0]["company"] == "Musterwerk GmbH"


def test_1011_der_kontakt_haengt_an_der_bewerbung(db):
    """Ohne Verknuepfung waere es eine Karteikarte ohne Historie."""
    antwort = _bewerbungen(db)["bewerbung_erstellen"](
        title="PLM Consultant", company="Musterwerk GmbH",
        ansprechpartner="Alex Muster", kontakt_email="alex@example.org")
    verknuepft = db.get_contacts_for_target(
        "application", antwort["bewerbung_id_voll"])
    assert [k["full_name"] for k in verknuepft] == ["Alex Muster"]


def test_1011_dieselbe_person_wird_wiedererkannt(db):
    """Sonst flutet die neue Regel die Kontaktliste.

    `add_contact` prueft nichts — jeder Aufruf legt an. Bei "Kontakt bei
    JEDER Interaktion" waere die Liste in wenigen Tagen unbrauchbar
    gewesen.
    """
    werkzeuge = _bewerbungen(db)
    werkzeuge["bewerbung_erstellen"](
        title="PLM Consultant", company="Musterwerk GmbH",
        ansprechpartner="Alex Muster", kontakt_email="alex@example.org")
    zweite = werkzeuge["bewerbung_erstellen"](
        title="PDM Manager", company="Musterwerk GmbH",
        ansprechpartner="Alex Muster", kontakt_email="alex@example.org",
        force=True)
    assert zweite["kontakt"]["status"] == "vorhanden"
    assert len(db.list_contacts()) == 1


def test_1011_gleicher_name_bei_anderer_firma_ist_ein_anderer_mensch(db):
    """Die Gegenrichtung — und die wichtigere.

    Zwei Historien in eine Karteikarte zusammenzuwerfen waere schlimmer
    als eine Dublette. Nur der Name reicht deshalb NICHT.
    """
    werkzeuge = _bewerbungen(db)
    werkzeuge["bewerbung_erstellen"](
        title="Rolle A", company="Musterwerk GmbH",
        ansprechpartner="Alex Muster")
    werkzeuge["bewerbung_erstellen"](
        title="Rolle B", company="Musterwerk Nord GmbH",
        ansprechpartner="Alex Muster")
    assert len(db.list_contacts()) == 2


def test_1011_ohne_ansprechpartner_entsteht_kein_kontakt(db):
    """"sofern ein Ansprechpartner bekannt ist" — sonst nichts.

    Eine Karteikarte ohne Person waere eine erfundene Angabe.
    """
    antwort = _bewerbungen(db)["bewerbung_erstellen"](
        title="PLM Consultant", company="Musterwerk GmbH")
    assert "kontakt" not in antwort
    assert db.list_contacts() == []


def test_1011_der_befund_steht_in_der_antwort(db):
    """Ein Rueckgabewert, den niemand liest, ist keiner (#997).

    Wer nicht erfaehrt, dass ein Kontakt entstanden ist, legt ihn ein
    zweites Mal an.
    """
    antwort = _bewerbungen(db)["bewerbung_erstellen"](
        title="PLM Consultant", company="Musterwerk GmbH",
        ansprechpartner="Alex Muster")
    assert "Alex Muster" in antwort["nachricht"]


# ══ AK 4: Lesevorgaenge erzeugen nichts ═════════════════════════════

def test_1011_sichten_und_bewerten_erzeugen_keinen_kontakt(db):
    """Die Abgrenzung ist die eigentliche Regel.

    Ein Ansprechpartner aus einer Anzeige, mit dem nie gesprochen wurde,
    ist eine Karteikarte; einer, mit dem ein Austausch lief, ist eine
    Historie.
    """
    db.save_jobs([{
        "hash": "les1", "title": "PLM Consultant (m/w/d)",
        "company": "Musterwerk GmbH", "location": "Hamburg", "score": 20,
        "url": "https://example.org/les1", "source": "manuell",
        "description": "Ansprechpartnerin ist Alex Muster. " * 8,
    }])
    werkzeuge = _jobs(db)
    werkzeuge["stellen_anzeigen"]()
    voll = next(j["hash"] for j in db.get_active_jobs())
    werkzeuge["fit_analyse"](job_hash=voll.split(":")[-1])
    werkzeuge["stelle_bewerten"](job_hash=voll.split(":")[-1],
                                 bewertung="passt_nicht",
                                 grund="falsches_fachgebiet")
    assert db.list_contacts() == [], \
        "Sichten, Analysieren und Aussortieren duerfen nichts anlegen."


# ══ AK 2: Anfrage ohne Stellenbezug ════════════════════════════════

def test_1011_kontakt_ohne_stelle_ist_moeglich(db):
    """Vor dem Bauen geprueft, ob es das schon gibt (#814).

    Es gibt es: `kontakt_anlegen` verlangt weder Stelle noch Firma. Der
    belegte Fall aus dem Issue — eine Anfrage, in der weder der
    Arbeitgeber der Absenderin noch der Mandant genannt war — laesst
    sich damit erfassen, ohne einen Platzhalter zu erfinden, der die
    Auswertung verfaelschen wuerde.
    """
    from bewerbungs_assistent.tools import kontakte as kt
    antwort = _werkzeuge(db, kt)["kontakt_anlegen"](
        name="Alex Muster", email="alex@example.org", rollen=["recruiter"])
    assert antwort.get("status") in ("angelegt", "erstellt", "ok")
    kontakte = db.list_contacts()
    assert len(kontakte) == 1
    assert not (kontakte[0].get("company") or "").strip(), \
        "Keine erfundene Firma."


# ══ AK 3: die Sammeluebernahme nimmt Kontaktdaten ═══════════════════

def test_1011_sammeluebernahme_nimmt_kontaktdaten(db):
    """Der gemessene Fall: 11 von 14 Stellen ohne Ansprechpartner."""
    treffer = [{
        "job_id": "4711", "titel": "PLM Consultant (m/w/d)",
        "firma": "Musterwerk GmbH", "ort": "Hamburg",
        "beschreibung": "Eine ausfuehrliche Stellenbeschreibung. " * 30,
        "kontakt_name": "Alex Muster", "kontakt_email": "alex@example.org",
    }]
    antwort = _jobs(db)["linkedin_treffer_uebernehmen"](
        treffer=treffer, dry_run=False)
    assert antwort["trichter"]["angelegt"] == 1
    assert antwort["trichter"].get("kontakte") == 1
    assert [k["full_name"] for k in db.list_contacts()] == ["Alex Muster"]


def test_1011_sammeluebernahme_ohne_kontaktdaten_legt_nichts_an(db):
    """Die Felder sind eine Ergaenzung, keine Pflicht."""
    treffer = [{
        "job_id": "4712", "titel": "PLM Consultant (m/w/d)",
        "firma": "Musterwerk GmbH",
        "beschreibung": "Eine ausfuehrliche Stellenbeschreibung. " * 30,
    }]
    antwort = _jobs(db)["linkedin_treffer_uebernehmen"](
        treffer=treffer, dry_run=False)
    assert antwort["trichter"]["angelegt"] == 1
    assert db.list_contacts() == []


# ══ Ein Nadeloehr, kein zweiter Weg ════════════════════════════════

def test_1011_die_anlage_steht_an_genau_einer_stelle():
    """Zehnter Fall desselben Musters — deshalb ein Aufruf, kein Hinweis.

    `add_contact` direkt zu rufen ist der Weg, auf dem die
    Wiedererkennung wieder verlorengeht. Erlaubt bleibt es nur im Dienst
    selbst und im Kontakt-Werkzeug, wo der Mensch bewusst anlegt.
    """
    # `kontakte.py` und der REST-Endpunkt `POST /api/contacts` sind der
    # BEWUSSTE Anlage-Weg: dort legt der Mensch selbst an und weiss, was
    # er tut. Alles andere ist eine Interaktion und gehoert durchs
    # Nadeloehr.
    erlaubt = {"kontakt_pflicht.py", "kontakte.py", "database.py"}
    bewusst = {"dashboard.py": {"api_create_contact"}}
    treffer = []
    for pfad in (_repo() / "src" / "bewerbungs_assistent").rglob("*.py"):
        if pfad.name in erlaubt:
            continue
        zeilen = pfad.read_text(encoding="utf-8", errors="replace").split("\n")
        for nr, zeile in enumerate(zeilen, 1):
            if "add_contact(" not in zeile.split("#")[0]:
                continue
            # Der bewusste Anlage-Endpunkt darf direkt schreiben.
            umfeld = "\n".join(zeilen[max(0, nr - 8):nr])
            if any(name in umfeld for name in bewusst.get(pfad.name, ())):
                continue
            treffer.append(f"{pfad.name}:{nr}")
    assert not treffer, (
        "Kontakt-Anlage am Nadeloehr vorbei — die Wiedererkennung "
        f"greift dort nicht: {treffer}")
