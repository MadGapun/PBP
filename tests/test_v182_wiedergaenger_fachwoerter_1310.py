"""#1310 - die Wiedergaenger-Automatik lernt Ortsnamen und Eigenschaftswoerter als "Fachgebiet".

Gemeldet aus 1.8.1: Stufe 1b (`find_titel_muster`) sortierte Stellen als
`falsches_fachgebiet` aus, deren einziges gemeinsames "Fachwort" ein Ortsname,
ein Eigenschaftswort ("kaufmaennischer") oder ein Fragment ("voll" aus "Voll-
oder Teilzeit") war - und alle drei gemessenen Titel trugen Pflichtbegriffe
(MUSS) des eigenen Profils.

Drei Teile, je ein Block:

1. Veto: oeffnet das MUSS-Tor der aktuellen Kriterien, wird
   `falsches_fachgebiet` nicht uebertragen (Stufe 1 und 1b). Gefragt wird
   `muss_tor.tor_offen` - dieselbe Funktion wie im Score.
2. Ortsnamen: ein Wort aus dem Ortsfeld der Stelle (bzw. des Belegs) ist kein
   Fachwort.
3. Stoppwoerter: "voll", "teamassistenz", "kaufmann", die Eigenschaftswoerter.

Beide Richtungen: ein echter Wiedergaenger ("Lohnbuchhaltung", Profil ohne
passenden Pflichtbegriff) wird weiter aussortiert. Testdaten fiktiv, jede
Datenbank isoliert (BA_DATA_DIR).
"""
from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.services import muss_tor  # noqa: E402
from bewerbungs_assistent.services import stellen_automatik as sa  # noqa: E402
from bewerbungs_assistent.services import wiedergaenger as wg  # noqa: E402

TEXT = ("Ihre Aufgaben: Bearbeitung der Vorgaenge, Abstimmung mit den "
        "Fachbereichen, Pflege der Unterlagen. Ihr Profil: abgeschlossene "
        "Ausbildung, sicherer Umgang mit den gaengigen Programmen. ") * 2


@pytest.fixture
def db(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent import database

    importlib.reload(database)
    datenbank = database.Database()
    datenbank.initialize()
    assert str(tmp_path) in str(datenbank.db_path), (
        f"DB nicht isoliert: {datenbank.db_path}")
    datenbank.save_profile({"name": "Test 1310"})
    try:
        yield datenbank
    finally:
        datenbank.close()
        os.environ.pop("BA_DATA_DIR", None)


def _stelle(db, kennung, titel, firma, grund=None, ort="Musterstadt"):
    db.save_jobs([{
        "hash": kennung, "title": titel, "company": firma, "location": ort,
        "url": f"https://example.com/1310/{kennung}",
        "source": "manuell", "_manual_entry": True,
        "description": TEXT, "score": 5,
    }])
    voll = db.resolve_job_hash(kennung)
    if grund:
        assert db.dismiss_job(voll, grund)
    return voll


def _belege(db, titel, grund="falsches_fachgebiet", n=3, ort="Musterstadt",
            praefix="b"):
    for i in range(n):
        _stelle(db, f"{praefix}{i}", titel, f"Musterfirma {praefix}{i} GmbH",
                grund, ort=ort)


def _neu(titel, firma="Neufirma GmbH", ort="Musterstadt", kennung="neu"):
    return {"hash": kennung, "title": titel, "company": firma,
            "location": ort, "description": TEXT}


def _muss(db, *begriffe):
    db.set_search_criteria("keywords_muss", list(begriffe))


# ───────────────────────────── 3. Stoppwoerter ──


def test_1310_kaufmaennisch_allein_ist_kein_fachwort():
    assert wg._domain_tokens(
        "Kaufmännischer Mitarbeiter (m/w/d) in Voll- oder Teilzeit") == set()
    assert wg._domain_tokens("Kaufmännische Sachbearbeiterin") == set()
    # auch in Umschrift
    assert wg._domain_tokens("Kaufmaennisches Personal") == {"personal"}


@pytest.mark.parametrize("wort", [
    "voll", "teamassistenz", "kaufmann", "kauffrau", "kaufleute",
    "kaufmännisch", "kaufmännische", "kaufmännischer", "kaufmännisches",
    "kaufmännischen", "technisch", "technische", "technischer",
    "technisches", "technischen", "gewerblich", "gewerbliche",
    "gewerblicher", "gewerbliches", "gewerblichen",
    # Messung auf einer Bestandskopie: Arbeitsmodell und Rolle trugen sonst das "Fachgebiet"
    "remote", "hybrid", "homeoffice", "onsite", "Projektleiter", "Projektleiterin",
    "Projektmanager", "Projektmanagerin",
])
def test_1310_neue_stoppwoerter(wort):
    assert wg._domain_tokens(f"{wort} Lohnbuchhaltung") == {"lohnbuchhaltung"}


@pytest.mark.parametrize("fach", [
    "buchhaltung", "sekretariat", "lohnbuchhaltung", "einkauf",
])
def test_1310_echte_faecher_bleiben_fachwoerter(fach):
    assert wg._domain_tokens(f"Kaufmännischer Mitarbeiter {fach}") == {fach}


# ───────────────────────────── 2. Ortsnamen ──


def test_1310_ortsname_aus_dem_ortsfeld_ist_kein_fachwort():
    titel = "Sachbearbeiter Musterstadt (m/w/d)"
    assert wg._domain_tokens(titel) == {"musterstadt"}
    assert wg._domain_tokens(titel, orte=("Musterstadt, Bayern",)) == set()
    # Umlaut und Umschrift fallen zusammen, in beide Richtungen
    assert wg._domain_tokens("Lohnbuchhaltung Mühlstadt",
                             orte=("Muehlstadt",)) == {"lohnbuchhaltung"}
    assert wg._domain_tokens("Lohnbuchhaltung Muehlstadt",
                             orte=("Mühlstadt",)) == {"lohnbuchhaltung"}
    # ohne Ortsangabe bleibt alles wie bisher
    assert wg._domain_tokens(titel, orte=(None,)) == {"musterstadt"}


def test_1310_ortsname_allein_stiftet_keinen_treffer(db):
    _belege(db, "Sachbearbeiter Musterstadt (m/w/d)")
    dismissed = db.get_dismissed_jobs()
    assert sa.find_titel_muster(db, "Sachbearbeiter Musterstadt", dismissed,
                                ort="Musterstadt") is None
    # auch wenn die NEUE Stelle ein anderes Ortsfeld hat: der Ort jedes
    # Belegs zaehlt fuer den Beleg
    assert sa.find_titel_muster(db, "Sachbearbeiter Musterstadt", dismissed,
                                ort="Andersdorf") is None
    e = sa.entscheide(db, _neu("Sachbearbeiter Musterstadt (m/w/d)"),
                      dismissed=dismissed, kriterien={})
    assert e["aktion"] == "anlegen", e


def test_1310_fachwort_plus_ort_traegt_weiter(db):
    _belege(db, "Lohnbuchhaltung Musterstadt (m/w/d)")
    dismissed = db.get_dismissed_jobs()
    m = sa.find_titel_muster(db, "Lohnbuchhaltung Musterstadt (m/w/d)",
                             dismissed, ort="Musterstadt")
    assert m is not None
    assert m["tokens"] == ["lohnbuchhaltung"], m
    e = sa.entscheide(db, _neu("Lohnbuchhaltung Musterstadt (m/w/d)"),
                      dismissed=dismissed, kriterien={})
    assert e["aktion"] == "aussortieren" and e["grund"] == "falsches_fachgebiet"
    assert "musterstadt" not in e["beleg"].lower()


def test_1310_ort_der_neuen_stelle_zaehlt_auch_wenn_die_belege_anderswo_stehen(db):
    """Belege mit "Musterstadt" im Titel, aber einem anderen Ortsfeld: dann
    nimmt erst der Ort der NEUEN Stelle das Wort heraus."""
    _belege(db, "Sachbearbeiter Musterstadt (m/w/d)", ort="Andersdorf")
    dismissed = db.get_dismissed_jobs()
    assert sa.find_titel_muster(db, "Sachbearbeiter Musterstadt", dismissed,
                                ort="Musterstadt") is None
    assert sa.find_titel_muster(db, "Sachbearbeiter Musterstadt",
                                dismissed) is not None  # ohne Ort wie bisher
    e = sa.entscheide(db, _neu("Sachbearbeiter Musterstadt (m/w/d)"),
                      dismissed=dismissed, kriterien={})
    assert e["aktion"] == "anlegen", e


def test_1310_stufe1_ortsname_derselben_firma_ist_kein_fachwort(db):
    for i in range(2):
        _stelle(db, f"f{i}", "Sachbearbeiter Musterstadt", "Musterfirma GmbH",
                "falsches_fachgebiet")
    for ort in ("Musterstadt", None):
        m = wg.find_wiedergaenger_pattern(db, "Musterfirma GmbH",
                                          "Lohnbuchhaltung Musterstadt",
                                          ort=ort)
        assert m is None, (ort, m)


def test_1310_stufe1_ort_der_neuen_stelle(db):
    for i in range(2):
        _stelle(db, f"f{i}", "Sachbearbeiter Musterstadt", "Musterfirma GmbH",
                "falsches_fachgebiet", ort="Andersdorf")
    assert wg.find_wiedergaenger_pattern(
        db, "Musterfirma GmbH", "Lohnbuchhaltung Musterstadt") is not None
    assert wg.find_wiedergaenger_pattern(
        db, "Musterfirma GmbH", "Lohnbuchhaltung Musterstadt",
        ort="Musterstadt") is None
    e = sa.entscheide(db, _neu("Lohnbuchhaltung Musterstadt", "Musterfirma GmbH"),
                      kriterien={})
    assert e["aktion"] == "anlegen", e


def _mcp(db):
    import logging

    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all

    mcp = FastMCP("t1310")
    register_all(mcp, db, logging.getLogger("t1310"))
    return mcp


def _call(mcp, name, args):
    import asyncio

    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return getattr(res, "structured_content", res)
    return asyncio.run(_run())


def test_1310_werkzeug_wiedergaenger_pruefen_kennt_den_ort(db):
    for i in range(2):
        _stelle(db, f"f{i}", "Sachbearbeiter Musterstadt", "Musterfirma GmbH",
                "falsches_fachgebiet", ort="Andersdorf")
    neu = _stelle(db, "neu", "Lohnbuchhaltung Musterstadt", "Musterfirma GmbH")
    erg = _call(_mcp(db), "stelle_wiedergaenger_pruefen", {"job_hash": neu})
    assert erg.get("status") == "kein_wiedergaenger", erg


def test_1310_reparatur_findet_ortsname_als_einziges_gemeinsames_wort(db):
    """`automatik_uebertragungen_pruefen`: ein Muster, das nur am eigenen
    Ortsnamen der Stelle hing, gilt als `nur_fuellwoerter` und kommt zurueck."""
    voll = _stelle(db, "r1", "Sachbearbeiter Musterstadt", "Musterfirma GmbH",
                   "falsches_fachgebiet")
    echt = _stelle(db, "r2", "Lohnbuchhaltung Musterstadt", "Musterfirma GmbH",
                   "falsches_fachgebiet")
    con = db.connect()
    for h, wort in ((voll, "musterstadt"), (echt, "lohnbuchhaltung")):
        con.execute("UPDATE jobs SET dismiss_note=? WHERE hash=?", (
            "Wiedergänger nach Fachgebiet: 3x mit Grund 'falsches_fachgebiet' "
            f"aussortiert (gemeinsam: {wort}).", h))
    con.commit()
    vorschau = _call(_mcp(db), "automatik_uebertragungen_pruefen", {})
    befunde = {e["titel"]: e["befund"] for e in vorschau["stichprobe"]}
    assert befunde.get("Sachbearbeiter Musterstadt") == "nur_fuellwoerter", vorschau
    assert "Lohnbuchhaltung Musterstadt" not in befunde


def test_1310_stufe2_schluessel_ohne_ortsname(db):
    """Vorher war {musterstadt} der Schluessel - jede weitere Anzeige
    derselben Firma am selben Ort wurde still ignoriert."""
    _stelle(db, "s0", "Sachbearbeiter Musterstadt", "Musterfirma GmbH",
            "falsches_fachgebiet")
    assert sa._domain_schluessel("Musterfirma GmbH", "Sachbearbeiter Musterstadt",
                                 "Musterstadt") is None
    e = sa.entscheide(db, _neu("Sachbearbeiter Musterstadt", "Musterfirma GmbH"),
                      kriterien={})
    assert e["aktion"] != "ignorieren", e


# ───────────────────────────── die drei gemeldeten Faelle ──


def test_1310_gemeldet_kaufmaennischer_sachbearbeiter(db):
    _belege(db, "Kaufmännischer Sachbearbeiter Viehabrechnung (m/w/d)")
    _muss(db, "Kaufmännischer Sachbearbeiter")
    e = sa.entscheide(db, _neu("Kaufmännischer Sachbearbeiter (m/w/d)"))
    assert e["aktion"] == "anlegen", e


def test_1310_gemeldet_teamassistenz(db):
    _belege(db, "Teamassistenz Vertrieb (m/w/d)")
    _muss(db, "Teamassistenz")
    e = sa.entscheide(db, _neu("Teamassistenz (m/w/d)"))
    assert e["aktion"] == "anlegen", e
    # auch ohne Pflichtbegriff: "teamassistenz" ist kein Fachwort mehr
    assert sa.find_titel_muster(db, "Teamassistenz (m/w/d)",
                                db.get_dismissed_jobs()) is None


def test_1310_gemeldet_auftragsabwicklung_veto_mit_hinweis(db):
    _belege(db, "Mitarbeiter Auftragsabwicklung Seefracht (m/w/d)", n=4)
    _muss(db, "Auftragsabwicklung")
    e = sa.entscheide(db, _neu(
        "Mitarbeiter Auftragsabwicklung & Einsatzplanung (m/w/d)"))
    assert e["aktion"] == "anlegen", e
    assert "Auftragsabwicklung" in e["hinweis"]
    assert "Pflichtbegriff" in e["hinweis"]
    assert "auftragsabwicklung" in e["hinweis"]  # das gemeinsame Wort des Musters


# ───────────────────────────── 1. Veto, beide Richtungen ──


def test_1310_ohne_pflichtbegriff_im_profil_kein_veto(db):
    _belege(db, "Mitarbeiter Auftragsabwicklung Seefracht (m/w/d)", n=4)
    e = sa.entscheide(db, _neu(
        "Mitarbeiter Auftragsabwicklung & Einsatzplanung (m/w/d)"))
    assert e["aktion"] == "aussortieren" and e["grund"] == "falsches_fachgebiet"


def test_1310_echter_wiedergaenger_bleibt_aussortiert(db):
    _belege(db, "Lohnbuchhaltung (m/w/d)")
    _muss(db, "Auftragsabwicklung")  # passt nicht auf die neue Stelle
    e = sa.entscheide(db, _neu("Sachbearbeiter Lohnbuchhaltung (m/w/d)"))
    assert e["aktion"] == "aussortieren", e
    assert e["grund"] == "falsches_fachgebiet"


def test_1310_veto_nur_fuer_fachgebiet_nicht_fuer_branche(db):
    _belege(db, "Mitarbeiter Auftragsabwicklung Seefracht (m/w/d)",
            grund="falsche_branche", n=4)
    _muss(db, "Auftragsabwicklung")
    e = sa.entscheide(db, _neu("Auftragsabwicklung Seefracht (m/w/d)"))
    assert e["aktion"] == "aussortieren", e
    assert e["grund"] == "falsche_branche"
    assert sa.TOR_GRUENDE == frozenset({"falsches_fachgebiet"})


def test_1310_veto_auch_in_stufe1_dieselbe_firma(db):
    for i in range(2):
        _stelle(db, f"f{i}", "Auftragsabwicklung Seefracht", "Musterfirma GmbH",
                "falsches_fachgebiet")
    neu = _neu("Auftragsabwicklung Einsatzplanung", "Musterfirma GmbH")
    ohne = sa.entscheide(db, neu)
    assert ohne["aktion"] == "aussortieren", ohne
    assert "dieselbe Firma" in ohne["beleg"]
    _muss(db, "Auftragsabwicklung")
    mit = sa.entscheide(db, neu)
    assert mit["aktion"] == "anlegen", mit
    assert "Pflichtbegriff" in mit.get("hinweis", "")


def test_1310_veto_liest_auch_die_beschreibung(db):
    """Text wie im Score: Titel UND Beschreibung."""
    _belege(db, "Lohnbuchhaltung (m/w/d)")
    _muss(db, "Entgeltabrechnung")
    neu = _neu("Lohnbuchhaltung (m/w/d)")
    assert sa.entscheide(db, dict(neu))["aktion"] == "aussortieren"
    neu["description"] = TEXT + " Schwerpunkt ist die Entgeltabrechnung."
    e = sa.entscheide(db, neu)
    assert e["aktion"] == "anlegen" and "Entgeltabrechnung" in e["hinweis"], e


def test_1310_veto_kennt_die_alternativbezeichnungen():
    """Dieselbe Tor-Pruefung wie der Score - samt amtlicher Synonyme (#969)."""
    krit = {"keywords_muss": ["Pflegefachkraft"],
            "_muss_synonyme": {"Pflegefachkraft": ["Krankenpfleger"]}}
    job = _neu("Krankenpfleger Intensivstation")
    assert muss_tor.tor_offen(job, krit) == ["Pflegefachkraft"]
    assert sa._tor_widerspricht(None, job, "falsches_fachgebiet",
                                {"tokens": ["intensivstation"]}, krit)
    assert sa._tor_widerspricht(None, job, "falsche_branche", None, krit) == ""
    assert muss_tor.tor_offen(job, {}) == []


def test_1310_automatik_fragt_die_funktion_des_scores(db, monkeypatch):
    """Eine Frage, eine Funktion: `muss_tor.pflicht_treffer` entscheidet fuer
    Score UND Automatik."""
    _belege(db, "Lohnbuchhaltung (m/w/d)")
    monkeypatch.setattr(muss_tor, "pflicht_treffer",
                        lambda criteria, text: ["Platzhalter"])
    e = sa.entscheide(db, _neu("Lohnbuchhaltung (m/w/d)"))
    assert e["aktion"] == "anlegen" and "Platzhalter" in e["hinweis"]

    from bewerbungs_assistent.job_scraper import calculate_score
    monkeypatch.setattr(muss_tor, "pflicht_treffer", lambda criteria, text: [])
    job = {"title": "Lohnbuchhaltung", "description": TEXT}
    assert calculate_score(job, {"keywords_muss": ["Lohnbuchhaltung"]}) == 0


def test_1310_anwenden_laedt_die_kriterien_einmal_je_lauf(db, monkeypatch):
    _belege(db, "Mitarbeiter Auftragsabwicklung Seefracht (m/w/d)", n=4)
    _muss(db, "Auftragsabwicklung")
    from bewerbungs_assistent.services import scoring_kriterien
    echt = scoring_kriterien.fuer_scoring
    aufrufe = []

    def zaehlen(d, *a, **k):
        aufrufe.append(1)
        return echt(d, *a, **k)

    monkeypatch.setattr(scoring_kriterien, "fuer_scoring", zaehlen)
    jobs = [_neu(f"Auftragsabwicklung Einsatzplanung {i}", f"Firma {i} GmbH",
                 kennung=f"n{i}") for i in range(5)]
    erg = sa.anwenden(db, jobs)
    assert len(aufrufe) == 1
    assert erg["zaehler"]["automatisch_aussortiert"] == 0
    assert all(j.get("is_active", 1) != 0 for j in erg["jobs"])
