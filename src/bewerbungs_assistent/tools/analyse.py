"""Erweiterte KI-Features — 11 Tools (#169: Scoring-Regler)."""

import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path


def register(mcp, db, logger):
    """Register all 9 analysis/KI-feature tools."""

    @mcp.tool()
    def gehalt_extrahieren(job_hash: str) -> dict:
        """Extrahiert Gehaltsinformationen aus einer Stellenbeschreibung.

        Durchsucht den Text nach Gehaltsangaben (Jahresgehalt, Tagessatz,
        Stundenlohn). Falls keine Angabe gefunden wird, erstellt eine Schätzung
        basierend auf Jobtitel und Standort. Speichert die Daten in der DB.

        Args:
            job_hash: Hash der Stelle aus stellen_anzeigen()
        """
        from ..job_scraper import extract_salary_from_text, estimate_salary

        job = db.get_job(job_hash)
        if not job:
            return {"fehler": "Stelle nicht gefunden. Prüfe den Hash mit stellen_anzeigen()."}

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
                "hinweis": "Keine Gehaltsangabe erkannt und keine Schätzung möglich. "
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
            "Gehaltsdaten werden automatisch bei der Jobsuche extrahiert oder geschätzt. "
            "Nutze gehalt_extrahieren(job_hash) um einzelne Stellen gezielt zu analysieren."
        )
        return stats

    @mcp.tool()
    def firmen_recherche(firma: str) -> dict:
        """Recherchiert Informationen über eine Firma anhand der gesammelten Stellendaten.

        Aggregiert alle bekannten Jobs, Standorte, Gehälter und Remote-Level
        für die angegebene Firma.

        Args:
            firma: Name der Firma (oder Teil davon)
        """
        jobs = db.get_company_jobs(firma)
        if not jobs:
            return {
                "status": "keine_daten",
                "firma": firma,
                "hinweis": "Keine Stellen von dieser Firma in der Datenbank. "
                           "Starte eine Jobsuche oder prüfe den Firmennamen.",
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

        Zählt Skill-Keywords in allen aktiven Job-Beschreibungen und vergleicht
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
        konkrete Empfehlungen welche Kompetenzen du ergänzen solltest.

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
                return {"fehler": "Stelle nicht gefunden. Prüfe den Hash mit stellen_anzeigen()."}
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

        Zeigt Trends bei Ablehnungen: welche Firmen, welche Gründe,
        und leitet daraus Verbesserungsvorschläge ab.
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
                "Hohe Ablehnungsquote. Prüfe ob dein Profil gut zu den Stellen passt "
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
        """Plant eine Nachfass-Erinnerung für eine Bewerbung.

        Erstellt einen Follow-up Eintrag mit Datum und Template-Vorschlag.

        Args:
            bewerbung_id: ID der Bewerbung
            tage: Tage ab heute bis zum Follow-up (Standard: 7)
            typ: Art des Follow-ups: nachfass, danke, info
        """
        apps = db.get_applications()
        app = next((a for a in apps if a["id"] == bewerbung_id), None)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden. Prüfe die ID mit bewerbungen_anzeigen()."}

        scheduled = (datetime.now(timezone.utc) + timedelta(days=tage)).strftime("%Y-%m-%d")

        templates = {
            "nachfass": (
                f"Betreff: Nachfrage zu meiner Bewerbung — {app['title']}\n\n"
                f"Sehr geehrte Damen und Herren,\n\n"
                f"ich habe mich am {{applied_at}} auf die Position \"{app['title']}\" beworben "
                f"und möchte höflich nachfragen, ob Sie bereits eine Entscheidung getroffen haben.\n\n"
                f"Ich bin weiterhin sehr an der Position interessiert und stehe gerne "
                f"für ein Gespräch zur Verfügung.\n\n"
                f"Mit freundlichen Grüßen"
            ),
            "danke": (
                f"Betreff: Vielen Dank für das Gespräch — {app['title']}\n\n"
                f"Sehr geehrte/r {{ansprechpartner}},\n\n"
                f"vielen Dank für das angenehme Gespräch. Ich bin nach unserem Austausch "
                f"noch überzeugter, dass die Position \"{app['title']}\" hervorragend "
                f"zu meinen Erfahrungen passt.\n\n"
                f"Mit freundlichen Grüßen"
            ),
            "info": (
                f"Betreff: Zusätzliche Informationen — {app['title']}\n\n"
                f"Sehr geehrte Damen und Herren,\n\n"
                f"ergänzend zu meiner Bewerbung möchte ich Ihnen noch folgende "
                f"Informationen zukommen lassen: [HIER ERGAENZEN]\n\n"
                f"Mit freundlichen Grüßen"
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
        """Zeigt alle geplanten und fälligen Nachfass-Erinnerungen.

        Gruppiert nach: überfällig, heute, diese Woche, später.
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
        """Speichert den Anschreiben-Stil einer Bewerbung für A/B-Tracking.

        Damit kannst du später analysieren, welcher Stil bessere
        Rücklaufquoten hat.

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
                       "um später Rücklaufquoten pro Stil zu analysieren.",
        }

    @mcp.tool()
    def antwort_formulieren(
        bewerbung_id: str = "",
        kontext: str = "",
        ton: str = "professionell",
        sprache: str = "deutsch"
    ) -> dict:
        """Formuliert eine kurze Antwortmail für Recruiter-Kontakte.

        Nicht für vollständige Anschreiben, sondern für kurze Antworten auf:
        - Recruiter-Anfragen auf LinkedIn/XING
        - Rückfragen zu Bewerbungen
        - Terminvorschläge
        - Absage-Antworten (höflich und professionell)

        Args:
            bewerbung_id: Optional: ID einer verknuepften Bewerbung (für Kontext)
            kontext: Beschreibung der Situation (z.B. 'Recruiter fragt nach Verfügbarkeit')
            ton: professionell, locker, kurz (Standard: professionell)
            sprache: deutsch oder englisch (Standard: deutsch)
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein Profil vorhanden."}

        context_data = {
            "name": profile.get("name", ""),
            "email": profile.get("email", ""),
            "phone": profile.get("phone", ""),
        }

        if bewerbung_id:
            app = db.get_application(bewerbung_id)
            if app:
                context_data["stelle"] = app.get("title", "")
                context_data["firma"] = app.get("company", "")
                context_data["status"] = app.get("status", "")
                context_data["ansprechpartner"] = app.get("ansprechpartner", "")

        return {
            "status": "bereit",
            "kontext": kontext,
            "profil_daten": context_data,
            "ton": ton,
            "sprache": sprache,
            "anweisung": (
                "Formuliere eine kurze, passende Antwortmail basierend auf dem Kontext. "
                f"Ton: {ton}. Sprache: {sprache}. "
                "Halte die Antwort kurz (3-5 Sätze). "
                "Verwende den Namen und die Kontaktdaten aus dem Profil. "
                "Wenn eine Bewerbung verknuepft ist, beziehe dich auf die Stelle."
            ),
        }

    @mcp.tool()
    def dokument_verknuepfen(dokument_id: str, bewerbung_id: str) -> dict:
        """Verknuepft ein hochgeladenes Dokument mit einer Bewerbung.

        Damit wird das Dokument (z.B. Lebenslauf, Anschreiben, Interview-Vorbereitung)
        direkt der Bewerbung zugeordnet und erscheint in bewerbung_details().

        Args:
            dokument_id: ID des Dokuments (von dokumente_zur_analyse)
            bewerbung_id: ID der Bewerbung (von bewerbungen_anzeigen)
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}

        conn = db.connect()
        doc = conn.execute("SELECT * FROM documents WHERE id=?", (dokument_id,)).fetchone()
        if not doc:
            return {"fehler": "Dokument nicht gefunden. Prüfe die ID mit dokumente_zur_analyse()."}

        if not db.link_document_to_application(dokument_id, bewerbung_id, profile_id=db.get_active_profile_id()):
            return {"fehler": "Dokument oder Bewerbung gehoeren nicht zum aktiven Profil."}
        return {
            "status": "verknuepft",
            "dokument": doc["filename"],
            "bewerbung": f"{app.get('title', '')} bei {app.get('company', '')}",
            "nachricht": f"Dokument '{doc['filename']}' wurde der Bewerbung zugeordnet."
        }

    @mcp.tool()
    def scoring_konfigurieren(
        aktion: str = "anzeigen",
        dimension: str = "",
        sub_key: str = "",
        wert: float = 0,
        ignorieren: bool = False
    ) -> dict:
        """Konfiguriert das Scoring-Regler-System (#169).

        Jede Bewertungsdimension hat einen konfigurierbaren Regler der Punkte
        zum Basis-Fit-Score addiert oder subtrahiert.

        Dimensionen:
        - stellentyp: Bonus/Malus pro Stellenart (freelance, festanstellung, zeitarbeit, etc.)
        - remote: Bonus/Malus pro Remote-Level (remote, hybrid, vor_ort)
        - entfernung_fest: km-Stufen-Malus fuer Festanstellung (30, 50, 80, 999)
        - entfernung_freelance: km-Stufen-Malus fuer Freelance (100, 200, 999)
        - gehalt: Punkte pro 10% Abweichung vom Wunschgehalt
        - schwellenwert: Auto-Ignore-Schwelle (Stellen unter diesem Score werden ausgeblendet)

        Args:
            aktion: 'anzeigen' (alle Regler), 'setzen' (einen Regler aendern),
                    'reset' (alle auf Defaults zuruecksetzen)
            dimension: Dimension des Reglers (stellentyp, remote, entfernung_fest, etc.)
            sub_key: Unter-Schluessel (z.B. 'freelance', 'zeitarbeit', '50', 'hybrid')
            wert: Punktwert (+/- Punkte). Positiv = Bonus, Negativ = Malus.
            ignorieren: True = Stellen mit diesem Wert komplett ignorieren
        """
        if aktion == "anzeigen":
            config = db.get_scoring_config(dimension if dimension else None)
            if not config:
                return {
                    "status": "leer",
                    "nachricht": "Keine Scoring-Konfiguration vorhanden. "
                                 "Nutze scoring_konfigurieren('setzen', dimension, sub_key, wert) "
                                 "um Regler einzustellen."
                }
            # Group by dimension for readability
            grouped = {}
            for c in config:
                dim = c["dimension"]
                if dim not in grouped:
                    grouped[dim] = []
                entry = {"sub_key": c["sub_key"], "wert": c["value"]}
                if c.get("ignore_flag"):
                    entry["ignorieren"] = True
                grouped[dim].append(entry)

            return {
                "status": "ok",
                "scoring_regler": grouped,
                "schwellenwert": db.get_scoring_threshold(),
                "hinweis": "Nutze scoring_konfigurieren('setzen', dimension, sub_key, wert) "
                           "um einen Regler zu aendern. Setze ignorieren=True um einen "
                           "Wert komplett auszublenden."
            }

        elif aktion == "setzen":
            if not dimension or not sub_key:
                return {"fehler": "dimension und sub_key sind Pflicht beim Setzen."}
            db.set_scoring_config(dimension, sub_key, wert, ignorieren)
            return {
                "status": "gespeichert",
                "dimension": dimension,
                "sub_key": sub_key,
                "wert": wert,
                "ignorieren": ignorieren,
                "nachricht": f"Scoring-Regler {dimension}/{sub_key} auf {wert} gesetzt"
                             + (" (IGNORIEREN)" if ignorieren else "") + "."
            }

        elif aktion == "reset":
            # Delete all custom scoring config and re-run migration defaults
            conn = db.connect()
            pid = db.get_active_profile_id() or ""
            conn.execute("DELETE FROM scoring_config WHERE profile_id=?", (pid,))
            conn.commit()
            return {
                "status": "zurueckgesetzt",
                "nachricht": "Alle Scoring-Regler auf Standard zurueckgesetzt. "
                             "Die Defaults werden beim nächsten Start geladen."
            }

        return {"fehler": "Unbekannte Aktion. Nutze 'anzeigen', 'setzen' oder 'reset'."}

    @mcp.tool()
    def scoring_vorschau(job_hash: str) -> dict:
        """Zeigt die Scoring-Berechnung fuer eine Stelle im Detail (#169).

        Zeigt den Basis-Score UND alle Scoring-Regler-Adjustments,
        sodass der User versteht warum eine Stelle hoch oder niedrig bewertet wird.

        Args:
            job_hash: Hash der Stelle
        """
        job = db.get_job(job_hash)
        if not job:
            return {"fehler": "Stelle nicht gefunden."}

        from ..services.scoring_service import apply_scoring_adjustments
        result = apply_scoring_adjustments(job, job.get("score", 0), db)

        return {
            "stelle": f"{job.get('title', '')} bei {job.get('company', '')}",
            "basis_score": result.get("basis_score", 0),
            "adjustments": result.get("adjustments", []),
            "adjustment_total": result.get("adjustment_total", 0),
            "final_score": result.get("final_score", 0),
            "ignoriert": result.get("ignored", False),
            "hinweis": "Passe die Regler mit scoring_konfigurieren('setzen', ...) an."
        }

    @mcp.tool()
    def pbp_diagnose(auto_fix: bool = False) -> dict:
        """Führt einen umfassenden Gesundheitscheck des PBP-Systems durch.

        Prüft die Datenbank auf bekannte Probleme, fehlende Daten, Inkonsistenzen
        und gibt konkrete Handlungsempfehlungen. Ideal wenn etwas nicht funktioniert
        oder du dir unsicher bist ob alles korrekt eingerichtet ist.

        Bei auto_fix=True werden einfache Probleme automatisch behoben.

        Args:
            auto_fix: True = behebbare Probleme automatisch fixen (Standard: False)
        """
        probleme = []
        warnungen = []
        info = []
        fixes = []

        # --- 1. Profil-Check ---
        profile = db.get_profile()
        if not profile:
            probleme.append({
                "bereich": "Profil",
                "problem": "Kein aktives Profil vorhanden",
                "loesung": "Erstelle ein Profil mit /ersterfassung oder profil_erstellen()",
                "schwere": "kritisch",
            })
        else:
            name = profile.get("name") or profile.get("full_name", "")
            if not name:
                warnungen.append({
                    "bereich": "Profil",
                    "problem": "Profil hat keinen Namen",
                    "loesung": "profil_bearbeiten(name='Dein Name')",
                })
            skills = profile.get("skills", [])
            if len(skills) < 3:
                warnungen.append({
                    "bereich": "Profil",
                    "problem": f"Nur {len(skills)} Skills hinterlegt — zu wenig für gutes Matching",
                    "loesung": "skill_hinzufuegen() oder /profil_erweiterung nutzen",
                })
            positions = profile.get("positions", [])
            if not positions:
                warnungen.append({
                    "bereich": "Profil",
                    "problem": "Keine Berufserfahrung hinterlegt",
                    "loesung": "position_hinzufuegen() oder Lebenslauf hochladen",
                })

        # --- 2. Suchkriterien-Check ---
        criteria = db.get_search_criteria()
        muss = criteria.get("keywords_muss", [])
        plus = criteria.get("keywords_plus", [])
        if not muss and not plus:
            probleme.append({
                "bereich": "Suchkriterien",
                "problem": "Keine Suchbegriffe definiert — Scoring kann nicht funktionieren",
                "loesung": "suchkriterien_setzen() oder /jobsuche_workflow starten",
                "schwere": "kritisch",
            })
        elif not muss:
            warnungen.append({
                "bereich": "Suchkriterien",
                "problem": "Keine MUSS-Keywords — alle Stellen bekommen Score 0",
                "loesung": "suchkriterien_setzen('keywords_muss', ['Keyword1', 'Keyword2'])",
            })

        # --- 3. Stellen-Check ---
        try:
            active_jobs = db.get_active_jobs()
            total_jobs = len(active_jobs)

            if total_jobs == 0:
                info.append({
                    "bereich": "Stellen",
                    "meldung": "Keine aktiven Stellen. Starte eine Jobsuche mit /jobsuche_workflow.",
                })
            else:
                # Jobs ohne Beschreibung
                ohne_beschreibung = [
                    j for j in active_jobs
                    if len((j.get("description") or "").strip()) < 50
                ]
                if ohne_beschreibung:
                    warnungen.append({
                        "bereich": "Stellen",
                        "problem": f"{len(ohne_beschreibung)} von {total_jobs} Stellen ohne Beschreibung — Score ist unzuverlässig",
                        "stellen": [
                            {"id": j["hash"][:8], "titel": j.get("title", ""), "firma": j.get("company", "")}
                            for j in ohne_beschreibung[:5]
                        ],
                        "loesung": "Öffne die Stellen-URLs und lade die Beschreibung nach (stelle_manuell_anlegen oder fit_analyse)",
                    })

                # Jobs mit Score 0
                score_null = [j for j in active_jobs if j.get("score", 0) == 0 and not j.get("is_pinned")]
                if score_null and len(score_null) > total_jobs * 0.5:
                    warnungen.append({
                        "bereich": "Scoring",
                        "problem": f"{len(score_null)} von {total_jobs} Stellen haben Score 0 — Keywords passen nicht zu den Stellenangeboten",
                        "loesung": "Prüfe deine MUSS-Keywords mit keyword_vorschlaege() oder suchkriterien_anzeigen()",
                    })

                # Quellen-Verteilung
                sources = {}
                for j in active_jobs:
                    src = j.get("source", "unbekannt")
                    sources[src] = sources.get(src, 0) + 1
                info.append({
                    "bereich": "Stellen",
                    "meldung": f"{total_jobs} aktive Stellen aus {len(sources)} Quellen",
                    "quellen": sources,
                })
        except Exception as e:
            probleme.append({
                "bereich": "Datenbank",
                "problem": f"Fehler beim Lesen der Stellen: {e}",
                "schwere": "kritisch",
            })

        # --- 4. Bewerbungs-Check ---
        try:
            apps = db.get_applications()
            if apps:
                # Source leer?
                ohne_source = [a for a in apps if not (a.get("source") or "").strip()]
                if ohne_source:
                    warnungen.append({
                        "bereich": "Bewerbungen",
                        "problem": f"{len(ohne_source)} von {len(apps)} Bewerbungen ohne Quelle",
                        "loesung": "bewerbung_bearbeiten(id, source='stepstone') oder automatisch bei neuen Bewerbungen",
                    })
                    if auto_fix:
                        fixed = 0
                        for a in ohne_source:
                            if a.get("job_hash"):
                                job = db.get_job(a["job_hash"])
                                if job and job.get("source"):
                                    db.update_application(a["id"], {"source": job["source"]})
                                    fixed += 1
                        if fixed:
                            fixes.append(f"{fixed} Bewerbungen: source aus verknüpfter Stelle nachgetragen")

                # Zombies: Seit >60 Tagen in beworben ohne Update
                _now = datetime.now()
                zombies = []
                for a in apps:
                    if a.get("status") in ("beworben", "offen"):
                        date_str = a.get("applied_at") or a.get("created_at") or ""
                        if date_str:
                            try:
                                app_date = datetime.fromisoformat(date_str[:19])
                                if (_now - app_date).days > 60:
                                    zombies.append({
                                        "id": a["id"][:8],
                                        "titel": a.get("title", ""),
                                        "firma": a.get("company", ""),
                                        "tage": (_now - app_date).days,
                                    })
                            except (ValueError, TypeError):
                                pass
                if zombies:
                    warnungen.append({
                        "bereich": "Bewerbungen",
                        "problem": f"{len(zombies)} Zombie-Bewerbungen (>60 Tage ohne Update)",
                        "bewerbungen": zombies[:5],
                        "loesung": "Status aktualisieren oder als abgelehnt/zurückgezogen markieren",
                    })

                # Pipeline-Übersicht
                by_status = {}
                for a in apps:
                    s = a.get("status", "offen")
                    by_status[s] = by_status.get(s, 0) + 1
                info.append({
                    "bereich": "Bewerbungen",
                    "meldung": f"{len(apps)} Bewerbungen",
                    "pipeline": by_status,
                })
        except Exception as e:
            probleme.append({
                "bereich": "Datenbank",
                "problem": f"Fehler beim Lesen der Bewerbungen: {e}",
                "schwere": "kritisch",
            })

        # --- 5. Blacklist-Check ---
        try:
            blacklist = db.get_blacklist()
            invalid = [b for b in blacklist if b.get("type") not in ("firma", "keyword")]
            if invalid:
                warnungen.append({
                    "bereich": "Blacklist",
                    "problem": f"{len(invalid)} Einträge mit ungültigem Typ (nicht firma/keyword)",
                    "loesung": "Diese Einträge haben keine Wirkung. Entferne sie mit blacklist_verwalten('entfernen', entry_id=...)",
                })
        except Exception:
            pass

        # --- 6. Scoring-Config-Check ---
        try:
            scoring = db.get_scoring_config()
            if not scoring:
                info.append({
                    "bereich": "Scoring",
                    "meldung": "Keine individuellen Scoring-Regler konfiguriert (Standardwerte aktiv). "
                               "Nutze scoring_konfigurieren() für Feintuning.",
                })
        except Exception:
            pass

        # --- 7. Dokumente-Integritaet (#441) ---
        # Prueft ob physische Dateien zu den Dokumenten-DB-Eintraegen existieren.
        # Nach dem v1.4.x → v1.5.0 Dual-DB-Migration-Bug koennen Files verloren gegangen sein.
        try:
            from ..database import get_data_dir
            docs = db._get_documents()
            if docs:
                missing = []
                missing_fixable = []
                dokumente_dir = get_data_dir() / "dokumente"

                for d in docs:
                    fp = d.get("filepath")
                    if not fp:
                        continue
                    if Path(fp).exists():
                        continue
                    # Datei fehlt — versuche sie im Standard-Dokumenten-Ordner zu finden
                    entry = {
                        "id": d.get("id", "")[:8],
                        "filename": d.get("filename", ""),
                        "doc_type": d.get("doc_type", ""),
                        "erwartet_unter": fp,
                    }
                    filename = d.get("filename", "")
                    candidate = dokumente_dir / filename if filename else None
                    if candidate and candidate.exists():
                        entry["gefunden_unter"] = str(candidate)
                        missing_fixable.append((d, candidate, entry))
                    else:
                        missing.append(entry)

                if auto_fix and missing_fixable:
                    fixed_count = 0
                    conn = db.connect()
                    for d, candidate, entry in missing_fixable:
                        try:
                            conn.execute(
                                "UPDATE documents SET filepath=? WHERE id=?",
                                (str(candidate), d["id"]),
                            )
                            fixed_count += 1
                        except Exception as exc:
                            logger.debug("Auto-Fix filepath fehlgeschlagen fuer %s: %s", d.get("id"), exc)
                    if fixed_count:
                        conn.commit()
                        fixes.append(
                            f"{fixed_count} Dokumente: filepath auf gefundene Datei in dokumente/ umgebogen"
                        )
                    # Nicht-fixbare bleiben in missing, fixable wurden oben behandelt
                else:
                    # Ohne auto_fix: alle als Warnung/Problem melden
                    for _, _, entry in missing_fixable:
                        entry["loesung"] = (
                            "Datei existiert im dokumente/-Ordner, aber DB zeigt auf alten Pfad. "
                            "Nutze pbp_diagnose(auto_fix=True) zum Reparieren."
                        )
                        missing.append(entry)

                if missing:
                    anteil = len(missing) / len(docs) if docs else 0
                    schwere = "kritisch" if anteil > 0.5 else "warnung"
                    eintrag = {
                        "bereich": "Dokumente",
                        "problem": (
                            f"{len(missing)} von {len(docs)} Dokumenten haben fehlende Dateien "
                            "(DB-Eintrag vorhanden, Datei fehlt auf Disk). "
                            "Moegliche Ursache: v1.4.x → v1.5.0 Dual-DB-Migration."
                        ),
                        "dokumente": missing[:10],
                        "loesung": (
                            "1) pbp_diagnose(auto_fix=True) fuer automatische Reparatur "
                            "(findet Dateien im dokumente/-Ordner und korrigiert Pfade). "
                            "2) Fehlende Dateien erneut hochladen. "
                            "3) Verwaiste DB-Eintraege manuell entfernen."
                        ),
                    }
                    if schwere == "kritisch":
                        eintrag["schwere"] = "kritisch"
                        probleme.append(eintrag)
                    else:
                        warnungen.append(eintrag)
                else:
                    info.append({
                        "bereich": "Dokumente",
                        "meldung": f"{len(docs)} Dokumente, alle physischen Dateien vorhanden.",
                    })
        except Exception as e:
            logger.debug("Dokumente-Integritaetspruefung fehlgeschlagen: %s", e)

        # --- Ergebnis ---
        gesundheit = "kritisch" if probleme else "warnungen" if warnungen else "gesund"
        result = {
            "status": gesundheit,
            "zusammenfassung": (
                f"{len(probleme)} Probleme, {len(warnungen)} Warnungen, {len(info)} Infos"
            ),
        }
        if probleme:
            result["probleme"] = probleme
        if warnungen:
            result["warnungen"] = warnungen
        if info:
            result["info"] = info
        if fixes:
            result["automatisch_behoben"] = fixes
        if gesundheit == "gesund":
            result["nachricht"] = "Alles in Ordnung! Dein PBP-System ist gesund."
        elif gesundheit == "kritisch":
            result["nachricht"] = "Es gibt kritische Probleme die zuerst behoben werden müssen."
        else:
            result["nachricht"] = "Es gibt Verbesserungsmöglichkeiten. Schau dir die Warnungen an."

        # Bugreport-Hinweis bei kritischen Problemen
        if probleme:
            result["bugreport_hinweis"] = (
                "Falls du ein technisches Problem vermutest, erstelle einen Bugreport: "
                "Kopiere diese Diagnose-Ausgabe und sende sie an den Entwickler."
            )

        return result

    @mcp.tool()
    def keyword_vorschlaege() -> dict:
        """Analysiert aktive Stellen und schlägt Keyword-Anpassungen vor (#184).

        Prüft welche Keywords in den Stellenbeschreibungen häufig vorkommen
        aber NICHT in den Suchkriterien enthalten sind, und umgekehrt.

        Ideal nach einer Jobsuche: 'Passen meine Keywords noch?'
        """
        criteria = db.get_search_criteria()
        muss = [kw.lower() for kw in criteria.get("keywords_muss", [])]
        plus = [kw.lower() for kw in criteria.get("keywords_plus", [])]
        ausschluss = [kw.lower() for kw in criteria.get("keywords_ausschluss", [])]
        alle_keywords = set(muss + plus)

        jobs = db.get_active_jobs(exclude_blacklisted=True)
        if not jobs:
            return {"nachricht": "Keine aktiven Stellen. Starte zuerst eine Jobsuche."}

        # Zähle häufige Begriffe in gut bewerteten Stellen
        good_jobs = [j for j in jobs if j.get("score", 0) >= 3]
        bad_jobs = [j for j in jobs if j.get("score", 0) <= 1]

        from collections import Counter as _Counter
        good_words = _Counter()
        bad_words = _Counter()

        # Relevante Fachbegriffe extrahieren (Wörter > 3 Zeichen, keine Stoppwörter)
        _stopwords = {"und", "oder", "der", "die", "das", "den", "dem", "ein", "eine",
                      "ist", "sind", "hat", "haben", "wird", "werden", "mit", "von",
                      "fuer", "für", "als", "bei", "zur", "zum", "auf", "aus", "nach",
                      "nicht", "auch", "sich", "wir", "sie", "uns", "ihr", "ihre",
                      "unser", "unsere", "deine", "ihre", "m/w/d", "m/w", "gmbh",
                      "bieten", "suchen", "ihre", "gerne", "dich", "dein", "team",
                      "arbeit", "deutsch", "english", "stelle", "stellen", "job"}

        def _extract_terms(text):
            words = re.findall(r'[a-zA-ZäöüÄÖÜß]{4,}', text.lower())
            return [w for w in words if w not in _stopwords]

        for j in good_jobs:
            text = f"{j.get('title', '')} {(j.get('description') or '')[:1000]}"
            for term in _extract_terms(text):
                good_words[term] += 1
        for j in bad_jobs:
            text = f"{j.get('title', '')} {(j.get('description') or '')[:1000]}"
            for term in _extract_terms(text):
                bad_words[term] += 1

        # Vorschläge berechnen
        vorschlaege_plus = []
        vorschlaege_ausschluss = []

        min_freq = max(2, len(good_jobs) // 4) if good_jobs else 2
        for term, count in good_words.most_common(50):
            if term not in alle_keywords and count >= min_freq:
                # Kommt häufig in guten Jobs vor, aber nicht in Keywords
                ratio = count / max(1, bad_words.get(term, 0))
                if ratio >= 2:  # Mindestens doppelt so häufig in guten Jobs
                    vorschlaege_plus.append({
                        "keyword": term,
                        "in_guten_stellen": count,
                        "in_schlechten_stellen": bad_words.get(term, 0),
                    })

        min_bad_freq = max(2, len(bad_jobs) // 4) if bad_jobs else 2
        for term, count in bad_words.most_common(30):
            if term not in alle_keywords and term not in ausschluss and count >= min_bad_freq:
                ratio = count / max(1, good_words.get(term, 0))
                if ratio >= 3:  # Dreimal häufiger in schlechten Jobs
                    vorschlaege_ausschluss.append({
                        "keyword": term,
                        "in_schlechten_stellen": count,
                        "in_guten_stellen": good_words.get(term, 0),
                    })

        # Keywords die in keiner Stelle vorkommen (tote Keywords)
        from ..job_scraper import _fuzzy_keyword_match
        tote_keywords = []
        all_text = " ".join(
            f"{j.get('title', '')} {(j.get('description') or '')[:500]}"
            for j in jobs
        ).lower()
        for kw in muss + plus:
            if not _fuzzy_keyword_match(kw, all_text):
                tote_keywords.append(kw)

        return {
            "aktive_stellen": len(jobs),
            "gut_bewertet": len(good_jobs),
            "schlecht_bewertet": len(bad_jobs),
            "aktuelle_keywords": {
                "muss": muss,
                "plus": plus,
                "ausschluss": ausschluss,
            },
            "vorschlaege_plus": vorschlaege_plus[:10],
            "vorschlaege_ausschluss": vorschlaege_ausschluss[:5],
            "tote_keywords": tote_keywords,
            "hinweis": (
                "Nutze suchkriterien_bearbeiten() um Keywords anzupassen. "
                "Tote Keywords matchen in keiner aktiven Stelle — prüfe ob sie noch relevant sind."
            ) if tote_keywords or vorschlaege_plus else
            "Deine Keywords passen gut zu den aktuellen Stellen."
        }

    @mcp.tool()
    def recherche_speichern(
        text: str,
        job_hash: str = "",
        bewerbung_id: str = "",
        kategorie: str = "allgemein"
    ) -> dict:
        """Speichert eine Recherche-Analyse dauerhaft zu einer Stelle oder Bewerbung (#240).

        Nutze dieses Tool, um Ergebnisse aus firmen_recherche(), branchen_trends(),
        skill_gap_analyse() oder eigene Notizen zu persistieren. Gespeicherte
        Recherchen bleiben über Chat-Sessions hinweg erhalten.

        Args:
            text: Der Analysetext / die Recherche-Ergebnisse
            job_hash: Hash der Stelle (optional, wenn stellenbezogen)
            bewerbung_id: ID der Bewerbung (optional, wenn bewerbungsbezogen)
            kategorie: Art der Recherche (allgemein, firmenrecherche, skillgap, gehalt, markt)
        """
        if not job_hash and not bewerbung_id:
            return {"fehler": "Entweder job_hash oder bewerbung_id muss angegeben werden."}

        now = datetime.now().isoformat()
        saved_to = []

        if job_hash:
            job = db.get_job(job_hash)
            if not job:
                return {"fehler": f"Stelle {job_hash} nicht gefunden."}
            existing = job.get("research_notes") or ""
            entry = f"\n\n--- {kategorie} ({now[:10]}) ---\n{text}"
            new_notes = (existing + entry).strip()
            # #270: resolve to stored hash (public hash differs in multi-profile)
            stored_hash = db.resolve_job_hash(job_hash)
            conn = db.connect()
            conn.execute(
                "UPDATE jobs SET research_notes=?, updated_at=? WHERE hash=?",
                (new_notes, now, stored_hash)
            )
            conn.commit()
            saved_to.append(f"Stelle {job_hash}")

        if bewerbung_id:
            app = db.get_application(bewerbung_id)
            if not app:
                return {"fehler": f"Bewerbung {bewerbung_id} nicht gefunden."}
            existing = app.get("fit_analyse") or ""
            if existing:
                try:
                    data = json.loads(existing)
                except (json.JSONDecodeError, TypeError):
                    data = {"vorherige_analyse": existing}
            else:
                data = {}
            data[f"{kategorie}_{now[:10]}"] = text
            db.save_fit_analyse(bewerbung_id, data)
            saved_to.append(f"Bewerbung {bewerbung_id}")

        return {
            "status": "gespeichert",
            "gespeichert_in": saved_to,
            "kategorie": kategorie,
            "laenge": len(text),
            "hinweis": "Die Recherche ist jetzt dauerhaft gespeichert und bleibt über Chat-Sessions hinweg verfügbar."
        }
