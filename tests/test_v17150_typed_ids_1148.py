"""#1148 Punkt 9 — typisierte Kennungen nimmt jedes Werkzeug an.

Befund (01.10.2026, auf isolierten Datenbanken gemessen): PBP gibt Kennungen mit Präfix aus
(`APP-42061e46`, `hash_typed` mit `JOB-`), aber nur einzelne Werkzeuge verstanden sie wieder.
`meetings_anzeigen` und `emails_anzeigen` wiesen `APP-…` mit „Bewerbung nicht gefunden“ ab,
`todos_anzeigen` und `skill_zeitraeume_anzeigen` antworteten leer, `fit_analyse(JOB-…)` wurde
abgewiesen — obwohl `bewerbung_stellen_anzeigen` genau diese Form ausgibt.

Jetzt entfernt die Middleware in `server.py` das Präfix, bevor ein Werkzeug die Argumente sieht
(`services/typed_ids.normalisiere_argumente`). Ein Registry-Test hält fest, dass jeder
Kennungs-Parameter eines Werkzeugs entweder behandelt oder bewusst ausgenommen ist.

Alle Firmen, Orte und Namen sind Platzhalter.
"""
import asyncio
import importlib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17150_1148_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test", "city": "Hamburg"})
    yield db, _srv_mod.mcp, _srv_mod
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _aufruf(mcp, name, args):
    from fastmcp import Client

    async def _run():
        async with Client(mcp) as c:
            return await c.call_tool(name, args, raise_on_error=False)
    return asyncio.run(_run())


def _text(res) -> str:
    return " ".join(getattr(t, "text", str(t)) for t in res.content)


# ══ Die Funktion allein ═══════════════════════════════════════════════════════

def test_1148_ein_praefix_faellt_weg():
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    neu = normalisiere_argumente({"bewerbung_id": "APP-42061e46", "titel": "x"})
    assert neu == {"bewerbung_id": "42061e46", "titel": "x"}


def test_1148_ohne_praefix_bleibt_alles_wie_es_ist():
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    assert normalisiere_argumente({"bewerbung_id": "42061e46", "seite": 2}) is None
    assert normalisiere_argumente({}) is None
    assert normalisiere_argumente(None) is None


def test_1148_das_urspruengliche_dict_wird_nicht_veraendert():
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    alt = {"bewerbung_id": "APP-42061e46"}
    normalisiere_argumente(alt)
    assert alt == {"bewerbung_id": "APP-42061e46"}


@pytest.mark.parametrize("parameter", ["job_hash", "stellen_hash", "hash_a", "hash_b", "master_hash", "duplikat_hash"])
def test_1148_stellen_kennungen(parameter):
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    assert normalisiere_argumente({parameter: "JOB-0a1b2c3d4e5f"}) == {parameter: "0a1b2c3d4e5f"}


@pytest.mark.parametrize("parameter,praefix", [
    ("bewerbung_id", "APP"), ("application_id", "APP"), ("dokument_id", "DOC"), ("document_id", "DOC"),
    ("meeting_id", "APT"), ("master_id", "APT"), ("duplikat_id", "APT"), ("email_id", "EML"),
    ("event_id", "EVT"), ("profil_id", "PRO"), ("position_id", "POS"), ("projekt_id", "PRJ"),
    ("skill_id", "SKL"), ("follow_up_id", "FUP"), ("kontakt_id", "CON"),
])
def test_1148_jede_art_hat_ihren_parameter(parameter, praefix):
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    assert normalisiere_argumente({parameter: f"{praefix}-abcd1234"}) == {parameter: "abcd1234"}


def test_1148_listen_werden_elementweise_behandelt():
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    neu = normalisiere_argumente({"document_ids": ["DOC-aaaa1111", "bbbb2222", "doc-cccc3333"],
                                  "termin_ids": ["APT-dddd4444"]})
    assert neu == {"document_ids": ["aaaa1111", "bbbb2222", "cccc3333"], "termin_ids": ["dddd4444"]}


def test_1148_die_schreibweise_des_praefixes_ist_egal():
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    assert normalisiere_argumente({"bewerbung_id": "app-42061e46"}) == {"bewerbung_id": "42061e46"}


def test_1148_eine_kennung_der_falschen_art_wird_benannt():
    from bewerbungs_assistent.services.typed_ids import FalscheKennung, normalisiere_argumente
    with pytest.raises(FalscheKennung) as e:
        normalisiere_argumente({"bewerbung_id": "DOC-aaaa1111"})
    text = str(e.value)
    assert "bewerbung_id" in text and "Bewerbungs-Kennung" in text and "APP-" in text
    assert "Dokument-Kennung" in text and "DOC-aaaa1111" in text


def test_1148_ein_falsches_element_in_einer_liste_wird_benannt():
    from bewerbungs_assistent.services.typed_ids import FalscheKennung, normalisiere_argumente
    with pytest.raises(FalscheKennung) as e:
        normalisiere_argumente({"document_ids": ["DOC-aaaa1111", "APP-bbbb2222"]})
    assert "document_ids" in str(e.value) and "APP-bbbb2222" in str(e.value)


@pytest.mark.parametrize("parameter", ["element_id", "ziel_id", "nur_id"])
@pytest.mark.parametrize("praefix", ["SKL", "POS", "EDU", "PRJ", "JOB", "APP"])
def test_1148_wo_die_art_vom_aufruf_abhaengt_faellt_jedes_praefix_weg(parameter, praefix):
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    assert normalisiere_argumente({parameter: f"{praefix}-abcd1234"}) == {parameter: "abcd1234"}


def test_1148_andere_parameter_bleiben_unberuehrt_auch_wenn_der_text_so_aussieht():
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    assert normalisiere_argumente({"notiz": "APP-42061e46", "titel": "JOB-1", "firma": "DOC-9"}) is None


def test_1148_ein_parameter_ohne_typisierte_form_bleibt_unberuehrt():
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    assert normalisiere_argumente({"todo_id": "APP-12", "grund_id": "SKL-1"}) is None


def test_1148_ein_gespeicherter_stellen_hash_mit_profil_bleibt_wie_er_ist():
    """Der gespeicherte Hash hat die Form `<Profil>:<Stelle>`; er enthält keinen Bindestrich-Präfix."""
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    assert normalisiere_argumente({"job_hash": "ab12cd34:0a1b2c3d4e5f"}) is None


def test_1148_nicht_zeichenketten_werden_nicht_angefasst():
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    assert normalisiere_argumente({"bewerbung_id": None, "job_hash": 5, "document_ids": [1, None]}) is None


def test_1148_eine_leere_oder_nur_aus_praefix_bestehende_kennung_wird_leer():
    from bewerbungs_assistent.services.typed_ids import normalisiere_argumente
    assert normalisiere_argumente({"bewerbung_id": "APP-"}) == {"bewerbung_id": ""}


# ══ Jedes Werkzeug: kein Kennungs-Parameter wird vergessen ═══════════════════════

def _alle_parameter(mcp) -> dict:
    async def _run():
        tools = await mcp.list_tools()
        return {t.name: list(((t.parameters or {}).get("properties") or {})) for t in tools}
    return asyncio.run(_run())


KENNUNG = re.compile(r"(_ids?|_hash)$|^hash_|^ids?$")


def test_1148_jeder_kennungs_parameter_ist_behandelt_oder_bewusst_ausgenommen(umgebung):
    """Kommt ein Werkzeug mit einem neuen Kennungs-Parameter dazu, entscheidet dieser Test, dass jemand
    klärt, ob es dafür eine typisierte Form gibt (dann in `PARAMETER_ARTEN`) oder nicht (dann in
    `OHNE_TYPISIERUNG`). Sonst nimmt genau dieses Werkzeug `APP-…` wieder nicht an."""
    from bewerbungs_assistent.services.typed_ids import OHNE_TYPISIERUNG, PARAMETER_ARTEN, PARAMETER_BELIEBIG
    db, mcp, srv = umgebung
    bekannt = set(PARAMETER_ARTEN) | set(PARAMETER_BELIEBIG) | set(OHNE_TYPISIERUNG)
    offen = {}
    for werkzeug, parameter in _alle_parameter(mcp).items():
        for p in parameter:
            if KENNUNG.search(p) and p not in bekannt:
                offen.setdefault(p, []).append(werkzeug)
    assert not offen, f"Kennungs-Parameter ohne Entscheidung: {offen}"


def test_1148_die_tabellen_nennen_nur_parameter_die_es_gibt(umgebung):
    """Ein Tippfehler in der Tabelle würde still nichts tun."""
    from bewerbungs_assistent.services.typed_ids import OHNE_TYPISIERUNG, PARAMETER_ARTEN, PARAMETER_BELIEBIG
    db, mcp, srv = umgebung
    vorhanden = {p for ps in _alle_parameter(mcp).values() for p in ps}
    for tabelle, name in ((set(PARAMETER_ARTEN), "PARAMETER_ARTEN"), (set(PARAMETER_BELIEBIG), "PARAMETER_BELIEBIG"),
                          (set(OHNE_TYPISIERUNG), "OHNE_TYPISIERUNG")):
        assert not (tabelle - vorhanden), f"{name} nennt Parameter, die kein Werkzeug hat: {sorted(tabelle - vorhanden)}"


def test_1148_keine_art_steht_in_zwei_tabellen():
    from bewerbungs_assistent.services.typed_ids import OHNE_TYPISIERUNG, PARAMETER_ARTEN, PARAMETER_BELIEBIG
    assert not (set(PARAMETER_ARTEN) & set(PARAMETER_BELIEBIG))
    assert not (set(PARAMETER_ARTEN) & set(OHNE_TYPISIERUNG))
    assert not (set(PARAMETER_BELIEBIG) & set(OHNE_TYPISIERUNG))


# ══ Durch den Server, wie Claude es aufruft ═════════════════════════════════════

@pytest.fixture
def bestand(umgebung):
    db, mcp, srv = umgebung
    app = db.add_application({"title": "Sachbearbeiter", "company": "Beispiel GmbH", "status": "beworben"})
    meeting = db.add_meeting({"application_id": app, "title": "Gespräch", "meeting_date": "2026-11-05T10:00"})
    db.add_email({"application_id": app, "subject": "Einladung", "sender": "test@example.com"})
    skill = db.add_skill({"name": "Python", "level": 3})
    db.save_jobs([{
        "hash": "a1b2c3d4e5f6", "title": "Sachbearbeiter", "company": "Beispiel GmbH",
        "url": "https://beispiel.example/job/1", "source": "bundesagentur",
        "description": "Beschreibung der Stelle. " * 20, "score": 20, "found_at": "2026-10-01T00:00:00"}])
    return db, mcp, {"app": app, "meeting": meeting, "skill": skill, "job": "a1b2c3d4e5f6"}


def _gleich(mcp, name, roh, typisiert):
    a = _aufruf(mcp, name, roh)
    b = _aufruf(mcp, name, typisiert)
    assert a.is_error == b.is_error, f"{name}: {_text(a)[:200]} gegen {_text(b)[:200]}"
    assert a.structured_content == b.structured_content, f"{name}: roh und typisiert liefern Verschiedenes"
    return a


def test_1148_meetings_anzeigen_nimmt_app_an(bestand):
    db, mcp, ids = bestand
    a = _gleich(mcp, "meetings_anzeigen", {"bewerbung_id": ids["app"]}, {"bewerbung_id": "APP-" + ids["app"]})
    assert "nicht gefunden" not in _text(a)
    assert "Gespräch" in _text(a)


def test_1148_emails_anzeigen_nimmt_app_an(bestand):
    db, mcp, ids = bestand
    a = _gleich(mcp, "emails_anzeigen", {"bewerbung_id": ids["app"]}, {"bewerbung_id": "APP-" + ids["app"]})
    assert "nicht gefunden" not in _text(a)
    assert "Einladung" in _text(a)


def test_1148_todos_anzeigen_nimmt_app_an(bestand):
    db, mcp, ids = bestand
    mcp_ergebnis = _aufruf(mcp, "todo_anlegen", {"bewerbung_id": "APP-" + ids["app"], "titel": "Unterlagen schicken"})
    assert mcp_ergebnis.is_error is False, _text(mcp_ergebnis)
    a = _gleich(mcp, "todos_anzeigen", {"bewerbung_id": ids["app"]}, {"bewerbung_id": "APP-" + ids["app"]})
    assert "Unterlagen schicken" in _text(a)


def test_1148_skill_zeitraeume_anzeigen_nimmt_skl_an(bestand):
    db, mcp, ids = bestand
    a = _gleich(mcp, "skill_zeitraeume_anzeigen", {"skill_id": ids["skill"]}, {"skill_id": "SKL-" + ids["skill"]})
    assert a.is_error is False, _text(a)
    assert "nicht gefunden" not in _text(a).lower()


def test_1148_fit_analyse_nimmt_job_an(bestand):
    db, mcp, ids = bestand
    a = _aufruf(mcp, "fit_analyse", {"job_hash": "JOB-" + ids["job"]})
    b = _aufruf(mcp, "fit_analyse", {"job_hash": ids["job"]})
    assert a.is_error == b.is_error
    assert "nicht gefunden" not in _text(a).lower(), _text(a)[:300]
    assert (a.structured_content or {}).get("error") == (b.structured_content or {}).get("error")


def test_1148_meeting_bearbeiten_nimmt_apt_an(bestand):
    db, mcp, ids = bestand
    res = _aufruf(mcp, "meeting_bearbeiten", {"meeting_id": "APT-" + ids["meeting"], "titel": "Zweites Gespräch"})
    assert res.is_error is False, _text(res)
    termine = db.get_meetings_for_application(ids["app"])
    assert [t["title"] for t in termine] == ["Zweites Gespräch"]


def test_1148_eine_kennung_der_falschen_art_kommt_als_klare_meldung(bestand):
    db, mcp, ids = bestand
    res = _aufruf(mcp, "meetings_anzeigen", {"bewerbung_id": "DOC-" + ids["app"]})
    assert res.is_error is True
    text = _text(res)
    assert "falsche_kennung" in text and "Bewerbungs-Kennung" in text and "Dokument-Kennung" in text
    assert "nicht gefunden" not in text


def test_1148_die_roh_form_geht_weiter(bestand):
    db, mcp, ids = bestand
    res = _aufruf(mcp, "meetings_anzeigen", {"bewerbung_id": ids["app"]})
    assert res.is_error is False
    assert "Gespräch" in _text(res)
