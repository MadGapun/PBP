"""Eine defekte Quelle melden — und zwar mit Bedarf (#937).

Nutzerwunsch vom 19.08.2026:

    "bei den fehlerhaften Quellen die Moeglichkeit geben, direkt ein
    Issue auf GH zu erstellen mit vorgefertigtem Text (haben ja da die
    Daten), um Nutzern die Moeglichkeit zu geben, wenn eine Quelle sehr
    wichtig ist, das auch zu melden."

**Der Wert liegt nicht im Melden des Defekts.** Den kennt PBP bereits —
`scraper_health` traegt Status, Fehlerklasse und Zaehler. Er liegt in
der **Priorisierung durch Bedarf**: von 32 konfigurierten Quellen
laufen 10, zwoelf tote zu reparieren ist unrealistisch, und es ist
nicht erkennbar, welche davon jemand tatsaechlich braucht. Deshalb ist
"wozu brauchst du diese Quelle" ein PFLICHTFELD im Template — ohne das
waere die Meldung wieder nur eine Defektmeldung.

## PBP sendet nichts

Kein Token, keine Authentifizierung, kein automatisches Absenden. Der
Text wird gebaut, in einem Dialog gezeigt und als Prefill-URL
geoeffnet; abgeschickt wird im GitHub-Formular vom Menschen. Damit
entfaellt die ganze Berechtigungsfrage — und niemand verschickt
versehentlich etwas.

## Warum der Text aus einer Positivliste entsteht

Das Akzeptanzkriterium verlangt, dass die Meldung **nachweislich** keine
Suchbegriffe, Profil-, Stellen- oder Kontaktdaten enthaelt. Ein
`dict`-Abzug der Health-Zeile waere heute sauber und beim naechsten
neuen Feld nicht mehr — genau die Bauform, aus der die PII-Vorfaelle
dieses Projekts entstanden sind.

Deshalb: `ERLAUBTE_FELDER` ist eine abschliessende Liste, und der Text
entsteht ausschliesslich daraus. Ein neues Feld in `scraper_health`
landet nicht automatisch in einer oeffentlichen Meldung, sondern erst,
wenn es hier bewusst eingetragen wird.

## `deprecated` bekommt keinen Knopf

Eine abgeschaltete Quelle ist eine ENTSCHEIDUNG, kein Defekt (#906:
`deprecated` und `auto_deaktiviert` sind zwei verschiedene Dinge in
zwei verschiedenen Feldern). Ein Melde-Knopf dort wuerde Meldungen
ueber etwas erzeugen, das absichtlich so ist.
"""
from __future__ import annotations

import logging
from urllib.parse import quote

logger = logging.getLogger(__name__)

REPO = "MadGapun/PBP"
TEMPLATE = "quelle-defekt.yml"
LABEL = "quelle-defekt"

# Prefill-URLs werden ab etwa 2.000 Zeichen unzuverlaessig — Browser und
# Server kappen unterschiedlich. Der Diagnoseblock wird deshalb gekuerzt,
# nicht die URL.
MAX_URL = 2000

# Zustaende, die einen Melde-Knopf bekommen. `deprecated` ist bewusst
# NICHT dabei: eine abgeschaltete Quelle ist eine Entscheidung.
MELDBAR = ("defekt", "timeout", "fehler", "server_weg")

# ABSCHLIESSENDE Liste der Felder, die nach draussen duerfen. Sie ist
# der eigentliche Schutz — siehe Modul-Kopf. Jedes Feld ist eine
# technische Angabe ueber die QUELLE, keines ueber den Menschen.
ERLAUBTE_FELDER = (
    ("scraper_name", "Quelle"),
    ("error_class", "Fehlerklasse"),
    ("last_error", "Letzte Fehlermeldung"),
    ("consecutive_failures", "Fehler in Folge"),
    ("consecutive_silent", "Stille Laeufe in Folge"),
    ("total_runs", "Laeufe gesamt"),
    ("total_successes", "Erfolgreiche Laeufe"),
    ("last_run", "Letzter Lauf"),
    ("last_success", "Letzter Erfolg"),
    ("letzte_probe_am", "Letzte Probe"),
    ("letzte_probe_status", "Probe-Ergebnis"),
    ("deaktiviert_am", "Abgeschaltet am"),
    ("deaktiviert_grund", "Abschaltgrund"),
    ("is_active", "Aktiv"),
)

# Felder, die es NIE in eine Meldung schaffen duerfen — auch nicht,
# wenn sie eines Tages in `scraper_health` auftauchen. Der Test prueft
# gegen diese Liste, damit der Schutz nicht nur im Kopf steht.
#
# Bewusst OHNE das nackte "name": `scraper_name` ist der Schluessel der
# QUELLE und muss hinaus — er ist der Gegenstand der Meldung. Ein
# Teilstring-Verbot auf "name" hat genau ihn getroffen. Verboten sind
# die Namen von MENSCHEN und FIRMEN, und die heissen anders.
VERBOTEN = (
    "keywords", "suchbegriff", "profile_id", "profil",
    "title", "titel", "company", "firma", "email", "mail",
    "kontakt", "bewerbung", "gehalt", "salary", "standort",
    "person", "vorname", "nachname", "adresse", "telefon",
)


def ist_meldbar(zeile: dict) -> bool:
    """Bekommt diese Quelle einen Melde-Knopf?"""
    if not zeile:
        return False
    if zeile.get("deprecated") or zeile.get("veraltet"):
        return False
    status = str(zeile.get("status") or zeile.get("error_class")
                 or zeile.get("last_error") or "").strip().lower()
    if status == "deprecated":
        return False
    if any(m in status for m in MELDBAR):
        return True
    # Ohne Statustext: mehrere Fehler in Folge zaehlen auch.
    try:
        return int(zeile.get("consecutive_failures") or 0) >= 3
    except (TypeError, ValueError):  # pragma: no cover
        return False


def bericht(zeile: dict, *, version: str = "") -> str:
    """Der Meldetext — ausschliesslich aus `ERLAUBTE_FELDER`.

    Kein dict-Abzug: was hier nicht steht, geht nicht hinaus.
    """
    zeile = zeile or {}
    zeilen = []
    for schluessel, beschriftung in ERLAUBTE_FELDER:
        wert = zeile.get(schluessel)
        if wert in (None, ""):
            continue
        zeilen.append(f"{beschriftung}: {str(wert)[:200]}")
    if version:
        zeilen.append(f"PBP-Version: {version}")
    return "\n".join(zeilen)


def melde_url(zeile: dict, *, version: str = "") -> str:
    """Die GitHub-Prefill-URL. PBP oeffnet sie nur — abgeschickt wird
    im Formular."""
    quelle = str((zeile or {}).get("scraper_name") or "unbekannt")
    text = bericht(zeile, version=version)
    basis = (f"https://github.com/{REPO}/issues/new"
             f"?template={TEMPLATE}&labels={LABEL}"
             f"&title={quote(f'Quelle defekt: {quelle}')}"
             f"&quelle={quote(quelle)}")
    # Der Diagnoseblock wird gekuerzt, bis die URL passt — die Grenze
    # liegt an der URL, nicht am Text.
    while True:
        url = f"{basis}&diagnose={quote(text)}"
        if len(url) <= MAX_URL or not text:
            return url
        # Von hinten kuerzen: die vorderen Zeilen tragen die Kernangaben.
        zeilen = text.split("\n")
        if len(zeilen) <= 1:
            text = text[:max(0, len(text) - 200)]
        else:
            text = "\n".join(zeilen[:-1])


def such_url(quelle: str) -> str:
    """Wo man nachsieht, ob es die Meldung schon gibt."""
    frage = quote(f'repo:{REPO} is:issue is:open label:{LABEL} "{quelle}"')
    return f"https://github.com/search?q={frage}&type=issues"


def vorhandene_meldung(quelle: str, client=None) -> dict:
    """Gibt es schon ein offenes Issue zu dieser Quelle?

    Bewusst OHNE Token: die Suche laeuft unangemeldet und ist
    ratenbegrenzt. **Ein Fehlschlag darf den Melde-Weg nie blockieren**
    — dann fehlt der Hinweis, mehr nicht. Ein Schutz, der den Nutzer
    aussperrt, wenn er selbst ausfaellt, waere schlimmer als keiner.
    """
    ergebnis = {"geprueft": False, "gefunden": [], "suche": such_url(quelle)}
    if not quelle:
        return ergebnis
    try:
        if client is None:  # pragma: no cover — Netzweg
            import httpx
            client = httpx.Client(timeout=8)
        antwort = client.get(
            "https://api.github.com/search/issues",
            params={"q": f'repo:{REPO} is:issue is:open '
                         f'label:{LABEL} "{quelle}"'},
            headers={"Accept": "application/vnd.github+json"},
        )
        if getattr(antwort, "status_code", 0) != 200:
            return ergebnis
        daten = antwort.json() or {}
        ergebnis["geprueft"] = True
        ergebnis["gefunden"] = [
            {"nummer": e.get("number"), "titel": (e.get("title") or "")[:120],
             "url": e.get("html_url", "")}
            for e in (daten.get("items") or [])[:5]
        ]
    except Exception as exc:
        logger.debug("Dublettenpruefung (#937) nicht moeglich: %s", exc)
    return ergebnis


def angebot(zeile: dict, *, version: str = "", client=None) -> dict | None:
    """Alles, was der Dialog braucht — oder None, wenn nicht meldbar."""
    if not ist_meldbar(zeile):
        return None
    quelle = str((zeile or {}).get("scraper_name") or "")
    text = bericht(zeile, version=version)
    return {
        "quelle": quelle,
        "bericht": text,
        "url": melde_url(zeile, version=version),
        "vorhandene": vorhandene_meldung(quelle, client=client),
        "hinweis": (
            "PBP schickt nichts ab. Der Knopf oeffnet das "
            "GitHub-Formular mit diesen Angaben; abschicken tust du. "
            "Wichtig ist das Feld 'wozu brauchst du die Quelle' — "
            "der Defekt allein ist bekannt, der Bedarf nicht."),
    }
