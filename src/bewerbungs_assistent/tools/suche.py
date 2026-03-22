"""Suchkriterien und Blacklist-Verwaltung — 4 Tools."""


def register(mcp, db, logger):
    """Registriert Suchkriterien-Tools."""

    @mcp.tool()
    def suchkriterien_setzen(
        keywords_muss: list[str] = None,
        keywords_plus: list[str] = None,
        keywords_ausschluss: list[str] = None,
        regionen: list[str] = None,
        stellentypen: list[str] = None,
        max_entfernung: dict = None,
        custom_kriterien: dict = None
    ) -> dict:
        """Setzt die Suchkriterien fuer die Jobsuche (ersetzt die gesamte Liste).

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
            stellentypen: Gewuenschte Stellentypen als Multi-Select (#166).
                Optionen: festanstellung, freelance, teilzeit, praktikum, werkstudent.
                Standard: ['festanstellung']
            max_entfernung: Max. Entfernung pro Stellentyp in km (#166).
                z.B. {"festanstellung": 50, "freelance": 200, "teilzeit": 30}
                Die Entfernung beeinflusst das Fit-Scoring als Malus.
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
        if custom_kriterien:
            db.set_search_criteria("custom_kriterien", custom_kriterien)
        return {"status": "gespeichert", "kriterien": db.get_search_criteria()}

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

        if aktion == "hinzufuegen":
            current_set = set(w.lower() for w in current)
            added = []
            for w in werte:
                if w.lower() not in current_set:
                    current.append(w)
                    added.append(w)
            db.set_search_criteria(key, current)
            return {"status": "hinzugefuegt", "kategorie": kategorie, "hinzugefuegt": added, "gesamt": len(current)}
        elif aktion == "entfernen":
            remove_set = set(w.lower() for w in werte)
            removed = [w for w in current if w.lower() in remove_set]
            current = [w for w in current if w.lower() not in remove_set]
            db.set_search_criteria(key, current)
            return {"status": "entfernt", "kategorie": kategorie, "entfernt": removed, "gesamt": len(current)}
        return {"fehler": "Aktion muss 'hinzufügen' oder 'entfernen' sein."}

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
        grund: str = ""
    ) -> dict:
        """Verwaltet die Blacklist (Firmen, Keywords die automatisch aussortiert werden).

        Args:
            aktion: 'hinzufügen', 'anzeigen'
            typ: 'firma', 'keyword', 'dismiss_pattern'
            wert: Der Blacklist-Eintrag
            grund: Grund für den Eintrag
        """
        if aktion == "hinzufuegen":
            db.add_to_blacklist(typ, wert, grund)
            return {"status": "hinzugefuegt", "typ": typ, "wert": wert}
        elif aktion == "anzeigen":
            return {"blacklist": db.get_blacklist()}
        return {"fehler": "Unbekannte Aktion. Nutze 'hinzufügen' oder 'anzeigen'."}
