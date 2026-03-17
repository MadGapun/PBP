"""Profil-Verwaltung — 14 Tools.

Enthalt: Profil-Grundlagen (8), Multi-Profil (4), Erfassungsfortschritt (3).
"""

import json

from ..services.profile_service import (
    get_profile_completeness,
    get_profile_completeness_labels,
    get_profile_preferences,
    get_profile_status_payload,
)


def register(mcp, db, logger):
    """Registriert alle Profil-Tools."""

    # --- Profil-Grundlagen (8 Tools) ---

    @mcp.tool()
    def profil_status() -> dict:
        """Prueft ob bereits ein Profil existiert und gibt eine Kurzuebersicht.

        IMMER als erstes aufrufen wenn der User den Assistent startet.
        Entscheidet ob Ersterfassung noetig ist oder ob es direkt losgehen kann.
        """
        return get_profile_status_payload(db.get_profile())

    @mcp.tool()
    def profil_zusammenfassung() -> dict:
        """Liest das komplette Profil und gibt eine formatierte Zusammenfassung zurueck.

        Inkl. Vollstaendigkeits-Checkliste. Nutze dieses Tool um dem User
        sein Profil zur Kontrolle zu zeigen (Review-Phase).
        """
        profile = db.get_profile()
        if profile is None:
            return {"status": "kein_profil", "nachricht": "Noch kein Profil vorhanden."}

        positions = profile.get("positions", [])
        education = profile.get("education", [])
        skills = profile.get("skills", [])
        documents = profile.get("documents", [])
        prefs = get_profile_preferences(profile)

        # Build formatted summary
        lines = []
        lines.append("=" * 50)
        lines.append(f"PROFIL: {profile.get('name', '(kein Name)')}")
        lines.append("=" * 50)

        # Personal data
        lines.append("\n--- Persoenliche Daten ---")
        for key, label in [
            ("email", "E-Mail"), ("phone", "Telefon"), ("address", "Adresse"),
            ("city", "Stadt"), ("plz", "PLZ"), ("country", "Land"),
            ("birthday", "Geburtstag"), ("nationality", "Nationalitaet"),
        ]:
            val = profile.get(key)
            if val:
                lines.append(f"  {label}: {val}")

        if profile.get("summary"):
            lines.append(f"\n--- Kurzprofil ---\n  {profile['summary']}")

        if profile.get("informal_notes"):
            lines.append(f"\n--- Persoenliche Notizen ---\n  {profile['informal_notes']}")

        # Preferences
        if prefs:
            lines.append("\n--- Job-Praeferenzen ---")
            pref_labels = {
                "stellentyp": "Stellentyp", "arbeitsmodell": "Arbeitsmodell",
                "min_gehalt": "Min. Gehalt (EUR/Jahr)", "ziel_gehalt": "Ziel-Gehalt (EUR/Jahr)",
                "min_tagessatz": "Min. Tagessatz (EUR)", "ziel_tagessatz": "Ziel-Tagessatz (EUR)",
                "reisebereitschaft": "Reisebereitschaft", "umzug_moeglich": "Umzug moeglich",
            }
            for key, label in pref_labels.items():
                val = prefs.get(key)
                if val and val != 0 and val != "":
                    if isinstance(val, bool):
                        val = "Ja" if val else "Nein"
                    lines.append(f"  {label}: {val}")

        # Positions
        lines.append(f"\n--- Berufserfahrung ({len(positions)} Positionen) ---")
        for pos in positions:
            current = " (aktuell)" if pos.get("is_current") else ""
            end = pos.get("end_date") or "heute"
            emp_type = pos.get("employment_type", "")
            type_badge = f" [{emp_type}]" if emp_type else ""
            lines.append(f"\n  {pos.get('title', '?')} bei {pos.get('company', '?')}{current}{type_badge}")
            lines.append(f"  {pos.get('start_date', '?')} - {end} | {pos.get('location', '')}")
            if pos.get("description"):
                lines.append(f"  Beschreibung: {pos['description'][:200]}")
            if pos.get("tasks"):
                lines.append(f"  Aufgaben: {pos['tasks'][:200]}")
            if pos.get("achievements"):
                lines.append(f"  Erfolge: {pos['achievements'][:200]}")
            if pos.get("technologies"):
                lines.append(f"  Technologien: {pos['technologies']}")
            projects = pos.get("projects", [])
            if projects:
                lines.append(f"  Projekte ({len(projects)}):")
                for proj in projects:
                    lines.append(f"    - {proj.get('name', '?')}: {proj.get('description', '')[:100]}")
                    if proj.get("result"):
                        lines.append(f"      Ergebnis: {proj['result'][:100]}")

        # Education
        lines.append(f"\n--- Ausbildung ({len(education)} Eintraege) ---")
        for edu in education:
            degree = edu.get("degree", "")
            field = edu.get("field_of_study", "")
            degree_str = f"{degree} in {field}" if degree and field else degree or field or "?"
            lines.append(f"  {degree_str} — {edu.get('institution', '?')}")
            if edu.get("start_date") or edu.get("end_date"):
                lines.append(f"  {edu.get('start_date', '?')} - {edu.get('end_date', '?')}")
            if edu.get("grade"):
                lines.append(f"  Note: {edu['grade']}")

        # Skills
        lines.append(f"\n--- Skills ({len(skills)} Eintraege) ---")
        by_cat = {}
        for s in skills:
            cat = s.get("category", "sonstige")
            by_cat.setdefault(cat, []).append(s)
        cat_labels = {
            "fachlich": "Fachlich", "methodisch": "Methodisch",
            "soft_skill": "Soft Skills", "sprache": "Sprachen",
            "tool": "Tools", "sonstige": "Sonstige",
        }
        for cat, items in by_cat.items():
            label = cat_labels.get(cat, cat)
            skill_strs = [f"{s['name']} (Lv.{s.get('level', '?')})" for s in items]
            lines.append(f"  {label}: {', '.join(skill_strs)}")

        # Documents
        if documents:
            lines.append(f"\n--- Dokumente ({len(documents)}) ---")
            for doc in documents:
                lines.append(f"  [{doc.get('doc_type', '?')}] {doc.get('filename', '?')}")

        # Completeness check
        lines.append("\n" + "=" * 50)
        lines.append("VOLLSTAENDIGKEITS-CHECK")
        lines.append("=" * 50)

        completeness = get_profile_completeness(profile)
        checks = get_profile_completeness_labels(profile)
        complete = completeness["complete"]
        for label, ok in checks.items():
            icon = "[OK]" if ok else "[FEHLT]"
            lines.append(f"  {icon} {label}")

        pct = completeness["completeness"]
        lines.append(f"\nVollstaendigkeit: {pct}% ({complete}/{len(checks)})")

        return {
            "zusammenfassung": "\n".join(lines),
            "vollstaendigkeit_prozent": pct,
            "fehlende_bereiche": [l for l, ok in checks.items() if not ok],
            "positionen_anzahl": len(positions),
            "projekte_anzahl": sum(len(p.get("projects", [])) for p in positions),
            "skills_anzahl": len(skills),
            "ausbildung_anzahl": len(education),
        }

    @mcp.tool()
    def profil_bearbeiten(
        bereich: str,
        aktion: str,
        element_id: str = "",
        daten: dict = None
    ) -> dict:
        """Bearbeitet Profildaten: Persoenliches, Berufserfahrung, Skills, Ausbildung, Projekte.

        Universaltool fuer alle Profil-Aenderungen. Auch nutzbar fuer Bulk-Import
        mit aktion='hinzufuegen_bulk' und daten als Liste.

        AKTIONEN PRO BEREICH:
        - persoenlich: aendern (Felder in daten)
        - praeferenzen: aendern (Key-Value in daten)
        - position: hinzufuegen, aendern (element_id + daten), loeschen (element_id), hinzufuegen_bulk
        - projekt: hinzufuegen (daten.position_id noetig), aendern (element_id + daten), loeschen (element_id), hinzufuegen_bulk
        - ausbildung: hinzufuegen, aendern (element_id + daten), loeschen (element_id), hinzufuegen_bulk
        - skill: hinzufuegen, aendern (element_id + daten), loeschen (element_id), hinzufuegen_bulk

        Feldnamen-Aliase fuer bereich='persoenlich':
        adresse/anschrift->address, kurzprofil/zusammenfassung->summary,
        stadt/ort->city, telefon->phone

        Args:
            bereich: persoenlich, praeferenzen, position, projekt, ausbildung, skill
            aktion: aendern, loeschen, hinzufuegen, hinzufuegen_bulk (Liste in daten)
            element_id: ID des Elements (bei aendern/loeschen)
            daten: Dict mit Aenderungen, oder Liste von Dicts bei hinzufuegen_bulk
        """
        if daten is None:
            daten = {}

        if bereich == "persoenlich":
            if aktion == "aendern":
                profile = db.get_profile()
                if not profile:
                    return {"fehler": "Kein Profil vorhanden"}
                # Alias-Support: deutsche Feldnamen -> DB-Spalten
                _FIELD_ALIASES = {
                    "adresse": "address", "strasse": "address", "anschrift": "address",
                    "stadt": "city", "ort": "city", "wohnort": "city",
                    "kurzprofil": "summary", "zusammenfassung": "summary", "profil": "summary",
                    "telefon": "phone", "tel": "phone", "handy": "phone",
                    "land": "country", "geburtstag": "birthday",
                    "staatsangehoerigkeit": "nationality", "nationalitaet": "nationality",
                    "notizen": "informal_notes",
                }
                resolved = {}
                for k, v in daten.items():
                    canonical = _FIELD_ALIASES.get(k.lower(), k.lower())
                    resolved[canonical] = v
                # Known DB fields
                _KNOWN_FIELDS = {"name", "email", "phone", "address", "city", "plz",
                                 "country", "birthday", "nationality", "summary", "informal_notes"}
                ignoriert = [k for k in resolved if k not in _KNOWN_FIELDS]
                # Merge: keep existing, update provided
                update = {
                    "name": resolved.get("name", profile.get("name")),
                    "email": resolved.get("email", profile.get("email")),
                    "phone": resolved.get("phone", profile.get("phone")),
                    "address": resolved.get("address", profile.get("address")),
                    "city": resolved.get("city", profile.get("city")),
                    "plz": resolved.get("plz", profile.get("plz")),
                    "country": resolved.get("country", profile.get("country")),
                    "birthday": resolved.get("birthday", profile.get("birthday")),
                    "nationality": resolved.get("nationality", profile.get("nationality")),
                    "summary": resolved.get("summary", profile.get("summary")),
                    "informal_notes": resolved.get("informal_notes", profile.get("informal_notes")),
                    "preferences": profile.get("preferences", {}),
                }
                db.save_profile(update)
                result = {"status": "aktualisiert", "bereich": "persoenlich",
                          "akzeptierte_felder": [k for k in resolved if k in _KNOWN_FIELDS]}
                if ignoriert:
                    result["ignorierte_felder"] = ignoriert
                    result["hinweis"] = f"Unbekannte Felder ignoriert: {', '.join(ignoriert)}"
                return result

        elif bereich == "praeferenzen":
            if aktion == "aendern":
                profile = db.get_profile()
                if not profile:
                    return {"fehler": "Kein Profil vorhanden"}
                prefs = profile.get("preferences", {})
                if isinstance(prefs, str):
                    prefs = json.loads(prefs) if prefs else {}
                prefs.update(daten)
                update_data = {
                    "name": profile.get("name"), "email": profile.get("email"),
                    "phone": profile.get("phone"), "address": profile.get("address"),
                    "city": profile.get("city"), "plz": profile.get("plz"),
                    "country": profile.get("country"), "birthday": profile.get("birthday"),
                    "nationality": profile.get("nationality"),
                    "summary": profile.get("summary"),
                    "informal_notes": profile.get("informal_notes"),
                    "preferences": prefs,
                }
                db.save_profile(update_data)
                return {"status": "aktualisiert", "bereich": "praeferenzen", "neue_werte": prefs}

        elif bereich == "position":
            if aktion == "loeschen" and element_id:
                db.delete_position(element_id)
                return {"status": "geloescht", "bereich": "position", "id": element_id}
            elif aktion == "aendern" and element_id:
                db.update_position(element_id, daten)
                return {"status": "aktualisiert", "bereich": "position", "id": element_id,
                        "geaenderte_felder": list(daten.keys())}
            elif aktion == "hinzufuegen":
                pid = db.add_position(daten)
                return {"status": "hinzugefuegt", "bereich": "position", "id": pid}
            elif aktion == "hinzufuegen_bulk" and isinstance(daten, list):
                ids = [db.add_position(d) for d in daten]
                return {"status": "hinzugefuegt", "bereich": "position", "anzahl": len(ids), "ids": ids}

        elif bereich == "projekt":
            if aktion == "loeschen" and element_id:
                db.delete_project(element_id)
                return {"status": "geloescht", "bereich": "projekt", "id": element_id}
            elif aktion == "aendern" and element_id:
                db.update_project(element_id, daten)
                return {"status": "aktualisiert", "bereich": "projekt", "id": element_id,
                        "geaenderte_felder": list(daten.keys())}
            elif aktion == "hinzufuegen" and daten.get("position_id"):
                pid = db.add_project(daten["position_id"], daten)
                return {"status": "hinzugefuegt", "bereich": "projekt", "id": pid}
            elif aktion == "hinzufuegen_bulk" and isinstance(daten, list):
                ids = []
                for d in daten:
                    if d.get("position_id"):
                        ids.append(db.add_project(d["position_id"], d))
                return {"status": "hinzugefuegt", "bereich": "projekt", "anzahl": len(ids), "ids": ids}

        elif bereich == "ausbildung":
            if aktion == "loeschen" and element_id:
                db.delete_education(element_id)
                return {"status": "geloescht", "bereich": "ausbildung", "id": element_id}
            elif aktion == "aendern" and element_id:
                db.update_education(element_id, daten)
                return {"status": "aktualisiert", "bereich": "ausbildung", "id": element_id,
                        "geaenderte_felder": list(daten.keys())}
            elif aktion == "hinzufuegen":
                eid = db.add_education(daten)
                return {"status": "hinzugefuegt", "bereich": "ausbildung", "id": eid}
            elif aktion == "hinzufuegen_bulk" and isinstance(daten, list):
                ids = [db.add_education(d) for d in daten]
                return {"status": "hinzugefuegt", "bereich": "ausbildung", "anzahl": len(ids), "ids": ids}

        elif bereich == "skill":
            if aktion == "loeschen" and element_id:
                db.delete_skill(element_id)
                return {"status": "geloescht", "bereich": "skill", "id": element_id}
            elif aktion == "aendern" and element_id:
                db.update_skill(element_id, daten)
                return {"status": "aktualisiert", "bereich": "skill", "id": element_id,
                        "geaenderte_felder": list(daten.keys())}
            elif aktion == "hinzufuegen":
                sid = db.add_skill(daten)
                return {"status": "hinzugefuegt", "bereich": "skill", "id": sid}
            elif aktion == "hinzufuegen_bulk" and isinstance(daten, list):
                ids = [db.add_skill(d) for d in daten]
                return {"status": "hinzugefuegt", "bereich": "skill", "anzahl": len(ids), "ids": ids}

        return {"fehler": f"Ungueltige Kombination: bereich={bereich}, aktion={aktion}"}

    @mcp.tool()
    def profil_erstellen(
        name: str,
        email: str = "",
        phone: str = "",
        address: str = "",
        city: str = "",
        plz: str = "",
        country: str = "Deutschland",
        birthday: str = "",
        nationality: str = "",
        summary: str = "",
        informal_notes: str = "",
        stellentyp: str = "beides",
        arbeitsmodell: str = "hybrid",
        min_gehalt: int = 0,
        ziel_gehalt: int = 0,
        min_tagessatz: int = 0,
        ziel_tagessatz: int = 0,
        reisebereitschaft: str = "mittel",
        umzug_moeglich: bool = False
    ) -> dict:
        """Erstellt oder aktualisiert das Bewerberprofil.

        Args:
            name: Vollstaendiger Name
            email: E-Mail-Adresse
            phone: Telefonnummer
            address: Strasse und Hausnummer
            city: Stadt/Ort
            plz: Postleitzahl
            country: Land
            birthday: Geburtsdatum (YYYY-MM-DD)
            nationality: Staatsangehoerigkeit
            summary: Kurzprofil / Zusammenfassung
            informal_notes: Zwanglose Informationen (Neigungen, Motivation, Wuensche)
            stellentyp: festanstellung, freelance, oder beides
            arbeitsmodell: remote, hybrid, vor_ort
            min_gehalt: Mindestgehalt Festanstellung (EUR/Jahr)
            ziel_gehalt: Zielgehalt Festanstellung (EUR/Jahr)
            min_tagessatz: Mindest-Tagessatz Freelance (EUR)
            ziel_tagessatz: Ziel-Tagessatz Freelance (EUR)
            reisebereitschaft: keine, gering, mittel, hoch
            umzug_moeglich: Umzugsbereitschaft
        """
        preferences = {
            "stellentyp": stellentyp,
            "arbeitsmodell": arbeitsmodell,
            "min_gehalt": min_gehalt,
            "ziel_gehalt": ziel_gehalt,
            "min_tagessatz": min_tagessatz,
            "ziel_tagessatz": ziel_tagessatz,
            "reisebereitschaft": reisebereitschaft,
            "umzug_moeglich": umzug_moeglich,
        }
        pid = db.save_profile({
            "name": name, "email": email, "phone": phone,
            "address": address, "city": city, "plz": plz,
            "country": country, "birthday": birthday, "nationality": nationality,
            "summary": summary, "informal_notes": informal_notes,
            "preferences": preferences,
        })
        return {
            "status": "gespeichert",
            "profil_id": pid,
            "naechster_schritt": "Fuege jetzt Berufserfahrung hinzu mit position_hinzufuegen(). "
                                "Frage nach: Firma, Position, Zeitraum, Aufgaben, Erfolge, Technologien. "
                                "Nutze die STAR-Methode (Situation, Task, Action, Result) fuer jedes Projekt."
        }

    @mcp.tool()
    def position_hinzufuegen(
        company: str,
        title: str,
        start_date: str,
        end_date: str = "",
        is_current: bool = False,
        location: str = "",
        employment_type: str = "festanstellung",
        industry: str = "",
        description: str = "",
        tasks: str = "",
        achievements: str = "",
        technologies: str = ""
    ) -> dict:
        """Fuegt eine Berufserfahrung (Position/Stelle/Job) zum Bewerberprofil hinzu.

        Alternativ: profil_bearbeiten(bereich='position', aktion='hinzufuegen')

        Args:
            company: Firmenname
            title: Jobtitel / Position
            start_date: Startdatum (YYYY-MM oder YYYY-MM-DD)
            end_date: Enddatum (leer wenn aktuell)
            is_current: Aktuelle Position?
            location: Arbeitsort
            employment_type: festanstellung, freelance, praktikum, werkstudent
            industry: Branche
            description: Allgemeine Beschreibung der Rolle
            tasks: Hauptaufgaben (kommasepariert oder als Text)
            achievements: Erfolge und Ergebnisse
            technologies: Verwendete Technologien und Tools
        """
        pid = db.add_position({
            "company": company, "title": title, "location": location,
            "start_date": start_date, "end_date": end_date,
            "is_current": is_current, "employment_type": employment_type,
            "industry": industry, "description": description,
            "tasks": tasks, "achievements": achievements, "technologies": technologies,
        })
        return {
            "status": "gespeichert",
            "position_id": pid,
            "naechster_schritt": f"Position '{title}' bei {company} hinzugefuegt. "
                                "Frage jetzt nach Projekten bei dieser Position: "
                                "projekt_hinzufuegen(). Nutze STAR: Situation, Task, Action, Result. "
                                "Frage am Ende: 'Gab es noch ein weiteres Projekt bei dieser Firma?'"
        }

    @mcp.tool()
    def projekt_hinzufuegen(
        position_id: str,
        name: str,
        description: str = "",
        role: str = "",
        situation: str = "",
        task: str = "",
        action: str = "",
        result: str = "",
        technologies: str = "",
        duration: str = ""
    ) -> dict:
        """Fuegt ein Projekt zu einer Berufsposition hinzu (STAR-Methode).

        Args:
            position_id: ID der Position (von position_hinzufuegen)
            name: Projektname
            description: Kurzbeschreibung des Projekts
            role: Rolle im Projekt (z.B. Projektleiter, Architekt)
            situation: STAR-S: Ausgangssituation / Kontext
            task: STAR-T: Aufgabe / Herausforderung
            action: STAR-A: Durchgefuehrte Massnahmen
            result: STAR-R: Ergebnis / Erfolg (moeglichst quantifizierbar)
            technologies: Eingesetzte Technologien
            duration: Dauer (z.B. "6 Monate", "2020-2021")
        """
        pid = db.add_project(position_id, {
            "name": name, "description": description, "role": role,
            "situation": situation, "task": task, "action": action,
            "result": result, "technologies": technologies, "duration": duration,
        })
        return {
            "status": "gespeichert",
            "projekt_id": pid,
            "hinweis": "Frage den User: 'Gab es noch ein weiteres Projekt in dieser Position?'"
        }

    @mcp.tool()
    def ausbildung_hinzufuegen(
        institution: str,
        degree: str = "",
        field_of_study: str = "",
        start_date: str = "",
        end_date: str = "",
        grade: str = "",
        description: str = ""
    ) -> dict:
        """Fuegt eine Ausbildung, Studium oder Weiterbildung hinzu.

        Args:
            institution: Name der Bildungseinrichtung
            degree: Abschluss (z.B. Diplom, Master, Bachelor, Zertifikat)
            field_of_study: Studiengang / Fachrichtung
            start_date: Startdatum
            end_date: Enddatum
            grade: Note / Bewertung
            description: Zusaetzliche Details
        """
        eid = db.add_education({
            "institution": institution, "degree": degree,
            "field_of_study": field_of_study,
            "start_date": start_date, "end_date": end_date,
            "grade": grade, "description": description,
        })
        return {"status": "gespeichert", "ausbildung_id": eid}

    @mcp.tool()
    def skill_hinzufuegen(
        name: str,
        category: str = "fachlich",
        level: int = 3,
        years_experience: int = 0,
        last_used_year: int = 0
    ) -> dict:
        """Fuegt einen Skill (Kompetenz/Faehigkeit/Expertise) zum Bewerberprofil hinzu.

        Fuer Fachwissen, Tools, Soft Skills, Sprachen und Methoden-Kompetenzen.
        Alternativ: profil_bearbeiten(bereich='skill', aktion='hinzufuegen')

        WICHTIG fuer Skill-Level-Bewertung:
        - Beruecksichtige WANN der Skill zuletzt aktiv genutzt wurde
        - Ein Skill von vor 20 Jahren der seitdem nicht mehr genutzt wurde → Level 1
        - Setze last_used_year auf das Jahr der letzten aktiven Nutzung
        - Level sollte die AKTUELLE Kompetenz widerspiegeln, nicht die historische
        - Beispiel: "C++ Programmierung, 5 Jahre Erfahrung, zuletzt 2008" → level=1, last_used_year=2008

        Args:
            name: Name der Kompetenz (z.B. Python, Projektmanagement, SAP)
            category: fachlich, methodisch, soft_skill, sprache, tool
            level: AKTUELLE Kompetenzstufe 1-5 (1=Grundkenntnisse, 5=Experte). Alte, nicht mehr genutzte Skills → niedrig bewerten!
            years_experience: Jahre Erfahrung (gesamt, auch historisch)
            last_used_year: Jahr der letzten aktiven Nutzung (z.B. 2024). 0 = aktuell/unbekannt.
        """
        sid = db.add_skill({
            "name": name, "category": category,
            "level": level, "years_experience": years_experience,
            "last_used_year": last_used_year if last_used_year else None,
        })
        return {"status": "gespeichert", "skill_id": sid}

    # --- Multi-Profil (4 Tools) ---

    @mcp.tool()
    def profile_auflisten() -> dict:
        """Listet alle vorhandenen Profile auf. Zeigt welches aktiv ist.

        Nutze dieses Tool wenn mehrere Personen den gleichen PC nutzen
        oder wenn der User zwischen Profilen wechseln moechte.
        """
        profiles = db.get_profiles()
        if not profiles:
            return {"status": "keine_profile", "nachricht": "Keine Profile vorhanden. Starte die Ersterfassung."}
        return {
            "status": "ok",
            "anzahl": len(profiles),
            "profile": [
                {
                    "id": p["id"],
                    "name": p["name"] or "(Ohne Name)",
                    "email": p.get("email", ""),
                    "aktiv": bool(p.get("is_active")),
                    "erstellt": p.get("created_at", ""),
                    "aktualisiert": p.get("updated_at", ""),
                }
                for p in profiles
            ],
        }

    @mcp.tool()
    def profil_wechseln(profil_id: str) -> dict:
        """Wechselt zum angegebenen Profil. Alle anderen Profile werden deaktiviert.

        Args:
            profil_id: Die ID des Profils zu dem gewechselt werden soll.
        """
        success = db.switch_profile(profil_id)
        if success:
            profile = db.get_profile()
            return {
                "status": "gewechselt",
                "aktives_profil": profile.get("name") if profile else "?",
                "nachricht": f"Profil gewechselt zu: {profile.get('name') if profile else profil_id}"
            }
        return {"fehler": f"Profil mit ID '{profil_id}' nicht gefunden."}

    @mcp.tool()
    def neues_profil_erstellen(name: str, email: str = "") -> dict:
        """Erstellt ein komplett neues, leeres Profil und aktiviert es.

        Das vorherige Profil bleibt gespeichert und kann spaeter wieder aktiviert werden.

        Args:
            name: Name der Person fuer das neue Profil
            email: Optional: E-Mail-Adresse
        """
        pid = db.create_profile(name, email)
        return {
            "status": "erstellt",
            "profil_id": pid,
            "name": name,
            "nachricht": f"Neues Profil '{name}' erstellt und aktiviert. Das vorherige Profil wurde gespeichert."
        }

    @mcp.tool()
    def profil_loeschen(profil_id: str, bestaetigung: bool = False) -> dict:
        """Loescht ein Profil und alle zugehoerigen Daten (Positionen, Skills, Dokumente).

        ACHTUNG: Diese Aktion kann nicht rueckgaengig gemacht werden!
        Erstelle vorher ein Backup mit profil_exportieren().

        Wenn das aktive Profil geloescht werden soll und es weitere Profile gibt,
        wird automatisch zum naechsten Profil gewechselt.
        Wenn es das einzige Profil ist, muss bestaetigung=True gesetzt werden.

        Args:
            profil_id: Die ID des zu loeschenden Profils
            bestaetigung: Muss True sein wenn das einzige Profil geloescht wird
        """
        active_id = db.get_active_profile_id()
        profiles = db.get_profiles()

        if profil_id == active_id:
            if len(profiles) > 1:
                # Switch to another profile first, then delete
                other = next(p for p in profiles if p["id"] != profil_id)
                db.switch_profile(other["id"])
                db.delete_profile(profil_id)
                return {
                    "status": "geloescht",
                    "nachricht": f"Profil geloescht. Automatisch gewechselt zu: {other['name']}",
                    "aktives_profil": other["name"],
                }
            elif not bestaetigung:
                return {
                    "fehler": "Dies ist dein einziges Profil. Setze bestaetigung=True um es trotzdem zu loeschen.",
                    "hinweis": "Erstelle vorher ein Backup mit profil_exportieren().",
                }
            else:
                db.delete_profile(profil_id)
                return {
                    "status": "geloescht",
                    "nachricht": "Einziges Profil geloescht. Erstelle ein neues mit profil_erstellen().",
                }

        db.delete_profile(profil_id)
        return {"status": "geloescht", "nachricht": f"Profil {profil_id} und alle zugehoerigen Daten wurden geloescht."}

    # --- Erfassungsfortschritt (2 Tools) ---

    @mcp.tool()
    def erfassung_fortschritt_lesen() -> dict:
        """Liest den Fortschritt der Profil-Ersterfassung.

        Gibt zurueck welche Bereiche bereits ausgefuellt sind und welche noch fehlen.
        Nutze dies zu Beginn einer Ersterfassung um zu pruefen ob es eine
        angefangene Erfassung gibt die fortgesetzt werden soll.
        """
        profile = db.get_profile()
        if profile is None:
            return {"status": "kein_profil", "fortschritt": {}}

        # Automatisch berechnen was schon da ist
        fortschritt = profile.get("erfassung_fortschritt", {})
        prefs = get_profile_preferences(profile)
        auto_check = {
            "persoenliche_daten": bool(profile.get("name") and profile.get("email")),
            "berufserfahrung": len(profile.get("positions", [])) > 0,
            "ausbildung": len(profile.get("education", [])) > 0,
            "kompetenzen": len(profile.get("skills", [])) > 0,
            "praeferenzen": bool(prefs.get("stellentyp")),
            "review_abgeschlossen": fortschritt.get("review_abgeschlossen", False),
        }
        return {
            "status": "ok",
            "profil_name": profile.get("name"),
            "bereiche": auto_check,
            "alle_komplett": all(auto_check.values()),
            "fehlende_bereiche": [k for k, v in auto_check.items() if not v],
            "letzte_notizen": fortschritt.get("notizen", ""),
        }

    @mcp.tool()
    def erfassung_fortschritt_speichern(
        bereich: str,
        abgeschlossen: bool = True,
        notizen: str = ""
    ) -> dict:
        """Speichert den Fortschritt eines Erfassungsbereichs.

        Wird automatisch waehrend der Ersterfassung aufgerufen um den Stand zu merken.
        So kann die Ersterfassung jederzeit unterbrochen und spaeter fortgesetzt werden.

        Args:
            bereich: Name des Bereichs (persoenliche_daten, berufserfahrung, ausbildung, kompetenzen, praeferenzen, review_abgeschlossen)
            abgeschlossen: Ob der Bereich fertig ist
            notizen: Optionale Notizen zum Fortschritt
        """
        fortschritt = db.get_erfassung_fortschritt()
        fortschritt[bereich] = abgeschlossen
        if notizen:
            fortschritt["notizen"] = notizen
        db.set_erfassung_fortschritt(fortschritt)

        # UI-Signal: Sobald das Kennlerngespraech arbeitet, Status auf "active" setzen.
        profile_id = db.get_active_profile_id()
        if profile_id:
            db.set_user_preference(f"profile_onboarding_started_{profile_id}", True)
            db.set_user_preference(f"profile_onboarding_completed_{profile_id}", False)
            db.set_user_preference(f"profile_onboarding_dismissed_{profile_id}", False)
            conversation_key = f"profile_onboarding_conversation_{profile_id}"
            if db.get_user_preference(conversation_key) != "complete":
                db.set_user_preference(conversation_key, "active")
        return {"status": "gespeichert", "bereich": bereich, "abgeschlossen": abgeschlossen}

    @mcp.tool()
    def kennlerngespraech_abschliessen() -> dict:
        """Markiert das Kennlerngespraech fuer das aktive Profil als abgeschlossen.

        Dieses Signal wird vom Onboarding in der Web-UI ausgewertet, damit nach dem
        Review direkt zum Schritt "Quellen" weitergegangen werden kann.
        """
        profile_id = db.get_active_profile_id()
        if not profile_id:
            return {"fehler": "Kein aktives Profil vorhanden."}

        db.set_user_preference(f"profile_onboarding_started_{profile_id}", True)
        db.set_user_preference(f"profile_onboarding_completed_{profile_id}", False)
        db.set_user_preference(f"profile_onboarding_dismissed_{profile_id}", False)
        db.set_user_preference(f"profile_onboarding_conversation_{profile_id}", "complete")

        return {
            "status": "ok",
            "profil_id": profile_id,
            "naechster_schritt": "quellen",
            "ui_signal": "profile_onboarding_conversation=complete",
            "nachricht": "Kennlerngespraech abgeschlossen. Als naechstes koennen die Quellen eingerichtet werden.",
        }

    # --- Jobtitel-Vorschlaege (2 Tools) ---

    @mcp.tool()
    def jobtitel_vorschlagen(titel: list[str], quelle: str = "auto") -> dict:
        """Speichert vorgeschlagene Jobtitel fuer das aktive Profil.

        Rufe dieses Tool auf nachdem du das Profil analysiert hast, um passende
        Jobtitel/Stellenbezeichnungen vorzuschlagen. Die Titel werden im Dashboard
        angezeigt und koennen vom User bearbeitet werden.

        WICHTIG: Beruecksichtige bei der Analyse:
        - Aktuelle Positionen und deren Titel
        - Branchen und Technologien aus der Berufserfahrung
        - Skill-Level und Aktualitaet (alte Skills zaehlen weniger)
        - Typische Stellenbezeichnungen im deutschen Arbeitsmarkt
        - Sowohl deutsch als auch englisch (z.B. "PLM Architekt" UND "PLM Architect")

        Args:
            titel: Liste von vorgeschlagenen Jobtiteln (z.B. ["PLM Architekt", "SAP PLM Berater"])
            quelle: Woher der Vorschlag kommt: 'auto' (aus Analyse), 'user' (vom Benutzer), 'extraktion' (aus Dokument)
        """
        profile_id = db.get_active_profile_id()
        if not profile_id:
            return {"fehler": "Kein aktives Profil vorhanden."}

        existing = {t["title"].lower() for t in db.get_suggested_job_titles(profile_id)}
        added = []
        skipped = []
        for t in titel:
            t = t.strip()
            if not t:
                continue
            if t.lower() in existing:
                skipped.append(t)
                continue
            db.add_job_title(t, source=quelle, confidence=0.8 if quelle == "auto" else 1.0,
                             profile_id=profile_id)
            existing.add(t.lower())
            added.append(t)

        return {
            "status": "ok",
            "hinzugefuegt": added,
            "uebersprungen_duplikate": skipped,
            "gesamt": len(db.get_suggested_job_titles(profile_id)),
            "hinweis": "Jobtitel sind im Dashboard unter 'Profil' sichtbar und editierbar."
        }

    @mcp.tool()
    def jobtitel_verwalten(titel_id: str, aktion: str = "loeschen", neuer_titel: str = "") -> dict:
        """Verwaltet einen vorgeschlagenen Jobtitel (aendern, loeschen, deaktivieren).

        Args:
            titel_id: ID des Jobtitels
            aktion: 'loeschen', 'aendern', 'deaktivieren', 'aktivieren'
            neuer_titel: Neuer Titeltext (nur bei aktion='aendern')
        """
        if aktion == "loeschen":
            db.delete_job_title(titel_id)
            return {"status": "geloescht"}
        elif aktion == "aendern" and neuer_titel:
            db.update_job_title(titel_id, {"title": neuer_titel})
            return {"status": "geaendert", "titel": neuer_titel}
        elif aktion == "deaktivieren":
            db.update_job_title(titel_id, {"is_active": 0})
            return {"status": "deaktiviert"}
        elif aktion == "aktivieren":
            db.update_job_title(titel_id, {"is_active": 1})
            return {"status": "aktiviert"}
        return {"fehler": f"Unbekannte Aktion: {aktion}"}
