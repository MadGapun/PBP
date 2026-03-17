"""Bewerbungs-Management — 4 Tools."""


def register(mcp, db, logger):
    """Registriert Bewerbungs-Tools."""

    @mcp.tool()
    def bewerbung_erstellen(
        title: str,
        company: str,
        url: str = "",
        job_hash: str = "",
        status: str = "beworben",
        applied_at: str = "",
        notes: str = "",
        bewerbungsart: str = "mit_dokumenten",
        lebenslauf_variante: str = "standard",
        ansprechpartner: str = "",
        kontakt_email: str = "",
        portal_name: str = ""
    ) -> dict:
        """Erstellt eine neue Bewerbung (manuell oder aus einer gefundenen Stelle).

        Args:
            title: Stellentitel
            company: Firmenname
            url: Link zur Stellenanzeige
            job_hash: Optional: Hash einer gefundenen Stelle
            status: offen, beworben, eingangsbestaetigung, interview, zweitgespraech, angebot, abgelehnt, zurueckgezogen
            applied_at: Bewerbungsdatum (YYYY-MM-DD, Standard: heute)
            notes: Notizen
            bewerbungsart: mit_dokumenten, elektronisch, ueber_portal
            lebenslauf_variante: standard, angepasst, keiner
            ansprechpartner: Name des Ansprechpartners
            kontakt_email: E-Mail des Ansprechpartners
            portal_name: Name des Portals (bei bewerbungsart=ueber_portal)
        """
        aid = db.add_application({
            "title": title, "company": company, "url": url,
            "job_hash": job_hash or None, "status": status,
            "applied_at": applied_at, "notes": notes,
            "bewerbungsart": bewerbungsart,
            "lebenslauf_variante": lebenslauf_variante,
            "ansprechpartner": ansprechpartner,
            "kontakt_email": kontakt_email,
            "portal_name": portal_name,
        })
        return {
            "status": "erstellt",
            "bewerbung_id": aid,
            "nachricht": f"Bewerbung bei {company} fuer '{title}' erfasst ({bewerbungsart})."
        }

    @mcp.tool()
    def bewerbung_status_aendern(
        bewerbung_id: str,
        neuer_status: str,
        notizen: str = "",
        ablehnungsgrund: str = ""
    ) -> dict:
        """Aendert den Status einer Bewerbung.

        Args:
            bewerbung_id: ID der Bewerbung
            neuer_status: offen, beworben, eingangsbestaetigung, interview, zweitgespraech, angebot, abgelehnt, zurueckgezogen
            notizen: Optionale Notizen zum Statuswechsel
            ablehnungsgrund: Grund der Ablehnung (nur bei status=abgelehnt). Wird fuer Musteranalyse gespeichert.
        """
        db.update_application_status(bewerbung_id, neuer_status, notizen, ablehnungsgrund)
        result = {"status": "aktualisiert", "neuer_status": neuer_status}
        if neuer_status == "abgelehnt":
            result["hinweis"] = "Nutze ablehnungs_muster() um Ablehnungsmuster zu analysieren und daraus zu lernen."
        return result

    @mcp.tool()
    def bewerbungen_anzeigen(status_filter: str = "") -> dict:
        """Zeigt alle erfassten Bewerbungen mit Status und Timeline.

        Args:
            status_filter: Optional: Nur Bewerbungen mit diesem Status
                (offen, beworben, eingangsbestaetigung, interview, zweitgespraech,
                 angebot, abgelehnt, zurueckgezogen)
        """
        apps = db.get_applications(status_filter if status_filter else None)

        if not apps:
            return {
                "anzahl": 0,
                "nachricht": "Noch keine Bewerbungen erfasst. "
                             "Erstelle eine neue Bewerbung mit bewerbung_erstellen() oder "
                             "nutze den Prompt 'bewerbung_schreiben' fuer eine gefuehrte Bewerbung."
            }

        formatted = []
        for a in apps:
            entry = {
                "id": a["id"],
                "titel": a.get("title", ""),
                "firma": a.get("company", ""),
                "status": a.get("status", ""),
                "bewerbungsart": a.get("bewerbungsart", ""),
                "datum": a.get("applied_at", ""),
                "events": len(a.get("events", [])),
            }
            if a.get("ansprechpartner"):
                entry["ansprechpartner"] = a["ansprechpartner"]
            if a.get("kontakt_email"):
                entry["kontakt_email"] = a["kontakt_email"]
            if a.get("notes"):
                entry["notizen"] = a["notes"][:200]
            formatted.append(entry)

        stats = db.get_statistics()
        return {
            "anzahl": len(apps),
            "bewerbungen": formatted,
            "statistik": {
                "gesamt": stats.get("total_applications", 0),
                "nach_status": stats.get("applications_by_status", {}),
                "interview_rate": stats.get("interview_rate", 0),
            },
            "hinweis": "Nutze bewerbung_status_aendern(id, status, notizen) um den Status zu aktualisieren."
        }

    @mcp.tool()
    def statistiken_abrufen() -> dict:
        """Ruft Bewerbungsstatistiken ab: Conversion-Rate, Antwortzeiten, Status-Verteilung.

        Gibt einen Ueberblick ueber:
        - Gesamtzahl Bewerbungen und aktive Stellen
        - Bewerbungen nach Status (beworben, interview, angebot, etc.)
        - Interview-Rate (% der Bewerbungen die zum Interview fuehren)
        """
        return db.get_statistics()
