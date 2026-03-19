"""Jobsuche und Stellenverwaltung — 5 Tools."""

import threading


def register(mcp, db, logger):
    """Registriert Jobsuche-Tools."""

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
            quellen = db.get_profile_setting("active_sources", [])
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

        # Start background search with timeout
        def _run_search():
            try:
                from ..job_scraper import run_search
                run_search(db, job_id, params)
            except Exception as e:
                logger.error("Jobsuche fehlgeschlagen: %s", e, exc_info=True)
                db.update_background_job(job_id, "fehler", message=str(e))

        thread = threading.Thread(target=_run_search, daemon=True)
        thread.start()

        # Timeout watchdog: mark as failed if still running after 10 minutes
        def _timeout_watchdog():
            thread.join(timeout=600)
            if thread.is_alive():
                logger.warning("Jobsuche Timeout nach 10 Minuten (Job %s)", job_id)
                db.update_background_job(job_id, "fehler", message="Timeout nach 10 Minuten")

        threading.Thread(target=_timeout_watchdog, daemon=True).start()

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

    # Standard rejection reasons for learning (#66)
    ABLEHNUNGSGRUENDE = [
        "zu_weit_entfernt",
        "gehalt_zu_niedrig",
        "falsches_fachgebiet",
        "zu_junior",
        "zu_senior",
        "unpassendes_arbeitsmodell",
        "firma_uninteressant",
        "zeitarbeit",
        "befristet",
        "sonstiges",
    ]

    @mcp.tool()
    def stelle_bewerten(job_hash: str, bewertung: str, grund: str = "") -> dict:
        """Bewertet eine gefundene Stelle.

        Bei 'passt_nicht' wird der Grund gespeichert und fuer kuenftige Suchen gelernt.
        Haeufig genutzte Gruende fuehren automatisch zu Gewichtungsanpassungen.

        Args:
            job_hash: Hash der Stelle
            bewertung: 'passt' oder 'passt_nicht'
            grund: Grund bei passt_nicht. Vordefinierte Optionen:
                zu_weit_entfernt, gehalt_zu_niedrig, falsches_fachgebiet,
                zu_junior, zu_senior, unpassendes_arbeitsmodell,
                firma_uninteressant, zeitarbeit, befristet, sonstiges
                (oder eigener Freitext)
        """
        if bewertung == "passt_nicht":
            db.dismiss_job(job_hash, grund)
            if grund:
                db.add_to_blacklist("dismiss_pattern", grund)

                # Track rejection counts for learning (#66)
                counts = db.get_setting("dismiss_counts", {})
                normalized = grund.lower().strip()
                counts[normalized] = counts.get(normalized, 0) + 1
                db.set_setting("dismiss_counts", counts)

                # Auto-adjust weights if pattern is strong enough
                hints = []
                if counts.get(normalized, 0) >= 3:
                    if normalized == "zu_weit_entfernt":
                        hints.append("Entfernungs-Malus wird verstaerkt (3+ Ablehnungen wegen Entfernung).")
                    elif normalized == "gehalt_zu_niedrig":
                        hints.append("Gehalts-Gewichtung wird verstaerkt (3+ Ablehnungen wegen Gehalt).")
                    elif normalized in ("zeitarbeit", "befristet"):
                        hints.append(f"Empfehlung: Fuege '{grund}' zu AUSSCHLUSS-Keywords hinzu.")

                return {
                    "status": "aussortiert",
                    "grund": grund,
                    "ablehnungs_statistik": {k: v for k, v in sorted(counts.items(), key=lambda x: -x[1])[:5]},
                    "hinweise": hints if hints else None,
                    "verfuegbare_gruende": ABLEHNUNGSGRUENDE,
                }
            return {"status": "aussortiert", "grund": grund}
        elif bewertung == "passt":
            db.restore_job(job_hash)
            return {"status": "als_passend_markiert"}
        return {"fehler": "Ungueltige Bewertung. Nutze 'passt' oder 'passt_nicht'."}

    @mcp.tool()
    def stellen_anzeigen(
        filter: str = "aktiv",
        min_score: int = 0,
        quelle: str = "",
        seite: int = 1,
        pro_seite: int = 20,
        max_alter_tage: int = 0,
        nur_nicht_beworben: bool = False
    ) -> dict:
        """Zeigt gefundene Stellenangebote an.

        Gibt die Liste der Stellen zurueck, sortiert nach Score.
        Nutze stelle_bewerten() um einzelne Stellen zu bewerten.

        Args:
            filter: 'aktiv' (Standard), 'aussortiert', oder 'alle'
            min_score: Nur Stellen mit mindestens diesem Score anzeigen (Tipp: 1 = mindestens ein Keyword-Treffer)
            quelle: Optional: Nur Stellen von dieser Quelle (z.B. 'stepstone', 'indeed', 'manuell')
            seite: Seitennummer fuer Paginierung (Standard: 1)
            pro_seite: Anzahl Stellen pro Seite (Standard: 20, max: 50)
            max_alter_tage: Nur Stellen die nicht aelter als X Tage sind (0 = kein Limit)
            nur_nicht_beworben: Nur Stellen anzeigen auf die noch nicht beworben wurde
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

        # Age filter (#52)
        if max_alter_tage > 0:
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(days=max_alter_tage)).isoformat()
            jobs = [j for j in jobs if (j.get("found_at") or "") >= cutoff]

        # Filter out already-applied jobs (#65)
        if nur_nicht_beworben:
            applied_hashes = {
                r["job_hash"] for r in db.get_applications()
                if r.get("job_hash")
            }
            jobs = [j for j in jobs if j["hash"] not in applied_hashes]

        if not jobs:
            return {
                "anzahl": 0,
                "nachricht": "Keine Stellen gefunden. "
                             "Starte eine Jobsuche mit jobsuche_starten() oder "
                             "aktiviere Quellen im Dashboard unter Einstellungen."
            }

        # Count per source for overview
        source_counts = {}
        for j in jobs:
            src = j.get("source", "unbekannt")
            source_counts[src] = source_counts.get(src, 0) + 1

        # Check which jobs have been applied to (#65)
        applied_hashes_all = {
            r["job_hash"] for r in db.get_applications()
            if r.get("job_hash")
        } if not nur_nicht_beworben else set()

        # Pagination (#58)
        pro_seite = min(pro_seite, 50)
        total = len(jobs)
        start = (seite - 1) * pro_seite
        end = start + pro_seite
        page_jobs = jobs[start:end]

        # Format for Claude readability
        formatted = []
        for j in page_jobs:
            entry = {
                "hash": j["hash"],
                "titel": j.get("title", ""),
                "firma": j.get("company", ""),
                "ort": j.get("location", ""),
                "score": j.get("score", 0),
                "quelle": j.get("source", ""),
                "remote": j.get("remote_level", "unbekannt"),
                "url": j.get("url", ""),
                "gefunden_am": (j.get("found_at") or "")[:10],
            }
            if j.get("employment_type"):
                entry["typ"] = j["employment_type"]
            if j.get("salary_min"):
                entry["gehalt_min"] = j["salary_min"]
                entry["gehalt_max"] = j.get("salary_max")
                entry["gehalt_typ"] = j.get("salary_type", "jaehrlich")
                if j.get("salary_estimated"):
                    entry["gehalt_geschaetzt"] = True
            if j.get("distance_km"):
                entry["entfernung_km"] = j["distance_km"]
            if j.get("dismiss_reason"):
                entry["aussortiert_grund"] = j["dismiss_reason"]
            if j["hash"] in applied_hashes_all:
                entry["bereits_beworben"] = True
            formatted.append(entry)

        result = {
            "anzahl_gesamt": total,
            "seite": seite,
            "pro_seite": pro_seite,
            "seiten_gesamt": (total + pro_seite - 1) // pro_seite,
            "angezeigt": len(formatted),
            "quellen_uebersicht": source_counts,
            "stellen": formatted,
        }
        if filter == "aktiv":
            result["hinweis"] = (
                "Nutze stelle_bewerten(hash, 'passt') oder stelle_bewerten(hash, 'passt_nicht', 'Grund') "
                "um Stellen zu bewerten. Fuer Details: fit_analyse(hash). "
                f"Naechste Seite: stellen_anzeigen(seite={seite+1})" if seite * pro_seite < total else
                "Nutze stelle_bewerten(hash, 'passt') oder stelle_bewerten(hash, 'passt_nicht', 'Grund') "
                "um Stellen zu bewerten. Fuer Details: fit_analyse(hash)."
            )
        return result

    @mcp.tool()
    def linkedin_browser_search(
        keywords: list[str] = None,
        location: str = "Deutschland",
        remote_only: bool = False,
        max_pages: int = 3
    ) -> dict:
        """Direkte LinkedIn-Jobsuche via Browser-Automation (Playwright).

        Kann unabhaengig von jobsuche_starten() aufgerufen werden.
        Nutzt die gespeicherte Browser-Session (beim ersten Mal wird ein
        Browser-Fenster zur Anmeldung geoeffnet).

        Ergebnisse werden automatisch in die PBP-Datenbank gespeichert
        und nach den aktuellen Suchkriterien bewertet.

        Args:
            keywords: Suchbegriffe (Standard: aus keywords_muss generiert)
            location: Standort-Filter (Standard: Deutschland)
            remote_only: Nur Remote-Stellen (f_WT=2)
            max_pages: Maximale Seiten pro Suchbegriff (Standard: 3, je 25 Ergebnisse)
        """
        from ..job_scraper import run_search, calculate_score, extract_salary_from_text, estimate_salary

        criteria = db.get_search_criteria()

        params = {
            "keywords": {"general": keywords} if keywords else {},
            "criteria": criteria,
            "quellen": ["linkedin"],
            "nur_remote": remote_only,
            "max_pages": max_pages,
        }

        # Override location if provided
        if location != "Deutschland":
            if "criteria" not in params:
                params["criteria"] = {}
            params["criteria"]["regionen"] = [location]

        job_id = db.create_background_job("linkedin_browser_search", params)

        def _run():
            try:
                from ..job_scraper.linkedin import search_linkedin
                import time

                def _progress(msg):
                    db.update_background_job(job_id, "running", message=msg)

                jobs = search_linkedin(params, progress_callback=_progress)

                # Score and enrich
                for job in jobs:
                    job["score"] = calculate_score(job, criteria)
                    if not job.get("salary_min"):
                        text = f"{job.get('description', '')} {job.get('title', '')}"
                        s_min, s_max, s_type = extract_salary_from_text(text)
                        if s_min:
                            job["salary_min"] = s_min
                            job["salary_max"] = s_max
                            job["salary_type"] = s_type
                            job["salary_estimated"] = 0
                    if not job.get("salary_min"):
                        s_min, s_max, s_type = estimate_salary(
                            job.get("title", ""), job.get("employment_type", ""), job.get("location", "")
                        )
                        job["salary_min"] = s_min
                        job["salary_max"] = s_max
                        job["salary_type"] = s_type
                        job["salary_estimated"] = 1

                # Filter by min score
                min_score = criteria.get("min_score_schwelle", 1)
                jobs = [j for j in jobs if j.get("score", 0) >= min_score]

                db.save_jobs(jobs)
                db.set_profile_setting("last_search_at", time.strftime("%Y-%m-%dT%H:%M:%S"))
                db.update_background_job(
                    job_id, "fertig", progress=100,
                    message=f"LinkedIn: {len(jobs)} Stellen gefunden und gespeichert",
                    result={"total": len(jobs), "quelle": "linkedin"},
                )
            except Exception as e:
                logger.error("LinkedIn Browser-Suche fehlgeschlagen: %s", e, exc_info=True)
                db.update_background_job(job_id, "fehler", message=str(e))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        return {
            "job_id": job_id,
            "status": "gestartet",
            "nachricht": (
                f"LinkedIn Browser-Suche laeuft (max {max_pages} Seiten pro Suchbegriff). "
                f"Pruefe Fortschritt mit jobsuche_status('{job_id}')."
            ),
        }

    @mcp.tool()
    def fit_analyse(job_hash: str) -> dict:
        """Detaillierte Passungsanalyse fuer eine bestimmte Stelle.

        Zeigt welche Keywords matchen, was fehlt, und gibt eine Risikobewertung.

        Args:
            job_hash: Hash der Stelle (von stellen_anzeigen)
        """
        from ..job_scraper import fit_analyse as _fit_analyse
        job_dict = db.get_job(job_hash)
        if not job_dict:
            return {"fehler": "Stelle nicht gefunden. Pruefe den Hash mit stellen_anzeigen()."}
        criteria = db.get_search_criteria()
        # Enrich criteria with profile skills and salary preferences for better fit analysis
        profile = db.get_profile()
        if profile:
            skills = profile.get("skills", [])
            criteria["_profile_skills"] = [s.get("name", "").lower() for s in skills if s.get("name")]
            prefs = profile.get("preferences", {})
            if prefs.get("min_gehalt"):
                criteria["min_gehalt"] = prefs["min_gehalt"]
            if prefs.get("min_tagessatz"):
                criteria["min_tagessatz"] = prefs["min_tagessatz"]
        result = _fit_analyse(job_dict, criteria)
        # Include job description in result (#55) so Claude can use it for analysis
        if job_dict.get("description"):
            result["stellenbeschreibung"] = job_dict["description"][:2000]
        result["url"] = job_dict.get("url", "")
        return result
