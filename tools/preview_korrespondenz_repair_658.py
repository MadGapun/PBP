"""READ-ONLY Vorschau: was wuerde dokumente_korrespondenz_abschliessen()
gegen die echte AppData-DB anpacken?

Repliziert die Filter-Logik des MCP-Tools 1:1, ohne irgendetwas zu
schreiben — der laufende MCP-Server bei dir kennt das neue Tool erst
nach Restart, deshalb hier ein eigener Vorschau-Pfad.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB = Path(r"C:\Users\MAD\AppData\Local\BewerbungsAssistent\data\pbp.db")
PROFILE_ID = "e913acc3"

_KORRESPONDENZ_DOC_TYPES = {
    "sonstiges", "recruiter_anfrage", "angebot",
    "absage", "einladung", "eingangsbestaetigung",
    "interview_bestaetigung", "interview_einladung",
    "gespraechs_feedback", "projekt_update",
    "vermittler_korrespondenz",
}


def main() -> int:
    uri = f"file:{DB.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    print(f"DB: {DB}")
    print(f"Profil: {PROFILE_ID}")
    print(f"Erlaubte Typen: {sorted(_KORRESPONDENZ_DOC_TYPES)}")
    print()

    placeholders = ",".join("?" * len(_KORRESPONDENZ_DOC_TYPES))
    rows = cur.execute(
        "SELECT id, filename, doc_type, extraction_status, "
        "COALESCE(linked_application_id, 0) AS aid, "
        "COALESCE(created_at,'') AS created_at "
        "FROM documents "
        "WHERE profile_id=? "
        "AND extraction_status IN ('basis_analysiert','analysiert','analysiert_leer') "
        f"AND doc_type IN ({placeholders}) "
        "ORDER BY created_at DESC",
        (PROFILE_ID, *sorted(_KORRESPONDENZ_DOC_TYPES)),
    ).fetchall()

    print(f"Vorschau-Treffer: {len(rows)} Dokument(e) wuerden auf 'angewendet' gesetzt")
    print()
    if rows:
        print(f"{'id':10s} {'doc_type':25s} {'status':22s} {'aid':>10} | filename")
        print("-" * 100)
        for r in rows:
            fn = (r["filename"] or "")
            if len(fn) > 50:
                fn = fn[:47] + "..."
            print(
                f"{r['id']:10s} {r['doc_type']:25s} "
                f"{r['extraction_status']:22s} {str(r['aid'] or ''):>10} | {fn}"
            )
    print()

    # Zusaetzlich: Schutz-Check — wieviele NICHT-Korrespondenz-Docs sind im
    # selben Bucket? Die bleiben unberuehrt, sollten aber sichtbar sein.
    rows2 = cur.execute(
        "SELECT doc_type, COUNT(*) AS n "
        "FROM documents "
        "WHERE profile_id=? "
        "AND extraction_status IN ('basis_analysiert','analysiert','analysiert_leer') "
        f"AND doc_type NOT IN ({placeholders}) "
        "GROUP BY doc_type ORDER BY n DESC",
        (PROFILE_ID, *sorted(_KORRESPONDENZ_DOC_TYPES)),
    ).fetchall()
    print(f"Nicht-Korrespondenz im selben Bucket (bleiben UNBERUEHRT): {len(rows2)}")
    for r in rows2:
        print(f"  {r['doc_type']:25s} {r['n']:6d}")

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
