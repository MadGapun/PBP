"""Scoring-Regler-Service (#169).

Berechnet Scoring-Adjustments basierend auf konfigurierbaren Reglern.
Der Basis-Score kommt aus calculate_score() (Keyword-Matching).
Dieser Service addiert/subtrahiert Punkte fuer:
- Stellentyp (Freelance, Festanstellung, Zeitarbeit, etc.)
- Entfernung (getrennt nach Stellentyp)
- Remote-Anteil
- Gehalt/Rate (Abweichung vom Wunsch)
- Ausschluss-Keywords (nur negativ)
"""

import logging
from typing import Optional

logger = logging.getLogger("bewerbungs_assistent.scoring")


# v1.7.36 (#988): Wie stark waechst der Preis jenseits des Wunschwerts?
# Je Verdopplung ein weiterer Punkt — logarithmisch, weil der Unterschied
# zwischen 30 und 60 km im Alltag groesser ist als zwischen 500 und 530.
# Gedeckelt, damit die Entfernung nicht die ganze Bewertung uebernimmt:
# sie ist ein Preis, kein Ausschluss (#910).
MAX_ENTFERNUNGS_ZUSCHLAG = 6

# v1.7.127 (#1082): die Regler, die den RAHMEN betreffen. Sie ordnen die
# Liste, entscheiden aber nicht ueber das Ausblenden — dieselbe Trennung
# wie Fachwert und Rahmen seit v1.7.117 (#1052).
RAHMEN_DIMENSIONEN = frozenset({"Remote", "Entfernung", "Gehalt/Rate"})

def _entfernungs_zuschlag(distance_km: float, emp_type: str,
                          db) -> tuple[int, int]:
    """Wie viele Punkte kostet die Entfernung ueber dem Wunschwert extra?

    Liefert (Zuschlag, Wunschwert). Ohne Wunschwert gilt der Standard des
    Stellentyps; ohne Ueberschreitung ist der Zuschlag 0.

    Der Wunschwert stand bis v1.7.36 in den Suchkriterien und wirkte in
    dieser Ebene nirgends — die Oberflaeche zeigte 30 km, gerechnet wurde
    gegen die Reglerstufe 999 km. Zwei Einstellungen fuer dieselbe Sache,
    von denen nur eine wirkt, sind eine Fehlerquelle (#988).

    v1.7.100: der Standard kommt aus `entfernung.grenze_km` — hier stand
    eine vierte Tabelle (`STANDARD_WUNSCH`), die #1036 uebersehen hatte.
    """
    import math
    from . import entfernung as _entfernung
    try:
        kriterien = db.get_search_criteria() or {}
    except Exception:  # pragma: no cover — Regler duerfen nie stoppen
        kriterien = {}
    wunsch = _entfernung.grenze_km(kriterien, emp_type)
    try:
        wunsch = int(wunsch)
    except (TypeError, ValueError):
        return 0, 0
    if wunsch <= 0 or distance_km <= wunsch:
        return 0, wunsch
    verdopplungen = math.log2(distance_km / wunsch)
    return min(MAX_ENTFERNUNGS_ZUSCHLAG, int(verdopplungen)), wunsch


def apply_scoring_adjustments(job: dict, base_score: int, db) -> dict:
    """Wende Scoring-Regler auf den Basis-Score an.

    Returns dict with:
        - final_score: Der finale Score nach allen Adjustments
        - adjustments: Liste der einzelnen Anpassungen
        - ignored: True wenn die Stelle komplett ignoriert werden soll
    """
    config = db.get_scoring_config()
    if not config:
        return {"final_score": base_score, "adjustments": [], "ignored": False}

    # Build lookup: (dimension, sub_key) -> {value, ignore_flag}
    cfg = {}
    for c in config:
        key = (c["dimension"], c["sub_key"])
        cfg[key] = {"value": c["value"] or 0, "ignore": bool(c.get("ignore_flag"))}

    adjustments = []
    total_adj = 0
    ignored = False

    # 1. Stellentyp
    emp_type = (job.get("employment_type") or "festanstellung").lower()
    type_key = ("stellentyp", emp_type)
    if type_key in cfg:
        entry = cfg[type_key]
        if entry["ignore"]:
            ignored = True
            adjustments.append({"dimension": "Stellentyp", "detail": emp_type,
                                "punkte": 0, "aktion": "IGNORIERT"})
        elif entry["value"] != 0:
            total_adj += entry["value"]
            adjustments.append({"dimension": "Stellentyp", "detail": emp_type,
                                "punkte": entry["value"]})

    # 2. Remote
    remote = (job.get("remote_level") or "unbekannt").lower()
    remote_key = ("remote", remote)
    if remote_key in cfg:
        entry = cfg[remote_key]
        if entry["ignore"]:
            ignored = True
            adjustments.append({"dimension": "Remote", "detail": remote,
                                "punkte": 0, "aktion": "IGNORIERT"})
        elif entry["value"] != 0:
            total_adj += entry["value"]
            adjustments.append({"dimension": "Remote", "detail": remote,
                                "punkte": entry["value"]})

    # 3. Entfernung (getrennt nach Stellentyp)
    # v1.7.94 (#950 AK 6): die Fahrstrecke, sobald sie vorliegt — die
    # Wahl trifft `entfernung.preis_km`, nicht jeder Rechenweg selbst.
    from . import entfernung as _entfernung
    try:
        _kriterien = db.get_search_criteria() or {}
    except Exception:  # pragma: no cover — Regler duerfen nie stoppen
        _kriterien = {}
    # v1.7.100 (#1037): ohne Routing-Schluessel die Luftlinie.
    # v1.7.127 (#1082 AK 3): ein naeherer Standort aus der Anzeige zaehlt
    # auch hier — sonst rechneten Regler und Rahmendaumen verschieden.
    try:
        if _kriterien.get("standort_lat") and _kriterien.get("standort_lon"):
            from . import standorte as _standorte
            _orte = _standorte.verzeichnis(db)
            if _orte:
                _kriterien = dict(_kriterien, _standorte=_orte)
    except Exception:  # pragma: no cover
        pass
    distance_km = _entfernung.preis_km(job, _kriterien)
    if distance_km is not None and distance_km > 0:
        if emp_type == "freelance":
            dim = "entfernung_freelance"
        else:
            dim = "entfernung_fest"

        # Find the matching distance bracket
        # v1.7.0-beta.81 (#661): Bracket-Key kann historisch als '50km'
        # statt '50' gespeichert sein — int('50km') wuerde crashen. Robust
        # parsen: nur Ziffern extrahieren, alles ohne Ziffern wird verworfen.
        def _parse_bracket(raw) -> int | None:
            if isinstance(raw, (int, float)):
                return int(raw)
            if not isinstance(raw, str):
                return None
            digits = "".join(ch for ch in raw if ch.isdigit())
            return int(digits) if digits else None

        brackets_raw = []
        for k, v in cfg.items():
            if k[0] != dim:
                continue
            parsed = _parse_bracket(k[1])
            if parsed is not None:
                brackets_raw.append((parsed, v))
        brackets = sorted(brackets_raw, key=lambda x: x[0])
        # v1.7.36 (#988, beim Testen gefunden): jenseits der obersten
        # Stufe traf GAR KEINE Stufe mehr — eine Stelle in 1200 km kostete
        # damit 0 Punkte, eine in 577 km vier. Die oberste Stufe ist ein
        # Auffangbecken, kein Fenster: was darueber liegt, faellt in sie.
        if brackets and distance_km > brackets[-1][0]:
            brackets = brackets + [(distance_km, brackets[-1][1])]
        for bracket_km, entry in brackets:
            if distance_km <= bracket_km:
                if entry["value"] != 0:
                    punkte = entry["value"]
                    detail = f"{distance_km:.0f}km (Grenze: {bracket_km}km, {emp_type})"
                    # v1.7.36 (#988): der Wunschwert aus den Suchkriterien
                    # wirkt hier mit. Vorher war die oberste Stufe ein
                    # Deckel: 87 km und 577 km kosteten beide 4 Punkte,
                    # bei einer Skala, auf der ein MUSS-Treffer 7 bringt.
                    # Eine Stelle am anderen Ende der Republik war damit
                    # so teuer wie eine im Nachbarkreis.
                    zuschlag, wunsch = _entfernungs_zuschlag(
                        distance_km, emp_type, db)
                    if punkte < 0 and zuschlag:
                        punkte -= zuschlag
                    if wunsch:
                        detail = (f"{distance_km:.0f}km (Wunsch: {wunsch}km, "
                                  f"Stufe: {bracket_km}km, {emp_type})")
                    # v1.7.17 (#910): echter Verdienst ueber Wunsch
                    # reduziert den Bracket-Malus anteilig — dieselbe
                    # Logik wie calculate_score/fit_analyse.
                    if punkte < 0:
                        try:
                            from ..job_scraper import (
                                entfernungs_kompensationsgrad)
                            _krit = db.get_search_criteria()
                            _grad = entfernungs_kompensationsgrad(job, _krit)
                        except Exception:
                            _grad = 0.0
                        if _grad > 0:
                            punkte = round(punkte * (1 - _grad), 1)
                            detail += (f" — Malus durch Gehalt kompensiert "
                                       f"({int(_grad * 100)} %, #910)")
                    total_adj += punkte
                    adjustments.append({
                        "dimension": "Entfernung",
                        "detail": detail,
                        "punkte": punkte
                    })
                break

    # 4. Gehalt (pro 10% Abweichung)
    # v1.6.7 (#552): Geschaetzte Gehaelter bekamen einen 0.5x-Multiplikator.
    # v1.7.12 (#827, C32): Schaetzungen zaehlen jetzt GAR NICHT mehr.
    # Begruendung (belegter Fall): 14 von 29 Stellen eines Laufs trugen
    # exakt eine von vier schematischen Spannen — ein Servicetechniker
    # dieselbe wie ein Category Planner. Das ist keine Information ueber
    # die Stelle, sondern ueber die Schaetzlogik; bei der Dimension mit
    # dem hoechsten Gewicht ist auch die Haelfte davon Scheingenauigkeit.
    # Echte Angaben aus der Anzeige zaehlen unveraendert; der transparente
    # 0-Punkte-Eintrag erklaert, warum die Dimension leer bleibt.
    gehalt_cfg = cfg.get(("gehalt", "pro_10_prozent"))
    if gehalt_cfg and gehalt_cfg["value"] != 0:
        salary_min = job.get("salary_min")
        salary_estimated = bool(job.get("salary_estimated"))
        if salary_estimated and salary_min:
            adjustments.append({
                "dimension": "Gehalt/Rate",
                "detail": "nur Schätzung vorhanden — neutral (#827)",
                "punkte": 0,
                "source": "geschaetzt",
            })
            salary_min = None  # Block unten ueberspringen
        gehalt_multiplikator = 1.0
        if salary_min:
            # Get user preferences for salary
            criteria = db.get_search_criteria()
            salary_type = job.get("salary_type", "jaehrlich")
            # v1.7.17 (#920): Stundensaetze auf Tagessatz-Basis normieren,
            # bevor der Freelance-Zweig sie als EUR/Tag fehlinterpretiert.
            if salary_type == "stuendlich":
                _pref_h = criteria.get("min_stundensatz", 0) or 0
                if isinstance(_pref_h, (int, float)) and _pref_h > 0:
                    pct_diff = (salary_min - _pref_h) / _pref_h * 100
                    points = round(pct_diff / 10) * gehalt_cfg["value"]
                    points = max(-5, min(5, points))
                    if points != 0:
                        total_adj += points
                        adjustments.append({
                            "dimension": "Gehalt/Rate",
                            "detail": (f"{pct_diff:+.0f}% vom Wunsch "
                                       f"({salary_min} EUR/Std)"),
                            "punkte": points,
                            "source": "extrahiert",
                        })
                    salary_min = None  # unten nicht nochmal als Tagessatz
                else:
                    salary_min = salary_min * 8  # Tagessatz-Aequivalent
            if salary_min and (salary_type in ("taeglich", "stuendlich")
                               or emp_type == "freelance"):
                pref = criteria.get("min_tagessatz", 0)
                if isinstance(pref, (int, float)) and pref > 0:
                    pct_diff = (salary_min - pref) / pref * 100
                    points = round(pct_diff / 10) * gehalt_cfg["value"] * gehalt_multiplikator
                    points = max(-5, min(5, points))  # Cap
                    if points != 0:
                        total_adj += points
                        detail = f"{pct_diff:+.0f}% vom Wunsch"
                        if salary_estimated:
                            detail += " (geschaetzt, 0.5x)"
                        adjustments.append({
                            "dimension": "Gehalt/Rate",
                            "detail": detail,
                            "punkte": points,
                            "source": "geschaetzt" if salary_estimated else "extrahiert",
                        })
            elif salary_min:
                pref = criteria.get("min_gehalt", 0)
                if isinstance(pref, (int, float)) and pref > 0:
                    pct_diff = (salary_min - pref) / pref * 100
                    points = round(pct_diff / 10) * gehalt_cfg["value"] * gehalt_multiplikator
                    points = max(-5, min(5, points))
                    if points != 0:
                        total_adj += points
                        detail = f"{pct_diff:+.0f}% vom Wunsch"
                        if salary_estimated:
                            detail += " (geschaetzt, 0.5x)"
                        adjustments.append({
                            "dimension": "Gehalt/Rate",
                            "detail": detail,
                            "punkte": points,
                            "source": "geschaetzt" if salary_estimated else "extrahiert",
                        })

    # 5. Ausschluss-Keywords (nur negativ, #169)
    # v1.7.23 (#944): `.get(key, "")` liefert None, wenn der Schluessel
    # MIT dem Wert None existiert — genau so kommen Stellen ohne
    # Beschreibung aus der Serialisierung. None[:500] stuerzt ab und
    # haette den Bericht mitgerissen, sobald er die Regler anwendet.
    job_text = (f"{job.get('title') or ''} "
                f"{(job.get('description') or '')[:500]}").lower()
    keyword_entries = [(k, v) for k, v in cfg.items() if k[0] == "keyword"]
    for (_, kw), entry in keyword_entries:
        if kw.lower() in job_text:
            if entry["ignore"]:
                ignored = True
                adjustments.append({"dimension": "Keyword", "detail": kw,
                                    "punkte": 0, "aktion": "IGNORIERT"})
            elif entry["value"] != 0:
                total_adj += entry["value"]
                adjustments.append({"dimension": "Keyword", "detail": kw,
                                    "punkte": entry["value"]})

    # 6. Muss-Kriterien (nur positiv, #169)
    muss_entries = [(k, v) for k, v in cfg.items() if k[0] == "muss_kriterium"]
    for (_, kw), entry in muss_entries:
        if kw.lower() in job_text and entry["value"] > 0:
            total_adj += entry["value"]
            adjustments.append({"dimension": "Muss-Kriterium", "detail": kw,
                                "punkte": entry["value"]})

    # 7. Beworben-Bonus: +5 wenn der User sich auf diese Stelle beworben hat (#178)
    job_hash = job.get("hash") or job.get("job_hash", "")
    if job_hash:
        try:
            apps = db.get_applications()
            applied_hashes = {a.get("job_hash") for a in apps if a.get("job_hash")}
            if job_hash in applied_hashes:
                bonus = 5
                total_adj += bonus
                adjustments.append({"dimension": "Beworben-Bonus", "detail": "Bewerbung vorhanden",
                                    "punkte": bonus})
        except Exception:
            pass

    # 8. Auto-Ignore Schwellenwert
    # v1.7.95 (#1035): auf eine Nachkommastelle. 11,2 ist binaer nicht
    # exakt darstellbar; nach einem Abzug von 2 stand `9.199999999999999`
    # auf der Stellenkarte. Gerundet wurden nur einzelne Posten, nie die
    # Summe — und die geht an alle Aufrufer.
    #
    # v1.7.127 (#1082): der Rahmen ordnet, er blendet nicht aus. Seit
    # v1.7.117 ist der Score der Fachwert, und Entfernung, Remote und
    # Gehalt stehen als Rahmen daneben. Hier liefen sie trotzdem in die
    # Zahl, gegen die die Schwelle vergleicht — und eine Stelle mit
    # Fachwert 41,8 in 450 km verschwand unter der Schwelle, fachlich
    # der staerkste Treffer des Bestands. Die Regler behalten ihre
    # Wirkung auf die REIHENFOLGE (sonst waeren sie Einstellungen ohne
    # Wirkung, #988); ueber das Ausblenden entscheidet nur, was die
    # Stelle fachlich ist. Das ist auch die Skala, auf der die Stufen
    # aus #1063 gerechnet werden.
    rahmen_adj = sum(a.get("punkte") or 0 for a in adjustments
                     if a.get("dimension") in RAHMEN_DIMENSIONEN)
    for a in adjustments:
        if a.get("dimension") in RAHMEN_DIMENSIONEN:
            a["rahmen"] = True
    final_score = round(base_score + total_adj, 1)
    fach_score = round(base_score + total_adj - rahmen_adj, 1)
    # v1.7.127: die Schwelle kommt aus dem Nadeloehr — mit gewaehlter
    # Stufe die Stufe (#1063). Bis hierher las die Liste die rohe Zahl
    # aus der Regler-Tabelle, und die Stufe wirkte nur in der Anzeige.
    try:
        threshold = float(db.get_scoring_threshold() or 0)
    except Exception:  # pragma: no cover — Testdoppel ohne Nadeloehr
        threshold = cfg.get(("schwellenwert", "auto_ignore"), {}).get("value", 0)

    unter_schwelle = False
    if not ignored and threshold and fach_score < threshold:
        ignored = True
        unter_schwelle = True
        adjustments.append({
            "dimension": "Schwellenwert",
            "detail": (f"Fachwert {fach_score} < Schwelle {threshold} "
                       "(Entfernung, Remote und Gehalt zählen hier nicht)"),
            "punkte": 0,
            "aktion": "AUTO-IGNORIERT"
        })

    # v1.7.127 (#1082): keine Kappung bei 0. Eine Stelle bei -8 darf
    # nicht aussehen wie eine bei 0 — dieselbe Regel wie beim Fachwert
    # seit v1.7.117 (#1052), hier war sie stehen geblieben.
    return {
        "final_score": final_score,
        "fach_score": fach_score,
        "rahmen_adjustment": round(rahmen_adj, 1),
        "unter_schwelle": unter_schwelle,
        # #1082 AK 4: haette die ALTE Regel (Schwelle gegen den Wert samt
        # Rahmen) diese Stelle verborgen? Nur fuer die Auskunft.
        "nur_durch_rahmen_unter_schwelle": bool(
            not ignored and threshold and final_score < threshold
            and fach_score >= threshold),
        "adjustments": adjustments,
        "ignored": ignored,
        "basis_score": base_score,
        "adjustment_total": total_adj,
    }
