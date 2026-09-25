"""H23 (#1087 G3) — Prompt-Aufrufe und Werkzeugnamen gegen die echten Signaturen.

`dokumente_verarbeiten` wies Claude an, `bewerbung_status_aendern(...,
rejection_reason=...)` aufzurufen (der Parameter heisst `ablehnungsgrund`)
und `meeting_hinzufuegen(application_id, datum, modus, beschreibung)` —
die Signatur lautet `(bewerbung_id, datum, typ, platform, ort, titel)`.
Dazu nannten zwei Werkzeugantworten Werkzeuge mit Umlaut im Namen
(`dokument_verknüpfen`, `position_hinzufügen`), die es so nicht gibt.
Ausgerechnet Absage und Termin, die wichtigsten Schritte im Verlauf.

#1000 hatte genau diese Pruefung — fuer EINEN Prompt und EIN Werkzeug.
Dieser Guard dehnt sie aus: jeder gerenderte Prompt, jeder Registry-Text
und jede Zeichenkette in den Werkzeugmodulen, gegen die Registrierung.
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


def prompt_text(ergebnis) -> str:
    nachrichten = getattr(ergebnis, "messages", ergebnis)
    teile = []
    for nachricht in nachrichten:
        inhalt = getattr(nachricht, "content", nachricht)
        teile.append(inhalt if isinstance(inhalt, str) else getattr(inhalt, "text", str(inhalt)))
    return "".join(teile)


@pytest.fixture(scope="module")
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_h23_")
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
    db.add_document({"filename": "absage.eml", "doc_type": "korrespondenz",
                     "extracted_text": "Sehr geehrte Damen und Herren, leider ...",
                     "extraction_status": "nicht_extrahiert",
                     "linked_application_id": app_id})
    mcp = _srv_mod.mcp

    async def _sammeln():
        tools = await mcp.list_tools()
        sig = {}
        for t in tools:
            props = (t.parameters or {}).get("properties", {})
            sig[t.name] = set(props)
        if hasattr(mcp, "get_prompts"):
            namen = list((await mcp.get_prompts()).keys())
        else:
            namen = [p.name for p in await mcp.list_prompts()]
        texte = {}
        for name in namen:
            prompt = await mcp.get_prompt(name)
            texte[f"prompt:{name}"] = prompt_text(await prompt.render({}))
        return sig, texte

    sig, texte = asyncio.run(_sammeln())
    from bewerbungs_assistent.tools.workflows import _prompt_registry
    for name, fn in _prompt_registry(db).items():
        texte[f"registry:{name}"] = fn()
    yield sig, texte
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _literale() -> dict:
    """Alle Zeichenketten der Werkzeugmodule und Prompts (auch f-Strings)."""
    texte = {}
    dateien = list((PAKET / "tools").glob("*.py")) + [PAKET / "prompts.py"]
    for datei in dateien:
        baum = ast.parse(datei.read_text(encoding="utf-8-sig"))
        teile = []
        for knoten in ast.walk(baum):
            if isinstance(knoten, ast.Constant) and isinstance(knoten.value, str):
                teile.append(knoten.value)
        # Trenner, den `_klammer` als Ende versteht: eine Klammer, die in
        # EINER Zeichenkette aufgeht und erst in der naechsten zugeht
        # (`"...(batch_nr=" + str(n) + ")"`), wird nicht gelesen.
        texte[f"quelle:{datei.name}"] = "\x00".join(teile)
    return texte


AUFRUF = re.compile(r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)+)\(")


def _klammer(text: str, start: int) -> str:
    tiefe, j = 0, start
    while j < len(text):
        if text[j] == "\x00":
            return ""
        if text[j] == "(":
            tiefe += 1
        elif text[j] == ")":
            tiefe -= 1
            if tiefe == 0:
                return text[start + 1:j]
        j += 1
    return text[start + 1:start + 400]


def _schluesselwoerter(argumente: str) -> set:
    """Nur `name=` auf oberster Ebene der Klammer — `a=b` in einem
    verschachtelten Aufruf gehoert zu dem."""
    ergebnis, tiefe, puffer = set(), 0, ""
    for zeichen in argumente:
        if zeichen in "([{":
            tiefe += 1
        elif zeichen in ")]}":
            tiefe -= 1
        if tiefe == 0:
            puffer += zeichen
        else:
            puffer += " "
    for treffer in re.finditer(r"(?<![\w.=!<>])([a-z_][a-z0-9_]*)\s*=(?!=)", puffer):
        ergebnis.add(treffer.group(1))
    return ergebnis


def falsche_parameter(sig: dict, texte: dict) -> list:
    befunde = []
    for herkunft, text in texte.items():
        for treffer in AUFRUF.finditer(text):
            name = treffer.group(1)
            if name not in sig:
                continue
            genannt = _schluesselwoerter(_klammer(text, treffer.end() - 1))
            falsch = genannt - sig[name]
            if falsch:
                befunde.append(f"{herkunft}: {name}({', '.join(sorted(falsch))}=)")
    return befunde


def test_h23_prompts_nennen_nur_echte_parameter(umgebung):
    sig, texte = umgebung
    befunde = falsche_parameter(sig, texte)
    assert not befunde, "Aufrufe mit Parametern, die es nicht gibt:\n" + "\n".join(befunde)


def test_h23_werkzeugquellen_nennen_nur_echte_parameter(umgebung):
    sig, _ = umgebung
    befunde = falsche_parameter(sig, _literale())
    assert not befunde, "Aufrufe mit Parametern, die es nicht gibt:\n" + "\n".join(befunde)


def test_h23_kein_werkzeugname_mit_umlaut():
    """Werkzeugnamen sind ASCII (#1062: ein Umlaut im Namen macht ein
    Werkzeug fuer die API ungueltig). Ein Name mit Umlaut in einer
    Antwort zeigt also auf ein Werkzeug, das es nicht gibt."""
    muster = re.compile(r"\b[a-z]+_[a-z_]*[äöüß][a-z_äöüß]*(?=\(|\"|\b)")
    befunde = []
    for herkunft, text in _literale().items():
        for treffer in muster.finditer(text):
            wort = treffer.group(0)
            if "_" in wort:
                befunde.append(f"{herkunft}: {wort}")
    assert not befunde, befunde


def test_h23_tool_verweise_in_antworten_sind_registriert(umgebung):
    """`{"tool": "..."}` in Folgeaktionen muss ein echtes Werkzeug sein."""
    sig, _ = umgebung
    befunde = []
    for datei in (PAKET / "tools").glob("*.py"):
        text = datei.read_text(encoding="utf-8-sig")
        for treffer in re.finditer(r'"tool":\s*"([a-z_0-9]+)"', text):
            if treffer.group(1) not in sig:
                befunde.append(f"{datei.name}: {treffer.group(1)}")
    assert not befunde, befunde


def test_h23_der_gemeldete_prompt_ist_korrigiert(umgebung):
    _, texte = umgebung
    text = texte["prompt:dokumente_verarbeiten"]
    assert "rejection_reason" not in text
    assert "ablehnungsgrund=" in text
    assert "erledigt_unklar" not in text
    assert "event_at" not in text
    assert "meeting_hinzufuegen(bewerbung_id=" in text


def test_h23_guard_faengt_einen_falschen_parameter(umgebung):
    """Gegenprobe im Test selbst: der Guard muss den alten Fall finden."""
    sig, _ = umgebung
    alt = {"x": 'bewerbung_status_aendern(bewerbung_id, "abgelehnt", rejection_reason="...")'}
    assert falsche_parameter(sig, alt), "Guard erkennt den Gruendungsfall nicht"
