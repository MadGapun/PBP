"""beta.100 — #683: ueberfaellige Aufgaben (Faelligkeitsdatum + Dashboard-Warnung).

get_overdue_tasks() liefert offene Aufgaben, deren faellig_am vor heute liegt,
angereichert mit Bewerbungs-Titel/Firma fuer die Dashboard-Warnung.
"""
from __future__ import annotations

from datetime import datetime, timezone, timedelta


def _d(offset_days):
    return (datetime.now(timezone.utc) + timedelta(days=offset_days)).strftime("%Y-%m-%d")


def _setup(tmp_db):
    tmp_db.create_profile("T", "t@example.com")
    aid = tmp_db.add_application({"title": "PLM Consultant", "company": "Firma X"})
    return aid


def test_overdue_nur_vergangene_offene(tmp_db):
    aid = _setup(tmp_db)
    tmp_db.add_task({"application_id": aid, "titel": "Gestern faellig", "faellig_am": _d(-1)})
    tmp_db.add_task({"application_id": aid, "titel": "Heute", "faellig_am": _d(0)})
    tmp_db.add_task({"application_id": aid, "titel": "Morgen", "faellig_am": _d(1)})
    tmp_db.add_task({"application_id": aid, "titel": "Ohne Datum"})
    over = tmp_db.get_overdue_tasks()
    assert [t["titel"] for t in over] == ["Gestern faellig"]
    assert over[0]["bewerbung_titel"] == "PLM Consultant"
    assert over[0]["firma"] == "Firma X"
    assert over[0]["application_id"] == aid


def test_overdue_schliesst_erledigte_aus(tmp_db):
    aid = _setup(tmp_db)
    tid = tmp_db.add_task({"application_id": aid, "titel": "Alt + erledigt", "faellig_am": _d(-5)})
    conn = tmp_db.connect()
    conn.execute("UPDATE tasks SET status='erledigt' WHERE id=?", (tid,))
    conn.commit()
    assert tmp_db.get_overdue_tasks() == []


def test_overdue_sortiert_aelteste_zuerst(tmp_db):
    aid = _setup(tmp_db)
    tmp_db.add_task({"application_id": aid, "titel": "B vor 2 Tagen", "faellig_am": _d(-2)})
    tmp_db.add_task({"application_id": aid, "titel": "A vor 9 Tagen", "faellig_am": _d(-9)})
    over = tmp_db.get_overdue_tasks()
    assert [t["titel"] for t in over] == ["A vor 9 Tagen", "B vor 2 Tagen"]


def test_overdue_leer_wenn_nichts_faellig(tmp_db):
    aid = _setup(tmp_db)
    tmp_db.add_task({"application_id": aid, "titel": "Zukunft", "faellig_am": _d(3)})
    assert tmp_db.get_overdue_tasks() == []


def test_add_task_speichert_faellig_am(tmp_db):
    """REST/Tool-Pfad: faellig_am wird durchgereicht (Frontend sendet es jetzt)."""
    aid = _setup(tmp_db)
    tid = tmp_db.add_task({"application_id": aid, "titel": "Mit Datum", "faellig_am": _d(-1)})
    task = tmp_db.get_task(tid)
    assert task and task["faellig_am"] == _d(-1)
