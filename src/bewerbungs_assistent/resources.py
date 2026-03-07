"""MCP Resources — 6 Datenquellen fuer Claude Desktop."""

import json


def register_resources(mcp, db, logger):
    """Registriert alle 6 MCP Resources."""

    @mcp.resource("profil://aktuell")
    def resource_profil() -> str:
        """Vollstaendiges Nutzerprofil mit allen Positionen, Skills und Dokumenten."""
        profile = db.get_profile()
        if profile is None:
            return json.dumps({"status": "kein_profil"}, ensure_ascii=False)
        return json.dumps(profile, ensure_ascii=False, indent=2, default=str)

    @mcp.resource("jobs://aktiv")
    def resource_active_jobs() -> str:
        """Alle aktiven Stellenangebote, sortiert nach Score."""
        jobs = db.get_active_jobs()
        return json.dumps(jobs, ensure_ascii=False, indent=2, default=str)

    @mcp.resource("jobs://aussortiert")
    def resource_dismissed_jobs() -> str:
        """Aussortierte Stellen mit Gruenden."""
        jobs = db.get_dismissed_jobs()
        return json.dumps(jobs, ensure_ascii=False, indent=2, default=str)

    @mcp.resource("bewerbungen://alle")
    def resource_applications() -> str:
        """Alle Bewerbungen mit Status und Timeline."""
        apps = db.get_applications()
        return json.dumps(apps, ensure_ascii=False, indent=2, default=str)

    @mcp.resource("bewerbungen://statistik")
    def resource_statistics() -> str:
        """Bewerbungsstatistiken: Conversion-Rate, Antwortzeiten."""
        stats = db.get_statistics()
        return json.dumps(stats, ensure_ascii=False, indent=2)

    @mcp.resource("config://suchkriterien")
    def resource_search_criteria() -> str:
        """Aktuelle Sucheinstellungen und Kriterien."""
        criteria = db.get_search_criteria()
        return json.dumps(criteria, ensure_ascii=False, indent=2)
