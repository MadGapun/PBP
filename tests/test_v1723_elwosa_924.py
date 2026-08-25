"""Tests fuer v1.7.23 — #924: dieselbe Ambiente-Linie stuendlich.

Belegt: dieselbe Linie stand dreimal wortgleich untereinander (3:07,
4:07, 5:07 Uhr), waehrend der Frontend-Heartbeat stuendlich feuerte.

`pick_line` hatte die Sperrfrist seit #822 korrekt. Mehrere Pfade
schreiben aber DIREKT in den Stream — Wiki-Hints, Provider-Linien, der
Claude-Schreibzugriff. Eine Regel, die fuer alle Pfade gelten soll,
gehoert deshalb an das Nadeloehr, durch das jeder Schreibzugriff laeuft
(dasselbe Muster wie `dismiss_job` in #913).
"""
import pytest


def test_924_dieselbe_linie_wird_nicht_zweimal_geschrieben(tmp_db):
    text = "Die lokale KI sortiert. Ich schaue zu."
    erste = tmp_db.add_elwosa_message(content=text, trigger_kind="world")
    zweite = tmp_db.add_elwosa_message(content=text, trigger_kind="world")
    assert erste > 0
    assert zweite == 0, "Wiederholung muss unterdrueckt werden"
    stream = tmp_db.get_elwosa_messages(limit=50)
    assert sum(1 for m in stream if m["content"] == text) == 1


def test_924_drei_heartbeat_zyklen_ergeben_keine_wortgleiche_wiederholung(tmp_db):
    """Der Regressionsfall aus dem Issue."""
    text = "Nachts ist die Trefferquote nicht besser, nur die Stille."
    geschrieben = [
        tmp_db.add_elwosa_message(content=text, trigger_kind="late_night")
        for _ in range(3)
    ]
    assert sum(1 for g in geschrieben if g) == 1, geschrieben
    stream = tmp_db.get_elwosa_messages(limit=50)
    assert sum(1 for m in stream if m["content"] == text) == 1


def test_924_sperre_gilt_auch_fuer_direkte_schreibpfade(tmp_db):
    """Wiki-Hints und Provider-Linien laufen an pick_line vorbei."""
    text = "Im Wiki steht, wie die Quellen konfiguriert werden."
    assert tmp_db.add_elwosa_message(content=text, trigger_kind="wiki_hint") > 0
    assert tmp_db.add_elwosa_message(content=text, trigger_kind="changelog") == 0


def test_924_verschiedene_linien_bleiben_moeglich(tmp_db):
    """Gegenrichtung: die Sperre darf Elwosa nicht verstummen lassen."""
    ids = [
        tmp_db.add_elwosa_message(content=f"Linie Nummer {i}.",
                                  trigger_kind="idle")
        for i in range(4)
    ]
    assert all(i > 0 for i in ids), ids


def test_924_bewusste_wiederholung_bleibt_moeglich(tmp_db):
    """Ein ausdruecklicher Wunsch schlaegt die Sperre — sonst waere sie
    ein Maulkorb statt einer Drossel."""
    text = "Bewusst zweimal."
    assert tmp_db.add_elwosa_message(content=text, trigger_kind="idle") > 0
    assert tmp_db.add_elwosa_message(
        content=text, trigger_kind="idle", erlaube_wiederholung=True) > 0


def test_924_leerer_inhalt_stolpert_nicht(tmp_db):
    tmp_db.add_elwosa_message(content="", trigger_kind="idle")


def test_924_sperre_endet_nach_der_frist(tmp_db):
    """Nach Ablauf darf dieselbe Linie wiederkommen — der Pool ist
    endlich, eine ewige Sperre waere Stille."""
    from datetime import datetime, timedelta, timezone
    text = "Wiederkehr nach Ablauf."
    assert tmp_db.add_elwosa_message(content=text, trigger_kind="idle") > 0
    alt = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    conn = tmp_db.connect()
    conn.execute("UPDATE elwosa_messages SET created_at=? WHERE content=?",
                 (alt, text))
    conn.commit()
    assert tmp_db.add_elwosa_message(content=text, trigger_kind="idle") > 0
