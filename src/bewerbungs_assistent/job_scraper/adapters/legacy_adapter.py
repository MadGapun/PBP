"""Generic legacy-scraper adapter (#499).

Wraps any existing `search_*`-Funktion des Scraper-Pakets hinter der
`JobSourceAdapter`-Schnittstelle, ohne fuer jede Quelle eine eigene
Klasse anzulegen. Quellen mit spezieller Logik (Bundesagentur, Hays,
JobSpy, GoogleJobs) bleiben als eigene Adapter bestehen — der
generische Wrapper ist der Default fuer alle uebrigen Eintraege in
`_SCRAPER_MAP`.
"""

from __future__ import annotations

import importlib
import time
from typing import Any

from .base import AdapterResult, AdapterStatus, JobPosting, JobSourceAdapter


class LegacyScraperAdapter(JobSourceAdapter):
    """Ruft die alte `search_*`-Funktion eines Scraper-Moduls auf."""

    def __init__(self, source_key: str, module_name: str, func_name: str) -> None:
        self.source_key = source_key
        self._module_name = module_name
        self._func_name = func_name

    def search(self, params: dict[str, Any]) -> AdapterResult:
        start = time.monotonic()
        try:
            mod = importlib.import_module(
                f"..{self._module_name}", package=__package__
            )
            fn = getattr(mod, self._func_name)
            raw = fn(params) or []
        except ImportError as exc:
            return AdapterResult(
                status=AdapterStatus.NOT_CONFIGURED,
                postings=[],
                message=str(exc),
                duration_s=round(time.monotonic() - start, 2),
            )
        except Exception as exc:
            return AdapterResult(
                status=AdapterStatus.ERROR,
                postings=[],
                message=str(exc),
                duration_s=round(time.monotonic() - start, 2),
            )
        postings = [JobPosting.from_job_dict(j) for j in raw]
        return AdapterResult(
            status=AdapterStatus.OK,
            postings=postings,
            duration_s=round(time.monotonic() - start, 2),
        )
