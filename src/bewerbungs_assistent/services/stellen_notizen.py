"""Eigene Notizen an einer Stelle, getrennt vom Anzeigentext (#1316).

## Warum es das gibt

Zu einer Stelle ohne Bewerbung gab es keinen Ort fuer eigene Gedanken. Der einzige Weg war die Konvention aus #603:
Notizen hinter eine Zeile `---` an die Beschreibung haengen. Das mischte Original und Notiz wieder in einem Feld (genau
das, was #588 fuer Bewerbungen beendet hat), verlangte fuer jeden Nachtrag den ganzen Anzeigentext, liess keinen Verlauf
und keinen Verfasser erkennen, und das Nachladen der Beschreibung konnte die Notizen ueberschreiben.

Hier steht jede Notiz als eigener Eintrag: Zeitpunkt, Herkunft (`mensch`, `ki`, `migriert`) und Freitext.

## Was bewusst so ist

* **Notizen sind nie Anzeigentext.** Sie liegen in einer eigenen Tabelle; Scoring, `fit_analyse`-Bewertung,
  Wiedergaenger-Erkennung, KI-Aussortierung und Dokumentexport lesen `jobs.description` und sehen sie nie.
* **Beim Anlegen einer Bewerbung gehen sie mit** - als Timeline-Eintraege der Bewerbung mit Herkunftsvermerk
  (`in_bewerbung_uebernehmen`, aufgerufen von `bewerbung_lebenszyklus.anlegen`). Die Eintraege an der Stelle bleiben.
* **Alte `---`-Notizen werden nie still umgeschrieben.** `notizteil_erkennen` findet den Teil mit derselben Grenze, die
  das Scoring seit #603 benutzt (`job_scraper._PBP_NOTES_RE`); uebernommen wird nur auf ausdrueckliche Bitte und je
  Stelle (`aus_beschreibung_uebernehmen`). Die Beschreibung behaelt danach genau den Teil, den das Scoring schon bisher
  gewertet hat - die Punkte bleiben deshalb dieselben.
* **`job_hash` traegt die gespeicherte Form** (`{profil}:{hash}`), dazu `profile_id`. Damit finden Zusammenfuehren,
  Entfernen nach Quelle und Heilung die Tabelle ueber ihre `job_hash`-Spalte von selbst; Loeschbereich `stellen` (#1025).

Abgrenzung: `research_notes` (Tabelle) haelt Recherche-Ergebnisse (`firmen_recherche`, `recherche_speichern`, Kategorie
je Eintrag) an Bewerbung oder Stelle; `jobs.research_notes` (Spalte) ist der Altbestand davon (#956). Eine Recherche ist
ein Befund ueber die Firma, eine Notiz ist ein Gedanke zu dieser Stelle (Rechnung, offene Fragen, Abwaegung).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

TABELLE = "job_notes"
HERKUNFT = ("mensch", "ki", "migriert")
#: Wie die Herkunft dem Menschen gezeigt wird.
HERKUNFT_TEXT = {"mensch": "von dir", "ki": "von Claude", "migriert": "aus der Beschreibung übernommen"}
#: Eine Notiz ist Freitext, aber kein zweiter Anzeigentext.
MAX_ZEICHEN = 20_000


def tabelle_anlegen(conn) -> None:
    """Safety-Net in `Database.initialize()` statt Schema-Bump (additiv, #1316)."""
    conn.execute(f"""
        CREATE TABLE IF NOT EXISTS {TABELLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL DEFAULT '',
            job_hash TEXT NOT NULL,
            herkunft TEXT NOT NULL DEFAULT 'mensch',
            text TEXT NOT NULL,
            erstellt_am TEXT NOT NULL,
            geaendert_am TEXT
        )
    """)
    conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{TABELLE}_job ON {TABELLE}(job_hash)")
    conn.commit()


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stelle(db, job_hash):
    """Die Stelle des aktiven Profils als (gespeicherter Hash, Stelle) - oder (None, None)."""
    from .typed_ids import strip_prefix
    h = strip_prefix(str(job_hash or "").strip())
    if not h:
        return None, None
    job = db.get_job(h)
    if not job:
        return None, None
    return db.resolve_job_hash(h) or h, job


def _zeile(z) -> dict:
    d = dict(z)
    d["von"] = HERKUNFT_TEXT.get(d.get("herkunft"), d.get("herkunft") or "")
    return d


def _text_pruefen(text) -> tuple[str, str | None]:
    t = str(text or "").strip()
    if not t:
        return "", "Die Notiz ist leer."
    if len(t) > MAX_ZEICHEN:
        return "", f"Die Notiz ist zu lang ({len(t)} Zeichen, höchstens {MAX_ZEICHEN})."
    return t, None


def anlegen(db, job_hash, text, herkunft: str = "mensch") -> dict:
    """Haengt eine Notiz an die Stelle. `{'ok': True, 'notiz': {...}}` oder `{'ok': False, 'grund', 'fehler'}`."""
    if herkunft not in HERKUNFT:
        return {"ok": False, "grund": "herkunft", "fehler": f"Unbekannte Herkunft „{herkunft}“."}
    t, fehler = _text_pruefen(text)
    if fehler:
        return {"ok": False, "grund": "text", "fehler": fehler}
    gespeichert, _job = _stelle(db, job_hash)
    if not gespeichert:
        return {"ok": False, "grund": "nicht_gefunden", "fehler": "Stelle nicht gefunden."}
    conn = db.connect()
    tabelle_anlegen(conn)
    cur = conn.execute(
        f"INSERT INTO {TABELLE} (profile_id, job_hash, herkunft, text, erstellt_am) VALUES (?, ?, ?, ?, ?)",
        (db.get_active_profile_id() or "", gespeichert, herkunft, t, _jetzt()))
    conn.commit()
    zeile = conn.execute(f"SELECT * FROM {TABELLE} WHERE id=?", (cur.lastrowid,)).fetchone()
    return {"ok": True, "notiz": _zeile(zeile)}


def liste(db, job_hash) -> list[dict]:
    """Alle Notizen einer Stelle des aktiven Profils, aelteste zuerst."""
    gespeichert, _job = _stelle(db, job_hash)
    if not gespeichert:
        return []
    conn = db.connect()
    tabelle_anlegen(conn)
    return [_zeile(z) for z in conn.execute(
        f"SELECT * FROM {TABELLE} WHERE job_hash=? AND profile_id=? ORDER BY erstellt_am, id",
        (gespeichert, db.get_active_profile_id() or ""))]


def _eintrag(db, job_hash, notiz_id):
    gespeichert, _job = _stelle(db, job_hash)
    if not gespeichert:
        return None, None
    try:
        nid = int(notiz_id)
    except (TypeError, ValueError):
        return gespeichert, None
    conn = db.connect()
    tabelle_anlegen(conn)
    z = conn.execute(f"SELECT * FROM {TABELLE} WHERE id=? AND job_hash=? AND profile_id=?",
                     (nid, gespeichert, db.get_active_profile_id() or "")).fetchone()
    return gespeichert, z


def aendern(db, job_hash, notiz_id, text) -> dict:
    """Aendert den Text einer Notiz. Die Herkunft bleibt, `geaendert_am` wird gesetzt."""
    t, fehler = _text_pruefen(text)
    if fehler:
        return {"ok": False, "grund": "text", "fehler": fehler}
    _g, z = _eintrag(db, job_hash, notiz_id)
    if z is None:
        return {"ok": False, "grund": "nicht_gefunden", "fehler": "Notiz nicht gefunden."}
    conn = db.connect()
    conn.execute(f"UPDATE {TABELLE} SET text=?, geaendert_am=? WHERE id=?", (t, _jetzt(), z["id"]))
    conn.commit()
    return {"ok": True, "notiz": _zeile(conn.execute(f"SELECT * FROM {TABELLE} WHERE id=?", (z["id"],)).fetchone())}


def loeschen(db, job_hash, notiz_id) -> dict:
    _g, z = _eintrag(db, job_hash, notiz_id)
    if z is None:
        return {"ok": False, "grund": "nicht_gefunden", "fehler": "Notiz nicht gefunden."}
    conn = db.connect()
    conn.execute(f"DELETE FROM {TABELLE} WHERE id=?", (z["id"],))
    conn.commit()
    return {"ok": True, "geloescht": _zeile(z)}


def anzahl_je_stelle(db) -> dict:
    """{oeffentlicher Hash: Zahl der Notizen} fuer das aktive Profil - EINE Abfrage fuer eine ganze Liste."""
    pid = db.get_active_profile_id() or ""
    conn = db.connect()
    tabelle_anlegen(conn)
    aus: dict = {}
    for z in conn.execute(f"SELECT job_hash, COUNT(*) AS n FROM {TABELLE} WHERE profile_id=? GROUP BY job_hash", (pid,)):
        aus[db._public_job_hash(z["job_hash"], pid)] = z["n"]
    return aus


def fuer_claude(eintraege) -> list[dict]:
    """Die Notizen in der Form, die Claude bekommt: kurz, mit Verfasser und Datum."""
    return [{"id": e["id"], "am": str(e.get("erstellt_am") or "")[:10], "von": e.get("von") or "", "text": e.get("text") or ""}
            for e in eintraege]


# ── Altbestand: Notizen hinter '---' in der Beschreibung ───────────────

def notizteil_erkennen(beschreibung) -> dict | None:
    """`{'anzeige': ..., 'notizen': ...}`, wenn die Beschreibung einen Notizteil traegt - sonst None.

    Die Grenze ist DIESELBE, an der das Scoring seit #603 abschneidet (eine Frage, eine Funktion): was davor steht,
    hat das Scoring schon bisher als Anzeige gewertet. Ohne Anzeigenteil oder ohne Notizteil gibt es nichts zu teilen."""
    from ..job_scraper import _PBP_NOTES_RE
    text = str(beschreibung or "")
    m = _PBP_NOTES_RE.search(text)
    if not m:
        return None
    anzeige = text[:m.start()].strip()
    rest = text[m.start():].strip()
    # Die Trennzeile selbst gehoert zu keinem der beiden Teile; eine Ueberschrift wie "## Analyse" schon.
    zeilen = rest.split("\n", 1)
    if zeilen[0].strip().strip("-") == "":
        rest = zeilen[1].strip() if len(zeilen) > 1 else ""
    if not anzeige or not rest:
        return None
    return {"anzeige": anzeige, "notizen": rest}


def aus_beschreibung_uebernehmen(db, job_hash, herkunft: str = "migriert") -> dict:
    """Verschiebt den Notizteil der Beschreibung in eine Notiz - nur auf ausdrueckliche Bitte, je Stelle.

    Erst die Notiz, dann die Beschreibung (ueber `stelle_aendern`, dem Weg des Bearbeiten-Dialogs). Scheitert das
    Kuerzen, wird die Notiz wieder entfernt: es gibt nie einen Zustand, in dem der Text an beiden Orten fehlt."""
    gespeichert, job = _stelle(db, job_hash)
    if not gespeichert:
        return {"ok": False, "grund": "nicht_gefunden", "fehler": "Stelle nicht gefunden."}
    teile = notizteil_erkennen(job.get("description"))
    if not teile:
        return {"ok": False, "grund": "kein_notizteil",
                "fehler": "In der Beschreibung steht kein Notizteil (keine Zeile „---“ mit Text dahinter)."}
    erg = anlegen(db, gespeichert, teile["notizen"], herkunft=herkunft)
    if not erg["ok"]:
        return erg
    from . import stelle_aendern
    geaendert = stelle_aendern.aendern(db, gespeichert, {"description": teile["anzeige"]})
    if not geaendert.get("ok"):
        loeschen(db, gespeichert, erg["notiz"]["id"])
        return {"ok": False, "grund": "beschreibung",
                "fehler": geaendert.get("fehler") or "Die Beschreibung ließ sich nicht kürzen; nichts geändert."}
    return {"ok": True, "notiz": erg["notiz"], "beschreibung_zeichen": len(teile["anzeige"])}


# ── Bewerbung aus der Stelle ───────────────────────────────────────────

def in_bewerbung_uebernehmen(db, app_id: str, job_hash) -> int:
    """Schreibt die Notizen der Stelle als Timeline-Eintraege in die neue Bewerbung. Liefert die Zahl."""
    eintraege = liste(db, job_hash)
    for e in eintraege:
        datum = str(e.get("erstellt_am") or "")[:10]
        try:
            datum = datetime.strptime(datum, "%Y-%m-%d").strftime("%d.%m.%Y")
        except ValueError:
            pass
        db.add_application_note(app_id, f"Notiz zur Stelle ({e['von']}, {datum}):\n{e['text']}")
    return len(eintraege)
