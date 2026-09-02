"""Kompetenzen aus Stellenbeschreibungen lesen (#963 Befund 2, v1.7.24).

Die alte Extraktion nahm jedes grossgeschriebene Wort:

    re.findall(r'\\b[A-Z][a-zA-Z+#.]+\\b', text)

Im Deutschen ist das JEDES SUBSTANTIV, dazu jedes Wort am Satzanfang.
Entsprechend sah das Ergebnis aus — belegt am 28.08.2026:

    vorhandene_skills: system, architektur, systeme, sie, ra, ort, teams, id
    fehlende_skills:   requirements, qm, balance, entscheidungsgrundlagen,
                       aufgaben, <VORNAME>, impulse, kein, start, ...

"sie", "kein", "aufgaben", "urlaub", "okt" sind keine Kompetenzen.
"balance" und "impulse" stammen aus dem Benefits-Absatz. Der Vorname
kam aus dem Notizteil hinter der Trennzeile. Das ausgewiesene
`match_prozent: 16` war damit bedeutungslos: Zaehler UND Nenner
bestanden ueberwiegend aus Rauschen.

Gleichzeitig fehlten die echten Anforderungen — Systems Engineering,
Requirements Engineering, IEC 62304, ISO 13485 — oder standen nur als
abgerissenes Fragment da ("requirements"), weil die Zerlegung nach
Einzelwoertern Mehrwortbegriffe zerreisst.

**Warum Positivliste statt Sperrliste.** Eine Sperrliste deutscher
Alltagswoerter wird nie fertig; jeder neue Anzeigentext bringt neue.
Dieselbe Lehre wie bei der Aussortier-Automatik (#941): automatisch
handeln nur auf ausdruecklich Erkanntem. Was hier nicht erkannt wird,
fehlt in der Liste — das ist der harmlose Fehler. Rauschen als
Kompetenz auszuweisen ist der teure.
"""
from __future__ import annotations

import re
from typing import Iterable

# Trennzeile, hinter der PBP Notizen ablegt (#603/#917). Alles dahinter
# ist Korrespondenz, nicht Anzeige — im belegten Fall stand dort der
# Vorname des Mail-Absenders.
_NOTIZ_TRENNER = re.compile(r"^-{3,}\s*$", re.MULTILINE)

# Normen und Standards. Ein Bezeichner wie "IEC 62304" ist EIN Begriff;
# in Einzelwoerter zerlegt bleibt "iec" und eine nackte Zahl uebrig.
_NORM = re.compile(
    r"\b(?:ISO|IEC|DIN|EN|ASME|VDA|IATF|ANSI|IPC|MIL|MDR|FDA|GMP|"
    r"AS|SAE|UL|ECSS)[\s/-]?\d{3,5}(?:[-:]\d{1,4})?\b",
    re.IGNORECASE,
)

# Mehrwortbegriffe der Fachsprache. Kuratiert und erweiterbar — genau
# der Punkt, an dem die Liste waechst, wenn eine Anzeige etwas Neues
# bringt.
_MEHRWORT = (
    "systems engineering", "requirements engineering",
    "engineering change management", "product lifecycle management",
    "model based systems engineering", "modellbasierte entwicklung",
    "functional safety", "funktionale sicherheit",
    "technische dokumentation", "technisches produktdesign",
    "continuous integration", "continuous delivery",
    "machine learning", "deep learning", "data science",
    "product data management", "change management",
    "configuration management", "konfigurationsmanagement",
    "risk management", "risikomanagement", "qualitaetsmanagement",
    "projektmanagement", "projektleitung", "teilprojektleitung",
    "anforderungsmanagement", "testmanagement", "variantenmanagement",
    "stuecklisten", "stuecklistenmanagement",
    "technischer vertrieb", "embedded software", "embedded systems",
    "digital twin", "digitaler zwilling", "additive fertigung",
    "supply chain", "lean management", "six sigma",
    "clean code", "test driven development", "domain driven design",
    "infrastructure as code", "site reliability engineering",
)

# Einzelbegriffe der Fachsprache. Bewusst klein gehalten und auf das
# beschraenkt, was in Stellenanzeigen tatsaechlich als Anforderung
# steht.
_FACHWORT = (
    "plm", "erp", "mes", "cad", "cam", "cae", "pdm", "plc", "sps",
    "teamcenter", "windchill", "enovia", "aras", "sap", "catia",
    "solidworks", "creo", "nx", "inventor", "autocad", "eplan",
    "polarion", "doors", "jira", "confluence", "git", "svn",
    "python", "java", "javascript", "typescript", "csharp", "kotlin",
    "golang", "rust", "matlab", "simulink", "labview", "fortran",
    "sql", "nosql", "postgresql", "mysql", "oracle", "mongodb",
    "docker", "kubernetes", "jenkins", "ansible", "terraform",
    "azure", "aws", "gcp", "linux", "windows", "bash", "powershell",
    "rest", "soap", "graphql", "grpc", "kafka", "rabbitmq",
    "scrum", "kanban", "safe", "itil", "prince2", "pmp",
    "fmea", "spc", "apqp", "ppap", "8d", "poka", "kaizen",
    "cnc", "hydraulik", "pneumatik", "mechatronik", "elektrotechnik",
    "maschinenbau", "verfahrenstechnik", "automatisierungstechnik",
    "konstruktion", "toleranzmanagement", "gdt",
    "react", "angular", "vue", "django", "flask", "fastapi", "spring",
    "dotnet", "nodejs", "opcua", "modbus", "profinet", "canbus",
    "ux", "ui", "figma", "sketch",
)

# Abkuerzungen, die wie ein Fachkuerzel aussehen, aber keines sind.
_STOPP_KUERZEL = frozenset({
    "gmbh", "ag", "kg", "ug", "se", "eg", "ohg", "mbh", "co",
    "der", "die", "das", "und", "oder", "sie", "wir", "ihr", "uns",
    "ein", "eine", "kein", "keine", "bei", "mit", "fuer", "von",
    "zum", "zur", "des", "dem", "den", "als", "auf", "aus", "ist",
    "eur", "chf", "usd", "pdf", "www", "http", "https", "html",
    "jan", "feb", "mrz", "apr", "mai", "jun", "jul", "aug",
    "sep", "okt", "nov", "dez", "mo", "di", "mi", "do", "fr",
    "ca", "ggf", "bzw", "inkl", "zzgl", "ff", "vgl", "usw", "etc",
    "id", "ra", "nr", "abs", "art", "tel", "fax", "str",
    "m/w/d", "w/m/d", "m/w/x", "fte", "vz", "tz",
})

# Vokabular des Benefits-Absatzes. Steht in fast jeder Anzeige und
# beschreibt nie eine Anforderung.
_BENEFIT = frozenset({
    "balance", "impulse", "urlaub", "gleitzeit", "jobrad", "bikeleasing",
    "kantine", "obst", "kaffee", "parkplatz", "zuschuss", "praemie",
    "weiterbildung", "entwicklungsmoeglichkeiten", "teamevents",
    "homeoffice", "flexibilitaet", "vergueltung", "verguetung",
    "altersvorsorge", "gesundheit", "sportangebot", "mitarbeiterrabatte",
    "onboarding", "duzkultur", "flache", "hierarchien", "start",
    "aufgaben", "profil", "benefits", "kontakt", "bewerbung",
})

# Ab wie vielen erkannten Begriffen ist eine Quote ueberhaupt eine
# Aussage? Darunter wird sie NICHT ausgewiesen (AK 7).
MINDEST_BEGRIFFE = 4


def anzeigenteil(text: str) -> str:
    """Nur die Anzeige, ohne den Notizteil dahinter (AK 6)."""
    if not text:
        return ""
    teile = _NOTIZ_TRENNER.split(str(text), maxsplit=1)
    return teile[0]


def _kandidaten(text: str) -> Iterable[str]:
    klein = text.lower()

    # 1) Normen als EIN Begriff, Schreibweise vereinheitlicht.
    for treffer in _NORM.findall(text):
        yield re.sub(r"[\s/-]+", " ", treffer.strip()).upper()

    # 2) Mehrwortbegriffe vor der Einzelwort-Zerlegung.
    for begriff in _MEHRWORT:
        if begriff in klein:
            yield begriff

    # 3) Kuratierte Einzelbegriffe.
    for wort in re.findall(r"[a-zA-ZäöüÄÖÜß+#.]{2,}", klein):
        bereinigt = wort.strip(".")
        if bereinigt in _FACHWORT:
            yield bereinigt

    # 4) Grossbuchstaben-Kuerzel (2-6 Zeichen), die kein Stoppwort sind.
    #    Fangen das ab, was die kuratierten Listen noch nicht kennen —
    #    ohne deutsche Substantive mitzunehmen, denn die sind nicht
    #    durchgehend gross.
    for kuerzel in re.findall(r"\b[A-Z][A-Z0-9]{1,5}\b", text):
        k = kuerzel.lower()
        if k in _STOPP_KUERZEL or k in _BENEFIT:
            continue
        if k.isdigit():
            continue
        yield k


def extrahiere_skills(text: str) -> list[str]:
    """Fachbegriffe aus einer Stellenbeschreibung, ohne Rauschen.

    Reihenfolge des Auftretens bleibt erhalten, Dubletten fallen weg.
    """
    roh = anzeigenteil(text or "")
    if not roh.strip():
        return []
    gesehen: list[str] = []
    for begriff in _kandidaten(roh):
        b = begriff.strip()
        if not b or b in _BENEFIT or b in _STOPP_KUERZEL:
            continue
        if b not in gesehen:
            gesehen.append(b)

    # Das Kuerzel einer Norm ist keine eigene Kompetenz, wenn die Norm
    # selbst schon erkannt wurde: "IEC 62304" und daneben "iec" waere
    # dieselbe Sache zweimal, einmal davon nichtssagend.
    normen = {g.split()[0].lower() for g in gesehen if " " in g and
              g.split()[0].isupper()}
    gesehen = [g for g in gesehen if g not in normen]

    # Teilphrasen entfernen: "engineering change management" macht
    # "change management" als eigenen Eintrag ueberfluessig und blaeht
    # den Nenner der Quote auf.
    mehrwort = [g for g in gesehen if " " in g]
    gesehen = [g for g in gesehen
               if not any(g != m and g in m for m in mehrwort)]
    return gesehen


def quote_belastbar(anzahl_begriffe: int) -> bool:
    """Reicht die Grundlage fuer eine Prozentangabe? (AK 7)

    Eine ehrliche Fehlanzeige ist besser als eine gerechnete Zahl ohne
    Grundlage — dasselbe Prinzip wie beim Bewerbungsbericht (v1.6.8).
    """
    return anzahl_begriffe >= MINDEST_BEGRIFFE
