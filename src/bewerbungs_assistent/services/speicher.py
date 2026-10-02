"""Speicher & Downloads: wohin PBP schreibt und lädt, wie viel dort liegt, und Bereinigen in zwei Schritten (#1131, I19).

Der Rechner des Anwenders soll nicht zugemüllt werden, und er soll sehen können, wo etwas liegt. Dieses Modul
liefert dafür EINE Auskunft, die das Dashboard (Einstellungen › Speicher & Downloads) und Claude
(`speicher_anzeigen`) gleichermaßen lesen. Es führt keine zweite Liste: der Datenordner kommt aus
`datenordner.uebersicht()` (#1097), die Komponenten aus `components`, die Programmversionen aus dem
Auto-Update (#1093).

Wer hat es angelegt? Jeder Ort trägt es:

* `pbp` — PBP selbst (Datenordner, Programmordner),
* `komponente` — ein Zusatzprogramm, das PBP auf Wunsch einrichtet (Texterkennung),
* `fremd` — ein anderes Programm (Playwright-Browser, Ollama-Modelle): PBP zeigt und erklärt es und löscht es nie,
* `du` — der Mensch selbst (Installationsdateien im Downloads-Ordner, gewählte Ablageordner).

Bereinigen geschieht in zwei Schritten, nie ohne Bestätigung und nie, solange Hintergrundarbeit läuft
(`datenordner.laufende_arbeit`): erst die Vorschau mit Zahlen und Dateiliste, dann `bestaetigt=True`. Jede Aktion
kennt ihre Wurzel und löscht nichts, was nicht darunter liegt.

Ein Guard (`tests/test_v18_speicher_1131.py`) hält jede Stelle im Code, die außerhalb des Datenordners schreibt, gegen
`STELLEN_IM_CODE`: eine neue Stelle ohne Eintrag fällt dort auf, statt unbemerkt Platz zu belegen.
"""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

logger = logging.getLogger("bewerbungs_assistent.speicher")

URHEBER_TEXT = {
    "pbp": "PBP",
    "komponente": "Von PBP eingerichtet",
    "du": "Du",
    "fremd": "Ein anderes Programm",
}

#: Wie lange das Nachmessen eines einzelnen Ortes höchstens dauert; danach steht „mindestens“.
FRIST_JE_ORT_S = 4.0
#: Ein Ort mit so vielen Einträgen ist ungewöhnlich; die Messung bricht ab und sagt „mindestens“.
MAX_EINTRAEGE_MESSUNG = 400_000
MAX_TIEFE = 25
#: So viele Zeilen zeigt die Vorschau höchstens (die Zahl insgesamt steht immer dabei).
MAX_ZEILEN_VORSCHAU = 60


# ── Stellen im Code ──────────────────────────────────────────────────────────────────────

#: Jede Datei unter `src/bewerbungs_assistent`, die auf einen Ort außerhalb des Datenordners zeigt, mit dem Grund, warum
#: das in Ordnung ist: (Kategorie, Satz). Kategorien: `ort` (steht in der Übersicht), `liest` (liest nur, schreibt nichts),
#: `kurz` (kurzlebig: Systemordner für temporäre Dateien, nach Gebrauch gelöscht), `klein` (wenige KB, z. B. eine
#: Verknüpfung), `eingabe` (der Mensch wählt den Ort selbst). Der Guard prüft, dass keine Datei fehlt.
STELLEN_IM_CODE = {
    "database.py": ("ort", "legt den Datenordner fest (Ort „daten“)"),
    "logging_config.py": ("ort", "Protokolle liegen im Datenordner (Ort „daten“)"),
    "services/auto_update/layout.py": ("ort", "der Programmordner (Ort „programm“)"),
    "services/components.py": ("ort", "Komponenten und Playwright-Browser (Orte „komponenten“, „playwright“)"),
    "services/ablage.py": ("eingabe", "Ablage- und Vorlagenordner wählt der Mensch (Ort „eigene“)"),
    "services/dateiablage.py": ("eingabe", "Dateien, die der Mensch ausdrücklich ablegt"),
    "services/ocr_service.py": ("kurz", "temporärer Ordner für die Seitenbilder der Texterkennung, wird sofort gelöscht"),
    "export_report.py": ("kurz", "temporäre Bilddatei für einen Bericht, wird nach dem Einbetten gelöscht"),
    "dashboard.py": ("liest", "die Ordnerauswahl zeigt Home und Downloads; der Datenexport baut sein ZIP in einem temporären Ordner"),
    "services/claude_neustart.py": ("liest", "sucht die Programmdatei von Claude Desktop, schreibt nichts"),
    "services/deinstallation.py": ("liest", "beschreibt, was der Deinstaller entfernt, schreibt nichts"),
    "services/ollama_start.py": ("klein", "findet Ollama; die Verknüpfung „Ollama beenden“ auf dem Desktop ist wenige KB groß"),
    "services/speicher.py": ("ort", "dieses Modul selbst: misst und bereinigt die Orte"),
}


# ── Messen ───────────────────────────────────────────────────────────────────────────────

def messen(pfad, frist_s: float = FRIST_JE_ORT_S) -> tuple:
    """(Bytes, vollständig). Folgt keinen Verknüpfungen, bricht nach `frist_s` Sekunden ab und sagt es."""
    pfad = Path(pfad)
    ende = time.monotonic() + frist_s
    try:
        if pfad.is_file():
            return pfad.stat().st_size, True
        if not pfad.is_dir():
            return 0, True
    except OSError:
        return 0, True
    gesamt = 0
    zaehler = 0
    stapel = [(str(pfad), 0)]
    while stapel:
        ordner, tiefe = stapel.pop()
        try:
            with os.scandir(ordner) as it:
                for eintrag in it:
                    zaehler += 1
                    if zaehler > MAX_EINTRAEGE_MESSUNG or time.monotonic() > ende:
                        return gesamt, False
                    try:
                        if eintrag.is_symlink():
                            continue
                        if eintrag.is_dir(follow_symlinks=False):
                            if tiefe < MAX_TIEFE:
                                stapel.append((eintrag.path, tiefe + 1))
                        else:
                            gesamt += eintrag.stat(follow_symlinks=False).st_size
                    except OSError:
                        continue
        except OSError:
            continue
    return gesamt, True


def _eintrag(name: str, was: str, pfad: Path, frist_s: float = FRIST_JE_ORT_S) -> dict:
    b, voll = messen(pfad, frist_s)
    return {"name": name, "was": was, "pfad": str(pfad), "bytes": b, "vollstaendig": voll}


# ── Die Orte ─────────────────────────────────────────────────────────────────────────────

def downloads_ordner() -> Path:
    return Path(os.environ.get("PBP_DOWNLOADS_ORDNER") or (Path.home() / "Downloads"))


def ollama_modelle() -> Path:
    vorgabe = os.environ.get("OLLAMA_MODELS")
    return Path(vorgabe) if vorgabe else (Path.home() / ".ollama" / "models")


def _ist_pbp_installer(zip_pfad: Path) -> bool:
    """Ein ZIP, das wirklich ein PBP-Installationspaket ist: Name `PBP-*.zip` UND `INSTALLIEREN.bat` darin."""
    try:
        with zipfile.ZipFile(zip_pfad) as zf:
            return any(n == "INSTALLIEREN.bat" or n.endswith("/INSTALLIEREN.bat") for n in zf.namelist()[:5000])
    except (OSError, zipfile.BadZipFile, ValueError):
        return False


def installationspakete() -> list:
    """PBP-Installationspakete im Downloads-Ordner: [(Pfad, Bytes)]. Name UND Inhalt, nie ein Muster allein."""
    gefunden = []
    try:
        with os.scandir(downloads_ordner()) as it:
            for e in it:
                n = e.name.lower()
                if not (n.startswith("pbp-") and n.endswith(".zip")):
                    continue
                try:
                    if e.is_file(follow_symlinks=False):
                        gefunden.append((Path(e.path), e.stat(follow_symlinks=False).st_size))
                except OSError:
                    continue
    except OSError:
        return []
    return sorted((g for g in gefunden if _ist_pbp_installer(g[0])), key=lambda g: g[0].name.lower())


def programmordner():
    try:
        from .auto_update import layout
        return layout.programmordner()
    except Exception:  # noqa: BLE001 — ohne Programmordner (Quellcode, macOS, Linux) gibt es den Ort nicht
        return None


def _ort_daten(db, frist_s) -> dict:
    from . import datenordner
    basis = datenordner._datenordner()
    eintraege = [{"name": e["name"], "was": e["was"], "pfad": e["pfad"], "bytes": e["bytes"], "vollstaendig": True}
                 for e in datenordner.uebersicht(basis)]
    return {
        "id": "daten", "name": "Deine Daten", "urheber": "pbp", "pfad": str(basis),
        "was": "Datenbank, Dokumente, Sicherungen, Protokolle und Browser-Sitzungen. Hier liegt alles Persönliche.",
        "eintraege": sorted(eintraege, key=lambda e: -e["bytes"]),
        "aktionen": ["sicherungen", "protokolle", "export"],
    }


def _ort_programm(db, frist_s) -> dict:
    app = programmordner()
    ort = {"id": "programm", "name": "Das Programm", "urheber": "pbp",
           "was": "Die Python-Laufzeit, der Startbaustein und die installierten Versionen von PBP (für das Zurückschalten).",
           "aktionen": ["alte_fassungen", "update_arbeitsordner"], "eintraege": []}
    if app is None:
        return {**ort, "pfad": "", "hinweis": "PBP läuft hier nicht aus dem Installationsordner (Quellcode oder ein anderes System)."}
    app = Path(app)
    ort["pfad"] = str(app)
    try:
        from .auto_update import layout
        pf = layout.pfade(app)
        klartext = {"python": "Python-Laufzeit", "boot": "Startbaustein"}
        for name in ("python", "boot"):
            if (app / name).exists():
                ort["eintraege"].append(_eintrag(klartext[name], "Wird bei jedem Start gebraucht.", app / name, frist_s))
        aktuell = layout.aktuelle_fassung(app)
        for v in layout.installierte_fassungen(app):
            rolle = "Diese Version läuft beim nächsten Start." if v == aktuell else "Frühere Version, bleibt zum Zurückschalten liegen."
            ort["eintraege"].append(_eintrag(f"Version {v}", rolle, pf.fassung(v), frist_s))
        if pf.arbeit.exists():
            ort["eintraege"].append(_eintrag("Arbeitsordner für Updates", "Zwischenablage eines Updates; wird nach jedem Lauf geleert.",
                                             pf.arbeit, frist_s))
    except Exception as exc:  # noqa: BLE001 — eine unlesbare Aufstellung darf die Übersicht nicht kippen
        logger.debug("Programmordner nicht aufgeschlüsselt: %s", exc)
    return ort


def _ort_komponenten(db, frist_s) -> dict:
    from . import components
    basis = components.components_dir()
    ort = {"id": "komponenten", "name": "Zusatzprogramme von PBP", "urheber": "komponente", "pfad": str(basis),
           "was": "Texterkennung (Tesseract) und andere Komponenten, die PBP auf Wunsch einrichtet.",
           "aktionen": ["komponenten_reste"], "eintraege": []}
    try:
        for kind in sorted(basis.iterdir()):
            ort["eintraege"].append(_eintrag(kind.name, "Ordner einer Komponente" if kind.is_dir() else "Datei im Komponenten-Ordner",
                                             kind, frist_s))
    except OSError:
        pass
    return ort


def _ort_playwright(db, frist_s) -> dict:
    from . import components
    return {"id": "playwright", "name": "Browser für die Jobsuche", "urheber": "fremd", "pfad": str(components.playwright_basis()),
            "was": ("Chromium von Playwright. Manche Jobbörsen verlangen einen Browser. Der Ordner liegt außerhalb von PBP "
                    "und wird auch von anderen Programmen benutzt; PBP löscht ihn nie."),
            "aktionen": [], "eintraege": []}


def _ort_ollama(db, frist_s) -> dict:
    return {"id": "ollama", "name": "Lokale KI (Ollama)", "urheber": "fremd", "pfad": str(ollama_modelle()),
            "was": ("Sprachmodelle von Ollama. PBP lädt sie auf deinen Wunsch, verwaltet werden sie von Ollama selbst "
                    "(Modelle entfernst du dort, im Terminal mit „ollama rm“). PBP löscht sie nie."),
            "aktionen": [], "eintraege": []}


def _ort_downloads(db, frist_s) -> dict:
    return {"id": "downloads", "name": "Installationsdateien im Downloads-Ordner", "urheber": "du",
            "pfad": str(downloads_ordner()),
            "was": ("PBP-ZIP-Dateien, die du für eine Installation oder ein Update heruntergeladen hast. Nach der Installation "
                    "werden sie nicht mehr gebraucht. Gezeigt werden nur Dateien, die wirklich ein PBP-Installationspaket sind."),
            "aktionen": ["downloads_zip"], "summe_aus_eintraegen": True,
            "eintraege": [{"name": p.name, "was": "PBP-Installationspaket", "pfad": str(p), "bytes": b, "vollstaendig": True}
                          for p, b in installationspakete()]}


def _ort_eigene(db, frist_s) -> dict:
    from . import datenordner
    ort = {"id": "eigene", "name": "Deine eigenen Ordner", "urheber": "du", "pfad": "",
           "was": "Ablage- und Vorlagenordner, die du in den Einstellungen gewählt hast. PBP legt dort Lebensläufe und Anschreiben ab.",
           "aktionen": [], "summe_aus_eintraegen": True, "eintraege": []}
    try:
        for e in datenordner.ausserhalb(db):
            ort["eintraege"].append(_eintrag(e["was"], "Von dir gewählt", Path(e["pfad"]), frist_s))
    except Exception as exc:  # noqa: BLE001
        logger.debug("Eigene Ordner nicht lesbar: %s", exc)
    return ort


_ORTE = (
    ("daten", _ort_daten), ("programm", _ort_programm), ("komponenten", _ort_komponenten),
    ("playwright", _ort_playwright), ("ollama", _ort_ollama), ("downloads", _ort_downloads), ("eigene", _ort_eigene),
)
ORT_IDS = tuple(i for i, _ in _ORTE)


def _ort_fertig(ort: dict, frist_s: float) -> dict:
    """Ergänzt Größe, Vorhandensein und Klartext. Orte mit eigener Summe (Treffer, mehrere Ordner) addieren ihre Einträge."""
    pfad = ort.get("pfad") or ""
    ort["urheber_text"] = URHEBER_TEXT.get(ort["urheber"], ort["urheber"])
    ort["aktionen"] = list(ort.get("aktionen", []))
    if ort.get("summe_aus_eintraegen"):
        ort["bytes"] = sum(e["bytes"] for e in ort["eintraege"])
        ort["vollstaendig"] = all(e.get("vollstaendig", True) for e in ort["eintraege"])
        ort["vorhanden"] = bool(ort["eintraege"])
    elif pfad:
        ort["vorhanden"] = Path(pfad).exists()
        ort["bytes"], ort["vollstaendig"] = messen(pfad, frist_s) if ort["vorhanden"] else (0, True)
    else:
        ort["bytes"], ort["vollstaendig"], ort["vorhanden"] = 0, True, False
    ort["oeffnen"] = bool(pfad) and Path(pfad).exists()
    ort["nichts_vorhanden"] = (not ort["vorhanden"]) or ort["bytes"] == 0
    return ort


def uebersicht(db, *, frist_s: float = FRIST_JE_ORT_S) -> dict:
    """Alle Orte mit Größe, Urheber und Bereinigungsmöglichkeiten. Liest nur."""
    from . import datenordner
    orte = []
    for ort_id, bauen in _ORTE:
        try:
            ort = bauen(db, frist_s)
        except Exception as exc:  # noqa: BLE001 — ein Ort, der sich nicht lesen lässt, darf die Übersicht nicht kippen
            logger.warning("Speicher: Ort %s nicht lesbar: %s", ort_id, exc)
            ort = {"id": ort_id, "name": ort_id, "urheber": "pbp", "pfad": "", "was": "Nicht lesbar.", "aktionen": [], "eintraege": []}
        orte.append(_ort_fertig(ort, frist_s))
    laufend = datenordner.laufende_arbeit()
    return {
        "orte": orte,
        "gesamt_bytes": sum(o["bytes"] for o in orte if o["urheber"] != "fremd"),
        "gesamt_fremd_bytes": sum(o["bytes"] for o in orte if o["urheber"] == "fremd"),
        "aktionen": {i: {k: v for k, v in a.items() if k in ("titel", "erklaerung", "ort", "braucht_auswahl", "knopf")}
                     for i, a in AKTIONEN.items()},
        "laufende_arbeit": laufend,
        "laufende_arbeit_text": datenordner.arbeit_klartext(laufend) if laufend else "",
    }


def ordner_oeffnen(ort_id: str, db=None) -> dict:
    """Öffnet den Ordner eines Ortes im Dateimanager. Der Pfad kommt NIE aus der Anfrage, nur aus der festen Liste."""
    if ort_id not in ORT_IDS:
        return {"status": "fehler", "text": f"Unbekannter Ort „{ort_id}“.", "erlaubt": list(ORT_IDS)}
    try:
        ort = dict(_ORTE)[ort_id](db, 0.0)
    except Exception as exc:  # noqa: BLE001
        return {"status": "fehler", "text": f"Der Ort ließ sich nicht bestimmen: {exc}"}
    pfad = Path(ort.get("pfad") or "")
    if not ort.get("pfad") or not pfad.exists():
        return {"status": "nicht_vorhanden", "text": "Diesen Ordner gibt es nicht (mehr)."}
    if not pfad.is_dir():
        pfad = pfad.parent
    try:
        if sys.platform == "win32":
            os.startfile(str(pfad))  # noqa: S606 — fester Pfad aus der eigenen Liste
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(pfad)])
        else:
            subprocess.Popen(["xdg-open", str(pfad)])
    except Exception as exc:  # noqa: BLE001
        return {"status": "fehler", "text": f"Der Ordner ließ sich nicht öffnen: {exc}", "pfad": str(pfad)}
    return {"status": "ok", "pfad": str(pfad)}


# ── Bereinigen: die Aktionen ─────────────────────────────────────────────────────────────

def _datum_text(iso: str) -> str:
    try:
        from datetime import datetime
        return datetime.fromisoformat(iso).strftime("%d.%m.%Y %H:%M")
    except (TypeError, ValueError):
        return str(iso)


def _kandidat(kid: str, name: str, was: str, pfad, wurzel) -> dict:
    p = Path(pfad)
    b, _ = messen(p, 10.0)
    return {"id": kid, "name": name, "was": was, "bytes": b, "pfade": [str(p)], "wurzel": str(wurzel)}


def _loeschen(pfad: Path, wurzel: Path) -> tuple:
    """(ok, Bytes). Löscht nur, was UNTER der Wurzel liegt, nie die Wurzel selbst und keine Verknüpfung."""
    try:
        echt, w = pfad.resolve(), Path(wurzel).resolve()
    except OSError:
        return False, 0
    if echt == w or not echt.is_relative_to(w) or pfad.is_symlink():
        logger.warning("Speicher: %s liegt nicht unter %s – nicht gelöscht", pfad, wurzel)
        return False, 0
    b, _ = messen(pfad, 30.0)
    for versuch in range(3):
        try:
            if pfad.is_dir():
                shutil.rmtree(pfad)
            else:
                pfad.unlink(missing_ok=True)
            return True, b
        except OSError as exc:
            if versuch == 2:
                logger.warning("Speicher: %s nicht gelöscht: %s", pfad, exc)
                return False, 0
            time.sleep(0.3)
    return False, 0


def _entferne_pfade(db, kandidaten) -> dict:
    entfernt, bytes_frei, fehler = 0, 0, []
    for k in kandidaten:
        ok_alle = True
        for pfad in k["pfade"]:
            ok, b = _loeschen(Path(pfad), Path(k["wurzel"]))
            ok_alle = ok_alle and ok
            bytes_frei += b if ok else 0
        if ok_alle:
            entfernt += 1
        else:
            fehler.append(k["name"])
    return {"entfernt": entfernt, "bytes": bytes_frei, "fehler": fehler}


def _leer(hinweis: str) -> dict:
    return {"kandidaten": [], "bleibt": [], "hinweis": hinweis}


# 1. Sicherungen ---------------------------------------------------------------------------

def _finde_sicherungen(db, auswahl) -> dict:
    from . import sicherung
    alle = sicherung.liste(db)
    if not alle:
        return _leer("Es gibt keine Sicherungen.")
    neueste = alle[0]
    kandidaten = [{"id": e["name"], "name": f"{_datum_text(e['zeit'])} · {e['anlass_text']}",
                   "was": "mit Dokumenten" if e["dokumente"] else "nur die Datenbank", "bytes": e["groesse"], "pfade": [], "wurzel": ""}
                  for e in alle[1:]]
    hinweis = (f"Die neueste Sicherung ({_datum_text(neueste['zeit'])}) bleibt immer. PBP räumt selbst auf: "
               f"{sicherung.TAGE_BEHALTEN} Tage täglich, danach {sicherung.WOCHEN_BEHALTEN} Wochen je eine.")
    if auswahl is not None:
        gewaehlt = {str(a) for a in auswahl}
        kandidaten = [k for k in kandidaten if k["id"] in gewaehlt]
    return {"kandidaten": kandidaten, "bleibt": [neueste["name"]], "hinweis": hinweis}


def _entferne_sicherungen(db, kandidaten) -> dict:
    from . import sicherung
    erg = sicherung.entfernen(db, [k["id"] for k in kandidaten])
    return {"entfernt": len(erg["geloescht"]), "bytes": erg["bytes"], "fehler": list(erg["abgelehnt"])}


# 2. Protokolle ----------------------------------------------------------------------------

def _offene_protokolle() -> set:
    offen = set()
    for lg in [logging.getLogger()] + [logging.getLogger(n) for n in list(logging.root.manager.loggerDict)]:
        for h in getattr(lg, "handlers", []):
            ziel = getattr(h, "baseFilename", "")
            if ziel:
                try:
                    offen.add(os.path.normcase(str(Path(ziel).resolve())))
                except OSError:
                    pass
    return offen


def _finde_protokolle(db, auswahl) -> dict:
    from . import datenordner
    ordner = datenordner._datenordner() / "logs"
    if not ordner.is_dir():
        return _leer("Es gibt keine Protokolle.")
    offen = _offene_protokolle()
    kandidaten = []
    for f in sorted(ordner.iterdir(), key=lambda p: p.name):
        if not f.is_file() or os.path.normcase(str(f.resolve())) in offen:
            continue
        kandidaten.append(_kandidat(f.name, f.name, "Älteres Protokoll", f, ordner))
    return {"kandidaten": kandidaten, "bleibt": [],
            "hinweis": "Das Protokoll, in das PBP gerade schreibt, bleibt. Protokolle nennen unter anderem Firmen."}


# 3. Export --------------------------------------------------------------------------------

def _finde_export(db, auswahl) -> dict:
    from . import datenordner
    ordner = datenordner._datenordner() / "export"
    if not ordner.is_dir():
        return _leer("Es gibt keine erzeugten Dateien.")
    kandidaten = [_kandidat(p.name, p.name, "Erzeugte Datei" if p.is_file() else "Erzeugter Ordner", p, ordner)
                  for p in sorted(ordner.iterdir(), key=lambda p: p.name.lower())]
    return {"kandidaten": kandidaten, "bleibt": [],
            "hinweis": ("Lebensläufe, Anschreiben und Berichte, die PBP erzeugt hat. Sie lassen sich jederzeit neu erzeugen. "
                        "Dateien in einem eigenen Ablageordner sind davon nicht betroffen.")}


# 4. Alte Programmversionen ------------------------------------------------------------------

def _finde_fassungen(db, auswahl) -> dict:
    app = programmordner()
    if app is None:
        return _leer("PBP läuft hier nicht aus dem Installationsordner.")
    from .auto_update import aufraeumen, layout, zustand
    behalten = zustand.vorgaenger_behalten(db)
    b = aufraeumen.fassungen_aufraeumen(app, behalten, nur_vorschau=True)
    pf = layout.pfade(app)
    kandidaten = [{"id": v, "name": f"Version {v}", "was": "Frühere Version", "bytes": aufraeumen.groesse(pf.fassung(v)),
                   "pfade": [], "wurzel": ""} for v in b["geloescht"]]
    hinweis = (f"PBP behält die laufende Version und {behalten} frühere (einstellbar unter Einstellungen › Updates). "
               "Eine Version, die gerade benutzt wird, bleibt immer.")
    return {"kandidaten": kandidaten, "bleibt": list(b["behalten"]), "hinweis": hinweis}


def _entferne_fassungen(db, kandidaten) -> dict:
    app = programmordner()
    from .auto_update import aufraeumen, zustand
    b = aufraeumen.fassungen_aufraeumen(app, zustand.vorgaenger_behalten(db))
    return {"entfernt": len(b["geloescht"]), "bytes": b["frei_bytes"], "fehler": list(b["uebersprungen"])}


# 5. Arbeitsordner und Reste von Updates ---------------------------------------------------------

def _update_laeuft() -> bool:
    try:
        from .auto_update import lauf
        return lauf.job_stand().get("status") == "laeuft"
    except Exception:  # noqa: BLE001
        return False


def _finde_update_reste(db, auswahl) -> dict:
    app = programmordner()
    if app is None:
        return _leer("PBP läuft hier nicht aus dem Installationsordner.")
    from .auto_update import aufraeumen, layout
    pf = layout.pfade(app)
    kandidaten = []
    if pf.arbeit.exists():
        b = aufraeumen.groesse(pf.arbeit)
        if b > 0 or any(pf.arbeit.iterdir()):
            kandidaten.append({"id": "arbeit", "name": "Arbeitsordner für Updates", "was": "Heruntergeladene und entpackte Reste",
                               "bytes": b, "pfade": [], "wurzel": ""})
    for name in aufraeumen.reste_entfernen(app, nur_vorschau=True):
        kandidaten.append({"id": name, "name": f"Angefangene Installation {name}", "was": "Rest eines abgebrochenen Updates",
                           "bytes": aufraeumen.groesse(pf.versionen / name), "pfade": [], "wurzel": ""})
    return {"kandidaten": kandidaten, "bleibt": [], "hinweis": "Das sind nur Reste: die installierten Versionen bleiben unberührt."}


def _entferne_update_reste(db, kandidaten) -> dict:
    app = programmordner()
    from .auto_update import aufraeumen, layout
    pf = layout.pfade(app)
    aufraeumen.arbeit_leeren(app)
    aufraeumen.reste_entfernen(app)
    entfernt, frei, fehler = 0, 0, []
    for k in kandidaten:
        ziel = pf.arbeit if k["id"] == "arbeit" else pf.versionen / k["id"]
        # Der Arbeitsordner darf als leerer Ordner stehen bleiben; bei einem Rest zaehlt, ob er weg ist.
        uebrig = (any(ziel.iterdir()) if ziel.is_dir() else False) if k["id"] == "arbeit" else ziel.exists()
        if uebrig:
            fehler.append(k["name"])
        else:
            entfernt += 1
            frei += k["bytes"]
    return {"entfernt": entfernt, "bytes": frei, "fehler": fehler}


# 6. Liegengebliebene Installationsdateien von Komponenten -------------------------------------------

def _finde_komponenten_reste(db, auswahl) -> dict:
    from . import components
    ordner = components.components_dir()
    kandidaten = [{"id": p.name, "name": p.name, "was": "Liegengebliebene Installationsdatei", "bytes": b, "pfade": [str(p)],
                   "wurzel": str(ordner)} for p, b in components.setup_reste_finden()]
    return {"kandidaten": kandidaten, "bleibt": [],
            "hinweis": "Fertig installierte Komponenten bleiben. Entfernt werden nur Setup-Dateien und angefangene Downloads."}


def _entferne_komponenten_reste(db, kandidaten) -> dict:
    from . import components
    erg = components.setup_reste_entfernen(db)
    return {"entfernt": erg.get("entfernt", 0), "bytes": erg.get("bytes", 0), "fehler": []}


# 7. Installationspakete im Downloads-Ordner ----------------------------------------------------------

def _finde_downloads_zip(db, auswahl) -> dict:
    ordner = downloads_ordner()
    kandidaten = [{"id": p.name, "name": p.name, "was": "PBP-Installationspaket", "bytes": b, "pfade": [str(p)], "wurzel": str(ordner)}
                  for p, b in installationspakete()]
    if auswahl is not None:
        gewaehlt = {str(a) for a in auswahl}
        kandidaten = [k for k in kandidaten if k["id"] in gewaehlt]
    return {"kandidaten": kandidaten, "bleibt": [],
            "hinweis": ("Das sind deine eigenen Downloads. Nichts wird ohne deine Auswahl gelöscht. "
                        "Eine Installation, die du später wiederholen willst, lädst du neu herunter.")}


AKTIONEN = {
    "sicherungen": {
        "titel": "Alte Sicherungen löschen", "ort": "daten", "braucht_auswahl": True, "knopf": "Auswählen …",
        "erklaerung": "Du wählst, welche Sicherungen weg sollen. Die neueste bleibt immer.",
        "finde": _finde_sicherungen, "entferne": _entferne_sicherungen},
    "protokolle": {
        "titel": "Alte Protokolle löschen", "ort": "daten", "braucht_auswahl": False, "knopf": "Vorschau …",
        "erklaerung": "Protokolle von früheren Starts. Das aktuelle bleibt.",
        "finde": _finde_protokolle, "entferne": _entferne_pfade},
    "export": {
        "titel": "Erzeugte Dateien löschen", "ort": "daten", "braucht_auswahl": False, "knopf": "Vorschau …",
        "erklaerung": "Lebensläufe, Anschreiben und Berichte im Export-Ordner von PBP. Sie lassen sich neu erzeugen.",
        "finde": _finde_export, "entferne": _entferne_pfade},
    "alte_fassungen": {
        "titel": "Frühere Versionen von PBP löschen", "ort": "programm", "braucht_auswahl": False, "knopf": "Vorschau …",
        "erklaerung": "Versionen, die über die eingestellte Anzahl hinausgehen. Die laufende Version bleibt immer.",
        "finde": _finde_fassungen, "entferne": _entferne_fassungen},
    "update_arbeitsordner": {
        "titel": "Reste von Updates löschen", "ort": "programm", "braucht_auswahl": False, "knopf": "Vorschau …",
        "erklaerung": "Heruntergeladene Update-Dateien und angefangene Installationen. Die installierten Versionen bleiben.",
        "finde": _finde_update_reste, "entferne": _entferne_update_reste},
    "komponenten_reste": {
        "titel": "Liegengebliebene Installationsdateien löschen", "ort": "komponenten", "braucht_auswahl": False, "knopf": "Vorschau …",
        "erklaerung": "Setup-Dateien und angefangene Downloads von Zusatzprogrammen. Fertig installierte Komponenten bleiben.",
        "finde": _finde_komponenten_reste, "entferne": _entferne_komponenten_reste},
    "downloads_zip": {
        "titel": "Installationspakete löschen", "ort": "downloads", "braucht_auswahl": True, "knopf": "Auswählen …",
        "erklaerung": "PBP-ZIP-Dateien in deinem Downloads-Ordner. Du wählst, welche weg sollen.",
        "finde": _finde_downloads_zip, "entferne": _entferne_pfade},
}


EIGENER_AUFRUF = "ein laufendes Claude-Werkzeug"


def _blockade(db, aktion: str, *, als_werkzeug: bool = False):
    """Warum jetzt nicht? (Text) oder None. Nie bereinigen, solange Hintergrundarbeit die Daten benutzt.

    Als Claude-Werkzeug ist der eigene Aufruf selbst ein „laufendes Claude-Werkzeug“; er zaehlt nicht als fremde Arbeit
    (sonst waere jede Bereinigung ueber Claude abgelehnt). Bereinigt werden nur Dateien, keine Datenbankverbindung.
    """
    from . import datenordner
    laufend = [n for n in datenordner.laufende_arbeit() if not (als_werkzeug and n == EIGENER_AUFRUF)]
    if laufend:
        return f"Gerade läuft {datenordner.arbeit_klartext(laufend)}. Warte, bis sie fertig ist, und versuche es dann noch einmal."
    if aktion in ("alte_fassungen", "update_arbeitsordner") and _update_laeuft():
        return "Gerade wird ein Update vorbereitet. Warte, bis es fertig ist."
    if aktion == "komponenten_reste":
        try:
            from . import components
            if components._installation_laeuft(db):
                return "Gerade wird ein Zusatzprogramm installiert. Warte, bis es fertig ist."
        except Exception:  # noqa: BLE001
            pass
    return None


def _oeffentlich(kandidaten: list) -> list:
    return [{k: v for k, v in c.items() if k in ("id", "name", "was", "bytes")} for c in kandidaten]


def bereinigen(db, aktion: str, auswahl=None, *, bestaetigt: bool = False, als_werkzeug: bool = False) -> dict:
    """Zwei Schritte: ohne `bestaetigt` nur die Vorschau; mit `bestaetigt=True` wird gelöscht.

    Antwort: `status` ist `auswahl` (Aktionen, bei denen der Mensch auswählt: die Liste), `vorschau` (Zahlen und Dateien),
    `bereinigt`, `teilweise`, `nichts`, `abgelehnt` (Hintergrundarbeit läuft) oder `fehler` (unbekannte Aktion, fehlende
    Auswahl). Nach dem Löschen steht der neu gemessene Ort in `ort_neu`.
    """
    a = AKTIONEN.get(aktion)
    if a is None:
        return {"status": "fehler", "text": f"Unbekannte Aktion „{aktion}“.", "erlaubt": list(AKTIONEN)}
    if auswahl is not None and not isinstance(auswahl, (list, tuple, set)):
        return {"status": "fehler", "text": "Die Auswahl muss eine Liste sein."}
    grund = _blockade(db, aktion, als_werkzeug=als_werkzeug)
    if grund:
        return {"status": "abgelehnt", "aktion": aktion, "titel": a["titel"], "text": grund}
    f = a["finde"](db, list(auswahl) if auswahl is not None else None)
    kandidaten = f["kandidaten"]
    summe = sum(k["bytes"] for k in kandidaten)
    basis = {"aktion": aktion, "titel": a["titel"], "ort": a["ort"], "braucht_auswahl": a["braucht_auswahl"],
             "anzahl": len(kandidaten), "bytes": summe, "kandidaten": _oeffentlich(kandidaten)[:MAX_ZEILEN_VORSCHAU],
             "weitere": max(0, len(kandidaten) - MAX_ZEILEN_VORSCHAU), "bleibt": f.get("bleibt", []), "hinweis": f.get("hinweis", "")}
    if not bestaetigt:
        if not kandidaten:
            return {**basis, "status": "nichts", "text": "Hier gibt es nichts zu bereinigen."}
        if a["braucht_auswahl"] and not auswahl:
            return {**basis, "status": "auswahl",
                    "text": f"{len(kandidaten)} Einträge stehen zur Auswahl ({_mb(summe)}). Wähle aus, was weg soll."}
        return {**basis, "status": "vorschau",
                "text": f"{len(kandidaten)} Einträge, zusammen {_mb(summe)}, würden gelöscht. Bestätige, um sie zu löschen."}
    if a["braucht_auswahl"] and not auswahl:
        return {**basis, "status": "fehler", "text": "Es ist nichts ausgewählt. Wähle aus, was gelöscht werden soll."}
    if not kandidaten:
        return {**basis, "status": "nichts", "text": "Hier gibt es nichts zu bereinigen."}
    erg = a["entferne"](db, kandidaten)
    ort = next((o for o in uebersicht(db)["orte"] if o["id"] == a["ort"]), None)
    status = "bereinigt" if not erg["fehler"] else ("teilweise" if erg["entfernt"] else "nichts")
    text = (f"{erg['entfernt']} Einträge gelöscht, {_mb(erg['bytes'])} frei." if status == "bereinigt"
            else f"{erg['entfernt']} Einträge gelöscht ({_mb(erg['bytes'])} frei); {len(erg['fehler'])} ließen sich nicht löschen: "
                 f"{', '.join(map(str, erg['fehler'][:5]))}. Sie sind vermutlich noch in Benutzung.")
    return {**basis, "status": status, "entfernt": erg["entfernt"], "bytes_frei": erg["bytes"], "nicht_geloescht": erg["fehler"],
            "text": text, "ort_neu": ort}


def _mb(b: int) -> str:
    mb = b / (1024 * 1024)
    if mb >= 1024:
        return f"{mb / 1024:.1f} GB".replace(".", ",")
    if mb >= 10:
        return f"{mb:.0f} MB"
    return f"{mb:.1f} MB".replace(".", ",")
