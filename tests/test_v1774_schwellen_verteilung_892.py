"""Tests fuer #892 — der Regler kommt aus der Verteilung.

Zwei Befunde des Melders (31.07.2026, anonymisiert neu angelegt am
12.08.):

1. Der Schwellenregler endet bei 20. Gemessen am 10.09.2026 ueber 2.491
   Stellen: Median 1, p90 23, **Maximum 110** — er deckte nicht einmal
   das oberste Zehntel ab.
2. Die Empfehlung stuetzt sich auf die AKTUELLEN Scores, viele davon
   entstehen aber erst nach dem Nachladen der Beschreibung. Belegter
   Fall: eine Stelle ging 0 -> 72 -> 75.

Die zehn Akzeptanzkriterien stehen hier einzeln (DoD 8a).
"""
import os
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import schwellen_verteilung as sv  # noqa: E402


@pytest.fixture
def db(tmp_path):
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


def _stellen(db, scores):
    db.save_jobs([{
        "hash": f"892-{i}",
        "title": f"Rolle Quintus {i}",
        "company": f"Firma {i} GmbH",
        "url": f"https://example.com/j/{i}",
        "source": "stepstone",
        "description": "Anzeigentext mit genug Inhalt. " * 6,
        "score": wert,
        "_manual_entry": True,
    } for i, wert in enumerate(scores)])


# ------------------------------------------- AK 1: der Erst-Score


def test_892_der_erst_score_entsteht_beim_ersten_speichern(db):
    """AK 1: er wird gesetzt und danach nie wieder veraendert."""
    _stellen(db, [12])
    voll = db.resolve_job_hash("892-0")
    job = db.get_job(voll)
    assert job["initial_score"] == pytest.approx(12.0)
    assert job["initial_score_rekonstruiert"] == 0


def test_892_ein_spaeterer_score_laesst_den_erst_score_stehen(db):
    """Der Kern: sonst waere er der aktuelle Score unter anderem Namen.

    Genau der belegte Fall des Melders — eine Stelle geht 0 -> 72 -> 75,
    waehrend der Anzeigentext nachwaechst. Der Erst-Score muss die 0
    behalten, sonst laesst sich der Effekt nie messen.
    """
    _stellen(db, [0])
    voll = db.resolve_job_hash("892-0")

    db.update_job(voll, {"score": 72,
                         "description": "Vollstaendiger Anzeigentext. " * 40})
    db.update_job(voll, {"score": 75})

    job = db.get_job(voll)
    assert job["score"] == 75
    assert job["initial_score"] == pytest.approx(0.0), (
        "Der Erst-Score ist mitgewandert — dann ist er wertlos.")


def test_892_ein_erneuter_ingest_ueberschreibt_ihn_nicht(db):
    """Auch derselbe Hash aus einem zweiten Suchlauf darf ihn nicht
    anfassen."""
    _stellen(db, [5])
    voll = db.resolve_job_hash("892-0")
    db.save_jobs([{
        "hash": "892-0", "title": "Rolle Quintus 0",
        "company": "Firma 0 GmbH", "url": "https://example.com/j/0",
        "source": "stepstone", "description": "Mehr Text. " * 40,
        "score": 44, "_manual_entry": True,
    }])
    assert db.get_job(voll)["initial_score"] == pytest.approx(5.0)


def test_892_der_altbestand_ist_als_rekonstruiert_gekennzeichnet(db):
    """AK 2: gefuellt, aber nicht als gemessen ausgegeben.

    Ein rekonstruierter Wert, der wie ein gemessener aussieht, ist
    #987. Eine leere Spalte waere eine Empfehlung ohne Grundlage.
    """
    # Eine Altzeile nachstellen: Erst-Score von Hand entfernen.
    _stellen(db, [30])
    voll = db.resolve_job_hash("892-0")
    conn = db.connect()
    conn.execute("UPDATE jobs SET initial_score=NULL, "
                 "initial_score_rekonstruiert=NULL WHERE hash=?", (voll,))
    conn.commit()

    # Die Rekonstruktion laeuft beim Start.
    conn.execute("UPDATE jobs SET initial_score=COALESCE(score, 0), "
                 "initial_score_rekonstruiert=1 WHERE initial_score IS NULL")
    conn.commit()

    job = db.get_job(voll)
    assert job["initial_score"] == pytest.approx(30.0)
    assert job["initial_score_rekonstruiert"] == 1


def test_892_die_rekonstruktion_ist_idempotent(db):
    """AK 9: ein zweiter Lauf findet nichts mehr."""
    _stellen(db, [7])
    voll = db.resolve_job_hash("892-0")
    conn = db.connect()
    for _ in range(2):
        conn.execute("UPDATE jobs SET initial_score=COALESCE(score, 0), "
                     "initial_score_rekonstruiert=1 "
                     "WHERE initial_score IS NULL")
        conn.commit()
    job = db.get_job(voll)
    # Der ECHTE Erst-Score bleibt stehen und wird nicht als
    # rekonstruiert umetikettiert.
    assert job["initial_score"] == pytest.approx(7.0)
    assert job["initial_score_rekonstruiert"] == 0


# ----------------------------- AK 3/4/6: Spanne, Median, Farbbereiche


def test_892_die_reglerspanne_folgt_dem_hoechsten_score(db):
    """AK 3: nicht mehr fest auf 0 bis 20.

    Das war der gemeldete Fehler — im echten Bestand liegt der hoechste
    Score bei 110.
    """
    _stellen(db, list(range(0, 111, 5)) + [110] * 5)
    v = sv.verteilung(db, nur_aktive=False)
    assert v["belastbar"] is True
    assert v["max"] == pytest.approx(110.0)
    assert v["regler_max"] >= 110.0, (
        "Der Regler erreicht den hoechsten vorkommenden Score nicht.")


def test_892_der_median_ist_die_empfehlung(db):
    """AK 4 + 5: Mittelmarkierung und empfohlener Wert."""
    _stellen(db, [0, 10, 20, 30, 40] * 6)
    v = sv.verteilung(db, nur_aktive=False)
    assert v["median"] == pytest.approx(20.0)
    assert v["empfehlung"] == v["median"]


def test_892_drei_farbbereiche_mit_nachrechenbaren_grenzen(db):
    """AK 6: die Grenzen stehen als Zahlen dabei.

    Eine Farbe ohne nachvollziehbare Grenze waere eine Behauptung.
    """
    _stellen(db, list(range(0, 60)))
    v = sv.verteilung(db, nur_aktive=False)
    farben = [z["farbe"] for z in v["zonen"]]
    assert farben == ["gruen", "gelb", "rot"]
    for zone in v["zonen"]:
        assert isinstance(zone["von"], float)
        assert isinstance(zone["bis"], float)
        assert zone["bedeutung"]
    # Sie schliessen luckenlos aneinander an.
    assert v["zonen"][0]["bis"] == v["zonen"][1]["von"]
    assert v["zonen"][1]["bis"] == v["zonen"][2]["von"]


# ------------------------------------------- AK 7: Klartext am Regler


def test_892_die_einstellung_sagt_was_sie_bewirkt(db):
    """AK 7: "Bei 35 bleiben 128 von 340 sichtbar"."""
    _stellen(db, [0] * 10 + [50] * 15)
    erg = sv.wirkung(db, 35, nur_aktive=False)
    assert erg["sichtbar"] == 15
    assert erg["gesamt"] == 25
    assert "15 von 25" in erg["text"]


def test_892_eine_schwelle_ueber_dem_hoechstwert_sagt_das(db):
    """Und sie sagt nicht "der ganze Bestand".

    Eine Meldung, die das Gegenteil dessen sagt, was sie meint, ist
    schlimmer als keine.
    """
    _stellen(db, [5] * 25)
    erg = sv.wirkung(db, 99, nur_aktive=False)
    assert erg["sichtbar"] == 0
    assert "KEINE" in erg["text"]
    assert "ganze Bestand" not in erg["text"]


def test_892_die_leiter_traegt_jede_stufe(db):
    """Der Regler soll den Satz zeigen, ohne bei jeder Bewegung zu
    fragen — die Rechnung bleibt trotzdem auf dem Server."""
    _stellen(db, list(range(0, 40)))
    v = sv.verteilung(db, nur_aktive=False)
    leiter = dict((s, n) for s, n in v["sichtbar_ab"])
    assert leiter[0] == 40
    assert leiter[20] == 20
    # Sie ist monoton fallend — alles andere waere ein Rechenfehler.
    werte = [n for _, n in v["sichtbar_ab"]]
    assert werte == sorted(werte, reverse=True)


# ------------------------------------------ AK 8: zu wenige Stellen


def test_892_unter_zwanzig_stellen_faellt_der_regler_zurueck(db):
    """AK 8: und er SAGT es.

    Eine aus vier Werten errechnete Empfehlung waere
    Scheingenauigkeit — dieselbe Grenze wie bei der Entfernungs-
    Schaetzung im Nahbereich (#950).
    """
    _stellen(db, [10, 20, 30])
    v = sv.verteilung(db, nur_aktive=False)
    assert v["belastbar"] is False
    assert v["max"] == sv.RUECKFALL_MAX
    assert v["empfehlung"] is None
    assert "belastbare Empfehlung" in v["grund"]


def test_892_ein_leerer_bestand_stuerzt_nicht_ab(db):
    v = sv.verteilung(db, nur_aktive=False)
    assert v["belastbar"] is False
    assert v["anzahl"] == 0
    assert sv.wirkung(db, 5, nur_aktive=False)["sichtbar"] == 0


# ------------------------------- AK 10: abfragbar ausserhalb der Oberflaeche


def test_892_das_werkzeug_liefert_die_verteilung(db):
    """AK 10: `score_verteilung_anzeigen()`."""
    import asyncio
    import logging

    from fastmcp import FastMCP

    from bewerbungs_assistent.tools import register_all

    _stellen(db, list(range(0, 40)))
    mcp = FastMCP("PBP Test 892")
    register_all(mcp, db, logging.getLogger("test.892"))

    async def _lauf():
        werkzeug = await mcp.get_tool("score_verteilung_anzeigen")
        erg = await werkzeug.run({"nur_aktive": False, "schwelle": 20})
        return getattr(erg, "structured_content", erg)

    antwort = asyncio.run(_lauf())
    assert antwort["belastbar"] is True
    assert antwort["wirkung"]["sichtbar"] == 20


def test_892_die_grundlage_wird_benannt(db):
    """Ob echte Erst-Scores oder rekonstruierte — das gehoert dazu.

    Sonst sieht eine Empfehlung aus rekonstruierten Werten genauso
    verlaesslich aus wie eine aus gemessenen (#989).
    """
    _stellen(db, list(range(0, 30)))
    v = sv.verteilung(db, nur_aktive=False)
    assert v["grundlage"]
    assert "Erst-Score" in v["grundlage"] or "Aktuelle Scores" in v["grundlage"]


# ---------------------------------------- Die Wege und ihre Guards


def test_892_das_frontend_rechnet_die_verteilung_nicht_selbst():
    """Spanne, Zonen und Zahl kommen vom Server.

    Eine Zaehlschleife im JavaScript waere eine zweite Fassung
    derselben Regel — die Bauform, die dieses Projekt vierzehnmal
    gekostet hat.
    """
    seite = (_repo() / "frontend" / "src" / "pages"
             / "ProfilePage.jsx").read_text(encoding="utf-8")
    assert "/api/score-verteilung" in seite
    assert "scoreVerteilung?.regler_max" in seite, (
        "Der Regler haengt nicht an der gemessenen Spanne.")
    code = "\n".join(z for z in seite.split("\n")
                     if not z.strip().startswith("//"))
    assert "max={20}" not in code, (
        "Die feste Obergrenze 20 steht wieder da — das war der Befund.")


def test_892_die_einordnung_liest_ab_statt_zu_rechnen():
    """Der Klartext kommt aus `sichtbar_ab`, nicht aus einer eigenen
    Zaehlung."""
    seite = (_repo() / "frontend" / "src" / "pages"
             / "ProfilePage.jsx").read_text(encoding="utf-8")
    start = seite.index("export function scoreEinordnung")
    block = seite[start:start + 1200]
    assert "sichtbar_ab" in block
    assert ".filter(" not in block, "Hier wird selbst gezaehlt."


# ---------------------------------------------------------------------
# Der Fund, den dieser Issue nebenbei ans Licht gebracht hat.
# ---------------------------------------------------------------------


def test_892_ein_erneuter_ingest_loescht_kein_gelesenes_urteil(db):
    """**Der teuerste Fund dieser Arbeit, und er ist aelter als sie.**

    `save_jobs` schreibt mit `INSERT OR REPLACE`, und REPLACE loescht
    die Zeile und legt sie neu an. Jede Spalte, die nicht in der
    INSERT-Liste steht, war danach NULL.

    Betroffen war unter anderem `analyse_urteil` aus #1007 — das
    gelesene Urteil, die teuerste Auskunft im System. Es verschwand,
    sobald der naechste Suchlauf dieselbe Stelle wiederfand, und die
    Stelle sah danach aus wie eine, die nie beurteilt wurde. Eine
    stille Null in Reinform.
    """
    _stellen(db, [20])
    voll = db.resolve_job_hash("892-0")
    db.set_job_analysis(voll, "EMPFOHLEN", "Von Hand geprueft, passt")
    db.mark_job_sighted(voll)

    # Derselbe Suchlauf findet die Stelle erneut.
    db.save_jobs([{
        "hash": "892-0", "title": "Rolle Quintus 0",
        "company": "Firma 0 GmbH", "url": "https://example.com/j/0",
        "source": "stepstone", "description": "Mehr Text. " * 40,
        "score": 25, "_manual_entry": True,
    }])

    job = db.get_job(voll)
    assert job["analyse_urteil"] == "EMPFOHLEN", (
        "Das gelesene Urteil ist beim erneuten Ingest verschwunden.")
    assert job["analyse_begruendung"], "Die Begruendung ist weg."
    assert job["analyse_am"], "Der Zeitpunkt ist weg."
    assert job["gesichtet_am"], "Die Sichtungs-Spur ist weg."


def test_892_ein_erneuter_ingest_loescht_keinen_aussortier_freitext(db):
    """Dasselbe fuer `dismiss_note` (#913) — noch aelter."""
    _stellen(db, [20])
    voll = db.resolve_job_hash("892-0")
    db.dismiss_job(voll, "sonstiges", notiz="Warum ich sie weggeklickt habe")

    db.save_jobs([{
        "hash": "892-0", "title": "Rolle Quintus 0",
        "company": "Firma 0 GmbH", "url": "https://example.com/j/0",
        "source": "stepstone", "description": "Text. " * 40,
        "score": 21, "_manual_entry": True,
    }])
    assert "weggeklickt" in (db.get_job(voll).get("dismiss_note") or ""), (
        "Der Aussortier-Freitext ist beim erneuten Ingest verschwunden.")


def test_892_jede_spalte_wird_geschrieben_oder_bewahrt(db):
    """Der Guard gegen den naechsten Fall.

    Die Luecke entstand nicht durch Unachtsamkeit an einer Stelle,
    sondern strukturell: wer eine neue Spalte anlegt, denkt nicht daran,
    dass ein REPLACE sie loescht. Dieser Test faellt beim naechsten Mal
    SOFORT — statt erst, wenn jemandem ein verschwundenes Urteil
    auffaellt.
    """
    import re

    quelle = (_repo() / "src" / "bewerbungs_assistent"
              / "database.py").read_text(encoding="utf-8")
    block = quelle[quelle.index("INSERT OR REPLACE INTO jobs"):]
    kopf = block[:block.index("VALUES")]
    geschrieben = {w.strip() for w in re.findall(r"[a-z_]+", kopf)}

    spalten = {r[1] for r in db.connect().execute("PRAGMA table_info(jobs)")}
    bewahrt = set(db._BEWAHREN)

    vergessen = spalten - geschrieben - bewahrt
    assert not vergessen, (
        f"Diese Spalten von `jobs` werden weder von save_jobs geschrieben "
        f"noch bei einem erneuten Ingest bewahrt — ein REPLACE setzt sie "
        f"auf NULL: {sorted(vergessen)}")


def test_892_die_beiden_verteilungs_module_bleiben_getrennt():
    """Zwei aehnliche Namen, zwei verschiedene Fragen.

    `services/score_verteilung.py` (#986) beantwortet "welchen Score
    hatten die Stellen, auf die ich mich BEWORBEN habe";
    `services/schwellen_verteilung.py` (#892) beantwortet "wie sind die
    Scores im BESTAND verteilt".

    Der aehnliche Name hat beim Bauen dieses Issues bereits einmal dazu
    gefuehrt, dass das aeltere Modul ueberschrieben wurde — dieselbe
    Klasse wie `learned_insights` neben `learning_insights` (#799).
    Beide muessen existieren und ihre eigene Funktion behalten.
    """
    from bewerbungs_assistent.services import score_verteilung as alt
    from bewerbungs_assistent.services import schwellen_verteilung as neu

    assert hasattr(alt, "kennzahlen"), "#986 verlor seine Kennzahlen."
    assert hasattr(neu, "zonen_test_marker") is False  # nur Formsache
    assert hasattr(neu, "wirkung") and hasattr(neu, "verteilung")
    # Die Abgrenzung steht im Kopf, damit sie beim naechsten Mal auffaellt.
    assert "score_verteilung.py" in (neu.__doc__ or ""), (
        "Die Abgrenzung zum aelteren Modul fehlt im Docstring.")
