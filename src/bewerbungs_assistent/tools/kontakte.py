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
