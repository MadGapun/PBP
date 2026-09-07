"""Tests fuer v1.7.33 — #979 (G29): der Prompt-Katalog als einzige Quelle.

Dieselben Metadaten standen an vier Stellen: `prompts.py` (25
registrierte Prompts), `_prompt_registry` (16 Builder), das META-Dict in
`dashboard.py` (18 Eintraege) und der Schnellzugriff im Frontend (12
Karten, mit Titel und Beschreibung als KOPIE aus META).

Eine Umbenennung musste damit zweimal passieren, ein neuer Prompt
dreimal — und genau das ist passiert: "Inbound erfassen" hiess
jahrelang anders als das, was der Prompt tut. Die Hilfe-Liste nannte
sich ausserdem "vollstaendige Liste aller Prompts" und zeigte 16 von
25.

Den Schnellzugriff konfigurierbar zu machen haette eine FUENFTE Kopie
erzeugt. Deshalb zuerst die Quelle.
"""
import re
from pathlib import Path

import pytest

from bewerbungs_assistent.services import prompt_katalog as katalog

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend" / "src"


def _registrierte_prompts() -> set[str]:
    quelle = (WURZEL / "src" / "bewerbungs_assistent"
              / "prompts.py").read_text(encoding="utf-8")
    return set(re.findall(r"@mcp\.prompt\(\)\s*\n\s*def (\w+)\(", quelle))


# ── Der Paritaets-Guard (Muster G20/#896) ───────────────────────────

def test_979_jeder_prompt_hat_einen_katalogeintrag_oder_eine_begruendung():
    """Der Kern des Issues.

    Er schlaegt fehl, sobald ein Prompt registriert wird, ohne dass
    jemand entschieden hat, ob und wie er in der Liste auftaucht.
    """
    registriert = _registrierte_prompts()
    im_katalog = {e["prompt"] for e in katalog.EINTRAEGE}
    offen = registriert - im_katalog - set(katalog.AUSNAHMEN)
    assert not offen, (
        "Diese Prompts haben weder einen Katalogeintrag noch eine "
        f"Begruendung in AUSNAHMEN: {sorted(offen)}")


def test_979_der_katalog_zeigt_auf_keinen_unbekannten_prompt():
    """Die Gegenrichtung: ein Eintrag auf einen entfernten Builder waere
    eine Karte, die beim Klick ins Leere laeuft."""
    registriert = _registrierte_prompts()
    verwaist = {e["prompt"] for e in katalog.EINTRAEGE} - registriert
    assert not verwaist, sorted(verwaist)


def test_979_jede_ausnahme_traegt_eine_begruendung():
    """Eine Ausnahmeliste ohne Begruendung ist eine Sperrliste."""
    for name, grund in katalog.AUSNAHMEN.items():
        assert grund and len(grund) > 10, name


def test_979_ausnahmen_sind_wirklich_registriert():
    """Sonst schleppt die Liste Namen mit, die es nicht mehr gibt, und
    verdeckt beim naechsten Mal einen echten Fund."""
    registriert = _registrierte_prompts()
    tot = set(katalog.AUSNAHMEN) - registriert
    assert not tot, sorted(tot)


def test_979_elwosa_prompts_stehen_nicht_im_katalog():
    """Nutzerentscheidung 07.09.2026: PBP laeuft unabhaengig von Elwosa,
    das gehoert nicht vermischt."""
    im_katalog = {e["prompt"] for e in katalog.EINTRAEGE}
    assert not any(p.startswith("elwosa_") for p in im_katalog)
    assert len([a for a in katalog.AUSNAHMEN if a.startswith("elwosa_")]) == 5


def test_979_die_beiden_arbeitsprompts_stehen_drin():
    """`dokumente_verarbeiten` und `problem_melden` fehlten in der
    Hilfe-Liste, obwohl sie sicher hineingehoeren."""
    im_katalog = {e["prompt"] for e in katalog.EINTRAEGE}
    assert "dokumente_verarbeiten" in im_katalog
    assert "problem_melden" in im_katalog


# ── Struktur des Katalogs ───────────────────────────────────────────

def test_979_jeder_eintrag_ist_vollstaendig():
    for e in katalog.EINTRAEGE:
        for feld in ("id", "prompt", "kategorie", "titel", "beschreibung",
                     "icon"):
            assert e.get(feld), (e.get("id"), feld)
        assert e["kategorie"] in katalog.KATEGORIEN, e["id"]


def test_979_kennungen_sind_eindeutig():
    ids = [e["id"] for e in katalog.EINTRAEGE]
    assert len(ids) == len(set(ids))


def test_979_zwei_eintraege_duerfen_auf_denselben_builder_zeigen():
    """Damit "Lebenslauf" und "Anschreiben" aus dem einen
    `bewerbung_schreiben` entstehen koennen (#981)."""
    mit_parametern = [e for e in katalog.EINTRAEGE if e.get("parameter")]
    assert mit_parametern, "keine Eintraege mit festen Parametern"
    for e in mit_parametern:
        assert e["id"] != e["prompt"], e["id"]
    nur_werte = {tuple(sorted(e["parameter"].items())) for e in mit_parametern}
    assert (("nur", "lebenslauf"),) in nur_werte
    assert (("nur", "anschreiben"),) in nur_werte


def test_979_standard_ist_ausgewogen():
    """Zwoelf Karten, drei je Kategorie — sonst steht eine Spalte leer."""
    standard = [e for e in katalog.alle() if e.get("standard")]
    assert len(standard) == 12, len(standard)
    aus_kategorie: dict[str, int] = {}
    for e in standard:
        aus_kategorie[e["kategorie"]] = aus_kategorie.get(e["kategorie"], 0) + 1
    assert set(aus_kategorie.values()) == {3}, aus_kategorie


def test_979_inbound_ist_nicht_mehr_im_standard():
    """#979 E: der Eintrag faellt aus dem Standard, bleibt waehlbar."""
    eintrag = katalog.eintrag("auto_bewerbung")
    assert eintrag is not None
    assert not eintrag.get("standard")


@pytest.mark.parametrize("kennung,titel", [
    ("bewerbung_schreiben", "Bewerbungsunterlagen"),
    ("auto_bewerbung", "Bewerbung aus Anzeige"),
])
def test_979_etiketten_sagen_was_der_prompt_tut(kennung, titel):
    assert katalog.eintrag(kennung)["titel"] == titel


# ── Die Auswahl des Nutzers ─────────────────────────────────────────

def test_979_ohne_auswahl_gilt_der_standard(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    assert katalog.auswahl(tmp_db) == katalog.standard_auswahl()


def test_979_auswahl_ueberlebt_und_wird_gelesen(tmp_db):
    """Update-Grundsatz: Einstellungen bleiben erhalten."""
    tmp_db.create_profile("Nutzerin", "n@example.com")
    katalog.auswahl_setzen(tmp_db, ["faq", "willkommen"])
    assert katalog.auswahl(tmp_db) == ["faq", "willkommen"]


def test_979_unbekannte_kennung_wird_gemeldet_nicht_geschluckt(tmp_db):
    """Eine erfundene Kennung waere sonst eine Karte, die einfach fehlt."""
    tmp_db.create_profile("Nutzerin", "n@example.com")
    erg = katalog.auswahl_setzen(tmp_db, ["faq", "gibt_es_nicht"])
    assert erg["uebernommen"] == ["faq"]
    assert erg["unbekannt"] == ["gibt_es_nicht"]


def test_979_leere_auswahl_faellt_auf_den_standard_zurueck(tmp_db):
    """Ein leerer Schnellzugriff waere eine Sackgasse (G23/#927)."""
    tmp_db.create_profile("Nutzerin", "n@example.com")
    katalog.auswahl_setzen(tmp_db, [])
    assert katalog.auswahl(tmp_db) == katalog.standard_auswahl()


def test_979_entfernter_katalogeintrag_zerlegt_nichts(tmp_db):
    """Bestandsinstallationen tragen Kennungen, die es spaeter nicht mehr
    gibt — sie fallen still weg statt den Schnellzugriff zu leeren."""
    tmp_db.create_profile("Nutzerin", "n@example.com")
    tmp_db.set_profile_setting(katalog.EINSTELLUNG, ["faq", "war_mal_da"])
    assert katalog.auswahl(tmp_db) == ["faq"]


def test_979_kaputter_wert_faellt_auf_den_standard(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    tmp_db.set_profile_setting(katalog.EINSTELLUNG, "keine liste")
    assert katalog.auswahl(tmp_db) == katalog.standard_auswahl()


def test_979_schnellzugriff_liefert_ganze_eintraege(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    katalog.auswahl_setzen(tmp_db, ["faq"])
    erg = katalog.schnellzugriff(tmp_db)
    assert len(erg) == 1
    assert erg[0]["titel"] == "FAQ"


# ── Das Frontend traegt keine Prompt-Texte mehr ─────────────────────

def test_979_dashboard_traegt_keine_prompt_texte():
    """Die Akzeptanz aus dem Issue: `grep` nach einem Titel findet EINE
    Stelle."""
    seite = (FRONTEND / "pages" / "DashboardPage.jsx").read_text(encoding="utf-8")
    for text in ("Profil im Gespraech erstellen", "Jobboersen durchsuchen lassen",
                 "Typische Fragen ueben", "Inbound erfassen"):
        assert text not in seite, text


def test_979_titel_stehen_im_repo_genau_einmal():
    """Gegen die Rueckkehr der Kopie."""
    treffer = []
    for pfad in list((WURZEL / "src").rglob("*.py")) + list(FRONTEND.rglob("*.jsx")):
        if "static" in pfad.parts:
            continue
        if "Profil im Gespraech erstellen" in pfad.read_text(
                encoding="utf-8", errors="replace"):
            treffer.append(pfad.name)
    assert treffer == ["prompt_katalog.py"], treffer


def test_979_schnellzugriff_rendert_aus_dem_katalog():
    quelle = (FRONTEND / "components"
              / "SchnellzugriffKarten.jsx").read_text(encoding="utf-8")
    assert "/api/prompts" in quelle
    assert "/api/prompts/schnellzugriff" in quelle


def test_979_hilfetext_oeffnet_die_hilfe_statt_sie_zu_nennen():
    """Befund 4: der Satz VERWIES auf den Reiter, ohne ihn oeffnen zu
    koennen — `helpOpen` lag als State in App.jsx und wurde nirgends
    durchgereicht."""
    quelle = (FRONTEND / "components"
              / "SchnellzugriffKarten.jsx").read_text(encoding="utf-8")
    assert 'openHelp?.("prompts")' in quelle
    app = (FRONTEND / "App.jsx").read_text(encoding="utf-8")
    assert "openHelp:" in app


def test_979_hilfe_liste_behauptet_keine_vollstaendigkeit_mehr():
    """Sie zeigte 16 von 25 und nannte sich vollstaendig."""
    app = (FRONTEND / "App.jsx").read_text(encoding="utf-8")
    assert "Vollstaendige Liste aller" not in app
    assert "Vollständige Liste aller" not in app


def test_979_hilfe_liste_schluesselt_nicht_mehr_nach_prompt_namen():
    """Zwei Eintraege duerfen auf denselben Builder zeigen — ein
    React-Key auf `name` waere doppelt."""
    app = (FRONTEND / "App.jsx").read_text(encoding="utf-8")
    assert "key={p.id || p.name}" in app


# ── Das MCP-Tool ────────────────────────────────────────────────────

def test_979_mcp_tool_existiert_und_zeigt_ohne_argument_den_katalog():
    quelle = (WURZEL / "src" / "bewerbungs_assistent" / "tools"
              / "workflows.py").read_text(encoding="utf-8")
    assert "def schnellzugriff_setzen(" in quelle
    block = quelle[quelle.index("def schnellzugriff_setzen("):]
    block = block[:block.index("def jobsuche_workflow_starten")]
    assert "prompt_katalog" in block
    assert '"katalog"' in block
    # Unbekannte Kennungen werden gemeldet, nicht geschluckt.
    assert '"unbekannt"' in block


def test_979_rest_endpunkt_liefert_katalog_und_auswahl():
    quelle = (WURZEL / "src" / "bewerbungs_assistent"
              / "dashboard.py").read_text(encoding="utf-8")
    block = quelle[quelle.index('@app.get("/api/prompts")'):]
    block = block[:block.index('@app.get("/api/workflow-prompt/{workflow_name}")')]
    assert "prompt_katalog" in block
    assert '"schnellzugriff"' in block
    # Das META-Dict ist wirklich weg, nicht nur ergaenzt.
    assert "META = {" not in block
