"""Wiedergaenger-Erkenner — Ebene 0: deterministischer DB-Check (#671, B-Cluster).

Architektur-Leitplanke (User-Vorgabe in #671): **PBP-Kernfunktionen duerfen
lokale KI NIE voraussetzen.** Dieser Modul ist Ebene 0: rein deterministisch,
ohne jede KI. Er traegt das Feature allein.

  Ebene 0 (hier)  — KI-frei, immer verfuegbar: gleiche Firma + Titel-Domaenen-
                    Token-Ueberlappung gegen aussortierte Stellen, aggregiert
                    nach dismiss_reason.
  Ebene 1 (Ollama) — optional, separat, ueberspringbar ohne Funktionsverlust.
  Ebene 2 (Claude) — in fit_analyse: liefert die Aussortier-Historie als Kontext.

Konkreter Fall (#671): Tchibo GmbH PLM-Rolle wurde 2x als
`falsches_fachgebiet` verworfen. Beim 3. Auftauchen (neuer Hash, andere Quelle)
soll PBP erkennen: "Firma Tchibo + Domaene PLM schon 2x als falsches_fachgebiet
verworfen" — bevor die Stelle wieder als frischer Fund auf dem Tisch landet.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Optional


# Rechtsform-Suffixe + generische Zusaetze, die bei der Firmen-Normalisierung
# entfernt werden. "Tchibo GmbH" und "Tchibo" sollen als gleiche Firma gelten.
_COMPANY_SUFFIXES = {
    "gmbh", "ag", "se", "kg", "kgaa", "mbh", "ohg", "ug", "ev", "co",
    "gbr", "ltd", "limited", "inc", "llc", "plc", "holding", "group",
    "deutschland", "germany", "international", "and", "the",
}

# Generische Job-Titel-Woerter + Grammatik + Gender-Marker. Diese zaehlen
# NICHT als Domaenen-Ueberlappung — sonst wuerde "Manager (m/w/d)" bei jeder
# zweiten Stelle derselben Firma falsch matchen. Nur fachliche Tokens (z.B.
# "plm", "teamcenter", "embedded") sollen als Domaenen-Signal durchgehen.
_TITLE_STOPS = {
    # Gender / Grammatik
    "m", "w", "d", "x", "mwd", "wmd", "divers", "in", "innen",
    "und", "der", "die", "das", "ein", "eine", "fuer", "im", "mit",
    "bei", "von", "zu", "an", "the", "and", "for", "with", "of",
    # Generische Rollen-Woerter
    "manager", "managerin", "specialist", "spezialist", "spezialistin",
    "senior", "junior", "lead", "leiter", "leiterin", "leitung",
    "mitarbeiter", "mitarbeiterin", "consultant", "berater", "beraterin",
    "engineer", "ingenieur", "ingenieurin", "developer", "entwickler",
    "entwicklerin", "expert", "experte", "expertin", "owner", "officer",
    "coordinator", "koordinator", "assistant", "assistent", "referent",
    "fachkraft", "sachbearbeiter", "sachbearbeiterin",
    "stelle", "position", "rolle", "job", "team", "all", "genders",
}


def normalize_company(name: Optional[str]) -> str:
    """Normalisiert einen Firmennamen fuer den Gleichheits-Vergleich.

    "Tchibo GmbH" -> "tchibo", "Beispiel AG & Co. KG" -> "beispiel".
    Lowercase, Interpunktion raus, Rechtsform-Suffixe raus.
    """
    if not name:
        return ""
    s = name.lower()
    s = re.sub(r"[^a-zäöüß0-9\s]", " ", s)
    tokens = [t for t in s.split() if t and t not in _COMPANY_SUFFIXES]
    return " ".join(tokens).strip()


def _domain_tokens(title: Optional[str]) -> set:
    """Extrahiert die fachlichen Domaenen-Tokens aus einem Stellentitel.

    Generische Rollen-/Grammatik-/Gender-Woerter werden entfernt, sodass
    nur das fachliche Signal (z.B. {"plm"} aus "PLM Project Manager (m/w/d)")
    uebrig bleibt.
    """
    if not title:
        return set()
    raw = set(re.findall(r"[a-zäöüß0-9]+", title.lower()))
    return {t for t in raw if t not in _TITLE_STOPS and len(t) >= 2}


def _reasons_of(job: dict) -> list[str]:
    """Liefert die dismiss_reasons eines Jobs als saubere Liste."""
    reasons = job.get("dismiss_reasons") or []
    if not reasons and job.get("dismiss_reason"):
        reasons = [job["dismiss_reason"]]
    out = []
    for r in reasons:
        rc = str(r).strip()
        # auto:-Prefix der Ollama-Auto-Aussortierung entfernen, damit
        # 'auto:falsches_fachgebiet' und 'falsches_fachgebiet' zusammenfallen
        if rc.startswith("auto:"):
            rc = rc[len("auto:"):]
        if rc:
            out.append(rc)
    return out


def find_wiedergaenger_pattern(
    db,
    company: str,
    title: str,
    *,
    schwellwert: int = 2,
    min_overlap: int = 1,
    target_hash: Optional[str] = None,
) -> Optional[dict]:
    """Ebene 0 (#671): KI-freier Wiedergaenger-Check.

    Sucht aussortierte Stellen DERSELBEN FIRMA mit Titel-Domaenen-Token-
    Ueberlappung und aggregiert nach dismiss_reason. Liefert ein Muster,
    wenn ein Grund >= `schwellwert` mal auftrat.

    Args:
        db: Database-Instanz (read-only genutzt).
        company: Firmenname der zu pruefenden Stelle.
        title: Titel der zu pruefenden Stelle.
        schwellwert: Mindestanzahl gleichgesinnter Aussortierungen (Default 2).
        min_overlap: Mindest-Anzahl gemeinsamer Domaenen-Tokens (Default 1).
            Guard gegen "gleiche Grossfirma, voellig andere Rolle".
        target_hash: Optional — eigener Hash, damit die Stelle sich nicht
            selbst matcht.

    Returns:
        None wenn kein klares Muster, sonst dict mit:
        - top_grund, anzahl, beispiele, domain_tokens, firma, alle_gruende
    """
    norm_company = normalize_company(company)
    if not norm_company:
        return None
    target_tokens = _domain_tokens(title)

    try:
        dismissed = db.get_dismissed_jobs()
    except Exception:
        return None

    matches: list[tuple[dict, set]] = []
    for j in dismissed:
        if target_hash and j.get("hash") == target_hash:
            continue
        if normalize_company(j.get("company")) != norm_company:
            continue
        if not _reasons_of(j):
            continue
        jt = _domain_tokens(j.get("title"))
        shared = target_tokens & jt
        # Wenn die neue Stelle Domaenen-Tokens hat, verlangen wir Ueberlappung.
        # Hat sie keine (leerer/sehr generischer Titel), zaehlt der reine
        # Firmen-Match — aber dann mit hoeherer impliziter Schwelle, weil das
        # Signal schwaecher ist.
        if target_tokens and len(shared) < min_overlap:
            continue
        matches.append((j, shared))

    if len(matches) < schwellwert:
        return None

    reason_counter: Counter = Counter()
    by_reason: dict[str, list] = {}
    domain_tokens_seen: set = set()
    for j, shared in matches:
        domain_tokens_seen |= shared
        for r in _reasons_of(j):
            reason_counter[r] += 1
            by_reason.setdefault(r, []).append(j)

    if not reason_counter:
        return None

    top_grund, anzahl = reason_counter.most_common(1)[0]
    if anzahl < schwellwert:
        return None

    beispiele = [
        {
            "hash": (j.get("hash") or "")[-12:],
            "title": (j.get("title") or "")[:80],
        }
        for j in by_reason[top_grund][:3]
    ]

    return {
        "firma": company,
        "top_grund": top_grund,
        "anzahl": anzahl,
        "domain_tokens": sorted(domain_tokens_seen & target_tokens) or sorted(domain_tokens_seen),
        "alle_gruende": dict(reason_counter),
        "beispiele": beispiele,
        "hinweis": (
            f"Firma '{company}' wurde bereits {anzahl}x mit Grund "
            f"'{top_grund}' aussortiert"
            + (f" (Domaene: {', '.join(sorted(domain_tokens_seen & target_tokens))})"
               if (domain_tokens_seen & target_tokens) else "")
            + "."
        ),
    }
