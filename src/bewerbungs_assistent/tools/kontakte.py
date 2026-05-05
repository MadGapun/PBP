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
