"""Woher das Auto-Update installieren darf — fest im Code, nie eine Einstellung (#1093 Akzeptanzkriterium 6).

Zwei Dinge sind zu unterscheiden:

* **Nachsehen**, ob es etwas Neues gibt (`update_quelle.py`, Einstellung `update_quellen`):
  die Quelle darf umgelenkt werden, ein Irrtum kostet hoechstens eine falsche Anzeige.
* **Installieren** (dieses Modul): geladen wird ausschliesslich von den GitHub-Releases dieses
  Repos. Adressen werden aus festen Teilen und einer streng geprueften Versionsnummer
  gebaut, nie aus einem Wert, den die Antwort einer Quelle nennt. Eine Weiterleitung darf
  nur zu den Hosts, ueber die GitHub Release-Dateien ausliefert.

Ohne diese Trennung genuegte ein geaenderter Wert in der Datenbank fuer eine Codeausfuehrung.

Das Netz ist austauschbar (`oeffner`): Tests geben ein Testdoppel herein, kein Test ruft
GitHub auf.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from . import fassung as _fassung
from .fehler import UpdateFehler

REPO = "MadGapun/PBP"
API_FREIGABEN = f"https://api.github.com/repos/{REPO}/releases?per_page=30"
DOWNLOAD_BASIS = f"https://github.com/{REPO}/releases/download"

#: Von hier aus darf eine Anfrage beginnen ...
START_HOSTS = frozenset({"github.com", "api.github.com"})
#: ... und hierhin darf GitHub weiterleiten (Release-Dateien liegen bei githubusercontent).
WEITERLEITUNG_HOSTS = frozenset({
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "github-releases.githubusercontent.com",
})
MAX_WEITERLEITUNGEN = 5

ARCHIV_NAME = "pbp-update-{version}.zip"
SUMMEN_NAME = "SHA256SUMS"
SIGNATUR_NAME = "SHA256SUMS.sig"

#: Obergrenzen. Das Archiv ist heute rund 20 MB gross; ab dieser Grenze stimmt etwas nicht.
MAX_ARCHIV_BYTES = 150 * 1024 * 1024
MAX_SUMMEN_BYTES = 64 * 1024
MAX_SIGNATUR_BYTES = 4 * 1024
MAX_JSON_BYTES = 4 * 1024 * 1024
BLOCK = 64 * 1024

USER_AGENT = "PBP-Auto-Update"


def _url_pruefen(url: str, *, erlaubte_hosts) -> str:
    """https, kein Zugang in der Adresse, kein Fremdport, Host aus der Liste — sonst Abbruch."""
    try:
        teile = urllib.parse.urlsplit(url)
        host = (teile.hostname or "").lower()
        port = teile.port
    except ValueError as exc:
        raise UpdateFehler("quelle_nicht_erlaubt", detail=f"Adresse nicht lesbar: {exc}") from exc
    if teile.scheme != "https" or host not in erlaubte_hosts or teile.username or teile.password or port not in (None, 443):
        raise UpdateFehler("quelle_nicht_erlaubt", detail=f"{teile.scheme}://{host}")
    return url


def asset_url(version: str, name: str) -> str:
    """Die Adresse einer Datei im Release `v<version>` — aus festen Teilen gebaut.

    #1199: auch eine Vorab-Fassung ist erlaubt, solange sie GUELTIG ist (strenger ASCII-Fullmatch,
    kein Pfad-Trick). Welche Fassung ueberhaupt gezogen werden darf (Linie, stabil vs. Vorab), hat
    `neueste_fuer_linie`/`kandidat_erlaubt` schon entschieden; hier zaehlt nur die Form der Nummer.
    """
    if not _fassung.gueltig(version):
        raise UpdateFehler("quelle_nicht_erlaubt", detail=f"keine gueltige Fassung: {version!r}")
    erlaubt = {ARCHIV_NAME.format(version=version), SUMMEN_NAME, SIGNATUR_NAME}
    if name not in erlaubt:
        raise UpdateFehler("quelle_nicht_erlaubt", detail=f"Dateiname nicht vorgesehen: {name!r}")
    return _url_pruefen(f"{DOWNLOAD_BASIS}/v{version}/{name}", erlaubte_hosts=START_HOSTS)


class _PruefendeWeiterleitung(urllib.request.HTTPRedirectHandler):
    max_redirections = MAX_WEITERLEITUNGEN

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _url_pruefen(newurl, erlaubte_hosts=WEITERLEITUNG_HOSTS)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def standard_oeffner():
    """Der echte Oeffner: Standardbibliothek, Weiterleitungen werden Schritt fuer Schritt geprueft."""
    return urllib.request.build_opener(_PruefendeWeiterleitung())


def _anfrage(url: str, version_pbp: str = "", accept: str = "*/*") -> urllib.request.Request:
    agent = f"{USER_AGENT}/{version_pbp}" if version_pbp else USER_AGENT
    return urllib.request.Request(url, headers={"User-Agent": agent, "Accept": accept})


def json_holen(url: str = API_FREIGABEN, *, oeffner=None, timeout: float = 20.0, version_pbp: str = ""):
    """Die Liste der Veroeffentlichungen. Nur von der festen API-Adresse."""
    if url != API_FREIGABEN:
        raise UpdateFehler("quelle_nicht_erlaubt", detail="andere Adresse als die feste API")
    oeffner = oeffner or standard_oeffner()
    try:
        with oeffner.open(_anfrage(url, version_pbp, "application/vnd.github+json"), timeout=timeout) as antwort:
            roh = antwort.read(MAX_JSON_BYTES + 1)
    except UpdateFehler:
        raise
    except Exception as exc:
        raise UpdateFehler("netz", detail=f"{type(exc).__name__}: {exc}") from exc
    if len(roh) > MAX_JSON_BYTES:
        raise UpdateFehler("zu_gross", detail="Antwort der Liste")
    try:
        return json.loads(roh.decode("utf-8"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise UpdateFehler("netz", "GitHub hat eine unlesbare Antwort geschickt.", detail=str(exc)) from exc


def laden(url: str, ziel: Path, *, max_bytes: int, oeffner=None, fortschritt=None, abbruch=None,
          timeout: float = 30.0, version_pbp: str = "") -> int:
    """Eine Datei laden: erst in `<ziel>.part`, erst bei vollstaendigem Empfang unter dem Zielnamen.

    Jeder Abbruchweg raeumt die `.part`-Datei weg (Akzeptanzkriterium 12). Gibt die Groesse zurueck.
    """
    _url_pruefen(url, erlaubte_hosts=START_HOSTS)
    oeffner = oeffner or standard_oeffner()
    ziel = Path(ziel)
    teil = ziel.with_name(ziel.name + ".part")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    geladen = 0
    try:
        with oeffner.open(_anfrage(url, version_pbp), timeout=timeout) as antwort:
            laenge = None
            try:
                roh = antwort.headers.get("Content-Length") if getattr(antwort, "headers", None) else None
                laenge = int(roh) if roh not in (None, "") else None
            except (TypeError, ValueError):
                laenge = None
            if laenge is not None and laenge > max_bytes:
                raise UpdateFehler("zu_gross", detail=f"{laenge} Byte angekündigt, erlaubt {max_bytes}")
            with open(teil, "wb") as f:
                while True:
                    if abbruch is not None and abbruch():
                        raise UpdateFehler("abgebrochen")
                    stueck = antwort.read(BLOCK)
                    if not stueck:
                        break
                    geladen += len(stueck)
                    if geladen > max_bytes:
                        raise UpdateFehler("zu_gross", detail=f"mehr als {max_bytes} Byte empfangen")
                    f.write(stueck)
                    if fortschritt is not None:
                        fortschritt(geladen, laenge)
                f.flush()
                os.fsync(f.fileno())
        if laenge is not None and geladen != laenge:
            raise UpdateFehler("netz", "Die Datei kam nicht vollständig an.", detail=f"{geladen} von {laenge} Byte")
        os.replace(teil, ziel)
        return geladen
    except UpdateFehler:
        raise
    except Exception as exc:
        raise UpdateFehler("netz", detail=f"{type(exc).__name__}: {exc}") from exc
    finally:
        try:
            if teil.exists():
                teil.unlink()
        except OSError:
            pass


# ── Die Liste der Veroeffentlichungen auswerten ──────────────────────────────────────

@dataclass(frozen=True)
class Freigabe:
    version: str
    tag: str
    titel: str
    notizen: str
    veroeffentlicht: str
    dateien: dict  # Dateiname -> Groesse in Byte

    def hat(self, name: str) -> bool:
        return name in self.dateien


def freigaben_lesen(daten, *, vorab: bool = False) -> list:
    """Aus der JSON-Liste die brauchbaren Freigaben: keine Entwuerfe, nur gueltige Tags.

    Vorgabe: nur stabile Fassungen (Vorabversionen fallen raus, wie bisher). Mit `vorab=True`
    bleiben auch Vorab-Releases (Beta/RC) stehen — ob von der laufenden Fassung aus darauf
    aktualisiert werden darf, entscheidet erst `kandidat_erlaubt` (eine stabile Installation nie
    auf eine Vorab)."""
    ergebnis = []
    if not isinstance(daten, list):
        return ergebnis
    for eintrag in daten:
        if not isinstance(eintrag, dict) or eintrag.get("draft"):
            continue
        if eintrag.get("prerelease") and not vorab:
            continue
        tag = eintrag.get("tag_name")
        version = _fassung.aus_tag(tag)
        if version is None:
            continue
        if not vorab and not _fassung.ist_stabil(version):
            continue
        dateien = {}
        for a in eintrag.get("assets") or []:
            if isinstance(a, dict) and isinstance(a.get("name"), str):
                groesse = a.get("size")
                dateien[a["name"]] = groesse if isinstance(groesse, int) and groesse >= 0 else 0
        ergebnis.append(Freigabe(
            version=version, tag=tag, titel=str(eintrag.get("name") or tag)[:200],
            notizen=str(eintrag.get("body") or "")[:20000],
            veroeffentlicht=str(eintrag.get("published_at") or "")[:40], dateien=dateien))
    return ergebnis


def kandidat_erlaubt(kandidat_version: str, laufende_fassung: str, vorab: bool) -> bool:
    """Darf von `laufende_fassung` automatisch auf `kandidat_version` aktualisiert werden (#1199)?

    Die Linie prueft der Aufrufer. Hier nur die Vorab-Regel:
    * Eine stabile Ziel-Fassung ist immer erlaubt (stabil -> stabil, wie bisher).
    * Eine Vorab-Ziel-Fassung NUR, wenn der Nutzer Vorabversionen zugelassen hat (`vorab`) UND die
      laufende Fassung selbst eine Vorab ist. Eine stabile Installation wird nie auf eine Vorab gezogen.
    """
    if _fassung.ist_stabil(kandidat_version):
        return True
    return bool(vorab) and not _fassung.ist_stabil(laufende_fassung)


def neueste_fuer_linie(freigaben, laufende_fassung: str, *, vorab: bool = False):
    """Die neueste erlaubte Freigabe der eigenen Linie, die echt neuer ist — sonst None.

    Nie ein Linienwechsel (1.8 -> 1.9, 1.8 -> 2.0): der bleibt eine bewusste Handlung.
    Vorabversionen nur unter den Bedingungen von `kandidat_erlaubt`.
    """
    linie = _fassung.linie(laufende_fassung)
    if linie is None:
        return None
    kandidaten = [f for f in freigaben
                  if _fassung.linie(f.version) == linie
                  and _fassung.ist_neuer(f.version, laufende_fassung)
                  and kandidat_erlaubt(f.version, laufende_fassung, vorab)]
    if not kandidaten:
        return None
    return max(kandidaten, key=lambda f: _fassung.schluessel(f.version))


def vollstaendig(freigabe: Freigabe, signatur_noetig: bool) -> bool:
    """Sind alle Dateien da, die ein Update braucht? Fehlt eine, ist das Update (noch) nicht installierbar."""
    noetig = [ARCHIV_NAME.format(version=freigabe.version), SUMMEN_NAME]
    if signatur_noetig:
        noetig.append(SIGNATUR_NAME)
    return all(freigabe.hat(n) for n in noetig)
