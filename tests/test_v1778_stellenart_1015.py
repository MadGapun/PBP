"""Tests fuer #1015 — `stellentypen` bekommt einen filternden Leser.

Gemeldet am 10.09.2026: in den Suchkriterien steht `festanstellung,
freelance`, ein Pflichtpraktikum lag trotzdem aktiv in der Liste.

Am Bestand gemessen (2.535 Titel, Kopie) — und die Messung hat die
erste Fassung der Marker ZWEIMAL korrigiert:

| Marker | roh | geschaerft |
|---|---|---|
| `praktikum` | 22 Treffer, 11 davon Fehlalarm ueber "International" | 11, sauber |
| `werkstudent` | 6 | 7 |
| `teilzeit` | 16 | 10 (6 bieten auch Vollzeit an) |

Der teuerste Fehlalarm war ein **Senior IT Projektmanager**, den
`\\bintern` ueber "International" als Praktikum ausgewiesen und damit
automatisch aussortiert haette.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import stellenart as sa  # noqa: E402
from bewerbungs_assistent.services import ablehnungsgruende as ag  # noqa: E402


@pytest.fixture
def db(tmp_path):
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


def _job(titel, **extra):
    basis = {
        "hash": "h" + str(abs(hash(titel)) % 10**8),
        "title": titel,
        "company": "Beispiel GmbH",
        "url": f"https://example.com/1015/{abs(hash(titel)) % 10**8}",
        "source": "bundesagentur",
        "description": "Beschreibungstext. " * 20,
        "employment_type": "festanstellung",
        "score": 5,
    }
    basis.update(extra)
    return basis


# ------------------------------------------------- Die Erkennung selbst


@pytest.mark.parametrize("titel,erwartet", [
    ("Pflichtpraktikum als CRM-Manager (m/w/d)", sa.PRAKTIKUM),
    ("Pflichtpraktikum Recruiting (m/w/d)", sa.PRAKTIKUM),
    ("Praktikum Redaktion (w/m/d)", sa.PRAKTIKUM),
    ("Intern, Brand Marketing", sa.PRAKTIKUM),
    ("Working Student Software Engineering (m/f/d)", sa.WERKSTUDENT),
    ("Werkstudent Datenpflege (m/w/d)", sa.WERKSTUDENT),
])
def test_1015_der_titel_weist_die_art_aus(titel, erwartet):
    befund = sa.erkenne(_job(titel))
    assert befund["art"] == erwartet
    assert befund["belegt"] is True
    assert befund["beleg"] == "titel"


def test_1015_teilzeit_ist_keine_anstellungsform_mehr():
    """Der Fall, den v1.7.84 (#1023) aus diesem Test herausgenommen hat.

    Hier stand bis dahin `("Steuerberater (m/w/d) in Teilzeit und im
    Homeoffice", sa.TEILZEIT)` — und die Erwartung war richtig, solange
    es nur EIN Feld gab.

    Der zweite Melder-Bericht hat gezeigt, dass genau das der Fehler
    ist: eine Stelle hat eine Anstellungsform UND einen Umfang, und
    "Festanstellung in Teilzeit" ist der Normalfall. Der Titel oben
    sagt nichts ueber die Vertragsart — er sagt etwas ueber den Umfang.

    **Der Test wird deshalb nicht geloescht, sondern gedreht**: die
    Aussage "der Titel weist es aus" gilt weiter, nur in der anderen
    Dimension (v1.7.31 MERKE 2).
    """
    job = _job("Steuerberater (m/w/d) in Teilzeit und im Homeoffice")
    assert sa.erkenne(job)["art"] == sa.FESTANSTELLUNG
    assert sa.erkenne(job)["belegt"] is False, (
        "Teilzeit im Titel darf die FORM nicht mehr belegen")

    umfang = sa.umfang_erkennen(job)
    assert umfang["umfang"] == sa.TEILZEIT
    assert umfang["beleg"] == "titel"
    assert sa.TEILZEIT not in sa.ANSTELLUNGSFORMEN


@pytest.mark.parametrize("titel", [
    # Die gemessenen Fehlalarme der ersten Fassung. Jeder einzelne haette
    # eine echte Festanstellung automatisch aussortiert.
    "Senior IT Projektmanager w/m/d International Presales",
    "Internal Project Manager (f/m/d) for Operational Excellence",
    "Projektcontroller & Contract Manager (m/w/d) Internationaler Anlagenbau",
    "IT Mitarbeiter (m/w/d) Internationale Anwaltskanzlei",
    "Business Program Manager (m/w/d) International",
])
def test_1015_international_ist_kein_praktikum(titel):
    """Die rechte Wortgrenze ist der ganze Unterschied.

    `\\bintern` ohne sie trifft "International" und "Internal" — am
    Bestand 11 von 14 Treffern. Dritter Fall nach "ki" in "Kita" (#970)
    und "us" in "Kundenservice" (#996).
    """
    befund = sa.erkenne(_job(titel))
    assert befund["art"] != sa.PRAKTIKUM
    assert befund["belegt"] is False


@pytest.mark.parametrize("titel", [
    "Berater Risk Consulting Voll/Teilzeit (w/m/d)",
    "Projekt- und Prozessmanager Steuern (m/w/d) Vollzeit oder Teilzeit",
    "SAP Solution Architect (m/f/d) [Full-time / part-time]",
    "Account Manager Teilzeit / Vollzeit",
])
def test_1015_auch_teilzeit_ist_nicht_teilzeit(titel):
    """Wer beides anbietet, bietet auch Vollzeit an.

    Am Bestand betrifft das 6 von 16 Teilzeit-Titeln. Sie als Teilzeit
    einzuordnen und dann auszuschliessen wuerde eine Vollzeitstelle
    wegwerfen — der teure Fehler (#827).
    """
    assert sa.erkenne(_job(titel))["belegt"] is False


def test_1015_die_quelle_wird_nicht_ueberschrieben_wenn_sie_etwas_weiss():
    """Ein Freelance-Portal meldet `freelance` — das ist eine Auskunft
    ueber sich selbst, keine Vorgabe."""
    befund = sa.erkenne(_job("Praktikum Beratung",
                             employment_type="freelance"))
    assert befund["art"] == "freelance"
    assert befund["belegt"] is False


def test_1015_ohne_titel_passiert_nichts():
    assert sa.erkenne({"employment_type": "festanstellung"})["belegt"] is False
    assert sa.erkenne({})["belegt"] is False


# --------------------------------------------- Nur belegt wird gefiltert


def test_1015_ohne_gepflegte_stellentypen_wird_nichts_ausgeschlossen():
    assert sa.unerwuenscht(_job("Pflichtpraktikum Recruiting"), {}) is None
    assert sa.unerwuenscht(_job("Pflichtpraktikum Recruiting"),
                           {"stellentypen": []}) is None


def test_1015_ohne_titelbeleg_wird_nichts_ausgeschlossen():
    """`bundesagentur` schreibt fuer JEDE Stelle `festanstellung`.

    Stuende der Ausschluss auf dieser Angabe, wuerde jede Stelle einer
    Quelle ohne echte Typ-Erkennung zum Zufallsopfer der Wunschliste.
    """
    job = _job("PLM Solution Architekt (m/w/d)")
    assert sa.unerwuenscht(job, {"stellentypen": ["freelance"]}) is None


def test_1015_belegte_falsche_art_wird_benannt():
    job = _job("Pflichtpraktikum als CRM-Manager (m/w/d)")
    erg = sa.unerwuenscht(job, {"stellentypen": ["festanstellung",
                                                 "freelance"]})
    assert erg is not None
    assert erg["art"] == sa.PRAKTIKUM
    assert "Pflichtpraktikum" in erg["wort"]
    assert "festanstellung" in erg["grund"]


def test_1015_gesuchte_art_bleibt():
    job = _job("Werkstudent Datenpflege (m/w/d)")
    assert sa.unerwuenscht(
        job, {"stellentypen": ["festanstellung", "werkstudent"]}) is None


# ------------------------------------------------- Der Weg durch save_jobs


def _art_und_grund(db, job):
    voll = db.resolve_job_hash(job["hash"])
    row = db.connect().execute(
        "SELECT is_active, dismiss_reason FROM jobs WHERE hash=?",
        (voll,)).fetchone()
    return row[0], row[1]


def test_1015_praktikum_landet_nicht_aktiv_im_bestand(db):
    """Das erste Akzeptanzkriterium des Melders, woertlich."""
    db.set_search_criteria("stellentypen", ["festanstellung", "freelance"])
    job = _job("Pflichtpraktikum als CRM-Manager (m/w/d)")
    erg = db.save_jobs([job])
    assert erg["stellenart_erkannt"] == 1
    aktiv, grund = _art_und_grund(db, job)
    assert aktiv == 0, "Das Praktikum liegt weiterhin aktiv in der Liste."
    assert "unpassendes_arbeitsmodell" in (grund or "")


def test_1015_eine_gesuchte_stelle_bleibt_aktiv(db):
    db.set_search_criteria("stellentypen", ["festanstellung", "freelance"])
    job = _job("PLM Solution Architekt (m/w/d)")
    erg = db.save_jobs([job])
    assert erg["stellenart_erkannt"] == 0
    assert _art_und_grund(db, job)[0] == 1


def test_1015_handeintrag_wird_nie_automatisch_aussortiert(db):
    """Eine bewusste Nutzer-Aktion schlaegt die Automatik — dieselbe
    Ausnahme, die der Nicht-DACH-Ausschluss aus #732 kennt."""
    db.set_search_criteria("stellentypen", ["festanstellung"])
    job = _job("Praktikum Redaktion (w/m/d)", source="manuell",
               _manual_entry=True)
    db.save_jobs([job])
    assert _art_und_grund(db, job)[0] == 1


def test_1015_der_grund_steht_in_der_whitelist(db):
    """Ein erfundener Ablehnungsgrund verfaelscht Statistik und
    Lerneffekt (#663 Teil 2) — und `normalisiere_dismiss_wert` wuerde
    ihn still auf `sonstiges` kippen."""
    db.set_search_criteria("stellentypen", ["festanstellung"])
    job = _job("Working Student Software Engineering (m/f/d)")
    db.save_jobs([job])
    grund = _art_und_grund(db, job)[1]
    assert ag.ist_konform(grund), f"'{grund}' ist kein Whitelist-Grund."


def test_1015_der_lauf_zaehlt_was_er_wegnimmt(db):
    """Eine stille Aussortierung ist eine unsichtbare Blockade (#992).

    Der Zaehler steht in der Antwort von `save_jobs`, damit der
    Filtertrichter ihn ausweisen kann.
    """
    db.set_search_criteria("stellentypen", ["festanstellung"])
    erg = db.save_jobs([
        _job("Pflichtpraktikum Recruiting (m/w/d)"),
        _job("Working Student Process Management (all genders)"),
        _job("PLM Solution Architekt (m/w/d)"),
    ])
    assert erg["stellenart_erkannt"] == 2


# ------------------------------------------------------------- Guard


def test_1015_keine_gehaltsschaetzung_fuer_praktika():
    """Drittes Akzeptanzkriterium: lieber keine Angabe als eine
    unmoegliche.

    Die Spannen in `estimate_salary` beschreiben Vollzeit-Anstellungen.
    Auf ein Pflichtpraktikum angewandt kamen 80.000 bis 120.000 EUR
    heraus, und die Zahl floss in die Durchschnittskennzahl.
    """
    from bewerbungs_assistent.job_scraper import estimate_salary

    assert estimate_salary("Pflichtpraktikum als CRM-Manager (m/w/d)",
                           "festanstellung", "Hamburg") == (None, None, None)
    assert estimate_salary("Working Student Software Engineering",
                           "festanstellung", "Hamburg") == (None, None, None)
    # Gegenrichtung: die Fehlalarm-Titel bekommen ihre Schaetzung.
    geschaetzt = estimate_salary(
        "Senior IT Projektmanager w/m/d International Presales",
        "festanstellung", "Hamburg")
    assert geschaetzt[0] and geschaetzt[2] == "jaehrlich"


def test_1015_die_schaetzung_nutzt_dasselbe_nadeloehr():
    """Eine zweite Markerliste in `estimate_salary` waere die Bauform
    gewesen, die dieses Projekt sechzehnmal gekostet hat.

    Der Guard gilt fuer den KOERPER von `estimate_salary`, nicht fuer
    die ganze Datei: `job_scraper/__init__.py` fuehrt seit jeher eine
    Synonymliste fuer den Keyword-Abgleich, in der "pflichtpraktikum"
    voellig zu Recht steht. Die erste Fassung dieses Tests hat genau
    daran angeschlagen — ein Guard, der bei korrektem Zustand Alarm
    gibt, wird nach dem zweiten Mal ignoriert (#929).
    """
    import inspect

    from bewerbungs_assistent.job_scraper import estimate_salary

    koerper = inspect.getsource(estimate_salary)
    assert "stellenart" in koerper, "Die Schaetzung fragt das Nadeloehr nicht."
    ohne_kommentar = "\n".join(
        z for z in koerper.split("\n") if not z.strip().startswith("#"))
    # Verboten sind eigene STRING-LITERALE. Ein `_art_modul.WERKSTUDENT`
    # ist die Konstante des Nadeloehrs und damit genau das Richtige —
    # die erste Fassung dieses Guards hat auch daran angeschlagen.
    for marker in ("pflichtpraktikum", "werkstudent", "internship",
                   "praktikum"):
        for literal in (f'"{marker}"', f"'{marker}'"):
            assert literal not in ohne_kommentar.lower(), (
                f"{literal} steht wieder im Rechenweg statt im Nadeloehr.")


def test_1015_die_gehaltskennzahl_liegt_nur_noch_einmal_im_frontend():
    """`buildAnnualSalaryMetrics` lag wortgleich in beiden Seiten.

    Die Doppelung war vorgefunden, nicht angelegt — beim Ergaenzen der
    Schaetz-Zaehlung waere sie um eine dritte Abweichung gewachsen.
    """
    lib = _repo() / "frontend" / "src" / "lib" / "gehaltsKennzahl.js"
    assert lib.exists()
    for seite in ("DashboardPage.jsx", "JobsPage.jsx"):
        jsx = (_repo() / "frontend" / "src" / "pages"
               / seite).read_text(encoding="utf-8")
        assert "@/lib/gehaltsKennzahl" in jsx, f"{seite} importiert nicht."
        assert "function buildAnnualSalaryMetrics" not in jsx, (
            f"{seite} haelt wieder eine eigene Fassung.")


def test_1015_stellentypen_hat_jetzt_einen_filternden_leser():
    """Die Lehre aus #1000, als Guard gedreht.

    Ein Kriterium, das entgegengenommen und gespeichert wird, ohne dass
    es einen Leser hat, ist schlimmer als ein fehlendes — es erzeugt
    falsche Sicherheit. Hier wird geprueft, dass der Leser AUFGERUFEN
    wird, nicht dass er existiert (DoD 8c).
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent"
              / "database.py").read_text(encoding="utf-8")
    assert "stellenart" in quelle and "unerwuenscht(" in quelle
