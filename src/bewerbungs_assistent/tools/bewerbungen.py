"""Bewerbungs-Management — 9 Tools (#170: gefuehrter Workflow)."""

import hashlib


# Status-zu-Aktionen Mapping (#170): Kontextabhaengige Aktionen pro Status
# Jeder Status zeigt dem User genau die Aktionen die JETZT relevant sind.
STATUS_ACTIONS = {
    "in_vorbereitung": {
        "beschreibung": "Du bereitest dich auf diese Bewerbung vor. Hier sind deine naechsten Schritte:",
        "aktionen": [
            {"label": "Fit-Analyse durchfuehren", "tool": "fit_analyse", "prioritaet": 1},
            {"label": "Skill-Gap-Analyse", "tool": "skill_gap_analyse", "prioritaet": 2},
            {"label": "Lebenslauf anpassen", "tool": "lebenslauf_angepasst_exportieren", "prioritaet": 3},
            {"label": "Lebenslauf bewerten lassen", "tool": "lebenslauf_bewerten", "prioritaet": 4},
            {"label": "Anschreiben erstellen", "tool": "anschreiben_exportieren", "prioritaet": 5},
            {"label": "Firmen-Recherche", "tool": "firmen_recherche", "prioritaet": 6},
            {"label": "Dokument verknuepfen", "tool": "dokument_verknuepfen", "prioritaet": 7},
            {"label": "Als 'beworben' markieren", "tool": "bewerbung_status_aendern", "status": "beworben", "prioritaet": 8},
        ],
        "motivation": "Gute Vorbereitung ist der halbe Erfolg! Nimm dir die Zeit.",
    },
    "beworben": {
        "beschreibung": "Bewerbung ist raus! Jetzt heisst es warten und vorbereitet sein.",
        "aktionen": [
            {"label": "Nachfass-Erinnerung planen", "tool": "nachfass_planen", "prioritaet": 1},
            {"label": "Notiz hinzufuegen", "tool": "bewerbung_notiz", "prioritaet": 2},
            {"label": "Eingangsbestaetigung erhalten", "tool": "bewerbung_status_aendern", "status": "eingangsbestaetigung", "prioritaet": 3},
            {"label": "Absage erhalten", "tool": "bewerbung_status_aendern", "status": "abgelehnt", "prioritaet": 9},
        ],
        "motivation": "Du hast den wichtigsten Schritt gemacht — die Bewerbung abgeschickt!",
    },
    "eingangsbestaetigung": {
        "beschreibung": "Die Firma hat deine Bewerbung erhalten. Bereite dich auf ein moegliches Interview vor!",
        "aktionen": [
            {"label": "Interview-Vorbereitung starten", "tool": "workflow_starten", "workflow": "interview_vorbereitung", "prioritaet": 1},
            {"label": "Interview-Simulation", "tool": "workflow_starten", "workflow": "interview_simulation", "prioritaet": 2},
            {"label": "Firmen-Recherche", "tool": "firmen_recherche", "prioritaet": 3},
            {"label": "Nachfass-Erinnerung planen", "tool": "nachfass_planen", "prioritaet": 4},
            {"label": "Interview-Termin erhalten", "tool": "bewerbung_status_aendern", "status": "interview", "prioritaet": 5},
            {"label": "Absage erhalten", "tool": "bewerbung_status_aendern", "status": "abgelehnt", "prioritaet": 9},
        ],
        "motivation": "Positive Zeichen! Nutze die Wartezeit fuer die Vorbereitung.",
    },
    "interview": {
        "beschreibung": "Du hast ein Interview! Jetzt zaehlt die Vorbereitung.",
        "aktionen": [
            {"label": "Interview-Vorbereitung fortsetzen", "tool": "workflow_starten", "workflow": "interview_vorbereitung", "prioritaet": 1},
            {"label": "Interview-Simulation", "tool": "workflow_starten", "workflow": "interview_simulation", "prioritaet": 2},
            {"label": "Gehaltsverhandlung vorbereiten", "tool": "workflow_starten", "workflow": "gehaltsverhandlung", "prioritaet": 3},
            {"label": "Gespraechsnotizen erfassen", "tool": "bewerbung_notiz", "prioritaet": 4},
            {"label": "Zweitgespraech erhalten", "tool": "bewerbung_status_aendern", "status": "zweitgespraech", "prioritaet": 5},
            {"label": "Angebot erhalten", "tool": "bewerbung_status_aendern", "status": "angebot", "prioritaet": 6},
            {"label": "Absage erhalten", "tool": "bewerbung_status_aendern", "status": "abgelehnt", "prioritaet": 9},
        ],
        "motivation": "Super, ein Interview! Du bist auf dem richtigen Weg.",
    },
    "zweitgespraech": {
        "beschreibung": "Du bist in der engeren Auswahl! Die Firma interessiert sich fuer dich.",
        "aktionen": [
            {"label": "Interview-Simulation (vertieft)", "tool": "workflow_starten", "workflow": "interview_simulation", "prioritaet": 1},
            {"label": "Gehaltsverhandlung vorbereiten", "tool": "workflow_starten", "workflow": "gehaltsverhandlung", "prioritaet": 2},
            {"label": "Gespraechsnotizen erfassen", "tool": "bewerbung_notiz", "prioritaet": 3},
            {"label": "Angebot erhalten", "tool": "bewerbung_status_aendern", "status": "angebot", "prioritaet": 4},
            {"label": "Absage erhalten", "tool": "bewerbung_status_aendern", "status": "abgelehnt", "prioritaet": 9},
        ],
        "motivation": "Die Firma investiert Zeit in dich — ein sehr gutes Zeichen!",
    },
    "angebot": {
        "beschreibung": "Glueckwunsch, du hast ein Angebot! Jetzt heisst es klug verhandeln.",
        "aktionen": [
            {"label": "Gehaltsverhandlung durchfuehren", "tool": "workflow_starten", "workflow": "gehaltsverhandlung", "prioritaet": 1},
            {"label": "Vertragsdetails notieren", "tool": "bewerbung_notiz", "prioritaet": 2},
            {"label": "Angebot annehmen", "tool": "bewerbung_status_aendern", "status": "angenommen", "prioritaet": 3},
            {"label": "Angebot ablehnen / zurueckziehen", "tool": "bewerbung_status_aendern", "status": "zurueckgezogen", "prioritaet": 9},
        ],
        "motivation": "Fantastisch! Du hast es geschafft. Nimm dir Zeit fuer die Entscheidung.",
    },
    "abgelehnt": {
        "beschreibung": "Eine Absage ist hart, aber jede bringt dich naeher ans Ziel.",
        "aktionen": [
            {"label": "Ablehnungsmuster analysieren", "tool": "ablehnungs_muster", "prioritaet": 1},
            {"label": "Rueckfrage an Firma formulieren", "tool": "antwort_formulieren", "prioritaet": 2},
            {"label": "Aehnliche Stellen suchen", "tool": "stellen_anzeigen", "prioritaet": 3},
            {"label": "Neue Jobsuche starten", "tool": "jobsuche_starten", "prioritaet": 4},
        ],
        "motivation": "Kopf hoch! Absagen gehoeren dazu. Schau was du daraus lernen kannst.",
    },
    "offen": {
        "beschreibung": "Diese Bewerbung ist offen. Was moechtest du als naechstes tun?",
        "aktionen": [
            {"label": "Bewerbung vorbereiten", "tool": "bewerbung_status_aendern", "status": "in_vorbereitung", "prioritaet": 1},
            {"label": "Als beworben markieren", "tool": "bewerbung_status_aendern", "status": "beworben", "prioritaet": 2},
            {"label": "Notiz hinzufuegen", "tool": "bewerbung_notiz", "prioritaet": 3},
        ],
        "motivation": "Los geht's! Der erste Schritt ist immer der wichtigste.",
    },
}


def _get_context_actions(status: str) -> dict:
    """Gibt kontextabhaengige Aktionen fuer einen Bewerbungsstatus zurueck (#170)."""
    default = {
        "beschreibung": "Aktionen verfuegbar:",
        "aktionen": [
            {"label": "Notiz hinzufuegen", "tool": "bewerbung_notiz"},
            {"label": "Status aendern", "tool": "bewerbung_status_aendern"},
        ],
    }
    return STATUS_ACTIONS.get(status, default)


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
        portal_name: str = "",
        bereits_beworben: bool = True,
        stellenbeschreibung: str = ""
    ) -> dict:
        """Erstellt eine neue Bewerbung (manuell oder aus einer gefundenen Stelle).

        EINSTIEGSFRAGE (#170): Frage den User zuerst:
        "Hast du dich bereits beworben, oder moechtest du dich bewerben?"
        - Bereits beworben (bereits_beworben=True): Status 'beworben', Datum erfassen
        - Will mich bewerben (bereits_beworben=False): Status 'in_vorbereitung',
          direkt in Bewerbungsdetails mit naechsten Schritten

        Args:
            title: Stellentitel
            company: Firmenname
            url: Link zur Stellenanzeige
            job_hash: Optional: Hash einer gefundenen Stelle
            status: in_vorbereitung, offen, beworben, eingangsbestaetigung, interview, zweitgespraech, angebot, abgelehnt, zurueckgezogen, abgelaufen
            applied_at: Bewerbungsdatum (YYYY-MM-DD, Standard: heute)
            notes: Notizen
            bewerbungsart: mit_dokumenten, elektronisch, ueber_portal
            lebenslauf_variante: standard, angepasst, keiner
            ansprechpartner: Name des Ansprechpartners
            kontakt_email: E-Mail des Ansprechpartners
            portal_name: Name des Portals (bei bewerbungsart=ueber_portal)
            bereits_beworben: True = schon beworben (Standard), False = will mich bewerben (#170)
            stellenbeschreibung: Optional: Vollstaendige Stellenbeschreibung (#172) — wird automatisch gespeichert
        """
        # #170: Wenn der User sich noch nicht beworben hat → in_vorbereitung
        if not bereits_beworben:
            status = "in_vorbereitung"

        # Check for duplicate applications (#63)
        existing_apps = db.get_applications()
        for existing in existing_apps:
            if (existing.get("company", "").lower() == company.lower() and
                    existing.get("title", "").lower() == title.lower()):
                return {
                    "status": "duplikat",
                    "bestehende_bewerbung_id": existing["id"][:8],
                    "nachricht": f"Es gibt bereits eine Bewerbung bei {company} für '{title}' "
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
                    "description": stellenbeschreibung or notes or "",
                    "score": 0,
                    "is_pinned": True,
                    "remote_level": "unbekannt",
                    "employment_type": "festanstellung",
                    "found_at": datetime.now().isoformat(),
                }])

        # #178 Bug 1: source aus jobs-Tabelle übernehmen
        source = ""
        if effective_hash:
            linked_job = db.get_job(effective_hash)
            if linked_job:
                source = linked_job.get("source", "") or ""

        aid = db.add_application({
            "title": title, "company": company, "url": url,
            "job_hash": effective_hash, "status": status,
            "applied_at": applied_at if status != "in_vorbereitung" else "",
            "notes": notes,
            "bewerbungsart": bewerbungsart,
            "lebenslauf_variante": lebenslauf_variante,
            "ansprechpartner": ansprechpartner,
            "kontakt_email": kontakt_email,
            "portal_name": portal_name,
            "source": source,
        })

        result = {
            "status": "erstellt",
            "bewerbung_id": aid[:8],
            "bewerbung_id_voll": aid,
            "job_hash": effective_hash[:8] if effective_hash else None,
            "bewerbungsstatus": status,
            "nachricht": f"Bewerbung bei {company} für '{title}' erfasst.",
        }

        # #170: Bei in_vorbereitung direkt die nächsten Schritte zeigen
        if status == "in_vorbereitung":
            result["naechste_schritte"] = _get_context_actions("in_vorbereitung")
            result["nachricht"] += (
                " Status: in_vorbereitung — Nutze bewerbung_details() um die "
                "Bewerbung zu oeffnen und die Vorbereitung zu starten."
            )
        else:
            result["nachricht"] += f" ({bewerbungsart})"

        return result

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

        Status-Journey (#170):
        in_vorbereitung -> beworben -> eingangsbestaetigung -> interview -> zweitgespraech -> angebot -> angenommen
        (von jedem Status auch: abgelehnt, zurueckgezogen)

        Args:
            bewerbung_id: ID der Bewerbung
            neuer_status: in_vorbereitung, offen, beworben, eingangsbestaetigung, interview, zweitgespraech, angebot, angenommen, abgelehnt, zurueckgezogen, abgelaufen
            notizen: Optionale Notizen zum Statuswechsel
            ablehnungsgrund: Grund der Ablehnung (nur bei status=abgelehnt). Wird fuer Musteranalyse gespeichert.
        """
        # Bei Wechsel von in_vorbereitung zu beworben: applied_at setzen
        if neuer_status == "beworben":
            app = db.get_application(bewerbung_id)
            if app and not app.get("applied_at"):
                from datetime import datetime
                db.update_application(bewerbung_id, {"applied_at": datetime.now().isoformat()[:10]})

        db.update_application_status(bewerbung_id, neuer_status, notizen, ablehnungsgrund)
        result = {
            "status": "aktualisiert",
            "neuer_status": neuer_status,
            "naechste_aktionen": _get_context_actions(neuer_status),
        }
        if neuer_status == "abgelehnt":
            actions = _get_context_actions("abgelehnt")
            result["motivation"] = actions.get("motivation", "")
            result["hinweis"] = "Nutze ablehnungs_muster() um Ablehnungsmuster zu analysieren und daraus zu lernen."
        elif neuer_status == "angenommen":
            result["nachricht"] = "Herzlichen Glueckwunsch! Du hast es geschafft!"
        return result

    @mcp.tool()
    def bewerbungen_anzeigen(
        status_filter: str = "",
        archiv: bool = False,
        stellenart: str = "",
        sortierung: str = "datum",
    ) -> dict:
        """Zeigt erfasste Bewerbungen mit Status und Timeline.

        Standardmäßig werden zurückgezogene, abgelehnte und abgelaufene Bewerbungen
        ausgeblendet. Setze archiv=True um sie zu sehen.

        Args:
            status_filter: Optional: Nur Bewerbungen mit diesem Status
                (offen, in_vorbereitung, beworben, eingangsbestaetigung, interview,
                 zweitgespraech, angebot, angenommen, abgelehnt, zurueckgezogen, abgelaufen)
            archiv: True = auch abgelehnte/zurückgezogene/abgelaufene zeigen (Standard: False)
            stellenart: Optional: Filter nach Stellenart (festanstellung, freelance, etc.)
            sortierung: datum (Standard), firma, status, score
        """
        apps = db.get_applications(status_filter if status_filter else None)

        # #182: Archivierte Bewerbungen standardmäßig ausblenden
        ARCHIVE_STATUSES = {"abgelehnt", "zurueckgezogen", "abgelaufen"}
        if not archiv and not status_filter:
            aktive = [a for a in apps if a.get("status") not in ARCHIVE_STATUSES]
            archivierte_count = len(apps) - len(aktive)
            apps = aktive
        else:
            archivierte_count = 0

        # Stellenart-Filter (#182)
        if stellenart:
            apps = [a for a in apps if (a.get("employment_type") or "").lower() == stellenart.lower()]

        if not apps:
            return {
                "anzahl": 0,
                "nachricht": "Noch keine Bewerbungen erfasst. "
                             "Erstelle eine neue Bewerbung mit bewerbung_erstellen() oder "
                             "nutze den Prompt 'bewerbung_schreiben' für eine geführte Bewerbung."
            }

        formatted = []
        for a in apps:
            entry = {
                "id": a["id"][:8],  # #171: Kurz-ID für schnelle Referenz
                "id_voll": a["id"],
                "titel": a.get("title", ""),
                "firma": a.get("company", ""),
                "status": a.get("status", ""),
                "bewerbungsart": a.get("bewerbungsart", ""),
                "datum": a.get("applied_at", ""),
                "events": len(a.get("events", [])),
            }
            if a.get("job_hash"):
                entry["stellen_id"] = a["job_hash"][:8]  # #171
            if a.get("ansprechpartner"):
                entry["ansprechpartner"] = a["ansprechpartner"]
            if a.get("kontakt_email"):
                entry["kontakt_email"] = a["kontakt_email"]
            if a.get("notes"):
                entry["notizen"] = a["notes"][:200]
            # #170: Fortschritts-Tracking bei in_vorbereitung
            if a.get("status") == "in_vorbereitung":
                events = a.get("events", [])
                done_steps = set()
                for e in events:
                    note = (e.get("notes") or "").lower()
                    if "fit-analyse" in note or "fit_analyse" in note:
                        done_steps.add("fit_analyse")
                    if "lebenslauf" in note or "cv" in note:
                        done_steps.add("cv")
                    if "anschreiben" in note:
                        done_steps.add("anschreiben")
                    if "skill-gap" in note or "skill_gap" in note:
                        done_steps.add("skill_gap")
                entry["vorbereitung_fortschritt"] = {
                    "erledigt": len(done_steps),
                    "gesamt": 5,
                    "schritte": list(done_steps),
                }
            formatted.append(entry)

        # #182: Sortierung
        if sortierung == "firma":
            formatted.sort(key=lambda x: x.get("firma", "").lower())
        elif sortierung == "status":
            status_order = ["in_vorbereitung", "beworben", "eingangsbestaetigung",
                            "interview", "zweitgespraech", "angebot", "angenommen",
                            "offen", "abgelehnt", "zurueckgezogen", "abgelaufen"]
            formatted.sort(key=lambda x: (
                status_order.index(x.get("status", "offen"))
                if x.get("status") in status_order else 99
            ))
        else:  # datum (default) — neueste zuerst
            formatted.sort(key=lambda x: x.get("datum", ""), reverse=True)

        stats = db.get_statistics()
        result = {
            "anzahl": len(formatted),
            "bewerbungen": formatted,
            "statistik": {
                "gesamt": stats.get("total_applications", 0),
                "nach_status": stats.get("applications_by_status", {}),
                "interview_rate": stats.get("interview_rate", 0),
            },
            "hinweis": "Nutze bewerbung_status_aendern(id, status, notizen) um den Status zu aktualisieren."
        }
        # #182: Archiv-Hinweis wenn Bewerbungen ausgeblendet
        if archivierte_count > 0:
            result["archiv_hinweis"] = (
                f"{archivierte_count} archivierte Bewerbungen ausgeblendet "
                "(abgelehnt/zurückgezogen/abgelaufen). Zeige mit archiv=True."
            )
        return result

    @mcp.tool()
    def bewerbung_loeschen(bewerbung_id: str, bestaetigung: bool = False) -> dict:
        """Löscht eine Bewerbung und alle zugehörigen Events/Timeline-Einträge.

        ACHTUNG: Diese Aktion kann nicht rückgängig gemacht werden!

        Args:
            bewerbung_id: ID der Bewerbung
            bestaetigung: Muss True sein um die Löschung zu bestätigen
        """
        if not bestaetigung:
            app = db.get_application(bewerbung_id)
            if not app:
                return {"fehler": "Bewerbung nicht gefunden."}
            return {
                "status": "bestaetigung_erforderlich",
                "bewerbung": f"{app.get('title', '')} bei {app.get('company', '')}",
                "hinweis": "Setze bestaetigung=True um die Bewerbung unwiderruflich zu löschen."
            }
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}
        title = app.get("title", "")
        company = app.get("company", "")
        db.delete_application(bewerbung_id)
        return {
            "status": "geloescht",
            "nachricht": f"Bewerbung '{title}' bei {company} wurde gelöscht."
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
        bewerbungsart: str = "",
        employment_type: str = "",
        source: str = "",
        vermittler: str = "",
        endkunde: str = "",
    ) -> dict:
        """Bearbeitet eine bestehende Bewerbung (Felder nachträglich ändern/ergänzen).

        Nur die angegebenen Felder werden geändert, leere Felder bleiben unverändert.

        Args:
            bewerbung_id: ID der Bewerbung
            title: Neuer Stellentitel
            company: Neuer Firmenname
            url: Neuer Link zur Stellenanzeige
            notes: Neue Notizen (überschreibt bisherige)
            ansprechpartner: Neuer Ansprechpartner
            kontakt_email: Neue Kontakt-E-Mail
            portal_name: Neues Portal
            bewerbungsart: Neue Bewerbungsart
            employment_type: Stellenart (festanstellung, freelance, teilzeit, praktikum, werkstudent)
            source: Quelle der Stelle (stepstone, indeed, linkedin, manuell, etc.)
            vermittler: Name des Vermittlers/der Agentur
            endkunde: Name des Endkunden (bei Freelance/Vermittlung)
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}

        updates = {}
        for key, val in [("title", title), ("company", company), ("url", url),
                         ("notes", notes), ("ansprechpartner", ansprechpartner),
                         ("kontakt_email", kontakt_email), ("portal_name", portal_name),
                         ("bewerbungsart", bewerbungsart), ("employment_type", employment_type),
                         ("source", source), ("vermittler", vermittler), ("endkunde", endkunde)]:
            if val:
                updates[key] = val

        if not updates:
            return {"fehler": "Keine Änderungen angegeben."}

        db.update_application(bewerbung_id, updates)
        return {
            "status": "aktualisiert",
            "geaenderte_felder": list(updates.keys()),
            "nachricht": f"Bewerbung bei {app.get('company', '')} aktualisiert."
        }

    @mcp.tool()
    def bewerbung_notiz(bewerbung_id: str, notiz: str) -> dict:
        """Fügt eine Gesprächsnotiz mit Timestamp zur Bewerbungs-Timeline hinzu.

        Ideal für: Interview-Notizen, Telefonate, E-Mail-Zusammenfassungen,
        Feedback nach Gesprächen, nächste Schritte.

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
            "nachricht": f"Notiz zu '{app.get('title', '')}' bei {app.get('company', '')} hinzugefügt.",
            "timeline_eintraege": len(app.get("events", [])) + 1
        }

    @mcp.tool()
    def bewerbung_details(bewerbung_id: str) -> dict:
        """Zeigt alle Details einer Bewerbung: Stellenbeschreibung, Timeline, Notizen, Dokumente.

        Das vollständige Dossier — alles auf einen Blick für Interview-Vorbereitung.

        Args:
            bewerbung_id: ID der Bewerbung
        """
        app = db.get_application(bewerbung_id)
        if not app:
            return {"fehler": "Bewerbung nicht gefunden."}

        result = {
            "bewerbung_id": app["id"][:8],  # #171: Kurz-ID
            "bewerbung_id_voll": app["id"],
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
        if app.get("job_hash"):
            result["stellen_id"] = app["job_hash"][:8]  # #171
            result["stellen_id_voll"] = app["job_hash"]
        if app.get("stellenbeschreibung"):
            result["stellenbeschreibung"] = app["stellenbeschreibung"]
        if app.get("employment_type"):
            result["stellenart"] = app["employment_type"]
        if app.get("events"):
            result["timeline"] = [
                {
                    "datum": e.get("event_date", ""),
                    "status": e.get("status", ""),
                    "notiz": e.get("notes", ""),
                }
                for e in app["events"]
            ]

        # #170: Kontextabhängige Aktionen basierend auf aktuellem Status
        result["naechste_aktionen"] = _get_context_actions(app.get("status", ""))

        return result

    @mcp.tool()
    def statistiken_abrufen(
        zeitraum_von: str = "",
        zeitraum_bis: str = ""
    ) -> dict:
        """Ruft Bewerbungsstatistiken ab: Conversion-Rate, Antwortzeiten, Status-Verteilung.

        Gibt einen Ueberblick ueber:
        - Gesamtzahl Bewerbungen und aktive Stellen
        - Bewerbungen nach Status (in_vorbereitung, beworben, interview, angebot, etc.)
        - Interview-Rate (% der Bewerbungen die zum Interview fuehren)
        - Pipeline-Uebersicht (wie viele Bewerbungen in welchem Status)

        Args:
            zeitraum_von: Optional: Start-Datum (YYYY-MM-DD) fuer den Bericht (#173)
            zeitraum_bis: Optional: End-Datum (YYYY-MM-DD) fuer den Bericht (#173)
        """
        stats = db.get_statistics()

        # Zeitraumfilter (#173)
        if zeitraum_von or zeitraum_bis:
            apps = db.get_applications()
            filtered = []
            for a in apps:
                date = a.get("applied_at") or a.get("created_at") or ""
                if zeitraum_von and date < zeitraum_von:
                    continue
                if zeitraum_bis and date > zeitraum_bis + "T23:59:59":
                    continue
                filtered.append(a)
            # Recalculate stats for filtered period
            by_status = {}
            for a in filtered:
                s = a.get("status", "offen")
                by_status[s] = by_status.get(s, 0) + 1
            total = len(filtered)
            in_vorb = by_status.get("in_vorbereitung", 0)
            submitted = total - in_vorb  # exclude in_vorbereitung from rate basis (#198)
            interviews = by_status.get("interview", 0) + by_status.get("zweitgespraech", 0)
            offers = by_status.get("angebot", 0) + by_status.get("angenommen", 0)
            stats["zeitraum"] = {"von": zeitraum_von, "bis": zeitraum_bis}
            stats["total_applications"] = total
            stats["applications_by_status"] = by_status
            stats["interview_rate"] = round(interviews / submitted * 100, 1) if submitted else 0
            stats["offer_rate"] = round(offers / submitted * 100, 1) if submitted else 0

        # Pipeline-Zusammenfassung (#170)
        by_status = stats.get("applications_by_status", {})
        pipeline = {
            "in_vorbereitung": by_status.get("in_vorbereitung", 0),
            "beworben": by_status.get("beworben", 0),
            "im_prozess": (by_status.get("eingangsbestaetigung", 0)
                           + by_status.get("interview", 0)
                           + by_status.get("zweitgespraech", 0)),
            "angebote": by_status.get("angebot", 0) + by_status.get("angenommen", 0),
        }
        stats["pipeline"] = pipeline

        return stats
