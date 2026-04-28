"""Suchkriterien und Blacklist-Verwaltung — 5 Tools (#559: blacklist_anwenden)."""


def register(mcp, db, logger):
    """Registriert Suchkriterien-Tools."""

    @mcp.tool()
    def suchkriterien_setzen(
        keywords_muss: list[str] = None,
        keywords_plus: list[str] = None,
        keywords_ausschluss: list[str] = None,
        regionen: list[str] = None,
        standort: str = "",
        stellentypen: list[str] = None,
        max_entfernung: dict = None,
        min_gehalt: float = None,
        min_tagessatz: float = None,
        min_stundensatz: float = None,
        custom_kriterien: dict = None
    ) -> dict:
        """Setzt die Suchkriterien für die Jobsuche (ersetzt die gesamte Liste).

        MUSS-Keywords: Stelle wird nur beruecksichtigt wenn mindestens eins vorkommt.
        PLUS-Keywords: Erhoehen den Score (= bessere Sortierung).
        AUSSCHLUSS-Keywords: Stelle wird komplett ignoriert wenn eins vorkommt.

        Tipp: Leite die Keywords aus dem Profil ab! Was kann der User,
        was sucht er? Nutze profil_zusammenfassung() als Basis.

        Args:
            keywords_muss: Pflicht-Keywords (muessen vorkommen)
            keywords_plus: Bonus-Keywords (erhoehen Score)
            keywords_ausschluss: Ausschluss-Keywords (z.B. Junior, Praktikum)
            regionen: Bevorzugte Regionen
            standort: Wohnort des Bewerbers für Entfernungsberechnung (#167).
                z.B. 'Bremen' oder 'Bremen, Deutschland'. Wird einmalig geocoded und gecacht.
            stellentypen: Gewuenschte Stellentypen als Multi-Select (#166).
                Optionen: festanstellung, freelance, teilzeit, praktikum, werkstudent.
                Standard: ['festanstellung']
            max_entfernung: Max. Entfernung pro Stellentyp in km (#166).
                z.B. {"festanstellung": 50, "freelance": 200, "teilzeit": 30}
                Die Entfernung beeinflusst das Fit-Scoring als Malus.
            min_gehalt: Wunsch-Jahresgehalt in EUR (#544). Beeinflusst Fit-Scoring
                via Gehalt-Dimension (Malus bei deutlich niedrigerem Angebot).
            min_tagessatz: Wunsch-Tagessatz in EUR fuer Freelance (#544).
            min_stundensatz: Wunsch-Stundensatz in EUR fuer Teilzeit/Werkstudent (#544).
            custom_kriterien: Eigene Kriterien mit Gewichtung, z.B. {"homeoffice": 8, "gehalt": 7}
        """
        if keywords_muss:
            db.set_search_criteria("keywords_muss", keywords_muss)
        if keywords_plus:
            db.set_search_criteria("keywords_plus", keywords_plus)
        if keywords_ausschluss:
            db.set_search_criteria("keywords_ausschluss", keywords_ausschluss)
        if regionen:
            db.set_search_criteria("regionen", regionen)
        if stellentypen is not None:
            valid = {"festanstellung", "freelance", "teilzeit", "praktikum", "werkstudent"}
            stellentypen = [s for s in stellentypen if s in valid]
            db.set_search_criteria("stellentypen", stellentypen or ["festanstellung"])
        if max_entfernung is not None:
            db.set_search_criteria("max_entfernung", max_entfernung)
        # #544: Gehalts-Wuensche als top-level Parameter (nicht mehr in custom_kriterien
        # versteckt). Scoring liest sie aus criteria.get("min_gehalt"/...).
        if min_gehalt is not None:
            db.set_search_criteria("min_gehalt", float(min_gehalt))
        if min_tagessatz is not None:
            db.set_search_criteria("min_tagessatz", float(min_tagessatz))
        if min_stundensatz is not None:
            db.set_search_criteria("min_stundensatz", float(min_stundensatz))
        if custom_kriterien:
            db.set_search_criteria("custom_kriterien", custom_kriterien)

        # Geocode user location (#167)
        geo_info = None
        if standort:
            try:
                from ..services.geocoding_service import cache_user_coordinates
                coords = cache_user_coordinates(db, standort)
                if coords:
                    geo_info = f"Standort '{standort}' geocoded: {coords[0]:.4f}, {coords[1]:.4f}"
                else:
                    geo_info = f"Standort '{standort}' konnte nicht geocoded werden."
            except Exception as e:
                geo_info = f"Geocoding fehlgeschlagen: {e}"

        result = {"status": "gespeichert", "kriterien": db.get_search_criteria()}
        if geo_info:
            result["geocoding"] = geo_info
        return result

    @mcp.tool()
    def suchkriterien_bearbeiten(
        kategorie: str,
        aktion: str,
        werte: list[str] = None
    ) -> dict:
        """Einzelne Keywords zu Suchkriterien hinzufügen oder entfernen.

        Statt die gesamte Liste zu ersetzen, können einzelne Keywords
        inkrementell hinzugefügt oder entfernt werden.

        Args:
            kategorie: 'muss', 'plus' oder 'ausschluss'
            aktion: 'hinzufügen' oder 'entfernen'
            werte: Liste der Keywords
        """
        key_map = {"muss": "keywords_muss", "plus": "keywords_plus", "ausschluss": "keywords_ausschluss"}
        key = key_map.get(kategorie)
        if not key:
            return {"fehler": f"Kategorie muss 'muss', 'plus' oder 'ausschluss' sein, nicht '{kategorie}'"}
        if not werte:
            return {"fehler": "Keine Werte angegeben"}

        criteria = db.get_search_criteria()
        current = criteria.get(key, [])
        if isinstance(current, str):
            import json
            current = json.loads(current) if current else []

        # v1.6.4 (#528): Umlaut UND ASCII-Variante akzeptieren — KI-Aufrufer
        # wechseln je nach Kontext. Fehlermeldung nutzte selbst den Umlaut.
        action_norm = (aktion or "").strip().lower()
        if action_norm in ("hinzufügen", "hinzufuegen", "add"):
            current_set = set(w.lower() for w in current)
            added = []
            for w in werte:
                if w.lower() not in current_set:
                    current.append(w)
                    added.append(w)
            db.set_search_criteria(key, current)
            return {"status": "hinzugefuegt", "kategorie": kategorie, "hinzugefuegt": added, "gesamt": len(current)}
        elif action_norm in ("entfernen", "remove"):
            remove_set = set(w.lower() for w in werte)
            removed = [w for w in current if w.lower() in remove_set]
            current = [w for w in current if w.lower() not in remove_set]
            db.set_search_criteria(key, current)
            return {"status": "entfernt", "kategorie": kategorie, "entfernt": removed, "gesamt": len(current)}
        return {"fehler": "Aktion muss 'hinzufuegen'/'hinzufügen' oder 'entfernen' sein."}

    @mcp.tool()
    def suchkriterien_anzeigen() -> dict:
        """Zeigt die aktuellen Suchkriterien an.

        Gibt alle MUSS-, PLUS- und AUSSCHLUSS-Keywords, Regionen und
        benutzerdefinierte Kriterien zurück.
        """
        return {"kriterien": db.get_search_criteria()}

    @mcp.tool()
    def blacklist_verwalten(
        aktion: str,
        typ: str = "firma",
        wert: str = "",
        grund: str = "",
        entry_id: int = 0
    ) -> dict:
        """Verwaltet die Blacklist (Firmen und Keywords die bei der Jobsuche automatisch aussortiert werden).

        WICHTIG (#168): Die Blacklist ist NUR für harte Ausschlüsse gedacht:
        - 'firma': Firmen die IMMER ignoriert werden (z.B. CIDEON, Zeitarbeitsfirma XY)
        - 'keyword': Begriffe die IMMER ignoriert werden (z.B. Werkstudent, Praktikum)

        Individuelle Ablehnungsgründe (zu_weit, zu_junior, etc.) gehoeren NICHT hierher!
        Diese werden automatisch bei stelle_bewerten() als dismiss_reason gespeichert.

        Args:
            aktion: 'hinzufuegen', 'anzeigen', 'entfernen'
            typ: 'firma' oder 'keyword' (keine anderen Typen mehr!)
            wert: Der Blacklist-Eintrag (Firmenname oder Keyword)
            grund: Optionaler Grund für den Eintrag
            entry_id: ID des Eintrags (nur bei aktion='entfernen')
        """
        if aktion == "hinzufuegen":
            # Validate type (#168)
            if typ not in ("firma", "keyword"):
                return {
                    "fehler": f"Ungültiger Typ '{typ}'. Nur 'firma' oder 'keyword' erlaubt. "
                              "Ablehnungsgründe werden automatisch bei stelle_bewerten() gespeichert."
                }
            if not wert or not wert.strip():
                return {"fehler": "Kein Wert angegeben."}
            # Warn if entry looks too specific (#168)
            if len(wert) > 50:
                return {
                    "warnung": f"Der Eintrag '{wert[:50]}...' ist sehr lang. "
                               "Blacklist-Einträge sollten kurz und generisch sein "
                               "(z.B. Firmenname oder einzelnes Keyword). "
                               "Trotzdem hinzufügen? Rufe erneut auf wenn ja."
                }
            db.add_to_blacklist(typ, wert.strip(), grund)
            result = {"status": "hinzugefuegt", "typ": typ, "wert": wert.strip()}
            # #109: Blacklist-Eintrag löscht sofort alle Stellen des Unternehmens
            if typ == "firma":
                conn = db.connect()
                firma_lower = wert.strip().lower()
                dismissed = conn.execute(
                    "UPDATE jobs SET is_active=0, dismiss_reason='firma_blacklisted' "
                    "WHERE is_active=1 AND LOWER(company) LIKE ?",
                    (f"%{firma_lower}%",)
                ).rowcount
                conn.commit()
                if dismissed:
                    result["stellen_deaktiviert"] = dismissed
                    result["hinweis"] = (
                        f"{dismissed} aktive Stelle(n) von '{wert.strip()}' "
                        "wurden automatisch deaktiviert."
                    )
            return result
        elif aktion == "entfernen":
            if entry_id:
                ok = db.remove_blacklist_entry(entry_id)
                return {"status": "entfernt" if ok else "nicht_gefunden"}
            return {"fehler": "entry_id ist erforderlich zum Entfernen."}
        elif aktion == "anzeigen":
            entries = db.get_blacklist()
            return {
                "blacklist": entries,
                "anzahl": len(entries),
                "hinweis": "Nutze blacklist_verwalten('entfernen', entry_id=<id>) um Einträge zu entfernen."
            }
        return {"fehler": "Unbekannte Aktion. Nutze 'hinzufuegen', 'anzeigen' oder 'entfernen'."}

    @mcp.tool()
    def blacklist_anwenden(dry_run: bool = True) -> dict:
        """Wendet die aktuelle Blacklist retroaktiv auf alle aktiven Stellen an (#559).

        Wenn die Blacklist NACH einer Jobsuche erweitert wird, bleiben Stellen
        der neuen Blacklist-Firmen weiter aktiv. Dieses Tool sortiert sie
        nachtraeglich aus, ohne die Suche neu starten zu muessen.

        Args:
            dry_run: True (Standard) zeigt nur die Vorschau, False fuehrt aus.

        Returns:
            dry_run=True: {"betroffen": N, "vorschau": [...10...]}
            dry_run=False: {"deaktiviert": N, "betroffene_firmen": [...]}
        """
        bl_entries = db.get_blacklist()
        bl_firms = [e["value"] for e in bl_entries if e.get("type") == "firma"]
        bl_keywords = [e["value"] for e in bl_entries if e.get("type") == "keyword"]

        if not bl_firms and not bl_keywords:
            return {
                "status": "leer",
                "nachricht": "Blacklist ist leer. Nutze blacklist_verwalten('hinzufuegen', ...).",
            }

        # Aktive Stellen laden (ohne Blacklist-Filter, sonst sehen wir nichts)
        active = db.get_active_jobs()
        bl_firms_lc = [f.lower() for f in bl_firms]
        bl_keywords_lc = [k.lower() for k in bl_keywords]

        matched = []
        for j in active:
            company_lc = (j.get("company") or "").lower()
            title_lc = (j.get("title") or "").lower()
            firma_treffer = next(
                (f for f in bl_firms_lc if f and (f in company_lc or company_lc in f)),
                None,
            )
            kw_treffer = next(
                (k for k in bl_keywords_lc if k and (k in company_lc or k in title_lc)),
                None,
            )
            if firma_treffer or kw_treffer:
                matched.append({
                    "job": j,
                    "trigger": "firma" if firma_treffer else "keyword",
                    "wert": firma_treffer or kw_treffer,
                })

        if not matched:
            return {
                "status": "kein_treffer",
                "nachricht": "Keine aktiven Stellen passen zur Blacklist. Nichts zu tun.",
            }

        if dry_run:
            preview = [
                {
                    "hash": (m["job"].get("hash") or "")[:12],
                    "titel": m["job"].get("title"),
                    "firma": m["job"].get("company"),
                    "blacklist_typ": m["trigger"],
                    "blacklist_wert": m["wert"],
                }
                for m in matched[:10]
            ]
            return {
                "dry_run": True,
                "betroffen": len(matched),
                "vorschau": preview,
                "hinweis": (
                    f"{len(matched)} aktive Stelle(n) wuerden aussortiert. "
                    "Erneut mit dry_run=False aufrufen, um sie zu deaktivieren."
                ),
            }

        # Tatsaechlich anwenden — nutzt db.dismiss_job (resolve_job_hash inside),
        # damit profile-scoped Hashes korrekt aufgeloest werden.
        deaktiviert = 0
        firmen_betroffen: dict[str, int] = {}
        for m in matched:
            job_hash = m["job"].get("hash")
            if not job_hash:
                continue
            reason = f"{m['trigger']}_blacklisted"
            try:
                db.dismiss_job(job_hash, reason)
                deaktiviert += 1
                firma = m["job"].get("company") or "?"
                firmen_betroffen[firma] = firmen_betroffen.get(firma, 0) + 1
            except Exception as exc:
                logger.warning("blacklist_anwenden: %s fehlgeschlagen: %s", job_hash, exc)
        return {
            "dry_run": False,
            "deaktiviert": deaktiviert,
            "betroffene_firmen": dict(sorted(firmen_betroffen.items(), key=lambda x: -x[1])[:10]),
        }
