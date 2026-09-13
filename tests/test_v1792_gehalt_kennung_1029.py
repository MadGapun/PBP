"""Tests fuer #1029: Gehalts-Erkennung und Kurz-Kennungen.

Befund 1: das Rate-Wort `gehalt` traf das Ende von "Jahresgehalt". Ein
Jahresbetrag unter der Jahres-Untergrenze landete in der Monatsart und
wurde mal zwoelf gerechnet — "Jahresgehalt: 14.000 bis 15.600 EUR im
Jahr" ergab 168.000 EUR, gespeichert als BELEGT.

Befund 2/3: "X € bis Y €" und "zwischen X und Y" trafen kein
Spannen-Muster; der Einzelwert-Pfad ersetzte die genannte Obergrenze
durch eine gerechnete (+10 Prozent) oder machte sie zur Untergrenze.

Befund 4 + Nachtrag: `[:8]` auf einen gespeicherten Hash ergab den
Profil-Praefix — dieselbe Kennung fuer verschiedene Stellen, und als
Eingabe traf sie ueber den Praefix-Rueckfall irgendeine Stelle.
"""
import asyncio
import importlib
import logging
import os
import re
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


def _g(text):
    from bewerbungs_assistent.services import gehalt_extraktion as G

    return G.extrahieren(text)


# ------------------------------------------------------------ Befund 1


def test_jahresgehalt_wird_nie_als_monatsgehalt_gerechnet():
    """AK 1, woertlich der gemeldete Satz."""
    e = _g("Jahresgehalt: 14.000 bis 15.600 EUR im Jahr bei 13 Gehältern")
    assert e["monat_erkannt"] is False
    assert e["max"] != 187200 and e["min"] != 168000
    # Ein ausdruecklicher Jahresbetrag darf unter 20.000 liegen.
    assert (e["min"], e["max"], e["art"]) == (14000, 15600, "jaehrlich")


def test_bruttojahresgehalt_wird_nie_als_monatsgehalt_gerechnet():
    """AK 2."""
    e = _g("Bruttojahresgehalt: 18.000 - 19.500 EUR")
    assert e["monat_erkannt"] is False
    assert (e["min"], e["max"]) == (18000, 19500)


def test_eine_jahresangabe_hinter_dem_betrag_sperrt_die_monatsart():
    """Isolierender Fall fuer die Umfeld-Pruefung: das nackte "Gehalt"
    davor ist beiden Arten recht, erst "im Jahr" dahinter entscheidet."""
    e = _g("Gehalt: 14.000 bis 15.600 EUR im Jahr")
    assert e["monat_erkannt"] is False
    assert (e["min"], e["max"]) == (14000, 15600)


def test_ein_jahresbetrag_unter_jeder_grenze_wird_kein_monatswert():
    """Isolierender Fall fuer die Monatssperre.

    Die Gegenprobe machte ohne Sperre zunaechst NICHTS rot: in allen
    uebrigen Faellen gewinnt der Jahreswert ohnehin ueber die Rangfolge.
    Hier liegt der Betrag unter BEIDEN Jahresgrenzen — ohne Sperre wird
    er in der Monatsart gelesen und mal zwoelf gerechnet (60.000).
    Lieber gar kein Wert als ein umgedeuteter (#989).
    """
    e = _g("Gehalt: 5.000 EUR im Jahr")
    assert e["monat_erkannt"] is False
    assert e["min"] is None


@pytest.mark.parametrize("text, erwartet", [
    ("Einstiegsgehalt: 45.000 - 55.000", (45000, 55000)),
    ("Fixgehalt: 60.000 bis 70.000 EUR", (60000, 70000)),
    ("Zielgehalt 80.000 - 95.000 €", (80000, 95000)),
])
def test_zusammengesetzte_gehaltswoerter_bleiben_erkannt(text, erwartet):
    """Gegenrichtung zur vorgeschlagenen Wortgrenze: `\\bgehalt` haette
    "Einstiegsgehalt", "Fixgehalt" und "Zielgehalt" nicht mehr getroffen.
    Die Wortgrenze war in der Gegenprobe redundant — und hier schaedlich."""
    e = _g(text)
    assert (e["min"], e["max"]) == erwartet, (text, e)


def test_ohne_ausdrueckliche_jahresangabe_bleibt_die_untergrenze():
    """Gegenrichtung: ein kleiner Betrag OHNE Jahreswort wird nicht zum
    Jahresgehalt — sonst waere aus jeder Monatsangabe eines geworden."""
    e = _g("Vergütung 14.000 EUR brutto")
    assert e["art"] != "jaehrlich" or (e["min"] or 0) >= 20000


def test_ein_echtes_monatsgehalt_bleibt_ein_monatsgehalt():
    e = _g("Monatsgehalt: 3.200 € brutto pro Monat")
    assert e["monat_erkannt"] is True
    assert e["min"] == 38400


# ------------------------------------------------------------ Befund 2


@pytest.mark.parametrize("text, erwartet", [
    ("Gehalt: 45.000 € bis 55.000 €", (45000, 55000)),
    ("Ein jährliches Bruttogehalt von derzeit 22.422,00 € bis 29.029,26 €",
     (22422, 29029.26)),
    ("Monatsgehalt: 3.000 € bis 3.500 €", (36000, 42000)),
    ("Vergütung 60.000 EUR - 70.000 EUR brutto", (60000, 70000)),
])
def test_waehrung_hinter_der_ersten_zahl_behaelt_die_obergrenze(text, erwartet):
    """AK 3-5."""
    e = _g(text)
    assert (e["min"], e["max"]) == erwartet, (text, e)
    assert e["gerechnete_spanne"] is False


# ------------------------------------------------------------ Befund 3


@pytest.mark.parametrize("text, erwartet", [
    ("zwischen 45.000 und 55.000 EUR brutto", (45000, 55000)),
    ("Jahresgehalt zwischen 20.000 € und 30.000 €", (20000, 30000)),
    ("Das Gehalt liegt zwischen 3.000 und 3.500 € im Monat", (36000, 42000)),
    # Nur das Rate-Wort davor belegt den Betrag (Muster 2b):
    ("Monatsgehalt zwischen 3.000 und 3.500", (36000, 42000)),
])
def test_zwischen_x_und_y_ist_eine_spanne(text, erwartet):
    """AK 6 — und die Obergrenze wird nicht mehr zur Untergrenze."""
    e = _g(text)
    assert (e["min"], e["max"]) == erwartet, (text, e)


def test_und_ohne_zwischen_bildet_keine_spanne():
    """Gegenrichtung: "und" steht bewusst nicht in `_BIS`. Sonst wuerde
    "3 Stellen und 45.000 EUR" zur Spanne 3 bis 45.000, und deren
    Verwerfen blockierte den echten Einzelwert."""
    e = _g("Wir besetzen 3 Stellen und zahlen 45.000 EUR brutto")
    assert e["min"] == 45000


# ------------------------------------------------ Alt-Faelle bleiben


@pytest.mark.parametrize("text, erwartet", [
    ("Gehalt: 58.000 - 62.000 Euro", (58000, 62000)),
    ("60.000 - 80.000 EUR brutto p.a.", (60000, 80000)),
    ("Stundensatz 30-35 EUR", None),  # Art stuendlich, Werte unten geprueft
])
def test_bisherige_spannen_bleiben_unveraendert(text, erwartet):
    e = _g(text)
    if erwartet:
        assert (e["min"], e["max"]) == erwartet, (text, e)
    else:
        assert e["art"] == "stuendlich" and (e["min"], e["max"]) == (30, 35)


def test_eine_telefonnummer_bleibt_kein_gehalt():
    """#1026 darf nicht zurueckkommen, auch nicht ueber die neue
    Jahres-Untergrenze."""
    e = _g("Rückfragen unter 0555 12345-10, Jahresgehalt nach Vereinbarung")
    assert e["min"] is None


# ------------------------------------------------------------ Befund 4


def test_die_kurz_kennung_kommt_aus_dem_oeffentlichen_teil():
    from bewerbungs_assistent.services.typed_ids import kurz_job_kennung

    assert kurz_job_kennung("a1b2c3d4:0123456789ab") == "01234567"
    assert kurz_job_kennung("0123456789ab") == "01234567"
    assert kurz_job_kennung(None) == ""


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    d = database.Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.switch_profile(d.create_profile("Test"))
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _stellen(db, n=3):
    # Die Hashes unterscheiden sich schon in den ersten acht Zeichen —
    # wie echte (zufaellige) Hashes. Meine erste Fassung hiess
    # "k1029stelle0/1/2": gleiche acht Zeichen, also zu Recht dieselbe
    # Kurz-Kennung, und der Test mass die Fixture statt des Codes.
    db.save_jobs([{
        "hash": f"{i}{i}{i}k1029stelle", "title": f"Stelle {i}", "company": f"Firma {i}",
        "url": f"https://example.com/1029/{i}", "source": "bundesagentur",
        "description": "Gehalt: 45.000 € bis 55.000 € im Jahr. " * 5, "score": 3,
    } for i in range(n)])
    return [r[0] for r in db.connect().execute("SELECT hash FROM jobs ORDER BY title")]


def test_die_profil_kennung_trifft_nicht_mehr_irgendeine_stelle(db):
    """Der teurere Teil von Befund 4: eine aus dem Speicherwert gekuerzte
    Kennung ist der Profil-Praefix. Als Eingabe traf sie ueber den
    Praefix-Rueckfall JEDE Stelle, und `LIMIT 1` nahm irgendeine."""
    gespeichert = _stellen(db)
    profil_praefix = gespeichert[0][:8]
    assert ":" in gespeichert[0], "Testannahme: Hashes sind profilgebunden"
    assert db.get_job(profil_praefix) is None


def test_eine_richtige_kurz_kennung_findet_ihre_stelle(db):
    from bewerbungs_assistent.services.typed_ids import kurz_job_kennung

    for gespeichert in _stellen(db):
        job = db.get_job(kurz_job_kennung(gespeichert))
        assert job is not None
        assert db.resolve_job_hash(job["hash"]) == gespeichert


def _mcp(db):
    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all

    mcp = FastMCP("t1029")
    register_all(mcp, db, logging.getLogger("t1029"))
    return mcp


def _rufen(mcp, name, args):
    async def _run():
        w = await mcp.get_tool(name)
        r = await w.run(args)
        return getattr(r, "structured_content", None) or r
    return asyncio.run(_run())


def test_die_vorschau_des_gehaltslaufs_zeigt_verschiedene_kennungen(db):
    """AK 7."""
    _stellen(db)
    db.connect().execute("UPDATE jobs SET salary_min=NULL, salary_max=NULL, salary_type=NULL")
    db.connect().commit()
    erg = _rufen(_mcp(db), "gehaelter_neu_auswerten", {"dry_run": True})
    kennungen = [z["job_hash"] for z in erg.get("stichprobe", [])]
    assert len(kennungen) >= 2, erg
    assert len(set(kennungen)) == len(kennungen), kennungen


def test_das_lernereignis_der_ruecknahme_nennt_die_stelle(db):
    """Nachtrag: alle Ereignisse `auto_dismiss_zurueckgeholt` trugen
    dieselbe `entity_id`. Jetzt der volle oeffentliche Hash."""
    gespeichert = _stellen(db, 2)
    con = db.connect()
    con.execute("UPDATE jobs SET is_active=0, "
                "dismiss_reason='auto:falsches_fachgebiet:wiedergaenger'")
    con.commit()
    mcp = _mcp(db)
    for h in gespeichert:
        _rufen(mcp, "stelle_reaktivieren", {"job_hash": db._public_job_hash(h)})
    ids = [r[0] for r in con.execute(
        "SELECT entity_id FROM user_activity_events "
        "WHERE event_type='auto_dismiss_zurueckgeholt'")]
    assert sorted(ids) == sorted(db._public_job_hash(h) for h in gespeichert)


def test_kein_werkzeug_kuerzt_einen_stellen_hash_mit_8_zeichen():
    """Guard: die Bauform `<...hash...>[:8]` ergibt bei einem
    gespeicherten Hash den Profil-Praefix. Erlaubt ist die gemeinsame
    Funktion oder ein ausdrueckliches `split(':')`."""
    src = _repo() / "src" / "bewerbungs_assistent"
    funde = []
    for p in src.rglob("*.py"):
        if p.name == "typed_ids.py":
            continue
        for nr, zeile in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if "[:8]" not in zeile or ".split(" in zeile:
                continue
            if re.search(r"hash[\w\"'\]\)]*\s*\)?\s*\[:8\]", zeile):
                funde.append(f"{p.relative_to(src)}:{nr}: {zeile.strip()}")
    assert not funde, "\n".join(funde)
