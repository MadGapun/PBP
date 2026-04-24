"""Hays-Adapter (#499 — Referenz-Adapter fuer Sitemap/JSON-LD-Quelle)."""

from __future__ import annotations

import time
from typing import Any

from .. import hays as _hays
from .base import AdapterResult, AdapterStatus, JobPosting, JobSourceAdapter


class HaysAdapter(JobSourceAdapter):
    source_key = "hays"

    def search(self, params: dict[str, Any]) -> AdapterResult:
        start = time.monotonic()
        try:
            raw = _hays.search_hays(params) or []
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
