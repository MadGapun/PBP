"""Welche Datei gehoert PBP — und darf PBP sie loeschen (#1099)?

Ein Dokument-Eintrag in PBP zeigt ueber `filepath` auf eine Datei. Bis
v1.7.139 entfernte `delete_document` jede Datei, auf die ein Eintrag
zeigte, ohne zu fragen, wem sie gehoert. Drei Wege liessen einen Eintrag
auf eine FREMDE Datei zeigen:

1. Der Ordner-Import kopierte nach `dokumente/<Dateiname>` und nahm, wenn
   dort schon eine gleichnamige Datei lag, einfach diese — zwei Eintraege,
   eine Datei. Scheiterte das Kopieren, zeigte der Eintrag auf das
   ORIGINAL im Ordner des Nutzers.
2. Der Profil-Import uebernahm die Pfade aus der Exportdatei, also die
   Dateien eines anderen Profils.
3. Die Pfad-Reparatur (#503) suchte eine fehlende Datei nur ueber den
   Dateinamen und bog einen Eintrag so auf die Datei eines anderen
   Dokuments um.

Die Folge: Loeschen eines Eintrags konnte die Datei eines anderen
Dokuments entfernen — oder die Originaldatei des Nutzers ausserhalb von
PBP.

Dieses Modul ist der EINE Ort fuer die Frage "darf PBP diese Datei
loeschen?". Die Antwort ist nur dann ja, wenn

* die Datei im Datenordner von PBP liegt — dem ganzen Datenordner, nicht
  nur `dokumente/` (Mail-Dokumente liegen unter `emails/`), und
* kein anderer Eintrag, auch nicht in einem anderen Profil oder in einer
  anderen Tabelle mit `filepath`, auf dieselbe Datei zeigt.

Sonst bleibt die Datei liegen, und der Grund wird genannt. Eine Datei zu
viel auf der Platte ist ein Aufraeumproblem; eine geloeschte Datei des
Nutzers ist ein Verlust, der sich nicht zurueckholen laesst.
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

logger = logging.getLogger("bewerbungs_assistent.dateiablage")

# Gruende, warum eine Datei liegen bleibt — in Alltagssprache, sie stehen
# in Werkzeugantworten und im Bericht.
AUSSERHALB = "liegt außerhalb des PBP-Datenordners (eine Datei des Nutzers)"
GETEILT = "wird noch von einem anderen Eintrag benutzt"


def _datenordner() -> Path:
    from ..database import get_data_dir
    return get_data_dir()


def _normal(pfad) -> str:
    """Vergleichsform eines Pfads: aufgeloest, und unter Windows ohne
    Unterschied in der Gross-/Kleinschreibung."""
    try:
        p = Path(str(pfad)).expanduser().resolve()
    except (OSError, RuntimeError, ValueError):
        p = Path(str(pfad))
    return os.path.normcase(str(p))


def ist_im_datenordner(pfad) -> bool:
    """Liegt `pfad` im Datenordner von PBP (auch in Unterordnern)?"""
    if not pfad:
        return False
    basis = _normal(_datenordner())
    ziel = _normal(pfad)
    return ziel == basis or ziel.startswith(basis.rstrip(os.sep) + os.sep)


def _tabellen_mit_filepath(db) -> list:
    con = db.connect()
    namen = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'")]
    out = []
    for t in namen:
        try:
            spalten = [r[1] for r in con.execute(f"PRAGMA table_info({t})")]
        except Exception:  # pragma: no cover
            continue
        if "filepath" in spalten and "id" in spalten:
            out.append(t)
    return out


def verweise(db, pfad) -> list:
    """Alle Eintraege (Tabelle, id), die auf dieselbe Datei zeigen —
    ueber alle Profile und alle Tabellen mit einer Spalte `filepath`.

    Verglichen wird die aufgeloeste Pfadform, damit `a/../b.pdf` und
    `b.pdf` als dieselbe Datei gelten."""
    if not pfad:
        return []
    ziel = _normal(pfad)
    name = Path(str(pfad).replace("\\", "/")).name
    con = db.connect()
    treffer = []
    for t in _tabellen_mit_filepath(db):
        # Vorfilter ueber den Dateinamen haelt die Pfad-Aufloesung klein.
        rows = con.execute(
            f"SELECT id, filepath FROM {t} WHERE filepath LIKE ?",
            (f"%{name}",)).fetchall()
        for r in rows:
            if r[1] and _normal(r[1]) == ziel:
                treffer.append((t, str(r[0])))
    return treffer


def loeschbar(db, pfad, eigene: tuple | None = None,
              ausser: set | None = None) -> tuple:
    """(darf_loeschen, grund).

    `eigene` ist der Eintrag (Tabelle, id), der gerade geloescht wird —
    sein eigener Verweis zaehlt nicht. `ausser` ist eine Menge solcher
    Paare, die im selben Vorgang mitgeloescht werden (Loeschbereiche):
    auch ihre Verweise zaehlen nicht."""
    if not pfad:
        return False, "kein Pfad"
    if not ist_im_datenordner(pfad):
        return False, AUSSERHALB
    frei = set(ausser or ())
    if eigene:
        frei.add(eigene)
    andere = [v for v in verweise(db, pfad) if v not in frei]
    if andere:
        return False, GETEILT
    return True, ""


def datei_loeschen(db, pfad, eigene: tuple | None = None,
                   ausser: set | None = None) -> dict:
    """Loescht die Datei nur, wenn `loeschbar` es erlaubt.

    Rueckgabe: {"geloescht": bool, "grund": str}. Ein Fehler beim Loeschen
    selbst wird gemeldet, nicht geworfen — der Eintrag verschwindet
    trotzdem, und die Datei ist dann ein Aufraeumfall."""
    ok, grund = loeschbar(db, pfad, eigene=eigene, ausser=ausser)
    if not ok:
        if grund != "kein Pfad":
            logger.info("Datei bleibt liegen (%s): %s", grund, pfad)
        return {"geloescht": False, "grund": grund}
    try:
        Path(str(pfad)).unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Dokument-Datei konnte nicht geloescht werden: %s", exc)
        return {"geloescht": False, "grund": f"Fehler beim Löschen: {exc}"}
    return {"geloescht": True, "grund": ""}


def inhalt_hash(pfad) -> str | None:
    """sha256 des Dateiinhalts, wie beim Upload (#570)."""
    try:
        h = hashlib.sha256()
        with open(pfad, "rb") as f:
            for block in iter(lambda: f.read(1 << 20), b""):
                h.update(block)
        return h.hexdigest()
    except OSError:
        return None


def eindeutiges_ziel(ordner: Path, dateiname: str) -> Path:
    """Ein freier Dateiname in `ordner`: `name.pdf`, sonst `name_1.pdf` ...
    Dieselbe Regel wie beim Upload (`_resolve_upload_filepath`)."""
    ziel = ordner / dateiname
    stem, suffix = ziel.stem or "datei", ziel.suffix
    n = 1
    while ziel.exists():
        ziel = ordner / f"{stem}_{n}{suffix}"
        n += 1
    return ziel


def bestandsbericht(db) -> dict:
    """Lesender Bericht (Expertenmodus): welche Dokument-Eintraege zeigen
    ausserhalb des Datenordners, welche teilen sich eine Datei, welche
    haben keine Datei mehr. Schreibt nichts."""
    con = db.connect()
    rows = con.execute(
        "SELECT id, filename, filepath, profile_id FROM documents "
        "WHERE filepath IS NOT NULL AND filepath != ''").fetchall()
    ausserhalb, fehlt = [], []
    nach_pfad: dict = {}
    for r in rows:
        eintrag = {"id": r["id"], "dateiname": r["filename"],
                   "profil_id": r["profile_id"]}
        if not ist_im_datenordner(r["filepath"]):
            ausserhalb.append({**eintrag, "pfad": r["filepath"]})
        if not Path(r["filepath"]).exists():
            fehlt.append(eintrag)
        nach_pfad.setdefault(_normal(r["filepath"]), []).append(eintrag)
    geteilt = [{"eintraege": v} for v in nach_pfad.values() if len(v) > 1]
    return {
        "geprueft": len(rows),
        "ausserhalb_datenordner": ausserhalb,
        "geteilte_dateien": geteilt,
        "datei_fehlt": fehlt,
        "hinweis": (
            "Nur ein Bericht, es wurde nichts geändert. Einträge außerhalb "
            "des Datenordners zeigen auf Dateien des Nutzers; PBP löscht sie "
            "nie. Geteilte Dateien bleiben beim Löschen eines Eintrags "
            "liegen, solange ein anderer Eintrag sie benutzt."),
    }
