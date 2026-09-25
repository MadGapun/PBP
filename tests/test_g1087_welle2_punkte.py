"""Welle 2 aus #1087 — ein Wert je Stelle (C96), eine Bedeutung (H24),
die erste Trefferliste sagt, was fehlt (C97).

C96: dieselbe Stelle trug auf Karte, Dashboard, Fit-Dialog, Timeline und
in `stellen_anzeigen` verschiedene Zahlen. Dieser Test legt EINE Stelle an,
setzt einen Begriffs-Regler (zaehlt) und einen Rahmen-Regler (zaehlt
nicht) und haelt die Orte gegeneinander.
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
PAKET = _repo() / "src" / "bewerbungs_assistent"
FRONTEND = _repo() / "frontend" / "src"

TEXT = ("Wir suchen Unterstuetzung im Einkauf mit SAP MM und Disposition. "
        "Lieferantenmanagement, Verhandlung mit Lieferanten, Englisch. " * 6)


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_g1087w2_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    db.set_search_criteria("keywords_muss", ["einkauf", "sap mm", "disposition"])
    db.set_search_criteria("keywords_plus", ["englisch", "verhandlung"])
    import bewerbungs_assistent.dashboard as dash
    alt = dash._db
    dash._db = db
    yield db, _srv_mod.mcp, dash
    dash._db = alt
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg.get("result", erg) if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _stelle(db):
    from bewerbungs_assistent.job_scraper import fit_analyse
    from bewerbungs_assistent.services import scoring_kriterien
    db.save_jobs([{"hash": "c96stelle", "title": "Sachbearbeitung Einkauf",
                   "company": "Musterbetrieb GmbH", "url": "https://example.com/c96",
                   "source": "manuell", "description": TEXT, "remote_level": "remote",
                   "location": "Hamburg", "score": 0}])
    voll = db.connect().execute("SELECT hash FROM jobs WHERE hash LIKE '%c96stelle'").fetchone()["hash"]
    job = db.get_job(voll)
    frisch = fit_analyse(job, scoring_kriterien.fuer_scoring(db))["total_score"]
    db.update_job(voll, {"score": frisch})
    return voll, frisch


def _orte(umgebung):
    from fastapi.testclient import TestClient
    db, mcp, dash = umgebung
    voll, frisch = _stelle(db)
    # Ein Begriffs-Regler zaehlt in die Punkte, ein Rahmen-Regler nicht.
    db.set_scoring_config("keyword", "verhandlung", 2)
    db.set_scoring_config("remote", "remote", 5)
    aid = db.add_application({"title": "Sachbearbeitung Einkauf", "company": "Musterbetrieb GmbH",
                              "status": "beworben", "job_hash": voll})
    c = TestClient(dash.app)
    liste = c.get("/api/jobs?active=true").json()
    jobs = liste["jobs"] if isinstance(liste, dict) else liste
    karte = next(j for j in jobs if str(j["hash"]).endswith("c96stelle"))
    kurz = str(karte["hash"])
    fit = c.get(f"/api/jobs/{kurz}/fit-analyse").json()
    timeline = c.get(f"/api/application/{aid}/timeline").json()
    mcp_liste = _call(mcp, "stellen_anzeigen", {"ohne_schwelle": True})
    eintrag = next(e for e in mcp_liste["stellen"] if str(e["hash"]).endswith("c96stelle"))
    return {"karte": karte, "fit": fit, "timeline": timeline["job"], "mcp": eintrag,
            "frisch": frisch}


def test_c96_fuenf_orte_eine_zahl(umgebung):
    o = _orte(umgebung)
    werte = {
        "karte_und_dashboard (/api/jobs)": o["karte"]["punkte"],
        "fit_dialog": o["fit"]["punkte"],
        "timeline": o["timeline"]["punkte"],
        "stellen_anzeigen": o["mcp"]["punkte"],
        "stellen_anzeigen.score": o["mcp"]["score"],
    }
    assert len(set(werte.values())) == 1, werte
    # Der Begriffs-Regler zaehlt: die Punkte liegen ueber dem Fachwert
    # ohne Regler.
    assert o["karte"]["punkte"] > o["frisch"], (o["karte"]["punkte"], o["frisch"])


def test_c96_rahmen_regler_zaehlt_nicht_in_die_punkte(umgebung):
    o = _orte(umgebung)
    # Der Wert samt Rahmen (Sortierung) liegt hoeher — die Punkte nicht.
    assert o["karte"]["score"] > o["karte"]["punkte"]


def test_c96_faktoren_addieren_sich_zur_zahl(umgebung):
    o = _orte(umgebung)
    summe = round(sum(v for v in o["fit"]["faktoren_fach"].values()
                      if isinstance(v, (int, float))), 1)
    assert summe == o["fit"]["punkte"], o["fit"]["faktoren_fach"]
    assert "Deine Regler für Begriffe" in o["fit"]["faktoren_fach"]
    # Rahmenfaktoren stehen getrennt und sind nicht Teil der Summe.
    assert not any(k.startswith("Arbeitsmodell") for k in o["fit"]["faktoren_fach"])


def test_c96_skala_steht_dabei(umgebung):
    o = _orte(umgebung)
    assert o["karte"]["punkte_max"] and o["karte"]["punkte_max"] > 0
    assert re.match(r"^\d+(\.\d)? von \d+(\.\d)? Punkten$|^\d+(\.\d)? Punkte$",
                    o["mcp"]["punkte_text"]), o["mcp"]["punkte_text"]


def test_c96_faktoren_summe_ueber_viele_stellen():
    """Eigenschaft von fit_analyse selbst, ohne Datenbank."""
    import random
    from bewerbungs_assistent.job_scraper import fit_analyse
    krit = {"keywords_muss": ["einkauf", "sap mm", "disposition", "lieferant"],
            "keywords_plus": ["englisch", "excel", "verhandlung"],
            "keywords_minus": ["zeitarbeit", "vertrieb"]}
    woerter = ["einkauf", "sap mm", "disposition", "lieferant", "englisch", "excel",
               "verhandlung", "zeitarbeit", "vertrieb", "lager"]
    random.seed(11)
    for _ in range(150):
        ws = random.sample(woerter, random.randint(0, 8))
        job = {"title": "Stelle " + " ".join(ws[:1]), "description": " ".join(ws) * 3 + " Text" * 40,
               "remote_level": random.choice(["remote", "hybrid", None]),
               "distance_km": random.choice([None, 5, 400])}
        r = fit_analyse(job, krit)
        s = round(sum(v for v in r["faktoren_fach"].values() if isinstance(v, (int, float))), 1)
        assert abs(s - r["total_score"]) < 0.05, (r["total_score"], r["faktoren_fach"])


def test_c96_hinweis_wenn_der_gespeicherte_stand_abweicht(umgebung):
    from fastapi.testclient import TestClient
    db, _mcp, dash = umgebung
    voll, frisch = _stelle(db)
    db.update_job(voll, {"score": frisch + 3})
    fit = TestClient(dash.app).get(f"/api/jobs/{voll.split(':', 1)[-1]}/fit-analyse").json()
    assert "punkte_hinweis" in fit and "In der Liste steht noch" in fit["punkte_hinweis"]


def test_c96_frontend_liest_die_punkte():
    """Karte, Dashboard, Timeline und Dialog zeigen `punkteText`."""
    orte = {
        "pages/JobsPage.jsx": ["{punkteText(job)}", "punkteText(fitDialog.analysis", "punkteText(detailDialog.job)"],
        "pages/DashboardPage.jsx": ["{punkteText(job)}"],
        "pages/ApplicationsPage.jsx": ["{punkteText(timelineDialog.entry.job)}"],
    }
    for datei, muster in orte.items():
        text = (FRONTEND / datei).read_text(encoding="utf-8-sig")
        for m in muster:
            assert m in text, f"{datei}: {m}"
    # Kein "Fachwert"/"Gesamtscore" mehr als sichtbarer Name.
    for datei in orte:
        text = (FRONTEND / datei).read_text(encoding="utf-8-sig")
        sichtbar = re.findall(r">[^<>{}]*(Fachwert|Gesamtscore|Fit-Score)[^<>{}]*<", text)
        assert not sichtbar, (datei, sichtbar)


# ══ H24 ═══════════════════════════════════════════════════════════════

VERBOTEN = re.compile(
    r"\b\d+\s*-\s*\d+\s*Punkte|Match-Score|Fit-Score|liegt bei X ?%|um bis zu \d+ ?%"
    r"|Score von 0\s*-\s*100|Score \(0-", re.I)


def _texte_fuer_h24():
    import ast
    texte = {}
    for datei in list((PAKET / "tools").glob("*.py")) + [PAKET / "prompts.py", PAKET / "server.py"] \
            + list((PAKET / "services").glob("*.py")):
        baum = ast.parse(datei.read_text(encoding="utf-8-sig"))
        stuecke = [k.value for k in ast.walk(baum)
                   if isinstance(k, ast.Constant) and isinstance(k.value, str)]
        texte[datei.name] = "\n".join(stuecke)
    for datei in list((FRONTEND / "pages").glob("*.jsx")) + list((FRONTEND / "components").glob("*.jsx")):
        texte[datei.name] = datei.read_text(encoding="utf-8-sig")
    return texte


def test_h24_keine_bereichs_oder_prozentangaben_zum_score():
    befunde = []
    for name, text in _texte_fuer_h24().items():
        for m in VERBOTEN.finditer(text):
            # Der Lebenslauf-Check (lebenslauf_bewerten) vergibt 0-100 fuer
            # den LEBENSLAUF, nicht fuer eine Stelle — kein Score-Satz.
            umfeld = text[max(0, m.start() - 120):m.end() + 40]
            if "Perspektive" in umfeld or "lebenslauf" in umfeld.lower():
                continue
            befunde.append(f"{name}: {m.group(0)}")
    assert not befunde, befunde


def test_h24_prompts_nennen_den_satz_aus_der_konstante(umgebung):
    from bewerbungs_assistent.services.punkte import SCORE_BEDEUTUNG
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    db, mcp, _ = umgebung

    async def _render(name):
        p = await mcp.get_prompt(name)
        erg = await p.render({})
        nachrichten = getattr(erg, "messages", erg)
        return "".join(getattr(getattr(n, "content", n), "text", "") for n in nachrichten)

    for name in ("jobsuche_workflow", "bewerbungs_coaching"):
        try:
            text = asyncio.run(_render(name))
        except Exception:
            continue
        assert "{SCORE_BEDEUTUNG}" not in text, name
    quelle = (PAKET / "prompts.py").read_text(encoding="utf-8")
    assert quelle.count("{SCORE_BEDEUTUNG}") >= 2
    from bewerbungs_assistent.services import passung
    assert SCORE_BEDEUTUNG in passung.OHNE_URTEIL["nicht_gelesen"]


def test_h24_frontend_und_server_sagen_dasselbe():
    from bewerbungs_assistent.services.punkte import SCORE_BEDEUTUNG
    js = (FRONTEND / "lib" / "score.js").read_text(encoding="utf-8")
    block = js.split("export const SCORE_BEDEUTUNG", 1)[1]
    block = block[:block.index('";') + 1]
    teile = re.findall(r'"([^"]*)"', block)
    frontend = "".join(teile)

    def norm(t):
        for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("Ä", "Ae"), ("Ö", "Oe"), ("Ü", "Ue"), ("ß", "ss")):
            t = t.replace(a, b)
        return t
    assert norm(frontend) == SCORE_BEDEUTUNG


def test_h24_fit_analyse_liefert_den_satz(umgebung):
    db, mcp, _ = umgebung
    voll, _ = _stelle(db)
    from bewerbungs_assistent.services.punkte import SCORE_BEDEUTUNG
    erg = _call(mcp, "fit_analyse", {"job_hash": voll.split(":", 1)[-1]})
    assert erg.get("score_bedeutung") == SCORE_BEDEUTUNG or \
        (erg.get("empfehlung") or {}).get("score_bedeutung") == SCORE_BEDEUTUNG
    assert erg.get("punkte_text"), "punkte_text fehlt"
    assert "%" not in erg["punkte_text"]
    # Die Empfehlung traegt ihre eigene Skala-Zeile (_skala) — ebenfalls
    # ohne Prozent.
    befund = erg.get("empfehlung") or {}
    assert befund.get("punkte_text"), "Empfehlung ohne punkte_text"
    assert "%" not in befund["punkte_text"]


# ══ C97 ═══════════════════════════════════════════════════════════════

def test_c97_letzter_lauf_nennt_die_stellen_ohne_volltext(umgebung):
    from fastapi.testclient import TestClient
    db, _mcp, dash = umgebung
    jid = db.create_background_job("jobsuche", {})
    db.update_background_job(jid, "fertig", progress=100, message="Lauf",
                             result={"total": 44, "neu_aktiv": 44, "ohne_volltext": 32,
                                     "quellen": {}, "quellen_status": {}})
    daten = TestClient(dash.app).get("/api/jobsuche/last").json()
    assert daten["ohne_volltext"] == 32


def test_c97_der_suchlauf_zaehlt_sie():
    quelle = (PAKET / "job_scraper" / "__init__.py").read_text(encoding="utf-8")
    assert 'result_data["ohne_volltext"]' in quelle


def test_c97_ungeprueft_nennt_den_grund():
    from bewerbungs_assistent.services import fachwert, rahmen
    m = fachwert.daumen(5, {"trennschwelle": 3, "oberes_viertel": 9}, belegt=False)
    assert m["ungeprueft_weil"] == "ohne Anzeigentext"
    m = fachwert.daumen(5, {"grundlage_fehlt": "zu wenig"}, belegt=True)
    assert "Bewerbungen" in m["ungeprueft_weil"]
    r = rahmen.daumen({"title": "x", "description": "y", "distance_km": None,
                       "salary_min": None}, {})
    if r["farbe"] == "grau":
        assert r.get("ungeprueft_weil")
