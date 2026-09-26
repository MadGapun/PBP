"""Tests fuer #1055 — Gehalt und Saetze standen an zwei Orten.

Gemeldet am 17.09.2026, gemessen in einem Bestand: Mindestgehalt 75.000
in den Suchkriterien gegen 80.000 in den Job-Praeferenzen, Tagessatz 800
gegen 900, Ziel-Tagessatz 1.350 gegen 1.200. Die Praeferenzen stammen
aus der Ersterfassung im Gespraech und haben in keiner Oberflaeche ein
Eingabefeld — sie wurden also nie nachgezogen.

**Der teuerste Leser war `fit_analyse`.** Es holte die Kriterien durch
das Nadeloehr aus #987 und ueberschrieb `min_gehalt` danach mit dem Wert
aus den Praeferenzen. Dieselbe Stelle bekam in der Liste einen anderen
Rahmenwert als in der Detailansicht, und beide Zahlen hiessen "dein
Minimum" — #963 an einer neuen Stelle.

Nutzervorgabe vom 17.09.2026, woertlich: *"Nur die Werte, die auf der
Einstellungsseite stehen, gelten. Wenn woanders Gehaltsangaben oder
Wuensche stehen, sind die dort falsch und muessen weg."*

Alle Firmen und Orte sind Platzhalter.
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

from bewerbungs_assistent.services import praeferenzen_quelle as pq  # noqa: E402


# ══ Das Nadeloehr ═══════════════════════════════════════════════════

class _FakeDB:
    def __init__(self, krit=None, prefs=None):
        self._krit = krit or {}
        self._profil = {"name": "Test", "preferences": dict(prefs or {})}
        self._settings = {}
        self.gespeichert = []

    def get_search_criteria(self):
        return dict(self._krit)

    def get_profile(self):
        return dict(self._profil)

    def save_profile(self, daten):
        self.gespeichert.append(daten)
        self._profil.update(daten)

    def get_profile_setting(self, key, default=None):
        return self._settings.get(key, default)

    def set_profile_setting(self, key, value):
        self._settings[key] = value


def test_die_werte_kommen_aus_den_suchkriterien():
    """Und tragen die Praeferenz-NAMEN, damit die vier Leser ihre
    Antwortform behalten koennen."""
    db = _FakeDB(krit={"min_gehalt": 75000, "wunsch_gehalt": 95000,
                       "min_tagessatz": 800, "wunsch_tagessatz": 1350})
    werte = pq.wunschwerte(db)
    assert werte["min_gehalt"] == 75000
    assert werte["ziel_gehalt"] == 95000
    assert werte["ziel_tagessatz"] == 1350
    # Was nicht gesetzt ist, steht nicht da — 0 ist kein Wunsch (#989).
    assert "min_stundensatz" not in werte


def test_der_gemeldete_widerspruch_wird_benannt():
    """Die Auskunft nennt beide Seiten und sagt, welche gilt.

    Sie schreibt nichts: wer nur nachsehen will, was doppelt steht, soll
    den Bestand dabei nicht veraendern.
    """
    db = _FakeDB(krit={"min_gehalt": 75000, "min_tagessatz": 800,
                       "wunsch_tagessatz": 1350},
                 prefs={"min_gehalt": 80000, "min_tagessatz": 900,
                        "ziel_tagessatz": 1200, "arbeitsmodell": "hybrid"})
    befund = pq.gefundene_doppelung(db)
    assert befund["min_gehalt"] == {"im_profil": 80000,
                                    "in_den_suchkriterien": 75000,
                                    "gilt": 75000}
    assert befund["ziel_tagessatz"]["gilt"] == 1350
    # Das Arbeitsmodell hat kein Gegenstueck auf der Einstellungsseite
    # und bleibt deshalb unberuehrt.
    assert "arbeitsmodell" not in befund
    assert not db.gespeichert, "eine Auskunft schreibt nicht"


def test_bereinigen_entfernt_die_felder_und_schreibt_den_beleg():
    """Ein gesetzter Wert darf nicht still verschwinden (#1053)."""
    db = _FakeDB(krit={"min_gehalt": 75000},
                 prefs={"min_gehalt": 80000, "ziel_gehalt": 90000,
                        "arbeitsmodell": "hybrid", "reisebereitschaft": "gering"})
    ergebnis = pq.bereinigen(db)
    assert ergebnis["entfernt"] == 2

    prefs = db.get_profile()["preferences"]
    assert "min_gehalt" not in prefs and "ziel_gehalt" not in prefs
    # Was kein Gegenstueck hat, bleibt — es zu loeschen waere kein
    # Aufraeumen, sondern ein Datenverlust.
    assert prefs["arbeitsmodell"] == "hybrid"
    assert prefs["reisebereitschaft"] == "gering"

    beleg = pq.entfernte_werte(db)
    assert beleg["min_gehalt"]["im_profil"] == 80000
    assert beleg["min_gehalt"]["gilt"] == 75000
    # Auch ohne Gegenstueck in den Kriterien wird der Wert festgehalten:
    # gerade dann ist er sonst weg.
    assert beleg["ziel_gehalt"]["im_profil"] == 90000
    assert beleg["ziel_gehalt"]["gilt"] is None


def test_ein_leeres_doppel_feld_faellt_ebenfalls_weg():
    """Gefunden auf der Bestandskopie, nicht im Bericht.

    Dort standen `max_entfernung_km` und `min_stundensatz` mit `null` in
    den Praeferenzen. Sie tragen keinen Wert, also gibt es nichts zu
    belegen — der SCHLUESSEL bliebe aber liegen, und `profil_bearbeiten`
    weist ihn seit diesem Release ab: ein Feld, das dasteht und das
    niemand mehr setzen kann (#988 in der Gegenrichtung).

    Gezaehlt wird getrennt: was einen Wert trug, gehoert in den Hinweis,
    ein leerer Schluessel nicht.
    """
    db = _FakeDB(krit={"min_gehalt": 75000},
                 prefs={"min_gehalt": 80000, "max_entfernung_km": None,
                        "min_stundensatz": "", "arbeitsmodell": "hybrid"})
    ergebnis = pq.bereinigen(db)
    assert ergebnis["entfernt"] == 1
    assert ergebnis["leere_entfernt"] == 2

    prefs = db.get_profile()["preferences"]
    assert "max_entfernung_km" not in prefs and "min_stundensatz" not in prefs
    assert prefs["arbeitsmodell"] == "hybrid"
    # Der Beleg nennt nur, was wirklich etwas wert war.
    assert list(pq.entfernte_werte(db)) == ["min_gehalt"]


def test_nur_leere_doppel_felder_schreiben_keinen_beleg():
    """Sonst stuende ein Hinweis da, der nichts zu sagen hat (#929)."""
    db = _FakeDB(krit={"min_gehalt": 75000}, prefs={"min_gehalt": None})
    ergebnis = pq.bereinigen(db)
    assert ergebnis["entfernt"] == 0 and ergebnis["leere_entfernt"] == 1
    assert pq.entfernte_werte(db) == {}
    # Und zwar gar keine Ablage, nicht eine mit leerer Liste: die
    # Pruefung oben allein war blind, weil `entfernte_werte` beides
    # gleich beantwortet. Gefunden von der Gegenprobe.
    assert db.get_profile_setting(pq.MARKE) is None


def test_bereinigen_ist_idempotent_und_verliert_den_beleg_nicht():
    """Der zweite Lauf findet nichts mehr — und darf den Beleg des
    ersten nicht ueberschreiben. Sonst stuende im Hinweis irgendwann
    nichts mehr, obwohl etwas entfernt wurde."""
    db = _FakeDB(krit={"min_gehalt": 75000}, prefs={"min_gehalt": 80000})
    assert pq.bereinigen(db)["entfernt"] == 1
    assert pq.bereinigen(db)["entfernt"] == 0
    assert pq.entfernte_werte(db)["min_gehalt"]["im_profil"] == 80000


def test_ein_zweiter_fund_kommt_zum_beleg_dazu():
    """Der Fall, in dem das Zusammenfuehren wirklich arbeitet.

    Der Test darueber erreicht ihn NICHT: sein zweiter Lauf findet
    nichts und steigt vorher aus. Gebraucht wird ein zweiter Lauf, der
    selbst etwas entfernt — dann treffen alter und neuer Beleg
    aufeinander, und der alte darf nicht verschwinden. Die Lage entsteht,
    wenn ein Wert nach dem ersten Lauf erneut ins Profil geraet (Import,
    Profil-Wiederherstellung, ein alter Client).

    Gefunden hat die Luecke die Gegenprobe: das Zusammenfuehren
    auszubauen machte nichts rot.
    """
    db = _FakeDB(krit={"min_gehalt": 75000, "min_tagessatz": 800},
                 prefs={"min_gehalt": 80000})
    assert pq.bereinigen(db)["entfernt"] == 1

    profil = db.get_profile()
    db.save_profile({**profil,
                     "preferences": {**profil["preferences"],
                                     "min_tagessatz": 900}})
    assert pq.bereinigen(db)["entfernt"] == 1

    beleg = pq.entfernte_werte(db)
    assert set(beleg) == {"min_gehalt", "min_tagessatz"}
    assert beleg["min_gehalt"]["im_profil"] == 80000, "der alte Beleg bleibt"


# ══ Die Leser ═══════════════════════════════════════════════════════

@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17118_gehalt_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _bestand_mit_doppelung(db):
    """Der gemeldete Zustand: zwei Orte, verschiedene Zahlen."""
    db.set_search_criteria("min_gehalt", 75000)
    db.set_search_criteria("wunsch_tagessatz", 1350)
    db.set_search_criteria("min_tagessatz", 800)
    profil = db.get_profile()
    db.save_profile({**profil, "preferences": {
        "min_gehalt": 80000, "min_tagessatz": 900, "ziel_tagessatz": 1200,
        "arbeitsmodell": "hybrid"}})


def test_die_fit_analyse_rechnet_nicht_mehr_mit_dem_profilwert(umgebung):
    """Der teuerste Leser: er ueberschrieb die Kriterien NACH dem
    Nadeloehr aus #987.

    Geprueft wird an der Sache — eine Stelle, deren Gehalt zwischen
    beiden Zahlen liegt. Mit dem Profilwert (80.000) liegt sie darunter,
    mit dem Wert der Einstellungsseite (75.000) darueber. Ohne diesen
    Zuschnitt haette der Test die Umstellung nicht gesehen.
    """
    db, mcp = umgebung
    _bestand_mit_doppelung(db)
    db.set_search_criteria("keywords_muss", ["Stammdaten"])
    db.save_jobs([{
        "hash": "g1", "title": "Stammdaten Migration",
        "company": "Musterfirma GmbH", "location": "Musterstadt",
        "url": "https://example.com/1055/g1", "source": "manuell",
        "_manual_entry": True,
        "description": "Stammdaten und Migration im Bestand. " * 12,
        "employment_type": "festanstellung", "salary_min": 78000,
        "salary_max": 78000, "salary_type": "jaehrlich",
        "salary_estimated": 0, "score": 5.0,
    }])
    hash_ = db.get_active_jobs()[0]["hash"]
    befund = _call(mcp, "fit_analyse", {"job_hash": hash_})
    faktoren = " ".join(str(f) for f in (befund.get("factors") or []))
    # 78.000 liegt ueber dem Minimum der Einstellungsseite — der
    # Rahmenwert traegt den Gehaltsbonus.
    assert befund["rahmenscore"] > 0, befund
    assert "80000" not in faktoren and "80.000" not in faktoren


def test_die_gehaltsauskunft_nennt_die_einstellungsseite(umgebung):
    """`gehalt_marktanalyse` las die Praeferenzen; jetzt die Kriterien —
    und sagt, woher die Zahl kommt."""
    db, mcp = umgebung
    _bestand_mit_doppelung(db)
    antwort = _call(mcp, "gehalt_marktanalyse", {})
    vorstellungen = antwort.get("deine_vorstellungen") or {}
    assert vorstellungen.get("min_gehalt") == 75000
    assert vorstellungen.get("ziel_tagessatz") == 1350
    assert "Suchkriterien" in str(vorstellungen.get("quelle"))


def test_die_gehaltspruefung_einer_stelle_nimmt_dieselbe_zahl(umgebung):
    """`gehalt_extrahieren` vergleicht das erkannte Gehalt mit "deinem
    Minimum" — und las es aus den Praeferenzen.

    Der Fall ist so zugeschnitten, dass die beiden Zahlen sich
    unterscheiden: 78.000 liegt ueber der Einstellungsseite (75.000) und
    unter dem Profilwert (80.000). Aus "passt" wurde damit "passt
    nicht", je nachdem wer fragt.
    """
    db, mcp = umgebung
    _bestand_mit_doppelung(db)
    db.save_jobs([{
        "hash": "g2", "title": "Stammdaten Migration",
        "company": "Musterfirma GmbH", "location": "Musterstadt",
        "url": "https://example.com/1055/g2", "source": "manuell",
        "_manual_entry": True,
        "description": ("Stammdaten und Migration im Bestand. " * 10 +
                        "Wir bieten 78.000 EUR pro Jahr."),
        "employment_type": "festanstellung", "score": 5.0,
    }])
    hash_ = db.get_active_jobs()[0]["hash"]
    antwort = _call(mcp, "gehalt_extrahieren", {"job_hash": hash_})
    vergleich = antwort.get("vergleich_mit_profil") or {}
    assert vergleich.get("dein_minimum") == 75000
    assert vergleich.get("passt") is True
    assert "Suchkriterien" in str(vergleich.get("quelle"))


def test_der_rest_weg_liefert_dieselben_zahlen(umgebung):
    """Zwei Wege, eine Quelle — sonst waere es #1008 noch einmal."""
    db, _ = umgebung
    _bestand_mit_doppelung(db)
    from fastapi.testclient import TestClient
    import bewerbungs_assistent.dashboard as _dash
    importlib.reload(_dash)
    _dash._db = db
    with TestClient(_dash.app) as client:
        antwort = client.get("/api/salary-stats").json()
    assert antwort["deine_vorstellungen"]["min_gehalt"] == 75000
    assert antwort["deine_vorstellungen"]["min_tagessatz"] == 800


# ══ Der Schreibweg ══════════════════════════════════════════════════

def test_die_praeferenzen_nehmen_gehalt_nicht_mehr_an(umgebung):
    """Abgewiesen und BENANNT, nicht still verworfen.

    Ein Feld, das man setzen kann und das nicht wirkt, ist schlimmer als
    ein fehlendes (#988) — genau so ist diese Doppelung entstanden.
    """
    db, mcp = umgebung
    antwort = _call(mcp, "profil_bearbeiten", {
        "bereich": "praeferenzen", "aktion": "aendern",
        "daten": {"min_gehalt": 99000, "arbeitsmodell": "remote"}})
    assert antwort["status"] == "aktualisiert"
    assert antwort["nicht_uebernommen"] == ["min_gehalt"]
    assert "suchkriterien_setzen" in antwort["stattdessen"]
    assert antwort["neue_werte"]["arbeitsmodell"] == "remote"
    assert "min_gehalt" not in antwort["neue_werte"]


def test_die_dokument_extraktion_schreibt_kein_gehalt_ins_profil(umgebung):
    """Der fuenfte Schreibweg, gefunden beim Nachmessen.

    `extraktion_anwenden` uebernimmt einen `praeferenzen`-Block aus einem
    Dokument. Ein Lebenslauf oder ein Anschreiben mit einer
    Gehaltsvorstellung haette die Doppelung damit neu angelegt — an der
    Abweisung in `profil_bearbeiten` vorbei. Eine Abweisung an EINEM von
    mehreren Schreibwegen ist keine.

    Was nicht uebernommen wird, wird BENANNT: die Angabe stand im
    Dokument, und der Mensch soll wissen, wohin sie gehoert.
    """
    db, mcp = umgebung
    db.set_search_criteria("min_gehalt", 75000)

    doc_id = db.add_document({
        "filename": "lebenslauf.txt", "file_path": "/tmp/lebenslauf.txt",
        "doc_type": "lebenslauf", "extracted_text": "Platzhalter",
    })
    lauf_id = db.add_extraction_history({
        "document_id": doc_id,
        "profile_id": db.get_active_profile_id(),
        "extraction_type": "test_1055",
        "extracted_fields": {
            "praeferenzen": {"min_gehalt": 99000, "arbeitsmodell": "remote"},
        },
    })

    antwort = _call(mcp, "extraktion_anwenden",
                    {"extraction_id": lauf_id, "bereiche": ["praeferenzen"]})
    uebernommen = antwort.get("angewendete_bereiche") or {}
    assert "min_gehalt" not in (uebernommen.get("praeferenzen") or [])
    assert uebernommen.get("praeferenzen_nicht_uebernommen") == ["min_gehalt"]
    assert "suchkriterien_setzen" in str(
        uebernommen.get("praeferenzen_stattdessen"))

    prefs = db.get_profile()["preferences"]
    assert "min_gehalt" not in prefs
    assert prefs.get("arbeitsmodell") == "remote", "der Rest kommt an"


def test_ein_alter_profil_export_bringt_die_doppelung_nicht_zurueck(umgebung):
    """Ein Export von vor v1.7.118 traegt Gehalt und Saetze im Profil.

    Sie dort wieder abzulegen hiesse, die Doppelung mit dem Import
    zurueckzuholen — und zwar an allen Abweisungen vorbei. Der Import
    legt ein NEUES Profil an, dessen Kriterien leer sind: die Angabe
    geht also nicht verloren, sie kommt an ihrem Ort an.

    In der Gegenprobe blieb dieser Weg stumm, bis der Fall dastand.
    """
    db, _ = umgebung
    db.import_profile_json({
        "name": "Importiert",
        "email": "import@example.com",
        "preferences": {
            "min_gehalt": 82000, "ziel_tagessatz": 1100,
            "arbeitsmodell": "hybrid",
        },
    })
    profil = db.get_profile()
    assert profil["name"] == "Importiert"
    prefs = profil["preferences"]
    assert "min_gehalt" not in prefs and "ziel_tagessatz" not in prefs
    assert prefs["arbeitsmodell"] == "hybrid", "ohne Gegenstueck bleibt es"

    krit = db.get_search_criteria()
    assert str(krit.get("min_gehalt")) == "82000"
    assert str(krit.get("wunsch_tagessatz")) == "1100"
    assert pq.wunschwerte(db)["ziel_tagessatz"] == 1100


def test_jeder_schreibweg_in_die_praeferenzen_ist_entschieden():
    """Wer einen `preferences`-Block schreibt, steht hier mit Grund.

    Die Abweisung sass zuerst nur in `profil_bearbeiten`. Gefunden wurden
    danach `extraktion_anwenden` (ein Lebenslauf mit Gehaltsvorstellung),
    `profil_erstellen` — die Ersterfassung, also genau der Weg, der die
    gemeldete Doppelung angelegt hat — und der Profil-Import. Ein Test je
    Fundstelle faengt die Fundstellen, die man kennt (v1.7.100 MERKE 3).

    Der Guard zaehlt keine Stellen ab, er verlangt eine Entscheidung: fuer
    jeden Weg steht da, was er mit Gehalt und Saetzen macht. Ein neuer Weg
    ist unbekannt und macht diesen Test rot.
    """
    import ast

    SCHREIBWEGE = {
        ("services/praeferenzen_quelle.py", "bereinigen"):
            "entfernt die Felder — das Safety-Net selbst",
        # v1.7.119 (#1056): der Guard hat ihn beim ersten Suitenlauf
        # gemeldet — genau die Entscheidung, die er erzwingen soll.
        ("services/notiz_routing.py", "verschieben"):
            "reicht den vorhandenen Block durch, legt nichts an",
        ("tools/profil.py", "profil_erstellen"):
            "leitet sie in die Suchkriterien um (nach_suchkriterien)",
        ("tools/profil.py", "profil_bearbeiten"):
            "weist sie ab und nennt den richtigen Ort",
        ("tools/profil.py", "profil_umlaute_reparieren"):
            "reicht den vorhandenen Block durch, legt nichts an",
        ("tools/dokumente.py", "extraktion_anwenden"):
            "weist sie ab und nennt sie im Ergebnis",
        ("database.py", "import_profile_json"):
            "leitet sie in die Suchkriterien des neuen Profils um",
        ("dashboard.py", "api_update_document_extraction"):
            "reicht den vorhandenen Block durch, legt nichts an",
        ("dashboard.py", "api_analyze_documents"):
            "reicht den vorhandenen Block durch, legt nichts an",
    }

    wurzel = _repo() / "src" / "bewerbungs_assistent"
    gefunden = set()
    for pfad in sorted(wurzel.rglob("*.py")):
        quelle = pfad.read_text(encoding="utf-8-sig")
        if "save_profile(" not in quelle or '"preferences"' not in quelle:
            continue
        baum = ast.parse(quelle)

        # Zu jedem Aufruf die INNERSTE umschliessende Funktion.
        eltern = {}
        for knoten in ast.walk(baum):
            for kind in ast.iter_child_nodes(knoten):
                eltern[kind] = knoten

        for knoten in ast.walk(baum):
            if not (isinstance(knoten, ast.Call)
                    and getattr(knoten.func, "attr", None) == "save_profile"):
                continue
            aktuell = eltern.get(knoten)
            while aktuell is not None and not isinstance(
                    aktuell, (ast.FunctionDef, ast.AsyncFunctionDef)):
                aktuell = eltern.get(aktuell)
            if aktuell is None:
                continue
            # Das Dict entsteht oft VOR dem Aufruf (`update_data`), also
            # zaehlt der Rumpf der Funktion, nicht das Argument. Die
            # erste Fassung las das Argument und sah 3 von 8 Wegen.
            rumpf = ast.get_source_segment(quelle, aktuell) or ""
            if '"preferences"' not in rumpf:
                continue
            gefunden.add((pfad.relative_to(wurzel).as_posix(), aktuell.name))

    unbekannt = sorted(gefunden - set(SCHREIBWEGE))
    assert not unbekannt, (
        "Neuer Schreibweg in die Praeferenzen — entscheide, was er mit "
        f"Gehalt und Saetzen macht (#1055): {unbekannt}")

    # Und die Liste darf nicht veralten: was es nicht mehr gibt, gehoert
    # heraus, sonst deckt sie irgendwann einen Weg, den niemand prueft.
    verschwunden = sorted(set(SCHREIBWEGE) - gefunden)
    assert not verschwunden, f"Eintrag ohne Fundstelle: {verschwunden}"
    for eintrag, grund in SCHREIBWEGE.items():
        assert grund.strip(), f"Ausnahme ohne Grund: {eintrag}"


def test_die_zusammenfassung_zeigt_die_werte_mit_herkunft(umgebung):
    """Sie standen unter "Job-Praeferenzen" — also genau dort, wo der
    Nutzer die zweite Ablage vermutete. Jetzt stehen sie unter ihrer
    Quelle."""
    db, mcp = umgebung
    _bestand_mit_doppelung(db)
    text = str(_call(mcp, "profil_zusammenfassung", {}))
    assert "Gehalt und Sätze (aus den Suchkriterien)" in text
    assert "75000" in text
    # Und NICHT mehr in der Praeferenz-Liste.
    praeferenzen = text.split("Job-Präferenzen")[-1].split("Gehalt und Saetze")[0]
    assert "80000" not in praeferenzen


def test_der_start_raeumt_auf_und_nennt_was_er_entfernt_hat(umgebung):
    """Das Safety-Net laeuft beim Start, der Hinweis nennt die Zahlen.

    Ein Hinweis ohne die Werte waere eine Behauptung ueber etwas, das
    niemand mehr nachlesen kann.
    """
    db, _ = umgebung
    _bestand_mit_doppelung(db)

    # Ueber `initialize()`, nicht ueber den direkten Aufruf: geprueft
    # werden soll der DRAHT. Mein erster Test rief `bereinigen` selbst
    # auf — das Safety-Net am Start haette fehlen koennen, ohne dass er
    # es merkt (DoD 8c: geschrieben ist nicht aufgerufen).
    import bewerbungs_assistent.database as _db_mod
    zweiter = _db_mod.Database()
    zweiter.initialize()
    try:
        prefs = zweiter.get_profile()["preferences"]
        assert "min_gehalt" not in prefs and "min_tagessatz" not in prefs
        assert prefs["arbeitsmodell"] == "hybrid", "ohne Gegenstueck bleibt es"
    finally:
        zweiter.close()

    from bewerbungs_assistent.services import onboarding_hints
    importlib.reload(onboarding_hints)
    hints = {h["id"]: h for h in onboarding_hints.list_active_hints(db)}
    assert "c86_gehalt_nur_einstellungsseite" in hints
    detail = hints["c86_gehalt_nur_einstellungsseite"].get("detail", "")
    assert "80000" in detail and "75000" in detail

    # Nach dem Wegklicken schweigt er — die Werte bleiben trotzdem
    # nachlesbar.
    onboarding_hints.dismiss_hint(db, "c86_gehalt_nur_einstellungsseite")
    ids = [h["id"] for h in onboarding_hints.list_active_hints(db)]
    assert "c86_gehalt_nur_einstellungsseite" not in ids
    assert pq.entfernte_werte(db)["min_gehalt"]["im_profil"] == 80000
