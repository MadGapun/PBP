"""#1189 (B78) - jobtic.com als Browser-Quelle mit eigenem angemeldeten Konto, wie XING.

Die AGB des Betreibers untersagen das automatisierte Auslesen (§ 5.2) und die Aufnahme von Kontaktdaten in fremde
Datenbanken (§ 5.3). Die Quelle laeuft deshalb nur im eigenen, angemeldeten Browser und von Hand gestartet; PBP selbst
ruft diese Seiten nie ab und uebernimmt keine Ansprechpartner. Eine Auflage nur in der Anleitung waere keine Kontrolle
(Lehre L66) - die Tests unten pruefen die Stellen, an denen PBP SELBST etwas tun wuerde.

Alle Firmen, Personen und Adressen in diesen Tests sind erfunden.
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

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src" / "bewerbungs_assistent"
FRONTEND = ROOT / "frontend" / "src"
sys.path.insert(0, str(ROOT / "src"))

PROJEKT = "https://jobtic.com/project/aaaaaaaaa1"
TEXT = ("Aufgaben: Betrieb und Weiterentwicklung der Identitaetsplattform, Anbindung von Anwendungen, Betrieb im "
        "Rechenzentrum. Profil: mehrjaehrige Erfahrung mit Keycloak, Java und Linux, sicherer Umgang mit Protokollen. ") * 4


@pytest.fixture
def env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v18_jobtic_1189_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    db.set_search_criteria("keywords_muss", ["Keycloak", "IAM"])
    yield db, _srv_mod.mcp
    db.close()
    os.environ.pop("BA_DATA_DIR", None)
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _anzahl(db, tabelle):
    return db.connect().execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0]


class _Client:
    """Ein HTTP-Client, der bei JEDEM Aufruf scheitert - wer ihn ruft, ist der Fehler."""
    aufrufe = 0

    def get(self, *a, **kw):
        type(self).aufrufe += 1
        raise AssertionError("PBP hat eine Seite mit Auflage selbst abgerufen")


# ══ das Quellenverzeichnis ═══════════════════════════════════════════════════════════════════════════════════

def test_jobtic_steht_im_quellenverzeichnis_wie_xing():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY, zugriffsart_von
    q = SOURCE_REGISTRY["jobtic"]
    assert zugriffsart_von("jobtic") == "browser_login"
    # Die Sitzung liegt im eigenen Chrome; der Login-Knopf des Dashboards kennt nur LinkedIn und XING.
    assert q["login_erforderlich"] is False
    assert q["konto_noetig"] is True
    assert q["konto_url"] == "https://jobtic.com/register"
    assert q["geschwindigkeit"] == "manuell"
    assert "eigenes jobtic-Konto" in q["login_hinweis"] and "Auslesen" in q["login_hinweis"]
    assert q["auflagen"]["kein_automatischer_abruf"] and q["auflagen"]["keine_kontaktdaten"]
    assert q["auflagen"]["stellenart"] == "freelance"


def test_nur_jobtic_traegt_konto_noetig_ohne_login_knopf():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    mit = {k for k, q in SOURCE_REGISTRY.items() if q.get("konto_noetig")}
    assert mit == {"jobtic"}
    for k in mit:
        assert not SOURCE_REGISTRY[k].get("login_erforderlich"), k


def test_die_quellenzeile_traegt_das_kennzeichen_fuers_dashboard():
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY
    from bewerbungs_assistent.services.search_service import build_source_rows
    zeilen = {z["key"]: z for z in build_source_rows(SOURCE_REGISTRY, [])}
    assert zeilen["jobtic"]["konto_noetig"] is True
    assert zeilen["jobtic"]["zugriffsart"] == "browser_login"
    assert zeilen["jobtic"]["login_erforderlich"] is False
    assert zeilen["xing"]["konto_noetig"] is False


def test_die_adresse_ordnet_die_quelle_zu():
    from bewerbungs_assistent.services.url_to_source import detect_source_from_url, hosts_von
    assert detect_source_from_url(PROJEKT) == "jobtic"
    assert detect_source_from_url("https://www.jobtic.com/search?type=projects&q=Keycloak") == "jobtic"
    assert detect_source_from_url("https://example.com/jobtic.com") == "manuell"
    assert hosts_von("jobtic") == ["jobtic.com"]


def test_jobtic_wird_nie_von_selbst_empfohlen():
    """Eine Quelle mit AGB-Auflage und eigenem Konto schaltet der Mensch selbst ein - im Dialog, mit dem Hinweis."""
    from bewerbungs_assistent.job_scraper import STELLENTYP_QUELLEN
    from bewerbungs_assistent.services import berufsfeld
    assert "jobtic" not in set().union(*STELLENTYP_QUELLEN.values())
    for tabelle in (berufsfeld.FELD_QUELLEN, berufsfeld.FORM_QUELLEN, berufsfeld.NIVEAU_QUELLEN):
        for liste in tabelle.values():
            assert "jobtic" not in liste


# ══ die Auflagen ═════════════════════════════════════════════════════════════════════════════════════════════

def test_die_auflagen_kommen_aus_quelle_oder_adresse():
    from bewerbungs_assistent.services import quellen_auflagen as a
    assert a.kein_automatischer_abruf(quelle="jobtic")
    assert a.kein_automatischer_abruf(url=PROJEKT)
    # eine falsch gesetzte Quelle entbindet nicht: die Adresse entscheidet mit
    assert a.kein_automatischer_abruf(quelle="manuell", url=PROJEKT)
    assert a.kein_automatischer_abruf(quelle="linkedin", url=PROJEKT)
    assert a.keine_kontaktdaten(quelle="manuell", url=PROJEKT)
    assert "§ 5.2" in a.hinweis_fuer_claude(quelle="jobtic")


def test_andere_quellen_haben_keine_auflage():
    from bewerbungs_assistent.services import quellen_auflagen as a
    for quelle, url in (("xing", "https://www.xing.com/jobs/1"), ("gulp", "https://www.gulp.de/p/1"),
                        ("manuell", ""), ("", "https://example.com/job/1"), ("linkedin", "")):
        assert not a.kein_automatischer_abruf(quelle=quelle, url=url), (quelle, url)
        assert a.auflagen(quelle, url) == {}


def test_die_sql_bedingung_schliesst_nur_quellen_mit_auflage_aus():
    from bewerbungs_assistent.services import quellen_auflagen as a
    bedingung, parameter = a.sql_ohne_abruf("url")
    assert bedingung.count("NOT LIKE ?") == len(parameter) >= 1
    assert "%jobtic.com%" in parameter
    assert all("xing" not in p and "gulp" not in p for p in parameter)


def test_die_auflagen_stehen_nur_an_einer_stelle():
    """Eine Fassung (L66): das Quellenverzeichnis. Alles andere liest sie."""
    satz = "Auflagen von jobtic (Nutzungsbedingungen"
    fundorte = [str(p.relative_to(SRC)) for p in SRC.rglob("*.py") if satz in p.read_text(encoding="utf-8-sig")]
    assert fundorte == [str(Path("job_scraper") / "__init__.py")], fundorte


# ══ PBP selbst ruft nichts ab ════════════════════════════════════════════════════════════════════════════════

def test_nachladen_ruft_eine_jobtic_adresse_nie_ab():
    from bewerbungs_assistent.services import nachladen
    client = _Client()
    _Client.aufrufe = 0
    befund = nachladen.beschreibung_holen(PROJEKT, client)
    assert _Client.aufrufe == 0
    assert befund.status == nachladen.NICHT_AUTOMATISCH
    assert not befund.erfolg and not befund.soll_aussortiert_werden
    assert "Nutzungsbedingungen" in befund.klartext() and "stelle_bearbeiten" in befund.klartext()
    assert befund.als_dict()["befund"] == "nicht_automatisch"
    assert nachladen.NICHT_AUTOMATISCH in nachladen.BEFUNDE


def test_nachladen_ruft_andere_adressen_weiter_ab():
    """Gegenprobe: die Sperre gilt der Quelle, nicht dem Nachladen."""
    from bewerbungs_assistent.services import nachladen
    client = _Client()
    _Client.aufrufe = 0
    befund = nachladen.beschreibung_holen("https://example.com/job/1", client)
    assert _Client.aufrufe == 1
    assert befund.status == nachladen.FEHLER


def test_der_url_check_ruft_eine_jobtic_adresse_nie_ab_und_sortiert_nicht_aus():
    from bewerbungs_assistent.services.url_health import HealthStatus, check_job_url_health
    client = _Client()
    _Client.aufrufe = 0
    erg = check_job_url_health(PROJEKT, "Keycloak Consultant", client=client)
    assert _Client.aufrufe == 0
    assert erg.status == HealthStatus.NICHT_GEPRUEFT
    assert erg.should_dismiss is False
    assert "Nutzungsbedingungen" in erg.note


def test_die_auto_engine_waehlt_jobtic_stellen_gar_nicht_erst_aus(env, monkeypatch):
    """Im SQL, nicht danach: sonst fuellen sie das LIMIT und verdraengen dieselben anderen bei jedem Lauf."""
    db, _ = env
    import bewerbungs_assistent.dashboard as dash
    from bewerbungs_assistent.services import nachladen, url_health
    dash._db = db
    stellen = [{"hash": f"jt{i}", "title": f"Projekt {i}", "company": "Nicht angegeben",
                "url": f"https://jobtic.com/project/aaaaaaaa{i:02d}", "source": "jobtic", "description": ""}
               for i in range(6)]
    stellen.append({"hash": "andere1", "title": "Ein anderes Projekt", "company": "Musterfirma GmbH",
                    "url": "https://example.com/job/andere1", "source": "manuell", "description": ""})
    db.save_jobs(stellen)

    geholt, geprueft = [], []

    def holen(url, client, **kw):
        geholt.append(url)
        return nachladen.Befund(status=nachladen.FEHLER)

    def pruefen(url, title=None, **kw):
        geprueft.append(url)
        return url_health.HealthResult(status=url_health.HealthStatus.OK)

    monkeypatch.setattr(nachladen, "beschreibung_holen", holen)
    monkeypatch.setattr(url_health, "check_job_url_health", pruefen)
    dash._run_auto_refetch_descriptions("2026-10-11T08:00:00", max_jobs=2)
    dash._run_url_aging_check("2026-10-11T08:00:00", max_jobs=2)
    assert geholt == ["https://example.com/job/andere1"], geholt
    assert geprueft == ["https://example.com/job/andere1"], geprueft


def test_stellenbeschreibung_nachladen_sagt_den_grund_und_ruft_nichts_ab(env, monkeypatch):
    db, mcp = env
    import httpx
    db.save_jobs([{"hash": "jt-nachladen", "title": "Keycloak Consultant", "company": "Nicht angegeben",
                   "url": PROJEKT, "source": "jobtic", "description": "kurz"}])

    def verboten(self, *a, **kw):
        raise AssertionError("PBP hat eine Seite mit Auflage selbst abgerufen")

    # Ein Abruf scheitert laut: die Sperre muss vor dem ersten `get` greifen.
    monkeypatch.setattr(httpx.Client, "get", verboten)
    res = _call(mcp, "stellenbeschreibung_nachladen", {"stellen_hash": "jt-nachladen"})
    assert res["status"] == "fehler"
    assert res["befund"] == "nicht_automatisch"
    assert "Nutzungsbedingungen" in res["grund"]


# ══ die Anlage ═══════════════════════════════════════════════════════════════════════════════════════════════

def _anlegen(mcp, **kw):
    args = {"titel": "Keycloak Consultant (m/w/d) Remote / ZXXX1", "firma": "Nicht angegeben", "ort": "Hannover",
            "quelle": "jobtic", "url": PROJEKT, "beschreibung": TEXT, "remote": "remote"}
    args.update(kw)
    return _call(mcp, "stelle_manuell_anlegen", args)


KONTAKT = {"kontakt_name": "Erika Beispiel", "kontakt_email": "kontakt@example.com", "kontakt_telefon": "0000 0000000"}


def test_kontaktdaten_aus_jobtic_werden_nicht_uebernommen_und_das_ergebnis_sagt_es(env):
    db, mcp = env
    vorher = _anzahl(db, "contacts")
    res = _anlegen(mcp, **KONTAKT)
    assert res["status"] == "angelegt", res
    assert _anzahl(db, "contacts") == vorher, "ein Ansprechpartner aus jobtic darf nicht entstehen"
    assert "nicht übernommen" in res["kontakt_nicht_uebernommen"]
    assert "kontakt_anlegen" in res["kontakt_nicht_uebernommen"]
    assert "kontakt" not in res or not res.get("kontakt")


def test_die_adresse_genuegt_auch_mit_quelle_manuell(env):
    db, mcp = env
    vorher = _anzahl(db, "contacts")
    res = _anlegen(mcp, quelle="manuell", titel="Cisco Netzwerkadministrator (m/w/d) Musterstadt", **KONTAKT)
    assert res["status"] == "angelegt", res
    assert _anzahl(db, "contacts") == vorher
    assert res["kontakt_nicht_uebernommen"]
    assert db.get_job(res["hash"])["source"] == "jobtic"


def test_die_stellenart_ist_freelance_wenn_nichts_anderes_genannt_ist(env):
    db, mcp = env
    res = _anlegen(mcp, titel="Python Backend Developer (m/w/d) Remote / ZXXX2")
    assert db.get_job(res["hash"])["employment_type"] == "freelance"


def test_jede_andere_quelle_legt_den_kontakt_weiter_an(env):
    """Gegenprobe: die Auflage gilt jobtic, nicht der Anlage."""
    db, mcp = env
    vorher = _anzahl(db, "contacts")
    res = _anlegen(mcp, quelle="linkedin", url="https://www.linkedin.com/jobs/view/4711/",
                   titel="Identity Engineer (m/w/d) Musterstadt", **KONTAKT)
    assert res["status"] == "angelegt", res
    assert _anzahl(db, "contacts") == vorher + 1
    assert "kontakt_nicht_uebernommen" not in res


# ══ der Auftrag an Claude ════════════════════════════════════════════════════════════════════════════════════

def test_quelle_handoff_liefert_such_url_auflagen_und_das_eigene_skript(env):
    from bewerbungs_assistent.services.browser_handoff import REGEL_IM_ZWEIFEL
    _, mcp = env
    res = _call(mcp, "quelle_handoff", {"quelle": "jobtic", "keyword": "Keycloak"})
    assert res["status"] == "handoff"
    assert res["url"] == "https://jobtic.com/search?type=projects&q=Keycloak"
    assert "§ 5.2" in res["auflagen"] and "höchstens zwei Ergebnisseiten" in res["auflagen"]
    assert res["auflagen"] in res["anleitung"] and REGEL_IM_ZWEIFEL in res["anleitung"]
    assert "Bot-Blocker" not in res["anleitung"], "kein 'umgeht Bot-Blocker' bei einer Quelle mit Auflage"
    assert "data-search-bulk-visible" in res["extraction_js"]


def test_quelle_handoff_anderer_quellen_bleibt_wie_es_war(env):
    _, mcp = env
    res = _call(mcp, "quelle_handoff", {"quelle": "gulp", "keyword": "PLM"})
    assert "auflagen" not in res
    assert "umgeht Bot-Blocker" in res["anleitung"]
    assert "data-search-bulk-visible" not in res["extraction_js"]


def test_der_auftrag_fuer_browserlaeufe_nennt_die_auflagen_unter_der_quelle(env):
    from bewerbungs_assistent.services import browser_handoff as bh
    db, _ = env
    text = bh.prompt(bh.browser_quellen(db, auswahl=["jobtic", "stepstone"]))
    assert "jobtic" in text and "quelle_handoff('jobtic'" in text
    assert text.count("Auflagen von jobtic") == 1, "die Auflagen stehen einmal, unter der Quelle"
    assert bh.MARKE_IM_ZWEIFEL in text
    assert "StepStone" in text, "die andere Quelle steht weiter im Auftrag, ohne Auflagen"


def test_das_auswerte_skript_liegt_im_paket_und_die_ci_fuehrt_es_aus():
    skript = SRC / "job_scraper" / "jobtic_extraction.js"
    assert skript.is_file()
    code = skript.read_text(encoding="utf-8")
    assert "data-search-bulk-visible" in code and "data-search-result-card" in code
    # gelesen wird nur die Liste: keine Detailseite, keine Profile, kein Abruf
    assert "fetch(" not in code and "XMLHttpRequest" not in code and "/profile/" not in code
    ci = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "node frontend/src/lib/jobticExtraction.test.mjs" in ci
    assert (FRONTEND / "lib" / "jobticExtraction.test.mjs").is_file()


# ══ das Dashboard ════════════════════════════════════════════════════════════════════════════════════════════

def test_der_aktivierungsdialog_sagt_die_regel_und_nicht_mehr_passende_treffer():
    liste = (FRONTEND / "components" / "SourceSelectionList.jsx").read_text(encoding="utf-8")
    assert "Passende Treffer legt Claude" not in liste
    assert "ob eine taugt, entscheidest du in PBP" in liste
    assert "source.login_hinweis" in liste and "source.konto_url" in liste


def test_das_abzeichen_liest_konto_noetig_und_der_login_knopf_bleibt_bei_login_erforderlich():
    badges = (FRONTEND / "lib" / "quellenBadges.js").read_text(encoding="utf-8")
    assert "q.login_erforderlich || q.konto_noetig" in badges
    liste = (FRONTEND / "components" / "SourceSelectionList.jsx").read_text(encoding="utf-8")
    assert "autoStartLogin: checked && Boolean(source.login_erforderlich) && !loginReady" in liste
    assert "konto_noetig" not in liste, "der Login-Knopf des alten Weges darf konto_noetig nicht lesen"


# ══ Nachtraege: die zweite Absicherung, die falsch gesetzte Quelle, das Skript unter Node ═══════════════════════

def test_der_bestands_nachzug_ueberspringt_jobtic_stellen_ohne_fehlversuch(env):
    """`holen` bekommt Hashes von jedem Aufrufer (Suchlauf, Bestand): auch dort ist die Adresse kein Kandidat."""
    db, _ = env
    from bewerbungs_assistent.services import text_nachzug
    db.save_jobs([{"hash": "jt-nz", "title": "Keycloak Consultant", "company": "Nicht angegeben",
                   "url": PROJEKT, "source": "jobtic", "description": ""}])
    client = _Client()
    _Client.aufrufe = 0
    erg = text_nachzug.holen(db, ["jt-nz"], max_jobs=5, client=client)
    assert _Client.aufrufe == 0
    assert erg["kandidaten"] == 0 and erg["fehlgeschlagen"] == 0 and erg["offen"] == 0
    assert text_nachzug._fehlversuche(db, "jt-nz") == 0


def test_eine_falsch_gesetzte_quelle_entbindet_nicht_von_der_auflage(env):
    """`quelle='linkedin'` mit einer jobtic-Adresse: die Adresse entscheidet mit."""
    db, mcp = env
    vorher = _anzahl(db, "contacts")
    res = _anlegen(mcp, quelle="linkedin", titel="Linux Administrator (m/w/d) Musterstadt", **KONTAKT)
    assert res["status"] == "angelegt", res
    assert _anzahl(db, "contacts") == vorher
    assert res["kontakt_nicht_uebernommen"]


def test_das_auswerte_skript_besteht_seinen_node_test():
    """Die CI fuehrt den Node-Test selbst aus; hier laeuft er mit, wo Node da ist - damit ein Fehler im Skript auch
    die Python-Suite und die Gegenprobe erreicht."""
    import shutil
    import subprocess
    node = shutil.which("node")
    if not node:
        pytest.skip("Node ist nicht installiert")
    erg = subprocess.run([node, str(FRONTEND / "lib" / "jobticExtraction.test.mjs")], capture_output=True,
                         text=True, encoding="utf-8", errors="replace", cwd=str(ROOT), timeout=120,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert erg.returncode == 0, (erg.stdout or "")[-1500:] + (erg.stderr or "")[-500:]


def test_die_qualitaetspruefung_nennt_jobtic_nicht_geprueft_statt_ok(env, monkeypatch):
    db, mcp = env
    import httpx
    db.save_jobs([{"hash": "jt-qp", "title": "Keycloak Consultant", "company": "Nicht angegeben",
                   "url": PROJEKT, "source": "jobtic", "description": TEXT}])

    def verboten(self, *a, **kw):
        raise AssertionError("PBP hat eine Seite mit Auflage selbst abgerufen")

    monkeypatch.setattr(httpx.Client, "get", verboten)
    res = _call(mcp, "stellen_qualitaet_pruefen", {"max_stellen": 10, "nur_problematische": False})
    assert res["befunde"].get("url_nicht_geprueft") == 1, res["befunde"]
    assert "url_404" not in res["befunde"] and "url_expired" not in res["befunde"]
