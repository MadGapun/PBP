"""#1308: Stellen nach der Sprache der Anzeige filtern und aussortieren.

Gemeldet aus 1.8.1: rein englische Anzeigen sollen raus, auch kuenftig. Die Sprache wird beim LESEN erkannt
(`services/sprache.py`), nicht gespeichert. Geprueft wird die Erkennung in beiden Richtungen (deutsche Anzeige mit englischen
Fachwoertern bleibt deutsch, englische mit deutschem Lehnwort bleibt englisch), der eigene Zustand "unbekannt", der Hinweis
"verlangt Deutsch", die Filter in `stellen_anzeigen` und `stellen_bulk_bewerten` und die Kosten auf einem grossen Bestand.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import shutil
import tempfile
import time

import pytest

from bewerbungs_assistent.services import sprache

DE = ("Für unseren Standort in Hamburg suchen wir einen PLM-Berater (m/w/d) mit Erfahrung in Teamcenter und Product "
      "Lifecycle Management. Deine Aufgaben: Du betreust unsere Kunden bei der Einführung von Teamcenter, analysierst "
      "Anforderungen und entwickelst Lösungen für das Engineering. Dein Profil: abgeschlossenes Studium, mehrere Jahre "
      "Erfahrung im Bereich PDM/PLM, sehr gute Deutsch- und gute Englischkenntnisse. Wir bieten ein Team, flexible "
      "Arbeitszeiten und Homeoffice.")
EN = ("We are looking for a Kindergarten teacher to join our international school in Berlin. You will plan and deliver "
      "lessons for children aged three to six, work closely with parents and colleagues, and contribute to the "
      "development of our early years curriculum. Requirements: a degree in early childhood education, at least two "
      "years of experience, and strong communication skills. We offer a competitive salary and support for relocation.")
FR = ("Nous recherchons un ingénieur pour notre site de Lyon. Vous serez responsable de la conception des pièces et de "
      "la coordination avec les équipes de production. Votre profil: diplôme d'ingénieur, expérience de cinq ans dans "
      "un poste similaire, maîtrise de l'anglais. Nous offrons une rémunération attractive et des avantages sociaux "
      "pour nos salariés.")
NL = ("Wij zoeken een ervaren monteur voor onze vestiging in Utrecht. Je bent verantwoordelijk voor het onderhoud van "
      "de machines en werkt samen met een klein team. Wij bieden een goed salaris, een vaste baan en ruimte voor "
      "ontwikkeling. Heb je ervaring met hydraulische systemen en ben je niet bang om de handen uit de mouwen te "
      "steken? Dan zijn wij op zoek naar jou.")


# ══ Erkennung ═══════════════════════════════════════════════════════════════════════════

def test_deutsche_anzeige_mit_englischen_fachwoertern_bleibt_deutsch():
    assert sprache.erkennen(DE) == "de"


def test_englische_anzeige_mit_deutschem_lehnwort_bleibt_englisch():
    assert "Kindergarten" in EN
    assert sprache.erkennen(EN) == "en"


@pytest.mark.parametrize("text", [FR, NL])
def test_andere_sprachen_sind_andere(text):
    assert sprache.erkennen(text) == "andere"


def test_zweisprachige_anzeige_ist_gemischt():
    assert sprache.erkennen(DE + "\n\n" + EN) == "gemischt"


@pytest.mark.parametrize("text", ["", None, "PLM Berater Hamburg", "Senior Engineer (m/w/d) – Teamcenter, Remote",
                                  "Kurztext: Wir suchen dich als Ingenieur in Hamburg."])
def test_fehlender_oder_kurzer_text_ist_unbekannt(text):
    assert sprache.erkennen(text) == "unbekannt"


def test_der_titel_allein_entscheidet_nie():
    # ein Titel, der fuer sich allein lang genug waere, um als englisch zu gelten (Gegenprobe 07.11.2026: mit einem
    # kurzen Titel blieb der Test gruen, auch als der Schutz ausgebaut war)
    langer_titel = EN
    assert sprache.erkennen(langer_titel) == "en"
    job = {"title": langer_titel, "description": ""}
    assert sprache.erkennen_stelle(job) == "unbekannt"
    assert sprache.erkennen_stelle({"title": langer_titel, "description": "   "}) == "unbekannt"
    assert sprache.erkennen_stelle({"title": "Ingenieur", "description": DE}) == "de"


def test_woerter_beider_sprachen_entscheiden_nichts():
    # nur Woerter, die in Deutsch UND Englisch vorkommen - viele, aber keines zaehlt
    text = " ".join(["die was also in an will mit so man war"] * 10)
    assert sprache.zaehlen(text)["de"] == sprache.zaehlen(text)["en"] == 0
    assert sprache.erkennen(text) == "unbekannt"
    for wort in ("die", "was", "also", "in", "an", "mit"):
        assert wort not in sprache.WOERTER_DE and wort not in sprache.WOERTER_EN


def test_die_listen_ueberschneiden_sich_nicht():
    assert not (sprache.WOERTER_DE & sprache.WOERTER_EN)
    assert not (sprache.WOERTER_ANDERE & (sprache.WOERTER_DE | sprache.WOERTER_EN))


def test_ein_einzelner_treffer_entscheidet_nicht():
    # eine englische Anzeige mit EINEM deutschen Wort bleibt englisch, eine deutsche mit einem englischen deutsch
    assert sprache.erkennen(EN + " Deutschkenntnisse und Erfahrung.") == "en"
    assert sprache.erkennen(DE + " Join the team!") == "de"


# ══ verlangt Deutsch (Hinweis, kein Filter) ═════════════════════════════════════════════

@pytest.mark.parametrize("text", [
    "Requirements: German (fluent) and English.",
    "German C1 level is a must.",
    "Very good German language skills required.",
    "You are fluent in English and German.",
    "Fluent German is required for this role.",
    "Sehr gute Deutschkenntnisse (C1) sind erforderlich.",
    "Business fluent German and English.",
])
def test_deutsch_verlangt_erkennt_die_anforderung(text):
    assert sprache.deutsch_verlangt(text), text


@pytest.mark.parametrize("text", [
    "We are a German company with offices worldwide. English is required.",
    "Our German headquarters is in Munich.",
    EN,
])
def test_deutsch_verlangt_nicht_bei_blosser_erwaehnung(text):
    assert not sprache.deutsch_verlangt(text), text


def test_merkmal_nennt_den_hinweis_nur_bei_englisch_oder_gemischt():
    en_mit = {"title": "Engineer", "description": EN + " German (fluent) is required."}
    assert sprache.merkmal(en_mit) == {"sprache": "en", "deutsch_verlangt": True}
    assert sprache.merkmal({"title": "x", "description": DE}) == {"sprache": "de"}


# ══ Werkzeuge ═══════════════════════════════════════════════════════════════════════════

@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v182_1308_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _srv_mod.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _stellen(db):
    db.save_jobs([
        {"hash": "s1308de", "title": "PLM-Berater", "company": "Musterfirma GmbH", "url": "https://example.com/de",
         "source": "manuell", "description": DE, "score": 5},
        {"hash": "s1308en", "title": "Kindergarten Teacher", "company": "Beispiel AG", "url": "https://example.com/en",
         "source": "manuell", "description": EN + " German (fluent) is required.", "score": 5},
        {"hash": "s1308kurz", "title": "Ingenieur", "company": "Muster KG", "url": "https://example.com/kurz",
         "source": "manuell", "description": "Kurztext.", "score": 5},
        {"hash": "s1308fr", "title": "Ingénieur", "company": "Exemple SA", "url": "https://example.com/fr",
         "source": "manuell", "description": FR, "score": 5},
    ])


def test_stellen_anzeigen_traegt_die_sprache_je_stelle(umgebung):
    db, mcp = umgebung
    _stellen(db)
    erg = _call(mcp, "stellen_anzeigen", {"ohne_schwelle": True})
    sprachen = {s["hash"]: s["sprache"] for s in erg["stellen"]}
    assert sprachen == {"s1308de": "de", "s1308en": "en", "s1308kurz": "unbekannt", "s1308fr": "andere"}
    en = next(s for s in erg["stellen"] if s["hash"] == "s1308en")
    assert en.get("deutsch_verlangt") is True


def test_stellen_anzeigen_filtert_nach_sprache(umgebung):
    db, mcp = umgebung
    _stellen(db)
    erg = _call(mcp, "stellen_anzeigen", {"ohne_schwelle": True, "sprache": ["de", "unbekannt"]})
    assert {s["hash"] for s in erg["stellen"]} == {"s1308de", "s1308kurz"}
    assert "Sprache" in erg["sprach_filter"]
    falsch = _call(mcp, "stellen_anzeigen", {"sprache": ["englisch"]})
    assert "fehler" in falsch and "en" in falsch["fehler"]


def test_bulk_trifft_englisch_aber_nie_unbekannt(umgebung):
    db, mcp = umgebung
    _stellen(db)
    erg = _call(mcp, "stellen_bulk_bewerten", {"bewertung": "passt_nicht", "gruende": ["sonstiges"],
                                               "sprache": ["en"], "dry_run": True})
    assert erg["anzahl_treffer"] == 1
    assert erg["vorschau"][0]["hash"].startswith("s1308en") and erg["vorschau"][0]["sprache"] == "en"
    assert erg["sprache_unbekannt_im_bestand"] == 1
    echt = _call(mcp, "stellen_bulk_bewerten", {"bewertung": "passt_nicht", "gruende": ["sonstiges"],
                                                "sprache": ["en"], "dry_run": False})
    assert echt["bearbeitet"] == 1
    aktiv = {j["hash"] for j in db.get_active_jobs()}
    assert aktiv == {"s1308de", "s1308kurz", "s1308fr"}


# ══ Kosten (erst messen, dann bewerten; Lehre 8f) ═══════════════════════════════════════

def test_messung_erkennung_auf_grossem_bestand(tmp_path):
    """3.000 Stellen mit je rund 2.000 Zeichen Anzeigentext: Erkennung und gefilterte Liste des Stellen-Tabs.

    Gemessen am 07.11.2026 auf dem Entwicklungsrechner: 0,09 s fuer 3.000 Erkennungen, die gefilterte Liste
    (`stellen_liste.aufbereiten` mit Sprachfilter und Zaehlung je Filter) 0,10 s statt 0,01 s. Die Grenze hier
    ist grosszuegig (CI-Rechner sind langsamer), faengt aber eine Erkennung je Durchgang statt je Stelle ab."""
    from bewerbungs_assistent.services import stellen_liste
    texte = [DE * 3, EN * 3, FR * 3, "Kurz."]
    jobs = [{"hash": f"h{i}", "title": f"Stelle {i}", "company": "Musterfirma GmbH", "source": "manuell",
             "score": i % 7, "description": texte[i % 4] + f" Nummer {i}."} for i in range(3000)]
    t0 = time.perf_counter()
    codes = [sprache.erkennen_stelle(j) for j in jobs]
    erkennung = time.perf_counter() - t0
    assert codes[:4] == ["de", "en", "andere", "unbekannt"]

    neutral = {"rahmen_ausblenden": False, "schwelle_ausblenden": False}
    t0 = time.perf_counter()
    stellen_liste.aufbereiten([dict(j) for j in jobs], neutral, limit=20)
    ohne = time.perf_counter() - t0
    t0 = time.perf_counter()
    erg = stellen_liste.aufbereiten([dict(j) for j in jobs], dict(neutral, sprache="de,gemischt", min_score="1"),
                                    limit=20)
    mit = time.perf_counter() - t0
    assert erg["treffer"] == sum(1 for i in range(3000) if i % 4 == 0 and i % 7 >= 1)
    assert erg["verborgen"]["sprache"] > 0
    assert all("sprache" in j for j in erg["jobs"])
    print(f"\n#1308 Messung: Erkennung 3000 Stellen {erkennung:.2f} s; Liste ohne Filter {ohne:.2f} s, "
          f"mit Sprach- und Punktefilter {mit:.2f} s")
    assert erkennung < 3.0, erkennung
    assert mit - ohne < 3.0, (ohne, mit)
