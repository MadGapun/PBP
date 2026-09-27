"""Die Blacklist auf die aktiven Stellen anwenden — ein Weg (#992-Klasse).

Abgrenzung: `blacklist_regel` beantwortet, OB ein Eintrag eine Stelle
trifft. Hier steht, was dann mit dem Bestand geschieht.

Bis hierher gab es zwei Wege mit zwei Regeln:
- `blacklist_anwenden` ging ueber `blacklist_regel` und `db.dismiss_job`;
- das sofortige Aussortieren beim Anlegen eines Firmen-Eintrags ueber
  Claude war ein rohes `UPDATE jobs ... LIKE`, ohne Profilfilter (es traf
  die Stellen ALLER Profile), ohne Zeitpunkt und Herkunft im
  Aussortier-Protokoll (#1010) und mit einer eigenen Fassung der Regel;
- der Dashboard-Weg sortierte beim Anlegen gar nichts aus.
"""
from __future__ import annotations

import logging

from . import blacklist_regel

logger = logging.getLogger(__name__)


def anwenden(db, *, dry_run: bool = True, nur_wert: str | None = None) -> dict:
    """Findet (und sortiert bei dry_run=False aus) aktive Stellen des
    aktiven Profils, die ein Blacklist-Eintrag trifft.

    Args:
        nur_wert: nur die Treffer dieses einen Eintrags (Wert, klein) —
            fuer das Aussortieren direkt beim Anlegen.
    """
    eintraege = db.get_blacklist()
    if nur_wert is not None:
        ziel = nur_wert.strip().lower()
        eintraege = [e for e in eintraege if (e.get("value") or "").strip().lower() == ziel]
    verschont, treffer = [], []
    for j in db.get_active_jobs():
        firma, titel = j.get("company") or "", j.get("title") or ""
        rettung = blacklist_regel.verschont(eintraege, firma, titel)
        if rettung:
            verschont.append({"hash": j.get("hash"), "titel": j.get("title"),
                              "firma": j.get("company"),
                              "ausnahme_begriff": rettung["begriff"]})
        hit = blacklist_regel.treffer(eintraege, firma, titel)
        if hit:
            treffer.append({"job": j, "trigger": hit["typ"],
                            "wert": (hit["wert"] or "").lower()})
    ergebnis = {"treffer": treffer, "verschont": verschont, "deaktiviert": 0,
                "firmen": {}}
    if dry_run:
        return ergebnis
    for m in treffer:
        h = m["job"].get("hash")
        if not h:
            continue
        try:
            # Das Nadeloehr: Zeitpunkt, Herkunft, Profil (#913, #1010).
            # Herkunft "ich": die Folge eines Blacklist-Eintrags, den der
            # Mensch gesetzt hat — kein Urteil der Automatik.
            if db.dismiss_job(h, f"{m['trigger']}_blacklisted", herkunft="ich"):
                ergebnis["deaktiviert"] += 1
                firma = m["job"].get("company") or "?"
                ergebnis["firmen"][firma] = ergebnis["firmen"].get(firma, 0) + 1
        except Exception as exc:  # noqa: BLE001 — eine Stelle stoppt nichts
            logger.warning("Blacklist: %s nicht aussortiert: %s", h, exc)
    return ergebnis
