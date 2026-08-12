"""Tests fuer v1.7.0-beta.41 — Elwosa-Polish (#614 + #612).

#614: Linien-Pool-Erweiterung, Markdown-Fettdruck, Anti-Wiederholung.
#612: tonfall_modus-Verdrahtung, Settings-Selbst-Reflektion.
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def setup_env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v170beta41_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import importlib
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.dashboard as _dash_mod
    importlib.reload(_dash_mod)
    from bewerbungs_assistent.database import Database
    db = Database()
    db.initialize()
    db.save_profile({"name": "Test"})
    # Ruhezeit (v1.7.12/#822) auf ein nie-aktives Fenster legen — sonst
    # sind Elwosa-Tests zwischen 22 und 7 Uhr Runner-Zeit rot (#853).
    from datetime import datetime as _dt
    _h = _dt.now().hour
    db.set_profile_setting("elwosa_ruhezeit", f"{(_h + 2) % 24}-{(_h + 3) % 24}")
    _dash_mod._db = db
    yield db
    db.close()
    import shutil
    shutil.rmtree(tmpdir, ignore_errors=True)


# ============= #614: Linien-Pool-Erweiterung ===============

def test_world_pool_min_lines_per_trigger():
    """Akzeptanz aus #614: jeder Welt-Trigger braucht genug Varianz."""
    from bewerbungs_assistent.services.elwosa_lines import WORLD_LINES
    assert len(WORLD_LINES["friday_evening"]) >= 7
    assert len(WORLD_LINES["weekend"]) >= 6
    assert len(WORLD_LINES["monday_morning"]) >= 5
    assert len(WORLD_LINES["late_night"]) >= 5
    assert len(WORLD_LINES["evening"]) >= 4
    assert len(WORLD_LINES["morning"]) >= 4
    assert len(WORLD_LINES["holiday_christmas"]) >= 4
    assert len(WORLD_LINES["holiday_summer"]) >= 4


def test_all_new_world_lines_pass_validator():
    """Alle erweiterten Welt-Linien muessen Sprach-DNA-konform sein."""
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    from bewerbungs_assistent.services.elwosa_lines import WORLD_LINES
    for trigger, lines in WORLD_LINES.items():
        for line in lines:
            try:
                filled = line.format(
                    firma="ACME", count=3, days=5, wochentag="Montag",
                )
            except (KeyError, ValueError):
                filled = line
            try:
                validate_tonfall(filled)
            except Exception as e:
                pytest.fail(f"{trigger}: {e} — {filled[:80]}")


def test_at_least_one_bold_line_per_set_of_world_triggers():
    """Mind. 1 Linie nutzt Fettdruck-Markup pro relevantem Trigger-Set."""
    from bewerbungs_assistent.services.elwosa_lines import WORLD_LINES
    # Wir verlangen mind. eine **bold**-Linie verteilt ueber die
    # erweiterten Trigger (friday_evening, weekend, late_night, etc.).
    has_bold = any(
        "**" in line
        for trigger in ("friday_evening", "weekend", "late_night",
                         "morning", "holiday_christmas")
        for line in WORLD_LINES.get(trigger, [])
    )
    assert has_bold, "Es sollte mind. eine **bold**-Linie geben"


def test_at_least_one_pause_link_in_world_lines():
    """Mind. 1 Linie hat einen klickbaren [link:pause:N|...]-Hint."""
    from bewerbungs_assistent.services.elwosa_lines import WORLD_LINES
    has_pause_link = any(
        "[link:pause:" in line
        for lines in WORLD_LINES.values()
        for line in lines
    )
    assert has_pause_link


# ============= #614: Markup-Stripping + Validator ==========

def test_strip_markup_removes_bold():
    from bewerbungs_assistent.services.elwosa import strip_markup
    assert strip_markup("Hallo **Welt** und tschoes") == "Hallo Welt und tschoes"


def test_strip_markup_removes_link():
    from bewerbungs_assistent.services.elwosa import strip_markup
    assert strip_markup(
        "Klick [link:pause:120|hier um mich kurz still zu halten]."
    ) == "Klick hier um mich kurz still zu halten."


def test_validator_accepts_bold():
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    validate_tonfall("**Freitag.** Geh raus.")


def test_validator_accepts_link():
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    validate_tonfall("Wenn du Ruhe brauchst — [link:pause:120|sag's]")


def test_validator_blocks_bang_inside_bold():
    """Fettdruck darf nicht zur Umgehung des !-Verbots werden."""
    from bewerbungs_assistent.services.elwosa import (
        TonfallError, validate_tonfall,
    )
    with pytest.raises(TonfallError):
        validate_tonfall("**Achtung!** Stop.")


def test_validator_blocks_hoeflichkeits_anrede_in_link_label():
    """Auch im Label des Markup-Links darf Hoeflichkeits-Anrede nicht durch."""
    from bewerbungs_assistent.services.elwosa import (
        TonfallError, validate_tonfall,
    )
    with pytest.raises(TonfallError):
        validate_tonfall("Klick [link:pause:60|wenn Ihre Pause hilft].")


def test_validator_length_uses_rendered_text():
    """280-Zeichen-Limit zaehlt das gerenderte (gestrippte), nicht das Markup."""
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    # Markup haengt ~30 Zeichen Overhead an, der nicht zaehlen darf
    body = "a" * 270
    line = f"**Bold** {body}"  # roh > 280, gestripped 4+1+270 = 275
    validate_tonfall(line)


# ============= #614: Anti-Wiederholung ============

def test_pick_line_avoids_same_day_repeat(setup_env):
    """pick_line zieht ohne Zuruecklegen: erst alle Linien einmal, dann —
    seit v1.7.12 (#822) — KEINE mehr, statt zu wiederholen.

    Der alte Vertrag ("Repeat erlaubt, wenn der Pool durch ist") war die
    zweite Ursache der stuendlichen Wiederholungen und ist abgeschafft.
    """
    db = setup_env
    from bewerbungs_assistent.services import elwosa
    pool = ["A. Vermerkt.", "B. Notiert.", "C. Markiert."]
    chosen = []
    for _ in range(3):
        line = elwosa.pick_line(db, pool, ctx={})
        assert line is not None
        db.add_elwosa_message(line, trigger_kind="world")
        chosen.append(line)
    # Alle 3 verschiedenen Linien genau einmal
    assert set(chosen) == set(pool)
    # Pool innerhalb der Sperrfrist verbraucht -> None statt Wiederholung
    assert elwosa.pick_line(db, pool, ctx={}) is None


def test_pick_line_falls_back_when_pool_exhausted(setup_env):
    """v1.7.12 (#822): Der Fallback ist ABGESCHAFFT. Ist der Pool
    innerhalb der Sperrfrist durch, kommt keine Linie — lieber Stille
    als dieselbe Aussage dreimal in drei Stunden (belegter Fall)."""
    db = setup_env
    from bewerbungs_assistent.services import elwosa
    pool = ["Einzige Linie. Vermerkt."]
    a = elwosa.pick_line(db, pool, ctx={})
    db.add_elwosa_message(a, trigger_kind="world")
    b = elwosa.pick_line(db, pool, ctx={})
    assert b is None, "kein Repeat innerhalb der Sperrfrist"


# ============= #612: tonfall_modus-Verdrahtung ============

def test_tonfall_aus_blocks_all_classes(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True, tonfall_modus="aus")
    from bewerbungs_assistent.services import elwosa
    settings = db.get_elwosa_settings()
    assert elwosa.can_post_class(db, "idle", settings) is False
    assert elwosa.can_post_class(db, "world", settings) is False
    assert elwosa.can_post_class(db, "mail_received", settings) is False
    assert elwosa.can_post_class(db, "settings_change", settings) is False


def test_tonfall_sachlich_blocks_idle_world_tip_easter(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True, tonfall_modus="sachlich")
    from bewerbungs_assistent.services import elwosa
    settings = db.get_elwosa_settings()
    assert elwosa.can_post_class(db, "idle", settings) is False
    assert elwosa.can_post_class(db, "world", settings) is False
    assert elwosa.can_post_class(db, "tip", settings) is False
    assert elwosa.can_post_class(db, "easter_egg", settings) is False
    # Status passt durch
    assert elwosa.can_post_class(db, "mail_received", settings) is True
    assert elwosa.can_post_class(db, "status_change", settings) is True


def test_tonfall_minimal_caps_at_one_per_day(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True, tonfall_modus="minimal")
    from bewerbungs_assistent.services import elwosa
    settings = db.get_elwosa_settings()
    # Erste Linie: ja
    assert elwosa.can_post_class(db, "mail_received", settings) is True
    # Linie persistieren
    db.add_elwosa_message("Erste. Vermerkt.", trigger_kind="mail_received")
    # Zweite Linie heute: nein, auch nicht fuer Status-Trigger
    assert elwosa.can_post_class(db, "mail_received", settings) is False
    assert elwosa.can_post_class(db, "world", settings) is False


# ============= #612: Settings-Reflektion ============

def test_speak_settings_reflection_posts(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    from bewerbungs_assistent.services import elwosa
    mid = elwosa.speak_settings_reflection(db, "frequency_unbegrenzt")
    assert mid is not None
    msgs = db.get_elwosa_messages()
    assert len(msgs) == 1
    assert msgs[0]["trigger_kind"] == "settings_change"


def test_speak_settings_reflection_works_with_sachlich(setup_env):
    """Reflektion soll auch bei tonfall_modus=sachlich quittieren."""
    db = setup_env
    db.set_elwosa_settings(enabled=True, tonfall_modus="sachlich")
    from bewerbungs_assistent.services import elwosa
    mid = elwosa.speak_settings_reflection(db, "tonfall_sachlich")
    assert mid is not None


def test_speak_settings_reflection_disabled_when_off(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=False)
    from bewerbungs_assistent.services import elwosa
    mid = elwosa.speak_settings_reflection(db, "frequency_aktiv")
    assert mid is None


def test_speak_settings_reflection_unknown_sub_no_error(setup_env):
    db = setup_env
    db.set_elwosa_settings(enabled=True)
    from bewerbungs_assistent.services import elwosa
    assert elwosa.speak_settings_reflection(db, "does_not_exist") is None


def test_settings_reflection_lines_pass_validator():
    from bewerbungs_assistent.services.elwosa import validate_tonfall
    from bewerbungs_assistent.services.elwosa_lines import (
        SETTINGS_REFLECTION_LINES,
    )
    for sub, lines in SETTINGS_REFLECTION_LINES.items():
        for line in lines:
            try:
                filled = line.format(wert="standard", trigger="idle")
            except (KeyError, ValueError):
                filled = line
            try:
                validate_tonfall(filled)
            except Exception as e:
                pytest.fail(f"{sub}: {e} — {filled[:80]}")


# ============= #612: API /api/elwosa/user-action ============

def test_api_user_action_settings_change_frequency(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/elwosa/user-action", json={
        "action": "settings_change",
        "target": "frequency",
        "payload": {"value": "aktiv"},
    })
    assert r.status_code == 200
    j = r.json()
    assert j["posted"] == 1
    assert j["sub"] == "frequency_aktiv"


def test_api_user_action_settings_change_tonfall(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/elwosa/user-action", json={
        "action": "settings_change",
        "target": "tonfall_modus",
        "payload": {"value": "humorvoll"},
    })
    j = r.json()
    assert j["posted"] == 1
    assert j["sub"] == "tonfall_humorvoll"


def test_api_user_action_settings_change_comment_actions(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/elwosa/user-action", json={
        "action": "settings_change",
        "target": "comment_user_actions",
        "payload": {"value": True},
    })
    assert r.json()["sub"] == "comment_user_actions_on"


def test_api_user_action_unknown_action(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/elwosa/user-action", json={"action": "voodoo"})
    assert r.status_code == 200
    assert r.json()["posted"] == 0


def test_api_user_action_missing_action(setup_env):
    from fastapi.testclient import TestClient
    from bewerbungs_assistent.dashboard import app
    client = TestClient(app)
    r = client.post("/api/elwosa/user-action", json={})
    assert r.status_code == 400
