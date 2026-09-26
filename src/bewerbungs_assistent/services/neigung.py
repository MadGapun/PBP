"""Was die Wortlisten uebersehen: das Signal aus dem eigenen Verhalten.

Nutzerantwort vom 16.09.2026 auf die Frage, was "Neigungen" heisst:

    "die beworbenen Stellen enthalten ein Signal, das die Wortlisten
    nicht abbilden ... eine Neigung zu bestimmten Stellen, die sich aus
    vielem ergibt und die ich selbst nicht praeziser benennen kann."

Der Beleg liegt im Bestand: nach der Kriterienueberarbeitung vom
15.09.2026 stehen ein Multiprojektleiter und ein Transformation Manager
bei Fachwert 0,0 — und auf beide hat sich der Mensch beworben. Eine
Bewertung, die das eigene Verhalten kennt, haette sie nicht auf 0
gesetzt.

## Vier Festlegungen, alle vom Nutzer

**Ausschliesslich nach oben.** Das Signal darf einen Fachwert heben, nie
senken. Woertlich: es soll nichts unterschlagen werden, und es soll
nicht bevormunden. Ein Signal, das nur hebt, macht sichtbar, was die
Wortlisten uebersehen haben, und kann keine ungewoehnliche Stelle
wegdruecken, nur weil sie keiner frueheren aehnelt. Damit ist zugleich
der typische Fehler lernender Verfahren ausgeschlossen: jemanden auf
das festzunageln, was er bisher gemacht hat.

**Kein dritter Indikator.** Es fliesst in den Fachwert ein, nicht
daneben. Ausdruecklicher Wunsch: einfacher, nicht komplizierter.

**Nachvollziehbar.** Es erscheint als eigener Faktor mit Beleg — "aehnelt
7 Stellen, auf die du dich beworben hast". Wer sieht, dass die
Aehnlichkeit an einem unerwuenschten Wort haengt, kann gegensteuern.

**Mindestbasis.** Unterhalb einer Mindestzahl beworbener Stellen bleibt
das Signal aus, statt aus wenigen Faellen ein Muster zu erfinden.

## Was ausdruecklich NICHT eingeht

Die **Ablehnungsgruende** — sie sind ueberwiegend Rahmenaussagen (zu
weit, Gehalt, Zeitarbeit) und wuerden im Fachwert wieder vermischen, was
#1052 trennt. Sie wirken weiter ueber die Regler und das
Wiedergaenger-Muster aus #671.

Die **Detailurteile aus #1007** — sie stehen bereits als eigene Aussage
neben dem Score. Sie in die Zahl zu ziehen hiesse, dasselbe zweimal zu
zaehlen.
"""
from __future__ import annotations

import re
import time
from collections import Counter

# Ab wie vielen beworbenen Stellen aus dem Verhalten ein Muster wird.
# Darunter bleibt das Signal aus — dieselbe Regel wie beim Fachdaumen,
# und aus demselben Grund: aus vier Faellen ein Muster zu lesen heisst,
# einen Einzelfall zu verkleiden.
MIN_BEWORBEN = 10

# Ein Begriff, der in mehr als diesem Anteil ALLER Stellen vorkommt,
# unterscheidet nichts — auch wenn er kein Stoppwort ist. Dieselbe
# Schwelle wie in `keyword_vorschlaege`.
ZU_ALLGEMEIN = 0.7

# Wie oft haeufiger ein Begriff in den beworbenen Stellen vorkommen
# muss als in den aussortierten, damit er als unterscheidend gilt.
MIN_VERHAELTNIS = 2.0

# Wieviele unterscheidende Begriffe hoechstens ins Profil kommen. Mehr
# waeren nicht praeziser, nur langsamer — und die Begruendung unlesbar.
MAX_BEGRIFFE = 60

# Ab wievielen gemeinsamen Begriffen zwei Stellen als aehnlich gelten.
MIN_GEMEINSAM = 2

# Bei wievielen aehnlichen Stellen das Signal seinen vollen Wert
# erreicht. Darueber waechst es nicht weiter: ob eine Stelle zwanzig
# oder fuenfzig frueheren aehnelt, sagt dasselbe.
VOLLE_WIRKUNG_AB = 5

# Der volle Wert, als Anteil dessen, was EIN Pflichttreffer wert ist.
# Relativ und nicht absolut, aus demselben Grund wie in `muss_tor`: bei
# einer kurzen MUSS-Liste ist jeder absolute Wert daneben zu gross.
# Hoechstens ein Pflichttreffer — ein Verhaltenssignal darf sichtbar
# machen, nicht ueberstimmen.
ANTEIL_EINES_TREFFERS = 1.0

CACHE_KEY = "neigung_profil_cache"
CACHE_MAX_ALTER_STUNDEN = 24

# Fuellwoerter und Stellenanzeigen-Floskeln. Ein Begriff, der in jeder
# zweiten Anzeige steht, unterscheidet nichts.
STOPPWOERTER = {
    "und", "oder", "der", "die", "das", "den", "dem", "des", "ein", "eine",
    "einer", "einem", "einen", "ist", "sind", "war", "waren", "hat", "habe",
    "haben", "wird", "werden", "wurde", "wurden", "mit", "ohne", "von", "vor",
    "nach", "fuer", "für", "als", "bei", "zur", "zum", "zu", "auf", "aus",
    "ueber", "über", "unter", "durch", "an", "am", "im", "in", "ins",
    "nicht", "auch", "sich", "wir", "sie", "uns", "ihr", "ihre", "ihren",
    "ihrer", "unser", "unsere", "unseren", "unserer", "unserem", "unseres",
    "deine", "dein", "dich", "dir", "du", "diese", "dieser", "diesem",
    "team", "stelle", "stellen", "job", "jobs", "position", "rolle",
    "aufgabe", "aufgaben", "taetigkeit", "taetigkeiten",
    "anforderung", "anforderungen", "kenntnisse", "kenntnis", "erfahrung",
    "erfahrungen", "kollege", "kollegen", "kolleginnen", "mitarbeiter",
    "mitarbeitern", "mitarbeiterinnen", "kunde", "kunden", "kundinnen",
    "partner", "partnern", "unternehmen", "firma", "gmbh", "co", "kg",
    "ohg", "bereich", "bereiche", "abteilung", "abteilungen",
    "projekt", "projekte", "projekten", "arbeit", "arbeiten",
    "arbeitsplatz", "arbeitsplaetze", "moeglichkeit", "moeglichkeiten",
    "deutsch", "deutsche", "deutschen", "english", "englisch",
    "bieten", "bietet", "suchen", "sucht", "gerne", "gern",
    "sowie", "sowohl", "ebenso", "erstellung", "erstellen", "umsetzung",
    "umsetzen", "durchfuehrung", "verantwortung", "verantwortlich",
    "qualifikation", "qualifikationen", "ausbildung",
    "stunden", "tage", "woche", "wochen", "monat", "monaten", "jahr",
    "jahre", "jahren", "montag", "dienstag", "mittwoch", "donnerstag",
    "freitag", "macht", "machen", "geht", "gehen", "kommt", "kommen",
    "gibt", "geben", "nehmen", "nimmt", "kann", "koennen", "muss",
    "muessen", "soll", "sollen", "will", "wollen",
}


def begriffe(text: str) -> list:
    """Die inhaltstragenden Woerter eines Textes.

    Mindestens fuenf Zeichen — kuerzere sind fast immer Fuellwoerter,
    und eine Liste, die jedes davon aufzaehlt, wird nie fertig.
    """
    woerter = re.findall(r"[a-zA-ZäöüÄÖÜß]{5,}", (text or "").lower())
    return [w for w in woerter if w not in STOPPWOERTER]


def _text(job: dict) -> str:
    # Titel UND Anzeigentext: der Titel allein traegt zu wenig, der
    # ganze Text zu viel Rauschen. Dieselbe Grenze wie in
    # `keyword_vorschlaege`.
    return f"{job.get('title', '')} {(job.get('description') or '')[:1500]}"


def profil_bauen(beworben: list, aussortiert: list, hintergrund: list) -> dict:
    """Welche Begriffe unterscheiden deine Bewerbungen von deinen Absagen?

    Nicht "welche Begriffe kommen in Bewerbungen vor" — das waeren die
    haeufigsten Woerter der Sprache. Gesucht ist der UNTERSCHIED.

    Args:
        hintergrund: Stellen, an denen gemessen wird, wie gewoehnlich ein
            Begriff ist — **ohne die beworbenen**. Das ist kein Detail:
            gefunden von der Gegenprobe. Nimmt man die beworbenen mit
            hinein und sind sie in der Ueberzahl, ueberschreiten
            ausgerechnet IHRE Begriffe die Allgemeinheitsschwelle und
            fallen heraus. Bei 60 beworbenen gegen 10 aussortierte blieb
            vom Profil fast nichts uebrig, und das Signal war still 0 —
            also genau dann kaputt, wenn jemand viel gearbeitet hat.
    """
    if len(beworben) < MIN_BEWORBEN:
        return {
            "begriffe": [],
            "beworben": len(beworben),
            "grundlage_fehlt": (
                f"Nur {len(beworben)} beworbene Stellen mit Text — unter "
                f"{MIN_BEWORBEN} wäre jedes Muster die Verkleidung "
                "einzelner Fälle. Das Signal bleibt aus."),
        }

    # Gemessen wird am Hintergrund OHNE die beworbenen Stellen (siehe
    # Args). Ist er zu duenn, um etwas ueber Allgemeinheit zu sagen,
    # entfaellt der Filter ganz — das Verhaeltnis zu den Aussortierten
    # unten faengt allgemeine Begriffe ohnehin ab, und ein Filter auf zu
    # kleiner Grundlage wirft die falschen Woerter weg.
    beworbene_texte = {_text(j) for j in beworben}
    rest = [j for j in hintergrund if _text(j) not in beworbene_texte]
    zu_allgemein = set()
    if len(rest) >= MIN_BEWORBEN:
        haeufigkeit = Counter()
        for job in rest:
            for begriff in set(begriffe(_text(job))):
                haeufigkeit[begriff] += 1
        zu_allgemein = {b for b, n in haeufigkeit.items()
                        if n / len(rest) > ZU_ALLGEMEIN}

    gut = Counter()
    for job in beworben:
        for begriff in set(begriffe(_text(job))):
            gut[begriff] += 1
    schlecht = Counter()
    for job in aussortiert:
        for begriff in set(begriffe(_text(job))):
            schlecht[begriff] += 1

    min_treffer = max(2, len(beworben) // 4)
    unterscheidend = []
    for begriff, anzahl in gut.most_common():
        if begriff in zu_allgemein or anzahl < min_treffer:
            continue
        verhaeltnis = anzahl / max(1, schlecht.get(begriff, 0))
        if verhaeltnis >= MIN_VERHAELTNIS:
            unterscheidend.append(begriff)
        if len(unterscheidend) >= MAX_BEGRIFFE:
            break

    # Die Begriffsmengen der beworbenen Stellen, eingeschraenkt auf die
    # unterscheidenden Begriffe. Nur damit laesst sich spaeter sagen,
    # WIEVIELEN Stellen eine neue aehnelt — und das ist der Beleg, den
    # der Nutzer sehen will.
    menge = set(unterscheidend)
    mengen = [sorted(set(begriffe(_text(j))) & menge) for j in beworben]
    return {
        "begriffe": unterscheidend,
        "beworben": len(beworben),
        "aussortiert": len(aussortiert),
        "mengen": [m for m in mengen if m],
    }


def profil(db, force_refresh: bool = False) -> dict:
    """Das Neigungsprofil — abgelegt, nicht bei jedem Blick neu gerechnet.

    Wer schreibt, frischt auf; wer liest, nimmt den abgelegten Stand.
    Ein Score darf nicht an einem Bestandsscan haengen (v1.7.36 MERKE 3).
    """
    if not force_refresh:
        abgelegt = _aus_cache(db)
        if abgelegt is not None:
            return abgelegt
    daten = _sammeln(db)
    ergebnis = profil_bauen(*daten)
    _in_cache(db, ergebnis)
    return ergebnis


def _sammeln(db):
    """Beworbene, aussortierte und alle Stellen — je mit Text."""
    try:
        bewerbungen = db.get_applications() or []
    except Exception:
        return [], [], []
    beworbene_hashes = {b.get("job_hash") for b in bewerbungen
                        if b.get("job_hash")}
    beworben = []
    for hash_ in beworbene_hashes:
        try:
            stelle = db.get_job(hash_)
        except Exception:
            continue
        if stelle and (stelle.get("description") or stelle.get("title")):
            beworben.append(stelle)

    try:
        aussortiert = [j for j in (db.get_dismissed_jobs() or [])
                       if j.get("hash") not in beworbene_hashes
                       and "bewerbung_erstellt" not in
                       str(j.get("dismiss_reason") or "")]
    except Exception:
        aussortiert = []
    try:
        aktiv = db.get_active_jobs(exclude_blacklisted=True) or []
    except Exception:
        aktiv = []
    # Der Hintergrund ist bewusst OHNE die beworbenen Stellen: an ihm
    # wird gemessen, wie gewoehnlich ein Begriff ist. Waeren sie darin,
    # gaelten ihre eigenen Begriffe als gewoehnlich.
    hashes = {j.get("hash") for j in beworben}
    hintergrund = [j for j in aktiv + aussortiert if j.get("hash") not in hashes]
    return beworben, aussortiert, hintergrund


def _aus_cache(db):
    try:
        roh = db.get_profile_setting(CACHE_KEY)
    except Exception:
        return None
    if not isinstance(roh, dict):
        return None
    alter = time.time() - float(roh.get("_stand", 0) or 0)
    if alter > CACHE_MAX_ALTER_STUNDEN * 3600:
        return None
    return roh.get("profil")


def _in_cache(db, ergebnis: dict) -> None:
    try:
        db.set_profile_setting(CACHE_KEY,
                               {"_stand": time.time(), "profil": ergebnis})
    except Exception:  # pragma: no cover — ein Cache stoppt nie eine Rechnung
        pass


def signal(job: dict, neigungsprofil: dict, muss_gewicht: float = 0) -> dict:
    """Wieviel hebt das eigene Verhalten diese Stelle?

    Returns:
        {"punkte": .., "aehnliche": .., "begriffe": [..], "grund": ".."}
        `punkte` ist NIE negativ — das ist die Festlegung des Nutzers,
        nicht eine Eigenschaft der Rechnung.
    """
    leer = {"punkte": 0.0, "aehnliche": 0, "begriffe": [], "grund": ""}
    if not neigungsprofil or neigungsprofil.get("grundlage_fehlt"):
        if neigungsprofil and neigungsprofil.get("grundlage_fehlt"):
            leer["grund"] = neigungsprofil["grundlage_fehlt"]
        return leer
    menge = set(neigungsprofil.get("begriffe") or [])
    if not menge:
        return leer

    eigene = set(begriffe(_text(job))) & menge
    # ABKUERZUNG, keine Regel — und der Unterschied gehoert hingeschrieben.
    # Die eigentliche Pruefung steht unten je beworbener Stelle. Weil
    # jede dieser Mengen eine Teilmenge der Profilbegriffe ist, kann bei
    # weniger als MIN_GEMEINSAM eigenen Begriffen ohnehin keine davon auf
    # zwei gemeinsame kommen: die Bedingung hier ist rechnerisch
    # impliziert. Sie steht nur da, damit nicht fuer jede Stelle des
    # Bestands alle beworbenen durchlaufen werden.
    #
    # Die Gegenprobe hat sie deshalb zu Recht als stumm gemeldet — kein
    # Testfall kann sie isolieren. Sie bleibt als Abkuerzung stehen
    # statt als Mechanismus, dem man vertraut, ohne dass ihn etwas
    # prueft (v1.7.108 MERKE 5).
    if len(eigene) < MIN_GEMEINSAM:
        return leer

    aehnlich = [m for m in (neigungsprofil.get("mengen") or [])
                if len(eigene & set(m)) >= MIN_GEMEINSAM]
    if not aehnlich:
        return leer

    voll = ANTEIL_EINES_TREFFERS * float(muss_gewicht or 0)
    anteil = min(1.0, len(aehnlich) / VOLLE_WIRKUNG_AB)
    punkte = round(max(0.0, voll * anteil), 1)
    gemeinsam = sorted(eigene)[:6]
    return {
        "punkte": punkte,
        "aehnliche": len(aehnlich),
        "begriffe": gemeinsam,
        "grund": (
            f"Aehnelt {len(aehnlich)} Stellen, auf die du dich beworben "
            f"hast (gemeinsam: {', '.join(gemeinsam)}). Das hebt den "
            "Fachwert und kann ihn nie senken."),
    }
