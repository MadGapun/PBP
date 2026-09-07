"""Wie heisst derselbe Beruf noch? (#969, v1.7.28)

Belegt in #968: eine Pflegekraft traegt "Pflegefachkraft" als
MUSS-Begriff ein — das Naheliegendste. "Gesundheits- und
Krankenpflegerin" bekommt Score 0 und erscheint nicht in der Liste,
obwohl es derselbe Beruf ist (die Amtsbezeichnung vor der
Pflegeberufereform 2020). Das MUSS-Tor kannte Synonyme nur fuer vier
Produktnamen, also ausschliesslich fuer ein technisches Berufsfeld.

**Warum keine gepflegte Liste.** Dieselbe Lehre wie bei
`issue_text_pruefen` (#946) und bei der Kompetenz-Erkennung: eine
kuratierte Synonymliste im Repo deckt genau die Berufsfelder ab, an die
jemand gedacht hat, und ist immer nur so gut wie ihre letzte Pflege.

**Warum nicht BERUFENET.** Naheliegend waere die Klassifikation der
Berufe. Live geprueft am 04.09.2026: die Berufe-Endpunkte der
Bundesagentur antworten mit dem oeffentlichen Jobsuche-Schluessel
durchgehend 403 beziehungsweise 404. Sie sind also nicht ohne
Registrierung erreichbar, und PBP soll ohne Anmeldung laufen.

**Was stattdessen funktioniert.** Die Jobsuche-API selbst liefert zu
jeder Suchanfrage eine Facette `beruf` — die amtlichen
Berufsbezeichnungen der Treffer, nach Haeufigkeit sortiert. Fuer
"Pflegefachkraft" sind das (live gemessen):

    9373  Altenpfleger/in
    7218  Pflegefachmann/-frau (Altenpflege)
    6723  Gesundheits- und Krankenpfleger/in
    1728  Krankenschwester/-pfleger

Also genau die Bezeichnungen, an denen das MUSS-Tor scheiterte. Der
Markt selbst sagt, wie derselbe Beruf noch heisst — ohne Registrierung,
ohne Pflege und in jedem Berufsfeld.

**Nachtrag v1.7.36 (#987) — was diese Annahme gekostet hat.** Der Absatz
oben stimmt genau dann, wenn der Suchbegriff SELBST ein Beruf ist. Fuer
"Pflegefachkraft" ist die Facette die Liste der Alternativbezeichnungen.
Fuer "PLM" ist sie die Liste der Berufe, die mit PLM arbeiten — live
gemessen am 07.09.2026: IT-Berater, Ingenieur/in - Maschinenbau,
Ingenieur/in - Elektrotechnik, Informatiker/in, Konstrukteur/in. Als
MUSS-Synonyme eingesetzt, oeffnete damit **jede Ingenieursanzeige** das
Tor: 86 von 86 Stellen eines Laufs waren zu hoch bewertet, im Maximum um
105 Punkte.

Die Facette beantwortet also "wer arbeitet damit", nicht "wie heisst das
noch" — und nur wenn der Begriff ein Beruf ist, sind das dieselbe Frage.
Seither muessen ZWEI Tore aufgehen, bevor eine Bezeichnung als Synonym
zaehlt (`_ist_alternativbezeichnung` und `MIN_SPITZENANTEIL`), und
zerlegt wird nur noch die SCHREIBWEISE, nicht die Bezeichnung.
"""
from __future__ import annotations

import itertools
import logging
import re
import threading
from typing import Optional

logger = logging.getLogger(__name__)

API_URL = ("https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
           "/pc/v6/jobs")
API_KEY = "jobboerse-jobsuche"  # oeffentlich, ohne Registrierung
_USER_AGENT = ("Jobsuche/2.9.3 (de.arbeitsagentur.jobboerse; build:1078; "
               "iOS 15.1.0)")

# Wie viele Bezeichnungen uebernehmen? Genug fuer die gaengigen
# Schreibweisen, wenig genug, dass ein MUSS-Begriff nicht zum Freifahrt-
# schein wird. Die Facette ist nach Haeufigkeit sortiert, die vorderen
# Eintraege sind die belastbaren.
MAX_SYNONYME = 8

# Ab wie vielen Treffern zaehlt eine Bezeichnung? Ein Beruf, der in drei
# von 25.000 Anzeigen vorkommt, ist ein Ausreisser und kein Synonym.
MIN_ANTEIL = 0.02

# v1.7.36 (#987): Wie stark muss sich die Facette auf ihre haeufigste
# Bezeichnung konzentrieren, damit der Begriff ueberhaupt als BERUF
# durchgeht? Ein Beruf zieht seine Alternativbezeichnungen an sich, eine
# Technologie streut ueber alle Berufe, die sie einsetzen. Gemessen am
# 07.09.2026 (Spitzenanteil der Facette):
#
#     Erzieherin              39 %   Beruf
#     Maschinenbauingenieur   36 %   Beruf
#     Pflegefachkraft         20 %   Beruf (Gruendungsfall #969)
#     Elektroniker            18 %   Beruf
#     -------------------------------------- Schwelle
#     PDM                     13 %   Technologie
#     PLM                     12 %   Technologie
#     Produktdatenmanagement  11 %   Sache
#     PLM Manager             10 %   Sache
#
# Die Schwelle liegt bewusst unter dem tiefsten gemessenen Beruf: eine
# fehlende Alternativbezeichnung ist genau das Verhalten von vor #969
# und damit harmlos, eine falsche kippt die ganze Liste.
MIN_SPITZENANTEIL = 0.15

# Wie lang muss ein gemeinsamer Wortstamm sein? Kuerzer wird beliebig
# ("man", "ing"), laenger verliert die Beugung ("pfleg" in
# "Pflegefachkraft" und "Altenpfleger").
MIN_STAMM = 5

_cache: dict[str, list[str]] = {}
_cache_lock = threading.Lock()


def aktiv() -> bool:
    """Darf die Abfrage ins Netz? Abschaltbar ueber PBP_BERUFE_LOOKUP=0.

    Die Testsuite schaltet sie in der conftest ab: ein Suchlauf-Test
    darf keine fremde API anrufen, sonst haengt die CI an einer
    Netzwerksperre oder misst fremde Latenz. Tests, die das Verhalten
    pruefen, reichen stattdessen einen eigenen Client herein.
    """
    import os
    return (os.environ.get("PBP_BERUFE_LOOKUP", "1") or "1").strip() != "0"


def _normwort(wort: str) -> str:
    """Ein Wort auf seinen vergleichbaren Kern bringen."""
    s = (wort or "").lower()
    for a, b in (("\u00e4", "ae"), ("\u00f6", "oe"), ("\u00fc", "ue"),
                 ("\u00df", "ss")):
        s = s.replace(a, b)
    return re.sub(r"[^a-z0-9]", "", s)


def _teilt_stamm(a: str, b: str) -> bool:
    """Teilen zwei Woerter einen Stamm von MIN_STAMM Zeichen?

    Bewusst als Teilstring in BEIDE Richtungen und nicht als Praefix:
    "Pflegefachkraft" und "Altenpfleger" teilen "pfleg", aber an
    verschiedenen Positionen. Ein Praefix-Vergleich haette den
    Gruendungsfall von #969 abgewiesen.
    """
    a, b = _normwort(a), _normwort(b)
    if not a or not b:
        return False
    kurz, lang = (a, b) if len(a) <= len(b) else (b, a)
    if len(kurz) < MIN_STAMM:
        return False
    return any(kurz[i:i + MIN_STAMM] in lang
               for i in range(len(kurz) - MIN_STAMM + 1))


def _ist_alternativbezeichnung(begriff: str, amtlich: str) -> bool:
    """Ist `amtlich` ein anderer NAME fuer `begriff` — oder nur verwandt?

    v1.7.36 (#987). Die Facette liefert die Berufe der Treffer, nicht die
    Synonyme des Begriffs. Fuer einen Beruf faellt beides zusammen, fuer
    eine Technologie nicht: zu "PLM" nennt sie Ingenieur, Konstrukteur,
    Informatiker — allesamt echte Berufe, aber keine anderen Namen fuer
    PLM. Als MUSS-Synonym eingesetzt oeffnen sie das Tor fuer ein ganzes
    Berufsfeld.

    Die Pruefung ist deshalb: **jedes tragende Wort des Begriffs muss
    sich in der Bezeichnung wiederfinden.** Ein anderer Name fuer
    dieselbe Sache teilt mit ihr den Wortstamm — "Pflegefachkraft" und
    "Gesundheits- und Krankenpfleger/in" teilen "pfleg". "PLM" und
    "Ingenieur/in - Elektrotechnik" teilen nichts.

    Ein Begriff, dessen Woerter alle kuerzer als MIN_STAMM sind (PLM,
    PDM, CAD), kann damit ueberhaupt keine Alternativbezeichnung haben.
    Das ist beabsichtigt: eine Abkuerzung ist kein Berufsname.
    """
    woerter = [w for w in re.split(r"[\s/\-.,]+", begriff or "")
               if len(_normwort(w)) >= 3]
    if not woerter:
        return False
    teile = [t for t in re.split(r"[\s/\-.,()]+", amtlich or "") if t]
    if not teile:
        return False
    return all(any(_teilt_stamm(w, t) for t in teile) for w in woerter)


def _varianten(token: str) -> list[str]:
    """Die Schreibweisen EINES Tokens: "Erzieher/in" -> Erzieher, Erzieherin.

    Zerlegt wird nur die Schraegstrich-Schreibweise, nicht die
    Bezeichnung selbst — siehe `_formen`.
    """
    if "/" not in token:
        return [token]
    stamm, _, rest = token.partition("/")
    ersetzung = rest.startswith("-")
    stamm = stamm.strip(" -")
    rest = rest.strip(" -")
    formen = [stamm] if stamm else []
    if not rest:
        return formen

    if ersetzung:
        # "Pflegefachmann/-frau": der Teil hinter dem Schraegstrich
        # ERSETZT die Endung des Stamms.
        if stamm.lower().endswith("mann") and rest.lower() == "frau":
            formen.append(stamm[:-4] + "frau")
        elif len(rest) >= 4 and rest[:1].isupper():
            formen.append(rest)
        return formen

    if rest.lower() in ("in", "innen", "r", "e", "er"):
        formen.append(stamm + rest.lower())
        return formen

    # "Sozialpaedagoge/paedagogin": der Rest wiederholt einen Teil des
    # Stamms — dort zusammenfuegen statt anhaengen.
    anker = rest[:4].lower()
    i = stamm.lower().find(anker)
    if i > 0:
        formen.append(stamm[:i] + rest)
    elif rest[:1].isupper() and len(rest) >= 4:
        formen.append(rest)
    return formen


def _formen(bezeichnung: str) -> list[str]:
    """Amtliche Schreibweise in suchbare Formen zerlegen.

    **Ein Synonym ist die ganze Bezeichnung, nicht eines ihrer Woerter.**
    Das ist die Lehre aus #987 und die einzige inhaltliche Aenderung
    gegenueber v1.7.28: die erste Fassung zerlegte die Bezeichnung an
    Leerzeichen und lieferte fuer "Ingenieur/in - Elektrotechnik" die
    Woerter "Ingenieur", "Ingenieurin" und "Elektrotechnik". Jedes davon
    ist ein ganzes Berufsfeld; als MUSS-Synonym eingesetzt traf es alles.
    Der Docstring der ersten Fassung warnte bereits vor Fragmenten
    ("Gesundheits" traefe jedes Kompositum) — die Warnung galt nur dem
    Kompositum-Vorderteil, nicht dem abgetrennten ganzen Wort.

    Zwei Regeln also:

    1. Der Teil hinter " - " ist eine FACHRICHTUNG, kein eigener Name.
       "Elektroniker/in - Betriebstechnik" ist ein Elektroniker; ein
       Elektroniker ist keine Betriebstechnik. Klammerzusaetze ebenso.
    2. Zerlegt wird nur die SCHREIBWEISE (Schraegstrich-Formen), die
       Wortfolge bleibt. "Technische/r Produktdesigner/in" ergibt
       "Technische Produktdesigner" bis "Technischer Produktdesignerin"
       — nie "Technische" allein.

    Grammatisch schiefe Kombinationen ("Technische Produktdesignerin")
    bleiben dabei stehen. Sie sind harmlos: sie stehen in keiner Anzeige
    und matchen deshalb nie. Ein FRAGMENT waere das Gegenteil.
    """
    if not bezeichnung:
        return []
    # Klammerzusaetze sind Praezisierungen, keine eigene Bezeichnung.
    text = re.sub(r"\([^)]*\)", " ", str(bezeichnung))
    # Fachrichtung hinter " - " bzw. " \u2013 " faellt weg.
    text = re.split(r"\s[-\u2013]\s", text)[0]
    tokens = [t for t in re.split(r"\s+", text.strip()) if t.strip(" ,;")]
    if not tokens or len(tokens) > 4:
        return []

    formen: list[str] = []

    def _aufnehmen(text: str) -> None:
        text = (text or "").strip(" -/,;")
        if len(_normwort(text)) < MIN_STAMM or not text[:1].isupper():
            return
        if not any(text.lower() == vorhanden.lower() for vorhanden in formen):
            formen.append(text)

    # Sonderfall Koordination: "Gesundheits- und Krankenpfleger/in" meint
    # "Gesundheitspfleger UND Krankenpfleger". Das letzte Glied ist damit
    # ein vollstaendiger Berufsname und darf allein stehen — das
    # Vorderteil ("Gesundheits-") niemals. Erkennbar am Bindestrich am
    # Wortende plus Bindewort; ein blosser Mehrwort-Titel wie
    # "Technische/r Produktdesigner/in" hat beides nicht und wird
    # deshalb NICHT zerlegt.
    koordination = any(t.endswith("-") for t in tokens[:-1]) and any(
        t.lower() in ("und", "oder") for t in tokens[:-1])
    if koordination:
        for variante in _varianten(tokens[-1]):
            _aufnehmen(variante)

    varianten = [_varianten(t) or [t] for t in tokens]
    for kombination in itertools.product(*varianten):
        _aufnehmen(" ".join(teil for teil in kombination if teil))
    return formen[:6]


def _aus_facette(daten: dict, begriff: str = "") -> list[str]:
    """Amtliche Berufsbezeichnungen aus einer v6-Antwort lesen.

    v1.7.36 (#987): `begriff` ist neu und entscheidet mit. Ohne ihn
    liefert die Funktion wie bisher die haeufigsten Bezeichnungen — mit
    ihm nur die, die auch ein anderer NAME fuer den Begriff sind, und
    nur, wenn die Facette sich ueberhaupt auf einen Beruf konzentriert.
    """
    facette = ((daten or {}).get("facetten") or {}).get("beruf") or {}
    counts = facette.get("counts") if isinstance(facette, dict) else None
    if not isinstance(counts, dict) or not counts:
        return []
    gesamt = sum(counts.values()) or 1
    gereiht = sorted(counts.items(), key=lambda p: -p[1])

    if begriff:
        # Tor 1: Ist der Begriff ueberhaupt ein Beruf? Ein Beruf zieht
        # seine Alternativbezeichnungen an sich, eine Technologie streut.
        if gereiht[0][1] / gesamt < MIN_SPITZENANTEIL:
            logger.debug("Facette zu breit fuer %r (Spitze %.0f %%) — "
                         "kein Berufsname", begriff,
                         100 * gereiht[0][1] / gesamt)
            return []

    treffer = [name for name, n in gereiht if n / gesamt >= MIN_ANTEIL]
    if begriff:
        # Tor 2: Nur andere NAMEN derselben Sache, keine verwandten Berufe.
        treffer = [n for n in treffer if _ist_alternativbezeichnung(begriff, n)]
    return treffer[:MAX_SYNONYME]


def synonyme(begriff: str, *, client=None) -> list[str]:
    """Wie heisst dieser Beruf sonst noch? Leere Liste, wenn unbekannt.

    Faellt die Quelle aus, wird das protokolliert und PBP arbeitet
    weiter wie bisher — eine fehlende Auskunft darf keine Suche
    verhindern.
    """
    begriff = (begriff or "").strip()
    if len(begriff) < 3:
        return []
    if client is None and not aktiv():
        return []
    schluessel = begriff.lower()
    with _cache_lock:
        if schluessel in _cache:
            return list(_cache[schluessel])

    ergebnis: list[str] = []
    try:
        import httpx
        eigener = client is None
        client = client or httpx.Client(timeout=15)
        try:
            antwort = client.get(
                API_URL,
                params={"was": begriff, "size": 1},
                headers={"X-API-Key": API_KEY, "User-Agent": _USER_AGENT},
            )
            if antwort.status_code == 200:
                # v1.7.36 (#987): der Begriff entscheidet mit — die
                # Facette allein sagt nur, WER damit arbeitet.
                amtlich = _aus_facette(antwort.json(), begriff)
                for bezeichnung in amtlich:
                    for form in _formen(bezeichnung):
                        if (form.lower() != schluessel
                                and not any(form.lower() == e.lower()
                                            for e in ergebnis)):
                            ergebnis.append(form)
            else:
                logger.debug("Berufs-Facette: HTTP %s fuer %r",
                             antwort.status_code, begriff)
        finally:
            if eigener:
                client.close()
    except Exception as exc:  # pragma: no cover — Ausfall darf nie stoeren
        logger.debug("Berufsbezeichnungen nicht abrufbar (%s): %s",
                     begriff, exc)
        return []

    ergebnis = ergebnis[:MAX_SYNONYME * 2]
    with _cache_lock:
        _cache[schluessel] = list(ergebnis)
    return ergebnis


def erweitere(begriffe: list[str], *, client=None) -> dict[str, list[str]]:
    """Zu jedem MUSS-Begriff die bekannten Alternativbezeichnungen.

    Wird EINMAL je Suchlauf aufgerufen und ueber die Kriterien
    weitergereicht — dasselbe Muster wie die IDF-Faktoren (#778). Eine
    Netzabfrage je Stelle und Keyword waere unbrauchbar.
    """
    erg: dict[str, list[str]] = {}
    for b in begriffe or []:
        gefunden = synonyme(b, client=client)
        if gefunden:
            erg[b] = gefunden
    return erg


def cache_leeren() -> None:
    """Nur fuer Tests."""
    with _cache_lock:
        _cache.clear()
