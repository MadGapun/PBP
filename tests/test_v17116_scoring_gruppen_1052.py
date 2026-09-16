"""Tests fuer v1.7.116 — #1052 Schritt 1 und #1045.

Drei Aenderungen an der Rechnung, jede am Bestand gemessen
(Backtest 15.09.2026, 56 Bewerbungen gegen 300 Aussortierte):

1. PLUS und MINUS zaehlen je Anforderung einmal, wie MUSS seit #1012.
2. Die Abzuege sind relativ zum Fachscore gedeckelt (#1045 AK 1a/2a).
   #942 hatte sie bewusst frei gelassen; am Bestand wirkte das umgekehrt.
3. Der Schwellenvorschlag kommt aus dem unteren Viertel und aus
   denselben Kriterien wie jeder Score-Schreiber.
"""
import asyncio
import importlib
import inspect
import os
import re
import shutil
import tempfile

import pytest

from bewerbungs_assistent.job_scraper import (
    MINUS_DECKEL_STANDARD,
    calculate_score,
    fit_analyse,
    fach_maximum,
    minus_deckel_faktor,
)


def _job(titel, text):
    return {"title": titel, "description": text, "company": "Musterfirma GmbH"}


def _krit(**extra):
    k = {
        "keywords_muss": ["Stammdaten", "Datenqualitaet", "Migration"],
        "keywords_plus": [],
        "keywords_minus": [],
        "keywords_ausschluss": [],
        "gewichtung": {"muss": 7, "plus": 3, "minus": 6},
    }
    k.update(extra)
    return k


# ── 1. Gruppierung auf PLUS und MINUS ───────────────────────────────

def test_plus_schreibweisen_zaehlen_einmal():
    text = "Stammdaten im Einkauf. Wir suchen Erfahrung mit Lieferantenportal Pflege."
    einzeln = _krit(keywords_plus=["Lieferantenportal"])
    doppelt = _krit(keywords_plus=["Lieferantenportal", "Lieferantenportal Pflege"])
    a, b = dict(_job("Sachbearbeitung", text)), dict(_job("Sachbearbeitung", text))
    assert calculate_score(b, doppelt) == calculate_score(a, einzeln)


def test_minus_schreibweisen_zaehlen_einmal():
    text = "Stammdaten und Migration. Einsatz ueber Zeitarbeit Vermittlung."
    einzeln = _krit(keywords_minus=["Zeitarbeit"], minus_deckel_faktor=99)
    doppelt = _krit(keywords_minus=["Zeitarbeit", "Zeitarbeit Vermittlung"],
                    minus_deckel_faktor=99)
    a, b = dict(_job("Stammdaten", text)), dict(_job("Stammdaten", text))
    calculate_score(a, einzeln)
    calculate_score(b, doppelt)
    assert b["_rahmenscore"] == a["_rahmenscore"], (a, b)


def test_verschiedene_minus_sachverhalte_bleiben_getrennt():
    """Die Gegenrichtung (#966): nur Belegtes wird zusammengefasst."""
    text = "Stammdaten und Migration. Automotive, Schichtdienst."
    eins = _krit(keywords_minus=["Automotive"], minus_deckel_faktor=99)
    zwei = _krit(keywords_minus=["Automotive", "Schichtdienst"], minus_deckel_faktor=99)
    a, b = dict(_job("Stammdaten", text)), dict(_job("Stammdaten", text))
    # v1.7.117 (#1052): MINUS zaehlt FACHLICH und steht damit im Score,
    # nicht mehr im Rahmenwert. Die geprueste Sache ist dieselbe — zwei
    # verschiedene Sachverhalte ziehen mehr ab als einer.
    assert calculate_score(b, zwei) < calculate_score(a, eins)


def test_beide_rechenwege_gruppieren_gleich():
    """#963: calculate_score und fit_analyse liefern denselben Wert."""
    krit = _krit(keywords_plus=["Lieferantenportal", "Lieferantenportal Pflege"],
                 keywords_minus=["Zeitarbeit", "Zeitarbeit Vermittlung", "Automotive"])
    job = _job("Stammdaten Migration",
               "Stammdaten, Datenqualitaet und Migration. Lieferantenportal Pflege. "
               "Einsatz ueber Zeitarbeit Vermittlung im Bereich Automotive.")
    assert calculate_score(dict(job), krit) == fit_analyse(dict(job), krit)["total_score"]


def test_der_hoechstwert_gruppiert_plus_mit():
    """#999: der Hoechstwert darf nicht ueber dem Erreichbaren liegen."""
    eins = _krit(keywords_plus=["Lieferantenportal Pflege"])
    zwei = _krit(keywords_plus=["Lieferantenportal", "Lieferantenportal Pflege"])
    assert fach_maximum(zwei) == fach_maximum(eins)


# ── 2. Der MINUS-Deckel (#1045) ─────────────────────────────────────

_MINUS_SECHS = ["Automotive", "Luftfahrt", "Verteidigung",
                "Schichtdienst", "Rufbereitschaft", "Reisetaetigkeit"]


def test_mehrere_pflichttreffer_landen_nicht_unter_einem_einzigen():
    """#1045 AK 3, der gemeldete Rechenweg als Testfall.

    Drei Pflichttreffer mit sechs Abzuegen standen bei 0, eine Stelle mit
    einem einzigen Pflichttreffer darueber.
    """
    krit = _krit(keywords_minus=_MINUS_SECHS)
    stark = _job("Stammdaten Migration",
                 "Stammdaten, Datenqualitaet und Migration. "
                 + ", ".join(_MINUS_SECHS) + ".")
    duenn = _job("Sachbearbeitung", "Pflege von Stammdaten.")
    assert calculate_score(dict(stark), krit) > calculate_score(dict(duenn), krit)


def test_ohne_deckel_waere_es_der_gemeldete_fall():
    """Die Umkehrung belegt, dass der Deckel den Unterschied macht."""
    krit = _krit(keywords_minus=_MINUS_SECHS, minus_deckel_faktor=99)
    stark = _job("Stammdaten Migration",
                 "Stammdaten, Datenqualitaet und Migration. "
                 + ", ".join(_MINUS_SECHS) + ".")
    duenn = _job("Sachbearbeitung", "Pflege von Stammdaten.")
    assert calculate_score(dict(stark), krit) < calculate_score(dict(duenn), krit)


def test_der_abzug_nimmt_hoechstens_den_anteil_des_fachwerts():
    krit = _krit(keywords_minus=_MINUS_SECHS)
    job = dict(_job("Stammdaten Migration",
                    "Stammdaten, Datenqualitaet und Migration. "
                    + ", ".join(_MINUS_SECHS) + "."))
    score = calculate_score(job, krit)
    # Der Abzug steht jetzt IM Fachwert: was vom Fachscore uebrig
    # bleibt, ist genau der ungedeckelte Anteil.
    abgezogen = job["_fachscore"] - score
    assert abgezogen == pytest.approx(MINUS_DECKEL_STANDARD * job["_fachscore"])
    assert score > 0


def test_fit_analyse_deckelt_die_abzuege_ebenso():
    krit = _krit(keywords_minus=_MINUS_SECHS)
    job = _job("Stammdaten Migration",
               "Stammdaten, Datenqualitaet und Migration. "
               + ", ".join(_MINUS_SECHS) + ".")
    fit = fit_analyse(dict(job), krit)
    abgezogen = fit["fachscore"] - fit["total_score"]
    assert abgezogen == pytest.approx(MINUS_DECKEL_STANDARD * fit["fachscore"])
    assert fit["total_score"] == calculate_score(dict(job), krit)


def test_minus_deckel_standard_und_fehlerhafte_werte():
    assert minus_deckel_faktor({}) == MINUS_DECKEL_STANDARD
    assert minus_deckel_faktor({"minus_deckel_faktor": ""}) == MINUS_DECKEL_STANDARD
    assert minus_deckel_faktor({"minus_deckel_faktor": "quatsch"}) == MINUS_DECKEL_STANDARD
    assert minus_deckel_faktor({"minus_deckel_faktor": -1}) == MINUS_DECKEL_STANDARD
    assert minus_deckel_faktor({"minus_deckel_faktor": 0}) == 0.0
    assert minus_deckel_faktor({"minus_deckel_faktor": "0.25"}) == 0.25


# ── 3. Backtest und Sichtbarkeit ────────────────────────────────────

def _ohne_kommentare(quelltext: str) -> str:
    return "\n".join(z.split("#", 1)[0] for z in quelltext.splitlines())


def test_der_backtest_rechnet_mit_den_kriterien_der_score_schreiber():
    """#987 in der Messung: roh gelesen lag der Median der Aussortierten
    bei 1,0 statt 3,5, und der Vorschlag kam aus Zahlen, die niemand sieht."""
    from bewerbungs_assistent.services import kalibrierung
    quelle = _ohne_kommentare(inspect.getsource(kalibrierung.backtest))
    assert "fuer_scoring(" in quelle
    assert not re.search(r"criteria\s*=\s*db\.get_search_criteria\(", quelle)


def test_jeder_schattenrechner_holt_seine_kriterien_aus_dem_nadeloehr():
    """Die Luecke im Guard aus #1051, geschlossen.

    Er liess jeden `calculate_score` durch, dessen Kriterien als
    Funktionsparameter hereinkommen — `schatten_score(job, criteria)` reichte
    damit rohe Kriterien ungeprueft weiter. Geprueft wird deshalb eine
    Ebene hoeher: wer `schatten_score` ruft, hat `fuer_scoring` gerufen.
    """
    import ast
    from pathlib import Path
    wurzel = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"
    verstoesse, gefunden = [], 0
    for datei in wurzel.rglob("*.py"):
        baum = ast.parse(datei.read_text(encoding="utf-8-sig"))
        for fn in ast.walk(baum):
            if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            ruft = [k for k in ast.walk(fn) if isinstance(k, ast.Call)
                    and getattr(k.func, "id", getattr(k.func, "attr", None)) == "schatten_score"]
            if not ruft:
                continue
            gefunden += 1
            if "fuer_scoring(" not in ast.unparse(fn):
                verstoesse.append(f"{datei.name}:{fn.name}")
    assert gefunden, "kein Aufrufer gefunden — der Guard prueft nichts"
    assert not verstoesse, verstoesse


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17116_1052_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def test_beide_deckel_lassen_sich_setzen_und_wirken(umgebung):
    db, mcp = umgebung
    res = _call(mcp, "suchkriterien_bearbeiten",
                {"kategorie": "scoring", "aktion": "deckel",
                 "werte": ["minus"], "gewicht": 0.25})
    assert "fehler" not in res, res
    res = _call(mcp, "suchkriterien_bearbeiten",
                {"kategorie": "scoring", "aktion": "deckel",
                 "werte": ["rahmen"], "gewicht": 0.75})
    assert "fehler" not in res, res
    from bewerbungs_assistent.job_scraper import rahmen_deckel_faktor
    from bewerbungs_assistent.services.scoring_kriterien import fuer_scoring
    krit = fuer_scoring(db)
    assert minus_deckel_faktor(krit) == 0.25
    assert rahmen_deckel_faktor(krit) == 0.75


@pytest.mark.parametrize("werte,gewicht", [
    (["minus"], -1), (["seitlich"], 0.5), ([], 0.5)])
def test_ein_unsinniger_deckel_wird_abgewiesen(umgebung, werte, gewicht):
    db, mcp = umgebung
    res = _call(mcp, "suchkriterien_bearbeiten",
                {"kategorie": "scoring", "aktion": "deckel",
                 "werte": werte, "gewicht": gewicht})
    assert "fehler" in res, res
    assert "minus_deckel_faktor" not in (db.get_search_criteria() or {})


def test_die_anzeige_nennt_beide_deckel(umgebung):
    db, mcp = umgebung
    db.set_search_criteria("minus_deckel_faktor", 0.3)
    res = _call(mcp, "scoring_konfigurieren", {"aktion": "anzeigen"})
    deckel = res["deckel_erklaert"]
    assert deckel["minus"]["faktor"] == 0.3
    assert deckel["rahmen"]["faktor"] == 0.5
    assert "aktion='deckel'" in deckel["minus"]["wo"]


# ── Nachtraege aus der Gegenprobe ───────────────────────────────────
#
# Drei Mechanismen blieben beim ersten Durchgang stumm. Jeder Fall hier
# stellt die Lage her, in der sich der Mechanismus unterscheidet.

def test_fit_analyse_fasst_minus_schreibweisen_zusammen():
    """Mit Deckel kappen beide Fassungen auf dieselbe Grenze — ohne nicht."""
    text = "Stammdaten und Migration. Einsatz ueber Zeitarbeit Vermittlung."
    einzeln = _krit(keywords_minus=["Zeitarbeit"], minus_deckel_faktor=99)
    doppelt = _krit(keywords_minus=["Zeitarbeit", "Zeitarbeit Vermittlung"],
                    minus_deckel_faktor=99)
    job = _job("Stammdaten", text)
    assert (fit_analyse(dict(job), doppelt)["rahmenscore"]
            == fit_analyse(dict(job), einzeln)["rahmenscore"])


def test_der_ungedeckelte_abzug_ist_ueber_den_faktor_sichtbar():
    """Was OHNE Deckel angefallen waere, bleibt nachrechenbar.

    v1.7.117 (#1052): das Feld `_rahmen_ungedeckelt` ist weg — es zeigte
    den Rahmen ohne den Deckel aus #942, und den Deckel gibt es nicht
    mehr. Die Auskunft selbst faellt damit nicht weg: wer den
    MINUS-Deckel auf 99 stellt, sieht den vollen Abzug. Das ist
    derselbe Weg wie in #942 und braucht kein eigenes Feld.
    """
    job = dict(_job("Stammdaten Migration",
                    "Stammdaten, Datenqualitaet und Migration. "
                    + ", ".join(_MINUS_SECHS) + "."))
    gedeckelt = calculate_score(job, _krit(keywords_minus=_MINUS_SECHS))
    fach = job["_fachscore"]
    offen = dict(_job("Stammdaten Migration",
                      "Stammdaten, Datenqualitaet und Migration. "
                      + ", ".join(_MINUS_SECHS) + "."))
    voll = calculate_score(offen, _krit(keywords_minus=_MINUS_SECHS,
                                        minus_deckel_faktor=99))
    assert fach - voll == pytest.approx(36.0), offen
    assert voll < gedeckelt


def _stelle(db, hash_, titel, beschreibung):
    conn = db.connect()
    conn.execute(
        "INSERT INTO jobs (hash, title, company, location, url, source, "
        "description, is_active, profile_id, found_at, updated_at, score) "
        "VALUES (?,?,?,?,?,?,?,1,?, '2026-09-01','2026-09-01', 0)",
        (hash_, titel, "Musterfirma GmbH", "Musterstadt",
         f"https://example.com/{hash_}", "demo", beschreibung,
         db.get_active_profile_id()))
    conn.commit()


def test_ein_ausreisser_setzt_den_vorschlag_nicht_mehr_auf_null(umgebung):
    """Der gemeldete Fall: eine Bewerbung mit 0, drei mit Treffer."""
    db, mcp = umgebung
    db.set_search_criteria("keywords_muss", ["PLM"])
    db.set_search_criteria("gewichtung", {"muss": 6})
    _stelle(db, "q0", "Kueche", "Kueche und Service. " * 20)
    for i in (1, 2, 3):
        _stelle(db, f"q{i}", f"PLM Rolle {i}", f"PLM Betreuung Nummer {i}. " * 20)
    for i in (0, 1, 2, 3):
        db.add_application({"company": "Musterfirma GmbH",
                            "title": f"Rolle {i}", "job_hash": f"q{i}"})
    res = _call(mcp, "kalibrierung_backtest", {})
    var = res["varianten"]["aktuell"]
    assert var["bewerbungen"]["min"] == 0, var["bewerbungen"]
    assert var["schwellen_vorschlag"] == int(var["bewerbungen"]["q25"] * 0.8)
    assert var["schwellen_vorschlag"] > 0, var
    assert var["bewerbungen_unter_vorschlag"] == 1, var
