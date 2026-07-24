"""Erweiterte KI-Features — 11 Tools (#169: Scoring-Regler)."""

import json
import re
from collections import Counter
from datetime import datetime, timezone, timedelta
from pathlib import Path


def register(mcp, db, logger):
    """Register all 9 analysis/KI-feature tools."""
    from . import ki_gate, get_recent_tool_calls, get_slow_tool_calls

    def _persist_recherche(kategorie, text, bewerbung_id="", job_hash=""):
        """#674 Ein-Schritt-Persistenz: legt eine Analyse als research_notes-
        Eintrag ab, sobald eine Bewerbung oder Stelle angegeben ist. Bindet bei
        einer Bewerbung ohne expliziten job_hash die verknuepfte Stelle mit.
        Gibt das Ziel-Dict zurueck oder None (nichts persistiert)."""
        if not bewerbung_id and not job_hash:
            return None
        ziel_job = job_hash
        if bewerbung_id and not job_hash:
            app = db.get_application(bewerbung_id)
            if app and app.get("job_hash"):
                ziel_job = app["job_hash"]
        nid = db.add_research_note(
            kategorie, text,
            bewerbung_id=bewerbung_id or None,
            job_hash=ziel_job or None,
        )
        ziele = []
        if bewerbung_id:
            ziele.append(f"Bewerbung {bewerbung_id}")
        if ziel_job:
            ziele.append(f"Stelle {str(ziel_job)[:8]}")
        return {"id": nid, "kategorie": kategorie, "gespeichert_in": ziele,
                "ziel": "research_notes-Tabelle (Abschnitt 'Recherchen')"}

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
    def firmen_recherche(firma: str, bewerbung_id: str = "", job_hash: str = "") -> dict:
        """Recherchiert Informationen über eine Firma anhand der gesammelten Stellendaten.

        Aggregiert alle bekannten Jobs, Standorte, Gehälter und Remote-Level
        für die angegebene Firma.

        Args:
            firma: Name der Firma (oder Teil davon)
            bewerbung_id: Optional — wird die Recherche im selben Aufruf an diese
                Bewerbung gespeichert (#674, Kategorie 'firmenrecherche').
            job_hash: Optional — speichert die Recherche an diese Stelle.
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
        # #674: optionale Ein-Schritt-Persistenz
        if bewerbung_id or job_hash:
            teile = [f"Firmen-Recherche {firma}: {result['stellen_gesamt']} Stellen "
                     f"({result['stellen_aktiv']} aktiv)."]
            if standorte:
                teile.append("Standorte: " + ", ".join(standorte[:5]) + ".")
            if result.get("gehaltsspanne"):
                teile.append(f"Gehalt: {result['gehaltsspanne']['min']}-"
                             f"{result['gehaltsspanne']['max']}.")
            teile.append(f"Quellen: {', '.join(quellen)}. Score best "
                         f"{result['score_best']}, Schnitt {result['score_durchschnitt']}.")
            ziel = _persist_recherche("firmenrecherche", " ".join(teile),
                                      bewerbung_id, job_hash)
            if ziel:
                result["gespeichert_als"] = ziel
        return result

    @mcp.tool()
    def branchen_trends(bewerbung_id: str = "") -> dict:
        """Analysiert gefragte Skills und Technologien in den gesammelten Stellenangeboten.

        Zählt Skill-Keywords in allen aktiven Job-Beschreibungen und vergleicht
        mit deinem Profil (Match/Gap-Analyse).

        Args:
            bewerbung_id: Optional — speichert die Markt-Analyse im selben Aufruf
                an diese Bewerbung (#674, Kategorie 'markt').
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

        ergebnis = {
            "status": "ok",
            "analysierte_stellen": total_jobs,
            "top_skills": top_20,
            "skill_gap": skill_gap[:10] if skill_gap else [],
            "tipp": "Skills die im Markt gefragt sind aber in deinem Profil fehlen, "
                    "sind unter 'skill_gap' aufgelistet.",
        }
        # #674: optionale Ein-Schritt-Persistenz
        if bewerbung_id:
            top = ", ".join(f"{s['skill']} ({s['nennungen']})" for s in top_20[:8])
            gap = ", ".join(g["skill"] for g in (skill_gap[:8] or []))
            txt = f"Markt-Trends ({total_jobs} Stellen). Top-Skills: {top}."
            if gap:
                txt += f" Luecken im Profil: {gap}."
            ziel = _persist_recherche("markt", txt, bewerbung_id)
            if ziel:
                ergebnis["gespeichert_als"] = ziel
        return ergebnis

    @mcp.tool()
    def skill_gap_analyse(job_hash: str = "", bewerbung_id: str = "") -> dict:
        """Vergleicht dein Profil mit einer Stelle oder allen aktiven Stellen.

        Zeigt welche Skills dir fehlen, welche gut passen, und gibt
        konkrete Empfehlungen welche Kompetenzen du ergänzen solltest.

        Args:
            job_hash: Hash einer spezifischen Stelle (leer = alle aktiven Stellen analysieren)
            bewerbung_id: Optional — speichert die Gap-Analyse im selben Aufruf an
                diese Bewerbung (#674, Kategorie 'skillgap').
        """
        gate = ki_gate(db, "stellenanalyse")
        if gate is not None:
            return gate
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

        # #674: optionale Ein-Schritt-Persistenz (nur bei expliziter Bewerbung)
        if bewerbung_id:
            fehlend = ", ".join(g["skill"] for g in gaps[:10]) or "keine"
            vorhanden = ", ".join(m["skill"] for m in matches[:10]) or "keine"
            txt = (f"Skill-Gap ({len(jobs)} Stellen, Match {match_pct}%). "
                   f"Fehlend: {fehlend}. Vorhanden: {vorhanden}.")
            ziel = _persist_recherche("skillgap", txt, bewerbung_id, job_hash)
            if ziel:
                result["gespeichert_als"] = ziel

        return result

    @mcp.tool()
    def ablehnungs_muster() -> dict:
        """Analysiert Ablehnungsmuster bei deinen Bewerbungen.

        Zeigt Trends bei Ablehnungen: welche Firmen, welche Gründe,
        und leitet daraus Verbesserungsvorschläge ab.
        """
        gate = ki_gate(db, "coaching")
        if gate is not None:
            return gate
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
    def nachfass_planen(
        bewerbung_id: str,
        tage: int = 7,
        typ: str = "nachfass",
        wenn_dublette: str = "melden",
    ) -> dict:
        """Plant eine Nachfass-Erinnerung für eine Bewerbung.

        Erstellt einen Follow-up Eintrag mit Datum und Template-Vorschlag.

        v1.7.0-beta.83 (#665): Dubletten-Check. Wenn bereits ein offener
        Nachfass (typ='nachfass', status='geplant') fuer dieselbe Bewerbung
        existiert, wird je nach `wenn_dublette` reagiert:

        - `melden` (Default): KEIN neuer Eintrag wird angelegt. Stattdessen
          liefert das Tool `status='dublette_offen'` zurueck — mit Details
          zum bestehenden Nachfass und konkreten Handlungsoptionen.
          Claude soll dann den User fragen und mit dem expliziten
          `wenn_dublette`-Wert erneut aufrufen.
        - `vorhandenen_erledigen`: bestehenden offenen Nachfass auf
          `gesendet` setzen + neuen anlegen. Default-Empfehlung wenn der
          User aktiv neu plant.
        - `vorhandenen_verschieben`: bestehenden offenen Nachfass auf das
          neue Datum aktualisieren statt einen zweiten anzulegen.
        - `trotzdem_neu`: bestehenden lassen + zusaetzlich neuen anlegen
          (das alte Verhalten — bewusst zweite Dublette wollen).

        Args:
            bewerbung_id: ID der Bewerbung
            tage: Tage ab heute bis zum Follow-up (Standard: 7)
            typ: Art des Follow-ups: nachfass, danke, info
            wenn_dublette: Verhalten bei bereits offenem Nachfass —
                melden (Default), vorhandenen_erledigen,
                vorhandenen_verschieben, trotzdem_neu
        """
        apps = db.get_applications()
        app = next((a for a in apps if a["id"] == bewerbung_id), None)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden. Prüfe die ID mit bewerbungen_anzeigen()."}

        scheduled = (datetime.now(timezone.utc) + timedelta(days=tage)).strftime("%Y-%m-%d")

        # v1.7.0-beta.83 (#665): Dubletten-Check
        # NUR fuer typ='nachfass' — danke/info-Follow-ups sind situativ
        # und sollen NICHT dedupliziert werden.
        existing_open: list[dict] = []
        if typ == "nachfass":
            try:
                pending = db.get_pending_follow_ups()
                existing_open = [
                    fu for fu in pending
                    if fu.get("application_id") == bewerbung_id
                    and (fu.get("follow_up_type") or "nachfass") == "nachfass"
                ]
            except Exception:
                existing_open = []

        if existing_open and wenn_dublette == "melden":
            ex = existing_open[0]
            return {
                "status": "dublette_offen",
                "bewerbung": app["title"],
                "firma": app["company"],
                "bestehender_nachfass": {
                    "follow_up_id": ex.get("id"),
                    "geplant_fuer": ex.get("scheduled_date"),
                    "follow_up_type": ex.get("follow_up_type") or "nachfass",
                },
                "gewuenschtes_neues_datum": scheduled,
                "optionen": {
                    "vorhandenen_erledigen": (
                        "Bestehenden als 'gesendet' markieren und neuen "
                        f"fuer {scheduled} anlegen (Default-Empfehlung, "
                        "wenn der User sich aktiv neu kuemmert)."
                    ),
                    "vorhandenen_verschieben": (
                        f"Bestehenden Nachfass auf {scheduled} "
                        "verschieben statt zweiten anzulegen."
                    ),
                    "trotzdem_neu": (
                        "Beide behalten — nur waehlen wenn bewusst gewollt."
                    ),
                },
                "naechster_aufruf": (
                    "Frage den User. Dann nachfass_planen(bewerbung_id, "
                    f"tage={tage}, wenn_dublette='<wahl>') erneut aufrufen."
                ),
            }

        # Wenn Dublette behandelt werden soll: alte Loeschung/Verschiebung VOR Insert
        dublette_aktion: dict | None = None
        if existing_open and wenn_dublette == "vorhandenen_erledigen":
            ex = existing_open[0]
            try:
                db.complete_follow_up(ex["id"], status="gesendet")
                dublette_aktion = {
                    "alter_follow_up_id": ex["id"],
                    "aktion": "erledigt_markiert",
                    "alter_status": "gesendet",
                }
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Dubletten-Erledigung fehlgeschlagen fuer %s: %s",
                    ex.get("id"), exc,
                )
        elif existing_open and wenn_dublette == "vorhandenen_verschieben":
            ex = existing_open[0]
            try:
                db.update_follow_up(ex["id"], {"scheduled_date": scheduled})
                # KEIN neuer Insert — nur Update. Result direkt zurueckgeben.
                return {
                    "status": "verschoben",
                    "follow_up_id": ex["id"],
                    "bewerbung": app["title"],
                    "firma": app["company"],
                    "alter_termin": ex.get("scheduled_date"),
                    "neuer_termin": scheduled,
                    "typ": typ,
                    "hinweis": (
                        "Bestehender Nachfass wurde auf das neue Datum "
                        "verschoben — kein zweiter Eintrag angelegt."
                    ),
                }
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Dubletten-Verschiebung fehlgeschlagen fuer %s: %s",
                    ex.get("id"), exc,
                )
        # trotzdem_neu fuehrt einfach durch zum normalen Insert unten.

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

        result = {
            "status": "geplant",
            "follow_up_id": fid,
            "bewerbung": app["title"],
            "firma": app["company"],
            "geplant_fuer": scheduled,
            "typ": typ,
            "template": template,
            "hinweis": "Das Template ist ein Vorschlag — passe es gerne an bevor du es versendest.",
        }
        # #665: Dubletten-Handhabung im Result transparent machen
        if dublette_aktion:
            result["dublette_behandelt"] = dublette_aktion
        return result

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
    def stilarchiv_speichern(
        kind: str,
        content: str,
        title: str = "",
        application_id: str = "",
        outcome: str = "",
        notes: str = "",
    ) -> dict:
        """Speichert eine Anschreiben- oder Lebenslauf-Version im Stilarchiv (#577).

        Beim naechsten Generieren werden die letzten Versionen als Kontext
        mitgegeben — Claude bleibt im User-Stil und nutzt erfolgreiche
        Formulierungen wieder.

        Args:
            kind: 'cover_letter', 'cv' oder 'other'.
            content: Der vollstaendige Text der Version.
            title: Optionaler Titel (z.B. Firma+Position).
            application_id: Optionale Bewerbung zum Verlinken.
            outcome: Optional 'interview', 'abgelehnt', 'ohne_antwort' —
                kann spaeter via stilarchiv_outcome_setzen ergaenzt werden.
            notes: Freitext-Anmerkungen.
        """
        if kind not in ("cover_letter", "cv", "other"):
            return {"fehler": "kind muss 'cover_letter', 'cv' oder 'other' sein."}
        if not content or not content.strip():
            return {"fehler": "content darf nicht leer sein."}
        vid = db.add_document_version({
            "kind": kind,
            "title": title,
            "content": content,
            "application_id": application_id or None,
            "outcome": outcome or None,
            "notes": notes,
        })
        return {"status": "gespeichert", "version_id": vid, "kind": kind}

    @mcp.tool()
    def stilarchiv_kontext(kind: str = "cover_letter", limit: int = 5) -> dict:
        """Liefert die letzten N Versionen als Kontext fuer eine Neu-Generierung (#577).

        Nutze das BEVOR du ein neues Anschreiben/Lebenslauf schreibst —
        damit der Stil konsistent bleibt und erfolgreiche Formulierungen
        nicht verloren gehen.

        Args:
            kind: 'cover_letter' oder 'cv'.
            limit: Anzahl der Versionen (Default 5).
        """
        if kind not in ("cover_letter", "cv", "other"):
            return {"fehler": "kind muss 'cover_letter', 'cv' oder 'other' sein."}
        versions = db.get_recent_document_versions(kind, limit=limit)
        if not versions:
            return {
                "kind": kind,
                "anzahl": 0,
                "hinweis": "Noch keine gespeicherten Versionen — beim ersten Mal "
                           "frei schreiben, dann via stilarchiv_speichern() ablegen.",
            }
        # Kontextueller Output: nur relevante Felder, mit Erfolgs-Markierung
        return {
            "kind": kind,
            "anzahl": len(versions),
            "versionen": [
                {
                    "id": v["id"],
                    "title": v.get("title") or "",
                    "word_count": v.get("word_count") or 0,
                    "outcome": v.get("outcome") or "unbekannt",
                    "created_at": v.get("created_at"),
                    "content_excerpt": (v.get("content") or "")[:500],
                }
                for v in versions
            ],
            "hinweis": (
                "Nutze diese Versionen als Stil-Vorlage. Erfolgreiche "
                "(outcome='interview') besonders beachten. KEINEN Inhalt 1:1 "
                "kopieren — Stil und Tonfall uebernehmen, Inhalt neu auf die "
                "konkrete Stelle ausrichten."
            ),
        }

    @mcp.tool()
    def stilarchiv_outcome_setzen(version_id: str, outcome: str) -> dict:
        """Markiert eine Stilarchiv-Version mit Erfolgs-Status (#577).

        Args:
            version_id: ID der Version (aus stilarchiv_speichern bekommen).
            outcome: 'interview' | 'abgelehnt' | 'ohne_antwort' | 'angebot' |
                'zurueckgezogen'.
        """
        valid = {"interview", "abgelehnt", "ohne_antwort", "angebot", "zurueckgezogen"}
        if outcome not in valid:
            return {"fehler": f"outcome muss eines von {sorted(valid)} sein."}
        ok = db.update_document_version_outcome(version_id, outcome)
        return {"status": "gespeichert" if ok else "nicht_gefunden", "version_id": version_id, "outcome": outcome}

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
            "hinweis": "Stil wurde als Event gespeichert. Nutze stil_auswertung() "
                       "um Rücklaufquoten pro Stil zu sehen.",
        }

    @mcp.tool()
    def stil_auswertung() -> dict:
        """Wertet getrackte Anschreiben-Stile aus: Welcher Stil oeffnet mehr Tueren (Interviews)? (#454, #736)

        Liest alle stil_tracking-Events aus application_events. Die
        Interview-Quote misst, welcher Anteil der Bewerbungen eines Stils
        MINDESTENS EIN Interview erreicht hat — bestimmt ueber den
        Status-Verlauf (Timeline), nicht ueber den finalen Status (#736).
        Eine Bewerbung mit Verlauf interview -> abgelehnt zaehlt also als
        Interview-Treffer UND als (Nach-Interview-)Absage. Begruendung: das
        Anschreiben beeinflusst die Einladung, nicht was im Gespraech folgt.

        Pro Stil: Anzahl, Interview-Quote, Angebots-Quote, Absage-Quote
        (zusaetzlich aufgeschluesselt in absage_nach_interview /
        absage_ohne_interview). Mindestens 3 Bewerbungen pro Stil noetig
        damit eine Quote ausgegeben wird (sonst zu rauschig).
        """
        conn = db.connect()
        rows = conn.execute("""
            SELECT e.notes, e.application_id, a.status, a.has_reached_interview
            FROM application_events e
            JOIN applications a ON a.id = e.application_id
            WHERE e.status = 'stil_tracking'
            ORDER BY e.event_date ASC
        """).fetchall()

        if not rows:
            return {
                "status": "keine_daten",
                "hinweis": "Noch keine Stil-Trackings vorhanden. Nutze bewerbung_stil_tracken() "
                           "nach jedem Anschreiben.",
                "stile": {},
            }

        # Letzten Stil pro Bewerbung gewinnen lassen (falls mehrfach getrackt)
        latest_per_app = {}
        for r in rows:
            notes = r["notes"] or ""
            m = re.match(r"Anschreiben-Stil:\s*(\w+)", notes)
            if not m:
                continue
            latest_per_app[r["application_id"]] = (
                m.group(1).lower(), r["status"], r["has_reached_interview"]
            )

        if not latest_per_app:
            return {
                "status": "keine_daten",
                "hinweis": "Stil-Events vorhanden, aber Format nicht parsebar.",
                "stile": {},
            }

        # #736: Interview-Stati inkl. interview_abgeschlossen — und die
        # Interview-Erreichung wird ueber den STATUS-VERLAUF
        # (application_events) bestimmt, nicht ueber den finalen Status.
        # Sonst zaehlt eine Bewerbung mit Verlauf interview -> abgelehnt
        # faelschlich als 0 Interviews. Das Anschreiben entscheidet, ob eine
        # Tuer aufgeht (Interview) — nicht was danach im Gespraech passiert.
        INTERVIEW_STATES = {"interview", "zweitgespraech", "interview_abgeschlossen"}
        OFFER_STATES = {"angebot", "angenommen"}
        REJECT_STATES = {"abgelehnt", "abgesagt"}

        # Status-Historie pro Bewerbung aus der Timeline holen (#736).
        app_ids = list(latest_per_app.keys())
        hist: dict[str, set] = {aid: set() for aid in app_ids}
        if app_ids:
            placeholders = ",".join("?" * len(app_ids))
            for er in conn.execute(
                f"SELECT application_id, status FROM application_events "
                f"WHERE application_id IN ({placeholders})",
                app_ids,
            ).fetchall():
                hist.setdefault(er["application_id"], set()).add(
                    (er["status"] or "").lower()
                )

        per_stil: dict[str, dict] = {}
        for app_id, (stil, app_status, has_reached) in latest_per_app.items():
            bucket = per_stil.setdefault(stil, {
                "anzahl": 0,
                "interviews": 0,
                "angebote": 0,
                "absagen": 0,
                "absage_nach_interview": 0,
                "absage_ohne_interview": 0,
                "in_prozess": 0,
            })
            bucket["anzahl"] += 1

            verlauf = hist.get(app_id, set())
            # Interview erreicht, wenn das kanonische Flag gesetzt ist (#530,
            # wird bei jedem Status-Wechsel gepflegt und historisch
            # backfilled) ODER irgendwann ein Interview-Event auftauchte ODER
            # der aktuelle Status Interview/Angebot ist (Angebot setzt ein
            # vorausgegangenes Gespraech voraus).
            reached_interview = bool(
                has_reached
                or (verlauf & INTERVIEW_STATES)
                or (verlauf & OFFER_STATES)
                or app_status in INTERVIEW_STATES
                or app_status in OFFER_STATES
            )
            if reached_interview:
                bucket["interviews"] += 1
            if app_status in OFFER_STATES:
                bucket["angebote"] += 1
            if app_status in REJECT_STATES:
                bucket["absagen"] += 1
                if reached_interview:
                    bucket["absage_nach_interview"] += 1
                else:
                    bucket["absage_ohne_interview"] += 1
            elif app_status not in OFFER_STATES:
                bucket["in_prozess"] += 1

        MIN_SAMPLES = 3
        for stil, bucket in per_stil.items():
            n = bucket["anzahl"]
            if n >= MIN_SAMPLES:
                bucket["interview_quote"] = round(bucket["interviews"] / n * 100, 1)
                bucket["angebots_quote"] = round(bucket["angebote"] / n * 100, 1)
                bucket["absage_quote"] = round(bucket["absagen"] / n * 100, 1)
            else:
                bucket["hinweis"] = f"Nur {n} Bewerbungen — fuer Quoten mindestens {MIN_SAMPLES} noetig."

        sortiert = sorted(
            per_stil.items(),
            key=lambda kv: kv[1].get("interview_quote", -1),
            reverse=True,
        )

        return {
            "status": "ok",
            "gesamt_getrackt": sum(b["anzahl"] for b in per_stil.values()),
            "stile": {k: v for k, v in sortiert},
            "min_samples_fuer_quoten": MIN_SAMPLES,
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
            # #705: Integritaets-Check gegen Profil-Datenverlust. Ein
            # GEPFLEGTES Profil (Positionen + Skills vorhanden) sollte auch
            # Kontaktdaten und informelle Notizen haben — sind die ploetzlich
            # leer, deutet das auf einen Datenverlust hin (z.B. den erst in
            # beta.101 gefixten profil_erstellen-Ueberschreib-Bug).
            if positions and len(skills) >= 3:
                leere_kontaktfelder = [
                    feld for feld in ("email", "phone", "address", "summary")
                    if not (profile.get(feld) or "").strip()
                ]
                notizen_leer = not (profile.get("informal_notes") or "").strip()
                if len(leere_kontaktfelder) >= 3 or (leere_kontaktfelder and notizen_leer):
                    warnungen.append({
                        "bereich": "Profil-Integritaet",
                        "problem": (
                            "Das Profil ist gepflegt (Positionen + Skills vorhanden), aber "
                            f"{'Kontaktfelder (' + ', '.join(leere_kontaktfelder) + ')' if leere_kontaktfelder else ''}"
                            f"{' und ' if leere_kontaktfelder and notizen_leer else ''}"
                            f"{'die informellen Notizen' if notizen_leer else ''} sind leer — "
                            "moeglicher Datenverlust (#705)."
                        ),
                        "loesung": (
                            "Pruefe data/backups/ — vor jeder Migration wird ein Backup "
                            "angelegt. Wiederherstellung einzelner Felder: Backup-DB oeffnen "
                            "und Werte via profil_bearbeiten() zuruecktragen. "
                            "Seit beta.101 ueberschreibt profil_erstellen() keine "
                            "Bestandsfelder mehr."
                        ),
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

                # v1.7.10 (#779/D27): applied_at leer bei Status, der eine
                # Bewerbung voraussetzt -> faellt aus der Statistik-
                # Segmentierung. auto_fix traegt aus dem aeltesten Timeline-
                # Event nach (Fallback created_at). Idempotent: einmal
                # gefuellt, taucht die Bewerbung hier nie wieder auf.
                _braucht_datum = {
                    "beworben", "eingangsbestaetigung", "interview",
                    "zweitgespraech", "interview_abgeschlossen", "angebot",
                    "angenommen", "abgelehnt", "arbeitgeber_ausgefallen",
                }
                ohne_applied = [
                    a for a in apps
                    if a.get("status") in _braucht_datum
                    and not (a.get("applied_at") or "").strip()
                ]
                if ohne_applied:
                    eintrag = {
                        "bereich": "Bewerbungen",
                        "problem": (
                            f"{len(ohne_applied)} Bewerbung(en) ohne applied_at "
                            "trotz fortgeschrittenem Status — unsichtbar in der "
                            "Statistik-Segmentierung (#779)"
                        ),
                        "bewerbungen": [
                            {"id": a["id"][:8], "firma": a.get("company", ""),
                             "status": a.get("status", "")}
                            for a in ohne_applied[:10]
                        ],
                        "loesung": "pbp_diagnose(auto_fix=True) oder "
                                   "bewerbung_bearbeiten(applied_at=...)",
                    }
                    if auto_fix:
                        fixed_dates = 0
                        conn_af = db.connect()
                        for a in ohne_applied:
                            row = conn_af.execute(
                                "SELECT MIN(event_date) AS erster "
                                "FROM application_events WHERE application_id=?",
                                (a["id"],),
                            ).fetchone()
                            datum = (row["erster"] or "") if row else ""
                            if not datum:
                                datum = a.get("created_at") or ""
                            if datum:
                                db.update_application(
                                    a["id"], {"applied_at": datum[:10]})
                                fixed_dates += 1
                        if fixed_dates:
                            fixes.append(
                                f"{fixed_dates} Bewerbungen: applied_at aus "
                                "aeltestem Timeline-Event nachgetragen (#779)")
                    else:
                        warnungen.append(eintrag)

                # v1.7.10 (#781/D29, Punkt 6): Gespraeche, die nur im
                # Notizfeld dokumentiert sind, aber weder als Event noch als
                # Meeting existieren — die Statistik zaehlt dort 0 Interviews.
                # NUR eine pruefbare Liste, KEIN automatisches Anlegen
                # (der Mensch muss bestaetigen, dass es echte Termine waren).
                try:
                    from ..services.statistik_erweitert import (
                        notizen_gespraeche_check)
                    nur_notiz = notizen_gespraeche_check(db)
                    if nur_notiz:
                        warnungen.append({
                            "bereich": "Bewerbungen",
                            "problem": (
                                f"{len(nur_notiz)} Bewerbung(en) mit "
                                "Gespraechs-Hinweisen im Notizfeld, aber ohne "
                                "Interview-Event/Meeting — Interviews fehlen "
                                "in der Statistik (#781)"
                            ),
                            "bewerbungen": nur_notiz[:10],
                            "loesung": (
                                "Je Fall pruefen und manuell nachtragen: "
                                "bewerbung_event_datum_setzen / "
                                "meeting_hinzufuegen. Bewusst KEIN auto_fix."
                            ),
                        })
                except Exception as _e:
                    logger.debug("Notiz-Gespraeche-Check: %s", _e)

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

        # v1.6.9 (#574): Hash-Format-Konsistenz-Check.
        # Nach Migration v31 sollten alle Eintraege mit profile_id im
        # Format '{pid}:hash' vorliegen. Mischformen sind ein Hinweis auf
        # eine fehlgeschlagene oder unvollstaendige Migration.
        try:
            conn = db.connect()
            mixed = conn.execute(
                "SELECT COUNT(*) AS n FROM jobs "
                "WHERE hash NOT LIKE '%:%' AND profile_id IS NOT NULL AND profile_id != ''"
            ).fetchone()
            mixed_count = mixed["n"] if mixed else 0
            if mixed_count > 0:
                warnungen.append({
                    "bereich": "Datenbank",
                    "problem": f"{mixed_count} Stellen haben altes Hash-Format (ohne profile_id-Praefix)",
                    "loesung": "Diese Eintraege werden bei Bedarf von _job_hash_candidates() trotzdem gefunden, "
                               "aber stellen_anzeigen() koennte sie unterschlagen. Schema-Migration v31 erneut "
                               "ausfuehren oder Issue auf GitHub melden.",
                })
        except Exception:
            pass

        # Bugreport-Hinweis bei kritischen Problemen
        if probleme:
            result["bugreport_hinweis"] = (
                "Falls du ein technisches Problem vermutest, erstelle einen Bugreport: "
                "Kopiere diese Diagnose-Ausgabe und sende sie an den Entwickler."
            )

        return result

    def _keyword_vorschlaege_aus_profil(muss, plus, ausschluss) -> dict:
        """G17/F24 (#744/#745): Keyword-Vorschlaege fuer frische Profile
        ohne Stellen-Bestand. Lokale KI bevorzugt (EXTRACT_KEYWORDS),
        sonst Heuristik aus Jobtiteln + fachlichen Skills.
        Kein MCP-Tool — interner Helper von keyword_vorschlaege."""
        profile = db.get_profile()
        if not profile:
            return {
                "nachricht": "Kein Profil vorhanden. "
                             "Starte mit dem Prompt ersterfassung_starten.",
            }

        vorhandene = muss + plus + ausschluss
        bereits = {str(v).lower() for v in vorhandene}
        quelle = "heuristik_profil"
        vorschlag_muss: list = []
        vorschlag_plus: list = []

        # F24 (#745): lokale KI bevorzugt — Feature-Gate + Verfuegbarkeit
        try:
            if db.is_ki_feature_enabled("stellenanalyse"):
                from ..services.llm_service import (
                    Backend, TaskKind, build_profil_kurztext, get_llm_service,
                )
                service = get_llm_service(db)
                if service.select_backend(TaskKind.EXTRACT_KEYWORDS) == Backend.LOCAL:
                    result = service.run(TaskKind.EXTRACT_KEYWORDS, {
                        "profil_text": build_profil_kurztext(profile),
                        "vorhandene_keywords": vorhandene,
                    })
                    if result.success and isinstance(result.payload, dict):
                        vorschlag_muss = result.payload.get("keywords_muss") or []
                        vorschlag_plus = result.payload.get("keywords_plus") or []
                        if vorschlag_muss or vorschlag_plus:
                            quelle = "lokale_ki"
        except Exception as exc:
            logger.debug("EXTRACT_KEYWORDS lokal fehlgeschlagen: %s", exc)

        if not vorschlag_muss and not vorschlag_plus:
            # Heuristik: gespeicherte Jobtitel als MUSS-Kandidaten,
            # fachliche Skills/Tools/Methoden nach Level als PLUS
            try:
                pid = db.get_active_profile_id()
                vorschlag_muss = [
                    t["title"] for t in db.get_suggested_job_titles(pid)
                    if t.get("is_active", 1)
                ][:4]
            except Exception:
                vorschlag_muss = []
            skills = sorted(
                profile.get("skills", []),
                key=lambda s: -(s.get("level") or 0),
            )
            vorschlag_plus = [
                s["name"] for s in skills
                if s.get("name")
                and s.get("category") in ("fachlich", "tool", "methodisch")
            ][:8]

        # Bereits gesetzte Keywords nicht nochmal vorschlagen
        vorschlag_muss = [k for k in vorschlag_muss if str(k).lower() not in bereits]
        vorschlag_plus = [
            k for k in vorschlag_plus
            if str(k).lower() not in bereits
            and str(k).lower() not in {str(m).lower() for m in vorschlag_muss}
        ]

        return {
            "aktive_stellen": 0,
            "datenquelle": (
                "Profil via lokale KI" if quelle == "lokale_ki"
                else "Profil (Heuristik: Jobtitel + Skills)"
            ),
            "quelle": quelle,
            "aktuelle_keywords": {"muss": muss, "plus": plus, "ausschluss": ausschluss},
            "profil_vorschlaege": {
                "muss": vorschlag_muss,
                "plus": vorschlag_plus,
            },
            "hinweis": (
                "Noch keine Stellen im Bestand — diese Vorschlaege stammen aus "
                "deinem Profil. Zeige sie dem User zur Bestaetigung, uebernimm "
                "sie mit suchkriterien_setzen(keywords_muss=[...], "
                "keywords_plus=[...]) und starte dann die erste Suche mit "
                "jobsuche_starten()."
            ),
        }

    @mcp.tool()
    def keyword_vorschlaege() -> dict:
        """Analysiert Bewerbungen vs. abgelehnte Stellen und schlägt
        Keyword-Anpassungen vor (#184 / #500 v1.6.0-beta.29).

        v1.7.4 (#744/#745): Ohne Stellen-Bestand (frisches Profil) kommen
        die Vorschläge aus dem Profil — lokale KI bevorzugt, sonst
        Jobtitel-/Skill-Heuristik. Antwortfeld `profil_vorschlaege`.

        Datenquelle (in dieser Reihenfolge):
            1. Beste Quelle: Stellen mit Bewerbung vs. dismissed Stellen.
               Was unterscheidet die Stellen, die du ANGEFASST hast,
               von denen, die du ABGELEHNT hast?
            2. Fallback: gut/schlecht bewertete aktive Stellen
               (alter Score-basierter Mechanismus, falls noch zu wenig
               Bewerbungen/Ablehnungen vorhanden).

        TF-IDF-aehnliche Spezifitaets-Heuristik: Begriffe die in zu
        vielen Quellen vorkommen werden abgewertet (Stoppwoerter sind
        nicht alle Stoppwoerter, manche sind nur "in jeder
        Stellenbeschreibung haeufig"). Ohne tiefere LLM-Analyse, aber
        deutlich brauchbarer als die alte Implementierung — siehe
        v1.7.0 Local-LLM-Roadmap fuer den naechsten Schritt.
        """
        criteria = db.get_search_criteria()
        muss = [kw.lower() for kw in criteria.get("keywords_muss", [])]
        plus = [kw.lower() for kw in criteria.get("keywords_plus", [])]
        ausschluss = [kw.lower() for kw in criteria.get("keywords_ausschluss", [])]
        alle_keywords = set(muss + plus)

        # Erweiterte Stoppwoerter: typische DACH-Stellenbeschreibungs-Floskeln,
        # die fast in jeder Anzeige vorkommen und keine Aussagekraft haben.
        _stopwords = {
            # Funktionswoerter
            "und", "oder", "der", "die", "das", "den", "dem", "des", "ein", "eine", "einer", "einem", "einen",
            "ist", "sind", "war", "waren", "hat", "habe", "haben", "wird", "werden", "wurde", "wurden",
            "mit", "ohne", "von", "vor", "nach", "fuer", "für", "als", "bei", "zur", "zum", "zu",
            "auf", "aus", "nach", "ueber", "über", "unter", "durch", "an", "am", "im", "in", "ins",
            "nicht", "auch", "sich", "wir", "sie", "uns", "ihr", "ihre", "ihren", "ihrer",
            "unser", "unsere", "unseren", "unserer", "unserem", "unseres",
            "deine", "dein", "dich", "dir", "du", "ihrer", "diese", "dieser", "diesem",
            # Typische Stellenanzeigen-Floskeln
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
            "sowie", "sowohl", "sowie", "ebenso", "auch",
            "erstellung", "erstellen", "umsetzung", "umsetzen", "durchfuehrung",
            "verantwortung", "verantwortlich",
            "qualifikation", "qualifikationen", "ausbildung",
            "stunden", "tage", "tag", "wochen", "woche",
            "montag", "dienstag", "mittwoch", "donnerstag", "freitag",
            "monat", "monaten", "jahr", "jahre", "jahren",
            "m/w/d", "m/w", "w/m/d", "w/m", "d/m/w",
            # Generic Verbs
            "macht", "machen", "tun", "tuen", "geht", "gehen", "kommt", "kommen",
            "gibt", "geben", "nehmen", "nimmt", "wird", "werden",
            "kann", "koennen", "muss", "muessen", "soll", "sollen", "will", "wollen",
        }

        def _extract_terms(text):
            # Min 5 Zeichen — eliminiert "team", "ihre", "team" etc.
            words = re.findall(r'[a-zA-ZäöüÄÖÜß]{5,}', text.lower())
            return [w for w in words if w not in _stopwords]

        # Versuch 1: Bewerbungen vs. abgelehnte Stellen (User-Wunsch)
        applications = db.get_applications()
        applied_hashes = {
            a["job_hash"] for a in applications
            if a.get("job_hash") and a.get("status") not in (
                "abgelehnt", "zurueckgezogen", "abgelaufen", "passt_nicht"
            )
        }
        dismissed_jobs = db.get_dismissed_jobs() if hasattr(db, "get_dismissed_jobs") else []

        all_jobs = db.get_active_jobs(exclude_blacklisted=True)
        applied_job_objs = [j for j in all_jobs if j.get("hash") in applied_hashes]
        # Falls bereits-beworben Stellen aussortiert sind, in dismissed_jobs schauen
        if not applied_job_objs and applied_hashes and dismissed_jobs:
            applied_job_objs = [j for j in dismissed_jobs if j.get("hash") in applied_hashes]

        # Datenquellen-Wahl: applied vs dismissed bevorzugt, sonst Score-Fallback
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
            # Fallback: alte Score-basierte Logik (zirkulaer, aber besser als gar nichts)
            good_jobs = [j for j in all_jobs if j.get("score", 0) >= 3]
            bad_jobs = [j for j in all_jobs if j.get("score", 0) <= 1]
            datenquelle = (
                f"Score-Vergleich (kein Bewerbungs-Vergleich moeglich, "
                f"Bewerbungen: {len(applied_job_objs)}, "
                f"Aussortiert: {len(dismissed_jobs)})"
            )

        if not all_jobs:
            # G17/F24 (#744/#745, v1.7.4): frueher eine Sackgasse ("starte
            # zuerst eine Jobsuche") — genau der Punkt, an dem ein Einsteiger
            # OHNE Stellen-Bestand Keywords braucht. Jetzt: Vorschlaege aus
            # dem Profil, lokale KI bevorzugt, sonst Skill-/Titel-Heuristik.
            return _keyword_vorschlaege_aus_profil(muss, plus, ausschluss)

        from collections import Counter as _Counter
        good_words = _Counter()
        bad_words = _Counter()
        # Document Frequency — fuer TF-IDF-Spezifitaets-Heuristik
        all_jobs_count = max(1, len(all_jobs))
        doc_freq = _Counter()

        for j in all_jobs:
            text = f"{j.get('title', '')} {(j.get('description') or '')[:1500]}"
            unique_terms = set(_extract_terms(text))
            for term in unique_terms:
                doc_freq[term] += 1
        for j in good_jobs:
            text = f"{j.get('title', '')} {(j.get('description') or '')[:1500]}"
            for term in _extract_terms(text):
                good_words[term] += 1
        for j in bad_jobs:
            text = f"{j.get('title', '')} {(j.get('description') or '')[:1500]}"
            for term in _extract_terms(text):
                bad_words[term] += 1

        # Spezifitaets-Filter: Begriffe die in mehr als 70% aller Stellen
        # vorkommen sind nicht aussagekraeftig, auch wenn sie nicht in
        # den Stoppwoertern sind.
        TOO_GENERIC_THRESHOLD = 0.7
        too_generic = {
            term for term, count in doc_freq.items()
            if count / all_jobs_count > TOO_GENERIC_THRESHOLD
        }

        vorschlaege_plus = []
        vorschlaege_ausschluss = []

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

        # beta.35: Term darf nur Ausschluss sein, wenn er in KEINER
        # User-Bewerbung vorkommt — sonst empfiehlt PBP echte Zielbegriffe
        # zur Ablehnung (User-Beobachtung mit "manager"/"consultant").
        min_bad_freq = max(2, len(bad_jobs) // 4) if bad_jobs else 2
        for term, count in bad_words.most_common(50):
            if term in alle_keywords or term in ausschluss or term in too_generic:
                continue
            if count < min_bad_freq:
                continue
            if good_words.get(term, 0) > 0:
                continue
            vorschlaege_ausschluss.append({
                "keyword": term,
                "in_schlechten_stellen": count,
                "in_guten_stellen": 0,
            })

        # Keywords die in keiner Stelle vorkommen (tote Keywords)
        from ..job_scraper import _fuzzy_keyword_match
        tote_keywords = []
        all_text = " ".join(
            f"{j.get('title', '')} {(j.get('description') or '')[:500]}"
            for j in all_jobs
        ).lower()
        for kw in muss + plus:
            if not _fuzzy_keyword_match(kw, all_text):
                tote_keywords.append(kw)

        return {
            "aktive_stellen": len(all_jobs),
            "gut_bewertet": len(good_jobs),
            "schlecht_bewertet": len(bad_jobs),
            "datenquelle": datenquelle,  # neu: erklaert die Vorschlags-Basis
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
        if not (text or "").strip():
            return {"fehler": "Kein Text angegeben."}

        # Ziele validieren
        ziel_bewerbung = None
        ziel_job = None
        if bewerbung_id:
            app = db.get_application(bewerbung_id)
            if not app:
                return {"fehler": f"Bewerbung {bewerbung_id} nicht gefunden."}
            ziel_bewerbung = bewerbung_id
            # Ohne expliziten job_hash: verknuepfte Stelle mitbinden, damit die
            # Recherche auch im Stellen-Detail auftaucht (n:m, #472).
            if not job_hash and app.get("job_hash"):
                ziel_job = app.get("job_hash")
        if job_hash:
            if not db.get_job(job_hash):
                return {"fehler": f"Stelle {job_hash} nicht gefunden."}
            ziel_job = job_hash

        # #674: strukturierter Eintrag in die research_notes-Tabelle (NICHT in
        # applications.fit_analyse und NICHT in den manuellen Notizblock
        # jobs.research_notes). Macht #673 (Anzeige) zu einer einfachen Query.
        note_id = db.add_research_note(
            kategorie=kategorie, text=text,
            bewerbung_id=ziel_bewerbung, job_hash=ziel_job,
        )

        saved_to = []
        if ziel_bewerbung:
            saved_to.append(f"Bewerbung {ziel_bewerbung}")
        if ziel_job:
            saved_to.append(f"Stelle {str(ziel_job)[:8]}")

        return {
            "status": "gespeichert",
            "id": note_id,
            "gespeichert_in": saved_to,
            "zielfeld": "research_notes-Tabelle (Bewerbungs-Detail, Abschnitt 'Recherchen')",
            "kategorie": (kategorie or "allgemein").strip().lower(),
            "laenge": len(text),
            "hinweis": "Recherche strukturiert gespeichert und im Detail-Dialog unter "
                       "'Recherchen' sichtbar. Auslesen via bewerbung_details.",
        }

    # ========================================================================
    # v1.6.3 / #514 — Capability-Awareness + Limitation-Reporting
    # ========================================================================

    @mcp.tool()
    def pbp_capabilities(kategorie: str = "") -> dict:
        """Liefert eine kuratierte Uebersicht aller PBP-MCP-Faehigkeiten (#514).

        ZWECK: Wenn du als KI unklar bist was PBP fuer eine User-Anfrage anbieten
        kann — RUFE DIESES TOOL AUF, bevor du auf andere Tools (Filesystem,
        sqlite-MCP, Direct-DB-Write) ausweichst. Direkte Eingriffe in die
        SQLite-Datei umgehen die PBP-Lifecycle-Logik und korrumpieren die
        Datenkonsistenz.

        Args:
            kategorie: Optional. Eine der folgenden Kategorien fuer Detail-View:
                'profil', 'jobsuche', 'bewerbungen', 'dokumente', 'kalender',
                'analyse', 'export', 'workflows', 'einstellungen', 'system'.
                Leer = Uebersicht aller Kategorien.
        """
        catalog = {
            "profil": {
                "use_case": "Profil aufbauen, bearbeiten, exportieren. Skills, Berufserfahrung, Ausbildung, Praeferenzen.",
                "hauptwerkzeuge": [
                    "ersterfassung_starten — Gefuehrtes Profil-Interview",
                    "dokument_profil_extrahieren — CV-Upload -> Profilfelder",
                    "profil_bearbeiten / position_hinzufuegen / skill_hinzufuegen / ausbildung_hinzufuegen",
                    "profile_auflisten / profil_wechseln / neues_profil_erstellen — Multi-Profil",
                    "profil_exportieren / profil_importieren — Backup & Migration",
                    # #696-B: war faelschlich unter 'bewerbungen' als Interview-Nachgang gelistet
                    "kennlerngespraech_abschliessen — Profil-Onboarding-Gespraech als abgeschlossen markieren (Dashboard-Wizard geht weiter)",
                ],
            },
            "jobsuche": {
                "use_case": "Stellen suchen, bewerten, sortieren. Suchkriterien, Quellen-Diagnose, Scoring.",
                "hauptwerkzeuge": [
                    "jobsuche_starten — Hintergrund-Suche auf konfigurierten Quellen",
                    "jobsuche_status — Fortschritt einer laufenden Suche",
                    "stellen_anzeigen — Liste mit Filter (Score, Quelle, Alter)",
                    "stelle_bewerten — EINZELNE Stelle aussortieren oder als-passend",
                    "stellen_bulk_bewerten — VIELE Stellen mit Filter aussortieren (#514). IMMER bevorzugen wenn mehr als ~10 Stellen betroffen. dry_run=True Default.",
                    "stelle_bearbeiten / stelle_manuell_anlegen / stelle_mergen",
                    "stelle_reaktivieren — aussortierte Stelle wieder aktivieren",
                    "stelle_wiedergaenger_pruefen — wiederkehrende Stellen erkennen (KI-frei)",
                    "fit_analyse — Profil-vs-Stelle Punkt-fuer-Punkt-Vergleich",
                    "scoring_konfigurieren / scoring_vorschau — Gewichtungs-Regler",
                    "suchkriterien_setzen / _bearbeiten / _anzeigen — inkl. keywords_minus (weiche Abwertung)",
                    "blacklist_verwalten — Firmen/Keywords ausschliessen",
                    "scraper_diagnose — Welche Quellen liefern aktuell?",
                ],
            },
            "bewerbungen": {
                "use_case": "Bewerbungen anlegen, tracken, Status, Notizen, Follow-ups, Anschreiben, Dossier.",
                "hauptwerkzeuge": [
                    "bewerbung_erstellen / _bearbeiten / _loeschen / _details",
                    "bewerbung_status_aendern — Lifecycle (offen -> eingeladen -> ...)",
                    "bewerbungen_anzeigen — Liste mit Filtern",
                    "bewerbung_notiz — Notizen je Bewerbung",
                    "anschreiben_exportieren / lebenslauf_angepasst_exportieren — Tailored Export",
                    "antwort_formulieren — E-Mail-Antwort generieren",
                    "nachfass_planen / nachfass_anzeigen — Follow-up-Tracking",
                    "follow_up_erledigen / _hinfaellig / _verschieben",
                    "interview_reflexion_speichern — Interview-Nachgang: eigene Notizen pro Interview-Termin",
                    "todo_anlegen / todos_anzeigen / todo_erledigen — Aufgaben pro Bewerbung mit Faelligkeitsdatum",
                    "bewerbungsbericht_exportieren — PDF-Bericht",
                    "ablehnungs_muster — Was wird oft abgelehnt?",
                ],
            },
            "dokumente": {
                "use_case": "Dokumente hochladen, analysieren, mit Bewerbungen verknuepfen.",
                "hauptwerkzeuge": [
                    "dokumente_zur_analyse — Liste der noch nicht analysierten Dokumente",
                    "dokumente_batch_analysieren — Mehrere Dokumente analysieren",
                    "bewerbungs_dokumente_erkennen — Auto-Klassifikation",
                    "dokumente_bulk_markieren — Status-Bulk-Update",
                    "dokument_verknuepfen / dokument_entverknuepfen — Bewerbungs-Zuordnung",
                    "dokument_archivieren / dokument_reaktivieren / dokumente_routing_plan_erstellen — Dokument-Lifecycle (aktiv/archiviert/veraltet) + Routing",
                    "dokument_status_setzen / dokument_loeschen",
                    "dokument_profil_extrahieren — CV -> Profil-Daten",
                ],
            },
            "kalender": {
                "use_case": "Termine, Meetings, ICS-Export.",
                "hauptwerkzeuge": [
                    "meeting_hinzufuegen / _bearbeiten / _loeschen / meetings_anzeigen",
                ],
            },
            "analyse": {
                "use_case": "Stellen-, Markt-, Skill-, Stil-Auswertungen. Recherche speichern.",
                "hauptwerkzeuge": [
                    "fit_analyse — Profil vs Stelle",
                    "skill_gap_analyse — Welche Skills fehlen fuer Wunschstellen?",
                    "lebenslauf_bewerten — 3-Perspektiven-Analyse (Recruiter/ATS/Berater)",
                    "gehalt_marktanalyse / branchen_trends — Marktdaten",
                    "firmen_recherche — Hintergrund zu einer Firma",
                    "keyword_vorschlaege — Welche Keywords aus erfolgreichen Bewerbungen?",
                    "stil_auswertung — Schreibstil-Profil",
                    "analyse_plan_erstellen — Welche Analysen sind sinnvoll?",
                    "recherche_speichern — Permanente Notiz fuer Profil/Stelle/Bewerbung",
                ],
            },
            "export": {
                "use_case": "CV, Anschreiben, Bericht, Backup, ZIP-Export.",
                "hauptwerkzeuge": [
                    "lebenslauf_exportieren / lebenslauf_angepasst_exportieren — PDF/DOCX",
                    "anschreiben_exportieren — PDF/DOCX",
                    "bewerbungsbericht_exportieren — PDF-Pipeline-Report",
                    "profil_report_exportieren — Profil-Snapshot",
                    "profil_exportieren — Vollstaendiges Profil als JSON-Backup",
                ],
            },
            "workflows": {
                "use_case": "Mehrstufige Gespraechsfuehrung mit dem User.",
                "hauptwerkzeuge": [
                    "workflow_starten — Generischer Workflow-Einstieg",
                    "ersterfassung_starten — Profil-Onboarding",
                    "jobsuche_workflow_starten — Geleitete Suchkriterien-Ergaenzung",
                ],
            },
            "einstellungen": {
                "use_case": "Job-Quellen, Scoring-Gewichtung, Such-Radius, Mindest-Score, Blacklist, Jobtitel.",
                "hauptwerkzeuge": [
                    "scoring_konfigurieren / scoring_vorschau",
                    "blacklist_verwalten",
                    "jobtitel_vorschlagen / jobtitel_verwalten",
                    "ablehnungsgruende_anzeigen / ablehnungsgrund_anlegen — eigene Ablehnungsgruende verwalten",
                ],
            },
            "system": {
                "use_case": "Diagnose, Capability-Discovery, Limitation-Reporting.",
                "hauptwerkzeuge": [
                    "pbp_diagnose — System-Health-Check",
                    "pbp_capabilities — Diese Tool-Uebersicht (#514)",
                    "pbp_grenze_melden — Wenn PBP fuer eine Aufgabe nichts hat (#514). ANSTATT auf andere Tools auszuweichen.",
                    "scraper_diagnose — Job-Quellen-Status",
                    "onboarding_hints_anzeigen — Tipps zu ungenutzten Features",
                ],
            },
        }

        # v1.7.0-beta.66 (#632 Stufe 1): statische Aufwand-Klassen pro Tool.
        # Hilft der KI VOR dem Aufruf einzuschaetzen ob eine Operation
        # Token kostet (Claude) oder gratis ist (lokal/DB), und bei
        # Bulk-Operationen vorzuwarnen.
        aufwand_klassen = {
            "gratis_db": {
                "beschreibung": "Reine DB-/Scraper-Operationen, KEINE LLM-Tokens.",
                "beispiele": [
                    "jobsuche_starten", "stellen_anzeigen", "bewerbung_*",
                    "stelle_bewerten", "meeting_*", "kosten_*", "profil_bearbeiten",
                    "suchkriterien_*", "blacklist_verwalten", "statistiken_abrufen",
                ],
            },
            "lokal_guenstig": {
                "beschreibung": "Lokale AI (Ollama) — kostenlos, aber RAM/Zeit. "
                                "Erster Aufruf nach Pause ~50s Cold-Load (#638).",
                "beispiele": [
                    "stellen_auto_aussortieren (~1 Call je Stelle)",
                    "dokument_profil_extrahieren (lokal wenn Ollama aktiv)",
                    "dokumente_batch_analysieren",
                ],
            },
            "claude_mittel": {
                "beschreibung": "Claude-Tokens, einzelne Operation. ~2-10k Tokens.",
                "beispiele": [
                    "fit_analyse", "skill_gap_analyse", "anschreiben_exportieren",
                    "lebenslauf_angepasst_exportieren", "firmen_recherche",
                    "antwort_formulieren",
                ],
            },
            "claude_teuer_bulk": {
                "beschreibung": "Claude-Tokens in Menge. Bei vielen Items schnell "
                                "25k+ Tokens. VOR Start dem User Volumen nennen.",
                "beispiele": [
                    "stellen_bulk_bewerten (skaliert mit Anzahl Stellen)",
                    "dokumente_batch_analysieren via Claude (statt lokal)",
                    "bewerbungsbericht_exportieren (grosse Profile)",
                ],
            },
        }

        # #647 (H12): Tool-Count-Sync — getrennt zwischen gesamt (echte Tool-
        # Anzahl im MCP-Registry) und kuratiert (Hauptwerkzeuge in diesem
        # Catalog). Vorher war "95 Tools" hardcoded und widersprach dem
        # tatsaechlichen Inventar (beta.90: 171 Tools).
        tools_kuratiert = sum(
            len(data["hauptwerkzeuge"]) for data in catalog.values()
        )
        # Echte Tool-Anzahl aus der MCP-Registrierung herausziehen. Bei
        # Ausfall (FastMCP API-Wechsel) defensiv weglassen statt zu crashen.
        tools_gesamt: int | None = None
        try:
            registered = getattr(mcp, "_tool_manager", None)
            if registered is not None and hasattr(registered, "_tools"):
                tools_gesamt = len(registered._tools)
            else:
                # Fallback: FastMCP 2.x list_tools (sync wrapper)
                fn = getattr(mcp, "list_tools_sync", None)
                if callable(fn):
                    tools_gesamt = len(fn())
        except Exception:
            tools_gesamt = None

        if not kategorie:
            count_text = (
                f"PBP-MCP bietet {tools_gesamt or '~171'} Tools "
                f"(davon {tools_kuratiert} kuratierte in 10 Kategorien)."
            ) if tools_gesamt and tools_gesamt != tools_kuratiert else (
                f"PBP-MCP bietet {tools_kuratiert} Tools in 10 Kategorien."
            )
            return {
                "ueberblick": (
                    f"{count_text} Ruf dieses Tool mit "
                    "kategorie='profil', 'jobsuche', 'bewerbungen', 'dokumente', "
                    "'kalender', 'analyse', 'export', 'workflows', 'einstellungen' "
                    "oder 'system' fuer Detail-View auf."
                ),
                # #647: getrennte Counts fuer Discoverability
                "tools_gesamt": tools_gesamt,
                "tools_kuratiert": tools_kuratiert,
                "tools_hinweis": (
                    f"{tools_kuratiert} kuratierte Haupt-Tools sind in den "
                    f"Kategorien gelistet. Die restlichen "
                    f"{(tools_gesamt or 0) - tools_kuratiert} Tools sind interne "
                    "Helper (Stilarchiv, Erfassung, Bridges, ...) — Vollliste "
                    "im Wiki unter MCP-Tools."
                ) if tools_gesamt and tools_gesamt > tools_kuratiert else None,
                "anti_bypass_hinweis": (
                    "WICHTIG: Wenn ein User ueber Bewerbungs-Daten redet, nutze IMMER "
                    "PBP-Tools — niemals direkte Eingriffe in die SQLite-Datei oder "
                    "Filesystem-Tools. Bei fehlender Tool-Abdeckung: pbp_grenze_melden."
                ),
                # #632: Token-/Kosten-Transparenz
                "aufwand_klassen": aufwand_klassen,
                "aufwand_hinweis": (
                    "Vor Bulk-Operationen der Klasse 'claude_teuer_bulk' dem User "
                    "kurz das geschaetzte Token-Volumen nennen. Lokale AI "
                    "(Ollama) ist immer kostenlos — wenn der User Tokens sparen "
                    "will, lokale Tasks bevorzugen (Settings -> KI-Steuerung)."
                ),
                "kategorien": {
                    name: {"use_case": data["use_case"], "tool_count": len(data["hauptwerkzeuge"])}
                    for name, data in catalog.items()
                },
            }

        kat_lower = kategorie.lower().strip()
        if kat_lower not in catalog:
            return {
                "fehler": f"Unbekannte Kategorie '{kategorie}'.",
                "verfuegbare_kategorien": sorted(catalog.keys()),
            }

        return {
            "kategorie": kat_lower,
            "use_case": catalog[kat_lower]["use_case"],
            "tools": catalog[kat_lower]["hauptwerkzeuge"],
        }

    @mcp.tool()
    def pbp_grenze_melden(
        was_versucht: str,
        warum_pbp_nicht_passt: str,
        vorschlag: str = "",
    ) -> dict:
        """Meldet eine PBP-Tool-Grenze, die ein neues Issue rechtfertigt (#514).

        ZWECK: Wenn du als KI eine User-Anfrage hast, fuer die PBP keine
        passenden Tools bietet — STATT auf Filesystem-MCP, sqlite-MCP oder
        direkte DB-Writes auszuweichen, melde die Grenze hier.

        Args:
            was_versucht: Was wollte der User tun? (1-2 Saetze)
            warum_pbp_nicht_passt: Welche PBP-Tools hast du gepruft und warum
                reichen sie nicht? (1-3 Saetze)
            vorschlag: Optional — wie koennte ein passendes Tool aussehen?
        """
        from datetime import datetime as _dt
        from urllib.parse import quote
        from .. import __version__ as _ver
        from ..database import get_data_dir

        # 1) Loggen
        try:
            log_path = get_data_dir() / "limitations.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(
                    f"[{_dt.now().isoformat()}] v{_ver}\n"
                    f"  Was: {was_versucht}\n"
                    f"  Warum nicht: {warum_pbp_nicht_passt}\n"
                    f"  Vorschlag: {vorschlag or '(keiner)'}\n"
                    f"---\n"
                )
        except Exception as exc:
            logger.warning("limitations.log konnte nicht geschrieben werden: %s", exc)

        # 2) Issue-Body vorbereiten
        issue_title = f"PBP-Grenze gemeldet: {was_versucht[:60]}"
        issue_body = (
            f"## Was wollte der User tun?\n\n{was_versucht}\n\n"
            f"## Warum reichen die bestehenden PBP-Tools nicht?\n\n"
            f"{warum_pbp_nicht_passt}\n\n"
        )
        if vorschlag:
            issue_body += f"## Vorschlag fuer ein neues Tool / Erweiterung\n\n{vorschlag}\n\n"
        issue_body += (
            f"---\n\n"
            f"_Gemeldet aus PBP v{_ver} via `pbp_grenze_melden`. "
            f"Anti-DB-Bypass-Pattern (#514)._"
        )

        gh_url = (
            "https://github.com/MadGapun/PBP/issues/new"
            f"?title={quote(issue_title)}"
            f"&body={quote(issue_body)}"
            f"&labels=enhancement"
        )

        return {
            "status": "gemeldet",
            "hinweis_fuer_user": (
                "Die fehlende Tool-Abdeckung wurde erkannt und in der lokalen "
                "limitations.log dokumentiert. PBP wird nicht durch direkten "
                "DB-Eingriff umgangen — stattdessen kann der unten verlinkte "
                "GitHub-Issue-Entwurf gepostet werden, damit das Feature in "
                "einer kuenftigen Version landet."
            ),
            "gh_issue_url": gh_url,
            "vorgeschlagener_issue_titel": issue_title,
            "vorgeschlagener_issue_body": issue_body,
            "moeglicher_workaround": (
                "Bis ein passendes Tool existiert: User kann die Aktion "
                "manuell im PBP-Dashboard (http://localhost:8200) durchfuehren — "
                "dort werden alle Lifecycle-Hooks korrekt ausgeloest."
            ),
        }

    # === Granulare KI-Steuerung (#425, v1.7.0-beta.56) =====================

    @mcp.tool()
    def ki_features_lesen() -> dict:
        """Liefert den aktuellen Stand der KI-Feature-Toggles.

        Acht Schalter: master + 7 Feature-Bereiche (jobsuche,
        dokumentenanalyse, stellenanalyse, bewerbungserstellung,
        coaching, ersterfassung, guidance). Default: alles True.

        Use Case: User fragt 'welche KI-Features sind bei mir an?'
        oder Claude will vor einer KI-Operation pruefen ob er darf.
        """
        cfg = db.get_ki_features()
        return {
            "features": cfg,
            "alle_aktiv": all(cfg.values()),
            "master_aus": not cfg.get("master", True),
            "hinweis": (
                "master=False blockt alles. Einzelne Features lassen sich "
                "via ki_features_setzen(jobsuche=False, ...) gezielt ab- "
                "oder anschalten."
            ),
        }

    @mcp.tool()
    def ki_features_setzen(
        master: bool | None = None,
        jobsuche: bool | None = None,
        dokumentenanalyse: bool | None = None,
        stellenanalyse: bool | None = None,
        bewerbungserstellung: bool | None = None,
        coaching: bool | None = None,
        ersterfassung: bool | None = None,
        guidance: bool | None = None,
    ) -> dict:
        """Aktualisiert KI-Feature-Toggles. Nur uebergebene Werte werden gesetzt.

        Args (jeweils True/False, None = unveraendert):
            master: Master-Switch. False = alle KI-Features blockt.
            jobsuche: Jobsuche via Claude (Dashboard-Button bleibt immer).
            dokumentenanalyse: Profildaten aus Dokumenten extrahieren.
            stellenanalyse: Fit-Analyse, Skill-Gap, Score-Refinement.
            bewerbungserstellung: Anschreiben + angepasster CV via Claude.
            coaching: Interview-Sim, Gehaltsverhandlung.
            ersterfassung: Profil-Gespraech via Claude.
            guidance: Dashboard-Hinweise die auf Claude verweisen.
        """
        fields = {
            k: v for k, v in {
                "master": master,
                "jobsuche": jobsuche,
                "dokumentenanalyse": dokumentenanalyse,
                "stellenanalyse": stellenanalyse,
                "bewerbungserstellung": bewerbungserstellung,
                "coaching": coaching,
                "ersterfassung": ersterfassung,
                "guidance": guidance,
            }.items() if v is not None
        }
        if not fields:
            return {
                "fehler": "Mindestens ein Feld muss gesetzt werden.",
                "aktueller_stand": db.get_ki_features(),
            }
        try:
            cfg = db.set_ki_features(**fields)
        except ValueError as exc:
            return {"fehler": str(exc)}
        return {
            "status": "gespeichert",
            "geaendert": fields,
            "features": cfg,
        }

    # === Telemetrie-Sharing-Steuerung (#594 Stufe 5, beta.93) ==========

    @mcp.tool()
    def telemetrie_status() -> dict:
        """Liefert den Stand des Telemetrie-Sharings (#594 Stufe 5).

        Telemetrie-Sharing ist opt-in und teilt NUR anonymisierte,
        aggregierte Lern-Erkenntnisse (keine Profildaten, keine Job-Titel,
        keine Firmen) — und auch das nur, wenn der User die Vorschau-Mail
        selbst abschickt. Es geht NIE automatisch etwas raus.

        Use Case: 'ist bei mir Telemetrie an?' oder Recovery, falls der
        Datenschutz-Tab im Dashboard gerade nicht erreichbar ist.
        """
        s = db.get_telemetry_settings()
        return {
            "aktiv": bool(s.get("enabled")),
            "intervall_tage": s.get("interval_days"),
            "letzter_share": s.get("last_share_at") or None,
            "empfaenger": s.get("recipient"),
            "hinweis": (
                "Mit telemetrie_setzen(aktiv=False) abschalten. Versand bleibt "
                "immer in User-Hand (mailto-Link), nie automatisch."
            ),
        }

    @mcp.tool()
    def telemetrie_setzen(
        aktiv: bool | None = None,
        intervall_tage: int | None = None,
    ) -> dict:
        """Schaltet Telemetrie-Sharing an/aus oder setzt das Nachfrage-Intervall.

        Recovery-Pfad: falls der Datenschutz-Tab im Dashboard mal nicht
        erreichbar ist, kann hierueber das Sharing wieder abgeschaltet werden.

        Args:
            aktiv: True = Sharing erlauben (wochenweise Vorschau), False = aus.
                None = unveraendert.
            intervall_tage: Nachfrage-Rhythmus: 0 (nie automatisch), 7, 14
                oder 30. None = unveraendert.
        """
        if aktiv is None and intervall_tage is None:
            return {
                "fehler": "Mindestens aktiv oder intervall_tage angeben.",
                "aktueller_stand": db.get_telemetry_settings(),
            }
        try:
            out = db.set_telemetry_settings(
                enabled=aktiv,
                interval_days=intervall_tage,
            )
        except ValueError as exc:
            return {"fehler": str(exc)}
        return {
            "status": "gespeichert",
            "aktiv": bool(out.get("enabled")),
            "intervall_tage": out.get("interval_days"),
        }

    # === Automatik-Scheduler (#677/#678, beta.94) ======================

    @mcp.tool()
    def automatik_status() -> dict:
        """Status der Hintergrund-Automatik (#677/#678).

        Zwei Tasks mit Intervall in Tagen (0 = aus):
        - `lernen`: Ollama analysiert Aktivitaet + Dokumente (Pattern-Lernen).
        - `jobsuche`: die INTERNE Jobsuche (nur Scraper; Browser-/Login-
          Quellen bleiben manuell ueber Claude-in-Chrome).

        Liefert je Task Intervall, letzten und naechsten Lauf. Laeuft nur,
        solange Claude Desktop / der MCP-Server offen ist (kein Dienst).
        """
        from ..services.automatik_scheduler import compute_status
        return compute_status(db)

    @mcp.tool()
    def automatik_setzen(
        jobsuche_intervall_tage: int | None = None,
        lernen_intervall_tage: int | None = None,
    ) -> dict:
        """Setzt die Intervalle der Hintergrund-Automatik (#677/#678).

        Erlaubte Werte: 0 (aus), 1, 3, 7, 14, 30 Tage. None = unveraendert.

        Args:
            jobsuche_intervall_tage: wie oft die INTERNE Jobsuche laeuft.
            lernen_intervall_tage: wie oft Ollama aus Verhalten/Dokumenten
                lernt (greift nur, wenn der Lern-Modus an ist).
        """
        if jobsuche_intervall_tage is None and lernen_intervall_tage is None:
            return {
                "fehler": "Mindestens ein Intervall angeben.",
                "aktueller_stand": db.get_automatik_settings(),
            }
        try:
            db.set_automatik_settings(
                jobsuche_intervall_tage=jobsuche_intervall_tage,
                lernen_intervall_tage=lernen_intervall_tage,
            )
        except ValueError as exc:
            return {"fehler": str(exc)}
        from ..services.automatik_scheduler import compute_status
        return {"status": "gespeichert", **compute_status(db)}

    # === MCP-Tool-Telemetrie (#636, beta.60) ===========================

    @mcp.tool()
    def pbp_mcp_diagnose(
        limit: int = 30,
        nur_langsame: bool = False,
        threshold_sec: float = 5.0,
    ) -> dict:
        """Liefert MCP-Tool-Call-Telemetrie fuer Diagnose von Hangern/Timeouts.

        Use Case: Wenn ein Tool im Claude Desktop in einen 4-Minuten-Timeout
        laeuft, hilft dieses Tool zu sehen ob der Server den Tool-Call ueberhaupt
        empfangen und verarbeitet hat — und wie lange er dafuer brauchte.

        Liefert:
        - Liste der letzten N Tool-Calls (neueste zuerst) mit Dauer + Status
        - Optional gefiltert auf langsame Calls (Default: >= 5 Sek)
        - Aktuelle Server-PID + Plattform-Info

        Args:
            limit: Max Anzahl Calls (Default 30, max 200)
            nur_langsame: True = nur Calls >= threshold_sec
            threshold_sec: Schwelle fuer "langsam" (Default 5.0)
        """
        import os as _os
        import platform as _pf
        import sys as _sys
        from .. import __version__

        limit = max(1, min(int(limit or 30), 200))
        if nur_langsame:
            calls = get_slow_tool_calls(limit, threshold_sec)
        else:
            calls = get_recent_tool_calls(limit)

        # Stats
        ok_count = sum(1 for c in calls if c.get("status") == "ok")
        fehler_count = sum(1 for c in calls if c.get("status") == "fehler")
        exception_count = sum(1 for c in calls if c.get("status") == "exception")

        # Convert "at" timestamps to readable
        from datetime import datetime
        for c in calls:
            try:
                c["at_iso"] = datetime.fromtimestamp(c["at"]).isoformat(timespec="seconds")
            except Exception:
                c["at_iso"] = str(c.get("at", ""))

        # v1.7.0-beta.66 (#638 Stufe 5): Ollama-Auto-Entscheidungs-Genauigkeit
        try:
            ollama_accuracy = db.get_ollama_accuracy_stats()
        except Exception:
            ollama_accuracy = {}

        return {
            "status": "ok",
            "server_pid": _os.getpid(),
            "pbp_version": __version__,
            "python_version": _sys.version.split()[0],
            "platform": _pf.platform(),
            "tool_calls": calls,
            "ollama_genauigkeit": ollama_accuracy,
            "stats": {
                "anzahl": len(calls),
                "ok": ok_count,
                "fehler": fehler_count,
                "exception": exception_count,
                "langsame_threshold_sec": threshold_sec,
            },
            "hinweis": (
                "Wenn ein Tool in Claude Desktop timeout, aber HIER nicht "
                "auftaucht: der MCP-Server hat den Aufruf nie empfangen "
                "(Transport-Problem). Wenn es auftaucht mit hoher Dauer: "
                "der Tool-Code selbst haengt — bitte Issue mit den "
                "args_summary-Daten oeffnen."
            ),
        }

    # === G11 (#652, beta.76): Onboarding-Hints fuer ungenutzte Features ===

    @mcp.tool()
    def onboarding_hints_anzeigen() -> dict:
        """Liefert aktive Onboarding-Hints fuer ungenutzte Features (#652).

        Pro Hint wird die Condition geprueft (z.B. "0 Suchprofile + 3+
        Bewerbungen"), bereits weggeklickte Hints werden uebersprungen.
        Frontend zeigt die zurueckgegebenen Hints als kleine Tipp-Cards
        in den jeweiligen Tabs.

        Use Case: User hat Features im Code, kennt sie aber nicht. Statt
        ihn mit Onboarding-Walkthrough zu nerven kommen die Tipps
        kontextuell wenn sie wirklich relevant sind (z.B. die
        Aufwand-Erfassung erst nach 5 Terminen).

        Liefert: {hints: [...], anzahl: N}. Bei Fehler eine leere Liste —
        Hints duerfen nie blocken.
        """
        from ..services.onboarding_hints import list_active_hints
        try:
            hints = list_active_hints(db)
        except Exception as exc:
            logger.warning("onboarding_hints_anzeigen failed: %s", exc)
            return {"hints": [], "anzahl": 0, "fehler": str(exc)[:200]}
        return {
            "hints": hints,
            "anzahl": len(hints),
            "hinweis": (
                "Pro Hint kann der User mit onboarding_hint_dismiss(hint_id) "
                "die Card wegklicken — sie kommt dann nie wieder."
            ) if hints else None,
        }

    @mcp.tool()
    def onboarding_hint_dismiss(hint_id: str) -> dict:
        """Markiert einen Onboarding-Hint als dauerhaft weggeklickt (#652).

        Die Hint-ID wird in `profile_settings.onboarding_hints_dismissed`
        gespeichert (JSON-Liste). Beim naechsten `onboarding_hints_anzeigen`
        erscheint sie nicht mehr — selbst wenn die Condition weiterhin
        zutrifft.

        Args:
            hint_id: Stabile ID des Hints (z.B. 'g11_suchprofile_anlegen').
                Bekannte IDs liefert `onboarding_hints_anzeigen`.

        Liefert {dismissed: True, hint_id, total_dismissed} bei Erfolg.
        Bei unbekannter ID: {error, bekannte_ids: [...]}.
        """
        from ..services.onboarding_hints import dismiss_hint
        return dismiss_hint(db, hint_id)

    # === v1.7.10 (#784, F28): learned_insights — Fundament der Lernschleife ===

    @mcp.tool()
    def erkenntnisse_ableiten(dry_run: bool = True) -> dict:
        """Leitet Kandidaten-Erkenntnisse aus dem PBP-Verhalten ab (#784/F28).

        Regelbasiert (deterministisch): dominante Aussortier-Gruende,
        Zeitarbeit-Muster, Hochscore-Fehlleitungen, Kanal-Unterschiede.
        Jede Aussage traegt EVIDENZ und eine KONFIDENZ aus der Fallzahl —
        zwei Faelle sind eine Vermutung, dreissig ein Muster.

        ⛔ GRUNDSATZ: Keine Erkenntnis wird ohne Nutzerbestaetigung wirksam.
        Dieses Tool leitet ab und legt UNBESTAETIGT ab — angewendet wird
        nichts. Bestaetigen/verwerfen: erkenntnis_bestaetigen(). Bereits
        widersprochene Aussagen werden NIE erneut vorgeschlagen.

        Args:
            dry_run: True (Default) = nur anzeigen, nichts speichern.
                False = Kandidaten als unbestaetigt ablegen.
        """
        from ..services.lerninsights import kandidaten_ableiten, speichern
        kandidaten = kandidaten_ableiten(db)
        result = {
            "status": "vorschau" if dry_run else "abgelegt",
            "kandidaten": kandidaten,
            "anzahl": len(kandidaten),
            "hinweis": (
                "Nichts davon ist wirksam, bevor der User es per "
                "erkenntnis_bestaetigen() bestaetigt hat."
            ),
        }
        if not dry_run and kandidaten:
            result["gespeichert"] = speichern(db, kandidaten)
        return result

    @mcp.tool()
    def erkenntnisse_anzeigen(filter: str = "alle") -> dict:
        """Zeigt abgeleitete Erkenntnisse mit Evidenz und Status (#784/F28).

        Args:
            filter: 'alle', 'offen' (unbestaetigt), 'bestaetigt' oder
                'widersprochen'.
        """
        conn = db.connect()
        pid = db.get_active_profile_id() or ""
        status_map = {"offen": 0, "bestaetigt": 1, "widersprochen": -1}
        sql = ("SELECT * FROM learned_insights "
               "WHERE (profile_id=? OR profile_id='')")
        params: list = [pid]
        if filter in status_map:
            sql += " AND bestaetigt_vom_user=?"
            params.append(status_map[filter])
        elif filter != "alle":
            return {"fehler": "filter muss alle/offen/bestaetigt/widersprochen sein."}
        rows = conn.execute(sql + " ORDER BY konfidenz DESC", params).fetchall()
        import json as _json
        eintraege = []
        for r in rows:
            try:
                evidenz = _json.loads(r["evidenz_json"] or "{}")
            except Exception:
                evidenz = {}
            eintraege.append({
                "id": r["id"][:8],
                "kategorie": r["kategorie"],
                "aussage": r["aussage"],
                "konfidenz": r["konfidenz"],
                "belegt_durch_n": r["belegt_durch_n"],
                "status": {0: "offen", 1: "bestaetigt",
                           -1: "widersprochen"}.get(
                    r["bestaetigt_vom_user"], "offen"),
                "evidenz": evidenz,
            })
        return {"erkenntnisse": eintraege, "anzahl": len(eintraege),
                "filter": filter}

    @mcp.tool()
    def erkenntnis_bestaetigen(erkenntnis_id: str, bestaetigen: bool) -> dict:
        """Kuratiert eine Erkenntnis: bestaetigen oder widersprechen (#784/F28).

        Widersprochene Erkenntnisse werden nicht geloescht, sondern als
        widersprochen markiert (-1) — dieselbe Fehlableitung wird dadurch
        nie erneut vorgeschlagen.

        Args:
            erkenntnis_id: ID aus erkenntnisse_anzeigen (Kurzform reicht).
            bestaetigen: True = bestaetigt (darf kuenftig als Kontext
                dienen), False = widersprochen.
        """
        conn = db.connect()
        pid = db.get_active_profile_id() or ""
        row = conn.execute(
            "SELECT id, aussage FROM learned_insights "
            "WHERE (profile_id=? OR profile_id='') AND id LIKE ?",
            (pid, (erkenntnis_id or "") + "%"),
        ).fetchone()
        if not row:
            return {"fehler": "Erkenntnis nicht gefunden. "
                              "IDs liefert erkenntnisse_anzeigen()."}
        wert = 1 if bestaetigen else -1
        from datetime import datetime as _dt
        conn.execute(
            "UPDATE learned_insights SET bestaetigt_vom_user=?, "
            "aktualisiert_am=? WHERE id=?",
            (wert, _dt.now().isoformat(), row["id"]))
        conn.commit()
        return {
            "status": "bestaetigt" if bestaetigen else "widersprochen",
            "id": row["id"][:8],
            "aussage": row["aussage"],
            "hinweis": (
                "Bestaetigte Erkenntnisse stehen der lokalen KI als Kontext "
                "zur Verfuegung (elwosa_fragen); automatisch ANGEWENDET "
                "wird weiterhin nichts (v1.8-Teil von #784)."
                if bestaetigen else
                "Wird nicht erneut vorgeschlagen."
            ),
        }
