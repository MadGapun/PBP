"""Ein Satz je Quelle, aus Sicht des Menschen (G70, #1087 F2).

Die Beschreibungen im Quellen-Register sind fuer Entwickler geschrieben:
Bibliotheksnamen und Lizenzen ("python-jobspy (MIT)"), Messdaten
("gemessen 0 von 20 Treffern ... (08.09.2026)"), Issue-Nummern ("#919",
"#501") und Umschriften statt Umlauten. Im Dashboard stand genau das.

Das Register bleibt, wie es ist — sein Text wird in Diagnosen und
Werkzeugantworten gelesen. Das Dashboard zeigt `KURZ`: ein Satz, was man
dort findet und was man dafuer tun muss. Ein Test haelt jede Quelle des
Registers gegen diese Tabelle und prueft die Form (ein Satz, keine
Issue-Nummer, keine Bibliotheks- oder Protokollnamen).
"""
from __future__ import annotations

KURZ: dict[str, str] = {
    "bundesagentur": "Die Jobbörse der Arbeitsagentur, mit den meisten Stellen in Deutschland.",
    "hays": "Stellen und Projekte eines Personaldienstleisters, vor allem in Technik und IT.",
    "freelance_de": "Projekte für Freiberufler, vor allem in der IT.",
    "ingenieur_de": "Stellen für Ingenieure und technische Berufe.",
    "heise_jobs": "Stellen in IT und Systemadministration.",
    "gulp": "Projekte für Freiberufler in IT und Technik.",
    "solcom": "IT- und Technikprojekte eines Personaldienstleisters.",
    "stellenanzeigen_de": "Eine große deutsche Jobbörse für alle Branchen.",
    "adzuna": "Sammelt Stellen aus vielen Börsen; braucht einen kostenlosen eigenen Zugangsschlüssel.",
    "jobware": "Stellen für Fachkräfte und Führungskräfte.",
    "ferchau": "Stellen eines Personaldienstleisters für Technik und IT.",
    "kimeta": "Sammelt Stellen aus vielen deutschen Börsen.",
    "jobspy_linkedin": "LinkedIn-Stellen ohne Anmeldung; ein Lauf dauert länger als bei anderen Quellen.",
    "jobspy_indeed": "Indeed-Stellen mit vollständigem Anzeigentext, ohne Anmeldung.",
    "jobspy_glassdoor": "Glassdoor-Stellen; die Börse lässt automatische Abfragen oft nicht zu.",
    "arbeitnow": "Sammelt Stellen aus Deutschland, oft in Technik und mit Homeoffice.",
    "personio": "Stellen direkt von den Karriereseiten kleiner und mittlerer Firmen, in allen Branchen.",
    "workable": "Stellen direkt von den Karriereseiten vieler Firmen, in allen Branchen.",
    "meinestadt": "Regionale Stellen in Handel, Gastronomie, Pflege und Handwerk.",
    "himalayas": "Weltweite Stellen mit Homeoffice; für Deutschland kommt selten etwas.",
    "remotive": "Weltweite Stellen mit Homeoffice, teils auch aus Deutschland bewerbbar.",
    "remoteok": "Weltweite Stellen mit Homeoffice, meist auf Englisch.",
    "praktikum_de": "Praktika und Werkstudentenstellen.",
    "studentjob": "Studentenjobs und Werkstudentenstellen.",
    "berufsstart": "Einstiegsstellen für Studierende und Absolventen: Trainee, Praktikum, Direkteinstieg.",
    "workday_dax": "Karriereseiten großer Konzerne in Deutschland, die Workday nutzen.",
    "greenhouse": "Karriereseiten einzelner Firmen, die Greenhouse nutzen.",
    "jobspy_google": "Stellen aus der Google-Jobsuche, die viele Börsen auf einmal zeigt.",
    "stepstone": "Eine große deutsche Jobbörse; läuft nur über den Browser mit Claude.",
    "freelancermap": "Projekte für Freiberufler und Selbstständige.",
    "indeed": "Die Indeed-Suche im Browser mit Claude.",
    "linkedin": "Die LinkedIn-Suche mit deinem Konto im Browser mit Claude.",
    "xing": "Die XING-Suche mit deinem Konto im Browser mit Claude.",
    "google_jobs": "Die Google-Jobsuche im Browser mit Claude; zeigt Stellen vieler Börsen auf einmal.",
}


def kurz(schluessel: str, info: dict | None = None) -> str:
    """Der Satz fuer das Dashboard; ohne Eintrag der Registertext."""
    return KURZ.get(schluessel) or (info or {}).get("beschreibung", "")
