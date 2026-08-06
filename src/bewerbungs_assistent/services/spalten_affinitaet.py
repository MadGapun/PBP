"""Heilung der SQLite-Spalten-Affinitaet bei Text-IDs (#796/A25, v1.7.11).

Das Problem in einem Satz: Eine Spalte mit NUMERIC-Affinitaet (Typ
INTEGER/REAL) wandelt einen Text still in eine Zahl um, wenn der Text wie
eine Zahl aussieht — und PBP-IDs sind 8-stellige Hex-Strings, von denen
manche genau das tun.

    '42061e46'  ->  4.2061e+50   (wissenschaftliche Notation)
    '1e960980'  ->  inf          (Ueberlauf!)

Folgen im belegten Bestand:

* `dokument_verknuepfen()` bricht mit "FOREIGN KEY constraint failed" ab —
  die geschriebene Zahl trifft keine Zeile in `applications`.
* Drei Dokumente tragen `inf`. Das ist die gefaehrlichere Haelfte: beim
  Vergleich konvertiert SQLite die Textspalte ebenfalls, und `inf = inf`
  ist wahr. Ein `NOT EXISTS`-Abgleich meldet solche Zeilen als sauber,
  obwohl sie rechnerisch zu JEDER ueberlaufenden Bewerbung passen. Eine
  falsche Zuordnung, die keine Pruefung als solche erkennt.

Frische Installationen sind nicht betroffen — dort steht laut SCHEMA_SQL
bereits TEXT. Der Fehler steckt ausschliesslich in gewachsenen Bestaenden
(Schema-Parity-Fehlerklasse aus #738).

Rueckuebersetzung: nicht raten, sondern gegen die echten IDs pruefen. Fuer
jeden verunglueckten Wert wird gesucht, welche vorhandene ID beim
Konvertieren genau diese Zahl ergibt. Genau ein Treffer = eindeutig
heilbar. Mehrere Treffer (der `inf`-Fall) = NICHT rekonstruierbar; dann
wird die Verknuepfung ehrlich geleert statt eine falsche zu behalten.
"""
from __future__ import annotations

from typing import Any

# (Tabelle, Spalte, Ziel-Tabelle mit den echten IDs)
ID_SPALTEN = [
    ("documents", "linked_application_id", "applications"),
    ("documents", "linked_position_id", "positions"),
]


def _deklarierter_typ(conn, tabelle: str, spalte: str) -> str | None:
    try:
        for c in conn.execute(f"PRAGMA table_info({tabelle})").fetchall():
            if c["name"] == spalte:
                return (c["type"] or "").upper()
    except Exception:
        pass
    return None


def _hat_numerische_affinitaet(typ: str | None) -> bool:
    """SQLite-Regeln: INT* -> INTEGER-Affinitaet; REAL/FLOA/DOUB -> REAL;
    leer -> BLOB (harmlos); alles mit CHAR/CLOB/TEXT -> TEXT (harmlos)."""
    if not typ:
        return False
    t = typ.upper()
    if "INT" in t:
        return True
    if any(k in t for k in ("CHAR", "CLOB", "TEXT")):
        return False
    if "BLOB" in t:
        return False
    if any(k in t for k in ("REAL", "FLOA", "DOUB")):
        return True
    return True  # NUMERIC und Unbekanntes: numerisch


def pruefe(db: Any) -> dict:
    """Reine Diagnose — findet falsche Affinitaeten und verunglueckte Werte."""
    conn = db.connect()
    befunde = []
    for tabelle, spalte, ziel in ID_SPALTEN:
        typ = _deklarierter_typ(conn, tabelle, spalte)
        if typ is None:
            continue  # Spalte existiert in dieser Linie nicht
        falsch_deklariert = _hat_numerische_affinitaet(typ)
        try:
            verteilung = {
                r["t"]: r["n"] for r in conn.execute(
                    f"SELECT typeof({spalte}) AS t, COUNT(*) AS n "
                    f"FROM {tabelle} WHERE {spalte} IS NOT NULL "
                    f"GROUP BY typeof({spalte})").fetchall()
            }
        except Exception:
            continue
        kaputt = sum(n for t, n in verteilung.items()
                     if t in ("real", "integer"))
        if falsch_deklariert or kaputt:
            befunde.append({
                "tabelle": tabelle,
                "spalte": spalte,
                "deklarierter_typ": typ,
                "affinitaet_falsch": falsch_deklariert,
                "typ_verteilung": verteilung,
                "betroffene_zeilen": kaputt,
            })
    return {
        "befunde": befunde,
        "handlungsbedarf": any(
            b["affinitaet_falsch"] or b["betroffene_zeilen"] for b in befunde),
    }


def _rueckuebersetzen(conn, tabelle: str, spalte: str, ziel: str) -> dict:
    """Verunglueckte Zahlwerte gegen die echten IDs aufloesen."""
    echte = [r["id"] for r in conn.execute(f"SELECT id FROM {ziel}").fetchall()
             if isinstance(r["id"], str)]
    # Mapping Zahl -> Liste passender echter IDs
    nach_zahl: dict = {}
    for eid in echte:
        try:
            zahl = float(eid)
        except (TypeError, ValueError):
            continue  # reine Text-ID, kann gar nicht verunglueckt sein
        nach_zahl.setdefault(zahl, []).append(eid)

    geheilt, geleert, unklar = 0, 0, []
    rows = conn.execute(
        f"SELECT rowid, {spalte} AS wert, typeof({spalte}) AS t "
        f"FROM {tabelle} WHERE {spalte} IS NOT NULL "
        f"AND typeof({spalte}) IN ('real','integer')").fetchall()
    for r in rows:
        try:
            wert = float(r["wert"])
        except (TypeError, ValueError):
            continue
        treffer = nach_zahl.get(wert, [])
        if len(treffer) == 1:
            conn.execute(
                f"UPDATE {tabelle} SET {spalte}=? WHERE rowid=?",
                (treffer[0], r["rowid"]))
            geheilt += 1
        else:
            # Kein oder mehrdeutiger Treffer (der inf-Fall): lieber keine
            # Verknuepfung als eine falsche.
            conn.execute(
                f"UPDATE {tabelle} SET {spalte}=NULL WHERE rowid=?",
                (r["rowid"],))
            geleert += 1
            unklar.append({
                "rowid": r["rowid"],
                "wert": str(r["wert"]),
                "moegliche_ziele": treffer[:5],
                "grund": ("mehrdeutig — der Wert passt rechnerisch zu "
                          f"{len(treffer)} IDs (Ueberlauf)"
                          if len(treffer) > 1 else
                          "kein passendes Ziel gefunden"),
            })
    return {"geheilt": geheilt, "geleert": geleert, "nicht_rekonstruierbar": unklar}


def _spalte_auf_text(conn, tabelle: str, spalte: str) -> bool:
    """Aendert die Spalten-Affinitaet auf TEXT.

    SQLite kann kein ALTER COLUMN — die Tabelle wird neu gebaut. Ab
    SQLite 3.25 laesst sich das mit einem Trick abkuerzen: das Schema in
    `sqlite_master` direkt umschreiben. Das ist heikel, aber gegenueber
    dem vollstaendigen Neuaufbau (mit allen Indizes, Triggern und
    Fremdschluesseln) deutlich risikoaermer — die Daten bleiben, wo sie
    sind, nur die Typangabe aendert sich.
    """
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (tabelle,)).fetchone()
    if not row or not row["sql"]:
        return False
    sql = row["sql"]
    import re
    # "<spalte> INTEGER" -> "<spalte> TEXT" (nur die Typangabe, Rest bleibt)
    muster = re.compile(
        rf"(\b{re.escape(spalte)}\s+)(INTEGER|REAL|NUMERIC|INT)\b",
        re.IGNORECASE)
    neu_sql, n = muster.subn(r"\1TEXT", sql, count=1)
    if not n:
        return False
    conn.execute("PRAGMA writable_schema=ON")
    try:
        conn.execute(
            "UPDATE sqlite_master SET sql=? WHERE type='table' AND name=?",
            (neu_sql, tabelle))
        # Schema-Version hochzaehlen: damit liest JEDE Connection das
        # geaenderte Schema bei der naechsten Anweisung neu ein. Das ist der
        # dokumentierte Weg — ein `close()` waere hier gefaehrlich, weil
        # Hintergrund-Threads (Jobsuche, Automatik) dieselbe Connection
        # benutzen und ein Schliessen unter ihnen weg zum Absturz fuehrt.
        version = conn.execute("PRAGMA schema_version").fetchone()[0]
        conn.execute(f"PRAGMA schema_version={int(version) + 1}")
    finally:
        conn.execute("PRAGMA writable_schema=OFF")
    return True


def heilen(db: Any, dry_run: bool = True) -> dict:
    """Affinitaet korrigieren und verunglueckte Werte zurueckuebersetzen.

    Idempotent: ein zweiter Lauf findet nichts mehr.
    """
    diagnose = pruefe(db)
    if not diagnose["handlungsbedarf"]:
        return {"status": "nichts_zu_tun", "befunde": diagnose["befunde"]}
    if dry_run:
        return {
            "status": "vorschau",
            "befunde": diagnose["befunde"],
            "hinweis": ("Mit dry_run=False werden die Spalten auf TEXT "
                        "gestellt und die Werte zurueckuebersetzt. "
                        "Nicht eindeutig aufloesbare Verknuepfungen werden "
                        "geleert statt falsch belassen."),
        }

    conn = db.connect()
    ergebnis = []
    schema_geaendert = False

    # REIHENFOLGE IST ENTSCHEIDEND: erst die Affinitaet korrigieren, dann
    # die Werte zurueckschreiben. Andersherum laeuft der korrigierte
    # Text-Wert direkt wieder in dieselbe Falle — SQLite wandelt ihn beim
    # UPDATE erneut in eine Zahl, und der Fremdschluessel bricht ab. Genau
    # dieser Fehler war der Ausloeser des Issues.
    for b in diagnose["befunde"]:
        if b["affinitaet_falsch"]:
            if _spalte_auf_text(conn, b["tabelle"], b["spalte"]):
                b["_typ_geaendert"] = True
                schema_geaendert = True
    if schema_geaendert:
        conn.commit()
        # KEIN db.close() hier: Hintergrund-Threads (Jobsuche, Automatik)
        # teilen sich diese Connection, und ein Schliessen unter ihnen weg
        # laesst SQLite auf C-Ebene abstuerzen (in der CI als Segfault
        # aufgetreten). Das Schema-Reload passiert stattdessen ueber den
        # schema_version-Bump in _spalte_auf_text. Die bereits
        # gespeicherten Zahlwerte bleiben physisch REAL — also weiterhin
        # lesbar und heilbar.
        pass

    # Waehrend der Heilung stehen kurzzeitig Werte, die auf nichts zeigen
    # (der inf-Fall wird geleert) — Fremdschluessel deshalb aussetzen und
    # danach explizit pruefen.
    conn.execute("PRAGMA foreign_keys=OFF")
    try:
        for b in diagnose["befunde"]:
            tabelle, spalte = b["tabelle"], b["spalte"]
            ziel = next(z for t, s, z in ID_SPALTEN
                        if t == tabelle and s == spalte)
            heilung = _rueckuebersetzen(conn, tabelle, spalte, ziel)
            ergebnis.append({
                "tabelle": tabelle, "spalte": spalte,
                "typ_auf_text_gesetzt": bool(b.get("_typ_geaendert")),
                **heilung})
        conn.commit()
    finally:
        conn.execute("PRAGMA foreign_keys=ON")

    if schema_geaendert:
        try:
            check = conn.execute("PRAGMA integrity_check").fetchone()[0]
            fk = conn.execute("PRAGMA foreign_key_check").fetchall()
        except Exception as e:
            check, fk = f"nicht pruefbar: {e}", []
        for e in ergebnis:
            e["integrity_check"] = check
            if fk:
                e["offene_fk_verletzungen"] = len(fk)
    return {"status": "ausgefuehrt", "ergebnis": ergebnis}
