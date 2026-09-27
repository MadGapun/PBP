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

Seit #1094 laeuft der Wechsel durch `bewerbung_lebenszyklus` — er setzt
auch das Bewerbungsdatum, sortiert die Stelle aus und laesst Dokumente
veralten. Der Rueckweg nimmt diese drei Dinge ebenfalls zurueck.
"""
from __future__ import annotations

INTERVIEW_STUFEN = ("interview", "zweitgespraech", "interview_abgeschlossen",
                    "angebot", "angenommen")


def wechseln(db, app_id: str, neu: str, notizen: str = "",
             profile_id: str | None = None) -> dict:
    """Setzt den Status ueber den Lebenszyklus-Dienst (#1094) und liefert
    den Rueckweg. Bei `ok=False` steht der Grund in `fehler`."""
    from . import bewerbung_lebenszyklus
    return bewerbung_lebenszyklus.status_wechseln(
        db, app_id, neu, notizen, profile_id=profile_id)


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
    # #1094: was der Wechsel sonst noch angelegt hat
    if rueckweg.get("applied_at_vorher") is not None:
        conn.execute("UPDATE applications SET applied_at=? WHERE id=?",
                     (rueckweg["applied_at_vorher"] or None, app_id))
    for doc in rueckweg.get("dokumente_veraltet") or []:
        if isinstance(doc, dict) and doc.get("id"):
            conn.execute("UPDATE documents SET lifecycle=? WHERE id=? AND lifecycle='veraltet'",
                         (doc.get("vorher") or "aktiv", doc["id"]))
    platz = ",".join("?" * len(INTERVIEW_STUFEN))
    hatte = conn.execute(
        f"SELECT 1 FROM application_events WHERE application_id=? AND status IN ({platz}) LIMIT 1",
        (app_id, *INTERVIEW_STUFEN)).fetchone()
    conn.execute("UPDATE applications SET has_reached_interview=? WHERE id=?",
                 (1 if hatte else 0, app_id))
    conn.commit()
    if rueckweg.get("stelle_aussortiert"):
        db.restore_job(str(rueckweg["stelle_aussortiert"]))
    return True
