"""Tests fuer v1.7.52 — #965 Befund 2: Reisewiderstand von Barrieren.

Vom Nutzer am 02.09.2026 eingebracht:

    Der Wohnort liegt am Nordufer der Elbe, westlich von Hamburg. Nach
    Sueden gibt es genau drei Wege: den Elbtunnel auf der A7, die
    Elbbruecken durch die Stadt oder die Faehre. Alle drei sind entweder
    staugefaehrdet oder taktgebunden. Nach Norden gibt es diese Barriere
    nicht.

**Zwei Stellen mit derselben Kilometerzahl sind damit nicht gleich
weit** — und der Unterschied ist kein Aufschlag, den man mitteln
koennte, sondern eine Streuung, die den Arbeitsweg unplanbar macht. Bei
drei der vier damals aktiven Stellen lag das Ziel jenseits des Flusses.

Das Issue nennt zwei Wege und laesst die Entscheidung offen. Umgesetzt
ist **Weg 2** (konfigurierbarer Widerstand statt Routing-Dienst), wie
vom Melder empfohlen: er bleibt lokal, braucht keine externe Abfrage je
Stelle, und **der Mensch sieht die Regel, statt sie zu erraten**. Eine
Routenberechnung traefe ausserdem die Streuung nicht, sondern nur den
Mittelwert.

Wichtig fuer die Umsetzung, wie der Melder schreibt: **das Muster ist
allgemein.** Fluesse ohne dichte Querungen, Meerengen, Gebirgskaemme,
Inseln und Grenzen erzeugen dasselbe. Dieses Modul kennt deshalb keine
Elbe, sondern nur Richtungen.

Befund 1 (stummes Geocoding) und der Nebenbefund (HTML-Entities) sind
seit v1.7.24/v1.7.39 erledigt; die Tests dazu stehen dort.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.job_scraper import (  # noqa: E402
    calculate_score, fit_analyse,
)
from bewerbungs_assistent.services import reisewiderstand as rw  # noqa: E402

# Wohnort am Nordufer, Barriere im Sueden — der gemeldete Fall,
# koordinatenbasiert und damit ohne jede Ortskenntnis im Code.
KRITERIEN = {
    "keywords_muss": ["plm", "pdm", "cad"],
    "max_entfernung": {"festanstellung": 50},
    "standort_lat": 53.58, "standort_lon": 9.70,
    "reisewiderstand": [{"richtung": "sueden", "aufschlag_km": 60,
                         "name": "Flussquerung"}],
}


def _stelle(lat, lon, km=92.0):
    return {"title": "PLM Architect", "description": "plm pdm cad " * 20,
            "employment_type": "festanstellung", "distance_km": km,
            "lat": lat, "lon": lon, "location": "Musterort"}


# ── Die Richtung ──────────────────────────────────────────────────────

def test_965_richtung_wird_aus_koordinaten_bestimmt():
    """Keine Ortsnamen, keine Landeskunde — nur ein Vergleich. Damit
    gilt die Regel fuer jede Geografie."""
    assert rw.richtung_von(53.0, 9.7, 53.58, 9.70) == {"sueden"}
    assert rw.richtung_von(54.2, 9.7, 53.58, 9.70) == {"norden"}
    assert rw.richtung_von(53.58, 11.0, 53.58, 9.70) == {"osten"}
    assert rw.richtung_von(53.58, 8.0, 53.58, 9.70) == {"westen"}


def test_965_ein_ziel_kann_in_zwei_richtungen_liegen():
    """Suedwestlich ist sueden UND westen — beide Regeln greifen."""
    assert rw.richtung_von(53.0, 8.0, 53.58, 9.70) == {"sueden", "westen"}


def test_965_ohne_koordinaten_keine_richtung():
    """Ohne Koordinaten gibt es keine Aussage — und keine erfundene."""
    assert rw.richtung_von(None, 9.7, 53.58, 9.70) == set()
    assert rw.richtung_von(53.0, 9.7, None, None) == set()


# ── Der gemeldete Fall ────────────────────────────────────────────────

def test_965_gleiche_kilometer_verschiedene_richtung():
    """Der Kern des Befunds: 92 km suedlich der Barriere sind teurer als
    92 km noerdlich davon."""
    nord = calculate_score(_stelle(54.2, 9.9), KRITERIEN)
    sued = calculate_score(_stelle(53.0, 9.9), KRITERIEN)
    assert sued < nord


def test_965_ohne_regel_aendert_sich_nichts():
    """Die wichtigste Gegenprobe: wer keine Barriere konfiguriert,
    bekommt exakt das Verhalten von vorher."""
    ohne = {k: v for k, v in KRITERIEN.items() if k != "reisewiderstand"}
    assert (calculate_score(_stelle(54.2, 9.9), ohne)
            == calculate_score(_stelle(53.0, 9.9), ohne))


def test_965_beide_rechenwege_sind_sich_einig():
    """Die Lehre aus #963 und sieben Wiederholungen: eine Regel in nur
    EINEN von zwei parallelen Rechenwegen zu bauen verschiebt die
    Divergenz bloss."""
    for lat, lon in ((54.2, 9.9), (53.0, 9.9), (53.58, 11.0)):
        job = _stelle(lat, lon)
        assert (float(calculate_score(dict(job), KRITERIEN))
                == float(fit_analyse(dict(job), KRITERIEN)["total_score"])), \
            f"({lat}, {lon})"


def test_965_die_ausgewiesene_entfernung_bleibt_unangetastet():
    """**Der Aufschlag ist ein Preis, keine Messung.** Wuerde er die
    Kilometerzahl veraendern, haette PBP wieder eine Zahl, die etwas
    anderes bedeutet als sie sagt (#950)."""
    job = _stelle(53.0, 9.9)
    calculate_score(job, KRITERIEN)
    assert job["distance_km"] == 92.0
    assert job["_reisewiderstand_km"] == 60.0


def test_965_unbekannte_entfernung_wird_nicht_ueber_umwege_bestraft():
    """Ohne aufgeloeste Entfernung gibt es keinen Malus, auf den ein
    Aufschlag wirken koennte — und "unbekannt" darf nicht doch noch
    einen erfundenen Malus bekommen (#989)."""
    job = _stelle(53.0, 9.9, km=None)
    job.pop("distance_km")
    assert rw.aufschlag(KRITERIEN, job) == (0.0, [])


# ── Die Regel ist sichtbar und pruefbar ───────────────────────────────

def test_965_die_begruendung_nennt_regel_und_richtung():
    """AK 7: nachvollziehbar, nicht nur wirksam."""
    _km, belege = rw.aufschlag(KRITERIEN, _stelle(53.0, 9.9))
    assert _km == 60.0
    assert "Flussquerung" in belege[0]
    assert "Sueden" in belege[0]


def test_965_fit_analyse_zeigt_die_regel_als_eigene_zeile():
    """Sie muss dort auftauchen, wo der Mensch die Rechnung liest."""
    factors = fit_analyse(_stelle(53.0, 9.9), KRITERIEN)["factors"]
    assert any("Reisewiderstand" in k for k in factors)


def test_965_ungueltige_regeln_werden_abgewiesen():
    """Eine Regel, die nicht wirken kann, gehoert nicht gespeichert —
    sonst entsteht wieder eine Einstellung, die aussieht als wirke sie
    (#988)."""
    assert not rw.regel_pruefen("suedwest", 40)["ok"]
    assert not rw.regel_pruefen("sueden", 0)["ok"]
    assert not rw.regel_pruefen("sueden", "viel")["ok"]
    assert not rw.regel_pruefen("sueden", 10_000)["ok"]
    assert rw.regel_pruefen("sueden", 40, "Fluss")["ok"]


def test_965_ein_unbegrenzter_aufschlag_waere_ein_ausschluss():
    """Die Obergrenze ist Absicht: Entfernung bleibt ein Preis
    (#910/#988), kein verstecktes k.o."""
    ergebnis = rw.regel_pruefen("sueden", rw.MAX_AUFSCHLAG_KM + 1)
    assert not ergebnis["ok"]
    assert "Preis" in ergebnis["fehler"]


def test_965_kaputte_gespeicherte_regeln_werden_uebergangen():
    """Der Aufschlag laeuft bei jeder Bewertung mit — ein Absturz waere
    teurer als die fehlende Regel."""
    for muell in (None, "kaputt", [{"richtung": "oben"}], [42], [{}]):
        assert rw.aufschlag({"reisewiderstand": muell,
                             "standort_lat": 53.5, "standort_lon": 9.7},
                            _stelle(53.0, 9.9)) == (0.0, [])


def test_965_das_modul_kennt_keine_einzelne_geografie():
    """Der Melder betont es ausdruecklich: sonst wird daraus ein
    Sonderfall fuer eine Stadt. Ein Mensch in Koeln, Rostock oder
    Konstanz hat dieselbe Frage mit anderer Geografie."""
    quelle = (Path(__file__).resolve().parents[1] / "src"
              / "bewerbungs_assistent" / "services"
              / "reisewiderstand.py").read_text(encoding="utf-8")
    code = "\n".join(z for z in quelle.split("\n")
                     if not z.strip().startswith("#"))
    code = code[code.index('"""', code.index('"""') + 3):]  # Docstring raus
    for ortsname in ("Elbe", "Hamburg", "Wedel", "Elbtunnel", "A7"):
        assert ortsname not in code, (
            f"'{ortsname}' steht im Code — die Regel gilt fuer jede "
            "Geografie, nicht fuer eine")


# ── Konfiguration ueber die MCP-Tools (AK 8) ──────────────────────────

@pytest.fixture
def suche(tmp_path):
    """QA-Isolation (HART): eigenes Temp-Verzeichnis, hart geprueft."""
    import importlib
    import logging
    import os
    alt = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    try:
        from bewerbungs_assistent import database as _database
        importlib.reload(_database)
        db = _database.Database()
        db.initialize()
        assert str(tmp_path) in str(db.db_path), f"nicht isoliert: {db.db_path}"
        db.save_profile({"name": "Muster Person"})

        gesammelt = {}

        class _Sammler:
            def tool(self, *a, **kw):
                def deko(fn):
                    gesammelt[fn.__name__] = fn
                    return fn
                return deko

        from bewerbungs_assistent.tools import suche as such_tools
        such_tools.register(_Sammler(), db, logging.getLogger("test"))
        yield gesammelt, db
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt


def test_965_regel_ueber_das_werkzeug_setzen(suche):
    """AK 8: ueber die MCP-Tools, nicht per Code- oder DB-Aenderung."""
    tools, db = suche
    antwort = tools["suchkriterien_setzen"](reisewiderstand=[
        {"richtung": "sueden", "aufschlag_km": 60, "name": "Flussquerung"}])
    assert "1 Regel" in antwort["reisewiderstand"]
    gespeichert = db.get_search_criteria()["reisewiderstand"]
    assert gespeichert[0]["richtung"] == "sueden"


def test_965_eine_kaputte_regel_speichert_gar_nichts(suche):
    """Teilweise gespeichert waere schlimmer als abgewiesen — der Mensch
    glaubte dann an eine Regel, die nur zur Haelfte gilt."""
    tools, db = suche
    tools["suchkriterien_setzen"](reisewiderstand=[
        {"richtung": "sueden", "aufschlag_km": 60}])
    antwort = tools["suchkriterien_setzen"](reisewiderstand=[
        {"richtung": "sueden", "aufschlag_km": 30},
        {"richtung": "oben", "aufschlag_km": 30}])
    assert "fehler" in antwort
    # Der alte Stand bleibt unangetastet.
    assert db.get_search_criteria()["reisewiderstand"][0]["aufschlag_km"] == 60


def test_965_leere_liste_loescht_die_regeln(suche):
    tools, db = suche
    tools["suchkriterien_setzen"](reisewiderstand=[
        {"richtung": "sueden", "aufschlag_km": 60}])
    antwort = tools["suchkriterien_setzen"](reisewiderstand=[])
    assert "geloescht" in antwort["reisewiderstand"]
    assert db.get_search_criteria().get("reisewiderstand") == []
