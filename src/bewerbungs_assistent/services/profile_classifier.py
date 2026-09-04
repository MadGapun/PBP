"""Profil-Klassifikation + Quellen-Cluster (#590 Aufgabe B).

User-Vorgabe: PBP wird nicht nur fuer High-Performer gebaut. Studenten,
Kassiererinnen, Pfleger, Handwerker — alle sollen sinnvolle Suchquellen
empfohlen bekommen, nicht nur LinkedIn/Workday.

Heuristik laeuft offline auf dem aktuellen Profil und gibt einen
Cluster-Schluessel zurueck. Der Schluessel mappt auf eine empfohlene
Quellen-Liste. Der User behaelt das letzte Wort — Empfehlungen sind
nicht-bindend, er kann jede Quelle einzeln zu-/abschalten.
"""

from __future__ import annotations

import re

from typing import Optional


PROFILE_TYPE_LABELS = {
    "student":            "Student / Werkstudent",
    "service":            "Service / Dienstleistung",
    "trade":              "Handwerk / Trade",
    "tech_junior":        "Tech-Einsteiger (Junior)",
    "tech_senior":        "Tech-Senior",
    "engineering_senior": "Engineering-Senior",
    "freelance":          "Freelancer",
    "executive":          "Fuehrungskraft",
    "health":             "Gesundheit / Pflege",
    "education":          "Erziehung / Bildung",
    "retail_logistics":   "Handel / Logistik",
    "hospitality":        "Gastronomie / Hotellerie",
    "creative":           "Kreativ / Medien",
    "admin_finance":      "Verwaltung / Finanzen",
    "mixed":              "Gemischt / Unbekannt",
}


# Keyword-Indikatoren fuer Service-Berufe (Pflege, Hotel, Gastro, Einzelhandel).
_SERVICE_KEYWORDS = {
    "pflege", "altenpflege", "krankenpflege", "kassier", "verkauf",
    "verkaeufer", "verkaeuferin", "hotel", "gastro", "kellner", "kellnerin",
    "service", "barista", "rezeption", "reinigung", "putzhilfe",
    "einzelhandel", "filialleiter", "filialleitung",
}

_TRADE_KEYWORDS = {
    "elektrik", "elektriker", "schlosser", "schreiner", "tischler",
    "maler", "lackierer", "klempner", "installateur", "dachdecker",
    "maurer", "fliesenleger", "bauhelfer", "kfz-mechan",
    "monteur", "azubi", "geselle", "meister",
    # v1.7.29 (#970): ein Elektroniker mit 15 Jahren Erfahrung landete in
    # "mixed" — die Liste kannte nur den "Elektriker". Ergaenzt um die
    # heute gebraeuchlichen Ausbildungsberufe.
    "elektroniker", "mechatroniker", "anlagenmechaniker",
    "industriemechaniker", "zerspanungsmechaniker", "werkzeugmechaniker",
    "metallbauer", "feinwerkmechaniker", "verfahrensmechaniker",
    "betriebstechnik", "gebaeudetechnik", "gebäudetechnik",
    "sanitaer", "sanitär", "heizung", "lueftung", "lüftung",
    "schweisser", "schweißer", "servicetechniker", "haustechnik",
}

_TECH_KEYWORDS = {
    "developer", "engineer", "entwickler", "programmierer",
    "softwareentwickler", "softwareentwicklung", "fullstack",
    "backend", "frontend", "devops", "data", "ml", "ai", "ki",
    "architect", "architekt", "cto", "tech-lead", "tech lead",
}

_ENGINEERING_KEYWORDS = {
    "konstrukteur", "konstrukteurin", "konstruktion", "techniker",
    "techn. zeichner", "produktion", "fertigung", "qualitaet",
    "instandhalt", "wartung", "maschinenbau", "elektrotechnik",
    "verfahrens", "produktionsingenieur", "vertriebsingenieur",
    "plm", "pdm", "cad", "cae", "cam",
}

# v1.7.29 (#970): Berufsfelder, die bisher komplett fehlten. Gemessen an
# sechs Lebenslaeufen quer durch den Arbeitsmarkt landeten vier von
# sechs in "mixed" mit Confidence 0,30 oder in einem falschen Cluster —
# eine Erzieherin galt als Tech-Einsteigerin.
#
# Die Listen sind bewusst nach BERUFSBEZEICHNUNGEN gebaut, nicht nach
# Taetigkeiten: "Pflege" steht auch in "Pflege der Kundenbeziehungen",
# "Erzieher" nicht in einer IT-Anzeige.

_HEALTH_KEYWORDS = {
    "pflegefachkraft", "pflegefachmann", "pflegefachfrau", "altenpfleger",
    "krankenpfleger", "krankenschwester", "gesundheits- und kranken",
    "intensivpflege", "heilerziehungspfleger", "pflegedienst",
    "medizinische fachangestellte", "mfa", "arzthelfer", "zahnarzthelfer",
    "physiotherapeut", "ergotherapeut", "logopaed", "logopäd",
    "hebamme", "rettungssanitaeter", "rettungssanitäter", "notfallsanitaeter",
    "pharmazeutisch", "pta ", "mta ", "operationstechnische",
}

_EDUCATION_KEYWORDS = {
    "erzieher", "erzieherin", "kinderpfleger", "kita", "krippe",
    "sozialpaedagog", "sozialpädagog", "sozialarbeiter", "heilpaedagog",
    "heilpädagog", "lehrer", "lehrerin", "dozent", "dozentin",
    "paedagogische", "pädagogische", "schulbegleit", "jugendhilfe",
    "ausbilder", "trainer/in",
}

_RETAIL_LOGISTICS_KEYWORDS = {
    "lagerist", "kommissionier", "staplerfahrer", "gabelstapler",
    "berufskraftfahrer", "lkw-fahrer", "auslieferungsfahrer", "zusteller",
    "disponent", "spedition", "logistik", "versandmitarbeiter",
    "warenverraeumung", "warenverräumung", "regalbetreuer",
}

_HOSPITALITY_KEYWORDS = {
    "koch", "koechin", "köchin", "chef de partie", "commis de cuisine",
    "restaurantfachmann", "restaurantfachfrau", "hotelfachmann",
    "hotelfachfrau", "kuechenhilfe", "küchenhilfe", "servicekraft",
    "barkeeper", "patissier", "hauswirtschaft",
}

_CREATIVE_KEYWORDS = {
    "grafikdesign", "grafiker", "mediengestalter", "kommunikationsdesign",
    "art director", "ux-designer", "ux designer", "ui-designer",
    "webdesign", "illustrator/in", "fotograf", "videograf", "cutter",
    "texter", "redakteur", "redakteurin", "content creator",
    "social media manager", "marketing manager", "brand manager",
}

_ADMIN_FINANCE_KEYWORDS = {
    "buchhalter", "buchhaltung", "finanzbuchhalter", "bilanzbuchhalter",
    "lohnbuchhalter", "steuerfachangestellte", "controller", "controlling",
    "sachbearbeiter", "sachbearbeitung", "bueromanagement", "büromanagement",
    "kaufmann", "kauffrau", "industriekauf", "buerokauf", "bürokauf",
    "personalsachbearbeit", "assistenz der", "sekretaer", "sekretär",
    "rechtsanwaltsfachangestellte", "notarfachangestellte",
}


_EXECUTIVE_KEYWORDS = {
    "geschaeftsfuehrer", "geschäftsführer", "gf", "head of", "leiter",
    "leitung", "ceo", "coo", "cto", "cfo", "vp ", "vorstand",
    "director", "managing director",
}

_FREELANCE_KEYWORDS = {
    "freelance", "freiberuflich", "freelancer", "selbstaendig",
    "selbstständig", "freier mitarbeiter",
}


def _years_of_experience(positions: list) -> int:
    """Summe der vollendeten Jahre aus den Position-Datenbereichen."""
    total = 0
    from datetime import datetime
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


def _is_currently_studying(profile: dict) -> bool:
    """Heuristik: laufendes Studium = end_year leer/Zukunft + degree-Indikator."""
    edu = profile.get("education") or []
    from datetime import datetime
    this_year = datetime.now().year
    for e in edu:
        end_raw = (e.get("end_year") or e.get("end_date") or "")
        end_str = str(end_raw)[:4]
        is_running = (
            not end_str
            or end_str in ("0", "0000", "")
            or (end_str.isdigit() and int(end_str) >= this_year)
        )
        if not is_running:
            continue
        degree = (
            e.get("degree") or e.get("type") or e.get("field") or ""
        ).lower()
        if any(t in degree for t in (
            "bachelor", "master", "diplom", "studium", "student",
            "phd", "promotion",
        )):
            return True
    return False


# Ab dieser Laenge darf ein Indikator als Teilstring matchen. Darunter
# braucht er Wortgrenzen.
_TEILSTRING_AB = 4


def _has_keyword_match(text: str, kws: set) -> bool:
    """Trifft einer der Indikatoren im Text?

    v1.7.29 (#970): kurze Kuerzel brauchen WORTGRENZEN. Belegt: das
    Tech-Kuerzel "ki" (kuenstliche Intelligenz) matchte per Teilstring
    auf "Kita" — eine Erzieherin mit acht Jahren Berufserfahrung wurde
    dadurch als Tech-Seniorin mit Confidence 0,85 gefuehrt und bekam
    neun internationale Tech-Boards empfohlen.

    Laengere Indikatoren duerfen weiter als Teilstring matchen, und das
    muss auch so sein: im Deutschen steckt "pflege" in
    "Intensivpflege", "buchhalter" in "Finanzbuchhalterin". Ohne
    Teilstring-Match traefe die Erkennung an Komposita durchgehend
    daneben.
    """
    txt = text.lower()
    for kw in kws:
        kw = kw.lower()
        if len(kw.strip()) >= _TEILSTRING_AB:
            if kw in txt:
                return True
        elif re.search(r"(?<![\wäöüß])" + re.escape(kw.strip())
                       + r"(?![\wäöüß])", txt):
            return True
    return False


def _aggregate_text(profile: dict) -> str:
    """Bringt Position-Titles + Skills + Bezeichnungen in einen Suchstring."""
    parts: list = []
    for p in profile.get("positions") or []:
        parts.append(p.get("title") or "")
        parts.append((p.get("description") or "")[:200])
    for s in profile.get("skills") or []:
        parts.append(s.get("name") or "")
    return " ".join(parts)


def detect_profile_type(profile: Optional[dict]) -> dict:
    """Klassifiziert ein Profil in einen Cluster-Schluessel.

    Rueckgabe:
        {
            "type": "student" | "service" | "trade" | "tech_junior" | ...,
            "confidence": 0.0..1.0,
            "reasons": [...],
            "label": "Mensch-lesbares Label",
        }
    """
    if not profile:
        return {
            "type": "mixed", "confidence": 0.0,
            "reasons": ["Kein Profil"],
            "label": PROFILE_TYPE_LABELS["mixed"],
        }

    positions = profile.get("positions") or []
    text = _aggregate_text(profile)
    years = _years_of_experience(positions)
    studying = _is_currently_studying(profile)
    latest_pos = positions[0] if positions else {}
    latest_title = (latest_pos.get("title") or "").lower()
    reasons: list = []

    # 1. Student — laufendes Studium ueberschreibt fast alles
    if studying and years <= 3:
        reasons.append("laufendes Studium erkannt")
        return {
            "type": "student", "confidence": 0.85,
            "reasons": reasons,
            "label": PROFILE_TYPE_LABELS["student"],
        }

    # 2. Freelance — wenn Position-Titles oder Beschreibung das anzeigen
    if _has_keyword_match(text, _FREELANCE_KEYWORDS):
        reasons.append("Freelance-Indikator in Position oder Skill")
        return {
            "type": "freelance", "confidence": 0.75,
            "reasons": reasons,
            "label": PROFILE_TYPE_LABELS["freelance"],
        }

    # 3. Executive — Title-Indikator + 10+ Jahre
    if _has_keyword_match(latest_title, _EXECUTIVE_KEYWORDS) and years >= 10:
        reasons.append(f"Executive-Title + {years}J Erfahrung")
        return {
            "type": "executive", "confidence": 0.8,
            "reasons": reasons,
            "label": PROFILE_TYPE_LABELS["executive"],
        }

    # 4. Berufsfelder, die bis v1.7.28 komplett fehlten (#970).
    # Sie stehen VOR Handwerk/Service/Tech, weil ihre Bezeichnungen
    # spezifischer sind: "pflege" steht auch in der Service-Liste,
    # aber "pflegefachkraft" sagt mehr als "Dienstleistung".
    # Reihenfolge: spezifisch vor allgemein. Gesundheit und Erziehung
    # zuerst, weil ihre Bezeichnungen eindeutig sind; Verwaltung zuletzt,
    # weil "Sachbearbeiter" in vielen Branchen vorkommt.
    for schluessel, gruppe, hinweis in (
        ("health", _HEALTH_KEYWORDS, "Gesundheits-/Pflege-Indikator"),
        ("education", _EDUCATION_KEYWORDS, "Erziehungs-/Bildungs-Indikator"),
        ("hospitality", _HOSPITALITY_KEYWORDS, "Gastronomie-Indikator"),
        ("creative", _CREATIVE_KEYWORDS, "Kreativ-/Medien-Indikator"),
        ("retail_logistics", _RETAIL_LOGISTICS_KEYWORDS,
         "Handels-/Logistik-Indikator"),
        ("admin_finance", _ADMIN_FINANCE_KEYWORDS,
         "Verwaltungs-/Finanz-Indikator"),
    ):
        if _has_keyword_match(text, gruppe):
            reasons.append(f"{hinweis} (Beruf)")
            return {
                "type": schluessel, "confidence": 0.75,
                "reasons": reasons,
                "label": PROFILE_TYPE_LABELS[schluessel],
            }

    # 5. Trade
    if _has_keyword_match(text, _TRADE_KEYWORDS):
        reasons.append("Handwerk-Indikator (Beruf)")
        return {
            "type": "trade", "confidence": 0.75,
            "reasons": reasons,
            "label": PROFILE_TYPE_LABELS["trade"],
        }

    # 6. Service
    if _has_keyword_match(text, _SERVICE_KEYWORDS):
        reasons.append("Service-Indikator (Beruf)")
        return {
            "type": "service", "confidence": 0.75,
            "reasons": reasons,
            "label": PROFILE_TYPE_LABELS["service"],
        }

    # 7. Engineering Senior
    if _has_keyword_match(text, _ENGINEERING_KEYWORDS) and years >= 5:
        reasons.append(f"Engineering-Indikator + {years}J Erfahrung")
        return {
            "type": "engineering_senior", "confidence": 0.8,
            "reasons": reasons,
            "label": PROFILE_TYPE_LABELS["engineering_senior"],
        }

    # 8. Tech (Junior vs Senior)
    if _has_keyword_match(text, _TECH_KEYWORDS):
        if years >= 7:
            reasons.append(f"Tech-Indikator + {years}J Erfahrung")
            return {
                "type": "tech_senior", "confidence": 0.85,
                "reasons": reasons,
                "label": PROFILE_TYPE_LABELS["tech_senior"],
            }
        reasons.append(f"Tech-Indikator + {years}J Erfahrung (junior)")
        return {
            "type": "tech_junior", "confidence": 0.7,
            "reasons": reasons,
            "label": PROFILE_TYPE_LABELS["tech_junior"],
        }

    # 9. Nichts erkannt. v1.7.29 (#970): das ist ein Achselzucken, kein
    # Ergebnis — und es wird jetzt auch so ausgewiesen. Vorher bekam ein
    # nicht eingeordnetes Profil die KLEINSTE Quellenliste (vier
    # Eintraege), ohne zu erfahren, dass die Zahl aus Ratlosigkeit
    # stammt und nicht aus Passung. Dieselbe Haltung wie bei der
    # unbekannten Entfernung (#965): die Luecke wird benannt, und im
    # Zweifel wird BREIT gesucht statt eng.
    reasons.append("Keine eindeutige Indikator-Gruppe")
    return {
        "type": "mixed", "confidence": 0.3,
        "unsicher": True,
        "reasons": reasons,
        "label": PROFILE_TYPE_LABELS["mixed"],
        "hinweis": (
            "PBP konnte dein Berufsfeld nicht sicher einordnen. Statt zu "
            "raten, empfiehlt es breit — lieber eine Quelle zu viel als "
            "die falsche. Mit suchkriterien_setzen() und einem gepflegten "
            "Profil wird die Empfehlung genauer."),
    }


# === Cluster-Definitionen — Default-Quellen-Empfehlung pro Typ. ===
#
# Quellen-IDs muessen im SOURCE_REGISTRY existieren. Reihenfolge bedeutet
# Empfehlungs-Prioritaet (an erster Stelle = unbedingt aktivieren).
PROFILE_TYPE_CLUSTERS: dict[str, list[str]] = {
    "student": [
        # v1.7.0-beta.36: Student-Cluster mit den dedizierten Quellen
        "praktikum_de", "studentjob", "berufsstart",
        "bundesagentur", "kimeta", "personio", "meinestadt", "arbeitnow",
    ],
    "service": [
        "bundesagentur", "meinestadt", "personio", "jobspy_indeed", "kimeta",
    ],
    "trade": [
        "bundesagentur", "meinestadt", "personio", "kimeta",
    ],
    "tech_junior": [
        "jobspy_indeed", "jobspy_linkedin", "arbeitnow",
        "himalayas", "remotive", "remoteok",
        "workable", "personio", "greenhouse",
    ],
    "tech_senior": [
        # v1.7.0-beta.36: Workday-DAX dazu (Konzern-Stellen)
        "jobspy_linkedin", "workday_dax", "greenhouse", "workable",
        "personio", "himalayas", "remotive", "remoteok", "jobspy_indeed",
    ],
    "engineering_senior": [
        # v1.7.0-beta.36: Workday-DAX als Top-Empfehlung fuer Konzern-Stellen
        "workday_dax", "jobspy_linkedin", "ingenieur_de", "personio",
        "workable", "stellenanzeigen_de", "jobspy_indeed", "ferchau", "hays",
    ],
    "freelance": [
        "freelance_de", "freelancermap", "gulp", "solcom", "hays",
    ],
    "executive": [
        # v1.7.0-beta.36: Workday-DAX fuer Konzern-Fuehrungspositionen
        "workday_dax", "jobspy_linkedin", "personio", "workable", "greenhouse",
    ],
    # v1.7.29 (#970): Berufsfelder, die bisher kein Cluster hatten.
    # Durchgaengig deutsche Generalisten voran — diese Berufe werden
    # ueberwiegend regional besetzt, nicht ueber internationale
    # Tech-Boards.
    "health": [
        "bundesagentur", "meinestadt", "stellenanzeigen_de", "kimeta",
        "jobspy_indeed", "personio", "jobware",
    ],
    "education": [
        "bundesagentur", "meinestadt", "stellenanzeigen_de", "kimeta",
        "jobspy_indeed", "personio",
    ],
    "retail_logistics": [
        "bundesagentur", "meinestadt", "kimeta", "stellenanzeigen_de",
        "jobspy_indeed", "adzuna",
    ],
    "hospitality": [
        "bundesagentur", "meinestadt", "kimeta", "stellenanzeigen_de",
        "jobspy_indeed",
    ],
    "creative": [
        "jobspy_indeed", "stellenanzeigen_de", "personio", "workable",
        "arbeitnow", "bundesagentur", "greenhouse",
    ],
    "admin_finance": [
        "bundesagentur", "stellenanzeigen_de", "jobware", "kimeta",
        "meinestadt", "jobspy_indeed", "personio",
    ],
    # Nicht eingeordnet heisst BREIT, nicht schmal (#970). Vorher standen
    # hier vier Quellen — die kleinste Liste ausgerechnet fuer den Fall,
    # in dem PBP am wenigsten weiss.
    "mixed": [
        "bundesagentur", "stellenanzeigen_de", "meinestadt", "kimeta",
        "jobware", "jobspy_indeed", "personio", "workable", "arbeitnow",
        "adzuna",
    ],
}


def recommend_sources(profile: Optional[dict]) -> dict:
    """Liefert die empfohlenen Quellen fuer das Profil.

    Rueckgabe:
        {
            "type": "...", "label": "...", "confidence": 0.x,
            "reasons": [...],
            "recommended": ["bundesagentur", "kimeta", ...],
            "rationale": "Kurzer Erklaer-Text fuer das UI",
        }
    """
    detection = detect_profile_type(profile)
    cluster_key = detection["type"]
    sources = PROFILE_TYPE_CLUSTERS.get(cluster_key, [])
    if detection.get("unsicher"):
        rationale = (
            f"PBP konnte das Berufsfeld nicht sicher einordnen und "
            f"empfiehlt deshalb BREIT: {len(sources)} Quellen quer durch "
            "die grossen deutschen Portale. Das ist bewusst mehr, nicht "
            "weniger — im Zweifel lieber eine Quelle zu viel. Sobald das "
            "Profil Stationen und Faehigkeiten enthaelt, wird die "
            "Empfehlung genauer."
        )
    else:
        rationale = (
            f"Erkannt als {detection['label']}. PBP empfiehlt diese "
            f"{len(sources)} Quellen — der Empfehlung folgen oder einzelne "
            "Quellen abwaehlen ist jederzeit moeglich."
        )
    return {
        **detection,
        "recommended": sources,
        "rationale": rationale,
    }
