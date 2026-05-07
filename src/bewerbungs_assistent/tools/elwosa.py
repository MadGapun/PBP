"""MCP-Tools fuer Elwosa (#599).

User koennen NICHT direkt mit Elwosa kommunizieren — Claude ist der
Uebersetzer. Diese Tools geben Claude die Bridge:

- elwosa_lesen: Verlauf abrufen
- elwosa_schreiben: Im Namen von Elwosa posten (Tonfall-validiert)
- elwosa_pause: Schweigen anordnen
- elwosa_tonfall: Modus umstellen
- elwosa_linie_vorschlagen: Pool erweitern (User-Genehmigung)
- elwosa_status: Stimmung + Trigger-State
"""

from __future__ import annotations

from datetime import datetime, timedelta


def register(mcp, db, logger):
    from ..services.elwosa import (
        TonfallError, get_status, speak_raw, validate_tonfall,
    )

    @mcp.tool()
    def elwosa_lesen(limit: int = 20, since_iso: str = "") -> dict:
        """Liest die letzten Elwosa-Nachrichten aus dem Stream.

        Use Cases:
        - User fragt 'was hat Elwosa heute gesagt?'
        - User fragt 'was meinte Elwosa zu der Bewerbung?'
        - Claude will den Tonfall des Tages mitbekommen bevor es selbst
          eine Linie ueber elwosa_schreiben postet

        Args:
            limit: Anzahl der Nachrichten (max 100)
            since_iso: Optional ISO-Timestamp — nur neuere zurueck

        Rueckgabe:
            messages: Liste mit {content, trigger_kind, created_at, ...}
        """
        limit = max(1, min(int(limit or 20), 100))
        msgs = db.get_elwosa_messages(
            limit=limit,
            since_iso=since_iso or None,
        )
        return {"messages": msgs, "count": len(msgs)}

    @mcp.tool()
    def elwosa_schreiben(
        content: str,
        trigger_kind: str = "manual_via_claude",
        trigger_ref: str = "",
    ) -> dict:
        """Schreibt eine Nachricht IM NAMEN VON Elwosa in den Stream.

        Erscheint im Sidebar-Chat als waere sie von Elwosa selbst
        getriggert. WICHTIG: Tonfall wird hart validiert.

        Sprach-DNA-Regeln (siehe docs/elwosa-character.md):
        - KEINE Ausrufezeichen
        - KEINE Emojis
        - KEIN Hoeflichkeits-'Sie' / 'Ihr' / 'Ihnen' (Elwosa duzt)
        - Max 280 Zeichen
        - Lakonisch, britisch ironisch
        - Schluss-Phrasen wie 'Vermerkt.' / 'Vom Tisch.' / 'Markiert.' bevorzugt

        Use Cases:
        - User: 'Sag Elwosa danke fuer den Tipp gestern'
          → elwosa_schreiben("Gern geschehen. War nichts.")
        - Claude beobachtet User-Aktion und kommentiert
          → elwosa_schreiben("Drei Stellen aussortiert. Saubere Quote heute.",
                              trigger_kind="claude_handoff")

        Args:
            content: die Nachricht (max 280 Zeichen, Sprach-DNA-validiert)
            trigger_kind: 'manual_via_claude' | 'user_question' | 'claude_handoff'
            trigger_ref: optionaler Bezug (application_id, job_hash, ...)

        Bei Sprach-DNA-Verstoss:
            {"fehler": "..."} mit Hinweis auf konkrete Regel
        """
        try:
            validate_tonfall(content)
        except TonfallError as exc:
            return {
                "fehler": str(exc),
                "hinweis": "Siehe docs/elwosa-character.md Sektion 3 (Sprach-DNA).",
                "verboten": [
                    "Ausrufezeichen", "Emojis", "Hoeflichkeits-'Sie'",
                    "Mehr als 280 Zeichen",
                ],
            }
        valid_kinds = (
            "manual_via_claude", "user_question", "claude_handoff",
        )
        if trigger_kind not in valid_kinds:
            trigger_kind = "manual_via_claude"
        try:
            msg_id = speak_raw(
                db, content,
                trigger_kind=trigger_kind,
                trigger_ref=trigger_ref or "",
            )
        except TonfallError as exc:
            return {"fehler": str(exc)}
        return {
            "status": "gepostet",
            "message_id": msg_id,
            "content": content,
        }

    @mcp.tool()
    def elwosa_pause(minuten: int = 60) -> dict:
        """Pausiert Elwosa fuer X Minuten.

        Use Case: User: 'Sag Elwosa er soll mal eine Stunde Ruhe geben'

        Wirkung: Trigger-Engine ueberspringt automatische Linien fuer die
        Pause-Dauer. Eine einzige Pause-Nachricht wird gepostet
        ('Pausiert. Kein Stress, ich auch.'), dann Stille bis Frist.

        Args:
            minuten: Pause-Dauer (1-1440, also max 24h)
        """
        try:
            mins = int(minuten or 60)
        except (TypeError, ValueError):
            return {"fehler": "minuten muss eine Zahl sein"}
        if mins < 1 or mins > 1440:
            return {"fehler": "minuten muss zwischen 1 und 1440 (24h) liegen"}
        until = (datetime.now() + timedelta(minutes=mins)).isoformat()
        db.set_elwosa_settings(paused_until=until)
        # Pause-Notiz posten
        try:
            speak_raw(
                db,
                "Pausiert. Kein Stress, ich auch.",
                trigger_kind="ai_state_change",
            )
        except Exception:
            pass
        return {
            "status": "pausiert",
            "minuten": mins,
            "paused_until": until,
        }

    @mcp.tool()
    def elwosa_tonfall(modus: str) -> dict:
        """Stellt den Elwosa-Tonfall um.

        Args:
            modus: 'standard' | 'sachlich' | 'humorvoll' | 'minimal' | 'aus'
                - standard:   Default, wie in docs/elwosa-character.md
                - sachlich:   Kein Ironie-Anteil, nur Status-Linien
                - humorvoll:  Mehr Easter Eggs + Idle-Linien
                - minimal:    Nur 1 Linie pro Tag (morgens)
                - aus:        Equivalent zu Setting 'enabled=False'
        """
        valid = {"standard", "sachlich", "humorvoll", "minimal", "aus"}
        if modus not in valid:
            return {
                "fehler": f"modus muss eines von {sorted(valid)} sein",
            }
        if modus == "aus":
            db.set_elwosa_settings(enabled=False)
            return {"status": "ausgeschaltet"}
        db.set_elwosa_settings(enabled=True, tonfall_modus=modus)
        return {"status": "gespeichert", "modus": modus}

    @mcp.tool()
    def elwosa_linie_vorschlagen(
        cluster: str,
        trigger_kind: str,
        content: str,
        auto_aktivieren: bool = False,
    ) -> dict:
        """Schlaegt eine neue Linie fuer den Elwosa-Pool vor.

        Tonfall-Check + Validierung. Wenn auto_aktivieren=False (Default):
        Linie landet in 'pending'-Bucket, User muss in Settings genehmigen.
        Wenn auto_aktivieren=True: Linie kommt direkt in Pool des aktiven
        Profils.

        Args:
            cluster: 'student' | 'service' | 'trade' | 'tech_junior' |
                     'tech_senior' | 'engineering_senior' | 'freelance' |
                     'executive' | 'mixed' | 'global' | 'tip' | 'idle' |
                     'easter_egg'
            trigger_kind: passende Trigger-Klasse fuer den Pool-Eintrag
            content: die neue Linie (max 280 Zeichen, Sprach-DNA-validiert)
            auto_aktivieren: Sofort in Pool? Default False (User-Genehmigung)
        """
        try:
            validate_tonfall(content)
        except TonfallError as exc:
            return {"fehler": str(exc)}
        valid_clusters = {
            "student", "service", "trade", "tech_junior", "tech_senior",
            "engineering_senior", "freelance", "executive", "mixed",
            "global", "tip", "idle", "easter_egg",
        }
        if cluster not in valid_clusters:
            return {
                "fehler": f"cluster muss eines von {sorted(valid_clusters)} sein",
            }
        line_id = db.add_elwosa_pending_line(
            cluster=cluster,
            trigger_kind=trigger_kind,
            content=content,
        )
        if auto_aktivieren:
            db.approve_elwosa_pending_line(line_id)
            return {
                "status": "aktiviert",
                "line_id": line_id,
                "hinweis": (
                    "Direkt im Pool. User kann in Settings -> Lokale KI -> "
                    "Elwosa wieder entfernen."
                ),
            }
        return {
            "status": "vorgeschlagen",
            "line_id": line_id,
            "hinweis": (
                "Wartet auf User-Genehmigung in Settings -> Lokale KI -> Elwosa."
            ),
        }

    @mcp.tool()
    def elwosa_status() -> dict:
        """Liefert Elwosa-Status + aktuelle Stimmung + Trigger-State.

        Use Cases:
        - User fragt 'wie geht's Elwosa heute?'
        - Claude will wissen ob es selbst eine Linie schreiben soll
          oder ob Elwosa bald von alleine spricht

        Rueckgabe:
            is_active, ai_state, is_paused, paused_until,
            mood, messages_today, tonfall_modus, frequency,
            pool_size_total, pool_size_pending, last_message_at
        """
        # AI-State aus llm_service holen
        try:
            from ..services.llm_service import get_llm_service
            svc = get_llm_service(db)
            llm_status = svc.get_status()
            ai_state = llm_status.user_state if llm_status.ollama_available else "off"
        except Exception:
            ai_state = "active"  # Fallback
        return get_status(db, ai_state=ai_state)
