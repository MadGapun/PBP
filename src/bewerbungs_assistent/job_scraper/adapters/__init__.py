"""Scraper-Adapter v2 (#499, seit v1.6.0-beta.2).

Die Adapter kapseln die bestehenden Scraper-Module hinter einer
einheitlichen Schnittstelle (`JobSourceAdapter`) und einem Orchestrator
mit Fehler-Isolation.

Aktivierung: Feature-Flag `scraper_adapter_v2` (Default=False). Solange
aus, laeuft die gewohnte `run_search()`-Pipeline unveraendert.

Regeln:
- Ein Adapter ruft **nur** die bestehende `search_*`-Funktion seines
  Scraper-Moduls auf. Keine Logik-Duplikation.
- Exceptions werden im Orchestrator abgefangen und in `AdapterStatus.ERROR`
  uebersetzt — ein Adapter-Fehler reisst andere nicht mit.
"""

from .base import AdapterResult, AdapterStatus, JobPosting, JobSourceAdapter
from .orchestrator import run_adapters
from .registry import available_adapters, get_adapter

__all__ = [
    "AdapterResult",
    "AdapterStatus",
    "JobPosting",
    "JobSourceAdapter",
    "available_adapters",
    "get_adapter",
    "run_adapters",
]
