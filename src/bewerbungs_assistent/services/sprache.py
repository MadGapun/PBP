"""In welcher Sprache ist eine Stellenanzeige geschrieben (#1308)?

Gemeldet aus 1.8.1: Der Mensch wollte alle Stellen aussortieren, deren
Anzeige ausschliesslich englisch ist - auch kuenftig. Bis hierher ging das
nur ueber `stellen_bulk_bewerten(beschreibung_enthaelt_nicht=[" und ", ...])`,
quellenweise, mit Gegenpruefung auf leere Kurztexte und auf franzoesische
Anzeigen. Eine solche Liste trifft jede Stelle ohne Text mit.

## Bestimmt beim LESEN, nicht gespeichert

Der Anzeigentext kommt oft erst nach der Suche (Text-Nachzug, #1038), und
`stellenbeschreibung_nachladen` ersetzt ihn spaeter. Ein beim Speichern
festgeschriebener Wert waere danach falsch und muesste an jedem Schreibweg
nachgezogen werden. Die Erkennung kostet wenig (gemessen in
`tests/test_v182_sprache_1308.py`), deshalb rechnet jeder Leser selbst.

## Wie erkannt wird

Gezaehlt werden FUNKTIONSWOERTER (Artikel, Praepositionen, Pronomen), nicht
Fachwoerter: eine deutsche Anzeige mit "Teamcenter, Product Lifecycle
Management" bleibt deutsch, eine englische mit "Kindergarten" englisch.
Woerter, die in beiden Sprachen vorkommen ("die", "was", "also", "in",
"an", "will", "mit", ...), zaehlen nicht - sie entscheiden nichts.
Entschieden wird ueber das VERHAELTNIS der Treffer, nie ueber einen
einzelnen.

* ``unbekannt`` - kein oder zu kurzer Anzeigentext (weniger als
  `MIN_WOERTER` Woerter oder weniger als `MIN_TREFFER` Funktionswoerter).
  XING und StepStone liefern oft nur einen Kurztext. **Unbekannt ist ein
  eigener Zustand** (Lehre L7-L10): eine Regel "englisch aussortieren"
  trifft eine solche Stelle nie.
* ``andere`` - franzoesische, spanische, italienische oder niederlaendische
  Funktionswoerter ueberwiegen.
* ``de`` / ``en`` - mindestens `ANTEIL_EINDEUTIG` der deutschen und
  englischen Treffer gehoeren zu einer Sprache.
* ``gemischt`` - dazwischen (zweisprachige Anzeigen, deutsche Anzeige mit
  englischem Block).

Titel und Beschreibung werden zusammen gelesen; der Titel allein entscheidet
nie (ohne Beschreibung: ``unbekannt``).

`deutsch_verlangt(text)` erkennt in einer englischen Anzeige Hinweise wie
"German (fluent/C1)", "German language skills" oder "Deutschkenntnisse". Das
ist ein HINWEIS an der Stelle, kein Filter: wer englische Anzeigen
aussortiert, soll sehen, dass eine davon Deutsch verlangt.

Abgrenzung: `stellen_filter.py` nutzt diese Erkennung fuer die Bedingung
``sprache``; `datenguete.py` beantwortet, ob ein Text eine Bewertung traegt.
"""
from __future__ import annotations

import re

#: Die moeglichen Ergebnisse. Werte, die Claude zurueckschickt: ASCII.
SPRACHEN = ("de", "en", "gemischt", "andere", "unbekannt")

#: Klartext fuer Oberflaeche und Antworten.
KLARTEXT = {
    "de": "Deutsch",
    "en": "Englisch",
    "gemischt": "Deutsch und Englisch gemischt",
    "andere": "andere Sprache",
    "unbekannt": "unbekannt (kein oder zu kurzer Anzeigentext)",
}

#: Unter so vielen Woertern (Titel plus Beschreibung) ist ein Text zu kurz.
MIN_WOERTER = 30
#: Unter so vielen erkannten Funktionswoertern entscheidet nichts.
MIN_TREFFER = 8
#: Anteil einer Sprache an den deutschen plus englischen Treffern, ab dem
#: sie eindeutig ist. Dazwischen: gemischt.
ANTEIL_EINDEUTIG = 0.8
#: Anteil der anderen Sprachen an ALLEN Treffern, ab dem "andere" gilt.
ANTEIL_ANDERE = 0.5

# Woerter, die in Deutsch UND Englisch (oder als haeufige Abkuerzung)
# vorkommen. Sie stehen in keiner Liste - "die" ist ein deutscher Artikel und
# ein englisches Verb, "was" ein Hilfsverb in beiden Sprachen.
MEHRDEUTIG = frozenset({
    "die", "was", "also", "in", "an", "will", "mit", "so", "man", "war",
    "bin", "hat", "am", "um", "of", "is", "we", "all", "here", "hier", "most", "fast", "rat", "elf", "bad", "gift",
    "art", "kind", "team", "job", "home", "office", "a",
})

_DE = frozenset("""
der das und ist nicht ein eine einen einem einer eines zu den dem des von
für fuer auf sich wir sie ihr ihre ihren ihrem ihrer ihres du dein deine
deinen deinem deiner dich dir auch als bei nach oder wie wenn aus über
ueber unter werden wird sind sein haben durch zum zur im vom uns unser
unsere unseren unserem unserer dass daß sowie gerne gern mehr bzw idealerweise
kenntnisse erfahrung erfahrungen aufgaben bieten suchen profil vollzeit teilzeit
mitarbeiter mitarbeiterin unternehmen bewerbung abgeschlossene
abgeschlossenes ausbildung studium sehr gute guten gutes einschlägige
weiterbildung arbeitszeiten deine ihnen einsatz kunden zusammenarbeit
""".split())

_EN = frozenset("""
the and for with you your we our are this that from by have has can which
who what their they its not any within across about into will would should
must experience skills requirements responsibilities role position benefits
to on or it as be company apply applicants candidates candidate looking join working
strong ability knowledge degree years preferred required opportunity
offer offers including such these those other more than well where while
there been being were has
""".split()) | frozenset({"you'll", "we're", "you're", "we'll"})

# Franzoesisch, Spanisch, Italienisch, Niederlaendisch - nur fuer "andere".
# Woerter, die auch in der deutschen oder englischen Liste stehen, sind
# unten herausgerechnet.
_ANDERE_ROH = frozenset("""
le la les des du et est une pour dans avec nous vous sur par qui que au aux
sont votre notre cette ces être poste profil expérience entreprise
el los las del y para con por una nuestro nuestra usted es su sus como más
il lo gli della delle dei e per con una nostro nostra sono essere della nel
het een van voor met zijn wij jij jouw je ons onze bij niet ook naar heb
""".split())

#: Was nach dem Herausrechnen der Ueberschneidungen gezaehlt wird.
WOERTER_DE = _DE - MEHRDEUTIG
WOERTER_EN = _EN - MEHRDEUTIG - _DE
WOERTER_ANDERE = _ANDERE_ROH - MEHRDEUTIG - WOERTER_DE - WOERTER_EN

_WORT = re.compile(r"[a-zäöüßàâæçéèêëîïôœùûüÿñáíóú']+")


def _woerter(text: str) -> list[str]:
    return _WORT.findall(str(text or "").lower())


def zaehlen(text: str) -> dict:
    """Die Zaehlung hinter `erkennen` - fuer Tests und Nachvollziehbarkeit."""
    woerter = _woerter(text)
    de = en = andere = 0
    for w in woerter:
        if w in WOERTER_DE:
            de += 1
        elif w in WOERTER_EN:
            en += 1
        elif w in WOERTER_ANDERE:
            andere += 1
    return {"woerter": len(woerter), "de": de, "en": en, "andere": andere}


def erkennen(text: str) -> str:
    """'de', 'en', 'gemischt', 'andere' oder 'unbekannt' (siehe Modulkopf)."""
    z = zaehlen(text)
    gesamt = z["de"] + z["en"] + z["andere"]
    if z["woerter"] < MIN_WOERTER or gesamt < MIN_TREFFER:
        return "unbekannt"
    if (z["andere"] > z["de"] and z["andere"] > z["en"]
            and z["andere"] / gesamt >= ANTEIL_ANDERE):
        return "andere"
    zwei = z["de"] + z["en"]
    if zwei < MIN_TREFFER:
        return "unbekannt"
    anteil_de = z["de"] / zwei
    if anteil_de >= ANTEIL_EINDEUTIG:
        return "de"
    if anteil_de <= 1 - ANTEIL_EINDEUTIG:
        return "en"
    return "gemischt"


def erkennen_stelle(job: dict) -> str:
    """Die Sprache einer Stelle: Titel und Beschreibung zusammen.

    Ohne Beschreibung entscheidet der Titel nie - dann ist sie unbekannt."""
    beschreibung = str((job or {}).get("description") or "").strip()
    if not beschreibung:
        return "unbekannt"
    return erkennen(f"{(job or {}).get('title') or ''}\n{beschreibung}")


# Hinweise, dass eine (englische) Anzeige Deutsch verlangt. Eng gefasst: "a
# German company" ist KEINE Anforderung an die Sprache.
_DEUTSCH_VERLANGT = [re.compile(m, re.IGNORECASE) for m in (
    r"\bgerman\s+(?:language\s+)?(?:skills|proficiency|fluency|knowledge|speaker|speaking|level)\b",
    r"\bgerman\s+language\b",
    r"\b(?:fluent|fluency|native|proficient|proficiency|business[- ]fluent|business[- ]level"
    r"|very good|good|excellent|strong|working knowledge of|command of)\s+(?:in\s+)?"
    r"(?:(?:written and spoken|spoken and written)\s+)?german\b",
    r"\bgerman\s*[(:–-]\s*(?:at least\s+|min(?:imum)?\.?\s+)?(?:c1|c2|b2|b1|fluent|native|business)",
    r"\bgerman\s+(?:at least\s+)?(?:c1|c2|b2|b1)\b",
    r"\bgerman\s+(?:is\s+)?(?:a\s+)?(?:must|required|mandatory|essential)\b",
    r"\b(?:english|englisch)\s+(?:and|&|und)\s+(?:german|deutsch)\b",
    r"\b(?:german|deutsch)\s+(?:and|&|und)\s+(?:english|englisch)\b",
    r"deutschkenntnisse",
    r"\bdeutsch(?:e|en)?\s+sprachkenntnisse\b",
    r"\bdeutsch\s*[(:–-]?\s*(?:c1|c2|b2|flie[sß]end|verhandlungssicher|muttersprach)",
    r"\b(?:flie[sß]end\w*|verhandlungssicher\w*|sehr gute\w*)\s+deutsch",
)]


def deutsch_fundstelle(text: str) -> str:
    """Die Textstelle, die Deutschkenntnisse verlangt, oder ''."""
    t = str(text or "")
    for muster in _DEUTSCH_VERLANGT:
        m = muster.search(t)
        if m:
            return t[max(0, m.start() - 20): m.end() + 20].strip()
    return ""


def deutsch_verlangt(text: str) -> bool:
    """True, wenn die Anzeige Deutschkenntnisse verlangt (ein Hinweis, kein Filter)."""
    return bool(deutsch_fundstelle(text))


def merkmal(job: dict, code: str | None = None) -> dict:
    """Was eine Liste je Stelle zeigt: `sprache`, bei einer englischen oder
    gemischten Anzeige mit Deutsch-Anforderung zusaetzlich `deutsch_verlangt`.
    `code`: die schon erkannte Sprache (spart die zweite Erkennung)."""
    code = code or erkennen_stelle(job)
    feld = {"sprache": code}
    if code in ("en", "gemischt") and deutsch_verlangt(
            f"{job.get('title') or ''}\n{job.get('description') or ''}"):
        feld["deutsch_verlangt"] = True
    return feld
