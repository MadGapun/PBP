"""Kleines sofort loeschen, mit Rueckweg (G67, #1087 H5).

Die Regel fuer das Loeschen im Dashboard hat zwei Teile: Folgenreiches
(Bewerbung, Kontakt, Dokument, Profil) fragt vorher in einem Dialog;
Kleines (Notiz, Aufgabe, Referenz-Verknuepfung) geht sofort weg und der
Toast bietet "Rueckgaengig" an. Neu anlegen haette Datum und Kennung
verloren — der Lösch-Endpunkt liefert deshalb die Zeile mit, und
`wiederherstellen` legt genau diese Zeile wieder an.

Nur fuer die Tabellen in `ARTEN`; eine Zeile wird nur mit den Spalten
angelegt, die die Tabelle wirklich hat, und nie ueber eine bestehende.
"""
from __future__ import annotations

ARTEN = {
    "notiz": "application_events",
    "aufgabe": "tasks",
    "referenz": "contact_references",
}


def aufheben(db, art: str, schluessel) -> dict | None:
    """Die Zeile vor dem Loeschen lesen."""
    tabelle = ARTEN.get(art)
    if not tabelle:
        return None
    zeile = db.connect().execute(
        f"SELECT * FROM {tabelle} WHERE id=?", (schluessel,)).fetchone()
    return dict(zeile) if zeile else None


def wiederherstellen(db, art: str, zeile: dict) -> bool:
    tabelle = ARTEN.get(art)
    if not tabelle or not isinstance(zeile, dict) or "id" not in zeile:
        return False
    conn = db.connect()
    spalten = [r["name"] for r in conn.execute(f"PRAGMA table_info({tabelle})").fetchall()]
    daten = {k: v for k, v in zeile.items() if k in spalten}
    if art == "notiz" and daten.get("status") != "notiz":
        return False
    if "profile_id" in spalten and daten.get("profile_id") not in (None, "", db.get_active_profile_id()):
        return False
    if conn.execute(f"SELECT 1 FROM {tabelle} WHERE id=?", (daten["id"],)).fetchone():
        return False
    namen = ", ".join(daten)
    platz = ", ".join("?" * len(daten))
    conn.execute(f"INSERT INTO {tabelle} ({namen}) VALUES ({platz})", tuple(daten.values()))
    conn.commit()
    return True
