"""Tests fuer v1.7.3 — #741: projekte_anzeigen (STAR-Volltext, H16).

Befund: profil_zusammenfassung kuerzt description/result auf 100 Zeichen und
laesst situation/task/action ganz weg. Kein Tool lieferte den Volltext —
schwaechere Modelle generierten dadurch unkonkretere Anschreiben, obwohl die
vollen STAR-Beschreibungen in der DB liegen. projekte_anzeigen schliesst die
Luecke und liefert nebenbei die Projekt-IDs fuer profil_bearbeiten.
"""
import asyncio
import logging

import pytest


LANGER_TEXT = (
    "Realistische Erwartungshaltung im Steering etabliert und die "
    "CAD-Datenbereinigung mit einem KI-gestuetzten Klassifikationskonzept "
    "auf 94 Prozent Trefferquote gebracht; Einsparung von rund 1200 "
    "Personenstunden pro Jahr, Rollout auf drei Standorte."
)


@pytest.fixture
def tmp_db(tmp_path):
    from bewerbungs_assistent.database import Database
    db = Database(tmp_path / "test.db")
    db.initialize()
    db.save_profile({"name": "Test"})
    assert str(tmp_path) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    yield db
    db.close()


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _make_mcp(db):
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import profil
    mcp = FastMCP("test")
    profil.register(mcp, db, logging.getLogger("test"))
    return mcp


def _add_position_mit_projekt(db, **proj_overrides):
    pos_id = db.add_position({
        "company": "Musterfirma GmbH", "title": "Lead Engineer",
        "start_date": "2020-01", "end_date": "2024-06",
    })
    proj = {
        "name": "KI-Implementierungskonzept CAD-Datenbereinigung",
        "description": "Konzept und Rollout einer KI-gestuetzten Datenbereinigung." * 4,
        "role": "Projektleiter",
        "situation": "Gewachsener CAD-Bestand mit inkonsistenten Metadaten." * 4,
        "task": "Bereinigungskonzept entwickeln und Stakeholder abholen." * 4,
        "action": "Klassifikator evaluiert, Pilot aufgesetzt, Steering etabliert." * 4,
        "result": LANGER_TEXT,
        "technologies": "Python, Teamcenter, NX",
        "start_date": "2022-01", "end_date": "2023-06",
    }
    proj.update(proj_overrides)
    proj_id = db.add_project(pos_id, proj)
    return pos_id, proj_id


class TestProjekteAnzeigen:
    def test_star_felder_ungekuerzt(self, tmp_db):
        _, proj_id = _add_position_mit_projekt(tmp_db)
        mcp = _make_mcp(tmp_db)
        result = _call(mcp, "projekte_anzeigen", {})
        assert result["status"] == "ok"
        assert result["anzahl"] == 1
        p = result["projekte"][0]
        # Volltext, nicht auf 100 Zeichen gekuerzt
        assert p["ergebnis"] == LANGER_TEXT
        assert len(p["ergebnis"]) > 100
        for feld in ("situation", "task", "action", "beschreibung"):
            assert len(p[feld]) > 100, f"{feld} gekuerzt: {p[feld]!r}"
        # IDs fuer profil_bearbeiten(bereich='projekt')
        assert p["projekt_id"] == proj_id
        assert p["position"] == "Lead Engineer bei Musterfirma GmbH"

    def test_position_id_filter(self, tmp_db):
        pos_id, _ = _add_position_mit_projekt(tmp_db)
        pos2 = tmp_db.add_position({"company": "Andere AG", "title": "Berater"})
        tmp_db.add_project(pos2, {"name": "Zweites Projekt"})
        mcp = _make_mcp(tmp_db)
        alle = _call(mcp, "projekte_anzeigen", {})
        assert alle["anzahl"] == 2
        # Kurz-ID/Praefix reicht
        gefiltert = _call(mcp, "projekte_anzeigen", {"position_id": pos_id[:8]})
        assert gefiltert["anzahl"] == 1
        assert gefiltert["projekte"][0]["position_id"] == pos_id

    def test_position_id_unbekannt(self, tmp_db):
        _add_position_mit_projekt(tmp_db)
        mcp = _make_mcp(tmp_db)
        result = _call(mcp, "projekte_anzeigen", {"position_id": "gibtsnicht"})
        assert result["status"] == "nicht_gefunden"

    def test_vertraulicher_kunde_maskiert(self, tmp_db):
        """#246-Semantik wie in den Exporten: Kundenname nie leaken."""
        _add_position_mit_projekt(
            tmp_db, customer_name="Geheimkunde AG", is_confidential=1)
        mcp = _make_mcp(tmp_db)
        result = _call(mcp, "projekte_anzeigen", {})
        p = result["projekte"][0]
        assert p["kunde"] == "[vertraulich]"
        assert "Geheimkunde" not in str(result)

    def test_kunde_ohne_vertraulichkeit_sichtbar(self, tmp_db):
        _add_position_mit_projekt(
            tmp_db, customer_name="Offener Kunde GmbH", is_confidential=0)
        mcp = _make_mcp(tmp_db)
        result = _call(mcp, "projekte_anzeigen", {})
        assert result["projekte"][0]["kunde"] == "Offener Kunde GmbH"

    def test_keine_projekte(self, tmp_db):
        tmp_db.add_position({"company": "Leer AG", "title": "X"})
        mcp = _make_mcp(tmp_db)
        result = _call(mcp, "projekte_anzeigen", {})
        assert result["status"] == "leer"
        assert result["projekte"] == []

    def test_kein_profil(self, tmp_path):
        from bewerbungs_assistent.database import Database
        db = Database(tmp_path / "leer.db")
        db.initialize()
        try:
            mcp = _make_mcp(db)
            result = _call(mcp, "projekte_anzeigen", {})
            assert result["status"] == "kein_profil"
        finally:
            db.close()


class TestZusammenfassungHinweis:
    def test_zusammenfassung_verweist_auf_volltext(self, tmp_db):
        """H16.2: Kurzuebersicht bleibt, aber der Weg zum Volltext ist
        dokumentiert (Akzeptanzkriterium #741)."""
        _add_position_mit_projekt(tmp_db)
        mcp = _make_mcp(tmp_db)
        result = _call(mcp, "profil_zusammenfassung", {})
        assert "projekte_anzeigen" in result["zusammenfassung"]
        assert "projekte_anzeigen" in result["projekt_volltext_hinweis"]
        # Kuerzung mit sichtbarem Marker statt hartem Abschneiden
        assert "…" in result["zusammenfassung"]

    def test_zusammenfassung_ohne_projekte_kein_hinweis_im_text(self, tmp_db):
        tmp_db.add_position({"company": "Leer AG", "title": "X"})
        mcp = _make_mcp(tmp_db)
        result = _call(mcp, "profil_zusammenfassung", {})
        assert "Volltext via projekte_anzeigen" not in result["zusammenfassung"]
