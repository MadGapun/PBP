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


def test_1254_die_antworten_der_hilfe_haben_keinen_eigenen_scroller():
    """#1254: das Zielbild aus #907 gilt weiter - EIN Scroll-Container. #1233 hatte mit `max-h-[38vh] overflow-y-auto` einen zweiten eingefuehrt,
    der dem Elwosa-Verlauf die Hoehe nahm. Am gerenderten Bild prueft das `test_v18_hilfe_frage_browser_1233.py` (Zahl der Bereiche, Hoehe des
    Verlaufs); dieser Test faengt die Rueckkehr schon im Quelltext ab."""
    hilfe = _lese("components/HilfeFrage.jsx")
    for verboten in ("overflow-y", "overflow-auto", "max-h-"):
        assert verboten not in hilfe, f"die Hilfe bekommt keinen eigenen Scroller zurueck ({verboten})"
    leiste = _lese("components/ElwosaSidebarChat.jsx")
    assert leiste.count("overflow-y-auto") == 1, "die Seitenleiste hat genau EINEN Bereich zum Scrollen"
    assert leiste.index("<HilfeAntwort") < leiste.index("<HilfeEingabe"), \
        "die Antworten stehen im Strom (im Bereich des Verlaufs), das Feld darunter"
    assert "<HilfeVerlauf" not in leiste, "der Verlauf des Dialogs gehoert nicht in die Seitenleiste"


def test_1256_der_strom_zaehlt_nach_kennung_und_beobachtet_seine_hoehe():
    """#1256: zwei Maengel im Mitscrollen (#611). Am gerenderten Bild pruefen es die `test_1256_*` in `test_v18_hilfe_frage_browser_1233.py`; dieser Test faengt
    die Rueckkehr der alten Rechnung schon im Quelltext ab: die Zahl der Nachrichten taugt nicht zum Zaehlen (der Verlauf holt nur zehn), und ein Merkmal aus
    einem Scroll-Ereignis allein veraltet, wenn sich die Hoehe aendert oder die Daten vor dem Ereignis eintreffen."""
    leiste = _lese("components/ElwosaSidebarChat.jsx")
    assert "lastMessageCountRef" not in leiste, "die Marke zaehlt wieder die Nachrichten der Liste statt der neuen Kennungen"
    assert "neueNachrichten(letzteKennung.current, messages)" in leiste
    assert "new ResizeObserver" in leiste, "der Bereich beobachtet seine Hoehe nicht mehr"
    assert "ref={listeRef}" in leiste
    assert "warAmEnde.current = scrollRef.current ? stehtAmEnde(scrollRef.current) : null" in leiste, \
        "ob der Mensch am Ende steht, wird nicht mehr beim Eintreffen der Daten gemessen"
    assert "stickyRef" not in leiste, "ein Merker aus einem Scroll-Ereignis allein veraltet: entschieden wird nach der Geometrie von jetzt"
    assert "key={activeProfileId" in _lese("App.jsx"), "nach einem Profilwechsel beginnt die Seitenleiste nicht neu: die Kennungen laufen ueber alle Profile"
