"""Welle 5 aus #1087 — die Claude-Seite (H21, H22, H25, H28-H32).

* H21 (G1, G14): Werkzeugkatalog mit Tags, Kurzbeschreibungen ohne
  Geschichte, Parametertexten im Eingabeschema und einem Expertenmodus,
  der Wartungs- und Entwicklerwerkzeuge ausblendet.
"""
import ast
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
PAKET = _repo() / "src" / "bewerbungs_assistent"


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_g1087w5_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def ohne_expertenmodus(monkeypatch):
    """Der Server, wie ihn ein Mensch ohne Einstellung startet."""
    monkeypatch.delenv("BA_EXPERTENMODUS", raising=False)
    tmpdir = tempfile.mkdtemp(prefix="pbp_g1087w5x_")
    monkeypatch.setenv("BA_DATA_DIR", tmpdir)
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    if isinstance(erg, dict) and set(erg) == {"result"}:
        return erg["result"]
    return erg


def _werkzeuge(mcp):
    return asyncio.run(mcp.list_tools())


# ══ H21 — Werkzeugkatalog ═══════════════════════════════════════════════

def test_h21_jedes_werkzeug_hat_genau_einen_tag(umgebung):
    from bewerbungs_assistent.services import werkzeug_katalog as k
    _db, mcp = umgebung
    werkzeuge = _werkzeuge(mcp)
    assert len(werkzeuge) > 200
    for w in werkzeuge:
        tags = set(w.tags) & set(k.TAGS)
        assert len(tags) == 1, (w.name, w.tags)


def test_h21_listen_nennen_nur_registrierte_werkzeuge(umgebung):
    from bewerbungs_assistent.services import werkzeug_katalog as k
    _db, mcp = umgebung
    namen = {w.name for w in _werkzeuge(mcp)}
    for liste in (k.WARTUNG, k.ENTWICKLER, k.EINSTELLUNG, set(k.KURZ)):
        fremd = set(liste) - namen
        assert not fremd, f"nicht registriert: {fremd}"


def test_h21_beschreibungen_kurz_und_ohne_geschichte(umgebung):
    _db, mcp = umgebung
    werkzeuge = _werkzeuge(mcp)
    zu_lang = [(w.name, len(w.description)) for w in werkzeuge if len(w.description or "") > 600]
    assert not zu_lang, zu_lang
    geschichte = [w.name for w in werkzeuge
                  if re.search(r"#\d{3,4}|\bv1\.\d|beta\.\d", w.description or "")]
    assert not geschichte, geschichte
    leer = [w.name for w in werkzeuge if len(w.description or "") < 20]
    assert not leer, leer
    gesamt = sum(len(w.description or "") for w in werkzeuge)
    assert gesamt < 100_000, gesamt


def test_h21_kernweg_hat_zweck_und_einsatz_in_300_bis_600_zeichen():
    from bewerbungs_assistent.services import werkzeug_katalog as k
    for name, text in k.KURZ.items():
        assert 300 <= len(text) <= 600, (name, len(text))
        assert not re.search(r"#\d{3}|\bv1\.\d", text), name


def test_h21_parametertexte_stehen_im_eingabeschema(umgebung):
    _db, mcp = umgebung

    async def _tool():
        return await mcp.get_tool("stellen_anzeigen")
    t = asyncio.run(_tool())
    props = t.parameters["properties"]
    assert "aussortiert" in props["filter"].get("description", "")
    assert not re.search(r"#\d{3}", props["nur_beurteilt"].get("description", ""))


def test_h21_generator_nimmt_die_geschichte_heraus():
    from bewerbungs_assistent.services import werkzeug_katalog as k
    doc = ("Zeigt die Stellen an.\n\nSeit v1.7.12 (#827) sinken k.o.-Stellen ans Ende. "
           "Nutze stelle_bewerten fuer einzelne Stellen.\n\nArgs:\n"
           "    filter: 'aktiv' oder 'alle' (#671)\n")
    text = k.beschreibung("irgendwas", doc)
    assert "Zeigt die Stellen an." in text
    assert "stelle_bewerten" in text
    assert "#827" not in text and "v1.7" not in text
    assert k.parameter_texte(doc) == {"filter": "'aktiv' oder 'alle'"}


def test_h21_ohne_expertenmodus_sind_wartung_und_entwickler_ausgeblendet(ohne_expertenmodus):
    from bewerbungs_assistent.services import werkzeug_katalog as k
    _db, mcp = ohne_expertenmodus
    namen = {w.name for w in _werkzeuge(mcp)}
    assert not (k.WARTUNG | k.ENTWICKLER) & namen
    assert {"stellen_anzeigen", "expertenmodus_setzen", "suchkriterien_setzen"} <= namen


def test_h21_expertenmodus_zeigt_sie_wieder(ohne_expertenmodus):
    from bewerbungs_assistent.services import werkzeug_katalog as k
    db, mcp = ohne_expertenmodus
    erg = _call(mcp, "expertenmodus_setzen", {"an": True})
    assert erg["expertenmodus"] is True
    assert db.get_setting("expertenmodus") is True
    namen = {w.name for w in _werkzeuge(mcp)}
    assert (k.WARTUNG | k.ENTWICKLER) <= namen
    _call(mcp, "expertenmodus_setzen", {"an": False})
    namen = {w.name for w in _werkzeuge(mcp)}
    assert not (k.WARTUNG | k.ENTWICKLER) & namen


def test_h21_server_wendet_die_sichtbarkeit_nach_dem_registrieren_an():
    """DoD 8c: der Ausblender wird im Server wirklich aufgerufen."""
    quelle = (PAKET / "server.py").read_text(encoding="utf-8")
    reg = quelle.index("register_all(mcp, db, logger)")
    anw = quelle.index("sichtbarkeit_anwenden(mcp, _werkzeug_katalog.beim_start_sichtbar(db))")
    assert reg < anw


def test_h21_register_all_setzt_tag_und_beschreibung():
    quelle = (PAKET / "tools" / "__init__.py").read_text(encoding="utf-8")
    rumpf = quelle[quelle.index("def registrieren(fn):"):quelle.index("def register_all(")]
    assert 'kwargs.setdefault("tags", {_katalog.tag(name)})' in rumpf
    assert 'kwargs.setdefault("description", _katalog.beschreibung(name, doc))' in rumpf
    assert "_parameter_beschreiben(fn, _katalog.parameter_texte(doc))" in rumpf


def _versteckte_verweise():
    from bewerbungs_assistent.services import werkzeug_katalog as k
    versteckt = k.WARTUNG | k.ENTWICKLER
    funde = []
    for p in sorted(PAKET.rglob("*.py")):
        if p.name in ("werkzeug_katalog.py", "werkzeug_schutz.py"):
            continue
        baum = ast.parse(p.read_text(encoding="utf-8-sig"))
        ueberspringen = set()
        for n in ast.walk(baum):
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)):
                if (n.body and isinstance(n.body[0], ast.Expr)
                        and isinstance(getattr(n.body[0], "value", None), ast.Constant)):
                    ueberspringen.add(id(n.body[0].value))
            if isinstance(n, ast.FunctionDef) and n.name in versteckt:
                ueberspringen.update(id(x) for x in ast.walk(n))
        for n in ast.walk(baum):
            if (isinstance(n, ast.Constant) and isinstance(n.value, str)
                    and id(n) not in ueberspringen):
                for z in versteckt:
                    if (re.search(r"(?<![A-Za-z_])" + z + r"(?![A-Za-z_])", n.value)
                            and "Expertenmodus" not in n.value):
                        funde.append(f"{p.name}:{n.lineno}: {z}")
    return funde


def test_h21_kein_sichtbarer_text_verweist_stumm_auf_ausgeblendetes():
    """Ein ausgeblendetes Werkzeug kann Claude nicht aufrufen. Wer es nennt,
    sagt dazu, dass es den Expertenmodus braucht."""
    assert not _versteckte_verweise()


def test_h21_der_verweis_guard_sieht_etwas(monkeypatch):
    """DoD 8c: ohne die Ausnahme fuer 'Expertenmodus' findet er Verweise."""
    from bewerbungs_assistent.services import werkzeug_katalog as k
    monkeypatch.setattr(k, "WARTUNG", k.WARTUNG | {"stelle_bewerten"})
    assert _versteckte_verweise()


def test_h21_capabilities_kennt_wartung_und_kostenklasse(umgebung):
    from bewerbungs_assistent.services import werkzeug_katalog as k
    _db, mcp = umgebung
    erg = _call(mcp, "pbp_capabilities", {"kategorie": "wartung"})
    text = str(erg)
    for name in k.WARTUNG | k.ENTWICKLER:
        assert name in text
    quelle = (PAKET / "tools" / "analyse.py").read_text(encoding="utf-8-sig")
    teuer = quelle[quelle.index('"claude_teuer_bulk": {'):]
    teuer = teuer[:teuer.index("},")]
    assert "stellen_bulk_bewerten" not in teuer
    gratis = quelle[quelle.index('"gratis_db": {'):quelle.index('"lokal_guenstig": {')]
    assert "stellen_bulk_bewerten" in gratis


def test_h21_endpunkt_nimmt_nur_wahrheitswerte(umgebung):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    db, _mcp = umgebung
    dash._db = db
    c = TestClient(dash.app)
    assert c.get("/api/expertenmodus").json()["expertenmodus"] is False
    assert c.put("/api/expertenmodus", json={"an": "ja"}).status_code == 400
    assert c.put("/api/expertenmodus", json={"an": True}).json()["expertenmodus"] is True
    assert db.get_setting("expertenmodus") is True


def test_h21_schalter_im_dashboard():
    seite = (_repo() / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    assert '<ExpertenmodusCard pushToast={pushToast} />' in seite
    assert 'putJson("/api/expertenmodus"' in seite


# ══ H22 — Prompts aus einer Quelle ══════════════════════════════════════

def _slash_texte(mcp):
    async def _run():
        aus = {}
        for p in await mcp.list_prompts():
            r = await p.render({})
            msgs = getattr(r, "messages", r)
            aus[p.name] = "\n".join(getattr(m.content, "text", str(m.content)) for m in msgs)
        return aus
    return asyncio.run(_run())


def test_h22_slash_und_dashboard_liefern_denselben_text(umgebung):
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    db, mcp = umgebung
    db.save_profile({"name": "Test Person"})
    reg = _prompt_registry(db)
    slash = _slash_texte(mcp)
    gemeinsam = set(slash) & set(reg)
    assert len(gemeinsam) >= 20
    for name in gemeinsam:
        assert slash[name] == reg[name](), name


def test_h22_mit_argumenten_ebenso(umgebung):
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    db, mcp = umgebung
    db.save_profile({"name": "Test Person"})
    reg = _prompt_registry(db)

    async def _render(name, args):
        p = await mcp.get_prompt(name)
        r = await p.render(args)
        return "\n".join(getattr(m.content, "text", str(m.content)) for m in r.messages)
    for name in ("interview_vorbereitung", "interview_simulation", "gehaltsverhandlung"):
        args = {"stelle": "Konstrukteur", "firma": "Musterbetrieb GmbH"}
        assert asyncio.run(_render(name, args)) == reg[name](**args), name
        assert "Musterbetrieb GmbH" in reg[name](**args)


def test_h22_kein_slash_prompt_haelt_eine_eigene_fassung():
    """Jeder registrierte Prompt delegiert an einen Builder; eine zweite
    Fassung als Textliteral im Prompt waere die Doppelung von vorher."""
    quelle = (PAKET / "prompts.py").read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    reg = next(n for n in baum.body if isinstance(n, ast.FunctionDef) and n.name == "register_prompts")
    from bewerbungs_assistent.services import prompt_katalog
    geprueft = 0
    for fn in reg.body:
        if not isinstance(fn, ast.FunctionDef) or fn.name in prompt_katalog.AUSNAHMEN:
            continue
        geprueft += 1
        doc = fn.body[0].value if isinstance(fn.body[0], ast.Expr) else None
        for n in ast.walk(fn):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and n is not doc:
                assert len(n.value) < 120, f"{fn.name} traegt einen eigenen Text"
            if isinstance(n, ast.JoinedStr):
                pytest.fail(f"{fn.name} baut einen eigenen f-String")
    assert geprueft >= 20


def test_h22_jobsuche_wartet_nicht_in_einer_schleife(umgebung):
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    db, _mcp = umgebung
    db.save_profile({"name": "Test Person"})
    text = _prompt_registry(db)["jobsuche_workflow"]()
    assert "NICHT in einer Schleife" in text
    assert "Ich halte dich auf dem Laufenden" not in text
    assert "manuelle_quellen" in text


def test_h22_regeln_der_dashboard_fassung_sind_erhalten(umgebung):
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    db, _mcp = umgebung
    db.save_profile({"name": "Test Person"})
    reg = _prompt_registry(db)
    iv = reg["interview_vorbereitung"](stelle="A", firma="B")
    assert "projekte_anzeigen()" in iv and "todo_anlegen(" in iv
    w = reg["willkommen"]()
    assert "firma_kontext(firmenname)" in w and "stellen_anzeigen()" in w


def test_h22_workflow_starten_listet_den_ganzen_katalog(umgebung):
    from bewerbungs_assistent.services import prompt_katalog
    _db, mcp = umgebung
    erg = _call(mcp, "workflow_starten", {"name": ""})
    ids = {w["name"] for w in erg["verfuegbare_workflows"]}
    assert ids == {e["id"] for e in prompt_katalog.alle()}


def test_h22_katalog_kennung_mit_parameter_startet(umgebung):
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    db, mcp = umgebung
    db.save_profile({"name": "Test Person"})
    erg = _call(mcp, "workflow_starten", {"name": "bewerbung_schreiben_lebenslauf"})
    assert erg["status"] == "gestartet"
    assert erg["anweisungen"] == _prompt_registry(db)["bewerbung_schreiben"](nur="lebenslauf")


# ══ H31 — der Weg zurueck ins Dashboard ═════════════════════════════════

def test_h31_link_nimmt_den_port_aus_der_umgebung(monkeypatch):
    from bewerbungs_assistent.services import dashboard_link as dl
    monkeypatch.setenv("BA_DASHBOARD_PORT", "8251")
    assert dl.dashboard_link("bewerbungen", "abc123") == "http://localhost:8251/#bewerbungen/abc123"
    assert dl.dashboard_link("stellen", "profil1:hash9") == "http://localhost:8251/#stellen/hash9"
    with pytest.raises(ValueError):
        dl.dashboard_link("gibtsnicht")


def test_h31_reiter_sind_die_seiten_des_dashboards():
    from bewerbungs_assistent.services import dashboard_link as dl
    utils = (_repo() / "frontend" / "src" / "utils.js").read_text(encoding="utf-8-sig")
    block = utils[utils.index("export const PAGE_IDS = ["):utils.index("];")]
    ids = re.findall(r'^\s*"([a-z]+)"', block, re.M)
    assert set(ids) == set(dl.REITER)


def test_h31_keine_feste_adresse_mehr():
    funde = []
    for p in PAKET.rglob("*.py"):
        for nr, zeile in enumerate(p.read_text(encoding="utf-8-sig").splitlines(), 1):
            if "localhost:8200" in zeile and p.name not in ("dashboard_link.py",) \
                    and not (p.name == "dashboard.py" and nr < 10):
                funde.append(f"{p.name}:{nr}")
    assert not funde, funde


def test_h31_antworten_tragen_den_link(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test Person"})
    aid = db.add_application({"title": "Konstrukteur", "company": "Musterbetrieb GmbH",
                              "status": "beworben"})
    liste = _call(mcp, "bewerbungen_anzeigen", {})
    assert liste["bewerbungen"][0]["dashboard_link"].endswith(f"/#bewerbungen/{aid}")
    details = _call(mcp, "bewerbung_details", {"bewerbung_id": aid})
    assert details["dashboard_link"].endswith(f"/#bewerbungen/{aid}")
    kontext = _call(mcp, "firma_kontext", {"firmenname": "Musterbetrieb GmbH"})
    assert kontext["bewerbungen"][0]["dashboard_link"].endswith(f"/#bewerbungen/{aid}")
    aufgaben = _call(mcp, "aufgaben_uebersicht", {})
    assert aufgaben["dashboard_link"].endswith("/#aufgaben")


def test_h31_stellen_tragen_den_link(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test Person"})
    db.save_jobs([{"hash": "h31stelle01", "title": "Konstrukteur", "company": "Musterbetrieb GmbH",
                   "url": "https://example.com/job/1", "source": "manuell",
                   "description": "Konstruktion von Baugruppen " * 10, "score": 5}])
    erg = _call(mcp, "stellen_anzeigen", {"min_score": 0, "ohne_schwelle": True})
    stellen = erg.get("stellen") or []
    assert stellen, erg
    assert "/#stellen/h31stelle01" in stellen[0]["dashboard_link"]


def test_h31_ics_verlinkt_eine_route_die_es_gibt():
    quelle = (PAKET / "services" / "ics_service.py").read_text(encoding="utf-8")
    assert "dashboard_link('bewerbungen', app_id)" in quelle
    assert "/bewerbungen?id=" not in quelle


def test_h31_frontend_liest_die_kennung_aus_dem_hash():
    utils = (_repo() / "frontend" / "src" / "utils.js").read_text(encoding="utf-8-sig")
    assert "export function parseHashZiel(" in utils
    assert 'if (ziel.page === "bewerbungen") return { applicationId: ziel.kennung };' in utils
    app = (_repo() / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8-sig")
    sync = app[app.index("const syncHash = useEffectEvent("):]
    sync = sync[:sync.index("});")]
    assert "sprungAusHash(ziel)" in sync and "setIntent(" in sync


# ══ H32 — keine Sackgassen auf der Claude-Seite ═════════════════════════

def test_h32_jobsuche_status_ohne_job_id_ohne_suche(umgebung):
    _db, mcp = umgebung
    erg = _call(mcp, "jobsuche_status", {})
    assert erg["status"] == "keine_suche"
    assert "jobsuche_starten()" in erg["hinweis"]


def test_h32_jobsuche_status_ohne_job_id_nimmt_die_letzte(umgebung):
    db, mcp = umgebung
    jid = db.create_background_job("jobsuche", {})
    db.update_background_job(jid, "fertig", 100, "Fertig", {"total": 3})
    erg = _call(mcp, "jobsuche_status", {})
    assert erg["job_id"] == jid
    assert erg["status"] == "fertig"


def test_h32_unbekannte_job_id_nennt_den_weg(umgebung):
    _db, mcp = umgebung
    erg = _call(mcp, "jobsuche_status", {"job_id": "gibtesnicht"})
    assert "Ohne job_id" in erg["hinweis"]


def test_h32_profil_status_ohne_profil_ist_kein_profil(umgebung):
    _db, mcp = umgebung
    erg = _call(mcp, "profil_status", {})
    assert erg["status"] == "kein_profil"
    assert "Starte die Ersterfassung" in erg["naechster_schritt"]
    assert "profil_erstellen()." not in erg.get("nachricht", "")


def test_h32_profil_status_nennt_den_naechsten_schritt(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test Person", "email": "t@example.com", "phone": "0",
                     "address": "Musterweg 1", "summary": "Konstrukteur " * 20})
    erg = _call(mcp, "profil_status", {})
    assert erg["status"] == "vorhanden"
    assert erg["naechster_schritt"]
    # Ohne Suchbegriffe (und nach einem vollstaendigen Profil) kommen die
    # Suchbegriffe; mit unvollstaendigem Profil zuerst das Profil.
    assert ("suchkriterien_setzen" in erg["naechster_schritt"]
            or "extraktion_starten" in erg["naechster_schritt"])


def test_h32_naechster_schritt_folgt_der_lage(umgebung, monkeypatch):
    from bewerbungs_assistent.services import workspace_service as ws
    db, _mcp = umgebung
    db.save_profile({"name": "Test Person"})
    db.set_search_criteria("keywords_muss", ["konstruktion"])
    for stufe, erwartet in (("quellen_aktivieren", "Einstellungen"),
                            ("jobsuche_erneuern", "jobsuche_starten()"),
                            ("bewerben", "stellen_anzeigen()"),
                            ("nachfassen", "aufgaben_uebersicht()")):
        s = {"has_profile": True, "readiness": {"stage": stufe}, "profile": {},
             "search": {"status": "veraltet"}, "jobs": {"active": 2},
             "applications": {"follow_ups_due": 1}}
        assert erwartet in ws.naechster_schritt(db, s)["text"], stufe


def test_h32_dashboard_und_claude_lesen_dieselbe_lage():
    quelle = (PAKET / "dashboard.py").read_text(encoding="utf-8-sig")
    rumpf = quelle[quelle.index("def _build_workspace_summary()"):]
    rumpf = rumpf[:rumpf.index("\ndef ")]
    assert "workspace_aus_db(_db)" in rumpf
    assert "build_workspace_summary(\n" not in rumpf and "profile=_db.get_profile()" not in rumpf


EIGENE_KEIN_PROFIL = re.compile(r"Kein Profil vorhanden|Noch kein Profil vorhanden|Kein aktives Profil\.")


def test_h32_keine_eigene_kein_profil_meldung_in_den_werkzeugen():
    funde = []
    for p in sorted((PAKET / "tools").glob("*.py")):
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8-sig"))):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) \
                    and EIGENE_KEIN_PROFIL.search(n.value):
                funde.append(f"{p.name}:{n.lineno}")
    assert not funde, funde


# ══ H29 — Werkzeugnamen nach Wirkung ════════════════════════════════════

ALT_NEU = {"stelle_bewerten": "stelle_einordnen",
           "stelle_analyse_speichern": "stelle_urteil_speichern",
           "jobtitel_vorschlagen": "jobtitel_speichern"}


def test_h29_neue_namen_und_alte_als_weiterleitung(umgebung):
    _db, mcp = umgebung
    werkzeuge = {w.name: w for w in _werkzeuge(mcp)}
    for alt, neu in ALT_NEU.items():
        assert neu in werkzeuge and alt in werkzeuge
        assert f"heisst jetzt {neu}" in werkzeuge[alt].description
        assert (set(werkzeuge[alt].parameters["properties"])
                == set(werkzeuge[neu].parameters["properties"])), alt


def test_h29_alter_name_wirkt_wie_der_neue(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test Person"})
    db.save_jobs([{"hash": "h29stelle1", "title": "Konstrukteur", "company": "Musterbetrieb GmbH",
                   "url": "https://example.com/h29", "source": "manuell",
                   "description": "Konstruktion " * 20, "score": 3}])
    erg = _call(mcp, "stelle_bewerten", {"job_hash": "h29stelle1", "bewertung": "passt_nicht",
                                         "grund": "zu_weit_entfernt"})
    assert "fehler" not in erg, erg
    zeile = db.connect().execute("SELECT is_active FROM jobs WHERE hash LIKE '%h29stelle1'").fetchone()
    assert zeile["is_active"] == 0


def test_h29_texte_nennen_nur_die_neuen_namen():
    """Anleitungen und Antworten fuehren zum neuen Namen; der alte steht
    nur noch in Kommentaren und in der Weiterleitung."""
    funde = []
    for p in sorted(PAKET.rglob("*.py")):
        if p.name == "werkzeug_katalog.py":
            continue
        baum = ast.parse(p.read_text(encoding="utf-8-sig"))
        for n in ast.walk(baum):
            if isinstance(n, ast.Constant) and isinstance(n.value, str):
                for alt in ALT_NEU:
                    if re.search(r"(?<![A-Za-z0-9_])" + alt + r"(?![A-Za-z0-9_])", n.value) \
                            and "Veraltet" not in n.value and n.value != alt:
                        funde.append(f"{p.name}:{n.lineno}: {alt}")
    assert not funde, funde


def test_h29_notizen_werden_angehaengt(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test Person"})
    aid = db.add_application({"title": "A", "company": "Musterbetrieb GmbH", "status": "beworben",
                              "notes": "Erste Notiz"})
    erg = _call(mcp, "bewerbung_bearbeiten", {"bewerbung_id": aid, "notes": "Zweite Notiz"})
    assert erg["notizen"] == "angehaengt"
    notes = db.get_application(aid)["notes"]
    assert "Erste Notiz" in notes and "Zweite Notiz" in notes
    _call(mcp, "bewerbung_bearbeiten", {"bewerbung_id": aid, "notes": "Zweite Notiz"})
    assert db.get_application(aid)["notes"].count("Zweite Notiz") == 1
    erg = _call(mcp, "bewerbung_bearbeiten", {"bewerbung_id": aid, "notes": "Neu",
                                              "notizen_ersetzen": True})
    assert erg["notizen"] == "ersetzt"
    assert db.get_application(aid)["notes"] == "Neu"


def test_h29_zweites_profil_nur_nach_rueckfrage(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test Person"})
    vorher = len(db.get_profiles())
    erg = _call(mcp, "neues_profil_erstellen", {"name": "Zweite Person"})
    assert erg["status"] == "rueckfrage"
    assert len(db.get_profiles()) == vorher
    assert db.get_profile()["name"] == "Test Person"
    erg = _call(mcp, "neues_profil_erstellen", {"name": "Zweite Person", "bestaetigung": True})
    assert erg["status"] == "erstellt"
    assert len(db.get_profiles()) == vorher + 1


# ══ H25 — Datenschutz-Anzeige und KI-Sperre ═════════════════════════════

def test_h25_datenfluss_nennt_was_wirklich_an_claude_geht():
    from bewerbungs_assistent.services.datenschutz import DATENFLUSS, KURZ
    an_claude = " ".join(DATENFLUSS["sent_to_claude"])
    for wort in ("Anthropic", "Adresse", "Geburtsdatum", "Dokumente", "Anzeigentexte", "Notizen"):
        assert wort in an_claude, wort
    extern = " ".join(DATENFLUSS["external_requests"])
    for wort in ("Nominatim", "OpenRouteService", "elwosa.de", "JobSpy"):
        assert wort in extern, wort
    assert "Copy & Paste" not in str(DATENFLUSS)
    assert "was du mit Claude bearbeitest, geht an Anthropic" in KURZ


def test_h25_endpunkt_liefert_den_datenfluss(umgebung):
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as dash
    from bewerbungs_assistent.services.datenschutz import DATENFLUSS
    db, _mcp = umgebung
    dash._db = db
    daten = TestClient(dash.app).get("/api/privacy-info").json()
    assert daten["data_flow"] == DATENFLUSS


def test_h25_readme_verspricht_nichts_falsches():
    readme = (_repo() / "README.md").read_text(encoding="utf-8")
    assert "verlassen niemals deinen Computer" not in readme
    assert "was du mit Claude bearbeitest, geht an Anthropic" in readme


def test_h25_sperre_greift_auch_bei_extraktion_und_ersterfassung(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test Person"})
    db.set_ki_features(dokumentenanalyse=False, ersterfassung=False)
    erg = _call(mcp, "extraktion_starten", {})
    assert erg.get("ki_blockiert") is True, erg
    erg = _call(mcp, "workflow_starten", {"name": "ersterfassung"})
    assert erg.get("ki_blockiert") is True, erg
    assert "Claude (Cloud)" in erg["hinweis"]
    erg = _call(mcp, "workflow_starten", {"name": "faq"})
    assert erg.get("status") == "gestartet"


def test_h25_zuordnung_nennt_nur_registrierte_werkzeuge(umgebung):
    from bewerbungs_assistent.services import ki_zuordnung
    _db, mcp = umgebung
    namen = {w.name for w in _werkzeuge(mcp)}
    assert set(ki_zuordnung.ZUORDNUNG) <= namen


def test_h25_keine_eigene_sperre_in_den_werkzeugen():
    """Die Sperre sitzt an einer Stelle; eine zweite im Werkzeug waere die
    Doppelung, aus der die Luecke entstanden ist."""
    funde = []
    for p in sorted((PAKET / "tools").glob("*.py")):
        if p.name == "__init__.py":
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8-sig"))):
            if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "ki_gate":
                funde.append(f"{p.name}:{n.lineno}")
    assert not funde, funde


def test_h25_register_all_setzt_die_sperre():
    quelle = (PAKET / "tools" / "__init__.py").read_text(encoding="utf-8")
    rumpf = quelle[quelle.index("def registrieren(fn):"):quelle.index("def mit_katalog(")]
    assert "fn = _mit_ki_sperre(fn, name, self._db)" in rumpf
    assert "mcp = _AnnotierendesMCP(mcp, db)" in quelle


def test_h25_reiter_claude_traegt_die_schalter():
    seite = (_repo() / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    assert '{ id: "claude", label: "Claude (Cloud)" }' in seite
    block = seite[seite.index('{settingsTab === "claude" && ('):]
    block = block[:block.index(")}")]
    assert "<KIFeaturesCard" in block
    ai = seite[seite.index('{settingsTab === "ai" && ('):]
    ai = ai[:ai.index("{settingsTab ===", 10)]
    assert "<KIFeaturesCard" not in ai


def test_h25_einmaliger_hinweis_in_profil_status(umgebung):
    db, mcp = umgebung
    erg = _call(mcp, "profil_status", {})
    assert "geht an Anthropic" in erg["datenschutz"]
    erg = _call(mcp, "profil_status", {})
    assert "datenschutz" not in erg


# ══ H30 — Ersterfassung kuerzer, Lebenslauf-zuerst traegt ═══════════════

def test_h30_kernprompt_unter_4000_zeichen(umgebung):
    from bewerbungs_assistent.prompts import build_kennlerngespraech_prompt
    db, _mcp = umgebung
    assert len(build_kennlerngespraech_prompt(db)) < 4000
    db.save_profile({"name": "Test Person", "email": "t@example.com"})
    text = build_kennlerngespraech_prompt(db)
    assert len(text) < 4000
    assert not re.search(r"#\d{3,4}|\bv1\.\d", text)
    assert "extraktion_starten()" in text and "`anleitung`" in text


def test_h30_anleitung_kommt_mit_der_werkzeugantwort(umgebung):
    db, mcp = umgebung
    db.save_profile({"name": "Test Person", "email": "t@example.com"})
    lesen = _call(mcp, "erfassung_fortschritt_lesen", {})
    assert lesen["phase"] == "erfassung" and "position_hinzufuegen()" in lesen["anleitung"]
    speichern = _call(mcp, "erfassung_fortschritt_speichern", {"bereich": "persoenliche_daten"})
    assert speichern["phase"] == "erfassung" and speichern["anleitung"]
    abschluss = _call(mcp, "kennlerngespraech_abschliessen", {})
    assert abschluss["phase"] == "suche"
    assert "keyword_vorschlaege()" in abschluss["anleitung"]
    assert "jobsuche_starten(quellen=['bundesagentur', 'arbeitnow'," in abschluss["anleitung"]


def test_h30_review_folgt_auf_die_erfassung():
    from bewerbungs_assistent.services import ersterfassung_phasen as ph
    alles = {b: True for b in ph.BEREICHE}
    assert ph.anleitung({**alles, "review_abgeschlossen": False})[0] == "review"
    assert ph.anleitung(alles)[0] == "suche"
    assert ph.anleitung({**alles, "ausbildung": False})[0] == "erfassung"


def test_h30_profil_erstellen_meldet_uebernommene_dokumente(umgebung):
    db, mcp = umgebung
    con = db.connect()
    con.execute("INSERT INTO documents (id, filename, filepath, doc_type, created_at) "
                "VALUES ('d1', 'Lebenslauf.pdf', '/x/Lebenslauf.pdf', 'lebenslauf', '2026-09-25')")
    con.commit()
    erg = _call(mcp, "profil_erstellen", {"name": "Test Person"})
    assert erg["uebernommene_dokumente"] == ["Lebenslauf.pdf"]
    assert erg["naechster_schritt"].startswith("extraktion_starten()")


def test_h30_ohne_dokumente_fuehrt_der_fortschritt(umgebung):
    _db, mcp = umgebung
    erg = _call(mcp, "profil_erstellen", {"name": "Test Person"})
    assert "uebernommene_dokumente" not in erg
    assert erg["naechster_schritt"].startswith("erfassung_fortschritt_lesen()")


def test_h30_menue_reiter_gibt_es_im_dashboard():
    from bewerbungs_assistent.services.menue import EINSTELLUNGEN_REITER
    seite = (_repo() / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    labels = set(re.findall(r'\{ id: "[a-z_]+", label: "([^"]+)" \}', seite))
    assert set(EINSTELLUNGEN_REITER.values()) <= labels, set(EINSTELLUNGEN_REITER.values()) - labels


def _menuepfade():
    from bewerbungs_assistent.services.menue import MENUE
    erlaubt = tuple(MENUE.values())
    falsch = []
    for p in sorted(PAKET.rglob("*.py")):
        if p.name == "menue.py":
            continue
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8-sig"))):
            if not (isinstance(n, ast.Constant) and isinstance(n.value, str)):
                continue
            s = n.value
            if re.search(r"(Einstellungen|Settings|Dashboard)\s*(→|->)", s):
                falsch.append(f"{p.name}:{n.lineno}: Pfeil")
            for m in re.finditer(r"Einstellungen › ", s):
                if not s[m.start():].startswith(erlaubt):
                    falsch.append(f"{p.name}:{n.lineno}: {s[m.start():m.start() + 40]!r}")
    return falsch


def test_h30_menuepfade_stehen_so_da_wie_im_dashboard():
    assert not _menuepfade()


def test_h30_der_pfad_guard_sieht_etwas(monkeypatch):
    """DoD 8c: ein falscher Reitername faellt auf."""
    from bewerbungs_assistent.services import menue
    monkeypatch.setattr(menue, "MENUE", {k: v for k, v in menue.MENUE.items() if k != "quellen"})
    assert _menuepfade()
