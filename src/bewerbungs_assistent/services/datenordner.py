"""Was PBP im Datenordner speichert — und wie die DSGVO-Löschung ihn leert (#1097).

Bis v1.7.139 entfernte "Alles unwiderruflich löschen (DSGVO)" nur
`pbp.db` und die Ordner `dokumente/` und `export/`. Im Datenordner
blieben danach vollstaendige Kopien der Datenbank (`backups/` vor jeder
Migration, `backup/` aus dem Dashboard), die Original-Mails, die
WAL-Datei, die Protokolle mit Firmennamen, die Freitexte aus
`pbp_grenze_melden` und die Browser-Sitzungen von LinkedIn und XING.
Die Oberflaeche versprach "nicht rückgängig zu machen" — die Daten lagen
mehrfach daneben.

Zwei Regeln, die dieses Modul traegt:

(1) **Die Loeschung leert den GANZEN Datenordner**, nicht die Eintraege
    einer Liste. Eine Liste waere beim naechsten neuen Unterordner
    unvollstaendig; genau so ist der Fehler entstanden. `INHALT` dient
    der Auskunft (Gefahrenzone, Datenuebersicht, Selbstauskunft) und
    wird von einem Guard gegen den Code gehalten — die Loeschung haengt
    nicht an ihr.

(2) **Eine teilweise Loeschung ist kein Erfolg** (#997). Unter Windows
    haelt ein zweiter Prozess (der MCP-Server in Claude Desktop) die
    Datenbank und das Protokoll offen. Was sich nicht loeschen laesst,
    wird je Datei benannt, und eine Vormerkung loescht den Rest beim
    naechsten Start, BEVOR die Datenbank geoeffnet wird.

Die Loeschung laeuft nicht, waehrend Hintergrundarbeit die Datenbank
benutzt (Jobsuche, Automatik, ein laufendes Werkzeug): eine Verbindung
unter einem laufenden Thread zu schliessen war die Absturzursache aus
v1.7.11 (Exit 139). Dann wird abgelehnt und genannt, was laeuft.
"""
from __future__ import annotations

import logging
import shutil
import threading
from pathlib import Path

logger = logging.getLogger("bewerbungs_assistent.datenordner")

# Vormerkung "beim naechsten Start loeschen". Sie liegt IM Datenordner
# und verschwindet mit ihm.
VORMERKUNG = "dsgvo_loeschung_vorgemerkt"

# Alles, was der Code unter dem Datenordner anlegt. Aufgezaehlt ist die
# ZUORDNUNG (was ist das, traegt es persoenliche Daten), nicht die
# Loeschung. Ein Guard (tests/test_1097_datenordner.py) haelt jeden Namen,
# den der Code unter get_data_dir() baut, gegen diese Liste.
INHALT = (
    {"name": "pbp.db", "art": "datei",
     "was": "Datenbank: Profil, Bewerbungen, Stellen, Kontakte, Notizen",
     "persoenlich": True},
    {"name": "pbp.db-wal", "art": "datei",
     "was": "Noch nicht zurückgeschriebene Änderungen der Datenbank",
     "persoenlich": True},
    {"name": "pbp.db-shm", "art": "datei",
     "was": "Hilfsdatei der Datenbank", "persoenlich": False},
    {"name": "pbp.db-journal", "art": "datei",
     "was": "Hilfsdatei der Datenbank", "persoenlich": True},
    {"name": "backups", "art": "ordner",
     "was": "Sicherungskopien der Datenbank vor jedem Update",
     "persoenlich": True},
    {"name": "backup", "art": "ordner",
     "was": "Sicherungskopien der Datenbank aus dem Dashboard",
     "persoenlich": True},
    {"name": "dokumente", "art": "ordner",
     "was": "Hochgeladene und importierte Dokumente", "persoenlich": True},
    {"name": "emails", "art": "ordner",
     "was": "Original-Mails mit Absendern, Inhalten und Anhängen",
     "persoenlich": True},
    {"name": "export", "art": "ordner",
     "was": "Erzeugte Lebensläufe, Anschreiben und Berichte",
     "persoenlich": True},
    {"name": "logs", "art": "ordner",
     "was": "Protokolle; sie nennen unter anderem Firmen",
     "persoenlich": True},
    {"name": "limitations.log", "art": "datei",
     "was": "Freitexte aus gemeldeten Grenzen von PBP", "persoenlich": True},
    {"name": "linkedin_session", "art": "ordner",
     "was": "Browser-Sitzung für LinkedIn (Anmeldung, Cookies)",
     "persoenlich": True},
    {"name": "xing_session", "art": "ordner",
     "was": "Browser-Sitzung für XING (Anmeldung, Cookies)",
     "persoenlich": True},
    {"name": "browser_selectors.json", "art": "datei",
     "was": "Einstellungen für den Browser-Zugriff", "persoenlich": False},
    {"name": "werkzeuge", "art": "ordner",
     "was": "Hilfsskripte (z. B. zum Beenden von Ollama)",
     "persoenlich": False},
    {"name": "mcp_heartbeat.json", "art": "datei",
     "was": "Lebenszeichen der Verbindung zu Claude", "persoenlich": False},
    {"name": "data", "art": "ordner",
     "was": "Altbestand aus früheren Versionen", "persoenlich": True},
    {"name": VORMERKUNG, "art": "datei",
     "was": "Vormerkung einer DSGVO-Löschung", "persoenlich": False},
)

NAMEN = frozenset(e["name"] for e in INHALT)

AUSSERHALB_SATZ = (
    "Nicht gelöscht wird, was außerhalb des Datenordners liegt: selbst "
    "gewählte Ablage- und Vorlagenordner, Originaldateien, aus denen "
    "Dokumente importiert wurden, und was du mit Claude bearbeitet hast — "
    "das liegt bei Anthropic und wird dort gelöscht, nicht in PBP.")


def _datenordner() -> Path:
    from ..database import get_data_dir
    return get_data_dir()


def _groesse(p: Path) -> int:
    try:
        if p.is_file():
            return p.stat().st_size
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except OSError:
        return 0


def uebersicht(datenordner: Path | None = None) -> list:
    """Was davon gerade vorhanden ist, mit Groesse. Dazu jeder Eintrag im
    Datenordner, den `INHALT` nicht kennt — er wird bei der Loeschung
    ebenfalls entfernt und soll deshalb auch hier stehen."""
    basis = Path(datenordner) if datenordner else _datenordner()
    out = []
    for e in INHALT:
        p = basis / e["name"]
        if p.exists():
            out.append({**e, "pfad": str(p), "bytes": _groesse(p)})
    try:
        fremd = sorted(c for c in basis.iterdir() if c.name not in NAMEN)
    except OSError:
        fremd = []
    for p in fremd:
        out.append({"name": p.name, "art": "ordner" if p.is_dir() else "datei",
                    "was": "Sonstige Datei im Datenordner",
                    "persoenlich": True, "pfad": str(p), "bytes": _groesse(p)})
    return out


def ausserhalb(db) -> list:
    """Orte AUSSERHALB des Datenordners, die PBP kennt und nicht loescht."""
    orte = []
    try:
        from . import ablage
        for art, schluessel in (("Ablageordner", ablage.AUSGABE_SCHLUESSEL),
                                ("Vorlagenordner", ablage.VORLAGEN_SCHLUESSEL)):
            wert = (db.get_setting(schluessel, "") or "").strip() if db else ""
            if wert:
                orte.append({"was": art, "pfad": wert})
    except Exception as exc:  # pragma: no cover
        logger.debug("Ablageordner nicht lesbar: %s", exc)
    return orte


# -- Hintergrundarbeit ------------------------------------------------

# Dauerlaeufer (Taktgeber, Lebenszeichen, Warmup) arbeiten kurz und
# zyklisch; Arbeits-Threads halten eine Aufgabe, die mitten in einer
# Schreibfolge stehen kann.
_ARBEIT_PRAEFIXE = ("pbp-", "automatik-lernen", "automatik-jobsuche")


def laufende_arbeit() -> list:
    """Namen der Hintergrundarbeiten, die gerade die Datenbank benutzen
    koennen. Leer heisst: jetzt darf geloescht werden."""
    laufend = [t.name for t in threading.enumerate()
               if t is not threading.current_thread() and t.is_alive()
               and t.name.startswith(_ARBEIT_PRAEFIXE)]
    try:
        from .tool_budget import warte_auf_leerlauf
        if not warte_auf_leerlauf(timeout=0.5):
            laufend.append("ein laufendes Claude-Werkzeug")
    except Exception:  # pragma: no cover
        pass
    return laufend


def arbeit_klartext(namen: list) -> str:
    teile = []
    for n in namen:
        if n.startswith("pbp-jobsuche") or n == "automatik-jobsuche":
            teile.append("eine Jobsuche")
        elif n.startswith("automatik-lernen"):
            teile.append("das automatische Lernen")
        elif n.startswith("pbp-komponente"):
            teile.append("eine Komponenten-Installation")
        elif n.startswith("pbp-watchdog"):
            continue
        else:
            teile.append(n)
    return ", ".join(dict.fromkeys(teile)) or "Hintergrundarbeit"


# -- Loeschen ---------------------------------------------------------

def _protokolle_schliessen(basis: Path) -> None:
    """Datei-Handler, die in den Datenordner schreiben, schliessen und
    abhaengen — sonst ist unter Windows `logs/pbp.log` gesperrt, und das
    Protokoll schreibt nach der Loeschung sofort weiter."""
    wurzel = logging.getLogger()
    for logger_ in [wurzel] + [logging.getLogger(n) for n in
                               list(logging.root.manager.loggerDict)]:
        for h in list(getattr(logger_, "handlers", [])):
            ziel = getattr(h, "baseFilename", "")
            if ziel and str(Path(ziel).resolve()).startswith(str(basis.resolve())):
                try:
                    h.close()
                finally:
                    logger_.removeHandler(h)


def alles_loeschen(datenordner: Path | None = None) -> dict:
    """Leert den Datenordner vollstaendig. Wirft nicht.

    Rueckgabe: {"geloescht": [namen], "fehler": [{"pfad", "grund"}]}.
    Bleibt etwas zurueck, steht eine Vormerkung im Ordner, die den Rest
    beim naechsten Start entfernt."""
    basis = Path(datenordner) if datenordner else _datenordner()
    geloescht, fehler = [], []
    if not basis.exists():
        return {"geloescht": [], "fehler": []}
    _protokolle_schliessen(basis)
    try:
        eintraege = sorted(basis.iterdir())
    except OSError as exc:
        return {"geloescht": [], "fehler": [{"pfad": str(basis), "grund": str(exc)}]}
    for p in eintraege:
        if p.name == VORMERKUNG:
            continue
        try:
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p)
            else:
                p.unlink()
            geloescht.append(p.name)
        except OSError as exc:
            fehler.append({"pfad": str(p), "grund": str(exc)})
    marke = basis / VORMERKUNG
    if fehler:
        try:
            marke.write_text("\n".join(f["pfad"] for f in fehler), encoding="utf-8")
        except OSError as exc:  # pragma: no cover
            logger.warning("Vormerkung nicht schreibbar: %s", exc)
    else:
        marke.unlink(missing_ok=True)
    return {"geloescht": geloescht, "fehler": fehler}


def vorgemerkte_loeschung_ausfuehren(datenordner: Path) -> dict | None:
    """Beim Start, BEVOR die Datenbank geoeffnet wird: liegt eine
    Vormerkung, wird der Rest geloescht. Ohne Vormerkung None."""
    basis = Path(datenordner)
    if not (basis / VORMERKUNG).exists():
        return None
    erg = alles_loeschen(basis)
    if erg["fehler"]:
        logger.warning("Vorgemerkte DSGVO-Löschung unvollständig: %s",
                       [f["pfad"] for f in erg["fehler"]])
    else:
        logger.info("Vorgemerkte DSGVO-Löschung ausgeführt (%d Einträge).",
                    len(erg["geloescht"]))
    return erg
