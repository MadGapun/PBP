"""PDF/DOCX-Export fuer Lebenslauf und Anschreiben — 2 Tools."""

from ..database import get_data_dir


def register(mcp, db, logger):
    """Registriert Export-Tools."""

    @mcp.tool()
    def lebenslauf_exportieren(
        format: str = "pdf",
        angepasst_fuer: str = ""
    ) -> dict:
        """Exportiert den Lebenslauf als PDF oder DOCX-Datei.

        Erzeugt ein professionell formatiertes Dokument aus dem gespeicherten Profil.
        Die Datei wird im Bewerbungs-Assistent Datenordner gespeichert.

        Args:
            format: 'pdf' oder 'docx'
            angepasst_fuer: Optional — Firma/Stelle fuer die der CV angepasst wird (fuer Dateinamen)
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein Profil vorhanden. Erstelle zuerst ein Profil mit der Ersterfassung."}

        from ..export import generate_cv_docx, generate_cv_pdf

        export_dir = get_data_dir() / "export"
        export_dir.mkdir(exist_ok=True)
        name_slug = (profile.get("name") or "lebenslauf").replace(" ", "_").lower()
        suffix = f"_{angepasst_fuer.replace(' ', '_').lower()}" if angepasst_fuer else ""

        if format == "docx":
            path = export_dir / f"lebenslauf_{name_slug}{suffix}.docx"
            generate_cv_docx(profile, path)
        elif format == "pdf":
            path = export_dir / f"lebenslauf_{name_slug}{suffix}.pdf"
            generate_cv_pdf(profile, path)
        else:
            return {"fehler": "Format muss 'pdf' oder 'docx' sein."}

        return {
            "status": "erstellt",
            "datei": str(path),
            "format": format,
            "nachricht": f"Lebenslauf als {format.upper()} exportiert: {path.name}. "
                         "Die Datei liegt im Bewerbungs-Assistent Datenordner. "
                         "Du kannst sie auch im Dashboard unter http://localhost:5173 herunterladen."
        }

    @mcp.tool()
    def anschreiben_exportieren(
        text: str,
        stelle: str,
        firma: str,
        format: str = "pdf"
    ) -> dict:
        """Exportiert ein Anschreiben als PDF oder DOCX-Datei.

        Nimmt den fertigen Anschreiben-Text und erzeugt ein formatiertes Dokument
        mit Absender, Datum, Betreffzeile und Text.

        Args:
            text: Der vollstaendige Anschreiben-Text (Absaetze mit Leerzeilen trennen)
            stelle: Stellentitel (z.B. 'PLM Consultant')
            firma: Firmenname (z.B. 'Siemens')
            format: 'pdf' oder 'docx'
        """
        if not text.strip():
            return {"fehler": "Kein Anschreiben-Text angegeben. Nutze den Prompt 'bewerbung_schreiben' um einen Text zu erstellen."}

        profile = db.get_profile() or {}

        from ..export import generate_cover_letter_docx, generate_cover_letter_pdf

        export_dir = get_data_dir() / "export"
        export_dir.mkdir(exist_ok=True)
        firma_slug = (firma or "bewerbung").replace(" ", "_").lower()

        if format == "docx":
            path = export_dir / f"anschreiben_{firma_slug}.docx"
            generate_cover_letter_docx(profile, text, stelle, firma, path)
        elif format == "pdf":
            path = export_dir / f"anschreiben_{firma_slug}.pdf"
            generate_cover_letter_pdf(profile, text, stelle, firma, path)
        else:
            return {"fehler": "Format muss 'pdf' oder 'docx' sein."}

        return {
            "status": "erstellt",
            "datei": str(path),
            "format": format,
            "nachricht": f"Anschreiben fuer {stelle} bei {firma} als {format.upper()} exportiert: {path.name}."
        }
