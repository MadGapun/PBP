"""Tests fuer #1016 — der Mengenweg deckte den haeufigen Fall nicht ab.

## Der gemeldete Widerspruch

`beschreibungen_nachladen_bestand` traegt den Namen fuer den
Mengenweg und antwortete:

    {"status": "nichts_zu_tun", "geprueft": 984,
     "hinweis": "Kein aktiver Anzeigentext ist exakt 2000 Zeichen
                 lang — es sieht nichts nach der alten Kappung aus."}

**Waehrend 370 aktive Stellen ohne jeden Anzeigentext danebenstanden.**

Die Auswahlregel war `ist_gekappt(text)`, also `len(text) == 2000` —
gebaut fuer den Altbestand aus #952 ("Text da, aber halb"). Eine
Stelle GANZ OHNE Text hat `len 0` und fiel durch das Raster. Nach dem
#952-Nachzug ist der urspruengliche Anlass erledigt, der haeufigere
Fall blieb unbedient.

## Am Bestand gemessen (Kopie, 12.09.2026)

Ueber alle 2.578 Stellen:

| | |
|---|---:|
| ohne brauchbaren Text | **1.198 (46,5 %)** |
| davon `description IS NULL` | 549 |
| davon ein Stummel von 13-46 Zeichen | **649** |
| exakt 2.000 Zeichen (gekappt, #952) | 800 |
| ohne brauchbare URL | 6 |

**Eine Pruefung auf NULL allein haette mehr als die Haelfte
uebersehen.** Deshalb die Laengenbedingung aus dem Auto-Refetch
(`< MIN_BESCHREIBUNG`) und nicht `IS NULL`.

Und: der Melder mass in seinem Bestand 0 gekappte Stellen, hier sind
es 800. Beide Faelle existieren, also loest ein Parameter das besser
als ein Austausch der Regel.
"""
import asyncio
import importlib
import logging
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database(db_path=tmp_path / "test.db")
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.switch_profile(datenbank.create_profile("Nachladen"))
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _mcp(db):
    from fastmcp import FastMCP

    from bewerbungs_assistent.tools.jobs import register
    mcp = FastMCP("test")
    register(mcp, db, logging.getLogger("test"))
    return mcp


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


def _stelle(db, hash_, text, url="https://example.com/1016/x"):
    db.save_jobs([{
        "hash": hash_, "title": f"Stelle {hash_}", "company": "Firma",
        "url": url, "source": "bundesagentur",
        "description": text, "score": 5,
    }])


def _bestand(db):
    """Je ein Fall: ohne Text, Stummel, gekappt, vollstaendig."""
    _stelle(db, "leer", "", "https://example.com/1016/leer")
    _stelle(db, "stummel", "Siehe Anzeige.", "https://example.com/1016/st")
    _stelle(db, "gekappt", "X" * 2000, "https://example.com/1016/ge")
    _stelle(db, "voll", "Y" * 3000, "https://example.com/1016/vo")


# ------------------------------------------------- AK 1: die Zaehlung


def test_ein_aufruf_ohne_argumente_meldet_die_stellen_ohne_beschreibung(db):
    """AK 1 — und die Umkehr der Vorgabe.

    Bis v1.7.86 war `gekappt` die einzige Regel. Wer das Werkzeug ohne
    Argumente rief, bekam fuer einen Bestand voller textloser Stellen
    "nichts zu tun".
    """
    _bestand(db)
    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand", {})
    assert erg["status"] == "vorschau"
    assert erg["umfang"] == "fehlend"
    assert erg["betroffen"] == 2, erg
    assert erg["gefunden"] == {"ohne_text": 2, "gekappt": 1}


def test_ein_stummel_zaehlt_als_fehlend(db):
    """Der gemessene Kern: 649 von 1.198 textlosen Stellen sind NICHT
    NULL, sondern tragen 13 bis 46 Zeichen.

    Eine Pruefung auf NULL haette mehr als die Haelfte uebersehen.
    """
    _stelle(db, "stummel", "Siehe Anzeige.")
    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand", {})
    assert erg["betroffen"] == 1
    assert erg["beispiele"][0]["zeichen"] == len("Siehe Anzeige.")


def test_die_schwelle_kommt_aus_dem_nadeloehr():
    """`MIN_BESCHREIBUNG` lag bis #989 siebenmal als Zahl 50 im Code.

    Sie hier erneut zu tippen waere der achte Fall.
    """
    import inspect

    from bewerbungs_assistent.tools import jobs
    quelle = inspect.getsource(jobs.register)
    i = quelle.index("def beschreibungen_nachladen_bestand")
    block = quelle[i:i + 6000]
    assert "MIN_BESCHREIBUNG" in block
    assert "< 50" not in block and "<50" not in block


# ------------------------------------------- AK 4: der Altfall bleibt


def test_der_alte_zweck_ist_ueber_denselben_aufruf_erreichbar(db):
    """AK 4 — #952 bleibt bedient, nur nicht mehr als einzige Regel."""
    _bestand(db)
    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"umfang": "gekappt"})
    assert erg["betroffen"] == 1
    assert erg["beispiele"][0]["zeichen"] == 2000


def test_beide_umfaenge_lassen_sich_zusammen_holen(db):
    _bestand(db)
    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"umfang": "beide"})
    assert erg["betroffen"] == 3


def test_die_beiden_faelle_ueberschneiden_sich_nicht(db):
    """`beide` darf keine Stelle doppelt zaehlen.

    Heute schliessen sich 2000 und "unter 50" aus; der Test haelt das
    fest, damit es beim naechsten Schwellenwert auffaellt.
    """
    _bestand(db)
    einzeln = sum(
        _call(_mcp(db), "beschreibungen_nachladen_bestand",
              {"umfang": u})["betroffen"]
        for u in ("fehlend", "gekappt"))
    zusammen = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                     {"umfang": "beide"})["betroffen"]
    assert einzeln == zusammen == 3


def test_ein_unbekannter_umfang_wird_abgewiesen(db):
    """Still auf die Vorgabe zu fallen waere #988: eine Auswahl, der man
    glaubt, die aber etwas anderes tut."""
    _bestand(db)
    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"umfang": "halb"})
    assert erg["status"] == "fehler"
    assert "halb" in erg["grund"]


# --------------------------------- Die Entwarnung nennt den anderen Fall


def test_nichts_zu_tun_sagt_was_der_andere_umfang_faende(db):
    """Die eigentliche Lehre des Berichts.

    Der alte Satz war RICHTIG ("nichts sieht nach der alten Kappung
    aus") und trotzdem irrefuehrend, weil daneben 370 Stellen ohne
    Text lagen. **Eine Entwarnung, die nur fuer einen Teil gilt, muss
    sagen fuer welchen.**
    """
    _stelle(db, "leer", "")
    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"umfang": "gekappt"})
    assert erg["status"] == "nichts_zu_tun"
    assert erg["gefunden"]["ohne_text"] == 1
    assert "fehlend" in erg["hinweis"]
    assert "1" in erg["hinweis"]


def test_ohne_jeden_befund_bleibt_der_hinweis_schlicht(db):
    """Die Gegenrichtung — sonst verweist die Entwarnung auf eine
    leere Menge und wird zum Rauschen (#929)."""
    _stelle(db, "voll", "Y" * 3000)
    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand", {})
    assert erg["status"] == "nichts_zu_tun"
    assert "gekappt" not in erg["hinweis"]


# ------------------------------- AK 2+3: der Lauf und die vier Befunde


class _Befund:
    """Nachbau von `services.nachladen.Befund` fuer den Testdoppel."""

    def __init__(self, status, text="", http_status=None):
        self.status = status
        self.text = text
        self.http_status = http_status

    @property
    def soll_aussortiert_werden(self):
        from bewerbungs_assistent.services import nachladen
        return self.status == nachladen.WEG

    def klartext(self):
        from bewerbungs_assistent.services import nachladen
        return nachladen.KLARTEXT.get(self.status, "")


@pytest.fixture
def kein_netz(monkeypatch):
    """Antworten je URL, ohne einen einzigen HTTP-Aufruf.

    Ein Test, der ans Netz geht, prueft das Netz (v1.7.70 MERKE 4:
    sieben Alt-Tests des Refetch-Pfades mockten den falschen Punkt und
    waeren auf einem Runner ohne Netz zu echten Aufrufen geworden).
    """
    from bewerbungs_assistent.services import nachladen

    antworten: dict = {}

    def _holen(url, client, **kwargs):
        return antworten.get(url, _Befund(nachladen.LEBT_UNLESBAR))

    monkeypatch.setattr(nachladen, "beschreibung_holen", _holen)
    return antworten


def test_der_lauf_holt_bis_zu_max_stellen(db, kein_netz):
    """AK 2."""
    from bewerbungs_assistent.services import nachladen

    for i in range(4):
        _stelle(db, f"leer{i}", "", f"https://example.com/1016/{i}")
        kein_netz[f"https://example.com/1016/{i}"] = _Befund(
            nachladen.GELESEN, "Volltext. " * 40)

    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"nur_zaehlen": False, "max_stellen": 2})
    assert erg["status"] == "fertig"
    assert erg["geheilt"] == 2
    assert erg["verbleibend"] == 2
    assert erg["befunde"] == {"gelesen": 2}

    # Und der Text steht wirklich in der Datenbank.
    con = db.connect()
    lang = con.execute(
        "SELECT COUNT(*) FROM jobs WHERE LENGTH(description) > 50"
    ).fetchone()[0]
    assert lang == 2


def test_die_vier_befunde_stehen_in_der_bilanz(db, kein_netz):
    """AK 3, erste Haelfte."""
    from bewerbungs_assistent.services import nachladen

    faelle = {
        "a": _Befund(nachladen.GELESEN, "Volltext. " * 40),
        "b": _Befund(nachladen.WEG, "", 410),
        "c": _Befund(nachladen.GEBLOCKT, "", 403),
        "d": _Befund(nachladen.LEBT_UNLESBAR, "", 200),
    }
    for name, befund in faelle.items():
        url = f"https://example.com/1016/{name}"
        _stelle(db, f"leer{name}", "", url)
        kein_netz[url] = befund

    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"nur_zaehlen": False, "max_stellen": 10})
    assert erg["befunde"] == {
        "gelesen": 1, "weg": 1, "geblockt": 1, "lebt_unlesbar": 1}
    # Jeder Befund kommt mit seinem Klartext — eine Meldung ohne Ausweg
    # ist eine Sackgasse (#927).
    for k, satz in erg["befunde_klartext"].items():
        assert satz, f"{k} ohne Klartext"


def test_eine_entfernte_anzeige_wird_aussortiert_statt_wiederholt(db,
                                                                  kein_netz):
    """AK 3, zweite Haelfte.

    Sie beim naechsten Lauf erneut zu versuchen kostet einen
    HTTP-Aufruf und aendert nichts — und die Stelle bliebe aktiv ohne
    Text stehen, also als Aufgabe, die niemand abarbeiten kann (#1014).
    """
    from bewerbungs_assistent.services import nachladen

    url = "https://example.com/1016/weg"
    _stelle(db, "weg", "", url)
    kein_netz[url] = _Befund(nachladen.WEG, "", 410)

    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"nur_zaehlen": False})
    assert erg["aussortiert"] == 1
    zeile = db.connect().execute(
        "SELECT is_active, dismiss_reason FROM jobs").fetchone()
    assert zeile["is_active"] == 0
    assert zeile["dismiss_reason"] == "veraltet_url"


def test_eine_geblockte_anzeige_bleibt_stehen(db, kein_netz):
    """Die Gegenrichtung, und sie ist die wichtigere.

    Ein 403 sagt etwas ueber diesen Moment, nicht ueber die Anzeige.
    Daraus eine Aussortierung abzuleiten waere geraten (#989) — und
    ein falscher Ausschluss ist teurer als ein fehlender Text (#827).
    """
    from bewerbungs_assistent.services import nachladen

    url = "https://example.com/1016/blockiert"
    _stelle(db, "blockiert", "", url)
    kein_netz[url] = _Befund(nachladen.GEBLOCKT, "", 403)

    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"nur_zaehlen": False})
    assert erg["aussortiert"] == 0
    assert db.connect().execute(
        "SELECT is_active FROM jobs").fetchone()[0] == 1


def test_ein_kuerzerer_text_ueberschreibt_nichts(db, kein_netz):
    """Sonst macht ein Lauf den Bestand schlechter.

    Betrifft vor allem `gekappt`: 2.000 Zeichen sind halb, aber immer
    noch mehr als 200.
    """
    from bewerbungs_assistent.services import nachladen

    url = "https://example.com/1016/ge"
    _stelle(db, "gekappt", "X" * 2000, url)
    kein_netz[url] = _Befund(nachladen.GELESEN, "Z" * 200)

    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"umfang": "gekappt", "nur_zaehlen": False})
    assert erg["geheilt"] == 0
    assert db.connect().execute(
        "SELECT LENGTH(description) FROM jobs").fetchone()[0] == 2000


def test_eine_stelle_ohne_brauchbare_url_wird_gezaehlt_statt_versucht(db,
                                                                     kein_netz):
    """Eine Such-URL fuehrt nicht zur Anzeige (#645/#763)."""
    db.save_jobs([{
        "hash": "suchurl", "title": "Stelle", "company": "Firma",
        "url": "https://example.com/suche?q=plm", "source": "bundesagentur",
        "description": "", "score": 5, "is_search_url": True,
    }])
    erg = _call(_mcp(db), "beschreibungen_nachladen_bestand",
                {"nur_zaehlen": False})
    assert erg["ohne_brauchbare_url"] == 1
    assert erg["geheilt"] == 0


def test_die_vorschau_schreibt_nichts(db, kein_netz):
    """Geprueft, nicht behauptet."""
    _bestand(db)
    con = db.connect()
    vorher = con.execute(
        "SELECT hash, description, is_active FROM jobs ORDER BY hash"
    ).fetchall()
    _call(_mcp(db), "beschreibungen_nachladen_bestand", {"umfang": "beide"})
    nachher = con.execute(
        "SELECT hash, description, is_active FROM jobs ORDER BY hash"
    ).fetchall()
    assert [tuple(r) for r in vorher] == [tuple(r) for r in nachher]


# ---------------------------------------------- Ein Weg, nicht zwei


def test_der_lauf_geht_durch_dasselbe_nadeloehr_wie_der_einzelweg():
    """`services/nachladen` ist die eine Fassung.

    Bis v1.7.86 importierte der Mengenweg zusaetzlich
    `fetch_description_from_detail` (ungenutzt) und warf den Befund weg
    — er rief `beschreibung_holen(...).text` und wusste danach nicht
    mehr, WARUM nichts kam. Das ist DoD 8c im Kleinen: der Mechanismus
    war da, sein Ergebnis wurde verworfen.
    """
    import inspect

    from bewerbungs_assistent.tools import jobs
    quelle = inspect.getsource(jobs.register)
    i = quelle.index("def beschreibungen_nachladen_bestand")
    block = quelle[i:i + 6000]
    assert "nachladen.beschreibung_holen" in block
    assert "fetch_description_from_detail" not in block
    assert "befund.status" in block
