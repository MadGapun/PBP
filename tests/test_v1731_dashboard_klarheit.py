"""Tests fuer v1.7.31 — Epic #978, erste drei Sub-Issues.

Ein externer Design-Review vom 05./06.09.2026 fand sieben Befunde an
EINEM Bildschirm. Der rote Faden ist nicht Optik: dieselbe Lage stand
an drei Stellen in drei Zaehlweisen, eine Empfehlung nannte eine Zahl
statt einer Handlung, und Onboarding-Information stand ausserhalb des
Onboardings.

Hier die drei, die zuerst drankommen:

* **#977 (G28)** — der Tagesimpuls riet am Samstag zur Ruhe, waehrend
  zwei Zeilen darueber zwei Aufgaben ueberfaellig standen.
* **#974 (G26)** — "100% Profil vollstaendig" stand bedingungslos in
  der Readiness-Karte, auch in Stufen, die mit dem Profil nichts zu
  tun haben.
* **#984 (G32)** — es fehlte die Regel, die beides verhindert, und der
  leere Zustand war nirgends festgelegt.
"""
import json
import re
import subprocess
from datetime import date
from pathlib import Path

import pytest

from bewerbungs_assistent.services.daily_impulse_service import (
    CONTEXT_PRIORITY,
    detect_context,
    get_daily_impulse,
)
from bewerbungs_assistent.services.workspace_service import (
    READINESS_STUFEN,
    readiness_stufe,
)

WURZEL = Path(__file__).resolve().parents[1]

# Der Samstag aus dem Review-Screenshot.
SAMSTAG = date(2026, 9, 5)
MONTAG = date(2026, 9, 7)

LAGE = dict(
    has_profile=True,
    profile_completeness=100,
    active_sources=3,
    search_status="aktuell",
    active_jobs=5,
    total_applications=24,
)


# ── #977: der Impuls kennt die Lage ─────────────────────────────────

def test_977_samstag_mit_ueberfaelliger_aufgabe_raet_nicht_zur_ruhe():
    """Der gemeldete Fall, mit den Zahlen aus dem Screenshot."""
    assert detect_context(
        **LAGE, follow_ups_due=0, overdue_tasks=2, today=SAMSTAG
    ) == "follow_up_due"


def test_977_samstag_mit_faelliger_nachfassung_ebenso():
    assert detect_context(
        **LAGE, follow_ups_due=2, overdue_tasks=0, today=SAMSTAG
    ) == "follow_up_due"


def test_977_samstag_ohne_offenes_bleibt_ruhe():
    """Die Gegenrichtung: das Wochenende wird nicht abgeschafft."""
    assert detect_context(
        **LAGE, follow_ups_due=0, overdue_tasks=0, today=SAMSTAG
    ) == "weekend"


def test_977_werktag_ohne_offenes_bleibt_default():
    assert detect_context(
        **LAGE, follow_ups_due=0, overdue_tasks=0, today=MONTAG
    ) == "default"


def test_977_reihenfolge_ist_dokumentiert():
    """Die Liste soll die Entscheidung erklaeren, nicht ihr widersprechen."""
    assert CONTEXT_PRIORITY.index("follow_up_due") < CONTEXT_PRIORITY.index("weekend")


def test_977_ueberfaellige_aufgaben_sind_optional():
    """Alt-Aufrufer ohne das neue Argument brechen nicht."""
    assert detect_context(**LAGE, follow_ups_due=0, today=SAMSTAG) == "weekend"


RUHE_IDS = {f"impuls_{n}" for n in range(111, 121)}


def _impulse() -> list[dict]:
    pfad = (WURZEL / "src" / "bewerbungs_assistent" / "content"
            / "tagesimpulse.json")
    return json.loads(pfad.read_text(encoding="utf-8"))


def test_977_ruhesaetze_erscheinen_an_werktagen_nicht_mehr():
    """Zehn Wochenend-Saetze trugen zusaetzlich `default`.

    Damit konnte "Heute darf es stiller sein" an einem beliebigen
    Dienstag stehen, ohne dass irgendein Kontext das wollte.
    """
    for eintrag in _impulse():
        if eintrag["id"] in RUHE_IDS:
            assert eintrag["contexts"] == ["weekend"], eintrag["id"]


def test_977_werktags_pool_bleibt_gross_genug():
    """Eine Bereinigung, die den Pool leert, waere keine."""
    default = [e for e in _impulse() if "default" in e["contexts"]]
    assert len(default) >= 60, len(default)


def test_977_am_samstag_mit_offenem_kommt_kein_ruhesatz():
    """Die Wirkung, nicht nur die Regel (DoD 8c)."""
    erg = get_daily_impulse(
        enabled=True, **LAGE, follow_ups_due=0, overdue_tasks=2, today=SAMSTAG
    )
    assert erg["context"] == "follow_up_due"
    assert erg["impulse"]["id"] not in RUHE_IDS


def test_977_dashboard_reicht_die_ueberfaelligen_aufgaben_durch():
    """Ein Signal zaehlt erst, wenn es auch ankommt (DoD 8c).

    Der Impuls kannte `follow_ups_due` schon vorher — die rote Warnung
    ganz oben speiste sich aber aus `get_overdue_tasks`, und die kam nie
    im Impuls an.
    """
    quelle = (WURZEL / "src" / "bewerbungs_assistent" / "dashboard.py").read_text(
        encoding="utf-8")
    block = quelle[quelle.index("def _get_daily_impulse"):]
    block = block[:block.index("async def api_daily_impulse")]
    assert "get_overdue_tasks" in block
    assert "overdue_tasks=overdue_tasks" in block


# ── #974: Onboarding-KPI nur im Onboarding ──────────────────────────

REGELN_JS = WURZEL / "frontend" / "src" / "lib" / "dashboardRegeln.js"


def test_974_regelmodul_existiert():
    assert REGELN_JS.exists()


def test_974_dashboard_entscheidet_nicht_selbst():
    """Die KPI stand als unbedingte Zeile im JSX.

    Sie muss durch die Regel laufen, sonst entscheidet die naechste
    Ansicht wieder selbst — und entscheidet wieder mit "ja".
    """
    seite = (WURZEL / "frontend" / "src" / "pages" / "DashboardPage.jsx").read_text(
        encoding="utf-8")
    assert "zeigeProfilKpi" in seite


def _agents_md() -> str:
    """AGENTS.md mit geglaetteten Umbruechen.

    Ohne die Glaettung zerreisst ein Zeilenumbruch mitten in der Regel
    jede Phrasenpruefung — derselbe Fehler wie bei den ATS-Mustern in
    #918.
    """
    text = (WURZEL / "AGENTS.md").read_text(encoding="utf-8")
    return re.sub(r"\s+", " ", text)


def test_974_regel_steht_in_agents_md():
    text = _agents_md()
    assert "readiness.stage" in text
    assert "#974" in text


def test_974_und_984_node_kipptest_laeuft():
    """Der JS-Kipptest deckt die sieben Stufen ab; hier wird er aufgerufen.

    Ohne diesen Aufruf haengt der Beweis allein am CI-Schritt — und ein
    Schutz zaehlt erst, wenn er laeuft (DoD 8c).
    """
    ziel = REGELN_JS.with_name("dashboardRegeln.test.mjs")
    try:
        node = subprocess.run(
            ["node", str(ziel)], capture_output=True, text=True,
            cwd=str(WURZEL), timeout=60,
        )
    except (FileNotFoundError, OSError):
        pytest.skip("node nicht verfuegbar")
    assert node.returncode == 0, node.stdout + node.stderr


# ── #984: die Regel, der Waechter, der leere Zustand ────────────────

def test_984_jede_stufe_ist_im_katalog():
    """Sieben Stufen aus `build_workspace_summary`, alle greifbar."""
    erwartet = {"onboarding", "im_fluss", "profil_aufbauen",
                "quellen_aktivieren", "jobsuche_erneuern", "bewerben",
                "nachfassen"}
    assert set(READINESS_STUFEN) == erwartet


def test_984_katalog_liefert_kopien():
    """Ein Aufrufer, der `tone` ueberschreibt, darf den Katalog nicht
    umschreiben — sonst traegt die naechste Anfrage die Abweichung."""
    vorher = READINESS_STUFEN["jobsuche_erneuern"]["tone"]
    readiness_stufe("jobsuche_erneuern", tone="blue")
    assert READINESS_STUFEN["jobsuche_erneuern"]["tone"] == vorher


def _normalisiere(text: str) -> str:
    text = (text or "").lower().replace("—", "-").replace("–", "-")
    text = re.sub(r"[.,;:!?()]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@pytest.mark.parametrize("stufe", sorted(READINESS_STUFEN))
def test_984_headline_und_beschreibung_wiederholen_sich_nicht(stufe):
    """Der Waechter aus #984.

    Ehrliche Grenze, damit sie niemand nachmessen muss: der ausloesende
    Fall ("Es gibt ueberfaellige Nachfassaktionen." / "Einige Bewerbungen
    warten auf deine Rueckmeldung") teilt kein einziges Wort und kommt
    hier durch. Ihn loest G27/#976, indem das Feld verschwindet. Dieser
    Test haelt nur die grobe Wiederholung fern.
    """
    daten = READINESS_STUFEN[stufe]
    kopf = _normalisiere(daten["headline"])
    rest = _normalisiere(daten.get("description", ""))
    if not rest:
        return
    assert kopf not in rest, stufe
    assert rest not in kopf, stufe


def test_984_leerer_zustand_ist_festgelegt():
    quelle = REGELN_JS.read_text(encoding="utf-8")
    assert 'NICHTS_OFFEN = "Nichts offen"' in quelle


def test_984_zeilenregel_steht_in_agents_md():
    text = _agents_md()
    assert "Titel, Datum oder Zahl und Herkunft" in text
    assert "#984" in text


def test_984_kein_hilfetext_schalter_wird_behauptet():
    """Der Nutzer nahm an, Hilfetexte seien abschaltbar. Sie sind es
    nicht, und es wird auch keiner gebaut — dann darf es auch nirgends
    stehen."""
    treffer = []
    for pfad in (WURZEL / "frontend" / "src").rglob("*.jsx"):
        text = pfad.read_text(encoding="utf-8", errors="replace").lower()
        for muster in ("hilfetexte ausblenden", "hilfetexte anzeigen",
                       "hilfetext-schalter"):
            if muster in text:
                treffer.append(f"{pfad.name}: {muster}")
    assert not treffer, treffer
