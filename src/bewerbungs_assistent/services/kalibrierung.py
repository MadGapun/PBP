"""Scoring-Kalibrierung (#778, C29, v1.7.10).

Drei Bausteine:

1. **Schattenrechnung** — `schatten_score()` bewertet eine Stelle mit
   beliebigen Kriterien, OHNE die `jobs`-Tabelle anzufassen. Der Backtest
   arbeitet ausschliesslich damit; `scores_neu_berechnen` wird hier nie
   aufgerufen. Ein Testlauf darf den Live-Stand nicht veraendern.

2. **IDF-Seltenheitsgewichtung** — `berechne_idf_faktoren()` misst je
   Keyword die Dokumentfrequenz im EIGENEN Korpus (alle bisher gesehenen
   Stellen) und normiert auf 0.3–1.0. Hintergrund (Praxis-Fall 24.07.):
   „Digital Transformation" steht in ~50 % aller Anzeigen und zaehlte
   gleich viel wie ein Nischenbegriff mit ~1 % — Masse schlug Klasse,
   220 statt ~10 Stellen pro Tag. Die Faktoren werden in den Settings
   gecacht (Neuberechnung ist ein voller Korpus-Scan).

3. **Backtest** — vergleicht die Score-Verteilung der bewerbungsverknuepften
   Stellen (positive Labels) mit einer Stichprobe der Aussortierten
   (negative Labels) und schlaegt eine Schwelle vor:
   niedrigster Bewerbungs-Score × 0,8 (20-%-Toleranz, User-Vorgabe).
   MERKE: Die Schwelle blendet aus, sie loescht nie — eine Stelle kann
   mit nachgeladener Beschreibung deutlich hoeher springen (belegt:
   43 → 104 → Bewerbung).
"""
from __future__ import annotations

import copy
import json
import math
from datetime import datetime, timedelta
from typing import Any, Optional

IDF_CACHE_KEY = "idf_faktoren_cache"
IDF_CACHE_MAX_ALTER_STUNDEN = 24
IDF_MIN_FAKTOR = 0.3

# Nur die staerksten MUSS-Treffer zaehlen im kalibrierten Modus —
# verhindert, dass viele schwache Treffer einen Fach-Score simulieren.
MUSS_TOP_N = 5


def _statistik(werte: list) -> dict:
    if not werte:
        return {"anzahl": 0}
    s = sorted(werte)
    n = len(s)

    def _quantil(q: float):
        idx = q * (n - 1)
        lo = int(math.floor(idx))
        hi = int(math.ceil(idx))
        if lo == hi:
            return s[lo]
        return round(s[lo] + (s[hi] - s[lo]) * (idx - lo), 1)

    return {
        "anzahl": n,
        "min": s[0],
        "q25": _quantil(0.25),
        "median": _quantil(0.5),
        "q75": _quantil(0.75),
        "max": s[-1],
        "mittel": round(sum(s) / n, 1),
    }


def schatten_score(job: dict, criteria: dict) -> int:
    """Score einer Stelle unter gegebenen Kriterien — ohne Seiteneffekte.

    `calculate_score` setzt Marker-Flags am Job-Dict (z.B. `_ko_ausschluss`);
    deshalb wird auf einer Kopie gerechnet. Es wird nichts persistiert.
    """
    from ..job_scraper import calculate_score
    return int(calculate_score(copy.deepcopy(job), criteria))


def berechne_idf_faktoren(db: Any, criteria: dict) -> dict:
    """Dokumentfrequenz je Keyword ueber den eigenen Stellen-Korpus.

    faktor(kw) = IDF_MIN + (1-IDF_MIN) * log(N/df) / log(N), geklemmt auf
    [IDF_MIN, 1.0]. Ein Begriff, der in jeder zweiten Anzeige steht, zaehlt
    damit deutlich weniger als ein Nischenbegriff. MUSS/PLUS werden mit dem
    fuzzy-Matcher gezaehlt (derselbe, der auch scored), MINUS strikt.
    """
    from ..job_scraper import _fuzzy_keyword_match, _strict_keyword_match

    conn = db.connect()
    pid = db.get_active_profile_id()
    rows = conn.execute(
        "SELECT title, description FROM jobs "
        "WHERE (profile_id=? OR profile_id IS NULL)",
        (pid,),
    ).fetchall()
    texte = [
        f"{r['title'] or ''} {r['description'] or ''}".lower() for r in rows
    ]
    n = len(texte)
    if n < 50:
        # Zu wenig Korpus fuer belastbare Frequenzen — lieber neutral
        # bleiben als aus 20 Stellen Seltenheit zu raten.
        return {}

    faktoren: dict[str, float] = {}
    log_n = math.log(n)
    kandidaten = [
        (kw, _fuzzy_keyword_match)
        for kw in (criteria.get("keywords_muss") or [])
    ] + [
        (kw, _fuzzy_keyword_match)
        for kw in (criteria.get("keywords_plus") or [])
    ] + [
        (kw, _strict_keyword_match)
        for kw in (criteria.get("keywords_minus") or [])
    ]
    for kw, matcher in kandidaten:
        kl = kw.lower()
        if kl in faktoren:
            continue
        df = sum(1 for t in texte if matcher(kw, t))
        if df <= 0:
            faktoren[kl] = 1.0
            continue
        roh = math.log(n / df) / log_n if log_n > 0 else 0.0
        faktoren[kl] = round(
            max(IDF_MIN_FAKTOR, min(1.0, IDF_MIN_FAKTOR + (1 - IDF_MIN_FAKTOR) * roh)),
            3,
        )
    return faktoren


def get_idf_faktoren(db: Any, criteria: dict, force_refresh: bool = False) -> dict:
    """Gecachte IDF-Faktoren (Settings-Cache, max. 24h alt).

    Der Cache invalidiert sich auch, wenn sich die Keyword-Menge aendert —
    sonst rechnet ein frisch ergaenztes Keyword mit Faktor 1.0 weiter.
    """
    alle_kws = sorted({
        kw.lower()
        for key in ("keywords_muss", "keywords_plus", "keywords_minus")
        for kw in (criteria.get(key) or [])
    })
    try:
        raw = db.get_setting(IDF_CACHE_KEY, "") or ""
        cache = json.loads(raw) if raw else {}
    except Exception:
        cache = {}

    if not force_refresh and cache.get("keywords") == alle_kws:
        try:
            alter = datetime.now() - datetime.fromisoformat(cache.get("computed_at", ""))
            if alter < timedelta(hours=IDF_CACHE_MAX_ALTER_STUNDEN):
                return cache.get("faktoren", {}) or {}
        except Exception:
            pass

    faktoren = berechne_idf_faktoren(db, criteria)
    try:
        db.set_setting(IDF_CACHE_KEY, json.dumps({
            "computed_at": datetime.now().isoformat(),
            "keywords": alle_kws,
            "faktoren": faktoren,
        }, ensure_ascii=False))
    except Exception:
        pass  # Cache ist Komfort, kein Muss
    return faktoren


def _kriterien_variante(db: Any, criteria: dict, idf: bool) -> dict:
    """Kriterien-Kopie mit oder ohne injizierte IDF-Faktoren."""
    c = dict(criteria)
    c.pop("_idf_faktoren", None)
    if idf:
        c["_idf_faktoren"] = get_idf_faktoren(db, criteria)
    return c


def backtest(db: Any, stichprobe_dismissed: int = 200,
             modus: str = "aktuell") -> dict:
    """Backtest der aktuellen Kriterien gegen die gelabelte Historie.

    Reine Schattenrechnung — es wird kein einziger Score persistiert.

    modus: 'aktuell' (Kriterien wie konfiguriert), 'idf' (mit
    Seltenheitsgewichtung), 'beide' (Vergleich).
    """
    criteria = db.get_search_criteria()
    criteria.pop("_idf_faktoren", None)  # frisch entscheiden, nicht erben

    # --- Positive Labels: Stellen, auf die tatsaechlich beworben wurde ---
    positive: list[dict] = []
    nicht_bewertbar = 0
    for app in db.get_applications():
        job = None
        try:
            linked = db.get_jobs_for_application(app.get("id"))
            job = linked[0] if linked else None
        except Exception:
            job = None
        if job is None and app.get("job_hash"):
            job = db.get_job(app["job_hash"])
        if not job:
            nicht_bewertbar += 1
            continue
        positive.append({
            "application_id": (app.get("id") or "")[:8],
            "firma": app.get("company", ""),
            "titel": app.get("title", ""),
            "job": job,
        })

    # --- Negative Labels: Stichprobe der Aussortierten ---
    conn = db.connect()
    pid = db.get_active_profile_id()
    neg_rows = conn.execute(
        "SELECT * FROM jobs WHERE is_active=0 "
        "AND (profile_id=? OR profile_id IS NULL) "
        "AND COALESCE(dismiss_reason,'') NOT LIKE '%bewerbung_erstellt%' "
        "ORDER BY RANDOM() LIMIT ?",
        (pid, max(1, int(stichprobe_dismissed))),
    ).fetchall()
    negative_jobs = [db._serialize_job_row(r) for r in neg_rows]

    varianten = {"aktuell": False}
    if modus == "idf":
        varianten = {"idf": True}
    elif modus == "beide":
        varianten = {"aktuell": False, "idf": True}

    aktuelle_schwelle = criteria.get("min_score_schwelle", 1) or 1
    ergebnis: dict = {
        "status": "fertig",
        "persistiert": False,
        "hinweis_persistenz": (
            "Reine Schattenrechnung — kein Score in der jobs-Tabelle wurde "
            "veraendert. scores_neu_berechnen wurde NICHT aufgerufen."
        ),
        "aktuelle_schwelle": aktuelle_schwelle,
        "labels": {
            "bewerbungen_gesamt": len(positive) + nicht_bewertbar,
            "bewerbungen_bewertbar": len(positive),
            "bewerbungen_ohne_stelle": nicht_bewertbar,
            "aussortierte_stichprobe": len(negative_jobs),
        },
        "varianten": {},
    }

    for name, idf_an in varianten.items():
        krit = _kriterien_variante(db, criteria, idf=idf_an)
        pos_scores = [schatten_score(p["job"], krit) for p in positive]
        neg_scores = [schatten_score(j, krit) for j in negative_jobs]

        block: dict = {
            "bewerbungen": _statistik(pos_scores),
            "aussortierte": _statistik(neg_scores),
        }
        if pos_scores:
            min_pos = min(pos_scores)
            vorschlag = int(min_pos * 0.8)
            block["schwellen_vorschlag"] = vorschlag
            block["schwellen_formel"] = (
                f"niedrigster Bewerbungs-Score ({min_pos}) x 0.8 = {vorschlag} "
                "(20 % Toleranz nach unten, User-Vorgabe)"
            )
            if neg_scores:
                ueber = sum(1 for s in neg_scores if s >= vorschlag)
                block["aussortierte_ueber_vorschlag"] = ueber
                block["aussortierte_ueber_vorschlag_quote"] = round(
                    ueber / len(neg_scores), 3)
                block["ueberlappungszone"] = {
                    "von": min_pos,
                    "bis": max(neg_scores),
                    "hinweis": (
                        "Zwischen niedrigstem Bewerbungs-Score und hoechstem "
                        "Aussortierten-Score kann keine Schwelle sauber trennen."
                    ) if max(neg_scores) >= min_pos else "keine Ueberlappung",
                }
            # Warnung: historische Bewerbungen, die die AKTUELLE Schwelle
            # ausblenden wuerde — genau der Blindflug, den das Issue meint.
            unter = [
                {
                    "application_id": p["application_id"],
                    "firma": p["firma"],
                    "titel": p["titel"],
                    "schatten_score": s,
                }
                for p, s in zip(positive, pos_scores) if s < aktuelle_schwelle
            ]
            if unter:
                block["warnung_unter_aktueller_schwelle"] = unter
                block["warnung"] = (
                    f"{len(unter)} historische Bewerbung(en) laegen mit den "
                    f"aktuellen Kriterien UNTER der Schwelle {aktuelle_schwelle} "
                    "— die Schwelle darf ausblenden, nie loeschen."
                )
        else:
            block["hinweis"] = (
                "Keine bewerbungsverknuepften Stellen bewertbar — "
                "Schwellen-Vorschlag nicht moeglich."
            )
        ergebnis["varianten"][name] = block

    if modus == "beide" and all(
        k in ergebnis["varianten"] for k in ("aktuell", "idf")
    ):
        a = ergebnis["varianten"]["aktuell"].get("schwellen_vorschlag")
        b = ergebnis["varianten"]["idf"].get("schwellen_vorschlag")
        av = ergebnis["varianten"]["aktuell"].get("aussortierte_ueber_vorschlag_quote")
        bv = ergebnis["varianten"]["idf"].get("aussortierte_ueber_vorschlag_quote")
        ergebnis["vergleich"] = {
            "schwellen_vorschlag": {"aktuell": a, "idf": b},
            "falsch_positiv_quote_bei_vorschlag": {"aktuell": av, "idf": bv},
            "lesart": (
                "Niedrigere Falsch-Positiv-Quote bei gleicher Abdeckung der "
                "Bewerbungen = besser kalibriert."
            ),
        }
    return ergebnis
