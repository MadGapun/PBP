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
                if t and t.lower() not in _ORT_ZUSATZ]
    return ", ".join(behalten).strip(" ,;-") or text.strip(" ,;-")


def geocode_location(location: str) -> Optional[tuple[float, float]]:
    """Geocode a location string to (lat, lon) coordinates.

    Returns None if geocoding fails or location is empty/remote.
    Results are cached in memory.
    """
    if not location:
        return None

    # Normalize
    loc_key = location.strip().lower()

    # Skip remote/home-office locations
    remote_keywords = {"remote", "home office", "homeoffice", "deutschlandweit",
                       "bundesweit", "weltweit", "europa", "global"}
    if loc_key in remote_keywords or loc_key.startswith("remote"):
        return None

    # Check cache
    with _cache_lock:
        if loc_key in _geo_cache:
            return _geo_cache[loc_key]

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
        search = f"{location}, Deutschland"
        result = geolocator.geocode(search, exactly_one=True)

        if result is None:
            # Retry without country
            _rate_limit()
            result = geolocator.geocode(location, exactly_one=True)

        if result is None:
            # #965: letzter Versuch mit bereinigtem Ort. Quellen haengen
            # Arbeitsmodell und Zusaetze an den Ortsstring; genau daran
            # scheiterte die Aufloesung stumm.
            sauber = normalisiere_ort(location)
            if sauber and sauber.lower() != location.strip().lower():
                _rate_limit()
                result = geolocator.geocode(f"{sauber}, Deutschland",
                                            exactly_one=True)
                if result is not None:
                    logger.info("Geocoding erst nach Bereinigung erfolgreich: "
                                "'%s' -> '%s'", location, sauber)

        if result:
            coords = (result.latitude, result.longitude)
            with _cache_lock:
                _geo_cache[loc_key] = coords
            logger.debug("Geocoded '%s' -> %s", location, coords)
            return coords
        else:
            with _cache_lock:
                _geo_cache[loc_key] = None
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
