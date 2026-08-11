"""Tests fuer v1.7.12 — #822 (F36): Elwosa-Frequenzsteuerung.

Belegter Fall 11.08.2026: 40 Nachrichten in 87 Stunden, exakt eine pro
Stunde, nur zwei Trigger-Arten (holiday_summer, late_night), sechs
verschiedene Texte aus einem 105-Linien-Pool — late_night nachts an einen
leeren Bildschirm.

Kern-Bug: can_post_class prueste die KLASSE ("world"), gefeuert wurde mit
dem konkreten Kind ("holiday_summer") — das fiel durch alle Limits und
durch den sachlich-Modus. Zweite Ursache: pick_line fiel auf den vollen
Pool zurueck, sobald alle Linien 'verbraucht' waren.
"""
import importlib
import os
import shutil
import tempfile
from datetime import datetime, timedelta, timezone

import pytest


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1712_822_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, tmpdir
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _backdate(db, msg_id: int, hours: float):
    """Setzt created_at einer Nachricht um N Stunden zurueck."""
    neu = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    conn = db.connect()
    conn.execute("UPDATE elwosa_messages SET created_at=? WHERE id=?",
                 (neu, msg_id))
    conn.commit()


def _praesenz(db):
    """Simuliert UI-Aktivitaet vor 1 Minute (user_activity_events, #594)."""
    conn = db.connect()
    conn.execute(
        "INSERT INTO user_activity_events (profile_id, event_type, timestamp) "
        "VALUES (?, 'click', ?)",
        (db.get_active_profile_id(),
         (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()))
    conn.commit()


def _ruhezeit_aus(db):
    """Ruhezeit auf ein nie-aktives Fenster legen (Test-Determinismus)."""
    h = datetime.now().hour
    db.set_profile_setting("elwosa_ruhezeit", f"{(h + 2) % 24}-{(h + 3) % 24}")


def test_822_klassen_mapping_holiday_summer_ist_world():
    from bewerbungs_assistent.services.elwosa import _trigger_klasse
    assert _trigger_klasse("holiday_summer") == "world"
    assert _trigger_klasse("late_night") == "world"
    assert _trigger_klasse("morning") == "world"
    assert _trigger_klasse("idle") == "idle"
    assert _trigger_klasse("status_change") == "hard"


def test_822_sachlich_blockt_jetzt_auch_konkrete_world_kinds(setup_env):
    """DER Kern-Bug: sachlich blockte 'world', aber nie 'holiday_summer'."""
    db, _ = setup_env
    from bewerbungs_assistent.services import elwosa
    _ruhezeit_aus(db)
    db.set_profile_setting("elwosa_tonfall_modus", "sachlich")
    assert elwosa.speak(db, "holiday_summer", ctx={}) is None, \
        "sachlich muss Ambiente-Kinds blocken"


def test_822_sperrfrist_pro_linie_kein_pool_fallback(setup_env):
    """Ist der ganze Pool innerhalb der Sperrfrist, kommt KEINE Linie —
    nicht dieselbe nochmal (alter Fallback = dreimal 'Sommerloch')."""
    db, _ = setup_env
    from bewerbungs_assistent.services.elwosa import pick_line
    pool = ["Eine einzige Linie."]
    erste = pick_line(db, pool, {})
    assert erste == "Eine einzige Linie."
    mid = db.add_elwosa_message(content=erste, trigger_kind="test")
    _backdate(db, mid, hours=2)  # 2h alt — innerhalb 24h-Sperre
    assert pick_line(db, pool, {}) is None, "Sperrfrist muss hart sein"
    _backdate(db, mid, hours=25)  # aelter als Sperrfrist
    assert pick_line(db, pool, {}) == "Eine einzige Linie."


def test_822_kind_sperre_12h(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services import elwosa
    _ruhezeit_aus(db)
    db.set_profile_setting("elwosa_ambiente_pro_tag", 10)
    mid = elwosa.speak(db, "holiday_summer", ctx={})
    assert mid, "erste Linie muss durchgehen"
    _backdate(db, mid, hours=2)  # Cooldown umgehen, Kind-Sperre bleibt
    assert elwosa.speak(db, "holiday_summer", ctx={}) is None, \
        "derselbe trigger_kind fruehestens nach 12 h"
    _backdate(db, mid, hours=13)
    assert elwosa.speak(db, "holiday_summer", ctx={}) is not None


def test_822_ambiente_kontingent_gilt_ueber_kinds_hinweg(setup_env):
    """Eine Welt-Linie heute = Ambiente-Kontingent (Default 1) verbraucht,
    auch fuer ANDERE Ambiente-Kinds."""
    db, _ = setup_env
    from bewerbungs_assistent.services import elwosa
    _ruhezeit_aus(db)
    mid = elwosa.speak(db, "holiday_summer", ctx={})
    assert mid
    _backdate(db, mid, hours=3)  # Cooldown + Kind-Sperre irrelevant machen
    assert elwosa.speak(db, "weekend", ctx={}) is None, \
        "Ambiente max 1/Tag — anderes Kind zaehlt mit"


def test_822_ereignis_trigger_bleiben_unberuehrt(setup_env):
    """Hard-Trigger duerfen nicht unter dem Ambiente-Kontingent leiden."""
    db, _ = setup_env
    from bewerbungs_assistent.services import elwosa
    _ruhezeit_aus(db)
    mid = elwosa.speak(db, "holiday_summer", ctx={})
    assert mid
    _backdate(db, mid, hours=1)  # aus dem 90s-Cooldown raus
    mid2 = elwosa.speak(db, "auto_dismiss_ran", ctx={"count": 5})
    assert mid2, "Ereignis-Trigger muss trotz verbrauchtem Ambiente posten"


def test_822_late_night_braucht_praesenz(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services import elwosa
    _ruhezeit_aus(db)
    db.set_profile_setting("elwosa_ambiente_pro_tag", 10)
    assert elwosa.speak(db, "late_night", ctx={}) is None, \
        "ohne Aktivitaet keine anredende Linie"
    _praesenz(db)
    assert elwosa.speak(db, "late_night", ctx={}) is not None, \
        "mit Aktivitaet in den letzten 15 min darf sie kommen"


def test_822_ruhezeit_unterdrueckt_ambiente_ohne_praesenz(setup_env):
    db, _ = setup_env
    from bewerbungs_assistent.services import elwosa
    h = datetime.now().hour
    db.set_profile_setting("elwosa_ruhezeit", f"{h}-{(h + 1) % 24}")
    assert elwosa.speak(db, "morning", ctx={}) is None, \
        "Ruhezeit ohne Praesenz: kein Ambiente"
    _praesenz(db)
    assert elwosa.speak(db, "morning", ctx={}) is not None, \
        "Praesenz hebt die Ruhezeit fuer Ambiente auf"


def test_822_ungelesen_daempfung(setup_env):
    """10 ungelesene Ambiente-Linien in Folge -> Elwosa wird leiser."""
    db, _ = setup_env
    from bewerbungs_assistent.services import elwosa
    _ruhezeit_aus(db)
    db.set_profile_setting("elwosa_ambiente_pro_tag", 99)
    for i in range(10):
        mid = db.add_elwosa_message(content=f"Alte Ambiente-Linie {i}.",
                                    trigger_kind="morning")
        _backdate(db, mid, hours=30 + i * 13)
    assert elwosa.speak(db, "weekend", ctx={}) is None, \
        "durchgehend ungelesen -> stumm"
    db.mark_elwosa_messages_read()
    assert elwosa.speak(db, "weekend", ctx={}) is not None, \
        "nach dem Lesen spricht sie wieder"


def test_822_48_ticks_maximal_kontingent(setup_env):
    """48 simulierte Engine-Ticks ohne Ereignisse: hoechstens das
    konfigurierte Ambiente-Kontingent, keine Wiederholung."""
    db, _ = setup_env
    from bewerbungs_assistent.services import elwosa
    _ruhezeit_aus(db)
    gepostet = []
    for _ in range(48):
        mid = elwosa.speak(db, "holiday_summer", ctx={})
        if mid:
            gepostet.append(mid)
    assert len(gepostet) <= 1, \
        f"Ambiente-Kontingent 1/Tag, aber {len(gepostet)} Linien"
    inhalte = [r["content"] for r in db.connect().execute(
        "SELECT content FROM elwosa_messages").fetchall()]
    assert len(inhalte) == len(set(inhalte)), "keine Wiederholung"


def test_822_unbegrenzt_hebt_sperrfristen_nicht_auf(setup_env):
    """frequency='unbegrenzt' heisst viele Linien — nie dieselbe oefter."""
    db, _ = setup_env
    from bewerbungs_assistent.services import elwosa
    _ruhezeit_aus(db)
    db.set_profile_setting("elwosa_frequency", "unbegrenzt")
    mid = elwosa.speak(db, "holiday_summer", ctx={})
    assert mid
    _backdate(db, mid, hours=2)
    assert elwosa.speak(db, "holiday_summer", ctx={}) is None, \
        "Kind-Sperre gilt auch bei unbegrenzt"
