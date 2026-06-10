"""Dokument-Analyse und Extraktion Tools (PBP-028, PBP v0.8.0+)."""

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from ..database import get_data_dir


def _company_match_key(name: str) -> str:
    """#686: Firmenname auf einen distinktiven Such-Schluessel reduzieren.

    Entfernt Rechtsformen/Generika (SE, GmbH, AG, Group, ...) und nimmt das
    laengste verbleibende Token (>=4 Zeichen): 'adesso SE' -> 'adesso',
    'Bechtle GmbH' -> 'bechtle', 'Lufthansa Technik' -> 'lufthansa'. Liefert ''
    wenn nichts Distinktives bleibt (dann findet kein Matching statt) — bewusst
    konservativ gegen Falsch-Treffer bei sehr kurzen/generischen Namen.
    """
    s = (name or "").lower()
    s = re.sub(r"[^\w\s]", " ", s, flags=re.UNICODE)
    stop = {
        "se", "ag", "gmbh", "mbh", "kg", "ohg", "ug", "kgaa", "ek", "co",
        "inc", "ltd", "llc", "plc", "group", "gruppe", "holding", "deutschland",
        "germany", "international", "the", "und", "and", "von", "der", "die", "das",
    }
    tokens = [t for t in s.split() if t not in stop and len(t) >= 4]
    if not tokens:
        tokens = [t for t in s.split() if len(t) >= 4]
    return max(tokens, key=len) if tokens else ""


def register(mcp, db, logger):
    """Register all document-related tools."""
    from . import ki_gate

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
        gate = ki_gate(db, "dokumentenanalyse")
        if gate is not None:
            return gate
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
    def dokumente_zur_analyse(archiv: bool = False) -> dict:
        """Listet alle Dokumente mit extrahiertem Text auf — auch bereits analysierte.

        Zeigt den Extraktions-Status jedes Dokuments an, damit auch wiederholte
        Extraktion möglich ist. Nutze extraktion_starten(document_ids=[...]) um
        bestimmte Dokumente erneut zu extrahieren.

        v1.7.0-beta.79 (#657 E16): Default-Filter `lifecycle='aktiv'`. Mit
        `archiv=True` werden archivierte/veraltete Dokumente mit aufgelistet
        — analog zu `bewerbungen_anzeigen(archiv=True)`.

        Args:
            archiv: False (Default) zeigt nur lifecycle=aktiv.
                True zeigt ALLE (aktiv + archiviert + veraltet).
        """
        profile = db.get_profile()
        if profile is None:
            return {"status": "kein_profil",
                    "nachricht": "Noch kein Profil vorhanden. Starte die Ersterfassung "
                                 "mit ersterfassung_starten() oder lege es mit profil_erstellen() an."}

        # v1.7.0-beta.64 (#640): Status-Stufen explizit trennen.
        # 'nicht_extrahiert'/'' = nie angefasst
        # 'basis_analysiert'    = nur Regex-Basics, KI-Tiefenanalyse FEHLT
        # 'angewendet'/sonstige = tief analysiert
        # Sowohl nie-angefasste ALS AUCH nur-Basis gelten als "zu analysieren".
        _PENDING = ("nicht_extrahiert", "", "basis_analysiert", None)
        docs = profile.get("documents", [])
        # v1.7.0-beta.79 (#657 E16): Default-Filter lifecycle=aktiv.
        if not archiv:
            docs = [d for d in docs if (d.get("lifecycle") or "aktiv") == "aktiv"]
        analysierbare = [
            {
                "id": d["id"],
                "filename": d["filename"],
                "doc_type": d.get("doc_type", "sonstiges"),
                "hat_text": bool(d.get("extracted_text")),
                "text_laenge": len(d.get("extracted_text", "")),
                "extraction_status": d.get("extraction_status", "nicht_extrahiert"),
                "lifecycle": d.get("lifecycle", "aktiv"),
                "bereits_analysiert": d.get("extraction_status", "") not in _PENDING,
                "nur_basis": d.get("extraction_status", "") == "basis_analysiert",
            }
            for d in docs
            if d.get("extracted_text")
        ]
        neue = [d for d in analysierbare if not d["bereits_analysiert"]]
        nur_basis = [d for d in analysierbare if d["nur_basis"]]
        nie_analysiert = [
            d for d in neue if not d["nur_basis"]
        ]
        return {
            "status": "ok",
            "dokumente_gesamt": len(docs),
            "analysierbare": len(analysierbare),
            "neue_dokumente": len(neue),
            # #640: separate Zaehler damit klar wird WAS noch aussteht
            "nie_analysiert": len(nie_analysiert),
            "nur_basis_extraktion": len(nur_basis),
            "hinweis_tiefenanalyse": (
                f"{len(nur_basis)} Dokument(e) haben nur die Basis-Extraktion "
                "(Regex) durchlaufen — die KI-Tiefenanalyse fehlt noch. "
                "Nutze /dokumente_verarbeiten oder extraktion_starten()."
            ) if nur_basis else "",
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

        # #243: Dokument-Status auf 'analysiert' setzen nach erfolgreicher Extraktion
        row = conn.execute(
            "SELECT document_id FROM extraction_history WHERE id=?",
            (extraction_id,)
        ).fetchone()
        if row:
            db.update_document_extraction_status(row["document_id"], "analysiert")

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

    # v1.7.0-beta.68 (#642): erweiterte Nicht-Firma-Blacklist (umlaut-normalisiert)
    _FIRMA_SKIP_WORDS = {
        "ausfuehrlich", "frankenstein", "freelance", "freelancer", "allgemein",
        "vorlage", "template", "entwurf", "draft", "final", "neu", "alt",
        "kopie", "copy", "kurz", "lang", "deutsch", "english", "englisch",
        "anonym", "anonymisiert", "blanko", "blank", "master", "standard",
        "aktuell", "version", "foto", "mitfoto", "ohnefoto",
    }

    def _norm_firma(token: str) -> str:
        """Normalisiert einen Firma-Token fuer Blacklist-Vergleich (#642)."""
        t = token.lower().strip()
        for uml, repl in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
            t = t.replace(uml, repl)
        return re.sub(r"[^a-z0-9]", "", t)

    def _extract_firma_from_filename(filename: str) -> str | None:
        """Extrahiert den Firmennamen aus CV/Lebenslauf-Dateinamen.

        Patterns:
        - Lebenslauf;Mustermann,Max-FIRMA.pdf
        - CV;Mustermann,Max-FIRMA.docx
        - Anschreiben;Mustermann,Max-FIRMA.pdf

        v1.7.0-beta.68 (#642): Greift nicht mehr bei generischen CV-Varianten
        (Kuerzel SC/SL, Sprach-/Versions-Suffixe, "ausfuehrlich"/"freelancer"),
        und behandelt firmeninterne Bindestriche korrekt (nimmt den GESAMTEN
        Rest nach dem Namen -> "Beispiel-Systems" bleibt ganz statt zu
        "Systems" verstuemmelt zu werden).
        """
        base = os.path.splitext(filename)[0]
        # DocType-Praefix entfernen (Lebenslauf/CV/Anschreiben + Trenner).
        m = re.match(r'(?:Lebenslauf|CV|Anschreiben)[;,\s]+(.+)', base, re.IGNORECASE)
        if not m:
            return None
        rest = m.group(1).strip()

        # Name/Firma-Trenner bestimmen. Gemischte Formate in der Praxis:
        #   "Name,Vorname; Firma-Mit-Bindestrich"  -> Trenner ';'
        #   "Name,Vorname-Firma"                    -> Trenner '-'
        # Wenn ein ';' vorhanden ist, ist die Firma der Teil nach dem LETZTEN
        # ';' (Firma darf dann Bindestriche enthalten -> "Dassault-Systems"
        # bleibt ganz). Sonst nach dem ERSTEN '-' (Name traegt selbst keinen
        # Bindestrich). Behebt das #642-Verstuemmeln zu "Systems".
        if ";" in rest:
            firma = rest.rsplit(";", 1)[1].strip()
        elif "-" in rest:
            firma = rest.split("-", 1)[1].strip()
        else:
            return None

        firma_norm = _norm_firma(firma)
        # Generische Nicht-Firma-Tokens raus (umlaut-normalisiert)
        if firma_norm in _FIRMA_SKIP_WORDS:
            return None
        # Leerer Token nach Normalisierung (nur Sonderzeichen/Zahlen)
        if not firma_norm:
            return None
        # Kuerzel ablehnen: <= 3 Zeichen UND keine Kleinbuchstaben
        # (z.B. "SC", "SL", "BWI" — Initialen, keine echte Firma)
        stripped = firma.replace(".", "").replace("-", "").replace(" ", "")
        if len(stripped) <= 3 and not any(c.islower() for c in stripped):
            return None
        # Reine Zahlen / Datum ablehnen (z.B. 20260203)
        if re.fullmatch(r'[\d\s.\-_]+', firma):
            return None
        return firma

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
    def analyse_plan_erstellen(archiv: bool = False) -> dict:
        """Erstellt einen Analyse-Plan BEVOR die eigentliche Extraktion startet.

        Zeigt:
        - Wie viele Dokumente es gibt
        - Wie viele Duplikate (PDF/DOCX-Paare) automatisch übersprungen werden
        - Geschätzte Batch-Anzahl und Token-Verbrauch
        - Empfohlene Vorgehensweise

        Rufe dieses Tool ZUERST auf, bevor du mit der Analyse beginnst.

        v1.7.0-beta.59 (#635): Response-Payload reduziert (nur 3 Datei-
        Vorschauen pro Batch statt aller). Byte-Counter nutzt CAST AS
        BLOB damit UTF-8-Sonderzeichen korrekt gezaehlt werden.

        v1.7.0-beta.79 (#657 E16): Default-Filter `lifecycle='aktiv'`.
        Archivierte/veraltete Dokumente tauchen nicht mehr im Plan auf —
        sie sind ausgeblendet, aber via `archiv=True` einsehbar.

        Args:
            archiv: False (Default) plant nur lifecycle=aktiv.
                True bezieht archivierte/veraltete Docs mit ein.
        """
        import time as _t
        _t0 = _t.time()
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein aktives Profil.",
                    "nachricht": "Starte die Ersterfassung mit ersterfassung_starten() "
                                 "oder lege ein Profil mit profil_erstellen() an."}

        conn = db.connect()
        pid = profile["id"]
        # #635: LENGTH(BLOB) liefert Bytes — bei UTF-8 mit Umlauten/Sonderzeichen
        # ist das praeziser als LENGTH() (Char-Count). Verhindert Underestimation
        # die zu zu-grossen Batches fuehrt.
        # #657 E16: Default-Filter lifecycle=aktiv.
        lifecycle_clause = "" if archiv else " AND lifecycle='aktiv'"
        all_docs = conn.execute(
            "SELECT id, filename, doc_type, extraction_status, lifecycle, "
            "LENGTH(CAST(extracted_text AS BLOB)) as text_laenge, created_at "
            "FROM documents WHERE profile_id=? AND extracted_text IS NOT NULL "
            "AND extracted_text != ''"
            + lifecycle_clause
            + " ORDER BY filename",
            (pid,)
        ).fetchall()

        docs = [dict(d) for d in all_docs]
        nicht_analysiert = [d for d in docs if d["extraction_status"] in ("nicht_extrahiert", "basis_analysiert")]
        bereits_analysiert = [d for d in docs if d["extraction_status"] not in ("nicht_extrahiert", "basis_analysiert")]

        # Duplikate erkennen
        unique, dup_ids = _find_duplicates(nicht_analysiert)

        # Batches berechnen (max 30KB Text pro Batch — nach unten korrigiert
        # in #635 weil 50KB + JSON-Overhead + Aktuelles-Profil regelmaessig
        # ueber MCP-Transport-Grenzen ging)
        MAX_BATCH_BYTES = 30000
        batches = []
        current_batch = []
        current_size = 0
        for doc in sorted(unique, key=lambda d: d.get("text_laenge", 0)):
            size = doc.get("text_laenge", 0) or 0
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

        # #686: Eingehende Dokumente gegen bestehende Bewerbungen matchen, damit
        # eine Mail/Anlage einer bestehenden Bewerbung zugeordnet werden kann
        # statt unbemerkt eine Dublette anzulegen. Firmenname (normalisiert) im
        # Dateinamen ODER Volltext -> Zuordnungsvorschlag. Bewusst grosszuegig
        # (Vorschlag, kein Auto-Link) — Claude/User bestaetigt.
        bewerbungs_zuordnungen = []
        try:
            apps = conn.execute(
                "SELECT id, company, title, status FROM applications "
                "WHERE profile_id=? AND company IS NOT NULL AND TRIM(company) != ''",
                (pid,)
            ).fetchall()
            analyse_ids = {d["id"] for d in nicht_analysiert}
            gesehen = set()
            for app in apps:
                firma_key = _company_match_key(app["company"])
                if len(firma_key) < 4:
                    continue
                like = f"%{firma_key}%"
                rows = conn.execute(
                    "SELECT id, filename FROM documents "
                    "WHERE profile_id=? AND extracted_text IS NOT NULL "
                    "AND extracted_text != ''" + lifecycle_clause +
                    " AND (LOWER(filename) LIKE ? OR LOWER(extracted_text) LIKE ?)",
                    (pid, like, like)
                ).fetchall()
                for r in rows:
                    schluessel = (r["id"], app["id"])
                    if schluessel in gesehen:
                        continue
                    gesehen.add(schluessel)
                    firmen.add(app["company"])  # Firma aus Bewerbung sichtbar machen
                    bewerbungs_zuordnungen.append({
                        "dokument_id": r["id"],
                        "dateiname": r["filename"],
                        "bewerbung_id": app["id"],
                        "firma": app["company"],
                        "bewerbung_titel": app["title"],
                        "bewerbung_status": app["status"],
                        "noch_zu_analysieren": r["id"] in analyse_ids,
                    })
        except Exception as exc:
            logger.warning("#686 Bewerbungs-Matching im Analyse-Plan fehlgeschlagen: %s", exc)

        total_bytes = sum((d.get("text_laenge") or 0) for d in unique)
        # #635: Pro Batch nur 3 Datei-Vorschauen + Counter — vorher alle
        # Dateinamen, was bei vielen Docs die Response sprengen konnte.
        batches_summary = []
        for i, b in enumerate(batches):
            previews = [d["filename"] for d in b[:3]]
            batches_summary.append({
                "nr": i + 1,
                "dokumente": len(b),
                "bytes": sum((d.get("text_laenge") or 0) for d in b),
                "dateien_vorschau": previews,
                "weitere_dateien": max(0, len(b) - 3),
            })

        result = {
            "status": "ok",
            "dokumente_gesamt": len(docs),
            "bereits_analysiert": len(bereits_analysiert),
            "noch_zu_analysieren": len(nicht_analysiert),
            "duplikate_erkannt": len(dup_ids),
            "unique_dokumente": len(unique),
            "geschaetzte_batches": len(batches),
            "total_text_bytes": total_bytes,
            "geschaetzte_tokens": total_bytes // 4,
            "erkannte_firmen": sorted(firmen)[:50],  # #635: Hard-Cap
            # #686: Vorschlaege, welche Dokumente zu bestehenden Bewerbungen gehoeren
            "bewerbungs_zuordnungen": bewerbungs_zuordnungen[:50],
            "batches": batches_summary,
            "empfehlung": (
                # #696: bei 0 zu analysierenden Docs nicht zum naechsten
                # Batch raten — der Neuling muss erst hochladen.
                (
                    "Keine Dokumente zu analysieren. Lade Lebenslauf & Zeugnisse "
                    "im Dashboard unter 'Dokumente' hoch."
                    if len(docs) == 0 else
                    "Alle vorhandenen Dokumente sind bereits analysiert."
                )
                if len(nicht_analysiert) == 0 else
                f"{len(dup_ids)} Duplikate werden automatisch übersprungen. "
                f"{len(unique)} einzigartige Dokumente in {len(batches)} Batches analysieren. "
                + (
                    f"{len(bewerbungs_zuordnungen)} Dokument(e) passen evtl. zu bestehenden "
                    "Bewerbungen (siehe bewerbungs_zuordnungen) — pruefe das, bevor du eine "
                    "neue Bewerbung anlegst (Dublettenschutz). "
                    if bewerbungs_zuordnungen else ""
                )
                + "Nutze dokumente_batch_analysieren() für den nächsten Batch."
            ),
        }
        logger.info(
            "analyse_plan_erstellen: %d Docs, %d Batches, %d Bytes, %.2fs",
            len(docs), len(batches), total_bytes, _t.time() - _t0,
        )
        return result

    @mcp.tool()
    def dokumente_batch_analysieren(
        batch_nr: int = 1,
        max_text_bytes: int = 30000,
        max_dokumente: int = 8,
        max_bytes_per_doc: int = 8000,
        profil_mitsenden: bool = True,
        archiv: bool = False,
        routing_modus: bool = False,
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

        v1.7.0-beta.59 (#635): Defaults nach unten korrigiert
        (max_text_bytes 50k -> 30k, max_dokumente 10 -> 8). Neuer
        Parameter `max_bytes_per_doc` (default 8000) — wenn ein einzelnes
        Dokument groesser ist wird der Text getrunkated mit Marker.
        Vorher konnte ein einzelnes 200KB-PDF die ganze MCP-Response
        sprengen und in den 4-Minuten-Timeout laufen.

        Args:
            batch_nr: Welcher Batch (1-basiert). Standard: 1.
            max_text_bytes: Maximale Text-Bytes pro Batch (Token-Budget).
                Standard: 30000 (~7.5K Tokens). Hard-Cap: 50000.
            max_dokumente: Maximale Anzahl Dokumente pro Batch. Standard: 8.
            max_bytes_per_doc: Pro-Doku-Limit. Default 8000 (~2K Tokens).
                Laengerer Text wird getrunkated mit Marker.
            profil_mitsenden: Wenn True (Standard), wird das Profil mitgesendet.
                Bei Folge-Batches auf False setzen um Tokens zu sparen.
        """
        import time as _t
        _t0 = _t.time()
        # Hard-Cap: schuetzt vor versehentlich riesigem Argument
        max_text_bytes = max(1000, min(int(max_text_bytes or 30000), 50000))
        max_dokumente = max(1, min(int(max_dokumente or 8), 20))
        max_bytes_per_doc = max(500, min(int(max_bytes_per_doc or 8000), 20000))

        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein aktives Profil.",
                    "nachricht": "Starte die Ersterfassung mit ersterfassung_starten() "
                                 "oder lege ein Profil mit profil_erstellen() an."}

        conn = db.connect()
        pid = profile["id"]
        # #635: LENGTH(BLOB) -> Bytes statt Chars (UTF-8 korrekt)
        # #657 E16: Default-Filter lifecycle=aktiv.
        lifecycle_clause = "" if archiv else " AND lifecycle='aktiv'"
        rows = conn.execute(
            "SELECT id, filename, doc_type, extraction_status, extracted_text, "
            "LENGTH(CAST(extracted_text AS BLOB)) as text_laenge "
            "FROM documents WHERE profile_id=? AND extraction_status IN ('nicht_extrahiert', 'basis_analysiert') "
            "AND extracted_text IS NOT NULL AND extracted_text != ''"
            + lifecycle_clause
            + " ORDER BY LENGTH(CAST(extracted_text AS BLOB))",
            (pid,)
        ).fetchall()
        all_docs = [dict(r) for r in rows]

        if not all_docs:
            # #696: ehrlich unterscheiden — "alles analysiert" stimmt nur,
            # wenn ueberhaupt Dokumente existieren. Der Neulings-Normalfall
            # (frische Installation, noch nichts hochgeladen) bekommt einen
            # Upload-Hinweis statt einer faktisch falschen Erfolgsmeldung.
            doc_count = conn.execute(
                "SELECT COUNT(*) AS n FROM documents WHERE profile_id=?", (pid,)
            ).fetchone()["n"]
            if doc_count == 0:
                return {"status": "keine_dokumente",
                        "nachricht": "Noch keine Dokumente hochgeladen. Lade Lebenslauf & "
                                     "Zeugnisse im Dashboard unter 'Dokumente' hoch — "
                                     "danach kann ich sie analysieren."}
            return {"status": "fertig", "nachricht": "Alle Dokumente sind bereits analysiert."}

        # Duplikate erkennen und automatisch markieren
        unique, dup_ids = _find_duplicates(all_docs)

        for dup_id in dup_ids:
            db.update_document_extraction_status(dup_id, "duplikat")
        if dup_ids:
            logger.info("Batch: %d Duplikate automatisch markiert", len(dup_ids))

        # Batches berechnen — basieren auf der **getrunkated** Groesse,
        # damit auch bei langen Dokumenten der Batch nicht ueber den Cap geht.
        sorted_docs = sorted(unique, key=lambda d: (d.get("text_laenge") or 0))
        batches = []
        current_batch = []
        current_size = 0
        for doc in sorted_docs:
            doc_size = min((doc.get("text_laenge") or 0), max_bytes_per_doc)
            if (current_size + doc_size > max_text_bytes
                    or len(current_batch) >= max_dokumente) and current_batch:
                batches.append(current_batch)
                current_batch = []
                current_size = 0
            current_batch.append(doc)
            current_size += doc_size
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

        # Dokumente aufbereiten — Text getrunkated wenn ueber Cap.
        dokumente = []
        truncations = 0
        for doc in batch:
            text = doc.get("extracted_text") or ""
            text_bytes = text.encode("utf-8", errors="replace")
            full_len = len(text_bytes)
            truncated = False
            if full_len > max_bytes_per_doc:
                # Auf Char-Grenze trunkaten damit kein Mojibake entsteht
                # (UTF-8 Multi-Byte-Sequence darf nicht in der Mitte gecuttet werden).
                text = text_bytes[:max_bytes_per_doc].decode("utf-8", errors="ignore")
                text += (
                    f"\n\n[... gekuerzt: weitere {full_len - max_bytes_per_doc} Bytes "
                    f"nicht uebertragen. extraktion_starten([\"{doc['id']}\"]) fuer "
                    f"Vollzugriff]"
                )
                truncated = True
                truncations += 1
            doc_entry = {
                "id": doc["id"],
                "filename": doc["filename"],
                "doc_type": doc.get("doc_type", "sonstiges"),
                "text_laenge_original": full_len,
                "text_laenge_uebertragen": len(text.encode("utf-8", errors="replace")),
                "gekuerzt": truncated,
                "extrahierter_text": text,
            }
            # v1.7.0-beta.80 (#643 E11): Routing-Modus -> Per-Typ-Hint mitsenden
            if routing_modus:
                from ..services.document_handlers import handle_doc
                try:
                    info = handle_doc(doc)
                except Exception:
                    info = {"typ": doc.get("doc_type"), "claude_action": "", "fields": {}}
                aktion = _DOC_ROUTING_ACTIONS.get(
                    doc.get("doc_type") or "sonstiges",
                    "noop_korrespondenz_abschliessen",
                )
                doc_entry["routing"] = {
                    "aktion": aktion,
                    "claude_action_hint": info.get("claude_action") or "",
                    "extrahierte_felder": info.get("fields") or {},
                    "naechster_aufruf_hinweis": _ROUTING_NAECHSTER_AUFRUF.get(
                        aktion, ""
                    ),
                }
            dokumente.append(doc_entry)

        if routing_modus:
            anleitung = (
                "Pro Dokument im Batch: schaue auf `routing.aktion` und nutze "
                "`dokument_aktion_ausfuehren(dokument_id, aktion, args)`. "
                "Fuer `profil_extraktion` weiter wie bisher (Profildaten "
                "ziehen + extraktion_ergebnis_speichern + extraktion_anwenden). "
                "Fuer `noop_korrespondenz_abschliessen` reicht das Tool "
                "`dokumente_korrespondenz_abschliessen()` am Ende des Batches. "
                "Danach: dokumente_batch_analysieren(batch_nr="
                + str(batch_nr + 1)
                + ", routing_modus=True) fuer den naechsten Batch."
            )
        else:
            anleitung = (
                "Analysiere die Dokumente und extrahiere Profildaten. "
                "Speichere mit extraktion_ergebnis_speichern(). "
                "Dann extraktion_anwenden(). "
                "Danach: dokumente_batch_analysieren(batch_nr="
                + str(batch_nr + 1)
                + ") für den nächsten Batch."
            )

        result = {
            "status": "ok",
            "extraction_id": eid,
            "batch_nr": batch_nr,
            "batches_gesamt": len(batches),
            "dokumente_in_batch": len(dokumente),
            "duplikate_uebersprungen": len(dup_ids),
            "dokumente_gekuerzt": truncations,
            "routing_modus": routing_modus,
            "dokumente": dokumente,
            "anleitung": anleitung,
        }

        if profil_mitsenden:
            # Skills auf max 100 limitieren — bei sehr grossen Profilen
            # macht der String sonst die Response auch fett.
            skills_all = [s.get("name") for s in profile.get("skills", []) if s.get("name")]
            result["aktuelles_profil"] = {
                "name": profile.get("name"),
                "summary": (profile.get("summary") or "")[:500],
                "positionen_anzahl": len(profile.get("positions", [])),
                "skills": skills_all[:100],
                "skills_anzahl": len(skills_all),
            }
        else:
            result["profil_hinweis"] = "Profil wurde im ersten Batch gesendet. Nutze das gleiche Profil als Referenz."

        logger.info(
            "dokumente_batch_analysieren: batch %d/%d, %d Docs, %d gekuerzt, %.2fs",
            batch_nr, len(batches), len(dokumente), truncations, _t.time() - _t0,
        )
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

    # === Dokument-Write-Tools (#447) =======================================
    # Schreibzugriff auf Dokumente: Entverknuepfen, Loeschen, Status setzen.
    # Bisher konnte Claude diese Operationen nur per direktem SQL ausfuehren.

    # v1.7.0-beta.78 (#658, E15): Whitelist um die Stati erweitert, die der
    # Auto-Pfad tatsaechlich vergibt. Vorher fehlten `basis_analysiert`,
    # `analysiert`, `analysiert_leer`, `duplikat`, `verworfen` — dadurch
    # konnte `dokument_status_setzen` z.B. ein Doku nicht manuell auf
    # `basis_analysiert` zuruecksetzen.
    _DOC_STATUS_VALUES = {
        "nicht_extrahiert", "gestartet", "extrahiert",
        "basis_analysiert", "analysiert", "analysiert_leer",
        "angewendet", "duplikat", "verworfen",
    }

    # v1.7.0-beta.78 (#658, E15): Korrespondenz-Typen, die keine Profildaten
    # liefern und deshalb nie ueber extraktion_anwenden() gehen. Wenn sie
    # nach Basis-Extraktion oder Tiefenanalyse keinen weiteren Schritt
    # brauchen, sollen sie via dokumente_korrespondenz_abschliessen()
    # auf `angewendet` wandern.
    _KORRESPONDENZ_DOC_TYPES = {
        "sonstiges", "recruiter_anfrage", "angebot",
        "absage", "einladung", "eingangsbestaetigung",
        "interview_bestaetigung", "interview_einladung",
        "gespraechs_feedback", "projekt_update",
        "vermittler_korrespondenz",
    }

    @mcp.tool()
    def dokument_entverknuepfen(dokument_id: str) -> dict:
        """Entfernt die Verknuepfung eines Dokuments zu einer Bewerbung (#447).

        Nutze dies, wenn eine automatische oder manuelle Zuordnung falsch ist
        und das Dokument wieder 'unverknuepft' erscheinen soll. Das Dokument
        selbst bleibt erhalten — nur die Verknuepfung wird geloest.

        Args:
            dokument_id: ID des Dokuments
        """
        profile_id = db.get_active_profile_id()
        doc = db.get_document(dokument_id, profile_id=profile_id)
        if not doc:
            return {"fehler": "Dokument nicht gefunden."}
        if not doc.get("linked_application_id"):
            return {
                "status": "nicht_verknuepft",
                "hinweis": "Das Dokument war bereits keiner Bewerbung zugeordnet.",
            }
        changed = db.relink_document(dokument_id, None, profile_id=profile_id)
        if not changed:
            return {"fehler": "Verknuepfung konnte nicht entfernt werden."}
        return {
            "status": "entverknuepft",
            "dokument_id": dokument_id,
            "dokument": doc.get("filename", ""),
            "nachricht": (
                f"Dokument '{doc.get('filename', '')}' ist nicht mehr mit einer "
                "Bewerbung verknuepft."
            ),
        }

    @mcp.tool()
    def dokument_loeschen(dokument_id: str, bestaetigung: bool = False) -> dict:
        """Loescht ein Dokument komplett — DB-Eintrag und physische Datei (#447).

        ACHTUNG: Nicht rueckgaengig zu machen. Beim ersten Aufruf ohne
        Bestaetigung wird nur eine Rueckfrage zurueckgegeben.

        Args:
            dokument_id: ID des Dokuments
            bestaetigung: Muss True sein um tatsaechlich zu loeschen
        """
        profile_id = db.get_active_profile_id()
        doc = db.get_document(dokument_id, profile_id=profile_id)
        if not doc:
            return {"fehler": "Dokument nicht gefunden."}
        if not bestaetigung:
            return {
                "status": "bestaetigung_erforderlich",
                "dokument_id": dokument_id,
                "dokument": doc.get("filename", ""),
                "hinweis": "Setze bestaetigung=True um Dokument und Datei unwiderruflich zu loeschen.",
            }
        deleted = db.delete_document(dokument_id, profile_id=profile_id)
        if not deleted:
            return {"fehler": "Dokument konnte nicht geloescht werden."}
        return {
            "status": "geloescht",
            "dokument_id": dokument_id,
            "nachricht": f"Dokument '{doc.get('filename', '')}' wurde geloescht.",
        }

    @mcp.tool()
    def dokument_typen_anzeigen(mit_verteilung: bool = True) -> dict:
        """Listet alle bekannten Dokumenten-Typen + Aktion-Vorschlag (#655 E14).

        Hilft Claude und User beim Discovery:
        - Welche Typen kennt PBP?
        - Welche Aktion sollte pro Typ ausgefuehrt werden?
        - Welche haben einen Per-Typ-Extraktor (strukturierte Felder)?
        - Wie sieht die Verteilung in der aktuellen DB aus?

        Args:
            mit_verteilung: True (Standard) = pro Typ die Anzahl der
                Dokumente in der DB mitliefern. False = nur die Typ-Definitionen.

        Liefert: {typen: [...], gesamt_dokumente, hinweis}.
        """
        from ..services.document_handlers import list_known_types
        types_info = list_known_types()

        if mit_verteilung:
            conn = db.connect()
            pid = db.get_active_profile_id()
            try:
                rows = conn.execute(
                    "SELECT doc_type, COUNT(*) AS n FROM documents "
                    "WHERE (profile_id=? OR profile_id IS NULL) "
                    "GROUP BY doc_type",
                    (pid,)
                ).fetchall()
                counts = {r["doc_type"]: r["n"] for r in rows}
                for t in types_info:
                    t["dokumente_in_db"] = counts.get(t["typ"], 0)
                # Unbekannte Typen die nicht in KNOWN_TYPES sind?
                bekannt = {t["typ"] for t in types_info}
                unbekannte = [
                    {"typ": dt, "dokumente_in_db": cnt}
                    for dt, cnt in counts.items() if dt not in bekannt and dt
                ]
                gesamt = sum(counts.values())
            except Exception as exc:
                logger.warning("dokument_typen_anzeigen Verteilung: %s", exc)
                unbekannte = []
                gesamt = 0
        else:
            unbekannte = []
            gesamt = None

        result = {
            "typen": types_info,
            "anzahl_typen": len(types_info),
            "hinweis": (
                "Nutze update_document_type(doc_id, typ) um Doku-Typ "
                "manuell zu setzen. Per-Typ-Handler-Aktionen siehe "
                "'claude_action'-Spalte."
            ),
        }
        if mit_verteilung:
            result["gesamt_dokumente"] = gesamt
            if unbekannte:
                result["unbekannte_typen_in_db"] = unbekannte
                result["unbekannte_typen_hinweis"] = (
                    "Diese doc_type-Werte sind in der DB, aber nicht in "
                    "KNOWN_TYPES dokumentiert — pruefen ob Typ obsolet ist "
                    "oder Handler-Eintrag ergaenzt werden sollte."
                )
        return result

    @mcp.tool()
    def dokument_status_setzen(dokument_id: str, status: str) -> dict:
        """Setzt den Extraktions-Status eines Dokuments manuell (#447).

        Nutze dies z.B. nachdem du eine tiefere Analyse abgeschlossen hast und
        das Dokument als 'angewendet' markieren willst, ohne `extraktion_anwenden`
        noch einmal durchlaufen zu lassen.

        Args:
            dokument_id: ID des Dokuments
            status: nicht_extrahiert, gestartet, extrahiert,
                basis_analysiert, analysiert, analysiert_leer,
                angewendet, duplikat, verworfen
        """
        if status not in _DOC_STATUS_VALUES:
            return {
                "fehler": f"Ungueltiger Status '{status}'.",
                "erlaubte_status": sorted(_DOC_STATUS_VALUES),
            }
        profile_id = db.get_active_profile_id()
        doc = db.get_document(dokument_id, profile_id=profile_id)
        if not doc:
            return {"fehler": "Dokument nicht gefunden."}
        db.update_document_extraction_status(dokument_id, status)
        return {
            "status": "aktualisiert",
            "dokument_id": dokument_id,
            "extraction_status": status,
            "nachricht": f"Dokument '{doc.get('filename', '')}' -> {status}.",
        }

    @mcp.tool()
    def dokumente_korrespondenz_abschliessen(
        dry_run: bool = True,
        zusaetzliche_doc_types: list = None,
    ) -> dict:
        """Schliesst Korrespondenz-Dokumente ab — `basis_analysiert`/`analysiert` -> `angewendet` (#658, E15).

        Hintergrund: Dokumente ohne Profildaten (Absagen, Einladungen,
        Recruiter-Anfragen, Benachrichtigungen) durchlaufen nie
        `extraktion_anwenden()`. Sie bleiben deshalb dauerhaft im
        `basis_analysiert`-Bucket haengen und tauchen bei jedem
        `analyse_plan_erstellen()`-Lauf erneut auf. Dieses Tool raeumt
        sie in einem Rutsch ab — Status wird auf `angewendet` gehoben,
        damit sie aus dem Plan verschwinden. Physische Dateien bleiben
        unberuehrt; Verknuepfungen zu Bewerbungen bleiben erhalten.

        Sicherheits-Hinweise:
        - **DB-only**: aendert nur `extraction_status` + `last_extraction_at`.
          Es werden keine Dateien gelesen, geschrieben oder geloescht.
        - **Konservativ**: nur Korrespondenz-Typen (siehe
          `_KORRESPONDENZ_DOC_TYPES`). Lebenslaeufe, Anschreiben,
          Projektlisten u.a. werden NIE durch dieses Tool angefasst —
          die brauchen `extraktion_anwenden()`.
        - **dry_run=True (Default)**: zeigt nur die Treffer, schreibt nichts.
          Erst mit `dry_run=False` wird umgesetzt.

        Args:
            dry_run: True (Default) = nur Vorschau; False = tatsaechlich umsetzen.
            zusaetzliche_doc_types: Optional Liste weiterer doc_type-Werte,
                die zusaetzlich zur Default-Korrespondenz-Whitelist als
                "abschliessbar" zaehlen sollen (z.B. ein neuer interner Typ).
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein aktives Profil."}

        types = set(_KORRESPONDENZ_DOC_TYPES)
        if zusaetzliche_doc_types:
            for t in zusaetzliche_doc_types:
                if isinstance(t, str) and t.strip():
                    types.add(t.strip())

        conn = db.connect()
        pid = profile["id"]
        placeholders = ",".join("?" * len(types))
        rows = conn.execute(
            "SELECT id, filename, doc_type, extraction_status, "
            "COALESCE(linked_application_id, 0) AS aid, "
            "COALESCE(created_at,'') AS created_at "
            "FROM documents "
            "WHERE profile_id=? "
            "AND extraction_status IN ('basis_analysiert','analysiert','analysiert_leer') "
            f"AND doc_type IN ({placeholders}) "
            "ORDER BY created_at DESC",
            (pid, *sorted(types)),
        ).fetchall()
        kandidaten = [dict(r) for r in rows]

        result = {
            "status": "vorschau" if dry_run else "abgeschlossen",
            "dry_run": dry_run,
            "kandidaten_anzahl": len(kandidaten),
            "kandidaten": [
                {
                    "id": k["id"],
                    "filename": k["filename"],
                    "doc_type": k["doc_type"],
                    "extraction_status_vorher": k["extraction_status"],
                    "linked_application_id": k["aid"] or None,
                }
                for k in kandidaten
            ],
            "hinweis": (
                "DB-only. Physische Dateien bleiben unberuehrt. "
                "Verknuepfungen zu Bewerbungen bleiben erhalten."
            ),
        }

        if dry_run or not kandidaten:
            if not kandidaten:
                # Bei "nichts zu tun": auch im Live-Modus konsistente
                # umgesetzt_anzahl=0 setzen, damit Caller einheitlich
                # auswerten koennen.
                if not dry_run:
                    result["status"] = "abgeschlossen"
                    result["umgesetzt_anzahl"] = 0
                result["nachricht"] = (
                    "Keine Korrespondenz-Dokumente im "
                    "basis_analysiert/analysiert-Bucket gefunden — "
                    "nichts zu tun."
                )
            else:
                result["nachricht"] = (
                    f"{len(kandidaten)} Korrespondenz-Dokument(e) wuerden "
                    "auf `angewendet` gesetzt. Setze `dry_run=False` "
                    "um umzusetzen."
                )
            return result

        # Tatsaechlicher Schreib-Pfad: ueber bestehenden DB-Helfer,
        # nicht roh in conn.execute() — so bleibt last_extraction_at
        # konsistent gepflegt.
        umgesetzt = 0
        for k in kandidaten:
            try:
                db.update_document_extraction_status(k["id"], "angewendet")
                umgesetzt += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Korrespondenz-Abschluss fehlgeschlagen fuer %s: %s",
                    k["id"], exc,
                )

        logger.info(
            "dokumente_korrespondenz_abschliessen: %d/%d auf `angewendet` gesetzt",
            umgesetzt, len(kandidaten),
        )
        result["umgesetzt_anzahl"] = umgesetzt
        result["nachricht"] = (
            f"{umgesetzt} von {len(kandidaten)} Korrespondenz-"
            "Dokument(en) auf `angewendet` gesetzt. Dateien unberuehrt."
        )
        return result

    # === Dokument-Lifecycle (v44, #657, E16) ===========================
    # archivieren / reaktivieren / bulk_archivieren operieren NUR auf der
    # DB-Spalte `lifecycle`. Physische Dateien bleiben unberuehrt — analog
    # zur file-vs-DB-Regel bei Duplikat-Cleanup.

    @mcp.tool()
    def dokument_archivieren(dokument_id: str, grund: str = "") -> dict:
        """Archiviert ein Dokument — weiche Markierung, kein Loeschen (#657 E16).

        Nutze dies, wenn ein Dokument aus den Standard-Analyse-Ansichten
        ausgeblendet werden soll, aber erhalten bleiben muss (z.B. reine
        Benachrichtigungs-Mails, erledigte Korrespondenz, Rauschen).

        Sicherheits-Hinweis: **DB-only**. Die physische Datei auf der
        Platte wird NIE angefasst. Reversibel ueber `dokument_reaktivieren`.

        Args:
            dokument_id: ID des Dokuments
            grund: Optionaler Kurz-Hinweis warum archiviert (wird ins
                Tool-Result zurueckgegeben, nicht in der DB persistiert).
        """
        profile_id = db.get_active_profile_id()
        doc = db.get_document(dokument_id, profile_id=profile_id)
        if not doc:
            return {"fehler": "Dokument nicht gefunden."}
        if doc.get("lifecycle") == "archiviert":
            return {
                "status": "bereits_archiviert",
                "dokument_id": dokument_id,
                "filename": doc.get("filename", ""),
                "hinweis": "Das Dokument war bereits archiviert.",
            }
        changed = db.update_document_lifecycle(
            dokument_id, "archiviert", profile_id=profile_id
        )
        if not changed:
            return {"fehler": "Archivierung konnte nicht angewendet werden."}
        return {
            "status": "archiviert",
            "dokument_id": dokument_id,
            "filename": doc.get("filename", ""),
            "lifecycle_vorher": doc.get("lifecycle", "aktiv"),
            "lifecycle_nachher": "archiviert",
            "grund": grund or None,
            "hinweis": (
                "Nur DB-Flag gesetzt. Physische Datei unberuehrt. "
                "Reaktivierbar mit `dokument_reaktivieren`."
            ),
        }

    @mcp.tool()
    def dokument_reaktivieren(dokument_id: str) -> dict:
        """Setzt ein archiviertes/veraltetes Dokument wieder auf `aktiv` (#657 E16).

        Gegenstueck zu `dokument_archivieren` und zum Auto-Veralten-Hook.
        Ist idempotent: wenn das Doku bereits `aktiv` ist, wird das gemeldet.

        Args:
            dokument_id: ID des Dokuments
        """
        profile_id = db.get_active_profile_id()
        doc = db.get_document(dokument_id, profile_id=profile_id)
        if not doc:
            return {"fehler": "Dokument nicht gefunden."}
        if doc.get("lifecycle") == "aktiv":
            return {
                "status": "bereits_aktiv",
                "dokument_id": dokument_id,
                "filename": doc.get("filename", ""),
                "hinweis": "Das Dokument war bereits aktiv.",
            }
        changed = db.update_document_lifecycle(
            dokument_id, "aktiv", profile_id=profile_id
        )
        if not changed:
            return {"fehler": "Reaktivierung konnte nicht angewendet werden."}
        return {
            "status": "aktiv",
            "dokument_id": dokument_id,
            "filename": doc.get("filename", ""),
            "lifecycle_vorher": doc.get("lifecycle", "?"),
            "lifecycle_nachher": "aktiv",
        }

    @mcp.tool()
    def dokumente_bulk_archivieren(
        filter_doc_type: list = None,
        filter_quelle: list = None,
        filter_extraction_status: list = None,
        dry_run: bool = True,
        max_treffer: int = 200,
    ) -> dict:
        """Archiviert mehrere Dokumente in einem Rutsch mit Filter (#657 E16).

        Sicherheits-Hinweise:
        - **DB-only**: aendert nur `lifecycle`. Keine Dateien werden angefasst.
        - **dry_run=True (Default)**: zeigt nur die Treffer, schreibt nichts.
        - **Hard-Cap `max_treffer`**: schuetzt vor versehentlich riesigen
          Operationen. Default 200 — wenn mehr in Frage kaemen, wird die
          Liste begrenzt und ein Hinweis ausgegeben.
        - Nur Dokumente mit aktuellem `lifecycle='aktiv'` werden archiviert.
          Bereits archivierte/veraltete bleiben unberuehrt.

        Args:
            filter_doc_type: Liste von doc_type-Werten (z.B. ["sonstiges",
                "absage"]). Default: kein Filter.
            filter_quelle: NICHT IMPLEMENTIERT in Phase 2 (Stub fuer spaeter,
                wenn `documents.source` existiert). Aktuell ignoriert.
            filter_extraction_status: Liste von extraction_status (z.B.
                ["angewendet"]). Default: kein Filter.
            dry_run: True (Default) = nur Vorschau, schreibt nichts.
            max_treffer: Maximale Anzahl Dokumente pro Aufruf (Hard-Cap).
        """
        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein aktives Profil."}
        max_treffer = max(1, min(int(max_treffer or 200), 2000))

        conn = db.connect()
        pid = profile["id"]
        clauses = ["profile_id=?", "lifecycle='aktiv'"]
        params: list = [pid]
        if filter_doc_type:
            placeholders = ",".join("?" * len(filter_doc_type))
            clauses.append(f"doc_type IN ({placeholders})")
            params.extend(filter_doc_type)
        if filter_extraction_status:
            placeholders = ",".join("?" * len(filter_extraction_status))
            clauses.append(f"extraction_status IN ({placeholders})")
            params.extend(filter_extraction_status)
        where = " AND ".join(clauses)

        rows = conn.execute(
            f"SELECT id, filename, doc_type, extraction_status, "
            f"COALESCE(linked_application_id,0) AS aid "
            f"FROM documents WHERE {where} "
            f"ORDER BY created_at DESC LIMIT ?",
            (*params, max_treffer + 1),
        ).fetchall()
        truncated = len(rows) > max_treffer
        kandidaten = [dict(r) for r in rows[:max_treffer]]

        result = {
            "status": "vorschau" if dry_run else "abgeschlossen",
            "dry_run": dry_run,
            "kandidaten_anzahl": len(kandidaten),
            "max_treffer": max_treffer,
            "max_treffer_erreicht": truncated,
            "filter_quelle_ignoriert": bool(filter_quelle),
            "hinweis": (
                "DB-only. Physische Dateien bleiben unberuehrt. "
                "Reaktivierbar mit `dokument_reaktivieren`."
            ),
        }
        if not dry_run:
            result["umgesetzt_anzahl"] = 0

        if not kandidaten:
            result["nachricht"] = "Keine passenden Dokumente gefunden."
            return result

        if dry_run:
            result["kandidaten"] = [
                {
                    "id": k["id"],
                    "filename": k["filename"],
                    "doc_type": k["doc_type"],
                    "extraction_status": k["extraction_status"],
                    "linked_application_id": k["aid"] or None,
                }
                for k in kandidaten
            ]
            result["nachricht"] = (
                f"{len(kandidaten)} Dokument(e) wuerden archiviert. "
                "Setze `dry_run=False` um umzusetzen."
            )
            if truncated:
                result["nachricht"] += (
                    f" (Hard-Cap {max_treffer} erreicht — weitere Treffer "
                    "wurden abgeschnitten. Erhoehe max_treffer oder filtere enger.)"
                )
            return result

        # Live-Apply
        umgesetzt = 0
        for k in kandidaten:
            try:
                if db.update_document_lifecycle(
                    k["id"], "archiviert", profile_id=pid
                ):
                    umgesetzt += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Bulk-Archivieren fehlgeschlagen fuer %s: %s",
                    k["id"], exc,
                )
        logger.info(
            "dokumente_bulk_archivieren: %d/%d archiviert", umgesetzt, len(kandidaten)
        )
        result["umgesetzt_anzahl"] = umgesetzt
        result["nachricht"] = (
            f"{umgesetzt} von {len(kandidaten)} Dokument(en) auf "
            "`lifecycle=archiviert` gesetzt. Dateien unberuehrt."
        )
        if truncated:
            result["nachricht"] += (
                f" (Hard-Cap {max_treffer} erreicht — Lauf erneut "
                "ausfuehren, falls weitere Treffer bestehen.)"
            )
        return result

    # === Dokument-Routing (#643, E11, beta.80) =========================
    # Phase 3 verbindet das Per-Typ-Handler-System (E14, beta.77) mit
    # `/dokumente_verarbeiten`. Statt "extrahiere Profildaten" bekommt
    # Claude jetzt typspezifische Aktions-Vorschlaege:
    #   lebenslauf      -> Profil-Extraktion
    #   absage          -> Bewerbung-Status setzen
    #   einladung       -> Termin anlegen
    #   recruiter_anfrage -> Anfrage erfassen, Antwort entwerfen
    #   eingangsbestaetigung -> Bewerbung-Status setzen
    #   sonstiges/noise -> Korrespondenz abschliessen oder archivieren

    # Mapping doc_type -> Aktions-Code, der spaeter via
    # `dokument_aktion_ausfuehren` umgesetzt wird. Bewusst klein gehalten —
    # neue Typen ergaenzen wir in document_handlers.KNOWN_TYPES.
    _DOC_ROUTING_ACTIONS = {
        "lebenslauf": "profil_extraktion",
        "anschreiben": "noop_korrespondenz_abschliessen",
        "projektliste": "profil_extraktion",
        "zeugnis": "profil_extraktion",
        "arbeitszeugnis": "profil_extraktion",
        "ausbildungszeugnis": "profil_extraktion",
        "zertifikat": "profil_extraktion",
        "absage": "bewerbung_status_setzen",
        "einladung": "termin_anlegen",
        "interview_einladung": "termin_anlegen",
        "interview_bestaetigung": "termin_anlegen",
        "eingangsbestaetigung": "eingangsbestaetigung",
        "recruiter_anfrage": "bewerbung_erfassen",
        "vermittler_korrespondenz": "noop_korrespondenz_abschliessen",
        "projekt_update": "noop_korrespondenz_abschliessen",
        "gespraechs_feedback": "noop_korrespondenz_abschliessen",
        "angebot": "noop_korrespondenz_abschliessen",
        "sonstiges": "noop_korrespondenz_abschliessen",
    }

    # Per-Aktion: kurzer Hinweis fuer den naechsten konkreten MCP-Tool-Call.
    _ROUTING_NAECHSTER_AUFRUF = {
        "profil_extraktion": (
            "Nutze `dokumente_batch_analysieren(routing_modus=False)` oder "
            "`extraktion_starten`, danach `extraktion_anwenden`."
        ),
        "termin_anlegen": (
            "Pro Doku: `dokument_aktion_ausfuehren(dokument_id, "
            "'termin_anlegen', args={datum,uhrzeit,plattform,bewerbung_id})`."
        ),
        "bewerbung_status_setzen": (
            "Pro Doku: `dokument_aktion_ausfuehren(dokument_id, "
            "'bewerbung_status_setzen', args={bewerbung_id, neuer_status, ablehnungsgrund?})`."
        ),
        "eingangsbestaetigung": (
            "Pro Doku: `dokument_aktion_ausfuehren(dokument_id, "
            "'eingangsbestaetigung', args={bewerbung_id})`."
        ),
        "bewerbung_erfassen": (
            "Pro Doku: `dokument_aktion_ausfuehren(dokument_id, "
            "'bewerbung_erfassen', args={firma, titel, url?})`."
        ),
        "noop_korrespondenz_abschliessen": (
            "Sammelweise: `dokumente_korrespondenz_abschliessen(dry_run=False)`."
        ),
    }

    @mcp.tool()
    def dokumente_routing_plan_erstellen(archiv: bool = False) -> dict:
        """Erstellt einen Routing-Plan: was sollte mit jedem Dokument passieren? (#643 E11)

        Wertet pro noch-nicht-vollstaendig-verarbeitetes Doku den
        `doc_type` aus und liefert die passende PBP-Aktion (Profil-
        Extraktion, Termin-Anlage, Status-Wechsel, ...). Aufbauend auf
        `services/document_handlers.handle_doc()` aus E14 (beta.77).

        Nutzung: Claude ruft das Tool VOR `dokumente_batch_analysieren`
        (im Routing-Modus) auf, um zu wissen welche Aktionen pro Typ
        anstehen. Pro Aktion gruppiert + Vorschlaege fuer den naechsten
        Tool-Aufruf.

        Args:
            archiv: False (Default) — nur lifecycle=aktiv. True bezieht
                archivierte/veraltete mit ein.
        """
        from ..services.document_handlers import handle_doc

        profile = db.get_profile()
        if not profile:
            return {"fehler": "Kein aktives Profil."}

        conn = db.connect()
        pid = profile["id"]
        lifecycle_clause = "" if archiv else " AND lifecycle='aktiv'"
        rows = conn.execute(
            "SELECT id, filename, doc_type, extraction_status, "
            "extracted_text, lifecycle, "
            "COALESCE(linked_application_id,0) AS aid "
            "FROM documents "
            "WHERE profile_id=? "
            "AND extraction_status IN "
            "  ('nicht_extrahiert','basis_analysiert','analysiert','analysiert_leer')"
            + lifecycle_clause
            + " ORDER BY created_at DESC LIMIT 200",
            (pid,)
        ).fetchall()

        gruppen: dict[str, list[dict]] = {}
        for r in rows:
            doc = dict(r)
            info = handle_doc(doc)
            aktion = _DOC_ROUTING_ACTIONS.get(
                doc["doc_type"] or "sonstiges",
                "noop_korrespondenz_abschliessen",
            )
            eintrag = {
                "id": doc["id"],
                "filename": doc["filename"],
                "doc_type": doc["doc_type"],
                "extraction_status": doc["extraction_status"],
                "lifecycle": doc["lifecycle"],
                "linked_application_id": doc["aid"] or None,
                "claude_action": info["claude_action"],
                "extrahierte_felder": info.get("fields") or {},
            }
            gruppen.setdefault(aktion, []).append(eintrag)

        gruppen_summary = []
        for aktion, items in sorted(gruppen.items()):
            gruppen_summary.append({
                "aktion": aktion,
                "anzahl": len(items),
                "naechster_aufruf_hinweis": _ROUTING_NAECHSTER_AUFRUF.get(
                    aktion, "Pruefe das Doku einzeln und entscheide."
                ),
                "dokumente": items,
            })

        return {
            "status": "ok",
            "dokumente_gesamt": len(rows),
            "aktionen_anzahl": len(gruppen),
            "aktionen": gruppen_summary,
            "anleitung": (
                "Pro Aktions-Gruppe: rufe `dokument_aktion_ausfuehren(dokument_id, "
                "aktion, args)` fuer jedes Doku auf — oder nutze "
                "`dokumente_batch_analysieren(routing_modus=True)` fuer den "
                "kombinierten Flow."
            ),
        }

    @mcp.tool()
    def dokument_aktion_ausfuehren(
        dokument_id: str,
        aktion: str,
        args: dict = None,
    ) -> dict:
        """Fuehrt die fuer ein Dokument vorgeschlagene Aktion aus (#643 E11).

        Wrapper um bestehende MCP-Tools — Claude muss nicht selber wissen
        welches Tool fuer welche Aktion zustaendig ist. Liefert das
        konkrete Ergebnis des delegierten Tools zurueck und setzt am Ende
        `extraction_status='angewendet'` fuer das Dokument.

        Unterstuetzte Aktionen:
        - `profil_extraktion` — Hinweis: hierfuer den klassischen Pfad
          extraktion_starten/extraktion_anwenden nutzen. Dieses Tool liefert
          dafuer nur eine Anleitung zurueck (keine implizite Anwendung,
          weil Profil-Apply einen User-Bestaetigungsschritt braucht).
        - `termin_anlegen` — args: {bewerbung_id, datum, uhrzeit?,
          plattform?, link?, ort?}. Delegiert an meeting_hinzufuegen().
        - `bewerbung_status_setzen` — args: {bewerbung_id, neuer_status,
          ablehnungsgrund?, notizen?}. Delegiert an bewerbung_status_aendern().
        - `eingangsbestaetigung` — args: {bewerbung_id, notizen?}.
          Setzt Status auf `eingangsbestaetigung`.
        - `bewerbung_erfassen` — args: {firma, titel, url?, status?}.
          Delegiert an bewerbung_erstellen().
        - `noop_korrespondenz_abschliessen` — keine externe Aktion, setzt
          nur extraction_status='angewendet'. Identisch zur Wirkung von
          `dokumente_korrespondenz_abschliessen` fuer dieses eine Doku.

        Args:
            dokument_id: ID des betreffenden Dokuments.
            aktion: einer der oben gelisteten Aktions-Codes.
            args: Aktions-spezifische Argumente (siehe oben).
        """
        args = args or {}
        profile_id = db.get_active_profile_id()
        doc = db.get_document(dokument_id, profile_id=profile_id)
        if not doc:
            return {"fehler": "Dokument nicht gefunden."}

        delegiert = None
        post_status = "angewendet"

        if aktion == "profil_extraktion":
            return {
                "status": "anleitung",
                "dokument_id": dokument_id,
                "aktion": aktion,
                "anleitung": (
                    "Profil-Extraktion: nutze `extraktion_starten(["
                    f"\"{dokument_id}\"])`, dann `extraktion_ergebnis_speichern` "
                    "und am Ende `extraktion_anwenden`. Diese setzt am "
                    "Ende selbst `angewendet` und braucht User-"
                    "Bestaetigung bei Konflikten."
                ),
            }

        # Sub-Tool-Loader: registriert die bewerbungen-Tools in einem
        # leichten Fake-MCP, sodass wir die echten Tool-Funktionen
        # (inklusive aller Lifecycle-Hooks wie Auto-Veralten aus #657)
        # aufrufen koennen, statt DB-Logik zu duplizieren.
        def _load_bewerbungen_tools() -> dict:
            from .bewerbungen import register as _reg_bw

            class _SubMCP:
                def __init__(self):
                    self.tools: dict = {}

                def tool(self):
                    def deco(fn):
                        self.tools[fn.__name__] = fn
                        return fn
                    return deco

            sub = _SubMCP()
            _reg_bw(sub, db, logger)
            return sub.tools

        if aktion == "termin_anlegen":
            try:
                tools = _load_bewerbungen_tools()
            except Exception as exc:  # noqa: BLE001
                return {"fehler": f"meeting_hinzufuegen nicht ladbar: {exc}"}
            fn = tools.get("meeting_hinzufuegen")
            if not fn:
                return {"fehler": "meeting_hinzufuegen nicht registriert."}
            datum_raw = args.get("datum") or ""
            uhrzeit_raw = args.get("uhrzeit") or ""
            if datum_raw and uhrzeit_raw and "T" not in datum_raw:
                datum_combined = f"{datum_raw}T{uhrzeit_raw}"
            else:
                datum_combined = datum_raw
            delegiert = fn(
                bewerbung_id=args.get("bewerbung_id"),
                datum=datum_combined,
                typ=args.get("typ") or "interview",
                platform=args.get("plattform") or args.get("platform") or "",
                ort=args.get("ort") or "",
                titel=args.get("titel") or "",
                notizen=args.get("notizen") or args.get("link") or "",
            )

        elif aktion == "bewerbung_status_setzen":
            try:
                tools = _load_bewerbungen_tools()
            except Exception as exc:  # noqa: BLE001
                return {"fehler": f"bewerbung_status_aendern nicht ladbar: {exc}"}
            fn = tools.get("bewerbung_status_aendern")
            if not fn:
                return {"fehler": "bewerbung_status_aendern nicht registriert."}
            delegiert = fn(
                bewerbung_id=args.get("bewerbung_id"),
                neuer_status=args.get("neuer_status"),
                notizen=args.get("notizen") or "",
                ablehnungsgrund=args.get("ablehnungsgrund") or "",
            )

        elif aktion == "eingangsbestaetigung":
            try:
                tools = _load_bewerbungen_tools()
            except Exception as exc:  # noqa: BLE001
                return {"fehler": f"bewerbung_status_aendern nicht ladbar: {exc}"}
            fn = tools.get("bewerbung_status_aendern")
            if not fn:
                return {"fehler": "bewerbung_status_aendern nicht registriert."}
            delegiert = fn(
                bewerbung_id=args.get("bewerbung_id"),
                neuer_status="eingangsbestaetigung",
                notizen=args.get("notizen") or "",
            )

        elif aktion == "bewerbung_erfassen":
            try:
                tools = _load_bewerbungen_tools()
            except Exception as exc:  # noqa: BLE001
                return {"fehler": f"bewerbung_erstellen nicht ladbar: {exc}"}
            fn = tools.get("bewerbung_erstellen")
            if not fn:
                return {"fehler": "bewerbung_erstellen nicht registriert."}
            delegiert = fn(
                title=args.get("titel") or args.get("title") or "",
                company=args.get("firma") or args.get("company") or "",
                url=args.get("url") or "",
                status=args.get("status") or "anfrage",
                notes=args.get("notes") or args.get("notizen") or "",
            )

        elif aktion == "noop_korrespondenz_abschliessen":
            delegiert = {"status": "korrespondenz_abgeschlossen"}

        else:
            return {
                "fehler": f"Unbekannte Aktion '{aktion}'.",
                "bekannte_aktionen": sorted(set(_DOC_ROUTING_ACTIONS.values())),
            }

        # Status auf `angewendet` heben — Doku gilt damit als verarbeitet
        # und verschwindet aus analyse_plan_erstellen/dokumente_batch_analysieren.
        try:
            db.update_document_extraction_status(dokument_id, post_status)
        except Exception as exc:
            logger.warning(
                "post-action status update fuer %s fehlgeschlagen: %s",
                dokument_id, exc,
            )

        return {
            "status": "umgesetzt",
            "dokument_id": dokument_id,
            "aktion": aktion,
            "delegiert_an_tool_result": delegiert,
            "extraction_status_nachher": post_status,
            "hinweis": (
                "Dokument wurde verarbeitet und auf extraction_status="
                "`angewendet` gesetzt. Bei Bedarf reaktivierbar via "
                "`dokument_status_setzen`."
            ),
        }
