"""PDF/DOCX-Export für Lebenslauf, Anschreiben und Profil-Report — 5 Tools."""

from ..services import ablage


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


def _auto_save_stilarchiv(db, kind: str, content: str, firma: str, stelle: str):
    """Legt nach einem Export automatisch eine Stilarchiv-Version an (#734).

    'Letzte Version gewinnt' pro (Bewerbung bzw. Titel, kind) via
    upsert_document_version — so stapeln sich nicht beliebig viele
    Versionen pro Bewerbung. Verlinkt die Bewerbung, wenn eine zu
    Firma+Stelle existiert. Komplett non-critical (Export schlaegt nie
    daran fehl). Gibt die Version-ID zurueck oder None.
    """
    if not content or not content.strip():
        return None
    try:
        title = " — ".join(t for t in (firma, stelle) if t) or "ohne Titel"
        application_id = None
        pid = db.get_active_profile_id()
        conn = db.connect()
        if firma and stelle:
            row = conn.execute(
                "SELECT id FROM applications WHERE company LIKE ? AND title LIKE ? "
                "AND (profile_id=? OR profile_id IS NULL) "
                "ORDER BY created_at DESC LIMIT 1",
                (f"%{firma}%", f"%{stelle}%", pid),
            ).fetchone()
            if row:
                application_id = row["id"]
        return db.upsert_document_version({
            "kind": kind,
            "title": title,
            "content": content,
            "application_id": application_id,
            "notes": "Automatisch beim Export archiviert (#734).",
        })
    except Exception:
        return None  # Non-critical feature


def register(mcp, db, logger):
    from . import ki_gate
    """Registriert Export-Tools."""

    @mcp.tool()
    def termine_ics_exportieren() -> dict:
        """Exportiert alle geplanten Bewerbungstermine als .ics-Kalenderdatei
        (J4.1/#481, v1.8.0-beta.3).

        Die Datei laesst sich in Thunderbird, Outlook, Apple- oder
        Google-Kalender importieren (Doppelklick reicht meist). Enthalten
        sind alle Termine mit Status 'geplant': Titel + Firma, Zeitraum,
        Ort, Meeting-Link und ein Ruecklink in die PBP-Bewerbung.

        RFC-5545-fest (Escaping + Line-Folding) — identischer Kern wie der
        Download-Button im Kalender-Tab (`/api/meetings/export.ics`).
        """
        from ..services.ics_service import build_meetings_ics
        ics_content, anzahl = build_meetings_ics(db)
        if anzahl == 0:
            return {
                "status": "leer",
                "hinweis": (
                    "Keine geplanten Termine vorhanden. Termine entstehen "
                    "aus E-Mail-Analyse oder via meeting_hinzufuegen()."
                ),
            }
        export_dir = ablage.ausgabe_ordner(db)
        vorlagen_befund: dict = {}
        path = export_dir / "pbp-termine.ics"
        path.write_text(ics_content, encoding="utf-8", newline="")
        return {
            "status": "exportiert",
            "datei": str(path),
            "termine": anzahl,
            "hinweis": (
                "Import: Datei im Kalender-Programm oeffnen (Doppelklick) "
                "oder in Thunderbird/Outlook importieren. Alternativ gibt "
                "es den Download-Button im PBP-Kalender-Tab."
            ),
        }

    @mcp.tool()
    def lebenslauf_exportieren(
        format: str = "docx",
        angepasst_für: str = ""
    ) -> dict:
        """Exportiert den Lebenslauf als DOCX (Default), PDF, Markdown oder TXT-Datei.

        Erzeugt ein professionell formatiertes Dokument aus dem gespeicherten Profil.
        Die Datei landet im eingestellten Ausgabe-Ordner (#973) —
        ohne Einstellung im Datenordner von PBP. Die Antwort nennt
        immer den tatsaechlichen Pfad.

        Default ist DOCX, weil ein direkt generiertes PDF typischerweise an Schrift,
        Layout und Formulierung als KI-generiert erkennbar ist. DOCX erlaubt es dir,
        das Dokument im eigenen Template nachzubearbeiten und erst dann zu finalisieren.

        Args:
            format: 'docx' (empfohlen), 'pdf', 'md' (Markdown) oder 'txt' (Klartext)
            angepasst_für: Optional — Firma/Stelle für die der CV angepasst wird (für Dateinamen)
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein Profil vorhanden. Erstelle zuerst ein Profil mit der Ersterfassung."}

        export_dir = ablage.ausgabe_ordner(db)
        vorlagen_befund: dict = {}
        name_slug = (profile.get("name") or "lebenslauf").replace(" ", "_").lower()
        suffix = f"_{angepasst_für.replace(' ', '_').lower()}" if angepasst_für else ""

        if format == "docx":
            from ..export import generate_cv_docx
            path = export_dir / f"lebenslauf_{name_slug}{suffix}.docx"
            _vorlage, _ = ablage.vorlage_finden(db, "lebenslauf")
            generate_cv_docx(profile, path, vorlage=_vorlage,
                             befund=vorlagen_befund)
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

        result = {
            "vorlage": vorlagen_befund or None,
            "status": "erstellt",
            "datei": str(path),
            "format": format,
            "ordner": str(export_dir),
            "nachricht": f"Lebenslauf als {format.upper()} exportiert: "
                         f"{path.name}. " + ablage.ziel_hinweis(db, path)
        }
        if format == "pdf":
            result["empfehlung"] = (
                "DOCX ist fuer Bewerbungen in der Regel besser geeignet: "
                "DOCX manuell im eigenen Template nachbearbeiten und erst dann als PDF speichern. "
                "Direkt generierte PDFs wirken haeufig KI-generiert."
            )
        return result

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
        gate = ki_gate(db, "bewerbungserstellung")
        if gate is not None:
            gate["alternative"] = (
                "Standard-Lebenslauf (ohne KI-Anpassung) via "
                "lebenslauf_exportieren bleibt jederzeit nutzbar."
            )
            return gate
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein Profil vorhanden. Erstelle zuerst ein Profil mit der Ersterfassung."}

        from ..export import generate_tailored_cv_docx

        export_dir = ablage.ausgabe_ordner(db)
        vorlagen_befund: dict = {}
        name_slug = (profile.get("name") or "lebenslauf").replace(" ", "_").lower()
        firma_slug = (firma or "stelle").replace(" ", "_").lower()

        path = export_dir / f"lebenslauf_{name_slug}_{firma_slug}.docx"
        _vorlage, _ = ablage.vorlage_finden(db, "lebenslauf")
        generate_tailored_cv_docx(profile, stelle, stellenbeschreibung, path,
                                  vorlage=_vorlage, befund=vorlagen_befund)

        # #172: Stellenbeschreibung automatisch speichern
        if stellenbeschreibung:
            _auto_save_job_description(db, firma, stelle, stellenbeschreibung)

        return {
            # Leer heisst: dieser Zweig hat kein DOCX gebaut (PDF, MD, TXT).
            # `None` ist hier "nicht anwendbar", nicht "keine Vorlage" —
            # der Unterschied steht im Befund selbst (#989).
            "vorlage": vorlagen_befund or None,
            "status": "erstellt",
            "datei": str(path),
            "format": "docx",
            "ordner": str(export_dir),
            "nachricht": f"Angepasster Lebenslauf für '{stelle}' bei {firma} "
                         f"als DOCX exportiert: {path.name}. "
                         + ablage.ziel_hinweis(db, path)
        }

    @mcp.tool()
    def fachprofil_exportieren(
        stelle: str,
        firma: str,
        stellenbeschreibung: str = "",
        projekte_anzahl: int = 5,
        format: str = "docx",
    ) -> dict:
        """v1.7.0-beta.53 (#617): Kombiniertes Dokument 'Fachprofil & Referenzprojekte'.

        Anders als `lebenslauf_angepasst_exportieren` (Lebenslauf-
        Format mit inline-Projekten unter Stationen) zieht dieses Tool
        die Projekte als eigene prominente Sektion heraus — nach
        Stellen-Relevanz sortiert und ausfuehrlicher dargestellt.

        Aufbau:
        1. Header (Name + Zielposition + Kontakt)
        2. Kurzprofil (3-4 Saetze)
        3. Kernkompetenzen (priorisiert nach Stellen-Match)
        4. Referenzprojekte (Top-N, ausfuehrlich)
        5. Berufliche Stationen (kompakt, ohne Projekt-Inline)
        6. Ausbildung

        Sinnvoll fuer:
        - Direktkontakte ueber LinkedIn/XING wo ein einzelnes Dokument
          kompakter wirkt als CV + separate Projektliste
        - Freelance-Anfragen ohne formelle Ausschreibung
        - Vorstellung beim ersten Recruiter-Gespraech

        Args:
            stelle: Zielposition (z.B. 'Senior PLM Architect')
            firma: Zielfirma (z.B. 'ACME GmbH')
            stellenbeschreibung: Optional — fuer bessere Projekt-Priorisierung
            projekte_anzahl: Top-N relevanteste Projekte (Default 5)
            format: 'docx' (empfohlen, manuell nachbearbeitbar) oder 'pdf'

        Returns:
            status, datei, format, nachricht.
        """
        gate = ki_gate(db, "bewerbungserstellung")
        if gate is not None:
            return gate
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein Profil vorhanden. Erstelle zuerst ein Profil."}
        if format not in ("docx", "pdf"):
            return {"fehler": "format muss 'docx' oder 'pdf' sein."}

        from ..export import generate_fachprofil_docx

        export_dir = ablage.ausgabe_ordner(db)
        vorlagen_befund: dict = {}
        name_slug = (profile.get("name") or "fachprofil").replace(" ", "_").lower()
        firma_slug = (firma or "stelle").replace(" ", "_").lower()

        path = export_dir / f"fachprofil_{name_slug}_{firma_slug}.{format}"
        if format == "docx":
            _vorlage, _ = ablage.vorlage_finden(db, "fachprofil")
            generate_fachprofil_docx(
                profile, stelle, firma, stellenbeschreibung,
                projekte_anzahl, path,
                vorlage=_vorlage, befund=vorlagen_befund,
            )
        else:
            # format == 'pdf': generiert DOCX als Zwischenstufe
            from ..export import generate_fachprofil_pdf
            actual = generate_fachprofil_pdf(
                profile, stelle, firma, stellenbeschreibung,
                projekte_anzahl, path,
            )
            path = actual

        # Stellenbeschreibung in DB speichern (analog #172)
        if stellenbeschreibung:
            _auto_save_job_description(db, firma, stelle, stellenbeschreibung)

        return {
            # Leer heisst: dieser Zweig hat kein DOCX gebaut (PDF, MD, TXT).
            # `None` ist hier "nicht anwendbar", nicht "keine Vorlage" —
            # der Unterschied steht im Befund selbst (#989).
            "vorlage": vorlagen_befund or None,
            "status": "erstellt",
            "datei": str(path),
            "format": format,
            "projekte_anzahl_genutzt": projekte_anzahl,
            "nachricht": (
                f"Fachprofil & Referenzprojekte fuer '{stelle}' bei {firma} "
                f"als {format.upper()} exportiert: {path.name}. "
                "Top-Projekte wurden nach Stellen-Relevanz priorisiert. "
                "Bei DOCX bitte vor dem Versenden manuell pruefen "
                "(Layout, Formulierungen). " + ablage.ziel_hinweis(db, path)
            ),
            "ordner": str(export_dir),
        }

    @mcp.tool()
    def anschreiben_exportieren(
        text: str,
        stelle: str,
        firma: str,
        format: str = "docx",
        stellenbeschreibung: str = ""
    ) -> dict:
        """Exportiert ein Anschreiben als DOCX (Default), PDF, Markdown oder TXT-Datei.

        Nimmt den fertigen Anschreiben-Text und erzeugt ein formatiertes Dokument
        mit Absender, Datum, Betreffzeile und Text.

        Default ist DOCX, weil ein direkt generiertes PDF typischerweise an Schrift,
        Layout und Formulierung als KI-generiert erkennbar ist. DOCX erlaubt das
        manuelle Nachbearbeiten im eigenen Template vor dem Versand.

        Args:
            text: Der vollständige Anschreiben-Text (Absaetze mit Leerzeilen trennen)
            stelle: Stellentitel (z.B. 'Software Architect')
            firma: Firmenname (z.B. 'TechCorp GmbH')
            format: 'docx' (empfohlen), 'pdf', 'md' (Markdown) oder 'txt' (Klartext)
            stellenbeschreibung: Optional — wird automatisch in der DB gespeichert (#172)
        """
        gate = ki_gate(db, "bewerbungserstellung")
        if gate is not None:
            return gate
        if not text.strip():
            return {"fehler": "Kein Anschreiben-Text angegeben. Nutze den Prompt 'bewerbung_schreiben' um einen Text zu erstellen."}

        profile = db.get_profile() or {}

        export_dir = ablage.ausgabe_ordner(db)
        vorlagen_befund: dict = {}
        firma_slug = (firma or "bewerbung").replace(" ", "_").lower()

        if format == "docx":
            from ..export import generate_cover_letter_docx
            path = export_dir / f"anschreiben_{firma_slug}.docx"
            _vorlage, _ = ablage.vorlage_finden(db, "anschreiben")
            generate_cover_letter_docx(profile, text, stelle, firma, path,
                                       vorlage=_vorlage,
                                       befund=vorlagen_befund)
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

        # #734: Anschreiben automatisch im Stilarchiv ablegen (letzte
        # Version gewinnt) — damit stil_auswertung()/stilarchiv_kontext()
        # echte Daten haben, ohne dass der manuelle Schritt vergessen wird.
        _stil_vid = _auto_save_stilarchiv(db, "cover_letter", text, firma, stelle)

        result = {
            "vorlage": vorlagen_befund or None,
            "status": "erstellt",
            "datei": str(path),
            "format": format,
            "ordner": str(export_dir),
            "nachricht": f"Anschreiben fuer {stelle} bei {firma} als "
                         f"{format.upper()} exportiert: {path.name}. "
                         + ablage.ziel_hinweis(db, path)
        }
        if _stil_vid:
            result["stilarchiv_version_id"] = _stil_vid
            result["nachricht"] += " Im Stilarchiv abgelegt (#734)."
        if format == "pdf":
            result["empfehlung"] = (
                "DOCX ist fuer Bewerbungen in der Regel besser geeignet: "
                "DOCX manuell im eigenen Template nachbearbeiten und erst dann als PDF speichern. "
                "Direkt generierte PDFs wirken haeufig KI-generiert."
            )
        return result

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

        export_dir = ablage.ausgabe_ordner(db)
        vorlagen_befund: dict = {}
        name_slug = (profile.get("name") or "profil").replace(" ", "_").lower()

        if format != "pdf":
            return {"fehler": "Aktuell wird nur PDF unterstützt."}

        from ..export import generate_cv_pdf
        path = export_dir / f"profil_report_{name_slug}.pdf"
        generate_cv_pdf(profile, path)

        return {
            # Leer heisst: dieser Zweig hat kein DOCX gebaut (PDF, MD, TXT).
            # `None` ist hier "nicht anwendbar", nicht "keine Vorlage" —
            # der Unterschied steht im Befund selbst (#989).
            "vorlage": vorlagen_befund or None,
            "status": "erstellt",
            "datei": str(path),
            "format": "pdf",
            "ordner": str(export_dir),
            "nachricht": f"Profil-Report als PDF exportiert: {path.name}. "
                         + ablage.ziel_hinweis(db, path) + " "
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
        # Kanonische Report-Daten aus DB (inkl. rejection_patterns, follow_ups,
        # bewerbungsart-Verteilung). Keine doppelte Aggregation hier.
        report_data = db.get_report_data()
        # v1.7.10 (#781/D29): Prozess-Kennzahlen, Kanal-Erfolg,
        # Ablehnungs-Kategorien und Aufwand in den Bericht. Fehler hier
        # duerfen den Bericht nie verhindern.
        try:
            from ..services import statistik_erweitert as _se
            report_data["prozess_kennzahlen"] = _se.zeitliche_kennzahlen(db)
            report_data["kanal_auswertung"] = _se.kanal_auswertung(db)
            report_data["ablehnungs_kategorien"] = _se.ablehnungs_kategorien(db)
            report_data["aufwand"] = db.get_aufwand_summary()
        except Exception as _e:
            logger.warning("Bericht-Erweiterung (#781) fehlgeschlagen: %s", _e)
        # v1.6.6 (#540): Optionale Bericht-Einstellungen
        report_settings = {
            "arbeitsamt_block_enabled": bool(db.get_profile_setting("report_arbeitsamt_block_enabled", False)),
            "ba_vermittlungsnummer": db.get_profile_setting("report_ba_vermittlungsnummer", "") or "",
            "ba_aktenzeichen": db.get_profile_setting("report_ba_aktenzeichen", "") or "",
            "ba_berater_name": db.get_profile_setting("report_ba_berater_name", "") or "",
            "ba_berater_stelle": db.get_profile_setting("report_ba_berater_stelle", "") or "",
            "berater_kommentar_block": bool(db.get_profile_setting("report_berater_kommentar_block", False)),
        }

        export_dir = ablage.ausgabe_ordner(db)
        vorlagen_befund: dict = {}
        name_slug = (profile.get("name", "bericht") if profile else "bericht").replace(" ", "_").lower()

        if format == "excel":
            from ..export_report import generate_excel_report
            path = export_dir / f"bewerbungsbericht_{name_slug}.xlsx"
            generate_excel_report(report_data, profile, path,
                                  zeitraum_von=zeitraum_von,
                                  zeitraum_bis=zeitraum_bis,
                                  report_settings=report_settings)
        else:
            from ..export_report import generate_application_report
            path = export_dir / f"bewerbungsbericht_{name_slug}.pdf"
            generate_application_report(report_data, profile, path,
                                        zeitraum_von=zeitraum_von,
                                        zeitraum_bis=zeitraum_bis,
                                        report_settings=report_settings)

        return {
            # Leer heisst: dieser Zweig hat kein DOCX gebaut (PDF, MD, TXT).
            # `None` ist hier "nicht anwendbar", nicht "keine Vorlage" —
            # der Unterschied steht im Befund selbst (#989).
            "vorlage": vorlagen_befund or None,
            "status": "erstellt",
            "datei": str(path),
            "format": format,
            "bewerbungen": len(report_data.get("applications", [])),
            "ordner": str(export_dir),
            "nachricht": f"Bewerbungsbericht als {format.upper()} exportiert: "
                         f"{path.name}. " + ablage.ziel_hinweis(db, path)
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
            stellenbeschreibung: Stellenbeschreibung für präzise Analyse
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

    @mcp.tool()
    def ablage_ordner(art: str = "", pfad: str = "") -> dict:
        """Wohin PBP schreibt und woher es die Vorlage nimmt (#973).

        Ohne Argumente: zeigt beide Ordner und was daraus folgt.

        Args:
            art: 'ausgabe' (wohin erzeugte Dateien gehen) oder
                'vorlagen' (wo deine DOCX-Vorlagen liegen).
            pfad: der vollstaendige Ordnerpfad. '-' loescht die
                Einstellung und stellt das bisherige Verhalten wieder her.

        **Ausgabe-Ordner:** ist er gesetzt, landen Lebenslauf,
        Anschreiben, Fachprofil, Berichte und Profil-Sicherungen direkt
        dort statt im Datenordner von PBP. Kein Umkopieren mehr.

        **Vorlagen-Ordner:** liegt dort eine `lebenslauf.docx`,
        `anschreiben.docx` oder `fachprofil.docx`, baut PBP das Dokument
        AUF DIESER GRUNDLAGE — Schriften, Raender sowie Kopf- und
        Fusszeilen bleiben deine. Fehlt eine Datei, gilt fuer sie das
        eingebaute Layout.

        Ein Pfad, den es nicht gibt, wird ABGEWIESEN und nicht
        gespeichert: eine Einstellung, an die man glaubt und die nichts
        tut, ist schlimmer als keine.
        """
        wahl = (art or "").strip().lower()
        if not wahl:
            return ablage.uebersicht(db)
        if wahl not in ablage.ARTEN:
            return {
                "fehler": "art muss 'ausgabe' oder 'vorlagen' sein "
                          "(oder leer bleiben zum Anzeigen).",
                "aktueller_stand": ablage.uebersicht(db),
            }
        wert = (pfad or "").strip()
        if wert == "-":
            wert = ""
        return ablage.ordner_setzen(db, wahl, wert)

    @mcp.tool()
    def dokument_regeln_pruefen(pfad: str = "") -> dict:
        """Prueft ein erzeugtes Dokument gegen die Versand-Regeln (#1006).

        Args:
            pfad: DOCX-Datei. Leer = die zuletzt geaenderte DOCX-Datei im
                Ausgabe-Ordner — also im Normalfall genau das, was gerade
                erzeugt wurde.

        Geprueft wird das ERGEBNIS, nicht der Quelltext: Platzhalter im
        Text (`None`, `null`), Gedankenstriche als Satzzeichen,
        umschriebene Umlaute und dritte Person im Kurzprofil.

        Zwei Dinge, die das Werkzeug bewusst NICHT tut: es schreibt keine
        Prosa um (aus "Er verfuegt ueber" wird maschinell kein guter
        Satz), und es meldet einen Bis-Strich zwischen zwei Datumsangaben
        nicht als Fehler — der ist typografisch richtig. Ein Pruefer, der
        bei korrektem Ergebnis Alarm gibt, wird nach dem zweiten Mal
        ignoriert.

        Auch fuer eigene Vorlagen nutzbar: `pfad` auf die Vorlage zeigen
        lassen, dann sagt PBP, was an ihr den Regeln widerspricht.
        """
        from pathlib import Path
        from ..services import dokument_regeln

        ziel = (pfad or "").strip().strip('"')
        if not ziel:
            ordner = ablage.ausgabe_ordner(db)
            kandidaten = sorted(
                (p for p in ordner.glob("*.docx") if p.is_file()),
                key=lambda p: p.stat().st_mtime, reverse=True)
            if not kandidaten:
                return {
                    "status": "nichts_zu_pruefen",
                    "ordner": str(ordner),
                    "hinweis": "Im Ausgabe-Ordner liegt keine DOCX-Datei. "
                               "Erzeuge zuerst eine (lebenslauf_exportieren) "
                               "oder gib einen Pfad an.",
                }
            ziel = str(kandidaten[0])

        ergebnis = dokument_regeln.pruefe_docx(Path(ziel))
        if "fehler" in ergebnis:
            return ergebnis
        if ergebnis["sauber"]:
            ergebnis["hinweis"] = (
                "Keine Regelverstoesse gefunden — das Dokument ist ohne "
                "Nachformatierung versandfaehig.")
        else:
            hart = [b for b in ergebnis["befunde"] if not b.get("weich")]
            ergebnis["hinweis"] = (
                f"{len(hart)} Befund(e), die vor dem Versand gehoeren. "
                "Regel 8 (dritte Person) betrifft deinen Profiltext und "
                "wird bewusst nicht automatisch umgeschrieben.")
        return ergebnis

