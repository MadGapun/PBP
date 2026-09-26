"""Sichtbare Texte der Oberflaeche pruefen — G66 (#1087 E1, E2).

Zwei Regeln, beide gegen das, was ein Mensch im Dashboard liest:

1. **Echte Umlaute.** Ein Wort mit "ae/oe/ue" als Umschrift ist ein
   Fund, ausser es steht in `ECHTE_WOERTER` (neue, aktuell, Quelle ...).
   Bis v1.7.133 stand "HEUTE FÜR DICH" neben "Uebungsgespraech" auf
   demselben Bildschirm.
2. **Ein Wort je Begriff.** Woerter aus `GLOSSAR_VERBOTEN` sind ein Fund
   (Follow-up statt Nachfassen, Todo statt Aufgabe, Docs statt
   Dokumente ...).

Gelesen werden JSX-Textknoten und Zeichenketten-Literale in den
Oberflaechen-Dateien sowie Titel und Beschreibung im Prompt-Katalog.
Code, Pfade, CSS-Klassen und Kommentare zaehlen nicht.

Aufruf: ``python scripts/ui_texte_pruefen.py`` — Exit 1 bei Funden.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
FRONTEND = REPO / "frontend" / "src"

# Woerter, in denen ae/oe/ue KEIN umschriebener Umlaut ist.
ECHTE_WOERTER = {
    "neu", "neue", "neuen", "neuer", "neues", "neuem", "erneut", "erneute", "erneuten",
    "aktuell", "aktuelle", "aktuellen", "aktueller", "aktuelles", "manuell", "manuelle",
    "manuellen", "manueller", "individuell", "individuelle", "individuellen", "eventuell",
    "virtuell", "virtuelle", "virtuellen", "quelle", "quellen", "quellenauswahl",
    "quellenliste", "quellenname", "quellenwahl", "dauer", "dauert", "dauerhaft",
    "genauer", "genaue", "genauen", "steuer", "steuern", "steuert", "gesteuert",
    "bauen", "baue", "gebaut", "treue", "abenteuer", "frequenz", "sequenz",
    "konsequenz", "konsequent", "konsequenzen", "queue", "blue", "true", "value",
    "issue", "issues", "continue", "michael", "israel", "poesie", "duell", "duelle",
    "feuer", "teuer", "teure", "teuren", "ungeheuer", "zuerst", "trauen", "vertrauen",
    "vertrauen", "schauen", "anschauen", "angeschaut", "schaue", "genau", "grauen",
    "frauen", "bauer", "mauer", "trauer", "sauer", "ueberhaupt_false", "bequem",
    "quer", "bequeme", "aquarell", "tuer", "rueckfall_false", "baueinheit",
    "reue", "freuen", "freue", "freut", "erfreut", "erfreulich", "betreuen", "betreut",
    "betreuung", "betreuer", "scheuen", "gebrauen", "euer", "eure", "euren", "heuer",
    "gebaeude_false", "requests", "request", "guest", "question", "questions",
    "unique", "league", "venue", "revenue", "avenue", "statue", "vue", "cue",
    "clue", "glue", "due", "sue", "tuesday", "hue", "argue", "aerobic", "aero",
    "coe", "joe", "shoe", "toe", "does", "goes", "heroes", "canoe", "oboe",
    "fraeulein_false", "boeing", "phoenix", "noel", "aeon", "raphael", "gael",
    "mae", "sundae", "reggae", "israeli", "kafkaesque", "ueberraschung_false",
    "zuerst", "abgebaut", "aufgebaut", "ausgebaut", "eingebaut", "umgebaut",
    "anbauen", "aufbauen", "ausbauen", "einbauen", "umbauen", "abbauen",
    "gefreut", "vertraut", "vertraute", "misstrauen", "stauen", "gestaut",
    "kauen", "hauen", "klauen", "tauen", "abschauen", "reinschauen",
    "nachschauen", "vorschauen", "durchschauen", "zuschauen", "zuschauer",
    "queere", "queer", "suez", "muenchen_false",
    # Eigennamen und Schrift in Backend-Texten (G73)
    "segoe", "poetisch", "schaeffler",
}

# Ein Wort je Begriff (Glossar). Links das verbotene Wort (klein), rechts
# das Wort, das stattdessen gilt — fuer die Meldung.
GLOSSAR_VERBOTEN = {
    "follow-up": "Nachfassen", "follow-ups": "Nachfassungen", "followup": "Nachfassen",
    "nachfass": "Nachfassen", "nachfässe": "Nachfassungen", "nachfaesse": "Nachfassungen",
    "nachfassaktion": "Nachfassung", "nachfassaktionen": "Nachfassungen",
    "todo": "Aufgabe", "todos": "Aufgaben", "to-do": "Aufgabe",
    "docs": "Dokumente",
    "hiring manager": "Fachvorgesetzte/r", "interviewer": "Gesprächspartner/in",
}

# Produktname: gross geschrieben ist er ein Name. Klein und mit Bindestrich
# ist "bewerbungs-assistent" der technische Name des MCP-Servers und des
# Datenordners — der bleibt.
GLOSSAR_NAME = {
    "Bewerbungs-Assistent": "PBP", "Bewerbungsassistent": "PBP",
    "Bewerbungs-Begleiter": "PBP", "Bewerbungs-Pilot": "PBP",
}

# Schreibweisen mit ss statt ß, die im UI vorkamen.
SCHREIBWEISE = {"schliessen": "Schließen", "groesse": "Größe", "grösse": "Größe"}

UI_DATEIEN = sorted(
    list((FRONTEND / "pages").glob("*.jsx"))
    + list((FRONTEND / "components").glob("*.jsx"))
    + [FRONTEND / "App.jsx", FRONTEND / "utils.js"]
    + list((FRONTEND / "lib").glob("*.js"))
)

_KOMMENTAR_BLOCK = re.compile(r"/\*.*?\*/", re.S)
_KOMMENTAR_ZEILE = re.compile(r"(^|[^:\"'`\\])//[^\n]*")
_LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"|`((?:[^`\\]|\\.)*)`')
_TEXTKNOTEN = re.compile(r">([^<>{}]+)<")
_WORT = re.compile(r"[A-Za-zÄÖÜäöüß][A-Za-zÄÖÜäöüß-]*")


def _ohne_kommentare(text: str) -> str:
    text = _KOMMENTAR_BLOCK.sub(lambda m: "\n" * m.group(0).count("\n"), text)
    return _KOMMENTAR_ZEILE.sub(lambda m: m.group(1), text)


def _sieht_aus_wie_text(s: str) -> bool:
    """Prosa statt Code: ein Leerzeichen und kein typisches Code-Zeichen."""
    s = s.strip()
    if not s or " " not in s:
        # Einzelwoerter nur, wenn sie gross beginnen (Beschriftungen).
        return bool(re.fullmatch(r"[A-ZÄÖÜ][a-zäöüß-]{2,}", s))
    if any(z in s for z in ("=>", "&&", "||", "===", "className", "px-", "text-", "bg-",
                            "border-", "rounded", "flex ", "grid ", "/api/", "${")):
        return "${" in s and not any(z in s for z in ("=>", "&&", "px-", "text-", "bg-"))
    return True


def texte(pfad: Path):
    """(zeile, text) je sichtbarem Textstueck."""
    roh = pfad.read_text(encoding="utf-8-sig")
    code = _ohne_kommentare(roh)
    for m in _TEXTKNOTEN.finditer(code):
        t = m.group(1)
        if _sieht_aus_wie_text(t) and not any(z in t for z in ("&&", "=>", "?.", "===")):
            yield code[:m.start()].count("\n") + 1, t
    for m in _LITERAL.finditer(code):
        t = m.group(1) if m.group(1) is not None else m.group(2)
        if t and _sieht_aus_wie_text(t):
            yield code[:m.start()].count("\n") + 1, t


def katalog_texte():
    pfad = REPO / "src" / "bewerbungs_assistent" / "services" / "prompt_katalog.py"
    roh = pfad.read_text(encoding="utf-8")
    for m in re.finditer(r'"(titel|beschreibung|gruppe)":\s*"((?:[^"\\]|\\.)*)"', roh):
        yield pfad, roh[:m.start()].count("\n") + 1, m.group(2)


# ── Backend-Texte, die das Dashboard zeigt (G73) ─────────────────────
#
# Bis v1.7.137 las der Pruefer nur das Frontend. Tagesimpuls, Elwosa,
# Hinweise, Quellenbeschreibungen, Meldungen der Endpunkte und die
# Faktoren im Fit-Dialog kommen aber vom Server — dort stand
# "Nachfassen ist kein Stoeren" neben "HEUTE FÜR DICH".
BACKEND = REPO / "src" / "bewerbungs_assistent"
BACKEND_DATEIEN = [BACKEND / p for p in (
    "services/elwosa_lines.py", "services/elwosa.py", "services/elwosa_provider.py",
    "services/onboarding_hints.py", "services/workspace_service.py",
    "services/datenguete.py", "services/rahmen.py", "services/punkte.py",
    "services/schwellen_stufen.py", "services/schwellen_verteilung.py",
    "services/score_verteilung.py", "services/statistik_erweitert.py",
    "services/loeschbereiche.py", "services/deinstallation.py", "services/ablage.py",
    "services/ollama_start.py", "services/components.py", "services/quellen_meldung.py",
    "services/schwellen_umstellung.py", "services/status_rueckweg.py",
    "services/papierkorb.py", "services/stellen_nach_quelle.py",
    "services/quellen_texte.py", "services/menue.py", "services/dashboard_bereiche.py",
    "dashboard.py", "job_scraper/__init__.py",
)]
# Die ganze Datei ist Anzeige (Linienpool) — auch kleingeschriebene Texte.
BACKEND_NUR_ANZEIGE = {"elwosa_lines.py"}
TAGESIMPULSE = BACKEND / "content" / "tagesimpulse.json"

# Kein Anzeigetext: SQL, Shell-Zeilen fuer Skripte.
_KEIN_TEXT = re.compile(r"^\s*(SELECT|UPDATE|INSERT|DELETE|CREATE|ALTER|WITH|PRAGMA)\b"
                        r"|\bFROM\b|\bWHERE\b|\bCASE WHEN\b|\becho\b")
# Aufrufe, deren Zeichenketten Muster, Schluessel oder Protokoll sind.
_KEIN_TEXT_AUFRUF = {"execute", "executemany", "compile", "sub", "search", "match",
                     "findall", "fullmatch", "split", "get_setting", "set_setting",
                     "get_profile_setting", "set_profile_setting", "startswith", "endswith"}


def _uebersprungene_knoten(baum) -> set:
    """Docstrings, Protokoll, Muster, Einstellungsschluessel, Dict-Schluessel
    und Vergleiche. Kleingeschriebene Wortlisten (Suchmuster fuer Mails
    und Anzeigen) fallen ueber die Grossbuchstaben-Regel weg — sie
    vergleichen Text von aussen und muessen beide Schreibweisen kennen."""
    skip = set()
    for n in ast.walk(baum):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)) \
                and n.body and isinstance(n.body[0], ast.Expr) \
                and isinstance(n.body[0].value, ast.Constant):
            skip.add(id(n.body[0].value))
        if isinstance(n, ast.Call):
            f = n.func
            name = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
            besitzer = f.value.id if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) else ""
            if besitzer in ("logger", "log", "logging", "re") or name in _KEIN_TEXT_AUFRUF:
                skip.update(id(s) for s in ast.walk(n) if s is not n.func)
        if isinstance(n, ast.Dict):
            skip.update(id(k) for k in n.keys if k is not None)
        if isinstance(n, ast.Compare):
            skip.update(id(s) for s in ast.walk(n))
    return skip


def backend_texte():
    """(pfad, zeile, text) je Anzeigetext im Backend."""
    for pfad in BACKEND_DATEIEN:
        baum = ast.parse(pfad.read_text(encoding="utf-8-sig"))
        skip = _uebersprungene_knoten(baum)
        alle = pfad.name in BACKEND_NUR_ANZEIGE
        for n in ast.walk(baum):
            if not (isinstance(n, ast.Constant) and isinstance(n.value, str)) or id(n) in skip:
                continue
            t = n.value
            if " " not in t or _KEIN_TEXT.search(t):
                continue
            if not alle and not (re.search(r"[A-ZÄÖÜ]", t) and _sieht_aus_wie_text(t)):
                continue
            yield pfad, n.lineno, t
    for nr, eintrag in enumerate(json.loads(TAGESIMPULSE.read_text(encoding="utf-8")), 1):
        yield TAGESIMPULSE, nr, eintrag["text"]


def ist_umschrift(wort: str) -> bool:
    """Steht in diesem Wort ein umschriebener Umlaut?

    Kein Fund: Woerter aus `ECHTE_WOERTER`, Bezeichner (camelCase,
    GROSS), und "ue"/"ae"/"oe" direkt nach einem Vokal oder nach "q"
    (dauern, neueste, Steuer, Quelle) — dort ist es keiner.
    """
    klein = wort.lower()
    if klein in ECHTE_WOERTER:
        return False
    if (wort.isupper() and len(wort) > 1) or re.search(r"[a-zäöü][A-ZÄÖÜ]", wort):
        return False
    for m in re.finditer(r"(?=(ae|oe|ue))", klein):
        i = m.start()
        vor = klein[i - 1] if i > 0 else ""
        if vor and vor in "aeiouq":
            continue
        if i + 2 > len(klein):
            continue
        return True
    return False


def umlaut_funde(text: str):
    text = re.sub(r"\$\{[^}]*\}", " ", text)
    for m in _WORT.finditer(text):
        wort = m.group(0)
        # Ein Parametername in einem Prompt (`begruendung=`, `stelle_x`)
        # ist ein Bezeichner, kein Text — er MUSS in Umschrift bleiben.
        nach = text[m.end():m.end() + 1]
        vor = text[m.start() - 1:m.start()] if m.start() else ""
        if nach in ("=", "_", "(") or vor in ("_", "."):
            continue
        teile = [t for t in wort.split("-") if t]
        if any(ist_umschrift(t) for t in teile):
            yield wort


def glossar_funde(text: str):
    klein = text.lower()
    for verboten, statt in {**GLOSSAR_VERBOTEN, **SCHREIBWEISE}.items():
        if re.search(r"(?<![\w-])" + re.escape(verboten) + r"(?![\w-])", klein):
            yield verboten, statt
    for verboten, statt in GLOSSAR_NAME.items():
        if re.search(r"(?<![\w-])" + re.escape(verboten) + r"(?![\w-])", text):
            yield verboten, statt


def pruefen():
    funde = []
    quellen = [(p, z, t) for p in UI_DATEIEN for z, t in texte(p)] + list(katalog_texte())
    backend = set()
    for eintrag in backend_texte():
        quellen.append(eintrag)
        backend.add(id(eintrag[2]))
    for pfad, zeile, text in quellen:
        name = pfad.relative_to(REPO).as_posix()
        ist_backend = id(text) in backend
        text = re.sub(r"\$\{[^}]*\}", " ", text)
        for wort in umlaut_funde(text):
            funde.append(f"{name}:{zeile}: Umschrift '{wort}' — echter Umlaut")
        if ist_backend:
            # Das Glossar gilt fuer die Oberflaeche; Backend-Texte nennen
            # Werkzeugnamen und Server-Begriffe, die bleiben.
            continue
        for verboten, statt in glossar_funde(text):
            funde.append(f"{name}:{zeile}: '{verboten}' — Glossar: {statt}")
    return funde


def main() -> int:
    funde = pruefen()
    for f in funde:
        print(f)
    print(f"{len(funde)} Funde")
    return 1 if funde else 0


if __name__ == "__main__":
    sys.exit(main())
