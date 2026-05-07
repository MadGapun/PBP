"""Elwosa-Service (#599).

Live-Statusanzeige der lokalen AI mit eigener Persoenlichkeit.

- Sprach-DNA-Validator (gemeinsam fuer schreiben + linie_vorschlagen)
- Linien-Auswahl-Algorithmus (cluster + trigger_kind + seen-Set)
- Variablen-Einsetzung
- Anti-Spam (90s-Cooldown, Frequenz-Drosselung pro Trigger-Klasse)
- AI-State-Logik

Quelle der Linien: services/elwosa_lines.py
Charakter-Briefing: docs/elwosa-character.md
"""

from __future__ import annotations

import logging
import random
import re
from datetime import datetime, timedelta
from typing import Optional

from .elwosa_lines import (
    AI_STATE_LINES, CLUSTER_LINES, EASTER_EGGS, FREQUENCY_LIMITS,
    IDLE_LINES, STATUS_CHANGE_LINES, STATUS_LINES, TIP_LINES,
    WELCOME_MESSAGE, WORLD_LINES,
)

logger = logging.getLogger("bewerbungs_assistent.elwosa")


# === Sprach-DNA-Validator ========================================

class TonfallError(ValueError):
    """Linie verstoesst gegen Elwosas Sprach-DNA."""


_FORBIDDEN_PATTERNS = [
    (r"!", "Ausrufezeichen sind verboten (Sprach-DNA)"),
    # Emoji-Range (vereinfacht — die haeufigsten Bloecke)
    (r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF]",
     "Emojis sind verboten (Sprach-DNA)"),
    # 'Sie' alleine ist mehrdeutig (Firma/Recruiter sind '3. Person Plural').
    # Hoeflichkeits-Anrede erkennen wir an Ihre/Ihnen/Ihres/Ihrem/Ihren —
    # die kommen NUR in Hoeflichkeitsform vor.
    (r"\bIhre[nrsm]?\b", "Hoeflichkeits-'Ihr/Ihre' ist verboten — Elwosa duzt"),
    (r"\bIhnen\b", "Hoeflichkeits-'Ihnen' ist verboten — Elwosa duzt"),
]

_MAX_LINE_LENGTH = 280


def validate_tonfall(content: str) -> None:
    """Prueft ob eine Linie der Elwosa-Sprach-DNA entspricht.

    Wirft TonfallError bei Verstoss. Wird sowohl von elwosa_schreiben
    als auch von elwosa_linie_vorschlagen genutzt.
    """
    if not content or not content.strip():
        raise TonfallError("Linie darf nicht leer sein")
    if len(content) > _MAX_LINE_LENGTH:
        raise TonfallError(
            f"Linie zu lang ({len(content)} Zeichen, max {_MAX_LINE_LENGTH})"
        )
    for pattern, hint in _FORBIDDEN_PATTERNS:
        if re.search(pattern, content):
            raise TonfallError(
                f"{hint}. Siehe docs/elwosa-character.md (Sektion 3 Sprach-DNA)."
            )


# === Welt-Trigger-Erkennung =====================================

def detect_world_trigger() -> Optional[str]:
    """Erkennt Welt-bezogene Trigger basierend auf aktueller Zeit/Datum."""
    now = datetime.now()
    h = now.hour
    weekday = now.weekday()  # 0=Mo, 6=So
    month = now.month
    day = now.day
    if h < 6:
        return "late_night"
    if month == 12 and day == 24 and h >= 18:
        return "holiday_christmas"
    if month in (7, 8):
        return "holiday_summer"
    if weekday == 0 and 6 <= h <= 9:
        return "monday_morning"
    if weekday == 4 and h >= 17:
        return "friday_evening"
    if weekday >= 5:
        return "weekend"
    if 6 <= h < 11:
        return "morning"
    if h >= 19:
        return "evening"
    return None


# === Variablen-Einsetzung ========================================

def fill_template(line: str, ctx: dict) -> str:
    """Ersetzt Platzhalter ({firma}, {count}, {days}, ...) durch Kontext."""
    if "{" not in line:
        return line
    try:
        return line.format(**{
            "firma": ctx.get("firma", ""),
            "count": ctx.get("count", 0),
            "title": ctx.get("title", ""),
            "score": ctx.get("score", 0),
            "percent": ctx.get("percent", 0),
            "days": ctx.get("days", 0),
            "tool": ctx.get("tool", ""),
            "wochentag": ctx.get("wochentag", ""),
        })
    except (KeyError, ValueError):
        # Wenn ein Platzhalter im Kontext fehlt: Linie unverändert ausgeben
        return line


# === Auswahl-Algorithmus =========================================

def _seen_recently(db, content: str, days: int = 7) -> bool:
    """Prueft ob eine Linie in den letzten N Tagen schon gepostet wurde."""
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    pid = db.get_active_profile_id()
    conn = db.connect()
    row = conn.execute(
        "SELECT 1 FROM elwosa_messages "
        "WHERE (profile_id=? OR profile_id IS NULL) "
        "AND content=? AND created_at >= ? LIMIT 1",
        (pid, content, cutoff)
    ).fetchone()
    return row is not None


def pick_line(db, pool: list, ctx: dict) -> Optional[str]:
    """Waehlt eine Linie aus dem Pool, die nicht in den letzten 7 Tagen
    benutzt wurde. Liefert None wenn der ganze Pool 'verbraucht' ist."""
    if not pool:
        return None
    candidates = [
        line for line in pool
        if not _seen_recently(db, fill_template(line, ctx), days=7)
    ]
    if not candidates:
        # Fallback: Pool wieder freischalten (alle gleich behandeln)
        candidates = pool
    chosen = random.choice(candidates)
    return fill_template(chosen, ctx)


# === Anti-Spam-Checks ============================================

def is_in_cooldown(db, seconds: int = 90) -> bool:
    """True wenn die letzte Nachricht weniger als N Sekunden her ist."""
    last = db.get_last_elwosa_message_at()
    if not last:
        return False
    try:
        last_dt = datetime.fromisoformat(last)
    except Exception:
        return False
    # Timezone-aware vs. naive abgleichen — DB liefert UTC mit tz-info,
    # datetime.now() ist naive (lokal).
    now = datetime.now(last_dt.tzinfo) if last_dt.tzinfo else datetime.now()
    delta = (now - last_dt).total_seconds()
    return delta < seconds


def can_post_class(db, trigger_kind: str, settings: dict) -> bool:
    """Prueft Frequenz-Limits pro Trigger-Klasse.

    Status-Trigger (mail_received, auto_dismiss_ran, status_change, etc.)
    sind UNBEGRENZT. Nur idle/world/tip werden gedrosselt.
    """
    if trigger_kind in (
        "llm_task_running", "mail_received", "auto_dismiss_ran",
        "pattern_insight", "status_change", "job_new_high_score",
        "ai_state_change", "welcome", "manual_via_claude",
        "user_question", "claude_handoff", "easter_egg",
    ):
        return True
    freq = settings.get("frequency", "standard")
    limits = FREQUENCY_LIMITS.get(freq, FREQUENCY_LIMITS["standard"])

    if trigger_kind == "idle":
        return _count_today(db, "idle") < limits["idle"]
    if trigger_kind == "world":
        return _count_today(db, "world") < limits["world"]
    if trigger_kind == "tip":
        if _count_today(db, "tip") >= limits["tip_per_day"]:
            return False
        if _count_in_days(db, "tip", 7) >= limits["tip_per_week"]:
            return False
        return True
    return True


def _count_today(db, trigger_kind: str) -> int:
    pid = db.get_active_profile_id()
    today = datetime.now().date().isoformat()
    conn = db.connect()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM elwosa_messages "
        "WHERE (profile_id=? OR profile_id IS NULL) "
        "AND trigger_kind=? AND date(created_at) = date(?)",
        (pid, trigger_kind, today)
    ).fetchone()
    return row["n"] if row else 0


def _count_in_days(db, trigger_kind: str, days: int) -> int:
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    pid = db.get_active_profile_id()
    conn = db.connect()
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM elwosa_messages "
        "WHERE (profile_id=? OR profile_id IS NULL) "
        "AND trigger_kind=? AND created_at >= ?",
        (pid, trigger_kind, cutoff)
    ).fetchone()
    return row["n"] if row else 0


# === Master-Speak-Funktion =======================================

def speak(db, trigger_kind: str, ctx: Optional[dict] = None,
           cluster: Optional[str] = None) -> Optional[int]:
    """Triggert Elwosa-Linie nach allen Regeln.

    Args:
        db: Database-Instanz
        trigger_kind: 'morning' | 'mail_received' | 'idle' | ...
        ctx: Variablen-Kontext fuer Template-Einsetzung
        cluster: Profil-Cluster (None = aus Profil ableiten)

    Returns:
        message_id wenn gepostet, None wenn unterdrueckt (Cooldown, Limit, etc.)
    """
    ctx = ctx or {}
    settings = db.get_elwosa_settings()
    if not settings.get("enabled"):
        return None
    # Pause-Check
    paused_until = settings.get("paused_until")
    if paused_until:
        try:
            until = datetime.fromisoformat(paused_until)
            now = datetime.now(until.tzinfo) if until.tzinfo else datetime.now()
            if until > now:
                return None
        except Exception:
            pass
    if is_in_cooldown(db):
        return None
    if not can_post_class(db, trigger_kind, settings):
        return None

    # Pool waehlen
    pool: list = []
    if trigger_kind in STATUS_LINES:
        pool = STATUS_LINES[trigger_kind]
    elif trigger_kind in WORLD_LINES:
        pool = WORLD_LINES[trigger_kind]
    elif trigger_kind in STATUS_CHANGE_LINES:
        pool = STATUS_CHANGE_LINES[trigger_kind]
    elif trigger_kind == "tip":
        pool = TIP_LINES
    elif trigger_kind == "idle":
        # Idle nutzt cluster-spezifischen Pool wenn moeglich, sonst global
        if cluster and cluster in CLUSTER_LINES:
            pool = CLUSTER_LINES[cluster] + IDLE_LINES
        else:
            pool = IDLE_LINES
    elif trigger_kind == "easter_egg":
        # Easter Eggs: ctx muss "egg_id" liefern
        egg_id = ctx.get("egg_id")
        if egg_id and egg_id in EASTER_EGGS:
            pool = [EASTER_EGGS[egg_id]]
    elif trigger_kind == "welcome":
        pool = [WELCOME_MESSAGE]

    line = pick_line(db, pool, ctx)
    if not line:
        return None
    try:
        validate_tonfall(line)
    except TonfallError as exc:
        logger.warning(
            "Linie verstoesst gegen Sprach-DNA: %s — Linie: %r",
            exc, line
        )
        return None

    msg_id = db.add_elwosa_message(
        content=line,
        trigger_kind=trigger_kind,
        trigger_ref=str(ctx.get("ref") or ""),
        cluster=cluster or ctx.get("cluster") or "",
    )
    return msg_id


def speak_raw(db, content: str, trigger_kind: str = "manual_via_claude",
               trigger_ref: str = "") -> int:
    """Direkter Schreibzugriff (von Claude via MCP-Tool).

    Validiert Tonfall, ignoriert Cooldown nicht (UX-Schutz).
    """
    validate_tonfall(content)
    if is_in_cooldown(db, seconds=10):
        # Bei Claude-Schreibzugriff geben wir 10s Cooldown statt 90s —
        # User-getriebene Konversation darf fluessiger sein.
        raise TonfallError("Zu schnell hintereinander, bitte 10s warten.")
    return db.add_elwosa_message(
        content=content,
        trigger_kind=trigger_kind,
        trigger_ref=trigger_ref,
    )


# === Stimmungs-Drift =============================================

def detect_mood(db) -> str:
    """Heuristische Stimmungs-Erkennung aus aktuellem Bewerbungs-Kontext.

    Rueckgabe: 'standard' | 'melancholisch' | 'beschuetzend' | 'aufmerksam' | 'gelangweilt'
    """
    conn = db.connect()
    pid = db.get_active_profile_id()
    try:
        # 3 Absagen in 7 Tagen → beschuetzend
        recent_rejections = conn.execute(
            "SELECT COUNT(*) AS n FROM applications "
            "WHERE status='abgelehnt' AND updated_at >= ? "
            "AND (profile_id=? OR profile_id IS NULL)",
            ((datetime.now() - timedelta(days=7)).isoformat(), pid)
        ).fetchone()
        if recent_rejections and (recent_rejections["n"] or 0) >= 3:
            return "beschuetzend"

        # Letzte Bewerbung > 14 Tage → melancholisch
        last_app = conn.execute(
            "SELECT MAX(applied_at) AS last FROM applications "
            "WHERE (profile_id=? OR profile_id IS NULL)",
            (pid,)
        ).fetchone()
        if last_app and last_app["last"]:
            try:
                last_dt = datetime.fromisoformat(last_app["last"])
                if (datetime.now() - last_dt).days >= 14:
                    return "melancholisch"
            except Exception:
                pass

        # Interview-Einladung in 7 Tagen → aufmerksam
        recent_interviews = conn.execute(
            "SELECT COUNT(*) AS n FROM applications "
            "WHERE status IN ('interview', 'zweitgespraech') "
            "AND updated_at >= ? "
            "AND (profile_id=? OR profile_id IS NULL)",
            ((datetime.now() - timedelta(days=7)).isoformat(), pid)
        ).fetchone()
        if recent_interviews and (recent_interviews["n"] or 0) >= 1:
            return "aufmerksam"
    except Exception as exc:
        logger.debug("detect_mood Fallback: %s", exc)
    return "standard"


# === Public API: Status =========================================

def get_status(db, ai_state: str = "active") -> dict:
    """Status-Snapshot fuer das Frontend / MCP-Tool elwosa_status."""
    settings = db.get_elwosa_settings()
    last = db.get_last_elwosa_message_at()
    pool_total = sum(len(p) for p in CLUSTER_LINES.values()) + len(IDLE_LINES) + len(TIP_LINES)
    pending = len(db.get_elwosa_pending_lines())
    paused_until = settings.get("paused_until")
    is_paused = False
    if paused_until:
        try:
            until = datetime.fromisoformat(paused_until)
            now = datetime.now(until.tzinfo) if until.tzinfo else datetime.now()
            is_paused = until > now
        except Exception:
            pass
    return {
        "is_active": settings.get("enabled") and not is_paused
                     and ai_state == "active",
        "ai_state": ai_state,
        "is_paused": is_paused,
        "paused_until": paused_until or "",
        "mood": detect_mood(db),
        "messages_today": db.count_elwosa_messages_today(),
        "tonfall_modus": settings.get("tonfall_modus", "standard"),
        "frequency": settings.get("frequency", "standard"),
        "pool_size_total": pool_total,
        "pool_size_pending": pending,
        "last_message_at": last or "",
    }
