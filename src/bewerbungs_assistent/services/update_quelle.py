"""Woher PBP erfaehrt, dass es eine neue Version gibt (#1069).

Bis v1.7.121 fragte die Pruefung ausschliesslich
`api.github.com/repos/MadGapun/PBP/releases/latest`. Das ist der einzige
Weg, auf dem eine installierte Kopie von einer neuen Version erfaehrt —
und er steht auf einem Bein. Faellt GitHub als Quelle weg (Repo privat,
Umzug der Entwicklung, geaenderter Pfad), bleibt die Anzeige stumm:
`update_available` ist dann dauerhaft False, **ohne Fehlermeldung**. Der
Mensch merkt nicht, dass er nichts mehr erfaehrt.

Das ist #989 an der Update-Pruefung: "konnte nicht nachsehen" sah aus
wie "alles aktuell".

Drei Aenderungen:

* **Mehrere Quellen, der Reihe nach.** Welche, steht in der
  Konfiguration (`update_quellen`), nicht im Code.
* **Die Linie zaehlt.** Wer auf 1.7 stable sitzt, soll keine 1.8-Beta
  als Update angeboten bekommen.
* **Antwortet keine Quelle, sagt PBP das.** `stand: unbekannt` statt
  eines stillen "aktuell".

Und eine vierte (#1144 Punkt 2): **die Liste der Veroeffentlichungen.**
`releases/latest` nennt immer nur die neueste STABILE Version. Fuer eine
Beta-Installation (Linie 1.8) war das die 1.7-Linie, der Linienfilter
verwarf sie, und die Anzeige stand dauerhaft auf "unbekannt" mit dem
falschen Grund "keine Quelle hat geantwortet" - obwohl GitHub mit 200
antwortete. Ab dem Tag, an dem 1.8 zur neuesten stabilen Version wird,
haette es jede 1.7-Installation getroffen. Deshalb fragt PBP als dritte
Quelle die Liste (`releases?per_page=30`) und nimmt daraus die neueste
Version der eigenen Linie; Vorabversionen zaehlen nur fuer eine
Installation, die selbst eine Vorabversion ist.

Und eine fuenfte (#1168): **eine hoehere Linie wird gemeldet, nie angeboten.**
Der Linienfilter hat eine Kehrseite: Sobald 1.8.0 erscheint, zeigt jede
1.7-Installation "aktuell", und niemand erfaehrt in PBP, dass es 1.8 gibt
(und damit das Auto-Update). Deshalb merkt sich die Pruefung zusaetzlich die
neueste STABILE Version einer hoeheren Linie (`neue_linie`). Sie wird nie als
Update angeboten - der Wechsel der Linie geht einmal von Hand -, aber die
Oberflaeche nennt sie mit dem Weg dorthin. Vorabversionen und Entwuerfe zaehlen
dafuer nie. Erkannt wird sie an `releases/latest` (oder der Liste), deshalb
traegt `--latest` immer die neueste stabile Linie.

**Gemessen am 21.09.2026:** der ELWOSA-Endpunkt antwortet mit HTTP 404 —
die Domain gibt es, die Route noch nicht. Er steht trotzdem an erster
Stelle, weil er fuer den Umzug gedacht ist; bis dahin ist der Rueckfall
auf GitHub der reale Pfad und wird damit von Anfang an benutzt statt
nur behauptet.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Die Vorgabe. Ueberschreibbar ueber die Einstellung `update_quellen`,
#: damit eine Installation umziehen kann, ohne auf ein Update zu warten
#: — was bei einer kaputten Update-Pruefung ein Widerspruch waere.
STANDARD_QUELLEN = [
    {
        "name": "elwosa",
        "url": "https://elwosa.de/api/projects/pbp/releases/latest",
        "art": "elwosa",
    },
    {
        "name": "github",
        "url": "https://api.github.com/repos/MadGapun/PBP/releases/latest",
        "art": "github",
    },
    # #1144 Punkt 2: die Liste, falls `latest` nichts aus der eigenen Linie nennt.
    {
        "name": "github-liste",
        "url": "https://api.github.com/repos/MadGapun/PBP/releases?per_page=30",
        "art": "github_liste",
    },
]

#: Quellen, die die GitHub-API sprechen (Kopfzeile, kein `linie`-Parameter).
GITHUB_ARTEN = ("github", "github_liste")

#: Wie lange eine Antwort gilt, wenn die Quelle nichts anderes sagt.
STANDARD_PAUSE_S = 3600

#: Wie lange ein FEHLSCHLAG gilt (#1134). Ein Erfolg bleibt bei der Pause der
#: Quelle (eine Stunde). Ein Fehlschlag darf nicht ebenso lange stehen
#: bleiben: ein einziger Netzfehler beim Start (Netz noch nicht bereit,
#: Zeitueberschreitung) nahm der Anzeige sonst eine Stunde lang jede
#: Auskunft, und "unbekannt" blieb stehen, obwohl das Netz laengst da war.
FEHLSCHLAG_PAUSE_S = 120
FEHLSCHLAG_PAUSE_MAX_S = 900

#: Ein Klick auf "Jetzt pruefen" umgeht den Speicher, aber nicht dichter als
#: so: GitHub erlaubt ohne Anmeldung 60 Anfragen je Stunde und Adresse.
MIN_ABSTAND_FRISCH_S = 15


def linie_von(version: str) -> str:
    """'1.7.122' -> '1.7'. Die Linie, auf der eine Installation sitzt."""
    teile = (version or "").split(".")
    return ".".join(teile[:2]) if len(teile) >= 2 else (version or "")


def quellen(db=None) -> list[dict]:
    """Die konfigurierte Quellenliste, sonst die Vorgabe."""
    if db is None:
        return list(STANDARD_QUELLEN)
    try:
        eigene = db.get_setting("update_quellen", None)
    except Exception:  # pragma: no cover — nie die Pruefung kippen
        eigene = None
    if not eigene:
        return list(STANDARD_QUELLEN)
    gueltig = [q for q in eigene
               if isinstance(q, dict) and q.get("url") and q.get("art")]
    return gueltig or list(STANDARD_QUELLEN)


def _passt_zur_linie(version: str, linie: str) -> bool:
    """Gehoert diese Version zur Linie der Installation?

    Ohne Linie kein Filter. Eine 1.8-Beta ist fuer eine 1.7-Installation
    kein Update, auch wenn die Zahl groesser ist.
    """
    return not linie or linie_von(version) == linie


def _ist_vorabversion(version: str) -> bool:
    try:
        from packaging.version import Version
        return Version(version).is_prerelease
    except Exception:
        return False


def _version_oder_none(text: str):
    try:
        from packaging.version import Version
        return Version(text)
    except Exception:
        return None


def auswerten_liste(daten, aktuell: str, linie: str) -> dict | None:
    """Aus der Liste der Veroeffentlichungen die neueste Version der Linie nehmen (#1144 Punkt 2).

    Entwuerfe zaehlen nie. Vorabversionen (Beta) zaehlen nur, wenn die
    Installation selbst eine ist: wer auf der stabilen Linie sitzt, bekommt
    keine Beta angeboten, wer eine Beta nutzt, bekommt die naechste Beta und
    die fertige Version.
    """
    if not isinstance(daten, list):
        return None
    mit_vorab = _ist_vorabversion(aktuell)
    beste = None
    for eintrag in daten:
        if not isinstance(eintrag, dict) or eintrag.get("draft"):
            continue
        version = str(eintrag.get("tag_name") or "").lstrip("v")
        if not version or not _passt_zur_linie(version, linie):
            continue
        parsed = _version_oder_none(version)
        if parsed is None:
            continue
        if (eintrag.get("prerelease") or parsed.is_prerelease) and not mit_vorab:
            continue
        if beste is None or parsed > beste[0]:
            beste = (parsed, version, eintrag)
    if beste is None:
        return None
    _, version, eintrag = beste
    return {"version": version, "url": eintrag.get("html_url") or "",
            "name": eintrag.get("name") or "", "pause_s": STANDARD_PAUSE_S}


def auswerten(art: str, daten, aktuell: str, linie: str) -> dict | None:
    """Die Antwort EINER Quelle deuten — ohne Netz, damit testbar.

    Rueckgabe: {"version", "url", "name", "pause_s"} oder None, wenn die
    Antwort nichts Brauchbares enthaelt.
    """
    if art == "github_liste":
        return auswerten_liste(daten, aktuell, linie)
    if not isinstance(daten, dict):
        return None
    if art == "github":
        version = (daten.get("tag_name") or "").lstrip("v")
        url = daten.get("html_url") or ""
        name = daten.get("name") or ""
        pause = STANDARD_PAUSE_S
    else:
        version = str(daten.get("version") or "").lstrip("v")
        url = daten.get("download_url") or daten.get("url") or ""
        name = daten.get("notiz") or daten.get("name") or ""
        try:
            pause = int(daten.get("poll_after_seconds") or STANDARD_PAUSE_S)
        except (TypeError, ValueError):
            pause = STANDARD_PAUSE_S
    if not version:
        return None
    if not _passt_zur_linie(version, linie):
        return None
    return {"version": version, "url": url, "name": name,
            "pause_s": max(60, pause)}


def _linie_hoeher(version: str, aktuell: str) -> bool:
    """Liegt `version` auf einer hoeheren Linie als `aktuell`? ('1.8.0' gegen '1.7.151': ja; '1.10' gegen '1.9': ja)."""
    neu = _version_oder_none(linie_von(version))
    alt = _version_oder_none(linie_von(aktuell))
    return neu is not None and alt is not None and neu > alt


def neue_linie(art: str, daten, aktuell: str) -> dict | None:
    """Die neueste STABILE Version einer hoeheren Linie in der Antwort EINER Quelle (#1168), sonst None.

    Ohne Netz, damit testbar. Entwuerfe und Vorabversionen zaehlen nie: eine 1.8-Beta ist fuer eine
    1.7-Installation keine Nachricht wert. Rueckgabe: {"version", "linie", "url", "name"}.
    """
    kandidaten = []
    if art == "github_liste":
        if not isinstance(daten, list):
            return None
        for eintrag in daten:
            if isinstance(eintrag, dict) and not eintrag.get("draft") and not eintrag.get("prerelease"):
                kandidaten.append((eintrag.get("tag_name"), eintrag.get("html_url"), eintrag.get("name")))
    elif isinstance(daten, dict):
        if art == "github":
            if not daten.get("draft") and not daten.get("prerelease"):
                kandidaten.append((daten.get("tag_name"), daten.get("html_url"), daten.get("name")))
        else:
            kandidaten.append((daten.get("version"), daten.get("download_url") or daten.get("url"),
                               daten.get("notiz") or daten.get("name")))
    beste = None
    for tag, url, name in kandidaten:
        version = str(tag or "").lstrip("v")
        parsed = _version_oder_none(version)
        if parsed is None or parsed.is_prerelease or not _linie_hoeher(version, aktuell):
            continue
        if beste is None or parsed > beste[0]:
            beste = (parsed, version, url, name)
    if beste is None:
        return None
    _, version, url, name = beste
    return {"version": version, "linie": linie_von(version), "url": url or "", "name": name or ""}


def fehlschlag_pause_s(fehlversuche: int) -> int:
    """Wie lange der n-te Fehlschlag in Folge gemerkt wird.

    120, 240, 480 Sekunden, danach hoechstens 900: ein kurzer Netzfehler ist
    bald behoben, ein dauerhafter Ausfall wird nicht im Zwei-Minuten-Takt
    bedraengt.
    """
    n = max(1, int(fehlversuche or 1))
    return min(FEHLSCHLAG_PAUSE_MAX_S, FEHLSCHLAG_PAUSE_S * 2 ** min(n - 1, 10))


def mit_restzeit(ergebnis: dict, rest_s: float) -> dict:
    """Kopie der Antwort mit `wieder_fragen_nach_s`: wann die Oberflaeche
    erneut fragen soll (mindestens 5 Sekunden). Der gemerkte Eintrag selbst
    bleibt unveraendert."""
    antwort = dict(ergebnis)
    antwort["wieder_fragen_nach_s"] = max(5, int(rest_s))
    return antwort


def ist_neuer(kandidat: str, aktuell: str) -> bool:
    try:
        from packaging.version import Version
        return Version(kandidat) > Version(aktuell)
    except Exception:
        return bool(kandidat) and kandidat != aktuell
