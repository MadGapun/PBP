"""Welle 7 aus #1087 — heller Modus und Barrierefreiheit (G71).

Die Regeln hier sind Guards ueber das ganze Frontend: eine einzelne
Stelle zu reparieren haelt nicht, solange die naechste Seite dieselbe
Bauform wieder einbaut.
"""
import re
from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


FRONTEND = _repo() / "frontend" / "src"


def _lesen(pfad: Path) -> str:
    return pfad.read_text(encoding="utf-8-sig")


def _quellen(endungen=(".jsx", ".js")):
    for p in sorted(FRONTEND.rglob("*")):
        if p.suffix in endungen and not p.name.endswith(".test.mjs"):
            yield p


def _ohne_kommentare(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


# ── Hilfen fuer JSX-Tags ────────────────────────────────────────────────

def _tag_ende(t: str, i: int):
    tiefe = 0
    in_str = None
    j = i
    while j < len(t):
        c = t[j]
        if in_str:
            if c == in_str:
                in_str = None
        elif c in "\"'`" and tiefe == 0:
            in_str = c
        elif c == "{":
            tiefe += 1
        elif c == "}":
            tiefe -= 1
        elif c == ">" and tiefe == 0:
            return j + 1, t[j - 1] == "/"
        j += 1
    return None, False


def symbolknoepfe_ohne_namen(text: str) -> list[int]:
    """Knoepfe, deren Inhalt nur Symbole sind und die keinen Namen tragen."""
    funde = []
    for m in re.finditer(r"<(button|Button)\b", text):
        name = m.group(1)
        ende, selbst = _tag_ende(text, m.end())
        if ende is None or selbst:
            continue
        kopf = text[m.start():ende]
        schluss = text.find(f"</{name}>", ende)
        if schluss < 0:
            continue
        inhalt = text[ende:schluss]
        if f"<{name}" in inhalt:
            continue
        rest = re.sub(r"\{/\*.*?\*/\}", "", inhalt, flags=re.S)
        if "<MitClaude" in rest:
            continue
        rest = re.sub(r"<[A-Z][A-Za-z.]*\b[^<>]*?/>", "", rest, flags=re.S)
        rest = re.sub(r"<svg\b.*?</svg>", "", rest, flags=re.S)
        if rest.strip() or "aria-label" in kopf:
            continue
        funde.append(text[:m.start()].count("\n") + 1)
    return funde


# ══ Kontrast und Schriftgroesse ═══════════════════════════════════════

def test_g71_lesefarben_haben_volle_deckkraft():
    funde = []
    for p in _quellen():
        for m in re.finditer(r"\b(?:[a-z-]+:)*text-(muted|teal|amber|coral|sky)/\d+\b|placeholder-muted/\d+",
                             _lesen(p)):
            funde.append(f"{p.name}: {m.group(0)}")
    assert not funde, funde[:20]


def test_g71_schrift_mindestens_12px_ausser_badge():
    funde = []
    for p in _quellen():
        text = _lesen(p)
        for m in re.finditer(r"text-\[(?:9|10|11)(?:\.\d+)?px\]", text):
            zeile = text[text.rfind("\n", 0, m.start()) + 1:text.find("\n", m.end())]
            if p.name == "ui.jsx" and "inline-flex items-center rounded-lg border px-2.5 py-0.5" in zeile:
                continue  # Badge
            funde.append(f"{p.name}:{text[:m.start()].count(chr(10)) + 1}")
    assert not funde, funde[:20]


def test_g71_kontrast_node_test_laeuft_in_der_ci():
    ci = (_repo() / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    assert "node frontend/src/lib/kontrast.test.mjs" in ci


# ══ Farb-Tokens statt fester Flaechen ═════════════════════════════════

def test_g71_keine_festen_dunklen_flaechen():
    funde = []
    for p in _quellen():
        text = _ohne_kommentare(_lesen(p))
        for muster in (r"rgba\(\s*30,\s*34,\s*52", r"#1a1d23", r"--surface-1\b", r"rgba\(\s*255,\s*255,\s*255"):
            if re.search(muster, text):
                funde.append(f"{p.name}: {muster}")
    assert not funde, funde


def test_g71_weiss_ist_eine_ueberlagerung():
    cfg = _lesen(_repo() / "frontend" / "tailwind.config.js")
    assert 'white: "rgb(var(--surface-overlay-soft) / <alpha-value>)",' in cfg
    css = _lesen(FRONTEND / "styles.css")
    hell = css[css.index('[data-theme="light"]'):]
    assert "--surface-overlay-soft: 20 24 40;" in hell


# ══ Dialoge, Hinweise, Knoepfe ═════════════════════════════════════════

def test_g71_dialog_semantik_und_fokusfalle():
    ui = _lesen(FRONTEND / "components" / "ui.jsx")
    modal = ui[ui.index("export function Modal("):ui.index("export function ToastViewport(")]
    for teil in ('role="dialog"', 'aria-modal="true"', "aria-labelledby={titelId}",
                 "useDialogFokus(dialogRef, open, schliessenVersuchen)", "<h2 id={titelId}"):
        assert teil in modal, teil
    fokus = ui[ui.index("export function useDialogFokus("):ui.index("export function Modal(")]
    for teil in ('event.key === "Escape"', 'event.key !== "Tab"', "vorher.focus()",
                 "offeneDialoge[offeneDialoge.length - 1] !== kennung"):
        assert teil in fokus, teil


def test_g71_jede_ueberlagerung_ist_ein_dialog():
    funde = []
    for p in _quellen((".jsx",)):
        text = _lesen(p)
        for m in re.finditer(r'className="[^"]*\bfixed inset-0\b', text):
            if p.name == "ui.jsx":
                continue  # Modal selbst
            danach = text[m.start():m.start() + 1500]
            if 'role="dialog"' not in danach:
                funde.append(f"{p.name}:{text[:m.start()].count(chr(10)) + 1}")
    assert not funde, funde
    for datei in ("components/ProfileOnboarding.jsx", "pages/TasksPage.jsx"):
        assert "useDialogFokus(" in _lesen(FRONTEND / datei), datei


def test_g71_hinweise_werden_vorgelesen():
    ui = _lesen(FRONTEND / "components" / "ui.jsx")
    toast = ui[ui.index("export function ToastViewport("):]
    assert 'aria-live="polite"' in toast
    assert 'role="status"' in toast


def test_g71_symbolknoepfe_haben_einen_namen():
    funde = []
    for p in _quellen((".jsx",)):
        funde += [f"{p.name}:{z}" for z in symbolknoepfe_ohne_namen(_lesen(p))]
    assert not funde, funde


def test_g71_der_knopf_guard_sieht_etwas():
    """DoD 8c: ein Knopf nur mit Symbol faellt auf, einer mit Namen nicht."""
    assert symbolknoepfe_ohne_namen('<button type="button"><X size={14} /></button>') == [1]
    assert symbolknoepfe_ohne_namen('<button aria-label="Zu"><X size={14} /></button>') == []
    assert symbolknoepfe_ohne_namen("<button><X size={14} /> Schließen</button>") == []


def test_g71_aktionen_nicht_nur_beim_ueberfahren():
    funde = []
    for p in _quellen((".jsx",)):
        for m in re.finditer(r"(?:opacity-0|invisible)[^\"]*group-hover:(?:opacity-100|visible)", _lesen(p)):
            funde.append(f"{p.name}: {m.group(0)[:60]}")
    assert not funde, funde


# ══ Auswahlfeld mit Tastatur, Suche auf dem Handy ══════════════════════

def test_g71_auswahlfeld_mit_tastatur():
    ui = _lesen(FRONTEND / "components" / "ui.jsx")
    select = ui[ui.index("export function SelectInput("):ui.index("export function CheckboxInput(")]
    for teil in ('role="combobox"', 'role="listbox"', 'role="option"', "aria-activedescendant",
                 "onKeyDown={taste}", '"ArrowDown"', '"ArrowUp"', '"Home"', '"End"', '"Escape"'):
        assert teil in select, teil


def test_g71_suche_auf_dem_handy():
    app = _lesen(FRONTEND / "App.jsx")
    suche = app[app.index("function GlobalSearch("):app.index("function PromptsTab(")]
    assert "data-suche-mobil" in suche and "md:hidden" in suche
    assert 'className="relative shrink-0 hidden md:block"' not in suche
    assert 'aria-label="Suchen"' in suche


# ══ Gueltige Varianten ════════════════════════════════════════════════

def _erlaubt():
    ui = _lesen(FRONTEND / "components" / "ui.jsx")

    def keys(start):
        a = ui.index(start)
        b = ui.index("};", a)
        return set(re.findall(r"^\s+([a-z_]+):", ui[a:b], re.M))
    stil, groesse, ton = keys("const BUTTON_STYLES"), keys("const BUTTON_SIZES"), keys("const toneClasses")
    return {("Button", "variant"): stil, ("Button", "size"): groesse,
            ("LinkButton", "variant"): stil, ("LinkButton", "size"): groesse,
            ("Badge", "tone"): ton}


def ungueltige_varianten(text: str, erlaubt: dict) -> list[str]:
    props = {"Button": {"variant", "size"}, "LinkButton": {"variant", "size"}, "Badge": {"tone"}}
    funde = []
    for m in re.finditer(r"<(Button|LinkButton|Badge)\b", text):
        ende, _ = _tag_ende(text, m.end())
        kopf = text[m.start():ende]
        for attr, wert in re.findall(r'\b(tone|variant|size)="([^"]*)"', kopf):
            if attr not in props[m.group(1)] or wert not in erlaubt.get((m.group(1), attr), set()):
                funde.append(f"<{m.group(1)} {attr}={wert}>")
    return funde


def test_g71_nur_gueltige_varianten():
    erlaubt = _erlaubt()
    assert {"primary", "secondary", "ghost", "danger"} <= erlaubt[("Button", "variant")]
    funde = []
    for p in _quellen((".jsx",)):
        funde += [f"{p.name}: {f}" for f in ungueltige_varianten(_lesen(p), erlaubt)]
    assert not funde, funde


def test_g71_der_varianten_guard_sieht_etwas():
    erlaubt = _erlaubt()
    assert ungueltige_varianten('<Button size="xs">', erlaubt)
    assert ungueltige_varianten('<Badge tone="subtle">', erlaubt)
    assert not ungueltige_varianten('<Button size="sm" variant="ghost">', erlaubt)


# ══ L13 — Anwender-Doku ohne Widersprueche ════════════════════════════

def _readme(name="README.md") -> str:
    return (_repo() / name).read_text(encoding="utf-8")


def test_l13_version_und_zahlen_an_einer_stelle():
    readme = _readme()
    assert "## Roadmap" not in readme and "## Changelog" not in readme
    assert "github.com/MadGapun/PBP/releases" in readme
    # Die Testzahl steht nur im Kopf (Zeile und Plakette), die der
    # Release-Check pflegt — nirgends sonst.
    assert len(re.findall(r"\d[\d.]* automatische Tests", readme)) == 1
    blick = readme[readme.index("## Auf einen Blick"):readme.index("###", readme.index("## Auf einen Blick"))]
    for wort in ("Tests", "Schema", "Modulen", "MCP-Tools"):
        assert wort not in blick, wort
    # Keine Versionsnummer als Etikett eines Features.
    kopf_ende = readme.index("## So funktioniert PBP")
    assert not re.search(r"\(neu in v1\.\d|\(v1\.\d+\.\d+\)", readme[kopf_ende:])


def test_l13_englische_fassung_ohne_eigene_zahlen():
    en = _readme("README.en.md")
    assert not re.search(r"\*\*\d+ MCP tools\*\*|\*\*\d+ configured job sources\*\*|\*\*\d+ automated tests\*\*", en)
    assert "Version **v1." not in en
    assert "releases/latest" in en


def test_l13_datenschutz_praezise():
    readme = _readme()
    assert "Deine Daten bleiben auf deinem Rechner." not in readme
    assert "Gespeichert wird lokal auf deinem Rechner; was du mit Claude bearbeitest, geht an Anthropic." in readme
    en = _readme("README.en.md")
    assert "is sent to Anthropic" in en


def test_l13_einstieg_ohne_portalnamen():
    readme = _readme()
    kopf = readme[:readme.index("## Auf einen Blick")]
    for portal in ("Kimeta", "Hays", "StepStone", "Indeed", "LinkedIn", "XING"):
        assert portal not in kopf, portal


def test_g71_leerer_bereich_zeigt_keinen_griff():
    bereich = _lesen(FRONTEND / "components" / "DashboardBereich.jsx")
    assert '<section className="dashboard-bereich min-w-0">' in bereich
    css = _lesen(FRONTEND / "styles.css")
    assert ".dashboard-bereich:not(:has(> :nth-child(2))) {\n  display: none;" in css


def test_g71_einordnung_mit_umlauten():
    """Die Texte der Profil-Einordnung erscheinen im Dashboard."""
    from bewerbungs_assistent.services import berufsfeld
    texte = list(berufsfeld.NIVEAUS.values()) + list(berufsfeld.FORMEN.values())
    texte += [f["name"] for f in berufsfeld.FELDER.values()]
    texte += [f["bereich"] for f in berufsfeld.FELDER.values()]
    umschrift = re.compile(r"(?i)taetig|kaufmaenn|gebaeude|selbststaendig|faehig|moeglich")
    assert not [t for t in texte if umschrift.search(t)]
    from bewerbungs_assistent.services import profile_classifier
    quelle = _lesen(Path(profile_classifier.__file__))
    assert "abwaehlen ist jederzeit" not in quelle and "Faehigkeiten enthaelt" not in quelle
