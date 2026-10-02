"""#1158 — der Stellen-Tab blendet keine Stellen mehr still aus.

Befund (02.10.2026, Meldung des Nutzers, nachgeprüft per Abfrage): der Tab zeigte 2 von 4 aktiven Stellen,
obwohl alle Filter aus waren. Die beiden fehlenden hatten einen negativen Punktestand (ein Abzug für Entfernung
beziehungsweise Gehalt):

1. `FILTER_VORGABE["min_score"] = 0.0` und `score < min_score` in `services/stellen_liste.py`: jede Stelle mit
   negativem Stand fiel still heraus. Das widerspricht #1052 (Rahmen als Tor, der Score ist nur Sortierhilfe).
2. Das Feld „Punkte ≥“ schickte nur Werte über 0 ab; -100 tippen bewirkte nichts.
3. Der Streifen nannte den wirksamen Filter nicht („Punkte ≥ 0“ stand nie darin).
4. Die Seite startete mit eingeschaltetem Rahmen- und Schwellenfilter, fest eingebaut.
5. „Filter zurücksetzen“ stellte genau diese Voreinstellung her, schaltete also Filter AN.
6. Der Filterzustand ging beim Neuladen verloren.
7. Stellen mit Bewerbung zählten im Tab als aktiv (im Menü nicht).
8. „Hamburg (hybrid), remote möglich“ wurde von Nominatim bei Mainz verortet (410 statt 20 km) und schob die
   beste Stelle des Tages auf einen negativen Stand.

Verbindliche Anforderung des Nutzers: „Filter zurücksetzen“ zeigt ALLE offenen Stellen — unabhängig von Punkten,
Rahmen, Schwelle, Gehalt, Entfernung, Remote und Quelle; ausgenommen nur Aussortierte und Stellen mit laufender
Bewerbung. Liste, Tab „Aktive (n)“ und Menü zählen dann gleich.

Alle Firmen, Orte und Namen in den Testdaten sind Platzhalter.
"""
import importlib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import stellen_liste as sl  # noqa: E402

JOBS_PAGE = ROOT / "frontend" / "src" / "pages" / "JobsPage.jsx"
DASHBOARD_PAGE = ROOT / "frontend" / "src" / "pages" / "DashboardPage.jsx"


def _stelle(nr, score, **extra):
    job = {"hash": f"h{nr:03d}", "title": f"Beispielstelle {nr}", "company": f"Beispiel GmbH {nr}",
           "score": score, "source": "bundesagentur", "description": "Beschreibung. " * 10}
    job.update(extra)
    return job


# Genau das schickt die Seite nach „Filter zurücksetzen“ (siehe FILTER_STANDARD): Beworbene aus der Liste,
# alles andere ohne Einschränkung. Ein statischer Test unten hält die Seite an dieser Form fest.
ZURUECKGESETZT = {"beworbene_ausblenden": "true", "rahmen_ausblenden": "false", "schwelle_ausblenden": "false"}


# ══ Punkt 1: keine Untergrenze ohne ausdrückliche Wahl ═══════════════════════════

def test_1158_die_vorgabe_hat_keine_untergrenze():
    assert sl.FILTER_VORGABE["min_score"] is None
    assert sl.filter_lesen({})["min_score"] is None
    assert sl.filter_lesen({"min_score": ""})["min_score"] is None


def test_1158_null_und_negative_zahlen_gelten_auch_als_zahl_nicht_nur_als_text():
    assert sl.filter_lesen({"min_score": 0})["min_score"] == 0.0
    assert sl.filter_lesen({"min_score": -5})["min_score"] == -5.0
    assert sl.filter_lesen({"min_score": 12.5})["min_score"] == 12.5


def test_1158_stellen_mit_minus_100_0_und_100_erscheinen_ohne_filter():
    jobs = [_stelle(1, -100), _stelle(2, 0), _stelle(3, 100)]
    antwort = sl.aufbereiten(jobs)
    assert {j["hash"] for j in antwort["jobs"]} == {"h001", "h002", "h003"}
    assert antwort["treffer"] == 3 and antwort["offen"] == 3


def test_1158_nach_dem_zuruecksetzen_erscheinen_alle_drei():
    """Die Anforderung des Nutzers, wörtlich: Punktestand -100, 0 und 100 — alle drei nach dem Zurücksetzen."""
    jobs = [_stelle(1, -100), _stelle(2, 0), _stelle(3, 100)]
    antwort = sl.aufbereiten(jobs, ZURUECKGESETZT, "score_desc")
    assert [j["score"] for j in antwort["jobs"]] == [100, 0, -100]
    assert antwort["treffer"] == antwort["offen"] == antwort["total"] == 3
    assert antwort["offen_verborgen"] == 0 and antwort["verborgen"] == {"beworbene_ausblenden": 0}


def test_1158_eine_stelle_mit_negativem_stand_fehlt_weder_in_der_liste_noch_im_zaehler():
    jobs = [_stelle(1, 22), _stelle(2, -21), _stelle(3, -1)]
    antwort = sl.aufbereiten(jobs, ZURUECKGESETZT)
    assert len(antwort["jobs"]) == antwort["offen"] == antwort["treffer"] == 3


def test_1158_eine_ausdrueckliche_untergrenze_gilt_auch_bei_0_und_negativ():
    jobs = [_stelle(1, -100), _stelle(2, 0), _stelle(3, 100)]
    ab_null = sl.aufbereiten(jobs, {"min_score": "0"})
    assert {j["hash"] for j in ab_null["jobs"]} == {"h002", "h003"}
    assert ab_null["verborgen"]["min_score"] == 1
    ab_minus_50 = sl.aufbereiten(jobs, {"min_score": "-50"})
    assert {j["hash"] for j in ab_minus_50["jobs"]} == {"h002", "h003"}
    ab_minus_200 = sl.aufbereiten(jobs, {"min_score": "-200"})
    assert len(ab_minus_200["jobs"]) == 3 and ab_minus_200["verborgen"]["min_score"] == 0
    assert sl.filter_lesen({"min_score": "-5"})["min_score"] == -5.0
    assert sl.filter_lesen({"min_score": "0"})["min_score"] == 0.0


@pytest.mark.parametrize("wert", ["viele", "1,5x", "nan", "NaN", "inf", "-inf", "Infinity"])
def test_1158_ein_unlesbarer_wert_wird_benannt_statt_ignoriert(wert):
    """'nan' liesse alles durch, 'inf' verbaerge alles: beides ist keine Untergrenze."""
    with pytest.raises(sl.UngueltigerParameter) as fehler:
        sl.filter_lesen({"min_score": wert})
    assert fehler.value.feld == "min_score"


def test_1158_eine_untergrenze_macht_die_anfrage_zur_listenanfrage():
    assert sl.ist_listenanfrage({}, "") is False
    assert sl.ist_listenanfrage({"min_score": "0"}, "") is True


# ══ Punkt 3: der Streifen nennt jeden wirksamen Filter mit seiner Zahl ═════════════

def test_1158_zahlen_je_filter_und_mehrere_zugleich_gehen_auf():
    """Fünf Stellen, drei Filter, eine Stelle unter zwei Filtern zugleich — die Rechnung muss aufgehen."""
    jobs = [
        _stelle(1, 10, remote_level="remote"),                       # passt
        _stelle(2, -5, remote_level="remote"),                       # nur die Untergrenze
        _stelle(3, 50, remote_level="vor_ort"),                      # nur Remote
        _stelle(4, 50, remote_level="remote", hash="beworben1"),     # nur die Bewerbung
        _stelle(5, -20, remote_level="vor_ort"),                     # Untergrenze UND Remote
    ]
    antwort = sl.aufbereiten(
        jobs, {"min_score": "0", "remote": "remote", "beworbene_ausblenden": "true",
               "rahmen_ausblenden": "false", "schwelle_ausblenden": "false"}, beworbene=["beworben1"])
    v = antwort["verborgen"]
    assert v == {"min_score": 1, "remote": 1, "beworbene_ausblenden": 1}
    assert antwort["total"] == 5 and antwort["offen"] == 4 and antwort["treffer"] == 1
    assert antwort["beworbene_anzahl"] == 1, "Nr. 4 hat eine Bewerbung und ist keine offene Stelle"
    assert antwort["offen_verborgen"] == 3, "Nr. 2, 3 und 5 fehlen; Nr. 4 ist keine offene Stelle"
    # Die Rechnung des Streifens: 3 offene Stellen fehlen = 1 (nur Untergrenze) + 1 (nur Remote) + 1 (beide).
    assert antwort["offen_verborgen"] - (v["min_score"] + v["remote"]) == 1


def test_1158_nur_wirksame_filter_stehen_in_der_zaehlung():
    jobs = [_stelle(1, 10), _stelle(2, -5)]
    ohne = sl.aufbereiten(jobs, {"rahmen_ausblenden": "false", "schwelle_ausblenden": "false"})
    assert ohne["verborgen"] == {}, "ohne Filter gibt es nichts zu zählen"
    mit = sl.aufbereiten(jobs, {"rahmen_ausblenden": "false", "schwelle_ausblenden": "false", "min_score": "0"})
    assert mit["verborgen"] == {"min_score": 1}
    assert "remote" not in mit["verborgen"] and "pruefstand" not in mit["verborgen"]


def test_1158_ein_wirksamer_filter_ohne_betroffene_stelle_steht_mit_null_da():
    """Der Streifen darf ihn nennen (er gilt), aber ohne Zahl — verborgen wird durch ihn nichts."""
    antwort = sl.aufbereiten([_stelle(1, 10)], {"min_score": "0", "rahmen_ausblenden": "false",
                                                 "schwelle_ausblenden": "false"})
    assert antwort["verborgen"] == {"min_score": 0}
    assert antwort["offen_verborgen"] == 0


def test_1158_beworbene_zaehlen_nicht_als_offen():
    jobs = [_stelle(1, 10), _stelle(2, 20, hash="beworben1"), _stelle(3, 30, hash="beworben2")]
    antwort = sl.aufbereiten(jobs, ZURUECKGESETZT, beworbene=["beworben1", "beworben2"])
    assert antwort["total"] == 3 and antwort["offen"] == 1 and antwort["beworbene_anzahl"] == 2
    assert antwort["treffer"] == 1
    assert antwort["verborgen"]["beworbene_ausblenden"] == 2
    assert antwort["offen_verborgen"] == 0, "die Beworbenen sind keine fehlenden offenen Stellen"


def test_1158_ohne_beworbene_auszublenden_bleiben_sie_in_der_liste_aber_nicht_in_offen():
    jobs = [_stelle(1, 10), _stelle(2, 20, hash="beworben1")]
    antwort = sl.aufbereiten(jobs, {"beworbene_ausblenden": "false"}, beworbene=["beworben1"])
    assert antwort["treffer"] == 2 and antwort["offen"] == 1 and antwort["offen_verborgen"] == 0


def test_1158_die_alten_zaehler_bleiben_fuer_andere_aufrufer():
    jobs = [_stelle(1, 10, hash="beworben1"), _stelle(2, 5)]
    antwort = sl.aufbereiten(jobs, {"beworbene_ausblenden": "true"}, beworbene=["beworben1"])
    assert antwort["treffer_mit_beworbenen"] == 2
    assert "rahmen_verborgen" in antwort and "schwelle_verborgen" in antwort


# ══ Durch den Endpunkt, wie die Seite fragt ═════════════════════════════════════

@pytest.fixture
def dashboard():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17150_1158_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test", "city": "Hamburg"})
    _dash_mod._db = db
    from fastapi.testclient import TestClient
    yield TestClient(_dash_mod.app), db
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _stellen_anlegen(db, scores):
    db.save_jobs([{"hash": f"abc{i:09d}", "title": f"Sachbearbeiter {i}", "company": f"Beispiel GmbH {i}",
                   "url": f"https://beispiel.example/job/{i}", "source": "bundesagentur",
                   "description": "Beschreibung der Stelle. " * 20, "score": s, "found_at": "2026-10-01T00:00:00"}
                  for i, s in enumerate(scores, 1)])
    con = db.connect()
    for i, s in enumerate(scores, 1):
        con.execute("UPDATE jobs SET score=? WHERE hash LIKE ?", (s, f"%abc{i:09d}"))
    con.commit()


def test_1158_der_endpunkt_liefert_nach_dem_zuruecksetzen_alle_offenen_stellen(dashboard, monkeypatch):
    client, db = dashboard
    _stellen_anlegen(db, [-100, 0, 100])
    # Die gespeicherten Stände bleiben, wie sie sind: hier geht es um den Filter, nicht um das Scoring.
    monkeypatch.setattr(db, "_mit_scoring_reglern", lambda jobs, sortieren=True: jobs)
    antwort = client.get("/api/jobs", params={
        "active": "true", "exclude_blacklisted": "true", "limit": 50, "sort": "score_desc", **ZURUECKGESETZT})
    assert antwort.status_code == 200
    daten = antwort.json()
    assert sorted(j["score"] for j in daten["jobs"]) == [-100, 0, 100]
    assert daten["treffer"] == daten["offen"] == 3


def test_1158_der_endpunkt_blendet_ohne_untergrenze_nichts_aus(dashboard, monkeypatch):
    client, db = dashboard
    _stellen_anlegen(db, [-21, -1, 22])
    monkeypatch.setattr(db, "_mit_scoring_reglern", lambda jobs, sortieren=True: jobs)
    daten = client.get("/api/jobs", params={"active": "true", "limit": 50, "sort": "score_desc"}).json()
    assert len(daten["jobs"]) == 3


def test_1158_der_endpunkt_nimmt_eine_negative_untergrenze_an(dashboard, monkeypatch):
    client, db = dashboard
    _stellen_anlegen(db, [-100, 0, 100])
    monkeypatch.setattr(db, "_mit_scoring_reglern", lambda jobs, sortieren=True: jobs)
    daten = client.get("/api/jobs", params={"active": "true", "limit": 50, "min_score": "-50"}).json()
    assert sorted(j["score"] for j in daten["jobs"]) == [0, 100]
    assert daten["verborgen"]["min_score"] == 1


def _bewerbung(db, nr, status="beworben"):
    return db.add_application({"title": f"Sachbearbeiter {nr}", "company": f"Beispiel GmbH {nr}",
                               "job_hash": f"abc{nr:09d}", "status": status, "applied_at": "2026-10-01"})


def test_1158_menue_tab_und_liste_nennen_nach_dem_zuruecksetzen_dieselbe_zahl(dashboard):
    """Die Anforderung des Nutzers: Anzahl in der Liste = Zahl im Tab „Aktive (n)“ = Zahl im Menü.

    Sechs Stellen, zwei mit negativem Stand; eine mit laufender Bewerbung (keine offene Stelle), eine mit
    beendeter Bewerbung (zählt wieder als offen). Der ECHTE Weg, ohne Eingriff in die Bewertung.
    """
    client, db = dashboard
    _stellen_anlegen(db, [-21, -1, 22, 0, 40, 15])
    _bewerbung(db, 5)                      # laufend: eine Bewerbung, keine offene Stelle
    _bewerbung(db, 6, "abgelehnt")         # beendet: die Stelle ist wieder offen
    menue = client.get("/api/workspace-summary").json()["navigation"]["jobs_badge"]
    liste = client.get("/api/jobs", params={
        "active": "true", "exclude_blacklisted": "true", "limit": 50, "sort": "score_desc", **ZURUECKGESETZT}).json()
    assert liste["total"] == 6 and liste["beworbene_anzahl"] == 1
    assert int(menue) == liste["offen"] == liste["treffer"] == len(liste["jobs"]) == 5
    assert liste["offen_verborgen"] == 0
    assert liste["verborgen"] == {"beworbene_ausblenden": 1}, "der Streifen nennt den einen Grund mit Zahl"


def test_1158_ohne_beworbene_auszublenden_zaehlt_die_liste_mehr_als_das_menue(dashboard):
    """Wer die Beworbenen ausdrücklich einblendet, sieht sie — „offen“ bleibt trotzdem die Menü-Zahl."""
    client, db = dashboard
    _stellen_anlegen(db, [-5, 10, 20])
    _bewerbung(db, 3)
    menue = client.get("/api/workspace-summary").json()["navigation"]["jobs_badge"]
    liste = client.get("/api/jobs", params={
        "active": "true", "exclude_blacklisted": "true", "limit": 50, "beworbene_ausblenden": "false",
        "rahmen_ausblenden": "false", "schwelle_ausblenden": "false"}).json()
    assert len(liste["jobs"]) == liste["treffer"] == liste["total"] == 3
    assert int(menue) == liste["offen"] == 2


# ══ Punkt 8: der Ort ═════════════════════════════════════════════════════════════

@pytest.mark.parametrize("roh,erwartet", [
    ("Hamburg (hybrid), remote möglich", "Hamburg"),
    ("Hamburg, remote möglich", "Hamburg"),
    ("Hamburg, Homeoffice möglich", "Hamburg"),
    ("München, Bayern (Remote möglich)", "München, Bayern"),
    ("Berlin, teilweise remote möglich", "Berlin"),
    ("Aerzen, Niedersachsen (Hybrid)", "Aerzen, Niedersachsen"),
    ("Hamburg - hybrid", "Hamburg"),
    ("Raum Hamburg", "Raum Hamburg"),
    ("Neustadt am Rübenberge, Niedersachsen", "Neustadt am Rübenberge, Niedersachsen"),
])
def test_1158_zusaetze_im_ortsstring_fallen_weg(roh, erwartet):
    from bewerbungs_assistent.services.geocoding_service import normalisiere_ort
    assert normalisiere_ort(roh) == erwartet


class _FalscherOrtsdienst:
    """Ahmt Nominatim nach: je Anfrage eine feste Antwort, alle Anfragen werden gemerkt."""
    anfragen: list = []
    antworten: dict = {}

    def __init__(self, user_agent=None, timeout=None):
        pass

    def geocode(self, anfrage, exactly_one=True):
        type(self).anfragen.append(anfrage)
        wert = type(self).antworten.get(anfrage)
        if wert is None:
            return None
        from types import SimpleNamespace
        return SimpleNamespace(latitude=wert[0], longitude=wert[1])


@pytest.fixture
def ortsdienst(monkeypatch):
    from bewerbungs_assistent.services import geocoding_service as geo
    geopy = pytest.importorskip("geopy.geocoders")
    _FalscherOrtsdienst.anfragen = []
    _FalscherOrtsdienst.antworten = {
        "Hamburg, Deutschland": (53.55, 10.0),
        # so antwortete der echte Dienst auf den Rohstring: bei Mainz
        "Hamburg (hybrid), remote möglich, Deutschland": (50.0, 8.27),
    }
    monkeypatch.setattr(geopy, "Nominatim", _FalscherOrtsdienst)
    monkeypatch.setenv("PBP_GEOCODING", "1")
    monkeypatch.setattr(geo, "_speicher", None)
    monkeypatch.setattr(geo, "_rate_limit", lambda: None)
    geo._geo_cache.clear()
    yield geo, _FalscherOrtsdienst
    geo._geo_cache.clear()


def test_1158_gefragt_wird_der_bereinigte_ort_nicht_der_rohstring(ortsdienst):
    geo, dienst = ortsdienst
    assert geo.geocode_location("Hamburg (hybrid), remote möglich") == (53.55, 10.0)
    assert dienst.anfragen == ["Hamburg, Deutschland"], "der Rohstring ging an den Dienst"


def test_1158_ein_falscher_merker_unter_dem_rohschluessel_wird_nicht_mehr_gelesen(ortsdienst):
    """Der Altbestand: 'Hamburg (hybrid), remote möglich' stand dauerhaft bei Mainz im Speicher."""
    geo, dienst = ortsdienst
    geo._geo_cache["hamburg (hybrid), remote möglich"] = (50.0, 8.27)
    assert geo.geocode_location("Hamburg (hybrid), remote möglich") == (53.55, 10.0)


def test_1158_gemerkt_wird_unter_dem_bereinigten_schluessel(ortsdienst):
    geo, dienst = ortsdienst
    geo.geocode_location("Hamburg (hybrid), remote möglich")
    assert "hamburg" in geo._geo_cache and "hamburg (hybrid), remote möglich" not in geo._geo_cache
    geo.geocode_location("Hamburg")
    geo.geocode_location("Hamburg, remote möglich")
    assert dienst.anfragen == ["Hamburg, Deutschland"], "dieselbe Stadt wurde mehrfach gefragt"


@pytest.mark.parametrize("text", ["Remote möglich", "Homeoffice möglich", "Deutschland", "hybrid", "Bundesweit"])
def test_1158_ein_text_ohne_ort_wird_nicht_verortet(ortsdienst, text):
    geo, dienst = ortsdienst
    assert geo.geocode_location(text) is None
    assert dienst.anfragen == []


def test_1158_findet_der_dienst_den_bereinigten_ort_nicht_gibt_es_keine_entfernung(ortsdienst):
    """Besser unbekannt als erfunden: kein Rückgriff auf den Rohstring."""
    geo, dienst = ortsdienst
    dienst.antworten = {"Hamburg (hybrid), remote möglich, Deutschland": (50.0, 8.27)}
    assert geo.geocode_location("Hamburg (hybrid), remote möglich") is None
    assert dienst.anfragen == ["Hamburg, Deutschland", "Hamburg"]


# ══ Die Oberfläche ═════════════════════════════════════════════════════════════

def _seite():
    return JOBS_PAGE.read_text(encoding="utf-8-sig")


def _ohne_kommentare(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def _standard():
    block = re.search(r"export const FILTER_STANDARD = \{(.*?)\n\};", _ohne_kommentare(_seite()), re.S)
    assert block, "FILTER_STANDARD fehlt"
    felder = {}
    for zeile in block.group(1).splitlines():
        m = re.match(r"\s*(\w+):\s*(.+?),?\s*$", zeile)
        if m:
            felder[m.group(1)] = m.group(2)
    return felder


def test_1158_die_seite_startet_und_setzt_zurueck_ohne_einschraenkung():
    f = _standard()
    assert f["minScore"] == '""'
    assert f["rahmenAusblenden"] == "false" and f["schwelleAusblenden"] == "false"
    assert f["hideApplied"] == "true", "eine Stelle mit laufender Bewerbung ist keine offene Stelle"
    for neutral in ("query", "source", "remote", "employmentType", "arbeitsumfang", "pruefstand"):
        assert f[neutral] == '""', neutral
    for aus in ("salaryOnly", "missingDescriptionOnly"):
        assert f[aus] == "false", aus


def test_1158_die_form_des_zuruecksetzens_entspricht_dem_test_der_anforderung():
    """`ZURUECKGESETZT` oben ist genau das, was die Seite aus FILTER_STANDARD schickt."""
    f = _standard()
    gesendet = {}
    if f["hideApplied"] == "true":
        gesendet["beworbene_ausblenden"] = "true"
    if f["rahmenAusblenden"] == "false":
        gesendet["rahmen_ausblenden"] = "false"
    if f["schwelleAusblenden"] == "false":
        gesendet["schwelle_ausblenden"] = "false"
    assert gesendet == ZURUECKGESETZT
    assert f["minScore"] == '""', "eine Untergrenze würde mitgeschickt"


def test_1158_die_top_stellen_des_dashboards_behalten_rahmen_und_schwelle():
    quelle = _ohne_kommentare(_seite())
    block = re.search(r"export const FILTER_TOP_STELLEN = \{(.*?)\};", quelle, re.S).group(1)
    assert "...FILTER_STANDARD" in block
    assert "rahmenAusblenden: true" in block and "schwelleAusblenden: true" in block
    dash = DASHBOARD_PAGE.read_text(encoding="utf-8-sig")
    assert 'listenParameter(FILTER_TOP_STELLEN, "", "", "active")' in dash
    assert "FILTER_STANDARD" not in dash


def test_1158_negative_werte_und_null_gehen_an_den_server():
    quelle = _ohne_kommentare(_seite())
    assert "minScoreParameter(filters.minScore)" in quelle
    assert "Number(filters.minScore || 0) > 0" not in quelle, "die alte Bedingung verschluckt 0 und negative Werte"
    assert "minScoreGesetzt(filters.minScore)" in quelle


def test_1158_der_streifen_nennt_jeden_filter_mit_zahl_und_die_mehrfachen():
    quelle = _ohne_kommentare(_seite())
    # Jeder wirksame Filter kommt in die Liste des Streifens - auch eine Untergrenze von 0 oder darunter.
    assert 'if (minScoreGesetzt(filters.minScore)) aktiv.push({ schluessel: "minScore"' in quelle
    assert 'if (filters.rahmenAusblenden) aktiv.push({ schluessel: "rahmenAusblenden"' in quelle
    assert 'if (filters.schwelleAusblenden) aktiv.push({ schluessel: "schwelleAusblenden"' in quelle
    assert 'if (filters.hideApplied) aktiv.push({ schluessel: "hideApplied"' in quelle
    assert "mitZahlen(aktiveFilter, ansichtMeta.verborgen)" in quelle
    assert "mehrereFilter(ansichtMeta.offen_verborgen, ansichtMeta.verborgen)" in quelle
    assert "durch mehrere Filter zugleich" in quelle


def test_1158_der_filterzustand_wird_gemerkt():
    quelle = _ohne_kommentare(_seite())
    # Lesen beim Öffnen: gibt es einen gemerkten Zustand, gilt er - die ganze Bedingung, nicht nur ihre Teile.
    assert "const gemerkt = localStorage.getItem(SPEICHER_SCHLUESSEL);" in quelle
    assert "if (gemerkt) return filterAusSpeicher(gemerkt, FILTER_STANDARD);" in quelle
    # Schreiben bei JEDER Änderung der Filter (Abhängigkeit [filters], sonst bliebe der erste Stand stehen).
    assert re.search(
        r"useEffect\(\(\) => \{\s*try \{\s*localStorage\.setItem\(SPEICHER_SCHLUESSEL, "
        r"filterFuerSpeicher\(filters\)\);.*?\}, \[filters\]\);", quelle, re.S)


def test_1158_tab_und_kachel_zaehlen_die_offenen_stellen():
    quelle = _ohne_kommentare(_seite())
    assert "setJobsTotal(aktiv.offen)" in quelle
    assert "setJobsTotal(aktiv.total)" not in quelle
    assert 'filters.view === "active" ? ansichtMeta.offen : ansichtMeta.total' in quelle


def test_1158_der_node_test_laeuft_in_der_ci():
    ci = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "node frontend/src/lib/stellenFilter.test.mjs" in ci


def test_1158_die_gebaute_oberflaeche_gehoert_zum_quelltext():
    assets = list((ROOT / "src" / "bewerbungs_assistent" / "static" / "dashboard" / "assets").glob("index-*.js"))
    assert assets and any("durch mehrere Filter zugleich" in a.read_text(encoding="utf-8") for a in assets), \
        "die Oberfläche wurde nach der Änderung nicht neu gebaut (pnpm exec vite build)"


# ── Die Laufkarte der Suche zählt „verschiedene Orte“ mit demselben Schlüssel wie der Dienst ─────────────────

def _ortsstelle(nr, ort):
    return {"hash": f"o{nr:03d}", "title": f"Beispielstelle {nr}", "company": f"Beispiel GmbH {nr}",
            "location": ort, "description": "Beschreibung. " * 10}


def test_1158_der_schluessel_ist_der_bereinigte_ort_in_kleinschrift():
    from bewerbungs_assistent.services.geocoding_service import ort_fuer_abfrage, ort_schluessel
    assert ort_fuer_abfrage("Hamburg (hybrid), remote möglich") == "Hamburg"
    assert ort_schluessel("Hamburg (hybrid), remote möglich") == "hamburg"
    assert ort_schluessel("HAMBURG ") == ort_schluessel("Hamburg, Homeoffice möglich") == "hamburg"
    for kein_ort in ("", "   ", "Remote möglich", "Remote (United States)", "Homeoffice", "Bundesweit", "hybrid"):
        assert ort_schluessel(kein_ort) == "", kein_ort


def test_1158_die_laufkarte_zaehlt_dieselbe_stadt_in_allen_schreibweisen_einmal():
    from bewerbungs_assistent.job_scraper import geocoding_auswahl
    stellen = [_ortsstelle(1, "Hamburg"),
               _ortsstelle(2, "Hamburg (hybrid), remote möglich"),
               _ortsstelle(3, "hamburg, Homeoffice möglich"),
               _ortsstelle(4, "Remote möglich"),
               _ortsstelle(5, "Berlin")]
    auswahl, orte, ko = geocoding_auswahl(stellen, {})
    assert len(auswahl) == 5 and ko == 0
    assert orte == 2, "Hamburg (dreimal) und Berlin; 'Remote möglich' fragt niemand"


# ── Ein angehängtes Land ändert die Abfrage nicht: bekannte Orte werden nicht neu gefragt ─────────────────────

def test_1158_ein_land_am_ende_nutzt_den_alten_merker(ortsdienst):
    """Die meisten Orte aus JobSpy enden auf ', Germany'. Ihre Antworten stehen unter dem alten Schlüssel."""
    geo, dienst = ortsdienst
    geo._geo_cache["hamburg, hamburg, germany"] = (53.5, 10.0)
    assert geo.geocode_location("Hamburg, Hamburg, Germany") == (53.5, 10.0)
    assert dienst.anfragen == [], "dieselbe Abfrage wie vor #1158: kein neuer Weg zum Dienst"
    assert geo._geo_cache["hamburg, hamburg"] == (53.5, 10.0), "und ab jetzt auch unter dem neuen Schlüssel"


def test_1158_ein_alter_merker_gilt_nicht_wenn_mehr_als_das_land_abgeschnitten_wurde(ortsdienst):
    geo, dienst = ortsdienst
    geo._geo_cache["hamburg (hybrid), remote möglich, deutschland"] = (50.0, 8.27)    # der alte Fehlmerker
    assert geo.geocode_location("Hamburg (hybrid), remote möglich, Deutschland") == (53.55, 10.0)
    assert dienst.anfragen == ["Hamburg, Deutschland"]


def test_1158_auch_ein_dauerhafter_merker_unter_dem_alten_schluessel_gilt_weiter(ortsdienst, tmp_path, monkeypatch):
    geo, dienst = ortsdienst
    import bewerbungs_assistent.database as _db_mod
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    datenbank = _db_mod.Database(db_path=tmp_path / "geo.db")
    datenbank.initialize()
    try:
        geo.speicher_setzen(datenbank)
        geo._in_speicher("hamburg, hamburg, germany", (53.5, 10.0))
        geo._geo_cache.clear()
        assert geo.geocode_location("Hamburg, Hamburg, Germany") == (53.5, 10.0)
        assert dienst.anfragen == []
    finally:
        geo.speicher_setzen(None)
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


@pytest.mark.parametrize("roh,ziel,erwartet", [
    ("Hamburg, Hamburg, Germany", "Hamburg, Hamburg", True),
    ("Hamburg, Deutschland", "Hamburg", True),
    ("Hamburg Germany", "Hamburg", True),
    ("Hamburg (hybrid), remote möglich, Deutschland", "Hamburg", False),
    ("Hamburg, Germany (hybrid)", "Hamburg", False),
    ("Germany", "", False),
    ("", "", False),
])
def test_1158_nur_das_land_am_ende_zaehlt_als_land_nur_entfernt(roh, ziel, erwartet):
    from bewerbungs_assistent.services.geocoding_service import nur_land_entfernt
    assert nur_land_entfernt(roh, ziel) is erwartet
