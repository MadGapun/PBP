"""Jobsuche und Stellenverwaltung — 9 Tools (#446: stelle_bearbeiten, #432: scraper_diagnose)."""

import threading

# #488: Quellen, die NICHT automatisch laufen — Claude soll den User
# VOR dem Start darueber informieren, damit er nicht 10 Minuten auf
# stumme Timeouts wartet. Begruendung siehe SOURCE_REGISTRY (veraltet/
# langsam/Claude-in-Chrome).
_MANUAL_SOURCES = {
    "linkedin": "LinkedIn (automatisch deaktiviert, #159) — nutze jobspy_linkedin oder Claude-in-Chrome",
    "xing": "XING (automatisch deaktiviert, #107) — nutze Claude-in-Chrome",
    "stepstone": "StepStone (Bot-Detection, #315) — nutze google_jobs_url oder Claude-in-Chrome",
    "indeed": "Indeed (haeufig Timeout) — nutze jobspy_indeed",
    "monster": "Monster (instabil) — nutze Claude-in-Chrome",
    "google_jobs": "Google Jobs (#501) — google_jobs_url aufrufen und in Chrome-Extension oeffnen",
}


def register(mcp, db, logger):
    """Registriert Jobsuche-Tools."""
    from . import ki_gate, time_tool

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

        HINWEIS #488: Wenn aktive Quellen dabei sind, die nur ueber
        Claude-in-Chrome laufen (LinkedIn, StepStone, XING, Indeed,
        Monster, Google Jobs), meldet dieses Tool sie im Feld
        `manuelle_quellen` zurueck UND ueberspringt sie im
        Hintergrund-Job — statt auf stumme Timeouts zu laufen. Claude
        soll den User vor dem Start ueber diese Quellen informieren und
        ihm empfehlen, sie via Chrome-Extension anzusteuern.

        Args:
            keywords: Suchbegriffe (Standard: aus Profil)
            quellen: Welche Portale durchsuchen (Standard: alle aktiven)
            nur_remote: Nur Remote-Stellen
            max_entfernung_km: Maximale Entfernung in km (0 = kein Limit)
        """
        # #425: KI-Gate. Dashboard-Button bleibt unabhaengig nutzbar.
        gate = ki_gate(db, "jobsuche")
        if gate is not None:
            gate["alternative"] = (
                "Dashboard -> Stellen -> 'Jetzt suchen' laeuft unabhaengig "
                "vom KI-Toggle und nutzt deine aktiven Quellen."
            )
            return gate

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

        # #488: Manuelle/deprecated Quellen rausfiltern und separat melden.
        manuelle = [q for q in quellen if q in _MANUAL_SOURCES]
        auto_quellen = [q for q in quellen if q not in _MANUAL_SOURCES]
        manuelle_info = {q: _MANUAL_SOURCES[q] for q in manuelle}

        if not auto_quellen:
            return {
                "status": "nur_manuelle_quellen",
                "manuelle_quellen": manuelle_info,
                "nachricht": (
                    "Alle ausgewaehlten Quellen laufen nur ueber Claude-in-Chrome "
                    "oder sind deprecated — es gibt nichts zu automatisieren. "
                    "Siehe manuelle_quellen fuer den jeweiligen Ersatzweg."
                ),
            }
        quellen = auto_quellen

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

        nachricht = (
            f"Jobsuche laeuft im Hintergrund auf {len(params['quellen'])} Portalen. "
            f"Das dauert 5-10 Minuten — du musst jetzt NICHT warten. "
            f"Die Status-Badge in der Sidebar zeigt den Fortschritt. "
            f"Wenn du spaeter prueft willst: jobsuche_status('{job_id}'). "
            f"Wenn fertig: stellen_anzeigen()."
        )
        result = {
            "job_id": job_id,
            "status": "gestartet",
            "nachricht": nachricht,
        }
        if manuelle_info:
            result["manuelle_quellen"] = manuelle_info
            result["hinweis"] = (
                "Zusaetzlich muesstest du fuer folgende manuelle Quellen "
                "Claude-in-Chrome oder die jeweiligen Ersatzwerkzeuge nutzen — "
                "sie sind im Hintergrund-Job NICHT enthalten."
            )
        return result

    @mcp.tool()
    def jobsuche_status(job_id: str) -> dict:
        """Prüft den Fortschritt einer laufenden Jobsuche.

        Args:
            job_id: Job-ID von jobsuche_starten()
        """
        job = db.get_background_job(job_id)
        if job is None:
            return {"fehler": "Unbekannte Job-ID"}
        # v1.6.5 (#549): bereinigung wurde sowohl in `ergebnis.bereinigung`
        # als auch top-level zurueckgegeben — doppelt. Wir extrahieren sie
        # einmalig auf top-level und entfernen sie aus `ergebnis`.
        ergebnis = None
        bereinigung = None
        if job["status"] == "fertig" and isinstance(job.get("result"), dict):
            ergebnis = dict(job["result"])
            bereinigung = ergebnis.pop("bereinigung", None)
        elif job["status"] == "fertig":
            ergebnis = job["result"]
        result = {
            "status": job["status"],
            "fortschritt": f"{job['progress']}%",
            "nachricht": job["message"],
            "ergebnis": ergebnis,
        }
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

    def _apply_dismiss_with_lifecycle(job_hash: str, reason_list: list[str],
                                       collect_hints: bool = True,
                                       skip_auto_adjust: bool = False) -> dict:
        """Wendet 'aussortieren' auf eine Stelle an mit voller PBP-Lifecycle-Logik.

        Geht durch alle Hooks: dismiss_counts, blacklist-hint, auto-adjust-scoring,
        dismiss_reasons-Statistik. Wird von stelle_bewerten UND von
        stellen_bulk_bewerten aufgerufen, damit Audit/Lerneffekt/Statistik in
        beiden Wegen identisch durchlaufen (#514: Anti-DB-Bypass-Pattern).

        Args:
            job_hash: Hash der Stelle
            reason_list: bereits validierte/normalisierte Gruende
            collect_hints: bei Bulk auf False setzen — Tipps werden dann nur
                in der Aggregat-Antwort summiert, nicht pro Einzelaufruf
            skip_auto_adjust: v1.6.5 (#558) — Bulk-Path uebernimmt den
                Auto-Adjust selbst (einmalig am Ende). Verhindert dass jeder
                der 100 Einzelaufrufe das Scoring weiter eskaliert (Drift).
        """
        import json as _json
        reason_str = _json.dumps(reason_list, ensure_ascii=False) if len(reason_list) > 1 else reason_list[0]

        # #168: Duplikat-Erkennung
        dup_info = None
        if "duplikat" in reason_list:
            dup_info = _detect_duplicate(job_hash)

        db.dismiss_job(job_hash, reason_str)

        # Track rejection counts for learning (#66)
        counts = db.get_setting("dismiss_counts", {})
        hints = []
        for g in reason_list:
            normalized = g.lower().strip()
            counts[normalized] = counts.get(normalized, 0) + 1

            # Suggest scoring adjustments (#169) when patterns are strong
            if collect_hints and counts.get(normalized, 0) >= 3:
                if normalized == "zu_weit_entfernt":
                    hints.append("Tipp: Passe den Entfernungs-Malus im Scoring-Regler an (scoring_konfigurieren).")
                elif normalized == "gehalt_zu_niedrig":
                    hints.append("Tipp: Passe den Gehalts-Regler im Scoring an (scoring_konfigurieren).")
                elif normalized in ("zeitarbeit", "befristet"):
                    hints.append(f"Tipp: Setze '{g}' im Scoring-Regler auf 'Komplett Ignorieren' (scoring_konfigurieren).")
                elif normalized == "firma_uninteressant":
                    job = db.get_job(job_hash)
                    if job:
                        hints.append(
                            f"Tipp: Moechtest du '{job.get('company', '')}' auf die Blacklist setzen? "
                            f"Nutze blacklist_verwalten('hinzufuegen', 'firma', '{job.get('company', '')}')."
                        )

        db.set_setting("dismiss_counts", counts)
        db.increment_dismiss_reason_usage(reason_list)

        # #110: Lernender Score — automatische Scoring-Anpassungen bei starken Mustern.
        # v1.6.5 (#558): Bei Bulk wird das einmalig am Ende ausgefuehrt, nicht
        # pro Einzelaufruf. Sonst eskaliert (count-5)*0.5 mit jedem Job und
        # treibt den Score-Malus immer weiter ins Negative ("Score-Drift").
        auto_adjustments = []
        if not skip_auto_adjust:
            for g in reason_list:
                normalized = g.lower().strip()
                cnt = counts.get(normalized, 0)
                if cnt >= 5:
                    _auto = _auto_adjust_scoring(db, normalized, cnt)
                    if _auto:
                        auto_adjustments.append(_auto)
            if collect_hints and auto_adjustments:
                hints.append("Scoring wurde automatisch angepasst: " + "; ".join(auto_adjustments))

        return {
            "counts": counts,
            "hints": hints,
            "auto_adjustments": auto_adjustments,
            "duplikat_info": dup_info,
        }

    def _normalize_reason_list(grund: str = "", gruende: list[str] = None) -> list[str]:
        """Normalisiert Eingabe-Gruende auf erlaubte Werte (#302)."""
        raw_reasons = [_normalize_dismiss_reason(r) for r in (gruende or ([grund] if grund else []))]
        return list(dict.fromkeys(
            r if r in ABLEHNUNGSGRUENDE else "sonstiges" for r in raw_reasons
        ))

    @mcp.tool()
    @time_tool(logger, "stelle_bewerten")
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

        FUER MEHRERE STELLEN AUF EINMAL: Nutze 'stellen_bulk_bewerten' mit
        Filtern wie min_score, titel_enthaelt_nicht, beschreibung_enthaelt_nicht.
        Spart Tokens und respektiert die PBP-Lifecycle-Logik (#514).

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
        if bewertung == "passt_nicht":
            reason_list = _normalize_reason_list(grund, gruende)
            if not reason_list:
                return {
                    "fehler": "Mindestens ein Ablehnungsgrund ist erforderlich.",
                    "verfuegbare_gruende": ABLEHNUNGSGRUENDE,
                }

            ctx = _apply_dismiss_with_lifecycle(job_hash, reason_list, collect_hints=True)
            counts = ctx["counts"]
            hints = ctx["hints"]
            dup_info = ctx["duplikat_info"]

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
            # v1.7.0-beta.28 (#594 Stufe 3): LLM-Correction-Loop. Wenn die
            # Stelle vorher von der LLM via Auto-Aussortierung weggeraeumt
            # wurde (`dismiss_reason='profil_match_negativ'`), dann ist das
            # eine Korrektur durch den User — Trainingsmaterial fuer die
            # adaptive Prompts.
            try:
                from ..tools.jobs import _resolve  # type: ignore
            except Exception:
                _resolve = None
            try:
                conn = db.connect()
                resolved_hash = db.resolve_job_hash(job_hash)
                if resolved_hash:
                    row = conn.execute(
                        "SELECT title, company, dismiss_reason FROM jobs "
                        "WHERE hash=?", (resolved_hash,)
                    ).fetchone()
                    if row and (row["dismiss_reason"] or "") == "profil_match_negativ":
                        # User korrigiert die LLM-Entscheidung
                        try:
                            db.add_activity_event({
                                "event_type": "llm_correction",
                                "entity_type": "job",
                                "entity_id": resolved_hash,
                                "page": "stellen",
                                "action": "user_overrides_dismiss",
                                "metadata": {
                                    "title": row["title"],
                                    "company": row["company"],
                                    "previous_dismiss_reason":
                                        row["dismiss_reason"],
                                },
                                "learning_enabled":
                                    db.is_learning_enabled(),
                            })
                        except Exception:
                            pass
            except Exception:
                pass
            db.restore_job(job_hash)
            return {"status": "als_passend_markiert"}
        return {"fehler": "Ungültige Bewertung. Nutze 'passt' oder 'passt_nicht'."}

    @mcp.tool()
    @time_tool(logger, "stellen_bulk_bewerten")
    def stellen_bulk_bewerten(
        bewertung: str,
        grund: str = "",
        gruende: list[str] = None,
        dry_run: bool = True,
        # Filter (alle optional, kombinierbar mit AND-Logik)
        min_score: int = None,
        max_score: int = None,
        min_alter_tage: int = None,
        max_alter_tage: int = None,
        quelle: str = "",
        firma: str = "",
        titel_enthaelt: list[str] = None,
        titel_enthaelt_nicht: list[str] = None,
        beschreibung_enthaelt_nicht: list[str] = None,
        max_treffer: int = 0,
    ) -> dict:
        """Bewertet mehrere aktive Stellen auf einmal anhand von Filtern (#514).

        ANTI-DB-BYPASS: Nutze dieses Tool fuer das Aussortieren grosser Mengen
        von Stellen. NIEMALS direkt in die SQLite-Datei schreiben — die
        PBP-Logik (Audit-Log, Lerneffekte, Auto-Adjust-Scoring,
        dismiss_reasons-Statistik) wird hier durchlaufen, bei direkten
        DB-Writes nicht.

        SICHERHEITS-DEFAULT: dry_run=True. Erst Vorschau (Anzahl Treffer +
        erste 10 Beispiele), dann mit dry_run=False ausfuehren. Das ist
        bewusst nicht verhandelbar — der Filter trifft sonst zu viel.

        REAL-CASE: Bei einer Suche kommen 500 Stellen, davon 200 falsches
        Fachgebiet. Anstatt 200 Einzelaufrufe von stelle_bewerten:

            stellen_bulk_bewerten(
                bewertung='passt_nicht',
                gruende=['falsches_fachgebiet'],
                titel_enthaelt_nicht=['Pflege', 'Vertrieb'],
                dry_run=True  # erst pruefen!
            )

        Args:
            bewertung: 'passt' oder 'passt_nicht'
            grund / gruende: wie bei stelle_bewerten. ABLEHNUNGSGRUENDE-Liste
                gilt analog. KI darf KEINE eigenen Gruende erfinden.
            dry_run: bei True (Default) wird NICHTS veraendert, nur Preview.
                Bei False: alle Treffer werden tatsaechlich bewertet.
            min_score / max_score: Score-Bereich (None = unbegrenzt)
            min_alter_tage / max_alter_tage: relativ zu found_at
            quelle: Quelle als String (z.B. 'bundesagentur')
            firma: Firmenname (case-insensitive Substring-Match)
            titel_enthaelt: AND-Liste — Titel muss ALLE Begriffe enthalten
            titel_enthaelt_nicht: NOR-Liste — Titel darf KEINEN davon enthalten
            beschreibung_enthaelt_nicht: NOR-Liste fuer Beschreibung —
                Hauptwerkzeug fuer Fachgebiets-Aussortierung
            max_treffer: harter Cap auf die Anzahl Treffer (0 = kein Limit).
                Sinnvoll wenn man nicht sicher ist wie weit der Filter trifft.

        Returns:
            dry_run=True:
                {"dry_run": True, "anzahl_treffer": N, "vorschau": [...10 Stellen...]}
            dry_run=False:
                {"dry_run": False, "bearbeitet": N, "ablehnungs_statistik": {...},
                 "hinweise": [...], "stichprobe_bearbeitet": [...erste 5...]}
        """
        from datetime import datetime, timedelta

        # 1) Bewertung validieren
        if bewertung not in ("passt", "passt_nicht"):
            return {"fehler": "Ungueltige Bewertung. Nutze 'passt' oder 'passt_nicht'."}

        reason_list: list[str] = []
        if bewertung == "passt_nicht":
            reason_list = _normalize_reason_list(grund, gruende)
            if not reason_list:
                return {
                    "fehler": "Mindestens ein Ablehnungsgrund ist erforderlich.",
                    "verfuegbare_gruende": ABLEHNUNGSGRUENDE,
                }

        # 2) Kandidaten laden — semantisch unterschiedlicher Pool je Aktion:
        #    - 'passt_nicht' (Aussortieren) wirkt auf aktuell aktive Stellen
        #    - 'passt' (Restore) wirkt auf bereits dismissed Stellen
        if bewertung == "passt":
            candidates = db.get_dismissed_jobs()
            # Anschliessend manuell auf min_score / quelle filtern
            # v1.6.5 (#557): Partial-Match analog get_active_jobs
            if quelle:
                q_lc = quelle.lower()
                if "_" in quelle or quelle in ("manuell", "google_jobs"):
                    candidates = [j for j in candidates
                                  if (j.get("source") or "").lower() == q_lc]
                else:
                    candidates = [j for j in candidates
                                  if q_lc in (j.get("source") or "").lower()]
            if min_score is not None and min_score > 0:
                candidates = [j for j in candidates if int(j.get("score") or 0) >= min_score]
        else:
            db_filters = {}
            if quelle:
                db_filters["source"] = quelle
            if min_score is not None and min_score > 0:
                db_filters["min_score"] = min_score
            # v1.6.5 (#556): Gleiche aktiv-Definition wie stellen_anzeigen —
            # Blacklist-gefilterte Stellen sollen nicht doppelt von einer
            # Bulk-Aussortierung beruehrt werden.
            candidates = db.get_active_jobs(
                filters=db_filters or None,
                exclude_blacklisted=True,
            )

        # 3) In-Memory-Filter fuer alles was die DB-API nicht direkt anbietet
        now = datetime.now()
        firma_lc = (firma or "").lower().strip()
        title_must = [t.lower() for t in (titel_enthaelt or []) if t]
        title_must_not = [t.lower() for t in (titel_enthaelt_nicht or []) if t]
        desc_must_not = [t.lower() for t in (beschreibung_enthaelt_nicht or []) if t]

        def _matches(job: dict) -> bool:
            score = int(job.get("score") or 0)
            if max_score is not None and score > max_score:
                return False
            # Alter
            found_at = job.get("found_at") or ""
            if min_alter_tage is not None or max_alter_tage is not None:
                if not found_at:
                    return False
                try:
                    found_dt = datetime.fromisoformat(found_at.replace("Z", "+00:00").split("+")[0])
                except (ValueError, TypeError):
                    return False
                age_days = (now - found_dt).days
                if min_alter_tage is not None and age_days < min_alter_tage:
                    return False
                if max_alter_tage is not None and age_days > max_alter_tage:
                    return False
            # Firma
            if firma_lc and firma_lc not in (job.get("company") or "").lower():
                return False
            # Titel-Filter
            title_lc = (job.get("title") or "").lower()
            if title_must and not all(t in title_lc for t in title_must):
                return False
            if title_must_not and any(t in title_lc for t in title_must_not):
                return False
            # Beschreibung
            if desc_must_not:
                desc_lc = (job.get("description") or "").lower()
                if any(t in desc_lc for t in desc_must_not):
                    return False
            return True

        matched = [j for j in candidates if _matches(j)]
        if max_treffer and max_treffer > 0:
            matched = matched[:max_treffer]

        # 4) Dry-Run: nur Vorschau zurueck
        if dry_run:
            preview = [
                {
                    "hash": (j.get("hash") or "")[:12],
                    "title": j.get("title"),
                    "company": j.get("company"),
                    "score": j.get("score"),
                    "source": j.get("source"),
                    "found_at": (j.get("found_at") or "")[:10],
                }
                for j in matched[:10]
            ]
            return {
                "dry_run": True,
                "bewertung": bewertung,
                "gruende": reason_list if bewertung == "passt_nicht" else None,
                "anzahl_treffer": len(matched),
                "vorschau": preview,
                "hinweis": (
                    f"{len(matched)} Stellen wuerden bewertet werden. "
                    "Pruefe die Vorschau und rufe das Tool erneut mit dry_run=False auf, "
                    "um die Aenderung tatsaechlich anzuwenden."
                ),
            }

        # 5) Tatsaechliche Anwendung — durch die echte Lifecycle-Logik
        if not matched:
            return {
                "dry_run": False,
                "bearbeitet": 0,
                "hinweis": "Kein Treffer mit den gegebenen Filtern.",
            }

        bearbeitet = 0
        last_counts: dict = {}
        bulk_auto_adjustments: list[str] = []
        sample_processed: list[dict] = []
        for j in matched:
            job_hash = j.get("hash")
            if not job_hash:
                continue
            try:
                if bewertung == "passt_nicht":
                    # v1.6.5 (#558): skip_auto_adjust=True — wir triggern den
                    # Lerneffekt nur einmal am Ende, mit dem Final-Count.
                    ctx = _apply_dismiss_with_lifecycle(
                        job_hash, reason_list,
                        collect_hints=False,
                        skip_auto_adjust=True,
                    )
                    last_counts = ctx["counts"]
                else:  # passt
                    db.restore_job(job_hash)
                bearbeitet += 1
                if len(sample_processed) < 5:
                    sample_processed.append({
                        "hash": (job_hash or "")[:12],
                        "title": j.get("title"),
                        "company": j.get("company"),
                    })
            except Exception as exc:
                logger.warning("Bulk-Bewertung fuer %s fehlgeschlagen: %s", job_hash, exc)

        # v1.6.5 (#558): EINMALIG nach der Bulk-Schleife den Auto-Adjust ausloesen.
        # Verhindert Score-Drift (s. _apply_dismiss_with_lifecycle Doc).
        if bewertung == "passt_nicht" and bearbeitet > 0:
            for g in reason_list:
                normalized = g.lower().strip()
                cnt = last_counts.get(normalized, 0)
                if cnt >= 5:
                    _auto = _auto_adjust_scoring(db, normalized, cnt)
                    if _auto:
                        bulk_auto_adjustments.append(_auto)

        # Aggregierte Hinweise — nur einmal, nicht pro Eintrag
        hinweise = []
        if bulk_auto_adjustments:
            unique_adj = list(dict.fromkeys(bulk_auto_adjustments))
            hinweise.append(
                f"Scoring wurde automatisch angepasst "
                f"({len(unique_adj)} Aenderung(en)): " + "; ".join(unique_adj[:5])
            )
            # v1.6.5 (#558): Klare Drift-Warnung mit Hinweis auf
            # Score-Recompute — sonst wundert man sich ueber niedrige Scores.
            hinweise.append(
                "Hinweis: Bestehende Stellen-Scores wurden nicht neu berechnet. "
                "Falls Du danach in stellen_anzeigen niedrigere Scores siehst, "
                "ist das die Folge der Scoring-Anpassung — fuer einen "
                "konsistenten Stand 'fit_analyse' auf einzelne Stellen neu laufen lassen."
            )

        result = {
            "dry_run": False,
            "bewertung": bewertung,
            "gruende": reason_list if bewertung == "passt_nicht" else None,
            "bearbeitet": bearbeitet,
            "stichprobe_bearbeitet": sample_processed,
        }
        if last_counts:
            result["ablehnungs_statistik"] = {
                k: v for k, v in sorted(last_counts.items(), key=lambda x: -x[1])[:5]
            }
        if hinweise:
            result["hinweise"] = hinweise
        return result

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
    def google_jobs_url(
        keyword: str,
        zeitraum: str = "woche",
        ort: str = "",
    ) -> dict:
        """Baut eine Google-Jobs-URL fuer Chrome-in-Claude (#501, #573).

        Google Jobs (`udm=8`) ist der groesste Aggregator in DE und
        indexiert u.a. StepStone-Stellen. Ein direkter HTTP-Abruf wird
        von Google zuverlaessig blockiert, ein eingeloggter Chrome-Tab
        mit Claude-in-Chrome funktioniert aber stabil.

        Workflow (v1.7.0-beta.14, #573):
        1. `google_jobs_url(keyword="PLM", ort="Hamburg")` aufrufen
        2. URL in Chrome mit Claude-in-Chrome oeffnen
        3. Mit dem mitgelieferten `extraction_js` strukturierte Job-Daten
           via `javascript_tool()` aus dem DOM ziehen (statt Rohtext-Parsing)
        4. Gefundene Stellen mit `stelle_manuell_anlegen()` uebernehmen

        Args:
            keyword: Suchbegriff (z.B. 'PLM Projektleiter').
            zeitraum: 'tag' | 'woche' | 'monat'. Default 'woche'.
            ort: Optionaler Ort (z.B. 'Hamburg'). Leer = Google nimmt
                 den Standort aus dem eingeloggten Google-Account.
        """
        if not keyword:
            return {"fehler": "keyword ist Pflichtfeld."}
        from ..job_scraper.google_jobs import build_google_jobs_url
        url = build_google_jobs_url(keyword, zeitraum=zeitraum, ort=ort or None)
        # v1.7.0-beta.14 (#573): JS-Snippet fuer DOM-Extraktion mitliefern.
        # Mehrere Selektor-Pfade probieren, weil Google die Klassen-Hashes
        # haeufig rotiert. Wenn keiner matcht, faellt der Aufrufer auf
        # get_page_text() + manuelles Parsen zurueck.
        extraction_js = """
(() => {
  // Google Jobs (udm=8) — DOM-Selektoren (Stand Mai 2026).
  // Klassen rotieren, daher mehrere Strategien.
  const cards = Array.from(document.querySelectorAll(
    '[data-ved][role="listitem"], li[data-ved], div.PwjeAc'
  ));
  const getText = (el, sel) => {
    if (!el) return '';
    const node = sel ? el.querySelector(sel) : el;
    return (node?.innerText || node?.textContent || '').trim();
  };
  const results = cards.slice(0, 30).map((el, idx) => {
    const titel = getText(el, '.PUpOsf, .BjJfJf, [role="heading"]');
    const firma = getText(el, '.a3jPc, .vNEEBe, .nJlQNd');
    const ort   = getText(el, '.tJ9zfc, .Qk80Jf');
    const link = el.querySelector('a[href]')?.href || '';
    return {
      idx, titel, firma, ort, link,
      _raw: el.innerText?.slice(0, 200),
    };
  }).filter((r) => r.titel || r.firma);
  return { count: results.length, jobs: results };
})()
""".strip()
        return {
            "url": url,
            "extraction_js": extraction_js,
            "hinweis": (
                "Oeffne diese URL in Chrome mit Claude-in-Chrome. Nutze dann "
                "javascript_tool() mit `extraction_js` um strukturierte "
                "Job-Daten direkt aus dem DOM zu ziehen — vermeidet "
                "Rohtext-Parsing. Pro Treffer: titel, firma, ort, link. "
                "Falls keine Treffer: Selektoren wurden von Google rotiert, "
                "Fallback ueber get_page_text()."
            ),
        }

    @mcp.tool()
    def scores_neu_berechnen(
        nur_aktive: bool = True,
        max_stellen: int = 0,
    ) -> dict:
        """Rechnet die Fit-Scores aller (aktiven) Stellen neu (#554, v1.6.9).

        Sinnvoll nach Aenderungen an:
        - Suchkriterien (`suchkriterien_setzen`/`suchkriterien_bearbeiten`)
        - Profil (relevante Skills, Wunsch-Gehalt, Standort)
        - Scoring-Regler (`scoring_konfigurieren`)
        - Geocoding-Cache (Standort-Aenderungen)

        Geht jede Stelle einmal durch `calculate_score()` und persistiert
        den neuen Wert via `db.update_job(hash, {"score": ...})`. Auto-
        Adjust-Hooks werden NICHT getriggert — das ist ein reiner Recompute.

        Args:
            nur_aktive: True (Standard) = nur is_active=1; False = auch aussortierte.
            max_stellen: 0 = unbegrenzt, sonst harter Cap (sinnvoll fuer Tests).
        """
        from ..job_scraper import calculate_score
        criteria = db.get_search_criteria()
        if nur_aktive:
            jobs = db.get_active_jobs()
        else:
            conn = db.connect()
            pid = db.get_active_profile_id()
            rows = conn.execute(
                "SELECT * FROM jobs WHERE (profile_id=? OR profile_id IS NULL)",
                (pid,)
            ).fetchall()
            jobs = [db._serialize_job_row(r) for r in rows]

        if max_stellen and max_stellen > 0:
            jobs = jobs[:max_stellen]

        recomputed = 0
        unchanged = 0
        deltas: list[int] = []
        for j in jobs:
            old_score = int(j.get("score") or 0)
            try:
                new_score = int(calculate_score(j, criteria))
            except Exception as e:
                logger.warning("Score-Recompute fuer %s fehlgeschlagen: %s",
                               j.get("hash"), e)
                continue
            if new_score != old_score:
                try:
                    db.update_job(j.get("hash"), {"score": new_score})
                    recomputed += 1
                    deltas.append(new_score - old_score)
                except Exception as e:
                    logger.warning("update_job fuer %s fehlgeschlagen: %s",
                                   j.get("hash"), e)
            else:
                unchanged += 1

        avg_delta = sum(deltas) / len(deltas) if deltas else 0
        return {
            "status": "fertig",
            "verarbeitet": len(jobs),
            "geaendert": recomputed,
            "unveraendert": unchanged,
            "durchschnittliche_aenderung": round(avg_delta, 1),
            "max_anstieg": max(deltas) if deltas else 0,
            "max_rueckgang": min(deltas) if deltas else 0,
        }

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

        # v1.7.0-beta.47 (#613): Wenn quelle="manuell" der Default ist
        # aber die URL klar auf eine bekannte Quelle zeigt, wird das
        # uebersteuert. Explizit gesetzte quelle bleibt unveraendert.
        if quelle == "manuell" and url:
            from ..services.url_to_source import detect_source_from_url
            detected = detect_source_from_url(url)
            if detected != "manuell":
                quelle = detected

        job_hash = stelle_hash(quelle, f"{firma} {titel}")

        # Check for duplicates (#219: nur echte DB-Treffer, nicht scope-Prefix)
        existing_job = db.get_job(job_hash)
        if existing_job:
            return {"fehler": f"Diese Stelle existiert bereits (Hash: {existing_job['hash']})."}

        # Duplikat-Pruefung (#317 + #471 + v1.6.9 #567: zweistufig)
        # Stufe A: laufende Bewerbung mit Titel-Match → blocken
        # Stufe B: identische AKTIVE Stelle → idempotent vorhandenen Hash zurueck
        # Stufe C: aussortierte/abgelehnte Eintraege blocken NICHT mehr
        from ..duplicate_detection import find_duplicate_job

        # v1.6.9 (#567): nur LAUFENDE Bewerbungen blocken — abgeschlossene
        # (abgelehnt/abgelaufen/zurueckgezogen/angenommen) sind kein Hindernis
        # fuer eine neue Bewerbung bei der gleichen Firma auf eine andere Stelle.
        TERMINAL_STATUSES = ("abgelehnt", "abgelaufen", "zurueckgezogen", "angenommen")
        all_apps = db.get_applications()
        running_apps = [a for a in all_apps
                        if (a.get("status") or "") not in TERMINAL_STATUSES]

        # Stufe A — laufende Bewerbung mit Titel-Match?
        app_hit = find_duplicate_job(firma, titel, url, running_apps)
        if app_hit:
            app = app_hit["job"]
            return {
                "warnung": "duplikat_bewerbung",
                "grund": app_hit["grund"],
                "nachricht": (
                    f"Moegliches Duplikat: laufende Bewerbung {app['id'][:8]} bei "
                    f"{app.get('company')} (Status: {app.get('status', 'unbekannt')}, "
                    f"Titel: '{app.get('title')}'). "
                    f"Match-Grund: {app_hit['grund']}"
                    + (f", gemeinsame Tokens: {app_hit.get('shared_tokens')}"
                       if app_hit.get("shared_tokens") else "")
                    + ". Die Stelle wurde NICHT angelegt. "
                    "Falls es sich tatsaechlich um eine andere Stelle handelt, "
                    "ergaenze den Titel eindeutig (z.B. Projekt- oder Team-Name) "
                    "oder nutze stelle_mergen(), falls eine frueher angelegte "
                    "Stelle die zweite Variante ersetzt."
                ),
                "existing_application_id": app["id"][:8],
                "shared_tokens": app_hit.get("shared_tokens"),
                "trotzdem_anlegen": False,
            }

        # Stufe B — identische AKTIVE Stelle (is_active=1) → idempotent
        # vorhandenen Hash zurueckgeben statt blocken. Aussortierte Stellen
        # blocken NICHT, weil sie schon mal aktiv abgelehnt wurden.
        active_jobs = db.get_active_jobs(exclude_applied=False)
        active_hit = find_duplicate_job(firma, titel, url, active_jobs)
        if active_hit and active_hit["job"].get("hash") != job_hash:
            existing = active_hit["job"]
            return {
                "warnung": "duplikat_aktive_stelle",
                "status": "bereits_vorhanden",
                "grund": active_hit["grund"],
                "nachricht": (
                    f"Identische aktive Stelle existiert bereits: "
                    f"'{existing.get('title')}' bei {existing.get('company')} "
                    f"(Quelle: {existing.get('source', 'unbekannt')}, "
                    f"Hash: {existing['hash']}). Es wird der vorhandene Hash "
                    "zurueckgegeben — kein Duplikat in der DB."
                ),
                "hash": existing["hash"],
                "existing_hash": existing["hash"],
                "shared_tokens": active_hit.get("shared_tokens"),
            }
        # Stufe C: alles andere (auch aussortierte Stellen bei gleicher Firma)
        # darf durchgehen.

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

    # === v1.7.0-beta.5: n:m + Stellen-Vergleich (#472, #580) ===

    @mcp.tool()
    def bewerbung_stelle_verknuepfen(
        bewerbung_id: str,
        stellen_hash: str,
        version_label: str = "",
        ist_primaer: bool = False,
    ) -> dict:
        """Verknuepft eine Bewerbung mit einer (zusaetzlichen) Stelle (#472).

        Use-Case: Eine Bewerbung kann sich auf MEHRERE Stellen-Versionen
        beziehen — z.B. wenn eine Firma die Stelle re-postet, oder wenn
        man sich gleichzeitig auf zwei verwandte Stellen bewirbt
        (Vermittler + Endkunde, oder Senior + Lead Variante).

        Args:
            bewerbung_id: ID der Bewerbung (mit oder ohne APP-Praefix).
            stellen_hash: Hash der Stelle (mit oder ohne JOB-Praefix).
            version_label: Optionale Bezeichnung (z.B. 'Senior-Variante',
                'Repost vom 15.05.', 'Endkunde-Sicht').
            ist_primaer: Wenn True, wird diese Verknuepfung als primaer
                gesetzt (alle anderen werden auf nicht-primaer gesetzt).
        """
        from ..services.typed_ids import strip_prefix
        bid = strip_prefix(bewerbung_id)
        jhash = strip_prefix(stellen_hash)
        try:
            link_id = db.link_application_to_job(
                bid, jhash, version_label=version_label,
                is_primary=ist_primaer
            )
        except Exception as e:
            return {"fehler": f"Verknuepfung fehlgeschlagen: {e}"}
        return {
            "status": "verknuepft",
            "link_id": link_id,
            "bewerbung_id": bewerbung_id,
            "stellen_hash": stellen_hash,
        }

    @mcp.tool()
    def bewerbung_stelle_entknuepfen(bewerbung_id: str, stellen_hash: str) -> dict:
        """Entfernt eine Stellen-Verknuepfung von einer Bewerbung."""
        from ..services.typed_ids import strip_prefix
        bid = strip_prefix(bewerbung_id)
        jhash = strip_prefix(stellen_hash)
        ok = db.unlink_application_job(bid, jhash)
        return {"status": "entfernt" if ok else "nicht_gefunden"}

    @mcp.tool()
    def bewerbung_stellen_anzeigen(bewerbung_id: str) -> dict:
        """Listet alle Stellen, die mit einer Bewerbung verknuepft sind (#472).

        Wenn die Bewerbung ein klassisches `applications.job_hash` hat,
        ist es als is_primary=True hier mit drin (durch Migration).
        """
        from ..services.typed_ids import strip_prefix
        bid = strip_prefix(bewerbung_id)
        jobs = db.get_jobs_for_application(bid)
        return {
            "bewerbung_id": bewerbung_id,
            "anzahl": len(jobs),
            "stellen": jobs,
        }

    @mcp.tool()
    def stellenbeschreibung_nachladen(stellen_hash: str) -> dict:
        """Holt die Beschreibung einer Stelle aus ihrer URL nach (v1.7.0-beta.44, #622).

        Wenn der Score einer Stelle unzuverlaessig wirkt weil die
        Beschreibung leer oder zu kurz ist, ruft dieses Tool die URL
        auf, parsed sie und schreibt die Beschreibung zurueck in die DB.

        Eine HTTP-GET pro Aufruf — bewusst nicht fuer Massen-Crawl
        gedacht. Fuer Bulk-Refetch nutzt PBP den Auto-Engine-Step
        `_run_auto_refetch_descriptions` (max 8 Stellen pro Lauf).

        Liefert {status, chars, preview} bei Erfolg, sonst
        {status: "fehler", grund}.
        """
        from ..services.typed_ids import strip_prefix
        from ..job_scraper import fetch_description_from_detail
        import httpx
        h = strip_prefix(stellen_hash)
        job = db.get_job(h)
        if not job:
            return {"status": "fehler", "grund": "Stelle nicht gefunden",
                    "stellen_hash": stellen_hash}
        url = (job.get("url") or "").strip()
        if not url:
            return {"status": "fehler",
                    "grund": "Stelle hat keine URL — bitte ueber stelle_bearbeiten manuell pflegen"}
        try:
            with httpx.Client(follow_redirects=True, timeout=15,
                              headers={"User-Agent": "PBP/1.7 (+github.com/MadGapun/PBP)"}) as client:
                text = fetch_description_from_detail(url, client, timeout=15)
        except Exception as exc:
            return {"status": "fehler", "grund": f"HTTP-Fehler: {exc}"}
        if not text or len(text) < 50:
            return {"status": "fehler",
                    "grund": "Keine brauchbare Beschreibung gefunden — Login-Wall oder Bot-Block?",
                    "url": url, "got_chars": len(text or "")}
        db.update_job(h, {"description": text})
        return {"status": "ok", "chars": len(text), "preview": text[:200]}

    @mcp.tool()
    def stelle_vergleichen(hash_a: str, hash_b: str) -> dict:
        """Vergleicht zwei Stellen strukturiert (#580).

        Liefert eine Gegenueberstellung von Skills (gemeinsam / nur A /
        nur B), Gehalt, Standort, Stellenart, Score und
        Beschreibungs-Laenge. Sehr hilfreich um zu erkennen ob zwei
        Stellen wirklich verschieden sind oder nur Schreibvarianten.
        """
        from ..services.typed_ids import strip_prefix
        ha = strip_prefix(hash_a)
        hb = strip_prefix(hash_b)
        ja = db.get_job(ha)
        jb = db.get_job(hb)
        if not ja or not jb:
            return {"fehler": "Mindestens eine der Stellen wurde nicht gefunden."}

        def _tokens(text):
            import re
            return set(re.findall(r"[a-zäöüß0-9]+", (text or "").lower())) - {
                "und", "der", "die", "das", "ein", "eine", "fuer", "im", "mit",
                "bei", "von", "zu", "in", "an", "the", "and", "for", "with",
            }

        title_a = _tokens(ja.get("title", ""))
        title_b = _tokens(jb.get("title", ""))
        desc_a = _tokens(ja.get("description", ""))
        desc_b = _tokens(jb.get("description", ""))

        common_title = title_a & title_b
        only_a_title = title_a - title_b
        only_b_title = title_b - title_a

        return {
            "stelle_a": {
                "hash": ja.get("hash"),
                "title": ja.get("title"),
                "company": ja.get("company"),
                "score": ja.get("score"),
                "source": ja.get("source"),
                "salary_min": ja.get("salary_min"),
                "salary_max": ja.get("salary_max"),
                "location": ja.get("location"),
                "remote_level": ja.get("remote_level"),
                "employment_type": ja.get("employment_type"),
                "is_active": bool(ja.get("is_active")),
                "description_length": len((ja.get("description") or "")),
            },
            "stelle_b": {
                "hash": jb.get("hash"),
                "title": jb.get("title"),
                "company": jb.get("company"),
                "score": jb.get("score"),
                "source": jb.get("source"),
                "salary_min": jb.get("salary_min"),
                "salary_max": jb.get("salary_max"),
                "location": jb.get("location"),
                "remote_level": jb.get("remote_level"),
                "employment_type": jb.get("employment_type"),
                "is_active": bool(jb.get("is_active")),
                "description_length": len((jb.get("description") or "")),
            },
            "vergleich": {
                "titel_gemeinsam": sorted(common_title),
                "titel_nur_a": sorted(only_a_title),
                "titel_nur_b": sorted(only_b_title),
                "beschreibung_overlap_pct": (
                    round(len(desc_a & desc_b) / max(len(desc_a | desc_b), 1) * 100, 1)
                    if (desc_a or desc_b) else 0
                ),
                "score_diff": (ja.get("score") or 0) - (jb.get("score") or 0),
                "gleiche_firma": (ja.get("company") or "").lower().strip() == (jb.get("company") or "").lower().strip(),
            },
        }

    @mcp.tool()
    def aehnliche_stellen_finden(stellen_hash: str, max_treffer: int = 5) -> dict:
        """Findet aehnliche Stellen zu einer gegebenen Stelle (#580).

        Algorithmus: Token-Overlap zwischen Title+Description. Bewerbungen
        und Stellen mit gleichem Hash werden ausgeschlossen. Liefert
        zusaetzlich den Outcome-Status (erfolgreich/abgelehnt/aussortiert)
        wenn vorhanden — als Lern-Signal.
        """
        from ..services.typed_ids import strip_prefix
        h = strip_prefix(stellen_hash)
        target = db.get_job(h)
        if not target:
            return {"fehler": "Stelle nicht gefunden."}

        import re
        def _tokens(text):
            return set(re.findall(r"[a-zäöüß0-9]+", (text or "").lower())) - {
                "und", "der", "die", "das", "ein", "eine", "fuer", "im", "mit",
                "bei", "von", "zu", "in", "an", "the", "and", "for", "with",
                "stelle", "position", "rolle", "team", "wir", "sie",
            }
        target_tokens = _tokens(target.get("title", "") + " " + (target.get("description") or "")[:1500])
        if not target_tokens:
            return {"hinweis": "Stelle hat zu wenig Text fuer Aehnlichkeits-Berechnung."}

        # Alle anderen Stellen durchgehen
        all_jobs = db.get_active_jobs() + db.get_dismissed_jobs()
        scored = []
        for j in all_jobs:
            if j.get("hash") == target.get("hash"):
                continue
            jt = _tokens(j.get("title", "") + " " + (j.get("description") or "")[:1500])
            if not jt:
                continue
            inter = target_tokens & jt
            union = target_tokens | jt
            jaccard = len(inter) / len(union) if union else 0
            if jaccard < 0.05:
                continue
            scored.append((jaccard, j))

        # Top N
        scored.sort(key=lambda x: -x[0])
        top = scored[:max_treffer]

        # Bewerbungen pruefen — gibt's zu der Stelle eine?
        results = []
        for sim, j in top:
            apps = db.get_applications_for_job(j.get("hash"))
            outcome = None
            if apps:
                statuses = [a.get("status") for a in apps]
                if any(s in ("interview", "zweitgespraech",
                            "interview_abgeschlossen", "angebot",
                            "angenommen") for s in statuses):
                    outcome = "interview_erreicht"
                elif "abgelehnt" in statuses:
                    outcome = "abgelehnt"
                else:
                    outcome = f"status:{statuses[0]}" if statuses else None
            elif not j.get("is_active"):
                outcome = f"aussortiert:{j.get('dismiss_reason') or 'unbekannt'}"
            results.append({
                "hash": j.get("hash"),
                "title": j.get("title"),
                "company": j.get("company"),
                "similarity": round(sim, 2),
                "outcome": outcome,
            })

        return {
            "vergleichsstelle": {
                "hash": target.get("hash"),
                "title": target.get("title"),
                "company": target.get("company"),
            },
            "anzahl": len(results),
            "aehnliche": results,
        }

    @mcp.tool()
    def stelle_mergen(
        master_hash: str,
        duplikat_hash: str,
        feld_strategie: dict | None = None,
        dry_run: bool = True,
    ) -> dict:
        """Fuehrt zwei doppelt angelegte Stellen zusammen (#470).

        Typischer Flow:
        1. Erst ``dry_run=True`` (Default) aufrufen -> Vorschau mit Feld-
           Entscheidungen, Konflikten und welche Bewerbungen umgehaengt werden.
        2. Output pruefen, bei Konflikten ggf. ``feld_strategie`` mitgeben.
        3. Mit ``dry_run=False`` finalisieren.

        Args:
            master_hash: Stelle, die erhalten bleibt.
            duplikat_hash: Stelle, die aufgeloest (geloescht) wird.
            feld_strategie: Optional dict pro Feld: 'master' | 'duplikat' |
                'merge' (letzteres nur fuer 'description' sinnvoll).
                Felder die nur im Duplikat gefuellt sind, werden IMMER automatisch
                uebernommen; Felder die nur im Master gefuellt sind, bleiben.
            dry_run: Default True. Bei True wird nichts geschrieben.

        Returns:
            dict mit 'status' ('vorschau'/'ok'), 'feld_entscheidungen',
            'konflikte' (Liste Felder mit abweichenden Werten),
            'umgehaengte_bewerbungen'.
        """
        if not master_hash or not duplikat_hash:
            return {"fehler": "master_hash und duplikat_hash sind Pflicht"}
        result = db.merge_jobs(
            master_hash=master_hash,
            duplicate_hash=duplikat_hash,
            field_strategy=feld_strategie,
            dry_run=dry_run,
        )
        if dry_run and "fehler" not in result:
            result["hinweis"] = (
                "Vorschau. Mit dry_run=False ausfuehren. "
                "Bei Konflikten feld_strategie mitgeben "
                "(z.B. {'description': 'merge', 'url': 'duplikat'})."
            )
        return result

    @mcp.tool()
    def fit_analyse(job_hash: str) -> dict:
        """Detaillierte Passungsanalyse für eine bestimmte Stelle.

        Zeigt welche Keywords matchen, was fehlt, und gibt eine Risikobewertung.

        Args:
            job_hash: Hash der Stelle (von stellen_anzeigen)
        """
        gate = ki_gate(db, "stellenanalyse")
        if gate is not None:
            return gate
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

        # v1.6.5 (#539, Folge von #535): Fit-Score zurueck in jobs.score
        # persistieren. Vorher rechnete fit_analyse on-demand mit Profile-
        # Daten + Risk-Faktoren (z.B. -2 fuer Hochschulabschluss), aber
        # jobs.score blieb auf dem reinen Scrape-Wert haengen — Listen
        # zeigten alten Wert, fit_analyse einen anderen.
        # Der Fit-Score ist „mehr wert" weil er Profile + Risiken
        # beruecksichtigt; daher ueberschreibt er den Scrape-Score.
        new_score = result.get("total_score")
        if new_score is not None and isinstance(new_score, (int, float)):
            try:
                old_score = job_dict.get("score")
                if old_score != new_score:
                    db.update_job(job_hash, {"score": int(new_score)})
                    result["score_aktualisiert"] = {
                        "alter_score": old_score,
                        "neuer_score": int(new_score),
                    }
            except Exception as exc:
                logger.warning("Score-Persistierung nach fit_analyse fehlgeschlagen: %s", exc)

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
        # v1.7.0-beta.46 (#618): Kurze IDs (8 Zeichen) wurden vorher
        # nicht akzeptiert — andere Tools (fit_analyse, scoring_vorschau)
        # tun das aber. Konsistenz: resolve_job_hash erlaubt beides.
        from ..services.typed_ids import strip_prefix
        h = strip_prefix(job_hash)
        resolved = db.resolve_job_hash(h)
        if not resolved:
            return {"fehler": "Stelle nicht gefunden. Pruefe den Hash mit stellen_anzeigen()."}
        job = db.get_job(resolved)
        if not job:
            return {"fehler": "Stelle nicht gefunden. Pruefe den Hash mit stellen_anzeigen()."}
        # Ab hier den vollen aufgeloesten Hash verwenden
        job_hash = resolved

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

        # #535 v1.6.4: Score nach Beschreibungs-/Titel-Update neu berechnen.
        # Vorher blieb der persistente score-Wert in jobs.score auf dem Stand
        # der initialen Scrape-Beschreibung — fit_analyse rechnete live mit
        # der neuen Beschreibung, stellen_anzeigen mit dem alten score.
        # Drei verschiedene Werte fuer dieselbe Stelle waren die Folge.
        score_recomputed = None
        if "description" in updates or "title" in updates:
            try:
                from ..job_scraper import calculate_score
                criteria = db.get_search_criteria()
                fresh_job = db.get_job(job_hash) or {}
                new_score = calculate_score(fresh_job, criteria)
                if new_score is not None:
                    db.update_job(job_hash, {"score": new_score})
                    score_recomputed = {
                        "alter_score": job.get("score"),
                        "neuer_score": new_score,
                    }
            except Exception as exc:
                logger.warning("Score-Recompute fuer %s fehlgeschlagen: %s", job_hash, exc)

        result = {
            "status": "aktualisiert",
            "job_hash": job_hash,
            "geaenderte_felder": list(updates.keys()),
            "nachricht": (
                f"Stelle '{updates.get('title') or job.get('title', '')}' "
                f"bei {updates.get('company') or job.get('company', '')} aktualisiert."
            ),
        }
        if score_recomputed:
            result["score_neu_berechnet"] = score_recomputed
        return result

    @mcp.tool()
    def stellen_auto_aussortieren(
        max_stellen: int = 50,
        min_score: int = 0,
        dry_run: bool = False,
    ) -> dict:
        """Profil-basiertes Auto-Aussortieren via lokaler AI (#586).

        Statt Filter-Listen zu pflegen entscheidet die lokale AI pro Stelle,
        ob sie zum Profil passt. Skaliert mit beliebigen Berufsfeldern —
        funktioniert fuer Senior-PLM genauso wie fuer Studenten oder
        Service-Berufe.

        Pro Stelle (max_stellen, sortiert nach Score absteigend):
        - LLM-Anfrage `match_job_to_skills` mit Profil-Kontext + Stelle
        - PASST_NICHT → dismiss_job mit Grund 'profil_match_negativ' und
          LLM-Begruendung in research_notes
        - UNSICHER → unangetastet (User entscheidet manuell)
        - PASST → unangetastet

        Voraussetzung: Lokale AI aktiv (Ollama laeuft, Modell installiert).
        Fallback: ohne Lokale AI gibt es eine ehrliche Meldung — keine
        Heuristik-Raterei.

        Args:
            max_stellen: Maximum Stellen pro Lauf (Default 50, Schutz gegen
                         lange Token-Runs).
            min_score: Mindest-Score-Schwelle. Stellen darunter werden gar
                       nicht erst der LLM vorgelegt (Default 0 = alle).
            dry_run: Wenn True, nur Vorschau ohne dismiss-Aktionen.

        Idempotent: bewertet keine Stelle erneut die schon `passt_nicht`
        oder eine Bewerbung hat.
        """
        # v1.7.0-beta.46 (#610): Try/except um den ganzen Body, alle
        # Returns mit uniformem Schema. Vorher: outputSchema-Validierungs-
        # fehler weil error-Pfade andere Keys hatten als Success-Pfade.
        def _err(msg: str, **extra) -> dict:
            base = {
                "status": "fehler",
                "fehler": msg,
                "geprueft": 0, "passt_nicht": 0, "unsicher": 0, "passt": 0,
                "errors_count": 0,
                "passt_nicht_details": [], "unsicher_details": [],
                "passt_details": [], "errors": [],
                "modell": "",
            }
            base.update(extra)
            return base

        try:
            from ..services.llm_service import get_llm_service, TaskKind, Backend

            svc = get_llm_service(db)
            status = svc.get_status(force_refresh=True)
            if not status.ollama_available or not status.available_models:
                return _err(
                    "Lokale AI nicht verfuegbar.",
                    hinweis="Stellen_auto_aussortieren braucht Ollama + ein installiertes Modell. Pruefe Einstellungen -> Lokale KI.",
                )
            if status.user_state != "active":
                return _err(
                    f"Lokale AI ist im State '{status.user_state}'.",
                    hinweis="Setze State auf 'active' in Einstellungen -> Lokale KI.",
                )
        except Exception as exc:
            return _err(f"unerwarteter_fehler: {str(exc)[:200]}")

        # Profil-Kontext sammeln
        profile = db.get_profile() or {}
        profile_skills = [
            s.get("name", "") for s in (profile.get("skills") or [])[:15]
        ]
        positions = profile.get("positions") or []
        latest_pos = positions[0] if positions else {}
        profile_position = latest_pos.get("title", "")
        # Heuristik: Karriere-Stufe aus aktueller Position + Jahren ableiten
        years = 0
        for p in positions:
            try:
                start = int((p.get("start_date") or "0000")[:4])
                end_raw = (p.get("end_date") or "")[:4]
                end = int(end_raw) if end_raw.isdigit() else 2026
                if start > 1900:
                    years += max(0, end - start)
            except Exception:
                pass
        if years >= 10:
            profile_seniority = f"Senior ({years} Jahre Erfahrung)"
        elif years >= 5:
            profile_seniority = f"Mid-Level ({years} Jahre Erfahrung)"
        elif years >= 1:
            profile_seniority = f"Junior ({years} Jahre Erfahrung)"
        else:
            profile_seniority = "Berufseinsteiger / Berufsanfaenger"

        # Kandidaten holen — aktive, noch nicht bewertete Stellen
        all_active = db.get_active_jobs()
        # Filter: keine Bewerbung, kein dismiss-Reason
        candidates = [
            j for j in all_active
            if not j.get("dismiss_reason")
            and (j.get("score") or 0) >= min_score
        ]
        candidates.sort(key=lambda j: -(j.get("score") or 0))
        candidates = candidates[:max_stellen]

        # v1.7.0-beta.28 (#594 Stufe 3): adaptive Prompt-Anreicherung —
        # Top-3 dismiss_reasons des Users bekommt die LLM mit, damit sie
        # bekannte Anti-Muster wiedererkennen kann.
        dismiss_reasons_top: list[dict] = []
        try:
            conn = db.connect()
            pid = db.get_active_profile_id()
            rows = conn.execute(
                "SELECT dismiss_reason, COUNT(*) AS n FROM jobs "
                "WHERE dismiss_reason IS NOT NULL AND dismiss_reason != '' "
                "AND is_active=0 AND (profile_id=? OR profile_id IS NULL) "
                "GROUP BY dismiss_reason ORDER BY n DESC LIMIT 3",
                (pid,)
            ).fetchall()
            dismiss_reasons_top = [
                {"reason": r["dismiss_reason"], "count": r["n"]}
                for r in rows
            ]
        except Exception:
            pass

        if not candidates:
            return _err(
                "Keine ungerateten Stellen oberhalb min_score.",
                status="leer",
            )

        passt_nicht_results = []
        unsicher_results = []
        passt_results = []
        errors = []

        for job in candidates:
            try:
                payload = {
                    "profile_skills": profile_skills,
                    "profile_position": profile_position,
                    "profile_seniority": profile_seniority,
                    "job_title": job.get("title") or "",
                    "job_company": job.get("company") or "",
                    "job_description": (job.get("description") or "")[:1500],
                    "dismiss_reasons_top": dismiss_reasons_top,
                }
                result = svc.run(TaskKind.MATCH_JOB_TO_SKILLS, payload)
                if not result.success:
                    errors.append({
                        "hash": job["hash"],
                        "title": job.get("title"),
                        "error": result.fallback_message or "unknown",
                    })
                    continue
                decision = (result.payload or {}).get("decision", "UNSICHER")
                reason = (result.payload or {}).get("reason", "")
                entry = {
                    "hash": job["hash"],
                    "title": job.get("title"),
                    "company": job.get("company"),
                    "score": job.get("score"),
                    "reason": reason,
                }
                if decision == "PASST_NICHT":
                    if not dry_run:
                        # Notiz in research_notes anhaengen, dann dismiss
                        try:
                            cur_notes = (job.get("research_notes") or "")
                            new_notes = (cur_notes + "\n\n" + f"[Auto-Aussortierung] {reason}").strip() if cur_notes else f"[Auto-Aussortierung] {reason}"
                            db.update_job(job["hash"], {"research_notes": new_notes})
                            db.dismiss_job(job["hash"], reason="profil_match_negativ")
                        except Exception as exc:
                            errors.append({
                                "hash": job["hash"], "error": str(exc)[:200],
                            })
                    passt_nicht_results.append(entry)
                elif decision == "PASST":
                    passt_results.append(entry)
                else:
                    unsicher_results.append(entry)
            except Exception as exc:
                errors.append({
                    "hash": job.get("hash"), "error": str(exc)[:200],
                })

        try:
            modell_name = status.selected_model or ""
        except Exception:
            modell_name = ""
        return {
            "status": "ok",
            "dry_run": dry_run,
            "fehler": "",
            "geprueft": len(candidates),
            "passt_nicht": len(passt_nicht_results),
            "unsicher": len(unsicher_results),
            "passt": len(passt_results),
            "errors_count": len(errors),
            "passt_nicht_details": passt_nicht_results[:20],
            "unsicher_details": unsicher_results[:10],
            "passt_details": passt_results[:10],
            "errors": errors[:5],
            "modell": modell_name,
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

        # #500: Defekt-Quellen aus SOURCE_REGISTRY anreichern
        from ..job_scraper import SOURCE_REGISTRY
        defekte = []
        for key, info in SOURCE_REGISTRY.items():
            if info.get("defekt"):
                defekte.append({
                    "name": key,
                    "anzeigename": info.get("name", key),
                    "grund": info.get("defekt_grund"),
                    "manueller_fallback": info.get("manueller_fallback"),
                })

        scrapers = []
        stumme = []
        deaktiviert_auto = []
        for h in health:
            success_rate = round(h["total_successes"] / h["total_runs"] * 100) if h["total_runs"] else 0
            consec_silent = h.get("consecutive_silent") or 0
            last_count = h.get("last_count") or 0
            entry = {
                "name": h["scraper_name"],
                "aktiv": bool(h["is_active"]),
                "letzter_lauf": h.get("last_run"),
                "letzter_erfolg": h.get("last_success"),
                "fehler_serie": h["consecutive_failures"],
                "stille_serie": consec_silent,
                # v1.6.5 (#553): drei klare Felder statt einem ambigen "letzte_treffer".
                # letzte_rohtreffer = was der Scraper geliefert hat,
                # letzte_gefilterte_treffer = nach MUSS/AUSSCHLUSS/Score-Filter,
                # letzte_neue_treffer = wirklich neu in der DB (Duplikate raus).
                "letzte_rohtreffer": last_count,
                "letzte_gefilterte_treffer": h.get("last_filtered_count") or 0,
                "letzte_neue_treffer": h.get("last_new_count") or 0,
                # Backward-compat-Alias (Frontend/Notes nutzen evtl. noch den alten Namen)
                "letzte_treffer": last_count,
                "letzter_status_detail": h.get("last_status_detail"),
                "erfolgsrate": f"{success_rate}%",
                "laeufe_gesamt": h["total_runs"],
                "durchschn_zeit_s": round(h["avg_time_s"], 1),
                "letzter_fehler": h.get("last_error"),
            }
            scrapers.append(entry)
            if consec_silent >= 3 and h["is_active"]:
                stumme.append(entry["name"])
            if not h["is_active"] and consec_silent >= 5:
                deaktiviert_auto.append(entry["name"])

        result = {
            "status": "ok",
            "scraper_anzahl": len(scrapers),
            "scrapers": scrapers,
        }
        if defekte:
            result["defekte_quellen"] = defekte
            result["hinweis_defekt"] = (
                f"{len(defekte)} Quelle(n) sind aktuell als defekt markiert "
                "(URL veraltet, Bot-Schutz oder Timeout). Sie werden nicht "
                "automatisch durchsucht. Workaround: Chrome-Extension oeffnen "
                "und Stellen via stelle_manuell_anlegen nach PBP uebernehmen."
            )
        if stumme:
            result["stumme_quellen"] = stumme
            result["hinweis_stumm"] = (
                f"{len(stumme)} Quelle(n) liefern seit mehreren Laeufen 0 Treffer. "
                "Pruefe, ob Selektoren veraltet sind oder die Quelle den Standort nicht abdeckt."
            )
        if deaktiviert_auto:
            result["auto_deaktiviert"] = deaktiviert_auto
            result["hinweis_reaktivierung"] = (
                "Diese Quellen wurden nach 5+ stillen Laeufen automatisch deaktiviert. "
                "Reaktivierung via scraper_diagnose(scraper_name=..., aktion='reaktivieren')."
            )
        return result

    @mcp.tool()
    def quellen_health_check(quellen: list[str] = [], parallel: bool = True) -> dict:
        """v1.7.0-beta.51 (#624 Phase 2): Aktiver Probe-Check fuer Job-Quellen.

        Macht pro Quelle einen minimalen HTTP-Request (1 Stelle, keine
        Filter) um zu pruefen ob die API/Feed-Endpoint erreichbar ist.
        Ergaenzt scraper_diagnose (das auf Liefer-Statistiken basiert) —
        hier kommt die Info „API selbst erreichbar JA/NEIN" aus einem
        echten Request.

        Args:
            quellen: Liste der zu pruefenden Source-Keys. Wenn leer:
                alle mit definiertem Probe (~12 Quellen).
            parallel: Wenn True (Default), Probes parallel via Threads.

        Returns:
            count_total, count_reachable, results (Liste pro Quelle).
            Pro Quelle: source, reachable, http_status, latency_ms, error.

        Use Case:
            User: „Warum kommen von <Quelle> seit Tagen keine Treffer?"
            Claude: ruft quellen_health_check mit dieser Quelle, sagt:
            „API liefert 503 seit 3 Sekunden — ist temporär weg."
            ODER „API liefert 200 — die Suche selbst ist das Problem,
            evtl. liegt's an deinen Suchbegriffen."
        """
        from ..job_scraper.health import check_source, get_probable_sources
        from concurrent.futures import ThreadPoolExecutor
        targets = quellen if quellen else get_probable_sources()
        if parallel and len(targets) > 1:
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(check_source, targets))
        else:
            results = [check_source(s) for s in targets]
        reachable = sum(1 for r in results if r.get("reachable"))
        return {
            "count_total": len(results),
            "count_reachable": reachable,
            "count_unreachable": len(results) - reachable,
            "results": results,
            "hinweis": (
                f"{reachable} von {len(results)} Quellen erreichbar. "
                "Ergaenzend zur Liefer-Statistik in scraper_diagnose."
            ),
        }

    @mcp.tool()
    def quellen_aus_urls_korrigieren(dry_run: bool = True) -> dict:
        """v1.7.0-beta.47 (#613): Korrigiert source='manuell' anhand der job-URL.

        Geht durch alle Stellen mit source='manuell' (egal ob aktiv oder
        aussortiert) und prueft die URL. Wenn die URL einer bekannten
        Quelle zugeordnet werden kann (LinkedIn, StepStone, Indeed, ...),
        wird source umgesetzt.

        Args:
            dry_run: Wenn True (Default), nur Vorschau ohne Aenderung.
                     Mit dry_run=False wird tatsaechlich geschrieben.

        Returns:
            count_total, count_changed, changes (Liste der geplanten
            oder durchgefuehrten Aenderungen pro Stelle).

        Idempotent: ein zweiter Lauf nach Erfolg findet 0 Kandidaten.
        """
        from ..services.url_to_source import detect_source_from_url
        conn = db.connect()
        pid = db.get_active_profile_id()
        rows = conn.execute(
            "SELECT hash, title, company, url, source FROM jobs "
            "WHERE source='manuell' AND url IS NOT NULL AND url != '' "
            "AND (profile_id=? OR profile_id IS NULL)",
            (pid,)
        ).fetchall()
        changes = []
        applied = 0
        for r in rows:
            new_source = detect_source_from_url(r["url"])
            if new_source != "manuell":
                changes.append({
                    "hash": r["hash"],
                    "title": (r["title"] or "")[:60],
                    "company": (r["company"] or "")[:40],
                    "url": (r["url"] or "")[:80],
                    "source_alt": "manuell",
                    "source_neu": new_source,
                })
                if not dry_run:
                    try:
                        conn.execute(
                            "UPDATE jobs SET source=? WHERE hash=?",
                            (new_source, r["hash"])
                        )
                        applied += 1
                    except Exception as exc:
                        changes[-1]["fehler"] = str(exc)[:200]
        if not dry_run:
            conn.commit()
        return {
            "status": "vorschau" if dry_run else "ausgefuehrt",
            "count_total": len(rows),
            "count_changed": len(changes),
            "count_applied": applied,
            "changes": changes[:50],
            "hinweis": (
                "dry_run=True — kein Schreibvorgang. Nochmal mit "
                "dry_run=False aufrufen um die Aenderungen zu speichern."
                if dry_run else
                f"{applied} Stellen umgestellt. Konversion in der Quellen-"
                "Statistik des Bewerbungsbericht jetzt korrekter."
            ),
        }

    @mcp.tool()
    def verwaiste_stellenrefs_bereinigen(
        strategie: str = "report",
        dry_run: bool = True,
    ) -> dict:
        """v1.7.0-beta.47 (#616): Findet/bereinigt verwaiste job_hash-Refs in Bewerbungen.

        Bewerbungen koennen einen `job_hash` referenzieren, dessen Stelle
        nicht (mehr) in der `jobs`-Tabelle existiert. Folge: stelle_bearbeiten
        scheitert, fit_analyse hat keinen Kontext, kontakt_verknuepfen
        bricht ab (#615).

        Args:
            strategie: 'report' (Default) — nur auflisten ohne Aenderung.
                       'rekonstruieren' — eine Platzhalter-Stelle anlegen aus
                         title/company/url der Bewerbung.
                       'leeren' — job_hash der Bewerbung auf '' setzen.
            dry_run: Bei 'rekonstruieren'/'leeren' Vorschau ohne Schreibvorgang.

        Returns:
            count_total, count_orphaned, list von Bewerbungen mit Detail.
        """
        if strategie not in ("report", "rekonstruieren", "leeren"):
            return {"fehler": "strategie muss 'report', 'rekonstruieren' "
                              "oder 'leeren' sein."}
        conn = db.connect()
        pid = db.get_active_profile_id()
        # Alle Bewerbungen mit nicht-leerem job_hash
        apps = conn.execute(
            "SELECT id, job_hash, title, company, url, status FROM applications "
            "WHERE job_hash IS NOT NULL AND job_hash != '' "
            "AND (profile_id=? OR profile_id IS NULL)",
            (pid,)
        ).fetchall()
        orphans = []
        for a in apps:
            jh = a["job_hash"]
            # Existiert die Stelle? db.get_job liest die jobs-Tabelle —
            # resolve_job_hash hier nicht nutzbar weil das nur den Hash
            # transformiert, nicht die Existenz prueft.
            if db.get_job(jh) is None:
                orphans.append({
                    "application_id": a["id"][:8],
                    "_full_id": a["id"],  # intern fuer cleanup
                    "title": (a["title"] or "")[:60],
                    "company": (a["company"] or "")[:40],
                    "url": (a["url"] or "")[:80],
                    "status": a["status"],
                    "missing_job_hash": jh,
                })
        applied = 0
        actions: list[dict] = []
        if strategie != "report" and not dry_run:
            from datetime import datetime as _dt
            from ..job_scraper import stelle_hash as _stelle_hash
            for o in orphans:
                aid_short = o["application_id"]
                full_app_id = o["_full_id"]
                if strategie == "leeren":
                    try:
                        # NULL statt '' — '' wuerde FK-Constraint verletzen
                        # weil hash='' nicht in jobs existiert.
                        conn.execute(
                            "UPDATE applications SET job_hash=NULL WHERE id=?",
                            (full_app_id,)
                        )
                        applied += 1
                        actions.append({"application_id": aid_short,
                                        "aktion": "job_hash auf NULL gesetzt"})
                    except Exception as exc:
                        actions.append({"application_id": aid_short,
                                        "fehler": str(exc)[:200]})
                elif strategie == "rekonstruieren":
                    try:
                        # Platzhalter-Stelle anlegen mit denselben Daten
                        company = o["company"] or "Unbekannt"
                        title = o["title"] or "Unbekannte Stelle"
                        url = o["url"] or ""
                        from ..services.url_to_source import detect_source_from_url
                        source = detect_source_from_url(url) if url else "manuell"
                        new_hash = _stelle_hash(source, f"{company} {title}")
                        existing = db.get_job(new_hash)
                        if not existing:
                            db.save_jobs([{
                                "hash": new_hash,
                                "title": title,
                                "company": company,
                                "location": "",
                                "url": url,
                                "source": source,
                                "description": (
                                    "[Rekonstruiert v1.7.0-beta.47 (#616)] "
                                    "Diese Stelle wurde aus einer Bewerbung "
                                    "rekonstruiert weil die urspruengliche "
                                    "Stelle nicht mehr in der jobs-Tabelle "
                                    "existierte."
                                ),
                                "score": 0,
                                "is_pinned": False,
                                "remote_level": "unbekannt",
                                "employment_type": "festanstellung",
                                "found_at": _dt.now().isoformat(),
                            }])
                            # save_jobs setzt is_active immer auf 1 —
                            # Platzhalter sollen nicht im aktiven Pool sein
                            scoped_for_active = db._scope_job_hash(new_hash)
                            conn.execute(
                                "UPDATE jobs SET is_active=0, "
                                "dismiss_reason='rekonstruiert_orphan_616' "
                                "WHERE hash=?",
                                (scoped_for_active,)
                            )
                        # Bewerbung auf den neuen Hash umstellen
                        scoped_hash = db._scope_job_hash(new_hash)
                        conn.execute(
                            "UPDATE applications SET job_hash=? WHERE id=?",
                            (scoped_hash, full_app_id)
                        )
                        applied += 1
                        actions.append({"application_id": aid_short,
                                        "aktion": f"rekonstruiert als {new_hash[:12]}"})
                    except Exception as exc:
                        actions.append({"application_id": aid_short,
                                        "fehler": str(exc)[:200]})
            conn.commit()
        return {
            "status": "vorschau" if (strategie == "report" or dry_run) else "ausgefuehrt",
            "strategie": strategie,
            "dry_run": dry_run,
            "count_total_apps": len(apps),
            "count_orphaned": len(orphans),
            "count_applied": applied,
            "orphans": orphans[:50],
            "actions": actions[:50],
            "hinweis": (
                "Strategie 'report' = nur auflisten. 'rekonstruieren' "
                "legt eine Platzhalter-Stelle an (is_active=0). 'leeren' "
                "setzt job_hash der Bewerbung auf ''."
                if strategie == "report" or dry_run else
                f"{applied} Bewerbung(en) bereinigt mit Strategie '{strategie}'."
            ),
        }
