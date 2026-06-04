"""Tests fuer beta.97 — Recherche-Routing (#672) + informal_notes-CRUD (#680).

- #672: recherche_speichern schreibt Bewerbung-Recherche ins ANZEIGBARE
  jobs.research_notes der verknuepften Stelle — NICHT in
  applications.fit_analyse (Kollision + unsichtbar).
- #680: profil_bearbeiten(notizen, ...) kann jetzt lesen / ersetzen /
  loeschen, nicht nur anhaengen.
"""
from __future__ import annotations

import logging


class FakeMCP:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn
        return decorator


def _register_analyse(tmp_db):
    from bewerbungs_assistent.tools.analyse import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def _register_profil(tmp_db):
    from bewerbungs_assistent.tools.profil import register
    mcp = FakeMCP()
    register(mcp, tmp_db, logging.getLogger("test"))
    return mcp


def _make_job(tmp_db, hash_="job-rech"):
    tmp_db.save_jobs([{
        "hash": hash_, "title": "PLM Consultant", "company": "Firma X",
        "source": "stepstone", "score": 7,
    }])
    return hash_


# ── #672 — recherche_speichern Routing ──────────────────────────────────


def test_recherche_job_hash_landet_in_research_notes(tmp_db):
    tmp_db.create_profile("Test User", "test@example.com")
    h = _make_job(tmp_db)
    mcp = _register_analyse(tmp_db)
    res = mcp.tools["recherche_speichern"](
        text="Firma waechst stark, gute Reviews.",
        job_hash=h, kategorie="firmenrecherche",
    )
    assert res.get("status") == "gespeichert", res
    # #674: landet in der research_notes-Tabelle (NICHT im Notizblock jobs.research_notes)
    rows = tmp_db.get_research_notes(job_hash=h)
    assert any("Firma waechst stark" in r["text"] for r in rows), rows
    assert any(r["kategorie"] == "firmenrecherche" for r in rows)
    # der manuelle Notizblock bleibt unberuehrt
    assert not (tmp_db.get_job(h).get("research_notes") or "")


def test_recherche_bewerbung_landet_in_tabelle_nicht_fit_analyse(tmp_db):
    """#672/#674 Kern: Bewerbung-Recherche -> research_notes-Tabelle, NICHT fit_analyse."""
    tmp_db.create_profile("Test User", "test@example.com")
    h = _make_job(tmp_db)
    app_id = tmp_db.add_application({
        "title": "PLM Consultant", "company": "Firma X", "job_hash": h,
    })
    mcp = _register_analyse(tmp_db)
    res = mcp.tools["recherche_speichern"](
        text="Gehaltsband laut Kununu 65-75k.",
        bewerbung_id=app_id, kategorie="gehalt",
    )
    assert res.get("status") == "gespeichert", res
    # strukturiert in der Tabelle, abrufbar ueber Bewerbung UND verknuepfte Stelle
    by_app = tmp_db.get_research_notes(bewerbung_id=app_id)
    assert any("Gehaltsband laut Kununu" in r["text"] for r in by_app), by_app
    assert any("Gehaltsband" in r["text"] for r in tmp_db.get_research_notes(job_hash=h))
    # und NICHT in applications.fit_analyse
    app = tmp_db.get_application(app_id)
    fit = app.get("fit_analyse") or ""
    assert "Gehaltsband" not in str(fit), f"fit_analyse verschmutzt: {fit!r}"


def test_recherche_bewerbung_ohne_stelle_wird_trotzdem_gespeichert(tmp_db):
    """#674: ohne verknuepfte Stelle wird die Recherche an die Bewerbung gebunden."""
    tmp_db.create_profile("Test User", "test@example.com")
    app_id = tmp_db.add_application({"title": "Freie Anfrage", "company": "Firma Y"})
    mcp = _register_analyse(tmp_db)
    res = mcp.tools["recherche_speichern"](
        text="Inbound-Anfrage, Konditionen offen", bewerbung_id=app_id,
        kategorie="allgemein",
    )
    assert res.get("status") == "gespeichert", res
    rows = tmp_db.get_research_notes(bewerbung_id=app_id)
    assert len(rows) == 1 and rows[0]["job_hash"] is None


def test_recherche_ohne_ziel_meldet_fehler(tmp_db):
    tmp_db.create_profile("Test User", "test@example.com")
    mcp = _register_analyse(tmp_db)
    res = mcp.tools["recherche_speichern"](text="x")
    assert "fehler" in res


def test_recherche_doppelziel_ein_eintrag_beide_bindungen(tmp_db):
    """job_hash + bewerbung_id: EIN Eintrag, an Bewerbung UND Stelle gebunden."""
    tmp_db.create_profile("Test User", "test@example.com")
    h = _make_job(tmp_db)
    app_id = tmp_db.add_application({
        "title": "PLM Consultant", "company": "Firma X", "job_hash": h,
    })
    mcp = _register_analyse(tmp_db)
    res = mcp.tools["recherche_speichern"](
        text="EINMALIGER_MARKER_TEXT",
        job_hash=h, bewerbung_id=app_id, kategorie="markt",
    )
    assert res.get("status") == "gespeichert", res
    by_app = tmp_db.get_research_notes(bewerbung_id=app_id)
    assert len([r for r in by_app if "EINMALIGER_MARKER_TEXT" in r["text"]]) == 1, by_app
    row = by_app[0]
    assert row["bewerbung_id"] == app_id and row["job_hash"]


# ── #680 — informal_notes lesen / ersetzen / loeschen ───────────────────


def _profil_notiz(tmp_db):
    tmp_db.create_profile("Test User", "test@example.com")
    return _register_profil(tmp_db).tools["profil_bearbeiten"]


def test_notizen_anhang_und_lesen(tmp_db):
    fn = _profil_notiz(tmp_db)
    fn(bereich="notizen", aktion="anhang",
       daten={"sektion": "ALLGEMEIN", "text": "mag Homeoffice"})
    fn(bereich="notizen", aktion="anhang",
       daten={"sektion": "ZIELE", "text": "Teamlead werden"})
    res = fn(bereich="notizen", aktion="lesen")
    assert res.get("status") == "ok", res
    assert res["anzahl_sektionen"] == 2
    assert "ALLGEMEIN" in res["sektionen"]
    assert "ZIELE" in res["sektionen"]
    assert any("mag Homeoffice" in z for z in res["sektionen"]["ALLGEMEIN"])


def test_notizen_ersetzen_sektion(tmp_db):
    fn = _profil_notiz(tmp_db)
    fn(bereich="notizen", aktion="anhang",
       daten={"sektion": "ALLGEMEIN", "text": "mag Homeoffice"})
    fn(bereich="notizen", aktion="anhang",
       daten={"sektion": "ZIELE", "text": "Teamlead werden"})
    res = fn(bereich="notizen", aktion="ersetzen",
             daten={"sektion": "ALLGEMEIN", "text": "mag Remote"})
    assert res.get("status") == "ersetzt", res
    gelesen = fn(bereich="notizen", aktion="lesen")
    allg = " ".join(gelesen["sektionen"]["ALLGEMEIN"])
    assert "mag Remote" in allg
    assert "mag Homeoffice" not in allg
    # andere Sektion unangetastet
    assert "ZIELE" in gelesen["sektionen"]


def test_notizen_ersetzen_legt_neue_sektion_an(tmp_db):
    fn = _profil_notiz(tmp_db)
    res = fn(bereich="notizen", aktion="ersetzen",
             daten={"sektion": "NEU", "text": "frischer Inhalt"})
    assert res.get("status") == "ersetzt", res
    gelesen = fn(bereich="notizen", aktion="lesen")
    assert "NEU" in gelesen["sektionen"]


def test_notizen_loeschen_sektion(tmp_db):
    fn = _profil_notiz(tmp_db)
    fn(bereich="notizen", aktion="anhang",
       daten={"sektion": "ALLGEMEIN", "text": "behalten"})
    fn(bereich="notizen", aktion="anhang",
       daten={"sektion": "ZIELE", "text": "weg damit"})
    res = fn(bereich="notizen", aktion="loeschen", daten={"sektion": "ZIELE"})
    assert res.get("status") == "geloescht", res
    gelesen = fn(bereich="notizen", aktion="lesen")
    assert "ZIELE" not in gelesen["sektionen"]
    assert "ALLGEMEIN" in gelesen["sektionen"]
    assert gelesen["anzahl_sektionen"] == 1


def test_notizen_loeschen_unbekannt_meldet_nicht_gefunden(tmp_db):
    fn = _profil_notiz(tmp_db)
    fn(bereich="notizen", aktion="anhang",
       daten={"sektion": "ALLGEMEIN", "text": "x"})
    res = fn(bereich="notizen", aktion="loeschen", daten={"sektion": "GIBTESNICHT"})
    assert res.get("status") == "nicht_gefunden", res


def test_notizen_ersetzen_ohne_sektion_meldet_fehler(tmp_db):
    fn = _profil_notiz(tmp_db)
    res = fn(bereich="notizen", aktion="ersetzen", daten={"text": "ohne sektion"})
    assert "fehler" in res
