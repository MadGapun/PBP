"""Regeln fuer jedes erzeugte Dokument (#1006).

Nutzer-Report vom 09.09.2026, an einem echten Lauf belegt: der erzeugte
Lebenslauf enthielt viermal die Zeichenfolge `None`, begann die
Berufserfahrung mit einer Station aus 2005, listete saemtliche Skills in
Speicherreihenfolge samt Satzfragmenten aus der Dokumentenextraktion und
zeigte ein Datum ohne Monat. **Das Ergebnis muss ohne Nachformatierung
versandfaehig sein.**

Die Regeln stehen hier als reine Funktionen, nicht als Absaetze in den
vier Erzeugern. Das ist der Punkt: dieselbe Regel viermal geschrieben
laeuft auseinander, und genau daraus sind #963, #991 und #992
entstanden. Ein Guard erzeugt am Ende ein echtes Dokument und prueft die
Regeln daran — nicht am Quelltext.

## Die `None`-Falle, weil sie lehrreich ist

    edu.get("degree", "")

sieht nach einem Vorgabewert aus und ist keiner. `dict.get` liefert den
Vorgabewert nur, wenn der SCHLUESSEL FEHLT. Steht die Spalte in der
Datenbank auf NULL, ist der Schluessel da und der Wert `None` — und
`f"{None} {None}"` ergibt `"None None"` mitten im Lebenslauf. Der
Ausdruck ist an Dutzenden Stellen im Export dieselbe stille Zusage, die
nie eingeloest wurde. Deshalb `text()`.

## Was diese Regeln NICHT tun

**Sie schreiben keine Prosa um.** Regel 8 (erste Person im Kurzprofil)
laesst sich pruefen, aber nicht automatisch herstellen: aus "Er verfuegt
ueber" wird maschinell kein guter Satz, sondern ein anderer Fehler. Der
Befund wird deshalb GEMELDET, nicht behoben — dasselbe Vorgehen wie bei
den wirkungslosen Reglern in #988.

**Sie erfinden keine Monate.** Steht im Profil nur ein Jahr, kommt ein
Jahr ins Dokument und die Luecke in den Befund. `01/2005` zu schreiben,
weil das Format MM/JJJJ verlangt, waere eine erfundene Angabe in einem
Bewerbungsdokument.
"""
from __future__ import annotations

import re

# Was nie in einem Dokument stehen darf. Kleinschreibung, verglichen wird
# der getrimmte Wert.
PLATZHALTER = {"none", "null", "nan", "leer", "n/a", "na", "-", "undefined"}

# Gedankenstriche als Satzzeichen. Zwei Ausnahmen, beide bewusst:
#
# * Der Bindestrich INNERHALB eines Wortes ("CAD-Integration") bleibt —
#   er ist kein Satzzeichen, sondern Teil der Schreibweise.
# * Der BIS-Strich zwischen zwei Datumsangaben ("04/2019 – heute") bleibt
#   ebenfalls. Er ist typografisch genau richtig, und ein Pruefer, der
#   ihn anmahnt, meldet bei korrektem Ergebnis Alarm — nach dem zweiten
#   Mal glaubt ihm niemand mehr (die Lehre aus #929).
#
# Gefunden hat diese zweite Ausnahme der Pruefer selbst, an meinem
# eigenen `zeitraum()`.
_DATUMSSEITE = re.compile(r"^(?:\d{1,2}/\d{4}|\d{4}|heute|laufend)$", re.I)
# Ein Strich mit Wortkontext links und rechts. Kein Lookbehind — der
# muesste feste Breite haben, und die Datumsformen sind verschieden lang.
_STRICH_MIT_KONTEXT = re.compile(r"(\S+)(\s+[–—]\s+|\s+-\s+(?=[A-ZÄÖÜ]))(\S+)")


def _ist_datumsspanne(links: str, rechts: str) -> bool:
    """Steht der Strich zwischen zwei Datumsangaben?"""
    return bool(_DATUMSSEITE.match(links.strip(",.;:"))
                and _DATUMSSEITE.match(rechts.strip(",.;:")))


def gedankenstrich_funde(zeile_text: str) -> list:
    """Striche, die als SATZZEICHEN stehen — Bis-Striche ausgenommen."""
    treffer = []
    for m in _STRICH_MIT_KONTEXT.finditer(zeile_text or ""):
        if _ist_datumsspanne(m.group(1), m.group(3)):
            continue
        treffer.append(m.group(0))
    return treffer

# Ein Skill ist ein Begriff, kein Satzteil. Diese Merkmale verraten
# Extraktions-Muell (#43/#129 kannten das Problem beim Anlegen; hier
# geht es um den Bestand, der schon drin ist).
_FRAGMENT_ZEICHEN = ("(", ")", "[", "]", ":", ";", "…")
_FRAGMENT_WOERTER = {
    "in", "im", "und", "oder", "mit", "von", "der", "die", "das", "des",
    "bei", "fuer", "für", "auf", "an", "zu", "als", "aus", "nach", "über",
}
MAX_SKILL_WOERTER = 5
MAX_SKILLS_JE_BLOCK = 12
MAX_PROJEKTE = 6

_MONATE = {
    "januar": 1, "februar": 2, "maerz": 3, "märz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12, "jan": 1, "feb": 2, "mrz": 3, "apr": 4,
    "jun": 6, "jul": 7, "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12,
}
LAUFEND = "heute"


# -- Regel 3: keine Platzhalter ---------------------------------------

def text(wert) -> str:
    """Jeder Wert, der ins Dokument geht, kommt hier durch.

    `None`, die ZEICHENKETTE "None" (so landet sie ueber f-Strings in
    Altbestaenden) und die uebrigen Platzhalter werden zu "". Ein
    fehlendes Feld entfaellt damit samt seinem Trennzeichen — es steht
    nicht als Wort im Dokument.
    """
    if wert is None:
        return ""
    gestutzt = str(wert).strip()
    if gestutzt.lower() in PLATZHALTER:
        return ""
    return gestutzt


def zeile(*teile, trenner: str = " | ") -> str:
    """Setzt eine Zeile aus Teilen, die fehlen duerfen.

    Der Grund fuer diese Funktion ist nicht das Zusammensetzen, sondern
    das TRENNZEICHEN: `f"{a} | {b}"` hinterlaesst bei leerem `b` ein
    " | " am Ende. So sah der gemeldete Lebenslauf aus.
    """
    vorhanden = [text(t) for t in teile]
    return trenner.join(t for t in vorhanden if t)


# -- Regel 5: Datumsformat --------------------------------------------

def datum(wert) -> str:
    """MM/JJJJ, wo Monat und Jahr bekannt sind.

    Ist nur ein Jahr bekannt, kommt das Jahr — **kein erfundener
    Monat**. In einem Bewerbungsdokument ist eine geraten wirkende
    Angabe teurer als eine unvollstaendige, und der Befund nennt die
    Luecke.
    """
    roh = text(wert)
    if not roh:
        return ""
    if roh.lower() in ("heute", "laufend", "aktuell", "present", "current"):
        return LAUFEND

    m = re.match(r"^(\d{4})-(\d{1,2})(?:-\d{1,2})?$", roh)      # 2005-03-01
    if m:
        return f"{int(m.group(2)):02d}/{m.group(1)}"
    m = re.match(r"^(\d{1,2})[./](\d{4})$", roh)                # 3/2005
    if m:
        return f"{int(m.group(1)):02d}/{m.group(2)}"
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$", roh)       # 01.03.2005
    if m:
        return f"{int(m.group(2)):02d}/{m.group(3)}"
    m = re.match(r"^([A-Za-zÄÖÜäöü]+)\s+(\d{4})$", roh)         # Maerz 2005
    if m and m.group(1).lower() in _MONATE:
        return f"{_MONATE[m.group(1).lower()]:02d}/{m.group(2)}"
    m = re.match(r"^(\d{4})$", roh)                             # 2005
    if m:
        return roh
    return roh                                                   # unveraendert


def nur_jahr(wert) -> bool:
    """Ist das eine Jahresangabe ohne Monat? (Befund, kein Fehler)"""
    return bool(re.match(r"^\d{4}$", datum(wert)))


def zeitraum(start, ende, laeuft_noch: bool = False) -> str:
    """Ein Zeitraum, der bei fehlendem Teil nicht zum Trennstrich wird."""
    a = datum(start)
    b = LAUFEND if laeuft_noch else datum(ende)
    if a and b:
        return f"{a} – {b}"
    return a or b or ""


def _sortierschluessel(eintrag: dict) -> tuple:
    """Neueste zuerst. Laufendes ganz oben.

    Parallele Zeitraeume duerfen die Sortierung nicht zerstoeren
    (Regel 4): sortiert wird nach dem BEGINN, absteigend, und bei
    gleichem Beginn nach dem Ende.
    """
    if eintrag.get("is_current"):
        return (2, 999999, 999999)
    d = datum(eintrag.get("start_date"))
    m = re.match(r"^(\d{2})/(\d{4})$", d)
    if m:
        beginn = int(m.group(2)) * 100 + int(m.group(1))
    elif re.match(r"^\d{4}$", d):
        beginn = int(d) * 100
    else:
        beginn = 0
    e = datum(eintrag.get("end_date"))
    m = re.match(r"^(\d{2})/(\d{4})$", e)
    if m:
        schluss = int(m.group(2)) * 100 + int(m.group(1))
    elif re.match(r"^\d{4}$", e):
        schluss = int(e) * 100
    else:
        schluss = 0
    return (1, beginn, schluss)


def absteigend(eintraege: list) -> list:
    """Regel 4: aktuelle Taetigkeit oben."""
    return sorted(eintraege or [], key=_sortierschluessel, reverse=True)


# -- Regel 1 + 2: Umlaute und Gedankenstriche -------------------------

def fliesstext(wert) -> str:
    """Fuer Prosa: Platzhalter raus, Umlaute her, Gedankenstriche weg."""
    roh = text(wert)
    if not roh:
        return ""
    from .umlaute import umlaute_reparieren
    roh, _ = umlaute_reparieren(roh)
    for fund in gedankenstrich_funde(roh):
        links, rechts = fund.split(maxsplit=1)
        roh = roh.replace(fund, links + ", " + rechts.lstrip("–— "), 1)
    return roh


# -- Regel 6 + 7: Kompetenzen -----------------------------------------

def ist_fragment(name) -> bool:
    """Ein Skill ist ein Begriff, kein Satzteil.

    Gemeldet wurden `in ERP-Systemen (Infor` und `CAD-Integration)` —
    beides Bruchstuecke aus der Dokumentenextraktion. Erkennbar an
    unpaarigen Klammern, Satzzeichen, einem Funktionswort am Anfang
    oder schlichter Laenge.
    """
    n = text(name)
    if not n:
        return True
    if n.count("(") != n.count(")") or n.count("[") != n.count("]"):
        return True
    if any(z in n for z in _FRAGMENT_ZEICHEN):
        return True
    woerter = n.split()
    if len(woerter) > MAX_SKILL_WOERTER:
        return True
    if woerter and woerter[0].lower() in _FRAGMENT_WOERTER:
        return True
    return False


def kompetenzen(skills: list, relevanz=None,
                grenze: int = MAX_SKILLS_JE_BLOCK) -> list:
    """Regel 6 und 7: gruppiert, gefiltert, begrenzt, priorisiert.

    Rueckgabe: [(Bezeichnung, [Namen]), ...] in der Reihenfolge, in der
    sie ins Dokument sollen. `relevanz` ist eine Funktion Skill -> Zahl
    (kleiner ist wichtiger); ohne sie bleibt die Reihenfolge im Block
    unveraendert.
    """
    bezeichnungen = {
        "fachlich": "Fachlich", "methodisch": "Methodisch",
        "soft_skill": "Soft Skills", "sprache": "Sprachen",
        "tool": "Tools & Software", "zertifizierung": "Zertifizierungen",
        "fuehrung": "Fuehrung", "sonstige": "Weitere",
    }
    nach_kategorie: dict = {}
    for s in skills or []:
        name = text(s.get("name"))
        if not name or ist_fragment(name):
            continue          # Regel 7: Fragmente gehoeren nicht ins Dokument
        kat = text(s.get("category")) or "sonstige"
        nach_kategorie.setdefault(kat, []).append(s)

    bloecke = []
    for kat, eintraege in nach_kategorie.items():
        if relevanz is not None:
            eintraege = sorted(eintraege, key=relevanz)
        namen, gesehen = [], set()
        for s in eintraege:
            name = text(s.get("name"))
            if name.lower() in gesehen:
                continue      # dieselbe Kompetenz nicht zweimal
            gesehen.add(name.lower())
            namen.append(name)
            if len(namen) >= grenze:
                break
        if namen:
            bloecke.append((bezeichnungen.get(kat, kat.capitalize()), namen))

    if relevanz is not None:
        bloecke.sort(key=lambda b: min(
            (relevanz(s) for s in nach_kategorie.get(
                next((k for k, v in bezeichnungen.items() if v == b[0]), b[0]),
                [])), default=99))
    return bloecke


def projekte(alle: list, relevanz=None, grenze: int = MAX_PROJEKTE) -> list:
    """Regel 9: kuratiert statt vollstaendig."""
    liste = [p for p in (alle or []) if text(p.get("name")) or text(p.get("title"))]
    if relevanz is not None:
        liste = sorted(liste, key=relevanz)
    return liste[:grenze]


# -- Der Pruefer ueber ein fertiges Dokument --------------------------

_DRITTE_PERSON = re.compile(
    r"\b(er|sie)\s+(verfuegt|verfügt|bringt|hat|ist|arbeitet|verantwortet)\b",
    re.IGNORECASE)


def pruefe_text(inhalt: str) -> list:
    """Prueft den Text eines erzeugten Dokuments gegen die Regeln.

    Rueckgabe: Liste von Befunden `{regel, fund, stelle}`. Leer heisst
    sauber. Der Pruefer arbeitet auf dem ERGEBNIS, nicht auf dem
    Quelltext — nur so faellt auf, wenn ein Erzeuger die Regeln umgeht
    (DoD 8c).
    """
    befunde = []
    for zeilennr, z in enumerate(inhalt.split("\n"), 1):
        for wort in re.findall(r"\b\w+\b", z):
            if wort.lower() in PLATZHALTER and wort.lower() not in ("na", "-"):
                befunde.append({"regel": 3, "fund": wort, "stelle": zeilennr,
                                "hinweis": "Platzhalter im Dokument."})
        for fund in gedankenstrich_funde(z):
            befunde.append({"regel": 2, "fund": fund[:60],
                            "stelle": zeilennr,
                            "hinweis": "Gedankenstrich als Satzzeichen. "
                                       "Ein Bis-Strich zwischen zwei Daten "
                                       "zaehlt bewusst nicht."})
        if _DRITTE_PERSON.search(z):
            befunde.append({"regel": 8, "fund": z.strip()[:60],
                            "stelle": zeilennr,
                            "hinweis": "Kurzprofil in der dritten Person. "
                                       "Wird bewusst NICHT automatisch "
                                       "umgeschrieben — daraus wird "
                                       "maschinell kein guter Satz."})
    from .umlaute import KANDIDAT_RE, UMLAUT_REPAIR_MAP, WORT_RE
    verdacht = set()
    for m in WORT_RE.finditer(inhalt):
        wort = m.group(0)
        if wort.lower() in UMLAUT_REPAIR_MAP:
            # Steht in der Liste und trotzdem im Dokument: hier hat ein
            # Erzeuger `fliesstext()` umgangen.
            befunde.append({"regel": 1, "fund": wort, "stelle": 0,
                            "hinweis": "Umschriebener Umlaut im Dokument — "
                                       "dieser Text ist an den Regeln "
                                       "vorbeigelaufen."})
        elif len(wort) >= 5 and KANDIDAT_RE.search(wort.lower()):
            verdacht.add(wort.lower())
    if verdacht:
        # Bewusst KEIN harter Befund: eine Positivliste kann nur finden,
        # was in ihr steht ("Poesie" und "Duell" sind keine Umlaute).
        # Der Verdacht gehoert trotzdem gemeldet, sonst waechst die
        # Luecke unbemerkt — dieselbe Rolle wie die
        # Kuratierungs-Kandidaten aus #742.
        befunde.append({
            "regel": 1, "stelle": 0, "weich": True,
            "fund": ", ".join(sorted(verdacht)[:10]),
            "hinweis": "Verdacht auf umschriebene Umlaute. Diese Woerter "
                       "stehen NICHT in der kuratierten Liste — bitte "
                       "ansehen und die Liste ergaenzen, wenn es welche "
                       "sind.",
        })
    return befunde


def pruefe_docx(pfad) -> dict:
    """Regel-Pruefung ueber eine DOCX-Datei."""
    from pathlib import Path
    from .office_text import LESER

    p = Path(pfad)
    if not p.is_file():
        return {"fehler": f"Datei nicht gefunden: {p}"}
    leser = LESER.get(p.suffix.lower())
    if leser is None:
        return {"fehler": f"Format {p.suffix} wird nicht gelesen."}
    inhalt = leser(p) or ""
    befunde = pruefe_text(inhalt)
    return {
        "datei": str(p),
        "zeichen": len(inhalt),
        "sauber": not befunde,
        "befunde": befunde[:50],
        "anzahl_befunde": len(befunde),
    }
