"""Ein Statuswechsel mit Rueckweg (G67, #1087 D8).

Das Status-Auswahlfeld im Dashboard speichert sofort. Ein Fehlgriff auf
"abgelehnt" archivierte die Bewerbung, schloss ihre Nachfassungen und
liess keinen Weg zurueck — erneut den alten Status zu setzen haette ein
zweites Ereignis in die Timeline geschrieben und die geschlossenen
Nachfassungen nicht wiederbelebt.

`wechseln` merkt sich, was der Wechsel veraendert: den vorherigen Status,
das neue Ereignis, die dabei geschlossenen und neu angelegten
Nachfassungen. `zuruecknehmen` nimmt genau das zurueck und rechnet die
Interview-Markierung aus der verbliebenen Timeline neu.
"""
from __future__ import annotations

INTERVIEW_STUFEN = ("interview", "zweitgespraech", "interview_abgeschlossen",
                    "angebot", "angenommen")


def _offene_nachfassungen(db, app_id: str) -> set[str]:
    return {fu["id"] for fu in db.get_pending_follow_ups()
            if fu.get("application_id") == app_id}


def wechseln(db, app_id: str, neu: str, notizen: str = "",
             profile_id: str | None = None) -> dict | None:
    """Setzt den Status und liefert den Rueckweg — oder None."""
    app = db.get_application(app_id)
    if not app:
        return None
    vorher = app.get("status") or ""
    offen_vorher = _offene_nachfassungen(db, app_id)
    if not db.update_application_status(app_id, neu, notizen, profile_id=profile_id):
        return None
    zeile = db.connect().execute(
        "SELECT MAX(id) AS id FROM application_events WHERE application_id=? AND status=?",
        (app_id, neu)).fetchone()
    offen_nachher = _offene_nachfassungen(db, app_id)
    return {
        "vorher": vorher,
        "neu": neu,
        "event_id": zeile["id"] if zeile else None,
        "geschlossen": sorted(offen_vorher - offen_nachher),
        "angelegt": sorted(offen_nachher - offen_vorher),
        "archiviert": neu in db.ARCHIVE_STATUSES and vorher not in db.ARCHIVE_STATUSES,
    }


def zuruecknehmen(db, app_id: str, rueckweg: dict,
                  profile_id: str | None = None) -> bool:
    """Nimmt einen Wechsel zurueck, den `wechseln` beschrieben hat."""
    vorher = str(rueckweg.get("vorher") or "")
    if not vorher:
        return False
    conn = db.connect()
    params: list = [vorher, app_id]
    sql = "UPDATE applications SET status=? WHERE id=?"
    if profile_id is not None:
        sql += " AND (profile_id=? OR profile_id IS NULL)"
        params.append(profile_id)
    if conn.execute(sql, params).rowcount == 0:
        return False
    if rueckweg.get("event_id"):
        conn.execute("DELETE FROM application_events WHERE id=? AND application_id=?",
                     (rueckweg["event_id"], app_id))
    for fid in rueckweg.get("geschlossen") or []:
        conn.execute("UPDATE follow_ups SET status='geplant', completed_at=NULL "
                     "WHERE id=? AND application_id=?", (fid, app_id))
    for fid in rueckweg.get("angelegt") or []:
        conn.execute("DELETE FROM follow_ups WHERE id=? AND application_id=?",
                     (fid, app_id))
    platz = ",".join("?" * len(INTERVIEW_STUFEN))
    hatte = conn.execute(
        f"SELECT 1 FROM application_events WHERE application_id=? AND status IN ({platz}) LIMIT 1",
        (app_id, *INTERVIEW_STUFEN)).fetchone()
    conn.execute("UPDATE applications SET has_reached_interview=? WHERE id=?",
                 (1 if hatte else 0, app_id))
    conn.commit()
    return True
