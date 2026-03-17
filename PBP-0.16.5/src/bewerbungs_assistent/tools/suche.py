"""Suchkriterien und Blacklist-Verwaltung — 2 Tools."""


def register(mcp, db, logger):
    """Registriert Suchkriterien-Tools."""

    @mcp.tool()
    def suchkriterien_setzen(
        keywords_muss: list[str] = None,
        keywords_plus: list[str] = None,
        keywords_ausschluss: list[str] = None,
        regionen: list[str] = None,
        custom_kriterien: dict = None
    ) -> dict:
        """Setzt die Suchkriterien fuer die Jobsuche.

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
        if custom_kriterien:
            db.set_search_criteria("custom_kriterien", custom_kriterien)
        return {"status": "gespeichert", "kriterien": db.get_search_criteria()}

    @mcp.tool()
    def blacklist_verwalten(
        aktion: str,
        typ: str = "firma",
        wert: str = "",
        grund: str = ""
    ) -> dict:
        """Verwaltet die Blacklist (Firmen, Keywords die automatisch aussortiert werden).

        Args:
            aktion: 'hinzufuegen', 'anzeigen'
            typ: 'firma', 'keyword', 'dismiss_pattern'
            wert: Der Blacklist-Eintrag
            grund: Grund fuer den Eintrag
        """
        if aktion == "hinzufuegen":
            db.add_to_blacklist(typ, wert, grund)
            return {"status": "hinzugefuegt", "typ": typ, "wert": wert}
        elif aktion == "anzeigen":
            return {"blacklist": db.get_blacklist()}
        return {"fehler": "Unbekannte Aktion. Nutze 'hinzufuegen' oder 'anzeigen'."}
