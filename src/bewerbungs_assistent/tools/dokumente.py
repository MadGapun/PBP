"""Dokument-Analyse und Extraktion Tools (PBP-028, PBP v0.8.0+)."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from ..database import get_data_dir


def register(mcp, db, logger):
    """Register all document-related tools."""

    @mcp.tool()
    def dokument_profil_extrahieren(document_id: str) -> dict:
        """Liest den extrahierten Text eines hochgeladenen Dokuments und gibt ihn
        zur Analyse zurück. Claude soll daraus Profildaten ableiten.

        WORKFLOW:
        1. Rufe dieses Tool mit der document_id auf
        2. Analysiere den Text und identifiziere Profildaten (Name, Skills, Positionen etc.)
        3. Vergleiche mit dem bestehenden Profil (profil_zusammenfassung)
        4. Bei neuen Daten: Frage den User ob diese übernommen werden sollen
        5. Bei Konflikten: Zeige beide Versionen und lasse den User entscheiden
        6. Speichere mit den jeweiligen Tools (profil_bearbeiten, position_hinzufügen etc.)

        Args:
            document_id: ID oder Dateiname des Dokuments
        """
        conn = db.connect()
        pid = db.get_active_profile_id()
        if not pid:
            return {"fehler": "Kein aktives Profil vorhanden."}
        # Try ID first, then filename fallback
        row = conn.execute(
            "SELECT * FROM documents WHERE id=? AND profile_id=?",
            (document_id, pid),
        ).fetchone()
        if row is None:
            row = conn.execute(
                "SELECT * FROM documents WHERE filename=? AND profile_id=? ORDER BY created_at DESC LIMIT 1",
                (document_id, pid),
            ).fetchone()
        if row is None:
            # List available documents as help
            docs = conn.execute(
                "SELECT id, filename FROM documents WHERE profile_id=? ORDER BY created_at DESC LIMIT 10",
                (pid,),
            ).fetchall()
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
                "neuen Informationen den User ob diese übernommen werden sollen. "
                "Nutze die entsprechenden Tools (profil_bearbeiten, position_hinzufügen, "
                "skill_hinzufügen etc.) um die Daten zu speichern."
            ),
        }

    @mcp.tool()
    def dokumente_zur_analyse() -> dict:
        """Listet alle Dokumente mit extrahiertem Text auf — auch bereits analysierte.

        Zeigt den Extraktions-Status jedes Dokuments an, damit auch wiederholte
        Extraktion möglich ist. Nutze extraktion_starten(document_ids=[...]) um
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
                "bereits_analysiert": d.get("extraction_status", "") not in ("nicht_extrahiert", "", "basis_analysiert"),
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
    def extraktion_starten(document_ids: list = None, force: bool = False,
                           profil_mitsenden: bool = True) -> dict:
        """Startet die intelligente Profil-Extraktion für ein oder mehrere Dokumente.

        Laedt den extrahierten Text aller angegebenen (oder aller noch nicht
        analysierten) Dokumente und gibt ihn zusammen mit dem aktuellen Profil
        zurück, damit Claude die Daten vergleichen und extrahieren kann.

        TIPP: Für viele Dokumente nutze stattdessen analyse_plan_erstellen()
        und dokumente_batch_analysieren() — das ist effizienter.

        WORKFLOW:
        1. Rufe dieses Tool auf (optional mit document_ids)
        2. Analysiere die Texte und extrahiere Profildaten
        3. Speichere mit extraktion_ergebnis_speichern()
        4. Zeige dem User Ergebnisse und Konflikte
        5. Wende an mit extraktion_anwenden()

        Args:
            document_ids: Liste von Dokument-IDs oder Dateinamen. Leer = alle noch nicht extrahierten.
            force: True = auch bereits extrahierte Dokumente erneut verarbeiten.
            profil_mitsenden: True (Standard) = Profil wird mitgesendet. False = nur Dokumente,
                spart Tokens wenn das Profil schon bekannt ist.
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
                "SELECT * FROM documents WHERE profile_id=? AND extraction_status IN ('nicht_extrahiert', 'basis_analysiert') AND extracted_text IS NOT NULL AND extracted_text != ''",
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

        result = {
            "status": "ok",
            "extraction_id": eid,
            "dokumente_anzahl": len(dokumente),
            "dokumente": dokumente,
            "anleitung": (
                "Analysiere die Dokumente und extrahiere ALLE verwertbaren Profildaten. "
                "Vergleiche mit dem aktuellen Profil. "
                "Speichere das Ergebnis mit extraktion_ergebnis_speichern(). "
                "WICHTIG: Das Feld 'zusammenfassung' ist NUR für echte Profil-Summaries "
                "(z.B. 'Lead Software Architect mit 20 Jahren Erfahrung'), NICHT für Dokument-"
                "Beschreibungen. Bei Dokumenten ohne Profil-relevante Daten: zusammenfassung weglassen. "
                "Bei Konflikten: IMMER den User fragen."
            ),
        }
        if profil_mitsenden:
            result["aktuelles_profil"] = profil_zusammenfassung_text
        else:
            result["profil_hinweis"] = "Profil nicht mitgesendet (profil_mitsenden=False). Nutze profil_zusammenfassung() bei Bedarf."
        return result

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
        sie bestätigt oder ablehnt.

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
        pid = db.get_active_profile_id()
        if not pid:
            return {"fehler": "Kein aktives Profil vorhanden."}
        updated = conn.execute("""
            UPDATE extraction_history SET
                extracted_fields=?, conflicts=?, status=?
            WHERE id=? AND profile_id=?
        """, (
            json.dumps(extrahierte_daten, ensure_ascii=False),
            json.dumps(konflikte or [], ensure_ascii=False),
            status, extraction_id, pid
        )).rowcount
        if updated == 0:
            return {"fehler": f"Extraktion '{extraction_id}' nicht gefunden."}
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
            "naechster_schritt": "Zeige dem User die Ergebnisse und frage ob er sie übernehmen möchte. "
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

        Standardmaessig werden alle Daten automatisch übernommen (auto_apply=True).
        Nur bei echten Konflikten (Feld hat bereits einen vom User eingegebenen Wert)
        wird der bestehende Wert beibehalten — es sei denn, konflikte_loesungen enthaelt
        eine explizite Entscheidung.

        Args:
            extraction_id: ID der Extraktion
            bereiche: Welche Bereiche anwenden (None = alle).
                Optionen: persönliche_daten, positionen, ausbildung, skills, präferenzen, zusammenfassung
            konflikte_loesungen: Entscheidungen für Konflikte.
                Format: {"phone": "neu", "email": "alt", ...}
                "alt" = bestehenden Wert behalten, "neu" = überschreiben
            auto_apply: Wenn True (Standard), werden alle leeren Felder und Default-Werte
                automatisch überschrieben ohne Rückfrage. Bei False müssen Konflikte
                über konflikte_loesungen aufgeloest werden.
        """
        conn = db.connect()
        pid = db.get_active_profile_id()
        if not pid:
            return {"fehler": "Kein aktives Profil vorhanden."}
        row = conn.execute(
            "SELECT * FROM extraction_history WHERE id=? AND profile_id=?",
            (extraction_id, pid),
        ).fetchone()
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
                          "country", "birthday", "nationality"]:
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

        # Apply summary — ONLY if it looks like a real profile summary,
        # NOT a document description. Dokument-Zusammenfassungen (z.B.
        # "Interview-Vorbereitung für Jungheinrich") duerfen NICHT das
        # Profil-Summary überschreiben.
        if "zusammenfassung" in all_bereiche and extracted.get("zusammenfassung"):
            new_summary = extracted["zusammenfassung"]
            current_summary = profile.get("summary", "")

            # Nur anwenden wenn: Summary ist leer/default ODER der neue Text
            # ist länger und sieht nach einem echten Profil-Summary aus
            # (enthaelt typische Profil-Keywords wie "Jahre", "Erfahrung", "Architekt" etc.)
            _PROFIL_KEYWORDS = {"erfahrung", "jahre", "beruf", "architekt", "engineer",
                                "manager", "berater", "consultant", "entwickler", "experte",
                                "spezialist", "leiter", "lead", "senior", "principal"}
            new_lower = new_summary.lower()
            has_profil_keywords = any(kw in new_lower for kw in _PROFIL_KEYWORDS)

            should_apply = False
            if _is_default_or_empty(current_summary):
                # Profil hat noch kein Summary — immer anwenden
                should_apply = True
            elif has_profil_keywords and len(new_summary) > len(current_summary):
                # Neues Summary sieht nach echtem Profil aus UND ist ausführlicher
                should_apply = True
            elif "zusammenfassung" in loesungen and loesungen["zusammenfassung"] == "neu":
                # User hat explizit entschieden
                should_apply = True
            # NICHT auto_apply für Summary — das war der Bug!

            if should_apply:
                # Re-read profile in case personal data was just updated
                profile = db.get_profile()
                update_data = {
                    k: profile.get(k) for k in
                    ["name", "email", "phone", "address", "city", "plz",
                     "country", "birthday", "nationality", "informal_notes"]
                }
                update_data["summary"] = new_summary
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
            "hinweis": "Profil wurde aktualisiert. Prüfe mit profil_zusammenfassung().",
        }

    # ── Hilfsfunktion: Duplikat-Erkennung ──────────────────────────────────

    def _find_duplicates(documents: list) -> tuple:
        """Erkennt PDF/DOCX-Paare mit gleichem Basisnamen.

        Returns:
            (unique_docs, duplicate_ids): unique_docs to analyze, IDs of duplicates to skip
        """
        by_basename = {}
        for doc in documents:
            fname = doc.get("filename", "")
            base = os.path.splitext(fname)[0].lower()
            if base not in by_basename:
                by_basename[base] = []
            by_basename[base].append(doc)

        unique = []
        duplicate_ids = []
        for base, group in by_basename.items():
            if len(group) == 1:
                unique.append(group[0])
            else:
                # Keep the version with more text
                group.sort(key=lambda d: d.get("text_laenge", 0), reverse=True)
                unique.append(group[0])
                for dup in group[1:]:
                    duplicate_ids.append(dup["id"])
        return unique, duplicate_ids

    # ── Hilfsfunktion: Firma aus Dateiname extrahieren ───────────────────

    def _extract_firma_from_filename(filename: str) -> str | None:
        """Extrahiert den Firmennamen aus CV/Lebenslauf-Dateinamen.

        Patterns:
        - Lebenslauf;Mustermann,Max-FIRMA.pdf
        - CV;Mustermann,Max-FIRMA.docx
        - Anschreiben;Mustermann,Max-FIRMA.pdf
        """
        base = os.path.splitext(filename)[0]
        patterns = [
            r'(?:Lebenslauf|CV|Anschreiben)[;,]\s*[^-]+-\s*(.+)',
            r'(?:Lebenslauf|CV|Anschreiben)\s+[^-]+-\s*(.+)',
        ]
        for pattern in patterns:
            match = re.match(pattern, base, re.IGNORECASE)
            if match:
                firma = match.group(1).strip()
                # Filter non-company values
                skip_words = {"ausfuehrlich", "frankenstein", "freelance", "allgemein",
                              "vorlage", "template", "entwurf", "draft"}
                if firma.lower() in skip_words:
                    return None
                if re.match(r'^\d{8}$', firma):  # Date like 20260203
                    return None
                return firma
        return None

    def _extract_doc_type_from_filename(filename: str) -> str:
        """Erkennt den Dokumenttyp aus dem Dateinamen."""
        lower = filename.lower()
        # Special cases
        if "master-wissen" in lower or "bewerbungs-master" in lower:
            return "referenz"
        if any(kw in lower for kw in ["vorbereitung", "preparation", "interview-prep"]):
            return "vorbereitung"
        if any(kw in lower for kw in ["projektliste", "project-list", "projekte"]):
            return "projektliste"
        if any(kw in lower for kw in ["lebenslauf", "cv", "resume", "vita"]):
            return "lebenslauf"
        if any(kw in lower for kw in ["anschreiben", "cover", "motivationsschreiben"]):
            return "anschreiben"
        if any(kw in lower for kw in ["zeugnis", "arbeitszeugnis"]):
            return "zeugnis"
        if any(kw in lower for kw in ["referenz", "reference", "empfehlung"]):
            return "referenz"
        if any(kw in lower for kw in ["zertifikat", "certificate", "bescheinigung"]):
            return "zertifikat"
        return "sonstiges"

    # ── Neue Tools ───────────────────────────────────────────────────────

    @mcp.tool()
    def analyse_plan_erstellen() -> dict:
        """Erstellt einen Analyse-Plan BEVOR die eigentliche Extraktion startet.

        Zeigt:
        - Wie viele Dokumente es gibt
        - Wie viele Duplikate (PDF/DOCX-Paare) automatisch übersprungen werden
        - Geschätzte Batch-Anzahl und Token-Verbrauch
        - Empfohlene Vorgehensweise

        Rufe dieses Tool ZUERST auf, bevor du mit der Analyse beginnst.
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein aktives Profil."}

        conn = db.connect()
        pid = profile["id"]
        all_docs = conn.execute(
            "SELECT id, filename, doc_type, extraction_status, "
            "LENGTH(extracted_text) as text_laenge, created_at "
            "FROM documents WHERE profile_id=? AND extracted_text IS NOT NULL "
            "AND extracted_text != '' ORDER BY filename",
            (pid,)
        ).fetchall()

        docs = [dict(d) for d in all_docs]
        nicht_analysiert = [d for d in docs if d["extraction_status"] in ("nicht_extrahiert", "basis_analysiert")]
        bereits_analysiert = [d for d in docs if d["extraction_status"] not in ("nicht_extrahiert", "basis_analysiert")]

        # Duplikate erkennen
        unique, dup_ids = _find_duplicates(nicht_analysiert)

        # Batches berechnen (max 50KB Text pro Batch)
        MAX_BATCH_BYTES = 50000
        batches = []
        current_batch = []
        current_size = 0
        for doc in sorted(unique, key=lambda d: d.get("text_laenge", 0)):
            size = doc.get("text_laenge", 0)
            if current_size + size > MAX_BATCH_BYTES and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_size = 0
            current_batch.append(doc)
            current_size += size
        if current_batch:
            batches.append(current_batch)

        # Firmen erkennen
        firmen = set()
        for doc in docs:
            firma = _extract_firma_from_filename(doc["filename"])
            if firma:
                firmen.add(firma)

        total_bytes = sum(d.get("text_laenge", 0) for d in unique)
        return {
            "status": "ok",
            "dokumente_gesamt": len(docs),
            "bereits_analysiert": len(bereits_analysiert),
            "noch_zu_analysieren": len(nicht_analysiert),
            "duplikate_erkannt": len(dup_ids),
            "unique_dokumente": len(unique),
            "geschaetzte_batches": len(batches),
            "total_text_bytes": total_bytes,
            "geschaetzte_tokens": total_bytes // 4,
            "erkannte_firmen": sorted(firmen),
            "batches": [
                {"nr": i + 1, "dokumente": len(b),
                 "bytes": sum(d.get("text_laenge", 0) for d in b),
                 "dateien": [d["filename"] for d in b]}
                for i, b in enumerate(batches)
            ],
            "empfehlung": (
                f"{len(dup_ids)} Duplikate werden automatisch übersprungen. "
                f"{len(unique)} einzigartige Dokumente in {len(batches)} Batches analysieren. "
                f"Nutze dokumente_batch_analysieren() für den nächsten Batch."
            ),
        }

    @mcp.tool()
    def dokumente_batch_analysieren(
        batch_nr: int = 1,
        max_text_bytes: int = 50000,
        max_dokumente: int = 10,
        profil_mitsenden: bool = True,
    ) -> dict:
        """Analysiert den nächsten Batch von Dokumenten — effizient und Token-sparend.

        Erkennt PDF/DOCX-Duplikate automatisch und überspring sie.
        Sortiert Dokumente nach Größe (kleinste zuerst) für optimale Batch-Füllung.

        WORKFLOW:
        1. Rufe analyse_plan_erstellen() auf um den Plan zu sehen
        2. Rufe dokumente_batch_analysieren(batch_nr=1) auf
        3. Analysiere die zurückgegebenen Texte
        4. Speichere Ergebnisse mit extraktion_ergebnis_speichern()
        5. Wende an mit extraktion_anwenden()
        6. Wiederhole mit batch_nr=2, 3, ... bis alle durch

        Args:
            batch_nr: Welcher Batch (1-basiert). Standard: 1 (erster Batch).
            max_text_bytes: Maximale Text-Bytes pro Batch (Token-Budget). Standard: 50000 (~12.5K Tokens).
            max_dokumente: Maximale Anzahl Dokumente pro Batch. Standard: 10.
            profil_mitsenden: Wenn True (Standard), wird das Profil mitgesendet. Bei Folge-Batches
                auf False setzen um Tokens zu sparen.
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein aktives Profil."}

        conn = db.connect()
        pid = profile["id"]
        rows = conn.execute(
            "SELECT * FROM documents WHERE profile_id=? AND extraction_status IN ('nicht_extrahiert', 'basis_analysiert') "
            "AND extracted_text IS NOT NULL AND extracted_text != '' ORDER BY LENGTH(extracted_text)",
            (pid,)
        ).fetchall()
        all_docs = [dict(r) for r in rows]

        if not all_docs:
            return {"status": "fertig", "nachricht": "Alle Dokumente sind bereits analysiert."}

        # Duplikate erkennen und automatisch markieren
        for d in all_docs:
            d["text_laenge"] = len(d.get("extracted_text", ""))
        unique, dup_ids = _find_duplicates(all_docs)

        # Duplikate als analysiert markieren
        for dup_id in dup_ids:
            db.update_document_extraction_status(dup_id, "duplikat")
        if dup_ids:
            logger.info("Batch: %d Duplikate automatisch markiert", len(dup_ids))

        # Batches berechnen
        sorted_docs = sorted(unique, key=lambda d: d.get("text_laenge", 0))
        batches = []
        current_batch = []
        current_size = 0
        for doc in sorted_docs:
            size = doc.get("text_laenge", 0)
            if (current_size + size > max_text_bytes or len(current_batch) >= max_dokumente) and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_size = 0
            current_batch.append(doc)
            current_size += size
        if current_batch:
            batches.append(current_batch)

        if batch_nr > len(batches):
            return {"status": "fertig", "nachricht": f"Nur {len(batches)} Batches vorhanden. Alle Dokumente verarbeitet."}

        batch = batches[batch_nr - 1]

        # Extraction history für den Batch erstellen
        eid = db.add_extraction_history({
            "document_id": batch[0]["id"],
            "profile_id": pid,
            "extraction_type": "batch",
        })

        # Dokumente aufbereiten (nur Text + Metadaten, KEIN Profil bei Folge-Batches)
        dokumente = []
        for doc in batch:
            dokumente.append({
                "id": doc["id"],
                "filename": doc["filename"],
                "doc_type": doc.get("doc_type", "sonstiges"),
                "text_laenge": doc["text_laenge"],
                "extrahierter_text": doc.get("extracted_text", ""),
            })

        result = {
            "status": "ok",
            "extraction_id": eid,
            "batch_nr": batch_nr,
            "batches_gesamt": len(batches),
            "dokumente_in_batch": len(dokumente),
            "duplikate_uebersprungen": len(dup_ids),
            "dokumente": dokumente,
            "anleitung": (
                "Analysiere die Dokumente und extrahiere Profildaten. "
                "Speichere mit extraktion_ergebnis_speichern(). "
                "Dann extraktion_anwenden(). "
                "Danach: dokumente_batch_analysieren(batch_nr=" + str(batch_nr + 1) + ") für den nächsten Batch."
            ),
        }

        if profil_mitsenden:
            result["aktuelles_profil"] = {
                "name": profile.get("name"),
                "summary": profile.get("summary"),
                "positionen_anzahl": len(profile.get("positions", [])),
                "skills": [s.get("name") for s in profile.get("skills", [])],
                "skills_anzahl": len(profile.get("skills", [])),
            }
        else:
            result["profil_hinweis"] = "Profil wurde im ersten Batch gesendet. Nutze das gleiche Profil als Referenz."

        return result

    @mcp.tool()
    def dokumente_bulk_markieren(
        document_ids: list = None,
        status: str = "angewendet",
        zusammenfassung: str = "Keine neuen Profildaten — bereits im Profil erfasst.",
    ) -> dict:
        """Markiert mehrere Dokumente gleichzeitig als analysiert.

        Ideal für Dokumente die offensichtlich keine neuen Profildaten enthalten
        (z.B. firmenspezifische CV-Varianten wenn das Basisprofil schon vollständig ist,
        oder Duplikate).

        Args:
            document_ids: Liste von Dokument-IDs. Wenn leer: markiert ALLE unanalysierten.
            status: Zielstatus. Standard: "angewendet". Optionen: angewendet, verworfen, duplikat.
            zusammenfassung: Kurze Begründung warum ohne Analyse markiert.
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein aktives Profil."}

        conn = db.connect()
        pid = profile["id"]

        if document_ids:
            placeholders = ",".join("?" * len(document_ids))
            rows = conn.execute(
                f"SELECT id, filename FROM documents WHERE id IN ({placeholders}) AND profile_id=?",
                (*document_ids, pid)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT id, filename FROM documents WHERE profile_id=? "
                "AND extraction_status IN ('nicht_extrahiert', 'basis_analysiert') "
                "AND extracted_text IS NOT NULL AND extracted_text != ''",
                (pid,)
            ).fetchall()

        if not rows:
            return {"status": "keine_dokumente", "nachricht": "Keine passenden Dokumente gefunden."}

        markiert = []
        for row in rows:
            db.update_document_extraction_status(row["id"], status)
            markiert.append({"id": row["id"], "filename": row["filename"]})

        logger.info("Bulk-Markierung: %d Dokumente als '%s' markiert", len(markiert), status)
        return {
            "status": "ok",
            "markiert_anzahl": len(markiert),
            "zielstatus": status,
            "zusammenfassung": zusammenfassung,
            "dokumente": markiert,
        }

    @mcp.tool()
    def bewerbungs_dokumente_erkennen(auto_erstellen: bool = False) -> dict:
        """Analysiert Dateinamen und erkennt Bewerbungs-Zuordnungen.

        Erkennt aus firmenspezifischen CVs und Anschreiben:
        - Firma (aus Dateiname extrahiert)
        - Dokumenttyp (Lebenslauf, Anschreiben, Projektliste)
        - Erstellungsdatum (= Bewerbungsdatum)
        - Ob bereits eine Bewerbung für diese Firma existiert

        Args:
            auto_erstellen: Wenn True, werden Bewerbungseinträge automatisch
                für alle erkannten Firmen angelegt (die noch keinen Eintrag haben).
                Das Erstellungsdatum des Dokuments wird als Bewerbungsdatum verwendet.
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein aktives Profil."}

        conn = db.connect()
        pid = profile["id"]
        docs = conn.execute(
            "SELECT id, filename, doc_type, created_at FROM documents "
            "WHERE profile_id=? ORDER BY filename",
            (pid,)
        ).fetchall()

        # Bestehende Bewerbungen laden
        existing_apps = conn.execute(
            "SELECT company, title FROM applications WHERE profile_id=?", (pid,)
        ).fetchall()
        existing_companies = {row["company"].lower() for row in existing_apps if row["company"]}

        # Dokumente nach Firma gruppieren
        firmen_docs = {}
        for doc in docs:
            doc = dict(doc)
            firma = _extract_firma_from_filename(doc["filename"])
            if not firma:
                continue
            doc_type = _extract_doc_type_from_filename(doc["filename"])
            if firma not in firmen_docs:
                firmen_docs[firma] = {
                    "firma": firma,
                    "dokumente": [],
                    "bewerbung_existiert": firma.lower() in existing_companies,
                    "fruehestes_datum": doc.get("created_at"),
                }
            firmen_docs[firma]["dokumente"].append({
                "id": doc["id"],
                "filename": doc["filename"],
                "typ": doc_type,
                "datum": doc.get("created_at"),
            })
            # Frühestes Datum tracken
            if doc.get("created_at") and (
                not firmen_docs[firma]["fruehestes_datum"] or
                doc["created_at"] < firmen_docs[firma]["fruehestes_datum"]
            ):
                firmen_docs[firma]["fruehestes_datum"] = doc["created_at"]

        # Ergebnis sortieren
        erkannt = sorted(firmen_docs.values(), key=lambda f: f["firma"])
        neue_firmen = [f for f in erkannt if not f["bewerbung_existiert"]]

        # Auto-Erstellung von Bewerbungseinträgen
        erstellt = []
        if auto_erstellen and neue_firmen:
            for firma_info in neue_firmen:
                firma = firma_info["firma"]
                # Dokumenttypen bestimmen
                doc_types = [d["typ"] for d in firma_info["dokumente"]]
                has_anschreiben = "anschreiben" in doc_types
                has_cv = "lebenslauf" in doc_types

                # Bewerbungsdatum = frühestes Dokument-Datum
                applied_at = ""
                if firma_info.get("fruehestes_datum"):
                    try:
                        dt = datetime.fromisoformat(firma_info["fruehestes_datum"])
                        applied_at = dt.strftime("%Y-%m-%d")
                    except (ValueError, TypeError):
                        pass

                # Stellentitel ableiten
                title = f"Bewerbung bei {firma}"
                bewerbungsart = "mit_dokumenten" if has_cv else "elektronisch"
                lv_variante = "angepasst" if has_cv else "keiner"

                notes = f"Automatisch erkannt aus {len(firma_info['dokumente'])} Dokument(en): "
                notes += ", ".join(d["filename"] for d in firma_info["dokumente"][:3])

                aid = db.add_application({
                    "title": title, "company": firma, "url": "",
                    "job_hash": None, "status": "beworben",
                    "applied_at": applied_at, "notes": notes,
                    "bewerbungsart": bewerbungsart,
                    "lebenslauf_variante": lv_variante,
                })
                erstellt.append({"firma": firma, "bewerbung_id": aid, "datum": applied_at})
                firma_info["bewerbung_erstellt"] = True
                firma_info["bewerbung_id"] = aid
            logger.info("Auto-Erstellung: %d Bewerbungen aus Dokumenten angelegt", len(erstellt))

        result = {
            "status": "ok",
            "erkannte_firmen": len(erkannt),
            "neue_firmen": len(neue_firmen),
            "bereits_erfasst": len(erkannt) - len(neue_firmen),
            "firmen": erkannt,
        }

        if erstellt:
            result["auto_erstellt"] = erstellt
            result["naechster_schritt"] = (
                f"{len(erstellt)} Bewerbung(en) automatisch angelegt. "
                "Prüfe im Dashboard unter 'Bewerbungen' ob alles stimmt."
            )
        elif neue_firmen:
            result["naechster_schritt"] = (
                f"{len(neue_firmen)} Firma(en) ohne Bewerbungseintrag erkannt. "
                "Nutze bewerbungs_dokumente_erkennen(auto_erstellen=True) um alle automatisch anzulegen, "
                "oder bewerbung_erstellen() für einzelne Firmen."
            )
        else:
            result["naechster_schritt"] = "Alle erkannten Firmen haben bereits Bewerbungseinträge."

        return result

    @mcp.tool()
    def extraktions_verlauf() -> dict:
        """Zeigt den Verlauf aller Dokument-Extraktionen für das aktive Profil.

        Nützlich um zu sehen welche Dokumente bereits analysiert wurden
        und was daraus übernommen wurde.
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
        und Präferenzen. Die JSON-Datei wird im Export-Verzeichnis gespeichert.

        Nutze dies für:
        - Backup vor größeren Änderungen
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
        wird gespeichert und kann später wieder aktiviert werden.

        ACHTUNG: Erstellt immer ein NEUES Profil — überschreibt nichts.

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
            return {"fehler": f"Ungültige JSON-Datei: {e}"}

        if "_export_meta" not in data:
            return {"fehler": "Keine gültige PBP-Backup-Datei (fehlende Metadaten)."}

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
