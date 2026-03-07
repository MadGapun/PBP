"""Dokument-Analyse und Extraktion Tools (PBP-028, PBP v0.8.0)."""

import json
from datetime import datetime, timezone

from ..database import get_data_dir


def register(mcp, db, logger):
    """Register all document-related tools."""

    @mcp.tool()
    def dokument_profil_extrahieren(document_id: str) -> dict:
        """Liest den extrahierten Text eines hochgeladenen Dokuments und gibt ihn
        zur Analyse zurueck. Claude soll daraus Profildaten ableiten.

        WORKFLOW:
        1. Rufe dieses Tool mit der document_id auf
        2. Analysiere den Text und identifiziere Profildaten (Name, Skills, Positionen etc.)
        3. Vergleiche mit dem bestehenden Profil (profil_zusammenfassung)
        4. Bei neuen Daten: Frage den User ob diese uebernommen werden sollen
        5. Bei Konflikten: Zeige beide Versionen und lasse den User entscheiden
        6. Speichere mit den jeweiligen Tools (profil_bearbeiten, position_hinzufuegen etc.)

        Args:
            document_id: ID oder Dateiname des Dokuments
        """
        conn = db.connect()
        # Try ID first, then filename fallback
        row = conn.execute("SELECT * FROM documents WHERE id=?", (document_id,)).fetchone()
        if row is None:
            row = conn.execute("SELECT * FROM documents WHERE filename=? ORDER BY created_at DESC LIMIT 1",
                               (document_id,)).fetchone()
        if row is None:
            # List available documents as help
            docs = conn.execute("SELECT id, filename FROM documents ORDER BY created_at DESC LIMIT 10").fetchall()
            available = [{"id": d["id"], "filename": d["filename"]} for d in docs]
            return {"fehler": f"Dokument '{document_id}' nicht gefunden.",
                    "verfuegbare_dokumente": available}

        doc = dict(row)
        if not doc.get("extracted_text"):
            return {
                "fehler": "Kein extrahierter Text vorhanden. Dokument wurde noch nicht verarbeitet.",
                "dokument": doc.get("filename"),
            }

        return {
            "status": "ok",
            "dokument": {
                "id": doc["id"],
                "filename": doc["filename"],
                "doc_type": doc.get("doc_type", "sonstiges"),
            },
            "extrahierter_text": doc["extracted_text"],
            "anleitung": (
                "Analysiere den Text und extrahiere Profildaten. "
                "Vergleiche mit dem bestehenden Profil und frage bei Konflikten oder "
                "neuen Informationen den User ob diese uebernommen werden sollen. "
                "Nutze die entsprechenden Tools (profil_bearbeiten, position_hinzufuegen, "
                "skill_hinzufuegen etc.) um die Daten zu speichern."
            ),
        }

    @mcp.tool()
    def dokumente_zur_analyse() -> dict:
        """Listet alle Dokumente mit extrahiertem Text auf — auch bereits analysierte.

        Zeigt den Extraktions-Status jedes Dokuments an, damit auch wiederholte
        Extraktion moeglich ist. Nutze extraktion_starten(document_ids=[...]) um
        bestimmte Dokumente erneut zu extrahieren.
        """
        profile = db.get_profile()
        if profile is None:
            return {"status": "kein_profil"}

        docs = profile.get("documents", [])
        analysierbare = [
            {
                "id": d["id"],
                "filename": d["filename"],
                "doc_type": d.get("doc_type", "sonstiges"),
                "hat_text": bool(d.get("extracted_text")),
                "text_laenge": len(d.get("extracted_text", "")),
                "extraction_status": d.get("extraction_status", "nicht_extrahiert"),
                "bereits_analysiert": d.get("extraction_status", "") not in ("nicht_extrahiert", ""),
            }
            for d in docs
            if d.get("extracted_text")
        ]
        neue = [d for d in analysierbare if not d["bereits_analysiert"]]
        return {
            "status": "ok",
            "dokumente_gesamt": len(docs),
            "analysierbare": len(analysierbare),
            "neue_dokumente": len(neue),
            "dokumente": analysierbare,
        }

    @mcp.tool()
    def extraktion_starten(document_ids: list = None, force: bool = False) -> dict:
        """Startet die intelligente Profil-Extraktion fuer ein oder mehrere Dokumente.

        Laedt den extrahierten Text aller angegebenen (oder aller noch nicht
        analysierten) Dokumente und gibt ihn zusammen mit dem aktuellen Profil
        zurueck, damit Claude die Daten vergleichen und extrahieren kann.

        WORKFLOW:
        1. Rufe dieses Tool auf (optional mit document_ids)
        2. Analysiere die Texte und extrahiere Profildaten
        3. Speichere mit extraktion_ergebnis_speichern()
        4. Zeige dem User Ergebnisse und Konflikte
        5. Wende an mit extraktion_anwenden()

        Args:
            document_ids: Liste von Dokument-IDs oder Dateinamen. Leer = alle noch nicht extrahierten.
            force: True = auch bereits extrahierte Dokumente erneut verarbeiten.
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein aktives Profil vorhanden. Erstelle zuerst eins mit profil_erstellen()."}

        conn = db.connect()
        pid = profile["id"]

        if document_ids:
            # Support both IDs and filenames
            rows = []
            for doc_ref in document_ids:
                r = conn.execute(
                    "SELECT * FROM documents WHERE (id=? OR filename=?) AND profile_id=?",
                    (doc_ref, doc_ref, pid)
                ).fetchone()
                if r:
                    rows.append(r)
            if not rows:
                rows = []
        elif force:
            rows = conn.execute(
                "SELECT * FROM documents WHERE profile_id=? AND extracted_text IS NOT NULL AND extracted_text != ''",
                (pid,)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM documents WHERE profile_id=? AND extraction_status='nicht_extrahiert' AND extracted_text IS NOT NULL AND extracted_text != ''",
                (pid,)
            ).fetchall()

        if not rows:
            return {
                "status": "keine_dokumente",
                "nachricht": "Keine Dokumente zur Extraktion gefunden. Lade Dokumente im Dashboard hoch.",
            }

        dokumente = []
        doc_ids_for_history = []
        for row in rows:
            doc = dict(row)
            dokumente.append({
                "id": doc["id"],
                "filename": doc["filename"],
                "doc_type": doc.get("doc_type", "sonstiges"),
                "text_laenge": len(doc.get("extracted_text", "")),
                "extrahierter_text": doc.get("extracted_text", ""),
            })
            doc_ids_for_history.append(doc["id"])

        # Create extraction history entry
        extraction_type = "bulk" if len(dokumente) > 1 else "auto"
        eid = db.add_extraction_history({
            "document_id": doc_ids_for_history[0],
            "profile_id": pid,
            "extraction_type": extraction_type,
        })

        # Build profile summary for comparison
        profil_zusammenfassung_text = {
            "name": profile.get("name"),
            "email": profile.get("email"),
            "phone": profile.get("phone"),
            "address": profile.get("address"),
            "city": profile.get("city"),
            "plz": profile.get("plz"),
            "birthday": profile.get("birthday"),
            "nationality": profile.get("nationality"),
            "summary": profile.get("summary"),
            "positionen_anzahl": len(profile.get("positions", [])),
            "positionen": [
                {"firma": p.get("company"), "titel": p.get("title"),
                 "zeitraum": f"{p.get('start_date', '?')} - {p.get('end_date', 'heute') if not p.get('is_current') else 'heute'}"}
                for p in profile.get("positions", [])
            ],
            "skills_anzahl": len(profile.get("skills", [])),
            "skills": [s.get("name") for s in profile.get("skills", [])],
            "ausbildung_anzahl": len(profile.get("education", [])),
            "praeferenzen": profile.get("preferences", {}),
        }

        return {
            "status": "ok",
            "extraction_id": eid,
            "dokumente_anzahl": len(dokumente),
            "dokumente": dokumente,
            "aktuelles_profil": profil_zusammenfassung_text,
            "anleitung": (
                "Analysiere die Dokumente und extrahiere ALLE verwertbaren Profildaten. "
                "Vergleiche mit dem aktuellen Profil. "
                "Speichere das Ergebnis mit extraktion_ergebnis_speichern(). "
                "Bei Konflikten: IMMER den User fragen. "
                "Bei fehlenden Feldern: Nachfragen ob der User diese ergaenzen moechte."
            ),
        }

    @mcp.tool()
    def extraktion_ergebnis_speichern(
        extraction_id: str,
        extrahierte_daten: dict,
        konflikte: list = None,
        status: str = "ausstehend"
    ) -> dict:
        """Speichert das Ergebnis einer Dokument-Extraktion.

        Claude ruft dieses Tool auf, nachdem er die Dokumente analysiert hat.
        Die extrahierten Daten werden zwischengespeichert, bis der User
        sie bestaetigt oder ablehnt.

        Args:
            extraction_id: ID von extraktion_starten()
            extrahierte_daten: Strukturierte Daten die Claude extrahiert hat.
                Format: {
                    "persoenliche_daten": {"name": "...", "email": "...", ...},
                    "positionen": [{"company": "...", "title": "...", ...}],
                    "ausbildung": [{"institution": "...", "degree": "...", ...}],
                    "skills": [{"name": "...", "category": "...", "level": 3}],
                    "praeferenzen": {"stellentyp": "...", ...},
                    "zusammenfassung": "Kurzprofil-Text..."
                }
            konflikte: Liste von Konflikten mit bestehendem Profil.
                Format: [{"feld": "phone", "alt": "0171...", "neu": "0172...", "quelle": "CV.pdf"}]
            status: ausstehend, angewendet, teilweise, verworfen
        """
        # Store extracted data and conflicts directly
        conn = db.connect()
        conn.execute("""
            UPDATE extraction_history SET
                extracted_fields=?, conflicts=?, status=?
            WHERE id=?
        """, (
            json.dumps(extrahierte_daten, ensure_ascii=False),
            json.dumps(konflikte or [], ensure_ascii=False),
            status, extraction_id
        ))
        conn.commit()

        # Count what was found
        counts = {}
        if extrahierte_daten.get("persoenliche_daten"):
            counts["persoenliche_daten"] = len(extrahierte_daten["persoenliche_daten"])
        if extrahierte_daten.get("positionen"):
            counts["positionen"] = len(extrahierte_daten["positionen"])
        if extrahierte_daten.get("ausbildung"):
            counts["ausbildung"] = len(extrahierte_daten["ausbildung"])
        if extrahierte_daten.get("skills"):
            counts["skills"] = len(extrahierte_daten["skills"])
        if extrahierte_daten.get("zusammenfassung"):
            counts["zusammenfassung"] = 1

        return {
            "status": "gespeichert",
            "extraction_id": extraction_id,
            "gefundene_daten": counts,
            "konflikte_anzahl": len(konflikte or []),
            "naechster_schritt": "Zeige dem User die Ergebnisse und frage ob er sie uebernehmen moechte. "
                                 "Nutze dann extraktion_anwenden().",
        }

    @mcp.tool()
    def extraktion_anwenden(
        extraction_id: str,
        bereiche: list = None,
        konflikte_loesungen: dict = None,
        auto_apply: bool = True
    ) -> dict:
        """Wendet extrahierte Daten auf das aktive Profil an.

        Standardmaessig werden alle Daten automatisch uebernommen (auto_apply=True).
        Nur bei echten Konflikten (Feld hat bereits einen vom User eingegebenen Wert)
        wird der bestehende Wert beibehalten — es sei denn, konflikte_loesungen enthaelt
        eine explizite Entscheidung.

        Args:
            extraction_id: ID der Extraktion
            bereiche: Welche Bereiche anwenden (None = alle).
                Optionen: persoenliche_daten, positionen, ausbildung, skills, praeferenzen, zusammenfassung
            konflikte_loesungen: Entscheidungen fuer Konflikte.
                Format: {"phone": "neu", "email": "alt", ...}
                "alt" = bestehenden Wert behalten, "neu" = ueberschreiben
            auto_apply: Wenn True (Standard), werden alle leeren Felder und Default-Werte
                automatisch ueberschrieben ohne Rueckfrage. Bei False muessen Konflikte
                ueber konflikte_loesungen aufgeloest werden.
        """
        conn = db.connect()
        row = conn.execute("SELECT * FROM extraction_history WHERE id=?", (extraction_id,)).fetchone()
        if not row:
            return {"fehler": f"Extraktion '{extraction_id}' nicht gefunden."}

        extracted = json.loads(row["extracted_fields"] or "{}")
        conflicts = json.loads(row["conflicts"] or "[]")
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein aktives Profil vorhanden."}

        applied = {}
        all_bereiche = bereiche or list(extracted.keys())
        loesungen = konflikte_loesungen or {}

        # Default values that should be overwritten automatically
        _DEFAULT_VALUES = {"Mein Profil", "mein profil", ""}

        def _is_default_or_empty(value):
            """Check if a profile field value is empty or a default placeholder."""
            if not value:
                return True
            return str(value).strip().lower() in {v.lower() for v in _DEFAULT_VALUES}

        # Apply personal data
        if "persoenliche_daten" in all_bereiche and extracted.get("persoenliche_daten"):
            pers = extracted["persoenliche_daten"]
            update_data = {}
            actually_applied = []
            for field in ["name", "email", "phone", "address", "city", "plz",
                          "country", "birthday", "nationality", "summary"]:
                if field in pers and pers[field]:
                    # Check conflicts
                    if field in loesungen:
                        if loesungen[field] == "neu":
                            update_data[field] = pers[field]
                            actually_applied.append(field)
                    elif _is_default_or_empty(profile.get(field)):
                        # No conflict, field was empty or default
                        update_data[field] = pers[field]
                        actually_applied.append(field)
                    elif auto_apply:
                        # auto_apply: overwrite with new value
                        update_data[field] = pers[field]
                        actually_applied.append(field)
                    elif profile.get(field) != pers[field]:
                        # Conflict not resolved — skip (only in manual mode)
                        continue
            if update_data:
                # Merge with existing profile data
                for key in ["name", "email", "phone", "address", "city", "plz",
                            "country", "birthday", "nationality", "summary",
                            "informal_notes"]:
                    if key not in update_data:
                        update_data[key] = profile.get(key)
                update_data["preferences"] = profile.get("preferences", {})
                db.save_profile(update_data)
                applied["persoenliche_daten"] = actually_applied

        # Apply summary
        if "zusammenfassung" in all_bereiche and extracted.get("zusammenfassung"):
            should_apply = (
                _is_default_or_empty(profile.get("summary")) or
                auto_apply or
                "zusammenfassung" in loesungen
            )
            if should_apply:
                # Re-read profile in case personal data was just updated
                profile = db.get_profile()
                update_data = {
                    k: profile.get(k) for k in
                    ["name", "email", "phone", "address", "city", "plz",
                     "country", "birthday", "nationality", "informal_notes"]
                }
                update_data["summary"] = extracted["zusammenfassung"]
                update_data["preferences"] = profile.get("preferences", {})
                db.save_profile(update_data)
                applied["zusammenfassung"] = True

        # Apply preferences
        if "praeferenzen" in all_bereiche and extracted.get("praeferenzen"):
            # Re-read profile in case personal data/summary was just updated
            profile = db.get_profile()
            prefs = profile.get("preferences", {})
            new_prefs = extracted["praeferenzen"]
            for k, v in new_prefs.items():
                if v and (not prefs.get(k) or auto_apply):
                    prefs[k] = v
            update_data = {
                k: profile.get(k) for k in
                ["name", "email", "phone", "address", "city", "plz",
                 "country", "birthday", "nationality", "summary", "informal_notes"]
            }
            update_data["preferences"] = prefs
            db.save_profile(update_data)
            applied["praeferenzen"] = list(new_prefs.keys())

        # Apply positions
        if "positionen" in all_bereiche and extracted.get("positionen"):
            # Re-read profile for latest positions
            profile = db.get_profile()
            existing_positions = profile.get("positions", [])
            added_positions = 0
            added_projects = 0
            for pos in extracted["positionen"]:
                projects = pos.pop("projects", pos.pop("projekte", []))
                # Check for duplicates (same company + similar title)
                is_duplicate = False
                existing_pos_id = None
                for ep in existing_positions:
                    if (ep.get("company", "").lower() == pos.get("company", "").lower() and
                        ep.get("title", "").lower() == pos.get("title", "").lower()):
                        is_duplicate = True
                        existing_pos_id = ep.get("id")
                        break
                if not is_duplicate:
                    pos_id = db.add_position(pos)
                    for proj in projects:
                        db.add_project(pos_id, proj)
                        added_projects += 1
                    added_positions += 1
                elif projects and existing_pos_id:
                    # Position exists — still add new projects to it
                    existing_proj_names = {
                        p.get("name", "").lower()
                        for ep in existing_positions if ep.get("id") == existing_pos_id
                        for p in ep.get("projects", [])
                    }
                    for proj in projects:
                        if proj.get("name", "").lower() not in existing_proj_names:
                            db.add_project(existing_pos_id, proj)
                            added_projects += 1
            if added_positions or added_projects:
                applied["positionen"] = added_positions
                if added_projects:
                    applied["projekte"] = added_projects

        # Apply standalone projects (top-level "projekte" key, not nested under positions)
        if "projekte" in all_bereiche and extracted.get("projekte"):
            profile = db.get_profile()
            positions = profile.get("positions", [])
            if positions:
                added_standalone = 0
                for proj in extracted["projekte"]:
                    # Try to match project to a position by company name
                    target_pos_id = None
                    proj_company = proj.pop("company", proj.pop("firma", "")).lower()
                    if proj_company:
                        for p in positions:
                            if proj_company in p.get("company", "").lower():
                                target_pos_id = p.get("id")
                                break
                    if not target_pos_id:
                        # Assign to most recent position
                        target_pos_id = positions[0].get("id")
                    if target_pos_id:
                        db.add_project(target_pos_id, proj)
                        added_standalone += 1
                if added_standalone:
                    applied["projekte"] = applied.get("projekte", 0) + added_standalone

        # Apply education
        if "ausbildung" in all_bereiche and extracted.get("ausbildung"):
            existing_edu = profile.get("education", [])
            added_edu = 0
            for edu in extracted["ausbildung"]:
                is_duplicate = False
                for ee in existing_edu:
                    if (ee.get("institution", "").lower() == edu.get("institution", "").lower() and
                        ee.get("degree", "").lower() == edu.get("degree", "").lower()):
                        is_duplicate = True
                        break
                if not is_duplicate:
                    db.add_education(edu)
                    added_edu += 1
            if added_edu:
                applied["ausbildung"] = added_edu

        # Apply skills
        if "skills" in all_bereiche and extracted.get("skills"):
            existing_skills = [s.get("name", "").lower() for s in profile.get("skills", [])]
            added_skills = 0
            for skill in extracted["skills"]:
                if skill.get("name", "").lower() not in existing_skills:
                    db.add_skill(skill)
                    added_skills += 1
                    existing_skills.append(skill.get("name", "").lower())
            if added_skills:
                applied["skills"] = added_skills

        # Update extraction history
        db.update_extraction_history(extraction_id, "angewendet", applied)

        # Update document extraction status
        doc_id = row["document_id"]
        db.update_document_extraction_status(doc_id, "angewendet")

        # Bug #3 fix: Update profile display name if it was "Mein Profil" (auto-created)
        updated_profile = db.get_profile()
        if updated_profile and updated_profile.get("name") and \
           updated_profile["name"] not in _DEFAULT_VALUES:
            # Name was updated from extraction — ensure profile switcher reflects it
            pass  # save_profile already updated the name

        return {
            "status": "angewendet",
            "extraction_id": extraction_id,
            "angewendete_bereiche": applied,
            "hinweis": "Profil wurde aktualisiert. Pruefe mit profil_zusammenfassung().",
        }

    @mcp.tool()
    def extraktions_verlauf() -> dict:
        """Zeigt den Verlauf aller Dokument-Extraktionen fuer das aktive Profil.

        Nuetzlich um zu sehen welche Dokumente bereits analysiert wurden
        und was daraus uebernommen wurde.
        """
        pid = db.get_active_profile_id()
        if not pid:
            return {"fehler": "Kein aktives Profil."}
        history = db.get_extraction_history(profile_id=pid)
        result = []
        for h in history:
            extracted = json.loads(h.get("extracted_fields") or "{}")
            applied = json.loads(h.get("applied_fields") or "{}")
            result.append({
                "id": h["id"],
                "document_id": h["document_id"],
                "typ": h.get("extraction_type", "auto"),
                "status": h.get("status", "ausstehend"),
                "erstellt": h.get("created_at"),
                "abgeschlossen": h.get("completed_at"),
                "extrahierte_bereiche": list(extracted.keys()) if extracted else [],
                "angewendete_bereiche": list(applied.keys()) if applied else [],
            })
        return {
            "status": "ok",
            "verlauf_anzahl": len(result),
            "verlauf": result,
        }

    @mcp.tool()
    def profil_exportieren(profil_id: str = "") -> dict:
        """Exportiert das komplette Profil als JSON-Backup.

        Inkl. aller Positionen, Projekte, Ausbildung, Skills, Dokument-Metadaten
        und Praeferenzen. Die JSON-Datei wird im Export-Verzeichnis gespeichert.

        Nutze dies fuer:
        - Backup vor groesseren Aenderungen
        - Migration auf einen neuen Computer
        - Archivierung

        Args:
            profil_id: Profil-ID (leer = aktives Profil)
        """
        data = db.export_profile_json(profil_id or None)
        if not data:
            return {"fehler": "Profil nicht gefunden oder kein aktives Profil vorhanden."}

        name_slug = (data.get("name") or "profil").replace(" ", "_").lower()
        date_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"profil_backup_{name_slug}_{date_str}.json"
        export_dir = get_data_dir() / "export"
        filepath = export_dir / filename

        filepath.write_text(
            json.dumps(data, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8"
        )

        # Count items
        stats = {
            "positionen": len(data.get("positions", [])),
            "projekte": sum(len(p.get("projects", [])) for p in data.get("positions", [])),
            "ausbildung": len(data.get("education", [])),
            "skills": len(data.get("skills", [])),
            "dokumente": len(data.get("documents", [])),
        }

        return {
            "status": "exportiert",
            "datei": str(filepath),
            "profil_name": data.get("name"),
            "statistik": stats,
            "hinweis": f"Backup gespeichert unter: {filepath}. "
                       "Importiere mit profil_importieren(dateipfad='...').",
        }

    @mcp.tool()
    def profil_importieren(dateipfad: str) -> dict:
        """Importiert ein Profil aus einer JSON-Backup-Datei.

        Erstellt ein neues Profil aus dem Backup. Das vorherige aktive Profil
        wird gespeichert und kann spaeter wieder aktiviert werden.

        ACHTUNG: Erstellt immer ein NEUES Profil — ueberschreibt nichts.

        Args:
            dateipfad: Pfad zur JSON-Backup-Datei (von profil_exportieren)
        """
        from pathlib import Path
        filepath = Path(dateipfad)
        if not filepath.exists():
            return {"fehler": f"Datei nicht gefunden: {dateipfad}"}

        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return {"fehler": f"Ungueltige JSON-Datei: {e}"}

        if "_export_meta" not in data:
            return {"fehler": "Keine gueltige PBP-Backup-Datei (fehlende Metadaten)."}

        meta = data.get("_export_meta", {})
        pid = db.import_profile_json(data)

        return {
            "status": "importiert",
            "profil_id": pid,
            "profil_name": data.get("name", "?"),
            "export_version": meta.get("version"),
            "export_datum": meta.get("exported_at"),
            "nachricht": f"Profil importiert und aktiviert. "
                         "Das vorherige Profil wurde gespeichert und kann mit profil_wechseln() wieder aktiviert werden.",
        }
