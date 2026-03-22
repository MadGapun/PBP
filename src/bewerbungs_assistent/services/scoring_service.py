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
    distance_km = job.get("distance_km")
    if distance_km is not None and distance_km > 0:
        if emp_type == "freelance":
            dim = "entfernung_freelance"
        else:
            dim = "entfernung_fest"

        # Find the matching distance bracket
        brackets = sorted(
            [(int(k[1]), v) for k, v in cfg.items() if k[0] == dim],
            key=lambda x: x[0]
        )
        for bracket_km, entry in brackets:
            if distance_km <= bracket_km:
                if entry["value"] != 0:
                    total_adj += entry["value"]
                    adjustments.append({
                        "dimension": "Entfernung",
                        "detail": f"{distance_km:.0f}km (Grenze: {bracket_km}km, {emp_type})",
                        "punkte": entry["value"]
                    })
                break

    # 4. Gehalt (pro 10% Abweichung)
    gehalt_cfg = cfg.get(("gehalt", "pro_10_prozent"))
    if gehalt_cfg and gehalt_cfg["value"] != 0:
        salary_min = job.get("salary_min")
        if salary_min:
            # Get user preferences for salary
            criteria = db.get_search_criteria()
            salary_type = job.get("salary_type", "jaehrlich")
            if salary_type == "taeglich" or emp_type == "freelance":
                pref = criteria.get("min_tagessatz", 0)
                if isinstance(pref, (int, float)) and pref > 0:
                    pct_diff = (salary_min - pref) / pref * 100
                    points = round(pct_diff / 10) * gehalt_cfg["value"]
                    points = max(-5, min(5, points))  # Cap
                    if points != 0:
                        total_adj += points
                        adjustments.append({
                            "dimension": "Gehalt/Rate",
                            "detail": f"{pct_diff:+.0f}% vom Wunsch",
                            "punkte": points
                        })
            else:
                pref = criteria.get("min_gehalt", 0)
                if isinstance(pref, (int, float)) and pref > 0:
                    pct_diff = (salary_min - pref) / pref * 100
                    points = round(pct_diff / 10) * gehalt_cfg["value"]
                    points = max(-5, min(5, points))
                    if points != 0:
                        total_adj += points
                        adjustments.append({
                            "dimension": "Gehalt/Rate",
                            "detail": f"{pct_diff:+.0f}% vom Wunsch",
                            "punkte": points
                        })

    # 5. Ausschluss-Keywords (nur negativ, #169)
    job_text = f"{job.get('title', '')} {job.get('description', '')[:500]}".lower()
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
    final_score = base_score + total_adj
    threshold = cfg.get(("schwellenwert", "auto_ignore"), {}).get("value", 0)

    if not ignored and threshold and final_score < threshold:
        ignored = True
        adjustments.append({
            "dimension": "Schwellenwert",
            "detail": f"Score {final_score} < Schwelle {threshold}",
            "punkte": 0,
            "aktion": "AUTO-IGNORIERT"
        })

    return {
        "final_score": max(0, final_score),
        "adjustments": adjustments,
        "ignored": ignored,
        "basis_score": base_score,
        "adjustment_total": total_adj,
    }
