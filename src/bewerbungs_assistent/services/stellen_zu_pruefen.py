"""Was wartet in der Stellenliste auf das Urteil des Menschen? (#1187 Stufe 3)

Nach einem Browserlauf ist der naechste Schritt nicht im Chat, sondern in PBP: die neuen Stellen nacheinander ansehen und
abarbeiten. Dieser Dienst beantwortet die zwei Fragen, die das Dashboard dazu stellt:

* **Wie viele Stellen sind noch ungeprueft?** Dieselbe Regel wie der Filter "Pruefstand: nur ungepruefte" der Liste
  (`passung.zustand`, #948): weder ein gespeichertes Urteil noch ein "angesehen". Eine Stelle mit laufender Bewerbung und
  eine Stelle einer Firma auf der Blacklist zaehlen nicht mit - die Liste blendet beide aus, und die Zahl auf der Karte
  muss die Zeilen nach dem Sprung treffen. `neu` ist die Teilmenge der letzten Tage - was der Lauf gerade gebracht hat.
* **Was hat Claude nach dem Lesen aussortiert?** (`dismissed_by = 'claude'`, Herkunft "von Claude"). Sie liegen in
  "Ausgeblendet" und lassen sich zurueckholen; die Karte nennt die Zahl UND die neuesten Eintraege samt Grund, damit der
  Rueckweg dort ist, wo man hinschaut (Regel "im Zweifel eintragen": aussortiert wird nur, was offensichtlich fachfremd oder
  geschlossen ist - und der Mensch entscheidet, ob das stimmt).

Abgrenzung: `stellen_liste` filtert und sortiert die Liste selbst; hier steht nur die Zaehlung fuer die Karte. Beide
benutzen dieselbe Definition von "ungeprueft" aus `passung`, damit die Zahl auf der Karte und die Zeilen nach dem Sprung
dieselben sind - ein Test haelt das gegeneinander.

Gelesen wird mit je einem SELECT ueber `jobs` und `applications`, nicht ueber `get_applications()`: das liest je Bewerbung
Verlauf, Notiz und Dokumente nach (#1143), und die Karte steht auf der Startseite.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

TAGE_NEU = 14
#: Wie viele von Claude aussortierte Stellen die Karte einzeln nennt; die Zahl daneben ist die volle.
MAX_LISTE = 20


def _beworbene(db, conn, pid) -> set:
    """Oeffentliche Hashes der Stellen mit laufender Bewerbung - dieselbe Menge wie `GET /api/jobs` sie ausblendet."""
    archiv = tuple(getattr(db, "ARCHIVE_STATUSES", ()) or ())
    sql = ("SELECT job_hash, profile_id FROM applications WHERE job_hash IS NOT NULL AND job_hash != '' "
           "AND (profile_id=? OR profile_id IS NULL)")
    params: list = [pid]
    if archiv:
        sql += f" AND (status IS NULL OR status NOT IN ({','.join('?' for _ in archiv)}))"
        params.extend(archiv)
    return {db._public_job_hash(r["job_hash"], r["profile_id"]) for r in conn.execute(sql, params)}


def _gruende(roh) -> list:
    """`dismiss_reason` steht als Klartext oder als JSON-Liste (#574)."""
    text = str(roh or "").strip()
    if text.startswith("["):
        try:
            teile = json.loads(text)
            if isinstance(teile, list):
                return [str(t) for t in teile if str(t).strip()]
        except ValueError:
            pass
    return [text] if text else []


def uebersicht(db, tage: int = TAGE_NEU) -> dict:
    pid = db.get_active_profile_id()
    conn = db.connect()
    try:
        beworbene = _beworbene(db, conn, pid)
    except Exception:  # noqa: BLE001 - die Karte darf nie die Seite kippen
        beworbene = set()
    try:
        sperren = db.get_blacklist() or []
    except Exception:  # noqa: BLE001
        sperren = []
    if sperren:
        from . import blacklist_regel
    tag_grenze = (datetime.now(timezone.utc) - timedelta(days=max(1, int(tage)))).date().isoformat()

    ungeprueft = neu = 0
    for z in conn.execute(
            "SELECT hash, profile_id, title, company, analyse_urteil, gesichtet_am, found_at FROM jobs "
            "WHERE is_active=1 AND (profile_id=? OR profile_id IS NULL)", (pid,)):
        if (z["analyse_urteil"] or "").strip() or (z["gesichtet_am"] or "").strip():
            continue
        if db._public_job_hash(z["hash"], z["profile_id"]) in beworbene:
            continue
        if sperren and blacklist_regel.treffer(sperren, z["company"] or "", z["title"] or ""):
            continue
        ungeprueft += 1
        if str(z["found_at"] or "")[:10] >= tag_grenze:
            neu += 1

    zeilen = conn.execute(
        "SELECT hash, profile_id, title, company, dismiss_reason, dismissed_at FROM jobs "
        "WHERE is_active=0 AND dismissed_by='claude' AND (profile_id=? OR profile_id IS NULL) "
        "ORDER BY COALESCE(dismissed_at, '') DESC, updated_at DESC", (pid,)).fetchall()
    aussortiert = []
    for z in zeilen[:MAX_LISTE]:
        gruende = _gruende(z["dismiss_reason"])
        aussortiert.append({
            "hash": db._public_job_hash(z["hash"], z["profile_id"]),
            "titel": z["title"] or "",
            "firma": z["company"] or "",
            "grund": gruende[0] if gruende else "",
            "gruende": gruende,
            "am": str(z["dismissed_at"] or "")[:10],
        })
    return {"ungeprueft": ungeprueft, "neu": neu, "tage": int(tage),
            "von_claude_aussortiert": len(zeilen), "aussortiert": aussortiert}
