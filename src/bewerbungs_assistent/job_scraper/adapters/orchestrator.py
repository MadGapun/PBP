"""Scraper-Orchestrator (#499).

Isoliert Adapter-Fehler, damit ein kaputter Adapter die anderen nicht
mitreisst. Ersetzt in Beta.2 noch NICHT die bestehende
`run_search()`-Pipeline — wird ueber das Feature-Flag
`scraper_adapter_v2` spaeter (Block B, Beta.4) aufgeschaltet.

Hier bewusst synchron gehalten — die Threading-/Playwright-Orchestration
der alten Pipeline bleibt als Referenz bestehen, bis alle Adapter
migriert sind.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Iterable

from .base import AdapterResult, AdapterStatus
from .registry import get_adapter

logger = logging.getLogger("bewerbungs_assistent.scraper.adapters")


def run_adapters(source_keys: Iterable[str], params: dict[str, Any]) -> dict[str, AdapterResult]:
    """Ruft alle gewaehlten Adapter nacheinander auf und sammelt Ergebnisse.

    Unbekannte/nicht registrierte source_keys liefern NOT_CONFIGURED —
    der Orchestrator kippt nicht um, der Aufrufer sieht transparent,
    welche Quellen fehlen.
    """
    results: dict[str, AdapterResult] = {}
    for key in source_keys:
        adapter = get_adapter(key)
        if adapter is None:
            results[key] = AdapterResult(
                status=AdapterStatus.NOT_CONFIGURED,
                postings=[],
                message="Kein Adapter registriert",
            )
            continue
        start = time.monotonic()
        try:
            res = adapter.search(params)
        except Exception as exc:  # Doppel-Isolation: falls der Adapter selbst wirft
            logger.exception("Adapter %s crash", key)
            res = AdapterResult(
                status=AdapterStatus.ERROR,
                postings=[],
                message=str(exc),
                duration_s=round(time.monotonic() - start, 2),
            )
        results[key] = res
        logger.info("adapter=%s status=%s count=%d dur=%.2fs",
                    key, res.status.value, res.count, res.duration_s)
    return results
