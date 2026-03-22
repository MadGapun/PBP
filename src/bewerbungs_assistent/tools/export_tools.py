"""PDF/DOCX-Export für Lebenslauf, Anschreiben und Profil-Report — 5 Tools."""

from ..database import get_data_dir


def _auto_save_job_description(db, firma: str, stelle: str, beschreibung: str):
    """Speichert Stellenbeschreibung automatisch bei passender Stelle/Bewerbung (#172)."""
    if not beschreibung or not firma:
        return
    try:
        conn = db.connect()
        pid = db.get_active_profile_id()
        # Find matching job by company+title
        row = conn.execute(
            "SELECT hash, description FROM jobs WHERE company LIKE ? AND title LIKE ? "
            "AND (profile_id=? OR profile_id IS NULL) LIMIT 1",
            (f"%{firma}%", f"%{stelle}%", pid)
        ).fetchone()
        if row and (not row["description"] or len(row["description"]) < len(beschreibung)):
            conn.execute(
                "UPDATE jobs SET description=?, updated_at=datetime('now') WHERE hash=?",
                (beschreibung, row["hash"])
            )
            conn.commit()
        # Also update application description_snapshot if exists
        app_row = conn.execute(
            "SELECT id, description_snapshot FROM applications "
            "WHERE company LIKE ? AND title LIKE ? "
            "AND (profile_id=? OR profile_id IS NULL) LIMIT 1",
            (f"%{firma}%", f"%{stelle}%", pid)
        ).fetchone()
        if app_row and not app_row["description_snapshot"]:
            conn.execute(
                "UPDATE applications SET description_snapshot=?, snapshot_date=datetime('now'), "
                "updated_at=datetime('now') WHERE id=?",
                (beschreibung, app_row["id"])
            )
            conn.commit()
    except Exception:
        pass  # Non-critical feature


def register(mcp, db, logger):
    """Registriert Export-Tools."""

    @mcp.tool()
    def lebenslauf_exportieren(
        format: str = "pdf",
        angepasst_für: str = ""
    ) -> dict:
        """Exportiert den Lebenslauf als PDF, DOCX, Markdown oder TXT-Datei.

        Erzeugt ein professionell formatiertes Dokument aus dem gespeicherten Profil.
        Die Datei wird im Bewerbungs-Assistent Datenordner gespeichert.

        Args:
            format: 'pdf', 'docx', 'md' (Markdown) oder 'txt' (Klartext)
            angepasst_für: Optional — Firma/Stelle für die der CV angepasst wird (für Dateinamen)
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein Profil vorhanden. Erstelle zuerst ein Profil mit der Ersterfassung."}

        export_dir = get_data_dir() / "export"
        export_dir.mkdir(exist_ok=True)
        name_slug = (profile.get("name") or "lebenslauf").replace(" ", "_").lower()
        suffix = f"_{angepasst_für.replace(' ', '_').lower()}" if angepasst_für else ""

        if format == "docx":
            from ..export import generate_cv_docx
            path = export_dir / f"lebenslauf_{name_slug}{suffix}.docx"
            generate_cv_docx(profile, path)
        elif format == "pdf":
            from ..export import generate_cv_pdf
            path = export_dir / f"lebenslauf_{name_slug}{suffix}.pdf"
            generate_cv_pdf(profile, path)
        elif format in ("md", "markdown"):
            from ..export import generate_cv_markdown
            path = export_dir / f"lebenslauf_{name_slug}{suffix}.md"
            generate_cv_markdown(profile, path)
            format = "md"
        elif format in ("txt", "text"):
            from ..export import generate_cv_text
            path = export_dir / f"lebenslauf_{name_slug}{suffix}.txt"
            generate_cv_text(profile, path)
            format = "txt"
        else:
            return {"fehler": "Format muss 'pdf', 'docx', 'md' oder 'txt' sein."}

        return {
            "status": "erstellt",
            "datei": str(path),
            "format": format,
            "nachricht": f"Lebenslauf als {format.upper()} exportiert: {path.name}. "
                         "Die Datei liegt im Bewerbungs-Assistent Datenordner. "
                         "Du kannst sie auch im Dashboard unter http://localhost:8200 herunterladen."
        }

    @mcp.tool()
    def lebenslauf_angepasst_exportieren(
        stelle: str,
        firma: str,
        stellenbeschreibung: str = ""
    ) -> dict:
        """Exportiert einen auf die Stelle angepassten Lebenslauf als DOCX.

        Erstellt einen Lebenslauf der relevante Skills und Erfahrungen
        für die Zielstelle hervorhebt und priorisiert. Immer als DOCX,
        da die finale Formatierung manuell erfolgt.

        Args:
            stelle: Stellentitel (z.B. 'Software Architect')
            firma: Firmenname (z.B. 'TechCorp GmbH')
            stellenbeschreibung: Optional — Beschreibung der Stelle für bessere Anpassung
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein Profil vorhanden. Erstelle zuerst ein Profil mit der Ersterfassung."}

        from ..export import generate_tailored_cv_docx

        export_dir = get_data_dir() / "export"
        export_dir.mkdir(exist_ok=True)
        name_slug = (profile.get("name") or "lebenslauf").replace(" ", "_").lower()
        firma_slug = (firma or "stelle").replace(" ", "_").lower()

        path = export_dir / f"lebenslauf_{name_slug}_{firma_slug}.docx"
        generate_tailored_cv_docx(profile, stelle, stellenbeschreibung, path)

        # #172: Stellenbeschreibung automatisch speichern
        if stellenbeschreibung:
            _auto_save_job_description(db, firma, stelle, stellenbeschreibung)

        return {
            "status": "erstellt",
            "datei": str(path),
            "format": "docx",
            "nachricht": f"Angepasster Lebenslauf für '{stelle}' bei {firma} als DOCX exportiert: {path.name}. "
                         "Die Datei ist als DOCX gespeichert, damit du die finale Formatierung anpassen kannst."
        }

    @mcp.tool()
    def anschreiben_exportieren(
        text: str,
        stelle: str,
        firma: str,
        format: str = "pdf",
        stellenbeschreibung: str = ""
    ) -> dict:
        """Exportiert ein Anschreiben als PDF, DOCX, Markdown oder TXT-Datei.

        Nimmt den fertigen Anschreiben-Text und erzeugt ein formatiertes Dokument
        mit Absender, Datum, Betreffzeile und Text.

        Args:
            text: Der vollstaendige Anschreiben-Text (Absaetze mit Leerzeilen trennen)
            stelle: Stellentitel (z.B. 'Software Architect')
            firma: Firmenname (z.B. 'TechCorp GmbH')
            format: 'pdf', 'docx', 'md' (Markdown) oder 'txt' (Klartext)
            stellenbeschreibung: Optional — wird automatisch in der DB gespeichert (#172)
        """
        if not text.strip():
            return {"fehler": "Kein Anschreiben-Text angegeben. Nutze den Prompt 'bewerbung_schreiben' um einen Text zu erstellen."}

        profile = db.get_profile() or {}

        export_dir = get_data_dir() / "export"
        export_dir.mkdir(exist_ok=True)
        firma_slug = (firma or "bewerbung").replace(" ", "_").lower()

        if format == "docx":
            from ..export import generate_cover_letter_docx
            path = export_dir / f"anschreiben_{firma_slug}.docx"
            generate_cover_letter_docx(profile, text, stelle, firma, path)
        elif format == "pdf":
            from ..export import generate_cover_letter_pdf
            path = export_dir / f"anschreiben_{firma_slug}.pdf"
            generate_cover_letter_pdf(profile, text, stelle, firma, path)
        elif format in ("md", "markdown"):
            path = export_dir / f"anschreiben_{firma_slug}.md"
            from ..export import generate_cover_letter_text
            generate_cover_letter_text(profile, text, stelle, firma, path, markdown=True)
            format = "md"
        elif format in ("txt", "text"):
            path = export_dir / f"anschreiben_{firma_slug}.txt"
            from ..export import generate_cover_letter_text
            generate_cover_letter_text(profile, text, stelle, firma, path, markdown=False)
            format = "txt"
        else:
            return {"fehler": "Format muss 'pdf', 'docx', 'md' oder 'txt' sein."}

        # #172: Stellenbeschreibung automatisch speichern
        if stellenbeschreibung:
            _auto_save_job_description(db, firma, stelle, stellenbeschreibung)

        return {
            "status": "erstellt",
            "datei": str(path),
            "format": format,
            "nachricht": f"Anschreiben fuer {stelle} bei {firma} als {format.upper()} exportiert: {path.name}."
        }

    @mcp.tool()
    def profil_report_exportieren(
        format: str = "pdf",
        bereiche: str = ""
    ) -> dict:
        """Exportiert einen vollständigen Profil-Report als PDF.

        Enthält alle Profildaten: persönliche Daten, Zusammenfassung,
        Berufserfahrung mit Projekten (STAR-Format), Skills als Tabelle,
        Ausbildung und Dokumente. Inklusive Erstellungsdatum im Footer.

        Args:
            format: 'pdf' (Standard). Weitere Formate später.
            bereiche: Optional — kommaseparierte Liste: persönlich,positionen,skills,ausbildung,dokumente (leer = alle)
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein Profil vorhanden."}

        export_dir = get_data_dir() / "export"
        export_dir.mkdir(exist_ok=True)
        name_slug = (profile.get("name") or "profil").replace(" ", "_").lower()

        if format != "pdf":
            return {"fehler": "Aktuell wird nur PDF unterstützt."}

        from ..export import generate_cv_pdf
        path = export_dir / f"profil_report_{name_slug}.pdf"
        generate_cv_pdf(profile, path)

        return {
            "status": "erstellt",
            "datei": str(path),
            "format": "pdf",
            "nachricht": f"Profil-Report als PDF exportiert: {path.name}. "
                         "Enthält alle Profildaten, Berufserfahrung, Skills und Ausbildung."
        }

    @mcp.tool()
    def bewerbungsbericht_exportieren(
        format: str = "pdf",
        zeitraum_von: str = "",
        zeitraum_bis: str = ""
    ) -> dict:
        """Exportiert einen professionellen Bewerbungsbericht als PDF oder Excel (#173).

        Enthält: Executive Summary, Status-Uebersicht, Quellenanalyse,
        detaillierte Bewerbungsliste, Fit-Score-Verteilung und Keyword-Analyse.
        Mit PBP-Branding und Inhaltsverzeichnis.

        Ideal fuer: Arbeitsamt-Dokumentation, eigene Analyse, Berater.

        Args:
            format: 'pdf' (Standard) oder 'excel'
            zeitraum_von: Optional: Start-Datum (YYYY-MM-DD)
            zeitraum_bis: Optional: End-Datum (YYYY-MM-DD)
        """
        profile = db.get_profile()
        stats = db.get_statistics()

        # Gather application data with job info
        apps = db.get_applications()
        for a in apps:
            if a.get("job_hash"):
                job = db.get_job(a["job_hash"])
                if job:
                    a["score"] = job.get("score", 0) + 5  # #173: +5 Score-Bonus fuer beworbene Stellen
                    a["job_source"] = job.get("source", "")
                    a["is_pinned"] = job.get("is_pinned", False)
                    a["job_description"] = job.get("description", "")
                else:
                    a["score"] = 5  # Beworbene Stelle ohne Job-Eintrag
                    a["job_source"] = a.get("source") or "importiert"
            else:
                # #173: Importierte Bewerbungen (pre-PBP, kein Job-Hash)
                a["score"] = 5
                a["job_source"] = a.get("source") or "importiert (pre-PBP)"

        # Score distribution
        all_jobs = db.get_active_jobs()
        score_dist = {}
        for j in all_jobs:
            s = j.get("score", 0)
            bracket = f"{(s // 2) * 2}-{(s // 2) * 2 + 1}"
            score_dist[bracket] = score_dist.get(bracket, 0) + 1

        # Unapplied high-score jobs
        applied_hashes = {a.get("job_hash") for a in apps if a.get("job_hash")}
        unapplied = [j for j in all_jobs if j["hash"] not in applied_hashes and j.get("score", 0) >= 5]
        unapplied.sort(key=lambda j: -j.get("score", 0))

        # Date range
        dates = [a.get("applied_at") for a in apps if a.get("applied_at")]
        date_range = {"first": min(dates) if dates else "", "last": max(dates) if dates else ""}

        report_data = {
            "applications": apps,
            "statistics": stats,
            "score_distribution": score_dist,
            "unapplied_high_score": unapplied[:20],
            "date_range": date_range,
        }

        export_dir = get_data_dir() / "export"
        export_dir.mkdir(exist_ok=True)
        name_slug = (profile.get("name", "bericht") if profile else "bericht").replace(" ", "_").lower()

        if format == "excel":
            from ..export_report import generate_excel_report
            path = export_dir / f"bewerbungsbericht_{name_slug}.xlsx"
            generate_excel_report(report_data, profile, path)
        else:
            from ..export_report import generate_application_report
            path = export_dir / f"bewerbungsbericht_{name_slug}.pdf"
            generate_application_report(report_data, profile, path,
                                        zeitraum_von=zeitraum_von,
                                        zeitraum_bis=zeitraum_bis)

        return {
            "status": "erstellt",
            "datei": str(path),
            "format": format,
            "bewerbungen": len(apps),
            "nachricht": f"Bewerbungsbericht als {format.upper()} exportiert: {path.name}."
        }

    @mcp.tool()
    def lebenslauf_bewerten(
        stelle: str,
        firma: str,
        stellenbeschreibung: str = "",
        gewicht_personalberater: float = 0.33,
        gewicht_ats: float = 0.34,
        gewicht_recruiter: float = 0.33
    ) -> dict:
        """Bewertet den Lebenslauf aus 3 Experten-Perspektiven für eine bestimmte Stelle.

        Analysiert wie der CV auf einen Personalberater, ein ATS-System und einen
        HR-Recruiter wirkt. Gibt Score (0-100) pro Perspektive und konkrete
        Verbesserungsvorschläge zurück. Die Gewichtung der Perspektiven ist einstellbar.

        Auch findbar als: CV bewerten, Lebenslauf analysieren, CV check, resume review,
        3-Perspektiven-Analyse, Personalberater, ATS, Recruiter.

        Args:
            stelle: Stellentitel (z.B. 'Software Architect')
            firma: Firmenname (z.B. 'TechCorp GmbH')
            stellenbeschreibung: Stellenbeschreibung für praezise Analyse
            gewicht_personalberater: Gewicht Personalberater-Perspektive (0.0-1.0, Standard 0.33)
            gewicht_ats: Gewicht ATS-Perspektive (0.0-1.0, Standard 0.34)
            gewicht_recruiter: Gewicht Recruiter-Perspektive (0.0-1.0, Standard 0.33)
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein Profil vorhanden. Erstelle zuerst ein Profil."}

        from ..export import analyse_cv_perspectives

        # Normalize weights
        total = gewicht_personalberater + gewicht_ats + gewicht_recruiter
        if total <= 0:
            total = 1.0
        weights = {
            "personalberater": gewicht_personalberater / total,
            "ats": gewicht_ats / total,
            "recruiter": gewicht_recruiter / total,
        }

        analysis = analyse_cv_perspectives(profile, stelle, stellenbeschreibung or stelle, weights)

        return {
            "status": "analysiert",
            "stelle": stelle,
            "firma": firma,
            **analysis,
            "naechster_schritt": "Nutze lebenslauf_angepasst_exportieren() um den optimierten CV zu erstellen. "
                                 "Oder passe dein Profil basierend auf den Empfehlungen an."
        }
