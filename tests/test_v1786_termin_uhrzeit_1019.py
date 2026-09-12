"""Tests fuer #1019 — die Uhrzeit kommt aus dem Text, nicht aus dem Kopf.

## Der gemeldete Fall

Eine Interview-Einladung aus dem Produktivbestand:

| | |
|---|---|
| Mail-Kopf | `Datum: 2026-09-10T14:43:25` |
| Einladungstext | "… folgenden Termin vor: Mittwoch, 30.09.2026 um 11:00 Uhr" |
| `moegliches_datum` | `30.09.2026` — richtig |
| `moegliche_uhrzeit` | **`43:25`** — aus dem Sendezeitstempel |

Die Ursache ist eine Wortgrenze: `\\b` oeffnet auch HINTER einem
Doppelpunkt, also setzte `\\b\\d{1,2}:\\d{2}` mitten in `14:43:25` neu
an. `43:25` ist keine Tageszeit und hat das Extraktionsergebnis
trotzdem verlassen.

## Warum das teuer ist

Der Routing-Plan schlaegt zu solchen Dokumenten `termin_anlegen` mit
genau diesen Argumenten vor. **Ein Gespraechstermin mit falscher
Uhrzeit ist teurer als ein fehlender, weil ihn niemand nachprueft.**

## Am Bestand gemessen (Kopie, 12.09.2026)

**Drei von drei** Interview-Einladungen trugen eine Uhrzeit aus dem
Mail-Kopf, keine davon eine gueltige Tageszeit — und in allen drei
Faellen stand die richtige Uhrzeit im Text:

| Dokument | vorher | nachher |
|---|---|---|
| 1 | `'43:47\\n'` | `15:00` |
| 2 | `'51:33\\n'` | `14:00` |
| 3 | `'43:25'` | `11:00` |

Die Datumserkennung bleibt in allen drei Faellen identisch (AK 5), und
ueber alle 238 Dokumente des Bestands laeuft `handle_doc` fehlerfrei
durch.

Nebenbefund aus derselben Messung: zwei der drei alten Werte trugen
einen **Zeilenumbruch**, die neuen Treffer im Rohzustand ein "Uhr".
Der Wert wandert als Argument in `termin_anlegen` — er wird deshalb
auf `HH:MM` normalisiert.

## Zwei Riegel, und sie sind nicht redundant

Das ist der Punkt, an dem die Gegenprobe etwas belegt:

1. **Der Kopfblock faellt weg.** Noetig, weil die Pruefung allein NICHT
   genuegt: aus `Datum: …T09:15:30` liest dieselbe Mechanik `09:15` —
   eine voellig gueltige Uhrzeit, die trotzdem der Sendezeitpunkt ist.
2. **Die Zeit wird geprueft.** Noetig, weil der Text selbst Unsinn
   enthalten kann und `43:25` nie herauskommen darf.
"""
import importlib
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import document_handlers as dh  # noqa: E402

# Der gemeldete Fall, woertlich nachgebaut.
MELDEFALL = """Betreff: Einladung zum Gespraech
Von: recruiting@example.com
An: bewerber@example.com
Datum: 2026-09-10T14:43:25

Hallo,

wir wuerden gerne ein Gespraech mit Dir fuehren. Hierfuer schlagen wir
folgenden Termin vor: Mittwoch, 30.09.2026 um 11:00 Uhr.

Viele Gruesse
"""

OHNE_UHRZEIT = """Betreff: Einladung zum Gespraech
Von: recruiting@example.com
Datum: 2026-09-10T14:43:25

Wir schlagen den 30.09.2026 vor. Die Uhrzeit stimmen wir noch ab.
"""


# --------------------------------------- AK 1: nur aus dem Nachrichtentext


def test_der_meldefall_liefert_die_uhrzeit_aus_dem_text():
    """Der Bericht, eins zu eins."""
    felder = dh._extract_interview_einladung({"extracted_text": MELDEFALL})
    assert felder["moegliches_datum"] == "30.09.2026"
    assert felder["moegliche_uhrzeit"] == "11:00"


def test_der_kopfblock_faellt_weg():
    """AK 1."""
    rumpf = dh.nachrichtentext(MELDEFALL)
    for kopf in ("Betreff:", "Von:", "An:", "Datum:", "14:43:25"):
        assert kopf not in rumpf, f"{kopf} steht noch im Rumpf"
    assert "30.09.2026 um 11:00 Uhr" in rumpf


def test_eine_gueltige_uhrzeit_im_kopf_wird_trotzdem_nicht_genommen():
    """**Der Fall, der den Kopf-Riegel noetig macht.**

    Die Plausibilitaetspruefung allein wuerde hier nichts merken:
    `09:15` aus `…T09:15:30` ist eine einwandfreie Tageszeit. Sie ist
    nur der Sendezeitpunkt und nicht der Termin — der Fehler waere
    still.
    """
    text = ("Betreff: Einladung\nDatum: 2026-09-10T09:15:30\n\n"
            "Wir schlagen den 30.09.2026 um 16:30 Uhr vor.")
    felder = dh._extract_interview_einladung({"extracted_text": text})
    assert felder["moegliche_uhrzeit"] == "16:30"


def test_ein_zitierter_thread_liefert_keine_uhrzeit():
    """Gemeinsame Wurzel mit #922.

    Dort entstanden Phantom-Termine aus zitierten Sendezeiten. Hier
    genuegt derselbe Riegel — und zwar ueber `strip_quoted_reply` aus
    #922, nicht ueber eine zweite Fassung davon.
    """
    text = ("Betreff: Re: Einladung\nDatum: 2026-09-10T08:00:00\n\n"
            "Passt uns leider nicht.\n\n"
            "-----Urspruengliche Nachricht-----\n"
            "Gesendet: 09.09.2026 17:45\n"
            "Wir schlagen den 30.09.2026 um 11:00 Uhr vor.")
    felder = dh._extract_interview_einladung({"extracted_text": text})
    assert felder["moegliche_uhrzeit"] is None
    assert felder["moegliches_datum"] is None


def test_das_zitat_wird_nicht_neu_erkannt():
    """Ein Nadeloehr statt einer zweiten Fassung."""
    import inspect
    quelle = inspect.getsource(dh.nachrichtentext)
    assert "strip_quoted_reply" in quelle


def test_ohne_kopfzeilen_bleibt_der_text_unveraendert():
    """Derselbe Extraktor sieht auch Dokumente, die nie eine Mail waren.

    Ein PDF oder DOCX hat keinen Kopfblock — es darf ihm auch keiner
    abgeschnitten werden.
    """
    text = ("Einladung zum Vorstellungsgespraech\n\n"
            "Termin: 30.09.2026 um 11:00 Uhr")
    assert dh.nachrichtentext(text) == text
    felder = dh._extract_interview_einladung({"extracted_text": text})
    assert felder["moegliche_uhrzeit"] == "11:00"


def test_ein_doppelpunkt_im_fliesstext_beendet_den_kopf_nicht():
    """Die Kopf-Erkennung ist eine Liste bekannter Feldnamen.

    "Termin:" oder "Ort:" mitten im Text sind keine Kopfzeilen — eine
    Regel "alles vor dem ersten Doppelpunkt" haette den halben Text
    weggeworfen.
    """
    text = "Guten Tag,\n\nTermin: 30.09.2026 um 11:00 Uhr\nOrt: Hamburg"
    assert dh.nachrichtentext(text) == text


# ------------------------------------------ AK 2: Plausibilitaetspruefung


@pytest.mark.parametrize("roh,erwartet", [
    ("11:00", "11:00"),
    ("9:30", "09:30"),
    ("00:00", "00:00"),
    ("23:59", "23:59"),
    ("24:00", None),
    ("43:25", None),
    ("51:33", None),
    ("12:60", None),
    ("99:99", None),
])
def test_nur_gueltige_tageszeiten_verlassen_die_extraktion(roh, erwartet):
    """AK 2.

    Verworfen statt korrigiert: bei `43:25` weiss niemand, was gemeint
    war. Ein Ersatzwert waere eine erfundene Angabe (#1006, #989).
    """
    assert dh.uhrzeit_aus_text(f"Termin am 30.09.2026 um {roh} Uhr") == erwartet


def test_die_ungueltige_zeit_verdeckt_keine_gueltige():
    """Gesucht wird weiter, nicht abgebrochen.

    Sonst haette ein Unsinnstreffer weiter vorn die richtige Angabe
    dahinter verschluckt — und das Ergebnis waere leer statt richtig.
    """
    assert dh.uhrzeit_aus_text(
        "Ref 43:25 — Termin 30.09.2026 um 11:00 Uhr") == "11:00"


def test_ein_datum_wird_nicht_als_uhrzeit_gelesen():
    """Der Grund, aus dem das alte Muster ":" verlangte (Alt-Entscheid).

    `19.05.2026` darf keine Uhrzeit ergeben. Die Rueckschau darf diese
    Eigenschaft nicht verlieren.
    """
    assert dh.uhrzeit_aus_text("Bewerbung vom 19.05.2026") is None
    assert dh.uhrzeit_aus_text("Datum 30.09.2026, Ort Hamburg") is None


def test_die_vierstellige_form_braucht_weiter_ihren_nachsatz():
    """Ebenfalls Alt-Verhalten: "1300 Uhr" ja, "1300 Bewerber" nein."""
    assert dh.uhrzeit_aus_text("Beginn 1300 Uhr") == "13:00"
    assert dh.uhrzeit_aus_text("Wir haben 1300 Bewerber") is None
    assert dh.uhrzeit_aus_text("Beginn 2500 Uhr") is None


# ------------------------------------------------- Normalisierung


@pytest.mark.parametrize("text,erwartet", [
    ("um 11:00 Uhr", "11:00"),
    ("um 11:00 Uhr\n", "11:00"),
    ("9:05 am", "09:05"),
    ("14:00 CEST", "14:00"),
    ("11:00:00", "11:00"),
])
def test_die_uhrzeit_kommt_in_maschinenform_heraus(text, erwartet):
    """Der Wert wandert als Argument in `termin_anlegen`.

    Am Bestand gemessen kam er bis v1.7.85 roh heraus — zweimal samt
    Zeilenumbruch, zweimal samt "Uhr".
    """
    assert dh.uhrzeit_aus_text(text) == erwartet


# ----------------------------------- AK 3: Luecke benennen statt fuellen


def test_ohne_uhrzeit_bleibt_das_feld_leer_und_wird_benannt():
    """AK 3."""
    felder = dh._extract_interview_einladung({"extracted_text": OHNE_UHRZEIT})
    assert felder["moegliches_datum"] == "30.09.2026"
    assert felder["moegliche_uhrzeit"] is None
    assert felder["uhrzeit_fehlt"] is True


def test_ohne_datum_gibt_es_auch_nichts_zu_beklagen():
    """`uhrzeit_fehlt` meint "Datum da, Uhrzeit nicht".

    Ein Dokument ohne beides ist keine Terminangabe, und ein Hinweis
    dazu waere Rauschen — ein Pruefer, der bei korrektem Zustand Alarm
    gibt, wird nach dem zweiten Mal ignoriert (#929).
    """
    felder = dh._extract_interview_einladung(
        {"extracted_text": "Betreff: Hallo\nDatum: 2026-09-10T14:43:25\n\n"
                           "Wir melden uns."})
    assert felder["uhrzeit_fehlt"] is False


# ----------------------------------------- AK 3: der Hinweis im Plan


def _plan(db):
    import asyncio
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools.dokumente import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("dokumente_routing_plan_erstellen")
        res = await tool.run({})
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "test.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.switch_profile(datenbank.create_profile("Termine"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _dokument(db, text, name="einladung.eml"):
    doc_id = db.add_document({
        "filename": name, "file_path": f"/tmp/{name}",
        "doc_type": "interview_einladung", "extracted_text": text,
        "extraction_status": "analysiert",
    })
    return doc_id


def test_der_routing_plan_nennt_die_fehlende_uhrzeit(db):
    """AK 3, zweite Haelfte — die Luecke muss im Plan ankommen.

    Ein Feld, das nur der Extraktor kennt, ist fuer den Menschen
    unsichtbar (#989 MERKE 1: ein Befund, den nur ein Werkzeug kennt,
    ist kein Befund).
    """
    _dokument(db, OHNE_UHRZEIT, "ohne_zeit.eml")
    _dokument(db, MELDEFALL, "mit_zeit.eml")

    plan = _plan(db)
    gruppe = next(a for a in plan["aktionen"] if a["aktion"] == "termin_anlegen")
    assert gruppe["anzahl"] == 2
    assert gruppe["ohne_uhrzeit"] == 1
    assert "ohne Uhrzeit im Text" in gruppe["naechster_aufruf_hinweis"]

    nach_name = {d["filename"]: d for d in gruppe["dokumente"]}
    assert "hinweis" in nach_name["ohne_zeit.eml"]
    assert "nach" in nach_name["ohne_zeit.eml"]["hinweis"].lower()
    assert "hinweis" not in nach_name["mit_zeit.eml"]


def test_der_plan_liefert_die_richtige_uhrzeit_bis_nach_vorn(db):
    """Die ganze Kette, nicht nur der Extraktor.

    Der Bericht beschreibt den Defekt am Ergebnis von
    `dokumente_routing_plan_erstellen` — dort gehoert er auch geprueft.
    """
    _dokument(db, MELDEFALL)
    plan = _plan(db)
    gruppe = next(a for a in plan["aktionen"] if a["aktion"] == "termin_anlegen")
    felder = gruppe["dokumente"][0]["extrahierte_felder"]
    assert felder["moegliche_uhrzeit"] == "11:00"
    assert felder["moegliches_datum"] == "30.09.2026"


def test_ein_plan_ohne_termindokumente_traegt_keinen_hinweis(db):
    """Die Gegenrichtung — sonst steht der Zusatz irgendwann ueberall."""
    db.add_document({
        "filename": "lebenslauf.pdf", "file_path": "/tmp/lebenslauf.pdf",
        "doc_type": "lebenslauf", "extracted_text": "Lebenslauf",
        "extraction_status": "analysiert",
    })
    plan = _plan(db)
    for gruppe in plan["aktionen"]:
        assert "ohne_uhrzeit" not in gruppe
        assert "ohne Uhrzeit im Text" not in gruppe["naechster_aufruf_hinweis"]


# ------------------------------------- AK 5: die Datumserkennung bleibt


@pytest.mark.parametrize("text,erwartet", [
    ("Termin am 30.09.2026", "30.09.2026"),
    ("Termin am 2026-09-30", "2026-09-30"),
    ("Termin am 30. September 2026", None),
    ("Termin am 30 Sep 2026", "30 Sep 2026"),
    ("Kein Datum hier", None),
])
def test_die_datumserkennung_ist_unveraendert(text, erwartet):
    """AK 5.

    Am Bestand gegengeprueft: drei von drei Dokumenten liefern
    dasselbe Datum wie vorher. Der Fall "30. September 2026" ist
    bewusst mit `None` erfasst — das konnte das Muster vorher auch
    nicht, und eine Erweiterung waere eine andere Arbeit als diese
    Fehlerbehebung.
    """
    treffer = dh._DATE_RE.findall(text)
    assert (treffer[0] if treffer else None) == erwartet


@pytest.mark.parametrize("kopfzeile", [
    "Datum: 10.09.2026",
    "Datum: 2026-09-10 14:43:25",
    "Gesendet: 2026-09-10 14:43:25",
])
def test_das_datum_kommt_ebenfalls_aus_dem_text(kopfzeile):
    """Die Regel gilt fuer BEIDE Felder — und das ist kein Zierrat.

    Beim Melder war das Datum richtig, aber nur um ein Zeichen. Sein
    Kopf lautet `Datum: 2026-09-10T14:43:25`, und daran scheitert das
    Datums-Muster: hinter der `10` steht ein `T`, also greift die
    Wortgrenze nicht. Nachgemessen:

        'Datum: 2026-09-10T14:43:25'  ->  []
        'Datum: 2026-09-10 14:43:25'  ->  ['2026-09-10']
        'Datum: 10.09.2026'           ->  ['10.09.2026']

    Ein Kopf mit Leerzeichen statt `T` — die uebliche Form vieler
    Mailprogramme — haette also das SENDEDATUM als Termindatum
    geliefert. Der Bericht nennt nur die Uhrzeit; das Datum lag
    daneben und war durch einen Zufall gedeckt.
    """
    text = (f"Betreff: Einladung\n{kopfzeile}\n\n"
            "Wir schlagen den 30.09.2026 um 11:00 Uhr vor.")
    felder = dh._extract_interview_einladung({"extracted_text": text})
    assert felder["moegliches_datum"] == "30.09.2026"
    assert felder["moegliche_uhrzeit"] == "11:00"


def test_die_bestaetigung_nutzt_denselben_extraktor():
    """`interview_bestaetigung` teilt sich die Felder mit der Einladung.

    Zwei Fassungen waeren das Muster, das dieses Projekt siebzehnmal
    gekostet hat.
    """
    doc = {"extracted_text": MELDEFALL}
    assert (dh._extract_interview_bestaetigung(doc)
            == dh._extract_interview_einladung(doc))
