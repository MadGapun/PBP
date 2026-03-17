"""Erweiterte KI-Features — 9 Tools."""

import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta


def register(mcp, db, logger):
    """Register all 9 analysis/KI-feature tools."""

    @mcp.tool()
    def gehalt_extrahieren(job_hash: str) -> dict:
        """Extrahiert Gehaltsinformationen aus einer Stellenbeschreibung.

        Durchsucht den Text nach Gehaltsangaben (Jahresgehalt, Tagessatz,
        Stundenlohn). Falls keine Angabe gefunden wird, erstellt eine Schaetzung
        basierend auf Jobtitel und Standort. Speichert die Daten in der DB.

        Args:
            job_hash: Hash der Stelle aus stellen_anzeigen()
        """
        from ..job_scraper import extract_salary_from_text, estimate_salary

        job = db.get_job(job_hash)
        if not job:
            return {"fehler": "Stelle nicht gefunden. Pruefe den Hash mit stellen_anzeigen()."}

        text = (job["description"] or "") + " " + (job["salary_info"] or "") + " " + (job["title"] or "")

        # Try extraction first
        salary_min, salary_max, salary_type = extract_salary_from_text(text)
        is_estimated = False

        # Fallback: estimate if not found
        if salary_min is None:
            salary_min, salary_max, salary_type = estimate_salary(
                job["title"] or "", job.get("employment_type", ""), job.get("location", "")
            )
            is_estimated = True

        if salary_min is None:
            return {
                "status": "nicht_gefunden",
                "stelle": job["title"],
                "firma": job["company"],
                "hinweis": "Keine Gehaltsangabe erkannt und keine Schaetzung moeglich. "
                           "Du kannst Claude bitten, den Text manuell zu analysieren.",
                "salary_info_text": job.get("salary_info", ""),
            }

        # Save to database
        db.save_salary_data(job_hash, salary_min, salary_max, salary_type)
        if is_estimated:
            conn = db.connect()
            target_hash = db.resolve_job_hash(job_hash)
            conn.execute(
                "UPDATE jobs SET salary_estimated=1 WHERE hash=?", (target_hash,)
            )
            conn.commit()

        # Compare with profile preferences
        profile = db.get_profile()
        vergleich = {}
        if profile and profile.get("preferences"):
            prefs = profile["preferences"]
            if salary_type in ("jaehrlich", "jahr") and prefs.get("min_gehalt"):
                min_g = float(prefs["min_gehalt"])
                vergleich["dein_minimum"] = min_g
                vergleich["passt"] = salary_max >= min_g
                if prefs.get("ziel_gehalt"):
                    vergleich["dein_ziel"] = float(prefs["ziel_gehalt"])
            elif salary_type in ("taeglich", "tag") and prefs.get("min_tagessatz"):
                min_t = float(prefs["min_tagessatz"])
                vergleich["dein_minimum"] = min_t
                vergleich["passt"] = salary_max >= min_t

        return {
            "status": "geschaetzt" if is_estimated else "extrahiert",
            "stelle": job["title"],
            "firma": job["company"],
            "gehalt_min": salary_min,
            "gehalt_max": salary_max,
            "gehalt_typ": salary_type,
            "geschaetzt": is_estimated,
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
            "Gehaltsdaten werden automatisch bei der Jobsuche extrahiert oder geschaetzt. "
            "Nutze gehalt_extrahieren(job_hash) um einzelne Stellen gezielt zu analysieren."
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
    def skill_gap_analyse(job_hash: str = "") -> dict:
        """Vergleicht dein Profil mit einer Stelle oder allen aktiven Stellen.

        Zeigt welche Skills dir fehlen, welche gut passen, und gibt
        konkrete Empfehlungen welche Kompetenzen du ergaenzen solltest.

        Args:
            job_hash: Hash einer spezifischen Stelle (leer = alle aktiven Stellen analysieren)
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein aktives Profil. Erstelle zuerst eins mit /ersterfassung."}

        user_skills = set()
        for s in profile.get("skills", []):
            user_skills.add(s["name"].lower())
        # Add technologies from positions
        for pos in profile.get("positions", []):
            if pos.get("technologies"):
                for tech in re.split(r"[,;/\s]+", pos["technologies"]):
                    if len(tech) > 1:
                        user_skills.add(tech.strip().lower())

        if job_hash:
            job = db.get_job(job_hash)
            if not job:
                return {"fehler": "Stelle nicht gefunden. Pruefe den Hash mit stellen_anzeigen()."}
            jobs = [job]
        else:
            jobs = db.get_active_jobs()[:50]

        if not jobs:
            return {"fehler": "Keine aktiven Stellen vorhanden. Starte zuerst eine Jobsuche."}

        # Extract skill requirements from job descriptions
        required_skills = Counter()
        for job in jobs:
            text = (job.get("description") or "") + " " + (job.get("title") or "")
            # Look for common skill patterns
            words = set(re.findall(r'\b[A-Z][a-zA-Z+#.]+\b', text))
            for w in words:
                if len(w) > 1:
                    required_skills[w.lower()] += 1

        # Classify skills
        matches = []
        gaps = []
        for skill, count in required_skills.most_common(50):
            if skill in user_skills or any(skill in us for us in user_skills):
                matches.append({"skill": skill, "nachfrage": count})
            elif count >= 2 or (job_hash and count >= 1):
                gaps.append({"skill": skill, "nachfrage": count})

        # Calculate match percentage
        total_relevant = len(matches) + len(gaps)
        match_pct = round(len(matches) / total_relevant * 100) if total_relevant > 0 else 0

        result = {
            "status": "ok",
            "analysierte_stellen": len(jobs),
            "match_prozent": match_pct,
            "vorhandene_skills": matches[:15],
            "fehlende_skills": gaps[:15],
            "deine_skills_gesamt": len(user_skills),
        }
        if job_hash and jobs:
            result["stelle"] = jobs[0].get("title")
            result["firma"] = jobs[0].get("company")

        return result

    @mcp.tool()
    def ablehnungs_muster() -> dict:
        """Analysiert Ablehnungsmuster bei deinen Bewerbungen.

        Zeigt Trends bei Ablehnungen: welche Firmen, welche Gruende,
        und leitet daraus Verbesserungsvorschlaege ab.
        """
        patterns = db.get_rejection_patterns()
        if patterns["anzahl"] == 0:
            return patterns

        # Calculate rejection rate
        stats = db.get_statistics()
        total = stats.get("total_applications", 0)
        patterns["ablehnungsquote"] = round(patterns["anzahl"] / total * 100, 1) if total > 0 else 0

        # Generate recommendations
        empfehlungen = []
        if patterns["ablehnungsquote"] > 60:
            empfehlungen.append(
                "Hohe Ablehnungsquote. Pruefe ob dein Profil gut zu den Stellen passt "
                "(/profil_analyse) oder fokussiere dich auf besser passende Stellen."
            )
        if patterns.get("nach_grund", {}).get("Kein Grund angegeben", 0) > 3:
            empfehlungen.append(
                "Viele Ablehnungen ohne Grund. Frage aktiv nach Feedback — "
                "nutze nachfass_planen() mit typ='info'."
            )
        repeated_companies = [c for c, n in patterns.get("nach_firma", {}).items() if n >= 2]
        if repeated_companies:
            empfehlungen.append(
                f"Mehrfach abgelehnt bei: {', '.join(repeated_companies[:3])}. "
                "Eventuell Profil anpassen oder andere Firmen fokussieren."
            )
        patterns["empfehlungen"] = empfehlungen
        return patterns

    @mcp.tool()
    def nachfass_planen(bewerbung_id: str, tage: int = 7, typ: str = "nachfass") -> dict:
        """Plant eine Nachfass-Erinnerung fuer eine Bewerbung.

        Erstellt einen Follow-up Eintrag mit Datum und Template-Vorschlag.

        Args:
            bewerbung_id: ID der Bewerbung
            tage: Tage ab heute bis zum Follow-up (Standard: 7)
            typ: Art des Follow-ups: nachfass, danke, info
        """
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
