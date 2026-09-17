"""Tests fuer #1054 — Abgleich Profil gegen Suchbegriffe (C87).

Der Fachwert misst die Suchbegriffe. Das ist nur eine Aussage ueber den
Bewerber, wenn die Listen sein Profil abbilden — und die driften, weil
sie von Hand gepflegt werden. Von Hand gefunden am 15.09.2026: zwanzig
Skills in keiner Liste, sechs MINUS-Begriffe auf dem eigenen Fachgebiet,
neun Rahmenbegriffe in der PLUS-Liste.

Der Regressionsfall (AK 6) baut diesen Bestand nach — mit Platzhaltern
fuer Orte und mit Skill-Namen, die im Issue stehen oder derselben
Fachrichtung entstammen. Alle Firmen und Orte sind Platzhalter.
"""
import asyncio
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.services import suchbegriff_abgleich as sa  # noqa: E402


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17119_abgleich_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test", "city": "Musterstadt"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _skill(db, name, level=4, level_current=None, category="fachlich"):
    daten = {"name": name, "category": category, "level": level}
    if level_current is not None:
        daten["level_current"] = level_current
    return db.add_skill(daten)


FUELLTEXT = ("Wir bieten ein modernes Arbeitsumfeld mit flachen "
             "Hierarchien und viel Gestaltungsspielraum. ") * 4


def _stelle(db, hash_, titel, text):
    db.save_jobs([{
        "hash": hash_, "title": titel, "company": "Musterfirma GmbH",
        "location": "Musterstadt", "url": f"https://example.com/1054/{hash_}",
        "source": "manuell", "_manual_entry": True,
        "description": text + " " + FUELLTEXT,
        "employment_type": "festanstellung", "score": 5.0,
    }])
    return db.get_active_jobs()


# ══ AK 6: der Bestand vom 15.09.2026 als Vorlage ═══════════════════

# Zwanzig Skills, die in keiner Liste standen. Sechs davon nennt das
# Issue woertlich; die uebrigen sind Fachbegriffe derselben Richtung.
ZWANZIG_SKILLS = [
    ("Change Management", 5), ("ECR/ECO/ECN-Prozesse", 4), ("BOM", 4),
    ("Data Governance", 5), ("Master Data Management", 4),
    ("DMS/Document Control", 4), ("Stuecklistenmanagement", 4),
    ("Variantenmanagement", 4), ("Freigabeprozesse", 5),
    ("Datenmigration", 4), ("Datenqualitaet", 5), ("Prozessmodellierung", 4),
    ("Anforderungsmanagement", 4), ("Schulung", 4), ("Workshop-Moderation", 5),
    ("Stakeholder-Management", 4), ("Projektleitung", 5), ("Testmanagement", 4),
    ("Rollout", 4), ("Change Request", 4),
]

SECHS_MINUS = ["Konfigurationsmanagement", "Configuration Management",
               "Konfigurationsmanager", "CMII", "Baseline Management", "LoCI"]

# Neun Begriffe ohne fachliche Aussage in der PLUS-Liste. Zwei Orte
# (Platzhalter), drei Arbeitsmodelle, zwei Vertragsformen, zwei
# Zusatzleistungen — die Verteilung aus dem Issue.
NEUN_RAHMEN = ["Remote", "Homeoffice", "hybrid", "Musterstadt", "Musterberg",
               "Festanstellung", "Freelance", "Firmenwagen", "Mobilitätsbudget"]


def _bestand_vom_15_09(db):
    for name, level in ZWANZIG_SKILLS:
        _skill(db, name, level)
    # Ein Skill, der in der MUSS-Liste steht — er darf NICHT fehlen.
    _skill(db, "PLM", 5)
    db.set_search_criteria("keywords_muss", ["PLM System", "Teamcenter"])
    db.set_search_criteria("keywords_plus", NEUN_RAHMEN + ["SAP"])
    db.set_search_criteria("keywords_minus", SECHS_MINUS)
    db.set_search_criteria("regionen", ["Musterland"])
    # Der zweite Ort ist nur ueber den Stellenbestand bekannt — und die
    # sechs MINUS-Begriffe ueber die eigenen Bewerbungen: das ist der
    # Weg, auf dem "auf zwei davon hatte er sich beworben" sichtbar wird.
    # Zwei Bewerbungen, weil ein Texttreffer erst ab zwei Bewerbungen
    # zaehlt — "auf zwei davon hatte er sich beworben" steht im Issue.
    _stelle(db, "b1", "Konfigurationsmanager Marine",
            "Konfigurationsmanagement nach CMII, Baseline Management und "
            "LoCI-Prozesse. Configuration Management im Systemumfeld.")
    _stelle(db, "b2", "Systemingenieur Wehrtechnik",
            "Konfigurationsmanagement nach CMII, Baseline Management und "
            "LoCI. Configuration Management als Konfigurationsmanager.")
    for job in db.get_active_jobs():
        if job["title"] in ("Konfigurationsmanager Marine", "Systemingenieur Wehrtechnik"):
            db.add_application({"title": job["title"], "company": job["company"],
                                "job_hash": job["hash"], "status": "beworben"})
    db.save_jobs([{
        "hash": "o1", "title": "Sachbearbeitung", "company": "Musterfirma GmbH",
        "location": "Musterberg", "url": "https://example.com/1054/o1",
        "source": "manuell", "_manual_entry": True,
        "description": FUELLTEXT, "employment_type": "festanstellung",
    }])


def test_der_bestand_vom_15_09_ergibt_zwanzig_sechs_neun(umgebung):
    """AK 6 woertlich: zwanzig fehlende Begriffe, sechs Widersprueche,
    neun Rahmenbegriffe — auf dem Bestand, wie er vor der Handkorrektur
    aussah."""
    db, _ = umgebung
    _bestand_vom_15_09(db)
    e = sa.abgleich(db)
    assert len(e["fehlende_skills"]) == 20, [v["begriff"] for v in e["fehlende_skills"]]
    assert len(e["widersprueche"]) == 6, [v["begriff"] for v in e["widersprueche"]]
    assert len(e["rahmenbegriffe"]) == 9, [v["begriff"] for v in e["rahmenbegriffe"]]
    assert e["offen"] == 35
    # Der Skill, der in der Liste steht, fehlt nicht — obwohl er dort
    # "PLM System" heisst und im Profil "PLM" (AK 2).
    assert "PLM" not in {v["begriff"] for v in e["fehlende_skills"]}
    # SAP ist ein Fachbegriff und bleibt.
    assert "SAP" not in {v["begriff"] for v in e["rahmenbegriffe"]}


# ══ 1. Fehlende Skills ══════════════════════════════════════════════

def test_level_entscheidet_ueber_die_zielliste(umgebung):
    db, _ = umgebung
    _skill(db, "Datenmigration", 5)
    _skill(db, "Excel", 3)
    # Spitze 5, aktuell 2: der Mensch sucht mit dem, was er heute kann.
    _skill(db, "COBOL", 5, level_current=2)
    ziele = {v["begriff"]: v["ziel"] for v in sa.abgleich(db)["fehlende_skills"]}
    assert ziele["Datenmigration"] == "keywords_muss"
    assert ziele["Excel"] == "keywords_plus"
    # Unter Level 3 wird nichts vorgeschlagen — nach Grundkenntnissen
    # sucht niemand Stellen. Wer alles sehen will, senkt die Grenze.
    assert "COBOL" not in ziele
    alle = {v["begriff"]: v["ziel"]
            for v in sa.abgleich(db, mindest_level=1)["fehlende_skills"]}
    assert alle["COBOL"] == "keywords_plus"


def test_nur_fachliches_geht_nach_muss_sprachen_und_soft_skills_nie(umgebung):
    """Auf der Bestandskopie standen "Deutsch (Muttersprache)" und
    "Verhandlungsfuehrung" als MUSS-Vorschlag, beide Level 4/5. Die
    MUSS-Liste ist das Tor (#968) — dort gehoert nur Fachliches hin;
    Werkzeuge und Methoden nach PLUS; Sprachen und Soft Skills sind
    keine Suchbegriffe. Die Kategorie steht im Bestand als Freitext
    ("Tools", "Softskills"), verglichen wird nach dem Wortanfang."""
    db, _ = umgebung
    _skill(db, "Datenmigration", 5, category="fachlich")
    _skill(db, "Agile/Scrum", 5, category="methodisch")
    _skill(db, "Deutsch (Muttersprache)", 5, category="sprache")
    # `add_skill` glaettet die Kategorie (#128). Die Freitext-Formen im
    # Bestand ("Tools", "Softskills", "KI/AI") stammen von anderen
    # Schreibern — hier werden sie fuer den isolierten Test direkt
    # gesetzt, damit die Normalisierung im Abgleich wirklich laeuft.
    roh = {
        _skill(db, "MS Visio", 4): "Tools",
        _skill(db, "Verhandlungsfuehrung", 4): "Softskills",
        _skill(db, "Prompt Engineering", 4): "KI/AI",   # unbekannt -> fachlich
    }
    conn = db.connect()
    for sid, kat in roh.items():
        conn.execute("UPDATE skills SET category=? WHERE id=?", (kat, sid))
    conn.commit()
    assert {s["category"] for s in db.get_profile()["skills"]} >= {"Tools", "Softskills", "KI/AI"}
    ziele = {v["begriff"]: v["ziel"] for v in sa.abgleich(db)["fehlende_skills"]}
    assert ziele == {"Datenmigration": "keywords_muss",
                     "MS Visio": "keywords_plus",
                     "Agile/Scrum": "keywords_plus",
                     "Prompt Engineering": "keywords_muss"}


def test_der_vorgeschlagene_begriff_ist_ein_suchbegriff(umgebung):
    """"Stakeholder-Management (C-Level/SVP)" trifft keine Anzeige — die
    Klammer steht dort nie. "Konfliktloesung & Eskalationsmanagement"
    sind zwei Begriffe. Ein Schraegstrich bleibt ("ECR/ECO/ECN")."""
    assert sa.suchbegriff_aus("Stakeholder-Management (C-Level/SVP)") == ["Stakeholder-Management"]
    assert sa.suchbegriff_aus("Konfliktloesung & Eskalationsmanagement") == ["Konfliktloesung", "Eskalationsmanagement"]
    assert sa.suchbegriff_aus("ECR/ECO/ECN-Prozesse") == ["ECR/ECO/ECN-Prozesse"]

    db, _ = umgebung
    _skill(db, "Stakeholder-Management (C-Level/SVP)", 5)
    _skill(db, "Konfliktloesung & Eskalationsmanagement", 4)
    e = sa.abgleich(db)
    v = {x["begriff"]: x for x in e["fehlende_skills"]}
    assert v["Stakeholder-Management (C-Level/SVP)"]["begriffe"] == ["Stakeholder-Management"]
    # Uebernommen wird die bereinigte Form — beide Teile.
    antwort = sa.uebernehmen(db, v["Konfliktloesung & Eskalationsmanagement"]["schluessel"])
    assert antwort["eingetragen"] == ["Konfliktloesung", "Eskalationsmanagement"]
    assert "Konfliktloesung" in db.get_search_criteria()["keywords_muss"]
    # Steht die bereinigte Form schon in der Liste, fehlt nichts mehr.
    db.set_search_criteria("keywords_plus", ["Stakeholder-Management"])
    assert [x["begriff"] for x in sa.abgleich(db)["fehlende_skills"]] == []


def test_vertragsformen_in_minus_zaehlen_doppelt_und_werden_genannt(umgebung):
    """Nicht im Issue, aber auf der Bestandskopie: sechs Vertragsformen
    in MINUS ("befristet", "Zeitarbeit", ...), jede zusaetzlich als
    Regler `stellentyp/...` gewertet. Ein Ort in MINUS bleibt — dafuer
    gibt es keinen Regler, die Liste ist dort der einzige Weg."""
    db, _ = umgebung
    db.set_search_criteria("keywords_minus", ["Zeitarbeit", "befristet", "Remote",
                                              "Musterstadt", "Vertrieb"])
    r = {v["begriff"]: v for v in sa.abgleich(db)["rahmenbegriffe"]}
    assert set(r) == {"Zeitarbeit", "befristet", "Remote"}
    assert r["Zeitarbeit"]["liste"] == "keywords_minus"
    assert "doppelt" in r["Zeitarbeit"]["grund"]


def test_die_begriffsgruppierung_erkennt_vorhandene_skills(umgebung):
    """AK 2: kein Zeichenkettenvergleich. "PLM" ist in "PLM System"
    enthalten, "PLM" und "Teamcenter" sind ueber PBPs Synonym-Karte
    dasselbe (#1012)."""
    db, _ = umgebung
    _skill(db, "PLM", 5)
    _skill(db, "Teamcenter", 4)
    _skill(db, "Product Lifecycle Management", 4)   # Abkuerzung: PLM
    db.set_search_criteria("keywords_muss", ["PLM System"])
    assert sa.abgleich(db)["fehlende_skills"] == []


def test_ein_rahmenbegriff_im_profil_wird_nicht_als_skill_vorgeschlagen(umgebung):
    """"Homeoffice" als Skill gehoert auch dann in keine Fachliste, wenn
    es dort fehlt — sonst schluege der Abgleich vor, was er zwei Zeilen
    weiter als Fehler meldet."""
    db, _ = umgebung
    _skill(db, "Homeoffice", 4)
    _skill(db, "Festanstellung", 4)
    assert sa.abgleich(db)["fehlende_skills"] == []


# ══ 2. Widersprueche ════════════════════════════════════════════════

def test_ein_minus_begriff_auf_dem_eigenen_skill_ist_ein_widerspruch(umgebung):
    db, _ = umgebung
    _skill(db, "Konfigurationsmanagement", 5)
    db.set_search_criteria("keywords_minus", ["Konfigurationsmanagement", "Vertrieb"])
    w = sa.abgleich(db)["widersprueche"]
    assert [v["begriff"] for v in w] == ["Konfigurationsmanagement"]
    assert w[0]["profil_skill"] == "Konfigurationsmanagement"
    assert w[0]["level"] == 5
    # Beide Seiten stehen da, NICHTS ist aufgeloest.
    assert "Vertrieb" not in [v["begriff"] for v in w]
    assert db.get_search_criteria()["keywords_minus"] == ["Konfigurationsmanagement", "Vertrieb"]


def test_ein_minus_begriff_in_einer_beworbenen_stelle_ist_ein_widerspruch(umgebung):
    """Der gemeldete Fall braucht diesen Beleg: "CMII" hat zu keinem
    Profil-Skill eine belegbare Beziehung — aber es steht in einer
    Stelle, auf die sich der Mensch beworben hat. Gemessen mit derselben
    Regel, die den Begriff im Score bestraft."""
    db, _ = umgebung
    _skill(db, "Change Management", 5)
    db.set_search_criteria("keywords_minus", ["CMII", "Vertrieb"])
    _stelle(db, "w1", "Konfigurationsmanager CMII", "Arbeit im Aenderungswesen.")
    job = db.get_active_jobs()[0]
    db.add_application({"title": job["title"], "company": job["company"],
                        "job_hash": job["hash"], "status": "beworben"})
    w = sa.abgleich(db)["widersprueche"]
    assert [v["begriff"] for v in w] == ["CMII"]
    assert w[0]["beworbene_stellen"][0]["titel"] == "Konfigurationsmanager CMII"
    assert w[0]["beleg"] == "titel"
    assert "im Titel" in w[0]["grund"]
    assert "profil_skill" not in w[0]


def test_ein_texttreffer_zaehlt_erst_ab_zwei_bewerbungen(umgebung):
    """Auf der Bestandskopie hatten sechs von zwoelf Widerspruechen genau
    EINEN Texttreffer — ein Wort in einer langen Anzeige, oft in einer
    Verneinung oder im Firmenabsatz. Wer sich zweimal auf Anzeigen mit
    dem Begriff bewirbt, hat ihn nicht uebersehen; einmal sagt nichts."""
    db, _ = umgebung
    db.set_search_criteria("keywords_minus", ["Customizing"])
    _stelle(db, "t1", "PLM Berater", "Customizing der Plattform gehoert dazu.")
    job = db.get_active_jobs()[0]
    db.add_application({"title": job["title"], "company": job["company"],
                        "job_hash": job["hash"], "status": "beworben"})
    assert sa.abgleich(db)["widersprueche"] == []

    _stelle(db, "t2", "PLM Consultant", "Customizing und Rollout.")
    job2 = [j for j in db.get_active_jobs() if j["title"] == "PLM Consultant"][0]
    db.add_application({"title": job2["title"], "company": job2["company"],
                        "job_hash": job2["hash"], "status": "beworben"})
    w = sa.abgleich(db)["widersprueche"]
    assert [v["begriff"] for v in w] == ["Customizing"]
    assert w[0]["beleg"] == "text"
    assert len(w[0]["beworbene_stellen"]) == 2


def test_eine_nur_gesichtete_stelle_belegt_keinen_widerspruch(umgebung):
    """Die Gegenrichtung: eine Stelle im Bestand, auf die sich niemand
    beworben hat, sagt nichts ueber die MINUS-Liste."""
    db, _ = umgebung
    db.set_search_criteria("keywords_minus", ["CMII"])
    # Im TITEL — bei einer Bewerbung wuerde das sofort zaehlen. Ohne
    # Bewerbung darf es das nicht.
    _stelle(db, "w2", "Konfigurationsmanager CMII", "Arbeit im Aenderungswesen.")
    assert sa.abgleich(db)["widersprueche"] == []


# ══ 3. Rahmenbegriffe ═══════════════════════════════════════════════

@pytest.mark.parametrize("begriff, art", [
    ("Remote", sa.ARBEITSMODELL), ("Home-Office", sa.ARBEITSMODELL),
    ("hybrid", sa.ARBEITSMODELL), ("Festanstellung", sa.VERTRAGSFORM),
    ("Freelance", sa.VERTRAGSFORM), ("Vollzeit", sa.VERTRAGSFORM),
    ("Firmenwagen", sa.ZUSATZLEISTUNG), ("Mobilitätsbudget", sa.ZUSATZLEISTUNG),
    ("Mobilitaetsbudget", sa.ZUSATZLEISTUNG), ("Deutschland", sa.ORT),
])
def test_rahmenbegriffe_werden_erkannt(begriff, art):
    assert sa.rahmenbegriff_art(begriff, set()) == art


@pytest.mark.parametrize("begriff", ["SAP", "PLM", "Stammdaten", "Change Management",
                                     "Python", "Remote Sensing"])
def test_fachbegriffe_bleiben_fachbegriffe(begriff):
    """Die Gegenrichtung (#966): "Remote Sensing" ist ein Fach, kein
    Arbeitsmodell — verglichen wird der ganze Begriff, nicht ein Wort
    darin."""
    assert sa.rahmenbegriff_art(begriff, set()) is None


def test_ein_ort_ist_nur_ein_ort_wenn_pbp_ihn_kennt(umgebung):
    """Keine Staedteliste im Code. Ein Ort ist die Stadt des Profils,
    eine Region aus den Kriterien oder eine Ortsangabe aus dem eigenen
    Bestand. "Bedford" kennt PBP nicht — es bleibt, wo es steht (#989:
    unbekannt ist nicht "Rahmenbegriff")."""
    db, _ = umgebung
    db.set_search_criteria("keywords_plus", ["Musterstadt", "Musterland", "Musterberg", "Bedford"])
    db.set_search_criteria("regionen", ["Musterland"])
    db.save_jobs([{
        "hash": "o2", "title": "Sachbearbeitung", "company": "Musterfirma GmbH",
        "location": "Musterberg, Musterland", "url": "https://example.com/1054/o2",
        "source": "manuell", "_manual_entry": True,
        "description": FUELLTEXT, "employment_type": "festanstellung",
    }])
    orte = {v["begriff"] for v in sa.abgleich(db)["rahmenbegriffe"]
            if v["rahmen_art"] == sa.ORT}
    assert orte == {"Musterstadt", "Musterland", "Musterberg"}


def test_ein_rahmenbegriff_nennt_wohin_er_gehoert(umgebung):
    db, _ = umgebung
    db.set_search_criteria("keywords_muss", ["Festanstellung"])
    db.set_search_criteria("keywords_plus", ["Remote", "Firmenwagen"])
    r = {v["begriff"]: v for v in sa.abgleich(db)["rahmenbegriffe"]}
    assert r["Festanstellung"]["liste"] == "keywords_muss"
    assert "stellentypen" in r["Festanstellung"]["grund"]
    assert "Remote-Regler" in r["Remote"]["grund"]
    assert "keine Liste" in r["Firmenwagen"]["grund"]


# ══ Bestaetigung, Verwerfen, Gedaechtnis ════════════════════════════

def test_der_abgleich_schreibt_nichts(umgebung):
    """AK 3: nichts ohne Bestaetigung — auch nicht beim Nachsehen."""
    db, _ = umgebung
    _bestand_vom_15_09(db)
    vorher = db.get_search_criteria()
    sa.abgleich(db)
    sa.abgleich(db)
    assert db.get_search_criteria() == vorher
    assert db.get_profile_setting(sa.MARKE_VERWORFEN) is None


def test_uebernehmen_setzt_einen_fehlenden_skill_in_die_liste(umgebung):
    db, _ = umgebung
    _skill(db, "Datenmigration", 5)
    _skill(db, "Excel", 3)
    db.set_search_criteria("keywords_muss", ["PLM"])
    e = sa.abgleich(db)
    s = {v["begriff"]: v["schluessel"] for v in e["fehlende_skills"]}
    assert sa.uebernehmen(db, s["Datenmigration"])["liste"] == "keywords_muss"
    # `ziel` ueberschreibt den Vorschlag.
    assert sa.uebernehmen(db, s["Excel"], ziel="keywords_muss")["liste"] == "keywords_muss"
    krit = db.get_search_criteria()
    assert krit["keywords_muss"] == ["PLM", "Datenmigration", "Excel"]
    assert sa.abgleich(db)["fehlende_skills"] == []
    # Ein unbekanntes Ziel wird abgewiesen, nicht geraten.
    _skill(db, "Python", 4)
    s2 = sa.abgleich(db)["fehlende_skills"][0]["schluessel"]
    assert "fehler" in sa.uebernehmen(db, s2, ziel="keywords_minus")


def test_uebernehmen_nimmt_widerspruch_und_rahmenbegriff_aus_der_liste(umgebung):
    db, _ = umgebung
    _skill(db, "Konfigurationsmanagement", 5)
    db.set_search_criteria("keywords_minus", ["Konfigurationsmanagement", "Vertrieb"])
    db.set_search_criteria("keywords_plus", ["Remote", "SAP"])
    e = sa.abgleich(db)
    w = e["widersprueche"][0]["schluessel"]
    r = e["rahmenbegriffe"][0]["schluessel"]
    assert sa.uebernehmen(db, w)["entfernt_aus"] == "keywords_minus"
    antwort = sa.uebernehmen(db, r)
    assert antwort["entfernt_aus"] == "keywords_plus"
    # Wohin er gehoert, steht da — geschrieben wird es NICHT: das waere
    # eine zweite Entscheidung, die niemand bestaetigt hat.
    assert "Remote-Regler" in antwort["stattdessen"]
    krit = db.get_search_criteria()
    assert krit["keywords_minus"] == ["Vertrieb"]
    assert krit["keywords_plus"] == ["SAP"]
    danach = sa.abgleich(db)
    assert danach["widersprueche"] == [] and danach["rahmenbegriffe"] == []
    # Und jetzt zeigt sich, was der MINUS-Begriff verdeckt hat: der
    # Level-5-Skill steht in KEINER Fachliste. Kein Fehler des Abgleichs,
    # sondern der naechste Schritt — genau die Reihenfolge, in der der
    # Bestand vom 15.09. von Hand korrigiert wurde.
    assert [v["begriff"] for v in danach["fehlende_skills"]] == ["Konfigurationsmanagement"]


def test_verwerfen_merkt_sich_den_vorschlag_bis_sich_etwas_aendert(umgebung):
    """AK 4: verworfen bleibt verworfen — solange sich weder Profil noch
    Liste an DIESER Stelle aendern. Ein hoeheres Level ist ein neuer
    Sachverhalt, und der Vorschlag kommt wieder."""
    db, _ = umgebung
    sid = _skill(db, "Datenmigration", 3)
    e = sa.abgleich(db)
    s = e["fehlende_skills"][0]["schluessel"]
    assert sa.verwerfen(db, s)["status"] == "verworfen"
    e2 = sa.abgleich(db)
    assert e2["fehlende_skills"] == [] and e2["verworfen"] == 1
    # Ein unbekannter Schluessel wird benannt.
    assert "fehler" in sa.verwerfen(db, "fehlender_skill:gibtesnicht")

    db.update_skill(sid, {"level": 5})
    e3 = sa.abgleich(db)
    assert [v["begriff"] for v in e3["fehlende_skills"]] == ["Datenmigration"]
    assert e3["fehlende_skills"][0]["ziel"] == "keywords_muss"


# ══ Der Weg zum Menschen ════════════════════════════════════════════

def test_der_hinweis_im_dashboard_nennt_die_zahlen(umgebung):
    """AK 5: offene Vorschlaege stehen im Dashboard, gerechnet beim
    Lesen — also nach jeder Aenderung an Profil oder Listen aktuell."""
    db, mcp = umgebung
    from bewerbungs_assistent.services import onboarding_hints
    importlib.reload(onboarding_hints)

    ids = {h["id"] for h in onboarding_hints.list_active_hints(db)}
    assert "c87_suchbegriffe_gegen_profil" not in ids, "ohne Befund kein Hinweis"

    _skill(db, "Datenmigration", 5)
    hints = {h["id"]: h for h in onboarding_hints.list_active_hints(db)}
    h = hints["c87_suchbegriffe_gegen_profil"]
    assert h["tab"] == "dashboard"
    assert "Datenmigration" in h["detail"]
    # Der Knopf fuehrt zu einem Werkzeug, das es gibt (#1000).
    assert h["cta_tool"] == "profil_suchbegriffe_abgleichen"
    assert asyncio.run(mcp.get_tool("profil_suchbegriffe_abgleichen")) is not None

    # Uebernommen -> der Hinweis verschwindet von allein.
    s = sa.abgleich(db)["fehlende_skills"][0]["schluessel"]
    sa.uebernehmen(db, s)
    ids = {h["id"] for h in onboarding_hints.list_active_hints(db)}
    assert "c87_suchbegriffe_gegen_profil" not in ids


def test_das_werkzeug_liefert_drei_listen_und_wendet_nur_auf_ansage_an(umgebung):
    db, mcp = umgebung
    _bestand_vom_15_09(db)
    antwort = _call(mcp, "profil_suchbegriffe_abgleichen", {})
    assert len(antwort["fehlende_skills"]) == 20
    assert len(antwort["widersprueche"]) == 6
    assert len(antwort["rahmenbegriffe"]) == 9
    assert "35" in str(antwort["offen"]) or antwort["offen"] == 35
    assert "uebernehmen" in antwort["naechster_schritt"]

    s = antwort["rahmenbegriffe"][0]["schluessel"]
    ok = _call(mcp, "profil_suchbegriffe_abgleichen",
               {"aktion": "uebernehmen", "schluessel": s})
    assert ok["status"] == "uebernommen"
    v = _call(mcp, "profil_suchbegriffe_abgleichen",
              {"aktion": "verwerfen", "schluessel": antwort["widersprueche"][0]["schluessel"]})
    assert v["status"] == "verworfen"
    danach = _call(mcp, "profil_suchbegriffe_abgleichen", {})
    assert danach["offen"] == 33
    assert "fehler" in _call(mcp, "profil_suchbegriffe_abgleichen",
                             {"aktion": "loeschen"})


def test_das_werkzeug_reicht_die_levelgrenze_durch(umgebung):
    """Vorgabe 3; wer alles sehen will, senkt sie. Unsinn faellt auf die
    Vorgabe zurueck statt auf einen Fehler — und jeder Vorschlag, der bei
    Grenze 1 sichtbar wird, laesst sich auch uebernehmen."""
    db, mcp = umgebung
    _skill(db, "Datenmigration", 5)
    _skill(db, "AutoCAD", 1)
    vorgabe = _call(mcp, "profil_suchbegriffe_abgleichen", {})
    assert vorgabe["mindest_level"] == 3
    assert [v["begriff"] for v in vorgabe["fehlende_skills"]] == ["Datenmigration"]

    alle = _call(mcp, "profil_suchbegriffe_abgleichen", {"mindest_level": 1})
    assert {v["begriff"] for v in alle["fehlende_skills"]} == {"Datenmigration", "AutoCAD"}
    autocad = [v for v in alle["fehlende_skills"] if v["begriff"] == "AutoCAD"][0]
    ok = _call(mcp, "profil_suchbegriffe_abgleichen",
               {"aktion": "uebernehmen", "schluessel": autocad["schluessel"]})
    assert ok["status"] == "uebernommen" and ok["liste"] == "keywords_plus"

    unsinn = _call(mcp, "profil_suchbegriffe_abgleichen", {"mindest_level": 99})
    assert unsinn["mindest_level"] == 5


def test_ohne_befund_sagt_das_werkzeug_das_und_nennt_den_naechsten_schritt(umgebung):
    db, mcp = umgebung
    antwort = _call(mcp, "profil_suchbegriffe_abgleichen", {})
    assert antwort["offen"] == 0
    # `leer()` (#927) faltet den naechsten Schritt in den Hinweis.
    assert "kein offener Vorschlag" in antwort["hinweis"]
    assert "profil_suchbegriffe_abgleichen()" in antwort["hinweis"]


def test_suchkriterien_anzeigen_und_skill_hinzufuegen_zeigen_den_abgleich(umgebung):
    """Die beiden Wege, auf denen sich Profil und Listen aendern, sagen
    es gleich — statt auf den naechsten Blick ins Dashboard zu warten."""
    db, mcp = umgebung
    db.set_search_criteria("keywords_plus", ["Remote"])
    antwort = _call(mcp, "suchkriterien_anzeigen", {})
    assert antwort["abgleich_profil"]["offene_vorschlaege"] == 1
    assert "Remote" in antwort["abgleich_profil"]["zusammenfassung"]

    neu = _call(mcp, "skill_hinzufuegen",
                {"name": "Datenmigration", "category": "fachlich", "level": 5})
    assert neu["status"] == "gespeichert"
    assert "keywords_muss" in neu["suchbegriffe"]["hinweis"]
    assert "profil_suchbegriffe_abgleichen" in neu["suchbegriffe"]["werkzeug"]
