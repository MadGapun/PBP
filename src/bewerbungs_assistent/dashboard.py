"""Web Dashboard for Bewerbungs-Assistent.

Serves a browser-based UI on localhost:8200 for visual management.
Runs in a background thread alongside the MCP server.
"""

import json
import math
import os
import logging
import threading
import hashlib
from html import escape
from pathlib import Path, PurePosixPath, PureWindowsPath
from datetime import datetime, timedelta

from fastapi import FastAPI, Request, UploadFile, File, Form, Body
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles


def _sanitize_for_json(obj):
    """Recursively replace inf/nan floats with None for JSON safety."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, float) and (math.isinf(obj) or math.isnan(obj)):
        return None
    return obj


class SafeJSONResponse(JSONResponse):
    """JSONResponse that sanitizes inf/nan floats before serialization."""

    def render(self, content):
        return json.dumps(
            _sanitize_for_json(content),
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
        ).encode("utf-8")

from .services.profile_service import (
    get_profile_completeness,
    get_profile_preferences,
    summarize_profile,
)
from .services.search_service import (
    build_source_rows,
    get_default_active_source_keys,
    get_search_status,
    summarize_active_sources,
)
from .services.workspace_service import build_workspace_summary, summarize_follow_ups
from .document_analysis_prompts import (
    TEMPLATES as DOC_ANALYSIS_TEMPLATES,
    available_templates as doc_analysis_available_templates,
    build_prompt as build_document_analysis_prompt,
)

logger = logging.getLogger("bewerbungs_assistent.dashboard")

# Reference to shared database (set in start_dashboard)
_db = None

_BLOCKED_PATH_PREFIXES = (
    "/etc",
    "/var",
    "/usr",
    "/bin",
    "/sbin",
    "/root",
    "/proc",
    "/sys",
    "C:\\Windows",
    "C:\\Program Files",
    "C:\\Program Files (x86)",
)

app = FastAPI(
    title="Bewerbungs-Assistent",
    docs_url=None,
    redoc_url=None,
    default_response_class=SafeJSONResponse,
)


class ApiRequestLoggingMiddleware:
    """ASGI logging middleware without BaseHTTPMiddleware response-body side effects."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        import time

        start = time.time()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
            if scope.get("path", "").startswith("/api/"):
                duration = time.time() - start
                logger.debug(
                    "%s %s %d (%.1fms)",
                    scope.get("method", "HTTP"),
                    scope.get("path", ""),
                    status_code,
                    duration * 1000,
                )
        except Exception as exc:
            logger.error("%s %s Fehler: %s", scope.get("method", "HTTP"), scope.get("path", ""), exc)
            raise


app.add_middleware(ApiRequestLoggingMiddleware)


# Static files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

DASHBOARD_BUILD_HTML = Path(__file__).parent / "static" / "dashboard" / "index.html"


# === Pages ===

@app.get("/", response_class=HTMLResponse)
async def index():
    """Main dashboard page."""
    if not DASHBOARD_BUILD_HTML.exists():
        logger.error("Dashboard-Frontend nicht gefunden: %s", DASHBOARD_BUILD_HTML)
        return HTMLResponse(
            _generate_dashboard_error_html(
                message="Das Dashboard-Frontend wurde nicht gefunden.",
                details=f"Erwarteter Pfad: {DASHBOARD_BUILD_HTML}",
                hint="Bitte Frontend-Build ausführen, z. B. mit 'pnpm run build:web'.",
            ),
            status_code=500,
        )
    try:
        return HTMLResponse(DASHBOARD_BUILD_HTML.read_text(encoding="utf-8"))
    except OSError as exc:
        logger.exception("Dashboard-Frontend konnte nicht geladen werden: %s", exc)
        return HTMLResponse(
            _generate_dashboard_error_html(
                message="Das Dashboard-Frontend konnte nicht geladen werden.",
                details=str(exc),
                hint=f"Pfad: {DASHBOARD_BUILD_HTML}",
            ),
            status_code=500,
        )


def _normalize_path_for_check(path: str) -> str:
    """Normalize user-provided and resolved paths for prefix checks."""
    return str(path).replace("/", "\\").rstrip("\\").lower()


def _is_blocked_path(raw_path: str, resolved_path: Path) -> bool:
    """Block obvious system directories on both Unix-like and Windows inputs."""
    blocked = {_normalize_path_for_check(prefix) for prefix in _BLOCKED_PATH_PREFIXES}
    candidates = {
        _normalize_path_for_check(raw_path),
        _normalize_path_for_check(str(resolved_path)),
    }
    return any(
        candidate == prefix or candidate.startswith(prefix + "\\")
        for candidate in candidates
        for prefix in blocked
    )


def _get_search_status_payload() -> dict:
    """Build the normalized search-status payload once for UI consumers."""
    return get_search_status(_db.get_profile_setting("last_search_at"), now=datetime.now())


def _get_source_summary() -> dict:
    """Return active vs. total configured job sources."""
    from .job_scraper import SOURCE_REGISTRY

    return summarize_active_sources(_db.get_profile_setting("active_sources", []) or [], SOURCE_REGISTRY.keys())


def _get_follow_up_summary() -> dict:
    """Return follow-up totals and due count for the active profile."""
    return summarize_follow_ups(_db.get_pending_follow_ups())


def _build_workspace_summary() -> dict:
    """Aggregate the current workspace state for dashboard navigation and guidance."""
    # #534 v1.6.5: exclude_blacklisted=True konsistent zur Stellen-Liste
    return build_workspace_summary(
        profile=_db.get_profile(),
        jobs=_db.get_active_jobs(exclude_applied=True, exclude_blacklisted=True),
        applications=_db.get_applications(),
        source_summary=_get_source_summary(),
        search_status=_get_search_status_payload(),
        follow_up_summary=_get_follow_up_summary(),
    )


def _build_live_update_token_payload() -> dict:
    """Build a stable token that changes whenever persisted DB files change."""
    profile_id = _db.get_active_profile_id() if _db else ""
    db_path = Path(getattr(_db, "db_path", "")) if _db else None
    parts = [str(profile_id or "")]

    if db_path:
        # Include SQLite main db plus WAL/SHM sidecars.
        for suffix in ("", "-wal", "-shm"):
            path = Path(f"{db_path}{suffix}")
            if not path.exists():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            parts.append(f"{path.name}:{stat.st_mtime_ns}:{stat.st_size}")

    raw = "|".join(parts)
    token = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
    return {
        "token": token,
        "profile_id": profile_id or None,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }


def _get_active_profile_id() -> str | None:
    """Return the current active profile id for profile-scoped API guards."""
    return _db.get_active_profile_id() if _db else None


def _get_application_row_for_active_profile(app_id: str):
    """Fetch an application only if it belongs to the active profile."""
    profile_id = _get_active_profile_id()
    if not profile_id:
        return None
    conn = _db.connect()
    return conn.execute(
        "SELECT * FROM applications WHERE id=? AND (profile_id=? OR profile_id IS NULL)",
        (app_id, profile_id),
    ).fetchone()


def _get_meeting_row_for_active_profile(meeting_id: str):
    """Fetch a meeting with application metadata, scoped to the active profile."""
    profile_id = _get_active_profile_id()
    if not profile_id:
        return None
    conn = _db.connect()
    return conn.execute(
        """SELECT m.*, a.title as app_title, a.company as app_company, a.id as app_id
           FROM application_meetings m
           LEFT JOIN applications a ON m.application_id = a.id
           WHERE m.id=? AND (m.profile_id=? OR m.profile_id IS NULL)""",
        (meeting_id, profile_id),
    ).fetchone()


def _get_email_for_active_profile(email_id: str):
    """Fetch an email only if it belongs to the active profile."""
    profile_id = _get_active_profile_id()
    if not profile_id:
        return None
    return _db.get_email(email_id, profile_id=profile_id) if _db else None


# === API Endpoints ===

@app.get("/api/status")
async def api_status():
    from . import __version__
    from .heartbeat import get_connection_status

    profile = _db.get_profile()
    summary = summarize_profile(profile)
    return {
        "version": __version__,
        "has_profile": profile is not None,
        "profile_name": summary["name"],
        # #534 v1.6.5: exclude_blacklisted=True angleichen an die Stellen-Liste,
        # die /api/jobs?active=true&exclude_blacklisted=true aufruft. Vorher
        # zaehlte die Sidebar Blacklist-Stellen mit, die Liste sortierte sie aus
        # — Counter-Drift war die Folge (Sidebar 2, Liste 1).
        "active_jobs": len(_db.get_active_jobs(exclude_applied=True, exclude_blacklisted=True)),
        "applications": len(_db.get_applications()),
        "statistics": _db.get_statistics(),
        "mcp_connection": get_connection_status(),
    }




@app.get("/api/public/hints")
async def api_public_hints():
    """Holt dezente Hinweise/Updates aus einer öffentlichen GitHub-Quelle (#233).

    Kein Login nötig. Ergebnis wird 1h gecacht.
    """
    import time
    cache = getattr(api_public_hints, "_cache", None)
    now = time.time()
    if cache and now - cache["ts"] < 3600:
        return cache["data"]

    from . import __version__
    # PBP_HINTS_URL kann auf "off" oder einen lokalen file://-Pfad gesetzt werden,
    # z.B. fuer Screenshot-Generierung oder Tests, in denen Cloud-Pulls stoeren.
    hints_url = os.environ.get(
        "PBP_HINTS_URL",
        "https://raw.githubusercontent.com/MadGapun/PBP/main/hints.json",
    )
    result = {"hints": [], "version": __version__}
    if hints_url.lower() == "off":
        api_public_hints._cache = {"ts": now, "data": result}
        return result
    try:
        if hints_url.startswith(("file://", "./", "/")) or os.path.isabs(hints_url):
            local_path = hints_url[len("file://"):] if hints_url.startswith("file://") else hints_url
            with open(local_path, "r", encoding="utf-8") as fh:
                import json as _json
                data = _json.load(fh)
        else:
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(hints_url)
                data = resp.json() if resp.status_code == 200 else {}
        hints = data if isinstance(data, list) else data.get("hints", [])
        result["hints"] = [
            h for h in hints
            if not h.get("min_version") or h["min_version"] <= __version__
        ]
    except Exception as exc:
        logger.debug("hints fetch failed: %s", exc)

    api_public_hints._cache = {"ts": now, "data": result}
    return result


@app.get("/api/workspace-summary")
async def api_workspace_summary():
    """Aggregated workspace state for dashboard guidance and navigation."""
    return _build_workspace_summary()


@app.get("/api/live-update-token")
async def api_live_update_token():
    """Token for frontend polling to detect external DB writes in near realtime."""
    return _build_live_update_token_payload()


# === Daily Impulse (#163) ===


def _get_daily_impulse() -> dict:
    """Build the daily impulse payload using the impulse service (#163)."""
    from .services.daily_impulse_service import get_daily_impulse
    from .services.profile_service import get_profile_completeness

    enabled = _db.get_profile_setting("daily_impulse_enabled", True)

    try:
        profile = _db.get_profile()
        has_profile = profile is not None
        completeness = get_profile_completeness(profile)["completeness"] if profile else 0
        source_summary = _get_source_summary()
        search_status = _get_search_status_payload()
        follow_up_summary = _get_follow_up_summary()
        active_jobs = len(_db.get_active_jobs())
        total_applications = len(_db.get_applications())
    except Exception:
        has_profile = False
        completeness = 0
        source_summary = {"active": 0}
        search_status = {"status": "nie"}
        follow_up_summary = {"due": 0}
        active_jobs = 0
        total_applications = 0

    return get_daily_impulse(
        enabled=enabled,
        has_profile=has_profile,
        profile_completeness=completeness,
        active_sources=source_summary["active"],
        search_status=search_status["status"],
        active_jobs=active_jobs,
        total_applications=total_applications,
        follow_ups_due=follow_up_summary["due"],
    )


@app.get("/api/daily-impulse")
async def api_daily_impulse():
    """Tagesimpuls für das Dashboard (#163)."""
    return _get_daily_impulse()


@app.post("/api/daily-impulse/toggle")
async def api_toggle_daily_impulse():
    """Toggle daily impulse on/off (#163)."""
    current = _db.get_profile_setting("daily_impulse_enabled", True)
    _db.set_profile_setting("daily_impulse_enabled", not current)
    return {"enabled": not current}


@app.get("/api/profile")
async def api_profile():
    profile = _db.get_profile()
    if profile is None:
        return JSONResponse({"error": "Kein Profil vorhanden"}, status_code=404)
    return profile


@app.post("/api/profile")
async def api_save_profile(request: Request):
    data = await request.json()
    if not data.get("name", "").strip():
        return JSONResponse({"error": "Name ist ein Pflichtfeld"}, status_code=400)
    pid = _db.save_profile(data)
    return {"status": "ok", "id": pid}


@app.get("/api/profiles")
async def api_list_profiles():
    """List all profiles for profile switching."""
    # Ensure active-profile state is canonicalized before listing.
    _db.get_active_profile_id()
    profiles = _db.get_profiles()
    return {"profiles": profiles}


@app.post("/api/profiles/switch")
async def api_switch_profile(request: Request):
    """Switch active profile."""
    data = await request.json()
    profile_id = data.get("profile_id")
    if not profile_id:
        return JSONResponse({"error": "Keine profil_id angegeben"}, status_code=400)
    success = _db.switch_profile(profile_id)
    if success:
        return {"status": "ok"}
    return JSONResponse({"error": "Profil nicht gefunden"}, status_code=404)


@app.post("/api/profiles/new")
async def api_new_profile(request: Request):
    """Create a new empty profile."""
    data = await request.json()
    name = data.get("name", "")
    if not name:
        return JSONResponse({"error": "Name ist erforderlich"}, status_code=400)
    pid = _db.create_profile(name, data.get("email", ""))
    return {"status": "ok", "id": pid}


@app.delete("/api/profiles/{profile_id}")
async def api_delete_profile(profile_id: str):
    """Delete a profile and all its data. If active, switch to another first."""
    active_id = _db.get_active_profile_id()
    if profile_id == active_id:
        # Try switching to another profile before deleting
        conn = _db.connect()
        other = conn.execute(
            "SELECT id FROM profile WHERE id != ? ORDER BY updated_at DESC LIMIT 1",
            (profile_id,),
        ).fetchone()
        if other:
            _db.switch_profile(other["id"])
        # else: last profile - delete anyway, no active profile afterwards
    deleted = _db.delete_profile(profile_id)
    if not deleted:
        return JSONResponse({"error": "Profil nicht gefunden"}, status_code=404)
    return {"status": "ok"}


# === Job Title Suggestions ===

@app.get("/api/job-titles")
async def api_get_job_titles():
    titles = _db.get_suggested_job_titles()
    return {"titles": titles}


@app.post("/api/job-title")
async def api_add_job_title(request: Request):
    data = await request.json()
    title = data.get("title", "").strip()
    if not title:
        return JSONResponse({"error": "Titel ist ein Pflichtfeld"}, status_code=400)
    tid = _db.add_job_title(title, source="user", confidence=1.0)
    return {"status": "ok", "id": tid}


@app.put("/api/job-title/{title_id}")
async def api_update_job_title(title_id: str, request: Request):
    data = await request.json()
    profile_id = _get_active_profile_id()
    if not profile_id or not _db.update_job_title(title_id, data, profile_id=profile_id):
        return JSONResponse({"error": "Jobtitel nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.delete("/api/job-title/{title_id}")
async def api_delete_job_title(title_id: str):
    profile_id = _get_active_profile_id()
    if not profile_id or not _db.delete_job_title(title_id, profile_id=profile_id):
        return JSONResponse({"error": "Jobtitel nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.post("/api/position")
async def api_add_position(request: Request):
    data = await request.json()
    if not data.get("company", "").strip():
        return JSONResponse({"error": "Firma ist ein Pflichtfeld"}, status_code=400)
    if not data.get("title", "").strip():
        return JSONResponse({"error": "Titel ist ein Pflichtfeld"}, status_code=400)
    pid = _db.add_position(data)
    return {"status": "ok", "id": pid}


@app.post("/api/project")
async def api_add_project(request: Request):
    data = await request.json()
    if not data.get("name", "").strip():
        return JSONResponse({"error": "Projektname ist ein Pflichtfeld"}, status_code=400)
    position_id = data.pop("position_id")
    pid = _db.add_project(position_id, data)
    return {"status": "ok", "id": pid}


@app.put("/api/project/{project_id}")
async def api_update_project(project_id: str, request: Request):
    data = await request.json()
    if not data.get("name", "").strip():
        return JSONResponse({"error": "Projektname ist ein Pflichtfeld"}, status_code=400)
    profile_id = _get_active_profile_id()
    if not profile_id or not _db.update_project(project_id, data, profile_id=profile_id):
        return JSONResponse({"error": "Projekt nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.delete("/api/project/{project_id}")
async def api_delete_project(project_id: str):
    profile_id = _get_active_profile_id()
    if not profile_id or not _db.delete_project(project_id, profile_id=profile_id):
        return JSONResponse({"error": "Projekt nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.post("/api/education")
async def api_add_education(request: Request):
    data = await request.json()
    if not data.get("institution", "").strip():
        return JSONResponse({"error": "Einrichtung ist ein Pflichtfeld"}, status_code=400)
    eid = _db.add_education(data)
    return {"status": "ok", "id": eid}


@app.post("/api/skill")
async def api_add_skill(request: Request):
    data = await request.json()
    if not data.get("name", "").strip():
        return JSONResponse({"error": "Name ist ein Pflichtfeld"}, status_code=400)
    sid = _db.add_skill(data)
    return {"status": "ok", "id": sid}


@app.put("/api/position/{position_id}")
async def api_update_position(position_id: str, request: Request):
    data = await request.json()
    profile_id = _get_active_profile_id()
    if not profile_id or not _db.update_position(position_id, data, profile_id=profile_id):
        return JSONResponse({"error": "Position nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.delete("/api/position/{position_id}")
async def api_delete_position(position_id: str):
    profile_id = _get_active_profile_id()
    if not profile_id or not _db.delete_position(position_id, profile_id=profile_id):
        return JSONResponse({"error": "Position nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.put("/api/education/{education_id}")
async def api_update_education(education_id: str, request: Request):
    data = await request.json()
    profile_id = _get_active_profile_id()
    if not profile_id or not _db.update_education(education_id, data, profile_id=profile_id):
        return JSONResponse({"error": "Ausbildung nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.delete("/api/education/{education_id}")
async def api_delete_education(education_id: str):
    profile_id = _get_active_profile_id()
    if not profile_id or not _db.delete_education(education_id, profile_id=profile_id):
        return JSONResponse({"error": "Ausbildung nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.put("/api/skill/{skill_id}")
async def api_update_skill(skill_id: str, request: Request):
    data = await request.json()
    profile_id = _get_active_profile_id()
    if not profile_id or not _db.update_skill(skill_id, data, profile_id=profile_id):
        return JSONResponse({"error": "Skill nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.delete("/api/skill/{skill_id}")
async def api_delete_skill(skill_id: str):
    profile_id = _get_active_profile_id()
    if not profile_id or not _db.delete_skill(skill_id, profile_id=profile_id):
        return JSONResponse({"error": "Skill nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.delete("/api/document/{doc_id}")
async def api_delete_document(doc_id: str):
    profile_id = _get_active_profile_id()
    if not profile_id:
        return JSONResponse({"error": "Dokument nicht gefunden"}, status_code=404)
    if not _db.delete_document(doc_id, profile_id=profile_id):
        return JSONResponse({"error": "Dokument nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.put("/api/document/{doc_id}/doc-type")
async def api_update_document_type(doc_id: str, request: Request):
    data = await request.json()
    new_type = data.get("doc_type", "sonstiges")
    profile_id = _get_active_profile_id()
    if not profile_id:
        return JSONResponse({"error": "Dokument nicht gefunden"}, status_code=404)
    if not _db.update_document_type(doc_id, new_type, profile_id=profile_id):
        return JSONResponse({"error": "Dokument nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.put("/api/document/{doc_id}/link")
async def api_link_document(doc_id: str, request: Request):
    """Change or remove document-application link (#366)."""
    data = await request.json()
    app_id = data.get("application_id") or None
    profile_id = _get_active_profile_id()
    if not profile_id:
        return JSONResponse({"error": "Dokument nicht gefunden"}, status_code=404)
    if not _db.relink_document(doc_id, app_id, profile_id=profile_id):
        return JSONResponse({"error": "Dokument oder Bewerbung nicht gefunden"}, status_code=404)
    return {"status": "ok"}


def _document_type_label(doc_type: str | None) -> str:
    labels = {
        "lebenslauf": "Lebenslauf",
        "lebenslauf_vorlage": "Lebenslauf-Vorlage",
        "anschreiben": "Anschreiben",
        "anschreiben_vorlage": "Anschreiben-Vorlage",
        "zeugnis": "Zeugnis",
        "zertifikat": "Zertifikat",
        "referenz": "Referenz",
        "projektliste": "Projektliste",
        "stellenbeschreibung": "Stellenbeschreibung",
        "vorbereitung": "Interview-Vorbereitung",
        "portfolio": "Portfolio",
        "foto": "Foto",
        "sonstiges": "Sonstiges Dokument",
    }
    return labels.get(doc_type or "", doc_type or "Dokument")


def _enrich_document_for_prompt(document: dict) -> dict:
    """Laedt Bewerbungs-Kontext (Firma/Stelle) zum Dokument, falls verknuepft."""
    enriched = dict(document)
    enriched["doc_type_label"] = _document_type_label(document.get("doc_type"))
    app_id = document.get("linked_application_id")
    if app_id:
        try:
            conn = _db.connect()
            row = conn.execute(
                "SELECT company, position FROM applications WHERE id=?",
                (app_id,),
            ).fetchone()
            if row:
                enriched["app_company"] = row["company"]
                enriched["app_title"] = row["position"]
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug("enrich document %s failed: %s", document.get("id"), exc)
    return enriched


def _format_email_document_text(parsed: dict) -> str:
    """Build readable extracted text for a parsed .eml/.msg document."""
    attachments = ", ".join(
        attachment.get("filename", "")
        for attachment in parsed.get("attachments", [])
        if attachment.get("filename")
    )
    extracted_parts = [
        f"Betreff: {parsed.get('subject', '')}".strip(),
        f"Von: {parsed.get('sender', '')}".strip(),
        f"An: {parsed.get('recipients', '')}".strip(),
        f"Datum: {parsed.get('sent_date', '')}".strip(),
        "",
        parsed.get("body_text", "") or "",
    ]
    return "\n".join(part for part in extracted_parts if part).strip()


def _build_email_document_context(parsed: dict) -> dict:
    """Reuse email helpers for document uploads when a mail file is detected."""
    from .services.email_service import (
        detect_direction,
        detect_email_status,
        extract_meetings_from_email,
        match_email_to_application,
    )

    profile = _db.get_profile() or {}
    parsed_for_matching = dict(parsed)
    direction = detect_direction(parsed.get("sender", ""), profile.get("email", ""))
    parsed_for_matching["_direction"] = direction

    apps = _db.get_applications()
    match_app_id, match_confidence = match_email_to_application(parsed_for_matching, apps)
    detected_status, status_confidence = detect_email_status(
        parsed.get("subject", ""),
        parsed.get("body_text", ""),
    )
    meetings = extract_meetings_from_email(parsed_for_matching)

    matched_application = None
    if match_app_id:
        for app in apps:
            if app.get("id") == match_app_id:
                matched_application = {
                    "id": app["id"],
                    "title": app.get("title"),
                    "company": app.get("company"),
                }
                break

    return {
        "direction": direction,
        "match_application_id": match_app_id,
        "match_confidence": match_confidence,
        "matched_application": matched_application,
        "detected_status": detected_status,
        "status_confidence": status_confidence,
        "meeting_count": len(meetings),
    }


def _extract_document_text(filepath: Path) -> tuple[str, dict | None]:
    """Extract readable text for supported document types."""
    fname = filepath.name.lower()
    email_context = None
    extracted = ""

    if fname.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(str(filepath))
        extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        # #192: OCR-Fallback for scanned PDFs
        if len(extracted.strip()) < 50 and reader.pages:
            try:
                from pdf2image import convert_from_path
                import pytesseract
                images = convert_from_path(str(filepath), dpi=200)
                ocr_parts = []
                for img in images:
                    ocr_parts.append(pytesseract.image_to_string(img, lang="deu+eng"))
                ocr_text = "\n".join(ocr_parts).strip()
                if ocr_text:
                    extracted = ocr_text
                    logger.info("OCR-Fallback erfolgreich für %s (%d Zeichen)", filepath.name, len(ocr_text))
            except ImportError:
                logger.debug("OCR nicht verfügbar (pip install pytesseract pdf2image)")
            except Exception as e:
                logger.warning("OCR-Fallback fehlgeschlagen für %s: %s", filepath.name, e)
    elif fname.endswith(".doc") and not fname.endswith(".docx"):
        # #192: .doc (legacy Word) support via antiword or textract
        import subprocess
        try:
            result = subprocess.run(
                ["antiword", str(filepath)],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode == 0:
                extracted = result.stdout
            else:
                logger.warning(".doc extraction via antiword failed: %s", result.stderr[:200])
        except FileNotFoundError:
            logger.debug(".doc support not available (apt install antiword)")
        except Exception as e:
            logger.warning(".doc extraction failed: %s", e)
    elif fname.endswith(".docx"):
        from docx import Document

        doc = Document(str(filepath))
        extracted = "\n".join(p.text for p in doc.paragraphs)
    elif fname.endswith((".eml", ".msg")):
        from .services.email_service import parse_email_file

        parsed = parse_email_file(str(filepath))
        extracted = _format_email_document_text(parsed)
        email_context = _build_email_document_context(parsed)
    elif fname.endswith((".txt", ".md", ".csv", ".json", ".xml", ".rtf")):
        extracted = filepath.read_text(encoding="utf-8", errors="replace")

    return extracted, email_context


@app.post("/api/documents/auto-mark-templates")
async def api_auto_mark_templates():
    """Auto-detect and mark unlinked CVs/cover letters as templates (#132).

    Marks documents as templates when they have doc_type 'lebenslauf' or
    'anschreiben' AND are not linked to any application or position.
    """
    conn = _db.connect()
    pid = _db.get_active_profile_id()
    result = conn.execute("""
        UPDATE documents SET doc_type =
            CASE
                WHEN doc_type = 'lebenslauf' THEN 'lebenslauf_vorlage'
                WHEN doc_type = 'anschreiben' THEN 'anschreiben_vorlage'
            END
        WHERE doc_type IN ('lebenslauf', 'anschreiben')
        AND linked_application_id IS NULL
        AND linked_position_id IS NULL
        AND (profile_id=? OR profile_id IS NULL)
    """, (pid,))
    conn.commit()
    count = result.rowcount
    return {"status": "ok", "marked": count}


@app.post("/api/document/{doc_id}/reanalyze")
async def api_reanalyze_document(doc_id: str):
    """Reset extraction status so document can be analyzed again."""
    _db.update_document_extraction_status(doc_id, "nicht_extrahiert")
    return {"status": "ok"}


@app.get("/api/document/{doc_id}/extraction")
async def api_get_document_extraction(doc_id: str):
    """Return latest extraction entry for a document in the active profile."""
    profile_id = _db.get_active_profile_id()
    if not profile_id:
        return JSONResponse({"error": "Kein aktives Profil vorhanden"}, status_code=400)

    history = _db.get_extraction_history(profile_id=profile_id, document_id=doc_id)
    if not history:
        return {"extraction": None}

    entry = history[0]
    entry["extracted_fields"] = json.loads(entry.get("extracted_fields") or "{}")
    entry["conflicts"] = json.loads(entry.get("conflicts") or "[]")
    entry["applied_fields"] = json.loads(entry.get("applied_fields") or "{}")
    return {"extraction": entry}


@app.get("/api/analysis-templates")
async def api_list_analysis_templates():
    """Return all available document-analysis templates (#496)."""
    return {"templates": doc_analysis_available_templates()}


@app.get("/api/document/{doc_id}/analysis-prompt")
async def api_get_document_analysis_prompt(doc_id: str, request: Request):
    """Return a Claude-ready prompt that targets exactly one uploaded document.

    Query params:
        template: Optional key to force a specific template (#496).
    """
    profile_id = _db.get_active_profile_id()
    if not profile_id:
        return JSONResponse({"error": "Kein aktives Profil vorhanden"}, status_code=400)

    conn = _db.connect()
    row = conn.execute(
        "SELECT * FROM documents WHERE id=? AND profile_id=?",
        (doc_id, profile_id),
    ).fetchone()
    if not row:
        return JSONResponse({"error": "Dokument nicht gefunden"}, status_code=404)

    document = _enrich_document_for_prompt(dict(row))
    requested_template = request.query_params.get("template")
    if requested_template and requested_template not in DOC_ANALYSIS_TEMPLATES:
        return JSONResponse(
            {"error": f"Template '{requested_template}' nicht bekannt",
             "available_templates": doc_analysis_available_templates()},
            status_code=400,
        )

    result = build_document_analysis_prompt(document, template_key=requested_template)
    return {
        "prompt": result["prompt"],
        "template": result["template"],
        "template_label": result["label"],
        "apply_to_profile": result["apply_to_profile"],
        "available_templates": doc_analysis_available_templates(),
        "document": {
            "id": document.get("id"),
            "filename": document.get("filename"),
            "doc_type": document.get("doc_type"),
            "extraction_status": document.get("extraction_status"),
            "app_company": document.get("app_company"),
            "app_title": document.get("app_title"),
        },
    }


@app.get("/api/workflow-prompt/{workflow_name}")
async def api_get_workflow_prompt(workflow_name: str):
    """Return the resolved workflow instructions instead of a raw slash command."""
    from .tools.workflows import _prompt_registry

    name = str(workflow_name or "").strip().lstrip("/")
    if not name:
        return JSONResponse({"error": "workflow_name ist erforderlich"}, status_code=400)

    prompt_funcs = _prompt_registry(_db)
    if name not in prompt_funcs:
        return JSONResponse({"error": f"Workflow '{name}' nicht gefunden"}, status_code=404)

    return {"workflow": name, "prompt": prompt_funcs[name]()}


@app.put("/api/document/{doc_id}/extraction")
async def api_update_document_extraction(doc_id: str, request: Request):
    """Persist corrected extraction fields and apply supported values to profile."""
    profile = _db.get_profile()
    if not profile:
        return JSONResponse({"error": "Kein aktives Profil vorhanden"}, status_code=400)

    data = await request.json()
    corrected_fields = data.get("corrected_fields")
    if not isinstance(corrected_fields, dict):
        return JSONResponse({"error": "corrected_fields muss ein Objekt sein"}, status_code=400)

    history = _db.get_extraction_history(profile_id=profile["id"], document_id=doc_id)
    if not history:
        return JSONResponse({"error": "Keine Extraktion für dieses Dokument vorhanden"}, status_code=404)

    extraction = history[0]
    conn = _db.connect()
    now = datetime.now().isoformat(timespec="seconds")

    # Persist corrected extraction payload first.
    conn.execute(
        "UPDATE extraction_history SET extracted_fields=?, status=?, completed_at=? WHERE id=? AND profile_id=?",
        (json.dumps(corrected_fields, ensure_ascii=False), "manuell_korrigiert", now, extraction["id"], profile["id"]),
    )
    conn.commit()

    applied = {}

    # Apply corrected personal fields directly to profile.
    personal_data = corrected_fields.get("persoenliche_daten")
    if isinstance(personal_data, dict):
        allowed_fields = [
            "name",
            "email",
            "phone",
            "address",
            "city",
            "plz",
            "country",
            "birthday",
            "nationality",
            "summary",
            "informal_notes",
        ]
        update_data = {}
        for field in allowed_fields:
            if field in personal_data:
                value = personal_data.get(field)
                update_data[field] = value.strip() if isinstance(value, str) else value

        if update_data:
            payload = {key: profile.get(key) for key in allowed_fields}
            payload.update(update_data)
            payload["preferences"] = profile.get("preferences", {})
            _db.save_profile(payload)
            applied["persoenliche_daten"] = sorted(update_data.keys())

    # Apply corrected skills (add missing skills; existing names are de-duplicated in add_skill()).
    skills = corrected_fields.get("skills")
    if isinstance(skills, list):
        existing_skill_names = {
            str(skill.get("name", "")).strip().lower()
            for skill in (_db.get_profile() or {}).get("skills", [])
            if skill.get("name")
        }
        added = 0
        for item in skills:
            if isinstance(item, str):
                skill_name = item.strip()
                skill_data = {"name": skill_name, "category": "fachlich", "level": 3}
            elif isinstance(item, dict):
                skill_name = str(item.get("name", "")).strip()
                skill_data = {
                    "name": skill_name,
                    "category": item.get("category") or "fachlich",
                    "level": item.get("level", 3),
                    "years_experience": item.get("years_experience"),
                    "last_used_year": item.get("last_used_year"),
                }
            else:
                continue

            if not skill_name:
                continue

            key = skill_name.lower()
            if key in existing_skill_names:
                continue
            sid = _db.add_skill(skill_data)
            if sid:
                existing_skill_names.add(key)
                added += 1

        if added:
            applied["skills"] = added

    conn.execute(
        "UPDATE extraction_history SET applied_fields=?, status=?, completed_at=? WHERE id=? AND profile_id=?",
        (
            json.dumps(applied, ensure_ascii=False),
            "manuell_korrigiert",
            now,
            extraction["id"],
            profile["id"],
        ),
    )
    conn.commit()
    _db.update_document_extraction_status(doc_id, "basis_analysiert")

    return {"status": "ok", "extraction_id": extraction["id"], "angewendet": applied}


@app.post("/api/browse-directory")
async def api_browse_directory(request: Request):
    """Browse directories for folder import. Returns subdirectories and file counts."""
    data = await request.json()
    dir_path = data.get("path", "")

    if not dir_path:
        import platform
        home = Path.home()
        if platform.system() == "Windows":
            drives = []
            for letter in "CDEFGHIJ":
                p = Path(f"{letter}:\\")
                if p.exists():
                    drives.append({"name": f"{letter}:\\", "path": str(p), "type": "drive"})
            return {"entries": drives, "current": "", "parent": "",
                    "suggestions": [
                        {"name": "Eigene Dateien", "path": str(home / "Documents")},
                        {"name": "Desktop", "path": str(home / "Desktop")},
                        {"name": "Downloads", "path": str(home / "Downloads")},
                    ]}
        else:
            return {"entries": [
                {"name": "Home", "path": str(home), "type": "dir"},
                {"name": "/tmp", "path": "/tmp", "type": "dir"},
            ], "current": "", "parent": "",
                    "suggestions": [
                        {"name": "Dokumente", "path": str(home / "Documents")},
                        {"name": "Downloads", "path": str(home / "Downloads")},
                    ]}

    folder = Path(dir_path).resolve()
    if _is_blocked_path(dir_path, folder):
        return JSONResponse({"error": "Zugriff auf Systemverzeichnisse nicht erlaubt"}, status_code=403)
    if not folder.exists() or not folder.is_dir():
        return JSONResponse({"error": f"Verzeichnis nicht gefunden: {dir_path}"}, status_code=404)

    entries = []
    supported = {".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".json", ".xml", ".rtf"}
    file_count = 0
    try:
        for item in sorted(folder.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if item.name.startswith("."):
                continue
            if item.is_dir():
                entries.append({"name": item.name, "path": str(item), "type": "dir"})
            elif item.suffix.lower() in supported:
                file_count += 1
                entries.append({"name": item.name, "path": str(item), "type": "file",
                                "size": item.stat().st_size})
    except PermissionError:
        return JSONResponse({"error": "Zugriff verweigert"}, status_code=403)

    parent = str(folder.parent) if folder.parent != folder else ""
    return {
        "entries": entries[:200],
        "current": str(folder),
        "parent": parent,
        "file_count": file_count,
        "total_entries": len(entries),
    }


@app.post("/api/documents/import-folder")
async def api_import_folder(request: Request):
    data = await request.json()
    folder_path = data.get("folder_path", "")
    if not folder_path:
        return JSONResponse({"error": "Kein Ordnerpfad angegeben"}, status_code=400)

    folder = Path(folder_path).resolve()
    # Security: block obvious system paths
    if _is_blocked_path(folder_path, folder):
        return JSONResponse({"error": "Zugriff auf Systemverzeichnisse nicht erlaubt"}, status_code=403)
    if not folder.exists() or not folder.is_dir():
        return JSONResponse({"error": f"Ordner nicht gefunden: {folder_path}"}, status_code=404)

    doc_dir = _get_active_profile_document_dir()

    import_apps = data.get("import_applications", True)
    import_docs = data.get("import_documents", True)
    recursive = data.get("recursive", False)

    files_found = 0
    docs_imported = 0
    apps_found = 0
    skipped_files = 0
    auto_linked_documents = 0
    warnings = []
    supported = (".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".json", ".xml", ".rtf", ".msg", ".eml")

    file_iter = folder.rglob("*") if recursive else folder.glob("*")
    for fpath in file_iter:
        if not fpath.is_file() or fpath.suffix.lower() not in supported:
            continue
        # Skip Word temp files (~$...)
        if fpath.name.startswith("~$"):
            continue
        files_found += 1

        extracted = ""
        email_context = None
        fname = fpath.name.lower()
        try:
            extracted, email_context = _extract_document_text(fpath)
        except ImportError as exc:
            warnings.append(f"{fpath.name}: {exc}")
            skipped_files += 1
            logger.warning("Import: E-Mail-Parsing nicht verfuegbar fuer %s: %s", fpath.name, exc)
            continue
        except Exception as e:
            if fname.endswith((".msg", ".eml")):
                warnings.append(f"{fpath.name}: E-Mail konnte nicht gelesen werden ({e})")
                skipped_files += 1
                logger.warning("Import: E-Mail-Parsing fehlgeschlagen fuer %s: %s", fpath.name, e)
                continue
            logger.warning("Import: Text extraction failed for %s: %s", fpath.name, e)

        # Determine doc type from filename (use shared _detect_doc_type)
        doc_type = _detect_doc_type(fpath.name, extracted) or "sonstiges"

        if import_docs:
            # Copy file to doc_dir
            import shutil
            dest = doc_dir / fpath.name
            if not dest.exists():
                try:
                    shutil.copy2(str(fpath), str(dest))
                except Exception:
                    dest = fpath  # Use original path

            did = _db.add_document({
                "filename": fpath.name,
                "filepath": str(dest),
                "doc_type": doc_type,
                "extracted_text": extracted,
                "linked_application_id": (email_context or {}).get("match_application_id"),
            })
            if email_context and email_context.get("match_application_id"):
                try:
                    _db.link_document_to_application(did, email_context["match_application_id"])
                    auto_linked_documents += 1
                except Exception as exc:
                    logger.warning("Import: Dokument %s konnte nicht mit Bewerbung verknuepft werden: %s", fpath.name, exc)
            if fname.endswith((".msg", ".eml")) and extracted.strip():
                _db.update_document_extraction_status(did, "basis_analysiert")
            docs_imported += 1

        # Try to detect applications from folder structure
        if import_apps and doc_type == "anschreiben":
            parent = fpath.parent.name
            if parent and parent != folder.name:
                _db.add_application({
                    "title": parent,
                    "company": parent,
                    "status": "beworben",
                    "notes": f"Importiert aus: {fpath}",
                })
                apps_found += 1

    return {
        "status": "ok",
        "files_found": files_found,
        "documents_imported": docs_imported,
        "applications_found": apps_found,
        "skipped_files": skipped_files,
        "auto_linked_documents": auto_linked_documents,
        "warning_count": len(warnings),
        "warnings": warnings,
    }


@app.get("/api/cv/generate")
async def api_generate_cv(format: str = "text"):
    """Generate a Master-CV from profile data."""
    profile = _db.get_profile()
    if not profile:
        return JSONResponse({"error": "Kein Profil vorhanden"}, status_code=404)

    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"LEBENSLAUF")
    lines.append(f"{'='*60}")
    lines.append("")

    # Personal data
    lines.append("PERSOENLICHE DATEN")
    lines.append(f"  Name:     {profile.get('name', '')}")
    if profile.get('address'): lines.append(f"  Adresse:  {profile['address']}")
    if profile.get('plz') or profile.get('city'):
        plz = profile.get('plz') or ''
        city = profile.get('city') or ''
        lines.append(f"  Ort:      {f'{plz} ' if plz else ''}{city}".rstrip())
    if profile.get('phone'): lines.append(f"  Telefon:  {profile['phone']}")
    if profile.get('email'): lines.append(f"  E-Mail:   {profile['email']}")
    lines.append("")

    # Summary
    if profile.get('summary'):
        lines.append("PROFIL / ZUSAMMENFASSUNG")
        lines.append(f"  {profile['summary']}")
        lines.append("")

    # Skills grouped by category
    skills = profile.get('skills', [])
    if skills:
        lines.append("KOMPETENZEN")
        cats = {}
        for s in skills:
            cat = s.get('category', 'sonstiges')
            cats.setdefault(cat, []).append(s)
        cat_labels = {'fachlich': 'Fachlich', 'tool': 'Tools/Software', 'methodisch': 'Methodisch',
                      'soft_skill': 'Soft Skills', 'sprache': 'Sprachen'}
        for cat, items in cats.items():
            skill_strs = []
            for s in items:
                entry = s['name']
                if s.get('years_experience'):
                    entry += f" ({s['years_experience']}J)"
                skill_strs.append(entry)
            lines.append(f"  {cat_labels.get(cat, cat)}: {', '.join(skill_strs)}")
        lines.append("")

    # Work experience
    positions = profile.get('positions', [])
    if positions:
        lines.append("BERUFSERFAHRUNG")
        for pos in positions:
            period = f"{pos.get('start_date', '?')} - {'heute' if pos.get('is_current') else pos.get('end_date', '?')}"
            lines.append(f"  {pos.get('title', '')} | {pos.get('company', '')} | {period}")
            if pos.get('employment_type'):
                lines.append(f"    Typ: {pos['employment_type']}")
            if pos.get('industry'):
                lines.append(f"    Branche: {pos['industry']}")
            if pos.get('tasks'):
                lines.append(f"    Aufgaben: {pos['tasks']}")
            if pos.get('achievements'):
                lines.append(f"    Erfolge: {pos['achievements']}")
            if pos.get('technologies'):
                lines.append(f"    Technologien: {pos['technologies']}")

            # Projects
            for pr in pos.get('projects', []):
                lines.append(f"    --- Projekt: {pr.get('name', '')} ---")
                if pr.get('role'): lines.append(f"      Rolle: {pr['role']}")
                if pr.get('duration'): lines.append(f"      Dauer: {pr['duration']}")
                if pr.get('description'): lines.append(f"      {pr['description']}")
                if pr.get('situation'): lines.append(f"      S: {pr['situation']}")
                if pr.get('task'): lines.append(f"      T: {pr['task']}")
                if pr.get('action'): lines.append(f"      A: {pr['action']}")
                if pr.get('result'): lines.append(f"      R: {pr['result']}")
                if pr.get('technologies'): lines.append(f"      Tech: {pr['technologies']}")
            lines.append("")

    # Education
    education = profile.get('education', [])
    if education:
        lines.append("AUSBILDUNG")
        for ed in education:
            start = ed.get('start_date') or ''
            end = ed.get('end_date') or ''
            period = f" | {start} - {end}" if start or end else ""
            lines.append(f"  {ed.get('degree', '')} {ed.get('field_of_study', '')} | {ed.get('institution', '')}{period}")
            if ed.get('grade'): lines.append(f"    Note: {ed['grade']}")
            if ed.get('description'): lines.append(f"    {ed['description']}")
        lines.append("")

    # Informal notes
    if profile.get('informal_notes'):
        lines.append("PERSOENLICHE NOTIZEN (nicht im CV)")
        lines.append(f"  {profile['informal_notes']}")

    cv_text = "\n".join(lines)
    return {"cv_text": cv_text, "line_count": len(lines)}


@app.get("/api/application/{app_id}/timeline")
async def api_application_timeline(app_id: str):
    """Get full event timeline for an application with job details and documents."""
    profile_id = _get_active_profile_id()
    app_row = _get_application_row_for_active_profile(app_id)
    if not profile_id or not app_row:
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    conn = _db.connect()
    events = [dict(r) for r in conn.execute(
        "SELECT * FROM application_events WHERE application_id = ? ORDER BY event_date DESC",
        (app_id,)
    ).fetchall()]
    application = _db._serialize_application_row(app_row) if hasattr(_db, '_serialize_application_row') else dict(app_row)

    # Enrich with job details if linked
    job = None
    if application.get("job_hash"):
        job = _db.get_job(application["job_hash"])

    # Get linked documents
    documents = _db.get_documents_for_application(app_id, profile_id=profile_id)

    # #313: Emails und Meetings als Timeline-Einträge einfügen
    emails = _db.get_emails_for_application(app_id, profile_id=profile_id) if hasattr(_db, 'get_emails_for_application') else []
    meetings = _db.get_meetings_for_application(app_id, profile_id=profile_id) if hasattr(_db, 'get_meetings_for_application') else []

    # Unified timeline: events + emails + meetings chronologisch
    unified_timeline = list(events)
    for email in emails:
        unified_timeline.append({
            "id": email.get("id"),
            "event_type": "email",
            "event_date": email.get("received_at") or email.get("created_at", ""),
            "description": f"E-Mail: {email.get('subject', '(Kein Betreff)')}",
            "details": email.get("sender", ""),
            "_source": "email",
            "_email_id": email.get("id"),
        })
    for meeting in meetings:
        unified_timeline.append({
            "id": meeting.get("id"),
            "event_type": "meeting",
            "event_date": meeting.get("meeting_date", ""),
            "description": f"Termin: {meeting.get('title', 'Termin')}",
            "details": f"{meeting.get('location', '')} {meeting.get('platform', '')}".strip(),
            "_source": "meeting",
            "_meeting_id": meeting.get("id"),
        })
    # Chronologisch sortieren (neueste zuerst)
    unified_timeline.sort(key=lambda e: e.get("event_date", ""), reverse=True)

    return {
        "application": application,
        "events": events,
        "unified_timeline": unified_timeline,
        "job": job,
        "documents": documents,
        "emails": emails,
        "meetings": meetings,
    }


def _build_application_print_html(app_id: str) -> str | None:
    """Baut das HTML-Protokoll fuer eine Bewerbung (#313 / beta.28).

    Liefert None, wenn die Bewerbung nicht zum aktiven Profil gehoert.
    Wird genutzt von:
      - /api/application/{id}/timeline/print (HTML-Anzeige, beta.28)
      - /api/application/{id}/export.zip (ZIP-Inhalt, beta.31)
    """
    from html import escape as _esc
    profile_id = _get_active_profile_id()
    app_row = _get_application_row_for_active_profile(app_id)
    if not profile_id or not app_row:
        return None
    return _render_application_print_html(app_id, app_row, profile_id, _esc)


def _render_application_print_html(app_id, app_row, profile_id, _esc):
    """Eigentlicher HTML-Renderer (beta.28 Protokoll, refaktoriert beta.31).

    Wurde aus api_application_timeline_print extrahiert, damit der ZIP-
    Endpoint denselben Code wiederverwenden kann.
    """
    conn = _db.connect()
    app_data = dict(app_row)

    events = [dict(r) for r in conn.execute(
        "SELECT * FROM application_events WHERE application_id = ? ORDER BY event_date ASC",
        (app_id,)
    ).fetchall()]
    emails = _db.get_emails_for_application(app_id, profile_id=profile_id) if hasattr(_db, 'get_emails_for_application') else []
    meetings = _db.get_meetings_for_application(app_id, profile_id=profile_id) if hasattr(_db, 'get_meetings_for_application') else []
    documents = _db.get_documents_for_application(app_id, profile_id=profile_id)
    job = None
    if app_data.get("job_hash"):
        job_row = conn.execute(
            "SELECT * FROM jobs WHERE hash=?", (app_data["job_hash"],)
        ).fetchone()
        if job_row:
            job = dict(job_row)

    # ── Statistik-Block ─────────────────────────────────────────────
    from datetime import datetime as _dt
    today = _dt.now()

    def _parse_date(s):
        if not s:
            return None
        try:
            return _dt.fromisoformat(s.replace(" ", "T")[:19])
        except Exception:
            try:
                return _dt.fromisoformat(s[:10])
            except Exception:
                return None

    applied_dt = _parse_date(app_data.get("applied_at"))
    days_since_applied = (today - applied_dt).days if applied_dt else None

    # Reaktionszeit: erste eingehende E-Mail nach Bewerbung oder erstes
    # Status-Wechsel-Event (eingangsbestaetigung/interview).
    first_response_dt = None
    for em in sorted(emails, key=lambda x: x.get("received_at") or x.get("sent_date") or ""):
        if em.get("direction") == "eingang":
            d = _parse_date(em.get("received_at") or em.get("sent_date"))
            if d and (not applied_dt or d >= applied_dt):
                first_response_dt = d
                break
    if not first_response_dt:
        for ev in events:
            if ev.get("status") in ("eingangsbestaetigung", "interview", "zweitgespraech",
                                     "abgelehnt", "angebot"):
                d = _parse_date(ev.get("event_date"))
                if d and (not applied_dt or d >= applied_dt):
                    first_response_dt = d
                    break
    response_days = (first_response_dt - applied_dt).days if (first_response_dt and applied_dt) else None

    # Letzte Aktivitaet
    last_activity_candidates = []
    for ev in events:
        d = _parse_date(ev.get("event_date"))
        if d: last_activity_candidates.append(d)
    for em in emails:
        d = _parse_date(em.get("received_at") or em.get("sent_date"))
        if d: last_activity_candidates.append(d)
    for m in meetings:
        d = _parse_date(m.get("meeting_date"))
        if d: last_activity_candidates.append(d)
    last_activity = max(last_activity_candidates) if last_activity_candidates else None
    days_since_activity = (today - last_activity).days if last_activity else None

    # Status-Historie nur Status-Wechsel-Events
    status_changes = [
        e for e in events
        if e.get("status") and e.get("status") not in ("notiz", "")
    ]
    # E-Mail-Direction-Aufschluesselung
    emails_in = [em for em in emails if em.get("direction") == "eingang"]
    emails_out = [em for em in emails if em.get("direction") == "ausgang"]
    # Notizen separat
    notes = [e for e in events if e.get("status") == "notiz" or (e.get("notes") and not e.get("status"))]

    # Build unified chronological entries (kompletter Zeitstrahl)
    entries = []
    for e in events:
        entries.append({
            "date": e.get("event_date", ""),
            "type": "Status" if e.get("status") and e.get("status") != "notiz" else "Notiz",
            "text": (f"{e.get('status', '')}: " if e.get("status") and e.get("status") != "notiz" else "") + (e.get("notes") or e.get("description") or ""),
        })
    for em in emails:
        direction = "Eingehend" if em.get("direction") == "eingang" else "Ausgehend"
        entries.append({
            "date": em.get("received_at") or em.get("sent_date", ""),
            "type": f"E-Mail ({direction})",
            "text": f"{em.get('subject', '(Kein Betreff)')} — {em.get('sender', '') if em.get('direction')=='eingang' else em.get('recipients', '')}",
        })
    for m in meetings:
        entries.append({
            "date": m.get("meeting_date", ""),
            "type": "Termin",
            "text": f"{m.get('title', 'Termin')}" + (f" ({m.get('platform', '')})" if m.get('platform') else ""),
        })
    entries.sort(key=lambda x: x["date"])

    # ── HTML rendern ────────────────────────────────────────────────
    title = _esc(str(app_data.get("title", "Bewerbung")))
    company = _esc(str(app_data.get("company", "")))
    status = _esc(str(app_data.get("status", "")))
    applied_at = app_data.get("applied_at", "")
    url = _esc(str(app_data.get("url") or (job.get("url") if job else "") or ""))

    def _stat(label, value, hint=None):
        return f"""<div class="stat"><div class="stat-label">{_esc(label)}</div><div class="stat-value">{_esc(str(value))}</div>{f'<div class="stat-hint">{_esc(hint)}</div>' if hint else ''}</div>"""

    stats_blocks = [
        _stat("Bewerbung gesendet", applied_at[:10] if applied_at else "—",
              f"vor {days_since_applied} Tagen" if days_since_applied is not None else None),
        _stat("Letzte Aktivitaet", last_activity.strftime("%d.%m.%Y") if last_activity else "—",
              f"vor {days_since_activity} Tagen" if days_since_activity is not None else None),
        _stat("Reaktionszeit", f"{response_days} Tage" if response_days is not None else "Noch keine Reaktion",
              first_response_dt.strftime("%d.%m.%Y") if first_response_dt else None),
        _stat("Aktueller Status", status, None),
        _stat("Status-Wechsel", str(len(status_changes))),
        _stat("E-Mails", f"{len(emails)} ({len(emails_in)} ein, {len(emails_out)} aus)"),
        _stat("Termine", str(len(meetings))),
        _stat("Dokumente", str(len(documents))),
        _stat("Notizen", str(len(notes))),
        _stat("Timeline-Eintraege", str(len(entries))),
    ]

    stats_html = '<div class="stat-grid">' + "".join(stats_blocks) + "</div>"

    # Status-Historie
    history_html = ""
    if status_changes:
        history_html = "<h2>Status-Historie</h2><ol class='status-history'>"
        for ev in status_changes:
            d = ev.get("event_date", "")[:10] or "—"
            st = _esc(str(ev.get("status", "")))
            note = _esc(str(ev.get("notes") or ev.get("description") or ""))
            history_html += f"<li><strong>{d}</strong> — <span class='badge'>{st}</span>"
            if note:
                history_html += f"<div class='note-text'>{note}</div>"
            history_html += "</li>"
        history_html += "</ol>"

    # Chronologie (komplett)
    rows_html = ""
    for e in entries:
        rows_html += f"<tr><td class='date-col'>{_esc(e['date'][:10] if e['date'] else '-')}</td><td><strong>{_esc(e['type'])}</strong></td><td>{_esc(e['text'])}</td></tr>\n"

    # E-Mails-Block
    emails_html = ""
    if emails:
        emails_html = "<h2>E-Mail-Korrespondenz</h2><table><tr><th>Datum</th><th>Richtung</th><th>Von / An</th><th>Betreff</th></tr>"
        for em in sorted(emails, key=lambda x: x.get("received_at") or x.get("sent_date") or ""):
            d = (em.get("received_at") or em.get("sent_date") or "")[:10]
            direction = "Eingehend" if em.get("direction") == "eingang" else "Ausgehend"
            partner = em.get("sender") if em.get("direction") == "eingang" else em.get("recipients")
            emails_html += f"<tr><td class='date-col'>{_esc(d)}</td><td>{_esc(direction)}</td><td>{_esc(partner or '')}</td><td>{_esc(em.get('subject') or '(Kein Betreff)')}</td></tr>"
        emails_html += "</table>"

    # Termine-Block
    meetings_html = ""
    if meetings:
        meetings_html = "<h2>Termine</h2><table><tr><th>Datum</th><th>Titel</th><th>Plattform</th></tr>"
        for m in sorted(meetings, key=lambda x: x.get("meeting_date") or ""):
            d = (m.get("meeting_date") or "")[:10]
            meetings_html += f"<tr><td class='date-col'>{_esc(d)}</td><td>{_esc(m.get('title') or 'Termin')}</td><td>{_esc(m.get('platform') or '—')}</td></tr>"
        meetings_html += "</table>"

    # Dokumente-Block
    docs_html = ""
    if documents:
        docs_html = "<h2>Verknuepfte Dokumente</h2><table><tr><th>Datei</th><th>Typ</th><th>Hinzugefuegt</th></tr>"
        for d in documents:
            created = (d.get("created_at") or "")[:10]
            docs_html += f"<tr><td>{_esc(d.get('filename') or '')}</td><td>{_esc(d.get('doc_type') or '—')}</td><td class='date-col'>{_esc(created)}</td></tr>"
        docs_html += "</table>"

    # Notizen-Block
    notes_html = ""
    if notes:
        notes_html = "<h2>Notizen</h2><div class='notes'>"
        for n in notes:
            d = (n.get("event_date") or "")[:10]
            text = _esc(n.get("notes") or n.get("description") or "")
            notes_html += f"<div class='note'><div class='note-date'>{d}</div><div class='note-text'>{text}</div></div>"
        notes_html += "</div>"

    # Stelle-Block
    job_html = ""
    if job or url:
        job_html = "<h2>Stelle</h2><dl class='kv'>"
        if job and job.get("location"):
            job_html += f"<dt>Standort</dt><dd>{_esc(job['location'])}</dd>"
        if job and job.get("source"):
            job_html += f"<dt>Quelle</dt><dd>{_esc(job['source'])}</dd>"
        if job and job.get("salary_min"):
            sal = f"{job.get('salary_min')}{' – ' + str(job.get('salary_max')) if job.get('salary_max') else ''}"
            job_html += f"<dt>Gehalt</dt><dd>{_esc(sal)}</dd>"
        if url:
            job_html += f"<dt>Link</dt><dd><a href='{url}'>{url[:80]}</a></dd>"
        contact_partner = app_data.get("ansprechpartner") or ""
        contact_email = app_data.get("kontakt_email") or ""
        if contact_partner or contact_email:
            job_html += f"<dt>Ansprechpartner</dt><dd>{_esc(contact_partner)}{' — <a href=\"mailto:' + _esc(contact_email) + '\">' + _esc(contact_email) + '</a>' if contact_email else ''}</dd>"
        if app_data.get("bewerbungsart"):
            job_html += f"<dt>Bewerbungsart</dt><dd>{_esc(app_data['bewerbungsart'])}</dd>"
        if app_data.get("lebenslauf_variante"):
            job_html += f"<dt>Lebenslauf</dt><dd>{_esc(app_data['lebenslauf_variante'])}</dd>"
        job_html += "</dl>"

    html = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<title>Bewerbungsprotokoll — {title} bei {company}</title>
<style>
* {{ box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       max-width: 880px; margin: 0 auto; padding: 2rem; color: #2a2a2a; line-height: 1.45; }}
header {{ border-bottom: 3px solid #2c5282; padding-bottom: 1rem; margin-bottom: 1.2rem; }}
h1 {{ font-size: 1.55rem; margin: 0 0 0.3rem; color: #1a365d; }}
h2 {{ font-size: 1.1rem; margin-top: 1.8rem; margin-bottom: 0.6rem;
      border-bottom: 1px solid #cbd5e0; padding-bottom: 0.25rem; color: #2c5282; }}
.subtitle {{ color: #4a5568; font-size: 1rem; }}
.meta {{ color: #718096; font-size: 0.85rem; margin-top: 0.4rem; }}
.stat-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
              gap: 0.6rem; margin: 0.8rem 0 1.2rem; }}
.stat {{ background: #f7fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 0.6rem 0.8rem; }}
.stat-label {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.05em;
               color: #718096; margin-bottom: 0.2rem; }}
.stat-value {{ font-size: 1.05rem; font-weight: 600; color: #2d3748; }}
.stat-hint {{ font-size: 0.72rem; color: #a0aec0; margin-top: 0.15rem; }}
table {{ width: 100%; border-collapse: collapse; font-size: 0.85rem; margin-top: 0.4rem; }}
th, td {{ text-align: left; padding: 0.5rem 0.7rem; border-bottom: 1px solid #edf2f7; vertical-align: top; }}
th {{ background: #edf2f7; font-weight: 600; color: #2d3748; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }}
.date-col {{ white-space: nowrap; color: #718096; font-variant-numeric: tabular-nums; width: 1%; }}
ol.status-history {{ list-style: none; padding-left: 0; counter-reset: step; }}
ol.status-history li {{ counter-increment: step; padding: 0.5rem 0; border-bottom: 1px solid #edf2f7; }}
ol.status-history li::before {{ content: counter(step); display: inline-block;
       width: 1.6rem; height: 1.6rem; line-height: 1.6rem; text-align: center;
       background: #2c5282; color: white; border-radius: 50%; margin-right: 0.6rem;
       font-size: 0.75rem; font-weight: 600; }}
.badge {{ display: inline-block; padding: 0.15rem 0.5rem; background: #ebf8ff; color: #2c5282;
          border-radius: 4px; font-size: 0.78rem; font-weight: 500; }}
.note-text {{ margin-top: 0.3rem; margin-left: 2.2rem; color: #4a5568; font-style: italic; font-size: 0.85rem; }}
.notes .note {{ background: #fffaf0; border-left: 3px solid #ed8936; padding: 0.5rem 0.8rem; margin-bottom: 0.6rem; border-radius: 0 4px 4px 0; }}
.notes .note-date {{ font-size: 0.75rem; color: #a0aec0; margin-bottom: 0.2rem; font-variant-numeric: tabular-nums; }}
.notes .note-text {{ margin: 0; color: #2d3748; font-style: normal; font-size: 0.88rem; }}
dl.kv {{ display: grid; grid-template-columns: 9rem 1fr; gap: 0.4rem 1rem; margin: 0.5rem 0; }}
dl.kv dt {{ color: #718096; font-size: 0.85rem; }}
dl.kv dd {{ margin: 0; color: #2d3748; font-size: 0.9rem; }}
a {{ color: #3182ce; }}
.footer {{ margin-top: 2.5rem; font-size: 0.72rem; color: #a0aec0;
           border-top: 1px solid #edf2f7; padding-top: 0.6rem; text-align: center; }}
@media print {{
  body {{ padding: 1cm; max-width: none; }}
  h2 {{ page-break-after: avoid; }}
  table, dl, .stat-grid {{ page-break-inside: avoid; }}
  .stat-grid {{ grid-template-columns: repeat(5, 1fr); }}
}}
</style>
</head>
<body>
<header>
  <h1>Bewerbungsprotokoll</h1>
  <p class="subtitle"><strong>{title}</strong> bei {company}</p>
  <p class="meta">ID {_esc(app_id[:8])} | Erstellt {datetime.now().strftime('%d.%m.%Y %H:%M')}</p>
</header>

<h2>Kennzahlen</h2>
{stats_html}

{job_html}

{history_html}

{emails_html}

{meetings_html}

{notes_html}

{docs_html}

<h2>Vollstaendige Chronologie ({len(entries)} Eintraege)</h2>
<table>
<tr><th>Datum</th><th>Typ</th><th>Beschreibung</th></tr>
{rows_html if rows_html else '<tr><td colspan="3" style="text-align:center;color:#a0aec0;">Keine Eintraege.</td></tr>'}
</table>

<div class="footer">Erstellt von PBP Bewerbungs-Assistent — {datetime.now().strftime('%d.%m.%Y %H:%M')}</div>
</body>
</html>"""

    return html


@app.get("/api/application/{app_id}/timeline/print")
async def api_application_timeline_print(app_id: str):
    """Druckbare HTML-Seite des Bewerbungsprotokolls (#313 / beta.28)."""
    html = _build_application_print_html(app_id)
    if html is None:
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    from starlette.responses import HTMLResponse
    return HTMLResponse(content=html)


@app.get("/api/application/{app_id}/export.zip")
async def api_application_export_zip(
    app_id: str,
    dokumente: int = 1,
    mails: int = 1,
    pdf: int = 0,
):
    """Vollstaendiger Bewerbungs-Export als ZIP (#474 / beta.31).

    Ersetzt das urspruenglich angedachte "Ordner pro Bewerbung"-Feature
    aus #474: statt das Dateisystem zu reorganisieren, packt PBP auf
    Knopfdruck alles zusammen, was zu einer Bewerbung gehoert:

    Phase 1 (immer dabei):
      - 00_INHALT.md          — Uebersicht des ZIP-Inhalts
      - 01_Bewerbungsprotokoll.html
      - 02_Stellenanzeige.html
      - 03_Notizen.md
      - 04_Termine.ics        — importierbar in Outlook/Thunderbird/Apple Calendar
      - 05_Mail-Verlauf.md    — strukturierte Zusammenfassung

    Phase 2 (optional via Query-Params):
      - dokumente/<file>      — Original-Files (default an, ?dokumente=0 abschalten)
      - mails/<file>          — Original .eml/.msg falls vorhanden (default an)
      - 01_Bewerbungsprotokoll.pdf — Playwright-PDF zusaetzlich (?pdf=1)
    """
    import io, zipfile, re as _re
    from html import escape as _esc
    from datetime import datetime as _dt
    from pathlib import Path as _Path

    profile_id = _get_active_profile_id()
    app_row = _get_application_row_for_active_profile(app_id)
    if not profile_id or not app_row:
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    app_data = dict(app_row)

    # Daten zusammensammeln
    conn = _db.connect()
    events = [dict(r) for r in conn.execute(
        "SELECT * FROM application_events WHERE application_id=? ORDER BY event_date ASC",
        (app_id,)
    ).fetchall()]
    emails = (
        _db.get_emails_for_application(app_id, profile_id=profile_id)
        if hasattr(_db, "get_emails_for_application") else []
    )
    meetings = (
        _db.get_meetings_for_application(app_id, profile_id=profile_id)
        if hasattr(_db, "get_meetings_for_application") else []
    )
    documents = _db.get_documents_for_application(app_id, profile_id=profile_id)
    job = None
    if app_data.get("job_hash"):
        row = conn.execute("SELECT * FROM jobs WHERE hash=?", (app_data["job_hash"],)).fetchone()
        if row:
            job = dict(row)

    # Slug fuer Datei-Namen
    def _slug(s, maxlen=40):
        s = (s or "").strip()
        s = _re.sub(r"[^\w\s-]", "", s, flags=_re.U)
        s = _re.sub(r"\s+", "-", s)
        return s[:maxlen] or "bewerbung"

    applied_at = (app_data.get("applied_at") or "")[:10]
    folder_slug = f"{applied_at}_{_slug(app_data.get('company'))}_{_slug(app_data.get('title'))}__{app_id[:8]}"
    folder_slug = folder_slug.strip("_-")

    # 01: Bewerbungsprotokoll-HTML
    bericht_html = _render_application_print_html(app_id, app_row, profile_id, _esc)

    # 02: Stellenanzeige als HTML
    stelle_html = _render_stelle_html(app_data, job, _esc)

    # 03: Notizen als Markdown
    notizen_md = _render_notes_md(app_data, events)

    # 04: Termine als ICS
    termine_ics = _render_termine_ics(app_data, meetings)

    # 05: Mail-Verlauf als Markdown
    mails_md = _render_mails_md(app_data, emails)

    # 00: Inhalt-Uebersicht
    inhalt_md = _render_inhalt_md(
        app_data, len(events), len(emails), len(meetings), len(documents),
        include_dokumente=bool(dokumente), include_mails=bool(mails),
        include_pdf=bool(pdf),
    )

    # ZIP zusammenbauen
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("00_INHALT.md", inhalt_md)
        zf.writestr("01_Bewerbungsprotokoll.html", bericht_html)
        zf.writestr("02_Stellenanzeige.html", stelle_html)
        zf.writestr("03_Notizen.md", notizen_md)
        zf.writestr("04_Termine.ics", termine_ics)
        zf.writestr("05_Mail-Verlauf.md", mails_md)

        # Phase 2: PDF via Playwright, falls angefordert
        if pdf:
            try:
                pdf_bytes = _render_html_to_pdf(bericht_html)
                if pdf_bytes:
                    zf.writestr("01_Bewerbungsprotokoll.pdf", pdf_bytes)
            except Exception as e:
                logger.warning("ZIP-Export: PDF-Konvertierung fehlgeschlagen: %s", e)

        # Phase 2: Original-Dokumente
        if dokumente:
            for d in documents:
                fp = d.get("filepath")
                if not fp:
                    continue
                src = _Path(fp)
                if not src.exists():
                    continue
                target = f"dokumente/{src.name}"
                try:
                    zf.write(src, target)
                except Exception as e:
                    logger.warning("ZIP-Export: Dokument %s konnte nicht gepackt werden: %s", src.name, e)

        # Phase 2: Original-Mail-Files
        if mails:
            for em in emails:
                fp = em.get("filepath")
                if not fp:
                    continue
                src = _Path(fp)
                if not src.exists():
                    continue
                target = f"mails/{src.name}"
                try:
                    zf.write(src, target)
                except Exception as e:
                    logger.warning("ZIP-Export: Mail %s konnte nicht gepackt werden: %s", src.name, e)

    buf.seek(0)
    from starlette.responses import StreamingResponse as _Stream
    filename = f"{folder_slug}.zip"
    return _Stream(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Helper fuer Bewerbungs-ZIP-Export (#474 / beta.31) ──────────────────

def _render_stelle_html(app_data: dict, job: dict | None, _esc) -> str:
    """Stellenanzeige als HTML (im ZIP)."""
    title = _esc(str(app_data.get("title", "")))
    company = _esc(str(app_data.get("company", "")))
    url = _esc(str(app_data.get("url") or (job and job.get("url")) or ""))
    location = _esc(str((job and job.get("location")) or ""))
    description = (job and job.get("description")) or app_data.get("notes") or ""
    description_html = _esc(description).replace("\n", "<br>\n")
    return f"""<!DOCTYPE html>
<html lang="de"><head><meta charset="utf-8"><title>Stelle — {title} bei {company}</title>
<style>body{{font-family:-apple-system,Segoe UI,sans-serif;max-width:800px;margin:2rem auto;padding:1rem;line-height:1.5}}
h1{{font-size:1.5rem;margin-bottom:0.3rem}}.meta{{color:#666;margin-bottom:1.5rem}}</style></head>
<body><h1>{title}</h1><p class="meta"><strong>{company}</strong>{f" — {location}" if location else ""}
{f'<br><a href="{url}">{url}</a>' if url else ''}</p>
<section>{description_html or '<em>Keine Stellenbeschreibung gespeichert.</em>'}</section></body></html>"""


def _render_notes_md(app_data: dict, events: list) -> str:
    """Notizen als Markdown."""
    lines = [
        f"# Notizen — {app_data.get('title', '')} bei {app_data.get('company', '')}",
        "",
        f"Bewerbungs-ID: `{app_data.get('id', '')[:8]}`",
        "",
    ]
    notes = [e for e in events if e.get("status") == "notiz" or (e.get("notes") and not e.get("status"))]
    if not notes:
        lines.append("_Keine Notizen vorhanden._")
        return "\n".join(lines)
    for n in notes:
        date = (n.get("event_date") or "")[:10]
        text = n.get("notes") or n.get("description") or ""
        lines.append(f"## {date}")
        lines.append("")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def _render_mails_md(app_data: dict, emails: list) -> str:
    """Mail-Verlauf als strukturierter Markdown-Output."""
    lines = [
        f"# Mail-Verlauf — {app_data.get('title', '')} bei {app_data.get('company', '')}",
        "",
        f"Insgesamt {len(emails)} E-Mails.",
        "",
    ]
    if not emails:
        lines.append("_Keine E-Mails verknuepft._")
        return "\n".join(lines)
    for em in sorted(emails, key=lambda x: x.get("received_at") or x.get("sent_date") or ""):
        date = (em.get("received_at") or em.get("sent_date") or "")[:10]
        direction = "Eingehend" if em.get("direction") == "eingang" else "Ausgehend"
        partner = em.get("sender") if em.get("direction") == "eingang" else em.get("recipients")
        lines.append(f"## {date} — {direction}")
        lines.append("")
        lines.append(f"**Von/An:** {partner or '—'}")
        lines.append(f"**Betreff:** {em.get('subject') or '(Kein Betreff)'}")
        lines.append("")
        body = (em.get("body_text") or "").strip()
        if body:
            lines.append("```")
            lines.append(body[:3000] + ("..." if len(body) > 3000 else ""))
            lines.append("```")
        lines.append("")
    return "\n".join(lines)


def _render_termine_ics(app_data: dict, meetings: list) -> str:
    """Termine als ICS (RFC 5545 minimal). Importierbar in jeden Kalender."""
    from datetime import datetime as _dt
    def _ics_dt(s):
        if not s:
            return None
        try:
            d = _dt.fromisoformat(s.replace(" ", "T")[:19])
            return d.strftime("%Y%m%dT%H%M%S")
        except Exception:
            try:
                d = _dt.fromisoformat(s[:10])
                return d.strftime("%Y%m%dT000000")
            except Exception:
                return None

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PBP//Bewerbungs-Assistent//DE",
        f"X-WR-CALNAME:{app_data.get('title', '')} bei {app_data.get('company', '')}",
    ]
    for i, m in enumerate(meetings):
        start = _ics_dt(m.get("meeting_date"))
        end = _ics_dt(m.get("meeting_end")) or start
        if not start:
            continue
        uid = f"{app_data.get('id', 'app')[:8]}-meeting-{i}@pbp"
        title = (m.get("title") or "Termin").replace("\n", " ")
        location = (m.get("location") or m.get("platform") or "").replace("\n", " ")
        lines += [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART:{start}",
            f"DTEND:{end}",
            f"SUMMARY:{title}",
            f"LOCATION:{location}" if location else "",
            f"DESCRIPTION:Bewerbung {app_data.get('title', '')} bei {app_data.get('company', '')}",
            "END:VEVENT",
        ]
    lines.append("END:VCALENDAR")
    # ICS will lines no longer than 75 octets; we keep it simple here.
    return "\r\n".join(line for line in lines if line)


def _render_inhalt_md(app_data, n_events, n_emails, n_meetings, n_dokumente,
                      include_dokumente=True, include_mails=True, include_pdf=False) -> str:
    """ZIP-Inhalt-Uebersicht als Markdown."""
    from datetime import datetime as _dt
    lines = [
        f"# Bewerbungs-Export — {app_data.get('title', '')} bei {app_data.get('company', '')}",
        "",
        f"Exportiert am: {_dt.now().strftime('%d.%m.%Y %H:%M')}",
        f"Bewerbungs-ID: `{app_data.get('id', '')}`",
        f"Status: **{app_data.get('status', '')}**",
        f"Beworben am: {app_data.get('applied_at', '')[:10] or '—'}",
        "",
        "## Inhalt dieses ZIP",
        "",
        "| Datei | Beschreibung |",
        "|---|---|",
        "| `00_INHALT.md` | Diese Uebersicht |",
        "| `01_Bewerbungsprotokoll.html` | Vollstaendiges Bewerbungs-Dossier (in Browser oeffnen oder drucken) |",
    ]
    if include_pdf:
        lines.append("| `01_Bewerbungsprotokoll.pdf` | Selbiges als PDF |")
    lines += [
        "| `02_Stellenanzeige.html` | Original-Stellenbeschreibung mit Link zur Anzeige |",
        f"| `03_Notizen.md` | Alle Notizen ({n_events} Timeline-Eintraege gesamt) |",
        f"| `04_Termine.ics` | {n_meetings} Termin(e), in Outlook/Thunderbird/Apple Calendar importierbar |",
        f"| `05_Mail-Verlauf.md` | {n_emails} E-Mail(s) als Zusammenfassung |",
    ]
    if include_dokumente:
        lines.append(f"| `dokumente/` | {n_dokumente} verknuepfte Original-Datei(en) |")
    if include_mails:
        lines.append("| `mails/` | Original-Mail-Dateien (.eml/.msg) falls vorhanden |")
    lines += [
        "",
        "## Tipps zum Lesen",
        "",
        "- **HTML-Dateien** im Browser oeffnen (Doppelklick).",
        "- **Markdown-Dateien** mit jedem Text-Editor lesbar; Renderer wie VS Code, Obsidian oder GitHub formatieren sie schoen.",
        "- **`.ics`** in deinen Kalender importieren — alle verknuepften Termine kommen sauber rein.",
        "",
        "Erstellt von [PBP — Persoenliches Bewerbungs-Portal](https://github.com/MadGapun/PBP).",
    ]
    return "\n".join(lines)


def _render_html_to_pdf(html: str) -> bytes | None:
    """HTML -> PDF via Playwright (Phase 2). None bei Fehlern.

    Playwright ist seit beta.16 Core-Dep, damit ist die Konvertierung
    ohne neue Dependency moeglich.
    """
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        logger.info("PDF-Export: Playwright nicht verfuegbar")
        return None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.set_content(html, wait_until="load")
            pdf_bytes = page.pdf(format="A4", print_background=True,
                                  margin={"top": "1.5cm", "bottom": "1.5cm",
                                          "left": "1.5cm", "right": "1.5cm"})
            browser.close()
            return pdf_bytes
    except Exception as e:
        logger.warning("PDF-Export ueber Playwright fehlgeschlagen: %s", e)
        return None


@app.get("/api/jobs")
async def api_jobs(active: bool = True,
                   exclude_blacklisted: bool = True,
                   exclude_applied: bool = False,
                   limit: int = 0,
                   offset: int = 0):
    """Get jobs with filtering and optional pagination (#118, #121, #145).

    By default, blacklisted companies are excluded from active jobs.
    Set exclude_applied=true to also hide already-applied jobs.
    Use limit/offset for pagination. limit=0 returns all (backward compatible).
    """
    if active:
        all_jobs = _db.get_active_jobs(
            exclude_blacklisted=exclude_blacklisted,
            exclude_applied=exclude_applied,
        )
        total = len(all_jobs)
        if limit > 0:
            page = all_jobs[offset:offset + limit]
            return {"jobs": page, "total": total, "offset": offset, "limit": limit, "has_more": offset + limit < total}
        return all_jobs
    return _db.get_dismissed_jobs()


@app.post("/api/jobs/dismiss")
async def api_dismiss_job(request: Request):
    data = await request.json()
    reasons = data.get("reasons", [])
    reason_str = data.get("reason", "")
    # Support both single reason (legacy) and multi-select reasons (#108, #120)
    if reasons:
        reason_str = json.dumps(reasons, ensure_ascii=False)
        _db.increment_dismiss_reason_usage(reasons)
    elif not reason_str:
        return JSONResponse({"error": "Mindestens ein Ablehnungsgrund ist erforderlich"}, status_code=400)
    _db.dismiss_job(data["hash"], reason_str)
    return {"status": "ok"}


@app.post("/api/jobs/restore")
async def api_restore_job(request: Request):
    data = await request.json()
    _db.restore_job(data["hash"])
    return {"status": "ok"}


@app.get("/api/jobs/{job_hash}/fit-analyse")
async def api_fit_analyse(job_hash: str):
    """Detailed fit analysis for a specific job."""
    from .job_scraper import fit_analyse
    job = _db.get_job(job_hash)
    if not job:
        return JSONResponse({"error": "Stelle nicht gefunden"}, status_code=404)
    criteria = _db.get_search_criteria()
    # #305: Education + Skills für Hochschulabschluss-Erkennung
    profile = _db.get_profile()
    if profile:
        skills = profile.get("skills", [])
        criteria["_profile_skills"] = [s.get("name", "").lower() for s in skills if s.get("name")]
        criteria["_profile_education"] = profile.get("education", [])
    result = fit_analyse(job, criteria)
    # #306: Research notes (Claude-Analyse) mitsenden
    result["research_notes"] = job.get("research_notes") or ""
    return result


@app.get("/api/applications")
async def api_applications(
    status: str = None, limit: int = 30, offset: int = 0,
    include_archived: bool = False,
    from_date: str = None, to_date: str = None,
    search: str = None, sort_by: str = "applied_at", sort_order: str = "desc",
):
    filter_kwargs = dict(from_date=from_date, to_date=to_date, search=search)
    total = _db.count_applications(status, include_archived=True)
    archived_count = _db.count_archived_applications()
    active_count = total - archived_count
    if status:
        apps = _db.get_applications(
            status=status, limit=limit, offset=offset,
            sort_by=sort_by, sort_order=sort_order, **filter_kwargs,
        )
        filtered_total = _db.count_applications(status=status, **filter_kwargs)
    else:
        apps = _db.get_applications(
            include_archived=include_archived, limit=limit, offset=offset,
            sort_by=sort_by, sort_order=sort_order, **filter_kwargs,
        )
        filtered_total = _db.count_applications(
            include_archived=include_archived, **filter_kwargs,
        )
    return {
        "applications": apps, "total": total,
        "filtered_total": filtered_total,
        "archived_count": archived_count,
        "limit": limit, "offset": offset,
    }


@app.post("/api/applications")
async def api_add_application(request: Request):
    data = await request.json()
    if not data.get("title", "").strip():
        return JSONResponse({"error": "Stelle ist ein Pflichtfeld"}, status_code=400)
    if not data.get("company", "").strip():
        return JSONResponse({"error": "Firma ist ein Pflichtfeld"}, status_code=400)
    aid = _db.add_application(data)
    return {"status": "ok", "id": aid}


@app.put("/api/applications/{app_id}/status")
async def api_update_app_status(app_id: str, request: Request):
    data = await request.json()
    new_status = data.get("status")
    if not new_status:
        return JSONResponse({"error": "status ist erforderlich"}, status_code=400)
    profile_id = _get_active_profile_id()
    # Zaehle offene Follow-ups vor dem Wechsel, damit UI das Lifecycle-Ergebnis anzeigen kann (#493/#494)
    open_before = sum(
        1 for fu in _db.get_pending_follow_ups() if fu.get("application_id") == app_id
    )
    if not profile_id or not _db.update_application_status(
        app_id,
        new_status,
        data.get("notes", ""),
        profile_id=profile_id,
    ):
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    open_after = sum(
        1 for fu in _db.get_pending_follow_ups() if fu.get("application_id") == app_id
    )
    lifecycle = {
        "followups_dismissed": max(0, open_before - open_after),
        "new_followup": None,
    }
    if new_status == "interview_abgeschlossen":
        # jungster offener Follow-up wurde soeben vom Lifecycle-Hook angelegt
        pending = [
            fu for fu in _db.get_pending_follow_ups()
            if fu.get("application_id") == app_id
        ]
        if pending:
            latest = max(pending, key=lambda f: f.get("created_at") or "")
            lifecycle["new_followup"] = {
                "id": latest.get("id"),
                "scheduled_date": latest.get("scheduled_date"),
            }
    return {"status": "ok", "lifecycle": lifecycle}


@app.get("/api/settings/followup")
async def api_get_followup_settings():
    """Liest die Follow-up-Automations-Einstellungen (#494)."""
    try:
        default_days = int(_db.get_setting("followup_default_days", 7) or 7)
    except Exception:
        default_days = 7
    try:
        interview_delay = int(_db.get_setting("followup_interview_delay_days", 14) or 14)
    except Exception:
        interview_delay = 14
    return {
        "followup_default_days": default_days,
        "followup_interview_delay_days": interview_delay,
    }


@app.put("/api/settings/followup")
async def api_set_followup_settings(request: Request):
    data = await request.json()
    out: dict[str, int] = {}
    for key in ("followup_default_days", "followup_interview_delay_days"):
        if key in data:
            try:
                val = int(data[key])
            except (TypeError, ValueError):
                return JSONResponse({"error": f"{key} muss eine Zahl sein"}, status_code=400)
            if val < 0 or val > 365:
                return JSONResponse({"error": f"{key} muss zwischen 0 und 365 liegen"}, status_code=400)
            _db.set_setting(key, val)
            out[key] = val
    return {"status": "ok", "gespeichert": out}


@app.put("/api/applications/{app_id}")
async def api_update_application(app_id: str, request: Request):
    """Update editable fields of an application (#134).

    Allowed fields: title, company, url, ansprechpartner, kontakt_email,
    portal_name, bewerbungsart, vermittler, endkunde, notes.
    Changes are logged as timeline events.
    """
    data = await request.json()
    allowed = (
        "title", "company", "url", "ansprechpartner", "kontakt_email",
        "portal_name", "bewerbungsart", "vermittler", "endkunde", "notes",
        "employment_type", "gehaltsvorstellung", "final_salary",
        "description_snapshot", "snapshot_date",
        "applied_at", "is_imported",
    )
    profile_id = _get_active_profile_id()
    if not profile_id:
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    conn = _db.connect()
    app_row = conn.execute(
        "SELECT * FROM applications WHERE id=? AND (profile_id=? OR profile_id IS NULL)",
        (app_id, profile_id),
    ).fetchone()
    if not app_row:
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)

    changes = []
    for field in allowed:
        if field in data:
            old_val = app_row[field] if field in app_row.keys() else ""
            new_val = data[field]
            if str(old_val or "") != str(new_val or ""):
                # Lange Felder (z.B. Snapshot) im Log kuerzen
                _old = str(old_val or "(leer)")
                _new = str(new_val or "(leer)")
                if len(_old) > 80:
                    _old = _old[:77] + "..."
                if len(_new) > 80:
                    _new = _new[:77] + "..."
                changes.append(f"{field}: {_old} \u2192 {_new}")

    if not changes:
        return {"status": "ok", "changes": 0}

    # Apply updates
    sets = []
    vals = []
    for field in allowed:
        if field in data:
            sets.append(f"{field}=?")
            vals.append(data[field])
    now = datetime.now().isoformat()
    sets.append("updated_at=?")
    vals.append(now)
    vals.append(app_id)
    conn.execute(f"UPDATE applications SET {', '.join(sets)} WHERE id=?", vals)

    # Log change as timeline event
    change_text = "Bewerbung bearbeitet: " + "; ".join(changes)
    conn.execute(
        "INSERT INTO application_events (application_id, status, event_date, notes) VALUES (?, ?, ?, ?)",
        (app_id, "bearbeitet", now, change_text)
    )
    conn.commit()
    return {"status": "ok", "changes": len(changes)}


@app.put("/api/applications/{app_id}/research-notes")
async def api_update_research_notes(app_id: str, request: Request):
    """Speichert Firmen-Recherche-Notizen am verknuepften Job des Dossiers (#463)."""
    profile_id = _get_active_profile_id()
    app_row = _get_application_row_for_active_profile(app_id)
    if not profile_id or not app_row:
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    job_hash = app_row["job_hash"] if "job_hash" in app_row.keys() else None
    if not job_hash:
        return JSONResponse(
            {"error": "Bewerbung ist nicht mit einer Stelle verknuepft. Recherche kann nicht gespeichert werden."},
            status_code=400,
        )
    data = await request.json()
    notes = data.get("research_notes", "")
    _db.update_job(job_hash, {"research_notes": notes})
    return {"status": "ok"}


@app.post("/api/applications/{app_id}/link-document")
async def api_link_document(app_id: str, request: Request):
    """Link an existing document to an application."""
    data = await request.json()
    doc_id = data.get("document_id")
    if not doc_id:
        return JSONResponse({"error": "document_id ist Pflicht"}, status_code=400)
    profile_id = _get_active_profile_id()
    if not profile_id or not _db.link_document_to_application(doc_id, app_id, profile_id=profile_id):
        return JSONResponse({"error": "Dokument oder Bewerbung nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.post("/api/applications/{app_id}/notes")
async def api_add_note(app_id: str, request: Request):
    """Add a timestamped note to an application."""
    if not _get_application_row_for_active_profile(app_id):
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    data = await request.json()
    text = (data.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "Notiz-Text ist Pflicht"}, status_code=400)
    parent_id = data.get("parent_event_id")
    _db.add_application_note(app_id, text, parent_event_id=parent_id)
    return {"status": "ok"}


@app.put("/api/applications/{app_id}/notes/{event_id}")
async def api_update_note(app_id: str, event_id: int, request: Request):
    """Update an existing note/event text."""
    if not _get_application_row_for_active_profile(app_id):
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    data = await request.json()
    text = (data.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "Notiz-Text ist Pflicht"}, status_code=400)
    _db.update_application_event(event_id, app_id, text)
    return {"status": "ok"}


@app.delete("/api/applications/{app_id}/notes/{event_id}")
async def api_delete_note(app_id: str, event_id: int):
    """Delete a note from the application timeline."""
    if not _get_application_row_for_active_profile(app_id):
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    _db.delete_application_event(event_id, app_id)
    return {"status": "ok"}


@app.post("/api/applications/{app_id}/snapshot")
async def api_snapshot_description(app_id: str, request: Request):
    """Fetch job description from URL and save as snapshot (#124).

    POST body: { "url": "https://..." }
    Uses simple HTTP fetch + HTML text extraction.
    """
    if not _get_application_row_for_active_profile(app_id):
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    data = await request.json()
    url = (data.get("url") or "").strip()
    if not url:
        return JSONResponse({"error": "URL ist erforderlich"}, status_code=400)

    import urllib.request
    import re
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; PBP/1.0)",
            "Accept": "text/html,application/xhtml+xml",
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        return JSONResponse(
            {"error": f"URL konnte nicht geladen werden: {str(e)}"},
            status_code=502
        )

    # Smart extraction: JSON-LD → CSS selectors → fallback regex (#268)
    text = ""
    try:
        from bs4 import BeautifulSoup
        import json as _json
        soup = BeautifulSoup(html, "html.parser")

        # Strategy 1: JSON-LD structured data (best quality)
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = _json.loads(script.string or "")
                items = data if isinstance(data, list) else data.get("@graph", [data])
                for item in items:
                    if item.get("@type") == "JobPosting":
                        desc = item.get("description", "")
                        if desc:
                            text = BeautifulSoup(desc, "html.parser").get_text(separator=" ", strip=True)
                            break
            except Exception:
                continue
            if text:
                break

        # Strategy 2: Common CSS selectors for job descriptions
        if not text:
            for selector in [
                "[class*='job-description']", "[class*='jobDescription']",
                "[class*='stellenbeschreibung']", "[class*='description']",
                "[class*='detail-content']", "[class*='job-detail']",
                "article .content", "article", ".content-area",
                "[itemprop='description']", "main",
            ]:
                el = soup.select_one(selector)
                if el:
                    candidate = el.get_text(separator="\n", strip=True)
                    if len(candidate) > 100:
                        text = candidate
                        break
    except ImportError:
        pass  # bs4 not available, fall through to regex fallback

    # Strategy 3: Regex fallback (only if smart extraction found nothing)
    if not text:
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '\n', text)
        text = re.sub(r'&nbsp;', ' ', text)
        text = re.sub(r'&amp;', '&', text)
        text = re.sub(r'&lt;', '<', text)
        text = re.sub(r'&gt;', '>', text)
        text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'\n\s*\n', '\n\n', text).strip()

    # Limit to reasonable size
    if len(text) > 20000:
        text = text[:20000] + "\n\n[... gekuerzt]"

    conn = _db.connect()
    now = datetime.now().isoformat()
    conn.execute(
        "UPDATE applications SET description_snapshot=?, snapshot_date=?, updated_at=? WHERE id=?",
        (text, now, now, app_id)
    )
    conn.commit()

    return {
        "status": "ok",
        "snapshot_length": len(text),
        "snapshot_date": now,
        "preview": text[:500],
    }


@app.get("/api/documents")
async def api_documents(
    q: str = "",
    doc_type: str = "",
    application_id: str = "",
    unlinked: str = "",
    extraction_status: str = "",
    sort: str = "created_at",
    order: str = "desc",
    page: int = 1,
    per_page: int = 25,
):
    """List documents with search, filter, sort, pagination and application cross-reference (#360, #366)."""
    pid = _db.get_active_profile_id()
    conn = _db.connect()

    # Base query with LEFT JOIN to applications for cross-reference
    base = """
        FROM documents d
        LEFT JOIN applications a ON d.linked_application_id = a.id
        WHERE (d.profile_id=? OR d.profile_id IS NULL)
    """
    params = [pid]

    # Fulltext search across filename and extracted_text
    if q:
        base += " AND (d.filename LIKE ? OR d.extracted_text LIKE ?)"
        like = f"%{q}%"
        params.extend([like, like])

    # Filter by document type
    if doc_type:
        base += " AND d.doc_type = ?"
        params.append(doc_type)

    # Filter by application (#366)
    if application_id:
        base += " AND d.linked_application_id = ?"
        params.append(application_id)

    # Filter unlinked documents (#366)
    if unlinked == "1":
        base += " AND (d.linked_application_id IS NULL OR d.linked_application_id = '')"

    # Filter by extraction status (#369). #492: "nicht_extrahiert" ist
    # fuer den UI-Filter ein Sammelbegriff fuer alle "nicht-fertigen"
    # Stati (inkl. basis_analysiert + NULL + leer) — sonst stimmen
    # Filter-Ergebnis und Zaehler nicht ueberein.
    if extraction_status == "nicht_extrahiert":
        base += " AND (d.extraction_status IS NULL OR d.extraction_status IN ('nicht_extrahiert', '', 'basis_analysiert'))"
    elif extraction_status:
        base += " AND d.extraction_status = ?"
        params.append(extraction_status)

    # Count total + unlinked count for badge
    total = conn.execute(f"SELECT COUNT(*) as cnt {base}", params).fetchone()["cnt"]
    unlinked_count = conn.execute(
        """SELECT COUNT(*) as cnt FROM documents d
           WHERE (d.profile_id=? OR d.profile_id IS NULL)
             AND (d.linked_application_id IS NULL OR d.linked_application_id = '')""",
        (pid,),
    ).fetchone()["cnt"]

    # Sort (#369: nicht-analysierte zuerst als Option)
    allowed_sorts = {"created_at": "d.created_at", "filename": "d.filename", "doc_type": "d.doc_type",
                     "extraction_status": "d.extraction_status"}
    sort_col = allowed_sorts.get(sort, "d.created_at")
    sort_dir = "ASC" if order.lower() == "asc" else "DESC"
    # #388: Documents linked to archived applications sort to end
    # Default: unanalyzed documents first, archived last, then by sort column
    archive_suffix = "CASE WHEN a.status IN ('abgelehnt', 'zurueckgezogen', 'abgelaufen') THEN 1 ELSE 0 END, "
    unanalyzed_prefix = f"CASE WHEN d.extraction_status IN ('nicht_extrahiert', NULL, '') THEN 0 ELSE 1 END, {archive_suffix}"

    # Paginate
    offset = (max(1, page) - 1) * per_page
    rows = conn.execute(
        f"""SELECT d.*, a.company as app_company, a.title as app_title, a.status as app_status
            {base}
            ORDER BY {unanalyzed_prefix}{sort_col} {sort_dir}
            LIMIT ? OFFSET ?""",
        params + [per_page, offset],
    ).fetchall()

    # Available doc_types for filter dropdown
    type_rows = conn.execute(
        "SELECT DISTINCT doc_type FROM documents WHERE (profile_id=? OR profile_id IS NULL) AND doc_type IS NOT NULL ORDER BY doc_type",
        (pid,),
    ).fetchall()

    # Available applications for filter dropdown (#366)
    app_rows = conn.execute(
        """SELECT DISTINCT a.id, a.company, a.title
           FROM documents d
           JOIN applications a ON d.linked_application_id = a.id
           WHERE (d.profile_id=? OR d.profile_id IS NULL)
           ORDER BY a.company""",
        (pid,),
    ).fetchall()

    # Count unanalyzed documents (#369)
    unanalyzed_count = conn.execute(
        """SELECT COUNT(*) as cnt FROM documents d
           WHERE (d.profile_id=? OR d.profile_id IS NULL)
             AND (d.extraction_status IS NULL OR d.extraction_status IN ('nicht_extrahiert', '', 'basis_analysiert'))""",
        (pid,),
    ).fetchone()["cnt"]

    return {
        "documents": [dict(r) for r in rows],
        "total": total,
        "unlinked_count": unlinked_count,
        "unanalyzed_count": unanalyzed_count,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
        "doc_types": [r["doc_type"] for r in type_rows],
        "applications": [dict(r) for r in app_rows],
    }


@app.get("/api/documents/{doc_id}/download")
async def api_download_document(doc_id: str):
    """Download/preview a document by ID."""
    profile_id = _get_active_profile_id()
    if not profile_id:
        return JSONResponse({"error": "Dokument nicht gefunden"}, status_code=404)
    row = _db.get_document(doc_id, profile_id=profile_id)
    if not row:
        return JSONResponse({"error": "Dokument nicht gefunden"}, status_code=404)
    filepath = Path(row["filepath"])
    if not filepath.exists():
        return JSONResponse({"error": "Datei nicht gefunden auf dem Dateisystem"}, status_code=404)
    import mimetypes
    mime, _ = mimetypes.guess_type(str(filepath))
    return FileResponse(str(filepath), filename=row["filename"], media_type=mime or "application/octet-stream")


@app.get("/api/emails/{email_id}/download")
async def api_download_email(email_id: str):
    """Download the original email file (.msg/.eml) by ID."""
    profile_id = _get_active_profile_id()
    if not profile_id:
        return JSONResponse({"error": "E-Mail nicht gefunden"}, status_code=404)
    row = _db.get_email(email_id, profile_id=profile_id)
    if not row:
        return JSONResponse({"error": "E-Mail nicht gefunden"}, status_code=404)
    filepath = Path(row.get("filepath", ""))
    if not filepath.exists():
        return JSONResponse({"error": "E-Mail-Datei nicht auf dem Dateisystem gefunden"}, status_code=404)
    import mimetypes
    mime, _ = mimetypes.guess_type(str(filepath))
    return FileResponse(str(filepath), filename=row.get("filename", filepath.name), media_type=mime or "application/octet-stream")


@app.get("/api/statistics")
async def api_statistics():
    return _db.get_statistics()


@app.get("/api/stats/timeline")
async def api_stats_timeline(interval: str = "month", range: str = ""):
    """Application timeline grouped by interval (week/month/quarter/year).
    Optional range param overrides time window: 30d, 90d, 6m, 12m."""
    return _db.get_timeline_stats(interval, time_range=range)


@app.get("/api/stats/scores")
async def api_stats_scores():
    """Score distribution and trend data for charts."""
    return _db.get_score_stats()


@app.get("/api/stats/extended")
async def api_stats_extended():
    """Extended statistics: daily activity, response times, dismiss reasons, import vs new (#135)."""
    return _db.get_extended_stats()


@app.get("/api/keyword-suggestions")
async def api_keyword_suggestions():
    """Keyword-Vorschlaege fuer das Frontend (#458 / beta.35).

    War bis beta.34 eine alte Schwester-Implementierung mit kurzer
    Stop-Word-Liste — User-Beobachtung "kunden, sowie, aufgaben usw.
    werden noch vorgeschlagen". Jetzt eine duenne Wrapper, die den
    schon ueberarbeiteten MCP-Tool-Algorithmus aus tools/analyse.py
    aufruft, sodass beide Pfade dieselbe Logik nutzen.
    """
    import re as _re
    from collections import Counter as _Counter

    criteria = _db.get_search_criteria()
    muss = [kw.lower() for kw in criteria.get("keywords_muss", [])]
    plus = [kw.lower() for kw in criteria.get("keywords_plus", [])]
    ausschluss = [kw.lower() for kw in criteria.get("keywords_ausschluss", [])]
    alle_keywords = set(muss + plus)

    # Erweiterte Stop-Word-Liste (DACH-Stellenanzeigen-Floskeln) — synchron
    # mit tools/analyse.py::keyword_vorschlaege.
    _stopwords = {
        "und", "oder", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einem", "einen",
        "ist", "sind", "war", "waren", "hat", "habe", "haben", "wird", "werden", "wurde", "wurden",
        "mit", "ohne", "von", "vor", "nach", "fuer", "für", "als", "bei", "zur", "zum", "zu",
        "auf", "aus", "nach", "ueber", "über", "unter", "durch", "an", "am", "im", "in", "ins",
        "nicht", "auch", "sich", "wir", "sie", "uns", "ihr", "ihre", "ihren", "ihrer",
        "unser", "unsere", "unseren", "unserer", "unserem", "unseres",
        "deine", "dein", "dich", "dir", "du", "diese", "dieser", "diesem",
        "team", "stelle", "stellen", "job", "jobs", "position", "rolle",
        "aufgabe", "aufgaben", "taetigkeit", "taetigkeiten",
        "anforderung", "anforderungen", "kenntnisse", "kenntnis", "erfahrung", "erfahrungen",
        "kollege", "kollegen", "kolleginnen", "mitarbeiter", "mitarbeitern", "mitarbeiterinnen",
        "kunde", "kunden", "kundinnen", "partner", "partnern",
        "unternehmen", "firma", "gmbh", "ag", "co", "kg", "ohg", "sa",
        "bereich", "bereiche", "abteilung", "abteilungen",
        "projekt", "projekte", "projekten",
        "arbeit", "arbeiten", "arbeitsplatz", "arbeitsplaetze",
        "moeglichkeit", "moeglichkeiten",
        "deutsch", "deutsche", "deutschen", "english", "englisch",
        "bieten", "bietet", "suchen", "sucht", "gerne", "gern",
        "sowie", "sowohl", "ebenso",
        "erstellung", "erstellen", "umsetzung", "umsetzen", "durchfuehrung",
        "verantwortung", "verantwortlich",
        "qualifikation", "qualifikationen", "ausbildung",
        "stunden", "tage", "tag", "wochen", "woche",
        "montag", "dienstag", "mittwoch", "donnerstag", "freitag",
        "monat", "monaten", "jahr", "jahre", "jahren",
        "m/w/d", "m/w", "w/m/d", "w/m", "d/m/w",
        "macht", "machen", "tun", "tuen", "geht", "gehen", "kommt", "kommen",
        "gibt", "geben", "nehmen", "nimmt",
        "kann", "koennen", "muss", "muessen", "soll", "sollen", "will", "wollen",
    }

    def _terms(text: str) -> list[str]:
        # Min 5 Zeichen — eliminiert "team", "ihre", "sowie" wenn Stoppwort fehlt
        words = _re.findall(r"[a-zA-ZäöüÄÖÜß]{5,}", text.lower())
        return [w for w in words if w not in _stopwords]

    # Datenquelle: Bewerbungen vs. aussortierte Stellen (User-Wunsch beta.29);
    # Fallback Score-Vergleich wenn nicht genug Daten.
    applications = _db.get_applications()
    applied_hashes = {
        a["job_hash"] for a in applications
        if a.get("job_hash") and a.get("status") not in (
            "abgelehnt", "zurueckgezogen", "abgelaufen", "passt_nicht"
        )
    }
    dismissed_jobs = _db.get_dismissed_jobs() if hasattr(_db, "get_dismissed_jobs") else []

    all_jobs = _db.get_active_jobs(exclude_blacklisted=True)
    if not all_jobs:
        return {"status": "keine_jobs", "aktive_stellen": 0}
    if len(all_jobs) < 20:
        return {"status": "zu_wenig_jobs", "aktive_stellen": len(all_jobs), "min_jobs": 20}

    applied_job_objs = [j for j in all_jobs if j.get("hash") in applied_hashes]
    if not applied_job_objs and applied_hashes and dismissed_jobs:
        applied_job_objs = [j for j in dismissed_jobs if j.get("hash") in applied_hashes]

    use_application_source = (
        len(applied_job_objs) >= 3 and len(dismissed_jobs) >= 3
    )

    if use_application_source:
        good_jobs = applied_job_objs
        bad_jobs = [j for j in dismissed_jobs if j.get("hash") not in applied_hashes]
        datenquelle = (
            f"Vergleich: {len(good_jobs)} Stellen mit Bewerbung "
            f"vs. {len(bad_jobs)} aussortierte Stellen"
        )
    else:
        good_jobs = [j for j in all_jobs if j.get("score", 0) >= 3]
        bad_jobs = [j for j in all_jobs if j.get("score", 0) <= 1]
        datenquelle = (
            f"Score-Vergleich (kein Bewerbungs-Vergleich moeglich, "
            f"Bewerbungen: {len(applied_job_objs)}, "
            f"Aussortiert: {len(dismissed_jobs)})"
        )

    # Document Frequency fuer Spezifitaets-Filter
    all_jobs_count = max(1, len(all_jobs))
    doc_freq: _Counter[str] = _Counter()
    for j in all_jobs:
        text = f"{j.get('title', '')} {(j.get('description') or '')[:1500]}"
        for term in set(_terms(text)):
            doc_freq[term] += 1

    good_words: _Counter[str] = _Counter()
    bad_words: _Counter[str] = _Counter()
    for j in good_jobs:
        text = f"{j.get('title', '')} {(j.get('description') or '')[:1500]}"
        for term in _terms(text):
            good_words[term] += 1
    for j in bad_jobs:
        text = f"{j.get('title', '')} {(j.get('description') or '')[:1500]}"
        for term in _terms(text):
            bad_words[term] += 1

    # Begriffe in >70% aller Stellen werden ausgefiltert (zu generisch)
    TOO_GENERIC_THRESHOLD = 0.7
    too_generic = {
        term for term, count in doc_freq.items()
        if count / all_jobs_count > TOO_GENERIC_THRESHOLD
    }

    vorschlaege_plus: list[dict] = []
    min_freq = max(2, len(good_jobs) // 4) if good_jobs else 2
    for term, count in good_words.most_common(80):
        if term in alle_keywords or term in too_generic:
            continue
        if count < min_freq:
            continue
        ratio = count / max(1, bad_words.get(term, 0))
        if ratio >= 2:
            vorschlaege_plus.append({
                "keyword": term,
                "in_guten_stellen": count,
                "in_schlechten_stellen": bad_words.get(term, 0),
            })

    # beta.35 / User-Feedback: "manager" wurde als Ausschluss empfohlen,
    # obwohl User sich auf Manager-Stellen beworben hatte. Logik
    # verschaerft: ein Term darf nur als Ausschluss vorgeschlagen werden,
    # wenn er in KEINER Bewerbung vorkommt (good_words.get(term, 0) == 0).
    # So vermeidet PBP, dass User echte Zielbegriffe ablehnen.
    vorschlaege_ausschluss: list[dict] = []
    min_bad_freq = max(2, len(bad_jobs) // 4) if bad_jobs else 2
    for term, count in bad_words.most_common(50):
        if term in alle_keywords or term in ausschluss or term in too_generic:
            continue
        if count < min_bad_freq:
            continue
        if good_words.get(term, 0) > 0:
            # Term ist in mindestens einer Bewerbung des Users vorhanden
            # -> kein Ausschluss-Kandidat.
            continue
        vorschlaege_ausschluss.append({
            "keyword": term,
            "in_schlechten_stellen": count,
            "in_guten_stellen": 0,
        })

    return {
        "status": "ok",
        "aktive_stellen": len(all_jobs),
        "gut_bewertet": len(good_jobs),
        "schlecht_bewertet": len(bad_jobs),
        "datenquelle": datenquelle,
        "vorschlaege_plus": vorschlaege_plus[:10],
        "vorschlaege_ausschluss": vorschlaege_ausschluss[:5],
    }


@app.get("/api/stats/style")
async def api_stats_style():
    """Anschreiben-Stil-Auswertung: Welcher Stil bringt mehr Interviews/Angebote? (#454)."""
    import re as _re

    conn = _db.connect()
    rows = conn.execute(
        """
        SELECT e.notes, e.application_id, a.status
        FROM application_events e
        JOIN applications a ON a.id = e.application_id
        WHERE e.status = 'stil_tracking'
        ORDER BY e.event_date ASC
        """
    ).fetchall()

    if not rows:
        return {"status": "keine_daten", "stile": {}, "min_samples_fuer_quoten": 3}

    latest_per_app: dict[str, tuple[str, str]] = {}
    for r in rows:
        notes = r["notes"] or ""
        m = _re.match(r"Anschreiben-Stil:\s*(\w+)", notes)
        if not m:
            continue
        latest_per_app[r["application_id"]] = (m.group(1).lower(), r["status"])

    INTERVIEW_STATES = {"interview", "zweitgespraech"}
    OFFER_STATES = {"angebot", "angenommen"}
    REJECT_STATES = {"abgelehnt", "abgesagt"}

    per_stil: dict[str, dict] = {}
    for stil, app_status in latest_per_app.values():
        bucket = per_stil.setdefault(stil, {
            "anzahl": 0, "interviews": 0, "angebote": 0, "absagen": 0, "in_prozess": 0,
        })
        bucket["anzahl"] += 1
        if app_status in INTERVIEW_STATES:
            bucket["interviews"] += 1
            bucket["in_prozess"] += 1
        elif app_status in OFFER_STATES:
            bucket["interviews"] += 1
            bucket["angebote"] += 1
        elif app_status in REJECT_STATES:
            bucket["absagen"] += 1
        else:
            bucket["in_prozess"] += 1

    MIN_SAMPLES = 3
    for bucket in per_stil.values():
        n = bucket["anzahl"]
        if n >= MIN_SAMPLES:
            bucket["interview_quote"] = round(bucket["interviews"] / n * 100, 1)
            bucket["angebots_quote"] = round(bucket["angebote"] / n * 100, 1)
            bucket["absage_quote"] = round(bucket["absagen"] / n * 100, 1)

    sortiert = sorted(
        per_stil.items(),
        key=lambda kv: kv[1].get("interview_quote", -1),
        reverse=True,
    )
    return {
        "status": "ok",
        "gesamt_getrackt": sum(b["anzahl"] for b in per_stil.values()),
        "stile": dict(sortiert),
        "min_samples_fuer_quoten": MIN_SAMPLES,
    }


# === E-Mail Integration (#136) ===

@app.post("/api/emails/upload")
async def api_upload_email(file: UploadFile = File(...)):
    """Upload and parse a .msg or .eml file.

    Parses the email, auto-matches to an application, detects status,
    extracts meetings, and saves attachments as documents.
    """
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        return JSONResponse(
            {"error": f"Datei zu gross ({len(content) // 1024 // 1024} MB). Maximum: 50 MB."},
            status_code=413,
        )
    incoming_name = file.filename or "email.eml"
    ext = Path(incoming_name).suffix.lower()
    if ext not in (".msg", ".eml"):
        return JSONResponse(
            {"error": "Nur .msg und .eml Dateien werden unterstützt."},
            status_code=400,
        )

    from .services.email_service import (
        parse_email_file,
        detect_direction,
        match_email_to_application,
        detect_email_status,
        extract_meetings_from_email,
        save_attachments,
        extract_sender_email,
        find_duplicate_document,
    )
    from .database import get_data_dir

    # Save the raw email file
    email_dir = get_data_dir() / "emails"
    email_dir.mkdir(parents=True, exist_ok=True)
    safe_name = _sanitize_upload_filename(incoming_name)
    email_path = email_dir / safe_name
    counter = 1
    stem, suffix = email_path.stem, email_path.suffix
    while email_path.exists():
        email_path = email_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    email_path.write_bytes(content)

    # Parse the email
    try:
        parsed = parse_email_file(str(email_path))
    except ImportError as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    except Exception as e:
        logger.error("E-Mail Parsing fehlgeschlagen: %s", e)
        return JSONResponse(
            {"error": f"E-Mail konnte nicht geparst werden: {str(e)}"},
            status_code=400,
        )

    # Duplicate protection against rapid drag-and-drop double-imports (#476)
    dup_email = _db.find_recent_duplicate_email(
        sender=parsed.get("sender", ""),
        subject=parsed.get("subject", ""),
        sent_date=parsed.get("sent_date"),
    )
    if dup_email:
        try:
            Path(email_path).unlink(missing_ok=True)
        except Exception:
            pass
        return JSONResponse(
            {
                "error": "E-Mail bereits importiert",
                "duplicate": True,
                "existing_email_id": dup_email["id"],
                "existing_created_at": dup_email.get("created_at"),
                "message": (
                    "Diese E-Mail wurde in den letzten 5 Minuten bereits importiert. "
                    "Falls das ein Fehlalarm ist, warte einen Moment und versuche es erneut."
                ),
            },
            status_code=409,
        )

    # Detect direction (incoming vs outgoing)
    profile = _db.get_profile()
    profile_email = (profile or {}).get("email", "")
    direction = detect_direction(parsed.get("sender", ""), profile_email)
    parsed["_direction"] = direction

    # Auto-match to application
    apps = _db.get_applications()
    match_app_id, match_confidence = match_email_to_application(parsed, apps)

    # Detect status from content
    detected_status, status_confidence = detect_email_status(
        parsed.get("subject", ""),
        parsed.get("body_text", ""),
    )

    # Extract meetings
    meetings = extract_meetings_from_email(parsed)

    # Save attachments as documents
    doc_dir = _get_active_profile_document_dir()
    saved_attachments = save_attachments(parsed, str(doc_dir))

    # Check for duplicate documents and auto-import new ones
    existing_docs = _db._get_documents(_db.get_active_profile_id())
    imported_docs = []
    for att in saved_attachments:
        # Check for duplicate
        dup_id = find_duplicate_document(att["content_hash"], existing_docs)
        if dup_id:
            att["duplicate_of"] = dup_id
            att["imported"] = False
            # Remove the duplicate file
            try:
                Path(att["filepath"]).unlink(missing_ok=True)
            except Exception:
                pass
        else:
            # Import as document
            fname = att["filename"].lower()
            # Auto-detect doc_type
            doc_type = _detect_doc_type(att["filename"], "") or "sonstiges"
            did = _db.add_document({
                "filename": att["filename"],
                "filepath": att["filepath"],
                "doc_type": doc_type,
                "extracted_text": "",
                "content_hash": att["content_hash"],
            })
            att["doc_id"] = did
            att["doc_type"] = doc_type
            att["imported"] = True
            # Link to matched application
            if match_app_id:
                try:
                    _db.link_document_to_application(did, match_app_id)
                except Exception:
                    pass
            imported_docs.append(att)

    # Store the email
    attachments_meta = [
        {k: v for k, v in a.items() if k != "payload"}
        for a in saved_attachments
    ]
    email_id = _db.add_email({
        "application_id": match_app_id,
        "filename": email_path.name,
        "filepath": str(email_path),
        "subject": parsed.get("subject", ""),
        "sender": parsed.get("sender", ""),
        "recipients": parsed.get("recipients", ""),
        "sent_date": parsed.get("sent_date"),
        "direction": direction,
        "body_text": parsed.get("body_text", ""),
        "body_html": parsed.get("body_html", ""),
        "detected_status": detected_status,
        "detected_status_confidence": status_confidence,
        "match_confidence": match_confidence,
        "attachments_meta": attachments_meta,
        "meeting_extracted": bool(meetings),
    })

    # Store meetings if matched to an application
    stored_meetings = []
    if match_app_id and meetings:
        for m in meetings:
            if m.get("start"):
                mid = _db.add_meeting({
                    "application_id": match_app_id,
                    "email_id": email_id,
                    "title": m.get("title", "Termin"),
                    "meeting_date": m["start"],
                    "meeting_end": m.get("end"),
                    "location": m.get("location", ""),
                    "meeting_url": m.get("meeting_url"),
                    "platform": m.get("platform"),
                    "meeting_type": "interview",
                })
                stored_meetings.append({"id": mid, **m})

    # Add timeline event if matched
    if match_app_id:
        event_note = f"E-Mail: {parsed.get('subject', 'Ohne Betreff')}"
        if direction == "ausgang":
            event_note = f"Ausgehende Mail: {parsed.get('subject', '')}"
        _db.add_application_event(match_app_id, "email_" + direction, event_note)

    # #225: Kontaktdaten aus E-Mail automatisch in Bewerbung übernehmen
    contact_updated = False
    if match_app_id and direction == "eingang":
        sender = parsed.get("sender", "")
        # Extract email and name from sender (e.g. "Max Müller <max@firma.de>")
        import re as _re_email
        email_match = _re_email.search(r'[\w.+-]+@[\w.-]+\.\w+', sender)
        name_match = _re_email.match(r'^([^<]+?)\s*<', sender)
        sender_email = email_match.group(0) if email_match else ""
        sender_name = name_match.group(1).strip().strip('"') if name_match else ""

        if sender_email or sender_name:
            conn = _db.connect()
            app_row = conn.execute(
                "SELECT kontakt_email, ansprechpartner FROM applications WHERE id=?",
                (match_app_id,)
            ).fetchone()
            updates = {}
            if app_row:
                if sender_email and not app_row["kontakt_email"]:
                    updates["kontakt_email"] = sender_email
                if sender_name and not app_row["ansprechpartner"]:
                    updates["ansprechpartner"] = sender_name
            if updates:
                set_clause = ", ".join(f"{k}=?" for k in updates)
                conn.execute(
                    f"UPDATE applications SET {set_clause}, updated_at=? WHERE id=?",
                    (*updates.values(), datetime.now().isoformat(), match_app_id)
                )
                conn.commit()
                contact_updated = True

    # Find matched application info for response
    matched_app = None
    if match_app_id:
        for a in apps:
            if a.get("id") == match_app_id:
                matched_app = {"id": a["id"], "title": a.get("title"), "company": a.get("company")}
                break

    return {
        "status": "ok",
        "email_id": email_id,
        "contact_updated": contact_updated,
        "parsed": {
            "subject": parsed.get("subject", ""),
            "sender": parsed.get("sender", ""),
            "recipients": parsed.get("recipients", ""),
            "sent_date": parsed.get("sent_date"),
            "direction": direction,
            "body_preview": (parsed.get("body_text") or "")[:500],
            "attachment_count": len(parsed.get("attachments", [])),
        },
        "match": {
            "application": matched_app,
            "confidence": match_confidence,
        },
        "detected_status": {
            "status": detected_status,
            "confidence": status_confidence,
        },
        "meetings": [
            {k: v for k, v in m.items() if k != "payload"}
            for m in stored_meetings
        ],
        "attachments": [
            {k: v for k, v in a.items() if k not in ("payload", "filepath")}
            for a in saved_attachments
        ],
        "imported_documents": len(imported_docs),
    }


@app.post("/api/emails/{email_id}/confirm-match")
async def api_confirm_email_match(email_id: str, request: Request):
    """Confirm or override auto-matched application for an email."""
    profile_id = _get_active_profile_id()
    data = await request.json()
    app_id = data.get("application_id")
    if not app_id:
        return JSONResponse({"error": "application_id ist erforderlich"}, status_code=400)

    em = _get_email_for_active_profile(email_id)
    if not profile_id or not em:
        return JSONResponse({"error": "E-Mail nicht gefunden"}, status_code=404)
    if not _get_application_row_for_active_profile(app_id):
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)

    _db.update_email(
        email_id,
        {"application_id": app_id, "match_confidence": 1.0, "is_processed": 1},
        profile_id=profile_id,
    )

    # Link any imported documents to the application
    for att in (em.get("attachments_meta") or []):
        doc_id = att.get("doc_id")
        if doc_id:
            try:
                _db.link_document_to_application(doc_id, app_id, profile_id=profile_id)
            except Exception:
                pass

    # Re-extract and store meetings if not yet done
    if not em.get("meeting_extracted"):
        from .services.email_service import extract_meetings_from_email
        meetings = extract_meetings_from_email({
            "subject": em.get("subject", ""),
            "body_text": em.get("body_text", ""),
            "body_html": em.get("body_html", ""),
            "attachments": [],
        })
        for m in meetings:
            if m.get("start"):
                _db.add_meeting({
                    "application_id": app_id,
                    "email_id": email_id,
                    "title": m.get("title", "Termin"),
                    "meeting_date": m["start"],
                    "meeting_end": m.get("end"),
                    "location": m.get("location", ""),
                    "meeting_url": m.get("meeting_url"),
                    "platform": m.get("platform"),
                })

    return {"status": "ok"}


@app.post("/api/emails/{email_id}/apply-status")
async def api_apply_email_status(email_id: str, request: Request):
    """Apply the detected status from an email to the linked application."""
    profile_id = _get_active_profile_id()
    data = await request.json()
    status = data.get("status")
    if not status:
        return JSONResponse({"error": "status ist erforderlich"}, status_code=400)

    em = _get_email_for_active_profile(email_id)
    if not profile_id or not em:
        return JSONResponse({"error": "E-Mail nicht gefunden"}, status_code=404)
    if not em.get("application_id"):
        return JSONResponse({"error": "E-Mail ist keiner Bewerbung zugeordnet"}, status_code=400)

    app_id = em["application_id"]
    if not _db.update_application_status(app_id, status, profile_id=profile_id):
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    _db.add_application_event(app_id, status, f"Status aus E-Mail: {em.get('subject', '')}")
    _db.update_email(email_id, {"is_processed": 1}, profile_id=profile_id)

    # Extract rejection feedback if applicable
    if status == "abgelehnt":
        from .services.email_service import extract_rejection_feedback
        feedback = extract_rejection_feedback(em.get("body_text", ""))
        if feedback:
            _db.add_application_event(app_id, "notiz", f"Feedback aus Absage:\n{feedback}")

    return {"status": "ok", "applied_status": status}


@app.get("/api/emails")
async def api_list_emails():
    """List all emails for the active profile."""
    emails = _db.get_all_emails()
    return {"emails": emails, "count": len(emails)}


@app.get("/api/emails/{email_id}")
async def api_get_email(email_id: str):
    """Get a single email with full body."""
    em = _get_email_for_active_profile(email_id)
    if not em:
        return JSONResponse({"error": "E-Mail nicht gefunden"}, status_code=404)
    return em


@app.get("/api/applications/{app_id}/emails")
async def api_get_application_emails(app_id: str):
    """List all emails linked to a specific application."""
    profile_id = _get_active_profile_id()
    if not profile_id or not _get_application_row_for_active_profile(app_id):
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    emails = _db.get_emails_for_application(app_id, profile_id=profile_id)
    return {"emails": emails, "count": len(emails)}


@app.post("/api/emails/{email_id}/create-application")
async def api_create_application_from_email(email_id: str, request: Request):
    """Erzeugt eine neue Bewerbung aus einer unzugeordneten E-Mail und verknuepft sie (#459).

    Body (optional): {title, company} — Felder zum manuellen Ueberschreiben der heuristischen
    Werte. Default: Subject als Titel, Sender-Domain als Firma.
    """
    profile_id = _get_active_profile_id()
    em = _get_email_for_active_profile(email_id)
    if not profile_id or not em:
        return JSONResponse({"error": "E-Mail nicht gefunden"}, status_code=404)
    if em.get("application_id"):
        return JSONResponse(
            {"error": "E-Mail ist bereits einer Bewerbung zugeordnet"},
            status_code=400,
        )

    try:
        data = await request.json()
    except Exception:
        data = {}

    sender = (em.get("sender") or "").strip()
    subject = (em.get("subject") or "").strip()
    sender_domain = ""
    if "@" in sender:
        domain_part = sender.rsplit("@", 1)[-1]
        domain_part = domain_part.split(">")[0].strip()
        sender_domain = domain_part.split(".")[0] if domain_part else ""

    title = (data.get("title") or "").strip() or subject or "Initiativ-Anfrage"
    company = (data.get("company") or "").strip() or sender_domain or "Unbekannt"

    aid = _db.add_application({
        "title": title,
        "company": company,
        "status": "offen",
        "notes": f"Aus E-Mail erstellt: {subject}",
    })
    _db.update_email(
        email_id,
        {"application_id": aid, "match_confidence": 1.0, "is_processed": 1},
        profile_id=profile_id,
    )
    for att in (em.get("attachments_meta") or []):
        doc_id = att.get("doc_id")
        if doc_id:
            try:
                _db.link_document_to_application(doc_id, aid, profile_id=profile_id)
            except Exception:
                pass
    return {"status": "ok", "id": aid, "title": title, "company": company}


@app.delete("/api/emails/{email_id}")
async def api_delete_email(email_id: str):
    """Delete an email."""
    profile_id = _get_active_profile_id()
    em = _get_email_for_active_profile(email_id)
    if not em:
        return JSONResponse({"error": "E-Mail nicht gefunden"}, status_code=404)
    # Delete file from disk
    filepath = em.get("filepath")
    if filepath:
        try:
            Path(filepath).unlink(missing_ok=True)
        except Exception:
            pass
    _db.delete_email(email_id, profile_id=profile_id)
    return {"status": "ok"}


# === Meetings (#136) ===

@app.get("/api/meetings")
async def api_upcoming_meetings(days: int = 30):
    """Get upcoming meetings for the dashboard widget."""
    meetings = _db.get_upcoming_meetings(days=days)
    return {"meetings": meetings, "count": len(meetings)}


@app.get("/api/meetings/export.ics")
async def api_meetings_export_ics():
    """Export all planned meetings as a single .ics calendar file (#310)."""
    conn = _db.connect()
    pid = _db.get_active_profile_id()
    rows = conn.execute(
        """SELECT m.*, a.title as app_title, a.company as app_company, a.id as app_id
           FROM application_meetings m
           LEFT JOIN applications a ON m.application_id = a.id
           WHERE m.status='geplant'
             AND (m.profile_id=? OR m.profile_id IS NULL)
           ORDER BY m.meeting_date ASC""",
        (pid,),
    ).fetchall()

    from datetime import datetime as _dt
    now_stamp = _dt.now().strftime("%Y%m%dT%H%M%SZ")

    def _fmt_dt(iso_str):
        if not iso_str:
            return None
        try:
            return _dt.fromisoformat(iso_str).strftime("%Y%m%dT%H%M%S")
        except (ValueError, TypeError):
            return None

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PBP Bewerbungs-Assistent//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:PBP Bewerbungstermine",
    ]

    for r in rows:
        m = dict(r)
        dt_start = _fmt_dt(m.get("meeting_date"))
        if not dt_start:
            continue
        dt_end = _fmt_dt(m.get("meeting_end")) or dt_start
        title = m.get("title", "Termin")
        company = m.get("app_company", "")
        app_title = m.get("app_title", "")
        app_id = m.get("app_id", "")
        location = m.get("location", "")
        meeting_url = m.get("meeting_url", "")
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

        ics_lines.append("BEGIN:VEVENT")
        ics_lines.append(f"UID:{m['id']}@pbp.local")
        ics_lines.append(f"DTSTAMP:{now_stamp}")
        ics_lines.append(f"DTSTART:{dt_start}")
        ics_lines.append(f"DTEND:{dt_end}")
        ics_lines.append(f"SUMMARY:{title}" + (f" — {company}" if company else ""))
        desc_text = "\\n".join(desc_parts)
        ics_lines.append(f"DESCRIPTION:{desc_text}")
        if location:
            ics_lines.append(f"LOCATION:{location}")
        if meeting_url:
            ics_lines.append(f"URL:{meeting_url}")
        ics_lines.append("END:VEVENT")

    ics_lines.append("END:VCALENDAR")
    ics_content = "\r\n".join(ics_lines)

    from starlette.responses import Response
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": 'attachment; filename="pbp-termine.ics"',
        },
    )


@app.get("/api/meetings/calendar")
async def api_meetings_calendar(days: int = 90):
    """Get all meetings + follow-ups for calendar view with collision detection (#267, #364)."""
    meetings = _db.get_upcoming_meetings(days=days)
    # Also include past meetings (last 30 days) for context
    conn = _db.connect()
    pid = _db.get_active_profile_id()
    past_cutoff = (datetime.now() - timedelta(days=30)).isoformat()
    now = datetime.now().isoformat()
    past_rows = conn.execute(
        """SELECT m.*, a.title as app_title, a.company as app_company
           FROM application_meetings m
           LEFT JOIN applications a ON m.application_id = a.id
           WHERE m.meeting_date >= ? AND m.meeting_date < ?
             AND m.status != 'abgesagt'
             AND (m.profile_id=? OR m.profile_id IS NULL)
           ORDER BY m.meeting_date ASC""",
        (past_cutoff, now, pid),
    ).fetchall()
    all_meetings = [dict(r) for r in past_rows] + meetings

    # Include follow-ups with scheduled_date as calendar entries (#364)
    follow_up_rows = conn.execute(
        """SELECT f.*, a.title as app_title, a.company as app_company
           FROM follow_ups f
           LEFT JOIN applications a ON f.application_id = a.id
           WHERE f.scheduled_date IS NOT NULL
             AND f.scheduled_date >= ?
             AND f.status = 'geplant'
             AND (a.profile_id=? OR a.profile_id IS NULL)
           ORDER BY f.scheduled_date ASC""",
        (past_cutoff, pid),
    ).fetchall()
    follow_ups = []
    for fu in follow_up_rows:
        fu = dict(fu)
        fu_type = fu.get("follow_up_type") or "nachfass"
        label = {"nachfass": "Nachfassen", "erinnerung": "Erinnerung"}.get(fu_type, fu_type.replace("_", " ").title())
        company = fu.get("app_company") or ""
        title = fu.get("app_title") or ""
        follow_ups.append({
            "id": f"followup-{fu['id']}",
            "title": f"{label}: {company}" if company else f"{label}: {title}" if title else label,
            "meeting_date": fu["scheduled_date"],
            "meeting_type": "followup",
            "app_title": title,
            "app_company": company,
            "application_id": fu.get("application_id"),
            "is_follow_up": True,
            "status": fu.get("status", "geplant"),
        })

    # Collision detection (#267): find overlapping meetings (exclude follow-ups)
    collisions = []
    sorted_m = sorted(all_meetings, key=lambda x: x.get("meeting_date", ""))
    for i, m1 in enumerate(sorted_m):
        for m2 in sorted_m[i + 1:]:
            try:
                start1 = datetime.fromisoformat(m1["meeting_date"])
                end1 = datetime.fromisoformat(m1.get("meeting_end") or m1["meeting_date"])
                if end1 == start1:
                    end1 = start1 + timedelta(hours=1)
                start2 = datetime.fromisoformat(m2["meeting_date"])
                if start2 < end1:
                    collisions.append({
                        "meeting_1": m1["id"],
                        "meeting_2": m2["id"],
                        "overlap_start": max(start1, start2).isoformat(),
                    })
            except (ValueError, TypeError):
                continue

    # Enrich meetings with category info (#417)
    _db.ensure_system_categories()
    categories = _db.get_meeting_categories()
    cat_map = {c["id"]: c for c in categories}
    for m in all_meetings:
        cat = cat_map.get(m.get("category_id"))
        if cat:
            m["category_name"] = cat["name"]
            m["category_color"] = cat["color"]

    return {
        "meetings": all_meetings + follow_ups,
        "collisions": collisions,
        "count": len(all_meetings) + len(follow_ups),
        "categories": categories,
    }


@app.get("/api/activity-log")
async def api_activity_log(days: int = 90, categories: str = ""):
    """Aggregated activity log from multiple sources (#373).

    Categories: termine, bewerbungen, followups, dokumente (comma-separated).
    If empty, returns all categories.
    """
    conn = _db.connect()
    pid = _db.get_active_profile_id()
    cutoff = (datetime.now() - timedelta(days=days)).isoformat()
    cat_set = set(c.strip() for c in categories.split(",") if c.strip()) if categories else None
    entries = []

    # 1. Meetings (termine) — exclude private meetings and categories with show_in_stats=0 (#394, #417)
    if not cat_set or "termine" in cat_set:
        rows = conn.execute(
            """SELECT m.id, m.meeting_date as event_date, m.title, m.meeting_type,
                      a.company as app_company, a.title as app_title, m.application_id,
                      m.is_private, m.category_id, mc.show_in_stats as cat_show_in_stats
               FROM application_meetings m
               LEFT JOIN applications a ON m.application_id = a.id
               LEFT JOIN meeting_categories mc ON m.category_id = mc.id
               WHERE m.meeting_date >= ? AND (m.profile_id=? OR m.profile_id IS NULL)
               ORDER BY m.meeting_date DESC""",
            (cutoff, pid),
        ).fetchall()
        for r in rows:
            r = dict(r)
            # Skip private meetings and categories with show_in_stats=0 (#394, #417)
            if r.get("is_private"):
                continue
            if r.get("cat_show_in_stats") == 0:
                continue
            label = r.get("title") or r.get("meeting_type") or "Termin"
            entries.append({
                "id": r["id"], "category": "termine", "event_date": r["event_date"],
                "title": label, "subtitle": f"{r.get('app_company', '')} — {r.get('app_title', '')}".strip(" —"),
                "link_type": "bewerbung", "link_id": r.get("application_id"),
            })

    # 2. Applications (bewerbungen) — applied_at events
    if not cat_set or "bewerbungen" in cat_set:
        rows = conn.execute(
            """SELECT id, title, company, applied_at, status, is_imported
               FROM applications
               WHERE COALESCE(applied_at, created_at) >= ?
                 AND (profile_id=? OR profile_id IS NULL)
               ORDER BY COALESCE(applied_at, created_at) DESC""",
            (cutoff, pid),
        ).fetchall()
        for r in rows:
            r = dict(r)
            date = r.get("applied_at") or r.get("created_at") or ""
            entries.append({
                "id": r["id"], "category": "bewerbungen", "event_date": date,
                "title": f"Bewerbung: {r['company']}" + (f" — {r['title']}" if r.get("title") else ""),
                "subtitle": r.get("status", ""),
                "link_type": "bewerbung", "link_id": r["id"],
                "is_imported": bool(r.get("is_imported")),
            })

    # 3. Follow-ups
    if not cat_set or "followups" in cat_set:
        rows = conn.execute(
            """SELECT f.id, f.scheduled_date as event_date, f.follow_up_type,
                      f.status, a.company as app_company, a.title as app_title, f.application_id
               FROM follow_ups f
               LEFT JOIN applications a ON f.application_id = a.id
               WHERE f.scheduled_date >= ?
                 AND (a.profile_id=? OR a.profile_id IS NULL)
               ORDER BY f.scheduled_date DESC""",
            (cutoff, pid),
        ).fetchall()
        for r in rows:
            r = dict(r)
            label = {"nachfass": "Nachfassen", "erinnerung": "Erinnerung"}.get(r.get("follow_up_type", ""), r.get("follow_up_type", ""))
            entries.append({
                "id": r["id"], "category": "followups", "event_date": r["event_date"],
                "title": label, "subtitle": f"{r.get('app_company', '')} — {r.get('app_title', '')}".strip(" —"),
                "link_type": "bewerbung", "link_id": r.get("application_id"),
                "status": r.get("status", ""),
            })

    # 4. Documents (incoming emails and uploads)
    if not cat_set or "dokumente" in cat_set:
        rows = conn.execute(
            """SELECT d.id, d.created_at as event_date, d.filename, d.doc_type,
                      a.company as app_company, a.title as app_title, d.linked_application_id
               FROM documents d
               LEFT JOIN applications a ON d.linked_application_id = a.id
               WHERE d.created_at >= ? AND (d.profile_id=? OR d.profile_id IS NULL)
               ORDER BY d.created_at DESC""",
            (cutoff, pid),
        ).fetchall()
        for r in rows:
            r = dict(r)
            entries.append({
                "id": r["id"], "category": "dokumente", "event_date": r["event_date"],
                "title": r.get("filename", "Dokument"), "subtitle": r.get("doc_type", ""),
                "link_type": "dokument" if not r.get("linked_application_id") else "bewerbung",
                "link_id": r.get("linked_application_id") or r["id"],
            })

    # Sort all entries by date descending
    entries.sort(key=lambda x: x.get("event_date", ""), reverse=True)

    return {
        "entries": entries,
        "total": len(entries),
        "days": days,
    }


@app.get("/api/meetings/{meeting_id}")
async def api_get_meeting(meeting_id: str):
    """Get a single meeting."""
    row = _get_meeting_row_for_active_profile(meeting_id)
    if not row:
        return JSONResponse({"error": "Termin nicht gefunden"}, status_code=404)
    return dict(row)


@app.put("/api/meetings/{meeting_id}")
async def api_update_meeting(meeting_id: str, request: Request):
    """Update a meeting."""
    data = await request.json()
    profile_id = _get_active_profile_id()
    if not profile_id:
        return JSONResponse({"error": "Termin nicht gefunden"}, status_code=404)
    if not _db.update_meeting(meeting_id, data, profile_id=profile_id):
        return JSONResponse({"error": "Termin nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.delete("/api/meetings/{meeting_id}")
async def api_delete_meeting(meeting_id: str):
    """Cancel/delete a meeting."""
    profile_id = _get_active_profile_id()
    if not profile_id:
        return JSONResponse({"error": "Termin nicht gefunden"}, status_code=404)
    if not _db.delete_meeting(meeting_id, profile_id=profile_id):
        return JSONResponse({"error": "Termin nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.post("/api/meetings")
async def api_create_meeting(request: Request):
    """Manually create a meeting, optionally linked to an application (#394)."""
    data = await request.json()
    app_id = data.get("application_id")
    meeting_date = data.get("meeting_date")
    if not meeting_date:
        return JSONResponse(
            {"error": "meeting_date ist erforderlich"},
            status_code=400,
        )
    if app_id and not _get_application_row_for_active_profile(app_id):
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    mid = _db.add_meeting({
        "application_id": app_id or None,
        "title": data.get("title", "Termin"),
        "meeting_date": meeting_date,
        "meeting_end": data.get("meeting_end"),
        "location": data.get("location", ""),
        "meeting_url": data.get("meeting_url"),
        "meeting_type": data.get("meeting_type", "sonstiges"),
        "platform": data.get("platform"),
        "notes": data.get("notes"),
        "is_private": data.get("is_private", False),
        "duration_minutes": data.get("duration_minutes"),
        "category_id": data.get("category_id"),
    })
    # Add timeline event only if linked to an application
    if app_id:
        _db.add_application_event(app_id, "termin_erstellt", f"Termin: {data.get('title', 'Termin')} am {meeting_date}")
    return {"status": "ok", "id": mid}


@app.get("/api/applications/{app_id}/meetings")
async def api_get_application_meetings(app_id: str):
    """List all meetings for a specific application."""
    profile_id = _get_active_profile_id()
    if not _get_application_row_for_active_profile(app_id):
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    meetings = _db.get_meetings_for_application(app_id, profile_id=profile_id)
    return {"meetings": meetings, "count": len(meetings)}


@app.get("/api/meetings/{meeting_id}/ics")
async def api_meeting_ics(meeting_id: str):
    """Export a single meeting as .ics file (#261, #263)."""
    row = _get_meeting_row_for_active_profile(meeting_id)
    if not row:
        return JSONResponse({"error": "Meeting nicht gefunden"}, status_code=404)

    m = dict(row)
    from datetime import datetime as _dt
    import uuid as _uuid

    # Build .ics content
    start = m.get("meeting_date", "")
    end = m.get("meeting_end") or ""
    title = m.get("title", "Termin")
    company = m.get("app_company", "")
    app_title = m.get("app_title", "")
    location = m.get("location", "")
    meeting_url = m.get("meeting_url", "")
    notes = m.get("notes", "") or ""
    app_id = m.get("app_id", "")

    # PBP-Link zur Bewerbung einbetten (#263)
    pbp_link = f"http://localhost:8200/bewerbungen?id={app_id}" if app_id else ""
    description_parts = []
    if company and app_title:
        description_parts.append(f"Bewerbung: {app_title} bei {company}")
    if pbp_link:
        description_parts.append(f"PBP-Link: {pbp_link}")
    if meeting_url:
        description_parts.append(f"Meeting-Link: {meeting_url}")
    if notes:
        description_parts.append(f"Notizen: {notes}")
    description = "\\n".join(description_parts)

    def _fmt_dt(iso_str):
        """Format ISO datetime to iCal DTSTART format."""
        if not iso_str:
            return None
        try:
            dt = _dt.fromisoformat(iso_str)
            return dt.strftime("%Y%m%dT%H%M%S")
        except (ValueError, TypeError):
            return None

    dt_start = _fmt_dt(start)
    if not dt_start:
        return JSONResponse({"error": "Ungültiges Meeting-Datum"}, status_code=400)
    dt_end = _fmt_dt(end) or _fmt_dt(start)  # fallback: same as start

    uid = f"{meeting_id}@pbp.local"
    now_stamp = _dt.now().strftime("%Y%m%dT%H%M%SZ")

    ics_lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//PBP Bewerbungs-Assistent//DE",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:{uid}",
        f"DTSTAMP:{now_stamp}",
        f"DTSTART:{dt_start}",
        f"DTEND:{dt_end}",
        f"SUMMARY:{title}" + (f" — {company}" if company else ""),
        f"DESCRIPTION:{description}",
    ]
    if location:
        ics_lines.append(f"LOCATION:{location}")
    if meeting_url:
        ics_lines.append(f"URL:{meeting_url}")
    ics_lines.extend(["END:VEVENT", "END:VCALENDAR"])

    ics_content = "\r\n".join(ics_lines)

    from starlette.responses import Response
    return Response(
        content=ics_content,
        media_type="text/calendar",
        headers={
            "Content-Disposition": f'attachment; filename="termin-{meeting_id[:8]}.ics"',
        },
    )


# === Meeting Categories (#417) ===

@app.get("/api/meeting-categories")
async def api_get_meeting_categories():
    """List all meeting categories for the active profile."""
    _db.ensure_system_categories()
    categories = _db.get_meeting_categories()
    return {"categories": categories}


@app.post("/api/meeting-categories")
async def api_create_meeting_category(request: Request):
    """Create a custom meeting category."""
    data = await request.json()
    name = (data.get("name") or "").strip()
    if not name:
        return JSONResponse({"error": "Name ist erforderlich"}, status_code=400)
    cid = _db.add_meeting_category({
        "name": name,
        "color": data.get("color", "#3b82f6"),
        "show_in_stats": data.get("show_in_stats", True),
    })
    return {"status": "ok", "id": cid}


@app.put("/api/meeting-categories/{category_id}")
async def api_update_meeting_category(category_id: str, request: Request):
    """Update a meeting category (name, color, show_in_stats)."""
    data = await request.json()
    if not _db.update_meeting_category(category_id, data):
        return JSONResponse({"error": "Kategorie nicht gefunden oder Systemkategorie"}, status_code=404)
    return {"status": "ok"}


@app.delete("/api/meeting-categories/{category_id}")
async def api_delete_meeting_category(category_id: str, request: Request):
    """Delete a custom category. Optional: reassign_to in body."""
    try:
        data = await request.json()
    except Exception:
        data = {}
    reassign_to = data.get("reassign_to")
    if not _db.delete_meeting_category(category_id, reassign_to=reassign_to):
        return JSONResponse({"error": "Kategorie nicht gefunden oder Systemkategorie"}, status_code=400)
    return {"status": "ok"}


@app.put("/api/jobs/{job_hash}/score")
async def api_update_job_score(job_hash: str, request: Request):
    data = await request.json()
    score = int(data.get("score", 0))
    _db.update_job_score(job_hash, score)
    return {"status": "ok", "score": score}


@app.put("/api/jobs/{job_hash}/pin")
async def api_toggle_job_pin(job_hash: str):
    new_state = _db.toggle_job_pin(job_hash)
    return {"status": "ok", "is_pinned": new_state}


@app.put("/api/jobs/{job_hash}")
async def api_update_job(job_hash: str, request: Request):
    """Update editable fields of a job (#90)."""
    data = await request.json()
    _db.update_job(job_hash, data)
    return {"status": "ok"}


@app.post("/api/applications/{app_id}/fit-analyse")
async def api_save_app_fit_analyse(app_id: str, request: Request):
    """Save fit analysis result to an application (#84)."""
    profile_id = _get_active_profile_id()
    data = await request.json()
    if not profile_id or not _db.save_fit_analyse(app_id, data, profile_id=profile_id):
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    return {"status": "ok"}


@app.get("/api/applications/zombies")
async def api_zombie_applications(days: int = 60):
    """Detect zombie applications â€” stuck in early status without activity (#130)."""
    zombies = _db.get_zombie_applications(days_threshold=days)
    return {"zombies": zombies, "count": len(zombies), "threshold_days": days}


@app.get("/api/applications/export")
async def api_export_applications(
    format: str = "pdf",
    from_: str = "",
    to: str = "",
    request: Request = None,
):
    """Export applications as PDF or Excel.

    Query params:
        format: 'pdf' (default) or 'xlsx'
        from:   Start-Datum (YYYY-MM-DD), optional
        to:     End-Datum (YYYY-MM-DD), optional
    """
    from .export_report import generate_application_report
    # FastAPI kann 'from' nicht als Parameter-Name nutzen -> aus request holen
    zeitraum_von = (request.query_params.get("from") if request else "") or ""
    zeitraum_bis = to or ""
    report_data = _db.get_report_data()
    profile = _db.get_profile()
    from .database import get_data_dir
    export_dir = get_data_dir() / "export"
    export_dir.mkdir(exist_ok=True)

    if format == "xlsx":
        try:
            from .export_report import generate_excel_report
            path = export_dir / "bewerbungsbericht.xlsx"
            generate_excel_report(report_data, profile, path,
                                   zeitraum_von=zeitraum_von, zeitraum_bis=zeitraum_bis)
            return FileResponse(
                str(path),
                filename="Bewerbungsbericht.xlsx",
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        except ImportError:
            return JSONResponse(
                {"error": "openpyxl nicht installiert. Installiere mit: pip install openpyxl"},
                status_code=501
            )
    else:
        path = export_dir / "bewerbungsbericht.pdf"
        generate_application_report(report_data, profile, path,
                                    zeitraum_von=zeitraum_von, zeitraum_bis=zeitraum_bis)
        return FileResponse(
            str(path),
            filename="Bewerbungsbericht.pdf",
            media_type="application/pdf"
        )


@app.get("/api/search-criteria")
async def api_search_criteria():
    return _db.get_search_criteria()


@app.post("/api/search-criteria")
async def api_set_criteria(request: Request):
    data = await request.json()
    for key, value in data.items():
        _db.set_search_criteria(key, value)
    return {"status": "ok"}


@app.get("/api/dismiss-reasons")
async def api_dismiss_reasons():
    """Get all dismiss reasons for the dismiss dialog (#108, #120)."""
    return _db.get_dismiss_reasons()


@app.post("/api/dismiss-reasons")
async def api_add_dismiss_reason(request: Request):
    """Add a custom dismiss reason (#108)."""
    data = await request.json()
    label = (data.get("label") or "").strip()
    if not label:
        return JSONResponse({"error": "Label ist erforderlich"}, status_code=400)
    rid = _db.add_dismiss_reason(label)
    return {"status": "ok", "id": rid}


@app.get("/api/blacklist")
async def api_blacklist():
    return _db.get_blacklist()


@app.post("/api/blacklist")
async def api_add_blacklist(request: Request):
    data = await request.json()
    _db.add_to_blacklist(data["type"], data["value"], data.get("reason", ""))
    return {"status": "ok"}


@app.delete("/api/blacklist/{entry_id}")
async def api_delete_blacklist(entry_id: int):
    if _db.remove_blacklist_entry(entry_id):
        return {"status": "ok"}
    return JSONResponse({"error": "Blacklist-Eintrag nicht gefunden"}, status_code=404)


MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB


def _sanitize_upload_filename(raw_name: str) -> str:
    """Normalize uploaded filenames so relative paths from drag&drop stay safe."""
    candidate = str(raw_name or "").replace("\x00", "").strip()
    candidate = PurePosixPath(candidate).name
    candidate = PureWindowsPath(candidate).name
    candidate = candidate.replace("/", "_").replace("\\", "_").strip()
    return candidate or "upload.bin"


def _resolve_upload_filepath(doc_dir: Path, raw_name: str) -> tuple[str, Path]:
    """Resolve a safe target filepath and avoid collisions on duplicate names."""
    safe_name = _sanitize_upload_filename(raw_name)
    target = doc_dir / safe_name
    stem = target.stem or "upload"
    suffix = target.suffix
    counter = 1
    while target.exists():
        target = doc_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    return target.name, target


def _get_active_profile_document_dir() -> Path:
    """Use profile-specific storage to avoid filename collisions across profiles."""
    from .database import get_data_dir

    doc_dir = get_data_dir() / "dokumente"
    profile_id = _db.get_active_profile_id() if _db else None
    if profile_id:
        doc_dir = doc_dir / str(profile_id)
    doc_dir.mkdir(parents=True, exist_ok=True)
    return doc_dir


@app.post("/api/documents/upload")
async def api_upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("sonstiges"),
    position_id: str = Form(""),
    link_application_id: str = Form(""),
    create_application: str = Form(""),
):
    # Read with size check
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        return JSONResponse(
            {"error": f"Datei zu gross ({len(content) // 1024 // 1024} MB). Maximum: 50 MB."},
            status_code=413
        )

    incoming_name = file.filename or "upload.bin"
    # Reject Word temp files (~$...)
    if incoming_name.startswith("~$"):
        return JSONResponse(
            {"error": "Temporaere Word-Datei (~$...) wird nicht importiert."},
            status_code=400,
        )
    doc_dir = _get_active_profile_document_dir()
    stored_filename, filepath = _resolve_upload_filepath(doc_dir, incoming_name)
    with open(filepath, "wb") as f:
        f.write(content)

    # Try to extract text
    extracted = ""
    email_context = None
    fname = stored_filename.lower()
    try:
        extracted, email_context = _extract_document_text(filepath)
    except ImportError as exc:
        logger.warning("Text extraction failed for %s: %s", incoming_name, exc)
        if fname.endswith(".msg"):
            filepath.unlink(missing_ok=True)
            return JSONResponse(
                {
                    "error": (
                        "Outlook-Mails (.msg) werden in dieser Installation nicht unterstuetzt. "
                        "Das Paket 'extract-msg' fehlt oder konnte nicht installiert werden."
                    ),
                    "hinweis": (
                        "Bitte PBP neu installieren (INSTALLIEREN.bat). "
                        "Falls das Problem bestehen bleibt: "
                        "Die Mail in Outlook oeffnen und als .eml oder PDF speichern, "
                        "dann hier erneut hochladen. "
                        "(Datei > Speichern unter > 'Nur Text (*.eml)' oder PDF)"
                    ),
                },
                status_code=501,
            )
    except Exception as e:
        if fname.endswith((".msg", ".eml")):
            logger.warning("E-Mail extraction failed for %s: %s", incoming_name, e)
            filepath.unlink(missing_ok=True)
            return JSONResponse(
                {"error": f"E-Mail-Datei konnte nicht verarbeitet werden: {e}"},
                status_code=400,
            )
        logger.warning("Text extraction failed for %s: %s", incoming_name, e)

    # Smart detection: auto-detect doc_type if "sonstiges"
    if doc_type == "sonstiges":
        detected = _detect_doc_type(stored_filename, extracted)
        if detected:
            doc_type = detected

    did = _db.add_document({
        "filename": stored_filename,
        "filepath": str(filepath),
        "doc_type": doc_type,
        "extracted_text": extracted,
        "linked_position_id": position_id or None,
        "linked_application_id": link_application_id or (email_context or {}).get("match_application_id"),
    })

    # Auto-link to application if requested
    linked_app = None
    if link_application_id:
        try:
            _db.link_document_to_application(did, str(link_application_id))
            linked_app = str(link_application_id)
        except Exception as e:
            logger.warning("Failed to link doc %s to app %s: %s", did, link_application_id, e)
    elif email_context and email_context.get("match_application_id"):
        try:
            _db.link_document_to_application(did, email_context["match_application_id"])
            linked_app = email_context["match_application_id"]
        except Exception as e:
            logger.warning(
                "Failed to auto-link mail doc %s to app %s: %s",
                did,
                email_context["match_application_id"],
                e,
            )
    elif create_application:
        # Create new application from detected info
        try:
            import json as _json
            app_data = _json.loads(create_application)
            aid = _db.add_application({
                "title": app_data.get("title", ""),
                "company": app_data.get("company", ""),
                "status": "beworben",
                "bewerbungsart": "mit_dokumenten",
            })
            _db.link_document_to_application(did, aid)
            linked_app = aid
        except Exception as e:
            logger.warning("Failed to create app from doc: %s", e)

    if fname.endswith((".msg", ".eml")) and extracted.strip():
        _db.update_document_extraction_status(did, "basis_analysiert")

    # For email documents: apply full email intelligence (meetings, status, timeline)
    stored_meetings = []
    if email_context and linked_app:
        try:
            from .services.email_service import parse_email_file, extract_meetings_from_email

            parsed = parse_email_file(str(filepath))

            # Store meetings if detected
            meetings = extract_meetings_from_email(parsed)
            for m in meetings:
                if m.get("start"):
                    mid = _db.add_meeting({
                        "application_id": linked_app,
                        "title": m.get("title", "Termin"),
                        "meeting_date": m["start"],
                        "meeting_end": m.get("end"),
                        "location": m.get("location", ""),
                        "meeting_url": m.get("meeting_url"),
                        "platform": m.get("platform"),
                        "meeting_type": "interview",
                    })
                    stored_meetings.append({"id": mid, **m})

            # Add timeline event
            direction = email_context.get("direction", "eingang")
            subject = parsed.get("subject", "Ohne Betreff")
            if direction == "ausgang":
                event_note = f"Ausgehende Mail: {subject}"
            else:
                event_note = f"E-Mail: {subject}"
            _db.add_application_event(linked_app, f"email_{direction}", event_note)
        except Exception as e:
            logger.warning("Email intelligence for doc %s failed: %s", did, e)

    return {
        "status": "ok",
        "id": did,
        "filename": stored_filename,
        "doc_type": doc_type,
        "extracted_length": len(extracted),
        "linked_application": linked_app,
        "email_context": email_context,
        "meetings": [
            {k: v for k, v in m.items() if k not in ("payload",)}
            for m in stored_meetings
        ] if stored_meetings else [],
    }


def _detect_doc_type(filename: str, text: str) -> str | None:
    """Auto-detect document type from filename and extracted text (#131)."""
    fname = filename.lower()
    text_lower = (text or "").lower()[:2000]

    # Special cases: known internal/reference documents
    if any(kw in fname for kw in ["master-wissen", "bewerbungs-master", "wissen"]):
        return "referenz"
    # Test/draft documents â†’ sonstiges
    if any(kw in fname for kw in ["test", "chaotisch", "draft", "entwurf", "tmp"]):
        return "sonstiges"
    # Templates/Vorlagen â€” generic CVs not tied to a specific application
    if any(kw in fname for kw in ["template", "vorlage", "standard", "generic", "muster"]):
        return "vorlage"

    # Filename patterns (order matters â€” more specific first)
    if any(kw in fname for kw in ["vorbereitung", "preparation", "interview-prep"]):
        return "vorbereitung"
    if any(kw in fname for kw in ["projektliste", "project-list", "projekte"]):
        return "projektliste"
    if any(kw in fname for kw in ["stellenbeschreibung", "job-description", "ausschreibung"]):
        return "stellenbeschreibung"
    if any(kw in fname for kw in ["lebenslauf", "cv", "resume", "curriculum", "vita"]):
        return "lebenslauf"
    if any(kw in fname for kw in ["anschreiben", "cover", "motivations"]):
        return "anschreiben"
    if any(kw in fname for kw in ["zeugnis", "arbeitszeugnis"]):
        return "zeugnis"
    if any(kw in fname for kw in ["referenz", "reference", "empfehlung"]):
        return "referenz"
    if any(kw in fname for kw in ["zertifikat", "certificate", "bescheinigung"]):
        return "zertifikat"
    if any(kw in fname for kw in ["foto", "bild", "bewerbungsfoto", "portrait", "photo"]):
        return "foto"
    if any(kw in fname for kw in ["portfolio", "mappe", "arbeitsproben"]):
        return "portfolio"

    # .md files are rarely cover letters â€” treat as reference/sonstiges
    if fname.endswith(".md"):
        return "referenz"

    # Text content patterns
    if text_lower:
        cv_keywords = ["berufserfahrung", "ausbildung", "kenntnisse", "werdegang",
                        "beruflicher werdegang", "work experience", "education"]
        letter_keywords = ["sehr geehrte", "bewerbung als", "mit grossem interesse",
                           "hiermit bewerbe", "ihre stellenanzeige", "dear"]
        project_keywords = ["auftraggeber", "technologien", "projektbeschreibung",
                            "projektlaufzeit", "projektzeitraum", "kunde"]
        cv_hits = sum(1 for kw in cv_keywords if kw in text_lower)
        letter_hits = sum(1 for kw in letter_keywords if kw in text_lower)
        project_hits = sum(1 for kw in project_keywords if kw in text_lower)
        if project_hits >= 2:
            return "projektliste"
        if letter_hits >= 2:
            return "anschreiben"
        if cv_hits >= 3:
            return "lebenslauf"

    return None


@app.post("/api/documents/analyze-filename")
async def api_analyze_filename(request: Request):
    """Analyze filename to detect document type and match to existing applications."""
    import re
    data = await request.json()
    filename = data.get("filename", "")
    fname = filename.lower()

    # Detect document type from filename
    doc_type = _detect_doc_type(filename, "") or "sonstiges"

    # Extract company/recipient from filename
    # Common patterns: "Anschreiben_Firma_2026-03-01.pdf", "CV_Firma_Stadt.docx",
    # "Bewerbung Firma Stellentitel.pdf"
    company_hint = ""
    date_hint = ""

    # Remove extension and common prefixes
    base = re.sub(r'\.\w{2,4}$', '', filename)
    # Remove common doc type words
    cleaned = re.sub(
        r'(?i)(anschreiben|bewerbung|lebenslauf|cv|resume|cover.?letter|motivations?schreiben)',
        '', base
    )
    # Extract date (YYYY-MM-DD, DD.MM.YYYY, YYYYMMDD)
    date_match = re.search(r'(\d{4}[-_.]\d{2}[-_.]\d{2}|\d{2}[.]\d{2}[.]\d{4}|\d{8})', cleaned)
    if date_match:
        date_hint = date_match.group(1)
        cleaned = cleaned.replace(date_match.group(0), "")

    # What remains after cleanup = likely company/position name
    parts = re.split(r'[_\-\s]+', cleaned.strip())
    parts = [p.strip() for p in parts if p.strip() and len(p.strip()) > 1]
    if parts:
        company_hint = " ".join(parts)

    # Match against existing applications
    matching_apps = []
    if company_hint:
        apps = _db.get_applications()
        hint_lower = company_hint.lower()
        for app in apps:
            app_company = (app.get("company") or "").lower()
            app_title = (app.get("title") or "").lower()
            if (app_company and any(w in app_company for w in hint_lower.split())) or \
               (app_title and any(w in app_title for w in hint_lower.split())):
                matching_apps.append({
                    "id": app["id"],
                    "title": app.get("title", ""),
                    "company": app.get("company", ""),
                    "status": app.get("status", ""),
                })

    return {
        "detected_type": doc_type,
        "company_hint": company_hint,
        "date_hint": date_hint,
        "matching_applications": matching_apps,
    }


@app.get("/api/sources")
async def api_sources():
    """List all available job sources with active status and health (#499)."""
    from .job_scraper import SOURCE_REGISTRY
    active = _db.get_profile_setting("active_sources", None)
    if active is None and _db.get_active_profile_id():
        active = get_default_active_source_keys(SOURCE_REGISTRY)
        _db.set_profile_setting("active_sources", active)
    active = active or []
    rows = build_source_rows(SOURCE_REGISTRY, active)
    health_by_name = {h["scraper_name"]: h for h in _db.get_scraper_health()}
    for row in rows:
        h = health_by_name.get(row["key"])
        if not h:
            row["health"] = None
            continue
        last_count = h.get("last_count") or 0
        consec_silent = h.get("consecutive_silent") or 0
        consec_fail = h.get("consecutive_failures") or 0
        if not h.get("is_active"):
            badge = "deaktiviert"
        elif consec_fail > 0:
            badge = "fehler"
        elif consec_silent >= 3:
            badge = "stumm"
        elif last_count > 0:
            badge = "ok"
        elif h.get("last_run"):
            badge = "leer"
        else:
            badge = "nie"
        row["health"] = {
            "last_run": h.get("last_run"),
            "last_count": last_count,
            "last_status_detail": h.get("last_status_detail"),
            "consecutive_silent": consec_silent,
            "consecutive_failures": consec_fail,
            "avg_time_s": h.get("avg_time_s") or 0,
            "is_active_health": bool(h.get("is_active")),
            "badge": badge,
        }
    return rows


@app.post("/api/sources")
async def api_set_sources(request: Request):
    """Set active job sources."""
    data = await request.json()
    active = data.get("active_sources", [])
    _db.set_profile_setting("active_sources", active)
    return {"status": "ok", "active_sources": active}


@app.post("/api/sources/{source_key}/login")
async def api_start_source_login(source_key: str):
    """Start the manual first-login flow for login-protected job sources."""
    from .job_scraper import SOURCE_REGISTRY

    source = SOURCE_REGISTRY.get(source_key)
    if source is None:
        return JSONResponse({"error": "Quelle nicht gefunden"}, status_code=404)
    if not source.get("login_erforderlich"):
        return JSONResponse({"error": "Für diese Quelle ist kein Login erforderlich"}, status_code=400)

    job_id = _db.create_background_job("quellen_login", {"source": source_key})

    def _progress(message: str, progress: int = 35):
        _db.update_background_job(job_id, "running", progress=progress, message=message)

    def _run_login():
        try:
            if source_key == "linkedin":
                from .job_scraper.linkedin import ensure_linkedin_session

                ready = ensure_linkedin_session(progress_callback=lambda message: _progress(message, 40))
            elif source_key == "xing":
                from .job_scraper.xing import ensure_xing_session

                ready = ensure_xing_session(progress_callback=lambda message: _progress(message, 40))
            else:
                # v1.6.5 (#541): klare Fehlermeldung statt generischem Exception-Text.
                # Falls ein zukuenftiger Source `login_erforderlich=True` hat, aber
                # ohne Implementation hier, kriegt der User wenigstens einen
                # nuetzlichen Hinweis statt eines kryptischen Fehlers.
                raise ValueError(
                    f"Quelle '{source_key}' braucht keinen Login-Flow im Dashboard — "
                    f"nutze sie direkt ueber jobsuche_starten oder die zustaendige "
                    f"Browser-/Chrome-Extension. Falls du hier landest, war "
                    f"login_erforderlich faelschlich auf True gesetzt — bitte als "
                    f"Issue auf GitHub melden."
                )

            if ready:
                _db.update_background_job(
                    job_id,
                    "fertig",
                    progress=100,
                    message=f"{source['name']}: Login abgeschlossen.",
                    result={"source": source_key, "session_ready": True},
                )
            else:
                _db.update_background_job(
                    job_id,
                    "fehler",
                    progress=100,
                    message=f"{source['name']}: Login wurde nicht abgeschlossen.",
                    result={"source": source_key, "session_ready": False},
                )
        except Exception as exc:
            logger.error("Login-Start für %s fehlgeschlagen: %s", source_key, exc, exc_info=True)
            _db.update_background_job(
                job_id,
                "fehler",
                progress=100,
                message=str(exc),
                result={"source": source_key, "session_ready": False},
            )

    threading.Thread(target=_run_login, daemon=True).start()

    return {
        "status": "gestartet",
        "job_id": job_id,
        "source": source_key,
        "nachricht": f"{source['name']}: Browser wird für den Login gestartet, falls noch keine Session vorhanden ist.",
    }


@app.get("/api/cv/export/{fmt}")
async def api_export_cv(fmt: str):
    """Export CV as DOCX or PDF."""
    profile = _db.get_profile()
    if not profile:
        return JSONResponse({"error": "Kein Profil vorhanden"}, status_code=404)

    from .database import get_data_dir
    from .export import generate_cv_docx, generate_cv_pdf

    export_dir = get_data_dir() / "export"
    export_dir.mkdir(exist_ok=True)
    name_slug = (profile.get("name") or "lebenslauf").replace(" ", "_").lower()

    if fmt == "docx":
        path = export_dir / f"lebenslauf_{name_slug}.docx"
        generate_cv_docx(profile, path)
        return FileResponse(str(path), filename=path.name,
                          media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    elif fmt == "pdf":
        path = export_dir / f"lebenslauf_{name_slug}.pdf"
        generate_cv_pdf(profile, path)
        return FileResponse(str(path), filename=path.name, media_type="application/pdf")
    return JSONResponse({"error": "Format muss 'docx' oder 'pdf' sein"}, status_code=400)


@app.post("/api/cover-letter/export/{fmt}")
async def api_export_cover_letter(fmt: str, request: Request):
    """Export cover letter as DOCX or PDF."""
    data = await request.json()
    text = data.get("text", "")
    stelle = data.get("stelle", "")
    firma = data.get("firma", "")
    if not text:
        return JSONResponse({"error": "Kein Anschreiben-Text angegeben"}, status_code=400)

    profile = _db.get_profile() or {}

    from .database import get_data_dir
    from .export import generate_cover_letter_docx, generate_cover_letter_pdf

    export_dir = get_data_dir() / "export"
    export_dir.mkdir(exist_ok=True)
    firma_slug = (firma or "bewerbung").replace(" ", "_").lower()

    if fmt == "docx":
        path = export_dir / f"anschreiben_{firma_slug}.docx"
        generate_cover_letter_docx(profile, text, stelle, firma, path)
        return FileResponse(str(path), filename=path.name,
                          media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    elif fmt == "pdf":
        path = export_dir / f"anschreiben_{firma_slug}.pdf"
        generate_cover_letter_pdf(profile, text, stelle, firma, path)
        return FileResponse(str(path), filename=path.name, media_type="application/pdf")
    return JSONResponse({"error": "Format muss 'docx' oder 'pdf' sein"}, status_code=400)


@app.get("/api/background-jobs/{job_id}")
async def api_background_job(job_id: str):
    job = _db.get_background_job(job_id)
    if job is None:
        return JSONResponse({"error": "Not found"}, status_code=404)
    # Stale-Detection: stuck jobs > 15 min → mark as error (#265)
    if job.get("status") in ("running", "pending"):
        updated = job.get("updated_at") or job.get("created_at")
        if updated:
            from datetime import datetime, timedelta
            try:
                if datetime.now() - datetime.fromisoformat(updated) > timedelta(minutes=15):
                    _db.update_background_job(
                        job_id, "fehler",
                        message="Timeout: Job lief länger als 15 Minuten ohne Update (#265)")
                    job["status"] = "fehler"
            except (ValueError, TypeError):
                pass
    return job


@app.post("/api/jobsuche/start")
async def api_jobsuche_start(payload: dict = Body(default={})):
    """Startet eine Jobsuche direkt aus dem Dashboard (#461).

    Spiegelt die Logik des MCP-Tools `jobsuche_starten` — manuelle
    Quellen werden rausgefiltert, laufende Jobs verhindern Doppel-
    Starts, der eigentliche Scrape laeuft im Thread.
    """
    import threading
    from .tools.jobs import _MANUAL_SOURCES

    keywords = payload.get("keywords") or None
    quellen = payload.get("quellen") or []
    nur_remote = bool(payload.get("nur_remote"))
    max_entfernung_km = int(payload.get("max_entfernung_km") or 0)

    if not quellen:
        quellen = _db.get_profile_setting("active_sources", []) or []
    if not quellen:
        return JSONResponse(
            {
                "status": "keine_quellen",
                "nachricht": (
                    "Keine Job-Quellen aktiviert. Aktiviere Quellen unter "
                    "Einstellungen \u2192 Job-Quellen."
                ),
            },
            status_code=400,
        )

    manuelle = [q for q in quellen if q in _MANUAL_SOURCES]
    auto_quellen = [q for q in quellen if q not in _MANUAL_SOURCES]
    manuelle_info = {q: _MANUAL_SOURCES[q] for q in manuelle}

    if not auto_quellen:
        return JSONResponse(
            {
                "status": "nur_manuelle_quellen",
                "manuelle_quellen": manuelle_info,
                "nachricht": (
                    "Alle ausgewaehlten Quellen laufen nur ueber Claude-in-Chrome "
                    "oder sind deprecated \u2014 hier gibt es nichts zu automatisieren."
                ),
            },
            status_code=400,
        )

    existing = _db.get_running_background_job("jobsuche")
    if existing:
        return {
            "status": "laeuft_bereits",
            "job_id": existing["id"],
            "nachricht": "Eine Jobsuche laeuft bereits.",
        }

    params = {
        "keywords": keywords,
        "quellen": auto_quellen,
        "nur_remote": nur_remote,
        "max_entfernung_km": max_entfernung_km,
    }
    job_id = _db.create_background_job("jobsuche", params)

    def _run_search():
        try:
            from .job_scraper import run_search
            run_search(_db, job_id, params)
        except Exception as exc:
            logger.error("Jobsuche (Dashboard) fehlgeschlagen: %s", exc, exc_info=True)
            _db.update_background_job(job_id, "fehler", message=str(exc))

    thread = threading.Thread(target=_run_search, daemon=True)
    thread.start()

    def _timeout_watchdog():
        thread.join(timeout=600)
        if thread.is_alive():
            logger.warning("Jobsuche (Dashboard) Timeout nach 10min (Job %s)", job_id)
            _db.update_background_job(job_id, "fehler", message="Timeout nach 10 Minuten")

    threading.Thread(target=_timeout_watchdog, daemon=True).start()

    result = {
        "status": "gestartet",
        "job_id": job_id,
        "quellen": auto_quellen,
        "nachricht": (
            f"Jobsuche laeuft auf {len(auto_quellen)} Portalen. "
            "Fortschritt in der Sidebar-Statusanzeige."
        ),
    }
    if manuelle_info:
        result["manuelle_quellen"] = manuelle_info
    return result


@app.get("/api/jobsuche/running")
async def api_jobsuche_running():
    """Return whether a jobsuche background job is currently running."""
    job = _db.get_running_background_job("jobsuche")
    if not job:
        return {"running": False}
    # Stale-Job-Erkennung (#155): Job > 30 Minuten ohne Update â†’ abbrechen
    updated = job.get("updated_at") or job.get("created_at")
    if updated:
        from datetime import datetime, timedelta
        try:
            last_update = datetime.fromisoformat(updated)
            now = datetime.now()
            if now - last_update > timedelta(minutes=15):
                _db.update_background_job(
                    job["id"], "fehler", message="Timeout: Job lief länger als 15 Minuten ohne Update (#265)")
                logger.warning("Stale background job %s bereinigt (letztes Update: %s)", job["id"], updated)
                return {"running": False}
        except (ValueError, TypeError):
            pass
    return {
        "running": True,
        "job_id": job.get("id"),
        "status": job.get("status"),
        "progress": int(job.get("progress") or 0),
        "message": job.get("message") or "",
        "updated_at": updated,
    }


@app.get("/api/jobsuche/last")
async def api_jobsuche_last():
    """Return the most recently finished jobsuche job (#487 Status-Badge)."""
    job = _db.get_last_finished_background_job("jobsuche")
    if not job:
        return {"vorhanden": False}
    result = job.get("result") or {}
    neue = int(result.get("neue_stellen") or 0) if isinstance(result, dict) else 0
    timeout_quellen = 0
    if isinstance(result, dict):
        quellen = result.get("quellen") or {}
        if isinstance(quellen, dict):
            timeout_quellen = sum(
                1 for v in quellen.values()
                if isinstance(v, dict) and (v.get("status") == "timeout" or v.get("error"))
            )
    return {
        "vorhanden": True,
        "job_id": job.get("id"),
        "status": job.get("status"),
        "neue_stellen": neue,
        "timeout_quellen": timeout_quellen,
        "updated_at": job.get("updated_at"),
    }


# ============================================================
# SMART AUTO-EXTRACTION & PROFILE BACKUP (PBP v0.8.0)
# ============================================================

@app.get("/api/follow-ups")
async def api_follow_ups():
    """Get all follow-ups with due status."""
    follow_ups = _db.get_pending_follow_ups()
    from datetime import date
    today = date.today().isoformat()
    for fu in follow_ups:
        fu["faellig"] = fu.get("scheduled_date", "") <= today
    return {"follow_ups": follow_ups, "faellige": sum(1 for f in follow_ups if f.get("faellig"))}


@app.post("/api/follow-ups/{follow_up_id}/complete")
async def api_follow_up_complete(follow_up_id: str, payload: dict = Body(default={})):
    """Mark follow-up as erledigt (done). #453"""
    fu = _db.get_follow_up(follow_up_id)
    if not fu:
        return JSONResponse({"error": "follow_up_not_found"}, status_code=404)
    _db.complete_follow_up(follow_up_id, status="erledigt")
    notiz = (payload or {}).get("notiz") or ""
    if notiz and fu.get("application_id"):
        try:
            _db.add_application_note(fu["application_id"], f"Nachfass erledigt: {notiz}")
        except Exception:
            pass
    return {"status": "erledigt", "id": follow_up_id}


@app.post("/api/follow-ups/{follow_up_id}/dismiss")
async def api_follow_up_dismiss(follow_up_id: str, payload: dict = Body(default={})):
    """Mark follow-up as hinfaellig (no longer relevant). #453"""
    fu = _db.get_follow_up(follow_up_id)
    if not fu:
        return JSONResponse({"error": "follow_up_not_found"}, status_code=404)
    _db.complete_follow_up(follow_up_id, status="hinfaellig")
    grund = (payload or {}).get("grund") or ""
    if grund and fu.get("application_id"):
        try:
            _db.add_application_note(fu["application_id"], f"Nachfass hinfaellig: {grund}")
        except Exception:
            pass
    return {"status": "hinfaellig", "id": follow_up_id}


@app.put("/api/follow-ups/{follow_up_id}")
async def api_follow_up_reschedule(follow_up_id: str, payload: dict = Body(...)):
    """Update (reschedule/edit) a follow-up. #453"""
    fu = _db.get_follow_up(follow_up_id)
    if not fu:
        return JSONResponse({"error": "follow_up_not_found"}, status_code=404)
    allowed = {k: v for k, v in (payload or {}).items()
               if k in ("scheduled_date", "template", "follow_up_type") and v is not None}
    if not allowed:
        return JSONResponse({"error": "no_valid_fields"}, status_code=400)
    _db.update_follow_up(follow_up_id, allowed)
    return {"status": "aktualisiert", "id": follow_up_id, "updated": list(allowed.keys())}


@app.post("/api/applications/{app_id}/adopt-position")
async def api_adopt_position(app_id: str, payload: dict = Body(default={})):
    """Uebernimm Stelle/Firma als neue Profil-Position. #455 / v1.5.7"""
    app_row = _db.get_application(app_id)
    if not app_row:
        return JSONResponse({"error": "application_not_found"}, status_code=404)
    if not app_row.get("title") or not app_row.get("company"):
        return JSONResponse({"error": "application_without_title_or_company"}, status_code=400)
    from datetime import date as _date
    start_date = (payload or {}).get("start_date") or _date.today().isoformat()
    description = (payload or {}).get("description") or f"Uebernommen aus Bewerbung {app_id[:8]}"
    position_id = _db.add_position({
        "title": app_row["title"],
        "company": app_row["company"],
        "start_date": start_date,
        "end_date": "",
        "is_current": 1,
        "description": description,
    })
    try:
        _db.add_application_note(
            app_id,
            f"Position ins Profil uebernommen (position_id={position_id}, Start {start_date})."
        )
    except Exception:
        pass
    return {"status": "uebernommen", "position_id": position_id, "start_date": start_date}


@app.get("/api/salary-stats")
async def api_salary_stats():
    """Get salary statistics for dashboard."""
    stats = _db.get_salary_statistics()
    profile = _db.get_profile()
    prefs = get_profile_preferences(profile)
    if prefs:
        stats["deine_vorstellungen"] = {
            "min_gehalt": prefs.get("min_gehalt"),
            "ziel_gehalt": prefs.get("ziel_gehalt"),
            "min_tagessatz": prefs.get("min_tagessatz"),
        }
    return stats


@app.get("/api/next-steps")
async def api_next_steps():
    """Get personalized next action recommendations."""
    steps = _db.get_next_steps()
    return {"steps": steps}


@app.get("/api/rejection-patterns")
async def api_rejection_patterns():
    """Get rejection analysis data."""
    return _db.get_rejection_patterns()


@app.get("/api/profile/completeness")
async def api_profile_completeness():
    """Calculate profile completeness percentage."""
    return get_profile_completeness(_db.get_profile())


@app.get("/api/extractions")
async def api_extraction_history():
    """Get extraction history for the active profile."""
    profile_id = _db.get_active_profile_id()
    if not profile_id:
        return {"extractions": []}
    history = _db.get_extraction_history(profile_id=profile_id)
    for h in history:
        h["extracted_fields"] = json.loads(h.get("extracted_fields") or "{}")
        h["conflicts"] = json.loads(h.get("conflicts") or "[]")
        h["applied_fields"] = json.loads(h.get("applied_fields") or "{}")
    return {"extractions": history}


@app.get("/api/profile/export")
async def api_export_profile():
    """Export active profile as JSON file download."""
    from .database import get_data_dir
    profile_id = _db.get_active_profile_id()
    if not profile_id:
        return JSONResponse({"error": "Kein Profil vorhanden"}, status_code=404)

    data = _db.export_profile_json(profile_id)
    if not data:
        return JSONResponse({"error": "Profil nicht gefunden"}, status_code=404)

    name_slug = (data.get("name") or "profil").replace(" ", "_").lower()
    date_str = datetime.now().strftime("%Y%m%d")
    filename = f"profil_backup_{name_slug}_{date_str}.json"

    export_dir = get_data_dir() / "export"
    export_dir.mkdir(exist_ok=True)
    filepath = export_dir / filename
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8"
    )

    return FileResponse(str(filepath), filename=filename, media_type="application/json")


# v1.6.5 (#542): Log-Download fuer Bug-Reports.
# Pfad ist je nach Plattform anders + tief in AppData verschachtelt — User-
# Friction beim Bug-Report-Workflow. Endpoint macht's einen Klick weg.

@app.get("/api/system/logs/download")
async def api_download_logs():
    """Liefert die aktuelle pbp.log als Download — fuer Bug-Reports (#542)."""
    from .logging_config import get_log_path
    from datetime import datetime as _dt
    import os as _os
    log_path = get_log_path()
    if not log_path or not _os.path.isfile(str(log_path)):
        return JSONResponse(
            {"error": "Logfile nicht gefunden", "expected_path": str(log_path) if log_path else "(unbekannt)"},
            status_code=404,
        )
    timestamp = _dt.now().strftime("%Y-%m-%d_%H%M%S")
    return FileResponse(
        str(log_path),
        filename=f"pbp-log-{timestamp}.log",
        media_type="text/plain; charset=utf-8",
    )


@app.get("/api/system/logs/info")
async def api_logs_info():
    """Kompakte Info zum Logfile (Groesse, letzte Warnungen) — fuer Settings-UI."""
    from .logging_config import get_log_path
    import os as _os
    log_path = get_log_path()
    if not log_path or not _os.path.isfile(str(log_path)):
        return {"available": False}
    size_bytes = _os.path.getsize(str(log_path))
    # Letzte ~50 Zeilen einlesen, daraus WARNING/ERROR zaehlen
    warn_lines: list[str] = []
    err_count = 0
    warn_count = 0
    try:
        with open(str(log_path), "r", encoding="utf-8", errors="replace") as f:
            # Performant: letzten 64KB lesen
            try:
                f.seek(max(0, size_bytes - 65536))
                content = f.read()
            except (OSError, ValueError):
                content = f.read()
            for line in content.splitlines()[-200:]:
                if "ERROR" in line:
                    err_count += 1
                    if len(warn_lines) < 5:
                        warn_lines.append(line[:160])
                elif "WARNING" in line:
                    warn_count += 1
    except Exception as exc:
        logger.warning("Log-Info-Read fehlgeschlagen: %s", exc)
    return {
        "available": True,
        "size_bytes": size_bytes,
        "size_kb": round(size_bytes / 1024, 1),
        "path": str(log_path),
        "recent_errors": err_count,
        "recent_warnings": warn_count,
        "last_error_lines": warn_lines,
    }


@app.post("/api/profile/import")
async def api_import_profile(file: UploadFile = File(...)):
    """Import a profile from JSON backup file."""
    content = await file.read()
    try:
        data = json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        return JSONResponse({"error": f"Ungueltige JSON-Datei: {e}"}, status_code=400)

    if "_export_meta" not in data:
        return JSONResponse(
            {"error": "Keine gueltige PBP-Backup-Datei (fehlende Metadaten)"},
            status_code=400
        )

    pid = _db.import_profile_json(data)
    return {"status": "ok", "id": pid, "name": data.get("name", "")}


@app.get("/api/backup")
async def api_backup():
    """Create a full backup of the pbp.db database file (#212)."""
    import shutil
    from .database import get_data_dir

    db_path = get_data_dir() / "pbp.db"
    if not db_path.exists():
        return JSONResponse({"error": "Keine Datenbank vorhanden"}, status_code=404)

    backup_dir = get_data_dir() / "backup"
    backup_dir.mkdir(exist_ok=True)
    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"pbp_backup_{date_str}.db"
    backup_path = backup_dir / backup_name

    # SQLite-safe backup via connection backup API
    import sqlite3
    src = sqlite3.connect(str(db_path))
    dst = sqlite3.connect(str(backup_path))
    src.backup(dst)
    dst.close()
    src.close()

    return FileResponse(
        str(backup_path),
        filename=backup_name,
        media_type="application/octet-stream",
    )


# === User Preferences (PBP v0.10.0) ===

@app.get("/api/user-preferences/{key}")
async def api_get_user_preference(key: str):
    value = _db.get_user_preference(key)
    return {"key": key, "value": value}


@app.post("/api/user-preferences/{key}")
async def api_set_user_preference(key: str, request: Request):
    data = await request.json()
    _db.set_user_preference(key, data.get("value"))
    return {"status": "ok"}


# === Search Status (PBP v0.10.0) ===

@app.get("/api/search-status")
async def api_search_status():
    return _get_search_status_payload()


# === Auto-Analyze Documents (v0.13.0) ===

@app.post("/api/dokumente-analysieren")
async def api_analyze_documents(request: Request):
    """Analyze uploaded documents and apply extracted data to the profile automatically."""
    import re as _re
    data = await request.json() if request.headers.get("content-length", "0") != "0" else {}
    force = data.get("force", False)

    profile = _db.get_profile()
    if not profile:
        return JSONResponse({"fehler": "Kein aktives Profil vorhanden."}, status_code=400)

    conn = _db.connect()
    pid = profile["id"]

    if force:
        rows = conn.execute(
            "SELECT * FROM documents WHERE profile_id=?",
            (pid,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM documents WHERE profile_id=? AND extraction_status IN ('nicht_extrahiert', 'basis_analysiert')",
            (pid,)
        ).fetchall()

    if not rows:
        return {"status": "keine_dokumente", "nachricht": "Keine neuen Dokumente zur Analyse gefunden."}

    combined_text = ""
    doc_ids = []
    empty_text_doc_ids = []
    for row in rows:
        doc = dict(row)
        extracted_text = (doc.get("extracted_text") or "").strip()
        if extracted_text:
            combined_text += f"\n--- {doc['filename']} ---\n{extracted_text}\n"
            doc_ids.append(doc["id"])
        else:
            empty_text_doc_ids.append(doc["id"])

    if not doc_ids:
        for doc_id in empty_text_doc_ids:
            _db.update_document_extraction_status(doc_id, "analysiert_leer")
        return {
            "status": "keine_daten",
            "nachricht": (
                f"{len(empty_text_doc_ids)} Dokument(e) enthalten keinen extrahierbaren Text "
                "und wurden als 'analysiert_leer' markiert."
            ),
            "analysiert_leer": len(empty_text_doc_ids),
        }

    # Rule-based extraction (no LLM needed)
    extracted = {}
    pers = {}
    email_match = _re.search(r'[\w.+-]+@[\w-]+\.[\w.-]+', combined_text)
    if email_match:
        pers["email"] = email_match.group()
    phone_match = _re.search(r'(?:Tel\.?|Telefon|Phone|Mobil|Handy)[:\s]*([+\d\s()/.-]{8,20})', combined_text, _re.IGNORECASE)
    if phone_match:
        pers["phone"] = phone_match.group(1).strip()
    addr_match = _re.search(r'(\w[\w\s.-]+(?:str(?:\.|ae|asse)|weg|gasse|platz|ring|allee)\s*\d+\w?)', combined_text, _re.IGNORECASE)
    if addr_match:
        pers["address"] = addr_match.group(1).strip()
    plz_city = _re.search(r'(\d{5})\s+([A-Za-zäöü][a-zäöü]+(?:\s+[a-zäöü]+)*)', combined_text)
    if plz_city:
        pers["plz"] = plz_city.group(1)
        pers["city"] = plz_city.group(2).strip()
    name_match = _re.search(r'^([A-Z][a-zäöü]+(?:\s+[A-Z][a-zäöü]+)+)\s*$', combined_text[:500], _re.MULTILINE)
    if name_match:
        pers["name"] = name_match.group(1).strip()
    bday_match = _re.search(r'(?:Geburtsdatum|geb\.|geboren)[:\s]*(\d{1,2}[./]\d{1,2}[./]\d{4})', combined_text, _re.IGNORECASE)
    if bday_match:
        pers["birthday"] = bday_match.group(1)
    nat_match = _re.search(r'(?:Nationalit(?:ä|ae)t|Staatsangeh(?:ö|oe)rigkeit)[:\s]*([A-Za-zäöü]+)', combined_text, _re.IGNORECASE)
    if nat_match:
        pers["nationality"] = nat_match.group(1).strip()
    if pers:
        extracted["persoenliche_daten"] = pers

    skill_patterns = _re.findall(
        r'(?:Kenntnisse|Skills|Kompetenzen|Faehigkeiten|Fähigkeiten|Technologien)[:\s]*([^\n]+(?:\n[^\n]+)*?)(?=\n\n|\n[A-Z])',
        combined_text, _re.IGNORECASE
    )
    if skill_patterns:
        skills = []
        for block in skill_patterns:
            for item in _re.split(r'[,;â€¢Â·|/\n]+', block):
                item = item.strip(' -â€“*')
                if 2 < len(item) < 50 and not _re.match(r'^\d+$', item):
                    skills.append({"name": item, "category": "Fachkenntnisse", "level": 3})
        if skills:
            extracted["skills"] = skills[:30]

    if not extracted:
        for doc_id in doc_ids:
            _db.update_document_extraction_status(doc_id, "basis_analysiert")
        for doc_id in empty_text_doc_ids:
            _db.update_document_extraction_status(doc_id, "analysiert_leer")
        return {
            "status": "keine_daten",
            "nachricht": (
                "Keine strukturierten Profildaten erkannt. "
                "Nutze im Profil den Button 'Profil-Prompt kopieren' oder den Analyse-Prompt des Dokuments "
                "fuer die Claude-gestuetzte Auswertung."
            ),
            "basis_analysiert": len(doc_ids),
            "analysiert_leer": len(empty_text_doc_ids),
        }

    eid = _db.add_extraction_history({
        "document_id": doc_ids[0],
        "profile_id": pid,
        "extraction_type": "auto_dashboard",
    })
    conn.execute("""
        UPDATE extraction_history SET extracted_fields=?, conflicts='[]', status='ausstehend'
        WHERE id=?
    """, (json.dumps(extracted, ensure_ascii=False), eid))
    conn.commit()

    # Apply extracted data directly
    applied = {}
    _DEFAULT_VALUES = {"Mein Profil", "mein profil", ""}

    if extracted.get("persoenliche_daten"):
        p = extracted["persoenliche_daten"]
        update_data = {}
        for field in ["name", "email", "phone", "address", "city", "plz",
                      "country", "birthday", "nationality", "summary"]:
            if field in p and p[field]:
                current = profile.get(field)
                if not current or str(current).strip().lower() in {v.lower() for v in _DEFAULT_VALUES}:
                    update_data[field] = p[field]
        if update_data:
            for key in ["name", "email", "phone", "address", "city", "plz",
                        "country", "birthday", "nationality", "summary", "informal_notes"]:
                if key not in update_data:
                    update_data[key] = profile.get(key)
            update_data["preferences"] = profile.get("preferences", {})
            _db.save_profile(update_data)
            applied["persoenliche_daten"] = list(update_data.keys())

    if extracted.get("skills"):
        existing_skills = [s.get("name", "").lower() for s in profile.get("skills", [])]
        added = 0
        for skill in extracted["skills"]:
            if skill.get("name", "").lower() not in existing_skills:
                _db.add_skill(skill)
                existing_skills.append(skill.get("name", "").lower())
                added += 1
        if added:
            applied["skills"] = added

    _db.update_extraction_history(eid, "angewendet", applied)
    for doc_id in doc_ids:
        _db.update_document_extraction_status(doc_id, "basis_analysiert")
    for doc_id in empty_text_doc_ids:
        _db.update_document_extraction_status(doc_id, "analysiert_leer")

    return {
        "status": "angewendet",
        "extraction_id": eid,
        "angewendet": applied,
        "nachricht": f"{len(applied)} Bereiche aktualisiert." if applied else "Keine neuen Daten zum Anwenden."
    }


# === Factory Reset (v0.10.1) ===

@app.post("/api/reset")
async def api_factory_reset(request: Request):
    """Factory reset â€” delete ALL data for clean testing."""
    data = await request.json()
    if data.get("confirm") != "RESET":
        return JSONResponse({"error": "Bestaetigung fehlt (confirm: RESET)"}, status_code=400)
    _db.reset_all_data()
    return {"status": "ok", "message": "Alle Daten gelöscht. Neustart empfohlen."}


@app.delete("/api/extraction-history/{entry_id}")
async def api_delete_extraction_entry(entry_id: str):
    """Delete a single extraction history entry."""
    conn = _db.connect()
    conn.execute("DELETE FROM extraction_history WHERE id=?", (entry_id,))
    conn.commit()
    return {"status": "ok"}


@app.delete("/api/extraction-history")
async def api_clear_extraction_history():
    """Clear all extraction history for the active profile."""
    pid = _db.get_active_profile_id()
    conn = _db.connect()
    if pid:
        conn.execute("DELETE FROM extraction_history WHERE profile_id=?", (pid,))
    else:
        conn.execute("DELETE FROM extraction_history")
    conn.commit()
    return {"status": "ok"}


# === Runtime Log Viewer (v0.10.1) ===

@app.get("/api/logs")
async def api_get_logs(lines: int = 100):
    """Return the last N lines of the runtime log."""
    from .logging_config import get_log_path
    log_path = get_log_path()
    if not log_path or not Path(log_path).exists():
        return {"lines": [], "path": log_path, "error": "Log-Datei nicht gefunden"}
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            all_lines = f.readlines()
        return {"lines": all_lines[-lines:], "path": log_path, "total": len(all_lines)}
    except Exception as e:
        return {"lines": [], "path": log_path, "error": str(e)}


# === Update Check (v1.4.0, #286) ===

_update_cache = {"ts": 0, "data": None}

@app.get("/api/update-check")
async def api_update_check():
    """Check GitHub for newer PBP releases (cached 1h)."""
    import time
    from . import __version__

    now = time.time()
    if _update_cache["data"] and now - _update_cache["ts"] < 3600:
        return _update_cache["data"]

    result = {"current_version": __version__, "latest_version": __version__,
              "update_available": False, "release_url": None}
    try:
        import httpx
        from packaging.version import Version
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(
                "https://api.github.com/repos/MadGapun/PBP/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                latest = data.get("tag_name", "").lstrip("v")
                if latest:
                    try:
                        is_newer = Version(latest) > Version(__version__)
                    except Exception:
                        is_newer = latest != __version__
                    if is_newer:
                        result["latest_version"] = latest
                        result["update_available"] = True
                        result["release_url"] = data.get("html_url")
                        result["release_name"] = data.get("name", "")
    except Exception as exc:
        logger.debug("update check failed: %s", exc)

    _update_cache["ts"] = now
    _update_cache["data"] = result
    return result


# === Health Info (v1.4.0, #290) ===

@app.get("/api/health")
async def api_health():
    """System health information for diagnostics."""
    import platform
    import sys
    from . import __version__
    from .database import get_data_dir
    from .heartbeat import get_connection_status

    data_dir = get_data_dir()
    db_path = data_dir / "pbp.db"
    db_size = db_path.stat().st_size if db_path.exists() else 0
    doc_dir = data_dir / "dokumente"
    doc_count = len(list(doc_dir.glob("*"))) if doc_dir.exists() else 0

    modules = {}
    for mod_name in ["httpx", "playwright", "docx", "pdfplumber", "openpyxl", "bs4"]:
        try:
            m = __import__(mod_name)
            modules[mod_name] = getattr(m, "__version__", "installed")
        except ImportError:
            modules[mod_name] = None

    return {
        "pbp_version": __version__,
        "python_version": platform.python_version(),
        "platform": platform.system(),
        "platform_detail": platform.platform(),
        "data_dir": str(data_dir),
        "db_size_bytes": db_size,
        "db_size_mb": round(db_size / (1024 * 1024), 2),
        "document_count": doc_count,
        "modules": modules,
        "mcp_connection": get_connection_status(),
    }


# === Scraper Health (#432) ===

@app.get("/api/scraper-health")
async def api_scraper_health():
    """Return per-scraper health status for dashboard display."""
    return {"scrapers": _db.get_scraper_health()}


@app.post("/api/scraper-health/{name}/toggle")
async def api_toggle_scraper(name: str, request: Request):
    """Activate or deactivate a scraper."""
    data = await request.json()
    active = data.get("active", True)
    _db.toggle_scraper(name, active)
    return {"status": "ok", "scraper": name, "active": active}


# === Privacy / Data Info (v1.4.0, #287) ===

@app.get("/api/privacy-info")
async def api_privacy_info():
    """Return data storage locations and statistics for privacy page."""
    import sys
    from .database import get_data_dir

    data_dir = get_data_dir()
    db_path = data_dir / "pbp.db"

    storage = {
        "data_dir": str(data_dir),
        "db_path": str(db_path),
        "db_exists": db_path.exists(),
        "db_size_bytes": db_path.stat().st_size if db_path.exists() else 0,
        "platform": sys.platform,
    }

    # Count stored items
    profile = _db.get_profile()
    counts = {
        "profiles": len(_db.list_profiles()) if hasattr(_db, "list_profiles") else (1 if profile else 0),
        "jobs": len(_db.get_active_jobs(exclude_applied=False)),
        "applications": len(_db.get_applications()),
        "documents": len(profile.get("documents", [])) if profile else 0,
    }

    subdirs = {}
    for name in ["dokumente", "export", "logs", "backup"]:
        sub = data_dir / name
        if sub.exists():
            files = list(sub.glob("*"))
            subdirs[name] = {"path": str(sub), "file_count": len(files)}
        else:
            subdirs[name] = {"path": str(sub), "file_count": 0}

    return {
        "storage": storage,
        "counts": counts,
        "subdirs": subdirs,
        "data_flow": {
            "local_only": ["Profildaten", "Bewerbungen", "Dokumente", "Stellenangebote", "Statistiken"],
            "sent_to_claude": ["Prompts (via Copy & Paste, du kontrollierst was gesendet wird)"],
            "external_requests": ["GitHub Hints (anonyme Abfrage, kein Login)", "Jobportale (nur bei aktiver Stellensuche)"],
        },
    }


@app.delete("/api/privacy-delete-all")
async def api_privacy_delete_all(request: Request):
    """Delete all user data (GDPR right to deletion)."""
    import shutil
    from .database import get_data_dir

    data = await request.json()
    if data.get("confirm") != "ALLES_LOESCHEN":
        return JSONResponse(
            {"error": "Bestaetigung fehlt (confirm: ALLES_LOESCHEN)"}, status_code=400
        )

    data_dir = get_data_dir()
    deleted = []

    # Delete database
    db_path = data_dir / "pbp.db"
    if db_path.exists():
        _db.close()
        db_path.unlink()
        deleted.append("Datenbank")

    # Delete documents
    for subdir in ["dokumente", "export"]:
        sub = data_dir / subdir
        if sub.exists():
            shutil.rmtree(sub)
            sub.mkdir()
            deleted.append(subdir.capitalize())

    return {"status": "ok", "deleted": deleted, "message": "Alle Daten geloescht. Bitte Dashboard neu starten."}


# === Export Package (v1.4.0, #289) ===

@app.get("/api/export-package")
async def api_export_package():
    """Create a ZIP package with all user data."""
    import shutil
    import tempfile
    import zipfile
    from .database import get_data_dir

    data_dir = get_data_dir()
    db_path = data_dir / "pbp.db"

    if not db_path.exists():
        return JSONResponse({"error": "Keine Daten vorhanden"}, status_code=404)

    tmp = tempfile.mkdtemp()
    zip_name = f"pbp_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
    zip_path = Path(tmp) / zip_name

    try:
        import sqlite3
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # Database (SQLite backup for consistency)
            backup_path = Path(tmp) / "pbp.db"
            src = sqlite3.connect(str(db_path))
            dst = sqlite3.connect(str(backup_path))
            src.backup(dst)
            dst.close()
            src.close()
            zf.write(backup_path, "pbp.db")

            # Documents
            doc_dir = data_dir / "dokumente"
            if doc_dir.exists():
                for f in doc_dir.iterdir():
                    if f.is_file():
                        zf.write(f, f"dokumente/{f.name}")

            # README
            zf.writestr("README.txt",
                "PBP Export-Paket\n"
                "================\n\n"
                "Inhalt:\n"
                "  - pbp.db: Deine Datenbank (Profil, Stellen, Bewerbungen)\n"
                "  - dokumente/: Deine hochgeladenen Dokumente\n\n"
                "Import:\n"
                "  1. PBP installieren (INSTALLIEREN.command / install.bat)\n"
                "  2. Dateien nach ~/.bewerbungs-assistent/ kopieren\n"
                "  3. Dashboard starten\n")

        return FileResponse(str(zip_path), filename=zip_name, media_type="application/zip")
    except Exception as exc:
        logger.error("Export failed: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


DASHBOARD_PORT = int(os.environ.get("BA_DASHBOARD_PORT", "8200"))

def _cleanup_stale_jobs(db):
    """Startup-Bereinigung: Alte stuck Background-Jobs auf 'fehler' setzen (#155)."""
    from datetime import datetime, timedelta
    try:
        conn = db.connect()
        rows = conn.execute(
            "SELECT id, updated_at, created_at FROM background_jobs "
            "WHERE status IN ('running', 'pending')"
        ).fetchall()
        now = datetime.now()
        cleaned = 0
        for row in rows:
            updated = row["updated_at"] or row["created_at"]
            if not updated:
                continue
            try:
                last = datetime.fromisoformat(updated)
                if now - last > timedelta(hours=1):
                    db.update_background_job(
                        row["id"], "fehler",
                        message="Startup-Bereinigung: Job war beim Neustart noch als laufend markiert")
                    cleaned += 1
            except (ValueError, TypeError):
                continue
        if cleaned:
            logger.info("Startup: %d veraltete Background-Jobs bereinigt", cleaned)
    except Exception as exc:
        logger.warning("Startup-Bereinigung fehlgeschlagen: %s", exc)


def start_dashboard(db_instance, port: int = None):
    """Start the dashboard web server (called from background thread).

    Port priority: port argument > BA_DASHBOARD_PORT env var > 8200
    """
    global _db
    _db = db_instance
    _cleanup_stale_jobs(db_instance)
    use_port = port or DASHBOARD_PORT
    logger.info("Dashboard startet auf http://localhost:%d", use_port)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=use_port, log_level="warning")


def _generate_dashboard_error_html(message: str, details: str = "", hint: str = "") -> str:
    """Generate a standalone error page when dashboard frontend is unavailable."""
    message = escape(message)
    details = escape(details)
    hint = escape(hint)
    details_block = f"<p><strong>Details:</strong> {details}</p>" if details else ""
    hint_block = f"<p><strong>Hinweis:</strong> {hint}</p>" if hint else ""
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PBP Dashboard-Fehler</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #0f172a;
    color: #e2e8f0;
    min-height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 24px;
}}
.card {{
    width: min(760px, 100%);
    background: #111827;
    border: 1px solid #334155;
    border-radius: 12px;
    padding: 24px;
}}
h1 {{ color: #f87171; font-size: 1.4rem; margin-bottom: 12px; }}
p {{ margin: 8px 0; line-height: 1.5; color: #cbd5e1; }}
code {{
    display: inline-block;
    background: #0b1220;
    border: 1px solid #243043;
    border-radius: 6px;
    padding: 2px 6px;
    color: #93c5fd;
}}
</style>
</head>
<body>
<main class="card" role="alert" aria-live="assertive">
  <h1>Dashboard-Fehler</h1>
  <p>{message}</p>
  {details_block}
  {hint_block}
</main>
</body>
</html>"""

