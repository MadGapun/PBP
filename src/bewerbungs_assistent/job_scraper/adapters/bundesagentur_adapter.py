"""Bundesagentur-Adapter (#489, #499)."""

from __future__ import annotations

import time
from typing import Any

from .. import bundesagentur as _ba
from .base import AdapterResult, AdapterStatus, JobPosting, JobSourceAdapter


class BundesagenturAdapter(JobSourceAdapter):
    source_key = "bundesagentur"

    def search(self, params: dict[str, Any]) -> AdapterResult:
        start = time.monotonic()
        try:
            raw = _ba.search_bundesagentur(params) or []
        except Exception as exc:  # Fehler-Isolation (#499)
            return AdapterResult(
                status=AdapterStatus.ERROR,
                postings=[],
                message=str(exc),
                duration_s=round(time.monotonic() - start, 2),
            )
        postings = [JobPosting.from_job_dict(j) for j in raw]
        return AdapterResult(
            status=AdapterStatus.OK if postings else AdapterStatus.OK,
            postings=postings,
            duration_s=round(time.monotonic() - start, 2),
        )
