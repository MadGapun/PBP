"""Tests fuer v1.7.35 — #985 (G33): das Dashboard selbst zusammenstellen.

Nutzerwunsch vom 07.09.2026, nach der Auslieferung von Epic #978. Die
Einzelwuensche ("das nach oben", "das nimmt viel Platz fuer wenig
Inhalt", "das ganze Kapitel einklappbar") sind Symptome derselben Sache:

> *"manche wollen es, andere nicht. manche zum anklicken, manche
> offen."*

Reihenfolge und Auswahl der Bloecke waren eine Entscheidung im
Quelltext. Damit endet jede Diskussion darueber in einem Kompromiss, den
niemand wollte. Der Prompt-Katalog (#979) hat dieselbe Frage schon
beantwortet: Katalog gibt die Voreinstellung, der Mensch weicht ab, die
Abweichung liegt am Profil.
"""
from pathlib import Path

import pytest

from bewerbungs_assistent.services import dashboard_bereiche as db_bereiche

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend" / "src"


# ── Der Katalog ─────────────────────────────────────────────────────

def test_985_jeder_bereich_ist_vollstaendig():
    for b in db_bereiche.BEREICHE:
        for feld in ("id", "titel", "beschreibung"):
            assert b.get(feld), (b.get("id"), feld)
        assert isinstance(b.get("standard_sichtbar"), bool), b["id"]
        assert isinstance(b.get("standard_offen"), bool), b["id"]


def test_985_kennungen_sind_eindeutig():
    ids = [b["id"] for b in db_bereiche.BEREICHE]
    assert len(ids) == len(set(ids))


def test_985_impuls_steht_ueber_offen():
    """Nutzerwunsch 1: 'Das ganz nach oben, also ueber dem Punkt offen.'"""
    reihenfolge = [b["id"] for b in db_bereiche.standard()]
    assert reihenfolge.index("impuls") < reihenfolge.index("offen")


def test_985_offen_und_schnellzugriff_sind_in_der_voreinstellung_an():
    """'Im Standard waeren dann offen und Schnellzugriff.'"""
    an = {b["id"] for b in db_bereiche.standard() if b["sichtbar"]}
    assert "offen" in an and "schnellzugriff" in an


def test_985_recap_ist_in_der_voreinstellung_aus():
    """'Hier nimmt es viel Platz fuer wenig Inhalt' — der Block bestand
    aus einer einzigen Kennzahl."""
    aus = {b["id"] for b in db_bereiche.standard() if not b["sichtbar"]}
    assert "recap" in aus


def test_985_umgezogene_bereiche_stehen_nicht_mehr_im_katalog():
    """E-Mails und Gelerntes sind UMGEZOGEN, nicht abgeschaltet.

    Sie im Katalog stehen zu lassen waere die schlechtere Loesung: dann
    gaebe es sie an zwei Orten, und die Frage "wo steht das eigentlich"
    kaeme sofort zurueck — genau die Wiederholung, gegen die Epic #978
    angetreten ist.
    """
    ids = {b["id"] for b in db_bereiche.BEREICHE}
    assert "emails" not in ids
    assert "gelernt" not in ids

    from pathlib import Path
    wurzel = Path(__file__).resolve().parents[1]
    docs = (wurzel / "frontend" / "src" / "pages"
            / "DocumentsPage.jsx").read_text(encoding="utf-8")
    stats = (wurzel / "frontend" / "src" / "pages"
             / "StatsPage.jsx").read_text(encoding="utf-8")
    assert "EmailListe" in docs, "E-Mails brauchen eine neue Heimat"
    assert "LearningInsightsCard" in stats, "Gelerntes braucht eine neue Heimat"

    dash = (wurzel / "frontend" / "src" / "pages"
            / "DashboardPage.jsx").read_text(encoding="utf-8")
    assert "EmailDetailModal" not in dash
    assert "LearningInsightsCard" not in dash


# ── Die drei Freiheitsgrade ─────────────────────────────────────────

def test_985_ohne_einstellung_gilt_die_voreinstellung(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    assert db_bereiche.zustand(tmp_db) == db_bereiche.standard()


def test_985_reihenfolge_wird_gespeichert(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    gedreht = list(reversed(db_bereiche.standard()))
    db_bereiche.setzen(tmp_db, gedreht)
    assert [b["id"] for b in db_bereiche.zustand(tmp_db)] == \
        [b["id"] for b in gedreht]


def test_985_sichtbarkeit_und_einklappen_werden_gespeichert(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    neu = [dict(b, sichtbar=False, offen=False)
           if b["id"] == "kennzahlen" else b
           for b in db_bereiche.standard()]
    db_bereiche.setzen(tmp_db, neu)
    gelesen = {b["id"]: b for b in db_bereiche.zustand(tmp_db)}
    assert gelesen["kennzahlen"]["sichtbar"] is False
    assert gelesen["kennzahlen"]["offen"] is False


def test_985_offen_laesst_sich_nicht_abschalten(tmp_db):
    """Ein Dashboard, auf dem man das Faellige ausblenden kann, waere
    keins mehr. Einklappen bleibt erlaubt."""
    tmp_db.create_profile("Nutzerin", "n@example.com")
    versuch = [dict(b, sichtbar=False) if b["id"] == "offen" else b
               for b in db_bereiche.standard()]
    db_bereiche.setzen(tmp_db, versuch)
    gelesen = {b["id"]: b for b in db_bereiche.zustand(tmp_db)}
    assert gelesen["offen"]["sichtbar"] is True

    einklappen = [dict(b, offen=False) if b["id"] == "offen" else b
                  for b in db_bereiche.standard()]
    db_bereiche.setzen(tmp_db, einklappen)
    assert db_bereiche.zustand(tmp_db)[
        [x["id"] for x in db_bereiche.zustand(tmp_db)].index("offen")
    ]["offen"] is False


def test_985_zuruecksetzen_stellt_die_voreinstellung_her(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    db_bereiche.setzen(tmp_db, list(reversed(db_bereiche.standard())))
    db_bereiche.zuruecksetzen(tmp_db)
    assert db_bereiche.zustand(tmp_db) == db_bereiche.standard()


# ── Zusammenfuehren mit dem Katalog ─────────────────────────────────

def test_985_neuer_bereich_haengt_hinten_an(tmp_db):
    """Sonst saehe ein Bestandsnutzer neue Bloecke nie — seine
    gespeicherte Liste kennt sie nicht."""
    tmp_db.create_profile("Nutzerin", "n@example.com")
    nur_zwei = [{"id": "offen", "sichtbar": True, "offen": True},
                {"id": "schnellzugriff", "sichtbar": True, "offen": True}]
    tmp_db.set_profile_setting(db_bereiche.EINSTELLUNG, nur_zwei)
    erg = db_bereiche.zustand(tmp_db)
    assert len(erg) == len(db_bereiche.BEREICHE)
    assert [b["id"] for b in erg][:2] == ["offen", "schnellzugriff"]


def test_985_entfernter_bereich_faellt_still_weg(tmp_db):
    """Eine Kennung aus einer alten Version darf keine leere Zeile
    erzeugen."""
    tmp_db.create_profile("Nutzerin", "n@example.com")
    tmp_db.set_profile_setting(db_bereiche.EINSTELLUNG, [
        {"id": "gab_es_mal", "sichtbar": True, "offen": True},
        {"id": "offen", "sichtbar": True, "offen": True},
    ])
    ids = [b["id"] for b in db_bereiche.zustand(tmp_db)]
    assert "gab_es_mal" not in ids
    assert ids[0] == "offen"


def test_985_dubletten_werden_verworfen(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    tmp_db.set_profile_setting(db_bereiche.EINSTELLUNG, [
        {"id": "offen", "sichtbar": True, "offen": True},
        {"id": "offen", "sichtbar": True, "offen": False},
    ])
    ids = [b["id"] for b in db_bereiche.zustand(tmp_db)]
    assert ids.count("offen") == 1


def test_985_kaputter_wert_faellt_auf_die_voreinstellung(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    tmp_db.set_profile_setting(db_bereiche.EINSTELLUNG, "keine liste")
    assert db_bereiche.zustand(tmp_db) == db_bereiche.standard()


def test_985_unbekannte_kennung_wird_gemeldet(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    erg = db_bereiche.setzen(tmp_db, [
        {"id": "offen", "sichtbar": True, "offen": True},
        {"id": "gibt_es_nicht", "sichtbar": True, "offen": True},
    ])
    assert erg["unbekannt"] == ["gibt_es_nicht"]


def test_985_keine_liste_wird_abgewiesen(tmp_db):
    tmp_db.create_profile("Nutzerin", "n@example.com")
    with pytest.raises(ValueError):
        db_bereiche.setzen(tmp_db, {"id": "offen"})


# ── Das Frontend ────────────────────────────────────────────────────

def test_985_dashboard_rendert_aus_der_reihenfolge():
    seite = (FRONTEND / "pages" / "DashboardPage.jsx").read_text(encoding="utf-8")
    assert "/api/dashboard/bereiche" in seite
    assert "bereiche.filter((b) => b.sichtbar)" in seite
    assert "bereichsInhalt[b.id]" in seite


def test_985_hooks_stehen_vor_jedem_frueh_ausstieg():
    """Der Fehler, der beim Bauen passiert ist: der neue `useEffect`
    stand 160 Zeilen weiter unten, direkt neben den Funktionen, zu denen
    er inhaltlich gehoert — und damit HINTER dem Lade-Ausstieg
    `if (loading ...) return <LoadingPanel/>`.

    Ein Hook hinter einem `return` laeuft im ersten Durchgang nicht und
    im zweiten schon. React bricht das mit Fehler 300 ab, der
    ErrorBoundary zeigt die ganze Seite als kaputt — und im Browser sah
    man zunaechst nur eine alte, gecachte Fassung.
    """
    import re
    seite = (FRONTEND / "pages" / "DashboardPage.jsx").read_text(encoding="utf-8")
    start = seite.index("export default function DashboardPage")
    rumpf = seite[start:seite.index("\n}\n", start)]
    zeilen = rumpf.splitlines()

    erster_ausstieg = None
    for i, z in enumerate(zeilen):
        if re.match(r"^    return <LoadingPanel", z) or re.match(r"^  return ", z):
            erster_ausstieg = i
            break
    assert erster_ausstieg is not None

    for i, z in enumerate(zeilen):
        if i <= erster_ausstieg:
            continue
        assert not re.search(r"\buse(State|Effect|Ref|Callback|Memo|EffectEvent)\(", z), (
            f"Hook in Zeile {i} steht hinter dem Ausstieg in Zeile "
            f"{erster_ausstieg}: {z.strip()[:60]}")


def test_985_anpassen_ansicht_kann_sortieren_und_zuruecksetzen():
    quelle = (FRONTEND / "components"
              / "DashboardAnpassen.jsx").read_text(encoding="utf-8")
    assert "verschieben" in quelle
    assert "onZuruecksetzen" in quelle
    # Feste Bereiche lassen sich nicht abwaehlen.
    assert "disabled={fest}" in quelle


def test_985_einklappen_merkt_sich_am_profil_nicht_im_browser():
    """'letzte einstellung merken' — und zwar so, dass sie den Rechner
    ueberlebt, nicht nur die Sitzung."""
    quelle = (FRONTEND / "components"
              / "DashboardBereich.jsx").read_text(encoding="utf-8")
    assert "localStorage" not in quelle
    assert "onUmschalten" in quelle


# ── "Neu seit dem letzten Mal" statt eines eigenen Blocks ───────────

def test_985_neue_zeilen_werden_markiert(tmp_db):
    """Nutzerhinweis: den Recap-Block mit der Offen-Liste verschmelzen,
    "indem man das irgendwie einfach mit einem Symbol kennzeichnet"."""
    from datetime import date, datetime, timedelta, timezone
    from bewerbungs_assistent.services import aufgaben_sicht

    tmp_db.create_profile("Nutzerin", "n@example.com")
    aid = tmp_db.add_application({"title": "Fachkraft",
                                  "company": "Musterbetrieb GmbH",
                                  "status": "beworben"})
    # Letzter Besuch: vor zwei Stunden — die Aufgabe entsteht danach.
    vorher = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    tmp_db.set_profile_setting(aufgaben_sicht.BESUCH_EINSTELLUNG, vorher)
    tmp_db.add_task({"application_id": aid, "titel": "Frisch",
                     "faellig_am": date.today().isoformat()})

    block = aufgaben_sicht.dashboard_block(tmp_db)
    zeilen = [e for g in block["gruppen"].values() for e in g]
    assert zeilen, "Testdaten fehlen"
    assert block["neu_anzahl"] >= 1
    assert any(e.get("neu") for e in zeilen)


def test_985_alte_zeilen_bleiben_unmarkiert(tmp_db):
    from datetime import date, datetime, timedelta, timezone
    from bewerbungs_assistent.services import aufgaben_sicht

    tmp_db.create_profile("Nutzerin", "n@example.com")
    aid = tmp_db.add_application({"title": "Fachkraft",
                                  "company": "Musterbetrieb GmbH",
                                  "status": "beworben"})
    tmp_db.add_task({"application_id": aid, "titel": "Alt",
                     "faellig_am": date.today().isoformat()})
    # Letzter Besuch: erst NACH der Anlage.
    nachher = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    tmp_db.set_profile_setting(aufgaben_sicht.BESUCH_EINSTELLUNG, nachher)

    block = aufgaben_sicht.dashboard_block(tmp_db)
    assert block["neu_anzahl"] == 0


def test_985_marke_ueberlebt_das_neuladen(tmp_db):
    """Der Zeitpunkt wird beim Lesen fortgeschrieben — aber nur, wenn
    genug Zeit vergangen ist.

    Ohne diese Bremse waere die Marke nach dem ersten Neuladen weg: die
    Auskunft "seit deinem letzten Besuch" haette sich beim ersten
    Hinsehen selbst geloescht.
    """
    from datetime import date, datetime, timedelta, timezone
    from bewerbungs_assistent.services import aufgaben_sicht

    tmp_db.create_profile("Nutzerin", "n@example.com")
    aid = tmp_db.add_application({"title": "Fachkraft",
                                  "company": "Musterbetrieb GmbH",
                                  "status": "beworben"})
    vorher = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    tmp_db.set_profile_setting(aufgaben_sicht.BESUCH_EINSTELLUNG, vorher)
    tmp_db.add_task({"application_id": aid, "titel": "Frisch",
                     "faellig_am": date.today().isoformat()})

    erst = aufgaben_sicht.dashboard_block(tmp_db)["neu_anzahl"]
    zweit = aufgaben_sicht.dashboard_block(tmp_db)["neu_anzahl"]
    assert erst == zweit >= 1


def test_985_langer_abstand_setzt_den_besuch_neu(tmp_db):
    """Nach einer echten Pause beginnt ein neuer Besuch."""
    from datetime import datetime, timedelta, timezone
    from bewerbungs_assistent.services import aufgaben_sicht

    tmp_db.create_profile("Nutzerin", "n@example.com")
    lange_her = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    tmp_db.set_profile_setting(aufgaben_sicht.BESUCH_EINSTELLUNG, lange_her)
    aufgaben_sicht.dashboard_block(tmp_db)
    danach = tmp_db.get_profile_setting(aufgaben_sicht.BESUCH_EINSTELLUNG, "")
    assert danach != lange_her, "Der Besuch muss fortgeschrieben werden"


def test_985_offenblock_zeigt_die_marke():
    quelle = (FRONTEND / "components" / "OffenBlock.jsx").read_text(encoding="utf-8")
    assert "e.neu" in quelle
    assert "neu_anzahl" in quelle
