"""#1187 - Browser-Suchlauf: im Zweifel eintragen, und die Vorschau prueft wirklich.

Gemeldet am 09.10.2026 (Beta 19): ein Lauf ueber sechs Browser-Quellen mit rund 1.300 Rohtreffern legte keine einzige
Stelle in PBP an. Die Anleitungen sagten Claude, "passende" Stellen zu uebernehmen und Verworfenes im Chat zu melden -
die Auswahl traf Claude, der Mensch sah nur den Bericht. Dazu kehrte die Vorschau von `linkedin_treffer_uebernehmen`
(Vorgabe `dry_run=True`) vor jeder Pruefung zurueck und zeigte "alle angelegt", wo der echte Lauf abgewiesen haette.

Teil A prueft, dass JEDE Anleitung dieselbe Regel traegt (`REGEL_IM_ZWEIFEL`, eine Fassung, Lehre L66). Teil B prueft,
dass die Vorschau dieselben Pruefungen macht wie die Anlage und dabei nichts schreibt.

Stable-Fassung (1.7.157): ohne `quelle_handoff` / `build_handoff` - dieser Weg gehoert zur 1.8-Linie.

Alle Firmen, Orte und Adressen in diesen Tests sind erfunden.
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
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import browser_handoff as bh  # noqa: E402

TEXT = (
    "Ihre Aufgaben: Sie betreuen die Engineering-Systeme unseres Werks, pflegen Stuecklisten und Freigabeprozesse "
    "und begleiten die Einfuehrung eines neuen PLM-Systems. Ihr Profil: abgeschlossenes Studium, mehrjaehrige "
    "Erfahrung im Maschinenbau, sicherer Umgang mit Datenmodellen. ") * 3
FIRMA = "Beispielwerk GmbH"
TITEL = "Systemadministrator Teamcenter (m/w/d)"
BROWSER_QUELLEN = ["stepstone", "indeed", "linkedin", "xing", "google_jobs"]


@pytest.fixture
def env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v18_browser_1187_")
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
    db.set_search_criteria("keywords_muss", ["PLM", "Teamcenter"])
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


def _tool_namen(mcp):
    async def _run():
        if hasattr(mcp, "list_tools"):
            return await mcp.list_tools()
        return list((await mcp.get_tools()).values())
    return {t.name for t in asyncio.run(_run())}


# ══ Teil A: eine Regel, alle Anleitungen ═════════════════════════════════════════════════════════════════════

def _anleitungen(db, mcp):
    """Alle Texte, die Claude fuer einen Browserlauf bekommt - jeder ueber seinen echten Einstieg."""
    from bewerbungs_assistent import prompts
    plan = _call(mcp, "linkedin_lauf_plan", {"max_begriffe": 3})
    assert plan["status"] == "bereit", plan
    return {
        "browser_handoff.prompt": bh.prompt(bh.browser_quellen(db, auswahl=BROWSER_QUELLEN)),
        "jobsuche_workflow": prompts.build_jobsuche_workflow_prompt(db),
        "google_jobs_url": _call(mcp, "google_jobs_url", {"keyword": "PLM"})["hinweis"],
        "linkedin_lauf_plan": plan["regel"],
    }


ANLEITUNGEN = ["browser_handoff.prompt", "jobsuche_workflow", "google_jobs_url",
               "linkedin_lauf_plan"]


def test_1187_die_regel_hat_eine_marke_und_steht_nur_einmal_im_code():
    """Eine Entscheidung an einer Stelle (L1, L66): die Fassung steht in `browser_handoff`, alle anderen setzen sie ein."""
    assert bh.REGEL_IM_ZWEIFEL.startswith(bh.MARKE_IM_ZWEIFEL)
    satz = "Eine Stelle zu viel in PBP ist besser als eine zu wenig"
    fundorte = [str(p.relative_to(SRC)) for p in SRC.rglob("*.py") if satz in p.read_text(encoding="utf-8")]
    assert fundorte == [str(Path("services") / "browser_handoff.py")], fundorte


def test_1187_die_regel_nennt_nur_vorhandene_werkzeuge(env):
    """Ein Auftrag, der auf ein Werkzeug zeigt, das es nicht gibt, fuehrt ins Leere (#1000)."""
    _, mcp = env
    genannt = set(re.findall(r"\b([a-z]+(?:_[a-z]+)+)\b", bh.REGEL_IM_ZWEIFEL))
    assert {"stelle_urteil_speichern", "stelle_reaktivieren", "stelle_einordnen"} <= genannt
    fehlt = genannt - _tool_namen(mcp)
    assert not fehlt, fehlt


KERNSAETZE = (
    "Eine Stelle zu viel in PBP ist besser als eine zu wenig",
    "entscheidet der Mensch in PBP, nicht du im Chat",
    "auch wenn ein einzelner Punkt dagegen spricht",
    "Schreibe dein Urteil und den Zweifelsgrund an die Stelle (stelle_urteil_speichern)",
    "Anzeige offen: ja, nein oder unklar",
    "hole sie mit stelle_reaktivieren zurück, statt sie nur im Chat zu erwähnen",
    "Sortiere nur aus (stelle_einordnen), was offensichtlich fachfremd oder geschlossen ist, und nenne den Grund",
    "Der Bericht im Chat ersetzt die Einträge in PBP nicht",
)


@pytest.mark.parametrize("satz", KERNSAETZE)
def test_1187_die_regel_traegt_ihre_kernaussagen(satz):
    """Die Regel besteht aus diesen Aussagen - faellt eine weg, ist es eine andere Regel."""
    assert satz in bh.REGEL_IM_ZWEIFEL


@pytest.mark.parametrize("name", ANLEITUNGEN)
def test_1187_jede_anleitung_setzt_die_regel_ein(env, name):
    db, mcp = env
    text = _anleitungen(db, mcp)[name]
    assert bh.MARKE_IM_ZWEIFEL in text, name
    assert bh.REGEL_IM_ZWEIFEL in text, f"{name}: die Regel steht nicht vollstaendig da"


ALTE_FORMULIERUNGEN = ("Übernimm passende", "Passende Stellen mit", "passende Treffer mit", "Passende Stellen übernehmen",
                       "Passende Stellen uebernehmen", "Nicht für Treffer aus einer Jobbörse", "und verworfen mit Grund")


@pytest.mark.parametrize("name", ANLEITUNGEN)
def test_1187_keine_anleitung_laesst_claude_vorab_auswaehlen(env, name):
    db, mcp = env
    text = _anleitungen(db, mcp)[name]
    for alt in ALTE_FORMULIERUNGEN:
        assert alt not in text, f"{name}: '{alt}'"


def test_1187_der_bericht_im_chat_ersetzt_die_eintraege_nicht(env):
    db, _ = env
    text = bh.prompt(bh.browser_quellen(db, auswahl=BROWSER_QUELLEN))
    assert "Rohtreffer, in PBP angelegt, schon bekannt, aussortiert mit Grund" in text
    assert "Der Bericht ersetzt die Einträge nicht" in text
    assert "Der Titel allein sagt zu wenig" in text


# Was einen Auftrag an Claude als "such dir die passenden aus" ausweist. Positivprobe unten: das Muster trifft die
# alte Fassung, sonst waere ein leeres Ergebnis kein Beleg.
_AUSWAHL = re.compile(
    r"(?i)(?:ü|ue)bernimm\s+passende|passende[nr]?\s+(?:stellen|treffer)\s+(?:mit\s+\S+\s+)?(?:ü|ue)bernehm"
    r"|passende[nr]?\s+(?:stellen|treffer)\s+mit\s+stelle_manuell_anlegen|passende\s+treffer\s+\S+\s+\S+\s+erfassen")


def test_1187_das_auswahlmuster_trifft_die_alte_fassung():
    assert _AUSWAHL.search("Übernimm passende Stellen mit stelle_manuell_anlegen()")
    assert _AUSWAHL.search("3. Passende Stellen mit stelle_manuell_anlegen(titel, firma")
    assert _AUSWAHL.search("passende Treffer mit stelle_manuell_anlegen() erfassen")
    assert not _AUSWAHL.search("Alle Treffer, die fachlich passen oder nahezu passen, mit stelle_manuell_anlegen()")
    assert not _AUSWAHL.search("Soll ich dir passende Stellen zeigen?")


def test_1187_kein_text_im_code_sagt_claude_passende_treffer_zu_uebernehmen():
    """Wer eine neue Anleitung schreibt, schreibt leicht wieder 'passende Stellen uebernehmen' - dieser Wortlaut hat den
    leeren Lauf verursacht. Der Waechter liest den ganzen Quelltext, nicht nur die bekannten Einstiege."""
    funde = []
    for pfad in SRC.rglob("*.py"):
        if "static" in pfad.parts:
            continue
        text = pfad.read_text(encoding="utf-8")
        text = re.sub(r"\s*\n\s*", " ", text)      # ein Satz, der ueber Zeilen laeuft
        for m in _AUSWAHL.finditer(text):
            funde.append(f"{pfad.relative_to(SRC)}: ...{text[max(0, m.start() - 20):m.end() + 40]}...")
    assert not funde, funde


def test_1187_der_katalogtext_gilt_auch_fuer_den_browserlauf(env):
    _, mcp = env
    beschreibung = asyncio.run(mcp.get_tool("stelle_manuell_anlegen")).description
    assert "Browserlauf" in beschreibung and "im Zweifel eintragen" in beschreibung
    assert "Nicht für Treffer aus einer Jobbörse" not in beschreibung
    assert len(beschreibung) <= 600


def test_1187_der_plan_trennt_vorfilter_und_urteil(env):
    _, mcp = env
    plan = _call(mcp, "linkedin_lauf_plan", {"max_begriffe": 3})
    ablauf = " ".join(plan["ablauf"])
    assert "spart nur Requests und urteilt nicht" in ablauf
    assert "dry_run=True" in ablauf and "dry_run=False" in ablauf
    assert plan["regel"] == bh.REGEL_IM_ZWEIFEL


def test_1187_der_hinweis_zur_aussortierten_dublette_laesst_den_zweifel_zu(env):
    """Sonst sagt dieser Text 'ordne mit demselben Grund ein', die Regel 'hole zurueck, was fachlich passt'."""
    db, mcp = env
    db.save_jobs([{"hash": "alt1187", "title": TITEL, "company": FIRMA, "location": "Musterstadt",
                   "url": "https://example.com/alt1187", "source": "manuell", "description": TEXT}])
    assert db.dismiss_job("alt1187", "zu_weit_entfernt")
    res = _call(mcp, "stelle_manuell_anlegen", {
        "titel": TITEL, "firma": FIRMA, "ort": "Musterstadt", "quelle": "linkedin",
        "url": "https://example.com/neu1187", "beschreibung": TEXT})
    hinweis = res["aussortierte_dublette"]["hinweis"]
    assert "stelle_einordnen" in hinweis and "stelle_urteil_speichern" in hinweis
    assert "entscheidet der Mensch" in hinweis


# ══ Teil B: die Vorschau prueft wie die Anlage und schreibt nichts ═══════════════════════════════════════════

def _treffer(job_id="9001", titel=TITEL, firma=FIRMA, **kw):
    d = {"job_id": job_id, "titel": titel, "firma": firma, "ort": "Musterstadt", "remote": "hybrid",
         "beschreibung": TEXT}
    d.update(kw)
    return d


def _lauf(mcp, treffer, dry_run):
    return _call(mcp, "linkedin_treffer_uebernehmen", {"treffer": treffer, "dry_run": dry_run})


def _bestand(db):
    """Zeilenzahl jeder Tabelle - ein Schreibzugriff irgendwo faellt auf."""
    conn = db.connect()
    namen = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    return {n: conn.execute(f'SELECT COUNT(*) FROM "{n}"').fetchone()[0] for n in namen}


def _zaehlung(res):
    t = res["trichter"]
    return {k: t[k] for k in ("rohtreffer", "nach_vorfilter", "volltexte", "angelegt", "uebersprungen", "gruende")}


def _vorhanden_anlegen(db, mcp):
    res = _call(mcp, "stelle_manuell_anlegen", {
        "titel": TITEL, "firma": FIRMA, "ort": "Musterstadt", "quelle": "linkedin",
        "url": "https://example.com/vorhanden1187", "beschreibung": TEXT})
    assert res["status"] == "angelegt", res


def _bewerbung(db, mcp):
    db.add_application({"title": TITEL, "company": FIRMA, "status": "beworben"})


def _gesperrt(db, mcp):
    db.add_to_blacklist("firma", "Beispielwerk", "Zeitarbeit")


def _aussortiert(db, mcp):
    db.save_jobs([{"hash": "alt1187", "title": TITEL, "company": FIRMA, "location": "Musterstadt",
                   "url": "https://example.com/alt1187", "source": "manuell", "description": TEXT}])
    assert db.dismiss_job("alt1187", "zu_weit_entfernt")


def _nichts(db, mcp):
    return None


# (Name, Vorbereitung, Treffer, erwartete Gruende, erwartet angelegt)
SZENARIEN = [
    ("neu", _nichts, [_treffer()], {}, 1),
    ("blacklist", _gesperrt, [_treffer()], {"blacklist": 1}, 0),
    ("gleiche_kennung", _vorhanden_anlegen, [_treffer("9002")], {"duplikat_aktiv": 1}, 0),
    ("laufende_bewerbung", _bewerbung, [_treffer("9003")], {"duplikat_beworben": 1}, 0),
    ("doppelt_im_aufruf", _nichts, [_treffer("9004"), _treffer("9005")], {"duplikat_aktiv": 1}, 1),
    ("ohne_volltext", _nichts, [_treffer("9006", beschreibung="zu kurz")], {"volltext_fehlt": 1}, 0),
    ("aussortierte_dublette", _aussortiert, [_treffer("9007")], {}, 1),
    ("mischung", _gesperrt, [_treffer("9008"), _treffer("9009", firma="Andere Firma AG", titel="PLM Berater"),
                             _treffer("9010", beschreibung="kurz"),
                             _treffer("9011", firma="Andere Firma AG", titel="PLM Berater")],
     {"blacklist": 1, "volltext_fehlt": 1, "duplikat_aktiv": 1}, 1),
]


@pytest.mark.parametrize("name,vorbereiten,treffer,gruende,angelegt", SZENARIEN, ids=[s[0] for s in SZENARIEN])
def test_1187_vorschau_und_lauf_zaehlen_gleich_und_die_vorschau_schreibt_nichts(
        env, name, vorbereiten, treffer, gruende, angelegt):
    db, mcp = env
    vorbereiten(db, mcp)
    vorher = _bestand(db)

    vorschau = _lauf(mcp, treffer, dry_run=True)
    assert _bestand(db) == vorher, "die Vorschau hat etwas geschrieben"
    assert vorschau["status"] == "vorschau"

    lauf = _lauf(mcp, treffer, dry_run=False)
    assert lauf["status"] == "uebernommen"

    assert _zaehlung(vorschau) == _zaehlung(lauf), "Vorschau und Lauf zaehlen verschieden"
    assert [(e["job_id"], e["hash"]) for e in vorschau["angelegt"]] == [(e["job_id"], e["hash"]) for e in lauf["angelegt"]]
    assert [(e["job_id"], e["grund"]) for e in vorschau["uebersprungen"]] == [
        (e["job_id"], e["grund"]) for e in lauf["uebersprungen"]]
    # Nicht nur gleich, sondern in der Sache richtig - zwei blinde Seiten waeren auch gleich.
    assert vorschau["trichter"]["gruende"] == gruende
    assert vorschau["trichter"]["angelegt"] == angelegt


def test_1187_die_vorschau_protokolliert_die_blacklist_nicht(env):
    db, mcp = env
    _gesperrt(db, mcp)
    _lauf(mcp, [_treffer()], dry_run=True)
    assert db.get_blacklist_blocks() == []
    _lauf(mcp, [_treffer()], dry_run=False)
    assert [p["kontext"] for p in db.get_blacklist_blocks()] == ["manuell_abgewiesen"]


def test_1187_die_vorschau_legt_keinen_kontakt_an(env):
    db, mcp = env
    kontakt = {"kontakt_name": "Erika Beispiel", "kontakt_email": "kontakt@example.com"}
    vorher = _bestand(db)
    vorschau = _lauf(mcp, [_treffer(**kontakt)], dry_run=True)
    assert _bestand(db) == vorher
    assert "kontakt" not in vorschau["angelegt"][0]
    lauf = _lauf(mcp, [_treffer(**kontakt)], dry_run=False)
    assert lauf["angelegt"][0].get("kontakt"), "der echte Lauf legt den Kontakt an"
    assert _bestand(db)["contacts"] == vorher["contacts"] + 1


def test_1187_nur_die_vorschau_nennt_die_laenge_des_volltexts(env):
    _, mcp = env
    vorschau = _lauf(mcp, [_treffer()], dry_run=True)
    assert vorschau["angelegt"][0]["beschreibung_zeichen"] == len(TEXT.strip())
    lauf = _lauf(mcp, [_treffer()], dry_run=False)
    assert "beschreibung_zeichen" not in lauf["angelegt"][0]


def test_1187_die_vorschau_meldet_die_hinweise_wie_der_lauf(env):
    """Aussortierte Dublette, laufende Bewerbung: der Mensch soll sie VOR dem Anlegen sehen."""
    db, mcp = env
    _aussortiert(db, mcp)
    vorschau = _lauf(mcp, [_treffer("9020")], dry_run=True)
    eintrag = vorschau["angelegt"][0]
    assert eintrag["aussortierte_dublette"]["aussortiert_wegen"] == ["zu_weit_entfernt"]
    assert vorschau["trichter"]["aussortierte_dublette"] == 1
    assert "schon aussortiert 1" in vorschau["trichter_text"]
    lauf = _lauf(mcp, [_treffer("9020")], dry_run=False)
    assert lauf["angelegt"][0]["aussortierte_dublette"] == eintrag["aussortierte_dublette"]


def test_1187_stelle_manuell_anlegen_zeigt_den_trockenlauf_nicht(env):
    """`trocken` ist ein Schalter fuer die Sammeluebernahme, kein Werkzeugparameter fuer Claude."""
    _, mcp = env
    schema = asyncio.run(mcp.get_tool("stelle_manuell_anlegen")).parameters["properties"]
    assert "trocken" not in schema
    assert "dry_run" not in schema


def test_1187_der_docstring_der_sammeluebernahme_sagt_was_die_vorschau_prueft():
    quelle = (SRC / "tools" / "jobs.py").read_text(encoding="utf-8")
    assert "denselben Prüfungen wie der echte Lauf" in quelle
    assert "trocken=dry_run" in quelle
