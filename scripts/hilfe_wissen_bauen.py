"""Die Wissensbasis der interaktiven Hilfe bauen (#1233, F51).

Die Hilfe antwortet nur aus eigenen Texten. Dieses Skript schneidet sie beim Release in Abschnitte:

* die eingebaute Hilfe (`frontend/src/lib/hilfe.js`: Hilfe je Seite, Haeufige Fragen, Probleme, Melden),
* ausgewaehlte Anwenderseiten des Wikis (eigenes Repository, ein Clone daneben),
* den Prompt-Katalog (`services/prompt_katalog.py`).

Jeder Abschnitt traegt Titel, Quelle, Text und, wo es passt, ein Ziel IN der App (Seite oder Reiter der
Einstellungen), eine Wiki-Seite mit Anker und einen Prompt aus dem Katalog. Ziele und Prompts kommen nur aus
den geprueften Listen (`PAGE_IDS`, `SETTINGS_REITER`, Prompt-Katalog), nie aus freiem Text.

Aufruf (Repo-Wurzel):

    python scripts/hilfe_wissen_bauen.py --wiki D:/.../PBP.wiki          # schreibt content/hilfe_wissen.json
    python scripts/hilfe_wissen_bauen.py --wiki D:/.../PBP.wiki --pruefen  # Exit 1, wenn die Datei veraltet ist

`release_check.py` ruft die Pruefung auf, sobald ein Wiki-Clone gefunden wird (Umgebungsvariable `PBP_WIKI_DIR`
oder der Ordner `PBP.wiki` neben dem Repository). Ohne Clone (zum Beispiel auf der CI) prueft ein Test nur die
Quellen im Repository: Hilfe, Reiter, Seiten und Prompt-Katalog.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import unicodedata
from datetime import date
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
AUSGABE = WURZEL / "src" / "bewerbungs_assistent" / "content" / "hilfe_wissen.json"
FORMAT = 1

#: Obergrenze fuer den Text eines Abschnitts (Suche, Karte und Modell lesen ihn; die Karte kuerzt zur Anzeige selbst).
MAX_TEXT = 2800
MIN_ABSCHNITT = 60

#: Wie die Seiten der App heissen (ein Test haelt die Schluessel gegen `PAGE_IDS`).
SEITEN_NAMEN = {
    "dashboard": "Dashboard", "profil": "Profil", "suche": "Suche & Bewertung", "dokumente": "Dokumente",
    "stellen": "Stellen", "bewerbungen": "Bewerbungen", "kontakte": "Kontakte", "aufgaben": "Aufgaben",
    "kalender": "Kalender", "statistiken": "Statistiken", "einstellungen": "Einstellungen",
}

#: Wiki-Seite -> Ziel in der App. Jede Seite des Wikis steht hier ODER in WIKI_AUSGESCHLOSSEN (ein Test haelt
#: beides gegen den Clone: eine neue Seite zwingt zu einer Entscheidung).
WIKI_SEITEN: dict[str, dict | None] = {
    "Erste-Schritte": None,
    "Installation": None,
    "FAQ": None,
    "Workflows": None,
    "Tab-Dashboard": {"art": "seite", "id": "dashboard"},
    "Dashboard": {"art": "seite", "id": "dashboard"},
    "Tab-Profil": {"art": "seite", "id": "profil"},
    "Profil-aus-Dokumenten": {"art": "seite", "id": "profil"},
    "Tab-Dokumente": {"art": "seite", "id": "dokumente"},
    "Tab-Stellen": {"art": "seite", "id": "stellen"},
    "Stellen-Qualitaet": {"art": "seite", "id": "stellen"},
    "Tab-Bewerbungen": {"art": "seite", "id": "bewerbungen"},
    "Tab-Kontakte": {"art": "seite", "id": "kontakte"},
    "Tab-Aufgaben": {"art": "seite", "id": "aufgaben"},
    "Tab-Kalender": {"art": "seite", "id": "kalender"},
    "Tab-Statistiken": {"art": "seite", "id": "statistiken"},
    "Tab-Einstellungen": {"art": "seite", "id": "einstellungen"},
    "Suchkriterien": {"art": "seite", "id": "suche"},
    "Scoring": {"art": "seite", "id": "suche"},
    "Jobportale": {"art": "einstellung", "id": "quellen"},
    "Lokale-KI": {"art": "einstellung", "id": "ai"},
    "Elwosa": {"art": "einstellung", "id": "ai"},
    "Lern-System": {"art": "einstellung", "id": "ai"},
    # 1.8.0
    "Firmen": {"art": "seite", "id": "bewerbungen"},
    "Mail-Ordner": {"art": "einstellung", "id": "quellen_details"},
    "Speicher-und-Downloads": {"art": "einstellung", "id": "speicher"},
    "Updates": {"art": "einstellung", "id": "updates"},
    "Wege-durch-PBP": None,
}

#: Entwickler-, Plan- und Pflegeseiten: kein Wissen fuer Anwender.
WIKI_AUSGESCHLOSSEN = (
    "Home", "Architektur", "Plugins", "Profile-Cluster", "Wiki-Pflege", "MCP-Tools",
    "Master-Plan", "Master-Plan-Optimierung", "_Sidebar",
)
WIKI_AUSGESCHLOSSEN_PRAEFIX = ("Plan-", "Roadmap")

#: Abschnitte der Anwenderseiten, die Entwicklerwissen sind (Namen von Funktionen, Stufen eines Umbaus, Messprotokolle):
#: sie wuerden bei einer Frage des Alltags nach oben rutschen und nichts erklaeren.
WIKI_ABSCHNITT_AUSSCHLUSS = tuple(re.compile(m, re.I) for m in (
    r"^`", r"\(\)", r"^Verwandte (Tools|Issues)", r"^MCP-Tools", r"Schema v\d", r"^Stufe \d", r"Sprach-DNA", r"Trigger-Klassen",
    r"Tonfall-Modi", r"Frequenz-Drosselung", r"Markup in Linien", r"^Platzhalter", r"MCP-Bridge", r"Wiki-Snippets", r"^Genus und",
    r"Lern-System-Integration", r"Health-Stand", r"Nachmessung", r"^Nachgemessen", r"^Defekte Quellen", r"Warum das so lange",
    r"^Hard-Guard", r"^Inhaltsverzeichnis", r"Profil-Cluster-spezifische", r"^Warum der Score reproduzierbar", r"Eine Quelle fuer Slash",
    r"Aufrufe in Prompts sind geprueft", r"^Auto-Engine", r"^Workflow vs\. Tool", r"AdaptiveHintBanner", r"^Recap-Card",
    # Entwicklerteile der Seiten von 1.8.0 und das Quellenverzeichnis (nennt einen Vermittler in Grossschreibung; die Quellen
    # stehen in den Einstellungen).
    r"[Ff]ür Entwickler", r"^Datenmodell", r"^Tech & Engineering$",
))


# ── Quellen aus dem Repository ──────────────────────────────────────────────────────────────

def _node_json(ausdruck_js: str) -> dict:
    """Fuehrt ein kleines ES-Modul-Programm aus und liest dessen JSON-Ausgabe."""
    r = subprocess.run(["node", "--input-type=module", "-e", ausdruck_js], capture_output=True, text=True,
                       encoding="utf-8", cwd=str(WURZEL), check=False)
    if r.returncode != 0:
        raise RuntimeError(f"node ist gescheitert: {r.stderr.strip()[:400]}")
    return json.loads(r.stdout)


def hilfe_quellen() -> dict:
    """Hilfe, Haeufige Fragen, Probleme, Melden, Reiter und Seiten aus dem Frontend."""
    lib = (WURZEL / "frontend" / "src").as_uri()
    js = f"""
    import {{ HILFE, FAQ, PROBLEME, MELDEWEGE, MELDE_PROMPT }} from '{lib}/lib/hilfe.js';
    import {{ SETTINGS_REITER }} from '{lib}/lib/einstellungenReiter.js';
    import {{ PAGE_IDS }} from '{lib}/utils.js';
    process.stdout.write(JSON.stringify({{ HILFE, FAQ, PROBLEME, MELDEWEGE, MELDE_PROMPT, SETTINGS_REITER, PAGE_IDS }}));
    """
    return _node_json(js)


def prompt_katalog() -> list[dict]:
    sys.path.insert(0, str(WURZEL / "src"))
    from bewerbungs_assistent.services import prompt_katalog as pk  # noqa: PLC0415
    return [dict(e) for e in pk.EINTRAEGE]


# ── Text ────────────────────────────────────────────────────────────────────────────────────

_VERSION = re.compile(r"\bv\d+\.\d+(?:\.\d+)?(?:-(?:beta|rc)\.\d+)?\b", re.I)
_SATZ_ENDE = re.compile(r"(?<=[.!?:])\s+(?=[A-ZÄÖÜ„\"(])")
_CODE_MARKE = "\x01"
_VERSION_KLAMMER = re.compile(r"\s*\((?:[^()]*?\b)?v\d+\.\d+(?:\.\d+)?[^()]*\)")
_ISSUE_KLAMMER = re.compile(r"\s*\((?:[^()]*?)#\d{2,4}[^()]*\)")
_ISSUE = re.compile(r"\s*#\d{3,4}\b")
_ENTITAETEN = {"&lt;": "<", "&gt;": ">", "&amp;": "&", "&nbsp;": " ", "&quot;": '"'}


def schluessel(text: str) -> str:
    """Ein stabiler Kennungsteil: klein, ohne Umlaute, nur Buchstaben, Ziffern, Unterstrich."""
    sys.path.insert(0, str(WURZEL / "src"))
    from bewerbungs_assistent.services.hilfe_suche import umschrift  # noqa: PLC0415 - dieselbe Umschrift wie die Suche
    return re.sub(r"[^a-z0-9]+", "_", umschrift(text)).strip("_")[:60] or "x"


def ohne_versionssaetze(zeile: str) -> str:
    """Saetze mit einer Versionsnummer sind Geschichte ('Bis v1.7.139 startete ...') oder veralten ('v1.7.148 ist die aktuelle
    Version'): sie fallen weg. Fuer den Menschen zaehlt, was HEUTE gilt."""
    if not _VERSION.search(zeile):
        return zeile
    return " ".join(s for s in _SATZ_ENDE.split(zeile) if not _VERSION.search(s))


def ohne_historie(text: str) -> str:
    """Entfernt Versions- und Issue-Hinweise (`(v1.7.143, #1126)`, `#1126`, ganze Saetze mit `v1.7.139`): sie helfen beim Lesen nicht."""
    for _ in range(2):
        text = _VERSION_KLAMMER.sub("", text)
        text = _ISSUE_KLAMMER.sub("", text)
    text = _ISSUE.sub("", text)
    for a, b in _ENTITAETEN.items():
        text = text.replace(a, b)
    text = "\n".join(ohne_versionssaetze(z) for z in text.split("\n"))
    return re.sub(r"[ \t]+", " ", text).strip()


_TITEL_VERSION = re.compile(r"(?:\b(?:seit|ab|bis|in|nach|vor)\s+)?\bv\d+\.\d+(?:\.\d+)?(?:-(?:beta|rc)\.\d+)?\b:?", re.I)


def titel_ohne_historie(titel: str) -> str:
    """Eine Ueberschrift ohne Versions- und Issue-Hinweise, aber nie ohne Titel: 'Seit v1.7.124: benannte Stufen' wird 'Benannte Stufen'.

    `ohne_historie` wirft ganze Saetze mit einer Version weg - fuer eine Ueberschrift hiesse das: kein Titel mehr."""
    t = _VERSION_KLAMMER.sub("", titel)
    t = _ISSUE_KLAMMER.sub("", t)
    t = _ISSUE.sub("", t)
    t = _TITEL_VERSION.sub(" ", t)
    for a, b in _ENTITAETEN.items():
        t = t.replace(a, b)
    t = re.sub(r"\s+", " ", t).strip(" :—-,;")
    return t[:1].upper() + t[1:] if t else t


def markdown_zu_text(md: str) -> str:
    """Wiki-Markdown als schlichter Text: Bilder, Links, Betonung und Tabellenkoepfe weg, Tabellenzeilen als Zeile."""
    zeilen = []
    im_code = False
    for roh in md.replace("\r\n", "\n").split("\n"):
        z = roh.rstrip()
        if z.strip().startswith("```"):
            im_code = not im_code
            continue
        if im_code:
            if z.strip():
                zeilen.append(_CODE_MARKE + z.strip())
            continue
        if re.match(r"^\s*<!--.*-->\s*$", z):
            continue
        if re.match(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$", z):
            continue  # Trennzeile einer Tabelle
        if z.lstrip().startswith("|"):
            zellen = [c.strip() for c in z.strip().strip("|").split("|")]
            z = " — ".join(c for c in zellen if c)
        z = re.sub(r"^\s{0,3}>\s?", "", z)                     # Zitat
        z = re.sub(r"^\s*#{4,6}\s+", "", z)                    # tiefere Ueberschriften bleiben als Zeile im Abschnitt
        z = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", z)              # Bilder
        z = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", z)          # Links
        z = re.sub(r"<br\s*/?>", " ", z, flags=re.I)
        z = re.sub(r"</?[a-zA-Z][^>]*>", "", z)                 # uebrige HTML-Marken
        z = re.sub(r"\*\*([^*]+)\*\*", r"\1", z)
        z = re.sub(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])", r"\1", z)
        z = re.sub(r"`([^`]+)`", r"\1", z)
        z = re.sub(r"^\s*[-*]\s+", "- ", z)
        zeilen.append(z.strip())
    text = "\n".join(zeilen)
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text, flags=re.S).replace("**", "")   # Fettdruck auch ueber Zeilenumbrueche
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return ohne_historie_zeilen(text)


def ohne_historie_zeilen(text: str) -> str:
    """Zeile fuer Zeile: Codezeilen behalten ihren Befehl (die Version darin wird zu vX.Y.Z), alle anderen verlieren ihre Versionssaetze."""
    aus: list[str] = []
    for z in text.split("\n"):
        if z.startswith(_CODE_MARKE):
            aus.append(_VERSION.sub("vX.Y.Z", z[1:]))
            continue
        z = ohne_historie(z)
        if z or (aus and aus[-1]):
            aus.append(z)
    return re.sub(r"\n{3,}", "\n\n", "\n".join(aus)).strip()


def kuerzen(text: str, grenze: int) -> str:
    """Auf `grenze` Zeichen, am Satzende oder am Zeilenende, sonst am Wort."""
    text = text.strip()
    if len(text) <= grenze:
        return text
    stueck = text[:grenze]
    ende = max(stueck.rfind(". "), stueck.rfind("! "), stueck.rfind("? "), stueck.rfind(".\n"), stueck.rfind("\n"))
    if ende >= grenze // 2:
        return stueck[: ende + 1].strip()
    wort = stueck.rfind(" ")
    return (stueck[:wort] if wort > grenze // 2 else stueck).rstrip(",;:—-") + " …"


def wiki_anker(ueberschrift: str) -> str:
    """Der Anker, den GitHub zu einer Ueberschrift bildet: klein, ohne Satzzeichen, Leerzeichen zu Bindestrichen."""
    t = ueberschrift.strip().lower()
    t = re.sub(r"[^\w\- ]", "", t, flags=re.UNICODE)
    return t.replace(" ", "-")


# ── Ziele ───────────────────────────────────────────────────────────────────────────────────

_PFEIL = r"(?:›|>|->|→)"


def reiter_ziel(text: str, reiter: list[dict]) -> dict | None:
    """Findet im Text einen Weg wie 'Einstellungen › Erweitert › Updates' oder 'unter Datenschutz' und liefert den Reiter dazu.

    Der fruehste Treffer gilt; bei gleichem Anfang der laengere Name ('Quellen im Detail' vor 'Quellen')."""
    gefunden = None  # (Anfang, -Laenge, id)
    for r in reiter:
        label = re.escape(r["label"])
        wege = (
            rf"(?:Einstellungen|Erweitert|Grundlagen)\s*{_PFEIL}\s*(?:(?:Erweitert|Grundlagen)\s*{_PFEIL}\s*)?{label}(?![\w])",
            rf"(?<![\w])[Uu]nter\s+(?:Einstellungen\s*{_PFEIL}\s*)?(?:(?:Erweitert|Grundlagen)\s*{_PFEIL}\s*)?{label}(?![\w])",
        )
        for muster in wege:
            m = re.search(muster, text)
            if m:
                kandidat = (m.start(), -len(r["label"]), r["id"])
                if gefunden is None or kandidat < gefunden:
                    gefunden = kandidat
    return {"art": "einstellung", "id": gefunden[2]} if gefunden else None


def reiter_aus_titel(titel: str, reiter: list[dict]) -> dict | None:
    """Der Reiter, den eine Ueberschrift selbst nennt ('Updates', 'Speicher & Downloads'); der laengste Name gewinnt."""
    treffer = [r for r in reiter if re.search(rf"(?<![\w]){re.escape(r['label'])}(?![\w])", titel)]
    if not treffer:
        return None
    r = max(treffer, key=lambda x: len(x["label"]))
    return {"art": "einstellung", "id": r["id"]}


def prompt_im_text(text: str, katalog: list[dict]) -> str | None:
    """Ein Prompt, dessen Titel im Text in Anfuehrungszeichen oder fett genannt wird („Jobsuche mit Claude“)."""
    for e in katalog:
        titel = e["titel"]
        if f"„{titel}“" in text or f'"{titel}"' in text or f"'{titel}'" in text:
            return e["id"]
    return None


# ── Abschnitte ──────────────────────────────────────────────────────────────────────────────

def abschnitt(id_: str, quelle: str, titel: str, pfad: str, text: str, ziel=None, wiki=None, prompt=None) -> dict:
    return {
        "id": id_, "quelle": quelle, "titel": titel_ohne_historie(titel), "pfad": pfad,
        "text": kuerzen(text, MAX_TEXT),
        "ziel": ziel, "wiki": wiki, "prompt": prompt,
    }


def abschnitte_aus_hilfe(q: dict, katalog: list[dict]) -> list[dict]:
    reiter = q["SETTINGS_REITER"]
    aus: list[dict] = []
    for seite, inhalt in q["HILFE"].items():
        name = SEITEN_NAMEN[seite]
        for a in inhalt["abschnitte"]:
            text = ohne_historie(a["text"])
            ziel = reiter_ziel(text, reiter)
            if ziel is None and seite == "einstellungen":
                ziel = reiter_aus_titel(a["titel"], reiter)     # in der Hilfe der Einstellungen nennt der Titel den Reiter
            ziel = ziel or {"art": "seite", "id": seite}
            aus.append(abschnitt(f"hilfe:{seite}:{schluessel(a['titel'])}", "hilfe", a["titel"], f"Hilfe › {name}", text,
                                 ziel=ziel, prompt=prompt_im_text(text, katalog)))
    for f in q["FAQ"]:
        text = ohne_historie(f["a"])
        aus.append(abschnitt(f"faq:{schluessel(f['q'])}", "faq", f["q"], "Hilfe › Häufige Fragen", text,
                             ziel=reiter_ziel(text, reiter), prompt=prompt_im_text(text, katalog)))
    for p in q["PROBLEME"]:
        text = ohne_historie(p["a"])
        aus.append(abschnitt(f"problem:{schluessel(p['q'])}", "probleme", p["q"], "Hilfe › Probleme", text,
                             ziel=reiter_ziel(text, reiter), prompt=prompt_im_text(text, katalog)))
    # Melden: zwei Wege, gleichrangig (hilfe.js MELDEWEGE) und der Prompt dazu.
    wege = " ".join(f"{w['titel']}: {ohne_historie(w['text'])}" for w in q["MELDEWEGE"])
    aus.append(abschnitt("hilfe:melden:fehler_melden", "hilfe", "Fehler melden oder eine Idee vorschlagen", "Hilfe › Melden",
                         "Einen Fehler oder eine Idee meldest du über Hilfe & Support › Melden. Erst mit Claude: der Prompt „Problem "
                         "melden“ sucht zuerst eine Lösung und schreibt dann einen Bericht ohne Namen und Kontaktdaten. " + wege,
                         prompt=q["MELDE_PROMPT"]))
    return aus


def abschnitte_aus_prompts(katalog: list[dict]) -> list[dict]:
    aus = []
    for e in katalog:
        text = f"{e['titel']}: {e['beschreibung']}. Das geht mit Claude — der Prompt legt los, du fügst ihn in Claude ein."
        aus.append(abschnitt(f"prompt:{e['id']}", "prompt", e["titel"], f"Prompts › {e['kategorie']}", text, prompt=e["id"]))
    return aus


def _teile_wiki_seite(seite: str, md: str) -> list[tuple[str, str, str]]:
    """Zerlegt eine Wiki-Seite an H2/H3: (Ueberschrift, Pfad, Inhalt). Der Text vor der ersten Ueberschrift gehoert zum Seitentitel."""
    md = md.replace("\r\n", "\n").lstrip("\ufeff")
    teile: list[tuple[str, str, str]] = []
    titel_seite = seite.replace("-", " ")
    aktuell_h2 = ""
    kopf = None
    puffer: list[str] = []

    def abschliessen():
        if kopf is not None:
            teile.append((kopf[0], kopf[1], "\n".join(puffer)))

    im_code = False
    for zeile in md.split("\n"):
        # Eine Zeile mit '#' in einem Codeblock ist ein Kommentar im Befehl, keine Ueberschrift ('# Repository klonen').
        if zeile.strip().startswith("```"):
            im_code = not im_code
            if kopf is None:
                kopf, puffer = (titel_seite, titel_seite), []
            puffer.append(zeile)
            continue
        m = None if im_code else re.match(r"^(#{1,3})\s+(.*\S)\s*$", zeile)
        if m and not zeile.startswith("####"):
            ebene, text = len(m.group(1)), m.group(2)
            if ebene == 1:
                abschliessen()
                kopf, puffer = (text, titel_seite), []
                continue
            abschliessen()
            if ebene == 2:
                aktuell_h2 = text
                kopf, puffer = (text, titel_seite), []
            else:
                kopf, puffer = (text, f"{titel_seite} › {titel_ohne_historie(aktuell_h2)}" if aktuell_h2 else titel_seite), []
            continue
        if kopf is None:
            kopf, puffer = (titel_seite, titel_seite), []
        puffer.append(zeile)
    abschliessen()
    return teile


def abschnitte_aus_wiki(wiki_dir: Path, katalog: list[dict], reiter: list[dict]) -> tuple[list[dict], dict]:
    aus: list[dict] = []
    hashes: dict[str, str] = {}
    for seite, ziel_seite in WIKI_SEITEN.items():
        datei = wiki_dir / f"{seite}.md"
        if not datei.is_file():
            raise FileNotFoundError(f"Wiki-Seite fehlt: {datei}")
        roh = datei.read_bytes()
        hashes[seite] = hashlib.sha256(roh).hexdigest()[:16]
        md = roh.decode("utf-8-sig")
        zaehler: dict[str, int] = {}
        for ueberschrift, pfad, inhalt in _teile_wiki_seite(seite, md):
            if any(m.search(ueberschrift) for m in WIKI_ABSCHNITT_AUSSCHLUSS) or not titel_ohne_historie(ueberschrift):
                continue
            text = markdown_zu_text(inhalt)
            if len(text) < MIN_ABSCHNITT:
                continue
            basis = f"wiki:{seite}:{schluessel(ueberschrift)}"
            zaehler[basis] = zaehler.get(basis, 0) + 1
            id_ = basis if zaehler[basis] == 1 else f"{basis}_{zaehler[basis]}"
            ziel = reiter_ziel(text, reiter)
            if ziel is None and seite == "Tab-Einstellungen":
                ziel = reiter_aus_titel(ueberschrift, reiter)   # in den Einstellungen nennt die Ueberschrift selbst den Reiter
            ziel = ziel or ziel_seite
            aus.append(abschnitt(id_, "wiki", ueberschrift, f"Wiki › {pfad}", text, ziel=ziel,
                                 wiki={"seite": seite, "anker": wiki_anker(ueberschrift)},
                                 prompt=prompt_im_text(text, katalog)))
    return aus, hashes


# ── Zusammenbau ─────────────────────────────────────────────────────────────────────────────

def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def personendaten(abschnitte: list[dict]) -> list[str]:
    """Funde des Pruefers `scripts/scrub_pii.py` in Titel, Pfad und Text der Abschnitte (leer = sauber).

    Die Datei geht mit der Installation an jeden Anwender und steht im Repository: eine reale Firma oder Person darf nicht darin stehen."""
    sys.path.insert(0, str(WURZEL / "scripts"))
    import scrub_pii  # noqa: PLC0415
    funde: list[str] = []
    for a in abschnitte:
        for f in scrub_pii.find_pii(f"{a['titel']}\n{a['pfad']}\n{a['text']}"):
            funde.append(f"{a['id']}: {f}")
    return funde


def bauen(wiki_dir: Path, fassung: str | None = None) -> dict:
    q = hilfe_quellen()
    katalog = prompt_katalog()
    reiter = q["SETTINGS_REITER"]
    abschnitte = abschnitte_aus_hilfe(q, katalog) + abschnitte_aus_prompts(katalog)
    wiki_abschnitte, wiki_hashes = abschnitte_aus_wiki(wiki_dir, katalog, reiter)
    abschnitte += wiki_abschnitte
    ids = [a["id"] for a in abschnitte]
    doppelt = sorted({i for i in ids if ids.count(i) > 1})
    if doppelt:
        raise ValueError(f"Doppelte Abschnittskennungen: {doppelt[:5]}")
    leer = [a["id"] for a in abschnitte if not a["titel"].strip() or not a["pfad"].strip()]
    if leer:
        raise ValueError(f"Abschnitte ohne Titel oder Pfad: {leer[:5]}")
    funde = personendaten(abschnitte)
    if funde:
        raise ValueError("Personendaten in der Wissensbasis (Abschnitt: Fund) - den Abschnitt in WIKI_ABSCHNITT_AUSSCHLUSS "
                         "aufnehmen oder die Quelle bereinigen: " + "; ".join(funde[:5]))
    if fassung is None:
        m = re.search(r'^__version__\s*=\s*"([^"]+)"', (WURZEL / "src/bewerbungs_assistent/__init__.py").read_text(encoding="utf-8"), re.M)
        fassung = m.group(1) if m else ""
    return {
        "format": FORMAT,
        "fassung": fassung,
        "quellen": {
            "hilfe": _hash({k: q[k] for k in ("HILFE", "FAQ", "PROBLEME", "MELDEWEGE", "MELDE_PROMPT")}),
            "reiter": _hash(reiter),
            "seiten": _hash(q["PAGE_IDS"]),
            "prompts": _hash([{k: e[k] for k in ("id", "kategorie", "titel", "beschreibung")} for e in katalog]),
            "wiki": wiki_hashes,
        },
        "seiten": {s: SEITEN_NAMEN[s] for s in q["PAGE_IDS"]},
        "reiter": {r["id"]: {"label": r["label"], "gruppe": r["gruppe"]} for r in reiter},
        "abschnitte": abschnitte,
    }


def schreiben(daten: dict, ziel: Path, gebaut: str | None = None) -> None:
    """Eine Zeile je Abschnitt: der Unterschied zweier Staende bleibt lesbar."""
    kopf = {k: v for k, v in daten.items() if k != "abschnitte"}
    kopf["gebaut"] = gebaut or date.today().isoformat()
    zeilen = [json.dumps(a, ensure_ascii=False, separators=(",", ":")) for a in daten["abschnitte"]]
    text = ("{\n" + ",\n".join(f'"{k}":{json.dumps(v, ensure_ascii=False, separators=(",", ":"))}' for k, v in kopf.items())
            + ',\n"abschnitte":[\n' + ",\n".join(zeilen) + "\n]\n}\n")
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_bytes(text.encode("utf-8"))


def wiki_ordner(angabe: str | None) -> Path | None:
    kandidaten = [angabe, os.environ.get("PBP_WIKI_DIR"), str(WURZEL.parent / "PBP.wiki")]
    for k in kandidaten:
        if k and (Path(k) / "FAQ.md").is_file():
            return Path(k)
    return None


def pruefen(daten_neu: dict, vorhanden: Path) -> list[str]:
    """Was an der vorhandenen Datei veraltet ist (leer = aktuell). Das Baudatum zaehlt nicht."""
    if not vorhanden.is_file():
        return ["Die Wissensbasis fehlt."]
    alt = json.loads(vorhanden.read_text(encoding="utf-8"))
    probleme = []
    for k in ("hilfe", "reiter", "seiten", "prompts"):
        if alt.get("quellen", {}).get(k) != daten_neu["quellen"][k]:
            probleme.append(f"Quelle '{k}' hat sich geändert")
    wiki_alt, wiki_neu = alt.get("quellen", {}).get("wiki", {}), daten_neu["quellen"]["wiki"]
    for seite in sorted(set(wiki_alt) | set(wiki_neu)):
        if wiki_alt.get(seite) != wiki_neu.get(seite):
            probleme.append(f"Wiki-Seite '{seite}' hat sich geändert")
    if alt.get("abschnitte") != daten_neu["abschnitte"]:
        probleme.append("Die Abschnitte stimmen nicht mehr mit den Quellen überein")
    return probleme


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--wiki", help="Ordner mit dem Clone des Wikis (sonst PBP_WIKI_DIR oder ../PBP.wiki)")
    p.add_argument("--ausgabe", default=str(AUSGABE))
    p.add_argument("--pruefen", action="store_true", help="nichts schreiben; Exit 1, wenn die Datei veraltet ist")
    a = p.parse_args()
    wiki = wiki_ordner(a.wiki)
    if wiki is None:
        print("Kein Wiki-Clone gefunden (--wiki, PBP_WIKI_DIR oder ../PBP.wiki).", file=sys.stderr)
        return 2
    daten = bauen(wiki)
    ziel = Path(a.ausgabe)
    if a.pruefen:
        probleme = pruefen(daten, ziel)
        for z in probleme:
            print("VERALTET:", z)
        print(f"{len(daten['abschnitte'])} Abschnitte aus den Quellen; Datei {'aktuell' if not probleme else 'VERALTET'}.")
        return 1 if probleme else 0
    schreiben(daten, ziel)
    print(f"{len(daten['abschnitte'])} Abschnitte -> {ziel} ({ziel.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
