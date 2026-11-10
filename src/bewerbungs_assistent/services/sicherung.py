"""Datensicherung: regelmaessig, vor grossen Eingriffen, mit Dokumenten —
und ein Weg zurueck (#1098).

Bis v1.7.139 entstand eine Sicherung fast nur vor einem Schemawechsel,
und das Schema stand auf der Stable-Linie seit Monaten still. Das Leeren
eines Bereichs sicherte nichts, die manuelle Sicherung wuchs ohne Grenze
in einem zweiten Ordner, und die Dokumente fehlten ueberall. Einspielen
ging nur von Hand, samt der Falle einer WAL-Datei, die nicht zur neuen
Datenbank passt.

Regeln:

* **Ein Ordner** (`backups` neben der Datenbank), eine Rotation fuer
  jede Art: alles der letzten 7 Tage (je Tag hoechstens die neueste
  taegliche), dazu die neueste Sicherung jeder der 4 Wochen davor. Die
  Sicherung vor einer Migration (#705) liegt im selben Ordner und
  unterliegt derselben Rotation.
* **Dokumente** kommen als ZIP neben die Datenbank-Kopie. Wo sie fehlen,
  sagt es die Liste (`dokumente: false`), statt es zu verschweigen.
* **Kein stilles Auslassen** (#989): reicht der Platz nicht, meldet die
  Sicherung `kein_platz` samt Zahl — eine Sicherung, die die Platte
  fuellt, waere ein neuer Ausfall.
* **Wiederherstellen beim naechsten Start**, BEVOR die Datenbank
  geoeffnet wird. Im laufenden Betrieb zeigen Verbindungen anderer
  Threads (und des MCP-Servers in Claude Desktop) auf die Datei; sie
  darunter auszutauschen war die Absturzursache aus v1.7.11. Vor dem
  Vormerken wird der aktuelle Stand selbst gesichert.
* **Nicht vor der DSGVO-Loeschung.** Die loescht alles, was PBP im Datenordner anlegt,
  Sicherungen eingeschlossen (#1097); eine Sicherung davor waere genau
  das, was sie verhindern soll.
"""
from __future__ import annotations

import logging
import os
import json
import re
import shutil
import sqlite3
import threading
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

ORDNER = "backups"
ALT_ORDNER = "backup"          # frueher: manuelle Sicherung aus dem Dashboard
VORMERKUNG = "wiederherstellen_vorgemerkt"

TAGE_BEHALTEN = 7
WOCHEN_BEHALTEN = 4
#: Ereignis-Sicherungen (vor dem Leeren, manuell ...) je Tag hoechstens so viele
EREIGNISSE_JE_TAG = 5
#: Sicherheitsabstand zum Plattenende
RESERVE_BYTES = 200 * 1024 * 1024

ANLAESSE = {
    "taeglich": "Tägliche Sicherung",
    "manuell": "Von dir angelegt",
    "vor_leeren": "Vor dem Leeren eines Bereichs",
    "vor_zusammenfuehren": "Vor dem Zusammenführen zweier Stellen",
    "vor_wiederherstellen": "Stand vor dem Wiederherstellen",
    "vor_update": "Vor einem Update",
}

_NAME = re.compile(r"^pbp-backup-(\d{4}-\d{2}-\d{2})_(\d{2}-\d{2}-\d{2})(?:-([a-z_]+))?(?:-\d+)?\.db$")


def ordner(db) -> Path:
    return Path(db.db_path).parent / ORDNER


def _zeit(name: str) -> datetime | None:
    m = _NAME.match(name)
    if not m:
        return None
    return datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H-%M-%S")


def _anlass(name: str) -> str:
    m = _NAME.match(name)
    return (m.group(3) if m and m.group(3) else "vor_update")


def _dokumente_zip(db_datei: Path) -> Path:
    return db_datei.with_name(db_datei.stem + "-dokumente.zip")


def _groesse(p: Path) -> int:
    try:
        if p.is_file():
            return p.stat().st_size
        return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
    except OSError:
        return 0


def _altbestand_uebernehmen(basis: Path) -> None:
    """Der alte Ordner `backup/` zieht in `backups/` um (ein Ort, AK 3)."""
    alt = basis / ALT_ORDNER
    if not alt.is_dir():
        return
    ziel = basis / ORDNER
    ziel.mkdir(parents=True, exist_ok=True)
    for f in alt.glob("pbp_backup_*.db"):
        m = re.match(r"pbp_backup_(\d{8})_(\d{6})\.db$", f.name)
        if not m:
            continue
        t = datetime.strptime(m.group(1) + m.group(2), "%Y%m%d%H%M%S")
        neu = ziel / f"pbp-backup-{t:%Y-%m-%d_%H-%M-%S}-manuell.db"
        if not neu.exists():
            shutil.move(str(f), str(neu))
    try:
        alt.rmdir()
    except OSError:
        pass  # dort liegt noch etwas Fremdes — nicht anfassen


def _datenbankkopie_pruefen(datei: Path) -> str:
    """Oeffnet die Kopie und prueft sie (#1350). Leer = in Ordnung, sonst der Mangel."""
    try:
        con = sqlite3.connect(f"file:{datei.as_posix()}?mode=ro", uri=True)
        try:
            ergebnis = [str(z[0]) for z in con.execute("PRAGMA quick_check").fetchall()]
            tabellen = con.execute(
                "SELECT count(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
        finally:
            con.close()
    except sqlite3.Error as exc:
        return f"nicht zu öffnen: {exc}"
    if ergebnis != ["ok"]:
        return "Integritätsprüfung: " + "; ".join(ergebnis[:3])
    if not tabellen:
        return "die Kopie enthält keine Tabellen"
    return ""


def _zip_pruefen(zip_pfad: Path, erwartet: int) -> str:
    """Prueft ein Dokumenten-ZIP: Pruefsummen und Zahl der Dateien (#1350)."""
    try:
        with zipfile.ZipFile(zip_pfad) as z:
            kaputt = z.testzip()
            if kaputt is not None:
                return f"Datei {kaputt} ist beschädigt"
            vorhanden = sum(1 for i in z.infolist() if not i.is_dir())
    except (zipfile.BadZipFile, OSError) as exc:
        return f"nicht zu öffnen: {exc}"
    if vorhanden != erwartet:
        return f"{vorhanden} Dateien statt {erwartet}"
    return ""


def sichern(db, anlass: str = "manuell", mit_dokumenten: bool = True,
            jetzt: datetime | None = None) -> dict:
    """Legt eine Sicherung an. Rueckgabe mit `status`:
    `gesichert` (samt `name`, `groesse`), `kein_platz` oder `fehler`."""
    if anlass not in ANLAESSE:
        raise ValueError(f"Unbekannter Anlass {anlass!r}")
    quelle = Path(db.db_path)
    if not quelle.exists():
        return {"status": "fehler", "fehler": "Keine Datenbank vorhanden."}
    basis = quelle.parent
    _altbestand_uebernehmen(basis)
    ziel_ordner = basis / ORDNER
    ziel_ordner.mkdir(parents=True, exist_ok=True)
    dokumente = basis / "dokumente"
    bedarf = _groesse(quelle) + (_groesse(dokumente) if mit_dokumenten else 0)
    frei = shutil.disk_usage(ziel_ordner).free
    if frei < bedarf + RESERVE_BYTES:
        return {"status": "kein_platz", "benoetigt": bedarf, "frei": frei,
                "fehler": (f"Zu wenig Speicherplatz für eine Sicherung: gebraucht "
                           f"werden etwa {bedarf // (1024 * 1024) + 1} MB plus Reserve, "
                           f"frei sind {frei // (1024 * 1024)} MB.")}
    jetzt = jetzt or datetime.now()
    name = f"pbp-backup-{jetzt:%Y-%m-%d_%H-%M-%S}-{anlass}.db"
    ziel = ziel_ordner / name
    zaehler = 1
    while ziel.exists():  # zwei Sicherungen in derselben Sekunde
        zaehler += 1
        ziel = ziel_ordner / name.replace(".db", f"-{zaehler}.db")
    try:
        # Eigene Verbindung und die Backup-API von SQLite: liest einen
        # konsistenten Stand, auch waehrend andere Threads schreiben.
        src = sqlite3.connect(str(quelle), timeout=30)
        dst = sqlite3.connect(str(ziel))
        try:
            src.execute("PRAGMA busy_timeout=30000")
            src.backup(dst)
        finally:
            dst.close()
            src.close()
    except Exception as exc:  # noqa: BLE001
        # Die Datenbankkopie ist nicht zustande gekommen: es gibt nichts zu behalten.
        try:
            ziel.unlink()
        except OSError:
            pass
        logger.warning("Sicherung fehlgeschlagen: %s", exc)
        return {"status": "fehler", "fehler": f"Sicherung fehlgeschlagen: {exc}"}
    # v1.8.5 (#1350): "gesichert" steht erst nach einer Probe des INHALTS
    # (Regel 8g): die Kopie wird geoeffnet und geprueft. Eine Kopie, die sich
    # nicht lesen laesst, ist keine Sicherung und wird nicht behalten.
    mangel = _datenbankkopie_pruefen(ziel)
    if mangel:
        try:
            ziel.unlink()
        except OSError:
            pass
        logger.warning("Sicherung verworfen, Leseprobe gescheitert: %s", mangel)
        return {"status": "fehler",
                "fehler": f"Die Sicherung wurde angelegt, ließ sich aber nicht lesen "
                          f"und wurde verworfen ({mangel}). Es gibt keine neue Sicherung."}
    # v1.7.146 (#1142): die Datenbank ist das Wichtige und ist jetzt gesichert.
    # Eine gesperrte Datei im Dokumentenordner (Virenscanner, Office) kippte
    # bisher die ganze Sicherung samt Datenbankkopie, und nirgends stand es.
    # Jetzt wird die einzelne Datei uebersprungen und genannt; scheitert das
    # Packen ganz, bleibt die Datenbankkopie und die Meldung sagt es.
    mit_zip, uebersprungen, hinweis = False, [], ""
    if mit_dokumenten and dokumente.is_dir() and any(dokumente.rglob("*")):
        zip_pfad = _dokumente_zip(ziel)
        try:
            geschrieben = 0
            with zipfile.ZipFile(zip_pfad, "w", zipfile.ZIP_DEFLATED) as z:
                for f in dokumente.rglob("*"):
                    if not f.is_file():
                        continue
                    try:
                        z.write(f, f.relative_to(dokumente).as_posix())
                        geschrieben += 1
                    except OSError as exc:  # gesperrt oder ohne Zugriff
                        uebersprungen.append(f.relative_to(dokumente).as_posix())
                        logger.warning("Sicherung: %s uebersprungen (%s)", f.name, exc)
            # v1.8.5 (#1350): Leseprobe auch fuer das ZIP - Zahl der Dateien
            # und Pruefsummen, nicht nur "das Packen warf keinen Fehler".
            mangel = _zip_pruefen(zip_pfad, geschrieben)
            if mangel:
                raise OSError(f"Leseprobe des Dokumenten-ZIP gescheitert: {mangel}")
            mit_zip = True
            if uebersprungen:
                beispiele = ", ".join(uebersprungen[:3]) + (" …" if len(uebersprungen) > 3 else "")
                hinweis = (f"{len(uebersprungen)} Datei(en) im Dokumentenordner waren gesperrt "
                           f"und fehlen in der Sicherung ({beispiele}). Schließe Programme, die "
                           f"sie offen halten, und sichere noch einmal.")
        except Exception as exc:  # noqa: BLE001 - die Datenbankkopie bleibt
            try:
                zip_pfad.unlink()
            except OSError:
                pass
            mit_zip = False
            hinweis = (f"Die Dokumente konnten nicht mitgesichert werden ({exc}). "
                       f"Die Datenbank ist gesichert.")
            logger.warning("Sicherung der Dokumente fehlgeschlagen: %s", exc)
    rotieren(db, jetzt=jetzt)
    logger.info("Sicherung angelegt: %s (%s)", ziel.name, anlass)
    return {"status": "gesichert", "name": ziel.name, "anlass": anlass,
            "dokumente": mit_zip, "uebersprungen": uebersprungen[:20], "hinweis": hinweis,
            "groesse": _groesse(ziel) + (
                _groesse(_dokumente_zip(ziel)) if mit_zip else 0)}


def liste(db) -> list[dict]:
    """Alle Sicherungen, neueste zuerst."""
    basis = ordner(db)
    if not basis.is_dir():
        return []
    eintraege = []
    for f in basis.glob("pbp-backup-*.db"):
        t = _zeit(f.name)
        if t is None:
            continue
        z = _dokumente_zip(f)
        anlass = _anlass(f.name)
        eintraege.append({
            "name": f.name, "zeit": t.isoformat(timespec="seconds"),
            "anlass": anlass, "anlass_text": ANLAESSE.get(anlass, anlass),
            "groesse": _groesse(f) + (_groesse(z) if z.exists() else 0),
            "dokumente": z.exists(),
        })
    eintraege.sort(key=lambda e: e["zeit"], reverse=True)
    return eintraege


def entfernen(db, namen) -> dict:
    """Entfernt die genannten Sicherungen samt Dokumente-ZIP (Einstellungen › Speicher & Downloads, #1131).

    Nur Namen, die `liste` kennt: sie folgen dem Namensmuster und liegen im Sicherungsordner. Die NEUESTE Sicherung
    bleibt immer. Rueckgabe: {'geloescht': [...], 'bytes': n, 'abgelehnt': {name: grund}}.
    """
    alle = liste(db)  # neueste zuerst
    bekannt = {e["name"]: e for e in alle}
    neueste = alle[0]["name"] if alle else None
    basis = ordner(db)
    erg = {"geloescht": [], "bytes": 0, "abgelehnt": {}}
    for name in dict.fromkeys(str(n) for n in (namen or [])):
        if name not in bekannt:
            erg["abgelehnt"][name] = "unbekannte Sicherung"
            continue
        if name == neueste:
            erg["abgelehnt"][name] = "die neueste Sicherung bleibt immer"
            continue
        f = basis / name
        frei = 0
        try:
            for p in (f, _dokumente_zip(f)):
                if p.exists():
                    frei += _groesse(p)
                    p.unlink()
            erg["geloescht"].append(name)
            erg["bytes"] += frei
        except OSError as exc:
            logger.warning("Sicherung nicht entfernt (%s): %s", name, exc)
            erg["abgelehnt"][name] = "ließ sich nicht löschen (in Benutzung?)"
    return erg


def rotieren(db, jetzt: datetime | None = None) -> list[str]:
    """Loescht, was die Regel nicht behaelt. Rueckgabe: geloeschte Namen."""
    jetzt = jetzt or datetime.now()
    alle = liste(db)
    behalten: set[str] = set()
    grenze_tage = jetzt - timedelta(days=TAGE_BEHALTEN)
    taeglich_gesehen: set[str] = set()
    ereignisse_je_tag: dict[str, int] = {}
    wochen: dict[tuple, str] = {}
    for e in alle:  # neueste zuerst
        t = datetime.fromisoformat(e["zeit"])
        tag = t.date().isoformat()
        if t >= grenze_tage:
            if e["anlass"] == "taeglich":
                if tag not in taeglich_gesehen:
                    taeglich_gesehen.add(tag)
                    behalten.add(e["name"])
            else:
                n = ereignisse_je_tag.get(tag, 0)
                if n < EREIGNISSE_JE_TAG:
                    ereignisse_je_tag[tag] = n + 1
                    behalten.add(e["name"])
        else:
            woche = tuple(t.isocalendar())[:2]
            if woche not in wochen and len(wochen) < WOCHEN_BEHALTEN:
                wochen[woche] = e["name"]
                behalten.add(e["name"])
    geloescht = []
    basis = ordner(db)
    for e in alle:
        if e["name"] in behalten:
            continue
        f = basis / e["name"]
        for p in (f, _dokumente_zip(f)):
            try:
                p.unlink()
            except FileNotFoundError:
                pass
            except OSError as exc:
                logger.warning("Alte Sicherung nicht entfernt (%s): %s", p.name, exc)
        geloescht.append(e["name"])
    return geloescht


def letzte(db) -> dict | None:
    alle = liste(db)
    return alle[0] if alle else None


def alter_tage(db, jetzt: datetime | None = None) -> float | None:
    e = letzte(db)
    if not e:
        return None
    return ((jetzt or datetime.now()) - datetime.fromisoformat(e["zeit"])).total_seconds() / 86400


def taeglich_faellig(db, jetzt: datetime | None = None) -> bool:
    heute = (jetzt or datetime.now()).date().isoformat()
    return not any(e["anlass"] == "taeglich" and e["zeit"].startswith(heute)
                   for e in liste(db))


EINSTELLUNG_DOKUMENTE_TAEGLICH = "sicherung_dokumente_taeglich"


def dokumente_taeglich(db) -> bool:
    """Gehört das Dokumenten-ZIP in die TÄGLICHE Sicherung? Vorgabe: ja.

    v1.7.146 (#1138): Seit der Planer auch über Claude Desktop läuft, legt PBP
    wirklich jeden Tag eine Sicherung an — bei großen Dokumentenordnern bis zu
    zwölf Stände mit je einem ZIP. Wer das nicht will, schaltet die Dokumente
    aus der täglichen Sicherung heraus (die Datenbank ist klein und bleibt
    immer drin). Sicherungen, die der Mensch selbst anlegt, und die vor einem
    Eingriff enthalten die Dokumente immer.
    """
    wert = db.get_setting(EINSTELLUNG_DOKUMENTE_TAEGLICH, True)
    return wert not in (False, 0, "0", "false", "nein", "aus")


def dokumente_taeglich_setzen(db, an: bool) -> None:
    db.set_setting(EINSTELLUNG_DOKUMENTE_TAEGLICH, bool(an))


def dokumente_groesse(db) -> int:
    """Bytes im Dokumentenordner (für die Karte: was ein ZIP etwa wiegt)."""
    return _groesse(Path(db.db_path).parent / "dokumente")


def _mit_dokumenten(db, anlass: str) -> bool:
    return anlass != "taeglich" or dokumente_taeglich(db)


_LAUF = threading.Lock()

#: v1.7.146 (#1142): Wartezeit in Minuten nach dem 1., 2., ... Fehlschlag in
#: Folge, bevor die Automatik es wieder versucht. Vorher startete jeder Takt
#: (alle 5 Minuten) einen neuen vollen Kopierversuch, solange eine Datei
#: gesperrt oder die Platte voll war. Das Gedaechtnis lebt im Prozess: nach
#: einem Neustart darf es einmal wieder versuchen.
FRIST_NACH_FEHLER_MIN = (15, 30, 60, 120, 240, 480)
_FEHL: dict = {"anzahl": 0, "zeit": None}


def fehlschlag_merken(jetzt: datetime | None = None) -> None:
    _FEHL["anzahl"] += 1
    _FEHL["zeit"] = jetzt or datetime.now()


def erfolg_merken() -> None:
    _FEHL["anzahl"] = 0
    _FEHL["zeit"] = None


def gesperrt_bis(jetzt: datetime | None = None) -> datetime | None:
    """Bis wann die Automatik nach Fehlschlaegen wartet; None = sie darf es versuchen."""
    if not _FEHL["anzahl"] or _FEHL["zeit"] is None:
        return None
    frist = FRIST_NACH_FEHLER_MIN[min(_FEHL["anzahl"], len(FRIST_NACH_FEHLER_MIN)) - 1]
    bis = _FEHL["zeit"] + timedelta(minutes=frist)
    return bis if (jetzt or datetime.now()) < bis else None


def im_hintergrund(db, anlass: str = "taeglich") -> dict:
    """Startet eine Sicherung im Hintergrund, mit `background_jobs`-Eintrag
    (#799) — die Kopie grosser Bestaende blockiert sonst das Dashboard."""
    if not _LAUF.acquire(blocking=False):
        return {"status": "laeuft_bereits"}
    try:
        job_id = db.create_background_job("sicherung", {"anlass": anlass})
    except Exception:
        _LAUF.release()
        raise

    def _lauf():
        try:
            db.update_background_job(job_id, "running", progress=10,
                                     message="Sicherung läuft")
            erg = sichern(db, anlass=anlass, mit_dokumenten=_mit_dokumenten(db, anlass))
            if erg["status"] == "gesichert":
                erfolg_merken()
            else:
                fehlschlag_merken()
            db.update_background_job(
                job_id, "fertig" if erg["status"] == "gesichert" else "fehler",
                progress=100,
                message=erg.get("fehler") or erg.get("hinweis") or "Sicherung angelegt",
                result=erg)
        except Exception as exc:  # noqa: BLE001
            fehlschlag_merken()
            db.update_background_job(job_id, "fehler", message=str(exc))
        finally:
            _LAUF.release()

    threading.Thread(target=_lauf, daemon=True, name=f"pbp-sicherung-{job_id[:8]}").start()
    return {"status": "gestartet", "job_id": job_id}


def taeglich(db) -> dict:
    """Aus der Automatik: einmal am Tag — und nach einem Fehlschlag mit Wartezeit."""
    if not taeglich_faellig(db):
        return {"status": "schon_gesichert"}
    bis = gesperrt_bis()
    if bis is not None:
        return {"status": "wartet_nach_fehler", "wieder_ab": bis.isoformat(timespec="minutes")}
    return im_hintergrund(db, "taeglich")


def letzter_versuch(db) -> dict | None:
    """Der jüngste Sicherungsversuch samt Ausgang (v1.7.146, #1142).

    `status`: `laeuft`, `fertig` oder `fehler`; `nachricht` der Satz dazu;
    `aktuell` ist wahr, wenn der Versuch NEUER ist als die neueste
    vorhandene Sicherung — ein alter Fehler, der inzwischen durch eine
    gelungene Sicherung überholt ist, soll nichts mehr melden.
    """
    try:
        z = db.connect().execute(
            "SELECT status, message, created_at, updated_at, params FROM background_jobs "
            "WHERE job_type='sicherung' ORDER BY created_at DESC LIMIT 1").fetchone()
    except Exception:  # noqa: BLE001
        return None
    if not z:
        return None
    status = {"fertig": "fertig", "fehler": "fehler", "abgebrochen": "fehler"}.get(z["status"], "laeuft")
    roh = z["updated_at"] or z["created_at"] or ""
    try:
        zeit = datetime.fromisoformat(roh)
        if zeit.tzinfo is not None:
            zeit = zeit.astimezone().replace(tzinfo=None)
    except ValueError:
        zeit = None
    try:
        anlass = (json.loads(z["params"] or "{}") or {}).get("anlass", "")
    except ValueError:
        anlass = ""
    neueste = letzte(db)
    aktuell = True
    if neueste and zeit is not None:
        try:
            aktuell = zeit > datetime.fromisoformat(neueste["zeit"])
        except ValueError:
            aktuell = True
    return {"status": status, "nachricht": z["message"] or "", "anlass": anlass,
            "zeit": zeit.isoformat(timespec="seconds") if zeit else "", "aktuell": aktuell}


# ── Wiederherstellen ────────────────────────────────────────────────

def vormerken(db, name: str) -> dict:
    """Merkt eine Sicherung zum Einspielen beim naechsten Start vor —
    nachdem der aktuelle Stand selbst gesichert ist."""
    if not _NAME.match(name or "") or not (ordner(db) / name).is_file():
        return {"status": "fehler", "fehler": "Diese Sicherung gibt es nicht."}
    vorher = sichern(db, anlass="vor_wiederherstellen")
    if vorher["status"] != "gesichert":
        return {"status": "fehler",
                "fehler": "Der aktuelle Stand ließ sich nicht sichern — "
                          "ohne diese Sicherung wird nichts vorgemerkt. "
                          + (vorher.get("fehler") or "")}
    (Path(db.db_path).parent / VORMERKUNG).write_text(name, encoding="utf-8")
    return {"status": "vorgemerkt", "name": name, "aktueller_stand": vorher["name"]}


def vormerkung(db) -> str | None:
    p = Path(db.db_path).parent / VORMERKUNG
    try:
        return p.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def vormerkung_aufheben(db) -> bool:
    p = Path(db.db_path).parent / VORMERKUNG
    try:
        p.unlink()
        return True
    except FileNotFoundError:
        return False


#: Unter Windows sperrt das Betriebssystem die offene Datenbank selbst.
_IST_POSIX = os.name == "posix"

#: So lange gilt ein Heartbeat als Lebenszeichen (er wird alle 30 s geschrieben).
HEARTBEAT_FRISCH_SEK = 90


def anderer_prozess_aktiv(basis: Path) -> int | None:
    """Die Prozess-ID eines ANDEREN PBP-Prozesses, der die Datenbank gerade
    benutzt — oder None.

    Grundlage ist der Heartbeat des MCP-Servers (`mcp_heartbeat.json`, alle
    30 s). Geprueft wird nur unter POSIX: dort laesst sich eine offene
    Datenbank ohne Fehler loeschen und ueberschreiben, und der laufende
    Prozess schriebe danach in eine ausgetauschte Datei. Unter Windows
    sperrt das Betriebssystem die Datei, das Loeschen scheitert, und die
    Vormerkung wartet von selbst — `os.kill(pid, 0)` wuerde dort den
    Prozess beenden statt ihn zu pruefen."""
    if not _IST_POSIX:
        return None
    try:
        from ..heartbeat import _HEARTBEAT_FILE
        daten = json.loads((Path(basis) / _HEARTBEAT_FILE).read_text(encoding="utf-8"))
        pid = int(daten.get("pid") or 0)
        zeit = datetime.fromisoformat(str(daten.get("last_heartbeat")))
    except (OSError, ValueError, TypeError):
        return None
    if not pid or pid == os.getpid():
        return None
    alter = (datetime.now(timezone.utc) - zeit).total_seconds()
    if alter > HEARTBEAT_FRISCH_SEK:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        return pid  # lebt, gehoert nur einem anderen Nutzer
    except OSError:
        return None
    return pid


def vorgemerkt_einspielen(db_path: Path) -> dict | None:
    """Beim Start, BEVOR die Datenbank geoeffnet wird. Ohne Vormerkung None.

    Benutzt ein anderer PBP-Prozess die Datenbank noch (Claude Desktop
    laeuft weiter, nur das Dashboard wurde neu gestartet), wird NICHT
    eingespielt: die Vormerkung bleibt fuer den naechsten Start."""
    db_path = Path(db_path)
    basis = db_path.parent
    marke = basis / VORMERKUNG
    if not marke.exists():
        return None
    fremd = anderer_prozess_aktiv(basis)
    if fremd:
        logger.warning("Sicherung nicht eingespielt: PBP-Prozess %s benutzt die "
                       "Datenbank noch (Claude Desktop). Vormerkung bleibt.", fremd)
        return {"status": "wartet", "pid": fremd}
    name = marke.read_text(encoding="utf-8").strip()
    quelle = basis / ORDNER / name
    if not _NAME.match(name) or not quelle.is_file():
        marke.unlink()
        logger.warning("Vorgemerkte Sicherung %s fehlt — nichts eingespielt.", name)
        return {"status": "fehlt", "name": name}
    # v1.8.5 (#1350): erst in eine Nebendatei kopieren, dann tauschen. Scheitert
    # das Kopieren, ist die Datenbank unberuehrt; und die Vormerkung wird
    # geloescht, SOBALD die Datenbank getauscht ist. Vorher blieb sie stehen,
    # wenn der zweite Teil (Dokumente) scheiterte, und jeder weitere Start
    # ueberschrieb die Datenbank erneut aus der Sicherung - alles, was dazwischen
    # eingetragen wurde, war weg.
    zwischen = db_path.with_name(db_path.name + ".einspielen")
    try:
        shutil.copy2(quelle, zwischen)
    except OSError as exc:
        _loeschen_still(zwischen)
        marke.unlink(missing_ok=True)  # kein zweiter Versuch, der dasselbe tut
        return _einspielen_melden(basis, "gescheitert", name, False,
                                  f"Die Sicherung ließ sich nicht kopieren ({exc}). "
                                  "Deine Daten sind unverändert.")
    # Die WAL-Dateien des alten Stands muessen weg, sonst mischt SQLite
    # beide Staende (A27/#768).
    try:
        for rest in (db_path.with_name(db_path.name + "-wal"),
                     db_path.with_name(db_path.name + "-shm")):
            try:
                rest.unlink()
            except FileNotFoundError:
                pass
        os.replace(zwischen, db_path)
    except PermissionError:
        # Windows sperrt die offene Datenbank: die Vormerkung wartet von selbst.
        _loeschen_still(zwischen)
        logger.warning("Sicherung nicht eingespielt: Datenbank ist in Benutzung. Vormerkung bleibt.")
        return {"status": "wartet", "pid": None}
    marke.unlink(missing_ok=True)
    dokumente, hinweis = True, ""
    zip_datei = _dokumente_zip(quelle)
    if zip_datei.exists():
        try:
            _dokumente_einspielen(zip_datei, basis / "dokumente")
        except Exception as exc:  # noqa: BLE001 - die Datenbank ist schon getauscht
            dokumente = False
            hinweis = (f"Die Dokumente konnten nicht eingespielt werden ({exc}). Die "
                       "Datenbank ist eingespielt, deine bisherigen Dokumente sind "
                       "unverändert. Spiel die Sicherung bei Bedarf noch einmal ein.")
            logger.warning("Dokumente der Sicherung nicht eingespielt: %s", exc)
    elif (basis / "dokumente").is_dir() and any((basis / "dokumente").rglob("*")):
        dokumente = False
        hinweis = ("Diese Sicherung enthält nur die Datenbank, keine Dokumente. "
                   "Deine Dokumente im Ordner bleiben unverändert.")
    ergebnis = "ganz" if dokumente else "teilweise"
    logger.info("Sicherung %s eingespielt (Dokumente: %s).", name, dokumente)
    return _einspielen_melden(basis, ergebnis, name, dokumente, hinweis)


EINSPIELEN_ERGEBNIS = "einspielen_ergebnis.json"


def _loeschen_still(pfad: Path) -> None:
    try:
        if pfad.is_dir():
            shutil.rmtree(pfad, ignore_errors=True)
        else:
            pfad.unlink()
    except OSError:
        pass


def _dokumente_einspielen(zip_datei: Path, ziel: Path) -> None:
    """Entpackt in einen Nebenordner und tauscht erst danach (#1350). Scheitert
    das Entpacken, bleibt der bisherige Dokumentenordner, wie er war."""
    neu = ziel.with_name(ziel.name + ".einspielen")
    alt = ziel.with_name(ziel.name + ".alt")
    for rest in (neu, alt):
        _loeschen_still(rest)
    neu.mkdir(parents=True)
    try:
        with zipfile.ZipFile(zip_datei) as z:
            for info in z.infolist():
                pfad = (neu / info.filename).resolve()
                if neu.resolve() not in pfad.parents and pfad != neu.resolve():
                    continue  # kein Pfad ausserhalb des Ordners (Zip-Slip)
                z.extract(info, neu)
    except Exception:
        _loeschen_still(neu)
        raise
    if ziel.exists():
        os.replace(ziel, alt)
    try:
        os.replace(neu, ziel)
    except OSError:
        if alt.exists():
            os.replace(alt, ziel)  # der bisherige Stand kommt zurueck
        _loeschen_still(neu)
        raise
    _loeschen_still(alt)  # der vorherige Stand liegt als Sicherung vor


def _einspielen_melden(basis: Path, ergebnis: str, name: str, dokumente: bool, hinweis: str) -> dict:
    """Haelt den Ausgang fest, damit das Dashboard ihn nennen kann (ganz,
    teilweise, gescheitert) - beim Start sieht niemand ins Protokoll."""
    erg = {"status": "gescheitert" if ergebnis == "gescheitert" else "eingespielt",
           "ergebnis": ergebnis, "name": name, "dokumente": dokumente, "hinweis": hinweis,
           "zeit": datetime.now().isoformat(timespec="seconds")}
    try:
        (basis / EINSPIELEN_ERGEBNIS).write_text(
            json.dumps(erg, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:  # pragma: no cover
        logger.warning("Ausgang des Einspielens nicht festgehalten: %s", exc)
    return erg


def einspielen_ergebnis(db) -> dict | None:
    """Der Ausgang des letzten Einspielens, bis der Mensch ihn gesehen hat."""
    try:
        return json.loads((Path(db.db_path).parent / EINSPIELEN_ERGEBNIS).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def einspielen_ergebnis_quittieren(db) -> bool:
    try:
        (Path(db.db_path).parent / EINSPIELEN_ERGEBNIS).unlink()
        return True
    except FileNotFoundError:
        return False
