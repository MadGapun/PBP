"""Regressionstest fuer v1.7.17 — #907: Sidebar-Hoehenkette.

Jobsuche-Badge und Elwosa-Header scrollten mit dem Chat weg, weil (a)
der Scroll-Container eine Ebene zu weit aussen sass und (b) der innere
Scroller mit maxHeight:100% gegen ein height:auto-Elternteil wirkungslos
war. Ein CSS-Layout laesst sich ohne Browser nicht rendern — dieser Test
verankert die STRUKTUR-Invarianten der Loesung in den Quelldateien
(dasselbe Muster wie der jobLink-Paritaets-Check aus #765).
"""
from pathlib import Path

FRONTEND = Path(__file__).resolve().parents[1] / "frontend" / "src"


def _lese(rel):
    return (FRONTEND / rel).read_text(encoding="utf-8")


def test_907_elwosa_scroller_hat_echte_hoehe():
    src = _lese("components/ElwosaSidebarChat.jsx")
    assert 'maxHeight: "100%"' not in src, \
        "maxHeight:100% gegen height:auto ist unaufloesbar — der Scroller scrollt dann nie (#907)"
    assert "min-h-[80px]" not in src
    assert 'className="h-full space-y-2 overflow-y-auto pr-1"' in src, \
        "die Nachrichtenliste ist DER eine Scroll-Container"
    assert 'className="relative flex-1 min-h-0"' in src, \
        "der Wrapper muss die Flex-Hoehe binden, sonst haengt der 'X neu'-Button am Inhaltsende"


def test_907_elwosa_wurzel_ist_flex_column_mit_fixem_header():
    src = _lese("components/ElwosaSidebarChat.jsx")
    assert "flex min-h-0 flex-col" in src, \
        "Wurzel muss die Hoehe aus dem Footer-Slot weiterreichen"
    assert "mb-2 flex shrink-0 items-center justify-between" in src, \
        "der Elwosa-Header (Avatar, Zahnrad, Auge, ...) bleibt stehen"


def test_907_sidebar_footer_scrollt_nicht_selbst():
    src = _lese("components/Sidebar.jsx")
    assert "border-t border-white/8 flex flex-col overflow-hidden" in src, \
        "der Footer-Slot darf nicht selbst scrollen — sonst wandert das Badge weg"
    assert 'maxHeight: "calc(100vh - 180px)"' not in src, \
        "die 180px-Magic-Number ist mit der Flex-Kette obsolet (#907)"


def test_907_footerslot_reicht_hoehe_durch():
    src = _lese("App.jsx")
    assert 'className="flex h-full min-h-0 flex-col"' in src
    assert 'className="flex-1 min-h-0"' in src, \
        "ElwosaSidebarChat muss den flexiblen Rest bekommen"
    assert 'className="shrink-0 px-3 pt-2"' in src, \
        "JobsucheStatusBadge bleibt fix ueber dem Chat"
