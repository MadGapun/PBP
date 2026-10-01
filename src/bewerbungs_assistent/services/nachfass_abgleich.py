"""Eine Nachfrage, die sich durch Kontakt erledigt hat, ist hinfällig (#1123).

Der Fall (29.09.2026): Eine automatische Erinnerung „nachfassen, 21 Tage
nach der letzten Aktivität“ blieb offen, obwohl die Bewerbung längst im
Interview war und ein Termin feststand. PBP erkannte den Zustand richtig
(`ueberholt`), schloss die Aufgabe aber nicht — sie stand weiter unter
„Überfällig“ und im roten Zähler. Die Regel dazu stand seit #945 im
Issue („wird automatisch hinfällig“) und wurde nur beim LESEN markiert.

Nutzerentscheidung (29.09.2026): automatisch hinfällig, und zwar nach
JEDER Kommunikation mit dem Arbeitgeber, die PBP gemeldet wird — nicht
nur beim Interview. Wer heute mit dem Arbeitgeber gesprochen hat und das
meldet, muss morgen nicht nach dem Sachstand fragen.

Was als gemeldeter Kontakt zählt
--------------------------------

* ein Statuswechsel, mit dem der Arbeitgeber geantwortet hat
  (`KONTAKT_STATUS`),
* ein Termin, der angelegt oder verschoben wird,
* eine Gesprächsnotiz (`bewerbung_notiz`),
* eine E-Mail, die einer Bewerbung zugeordnet wird.

Was NICHT schließt
------------------

* Nur Erinnerungen vom Typ `nachfass`. Eine Danke-Mail oder eine
  Interview-Erinnerung ist keine Nachfrage nach dem Sachstand.
* Nur Erinnerungen, die VOR dem Kontakt angelegt wurden. Wer nach dem
  Gespräch bewusst „in zwei Wochen nachfragen“ einplant, will genau diese
  Erinnerung behalten.

Der Eintrag im Verlauf ist eine Notiz an der Bewerbung; die Erinnerung
selbst bleibt als `hinfaellig` mit Zeitstempel erhalten (nicht gelöscht).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from .nachfass_text import UEBERHOLTE_STATUS, ist_ueberholt

logger = logging.getLogger(__name__)

#: Status, mit denen der Arbeitgeber geantwortet hat. `beworben` gehört
#: nicht dazu: das ist der eigene Versand.
KONTAKT_STATUS = frozenset({"eingangsbestaetigung"}) | UEBERHOLTE_STATUS


def _jetzt() -> str:
    # UTC wie `created_at` (database._now): ein Vergleich Ortszeit gegen
    # UTC hätte eine Erinnerung, die eine Stunde NACH dem Kontakt angelegt
    # wurde, als älter gewertet und geschlossen.
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _offene(db, app_id: str) -> list[dict]:
    zeilen = db.connect().execute(
        "SELECT id, scheduled_date, created_at FROM follow_ups "
        "WHERE application_id=? AND status='geplant' "
        "AND COALESCE(follow_up_type, 'nachfass')='nachfass'",
        (app_id,)).fetchall()
    return [dict(z) for z in zeilen]


def schliessen(db, app_id: str, anlass: str, *, wann: str | None = None,
               notiz: bool = True) -> list[dict]:
    """Schließt offene Nachfrage-Erinnerungen dieser Bewerbung.

    Args:
        anlass: Worum es ging — landet im Verlauf der Bewerbung.
        wann: Zeitpunkt des Kontakts (ISO). Erinnerungen, die danach
            angelegt wurden, bleiben offen. Vorgabe: jetzt.
        notiz: Verlaufseintrag schreiben.

    Returns:
        Die geschlossenen Erinnerungen als `{id, geplant_fuer}`.
    """
    if not app_id:
        return []
    # Nur ein ISO-Zeitpunkt lässt sich mit `created_at` vergleichen; alles
    # andere (leer, "Tue, 29 Sep ...") gilt als "jetzt".
    wann = str(wann) if re.match(r"^\d{4}-\d{2}-\d{2}", str(wann or "")) else _jetzt()
    wann = wann[:19]
    geschlossen = []
    conn = db.connect()
    for fu in _offene(db, app_id):
        angelegt = str(fu.get("created_at") or "")[:19]
        if angelegt and angelegt > wann:
            continue
        conn.execute(
            "UPDATE follow_ups SET status='hinfaellig', completed_at=? WHERE id=?",
            (_jetzt(), fu["id"]))
        geschlossen.append({"id": fu["id"],
                            "geplant_fuer": str(fu.get("scheduled_date") or "")[:10]})
    if not geschlossen:
        return []
    conn.commit()
    if notiz:
        try:
            db.add_application_note(
                app_id, f"Nachfrage erledigt ({anlass}) — automatisch "
                        f"{len(geschlossen)} Erinnerung(en) auf hinfällig gesetzt.")
        except Exception as exc:  # noqa: BLE001 — der Verlauf darf nie das Schließen kippen
            logger.debug("Verlaufseintrag Nachfrage (#1123): %s", exc)
    return geschlossen


def kontakt_gemeldet(db, app_id: str, anlass: str,
                     wann: str | None = None) -> list[dict]:
    """Ein Kontakt mit dem Arbeitgeber wurde gemeldet."""
    return schliessen(db, app_id, anlass, wann=wann)


def ueberholte_schliessen(db) -> list[dict]:
    """Schließt Erinnerungen, deren Bewerbung schon weiter ist (#945, #1123).

    Zustandsbasiert und idempotent. Das Urteil bleibt
    `nachfass_text.ist_ueberholt` — eine Frage, eine Funktion; hier wird
    nur gehandelt. Aufrufer sind die Dashboard-Automatik
    (`_run_followup_ueberholt`) und der Start. NICHT das Lesen der
    Aufgabenliste: „eine Liste abzurufen darf nichts verändern“ (#945).

    Die Automatik läuft höchstens stündlich und nur bei offenem Dashboard;
    wer über Claude arbeitet, hat sie nie laufen. Deshalb schließen die
    Ereignisse (`kontakt_gemeldet`) sofort, und dies hier ist das Netz
    darunter für Wege ohne Hook (Import, direkter Aufruf).

    Geschlossen wird über `schliessen`, also nur Erinnerungen vom Typ
    `nachfass`: die alte Fassung schloss auch Interview-Erinnerungen und
    Danke-Mails, sobald der Stand „Interview“ hieß.

    Returns:
        Je geschlossener Erinnerung `{id, geplant_fuer, firma, grund}`.
    """
    von_bewerbung: dict[str, dict] = {}
    for fu in db.get_pending_follow_ups() or []:
        app_id = fu.get("application_id") or ""
        app = db.get_application(app_id) or {}
        if not app:
            continue
        weg, grund = ist_ueberholt(fu, app)
        if weg:
            von_bewerbung.setdefault(
                app_id, {"grund": grund, "firma": app.get("company") or ""})
    geschlossen = []
    for app_id, info in von_bewerbung.items():
        for g in schliessen(db, app_id, info["grund"], wann="9999-12-31T00:00:00"):
            geschlossen.append({**g, "firma": info["firma"], "grund": info["grund"]})
    return geschlossen
