"""Wiki-Snippet-Loader (#623, v1.7.0-beta.45).

Liest beim Start alle `*.md`-Dateien aus `docs/wiki-snippets/` (außer
`README.md`), parsed YAML-Frontmatter und indexiert nach `page_route`.

Konsumenten:
- `dashboard.py::POST /api/wiki/request-hint` → Frontend ruft pro
  Page-Mount, max 1 pro Tag pro (profile, route)
- Elwosa-Trigger `wiki_hint` postet die ausgewaehlte Linie

Snippet-Format siehe `docs/wiki-snippets/README.md`.
"""
from __future__ import annotations

import logging
import random
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bewerbungs_assistent.wiki_snippets")

# Cache: einmalig beim Modul-Import befuellt, dann immutable.
_SNIPPETS: list[dict] = []
_INDEX_BY_ROUTE: dict[str, list[dict]] = {}


def _snippets_dir() -> Path:
    """Pfad zu docs/wiki-snippets/ — relativ zum Repo-Root."""
    # services/ -> bewerbungs_assistent/ -> src/ -> Repo-Root -> docs/
    return Path(__file__).resolve().parents[3] / "docs" / "wiki-snippets"


_FRONTMATTER_RE = re.compile(
    r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL
)
_KV_RE = re.compile(r"^([a-z_]+)\s*:\s*(.+?)\s*$", re.MULTILINE)


def _parse_snippet_file(path: Path) -> Optional[dict]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Kann Snippet %s nicht lesen: %s", path.name, exc)
        return None
    m = _FRONTMATTER_RE.match(text)
    if not m:
        logger.warning("Snippet %s hat kein YAML-Frontmatter", path.name)
        return None
    fm_block, body = m.group(1), m.group(2).strip()
    meta: dict[str, str] = {}
    for kv in _KV_RE.finditer(fm_block):
        meta[kv.group(1)] = kv.group(2).strip()
    required = ("id", "page_route", "wiki_page")
    missing = [k for k in required if k not in meta]
    if missing:
        logger.warning("Snippet %s fehlt Felder: %s", path.name, missing)
        return None
    return {
        "id": meta["id"],
        "page_route": meta["page_route"],
        "wiki_page": meta["wiki_page"],
        "title": meta.get("title", ""),
        "body": body,
        "source_file": path.name,
    }


def _load_all_snippets() -> None:
    """Modul-Init: laedt + indexiert alle Snippets. Idempotent."""
    global _SNIPPETS, _INDEX_BY_ROUTE
    _SNIPPETS = []
    _INDEX_BY_ROUTE = {}
    sdir = _snippets_dir()
    if not sdir.is_dir():
        logger.info("wiki-snippets Verzeichnis nicht gefunden: %s", sdir)
        return
    for path in sorted(sdir.glob("*.md")):
        if path.name.lower() == "readme.md":
            continue
        snippet = _parse_snippet_file(path)
        if snippet:
            _SNIPPETS.append(snippet)
            _INDEX_BY_ROUTE.setdefault(snippet["page_route"], []).append(snippet)
    logger.info("Wiki-Snippets geladen: %d aus %s",
                 len(_SNIPPETS), sdir)


# Auto-Load bei Modul-Import
_load_all_snippets()


def reload_snippets() -> int:
    """Re-load (z.B. fuer Tests oder Hot-Reload). Liefert Anzahl."""
    _load_all_snippets()
    return len(_SNIPPETS)


def get_all_snippets() -> list[dict]:
    """Alle geladenen Snippets (Read-only Snapshot)."""
    return list(_SNIPPETS)


def get_snippets_for_route(page_route: str) -> list[dict]:
    """Liefert alle Snippets fuer eine Route plus alle 'global'-Snippets."""
    out = list(_INDEX_BY_ROUTE.get(page_route, []))
    if page_route != "global":
        out.extend(_INDEX_BY_ROUTE.get("global", []))
    return out


def pick_snippet_for_route(page_route: str,
                            seen_ids: Optional[set[str]] = None) -> Optional[dict]:
    """Waehlt einen Snippet fuer die Route, der nicht in seen_ids steht.

    Wenn alle Kandidaten in seen_ids sind: faellt zurueck auf den vollen
    Pool (Repeat-zulassen). Wenn die Route keine Snippets hat (auch nicht
    via 'global'): None.
    """
    candidates = get_snippets_for_route(page_route)
    if not candidates:
        return None
    seen_ids = seen_ids or set()
    fresh = [s for s in candidates if s["id"] not in seen_ids]
    pool = fresh if fresh else candidates
    return random.choice(pool)
