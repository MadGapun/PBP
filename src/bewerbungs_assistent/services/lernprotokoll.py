"""Lernprotokoll: jeder Lernlauf hinterlaesst einen Eintrag (#792).

Der Lern-Task lief taeglich, und sein sichtbares Ergebnis war oft null.
Von aussen waren drei Lagen nicht zu unterscheiden: ausgewertet, aber
nichts Belegbares; abgeleitet, aber nicht gespeichert; oder etwas ganz
anderes. Ein Eintrag je Lauf haelt fest, was angeschaut wurde (Quellen
mit Zahl), was herauskam (Kandidaten, neu, schon bekannt, verworfen), wie
lange es dauerte, ob die lokale KI beteiligt war — und warum nichts kam.

Ein Weg fuer beide Ausloeser: die Automatik (und ihr Knopf "Jetzt
lernen") und `erkenntnisse_ableiten(dry_run=False)` rufen `regeln_lauf`.
Eine Vorschau (`dry_run=True`) speichert nichts und steht nicht im
Protokoll — sie ist kein Lauf, sondern ein Blick.

Abgrenzung: `background_jobs` zeigt, dass gerade etwas laeuft; dieses
Protokoll bleibt und ist nach Profil getrennt.
"""
from __future__ import annotations

import csv
import io
import json
import time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

#: Wie viele Laeufe je Profil stehen bleiben — genug fuer ein halbes
#: Jahr taeglicher Laeufe, ohne dass die Tabelle unbegrenzt waechst.
MAX_EINTRAEGE = 200


def tabelle_anlegen(conn) -> None:
    """Safety-Net statt Schema-Bump (additiv, wie `job_tombstones`)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS learning_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT,
            gestartet_am TEXT NOT NULL,
            dauer_ms INTEGER DEFAULT 0,
            ausloeser TEXT DEFAULT '',
            status TEXT DEFAULT '',
            quellen_json TEXT DEFAULT '[]',
            kandidaten_json TEXT DEFAULT '[]',
            neu INTEGER DEFAULT 0,
            aufgefrischt INTEGER DEFAULT 0,
            verworfen INTEGER DEFAULT 0,
            regeln_json TEXT DEFAULT '{}',
            lokale_ki_json TEXT DEFAULT '{}',
            fehler TEXT DEFAULT ''
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_learning_runs_profil "
                 "ON learning_runs(profile_id, gestartet_am)")


def _jetzt() -> str:
    return datetime.now().isoformat(timespec="seconds")


def regeln_lauf(db: Any, ausloeser: str, budget_sekunden: int = 20) -> dict:
    """Die regelbasierte Stufe: ableiten, speichern, protokollieren.

    Haelt den Datenschutz-Schalter ein (#1107): ist das Lernen aus, wird
    nichts abgeleitet und nichts gespeichert — und das steht im Protokoll,
    damit ein leerer Tag nicht wie ein Fehler aussieht."""
    from .lerninsights import kandidaten_ableiten, speichern
    from .lernquellen import uebersicht
    from .. import __version__ as _v
    tabelle_anlegen(db.connect())
    start = time.time()
    eintrag: dict = {"ausloeser": ausloeser, "gestartet_am": _jetzt(),
                     "quellen": [], "kandidaten": []}
    if not db.is_learning_enabled():
        eintrag["status"] = "lernen_aus"
        eintrag["id"] = _schreiben(db, eintrag, start)
        return eintrag
    try:
        eintrag["quellen"] = [
            {k: q.get(k) for k in ("key", "name", "anzahl", "von", "bis")}
            for q in uebersicht(db) if q["fliesst_ein"]]
    except Exception as exc:  # die Zaehlung darf den Lauf nicht kippen
        eintrag["quellen_fehler"] = str(exc)
    lauf = kandidaten_ableiten(db, budget_sekunden=budget_sekunden)
    eintrag.update({k: lauf[k] for k in ("regeln_gelaufen", "regeln_mit_ergebnis",
                                         "regeln_uebersprungen", "regel_fehler")})
    eintrag["kandidaten"] = lauf["kandidaten"]
    gespeichert = speichern(db, lauf["kandidaten"], app_version=_v) \
        if lauf["kandidaten"] else {"neu": 0, "aufgefrischt": 0,
                                    "uebersprungen_widersprochen": 0}
    eintrag["neu"] = gespeichert["neu"]
    eintrag["aufgefrischt"] = gespeichert["aufgefrischt"]
    eintrag["verworfen"] = gespeichert["uebersprungen_widersprochen"]
    eintrag["gespeichert"] = gespeichert
    eintrag["status"] = "teilweise" if lauf["abgebrochen"] or lauf["regel_fehler"] \
        else "fertig"
    eintrag["id"] = _schreiben(db, eintrag, start)
    return eintrag


def _schreiben(db: Any, e: dict, start: float) -> int:
    conn = db.connect()
    pid = db.get_active_profile_id() or ""
    kandidaten = [{"kind": k.get("kind"), "scope": k.get("scope"),
                   "aussage": k.get("aussage"), "belegt_durch_n": k.get("belegt_durch_n"),
                   "konfidenz": k.get("konfidenz")} for k in e.get("kandidaten") or []]
    regeln = {k: e.get(k) for k in ("regeln_gelaufen", "regeln_mit_ergebnis",
                                    "regeln_uebersprungen", "regel_fehler")
              if e.get(k) is not None}
    cur = conn.execute(
        "INSERT INTO learning_runs (profile_id, gestartet_am, dauer_ms, ausloeser, "
        "status, quellen_json, kandidaten_json, neu, aufgefrischt, verworfen, "
        "regeln_json, fehler) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (pid, e["gestartet_am"], int((time.time() - start) * 1000), e["ausloeser"],
         e.get("status", ""), json.dumps(e.get("quellen") or [], ensure_ascii=False),
         json.dumps(kandidaten, ensure_ascii=False), e.get("neu", 0),
         e.get("aufgefrischt", 0), e.get("verworfen", 0),
         json.dumps(regeln, ensure_ascii=False), e.get("fehler", "")))
    conn.execute(
        "DELETE FROM learning_runs WHERE profile_id=? AND id NOT IN ("
        "SELECT id FROM learning_runs WHERE profile_id=? "
        "ORDER BY id DESC LIMIT ?)", (pid, pid, MAX_EINTRAEGE))
    conn.commit()
    return cur.lastrowid


def ki_nachtragen(db: Any, lauf_id: int, ergebnis: dict) -> None:
    """Die Muster-Analyse der lokalen KI laeuft nach den Regeln; ihr
    Ergebnis kommt an denselben Eintrag."""
    ki = {"uebersprungen": bool(ergebnis.get("skipped")),
          "grund": ergebnis.get("reason") or "",
          "erkenntnisse": ergebnis.get("insights", 0),
          "ereignisse": ergebnis.get("events_analysed")}
    conn = db.connect()
    conn.execute("UPDATE learning_runs SET lokale_ki_json=? WHERE id=? AND profile_id=?",
                 (json.dumps(ki, ensure_ascii=False), lauf_id,
                  db.get_active_profile_id() or ""))
    conn.commit()


def _zeile(r) -> dict:
    from .lernquellen import warum_leer
    e = dict(r)
    for feld, leer in (("quellen_json", []), ("kandidaten_json", []),
                       ("regeln_json", {}), ("lokale_ki_json", {})):
        try:
            e[feld[:-5]] = json.loads(e.pop(feld) or "null") or leer
        except (TypeError, ValueError):
            e[feld[:-5]] = leer
    e.update(e.pop("regeln"))
    if not e.get("neu"):
        e["warum_nichts_neues"] = warum_leer(e)
    return e


def anzeigen(db: Any, limit: int = 20) -> list[dict]:
    """Die letzten Laeufe des aktiven Profils, neueste zuerst."""
    conn = db.connect()
    tabelle_anlegen(conn)
    rows = conn.execute(
        "SELECT * FROM learning_runs WHERE profile_id=? ORDER BY id DESC LIMIT ?",
        (db.get_active_profile_id() or "", max(1, min(int(limit or 20), MAX_EINTRAEGE)))
    ).fetchall()
    return [_zeile(r) for r in rows]


# ------------------------------------------------------------- Export

def _csv(zeilen: list[dict], spalten: list[str]) -> str:
    puffer = io.StringIO()
    w = csv.DictWriter(puffer, fieldnames=spalten, extrasaction="ignore",
                       delimiter=";")
    w.writeheader()
    for z in zeilen:
        w.writerow({k: z.get(k, "") for k in spalten})
    return "﻿" + puffer.getvalue()  # BOM: Excel liest Umlaute richtig


def _uebersicht_md(quellen: list[dict], stand: str) -> str:
    zeilen = [f"# Was PBP über dich lernt — Stand {stand}", "",
              "Dieser Export enthält genau die Daten, die das Lernen auswertet, "
              "dazu die abgeleiteten Erkenntnisse und das Protokoll der Läufe.", "",
              "**Achtung:** Er enthält Firmennamen aus deinen Bewerbungen und "
              "aussortierten Stellen. Gib ihn nicht unbedacht weiter.", "",
              "| Quelle | Tabellen | fließt ein | Datensätze | Zeitraum | wofür |",
              "|---|---|---|---|---|---|"]
    for q in quellen:
        zeitraum = f"{q.get('von') or '?'} bis {q.get('bis') or '?'}" \
            if q["fliesst_ein"] else ""
        zeilen.append("| {} | {} | {} | {} | {} | {} |".format(
            q["name"], ", ".join(q["tabellen"]), "ja" if q["fliesst_ein"] else "nein",
            q.get("anzahl", "") if q["fliesst_ein"] else "", zeitraum, q["wofuer"]))
    zeilen += ["", "Die Nutzung des Dashboards wertet nur die lokale KI aus "
               "(Muster in der Bedienung) — ohne eingeschaltete lokale KI "
               "fließt sie nicht ein.", ""]
    return "\n".join(zeilen)


def export_erstellen(db: Any, ziel: Path | None = None) -> dict:
    """ZIP mit CSV (Rohdaten), JSON (Erkenntnisse) und Markdown (Übersicht).

    Der Umfang ist deckungsgleich mit dem, was `lerninsights` liest: die
    Felder je Quelle aus `lernquellen.QUELLEN`, dieselben Filter."""
    from .lernquellen import uebersicht, FENSTER_AKTIVITAET_TAGE
    conn = db.connect()
    pid = db.get_active_profile_id() or ""
    stand = datetime.now().strftime("%Y-%m-%d")
    quellen = uebersicht(db)
    wo_profil = "(profile_id=? OR profile_id IS NULL)"
    aussortiert = [dict(r) for r in conn.execute(
        f"SELECT title, company, score, dismiss_reason, dismissed_at FROM jobs "
        f"WHERE is_active=0 AND {wo_profil} AND COALESCE(dismiss_reason,'') "
        f"NOT IN ('', 'bewerbung_erstellt') ORDER BY dismissed_at", (pid,))]
    bewerbungen = [dict(r) for r in conn.execute(
        f"SELECT id, title, company, status, applied_at, source, portal_name, "
        f"bewerbungsart, vermittler FROM applications WHERE {wo_profil} "
        f"ORDER BY applied_at", (pid,))]
    verlauf = [dict(r) for r in conn.execute(
        f"SELECT application_id, status, event_date FROM application_events "
        f"WHERE application_id IN (SELECT id FROM applications WHERE {wo_profil}) "
        f"ORDER BY event_date", (pid,))]
    aktivitaet = [dict(r) for r in conn.execute(
        f"SELECT page, action, event_type, timestamp FROM user_activity_events "
        f"WHERE (profile_id=? OR profile_id IS NULL OR profile_id='') "
        f"AND timestamp >= datetime('now', '-{FENSTER_AKTIVITAET_TAGE} days') "
        f"ORDER BY timestamp", (pid,))]
    erkenntnisse = []
    for r in conn.execute(
            "SELECT kind, scope, title, details_json, score, observed_count, "
            "last_seen_at, COALESCE(bestaetigt_vom_user, 0) AS bvu "
            "FROM learning_insights WHERE (profile_id=? OR profile_id='' "
            "OR profile_id IS NULL) AND is_active=1 ORDER BY score DESC", (pid,)):
        try:
            details = json.loads(r["details_json"] or "{}")
        except (TypeError, ValueError):
            details = {}
        erkenntnisse.append({
            "aussage": r["title"], "art": r["kind"], "bereich": r["scope"],
            "konfidenz": r["score"], "belegt_durch_n": details.get("belegt_durch_n"),
            "evidenz": details.get("evidenz") or details,
            "status": {1: "bestaetigt", -1: "widersprochen"}.get(r["bvu"], "offen"),
            "zuletzt_gesehen": r["last_seen_at"]})
    laeufe = anzeigen(db, limit=MAX_EINTRAEGE)

    if ziel is None:
        from .ablage import ausgabe_ordner
        ziel = ausgabe_ordner(db)
    ziel = Path(ziel)
    ziel.mkdir(parents=True, exist_ok=True)
    datei = ziel / f"lerndaten_{stand}.zip"
    n = 2
    while datei.exists():  # kein Export ueberschreibt einen anderen (#1101)
        datei = ziel / f"lerndaten_{stand}_{n}.zip"
        n += 1
    ordner = f"lerndaten_{stand}"
    with zipfile.ZipFile(datei, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(f"{ordner}/uebersicht.md", _uebersicht_md(quellen, stand))
        z.writestr(f"{ordner}/quellen/aussortierungen.csv", _csv(
            aussortiert, ["title", "company", "score", "dismiss_reason", "dismissed_at"]))
        z.writestr(f"{ordner}/quellen/bewerbungen.csv", _csv(
            bewerbungen, ["id", "title", "company", "status", "applied_at", "source",
                          "portal_name", "bewerbungsart", "vermittler"]))
        z.writestr(f"{ordner}/quellen/bewerbungs_verlauf.csv", _csv(
            verlauf, ["application_id", "status", "event_date"]))
        z.writestr(f"{ordner}/quellen/nutzung_letzte_{FENSTER_AKTIVITAET_TAGE}_tage.csv",
                   _csv(aktivitaet, ["timestamp", "page", "action", "event_type"]))
        z.writestr(f"{ordner}/erkenntnisse.json",
                   json.dumps(erkenntnisse, ensure_ascii=False, indent=2))
        z.writestr(f"{ordner}/lernlaeufe.csv", _csv(
            [{**l, "warum_nichts_neues": " | ".join(l.get("warum_nichts_neues") or []),
              "kandidaten": len(l.get("kandidaten") or [])} for l in laeufe],
            ["gestartet_am", "ausloeser", "status", "dauer_ms", "kandidaten", "neu",
             "aufgefrischt", "verworfen", "warum_nichts_neues"]))
    return {"datei": str(datei), "zeilen": {
        "aussortierungen": len(aussortiert), "bewerbungen": len(bewerbungen),
        "bewerbungs_verlauf": len(verlauf), "nutzung": len(aktivitaet),
        "erkenntnisse": len(erkenntnisse), "laeufe": len(laeufe)}}
