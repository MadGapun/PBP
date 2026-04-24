"""Google-Jobs-Adapter (#501).

Kein automatischer Abruf — der Adapter existiert, damit Google Jobs
als Quelle im Dashboard erscheint und der URL-Builder eine konsistente
Adresse liefert, die die Chrome-Extension oeffnen kann.
"""

from __future__ import annotations

import time
from typing import Any

from .. import google_jobs as _gj
from .base import AdapterResult, AdapterStatus, JobSourceAdapter


class GoogleJobsChromeAdapter(JobSourceAdapter):
    source_key = "google_jobs"

    def search(self, params: dict[str, Any]) -> AdapterResult:
        start = time.monotonic()
        _gj.search_google_jobs(params)  # loggt URLs fuer den Nutzer

        kw_data = params.get("keywords", {}) or {}
        if isinstance(kw_data, dict):
            keywords = kw_data.get("general", [])
            regionen = kw_data.get("regionen", [])
        else:
            keywords = kw_data or []
            regionen = []
        ort = regionen[0] if regionen else None
        urls = [
            _gj.build_google_jobs_url(kw, zeitraum="woche", ort=ort)
            for kw in keywords
        ]

        base_msg = (
            "Google Jobs laeuft manuell: URL(s) im Chrome-Browser mit "
            "Claude-in-Chrome oeffnen und Treffer ueber "
            "stelle_manuell_anlegen() uebernehmen."
        )
        message = f"{base_msg} URLs: {urls}" if urls else base_msg

        return AdapterResult(
            status=AdapterStatus.NOT_CONFIGURED,
            postings=[],
            message=message,
            duration_s=round(time.monotonic() - start, 2),
        )
