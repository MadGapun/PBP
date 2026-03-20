"""Zentrales Logging für alle PBP-Komponenten.

Schreibt in eine rotierende Log-Datei (max 1MB, 1 Backup).
Log-Verzeichnis: %BA_DATA_DIR%/logs/pbp.log
Log-Level konfigurierbar via BA_LOG_LEVEL Umgebungsvariable.

Nutzung:
    from bewerbungs_assistent.logging_config import setup_logging
    setup_logging()  # Einmal beim Start aufrufen
"""
import logging
import os
import sys
from logging.handlers import RotatingFileHandler

_initialized = False


class SafeRotatingFileHandler(RotatingFileHandler):
    """RotatingFileHandler that tolerates transient file locks on Windows."""

    def doRollover(self):
        try:
            super().doRollover()
        except PermissionError:
            # Another process may temporarily hold the log file.
            # Skip this rollover attempt; keep logging to current file.
            if self.stream is None:
                try:
                    self.stream = self._open()
                except Exception:
                    pass
        except OSError as exc:
            if getattr(exc, "winerror", None) == 32:
                if self.stream is None:
                    try:
                        self.stream = self._open()
                    except Exception:
                        pass
                return
            raise


def setup_logging(level=None, console=True):
    """Richte zentrales Logging ein.

    Args:
        level: Log-Level (default: aus BA_LOG_LEVEL env oder INFO)
        console: Auch auf stderr ausgeben (default: True, aber
                 bei MCP-Server auf False setzen da stdout/stderr
                 für das MCP-Protokoll reserviert sind)

    Returns:
        Der konfigurierte Root-Logger für bewerbungs_assistent
    """
    global _initialized

    logger = logging.getLogger("bewerbungs_assistent")

    # Nur einmal initialisieren
    if _initialized:
        return logger

    # Log-Level bestimmen
    log_level_str = level or os.environ.get("BA_LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_str.upper(), logging.INFO)
    logger.setLevel(log_level)
    # Logging errors should not spam stderr in production-like runs.
    logging.raiseExceptions = False

    # Format
    fmt = logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Datenverzeichnis ermitteln
    data_dir = os.environ.get("BA_DATA_DIR")
    if not data_dir:
        local_app = os.environ.get("LOCALAPPDATA", "")
        if local_app:
            data_dir = os.path.join(local_app, "BewerbungsAssistent")
        else:
            data_dir = os.path.join(os.path.expanduser("~"), ".bewerbungs_assistent")
    os.environ["BA_DATA_DIR"] = data_dir

    # Log-Verzeichnis erstellen
    log_dir = os.path.join(data_dir, "logs")
    try:
        os.makedirs(log_dir, exist_ok=True)

        # Rotierende Log-Datei (max 1MB, 1 Backup = max 2MB gesamt)
        log_file = os.path.join(log_dir, "pbp.log")
        fh = SafeRotatingFileHandler(
            log_file,
            maxBytes=1_000_000,
            backupCount=1,
            encoding="utf-8",
        )
        fh.setFormatter(fmt)
        fh.setLevel(log_level)
        logger.addHandler(fh)
    except Exception:
        # Kann nicht in Datei loggen (z.B. Rechte-Problem)
        # Dann halt nur Console
        pass

    # Console-Handler (stderr, nicht stdout!)
    if console:
        sh = logging.StreamHandler(sys.stderr)
        sh.setFormatter(fmt)
        sh.setLevel(log_level)
        logger.addHandler(sh)

    _initialized = True
    return logger


def get_log_path():
    """Gibt den Pfad zur Log-Datei zurück."""
    data_dir = os.environ.get("BA_DATA_DIR", "")
    if data_dir:
        return os.path.join(data_dir, "logs", "pbp.log")
    return None
