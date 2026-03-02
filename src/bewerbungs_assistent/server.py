"""MCP Server for Bewerbungs-Assistent.

Provides Tools, Resources, and Prompts for Claude Desktop integration.
Also starts a web dashboard on localhost:8200 in a background thread.
"""

import sys
import os
import json
import threading
import logging
from typing import Optional
from datetime import datetime, timezone

from fastmcp import FastMCP

from .database import Database, get_data_dir

# Logging: Datei + stderr (stdout ist fuer MCP-Protokoll reserviert!)
from .logging_config import setup_logging
setup_logging(console=True)
logger = logging.getLogger("bewerbungs_assistent")

# Initialize database
db = Database()
db.initialize()

# Create MCP server
mcp = FastMCP(
    "Bewerbungs-Assistent",
)


# ============================================================
# TOOLS — Actions that Claude can perform
# ============================================================

import functools

# Zentrale Tool-Aufruf-Protokollierung
_original_tool = mcp.tool

def _logged_tool(*args, **kwargs):
    """Wrapper: Loggt jeden Tool-Aufruf und Fehler in die Log-Datei."""
    decorator = _original_tool(*args, **kwargs)
    def wrapper(func):
        @functools.wraps(func)
        def logged_func(*a, **kw):
            logger.info("Tool aufgerufen: %s", func.__name__)
            try:
                result = func(*a, **kw)
                if isinstance(result, dict) and "fehler" in result:
                    logger.warning("Tool %s: %s", func.__name__, result["fehler"])
                return result
            except Exception as e:
                logger.error("Tool %s Fehler: %s", func.__name__, e, exc_info=True)
                raise
        return decorator(logged_func)
    return wrapper

mcp.tool = _logged_tool


# --- Profile ---

@mcp.tool()
def profil_status() -> dict:
    """Prueft ob bereits ein Profil existiert und gibt eine Kurzuebersicht.

    IMMER als erstes aufrufen wenn der User den Assistent startet.
    Entscheidet ob Ersterfassung noetig ist oder ob es direkt losgehen kann.
    """
    profile = db.get_profile()
    if profile is None:
        return {
            "status": "kein_profil",
            "nachricht": "Noch kein Profil vorhanden. Bitte starte die Ersterfassung mit profil_erstellen().",
            "dashboard_url": "http://localhost:8200"
        }
    return {
        "status": "vorhanden",
        "name": profile.get("name"),
        "positionen": len(profile.get("positions", [])),
        "skills": len(profile.get("skills", [])),
        "dokumente": len(profile.get("documents", [])),
        "dashboard_url": "http://localhost:8200"
    }


@mcp.tool()
def profil_zusammenfassung() -> dict:
    """Liest das komplette Profil und gibt eine formatierte Zusammenfassung zurueck.

    Inkl. Vollstaendigkeits-Checkliste. Nutze dieses Tool um dem User
    sein Profil zur Kontrolle zu zeigen (Review-Phase).
    """
    profile = db.get_profile()
    if profile is None:
        return {"status": "kein_profil", "nachricht": "Noch kein Profil vorhanden."}

    positions = profile.get("positions", [])
    education = profile.get("education", [])
    skills = profile.get("skills", [])
    documents = profile.get("documents", [])
    prefs = profile.get("preferences", {})
    if isinstance(prefs, str):
        prefs = json.loads(prefs) if prefs else {}

    # Build formatted summary
    lines = []
    lines.append("=" * 50)
    lines.append(f"PROFIL: {profile.get('name', '(kein Name)')}")
    lines.append("=" * 50)

    # Personal data
    lines.append("\n--- Persoenliche Daten ---")
    for key, label in [
        ("email", "E-Mail"), ("phone", "Telefon"), ("address", "Adresse"),
        ("city", "Stadt"), ("plz", "PLZ"), ("country", "Land"),
        ("birthday", "Geburtstag"), ("nationality", "Nationalitaet"),
    ]:
        val = profile.get(key)
        if val:
            lines.append(f"  {label}: {val}")

    if profile.get("summary"):
        lines.append(f"\n--- Kurzprofil ---\n  {profile['summary']}")

    if profile.get("informal_notes"):
        lines.append(f"\n--- Persoenliche Notizen ---\n  {profile['informal_notes']}")

    # Preferences
    if prefs:
        lines.append("\n--- Job-Praeferenzen ---")
        pref_labels = {
            "stellentyp": "Stellentyp", "arbeitsmodell": "Arbeitsmodell",
            "min_gehalt": "Min. Gehalt (EUR/Jahr)", "ziel_gehalt": "Ziel-Gehalt (EUR/Jahr)",
            "min_tagessatz": "Min. Tagessatz (EUR)", "ziel_tagessatz": "Ziel-Tagessatz (EUR)",
            "reisebereitschaft": "Reisebereitschaft", "umzug_moeglich": "Umzug moeglich",
        }
        for key, label in pref_labels.items():
            val = prefs.get(key)
            if val and val != 0 and val != "":
                if isinstance(val, bool):
                    val = "Ja" if val else "Nein"
                lines.append(f"  {label}: {val}")

    # Positions
    lines.append(f"\n--- Berufserfahrung ({len(positions)} Positionen) ---")
    for pos in positions:
        current = " (aktuell)" if pos.get("is_current") else ""
        end = pos.get("end_date") or "heute"
        emp_type = pos.get("employment_type", "")
        type_badge = f" [{emp_type}]" if emp_type else ""
        lines.append(f"\n  {pos.get('title', '?')} bei {pos.get('company', '?')}{current}{type_badge}")
        lines.append(f"  {pos.get('start_date', '?')} - {end} | {pos.get('location', '')}")
        if pos.get("description"):
            lines.append(f"  Beschreibung: {pos['description'][:200]}")
        if pos.get("tasks"):
            lines.append(f"  Aufgaben: {pos['tasks'][:200]}")
        if pos.get("achievements"):
            lines.append(f"  Erfolge: {pos['achievements'][:200]}")
        if pos.get("technologies"):
            lines.append(f"  Technologien: {pos['technologies']}")
        projects = pos.get("projects", [])
        if projects:
            lines.append(f"  Projekte ({len(projects)}):")
            for proj in projects:
                lines.append(f"    - {proj.get('name', '?')}: {proj.get('description', '')[:100]}")
                if proj.get("result"):
                    lines.append(f"      Ergebnis: {proj['result'][:100]}")

    # Education
    lines.append(f"\n--- Ausbildung ({len(education)} Eintraege) ---")
    for edu in education:
        degree = edu.get("degree", "")
        field = edu.get("field_of_study", "")
        degree_str = f"{degree} in {field}" if degree and field else degree or field or "?"
        lines.append(f"  {degree_str} — {edu.get('institution', '?')}")
        if edu.get("start_date") or edu.get("end_date"):
            lines.append(f"  {edu.get('start_date', '?')} - {edu.get('end_date', '?')}")
        if edu.get("grade"):
            lines.append(f"  Note: {edu['grade']}")

    # Skills
    lines.append(f"\n--- Skills ({len(skills)} Eintraege) ---")
    by_cat = {}
    for s in skills:
        cat = s.get("category", "sonstige")
        by_cat.setdefault(cat, []).append(s)
    cat_labels = {
        "fachlich": "Fachlich", "methodisch": "Methodisch",
        "soft_skill": "Soft Skills", "sprache": "Sprachen",
        "tool": "Tools", "sonstige": "Sonstige",
    }
    for cat, items in by_cat.items():
        label = cat_labels.get(cat, cat)
        skill_strs = [f"{s['name']} (Lv.{s.get('level', '?')})" for s in items]
        lines.append(f"  {label}: {', '.join(skill_strs)}")

    # Documents
    if documents:
        lines.append(f"\n--- Dokumente ({len(documents)}) ---")
        for doc in documents:
            lines.append(f"  [{doc.get('doc_type', '?')}] {doc.get('filename', '?')}")

    # Completeness check
    lines.append("\n" + "=" * 50)
    lines.append("VOLLSTAENDIGKEITS-CHECK")
    lines.append("=" * 50)

    checks = {
        "Name": bool(profile.get("name")),
        "Kontaktdaten (E-Mail/Telefon)": bool(profile.get("email") or profile.get("phone")),
        "Adresse": bool(profile.get("city")),
        "Kurzprofil/Summary": bool(profile.get("summary")),
        "Berufserfahrung": len(positions) > 0,
        "Projekte (STAR)": any(pos.get("projects") for pos in positions),
        "Ausbildung": len(education) > 0,
        "Skills": len(skills) > 0,
        "Job-Praeferenzen": bool(prefs.get("stellentyp")),
    }

    complete = 0
    for label, ok in checks.items():
        icon = "[OK]" if ok else "[FEHLT]"
        lines.append(f"  {icon} {label}")
        if ok:
            complete += 1

    pct = int(complete / len(checks) * 100)
    lines.append(f"\nVollstaendigkeit: {pct}% ({complete}/{len(checks)})")

    return {
        "zusammenfassung": "\n".join(lines),
        "vollstaendigkeit_prozent": pct,
        "fehlende_bereiche": [l for l, ok in checks.items() if not ok],
        "positionen_anzahl": len(positions),
        "projekte_anzahl": sum(len(p.get("projects", [])) for p in positions),
        "skills_anzahl": len(skills),
        "ausbildung_anzahl": len(education),
    }


@mcp.tool()
def profil_bearbeiten(
    bereich: str,
    aktion: str,
    element_id: str = "",
    daten: dict = None
) -> dict:
    """Bearbeitet einen bestimmten Bereich des Profils gezielt.

    Ermoeglicht Korrekturen ohne alles neu eingeben zu muessen.

    Args:
        bereich: persoenlich, praeferenzen, position, projekt, ausbildung, skill
        aktion: aendern, loeschen, hinzufuegen
        element_id: ID des Elements (bei aendern/loeschen)
        daten: Die konkreten Aenderungsdaten (bei aendern/hinzufuegen)
    """
    if daten is None:
        daten = {}

    if bereich == "persoenlich":
        if aktion == "aendern":
            profile = db.get_profile()
            if not profile:
                return {"fehler": "Kein Profil vorhanden"}
            # Merge: keep existing, update provided
            update = {
                "name": daten.get("name", profile.get("name")),
                "email": daten.get("email", profile.get("email")),
                "phone": daten.get("phone", profile.get("phone")),
                "address": daten.get("address", profile.get("address")),
                "city": daten.get("city", profile.get("city")),
                "plz": daten.get("plz", profile.get("plz")),
                "country": daten.get("country", profile.get("country")),
                "birthday": daten.get("birthday", profile.get("birthday")),
                "nationality": daten.get("nationality", profile.get("nationality")),
                "summary": daten.get("summary", profile.get("summary")),
                "informal_notes": daten.get("informal_notes", profile.get("informal_notes")),
                "preferences": profile.get("preferences", {}),
            }
            db.save_profile(update)
            return {"status": "aktualisiert", "bereich": "persoenlich"}

    elif bereich == "praeferenzen":
        if aktion == "aendern":
            profile = db.get_profile()
            if not profile:
                return {"fehler": "Kein Profil vorhanden"}
            prefs = profile.get("preferences", {})
            if isinstance(prefs, str):
                prefs = json.loads(prefs) if prefs else {}
            prefs.update(daten)
            update_data = {
                "name": profile.get("name"), "email": profile.get("email"),
                "phone": profile.get("phone"), "address": profile.get("address"),
                "city": profile.get("city"), "plz": profile.get("plz"),
                "country": profile.get("country"), "birthday": profile.get("birthday"),
                "nationality": profile.get("nationality"),
                "summary": profile.get("summary"),
                "informal_notes": profile.get("informal_notes"),
                "preferences": prefs,
            }
            db.save_profile(update_data)
            return {"status": "aktualisiert", "bereich": "praeferenzen", "neue_werte": prefs}

    elif bereich == "position":
        if aktion == "loeschen" and element_id:
            db.delete_position(element_id)
            return {"status": "geloescht", "bereich": "position", "id": element_id}
        elif aktion == "hinzufuegen":
            pid = db.add_position(daten)
            return {"status": "hinzugefuegt", "bereich": "position", "id": pid}

    elif bereich == "projekt":
        if aktion == "hinzufuegen" and daten.get("position_id"):
            pid = db.add_project(daten["position_id"], daten)
            return {"status": "hinzugefuegt", "bereich": "projekt", "id": pid}

    elif bereich == "ausbildung":
        if aktion == "loeschen" and element_id:
            db.delete_education(element_id)
            return {"status": "geloescht", "bereich": "ausbildung", "id": element_id}
        elif aktion == "hinzufuegen":
            eid = db.add_education(daten)
            return {"status": "hinzugefuegt", "bereich": "ausbildung", "id": eid}

    elif bereich == "skill":
        if aktion == "loeschen" and element_id:
            db.delete_skill(element_id)
            return {"status": "geloescht", "bereich": "skill", "id": element_id}
        elif aktion == "hinzufuegen":
            sid = db.add_skill(daten)
            return {"status": "hinzugefuegt", "bereich": "skill", "id": sid}

    return {"fehler": f"Ungueltige Kombination: bereich={bereich}, aktion={aktion}"}


@mcp.tool()
def profil_erstellen(
    name: str,
    email: str = "",
    phone: str = "",
    address: str = "",
    city: str = "",
    plz: str = "",
    country: str = "Deutschland",
    birthday: str = "",
    nationality: str = "",
    summary: str = "",
    informal_notes: str = "",
    stellentyp: str = "beides",
    arbeitsmodell: str = "hybrid",
    min_gehalt: int = 0,
    ziel_gehalt: int = 0,
    min_tagessatz: int = 0,
    ziel_tagessatz: int = 0,
    reisebereitschaft: str = "mittel",
    umzug_moeglich: bool = False
) -> dict:
    """Erstellt oder aktualisiert das Bewerberprofil.

    Args:
        name: Vollstaendiger Name
        email: E-Mail-Adresse
        phone: Telefonnummer
        address: Strasse und Hausnummer
        city: Stadt/Ort
        plz: Postleitzahl
        country: Land
        birthday: Geburtsdatum (YYYY-MM-DD)
        nationality: Staatsangehoerigkeit
        summary: Kurzprofil / Zusammenfassung
        informal_notes: Zwanglose Informationen (Neigungen, Motivation, Wuensche)
        stellentyp: festanstellung, freelance, oder beides
        arbeitsmodell: remote, hybrid, vor_ort
        min_gehalt: Mindestgehalt Festanstellung (EUR/Jahr)
        ziel_gehalt: Zielgehalt Festanstellung (EUR/Jahr)
        min_tagessatz: Mindest-Tagessatz Freelance (EUR)
        ziel_tagessatz: Ziel-Tagessatz Freelance (EUR)
        reisebereitschaft: keine, gering, mittel, hoch
        umzug_moeglich: Umzugsbereitschaft
    """
    preferences = {
        "stellentyp": stellentyp,
        "arbeitsmodell": arbeitsmodell,
        "min_gehalt": min_gehalt,
        "ziel_gehalt": ziel_gehalt,
        "min_tagessatz": min_tagessatz,
        "ziel_tagessatz": ziel_tagessatz,
        "reisebereitschaft": reisebereitschaft,
        "umzug_moeglich": umzug_moeglich,
    }
    pid = db.save_profile({
        "name": name, "email": email, "phone": phone,
        "address": address, "city": city, "plz": plz,
        "country": country, "birthday": birthday, "nationality": nationality,
        "summary": summary, "informal_notes": informal_notes,
        "preferences": preferences,
    })
    return {
        "status": "gespeichert",
        "profil_id": pid,
        "naechster_schritt": "Fuege jetzt Berufserfahrung hinzu mit position_hinzufuegen(). "
                            "Frage nach: Firma, Position, Zeitraum, Aufgaben, Erfolge, Technologien. "
                            "Nutze die STAR-Methode (Situation, Task, Action, Result) fuer jedes Projekt."
    }


@mcp.tool()
def position_hinzufuegen(
    company: str,
    title: str,
    start_date: str,
    end_date: str = "",
    is_current: bool = False,
    location: str = "",
    employment_type: str = "festanstellung",
    industry: str = "",
    description: str = "",
    tasks: str = "",
    achievements: str = "",
    technologies: str = ""
) -> dict:
    """Fuegt eine Berufsposition zum Profil hinzu.

    Args:
        company: Firmenname
        title: Jobtitel / Position
        start_date: Startdatum (YYYY-MM oder YYYY-MM-DD)
        end_date: Enddatum (leer wenn aktuell)
        is_current: Aktuelle Position?
        location: Arbeitsort
        employment_type: festanstellung, freelance, praktikum, werkstudent
        industry: Branche
        description: Allgemeine Beschreibung der Rolle
        tasks: Hauptaufgaben (kommasepariert oder als Text)
        achievements: Erfolge und Ergebnisse
        technologies: Verwendete Technologien und Tools
    """
    pid = db.add_position({
        "company": company, "title": title, "location": location,
        "start_date": start_date, "end_date": end_date,
        "is_current": is_current, "employment_type": employment_type,
        "industry": industry, "description": description,
        "tasks": tasks, "achievements": achievements, "technologies": technologies,
    })
    return {
        "status": "gespeichert",
        "position_id": pid,
        "naechster_schritt": f"Position '{title}' bei {company} hinzugefuegt. "
                            "Frage jetzt nach Projekten bei dieser Position: "
                            "projekt_hinzufuegen(). Nutze STAR: Situation, Task, Action, Result. "
                            "Frage am Ende: 'Gab es noch ein weiteres Projekt bei dieser Firma?'"
    }


@mcp.tool()
def projekt_hinzufuegen(
    position_id: str,
    name: str,
    description: str = "",
    role: str = "",
    situation: str = "",
    task: str = "",
    action: str = "",
    result: str = "",
    technologies: str = "",
    duration: str = ""
) -> dict:
    """Fuegt ein Projekt zu einer Berufsposition hinzu (STAR-Methode).

    Args:
        position_id: ID der Position (von position_hinzufuegen)
        name: Projektname
        description: Kurzbeschreibung des Projekts
        role: Rolle im Projekt (z.B. Projektleiter, Architekt)
        situation: STAR-S: Ausgangssituation / Kontext
        task: STAR-T: Aufgabe / Herausforderung
        action: STAR-A: Durchgefuehrte Massnahmen
        result: STAR-R: Ergebnis / Erfolg (moeglichst quantifizierbar)
        technologies: Eingesetzte Technologien
        duration: Dauer (z.B. "6 Monate", "2020-2021")
    """
    pid = db.add_project(position_id, {
        "name": name, "description": description, "role": role,
        "situation": situation, "task": task, "action": action,
        "result": result, "technologies": technologies, "duration": duration,
    })
    return {
        "status": "gespeichert",
        "projekt_id": pid,
        "hinweis": "Frage den User: 'Gab es noch ein weiteres Projekt in dieser Position?'"
    }


@mcp.tool()
def ausbildung_hinzufuegen(
    institution: str,
    degree: str = "",
    field_of_study: str = "",
    start_date: str = "",
    end_date: str = "",
    grade: str = "",
    description: str = ""
) -> dict:
    """Fuegt eine Ausbildung, Studium oder Weiterbildung hinzu.

    Args:
        institution: Name der Bildungseinrichtung
        degree: Abschluss (z.B. Diplom, Master, Bachelor, Zertifikat)
        field_of_study: Studiengang / Fachrichtung
        start_date: Startdatum
        end_date: Enddatum
        grade: Note / Bewertung
        description: Zusaetzliche Details
    """
    eid = db.add_education({
        "institution": institution, "degree": degree,
        "field_of_study": field_of_study,
        "start_date": start_date, "end_date": end_date,
        "grade": grade, "description": description,
    })
    return {"status": "gespeichert", "ausbildung_id": eid}


@mcp.tool()
def skill_hinzufuegen(
    name: str,
    category: str = "fachlich",
    level: int = 3,
    years_experience: int = 0
) -> dict:
    """Fuegt eine Kompetenz/Faehigkeit zum Profil hinzu.

    Args:
        name: Name der Kompetenz
        category: fachlich, methodisch, soft_skill, sprache, tool
        level: Kompetenzstufe 1-5 (1=Grundkenntnisse, 5=Experte)
        years_experience: Jahre Erfahrung
    """
    sid = db.add_skill({
        "name": name, "category": category,
        "level": level, "years_experience": years_experience,
    })
    return {"status": "gespeichert", "skill_id": sid}


# --- Job Search ---

@mcp.tool()
def jobsuche_starten(
    keywords: list[str] = None,
    quellen: list[str] = None,
    nur_remote: bool = False,
    max_entfernung_km: int = 0
) -> dict:
    """Startet eine Jobsuche im Hintergrund auf allen konfigurierten Portalen.

    VORAUSSETZUNGEN:
    1. Mindestens eine Quelle muss aktiviert sein (Dashboard → Einstellungen → Job-Quellen)
    2. Suchkriterien sollten gesetzt sein (suchkriterien_setzen)

    Die Suche dauert 5-10 Minuten. Pruefe den Fortschritt mit jobsuche_status().
    Ergebnisse danach mit stellen_anzeigen() ansehen.

    Args:
        keywords: Suchbegriffe (Standard: aus Profil)
        quellen: Welche Portale durchsuchen (Standard: alle aktiven)
        nur_remote: Nur Remote-Stellen
        max_entfernung_km: Maximale Entfernung in km (0 = kein Limit)
    """
    # Default sources from DB settings (all disabled by default)
    if not quellen:
        quellen = db.get_setting("active_sources", [])
        if not quellen:
            return {
                "status": "keine_quellen",
                "nachricht": "Keine Job-Quellen aktiviert. "
                             "Aktiviere Quellen im Dashboard unter Einstellungen → Job-Quellen, "
                             "oder gib sie explizit an: quellen=['stepstone', 'bundesagentur']"
            }

    params = {
        "keywords": keywords,
        "quellen": quellen,
        "nur_remote": nur_remote,
        "max_entfernung_km": max_entfernung_km,
    }
    job_id = db.create_background_job("jobsuche", params)

    # Start background search
    def _run_search():
        try:
            from .job_scraper import run_search
            run_search(db, job_id, params)
        except Exception as e:
            logger.error("Jobsuche fehlgeschlagen: %s", e, exc_info=True)
            db.update_background_job(job_id, "fehler", message=str(e))

    thread = threading.Thread(target=_run_search, daemon=True)
    thread.start()

    return {
        "job_id": job_id,
        "status": "gestartet",
        "nachricht": f"Jobsuche laeuft auf {len(params['quellen'])} Portalen. "
                    f"Pruefe den Fortschritt mit jobsuche_status('{job_id}')."
    }


@mcp.tool()
def jobsuche_status(job_id: str) -> dict:
    """Prueft den Fortschritt einer laufenden Jobsuche.

    Args:
        job_id: Job-ID von jobsuche_starten()
    """
    job = db.get_background_job(job_id)
    if job is None:
        return {"fehler": "Unbekannte Job-ID"}
    return {
        "status": job["status"],
        "fortschritt": f"{job['progress']}%",
        "nachricht": job["message"],
        "ergebnis": job["result"] if job["status"] == "fertig" else None,
    }


@mcp.tool()
def stelle_bewerten(job_hash: str, bewertung: str, grund: str = "") -> dict:
    """Bewertet eine gefundene Stelle.

    Args:
        job_hash: Hash der Stelle
        bewertung: 'passt' oder 'passt_nicht'
        grund: Grund bei passt_nicht (z.B. 'Zu weit entfernt', 'Falsches Fachgebiet')
    """
    if bewertung == "passt_nicht":
        db.dismiss_job(job_hash, grund)
        if grund:
            # Learn from dismissal reasons
            db.add_to_blacklist("dismiss_pattern", grund)
        return {"status": "aussortiert", "grund": grund}
    elif bewertung == "passt":
        db.restore_job(job_hash)
        return {"status": "als_passend_markiert"}
    return {"fehler": "Ungueltige Bewertung. Nutze 'passt' oder 'passt_nicht'."}


# --- Export ---

@mcp.tool()
def lebenslauf_exportieren(
    format: str = "pdf",
    angepasst_fuer: str = ""
) -> dict:
    """Exportiert den Lebenslauf als PDF oder DOCX-Datei.

    Erzeugt ein professionell formatiertes Dokument aus dem gespeicherten Profil.
    Die Datei wird im Bewerbungs-Assistent Datenordner gespeichert.

    Args:
        format: 'pdf' oder 'docx'
        angepasst_fuer: Optional — Firma/Stelle fuer die der CV angepasst wird (fuer Dateinamen)
    """
    profile = db.get_profile()
    if not profile:
        return {"fehler": "Kein Profil vorhanden. Erstelle zuerst ein Profil mit der Ersterfassung."}

    from .export import generate_cv_docx, generate_cv_pdf

    export_dir = get_data_dir() / "export"
    export_dir.mkdir(exist_ok=True)
    name_slug = (profile.get("name") or "lebenslauf").replace(" ", "_").lower()
    suffix = f"_{angepasst_fuer.replace(' ', '_').lower()}" if angepasst_fuer else ""

    if format == "docx":
        path = export_dir / f"lebenslauf_{name_slug}{suffix}.docx"
        generate_cv_docx(profile, path)
    elif format == "pdf":
        path = export_dir / f"lebenslauf_{name_slug}{suffix}.pdf"
        generate_cv_pdf(profile, path)
    else:
        return {"fehler": "Format muss 'pdf' oder 'docx' sein."}

    return {
        "status": "erstellt",
        "datei": str(path),
        "format": format,
        "nachricht": f"Lebenslauf als {format.upper()} exportiert: {path.name}. "
                     "Die Datei liegt im Bewerbungs-Assistent Datenordner. "
                     "Du kannst sie auch im Dashboard unter http://localhost:8200 herunterladen."
    }


@mcp.tool()
def anschreiben_exportieren(
    text: str,
    stelle: str,
    firma: str,
    format: str = "pdf"
) -> dict:
    """Exportiert ein Anschreiben als PDF oder DOCX-Datei.

    Nimmt den fertigen Anschreiben-Text und erzeugt ein formatiertes Dokument
    mit Absender, Datum, Betreffzeile und Text.

    Args:
        text: Der vollstaendige Anschreiben-Text (Absaetze mit Leerzeilen trennen)
        stelle: Stellentitel (z.B. 'PLM Consultant')
        firma: Firmenname (z.B. 'Siemens')
        format: 'pdf' oder 'docx'
    """
    if not text.strip():
        return {"fehler": "Kein Anschreiben-Text angegeben. Nutze den Prompt 'bewerbung_schreiben' um einen Text zu erstellen."}

    profile = db.get_profile() or {}

    from .export import generate_cover_letter_docx, generate_cover_letter_pdf

    export_dir = get_data_dir() / "export"
    export_dir.mkdir(exist_ok=True)
    firma_slug = (firma or "bewerbung").replace(" ", "_").lower()

    if format == "docx":
        path = export_dir / f"anschreiben_{firma_slug}.docx"
        generate_cover_letter_docx(profile, text, stelle, firma, path)
    elif format == "pdf":
        path = export_dir / f"anschreiben_{firma_slug}.pdf"
        generate_cover_letter_pdf(profile, text, stelle, firma, path)
    else:
        return {"fehler": "Format muss 'pdf' oder 'docx' sein."}

    return {
        "status": "erstellt",
        "datei": str(path),
        "format": format,
        "nachricht": f"Anschreiben fuer {stelle} bei {firma} als {format.upper()} exportiert: {path.name}."
    }


# --- Stellen & Bewerbungen lesen ---

@mcp.tool()
def stellen_anzeigen(
    filter: str = "aktiv",
    min_score: int = 0,
    quelle: str = ""
) -> dict:
    """Zeigt gefundene Stellenangebote an.

    Gibt die Liste der Stellen zurueck, sortiert nach Score.
    Nutze stelle_bewerten() um einzelne Stellen zu bewerten.

    Args:
        filter: 'aktiv' (Standard), 'aussortiert', oder 'alle'
        min_score: Nur Stellen mit mindestens diesem Score anzeigen
        quelle: Optional: Nur Stellen von dieser Quelle (z.B. 'stepstone', 'indeed')
    """
    if filter == "aussortiert":
        jobs = db.get_dismissed_jobs()
    else:
        filters = {}
        if min_score > 0:
            filters["min_score"] = min_score
        if quelle:
            filters["source"] = quelle
        jobs = db.get_active_jobs(filters if filters else None)

    if not jobs:
        return {
            "anzahl": 0,
            "nachricht": "Keine Stellen gefunden. "
                         "Starte eine Jobsuche mit jobsuche_starten() oder "
                         "aktiviere Quellen im Dashboard unter Einstellungen."
        }

    # Format for Claude readability
    formatted = []
    for j in jobs[:20]:  # Max 20 to avoid token overflow
        entry = {
            "hash": j["hash"],
            "titel": j.get("title", ""),
            "firma": j.get("company", ""),
            "ort": j.get("location", ""),
            "score": j.get("score", 0),
            "quelle": j.get("source", ""),
            "remote": j.get("remote_level", "unbekannt"),
            "url": j.get("url", ""),
        }
        if j.get("distance_km"):
            entry["entfernung_km"] = j["distance_km"]
        if j.get("dismiss_reason"):
            entry["aussortiert_grund"] = j["dismiss_reason"]
        formatted.append(entry)

    return {
        "anzahl": len(jobs),
        "angezeigt": len(formatted),
        "stellen": formatted,
        "hinweis": "Nutze stelle_bewerten(hash, 'passt') oder stelle_bewerten(hash, 'passt_nicht', 'Grund') "
                   "um Stellen zu bewerten. Fuer Details zu einer Stelle nutze fit_analyse(hash)."
                   if filter == "aktiv" else ""
    }


@mcp.tool()
def fit_analyse(job_hash: str) -> dict:
    """Detaillierte Passungsanalyse fuer eine bestimmte Stelle.

    Zeigt welche Keywords matchen, was fehlt, und gibt eine Risikobewertung.

    Args:
        job_hash: Hash der Stelle (von stellen_anzeigen)
    """
    from .job_scraper import fit_analyse as _fit_analyse
    conn = db.connect()
    row = conn.execute("SELECT * FROM jobs WHERE hash = ?", (job_hash,)).fetchone()
    if not row:
        return {"fehler": "Stelle nicht gefunden. Pruefe den Hash mit stellen_anzeigen()."}
    criteria = db.get_search_criteria()
    return _fit_analyse(dict(row), criteria)


@mcp.tool()
def bewerbungen_anzeigen(status_filter: str = "") -> dict:
    """Zeigt alle erfassten Bewerbungen mit Status und Timeline.

    Args:
        status_filter: Optional: Nur Bewerbungen mit diesem Status
            (offen, beworben, eingangsbestaetigung, interview, zweitgespraech,
             angebot, abgelehnt, zurueckgezogen)
    """
    apps = db.get_applications(status_filter if status_filter else None)

    if not apps:
        return {
            "anzahl": 0,
            "nachricht": "Noch keine Bewerbungen erfasst. "
                         "Erstelle eine neue Bewerbung mit bewerbung_erstellen() oder "
                         "nutze den Prompt 'bewerbung_schreiben' fuer eine gefuehrte Bewerbung."
        }

    formatted = []
    for a in apps:
        entry = {
            "id": a["id"],
            "titel": a.get("title", ""),
            "firma": a.get("company", ""),
            "status": a.get("status", ""),
            "bewerbungsart": a.get("bewerbungsart", ""),
            "datum": a.get("applied_at", ""),
            "events": len(a.get("events", [])),
        }
        if a.get("ansprechpartner"):
            entry["ansprechpartner"] = a["ansprechpartner"]
        if a.get("kontakt_email"):
            entry["kontakt_email"] = a["kontakt_email"]
        if a.get("notes"):
            entry["notizen"] = a["notes"][:200]
        formatted.append(entry)

    stats = db.get_statistics()
    return {
        "anzahl": len(apps),
        "bewerbungen": formatted,
        "statistik": {
            "gesamt": stats.get("total_applications", 0),
            "nach_status": stats.get("applications_by_status", {}),
            "interview_rate": stats.get("interview_rate", 0),
        },
        "hinweis": "Nutze bewerbung_status_aendern(id, status, notizen) um den Status zu aktualisieren."
    }


# --- Applications ---

@mcp.tool()
def bewerbung_erstellen(
    title: str,
    company: str,
    url: str = "",
    job_hash: str = "",
    status: str = "beworben",
    applied_at: str = "",
    notes: str = "",
    bewerbungsart: str = "mit_dokumenten",
    lebenslauf_variante: str = "standard",
    ansprechpartner: str = "",
    kontakt_email: str = "",
    portal_name: str = ""
) -> dict:
    """Erstellt eine neue Bewerbung (manuell oder aus einer gefundenen Stelle).

    Args:
        title: Stellentitel
        company: Firmenname
        url: Link zur Stellenanzeige
        job_hash: Optional: Hash einer gefundenen Stelle
        status: offen, beworben, eingangsbestaetigung, interview, zweitgespraech, angebot, abgelehnt, zurueckgezogen
        applied_at: Bewerbungsdatum (YYYY-MM-DD, Standard: heute)
        notes: Notizen
        bewerbungsart: mit_dokumenten, elektronisch, ueber_portal
        lebenslauf_variante: standard, angepasst, keiner
        ansprechpartner: Name des Ansprechpartners
        kontakt_email: E-Mail des Ansprechpartners
        portal_name: Name des Portals (bei bewerbungsart=ueber_portal)
    """
    aid = db.add_application({
        "title": title, "company": company, "url": url,
        "job_hash": job_hash, "status": status,
        "applied_at": applied_at, "notes": notes,
        "bewerbungsart": bewerbungsart,
        "lebenslauf_variante": lebenslauf_variante,
        "ansprechpartner": ansprechpartner,
        "kontakt_email": kontakt_email,
        "portal_name": portal_name,
    })
    return {
        "status": "erstellt",
        "bewerbung_id": aid,
        "nachricht": f"Bewerbung bei {company} fuer '{title}' erfasst ({bewerbungsart})."
    }


@mcp.tool()
def bewerbung_status_aendern(
    bewerbung_id: str,
    neuer_status: str,
    notizen: str = ""
) -> dict:
    """Aendert den Status einer Bewerbung.

    Args:
        bewerbung_id: ID der Bewerbung
        neuer_status: offen, beworben, eingangsbestaetigung, interview, zweitgespraech, angebot, abgelehnt, zurueckgezogen
        notizen: Optionale Notizen zum Statuswechsel
    """
    db.update_application_status(bewerbung_id, neuer_status, notizen)
    return {"status": "aktualisiert", "neuer_status": neuer_status}


@mcp.tool()
def statistiken_abrufen() -> dict:
    """Ruft Bewerbungsstatistiken ab: Conversion-Rate, Antwortzeiten, Status-Verteilung.

    Gibt einen Ueberblick ueber:
    - Gesamtzahl Bewerbungen und aktive Stellen
    - Bewerbungen nach Status (beworben, interview, angebot, etc.)
    - Interview-Rate (% der Bewerbungen die zum Interview fuehren)
    """
    return db.get_statistics()


@mcp.tool()
def suchkriterien_setzen(
    keywords_muss: list[str] = None,
    keywords_plus: list[str] = None,
    keywords_ausschluss: list[str] = None,
    regionen: list[str] = None,
    custom_kriterien: dict = None
) -> dict:
    """Setzt die Suchkriterien fuer die Jobsuche.

    MUSS-Keywords: Stelle wird nur beruecksichtigt wenn mindestens eins vorkommt.
    PLUS-Keywords: Erhoehen den Score (= bessere Sortierung).
    AUSSCHLUSS-Keywords: Stelle wird komplett ignoriert wenn eins vorkommt.

    Tipp: Leite die Keywords aus dem Profil ab! Was kann der User,
    was sucht er? Nutze profil_zusammenfassung() als Basis.

    Args:
        keywords_muss: Pflicht-Keywords (muessen vorkommen)
        keywords_plus: Bonus-Keywords (erhoehen Score)
        keywords_ausschluss: Ausschluss-Keywords (z.B. Junior, Praktikum)
        regionen: Bevorzugte Regionen
        custom_kriterien: Eigene Kriterien mit Gewichtung, z.B. {"homeoffice": 8, "gehalt": 7}
    """
    if keywords_muss:
        db.set_search_criteria("keywords_muss", keywords_muss)
    if keywords_plus:
        db.set_search_criteria("keywords_plus", keywords_plus)
    if keywords_ausschluss:
        db.set_search_criteria("keywords_ausschluss", keywords_ausschluss)
    if regionen:
        db.set_search_criteria("regionen", regionen)
    if custom_kriterien:
        db.set_search_criteria("custom_kriterien", custom_kriterien)
    return {"status": "gespeichert", "kriterien": db.get_search_criteria()}


@mcp.tool()
def blacklist_verwalten(
    aktion: str,
    typ: str = "firma",
    wert: str = "",
    grund: str = ""
) -> dict:
    """Verwaltet die Blacklist (Firmen, Keywords die automatisch aussortiert werden).

    Args:
        aktion: 'hinzufuegen', 'anzeigen'
        typ: 'firma', 'keyword', 'dismiss_pattern'
        wert: Der Blacklist-Eintrag
        grund: Grund fuer den Eintrag
    """
    if aktion == "hinzufuegen":
        db.add_to_blacklist(typ, wert, grund)
        return {"status": "hinzugefuegt", "typ": typ, "wert": wert}
    elif aktion == "anzeigen":
        return {"blacklist": db.get_blacklist()}
    return {"fehler": "Unbekannte Aktion. Nutze 'hinzufuegen' oder 'anzeigen'."}


# --- Profil-Management (Multi-Profil) ---

@mcp.tool()
def profile_auflisten() -> dict:
    """Listet alle vorhandenen Profile auf. Zeigt welches aktiv ist.

    Nutze dieses Tool wenn mehrere Personen den gleichen PC nutzen
    oder wenn der User zwischen Profilen wechseln moechte.
    """
    profiles = db.get_profiles()
    if not profiles:
        return {"status": "keine_profile", "nachricht": "Keine Profile vorhanden. Starte die Ersterfassung."}
    return {
        "status": "ok",
        "anzahl": len(profiles),
        "profile": [
            {
                "id": p["id"],
                "name": p["name"] or "(Ohne Name)",
                "email": p.get("email", ""),
                "aktiv": bool(p.get("is_active")),
                "erstellt": p.get("created_at", ""),
                "aktualisiert": p.get("updated_at", ""),
            }
            for p in profiles
        ],
    }


@mcp.tool()
def profil_wechseln(profil_id: str) -> dict:
    """Wechselt zum angegebenen Profil. Alle anderen Profile werden deaktiviert.

    Args:
        profil_id: Die ID des Profils zu dem gewechselt werden soll.
    """
    success = db.switch_profile(profil_id)
    if success:
        profile = db.get_profile()
        return {
            "status": "gewechselt",
            "aktives_profil": profile.get("name") if profile else "?",
            "nachricht": f"Profil gewechselt zu: {profile.get('name') if profile else profil_id}"
        }
    return {"fehler": f"Profil mit ID '{profil_id}' nicht gefunden."}


@mcp.tool()
def neues_profil_erstellen(name: str, email: str = "") -> dict:
    """Erstellt ein komplett neues, leeres Profil und aktiviert es.

    Das vorherige Profil bleibt gespeichert und kann spaeter wieder aktiviert werden.

    Args:
        name: Name der Person fuer das neue Profil
        email: Optional: E-Mail-Adresse
    """
    pid = db.save_profile({"name": name, "email": email})
    return {
        "status": "erstellt",
        "profil_id": pid,
        "name": name,
        "nachricht": f"Neues Profil '{name}' erstellt und aktiviert. Das vorherige Profil wurde gespeichert."
    }


@mcp.tool()
def profil_loeschen(profil_id: str) -> dict:
    """Loescht ein Profil und alle zugehoerigen Daten (Positionen, Skills, Dokumente).

    ACHTUNG: Diese Aktion kann nicht rueckgaengig gemacht werden!
    Das aktive Profil kann nicht geloescht werden — wechsle zuerst zu einem anderen.

    Args:
        profil_id: Die ID des zu loeschenden Profils
    """
    active_id = db.get_active_profile_id()
    if profil_id == active_id:
        return {"fehler": "Das aktive Profil kann nicht geloescht werden. Wechsle zuerst zu einem anderen Profil."}
    db.delete_profile(profil_id)
    return {"status": "geloescht", "nachricht": f"Profil {profil_id} und alle zugehoerigen Daten wurden geloescht."}


# --- Erfassungsfortschritt (PBP-026) ---

@mcp.tool()
def erfassung_fortschritt_lesen() -> dict:
    """Liest den Fortschritt der Profil-Ersterfassung.

    Gibt zurueck welche Bereiche bereits ausgefuellt sind und welche noch fehlen.
    Nutze dies zu Beginn einer Ersterfassung um zu pruefen ob es eine
    angefangene Erfassung gibt die fortgesetzt werden soll.
    """
    profile = db.get_profile()
    if profile is None:
        return {"status": "kein_profil", "fortschritt": {}}

    # Automatisch berechnen was schon da ist
    fortschritt = profile.get("erfassung_fortschritt", {})
    auto_check = {
        "persoenliche_daten": bool(profile.get("name") and profile.get("email")),
        "berufserfahrung": len(profile.get("positions", [])) > 0,
        "ausbildung": len(profile.get("education", [])) > 0,
        "kompetenzen": len(profile.get("skills", [])) > 0,
        "praeferenzen": bool(profile.get("preferences", {}).get("stellentyp")),
        "review_abgeschlossen": fortschritt.get("review_abgeschlossen", False),
    }
    return {
        "status": "ok",
        "profil_name": profile.get("name"),
        "bereiche": auto_check,
        "alle_komplett": all(auto_check.values()),
        "fehlende_bereiche": [k for k, v in auto_check.items() if not v],
        "letzte_notizen": fortschritt.get("notizen", ""),
    }


@mcp.tool()
def erfassung_fortschritt_speichern(
    bereich: str,
    abgeschlossen: bool = True,
    notizen: str = ""
) -> dict:
    """Speichert den Fortschritt eines Erfassungsbereichs.

    Wird automatisch waehrend der Ersterfassung aufgerufen um den Stand zu merken.
    So kann die Ersterfassung jederzeit unterbrochen und spaeter fortgesetzt werden.

    Args:
        bereich: Name des Bereichs (persoenliche_daten, berufserfahrung, ausbildung, kompetenzen, praeferenzen, review_abgeschlossen)
        abgeschlossen: Ob der Bereich fertig ist
        notizen: Optionale Notizen zum Fortschritt
    """
    fortschritt = db.get_erfassung_fortschritt()
    fortschritt[bereich] = abgeschlossen
    if notizen:
        fortschritt["notizen"] = notizen
    db.set_erfassung_fortschritt(fortschritt)
    return {"status": "gespeichert", "bereich": bereich, "abgeschlossen": abgeschlossen}


# --- Dokument-Analyse (PBP-028) ---

@mcp.tool()
def dokument_profil_extrahieren(document_id: str) -> dict:
    """Liest den extrahierten Text eines hochgeladenen Dokuments und gibt ihn
    zur Analyse zurueck. Claude soll daraus Profildaten ableiten.

    WORKFLOW:
    1. Rufe dieses Tool mit der document_id auf
    2. Analysiere den Text und identifiziere Profildaten (Name, Skills, Positionen etc.)
    3. Vergleiche mit dem bestehenden Profil (profil_zusammenfassung)
    4. Bei neuen Daten: Frage den User ob diese uebernommen werden sollen
    5. Bei Konflikten: Zeige beide Versionen und lasse den User entscheiden
    6. Speichere mit den jeweiligen Tools (profil_bearbeiten, position_hinzufuegen etc.)

    Args:
        document_id: ID des Dokuments aus dem Profildaten extrahiert werden sollen
    """
    conn = db.connect()
    cur = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,))
    row = cur.fetchone()
    if row is None:
        return {"fehler": f"Dokument mit ID '{document_id}' nicht gefunden."}

    doc = dict(row)
    if not doc.get("extracted_text"):
        return {
            "fehler": "Kein extrahierter Text vorhanden. Dokument wurde noch nicht verarbeitet.",
            "dokument": doc.get("filename"),
        }

    return {
        "status": "ok",
        "dokument": {
            "id": doc["id"],
            "filename": doc["filename"],
            "doc_type": doc.get("doc_type", "sonstiges"),
        },
        "extrahierter_text": doc["extracted_text"],
        "anleitung": (
            "Analysiere den Text und extrahiere Profildaten. "
            "Vergleiche mit dem bestehenden Profil und frage bei Konflikten oder "
            "neuen Informationen den User ob diese uebernommen werden sollen. "
            "Nutze die entsprechenden Tools (profil_bearbeiten, position_hinzufuegen, "
            "skill_hinzufuegen etc.) um die Daten zu speichern."
        ),
    }


@mcp.tool()
def dokumente_zur_analyse() -> dict:
    """Listet alle Dokumente mit extrahiertem Text auf, die noch nicht
    fuer die Profil-Extraktion analysiert wurden.

    Nutze dies nach einem Dokument-Upload um dem User anzubieten,
    automatisch Profildaten aus den Dokumenten zu extrahieren.
    """
    profile = db.get_profile()
    if profile is None:
        return {"status": "kein_profil"}

    docs = profile.get("documents", [])
    analysierbare = [
        {
            "id": d["id"],
            "filename": d["filename"],
            "doc_type": d.get("doc_type", "sonstiges"),
            "hat_text": bool(d.get("extracted_text")),
            "text_laenge": len(d.get("extracted_text", "")),
        }
        for d in docs
        if d.get("extracted_text")
    ]
    return {
        "status": "ok",
        "dokumente_gesamt": len(docs),
        "analysierbare": len(analysierbare),
        "dokumente": analysierbare,
    }


# ============================================================
# ERWEITERTE KI-FEATURES (PBP-014)
# ============================================================

@mcp.tool()
def gehalt_extrahieren(job_hash: str) -> dict:
    """Extrahiert Gehaltsinformationen aus einer Stellenbeschreibung.

    Durchsucht den Text nach Gehaltsangaben (Jahresgehalt, Tagessatz,
    Stundenlohn) und speichert die strukturierten Daten.

    Args:
        job_hash: Hash der Stelle aus stellen_anzeigen()
    """
    import re
    conn = db.connect()
    row = conn.execute("SELECT * FROM jobs WHERE hash=?", (job_hash,)).fetchone()
    if not row:
        return {"fehler": "Stelle nicht gefunden. Pruefe den Hash mit stellen_anzeigen()."}

    text = (row["description"] or "") + " " + (row["salary_info"] or "") + " " + (row["title"] or "")

    # Regex patterns for salary extraction
    patterns = [
        # EUR ranges: 60.000-80.000, 60000-80000, 60k-80k
        (r'(\d{2,3}[\.,]?\d{3})\s*[-–bis]+\s*(\d{2,3}[\.,]?\d{3})\s*(?:EUR|€|Euro)', 'jaehrlich'),
        (r'€\s*(\d{2,3}[\.,]?\d{3})\s*[-–bis]+\s*(\d{2,3}[\.,]?\d{3})', 'jaehrlich'),
        (r'(\d{2,3})\s*k\s*[-–bis]+\s*(\d{2,3})\s*k', 'jaehrlich'),
        # Single annual amounts
        (r'(?:Gehalt|Jahresgehalt|Brutto)[:\s]*(?:ab|bis|ca\.?)?\s*(\d{2,3}[\.,]?\d{3})\s*(?:EUR|€|Euro)?', 'jaehrlich'),
        # Daily rates: 800-1200€/Tag
        (r'(\d{3,4})\s*[-–bis]+\s*(\d{3,4})\s*(?:EUR|€)?\s*/?\s*(?:Tag|day|d)', 'taeglich'),
        (r'(?:Tagessatz|Tagesrate|daily rate)[:\s]*(\d{3,4})\s*(?:[-–bis]+\s*(\d{3,4}))?\s*(?:EUR|€)?', 'taeglich'),
        # Hourly rates
        (r'(\d{2,3})\s*[-–bis]+\s*(\d{2,3})\s*(?:EUR|€)?\s*/?\s*(?:Stunde|hour|h)', 'stuendlich'),
    ]

    salary_min = None
    salary_max = None
    salary_type = None

    for pattern, stype in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            groups = [g for g in match.groups() if g]
            nums = []
            for g in groups:
                g_clean = g.replace(".", "").replace(",", "")
                try:
                    n = float(g_clean)
                    # k-notation
                    if n < 300 and stype == 'jaehrlich':
                        n *= 1000
                    nums.append(n)
                except ValueError:
                    continue
            if nums:
                salary_min = min(nums)
                salary_max = max(nums) if len(nums) > 1 else salary_min
                salary_type = stype
                break

    if salary_min is None:
        return {
            "status": "nicht_gefunden",
            "stelle": row["title"],
            "firma": row["company"],
            "hinweis": "Keine Gehaltsangabe in der Stellenbeschreibung erkannt. "
                       "Du kannst Claude bitten, den Text manuell zu analysieren.",
            "salary_info_text": row.get("salary_info", ""),
        }

    # Save to database
    db.save_salary_data(job_hash, salary_min, salary_max, salary_type)

    # Compare with profile preferences
    profile = db.get_profile()
    vergleich = {}
    if profile and profile.get("preferences"):
        prefs = profile["preferences"]
        if salary_type == "jaehrlich" and prefs.get("min_gehalt"):
            min_g = float(prefs["min_gehalt"])
            vergleich["dein_minimum"] = min_g
            vergleich["passt"] = salary_max >= min_g
            if prefs.get("ziel_gehalt"):
                vergleich["dein_ziel"] = float(prefs["ziel_gehalt"])
        elif salary_type == "taeglich" and prefs.get("min_tagessatz"):
            min_t = float(prefs["min_tagessatz"])
            vergleich["dein_minimum"] = min_t
            vergleich["passt"] = salary_max >= min_t

    return {
        "status": "extrahiert",
        "stelle": row["title"],
        "firma": row["company"],
        "gehalt_min": salary_min,
        "gehalt_max": salary_max,
        "gehalt_typ": salary_type,
        "vergleich_mit_profil": vergleich,
    }


@mcp.tool()
def gehalt_marktanalyse() -> dict:
    """Analysiert Gehaltsdaten aller gesammelten Stellenangebote.

    Zeigt Durchschnitt, Median, Spanne — getrennt nach Festanstellung
    und Freelance. Vergleicht mit deinen Gehaltsvorstellungen.
    """
    stats = db.get_salary_statistics()
    profile = db.get_profile()
    if profile and profile.get("preferences"):
        prefs = profile["preferences"]
        stats["deine_vorstellungen"] = {
            "min_gehalt": prefs.get("min_gehalt"),
            "ziel_gehalt": prefs.get("ziel_gehalt"),
            "min_tagessatz": prefs.get("min_tagessatz"),
            "ziel_tagessatz": prefs.get("ziel_tagessatz"),
        }
    stats["tipp"] = (
        "Nutze gehalt_extrahieren(job_hash) um Gehaltsdaten aus einzelnen "
        "Stellen zu extrahieren und die Datenbasis zu vergroessern."
    )
    return stats


@mcp.tool()
def firmen_recherche(firma: str) -> dict:
    """Recherchiert Informationen ueber eine Firma anhand der gesammelten Stellendaten.

    Aggregiert alle bekannten Jobs, Standorte, Gehaelter und Remote-Level
    fuer die angegebene Firma.

    Args:
        firma: Name der Firma (oder Teil davon)
    """
    jobs = db.get_company_jobs(firma)
    if not jobs:
        return {
            "status": "keine_daten",
            "firma": firma,
            "hinweis": "Keine Stellen von dieser Firma in der Datenbank. "
                       "Starte eine Jobsuche oder pruefe den Firmennamen.",
        }

    standorte = list(set(j.get("location", "unbekannt") for j in jobs if j.get("location")))
    quellen = list(set(j.get("source", "unbekannt") for j in jobs))
    remote_levels = [j.get("remote_level", "unbekannt") for j in jobs]
    scores = [j.get("score", 0) for j in jobs]
    gehalt_jobs = [j for j in jobs if j.get("salary_min")]

    result = {
        "status": "ok",
        "firma": firma,
        "stellen_gesamt": len(jobs),
        "stellen_aktiv": sum(1 for j in jobs if j.get("is_active")),
        "standorte": standorte,
        "quellen": quellen,
        "remote_level": {r: remote_levels.count(r) for r in set(remote_levels)},
        "score_durchschnitt": round(sum(scores) / len(scores)) if scores else 0,
        "score_best": max(scores) if scores else 0,
        "stellen": [
            {"titel": j["title"], "standort": j.get("location"), "score": j.get("score", 0),
             "remote": j.get("remote_level"), "hash": j["hash"]}
            for j in sorted(jobs, key=lambda x: x.get("score", 0), reverse=True)[:10]
        ],
    }
    if gehalt_jobs:
        result["gehaltsspanne"] = {
            "min": min(j["salary_min"] for j in gehalt_jobs),
            "max": max(j["salary_max"] for j in gehalt_jobs),
        }
    return result


@mcp.tool()
def branchen_trends() -> dict:
    """Analysiert gefragte Skills und Technologien in den gesammelten Stellenangeboten.

    Zaehlt Skill-Keywords in allen aktiven Job-Beschreibungen und vergleicht
    mit deinem Profil (Match/Gap-Analyse).
    """
    import re
    from collections import Counter

    descriptions = db.get_skill_frequency()
    if not descriptions:
        return {
            "status": "keine_daten",
            "hinweis": "Noch keine Stellenangebote vorhanden. Starte zuerst eine Jobsuche.",
        }

    # Common tech/skill keywords to look for
    skill_keywords = [
        "Python", "Java", "JavaScript", "TypeScript", "C#", "C\\+\\+", "SQL", "NoSQL",
        "React", "Angular", "Vue", "Node\\.js", "Docker", "Kubernetes", "AWS", "Azure",
        "SAP", "ERP", "CRM", "PLM", "PDM", "CAD", "CAM", "MES", "PPS",
        "Agile", "Scrum", "Kanban", "ITIL", "DevOps", "CI/CD",
        "REST", "API", "Microservices", "Cloud", "Linux", "Windows Server",
        "Machine Learning", "KI", "AI", "Data Science", "Big Data",
        "Projektmanagement", "Teamleitung", "Fuehrung", "Consulting",
        "PRO\\.FILE", "Teamcenter", "Windchill", "ENOVIA", "3DExperience",
        "SolidWorks", "AutoCAD", "CATIA", "NX", "Inventor",
        "Freelance", "Remote", "Hybrid", "Home.?Office",
        "Englisch", "Deutsch",
    ]

    full_text = " ".join(descriptions)
    total_jobs = len(descriptions)
    trend_counts = Counter()

    for keyword in skill_keywords:
        count = len(re.findall(keyword, full_text, re.IGNORECASE))
        if count > 0:
            clean_key = keyword.replace("\\", "").replace(".?", "-")
            trend_counts[clean_key] = count

    # Compare with user skills
    profile = db.get_profile()
    user_skills = []
    skill_gap = []
    if profile:
        user_skills = [s["name"].lower() for s in profile.get("skills", [])]
        for skill, count in trend_counts.most_common(30):
            if skill.lower() not in user_skills and count >= 2:
                skill_gap.append({"skill": skill, "nachfrage": count})

    top_20 = [
        {"skill": skill, "nennungen": count, "prozent_jobs": round(count / total_jobs * 100, 1)}
        for skill, count in trend_counts.most_common(20)
    ]

    return {
        "status": "ok",
        "analysierte_stellen": total_jobs,
        "top_skills": top_20,
        "skill_gap": skill_gap[:10] if skill_gap else [],
        "tipp": "Skills die im Markt gefragt sind aber in deinem Profil fehlen, "
                "sind unter 'skill_gap' aufgelistet.",
    }


@mcp.tool()
def nachfass_planen(bewerbung_id: str, tage: int = 7, typ: str = "nachfass") -> dict:
    """Plant eine Nachfass-Erinnerung fuer eine Bewerbung.

    Erstellt einen Follow-up Eintrag mit Datum und Template-Vorschlag.

    Args:
        bewerbung_id: ID der Bewerbung
        tage: Tage ab heute bis zum Follow-up (Standard: 7)
        typ: Art des Follow-ups: nachfass, danke, info
    """
    from datetime import timedelta
    apps = db.get_applications()
    app = next((a for a in apps if a["id"] == bewerbung_id), None)
    if not app:
        return {"fehler": "Bewerbung nicht gefunden. Pruefe die ID mit bewerbungen_anzeigen()."}

    scheduled = (datetime.now(timezone.utc) + timedelta(days=tage)).strftime("%Y-%m-%d")

    templates = {
        "nachfass": (
            f"Betreff: Nachfrage zu meiner Bewerbung — {app['title']}\n\n"
            f"Sehr geehrte Damen und Herren,\n\n"
            f"ich habe mich am {{applied_at}} auf die Position \"{app['title']}\" beworben "
            f"und moechte hoeflich nachfragen, ob Sie bereits eine Entscheidung getroffen haben.\n\n"
            f"Ich bin weiterhin sehr an der Position interessiert und stehe gerne "
            f"fuer ein Gespraech zur Verfuegung.\n\n"
            f"Mit freundlichen Gruessen"
        ),
        "danke": (
            f"Betreff: Vielen Dank fuer das Gespraech — {app['title']}\n\n"
            f"Sehr geehrte/r {{ansprechpartner}},\n\n"
            f"vielen Dank fuer das angenehme Gespraech. Ich bin nach unserem Austausch "
            f"noch ueberzeugter, dass die Position \"{app['title']}\" hervorragend "
            f"zu meinen Erfahrungen passt.\n\n"
            f"Mit freundlichen Gruessen"
        ),
        "info": (
            f"Betreff: Zusaetzliche Informationen — {app['title']}\n\n"
            f"Sehr geehrte Damen und Herren,\n\n"
            f"ergaenzend zu meiner Bewerbung moechte ich Ihnen noch folgende "
            f"Informationen zukommen lassen: [HIER ERGAENZEN]\n\n"
            f"Mit freundlichen Gruessen"
        ),
    }

    template = templates.get(typ, templates["nachfass"])
    fid = db.add_follow_up(bewerbung_id, scheduled, typ, template)

    return {
        "status": "geplant",
        "follow_up_id": fid,
        "bewerbung": app["title"],
        "firma": app["company"],
        "geplant_fuer": scheduled,
        "typ": typ,
        "template": template,
        "hinweis": "Das Template ist ein Vorschlag — passe es gerne an bevor du es versendest.",
    }


@mcp.tool()
def nachfass_anzeigen() -> dict:
    """Zeigt alle geplanten und faelligen Nachfass-Erinnerungen.

    Gruppiert nach: ueberfaellig, heute, diese Woche, spaeter.
    """
    follow_ups = db.get_pending_follow_ups()
    if not follow_ups:
        return {
            "status": "keine_followups",
            "nachricht": "Keine Nachfass-Erinnerungen geplant. "
                         "Nutze nachfass_planen() um einen Follow-up zu erstellen.",
        }

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    from datetime import timedelta
    week_end = (datetime.now(timezone.utc) + timedelta(days=7)).strftime("%Y-%m-%d")

    grouped = {"ueberfaellig": [], "heute": [], "diese_woche": [], "spaeter": []}
    for f in follow_ups:
        entry = {
            "id": f["id"],
            "bewerbung": f.get("title", "?"),
            "firma": f.get("company", "?"),
            "app_status": f.get("app_status", "?"),
            "typ": f["follow_up_type"],
            "geplant_fuer": f["scheduled_date"],
            "template": f.get("template", ""),
        }
        if f["scheduled_date"] < today:
            grouped["ueberfaellig"].append(entry)
        elif f["scheduled_date"] == today:
            grouped["heute"].append(entry)
        elif f["scheduled_date"] <= week_end:
            grouped["diese_woche"].append(entry)
        else:
            grouped["spaeter"].append(entry)

    return {
        "status": "ok",
        "gesamt": len(follow_ups),
        "ueberfaellig": len(grouped["ueberfaellig"]),
        "follow_ups": grouped,
    }


@mcp.tool()
def bewerbung_stil_tracken(bewerbung_id: str, stil: str, notizen: str = "") -> dict:
    """Speichert den Anschreiben-Stil einer Bewerbung fuer A/B-Tracking.

    Damit kannst du spaeter analysieren, welcher Stil bessere
    Ruecklaufquoten hat.

    Args:
        bewerbung_id: ID der Bewerbung
        stil: Stil des Anschreibens: formell, kreativ, direkt, storytelling
        notizen: Optionale Notizen zum Stil
    """
    conn = db.connect()
    row = conn.execute("SELECT * FROM applications WHERE id=?", (bewerbung_id,)).fetchone()
    if not row:
        return {"fehler": "Bewerbung nicht gefunden."}

    event_notes = f"Anschreiben-Stil: {stil}"
    if notizen:
        event_notes += f" | {notizen}"

    conn.execute("""
        INSERT INTO application_events (application_id, status, event_date, notes)
        VALUES (?, ?, ?, ?)
    """, (bewerbung_id, "stil_tracking", datetime.now(timezone.utc).isoformat(), event_notes))
    conn.commit()

    return {
        "status": "gespeichert",
        "bewerbung_id": bewerbung_id,
        "titel": row["title"],
        "firma": row["company"],
        "stil": stil,
        "hinweis": "Stil wurde als Event gespeichert. Nutze statistiken_abrufen() "
                   "um spaeter Ruecklaufquoten pro Stil zu analysieren.",
    }


# ============================================================
# RESOURCES — Data that Claude can read
# ============================================================

@mcp.resource("profil://aktuell")
def resource_profil() -> str:
    """Vollstaendiges Nutzerprofil mit allen Positionen, Skills und Dokumenten."""
    profile = db.get_profile()
    if profile is None:
        return json.dumps({"status": "kein_profil"}, ensure_ascii=False)
    return json.dumps(profile, ensure_ascii=False, indent=2, default=str)


@mcp.resource("jobs://aktiv")
def resource_active_jobs() -> str:
    """Alle aktiven Stellenangebote, sortiert nach Score."""
    jobs = db.get_active_jobs()
    return json.dumps(jobs, ensure_ascii=False, indent=2, default=str)


@mcp.resource("jobs://aussortiert")
def resource_dismissed_jobs() -> str:
    """Aussortierte Stellen mit Gruenden."""
    jobs = db.get_dismissed_jobs()
    return json.dumps(jobs, ensure_ascii=False, indent=2, default=str)


@mcp.resource("bewerbungen://alle")
def resource_applications() -> str:
    """Alle Bewerbungen mit Status und Timeline."""
    apps = db.get_applications()
    return json.dumps(apps, ensure_ascii=False, indent=2, default=str)


@mcp.resource("bewerbungen://statistik")
def resource_statistics() -> str:
    """Bewerbungsstatistiken: Conversion-Rate, Antwortzeiten."""
    stats = db.get_statistics()
    return json.dumps(stats, ensure_ascii=False, indent=2)


@mcp.resource("config://suchkriterien")
def resource_search_criteria() -> str:
    """Aktuelle Sucheinstellungen und Kriterien."""
    criteria = db.get_search_criteria()
    return json.dumps(criteria, ensure_ascii=False, indent=2)


# ============================================================
# PROMPTS — Structured interaction templates
# ============================================================

@mcp.prompt()
def ersterfassung() -> str:
    """Zwangloses Interview zur Profilerfassung — wie ein Kaffeegespraech.
    Kann jederzeit unterbrochen und spaeter fortgesetzt werden."""
    return """Du bist ein freundlicher, erfahrener Karriereberater. Dies ist KEIN steifes Formular —
es ist ein zwangloses Gespraech, wie bei einem Kaffee unter Freunden. Du bist per Du.

═══════════════════════════════════════════════════
SCHRITT 0: FORTSCHRITT PRUEFEN
═══════════════════════════════════════════════════

BEVOR du anfaengst, rufe IMMER zuerst diese Tools auf:
1. erfassung_fortschritt_lesen() — Prueft ob eine angefangene Erfassung existiert
2. profile_auflisten() — Prueft ob mehrere Profile vorhanden sind

WENN ein angefangenes Profil existiert:
→ Zeige dem User was schon erfasst ist und frage:
  "Hey! Ich sehe, wir haben schon angefangen. [Name], du hast bereits
   [X Positionen, Y Skills, ...] erfasst. Sollen wir da weitermachen
   wo wir aufgehoert haben? Es fehlen noch: [fehlende Bereiche]"
→ Springe direkt zum ersten fehlenden Bereich

WENN mehrere Profile vorhanden:
→ "Ich sehe, es gibt bereits [N] Profile: [Liste]. Moechtest du
   eines davon bearbeiten oder ein ganz neues erstellen?"

WENN noch kein Profil existiert:
→ Starte normal mit Phase 1

NACH JEDER PHASE: Speichere den Fortschritt mit erfassung_fortschritt_speichern()!

WICHTIG: Dieses Tool ist fuer ALLE Lebenssituationen gedacht:
- Studenten und Berufseinsteiger (wenig Erfahrung ist voellig ok!)
- Langjaehrige Mitarbeiter (20 Jahre in einer Firma = wertvolle Tiefe!)
- Haeufige Wechsler (Vielfalt = breite Kompetenz!)
- Freelancer und Selbstaendige (Projektvielfalt = Flexibilitaet!)
- Wiedereinsteigerinnen nach Familienpause (Lebenserfahrung zaehlt!)
- Menschen mit ungewoehnlichen Karrierewegen (jeder Weg ist einzigartig!)
- Alle, die kein Geld fuer teures Karriere-Coaching haben

WERTE diese Informationen NIEMALS. Jede berufliche Station und jede Lebensphase ist wertvoll.
Hilf dabei, das Beste aus jedem Werdegang herauszuholen — ermutigend und wertschaetzend.

═══════════════════════════════════════════════════
PHASE 1: LOCKERER EINSTIEG
═══════════════════════════════════════════════════

Beginne so (oder aehnlich natuerlich):

"Hey, schoen dass du hier bist! Ich bin dein persoenlicher Bewerbungs-Assistent.
Keine Sorge — das hier ist kein steifes Formular. Wir unterhalten uns einfach
ganz locker und ich helfe dir, dein Profil zusammenzustellen.

Am Ende zeige ich dir alles nochmal und du kannst in Ruhe korrigieren.

Also, erzaehl mal: Wie heisst du und was machst du so beruflich?
Oder falls du gerade auf der Suche bist — was hast du zuletzt gemacht?"

→ Nur 1-2 offene Fragen, NICHT nach E-Mail/Telefon/PLZ im ersten Schritt!
→ Lass den User erzaehlen, unterbrich nicht mit Formularfragen.
→ Reagiere auf das, was der User erzaehlt — stelle Anschlussfragen.

═══════════════════════════════════════════════════
PHASE 2: STRUKTURIERTE ERFASSUNG (aus dem Gespraech heraus)
═══════════════════════════════════════════════════

Sobald du genug weisst, fange an die Daten mit den Tools zu speichern.
Arbeite dich organisch durch diese Bereiche:

2a) PERSOENLICHE DATEN
    → Irgendwann beilaeuig: "Fuer den Lebenslauf brauch ich noch ein paar Basics —
       E-Mail, Telefon, wo wohnst du ungefaehr?"
    → Speichere mit profil_erstellen()

2b) BERUFSERFAHRUNG — Fuer JEDE Station:
    → Firma, Position, ungefaehrer Zeitraum
    → "Was hast du da so gemacht? Was war deine Rolle?"
    → "Gab es ein Projekt oder eine Aufgabe wo du richtig stolz drauf bist?"
      (STAR: Situation, Aufgabe, was hast du gemacht, was kam dabei raus)
    → "Hast du dabei bestimmte Tools oder Technologien benutzt?"
    → Am Ende: "Gab es noch was bei [Firma]? Oder vorher eine andere Station?"
    → Speichere mit position_hinzufuegen() und projekt_hinzufuegen()

    SPEZIELLE SITUATIONEN — erkenne und reagiere angemessen:
    • Student/Berufseinsteiger:
      "Praktika, Werkstudentenjobs, Uni-Projekte — das zaehlt alles!
       Auch ehrenamtliche Arbeit oder Vereinstaetigkeit."
    • Familienphase/Elternzeit:
      "Das ist voellig normal und wird von guten Arbeitgebern respektiert.
       Hast du in der Zeit vielleicht ehrenamtlich was gemacht oder dich weitergebildet?"
    • Freelancer/Selbstaendige:
      "Lass uns deine wichtigsten Projekte durchgehen. Bei Freelancern zaehlen
       Projekte mehr als Positionen — und du hast sicher eine spannende Vielfalt."
    • Lange bei einer Firma:
      "20 Jahre zeigen echte Loyalitaet und Tiefe! Lass uns die verschiedenen
       Rollen und Verantwortungen aufschlüsseln — da steckt bestimmt viel Entwicklung drin."
    • Haeufige Wechsel:
      "Vielfaeltige Erfahrung ist super — du kennst verschiedene Unternehmenskulturen
       und Branchen. Lass uns das als Staerke positionieren."

2c) AUSBILDUNG
    → "Wo hast du gelernt/studiert? Gibt es Weiterbildungen oder Zertifikate?"
    → Speichere mit ausbildung_hinzufuegen()

2d) SKILLS & KOMPETENZEN
    → Leite aus dem Gespraech ab! "Aus dem was du erzaehlt hast, notiere ich mal:
       [X, Y, Z] — faellt dir noch was ein?"
    → Kategorien: fachlich, tool, methodisch, sprache, soft_skill
    → Speichere mit skill_hinzufuegen()

2e) ZWANGLOSE NOTIZEN
    → "Was motiviert dich? Was ist dir wichtig bei der Arbeit?"
    → "Gibt es was, das du auf keinen Fall willst?"
    → Speichere als informal_notes in profil_erstellen()

═══════════════════════════════════════════════════
PHASE 3: PRAEFERENZ-FRAGEN (basierend auf dem CV)
═══════════════════════════════════════════════════

Stelle gezielte Fragen basierend auf dem, was du erfasst hast:

→ "Du warst [X Jahre] bei [Firma] — moechtest du in der Branche bleiben
   oder was Neues ausprobieren?"
→ "Du hast sowohl Festanstellung als auch Freelance-Erfahrung —
   was liegt dir mehr? Oder beides?"
→ "Deine Jobs waren hauptsaechlich in [Region] — bist du offen fuer andere Orte?"
→ "Remote, vor Ort oder Mix — was waere ideal fuer dich?"
→ "Hast du eine Vorstellung was Gehalt/Tagessatz angeht?
   Kein Stress wenn nicht — wir koennen das spaeter noch anpassen."
→ "Wie sieht's mit Reisebereitschaft aus?"

→ Aktualisiere profil_erstellen() mit den Praeferenzen.

═══════════════════════════════════════════════════
PHASE 4: REVIEW & KORREKTUR
═══════════════════════════════════════════════════

→ Rufe profil_zusammenfassung() auf
→ Zeige dem User die komplette Zusammenfassung
→ "So, das ist alles was ich aufgeschrieben habe. Stimmt das so?
   Moechtest du irgendwas aendern, ergaenzen oder loeschen?"
→ Bei Korrekturen: Nutze profil_bearbeiten() fuer gezielte Aenderungen
→ Iteriere bis der User zufrieden ist
→ Erst dann: "Super, dein Profil ist fertig! Du kannst es jederzeit
   spaeter noch anpassen. Im Dashboard (http://localhost:8200) siehst du
   alles auf einen Blick."

═══════════════════════════════════════════════════
REGELN
═══════════════════════════════════════════════════

1. MAXIMAL 2-3 Fragen pro Nachricht — kein Fragenkatalog!
2. Reagiere auf das Erzaehlte, stelle Anschlussfragen
3. Hilf bei der Formulierung: "Kann man das irgendwie beziffern?
   Z.B. Teamgroesse, Budget, Zeitersparnis?"
4. Sprich IMMER Deutsch und per Du
5. Sei ermutigend — besonders bei Luecken oder ungewoehnlichen Wegen
6. Wenn jemand unsicher ist: "Kein Problem, wir passen das spaeter an"
7. Speichere SOFORT mit den Tools — nicht erst am Ende sammeln
8. Keine Bewertung von Karriereentscheidungen — nur konstruktive Hilfe
9. FORTSCHRITT SPEICHERN: Nach jedem abgeschlossenen Bereich
   erfassung_fortschritt_speichern() aufrufen!
10. UNTERBRECHUNG: Wenn der User abbricht, sage:
    "Kein Problem! Ich habe deinen Fortschritt gespeichert.
     Starte einfach spaeter /ersterfassung erneut und wir machen
     genau da weiter, wo wir aufgehoert haben."
11. DOKUMENT-HINWEIS: Wenn der User Dokumente hochgeladen hat, biete an:
    "Ich sehe du hast [N] Dokumente hochgeladen. Soll ich daraus automatisch
     Profildaten extrahieren? Das geht schneller als alles von Hand einzugeben."
    → Nutze dokument_profil_extrahieren() dafuer"""


@mcp.prompt()
def bewerbung_schreiben(stelle: str = "", firma: str = "") -> str:
    """Erstellt ein stellenspezifisches Anschreiben mit Export-Option."""
    return f"""Erstelle ein professionelles Anschreiben fuer folgende Stelle:
Stelle: {stelle}
Firma: {firma}

SCHRITTE:
1. Rufe profil_zusammenfassung() auf — lerne den Bewerber kennen
2. Analysiere die Stellenanforderungen (wenn URL vorhanden, darauf eingehen)
3. Waehle die relevantesten Erfahrungen und Projekte aus dem Profil
4. Erstelle ein Anschreiben das:
   - Sofort einen Bezug zur Stelle herstellt
   - 2-3 konkrete Erfolge/Projekte aus dem Profil einbindet
   - Die Motivation fuer genau diese Stelle deutlich macht
   - Professionell aber persoenlich klingt
   - Max. 1 Seite lang ist
5. Zeige den Text dem User — "Passt das so? Soll ich etwas aendern?"
6. Nach Freigabe: Biete Export an!
   → "Soll ich das als PDF oder Word-Dokument exportieren?"
   → anschreiben_exportieren(text, '{stelle}', '{firma}', format)
7. Biete auch den Lebenslauf-Export an:
   → "Moechtest du deinen Lebenslauf auch als PDF/DOCX fuer diese Bewerbung exportieren?"
   → lebenslauf_exportieren(format, angepasst_fuer='{firma}')
8. Frage ob die Bewerbung erfasst werden soll:
   → "Soll ich die Bewerbung in dein Tracking aufnehmen?"
   → bewerbung_erstellen(title='{stelle}', company='{firma}')

REGELN:
- Sprich Deutsch
- Zeige erst den Text, dann biete Export an
- Daten werden gespeichert — der User kann alles im Dashboard wiederfinden"""


@mcp.prompt()
def interview_vorbereitung(stelle: str = "", firma: str = "") -> str:
    """Umfassende Vorbereitung auf ein Bewerbungsgespraech — personalisiert aus dem Profil."""
    return f"""Bereite den Nutzer auf ein Bewerbungsgespraech vor:
Stelle: {stelle}
Firma: {firma}

ZUERST:
→ Rufe profil_zusammenfassung() auf — du brauchst das Profil fuer personalisierte Antworten!

DANN LIEFERE:

1. **Erwartbare Fragen** — Die 10 wahrscheinlichsten Fragen fuer diese Position
   Unterteilt in: Fachlich, Persoenlich, Situativ, Motivation

2. **STAR-Antworten** — Fuer jede Frage eine vorbereitete Antwort
   mit konkretem Beispiel aus dem Profil des Users!
   Format: Situation → Aufgabe → Aktion → Ergebnis

3. **Schwaechen-Strategie** — Authentisch, nicht ausweichend
   Basierend auf dem Profil: was FEHLT ggf., und wie kann man es positiv frammen?

4. **Gehaltsverhandlung** — Basierend auf Erfahrung, Region, Branche
   Nutze die Praeferenzen aus dem Profil (min_gehalt, ziel_gehalt)

5. **Eigene Fragen** — 5 kluge Fragen die Kompetenz zeigen

6. **Argumentationsleitfaden** — "Warum bin ICH der ideale Kandidat?"
   3-4 Kernargumente, jedes mit einem konkreten Beweis aus dem Profil

7. **Quick-Reference-Karte** — Am Ende eine kompakte Zusammenfassung
   die man sich vor dem Gespraech nochmal durchlesen kann

REGELN:
- Sprich Deutsch und per Du
- Alles MUSS personalisiert sein — nutze konkrete Projekte, Erfolge, Zahlen aus dem Profil
- Sei ermutigend: "Du hast X Jahre Erfahrung in Y — das ist eine echte Staerke!"
- Biete an: "Soll ich mit dir ein Probe-Interview ueben?"
- Am Ende: "Soll ich den Status deiner Bewerbung bei {firma} auf 'interview' setzen?"
  → bewerbung_status_aendern(id, 'interview', notizen)"""


@mcp.prompt()
def profil_ueberpruefen() -> str:
    """Profil nochmal anschauen und korrigieren — fuer spaetere Aenderungen."""
    return """Der User moechte sein Profil ueberpruefen und ggf. korrigieren.

ABLAUF:
1. Rufe profil_zusammenfassung() auf und zeige dem User die Uebersicht
2. Frage: "Stimmt alles so? Was moechtest du aendern?"
3. Bei Korrekturen:
   - Nutze profil_bearbeiten() fuer gezielte Aenderungen
   - Oder die spezifischen Tools (position_hinzufuegen, skill_hinzufuegen etc.)
   - Zeige nach jeder Aenderung nochmal die betroffene Stelle
4. Wenn fehlende Bereiche angezeigt werden:
   "Ich sehe dass [X] noch fehlt. Moechtest du das jetzt ergaenzen?"
5. Iteriere bis der User zufrieden ist

REGELN:
- Sprich Deutsch und per Du
- Sei nicht aufdringlich mit fehlenden Daten — biete an, draenge nicht
- Bei Korrekturen: Frage genau nach was sich aendern soll
- Zeige am Ende nochmal die aktualisierte Zusammenfassung"""


@mcp.prompt()
def profil_analyse() -> str:
    """Detaillierte Analyse und Bewertung des Bewerberprofils."""
    return """Analysiere das Bewerberprofil (Resource: profil://aktuell) und liefere:

1. **Staerken** — Was macht dieses Profil besonders attraktiv?
2. **Verbesserungspotenzial** — Was koennte ergaenzt oder besser formuliert werden?
3. **Luecken** — Gibt es erkennbare Luecken im Lebenslauf?
   Bei Luecken: NICHT werten! Stattdessen konstruktiv helfen:
   - Familienphase → "Moechtest du angeben, dass du in der Zeit X gemacht hast?"
   - Arbeitslosigkeit → "Gab es Weiterbildungen oder Projekte in der Zeit?"
   - Haeufige Wechsel → als Vielfalt und Anpassungsfaehigkeit positionieren
4. **Marktposition** — Wie steht das Profil im aktuellen Arbeitsmarkt?
5. **Empfehlungen** — Konkrete Vorschlaege fuer Optimierungen
6. **Passende Berufsbezeichnungen** — Liste von Stellentiteln die zum Profil passen
   (User kann diese Liste bearbeiten, loeschen oder ergaenzen)

Sei ehrlich aber konstruktiv und ermutigend. Gib konkrete, umsetzbare Tipps.
Denke daran: Dieses Tool ist auch fuer Menschen die sich kein Coaching leisten koennen.
Jeder Karriereweg ist einzigartig und hat seinen Wert."""


@mcp.prompt()
def willkommen() -> str:
    """Willkommensbildschirm — erklaert was PBP kann und wie man startet."""
    profile = db.get_profile()
    has_profile = profile is not None
    active_jobs = len(db.get_active_jobs()) if has_profile else 0
    apps = len(db.get_applications()) if has_profile else 0
    criteria = db.get_search_criteria() if has_profile else {}

    if has_profile:
        name = profile.get("name", "")
        return f"""Willkommen zurueck, {name}!

Dein Bewerbungs-Assistent ist bereit. Hier ein Ueberblick:

📊 DEIN STATUS
  Profil: ✓ angelegt
  Aktive Stellen: {active_jobs}
  Bewerbungen: {apps}
  Suchkriterien: {'✓ gesetzt' if criteria.get('keywords_muss') else '✗ noch nicht gesetzt'}
  Dashboard: http://localhost:8200

🎯 WAS KANN ICH FUER DICH TUN?
  • "Zeig mir meine Stellen" → stellen_anzeigen()
  • "Zeig mir meine Bewerbungen" → bewerbungen_anzeigen()
  • "Starte eine Jobsuche" → jobsuche_starten()
  • "Schreib mir ein Anschreiben fuer [Stelle] bei [Firma]" → Prompt: bewerbung_schreiben
  • "Bereite mich auf ein Interview vor" → Prompt: interview_vorbereitung
  • "Exportiere meinen Lebenslauf als PDF" → lebenslauf_exportieren()
  • "Wie sieht mein Profil aus?" → profil_zusammenfassung()
  • "Ich moechte mein Profil aendern" → Prompt: profil_ueberpruefen
  • "Analysiere mein Profil" → Prompt: profil_analyse

Frag einfach in deinen eigenen Worten — ich verstehe schon was du meinst!"""

    return """Willkommen beim Bewerbungs-Assistent! 👋

Ich bin dein persoenlicher Karriere-Helfer. Ich helfe dir dabei:

📋 PROFIL ERSTELLEN
  Wir fuehren ein lockeres Gespraech und ich erfasse dein komplettes Profil —
  Berufserfahrung, Skills, Ausbildung. Kein steifes Formular, mehr wie ein Kaffeegespraech.

🔍 JOBS FINDEN
  Ich durchsuche bis zu 8 Jobportale gleichzeitig und bewerte die Ergebnisse
  automatisch nach deinen Kriterien.

✉️ BEWERBUNGEN SCHREIBEN
  Ich schreibe stellenspezifische Anschreiben, basierend auf deinem Profil
  und den Anforderungen der Stelle. Export als PDF oder DOCX.

📄 LEBENSLAUF EXPORTIEREN
  Professionell formatierter CV als PDF oder Word-Dokument.

🎤 INTERVIEW-VORBEREITUNG
  STAR-Antworten, erwartbare Fragen, Gehaltsverhandlung — alles personalisiert.

📊 BEWERBUNGS-TRACKING
  Dashboard auf http://localhost:8200 mit Uebersicht aller Bewerbungen,
  Status-Tracking und Statistiken.

═══════════════════════════════════════════════════
LOS GEHT'S — Starte die Ersterfassung mit dem Prompt 'ersterfassung'.
Sag einfach: "Lass uns mein Profil erstellen!"
═══════════════════════════════════════════════════

Du brauchst kein Computerwissen. Ich fuehre dich durch alles Schritt fuer Schritt."""


@mcp.prompt()
def jobsuche_workflow() -> str:
    """Gefuehrter Workflow: Von Suchkriterien bis zur Bewerbung."""
    criteria = db.get_search_criteria()
    active_sources = db.get_setting("active_sources", [])
    active_jobs = len(db.get_active_jobs())

    return f"""Starte den gefuehrten Jobsuche-Workflow.

DU FUEHRST DEN USER SCHRITT FUER SCHRITT DURCH DIESEN PROZESS:

═══════════════════════════════════════════════════
SCHRITT 1: SUCHKRITERIEN PRUEFEN
═══════════════════════════════════════════════════
Aktueller Stand: {json.dumps(criteria, ensure_ascii=False, indent=2) if criteria else 'Noch keine Kriterien gesetzt!'}

Falls keine/wenige Kriterien gesetzt:
→ Frage den User:
  "Welche Begriffe MUESSEN in einer Stelle vorkommen? (z.B. PLM, SAP, Projektmanagement)"
  "Welche Begriffe waeren ein Bonus? (z.B. Remote, Python, Agile)"
  "Gibt es Begriffe die du NICHT willst? (z.B. Junior, Praktikum, Zeitarbeit)"
→ Speichere mit suchkriterien_setzen()

═══════════════════════════════════════════════════
SCHRITT 2: QUELLEN AKTIVIEREN
═══════════════════════════════════════════════════
Aktive Quellen: {active_sources if active_sources else 'KEINE! (Quellen muessen erst aktiviert werden)'}

Falls keine Quellen aktiv:
→ Erklaere: "Du musst mindestens eine Jobquelle aktivieren. Das geht am einfachsten
   im Dashboard (http://localhost:8200) unter Einstellungen → Job-Quellen.
   Oder sag mir welche du nutzen moechtest:
   - StepStone (keine Anmeldung noetig)
   - Indeed (keine Anmeldung noetig)
   - Monster (keine Anmeldung noetig)
   - Bundesagentur fuer Arbeit (keine Anmeldung noetig)
   - Hays (keine Anmeldung noetig)
   - Freelancermap (keine Anmeldung noetig)
   - LinkedIn (Anmeldung erforderlich)
   - XING (Anmeldung erforderlich)"

═══════════════════════════════════════════════════
SCHRITT 3: SUCHE STARTEN
═══════════════════════════════════════════════════
{f'Es gibt bereits {active_jobs} aktive Stellen.' if active_jobs > 0 else 'Noch keine Stellen gefunden.'}

→ Starte die Suche mit jobsuche_starten()
→ Die Suche dauert ca. 5-10 Minuten
→ Informiere den User ueber den Fortschritt mit jobsuche_status()

═══════════════════════════════════════════════════
SCHRITT 4: ERGEBNISSE SICHTEN
═══════════════════════════════════════════════════
→ Zeige die Ergebnisse mit stellen_anzeigen()
→ Gehe die Top-Stellen durch: "Schau dir die besten Treffer an:"
→ Fuer interessante Stellen: fit_analyse(hash) fuer Details
→ Bewerte gemeinsam: stelle_bewerten(hash, 'passt') oder stelle_bewerten(hash, 'passt_nicht', grund)

═══════════════════════════════════════════════════
SCHRITT 5: BEWERBUNG VORBEREITEN
═══════════════════════════════════════════════════
Fuer passende Stellen:
→ "Soll ich ein Anschreiben fuer [Stelle] bei [Firma] schreiben?"
→ Nutze den Prompt 'bewerbung_schreiben' fuer das Anschreiben
→ Exportiere als PDF/DOCX mit anschreiben_exportieren()
→ Exportiere den Lebenslauf mit lebenslauf_exportieren()
→ Erfasse die Bewerbung mit bewerbung_erstellen()

REGELN:
- Erklaere jeden Schritt verstaendlich
- Ueberspringe Schritte die bereits erledigt sind
- Biete Hilfe bei jedem Schritt an
- Sprich Deutsch und per Du"""


@mcp.prompt()
def bewerbungs_uebersicht() -> str:
    """Komplette Uebersicht: Profil, Stellen, Bewerbungen, naechste Schritte."""
    return """Erstelle eine umfassende Uebersicht fuer den User.

ABLAUF:
1. Rufe profil_zusammenfassung() auf — zeige den Vollstaendigkeits-Check
2. Rufe stellen_anzeigen() auf — zeige die Top-Stellen
3. Rufe bewerbungen_anzeigen() auf — zeige den Bewerbungsstatus
4. Rufe statistiken_abrufen() auf — zeige Conversion-Rate etc.

DANN:
→ Fasse die Situation zusammen:
  "Du hast X Bewerbungen laufen, davon Y im Interview-Status."
  "Es gibt Z neue Stellen die gut zu dir passen."
→ Schlage naechste Schritte vor:
  - Falls Profil unvollstaendig: "Dein Profil ist zu X% vollstaendig. Soll ich helfen?"
  - Falls es gute Stellen gibt: "Die Stelle [X] bei [Y] hat Score [Z] — soll ich ein Anschreiben schreiben?"
  - Falls Bewerbungen offen: "Bei [Firma] hast du seit [X Tagen] nichts gehoert. Soll ich nachfassen helfen?"
  - Falls keine Stellen: "Lass uns eine Jobsuche starten!"

Sprich Deutsch und per Du. Sei proaktiv mit Vorschlaegen."""


# ============================================================
# ERWEITERTE KI-PROMPTS (PBP-014)
# ============================================================

@mcp.prompt()
def interview_simulation(stelle: str = "", firma: str = "") -> str:
    """Simuliertes Bewerbungsgespraech — Claude spielt den Interviewer."""
    return f"""Du bist jetzt der Interviewer fuer folgende Position:
Stelle: {stelle}
Firma: {firma}

VORBEREITUNG (still, nicht anzeigen):
1. Rufe profil_zusammenfassung() auf — lerne den Bewerber kennen
2. Falls eine Stelle angegeben: Rufe fit_analyse() oder stellen_anzeigen() auf
3. Rufe firmen_recherche('{firma}') auf falls Firmendaten vorhanden

ABLAUF DES INTERVIEWS:
Fuehre ein realistisches Bewerbungsgespraech in 3 Phasen:

PHASE 1 — KENNENLERNEN (2-3 Fragen):
- "Erzaehlen Sie mir etwas ueber sich und Ihren beruflichen Werdegang."
- "Was hat Sie an dieser Position besonders angesprochen?"
- Reagiere auf die Antworten wie ein echter Interviewer

PHASE 2 — FACHFRAGEN (3-4 Fragen):
- Stelle Fragen passend zur Position und den erforderlichen Skills
- "Wie wuerden Sie [konkretes Szenario] loesen?"
- "Welche Erfahrung haben Sie mit [Technologie/Methode]?"

PHASE 3 — SITUATIVE FRAGEN / STAR (2-3 Fragen):
- "Erzaehlen Sie von einer Situation, in der..."
- Pruefe ob die Antworten dem STAR-Format folgen
- Falls nicht: Hilf mit Nachfragen (Situation? Aufgabe? Aktion? Ergebnis?)

WICHTIGE REGELN:
- Stelle immer NUR EINE Frage auf einmal
- Warte auf die Antwort bevor du die naechste Frage stellst
- Reagiere natuerlich auf die Antworten (Nachfragen, Bestaetigung)
- Am Ende: Gib konstruktives Feedback zu JEDER Antwort
- Bewerte: Struktur, Konkretheit, STAR-Format, Ueberzeugungskraft
- Schlage Verbesserungen vor fuer schwache Antworten
- Sprich formal (Sie) als Interviewer, aber sei wohlwollend

ABSCHLUSS:
→ Gib eine Gesamtbewertung (1-10)
→ Liste die 3 staerksten und 3 verbesserungswuerdigsten Punkte
→ Biete an: "Soll ich den Bewerbungsstatus auf 'interview' setzen?"
→ bewerbung_status_aendern(id, 'interview')"""


@mcp.prompt()
def gehaltsverhandlung(stelle: str = "", firma: str = "") -> str:
    """Gehaltsverhandlung vorbereiten — Strategie, Argumente und Taktik."""
    return f"""Bereite eine Gehaltsverhandlung vor fuer:
Stelle: {stelle}
Firma: {firma}

DATENSAMMLUNG (zuerst ausfuehren):
1. Rufe profil_zusammenfassung() auf — zeige Erfahrung und Gehaltsvorstellungen
2. Rufe gehalt_marktanalyse() auf — zeige Marktdaten
3. Falls Firma angegeben: Rufe firmen_recherche('{firma}') auf
4. Falls Stelle angegeben: Rufe gehalt_extrahieren() fuer die Stelle auf

ANALYSE & STRATEGIE:
Erstelle eine vollstaendige Verhandlungsvorbereitung:

1. MARKTANALYSE
   - Was zahlt der Markt fuer diese Position/Region/Erfahrung?
   - Wie steht das Angebot im Vergleich?
   - Freelance vs. Festanstellung Unterschied

2. DEIN WERT
   - Welche einzigartigen Kompetenzen bringst du mit?
   - Welche Erfolge/Projekte sind besonders verhandlungsrelevant?
   - Wie viele Jahre relevante Erfahrung?

3. VERHANDLUNGSSTRATEGIE
   - Ankerpunkt: Nenne zuerst eine Zahl (leicht ueber Ziel)
   - Minimum: Unter diesem Wert nicht akzeptieren
   - Ziel: Realistische Erwartung
   - Stretch: Beste erreichbare Zahl
   - Timing: Wann das Gehaltsthema ansprechen

4. ARGUMENTATION (5 Saetze)
   - Formuliere 5 konkrete Saetze fuer die Verhandlung
   - Verknuepfe jeden mit einem Erfolg/Projekt aus dem Profil
   - Beispiel: "In meinem letzten Projekt habe ich [Ergebnis] erzielt,
     was zeigt dass ich [Wert] bringe."

5. TAKTIKEN
   - "Gesamtpaket" denken: Gehalt + Benefits + Urlaub + Remote + Weiterbildung
   - Nie sofort zusagen — "Ich moechte darueber nachdenken"
   - Gegenangebot vorbereiten
   - Schriftlich festhalten

6. FALLSTRICKE
   - Was tun wenn das Angebot zu niedrig ist?
   - Was tun wenn "das Budget ist fix" kommt?
   - Wie auf "Was verdienen Sie aktuell?" reagieren?

Sprich Deutsch, per Du, und sei direkt mit konkreten Zahlen."""


@mcp.prompt()
def netzwerk_strategie(firma: str = "") -> str:
    """Networking-Strategie fuer eine Zielfirma — Kontakte und Ansprache."""
    return f"""Entwickle eine Networking-Strategie fuer die Firma: {firma}

DATENSAMMLUNG (zuerst ausfuehren):
1. Rufe profil_zusammenfassung() auf — zeige Erfahrung und Kontakte
2. Falls Firmendaten vorhanden: Rufe firmen_recherche('{firma}') auf
3. Rufe bewerbungen_anzeigen() auf — pruefe ob du dort schon beworben bist

STRATEGIE ENTWICKELN:

1. FIRMEN-ANALYSE
   - Was macht die Firma? (aus Stellenanzeigen ablesen)
   - Welche Abteilungen/Bereiche sind relevant?
   - Welche Technologien/Methoden nutzen sie?

2. KONTAKTSUCHE (Anleitung fuer LinkedIn)
   - Suche auf LinkedIn nach: "{firma}" + deine Branche
   - Interessante Positionen: HR, Teamleiter, Fachkollegen
   - Ehemalige Kollegen die dort arbeiten koennten
   - Alumni von deiner Ausbildung/Uni

3. ANSCHREIBEN-TEMPLATES

   a) Erstkontakt (LinkedIn Connection Request):
   "Hallo [Name], ich bin [Dein Name] und arbeite seit [X Jahren] im Bereich
   [Fachgebiet]. Ich interessiere mich fuer [Firma] und wuerde mich gerne
   austauschen. Beste Gruesse"

   b) Informationsgespraech anfragen:
   "Hallo [Name], vielen Dank fuer die Vernetzung! Ich schaue mich gerade
   nach neuen Herausforderungen im Bereich [Fachgebiet] um und finde
   [Firma] sehr spannend. Haetten Sie Zeit fuer ein kurzes
   Informationsgespraech (15-20 Minuten)? Ich wuerde gerne mehr ueber
   die Arbeit bei [Firma] erfahren."

   c) Nach Informationsgespraech:
   "Vielen Dank fuer Ihre Zeit! Das Gespraech hat mich noch mehr
   ueberzeugt, dass [Firma] zu mir passt. Sie hatten erwaehnt, dass
   [Detail]. Gibt es eine offene Position fuer die ich mich bewerben koennte?"

4. ZEITPLAN
   - Woche 1: LinkedIn-Profil optimieren, Kontakte identifizieren
   - Woche 2: Connection Requests senden (5-10 Personen)
   - Woche 3: Follow-up, Informationsgespraeche vereinbaren
   - Woche 4: Bewerbung mit Referenz aus dem Netzwerk

5. DOS AND DON'TS
   ✅ Authentisch sein, echtes Interesse zeigen
   ✅ Erst Wert bieten, dann fragen
   ✅ Geduldig sein — Netzwerken dauert
   ❌ Nicht sofort nach Jobs fragen
   ❌ Nicht zu viele Nachrichten auf einmal
   ❌ Nicht copy-paste fuer alle Kontakte

Sprich Deutsch und per Du. Passe die Templates an das Profil an."""


# ============================================================
# Server runner
# ============================================================

def run_server():
    """Start the MCP server with optional web dashboard."""
    # Start web dashboard in background thread
    try:
        from .dashboard import start_dashboard
        dashboard_thread = threading.Thread(target=start_dashboard, args=(db,), daemon=True)
        dashboard_thread.start()
        logger.info("Web Dashboard gestartet auf http://localhost:8200")
    except Exception as e:
        logger.warning("Dashboard konnte nicht gestartet werden: %s", e)

    # Run MCP server (blocks on stdio)
    logger.info("Bewerbungs-Assistent MCP Server v%s gestartet", "0.7.0")
    mcp.run(transport="stdio")
