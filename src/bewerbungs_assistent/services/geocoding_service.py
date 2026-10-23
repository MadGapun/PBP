"""Geocoding-Service fuer Entfernungsberechnung (#167).

Nutzt Nominatim (OpenStreetMap) via geopy — kostenlos, kein API-Key.
Rate-Limit: max 1 Request/Sekunde (Nominatim Fair-Use-Policy).
"""

import json
import logging
import re
import time
import threading
from typing import Optional

logger = logging.getLogger("bewerbungs_assistent.geocoding")

# In-memory cache: city_name -> (lat, lon) to avoid redundant geocoding
_geo_cache: dict[str, Optional[tuple[float, float]]] = {}
# #1235: Orte, die der Dienst MEHRFACH kennt: Schluessel -> Kandidaten. Im `_geo_cache` steht dazu `None`
# (keine Koordinaten), hier steht, WARUM.
_mehrdeutig_orte: dict[str, list] = {}
_cache_lock = threading.Lock()
_last_request_time = 0.0
_rate_lock = threading.Lock()

# #1090 AK 6: dauerhafter Speicher (Tabelle geo_cache). Angebunden von
# Database.initialize; ohne ihn bleibt es beim Arbeitsspeicher.
_speicher = None

#: #1235: Ab diesem Abstand (km) sind zwei Treffer des Dienstes verschiedene Orte desselben Namens.
MEHRDEUTIG_AB_KM = 50.0

#: #1235: Wie weit das Gewicht (`importance` des Dienstes) des ersten Treffers ueber dem des naechsten WEIT
#: entfernten Ortes liegen muss, damit der erste als DER Ort gilt. Gemessen am 16.10.2026 an 15 Abfragen:
#: mehrdeutig waren Neuenkirchen (Abstand 0,000), Rosengarten (0,006), Lichtenau (0,009), Hohenfelde (0,020) und
#: Neustadt (0,061); eindeutig Offenbach (0,136), Frankfurt (0,140), Halle (0,164), Freiburg (0,251) und
#: "Rosengarten, Baden-Württemberg" (0,287). Dazwischen liegt eine Lücke von 0,075; die Grenze steht in der Mitte.
MEHRDEUTIG_GEWICHT = 0.10

#: #1235: So viele Treffer fragt PBP je Ort ab (eine Anfrage, nur mehr Antwort).
MAX_TREFFER = 8

#: #1235: Stand der Zeilen in `geo_cache`. Zeilen ohne Stand stammen aus der Zeit, als nur der erste Treffer
#: genommen wurde; sie kennen die Mehrdeutigkeit nicht und werden beim naechsten Bedarf neu gefragt.
SPEICHER_STAND = 2


def speicher_setzen(db) -> None:
    global _speicher
    _speicher = db


def _aus_speicher(loc_key: str):
    """(True, Wert) wenn der Ort dauerhaft bekannt ist, sonst (False, None).
    Wert ist (lat, lon) oder None fuer 'nicht gefunden'."""
    if _speicher is None:
        return False, None
    try:
        row = _speicher.connect().execute(
            "SELECT lat, lon, status, stand, kandidaten FROM geo_cache WHERE ort_key=?",
            (loc_key,)).fetchone()
    except Exception:
        return False, None
    if not row:
        return False, None
    if row[2] == "mehrdeutig":
        try:
            kandidaten = json.loads(row[4] or "[]")
        except ValueError:
            kandidaten = []
        if not kandidaten:
            return False, None          # ohne Kandidaten ist es kein Befund, den man erklaeren koennte
        with _cache_lock:
            _mehrdeutig_orte[loc_key] = kandidaten
        return True, None
    if row[2] == "gefunden" and row[0] is not None:
        if (row[3] or 0) < SPEICHER_STAND:
            # #1235: vor der Mehrdeutigkeits-Pruefung gemerkt - es war der erste Treffer, mehr nicht.
            return False, None
        return True, (float(row[0]), float(row[1]))
    return True, None


def _in_speicher(loc_key: str, coords, kandidaten=None) -> None:
    if _speicher is None:
        return
    try:
        from datetime import datetime, timezone
        con = _speicher.connect()
        con.execute(
            "INSERT OR REPLACE INTO geo_cache (ort_key, lat, lon, status, abgerufen_am, stand, kandidaten) "
            "VALUES (?,?,?,?,?,?,?)",
            (loc_key, coords[0] if coords else None, coords[1] if coords else None,
             "gefunden" if coords else ("mehrdeutig" if kandidaten else "nicht_gefunden"),
             datetime.now(timezone.utc).isoformat(timespec="seconds"), SPEICHER_STAND,
             json.dumps(kandidaten, ensure_ascii=False) if kandidaten else None))
        con.commit()
    except Exception as exc:
        logger.debug("Geo-Speicher nicht beschreibbar: %s", exc)


# User-Agent for Nominatim (required)
_USER_AGENT = "PBP/0.32 bewerbungs-assistent (https://github.com/MadGapun/PBP)"


def _rate_limit():
    """Ensure at least 1 second between Nominatim requests."""
    global _last_request_time
    with _rate_lock:
        now = time.monotonic()
        elapsed = now - _last_request_time
        if elapsed < 1.0:
            time.sleep(1.0 - elapsed)
        _last_request_time = time.monotonic()


# Zusaetze, die Quellen an den Ortsstring haengen und die Nominatim
# nicht aufloesen kann. Sie stehen fast immer in Klammern oder hinter
# einem Trenner am Ende: "Aerzen, Niedersachsen (Hybrid)".
_ORT_ZUSATZ = {
    "hybrid", "remote", "vor ort", "homeoffice", "home office",
    "teilremote", "teilweise remote", "mobiles arbeiten", "vollzeit",
    "teilzeit", "befristet", "unbefristet", "festanstellung",
    "m/w/d", "m/w/x", "w/m/d", "und umgebung", "umgebung", "raum",
    "deutschland", "germany",
}


#: Einzelne Wörter, die nie einen Ort bezeichnen (#1158 Punkt 8). Ein Teil des Ortsstrings, der NUR aus solchen
#: Wörtern besteht, fällt weg: "remote möglich", "Homeoffice möglich", "teilweise hybrid". Vorher blieb "remote
#: möglich" stehen (nur "remote" allein stand in der Liste), Nominatim las "Hamburg, remote möglich" als einen
#: Ort bei Mainz - 410 km statt 20 -, und die beste Stelle des Tages rutschte durch den Entfernungsabzug auf
#: einen negativen Stand.
_ORT_ZUSATZ_WOERTER = {
    "hybrid", "remote", "homeoffice", "home", "office", "teilremote", "mobil", "mobiles", "arbeiten", "arbeit",
    "möglich", "moeglich", "optional", "wahlweise", "flexibel", "teilweise", "teils", "zeitweise", "oder", "und",
    "vor", "ort", "vollzeit", "teilzeit", "befristet", "unbefristet", "festanstellung", "umgebung", "raum",
    "ortsunabhängig", "ortsunabhaengig", "bundesweit", "deutschlandweit", "deutschland", "germany",
}


def _ist_nur_zusatz(text: str) -> bool:
    """Besteht der Text nur aus Zusätzen wie "remote möglich" - also aus gar keinem Ort?"""
    woerter = [w for w in re.split(r"[\s,/\-]+", str(text or "").lower()) if w]
    return bool(woerter) and all(w in _ORT_ZUSATZ_WOERTER for w in woerter)


def geocoding_aktiv() -> bool:
    """False, wenn kein Weg ins Netz gehen darf (Test-Suite, #1090)."""
    import os as _os
    return _os.environ.get("PBP_GEOCODING") != "0"


def normalisiere_ort(ort: str) -> str:
    """Ortsstring von Quellen-Zusaetzen befreien (#965).

    Belegter Fall: "Aerzen, Niedersachsen (Hybrid)" scheiterte am
    Geocoding, waehrend die drei uebrigen aktiven Stellen mit sauberem
    Ort funktionierten. Der Fehlschlag blieb stumm — und weil eine
    unbekannte Entfernung im Scoring gar nicht gerechnet wird, stand
    ausgerechnet die WEITESTE Stelle mit dem hoechsten Score oben.

    Der Ortsstring ist damit ein Datenqualitaets-Nadeloehr: was hier
    durchfaellt, wird nicht als Fehler sichtbar, sondern als Vorteil.
    """
    if not ort:
        return ""
    text = str(ort)
    # Klammerzusaetze entfernen — sie tragen nie die Ortsangabe.
    text = re.sub(r"[(\[][^)\]]*[)\]]", " ", text)
    # Trenner, hinter denen Quellen das Arbeitsmodell anhaengen.
    text = re.split(r"\s+[|/·•]\s+|\s+-\s+", text)[0]
    teile = [t.strip(" ,;-") for t in text.split(",")]
    behalten = [t for t in teile
                if t and t.lower() not in _ORT_ZUSATZ
                and not all(w in _ORT_ZUSATZ_WOERTER for w in re.split(r"[\s/\-]+", t.lower()) if w)]
    return ", ".join(behalten).strip(" ,;-") or text.strip(" ,;-")


#: Ein Land am Ende des Ortstextes ("Hamburg, Germany").
_LAND_ENDE = re.compile(r"[\s,;-]*\b(?:deutschland|germany)\b\s*$", re.IGNORECASE)


def nur_land_entfernt(roh: str, ziel: str) -> bool:
    """Unterscheiden sich Rohtext und bereinigter Ort NUR um ein angehaengtes Land?

    Dann ist die Abfrage dieselbe wie vor #1158 (das Land haengt `geocode_location` ohnehin selbst an), und
    eine frueher unter dem Rohtext gemerkte Antwort gilt weiter."""
    ohne_land = _LAND_ENDE.sub("", str(roh or "").strip()).strip(" ,;-").lower()
    return bool(ohne_land) and ohne_land == str(ziel or "").strip().lower()


#: Angaben, die keinen Ort nennen, sondern das Arbeitsmodell oder den Raum.
_KEIN_ORT = {"remote", "home office", "homeoffice", "deutschlandweit",
             "bundesweit", "weltweit", "europa", "global"}


def ort_fuer_abfrage(location: str) -> str:
    """Der Ort, der an den Dienst geht - leer, wenn der Text keinen Ort nennt (#1158 Punkt 8).

    Bis v1.7.149 ging der Rohstring zuerst an Nominatim; die Bereinigung lief nur als letzter Versuch, wenn
    nichts zurueckkam. "Hamburg (hybrid), remote moeglich, Deutschland" kam aber nicht leer zurueck, sondern
    mit einem Treffer bei Mainz (410 km statt 20) - und der wurde unter dem Rohschluessel dauerhaft gemerkt.
    Ein Text, der nur aus Zusaetzen besteht ("Remote moeglich"), ist kein Ort: keine Anfrage, keine Entfernung.
    """
    if not location:
        return ""
    roh = location.strip().lower()
    if roh in _KEIN_ORT or roh.startswith("remote") or _ist_nur_zusatz(location):
        return ""
    ziel = normalisiere_ort(location) or location.strip()
    return "" if ziel.lower() in _KEIN_ORT else ziel


def ort_schluessel(location: str) -> str:
    """Unter diesem Schluessel wird ein Ort gefragt und gemerkt; leer = es wird nichts gefragt.

    Die Laufkarte der Suche zaehlt ihre "verschiedenen Orte" mit genau diesem Schluessel - eine eigene
    Rechnung waere eine Zahl, die nicht zu den Abfragen passt.
    """
    return ort_fuer_abfrage(location).lower()


def _ist_ortstreffer(treffer) -> bool:
    """Ist das ein Ort (Gemeinde, Stadt, Ortsteil) - kein Park, keine Strasse, keine Postleitzahl? (#1235)"""
    raw = getattr(treffer, "raw", None) or {}
    return raw.get("class") in ("boundary", "place") and raw.get("type") != "postal_code"


def _gewicht(treffer) -> float:
    try:
        return float((getattr(treffer, "raw", None) or {}).get("importance") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _kurzname(treffer) -> str:
    """"Rosengarten, Landkreis Harburg, Niedersachsen" aus dem langen Namen des Dienstes - ohne PLZ und Land."""
    raw = getattr(treffer, "raw", None) or {}
    teile = [t.strip() for t in str(raw.get("display_name") or "").split(",") if t.strip()]
    teile = [t for t in teile if not re.fullmatch(r"\d{5}", t) and t.lower() not in ("deutschland", "germany")]
    return ", ".join(teile[:4])


def _ortsfund(treffer) -> dict:
    """Wertet die Treffer EINER Abfrage aus: eindeutig, mehrdeutig oder nichts (#1235).

    Bis v1.8.0 hiess die Abfrage `exactly_one=True`: bei einem Namen, den es in Deutschland mehrfach gibt
    (Rosengarten, Neustadt, Neuenkirchen, Lichtenau, Hohenfelde), lieferte der Dienst den Treffer mit dem hoechsten
    Gewicht, und PBP nahm ihn ohne Hinweis - eine Stelle in Baden-Württemberg stand mit 24 statt 500 km als nahe
    in der Liste. Jetzt gilt der erste Treffer nur dann als DER Ort, wenn kein anderer Ort desselben Namens,
    mehr als `MEHRDEUTIG_AB_KM` entfernt, ein aehnliches Gewicht hat (`MEHRDEUTIG_GEWICHT`). Frankfurt und Halle
    haben einen klaren Spitzenreiter; Rosengarten nicht.

    Rueckgabe: {"status": "nicht_gefunden"}, {"status": "gefunden", "koordinaten": (lat, lon)} oder
    {"status": "mehrdeutig", "kandidaten": [{"name", "lat", "lon"}, ...]}.
    """
    treffer = list(treffer or [])
    if not treffer:
        return {"status": "nicht_gefunden"}
    erster = treffer[0]
    koordinaten = (erster.latitude, erster.longitude)
    orte = [t for t in treffer if _ist_ortstreffer(t)]
    if len(treffer) == 1 or len(orte) < 2:
        return {"status": "gefunden", "koordinaten": koordinaten}
    spitze = orte[0]
    ref = (spitze.latitude, spitze.longitude)
    gegner = [t for t in orte[1:]
              if calculate_distance_km(ref, (t.latitude, t.longitude)) > MEHRDEUTIG_AB_KM
              and _gewicht(spitze) - _gewicht(t) < MEHRDEUTIG_GEWICHT]
    if not gegner:
        return {"status": "gefunden", "koordinaten": koordinaten}
    kandidaten: list = []
    for t in [spitze] + gegner:
        punkt = (t.latitude, t.longitude)
        # Dieselbe Gemeinde taucht oft als Gemeinde UND als Ortsteil auf - nur einmal nennen.
        if any(calculate_distance_km(punkt, (k["lat"], k["lon"])) < 10.0 for k in kandidaten):
            continue
        kandidaten.append({"name": _kurzname(t), "lat": punkt[0], "lon": punkt[1]})
    if len(kandidaten) < 2:
        return {"status": "gefunden", "koordinaten": koordinaten}
    return {"status": "mehrdeutig", "kandidaten": kandidaten[:5]}


def _abfragen(geolocator, anfrage: str) -> list:
    """Die Treffer des Dienstes als Liste - auch wenn ein Testdouble nur den alten Einzeltreffer kennt."""
    try:
        antwort = geolocator.geocode(anfrage, exactly_one=False, limit=MAX_TREFFER)
    except TypeError:                      # ein Dienst ohne `limit`
        antwort = geolocator.geocode(anfrage, exactly_one=False)
    if antwort is None:
        return []
    return list(antwort) if isinstance(antwort, (list, tuple)) else [antwort]


def _gedaechtnis(loc_key: str) -> Optional[dict]:
    """Was PBP zu diesem Ort schon weiss (Arbeitsspeicher), sonst None."""
    with _cache_lock:
        if loc_key not in _geo_cache:
            return None
        wert = _geo_cache[loc_key]
        if wert is not None:
            return {"status": "gefunden", "koordinaten": wert}
        kandidaten = _mehrdeutig_orte.get(loc_key)
        if kandidaten:
            return {"status": "mehrdeutig", "koordinaten": None, "kandidaten": list(kandidaten)}
        return {"status": "nicht_gefunden", "koordinaten": None}


def _ort_aufloesen(location: str) -> dict:
    """Loest einen Ort auf und sagt, WIE sicher das ist (#1235).

    Rueckgabe: {"status", "koordinaten", "kandidaten"?}; status ist `kein_ort` (der Text nennt keinen Ort),
    `gefunden`, `mehrdeutig` (mehrere Orte dieses Namens: keine Koordinaten), `nicht_gefunden` oder
    `nicht_erreichbar` (Dienst ausgefallen oder im Test gesperrt - nichts gemerkt).
    """
    # #1158 Punkt 8: gefragt wird der BEREINIGTE Ort, und er ist auch der Schluessel des Speichers.
    ziel = ort_fuer_abfrage(location)
    if not ziel:
        return {"status": "kein_ort", "koordinaten": None}
    loc_key = ziel.lower()

    # Check cache
    bekannt = _gedaechtnis(loc_key)
    if bekannt:
        return bekannt
    gespeichert, wert = _aus_speicher(loc_key)
    if gespeichert:
        with _cache_lock:
            _geo_cache[loc_key] = wert
        return _gedaechtnis(loc_key)

    # Der Rohtext trug nur ein angehaengtes Land ("Hamburg, Germany"): die Abfrage ist dieselbe wie vor #1158,
    # eine Antwort unter dem alten Schluessel gilt weiter - ohne sie muesste jeder bekannte Ort einmal neu
    # beim Dienst angefragt werden.
    alt_key = location.strip().lower()
    if alt_key != loc_key and nur_land_entfernt(location, ziel):
        with _cache_lock:
            if alt_key in _geo_cache:
                _geo_cache[loc_key] = _geo_cache[alt_key]
                if alt_key in _mehrdeutig_orte:
                    _mehrdeutig_orte[loc_key] = _mehrdeutig_orte[alt_key]
        bekannt = _gedaechtnis(loc_key)
        if bekannt:
            return bekannt
        gespeichert, wert = _aus_speicher(alt_key)
        if gespeichert:
            with _cache_lock:
                _geo_cache[loc_key] = wert
                if alt_key in _mehrdeutig_orte:
                    _mehrdeutig_orte[loc_key] = _mehrdeutig_orte[alt_key]
            return _gedaechtnis(loc_key)

    # #1090: in der Test-Suite geht kein Weg ins Netz (wie
    # PBP_BERUFE_LOOKUP, #969). Behandelt wie ein Ausfall: nichts gemerkt.
    import os as _os
    if _os.environ.get("PBP_GEOCODING") == "0":
        return {"status": "nicht_erreichbar", "koordinaten": None}

    # Geocode via Nominatim
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderServiceError
    except ImportError:
        logger.warning("geopy not installed — geocoding disabled")
        return {"status": "nicht_erreichbar", "koordinaten": None}

    try:
        geolocator = Nominatim(user_agent=_USER_AGENT, timeout=5)
        _rate_limit()

        # Try with country bias for better results
        search = f"{ziel}, Deutschland"
        treffer = _abfragen(geolocator, search)

        if not treffer:
            # Retry without country
            _rate_limit()
            treffer = _abfragen(geolocator, ziel)

        # Kein Rueckgriff auf den Rohstring mehr (#1158): was der bereinigte Ort nicht findet, findet der
        # Rohstring nur falsch. Eine unbekannte Entfernung ist besser als eine erfundene.

        fund = _ortsfund(treffer)
        if fund["status"] == "gefunden":
            coords = fund["koordinaten"]
            with _cache_lock:
                _geo_cache[loc_key] = coords
                _mehrdeutig_orte.pop(loc_key, None)
            _in_speicher(loc_key, coords)
            logger.debug("Geocoded '%s' -> %s", location, coords)
            return {"status": "gefunden", "koordinaten": coords}
        if fund["status"] == "mehrdeutig":
            # #1235: ein Befund ueber den Ort - der Dienst kennt mehrere. Gemerkt wird er samt Kandidaten, damit
            # die Oberflaeche sagen kann, WARUM keine Entfernung dasteht.
            with _cache_lock:
                _geo_cache[loc_key] = None
                _mehrdeutig_orte[loc_key] = fund["kandidaten"]
            _in_speicher(loc_key, None, fund["kandidaten"])
            logger.debug("Ort '%s' ist mehrdeutig: %s", location, [k["name"] for k in fund["kandidaten"]])
            return {"status": "mehrdeutig", "koordinaten": None, "kandidaten": list(fund["kandidaten"])}
        with _cache_lock:
            _geo_cache[loc_key] = None
            _mehrdeutig_orte.pop(loc_key, None)
        # Der Dienst hat geantwortet und nichts gefunden — das ist ein
        # Befund ueber den Ort. Ein Timeout oder Dienstfehler landet
        # im except-Zweig unten und wird NICHT gemerkt.
        _in_speicher(loc_key, None)
        logger.debug("Geocoding failed for '%s'", location)
        return {"status": "nicht_gefunden", "koordinaten": None}

    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning("Geocoding error for '%s': %s", location, e)
        return {"status": "nicht_erreichbar", "koordinaten": None}
    except Exception as e:
        logger.warning("Unexpected geocoding error for '%s': %s", location, e)
        return {"status": "nicht_erreichbar", "koordinaten": None}


def geocode_location(location: str) -> Optional[tuple[float, float]]:
    """Geocode a location string to (lat, lon) coordinates.

    Returns None if geocoding fails or location is empty/remote - und seit #1235 auch, wenn der Name mehrere
    Orte meint (Rosengarten): dann gibt es keine Koordinaten, nur die Kandidaten (`geocode_ort`).
    Results are cached in memory.
    """
    return _ort_aufloesen(location)["koordinaten"]


_BUNDESLAENDER = (
    "Baden-Württemberg", "Bayern", "Berlin", "Brandenburg", "Bremen", "Hamburg", "Hessen",
    "Mecklenburg-Vorpommern", "Niedersachsen", "Nordrhein-Westfalen", "Rheinland-Pfalz", "Saarland",
    "Sachsen-Anhalt", "Sachsen", "Schleswig-Holstein", "Thüringen",
)


def _umschreiben(text: str) -> str:
    return str(text or "").lower().translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))


def ort_aus_anzeige(ort: str, anzeige: str) -> str:
    """Die Postleitzahl oder das Bundesland, das die Anzeige direkt hinter dem Ortsnamen nennt (#1235).

    "Rosengarten" + "... Standort: 74538 Rosengarten ..." -> "74538 Rosengarten";
    "Rosengarten" + "... in Rosengarten (Baden-Württemberg) ..." -> "Rosengarten, Baden-Württemberg".
    Leer, wenn die Anzeige nichts davon nennt oder verschiedene Angaben macht: eine PLZ, die nicht direkt vor
    dem Namen steht, gehoert vielleicht zum Firmensitz. Erst die Postleitzahl, dann das Bundesland.
    """
    name = str(ort or "").split(",")[0].strip()
    text = str(anzeige or "")
    if len(name) < 3 or not text:
        return ""
    plz = {m.group(1) for m in re.finditer(r"(?<!\d)(\d{5})\s+" + re.escape(name) + r"(?![\w-])", text, re.IGNORECASE)}
    if len(plz) == 1:
        return f"{next(iter(plz))} {name}"
    if plz:
        return ""
    umgeschrieben = _umschreiben(text)
    name_u = _umschreiben(name)
    gefunden = set()
    for land in _BUNDESLAENDER:
        muster = (r"(?<![\w-])" + re.escape(name_u) + r"\s*(?:,|\(|/|-|–|in|im)?\s*\(?\s*" + re.escape(_umschreiben(land)) + r"(?![\w-])")
        if re.search(muster, umgeschrieben):
            gefunden.add(land)
    # "Sachsen" steckt in "Sachsen-Anhalt": das laengere Land gewinnt.
    gefunden = {l for l in gefunden if not any(l != g and g.startswith(l + "-") for g in gefunden)}
    if len(gefunden) == 1:
        return f"{name}, {next(iter(gefunden))}"
    return ""


def geocode_ort(location: str, anzeige: str = "") -> dict:
    """Wie `geocode_location`, aber mit Befund: {"status", "koordinaten", "kandidaten"?, "aufgeloest_durch"?} (#1235).

    Meint der Name mehrere Orte und nennt die Anzeige Postleitzahl oder Bundesland direkt dahinter, wird damit
    ein zweites Mal gefragt ("74538 Rosengarten"); `aufgeloest_durch` nennt dann die Angabe.
    """
    fund = _ort_aufloesen(location)
    if fund["status"] != "mehrdeutig" or not anzeige:
        return fund
    genauer = ort_aus_anzeige(ort_fuer_abfrage(location), anzeige)
    if not genauer:
        return fund
    zweit = _ort_aufloesen(genauer)
    if zweit["status"] == "gefunden":
        return {**zweit, "aufgeloest_durch": genauer}
    return fund


def mehrdeutigkeit_offen(location: str) -> bool:
    """Wurde dieser Ort noch nie auf Mehrdeutigkeit geprueft - und lohnt es sich? (#1235)

    Nein bei einem Text ohne Ort, mit Postleitzahl, bei einer grossen Stadt oder einem Land (`ist_ortsname`)
    und bei jedem Ort, den PBP in dieser Fassung schon gefragt hat (Arbeitsspeicher oder Speicherzeile mit Stand).
    Nur Gedaechtnis, kein Netz.
    """
    ziel = ort_fuer_abfrage(location)
    if not ziel or re.search(r"(?<!\d)\d{5}(?!\d)", ziel) or ist_ortsname(ziel):
        return False
    loc_key = ziel.lower()
    with _cache_lock:
        if loc_key in _geo_cache:
            return False
    bekannt, _wert = _aus_speicher(loc_key)
    return not bekannt


def mehrdeutigkeit(location: str) -> Optional[list]:
    """Die Kandidaten, wenn PBP diesen Ort als mehrdeutig kennt - OHNE Netz (#1235). Sonst None.

    Zum Erklaeren, warum eine Stelle keine Entfernung hat; fragt nie den Dienst.
    """
    ziel = ort_fuer_abfrage(location)
    if not ziel:
        return None
    loc_key = ziel.lower()
    with _cache_lock:
        kandidaten = _mehrdeutig_orte.get(loc_key)
    if not kandidaten:
        _aus_speicher(loc_key)
        with _cache_lock:
            kandidaten = _mehrdeutig_orte.get(loc_key)
    return list(kandidaten) if kandidaten else None


def calculate_distance_km(coord1: tuple[float, float],
                          coord2: tuple[float, float]) -> float:
    """Calculate geodesic distance between two (lat, lon) points in km."""
    try:
        from geopy.distance import geodesic
        return round(geodesic(coord1, coord2).km, 1)
    except ImportError:
        logger.warning("geopy not installed — distance calculation disabled")
        return 0.0
    except Exception as e:
        logger.warning("Distance calculation error: %s", e)
        return 0.0


def geocode_and_calculate_distance(job_location: str,
                                   user_lat: float, user_lon: float) -> Optional[float]:
    """Geocode a job location and calculate distance to user coordinates.

    Returns distance in km, or None if geocoding fails.
    """
    if not job_location or not user_lat or not user_lon:
        return None

    job_coords = geocode_location(job_location)
    if job_coords is None:
        return None

    return calculate_distance_km((user_lat, user_lon), job_coords)


def entfernung_aus_anzeige(job_location: str, user_lat: float, user_lon: float, anzeige: str) -> Optional[dict]:
    """Zweiter Versuch fuer einen MEHRDEUTIGEN Ort: die Anzeige nennt Postleitzahl oder Bundesland (#1235).

    Der erste Versuch (`geocode_and_calculate_distance`) liefert bei einem Namen, den es mehrfach gibt, keine
    Entfernung. Nennt die Anzeige direkt hinter dem Namen eine PLZ ("74538 Rosengarten") oder ein Bundesland,
    wird damit noch einmal gefragt. Rueckgabe: {"km", "koordinaten", "aufgeloest_durch"} oder None - auch wenn
    der Ort gar nicht mehrdeutig ist; der Aufrufer fragt zuerst auf dem gewohnten Weg.
    """
    if not job_location or not anzeige or not user_lat or not user_lon:
        return None
    if not mehrdeutigkeit(job_location):
        return None
    fund = geocode_ort(job_location, anzeige)
    if fund.get("status") != "gefunden" or not fund.get("aufgeloest_durch"):
        return None
    koord = fund["koordinaten"]
    return {"km": calculate_distance_km((user_lat, user_lon), koord), "koordinaten": koord,
            "aufgeloest_durch": fund["aufgeloest_durch"]}


def get_user_coordinates(db) -> Optional[tuple[float, float]]:
    """Get cached user coordinates from search criteria.

    Returns (lat, lon) tuple or None.
    """
    criteria = db.get_search_criteria()
    lat = criteria.get("standort_lat")
    lon = criteria.get("standort_lon")
    if lat and lon:
        return (float(lat), float(lon))
    return None


def cache_user_coordinates(db, address: str) -> Optional[tuple[float, float]]:
    """Geocode user address and cache in search criteria.

    Returns (lat, lon) tuple or None.
    """
    coords = geocode_location(address)
    if coords:
        db.set_search_criteria("standort_lat", coords[0])
        db.set_search_criteria("standort_lon", coords[1])
        logger.info("User coordinates cached: %s -> %s", address, coords)
    return coords


# === #732: Nicht-DACH-Erkennung fuer den Geo-Filter ===
#
# Hintergrund: Globale Remote-Aggregatoren (remotive, remoteok) liefern
# Stellen mit Orten wie "Brazil" oder "Remote (Florianópolis)". Das
# Geocoding haengt ", Deutschland" an die Anfrage (s.o. Zeile 71) und
# bekommt dann irgendeinen DE-Treffer mit falscher Naehe (z.B. 533 km
# statt ~10.000 km). Der Entfernungs-Malus ist zudem gedeckelt und reicht
# nicht, eine solche Stelle aus dem aktiven Pool zu draengen. Darum eine
# String-Heuristik VOR dem Geocoding.
#
# Konservativ by design: Ein DACH-Marker gewinnt IMMER (-> False). Nur ein
# klarer Auslands-Marker OHNE DACH-Marker liefert True. Unbekannte oder
# leere Orte bleiben False (kein Auto-Aussortieren bei Unsicherheit).

# Reine Remote-/Weitraum-Angaben ohne Ortsbezug — koennen DACH sein,
# darum NICHT filtern.
_GEO_PURE_REMOTE = {
    "remote", "home office", "homeoffice", "deutschlandweit", "bundesweit",
    "weltweit", "worldwide", "europa", "europe", "eu", "global", "anywhere",
    "remote (eu)", "eu remote", "europe remote", "remote europe",
}

# DACH-Marker: Laendernamen/Codes + grosse Staedte als Positivliste.
_GEO_DACH_MARKERS = {
    "deutschland", "germany", "allemagne", "de", "ger", "deu", "brd",
    "oesterreich", "österreich", "austria", "at", "aut",
    "schweiz", "switzerland", "suisse", "svizzera", "ch", "che", "dach",
    "berlin", "hamburg", "muenchen", "münchen", "munich", "koeln", "köln",
    "cologne", "frankfurt", "stuttgart", "duesseldorf", "düsseldorf",
    "dortmund", "essen", "leipzig", "dresden", "hannover", "nuernberg",
    "nürnberg", "nuremberg", "bremen", "bonn", "mannheim", "karlsruhe",
    "wiesbaden", "muenster", "münster", "kiel", "wedel", "pinneberg",
    "wien", "vienna", "graz", "linz", "salzburg", "innsbruck", "klagenfurt",
    "zuerich", "zürich", "zurich", "bern", "basel", "genf", "geneva",
    "geneve", "lausanne", "luzern", "lucerne", "winterthur",
}

def ist_ortsname(name) -> bool:
    """Ist das der Name einer grossen DACH-Stadt oder eines DACH-Landes?

    Aus derselben Liste wie die Standort-Erkennung (#1124): eine zweite
    Ortsliste im PII-Pruefer waere die Bauform aus #963. Verglichen wird
    der GANZE Name - "Hamburg" ja, "Hamburg Wasser" nein.
    """
    return " ".join(str(name or "").lower().split()) in _GEO_DACH_MARKERS


# Klare Auslands-Marker (Laender).
_GEO_NON_DACH_COUNTRIES = {
    "usa", "u.s.a", "us", "united states", "america", "uk", "u.k",
    "united kingdom", "england", "scotland", "wales", "ireland", "irland",
    "brazil", "brasil", "brasilien", "india", "indien", "china", "japan",
    "poland", "polen", "polska", "france", "frankreich", "spain", "spanien",
    "espana", "españa", "italy", "italien", "italia", "portugal",
    "netherlands", "niederlande", "nederland", "holland", "belgium",
    "belgien", "belgique", "sweden", "schweden", "norway", "norwegen",
    "denmark", "daenemark", "dänemark", "finland", "finnland", "czech",
    "czechia", "tschechien", "slovakia", "slowakei", "hungary", "ungarn",
    "romania", "rumaenien", "rumänien", "bulgaria", "bulgarien", "greece",
    "griechenland", "ukraine", "russia", "russland", "turkey", "tuerkei",
    "türkei", "canada", "kanada", "mexico", "mexiko", "argentina",
    "argentinien", "chile", "colombia", "kolumbien", "peru", "uruguay",
    "venezuela", "singapore", "singapur", "australia", "australien",
    "new zealand", "neuseeland", "philippines", "philippinen", "indonesia",
    "indonesien", "malaysia", "vietnam", "thailand", "egypt", "aegypten",
    "ägypten", "morocco", "marokko", "south africa", "suedafrika",
    "südafrika", "nigeria", "kenya", "kenia", "israel", "uae", "emirates",
    "dubai", "abu dhabi", "qatar", "katar", "saudi", "pakistan", "bangladesh",
}

# Notorische Auslands-Staedte aus globalen Remote-Aggregatoren.
_GEO_NON_DACH_CITIES = {
    "florianopolis", "florianópolis", "sao paulo", "são paulo",
    "rio de janeiro", "new york", "san francisco", "los angeles", "chicago",
    "boston", "austin", "seattle", "denver", "miami", "atlanta", "toronto",
    "vancouver", "montreal", "london", "manchester", "dublin", "paris",
    "lyon", "madrid", "barcelona", "lisbon", "lissabon", "lisboa", "porto",
    "amsterdam", "rotterdam", "brussels", "bruessel", "warsaw", "warschau",
    "krakow", "krakau", "wroclaw", "prague", "prag", "bangalore",
    "bengaluru", "mumbai", "delhi", "hyderabad", "pune", "chennai", "manila",
    "jakarta", "singapore city", "tel aviv", "sydney", "melbourne",
}


def is_non_dach_location(location: str) -> bool:
    """True, wenn der Ort erkennbar ausserhalb DACH liegt (#732).

    Konservativ: ein DACH-Marker gewinnt immer; nur ein klarer
    Auslands-Marker ohne DACH-Marker liefert True. Leere, reine Remote-
    oder unbekannte Orte liefern False (kein Auto-Aussortieren bei
    Unsicherheit).
    """
    if not location:
        return False
    loc = location.strip().lower()
    if not loc or loc in _GEO_PURE_REMOTE:
        return False

    # Einwort-Marker per Token, Mehrwort-/gepunktete Marker per Substring.
    # \w ist in Python-3-str-Regex Unicode-aware und erfasst akzentuierte
    # Buchstaben (z.B. "florianópolis", "münchen") als ganzes Token.
    tokens = set(re.findall(r"\w+", loc))

    def _has(markers: set) -> bool:
        for m in markers:
            if " " in m or "." in m:
                if m in loc:
                    return True
            elif m in tokens:
                return True
        return False

    # DACH gewinnt immer.
    if _has(_GEO_DACH_MARKERS):
        return False
    if _has(_GEO_NON_DACH_COUNTRIES) or _has(_GEO_NON_DACH_CITIES):
        return True
    return False
