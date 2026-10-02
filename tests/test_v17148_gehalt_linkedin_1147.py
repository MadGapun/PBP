"""#1147 — Schätzgehälter in der Marktanalyse und fremde Suchbegriffe bei LinkedIn.

Durchsicht vom 01.10.2026 (Prüfbereich MCP-Werkzeuge), jeweils auf einer
isolierten Datenbank gemessen:

1. `gehalt_marktanalyse` und `firmen_recherche` mischten die Schätzwerte des
   Scrapers unter die echten Angaben. Gemessen: 2 echte Angaben (38.000 bis
   44.000 EUR) plus 18 geschätzte ergaben "Anzahl 20, Durchschnitt
   48.900-67.300, Median 50.000" — und nichts kennzeichnete die Schätzwerte.
   Der Prompt `gehaltsverhandlung` schickt Claude genau darauf.
2. Das LinkedIn-Suchprofil startete für jeden mit den Suchbegriffen des
   Entwicklers (PDM, PLM Berater, ...) und dem Branchenfilter Maschinenbau.
   Schon das Lesen legte die Zeile an.

(Punkt 3 — die KI-Schalter — wartet auf eine Entscheidung und ist hier nicht
enthalten.) Alle Firmen und Orte sind Platzhalter.
"""
import asyncio
import importlib
import json
import os
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
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17148_1147_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp, _db_mod
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


_zaehler = {"n": 0}


def _stelle(db, *, firma="Musterfirma GmbH", s_min, s_max, typ="jaehrlich",
            geschaetzt=0, titel=None):
    _zaehler["n"] += 1
    n = _zaehler["n"]
    db.save_jobs([{
        "hash": f"gh{n:04d}", "title": titel or f"Fachkraft Nummer {n}",
        "company": firma, "location": "Musterstadt",
        "url": f"https://example.com/1147/{n}", "source": "manuell",
        "_manual_entry": True,
        "description": "Eine Stelle mit genug Text, damit sie angelegt wird. " * 6,
        "employment_type": "freelance" if typ == "taeglich" else "festanstellung",
        "salary_min": s_min, "salary_max": s_max, "salary_type": typ,
        "salary_estimated": geschaetzt, "score": 5.0,
    }])


def _gemessener_bestand(db):
    """2 echte Angaben (38.000-44.000) plus 18 Schaetzwerte der Standardspanne."""
    _stelle(db, s_min=38000, s_max=42000)
    _stelle(db, s_min=40000, s_max=44000)
    for _ in range(18):
        _stelle(db, s_min=50000, s_max=70000, geschaetzt=1)


# ══ Punkt 1: Schaetzwerte sind keine Marktdaten ═══════════════════════

def test_1147_die_marktanalyse_zaehlt_nur_belegte_angaben(umgebung):
    db, mcp, _ = umgebung
    _gemessener_bestand(db)
    erg = _call(mcp, "gehalt_marktanalyse")
    assert erg["anzahl"] == 2, erg
    fest = erg["festanstellung"]
    assert fest["anzahl"] == 2
    assert fest["gehalt_min"] == 38000
    assert fest["gehalt_max"] == 44000
    assert fest["durchschnitt_min"] == 39000
    assert fest["durchschnitt_max"] == 43000


def test_1147_die_schaetzwerte_werden_benannt_nicht_verschwiegen(umgebung):
    db, mcp, _ = umgebung
    _gemessener_bestand(db)
    erg = _call(mcp, "gehalt_marktanalyse")
    assert erg["geschaetzt_nicht_gezaehlt"] == 18
    assert "geschätzt" in erg["hinweis"]
    assert "18" in erg["hinweis"]


def test_1147_zwei_belegte_angaben_sind_keine_marktzahl(umgebung):
    db, mcp, _ = umgebung
    _gemessener_bestand(db)
    erg = _call(mcp, "gehalt_marktanalyse")
    assert erg["aussagekraft"] == "gering"
    assert "keine Marktzahl" in erg["hinweis"]


def test_1147_genug_belegte_angaben_tragen_eine_aussage(umgebung):
    db, mcp, _ = umgebung
    for i in range(5):
        _stelle(db, s_min=60000 + i * 1000, s_max=70000 + i * 1000)
    erg = _call(mcp, "gehalt_marktanalyse")
    assert erg["anzahl"] == 5
    assert erg["aussagekraft"] == "ok"
    assert erg["geschaetzt_nicht_gezaehlt"] == 0
    assert "keine Marktzahl" not in erg.get("hinweis", "")


def test_1147_nur_schaetzwerte_heissen_unbekannt_nicht_marktdaten(umgebung):
    db, mcp, _ = umgebung
    for _ in range(6):
        _stelle(db, s_min=50000, s_max=70000, geschaetzt=1)
    erg = _call(mcp, "gehalt_marktanalyse")
    assert erg["anzahl"] == 0
    assert "festanstellung" not in erg and "freelance" not in erg
    assert erg["geschaetzt_nicht_gezaehlt"] == 6
    assert "geschätzt" in erg["nachricht"]


def test_1147_ohne_jede_angabe_bleibt_die_alte_auskunft(umgebung):
    db, mcp, _ = umgebung
    erg = _call(mcp, "gehalt_marktanalyse")
    assert erg["anzahl"] == 0
    assert "Keine Gehaltsdaten" in erg["nachricht"]


def test_1147_tagessaetze_werden_genauso_getrennt(umgebung):
    db, mcp, _ = umgebung
    for i in range(3):
        _stelle(db, s_min=800 + i * 50, s_max=900 + i * 50, typ="taeglich")
    for _ in range(9):
        _stelle(db, s_min=700, s_max=1100, typ="taeglich", geschaetzt=1)
    erg = _call(mcp, "gehalt_marktanalyse")
    assert erg["anzahl"] == 3
    assert erg["freelance"]["anzahl"] == 3
    assert erg["freelance"]["tagessatz_min"] == 800
    assert erg["freelance"]["tagessatz_max"] == 1000
    assert erg["geschaetzt_nicht_gezaehlt"] == 9


def test_1147_eine_stelle_ohne_obergrenze_wirft_nicht(umgebung):
    db, mcp, _ = umgebung
    _stelle(db, s_min=55000, s_max=None)
    erg = _call(mcp, "gehalt_marktanalyse")
    assert erg["anzahl"] == 1
    assert erg["festanstellung"]["gehalt_max"] == 55000


def test_1147_das_dashboard_rechnet_mit_derselben_zahl(umgebung):
    """Zwei Wege, eine Quelle."""
    db, mcp, _ = umgebung
    _gemessener_bestand(db)
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as _dash
    importlib.reload(_dash)
    _dash._db = db
    with TestClient(_dash.app) as client:
        antwort = client.get("/api/salary-stats").json()
    assert antwort["anzahl"] == 2
    assert antwort["geschaetzt_nicht_gezaehlt"] == 18


def test_1147_die_firmenrecherche_nennt_nur_die_belegte_spanne(umgebung):
    """Gemessen: 'Gehaltsspanne 38.000-70.000' — die Obergrenze war ein Schaetzwert."""
    db, mcp, _ = umgebung
    _stelle(db, firma="Beispielwerk AG", s_min=38000, s_max=42000)
    for _ in range(3):
        _stelle(db, firma="Beispielwerk AG", s_min=50000, s_max=70000, geschaetzt=1)
    erg = _call(mcp, "firmen_recherche", {"firma": "Beispielwerk"})
    assert erg["gehaltsspanne"] == {"min": 38000, "max": 42000}
    assert erg["gehalt_geschaetzt_stellen"] == 3
    assert "geschätzt" in erg["gehalt_hinweis"]


def test_1147_eine_firma_nur_mit_schaetzwerten_hat_keine_gehaltsspanne(umgebung):
    db, mcp, _ = umgebung
    for _ in range(2):
        _stelle(db, firma="Beispielwerk AG", s_min=50000, s_max=70000, geschaetzt=1)
    erg = _call(mcp, "firmen_recherche", {"firma": "Beispielwerk"})
    assert "gehaltsspanne" not in erg
    assert erg["gehalt_geschaetzt_stellen"] == 2


def test_1147_eine_firma_ohne_schaetzwerte_bekommt_keinen_zusatzhinweis(umgebung):
    db, mcp, _ = umgebung
    _stelle(db, firma="Beispielwerk AG", s_min=38000, s_max=42000)
    erg = _call(mcp, "firmen_recherche", {"firma": "Beispielwerk"})
    assert erg["gehaltsspanne"] == {"min": 38000, "max": 42000}
    assert erg.get("gehalt_geschaetzt_stellen", 0) == 0
    assert "gehalt_hinweis" not in erg


# ══ Punkt 2: LinkedIn startet ohne die Suchbegriffe des Entwicklers ═════

_FREMD = ("PDM", "PLM", "Product Lifecycle", "PRO.FILE", "Maschinenbau",
          "Automotive", "Industrieautomation")


def _text(daten) -> str:
    return json.dumps(daten, ensure_ascii=False)


def test_1147_eine_leere_datenbank_meldet_keine_suchbegriffe(umgebung):
    """Gemessen: 'bereit' mit PDM, PLM Berater, Product Lifecycle Management, PLM."""
    db, mcp, _ = umgebung
    erg = _call(mcp, "linkedin_lauf_plan")
    assert erg["status"] == "leer", erg
    assert erg["begriffe"] == []


def test_1147_das_profil_eines_anderen_fachgebiets_bekommt_nur_eigene_begriffe(umgebung):
    db, mcp, _ = umgebung
    db.set_search_criteria("keywords_muss", ["python", "linux"])
    erg = _call(mcp, "linkedin_lauf_plan")
    assert erg["begriffe"] == ["python", "linux"]
    assert erg["begriffe_quelle"] == "keywords_muss"


def test_1147_eine_pflegekraft_bekommt_weder_plm_noch_den_branchenfilter(umgebung):
    db, mcp, _ = umgebung
    db.update_portal_search_profile(
        "linkedin", primaere_suchen=[{"keywords": "Pflegefachkraft"},
                                     {"keywords": "Altenpflege"}])
    profil = db.get_portal_search_profile("linkedin")
    assert [s["keywords"] for s in profil["primaere_suchen"]] == ["Pflegefachkraft", "Altenpflege"]
    assert profil["sekundaere_suchen"] == []
    assert profil["nicht_verwenden"] == []
    erg = _call(mcp, "linkedin_lauf_plan")
    assert erg["begriffe"] == ["Pflegefachkraft", "Altenpflege"]
    for fremd in _FREMD:
        assert fremd not in _text(profil), fremd


def test_1147_die_neue_vorgabe_traegt_keinen_fachbegriff(umgebung):
    db, mcp, db_mod = umgebung
    vorgabe = _text(db_mod.Database._LINKEDIN_START)
    for fremd in _FREMD:
        assert fremd not in vorgabe, fremd
    # Die allgemeinen Erfahrungen mit LinkedIn bleiben als Notiz erhalten.
    assert db_mod.Database._LINKEDIN_START["notizen"]


def test_1147_das_lesen_legt_ein_profil_ohne_fremde_begriffe_an(umgebung):
    db, mcp, _ = umgebung
    profil = db.get_portal_search_profile("linkedin")
    assert profil["primaere_suchen"] == []
    assert profil["sekundaere_suchen"] == []
    assert profil["notizen"]
    for fremd in _FREMD:
        assert fremd not in _text(profil), fremd


def _alte_vorgabe_einspielen(db, db_mod, *, bearbeitet=False, geaendert=None):
    """Eine Zeile, wie sie auf Installationen steht, die das Profil je gelesen haben."""
    alt = db_mod.Database._LINKEDIN_VORGABE_ALT
    pid = db.get_active_profile_id()
    jetzt = "2026-06-01T10:00:00"
    spaeter = "2026-07-01T10:00:00" if bearbeitet else jetzt
    liste = dict(alt)
    liste.update(geaendert or {})
    conn = db.connect()
    conn.execute("DELETE FROM portal_search_profiles WHERE portal='linkedin'")
    conn.execute(
        "INSERT INTO portal_search_profiles (profile_id, portal, primaere_suchen_json, "
        "sekundaere_suchen_json, nicht_verwenden_json, notizen, created_at, updated_at) "
        "VALUES (?, 'linkedin', ?, ?, ?, ?, ?, ?)",
        (pid, json.dumps(liste["primaere_suchen"], ensure_ascii=False),
         json.dumps(liste["sekundaere_suchen"], ensure_ascii=False),
         json.dumps(liste["nicht_verwenden"], ensure_ascii=False),
         liste["notizen"], jetzt, spaeter))
    conn.commit()


def test_1147_die_alte_unveraenderte_vorgabe_wird_beim_start_bereinigt(umgebung):
    """Wer das Profil nie angefasst hat, behaelt nicht die Begriffe eines Fremden."""
    db, mcp, db_mod = umgebung
    assert "PDM" in _text(db_mod.Database._LINKEDIN_VORGABE_ALT)  # die Vorlage bleibt zum Erkennen
    _alte_vorgabe_einspielen(db, db_mod)
    assert "PDM" in _text(db.find_portal_search_profile("linkedin"))
    db.initialize()
    profil = db.find_portal_search_profile("linkedin")
    assert profil is not None
    for fremd in _FREMD:
        assert fremd not in _text(profil), fremd
    assert _call(mcp, "linkedin_lauf_plan")["status"] == "leer"


def test_1147_die_bereinigung_laeuft_nur_einmal_und_ist_harmlos(umgebung):
    db, mcp, db_mod = umgebung
    _alte_vorgabe_einspielen(db, db_mod)
    db.initialize()
    erst = db.find_portal_search_profile("linkedin")
    db.initialize()
    zweit = db.find_portal_search_profile("linkedin")
    assert erst == zweit


def test_1147_ein_bearbeitetes_profil_bleibt_unberuehrt(umgebung):
    """Auch wenn der Inhalt zufaellig noch der alten Vorgabe entspricht: wer
    gespeichert hat (updated_at nach created_at), hat es sich zu eigen gemacht."""
    db, mcp, db_mod = umgebung
    _alte_vorgabe_einspielen(db, db_mod, bearbeitet=True)
    db.initialize()
    assert "PDM" in _text(db.find_portal_search_profile("linkedin"))


def test_1147_eigene_aenderungen_an_der_vorgabe_bleiben(umgebung):
    db, mcp, db_mod = umgebung
    _alte_vorgabe_einspielen(
        db, db_mod, geaendert={"primaere_suchen": [{"keywords": "Elektriker"}]})
    db.initialize()
    profil = db.find_portal_search_profile("linkedin")
    assert [s["keywords"] for s in profil["primaere_suchen"]] == ["Elektriker"]


def test_1147_nur_linkedin_wird_bereinigt(umgebung):
    """Ein anderes Portal mit gleichem Inhalt gehoert dem Menschen — die
    Bereinigung gilt der Vorgabe von LinkedIn, sonst nichts."""
    db, mcp, db_mod = umgebung
    pid = db.get_active_profile_id()
    alt = db_mod.Database._LINKEDIN_VORGABE_ALT
    conn = db.connect()
    conn.execute(
        "INSERT INTO portal_search_profiles (profile_id, portal, primaere_suchen_json, "
        "sekundaere_suchen_json, nicht_verwenden_json, notizen, created_at, updated_at) "
        "VALUES (?, 'xing', ?, ?, ?, ?, '2026-06-01T10:00:00', '2026-06-01T10:00:00')",
        (pid, json.dumps(alt["primaere_suchen"], ensure_ascii=False),
         json.dumps(alt["sekundaere_suchen"], ensure_ascii=False),
         json.dumps(alt["nicht_verwenden"], ensure_ascii=False), alt["notizen"]))
    conn.commit()
    db.initialize()
    assert "PDM" in _text(db.find_portal_search_profile("xing"))
