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
# sha256 leer = Pruefung wird uebersprungen (mit Warnung im Log). Die
# Checksum der UB-Mannheim-Releases aendert sich pro Version; sie wird beim
# Versions-Bump hier nachgezogen. Der Beta-Exit (Kriterium 3) verifiziert
# den kompletten Install-Pfad auf einer frischen Maschine.
COMPONENT_DEFS: dict[str, dict] = {
    "tesseract": {
        "label": "Tesseract OCR",
        "beschreibung": (
            "Texterkennung fuer gescannte PDFs — Zeugnisse, Zertifikate und "
            "alte Arbeitszeugnisse ohne Text-Ebene werden damit lesbar und "
            "fliessen in Profil-Extraktion und Dokumente-Analyse ein."
        ),
        "freigeschaltete_funktion": "Auto-OCR beim Dokument-Import (E19)",
        "lizenz": "Apache-2.0",
        "groesse_mb": 55,
        "binary_name": "tesseract.exe" if sys.platform == "win32" else "tesseract",
        "windows_download": {
            "url": (
                "https://github.com/UB-Mannheim/tesseract/releases/download/"
                "v5.4.0.20240606/tesseract-ocr-w64-setup-5.4.0.20240606.exe"
            ),
            "sha256": "",
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
            "Headless-Browser fuer Quellen, die ohne echten Browser nicht "
            "lesbar sind (SPA-Portale, LinkedIn-Suche). Wird vom Installer "
            "normalerweise mitgeliefert — hier sichtbar und reparierbar."
        ),
        "freigeschaltete_funktion": (
            "Browser-gestuetzte Quellen-Adapter + linkedin_browser_search (B18)"
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
# Detection
# ---------------------------------------------------------------------------

def _binary_version(binary: str) -> str:
    """Liest die Versionszeile eines Tesseract-Binaries (leer bei Fehler)."""
    try:
        proc = subprocess.run(
            [binary, "--version"], capture_output=True, text=True,
            timeout=15, **_SUBPROCESS_FLAGS,
        )
        first = ((proc.stdout or "") + (proc.stderr or "")).strip().splitlines()
        if first:
            m = re.search(r"tesseract\s+v?([\w.]+)", first[0], re.IGNORECASE)
            return m.group(1) if m else first[0][:40]
    except Exception:
        pass
    return ""


def _playwright_chromium_dir() -> Optional[str]:
    """Ordner der installierten Chromium-Distribution (ms-playwright)."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", "")) / "ms-playwright"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Caches" / "ms-playwright"
    else:
        base = Path.home() / ".cache" / "ms-playwright"
    env_base = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if env_base and env_base != "0":
        base = Path(env_base)
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
    """Laedt url nach target, meldet Fortschritt zwischen lo und hi Prozent."""
    req = urllib.request.Request(url, headers={"User-Agent": "PBP-Komponenten/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "wb") as fh:
            while True:
                chunk = resp.read(1024 * 256)
                if not chunk:
                    break
                fh.write(chunk)
                done += len(chunk)
                if total:
                    pct = lo + int((hi - lo) * done / total)
                    progress(min(pct, hi), f"Download {done // (1024*1024)} MB")


def _sha256_ok(path: Path, expected: str) -> bool:
    if not expected:
        logger.warning(
            "Komponenten-Download ohne Checksum-Pruefung (keine sha256 in "
            "der Registry hinterlegt): %s", path.name,
        )
        return True
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
                               "Extra). PBP-Update drueberinstallieren, dann "
                               "erneut versuchen.")}
        db.set_component_state(name, STATUS_WIRD_INSTALLIERT, last_error="")
        try:
            progress(10, "Chromium wird geladen (playwright install)")
            proc = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True, text=True, timeout=900,
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

    target_dir = components_dir() / name
    db.set_component_state(name, STATUS_WIRD_INSTALLIERT, last_error="")
    try:
        progress(1, "Download startet")
        setup_path = components_dir() / f"{name}-setup.exe"
        _download(dl["url"], setup_path, progress, lo=1, hi=80)

        progress(82, "Pruefe Download")
        if not _sha256_ok(setup_path, dl.get("sha256", "")):
            raise RuntimeError("Checksum-Pruefung fehlgeschlagen — Download verworfen.")

        progress(85, "Installiere (silent)")
        target_dir.mkdir(parents=True, exist_ok=True)
        if dl.get("installer_art") == "nsis":
            # NSIS: /S = silent, /D=<dir> MUSS der letzte Parameter sein und
            # vertraegt keine Anfuehrungszeichen. Pfade mit Leerzeichen
            # koennen scheitern — dann greift der manuelle Weg
            # (komponente_pfad_setzen / Settings).
            proc = subprocess.run(
                [str(setup_path), "/S", f"/D={target_dir}"],
                timeout=900, capture_output=True, text=True,
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
                "Moeglicherweise enthaelt der Zielpfad Leerzeichen (NSIS-/D-"
                "Grenze) — bitte manuell installieren und den Pfad in den "
                "Einstellungen setzen."
            )
        version = _binary_version(str(binary))

        try:
            setup_path.unlink()
        except Exception:
            pass

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
                "hinweis": "Es laeuft bereits eine Komponenten-Installation."}
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
            [binary, "--list-langs"], capture_output=True, text=True,
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
        return {"status": "fehler", "fehler": f"Ungueltiger Sprachcode: {lang!r}"}
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


def _ocr_env() -> dict:
    """Prozess-Env fuer Tesseract-Aufrufe.

    Nachgeladene Sprachen liegen im PBP-tessdata-Ordner; TESSDATA_PREFIX
    wird nur gesetzt, wenn dort tatsaechlich Dateien liegen — sonst nutzt
    Tesseract sein eigenes tessdata neben dem Binary.
    """
    env = dict(os.environ)
    td = _tessdata_dir()
    if td.is_dir() and any(td.glob("*.traineddata")):
        env["TESSDATA_PREFIX"] = str(td)
    return env
