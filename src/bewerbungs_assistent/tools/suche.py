"""Suchkriterien und Blacklist-Verwaltung — 6 Tools

#559 blacklist_anwenden, #992 blacklist_wirkung.
"""

from ..services import blacklist_regel
from ..services.nutzerfuehrung import leer

# v1.7.12 (#828, C33) / v1.7.41 (#992): die Wortliste liegt jetzt im
# Nadeloehr, weil sie drei Aufrufer hat — der Hinweis beim Anlegen, die
# Bestandspruefung und die Blockade-Auskunft.
_KATEGORIEN_WOERTER = blacklist_regel.KATEGORIEN_WOERTER


def _entfernung_widerspruch(kriterien: dict):
    """Steht ein Entfernungswunsch da, gegen den niemand rechnet? (#1000)

    Bis v1.7.47 nahm `suchkriterien_setzen` keinen Einzelwert entgegen —
    das Frontend schrieb `max_entfernung_km` trotzdem in die Kriterien,
    gelesen wurde allein die Karte `max_entfernung` je Stellenart.
    Gemessen am 08.09.2026 im echten Bestand: `max_entfernung_km` stand
    auf 30, `max_entfernung.freelance` auf 1500.

    Solche Altwerte werden BENANNT statt still umgedeutet — dasselbe
    Vorgehen wie bei den wirkungslosen Scoring-Reglern aus #988. Eine
    stille Neudeutung waere eine Aenderung am Score, die niemand
    veranlasst hat.
    """
    einzel = kriterien.get("max_entfernung_km")
    karte = kriterien.get("max_entfernung") or {}
    if einzel in (None, "", 0) or not karte:
        return None
    abweichend = {art: km for art, km in karte.items()
                  if float(km or 0) != float(einzel)}
    if not abweichend:
        return None
    paare = ", ".join(f"{art} {km:g} km" for art, km in abweichend.items())
    return (
        f"In den Kriterien steht max_entfernung_km = {float(einzel):g}, "
        f"gerechnet wird aber je Stellenart: {paare}. Der Einzelwert "
        "hatte bis v1.7.47 gar keinen Leser. Setze ihn mit "
        "suchkriterien_setzen(max_entfernung_km=...) neu, dann gilt er "
        "fuer alle Stellenarten — oder nutze max_entfernung, wenn die "
        "Unterschiede Absicht sind."
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
        "blacklist_verwalten('aendern', entry_id=..., grund=...). "
        # v1.7.41 (#992): der Hinweis auf die Ausnahme kam bisher erst,
        # wenn eine Stelle schon abgewiesen war — also im schlechtest-
        # moeglichen Moment. Personaldienstleister und Beratungen
        # schreiben quer durch alle Fachgebiete aus; ein pauschaler Block
        # wirft dort zwangslaeufig auch die passenden Rollen weg.
        "Und wenn die Gattung wirklich der Grund ist: blocke die Firma, "
        "aber lass deine Fachrollen durch — "
        "blacklist_verwalten('aendern', entry_id=..., "
        "ausser_wenn_titel_enthaelt=['<dein MUSS-Begriff>'])."
    )


def _muss_kollisionen(db, wert: str, typ: str, limit: int = 5):
    """Wuerde dieser Eintrag Stellen mit MUSS-Begriffen wegwerfen? (#992)

    Der maschinell erkennbare Widerspruch, und er gehoert in den Moment
    des Anlegens: "das suche ich" und "das will ich nicht" ueber derselben
    Stelle. Geprueft wird gegen den bekannten Bestand — aktive wie
    aussortierte Stellen, denn gerade die aussortierten sind ja der
    Anlass fuer den Eintrag.
    """
    try:
        kriterien = db.get_search_criteria() or {}
        if not (kriterien.get("keywords_muss") or []):
            return []
        w = (wert or "").strip().lower()
        if not w:
            return []
        bestand = list(db.get_active_jobs()) + list(db.get_dismissed_jobs())
    except Exception:
        return []
    out, gesehen = [], set()
    for j in bestand:
        firma = (j.get("company") or "").lower()
        titel = j.get("title") or ""
        if typ == "firma":
            passt = bool(firma) and (w in firma or firma in w)
        else:
            passt = w in titel.lower() or w in firma
        if not passt:
            continue
        begriffe = blacklist_regel.muss_treffer(titel, kriterien)
        if not begriffe or titel.lower() in gesehen:
            continue
        gesehen.add(titel.lower())
        out.append({"titel": titel, "firma": j.get("company"),
                    "muss_begriffe": begriffe})
        if len(out) >= limit:
            break
    return out


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
        max_entfernung_km: float = None,
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
            max_entfernung_km: EINE Zahl fuer alle Stellentypen (#1000) —
                der einfache Weg, wenn kein Unterschied noetig ist.
                Ein Mensch sagt "hoechstens 30 km", nicht eine Karte je
                Stellenart. Wird in `max_entfernung` uebersetzt und wirkt
                damit ueberall, wo gerechnet wird. Wer BEIDES angibt,
                bekommt `max_entfernung` — das ist der genauere Wunsch.
                Hintergrund: dieses Feld stand vorher in den Kriterien
                und hatte KEINEN Leser; gerechnet wurde allein gegen die
                Karte.
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
        # #1000: eine Zahl fuer alle Stellentypen. Die Karte gewinnt,
        # wenn beides kommt — sie ist der genauere Wunsch.
        entfernung_hinweis = None
        if max_entfernung_km is not None and max_entfernung is None:
            arten = (stellentypen
                     or db.get_search_criteria().get("stellentypen")
                     or ["festanstellung", "freelance", "teilzeit",
                         "praktikum", "werkstudent"])
            max_entfernung = {a: float(max_entfernung_km) for a in arten}
            entfernung_hinweis = (
                f"{max_entfernung_km:g} km gilt jetzt fuer "
                f"{', '.join(arten)}. Entfernung ist ein Preis im Score, "
                "kein Ausschluss (#910/#988): eine weitere Stelle rutscht "
                "nach unten, statt zu verschwinden."
            )
        elif max_entfernung_km is not None and max_entfernung is not None:
            entfernung_hinweis = (
                "max_entfernung_km wurde ignoriert — die Karte "
                "max_entfernung ist der genauere Wunsch und gewinnt."
            )
        if max_entfernung is not None:
            db.set_search_criteria("max_entfernung", max_entfernung)
            # Den frueher toten Einzelwert nicht als Leiche stehen
            # lassen: er wird mitgezogen, damit Anzeige und Rechnung
            # nicht auseinanderlaufen (#1000).
            werte = set(max_entfernung.values())
            db.set_search_criteria(
                "max_entfernung_km",
                float(next(iter(werte))) if len(werte) == 1 else None)
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
        if entfernung_hinweis:
            result["entfernung"] = entfernung_hinweis
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
        kriterien = db.get_search_criteria()
        # v1.7.21 (#927): Ein leeres {} war die haeufigste Sackgasse
        # ueberhaupt — die Suchkriterien sind die Grundlage JEDER
        # Jobsuche, und der Nutzer erfuhr nicht, dass sie fehlen.
        if not kriterien:
            return leer(
                {"kriterien": {}},
                "Es sind noch keine Suchkriterien gesetzt — ohne sie "
                "findet die Jobsuche nichts Passendes.",
                "Vorschlaege aus deinem Profil bekommst du mit "
                "keyword_vorschlaege(); setzen kannst du sie mit "
                "suchkriterien_setzen(keywords_muss=[...]). MUSS-Begriffe "
                "muessen in der Anzeige vorkommen, PLUS-Begriffe "
                "verbessern nur die Reihenfolge.")
        antwort = {"kriterien": kriterien}
        hinweis = _entfernung_widerspruch(kriterien)
        if hinweis:
            antwort["hinweis_entfernung"] = hinweis
        return antwort

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
        - 'firma': Firmen die IMMER ignoriert werden (z.B. Musterfirma, Zeitarbeitsfirma XY)
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
            # v1.7.41 (#992): der harte, maschinell erkennbare Widerspruch.
            # Ein Eintrag, der Titel mit den eigenen MUSS-Begriffen
            # wegwirft, sagt zwei Dinge gleichzeitig — das gehoert gesagt,
            # bevor der Filter still zu arbeiten beginnt.
            kollisionen = _muss_kollisionen(db, wert.strip(), typ)
            if kollisionen and not ausnahmen:
                begriffe = sorted({b for k in kollisionen
                                   for b in k["muss_begriffe"]})
                result["muss_kollisionen"] = kollisionen
                result["warnung_muss"] = (
                    f"Dieser Eintrag betrifft {len(kollisionen)} bekannte "
                    "Stelle(n), deren Titel deine MUSS-Begriffe enthaelt "
                    f"({', '.join(begriffe)}). Kuenftige Treffer dieser Art "
                    "werden ab jetzt still verworfen. Wenn das nicht "
                    "gewollt ist, setz eine Ausnahme: "
                    f"blacklist_verwalten('aendern', entry_id={neu_id}, "
                    f"ausser_wenn_titel_enthaelt={begriffe!r})."
                )
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

        # v1.7.11 (#790/C31): Titel-Ausnahmen je Firmen-Eintrag. Ohne das
        # entfernt ein retroaktiver Lauf genau die passenden Stellen wieder,
        # die die Ausnahme beim Anlegen durchgelassen hat.
        # v1.7.41 (#992/C52): ueber das Nadeloehr statt eigener Fassung.
        verschont = []
        matched = []
        for j in active:
            _rettung = blacklist_regel.verschont(
                bl_entries, j.get("company") or "", j.get("title") or "")
            if _rettung:
                verschont.append({
                    "hash": j.get("hash"), "titel": j.get("title"),
                    "firma": j.get("company"),
                    "ausnahme_begriff": _rettung["begriff"],
                })
            hit = blacklist_regel.treffer(
                bl_entries, j.get("company") or "", j.get("title") or "")
            if hit:
                matched.append({
                    "job": j,
                    "trigger": hit["typ"],
                    "wert": (hit["wert"] or "").lower(),
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
            res = {
                "dry_run": True,
                "betroffen": len(matched),
                "vorschau": preview,
                "hinweis": (
                    f"{len(matched)} aktive Stelle(n) wuerden aussortiert. "
                    "Erneut mit dry_run=False aufrufen, um sie zu deaktivieren."
                ),
            }
            # v1.7.41 (#992): die verschonten Stellen standen bisher NUR im
            # Zweig "kein Treffer" — sobald irgendeine andere Stelle passte,
            # verschwand die Auskunft darueber, was die Ausnahme gerettet
            # hat. Sichtbar ist sie damit genau dann nicht, wenn es
            # interessant wird.
            if verschont:
                res["durch_ausnahme_verschont"] = verschont
            return res

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
        res = {
            "dry_run": False,
            "deaktiviert": deaktiviert,
            "betroffene_firmen": dict(sorted(firmen_betroffen.items(), key=lambda x: -x[1])[:10]),
        }
        if verschont:
            res["durch_ausnahme_verschont"] = verschont
        return res

    @mcp.tool()
    def blacklist_wirkung(limit: int = 30, nur_auffaellige: bool = False) -> dict:
        """Was wirft deine Blacklist gerade weg — und ist das noch richtig? (#992)

        Ein Filter, dessen Wirkung niemand sehen kann, laesst sich nicht
        ueberpruefen. Man weiss nicht, ob er richtig arbeitet, und man
        merkt nicht, wenn seine Begruendung veraltet ist. Genau das ist
        am 07.09.2026 passiert: eine fachlich passende Stelle wurde von
        einem Eintrag geblockt, dessen Begruendung aus einer Zeit stammte,
        in der von dieser Firma nur unpassende Rollen kamen.

        Dieses Werkzeug beantwortet drei Fragen auf einmal:

        1. **Welche Stellen hat die Blacklist verworfen?** Seit v1.7.41
           protokolliert PBP jede Blockade — aus dem Suchlauf, beim
           Anlegen von Hand und ueber Plugins.
        2. **Widerspricht ein Eintrag den eigenen Suchkriterien?** Ein
           Eintrag, der Titel mit MUSS-Begriffen wegwirft, sagt zwei
           Dinge gleichzeitig. Das ist maschinell erkennbar und steht
           deshalb ganz oben.
        3. **Ist die Begruendung noch tragfaehig?** Gattungsurteile
           ("Zeitarbeit", "Consulting") beschreiben keine Firma, sondern
           eine Annahme; mit Alter wird daraus eine Vermutung mit Datum.

        Der uebliche Ausweg ist nicht Loeschen, sondern eine Ausnahme:
        `blacklist_verwalten('aendern', entry_id=..., ausser_wenn_titel_
        enthaelt=['PLM'])` haelt die Firma draussen und laesst die
        Fachrollen durch.

        Args:
            limit: wie viele protokollierte Blockaden gelesen werden.
            nur_auffaellige: True zeigt nur Eintraege mit Befund
                (MUSS-Kollision, Gattungsurteil ohne Ausnahme, fehlende
                Begruendung).
        """
        eintraege = db.get_blacklist(include_inactive=True)
        if not eintraege:
            return leer(
                {"status": "leer", "eintraege": [], "eintraege_gesamt": 0},
                "Die Blacklist ist leer — es wird nichts weggefiltert.",
                "Firmen oder Begriffe sperren: "
                "blacklist_verwalten('hinzufuegen', 'firma', '...').")

        try:
            kriterien = db.get_search_criteria() or {}
        except Exception:
            kriterien = {}
        blockaden = db.get_blacklist_blocks(limit=max(1, int(limit)))
        eintrags_befund = blacklist_regel.befund(eintraege, kriterien, blockaden)

        auffaellig = [e for e in eintrags_befund
                      if e["muss_kollisionen"]
                      or (e["gattungswoerter"] and not e["ausser_wenn_titel_enthaelt"])
                      or not e["grund"].strip()]

        letzte = [{
            "titel": b.get("titel"), "firma": b.get("firma"),
            "geblockt_durch": b.get("eintrag_wert"), "typ": b.get("typ"),
            "kontext": b.get("kontext"), "am": b.get("blockiert_am"),
            "muss_begriffe": blacklist_regel.muss_treffer(
                b.get("titel") or "", kriterien),
        } for b in blockaden]

        ergebnis = {
            "status": "ok",
            "eintraege_gesamt": len(eintraege),
            "eintraege": auffaellig if nur_auffaellige else eintrags_befund,
            "auffaellige_eintraege": len(auffaellig),
            "geblockt_protokolliert": len(blockaden),
            "geblockt_mit_muss_begriff": len([x for x in letzte
                                              if x["muss_begriffe"]]),
            "letzte_blockaden": letzte,
        }
        if not blockaden:
            ergebnis["hinweis_protokoll"] = (
                "Noch keine Blockade protokolliert. Das Protokoll beginnt "
                "mit v1.7.41 — aeltere Blockaden sind nicht rekonstruierbar, "
                "weil sie nie irgendwo standen. Nach dem naechsten Suchlauf "
                "steht hier, was der Filter tatsaechlich wegwirft."
            )
        # Die Zahl oben ist Protokoll, also Vergangenheit. Gewarnt wird
        # nur ueber das, was HEUTE noch blockt — sonst ermahnt PBP jemanden
        # fuer ein Problem, das er schon geloest hat.
        offen = sum(len(e["muss_kollisionen"]) for e in eintrags_befund)
        behoben = sum(e.get("muss_kollisionen_behoben", 0)
                      for e in eintrags_befund)
        ergebnis["muss_kollisionen_offen"] = offen
        if offen:
            ergebnis["warnung"] = (
                f"{offen} verworfene Stelle(n) tragen einen deiner "
                "MUSS-Begriffe im Titel und wuerden auch jetzt wieder "
                "verworfen. Das ist der Widerspruch aus #992 — sieh dir "
                "die betroffenen Eintraege an."
            )
        elif behoben:
            ergebnis["hinweis_behoben"] = (
                f"{behoben} frueher verworfene Stelle(n) mit MUSS-Begriff "
                "kaemen inzwischen durch — die Ausnahme wirkt."
            )
        return ergebnis

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
        if not items:
            return leer(
                {"profile": [], "anzahl": 0},
                "Noch keine Suchprofile angelegt.",
                "Ein Suchprofil buendelt Suchbegriffe und Quellen fuer "
                "eine Richtung — etwa 'Festanstellung in der Naehe' und "
                "'Freelance bundesweit' getrennt. Wer nur eine Richtung "
                "verfolgt, braucht das nicht: die normalen "
                "Suchkriterien reichen.")
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
