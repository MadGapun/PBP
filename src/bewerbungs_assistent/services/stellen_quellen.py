"""Eine Stelle, mehrere Fundstellen (#951).

Bis v1.7.71 trug eine Stelle genau EINE Quelle. Wurde dieselbe Anzeige
ueber ein zweites Portal gefunden, entstand ein zweiter Eintrag — im
guenstigen Fall automatisch als `duplikat` aussortiert, im ungueltigen
Fall als vermeintlicher Neufund, den der Mensch von Hand wegklickte.
Gemessen am Bestand: **44 Aussortierungen von Hand**, die keine
fachliche Entscheidung waren.

Der Nutzer nennt zwei Gruende, und der zweite wiegt schwerer als der
erste:

1. Dieselbe Stelle soll nicht ueber jede weitere Quelle erneut als
   Neufund hereinkommen.
2. **Zu wissen, wo ueberall eine Stelle ausgeschrieben ist, ist selbst
   eine Information.**

## Was gespeichert wird

Eine Zeile je Fundstelle: Quelle, URL, Zeitpunkt. Das Feld `jobs.source`
bleibt unangetastet und traegt weiterhin die ERSTE Quelle — so bricht
nichts, was heute darauf zeigt (Quellen-Statistik, Health-Check,
Trichter).

## Was ausdruecklich NICHT passiert

**Kein Score-Bonus je Mehrfachfund.** #59 hatte das vorgeschlagen; die
Nutzer-Einordnung im Issue widerspricht mit einem guten Argument: eine
breit gestreute Stelle ist oft eine schwer besetzbare, nicht eine
bessere. Streuung ist nicht Passung. Die Zahl ist ein HINWEIS
("auf 4 Portalen ausgeschrieben"), keine Bewertung.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def tabelle_anlegen(conn) -> None:
    """Safety-Net statt Schema-Bump — additiv, Muster aus #784/#1007.

    Die beiden Linien stehen auf v48 und v52; eine reine
    CREATE-IF-NOT-EXISTS-Tabelle braucht keine Versionsnummer.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            job_hash TEXT NOT NULL,
            source TEXT NOT NULL,
            url TEXT DEFAULT '',
            gefunden_am TEXT NOT NULL,
            veroeffentlicht_am TEXT DEFAULT '',
            UNIQUE(job_hash, source, url)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_job_sources_hash "
                 "ON job_sources(job_hash)")
    conn.commit()


def vermerken(db, job_hash: str, quelle: str, *, url: str = "",
              veroeffentlicht_am: str = "") -> bool:
    """Haelt fest, dass diese Stelle bei dieser Quelle gefunden wurde.

    Das Nadeloehr: wer eine Fundstelle notiert, ruft das hier. Eine
    zweite Schreibstelle waere genau die Bauform, aus der dieses Issue
    entstanden ist.

    Doppelte Eintraege sind unmoeglich (UNIQUE) und kosten nichts —
    derselbe Suchlauf darf dieselbe Stelle mehrfach liefern.

    Returns:
        True, wenn eine NEUE Fundstelle entstanden ist.
    """
    quelle = (quelle or "").strip()
    if not job_hash or not quelle:
        return False
    try:
        from ..database import _now
        conn = db.connect()
        tabelle_anlegen(conn)
        cur = conn.execute(
            "INSERT OR IGNORE INTO job_sources "
            "(job_hash, source, url, gefunden_am, veroeffentlicht_am) "
            "VALUES (?, ?, ?, ?, ?)",
            (job_hash, quelle, (url or "").strip(), _now(),
             (veroeffentlicht_am or "").strip()),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception as exc:  # pragma: no cover — nie einen Suchlauf kippen
        logger.debug("Fundstelle nicht vermerkbar (%s): %s", job_hash, exc)
        return False


def lesen(db, job_hash: str) -> list:
    """Alle Fundstellen einer Stelle, aelteste zuerst."""
    if not job_hash:
        return []
    try:
        conn = db.connect()
        tabelle_anlegen(conn)
        return [dict(r) for r in conn.execute(
            "SELECT source, url, gefunden_am, veroeffentlicht_am "
            "FROM job_sources WHERE job_hash=? ORDER BY gefunden_am",
            (job_hash,)).fetchall()]
    except Exception as exc:  # pragma: no cover
        logger.debug("Fundstellen nicht lesbar (%s): %s", job_hash, exc)
        return []


def uebersicht(db, job: dict) -> dict | None:
    """Die Quellenliste einer Stelle, fertig zum Anzeigen.

    Gibt None zurueck, solange es nur EINE Fundstelle gibt — dann ist
    die Liste keine Information, sondern eine Wiederholung des
    `source`-Feldes.
    """
    if not job:
        return None
    hash_ = job.get("hash") or ""
    eintraege = lesen(db, hash_)
    quellen = []
    for e in eintraege:
        if e.get("source") and e["source"] not in quellen:
            quellen.append(e["source"])
    # Die urspruengliche Quelle gehoert dazu, auch wenn sie (Altbestand)
    # noch keine eigene Zeile hat.
    erste = (job.get("source") or "").strip()
    if erste and erste not in quellen:
        quellen.insert(0, erste)
    if len(quellen) < 2:
        return None
    return {
        "quellen": quellen,
        "anzahl": len(quellen),
        "text": f"Auf {len(quellen)} Portalen ausgeschrieben",
        # Bewusst ohne Score-Wirkung: siehe Modul-Kopf.
        "wirkt_auf_score": False,
        "fundstellen": eintraege,
    }
