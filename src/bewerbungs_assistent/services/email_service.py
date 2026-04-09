"""Email parsing and processing service for Bewerbungs-Assistent.

Handles .msg and .eml file parsing, meeting extraction, status detection,
and auto-matching of emails to existing applications.
"""

import email
import email.utils
import email.header
import hashlib
import logging
import os
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("bewerbungs_assistent.email_service")

# ---------------------------------------------------------------------------
# Meeting link patterns
# ---------------------------------------------------------------------------
TEAMS_PATTERN = re.compile(r'https://teams\.microsoft\.com/l/meetup-join/[^\s<>"\')\]]+', re.I)
ZOOM_PATTERN = re.compile(r'https://[a-z0-9]*\.?zoom\.us/[jw]/[^\s<>"\')\]]+', re.I)
MEET_PATTERN = re.compile(r'https://meet\.google\.com/[a-z\-]+', re.I)
WEBEX_PATTERN = re.compile(r'https://[a-z0-9]*\.?webex\.com/[^\s<>"\')\]]+', re.I)

MEETING_LINK_PATTERNS = [
    (TEAMS_PATTERN, "teams"),
    (ZOOM_PATTERN, "zoom"),
    (MEET_PATTERN, "google_meet"),
    (WEBEX_PATTERN, "webex"),
]

# ---------------------------------------------------------------------------
# Status detection patterns (German + English)
# ---------------------------------------------------------------------------
STATUS_PATTERNS = {
    "eingangsbestaetigung": [
        "vielen dank für ihre bewerbung",
        "vielen dank für ihre bewerbung",
        "bewerbung erhalten",
        "eingangsbestätigung",
        "eingangsbestaetigung",
        "bestätigen den eingang",
        "bestaetigen den eingang",
        "thank you for your application",
        "application has been received",
        "wir haben ihre bewerbung erhalten",
        "ihre bewerbung ist bei uns eingegangen",
        # #362: Du-Anrede Varianten (z.B. TKMS/Lumesse TalentLink)
        "vielen dank für deine bewerbung",
        "herzlichen dank für deine bewerbung",
        "deine bewerbung ist bei uns eingegangen",
        "wir haben deine bewerbung erhalten",
        "deine bewerbung erhalten",
        "danke für deine bewerbung",
    ],
    "interview": [
        "einladen",
        "vorstellungsgespräch",
        "vorstellungsgespraech",
        "interview",
        "kennenlernen",
        "persönlich vorstellen",
        "persoenlich vorstellen",
        "telefonisch besprechen",
        "möchten sie gerne",
        "moechten sie gerne",
        "würden uns freuen sie",
        "wuerden uns freuen sie",
        "terminvorschlag",
        "gesprächstermin",
        "gespraechstermin",
        "invite you to",
        "schedule a call",
        "phone screen",
        # #362: Du-Anrede
        "möchten dich gerne",
        "moechten dich gerne",
        "würden uns freuen dich",
        "wuerden uns freuen dich",
        "dich kennenlernen",
        "laden dich ein",
    ],
    "abgelehnt": [
        "leider absagen",
        "leider mitteilen",
        "nicht weiter berücksichtigen",
        "nicht weiter beruecksichtigen",
        "anderen kandidaten",
        "absage",
        "leider müssen wir",
        "leider muessen wir",
        "unfortunately",
        "regret to inform",
        "not proceed",
        "position has been filled",
        "stelle wurde besetzt",
        "nicht mehr vakant",
        # #362: Du-Anrede
        "deine bewerbung leider",
        "dir leider absagen",
        "dir leider mitteilen",
        "dich leider nicht",
    ],
    "angebot": [
        "vertragsentwurf",
        "vertragsangebot",
        "konditionen",
        "freuen uns ihnen anbieten",
        "offer letter",
        "pleased to offer",
        "gehaltsvorschlag",
        "vertragsunterlagen",
        "rahmenvertrag",
        # #362: Du-Anrede
        "freuen uns dir anbieten",
        "dein vertragsangebot",
    ],
}

# ---------------------------------------------------------------------------
# German date patterns for meeting extraction from body text
# ---------------------------------------------------------------------------
# "am 15.03.2026 um 14:00"
DATE_TIME_DE = re.compile(
    r'(?:am\s+)?(\d{1,2})\.(\d{1,2})\.(\d{4})\s+(?:um\s+)?(\d{1,2})[:\.](\d{2})\s*(?:uhr)?',
    re.I,
)
# "Montag, 15. März 2026, 14:00 Uhr"
DATE_LONG_DE = re.compile(
    r'(?:montag|dienstag|mittwoch|donnerstag|freitag|samstag|sonntag)[,\s]+(\d{1,2})\.\s*'
    r'(januar|februar|märz|maerz|april|mai|juni|juli|august|september|oktober|november|dezember)\s+'
    r'(\d{4})[,\s]+(\d{1,2})[:\.](\d{2})',
    re.I,
)
# "15.03.2026" (date only, no time)
DATE_ONLY_DE = re.compile(r'(\d{1,2})\.(\d{1,2})\.(\d{4})')

MONTH_DE = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4,
    "mai": 5, "juni": 6, "juli": 7, "august": 8, "september": 9,
    "oktober": 10, "november": 11, "dezember": 12,
}


def _decode_header(value):
    """Decode a possibly encoded email header value."""
    if not value:
        return ""
    decoded_parts = email.header.decode_header(value)
    parts = []
    for part, charset in decoded_parts:
        if isinstance(part, bytes):
            parts.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            parts.append(part)
    return " ".join(parts)


def _get_text_parts(msg):
    """Extract plain text and html from an email.message.Message."""
    text_parts = []
    html_parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    text_parts.append(payload.decode(charset, errors="replace"))
            elif ct == "text/html":
                payload = part.get_payload(decode=True)
                if payload:
                    charset = part.get_content_charset() or "utf-8"
                    html_parts.append(payload.decode(charset, errors="replace"))
    else:
        ct = msg.get_content_type()
        payload = msg.get_payload(decode=True)
        if payload:
            charset = msg.get_content_charset() or "utf-8"
            decoded = payload.decode(charset, errors="replace")
            if ct == "text/html":
                html_parts.append(decoded)
            else:
                text_parts.append(decoded)
    return "\n".join(text_parts), "\n".join(html_parts)


def _extract_attachments_eml(msg):
    """Extract attachment metadata from an email.message.Message."""
    attachments = []
    for part in msg.walk():
        cd = part.get("Content-Disposition")
        if cd and ("attachment" in cd.lower() or "inline" in cd.lower()):
            filename = part.get_filename()
            if filename:
                filename = _decode_header(filename)
                payload = part.get_payload(decode=True)
                size = len(payload) if payload else 0
                ct = part.get_content_type() or ""
                attachments.append({
                    "filename": filename,
                    "content_type": ct,
                    "size": size,
                    "payload": payload,
                })
    return attachments


# =====================================================================
# Main parsing functions
# =====================================================================

def parse_eml(filepath: str) -> dict:
    """Parse a .eml file and return structured email data."""
    with open(filepath, "rb") as f:
        msg = email.message_from_bytes(f.read())

    sender = _decode_header(msg.get("From", ""))
    to = _decode_header(msg.get("To", ""))
    subject = _decode_header(msg.get("Subject", ""))
    date_str = msg.get("Date", "")
    date_tuple = email.utils.parsedate_tz(date_str)
    sent_date = None
    if date_tuple:
        ts = email.utils.mktime_tz(date_tuple)
        sent_date = datetime.fromtimestamp(ts).isoformat()

    body_text, body_html = _get_text_parts(msg)
    attachments = _extract_attachments_eml(msg)

    return {
        "subject": subject,
        "sender": sender,
        "recipients": to,
        "sent_date": sent_date,
        "body_text": body_text,
        "body_html": body_html,
        "attachments": attachments,
        "source_format": "eml",
    }


def parse_msg(filepath: str) -> dict:
    """Parse a .msg (Outlook) file and return structured email data."""
    try:
        import extract_msg
    except ImportError:
        raise ImportError(
            "extract-msg ist nicht installiert. "
            "Bitte PBP neu installieren (INSTALLIEREN.bat). "
            "Falls das nicht hilft: Mail in Outlook als .eml oder PDF speichern und erneut hochladen."
        )
    msg = extract_msg.Message(filepath)
    sender = msg.sender or ""
    to = msg.to or ""
    subject = msg.subject or ""
    body_text = msg.body or ""
    body_html = getattr(msg, "htmlBody", None) or ""
    if isinstance(body_html, bytes):
        body_html = body_html.decode("utf-8", errors="replace")
    sent_date = None
    if msg.date:
        try:
            if isinstance(msg.date, datetime):
                sent_date = msg.date.isoformat()
            else:
                sent_date = str(msg.date)
        except Exception:
            pass

    attachments = []
    for att in (msg.attachments or []):
        att_name = getattr(att, "longFilename", None) or getattr(att, "shortFilename", None) or "attachment"
        att_data = getattr(att, "data", None) or b""
        attachments.append({
            "filename": att_name,
            "content_type": getattr(att, "mimetype", "") or "",
            "size": len(att_data),
            "payload": att_data,
        })

    msg.close()

    return {
        "subject": subject,
        "sender": sender,
        "recipients": to,
        "sent_date": sent_date,
        "body_text": body_text,
        "body_html": body_html,
        "attachments": attachments,
        "source_format": "msg",
    }


def parse_email_file(filepath: str) -> dict:
    """Auto-detect format (.msg or .eml) and parse."""
    ext = Path(filepath).suffix.lower()
    if ext == ".msg":
        return parse_msg(filepath)
    elif ext == ".eml":
        return parse_eml(filepath)
    else:
        raise ValueError(f"Nicht unterstütztes E-Mail-Format: {ext}")


# =====================================================================
# Direction detection
# =====================================================================

def detect_direction(sender: str, profile_email: str) -> str:
    """Determine if email is incoming or outgoing based on sender vs profile email."""
    if not profile_email:
        return "eingang"
    sender_lower = sender.lower()
    profile_lower = profile_email.lower()
    # Check if profile email appears in the sender field
    if profile_lower in sender_lower:
        return "ausgang"
    return "eingang"


def extract_sender_email(sender: str) -> str:
    """Extract bare email address from 'Name <email@example.com>' format."""
    match = re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', sender or "")
    return match.group(0).lower() if match else ""


def extract_sender_domain(sender: str) -> str:
    """Extract domain from sender email."""
    addr = extract_sender_email(sender)
    if "@" in addr:
        return addr.split("@", 1)[1]
    return ""


# =====================================================================
# Application matching
# =====================================================================

def match_email_to_application(parsed_email: dict, applications: list) -> tuple[Optional[str], float]:
    """Try to match an email to an existing application.

    Returns (application_id, confidence) or (None, 0.0) if no match.
    Matching strategies (in order of confidence):
    1. Sender email domain matches application kontakt_email domain
    2. Sender email exactly matches application kontakt_email
    3. Company name appears in subject or sender
    4. Ansprechpartner name appears in sender
    """
    if not applications:
        return None, 0.0

    sender = (parsed_email.get("sender") or "").lower()
    sender_email = extract_sender_email(sender)
    sender_domain = extract_sender_domain(sender)
    subject = (parsed_email.get("subject") or "").lower()
    recipients = (parsed_email.get("recipients") or "").lower()
    # For outgoing emails, match by recipient domain instead
    direction = parsed_email.get("_direction", "eingang")
    match_text = recipients if direction == "ausgang" else sender

    best_match = None
    best_score = 0.0
    best_app_date = ""  # #389: tie-breaking by recency

    # #389: Archive statuses are deprioritized
    _archive_statuses = {"abgelehnt", "zurueckgezogen", "abgelaufen"}

    for app in applications:
        score = 0.0
        app_id = app.get("id")
        company = (app.get("company") or "").lower()
        kontakt_email = (app.get("kontakt_email") or "").lower()
        ansprechpartner = (app.get("ansprechpartner") or "").lower()
        title = (app.get("title") or "").lower()
        app_url = (app.get("url") or "").lower()
        app_status = (app.get("status") or "").lower()
        app_date = app.get("applied_at") or app.get("created_at") or ""

        # Strategy 1: Exact kontakt_email match → highest confidence
        if kontakt_email and kontakt_email == sender_email:
            score = max(score, 0.95)

        # Strategy 2: Domain match (kontakt_email domain)
        if kontakt_email and "@" in kontakt_email:
            app_domain = kontakt_email.split("@", 1)[1]
            if sender_domain and sender_domain == app_domain:
                score = max(score, 0.8)

        # Strategy 3: Company name in sender/subject
        if company and len(company) > 2:
            # Exact company in sender
            if company in match_text:
                score = max(score, 0.7)
            # Company in subject
            if company in subject:
                score = max(score, 0.65)
            # Domain contains company (e.g. "siemens" in "siemens.com")
            if sender_domain and company.replace(" ", "").replace("-", "") in sender_domain.replace("-", ""):
                score = max(score, 0.75)

        # Strategy 4: Job title in subject
        if title and len(title) > 4:
            # Look for significant words from title in subject
            title_words = [w for w in title.split() if len(w) > 3]
            if title_words:
                matches = sum(1 for w in title_words if w in subject)
                if matches >= 2 or (matches >= 1 and len(title_words) <= 2):
                    score = max(score, 0.6)

        # Strategy 5: Ansprechpartner in sender
        if ansprechpartner and len(ansprechpartner) > 3:
            name_parts = [p for p in ansprechpartner.split() if len(p) > 2]
            if name_parts and all(p in sender for p in name_parts):
                score = max(score, 0.5)

        # Strategy 6: URL domain match
        if app_url and sender_domain:
            url_match = re.search(r'://([^/]+)', app_url)
            if url_match:
                url_domain = url_match.group(1).lower()
                if sender_domain in url_domain or url_domain.endswith(sender_domain):
                    score = max(score, 0.7)

        # #389: Tie-breaking — prefer active (non-archived) applications and newer ones
        is_better = False
        if score > best_score:
            is_better = True
        elif score == best_score and score > 0:
            # Same score: prefer active over archived, then newer over older
            best_is_archived = best_match and any(
                a.get("id") == best_match and (a.get("status") or "").lower() in _archive_statuses
                for a in applications
            )
            this_is_archived = app_status in _archive_statuses
            if best_is_archived and not this_is_archived:
                is_better = True
            elif best_is_archived == this_is_archived and app_date > best_app_date:
                is_better = True

        if is_better:
            best_score = score
            best_match = app_id
            best_app_date = app_date

    # #389: Raise minimum threshold from 0.3 to 0.5 to reduce wrong associations
    if best_score < 0.5:
        return None, 0.0

    return best_match, round(best_score, 2)


# =====================================================================
# Status detection
# =====================================================================

def detect_email_status(subject: str, body_text: str) -> tuple[Optional[str], float]:
    """Detect application status from email content.

    Returns (status, confidence) where status is one of:
    - 'eingangsbestaetigung'
    - 'interview'
    - 'abgelehnt'
    - 'angebot'
    - None (if unclear)
    """
    combined = f"{subject} {body_text}".lower()
    # Normalize umlauts for matching
    combined_norm = (
        combined
        .replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
        .replace("ß", "ss")
    )

    best_status = None
    best_score = 0.0

    for status, patterns in STATUS_PATTERNS.items():
        hits = 0
        for pattern in patterns:
            p_norm = pattern.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
            if p_norm in combined_norm or pattern in combined:
                hits += 1
        if hits > 0:
            # More hits = higher confidence
            confidence = min(0.5 + hits * 0.15, 0.95)
            if confidence > best_score:
                best_score = confidence
                best_status = status

    # Map to application status
    status_map = {
        "eingangsbestaetigung": "beworben",  # Confirms current status
        "interview": "interview",
        "abgelehnt": "abgelehnt",
        "angebot": "angebot",
    }

    if best_status:
        return status_map.get(best_status, best_status), round(best_score, 2)
    return None, 0.0


# =====================================================================
# Meeting extraction
# =====================================================================

def extract_meeting_links(text: str) -> list[dict]:
    """Extract meeting URLs (Teams, Zoom, Meet, WebEx) from text."""
    results = []
    for pattern, platform in MEETING_LINK_PATTERNS:
        for match in pattern.finditer(text or ""):
            url = match.group(0).rstrip(".,;:)>]")
            results.append({"url": url, "platform": platform})
    return results


def _parse_ics(content: str) -> list[dict]:
    """Parse .ics calendar data and extract events."""
    events = []
    try:
        from icalendar import Calendar
        cal = Calendar.from_ical(content)
        for component in cal.walk():
            if component.name == "VEVENT":
                start = component.get("DTSTART")
                end = component.get("DTEND")
                summary = str(component.get("SUMMARY", ""))
                location = str(component.get("LOCATION", ""))
                description = str(component.get("DESCRIPTION", ""))

                start_dt = start.dt if start else None
                end_dt = end.dt if end else None

                # Convert date to datetime if needed
                if start_dt and not isinstance(start_dt, datetime):
                    start_dt = datetime.combine(start_dt, datetime.min.time())
                if end_dt and not isinstance(end_dt, datetime):
                    end_dt = datetime.combine(end_dt, datetime.min.time())

                # Look for meeting links in location or description
                links = extract_meeting_links(f"{location} {description}")

                events.append({
                    "title": summary,
                    "start": start_dt.isoformat() if start_dt else None,
                    "end": end_dt.isoformat() if end_dt else None,
                    "location": location,
                    "description": description,
                    "meeting_url": links[0]["url"] if links else None,
                    "platform": links[0]["platform"] if links else None,
                    "source": "ics",
                })
    except ImportError:
        logger.warning("icalendar nicht installiert — .ics Parsing übersprungen")
    except Exception as e:
        logger.warning("ICS Parsing fehlgeschlagen: %s", e)

    return events


def _extract_dates_from_text(text: str) -> list[dict]:
    """Extract date/time from German text patterns."""
    results = []
    if not text:
        return results

    # Pattern 1: "am 15.03.2026 um 14:00"
    for m in DATE_TIME_DE.finditer(text):
        day, month, year, hour, minute = m.groups()
        try:
            dt = datetime(int(year), int(month), int(day), int(hour), int(minute))
            # Only consider future or recent dates (not older than 1 year)
            if dt > datetime.now() - timedelta(days=365):
                results.append({
                    "start": dt.isoformat(),
                    "end": (dt + timedelta(hours=1)).isoformat(),
                    "source": "text",
                })
        except ValueError:
            pass

    # Pattern 2: "Montag, 15. März 2026, 14:00 Uhr"
    for m in DATE_LONG_DE.finditer(text):
        day, month_name, year, hour, minute = m.groups()
        month_num = MONTH_DE.get(month_name.lower())
        if month_num:
            try:
                dt = datetime(int(year), month_num, int(day), int(hour), int(minute))
                if dt > datetime.now() - timedelta(days=365):
                    results.append({
                        "start": dt.isoformat(),
                        "end": (dt + timedelta(hours=1)).isoformat(),
                        "source": "text",
                    })
            except ValueError:
                pass

    return results


def extract_meetings_from_email(parsed_email: dict) -> list[dict]:
    """Extract meeting information from a parsed email.

    Checks:
    1. .ics attachments
    2. Meeting links in body
    3. Date/time patterns in body text
    """
    meetings = []
    body = parsed_email.get("body_text", "") or ""
    html = parsed_email.get("body_html", "") or ""
    subject = parsed_email.get("subject", "") or ""
    combined_text = f"{subject}\n{body}\n{html}"

    # 1. Parse .ics attachments
    for att in (parsed_email.get("attachments") or []):
        fname = (att.get("filename") or "").lower()
        if fname.endswith(".ics") and att.get("payload"):
            try:
                ics_content = att["payload"]
                if isinstance(ics_content, bytes):
                    ics_content = ics_content.decode("utf-8", errors="replace")
                ics_events = _parse_ics(ics_content)
                meetings.extend(ics_events)
            except Exception as e:
                logger.warning("ICS attachment parsing failed: %s", e)

    # 2. Extract meeting links from body
    links = extract_meeting_links(combined_text)

    # 3. Extract dates from text
    dates = _extract_dates_from_text(body)

    # Combine: if we have dates and links but no ICS meetings, create meetings
    if dates and not meetings:
        for date_info in dates:
            meeting = {
                "title": subject,
                "start": date_info["start"],
                "end": date_info["end"],
                "location": "Online" if links else "",
                "meeting_url": links[0]["url"] if links else None,
                "platform": links[0]["platform"] if links else None,
                "source": "text",
            }
            meetings.append(meeting)
    elif meetings and links:
        # Enrich ICS meetings with links found in body (if ICS didn't have them)
        for m in meetings:
            if not m.get("meeting_url") and links:
                m["meeting_url"] = links[0]["url"]
                m["platform"] = links[0]["platform"]

    # If we only have links but no dates, record the link for reference
    if links and not meetings and not dates:
        meetings.append({
            "title": subject,
            "start": None,
            "end": None,
            "location": "Online",
            "meeting_url": links[0]["url"],
            "platform": links[0]["platform"],
            "source": "link_only",
        })

    return meetings


# =====================================================================
# Attachment processing
# =====================================================================

def save_attachments(parsed_email: dict, target_dir: str) -> list[dict]:
    """Save email attachments to disk and return metadata.

    Returns list of dicts with: filename, filepath, size, content_hash
    """
    saved = []
    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)

    for att in (parsed_email.get("attachments") or []):
        fname = att.get("filename", "")
        payload = att.get("payload")
        if not fname or not payload:
            continue
        # Skip .ics files (handled by meeting extraction)
        if fname.lower().endswith(".ics"):
            continue
        # Skip tiny or temp files
        if len(payload) < 100:
            continue
        if fname.startswith("~$"):
            continue

        # Resolve unique filename
        dest = target / fname
        counter = 1
        stem = dest.stem
        suffix = dest.suffix
        while dest.exists():
            dest = target / f"{stem}_{counter}{suffix}"
            counter += 1

        dest.write_bytes(payload)
        content_hash = hashlib.sha256(payload).hexdigest()

        saved.append({
            "filename": dest.name,
            "filepath": str(dest),
            "size": len(payload),
            "content_hash": content_hash,
            "content_type": att.get("content_type", ""),
        })

    return saved


def compute_file_hash(filepath: str) -> str:
    """Compute SHA256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def find_duplicate_document(content_hash: str, existing_docs: list) -> Optional[str]:
    """Check if a document with the same content hash already exists.

    Returns the document ID if found, None otherwise.
    """
    for doc in existing_docs:
        if doc.get("content_hash") == content_hash:
            return doc.get("id")
    return None


# =====================================================================
# Rejection feedback extraction
# =====================================================================

def extract_rejection_feedback(body_text: str) -> Optional[str]:
    """Extract useful feedback from rejection emails."""
    if not body_text:
        return None

    text_lower = body_text.lower()

    # Look for feedback indicators
    feedback_markers = [
        "profil passt nicht",
        "andere qualifikation",
        "erfahrung in",
        "stelle wurde intern",
        "position is no longer",
        "better suited candidate",
        "andere kandidaten bevorzugt",
        "anforderungsprofil",
        "leider nicht",
    ]

    has_feedback = any(m in text_lower for m in feedback_markers)
    if not has_feedback:
        return None

    # Extract relevant paragraph (around rejection keywords)
    paragraphs = body_text.split("\n\n")
    feedback_parts = []
    for para in paragraphs:
        para_lower = para.lower()
        if any(m in para_lower for m in feedback_markers):
            cleaned = para.strip()
            if 20 < len(cleaned) < 500:
                feedback_parts.append(cleaned)

    if feedback_parts:
        return "\n\n".join(feedback_parts[:3])
    return None
