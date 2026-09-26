"""#1063 — Score-Schwellen als benannte Stufen statt als Zahl.

Zwei Schwellen, beide Zahlen ohne Bezugsgroesse, und sie wirken an
verschiedenen Stellen: `min_score_schwelle` beim SPEICHERN,
`schwellenwert/auto_ignore` in der LISTE.

Drei Befunde des Melders (21.09.2026):

1. Die Zahl sagt nichts — Median 1, p90 21, max 110 ueber 2.780
   Stellen; die 7 sah niedrig aus und verwarf 82 %.
2. Sie verschiebt sich unter dem Nutzer: seit #1012 faellt der Score
   fuer dieselbe Anzeige niedriger aus.
3. Direkt ueber der Vorgabe liegt eine Klippe (1 -> 2 halbiert den
   sichtbaren Bestand).

Gemessen auf einer Bestandskopie (57 bewertbare Bewerbungen, 2.765
Aussortierte): Offensichtliches aus 3,5 / Locker 7,0 / Ausgewogen 9,0 /
Streng 17,0 / Nur Volltreffer 28,8 — und schon die mildeste Stufe haette
4 von 57 Stellen verworfen, auf die sich der Mensch beworben hat.
"""
import importlib
import logging
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import schwellen_stufen as st  # noqa: E402


@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17124_1063_")
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


def _stelle(db, kennung, score, aktiv=True):
    """Legt eine Stelle an und gibt den OEFFENTLICHEN Hash zurueck.

    `jobs.hash` traegt den Profil-Praefix, `applications.job_hash` die
    oeffentliche Form — ein rohes Gleichsetzen findet nichts
    (v1.7.56 MERKE 4). Deshalb wird hier ueber LIKE aufgeloest.
    """
    db.save_jobs([{
        "hash": kennung, "title": f"Stelle {kennung}",
        "company": f"Musterbetrieb {kennung}",
        "url": f"https://example.com/{kennung}", "source": "manuell",
        "description": "Ein Anzeigentext. " * 10, "score": score,
    }])
    conn = db.connect()
    voll = conn.execute("SELECT hash FROM jobs WHERE hash LIKE ?",
                        (f"%{kennung}",)).fetchone()["hash"]
    conn.execute("UPDATE jobs SET score=?, fachscore=? WHERE hash=?",
                 (score, score, voll))
    if not aktiv:
        conn.execute(
            "UPDATE jobs SET is_active=0, dismiss_reason='falsches_fachgebiet' "
            "WHERE hash=?", (voll,))
    conn.commit()
    return voll.split(":", 1)[-1]


def _bestand(db, beworben_scores, aussortiert_scores, aktiv_scores=()):
    """Ein Bestand mit den drei Toepfen, aus denen die Stufen kommen."""
    for i, s in enumerate(beworben_scores):
        voll = _stelle(db, f"k63b{i:03d}", s)
        db.add_application({"title": f"Stelle k63b{i:03d}",
                            "company": f"Musterbetrieb k63b{i:03d}",
                            "status": "beworben",
                            "job_hash": voll})
    for i, s in enumerate(aussortiert_scores):
        _stelle(db, f"k63a{i:03d}", s, aktiv=False)
    for i, s in enumerate(aktiv_scores):
        _stelle(db, f"k63x{i:03d}", s)


# ══ Die Stufen und ihre Werte ═══════════════════════════════════════

def test_1063_sechs_stufen_mit_alles_zeigen_zuerst():
    assert [s["schluessel"] for s in st.STUFEN] == [
        "alles_zeigen", "offensichtliches_aus", "locker",
        "ausgewogen", "streng", "nur_volltreffer"]
    assert st.VORGABE == "alles_zeigen"


def test_1063_neues_profil_startet_auf_alles_zeigen(db):
    """AK 3."""
    for bereich in st.BEREICHE:
        assert st.gewaehlte_stufe(db, bereich) == "alles_zeigen"
        assert st.wert_fuer(db, bereich) == 0.0


def test_1063_die_werte_kommen_aus_der_verteilung(db):
    """AK 2: berechnet, nicht hinterlegt."""
    _bestand(db, beworben_scores=list(range(5, 45)),
             aussortiert_scores=list(range(0, 30)))
    befund = st.stufen(db)
    assert befund["belastbar"] is True
    werte = {s["schluessel"]: s["wert"] for s in befund["stufen"]}
    assert werte["alles_zeigen"] == 0.0
    # Aussortierte 0..29 -> Median ~14.5, oberes Viertel ~21.8
    assert 13 <= werte["offensichtliches_aus"] <= 16
    assert 20 <= werte["locker"] <= 23
    # Bewerbungen 5..44 -> q25 ~14.8, Median ~24.5, q75 ~34.2
    assert 23 <= werte["streng"] <= 26
    assert 33 <= werte["nur_volltreffer"] <= 36


def test_1063_die_stufen_steigen_immer(db):
    """Ueberlappen Bewerbungen und Aussortierte, kaeme eine Stufe unter
    ihre Vorgaengerin zu liegen. Auf der gemessenen Kopie passt die
    Reihenfolge — garantiert ist sie nicht."""
    # Bewusst verdreht: die Aussortierten liegen HOEHER als die Bewerbungen.
    _bestand(db, beworben_scores=[1] * 25,
             aussortiert_scores=list(range(40, 80)))
    werte = [s["wert"] for s in st.stufen(db)["stufen"]]
    assert werte == sorted(werte), werte
    # Und die Anhebung wird benannt, nicht stillschweigend gemacht.
    angehoben = [s for s in st.stufen(db)["stufen"]
                 if "angehoben_auf_vorstufe" in s]
    assert angehoben


def test_1063_jede_stufe_nennt_ihre_herkunft(db):
    """Eine Stufe ohne nachrechenbare Quelle waere eine Behauptung."""
    _bestand(db, beworben_scores=list(range(5, 45)),
             aussortiert_scores=list(range(0, 30)))
    for s in st.stufen(db)["stufen"]:
        assert s["herkunft"], s["schluessel"]
        assert s["bedeutung"]


# ══ Die Kostenseite ═════════════════════════════════════════════════

def test_1063_jede_stufe_nennt_was_sie_kostet(db):
    """AK 4 und darueber hinaus: nicht nur "wie viele bleiben sichtbar",
    sondern wie viele der EIGENEN Bewerbungen sie verworfen haette.
    Gemessen war schon die mildeste Stufe bei 7 %."""
    _bestand(db, beworben_scores=list(range(5, 45)),
             aussortiert_scores=list(range(0, 30)),
             aktiv_scores=[0, 5, 10, 20, 40])
    befund = st.stufen(db)
    for s in befund["stufen"]:
        assert "sichtbar" in s
        assert "bewerbungen_darunter" in s
    nach = {s["schluessel"]: s for s in befund["stufen"]}
    assert nach["alles_zeigen"]["bewerbungen_darunter"] == 0
    assert nach["alles_zeigen"]["sichtbar"] == befund["gesamt_aktiv"]
    # Je strenger, desto teurer — beides monoton.
    kosten = [s["bewerbungen_darunter"] for s in befund["stufen"]]
    assert kosten == sorted(kosten)
    sichtbar = [s["sichtbar"] for s in befund["stufen"]]
    assert sichtbar == sorted(sichtbar, reverse=True)


def test_1063_ohne_genug_daten_gibt_es_nur_alles_zeigen(db):
    """Eine Stufe aus einer Handvoll Werte waere geraten — dieselbe
    Grenze wie beim Fachdaumen (#1052)."""
    _bestand(db, beworben_scores=[10, 20, 30],
             aussortiert_scores=[1, 2, 3])
    befund = st.stufen(db)
    assert befund["belastbar"] is False
    assert "20" in befund["grund"]
    berechnet = [s for s in befund["stufen"]
                 if s.get("nicht_berechenbar")]
    assert len(berechnet) == 5
    assert st.wert_fuer(db, st.LISTE) == 0.0


# ══ Setzen und lesen ════════════════════════════════════════════════

def test_1063_gesetzte_stufe_wirkt_auf_beide_leser(db):
    """AK 1: beide Schwellen ueber Stufen."""
    _bestand(db, beworben_scores=list(range(5, 45)),
             aussortiert_scores=list(range(0, 30)))
    st.stufe_setzen(db, st.LISTE, "locker")
    st.stufe_setzen(db, st.SPEICHERN, "offensichtliches_aus")
    assert db.get_scoring_threshold() == st.wert_fuer(db, st.LISTE)
    krit = db.get_search_criteria()
    assert krit["min_score_schwelle"] == st.wert_fuer(db, st.SPEICHERN)
    assert krit["_schwelle_stufe"] == "offensichtliches_aus"


def test_1063_ohne_stufe_bleibt_die_alte_zahl(db):
    """Wer nie eine Stufe gesetzt hat, merkt von der Umstellung nichts."""
    db.set_scoring_config("schwellenwert", "auto_ignore", 12)
    assert db.get_scoring_threshold() == 12


def test_1063_die_stufe_bleibt_wenn_sich_die_zahl_verschiebt(db):
    """AK 5 — der Kern des Issues. Eine Aenderung an den Gewichten
    verschiebt die ZAHL, nicht die WAHL."""
    _bestand(db, beworben_scores=list(range(5, 45)),
             aussortiert_scores=list(range(0, 30)))
    st.stufe_setzen(db, st.LISTE, "locker")
    vorher = st.wert_fuer(db, st.LISTE)

    # Die Verteilung verschiebt sich (wie nach #1012).
    db.connect().execute("UPDATE jobs SET score = score / 2.0")
    db.connect().commit()

    assert st.gewaehlte_stufe(db, st.LISTE) == "locker"
    nachher = st.wert_fuer(db, st.LISTE)
    assert nachher < vorher, (vorher, nachher)


def test_1063_unbekannte_stufe_wird_abgewiesen(db):
    """Still zu ignorieren waere #988: eine Einstellung ohne Wirkung,
    der man glaubt."""
    assert "fehler" in st.stufe_setzen(db, st.LISTE, "sehr_streng")
    assert "fehler" in st.stufe_setzen(db, "irgendwo", "locker")
    assert st.gewaehlte_stufe(db, st.LISTE) == "alles_zeigen"


# ══ Die Umstellung des Bestands ═════════════════════════════════════

def test_1063_eine_gesetzte_zahl_wird_zur_naechsten_stufe(db):
    """AK 6: ohne dass jemand etwas verliert."""
    _bestand(db, beworben_scores=list(range(5, 45)),
             aussortiert_scores=list(range(0, 30)))
    db.set_scoring_config("schwellenwert", "auto_ignore", 21)
    ergebnis = st.umstellen(db)
    umgestellt = {e["bereich"]: e for e in ergebnis["umgestellt"]}
    assert umgestellt[st.LISTE]["zahl_vorher"] == 21
    assert umgestellt[st.LISTE]["stufe"] == "locker"
    assert st.gewaehlte_stufe(db, st.LISTE) == "locker"


def test_1063_die_umstellung_ist_idempotent(db):
    _bestand(db, beworben_scores=list(range(5, 45)),
             aussortiert_scores=list(range(0, 30)))
    db.set_scoring_config("schwellenwert", "auto_ignore", 21)
    st.umstellen(db)
    zweiter = st.umstellen(db)
    assert zweiter["umgestellt"] == []


def test_1063_ohne_berechenbare_stufen_wird_nicht_abgeschaltet(db):
    """Sonst waere die Umstellung ein stilles Entfernen der Schwelle."""
    db.set_scoring_config("schwellenwert", "auto_ignore", 21)
    ergebnis = st.umstellen(db)
    assert st.gewaehlte_stufe(db, st.LISTE) == "alles_zeigen"
    # Und die alte Zahl wirkt weiter, weil keine Stufe gesetzt wurde.
    assert db.get_scoring_threshold() == 21
    # Der isolierende Teil: es wird auch nichts BEHAUPTET. Ohne diese
    # Pruefung meldete die Umstellung eine Umstellung auf "Alles
    # zeigen" — mit Beleg und einmaligem Hinweis, obwohl nichts
    # geschehen ist. Die Gegenprobe hat den Mechanismus zu Recht als
    # stumm gemeldet.
    assert ergebnis["umgestellt"] == []
    assert not db.get_profile_setting(st.BELEG, None)


def test_1063_die_umstellung_hinterlaesst_einen_beleg(db):
    """Ein gesetzter Wert darf nicht still verschwinden (#1053)."""
    _bestand(db, beworben_scores=list(range(5, 45)),
             aussortiert_scores=list(range(0, 30)))
    db.set_scoring_config("schwellenwert", "auto_ignore", 21)
    st.umstellen(db)
    beleg = db.get_profile_setting(st.BELEG, None)
    assert beleg and beleg[0]["zahl_vorher"] == 21


# ══ Das Werkzeug ════════════════════════════════════════════════════

def _werkzeug(db, name):
    import asyncio
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    mcp = FastMCP("PBP Test")
    register_all(mcp, db, logging.getLogger("t"))

    def aufrufen(**kwargs):
        async def _run():
            tool = await mcp.get_tool(name)
            res = await tool.run(kwargs)
            return getattr(res, "structured_content", res)
        return asyncio.run(_run())
    return aufrufen


def test_1063_das_werkzeug_zeigt_die_stufen(db):
    _bestand(db, beworben_scores=list(range(5, 45)),
             aussortiert_scores=list(range(0, 30)),
             aktiv_scores=[0, 5, 20])
    res = _werkzeug(db, "schwelle_stufe_setzen")()
    assert len(res["stufen"]) == 6
    assert res["gewaehlt"]["liste"] == "alles_zeigen"
    assert "unwiederbringlich" in res["hinweis"] or \
           "nicht zurückzuholen" in res["hinweis"]


def test_1063_die_speicher_stufe_warnt_vor_ihren_kosten(db):
    """Was die Speicher-Schwelle verwirft, kommt nie in den Bestand."""
    _bestand(db, beworben_scores=list(range(5, 45)),
             aussortiert_scores=list(range(0, 30)))
    res = _werkzeug(db, "schwelle_stufe_setzen")(
        bereich="speichern", stufe="streng")
    assert res["status"] == "gesetzt"
    assert "beworben" in res["warnung"]
    # Die Liste warnt nicht — dort ist nichts endgueltig.
    res2 = _werkzeug(db, "schwelle_stufe_setzen")(
        bereich="liste", stufe="streng")
    assert "warnung" not in res2


def test_1063_die_verteilung_zeigt_die_stufen_mit(db):
    """Der Regler bleibt fuer Fortgeschrittene, ist aber nicht mehr der
    einzige Weg (AK 1)."""
    _bestand(db, beworben_scores=list(range(5, 45)),
             aussortiert_scores=list(range(0, 30)))
    res = _werkzeug(db, "score_verteilung_anzeigen")(nur_aktive=False)
    assert "stufen" in res
    assert len(res["stufen"]["stufen"]) == 6
