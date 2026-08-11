"""Elwosa-Inhaltskanaele als Provider (#823/F37, v1.7.12).

Elwosa hatte genau eine Inhaltsquelle: vorformulierte Stimmungslinien.
Alles, was PBP tatsaechlich WEISS und der Nutzer nicht sieht, blieb
ungesagt. Jeder Kanal ist ein Provider, der Kandidaten liefert; die
Engine (#822) waehlt, drosselt und postet — kein Kanal schreibt an ihr
vorbei.

In dieser Welle geliefert: Kanal 1 (Changelog) und Kanal 6
(Betriebslage). Kanal 4 (Feature-Tipps) existierte als
`_feature_tipp_linien` (F24/#713) und bekommt hier die geteilte
Dismiss-Mechanik. Kanal 3 (Statistik), Kanal 2 (Wiki) und Kanal 5
(#794) folgen — Reihenfolge aus dem Issue.

Regelbasiert, ohne Sprachmodell. Alle Linien durchlaufen die
Sprach-DNA-Validierung beim Posten (post_candidate in elwosa.py).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Maximal so viele Changelog-Linien je Version, verteilt ueber Tage.
CHANGELOG_MAX_LINIEN = 3


@dataclass
class Candidate:
    content: str              # max. 280 Zeichen, Sprach-DNA-konform
    trigger_kind: str
    cluster: str = ""
    trigger_ref: str = ""     # ID des ausloesenden Objekts
    dedup_key: str = ""       # Grundlage der Sperrfrist (#822)
    link_url: str = ""
    link_label: str = ""
    prioritaet: int = 1       # 0 = Ereignis (zuerst), 1 = Fuellstoff


# ---------------------------------------------------------------- Kanal 1

def _changelog_pfad() -> Path:
    # Repo-Root: src/bewerbungs_assistent/services/ -> drei Ebenen hoch
    return Path(__file__).resolve().parents[3] / "CHANGELOG.md"


def _parse_changelog_kopf(text: str):
    """Version + anwendersichtbare Eintraege (Added/Fixed) der NEUESTEN
    Version. Keep-a-Changelog-Struktur — die Zusatz-Markierung aus der
    Spec ist unnoetig, interne Refactorings stehen dort ohnehin nicht.
    """
    m = re.search(r"^## \[([^\]]+)\][^\n]*$", text, re.M)
    if not m:
        return None, []
    version = m.group(1)
    start = m.end()
    naechste = re.search(r"^## \[", text[start:], re.M)
    block = text[start:start + naechste.start()] if naechste else text[start:]
    eintraege = []
    in_relevanter_sektion = False
    for zeile in block.split("\n"):
        s = zeile.strip()
        if s.startswith("### "):
            in_relevanter_sektion = s[4:].strip().lower() in (
                "added", "fixed", "changed")
            continue
        if in_relevanter_sektion and s.startswith("- "):
            # Ersten Satz nehmen, Markdown-Sternchen raus
            eintrag = re.sub(r"\*\*|\`", "", s[2:]).split(". ")[0].strip()
            if eintrag:
                eintraege.append(eintrag)
    return version, eintraege


def changelog_kandidaten(db) -> list:
    """Kanal 1: Nach einem Update die wichtigsten Aenderungen melden.

    Zustand in profile_settings: zuletzt gemeldete Version + wie viele
    Linien dazu schon liefen (max. 3, verteilt — die Kind-Sperrfrist aus
    #822 sorgt fuer den Abstand). Uebersprungene Versionen werden nicht
    einzeln nachgemeldet — es zaehlt der Stand der installierten Version.
    """
    try:
        text = _changelog_pfad().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    version, eintraege = _parse_changelog_kopf(text)
    if not version or not eintraege:
        return []
    gemeldet_version = db.get_profile_setting(
        "elwosa_changelog_version", "") or ""
    try:
        gemeldet_n = int(db.get_profile_setting(
            "elwosa_changelog_anzahl", 0) or 0)
    except (TypeError, ValueError):
        gemeldet_n = 0
    if gemeldet_version != version:
        gemeldet_n = 0
    if gemeldet_n >= min(CHANGELOG_MAX_LINIEN, len(eintraege)):
        return []
    eintrag = eintraege[gemeldet_n]
    if len(eintrag) > 200:
        eintrag = eintrag[:197] + "..."
    content = f"Neue Version ist drin. {eintrag}. Vermerkt."
    if len(content) > 280:
        content = content[:277] + "..."
    return [Candidate(
        content=content,
        trigger_kind="changelog",
        trigger_ref=version,
        dedup_key=f"changelog:{version}:{gemeldet_n}",
        link_url=("https://github.com/MadGapun/PBP/releases/tag/"
                  f"v{version}"),
        link_label="Was noch neu ist",
        prioritaet=1,
    )]


def changelog_gemeldet(db, version: str):
    """Nach erfolgreichem Post den Zaehler fortschreiben."""
    alt = db.get_profile_setting("elwosa_changelog_version", "") or ""
    try:
        n = int(db.get_profile_setting("elwosa_changelog_anzahl", 0) or 0)
    except (TypeError, ValueError):
        n = 0
    if alt != version:
        n = 0
    db.set_profile_setting("elwosa_changelog_version", version)
    db.set_profile_setting("elwosa_changelog_anzahl", n + 1)


# ---------------------------------------------------------------- Kanal 6

def betriebslage_kandidaten(db) -> list:
    """Kanal 6: betriebliche Probleme, die kein Fehlerdialog sind.

    Auslaeser aus vorhandenen Daten: Stellen ohne Anker (#766), bisher
    tragende Quellen, die versiegt sind (scraper_health), erkannte
    Reposts auf frueher beworbene Stellen (#782). Der Score-Sprung nach
    Beschreibungs-Nachladen braucht eine Alt-Score-Erfassung am
    Refetch-Pfad und folgt separat — hier bewusst nicht halb gebaut.
    """
    kandidaten: list = []

    # 1 — aktive Stellen ohne jeden Anker (#766)
    try:
        from .stellen_anker import anker_status
        aktive = db.get_active_jobs()
        ohne = [j for j in aktive[:200]
                if not anker_status(db, j)["hat_anker"]]
        if ohne:
            j = ohne[0]
            n = len(ohne)
            if n == 1:
                content = ("Eine Stelle im Bestand hat weder Link noch "
                           "Ansprechpartner. Bewerben kannst du dich da "
                           "nicht. Schau mal drauf.")
            else:
                content = (f"{n} Stellen im Bestand haben weder Link noch "
                           "Ansprechpartner. Bewerben geht so nicht. "
                           "stellen_urls_heilen hilft beim Aufraeumen.")
            kandidaten.append(Candidate(
                content=content, trigger_kind="betriebslage",
                trigger_ref=j.get("hash", ""),
                dedup_key=f"ohne_anker:{n}",
                link_url="pbp://tab/stellen", link_label="Stellen ansehen",
                prioritaet=0))
    except Exception:
        pass

    # 2 — bisher tragende Quelle versiegt (scraper_health). "Tragend"
    # heisst: es gab dort mal regelmaessig Erfolge (total_successes) —
    # eine Quelle, die noch nie lieferte, ist kein Betriebslage-Fall.
    try:
        conn = db.connect()
        row = conn.execute(
            "SELECT scraper_name, consecutive_silent, consecutive_failures "
            "FROM scraper_health "
            "WHERE (consecutive_silent >= 3 OR consecutive_failures >= 3) "
            "AND COALESCE(total_successes, 0) >= 10 "
            "ORDER BY total_successes DESC LIMIT 1").fetchone()
        if row:
            kandidaten.append(Candidate(
                content=(f"Die Quelle {row['scraper_name']} liefert seit "
                         "mehreren Laeufen nichts mehr. Frueher kam dort "
                         "einiges. quellen_health_check zeigt den Stand."),
                trigger_kind="betriebslage",
                trigger_ref=row["scraper_name"],
                dedup_key=f"quelle_versiegt:{row['scraper_name']}",
                link_url="pbp://tab/einstellungen",
                link_label="Quellen pruefen",
                prioritaet=0))
    except Exception:
        pass

    # 3 — Repost einer frueher beworbenen Stelle im aktiven Bestand (#782)
    try:
        from ..duplicate_detection import find_repost_of_application
        bewerbungen = db.get_applications()
        for j in db.get_active_jobs()[:100]:
            rep = find_repost_of_application(j, bewerbungen)
            if rep:
                kandidaten.append(Candidate(
                    content=(f"Die Stelle bei {j.get('company', '?')} kennst "
                             "du — da lief schon mal eine Bewerbung. "
                             "Repost, keine neue Chance ohne neuen Plan."),
                    trigger_kind="betriebslage",
                    trigger_ref=j.get("hash", ""),
                    dedup_key=f"repost:{j.get('hash', '')}",
                    link_url=f"pbp://stellen/{j.get('hash', '')}",
                    link_label="Stelle ansehen",
                    prioritaet=0))
                break
    except Exception:
        pass

    return kandidaten


def alle_kandidaten(db) -> list:
    """Alle Provider abfragen, Ereignis-Kandidaten zuerst."""
    out: list = []
    for provider in (betriebslage_kandidaten, changelog_kandidaten):
        try:
            out.extend(provider(db))
        except Exception:
            continue
    return sorted(out, key=lambda c: c.prioritaet)
