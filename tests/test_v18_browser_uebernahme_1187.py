"""#1187 Stufe 2/3: ein gemeinsamer Sammelweg fuer alle Browser-Quellen, der Lauf wird verbucht, und was danach auf den
Menschen wartet, steht im Dashboard.

Befund (09.10.2026, Beta 19): ein Lauf ueber sechs Browser-Quellen mit rund 1.300 Rohtreffern legte keine Stelle in PBP an.
Stufe 1 hat die Anleitungen gedreht ("im Zweifel eintragen") und die Vorschau von `linkedin_treffer_uebernehmen` ehrlich gemacht
(`test_v18_browser_im_zweifel_1187.py`). Hier:

* Stufe 2 - `browser_treffer_uebernehmen`: derselbe Anlageweg wie `stelle_manuell_anlegen`, Vorschau ohne Schreiben, der Lauf wird
  in `scraper_runs` verbucht (auch ohne Anlage), Urteil nur mit gelesenem Volltext, Aussortieren mit Herkunft "claude".
* Stufe 3 - `services/stellen_zu_pruefen` und `GET /api/stellen/zu-pruefen`: was wartet, und was Claude aussortiert hat.

Alle Firmen, Orte und Adressen sind erfunden.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

import pytest

import test_mcp_registry as reg
from bewerbungs_assistent.services import aussortier_protokoll, browser_handoff as bh, browser_uebernahme as bu, stellen_zu_pruefen

SRC = Path(__file__).resolve().parents[1] / "src" / "bewerbungs_assistent"

TEXT = ("Ihre Aufgaben: Sie betreuen die Engineering-Systeme unseres Werks, pflegen Stuecklisten und Freigabeprozesse "
        "und begleiten die Einfuehrung eines neuen PLM-Systems. Ihr Profil: abgeschlossenes Studium, mehrjaehrige "
        "Erfahrung im Maschinenbau, sicherer Umgang mit Datenmodellen.")
FIRMEN = ["Nordlicht Werke GmbH", "Sonnenhof Systeme AG", "Kupferberg Anlagenbau GmbH", "Wiesengrund Software GmbH",
          "Tannenwald Logistik AG", "Seeblick Elektronik GmbH"]
TITEL = ["PLM Systemadministrator (m/w/d)", "Teamcenter Berater (m/w/d)", "Konstruktionsleiter Maschinenbau (m/w/d)",
         "IT-Projektleiter ERP (m/w/d)", "Einkaufsleiter Beschaffung (m/w/d)", "Qualitaetsingenieur Elektronik (m/w/d)"]


@pytest.fixture
def umgebung(tmp_path):
    mcp, db = reg._build_test_server(tmp_path)
    # QA-Isolations-Regel: nie die echte Datenbank treffen
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Erika Musterfrau"})
    db.set_search_criteria("keywords_muss", ["PLM", "Teamcenter"])
    yield mcp, db
    db.close()


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _t(i, **kw):
    """Treffer Nr. i - jeder mit eigener Firma und eigenem Titel, damit keine Dublettenregel zugreift."""
    d = {"titel": TITEL[i], "firma": FIRMEN[i], "ort": "Musterstadt",
         "url": f"https://karriere.beispiel-{i}.example/jobs/{4700 + i}"}
    d.update(kw)
    return d


def _lauf(mcp, treffer, **kw):
    args = {"quelle": "stepstone", "treffer": treffer}
    args.update(kw)
    return _call(mcp, "browser_treffer_uebernehmen", args)


def _bestand(db):
    """Zeilenzahl jeder Tabelle - ein Schreibzugriff irgendwo faellt auf."""
    conn = db.connect()
    namen = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in namen}


def _stellen(db):
    return db.connect().execute("SELECT hash, title, is_active, dismissed_by, dismiss_reason FROM jobs").fetchall()


# ══ Stufe 2: Vorschau und echter Lauf ══════════════════════════════════════════════════════════════════════

def test_die_vorschau_ist_die_vorgabe_und_schreibt_nichts(umgebung):
    mcp, db = umgebung
    vorher = _bestand(db)
    erg = _lauf(mcp, [_t(0), _t(1)], rohtreffer=40)
    assert erg["status"] == "vorschau" and erg["dry_run"] is True and erg["verbucht"] is False
    assert erg["trichter"]["angelegt"] == 2 and erg["trichter"]["rohtreffer"] == 40 and erg["trichter"]["uebergeben"] == 2
    assert _bestand(db) == vorher, "die Vorschau hat etwas geschrieben (auch die Verbuchung des Laufs gehoert dazu)"
    assert "dry_run=False" in erg["hinweis"]


def test_der_echte_lauf_legt_an_und_verbucht_den_lauf(umgebung):
    mcp, db = umgebung
    erg = _lauf(mcp, [_t(0, beschreibung=TEXT), _t(1, beschreibung=TEXT)], dry_run=False, rohtreffer=12, volltexte_gelesen=3)
    assert erg["status"] == "uebernommen" and erg["verbucht"] is True, erg
    assert erg["trichter"]["angelegt"] == 2 and erg["trichter"]["volltexte_gelesen"] == 3
    assert len(db.get_active_jobs()) == 2
    (lauf,) = db.get_scraper_runs("stepstone")
    assert lauf["count"] == 12 and lauf["new_count"] == 2 and lauf["state"] == "ok"
    assert lauf["detail"].startswith("Browserlauf:") and "12 Rohtreffer" in lauf["detail"] and "2 angelegt" in lauf["detail"]
    assert "Stellen zu prüfen" in erg["naechster_schritt"]


def test_ein_lauf_ohne_jede_anlage_wird_trotzdem_verbucht(umgebung):
    """Der Kern des Befunds: 1.300 Rohtreffer, nichts angelegt - und nirgends eine Spur davon."""
    mcp, db = umgebung
    erg = _lauf(mcp, [{"titel": "", "firma": "Nordlicht Werke GmbH"}, {"url": "https://x.example/1"}],
                dry_run=False, rohtreffer=300)
    assert erg["trichter"]["angelegt"] == 0 and erg["trichter"]["uebersprungen"] == 2
    assert erg["trichter"]["gruende"] == {"titel_oder_firma_fehlt": 2}
    assert "Keine Stelle angelegt" in erg["hinweis"]
    (lauf,) = db.get_scraper_runs("stepstone")
    assert lauf["count"] == 300 and lauf["new_count"] == 0 and lauf["state"] == "ok"
    assert "300 Rohtreffer" in lauf["detail"] and "0 angelegt" in lauf["detail"]
    assert "Titel oder Firma fehlt: 2" in lauf["detail"]


def test_eine_leere_uebergabe_wird_nur_im_echten_lauf_verbucht(umgebung):
    mcp, db = umgebung
    vorschau = _lauf(mcp, [], rohtreffer=25)
    assert vorschau["status"] == "leer" and vorschau["verbucht"] is False
    assert db.get_scraper_runs("stepstone") == []
    echt = _lauf(mcp, [], dry_run=False, rohtreffer=25)
    assert echt["status"] == "leer" and echt["verbucht"] is True
    (lauf,) = db.get_scraper_runs("stepstone")
    assert lauf["count"] == 25 and lauf["new_count"] == 0


def test_ein_lauf_mit_null_rohtreffern_ist_still_nicht_ok(umgebung):
    mcp, db = umgebung
    _lauf(mcp, [], dry_run=False, rohtreffer=0)
    (lauf,) = db.get_scraper_runs("stepstone")
    assert lauf["state"] == "silent" and lauf["count"] == 0


def test_der_gesundheitszustand_der_quelle_bleibt_unberuehrt(umgebung):
    """Ein Browserlauf ist kein Scraper-Lauf: "0 neu" darf keine Quelle als stumm zaehlen und abschalten (B25)."""
    mcp, db = umgebung
    conn = db.connect()
    vorher = conn.execute("SELECT COUNT(*) FROM scraper_health").fetchone()[0]
    for _ in range(3):
        _lauf(mcp, [], dry_run=False, rohtreffer=0)
    assert conn.execute("SELECT COUNT(*) FROM scraper_health").fetchone()[0] == vorher
    assert len(db.get_scraper_runs("stepstone")) == 3


def test_die_quelle_wird_normalisiert(umgebung):
    mcp, db = umgebung
    erg = _lauf(mcp, [_t(0, beschreibung=TEXT)], quelle="  StepStone ", dry_run=False, rohtreffer=1)
    assert erg["quelle"] == "stepstone"
    assert len(db.get_scraper_runs("stepstone")) == 1
    assert {r["source"] for r in db.connect().execute("SELECT source FROM jobs")} == {"stepstone"}


def test_ohne_quelle_wird_nichts_getan(umgebung):
    mcp, db = umgebung
    vorher = _bestand(db)
    erg = _lauf(mcp, [_t(0)], quelle="  ", dry_run=False)
    assert "fehler" in erg and _bestand(db) == vorher


def test_ein_fehlender_login_ist_kein_befund_ueber_den_markt(umgebung):
    mcp, db = umgebung
    vorher = _bestand(db)
    erg = _lauf(mcp, [], login_fehlt=True, dry_run=False, quelle="xing")
    assert erg["status"] == "wartet_auf_login" and "NICHT automatisch deaktiviert" in erg["hinweis"]
    assert _bestand(db) == vorher, "ein Login-Problem darf keinen Lauf verbuchen"


# ══ Anlage: dieselben Regeln wie stelle_manuell_anlegen ════════════════════════════════════════════════════

def test_eine_karte_ohne_volltext_ist_trotzdem_eine_stelle(umgebung):
    mcp, db = umgebung
    erg = _lauf(mcp, [_t(0)], dry_run=False, rohtreffer=1)
    assert erg["trichter"]["angelegt"] == 1 and erg["trichter"]["ohne_volltext"] == 1
    assert erg["angelegt"][0]["ohne_volltext"] is True
    assert "ohne Volltext" in erg["trichter_text"] and "stellenbeschreibung_nachladen" in erg["naechster_schritt"]
    assert len(db.get_active_jobs()) == 1


def test_ohne_adresse_und_ohne_text_gibt_es_keinen_anker(umgebung):
    mcp, db = umgebung
    erg = _lauf(mcp, [_t(0, url="", beschreibung="")], quelle="xing", dry_run=False, rohtreffer=1)
    assert erg["trichter"]["angelegt"] == 0 and erg["trichter"]["gruende"] == {"kein_anker": 1}
    assert _stellen(db) == []
    assert "weder Adresse noch Anzeigentext" in erg["trichter_text"]


def test_google_ohne_original_nennt_die_suche_und_legt_nichts_an(umgebung):
    mcp, db = umgebung
    erg = _lauf(mcp, [_t(0, url="", beschreibung="")], quelle="google_jobs", dry_run=False, rohtreffer=5)
    assert erg["trichter"]["gruende"] == {"google_original_fehlt": 1}
    such = erg["uebersprungen"][0]["original_suchen"]
    assert such["suchen"][0]["wo"].startswith("Karriereseite") and "stelle_manuell_anlegen" in such["danach"]
    assert _stellen(db) == []


def test_eine_google_adresse_ist_kein_original(umgebung):
    mcp, db = umgebung
    erg = _lauf(mcp, [_t(0, url="https://www.google.com/search?q=plm&ibp=htl;jobs")], quelle="google_jobs",
                dry_run=False, rohtreffer=1)
    assert erg["trichter"]["gruende"] == {"google_original_fehlt": 1}
    assert erg["uebersprungen"][0]["original_suchen"]["suchen"], "auch hier die vorbereitete Suche"
    assert _stellen(db) == []


def test_google_mit_detail_adresse_wird_angelegt_unter_vorbehalt(umgebung):
    mcp, db = umgebung
    erg = _lauf(mcp, [_t(0, remote="remote")], quelle="google_jobs", dry_run=False, rohtreffer=1)
    assert erg["trichter"]["angelegt"] == 1
    assert erg["angelegt"][0]["google_vorbehalt"]["remote"]["gespeichert"] == "unbekannt"


def test_die_vorschau_sagt_zu_google_dasselbe_wie_der_lauf(umgebung):
    mcp, db = umgebung
    treffer = [_t(0, url="", beschreibung=""), _t(1)]
    vorschau = _lauf(mcp, treffer, quelle="google_jobs", rohtreffer=2)
    lauf = _lauf(mcp, treffer, quelle="google_jobs", rohtreffer=2, dry_run=False)
    assert vorschau["trichter"]["gruende"] == lauf["trichter"]["gruende"] == {"google_original_fehlt": 1}
    assert vorschau["trichter"]["angelegt"] == lauf["trichter"]["angelegt"] == 1


def test_blacklist_und_dubletten_gelten_unveraendert(umgebung):
    mcp, db = umgebung
    db.add_to_blacklist("firma", "Nordlicht", "Zeitarbeit")
    erg = _lauf(mcp, [_t(0, beschreibung=TEXT), _t(1, beschreibung=TEXT)], dry_run=False, rohtreffer=2)
    assert erg["trichter"]["gruende"] == {"blacklist": 1} and erg["trichter"]["angelegt"] == 1
    zweiter = _lauf(mcp, [_t(1, beschreibung=TEXT)], dry_run=False, rohtreffer=1)
    assert zweiter["trichter"]["angelegt"] == 0 and zweiter["trichter"]["gruende"] == {"duplikat_aktiv": 1}
    assert len(db.get_active_jobs()) == 1
    assert len(db.get_scraper_runs("stepstone")) == 2, "auch der Lauf ohne Anlage steht in der Auswertung"


def test_eine_such_adresse_ohne_text_wird_angelegt_aber_gemeldet(umgebung):
    """Im Zweifel hinein - aber der Mensch erfaehrt, dass die Adresse keine Anzeige ist (#436/#766)."""
    mcp, db = umgebung
    erg = _lauf(mcp, [_t(0, url="https://www.stepstone.de/jobs/plm-administrator/in-hamburg")], dry_run=False, rohtreffer=1)
    assert erg["trichter"]["angelegt"] == 1
    e = erg["angelegt"][0]
    assert e.get("url_warnung") and e.get("anker_warnung")
    assert erg["trichter"]["ohne_anker"] == 1 and "ohne verfolgbaren Anker" in erg["trichter_text"]


# ══ Urteil und Aussortieren nach dem Lesen ══════════════════════════════════════════════════════════════════

def test_ein_urteil_wird_nur_mit_gelesenem_volltext_gespeichert(umgebung):
    mcp, db = umgebung
    erg = _lauf(mcp, [
        _t(0, beschreibung=TEXT, urteil="EMPFOHLEN", urteil_begruendung="PLM-Administration, Profil passt"),
        _t(1, urteil="EMPFOHLEN"),
        _t(2, urteil="NICHT_BEURTEILBAR"),
        _t(3, beschreibung=TEXT, urteil="VIELLEICHT"),
    ], dry_run=False, rohtreffer=4)
    gespeichert = {e["titel"]: e for e in erg["angelegt"]}
    mit = gespeichert[TITEL[0]]
    assert mit["urteil"] == "EMPFOHLEN" and erg["trichter"]["mit_urteil"] == 2
    job = db.get_job(mit["hash"])
    assert job["analyse_urteil"] == "EMPFOHLEN" and "Profil passt" in job["analyse_begruendung"]
    ohne = gespeichert[TITEL[1]]
    assert "urteil" not in ohne and "ohne gelesenen Volltext" in ohne["urteil_nicht_gespeichert"]
    assert not (db.get_job(ohne["hash"]).get("analyse_urteil") or "").strip()
    assert gespeichert[TITEL[2]]["urteil"] == "NICHT_BEURTEILBAR", "'noch nicht gelesen' braucht keinen Text"
    falsch = gespeichert[TITEL[3]]
    assert "kein Urteil" in falsch["urteil_nicht_gespeichert"] and "urteil" not in falsch


def test_die_vorschau_speichert_weder_urteil_noch_aussortieren(umgebung):
    mcp, db = umgebung
    vorher = _bestand(db)
    erg = _lauf(mcp, [_t(0, beschreibung=TEXT, urteil="EMPFOHLEN", aussortieren_grund="falsches_fachgebiet")], rohtreffer=1)
    assert erg["trichter"]["angelegt"] == 1 and erg["trichter"]["mit_urteil"] == 0
    assert erg["trichter"]["nach_lesen_aussortiert"] == 0
    assert _bestand(db) == vorher


def test_aussortieren_setzt_grund_herkunft_claude_und_laesst_sich_zurueckholen(umgebung):
    mcp, db = umgebung
    erg = _lauf(mcp, [_t(0, beschreibung=TEXT, aussortieren_grund="falsches_fachgebiet")], dry_run=False, rohtreffer=1)
    e = erg["angelegt"][0]
    assert e["aussortiert"] == {"gruende": ["falsches_fachgebiet"], "herkunft": "claude"}
    assert erg["trichter"]["nach_lesen_aussortiert"] == 1 and "1 nach dem Lesen aussortiert" in erg["trichter_text"]
    (z,) = _stellen(db)
    assert z["is_active"] == 0 and z["dismissed_by"] == "claude" and z["dismiss_reason"] == "falsches_fachgebiet"
    assert db.get_active_jobs() == []
    # Lerneffekt und Statistik laufen wie bei jedem Aussortieren
    assert db.get_setting("dismiss_counts", {}).get("falsches_fachgebiet") == 1
    # Das Protokoll nennt die Herkunft und laesst sich danach filtern
    alle = aussortier_protokoll.eintraege(db, zeitfenster="alle")
    assert [x["herkunft"] for x in alle["eintraege"]] == ["claude"]
    assert aussortier_protokoll.eintraege(db, zeitfenster="alle", herkunft_filter="claude")["eintraege"]
    assert aussortier_protokoll.eintraege(db, zeitfenster="alle", herkunft_filter="ich")["eintraege"] == []
    # Zurueckholen wie jede andere Stelle - und die Herkunft verschwindet mit dem Aussortieren
    assert db.restore_job(z["hash"])
    (z2,) = _stellen(db)
    assert z2["is_active"] == 1 and not z2["dismissed_by"] and not z2["dismiss_reason"]


def test_ein_erfundener_grund_wird_nicht_zur_statistik(umgebung):
    mcp, db = umgebung
    _lauf(mcp, [_t(0, beschreibung=TEXT, aussortieren_grund="windchill_fehlt")], dry_run=False, rohtreffer=1)
    (z,) = _stellen(db)
    assert z["dismiss_reason"] == "sonstiges"
    assert "windchill_fehlt" not in db.get_setting("dismiss_counts", {})


def test_was_claude_aussortiert_hat_wird_beim_naechsten_lauf_nicht_neu_angelegt(umgebung):
    """Der Sinn des Aussortierens nach dem Lesen: der naechste Lauf liest dieselbe Anzeige nicht noch einmal."""
    mcp, db = umgebung
    _lauf(mcp, [_t(0, beschreibung=TEXT, aussortieren_grund="falsches_fachgebiet")], dry_run=False, rohtreffer=1)
    zweiter = _lauf(mcp, [_t(0, beschreibung=TEXT)], dry_run=False, rohtreffer=1)
    assert zweiter["trichter"]["angelegt"] == 0 and zweiter["trichter"]["uebersprungen"] == 1
    assert zweiter["uebersprungen"][0]["grund"].startswith("duplikat")
    (z,) = _stellen(db)
    assert z["is_active"] == 0 and z["dismissed_by"] == "claude"


# ══ Vorschau und Lauf zaehlen gleich ════════════════════════════════════════════════════════════════════════

def _zaehlung(erg):
    t = erg["trichter"]
    return {k: t[k] for k in ("rohtreffer", "uebergeben", "angelegt", "ohne_volltext", "uebersprungen", "gruende")}


SZENARIEN = [
    ("neu", [lambda: _t(0, beschreibung=TEXT)]),
    ("doppelt_in_der_uebergabe", [lambda: _t(0, beschreibung=TEXT), lambda: _t(0, beschreibung=TEXT)]),
    ("mischung", [lambda: _t(0, beschreibung=TEXT), lambda: _t(1), lambda: _t(2, url="", beschreibung=""),
                  lambda: {"titel": "", "firma": FIRMEN[3]}]),
]


@pytest.mark.parametrize("name,treffer", SZENARIEN, ids=[s[0] for s in SZENARIEN])
def test_vorschau_und_lauf_zaehlen_gleich(umgebung, name, treffer):
    mcp, db = umgebung
    eintraege = [t() for t in treffer]
    vorher = _bestand(db)
    vorschau = _lauf(mcp, eintraege, rohtreffer=50, quelle="indeed")
    assert _bestand(db) == vorher
    lauf = _lauf(mcp, eintraege, rohtreffer=50, quelle="indeed", dry_run=False)
    assert _zaehlung(vorschau) == _zaehlung(lauf), "Vorschau und Lauf zaehlen verschieden"
    assert [e["hash"] for e in vorschau["angelegt"]] == [e["hash"] for e in lauf["angelegt"]]
    assert [(u["titel"], u["grund"]) for u in vorschau["uebersprungen"]] == [
        (u["titel"], u["grund"]) for u in lauf["uebersprungen"]]


# ══ Die Anleitungen nennen den Weg ═════════════════════════════════════════════════════════════════════════

def test_das_werkzeug_ist_registriert_und_der_katalogtext_nennt_den_zweck(umgebung):
    mcp, _ = umgebung
    tool = asyncio.run(mcp.get_tool("browser_treffer_uebernehmen"))
    params = tool.parameters["properties"]
    assert params["dry_run"]["default"] is True, "die Vorgabe ist die Vorschau"
    assert {"quelle", "treffer", "rohtreffer", "volltexte_gelesen", "login_fehlt"} <= set(params)
    # Claude liest den kuratierten Katalogtext (`werkzeug_katalog.KURZ`), nicht den Docstring (Falle aus #1182)
    beschreibung = " ".join(tool.description.split())
    assert "Im Zweifel eintragen" in beschreibung and "verbucht den Lauf, auch wenn nichts angelegt wird" in beschreibung
    assert "dry_run=True die Vorschau" in beschreibung and "rohtreffer" in beschreibung
    assert len(beschreibung) <= 600
    # Der Parametertext muss ohne den Docstring tragen: die Eintragsfelder stehen darin
    feld = params["treffer"]["description"]
    for name in ("titel", "firma", "url", "beschreibung", "urteil", "urteil_begruendung", "aussortieren_grund"):
        assert name in feld, name
    assert "siehe oben" not in feld


def test_jede_anleitung_nennt_den_sammelweg(umgebung):
    mcp, db = umgebung
    from bewerbungs_assistent import prompts
    from bewerbungs_assistent.job_scraper.handoff import build_handoff
    texte = {
        "browser_handoff.prompt": bh.prompt(bh.browser_quellen(db, auswahl=["stepstone", "xing", "indeed", "google_jobs"])),
        "quelle_handoff": build_handoff("gulp", "PLM")["anleitung"],
        "jobsuche_workflow": prompts.build_jobsuche_workflow_prompt(db),
        "google_jobs_url": " ".join(_call(mcp, "google_jobs_url", {"keyword": "PLM"})["hinweis"].split()),
    }
    for name, text in texte.items():
        assert "browser_treffer_uebernehmen" in " ".join(text.split()), name


def test_die_anleitung_nennt_nur_vorhandene_werkzeuge(umgebung):
    """Ein Auftrag, der auf ein Werkzeug zeigt, das es nicht gibt, fuehrt ins Leere (#1000)."""
    mcp, db = umgebung
    async def _namen():
        return {t.name for t in await mcp.list_tools()} if hasattr(mcp, "list_tools") else set((await mcp.get_tools()))
    vorhanden = asyncio.run(_namen())
    text = bh.prompt(bh.browser_quellen(db, auswahl=["stepstone", "xing"]))
    genannt = set(re.findall(r"\b((?:browser|stelle|stellen|linkedin)_[a-z_]+)\(", text))
    assert "browser_treffer_uebernehmen" in genannt
    assert not (genannt - vorhanden), genannt - vorhanden


# ══ Reine Teile ═════════════════════════════════════════════════════════════════════════════════════════════

def test_der_trichtertext_ist_ehrlich_auch_bei_null():
    t = bu.trichter_leer()
    assert bu.trichter_text(t) == "0 Rohtreffer, 0 übergeben, 0 angelegt."
    t.update(rohtreffer=300, uebergeben=20, angelegt=4, ohne_volltext=3, ohne_anker=1, nach_lesen_aussortiert=2,
             uebersprungen=16, gruende={"duplikat_aktiv": 10, "kein_anker": 6})
    text = bu.trichter_text(t)
    assert text.startswith("300 Rohtreffer, 20 übergeben, 4 angelegt (davon 3 ohne Volltext, 1 ohne verfolgbaren Anker)")
    assert "2 nach dem Lesen aussortiert" in text and "16 nicht übernommen" in text
    assert text.index("schon als aktive Stelle da: 10") < text.index("weder Adresse noch Anzeigentext: 6"), "haeufigster Grund zuerst"


def test_ein_anker_ist_adresse_oder_text():
    assert bu.hat_anker("https://x.example/1", "", 50)
    assert bu.hat_anker("", "x" * 50, 50)
    assert not bu.hat_anker("", "x" * 49, 50)
    assert not bu.hat_anker("  ", None, 50)
    assert not bu.hat_anker("ftp://x.example", "", 50)


# ══ Stufe 3: was wartet ═════════════════════════════════════════════════════════════════════════════════════

def _job(db, i, **kw):
    j = {"hash": f"h{i:04d}", "title": TITEL[i % len(TITEL)], "company": FIRMEN[i % len(FIRMEN)], "location": "Musterstadt",
         "url": f"https://karriere.beispiel-{i}.example/jobs/{i}", "source": "stepstone", "description": TEXT, "score": 10}
    j.update(kw)
    db.save_jobs([j])
    return j["hash"]


def _zu_pruefen_aufbauen(db, mcp):
    """Sieben Stellen, jede in einem anderen Zustand. Rueckgabe: Hashes nach Rolle."""
    h = {}
    h["neu"] = _job(db, 0)
    h["beurteilt"] = _job(db, 1)
    assert db.set_job_analysis(h["beurteilt"], "BEDINGT", "Methodenluecke")
    h["gesichtet"] = _job(db, 2)
    assert db.mark_job_sighted(h["gesichtet"])
    h["beworben"] = _job(db, 3)
    db.add_application({"title": TITEL[3], "company": FIRMEN[3], "status": "beworben", "job_hash": h["beworben"]})
    h["alt"] = _job(db, 4)
    # gespeichert wird mit Profil-Praefix, die oeffentliche Kennung steht hinten
    db.connect().execute("UPDATE jobs SET found_at='2026-01-02T08:00:00+00:00' WHERE hash=? OR hash LIKE ?",
                         (h["alt"], "%:" + h["alt"]))
    db.connect().commit()
    h["gesperrt"] = _job(db, 5, company="Zeitarbeit Express GmbH", title="Helfer Lager (m/w/d)")
    db.add_to_blacklist("firma", "Zeitarbeit Express", "Zeitarbeit")
    return h


def test_die_zaehlung_folgt_der_regel_der_liste(umgebung):
    mcp, db = umgebung
    h = _zu_pruefen_aufbauen(db, mcp)
    erg = stellen_zu_pruefen.uebersicht(db)
    # ungeprueft: neu + alt; nicht: beurteilt, gesichtet, beworben, gesperrt
    assert erg["ungeprueft"] == 2, erg
    assert erg["neu"] == 1, "'alt' ist ungeprueft, aber nicht aus den letzten Tagen"
    assert erg["von_claude_aussortiert"] == 0 and erg["aussortiert"] == []
    assert erg["tage"] == stellen_zu_pruefen.TAGE_NEU


def test_die_zahl_der_karte_ist_die_zeilenzahl_nach_dem_sprung(umgebung):
    """Die Karte verspricht "N warten" und springt mit dem Filter in die Liste: beide muessen dieselbe Zahl nennen."""
    mcp, db = umgebung
    _zu_pruefen_aufbauen(db, mcp)
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    alt = dash._db
    dash._db = db
    try:
        c = TestClient(dash.app)
        liste = c.get("/api/jobs", params={"pruefstand": "ungeprueft", "beworbene_ausblenden": "true"}).json()
        karte = c.get("/api/stellen/zu-pruefen").json()
    finally:
        dash._db = alt
    assert len(liste["jobs"]) == karte["ungeprueft"] == 2


def test_was_claude_aussortiert_hat_steht_mit_grund_in_der_karte(umgebung):
    mcp, db = umgebung
    _lauf(mcp, [_t(0, beschreibung=TEXT, aussortieren_grund="falsches_fachgebiet"),
                _t(1, beschreibung=TEXT, aussortieren_grund="zu_weit_entfernt")], dry_run=False, rohtreffer=2)
    # eine Stelle, die der Mensch selbst aussortiert hat, ist nicht "von Claude"
    ich = _job(db, 4)
    assert db.dismiss_job(ich, "zeitarbeit")
    erg = stellen_zu_pruefen.uebersicht(db)
    assert erg["von_claude_aussortiert"] == 2
    gruende = {z["titel"]: z["grund"] for z in erg["aussortiert"]}
    assert gruende == {TITEL[0]: "falsches_fachgebiet", TITEL[1]: "zu_weit_entfernt"}
    assert all(z["hash"] and z["firma"] and z["am"] for z in erg["aussortiert"])
    assert erg["ungeprueft"] == 0 and erg["neu"] == 0


def test_die_liste_der_karte_ist_begrenzt_die_zahl_nicht(umgebung):
    mcp, db = umgebung
    for i in range(stellen_zu_pruefen.MAX_LISTE + 5):
        h = _job(db, 10 + i, title=f"Stelle {i}", company=f"Firma {i} GmbH")
        db.dismiss_job(h, "sonstiges", herkunft="claude")
    erg = stellen_zu_pruefen.uebersicht(db)
    assert erg["von_claude_aussortiert"] == stellen_zu_pruefen.MAX_LISTE + 5
    assert len(erg["aussortiert"]) == stellen_zu_pruefen.MAX_LISTE


def test_ein_anderes_profil_sieht_die_stellen_nicht(umgebung):
    mcp, db = umgebung
    _job(db, 0)
    h = _job(db, 1)
    db.dismiss_job(h, "sonstiges", herkunft="claude")
    erstes = db.get_active_profile_id()
    zweites = db.create_profile("Max Beispiel")
    assert db.switch_profile(zweites)
    assert stellen_zu_pruefen.uebersicht(db)["ungeprueft"] == 0
    assert stellen_zu_pruefen.uebersicht(db)["von_claude_aussortiert"] == 0
    db.switch_profile(erstes)
    assert stellen_zu_pruefen.uebersicht(db)["ungeprueft"] == 1
    assert stellen_zu_pruefen.uebersicht(db)["von_claude_aussortiert"] == 1


def test_die_zaehlung_schreibt_nichts_und_haelt_sich_an_die_regel_ohne_bewerbungslesen(umgebung):
    mcp, db = umgebung
    _zu_pruefen_aufbauen(db, mcp)
    vorher = _bestand(db)
    stellen_zu_pruefen.uebersicht(db)
    assert _bestand(db) == vorher
    quelle = (SRC / "services" / "stellen_zu_pruefen.py").read_text(encoding="utf-8")
    assert "get_applications(" not in quelle.split('"""', 2)[2], "get_applications liest je Bewerbung fuenf Abfragen nach (#1143)"


def test_die_schnittstelle_und_der_rueckweg(umgebung):
    mcp, db = umgebung
    _lauf(mcp, [_t(0, beschreibung=TEXT, aussortieren_grund="falsches_fachgebiet")], dry_run=False, rohtreffer=1)
    import bewerbungs_assistent.dashboard as dash
    from fastapi.testclient import TestClient
    alt = dash._db
    dash._db = db
    try:
        c = TestClient(dash.app)
        j = c.get("/api/stellen/zu-pruefen").json()
        assert j["von_claude_aussortiert"] == 1 and j["ungeprueft"] == 0
        hash_ = j["aussortiert"][0]["hash"]
        assert c.post("/api/jobs/restore", json={"hash": hash_}).status_code == 200
        danach = c.get("/api/stellen/zu-pruefen").json()
    finally:
        dash._db = alt
    assert danach["von_claude_aussortiert"] == 0 and danach["aussortiert"] == []
    assert danach["ungeprueft"] == 1, "die zurueckgeholte Stelle wartet wieder auf das Urteil des Menschen"
    assert json.dumps(danach)  # serialisierbar


def test_die_herkunft_claude_steht_im_etikett_der_oberflaeche():
    jobs = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "pages" / "JobsPage.jsx").read_text(encoding="utf-8")
    assert 'claude: "von Claude gelesen und aussortiert"' in jobs
    assert 'job.herkunft === "automatik" || job.herkunft === "claude"' in jobs
    dash = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "pages" / "DashboardPage.jsx").read_text(encoding="utf-8")
    assert "<StellenZuPruefen" in dash
