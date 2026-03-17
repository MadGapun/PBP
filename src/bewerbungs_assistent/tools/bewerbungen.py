"""Bewerbungs-Management — 4 Tools."""

import hashlib


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
            status: offen, beworben, eingangsbestaetigung, interview, zweitgespraech, angebot, abgelehnt, zurueckgezogen, abgelaufen
            applied_at: Bewerbungsdatum (YYYY-MM-DD, Standard: heute)
            notes: Notizen
            bewerbungsart: mit_dokumenten, elektronisch, ueber_portal
            lebenslauf_variante: standard, angepasst, keiner
            ansprechpartner: Name des Ansprechpartners
            kontakt_email: E-Mail des Ansprechpartners
            portal_name: Name des Portals (bei bewerbungsart=ueber_portal)
        """
        # Check for duplicate applications (#63)
        existing_apps = db.get_applications()
        for existing in existing_apps:
            if (existing.get("company", "").lower() == company.lower() and
                    existing.get("title", "").lower() == title.lower()):
                return {
                    "status": "duplikat",
                    "bestehende_bewerbung_id": existing["id"],
                    "nachricht": f"Es gibt bereits eine Bewerbung bei {company} fuer '{title}' "
                                 f"(Status: {existing.get('status', '?')}). "
                                 "Nutze bewerbung_bearbeiten() um diese zu aktualisieren."
                }

        # If no job_hash given, create a manual job entry so it appears in stellen_anzeigen
        effective_hash = job_hash or None
        if not effective_hash:
            effective_hash = hashlib.md5(f"manuell:{company}:{title}:{url}".encode()).hexdigest()[:12]
            # Check if job already exists
            existing = db.get_job(effective_hash)
            if not existing:
                from datetime import datetime
                db.save_jobs([{
                    "hash": effective_hash,
                    "title": title,
                    "company": company,
                    "location": "",
                    "url": url,
                    "source": "manuell",
                    "description": notes or "",
                    "score": 0,
                    "is_pinned": True,
                    "remote_level": "unbekannt",
                    "employment_type": "festanstellung",
                    "found_at": datetime.now().isoformat(),
                }])

        aid = db.add_application({
            "title": title, "company": company, "url": url,
            "job_hash": effective_hash, "status": status,
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
            "job_hash": effective_hash,
            "nachricht": f"Bewerbung bei {company} fuer '{title}' erfasst ({bewerbungsart})."
        }

    @mcp.tool()
    def bewerbung_status_aendern(
        bewerbung_id: str,
        neuer_status: str,
        notizen: str = "",
        ablehnungsgrund: str = ""
    ) -> dict:
        """Aendert den Status einer Bewerbung (Bewerbungsstatus aendern/aktualisieren).

        Auch findbar als: status aendern, bewerbung aktualisieren, application status update,
        interview eingetragen, absage melden, angebot erhalten, zurueckgezogen.

        Args:
            bewerbung_id: ID der Bewerbung
            neuer_status: offen, beworben, eingangsbestaetigung, interview, zweitgespraech, angebot, abgelehnt, zurueckgezogen, abgelaufen
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
                 angebot, abgelehnt, zurueckgezogen, abgelaufen)
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
    def bewerbung_loeschen(bewerbung_id: str, bestaetigung: bool = False) -> dict:
        """Loescht eine Bewerbung und alle zugehoerigen Events/Timeline-Eintraege.

        ACHTUNG: Diese Aktion kann nicht rueckgaengig gemacht werden!

        Args:
            bewerbung_id: ID der Bewerbung
            bestaetigung: Muss True sein um die Loeschung zu bestaetigen
        """
        if not bestaetigung:
            app = db.get_application(bewerbung_id)
            if not app:
                return {"fehler": "Bewerbung nicht gefunden."}
            return {
                "status": "bestaetigung_erforderlich",
                "bewerbung": f"{app.get('title', '')} bei {app.get('company', '')}",
                "hinweis": "Setze bestaetigung=True um die Bewerbung unwiderruflich zu loeschen."
            }
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}
        title = app.get("title", "")
        company = app.get("company", "")
        db.delete_application(bewerbung_id)
        return {
            "status": "geloescht",
            "nachricht": f"Bewerbung '{title}' bei {company} wurde geloescht."
        }

    @mcp.tool()
    def bewerbung_bearbeiten(
        bewerbung_id: str,
        title: str = "",
        company: str = "",
        url: str = "",
        notes: str = "",
        ansprechpartner: str = "",
        kontakt_email: str = "",
        portal_name: str = "",
        bewerbungsart: str = ""
    ) -> dict:
        """Bearbeitet eine bestehende Bewerbung (Felder nachtraeglich aendern/ergaenzen).

        Nur die angegebenen Felder werden geaendert, leere Felder bleiben unveraendert.

        Args:
            bewerbung_id: ID der Bewerbung
            title: Neuer Stellentitel
            company: Neuer Firmenname
            url: Neuer Link zur Stellenanzeige
            notes: Neue Notizen (ueberschreibt bisherige)
            ansprechpartner: Neuer Ansprechpartner
            kontakt_email: Neue Kontakt-E-Mail
            portal_name: Neues Portal
            bewerbungsart: Neue Bewerbungsart
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}

        updates = {}
        for key, val in [("title", title), ("company", company), ("url", url),
                         ("notes", notes), ("ansprechpartner", ansprechpartner),
                         ("kontakt_email", kontakt_email), ("portal_name", portal_name),
                         ("bewerbungsart", bewerbungsart)]:
            if val:
                updates[key] = val

        if not updates:
            return {"fehler": "Keine Aenderungen angegeben."}

        db.update_application(bewerbung_id, updates)
        return {
            "status": "aktualisiert",
            "geaenderte_felder": list(updates.keys()),
            "nachricht": f"Bewerbung bei {app.get('company', '')} aktualisiert."
        }

    @mcp.tool()
    def bewerbung_notiz(bewerbung_id: str, notiz: str) -> dict:
        """Fuegt eine Gespraechsnotiz mit Timestamp zur Bewerbungs-Timeline hinzu.

        Ideal fuer: Interview-Notizen, Telefonate, E-Mail-Zusammenfassungen,
        Feedback nach Gespraechen, naechste Schritte.

        Args:
            bewerbung_id: ID der Bewerbung
            notiz: Die Notiz (wird mit aktuellem Datum/Uhrzeit gespeichert)
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}

        db.add_application_note(bewerbung_id, notiz)
        return {
            "status": "gespeichert",
            "nachricht": f"Notiz zu '{app.get('title', '')}' bei {app.get('company', '')} hinzugefuegt.",
            "timeline_eintraege": len(app.get("events", [])) + 1
        }

    @mcp.tool()
    def bewerbung_details(bewerbung_id: str) -> dict:
        """Zeigt alle Details einer Bewerbung: Stellenbeschreibung, Timeline, Notizen, Dokumente.

        Das vollstaendige Dossier — alles auf einen Blick fuer Interview-Vorbereitung.

        Args:
            bewerbung_id: ID der Bewerbung
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}

        result = {
            "id": app["id"],
            "titel": app.get("title", ""),
            "firma": app.get("company", ""),
            "status": app.get("status", ""),
            "datum": app.get("applied_at", ""),
            "url": app.get("url", ""),
            "bewerbungsart": app.get("bewerbungsart", ""),
            "ansprechpartner": app.get("ansprechpartner", ""),
            "kontakt_email": app.get("kontakt_email", ""),
            "notizen": app.get("notes", ""),
        }
        if app.get("stellenbeschreibung"):
            result["stellenbeschreibung"] = app["stellenbeschreibung"]
        if app.get("events"):
            result["timeline"] = [
                {
                    "datum": e.get("event_date", ""),
                    "status": e.get("status", ""),
                    "notiz": e.get("notes", ""),
                }
                for e in app["events"]
            ]
        return result

    @mcp.tool()
    def statistiken_abrufen() -> dict:
        """Ruft Bewerbungsstatistiken ab: Conversion-Rate, Antwortzeiten, Status-Verteilung.

        Gibt einen Ueberblick ueber:
        - Gesamtzahl Bewerbungen und aktive Stellen
        - Bewerbungen nach Status (beworben, interview, angebot, etc.)
        - Interview-Rate (% der Bewerbungen die zum Interview fuehren)
        """
        return db.get_statistics()
