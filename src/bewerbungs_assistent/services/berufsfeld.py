"""Berufsfeld, Niveau und Beschaeftigungsform als DREI Angaben (#1070).

Bis v1.7.124 beantwortete EIN Schluessel drei verschiedene Fragen. Die
fuenfzehn Cluster aus #590/#970 mischten:

===========================  ==================================================
In welchem Feld?             service, trade, tech, engineering, health,
                             education, retail_logistics, hospitality,
                             creative, admin_finance
Auf welcher Stufe?           tech_junior, tech_senior, engineering_senior,
                             executive
In welcher Form?             student, freelance
===========================  ==================================================

Daraus folgte die Frage des Melders unmittelbar: es gibt `tech_junior`
und `tech_senior`, weil das Raster ausgerechnet dort feiner ist, und es
gibt kein `health_junior`, weil dort niemand nachgeschaerft hat. Das ist
keine Systematik, sondern Entstehungsgeschichte.

**Und der erste Treffer gewann.** `detect_profile_type` kehrte beim
ersten passenden Zweig zurueck. Gemessen am 21.09.2026:

    Freiberuflicher Senior-Entwickler  -> freelance   (Tech-Signal weg)
    Pflegedienstleitung, 12 Jahre      -> executive   (Pflege-Signal weg)
    Dualer Student im Handwerk         -> student     (Handwerk-Signal weg)

Der Cluster steuert die Quellen-Empfehlung. Eine falsche Einordnung
kostet also nicht ein Etikett, sondern die halbe Trefferliste.

## Woher die Einteilung kommt

Die Klassifikation der Berufe 2010 der Bundesagentur fuer Arbeit loest
dasselbe Problem, indem sie zwei Dimensionen trennt: zehn
**Berufsbereiche** (wo jemand arbeitet) und vier **Anforderungsniveaus**
(wie weit jemand ist). ESCO und ISCO-08 machen es genauso. Jedes Feld
hier traegt seinen Berufsbereich als Herkunft; die Felder sind feiner
als die zehn Bereiche, weil PBP je Feld andere Quellen empfiehlt.

Gemessen an diesem Raster fehlten PBP ganze Bereiche — Landwirtschaft,
Produktion und Fertigung, Verkehr und Logistik getrennt vom Handel,
Schutz und Sicherheit, Recht, Wissenschaft und Forschung. Alle sechs
landeten in `mixed`.

## Abgrenzung zu `berufsbezeichnungen.py`

Dort wird gefragt, **wie derselbe Beruf sonst noch heisst** (Synonyme zu
einem SUCHBEGRIFF, aus der Facette der Jobsuche-API). Hier wird das
EIGENE Profil eingeordnet. Zwei verschiedene Fragen, zwei Module.
"""

from __future__ import annotations

import re
from typing import Optional

# --- Dimension 1: das Feld ------------------------------------------------
#
# Die Begriffslisten sind bewusst nach BERUFSBEZEICHNUNGEN gebaut, nicht
# nach Taetigkeiten (#970): "Pflege" steht auch in "Pflege der
# Kundenbeziehungen", "Erzieher" nicht in einer IT-Anzeige.

BEREICH_GESUNDHEIT = "Gesundheit, Soziales, Lehre und Erziehung"
BEREICH_BAU = "Bau, Architektur und Gebaeudetechnik"
BEREICH_PRODUKTION = "Rohstoffe, Produktion und Fertigung"
BEREICH_AGRAR = "Land- und Forstwirtschaft, Gartenbau"
BEREICH_MINT = "Naturwissenschaft, Geografie und Informatik"
BEREICH_VERKEHR = "Verkehr, Logistik, Schutz und Sicherheit"
BEREICH_KAUFM = ("Kaufmaennische Dienstleistungen, Handel, Vertrieb, "
                 "Hotel und Tourismus")
BEREICH_ORG = "Unternehmensorganisation, Buchhaltung, Recht und Verwaltung"
BEREICH_MEDIEN = ("Sprach-, Geistes- und Gesellschaftswissenschaften, "
                  "Medien, Kunst und Gestaltung")

FELDER: dict[str, dict] = {
    "gesundheit": {
        "name": "Gesundheit / Pflege",
        "bereich": BEREICH_GESUNDHEIT,
        "begriffe": {
            "pflegefachkraft", "pflegefachmann", "pflegefachfrau",
            "altenpfleger", "krankenpfleger", "krankenschwester",
            "gesundheits- und kranken", "intensivpflege",
            "heilerziehungspfleger", "pflegedienst",
            "medizinische fachangestellte", "mfa", "arzthelfer",
            "zahnarzthelfer", "physiotherapeut", "ergotherapeut",
            "logopaed", "logopäd", "hebamme", "rettungssanitaeter",
            "rettungssanitäter", "notfallsanitaeter", "pharmazeutisch",
            "pta ", "mta ", "operationstechnische",
        },
    },
    "bildung": {
        "name": "Erziehung / Bildung",
        "bereich": BEREICH_GESUNDHEIT,
        "begriffe": {
            "erzieher", "erzieherin", "kinderpfleger", "kita", "krippe",
            "sozialpaedagog", "sozialpädagog", "sozialarbeiter",
            "heilpaedagog", "heilpädagog", "lehrer", "lehrerin",
            "dozent", "dozentin", "paedagogische", "pädagogische",
            "schulbegleit", "jugendhilfe", "ausbilder", "trainer/in",
        },
    },
    "handwerk": {
        "name": "Handwerk / Bau",
        "bereich": BEREICH_BAU,
        "begriffe": {
            "elektrik", "elektriker", "schlosser", "schreiner", "tischler",
            "maler", "lackierer", "klempner", "installateur", "dachdecker",
            "maurer", "fliesenleger", "bauhelfer", "kfz-mechan",
            "monteur", "geselle",
            "elektroniker", "mechatroniker", "anlagenmechaniker",
            "industriemechaniker", "zerspanungsmechaniker",
            "werkzeugmechaniker", "metallbauer", "feinwerkmechaniker",
            "verfahrensmechaniker", "betriebstechnik", "gebaeudetechnik",
            "gebäudetechnik", "sanitaer", "sanitär", "heizung", "lueftung",
            "lüftung", "schweisser", "schweißer", "servicetechniker",
            "haustechnik",
        },
    },
    # NEU (#1070): der Berufsbereich "Rohstoffe, Produktion und Fertigung"
    # hatte gar kein Feld. Eine Produktionsmitarbeiterin fiel ueber
    # "produktion" in die Ingenieur-Liste und bekam ab sieben Jahren
    # Konzern-Boards empfohlen.
    "produktion": {
        "name": "Produktion / Fertigung",
        "bereich": BEREICH_PRODUKTION,
        "begriffe": {
            "produktionsmitarbeiter", "produktionshelfer",
            "produktionsfachkraft", "maschinenbediener", "maschinenfuehrer",
            "maschinenführer", "anlagenfuehrer", "anlagenführer",
            "montagemitarbeiter", "montagehelfer", "fertigungsmitarbeiter",
            "chemikant", "papiertechnolog", "textil- und modenaeher",
            "fachkraft fuer lebensmitteltechnik",
            "fachkraft für lebensmitteltechnik", "baecker", "bäcker",
            "fleischer", "metzger", "konditor",
        },
    },
    # NEU (#1070): Berufsbereich "Land- und Forstwirtschaft, Gartenbau".
    "landwirtschaft": {
        "name": "Land- / Forstwirtschaft, Garten",
        "bereich": BEREICH_AGRAR,
        "begriffe": {
            "landwirt", "landwirtin", "tierwirt", "winzer", "gaertner",
            "gärtner", "garten- und landschaftsbau", "galabau",
            "forstwirt", "pferdewirt", "fischwirt", "florist",
            "agrarservice",
        },
    },
    "it": {
        "name": "IT / Software",
        "bereich": BEREICH_MINT,
        "begriffe": {
            "developer", "engineer", "entwickler", "programmierer",
            "softwareentwickler", "softwareentwicklung", "fullstack",
            "backend", "frontend", "devops", "data", "ml", "ai", "ki",
            "architect", "architekt", "cto", "tech-lead", "tech lead",
        },
    },
    "ingenieurwesen": {
        "name": "Ingenieurwesen / Technik",
        "bereich": BEREICH_MINT,
        "begriffe": {
            "konstrukteur", "konstrukteurin", "konstruktion", "techniker",
            "techn. zeichner", "produktion", "fertigung", "qualitaet",
            "instandhalt", "wartung", "maschinenbau", "elektrotechnik",
            "verfahrens", "produktionsingenieur", "vertriebsingenieur",
            "plm", "pdm", "cad", "cae", "cam",
        },
    },
    # NEU (#1070): Forschung und Lehre an Hochschulen fiel durch jedes
    # Raster — "wissenschaftliche Mitarbeiterin" landete in `mixed`.
    "wissenschaft": {
        "name": "Wissenschaft / Forschung",
        "bereich": BEREICH_MINT,
        "begriffe": {
            "wissenschaftliche mitarbeit", "wissenschaftlicher mitarbeit",
            "doktorand", "postdoc", "post-doc", "forschungsassistent",
            "laborant", "biologielaborant", "chemielaborant",
            "forschungsgruppe", "promotionsstelle", "research associate",
            "research scientist",
        },
    },
    # NEU (#1070): Logistik war mit dem Handel in EINEM Cluster. Die
    # Berufe liegen in verschiedenen Berufsbereichen der KldB, und ein
    # Berufskraftfahrer sucht anders als eine Verkaeuferin.
    "logistik": {
        "name": "Verkehr / Logistik",
        "bereich": BEREICH_VERKEHR,
        "begriffe": {
            "lagerist", "kommissionier", "staplerfahrer", "gabelstapler",
            "berufskraftfahrer", "lkw-fahrer", "auslieferungsfahrer",
            "zusteller", "disponent", "spedition", "logistik",
            "versandmitarbeiter", "fachlagerist", "fachkraft fuer lagerlog",
            "fachkraft für lagerlog", "busfahrer", "triebfahrzeugfuehrer",
            "triebfahrzeugführer",
        },
    },
    # NEU (#1070): Schutz und Sicherheit, bisher ohne Feld.
    "sicherheit": {
        "name": "Schutz / Sicherheit",
        "bereich": BEREICH_VERKEHR,
        "begriffe": {
            "sicherheitsmitarbeiter", "sicherheitskraft", "werkschutz",
            "objektschutz", "sicherheitsdienst", "wachmann", "wachdienst",
            "fachkraft fuer schutz und sicherheit",
            "fachkraft für schutz und sicherheit", "pfoertner", "pförtner",
            "feuerwehr", "rettungsdienstleit", "brandschutz",
        },
    },
    "handel": {
        "name": "Handel / Verkauf",
        "bereich": BEREICH_KAUFM,
        "begriffe": {
            "kassier", "verkauf", "verkaeufer", "verkaeuferin",
            "verkäufer", "verkäuferin", "einzelhandel", "filialleiter",
            "filialleitung", "warenverraeumung", "warenverräumung",
            "regalbetreuer", "aussendienst", "außendienst",
            "vertriebsmitarbeiter", "kundenberater",
        },
    },
    "gastgewerbe": {
        "name": "Gastronomie / Hotellerie",
        "bereich": BEREICH_KAUFM,
        "begriffe": {
            "koch", "koechin", "köchin", "chef de partie",
            "commis de cuisine", "restaurantfachmann",
            "restaurantfachfrau", "hotelfachmann", "hotelfachfrau",
            "kuechenhilfe", "küchenhilfe", "servicekraft", "barkeeper",
            "patissier", "hauswirtschaft", "hotel", "gastro", "kellner",
            "kellnerin", "barista", "rezeption",
        },
    },
    "verwaltung": {
        "name": "Verwaltung / Finanzen",
        "bereich": BEREICH_ORG,
        "begriffe": {
            "buchhalter", "buchhaltung", "finanzbuchhalter",
            "bilanzbuchhalter", "lohnbuchhalter", "steuerfachangestellte",
            "controller", "controlling", "sachbearbeiter",
            "sachbearbeitung", "bueromanagement", "büromanagement",
            "kaufmann", "kauffrau", "industriekauf", "buerokauf",
            "bürokauf", "personalsachbearbeit", "assistenz der",
            "sekretaer", "sekretär", "verwaltungsfachangestellte",
        },
    },
    # NEU (#1070): Rechtsberufe, bisher ohne Feld — nur die beiden
    # Fachangestellten-Berufe standen in der Verwaltungsliste.
    "recht": {
        "name": "Recht",
        "bereich": BEREICH_ORG,
        "begriffe": {
            "rechtsanwalt", "rechtsanwaeltin", "rechtsanwältin", "jurist",
            "justiziar", "notar", "syndikus", "wirtschaftspruefer",
            "wirtschaftsprüfer", "steuerberater", "compliance",
            "rechtsanwaltsfachangestellte", "notarfachangestellte",
            "rechtspfleger",
        },
    },
    "medien": {
        "name": "Kreativ / Medien",
        "bereich": BEREICH_MEDIEN,
        "begriffe": {
            "grafikdesign", "grafiker", "mediengestalter",
            "kommunikationsdesign", "art director", "ux-designer",
            "ux designer", "ui-designer", "webdesign", "illustrator/in",
            "fotograf", "videograf", "cutter", "texter", "redakteur",
            "redakteurin", "content creator", "social media manager",
            "marketing manager", "brand manager",
        },
    },
    "dienstleistung": {
        "name": "Service / Dienstleistung",
        "bereich": BEREICH_KAUFM,
        "begriffe": {
            "service", "reinigung", "putzhilfe", "gebaeudereinig",
            "gebäudereinig", "kosmetiker", "friseur", "fusspfleg",
            "fußpfleg", "hausmeister", "kurier",
        },
    },
}

#: Reihenfolge bei GLEICHSTAND: spezifisch vor allgemein. "pflege" steht
#: auch in der Dienstleistungs-Liste, "pflegefachkraft" sagt mehr.
#:
#: Entschieden wird zuerst nach der ZAHL der Treffer; der Rang greift
#: nur, wenn zwei Felder gleich oft treffen. Gemessen am 21.09.2026 hat
#: die erste Fassung dabei "Servicetechniker Aussendienst" dem Handel
#: zugeschlagen: je ein Treffer fuer `aussendienst`, `servicetechniker`
#: und `techniker`, und `handel` stand weiter vorn. Die Fachberufe
#: stehen deshalb vor den kaufmaennischen Sammelbegriffen — ein
#: Aussendienst-Servicetechniker ist Handwerk, kein Vertrieb.
FELD_RANG = [
    "gesundheit", "bildung", "recht", "wissenschaft", "sicherheit",
    "landwirtschaft", "gastgewerbe", "medien", "produktion", "logistik",
    "handwerk", "ingenieurwesen", "it", "verwaltung", "handel",
    "dienstleistung",
]

# --- Dimension 2: das Niveau ---------------------------------------------
#
# Die vier Anforderungsniveaus der KldB 2010.

NIVEAUS: dict[str, str] = {
    "helfer": "Helfer- und Anlerntaetigkeit",
    "fachkraft": "Fachlich ausgerichtete Taetigkeit",
    "spezialist": "Komplexe Spezialistentaetigkeit",
    "experte": "Hoch komplexe Taetigkeit",
    "unbekannt": "Nicht einzuordnen",
}

_HELFER_BEGRIFFE = {
    "helfer", "hilfskraft", "aushilfe", "ungelernt", "anlern",
    "aushilfskraft", "servicekraft", "reinigungskraft",
}

_FACHKRAFT_BEGRIFFE = {
    "geselle", "fachkraft", "facharbeiter", "sachbearbeiter",
    "kaufmann", "kauffrau", "fachangestellte", "assistenz", "assistent",
    "junior", "berufseinsteiger", "trainee",
}

#: Bewusst ENG: nur Bezeichnungen, die eine Fortbildung oder eine
#: herausgehobene Rolle benennen. Drei Begriffe standen im ersten
#: Entwurf und sind wieder raus, weil sie zu breit trafen — "techniker"
#: matcht in "Servicetechniker" (eine Fachkraft), "berater" in
#: "Kundenberater", "consultant" ohne Zusatz in jeder Junior-Rolle einer
#: Beratung.
_SPEZIALIST_BEGRIFFE = {
    "senior", "spezialist", "specialist", "meister", "fachwirt",
    "betriebswirt", "principal", "tech lead", "team lead", "referent",
    "projektleiter", "teamleiter", "expert", "architekt", "architect",
    "senior consultant",
}

_EXPERTE_BEGRIFFE = {
    "geschaeftsfuehrer", "geschäftsführer", "gf", "head of", "leiter",
    "leitung", "ceo", "coo", "cto", "cfo", "vp ", "vorstand",
    "director", "managing director", "bereichsleit", "werkleit",
}

#: Woerter, in denen ein Fuehrungsbegriff nur ZUFAELLIG steckt (#1070).
#:
#: `leiter` matcht als Teilstring in `Begleiter` — gemessen am
#: 21.09.2026 galten **Schulbegleiterin, Alltagsbegleiterin,
#: Integrationsbegleiter und Reisebegleiter** ab zehn Berufsjahren als
#: Fuehrungskraft und bekamen Konzern-Boards empfohlen. Dieselbe Klasse
#: wie "ki" in "Kita" (#970) — und sie trifft wieder genau die Berufe,
#: fuer die PBP ausdruecklich mitgebaut ist.
#:
#: Eine Liste findet nur, was in ihr steht (#742, #1006). Ein fehlender
#: Eintrag bedeutet hier das Verhalten von vorher, also einen zu hohen
#: Niveau-Wert — kein Ausfall, aber ein Grund nachzutragen.
_KEIN_FUEHRUNGSWORT = (
    "begleiter", "begleiterin", "begleitung", "begleitet",
    "gleiter", "gleitung",
)

# --- Dimension 3: die Form -----------------------------------------------

FORMEN: dict[str, str] = {
    "festanstellung": "Festanstellung",
    "freiberuflich": "Freiberuflich / selbststaendig",
    "werkstudent": "Studium / Werkstudent",
    "praktikum": "Praktikum / Ausbildung",
    "unbekannt": "Nicht einzuordnen",
}

_FREIBERUFLICH_BEGRIFFE = {
    "freelance", "freiberuflich", "freelancer", "selbstaendig",
    "selbstständig", "freier mitarbeiter", "auf honorarbasis",
}

_PRAKTIKUM_BEGRIFFE = {
    "praktikant", "praktikum", "auszubildende", "auszubildender",
    "azubi", "volontaer", "volontär", "referendar",
}

_WERKSTUDENT_BEGRIFFE = {
    "werkstudent", "werkstudentin", "studentische hilfskraft", "shk ",
}


# Ab dieser Laenge darf ein Indikator als Teilstring matchen. Darunter
# braucht er Wortgrenzen (#970: "ki" matchte in "Kita").
_TEILSTRING_AB = 4


def treffer(text: str, begriffe) -> list[str]:
    """Alle passenden Indikatoren — nicht nur ob einer passt.

    Kurze Kuerzel brauchen WORTGRENZEN (#970). Laengere duerfen weiter
    als Teilstring matchen, und das muss auch so sein: im Deutschen
    steckt "pflege" in "Intensivpflege", "buchhalter" in
    "Finanzbuchhalterin".
    """
    txt = (text or "").lower()
    gefunden = []
    for kw in sorted(begriffe):
        k = kw.lower().strip()
        if not k:
            continue
        if len(k) >= _TEILSTRING_AB:
            if k in txt:
                gefunden.append(kw)
        elif re.search(r"(?<![\wäöüß])" + re.escape(k) + r"(?![\wäöüß])",
                       txt):
            gefunden.append(kw)
    return gefunden


def _ohne_scheintreffer(text: str) -> str:
    """Entfernt Woerter, in denen ein Fuehrungsbegriff nur zufaellig steckt."""
    txt = (text or "").lower()
    for wort in _KEIN_FUEHRUNGSWORT:
        txt = txt.replace(wort, " ")
    return txt


def berufsjahre(positions: list) -> int:
    """Summe der vollendeten Jahre aus den Position-Datenbereichen."""
    from datetime import datetime
    total = 0
    this_year = datetime.now().year
    for p in positions or []:
        start_raw = (p.get("start_date") or "0000")[:4]
        end_raw = (p.get("end_date") or "")[:4]
        if not start_raw.isdigit():
            continue
        start = int(start_raw)
        if start < 1900:
            continue
        end = int(end_raw) if end_raw.isdigit() else this_year
        total += max(0, end - start)
    return total


def laeuft_studium(profile: dict) -> bool:
    """Heuristik: laufendes Studium = end_year leer/Zukunft + Abschlussart."""
    from datetime import datetime
    this_year = datetime.now().year
    for e in profile.get("education") or []:
        end_str = str(e.get("end_year") or e.get("end_date") or "")[:4]
        is_running = (
            not end_str
            or end_str in ("0", "0000", "")
            or (end_str.isdigit() and int(end_str) >= this_year)
        )
        if not is_running:
            continue
        degree = (e.get("degree") or e.get("type") or e.get("field")
                  or "").lower()
        if any(t in degree for t in (
                "bachelor", "master", "diplom", "studium", "student",
                "phd", "promotion")):
            return True
    return False


def _volltext(profile: dict) -> str:
    """Position-Titel + Kurzbeschreibung + Kompetenzen als ein Suchstring."""
    parts: list = []
    for p in profile.get("positions") or []:
        parts.append(p.get("title") or "")
        parts.append((p.get("description") or "")[:200])
    for s in profile.get("skills") or []:
        parts.append(s.get("name") or "")
    return " ".join(parts)


def _feld_bestimmen(text: str) -> tuple[Optional[str], list[dict]]:
    """ALLE passenden Felder, staerkster zuerst (#1070 Scheibe 1).

    Gewicht = Zahl der getroffenen Indikatoren. Bei Gleichstand
    entscheidet FELD_RANG, also spezifisch vor allgemein.
    """
    alle: list[dict] = []
    for schluessel in FELD_RANG:
        eintrag = FELDER[schluessel]
        gefunden = treffer(text, eintrag["begriffe"])
        if gefunden:
            alle.append({
                "feld": schluessel,
                "name": eintrag["name"],
                "bereich": eintrag["bereich"],
                "gewicht": len(gefunden),
                "begriffe": gefunden[:5],
            })
    if not alle:
        return None, []
    alle.sort(key=lambda e: (-e["gewicht"], FELD_RANG.index(e["feld"])))
    return alle[0]["feld"], alle


def _niveau_bestimmen(titel: str, text: str, jahre: int) -> dict:
    """Anforderungsniveau samt seiner GRUNDLAGE.

    Der Wert allein waere eine Behauptung; `beleg` sagt, ob er aus einer
    Berufsbezeichnung stammt oder nur aus der Zahl der Berufsjahre
    (#989: eine Angabe ohne ihre Grundlage ist keine Auskunft).
    """
    titel_rein = _ohne_scheintreffer(titel)
    text_rein = _ohne_scheintreffer(text)

    if treffer(titel_rein, _EXPERTE_BEGRIFFE) and jahre >= 10:
        return {"niveau": "experte", "beleg": "titel",
                "begriffe": treffer(titel_rein, _EXPERTE_BEGRIFFE)[:3]}
    if treffer(text_rein, _SPEZIALIST_BEGRIFFE):
        return {"niveau": "spezialist", "beleg": "titel",
                "begriffe": treffer(text_rein, _SPEZIALIST_BEGRIFFE)[:3]}
    if treffer(text, _HELFER_BEGRIFFE):
        return {"niveau": "helfer", "beleg": "titel",
                "begriffe": treffer(text, _HELFER_BEGRIFFE)[:3]}
    if treffer(text, _FACHKRAFT_BEGRIFFE):
        return {"niveau": "fachkraft", "beleg": "titel",
                "begriffe": treffer(text, _FACHKRAFT_BEGRIFFE)[:3]}
    # Kein Indikator — dann traegt nur die Erfahrung, und die ist bei
    # `fachkraft` GEDECKELT. Das Anforderungsniveau der KldB beschreibt
    # die KOMPLEXITAET der Taetigkeit, nicht die Dauer: fuenfzehn Jahre
    # am Steuer machen keinen Spezialisten.
    #
    # Der Deckel ist nicht kosmetisch. Ohne ihn wurde jedes Profil ab
    # sieben Berufsjahren zum Spezialisten, und `NIVEAU_QUELLEN` legte
    # Konzern-Boards auf die Empfehlung — gemessen am 21.09.2026 traf
    # das Sicherheitsmitarbeiter, Berufskraftfahrer und
    # Produktionsmitarbeiter. Das ist derselbe Schaden, den #1070
    # meldet, nur durch eine andere Tuer.
    if jahre >= 2:
        return {"niveau": "fachkraft", "beleg": "berufsjahre",
                "begriffe": []}
    return {"niveau": "unbekannt", "beleg": "keiner", "begriffe": []}


#: Wie lange eine beendete Station noch als "aktuell" gilt (#1074).
AKTUELL_JAHRE = 2

_PRAEFERENZ_FORM = {
    "festanstellung": "festanstellung", "fest": "festanstellung",
    "freelance": "freiberuflich", "freiberuflich": "freiberuflich",
    "selbststaendig": "freiberuflich", "selbstaendig": "freiberuflich",
}

_POSITION_FORM = {
    "festanstellung": "festanstellung", "angestellt": "festanstellung",
    "freelance": "freiberuflich", "freiberuflich": "freiberuflich",
    "selbststaendig": "freiberuflich", "selbstaendig": "freiberuflich",
    "werkstudent": "werkstudent", "praktikum": "praktikum",
    "ausbildung": "praktikum",
}


def aktuelle_positionen(positions: list) -> list:
    """Stationen, die laufen oder vor hoechstens AKTUELL_JAHRE endeten (#1074).

    Eine Selbstaendigkeit, die 2018 endete, sagt nichts darueber, in
    welcher Form jemand 2026 arbeiten will — sie schlug aber sieben Jahre
    Festanstellung, weil die Einordnung den ganzen Lebenslauf las.
    """
    from datetime import datetime
    grenze = datetime.now().year - AKTUELL_JAHRE
    aus = []
    for p in positions or []:
        ende = str(p.get("end_date") or "")[:4]
        if p.get("is_current") or not ende.isdigit() or int(ende) >= grenze:
            aus.append(p)
    return aus


def _form_bestimmen(profile: dict, text: str, jahre: int) -> dict:
    """Beschaeftigungsform. Mehrfachnennung ist moeglich und normal.

    #1074: die Reihenfolge der Belege ist eine Rangfolge. Erst was der
    Mensch WILL (Praeferenz `stellentyp`), dann wie er JETZT arbeitet
    (Anstellungsart und Titel der aktuellen Stationen), dann die
    Ausbildung. Beendete Stationen zaehlen nicht. `beides` ist die
    Vorgabe des Erfassungsbogens und damit keine Aussage.
    """
    prefs = profile.get("preferences") or {}
    if isinstance(prefs, str):
        import json
        try:
            prefs = json.loads(prefs) or {}
        except ValueError:
            prefs = {}
    wunsch = _PRAEFERENZ_FORM.get(
        str(prefs.get("stellentyp") or "").strip().lower())

    gefunden: list[str] = []
    beleg = "keiner"
    if wunsch:
        gefunden.append(wunsch)
        beleg = "praeferenz"

    aktuell = aktuelle_positionen(profile.get("positions") or [])
    aus_stationen: list[str] = []
    for pos in aktuell:
        art = _POSITION_FORM.get(
            str(pos.get("employment_type") or "").strip().lower())
        if art:
            aus_stationen.append(art)
    aktueller_text = " ".join(
        f"{p.get('title') or ''} {(p.get('description') or '')[:200]}"
        for p in aktuell) + " " + (profile.get("summary") or "")
    if treffer(aktueller_text, _FREIBERUFLICH_BEGRIFFE):
        aus_stationen.append("freiberuflich")
    if treffer(aktueller_text, _WERKSTUDENT_BEGRIFFE):
        aus_stationen.append("werkstudent")
    if treffer(aktueller_text, _PRAKTIKUM_BEGRIFFE):
        aus_stationen.append("praktikum")
    if not wunsch:
        for art in aus_stationen:
            if art not in gefunden:
                gefunden.append(art)
        if gefunden:
            beleg = "aktuelle_stationen"
    # Ein laufendes Studium gilt immer — auch neben einer Praeferenz.
    if laeuft_studium(profile) and jahre <= 3 and "werkstudent" not in gefunden:
        gefunden.append("werkstudent")
        if beleg == "keiner":
            beleg = "ausbildung"
    if not gefunden:
        # Ohne jeden Hinweis ist eine Festanstellung die haeufigste Form,
        # aber sie ist GERATEN — deshalb `unbekannt` (#989).
        return {"form": "unbekannt", "alle": [], "beleg": "keiner"}
    # Eine Festanstellung neben einer anderen Form schaltet keine Quellen;
    # die spezifische Form steht deshalb vorn.
    gefunden.sort(key=lambda f: f == "festanstellung")
    return {"form": gefunden[0], "alle": gefunden, "beleg": beleg}


def _zieltext(profile: dict, suchbegriffe=None) -> str:
    """Was der Mensch SUCHT, nicht was er war (#1074).

    Kurzprofil, aktive Jobtitel-Vorschlaege und die MUSS-Suchbegriffe.
    Die persoenlichen Notizen bleiben bewusst draussen: dort steht
    "KEIN Vertrieb" genauso wie "Vertrieb", und eine Verneinung erkennt
    eine Begriffsliste nicht.
    """
    teile = [profile.get("summary") or ""]
    for jt in profile.get("suggested_job_titles") or []:
        if isinstance(jt, dict):
            if jt.get("is_active", 1):
                teile.append(jt.get("title") or "")
        else:
            teile.append(str(jt))
    teile.extend(str(b) for b in (suchbegriffe or []))
    return " ".join(t for t in teile if t)


def einordnen(profile: Optional[dict], suchbegriffe=None) -> dict:
    """Ordnet ein Profil in Feld, Niveau und Form ein.

    Rueckgabe:
        {
          "feld": "gesundheit" | None, "feld_name": ..., "bereich": ...,
          "alle_felder": [{feld, name, bereich, gewicht, begriffe}, ...],
          "niveau": "spezialist", "niveau_name": ..., "niveau_beleg": ...,
          "form": "freiberuflich", "formen": [...], "form_beleg": ...,
          "berufsjahre": 12,
          "mehrfach": True,     # mehr als ein Feld getroffen
          "unsicher": True,     # kein Feld getroffen
          "feld_beleg": "ziel" | "lebenslauf" | "keiner",
          "quereinstieg": True, # Ziel-Feld weicht vom Lebenslauf ab
        }

    #1074: das ZIEL geht vor der Herkunft. Die Einordnung steuert, wo PBP
    sucht — fuer einen Quereinsteiger ist das Feld, aus dem er heraus
    will, die falsche Antwort. `suchbegriffe` sind die MUSS-Begriffe;
    Kurzprofil und Jobtitel stehen im Profil selbst.
    """
    if not profile:
        return {
            "feld": None, "feld_name": None, "bereich": None,
            "alle_felder": [],
            "niveau": "unbekannt", "niveau_name": NIVEAUS["unbekannt"],
            "niveau_beleg": "keiner", "niveau_begriffe": [],
            "form": "unbekannt", "formen": [], "form_beleg": "keiner",
            "berufsjahre": 0, "mehrfach": False, "unsicher": True,
            "feld_beleg": "keiner", "lebenslauf_feld": None,
            "quereinstieg": False,
        }

    positions = profile.get("positions") or []
    text = _volltext(profile)
    titel = (positions[0].get("title") if positions else "") or ""
    jahre = berufsjahre(positions)

    lebenslauf_feld, alle_felder = _feld_bestimmen(text)
    ziel = _zieltext(profile, suchbegriffe)
    ziel_feld, ziel_felder = _feld_bestimmen(ziel)
    # Das Ziel ueberstimmt den Lebenslauf nur, wenn dessen Feld im Ziel
    # GAR NICHT vorkommt. Gemessen am 23.09.2026: Kurzprofil und
    # Jobtitel eines PLM-Beraters tragen "Data", "Engineer" und
    # "Architect" — fuer sich genommen IT, und eine reine
    # Mehrheitsregel haette ihn zum Quereinsteiger gemacht. Kommt das
    # bisherige Feld im Ziel vor, ist es Kontinuitaet, kein Wechsel.
    if (ziel_feld and lebenslauf_feld
            and lebenslauf_feld in {e["feld"] for e in ziel_felder}):
        ziel_feld = lebenslauf_feld
        ziel_felder = ([e for e in ziel_felder if e["feld"] == lebenslauf_feld]
                       + [e for e in ziel_felder if e["feld"] != lebenslauf_feld])
    if ziel_feld:
        feld, feld_beleg = ziel_feld, "ziel"
        for e in ziel_felder:
            e["herkunft"] = "ziel"
        schon = {e["feld"] for e in ziel_felder}
        for e in alle_felder:
            e["herkunft"] = "lebenslauf"
        alle_felder = ziel_felder + [e for e in alle_felder
                                     if e["feld"] not in schon]
    else:
        feld = lebenslauf_feld
        feld_beleg = "lebenslauf" if feld else "keiner"
        for e in alle_felder:
            e["herkunft"] = "lebenslauf"
    quereinstieg = bool(ziel_feld and lebenslauf_feld
                        and ziel_feld != lebenslauf_feld)

    niveau = _niveau_bestimmen(titel, text, jahre)
    if quereinstieg:
        # #1074: die Stufe gehoert zur Taetigkeit, nicht zur Person. Wer
        # als Filialleiter Sachbearbeitung sucht, sucht keine
        # Bereichsleitung. Nennt das ZIEL selbst eine Stufe, gilt sie.
        ziel_niveau = _niveau_bestimmen(ziel, ziel, jahre)
        if ziel_niveau["beleg"] == "titel":
            niveau = dict(ziel_niveau, beleg="ziel")
        elif niveau["niveau"] in ("spezialist", "experte"):
            niveau = {"niveau": "fachkraft", "beleg": "quereinstieg",
                      "begriffe": []}
    form = _form_bestimmen(profile, text, jahre)

    return {
        "feld": feld,
        "feld_name": FELDER[feld]["name"] if feld else None,
        "bereich": FELDER[feld]["bereich"] if feld else None,
        "alle_felder": alle_felder,
        "niveau": niveau["niveau"],
        "niveau_name": NIVEAUS[niveau["niveau"]],
        "niveau_beleg": niveau["beleg"],
        "niveau_begriffe": niveau["begriffe"],
        "form": form["form"],
        "formen": form["alle"],
        "form_beleg": form["beleg"],
        "berufsjahre": jahre,
        "mehrfach": len(alle_felder) > 1,
        "unsicher": feld is None,
        "feld_beleg": feld_beleg,
        "lebenslauf_feld": lebenslauf_feld,
        "quereinstieg": quereinstieg,
    }


# === Quellen je Dimension ================================================
#
# Die Empfehlung ergibt sich aus der KOMBINATION statt aus einem
# Schluessel: das Feld bestimmt die Fach- und Regionalportale, die Form
# schaltet Freelance- oder Studenten-Boersen dazu, das Niveau die
# Konzern-Quellen. Ein freiberuflicher Senior-Entwickler bekommt dann
# beides, nicht entweder oder (#1070).
#
# Quellen-IDs muessen im SOURCE_REGISTRY existieren — ein Test prueft das.

#: Die breite deutsche Grundausstattung. Sie steht unter JEDEM Feld,
#: weil sie berufsunabhaengig traegt.
GRUNDQUELLEN = ["bundesagentur", "stellenanzeigen_de", "kimeta",
                "meinestadt", "jobspy_indeed"]

FELD_QUELLEN: dict[str, list[str]] = {
    "gesundheit": GRUNDQUELLEN + ["jobware", "personio"],
    "bildung": GRUNDQUELLEN + ["personio"],
    "handwerk": GRUNDQUELLEN + ["personio"],
    "produktion": GRUNDQUELLEN + ["personio", "jobware"],
    "landwirtschaft": GRUNDQUELLEN,
    "it": ["jobspy_linkedin", "jobspy_indeed", "arbeitnow", "himalayas",
           "remotive", "remoteok", "workable", "personio", "greenhouse"],
    "ingenieurwesen": ["jobspy_linkedin", "ingenieur_de",
                       "stellenanzeigen_de", "personio", "workable",
                       "jobspy_indeed", "ferchau", "hays"],
    "wissenschaft": GRUNDQUELLEN + ["ingenieur_de", "personio"],
    "logistik": GRUNDQUELLEN + ["adzuna"],
    "sicherheit": GRUNDQUELLEN,
    "handel": GRUNDQUELLEN + ["personio"],
    "gastgewerbe": GRUNDQUELLEN,
    "verwaltung": GRUNDQUELLEN + ["jobware", "personio"],
    "recht": GRUNDQUELLEN + ["jobware", "personio", "workable"],
    "medien": ["jobspy_indeed", "stellenanzeigen_de", "personio",
               "workable", "arbeitnow", "bundesagentur", "greenhouse"],
    "dienstleistung": GRUNDQUELLEN + ["personio"],
}

#: Die Form SCHALTET Quellen DAZU, sie ersetzt das Feld nicht. Genau das
#: war der gemeldete Schaden: `freelance` verdraengte das Fachfeld.
FORM_QUELLEN: dict[str, list[str]] = {
    "freiberuflich": ["freelance_de", "freelancermap", "gulp", "solcom",
                      "hays"],
    "werkstudent": ["praktikum_de", "studentjob", "berufsstart"],
    "praktikum": ["praktikum_de", "studentjob", "berufsstart"],
    "festanstellung": [],
    "unbekannt": [],
}

#: Ab `spezialist` kommen Konzern- und Fuehrungsquellen dazu.
NIVEAU_QUELLEN: dict[str, list[str]] = {
    "helfer": [],
    "fachkraft": [],
    "spezialist": ["workday_dax", "jobspy_linkedin", "greenhouse",
                   "workable"],
    "experte": ["workday_dax", "jobspy_linkedin", "greenhouse",
                "workable", "personio"],
    "unbekannt": [],
}

#: Wenn kein Feld erkannt wurde, wird BREIT empfohlen statt schmal
#: (#970/#989): im Zweifel lieber eine Quelle zu viel als die falsche.
UNSICHER_QUELLEN = GRUNDQUELLEN + [
    "jobware", "personio", "workable", "arbeitnow", "adzuna",
]


def quellen_fuer(einordnung: dict) -> dict:
    """Quellen aus der KOMBINATION der drei Angaben.

    Rueckgabe trennt, WOHER jede Quelle kommt — sonst ist von aussen
    nicht zu sehen, ob eine Empfehlung am Feld, an der Form oder am
    Niveau haengt.
    """
    aus_feld = (FELD_QUELLEN.get(einordnung.get("feld") or "")
                or (UNSICHER_QUELLEN if einordnung.get("unsicher") else []))
    aus_form: list[str] = []
    for f in einordnung.get("formen") or []:
        aus_form.extend(FORM_QUELLEN.get(f, []))
    aus_niveau = NIVEAU_QUELLEN.get(einordnung.get("niveau") or "", [])

    reihenfolge: list[str] = []
    for gruppe in (aus_feld, aus_form, aus_niveau):
        for q in gruppe:
            if q not in reihenfolge:
                reihenfolge.append(q)
    return {
        "quellen": reihenfolge,
        "aus_feld": list(dict.fromkeys(aus_feld)),
        "aus_form": list(dict.fromkeys(aus_form)),
        "aus_niveau": list(dict.fromkeys(aus_niveau)),
    }
