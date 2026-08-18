"""Wiedergaenger-Erkenner — Ebene 0: deterministischer DB-Check (#671, B-Cluster).

Architektur-Leitplanke (User-Vorgabe in #671): **PBP-Kernfunktionen duerfen
lokale KI NIE voraussetzen.** Dieser Modul ist Ebene 0: rein deterministisch,
ohne jede KI. Er traegt das Feature allein.

  Ebene 0 (hier)  — KI-frei, immer verfuegbar: gleiche Firma + Titel-Domaenen-
                    Token-Ueberlappung gegen aussortierte Stellen, aggregiert
                    nach dismiss_reason.
  Ebene 1 (Ollama) — optional, separat, ueberspringbar ohne Funktionsverlust.
  Ebene 2 (Claude) — in fit_analyse: liefert die Aussortier-Historie als Kontext.

Konkreter Fall (#671): Konsumgueter GmbH PLM-Rolle wurde 2x als
`falsches_fachgebiet` verworfen. Beim 3. Auftauchen (neuer Hash, andere Quelle)
soll PBP erkennen: "Firma Konsumgueter + Domaene PLM schon 2x als falsches_fachgebiet
verworfen" — bevor die Stelle wieder als frischer Fund auf dem Tisch landet.

Gegenfall (#754, v1.7.7): Der Match darf NICHT ueber generische Tokens
("sr", "project") oder den reinen Firmen-Namen entstehen. 3x aussortierte
Halbleiter-Fachrollen (Quality/Reliability/Wafertest Engineer) machen einen
"(Sr.) Project Manager" derselben Firma NICHT zum Wiedergaenger — das ist
eine andere ROLLE. Regelwerk seitdem:

  1. Fach-Domaenen-Ueberlappung (z.B. "plm") traegt den Match — Rolle egal
     (PLM Owner + PLM Manager -> PLM Architect bleibt Wiedergaenger, #671).
  2. Ohne Fach-Signal im neuen Titel zaehlt ein Treffer nur bei
     uebereinstimmender ROLLEN-FAMILIE (Manager/Engineer/Entwickler/...).
  3. Aussortier-Gruende gelten je STELLE, nie fuer die Firma (#757) —
     `firmen_historie()` liefert den neutralen Kontext dafuer.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Optional


# Rechtsform-Suffixe + generische Zusaetze, die bei der Firmen-Normalisierung
# entfernt werden. "Konsumgueter GmbH" und "Konsumgueter" sollen als gleiche Firma gelten.
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
    # Seniority-Abkuerzungen (#754 — "sr" hatte den Praxis-Fehlmatch vom 13.07. getragen)
    "sr", "jr", "sen",
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

# #754: Tokens, die einen ROLLEN-Zuschnitt beschreiben, kein Fachgebiet.
# "Project"/"Program"/"Product" duerfen keine Domaenen-Ueberlappung stiften —
# sonst wird ein "Project Manager" zum Wiedergaenger eines "Project Engineer
# Wafertest". Sie fliessen stattdessen in die Rollen-Familien unten ein.
# Bewusst NICHT dabei: "process"/"prozess" (oft echtes Fachgebiet, z.B.
# Halbleiter-"Process Engineer").
_GENERIC_ROLE_TOKENS = {
    "project", "projekt", "program", "programm", "pmo",
    "product", "produkt", "interim",
}

# #754: Rollen-Familien fuer den Fallback OHNE Fach-Signal. Ein Token gehoert
# zur Familie, wenn es mit einem Muster beginnt ODER endet — das faengt
# deutsche Komposita ("Projektleiter" -> projektrolle + management,
# "Softwareentwickler" -> entwicklung), ohne Substring-Falschtreffer wie
# "test" in "Wafertest".
_ROLE_FAMILIES = {
    "management": (
        "manager", "management", "leiter", "leitung", "lead", "head",
        "chief", "director", "direktor", "vorstand",
    ),
    "projektrolle": (
        "project", "projekt", "program", "programm", "pmo", "scrum",
    ),
    "produktrolle": ("product", "produkt", "owner"),
    "engineering": (
        "engineer", "ingenieur", "techniker", "technician", "technologe",
    ),
    "entwicklung": ("developer", "entwickler", "programmierer", "software"),
    "beratung": ("consultant", "berater"),
    "analyse": ("analyst",),
    "architektur": ("architect", "architekt"),
    "vertrieb": ("sales", "vertrieb", "account"),
    "verwaltung": (
        "sachbearbeiter", "referent", "assistent", "assistant",
        "kaufmann", "kauffrau", "administrator",
    ),
}


def normalize_company(name: Optional[str]) -> str:
    """Normalisiert einen Firmennamen fuer den Gleichheits-Vergleich.

    "Konsumgueter GmbH" -> "konsumgueter", "Beispiel AG & Co. KG" -> "beispiel".
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
    uebrig bleibt. Seit #754 fallen auch Rollen-Zuschnitt-Tokens raus
    ("project", "product", ...) — die tragen Rollen-, keine Fach-Information.
    """
    if not title:
        return set()
    raw = set(re.findall(r"[a-zäöüß0-9]+", title.lower()))
    return {
        t for t in raw
        if t not in _TITLE_STOPS and t not in _GENERIC_ROLE_TOKENS and len(t) >= 2
    }


def _role_families(title: Optional[str]) -> set:
    """Ordnet einen Stellentitel Rollen-Familien zu (#754).

    "(Sr.) Project Manager (m/f/d)" -> {"management", "projektrolle"},
    "Senior Quality Engineer" -> {"engineering"}, "PLM" -> set().
    Prefix-/Suffix-Match je Token, damit deutsche Komposita
    ("Projektleiter", "Softwareentwickler") beide Anteile liefern.
    """
    if not title:
        return set()
    tokens = re.findall(r"[a-zäöüß0-9]+", title.lower())
    families = set()
    for tok in tokens:
        for family, patterns in _ROLE_FAMILIES.items():
            if any(tok == p or tok.startswith(p) or tok.endswith(p)
                   for p in patterns):
                families.add(family)
    return families


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
    dismissed: Optional[list] = None,
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
        dismissed: v1.7.12 (#827) — vorab geladene Liste aussortierter
            Stellen. stellen_anzeigen prueft jede Stelle der Seite; ohne
            Preload wuerde jeder Aufruf den vollen Bestand neu laden.

    Returns:
        None wenn kein klares Muster, sonst dict mit:
        - top_grund, anzahl, beispiele, domain_tokens, firma, alle_gruende
    """
    norm_company = normalize_company(company)
    if not norm_company:
        return None
    target_tokens = _domain_tokens(title)
    target_roles = _role_families(title)

    if dismissed is None:
        try:
            dismissed = db.get_dismissed_jobs()
        except Exception:
            return None

    matches: list[tuple[dict, set]] = []
    roles_matched: set = set()
    for j in dismissed:
        if target_hash and j.get("hash") == target_hash:
            continue
        if normalize_company(j.get("company")) != norm_company:
            continue
        if not _reasons_of(j):
            continue
        jt = _domain_tokens(j.get("title"))
        shared = target_tokens & jt
        if target_tokens:
            # Die neue Stelle hat ein Fach-Signal: Ueberlappung ist Pflicht.
            # Faecher-Match traegt allein — Rolle egal (#671: PLM Owner +
            # PLM Manager machen einen PLM Architect zum Wiedergaenger).
            if len(shared) < min_overlap:
                continue
        elif target_roles:
            # Kein Fach-Signal (generischer Titel wie "(Sr.) Project
            # Manager"): reiner Firmen-Match reicht NICHT (#754). Es zaehlt
            # nur, wer dieselbe Rollen-Familie hat — ein Project Manager ist
            # kein Wiedergaenger dreier aussortierter Quality Engineers.
            shared_roles = target_roles & _role_families(j.get("title"))
            if not shared_roles:
                continue
            roles_matched |= shared_roles
        # Titel komplett ohne Tokens (leer): bewusster "Firma pruefen"-Modus
        # von stelle_wiedergaenger_pruefen — Firmen-Match zaehlt wie bisher.
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

    result = {
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
            + (f" (gleiche Rolle: {', '.join(sorted(roles_matched))})"
               if roles_matched else "")
            + "."
        ),
    }
    if roles_matched:
        result["rollen_familien"] = sorted(roles_matched)
    return result


def firmen_historie(
    db,
    company: str,
    *,
    target_hash: Optional[str] = None,
) -> Optional[dict]:
    """Neutraler Firmen-Kontext ohne Wiedergaenger-Wertung (#754/#757).

    Liefert die Aussortier-Historie einer Firma als EINORDNUNG — ausdruecklich
    KEIN k.o.-Signal. Gedacht fuer Faelle, in denen der Wiedergaenger-Check
    leer ausgeht (andere Rolle/Domaene), die Historie aber trotzdem erwaehnt
    werden soll: "3 fruehere Aussortierungen betrafen ANDERE Rollen dieser
    Firma; die Gruende gelten je Stelle, nicht firmenweit."

    Returns:
        None wenn die Firma keine aussortierten Stellen hat, sonst dict mit
        aussortiert_anzahl, gruende, beispiel_titel, hinweis.
    """
    norm_company = normalize_company(company)
    if not norm_company:
        return None
    try:
        dismissed = db.get_dismissed_jobs()
    except Exception:
        return None

    reason_counter: Counter = Counter()
    titles: list[str] = []
    for j in dismissed:
        if target_hash and j.get("hash") == target_hash:
            continue
        if normalize_company(j.get("company")) != norm_company:
            continue
        reasons = _reasons_of(j)
        if not reasons:
            continue
        for r in reasons:
            reason_counter[r] += 1
        if j.get("title"):
            titles.append(str(j["title"])[:80])

    if not reason_counter:
        return None

    anzahl = len(titles) or sum(reason_counter.values())
    top_grund, _ = reason_counter.most_common(1)[0]
    return {
        "firma": company,
        "aussortiert_anzahl": anzahl,
        "gruende": dict(reason_counter),
        "beispiel_titel": titles[:5],
        "hinweis": (
            f"Zur Einordnung: bei '{company}' wurden {anzahl} andere "
            f"Stellen aussortiert (haeufigster Grund: '{top_grund}'). Die "
            "Gruende gelten je STELLE, nicht fuer die Firma (#757) — diese "
            "Rolle unvoreingenommen bewerten."
        ),
    }
