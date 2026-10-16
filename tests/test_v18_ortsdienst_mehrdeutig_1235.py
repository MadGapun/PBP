"""#1235 - der Ortsdienst nahm bei einem mehrdeutigen Ortsnamen still den erstbesten Treffer.

Gemeldet am 16.10.2026: eine Stelle mit Ort "Rosengarten" stand mit 24 km Luftlinie "innerhalb der Grenze" in der
Liste. Die Anzeige beim Arbeitgeber nannte 74538 Rosengarten in Baden-Württemberg, rund 500 km entfernt. PBP hatte das
gleichnamige Rosengarten im Landkreis Harburg genommen (`exactly_one=True`), ohne Hinweis.

Die Gewichte in den Testdaten sind GEMESSEN (Nominatim, 16.10.2026, Abfragen im Sekundentakt von Hand, nicht in der
Suite): mehrdeutig waren Neuenkirchen, Rosengarten, Lichtenau, Hohenfelde und Neustadt (Abstand der Gewichte höchstens
0,061), eindeutig Offenbach, Frankfurt, Halle, Freiburg und "Rosengarten, Baden-Württemberg" (mindestens 0,136).

Der Ortsdienst ist ein Testdouble (kein Netz). Alle Firmen und Texte sind Platzhalter; die Orte sind öffentliche Geographie.
"""
from __future__ import annotations

import json
import os
import threading
from types import SimpleNamespace

import pytest

HAMBURG = (53.55, 10.0)
HARBURG = (53.40, 9.98)         # Rosengarten, Landkreis Harburg, Niedersachsen
HALL = (49.10, 9.80)            # Rosengarten, Landkreis Schwäbisch Hall, Baden-Württemberg
FFM = (50.11, 8.68)
FFO = (52.35, 14.55)


def _t(name, lat, lon, gewicht, klasse="boundary", typ="administrative"):
    """Ein Treffer des Ortsdienstes, wie ihn geopy liefert (Koordinaten und `raw`)."""
    return SimpleNamespace(latitude=lat, longitude=lon, raw={
        "class": klasse, "type": typ, "importance": gewicht, "display_name": f"{name}, 12345, Deutschland"})


def _rosengarten():
    return [
        _t("Rosengarten, Landkreis Harburg, Niedersachsen", *HARBURG, 0.426),
        _t("Rosengarten, VVG der Stadt Schwäbisch Hall, Landkreis Schwäbisch Hall, Baden-Württemberg", *HALL, 0.420),
        _t("Rosengarten, Creidlitz, Coburg, Bayern", 50.27, 10.96, 0.373, klasse="leisure", typ="park"),
        _t("Rosengarten, Frankfurt (Oder), Brandenburg", *FFO, 0.273, klasse="place", typ="village"),
    ]


def _plz(name, plz, lat, lon):
    return SimpleNamespace(latitude=lat, longitude=lon, raw={
        "class": "boundary", "type": "postal_code", "importance": 0.12,
        "display_name": f"{plz}, {name}, Deutschland"})


# ── die Auswertung der Treffer (rein) ───────────────────────────────────────────────────────────────────────────────

def test_rosengarten_ist_mehrdeutig_und_nennt_nur_orte():
    from bewerbungs_assistent.services.geocoding_service import _ortsfund
    fund = _ortsfund(_rosengarten())
    assert fund["status"] == "mehrdeutig"
    namen = [k["name"] for k in fund["kandidaten"]]
    assert len(namen) == 2
    assert any("Landkreis Harburg" in n for n in namen) and any("Schwäbisch Hall" in n for n in namen)
    assert all("Coburg" not in n and "Oder" not in n for n in namen), "ein Park ist kein Ort; ein viel leichterer Treffer kein Gegner"
    assert all("12345" not in n and "Deutschland" not in n for n in namen)
    assert "koordinaten" not in fund, "bei einem mehrdeutigen Ort gibt es keine Koordinaten"


@pytest.mark.parametrize("name, treffer, erwartet", [
    ("Frankfurt", [_t("Frankfurt am Main, Hessen", *FFM, 0.758), _t("Frankfurt (Oder), Brandenburg", *FFO, 0.618)], FFM),
    ("Halle", [_t("Halle (Saale), Sachsen-Anhalt", 51.48, 11.97, 0.666),
               _t("Halle (Westf.), Nordrhein-Westfalen", 52.06, 8.36, 0.502),
               _t("Halle, Niedersachsen", 51.89, 9.55, 0.414)], (51.48, 11.97)),
    ("Offenbach", [_t("Offenbach am Main, Hessen", 50.10, 8.77, 0.598),
                   _t("Offenbach an der Queich, Rheinland-Pfalz", 49.20, 8.17, 0.462)], (50.10, 8.77)),
    ("Freiburg", [_t("Freiburg im Breisgau, Baden-Württemberg", 47.99, 7.85, 0.678),
                  _t("Freiburg (Elbe), Niedersachsen", 53.83, 9.28, 0.427)], (47.99, 7.85)),
    ("Rosengarten, Baden-Württemberg",
     [_t("Rosengarten, Landkreis Schwäbisch Hall, Baden-Württemberg", *HALL, 0.420),
      _t("Rosengarten, Ettenkirch, Friedrichshafen", 47.65, 9.50, 0.133, klasse="place", typ="hamlet"),
      _t("Rosengarten, Berkach, Ehingen (Donau)", 48.28, 9.73, 0.133, klasse="place", typ="hamlet")], HALL),
])
def test_ein_klarer_spitzenreiter_ist_eindeutig(name, treffer, erwartet):
    """Frankfurt und Halle gibt es mehrfach - aber eine Stadt wiegt klar mehr. Das Gegenstueck zu Rosengarten."""
    from bewerbungs_assistent.services.geocoding_service import _ortsfund
    fund = _ortsfund(treffer)
    assert fund["status"] == "gefunden", name
    assert fund["koordinaten"] == erwartet


def test_neustadt_und_die_anderen_gleichgewichtigen_sind_mehrdeutig():
    from bewerbungs_assistent.services.geocoding_service import _ortsfund
    neustadt = [_t("Neustadt an der Weinstraße", 49.35, 8.14, 0.551), _t("Neustadt am Rübenberge", 52.50, 9.46, 0.490),
                _t("Neustadt in Holstein", 54.10, 10.81, 0.488)]
    assert _ortsfund(neustadt)["status"] == "mehrdeutig"
    neuenkirchen = [_t("Neuenkirchen, Vorpommern-Greifswald", 53.96, 13.28, 0.492),
                    _t("Neuenkirchen, Kreis Dithmarschen", 54.18, 9.17, 0.492)]
    assert _ortsfund(neuenkirchen)["status"] == "mehrdeutig"


def test_dieselbe_gemeinde_als_ortsteil_zaehlt_einmal():
    """Lichtenau bei Paderborn kommt als Gemeinde UND als Ortsteil - ein Kandidat, nicht zwei."""
    from bewerbungs_assistent.services.geocoding_service import _ortsfund
    fund = _ortsfund([_t("Lichtenau, Landkreis Ansbach, Bayern", 49.28, 10.61, 0.464),
                      _t("Lichtenau, Kreis Paderborn, NRW", 51.62, 8.91, 0.455),
                      _t("Lichtenau, Kreis Paderborn, NRW", 51.621, 8.911, 0.455, typ="administrative")])
    assert fund["status"] == "mehrdeutig"
    assert len(fund["kandidaten"]) == 2


def test_nur_ein_treffer_oder_gar_keiner():
    from bewerbungs_assistent.services.geocoding_service import _ortsfund
    assert _ortsfund([])["status"] == "nicht_gefunden"
    assert _ortsfund(None)["status"] == "nicht_gefunden"
    eins = _ortsfund([_plz("Rosengarten", "74538", *HALL)])
    assert eins == {"status": "gefunden", "koordinaten": HALL}


def test_treffer_ohne_ortsklasse_bleiben_wie_vorher():
    """Eine Strasse oder ein Gebaeude: keine Mehrdeutigkeits-Pruefung, der erste Treffer gilt wie bisher."""
    from bewerbungs_assistent.services.geocoding_service import _ortsfund
    fund = _ortsfund([_t("Hauptstrasse 5", 53.5, 10.0, 0.3, klasse="highway", typ="residential"),
                      _t("Hauptstrasse 5", 48.1, 11.5, 0.3, klasse="highway", typ="residential")])
    assert fund == {"status": "gefunden", "koordinaten": (53.5, 10.0)}


def test_liegen_die_gleichnamigen_nah_beieinander_ist_es_derselbe_ort():
    from bewerbungs_assistent.services.geocoding_service import _ortsfund
    fund = _ortsfund([_t("Hohenfelde, Plön", 54.30, 10.40, 0.464), _t("Hohenfelde, Stormarn", 53.65, 10.30, 0.444)])
    # 72 km auseinander: zwei Orte. Dieselbe Rechnung mit 30 km:
    assert fund["status"] == "mehrdeutig"
    nah = _ortsfund([_t("Hohenfelde, A", 54.00, 10.00, 0.464), _t("Hohenfelde, B", 54.20, 10.10, 0.444)])
    assert nah["status"] == "gefunden"


def test_fehlt_das_gewicht_gilt_der_vorsichtige_fall():
    """Ohne `importance` (aelterer Dienst) weiss PBP nicht, welcher Ort schwerer wiegt - es rät nicht."""
    from bewerbungs_assistent.services.geocoding_service import _ortsfund
    a = SimpleNamespace(latitude=53.4, longitude=9.98, raw={"class": "boundary", "type": "administrative", "display_name": "X, A"})
    b = SimpleNamespace(latitude=49.1, longitude=9.8, raw={"class": "boundary", "type": "administrative", "display_name": "X, B"})
    assert _ortsfund([a, b])["status"] == "mehrdeutig"


# ── der Dienst (Testdouble) ─────────────────────────────────────────────────────────────────────────────────────────

class _Dienst:
    """Ahmt Nominatim nach: je Anfrage eine feste Trefferliste, alle Anfragen werden gemerkt."""
    anfragen: list = []
    antworten: dict = {}
    ausfall = False

    def __init__(self, user_agent=None, timeout=None):
        pass

    def geocode(self, anfrage, exactly_one=True, limit=None):
        type(self).anfragen.append(anfrage)
        if type(self).ausfall:
            from geopy.exc import GeocoderServiceError
            raise GeocoderServiceError("Dienst nicht erreichbar")
        treffer = type(self).antworten.get(anfrage)
        if not treffer:
            return None
        return list(treffer) if not exactly_one else treffer[0]


@pytest.fixture
def dienst(monkeypatch):
    from bewerbungs_assistent.services import geocoding_service as geo
    geopy = pytest.importorskip("geopy.geocoders")
    _Dienst.anfragen = []
    _Dienst.ausfall = False
    _Dienst.antworten = {
        "Rosengarten, Deutschland": _rosengarten(),
        "74538 Rosengarten, Deutschland": [_plz("Rosengarten", "74538", *HALL)],
        "21224 Rosengarten, Deutschland": [_plz("Rosengarten", "21224", *HARBURG)],
        "Rosengarten, Baden-Württemberg, Deutschland": [
            _t("Rosengarten, Landkreis Schwäbisch Hall, Baden-Württemberg", *HALL, 0.420),
            _t("Rosengarten, Ettenkirch", 47.65, 9.50, 0.133, klasse="place", typ="hamlet")],
        "Frankfurt, Deutschland": [_t("Frankfurt am Main", *FFM, 0.758), _t("Frankfurt (Oder)", *FFO, 0.618)],
        "Hamburg, Deutschland": [_t("Hamburg", *HAMBURG, 0.788)],
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


def test_rosengarten_ohne_zusatz_hat_keine_koordinaten_nur_kandidaten(dienst):
    geo, d = dienst
    assert geo.geocode_location("Rosengarten") is None
    fund = geo.geocode_ort("Rosengarten")
    assert fund["status"] == "mehrdeutig" and fund["koordinaten"] is None
    assert len(fund["kandidaten"]) == 2
    assert d.anfragen == ["Rosengarten, Deutschland"], "eine Anfrage, danach aus dem Gedaechtnis"


def test_die_gegenprobe_der_meldung_zwei_plz_zwei_entfernungen(dienst):
    """AK 5: '74538 Rosengarten' und '21224 Rosengarten' ergeben zwei verschiedene, plausible Entfernungen."""
    geo, _ = dienst
    nord = geo.geocode_location("21224 Rosengarten")
    sued = geo.geocode_location("74538 Rosengarten")
    assert nord == HARBURG and sued == HALL
    assert _km(HAMBURG, nord) < 30 and _km(HAMBURG, sued) > 450


def test_ein_bundesland_im_ort_loest_auf(dienst):
    geo, _ = dienst
    assert geo.geocode_location("Rosengarten, Baden-Württemberg") == HALL


def test_grosse_staedte_bleiben_aufgeloest(dienst):
    geo, _ = dienst
    assert geo.geocode_location("Frankfurt") == FFM
    assert geo.geocode_location("Hamburg") == HAMBURG


def test_die_kandidaten_kommen_ohne_netz_aus_dem_gedaechtnis(dienst):
    geo, d = dienst
    assert geo.mehrdeutigkeit("Rosengarten") is None, "noch nie gefragt: nichts zu sagen, und kein Netz"
    assert d.anfragen == []
    geo.geocode_location("Rosengarten")
    kandidaten = geo.mehrdeutigkeit("Rosengarten")
    assert len(kandidaten) == 2 and {"name", "lat", "lon"} <= set(kandidaten[0])
    assert len(d.anfragen) == 1
    assert geo.mehrdeutigkeit("Frankfurt") is None


def test_ein_ausfall_des_dienstes_wird_nicht_gemerkt(dienst):
    geo, d = dienst
    d.ausfall = True
    fund = geo.geocode_ort("Rosengarten")
    assert fund["status"] == "nicht_erreichbar" and fund["koordinaten"] is None
    assert "rosengarten" not in geo._geo_cache and not geo._mehrdeutig_orte
    d.ausfall = False
    assert geo.geocode_ort("Rosengarten")["status"] == "mehrdeutig"


def test_die_testsperre_fragt_nichts(dienst, monkeypatch):
    geo, d = dienst
    monkeypatch.setenv("PBP_GEOCODING", "0")
    assert geo.geocode_ort("Rosengarten")["status"] == "nicht_erreichbar"
    assert d.anfragen == []


# ── der Ort steht in der Anzeige ────────────────────────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("ort, text, erwartet", [
    ("Rosengarten", "Ihr Einsatzort: 74538 Rosengarten, Hohenloher Strasse 1.", "74538 Rosengarten"),
    ("Rosengarten", "Standort 74538   Rosengarten.", "74538 Rosengarten"),
    ("rosengarten", "Wir sitzen in 74538 ROSENGARTEN", "74538 rosengarten"),
    ("Rosengarten", "Zentrale: 20095 Hamburg, Werk: 74538 Rosengarten", "74538 Rosengarten"),
    ("Rosengarten", "Rosengarten (Baden-Württemberg) liegt bei Schwäbisch Hall", "Rosengarten, Baden-Württemberg"),
    ("Rosengarten", "Standort Rosengarten, Baden-Wuerttemberg", "Rosengarten, Baden-Württemberg"),
    ("Rosengarten", "Wir sind in Rosengarten in Niedersachsen zuhause", "Rosengarten, Niedersachsen"),
    ("Neustadt", "Büro in Neustadt, Sachsen-Anhalt", "Neustadt, Sachsen-Anhalt"),
    ("Neustadt", "Büro in Neustadt Sachsen", "Neustadt, Sachsen"),
])
def test_die_anzeige_nennt_plz_oder_bundesland_direkt_hinter_dem_namen(ort, text, erwartet):
    from bewerbungs_assistent.services.geocoding_service import ort_aus_anzeige
    assert ort_aus_anzeige(ort, text) == erwartet


@pytest.mark.parametrize("ort, text", [
    ("Rosengarten", ""),
    ("", "74538 Rosengarten"),
    ("Rosengarten", "Zentrale: 20095 Hamburg, remote möglich"),                                 # keine Angabe zum Ort
    ("Rosengarten", "Werke in 74538 Rosengarten und 21224 Rosengarten"),                         # zwei verschiedene
    ("Rosengarten", "Standorte: Rosengarten (Bayern) und Rosengarten (Hessen)"),                 # zwei Laender
    ("Rosengarten", "Geschaeftsstelle 74538 Altrosengarten"),                                    # anderer Name
    ("Rosengarten", "Postfach 74538 in Hamburg, Rosengarten ist die Marke"),                      # PLZ nicht am Namen
    ("Ro", "74538 Ro"),                                                                          # zu kurz fuer eine Aussage
])
def test_ohne_eindeutige_angabe_raet_die_anzeige_nichts(ort, text):
    from bewerbungs_assistent.services.geocoding_service import ort_aus_anzeige
    assert ort_aus_anzeige(ort, text) == ""


def test_die_anzeige_loest_einen_mehrdeutigen_ort_auf(dienst):
    geo, d = dienst
    fund = geo.geocode_ort("Rosengarten", "Einsatzort: 74538 Rosengarten.")
    assert fund["status"] == "gefunden" and fund["koordinaten"] == HALL
    assert fund["aufgeloest_durch"] == "74538 Rosengarten"
    assert d.anfragen == ["Rosengarten, Deutschland", "74538 Rosengarten, Deutschland"]
    # Ohne passende Angabe bleibt er mehrdeutig - und der Name allein ist weiter gemerkt, nicht aufgeloest.
    assert geo.geocode_ort("Rosengarten", "kein Hinweis auf den Ort")["status"] == "mehrdeutig"
    assert geo.geocode_location("Rosengarten") is None


def test_entfernung_aus_anzeige_ist_nur_der_zweite_versuch(dienst):
    geo, d = dienst
    # Ein Ort, der eindeutig ist, braucht ihn nicht (und die Anzeige wird nicht befragt).
    assert geo.geocode_location("Frankfurt") == FFM
    assert geo.entfernung_aus_anzeige("Frankfurt", *HAMBURG, "74538 Frankfurt") is None
    # Ein mehrdeutiger, den die Anzeige klaert:
    assert geo.geocode_location("Rosengarten") is None
    erg = geo.entfernung_aus_anzeige("Rosengarten", *HAMBURG, "Werk 74538 Rosengarten")
    assert erg["koordinaten"] == HALL and erg["aufgeloest_durch"] == "74538 Rosengarten"
    assert erg["km"] == _km(HAMBURG, HALL) and erg["km"] > 450
    # Ohne Anzeige, ohne Standort, ohne dass der Ort mehrdeutig ist: nichts.
    assert geo.entfernung_aus_anzeige("Rosengarten", *HAMBURG, "") is None
    assert geo.entfernung_aus_anzeige("Rosengarten", 0, 0, "74538 Rosengarten") is None
    assert geo.entfernung_aus_anzeige("Nirgendwo", *HAMBURG, "74538 Nirgendwo") is None


# ── das Gedaechtnis ueber Neustarts ─────────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def db(tmp_path, monkeypatch, dienst):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    from bewerbungs_assistent.services import eigener_standort as es
    es._BEREINIGT_VERSUCHT.clear()
    es._MEHRDEUTIG_VERSUCHT.clear()
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.create_profile("Test", "test@example.com")
    yield d
    for t in threading.enumerate():
        if t.name.startswith("pbp-"):
            t.join(timeout=10)
    from bewerbungs_assistent.services import geocoding_service as geo
    geo.speicher_setzen(None)
    d.close()
    es._MEHRDEUTIG_VERSUCHT.clear()
    os.environ.pop("BA_DATA_DIR", None)


def test_die_geo_tabelle_hat_stand_und_kandidaten(db):
    spalten = {r[1] for r in db.connect().execute("PRAGMA table_info(geo_cache)").fetchall()}
    assert {"stand", "kandidaten"} <= spalten


def test_die_spalten_kommen_auch_in_eine_alte_datenbank(db):
    """Additiv und ohne Schema-Sprung: eine Tabelle von v1.7.x bekommt die Spalten beim naechsten Start."""
    con = db.connect()
    con.execute("DROP TABLE geo_cache")
    con.execute("CREATE TABLE geo_cache (ort_key TEXT PRIMARY KEY, lat REAL, lon REAL, status TEXT NOT NULL, "
                "abgerufen_am TEXT)")
    con.execute("INSERT INTO geo_cache VALUES ('altort', 1.0, 2.0, 'gefunden', '2026-01-01')")
    con.commit()
    db.initialize()
    spalten = {r[1] for r in db.connect().execute("PRAGMA table_info(geo_cache)").fetchall()}
    assert {"stand", "kandidaten"} <= spalten
    assert db.connect().execute("SELECT lat FROM geo_cache WHERE ort_key='altort'").fetchone()[0] == 1.0


def test_ein_mehrdeutiger_ort_ueberlebt_den_neustart(db, dienst):
    geo, d = dienst
    geo.speicher_setzen(db)
    assert geo.geocode_location("Rosengarten") is None
    z = db.connect().execute("SELECT status, stand, kandidaten, lat FROM geo_cache WHERE ort_key='rosengarten'").fetchone()
    assert z[0] == "mehrdeutig" and z[1] == geo.SPEICHER_STAND and z[3] is None
    assert len(json.loads(z[2])) == 2
    geo._geo_cache.clear()
    geo._mehrdeutig_orte.clear()
    n = len(d.anfragen)
    assert len(geo.mehrdeutigkeit("Rosengarten")) == 2, "nach dem Neustart aus der Datenbank"
    assert geo.geocode_ort("Rosengarten")["status"] == "mehrdeutig"
    assert len(d.anfragen) == n, "keine neue Anfrage"


def test_ein_alter_merker_ohne_stand_wird_neu_gefragt(db, dienst):
    """Vor #1235 stand dort der ERSTE Treffer. Er kennt die Mehrdeutigkeit nicht - und bliebe sonst fuer immer."""
    geo, d = dienst
    geo.speicher_setzen(db)
    db.connect().execute("INSERT INTO geo_cache (ort_key, lat, lon, status, abgerufen_am) "
                         "VALUES ('rosengarten', ?, ?, 'gefunden', '2026-09-01')", HARBURG)
    db.connect().commit()
    assert geo._aus_speicher("rosengarten") == (False, None)
    assert geo.geocode_location("Rosengarten") is None, "nicht mehr der alte erste Treffer"
    assert d.anfragen == ["Rosengarten, Deutschland"]
    # Ein Merker mit Stand wird dagegen geglaubt.
    geo._in_speicher("hamburg", HAMBURG)
    assert geo._aus_speicher("hamburg") == (True, HAMBURG)
    # 'nicht gefunden' bleibt ein Befund.
    geo._in_speicher("nirgendwo", None)
    assert geo._aus_speicher("nirgendwo") == (True, None)


def test_eine_mehrdeutig_zeile_ohne_kandidaten_ist_kein_befund(db, dienst):
    geo, _ = dienst
    geo.speicher_setzen(db)
    db.connect().execute("INSERT INTO geo_cache (ort_key, status, stand) VALUES ('leerort', 'mehrdeutig', 2)")
    db.connect().commit()
    assert geo._aus_speicher("leerort") == (False, None)


# ── die Anzeige: warum fehlt die Entfernung? ────────────────────────────────────────────────────────────────────────

def test_herkunft_nennt_den_grund_und_die_kandidaten(db, dienst):
    geo, _ = dienst
    geo.speicher_setzen(db)
    geo.geocode_location("Rosengarten")
    from bewerbungs_assistent.services import wahrheit
    e = wahrheit.felder({"location": "Rosengarten", "description": "x" * 400})["entfernung"]
    assert e["guete"] == wahrheit.UNBEKANNT and e["methode"] == "ort_mehrdeutig"
    assert "mehrfach" in e["text"] and "Landkreis Harburg" in e["text"] and "Schwäbisch Hall" in e["text"]
    assert "PLZ" in e["text"]
    assert "ort_mehrdeutig" in wahrheit.kurz(wahrheit.felder({"location": "Rosengarten", "description": "x" * 400}))


def test_herkunft_ohne_befund_bleibt_wie_vorher(db, dienst):
    from bewerbungs_assistent.services import wahrheit
    e = wahrheit.felder({"location": "Rosengarten", "description": "x" * 400})["entfernung"]
    assert e["methode"] == "keine", "noch nie gefragt: kein Grund zu behaupten, der Ort sei mehrdeutig"
    assert wahrheit.felder({"location": "", "description": "x" * 400})["entfernung"]["methode"] == "keine"
    mit = wahrheit.felder({"location": "Rosengarten", "distance_km": 12.0, "description": "x" * 400})["entfernung"]
    assert mit["methode"] == "luftlinie"


# ── der eigene Wohnort ──────────────────────────────────────────────────────────────────────────────────────────────

def test_ein_mehrdeutiger_wohnort_wird_benannt_statt_geraten(db, dienst):
    from bewerbungs_assistent.services import eigener_standort as es
    erg = es.eigenen_setzen(db, "Rosengarten", neu_rechnen=False)
    assert erg["status"] == "nicht_aufgeloest" and len(erg["mehrdeutig"]) == 2
    assert "mehrfach" in erg["hinweis"] and "PLZ" in erg["hinweis"] and "12345 Rosengarten" in erg["hinweis"]
    assert "standort_lat" not in (db.get_search_criteria() or {}) or not db.get_search_criteria().get("standort_lat")
    assert es.eigenen_setzen(db, "21224 Rosengarten", neu_rechnen=False)["status"] == "gesetzt"


def test_der_befund_nennt_die_kandidaten_des_wohnorts(db, dienst):
    from bewerbungs_assistent.services import eigener_standort as es
    db.save_profile({"name": "Test", "city": "Rosengarten"})
    for t in threading.enumerate():
        if t.name.startswith("pbp-standort"):
            t.join(timeout=10)
    b = es.befund(db)
    assert not b["aufgeloest"] and len(b.get("mehrdeutig") or []) == 2
    assert es.befund(db)["profil_wohnort"] == "Rosengarten"


def test_ein_aufgeloester_wohnort_hat_kein_mehrdeutig(db, dienst):
    from bewerbungs_assistent.services import eigener_standort as es
    es.eigenen_setzen(db, "Hamburg", neu_rechnen=False)
    assert "mehrdeutig" not in es.befund(db)


# ── der Bestand ─────────────────────────────────────────────────────────────────────────────────────────────────────

def _standort(db, ort="Hamburg"):
    from bewerbungs_assistent.services import eigener_standort as es
    assert es.eigenen_setzen(db, ort, neu_rechnen=False)["status"] == "gesetzt"


def _stelle(db, kennung, ort, km, text="Aufgaben im Einkauf. " * 20, quelle=None):
    db.save_jobs([{"hash": kennung, "title": "Sachbearbeitung", "company": "Musterbetrieb GmbH",
                   "url": f"https://beispiel.example/{kennung}", "source": "manuell",
                   "location": ort, "description": text, "score": 3}])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE ?", (f"%{kennung}",)).fetchone()[0]
    db.connect().execute("UPDATE jobs SET distance_km=?, lat=?, lon=?, entfernung_quelle=? WHERE hash=?",
                         (km, HARBURG[0] if km is not None else None, HARBURG[1] if km is not None else None,
                          quelle, voll))
    db.connect().commit()
    return voll


def _zeile(db, voll):
    return dict(db.connect().execute("SELECT * FROM jobs WHERE hash=?", (voll,)).fetchone())


def test_der_bestand_wird_geprueft_die_anzeige_klaert_der_rest_steht_auf_unbekannt(db, dienst):
    from bewerbungs_assistent.services import eigener_standort as es
    _standort(db)
    ohne = _stelle(db, "h1", "Rosengarten", 17.0)                                   # die Meldung: nah, aber geraten
    mit = _stelle(db, "h2", "Rosengarten", 17.0, text="Einsatzort: 74538 Rosengarten. " + "Aufgaben. " * 30)
    hand = _stelle(db, "h3", "Rosengarten", 5.0, quelle="mensch")                   # von Hand: bleibt
    eindeutig = _stelle(db, "h4", "Frankfurt", 300.0)                               # gross und klar: bleibt
    gross = _stelle(db, "h5", "Hamburg", 1.0)                                        # grosse Stadt: gar nicht gefragt
    plz = _stelle(db, "h6", "21224 Rosengarten", 17.0)                               # PLZ im Ort: gar nicht gefragt
    d = dienst[1]
    erg = es.entfernungen_mehrdeutige_pruefen(db)
    assert erg["status"] == "fertig" and erg["geklaert"] == 1 and erg["unbekannt"] == 1
    assert _zeile(db, ohne)["distance_km"] is None and _zeile(db, ohne)["lat"] is None, \
        "die geratene Entfernung steht nicht mehr als 'nah' da"
    z = _zeile(db, mit)
    assert z["distance_km"] == _km(HAMBURG, HALL) and z["distance_km"] > 450 and (z["lat"], z["lon"]) == HALL
    assert _zeile(db, hand)["distance_km"] == 5.0 and _zeile(db, hand)["entfernung_quelle"] == "mensch"
    assert _zeile(db, eindeutig)["distance_km"] == 300.0
    assert _zeile(db, gross)["distance_km"] == 1.0 and _zeile(db, plz)["distance_km"] == 17.0
    gefragt = [a for a in d.anfragen if a not in ("74538 Rosengarten, Deutschland",)]
    assert "Hamburg, Deutschland" not in gefragt[1:], "die grosse Stadt und der Ort mit PLZ wurden nicht eigens gefragt"
    assert not any(a.startswith("21224") for a in d.anfragen)
    # Ein zweiter Lauf fragt nichts mehr.
    n = len(d.anfragen)
    zwei = es.entfernungen_mehrdeutige_pruefen(db)
    assert len(d.anfragen) == n and zwei["orte"] == 0


def test_die_pruefung_ist_je_lauf_begrenzt(db, dienst):
    from bewerbungs_assistent.services import eigener_standort as es
    _standort(db)
    dienst[1].antworten["Musterdorf, Deutschland"] = [_t("Musterdorf", 52.0, 9.0, 0.4)]
    _stelle(db, "k1", "Rosengarten", 17.0)
    _stelle(db, "k2", "Musterdorf", 40.0)
    es.entfernungen_mehrdeutige_pruefen(db, max_orte=1)
    gefragt = [a for a in dienst[1].anfragen if a != "Hamburg, Deutschland"]
    assert len(gefragt) == 1, "ein Ort je Lauf"
    es.entfernungen_mehrdeutige_pruefen(db, max_orte=1)
    gefragt = [a for a in dienst[1].anfragen if a != "Hamburg, Deutschland"]
    assert len(gefragt) == 2, "der naechste Lauf nimmt den naechsten Ort"


def test_ein_ausfall_laesst_die_gespeicherte_zahl_stehen(db, dienst):
    from bewerbungs_assistent.services import eigener_standort as es
    _standort(db)
    voll = _stelle(db, "m1", "Rosengarten", 17.0)
    dienst[1].ausfall = True
    es.entfernungen_mehrdeutige_pruefen(db)
    assert _zeile(db, voll)["distance_km"] == 17.0, "ein Ausfall ist kein Befund ueber den Ort (#950)"


def test_nachholen_ruft_die_pruefung_und_rechnet_die_punkte_neu(db, dienst, monkeypatch):
    from bewerbungs_assistent.services import eigener_standort as es
    _standort(db)
    _stelle(db, "n1", "Rosengarten", 17.0)
    punkte = []
    monkeypatch.setattr(es, "_punkte_neu", lambda _db: punkte.append(1) or {"geaendert": 0})
    erg = es.nachholen(db)
    assert erg["bereinigt"] >= 1 and punkte, "geaenderte Entfernungen -> neue Punkte"


def test_neu_rechnen_klaert_oder_leert_mehrdeutige_orte(db, dienst):
    """Nach einem neuen Standort: die alte Zahl galt vom alten Wohnort aus - bei einem mehrdeutigen Ort steht sie nicht mehr."""
    from bewerbungs_assistent.services import eigener_standort as es
    _standort(db)
    ohne = _stelle(db, "p1", "Rosengarten", 17.0)
    mit = _stelle(db, "p2", "Rosengarten", 17.0, text="Standort 74538 Rosengarten. " + "Aufgaben. " * 30)
    gut = _stelle(db, "p3", "Frankfurt", 1.0)
    erg = es.entfernungen_nachziehen(db, alle=True, max_orte=None)
    assert erg["mehrdeutig"] == 1
    assert _zeile(db, ohne)["distance_km"] is None
    assert _zeile(db, mit)["distance_km"] == _km(HAMBURG, HALL)
    assert _zeile(db, gut)["distance_km"] == _km(HAMBURG, FFM)


def test_nachziehen_holt_die_entfernung_per_anzeige_nach(db, dienst):
    from bewerbungs_assistent.services import eigener_standort as es
    _standort(db)
    mit = _stelle(db, "q1", "Rosengarten", None, text="Einsatzort 74538 Rosengarten. " + "Aufgaben. " * 30)
    es.entfernungen_nachziehen(db, alle=False)
    assert _zeile(db, mit)["distance_km"] == _km(HAMBURG, HALL)


# ── die Aufrufer ────────────────────────────────────────────────────────────────────────────────────────────────────

def test_ort_aendern_mit_plz_rechnet_neu_ohne_plz_steht_auf_unbekannt(db, dienst):
    from bewerbungs_assistent.services import stelle_aendern
    _standort(db)
    voll = _stelle(db, "r1", "Hamburg", 1.0)
    erg = stelle_aendern.aendern(db, voll, {"location": "74538 Rosengarten"})
    assert erg["ok"] and erg["entfernung_neu_km"] == _km(HAMBURG, HALL) and erg["entfernung_neu_km"] > 450
    erg = stelle_aendern.aendern(db, voll, {"location": "Rosengarten"})
    assert erg["ok"] and erg["entfernung_neu_km"] is None
    assert "unbekannt" in erg["entfernung_text"]


def test_ort_aendern_nimmt_plz_aus_dem_anzeigentext(db, dienst):
    from bewerbungs_assistent.services import stelle_aendern
    _standort(db)
    voll = _stelle(db, "r2", "Hamburg", 1.0, text="Einsatzort 74538 Rosengarten. " + "Aufgaben. " * 30)
    erg = stelle_aendern.aendern(db, voll, {"location": "Rosengarten"})
    assert erg["entfernung_neu_km"] == _km(HAMBURG, HALL)


def test_manuell_angelegt_nimmt_plz_aus_dem_anzeigentext(db, dienst):
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all
    _standort(db)
    mcp = FastMCP("PBP Test")
    register_all(mcp, db, logging.getLogger("t"))

    async def _run():
        tool = await mcp.get_tool("stelle_manuell_anlegen")
        res = await tool.run({
            "titel": "Sachbearbeitung Einkauf", "firma": "Musterbetrieb GmbH", "ort": "Rosengarten",
            "url": "https://beispiel.example/rosengarten", "quelle": "xing",
            "beschreibung": "Einsatzort: 74538 Rosengarten. " + "Aufgaben im Einkauf. " * 30})
        return getattr(res, "structured_content", res)
    res = asyncio.run(_run())
    assert res["status"] == "angelegt", res
    z = _zeile(db, db.resolve_job_hash(res["hash"]))
    assert z["distance_km"] == _km(HAMBURG, HALL) and (z["lat"], z["lon"]) == HALL


def test_die_aufrufer_fragen_mit_der_anzeige_nach():
    """Suchlauf, Anlage von Hand, Heilung, Nachladen und Ort aendern benutzen alle den zweiten Versuch."""
    import ast
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"

    def ruft(datei, funktion, ziel):
        baum = ast.parse((src / datei).read_text(encoding="utf-8-sig"))
        for f in ast.walk(baum):
            if isinstance(f, (ast.FunctionDef, ast.AsyncFunctionDef)) and f.name == funktion:
                return any(isinstance(c, ast.Call) and getattr(c.func, "attr", getattr(c.func, "id", "")) == ziel
                           for c in ast.walk(f))
        return False

    assert ruft("job_scraper/__init__.py", "run_search", "entfernung_aus_anzeige")
    assert ruft("tools/jobs.py", "_stelle_uebernehmen", "entfernung_aus_anzeige")
    assert ruft("services/karten_heilung.py", "heilen", "entfernung_aus_anzeige")
    assert ruft("services/nachladen.py", "kopf_ergaenzen", "entfernung_aus_anzeige")
    assert ruft("services/stelle_aendern.py", "_neue_entfernung", "entfernung_aus_anzeige")
    assert ruft("services/eigener_standort.py", "_mehrdeutigen_ort_klaeren", "entfernung_aus_anzeige")
    assert ruft("services/eigener_standort.py", "nachholen", "entfernungen_mehrdeutige_pruefen")
