"""Beispiele fuer die lokale KI - nach Aehnlichkeit statt nach Datum (#1396).

Bis 1.8.6 zeigte der Prompt der Auto-Aussortierung die zehn zuletzt vom Menschen
aussortierten Stellen: ohne Bezug zur Stelle, die gerade bewertet wird, und nur
Ablehnungen. Hier kommen die 5 bis 8 entschiedenen Stellen, die der aktuellen
am AEHNLICHSTEN sind (Titel, Fachbegriffe), gemischt aus "passt" und "passt
nicht":

* nur Entscheidungen von Mensch und Claude (`ki_lernen.entscheidungsklasse`);
  AUTOMATISCHE Entscheidungen (KI, Regeln) und Unbekanntes sind nie ein Beispiel
  (#1239, #1395) - sonst lernt das Modell von sich selbst;
* Gewicht: Claude-Urteil mit Begruendung vor Mensch mit Grund vor Mensch ohne
  Grund; eine bekannte Fehleinschaetzung der KI (`ollama_lag_richtig=0`) zuerst;
* Kurzform: Titel, zwei bis drei Kernanforderungen, Entscheidung, Grund, ein Satz;
* die Stelle selbst ist nie ihr eigenes Beispiel (die Gegenprobe ist BLIND).

Ganze Woerter (Wortgrenzen, L5), keine Teilstrings: "ki" steckt in "Kita".
"""
from __future__ import annotations

import logging
import math
import re

logger = logging.getLogger("bewerbungs_assistent.ki_beispiele")

#: Obergrenze der Beispiele je Prompt und der Zeilenlaenge (der Prompt soll kurz bleiben).
STANDARD_ANZAHL = 8
ZEILE_MAX = 330
#: Wie viele entschiedene Stellen je Lauf als Vergleichsmenge geladen werden.
POOL_MAX = 2500

_STOPP = frozenset("""
und oder der die das den dem des ein eine einen einer eines fuer mit von bei zur zum
als auch aus nach ueber unter sie wir ihr ihre ihren sich ist sind wird werden sein
oder m w d mwd gmbh ag kg mbh co deutschland stelle job jobs suche gesucht bereich
team unser unsere unserem unseren dich dir uns und/oder in im am an auf the and for
""".split())

_UMLAUTE = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})
_WORT = re.compile(r"[a-z0-9][a-z0-9+#.]{2,}")


def stamm_menge(text) -> set:
    """Die Woerter eines Textes als Staemme (die ersten sechs Zeichen).

    So treffen sich "Konstruktionsleiter" und "Konstruktion", ohne dass ein
    kurzes Wort in einem langen steckt: verglichen werden ganze Woerter."""
    ergebnis = set()
    for w in _WORT.findall(str(text or "").lower().translate(_UMLAUTE)):
        w = w.strip(".")
        if len(w) < 3 or w in _STOPP:
            continue
        ergebnis.add(w[:6])
    return ergebnis


def aehnlichkeit(titel_a: set, text_a: set, titel_b: set, text_b: set) -> float:
    """Titel zaehlt dreifach, die Fachbegriffe der Anzeige einfach (Kosinus-aehnlich)."""
    def _mass(a: set, b: set) -> float:
        if not a or not b:
            return 0.0
        return len(a & b) / math.sqrt(len(a) * len(b))
    return 3.0 * _mass(titel_a, titel_b) + _mass(text_a, text_b)


_KOPF = re.compile(
    r"(anforderung|dein profil|ihr profil|qualifikation|das bringst|was du mitbringst|"
    r"was sie mitbringen|wir erwarten|voraussetzung|ihre kompetenz|dein background)",
    re.IGNORECASE)


def kern_anforderungen(text, n: int = 3, laenge: int = 70) -> list:
    """Zwei bis drei Kernanforderungen aus der Anzeige (leer, wenn nichts Klares dasteht)."""
    zeilen = [z.strip(" \t-*•·–") for z in str(text or "").splitlines()]
    treffer = []
    drin = False
    for z in zeilen:
        if not z:
            continue
        if _KOPF.search(z) and len(z) < 80:
            drin = True
            rest = z.split(":", 1)[1].strip() if ":" in z else ""
            if rest:
                treffer.append(rest)
            continue
        if drin:
            if len(z) < 25 and z.endswith(":"):  # naechste Ueberschrift
                break
            treffer.append(z)
        if len(treffer) >= n:
            break
    if not treffer:  # Fliesstext mit "Anforderungen: a, b, c"
        m = re.search(r"(?:anforderungen|erwarten wir|bringst du mit)\s*:\s*([^\n]+)",
                      str(text or ""), re.IGNORECASE)
        if m:
            treffer = [t.strip() for t in re.split(r"[;,]", m.group(1)) if t.strip()]
    kurz = []
    for t in treffer[:n]:
        t = re.sub(r"\s+", " ", t).strip(" .;,")
        if t:
            kurz.append(t[:laenge].rstrip())
    return kurz


def _satz(text, laenge: int = 160) -> str:
    t = re.sub(r"\s+", " ", str(text or "")).strip()
    if not t:
        return ""
    ende = re.search(r"[.!?](\s|$)", t)
    if ende and ende.end() <= laenge:
        t = t[:ende.end()].strip()
    return t[:laenge].rstrip()


def pool_laden(db, max_pool: int = POOL_MAX) -> list:
    """Alle Stellen mit einer belastbaren Entscheidung von Mensch oder Claude.

    Einmal je Lauf laden und weitergeben, nie je Stelle."""
    from .ablehnungsgruende import (
        SYSTEM_GRUENDE, abgeschaltete_gruende, gruende_aus_wert, ist_urteil,
        urteilsgruende_des_menschen)
    from .ki_lernen import AUTO_NOTIZ, entscheidungsklasse

    aus = abgeschaltete_gruende(db)
    conn = db.connect()
    pid = db.get_active_profile_id()
    zeilen = conn.execute(
        "SELECT hash, title, description, is_active, dismiss_reason, dismiss_note, "
        "dismissed_by, entschieden_von, zurueckgeholt_am, analyse_urteil, analyse_begruendung, "
        "ollama_lag_richtig, updated_at FROM jobs "
        "WHERE (profile_id=? OR profile_id IS NULL) "
        "AND entschieden_von IN ('mensch','claude') "
        "ORDER BY CASE WHEN ollama_lag_richtig=0 THEN 0 ELSE 1 END, updated_at DESC "
        "LIMIT ?", (pid, int(max_pool))).fetchall()
    pool = []
    for z in zeilen:
        klasse = entscheidungsklasse(z)
        if not klasse:
            continue
        if (klasse == "passt_nicht" and z["entschieden_von"] == "mensch"):
            # EINE Frage, eine Funktion (#1239): was zaehlt als Urteil des
            # Menschen, entscheidet `urteilsgruende_des_menschen` - auch dann,
            # wenn der Marker etwas anderes sagt (Altbestand ohne Herkunft).
            gruende = urteilsgruende_des_menschen(z["dismissed_by"], z["dismiss_reason"])
        else:
            gruende = gruende_aus_wert(z["dismiss_reason"])
        gruende = [g for g in gruende
                   if g not in SYSTEM_GRUENDE and ist_urteil(g) and g.lower() not in aus]
        if klasse == "passt_nicht" and not gruende:
            continue  # ein abgeschalteter Grund ist kein Muster mehr (#1297)
        notiz = str(z["dismiss_note"] or "").strip()
        if z["entschieden_von"] == "claude":
            begruendung = _satz(z["analyse_begruendung"] or notiz)
        else:
            begruendung = "" if notiz.startswith(AUTO_NOTIZ) else _satz(notiz)
        grund = ", ".join(gruende)
        if z["entschieden_von"] == "claude":
            gewicht = 1.3 if begruendung else 1.1
        elif grund and grund != "sonstiges" or begruendung:
            gewicht = 1.15
        else:
            gewicht = 1.0
        gegen = z["ollama_lag_richtig"] == 0
        if gegen:
            gewicht *= 1.5
        titel = str(z["title"] or "")
        beschreibung = str(z["description"] or "")[:1500]
        pool.append({
            "hash": z["hash"], "titel": titel, "klasse": klasse,
            "von": z["entschieden_von"], "grund": grund,
            "begruendung": begruendung, "gegenbeispiel": gegen,
            "gewicht": gewicht, "beschreibung": beschreibung,
            "_titel": stamm_menge(titel), "_text": stamm_menge(beschreibung),
            "_neu": z["updated_at"] or "",
        })
    return pool


def _ohne_praefix(h) -> str:
    return str(h or "").split(":", 1)[-1]


def waehlen(pool: list, job: dict, limit: int = STANDARD_ANZAHL) -> list:
    """Die Beispiele fuer EINE Stelle: aehnlichste zuerst, gemischt, Fehler der KI voran."""
    if not pool:
        return []
    eigener = _ohne_praefix(job.get("hash"))
    t_job = stamm_menge(job.get("title"))
    d_job = stamm_menge(str(job.get("description") or "")[:1500])
    bewertet = []
    for p in pool:
        if eigener and _ohne_praefix(p["hash"]) == eigener:
            continue  # nie die Stelle selbst: die Gegenprobe ist blind
        s = aehnlichkeit(t_job, d_job, p["_titel"], p["_text"])
        if s > 0:
            bewertet.append((s * p["gewicht"], p))
    bewertet.sort(key=lambda x: (-x[0], x[1]["_neu"]), reverse=False)
    gruppen = {"nicht": [], "passt": []}
    for s, p in bewertet:
        gruppen["nicht" if p["klasse"] == "passt_nicht" else "passt"].append(p)
    halb = max(1, limit // 2)
    nimm = gruppen["nicht"][:halb] + gruppen["passt"][:halb]
    rest = limit - len(nimm)
    if rest > 0:
        uebrig = gruppen["nicht"][halb:] + gruppen["passt"][halb:]
        uebrig.sort(key=lambda p: -p["gewicht"])
        nimm += uebrig[:rest]
    if not nimm:
        # Nichts Aehnliches: die juengsten Entscheidungen des Menschen, wie bisher.
        neueste = [p for p in pool if eigener != _ohne_praefix(p["hash"])]
        neueste.sort(key=lambda p: p["_neu"], reverse=True)
        nimm = neueste[:min(4, limit)]
    nimm.sort(key=lambda p: (not p["gegenbeispiel"],))  # Fehler der KI zuerst (stabil)
    return [_beispiel(p) for p in nimm[:limit]]


def _beispiel(p: dict) -> dict:
    kern = kern_anforderungen(p["beschreibung"])
    return {"titel": p["titel"], "klasse": p["klasse"], "von": p["von"],
            "grund": p["grund"], "begruendung": p["begruendung"],
            "kern": kern, "gegenbeispiel": p["gegenbeispiel"]}


def als_zeile(b: dict) -> str:
    """Ein Beispiel als eine kurze Zeile fuer den Prompt."""
    entscheidung = {"passt_nicht": "PASST_NICHT", "passt": "PASST",
                    "bedingt": "UNSICHER"}.get(b.get("klasse"), "UNSICHER")
    wer = "Bewerber" if b.get("von") == "mensch" else "Claude nach dem Lesen"
    teile = [f"  - '{(b.get('titel') or '').strip()[:90]}' → {entscheidung} ({wer}"]
    if b.get("grund"):
        teile[0] += f", Grund: {b['grund']}"
    teile[0] += ")"
    if b.get("kern"):
        teile.append("Kern: " + "; ".join(b["kern"]))
    if b.get("begruendung"):
        teile.append("Begründung: " + b["begruendung"])
    if b.get("gegenbeispiel"):
        teile.append("Die lokale KI lag hier früher falsch.")
    zeile = ". ".join(teile) if len(teile) > 1 else teile[0]
    return zeile[:ZEILE_MAX].rstrip()


def beispiele_fuer(db, job: dict, limit: int = STANDARD_ANZAHL, pool: list | None = None) -> list:
    """Bequemer Einzelaufruf; im Lauf den Pool einmal laden und weitergeben."""
    try:
        return waehlen(pool if pool is not None else pool_laden(db), job, limit)
    except Exception as exc:  # pragma: no cover - ein Beispiel-Fehler stoppt nie den Lauf
        logger.warning("Beispiele nicht gewaehlt: %s", exc)
        return []
