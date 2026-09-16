"""Filter, Sortierung und Seiten der Stellenliste — an EINER Stelle (#1030, #1032).

## Der Befund

Der Stellen-Tab lud 20 Stellen und filterte und sortierte dann diese 20.
Der Endpunkt hatte die volle Liste in der Hand, schnitt die Seite heraus
und ueberliess den Rest dem Browser ("sortiert wird im Frontend"). Beim
Melder hiess das: Suchtext "buchhaltung" 5 statt 209 Treffer, Umfang
"Vollzeit" 0 statt 59, und der Hinweis dazu lautete, die Filter seien
"strenger als noetig".

**Ein Filter, der nur auf die geladene Seite wirkt, beantwortet eine
andere Frage als die, die er stellt.** Dieselbe Klasse wie #1022 (eine
Kennzahl ueber die geladene Seite misst das Blaettern) — nur dass hier
nicht eine Zahl falsch war, sondern die Liste selbst.

## Warum auf den Server und nicht "alles laden"

Beide Wege erfuellen die Akzeptanzkriterien. Der Unterschied liegt darin,
wie viele Fassungen der Regeln es danach gibt: der Ausgeblendet-Tab laedt
schon heute alles und filtert im Browser. Filterte der Server nur die
aktiven Stellen, gaebe es eine Fassung in Python und eine in JavaScript
fuer dieselben zehn Filter — #963 zum achtzehnten Mal. Deshalb gehen
BEIDE Ansichten durch diesen Dienst, und der Browser zeigt nur noch an.

## Was hier bewusst nicht neu formuliert wird

- ob ein Gehalt belegt ist: `gehalt_vergleich.vergleich` (#1017, #827)
- ob eine Beschreibung traegt: `datenguete.hat_beschreibung` (#989)
- die Datenguete-Ordnung: `datenguete.sortierschluessel` (#989)
- der Pruefstand: kommt fertig als `job["pruefstand"]` (#948)
- der Pflichttreffer: kommt fertig als `job["muss_tor"]` (#968)

Der Dienst liest keine Datenbank. Was er ueber den Bestand wissen muss
(beworbene Stellen, Einstellung zur Datenguete), bekommt er uebergeben —
damit bleibt er ohne Fixture pruefbar.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Callable, Iterable, Optional

from . import datenguete, gehalt_vergleich, indikatoren

VORGABE_SORTIERUNG = "score_desc"
SORTIERUNGEN = (
    "score_desc", "score_asc", "salary_desc", "company", "title",
    # #1032: nach dem ERSTFUND. Bewusst nicht `veroeffentlicht_am` mit
    # Rueckfall — das Datum liefert nur eine Quelle, und eine Mischung
    # stellte eine heute gefundene Stelle hinter eine von gestern, nur
    # weil die andere Quelle kein Veroeffentlichungsdatum kennt.
    "found_desc", "found_asc",
    # #1010: die Ordnung des Protokolls. Bis v1.7.92 wurde sie im Browser
    # vorsortiert und danach vom gewaehlten Kriterium ueberschrieben —
    # sie hielt nur bei gleichem Score.
    "dismissed_desc",
)
PRUEFSTAENDE = ("ungeprueft", "gesichtet", "beurteilt")
ZEITFENSTER = ("alle", "heute", "7tage", "30tage")

FILTER_VORGABE: dict = {
    "query": "",
    "source": "",
    "min_score": 0.0,
    "remote": "",
    "nur_mit_gehalt": False,
    "employment_type": "",
    "arbeitsumfang": "",
    # Vorgabe AUS: andere Aufrufer (Dashboard, Onboarding) erwarten alle
    # Stellen. Der Stellen-Tab schickt den Wert ausdruecklich mit.
    "beworbene_ausblenden": False,
    "nur_ohne_beschreibung": False,
    "pruefstand": "",
    "zeitfenster": "alle",
    # v1.7.117 (#1052): Vorgabe AN — eine Stelle, deren Rahmen BELEGT
    # nicht passt, kommt fuer diesen Menschen nicht in Frage
    # (Nutzerantwort 15.09.2026). Die Lehre aus #1008 gilt trotzdem und
    # sogar staerker: der Filter steht sichtbar da und nennt seine Zahl
    # (`rahmen_verborgen`).
    "rahmen_ausblenden": True,
}

_UMFANG_BEIDES = "beides"
_WAHR = {"1", "true", "ja", "yes", "on"}


class UngueltigerParameter(ValueError):
    """Ein Wert, den die Liste nicht kennt — benannt statt ignoriert (#988)."""

    def __init__(self, feld: str, wert, erlaubt: Iterable[str]):
        self.feld = feld
        self.wert = wert
        self.erlaubt = list(erlaubt)
        super().__init__(
            f"'{wert}' ist fuer '{feld}' nicht moeglich. Moeglich: "
            + ", ".join(self.erlaubt))


def _zahl(wert) -> float:
    try:
        return float(wert or 0)
    except (TypeError, ValueError):
        return 0.0


def _wahr(wert) -> bool:
    if isinstance(wert, bool):
        return wert
    return str(wert or "").strip().lower() in _WAHR


def filter_lesen(roh: Optional[dict]) -> dict:
    """Macht aus Anfrage-Parametern einen gueltigen Filter.

    Ein unbekannter Wert wird ABGEWIESEN. Ihn still zu ignorieren waere
    #988: eine Auswahl, der man glaubt, die aber nichts bewirkt.
    """
    roh = roh or {}
    f = dict(FILTER_VORGABE)
    for feld in ("query", "source", "remote", "employment_type",
                 "arbeitsumfang", "pruefstand", "zeitfenster"):
        if roh.get(feld) is not None:
            f[feld] = str(roh[feld]).strip()
    for feld in ("nur_mit_gehalt", "beworbene_ausblenden",
                 "nur_ohne_beschreibung", "rahmen_ausblenden"):
        if roh.get(feld) is not None:
            f[feld] = _wahr(roh[feld])
    if roh.get("min_score") not in (None, ""):
        try:
            f["min_score"] = float(roh["min_score"])
        except (TypeError, ValueError):
            raise UngueltigerParameter("min_score", roh["min_score"],
                                       ["eine Zahl"]) from None
    if f["pruefstand"] and f["pruefstand"] not in PRUEFSTAENDE:
        raise UngueltigerParameter("pruefstand", f["pruefstand"], PRUEFSTAENDE)
    if not f["zeitfenster"]:
        f["zeitfenster"] = "alle"
    if f["zeitfenster"] not in ZEITFENSTER:
        raise UngueltigerParameter("zeitfenster", f["zeitfenster"], ZEITFENSTER)
    return f


def ist_listenanfrage(roh: Optional[dict], sort: str = "") -> bool:
    """Wurde irgendetwas verlangt, das ueber "gib mir alles" hinausgeht?"""
    if sort:
        return True
    try:
        return filter_lesen(roh) != FILTER_VORGABE
    except UngueltigerParameter:
        return True  # der Fehler soll beim Aufbereiten benannt werden


def hat_belegtes_gehalt(job: dict) -> bool:
    """#1030 Nebenbefund: "nur mit Gehalt" zaehlte Schaetzungen mit.

    Beim Melder galten 1.169 von 1.174 Stellen als "mit Gehalt", eine
    Angabe aus der Anzeige hatten 124 — der Filter blendete praktisch
    nichts aus. Die Unterscheidung kennt `gehalt_vergleich` seit #1017;
    ohne Wunschwert antwortet es mit `ohne_wunsch`, und das heisst hier:
    ein Betrag steht in der Anzeige.
    """
    stand = gehalt_vergleich.vergleich(job, {})["stand"]
    return stand not in (gehalt_vergleich.GESCHAETZT,
                         gehalt_vergleich.OHNE_ANGABE)


def _zeitpunkt(wert) -> Optional[datetime]:
    if not wert:
        return None
    try:
        ts = datetime.fromisoformat(str(wert).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.astimezone()  # Altbestand ohne Offset: Ortszeit
    return ts


def zeitfenster_grenze(fenster: str,
                       jetzt: Optional[datetime] = None) -> Optional[datetime]:
    """Ab wann eine Aussortierung im Fenster liegt (#1010).

    "heute" beginnt um Mitternacht ORTSZEIT — wer um 01:00 Uhr etwas
    wegklickt, sucht es am selben Morgen unter "heute" (v1.7.64 MERKE 6).
    """
    if fenster == "alle":
        return None
    jetzt = jetzt or datetime.now().astimezone()
    if fenster == "heute":
        return jetzt.replace(hour=0, minute=0, second=0, microsecond=0)
    return jetzt - timedelta(days=30 if fenster == "30tage" else 7)


def _passt(job: dict, f: dict, beworbene: set, hash_von: Callable,
           grenze: Optional[datetime]) -> bool:
    query = f["query"].lower()
    if query:
        heuhaufen = " ".join(str(job.get(k) or "") for k in
                             ("title", "company", "description")).lower()
        if query not in heuhaufen:
            return False
    if f["source"] and job.get("source") != f["source"]:
        return False
    if _zahl(job.get("score")) < f["min_score"]:
        return False
    if f["remote"] and job.get("remote_level") != f["remote"]:
        return False
    if f["nur_mit_gehalt"] and not hat_belegtes_gehalt(job):
        return False
    if f["employment_type"] and job.get("employment_type") != f["employment_type"]:
        return False
    if f["arbeitsumfang"]:
        umfang = job.get("arbeitsumfang")
        # #1023: "beides" ist fuer BEIDE Richtungen ein Treffer.
        if not (umfang == f["arbeitsumfang"]
                or (umfang == _UMFANG_BEIDES
                    and f["arbeitsumfang"] in ("vollzeit", "teilzeit"))):
            return False
    if f["beworbene_ausblenden"] and hash_von(job.get("hash")) in beworbene:
        return False
    if f["nur_ohne_beschreibung"] and datenguete.hat_beschreibung(job):
        return False
    # #1052: nur BELEGT verletzte Rahmenbedingungen. Ein grauer Daumen
    # nach unten heisst "ungeprueft" — ihn auszublenden waere die
    # Verwechslung aus #989.
    if f["rahmen_ausblenden"] and indikatoren.rahmen_passt_nicht(job):
        return False
    if f["pruefstand"]:
        art = (job.get("pruefstand") or {}).get("art") or "ungeprueft"
        if art != f["pruefstand"]:
            return False
    if grenze is not None:
        wann = _zeitpunkt(job.get("dismissed_at"))
        # Ohne Zeitpunkt (Altbestand) laesst sich nichts einordnen — die
        # Zeile erscheint nur unter "alle" (#1010).
        if wann is None or wann < grenze:
            return False
    return True


def _datum_schluessel(job: dict, feld: str, neueste_zuerst: bool) -> tuple:
    """Ohne Datum steht eine Stelle HINTEN, in beiden Richtungen.

    "Unbekannt" ist weder das neueste noch das aelteste Datum (#989).
    """
    wann = _zeitpunkt(job.get(feld))
    if wann is None:
        return (1, 0.0)
    ts = wann.timestamp()
    return (0, -ts if neueste_zuerst else ts)


def _kriterium(sort: str) -> Callable[[dict], object]:
    if sort == "score_asc":
        return lambda j: _zahl(j.get("score"))
    if sort == "salary_desc":
        return lambda j: -(_zahl(j.get("salary_max")) or _zahl(j.get("salary_min")))
    if sort == "company":
        return lambda j: str(j.get("company") or "").casefold()
    if sort == "title":
        return lambda j: str(j.get("title") or "").casefold()
    if sort == "found_desc":
        return lambda j: _datum_schluessel(j, "found_at", True)
    if sort == "found_asc":
        return lambda j: _datum_schluessel(j, "found_at", False)
    if sort == "dismissed_desc":
        return lambda j: _datum_schluessel(j, "dismissed_at", True)
    return lambda j: -_zahl(j.get("score"))


def sortieren(jobs: list, sort: str = VORGABE_SORTIERUNG,
              guete_umgang: str = datenguete.NACHRANGIG) -> list:
    """Dieselbe Rangfolge, die der Stellen-Tab bis v1.7.92 im Browser hatte.

    1. angepinnt vor nicht angepinnt
    2. mit Pflichttreffer vor ohne (#968 AK 4 — Gruppe vor Zahl)
    3. mit Bewertungsgrundlage vor ohne, je nach Einstellung (#989)
    4. das gewaehlte Kriterium
    """
    if sort not in SORTIERUNGEN:
        raise UngueltigerParameter("sort", sort, SORTIERUNGEN)
    kriterium = _kriterium(sort)
    return sorted(jobs, key=lambda j: (
        0 if j.get("is_pinned") else 1,
        1 if j.get("muss_tor") else 0,
        datenguete.sortierschluessel(j, guete_umgang),
        kriterium(j),
    ))


def optionen(jobs: Iterable[dict]) -> dict:
    """Die Werte der Auswahllisten — ueber die GANZE Ansicht (#1030 AK 6).

    Vorher entstanden sie aus den geladenen aktiven plus allen
    ausgeblendeten Stellen: ein Wert konnte fehlen, obwohl aktive Stellen
    ihn tragen, oder angeboten werden, ohne dass eine passt.
    `unbekannt` gehoert nicht in eine Auswahl, die etwas einschraenken
    soll (#1023).
    """
    jobs = list(jobs)

    def werte(feld: str, ohne: tuple = ()) -> list:
        return sorted({str(j.get(feld)) for j in jobs
                       if j.get(feld) and j.get(feld) not in ohne},
                      key=str.casefold)

    return {
        "source": werte("source"),
        "remote": werte("remote_level", ("unbekannt",)),
        "employment_type": werte("employment_type"),
        "arbeitsumfang": werte("arbeitsumfang", ("unbekannt",)),
    }


def aufbereiten(jobs: list, filter_roh: Optional[dict] = None,
                sort: str = "", *, limit: int = 0, offset: int = 0,
                beworbene: Iterable[str] = (),
                hash_von: Optional[Callable] = None,
                guete_umgang: str = datenguete.NACHRANGIG,
                jetzt: Optional[datetime] = None) -> dict:
    """Filtert, sortiert und schneidet die Seite — in dieser Reihenfolge.

    `total` bleibt die Zahl der Stellen in der Ansicht (Tab-Name, Kachel:
    Bestandsanzeigen, #1022). `treffer` ist die Zahl, die durch die
    Filter kommt — sie gehoert an den Zaehler neben dem Suchfeld, und
    `has_more` rechnet mit ihr.
    """
    f = filter_lesen(filter_roh)
    sort = sort or VORGABE_SORTIERUNG
    if sort not in SORTIERUNGEN:
        raise UngueltigerParameter("sort", sort, SORTIERUNGEN)
    limit = max(0, int(limit or 0))
    offset = max(0, int(offset or 0))
    hv = hash_von or (lambda h: str(h or ""))
    bew = {hv(h) for h in beworbene if h}
    grenze = zeitfenster_grenze(f["zeitfenster"], jetzt)

    treffer = [j for j in jobs if _passt(j, f, bew, hv, grenze)]
    sortiert = sortieren(treffer, sort, guete_umgang)
    seite = sortiert[offset:offset + limit] if limit else sortiert[offset:]

    # Fuer den Hinweis "alle Treffer sind nur wegen 'Beworbene
    # ausblenden' weg" — gezaehlt ueber den Bestand, nicht die Seite.
    if f["beworbene_ausblenden"]:
        ohne_diesen = dict(f, beworbene_ausblenden=False)
        treffer_mit_beworbenen = sum(
            1 for j in jobs if _passt(j, ohne_diesen, bew, hv, grenze))
    else:
        treffer_mit_beworbenen = len(treffer)

    # #1052 / #1008: wie viele Stellen blendet der Rahmenfilter aus?
    # Gezaehlt ueber die Stellen, die ALLE anderen Filter passieren —
    # sonst zaehlte er Zeilen mit, die ohnehin nicht zu sehen waeren.
    if f["rahmen_ausblenden"]:
        ohne_rahmen = dict(f, rahmen_ausblenden=False)
        rahmen_verborgen = sum(
            1 for j in jobs if _passt(j, ohne_rahmen, bew, hv, grenze))             - len(treffer)
    else:
        rahmen_verborgen = 0

    return {
        "jobs": seite,
        "total": len(jobs),
        "treffer": len(treffer),
        "treffer_mit_beworbenen": treffer_mit_beworbenen,
        "offset": offset,
        "limit": limit,
        "has_more": bool(limit) and offset + limit < len(treffer),
        "sort": sort,
        "filter": f,
        "optionen": optionen(jobs),
        "ohne_beschreibung": sum(
            1 for j in jobs if not datenguete.hat_beschreibung(j)),
        "ohne_zeitpunkt": sum(1 for j in jobs if not j.get("dismissed_at")),
        "rahmen_verborgen": rahmen_verborgen,
    }
