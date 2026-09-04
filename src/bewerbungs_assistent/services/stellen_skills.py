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
from typing import Iterable, Optional

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
    # v1.7.30 (#971): Floskeln der TEXTSORTE Stellenanzeige. Diese
    # Liste bindet sich bewusst NICHT an ein Berufsfeld — "Team" und
    # "Fortbildungen" stehen in einer Pflege-Anzeige genauso wie in
    # einer IT-Anzeige. Sie bleibt damit gueltig, egal wer sucht.
    "team", "teams", "fortbildungen", "fortbildung", "erfahrung",
    "kenntnisse", "faehigkeiten", "fähigkeiten", "einsatz",
    "unternehmen", "arbeitgeber", "stelle", "position", "taetigkeit",
    "tätigkeit", "verantwortung", "zusammenarbeit", "umfeld",
    "moeglichkeiten", "möglichkeiten", "weiterentwicklung", "chancen",
    "wochenstunden", "arbeitszeit", "verguetung", "bezahlung",
    "abschluss", "ausbildung", "studium", "berufserfahrung",
    "mitarbeiter", "mitarbeiterinnen", "kolleginnen", "kollegen",
    "kunden", "kundinnen", "bereich", "abteilung", "standort",
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


def _kandidaten(text: str, gelernt: Optional[set] = None) -> Iterable[str]:
    klein = text.lower()

    # 0) Gelerntes zuerst — Mehrwortbegriffe vor der Zerlegung.
    for begriff in sorted(gelernt or (), key=len, reverse=True):
        if len(begriff) >= MIN_LAENGE and begriff in klein:
            yield begriff

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


def extrahiere_skills(text: str, vokabular: Optional[set] = None) -> list[str]:
    """Fachbegriffe aus einer Stellenbeschreibung, ohne Rauschen.

    Reihenfolge des Auftretens bleibt erhalten, Dubletten fallen weg.

    v1.7.30 (#971): `vokabular` erweitert die kuratierten Listen um das,
    was aus Profil und Bestand gelernt wurde. Ohne Argument verhaelt
    sich die Funktion wie bisher — Aufrufer, die kein Vokabular haben,
    verlieren nichts.
    """
    roh = anzeigenteil(text or "")
    if not roh.strip():
        return []
    gesehen: list[str] = []
    for begriff in _kandidaten(roh, vokabular):
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


# ══ Aus dem Bestand lernen (#971, v1.7.30) ══════════════════════════
#
# Die kuratierten Listen oben decken ein Berufsfeld ab. Gemessen an
# sechs Lebenslaeufen quer durch den Arbeitsmarkt erkannten sie fuer
# Pflege, Erziehung und Grafik NULL Begriffe; die drei Treffer bei den
# uebrigen fielen durch die Abkuerzungs-Regel an, nicht durch die Liste.
#
# Dieselbe Umkehr wie bei `issue_text_pruefen` (#946) und bei den
# Berufsbezeichnungen (#969): nicht gegen eine gepflegte Liste pruefen,
# sondern gegen den vorhandenen Bestand. Die Begriffe eines Menschen
# stehen in seinem eigenen Lebenslauf; was in seinem Berufsfeld gefragt
# ist, steht in den Anzeigen, die PBP ohnehin gesammelt hat.
#
# Eine Liste ist immer nur so gut wie ihre letzte Pflege. Ein Bestand
# waechst von allein, und zwar in genau dem Feld, in dem gesucht wird.

# In wie vielen Anzeigen muss ein Begriff vorkommen, um als Fachbegriff
# zu gelten? Einmal ist Zufall.
MIN_ANZEIGEN = 3

# Und in hoechstens wie vielen? Was in fast jeder Anzeige steht, ist
# Floskel und kein Fachbegriff ("Team", "Erfahrung", "Kunden").
MAX_ANTEIL = 0.4

# Ein Fachbegriff hat Substanz. Kuerzer als vier Zeichen ist entweder
# ein Kuerzel (die faengt die Grossbuchstaben-Regel ab) oder Rauschen.
MIN_LAENGE = 4

_WORT = re.compile(r"[A-ZÄÖÜ][a-zäöüß]{3,}(?:-[A-ZÄÖÜ][a-zäöüß]+)?")


def _rohbegriffe(text: str) -> set[str]:
    """Kandidaten einer einzelnen Anzeige: grossgeschriebene Woerter.

    Im Deutschen ist das jedes Substantiv — als Kandidatenmenge taugt
    das, als ERGEBNIS nicht (genau daran scheiterte die alte Fassung).
    Die Auswahl trifft erst die Haeufigkeit ueber viele Anzeigen.
    """
    roh = anzeigenteil(text or "")
    if not roh.strip():
        return set()
    treffer = set()
    for w in _WORT.findall(roh):
        klein = w.lower()
        if (len(w) >= MIN_LAENGE and klein not in _BENEFIT
                and klein not in _STOPP_KUERZEL):
            treffer.add(w)
    return treffer


def lerne_aus_bestand(db, *, limit: int = 400) -> set[str]:
    """Fachvokabular aus den gesammelten Anzeigen ableiten.

    Ein Begriff zaehlt, wenn er in mehreren Anzeigen vorkommt, aber
    nicht in fast allen: das erste schliesst Zufall aus, das zweite
    Floskeln. Was uebrig bleibt, ist das, was dieses Berufsfeld von
    anderen unterscheidet — unabhaengig davon, welches Feld es ist.
    """
    try:
        stellen = (db.get_active_jobs() or [])[:limit]
    except Exception:
        return set()
    beschreibungen = [
        f"{s.get('title') or ''}\n{s.get('description') or ''}"
        for s in stellen
        if (s.get("description") or "").strip()
    ]
    if len(beschreibungen) < MIN_ANZEIGEN:
        return set()

    haeufigkeit: dict[str, int] = {}
    for text in beschreibungen:
        for begriff in _rohbegriffe(text):
            haeufigkeit[begriff] = haeufigkeit.get(begriff, 0) + 1

    obergrenze = max(MIN_ANZEIGEN, int(len(beschreibungen) * MAX_ANTEIL))
    return {b.lower() for b, n in haeufigkeit.items()
            if MIN_ANZEIGEN <= n <= obergrenze}


def aus_profil(profil: Optional[dict]) -> set[str]:
    """Die Begriffe, die der Mensch selbst aufgeschrieben hat.

    Die verlaesslichste Quelle fuer sein Berufsfeld — und die einzige,
    die auf gar kein Feld kalibriert ist.
    """
    begriffe: set[str] = set()
    for skill in (profil or {}).get("skills") or []:
        name = ((skill or {}).get("name") or "").strip()
        if len(name) >= MIN_LAENGE:
            begriffe.add(name.lower())
    for pos in (profil or {}).get("positions") or []:
        for feld in ("title", "technologies"):
            wert = (pos or {}).get(feld) or ""
            for teil in re.split(r"[,;/]", str(wert)):
                teil = teil.strip()
                if len(teil) >= MIN_LAENGE and len(teil.split()) <= 3:
                    begriffe.add(teil.lower())
    return begriffe


def vokabular(db=None, profil: Optional[dict] = None) -> set[str]:
    """Alles zusammen: kuratierter Startwert, Profil, Bestand.

    Die kuratierten Listen bleiben als STARTWERT — sie sind fuer ihr
    Feld richtig und kosten nichts. Sie sind nur nicht mehr die Grenze.
    """
    erg = {b.lower() for b in _FACHWORT} | {b.lower() for b in _MEHRWORT}
    if profil:
        erg |= aus_profil(profil)
    if db is not None:
        erg |= lerne_aus_bestand(db)
    return erg
