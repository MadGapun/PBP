"""JobSpy-Adapter (#490).

Zwei separate Adapter-Instanzen, damit LinkedIn und Indeed im Dashboard
einzeln an/abschaltbar sind — intern teilen sie sich `python-jobspy`.
"""

from __future__ import annotations

import time
from typing import Any

from .. import jobspy_source as _js
from .base import AdapterResult, AdapterStatus, JobPosting, JobSourceAdapter


class _JobSpyBase(JobSourceAdapter):
    """Gemeinsame Logik — Unterklassen setzen `source_key` + `_fn`."""

    _fn = staticmethod(lambda params: [])  # type: ignore

    def search(self, params: dict[str, Any]) -> AdapterResult:
        start = time.monotonic()
        if _js._ensure_jobspy() is None:
            return AdapterResult(
                status=AdapterStatus.NOT_CONFIGURED,
                postings=[],
                message="python-jobspy nicht installiert (pip install python-jobspy)",
                duration_s=round(time.monotonic() - start, 2),
            )
        try:
            raw = type(self)._fn(params) or []
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


class JobSpyLinkedInAdapter(_JobSpyBase):
    source_key = "jobspy_linkedin"
    _fn = staticmethod(_js.search_jobspy_linkedin)


class JobSpyIndeedAdapter(_JobSpyBase):
    source_key = "jobspy_indeed"
    _fn = staticmethod(_js.search_jobspy_indeed)
