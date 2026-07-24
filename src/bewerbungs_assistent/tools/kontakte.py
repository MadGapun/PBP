"""Kontaktdatenbank — MCP-Tools (v1.7.0 #563).

Personen als zentrale Entitaet mit Historie ueber Bewerbungen, Stellen,
Meetings und Mails. Rollen als JSON-Array Tags.
"""


def register(mcp, db, logger):
    """Registriert Kontakt-Tools."""

    @mcp.tool()
    def kontakt_anlegen(
        name: str,
        email: str = "",
        firma: str = "",
        position: str = "",
        telefon: str = "",
        linkedin_url: str = "",
        rollen: list[str] = None,
        notizen: str = "",
    ) -> dict:
        """Legt einen neuen Kontakt in der Kontaktdatenbank an (#563).

        Rollen sind frei waehlbare Tags — Beispiele:
        - 'recruiter' — externe(r) Personalvermittler(in)
        - 'headhunter' — proaktiv anschreibende(r) Recruiter(in)
        - 'hiring_manager' — entscheidende Person bei der Stelle
        - 'interviewer' — fuehrt Gespraech
        - 'hr' — Personalabteilung
        - 'kollege' — bekannte Person aus eigenem Netzwerk
        - 'mentor' — Mentor / Coach
        - 'sonstiges'

        Args:
            name: Vollstaendiger Name (Pflicht).
            email: E-Mail-Adresse.
            firma: Firma der Person.
            position: Titel/Rolle bei der Firma.
            telefon: Telefonnummer.
            linkedin_url: LinkedIn-Profil-URL.
            rollen: Liste von Rollen (siehe oben). Default: [].
            notizen: Freitext.
        """
        if not name or not name.strip():
            return {"fehler": "name ist Pflicht."}
        try:
            cid = db.add_contact({
                "full_name": name.strip(),
                "email": email or None,
                "phone": telefon or None,
                "linkedin_url": linkedin_url or None,
                "company": firma or None,
                "position": position or None,
                "tags": rollen or [],
                "notes": notizen or None,
            })
        except ValueError as e:
            return {"fehler": str(e)}
        return {
            "status": "angelegt",
            "kontakt_id": f"CON-{cid[:8]}",
            "id": cid,
            "name": name.strip(),
        }

    @mcp.tool()
    def kontakt_anzeigen(kontakt_id: str) -> dict:
        """Zeigt Details eines Kontakts inkl. Verknuepfungen."""
        # Typed-ID strippen wenn vorhanden
        from ..services.typed_ids import strip_prefix
        raw = strip_prefix(kontakt_id)
        # Wenn kurzes Praefix (8 Zeichen), suchen wir nach LIKE
        contact = None
        if len(raw) <= 8:
            conn = db.connect()
            row = conn.execute(
                "SELECT * FROM contacts WHERE id LIKE ? AND (profile_id=? OR profile_id IS NULL) LIMIT 1",
                (f"{raw}%", db.get_active_profile_id())
            ).fetchone()
            if row:
                contact = db._serialize_contact_row(row)
        else:
            contact = db.get_contact(raw)
        if not contact:
            return {"fehler": "Kontakt nicht gefunden."}
        links = db.get_contact_links(contact["id"])
        return {
            "kontakt": contact,
            "verknuepfungen": links,
            "anzahl_verknuepfungen": len(links),
        }

    @mcp.tool()
    def kontakte_auflisten(
        suche: str = "",
        rolle: str = "",
        firma: str = "",
    ) -> dict:
        """Listet Kontakte, optional gefiltert.

        Args:
            suche: Volltext (Name, E-Mail, Firma).
            rolle: Filter nach Rolle (z.B. 'recruiter').
            firma: Filter nach Firma (Substring).
        """
        contacts = db.list_contacts(search=suche, role=rolle, company=firma)
        return {
            "anzahl": len(contacts),
            "kontakte": contacts,
        }

    @mcp.tool()
    def kontakt_bearbeiten(
        kontakt_id: str,
        name: str = None,
        email: str = None,
        firma: str = None,
        position: str = None,
        telefon: str = None,
        linkedin_url: str = None,
        rollen: list[str] = None,
        notizen: str = None,
    ) -> dict:
        """Aktualisiert ausgewaehlte Felder eines Kontakts (#563)."""
        from ..services.typed_ids import strip_prefix
        raw = strip_prefix(kontakt_id)
        # Resolve short ID
        if len(raw) <= 8:
            conn = db.connect()
            row = conn.execute(
                "SELECT id FROM contacts WHERE id LIKE ? AND (profile_id=? OR profile_id IS NULL) LIMIT 1",
                (f"{raw}%", db.get_active_profile_id())
            ).fetchone()
            if not row:
                return {"fehler": "Kontakt nicht gefunden."}
            raw = row["id"]
        data = {}
        if name is not None:
            data["full_name"] = name
        if email is not None:
            data["email"] = email or None
        if firma is not None:
            data["company"] = firma or None
        if position is not None:
            data["position"] = position or None
        if telefon is not None:
            data["phone"] = telefon or None
        if linkedin_url is not None:
            data["linkedin_url"] = linkedin_url or None
        if rollen is not None:
            data["tags"] = rollen
        if notizen is not None:
            data["notes"] = notizen or None
        if not data:
            return {"fehler": "Keine Aenderungen angegeben."}
        ok = db.update_contact(raw, data)
        return {"status": "aktualisiert" if ok else "nicht_gefunden", "kontakt_id": kontakt_id}

    @mcp.tool()
    def kontakt_loeschen(kontakt_id: str, bestaetigung: bool = False) -> dict:
        """Loescht einen Kontakt. bestaetigung=True ist Pflicht."""
        if not bestaetigung:
            return {"fehler": "Bitte mit bestaetigung=True bestaetigen."}
        from ..services.typed_ids import strip_prefix
        raw = strip_prefix(kontakt_id)
        if len(raw) <= 8:
            conn = db.connect()
            row = conn.execute(
                "SELECT id FROM contacts WHERE id LIKE ? AND (profile_id=? OR profile_id IS NULL) LIMIT 1",
                (f"{raw}%", db.get_active_profile_id())
            ).fetchone()
            if not row:
                return {"fehler": "Kontakt nicht gefunden."}
            raw = row["id"]
        ok = db.delete_contact(raw)
        return {"status": "geloescht" if ok else "nicht_gefunden"}

    @mcp.tool()
    def kontakt_verknuepfen(
        kontakt_id: str,
        ziel_typ: str,
        ziel_id: str,
        rolle: str = "",
        notizen: str = "",
    ) -> dict:
        """Verknuepft einen Kontakt mit Bewerbung/Meeting/Stelle/Firma.

        Args:
            kontakt_id: ID des Kontakts (mit oder ohne CON-Prefix).
            ziel_typ: 'bewerbung' | 'meeting' | 'stelle' | 'firma'.
            ziel_id: ID des Ziels.
            rolle: Optional die Rolle in diesem Kontext (kann sich von den
                allgemeinen Tags unterscheiden — z.B. die gleiche Person
                ist 'recruiter' bei Firma A und 'kollege' bei Firma B).
            notizen: Freitext.
        """
        # Mapping deutsche Begriffe → interne target_kinds
        kind_map = {
            "bewerbung": "application",
            "meeting": "meeting",
            "termin": "meeting",
            "stelle": "job",
            "job": "job",
            "firma": "company",
        }
        target_kind = kind_map.get(ziel_typ.lower())
        if target_kind is None:
            return {"fehler": f"ziel_typ muss bewerbung/meeting/stelle/firma sein, nicht {ziel_typ!r}"}
        # IDs ggf. entprefixen
        from ..services.typed_ids import strip_prefix
        kraw = strip_prefix(kontakt_id)
        traw = strip_prefix(ziel_id)
        # Kurz-IDs aufloesen
        if len(kraw) <= 8:
            conn = db.connect()
            row = conn.execute(
                "SELECT id FROM contacts WHERE id LIKE ? LIMIT 1",
                (f"{kraw}%",)
            ).fetchone()
            if not row:
                return {"fehler": "Kontakt nicht gefunden."}
            kraw = row["id"]
        try:
            lid = db.link_contact(kraw, target_kind, traw, role=rolle, notes=notizen)
        except ValueError as e:
            return {"fehler": str(e)}
        return {"status": "verknuepft", "link_id": lid}

    @mcp.tool()
    def kontakt_entknuepfen(link_id: str) -> dict:
        """Entfernt eine Verknuepfung zwischen Kontakt und Ziel."""
        ok = db.unlink_contact(link_id)
        return {"status": "entfernt" if ok else "nicht_gefunden"}

    @mcp.tool()
    def kontakte_zu_bewerbung(bewerbung_id: str) -> dict:
        """Liste alle Kontakte zu einer Bewerbung (mit Rollen)."""
        from ..services.typed_ids import strip_prefix
        traw = strip_prefix(bewerbung_id)
        contacts = db.get_contacts_for_target("application", traw)
        return {
            "bewerbung_id": bewerbung_id,
            "anzahl": len(contacts),
            "kontakte": contacts,
        }

    # === v1.7.0-beta.39 (#608): Kontakt-Kategorien ===

    @mcp.tool()
    def kontakt_kategorien_auflisten() -> dict:
        """Listet alle Kontakt-Kategorien des aktiven Profils mit Farben.

        Liefert auch die Anzahl Kontakte pro Kategorie.
        Default-Kategorien (is_system=1) werden bei Bedarf automatisch
        angelegt: Recruiter, HR, Ansprechpartner, Endkunde, Vermittler,
        Referenz, Sonstiges.
        """
        items = db.list_contact_categories()
        return {"anzahl": len(items), "kategorien": items}

    @mcp.tool()
    def kontakt_kategorie_anlegen(name: str, farbe: str = "") -> dict:
        """Legt eine neue Kontakt-Kategorie an (#608).

        Args:
            name: Anzeigename (z.B. 'Headhunter', 'Alumni')
            farbe: Optional Hex-Code. Leer = Auto-Farbe aus Palette
                   (16 Farben, naechste freie wird gewaehlt).
        """
        try:
            cid = db.add_contact_category(name, color=farbe or "")
        except ValueError as e:
            return {"fehler": str(e)}
        return {"status": "angelegt", "id": cid, "name": name}

    @mcp.tool()
    def kontakt_kategorie_bearbeiten(
        kategorie_id: int, name: str = "", farbe: str = "",
    ) -> dict:
        """Aendert Name oder Farbe einer Kategorie. Nur uebergebene Felder."""
        if not name and not farbe:
            return {"fehler": "Mindestens name oder farbe muss angegeben sein"}
        ok = db.update_contact_category(
            kategorie_id,
            name=name or None,
            color=farbe or None,
        )
        if not ok:
            return {"fehler": "Kategorie nicht gefunden oder keine Aenderung"}
        return {"status": "aktualisiert", "id": kategorie_id}

    @mcp.tool()
    def kontakt_kategorie_loeschen(kategorie_id: int) -> dict:
        """Loescht eine Kategorie (#608).

        is_system=1-Kategorien sind geschuetzt und koennen nicht
        geloescht werden. Wenn noch zugewiesen: Fehler mit Anzahl
        betroffener Kontakte.
        """
        return db.delete_contact_category(kategorie_id)

    # === v1.7.0-beta.39 (#606): Auto-Import via lokale LLM ===

    @mcp.tool()
    def kontakte_aus_bestand_importieren(dry_run: bool = True) -> dict:
        """One-Shot-Migration: scannt alle Bewerbungen + Mails nach
        Kontakten und legt sie als pending an (User-Genehmigung in UI).

        Greift nur wenn lokale AI aktiv. Idempotent — Bewerbungen, die
        schon einen Contact mit `extracted_from='application:<id>'`
        haben, werden uebersprungen.

        Args:
            dry_run: True = nur Vorschau (default), False = echt anlegen.
        """
        from ..services.llm_service import get_llm_service, TaskKind
        svc = get_llm_service(db)
        s = svc.get_status(force_refresh=True)
        if not s.ollama_available or not s.available_models:
            return {
                "fehler": "Lokale AI nicht verfuegbar.",
                "hinweis": "Ollama + installiertes Modell noetig.",
            }
        if s.user_state != "active":
            return {
                "fehler": f"Lokale AI im State '{s.user_state}'.",
                "hinweis": "Setze State auf 'active' in Lokale-KI-Settings.",
            }

        bekannte = [c["slug"] for c in db.list_contact_categories()]
        pid = db.get_active_profile_id()
        conn = db.connect()

        # Alle Bewerbungen ohne extracted_from-Eintrag in contacts
        rows = conn.execute(
            "SELECT a.id, a.title, a.company, a.notes, a.description_snapshot, "
            "a.ansprechpartner, a.kontakt_email "
            "FROM applications a "
            "WHERE (a.profile_id=? OR a.profile_id IS NULL) "
            "AND NOT EXISTS ("
            "  SELECT 1 FROM contacts c "
            "  WHERE c.extracted_from = 'application:' || a.id"
            ") "
            "ORDER BY a.created_at DESC",
            (pid,)
        ).fetchall()

        candidates: list[dict] = []
        extracted = 0
        errors = 0
        for app_row in rows[:100]:  # Cap bei 100 fuer einen Lauf
            text_parts = [
                app_row["company"] or "",
                app_row["ansprechpartner"] or "",
                app_row["kontakt_email"] or "",
                (app_row["description_snapshot"] or "")[:1500],
                (app_row["notes"] or "")[:1500],
            ]
            text = "\n".join([p for p in text_parts if p])
            if not text.strip():
                continue
            try:
                result = svc.run(TaskKind.EXTRACT_CONTACTS, {
                    "text": text,
                    "context_company": app_row["company"] or "",
                    "bekannte_kategorien": bekannte,
                })
            except Exception:
                errors += 1
                continue
            if not result.success or not result.payload:
                errors += 1
                continue
            for c in result.payload.get("contacts") or []:
                if c.get("confidence", 0) < 0.5:
                    continue
                candidate = {
                    "name": c.get("name", ""),
                    "email": c.get("email", ""),
                    "kategorie": c.get("kategorie", "sonstiges"),
                    "rolle": c.get("rolle", ""),
                    "firma": app_row["company"] or "",
                    "confidence": c.get("confidence"),
                    "from_application": app_row["id"],
                }
                candidates.append(candidate)
                if not dry_run:
                    try:
                        db.add_contact({
                            "full_name": candidate["name"],
                            "email": candidate["email"],
                            "company": candidate["firma"],
                            "position": candidate["rolle"],
                            "tags": [candidate["kategorie"]],
                            "is_pending": 1,
                            "extracted_from": f"application:{app_row['id']}",
                        })
                        extracted += 1
                    except Exception:
                        errors += 1

        return {
            "status": "vorschau" if dry_run else "ausgefuehrt",
            "geprueft": len(rows),
            "kandidaten": len(candidates),
            "extrahiert": 0 if dry_run else extracted,
            "fehler": errors,
            "vorschau_sample": candidates[:10] if dry_run else None,
            "hinweis": (
                "Dry-Run — User in der UI mit pending-Genehmigung sichten."
                if dry_run else
                f"{extracted} Kontakte als 'pending' angelegt. "
                "Genehmigung in Kontakte-Tab."
            ),
        }

    # === v1.7.0-beta.54 (#605): Erweiterte Reverse-Extraktion ===

    @mcp.tool()
    def kontakte_aus_bewerbungen_extrahieren(
        nur_ohne_kontakte: bool = True,
        max_bewerbungen: int = 20,
        dry_run: bool = True,
    ) -> dict:
        """v1.7.0-beta.54 (#605): Reverse-Extraktion von Kontakten aus Bewerbungen.

        Erweitert `kontakte_aus_bestand_importieren` um drei wichtige
        Quellen:
        - `application_events.notes` (Timeline-Notizen mit Gespraechs-
          partnern)
        - Verknuepfte Dokumente (außer cv_path / cover_letter_path —
          das sind eigene Texte, keine Dritt-Kontaktdaten)
        - Konfigurierbares max_bewerbungen statt Hard-Cap 100

        Args:
            nur_ohne_kontakte: True (Default) = nur Bewerbungen die noch
                keinen verknuepften Kontakt haben (extracted_from leer).
                False = alle, auch schon mal extrahierte (ueberschreibt
                NICHT, legt nur neue an).
            max_bewerbungen: Sicherheits-Cap pro Lauf (Default 20).
            dry_run: True (Default) = nur Vorschau ohne Schreiben.

        Returns:
            status, geprueft, kandidaten, extrahiert (0 bei dry_run),
            fehler, vorschau_sample (10 erste Kandidaten bei dry_run).

        Idempotent. Sicher: bei `extracted_from='application:<id>'`-
        Markierung werden Bewerbungen uebersprungen (außer
        nur_ohne_kontakte=False).
        """
        from ..services.llm_service import get_llm_service, TaskKind
        svc = get_llm_service(db)
        s = svc.get_status(force_refresh=True)
        if not s.ollama_available or not s.available_models:
            return {
                "fehler": "Lokale AI nicht verfuegbar.",
                "hinweis": "Ollama + installiertes Modell noetig.",
            }
        if s.user_state != "active":
            return {
                "fehler": f"Lokale AI im State '{s.user_state}'.",
                "hinweis": "Setze State auf 'active' in Lokale-KI-Settings.",
            }

        bekannte = [c["slug"] for c in db.list_contact_categories()]
        pid = db.get_active_profile_id()
        conn = db.connect()

        # Bewerbungs-Auswahl mit/ohne Filter
        if nur_ohne_kontakte:
            rows = conn.execute(
                "SELECT a.id, a.title, a.company, a.notes, "
                "a.description_snapshot, a.ansprechpartner, a.kontakt_email, "
                "a.cv_path, a.cover_letter_path "
                "FROM applications a "
                "WHERE (a.profile_id=? OR a.profile_id IS NULL) "
                "AND NOT EXISTS ("
                "  SELECT 1 FROM contacts c "
                "  WHERE c.extracted_from = 'application:' || a.id"
                ") "
                "ORDER BY a.created_at DESC LIMIT ?",
                (pid, max_bewerbungen)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT a.id, a.title, a.company, a.notes, "
                "a.description_snapshot, a.ansprechpartner, a.kontakt_email, "
                "a.cv_path, a.cover_letter_path "
                "FROM applications a "
                "WHERE (a.profile_id=? OR a.profile_id IS NULL) "
                "ORDER BY a.created_at DESC LIMIT ?",
                (pid, max_bewerbungen)
            ).fetchall()

        candidates: list[dict] = []
        extracted = 0
        errors = 0
        for app_row in rows:
            text_parts = [
                f"Firma: {app_row['company']}" if app_row["company"] else "",
                f"Stelle: {app_row['title']}" if app_row["title"] else "",
                f"Ansprechpartner-Hint: {app_row['ansprechpartner']}"
                    if app_row["ansprechpartner"] else "",
                f"Kontakt-Email: {app_row['kontakt_email']}"
                    if app_row["kontakt_email"] else "",
            ]
            # Stellenbeschreibung
            if app_row["description_snapshot"]:
                text_parts.append(
                    f"Stellenbeschreibung:\n{app_row['description_snapshot'][:1500]}"
                )
            # Notizen
            if app_row["notes"]:
                text_parts.append(f"Notizen:\n{app_row['notes'][:1500]}")
            # Events (Timeline-Notizen)
            try:
                event_rows = conn.execute(
                    "SELECT status, event_date, notes "
                    "FROM application_events "
                    "WHERE application_id=? AND notes IS NOT NULL "
                    "AND notes != '' ORDER BY event_date DESC LIMIT 10",
                    (app_row["id"],)
                ).fetchall()
                for ev in event_rows:
                    snippet = (ev["notes"] or "")[:500]
                    if snippet:
                        text_parts.append(
                            f"Event {ev['event_date'][:10]} ({ev['status']}): {snippet}"
                        )
            except Exception:
                pass
            # Verknuepfte Dokumente (außer cv/cover_letter)
            try:
                docs = db.get_documents_for_application(app_row["id"], pid) or []
                cv_path = (app_row["cv_path"] or "").lower()
                cover_path = (app_row["cover_letter_path"] or "").lower()
                for d in docs:
                    fname = (d.get("filename") or "").lower()
                    fpath = (d.get("filepath") or "").lower()
                    if (fname == cv_path or fpath == cv_path
                            or fname == cover_path or fpath == cover_path):
                        continue
                    # Skip CV-/Anschreiben-typische Dokument-Typen
                    if d.get("doc_type") in ("cv", "lebenslauf", "anschreiben",
                                               "cover_letter"):
                        continue
                    text_parts.append(
                        f"Dokument {d.get('filename', '')}: "
                        f"(Typ: {d.get('doc_type', 'unbekannt')})"
                    )
            except Exception:
                pass

            text = "\n".join([p for p in text_parts if p]).strip()
            if not text:
                continue
            try:
                result = svc.run(TaskKind.EXTRACT_CONTACTS, {
                    "text": text[:5000],  # cap fuer LLM-Kontext
                    "context_company": app_row["company"] or "",
                    "bekannte_kategorien": bekannte,
                })
            except Exception:
                errors += 1
                continue
            if not result.success or not result.payload:
                errors += 1
                continue
            for c in result.payload.get("contacts") or []:
                if c.get("confidence", 0) < 0.5:
                    continue
                candidate = {
                    "name": c.get("name", ""),
                    "email": c.get("email", ""),
                    "telefon": c.get("telefon", ""),
                    "rolle": c.get("rolle", ""),
                    "kategorie": c.get("kategorie", "sonstiges"),
                    "firma": c.get("firma") or app_row["company"] or "",
                    "from_application": app_row["id"][:8],
                    "from_company": app_row["company"] or "",
                    "from_title": app_row["title"] or "",
                    "confidence": round(c.get("confidence", 0), 2),
                }
                candidates.append(candidate)
                if not dry_run:
                    try:
                        db.add_contact({
                            "full_name": candidate["name"],
                            "email": candidate["email"],
                            "phone": candidate["telefon"],
                            "company": candidate["firma"],
                            "position": candidate["rolle"],
                            "tags": [candidate["kategorie"]],
                            "is_pending": 1,
                            "extracted_from": f"application:{app_row['id']}",
                        })
                        extracted += 1
                    except Exception:
                        errors += 1

        return {
            "status": "vorschau" if dry_run else "ausgefuehrt",
            "geprueft": len(rows),
            "kandidaten": len(candidates),
            "extrahiert": 0 if dry_run else extracted,
            "fehler": errors,
            "vorschau_sample": candidates[:10] if dry_run else None,
            "hinweis": (
                f"Dry-Run mit max_bewerbungen={max_bewerbungen}. "
                "Mit dry_run=False werden die Kontakte als 'pending' angelegt "
                "und muessen via UI/MCP-Tool genehmigt werden."
                if dry_run else
                f"{extracted} Kontakte als 'pending' angelegt. "
                "Genehmigung in Kontakte-Tab."
            ),
        }

    # === v1.7.10 (#780, D28): Recruiter-Historie ===

    @mcp.tool()
    def kontakt_historie(suchbegriff: str) -> dict:
        """Historie zu einer Person: wer hat schon mal angefragt, wie lief es? (#780)

        Sucht ueber Personennamen, E-Mail und Telefonnummer — sowohl in der
        Kontaktdatenbank als auch in den FREITEXTFELDERN der Bewerbungen
        (`ansprechpartner`, `kontakt_email`). Damit funktioniert die Suche
        auch fuer den Altbestand, in dem Ansprechpartner nie als Kontakt
        angelegt wurden. Teilnamen genuegen ("van Wijk" findet
        "Saskia van Wijk").

        Typischer Ausloeser: ein Anruf — "Hier ist <Name>". Erst dieses Tool
        aufrufen, dann antworten (analog zur firma_kontext-Pflicht #753).

        Args:
            suchbegriff: Name, Namensteil, E-Mail oder Telefonnummer.
        """
        begriff = (suchbegriff or "").strip()
        if len(begriff) < 3:
            return {"fehler": "Suchbegriff braucht mindestens 3 Zeichen."}
        like = f"%{begriff.lower()}%"
        conn = db.connect()
        pid = db.get_active_profile_id()

        # 1) Kontaktdatenbank
        kontakt_rows = conn.execute(
            "SELECT * FROM contacts WHERE (profile_id=? OR profile_id IS NULL) "
            "AND (LOWER(COALESCE(full_name,'')) LIKE ? "
            "  OR LOWER(COALESCE(email,'')) LIKE ? "
            "  OR REPLACE(COALESCE(phone,''),' ','') LIKE REPLACE(?,' ','')) "
            "ORDER BY full_name",
            (pid, like, like, like),
        ).fetchall()
        kontakte = []
        for r in kontakt_rows:
            kontakte.append({
                "id": r["id"][:8],
                "name": r["full_name"],
                "firma": r["company"] or "",
                "email": r["email"] or "",
                "telefon": r["phone"] or "",
                "position": r["position"] or "",
            })

        # 2) Freitextfelder der Bewerbungen (Altbestand!)
        app_rows = conn.execute(
            "SELECT id, company, title, status, applied_at, created_at, "
            "       ansprechpartner, kontakt_email, vermittler, endkunde "
            "FROM applications WHERE (profile_id=? OR profile_id IS NULL) "
            "AND (LOWER(COALESCE(ansprechpartner,'')) LIKE ? "
            "  OR LOWER(COALESCE(kontakt_email,'')) LIKE ?) "
            "ORDER BY COALESCE(NULLIF(applied_at,''), created_at) DESC",
            (pid, like, like),
        ).fetchall()

        vorgaenge = []
        letzter_kontakt = ""
        for r in app_rows:
            datum = (r["applied_at"] or r["created_at"] or "")[:10]
            letzter_kontakt = max(letzter_kontakt, datum)
            vorgaenge.append({
                "bewerbung_id": r["id"][:8],
                "firma": r["company"],
                "titel": r["title"],
                "status": r["status"],
                "datum": datum,
                "ansprechpartner": r["ansprechpartner"] or "",
                "vermittler": r["vermittler"] or "",
                "endkunde": r["endkunde"] or "",
            })

        # 3) Verknuepfte Vorgaenge der gefundenen Kontakte (contact_links)
        for r in kontakt_rows:
            try:
                for link in db.get_contact_links(r["id"]):
                    if link.get("target_kind") != "application":
                        continue
                    app = db.get_application(link.get("target_id") or "")
                    if app and app["id"][:8] not in {
                        v["bewerbung_id"] for v in vorgaenge
                    }:
                        datum = (app.get("applied_at")
                                 or app.get("created_at") or "")[:10]
                        letzter_kontakt = max(letzter_kontakt, datum)
                        vorgaenge.append({
                            "bewerbung_id": app["id"][:8],
                            "firma": app.get("company", ""),
                            "titel": app.get("title", ""),
                            "status": app.get("status", ""),
                            "datum": datum,
                            "ansprechpartner": app.get("ansprechpartner") or "",
                            "vermittler": app.get("vermittler") or "",
                            "endkunde": app.get("endkunde") or "",
                            "quelle": "kontakt_verknuepfung",
                        })
            except Exception as e:
                logger.debug("kontakt_historie Links: %s", e)

        vorgaenge.sort(key=lambda v: v["datum"], reverse=True)
        if not kontakte and not vorgaenge:
            return {
                "status": "nichts_gefunden",
                "suchbegriff": begriff,
                "hinweis": (
                    "Weder in der Kontaktdatenbank noch in den "
                    "Bewerbungs-Freitextfeldern gefunden. Bei Firmen "
                    "stattdessen vermittler_historie() oder firma_kontext()."
                ),
            }
        return {
            "status": "ok",
            "suchbegriff": begriff,
            "kontakte": kontakte,
            "vorgaenge": vorgaenge,
            "anzahl_vorgaenge": len(vorgaenge),
            "letzter_kontakt": letzter_kontakt or None,
        }

    @mcp.tool()
    def vermittler_historie(firma: str) -> dict:
        """Aggregierte Historie eines Vermittlers/Personaldienstleisters (#780).

        Beantwortet vor der Reaktion auf eine neue Anfrage: Wie oft kam
        dieser Vermittler schon? Wohin fuehrte es? Welche Endkunden, welche
        Ansprechpartner? "Die sechste Anfrage, keine fuehrte zum Abschluss"
        aendert die Antwort.

        Args:
            firma: Vermittler-Name (Substring genuegt).
        """
        name = (firma or "").strip()
        if len(name) < 2:
            return {"fehler": "Firmenname braucht mindestens 2 Zeichen."}
        like = f"%{name.lower()}%"
        conn = db.connect()
        pid = db.get_active_profile_id()
        rows = conn.execute(
            "SELECT id, company, title, status, applied_at, created_at, "
            "       ansprechpartner, kontakt_email, vermittler, endkunde, "
            "       has_reached_interview "
            "FROM applications WHERE (profile_id=? OR profile_id IS NULL) "
            "AND (LOWER(COALESCE(company,'')) LIKE ? "
            "  OR LOWER(COALESCE(vermittler,'')) LIKE ?) "
            "ORDER BY COALESCE(NULLIF(applied_at,''), created_at)",
            (pid, like, like),
        ).fetchall()
        if not rows:
            return {
                "status": "nichts_gefunden",
                "firma": name,
                "hinweis": "Keine Bewerbung mit diesem Vermittler im Bestand. "
                           "Fuer Einzelpersonen: kontakt_historie(name).",
            }

        ausgaenge = {}
        endkunden = set()
        ansprechpartner = set()
        interviews = 0
        beworben = 0
        daten = []
        vorgaenge = []
        for r in rows:
            ausgaenge[r["status"]] = ausgaenge.get(r["status"], 0) + 1
            if r["endkunde"]:
                endkunden.add(r["endkunde"])
            if r["ansprechpartner"]:
                # Freitext kann mehrere Personen enthalten — grob an
                # Kommas/Und trennen, Klammer-Zusaetze bleiben dran.
                for teil in (r["ansprechpartner"]
                             .replace(" und ", ",").split(",")):
                    t = teil.strip()
                    if len(t) > 2:
                        ansprechpartner.add(t)
            if r["has_reached_interview"] == 1:
                interviews += 1
            if r["status"] != "in_vorbereitung":
                beworben += 1
            datum = (r["applied_at"] or r["created_at"] or "")[:10]
            if datum:
                daten.append(datum)
            vorgaenge.append({
                "bewerbung_id": r["id"][:8],
                "titel": r["title"],
                "status": r["status"],
                "datum": datum,
                "endkunde": r["endkunde"] or "",
                "ansprechpartner": r["ansprechpartner"] or "",
            })

        gesamt = len(rows)
        return {
            "status": "ok",
            "firma": name,
            "anfragen_gesamt": gesamt,
            "davon_beworben": beworben,
            "interviews": interviews,
            "interview_quote": round(interviews / gesamt * 100, 1) if gesamt else 0,
            "ausgaenge": ausgaenge,
            "endkunden": sorted(endkunden),
            "ansprechpartner": sorted(ansprechpartner),
            "zeitraum": {
                "erster_kontakt": min(daten) if daten else None,
                "letzter_kontakt": max(daten) if daten else None,
            },
            "vorgaenge": vorgaenge,
            "hinweis": (
                f"{gesamt + 1}. Anfrage waere die naechste. "
                + ("Noch kein Vorgang fuehrte zu einem Interview."
                   if interviews == 0 else
                   f"{interviews} Vorgang/Vorgaenge erreichten ein Interview.")
            ),
        }
