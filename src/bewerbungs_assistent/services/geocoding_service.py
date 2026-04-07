"""Geocoding-Service fuer Entfernungsberechnung (#167).

Nutzt Nominatim (OpenStreetMap) via geopy — kostenlos, kein API-Key.
Rate-Limit: max 1 Request/Sekunde (Nominatim Fair-Use-Policy).
"""

import logging
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
