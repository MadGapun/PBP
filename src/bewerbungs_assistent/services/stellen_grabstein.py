"""Was zusammengefuehrt ist, kommt nicht wieder (#1084).

Gemeldet am 24.09.2026: eine Neuausschreibung wurde als Dublette erkannt
und per `stelle_mergen` in die Stelle mit der laufenden Bewerbung
zusammengefuehrt. Am naechsten Morgen stand sie mit DEMSELBEN Hash
wieder als ungepruefte Stelle auf Platz 1 der Liste.

**Die Ursache ist eine Luecke, kein Fehler im Zusammenfuehren.**
`merge_jobs` loescht die Dublette — damit weiss PBP nicht mehr, dass es
sie gab. Der naechste Suchlauf findet die Anzeige erneut, der Hash ist
unbekannt, und die Duplikaterkennung vergleicht nur mit der URL, die am
Master steht (die ALTE Anzeige). Die neue URL war nirgends gespeichert.

**Zwei Dinge halten die Erinnerung fest:**

1. Ein Grabstein je aufgeloester Stelle: ihr Hash zeigt dauerhaft auf
   den Master. Die Spalte heisst `job_hash`, damit ein spaeteres
   Zusammenfuehren des Masters den Verweis mitnimmt — `merge_jobs`
   haengt jede Tabelle mit dieser Spalte um (#1077).
2. Die URL der Dublette als Fundstelle am Master (`job_sources`, #951).
   Der Import vergleicht seit v1.7.127 auch gegen diese URLs.

**Ein Wiederfund wird vermerkt, nicht verschluckt.** Die Fundstelle am
Master bekommt `zuletzt_gesehen` — das ist ein Signal ("die Vakanz ist
weiter offen"), und #951 hat festgehalten, dass ein ersatzlos
verworfener Fund den Trichter aus #813 beluegt. Gezaehlt wird er als
Duplikat.

**Nicht fuer die manuelle Anlage.** Wer eine Stelle von Hand anlegt,
entscheidet bewusst; dort gilt die vorhandene Duplikat-Warnung.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def tabelle_anlegen(conn) -> None:
    """Safety-Net statt Schema-Bump — additiv, wie `job_sources` (#951)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS job_tombstones (
            alter_hash TEXT PRIMARY KEY,
            job_hash TEXT NOT NULL,
            url TEXT DEFAULT '',
            titel TEXT DEFAULT '',
            aufgeloest_am TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_job_tombstones_master "
                 "ON job_tombstones(job_hash)")
    # Die Fundstelle traegt seit #1084, wann sie zuletzt gesehen wurde.
    from . import stellen_quellen
    stellen_quellen.tabelle_anlegen(conn)
    spalten = {r[1] for r in conn.execute("PRAGMA table_info(job_sources)")}
    if "zuletzt_gesehen" not in spalten:
        conn.execute("ALTER TABLE job_sources ADD COLUMN zuletzt_gesehen "
                     "TEXT DEFAULT ''")


def anlegen(conn, alter_hash: str, master_hash: str, *, url: str = "",
            titel: str = "", jetzt: str = "") -> None:
    """Grabstein fuer eine aufgeloeste Stelle — innerhalb der Transaktion
    des Aufrufers, deshalb ohne eigenes commit."""
    if not alter_hash or not master_hash or alter_hash == master_hash:
        return
    # Die Tabelle legt der Aufrufer VOR seiner Transaktion an:
    # `stellen_quellen.tabelle_anlegen` committet, und ein commit mitten
    # im Zusammenfuehren machte es halb.
    conn.execute(
        "INSERT OR REPLACE INTO job_tombstones "
        "(alter_hash, job_hash, url, titel, aufgeloest_am) "
        "VALUES (?, ?, ?, ?, ?)",
        (alter_hash, master_hash, (url or "").strip(), titel or "", jetzt))
    # Grabsteine, die auf die aufgeloeste Stelle zeigten, haengt
    # `merge_jobs` schon um — wie jede Tabelle mit `job_hash` (#1077).


def master_fuer(conn, stored_hash: str) -> str | None:
    """Der Master einer aufgeloesten Stelle — nur, wenn es ihn noch gibt."""
    if not stored_hash:
        return None
    try:
        tabelle_anlegen(conn)
        zeile = conn.execute(
            "SELECT t.job_hash FROM job_tombstones t "
            "JOIN jobs j ON j.hash = t.job_hash WHERE t.alter_hash=?",
            (stored_hash,)).fetchone()
    except Exception as exc:  # pragma: no cover — nie einen Suchlauf kippen
        logger.debug("Grabstein nicht lesbar (%s): %s", stored_hash, exc)
        return None
    return zeile[0] if zeile else None


def fundstellen_kandidaten(conn, profil_id) -> list[dict]:
    """Die URLs aller Fundstellen aktiver Stellen, als Duplikat-Kandidaten.

    Bis v1.7.126 verglich der Import nur mit `jobs.url` — der ersten
    Anzeige. Eine zusammengefuehrte Neuausschreibung traegt eine andere.
    """
    try:
        tabelle_anlegen(conn)
        zeilen = conn.execute(
            "SELECT s.job_hash AS hash, j.title, j.company, s.url "
            "FROM job_sources s JOIN jobs j ON j.hash = s.job_hash "
            "WHERE j.is_active=1 AND s.url != '' AND s.url != j.url "
            "AND (j.profile_id=? OR j.profile_id IS NULL)",
            (profil_id,)).fetchall()
    except Exception as exc:  # pragma: no cover
        logger.debug("Fundstellen-Kandidaten nicht lesbar: %s", exc)
        return []
    return [dict(z) for z in zeilen]


def wiederfund(conn, master_hash: str, quelle: str, url: str, jetzt: str,
               job: dict | None = None) -> None:
    """Haelt am Master fest, dass die Anzeige erneut gefunden wurde."""
    job = job or {}
    tabelle_anlegen(conn)
    conn.execute(
        "INSERT OR IGNORE INTO job_sources "
        "(job_hash, source, url, gefunden_am, veroeffentlicht_am, "
        "suchbegriff, zuletzt_gesehen) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (master_hash, quelle or "unbekannt", (url or "").strip(), jetzt,
         job.get("veroeffentlicht_am") or "", job.get("suchbegriff") or "",
         jetzt))
    conn.execute(
        "UPDATE job_sources SET zuletzt_gesehen=? "
        "WHERE job_hash=? AND source=? AND url=?",
        (jetzt, master_hash, quelle or "unbekannt", (url or "").strip()))


def erneut_gesehen(db, job_hash: str) -> dict | None:
    """Wann und wo die Stelle zuletzt erneut gefunden wurde — oder None."""
    if not job_hash:
        return None
    try:
        conn = db.connect()
        tabelle_anlegen(conn)
        zeilen = conn.execute(
            "SELECT source, url, zuletzt_gesehen FROM job_sources "
            "WHERE job_hash=? AND zuletzt_gesehen != '' "
            "ORDER BY zuletzt_gesehen DESC", (job_hash,)).fetchall()
    except Exception as exc:  # pragma: no cover
        logger.debug("Wiederfunde nicht lesbar (%s): %s", job_hash, exc)
        return None
    if not zeilen:
        return None
    return {
        "am": zeilen[0]["zuletzt_gesehen"],
        "quelle": zeilen[0]["source"],
        "fundstellen": len(zeilen),
        "text": (f"Erneut gesehen am {zeilen[0]['zuletzt_gesehen'][:10]} "
                 f"({zeilen[0]['source']}) — die Anzeige läuft weiter."),
    }


def bericht(db) -> dict:
    """AK 4: zusammengefuehrte Stellen, die wieder aktiv im Bestand stehen.

    Nur lesend, ohne Auto-Fix. **Die Grenze gehoert gesagt:** fuer
    Zusammenfuehrungen vor v1.7.127 gibt es keine Spur — `merge_jobs`
    hat die Dublette damals ohne Vermerk geloescht. Solche Faelle findet
    nur der Dublettenvergleich (`stellen_dubletten_pruefen`).
    """
    conn = db.connect()
    tabelle_anlegen(conn)
    zeilen = conn.execute(
        "SELECT t.alter_hash, t.job_hash AS master, t.aufgeloest_am, "
        "j.title, j.found_at FROM job_tombstones t "
        "JOIN jobs j ON j.hash = t.alter_hash WHERE j.is_active=1").fetchall()
    gesamt = conn.execute("SELECT COUNT(*) FROM job_tombstones").fetchone()[0]
    return {
        "grabsteine": gesamt,
        "wiedergekehrt": [
            {"hash": db._public_job_hash(z["alter_hash"]) or z["alter_hash"],
             "master": db._public_job_hash(z["master"]) or z["master"],
             "titel": z["title"], "aufgeloest_am": z["aufgeloest_am"],
             "wieder_da_seit": z["found_at"]}
            for z in zeilen],
        "grenze": ("Zusammenführungen vor v1.7.127 hinterliessen keine "
                   "Spur. Wiedergekehrte Fälle daraus findet nur der "
                   "Dublettenvergleich dieses Werkzeugs."),
        "auto_fix": False,
    }
