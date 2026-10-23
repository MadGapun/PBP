"""#1250 - die Automatik sortiert zurueckgeholte und empfohlene Stellen aus.

Gemeldet am 19.10.2026 beim Abgleich der aktiven Stellen
(`aussortier_protokoll(zeitfenster='7tage')`). Vier Muster, je ein Block:

1. Eine vom Menschen zurueckgeholte Stelle mit Urteil BEDINGT fiel drei Tage
   spaeter `profil_match_negativ` durch die lokale KI. Der Kandidatenfilter
   fragte nur `dismiss_reason`, und den loescht das Zurueckholen.
2. Drei Kopien derselben Anzeige, keine blieb aktiv: die Kopie mit Volltext
   und Urteil EMPFOHLEN fiel mit der KI-Begruendung "Grund: duplikat" (die KI
   sprach den Grund der Kopie aus ihren Beispielen nach).
3. Die Wiedergaenger-Regel "nach Fachgebiet" vererbte `befristet` ueber das
   Titelwort "data" an eine unbefristete Anzeige, `falsches_system` ueber "mdm".
4. Die MDM-Stelle fiel mit 0 Zeichen Anzeigentext.

Die Faelle unten bilden die vier Muster mit fiktiven Firmen nach; die echten
Kennungen stehen im Issue. Alle Datenbanken sind isoliert (BA_DATA_DIR).
"""
from __future__ import annotations

import logging
import os
from types import SimpleNamespace

import pytest

TEXT = ("Ab sofort, in Vollzeit und unbefristet. Aufgaben: Pflege der Stammdaten, "
        "Abstimmung mit den Fachbereichen, Aufbau von Pruefregeln und Berichten. "
        "Anforderungen: mehrjaehrige Erfahrung, sicheres Deutsch und Englisch.")


class _KI:
    """Testdoppel der lokalen KI: sagt zu JEDER Stelle PASST_NICHT."""

    def __init__(self, grund="Passt fachlich nicht"):
        self.grund = grund
        self.gefragt = []

    def get_status(self, force_refresh=False):
        return SimpleNamespace(ollama_available=True, available_models=["m"],
                               user_state="active", selected_model="m")

    def warmup(self):
        return {"status": "warm", "duration_sec": 0}

    def run(self, kind, payload):
        self.gefragt.append(payload["job_title"])
        return SimpleNamespace(success=True, fallback_message="",
                               payload={"decision": "PASST_NICHT",
                                        "reason": self.grund})


@pytest.fixture
def db(tmp_path, monkeypatch):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    d = Database(db_path=tmp_path / "test.db")
    d.initialize()
    assert str(tmp_path) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test 1250"})
    d.ki = _KI()
    from bewerbungs_assistent.services import llm_service
    monkeypatch.setattr(llm_service, "get_llm_service", lambda _db=None: d.ki)
    yield d
    d.close()
    os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, kennung, titel, firma="Musterwerk Nord GmbH", *, text=TEXT,
            grund=None, quelle="stepstone", score=20):
    db.save_jobs([{
        "hash": kennung, "title": titel, "company": firma, "location": "Hamburg",
        "url": f"https://example.com/1250/{kennung}", "source": quelle,
        "description": text, "score": score,
    }])
    voll = db.resolve_job_hash(kennung)
    if grund:
        assert db.dismiss_job(voll, grund)
    return voll


def _zeile(db, voll):
    return dict(db.connect().execute(
        "SELECT * FROM jobs WHERE hash=?", (voll,)).fetchone())


def _aktiv(db, voll):
    return bool(_zeile(db, voll)["is_active"])


# -- 1. Zurueckgeholt oder beurteilt: keine Automatik ---------------------


def test_1250_zurueckgeholte_stelle_bekommt_die_ki_nicht_mehr(db):
    """Muster 1: aussortiert, vom Menschen zurueckgeholt, naechster KI-Lauf."""
    from bewerbungs_assistent.services import auto_aussortierung as aa
    voll = _stelle(db, "k1250", "Projektleiter Entwicklung (m/w/d)")
    assert db.dismiss_job(voll, "profil_match_negativ", herkunft="automatik")
    assert db.restore_job(voll)
    assert _zeile(db, voll)["zurueckgeholt_am"], "Das Zurueckholen hinterlaesst keine Spur."
    frei = _stelle(db, "k1251", "Sachbearbeiter Einkauf (m/w/d)")

    erg = aa.aussortieren(db, max_stellen=30)

    assert "Projektleiter Entwicklung (m/w/d)" not in db.ki.gefragt
    assert _aktiv(db, voll), "Die KI hat die zurueckgeholte Stelle wieder aussortiert."
    assert not _aktiv(db, frei), "Gegenprobe: eine ungeschuetzte Stelle beurteilt die KI weiter."
    assert erg.get("uebersprungen_geschuetzt") == 1


def test_1250_alles_geschuetzt_die_meldung_sagt_warum(db):
    from bewerbungs_assistent.services import auto_aussortierung as aa
    voll = _stelle(db, "k1252", "Projektleiter Entwicklung (m/w/d)",
                   grund="falsches_fachgebiet")
    db.restore_job(voll)
    erg = aa.aussortieren(db, max_stellen=30)
    assert erg["status"] == "leer"
    assert erg.get("uebersprungen_geschuetzt") == 1


def test_1250_die_ki_meldet_keine_aussortierung_die_nicht_geschah(db, monkeypatch):
    """Rueckgabewert auswerten (L11): weist das Nadeloehr ab, ist die Stelle
    nicht aussortiert und wird nicht so gezaehlt."""
    from bewerbungs_assistent.services import auto_aussortierung as aa
    voll = _stelle(db, "k1253", "Sachbearbeiter Einkauf (m/w/d)")
    monkeypatch.setattr(db, "dismiss_job", lambda *a, **k: False)
    erg = aa.aussortieren(db, max_stellen=30)
    assert erg["passt_nicht"] == 0 and erg["unsicher"] == 1, erg
    assert _aktiv(db, voll)


@pytest.mark.parametrize("urteil", ["EMPFOHLEN", "BEDINGT"])
def test_1250_gelesenes_urteil_schuetzt_vor_der_ki(db, urteil):
    from bewerbungs_assistent.services import auto_aussortierung as aa
    voll = _stelle(db, f"u{urteil}", "Global Data Steward (m/w/d)")
    assert db.set_job_analysis(voll, urteil, "gelesen und beurteilt")

    aa.aussortieren(db, max_stellen=30)

    assert _aktiv(db, voll), f"Urteil {urteil} wurde von der KI ueberstimmt."
    assert "Global Data Steward (m/w/d)" not in db.ki.gefragt


@pytest.mark.parametrize("urteil", ["NICHT_EMPFOHLEN", "NICHT_BEURTEILBAR"])
def test_1250_andere_urteile_schuetzen_nicht(db, urteil):
    """Gegenrichtung: nur EMPFOHLEN und BEDINGT sind ein Wort fuer die Stelle."""
    from bewerbungs_assistent.services import auto_aussortierung as aa
    voll = _stelle(db, f"n{urteil}", "Sachbearbeiter Einkauf (m/w/d)")
    assert db.set_job_analysis(voll, urteil, "gelesen")
    aa.aussortieren(db, max_stellen=30)
    assert not _aktiv(db, voll)


def test_1250_das_nadeloehr_weist_die_automatik_ab(db):
    """Doppelter Boden: auch ein Weg, der die Regel nicht vorher fragt."""
    zurueck = _stelle(db, "z1", "Projektleiter Entwicklung (m/w/d)",
                      grund="falsches_fachgebiet")
    assert db.restore_job(zurueck)
    empfohlen = _stelle(db, "z2", "Global Data Steward (m/w/d)")
    db.set_job_analysis(empfohlen, "EMPFOHLEN", "passt")
    frei = _stelle(db, "z3", "Sachbearbeiter Einkauf (m/w/d)")

    assert not db.dismiss_job(zurueck, "profil_match_negativ", herkunft="automatik")
    assert not db.dismiss_job(empfohlen, "falsches_fachgebiet", herkunft="automatik")
    assert _aktiv(db, zurueck) and _aktiv(db, empfohlen)
    assert db.dismiss_job(frei, "profil_match_negativ", herkunft="automatik")
    assert not _aktiv(db, frei)


@pytest.mark.parametrize("grund", ["veraltet_url", "bewerbung_erstellt"])
def test_1250_tatsachen_gelten_auch_fuer_geschuetzte_stellen(db, grund):
    """Eine entfernte Anzeige und die eigene Bewerbung sind kein Urteil."""
    voll = _stelle(db, f"t{grund}", "Global Data Steward (m/w/d)")
    db.set_job_analysis(voll, "EMPFOHLEN", "passt")
    assert db.dismiss_job(voll, grund, herkunft="automatik")
    assert not _aktiv(db, voll)


def test_1250_der_mensch_darf_immer(db):
    voll = _stelle(db, "m1", "Global Data Steward (m/w/d)")
    db.set_job_analysis(voll, "EMPFOHLEN", "passt")
    assert db.dismiss_job(voll, "befristet")
    assert not _aktiv(db, voll)


def test_1250_der_vermerk_ueberlebt_den_naechsten_suchlauf(db):
    """`save_jobs` schreibt mit INSERT OR REPLACE (DoD 8e)."""
    voll = _stelle(db, "s1", "Projektleiter Entwicklung (m/w/d)",
                   grund="falsches_fachgebiet")
    db.restore_job(voll)
    vorher = _zeile(db, voll)["zurueckgeholt_am"]
    _stelle(db, "s1", "Projektleiter Entwicklung (m/w/d)")
    assert _zeile(db, voll)["zurueckgeholt_am"] == vorher
    assert "zurueckgeholt_am" in db._BEWAHREN


def test_1250_eine_reparatur_ist_kein_wort_des_menschen(db):
    voll = _stelle(db, "r1", "Projektleiter Entwicklung (m/w/d)",
                   grund="falsches_fachgebiet")
    assert db.restore_job(voll, durch_mensch=False)
    assert _aktiv(db, voll)
    assert not _zeile(db, voll)["zurueckgeholt_am"]


@pytest.mark.parametrize("weg", ["mcp", "dashboard"])
def test_1250_jeder_weg_des_menschen_setzt_den_vermerk(db, weg, monkeypatch):
    voll = _stelle(db, f"w{weg}", "Projektleiter Entwicklung (m/w/d)",
                   grund="falsches_fachgebiet")
    if weg == "mcp":
        werkzeug = _werkzeuge(db)["stelle_reaktivieren"]
        assert werkzeug(job_hash=voll)["status"] == "reaktiviert"
    else:
        from fastapi.testclient import TestClient

        from bewerbungs_assistent import dashboard
        monkeypatch.setattr(dashboard, "_db", db)
        antwort = TestClient(dashboard.app).post("/api/jobs/restore",
                                                 json={"hash": voll})
        assert antwort.status_code == 200, antwort.text
    assert _zeile(db, voll)["zurueckgeholt_am"]


class _FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self, name=None, **_kwargs):
        def decorator(fn):
            self.tools[name or fn.__name__] = fn
            return fn
        return decorator


def _werkzeuge(db):
    from bewerbungs_assistent.tools.jobs import register
    mcp = _FakeMCP()
    register(mcp, db, logging.getLogger("test"))
    return mcp.tools


def test_1250_eigenes_aussortieren_loescht_den_vermerk(db):
    """Das letzte Wort des Menschen zaehlt: sortiert er selbst aus, lebt ein
    frueheres Zurueckholen nach einer Reparatur nicht wieder auf."""
    voll = _stelle(db, "e1250", "Projektleiter Entwicklung (m/w/d)",
                   grund="falsches_fachgebiet")
    db.restore_job(voll)
    assert _zeile(db, voll)["zurueckgeholt_am"]
    assert db.dismiss_job(voll, "zu_junior")
    assert not _zeile(db, voll)["zurueckgeholt_am"]
    db.restore_job(voll, durch_mensch=False)
    assert db.dismiss_job(voll, "profil_match_negativ", herkunft="automatik")


def test_1250_der_rueckweg_eines_statuswechsels_ist_kein_wort_des_menschen(db):
    from bewerbungs_assistent.services import status_rueckweg as rw
    voll = _stelle(db, "s1250", "Projektleiter Entwicklung (m/w/d)",
                   grund="bewerbung_erstellt")
    aid = db.add_application({"title": "A", "company": "Musterwerk Nord GmbH",
                              "status": "beworben"})
    assert rw.zuruecknehmen(db, aid, {"vorher": "offen", "stelle_aussortiert": voll},
                            profile_id=db.get_active_profile_id())
    assert _aktiv(db, voll)
    assert not _zeile(db, voll)["zurueckgeholt_am"]


def test_1250_wiedergaenger_werkzeug_respektiert_den_schutz(db):
    """`stelle_wiedergaenger_pruefen(auto_aussortieren=True)` meldete
    "auto_aussortiert", ohne den Rueckgabewert zu lesen."""
    for i in range(3):
        _stelle(db, f"h{i}", f"Datenmanager Stammdaten {i} (m/w/d)",
                grund="falsches_fachgebiet")
    ziel = _stelle(db, "hziel", "Datenmanager Stammdaten neu (m/w/d)")
    db.set_job_analysis(ziel, "BEDINGT", "auf Wunsch aktiv gehalten")

    erg = _werkzeuge(db)["stelle_wiedergaenger_pruefen"](
        job_hash=ziel, auto_aussortieren=True)

    assert erg["aktion"] == "geschuetzt", erg
    assert _aktiv(db, ziel)


# -- 2. Dubletten: genau eine Kopie bleibt ---------------------------------


def test_1250_eine_ki_begruendung_duplikat_sortiert_nicht_aus(db):
    from bewerbungs_assistent.services import auto_aussortierung as aa
    db.ki.grund = "Grund: duplikat"
    voll = _stelle(db, "d1", "Global Data Steward (m/w/d)")
    erg = aa.aussortieren(db, max_stellen=30)
    assert _aktiv(db, voll), "Die KI hat eine Stelle als Dublette aussortiert."
    assert erg["passt_nicht"] == 0 and erg["unsicher"] == 1


def test_1250_die_behaltene_kopie_bekommt_den_volltext(db):
    """Original nur mit Titel, die Dublette bringt den Text: es bleibt genau
    eine Kopie aktiv, und sie traegt den Volltext."""
    original = _stelle(db, "o1", "Global Data Steward (m/w/d)", text="")
    kopie = _stelle(db, "o2", "Global Data Steward (m/w/d)")

    assert _aktiv(db, original) and not _aktiv(db, kopie)
    assert _zeile(db, kopie)["dismiss_reason"] == "duplikat"
    assert len((_zeile(db, original)["description"] or "").strip()) >= 50, (
        "Die aktive Kopie ist die ohne Anzeigentext.")
    assert "Original" in (_zeile(db, kopie)["dismiss_note"] or "")


def test_1250_ein_lauf_ohne_text_loescht_den_text_nicht(db):
    """Der uebernommene (oder nachgeladene) Text uebersteht einen erneuten
    Ingest derselben Stelle ohne Text - `description` steht in der INSERT-Liste."""
    original = _stelle(db, "t1", "Global Data Steward (m/w/d)", text="")
    _stelle(db, "t2", "Global Data Steward (m/w/d)")
    _stelle(db, "t1", "Global Data Steward (m/w/d)", text="")
    assert len((_zeile(db, original)["description"] or "").strip()) >= 50


def test_1250_ein_original_mit_text_behaelt_seinen(db):
    original = _stelle(db, "p1", "Global Data Steward (m/w/d)")
    _stelle(db, "p2", "Global Data Steward (m/w/d)",
            text="Ganz anderer Text, aber auch lang genug fuer eine Bewertung hier.")
    assert _zeile(db, original)["description"] == TEXT


def test_1250_drei_kopien_es_bleibt_genau_eine(db):
    """Muster 2 nachgestellt: Kopie mit Volltext und Urteil EMPFOHLEN, eine
    Dublette beim Ingest, danach ein Lauf der KI, die "duplikat" sagt."""
    from bewerbungs_assistent.services import auto_aussortierung as aa
    a = _stelle(db, "l1", "Global Data Steward (m/w/d)")
    db.set_job_analysis(a, "EMPFOHLEN", "gelesen, passt")
    b = _stelle(db, "l2", "Global Data Steward (m/w/d)", text="")
    db.ki.grund = "Grund: duplikat"
    aa.aussortieren(db, max_stellen=30)
    aktiv = [h for h in (a, b) if _aktiv(db, h)]
    assert aktiv == [a], f"Aktiv geblieben: {aktiv}"


def test_1250_grund_und_notiz_einer_dublette_passen_zusammen(db):
    """Gemessen auf einer Kopie: Grund `duplikat`, Notiz der Wiedergaenger-
    Automatik. Hat die Dubletten-Erkennung entschieden, steht ihre Notiz da."""
    original = _stelle(db, "n1", "Global Data Steward (m/w/d)")
    db.save_jobs([{
        "hash": "n2", "title": "Global Data Steward (m/w/d)",
        "company": "Musterwerk Nord GmbH", "url": "https://example.com/1250/n2",
        "source": "stepstone", "description": TEXT, "score": 20,
        "is_active": 0, "dismiss_reason": "auto:befristet:wiedergaenger",
        "dismiss_note": "Wiedergänger nach Fachgebiet: 13x mit Grund 'befristet'.",
    }])
    kopie = _zeile(db, db.resolve_job_hash("n2"))
    assert kopie["dismiss_reason"] == "duplikat"
    assert "Duplikat von" in kopie["dismiss_note"], kopie["dismiss_note"]
    assert _aktiv(db, original)


def test_1250_eine_dublette_ist_kein_beispiel_fuer_die_ki(db):
    """Die Echokammer aus Muster 2 (seit #1239 geschlossen, hier festgehalten)."""
    _stelle(db, "e1", "Global Data Steward (m/w/d)")
    _stelle(db, "e2", "Global Data Steward (m/w/d)")
    beispiele = db.get_recent_user_dismissals(limit=10)
    assert not any("duplikat" in (b.get("dismiss_reason") or "") for b in beispiele)


# -- 3. Nach Fachgebiet wandern nur Fachgebiet und Branche -------------------


def test_1250_nur_fachgebiet_und_branche_wandern():
    from bewerbungs_assistent.services import stellen_automatik as sa
    assert sa.UEBERTRAGBARE_GRUENDE == {"falsches_fachgebiet", "falsche_branche"}


@pytest.mark.parametrize("grund", [
    "befristet", "zeitarbeit", "gehalt_zu_niedrig", "zu_weit_entfernt",
    "duplikat", "bewerbung_erstellt", "bereits_beworben", "falsches_system",
    "zu_junior", "zu_senior", "kein_hochschulabschluss",
    "unpassendes_arbeitsmodell", "firma_uninteressant",
])
def test_1250_anzeigenbezogene_gruende_wandern_nicht(db, grund):
    """Muster 3: 13 befristete Stellen anderer Firmen mit "data" im Titel."""
    from bewerbungs_assistent.services import stellen_automatik as sa
    for i in range(13):
        _stelle(db, f"b{grund[:6]}{i}", f"Data Analyst Vertrieb {i} (m/w/d)",
                firma=f"Firma {i} GmbH", grund=grund)
    neu = {"hash": f"neu{grund[:8]}", "title": "Global Data Steward (m/w/d)",
           "company": "Musterwerk Sued GmbH", "description": TEXT}
    erg = sa.entscheide(db, neu)
    assert erg["aktion"] == "anlegen", f"'{grund}' wurde vererbt: {erg}"


@pytest.mark.parametrize("grund", ["falsches_fachgebiet", "falsche_branche"])
def test_1250_fachliche_gruende_wandern_weiter(db, grund):
    """Gegenrichtung: der Gruendungsfall aus #941 bleibt (#991 MERKE 3)."""
    from bewerbungs_assistent.services import stellen_automatik as sa
    for i in range(3):
        _stelle(db, f"f{grund[:8]}{i}", f"CRM Manager Vertrieb {i} (m/w/d)",
                firma=f"Firma {i} GmbH", grund=grund)
    neu = {"hash": f"crm{grund[:8]}", "title": "CRM Manager Vertrieb neu (m/w/d)",
           "company": "Musterwerk Sued GmbH", "description": TEXT}
    assert sa.entscheide(db, neu)["aktion"] == "aussortieren"


def test_1250_reparatur_findet_und_holt_vererbte_vertragsgruende(db):
    """`automatik_uebertragungen_pruefen` liest dieselbe Menge: eine Stelle,
    die `befristet` "nach Fachgebiet" bekam, ist ein Fall fuer die Ruecknahme."""
    voll = _stelle(db, "x1", "Global Data Steward (m/w/d)")
    db.dismiss_job(voll, "auto:befristet:wiedergaenger", herkunft="automatik",
                   notiz="Wiedergänger nach Fachgebiet: 13x mit Grund "
                         "'befristet' aussortiert (gemeinsam: data).")
    werkzeug = _werkzeuge(db)["automatik_uebertragungen_pruefen"]
    vorschau = werkzeug(dry_run=True)
    assert vorschau["betroffen"] == 1, vorschau
    assert vorschau["stichprobe"][0]["befund"] == "grund_nicht_uebertragbar"
    erg = werkzeug(dry_run=False)
    assert erg["zurueckgeholt"] == 1
    assert _aktiv(db, voll)
    assert not _zeile(db, voll)["zurueckgeholt_am"], (
        "Die Reparatur hat sich als Wort des Menschen eingetragen.")


# -- 4. Ohne Anzeigentext kein automatisches Aussortieren --------------------


def test_1250_fachgebiet_ohne_text_bleibt_ein_verdacht(db):
    """Muster 4: die MDM-Stelle mit 0 Zeichen."""
    from bewerbungs_assistent.services import stellen_automatik as sa
    for i in range(3):
        _stelle(db, f"q{i}", f"Teamleiter MDM Stammdaten {i} (m/w/d)",
                firma=f"Firma {i} GmbH", grund="falsches_fachgebiet")
    neu = {"hash": "qneu", "title": "Teamleiter Materialstammdaten MDM (m/w/d)",
           "company": "Musterwerk Sued GmbH", "description": ""}
    erg = sa.entscheide(db, neu)
    assert erg["aktion"] == "anlegen", erg
    assert erg["verdacht_ohne_text"] == "falsches_fachgebiet"
    assert "nachladen" in erg["hinweis"]


def test_1250_dieselbe_firma_ortsgrund_braucht_keinen_text(db):
    """Gegenrichtung (zweiter Leser): in Stufe 1 haengt die Entfernung am
    Ort, nicht am Anzeigentext - dort bleibt es beim Aussortieren."""
    from bewerbungs_assistent.services import stellen_automatik as sa
    for i in range(2):
        _stelle(db, f"o{i}", f"Datenmanager Stammdaten {i} (m/w/d)",
                grund="zu_weit_entfernt")
    neu = {"hash": "oneu", "title": "Datenmanager Stammdaten neu (m/w/d)",
           "company": "Musterwerk Nord GmbH", "location": "Hamburg",
           "description": ""}
    assert sa.entscheide(db, neu)["aktion"] == "aussortieren"


def test_1250_dieselbe_firma_ohne_text_bleibt_ein_verdacht(db):
    """Auch Stufe 1 (gleiche Firma) urteilt aus dem Titel."""
    from bewerbungs_assistent.services import stellen_automatik as sa
    for i in range(2):
        _stelle(db, f"g{i}", f"Datenmanager Stammdaten {i} (m/w/d)",
                grund="falsches_fachgebiet")
    neu = {"hash": "gneu", "title": "Datenmanager Stammdaten neu (m/w/d)",
           "company": "Musterwerk Nord GmbH", "description": "kurz"}
    assert sa.entscheide(db, neu)["aktion"] == "anlegen"
    neu["description"] = TEXT
    assert sa.entscheide(db, neu)["aktion"] == "aussortieren"


def test_1250_anwenden_zaehlt_den_verdacht_und_legt_aktiv_an(db):
    from bewerbungs_assistent.services import stellen_automatik as sa
    for i in range(3):
        _stelle(db, f"v{i}", f"Teamleiter MDM Stammdaten {i} (m/w/d)",
                firma=f"Firma {i} GmbH", grund="falsches_fachgebiet")
    neu = {"hash": "vneu", "title": "Teamleiter Materialstammdaten MDM (m/w/d)",
           "company": "Musterwerk Sued GmbH", "description": "",
           "url": "https://example.com/1250/vneu", "source": "stepstone"}
    erg = sa.anwenden(db, [neu])
    assert erg["zaehler"]["wiedergaenger_ohne_text"] == 1
    assert erg["zaehler"]["automatisch_aussortiert"] == 0
    db.save_jobs(erg["jobs"])
    assert _aktiv(db, db.resolve_job_hash("vneu"))


def test_1250_eine_vorhandene_stelle_zaehlt_nicht_als_aussortiert(db):
    """`save_jobs` uebernimmt `is_active=0` nur fuer NEUE Stellen - die
    Abschlussmeldung zaehlte trotzdem."""
    from bewerbungs_assistent.services import stellen_automatik as sa
    for i in range(3):
        _stelle(db, f"y{i}", f"CRM Manager Vertrieb {i} (m/w/d)",
                firma=f"Firma {i} GmbH", grund="falsches_fachgebiet")
    vorhanden = _stelle(db, "yalt", "CRM Manager Vertrieb neu (m/w/d)",
                        firma="Musterwerk Sued GmbH")
    db.restore_job(vorhanden)
    erneut = {"hash": "yalt", "title": "CRM Manager Vertrieb neu (m/w/d)",
              "company": "Musterwerk Sued GmbH", "description": TEXT,
              "url": "https://example.com/1250/yalt", "source": "stepstone"}
    erg = sa.anwenden(db, [erneut])
    assert erg["zaehler"]["automatisch_aussortiert"] == 0
    assert erg["jobs"] and erg["jobs"][0].get("is_active") != 0


def test_1250_der_trichter_kennt_den_neuen_zaehler():
    from bewerbungs_assistent.job_scraper import _STUFEN_TEXT
    assert "wiedergaenger_ohne_text" in _STUFEN_TEXT


def test_1250_eine_frage_eine_funktion_fuer_den_anzeigentext():
    """Automatik und lokale KI fragen dieselbe Schwelle (L1)."""
    from pathlib import Path
    src = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent" / "services"
    for datei in ("stellen_automatik.py", "auto_aussortierung.py"):
        quelle = (src / datei).read_text(encoding="utf-8")
        assert "hat_beschreibung" in quelle, datei
        assert ".strip()) < 50" not in quelle, datei
