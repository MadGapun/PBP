"""Tests fuer #1023 — Anstellungsform und Umfang sind zwei Fragen.

Gemeldet am 11.09.2026 mit Messungen aus einem Bestand von 1.110
aktiven Stellen. Der Kern steht im Titel des Berichts, und er ist eine
Modellfrage, kein Fehler in einer Zeile:

    Eine Stelle hat eine Anstellungsform UND einen Umfang.
    "Festanstellung in Teilzeit" ist der Normalfall, im Ein-Feld-Modell
    aber nicht ausdrueckbar. Der Adapter muss sich entscheiden und
    waehlt immer die Vertragsart; der Umfang faellt weg.

## Die Zahl, an der man es sieht

| | |
|---|---:|
| aktive Titel mit "Teilzeit" | 103 |
| davon gespeichert als `festanstellung` | 102 |
| davon gespeichert als `teilzeit` | **0** |

`_normalize_job_type` nennt `parttime` im Docstring und hatte keinen
Zweig dafuer — jede Teilzeitstelle fiel durch bis zum letzten `return`.

## Was hier gemessen wurde — an einem ANDEREN Bestand

Die Groessenordnungen des Melders liessen sich nicht nachstellen: die
Kopie hier traegt 2.535 Stellen (davon 1 aktiv), 14 Teilzeit-Titel und
keine Ausbildungsstelle. **Ein Bericht beschreibt den Bestand, an dem
er entstanden ist** — der Mechanismus ist derselbe, die Zahlen sind es
nicht. Gemessen wurde deshalb, was die neue Erkennung am hiesigen
Bestand AENDERT:

| | vorher | nachher |
|---|---:|---:|
| Stellen mit einem Umfang | **0** (Feld gab es nicht) | **219** |
| davon `vollzeit` / `beides` / `teilzeit` | — | 167 / 41 / 11 |
| `werkstudent` | 0 | 7 |
| `praktikum` | 3 | 10 |
| `zeitarbeit` | 0 | 2 |
| `befristet` erkannt | — | 30 |

## Ein Nebenbefund aus der Messung

Eine Stelle trug `employment_type = "arbeitnehmerueberlassung"` — ein
Wert, den **keines der drei Vokabulare kennt** (Suchkriterien, Scoring,
Adapter-Zuordnung). Sie war damit weder filterbar noch bewertbar,
obwohl das Feld genau das sagt, wonach der Melder fragt. Das ist sein
Befund 3 im Bestand angetroffen, nicht im Code gelesen.

## Warum der Umfang nichts aussortiert

Er steht bei 993 von 1.110 Stellen gar nicht da, ist oft verhandelbar,
und ein Ausschluss darauf traefe vor allem die, bei denen die Angabe
nur FEHLT. Dieselbe Linie wie Remote (#989) und Entfernung
(#910/#988) — und der Melder hat sie selbst gezogen.
"""
import importlib
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import stellenart as sa  # noqa: E402

JOBS_PAGE = _repo() / "frontend" / "src" / "pages" / "JobsPage.jsx"


def _ohne_kommentare(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return "\n".join(
        z for z in text.split("\n") if not z.lstrip().startswith("//"))


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.switch_profile(datenbank.create_profile("Merkmale"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _speichern(db, titel, **extra):
    job = {
        "hash": f"h{abs(hash(titel)) % 10**8}",
        "title": titel, "company": "Firma",
        "url": f"https://example.com/1023/{abs(hash(titel)) % 10**8}",
        "source": "bundesagentur",
        "description": "Beschreibungstext. " * 20,
        "employment_type": "festanstellung",
        "score": 5,
    }
    job.update(extra)
    db.save_jobs([job])
    return db.get_job(db.resolve_job_hash(job["hash"]))


# ------------------------------------------- AK 1: zwei getrennte Merkmale


def test_form_und_umfang_sind_getrennte_dimensionen():
    """AK 1 — und die Modellaussage des ganzen Issues."""
    assert sa.TEILZEIT not in sa.ANSTELLUNGSFORMEN
    assert sa.TEILZEIT in sa.UMFAENGE
    assert sa.FESTANSTELLUNG not in sa.UMFAENGE
    # `befristet` ist ein Kennzeichen am Vertrag, keine Form —
    # ausdruecklicher Wunsch des Melders.
    assert "befristet" not in sa.ANSTELLUNGSFORMEN


def test_festanstellung_in_teilzeit_ist_ausdrueckbar():
    """Der Satz, an dem das alte Modell zerbricht."""
    m = sa.merkmale({"title": "Sachbearbeiter (m/w/d) in Teilzeit",
                     "employment_type": "festanstellung"})
    assert m["form"] == sa.FESTANSTELLUNG
    assert m["umfang"] == sa.TEILZEIT


# ---------------------------------------------------- AK 2: "beides"


@pytest.mark.parametrize("titel", [
    "Sachbearbeiter (m/w/d) Vollzeit oder Teilzeit",
    "Pflegefachkraft Voll-/Teilzeit",
    "Pflegefachkraft Voll/Teilzeit",
    "Erzieher (m/w/d) Vollzeit / Teilzeit",
    "[Full-time / part-time] Engineer",
])
def test_vollzeit_teilzeit_ist_beides_und_nicht_eines_davon(titel):
    """AK 2.

    "Vollzeit / Teilzeit" ist keine Mehrdeutigkeit, sondern eine
    Zusage. Ein Etikett mit nur zwei Werten macht daraus eine
    Falschangabe, egal welches es waehlt.
    """
    assert sa.umfang_erkennen({"title": titel})["umfang"] == sa.BEIDES


def test_das_vollzeit_muster_vertraegt_zwei_trennzeichen():
    """Vom Durchspielen der Beispiele gefunden, nicht vom Nachdenken.

    `[-\\s/]?` liess nur EIN Trennzeichen zu und verfehlte damit
    "Voll-/Teilzeit" — die haeufigste Schreibweise ueberhaupt. Die
    Stelle galt dann als reine Teilzeitstelle, obwohl der Titel
    ausdruecklich beides anbietet.
    """
    assert sa._VOLLZEIT.search("Voll-/Teilzeit")
    assert sa._VOLLZEIT.search("Voll/Teilzeit")
    assert sa._VOLLZEIT.search("Vollzeit")
    assert not sa._VOLLZEIT.search("Teilzeit")


# ------------------------------------- AK 3: unbekannt bleibt aktiv


def test_ohne_angabe_ist_der_umfang_unbekannt(db):
    """AK 3 — und der Grund, warum er nichts aussortiert."""
    job = _speichern(db, "Senior IT Projektmanager (m/w/d)")
    assert job["arbeitsumfang"] == sa.UNBEKANNT
    assert job["is_active"] == 1


def test_der_umfang_sortiert_nie_aus(db):
    """AK 9.

    Auch eine Teilzeitstelle bleibt aktiv, wenn die Auswahl sie nicht
    nennt — der Umfang ist kein Ausschlusskriterium. Der Melder hat das
    selbst begruendet: er fehlt bei 993 von 1.110 Stellen.
    """
    db.set_search_criteria("stellentypen", ["festanstellung"])
    job = _speichern(db, "Sachbearbeiter (m/w/d) in Teilzeit")
    assert job["arbeitsumfang"] == sa.TEILZEIT
    assert job["is_active"] == 1, "Der Umfang hat aussortiert"


# ------------------------------- AK 4: die Auswahl entscheidet ueber aktiv


def test_die_auswahl_entscheidet_ueber_aktiv_und_ausgeblendet(db):
    """AK 4 — der Punkt, an dem die Auswahl endlich etwas bewirkt."""
    db.set_search_criteria("stellentypen", ["festanstellung"])
    passt = _speichern(db, "Senior Consultant (m/w/d)")
    passt_nicht = _speichern(db, "Werkstudent Data Science (m/w/d)")
    assert passt["is_active"] == 1
    assert passt_nicht["is_active"] == 0
    assert passt_nicht["dismiss_reason"] == "unpassendes_arbeitsmodell"


def test_eine_auswahl_aus_nur_teilzeit_filtert_gar_nichts():
    """Der Fall, der ohne `fuer_form` jede Stelle ausgeschlossen haette.

    Bis #1023 war `teilzeit` ein zulaessiger `stellentypen`-Wert. Wer
    NUR ihn gewaehlt hatte, haette nach der Trennung eine Auswahl ohne
    jede Anstellungsform — und die rohe Liste haette jede Stelle mit
    belegter Form verworfen, weil keine davon "teilzeit" heisst.
    """
    job = {"title": "Werkstudent Data Science",
           "employment_type": "festanstellung"}
    assert sa.fuer_form(["teilzeit"]) == []
    assert sa.unerwuenscht(job, {"stellentypen": ["teilzeit"]}) is None
    # Die Einstellung verdunstet dabei nicht — sie lebt als Umfang
    # weiter (#988: ein vom Menschen gesetzter Wert wird nicht still
    # verworfen).
    assert sa.umfang_aus_auswahl(["teilzeit"]) == sa.TEILZEIT


# ------------------------------------------------ AK 7: Ausbildung


@pytest.mark.parametrize("titel", [
    "Ausbildung zum Fachinformatiker (m/w/d)",
    "Auszubildende zur Kauffrau für Büromanagement",
    "Azubi Mechatronik (m/w/d)",
])
def test_ausbildung_ist_eine_eigene_form(titel):
    """AK 7.

    Sie kam ueber die Pflichtbegriffe herein (36 aktive Stellen beim
    Melder) und hatte keinen Weg hinaus: kein Stellentyp, kein
    Etikett, kein Regler. Er musste sich dafuer einen eigenen
    Ablehnungsgrund anlegen.
    """
    assert sa.erkenne({"title": titel})["art"] == sa.AUSBILDUNG
    assert sa.AUSBILDUNG in sa.ANSTELLUNGSFORMEN


def test_ausbildung_ist_abwaehlbar(db):
    """Waehlbar UND abwaehlbar — beides gehoert zum Kriterium."""
    db.set_search_criteria("stellentypen", ["festanstellung"])
    job = _speichern(db, "Ausbildung zum Fachinformatiker (m/w/d)")
    assert job["is_active"] == 0

    db.set_search_criteria("stellentypen", ["festanstellung", "ausbildung"])
    job2 = _speichern(db, "Ausbildung zur Industriekauffrau (m/w/d)")
    assert job2["is_active"] == 1


# ------------------------------------- AK 8: Teilzeit im Titel wird gespeichert


def test_teilzeit_im_titel_landet_als_umfang_in_der_datenbank(db):
    """AK 8 — die Zahl 103 gegen 0.

    Bis v1.7.83 hat `stellenart` zwar ENTSCHIEDEN, aber nichts
    abgelegt. Eine Erkennung, deren Ergebnis nirgends landet, ist fuer
    jede Anzeige und jeden Filter unsichtbar.
    """
    job = _speichern(db, "Pflegefachkraft (m/w/d) in Teilzeit")
    assert job["arbeitsumfang"] == sa.TEILZEIT
    assert job["employment_type"] == sa.FESTANSTELLUNG


def test_die_erkannte_form_wird_gespeichert(db):
    """Dieselbe Luecke bei der Form."""
    job = _speichern(db, "Working Student Software Engineering (m/f/d)")
    assert job["employment_type"] == sa.WERKSTUDENT


# ------------------------------- AK 10: strukturierte Felder, quellenunabhaengig


@pytest.mark.parametrize("job_type,form,umfang", [
    ("fulltime", "festanstellung", "vollzeit"),
    ("parttime", "festanstellung", "teilzeit"),
    ("fulltime, parttime", "festanstellung", "beides"),
    ("contract", "freelance", ""),
    ("internship", "praktikum", ""),
    ("apprenticeship", "ausbildung", ""),
    ("", "festanstellung", ""),
])
def test_jobspy_liest_beide_dimensionen_aus_job_type(job_type, form, umfang):
    """AK 10 fuer jobspy.

    Ein Feld, zwei Fragen — und bis v1.7.83 wurde nur eine davon
    gelesen. `parttime` stand im Docstring und hatte keinen Zweig.
    """
    from bewerbungs_assistent.job_scraper.jobspy_source import (
        _normalize_job_type, _normalize_umfang)
    assert _normalize_job_type(job_type) == form
    assert _normalize_umfang(job_type) == umfang


@pytest.mark.parametrize("daten,erwartet", [
    ({"arbeitszeitVollzeit": True}, {"arbeitsumfang": "vollzeit"}),
    ({"arbeitszeitTeilzeitVormittag": True}, {"arbeitsumfang": "teilzeit"}),
    ({"arbeitszeitVollzeit": True, "arbeitszeitTeilzeitFlexibel": True},
     {"arbeitsumfang": "beides"}),
    ({"istArbeitnehmerUeberlassung": True},
     {"employment_type": "zeitarbeit"}),
    ({"befristung": "BEFRISTET"}, {"befristet": 1}),
    ({}, {}),
])
def test_bundesagentur_liest_ihre_strukturierten_felder(daten, erwartet):
    """AK 10 fuer die Bundesagentur.

    Die Detail-API liefert das alles; im Projekt kam keines dieser
    Felder vor. Zeitarbeit wurde stattdessen aus Stichwoertern im Text
    GERATEN, obwohl die Quelle es ausdruecklich sagt.
    """
    from bewerbungs_assistent.job_scraper.bundesagentur import _ba_merkmale
    assert _ba_merkmale(daten) == erwartet


def test_ein_wert_ausserhalb_jedes_vokabulars_wird_zugeordnet():
    """Der Nebenbefund aus der Messung.

    Eine Stelle im Bestand trug `arbeitnehmerueberlassung` als
    `employment_type` — ein Wert, den weder die Suchkriterien noch das
    Scoring-Vokabular noch die Adapter-Zuordnung kennen. Sie war damit
    weder filterbar noch bewertbar.
    """
    assert sa.normalisiere_form("arbeitnehmerueberlassung") == sa.ZEITARBEIT
    # Ein UMFANG im Formfeld gehoert zur Form `festanstellung` — der
    # Umfang selbst kommt aus seiner eigenen Dimension.
    assert sa.normalisiere_form("vollzeit") == sa.FESTANSTELLUNG
    # Unbekanntes wird NICHT geraten, sondern durchgereicht (#989).
    assert sa.normalisiere_form("voellig_neu") == "voellig_neu"


# ------------------------------------ Die Beschreibung markiert nur


def test_die_beschreibung_aendert_die_form_nie():
    """Rangfolge 3 des Melders, woertlich.

    "Erfahrung durch Praktikum wuenschenswert" ist eine ANFORDERUNG,
    keine Praktikumsstelle.
    """
    m = sa.merkmale({
        "title": "Senior Consultant (m/w/d)",
        "description": "Erfahrung durch ein Praktikum ist wuenschenswert. "
                       "Auch eine Ausbildung im Bereich X hilft.",
    })
    assert m["form"] == sa.FESTANSTELLUNG


def test_die_beschreibung_ergibt_hoechstens_beides():
    """Teilzeit im Fliesstext ist ein ANGEBOT, keine Festlegung."""
    m = sa.merkmale({
        "title": "Sachbearbeiter (m/w/d)",
        "description": "Die Stelle ist auch in Teilzeit moeglich.",
    })
    assert m["umfang"] == sa.BEIDES
    assert m["umfang_beleg"] == "beschreibung"


# --------------------------------------------- AK 5+6: die Oberflaeche


def test_beide_merkmale_stehen_als_kennzeichen_auf_der_karte():
    """AK 5."""
    quelle = _ohne_kommentare(JOBS_PAGE.read_text(encoding="utf-8"))
    assert "ANSTELLUNGSFORM_TEXT[job.employment_type]" in quelle
    assert "UMFANG_TEXT[job.arbeitsumfang]" in quelle
    assert 'job.befristet ? <Badge tone="neutral">Befristet</Badge>' in quelle
    # `unbekannt` bekommt bewusst KEIN Abzeichen — ein Etikett
    # "unbekannt" an fast jeder Stelle waere Rauschen.
    assert 'job.arbeitsumfang !== "unbekannt"' in quelle


def test_es_gibt_zwei_kombinierbare_filter():
    """AK 6."""
    quelle = _ohne_kommentare(JOBS_PAGE.read_text(encoding="utf-8"))
    assert "filters.employmentType" in quelle
    assert "filters.arbeitsumfang" in quelle
    assert "typeMatch && umfangMatch" in quelle, (
        "Die beiden Filter muessen UND-verknuepft sein, sonst sind sie "
        "nicht kombinierbar")


def test_beides_zaehlt_fuer_beide_filterrichtungen():
    """Eine Anzeige, die beides anbietet, ist fuer den Teilzeit-Suchenden
    eine Teilzeitstelle."""
    quelle = _ohne_kommentare(JOBS_PAGE.read_text(encoding="utf-8"))
    assert 'job.arbeitsumfang === "beides"' in quelle
    assert 'filters.arbeitsumfang === "teilzeit"' in quelle


def test_die_oberflaeche_kennt_alle_formen():
    """Die Zuordnung stand als verschachtelter Ternaer im JSX und kannte
    `zeitarbeit` und `ausbildung` nicht — obwohl beide im Bestand
    vorkommen."""
    quelle = JOBS_PAGE.read_text(encoding="utf-8")
    for form in sa.ANSTELLUNGSFORMEN:
        assert f"{form}:" in quelle, f"{form} fehlt in der Oberflaeche"


# ----------------------------------------- AK 11: Altbestand nachziehen


def _register(db):
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools.jobs import register as _reg
    mcp = FastMCP("test")
    _reg(mcp, db, logging.getLogger("test"))
    return mcp


def _call(mcp, name, args):
    import asyncio

    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


def test_der_altbestand_laesst_sich_nachziehen_vorschau_zuerst(db):
    """AK 11."""
    con = db.connect()
    _speichern(db, "Sachbearbeiter (m/w/d) in Teilzeit")
    # Den Altzustand herstellen: so sah der Bestand vor #1023 aus.
    con.execute("UPDATE jobs SET arbeitsumfang=NULL, "
                "employment_type='festanstellung'")
    con.commit()

    mcp = _register(db)
    vorschau = _call(mcp, "stellen_merkmale_nachziehen", {})
    assert vorschau["status"] == "vorschau"
    assert vorschau["geaendert"] >= 1
    assert con.execute(
        "SELECT arbeitsumfang FROM jobs").fetchone()[0] is None, (
        "Die Vorschau hat geschrieben")

    erg = _call(mcp, "stellen_merkmale_nachziehen", {"dry_run": False})
    assert erg["status"] == "nachgetragen"
    assert con.execute(
        "SELECT arbeitsumfang FROM jobs").fetchone()[0] == sa.TEILZEIT


def test_der_nachzieh_lauf_aendert_aktiv_nicht(db):
    """Er traegt Merkmale nach und entscheidet nichts.

    Eine Stelle, die heute in der Liste steht, bleibt dort — wer seine
    Auswahl danach anwenden will, hat mit den nachgetragenen Merkmalen
    erst die Grundlage dafuer.
    """
    con = db.connect()
    _speichern(db, "Werkstudent Data Science (m/w/d)")
    con.execute("UPDATE jobs SET is_active=1, employment_type='festanstellung',"
                " arbeitsumfang=NULL, dismiss_reason=NULL")
    con.commit()

    mcp = _register(db)
    _call(mcp, "stellen_merkmale_nachziehen", {"dry_run": False})
    zeile = con.execute(
        "SELECT is_active, employment_type FROM jobs").fetchone()
    assert zeile["employment_type"] == sa.WERKSTUDENT
    assert zeile["is_active"] == 1, "Der Nachzieh-Lauf hat aussortiert"


# ----------------------------------------------- Das Vokabular, einmal


def test_die_suchkriterien_nehmen_das_vokabular_aus_dem_modul():
    """Befund 3: drei Vokabulare, keins deckungsgleich.

    Die Liste stand in `tools/suche.py` fest verdrahtet. Jetzt kommt
    sie aus dem Modul, das die Erkennung macht — sonst laufen sie beim
    naechsten neuen Wert wieder auseinander.
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "tools"
              / "suche.py").read_text(encoding="utf-8")
    assert "valid = set(_art.BEKANNTE_ARTEN)" in quelle
    assert '{"festanstellung", "freelance", "teilzeit", "praktikum", "werkstudent"}' not in quelle
