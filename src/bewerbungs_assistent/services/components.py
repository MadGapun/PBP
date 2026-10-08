"""Optionale-Komponenten-Framework — I10 (#751, v1.8.0-beta.0).

Komponenten sind lokale Binaries/Runtimes, die PBP-KERN-Funktionen
freischalten (erste: Tesseract-OCR fuer gescannte PDFs, E19/#750; als
naechstes geplant: Playwright-Browser, B18/#656). Abgrenzung zu Plugins
(J1/#504): Komponenten werden von PBP AUFGERUFEN (subprocess), Plugins
rufen PBP an (Ingest-API) — Architektur-Entscheidung D2 im Wiki
(Plan-Roadmap-v18).

Grundregeln (User-Leitlinie, #751):
  1. NIE Auto-Install — jede Installation braucht eine explizite
     Zustimmung (MCP: ``bestaetigt=True``; REST: expliziter POST aus der
     Settings-UI). PBP darf nur ANBIETEN (on-demand, wenn eine Funktion
     die Komponente braucht).
  2. Groesse + Quelle + Lizenz werden VOR dem Download genannt.
  3. Extern installierte Binaries (PATH, Program Files) werden erkannt
     und genutzt, aber nie angefasst — deinstallieren betrifft nur, was
     PBP selbst nach ``components/`` gelegt hat.
  4. Ollama bleibt eigenstaendig verwaltet (llm_service) und wird in der
     Erweiterungen-UI nur mit-ANGEZEIGT.

Die Komponenten-DEFINITIONEN leben hier im Code; der Install-ZUSTAND in
der ``components``-Tabelle (Schema v49, database.py).
"""
from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger("bewerbungs_assistent")

# Statuswerte der components-Tabelle
STATUS_NICHT_INSTALLIERT = "nicht_installiert"
STATUS_WIRD_INSTALLIERT = "wird_installiert"
STATUS_INSTALLIERT = "installiert"
STATUS_FEHLER = "fehler"

_SUBPROCESS_FLAGS = {"creationflags": 0x08000000} if sys.platform == "win32" else {}

# ---------------------------------------------------------------------------
# Komponenten-Registry
# ---------------------------------------------------------------------------
# Jede Komponente mit Download-Adresse braucht eine SHA-256-Pruefsumme (#1152):
# ohne sie wird NICHTS geladen und nichts gestartet (`_pruefsumme_gueltig`).
# Die Summe aendert sich mit jeder Version und wird beim Versions-Bump
# nachgezogen; ein Test haelt, dass keine Komponente ohne sie in der Registry
# steht. Der Beta-Exit (Kriterium 3) verifiziert den kompletten Install-Pfad
# auf einer frischen Maschine.
COMPONENT_DEFS: dict[str, dict] = {
    "tesseract": {
        "label": "Tesseract OCR",
        "beschreibung": (
            "Texterkennung für gescannte PDFs — Zeugnisse, Zertifikate und "
            "alte Arbeitszeugnisse ohne Text-Ebene werden damit lesbar und "
            "fliessen in Profil-Extraktion und Dokumente-Analyse ein."
        ),
        "freigeschaltete_funktion": "Texterkennung beim Hochladen von Dokumenten (Auto-OCR)",
        "lizenz": "Apache-2.0",
        "groesse_mb": 55,
        "binary_name": "tesseract.exe" if sys.platform == "win32" else "tesseract",
        "windows_download": {
            "url": (
                "https://github.com/UB-Mannheim/tesseract/releases/download/"
                "v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
            ),
            # SHA-256 des Installers, entnommen dem winget-Manifest
            # UB-Mannheim.TesseractOCR 5.4.0.20240606 (microsoft/winget-pkgs):
            # Microsoft laedt dieselbe Adresse und vergleicht. Nicht selbst
            # heruntergeladen; die Probe auf frischem Windows (Beta-Exit 3)
            # bestaetigt sie.
            "sha256": "c885fff6998e0608ba4bb8ab51436e1c6775c2bafc2559a19b423e18678b60c9",
            "installer_art": "nsis",  # silent: /S /D=<zielordner>
        },
        # Bekannte Orte fuer extern installierte Instanzen (zusaetzlich
        # zu PATH-Lookup) — werden erkannt, aber nie veraendert.
        "bekannte_pfade_win": [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ],
        "hinweis_macos": "brew install tesseract tesseract-lang",
        "hinweis_linux": "sudo apt install tesseract-ocr tesseract-ocr-deu",
    },
    # B18 (#656, v1.8.0-beta.5): Sichtbarkeit + Nachinstallation des
    # Playwright-Browsers. Der Installer laedt Chromium zwar mit — schlaegt
    # das fehl (Netz, Platz) oder wurde es geloescht, scheiterten die
    # browser-gestuetzten Adapter bisher STILL. Install laeuft ueber
    # `python -m playwright install chromium` (art 'playwright'), nicht
    # ueber einen Binary-Download.
    "playwright-chromium": {
        "label": "Browser (Playwright/Chromium)",
        "beschreibung": (
            "Headless-Browser für Quellen, die ohne echten Browser nicht "
            "lesbar sind (SPA-Portale, LinkedIn-Suche). Wird vom Installer "
            "normalerweise mitgeliefert — hier sichtbar und reparierbar."
        ),
        "freigeschaltete_funktion": (
            "Quellen, die einen richtigen Browser brauchen (z. B. die LinkedIn-Suche)"
        ),
        "lizenz": "Apache-2.0 (Playwright) / BSD (Chromium)",
        "groesse_mb": 130,
        "art": "playwright",
        "binary_name": "",
        "hinweis_macos": "python -m playwright install chromium",
        "hinweis_linux": "python -m playwright install chromium",
    },
}

# Sprachdaten (tessdata_fast, je ~2 MB) — nachladbar, falls die
# Installation nur eng/osd mitbringt.
_TESSDATA_FAST_URL = (
    "https://github.com/tesseract-ocr/tessdata_fast/raw/main/{lang}.traineddata"
)


def components_dir() -> Path:
    """Basis-Ordner fuer PBP-installierte Komponenten.

    Liegt BEWUSST unter dem BewerbungsAssistent-Datenbaum, damit der
    Windows-Deinstaller (#739) die Komponenten symmetrisch mit entfernt.
    """
    from ..database import get_data_dir
    return Path(get_data_dir()).parent / "components"


def _tessdata_dir() -> Path:
    """Eigener tessdata-Ordner fuer nachgeladene Sprachen (TESSDATA_PREFIX)."""
    return components_dir() / "tessdata"


# ---------------------------------------------------------------------------
# Aufraeumen (#1130)
# ---------------------------------------------------------------------------

def _setup_datei(name: str) -> Path:
    """Wohin der Installer einer Komponente heruntergeladen wird."""
    return components_dir() / f"{name}-setup.exe"


def _teildatei(ziel: Path) -> Path:
    """Unter diesem Namen entsteht ein Download, bis er vollstaendig ist."""
    return ziel.with_name(ziel.name + ".part")


def _entfernen(pfad: Path, versuche: int = 3, pause: float = 0.3) -> bool:
    """Loescht eine Datei. True = sie ist weg (auch: war nie da).

    Wirft nie: wer aufraeumt, darf den eigentlichen Vorgang nicht mit einem
    zweiten Fehler ueberlagern. Unter Windows haelt ein Virenscanner eine
    frisch geschriebene .exe oft noch einen Augenblick fest -- darum ein
    paar Versuche, bevor "nicht loeschbar" gemeldet wird.
    """
    for versuch in range(versuche):
        try:
            pfad.unlink(missing_ok=True)
            return True
        except OSError as exc:
            if versuch + 1 < versuche:
                time.sleep(pause)
            else:
                logger.warning("Datei nicht entfernbar (%s): %s", pfad, exc)
    return False


def _installation_laeuft(db) -> bool:
    """Arbeitet gerade eine Komponenten-Installation?

    Der Hintergrund-Job ist die eine Antwort -- dieselbe Frage stellt
    start_install_job fuer den Doppelstart. Ein Job, der seit langem nichts
    mehr gemeldet hat, gilt als tot (hintergrund_alter, #1118); sonst
    blockierte ein abgestuerzter Lauf das Aufraeumen fuer immer. Im Zweifel
    gilt "laeuft": lieber ein Rest mehr als eine gestoerte Installation.
    """
    try:
        job = db.get_running_background_job("komponente_install")
        if not job:
            return False
        from .hintergrund_alter import veraltet
        return not veraltet(job)
    except Exception:
        return True


def setup_reste_finden() -> list:
    """Was ein fehlgeschlagener oder abgebrochener Lauf liegen gelassen hat: [(Pfad, Bytes)].

    Die eine Liste, nach der `setup_reste_entfernen` aufraeumt UND die Uebersicht
    "Speicher & Downloads" (#1131) zeigt, was dort aufgeraeumt wuerde. Liest nur.
    """
    kandidaten: list[Path] = []
    try:
        for name in COMPONENT_DEFS:
            setup = _setup_datei(name)
            kandidaten += [setup, _teildatei(setup)]
        # Sprachdaten landen im tessdata-Ordner der PBP-Installation oder,
        # wenn der nicht beschreibbar ist, im eigenen (ensure_language).
        sprachordner = {_tessdata_dir()} | {
            components_dir() / name / "tessdata" for name in COMPONENT_DEFS}
        for ordner in sorted(sprachordner):
            if ordner.is_dir():
                kandidaten += sorted(ordner.glob("*.traineddata.part"))
    except Exception as exc:  # noqa: BLE001 -- Aufraeumen darf nie werfen
        logger.warning("Komponenten-Ordner nicht lesbar: %s", exc)
    gefunden = []
    for pfad in kandidaten:
        try:
            if pfad.is_file():
                gefunden.append((pfad, pfad.stat().st_size))
        except OSError:
            continue
    return gefunden


def setup_reste_entfernen(db) -> dict:
    """Raeumt liegengebliebene Installationsdateien weg (#1130).

    Gemeint ist, was ein frueherer Lauf hinterlassen hat, der fehlschlug,
    abgebrochen wurde oder mitten im Download endete: die Setup-Datei jeder
    Komponente, ihre Teildatei und angefangene Sprachdaten (``*.part``).
    Nur diese Namen, nur im PBP-Ordner -- nie eine fremde Datei, nie eine
    fertige Installation oder fertige Sprache.

    Laeuft gerade eine Installation, passiert NICHTS: die Datei, die sie
    braucht, ist dann kein Rest. Wirft nie (Aufrufer sind die beiden
    Startwege und start_install_job).
    """
    if _installation_laeuft(db):
        return {"entfernt": 0, "bytes": 0, "uebersprungen": "installation_laeuft"}
    entfernt = 0
    bytes_frei = 0
    for pfad, groesse in setup_reste_finden():
        if _entfernen(pfad):
            entfernt += 1
            bytes_frei += groesse
    if entfernt:
        logger.info(
            "Komponenten: %d liegengebliebene Installationsdatei(en) entfernt "
            "(%.1f MB)", entfernt, bytes_frei / (1024 * 1024))
    return {"entfernt": entfernt, "bytes": bytes_frei}


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------

def _binary_version(binary: str) -> str:
    """Liest die Versionszeile eines Tesseract-Binaries (leer bei Fehler)."""
    try:
        proc = subprocess.run(
            [binary, "--version"], capture_output=True, text=True, errors="replace",
            timeout=15, **_SUBPROCESS_FLAGS,
        )
        first = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
        if first:
            m = re.search(r"tesseract\s+v?([\w.]+)", first[0], re.IGNORECASE)
            return m.group(1) if m else first[0][:40]
    except Exception:
        pass
    return ""


def playwright_basis() -> Path:
    """Der Ordner, in dem Playwright seine Browser ablegt (ms-playwright) -- auch fuer "Speicher & Downloads"."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches" / "ms-playwright"
    else:
        base = Path.home() / ".cache" / "ms-playwright"
    env_base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env_base and env_base != "0":
        base = Path(env_base)
    return base


def _playwright_chromium_dir() -> Optional[str]:
    """Ordner der installierten Chromium-Distribution (ms-playwright)."""
    base = playwright_basis()
    try:
        for entry in sorted(base.glob("chromium*")):
            if entry.is_dir():
                return str(entry)
    except Exception:
        pass
    return None


def find_component_binary(db, name: str) -> Optional[str]:
    """Findet das nutzbare Binary einer Komponente (oder None).

    Reihenfolge: (1) von PBP installierter Pfad (DB), (2) manuell
    gesetzter Pfad (DB), (3) PATH, (4) bekannte System-Pfade.
    """
    definition = COMPONENT_DEFS.get(name)
    if not definition:
        return None
    if definition.get("art") == "playwright":
        # "Binary" = installierte Chromium-Distribution + importierbares
        # playwright-Paket. Manuelle Pfade/PATH sind hier nicht sinnvoll.
        try:
            import playwright  # noqa: F401
        except ImportError:
            return None
        return _playwright_chromium_dir()
    state = None
    try:
        state = db.get_component_state(name)
    except Exception:
        pass
    if state and state.get("install_path"):
        candidate = Path(state["install_path"])
        if candidate.is_file():
            return str(candidate)
    which = shutil.which(name)
    if which:
        return which
    if sys.platform == "win32":
        for p in definition.get("bekannte_pfade_win", []):
            if Path(p).is_file():
                return p
    return None


def _playwright_version() -> str:
    try:
        from importlib.metadata import version
        return version("playwright")
    except Exception:
        return ""


def get_component_status(db, name: str) -> dict:
    """Live-Status einer Komponente: Registry-Def + DB-Zustand + Detection."""
    definition = COMPONENT_DEFS.get(name)
    if not definition:
        return {"name": name, "fehler": "unbekannte_komponente"}
    state = None
    try:
        state = db.get_component_state(name)
    except Exception:
        pass
    binary = find_component_binary(db, name)
    pbp_installiert = bool(
        state and state.get("status") == STATUS_INSTALLIERT
        and state.get("install_path") and Path(state["install_path"]).is_file()
    )
    wird_installiert = bool(state and state.get("status") == STATUS_WIRD_INSTALLIERT)
    result = {
        "name": name,
        "label": definition["label"],
        "beschreibung": definition["beschreibung"],
        "freigeschaltete_funktion": definition["freigeschaltete_funktion"],
        "lizenz": definition["lizenz"],
        "groesse_mb": definition["groesse_mb"],
        "verfuegbar": bool(binary),
        "quelle": (
            "pbp" if pbp_installiert
            else ("extern" if binary else "")
        ),
        "binary": binary or "",
        "version": (
            _playwright_version() if definition.get("art") == "playwright" and binary
            else (_binary_version(binary) if binary else "")
        ),
        "status": (
            STATUS_WIRD_INSTALLIERT if wird_installiert
            else (STATUS_INSTALLIERT if binary else STATUS_NICHT_INSTALLIERT)
        ),
        "letzter_fehler": (state or {}).get("last_error", "") or "",
    }
    if sys.platform == "darwin":
        result["install_hinweis"] = definition.get("hinweis_macos", "")
    elif sys.platform.startswith("linux"):
        result["install_hinweis"] = definition.get("hinweis_linux", "")
    return result


def get_components_overview(db) -> list[dict]:
    """Status aller registrierten Komponenten (fuer REST/MCP/UI)."""
    return [get_component_status(db, name) for name in COMPONENT_DEFS]


# ---------------------------------------------------------------------------
# Installation (synchroner Kern — Aufrufer startet ihn im Background-Thread)
# ---------------------------------------------------------------------------

def _download(url: str, target: Path, progress: Callable[[int, str], None],
              lo: int = 0, hi: int = 80) -> None:
    """Laedt url nach target, meldet Fortschritt zwischen lo und hi Prozent.

    Geschrieben wird unter ``<target>.part`` und erst bei vollstaendigem
    Empfang umbenannt (#1130): ein Name ohne ``.part`` steht damit immer fuer
    eine GANZE Datei. Bricht der Download ab -- Netz weg, Server kappt,
    Abbruch --, bleibt nichts liegen. http.client meldet eine zu kurz
    angekommene Antwort nicht als Fehler; darum die Laengenpruefung (sonst
    waere eine abgeschnittene Sprachdatei ohne Pruefsumme "fertig").
    """
    req = urllib.request.Request(url, headers={"User-Agent": "PBP-Komponenten/1.0"})
    teil = _teildatei(target)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length") or 0)
            done = 0
            target.parent.mkdir(parents=True, exist_ok=True)
            with open(teil, "wb") as fh:
                while True:
                    chunk = resp.read(1024 * 256)
                    if not chunk:
                        break
                    fh.write(chunk)
                    done += len(chunk)
                    if total:
                        pct = lo + int((hi - lo) * done / total)
                        progress(min(pct, hi), f"Download {done // (1024*1024)} MB")
        if total and done != total:
            raise RuntimeError(
                f"Download unvollständig ({done} von {total} Bytes).")
        os.replace(teil, target)
    except BaseException:
        _entfernen(teil)
        raise


def _pruefsumme_gueltig(wert) -> bool:
    """Eine SHA-256-Summe: genau 64 Hexzeichen. Alles andere (leer, zu kurz, kein Hex) gilt als „keine“."""
    return isinstance(wert, str) and re.fullmatch(r"[0-9a-fA-F]{64}", wert) is not None


def _sha256_ok(path: Path, expected: str) -> bool:
    if not _pruefsumme_gueltig(expected):
        # #1152: ohne Sollwert gibt es nichts zu pruefen, und was sich nicht pruefen laesst, gilt nicht.
        logger.error(
            "Komponenten-Download ohne gueltige Pruefsumme in der Registry "
            "wird nicht verwendet: %s", path.name,
        )
        return False
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower() == expected.lower()


def install_component(db, name: str,
                      progress: Callable[[int, str], None] = None) -> dict:
    """Installiert eine Komponente nach ``components/<name>`` (synchron).

    Gibt {"status": "installiert"|"fehler", ...} zurueck und pflegt die
    components-Tabelle. NIEMALS ohne vorherige User-Zustimmung aufrufen
    (die Zustimmung erzwingen die Aufrufer: MCP ``bestaetigt=True`` bzw.
    der explizite Button in der Settings-UI).
    """
    progress = progress or (lambda pct, msg: None)
    definition = COMPONENT_DEFS.get(name)
    if not definition:
        return {"status": "fehler", "fehler": f"Unbekannte Komponente '{name}'."}

    existing = find_component_binary(db, name)
    if existing:
        db.set_component_state(name, STATUS_INSTALLIERT, install_path=existing,
                               version=_binary_version(existing), last_error="")
        return {"status": "installiert", "binary": existing,
                "hinweis": "War bereits vorhanden — nichts heruntergeladen."}

    if definition.get("art") == "playwright":
        # B18 (#656): kein Binary-Download, sondern Playwrights eigener
        # Browser-Installer — plattformuebergreifend identisch.
        try:
            import playwright  # noqa: F401
        except ImportError:
            db.set_component_state(name, STATUS_FEHLER,
                                   last_error="playwright-Paket fehlt")
            return {"status": "fehler",
                    "fehler": ("Das playwright-Python-Paket fehlt (scraper-"
                               "Extra). PBP-Update drüberinstallieren, dann "
                               "erneut versuchen.")}
        db.set_component_state(name, STATUS_WIRD_INSTALLIERT, last_error="")
        try:
            progress(10, "Chromium wird geladen (playwright install)")
            proc = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True, text=True, errors="replace", timeout=900,
                **_SUBPROCESS_FLAGS,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    (proc.stderr or proc.stdout or "playwright install fehlgeschlagen")[:200])
            chromium = _playwright_chromium_dir()
            if not chromium:
                raise RuntimeError("Chromium-Ordner nach Install nicht gefunden.")
            db.set_component_state(name, STATUS_INSTALLIERT,
                                   install_path=chromium,
                                   version=_playwright_version(), last_error="")
            progress(100, "Fertig")
            return {"status": "installiert", "binary": chromium,
                    "version": _playwright_version()}
        except Exception as exc:
            msg = str(exc)[:300]
            logger.error("Playwright-Install fehlgeschlagen: %s", msg)
            db.set_component_state(name, STATUS_FEHLER, last_error=msg)
            return {"status": "fehler", "fehler": msg}

    if sys.platform != "win32":
        hint = definition.get(
            "hinweis_macos" if sys.platform == "darwin" else "hinweis_linux", "")
        db.set_component_state(name, STATUS_NICHT_INSTALLIERT,
                               last_error="auto-install nur unter Windows")
        return {
            "status": "fehler",
            "fehler": (
                "Automatische Installation gibt es aktuell nur unter Windows. "
                f"Bitte per Paketmanager installieren: {hint} — PBP erkennt "
                "die Installation danach automatisch."
            ),
        }

    dl = definition.get("windows_download") or {}
    if not dl.get("url"):
        return {"status": "fehler", "fehler": "Keine Download-Quelle hinterlegt."}
    if not _pruefsumme_gueltig(dl.get("sha256", "")):
        # #1152: nicht erst laden und dann ablehnen -- 50 MB umsonst, und die Datei laege auf der Platte.
        logger.error("Komponente %s: keine gueltige Pruefsumme in der Registry, Installation abgelehnt", name)
        return {"status": "fehler", "fehler": (
            "Für diese Komponente ist keine Prüfsumme hinterlegt. PBP lädt und startet nichts, "
            "das es nicht prüfen kann. Du kannst sie selbst installieren und den Pfad in den "
            "Einstellungen setzen.")}

    target_dir = components_dir() / name
    setup_path = _setup_datei(name)
    db.set_component_state(name, STATUS_WIRD_INSTALLIERT, last_error="")
    try:
        progress(1, "Download startet")
        _download(dl["url"], setup_path, progress, lo=1, hi=80)

        progress(82, "Prüfe Download")
        if not _sha256_ok(setup_path, dl.get("sha256", "")):
            # #1130: "verworfen" erst sagen, wenn die Datei wirklich weg ist.
            # Vorher stand die Zeile im Protokoll, die Datei blieb liegen.
            if _entfernen(setup_path):
                raise RuntimeError(
                    "Checksum-Prüfung fehlgeschlagen — Download verworfen.")
            raise RuntimeError(
                "Checksum-Prüfung fehlgeschlagen — der Download wird nicht "
                "verwendet. Die Datei ließ sich gerade nicht löschen; PBP "
                "entfernt sie beim nächsten Versuch oder Start.")

        progress(85, "Installiere (silent)")
        target_dir.mkdir(parents=True, exist_ok=True)
        if dl.get("installer_art") == "nsis":
            # NSIS: /S = silent, /D=<dir> MUSS der letzte Parameter sein und
            # vertraegt keine Anfuehrungszeichen. Pfade mit Leerzeichen
            # koennen scheitern — dann greift der manuelle Weg
            # (komponente_pfad_setzen / Settings).
            proc = subprocess.run(
                [str(setup_path), "/S", f"/D={target_dir}"],
                timeout=900, capture_output=True, text=True, errors="replace",
                **_SUBPROCESS_FLAGS,
            )
            if proc.returncode != 0:
                raise RuntimeError(
                    f"Installer-Exit-Code {proc.returncode}: "
                    f"{(proc.stderr or proc.stdout or '')[:200]}"
                )
        else:
            raise RuntimeError(f"Unbekannte installer_art: {dl.get('installer_art')}")

        progress(95, "Verifiziere")
        binary = target_dir / definition["binary_name"]
        if not binary.is_file():
            raise RuntimeError(
                f"Binary nach Installation nicht gefunden: {binary}. "
                "Möglicherweise enthält der Zielpfad Leerzeichen (NSIS-/D-"
                "Grenze) — bitte manuell installieren und den Pfad in den "
                "Einstellungen setzen."
            )
        version = _binary_version(str(binary))

        db.set_component_state(name, STATUS_INSTALLIERT,
                               install_path=str(binary), version=version,
                               last_error="")
        progress(100, "Fertig")
        return {"status": "installiert", "binary": str(binary), "version": version}
    except Exception as exc:
        msg = str(exc)[:300]
        logger.error("Komponenten-Install '%s' fehlgeschlagen: %s", name, msg)
        db.set_component_state(name, STATUS_FEHLER, last_error=msg)
        return {"status": "fehler", "fehler": msg}
    finally:
        # #1130: egal wie der Lauf endet -- Erfolg, Pruefsumme, Installer-
        # Fehler, Abbruch -- die Setup-Datei (rund 55 MB) bleibt nicht liegen.
        _entfernen(setup_path)


def start_install_job(db, name: str) -> dict:
    """Startet install_component als Background-Job (gemeinsamer Kern fuer
    REST-Endpoint und MCP-Tool — beide setzen vorher die User-Zustimmung
    voraus)."""
    if name not in COMPONENT_DEFS:
        return {"status": "fehler", "fehler": f"Unbekannte Komponente '{name}'."}
    running = None
    try:
        running = db.get_running_background_job("komponente_install")
    except Exception:
        pass
    if running:
        return {"status": "laeuft_bereits", "job_id": running.get("id"),
                "hinweis": "Es läuft bereits eine Komponenten-Installation."}
    # #1130: Reste frueherer Laeufe weg, BEVOR ein neuer Versuch beginnt.
    # Eben wurde geprueft, dass keine Installation laeuft.
    setup_reste_entfernen(db)
    job_id = db.create_background_job("komponente_install", {"name": name})

    def _run():
        def _progress(pct: int, msg: str):
            try:
                db.update_background_job(job_id, "running", pct, msg)
            except Exception:
                pass
        try:
            result = install_component(db, name, progress=_progress)
            if result.get("status") == "installiert" and name == "tesseract":
                # deu-Sprachpaket best-effort nachziehen (~2 MB)
                try:
                    lang = ensure_language(db, "deu")
                    result["sprachpaket_deu"] = lang.get("status")
                except Exception:
                    pass
            final = "fertig" if result.get("status") == "installiert" else "fehler"
            db.update_background_job(
                job_id, final, 100,
                result.get("fehler", "") or "Installation abgeschlossen",
                result=result,
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Komponenten-Install-Job crashte: %s", exc, exc_info=True)
            try:
                db.update_background_job(job_id, "fehler", 100, str(exc)[:200])
            except Exception:
                pass

    import threading
    # A22 (#759): benannt fuer den conftest-Thread-Drain der Test-Suite
    threading.Thread(target=_run, daemon=True,
                     name=f"pbp-komponente-install-{name}").start()
    return {"status": "gestartet", "job_id": job_id}


def set_manual_path(db, name: str, path: str) -> dict:
    """Traegt ein extern installiertes Binary ein (Offline-/Fallback-Weg)."""
    definition = COMPONENT_DEFS.get(name)
    if not definition:
        return {"status": "fehler", "fehler": f"Unbekannte Komponente '{name}'."}
    candidate = Path(path)
    if candidate.is_dir():
        candidate = candidate / definition["binary_name"]
    if not candidate.is_file():
        return {"status": "fehler",
                "fehler": f"Binary nicht gefunden: {candidate}"}
    version = _binary_version(str(candidate))
    if not version:
        return {"status": "fehler",
                "fehler": "Datei antwortet nicht auf --version — falsches Binary?"}
    db.set_component_state(name, STATUS_INSTALLIERT,
                           install_path=str(candidate), version=version,
                           last_error="")
    return {"status": "installiert", "binary": str(candidate), "version": version}


def uninstall_component(db, name: str) -> dict:
    """Entfernt eine VON PBP installierte Komponente.

    Externe Installationen (PATH/Program Files) werden nie angefasst —
    dort wird nur die PBP-Registrierung geloescht.
    """
    definition = COMPONENT_DEFS.get(name)
    if not definition:
        return {"status": "fehler", "fehler": f"Unbekannte Komponente '{name}'."}
    state = db.get_component_state(name)
    removed = False
    target_dir = components_dir() / name
    if target_dir.exists():
        try:
            shutil.rmtree(target_dir)
            removed = True
        except Exception as exc:
            return {"status": "fehler",
                    "fehler": f"Ordner nicht entfernbar: {str(exc)[:150]}"}
    db.set_component_state(name, STATUS_NICHT_INSTALLIERT,
                           install_path="", version="", last_error="")
    extern = find_component_binary(db, name)
    return {
        "status": "entfernt",
        "pbp_installation_geloescht": removed,
        "hinweis": (
            f"Extern installierte Instanz bleibt unangetastet ({extern})."
            if extern else ""
        ),
        "war_registriert": bool(state),
    }


# ---------------------------------------------------------------------------
# Sprachdaten (tessdata) fuer Tesseract
# ---------------------------------------------------------------------------

def available_languages(db) -> list[str]:
    """Sprachen der aktiven Tesseract-Installation (inkl. nachgeladener)."""
    binary = find_component_binary(db, "tesseract")
    if not binary:
        return []
    try:
        env = _ocr_env()
        proc = subprocess.run(
            [binary, "--list-langs"], capture_output=True, text=True, errors="replace",
            timeout=20, env=env, **_SUBPROCESS_FLAGS,
        )
        langs = []
        for line in (proc.stdout or "").splitlines()[1:]:
            line = line.strip()
            if line and re.fullmatch(r"[a-z_]{2,12}", line):
                langs.append(line)
        return sorted(set(langs))
    except Exception:
        return []


def _install_tessdata_dir(db) -> Optional[Path]:
    """tessdata-Ordner NEBEN dem aktiven Binary, falls beschreibbar."""
    binary = find_component_binary(db, "tesseract")
    if not binary:
        return None
    td = Path(binary).parent / "tessdata"
    if td.is_dir() and os.access(td, os.W_OK):
        return td
    return None


def ensure_language(db, lang: str = "deu",
                    progress: Callable[[int, str], None] = None) -> dict:
    """Laedt ein tessdata_fast-Sprachpaket nach (~2 MB).

    Bevorzugt in den tessdata-Ordner der Installation (Standardfall bei
    PBP-Install unter AppData). Ist der schreibgeschuetzt (Program Files,
    apt), landet die Sprache im PBP-tessdata-Ordner — der wird dann per
    TESSDATA_PREFIX genutzt und ERSETZT Tesseracts Suchpfad komplett,
    darum werden eng+osd dort automatisch mit-nachgeladen (selbsttragend).
    """
    progress = progress or (lambda pct, msg: None)
    if not re.fullmatch(r"[a-z_]{2,12}", lang):
        return {"status": "fehler", "fehler": f"Ungültiger Sprachcode: {lang!r}"}
    if lang in available_languages(db):
        return {"status": "vorhanden", "sprache": lang}
    install_td = _install_tessdata_dir(db)
    try:
        if install_td is not None:
            target = install_td / f"{lang}.traineddata"
            _download(_TESSDATA_FAST_URL.format(lang=lang), target, progress, 0, 100)
            return {"status": "nachgeladen", "sprache": lang, "pfad": str(target)}
        # Fallback: eigener, selbsttragender TESSDATA_PREFIX-Ordner
        needed = [lang] + [
            base for base in ("eng", "osd")
            if not (_tessdata_dir() / f"{base}.traineddata").is_file()
        ]
        for i, one in enumerate(needed):
            target = _tessdata_dir() / f"{one}.traineddata"
            lo = int(100 * i / len(needed))
            hi = int(100 * (i + 1) / len(needed))
            _download(_TESSDATA_FAST_URL.format(lang=one), target, progress, lo, hi)
        return {"status": "nachgeladen", "sprache": lang,
                "pfad": str(_tessdata_dir() / f"{lang}.traineddata"),
                "hinweis": "eng/osd in den PBP-tessdata-Ordner mitgeladen "
                           "(TESSDATA_PREFIX ersetzt den Suchpfad komplett)."}
    except Exception as exc:
        return {"status": "fehler", "fehler": str(exc)[:200]}


def _ansi_sicher(pfad: str) -> str:
    """Pfad fuer Programme, die Pfade in der ANSI-Zeichentabelle lesen (Tesseract: TESSDATA_PREFIX und Argumente).

    Der Pfad liegt im Benutzerordner. Steckt darin ein Zeichen ausserhalb der Tabelle (Benutzername mit ł, ş, ř ...), meldet das
    Programm "Error opening data file". Dann hilft der Kurzpfad (8.3) -- wenn das Laufwerk Kurznamen fuehrt; sonst bleibt der Pfad,
    wie er ist, und der Fehler bleibt der alte.
    """
    if sys.platform != "win32":
        return pfad
    try:
        pfad.encode("mbcs")
        return pfad
    except UnicodeEncodeError:
        pass
    try:
        import ctypes
        puffer = ctypes.create_unicode_buffer(1024)
        laenge = ctypes.windll.kernel32.GetShortPathNameW(pfad, puffer, 1024)
        if 0 < laenge < 1024:
            puffer.value.encode("mbcs")
            return puffer.value
    except Exception:  # kein Kurzname, Aufruf nicht moeglich oder der Kurzpfad ist selbst nicht lesbar
        pass
    return pfad


def _ocr_env() -> dict:
    """Prozess-Env fuer Tesseract-Aufrufe.

    Nachgeladene Sprachen liegen im PBP-tessdata-Ordner; TESSDATA_PREFIX
    wird nur gesetzt, wenn dort tatsaechlich Dateien liegen — sonst nutzt
    Tesseract sein eigenes tessdata neben dem Binary.
    """
    env = dict(os.environ)
    td = _tessdata_dir()
    if td.is_dir() and any(td.glob("*.traineddata")):
        env["TESSDATA_PREFIX"] = _ansi_sicher(str(td))
    return env
