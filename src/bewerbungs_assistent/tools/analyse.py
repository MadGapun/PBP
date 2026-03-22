"""Erweiterte KI-Features — 11 Tools (#169: Scoring-Regler)."""

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

        db.link_document_to_application(dokument_id, bewerbung_id)
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
                             "Die Defaults werden beim naechsten Start geladen."
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
