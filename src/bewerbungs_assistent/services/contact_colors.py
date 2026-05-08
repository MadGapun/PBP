"""Farb-Palette fuer Kontakt-Kategorien (#608).

16 vordefinierte Farben mit gutem Kontrast in Dark + Light Theme.
Auto-Farb-Vergabe: erste Farbe aus der Palette die noch keiner
Kategorie zugewiesen ist. Wenn alle belegt: rotieren.

Default-Kategorien (`is_system=1`) bekommen handpicked Farben damit
sie semantisch passen (z.B. Recruiter = Teal, HR = Blue).
"""

from __future__ import annotations


# 16-Farben-Palette, Hex-Werte. Alle haben Kontrastverhaeltnis >= 4.5
# auf dunklem (--bg ~#0d1117) UND hellem Hintergrund (--bg ~#fafafa).
COLOR_PALETTE: list[str] = [
    "#10B981",  # 1  Teal
    "#3B82F6",  # 2  Blue
    "#A855F7",  # 3  Purple
    "#F59E0B",  # 4  Amber
    "#EC4899",  # 5  Pink
    "#0EA5E9",  # 6  Sky
    "#84CC16",  # 7  Lime
    "#EF4444",  # 8  Red
    "#06B6D4",  # 9  Cyan
    "#8B5CF6",  # 10 Violet
    "#F97316",  # 11 Orange
    "#14B8A6",  # 12 Emerald
    "#6366F1",  # 13 Indigo
    "#D946EF",  # 14 Fuchsia
    "#22C55E",  # 15 Green
    "#6B7280",  # 16 Gray
]


# Default-Kategorien mit handpicked Farben, in dieser Reihenfolge angelegt.
DEFAULT_CATEGORIES: list[dict] = [
    {"slug": "recruiter",       "name": "Recruiter",       "color": "#10B981", "sort_order": 10},
    {"slug": "hr",              "name": "HR / Personal",   "color": "#3B82F6", "sort_order": 20},
    {"slug": "ansprechpartner", "name": "Ansprechpartner", "color": "#A855F7", "sort_order": 30},
    {"slug": "endkunde",        "name": "Endkunde",        "color": "#F59E0B", "sort_order": 40},
    {"slug": "vermittler",      "name": "Vermittler",      "color": "#EC4899", "sort_order": 50},
    {"slug": "referenz",        "name": "Referenz",        "color": "#0EA5E9", "sort_order": 60},
    {"slug": "sonstiges",       "name": "Sonstiges",       "color": "#6B7280", "sort_order": 90},
]


def slug_for_name(name: str) -> str:
    """Lowercase + ersetzt Umlaute + Whitespace zu '-'."""
    s = (name or "").strip().lower()
    rep = {
        "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        "Ä": "ae", "Ö": "oe", "Ü": "ue",
    }
    for k, v in rep.items():
        s = s.replace(k, v)
    out = []
    for ch in s:
        if ch.isalnum():
            out.append(ch)
        elif ch in (" ", "-", "_", "/"):
            out.append("-")
    slug = "".join(out).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return slug or "unbenannt"


def pick_next_color(existing_colors: list[str]) -> str:
    """Liefert die naechste freie Farbe aus der Palette.

    Wenn alle belegt: rotiert (Modulo) ueber die Palette.
    """
    if not existing_colors:
        return COLOR_PALETTE[0]
    used = set(existing_colors)
    for c in COLOR_PALETTE:
        if c not in used:
            return c
    # Alle 16 belegt → rotiert weiter
    return COLOR_PALETTE[len(existing_colors) % len(COLOR_PALETTE)]
