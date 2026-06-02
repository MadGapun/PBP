"""Phase 0 IST-Analyse: Inventur der echten DB unter AppData.

Liest READ-ONLY, schreibt nichts. Gibt ASCII-sicheren Bericht aus.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

DB = Path(r"C:\Users\MAD\AppData\Local\BewerbungsAssistent\data\pbp.db")


def header(title: str) -> None:
    print("\n=== " + title + " ===")


def main() -> int:
    if not DB.exists():
        print("DB nicht gefunden: " + str(DB))
        return 1
    # READ-ONLY URI mode + WAL-safe (immutable=0 default)
    uri = f"file:{DB.as_posix()}?mode=ro"
    con = sqlite3.connect(uri, uri=True)
    con.row_factory = sqlite3.Row
    cur = con.cursor()

    header("DB-Datei")
    print(f"path={DB}")
    print(f"size_bytes={DB.stat().st_size}")

    header("PRAGMA user_version")
    cur.execute("PRAGMA user_version")
    print(cur.fetchone()[0])

    header("documents: Schema")
    cur.execute("PRAGMA table_info(documents)")
    for row in cur.fetchall():
        print(dict(row))

    header("documents: Indexe")
    cur.execute("PRAGMA index_list(documents)")
    idx_list = cur.fetchall()
    for row in idx_list:
        print(dict(row))
        cur2 = con.cursor()
        cur2.execute(f"PRAGMA index_info({row['name']})")
        for ir in cur2.fetchall():
            print("  " + str(dict(ir)))

    header("documents: Gesamtzahl")
    cur.execute("SELECT COUNT(*) FROM documents")
    print(cur.fetchone()[0])

    header("documents: extraction_status Verteilung")
    cur.execute(
        "SELECT COALESCE(extraction_status,'<NULL>') AS s, COUNT(*) AS n "
        "FROM documents GROUP BY s ORDER BY n DESC"
    )
    for row in cur.fetchall():
        print(f"{row['s']:30s} {row['n']:6d}")

    header("documents: doc_type Verteilung")
    cur.execute(
        "SELECT COALESCE(doc_type,'<NULL>') AS t, COUNT(*) AS n "
        "FROM documents GROUP BY t ORDER BY n DESC"
    )
    for row in cur.fetchall():
        print(f"{row['t']:30s} {row['n']:6d}")

    header("documents: profile_id Verteilung (Top 5)")
    cur.execute(
        "SELECT COALESCE(profile_id,'<NULL>') AS p, COUNT(*) AS n "
        "FROM documents GROUP BY p ORDER BY n DESC LIMIT 5"
    )
    for row in cur.fetchall():
        print(f"{row['p']:40s} {row['n']:6d}")

    header("documents: basis_analysiert nach doc_type (das #658-Knaeuel)")
    cur.execute(
        "SELECT COALESCE(doc_type,'<NULL>') AS t, COUNT(*) AS n "
        "FROM documents WHERE extraction_status='basis_analysiert' "
        "GROUP BY t ORDER BY n DESC"
    )
    for row in cur.fetchall():
        print(f"{row['t']:30s} {row['n']:6d}")

    header("documents: Beispiele basis_analysiert (5 Stueck)")
    cur.execute(
        "SELECT id, doc_type, COALESCE(filename,'') AS fn, "
        "COALESCE(linked_application_id,0) AS aid, "
        "COALESCE(extraction_status,'') AS es, "
        "COALESCE(created_at,'') AS ca "
        "FROM documents WHERE extraction_status='basis_analysiert' "
        "ORDER BY created_at DESC LIMIT 5"
    )
    for row in cur.fetchall():
        print(dict(row))

    header("documents: angewendet Beispiele (5 Stueck) - Vergleich")
    cur.execute(
        "SELECT id, doc_type, COALESCE(filename,'') AS fn, "
        "COALESCE(linked_application_id,0) AS aid, "
        "COALESCE(extraction_status,'') AS es, "
        "COALESCE(created_at,'') AS ca "
        "FROM documents WHERE extraction_status='angewendet' "
        "ORDER BY created_at DESC LIMIT 5"
    )
    for row in cur.fetchall():
        print(dict(row))

    header("documents: Korrespondenz-Typen, die #658 trifft (sonstiges/recruiter/angebot)")
    cur.execute(
        "SELECT doc_type, extraction_status, COUNT(*) AS n "
        "FROM documents "
        "WHERE doc_type IN ('sonstiges','recruiter_anfrage','angebot') "
        "GROUP BY doc_type, extraction_status "
        "ORDER BY doc_type, extraction_status"
    )
    for row in cur.fetchall():
        print(f"{row['doc_type']:25s} {row['extraction_status']:25s} {row['n']:6d}")

    header("documents: Wie viele Korrespondenz-Docs OHNE linked_application_id?")
    cur.execute(
        "SELECT doc_type, COUNT(*) AS n "
        "FROM documents "
        "WHERE doc_type IN ('sonstiges','recruiter_anfrage','angebot') "
        "  AND (linked_application_id IS NULL OR linked_application_id=0) "
        "GROUP BY doc_type"
    )
    for row in cur.fetchall():
        print(f"{row['doc_type']:25s} {row['n']:6d}")

    header("Tabellen mit 'document' im Namen / Lookup-Strukturen")
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND (name LIKE '%document%' OR name LIKE '%doc_%' OR name='applications') "
        "ORDER BY name"
    )
    for row in cur.fetchall():
        print(row[0])

    header("applications: Schema (fuer Lifecycle-Auto-Veralten)")
    cur.execute("PRAGMA table_info(applications)")
    for row in cur.fetchall():
        print(dict(row))

    header("applications: status Verteilung (Auto-Veralten-Quellen)")
    cur.execute(
        "SELECT COALESCE(status,'<NULL>') AS s, COUNT(*) AS n "
        "FROM applications GROUP BY s ORDER BY n DESC"
    )
    for row in cur.fetchall():
        print(f"{row['s']:30s} {row['n']:6d}")

    header("documents: existiert bereits 'lifecycle' Spalte? (Vorab-Check)")
    cur.execute("PRAGMA table_info(documents)")
    cols = [r["name"] for r in cur.fetchall()]
    print("lifecycle vorhanden?", "lifecycle" in cols)
    print("alle Spalten:", cols)

    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
