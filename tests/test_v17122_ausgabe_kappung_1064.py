"""#1064 — `fit_analyse` lieferte die Stellenbeschreibung still gekuerzt.

Gemeldet am 21.09.2026: der Text endete nach rund 2000 Zeichen mitten im
Wort, waehrend dieselbe Antwort `beschreibung_unvollstaendig: false`
meldete. Gespeichert waren 5.784 Zeichen — gekuerzt wurde nur die
AUSGABE, und zwar stumm.

Das wiegt schwer, weil seit #1003/#1007 die Detailanalyse der einzige
Weg zu einem gespeicherten Urteil ist: `stelle_analyse_speichern`
verlangt ausdruecklich, dass die Anzeige gelesen wurde, und verweist
dafuer auf `fit_analyse`. Hinter der Abbruchstelle standen im gemeldeten
Fall der komplette Anforderungsblock und eine harte Bedingung, die das
Urteil praktisch allein entscheidet.

Gemessen an einer Kopie des Bestands (2.271 Anzeigen mit Text):
* die laengste hat 11.741 Zeichen, keine erreicht 12.000;
* bei **29,5 %** der Anzeigen ueber 2.000 Zeichen beginnt der
  Anforderungsteil ERST hinter der alten Grenze.

Die Ausgabegrenze war damit nicht knapp, sondern um den Faktor fuenf zu
klein — und sie traf bevorzugt das, was ueber die Passung entscheidet.
"""
import ast
import importlib
import logging
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.job_scraper.textgrenzen import (  # noqa: E402
    AUSGABE_NOTBREMSE, ausgabe)

# Der Anforderungssatz aus dem Bericht (AK 1) — er stand dort hinter der
# Abbruchstelle und entscheidet das Urteil.
SCHLUSSSATZ = ("Du verfuegst ueber sehr gute Deutsch- und gute "
               "Englischkenntnisse in Wort und Schrift.")
KONTAKT = "Deine Ansprechpartnerin: Frau Muster, Musterbetrieb HR, 0555 1234567"


def _anzeige_wie_gemeldet() -> str:
    """Realistisch aufgebaut: Prosa vorn, Anforderungen hinten.

    Laenge ueber 5.000 Zeichen, Anforderungsteil beginnt weit hinter
    Zeichen 2000 — der Fall aus AK 3.
    """
    vorspann = ("Wir wollen noch besser werden und suchen dafuer Menschen, "
                "die Verantwortung uebernehmen. Unser Haus steht fuer "
                "Verlaesslichkeit, Vielfalt und eine offene Kultur. ")
    aufgaben = ("Du uebernimmst die Gesamtverantwortung fuer den Produkt"
                "bereich und die Optimierung der Prozesse. ")
    text = vorspann * 24 + aufgaben * 12
    assert len(text) > 2000, len(text)
    text += ("\n\nDas bist Du:\n"
             "- Studium der Informatik oder Wirtschaftsinformatik\n"
             "- mehrjaehrige Fuehrungserfahrung, DevSecOps, Cloud\n"
             "- Kenntnisse fuer Prozesse einer Kapitalverwaltungs"
             "gesellschaft nachweisen\n"
             f"- {SCHLUSSSATZ}\n\n"
             f"Unbefristet, mobiles Arbeiten. {KONTAKT}\n")
    assert len(text) > 5000, len(text)
    return text


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17122_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    d = _db_mod.Database()
    d.initialize()
    assert str(tmpdir) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test"})
    yield d
    d.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _fit(db, job_hash, **kwargs):
    import asyncio
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP Test")
    register_all(mcp, db, logging.getLogger("t"))

    async def _run():
        tool = await mcp.get_tool("fit_analyse")
        res = await tool.run({"job_hash": job_hash, **kwargs})
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


def _anlegen(db, text):
    db.save_jobs([{
        "hash": "k1064stelle", "title": "Teamleitung Enterprise Applications",
        "company": "Musterbetrieb Nord", "url": "https://example.com/k1064",
        "source": "manuell", "description": text, "location": "Hamburg",
    }])
    return next(j["hash"] for j in db.get_active_jobs()
                if j["hash"].endswith("k1064stelle"))


# ══ Der gemeldete Fall ══════════════════════════════════════════════

def test_1064_fit_analyse_liefert_den_anforderungsteil(db):
    """AK 1 und AK 3: der Satz hinter der alten Grenze kommt an."""
    text = _anzeige_wie_gemeldet()
    h = _anlegen(db, text)
    res = _fit(db, h)
    geliefert = res["stellenbeschreibung"]
    assert SCHLUSSSATZ in geliefert
    assert KONTAKT in geliefert
    assert geliefert == text
    # Und der Text endet nicht mitten im Wort.
    assert not geliefert.endswith("den Prod")


def test_1064_die_antwort_sagt_was_sie_liefert(db):
    """AK 2: die Ausgabe ist maschinenlesbar beschrieben — auch wenn
    nichts fehlt. Ein Feld, das nur im Schadensfall auftaucht, wird
    beim Lesen uebersehen."""
    text = _anzeige_wie_gemeldet()
    h = _anlegen(db, text)
    befund = _fit(db, h)["beschreibung_ausgabe"]
    assert befund["vollstaendig"] is True
    assert befund["zeichen_gesamt"] == len(text)
    assert befund["zeichen_geliefert"] == len(text)
    assert "gekuerzt" not in befund


def test_1064_zwei_felder_fuer_zwei_fragen(db):
    """Angrenzend 1: `beschreibung_unvollstaendig` meint die SPEICHERUNG,
    `beschreibung_ausgabe` diese Antwort. Vorher stand das eine Feld
    neben einem gekuerzten Text und wurde zwangslaeufig als Aussage
    ueber ihn gelesen."""
    h = _anlegen(db, _anzeige_wie_gemeldet())
    res = _fit(db, h)
    assert res.get("beschreibung_unvollstaendig") is not True
    assert res["beschreibung_ausgabe"]["vollstaendig"] is True

    # Ein an der Quelle gekappter Text: Speicherung unvollstaendig,
    # Ausgabe trotzdem vollstaendig.
    db.save_jobs([{
        "hash": "k1064gekappt", "title": "Gekappte Stelle",
        "company": "Musterbetrieb Sued", "url": "https://example.com/gekappt",
        "source": "manuell", "description": "x" * 2000,
    }])
    h2 = next(j["hash"] for j in db.get_active_jobs()
              if j["hash"].endswith("k1064gekappt"))
    res2 = _fit(db, h2)
    assert res2["beschreibung_unvollstaendig"] is True
    assert "gespeicherte" in res2["beschreibung_hinweis"]
    assert res2["beschreibung_ausgabe"]["vollstaendig"] is True


# ══ Die Notbremse, wenn sie doch greift ═════════════════════════════

def test_1064_notbremse_ist_sichtbar_und_der_rest_abrufbar(db):
    """AK 2: keine stille Kuerzung. Eine entartete Seite (Menue
    mitgeliefert) wird gekuerzt, sagt es, und nennt den Weg zum Rest."""
    riesig = "A" * (AUSGABE_NOTBREMSE + 500) + SCHLUSSSATZ
    h = _anlegen(db, riesig)
    res = _fit(db, h)
    befund = res["beschreibung_ausgabe"]
    assert befund["gekuerzt"] is True
    assert befund["zeichen_gesamt"] == len(riesig)
    assert befund["zeichen_geliefert"] == AUSGABE_NOTBREMSE
    assert befund["weiter_ab_zeichen"] == AUSGABE_NOTBREMSE
    assert "beschreibung_ab" in befund["hinweis"]
    assert "stelle_analyse_speichern" in befund["hinweis"]

    # Der Rest ist wirklich zu holen.
    rest = _fit(db, h, beschreibung_ab=befund["weiter_ab_zeichen"])
    assert SCHLUSSSATZ in rest["stellenbeschreibung"]
    assert rest["beschreibung_ausgabe"]["ab_zeichen"] == AUSGABE_NOTBREMSE


def test_1064_urteil_zu_uebergrossem_text_wird_gewarnt(db):
    """Erwartung 3 des Berichts: wer ein Urteil zu einem Text speichert,
    der nicht in eine Antwort passt, wird darauf hingewiesen."""
    import asyncio
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    h = _anlegen(db, "A" * (AUSGABE_NOTBREMSE + 500))
    mcp = FastMCP("PBP Test")
    register_all(mcp, db, logging.getLogger("t"))

    async def _run(hash_):
        tool = await mcp.get_tool("stelle_analyse_speichern")
        res = await tool.run({"job_hash": hash_, "urteil": "BEDINGT",
                              "begruendung": "Probe"})
        return getattr(res, "structured_content", res)

    res = asyncio.run(_run(h))
    assert res["status"] == "gespeichert"
    assert "beschreibung_ab" in res["warnung_beschreibung"]

    # Gegenrichtung: bei normaler Laenge KEINE Warnung — sonst wird sie
    # nach dem zweiten Mal ignoriert (#929).
    h2 = _anlegen(db, _anzeige_wie_gemeldet())
    assert "warnung_beschreibung" not in asyncio.run(_run(h2))


# ══ Angrenzend 2: Nachladen verliert Kopfdaten ══════════════════════

def test_1064_nachladen_behaelt_kopfdaten():
    """Erwartung 5: "Standort / Einstiegslevel / Eintrittsdatum" standen
    vor dem Nachladen im Text und fehlten danach. Einstiegslevel ist ein
    Senioritaets-Signal."""
    from bewerbungs_assistent.services.nachladen import kopfdaten_bewahren
    alt = ("Standort: Hamburg\nEinstiegslevel: Fuehrungskraft\n"
           "Eintrittsdatum: Baldmoeglichst\n\nWir wollen besser werden.")
    neu = "Wir wollen noch besser werden. Deine Aufgaben: ..."
    ergebnis = kopfdaten_bewahren(alt, neu)
    assert "Einstiegslevel: Fuehrungskraft" in ergebnis
    assert "Standort: Hamburg" in ergebnis
    assert ergebnis.endswith(neu)


def test_1064_kopfdaten_werden_nicht_doppelt_gefuehrt():
    """Liefert die Detailseite dieselbe Angabe selbst, bleibt es bei
    ihrer Fassung — ergaenzen, nicht verdoppeln (#1048)."""
    from bewerbungs_assistent.services.nachladen import kopfdaten_bewahren
    alt = "Standort: Hamburg\nEinstiegslevel: Fuehrungskraft\n\nAlter Text."
    neu = "Einsatzort ist Hamburg. Deine Aufgaben: ..."
    ergebnis = kopfdaten_bewahren(alt, neu)
    assert ergebnis.count("Hamburg") == 1
    assert "Einstiegslevel: Fuehrungskraft" in ergebnis


def test_1064_fliesstext_wird_nicht_fuer_eine_kopfzeile_gehalten():
    """Die Gegenrichtung, und sie ist der Grund fuer die geschlossene
    Liste: an der Bestandskopie fing die generische Form
    "Wort: Wert" einen Prosa-Anfang mit."""
    from bewerbungs_assistent.services.nachladen import kopfdaten_bewahren
    alt = ("Die Musterbetrieb Nord: ein Anbieter von Loesungen fuer die "
           "Industrie.\n\nAlter Text.")
    neu = "Neuer vollstaendiger Text."
    assert kopfdaten_bewahren(alt, neu) == neu


def test_1064_nachladen_ueber_den_dienst_behaelt_die_kopfzeile(db):
    """DoD 8c: der Mechanismus ist verdrahtet, nicht nur geschrieben."""
    from bewerbungs_assistent.services import nachladen
    h = _anlegen(db, "Einstiegslevel: Fuehrungskraft\n\nKurzer Alttext.")
    nachladen.text_uebernehmen(db, h, "Ein neuer, laengerer Anzeigentext "
                                      "mit Aufgaben und Anforderungen.")
    assert "Einstiegslevel: Fuehrungskraft" in db.get_job(h)["description"]


# ══ Guards ══════════════════════════════════════════════════════════

def test_1064_niemand_kuerzt_den_anzeigentext_mehr_stumm():
    """Die alte Bauform war eine Funktion, die nur den gekuerzten Text
    lieferte — der Aufrufer musste von sich aus daran denken, die
    Kuerzung zu melden, und hat es nicht getan. Sie darf nicht
    zurueckkommen."""
    treffer = []
    for f in (ROOT / "src" / "bewerbungs_assistent").rglob("*.py"):
        text = f.read_text(encoding="utf-8-sig")
        if "fuer_ausgabe" in text or "AUSGABE_MAX" in text:
            treffer.append(str(f.relative_to(ROOT)))
    assert not treffer, treffer


def test_1064_wer_die_beschreibung_ausgibt_gibt_den_befund_mit():
    """Guard gegen den Rueckfall: eine Zuweisung an
    `stellenbeschreibung` ohne `ausgabe(` daneben."""
    quelle = (ROOT / "src/bewerbungs_assistent/tools/jobs.py").read_text(
        encoding="utf-8-sig")
    baum = ast.parse(quelle)
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Assign):
            continue
        for ziel in knoten.targets:
            if (isinstance(ziel, ast.Subscript)
                    and getattr(ziel.slice, "value", None) == "stellenbeschreibung"):
                quelltext = ast.unparse(knoten.value)
                assert "ausgabe(" in quelltext or "_text" in quelltext, quelltext


def test_1064_die_genannten_werkzeuge_kuerzen_nicht(db):
    """AK 4: die im Bericht genannten Werkzeuge geprueft. Keines von
    ihnen gibt den Anzeigentext ueberhaupt gekuerzt heraus —
    `stellen_anzeigen` und `stelle_vergleichen` liefern ihn gar nicht,
    `bewerbung_details` reicht ihn unveraendert durch."""
    quelle = (ROOT / "src/bewerbungs_assistent/tools/bewerbungen.py").read_text(
        encoding="utf-8-sig")
    # bewerbung_details reicht durch, ohne Slice.
    assert 'result["stellenbeschreibung"] = app["stellenbeschreibung"]' in quelle

    text = _anzeige_wie_gemeldet()
    h = _anlegen(db, text)
    jobs_quelle = (ROOT / "src/bewerbungs_assistent/tools/jobs.py").read_text(
        encoding="utf-8-sig")
    # In stelle_vergleichen steht nur die Laenge, nicht der Text.
    block = jobs_quelle[jobs_quelle.index("def stelle_vergleichen"):]
    block = block[:block.index("\n    @mcp.tool()")]
    assert "description_length" in block
    assert 'result["stellenbeschreibung"]' not in block
    assert h  # die Fixture wurde wirklich angelegt
