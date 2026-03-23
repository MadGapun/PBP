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
from datetime import datetime

from fastapi import FastAPI, Request, UploadFile, File, Form
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


# Request-Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Loggt alle API-Anfragen und Fehler."""
    import time
    start = time.time()
    try:
        response = await call_next(request)
        duration = time.time() - start
        if request.url.path.startswith("/api/"):
            logger.debug(
                "%s %s %d (%.1fms)",
                request.method,
                request.url.path,
                response.status_code,
                duration * 1000,
            )
        return response
    except Exception as e:
        logger.error("%s %s Fehler: %s", request.method, request.url.path, e)
        raise


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
    return build_workspace_summary(
        profile=_db.get_profile(),
        jobs=_db.get_active_jobs(exclude_applied=True),
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


# === API Endpoints ===

@app.get("/api/status")
async def api_status():
    from . import __version__

    profile = _db.get_profile()
    summary = summarize_profile(profile)
    return {
        "version": __version__,
        "has_profile": profile is not None,
        "profile_name": summary["name"],
        "active_jobs": len(_db.get_active_jobs()),
        "applications": len(_db.get_applications()),
        "statistics": _db.get_statistics(),
    }


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
    """Tagesimpuls fuer das Dashboard (#163)."""
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
    _db.update_job_title(title_id, data)
    return {"status": "ok"}


@app.delete("/api/job-title/{title_id}")
async def api_delete_job_title(title_id: str):
    _db.delete_job_title(title_id)
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
    _db.update_project(project_id, data)
    return {"status": "ok"}


@app.delete("/api/project/{project_id}")
async def api_delete_project(project_id: str):
    _db.delete_project(project_id)
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
    _db.update_position(position_id, data)
    return {"status": "ok"}


@app.delete("/api/position/{position_id}")
async def api_delete_position(position_id: str):
    _db.delete_position(position_id)
    return {"status": "ok"}


@app.put("/api/education/{education_id}")
async def api_update_education(education_id: str, request: Request):
    data = await request.json()
    _db.update_education(education_id, data)
    return {"status": "ok"}


@app.delete("/api/education/{education_id}")
async def api_delete_education(education_id: str):
    _db.delete_education(education_id)
    return {"status": "ok"}


@app.put("/api/skill/{skill_id}")
async def api_update_skill(skill_id: str, request: Request):
    data = await request.json()
    _db.update_skill(skill_id, data)
    return {"status": "ok"}


@app.delete("/api/skill/{skill_id}")
async def api_delete_skill(skill_id: str):
    _db.delete_skill(skill_id)
    return {"status": "ok"}


@app.delete("/api/document/{doc_id}")
async def api_delete_document(doc_id: str):
    _db.delete_document(doc_id)
    return {"status": "ok"}


@app.put("/api/document/{doc_id}/doc-type")
async def api_update_document_type(doc_id: str, request: Request):
    data = await request.json()
    new_type = data.get("doc_type", "sonstiges")
    conn = _db.connect()
    conn.execute("UPDATE documents SET doc_type=? WHERE id=?", (new_type, doc_id))
    conn.commit()
    return {"status": "ok"}


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
    supported = (".pdf", ".docx", ".doc", ".txt", ".md", ".csv", ".json", ".xml", ".rtf")

    file_iter = folder.rglob("*") if recursive else folder.glob("*")
    for fpath in file_iter:
        if not fpath.is_file() or fpath.suffix.lower() not in supported:
            continue
        # Skip Word temp files (~$...)
        if fpath.name.startswith("~$"):
            continue
        files_found += 1

        extracted = ""
        fname = fpath.name.lower()
        try:
            if fname.endswith(".pdf"):
                from pypdf import PdfReader
                reader = PdfReader(str(fpath))
                extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
            elif fname.endswith(".docx"):
                from docx import Document
                doc = Document(str(fpath))
                extracted = "\n".join(p.text for p in doc.paragraphs)
            elif fname.endswith((".txt", ".md", ".csv", ".json", ".xml", ".rtf")):
                extracted = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
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

            _db.add_document({
                "filename": fpath.name,
                "filepath": str(dest),
                "doc_type": doc_type,
                "extracted_text": extracted,
            })
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
    conn = _db.connect()
    events = [dict(r) for r in conn.execute(
        "SELECT * FROM application_events WHERE application_id = ? ORDER BY event_date DESC",
        (app_id,)
    ).fetchall()]
    app_row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    if not app_row:
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    application = _db._serialize_application_row(app_row) if hasattr(_db, '_serialize_application_row') else dict(app_row)

    # Enrich with job details if linked
    job = None
    if application.get("job_hash"):
        job = _db.get_job(application["job_hash"])

    # Get linked documents
    documents = _db.get_documents_for_application(app_id)

    return {
        "application": application,
        "events": events,
        "job": job,
        "documents": documents,
    }


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
    return fit_analyse(job, criteria)


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
    _db.update_application_status(app_id, data["status"], data.get("notes", ""))
    return {"status": "ok"}


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
        "employment_type",
    )
    conn = _db.connect()
    app_row = conn.execute("SELECT * FROM applications WHERE id=?", (app_id,)).fetchone()
    if not app_row:
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)

    changes = []
    for field in allowed:
        if field in data:
            old_val = app_row[field] if field in app_row.keys() else ""
            new_val = data[field]
            if str(old_val or "") != str(new_val or ""):
                changes.append(f"{field}: {old_val or '(leer)'} \u2192 {new_val or '(leer)'}")

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


@app.post("/api/applications/{app_id}/link-document")
async def api_link_document(app_id: str, request: Request):
    """Link an existing document to an application."""
    data = await request.json()
    doc_id = data.get("document_id")
    if not doc_id:
        return JSONResponse({"error": "document_id ist Pflicht"}, status_code=400)
    _db.link_document_to_application(doc_id, app_id)
    return {"status": "ok"}


@app.post("/api/applications/{app_id}/notes")
async def api_add_note(app_id: str, request: Request):
    """Add a timestamped note to an application."""
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
    data = await request.json()
    text = (data.get("text") or "").strip()
    if not text:
        return JSONResponse({"error": "Notiz-Text ist Pflicht"}, status_code=400)
    _db.update_application_event(event_id, app_id, text)
    return {"status": "ok"}


@app.delete("/api/applications/{app_id}/notes/{event_id}")
async def api_delete_note(app_id: str, event_id: int):
    """Delete a note from the application timeline."""
    _db.delete_application_event(event_id, app_id)
    return {"status": "ok"}


@app.post("/api/applications/{app_id}/snapshot")
async def api_snapshot_description(app_id: str, request: Request):
    """Fetch job description from URL and save as snapshot (#124).

    POST body: { "url": "https://..." }
    Uses simple HTTP fetch + HTML text extraction.
    """
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

    # Extract text from HTML (strip tags, decode entities)
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
async def api_documents():
    """List all documents for the active profile."""
    pid = _db.get_active_profile_id()
    docs = _db._get_documents(pid)
    return {"documents": docs}


@app.get("/api/documents/{doc_id}/download")
async def api_download_document(doc_id: str):
    """Download/preview a document by ID."""
    conn = _db.connect()
    row = conn.execute("SELECT filename, filepath FROM documents WHERE id=?", (doc_id,)).fetchone()
    if not row:
        return JSONResponse({"error": "Dokument nicht gefunden"}, status_code=404)
    filepath = Path(row["filepath"])
    if not filepath.exists():
        return JSONResponse({"error": "Datei nicht gefunden auf dem Dateisystem"}, status_code=404)
    import mimetypes
    mime, _ = mimetypes.guess_type(str(filepath))
    return FileResponse(str(filepath), filename=row["filename"], media_type=mime or "application/octet-stream")


@app.get("/api/statistics")
async def api_statistics():
    return _db.get_statistics()


@app.get("/api/stats/timeline")
async def api_stats_timeline(interval: str = "month"):
    """Application timeline grouped by interval (week/month/quarter/year)."""
    return _db.get_timeline_stats(interval)


@app.get("/api/stats/scores")
async def api_stats_scores():
    """Score distribution and trend data for charts."""
    return _db.get_score_stats()


@app.get("/api/stats/extended")
async def api_stats_extended():
    """Extended statistics: daily activity, response times, dismiss reasons, import vs new (#135)."""
    return _db.get_extended_stats()


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
    data = await request.json()
    app_id = data.get("application_id")
    if not app_id:
        return JSONResponse({"error": "application_id ist erforderlich"}, status_code=400)

    em = _db.get_email(email_id)
    if not em:
        return JSONResponse({"error": "E-Mail nicht gefunden"}, status_code=404)

    _db.update_email(email_id, {"application_id": app_id, "match_confidence": 1.0, "is_processed": 1})

    # Link any imported documents to the application
    for att in (em.get("attachments_meta") or []):
        doc_id = att.get("doc_id")
        if doc_id:
            try:
                _db.link_document_to_application(doc_id, app_id)
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
    data = await request.json()
    status = data.get("status")
    if not status:
        return JSONResponse({"error": "status ist erforderlich"}, status_code=400)

    em = _db.get_email(email_id)
    if not em:
        return JSONResponse({"error": "E-Mail nicht gefunden"}, status_code=404)
    if not em.get("application_id"):
        return JSONResponse({"error": "E-Mail ist keiner Bewerbung zugeordnet"}, status_code=400)

    app_id = em["application_id"]
    _db.update_application_status(app_id, status)
    _db.add_application_event(app_id, status, f"Status aus E-Mail: {em.get('subject', '')}")
    _db.update_email(email_id, {"is_processed": 1})

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
    em = _db.get_email(email_id)
    if not em:
        return JSONResponse({"error": "E-Mail nicht gefunden"}, status_code=404)
    return em


@app.get("/api/applications/{app_id}/emails")
async def api_get_application_emails(app_id: str):
    """List all emails linked to a specific application."""
    emails = _db.get_emails_for_application(app_id)
    return {"emails": emails, "count": len(emails)}


@app.delete("/api/emails/{email_id}")
async def api_delete_email(email_id: str):
    """Delete an email."""
    em = _db.get_email(email_id)
    if not em:
        return JSONResponse({"error": "E-Mail nicht gefunden"}, status_code=404)
    # Delete file from disk
    filepath = em.get("filepath")
    if filepath:
        try:
            Path(filepath).unlink(missing_ok=True)
        except Exception:
            pass
    _db.delete_email(email_id)
    return {"status": "ok"}


# === Meetings (#136) ===

@app.get("/api/meetings")
async def api_upcoming_meetings(days: int = 30):
    """Get upcoming meetings for the dashboard widget."""
    meetings = _db.get_upcoming_meetings(days=days)
    return {"meetings": meetings, "count": len(meetings)}


@app.get("/api/meetings/{meeting_id}")
async def api_get_meeting(meeting_id: str):
    """Get a single meeting."""
    conn = _db.connect()
    row = conn.execute(
        """SELECT m.*, a.title as app_title, a.company as app_company
           FROM application_meetings m
           LEFT JOIN applications a ON m.application_id = a.id
           WHERE m.id=?""",
        (meeting_id,),
    ).fetchone()
    if not row:
        return JSONResponse({"error": "Termin nicht gefunden"}, status_code=404)
    return dict(row)


@app.put("/api/meetings/{meeting_id}")
async def api_update_meeting(meeting_id: str, request: Request):
    """Update a meeting."""
    data = await request.json()
    _db.update_meeting(meeting_id, data)
    return {"status": "ok"}


@app.delete("/api/meetings/{meeting_id}")
async def api_delete_meeting(meeting_id: str):
    """Cancel/delete a meeting."""
    _db.delete_meeting(meeting_id)
    return {"status": "ok"}


@app.post("/api/meetings")
async def api_create_meeting(request: Request):
    """Manually create a meeting for an application."""
    data = await request.json()
    app_id = data.get("application_id")
    meeting_date = data.get("meeting_date")
    if not app_id or not meeting_date:
        return JSONResponse(
            {"error": "application_id und meeting_date sind erforderlich"},
            status_code=400,
        )
    mid = _db.add_meeting({
        "application_id": app_id,
        "title": data.get("title", "Termin"),
        "meeting_date": meeting_date,
        "meeting_end": data.get("meeting_end"),
        "location": data.get("location", ""),
        "meeting_url": data.get("meeting_url"),
        "meeting_type": data.get("meeting_type", "interview"),
        "platform": data.get("platform"),
        "notes": data.get("notes"),
    })
    # Add timeline event
    _db.add_application_event(app_id, "termin_erstellt", f"Termin: {data.get('title', 'Termin')} am {meeting_date}")
    return {"status": "ok", "id": mid}


@app.get("/api/applications/{app_id}/meetings")
async def api_get_application_meetings(app_id: str):
    """List all meetings for a specific application."""
    meetings = _db.get_meetings_for_application(app_id)
    return {"meetings": meetings, "count": len(meetings)}


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
    data = await request.json()
    _db.save_fit_analyse(app_id, data)
    return {"status": "ok"}


@app.get("/api/applications/zombies")
async def api_zombie_applications(days: int = 60):
    """Detect zombie applications — stuck in early status without activity (#130)."""
    zombies = _db.get_zombie_applications(days_threshold=days)
    return {"zombies": zombies, "count": len(zombies), "threshold_days": days}


@app.get("/api/applications/export")
async def api_export_applications(format: str = "pdf"):
    """Export applications as PDF or Excel."""
    from .export_report import generate_application_report
    report_data = _db.get_report_data()
    profile = _db.get_profile()
    from .database import get_data_dir
    export_dir = get_data_dir() / "export"
    export_dir.mkdir(exist_ok=True)

    if format == "xlsx":
        try:
            from .export_report import generate_excel_report
            path = export_dir / "bewerbungsbericht.xlsx"
            generate_excel_report(report_data, profile, path)
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
        generate_application_report(report_data, profile, path)
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
    fname = stored_filename.lower()
    try:
        if fname.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(str(filepath))
            extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif fname.endswith(".docx"):
            from docx import Document
            doc = Document(str(filepath))
            extracted = "\n".join(p.text for p in doc.paragraphs)
        elif fname.endswith((".txt", ".md", ".csv", ".json", ".xml", ".rtf")):
            extracted = content.decode("utf-8", errors="replace")
    except Exception as e:
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
    })

    # Auto-link to application if requested
    linked_app = None
    if link_application_id:
        try:
            _db.link_document_to_application(did, int(link_application_id))
            linked_app = int(link_application_id)
        except Exception as e:
            logger.warning("Failed to link doc %s to app %s: %s", did, link_application_id, e)
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

    return {
        "status": "ok",
        "id": did,
        "filename": stored_filename,
        "doc_type": doc_type,
        "extracted_length": len(extracted),
        "linked_application": linked_app,
    }


def _detect_doc_type(filename: str, text: str) -> str | None:
    """Auto-detect document type from filename and extracted text (#131)."""
    fname = filename.lower()
    text_lower = (text or "").lower()[:2000]

    # Special cases: known internal/reference documents
    if any(kw in fname for kw in ["master-wissen", "bewerbungs-master", "wissen"]):
        return "referenz"
    # Test/draft documents → sonstiges
    if any(kw in fname for kw in ["test", "chaotisch", "draft", "entwurf", "tmp"]):
        return "sonstiges"
    # Templates/Vorlagen — generic CVs not tied to a specific application
    if any(kw in fname for kw in ["template", "vorlage", "standard", "generic", "muster"]):
        return "vorlage"

    # Filename patterns (order matters — more specific first)
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

    # .md files are rarely cover letters — treat as reference/sonstiges
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
    """List all available job sources with active status."""
    from .job_scraper import SOURCE_REGISTRY
    active = _db.get_profile_setting("active_sources", None)
    if active is None and _db.get_active_profile_id():
        active = get_default_active_source_keys(SOURCE_REGISTRY)
        _db.set_profile_setting("active_sources", active)
    active = active or []
    return build_source_rows(SOURCE_REGISTRY, active)


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
                raise ValueError(f"Login-Flow für Quelle '{source_key}' ist nicht implementiert")

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
    return job


@app.get("/api/jobsuche/running")
async def api_jobsuche_running():
    """Return whether a jobsuche background job is currently running."""
    job = _db.get_running_background_job("jobsuche")
    if not job:
        return {"running": False}
    # Stale-Job-Erkennung (#155): Job > 30 Minuten ohne Update → abbrechen
    updated = job.get("updated_at") or job.get("created_at")
    if updated:
        from datetime import datetime, timedelta
        try:
            last_update = datetime.fromisoformat(updated)
            now = datetime.now()
            if now - last_update > timedelta(minutes=30):
                _db.update_background_job(
                    job["id"], "fehler", message="Timeout: Job lief länger als 30 Minuten ohne Update")
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
    filepath = export_dir / filename
    filepath.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8"
    )

    return FileResponse(str(filepath), filename=filename, media_type="application/json")


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
    addr_match = _re.search(r'(\w[\w\s.-]+(?:str(?:\.|aße|asse)|weg|gasse|platz|ring|allee)\s*\d+\w?)', combined_text, _re.IGNORECASE)
    if addr_match:
        pers["address"] = addr_match.group(1).strip()
    plz_city = _re.search(r'(\d{5})\s+([A-ZÄÖÜa-zäöü][a-zäöüß]+(?:\s+[a-zäöüß]+)*)', combined_text)
    if plz_city:
        pers["plz"] = plz_city.group(1)
        pers["city"] = plz_city.group(2).strip()
    name_match = _re.search(r'^([A-ZÄÖÜ][a-zäöüß]+(?:\s+[A-ZÄÖÜ][a-zäöüß]+)+)\s*$', combined_text[:500], _re.MULTILINE)
    if name_match:
        pers["name"] = name_match.group(1).strip()
    bday_match = _re.search(r'(?:Geburtsdatum|geb\.|geboren)[:\s]*(\d{1,2}[./]\d{1,2}[./]\d{4})', combined_text, _re.IGNORECASE)
    if bday_match:
        pers["birthday"] = bday_match.group(1)
    nat_match = _re.search(r'(?:Nationalit(?:ä|ae)t|Staatsangeh(?:ö|oe)rigkeit)[:\s]*([A-ZÄÖÜa-zäöüß]+)', combined_text, _re.IGNORECASE)
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
            for item in _re.split(r'[,;•·|/\n]+', block):
                item = item.strip(' -–*')
                if 2 < len(item) < 50 and not _re.match(r'^\d+$', item):
                    skills.append({"name": item, "category": "Fachkenntnisse", "level": 3})
        if skills:
            extracted["skills"] = skills[:30]

    if not extracted:
        for doc_id in [*doc_ids, *empty_text_doc_ids]:
            _db.update_document_extraction_status(doc_id, "analysiert_leer")
        return {"status": "keine_daten", "nachricht": "Keine strukturierten Profildaten erkannt. Nutze /profil_erweiterung in Claude für KI-gestuetzte Extraktion."}

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
    """Factory reset — delete ALL data for clean testing."""
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

