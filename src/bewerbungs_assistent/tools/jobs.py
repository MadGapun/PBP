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
        from ..job_scraper import fit_analyse as _fit_analyse
        conn = db.connect()
        row = conn.execute("SELECT * FROM jobs WHERE hash = ?", (job_hash,)).fetchone()
        if not row:
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
        return _fit_analyse(dict(row), criteria)
