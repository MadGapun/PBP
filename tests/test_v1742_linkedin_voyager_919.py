"""Tests fuer v1.7.42 — #919: LinkedIn ueber die Voyager-API.

Der `linkedin`-Scraper stand auf aktiv, hatte aber `letzter_lauf:
23.04.2026` und Erfolgsrate 0 %; `jobspy_linkedin` ist deprecated mit 24
Fehlern in Serie. Faktisch lieferte LinkedIn seit Monaten nichts —
ausgerechnet die Quelle, in der sich der Nutzer laut #813 tatsaechlich
bewegt.

Am 17.08.2026 wurde ein Weg gefunden und vollstaendig durchgespielt:
22 Suchbegriffe, 511 deduplizierte Rohtreffer, 59 Volltexte, 3
uebernommene Stellen. HTTP von aussen blockt LinkedIn zuverlaessig;
Requests aus dem eingeloggten Tab laufen durch.

**Der eigentliche Wert steckt im Volltext.** Von 59 Titeln, die den
Vorfilter passiert hatten, blieben nach dem Lesen der Volltexte 3 uebrig.
Der beste Titel-Treffer des ganzen Laufs verlangte im Fliesstext ein
System von der harten Ausschlussliste. Ein Import, der nur Titel und
Kurzbeschreibung uebernimmt, haette alle falschen mit hohem Score
eingeliefert — deshalb pruefen mehrere Tests unten genau diese Grenze.

AK5 des Issues: Regression gegen gespeicherte Voyager-Antworten, damit
ein Feldumbau bei LinkedIn sofort auffaellt. Die Fixtures unten bilden
die Antwortform nach, nicht die Inhalte eines realen Laufs.
"""
import asyncio
import importlib
import json
import logging
import os
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.job_scraper import linkedin_voyager as lv  # noqa: E402

# Zeilenumbruch als Literal — Heredoc-Escaping frisst rohe
# Backslash-Sequenzen unter Git-Bash (CLAUDE.md, v1.7.24 MERKE 4).
NL = chr(10)


# ── Fixtures: die Antwortform der Voyager-API (AK5) ───────────────────

def _karte(job_id, titel, firma, ort="Hamburg, Deutschland", fuss=None):
    return {
        "$type": lv.CARD_TYPE,
        "preDashNormalizedJobPostingUrn": f"urn:li:fs_normalized_jobPosting:{job_id}",
        "title": {"text": titel},
        "primaryDescription": {"text": firma},
        "secondaryDescription": {"text": ort},
        "footerItems": [{"text": {"text": f}} for f in (fuss or [])],
    }


TREFFERLISTE = {
    "included": [
        # Fremde Objekttypen liegen in derselben Liste — sie duerfen den
        # Parser nicht durcheinanderbringen.
        {"$type": "com.linkedin.voyager.dash.common.Image", "id": "x"},
        _karte("4001", "Senior PLM Consultant", "Musterberatung GmbH",
               fuss=["Vor 2 Tagen erneut gepostet", "Easy Apply"]),
        _karte("4002", "PLM Engineer", "Musterwerft AG", "Wedel, Deutschland"),
        {"$type": "com.linkedin.voyager.dash.jobs.JobPostingCard",
         "title": {"text": "Ohne ID"}},           # faellt heraus
    ]
}

DETAIL = {
    "data": {
        "description": {"text": "A" * 2400},
        "formattedLocation": "Hamburg, Deutschland",
        "workRemoteAllowed": True,
        "applies": 37,
        "employmentStatus": "FULL_TIME",
        "formattedIndustries": ["Maschinenbau"],
        "originalListedAt": 1755388800000,
        "jobPostingUrl": "https://www.linkedin.com/jobs/view/4001/",
    }
}


# ── Der Bauplan: URLs, Header, Zeitfenster ────────────────────────────

def test_919_such_url_traegt_alle_pflichtteile():
    url = lv.such_url("PLM Berater", start=25, fenster="r604800")
    assert "voyagerJobsDashJobCards" in url
    assert "decorationId=" + lv.DECORATION_LISTE in url
    assert "start=25" in url and "count=25" in url
    assert "PLM%20Berater" in url
    assert f"geoId:{lv.GEO_ID_DE}" in url
    assert "timePostedRange:List(r604800)" in url


def test_919_detail_und_anzeige_url():
    assert lv.detail_url("4001").endswith(lv.DECORATION_DETAIL)
    assert "jobPostings/4001" in lv.detail_url("4001")
    # Der Anker ist die Seite, die ein Mensch oeffnet — keine API-URL (#766).
    assert lv.anzeige_url("4001") == "https://www.linkedin.com/jobs/view/4001/"


def test_919_header_sind_vollstaendig():
    h = lv.header("abc")
    assert h["csrf-token"] == "abc"
    assert h["accept"].startswith("application/vnd.linkedin.normalized")
    assert h["x-restli-protocol-version"] == "2.0.0"


def test_919_zeitfenster_folgt_dem_letzten_lauf():
    """Fix r604800 verliert alles, was zwischen zwei Laeufen mit mehr als
    einer Woche Abstand erschien (#919 Vorschlag 3)."""
    assert lv.zeitfenster("") == "r604800"
    vor3 = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    fenster = int(lv.zeitfenster(vor3)[1:])
    assert 3 * 86400 < fenster < 5 * 86400          # inkl. Ueberlappung
    vor99 = (datetime.now(timezone.utc) - timedelta(days=99)).isoformat()
    assert lv.zeitfenster(vor99) == f"r{lv.FENSTER_MAX}"
    assert lv.zeitfenster("kein datum") == "r604800"


# ── Die Parser (AK5) ──────────────────────────────────────────────────

def test_919_trefferliste_wird_zerlegt():
    treffer = lv.parse_trefferliste(TREFFERLISTE)
    assert [t["job_id"] for t in treffer] == ["4001", "4002"]
    erster = treffer[0]
    assert erster["titel"] == "Senior PLM Consultant"
    assert erster["firma"] == "Musterberatung GmbH"
    assert erster["ort"] == "Hamburg, Deutschland"
    assert erster["fusszeile"] == ["Vor 2 Tagen erneut gepostet", "Easy Apply"]
    assert erster["url"] == lv.anzeige_url("4001")


def test_919_trefferliste_uebersteht_leere_antworten():
    """Ein Feldumbau darf den Lauf nicht kippen — er soll auffallen."""
    assert lv.parse_trefferliste({}) == []
    assert lv.parse_trefferliste({"included": []}) == []
    assert lv.parse_trefferliste({"included": [None, 42, "text"]}) == []


def test_919_detail_wird_zerlegt():
    d = lv.parse_detail(DETAIL)
    assert len(d["beschreibung"]) == 2400
    assert d["ort"] == "Hamburg, Deutschland"
    assert d["remote"] == "remote"
    assert d["bewerber"] == 37
    assert d["anstellungsart"] == "FULL_TIME"
    assert d["branchen"] == ["Maschinenbau"]


def test_919_remote_unterscheidet_unbekannt_von_vor_ort():
    """#989: 'nicht gesetzt' und 'ausdruecklich nein' sind nicht dasselbe."""
    assert lv.parse_detail({"data": {"workRemoteAllowed": False}})["remote"] == "vor_ort"
    assert lv.parse_detail({"data": {}})["remote"] == "unbekannt"


def test_919_dedupliziert_ueber_alle_begriffe():
    """22 Begriffe ergaben 511 EINDEUTIGE Treffer — ohne Deduplizierung
    haette jeder Doppeltreffer einen Volltext-Abruf gekostet."""
    a = lv.parse_trefferliste(TREFFERLISTE)
    b = lv.parse_trefferliste(TREFFERLISTE)
    assert len(lv.dedupliziert([a, b])) == 2


# ── Fehlerdeutung: die stille Null ist der teure Fall ─────────────────

def test_919_decoration_fehler_wird_benannt():
    """LinkedIn zieht die Versionsnummern hoch; 400/426 sieht sonst aus
    wie 'gerade keine passenden Stellen' (#919 Vorschlag 5)."""
    assert lv.fehlerklasse(400) == "decoration_veraltet"
    assert lv.fehlerklasse(426) == "decoration_veraltet"
    assert lv.fehlerklasse(403) == "nicht_eingeloggt"
    assert lv.fehlerklasse(429) == "gedrosselt"
    assert lv.fehlerklasse(503) == "linkedin_stoerung"
    assert lv.fehlerklasse(200) == ""
    for klasse in ("decoration_veraltet", "nicht_eingeloggt", "gedrosselt"):
        assert klasse in lv.FEHLER_TEXTE


# ── Suchbegriffe: das Portal-Profil gewinnt (#564) ────────────────────

def test_919_portal_profil_kommt_vor_muss_keywords():
    """#564 wurde genau fuer LinkedIn gelernt: Phrase-Match ergibt dort
    0 Treffer, drei Buchstaben matchen massenhaft Unbeteiligtes."""
    profil = {"primaere_suchen": [{"keywords": "PDM"},
                                  {"keywords": "PLM Berater"}],
              "sekundaere_suchen": [{"keywords": "PLM"}]}
    kriterien = {"keywords_muss": ["Engineering IT", "PDM"]}
    assert lv.begriffe(profil, kriterien, 10) == [
        "PDM", "PLM Berater", "PLM", "Engineering IT"]


def test_919_nicht_verwenden_gewinnt_immer():
    """Gelerntes Wissen ueber die Quelle ist kein Vorschlag."""
    profil = {"nicht_verwenden": [{"wert": "PLM Architect",
                                   "grund": "0 Treffer"}]}
    kriterien = {"keywords_muss": ["PLM Architect", "PDM"]}
    assert lv.begriffe(profil, kriterien, 10) == ["PDM"]


def test_919_begriffe_werden_gedeckelt():
    kriterien = {"keywords_muss": [f"K{i}" for i in range(40)]}
    assert len(lv.begriffe({}, kriterien, 5)) == 5


# ── Die Browser-Skripte ───────────────────────────────────────────────

def test_919_js_bekommt_die_konfiguration_eingesetzt():
    cfg = lv.konfig(["PDM", "PLM Berater"], "r604800")
    js = lv.js_mit_konfig(lv.JS_ERNTE, cfg)
    assert "__CFG__" not in js
    assert '"PLM Berater"' in js
    assert lv.DECORATION_LISTE in js


def test_919_js_gibt_niemals_texte_oder_urls_zurueck():
    """Stolperstein 3 und 4: javascript_tool kappt bei rund 1000 Zeichen,
    und eine URL mit Query-String in der Rueckgabe loest einen Block aus.
    Die Skripte geben deshalb nur Zahlen und Zustaende zurueck."""
    for js in (lv.JS_ERNTE, lv.JS_STATUS, lv.JS_VOLLTEXTE):
        rueckgaben = [z for z in js.split("\n") if z.strip().startswith("return")]
        assert rueckgaben, js[:80]
        for z in rueckgaben:
            assert "beschreibung" not in z, z
            assert "http" not in z, z


def test_919_js_laeuft_als_async_iife():
    """Stolperstein 2: javascript_tool bricht nach rund 45 s ab. Eine
    synchrone Schleife ueber 511 Treffer laeuft da nie durch."""
    for js in (lv.JS_ERNTE, lv.JS_VOLLTEXTE):
        assert "(async () => {" in js
        assert "setTimeout" in js          # Pause zwischen den Requests


def test_919_ausgabe_geht_am_sanitizer_vorbei():
    """Live gemessen am 07.09.2026: LinkedIn sanitisiert `innerHTML`.

    Die erste Fassung schrieb `<main><article>` in den Body. Der Text
    stand danach da (10.589 Zeichen), aber `document.body.children` war
    LEER — kein Element hatte ueberlebt, auch die `<hr>`-Trenner nicht.
    Der Text waere gekommen, nur nicht mehr zerlegbar gewesen. Das
    findet kein Test gegen Fixtures, nur ein Lauf im echten Browser.
    """
    assert "innerHTML" not in lv.JS_AUSGABE
    assert "document.body.textContent" in lv.JS_AUSGABE
    # Ohne pre-wrap faltet der Browser die Zeilenumbrueche zu Leerzeichen.
    assert "pre-wrap" in lv.JS_AUSGABE
    assert "get_page_text" in lv.JS_AUSGABE


def test_919_ausgabe_und_parser_passen_zusammen():
    """Die Marker sind der Vertrag zwischen Seite und Auswertung."""
    seite = (
        lv.MARKER_START + "4001 ===" + NL +
        "TITEL: PLM Consultant" + NL +
        "FIRMA: Musterberatung GmbH" + NL +
        "ORT: Hamburg" + NL +
        "REMOTE: remote" + NL +
        "TEXT:" + NL + "Zeile eins." + NL + "Zeile zwei." + NL +
        lv.MARKER_ENDE + "4001 ===" + NL + NL +
        lv.MARKER_START + "4002 ===" + NL +
        "TITEL: PLM Engineer" + NL +
        "FIRMA: Musterwerft AG" + NL +
        "ORT: Wedel" + NL +
        "REMOTE: unbekannt" + NL +
        "TEXT:" + NL + "Anderer Text." + NL +
        lv.MARKER_ENDE + "4002 ==="
    )
    eintraege = lv.parse_ausgabe(seite)
    assert [e["job_id"] for e in eintraege] == ["4001", "4002"]
    assert eintraege[0]["titel"] == "PLM Consultant"
    assert eintraege[0]["firma"] == "Musterberatung GmbH"
    assert eintraege[0]["remote"] == "remote"
    # Mehrzeilige Anzeigentexte bleiben mehrzeilig.
    assert eintraege[0]["beschreibung"] == "Zeile eins." + NL + "Zeile zwei."
    assert eintraege[1]["beschreibung"] == "Anderer Text."


def test_919_parser_uebersteht_kaputte_seiten():
    assert lv.parse_ausgabe("") == []
    assert lv.parse_ausgabe("irgendein Seitentext ohne Marker") == []


# ── Der Trichter (AK4) ────────────────────────────────────────────────

def test_919_trichter_erklaert_den_lauf():
    t = lv.trichter_leer()
    t.update({"rohtreffer": 511, "nach_vorfilter": 59, "volltexte": 59,
              "angelegt": 3, "uebersprungen": 56,
              "gruende": {"volltext_fehlt": 50, "blacklist": 6}})
    text = lv.trichter_text(t)
    assert "511 Rohtreffer" in text and "59 nach Vorfilter" in text
    assert "3 angelegt" in text and "volltext_fehlt 50" in text


# ── Die Werkzeuge ─────────────────────────────────────────────────────

@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v1742_919_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    datenbank = _db_mod.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.save_profile({"name": "Test Person"})
    datenbank.set_search_criteria("keywords_muss", ["PLM", "PDM"])
    yield datenbank
    datenbank.close()
    os.environ.pop("BA_DATA_DIR", None)
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import jobs
    server = FastMCP("test")
    jobs.register(server, db, logging.getLogger("test"))
    return server


def _call(server, name, args=None):
    async def _run():
        tool = await server.get_tool(name)
        res = await tool.run(args or {})
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _treffer(job_id="4001", titel="Senior PLM Consultant",
             firma="Musterberatung GmbH", zeichen=2400):
    return {"job_id": job_id, "titel": titel, "firma": firma,
            "ort": "Hamburg", "remote": "remote",
            "beschreibung": "PLM-Rollout und Prozessarbeit. " * (zeichen // 28)}


def test_919_plan_liefert_begriffe_und_skripte(db, mcp):
    plan = _call(mcp, "linkedin_lauf_plan", {"max_begriffe": 4})
    assert plan["status"] == "bereit"
    assert plan["begriffe"]
    assert plan["requests_gesamt"] == len(plan["begriffe"]) * 2
    assert "__CFG__" not in plan["js"]["1_ernte"]
    assert len(plan["ablauf"]) >= 6 and len(plan["stolpersteine"]) >= 5


def test_919_plan_ohne_kriterien_ist_keine_sackgasse(db, mcp):
    db.set_search_criteria("keywords_muss", [])
    # Das Default-LinkedIn-Profil (#564) waere sonst die Quelle — hier
    # bewusst leeren, um den echten Leerfall zu treffen.
    db.update_portal_search_profile("linkedin", primaere_suchen=[],
                                    sekundaere_suchen=[])
    plan = _call(mcp, "linkedin_lauf_plan")
    assert plan["status"] == "leer"
    assert "suchkriterien_setzen" in plan["hinweis"]


def test_919_ohne_login_kein_befund_ueber_den_markt(db, mcp):
    """AK3: sauberer Abbruch mit eigenem Statuswert, keine
    Auto-Deaktivierung — ein fehlender Login sagt nichts ueber den
    Stellenmarkt (#906 Befund 1)."""
    res = _call(mcp, "linkedin_treffer_uebernehmen", {"login_fehlt": True})
    assert res["status"] == "wartet_auf_login"
    assert "automatisch deaktiviert" in res["hinweis"]


def test_919_dry_run_legt_nichts_an(db, mcp):
    res = _call(mcp, "linkedin_treffer_uebernehmen",
                {"treffer": [_treffer()], "rohtreffer": 511})
    assert res["status"] == "vorschau"
    assert res["trichter"]["rohtreffer"] == 511
    assert res["trichter"]["angelegt"] == 1
    assert db.get_active_jobs() == []


def test_919_uebernahme_legt_mit_anker_an(db, mcp):
    """AK2: beschreibung > 500 Zeichen UND eine Detail-URL als Anker."""
    res = _call(mcp, "linkedin_treffer_uebernehmen",
                {"treffer": [_treffer()], "dry_run": False})
    assert res["status"] == "uebernommen"
    assert res["trichter"]["angelegt"] == 1
    job = db.get_active_jobs()[0]
    assert job["url"] == lv.anzeige_url("4001")
    assert len(job["description"]) > lv.MIN_BESCHREIBUNG
    assert job["source"] == "linkedin"


def test_919_ohne_volltext_keine_anlage(db, mcp):
    """Der Kern des Issues: von 59 Titeln blieben nach dem Volltext 3.
    Ein Import mit halbem Text liefert genau die falschen ein."""
    duenn = _treffer()
    duenn["beschreibung"] = "PLM Consultant gesucht."
    res = _call(mcp, "linkedin_treffer_uebernehmen",
                {"treffer": [duenn], "dry_run": False})
    assert res["trichter"]["angelegt"] == 0
    assert res["trichter"]["gruende"]["volltext_fehlt"] == 1
    assert db.get_active_jobs() == []


def test_919_ohne_job_id_kein_anker(db, mcp):
    ohne = _treffer()
    ohne["job_id"] = ""
    res = _call(mcp, "linkedin_treffer_uebernehmen",
                {"treffer": [ohne], "dry_run": False})
    assert res["trichter"]["gruende"]["kein_anker"] == 1


def test_919_blacklist_gilt_auch_hier(db, mcp):
    """Der Import geht durch denselben Schreibweg wie
    stelle_manuell_anlegen — sonst waere er das achte Nadeloehr, das
    keines ist (#992)."""
    db.add_to_blacklist("firma", "Musterberatung", "Nie eine Rueckmeldung")
    res = _call(mcp, "linkedin_treffer_uebernehmen",
                {"treffer": [_treffer()], "dry_run": False})
    assert res["trichter"]["angelegt"] == 0
    assert res["trichter"]["gruende"]["blacklist"] == 1
    assert db.get_blacklist_blocks(), "Blockade nicht protokolliert (#992)"


def test_919_titel_ausnahme_wirkt_auch_beim_import(db, mcp):
    db.add_to_blacklist("firma", "Musterberatung", "Zeitarbeit",
                        ausser_wenn_titel_enthaelt=["PLM"])
    res = _call(mcp, "linkedin_treffer_uebernehmen",
                {"treffer": [_treffer()], "dry_run": False})
    assert res["trichter"]["angelegt"] == 1


def test_919_zweiter_lauf_legt_nicht_doppelt_an(db, mcp):
    args = {"treffer": [_treffer()], "dry_run": False}
    _call(mcp, "linkedin_treffer_uebernehmen", args)
    zweiter = _call(mcp, "linkedin_treffer_uebernehmen", args)
    assert zweiter["trichter"]["angelegt"] == 0
    assert len(db.get_active_jobs()) == 1


def test_919_trichter_macht_die_null_lesbar(db, mcp):
    """"0 angelegt" heisst hier NICHT "0 gefunden" (#813/#989)."""
    duenn = _treffer()
    duenn["beschreibung"] = "kurz"
    res = _call(mcp, "linkedin_treffer_uebernehmen",
                {"treffer": [duenn], "dry_run": False, "rohtreffer": 511})
    assert "511 Rohtreffer" in res["trichter_text"]
    assert "kein Ausfall" in res["hinweis"]


def test_919_leere_uebergabe_ist_keine_sackgasse(db, mcp):
    res = _call(mcp, "linkedin_treffer_uebernehmen", {"treffer": []})
    assert res["status"] == "leer"
    assert "linkedin_lauf_plan" in res["hinweis"]


def test_919_quelle_ist_nicht_mehr_veraltet():
    """Es gibt jetzt einen funktionierenden Weg — 'veraltet' waere eine
    Falschaussage, und die Quelle darf nicht als tot gefuehrt werden."""
    from bewerbungs_assistent.job_scraper import SOURCE_REGISTRY, zugriffsart_von
    eintrag = SOURCE_REGISTRY["linkedin"]
    assert not eintrag.get("veraltet")
    assert not eintrag.get("deprecated")
    assert zugriffsart_von("linkedin") == "browser_login"
    assert "linkedin_lauf_plan" in eintrag["hinweis"]
