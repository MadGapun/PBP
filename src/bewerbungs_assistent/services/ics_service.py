"""iCalendar-Export der Bewerbungstermine — J4.1 (#481, v1.8.0-beta.3).

Die Basis (Export aller geplanten Termine als .ics) existiert seit #310 im
Dashboard-Endpoint. Hier lebt seit beta.3 der gemeinsame, RFC-5545-feste
Kern fuer REST-Endpoint UND MCP-Tool:

  - **Escaping** von Komma/Semikolon/Backslash/Zeilenumbruechen in
    SUMMARY/LOCATION/DESCRIPTION — vorher zerbrach ein Titel wie
    "Interview, 2. Runde" oder eine mehrzeilige Notiz die Datei.
  - **Line-Folding** bei 75 Oktetten (RFC 5545 3.1) — Outlook/Apple
    Kalender lehnen ueberlange Zeilen sonst teils ab.

Zeiten werden als lokale "floating time" geschrieben (ohne TZID) — der
importierende Kalender interpretiert sie in seiner lokalen Zeitzone, was
fuer lokal erfasste Bewerbungstermine das erwartete Verhalten ist.
"""
from __future__ import annotations

from datetime import datetime


def ics_escape(text) -> str:
    """RFC-5545-Escaping fuer TEXT-Werte (3.3.11)."""
    s = str(text or "")
    s = s.replace("\\", "\\\\")
    s = s.replace(";", "\\;").replace(",", "\\,")
    s = s.replace("\r\n", "\\n").replace("\n", "\\n").replace("\r", "\\n")
    return s


def ics_fold(line: str) -> str:
    """Line-Folding bei 75 Oktetten (Fortsetzungszeilen mit Leerzeichen).

    Oktett-genau (UTF-8), ohne Multibyte-Zeichen zu zerschneiden.
    """
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts: list[str] = []
    current = b""
    limit = 75
    for ch in line:
        b = ch.encode("utf-8")
        if len(current) + len(b) > limit:
            parts.append(current.decode("utf-8"))
            current = b" " + b  # Fortsetzungszeile beginnt mit Space
            limit = 75
        else:
            current += b
    if current:
        parts.append(current.decode("utf-8"))
    return "\r\n".join(parts)


def _fmt_dt(iso_str) -> str | None:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(str(iso_str)).strftime("%Y%m%dT%H%M%S")
    except (ValueError, TypeError):
        return None


def build_meetings_ics(db) -> tuple[str, int]:
    """Baut den VCALENDAR aller GEPLANTEN Termine des aktiven Profils.

    Returns:
        (ics_content, anzahl_events)
    """
    conn = db.connect()
    pid = db.get_active_profile_id()
    rows = conn.execute(
        """SELECT m.*, a.title as app_title, a.company as app_company, a.id as app_id
           FROM application_meetings m
           LEFT JOIN applications a ON m.application_id = a.id
           WHERE m.status='geplant'
             AND (m.profile_id=? OR m.profile_id IS NULL)
           ORDER BY m.meeting_date ASC""",
        (pid,),
    ).fetchall()

    now_stamp = datetime.now().strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PBP Bewerbungs-Assistent//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:PBP Bewerbungstermine",
    ]

    count = 0
    for r in rows:
        m = dict(r)
        dt_start = _fmt_dt(m.get("meeting_date"))
        if not dt_start:
            continue
        dt_end = _fmt_dt(m.get("meeting_end")) or dt_start
        title = m.get("title", "Termin") or "Termin"
        company = m.get("app_company", "") or ""
        app_title = m.get("app_title", "") or ""
        app_id = m.get("app_id", "") or ""
        location = m.get("location", "") or ""
        meeting_url = m.get("meeting_url", "") or ""
        notes = m.get("notes", "") or ""

        desc_parts = []
        if company and app_title:
            desc_parts.append(f"Bewerbung: {app_title} bei {company}")
        if app_id:
            desc_parts.append(f"PBP-Link: http://localhost:8200/bewerbungen?id={app_id}")
        if meeting_url:
            desc_parts.append(f"Meeting-Link: {meeting_url}")
        if notes:
            desc_parts.append(f"Notizen: {notes}")

        summary = title + (f" — {company}" if company else "")
        lines.append("BEGIN:VEVENT")
        lines.append(f"UID:{m['id']}@pbp.local")
        lines.append(f"DTSTAMP:{now_stamp}")
        lines.append(f"DTSTART:{dt_start}")
        lines.append(f"DTEND:{dt_end}")
        lines.append("SUMMARY:" + ics_escape(summary))
        lines.append("DESCRIPTION:" + ics_escape("\n".join(desc_parts)))
        if location:
            lines.append("LOCATION:" + ics_escape(location))
        if meeting_url:
            # URL ist kein TEXT-Typ — nicht escapen, nur uebernehmen
            lines.append(f"URL:{meeting_url}")
        lines.append("END:VEVENT")
        count += 1

    lines.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(line) for line in lines) + "\r\n", count
