"""URL → Source-Detection (#613, v1.7.0-beta.47).

Wenn eine Stelle manuell angelegt wird (z.B. via `bewerbung_erstellen`
aus einer LinkedIn-Anzeige) wurde sie historisch als
`source='manuell'` gespeichert — auch wenn die URL klar auf
LinkedIn, StepStone etc. zeigt. Das verfaelscht die Quellen-
Statistik im Bewerbungsbericht (Issue #613).

Dieses Modul liefert eine pure Funktion `detect_source_from_url(url)`,
die anhand des Hostnames die Quelle erkennt. Wird genutzt von:

- `bewerbung_erstellen` (Hot-Path, beim Anlegen)
- `stelle_manuell_anlegen` (Hot-Path, beim Anlegen)
- `quellen_aus_urls_korrigieren` (MCP-Migrations-Tool)
"""
from __future__ import annotations

from urllib.parse import urlparse


# Hostname-Pattern -> Source-Key (matcht SOURCE_REGISTRY in job_scraper).
# Reihenfolge ist relevant: spezifischere Pattern zuerst.
_HOST_PATTERNS: list[tuple[str, str]] = [
    # LinkedIn
    ("linkedin.com", "linkedin"),
    ("lnkd.in", "linkedin"),
    # XING
    ("xing.com", "xing"),
    ("xing.de", "xing"),
    # StepStone
    ("stepstone.de", "stepstone"),
    ("stepstone.com", "stepstone"),
    ("stepstone.at", "stepstone"),
    # Indeed
    ("de.indeed.com", "indeed"),
    ("indeed.com", "indeed"),
    ("indeed.de", "indeed"),
    # Monster
    ("monster.de", "monster"),
    ("monster.com", "monster"),
    # Bundesagentur
    ("arbeitsagentur.de", "bundesagentur"),
    ("jobboerse.arbeitsagentur.de", "bundesagentur"),
    # Hays
    ("hays.de", "hays"),
    ("hays.com", "hays"),
    # Freelance
    ("freelance.de", "freelance_de"),
    ("freelancermap.de", "freelancermap"),
    ("freelancermap.com", "freelancermap"),
    ("gulp.de", "gulp"),
    ("solcom.de", "solcom"),
    # Tech & Engineering
    ("ingenieur.de", "ingenieur_de"),
    ("vdi-nachrichten.com", "ingenieur_de"),
    ("heise.de", "heise_jobs"),
    # Aggregatoren
    ("kimeta.de", "kimeta"),
    ("jobware.de", "jobware"),
    ("stellenanzeigen.de", "stellenanzeigen_de"),
    ("meinestadt.de", "meinestadt"),
    # Remote-Boards
    ("remoteok.com", "remoteok"),
    ("remoteok.io", "remoteok"),
    ("remotive.com", "remotive"),
    ("remotive.io", "remotive"),
    ("himalayas.app", "himalayas"),
    ("arbeitnow.com", "arbeitnow"),
    # Tech-Recruiting
    ("greenhouse.io", "greenhouse"),
    ("workable.com", "workable"),
    ("personio.com", "personio"),
    ("personio.de", "personio"),
    ("workday.com", "workday_dax"),
    ("myworkdayjobs.com", "workday_dax"),
    # Berufseinstieg
    ("studentjob.de", "studentjob"),
    ("praktikum.de", "praktikum_de"),
    ("berufsstart.de", "berufsstart"),
    # Engineering-Dienstleister
    ("ferchau.com", "ferchau"),
    # Google
    ("google.com/search", "google_jobs"),  # nur fuer /search?q=...&ibp=htl;jobs
]


def detect_source_from_url(url: str) -> str:
    """Liefert den Source-Key fuer eine Job-URL, oder 'manuell' wenn
    die Domain nicht erkannt wird.

    Beispiele:
        detect_source_from_url("https://www.linkedin.com/jobs/view/12345")
        # -> 'linkedin'
        detect_source_from_url("https://www.firma-xyz.de/karriere/job/42")
        # -> 'manuell'  (unbekannte Domain)
        detect_source_from_url("")
        # -> 'manuell'
    """
    if not url or not isinstance(url, str):
        return "manuell"
    url = url.strip()
    if not url:
        return "manuell"
    # urlparse braucht ein Schema; sonst landet alles im path
    if "://" not in url:
        url = "https://" + url
    try:
        parsed = urlparse(url)
        host = (parsed.netloc or "").lower()
        if host.startswith("www."):
            host = host[4:]
    except Exception:
        return "manuell"
    if not host:
        return "manuell"
    # Substring-Match in der definierten Reihenfolge
    full_url = url.lower()
    for pattern, source in _HOST_PATTERNS:
        if "/" in pattern:
            # Pattern enthaelt Path-Anteil → ganze URL pruefen
            if pattern in full_url:
                return source
        elif host == pattern or host.endswith("." + pattern):
            return source
    return "manuell"


def is_known_source_pattern(url: str) -> bool:
    """True wenn die URL einer bekannten Quelle zugeordnet werden kann."""
    return detect_source_from_url(url) != "manuell"
