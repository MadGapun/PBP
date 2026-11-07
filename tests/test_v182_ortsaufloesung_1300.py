"""#1300 - Ortsangaben wie "Hamburg u.a.", "Deutschland (remote)" und Mehrortangaben ergaben falsche Entfernungen.

Gemeldet an Browser-Uebernahmen vom 02. bis 05.11.2026 (Wohnort rund 20 km von Hamburg):
"Hamburg u.a." 218 km, "Deutschland (remote)" 619 km, "100 % remote (Frankfurt)" 8.425 km, und bei
"Deutschland (mostly remote; Frankfurt, Mannheim, Stuttgart, München)" stand im Feld eine andere Zahl als im Rahmen.

Der Ortsdienst ist ein Testdouble (kein Netz, kein Ollama). Firmen und Texte sind Platzhalter; die Orte sind
oeffentliche Geographie.
"""
from __future__ import annotations

import os
import threading
from types import SimpleNamespace

import pytest

HEIM = (53.58, 9.70)            # westlich von Hamburg
HAMBURG = (53.55, 10.0)
FFM = (50.11, 8.68)
MANNHEIM = (49.49, 8.47)
STUTTGART = (48.78, 9.18)
MUENCHEN = (48.14, 11.58)
UEBERSEE = (38.20, -84.87)      # ein Namensvetter in Uebersee
DEUTSCHLAND_MITTE = (51.16, 10.45)
IRGENDWO = (51.5, 7.5)          # was "Hamburg u.a." frueher traf


def _t(name, lat, lon, gewicht=0.7):
    return SimpleNamespace(latitude=lat, longitude=lon, raw={
        "class": "boundary", "type": "administrative", "importance": gewicht,
        "display_name": f"{name}, Deutschland"})


class _Dienst:
    """Ahmt Nominatim nach: je Anfrage eine feste Trefferliste; alle Anfragen werden gemerkt."""
    anfragen: list = []
    antworten: dict = {}

    def __init__(self, user_agent=None, timeout=None):
        pass

    def geocode(self, anfrage, exactly_one=True, limit=None):
        type(self).anfragen.append(anfrage)
        treffer = type(self).antworten.get(anfrage)
        if not treffer:
            return None
        return list(treffer) if not exactly_one else treffer[0]


@pytest.fixture
def dienst(monkeypatch):
    from bewerbungs_assistent.services import geocoding_service as geo
    geopy = pytest.importorskip("geopy.geocoders")
    _Dienst.anfragen = []
    _Dienst.antworten = {
        "Hamburg, Deutschland": [_t("Hamburg", *HAMBURG)],
        # So kam die alte Anfrage an: mit dem Zusatz - und traf etwas Fremdes.
        "Hamburg u.a., Deutschland": [_t("Irgendwo", *IRGENDWO)],
        "Deutschland, Deutschland": [_t("Deutschland", *DEUTSCHLAND_MITTE)],
        "Frankfurt, Deutschland": [_t("Frankfurt am Main", *FFM)],
        "Mannheim, Deutschland": [_t("Mannheim", *MANNHEIM)],
        "Stuttgart, Deutschland": [_t("Stuttgart", *STUTTGART)],
        "München, Deutschland": [_t("München", *MUENCHEN)],
        # Ein Ort, den der Dienst nur ohne Landeszusatz kennt - und dann in Uebersee.
        "Neuhausen am Fluss": [_t("Neuhausen am Fluss", *UEBERSEE)],
        "Paris": [_t("Paris", 48.86, 2.35)],
        "Kremotendorf, Deutschland": [_t("Kremotendorf", 52.0, 9.0)],
    }
    monkeypatch.setattr(geopy, "Nominatim", _Dienst)
    monkeypatch.setenv("PBP_GEOCODING", "1")
    monkeypatch.setattr(geo, "_speicher", None)
    monkeypatch.setattr(geo, "_rate_limit", lambda: None)
    geo._geo_cache.clear()
    geo._mehrdeutig_orte.clear()
    yield geo, _Dienst
    geo._geo_cache.clear()
    geo._mehrdeutig_orte.clear()


def _km(a, b):
    from bewerbungs_assistent.services.geocoding_service import calculate_distance_km
    return calculate_distance_km(a, b)


MEHRORT = "Deutschland (mostly remote; Frankfurt, Mannheim, Stuttgart, München)"


# ── Zerlegen (rein, ohne Netz) ──────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("text, orte, abfrage, remote, flaeche", [
    ("Hamburg u.a.", ["Hamburg"], ["Hamburg"], None, False),
    ("Hamburg u. a.", ["Hamburg"], ["Hamburg"], None, False),
    ("Hamburg u.a., Home Office", ["Hamburg"], ["Hamburg"], "teilweise", False),
    ("Hamburg, Homeoffice", ["Hamburg"], ["Hamburg"], "teilweise", False),
    ("Deutschland (remote)", [], [], "remote", True),
    ("100 % remote (Frankfurt)", ["Frankfurt"], [], "remote", False),
    (MEHRORT, ["Frankfurt", "Mannheim", "Stuttgart", "München"],
     ["Frankfurt", "Mannheim", "Stuttgart", "München"], "teilweise", True),
    ("Hamburg / Bremen", ["Hamburg", "Bremen"], ["Hamburg", "Bremen"], None, False),
    ("Hamburg; Bremen", ["Hamburg", "Bremen"], ["Hamburg", "Bremen"], None, False),
    ("Hamburg (hybrid)", ["Hamburg"], ["Hamburg"], "teilweise", False),
])
def test_die_meldung_zerlegt(text, orte, abfrage, remote, flaeche):
    from bewerbungs_assistent.services.geocoding_service import ort_zerlegen
    z = ort_zerlegen(text)
    assert (z["orte"], z["abfrage"], z["remote"], z["flaeche"]) == (orte, abfrage, remote, flaeche)


@pytest.mark.parametrize("text", ["Deutschland", "bundesweit", "Bundesweit", "DACH", "Germany", "Niedersachsen",
                                  "Deutschland, bundesweit"])
def test_ein_land_oder_raum_ist_kein_ort(text):
    from bewerbungs_assistent.services.geocoding_service import ort_fuer_abfrage, ort_zerlegen
    z = ort_zerlegen(text)
    assert z["abfrage"] == [] and z["flaeche"] is True
    assert ort_fuer_abfrage(text) == ""


@pytest.mark.parametrize("text, erwartet", [
    # Gegenrichtung: was wie ein Zusatz aussieht, aber zum Ort gehoert, bleibt.
    ("Kremotendorf", ["Kremotendorf"]),               # "remote" steckt im Namen
    ("Bau.a.-Siedlung", ["Bau.a.-Siedlung"]),         # "u.a." steckt im Namen
    ("Hamburg", ["Hamburg"]),                         # ein Stadtstaat ist ein Ort, keine Flaeche
    ("Hamburg, Hamburg, Germany", ["Hamburg, Hamburg"]),
    ("Aerzen, Niedersachsen (Hybrid)", ["Aerzen, Niedersachsen"]),     # #965: derselbe Schluessel wie vorher
    ("Frankfurt/Main", ["Frankfurt/Main"]),
    ("Frankfurt (Oder)", ["Frankfurt/Oder"]),
    ("Musterstraße 5, 22880 Wedel", ["Musterstraße 5, 22880 Wedel"]),  # eine Adresse, keine Ortsliste
    ("20095 Hamburg, Deutschland", ["20095 Hamburg"]),
    ("Bremen, Hamburg", ["Bremen", "Hamburg"]),
])
def test_was_zum_ort_gehoert_bleibt(text, erwartet):
    from bewerbungs_assistent.services.geocoding_service import ort_zerlegen
    assert ort_zerlegen(text)["orte"] == erwartet


@pytest.mark.parametrize("text", ["Remote", "Remote möglich", "Remote-Arbeit", "Home Office", "100% remote"])
def test_nur_remote_ist_kein_ort(text):
    from bewerbungs_assistent.services.geocoding_service import ort_fuer_abfrage
    assert ort_fuer_abfrage(text) == ""


def test_der_schluessel_bleibt_fuer_saubere_orte_gleich():
    """Kein neuer Schluessel fuer schon gemerkte Orte: sonst fragte PBP jeden bekannten Ort neu."""
    from bewerbungs_assistent.services.geocoding_service import ort_schluessel, ort_schluessel_alle
    assert ort_schluessel("Hamburg") == "hamburg"
    assert ort_schluessel("Hamburg (hybrid), remote möglich, Deutschland") == "hamburg"
    assert ort_schluessel_alle(MEHRORT) == ["frankfurt", "mannheim", "stuttgart", "münchen"]


# ── Aufloesen mit dem Testdouble ────────────────────────────────────────────────────────────────────────────────────

def test_hamburg_ua_ergibt_die_entfernung_nach_hamburg(dienst):
    geo, d = dienst
    for text in ("Hamburg u.a.", "Hamburg u.a., Home Office"):
        assert geo.geocode_and_calculate_distance(text, *HEIM) == _km(HEIM, HAMBURG)
    assert "Hamburg u.a., Deutschland" not in d.anfragen
    assert _km(HEIM, HAMBURG) < 30


def test_ein_land_mit_remote_hat_keine_punkt_entfernung(dienst):
    geo, d = dienst
    for text in ("Deutschland (remote)", "Deutschland", "bundesweit", "100 % remote (Frankfurt)"):
        assert geo.geocode_and_calculate_distance(text, *HEIM) is None, text
        assert geo.geocode_location(text) is None
    assert d.anfragen == []          # ein Land oder "remote" wird gar nicht erst gefragt
    assert geo.stellenort_aufloesen("Deutschland (remote)")["status"] == "remote"
    assert geo.stellenort_aufloesen("Deutschland")["status"] == "nur_flaeche"


def test_ein_treffer_in_uebersee_ist_ein_fehlschlag(dienst):
    geo, d = dienst
    fund = geo.stellenort_aufloesen("Neuhausen am Fluss", HEIM)
    assert fund["status"] == "ausserhalb_dach" and fund["koordinaten"] is None
    assert geo.geocode_and_calculate_distance("Neuhausen am Fluss", *HEIM) is None
    # Auch ein frueher gemerkter Treffer in Uebersee zaehlt nicht - die Pruefung gilt beim Lesen.
    geo._geo_cache["frankfurt"] = UEBERSEE
    assert geo.geocode_location("Frankfurt") is None
    assert geo.ort_auskunft("Frankfurt")["status"] == "ausserhalb_dach"


def test_ein_ausdruecklich_fremder_ort_behaelt_seine_zahl(dienst):
    """Gegenrichtung: "Paris" liegt wirklich ausserhalb - die grosse Zahl stimmt (#732 sortiert solche aus)."""
    geo, _d = dienst
    assert geo.geocode_and_calculate_distance("Paris", *HEIM) > 600


def test_mehrere_orte_der_naechste_zaehlt(dienst):
    geo, _d = dienst
    fund = geo.stellenort_aufloesen(MEHRORT, HEIM)
    assert fund["status"] == "gefunden" and fund["ort"] == "Frankfurt"
    assert fund["koordinaten"] == FFM and fund["km"] == _km(HEIM, FFM)
    assert geo.geocode_and_calculate_distance(MEHRORT, *HEIM) == _km(HEIM, FFM)
    assert geo.geocode_location(MEHRORT, HEIM) == FFM
    # Von Muenchen aus ist es Muenchen: der naechste haengt am Standort, nicht an der Reihenfolge.
    assert geo.stellenort_aufloesen(MEHRORT, MUENCHEN)["ort"] == "München"


def test_ohne_standort_nimmt_mehrort_den_ersten_gefundenen(dienst):
    geo, _d = dienst
    assert geo.geocode_location("Unbekanntheim / Mannheim / Frankfurt") == MANNHEIM


# ── Feld und Rahmen: eine Zahl ──────────────────────────────────────────────────────────────────────────────────────

def _kriterien(orte):
    return {"standort_lat": HEIM[0], "standort_lon": HEIM[1], "_standorte": orte,
            "max_entfernung": {"festanstellung": 50}}


def test_feld_und_rahmen_haben_dieselbe_zahl_bei_mehreren_orten(dienst):
    """Die Meldung: Feld 618,8 km, Rahmen 392,2 km. Jetzt eine Zahl, der naechste Ort."""
    geo, _d = dienst
    from bewerbungs_assistent.services import entfernung, rahmen
    job = {"location": MEHRORT, "description": "Standorte: Frankfurt, Mannheim, Stuttgart und München.",
           "distance_km": geo.geocode_and_calculate_distance(MEHRORT, *HEIM), "remote_level": "hybrid"}
    krit = _kriterien({"frankfurt": list(FFM), "mannheim": list(MANNHEIM), "münchen": list(MUENCHEN)})
    feld = entfernung.befund(job, krit)["entfernung_km"]
    assert feld == entfernung.preis_km(job, krit) == rahmen._entfernungs_befund(job, krit)["entfernung_km"]
    assert feld == _km(HEIM, FFM)


def test_ein_naeherer_standort_aus_der_anzeige_steht_auch_im_feld():
    """Die zweite Haelfte von Punkt 2: `naechster_standort` und `entfernung_km` aus EINER Wahl."""
    from bewerbungs_assistent.services import entfernung, rahmen
    job = {"location": "Frankfurt", "description": "Standorte: Frankfurt oder Hamburg.",
           "distance_km": _km(HEIM, FFM), "remote_level": "vor_ort"}
    krit = _kriterien({"hamburg": list(HAMBURG), "frankfurt": list(FFM)})
    b = entfernung.befund(job, krit)
    assert b["entfernung_km"] == entfernung.preis_km(job, krit) == rahmen._entfernungs_befund(job, krit)["entfernung_km"]
    assert b["entfernung_km"] < 30
    assert b["naechster_standort"]["ort"] == "Hamburg" and b["ortsfeld_km"] == _km(HEIM, FFM)
    assert "Hamburg" in b["entfernung_text"]


def test_ein_ort_aus_dem_feld_ist_kein_weiterer_standort():
    from bewerbungs_assistent.services import standorte
    job = {"location": "Deutschland (Frankfurt, Mannheim)", "description": "Standorte: Mannheim.",
           "distance_km": 900.0}
    krit = _kriterien({"mannheim": list(MANNHEIM)})
    assert standorte.naechster(job, krit) is None


# ── Unbekannt ist ein eigener Zustand ───────────────────────────────────────────────────────────────────────────────

def test_ein_land_ist_in_liste_und_fit_als_unbekannt_benannt(dienst):
    geo, _d = dienst
    from bewerbungs_assistent.job_scraper import entfernungs_guete
    from bewerbungs_assistent.services import entfernung, wahrheit
    job = {"location": "Deutschland", "remote_level": "unbekannt"}
    assert entfernung.befund(job, {}) == {}            # keine erfundene Zahl
    eintrag = wahrheit._entfernung(job, {})
    assert eintrag["guete"] == wahrheit.UNBEKANNT and eintrag["methode"] == "nur_flaeche"
    guete, grund = entfernungs_guete(job)
    assert guete == "unbekannt" and "Land oder einen Raum" in grund


def test_ein_fehlschlag_in_uebersee_ist_benannt(dienst):
    geo, _d = dienst
    from bewerbungs_assistent.job_scraper import entfernungs_guete
    from bewerbungs_assistent.services import rahmen, wahrheit
    geo.stellenort_aufloesen("Neuhausen am Fluss", HEIM)      # einmal gefragt, jetzt im Gedaechtnis
    job = {"location": "Neuhausen am Fluss", "remote_level": "vor_ort"}
    assert wahrheit._entfernung(job, {})["methode"] == "ort_unplausibel"
    guete, grund = entfernungs_guete(job)
    assert guete == "unbekannt" and "außerhalb" in grund
    befund = rahmen._entfernungs_befund(job, _kriterien({}))
    assert befund["belegt"] is False and "außerhalb" in befund["grund"]


def test_ein_unbekannter_ort_ohne_befund_bleibt_beim_alten_satz(dienst):
    """Gegenrichtung: ohne Gedaechtnis kein neuer Grund - der alte Satz steht."""
    from bewerbungs_assistent.job_scraper import entfernungs_guete
    guete, grund = entfernungs_guete({"location": "Nirgendwo", "remote_level": "vor_ort"})
    assert guete == "unbekannt" and "liess sich nicht" in grund


# ── Remote-Hinweis aus dem Ort ──────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ort, vorher, nachher", [
    ("Deutschland (remote)", "unbekannt", "remote"),
    ("Deutschland (remote)", "", "remote"),
    ("100 % remote (Frankfurt)", None, "remote"),
    ("Deutschland (remote)", "hybrid", "hybrid"),     # was die Quelle sagt, bleibt
    ("Deutschland (remote)", "vor_ort", "vor_ort"),
    ("Hamburg u.a., Home Office", "unbekannt", "unbekannt"),   # teilweise setzt nichts
    (MEHRORT, "unbekannt", "unbekannt"),
    ("Hamburg", "unbekannt", "unbekannt"),
])
def test_remote_aus_dem_ort_nur_wo_nichts_steht(ort, vorher, nachher):
    from bewerbungs_assistent.services.geocoding_service import remote_aus_ort
    job = {"location": ort, "remote_level": vorher}
    remote_aus_ort(job)
    assert job["remote_level"] == nachher


# ── Bestand: gespeicherte falsche Zahlen werden geheilt ─────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path, dienst):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.services import eigener_standort as es
    es._BEREINIGT_VERSUCHT.clear()
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.create_profile("Test", "test@example.com")
    d.set_search_criteria("standort_lat", HEIM[0])
    d.set_search_criteria("standort_lon", HEIM[1])
    yield d
    for t in threading.enumerate():
        if t.name.startswith("pbp-"):
            t.join(timeout=10)
    from bewerbungs_assistent.services import geocoding_service as geo
    geo.speicher_setzen(None)
    d.close()
    es._BEREINIGT_VERSUCHT.clear()
    os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, kennung, ort, km, lat=None, lon=None):
    db.save_jobs([{"hash": kennung, "title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                   "url": f"https://example.com/{kennung}", "source": "manuell",
                   "location": ort, "description": "x" * 80, "score": 3}])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE ?", (f"%{kennung}",)).fetchone()[0]
    db.connect().execute("UPDATE jobs SET distance_km=?, lat=?, lon=? WHERE hash=?", (km, lat, lon, voll))
    db.connect().commit()
    return voll


def _km_von(db, voll):
    return db.connect().execute("SELECT distance_km FROM jobs WHERE hash=?", (voll,)).fetchone()[0]


def test_der_bestand_wird_geheilt(db, dienst):
    from bewerbungs_assistent.services import eigener_standort as es
    ua = _stelle(db, "a1", "Hamburg u.a.", 218.2, *IRGENDWO)
    land = _stelle(db, "a2", "Deutschland (remote)", 618.8, *DEUTSCHLAND_MITTE)
    mehr = _stelle(db, "a3", MEHRORT, 618.8, *DEUTSCHLAND_MITTE)
    fern = _stelle(db, "a4", "Neuhausen am Fluss", 8425.1, *UEBERSEE)
    sauber = _stelle(db, "a5", "Hamburg", _km(HEIM, HAMBURG), *HAMBURG)
    es.entfernungen_bereinigen(db, max_orte=None)
    assert _km_von(db, ua) == _km(HEIM, HAMBURG)
    assert _km_von(db, land) is None
    assert _km_von(db, mehr) == _km(HEIM, FFM)
    assert _km_von(db, fern) is None
    assert _km_von(db, sauber) == _km(HEIM, HAMBURG)


# ── Der Weg der Meldung: Browser-Uebernahme ueber `stelle_manuell_anlegen`, dann Liste und Fit-Analyse ─────────────

@pytest.fixture
def server(tmp_path, dienst):
    import asyncio
    import importlib
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    d = _db_mod.Database()
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test"})
    d.set_search_criteria("standort_lat", HEIM[0])
    d.set_search_criteria("standort_lon", HEIM[1])

    def rufen(name, args):
        async def _run():
            tool = await _srv_mod.mcp.get_tool(name)
            res = await tool.run(args)
            return getattr(res, "structured_content", res)
        erg = asyncio.run(_run())
        return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg

    yield d, rufen
    for t in threading.enumerate():
        if t.name.startswith("pbp-"):
            t.join(timeout=10)
    from bewerbungs_assistent.services import geocoding_service as geo
    geo.speicher_setzen(None)
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _anlegen(rufen, ort, nr):
    erg = rufen("stelle_manuell_anlegen", {
        "titel": f"Sachbearbeitung Einkauf {nr} (m/w/d)", "firma": f"Musterbetrieb {nr} GmbH",
        "url": f"https://example.com/stelle/{nr}", "ort": ort, "remote": "unbekannt", "quelle": "manuell",
        "beschreibung": "Sie betreuen den Einkauf, pflegen Lieferantendaten und begleiten Ausschreibungen. " * 3})
    assert erg.get("status") == "angelegt", erg
    return erg["hash"]


def test_die_uebernahme_rechnet_wie_gemeldet_richtig(server):
    db, rufen = server
    ua = db.get_job(_anlegen(rufen, "Hamburg u.a., Home Office", 1))
    land = db.get_job(_anlegen(rufen, "Deutschland (remote)", 2))
    mehr = db.get_job(_anlegen(rufen, MEHRORT, 3))
    assert ua["distance_km"] == _km(HEIM, HAMBURG)
    assert land["distance_km"] is None and land["remote_level"] == "remote"
    assert mehr["distance_km"] == _km(HEIM, FFM) and (mehr["lat"], mehr["lon"]) == FFM
    assert ua["remote_level"] == "unbekannt"      # "Home Office" neben einem Ort setzt nichts


def test_ein_land_ohne_remote_ist_in_der_fit_analyse_unbekannt(server):
    db, rufen = server
    kennung = _anlegen(rufen, "Deutschland", 4)
    assert db.get_job(kennung)["distance_km"] is None
    fit = rufen("fit_analyse", {"job_hash": kennung})
    eintrag = fit["herkunft"]["entfernung"]
    assert eintrag["guete"] == "unbekannt" and eintrag["methode"] == "nur_flaeche"
    liste = rufen("stellen_anzeigen", {})
    zeilen = [z for z in (liste.get("stellen") or liste.get("jobs") or []) if "Musterbetrieb 4" in str(z)]
    assert zeilen and "entfernung_km" not in zeilen[0]
    assert "nur_flaeche" in zeilen[0].get("herkunft", "")
