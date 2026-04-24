"""Adapter-Registry (#499).

Kartiert `source_key` → Adapter-Instanz. Bewusst minimal: kein
Auto-Discovery, damit ein importierter Adapter-Bug nicht das ganze
Paket abschiesst.

Spezialisierte Adapter (Bundesagentur, Hays, JobSpy, GoogleJobs) mit
eigener Logik werden explizit registriert. Der Rest wird ueber den
generischen `LegacyScraperAdapter` aus `_SCRAPER_MAP` abgeleitet — so
deckt der Orchestrator ab Beta.12 alle Quellen ab, ohne dass wir fuer
jede Quelle eine eigene Adapter-Klasse schreiben muessen.
"""

from __future__ import annotations

from typing import Dict

from .base import JobSourceAdapter
from .bundesagentur_adapter import BundesagenturAdapter
from .google_jobs_adapter import GoogleJobsChromeAdapter
from .hays_adapter import HaysAdapter
from .jobspy_adapter import JobSpyIndeedAdapter, JobSpyLinkedInAdapter
from .legacy_adapter import LegacyScraperAdapter

# Quellen mit eigener Adapter-Klasse. Diese ueberschreiben ggf.
# gleichnamige Eintraege aus _SCRAPER_MAP.
_SPECIALIZED: Dict[str, JobSourceAdapter] = {
    "bundesagentur": BundesagenturAdapter(),
    "hays": HaysAdapter(),
    "jobspy_linkedin": JobSpyLinkedInAdapter(),
    "jobspy_indeed": JobSpyIndeedAdapter(),
    "google_jobs": GoogleJobsChromeAdapter(),
}


def _build_registry() -> Dict[str, JobSourceAdapter]:
    """Baut Registry aus Specialised + Legacy-Adapter pro _SCRAPER_MAP-Eintrag."""
    # Import hier, um Zirkel beim Paket-Laden zu vermeiden
    from .. import _SCRAPER_MAP

    registry: Dict[str, JobSourceAdapter] = {}
    for source_key, (module_name, func_name) in _SCRAPER_MAP.items():
        if source_key in _SPECIALIZED:
            continue
        registry[source_key] = LegacyScraperAdapter(source_key, module_name, func_name)
    registry.update(_SPECIALIZED)
    return registry


_ADAPTERS: Dict[str, JobSourceAdapter] = _build_registry()


def get_adapter(source_key: str) -> JobSourceAdapter | None:
    return _ADAPTERS.get(source_key)


def available_adapters() -> list[str]:
    return sorted(_ADAPTERS.keys())
