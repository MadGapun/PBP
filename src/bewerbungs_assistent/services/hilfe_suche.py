"""Die Suche der interaktiven Hilfe (#1233, F51): nachschlagen statt raten.

Die Hilfe antwortet NUR aus eigenen Texten: der eingebauten Hilfe, ausgewaehlten Wiki-Seiten und dem Prompt-Katalog.
`scripts/hilfe_wissen_bauen.py` schneidet sie beim Release in Abschnitte (`content/hilfe_wissen.json`). Dieses
Modul liest die Datei, sucht darin und baut die Antwortkarte. Es braucht weder Netz noch ein Sprachmodell:

* Die Suche ist eine deutsche Volltextsuche (BM25 ueber Wortstaemme, Umschrift der Umlaute, trennbare Verben wie
  "lege ... an", Zusammensetzungen, kleine Synonymliste). Sie ist der Boden: die Antwort steht in Millisekunden da,
  auch ohne KI.
* Eine Karte nennt Titel, Kurztext, Quelle und hoechstens drei Wege weiter: einen Sprung in die App (nur eine Seite oder
  ein Reiter aus der geprueften Liste), die Wiki-Seite und den Prompt aus dem Katalog zum Kopieren. Nichts davon
  kommt aus einem Modell.
* Findet die Suche nichts Sicheres, sagt sie das: "Dazu steht nichts in der Hilfe", bei Fragen ausserhalb von PBP, dass sie
  nur zur Bedienung etwas sagen kann, und bei einem unsicheren Treffer, dass er unsicher ist. Immer mit einem
  kopierfertigen Satz fuer Claude.

Wie sicher ein Treffer ist, misst die ABDECKUNG: der Anteil des Gewichts der Fragewoerter (nach ihrer Seltenheit), der im
Abschnitt vorkommt. Ein Wort, das die Hilfe nicht kennt ("Dieselmotor"), zaehlt voll gegen die Abdeckung: so bleibt eine
Frage, die nur ein Fuellwort mit der Hilfe teilt ("funktioniert"), ohne sichere Antwort.

Die Fragen werden nicht gespeichert und nirgends protokolliert (Nutzerentscheidung 16.10.2026).
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

PFAD = Path(__file__).resolve().parent.parent / "content" / "hilfe_wissen.json"
WIKI_BASIS = "https://github.com/MadGapun/PBP/wiki/"
MAX_FRAGE = 400
MAX_KARTEN = 3
KURZ_ZEICHEN = 330

# BM25
K1 = 1.2
B = 0.6
GEWICHT_TITEL = 3.0
GEWICHT_PFAD = 0.5
GEWICHT_TEXT = 1.0

# Quellen, die der Mensch eher gemeint hat als einen Wiki-Absatz: die eingebaute Hilfe ist kuratiert und aktuell.
QUELLEN_GEWICHT = {"hilfe": 1.15, "faq": 1.15, "probleme": 1.15, "prompt": 1.0, "wiki": 1.0}

# Schwellen (am Fragenkatalog gemessen, tests/test_v18_hilfe_suche_1233.py). ABDECKUNG = Anteil des Fragegewichts im Abschnitt.
ABDECKUNG_GEFUNDEN = 0.55
ABDECKUNG_UNSICHER = 0.35
# Woerter, die die Hilfe gar nicht kennt, tragen ihr Gewicht als Anteil der Frage: ab UNBEKANNT_GEFUNDEN ist kein sicherer Treffer
# mehr moeglich, ab UNBEKANNT_UNSICHER auch kein unsicherer.
UNBEKANNT_GEFUNDEN = 0.34
UNBEKANNT_UNSICHER = 0.5
# Eine Frage, deren bekannte Woerter zusammen weniger Gewicht tragen, hat mit PBP nichts zu tun.
THEMA_MASSE = 4.0

_UMSCHRIFT = (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss"))

STOPPWOERTER = frozenset("""
a ab aber alle allen aller alles also am an andere anderen auch auf aus bei bin bis bitte da dabei dafuer dagegen dann das dass
dazu dein deine deinen deinem deiner dem den denn der des die dies diese diesen diesem dieser dieses dir doch du durch eben
ein eine einen einem einer eines einfach er es etwas fuer gibt gar geht gern haben habe hast hat hatte hier hilfe ich ihm ihn
ihr ihre im in ist ja jede jeden jeder jedes jetzt kann kannst koennen koennte man mal mehr mein meine meinen meinem meiner
mich mir mit muss musst muessen nach nicht noch nun nur ob oder ohne pbp sage sag sagen schon sehr sein seine sich sie sind so
soll sollen sollte sonst ueber um und uns unter von vom vor wann war was weil welche welchen welcher welches wenn wer werde
werden wie wieder will wir wird wirst wo woher wohin wollen wuerde zeig zeige zeigen zu zum zur zwar
ueberhaupt eigentlich genau gerade ganz gleich mache machen mach bekomme bekommen brauche brauchen braucht moechte moechten
passiert passieren geschieht ploetzlich schon mal sehe sehen sieht kann koennen
als erklaere erklaer erklaeren erklaert nenne nenn beschreibe beschreib dich euch ihnen finde finden findet kriege kriegen moeglich worauf wozu womit wofuer selbst selber funktioniert funktionieren funktion
""".split())

# Trennbare Verben: "lege ich eine Bewerbung an" meint "anlegen", "stelle ich ein" meint "einstellen". Die Partikel steht am Ende
# des Satzes, der Stamm des Verbs davor.
PARTIKEL = frozenset("an ein aus auf ab hoch zurueck fest um vor weg her hin frei zusammen".split())

# Gleichwertige Woerter, in Umschrift. Nur eng gefasste Gruppen: eine zu weite Gruppe fuegt Rauschen hinzu.
SYNONYME: tuple[tuple[str, ...], ...] = (
    ("update", "aktualisieren", "aktualisierung", "upgrade", "versionswechsel"),
    ("sicherung", "backup", "datensicherung", "zurueckholen", "wiederherstellen"),
    ("loeschen", "entfernen", "wegmachen", "loeschung"),
    ("stelle", "job", "stellenanzeige", "stellenangebot", "anzeige"),
    ("lebenslauf", "cv", "curriculum"),
    ("anschreiben", "motivationsschreiben", "bewerbungsschreiben"),
    ("nachfassen", "nachfrage", "nachfassung", "erinnerung", "nachhaken", "followup"),
    ("ki", "ollama", "elwosa", "sprachmodell"),
    ("mail", "email", "mails", "postfach"),
    ("termin", "kalender", "interviewtermin"),
    ("interview", "vorstellungsgespraech", "bewerbungsgespraech", "gespraech"),
    ("einstellung", "einstellungen", "konfiguration", "optionen", "schalter"),
    ("fehler", "problem", "stoerung", "kaputt", "klappt"),
    ("kosten", "preis", "kostenlos", "gebuehr", "bezahlen"),
    ("datenschutz", "privatsphaere", "dsgvo"),
    ("installieren", "installation", "installer", "einrichten", "setup"),
    ("gehalt", "verguetung", "lohn", "verdienst"),
    ("entfernung", "pendeln", "fahrzeit", "anfahrt", "fahrstrecke", "kilometer"),
    ("punkte", "score", "bewertung", "punktzahl"),
    ("aussortieren", "ausblenden", "verwerfen"),
    ("quelle", "quellen", "portal", "boerse", "jobboerse", "jobportal"),
    ("suchbegriffe", "keywords", "stichwoerter", "schlagwoerter", "suchkriterien"),
    ("hochladen", "upload", "einlesen", "importieren"),
    ("dokument", "datei", "pdf"),
    ("ordner", "verzeichnis", "ablage", "speicherort", "gespeichert", "speichern", "landen"),
    ("absage", "ablehnung", "abgelehnt"),
    ("firma", "unternehmen", "arbeitgeber"),
    ("kontakt", "ansprechpartner", "recruiter"),
    ("sperren", "blacklist", "ausschliessen"),
    ("knopf", "button", "schaltflaeche"),
    ("starten", "oeffnen", "aufrufen"),
    ("dashboard", "startseite", "oberflaeche"),
    ("texterkennung", "ocr", "scan", "gescannt"),
    ("anlegen", "erstellen", "eintragen", "erfassen", "hinzufuegen", "erzeugen", "lege", "erstelle"),
    ("rechner", "computer", "pc", "geraet", "geraete", "laptop"),
    ("kachel", "bereich", "karte", "widget"),
    ("protokoll", "log", "logs", "logbuch"),
    ("rueckgaengig", "zurueckholen", "zuruecksetzen", "wiederherstellen"),
    ("melden", "berichten", "vorschlagen", "idee"),
    # Umgangssprache gegen die Woerter der Oberflaeche (16.10.2026, nach der Messung an ungesehenen Fragen)
    ("docx", "word", "worddatei", "textverarbeitung"),
    ("punkte", "zahl", "wert", "zahlen"),
    ("beworben", "bewerbung", "verschickt", "abgeschickt", "versendet"),
    ("doppelt", "dublette", "duplikat", "mehrfach", "zweimal"),
    ("laedt", "startet", "erscheint"),
    ("funktionen", "werkzeuge", "tools"),
    ("ausschalten", "abschalten", "deaktivieren", "pausieren", "abstellen", "ausmachen"),
    ("beta", "betaversion", "vorabversion", "vorabversionen", "testversion"),
    ("festplatte", "speicherplatz", "platz", "gigabyte", "groesse"),
    ("aktuell", "update", "version", "neueste", "veraltet"),
    ("weg", "verschwunden", "verloren", "ausgeblendet", "aussortiert", "fehlt"),
    ("herunterladen", "download", "exportieren", "ausgeben"),
)


def umschrift(text: str) -> str:
    """Klein, NFC, Umlaute und ß in Umschrift: 'Süd' und 'sued' sind dasselbe Wort."""
    t = unicodedata.normalize("NFC", text).lower()
    for a, b in _UMSCHRIFT:
        t = t.replace(a, b)
    return t


def woerter(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", umschrift(text))


_ENDUNGEN = (
    "ungen", "ung", "heiten", "heit", "keiten", "keit", "lichen", "lichem", "licher", "liches", "liche", "lich",
    "ischen", "isch", "enden", "ende", "ern", "ens", "sten", "ste", "er", "en", "es", "em", "e", "n", "s",
)
_PARTIZIP_IER = re.compile(r"ier(?:ten|te|t)$")


def stamm(wort: str) -> str:
    """Leichter Wortstamm: 'nachfassung', 'nachfassen' und 'nachfassungen' werden 'nachfass'; 'aktualisiert' wird 'aktualisier'."""
    if len(wort) <= 4 or wort.isdigit():
        return wort
    if _PARTIZIP_IER.search(wort):
        # installiert -> installier: dieselbe Form wie 'installieren' (Endung 'en' ab). Danach NICHT noch 'er' abschneiden,
        # sonst wird aus 'aktualisiert' ein 'aktualisi' und aus 'aktualisieren' ein 'aktualisier'.
        return _PARTIZIP_IER.sub("ier", wort)
    for e in _ENDUNGEN:
        if wort.endswith(e) and len(wort) - len(e) >= 4:
            wort = wort[: -len(e)]
            break
    # 'verhandeln' / 'Verhandlung': das e vor dem l oder r faellt in der Ableitung weg - beides wird 'verhandl'.
    if len(wort) >= 7 and wort.endswith(("el", "er")) and wort[-3] not in "aeiou":
        wort = wort[:-2] + wort[-1]
    return wort


def inhaltsstaemme(text: str) -> list[str]:
    """Die Staemme der Woerter, die etwas bedeuten (ohne Fuellwoerter)."""
    return [stamm(w) for w in woerter(text) if w not in STOPPWOERTER and w not in PARTIKEL and len(w) > 1]


@lru_cache(maxsize=1)
def _synonym_karte() -> dict[str, tuple[str, ...]]:
    karte: dict[str, set[str]] = {}
    for gruppe in SYNONYME:
        staemme = {stamm(umschrift(w)) for w in gruppe}
        for s in staemme:
            karte.setdefault(s, set()).update(staemme - {s})
    return {k: tuple(sorted(v)) for k, v in karte.items()}


# ── Die Wissensbasis ────────────────────────────────────────────────────────────────────────

@dataclass
class Wissen:
    abschnitte: list[dict]
    seiten: dict[str, str]
    reiter: dict[str, dict]
    nach_id: dict[str, dict] = field(default_factory=dict)
    tf: list[Counter] = field(default_factory=list)
    laenge: list[float] = field(default_factory=list)
    mittlere_laenge: float = 1.0
    df: Counter = field(default_factory=Counter)
    idf: dict[str, float] = field(default_factory=dict)
    max_idf: float = 1.0
    invertiert: dict[str, list[int]] = field(default_factory=dict)
    titel_staemme: list[frozenset] = field(default_factory=list)
    vokabular_lang: tuple[str, ...] = ()
    domaene: frozenset = frozenset()   # Woerter der Welt der Hilfe: aus einer Ueberschrift, der eingebauten Hilfe oder haeufig

    @classmethod
    def aus_daten(cls, daten: dict) -> "Wissen":
        w = cls(abschnitte=list(daten["abschnitte"]), seiten=dict(daten.get("seiten") or {}), reiter=dict(daten.get("reiter") or {}))
        w.nach_id = {a["id"]: a for a in w.abschnitte}
        for a in w.abschnitte:
            tf: Counter = Counter()
            for s in inhaltsstaemme(a["titel"]):
                tf[s] += GEWICHT_TITEL
            for s in inhaltsstaemme(a["pfad"]):
                tf[s] += GEWICHT_PFAD
            for s in inhaltsstaemme(a["text"]):
                tf[s] += GEWICHT_TEXT
            w.tf.append(tf)
            w.laenge.append(sum(tf.values()) or 1.0)
            w.titel_staemme.append(frozenset(inhaltsstaemme(a["titel"])))
        n = len(w.abschnitte)
        w.mittlere_laenge = (sum(w.laenge) / n) if n else 1.0
        for i, tf in enumerate(w.tf):
            for s in tf:
                w.df[s] += 1
                w.invertiert.setdefault(s, []).append(i)
        w.idf = {s: math.log(1.0 + (n - df + 0.5) / (df + 0.5)) for s, df in w.df.items()}
        w.max_idf = math.log(1.0 + (n + 0.5) / 0.5)
        w.vokabular_lang = tuple(sorted((s for s in w.df if len(s) >= 5), key=len, reverse=True))
        kuratiert: set[str] = set()
        for a in w.abschnitte:
            if a["quelle"] != "wiki":
                kuratiert |= set(inhaltsstaemme(a["titel"])) | set(inhaltsstaemme(a["text"]))
        w.domaene = frozenset({s for ts in w.titel_staemme for s in ts} | kuratiert | {s for s, d in w.df.items() if d >= 12})
        return w


@lru_cache(maxsize=4)
def _laden_cached(pfad: str, mtime: float) -> Wissen:
    daten = json.loads(Path(pfad).read_text(encoding="utf-8"))
    return Wissen.aus_daten(daten)


def laden(pfad: Path | None = None) -> Wissen:
    """Die Wissensbasis (einmal gelesen, bei geaenderter Datei neu)."""
    p = Path(pfad or PFAD)
    return _laden_cached(str(p), p.stat().st_mtime)


def verfuegbar() -> bool:
    return PFAD.is_file()


# ── Die Suche ───────────────────────────────────────────────────────────────────────────────

@dataclass
class Treffer:
    abschnitt: dict
    score: float
    abdeckung: float      # Anteil des Fragegewichts (nach Seltenheit), der im Abschnitt vorkommt


@dataclass
class Ergebnis:
    status: str           # gefunden | unsicher | nichts_gefunden | ausserhalb | leer
    treffer: list[Treffer]
    fragewoerter: list[str]
    thema: bool           # hat die Frage Woerter, die die Hilfe kennt und die etwas bedeuten?
    unbekannt: float = 0.0   # Anteil des Fragegewichts, den die Hilfe gar nicht kennt


def bereinige_frage(frage: Any) -> str:
    t = re.sub(r"\s+", " ", str(frage or "")).strip()
    return t[:MAX_FRAGE]


def _gemeinsamer_anfang(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a, b):
        if x != y:
            break
        n += 1
    return n


@dataclass
class Konzept:
    """Ein Gedanke der Frage: ein Wort oder ein trennbares Verb ('lege ... an' = 'anleg') mit seinen Schreibweisen."""
    haupt: str
    formen: dict[str, float]
    masse: float = 0.0
    alt: dict[str, float] = field(default_factory=dict)
    bekannt: bool = True


def _konzepte(w: Wissen, frage: str) -> list[Konzept]:
    """Die Gedanken der Frage. Ein trennbares Verb wird, wenn es das in der Hilfe gibt, zu EINEM Gedanken mit zwei Schreibweisen."""
    roh = woerter(frage)
    konzepte: dict[str, Konzept] = {}
    reihenfolge: list[str] = []
    verbraucht: set[int] = set()

    def neu(haupt: str, formen: dict[str, float]):
        k = konzepte.get(haupt)
        if k is None:
            konzepte[haupt] = Konzept(haupt, dict(formen))
            reihenfolge.append(haupt)
        else:
            for f, g in formen.items():
                k.formen[f] = max(k.formen.get(f, 0.0), g)

    for idx, t in enumerate(roh):
        if t not in PARTIKEL or idx == 0:
            continue
        beste = None                                                   # (df des zusammengesetzten Verbs, naeher = groesser, j, kandidat)
        for j in range(idx - 1, max(0, idx - 8) - 1, -1):
            v = roh[j]
            if j in verbraucht or v in STOPPWOERTER or v in PARTIKEL or len(v) < 3 or v.isdigit():
                continue
            kandidat = stamm(t + v)
            if kandidat in w.df and (beste is None or (w.df[kandidat], j) > beste[:2]):
                beste = (w.df[kandidat], j, kandidat)           # das Verb, das es am haeufigsten gibt ('aussortier', nicht 'ausstell')
        if beste is not None:
            _, j, kandidat = beste
            grund = stamm(roh[j])
            # Das Grundwort ('stelle' in 'stelle ich ein') meint dann das Verb, nicht die Stelle: leiser, wenn es viel haeufiger
            # vorkommt als das zusammengesetzte Verb.
            leise = w.df.get(grund, 0) > 2 * w.df[kandidat]
            neu(kandidat, {kandidat: 1.0, grund: 0.35 if leise else 0.8})
            verbraucht.add(j)
    for idx, t in enumerate(roh):
        if idx in verbraucht or t in STOPPWOERTER or t in PARTIKEL or len(t) <= 1 or t.isdigit():
            continue
        s = stamm(t)
        neu(s, {s: 1.0})

    ergebnis = [konzepte[h] for h in reihenfolge]
    for k in ergebnis:
        k.alt = _alternativen(w, k.haupt)
        k.bekannt = k.haupt in w.df or any(f in w.df for f in k.formen) or bool(k.alt)
        k.masse = max((w.idf.get(f, w.max_idf) for f in k.formen), default=w.max_idf) if k.bekannt else w.max_idf
        if k.haupt not in w.df and not any(f in w.df for f in k.formen):
            k.masse = w.max_idf
    return ergebnis


def _alternativen(w: Wissen, s: str) -> dict[str, float]:
    """Woerter, die statt `s` zaehlen, mit ihrem Gewicht: Synonyme, Wortfamilie (gleicher Anfang), Bestandteile und Zusammensetzungen."""
    alt: dict[str, float] = {}
    for t in _synonym_karte().get(s, ()):
        alt[t] = 0.6
    if len(s) >= 6 and w.df.get(s, 0) <= 3:
        for v in w.vokabular_lang:
            if v == s:
                continue
            p = _gemeinsamer_anfang(s, v)
            # Gleiche Wortfamilie: der Anfang stimmt und die Laengen sind aehnlich ('verhandl' / 'verhandel', nicht 'diesel' / 'dieselmotor').
            if p >= 6 and p >= min(len(s), len(v)) - 2 and min(len(s), len(v)) >= 0.75 * max(len(s), len(v)):
                alt[v] = max(alt.get(v, 0.0), 0.55)
    if len(s) >= 9 or (s not in w.df and len(s) >= 6):
        teile = []
        belegt = [False] * len(s)
        for v in w.vokabular_lang:
            if len(v) >= 5 and v != s and v in s:
                pos = s.find(v)
                if not all(belegt[pos:pos + len(v)]):
                    teile.append(v)
                    for k in range(pos, pos + len(v)):
                        belegt[k] = True
        # 'gehaltsverhandlung' besteht aus 'gehalt' und 'verhandl' (plus Fugen-s); 'steuererklaerung' nur zu zwei Dritteln
        # aus einem Wort der Hilfe und zaehlt deshalb als unbekannt.
        if teile and sum(belegt) >= 0.85 * len(s):
            for v in teile:
                alt[v] = max(alt.get(v, 0.0), 0.5)
        for v in w.vokabular_lang:
            if len(v) >= 5 and v != s and s in v and len(s) >= 0.6 * len(v):
                alt[v] = max(alt.get(v, 0.0), 0.4)
    return alt


def _ist_teil(t: str, s: str) -> bool:
    """Ist `t` ein Bestandteil der Zusammensetzung `s`?"""
    return len(t) < len(s) and t in s


def _bm25(w: Wissen, gew: dict[str, float]) -> dict[int, float]:
    punkte: dict[int, float] = {}
    for s, g in gew.items():
        idf = w.idf.get(s)
        if idf is None:
            continue
        for i in w.invertiert[s]:
            tf = w.tf[i][s]
            nenner = tf + K1 * (1.0 - B + B * w.laenge[i] / w.mittlere_laenge)
            punkte[i] = punkte.get(i, 0.0) + g * idf * (tf * (K1 + 1.0)) / nenner
    return punkte


def _gehoert_zur_hilfe(k: Konzept, w: Wissen) -> bool:
    """Gehoert der Gedanke zur Welt der Hilfe? Ein Wort oder Synonym aus ihr, oder eine Zusammensetzung, die zu mehr als der Haelfte aus ihr besteht."""
    if not k.bekannt:
        return False
    if any(f in w.domaene for f in k.formen):
        return True
    for t in k.alt:
        if not _ist_teil(t, k.haupt) and t in w.domaene:
            return True
    teile = sum(len(t) for t in k.alt if _ist_teil(t, k.haupt) and t in w.domaene)
    return teile > 0.5 * len(k.haupt)


def _anteil(k: Konzept, tf: Counter) -> float:
    """Wie weit deckt der Abschnitt diesen Gedanken? 1,0 bei einer Schreibweise des Gedankens, sonst nur anteilig."""
    eigene = max((g for f, g in k.formen.items() if f in tf), default=0.0)
    if eigene:
        return eigene
    # Ein Ersatzwort deckt das Fragewort nur mit seinem Gewicht; Teile einer Zusammensetzung zusammen nur bis zu ihrem Anteil.
    einzeln = max((g for t, g in k.alt.items() if t in tf and not _ist_teil(t, k.haupt)), default=0.0)
    teile = sum(len(t) for t in k.alt if t in tf and _ist_teil(t, k.haupt)) / max(len(k.haupt), 1)
    return min(0.9, max(einzeln / 0.6 * 0.8 if einzeln else 0.0, teile))


def suche(frage: str, vorherige: str = "", wissen: Wissen | None = None, limit: int = MAX_KARTEN) -> Ergebnis:
    w = wissen or laden()
    frage = bereinige_frage(frage)
    if not frage:
        return Ergebnis("leer", [], [], False)
    konzepte = _konzepte(w, frage)
    if not konzepte and vorherige:
        # "und wo finde ich das?" besteht nur aus Fuellwoertern: gemeint ist das Thema der Frage davor.
        konzepte = _konzepte(w, bereinige_frage(vorherige))
    if not konzepte:
        return Ergebnis("nichts_gefunden", [], [], False)
    staemme = [k.haupt for k in konzepte]

    # Eine kurze Nachfrage ("und wo finde ich das?") erbt die Woerter der vorigen Frage, schwach gewichtet.
    kontext = inhaltsstaemme(vorherige) if vorherige and len(konzepte) <= 2 else []

    gew: dict[str, float] = {}
    for k in konzepte:
        for f, g in k.formen.items():
            gew[f] = max(gew.get(f, 0.0), g)
        for t, g in k.alt.items():
            gew[t] = max(gew.get(t, 0.0), g)
    for s in kontext:
        gew[s] = max(gew.get(s, 0.0), 0.3)

    # Gewicht jedes Gedankens nach Seltenheit; ein unbekanntes Wort zaehlt als das seltenste.
    gesamt = sum(k.masse for k in konzepte) or 1.0
    unbekannt_anteil = sum(k.masse for k in konzepte if not k.bekannt) / gesamt
    # Hat die Frage ueberhaupt ein Wort aus der Welt der Hilfe (ein Wort aus einer Ueberschrift oder ein haeufiges)?
    thema = any(_gehoert_zur_hilfe(k, w) for k in konzepte)

    if not thema:
        return Ergebnis("ausserhalb", [], staemme, False, round(unbekannt_anteil, 3))
    punkte = _bm25(w, gew)
    if not punkte:
        return Ergebnis("nichts_gefunden", [], staemme, True, round(unbekannt_anteil, 3))

    rangliste = []
    for i, p in punkte.items():
        a = w.abschnitte[i]
        tf = w.tf[i]
        gedeckt = 0.0
        titel_masse = 0.0
        for k in konzepte:
            anteil = _anteil(k, tf)
            if anteil:
                gedeckt += k.masse * anteil
                if any(f in w.titel_staemme[i] for f in k.formen) or any(t in w.titel_staemme[i] for t in k.alt):
                    titel_masse += k.masse * anteil
        abdeckung = gedeckt / gesamt
        titel_abdeckung = titel_masse / gesamt
        p = p * QUELLEN_GEWICHT.get(a["quelle"], 1.0) * (1.0 + 0.8 * abdeckung + 1.0 * titel_abdeckung)
        rangliste.append((p, i, abdeckung))
    rangliste.sort(key=lambda x: (-x[0], x[1]))

    # Gleiche Titel nur einmal (die eingebaute Hilfe vor dem Wiki).
    gesehen: set[str] = set()
    treffer: list[Treffer] = []
    for p, i, abdeckung in rangliste:
        a = w.abschnitte[i]
        schluessel = umschrift(a["titel"])
        if schluessel in gesehen:
            continue
        gesehen.add(schluessel)
        treffer.append(Treffer(a, round(p, 3), round(abdeckung, 3)))
        if len(treffer) >= limit:
            break

    beste = max(treffer, key=lambda t: t.abdeckung)
    if beste.abdeckung >= ABDECKUNG_GEFUNDEN and unbekannt_anteil < UNBEKANNT_GEFUNDEN:
        status = "gefunden"
    elif beste.abdeckung >= ABDECKUNG_UNSICHER and unbekannt_anteil < UNBEKANNT_UNSICHER:
        status = "unsicher"
    else:
        status = "nichts_gefunden"
    return Ergebnis(status, treffer, staemme, True, round(unbekannt_anteil, 3))


# ── Die Karte ───────────────────────────────────────────────────────────────────────────────

def kurztext(text: str, grenze: int = KURZ_ZEICHEN) -> str:
    """Der Anfang des Abschnitts, am Satzende oder Zeilenende gekuerzt."""
    t = text.strip()
    if len(t) <= grenze:
        return t
    stueck = t[:grenze]
    ende = max(stueck.rfind(". "), stueck.rfind("! "), stueck.rfind("? "), stueck.rfind(".\n"), stueck.rfind("\n"))
    if ende >= grenze // 2:
        return stueck[: ende + 1].strip()
    wort = stueck.rfind(" ")
    return (stueck[:wort] if wort > grenze // 2 else stueck).rstrip(",;:—-") + " …"


def oeffnen_fuer(ziel: dict | None, w: Wissen) -> dict | None:
    """Der Sprung in die App. Nur eine Seite oder ein Reiter aus der geprueften Liste; sonst keiner."""
    if not ziel:
        return None
    if ziel.get("art") == "seite" and ziel.get("id") in w.seiten:
        return {"art": "seite", "id": ziel["id"], "label": f"Öffnen: {w.seiten[ziel['id']]}"}
    if ziel.get("art") == "einstellung" and ziel.get("id") in w.reiter:
        # Der Pfad wird aus dem Trenner der Menuepfade gebaut (services/menue.py): kein frei getippter Pfad im Quelltext (H30).
        from .menue import TRENNER
        return {"art": "einstellung", "id": ziel["id"],
                "label": "Öffnen: Einstellungen" + TRENNER + w.reiter[ziel["id"]]["label"]}
    return None


def wiki_fuer(wiki: dict | None) -> dict | None:
    if not wiki or not wiki.get("seite"):
        return None
    url = WIKI_BASIS + wiki["seite"] + (f"#{wiki['anker']}" if wiki.get("anker") else "")
    return {"seite": wiki["seite"], "url": url}


def prompt_fuer(prompt_id: str | None) -> dict | None:
    """Der Prompt aus dem Katalog zum Kopieren (`/name`, den die App zur Anleitung aufloest)."""
    if not prompt_id:
        return None
    try:
        from . import prompt_katalog
    except Exception:  # noqa: BLE001
        return None
    e = prompt_katalog.eintrag(prompt_id)
    if not e:
        return None
    return {"id": e["id"], "titel": e["titel"], "kopieren": "/" + (e.get("prompt") or e["id"])}


def karte(treffer: Treffer, w: Wissen) -> dict:
    a = treffer.abschnitt
    return {
        "id": a["id"],
        "titel": a["titel"],
        "kurz": kurztext(a["text"]),
        "quelle": a["pfad"],
        "oeffnen": oeffnen_fuer(a.get("ziel"), w),
        "wiki": wiki_fuer(a.get("wiki")),
        "prompt": prompt_fuer(a.get("prompt")),
        "sicher": treffer.abdeckung >= ABDECKUNG_GEFUNDEN,
    }


HINWEIS_AUSSERHALB = "Dazu kann ich nur zur Bedienung von PBP etwas sagen. Für alles andere ist Claude da."
HINWEIS_NICHTS = "Dazu steht nichts in der Hilfe."
HINWEIS_UNSICHER = "Ich bin nicht sicher, ob das passt. Vielleicht hilft einer dieser Abschnitte:"


def satz_fuer_claude(frage: str) -> str:
    """Ein kopierfertiger Satz: die Frage geht erst an Claude, wenn der Mensch ihn dort einfuegt."""
    return f"Ich habe eine Frage zu PBP, die ich in der Hilfe nicht finde: {frage}"


def antwort(frage: str, vorherige: str = "", wissen: Wissen | None = None) -> dict:
    """Die Antwort der Hilfe auf eine Frage: Status, Karten, Hinweis und, wenn nichts Sicheres passt, der Satz fuer Claude."""
    w = wissen or laden()
    frage = bereinige_frage(frage)
    erg = suche(frage, vorherige, w)
    if erg.status == "leer":
        return {"status": "leer", "frage": "", "karten": [], "hinweis": "Stell eine Frage zur Bedienung von PBP.", "claude": None}
    if erg.status in ("gefunden", "unsicher"):
        karten = [karte(t, w) for t in erg.treffer]
        return {
            "status": erg.status, "frage": frage, "karten": karten,
            "hinweis": HINWEIS_UNSICHER if erg.status == "unsicher" else "",
            # Auch zu einer sicher wirkenden Antwort: auf ungesehene Fragen stimmt sie nur in rund drei von vier Faellen, und
            # "passt nicht" braucht einen Weg weiter.
            "claude": {"satz": satz_fuer_claude(frage)},
        }
    hinweis = HINWEIS_AUSSERHALB if erg.status == "ausserhalb" else HINWEIS_NICHTS
    return {"status": erg.status, "frage": frage, "karten": [], "hinweis": hinweis, "claude": {"satz": satz_fuer_claude(frage)}}
