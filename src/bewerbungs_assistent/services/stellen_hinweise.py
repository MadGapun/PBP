"""Hinweise auf Stellen, die noch keine Stellen sind (#1184 d, B76).

## Warum es das gibt

Eine Google-Jobs-Benachrichtigung nennt je Treffer nur Titel, Firma, Ort, Ursprungsportal und Datum. Alle Links laufen ueber
einen Umleiter auf eine allgemeine Google-Suche (#1120). Dieselbe Anzeige kommt in mehreren Mails mit verschiedenen Orten, und
ein Ort passte nicht zur Originalanzeige (Mail: Hamburg, Anzeige: Koeln). Eine Stelle, die allein aus so einer Mail entsteht,
ist deshalb eine Behauptung ohne Beleg - und sie stand bis 1.8.0-rc.x in der Trefferliste, bewertet, sortiert, neben den
echten.

Ab 1.8.0 entsteht aus einer Alert-Mail **keine Stelle** mehr. Jeder Treffer wird ein *Hinweis*: Titel, Firma, Ort, Portal,
ohne Bewertung, ohne Platz in der Liste der Stellen. Wer sich dafuer interessiert, sucht das Original beim Arbeitgeber
(`google_angaben.original_suchen` bereitet die Suche vor) und legt die Stelle mit `stelle_manuell_anlegen` an - dann, mit
URL und Text, als echte Stelle. Der Hinweis wird dabei von selbst als erledigt vermerkt.

## Was bewusst so ist

* **Eine eigene Liste, keine Stellen mit Merker.** Ein Merker an Stellen haette jede Auswertung (Statistik, Score,
  Sortierung, Aussortieren) einzeln lernen muessen, ihn zu ueberspringen - dieselbe Bauform wie bei `unbewertet` (#756).
* **Dubletten werden zusammengefasst**, nicht vervielfacht: gleiche Firma und gleicher Titel sind EIN Hinweis; die Orte
  aus mehreren Mails stehen nebeneinander (der Widerspruch ist selbst eine Auskunft), `anzahl_mails` zaehlt mit.
* **Was schon eine Stelle ist, wird nicht noch einmal gemerkt** (aktiv oder aussortiert): der Hinweis steht dann gleich als
  `angelegt` da.
* **Die Tabelle entsteht erst bei Bedarf** (Safety-Net statt Schema-Bump, wie `job_sources` und `job_tombstones`).

Abgrenzung: `google_alert` liest die Mail, `newsletter_service` ruft diesen Dienst auf, `google_angaben` entscheidet, wann
eine Google-Stelle unter Vorbehalt steht und liefert die Suchhilfe; hier steht nur die Liste der Hinweise.
"""
from __future__ import annotations

import logging
from datetime import datetime

logger = logging.getLogger(__name__)

STATUS = ("offen", "angelegt", "verworfen")
#: Mehr als so viele Orte je Hinweis sind kein Erkenntnisgewinn mehr.
MAX_ORTE = 6


def tabelle_anlegen(conn) -> None:
    """Safety-Net statt Schema-Bump - additiv, wie `job_tombstones` (#1084)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS stellen_hinweise (
            id TEXT PRIMARY KEY,
            profile_id TEXT,
            quelle TEXT DEFAULT 'google_alert',
            titel TEXT NOT NULL,
            firma TEXT DEFAULT '',
            ort TEXT DEFAULT '',
            portal TEXT DEFAULT '',
            suchanfrage TEXT DEFAULT '',
            vertragsart TEXT DEFAULT '',
            veroeffentlicht_am TEXT DEFAULT '',
            weiterverbreiter INTEGER DEFAULT 0,
            google_link TEXT DEFAULT '',
            status TEXT DEFAULT 'offen',
            job_hash TEXT DEFAULT '',
            anzahl_mails INTEGER DEFAULT 1,
            erstellt_am TEXT,
            aktualisiert_am TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_stellen_hinweise_status ON stellen_hinweise(profile_id, status)")
    conn.commit()


def _norm(text) -> str:
    import re
    return re.sub(r"\s+", " ", str(text or "").strip().lower())


def _kennung(profil_id, firma, titel) -> str:
    from ..job_scraper import stelle_hash
    return stelle_hash("hinweis", f"{profil_id or ''}|{_norm(firma)}|{_norm(titel)}")[:32]


def _orte(vorhanden: str, neu: str) -> str:
    teile = [t.strip() for t in str(vorhanden or "").split(";") if t.strip()]
    for kandidat in (str(neu or "").strip(),):
        if kandidat and _norm(kandidat) not in {_norm(t) for t in teile}:
            teile.append(kandidat)
    return "; ".join(teile[:MAX_ORTE])


def _bereits_stelle(db, firma, titel) -> str:
    """Der Hash einer Stelle gleicher Firma und gleichen Titels (aktiv oder aussortiert) - sonst leer."""
    try:
        pid = db.get_active_profile_id()
        zeile = db.connect().execute(
            "SELECT hash FROM jobs WHERE (profile_id=? OR profile_id IS NULL) "
            "AND LOWER(TRIM(company))=? AND LOWER(TRIM(title))=? LIMIT 1",
            (pid, _norm(firma), _norm(titel))).fetchone()
        return zeile[0] if zeile else ""
    except Exception as exc:  # pragma: no cover - nie den Import kippen
        logger.debug("Hinweis: Bestandspruefung fehlgeschlagen: %s", exc)
        return ""


def merken(db, treffer: list[dict], *, suchanfrage: str = "", quelle: str = "google_alert") -> dict:
    """Haelt die Treffer einer Alert-Mail als Hinweise fest. Rueckgabe: Zaehler.

    `treffer` sind die Eintraege aus `google_alert.parse_alert`. Es entsteht KEINE Stelle.
    """
    conn = db.connect()
    tabelle_anlegen(conn)
    pid = db.get_active_profile_id()
    jetzt = datetime.now().isoformat(timespec="seconds")
    neu = bekannt = schon_stelle = 0
    for e in treffer:
        titel = str(e.get("titel") or "").strip()
        firma = str(e.get("firma") or "").strip()
        if not titel:
            continue
        hid = _kennung(pid, firma, titel)
        zeile = conn.execute("SELECT * FROM stellen_hinweise WHERE id=?", (hid,)).fetchone()
        if zeile:
            conn.execute(
                "UPDATE stellen_hinweise SET ort=?, anzahl_mails=COALESCE(anzahl_mails,1)+1, aktualisiert_am=? WHERE id=?",
                (_orte(zeile["ort"], e.get("ort")), jetzt, hid))
            bekannt += 1
            continue
        stelle = _bereits_stelle(db, firma, titel)
        conn.execute(
            "INSERT INTO stellen_hinweise (id, profile_id, quelle, titel, firma, ort, portal, suchanfrage, vertragsart, "
            "veroeffentlicht_am, weiterverbreiter, google_link, status, job_hash, anzahl_mails, erstellt_am, aktualisiert_am) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (hid, pid, quelle, titel, firma, str(e.get("ort") or "").strip(), str(e.get("portal") or "").strip(),
             suchanfrage or "", str(e.get("vertragsart") or ""), str(e.get("veroeffentlicht_am") or ""),
             1 if e.get("weiterverbreiter") else 0, str(e.get("google_link") or ""),
             "angelegt" if stelle else "offen", stelle, 1, jetzt, jetzt))
        if stelle:
            schon_stelle += 1
        else:
            neu += 1
    conn.commit()
    return {"neu": neu, "bekannt": bekannt, "schon_stelle": schon_stelle}


def _als_dict(z) -> dict:
    d = dict(z)
    d["weiterverbreiter"] = bool(d.get("weiterverbreiter"))
    return d


def liste(db, status: str = "offen", limit: int = 100) -> list[dict]:
    """Die Hinweise des aktiven Profils, neueste zuerst. `status`: offen | angelegt | verworfen | alle."""
    conn = db.connect()
    tabelle_anlegen(conn)
    pid = db.get_active_profile_id()
    sql = "SELECT * FROM stellen_hinweise WHERE (profile_id=? OR profile_id IS NULL)"
    params: list = [pid]
    if status in STATUS:
        sql += " AND status=?"
        params.append(status)
    sql += " ORDER BY aktualisiert_am DESC, erstellt_am DESC LIMIT ?"
    params.append(max(1, min(int(limit or 100), 500)))
    return [_als_dict(z) for z in conn.execute(sql, params).fetchall()]


def zaehlen(db) -> dict:
    """Wie viele Hinweise in welchem Stand? Ohne Tabelle: alles null (es wird nichts angelegt)."""
    try:
        conn = db.connect()
        pid = db.get_active_profile_id()
        zeilen = conn.execute(
            "SELECT status, COUNT(*) AS n FROM stellen_hinweise WHERE (profile_id=? OR profile_id IS NULL) GROUP BY status",
            (pid,)).fetchall()
    except Exception:  # Tabelle noch nicht da
        return {s: 0 for s in STATUS}
    ergebnis = {s: 0 for s in STATUS}
    for z in zeilen:
        ergebnis[z["status"]] = z["n"]
    return ergebnis


def verwerfen(db, hinweis_id: str) -> bool:
    conn = db.connect()
    tabelle_anlegen(conn)
    cur = conn.execute(
        "UPDATE stellen_hinweise SET status='verworfen', aktualisiert_am=? WHERE id=? AND status='offen'",
        (datetime.now().isoformat(timespec="seconds"), hinweis_id))
    conn.commit()
    return cur.rowcount > 0


def wiederherstellen(db, hinweis_id: str) -> bool:
    conn = db.connect()
    tabelle_anlegen(conn)
    cur = conn.execute(
        "UPDATE stellen_hinweise SET status='offen', aktualisiert_am=? WHERE id=? AND status='verworfen'",
        (datetime.now().isoformat(timespec="seconds"), hinweis_id))
    conn.commit()
    return cur.rowcount > 0


def als_angelegt(db, firma, titel, job_hash: str) -> int:
    """Eine Stelle gleicher Firma und gleichen Titels ist angelegt: der Hinweis ist erledigt. Rueckgabe: wie viele."""
    try:
        conn = db.connect()
        zeile = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='stellen_hinweise'").fetchone()
        if not zeile:
            return 0
        pid = db.get_active_profile_id()
        cur = conn.execute(
            "UPDATE stellen_hinweise SET status='angelegt', job_hash=?, aktualisiert_am=? "
            "WHERE (profile_id=? OR profile_id IS NULL) AND status!='angelegt' "
            "AND LOWER(TRIM(firma))=? AND LOWER(TRIM(titel))=?",
            (job_hash, datetime.now().isoformat(timespec="seconds"), pid, _norm(firma), _norm(titel)))
        conn.commit()
        return cur.rowcount
    except Exception as exc:  # pragma: no cover - nie die Anlage kippen
        logger.debug("Hinweis nicht als angelegt vermerkt: %s", exc)
        return 0
