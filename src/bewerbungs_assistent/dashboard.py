"""Web Dashboard for Bewerbungs-Assistent.

Serves a browser-based UI on localhost:8200 for visual management.
Runs in a background thread alongside the MCP server.
"""

import json
import os
import logging
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

logger = logging.getLogger("bewerbungs_assistent.dashboard")

# Reference to shared database (set in start_dashboard)
_db = None

app = FastAPI(title="Bewerbungs-Assistent", docs_url=None, redoc_url=None)


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
            logger.info("%s %s %d (%.1fms)",
                        request.method, request.url.path,
                        response.status_code, duration * 1000)
        return response
    except Exception as e:
        logger.error("%s %s Fehler: %s", request.method, request.url.path, e)
        raise


# Static files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# === Pages ===

@app.get("/", response_class=HTMLResponse)
async def index():
    """Main dashboard page."""
    html_path = Path(__file__).parent / "templates" / "dashboard.html"
    if html_path.exists():
        return HTMLResponse(html_path.read_text(encoding="utf-8"))
    return HTMLResponse(_generate_dashboard_html())


# === API Endpoints ===

@app.get("/api/status")
async def api_status():
    profile = _db.get_profile()
    return {
        "has_profile": profile is not None,
        "profile_name": profile.get("name") if profile else None,
        "active_jobs": len(_db.get_active_jobs()),
        "applications": len(_db.get_applications()),
        "statistics": _db.get_statistics(),
    }


@app.get("/api/profile")
async def api_profile():
    profile = _db.get_profile()
    if profile is None:
        return JSONResponse({"error": "Kein Profil vorhanden"}, status_code=404)
    return profile


@app.post("/api/profile")
async def api_save_profile(request: Request):
    data = await request.json()
    pid = _db.save_profile(data)
    return {"status": "ok", "id": pid}


@app.post("/api/position")
async def api_add_position(request: Request):
    data = await request.json()
    pid = _db.add_position(data)
    return {"status": "ok", "id": pid}


@app.post("/api/project")
async def api_add_project(request: Request):
    data = await request.json()
    position_id = data.pop("position_id")
    pid = _db.add_project(position_id, data)
    return {"status": "ok", "id": pid}


@app.post("/api/education")
async def api_add_education(request: Request):
    data = await request.json()
    eid = _db.add_education(data)
    return {"status": "ok", "id": eid}


@app.post("/api/skill")
async def api_add_skill(request: Request):
    data = await request.json()
    sid = _db.add_skill(data)
    return {"status": "ok", "id": sid}


@app.delete("/api/position/{position_id}")
async def api_delete_position(position_id: str):
    _db.delete_position(position_id)
    return {"status": "ok"}


@app.delete("/api/education/{education_id}")
async def api_delete_education(education_id: str):
    _db.delete_education(education_id)
    return {"status": "ok"}


@app.delete("/api/skill/{skill_id}")
async def api_delete_skill(skill_id: str):
    _db.delete_skill(skill_id)
    return {"status": "ok"}


@app.delete("/api/document/{doc_id}")
async def api_delete_document(doc_id: str):
    _db.delete_document(doc_id)
    return {"status": "ok"}


@app.post("/api/documents/import-folder")
async def api_import_folder(request: Request):
    data = await request.json()
    folder_path = data.get("folder_path", "")
    if not folder_path:
        return JSONResponse({"error": "Kein Ordnerpfad angegeben"}, status_code=400)

    folder = Path(folder_path).resolve()
    # Security: block obvious system paths
    blocked = ["/etc", "/var", "/usr", "/bin", "/sbin", "/root", "/proc", "/sys",
               "C:\\Windows", "C:\\Program Files"]
    if any(str(folder).startswith(b) for b in blocked):
        return JSONResponse({"error": "Zugriff auf Systemverzeichnisse nicht erlaubt"}, status_code=403)
    if not folder.exists() or not folder.is_dir():
        return JSONResponse({"error": f"Ordner nicht gefunden: {folder_path}"}, status_code=404)

    from .database import get_data_dir
    doc_dir = get_data_dir() / "dokumente"

    import_apps = data.get("import_applications", True)
    import_docs = data.get("import_documents", True)

    files_found = 0
    docs_imported = 0
    apps_found = 0
    supported = (".pdf", ".docx", ".doc", ".txt")

    for fpath in folder.rglob("*"):
        if not fpath.is_file() or fpath.suffix.lower() not in supported:
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
            elif fname.endswith(".txt"):
                extracted = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            logger.warning("Import: Text extraction failed for %s: %s", fpath.name, e)

        # Determine doc type from filename
        doc_type = "sonstiges"
        fl = fname
        if any(k in fl for k in ("lebenslauf", "cv", "resume", "vita")):
            doc_type = "lebenslauf"
        elif any(k in fl for k in ("zeugnis", "referenz", "certificate")):
            doc_type = "zeugnis"
        elif any(k in fl for k in ("anschreiben", "cover", "motivationsschreiben")):
            doc_type = "anschreiben"
        elif any(k in fl for k in ("zertifikat", "cert", "bescheinigung")):
            doc_type = "zertifikat"

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
    """Get full event timeline for an application."""
    conn = _db.connect()
    events = [dict(r) for r in conn.execute(
        "SELECT * FROM application_events WHERE application_id = ? ORDER BY event_date DESC",
        (app_id,)
    ).fetchall()]
    app_row = conn.execute("SELECT * FROM applications WHERE id = ?", (app_id,)).fetchone()
    if not app_row:
        return JSONResponse({"error": "Bewerbung nicht gefunden"}, status_code=404)
    return {"application": dict(app_row), "events": events}


@app.get("/api/jobs")
async def api_jobs(active: bool = True):
    if active:
        return _db.get_active_jobs()
    return _db.get_dismissed_jobs()


@app.post("/api/jobs/dismiss")
async def api_dismiss_job(request: Request):
    data = await request.json()
    _db.dismiss_job(data["hash"], data.get("reason", ""))
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
    conn = _db.connect()
    row = conn.execute("SELECT * FROM jobs WHERE hash = ?", (job_hash,)).fetchone()
    if not row:
        return JSONResponse({"error": "Stelle nicht gefunden"}, status_code=404)
    job = dict(row)
    criteria = _db.get_search_criteria()
    return fit_analyse(job, criteria)


@app.get("/api/applications")
async def api_applications(status: str = None):
    return _db.get_applications(status)


@app.post("/api/applications")
async def api_add_application(request: Request):
    data = await request.json()
    aid = _db.add_application(data)
    return {"status": "ok", "id": aid}


@app.put("/api/applications/{app_id}/status")
async def api_update_app_status(app_id: str, request: Request):
    data = await request.json()
    _db.update_application_status(app_id, data["status"], data.get("notes", ""))
    return {"status": "ok"}


@app.get("/api/statistics")
async def api_statistics():
    return _db.get_statistics()


@app.get("/api/search-criteria")
async def api_search_criteria():
    return _db.get_search_criteria()


@app.post("/api/search-criteria")
async def api_set_criteria(request: Request):
    data = await request.json()
    for key, value in data.items():
        _db.set_search_criteria(key, value)
    return {"status": "ok"}


@app.get("/api/blacklist")
async def api_blacklist():
    return _db.get_blacklist()


@app.post("/api/blacklist")
async def api_add_blacklist(request: Request):
    data = await request.json()
    _db.add_to_blacklist(data["type"], data["value"], data.get("reason", ""))
    return {"status": "ok"}


MAX_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB

@app.post("/api/documents/upload")
async def api_upload_document(
    file: UploadFile = File(...),
    doc_type: str = Form("sonstiges"),
    position_id: str = Form("")
):
    from .database import get_data_dir

    # Read with size check
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        return JSONResponse(
            {"error": f"Datei zu gross ({len(content) // 1024 // 1024} MB). Maximum: 50 MB."},
            status_code=413
        )

    doc_dir = get_data_dir() / "dokumente"
    filepath = doc_dir / file.filename
    with open(filepath, "wb") as f:
        f.write(content)

    # Try to extract text
    extracted = ""
    fname = file.filename.lower()
    try:
        if fname.endswith(".pdf"):
            from pypdf import PdfReader
            reader = PdfReader(str(filepath))
            extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
        elif fname.endswith(".docx"):
            from docx import Document
            doc = Document(str(filepath))
            extracted = "\n".join(p.text for p in doc.paragraphs)
        elif fname.endswith(".txt"):
            extracted = content.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning("Text extraction failed for %s: %s", file.filename, e)

    did = _db.add_document({
        "filename": file.filename,
        "filepath": str(filepath),
        "doc_type": doc_type,
        "extracted_text": extracted,
        "linked_position_id": position_id or None,
    })
    return {"status": "ok", "id": did, "extracted_length": len(extracted)}


@app.get("/api/sources")
async def api_sources():
    """List all available job sources with active status."""
    from .job_scraper import SOURCE_REGISTRY
    active = _db.get_setting("active_sources", [])
    sources = []
    for key, info in SOURCE_REGISTRY.items():
        sources.append({
            "key": key,
            "name": info["name"],
            "beschreibung": info["beschreibung"],
            "methode": info["methode"],
            "login_erforderlich": info["login_erforderlich"],
            "active": key in active,
        })
    return sources


@app.post("/api/sources")
async def api_set_sources(request: Request):
    """Set active job sources."""
    data = await request.json()
    active = data.get("active_sources", [])
    _db.set_setting("active_sources", active)
    return {"status": "ok", "active_sources": active}


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


DASHBOARD_PORT = int(os.environ.get("BA_DASHBOARD_PORT", "8200"))

def start_dashboard(db_instance, port: int = None):
    """Start the dashboard web server (called from background thread).

    Port priority: port argument > BA_DASHBOARD_PORT env var > 8200
    """
    global _db
    _db = db_instance
    use_port = port or DASHBOARD_PORT
    logger.info("Dashboard startet auf http://localhost:%d", use_port)
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=use_port, log_level="warning")


def _generate_dashboard_html() -> str:
    """Generate a minimal fallback dashboard if template not found."""
    return """<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Bewerbungs-Assistent</title>
<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
       background: #0d1117; color: #c9d1d9; }
.loading { display: flex; align-items: center; justify-content: center;
           height: 100vh; font-size: 1.5rem; }
</style>
</head>
<body>
<div class="loading">Dashboard wird geladen... Bitte Templates installieren.</div>
</body>
</html>"""
