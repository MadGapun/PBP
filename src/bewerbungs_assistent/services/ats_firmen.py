"""Welche Firmen fragen die ATS-Quellen ab (#811)?

## Befund

Personio, Greenhouse und Workable liefern keine Suche, sondern die
Stellenliste EINER Firma je Slug. Die Slugs standen als feste Liste im
Code (`DEFAULT_COMPANIES`) — eine Stichprobe fremder Arbeitgeber ohne
Bezug zu Beruf, Region oder Bewerbungen. Dazu zwei stille Nullen:

- **Ein erfundener Personio-Slug endet auf einem fremden Host.** Im
  Bericht vom 06.08. mit HTTP 200 und 1,7 MB Marketing-Seite, am 13.09.
  nachgemessen mit HTTP 429 auf personio.com. Beide Male sagt der Status
  nichts — erst der Zielhost. Deshalb wird der Host VOR dem Status
  geprueft; umgekehrt galt der zweite Fall als "nicht erreichbar" statt
  als ungueltig.
- **`personio_firmen` und `workable_firmen` kamen nie beim Adapter an.**
  Der Parameterbau reichte nur `greenhouse_companies` durch; die
  Docstrings der Adapter versprachen eine Einstellung ohne Draht.

## Was dieses Modul tut

1. Kandidaten aus dem eigenen Bestand bilden — Bewerbungen, Kontakte,
   gefundene Stellen. Aus einer Stellen-URL auf dem ATS selbst ist der
   Slug SICHER; aus einem Firmennamen ist er eine Vermutung und wird
   geprueft, bevor er zaehlt.
2. Einen Slug INHALTLICH pruefen: der Abruf muss auf dem angefragten Host
   enden und die erwartete Struktur tragen. HTTP 200 allein belegt nichts.
3. Das Ergebnis speichern (`ats_firmen`), damit nicht jeder Suchlauf neu
   raet. Ungueltige Kandidaten bleiben gespeichert — sonst fragt der
   naechste Lauf dieselben Namen wieder ab.

## Workable fehlt mit Absicht

Nachgemessen am 13.09.: die Widget-Schnittstelle, die der Adapter
abfragt, antwortet selbst fuer Workables eigenen Account mit 404. Die
Quelle steht seit #927 als `defekt` in der Registry und wird im Suchlauf
uebersprungen. Slugs dafuer zu ermitteln hiesse, eine Einstellung ohne
Draht zu bauen (#988) — deshalb nur Personio und Greenhouse.

## Was es bewusst nicht tut

- **Kein Abgleich aller Stellenfirmen auf einmal.** Eine Kopie des
  Bestands trug 1.141 verschiedene Firmennamen; mal drei Systeme waeren
  das ueber 3.400 Anfragen. Vorrang haben Bewerbungen und Kontakte, die
  Menge ist begrenzt, und die Vorschau ist die Vorgabe.
- **Keine Namensaehnlichkeit.** Ein Slug entsteht aus dem Namen nach
  festen Regeln (Rechtsform weg, Umlaute umschreiben, Bindestrich oder
  zusammengeschrieben). Was nicht trifft, trifft nicht — ein falscher
  Treffer fragte die Stellen einer FREMDEN Firma ab.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

PERSONIO = "personio"
GREENHOUSE = "greenhouse"
SYSTEME = (PERSONIO, GREENHOUSE)

URLS = {
    PERSONIO: "https://{slug}.jobs.personio.de/xml",
    GREENHOUSE: "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs",
}

GUELTIG = "gueltig"
UNGUELTIG = "ungueltig"
NICHT_ERREICHBAR = "nicht_erreichbar"

QUELLE_URL = "stellen_url"
QUELLE_NAME = "firmenname"
QUELLE_WUNSCH = "wunsch"

#: Obergrenze je Lauf — Namen je System. Siehe Modul-Docstring.
MAX_KANDIDATEN = 30

#: Endwoerter, die nie Teil eines Slugs sind.
_RECHTSFORM = {
    "gmbh", "mbh", "ag", "se", "kg", "kgaa", "ohg", "gbr", "ug", "ev", "e.v",
    "ltd", "limited", "inc", "llc", "bv", "b.v", "nv", "sa", "s.a", "sarl",
    "plc", "co", "&", "und", "haftungsbeschraenkt",
}
#: Endwoerter, die Teil eines Slugs sein KOENNEN — beide Fassungen pruefen.
_ZUSATZ = {"deutschland", "germany", "group", "gruppe", "holding", "dach"}

_UMSCHRIFT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def _worte(firmenname: str) -> list[str]:
    name = (firmenname or "").strip().lower().translate(_UMSCHRIFT)
    name = re.sub(r"\([^)]*\)", " ", name)  # Klammerzusaetze (#956)
    worte = [w.strip(".") for w in re.findall(r"[a-z0-9&.]+", name)]
    worte = [w for w in worte if w]
    while worte and worte[-1] in _RECHTSFORM:
        worte.pop()
    return [re.sub(r"[^a-z0-9]", "", w) for w in worte if re.sub(r"[^a-z0-9]", "", w)]


def slug_kandidaten(firmenname: str) -> list[str]:
    """Moegliche Slugs zu einem Firmennamen — geordnet, ohne Dubletten.

    "Musterbetrieb Nord GmbH & Co. KG" -> ["musterbetrieb-nord",
    "musterbetriebnord"]
    """
    worte = _worte(firmenname)
    fassungen = [worte]
    if len(worte) > 1 and worte[-1] in _ZUSATZ:
        fassungen.append(worte[:-1])
    kandidaten: list[str] = []
    for w in fassungen:
        if w:
            kandidaten += ["-".join(w), "".join(w)]
    return list(dict.fromkeys(k for k in kandidaten if len(k) >= 3))


def slug_aus_url(url: str) -> tuple[str, str] | None:
    """(system, slug), wenn die URL auf ein ATS-Board zeigt — sonst None."""
    try:
        teile = urlparse(url or "")
    except ValueError:
        return None
    host = (teile.hostname or "").lower()
    pfad = [p for p in (teile.path or "").split("/") if p]
    m = re.match(r"^([a-z0-9-]+)\.jobs\.personio\.(de|com)$", host)
    if m and m.group(1) not in ("www", "jobs"):
        return PERSONIO, m.group(1)
    if re.match(r"^(boards|job-boards)(\.eu)?\.greenhouse\.io$", host) and pfad:
        return GREENHOUSE, pfad[0].lower()
    if host == "boards-api.greenhouse.io" and len(pfad) >= 3 and pfad[1] == "boards":
        return GREENHOUSE, pfad[2].lower()
    return None


def bewerte_antwort(system: str, slug: str, antwort) -> tuple[str, int]:
    """Ist die Antwort die Stellenliste DIESER Firma? -> (befund, anzahl).

    Reihenfolge ist Absicht: erst der Zielhost, dann der Status, dann die
    Struktur. Siehe Modul-Docstring.
    """
    erwartet = urlparse(URLS[system].format(slug=slug)).hostname
    ziel = getattr(getattr(antwort, "url", None), "host", None)
    # Eine echte httpx-Antwort traegt den Zielhost immer als Text. Nur
    # dann laesst er sich vergleichen — ein Testdoppel ohne Host soll nicht
    # als Umleitung gelten.
    if isinstance(ziel, str) and ziel and ziel != erwartet:
        return UNGUELTIG, 0
    status = getattr(antwort, "status_code", 0)
    if status in (404, 410):
        return UNGUELTIG, 0
    if status != 200:
        return NICHT_ERREICHBAR, 0
    if system == PERSONIO:
        inhalt = antwort.content or b""
        if b"<workzag-jobs" not in inhalt[:500]:
            return UNGUELTIG, 0
        return GUELTIG, inhalt.count(b"<position>")
    try:
        daten = antwort.json()
    except Exception:
        return UNGUELTIG, 0
    if not isinstance(daten, dict) or not isinstance(daten.get("jobs"), list):
        return UNGUELTIG, 0
    return GUELTIG, len(daten["jobs"])


# ------------------------------------------------------------ Bestand


def tabelle_anlegen(db) -> None:
    """Defensiv — `Database.initialize` legt die Tabelle ebenfalls an."""
    db.connect().execute("""
        CREATE TABLE IF NOT EXISTS ats_firmen (
            profile_id TEXT NOT NULL,
            system TEXT NOT NULL,
            slug TEXT NOT NULL,
            firma TEXT,
            quelle TEXT,
            befund TEXT,
            stellen INTEGER,
            geprueft_am TEXT,
            PRIMARY KEY (profile_id, system, slug)
        )
    """)


def _pid(db) -> str:
    return db.get_active_profile_id() or ""


def kandidaten(db, max_namen: int = MAX_KANDIDATEN) -> list[dict]:
    """Was aus dem Bestand abgefragt wuerde — noch ungeprueft, ohne Netz.

    Reihenfolge: sichere Slugs aus Stellen-URLs, dann Firmennamen aus
    Bewerbungen, dann aus Kontakten, dann aus gefundenen Stellen. Bereits
    gepruefte Paare fallen heraus; ein Wunscharbeitgeber wird nie
    verdraengt.
    """
    tabelle_anlegen(db)
    conn = db.connect()
    pid = _pid(db)
    bekannt = {(z[0], z[1]) for z in conn.execute(
        "SELECT system, slug FROM ats_firmen WHERE profile_id=?", (pid,))}
    ergebnis: list[dict] = []
    gesehen: set = set()

    def _neu(system, slug, firma, quelle):
        schluessel = (system, slug)
        if schluessel in bekannt or schluessel in gesehen:
            return
        gesehen.add(schluessel)
        ergebnis.append({"system": system, "slug": slug, "firma": firma,
                         "quelle": quelle})

    for tabelle in ("applications", "jobs"):
        for url, firma in conn.execute(
                f"SELECT url, company FROM {tabelle} WHERE url IS NOT NULL "
                f"AND (profile_id=? OR profile_id IS NULL OR profile_id='')",
                (pid,)):
            treffer = slug_aus_url(url)
            if treffer:
                _neu(treffer[0], treffer[1], firma, QUELLE_URL)

    namen: list[str] = []
    for abfrage in (
        "SELECT company, MAX(applied_at) FROM applications WHERE company "
        "IS NOT NULL AND company != '' AND (profile_id=? OR profile_id IS "
        "NULL OR profile_id='') GROUP BY lower(company) ORDER BY 2 DESC",
        "SELECT company, MAX(updated_at) FROM contacts WHERE company IS NOT "
        "NULL AND company != '' AND (profile_id=? OR profile_id IS NULL OR "
        "profile_id='') GROUP BY lower(company) ORDER BY 2 DESC",
        "SELECT company, COUNT(*) FROM jobs WHERE company IS NOT NULL AND "
        "company != '' AND (profile_id=? OR profile_id IS NULL OR "
        "profile_id='') GROUP BY lower(company) ORDER BY 2 DESC",
    ):
        try:
            namen += [z[0] for z in conn.execute(abfrage, (pid,))]
        except Exception:  # pragma: no cover — Spalte fehlt in Altbestand
            continue
    anzahl_namen = 0
    for firma in dict.fromkeys(namen):
        if anzahl_namen >= max_namen:
            break
        slugs = slug_kandidaten(firma)
        if not slugs:
            continue
        anzahl_namen += 1
        for system in SYSTEME:
            for slug in slugs:
                _neu(system, slug, firma, QUELLE_NAME)
    return ergebnis


def pruefen(system: str, slug: str, *, client=None) -> tuple[str, int]:
    """Ein Slug gegen sein System — mit einer echten Anfrage."""
    url = URLS[system].format(slug=slug)
    try:
        if client is None:
            from ..job_scraper import make_session
            with make_session(content_type="any", timeout=12) as eigen:
                antwort = eigen.get(url)
        else:
            antwort = client.get(url)
    except Exception:
        return NICHT_ERREICHBAR, 0
    return bewerte_antwort(system, slug, antwort)


def speichern(db, system: str, slug: str, firma, quelle: str, befund: str,
              stellen: int) -> None:
    from datetime import datetime, timezone
    tabelle_anlegen(db)
    db.connect().execute(
        "INSERT OR REPLACE INTO ats_firmen (profile_id, system, slug, firma, "
        "quelle, befund, stellen, geprueft_am) VALUES (?,?,?,?,?,?,?,?)",
        (_pid(db), system, slug, firma, quelle, befund, stellen,
         datetime.now(timezone.utc).isoformat(timespec="seconds")))
    db.connect().commit()


def ermitteln(db, *, max_namen: int = MAX_KANDIDATEN, client=None) -> dict:
    """Kandidaten pruefen und speichern. Ein nicht erreichbarer Dienst wird
    NICHT gespeichert — sonst gaelte ein voruebergehender Ausfall dauerhaft
    als ungueltiger Slug (dieselbe Regel wie beim Routen-Zwischenspeicher)."""
    gefunden, ungueltig, offen = [], 0, 0
    for k in kandidaten(db, max_namen):
        befund, stellen = pruefen(k["system"], k["slug"], client=client)
        if befund == NICHT_ERREICHBAR:
            offen += 1
            continue
        speichern(db, k["system"], k["slug"], k["firma"], k["quelle"],
                  befund, stellen)
        if befund == GUELTIG:
            gefunden.append({**k, "stellen": stellen})
        else:
            ungueltig += 1
    return {"gefunden": gefunden, "ungueltig": ungueltig,
            "nicht_erreichbar": offen}


def gueltige_slugs(db, system: str) -> list[str]:
    try:
        tabelle_anlegen(db)
        return [z[0] for z in db.connect().execute(
            "SELECT slug FROM ats_firmen WHERE profile_id=? AND system=? AND "
            "befund=? ORDER BY quelle='wunsch' DESC, slug",
            (_pid(db), system, GUELTIG))]
    except Exception:  # pragma: no cover — nie einen Suchlauf stoppen
        return []


def status(db) -> dict:
    """Wie viele Firmen je System abgefragt werden — 0 ist ein Zustand."""
    from ..job_scraper.greenhouse import DEFAULT_COMPANIES as _gh
    from ..job_scraper.personio import DEFAULT_COMPANIES as _pe
    beispiele = {PERSONIO: len(_pe), GREENHOUSE: len(_gh)}
    tabelle_anlegen(db)
    zeilen = db.connect().execute(
        "SELECT system, befund, COUNT(*) FROM ats_firmen WHERE profile_id=? "
        "GROUP BY system, befund", (_pid(db),)).fetchall()
    stand = {s: {"eigene_gueltig": 0, "geprueft_ungueltig": 0,
                 "beispielfirmen": beispiele[s]} for s in SYSTEME}
    for system, befund, anzahl in zeilen:
        if system not in stand:
            continue
        if befund == GUELTIG:
            stand[system]["eigene_gueltig"] = anzahl
        else:
            stand[system]["geprueft_ungueltig"] += anzahl
    return stand
