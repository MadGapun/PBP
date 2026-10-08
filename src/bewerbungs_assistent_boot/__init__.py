"""Startbaustein: waehlt beim Start die aktuelle PBP-Fassung (#1093, v1.8).

Dieses Paket ist der Teil von PBP, der sich NIE aendert. Der Installer legt eine
Kopie nach `<Programmordner>/boot`; Claude Desktop und die Desktop-Verknuepfung
starten PBP ueber `python -m bewerbungs_assistent_boot` bzw. den kleinen Starter
`start_dashboard.py` im Programmordner. Von hier aus geht es weiter in die
Fassung, auf die `aktuell.txt` zeigt:

    <Programmordner>/
        python/                 Laufzeit (nur der Installer aendert sie)
        boot/                   dieses Paket
        versions/<fassung>/     src/, start_dashboard.py, _selftest.py, manifest.json,
                                .fertig, optional site/ (zusaetzliche Pakete)
        aktuell.txt             "1.8.1" — atomar ersetzt, nie halb geschrieben
        update_status.json      Start bestaetigt? Vorherige Fassung? Rueckfall?

Warum so: unter Windows laesst sich Code, den ein laufender Prozess geladen hat,
nicht ersetzen, und das Ueberschreiben mischt zwei Fassungen in einem Prozess.
Neue Fassungen entstehen deshalb in einem NEUEN Ordner, `aktuell.txt` wird erst
ganz am Ende umgestellt, und der naechste Start nimmt die neue Fassung.

Weil dieser Baustein sich nie aendert, ist alles hier **nur Standardbibliothek**,
bewusst klein und defensiv. Die Dateinamen und das Format der Statusdatei sind
ein Vertrag mit dem Programm (`services/auto_update`); `tests/test_v18_auto_update_boot.py`
haelt beide Seiten gegeneinander.

Rueckfall (Akzeptanzkriterium 5): startet eine neue Fassung nicht, laeuft wieder
die vorige und PBP sagt das.

* **Harter Fehler** — die Fassung wirft eine Ausnahme, BEVOR sie `bereit_melden()` gerufen hat
  (Importfehler, Syntaxfehler, Migrationsfehler, ein Fehler in ihrem Startcode): sofort zurueck, im
  selben Prozess. Danach ist jede Ausnahme eine des laufenden Betriebs (zum Beispiel eine abrupt
  getrennte Verbindung zu Claude Desktop) und kein Grund, die Fassung zu verwerfen.
* **Stiller Fehler** — der Prozess starb, ohne je zu bestaetigen: nach
  `MAX_UNBESTAETIGT` solchen Starts hintereinander zurueck. Ein Start, der erst
  Sekunden alt ist, zaehlt nicht (zwei Prozesse starten gleichzeitig: Claude
  Desktop und die Verknuepfung).

Die Fassung bestaetigt ihren Start selbst (`services/auto_update/zustand.py`), sobald
Datenbank und Dashboard bereit sind.
"""
from __future__ import annotations

import atexit
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Vertrag mit dem Programm (nie aendern ohne neues FORMAT) ──────────────────────
FORMAT = 1
ENV_APP = "PBP_APP_DIR"
ENV_FASSUNG = "PBP_FASSUNG"
VERSIONEN = "versions"
AKTUELL = "aktuell.txt"
STATUS = "update_status.json"
FERTIG = ".fertig"
BELEGUNG = ".in_benutzung"
PAKET = "bewerbungs_assistent"
#: So viele Starts hintereinander ohne Bestaetigung, dann wird zurueckgeschaltet.
MAX_UNBESTAETIGT = 2
#: Ein unbestaetigter Start, der juenger ist, laeuft vielleicht noch an (zweiter Prozess).
NACHSICHT_S = 90

# ASCII und fullmatch: `\d` laesst auch arabisch-indische Ziffern zu und `$` ein Zeilenende am Schluss.
_BEREIT = False

_FASSUNG = re.compile(r"([0-9]{1,3})\.([0-9]{1,3})\.([0-9]{1,4})(?:-(alpha|beta|rc)\.([0-9]{1,3}))?", re.ASCII)
_RANG = {None: 9, "rc": 3, "beta": 2, "alpha": 1}


def sortschluessel(fassung):
    """Vergleichswert einer Fassung; None, wenn es keine gueltige Fassung ist."""
    m = _FASSUNG.fullmatch(fassung) if isinstance(fassung, str) else None
    if not m:
        return None
    major, minor, patch, art, nr = m.groups()
    return (int(major), int(minor), int(patch), _RANG[art], int(nr or 0))


def app_dir():
    """Der Programmordner, oder None, wenn PBP nicht ueber den Installer eingerichtet ist."""
    roh = os.environ.get(ENV_APP)
    if roh:
        p = Path(roh)
        return p if p.is_dir() else None
    try:
        paket = Path(__file__).resolve().parent
        if paket.parent.name == "boot" and (paket.parent.parent / VERSIONEN).is_dir():
            return paket.parent.parent
    except OSError:
        pass
    return None


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def schreibe_atomar(pfad: Path, text: str) -> None:
    """Datei ganz oder gar nicht ersetzen (nie halb geschrieben sichtbar)."""
    tmp = pfad.with_name(f"{pfad.name}.tmp-{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, pfad)
    finally:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass


def lese_status(app) -> dict:
    """Die Statusdatei; fehlt sie oder ist sie kaputt, ein leerer Stand (nie eine Ausnahme)."""
    try:
        daten = json.loads((Path(app) / STATUS).read_text(encoding="utf-8-sig"))
        if isinstance(daten, dict):
            return daten
    except (OSError, ValueError):
        pass
    return {"format": FORMAT}


def schreibe_status(app, status: dict) -> None:
    status = dict(status)
    status["format"] = FORMAT
    try:
        schreibe_atomar(Path(app) / STATUS, json.dumps(status, ensure_ascii=False, indent=1))
    except OSError:
        pass  # ein Status, der sich nicht schreiben laesst, darf den Start nicht verhindern


def lese_aktuell(app):
    try:
        text = (Path(app) / AKTUELL).read_text(encoding="utf-8-sig").strip()
    except OSError:
        return None
    return text if sortschluessel(text) else None


def fassung_gueltig(app, fassung) -> bool:
    """Ein fertig installierter Ordner: Marke `.fertig` und das Paket sind da."""
    if not sortschluessel(fassung):
        return False
    ordner = Path(app) / VERSIONEN / fassung
    return (ordner / FERTIG).is_file() and (ordner / "src" / PAKET / "__init__.py").is_file()


def gueltige_fassungen(app) -> list:
    """Alle fertig installierten Fassungen, die neueste zuerst."""
    wurzel = Path(app) / VERSIONEN
    try:
        namen = [p.name for p in wurzel.iterdir() if p.is_dir()]
    except OSError:
        return []
    ok = [n for n in namen if fassung_gueltig(app, n)]
    return sorted(ok, key=sortschluessel, reverse=True)


def _log(app, text: str) -> None:
    """Zeile in `<app>/boot.log` (bei ueber 200 KB wird die aeltere Haelfte verworfen)."""
    try:
        pfad = Path(app) / "boot.log"
        zeile = f"{_jetzt()} {text}\n"
        if pfad.exists() and pfad.stat().st_size > 200_000:
            alt = pfad.read_text(encoding="utf-8", errors="replace")
            pfad.write_text(alt[len(alt) // 2:], encoding="utf-8")
        with open(pfad, "a", encoding="utf-8") as f:
            f.write(zeile)
    except OSError:
        pass


def _alter_s(iso) -> float:
    try:
        return (datetime.now(timezone.utc) - datetime.fromisoformat(str(iso))).total_seconds()
    except (TypeError, ValueError):
        return 10 ** 9


def _rueckfall_ziel(app, von: str, status: dict):
    """Auf welche Fassung zurueck? Die gemerkte vorherige, sonst die neueste aeltere."""
    vorherige = status.get("vorherige")
    if vorherige and vorherige != von and fassung_gueltig(app, vorherige):
        return vorherige
    schluessel_von = sortschluessel(von)
    for kandidat in gueltige_fassungen(app):
        if kandidat != von and (schluessel_von is None or sortschluessel(kandidat) < schluessel_von):
            return kandidat
    return None


def _zuruecknehmen(app, von: str, nach: str, grund: str, status: dict) -> dict:
    """Schaltet `aktuell.txt` auf `nach` zurueck und merkt, warum (fuer die Meldung im Dashboard)."""
    schreibe_atomar(Path(app) / AKTUELL, nach + "\n")
    gescheitert = [v for v in status.get("gescheitert", []) if isinstance(v, str)]
    if von not in gescheitert:
        gescheitert.append(von)
    status["gescheitert"] = gescheitert
    status["rueckgang"] = {"von": von, "nach": nach, "grund": grund[:300], "zeit": _jetzt(), "gemeldet": False}
    status["start"] = {"version": nach, "versuche": 1, "bestaetigt": False, "zeit": _jetzt()}
    schreibe_status(app, status)
    _log(app, f"RUECKFALL {von} -> {nach}: {grund[:300]}")
    return status


def waehle_fassung(app):
    """Welche Fassung startet? Gibt (fassung, hinweis) zurueck; fassung None, wenn keine brauchbar ist."""
    status = lese_status(app)
    hinweis = None
    aktuell = lese_aktuell(app)
    if aktuell and not fassung_gueltig(app, aktuell):
        hinweis = f"Fassung {aktuell} ist unvollstaendig oder fehlt"
        _log(app, hinweis)
        aktuell = None
    if aktuell is None:
        gueltig = gueltige_fassungen(app)
        if not gueltig:
            return None, hinweis or "Keine installierte Fassung gefunden"
        aktuell = gueltig[0]
        try:
            schreibe_atomar(Path(app) / AKTUELL, aktuell + "\n")
        except OSError:
            pass
        _log(app, f"aktuell.txt neu gesetzt auf {aktuell}")

    start = status.get("start") if isinstance(status.get("start"), dict) else {}
    versuche = 1
    if start.get("version") == aktuell and not start.get("bestaetigt"):
        bisher = int(start.get("versuche") or 1)
        frisch = _alter_s(start.get("zeit")) < NACHSICHT_S
        if frisch:
            versuche = bisher  # laeuft vielleicht noch an: nicht als gescheitert zaehlen
        elif start.get("fehler") or bisher >= MAX_UNBESTAETIGT:
            ziel = _rueckfall_ziel(app, aktuell, status)
            if ziel:
                grund = start.get("fehler") or f"{bisher} Starts hintereinander ohne Bestaetigung"
                _zuruecknehmen(app, aktuell, ziel, grund, status)
                return ziel, f"Fassung {aktuell} liess sich nicht starten, PBP laeuft wieder mit {ziel}"
        else:
            versuche = bisher + 1
    status["start"] = {"version": aktuell, "versuche": versuche, "bestaetigt": False, "zeit": _jetzt()}
    schreibe_status(app, status)
    return aktuell, hinweis


def bereit_melden() -> None:
    """Die Fassung meldet: mein Startcode ist durch, ab jetzt laufe ich. Spaetere Ausnahmen sind kein Versionsfehler."""
    global _BEREIT
    _BEREIT = True


def ist_bereit() -> bool:
    return _BEREIT


def start_bestaetigen(app, fassung: str) -> bool:
    """Die Fassung meldet: Datenbank und Dashboard sind bereit. Gibt True, wenn eingetragen."""
    status = lese_status(app)
    start = status.get("start") if isinstance(status.get("start"), dict) else {}
    if start.get("version") != fassung:
        return False
    start["bestaetigt"] = True
    start["bestaetigt_am"] = _jetzt()
    start.pop("fehler", None)
    status["start"] = start
    status["bestaetigt"] = fassung
    schreibe_status(app, status)
    return True


def _belegung_anlegen(app, fassung: str):
    """Marke 'dieser Prozess benutzt diese Fassung', damit sie nie unter ihm geloescht wird."""
    try:
        ordner = Path(app) / VERSIONEN / fassung / BELEGUNG
        ordner.mkdir(exist_ok=True)
        datei = ordner / f"{os.getpid()}.json"
        datei.write_text(json.dumps({"pid": os.getpid(), "version": fassung, "start": _jetzt()}), encoding="utf-8")

        def _weg():
            try:
                datei.unlink()
            except OSError:
                pass
        atexit.register(_weg)
        return datei
    except OSError:
        return None


def _pfade_einrichten(app, fassung: str) -> None:
    """`sys.path` auf die Fassung stellen; alte Einraege auf den frueheren `app/src` fliegen raus."""
    ordner = Path(app) / VERSIONEN / fassung
    alt_src = str(Path(app) / "src")
    sys.path[:] = [p for p in sys.path if p != alt_src]
    eintraege = [str(ordner / "src")]
    zusatz = ordner / "site"
    if zusatz.is_dir():
        eintraege.append(str(zusatz))
    for i, e in enumerate(eintraege):
        if e in sys.path:
            sys.path.remove(e)
        sys.path.insert(i, e)
    os.environ[ENV_APP] = str(app)
    os.environ[ENV_FASSUNG] = fassung


def _module_vergessen() -> None:
    """Fuer den Rueckfall im selben Prozess: halb geladene Module der gescheiterten Fassung verwerfen."""
    for name in [n for n in sys.modules if n == PAKET or n.startswith(PAKET + ".")]:
        del sys.modules[name]


def _ausfuehren(app, fassung: str, ziel: str) -> None:
    import runpy
    if ziel == "dashboard":
        runpy.run_path(str(Path(app) / VERSIONEN / fassung / "start_dashboard.py"), run_name="__main__")
    else:
        runpy.run_module(PAKET, run_name="__main__", alter_sys=True)


def _lauf(app, fassung: str, ziel: str, rueckfall_erlaubt: bool) -> None:
    _pfade_einrichten(app, fassung)
    _belegung_anlegen(app, fassung)
    _log(app, f"Start {ziel} mit {fassung} (pid {os.getpid()})")
    try:
        _ausfuehren(app, fassung, ziel)
    except Exception as exc:  # SystemExit/KeyboardInterrupt laufen bewusst durch
        status = lese_status(app)
        start = status.get("start") if isinstance(status.get("start"), dict) else {}
        bestaetigt = start.get("version") == fassung and start.get("bestaetigt")
        if bestaetigt or _BEREIT or not rueckfall_erlaubt:
            raise
        beschreibung = f"{type(exc).__name__}: {exc}"[:300]
        start.update({"version": fassung, "fehler": beschreibung})
        status["start"] = start
        ziel_fassung = _rueckfall_ziel(app, fassung, status)
        if not ziel_fassung:
            schreibe_status(app, status)
            _log(app, f"FEHLER ohne Rueckfall in {fassung}: {beschreibung}")
            raise
        _zuruecknehmen(app, fassung, ziel_fassung, beschreibung, status)
        print(f"[PBP] Fassung {fassung} liess sich nicht starten ({beschreibung}). "
              f"PBP laeuft wieder mit {ziel_fassung}.", file=sys.stderr)
        _module_vergessen()
        _lauf(app, ziel_fassung, ziel, rueckfall_erlaubt=False)


def starte(ziel: str = "server") -> None:
    """Einstieg: Fassung waehlen und starten. `ziel` ist 'server' oder 'dashboard'."""
    app = app_dir()
    if app is None:
        print("[PBP] Der Programmordner wurde nicht gefunden. Bitte INSTALLIEREN.bat noch einmal ausfuehren.",
              file=sys.stderr)
        raise SystemExit(1)
    fassung, hinweis = waehle_fassung(app)
    if fassung is None:
        print(f"[PBP] {hinweis}. Bitte INSTALLIEREN.bat noch einmal ausfuehren.", file=sys.stderr)
        raise SystemExit(1)
    if hinweis:
        print(f"[PBP] {hinweis}", file=sys.stderr)
    _lauf(app, fassung, ziel, rueckfall_erlaubt=True)
