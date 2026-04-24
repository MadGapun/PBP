"""Adapter-Interface (#499).

Die Job-Dicts, die die bestehenden Scraper liefern, werden im Adapter-
Pfad als `JobPosting`-Dataclass verpackt. Wichtig: Das Mapping ist
1:1 zu dem Dict-Schema, mit dem `db.save_jobs()` heute schon arbeitet —
ein Adapter gibt also keine neue Struktur ins System, nur eine
typisierte Sicht. Damit bleibt der Schreibpfad unveraendert.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class AdapterStatus(str, Enum):
    OK = "ok"
    DEPRECATED = "deprecated"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    NOT_CONFIGURED = "not_configured"
    ERROR = "error"


@dataclass
class JobPosting:
    """Typisierte Sicht auf das Job-Dict-Format.

    Alle Felder entsprechen den Spalten der `jobs`-Tabelle (siehe
    Database.save_jobs). Optional-Felder duerfen fehlen; der Schreibpfad
    behandelt `None` als Default.
    """

    hash: str
    title: str
    company: str
    location: str
    url: str
    source: str
    description: Optional[str] = None
    employment_type: str = "festanstellung"
    remote_level: str = "unbekannt"
    distance_km: Optional[float] = None
    salary_info: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_type: Optional[str] = None
    veroeffentlicht_am: Optional[str] = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_job_dict(self) -> dict[str, Any]:
        """Serialisiert in das Dict-Schema, das save_jobs() erwartet."""
        out: dict[str, Any] = {
            "hash": self.hash,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": self.url,
            "source": self.source,
            "description": self.description,
            "employment_type": self.employment_type,
            "remote_level": self.remote_level,
        }
        for key in ("distance_km", "salary_info", "salary_min", "salary_max",
                    "salary_type", "veroeffentlicht_am"):
            val = getattr(self, key)
            if val is not None:
                out[key] = val
        out.update(self.extra)
        return out

    @classmethod
    def from_job_dict(cls, data: dict[str, Any]) -> "JobPosting":
        """Baut eine JobPosting aus einem bestehenden Scraper-Dict.

        Unbekannte Keys landen in `extra` — damit brauchen wir die Adapter
        nicht zu aendern, wenn neue Felder dazukommen.
        """
        known = {
            "hash", "title", "company", "location", "url", "source",
            "description", "employment_type", "remote_level", "distance_km",
            "salary_info", "salary_min", "salary_max", "salary_type",
            "veroeffentlicht_am",
        }
        kwargs = {k: data[k] for k in known if k in data}
        extra = {k: v for k, v in data.items() if k not in known}
        return cls(**kwargs, extra=extra)


@dataclass
class AdapterResult:
    status: AdapterStatus
    postings: list[JobPosting] = field(default_factory=list)
    message: Optional[str] = None
    duration_s: float = 0.0

    @property
    def count(self) -> int:
        return len(self.postings)


class JobSourceAdapter(ABC):
    """Basisklasse fuer alle Adapter."""

    #: Stabiler Schluessel im SOURCE_REGISTRY (z.B. "bundesagentur").
    source_key: str = ""

    @abstractmethod
    def search(self, params: dict[str, Any]) -> AdapterResult:
        """Fuehrt eine Suche aus.

        Erwartet das bestehende `params`-Dict-Format der Pipeline
        (keywords, criteria, ...). Der Adapter ruft intern die alte
        `search_*`-Funktion auf und mappt auf `AdapterResult`.
        """

    def test_connection(self) -> AdapterStatus:
        """Default: OK melden. Adapter koennen das ueberschreiben."""
        return AdapterStatus.OK
