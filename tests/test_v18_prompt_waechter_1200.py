"""#1200 A12 — der Prompt-Waechter liest jede Stelle, an der ein Text fuer Claude entsteht.

H23 (`test_g1087_prompt_signaturen_h23.py`) prueft Parameternamen in
`tools/*.py` und `prompts.py`. Der zweite Anwender-Review (#1200) fand
drei Luecken, durch die falsche Anweisungen gruen blieben:

1. **Unbekannte Werkzeuge** wurden uebersprungen (`if name not in sig:
   continue`). Ein Prompt, der ein Werkzeug nennt, das es nicht gibt,
   fiel nie auf.
2. **Pflichtparameter** wurden nicht geprueft:
   `stilarchiv_speichern(kind="cv")` ohne `content` lief bei jedem
   Lebenslauf ins Leere.
3. **Quellen fehlten:** `dashboard.py` (LinkedIn, Sammel-Analyse),
   `document_analysis_prompts.py` (Einzel-Dokument), `services/*` und
   die Texte im Frontend. In `dashboard.py` stand
   `dokumente_batch_analysieren(dokument_ids=...)` — den Parameter gibt
   es nicht.

Docstrings und SQL zaehlen fuer die Namenspruefung nicht: sie sind
Entwicklerdokumentation bzw. Datenbanksprache, keine Anweisung an Claude.
"""
import ast
import asyncio
import importlib
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

import pytest


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))
PAKET = _repo() / "src" / "bewerbungs_assistent"
FRONTEND = _repo() / "frontend" / "src"

#: Werkzeuge anderer Server, die PBP-Texte bewusst nennen (Claude in Chrome).
FREMDE_WERKZEUGE = frozenset({
    "javascript_tool", "get_page_text", "read_page", "tabs_create", "tabs_context",
})
#: Namen mit Klammer, die keine Anweisung an Claude sind — mit Begruendung.
KEINE_ANWEISUNG = {
    "is_scanned_pdf": "Protokollzeile in services/ocr_service.py",
}

AUFRUF = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\(")
SQL = re.compile(r"\b(SELECT|PRAGMA|UPDATE|INSERT|CREATE|DELETE)\b")


# ---------------------------------------------------------------- Quellen

def _python_quellen() -> list[Path]:
    return ([PAKET / "prompts.py", PAKET / "document_analysis_prompts.py", PAKET / "dashboard.py"]
            + sorted((PAKET / "tools").glob("*.py"))
            + sorted((PAKET / "services").glob("*.py")))


def _literale(datei: Path, mit_doku: bool) -> str:
    baum = ast.parse(datei.read_text(encoding="utf-8-sig"))
    doku, in_fstring = set(), set()
    teile = []
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and knoten.body:
            erst = knoten.body[0]
            if isinstance(erst, ast.Expr) and isinstance(erst.value, ast.Constant) \
                    and isinstance(erst.value.value, str):
                doku.add(id(erst.value))
        if isinstance(knoten, ast.JoinedStr):
            # Ein f-String als EIN Text; eingesetzte Werte als <wert>.
            stuecke = []
            for v in knoten.values:
                in_fstring.add(id(v))
                stuecke.append(v.value if isinstance(v, ast.Constant) else "<wert>")
            teile.append("".join(stuecke))
    teile += [k.value for k in ast.walk(baum)
              if isinstance(k, ast.Constant) and isinstance(k.value, str)
              and id(k) not in in_fstring and (mit_doku or id(k) not in doku)]
    teile = [s for s in teile if not SQL.search(s)]
    # Trenner: eine Klammer, die erst in der naechsten Zeichenkette zugeht,
    # wird nicht gelesen (wie in H23).
    return "\x00".join(teile)


def _frontend_texte() -> dict:
    texte = {}
    for datei in sorted(FRONTEND.rglob("*.js*")):
        if ".test." in datei.name:
            continue
        roh = datei.read_text(encoding="utf-8")
        roh = re.sub(r"/\*.*?\*/", " ", roh, flags=re.S)
        roh = re.sub(r"(?<![:\\])//[^\n]*", " ", roh)
        # "a " + "b" bzw. `a ` + `b`: zusammengesetzte Texte als einer
        roh = re.sub(r"[\"'`]\s*\+\s*[\"'`]", "", roh)
        texte["frontend/" + datei.relative_to(FRONTEND).as_posix()] = roh
    return texte


def quell_texte(mit_doku: bool = False) -> dict:
    texte = {f"quelle:{d.relative_to(PAKET).as_posix()}": _literale(d, mit_doku)
             for d in _python_quellen()}
    texte.update(_frontend_texte())
    return texte


# ---------------------------------------------------------------- Pruefungen

def _klammer(text: str, start: int) -> str | None:
    tiefe, j = 0, start
    while j < len(text):
        if text[j] == "\x00":
            return None
        if text[j] == "(":
            tiefe += 1
        elif text[j] == ")":
            tiefe -= 1
            if tiefe == 0:
                return text[start + 1:j]
        j += 1
    return None


def _argumente(inhalt: str) -> list[str]:
    """Teilt auf oberster Ebene an Kommas; Klammern und Anfuehrungszeichen schuetzen."""
    teile, tiefe, puffer, quote = [], 0, "", ""
    for z in inhalt:
        if quote:
            puffer += z
            if z == quote:
                quote = ""
            continue
        if z in "'\"`":
            quote = z
        elif z in "([{<":
            tiefe += 1
        elif z in ")]}>":
            tiefe -= 1
        if z == "," and tiefe == 0:
            teile.append(puffer.strip())
            puffer = ""
        else:
            puffer += z
    if puffer.strip():
        teile.append(puffer.strip())
    return teile


def _ist_kennung(param: str) -> bool:
    """IDs und Hashes: die nennt eine Kurzform wie `stelle_bearbeiten(url=...)`
    nicht — das Objekt ergibt sich aus dem Zusammenhang."""
    return param.endswith(("_id", "_hash"))


def _schluessel(teil: str) -> str | None:
    m = re.match(r"^([a-z_][a-z0-9_]*)\s*=(?!=)", teil)
    return m.group(1) if m else None


def pruefe(schema: dict, texte: dict) -> dict:
    """Liefert {'unbekannt': [...], 'falsch': [...], 'pflicht_fehlt': [...]}."""
    befunde = {"unbekannt": [], "falsch": [], "pflicht_fehlt": []}
    for herkunft, text in texte.items():
        for treffer in AUFRUF.finditer(text):
            name = treffer.group(1)
            if name not in schema:
                if name not in FREMDE_WERKZEUGE and name not in KEINE_ANWEISUNG:
                    befunde["unbekannt"].append(f"{herkunft}: {name}(")
                continue
            inhalt = _klammer(text, treffer.end() - 1)
            if inhalt is None or not inhalt.strip():
                continue  # Erwaehnung wie `bewerbung_details()` — kein Aufruf mit Werten
            teile = _argumente(inhalt)
            eigen = schema[name]["props"]
            genannt = {s for s in (_schluessel(t) for t in teile) if s}
            falsch = genannt - set(eigen)
            if falsch:
                befunde["falsch"].append(f"{herkunft}: {name}({', '.join(sorted(falsch))}=)")
            if any(t.strip() in ("...", "…") for t in teile):
                continue  # ausdruecklich offen: "und weitere"
            positionell = [t for t in teile if not _schluessel(t)]
            gedeckt = genannt | set(eigen[:len(positionell)])
            fehlt = [p for p in schema[name]["pflicht"] if p not in gedeckt
                     and not (_ist_kennung(p) and not positionell)]
            if fehlt:
                befunde["pflicht_fehlt"].append(f"{herkunft}: {name}(...) ohne {', '.join(fehlt)}")
    return befunde


# ---------------------------------------------------------------- Umgebung

@pytest.fixture(scope="module")
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1200_a12_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    app_id = db.add_application({"title": "Sachbearbeitung Einkauf",
                                 "company": "Musterbetrieb GmbH", "status": "beworben"})
    mcp = _srv_mod.mcp
    beispiel = {"stelle": "Sachbearbeitung Einkauf", "firma": "Musterbetrieb GmbH",
                "bewerbung_id": app_id, "gefunden_seit": "2026-10-01", "beschreibung": "x",
                "text": "x", "beobachtung": "x", "minuten": 30}

    async def _sammeln():
        schema = {}
        for t in await mcp.list_tools():
            p = t.parameters or {}
            schema[t.name] = {"props": list(p.get("properties", {})),
                              "pflicht": list(p.get("required", []))}
        texte = {}
        for prompt in await mcp.list_prompts():
            obj = await mcp.get_prompt(prompt.name)
            namen = {a.name for a in (getattr(obj, "arguments", None) or [])}
            for variante, args in (("leer", {}),
                                   ("mit", {k: v for k, v in beispiel.items() if k in namen})):
                r = await obj.render(args)
                texte[f"prompt:{prompt.name}:{variante}"] = "".join(
                    getattr(m.content, "text", str(m.content)) for m in r.messages)
        return schema, texte

    schema, texte = asyncio.run(_sammeln())
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    for name, fn in _prompt_registry(db).items():
        texte[f"registry:{name}"] = fn()
    texte["registry:bewerbung_schreiben:mit"] = _prompt_registry(db)["bewerbung_schreiben"](
        stelle="Sachbearbeitung", firma="Musterbetrieb GmbH", bewerbung_id=app_id)
    from bewerbungs_assistent import document_analysis_prompts as dap
    for key in dap.TEMPLATES:
        for mit_app in (False, True):
            dok = {"id": "DOC-1", "filename": "brief.pdf", "doc_type": "sonstiges",
                   "extracted_text": "x"}
            if mit_app:
                dok.update(app_company="Musterbetrieb GmbH", app_title="Einkauf")
            texte[f"dokument:{key}:{mit_app}"] = dap.build_prompt(dok, key)["prompt"]
    yield schema, texte
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


# ---------------------------------------------------------------- Tests

def test_a12_gerenderte_prompts_nennen_nur_echte_werkzeuge(umgebung):
    schema, texte = umgebung
    b = pruefe(schema, texte)
    assert not b["unbekannt"], "Werkzeuge, die es nicht gibt:\n" + "\n".join(b["unbekannt"])
    assert not b["falsch"], "Parameter, die es nicht gibt:\n" + "\n".join(b["falsch"])
    assert not b["pflicht_fehlt"], "Pflichtparameter fehlen:\n" + "\n".join(b["pflicht_fehlt"])


def test_a12_quellen_nennen_nur_echte_werkzeuge(umgebung):
    schema, _ = umgebung
    b = pruefe(schema, quell_texte())
    assert not b["unbekannt"], "Werkzeuge, die es nicht gibt:\n" + "\n".join(b["unbekannt"])
    assert not b["falsch"], "Parameter, die es nicht gibt:\n" + "\n".join(b["falsch"])
    assert not b["pflicht_fehlt"], "Pflichtparameter fehlen:\n" + "\n".join(b["pflicht_fehlt"])


def test_a12_parameter_auch_in_docstrings(umgebung):
    """Docstrings landen im Werkzeugkatalog — ein falscher Parametername dort fuehrt Claude genauso."""
    schema, _ = umgebung
    b = pruefe(schema, quell_texte(mit_doku=True))
    assert not b["falsch"], "Parameter, die es nicht gibt:\n" + "\n".join(b["falsch"])


def test_a12_der_waechter_liest_alle_quellen():
    """Ein Schutz zaehlt erst, wenn er aufgerufen wird (CLAUDE.md 8c)."""
    texte = quell_texte()
    for pflicht in ("quelle:dashboard.py", "quelle:document_analysis_prompts.py",
                    "quelle:prompts.py", "quelle:tools/workflows.py",
                    "quelle:services/nachfass_text.py"):
        assert pflicht in texte and texte[pflicht], pflicht
    assert sum(k.startswith("frontend/") for k in texte) >= 20
    assert "kontakt_bearbeiten(" in texte["quelle:dashboard.py"], "LinkedIn-Text nicht gelesen"


def test_a12_ausnahmen_gibt_es_noch():
    """Eine Ausnahme fuer einen Namen, den niemand mehr nennt, ist toter Freibrief."""
    alle = "\n".join(quell_texte().values())
    for name in KEINE_ANWEISUNG:
        assert f"{name}(" in alle, f"Ausnahme {name} ist verwaist"


@pytest.mark.parametrize("text, art", [
    ('stilarchiv_speichern(kind="cv")', "pflicht_fehlt"),
    ("profil_erstellen(plz='12345', city='Musterstadt')", "pflicht_fehlt"),
    ("kontakt_verknuepfen('CON-1', ziel_typ='job')", "pflicht_fehlt"),
    ("dokumente_batch_analysieren(dokument_ids=[1, 2])", "falsch"),
    ("kontakt_aktualisieren(kontakt_id='CON-1', firma='X')", "unbekannt"),
    ("bewerbung_status_aendern(bewerbung_id, 'abgelehnt', rejection_reason='x')", "falsch"),
])
def test_a12_gegenprobe_der_waechter_findet_die_alten_faelle(umgebung, text, art):
    schema, _ = umgebung
    assert pruefe(schema, {"probe": text})[art], f"{art} nicht erkannt: {text}"


@pytest.mark.parametrize("text", [
    "bewerbung_details()",
    "bewerbung_bearbeiten(applied_at='2026-10-01')",
    "nachfass_planen(bewerbung_id, tage=7)",
    "kontakt_bearbeiten(kontakt_id='CON-1', ...)",
    "meeting_hinzufuegen(bewerbung_id=..., datum='2026-10-20 10:00', typ='interview')",
])
def test_a12_gegenprobe_richtige_aufrufe_bleiben_still(umgebung, text):
    schema, _ = umgebung
    assert not any(pruefe(schema, {"probe": text}).values()), text
