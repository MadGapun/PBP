"""Duplikat-Erkennung fuer Stellen (#471).

Haertet die Duplikat-Pruefung in stelle_manuell_anlegen gegen:
- Firma mit Klammer-Zusaetzen (z.B. "VirtoTech Ltd." vs. "VirtoTech Ltd. (Endkunde: Rota Yokogawa)")
- Rechtsform-Suffixe (GmbH, AG, Ltd., KG, ...)
- Titel-Umformulierungen mit gleichem Fachbereich
- Zeitnaehe als zusaetzliches Signal
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import Iterable, Optional

# Rechtsform-Suffixe die beim Vergleich ignoriert werden
_LEGAL_SUFFIXES = (
    "gmbh & co. kg", "gmbh & co kg", "gmbh + co kg",
    "ag & co kg", "ag + co kg",
    "gmbh", "ag", "kg", "ohg", "ug", "se",
    "ltd.", "ltd", "limited",
    "inc.", "inc", "llc", "plc",
    "e.v.", "ev", "e. v.",
    "co.", "co", "corp.", "corp",
    "holding", "group", "gruppe",
)

# Domaenen-Keywords: markieren den Fachbereich. v1.7.0-beta.87 (#670):
# NICHT mehr als Standalone-Trigger — nur noch als Bonus in der Titel-
# Aehnlichkeit (_title_similarity). Ein einzelnes geteiltes "PLM" macht
# zwei sonst verschiedene Stellen NICHT zu Duplikaten.
_DOMAIN_KEYWORDS = {
    "plm", "sap", "erp", "cad", "pdm", "ecm", "dms",
    "devops", "sre", "mlops", "qa",
    "teamcenter", "windchill", "aras", "enovia", "3dexperience",
    "solidworks", "catia", "nx", "inventor",
}

# v1.7.0-beta.87 (#670): Schwellwerte fuer die Duplikat-Entscheidung.
# Die Titel-Aehnlichkeit (inkl. Domain-Keyword-Bonus) muss diesen Wert
# erreichen, sonst KEIN Duplikat. Bloße Zeitnaehe oder ein einzelnes
# geteiltes Keyword reichen NICHT mehr.
_TITLE_DUP_THRESHOLD = 0.5
# Unterschiedliche URLs sind ein starkes "verschiedene Stellen"-Signal —
# dann nur bei nahezu identischem Titel als Duplikat werten.
_TITLE_DUP_THRESHOLD_DIFF_URL = 0.85


def normalize_company_name(name: Optional[str]) -> str:
    """Normalisiere Firmennamen fuer Vergleich.

    - lowercase
    - Inhalt in runden Klammern entfernen
    - Rechtsform-Suffixe abschneiden (GmbH, Ltd., ...)
    - Umlaute auf ASCII
    - Whitespace und Satzzeichen kollabieren
    """
    if not name:
        return ""
    n = name.lower().strip()
    # Klammer-Zusaetze entfernen: "VirtoTech Ltd. (Endkunde: ...)" -> "virtotech ltd."
    n = re.sub(r"\([^)]*\)", " ", n)
    # Umlaute
    for uml, repl in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        n = n.replace(uml, repl)
    # Rechtsform-Suffixe iterativ abschneiden (von hinten)
    changed = True
    while changed:
        changed = False
        stripped = n.rstrip(" ,.")
        for suffix in _LEGAL_SUFFIXES:
            if stripped.endswith(" " + suffix) or stripped == suffix:
                stripped = stripped[: -len(suffix)].rstrip(" ,.-&+")
                n = stripped
                changed = True
                break
        else:
            n = stripped
    # Satzzeichen -> Leerzeichen, multiple Spaces kollabieren
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


def _title_tokens(title: Optional[str]) -> set[str]:
    """Titel in vergleichbare Tokens zerlegen (ohne Stopwords, ohne Gender-Suffixe)."""
    if not title:
        return set()
    t = title.lower()
    # Gender/Genus Suffixe entfernen
    t = re.sub(r"\(?\s*m\s*[/|]\s*w\s*[/|]?\s*d?\s*\)?", " ", t)
    # Alle Nicht-Wort-Zeichen -> Space
    t = re.sub(r"[^\w\s]", " ", t)
    stop = {
        "und", "oder", "der", "die", "das", "im", "in", "fuer", "für",
        "mit", "von", "zur", "zum", "als", "bei", "auf",
        "via", "for", "and", "or", "the", "a", "an",
        "senior", "junior", "lead", "chief", "principal",
        "m", "w", "d",
    }
    tokens = {w for w in t.split() if len(w) >= 2 and w not in stop}
    return tokens


def _title_similarity(t1: str, t2: str) -> tuple[float, set[str]]:
    """Vergleiche zwei Titel, Rueckgabe (similarity in [0..1], shared tokens).

    Gewichtung: wenn mindestens 1 Domain-Keyword (PLM/SAP/...) gemeinsam ist,
    wirkt das doppelt — sonst waeren zwei PLM-Stellen mit sehr unterschiedlichen
    Titeln nie erkannt.
    """
    a = _title_tokens(t1)
    b = _title_tokens(t2)
    if not a or not b:
        return 0.0, set()
    common = a & b
    if not common:
        return 0.0, set()
    # Jaccard mit Domain-Keyword-Bonus
    jaccard = len(common) / len(a | b)
    domain_hits = common & _DOMAIN_KEYWORDS
    if domain_hits:
        jaccard = min(1.0, jaccard + 0.2 * len(domain_hits))
    return jaccard, common


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    """Parse ISO-Timestamp und gib IMMER ein tz-aware datetime zurueck (#565).

    Wenn der Timestamp keine Timezone-Info hat (Legacy-Eintraege), nehmen wir
    UTC an — sonst crasht jede spaetere Subtraktion mit `datetime.now(UTC)`.
    """
    if not ts:
        return None
    try:
        from datetime import timezone
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def find_duplicate_job(
    firma: str,
    titel: str,
    url: str,
    candidates: Iterable[dict],
    *,
    now: Optional[datetime] = None,
    time_window_hours: int = 72,
) -> Optional[dict]:
    """Sucht den staerksten Duplikat-Kandidaten unter ``candidates``.

    Rueckgabe: {"job": <candidate>, "grund": str, "score": float} oder None.

    Regeln (absteigend nach Staerke):
    1. URL exakt gleich (normalisiert)     -> sicher
    2. Normalisierte Firma gleich + (Titel-Sim >= 0.4 ODER Domain-Keyword-Overlap)
    3. Normalisierte Firma gleich + Zeitnaehe < 72h    (Vorsicht-Warnung)
    """
    if not firma or not titel:
        return None

    norm_firma = normalize_company_name(firma)
    url_norm = (url or "").strip().lower().rstrip("/") if url else ""
    # v1.6.9 (#565, #567): tz-aware now — vorher war das naive und crashte
    # gegen aware found_at-Werte aus der DB.
    from datetime import timezone
    now = now or datetime.now(timezone.utc)

    best: Optional[dict] = None
    best_score = 0.0

    for cand in candidates:
        cand_firma = normalize_company_name(cand.get("company") or cand.get("firma"))
        cand_title = cand.get("title") or cand.get("titel") or ""
        cand_url = (cand.get("url") or "").strip().lower().rstrip("/")

        # 1. URL-Match
        if url_norm and cand_url and url_norm == cand_url:
            return {"job": cand, "grund": "url_match", "score": 1.0}

        # Firma muss normalisiert uebereinstimmen (oder Teilmenge, wenn der
        # kuerzere der Basisname ist — z.B. "virtotech" in "virtotech holding").
        if not norm_firma or not cand_firma:
            continue
        firma_match = (
            norm_firma == cand_firma
            or (len(norm_firma) >= 4 and len(cand_firma) >= 4
                and (norm_firma in cand_firma or cand_firma in norm_firma))
        )
        if not firma_match:
            continue

        # 2. Titel-Aehnlichkeit
        sim, common = _title_similarity(titel, cand_title)

        # 3. Zeitnaehe — NUR Tiebreaker im Ranking, NIE Standalone-Trigger (#670)
        cand_ts = _parse_iso(cand.get("found_at") or cand.get("created_at")
                             or cand.get("applied_at"))
        time_bonus = 0.0
        hours_ago = None
        if cand_ts:
            hours_ago = (now - cand_ts).total_seconds() / 3600
            if 0 <= hours_ago <= time_window_hours:
                time_bonus = 0.3 * (1 - hours_ago / time_window_hours)

        # v1.7.0-beta.87 (#670): Entscheidung allein an der Titel-Aehnlichkeit.
        # Vorher triggerte ein einzelnes geteiltes Domain-Keyword ODER bloße
        # Zeitnaehe (ohne Titel-Overlap) einen harten Block — das machte
        # verschiedene Stellen derselben Firma unsichtbar (PLM Project Manager
        # vs PLM Product Owner). Jetzt: `sim` muss ueber den Schwellwert.
        # Das Domain-Keyword zaehlt nur als Bonus IN `sim` (siehe
        # _title_similarity), Zeitnaehe nur als Ranking-Tiebreaker. Wichtig:
        # der Schwellwert-Vergleich passiert auf `sim` (ohne time_bonus),
        # damit Zeitnaehe einen knappen Nicht-Treffer nicht ueber die Grenze hebt.
        urls_differ = bool(url_norm and cand_url and url_norm != cand_url)
        threshold = _TITLE_DUP_THRESHOLD_DIFF_URL if urls_differ else _TITLE_DUP_THRESHOLD
        if sim < threshold:
            continue

        final_score = sim + time_bonus
        if final_score > best_score:
            grund = (
                "firma_plus_domainkeyword" if (common & _DOMAIN_KEYWORDS)
                else "firma_plus_titel_fuzzy"
            )
            best = {
                "job": cand,
                "grund": grund,
                "score": round(final_score, 2),
                "shared_tokens": sorted(common),
                "hours_ago": round(hours_ago, 1) if hours_ago is not None else None,
            }
            best_score = final_score

    return best
