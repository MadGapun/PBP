"""Feature-Flags fuer PBP (#498).

Flags mit potenziell grossem Blast-Radius werden hier zentral verwaltet.
Default-Werte bleiben konservativ ("alte, stabile Implementierung") — neue
Codewege schalten sich erst ein, wenn der Flag explizit gesetzt wird.

Steuerung:
- In-Code: FEATURES-Dict in dieser Datei
- Zur Laufzeit: Env-Var `PBP_FEATURES="flag1,flag2"` (komma-separiert,
  aktiviert die aufgelisteten Flags zusaetzlich zum Default)

Konvention: Neue Flags werden dokumentiert mit *Zweck*, *Standardwert*
und *seit welcher Beta* sie existieren. Entfernung eines Flags erst,
wenn der neue Pfad stabil ist und der alte Code weg darf.
"""

from __future__ import annotations

import os
from typing import Dict


# Registrierte Flags. Default=False bedeutet: alter Code laeuft, neuer
# Code nur mit explizitem Opt-In.
FEATURES: Dict[str, bool] = {
    # #499 (seit Beta.2): Scraper-Architektur v2 als opt-in Orchestrator-Pfad.
    # Default=False: die gewohnte run_search()-Pipeline laeuft. Mit flag=True
    # ruft die Pipeline die neuen Adapter ueber den Orchestrator auf.
    "scraper_adapter_v2": False,
}


def _env_overrides() -> Dict[str, bool]:
    raw = os.environ.get("PBP_FEATURES", "").strip()
    if not raw:
        return {}
    return {name.strip(): True for name in raw.split(",") if name.strip()}


def is_enabled(name: str) -> bool:
    """Prueft ob ein Feature-Flag aktiv ist.

    Unbekannte Flags liefern False — neuer Code darf so keinen Default-Pfad
    verpassen.
    """
    overrides = _env_overrides()
    if name in overrides:
        return overrides[name]
    return FEATURES.get(name, False)


def enabled_flags() -> Dict[str, bool]:
    """Liefert alle aktuell aktiven Flags (fuer Debug/Dashboard)."""
    merged = dict(FEATURES)
    merged.update(_env_overrides())
    return {k: v for k, v in merged.items() if v}
