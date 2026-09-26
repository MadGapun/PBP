"""Abgleich Profil gegen Suchbegriffe (#1054, C87).

## Warum

Der Fachwert misst, wie gut eine Anzeige die SUCHBEGRIFFE trifft (#1003,
#1052). Das ist nur dann eine Aussage ueber den Bewerber, wenn die
Suchbegriffe sein Profil abbilden. Die Listen werden von Hand gepflegt
und driften vom Profil weg, ohne dass es jemand merkt.

Belegt am 15.09.2026 bei einer Handpruefung eines Bestands:

* **Zwanzig Begriffe** standen im Profil als Skill mit Level 4 oder 5
  und in keiner Liste. Stellen, die genau diese Kompetenzen suchten,
  standen bei Fachwert 0 — auf zwei davon hatte sich der Mensch schon
  beworben.
* **Sechs MINUS-Begriffe** trafen das eigene Fachgebiet: im Zielumfeld
  ist "Konfigurationsmanagement" der dortige Name fuer eine
  Level-5-Kompetenz des Profils. Die Zielbranche wurde systematisch
  abgewertet.
* **Neun Begriffe ohne fachliche Aussage** in der PLUS-Liste (Remote,
  Homeoffice, ein Ort, Festanstellung, Firmenwagen ...), drei davon
  zusaetzlich ueber den Remote-Regler gewertet, also doppelt. Einer der
  Gruende, warum ein fachfremder Treffer ueber der fachlich besten
  Stelle stand (#1052).

Alle drei wurden von Hand gefunden und von Hand korrigiert. Nutzervorgabe
vom 17.09.2026: *Dinge, die wiederholt von Hand gemacht werden, sollen
automatisiert laufen.*

## Drei Pruefungen, eine Vorschlagsliste

1. **Fehlende Skills** — jeder Profil-Skill, der weder in MUSS noch in
   PLUS vorkommt. Verglichen wird ueber `anforderungen.dieselbe_anforderung`
   (#1012), nicht ueber Zeichenketten: "PLM" im Profil erkennt den
   MUSS-Begriff "PLM System" als vorhanden. Level 4 und 5 nach MUSS,
   darunter nach PLUS.
2. **Widersprueche** — jeder MINUS-Begriff, der einen Profil-Skill
   trifft. Ausgabe mit beiden Seiten, KEINE Aufloesung: der Mensch kann
   einen Begriff bewusst auf MINUS haben, weil er die Rolle nicht mehr
   ausfuellen will.
3. **Rahmenbegriffe in Fachlisten** — jeder MUSS- oder PLUS-Begriff,
   der einen Ort, ein Arbeitsmodell, eine Vertragsform oder eine
   Zusatzleistung bezeichnet. Die gehoeren in Regler und Regionen,
   nicht in die Fachlisten.

**Nie eine stille Aenderung.** PBP schlaegt vor, der Mensch bestaetigt
oder verwirft. Eine Verwerfung wird gemerkt — mit einem Fingerabdruck
der Stelle, um die es geht — und gilt, solange sich weder das Profil
noch die Liste dort aendert (#799, #784: derselbe Weg wie bei den
Erkenntnissen und Lerneffekten).

## Was NICHT gruppiert wird, und warum

`dieselbe_anforderung` kennt drei belegbare Beziehungen: Enthaltensein,
Abkuerzung/Ausschreibung, PBPs eigene Synonym-Karte. "Aenderungswesen"
und "Engineering Change Management" stehen in keiner davon — sie
werden also als VERSCHIEDEN gefuehrt, und der Skill erscheint als
fehlend. Das ist ein Vorschlag, den der Mensch mit einem Klick verwirft,
kein Schaden. Die Alternative — eine Aehnlichkeitsrechnung — wuerde
raten, und ein falsch als "vorhanden" gefuehrter Skill bliebe unsichtbar
(#1012: lieber eine Blaehung uebrig lassen als eine Anforderung
schlucken).

## Abgrenzung

`keyword_vorschlaege` rechnet beworbene gegen aussortierte Stellen und
beantwortet "womit anfangen". Dieses Modul beantwortet "was fehlt und
was ist falsch" — gegen das Profil, nicht gegen den Stellenbestand.
Beide bleiben.
"""
from __future__ import annotations

import logging
import re

from . import anforderungen

logger = logging.getLogger(__name__)

# Arten der Vorschlaege — Vertrag mit Werkzeug, Hinweis und Tests.
FEHLENDER_SKILL = "fehlender_skill"
WIDERSPRUCH = "widerspruch"
RAHMENBEGRIFF = "rahmenbegriff"

#: Ab diesem Level (aktuelles Niveau, sonst Spitze) geht ein fehlender
#: Skill nach MUSS, darunter nach PLUS. Aus dem Issue (#1054).
MIN_LEVEL_MUSS = 4

#: Unter diesem Level wird ein fehlender Skill gar nicht vorgeschlagen.
#: Gemessen auf einer Bestandskopie: von 62 fehlenden Skills trugen 43
#: Level 1 bis 3, davon 23 Level 1 oder 2 — "Grundkenntnisse". Nach
#: Grundkenntnissen sucht niemand Stellen, und eine Wand aus 43
#: Vorschlaegen, die man einzeln wegklickt, ist die Bauform, mit der ein
#: Hinweis zur Tapete wird (#929). Das Werkzeug kann die Grenze senken.
MIN_LEVEL_VORSCHLAG = 3

#: Nur fachliche Skills gehoeren nach MUSS — die MUSS-Liste ist das Tor
#: (#968). Werkzeuge und Methoden nach PLUS. Sprachen und Soft Skills
#: nie: "Deutsch (Muttersprache)" und "Verhandlungsfuehrung" standen auf
#: der Bestandskopie als MUSS-Vorschlag, beide mit Level 4/5, und keiner
#: von beiden ist ein Suchbegriff.
KATEGORIE_MUSS = {"fachlich"}
KATEGORIE_PLUS = {"tool", "methodisch"}
KATEGORIE_NIE = {"soft_skill", "sprache"}


def kategorie(skill: dict) -> str:
    """Die Kategorie in einer festen Form.

    Im Bestand steht sie als Freitext: `Tools`, `Softskills`, `KI/AI`
    neben `tool` und `soft_skill`. Verglichen wird nach dem Wortanfang;
    was sich nicht einordnen laesst, gilt als fachlich — das ist die
    Vorgabe von `skill_hinzufuegen`.
    """
    k = _umschrift(skill.get("category") or "fachlich")
    if k.startswith("soft"):
        return "soft_skill"
    if k.startswith("sprach") or k.startswith("lang"):
        return "sprache"
    if k.startswith("tool") or k.startswith("werkzeug"):
        return "tool"
    if k.startswith("method"):
        return "methodisch"
    return "fachlich"


def suchbegriff_aus(name: str) -> list[str]:
    """Aus einem Skill-Namen die Suchbegriffe, die man wirklich sucht.

    Skill-Namen tragen Zusaetze, die in einer Suchliste nichts finden:
    "Stakeholder-Management (C-Level/SVP)" trifft keine Anzeige, weil
    dort die Klammer nie steht. "Konfliktloesung & Eskalationsmanagement"
    sind zwei Begriffe. Klammern fallen weg, "&" trennt; ein Schraegstrich
    bleibt, weil "CAD/PLM" und "ECR/ECO/ECN" so geschrieben werden.
    """
    ohne_klammer = re.sub(r"\s*\([^)]*\)", "", str(name or ""))
    teile = [t.strip(" -–,") for t in re.split(r"\s+&\s+|\s+und\s+", ohne_klammer)]
    return [t for t in teile if len(t) >= 2]

#: profile_settings-Schluessel: {vorschlags_schluessel: fingerabdruck}
MARKE_VERWORFEN = "suchbegriff_abgleich_verworfen"

# ── Rahmenbegriffe: was in KEINE Fachliste gehoert ──────────────────
#
# Die Woerter sind in Umschrift (ae/oe/ue/ss) hinterlegt; verglichen wird
# nach derselben Umschrift, damit "Mobilitätsbudget" und
# "Mobilitaetsbudget" beide treffen (v1.7.92 MERKE 1: eine Liste findet
# nur die Schreibweise, in der sie steht — deshalb wird die Schreibweise
# beim Vergleich angeglichen, nicht die Liste verdoppelt).

ARBEITSMODELL = "arbeitsmodell"
VERTRAGSFORM = "vertragsform"
ORT = "ort"
ZUSATZLEISTUNG = "zusatzleistung"

_ARBEITSMODELL = {
    "remote", "homeoffice", "home office", "home-office", "hybrid",
    "hybrides arbeiten", "mobiles arbeiten", "mobile arbeit",
    "remote work", "work from home", "working from home", "wfh",
    "100% remote", "full remote", "vollstaendig remote", "rein remote",
    "teilweise remote", "remote-anteil", "remote anteil",
    "ortsunabhaengig", "standortunabhaengig", "deutschlandweit",
    "bundesweit", "vor ort", "vor-ort", "onsite", "on-site", "praesenz",
    "praesenzarbeit", "flexibler arbeitsort", "flexible arbeitsmodelle",
    "workation",
}

_VERTRAGSFORM = {
    "festanstellung", "fest angestellt", "festangestellt", "unbefristet",
    "befristet", "freelance", "freelancer", "freiberuflich",
    "freiberufler", "freie mitarbeit", "selbststaendig", "interim",
    "interim management", "contracting", "contractor", "werkvertrag",
    "zeitarbeit", "arbeitnehmerueberlassung", "personaldienstleistung",
    # Auf der Bestandskopie standen die drei in MINUS neben den
    # Formen darueber — dieselbe Sache in drei Schreibweisen.
    "leiharbeit", "anue", "personaldienstleister",
    "vollzeit", "teilzeit", "voll- oder teilzeit", "werkstudent",
    "praktikum", "ausbildung", "trainee", "minijob", "permanent",
    "full-time", "part-time", "fulltime", "parttime",
}

_ZUSATZLEISTUNG = {
    "firmenwagen", "dienstwagen", "mobilitaetsbudget", "jobrad",
    "jobticket", "deutschlandticket", "betriebliche altersvorsorge",
    "bav", "urlaubstage", "30 tage urlaub", "gleitzeit",
    "flexible arbeitszeiten", "flexible arbeitszeit", "kantine",
    "sabbatical", "weiterbildungsbudget", "bonus", "praemie",
    "13. gehalt", "13. monatsgehalt", "weihnachtsgeld", "urlaubsgeld",
    "4-tage-woche", "vier-tage-woche", "kita", "kinderbetreuung",
    "fitnessstudio", "essenszuschuss", "diensthandy", "firmenhandy",
    "corporate benefits", "mitarbeiterrabatte",
}

#: Aus `arbeitsregion.DACH_MARKER` — ein Land ist ein Ort, kein Fach.
_LAENDER = {
    "deutschland", "germany", "oesterreich", "austria", "schweiz",
    "switzerland", "dach", "dach-region", "dach region",
}


def _umschrift(text: str) -> str:
    t = str(text or "").strip().lower()
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        t = t.replace(a, b)
    return re.sub(r"\s+", " ", t)


def _level(skill: dict) -> int:
    """Aktuelles Niveau, sonst die Spitze. Ein alter Skill auf Spitze 5
    und aktuell 2 gehoert nicht nach MUSS — der Mensch sucht mit dem,
    was er heute kann (#511)."""
    for feld in ("level_current", "level"):
        wert = skill.get(feld)
        if wert not in (None, "", 0):
            try:
                return int(wert)
            except (TypeError, ValueError):
                continue
    return 3


def _orte(db, profil: dict, krit: dict) -> set[str]:
    """Bekannte Orte — datengetrieben, keine Staedteliste im Code.

    Ein Begriff ist ein Ort, wenn er die Stadt des Profils, eine der
    Regionen aus den Kriterien oder eine Ortsangabe aus dem eigenen
    Stellenbestand ist (auch als Teil vor einem Komma: aus "Musterstadt,
    Musterland" wird "musterstadt"). Eine kuratierte Staedteliste waere
    fuer jedes Land ausser einem falsch — und dieses Projekt hat mit
    Landeskunde im Code schlechte Erfahrungen (v1.7.52 MERKE 2).
    """
    orte: set[str] = set(_LAENDER)
    for wert in (profil.get("city"),):
        if wert:
            orte.add(_umschrift(wert))
    for region in krit.get("regionen") or []:
        r = _umschrift(region)
        if r and r != "remote":
            orte.add(r)
    try:
        conn = db.connect()
        zeilen = conn.execute(
            "SELECT DISTINCT location FROM jobs WHERE location IS NOT NULL "
            "AND location != '' LIMIT 5000").fetchall()
    except Exception as exc:  # pragma: no cover
        logger.debug("Orte aus dem Bestand nicht lesbar (#1054): %s", exc)
        zeilen = []
    for zeile in zeilen:
        roh = zeile[0] if not isinstance(zeile, dict) else zeile.get("location")
        for teil in re.split(r"[,/|;()]", str(roh or "")):
            teil = _umschrift(teil)
            # Ein Ortsteil, der ein Arbeitsmodell ist ("Remote (United
            # States)"), ist kein Ort.
            if teil and teil not in _ARBEITSMODELL and len(teil) > 2:
                orte.add(teil)
    return orte


def rahmenbegriff_art(begriff: str, orte: set[str]) -> str | None:
    """Ist der Begriff ein Rahmenbegriff — und welcher Art?"""
    b = _umschrift(begriff)
    if not b:
        return None
    if b in _ARBEITSMODELL:
        return ARBEITSMODELL
    if b in _VERTRAGSFORM:
        return VERTRAGSFORM
    if b in _ZUSATZLEISTUNG:
        return ZUSATZLEISTUNG
    # Ein Land ist immer ein Ort — unabhaengig davon, was der Bestand
    # kennt.
    if b in orte or b in _LAENDER:
        return ORT
    return None


_GEHOERT_ZU = {
    ARBEITSMODELL: ("Arbeitsmodell — der Remote-Regler wertet das bereits; "
                    "in der Fachliste zählt es doppelt und verfälscht den "
                    "Fachwert"),
    VERTRAGSFORM: ("Vertragsform — gehört in `stellentypen` "
                   "(suchkriterien_setzen(stellentypen=[...]))"),
    ORT: ("Ort — gehört in `regionen` oder die Entfernungsgrenze "
          "(suchkriterien_setzen(regionen=[...], max_entfernung_km=...))"),
    ZUSATZLEISTUNG: ("Zusatzleistung — sagt nichts über die Passung und "
                     "gehört in keine Liste"),
}


def _vorhandene_skills(skill_namen: list[str], muss: list[str],
                       plus: list[str]) -> set[str]:
    """Welche Skills belegt eine der beiden Fachlisten bereits?

    Gruppiert wird ALLES zusammen — Listen und Skills — mit derselben
    transitiven Gruppierung, die das Scoring benutzt (#1012). Ein
    paarweiser Vergleich Skill gegen Eintrag haette "Product Lifecycle
    Management" gegen "PLM System" als fehlend gefuehrt: die Abkuerzung
    "PLM" verbindet beide, steht aber in keinem der zwei Begriffe
    allein. In der Gruppe sind es drei Schreibweisen einer Sache — und
    genau so rechnet der Fachwert damit.
    """
    liste = list(muss) + list(plus)
    liste_norm = {_umschrift(b) for b in liste}
    vorhanden: set[str] = set()
    for gruppe in anforderungen.gruppen(liste + list(skill_namen)):
        # Beruehrt die Gruppe einen Listeneintrag, sind ALLE Mitglieder
        # belegt — auch ein Skill, der wortgleich in der Liste steht.
        # Die erste Fassung nahm nur die Nicht-Listeneintraege einer
        # Gruppe und fuehrte damit ausgerechnet den gerade uebernommenen
        # Begriff weiter als fehlend.
        if any(_umschrift(m) in liste_norm for m in gruppe):
            vorhanden.update(_umschrift(m) for m in gruppe)
    return vorhanden


def _beworbene_stellen(db) -> list[dict]:
    """Titel und Text der Stellen, auf die sich der Mensch beworben hat.

    Derselbe Weg wie im Backtest (`kalibrierung`): Junction zuerst, dann
    der Altbestand ueber `applications.job_hash`.
    """
    stellen: list[dict] = []
    gesehen: set[str] = set()
    try:
        bewerbungen = db.get_applications() or []
    except Exception as exc:  # pragma: no cover
        logger.debug("Bewerbungen nicht lesbar (#1054): %s", exc)
        return stellen
    for app in bewerbungen:
        job = None
        try:
            linked = db.get_jobs_for_application(app.get("id"))
            job = linked[0] if linked else None
        except Exception:
            job = None
        if job is None and app.get("job_hash"):
            try:
                job = db.get_job(app["job_hash"])
            except Exception:
                job = None
        if not job or job.get("hash") in gesehen:
            continue
        gesehen.add(job.get("hash"))
        stellen.append({
            "hash": job.get("hash"),
            "titel": job.get("title") or "",
            "text": " ".join(str(job.get(f) or "")
                             for f in ("title", "description")),
        })
    return stellen


def _im_text(begriff: str, text: str) -> bool:
    """Dieselbe Regel, mit der ein MINUS-Begriff im Score bestraft wird.

    Eine eigene, weichere Regel hier wuerde Widersprueche melden, die
    das Scoring nie bestraft — oder umgekehrt (#963).
    """
    try:
        from ..job_scraper import _strict_keyword_match
    except ImportError:  # pragma: no cover
        return _umschrift(begriff) in _umschrift(text)
    return bool(_strict_keyword_match(begriff, text or ""))


def _verworfen(db) -> dict:
    try:
        wert = db.get_profile_setting(MARKE_VERWORFEN) or {}
    except Exception:  # pragma: no cover
        return {}
    return wert if isinstance(wert, dict) else {}


def abgleich(db, mindest_level: int = MIN_LEVEL_VORSCHLAG) -> dict:
    """Die drei Pruefungen als getrennte Listen (AK 1).

    Schreibt nichts. Jeder Vorschlag traegt einen `schluessel` fuer
    `verwerfen`/`uebernehmen` und einen `fingerabdruck` der Stelle, um
    die es geht.

    Args:
        mindest_level: fehlende Skills unter diesem Level werden nicht
            vorgeschlagen (Vorgabe `MIN_LEVEL_VORSCHLAG`).
    """
    try:
        profil = db.get_profile() or {}
        krit = db.get_search_criteria() or {}
    except Exception as exc:  # pragma: no cover
        logger.debug("Abgleich ohne Daten (#1054): %s", exc)
        return {"fehlende_skills": [], "widersprueche": [],
                "rahmenbegriffe": [], "verworfen": 0, "offen": 0}

    muss = [str(b) for b in (krit.get("keywords_muss") or []) if str(b).strip()]
    plus = [str(b) for b in (krit.get("keywords_plus") or []) if str(b).strip()]
    minus = [str(b) for b in (krit.get("keywords_minus") or []) if str(b).strip()]
    skills = [s for s in (profil.get("skills") or [])
              if str(s.get("name") or "").strip()]
    verworfen = _verworfen(db)
    unterdrueckt = 0

    def _aktiv(vorschlag: dict) -> bool:
        nonlocal unterdrueckt
        if verworfen.get(vorschlag["schluessel"]) == vorschlag["fingerabdruck"]:
            unterdrueckt += 1
            return False
        return True

    # ── 1. Fehlende Skills ──────────────────────────────────────────
    fehlend = []
    vorhanden = _vorhandene_skills(
        [str(s["name"]).strip() for s in skills], muss, plus)
    for skill in skills:
        name = str(skill["name"]).strip()
        if _umschrift(name) in vorhanden:
            continue
        level = _level(skill)
        if level < mindest_level:
            continue
        kat = kategorie(skill)
        if kat in KATEGORIE_NIE:
            continue
        # Ein Rahmenbegriff im Profil ("Homeoffice" als Skill) gehoert
        # auch dann nicht in eine Fachliste, wenn er fehlt.
        if rahmenbegriff_art(name, set()) in (ARBEITSMODELL, VERTRAGSFORM,
                                              ZUSATZLEISTUNG):
            continue
        begriffe = suchbegriff_aus(name)
        if not begriffe:
            continue
        # Steht die bereinigte Form schon in der Liste ("Stakeholder-
        # Management" neben dem Skill "Stakeholder-Management (C-Level)"),
        # hat die Gruppierung oben das bereits erkannt: die Woerter der
        # Listenform sind eine Teilmenge der Woerter des Skill-Namens.
        # Ein zweiter Vergleich je Teilbegriff stand hier zuerst — die
        # Gegenprobe zeigte, dass er nie etwas aendert, also ist er weg
        # (v1.7.104 MERKE 3).
        begriffe = [b for b in begriffe if _umschrift(b) not in vorhanden]
        if not begriffe:
            continue
        ziel = ("keywords_muss"
                if kat in KATEGORIE_MUSS and level >= MIN_LEVEL_MUSS
                else "keywords_plus")
        vorschlag = {
            "art": FEHLENDER_SKILL,
            "schluessel": f"{FEHLENDER_SKILL}:{_umschrift(name)}",
            "fingerabdruck": f"{_umschrift(name)}|{level}|{kat}",
            "begriff": name,
            "begriffe": begriffe,
            "level": level,
            "kategorie": kat,
            "ziel": ziel,
            "grund": (f"Im Profil mit Level {level} ({kat}), in keiner "
                      f"Liste — Stellen, die das suchen, bekommen dafür "
                      f"keinen Punkt."),
        }
        if _aktiv(vorschlag):
            fehlend.append(vorschlag)

    # ── 2. Widersprueche ────────────────────────────────────────────
    #
    # Zwei Belege, beide messbar, keiner geraten:
    #
    # (a) Der MINUS-Begriff trifft einen Profil-Skill ueber die
    #     Begriffsgruppierung (#1012).
    # (b) Der MINUS-Begriff steht in einer Stelle, auf die sich der
    #     Mensch SELBST beworben hat — gemessen mit derselben Regel, die
    #     ihn im Score bestraft (`_strict_keyword_match`, #755). Ein
    #     Begriff, den man abwertet und fuer den man sich bewirbt, ist
    #     ein Widerspruch, egal wie er zum Profil steht.
    #
    # Der gemeldete Fall (#1054) braucht (b): "Konfigurationsmanagement"
    # ist im Zielumfeld der Name fuer Aenderungswesen — aber KEINE der
    # drei belegbaren Beziehungen aus `anforderungen` verbindet die
    # beiden Woerter. Ueber das Profil allein waere der Widerspruch
    # unsichtbar; ueber die eigenen Bewerbungen ist er belegt.
    beworbene = _beworbene_stellen(db)
    widersprueche = []
    for begriff in minus:
        treffer_skill = None
        for skill in skills:
            name = str(skill["name"]).strip()
            if anforderungen.dieselbe_anforderung(begriff, name):
                treffer_skill = skill
                break
        # Ein Treffer im TITEL zaehlt immer; im Text erst ab zwei
        # Bewerbungen. Auf der Bestandskopie lagen zwoelf Widersprueche
        # vor, sechs davon mit genau EINEM Texttreffer — ein Wort in
        # einer langen Anzeige, oft in einer Verneinung oder im
        # Firmenabsatz (#827). Wer sich zweimal auf Anzeigen mit dem
        # Begriff bewirbt, oder einmal auf eine, die ihn im Titel
        # traegt, hat ihn nicht versehentlich uebersehen.
        im_titel = [s for s in beworbene if _im_text(begriff, s["titel"])]
        im_text = [s for s in beworbene if _im_text(begriff, s["text"])]
        treffer_bewerbungen = im_titel or (im_text if len(im_text) >= 2 else [])
        if treffer_skill is None and not treffer_bewerbungen:
            continue
        vorschlag = {
            "art": WIDERSPRUCH,
            "schluessel": f"{WIDERSPRUCH}:{_umschrift(begriff)}",
            "begriff": begriff,
            "liste": "keywords_minus",
        }
        belege = []
        if treffer_skill is not None:
            name = str(treffer_skill["name"]).strip()
            level = _level(treffer_skill)
            vorschlag["profil_skill"] = name
            vorschlag["level"] = level
            belege.append(f"trifft deinen Skill '{name}' (Level {level})")
        if treffer_bewerbungen:
            vorschlag["beworbene_stellen"] = [
                {"hash": s["hash"], "titel": s["titel"]}
                for s in treffer_bewerbungen[:5]]
            wo = "im Titel" if im_titel else "im Anzeigentext"
            vorschlag["beleg"] = "titel" if im_titel else "text"
            belege.append(
                f"steht {wo} von {len(treffer_bewerbungen)} Stelle(n), auf "
                f"die du dich beworben hast")
        vorschlag["fingerabdruck"] = "|".join([
            _umschrift(begriff),
            _umschrift(vorschlag.get("profil_skill", "")),
            str(vorschlag.get("level", "")),
            str(len(treffer_bewerbungen)),
        ])
        vorschlag["grund"] = (
            f"MINUS-Begriff {' und '.join(belege)}. Bewusst, weil du die "
            f"Rolle nicht mehr willst — oder ein Fehler?")
        if _aktiv(vorschlag):
            widersprueche.append(vorschlag)

    # ── 3. Rahmenbegriffe in Fachlisten ─────────────────────────────
    orte = _orte(db, profil, krit)
    rahmen = []
    # Das Issue nennt MUSS und PLUS. Die MINUS-Liste kommt fuer
    # Vertragsform und Arbeitsmodell dazu — mit derselben Begruendung:
    # fuer beides gibt es einen Regler (`stellentyp/...`, Remote), und
    # `stellentypen` filtert seit #1023 ohnehin. Auf der Bestandskopie
    # standen sechs Vertragsformen in MINUS, jede davon zusaetzlich als
    # Regler gewertet. Ein Ort in MINUS bleibt: dafuer gibt es keinen
    # Regler, die Liste ist dort der einzige Weg.
    for liste_name, liste, erlaubt in (
            ("keywords_muss", muss, (ARBEITSMODELL, VERTRAGSFORM, ORT, ZUSATZLEISTUNG)),
            ("keywords_plus", plus, (ARBEITSMODELL, VERTRAGSFORM, ORT, ZUSATZLEISTUNG)),
            ("keywords_minus", minus, (ARBEITSMODELL, VERTRAGSFORM))):
        for begriff in liste:
            art = rahmenbegriff_art(begriff, orte)
            if art not in erlaubt:
                continue
            grund = _GEHOERT_ZU[art]
            if liste_name == "keywords_minus":
                grund = (f"{art} in MINUS — `stellentypen` filtert das "
                         "bereits, und der Regler `stellentyp/...` bzw. "
                         "der Remote-Regler wertet es; in der Liste zählt "
                         "es doppelt (scoring_konfigurieren('anzeigen')).")
            vorschlag = {
                "art": RAHMENBEGRIFF,
                "schluessel": f"{RAHMENBEGRIFF}:{liste_name}:{_umschrift(begriff)}",
                "fingerabdruck": f"{_umschrift(begriff)}|{liste_name}",
                "begriff": begriff,
                "liste": liste_name,
                "rahmen_art": art,
                "grund": grund,
            }
            if _aktiv(vorschlag):
                rahmen.append(vorschlag)

    offen = len(fehlend) + len(widersprueche) + len(rahmen)
    return {
        "fehlende_skills": fehlend,
        "widersprueche": widersprueche,
        "rahmenbegriffe": rahmen,
        "offen": offen,
        "verworfen": unterdrueckt,
        "grundlage": {"skills": len(skills), "muss": len(muss),
                      "plus": len(plus), "minus": len(minus)},
    }


def _finde(db, schluessel: str) -> dict | None:
    # Ohne Levelgrenze: wer die Grenze im Werkzeug gesenkt und einen
    # Vorschlag darunter gesehen hat, muss ihn auch uebernehmen und
    # verwerfen koennen.
    ergebnis = abgleich(db, mindest_level=1)
    for liste in ("fehlende_skills", "widersprueche", "rahmenbegriffe"):
        for v in ergebnis[liste]:
            if v["schluessel"] == schluessel:
                return v
    return None


def verwerfen(db, schluessel: str) -> dict:
    """Merkt einen Vorschlag als verworfen (AK 4).

    Gemerkt wird der FINGERABDRUCK: aendert sich das Profil oder die
    Liste an dieser Stelle (anderes Level, Begriff in anderer Liste),
    kommt der Vorschlag wieder — dann ist es ein neuer Sachverhalt.
    """
    vorschlag = _finde(db, schluessel)
    if vorschlag is None:
        return {"fehler": f"Kein offener Vorschlag mit Schluessel '{schluessel}'.",
                "hinweis": "profil_suchbegriffe_abgleichen() nennt die offenen."}
    merk = _verworfen(db)
    merk[schluessel] = vorschlag["fingerabdruck"]
    db.set_profile_setting(MARKE_VERWORFEN, merk)
    return {"status": "verworfen", "schluessel": schluessel,
            "gilt_bis": "Profil oder Liste aendern sich an dieser Stelle"}


def uebernehmen(db, schluessel: str, ziel: str = "") -> dict:
    """Wendet EINEN Vorschlag an — nach Bestaetigung (AK 3).

    * fehlender Skill: Begriff in die Zielliste (`ziel` ueberschreibt
      den Vorschlag: 'keywords_muss' oder 'keywords_plus').
    * Widerspruch: Begriff aus der MINUS-Liste.
    * Rahmenbegriff: Begriff aus der Fachliste. Wohin er stattdessen
      gehoert, steht in der Antwort — er wird NICHT automatisch in einen
      Regler geschrieben, das waere eine zweite Entscheidung.

    Geschrieben wird ueber `db.set_search_criteria`, denselben Weg wie
    `suchkriterien_setzen`.
    """
    vorschlag = _finde(db, schluessel)
    if vorschlag is None:
        return {"fehler": f"Kein offener Vorschlag mit Schluessel '{schluessel}'.",
                "hinweis": "profil_suchbegriffe_abgleichen() nennt die offenen."}
    krit = db.get_search_criteria() or {}
    art = vorschlag["art"]

    if art == FEHLENDER_SKILL:
        liste_name = ziel or vorschlag["ziel"]
        if liste_name not in ("keywords_muss", "keywords_plus"):
            return {"fehler": f"ziel muss keywords_muss oder keywords_plus sein, "
                              f"nicht '{liste_name}'."}
        liste = [str(b) for b in (krit.get(liste_name) or [])]
        # Die bereinigten Suchbegriffe, nicht der rohe Skill-Name — eine
        # Klammer oder ein "&" finden in keiner Anzeige etwas.
        neu = []
        for begriff in vorschlag.get("begriffe") or [vorschlag["begriff"]]:
            if not any(_umschrift(b) == _umschrift(begriff) for b in liste):
                liste.append(begriff)
                neu.append(begriff)
        db.set_search_criteria(liste_name, liste)
        return {"status": "uebernommen", "art": art,
                "begriff": vorschlag["begriff"], "eingetragen": neu,
                "liste": liste_name,
                "naechster_schritt": ("scores_neu_berechnen() — der Fachwert "
                                      "kennt den Begriff erst nach der "
                                      "Neuberechnung.")}

    liste_name = vorschlag["liste"]
    liste = [str(b) for b in (krit.get(liste_name) or [])]
    neu = [b for b in liste if _umschrift(b) != _umschrift(vorschlag["begriff"])]
    if len(neu) == len(liste):
        return {"fehler": f"'{vorschlag['begriff']}' steht nicht mehr in "
                          f"{liste_name}."}
    db.set_search_criteria(liste_name, neu)
    antwort = {"status": "uebernommen", "art": art,
               "begriff": vorschlag["begriff"], "entfernt_aus": liste_name}
    if art == RAHMENBEGRIFF:
        antwort["stattdessen"] = vorschlag["grund"]
    antwort["naechster_schritt"] = "scores_neu_berechnen()"
    return antwort


def kurzfassung(ergebnis: dict) -> str:
    """Ein Satz fuer Hinweis und Werkzeugantworten — mit Zahlen."""
    teile = []
    if ergebnis["fehlende_skills"]:
        namen = ", ".join(v["begriff"] for v in ergebnis["fehlende_skills"][:3])
        teile.append(f"{len(ergebnis['fehlende_skills'])} Profil-Skill(s) in "
                     f"keiner Liste (z.B. {namen})")
    if ergebnis["widersprueche"]:
        namen = ", ".join(v["begriff"] for v in ergebnis["widersprueche"][:3])
        teile.append(f"{len(ergebnis['widersprueche'])} MINUS-Begriff(e) auf "
                     f"dem eigenen Fachgebiet ({namen})")
    if ergebnis["rahmenbegriffe"]:
        namen = ", ".join(v["begriff"] for v in ergebnis["rahmenbegriffe"][:3])
        teile.append(f"{len(ergebnis['rahmenbegriffe'])} Rahmenbegriff(e) in "
                     f"den Fachlisten ({namen})")
    return "; ".join(teile)
