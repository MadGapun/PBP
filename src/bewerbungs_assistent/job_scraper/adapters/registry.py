"""Adapter-Registry (#499).

Kartiert `source_key` → Adapter-Instanz. Bewusst minimal: kein
Auto-Discovery, damit ein importierter Adapter-Bug nicht das ganze
Paket abschiesst.

Mit wachsender Adapter-Zahl wandern weitere Registrierungen hier rein —
der Orchestrator bekommt die Adapter nur ueber diese Schicht, nie direkt.
"""

from __future__ import annotations

from typing import Dict

from .base import JobSourceAdapter
from .bundesagentur_adapter import BundesagenturAdapter
from .hays_adapter import HaysAdapter

_ADAPTERS: Dict[str, JobSourceAdapter] = {
    "bundesagentur": BundesagenturAdapter(),
    "hays": HaysAdapter(),
}


def get_adapter(source_key: str) -> JobSourceAdapter | None:
    return _ADAPTERS.get(source_key)


def available_adapters() -> list[str]:
    return sorted(_ADAPTERS.keys())
