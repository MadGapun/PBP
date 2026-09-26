"""Stellen einer Quelle endgueltig entfernen (#1075).

Wer eine Quelle abwaehlt, will ihre Treffer meist auch nicht mehr im
Bestand haben. Es gab dafuer nur zwei Wege, und beide passten nicht:
Aussortieren laesst die Zeile stehen (sie zaehlt weiter in den
Schwellen-Stufen aus #1063, in der Ablehnungs-Statistik und im
Quellen-Filter der Liste), und `daten_bereiche_leeren(['stellen'])` loescht
den ganzen Bestand. Beim Melder: 2.600 Stellen samt Historie, um 62
loszuwerden. Uebrig blieb der Griff in die Datenbank — und den macht
Claude zu Recht nicht (#514).

Geschuetzt bleibt, was mehr ist als ein Treffer dieser Quelle:

* eine Stelle mit **Bewerbung** (ueber `applications.job_hash` oder die
  Verknuepfung `application_jobs`, #764) — sie ist Teil einer Geschichte;
* eine Stelle, die eine **gewaehlte Quelle ebenfalls gefunden** hat
  (`job_sources`, #951) — sie kaeme sonst mit dem naechsten Lauf wieder.

Abgrenzung zu `loeschbereiche.py`: dort werden ganze BEREICHE geleert,
hier einzelne Stellen nach einem Filter. Die Kind-Tabellen kommen aber
auf dieselbe Weise zustande — aus dem Schema, nicht aus einer Liste —,
sonst bliebe die naechste neue Tabelle als Waise liegen (#1025).
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _kinder(db) -> list:
    """(Tabelle, Spalte) fuer alles, was ueber den Hash an `jobs` haengt."""
    conn = db.connect()
    aus = []
    for (tab,) in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%'").fetchall():
        if tab in ("jobs", "applications"):
            continue
        spalten = {r[1] for r in conn.execute(f"PRAGMA table_info({tab})")}
        verweise = set()
        for fk in conn.execute(f"PRAGMA foreign_key_list({tab})"):
            if fk[2] == "jobs":
                verweise.add(fk[3])
        if "job_hash" in spalten:
            verweise.add("job_hash")
        for sp in sorted(verweise):
            aus.append((tab, sp))
    return aus


def _formen(db, stored: str, pid: str) -> tuple:
    """Gespeicherte UND oeffentliche Form — Bewerbungen tragen beide
    (v1.7.56 MERKE 4)."""
    oeffentlich = db._public_job_hash(stored, pid) or stored
    return tuple({stored, oeffentlich})


def planen(db, quelle: str) -> dict:
    """Welche Stellen der Quelle gingen, welche bleiben und warum."""
    from . import search_service
    quelle = (quelle or "").strip().lower()
    conn = db.connect()
    pid = db.get_active_profile_id()
    gewaehlt = set(search_service.aktive_quellen(db) or [])
    zeilen = conn.execute(
        "SELECT hash, title, company, is_active FROM jobs "
        "WHERE LOWER(source)=? AND (profile_id=? OR profile_id IS NULL)",
        (quelle, pid)).fetchall()

    weg, bleibt = [], []
    for r in zeilen:
        formen = _formen(db, r["hash"], pid)
        platz = ",".join("?" * len(formen))
        bewerbung = conn.execute(
            f"SELECT 1 FROM applications WHERE job_hash IN ({platz}) LIMIT 1",
            formen).fetchone() or conn.execute(
            f"SELECT 1 FROM application_jobs WHERE job_hash IN ({platz}) LIMIT 1",
            formen).fetchone()
        if bewerbung:
            bleibt.append({"hash": r["hash"], "titel": r["title"],
                           "grund": "bewerbung"})
            continue
        andere = []
        try:
            andere = [x["source"] for x in conn.execute(
                f"SELECT DISTINCT source FROM job_sources WHERE job_hash IN "
                f"({platz}) AND LOWER(source) != ?", (*formen, quelle))]
        except Exception:  # pragma: no cover — Tabelle fehlt in Altbestaenden
            andere = []
        gewaehlte_andere = [s for s in andere if s in gewaehlt]
        if gewaehlte_andere:
            bleibt.append({"hash": r["hash"], "titel": r["title"],
                           "grund": "weitere_fundstelle",
                           "quellen": gewaehlte_andere})
            continue
        weg.append({"hash": r["hash"], "titel": r["title"],
                    "firma": r["company"], "aktiv": bool(r["is_active"])})
    return {
        "quelle": quelle,
        "quelle_ist_gewaehlt": quelle in gewaehlt,
        "gefunden": len(zeilen),
        "zu_entfernen": weg,
        "bleiben": bleibt,
    }


def entfernen(db, quelle: str, dry_run: bool = True) -> dict:
    """Entfernt die Stellen einer Quelle — oder zeigt nur, welche (Vorgabe)."""
    plan = planen(db, quelle)
    weg = plan["zu_entfernen"]
    ergebnis = {
        "status": "vorschau" if dry_run else "entfernt",
        "quelle": plan["quelle"],
        "gefunden": plan["gefunden"],
        "zu_entfernen": len(weg),
        "davon_aktiv": sum(1 for s in weg if s["aktiv"]),
        "davon_aussortiert": sum(1 for s in weg if not s["aktiv"]),
        "bleiben": len(plan["bleiben"]),
        "bleiben_gruende": {
            g: sum(1 for b in plan["bleiben"] if b["grund"] == g)
            for g in ("bewerbung", "weitere_fundstelle")},
        "beispiele": [s["titel"] for s in weg[:10]],
    }
    if plan["quelle_ist_gewaehlt"]:
        ergebnis["warnung"] = (
            f"'{plan['quelle']}' ist noch ausgewählt — der nächste Suchlauf "
            "bringt ihre Stellen zurück. Erst abwählen, dann entfernen.")
    if dry_run or not weg:
        if dry_run:
            ergebnis["hinweis"] = (
                "Vorschau, nichts gelöscht. Mit dry_run=False endgültig "
                "entfernen — aussortierte Stellen zählen danach auch nicht "
                "mehr in Statistik und Schwellen-Stufen.")
        return ergebnis

    conn = db.connect()
    pid = db.get_active_profile_id()
    kinder = _kinder(db)
    geloescht_bezuege: dict = {}
    try:
        _loeschen(conn, db, weg, pid, kinder, geloescht_bezuege)
    except Exception as exc:
        # Eine Transaktion: entweder alle oder keine.
        return {**ergebnis, "status": "fehler",
                "fehler": f"Nichts entfernt, die Transaktion scheiterte: {exc}"}
    ergebnis["geloeschte_bezuege"] = geloescht_bezuege
    logger.info("#1075: %d Stellen der Quelle %s entfernt (%s)",
                len(weg), plan["quelle"], geloescht_bezuege)
    return ergebnis


def _loeschen(conn, db, weg, pid, kinder, geloescht_bezuege) -> None:
    with conn:
        for s in weg:
            formen = _formen(db, s["hash"], pid)
            platz = ",".join("?" * len(formen))
            for tab, sp in kinder:
                cur = conn.execute(
                    f"DELETE FROM {tab} WHERE {sp} IN ({platz})", formen)
                if cur.rowcount:
                    geloescht_bezuege[tab] = (
                        geloescht_bezuege.get(tab, 0) + cur.rowcount)
            # Kontakt-Verknuepfungen sind polymorph (`target_kind`) und
            # haben keine `job_hash`-Spalte — die Schema-Suche findet sie
            # nicht. Der Kontakt selbst bleibt.
            cur = conn.execute(
                "DELETE FROM contact_links WHERE target_kind='job' "
                f"AND target_id IN ({platz})", formen)
            if cur.rowcount:
                geloescht_bezuege["contact_links"] = (
                    geloescht_bezuege.get("contact_links", 0) + cur.rowcount)
            conn.execute("DELETE FROM jobs WHERE hash=?", (s["hash"],))
