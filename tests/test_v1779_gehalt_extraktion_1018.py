r"""Tests fuer #1018 — der Extraktor las Arbeitszeit als Stundenlohn.

Gemeldet am 11.09.2026. Am Bestand nachgemessen (1.337 Anzeigen mit
Text, Kopie, Original nie angefasst):

| | vorher | nachher |
|---|---|---|
| `stuendlich` | 12 | **4** |
| davon echte Stundensaetze | 2 | 4 |
| `jaehrlich` | 38 | **60** |
| Monatsangaben verworfen | 3 | 0 |

Der lehrreichste Fall trug beides im selben Satz: *"32-40h/Woche, 100%
Remote. Stundensatz: 60 EUR/h."* Genommen wurden die **32-40**.

## Drei eigene Fehler, alle vom Bestand gefunden

Sie stehen hier als Tests, weil jeder davon ohne die Messung
ausgeliefert worden waere:

1. **`p.a.` ohne rechte Wortgrenze trifft jedes "Pa".** "23.800
   Patient:innen" und "100.000 Paletten-Stellplaetze" wurden zu
   Jahresgehaeltern — und zwar ganz ohne Waehrung, womit meine eigene
   Regel aus dem Modulkopf verletzt war.
2. **Die Einheit im Spannen-Muster war optional.** Damit passte
   "900-1100 EUR" gleichzeitig auf Monat, Tag und Stunde, und der erste
   Rang gewann: aus "Tagessatz 900-1100 EUR" wurden 10.800 Euro im Jahr.
3. **Die Arbeitszeit-Pruefung galt fuer JEDE Art.** "Gehalt: 58.000 -
   62.000 Euro, Wochenstunden: 35" wurde deshalb als Arbeitszeit
   verworfen; danach griff das Einzelmuster und ERFAND ein Maximum von
   63.800. Genau der Randbefund des Melders, von mir neu gebaut.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import gehalt_extraktion as ge  # noqa: E402


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


# ----------------------------------------- AK 1: Arbeitszeit ist kein Lohn


@pytest.mark.parametrize("text", [
    "Teilzeit: 30-35 Stunden pro Woche",
    "Wir suchen in Vollzeit (35-38 Stunden pro Woche)",
    "Voll- oder Teilzeit (30-40 Std./Woche)",
    "Eine 38-40 Std.-Woche mit flexibler Arbeitszeit",
    "Availability of 12-20 hours per week",
    "24-40 Stunden",
])
def test_1018_arbeitszeit_ergibt_keine_gehaltsangabe(text):
    """Zehn von zwoelf `stuendlich`-Treffern im Bestand waren das hier."""
    assert ge.extrahieren(text)["art"] is None


@pytest.mark.parametrize("text", [
    "Stundensatz 30-35 Stunden pro Woche",
    "Verguetung: 35-40 Stunden pro Woche",
    "Gehalt 20-25 Stunden pro Woche",
])
def test_1018_rate_wort_allein_macht_aus_stunden_kein_geld(text):
    """Das Rate-Wort-Muster verlangt KEINE Einheit — hier greift die
    Arbeitszeit-Pruefung.

    Gefunden hat die Luecke die Gegenprobe: mit abgeschalteter Pruefung
    blieben zuerst alle Tests gruen. Die Waehrungspflicht deckt die
    gemeldeten Faelle naemlich schon ab, und damit sah die Pruefung nach
    einer Regel aus, die nie greift. Tatsaechlich fehlte der Fall, in
    dem sie greift. **Eine Gegenprobe, die nichts rot macht, ist ein
    Befund ueber die Tests und nicht ueber den Code.**

    Ehrlich dazu: von diesen drei Faellen haelt die Arbeitszeit-Pruefung
    nur den ERSTEN auf. Bei den beiden anderen ist das Rate-Wort ein
    Jahres-Wort, und 35 bis 40 liegt unter der Jahres-Untergrenze von
    20.000 — sie scheitern an der Groessenordnung. Sie stehen trotzdem
    hier, weil das Verhalten in allen drei Faellen dasselbe sein muss.
    """
    assert ge.extrahieren(text)["art"] is None


@pytest.mark.parametrize("text,erwartet", [
    ("Rate discussed: 140-150 EUR/h", (140.0, 150.0)),
    ("50-60 EUR/Stunde", (50.0, 60.0)),
    ("Stundensatz: 60 EUR/h", (60.0, 66.0)),
    ("Rate: 100 EUR/hour (negotiable)", (100.0, 110.0)),
])
def test_1018_echte_stundensaetze_bleiben(text, erwartet):
    """Die Gegenrichtung (#966): eine Verschaerfung, die die echten
    Faelle mitnimmt, ist keine Verbesserung."""
    erg = ge.extrahieren(text)
    assert erg["art"] == "stuendlich"
    assert (erg["min"], round(erg["max"])) == (erwartet[0],
                                               round(erwartet[1]))


# --------------------------------------------------- AK 2: Monatsgehalt


@pytest.mark.parametrize("text,jahr", [
    ("Gehalt: 2.500 EUR pro Monat", 30000.0),
    ("3.750 - 4.050 € / Monat", 45000.0),
    ("8.000 € pro Monat", 96000.0),
    ("4.200 EUR monatlich", 50400.0),
])
def test_1018_monatsgehalt_wird_erkannt_und_umgerechnet(text, jahr):
    """Ein vierter `salary_type` haette an rund zwanzig Stellen einen
    Zweig gebraucht, den man vergessen kann — die Bauform aus #1015."""
    erg = ge.extrahieren(text)
    assert erg["art"] == "jaehrlich"
    assert erg["monat_erkannt"] is True
    assert erg["min"] == jahr


def test_1018_monat_wird_als_herkunft_ausgewiesen():
    """Ohne `monat_erkannt` liesse sich nicht mehr sagen, woher 30.000
    stammen — eine umgerechnete Zahl, die wie eine gelesene aussieht,
    waere #987."""
    assert ge.extrahieren("60.000 EUR p.a.")["monat_erkannt"] is False


# ------------------------------- AK 4: Gehalt schlaegt Arbeitszeit daneben


def test_1018_gehalt_gewinnt_gegen_arbeitszeit_im_selben_satz():
    """Der belegte Fall aus dem Bestand."""
    text = ("Freiberuflich, ab sofort, 6 Monate+, 32-40h/Woche, "
            "100% Remote. Stundensatz: 60 EUR/h.")
    erg = ge.extrahieren(text)
    assert erg["art"] == "stuendlich"
    assert erg["min"] == 60.0


def test_1018_jahresgehalt_neben_wochenstunden():
    """Aus dem Bericht: derselbe Text nennt beides."""
    erg = ge.extrahieren("35-40 h pro Woche. 45.000-60.000 EUR pro Jahr")
    assert (erg["min"], erg["max"], erg["art"]) == (45000.0, 60000.0,
                                                    "jaehrlich")


# --------------------------- AK 5: genannte Spanne schlaegt gerechnete


def test_1018_genannte_spanne_wird_nicht_durch_gerechnete_ersetzt():
    """Randbefund 2 des Melders: "Stundensatz 30-35 EUR" ergab (30, 33),
    weil die Einheit zwischen Praefix und Zahlen steht."""
    erg = ge.extrahieren("Stundensatz 30-35 EUR")
    assert (erg["min"], erg["max"]) == (30.0, 35.0)
    assert erg["gerechnete_spanne"] is False


def test_1018_wochenstunden_verwerfen_nicht_das_jahresgehalt():
    """Mein eigener Fehler Nummer 3, als Test festgehalten."""
    erg = ge.extrahieren(
        "Gehalt: 58.000 - 62.000 Euro, Wochenstunden: 35 Stunden")
    assert (erg["min"], erg["max"]) == (58000.0, 62000.0)
    assert erg["gerechnete_spanne"] is False


def test_1018_einzelwert_darf_eine_spanne_rechnen():
    """Nur dort — und es steht in der Antwort."""
    erg = ge.extrahieren("Gehalt: 95.000 EUR")
    assert erg["min"] == 95000.0
    assert erg["gerechnete_spanne"] is True


# ------------------------------------------- Die drei eigenen Fehler


@pytest.mark.parametrize("text", [
    "Jaehrlich lassen sich rund 23.800 Patient:innen behandeln",
    "Logistikzentrum mit 100.000 Paletten- und 180.000 Behaelterplaetzen",
    "Fast 30.000 Patient:innen im Jahr, 9 Spezialkliniken",
])
def test_1018_pa_ohne_wortgrenze_ist_kein_jahresgehalt(text):
    """Eigener Fehler 1 — vierter Fall nach "ki" in "Kita" (#970), "us"
    in "Kundenservice" (#996), "intern" in "International" (#1015)."""
    assert ge.extrahieren(text)["art"] is None


def test_1018_ohne_waehrung_kein_gehalt():
    """Die Regel aus dem Modulkopf, als Test — sonst steht sie nur da.

    Eine blosse Zeitangabe belegt kein Geld; ohne Waehrungszeichen
    genuegt nur ein Geld-Wort.
    """
    assert ge.extrahieren("40.000 pro Jahr")["art"] is None
    assert ge.extrahieren("40.000 EUR pro Jahr")["art"] == "jaehrlich"
    assert ge.extrahieren("40.000 brutto")["art"] == "jaehrlich"


def test_1018_die_einheit_ist_pflicht_ausser_beim_jahresgehalt():
    """Eigener Fehler 2: aus "Tagessatz 900-1100 EUR" wurden 10.800
    Euro im Jahr, weil "Zahl-Zahl EUR" auf jede Art passte."""
    erg = ge.extrahieren("Tagessatz 900-1100 EUR")
    assert (erg["min"], erg["max"], erg["art"]) == (900.0, 1100.0,
                                                    "taeglich")
    # Ohne Einheit bleibt es ohne Befund — ausser die Groessenordnung
    # macht das Jahresgehalt eindeutig.
    assert ge.extrahieren("900-1100 EUR")["art"] is None
    assert ge.extrahieren("60.000-80.000 EUR")["art"] == "jaehrlich"


def test_1018_vierstellige_zahl_ohne_tausenderpunkt():
    """Auch eigener Fehler: `\\d{1,3}` las aus "1100" die "110"."""
    erg = ge.extrahieren("Tagessatz 900-1100 EUR")
    assert erg["max"] == 1100.0


# ------------------------------------------------ Markdown-Escapes


def test_1018_markdown_escapes_verdecken_gehaelter():
    """348 der 1.337 Beschreibungen im Bestand tragen sie.

    Ohne Entschaerfung findet kein Zahlenmuster mehr etwas — vier echte
    Jahresgehaelter gingen bis hierher verloren. Stand in keinem
    Bericht; gefunden hat es die Messung.
    """
    erg = ge.extrahieren(r"Hamburg 43\.933 \- 52\.962 € / Jahr")
    assert (erg["min"], erg["max"], erg["art"]) == (43933.0, 52962.0,
                                                    "jaehrlich")


# --------------------------------------------- AK 6: min > max nie


@pytest.mark.parametrize("ein,aus", [
    ((75, 30), (30, 75)),
    ((30, 75), (30, 75)),
    ((None, 5), (None, 5)),
    ((5, None), (5, None)),
])
def test_1018_min_groesser_max_wird_gedreht(ein, aus):
    assert ge.gesund(*ein) == aus


def test_1018_der_riegel_sitzt_am_speicherweg(db):
    """Nicht in der Erkennung: die Werte koennen auch aus einer Quelle
    kommen, und eine Regel in einem von zwei Schreibwegen verschiebt
    die Divergenz bloss (#963)."""
    db.save_jobs([{
        "hash": "ak6", "title": "Test-Rolle", "company": "Beispiel GmbH",
        "url": "https://example.com/1018/ak6",
        "source": "manuell", "description": "Text. " * 20,
        "salary_min": 75.0, "salary_max": 30.0, "salary_type": "stuendlich",
        "score": 5, "_manual_entry": True,
    }])
    voll = db.resolve_job_hash("ak6")
    row = db.connect().execute(
        "SELECT salary_min, salary_max FROM jobs WHERE hash=?",
        (voll,)).fetchone()
    assert row[0] <= row[1], f"min {row[0]} > max {row[1]} gespeichert"


# ------------------------------------- AK 3: strukturierte BA-Felder


def test_1018_ba_strukturierte_felder_schlagen_die_regex():
    from bewerbungs_assistent.job_scraper.bundesagentur import _ba_gehalt

    erg = _ba_gehalt({"verguetungsangabe": "JAHRESGEHALT",
                      "artDerVerguetung": "GEHALTSSPANNE",
                      "gehaltsspanneVon": 30000.0,
                      "gehaltsspanneBis": 42000.0})
    assert erg == {"salary_min": 30000.0, "salary_max": 42000.0,
                   "salary_type": "jaehrlich", "salary_estimated": 0}


def test_1018_ba_monatsgehalt_wird_umgerechnet():
    from bewerbungs_assistent.job_scraper.bundesagentur import _ba_gehalt

    erg = _ba_gehalt({"verguetungsangabe": "MONATSGEHALT",
                      "gehaltsspanneVon": 2500.0, "gehaltsspanneBis": 3000.0})
    assert erg["salary_type"] == "jaehrlich"
    assert erg["salary_min"] == 30000.0


@pytest.mark.parametrize("data", [
    {},
    {"verguetungsangabe": "JAHRESGEHALT"},
    {"gehaltsspanneVon": 30000.0},
    {"verguetungsangabe": "UNSINN", "gehaltsspanneVon": 30000.0},
    {"verguetungsangabe": "JAHRESGEHALT", "gehaltsspanneVon": 12.0},
])
def test_1018_ba_ohne_brauchbare_felder_bleibt_es_beim_fliesstext(data):
    """Fehlt die strukturierte Angabe, aendert sich gar nichts — das
    Verhalten von vorher ist der Rueckfall, nicht ein Fehler."""
    from bewerbungs_assistent.job_scraper.bundesagentur import _ba_gehalt

    assert _ba_gehalt(data) == {}


def test_1018_ba_holt_das_gehalt_aus_derselben_antwort():
    """Ein zweiter Abruf je Stelle waere #1014 MERKE 3 woertlich.

    Geprueft wird die Signatur: `_fetch_ba_detail` nimmt ein
    Ausgabe-Dict entgegen, statt dass jemand die Detail-API ein zweites
    Mal fragt.
    """
    import inspect

    from bewerbungs_assistent.job_scraper import bundesagentur

    sig = inspect.signature(bundesagentur._fetch_ba_detail)
    assert "gehalt_raus" in sig.parameters
    quelle = inspect.getsource(bundesagentur.search_bundesagentur)
    assert quelle.count("_fetch_ba_detail") == 1, (
        "Die Detail-API wird mehr als einmal je Stelle gefragt.")


# ------------------------------------------------------------ Guards


def test_1018_die_alten_muster_sind_weg():
    """`SALARY_PATTERNS` und `_normalize_salary` haben keinen Aufrufer
    mehr. Sie stehen zu lassen waere ein Muster ohne Leser gewesen —
    davon hat dieses Projekt genug gefunden (#993, #1000, #1008)."""
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "job_scraper"
              / "__init__.py").read_text(encoding="utf-8")
    ohne_kommentar = "\n".join(
        z for z in quelle.split("\n") if not z.strip().startswith("#"))
    assert "SALARY_PATTERNS" not in ohne_kommentar
    assert "_normalize_salary" not in ohne_kommentar


def test_1018_extract_salary_from_text_ruft_das_nadeloehr():
    """DoD 8c: geschrieben ist nicht aufgerufen. Die Funktion behaelt
    ihren Namen, weil zahlreiche Aufrufer ihr Tupel entpacken."""
    import inspect

    from bewerbungs_assistent.job_scraper import extract_salary_from_text

    assert "gehalt_extraktion" in inspect.getsource(extract_salary_from_text)
    assert extract_salary_from_text("60.000-80.000 EUR brutto") == (
        60000.0, 80000.0, "jaehrlich")


def test_1018_extrahieren_liefert_immer_ein_dict():
    for text in ("", None, "kein Gehalt hier", "abc", "€"):
        erg = ge.extrahieren(text)
        assert isinstance(erg, dict)
        assert erg["art"] in (None, "jaehrlich", "taeglich", "stuendlich")
        if erg["art"] is None:
            assert erg["grund"], "Ein leeres Ergebnis ohne Begruendung"


def test_1018_beide_module_existieren_nebeneinander():
    """DoD 8d: `gehalt_extraktion` liest, `gehalt_vergleich` vergleicht.
    Zwei aehnliche Namen brauchen eine Abgrenzung im Kopf und einen
    Test, der beide festhaelt (Lehre aus #799 und v1.7.74)."""
    dienste = _repo() / "src" / "bewerbungs_assistent" / "services"
    for name in ("gehalt_extraktion.py", "gehalt_vergleich.py"):
        assert (dienste / name).exists(), name
    kopf = (dienste / "gehalt_extraktion.py").read_text(encoding="utf-8")[:2000]
    assert "gehalt_vergleich" in kopf, "Die Abgrenzung fehlt im Modulkopf."


# ------------------------------------------- AK 7: Bestandskorrektur


def test_1018_bestand_laesst_sich_neu_auswerten(db):
    """Ein besserer Leser hilft nur neuen Stellen (#998).

    Die Stelle traegt einen Wert aus der alten, kaputten Erkennung:
    30 bis 35 Euro die Stunde, aus "30-35 Stunden pro Woche", und als
    BELEGT gefuehrt.
    """
    from bewerbungs_assistent.tools.jobs import register as _register

    db.save_jobs([{
        "hash": "ak7", "title": "Sachbearbeiter (m/w/d)",
        "company": "Beispiel GmbH", "url": "https://example.com/1018/ak7",
        "source": "manuell", "_manual_entry": True, "score": 5,
        "description": ("Wir suchen in Teilzeit: 30-35 Stunden pro Woche "
                        "eine Unterstuetzung. " + "Text. " * 20),
        "salary_min": 30.0, "salary_max": 35.0,
        "salary_type": "stuendlich", "salary_estimated": 0,
    }])

    import asyncio

    from fastmcp import FastMCP

    import logging

    mcp = FastMCP("test")
    _register(mcp, db, logging.getLogger("test"))

    async def _lauf(args):
        werkzeug = await mcp.get_tool("gehaelter_neu_auswerten")
        res = await werkzeug.run(args)
        return getattr(res, "structured_content", res)

    vorschau = asyncio.run(_lauf({"dry_run": True}))
    assert vorschau["status"] == "vorschau"
    assert vorschau["geaendert"] >= 1

    voll = db.resolve_job_hash("ak7")
    vorher = db.connect().execute(
        "SELECT salary_min FROM jobs WHERE hash=?", (voll,)).fetchone()[0]
    assert vorher == 30.0, "Die Vorschau hat geschrieben."

    asyncio.run(_lauf({"dry_run": False}))
    nachher = db.connect().execute(
        "SELECT salary_min, salary_type FROM jobs WHERE hash=?",
        (voll,)).fetchone()
    assert nachher[0] is None, (
        "Die Arbeitszeit steht weiterhin als Gehalt in der Datenbank.")
