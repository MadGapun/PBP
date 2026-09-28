"""iCalendar-Export der Bewerbungstermine — J4.1 (#481, v1.8.0-beta.3).

Die Basis (Export aller geplanten Termine als .ics) existiert seit #310 im
Dashboard-Endpoint. Hier lebt seit beta.3 der gemeinsame, RFC-5545-feste
Kern fuer REST-Endpoint UND MCP-Tool (auf der 1.7-Linie seit v1.7.140
mit #1102, dort nur fuer die beiden Dashboard-Exporte):

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

from .dashboard_link import dashboard_link


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
    """Wert fuer DTSTART/DTEND ohne Eigenschaftsnamen.

    #1102: eine Zeit MIT Zone wird als UTC (`...Z`) geschrieben — ohne
    Zone liest der Kalender sie als Ortszeit, und eine Einladung fuer
    12:00 UTC stand bei 12:00 statt 14:00. Ohne Zone bleibt es Ortszeit;
    so speichert PBP seit #1102 alle Termine."""
    if not iso_str:
        return None
    try:
        dt = datetime.fromisoformat(str(iso_str).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    if dt.tzinfo is not None:
        from datetime import timezone
        return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return dt.strftime("%Y%m%dT%H%M%S")


def _zeitzeilen(start, ende) -> list | None:
    """DTSTART/DTEND; ein reines Datum ist ein ganztaegiger Termin."""
    from datetime import date, timedelta
    text = str(start or "").strip()
    if len(text) == 10:
        try:
            tag = date.fromisoformat(text)
        except ValueError:
            return None
        return [f"DTSTART;VALUE=DATE:{tag.strftime('%Y%m%d')}",
                f"DTEND;VALUE=DATE:{(tag + timedelta(days=1)).strftime('%Y%m%d')}"]
    dt_start = _fmt_dt(start)
    if not dt_start:
        return None
    return [f"DTSTART:{dt_start}", f"DTEND:{_fmt_dt(ende) or dt_start}"]


def _vevent(m: dict, now_stamp: str) -> list | None:
    """Die Zeilen eines Termins — fuer Gesamt- UND Einzelexport (#1102)."""
    zeiten = _zeitzeilen(m.get("meeting_date"), m.get("meeting_end"))
    if not zeiten:
        return None
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
        desc_parts.append(f"PBP-Link: {dashboard_link('bewerbungen', app_id)}")
    if meeting_url:
        desc_parts.append(f"Meeting-Link: {meeting_url}")
    if notes:
        desc_parts.append(f"Notizen: {notes}")

    summary = title + (f" — {company}" if company else "")
    zeilen = ["BEGIN:VEVENT", f"UID:{m['id']}@pbp.local", f"DTSTAMP:{now_stamp}",
              *zeiten,
              "SUMMARY:" + ics_escape(summary),
              "DESCRIPTION:" + ics_escape("\n".join(desc_parts))]
    if location:
        zeilen.append("LOCATION:" + ics_escape(location))
    if meeting_url:
        # URL ist kein TEXT-Typ — nicht escapen, nur uebernehmen
        zeilen.append(f"URL:{meeting_url}")
    zeilen.append("END:VEVENT")
    return zeilen


def _kalender(ereignisse: list, name: str = "") -> str:
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0",
             "PRODID:-//PBP Bewerbungs-Assistent//DE",
             "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    if name:
        lines.append(f"X-WR-CALNAME:{name}")
    for e in ereignisse:
        lines.extend(e)
    lines.append("END:VCALENDAR")
    return "\r\n".join(ics_fold(line) for line in lines) + "\r\n"


def build_meeting_ics(meeting: dict) -> str | None:
    """Ein einzelner Termin als Kalenderdatei. None bei unlesbarer Zeit."""
    from datetime import timezone
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    e = _vevent(dict(meeting), now_stamp)
    return _kalender([e]) if e else None


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

    from datetime import timezone
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    ereignisse = [e for e in (_vevent(dict(r), now_stamp) for r in rows) if e]
    return _kalender(ereignisse, "PBP Bewerbungstermine"), len(ereignisse)
