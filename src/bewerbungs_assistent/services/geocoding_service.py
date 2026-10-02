"""Geocoding-Service fuer Entfernungsberechnung (#167).

Nutzt Nominatim (OpenStreetMap) via geopy — kostenlos, kein API-Key.
Rate-Limit: max 1 Request/Sekunde (Nominatim Fair-Use-Policy).
"""

import logging
import re
import time
import threading
from typing import Optional

logger = logging.getLogger("bewerbungs_assistent.geocoding")

# In-memory cache: city_name -> (lat, lon) to avoid redundant geocoding
_geo_cache: dict[str, Optional[tuple[float, float]]] = {}
_cache_lock = threading.Lock()
_last_request_time = 0.0
_rate_lock = threading.Lock()

# #1090 AK 6: dauerhafter Speicher (Tabelle geo_cache). Angebunden von
# Database.initialize; ohne ihn bleibt es beim Arbeitsspeicher.
_speicher = None


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
            "SELECT lat, lon, status FROM geo_cache WHERE ort_key=?",
            (loc_key,)).fetchone()
    except Exception:
        return False, None
    if not row:
        return False, None
    if row[2] == "gefunden" and row[0] is not None:
        return True, (float(row[0]), float(row[1]))
    return True, None


def _in_speicher(loc_key: str, coords) -> None:
    if _speicher is None:
        return
    try:
        from datetime import datetime, timezone
        con = _speicher.connect()
        con.execute(
            "INSERT OR REPLACE INTO geo_cache (ort_key, lat, lon, status, abgerufen_am) "
            "VALUES (?,?,?,?,?)",
            (loc_key, coords[0] if coords else None, coords[1] if coords else None,
             "gefunden" if coords else "nicht_gefunden",
             datetime.now(timezone.utc).isoformat(timespec="seconds")))
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


def geocode_location(location: str) -> Optional[tuple[float, float]]:
    """Geocode a location string to (lat, lon) coordinates.

    Returns None if geocoding fails or location is empty/remote.
    Results are cached in memory.
    """
    # #1158 Punkt 8: gefragt wird der BEREINIGTE Ort, und er ist auch der Schluessel des Speichers.
    ziel = ort_fuer_abfrage(location)
    if not ziel:
        return None
    loc_key = ziel.lower()

    # Check cache
    with _cache_lock:
        if loc_key in _geo_cache:
            return _geo_cache[loc_key]
    bekannt, wert = _aus_speicher(loc_key)
    if bekannt:
        with _cache_lock:
            _geo_cache[loc_key] = wert
        return wert

    # #1090: in der Test-Suite geht kein Weg ins Netz (wie
    # PBP_BERUFE_LOOKUP, #969). Behandelt wie ein Ausfall: nichts gemerkt.
    import os as _os
    if _os.environ.get("PBP_GEOCODING") == "0":
        return None

    # Geocode via Nominatim
    try:
        from geopy.geocoders import Nominatim
        from geopy.exc import GeocoderTimedOut, GeocoderServiceError
    except ImportError:
        logger.warning("geopy not installed — geocoding disabled")
        return None

    try:
        geolocator = Nominatim(user_agent=_USER_AGENT, timeout=5)
        _rate_limit()

        # Try with country bias for better results
        search = f"{ziel}, Deutschland"
        result = geolocator.geocode(search, exactly_one=True)

        if result is None:
            # Retry without country
            _rate_limit()
            result = geolocator.geocode(ziel, exactly_one=True)

        # Kein Rueckgriff auf den Rohstring mehr (#1158): was der bereinigte Ort nicht findet, findet der
        # Rohstring nur falsch. Eine unbekannte Entfernung ist besser als eine erfundene.

        if result:
            coords = (result.latitude, result.longitude)
            with _cache_lock:
                _geo_cache[loc_key] = coords
            _in_speicher(loc_key, coords)
            logger.debug("Geocoded '%s' -> %s", location, coords)
            return coords
        else:
            with _cache_lock:
                _geo_cache[loc_key] = None
            # Der Dienst hat geantwortet und nichts gefunden — das ist ein
            # Befund ueber den Ort. Ein Timeout oder Dienstfehler landet
            # im except-Zweig unten und wird NICHT gemerkt.
            _in_speicher(loc_key, None)
            logger.debug("Geocoding failed for '%s'", location)
            return None

    except (GeocoderTimedOut, GeocoderServiceError) as e:
        logger.warning("Geocoding error for '%s': %s", location, e)
        return None
    except Exception as e:
        logger.warning("Unexpected geocoding error for '%s': %s", location, e)
        return None


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
