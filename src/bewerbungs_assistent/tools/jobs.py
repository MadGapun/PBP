"""Jobsuche und Stellenverwaltung — 9 Tools (#446: stelle_bearbeiten, #432: scraper_diagnose)."""

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

        Die Suche dauert 5-10 Minuten. Prüfe den Fortschritt mit jobsuche_status().
        Ergebnisse danach mit stellen_anzeigen() ansehen.

        HINWEIS StepStone (#315): StepStone blockiert automatische Suche (Bot-Detection).
        Fuer StepStone-Stellen nutze stattdessen Claude-in-Chrome:
        1. Oeffne https://www.stepstone.de/jobs/{keyword}?radius=100&location={ort}
        2. Uebernimm gefundene Stellen mit stelle_manuell_anlegen().

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

        # Prevent duplicate concurrent searches (#265)
        existing = db.get_running_background_job("jobsuche")
        if existing:
            return {
                "status": "laeuft_bereits",
                "job_id": existing["id"],
                "nachricht": "Eine Jobsuche läuft bereits. "
                            f"Prüfe den Fortschritt mit jobsuche_status('{existing['id']}')."
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
            "nachricht": f"Jobsuche läuft auf {len(params['quellen'])} Portalen. "
                        f"Prüfe den Fortschritt mit jobsuche_status('{job_id}')."
        }

    @mcp.tool()
    def jobsuche_status(job_id: str) -> dict:
        """Prüft den Fortschritt einer laufenden Jobsuche.

        Args:
            job_id: Job-ID von jobsuche_starten()
        """
        job = db.get_background_job(job_id)
        if job is None:
            return {"fehler": "Unbekannte Job-ID"}
        result = {
            "status": job["status"],
            "fortschritt": f"{job['progress']}%",
            "nachricht": job["message"],
            "ergebnis": job["result"] if job["status"] == "fertig" else None,
        }
        # Include cleanup stats if available (#153)
        if job["status"] == "fertig" and isinstance(job.get("result"), dict):
            bereinigung = job["result"].get("bereinigung")
            if bereinigung:
                result["bereinigung"] = bereinigung
        return result

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
        "bereits_beworben",
        "duplikat",
        "kein_hochschulabschluss",
        "sonstiges",
    ]

    def _detect_duplicate(job_hash: str) -> dict | None:
        """Duplikat-Erkennung (#168): Prüft ob eine ähnliche Stelle existiert."""
        job = db.get_job(job_hash)
        if not job:
            return None
        title = (job.get("title") or "").lower()
        company = (job.get("company") or "").lower()
        if not title or not company:
            return None

        # Check existing applications
        apps = db.get_applications()
        for app in apps:
            app_title = (app.get("title") or "").lower()
            app_company = (app.get("company") or "").lower()
            if company in app_company or app_company in company:
                # Company match — check title similarity
                title_words = set(title.split())
                app_words = set(app_title.split())
                overlap = title_words & app_words
                if len(overlap) >= min(2, len(title_words)):
                    return {
                        "typ": "bewerbung",
                        "id": app["id"][:8],
                        "titel": app.get("title"),
                        "firma": app.get("company"),
                        "status": app.get("status"),
                    }

        # Check existing dismissed jobs with same company
        dismissed = db.get_dismissed_jobs()
        for dj in dismissed:
            dj_company = (dj.get("company") or "").lower()
            dj_title = (dj.get("title") or "").lower()
            if company in dj_company or dj_company in company:
                title_words = set(title.split())
                dj_words = set(dj_title.split())
                overlap = title_words & dj_words
                if len(overlap) >= min(2, len(title_words)):
                    return {
                        "typ": "aussortierte_stelle",
                        "hash": dj["hash"][:8],
                        "titel": dj.get("title"),
                        "firma": dj.get("company"),
                        "grund": dj.get("dismiss_reason"),
                    }
        return None

    def _normalize_dismiss_reason(reason: str) -> str:
        """Normalisiere Freitext-Ablehnungsgründe auf Standard-Keywords (#158)."""
        lower = reason.lower().strip()
        if "bereits beworben" in lower or "schon beworben" in lower:
            return "bereits_beworben"
        if "zu weit" in lower or "entfernung" in lower:
            return "zu_weit_entfernt"
        if "gehalt" in lower or "zu niedrig" in lower:
            return "gehalt_zu_niedrig"
        if "zeitarbeit" in lower or "arbeitnehmerüberl" in lower:
            return "zeitarbeit"
        if "befristet" in lower:
            return "befristet"
        if "hochschul" in lower or "studium" in lower or "abschluss" in lower or "ats" in lower:
            return "kein_hochschulabschluss"
        return reason

    def _auto_adjust_scoring(db_ref, reason: str, count: int) -> str | None:
        """#110: Automatische Scoring-Anpassung bei wiederholten Ablehnungsmustern.

        Bug #269: Seed-Daten haben profile_id='', daher muss mit
        (profile_id=? OR profile_id='') gesucht werden.
        """
        LEARN_MAP = {
            "zu_weit_entfernt": ("entfernung_fest", "50km", -2),
            "zeitarbeit": ("stellentyp", "zeitarbeit", None),  # None = ignore
            "befristet": ("stellentyp", "befristet", None),
            "zu_junior": ("stellentyp", "praktikum", None),
        }
        if reason not in LEARN_MAP:
            return None
        dim, sub, adjustment = LEARN_MAP[reason]
        conn = db_ref.connect()
        pid = db_ref.get_active_profile_id() or ""
        # #269: Seed-Daten haben profile_id='' — beides prüfen
        existing = conn.execute(
            "SELECT id, value, ignore_flag, profile_id FROM scoring_config "
            "WHERE (profile_id=? OR profile_id='') AND dimension=? AND sub_key=? "
            "ORDER BY CASE WHEN profile_id=? THEN 0 ELSE 1 END LIMIT 1",
            (pid, dim, sub, pid)
        ).fetchone()
        if adjustment is None:
            # Set ignore flag
            if existing and existing["ignore_flag"]:
                return None  # already ignored
            if existing:
                conn.execute(
                    "UPDATE scoring_config SET ignore_flag=1 WHERE id=?",
                    (existing["id"],)
                )
            else:
                conn.execute(
                    "INSERT INTO scoring_config (profile_id, dimension, sub_key, value, ignore_flag, created_at) "
                    "VALUES (?, ?, ?, 0, 1, ?)",
                    (pid, dim, sub, __import__("datetime").datetime.now().isoformat())
                )
            conn.commit()
            return f"'{reason}' → {dim}/{sub} auf IGNORIEREN gesetzt"
        else:
            # Increase penalty proportionally to count
            new_val = adjustment * (1 + (count - 5) * 0.5)
            new_val = max(new_val, -10)
            if existing:
                if existing["value"] <= new_val:
                    return None  # already penalized enough
                conn.execute(
                    "UPDATE scoring_config SET value=? WHERE id=?",
                    (new_val, existing["id"])
                )
            else:
                conn.execute(
                    "INSERT INTO scoring_config (profile_id, dimension, sub_key, value, ignore_flag, created_at) "
                    "VALUES (?, ?, ?, ?, 0, ?)",
                    (pid, dim, sub, new_val, __import__("datetime").datetime.now().isoformat())
                )
            conn.commit()
            return f"'{reason}' → {dim}/{sub} Malus auf {new_val}"

    @mcp.tool()
    def stelle_bewerten(job_hash: str, bewertung: str, grund: str = "",
                        gruende: list[str] = None) -> dict:
        """Bewertet eine gefundene Stelle.

        Bei 'passt_nicht' wird der Grund gespeichert und für künftige Suchen gelernt.
        Häufig genutzte Gründe führen automatisch zu Gewichtungsanpassungen.

        STRENG VERBOTEN: Die KI darf KEINE eigenen Ablehnungsgruende erfinden,
        generieren oder formulieren! Auch keine "intelligenten" Gruende wie
        "Duplikat — bereits als Bewerbung xyz erfasst". AUSSCHLIESSLICH die
        vordefinierten Gruende aus der Liste unten verwenden. Bei Unsicherheit
        den Nutzer fragen oder 'sonstiges' waehlen. Jeder nicht-vordefinierte
        Grund wird automatisch auf 'sonstiges' normalisiert.

        Args:
            job_hash: Hash der Stelle
            bewertung: 'passt' oder 'passt_nicht'
            grund: Einzelner Grund bei passt_nicht (Legacy, nutze besser gruende)
            gruende: Liste von Gruenden bei passt_nicht (Multi-Select, #108).
                ERLAUBTE WERTE (nur diese, nichts anderes!):
                zu_weit_entfernt, gehalt_zu_niedrig, falsches_fachgebiet,
                zu_junior, zu_senior, unpassendes_arbeitsmodell,
                firma_uninteressant, zeitarbeit, befristet, bereits_beworben,
                duplikat, kein_hochschulabschluss, sonstiges
        """
        import json as _json
        if bewertung == "passt_nicht":
            # Support multi-select reasons (#108, #120)
            # #302: KI-erfundene Gründe auf 'sonstiges' normalisieren
            raw_reasons = [_normalize_dismiss_reason(r) for r in (gruende or ([grund] if grund else []))]
            reason_list = list(dict.fromkeys(
                r if r in ABLEHNUNGSGRUENDE else "sonstiges" for r in raw_reasons
            ))
            if not reason_list:
                return {
                    "fehler": "Mindestens ein Ablehnungsgrund ist erforderlich.",
                    "verfuegbare_gruende": ABLEHNUNGSGRUENDE,
                }
            reason_str = _json.dumps(reason_list, ensure_ascii=False) if len(reason_list) > 1 else reason_list[0]

            # #168: Duplikat-Erkennung
            dup_info = None
            if "duplikat" in reason_list:
                dup_info = _detect_duplicate(job_hash)

            db.dismiss_job(job_hash, reason_str)

            # #168: Ablehnungsgründe gehören NICHT in die Blacklist!
            # Sie werden als dismiss_reason bei der Stelle gespeichert und
            # in dismiss_reasons für Statistiken getrackt.
            # Nur explizite Firmen-Blacklist-Anfragen → blacklist_verwalten()

            # Track rejection counts for learning (#66)
            counts = db.get_setting("dismiss_counts", {})
            hints = []
            for g in reason_list:
                normalized = g.lower().strip()
                counts[normalized] = counts.get(normalized, 0) + 1

                # Suggest scoring adjustments (#169) when patterns are strong
                if counts.get(normalized, 0) >= 3:
                    if normalized == "zu_weit_entfernt":
                        hints.append("Tipp: Passe den Entfernungs-Malus im Scoring-Regler an (scoring_konfigurieren).")
                    elif normalized == "gehalt_zu_niedrig":
                        hints.append("Tipp: Passe den Gehalts-Regler im Scoring an (scoring_konfigurieren).")
                    elif normalized in ("zeitarbeit", "befristet"):
                        hints.append(f"Tipp: Setze '{g}' im Scoring-Regler auf 'Komplett Ignorieren' (scoring_konfigurieren).")
                    elif normalized == "firma_uninteressant":
                        # Suggest adding company to blacklist
                        job = db.get_job(job_hash)
                        if job:
                            hints.append(
                                f"Tipp: Moechtest du '{job.get('company', '')}' auf die Blacklist setzen? "
                                f"Nutze blacklist_verwalten('hinzufuegen', 'firma', '{job.get('company', '')}')."
                            )

            db.set_setting("dismiss_counts", counts)
            db.increment_dismiss_reason_usage(reason_list)

            # #110: Lernender Score — automatische Scoring-Anpassungen bei starken Mustern
            auto_adjustments = []
            for g in reason_list:
                normalized = g.lower().strip()
                cnt = counts.get(normalized, 0)
                if cnt >= 5:
                    _auto = _auto_adjust_scoring(db, normalized, cnt)
                    if _auto:
                        auto_adjustments.append(_auto)
            if auto_adjustments:
                hints.append(
                    "Scoring wurde automatisch angepasst: "
                    + "; ".join(auto_adjustments)
                )

            result = {
                "status": "aussortiert",
                "gruende": reason_list,
                "ablehnungs_statistik": {k: v for k, v in sorted(counts.items(), key=lambda x: -x[1])[:5]},
                "hinweise": hints if hints else None,
                "verfuegbare_gruende": ABLEHNUNGSGRUENDE,
            }
            if dup_info:
                result["duplikat_erkannt"] = dup_info
            return result
        elif bewertung == "passt":
            db.restore_job(job_hash)
            return {"status": "als_passend_markiert"}
        return {"fehler": "Ungültige Bewertung. Nutze 'passt' oder 'passt_nicht'."}

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

        Gibt die Liste der Stellen zurück, sortiert nach Score.
        Nutze stelle_bewerten() um einzelne Stellen zu bewerten.

        Args:
            filter: 'aktiv' (Standard), 'aussortiert', oder 'alle'
            min_score: Nur Stellen mit mindestens diesem Score anzeigen (Tipp: 1 = mindestens ein Keyword-Treffer)
            quelle: Optional: Nur Stellen von dieser Quelle (z.B. 'stepstone', 'indeed', 'manuell')
            seite: Seitennummer für Paginierung (Standard: 1)
            pro_seite: Anzahl Stellen pro Seite (Standard: 20, max: 50)
            max_alter_tage: Nur Stellen die nicht älter als X Tage sind (0 = kein Limit)
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
            jobs = db.get_active_jobs(
                filters if filters else None,
                exclude_blacklisted=True,
                exclude_applied=nur_nicht_beworben,
            )

        # Age filter (#52)
        if max_alter_tage > 0:
            from datetime import datetime, timedelta
            cutoff = (datetime.now() - timedelta(days=max_alter_tage)).isoformat()
            jobs = [j for j in jobs if (j.get("found_at") or "") >= cutoff]

        # Apply scoring adjustments (#169)
        if filter != "aussortiert":
            try:
                from ..services.scoring_service import apply_scoring_adjustments
                auto_ignored = 0
                scored_jobs = []
                for j in jobs:
                    result = apply_scoring_adjustments(j, j.get("score", 0), db)
                    j["score"] = result["final_score"]
                    if result.get("ignored"):
                        auto_ignored += 1
                        continue
                    scored_jobs.append(j)
                if auto_ignored:
                    logger.info("Scoring-Regler: %d Stellen auto-ignoriert", auto_ignored)
                jobs = scored_jobs
                # Re-sort by new score
                jobs.sort(key=lambda j: (-j.get("is_pinned", 0), -j.get("score", 0)))
            except Exception as e:
                logger.debug("Scoring adjustments fehlgeschlagen: %s", e)

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
                "id": j["hash"][:8],  # #171: Kurz-ID fuer schnelle Referenz
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
            if j.get("veroeffentlicht_am"):
                entry["veroeffentlicht_am"] = j["veroeffentlicht_am"]
            emp_type = j.get("employment_type") or ""
            if emp_type == "freelance":
                typ_emoji = "🟢"
                typ_label = "🟢 Freelance"
            elif emp_type == "festanstellung":
                typ_emoji = "🔵"
                typ_label = "🔵 Festanstellung"
            else:
                typ_emoji = "⚪"
                typ_label = "⚪ Sonstige"
            entry["titel"] = f"{typ_emoji} {entry['titel']}"
            entry["typ_label"] = typ_label
            if emp_type:
                entry["typ"] = emp_type
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
            # #180: Warnung wenn Beschreibung fehlt (Score unsicher)
            desc = j.get("description") or ""
            if len(desc.strip()) < 50:
                entry["beschreibung_fehlt"] = True
                entry["score_hinweis"] = "Score basiert nur auf dem Titel — Beschreibung fehlt"
            # #436: Warnung wenn URL auf Suchergebnis-Seite zeigt statt auf Detail-Anzeige
            if j.get("is_search_url"):
                entry["url_warnung"] = (
                    "Diese URL zeigt auf eine Suchergebnis-Seite, nicht auf die konkrete "
                    "Stellenanzeige. Die Detail-URL konnte vom Scraper nicht extrahiert "
                    "werden — suche die Stelle manuell auf dem Portal."
                )
            elif j.get("url"):
                from ..job_scraper import is_search_result_url
                if is_search_result_url(j["url"]):
                    entry["url_warnung"] = (
                        "Diese URL zeigt auf eine Suchergebnis-Seite, nicht auf die konkrete "
                        "Stellenanzeige. Suche die Stelle manuell auf dem Portal."
                    )
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
                "um Stellen zu bewerten. Für Details: fit_analyse(hash). "
                f"Nächste Seite: stellen_anzeigen(seite={seite+1})" if seite * pro_seite < total else
                "Nutze stelle_bewerten(hash, 'passt') oder stelle_bewerten(hash, 'passt_nicht', 'Grund') "
                "um Stellen zu bewerten. Für Details: fit_analyse(hash)."
            )
        return result

    @mcp.tool()
    def linkedin_browser_search(
        keywords: list[str] = None,
        location: str = "Deutschland",
        remote_only: bool = False,
        max_pages: int = 3
    ) -> dict:
        """VERALTET: LinkedIn Browser-Suche ist deaktiviert (#159).

        LinkedIn blockiert automatisierte Zugriffe zuverlaessig.
        Nutze stattdessen Claude-in-Chrome Extension:
        1. Oeffne LinkedIn im Chrome-Browser mit Claude-in-Chrome
        2. Suche manuell nach Stellen
        3. Uebertrage gefundene Stellen mit stelle_manuell_anlegen()

        Args:
            keywords: (ignoriert)
            location: (ignoriert)
            remote_only: (ignoriert)
            max_pages: (ignoriert)
        """
        return {
            "status": "veraltet",
            "nachricht": (
                "Die automatische LinkedIn-Suche via Playwright ist deaktiviert (#159). "
                "LinkedIn blockiert automatisierte Zugriffe zuverlaessig. "
                "Nutze stattdessen: 1) Claude-in-Chrome Extension oeffnen, "
                "2) LinkedIn manuell durchsuchen, "
                "3) Stellen mit stelle_manuell_anlegen() uebertragen."
            ),
        }

    @mcp.tool()
    def stelle_manuell_anlegen(
        titel: str,
        firma: str,
        url: str = "",
        ort: str = "",
        beschreibung: str = "",
        quelle: str = "manuell",
        remote: str = "unbekannt",
        stellenart: str = "festanstellung",
    ) -> dict:
        """Legt eine Stelle manuell an (z.B. von LinkedIn/XING via Claude-in-Chrome) (#160).

        Nutze dieses Tool, um Stellen aus externen Quellen (LinkedIn, XING,
        Firmen-Webseiten) in PBP zu uebertragen. Die Stelle wird automatisch
        bewertet und erscheint in stellen_anzeigen().

        WICHTIG: Vor dem Anlegen wird automatisch geprueft ob bereits eine
        Bewerbung mit aehnlicher Firma+Titel existiert (#317). Bei Duplikat
        wird eine Warnung zurueckgegeben und die Stelle NICHT angelegt.

        Args:
            titel: Stellentitel (z.B. 'Senior Projektmanager PLM')
            firma: Firmenname
            url: Link zur Stellenanzeige
            ort: Arbeitsort (z.B. 'Hamburg', 'Remote')
            beschreibung: Stellenbeschreibung (so ausfuehrlich wie moeglich)
            quelle: Herkunft der Stelle (z.B. 'linkedin', 'xing', 'firmenwebsite', 'manuell')
            remote: Remote-Level ('remote', 'hybrid', 'vor_ort', 'unbekannt')
            stellenart: Art der Stelle ('festanstellung', 'freelance', 'praktikum', 'werkstudent')
        """
        if not titel or not firma:
            return {"fehler": "Titel und Firma sind Pflichtfelder."}

        from ..job_scraper import stelle_hash, calculate_score, extract_salary_from_text, estimate_salary

        job_hash = stelle_hash(quelle, f"{firma} {titel}")

        # Check for duplicates (#219: nur echte DB-Treffer, nicht scope-Prefix)
        existing_job = db.get_job(job_hash)
        if existing_job:
            return {"fehler": f"Diese Stelle existiert bereits (Hash: {existing_job['hash']})."}

        # Duplikat-Prüfung gegen bestehende Bewerbungen (#317)
        import re as _re
        apps = db.get_applications()

        # 1. URL-basierte Prüfung (stärkster Indikator)
        if url:
            url_norm = url.lower().rstrip("/")
            for app in apps:
                app_url = (app.get("url") or "").lower().rstrip("/")
                if app_url and app_url == url_norm:
                    return {
                        "warnung": "duplikat_bewerbung",
                        "nachricht": (
                            f"Exaktes URL-Duplikat: Bewerbung {app['id'][:8]} bei "
                            f"{app.get('company')} hat dieselbe URL "
                            f"(Status: {app.get('status', 'unbekannt')}). "
                            "Die Stelle wurde NICHT angelegt."
                        ),
                        "existing_application_id": app["id"][:8],
                        "trotzdem_anlegen": False,
                    }

        # 2. Firma+Titel Fuzzy-Match
        firma_lower = firma.lower()
        titel_lower = titel.lower()
        titel_words = set(titel_lower.split())
        for app in apps:
            app_company = (app.get("company") or "").lower()
            app_title = (app.get("title") or "").lower()
            # Firma-Match (fuzzy: Teilstring in beide Richtungen)
            if firma_lower in app_company or app_company in firma_lower:
                # Titel-Ähnlichkeit: mindestens 2 gemeinsame Wörter
                app_words = set(app_title.split())
                overlap = titel_words & app_words
                if len(overlap) >= min(2, len(titel_words)):
                    return {
                        "warnung": "duplikat_bewerbung",
                        "nachricht": (
                            f"Mögliches Duplikat: Bewerbung {app['id'][:8]} bei "
                            f"{app.get('company')} bereits vorhanden "
                            f"(Status: {app.get('status', 'unbekannt')}, "
                            f"Titel: '{app.get('title')}'). "
                            "Die Stelle wurde NICHT angelegt. "
                            "Falls es sich um eine andere Stelle handelt, "
                            "verwende einen deutlich abweichenden Titel."
                        ),
                        "existing_application_id": app["id"][:8],
                        "trotzdem_anlegen": False,
                    }

        # Cross-source duplicate detection (#222): Check if similar stelle exists
        norm_key = _re.sub(r'[^a-z0-9]', '', f"{firma}{titel}".lower())
        all_active = db.get_active_jobs(exclude_applied=False)
        for existing in all_active:
            exist_key = _re.sub(r'[^a-z0-9]', '', f"{existing.get('company','')}{existing.get('title','')}".lower())
            if norm_key == exist_key and existing["hash"] != job_hash:
                return {
                    "warnung": "duplikat_erkannt",
                    "nachricht": f"Aehnliche Stelle existiert bereits: '{existing['title']}' bei {existing['company']} "
                                 f"(Quelle: {existing.get('source', 'unbekannt')}, Hash: {existing['hash']}). "
                                 "Falls du die Stelle trotzdem anlegen moechtest, aendere den Titel leicht ab.",
                    "existing_hash": existing["hash"],
                }

        criteria = db.get_search_criteria()
        job = {
            "hash": job_hash,
            "title": titel,
            "company": firma,
            "url": url,
            "location": ort,
            "description": beschreibung,
            "source": quelle,
            "remote_level": remote,
            "employment_type": stellenart,
        }

        # Score
        job["score"] = calculate_score(job, criteria)

        # Extract/estimate salary
        text = f"{beschreibung} {titel}"
        s_min, s_max, s_type = extract_salary_from_text(text)
        if s_min:
            job["salary_min"] = s_min
            job["salary_max"] = s_max
            job["salary_type"] = s_type
            job["salary_estimated"] = 0
        else:
            s_min, s_max, s_type = estimate_salary(titel, stellenart, ort)
            job["salary_min"] = s_min
            job["salary_max"] = s_max
            job["salary_type"] = s_type
            job["salary_estimated"] = 1

        # Geocoding (#167): Entfernung berechnen wenn Standort bekannt
        if ort:
            try:
                from ..services.geocoding_service import get_user_coordinates, geocode_and_calculate_distance
                user_coords = get_user_coordinates(db)
                if user_coords:
                    dist = geocode_and_calculate_distance(ort, user_coords[0], user_coords[1])
                    if dist is not None:
                        job["distance_km"] = dist
            except Exception:
                pass

        db.save_jobs([job])

        result = {
            "status": "angelegt",
            "id": job_hash[:8],
            "hash": job_hash,
            "score": job["score"],
            "nachricht": f"Stelle '{titel}' bei {firma} angelegt (Score: {job['score']}, Quelle: {quelle}). "
                         f"Bewerte mit stelle_bewerten('{job_hash[:8]}', 'passt'/'passt_nicht').",
        }
        if job.get("distance_km"):
            result["entfernung_km"] = job["distance_km"]
        # #436: Warnung wenn URL auf Suchergebnis-Seite zeigt
        from ..job_scraper import is_search_result_url
        if url and is_search_result_url(url):
            result["url_warnung"] = (
                "Die angegebene URL zeigt auf eine Suchergebnis-Seite, nicht auf die "
                "konkrete Stellenanzeige. Die Stelle wurde trotzdem angelegt, aber der "
                "Link wird zur Such-Seite zurueckfuehren. Falls moeglich die Detail-URL "
                "der Stellenanzeige statt der Suchergebnis-URL nutzen."
            )
        return result

    @mcp.tool()
    def fit_analyse(job_hash: str) -> dict:
        """Detaillierte Passungsanalyse für eine bestimmte Stelle.

        Zeigt welche Keywords matchen, was fehlt, und gibt eine Risikobewertung.

        Args:
            job_hash: Hash der Stelle (von stellen_anzeigen)
        """
        from ..job_scraper import fit_analyse as _fit_analyse
        job_dict = db.get_job(job_hash)
        if not job_dict:
            return {"fehler": "Stelle nicht gefunden. Prüfe den Hash mit stellen_anzeigen()."}
        criteria = db.get_search_criteria()
        # Enrich criteria with profile skills and salary preferences for better fit analysis
        profile = db.get_profile()
        if profile:
            skills = profile.get("skills", [])
            criteria["_profile_skills"] = [s.get("name", "").lower() for s in skills if s.get("name")]
            # #305: Education für Hochschulabschluss-Erkennung
            criteria["_profile_education"] = profile.get("education", [])
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
        # #436: Warne wenn URL nur auf Suchergebnis-Seite zeigt
        if job_dict.get("is_search_url"):
            result["url_warnung"] = (
                "URL zeigt auf eine Suchergebnis-Seite, nicht auf die konkrete "
                "Stellenanzeige. Die Stelle muss manuell auf dem Portal gesucht werden."
            )
        elif result["url"]:
            from ..job_scraper import is_search_result_url
            if is_search_result_url(result["url"]):
                result["url_warnung"] = (
                    "URL zeigt auf eine Suchergebnis-Seite. "
                    "Stelle manuell auf dem Portal suchen."
                )
        if job_dict.get("veroeffentlicht_am"):
            result["veroeffentlicht_am"] = job_dict["veroeffentlicht_am"]
        return result

    @mcp.tool()
    def stelle_bearbeiten(
        job_hash: str,
        titel: str = "",
        firma: str = "",
        ort: str = "",
        beschreibung: str = "",
    ) -> dict:
        """Aktualisiert Felder einer bestehenden Stelle (#446).

        Nutze dies, um eine gescrapte oder manuell angelegte Stelle
        nachtraeglich zu korrigieren oder zu verfeinern — z.B. wenn aus einer
        E-Mail eine ausfuehrlichere Beschreibung hervorgeht oder die
        Ortsangabe prezisiert werden muss.

        Nur angegebene Felder werden geaendert. Leere Strings bleiben unveraendert.

        Args:
            job_hash: Hash der Stelle (aus stellen_anzeigen)
            titel: Neuer Stellentitel
            firma: Neuer Firmenname
            ort: Neuer Arbeitsort
            beschreibung: Neue Stellenbeschreibung
        """
        job = db.get_job(job_hash)
        if not job:
            return {"fehler": "Stelle nicht gefunden. Pruefe den Hash mit stellen_anzeigen()."}

        updates: dict = {}
        if titel:
            updates["title"] = titel
        if firma:
            updates["company"] = firma
        if ort:
            updates["location"] = ort
        if beschreibung:
            updates["description"] = beschreibung

        if not updates:
            return {"fehler": "Keine Aenderungen angegeben."}

        db.update_job(job_hash, updates)
        return {
            "status": "aktualisiert",
            "job_hash": job_hash,
            "geaenderte_felder": list(updates.keys()),
            "nachricht": (
                f"Stelle '{updates.get('title') or job.get('title', '')}' "
                f"bei {updates.get('company') or job.get('company', '')} aktualisiert."
            ),
        }

    @mcp.tool()
    def scraper_diagnose(
        scraper_name: str = "",
        aktion: str = "status"
    ) -> dict:
        """Zeigt den Gesundheitszustand aller Scraper oder reaktiviert einen deaktivierten Scraper (#432).

        Args:
            scraper_name: Name eines bestimmten Scrapers (z.B. 'stepstone', 'indeed'). Leer = alle anzeigen.
            aktion: 'status' = Gesundheitsdaten anzeigen, 'reaktivieren' = deaktivierten Scraper wieder aktivieren.
        """
        health = db.get_scraper_health()
        if not health:
            return {
                "status": "leer",
                "nachricht": "Keine Scraper-Daten vorhanden. Starte zuerst eine Jobsuche."
            }

        if aktion == "reaktivieren" and scraper_name:
            entry = next((h for h in health if h["scraper_name"] == scraper_name), None)
            if not entry:
                return {"fehler": f"Scraper '{scraper_name}' nicht gefunden."}
            db.toggle_scraper(scraper_name, True)
            return {
                "status": "reaktiviert",
                "scraper": scraper_name,
                "nachricht": f"Scraper '{scraper_name}' wurde reaktiviert und wird bei der naechsten Suche wieder verwendet."
            }

        if scraper_name:
            health = [h for h in health if h["scraper_name"] == scraper_name]
            if not health:
                return {"fehler": f"Scraper '{scraper_name}' nicht gefunden."}

        scrapers = []
        for h in health:
            success_rate = round(h["total_successes"] / h["total_runs"] * 100) if h["total_runs"] else 0
            scrapers.append({
                "name": h["scraper_name"],
                "aktiv": bool(h["is_active"]),
                "letzter_lauf": h.get("last_run"),
                "letzter_erfolg": h.get("last_success"),
                "fehler_serie": h["consecutive_failures"],
                "erfolgsrate": f"{success_rate}%",
                "laeufe_gesamt": h["total_runs"],
                "durchschn_zeit_s": round(h["avg_time_s"], 1),
                "letzter_fehler": h.get("last_error"),
            })

        return {
            "status": "ok",
            "scraper_anzahl": len(scrapers),
            "scrapers": scrapers,
        }
