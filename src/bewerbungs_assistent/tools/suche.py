"""Suchkriterien und Blacklist-Verwaltung — 5 Tools (#559: blacklist_anwenden)."""

# v1.7.12 (#828, C33): Woerter, die auf ein Gattungsurteil statt einer
# konkreten Erfahrung hindeuten. Belegter Fall 11.08.: ein Blacklist-Grund
# "bewusste Entscheidung gegen Beratungshaus" (tatsaechlicher Anlass: nie
# Rueckmeldung von genau EINER Firma) wurde bei spaeteren Bewertungen als
# generelle Haltung gelesen und verzerrte zwei unbeteiligte Stellen.
_KATEGORIEN_WOERTER = (
    "beratungshaus", "beratungshaeuser", "consulting", "zeitarbeit",
    "personaldienstleister", "vermittler", "branche", "generell",
    "grundsaetzlich", "alle ", "solche firmen", "diese art",
)


def _kategorienurteil_hinweis(grund: str):
    """Hinweis-Text, wenn ein Grund wie ein Gattungsurteil formuliert ist.

    Kein Block — nur der Hinweis. Die Entscheidung bleibt beim Nutzer.
    """
    g = (grund or "").lower()
    if not g:
        return None
    treffer = next((w for w in _KATEGORIEN_WOERTER if w in g), None)
    if not treffer:
        return None
    return (
        f"Der Grund klingt nach einem Urteil ueber eine ganze Gattung "
        f"('{treffer.strip()}'). Blacklist-Gruende werden bei spaeteren "
        "Bewertungen mitgelesen — ein Kategorienurteil faerbt dann auf "
        "unbeteiligte Firmen derselben Art ab. Praeziser ist, was mit "
        "DIESER Firma passiert ist (z. B. 'nie Rueckmeldung auf 3 "
        "Bewerbungen'). Aendern geht jederzeit: "
        "blacklist_verwalten('aendern', entry_id=..., grund=...)."
    )


def register(mcp, db, logger):
    """Registriert Suchkriterien-Tools."""

    @mcp.tool()
    def suchkriterien_setzen(
        keywords_muss: list[str] = None,
        keywords_plus: list[str] = None,
        keywords_minus: list[str] = None,
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
        MINUS-Keywords (#667, B19, beta.84): Senken den Score (weiche Abwertung).
            Stelle bleibt sichtbar, rutscht aber nach unten. Gegenstueck zu PLUS.
        AUSSCHLUSS-Keywords: Stelle wird komplett ignoriert wenn eins vorkommt.

        Wann was nutzen:
        - **Ausschluss**: harte k.o.-Begriffe (Junior, Werkstudent, Zeitarbeit, Bauwesen)
        - **Minus**: weich unschoen, aber nicht disqualifizierend (Automotive,
          Versicherung, Beratungshaus, "SAP-only")

        Tipp: Leite die Keywords aus dem Profil ab! Was kann der User,
        was sucht er? Nutze profil_zusammenfassung() als Basis.

        MALUS VERSCHAERFEN (#908): NIE ein Keyword doppelt eintragen —
        Listen werden dedupliziert. Der Weg zu einem staerkeren Einzel-
        Malus ist `keyword_gewichte` (#778):
        suchkriterien_bearbeiten(aktion='gewichten', ...).

        Args:
            keywords_muss: Pflicht-Keywords (muessen vorkommen)
            keywords_plus: Bonus-Keywords (erhoehen Score)
            keywords_minus: Malus-Keywords (senken Score, schliessen nicht aus)
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
        # v1.7.17 (#908 Befund 6): dedupliziert wie 'hinzufuegen' —
        # der Vollersatz war die stille Hintertuer, ueber die ein doppelt
        # eingetragenes MINUS-Keyword doppelt zaehlte und die
        # Trefferanzeige verfaelschte ("2 Treffer" fuer ein Wort).
        # Malus VERSCHAERFEN geht ueber keyword_gewichte (#778), nie
        # ueber Duplikate.
        def _dedup(werte: list) -> list:
            gesehen: set = set()
            out = []
            for w in werte or []:
                k = str(w).strip().lower()
                if k and k not in gesehen:
                    gesehen.add(k)
                    out.append(str(w).strip())
            return out

        if keywords_muss:
            db.set_search_criteria("keywords_muss", _dedup(keywords_muss))
        if keywords_plus:
            db.set_search_criteria("keywords_plus", _dedup(keywords_plus))
        # #667 (B19, beta.84): Minus-Keywords als weiche Score-Abwertung
        if keywords_minus:
            db.set_search_criteria("keywords_minus", _dedup(keywords_minus))
        if keywords_ausschluss:
            db.set_search_criteria("keywords_ausschluss",
                                   _dedup(keywords_ausschluss))
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
        # v1.7.12 (#827, C32): MUSS/PLUS-Ueberschneidung sichtbar machen.
        # Doppelt gelistete Begriffe zaehlen im Score nur noch EINMAL (als
        # MUSS) — der Hinweis erklaert, warum die PLUS-Liste kuerzer wirkt.
        _krit = result["kriterien"]
        _m = {k.strip().lower() for k in (_krit.get("keywords_muss") or [])}
        _doppelt = [k for k in (_krit.get("keywords_plus") or [])
                    if k.strip().lower() in _m]
        if _doppelt:
            result["hinweis_ueberschneidung"] = (
                f"{len(_doppelt)} Begriff(e) stehen in MUSS UND PLUS "
                f"({', '.join(_doppelt[:5])}) — sie zaehlen im Score nur "
                "einmal (als MUSS). In PLUS gehoeren Begriffe, die KEIN "
                "Pflichtkriterium sind, aber die Sortierung verbessern."
            )
        return result

    @mcp.tool()
    def suchkriterien_bearbeiten(
        kategorie: str,
        aktion: str,
        werte: list[str] = None,
        gewicht: float = 0.0,
    ) -> dict:
        """Einzelne Keywords zu Suchkriterien hinzufügen, entfernen oder gewichten.

        Statt die gesamte Liste zu ersetzen, können einzelne Keywords
        inkrementell hinzugefügt oder entfernt werden.

        v1.7.10 (#778/C29):
        - aktion='gewichten' setzt ein EINZELGEWICHT pro Keyword (Override
          des Kategorie-Gewichts, z.B. 'Arbeitnehmerueberlassung' mit
          Gewicht 2 statt Kategorie-Malus 6). aktion='gewicht_entfernen'
          setzt zurueck auf das Kategorie-Gewicht.
        - kategorie='scoring', aktion='idf' mit werte=['an']/['aus']
          schaltet die IDF-Seltenheitsgewichtung + Top-5-Deckelung um
          (Default: aus). Danach `kalibrierung_backtest()` laufen lassen
          und erst dann `scores_neu_berechnen()`.

        Args:
            kategorie: 'muss', 'plus', 'minus' oder 'ausschluss'
                (minus seit #667 / B19, beta.84 — weiche Score-Abwertung);
                'scoring' nur fuer aktion='idf'
            aktion: 'hinzufügen', 'entfernen', 'gewichten',
                'gewicht_entfernen' oder 'idf'
            werte: Liste der Keywords (bei 'idf': ['an'] oder ['aus'])
            gewicht: Punktwert pro Treffer bei aktion='gewichten'
        """
        action_norm0 = (aktion or "").strip().lower()

        # --- #778: IDF-Schalter ---
        if action_norm0 == "idf":
            wert = (werte[0].lower() if werte else "").strip()
            if wert not in ("an", "aus", "on", "off"):
                return {"fehler": "aktion='idf' braucht werte=['an'] oder ['aus']."}
            an = wert in ("an", "on")
            db.set_search_criteria("scoring_idf", an)
            result = {
                "status": "idf_" + ("aktiviert" if an else "deaktiviert"),
                "hinweis": (
                    "Seltenheitsgewichtung (IDF) + Top-5-Deckelung der "
                    "MUSS-Summe sind jetzt "
                    + ("AKTIV. Empfehlung: erst kalibrierung_backtest() "
                       "pruefen, dann scores_neu_berechnen()."
                       if an else "aus — das Scoring rechnet wieder klassisch. "
                       "scores_neu_berechnen() nicht vergessen.")
                ),
            }
            return result

        key_map = {
            "muss": "keywords_muss",
            "plus": "keywords_plus",
            "minus": "keywords_minus",  # #667
            "ausschluss": "keywords_ausschluss",
        }
        key = key_map.get(kategorie)
        if not key:
            return {
                "fehler": (
                    f"Kategorie muss 'muss', 'plus', 'minus' oder 'ausschluss' "
                    f"sein, nicht '{kategorie}'"
                )
            }
        if not werte:
            return {"fehler": "Keine Werte angegeben"}

        # --- #778: Einzelgewichte pro Keyword ---
        if action_norm0 in ("gewichten", "gewicht_entfernen"):
            if kategorie == "ausschluss":
                return {"fehler": (
                    "Ausschluss-Keywords haben kein Gewicht — sie sind ein "
                    "harter K.o. Fuer eine mildere Wirkung das Keyword nach "
                    "'minus' verschieben und dort gewichten."
                )}
            criteria_g = db.get_search_criteria()
            kg = criteria_g.get("keyword_gewichte") or {}
            if not isinstance(kg, dict):
                kg = {}
            geaendert = []
            for wrt in werte:
                wl = wrt.lower()
                if action_norm0 == "gewichten":
                    if gewicht <= 0:
                        return {"fehler": "gewicht muss > 0 sein (Punkte pro Treffer)."}
                    kg[wl] = gewicht
                    geaendert.append({wrt: gewicht})
                else:
                    kg.pop(wl, None)
                    geaendert.append({wrt: "Kategorie-Gewicht"})
            db.set_search_criteria("keyword_gewichte", kg)
            return {
                "status": "gewichtet" if action_norm0 == "gewichten" else "zurueckgesetzt",
                "kategorie": kategorie,
                "geaendert": geaendert,
                "alle_einzelgewichte": kg,
                "hinweis": "Wirkt ab der naechsten Score-Berechnung — "
                           "scores_neu_berechnen() fuer den Bestand.",
            }

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
            result = {"status": "hinzugefuegt", "kategorie": kategorie,
                      "hinzugefuegt": added, "gesamt": len(current)}
            # v1.7.10 (#778): DE/EN-Paare fuer Ausschluss-Klassiker. Praxis-
            # Fall 24.07.: nur deutsche Junior-Begriffe gepflegt — eine
            # englische "Working Student (f/m/d)"-Anzeige erreichte Score 40.
            if kategorie == "ausschluss":
                paare = {
                    "werkstudent": "Working Student",
                    "working student": "Werkstudent",
                    "praktikant": "Intern",
                    "praktikum": "Internship",
                    "intern": "Praktikant",
                    "internship": "Praktikum",
                    "auszubildende": "Apprentice",
                    "ausbildung": "Apprenticeship",
                    "apprentice": "Auszubildende",
                    "berufseinsteiger": "Entry Level",
                    "entry level": "Berufseinsteiger",
                    "studentische hilfskraft": "Student Assistant",
                }
                jetzt = {w.lower() for w in current}
                fehlend = sorted({
                    partner for wrt in added
                    for kw_l, partner in paare.items()
                    if kw_l == wrt.lower() and partner.lower() not in jetzt
                })
                if fehlend:
                    result["hinweis_sprachpaare"] = (
                        "Anzeigen sind oft englisch — diese Pendants fehlen "
                        f"noch im Ausschluss: {', '.join(fehlend)}. "
                        "Bei Bedarf gleich mit aufnehmen."
                    )
            return result
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

        Gibt alle MUSS-, PLUS-, MINUS- und AUSSCHLUSS-Keywords, Regionen und
        benutzerdefinierte Kriterien zurueck. (MINUS seit #667 / B19, beta.84.)
        """
        return {"kriterien": db.get_search_criteria()}

    @mcp.tool()
    def blacklist_verwalten(
        aktion: str,
        typ: str = "firma",
        wert: str = "",
        grund: str = "",
        entry_id: int = 0,
        force: bool = False,
        ausser_wenn_titel_enthaelt: list[str] = None,
    ) -> dict:
        """Verwaltet die Blacklist (Firmen und Keywords die bei der Jobsuche automatisch aussortiert werden).

        WICHTIG (#168): Die Blacklist ist NUR für harte Ausschlüsse gedacht:
        - 'firma': Firmen die IMMER ignoriert werden (z.B. CIDEON, Zeitarbeitsfirma XY)
        - 'keyword': Begriffe die IMMER ignoriert werden (z.B. Werkstudent, Praktikum)

        Individuelle Ablehnungsgründe (zu_weit, zu_junior, etc.) gehoeren NICHT hierher!
        Diese werden automatisch bei stelle_bewerten() als dismiss_reason gespeichert.

        Args:
            aktion: 'hinzufuegen', 'anzeigen', 'aendern', 'deaktivieren',
                'aktivieren', 'entfernen'. v1.7.12 (#828, C33): 'aendern'
                korrigiert grund/wert/ausser_wenn_titel_enthaelt in place
                (created_at bleibt, alter Grund wandert nach grund_vorher);
                'deaktivieren' pausiert den Eintrag ohne Datenverlust —
                fuer "die Firma will ich erstmal wieder zulassen, aber den
                Eintrag nicht wegwerfen".
            typ: 'firma' oder 'keyword' (keine anderen Typen mehr!)
            wert: Der Blacklist-Eintrag (Firmenname oder Keyword)
            grund: Grund fuer den Eintrag. WICHTIG: beschreiben, was mit
                DIESER Firma passiert ist ("nie Rueckmeldung auf 3
                Bewerbungen"), nicht ihre Gattung ("Beratungshaus") —
                der Grund wird bei spaeteren Bewertungen mitgelesen, und
                ein Kategorienurteil faerbt auf unbeteiligte Firmen
                derselben Branche ab.
            entry_id: ID des Eintrags (bei aendern/deaktivieren/
                aktivieren/entfernen; steht im hinzufuegen-Result und in
                'anzeigen')
            force: True ueberstimmt die Warnung bei laufenden Bewerbungen
                im Interview-Stadium (#699) und traegt trotzdem ein.
            ausser_wenn_titel_enthaelt: v1.7.11 (#790/C31) — Liste von
                Begriffen, bei denen ein FIRMEN-Block NICHT greift
                (case-insensitiv im Stellentitel). Gedacht fuer
                Personaldienstleister und Beratungen, die quer durch alle
                Fachgebiete ausschreiben: die Firma bleibt grundsaetzlich
                geblockt, die fachlich passenden Rollen kommen trotzdem
                durch. Beispiel: ausser_wenn_titel_enthaelt=['PLM', 'PDM'].
                Wirkt auch retroaktiv in blacklist_anwenden().
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
            # #699: Schutz fuer laufende Bewerbungen — eine Blacklist-Firma
            # deaktiviert automatisch alle aktiven Stellen der Firma. Laeuft
            # parallel eine Bewerbung im Interview-Stadium, verliert der User
            # genau dann den Stellen-Kontext (Fit-Analyse, Beschreibung),
            # wenn er ihn am dringendsten braucht.
            if typ == "firma" and not force:
                kritische_status = (
                    "interview", "zweitgespraech", "angebot",
                    "interview_abgeschlossen",
                )
                conn = db.connect()
                pid = db.get_active_profile_id()
                betroffene = conn.execute(
                    "SELECT id, title, company, status FROM applications "
                    f"WHERE status IN ({','.join('?' * len(kritische_status))}) "
                    "AND LOWER(company) LIKE ? "
                    "AND (profile_id=? OR profile_id IS NULL)",
                    (*kritische_status, f"%{wert.strip().lower()}%", pid)
                ).fetchall()
                if betroffene:
                    details = [
                        {
                            "id": r["id"], "titel": r["title"],
                            "firma": r["company"], "status": r["status"],
                        } for r in betroffene
                    ]
                    return {
                        "status": "warnung",
                        "nachricht": (
                            f"Firma '{wert.strip()}' hat {len(betroffene)} "
                            f"laufende Bewerbung(en) im Status "
                            f"{', '.join(sorted({r['status'] for r in betroffene}))}. "
                            "Ein Blacklist-Eintrag wuerde die zugehoerigen "
                            "Stellen deaktivieren."
                        ),
                        "betroffene_bewerbungen": details,
                        "hinweis": "Mit force=True trotzdem eintragen.",
                    }
            ausnahmen = [a.strip() for a in (ausser_wenn_titel_enthaelt or [])
                         if a and a.strip()]
            neu_id = db.add_to_blacklist(typ, wert.strip(), grund,
                                         ausser_wenn_titel_enthaelt=ausnahmen)
            result = {"status": "hinzugefuegt", "typ": typ,
                      "wert": wert.strip(), "entry_id": neu_id}
            # v1.7.12 (#828): beim Anlegen zum praezisen Grund anleiten.
            warnung = _kategorienurteil_hinweis(grund)
            if warnung:
                result["hinweis_grund"] = warnung
            if ausnahmen:
                result["ausser_wenn_titel_enthaelt"] = ausnahmen
                result["hinweis_ausnahme"] = (
                    "Stellen dieser Firma werden NICHT geblockt, wenn ihr "
                    f"Titel einen dieser Begriffe enthaelt: {', '.join(ausnahmen)}."
                )
            # #109: Blacklist-Eintrag löscht sofort alle Stellen des Unternehmens
            # v1.7.11 (#790): ausser denen, die unter die Ausnahme fallen
            if typ == "firma":
                conn = db.connect()
                firma_lower = wert.strip().lower()
                sql = ("UPDATE jobs SET is_active=0, "
                       "dismiss_reason='firma_blacklisted' "
                       "WHERE is_active=1 AND LOWER(company) LIKE ?")
                params = [f"%{firma_lower}%"]
                for a in ausnahmen:
                    sql += " AND LOWER(COALESCE(title,'')) NOT LIKE ?"
                    params.append(f"%{a.lower()}%")
                dismissed = conn.execute(sql, params).rowcount
                conn.commit()
                if dismissed:
                    result["stellen_deaktiviert"] = dismissed
                    result["hinweis"] = (
                        f"{dismissed} aktive Stelle(n) von '{wert.strip()}' "
                        "wurden automatisch deaktiviert."
                        + (" Stellen mit den Ausnahme-Begriffen im Titel "
                           "blieben aktiv." if ausnahmen else "")
                    )
            return result
        elif aktion == "entfernen":
            if entry_id:
                ok = db.remove_blacklist_entry(entry_id)
                return {"status": "entfernt" if ok else "nicht_gefunden",
                        "hinweis": ("Loeschen verwirft Grund, Historie und "
                                    "Titel-Ausnahmen. 'deaktivieren' behaelt "
                                    "alles und laesst sich rueckgaengig machen.")}
            return {"fehler": "entry_id ist erforderlich zum Entfernen."}
        elif aktion == "aendern":
            # v1.7.12 (#828, C33): in place aendern statt loeschen+neu —
            # created_at und Ausnahmen bleiben, der alte Grund wandert nach
            # grund_vorher.
            if not entry_id:
                return {"fehler": "entry_id ist erforderlich zum Aendern. "
                                  "IDs zeigt blacklist_verwalten('anzeigen')."}
            neu = db.update_blacklist_entry(
                entry_id,
                wert=wert.strip() if wert and wert.strip() else None,
                grund=grund if grund else None,
                ausser_wenn_titel_enthaelt=(
                    [a.strip() for a in ausser_wenn_titel_enthaelt
                     if a and a.strip()]
                    if ausser_wenn_titel_enthaelt is not None else None),
            )
            if neu is None:
                return {"status": "nicht_gefunden", "entry_id": entry_id}
            result = {"status": "geaendert", "entry_id": entry_id,
                      "eintrag": {"wert": neu.get("value"),
                                  "grund": neu.get("reason"),
                                  "grund_vorher": neu.get("grund_vorher"),
                                  "updated_at": neu.get("updated_at")}}
            warnung = _kategorienurteil_hinweis(grund)
            if warnung:
                result["hinweis_grund"] = warnung
            return result
        elif aktion in ("deaktivieren", "aktivieren"):
            if not entry_id:
                return {"fehler": f"entry_id ist erforderlich zum "
                                  f"{aktion.capitalize()}."}
            aktiv = aktion == "aktivieren"
            ok = db.set_blacklist_active(entry_id, aktiv)
            if not ok:
                return {"status": "nicht_gefunden", "entry_id": entry_id}
            result = {"status": "aktiviert" if aktiv else "deaktiviert",
                      "entry_id": entry_id}
            if not aktiv:
                result["hinweis"] = (
                    "Der Eintrag bleibt sichtbar, greift aber nicht mehr — "
                    "weder bei neuen Funden noch in blacklist_anwenden. "
                    "Bereits deaktivierte Stellen der Firma bleiben "
                    "deaktiviert; stelle_reaktivieren holt sie zurueck.")
            return result
        elif aktion == "anzeigen":
            entries = db.get_blacklist(include_inactive=True)
            aktive = [e for e in entries
                      if (e.get("is_active") if e.get("is_active") is not None
                          else 1)]
            inaktive = [e for e in entries if e not in aktive]
            mit_ausnahme = [e for e in aktive
                            if e.get("ausser_wenn_titel_enthaelt")]
            res = {
                "blacklist": aktive,
                "anzahl": len(aktive),
                "hinweis": ("Aendern: blacklist_verwalten('aendern', "
                            "entry_id=<id>, grund=...). Pausieren: "
                            "'deaktivieren' statt 'entfernen' — behaelt "
                            "Grund und Ausnahmen.")
            }
            if inaktive:
                res["inaktiv"] = [
                    {"id": e.get("id"), "typ": e.get("type"),
                     "wert": e.get("value"), "grund": e.get("reason")}
                    for e in inaktive
                ]
                res["inaktiv_hinweis"] = (
                    f"{len(inaktive)} Eintraege sind deaktiviert und greifen "
                    "NICHT. Reaktivieren: blacklist_verwalten('aktivieren', "
                    "entry_id=<id>).")
            if mit_ausnahme:
                res["mit_titel_ausnahme"] = [
                    {"wert": e.get("value"),
                     "ausser_wenn_titel_enthaelt": e["ausser_wenn_titel_enthaelt"]}
                    for e in mit_ausnahme
                ]
            return res
        return {"fehler": "Unbekannte Aktion. Nutze 'hinzufuegen', 'anzeigen', "
                          "'aendern', 'deaktivieren', 'aktivieren' oder "
                          "'entfernen'."}

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

        # v1.7.11 (#790/C31): Titel-Ausnahmen je Firmen-Eintrag. Ohne das
        # entfernt ein retroaktiver Lauf genau die passenden Stellen wieder,
        # die die Ausnahme beim Anlegen durchgelassen hat.
        ausnahmen_je_firma = {
            (e.get("value") or "").lower(): [
                a.lower() for a in (e.get("ausser_wenn_titel_enthaelt") or [])
            ]
            for e in bl_entries if e.get("type") == "firma"
        }
        verschont = []

        matched = []
        for j in active:
            company_lc = (j.get("company") or "").lower()
            title_lc = (j.get("title") or "").lower()
            firma_treffer = next(
                (f for f in bl_firms_lc if f and (f in company_lc or company_lc in f)),
                None,
            )
            if firma_treffer:
                _greift = next(
                    (a for a in ausnahmen_je_firma.get(firma_treffer, [])
                     if a and a in title_lc), None)
                if _greift:
                    verschont.append({
                        "hash": j.get("hash"), "titel": j.get("title"),
                        "firma": j.get("company"),
                        "ausnahme_begriff": _greift,
                    })
                    firma_treffer = None
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
            res = {
                "status": "kein_treffer",
                "nachricht": "Keine aktiven Stellen passen zur Blacklist. Nichts zu tun.",
            }
            if verschont:
                res["durch_ausnahme_verschont"] = verschont
            return res

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

    # === v1.7.0-beta.32 (#564): Portal-spezifische Such-Profile ===
    #
    # Wenn die Chrome-Extension auf LinkedIn/StepStone/XING sucht, soll
    # sie NICHT die naiven `keywords_muss` einsetzen — die sind fuer
    # Volltext-Filtern nach dem Scraping gebaut. LinkedIn akzeptiert z.B.
    # Phrase-Match `"PLM Architect"` nicht (0 Treffer), und 3-Buchstaben-
    # Abkuerzungen wie `PLM` matchen massenhaft Muell. Diese Tools
    # speichern erprobte Suchbegriffe pro Portal.

    @mcp.tool()
    def suchprofil_lesen(portal: str) -> dict:
        """Liefert das gespeicherte Such-Profil fuer ein Portal (#564).

        Wird von der Chrome-Extension VOR jeder Suche aufgerufen, damit
        statt der naiven `keywords_muss` die portal-spezifisch erprobten
        Suchbegriffe + Filter eingesetzt werden.

        Args:
            portal: 'linkedin' | 'xing' | 'stepstone' | ...

        Rueckgabe-Struktur:
            primaere_suchen: list[{keywords, filter?, notiz?}]
            sekundaere_suchen: list[{keywords, filter?, notiz?}]
            nicht_verwenden: list[{wert, grund}]
            notizen: str
        """
        if not portal:
            return {"fehler": "portal-Parameter ist Pflicht"}
        return db.get_portal_search_profile(portal)

    @mcp.tool()
    def suchprofil_aktualisieren(
        portal: str,
        primaere_suchen: list = None,
        sekundaere_suchen: list = None,
        nicht_verwenden: list = None,
        notizen: str = None,
    ) -> dict:
        """Aktualisiert das Such-Profil eines Portals (#564).

        Nur die uebergebenen Felder werden ueberschrieben — leer/None
        heisst „nicht aendern".

        Args:
            portal: 'linkedin' | 'xing' | 'stepstone' | ...
            primaere_suchen: Liste von Suchen, die zuerst probiert werden.
                Format: [{"keywords": "PDM", "filter": {"branche": [...]},
                          "notiz": "treffsicher"}]
            sekundaere_suchen: Liste von Such-Fallbacks (z.B. generischere
                Begriffe, die ohne Filter Muell liefern).
            nicht_verwenden: Liste von ausgeschlossenen Suchen.
                Format: [{"wert": "PLM Architect", "grund": "0 Treffer"}]
            notizen: Freitext mit Lessons.
        """
        if not portal:
            return {"fehler": "portal-Parameter ist Pflicht"}
        try:
            return db.update_portal_search_profile(
                portal,
                primaere_suchen=primaere_suchen,
                sekundaere_suchen=sekundaere_suchen,
                nicht_verwenden=nicht_verwenden,
                notizen=notizen,
            )
        except ValueError as exc:
            return {"fehler": str(exc)}

    @mcp.tool()
    def suchprofile_auflisten() -> dict:
        """Listet alle gespeicherten Portal-Such-Profile (#564)."""
        items = db.list_portal_search_profiles()
        return {"profile": items, "anzahl": len(items)}

    # === Ablehnungsgruende-Verwaltung (#663 C20, beta.85) ==================
    # Erweitert die hardcoded Whitelist um User-Custom-Eintraege. is_custom=1
    # + is_active=1 -> wird in stelle_bewerten zusaetzlich akzeptiert.

    @mcp.tool()
    def ablehnungsgruende_anzeigen(nur_aktiv: bool = False) -> dict:
        """Listet alle Ablehnungsgruende (Standard + Custom) mit Verwendungs-Haeufigkeit (#663 C20).

        Args:
            nur_aktiv: True = nur aktive Gruende. False (Default) zeigt alle
                inkl. deaktivierte.
        """
        rows = db.get_dismiss_reasons() or []
        items = []
        for r in rows:
            entry = {
                "id": r.get("id"),
                "label": r.get("label"),
                "is_custom": bool(r.get("is_custom")),
                "usage_count": r.get("usage_count", 0),
                "is_active": bool(r.get("is_active", 1)),
                "created_at": r.get("created_at"),
            }
            if nur_aktiv and not entry["is_active"]:
                continue
            items.append(entry)
        items.sort(key=lambda x: (-x["usage_count"], x["label"] or ""))
        return {
            "status": "ok",
            "anzahl": len(items),
            "gruende": items,
        }

    @mcp.tool()
    def ablehnungsgrund_anlegen(label: str) -> dict:
        """Legt einen neuen Custom-Ablehnungsgrund an (#663 C20).

        Wenn der Grund schon existiert (gleicher Label im Profil-Scope),
        wird das gemeldet ohne Duplikat anzulegen.

        Args:
            label: Kurzbezeichnung (z.B. 'kein_homeoffice', 'falsche_branche').
                Snake_case empfohlen, Umlaute erlaubt.
        """
        label = (label or "").strip()
        if not label:
            return {"fehler": "label ist Pflicht."}
        # Existenz-Check
        try:
            existing = next(
                (r for r in (db.get_dismiss_reasons() or []) if r.get("label") == label),
                None,
            )
            if existing:
                return {
                    "status": "bereits_vorhanden",
                    "id": existing.get("id"),
                    "label": label,
                    "is_active": bool(existing.get("is_active", 1)),
                    "hinweis": (
                        "Nutze ablehnungsgrund_aktivieren_setzen(id, True) "
                        "falls deaktiviert, oder ablehnungsgrund_umbenennen "
                        "wenn du einen aehnlichen meintest."
                    ),
                }
        except Exception:
            pass
        rid = db.add_dismiss_reason(label)
        return {
            "status": "angelegt",
            "id": rid,
            "label": label,
            "is_custom": True,
            "is_active": True,
            "hinweis": (
                "Custom-Grund ab sofort in stelle_bewerten/stellen_bulk_bewerten "
                "akzeptiert. Mit ablehnungsgrund_aktivieren_setzen(id, False) "
                "deaktivierbar."
            ),
        }

    @mcp.tool()
    def ablehnungsgrund_umbenennen(grund_id: int, neues_label: str) -> dict:
        """Benennt einen Ablehnungsgrund um — z.B. zur Tippfehler-Korrektur (#663 C20).

        beta.92: bereits gespeicherte dismiss_reason-Werte in der jobs-Tabelle
        werden JETZT mit umgeschrieben — ein Tippfehler verschwindet damit
        komplett aus den Daten, statt als Karteileiche zurueckzubleiben.
        Kollidiert das neue Label mit einem bestehenden Grund, werden beide
        zusammengefuehrt (Merge).

        Args:
            grund_id: ID des Grunds (aus ablehnungsgruende_anzeigen)
            neues_label: Neuer Label-Text
        """
        try:
            res = db.rename_dismiss_reason(grund_id, neues_label)
        except ValueError as exc:
            return {"fehler": str(exc)}
        if res.get("status") == "nicht_gefunden":
            return {"fehler": f"Kein Grund mit id={grund_id} gefunden."}
        return {
            "status": res.get("status", "umbenannt"),
            "id": grund_id,
            "neues_label": res.get("label", neues_label),
            "stellen_umgezogen": res.get("reassigned_jobs", 0),
        }

    @mcp.tool()
    def ablehnungsgrund_loeschen(grund_id: int, neu_zuordnen_zu: str = "") -> dict:
        """Loescht einen Ablehnungsgrund (#663 C20, beta.92).

        Wenn der Grund bereits Stellen zugeordnet ist (jobs.dismiss_reason),
        MUSS `neu_zuordnen_zu` einen anderen Grund nennen — diese Stellen
        werden dann darauf umgehaengt, damit keine Stelle ohne gueltigen
        Grund zurueckbleibt. Ohne Verwendung wird direkt geloescht.

        Args:
            grund_id: ID des Grunds (aus ablehnungsgruende_anzeigen)
            neu_zuordnen_zu: Label des Ziel-Grunds fuer betroffene Stellen
                (z.B. 'sonstiges'). Pflicht, wenn der Grund verwendet wird.
        """
        try:
            res = db.delete_dismiss_reason(grund_id, neu_zuordnen_zu or None)
        except ValueError as exc:
            return {"fehler": str(exc)}
        if res.get("status") == "nicht_gefunden":
            return {"fehler": f"Kein Grund mit id={grund_id} gefunden."}
        return {
            "status": "geloescht",
            "id": grund_id,
            "label": res.get("label"),
            "stellen_umgezogen": res.get("reassigned_jobs", 0),
            "neu_zugeordnet_zu": res.get("reassigned_to"),
        }

    @mcp.tool()
    def ablehnungsgrund_aktivieren_setzen(grund_id: int, aktiv: bool) -> dict:
        """Aktiviert/Deaktiviert einen Ablehnungsgrund (#663 C20).

        Deaktivierte Gruende werden nicht mehr in stelle_bewerten akzeptiert
        (Treffer fallen auf 'sonstiges' zurueck), bleiben aber in
        ablehnungsgruende_anzeigen() sichtbar mit `is_active=False` und in
        den Statistiken erhalten.

        Args:
            grund_id: ID des Grunds
            aktiv: True = aktivieren, False = deaktivieren
        """
        changed = db.set_dismiss_reason_active(grund_id, bool(aktiv))
        if not changed:
            return {"fehler": f"Kein Grund mit id={grund_id} gefunden."}
        return {
            "status": "aktualisiert",
            "id": grund_id,
            "is_active": bool(aktiv),
        }
