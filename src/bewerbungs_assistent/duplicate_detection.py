"""Duplikat-Erkennung fuer Stellen (#471).

Haertet die Duplikat-Pruefung in stelle_manuell_anlegen gegen:
- Firma mit Klammer-Zusaetzen (z.B. "Systemhaus Nord Ltd." vs. "Systemhaus Nord Ltd. (Endkunde: Anlagenbau Sued)")
- Rechtsform-Suffixe (GmbH, AG, Ltd., KG, ...)
- Titel-Umformulierungen mit gleichem Fachbereich
- Zeitnaehe als zusaetzliches Signal
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Iterable, Optional

# Rechtsform-Suffixe die beim Vergleich ignoriert werden
_LEGAL_SUFFIXES = (
    "gmbh & co. kg", "gmbh & co kg", "gmbh + co kg",
    "ag & co kg", "ag + co kg",
    "gmbh", "ag", "kg", "ohg", "ug", "se",
    "ltd.", "ltd", "limited",
    "inc.", "inc", "llc", "plc",
    "e.v.", "ev", "e. v.",
    "co.", "co", "corp.", "corp",
    "holding", "group", "gruppe",
)

# Domaenen-Keywords: markieren den Fachbereich. v1.7.0-beta.87 (#670):
# NICHT mehr als Standalone-Trigger — nur noch als Bonus in der Titel-
# Aehnlichkeit (_title_similarity). Ein einzelnes geteiltes "PLM" macht
# zwei sonst verschiedene Stellen NICHT zu Duplikaten.
_DOMAIN_KEYWORDS = {
    "plm", "sap", "erp", "cad", "pdm", "ecm", "dms",
    "devops", "sre", "mlops", "qa",
    "teamcenter", "windchill", "aras", "enovia", "3dexperience",
    "solidworks", "catia", "nx", "inventor",
}

# v1.7.0-beta.87 (#670): Schwellwerte fuer die Duplikat-Entscheidung.
# Die Titel-Aehnlichkeit (inkl. Domain-Keyword-Bonus) muss diesen Wert
# erreichen, sonst KEIN Duplikat. Bloße Zeitnaehe oder ein einzelnes
# geteiltes Keyword reichen NICHT mehr.
_TITLE_DUP_THRESHOLD = 0.5
# Unterschiedliche URLs sind ein starkes "verschiedene Stellen"-Signal —
# dann nur bei nahezu identischem Titel als Duplikat werten.
_TITLE_DUP_THRESHOLD_DIFF_URL = 0.85


def normalize_company_name(name: Optional[str]) -> str:
    """Normalisiere Firmennamen fuer Vergleich.

    - lowercase
    - Inhalt in runden Klammern entfernen
    - Rechtsform-Suffixe abschneiden (GmbH, Ltd., ...)
    - Umlaute auf ASCII, uebrige Akzente auf den Grundbuchstaben (#1117)
    - Whitespace und Satzzeichen kollabieren

    Das Ergebnis haengt nur vom Namen ab und wird zwischengespeichert: ein
    Stellenabgleich fragt denselben Namen hundertfach (Stelle x Bewerbung).
    """
    if not name:
        return ""
    return _firma_normalisiert(str(name))


#: Buchstaben mit Strich oder Ligatur zerlegt Unicode nicht in Grundbuchstabe
#: und Akzent - sie brauchen eine eigene Zeile (#1117).
_SONDERBUCHSTABEN = str.maketrans({
    "ø": "o", "æ": "ae", "œ": "oe", "ł": "l", "đ": "d", "ð": "d", "þ": "th",
})


def _akzente_falten(text: str) -> str:
    """Akzente auf den Grundbuchstaben: "Société" -> "Societe" (#1117).

    Der Konzernname traegt den Akzent, die Landesgesellschaft in der
    Anzeige oft nicht - und "societe x" ist kein Teilstring von
    "société x deutschland", der Abgleich verfehlte die Firma. Umlaute sind
    vorher schon ersetzt ("ä" -> "ae"), sonst wuerde daraus ein "a".
    """
    zerlegt = unicodedata.normalize("NFD", text.translate(_SONDERBUCHSTABEN))
    return "".join(z for z in zerlegt if not unicodedata.combining(z))


@lru_cache(maxsize=8192)
def _firma_normalisiert(name: str) -> str:
    n = name.lower().strip()
    # Klammer-Zusaetze entfernen: "Systemhaus Nord Ltd. (Endkunde: ...)" -> "systemhaus nord ltd."
    n = re.sub(r"\([^)]*\)", " ", n)
    # Umlaute
    for uml, repl in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        n = n.replace(uml, repl)
    # Uebrige Akzente und Sonderbuchstaben (#1117)
    n = _akzente_falten(n)
    # Rechtsform-Suffixe iterativ abschneiden (von hinten)
    changed = True
    while changed:
        changed = False
        stripped = n.rstrip(" ,.")
        for suffix in _LEGAL_SUFFIXES:
            if stripped.endswith(" " + suffix) or stripped == suffix:
                stripped = stripped[: -len(suffix)].rstrip(" ,.-&+")
                n = stripped
                changed = True
                break
        else:
            n = stripped
    # Satzzeichen -> Leerzeichen, multiple Spaces kollabieren
    n = re.sub(r"[^\w\s]", " ", n)
    n = re.sub(r"\s+", " ", n).strip()
    return n


#: v1.7.126 (#1076, zweiter Fall): Portale setzen einen Vorspann vor den
#: Titel. "Freelancer Opportunity - Senior Engineering Data Management"
#: gegen denselben Titel ohne Vorspann ergab 0,71 — unter der Schwelle
#: fuer verschiedene URLs (0,85). Verlangt wird ein Trenner MIT
#: Leerzeichen davor, damit "Projekt- und Qualitaetsmanager" bleibt.
_PORTAL_VORSPANN = re.compile(
    r"^\s*(?:freelancer?\s+opportunity|freelance\s+(?:projekt|project|job)"
    r"|job(?:angebot)?|stellenangebot|projekt|project|position|remote\s+job)"
    r"(?:\s+[-–—|]\s+|\s*:\s*)",
    re.IGNORECASE)


def ohne_portal_vorspann(title: Optional[str]) -> str:
    """Titel ohne Vorspann wie "Job:" oder "Freelancer Opportunity -"."""
    return _PORTAL_VORSPANN.sub("", title or "", count=1)


def _title_tokens(title: Optional[str]) -> set[str]:
    """Titel in vergleichbare Tokens zerlegen (ohne Stopwords, ohne Gender-Suffixe)."""
    if not title:
        return set()
    t = ohne_portal_vorspann(title).lower()
    # Gender/Genus Suffixe entfernen
    t = re.sub(r"\(?\s*m\s*[/|]\s*w\s*[/|]?\s*d?\s*\)?", " ", t)
    # Alle Nicht-Wort-Zeichen -> Space
    t = re.sub(r"[^\w\s]", " ", t)
    stop = {
        "und", "oder", "der", "die", "das", "im", "in", "fuer", "für",
        "mit", "von", "zur", "zum", "als", "bei", "auf",
        "via", "for", "and", "or", "the", "a", "an",
        "senior", "junior", "lead", "chief", "principal",
        "m", "w", "d",
    }
    tokens = {w for w in t.split() if len(w) >= 2 and w not in stop}
    return tokens


def _title_similarity(t1: str, t2: str) -> tuple[float, set[str]]:
    """Vergleiche zwei Titel, Rueckgabe (similarity in [0..1], shared tokens).

    Gewichtung: wenn mindestens 1 Domain-Keyword (PLM/SAP/...) gemeinsam ist,
    wirkt das doppelt — sonst waeren zwei PLM-Stellen mit sehr unterschiedlichen
    Titeln nie erkannt.
    """
    a = _title_tokens(t1)
    b = _title_tokens(t2)
    if not a or not b:
        return 0.0, set()
    common = a & b
    if not common:
        return 0.0, set()
    # Jaccard mit Domain-Keyword-Bonus
    jaccard = len(common) / len(a | b)
    domain_hits = common & _DOMAIN_KEYWORDS
    if domain_hits:
        jaccard = min(1.0, jaccard + 0.2 * len(domain_hits))
    return jaccard, common


def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
    """Parse ISO-Timestamp und gib IMMER ein tz-aware datetime zurueck (#565).

    Wenn der Timestamp keine Timezone-Info hat (Legacy-Eintraege), nehmen wir
    UTC an — sonst crasht jede spaetere Subtraktion mit `datetime.now(UTC)`.
    """
    if not ts:
        return None
    try:
        from datetime import timezone
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def find_duplicate_job(
    firma: str,
    titel: str,
    url: str,
    candidates: Iterable[dict],
    *,
    now: Optional[datetime] = None,
    time_window_hours: int = 72,
) -> Optional[dict]:
    """Sucht den staerksten Duplikat-Kandidaten unter ``candidates``.

    Rueckgabe: {"job": <candidate>, "grund": str, "score": float} oder None.

    Regeln (absteigend nach Staerke):
    1. URL exakt gleich (normalisiert)     -> sicher
    2. Normalisierte Firma gleich + (Titel-Sim >= 0.4 ODER Domain-Keyword-Overlap)
    3. Normalisierte Firma gleich + Zeitnaehe < 72h    (Vorsicht-Warnung)
    """
    if not firma or not titel:
        return None

    norm_firma = normalize_company_name(firma)
    url_norm = (url or "").strip().lower().rstrip("/") if url else ""
    # v1.6.9 (#565, #567): tz-aware now — vorher war das naive und crashte
    # gegen aware found_at-Werte aus der DB.
    from datetime import timezone
    now = now or datetime.now(timezone.utc)

    best: Optional[dict] = None
    best_score = 0.0

    for cand in candidates:
        cand_firma = normalize_company_name(cand.get("company") or cand.get("firma"))
        cand_title = cand.get("title") or cand.get("titel") or ""
        cand_url = (cand.get("url") or "").strip().lower().rstrip("/")

        # 1. URL-Match
        if url_norm and cand_url and url_norm == cand_url:
            return {"job": cand, "grund": "url_match", "score": 1.0}

        # Firma muss normalisiert uebereinstimmen (oder Teilmenge, wenn der
        # kuerzere der Basisname ist — z.B. "systemhaus nord" in "systemhaus nord holding").
        if not norm_firma or not cand_firma:
            continue
        firma_match = (
            norm_firma == cand_firma
            or (len(norm_firma) >= 4 and len(cand_firma) >= 4
                and (norm_firma in cand_firma or cand_firma in norm_firma))
        )
        if not firma_match:
            continue

        # 2. Titel-Aehnlichkeit
        sim, common = _title_similarity(titel, cand_title)

        # 3. Zeitnaehe — NUR Tiebreaker im Ranking, NIE Standalone-Trigger (#670)
        cand_ts = _parse_iso(cand.get("found_at") or cand.get("created_at")
                             or cand.get("applied_at"))
        time_bonus = 0.0
        hours_ago = None
        if cand_ts:
            hours_ago = (now - cand_ts).total_seconds() / 3600
            if 0 <= hours_ago <= time_window_hours:
                time_bonus = 0.3 * (1 - hours_ago / time_window_hours)

        # v1.7.0-beta.87 (#670): Entscheidung allein an der Titel-Aehnlichkeit.
        # Vorher triggerte ein einzelnes geteiltes Domain-Keyword ODER bloße
        # Zeitnaehe (ohne Titel-Overlap) einen harten Block — das machte
        # verschiedene Stellen derselben Firma unsichtbar (PLM Project Manager
        # vs PLM Product Owner). Jetzt: `sim` muss ueber den Schwellwert.
        # Das Domain-Keyword zaehlt nur als Bonus IN `sim` (siehe
        # _title_similarity), Zeitnaehe nur als Ranking-Tiebreaker. Wichtig:
        # der Schwellwert-Vergleich passiert auf `sim` (ohne time_bonus),
        # damit Zeitnaehe einen knappen Nicht-Treffer nicht ueber die Grenze hebt.
        urls_differ = bool(url_norm and cand_url and url_norm != cand_url)
        threshold = _TITLE_DUP_THRESHOLD_DIFF_URL if urls_differ else _TITLE_DUP_THRESHOLD
        if sim < threshold:
            continue

        final_score = sim + time_bonus
        if final_score > best_score:
            grund = (
                "firma_plus_domainkeyword" if (common & _DOMAIN_KEYWORDS)
                else "firma_plus_titel_fuzzy"
            )
            best = {
                "job": cand,
                "grund": grund,
                "score": round(final_score, 2),
                "shared_tokens": sorted(common),
                "hours_ago": round(hours_ago, 1) if hours_ago is not None else None,
            }
            best_score = final_score

    return best


@lru_cache(maxsize=8192)
def _stellen_url(url: str) -> str:
    """Die Anzeigen-URL als Vergleichsschluessel - leer, wenn sie keine
    einzelne Anzeige benennt (#1117).

    Dieselbe Bereinigung wie beim Aussortieren (`url_schluessel`: ohne
    Tracking-Parameter, klein, ohne Endstrich). Eine Suchergebnisseite
    benennt keine Anzeige - zwei verschiedene Stellen koennen dieselbe
    haben -, deshalb zaehlt sie nicht als Beleg.
    """
    from .services.stellen_dublette import url_schluessel
    schluessel = url_schluessel(url)
    if not schluessel:
        return ""
    try:
        from .job_scraper import is_search_result_url
        if is_search_result_url(url):
            return ""
    except Exception:  # pragma: no cover - ohne Scraper bleibt der Vergleich gueltig
        pass
    return schluessel


def _url_treffer(url, kandidaten) -> Optional[dict]:
    """Eine Bewerbung auf DIESELBE Anzeige, erkannt an der URL (#1117).

    Rueckgabe in der Form von `find_duplicate_job`, damit die Weiterver-
    arbeitung nur einen Weg kennt.
    """
    schluessel = _stellen_url(str(url or ""))
    if not schluessel:
        return None
    from .services.bewerbung_status import laeuft
    gleiche = [a for a in kandidaten
               if _stellen_url(str(a.get("url") or "")) == schluessel]
    if not gleiche:
        return None
    # Bei mehreren zaehlt die laufende, dann die juengste: sie sagt, was jetzt gilt.
    bester = max(gleiche, key=lambda a: (
        laeuft(a.get("status")),
        a.get("applied_at") or a.get("created_at") or ""))
    return {"job": bester, "grund": "url_match", "score": 1.0}


def bewerbungen_ohne_eigene(job: dict, applications) -> list:
    """Die Bewerbungen, die als "schon beworben" in Frage kommen.

    Ohne die Bewerbung, die an DIESER Stelle haengt (das ist "Bereits
    beworben", keine Wiederholung) und ohne Entwuerfe (`in_vorbereitung`):
    darauf wurde noch nicht beworben.
    """
    eigener = job.get("hash") or ""
    return [
        a for a in applications
        if not (eigener and (a.get("job_hash") or "") == eigener)
        and (a.get("status") or "") != "in_vorbereitung"
    ]


def _repost_texte(*, laeuft: bool, sicher: bool, datum: str, status: str,
                  titel: str, grund, grund_dokumentiert: bool) -> tuple:
    """(kurz, warnung) - der Wortlaut folgt dem Stand der Bewerbung (#1126).

    Eine LAUFENDE Bewerbung ist keine "zweite Chance": dort hilft nur der
    Satz, nicht noch einmal zu bewerben. Der Wortlaut fuer abgeschlossene
    Bewerbungen bleibt wie seit #782/#1083 - samt Absagegrund, nur Datum
    und Status stehen jetzt lesbar da statt als Rohwert.
    """
    from .services.anzeigenamen import datum_text, status_text
    am = f" am {datum_text(datum)}" if datum else ""
    vom = f" vom {datum_text(datum)}" if datum else ""
    stand = status_text(status)
    if laeuft:
        if sicher:
            kurz = f"Schon beworben{am} — die Bewerbung läuft noch"
            warnung = (
                f"Du hast dich auf diese Anzeige bereits{am} beworben "
                f"— die Bewerbung läuft noch (Stand: {stand}). "
                "Nicht noch einmal bewerben.")
        else:
            kurz = f"Schon beworben? Bewerbung{vom} — läuft noch"
            warnung = (
                "Das sieht nach der Stelle aus, auf die du dich"
                f"{am} beworben hast („{titel}“) — die "
                f"Bewerbung läuft noch (Stand: {stand}). Falls es "
                "dieselbe Stelle ist: nicht noch einmal bewerben.")
        return kurz, warnung

    kurz = (f"Schon beworben{am} — {stand}" if sicher else
            f"Schon beworben? Bewerbung{vom} — {stand}")
    kopf = ("Dieselbe Anzeige (gleiche URL): " if sicher
            else "Repost-Verdacht: ")
    # Datum und Status lesbar (G65, #1087 D2): in der Karte steht "12.05.2026
    # - Abgelehnt", und derselbe Kasten darf darunter nicht "2026-05-12" und
    # "abgelehnt" sagen.
    warnung = (
        f"{kopf}Auf diese Stelle wurde{am} bereits "
        f"beworben (Status: {stand}). "
        + (f"Dokumentierter Grund: „{grund['text']}“"
           + (f" (aus {grund.get('dateiname')})"
              if grund.get("quelle") == "dokument" else "") + "."
           if grund else
           "Ablehnungsgrund dokumentiert: ja."
           if grund_dokumentiert else
           "Ablehnungsgrund dokumentiert: NEIN — ob die alte Hürde "
           "noch steht, ist unbekannt.")
        + " Keine automatische Aussortierung — ein Repost kann eine "
        "echte zweite Chance sein."
    )
    return kurz, warnung


def find_repost_of_application(job: dict, applications,
                               db=None) -> Optional[dict]:
    """Repost-Erkennung (#782/C30, v1.7.10): entspricht eine (neu gefundene)
    Stelle einer Bewerbung, die es schon gab?

    Firma + Titel-Aehnlichkeit tragen bewusst OHNE URL-Vergleich: Reposts
    haben praktisch immer eine neue Portal-URL, und die "unterschiedliche
    URLs = verschiedene Stellen"-Regel aus #670 wuerde genau den Repost-Fall
    wegfiltern.

    v1.7.143 (#1117): eine IDENTISCHE URL ist der staerkste denkbare Beleg
    fuer dieselbe Anzeige - und wurde hier nie angesehen. Sie zaehlt jetzt
    ZUSAETZLICH, als hinreichender Treffer (`match_grund` "url_match"),
    nie als notwendige Bedingung: ein Repost mit neuer URL wird weiter
    ueber Firma und Titel erkannt.

    Liefert eine WARNUNG, keine Entscheidung - ein Repost nach Monaten kann
    eine echte zweite Chance sein (neue Ansprechpartner, geaenderte
    Anforderungen, besserer CV). Nichts wird automatisch aussortiert.

    v1.7.127 (#1083): mit `db` nennt die Warnung den dokumentierten
    Grund im Wortlaut - aus der Bewerbung oder aus der verknuepften
    Absagemail. "Ablehnungsgrund dokumentiert: ja" allein hat im
    Praxisfall dazu gefuehrt, dass die Neuausschreibung als zweite
    Chance galt, obwohl der Grund dagegen sprach.

    v1.7.143 (#1126): der Wortlaut folgt dem Stand. Bei einer LAUFENDEN
    Bewerbung steht dort "nicht noch einmal bewerben" statt einer Frage
    nach dem Absagegrund, den es nicht gibt (`laeuft`, `kurz`). Die
    Antwort traegt auch die volle Bewerbungs-ID (`bewerbung_id_voll`) -
    das Dashboard springt damit zur Bewerbung.
    """
    kandidaten = bewerbungen_ohne_eigene(job, applications)
    if not kandidaten:
        return None
    hit = _url_treffer(job.get("url"), kandidaten)
    if not hit:
        hit = find_duplicate_job(
            job.get("company") or "", job.get("title") or "", "", kandidaten)
    if not hit:
        return None
    app = hit["job"]
    from .services.bewerbung_status import laeuft as _laeuft
    laeuft = _laeuft(app.get("status"))
    sicher = hit.get("grund") == "url_match"
    # Der Grund wird auch bei "laufend" nachgeschlagen: steht bei einer
    # Bewerbung im Stand "beworben" schon eine Absage im Bestand, ist das
    # ein Befund (Stand hinkt hinterher) - er gehoert in `repost_details`,
    # nicht unter den Tisch. Der Satz folgt trotzdem dem Stand.
    grund_dokumentiert = bool((app.get("rejection_reason") or "").strip())
    grund = None
    if db is not None:
        try:
            from .services import dokument_text
            grund = dokument_text.ablehnungsgrund(db, app.get("id") or "")
        except Exception:  # pragma: no cover - nie eine Liste stoppen
            grund = None
    if grund:
        grund_dokumentiert = True
    datum = (app.get("applied_at") or app.get("created_at") or "")[:10]
    kurz, warnung = _repost_texte(
        laeuft=laeuft, sicher=sicher, datum=datum,
        status=app.get("status") or "", titel=app.get("title") or "",
        grund=grund, grund_dokumentiert=grund_dokumentiert)
    return {
        "art": "wiederholung",
        "bewerbung_id": (app.get("id") or "")[:8],
        "bewerbung_id_voll": app.get("id") or "",
        "beworben_am": datum,
        "status": app.get("status") or "",
        "laeuft": laeuft,
        "sicher": sicher,
        "titel_damals": app.get("title") or "",
        "firma_damals": app.get("company") or "",
        "ablehnungsgrund_dokumentiert": grund_dokumentiert,
        **({"ablehnungsgrund": grund} if grund else {}),
        "match_grund": hit.get("grund", ""),
        "kurz": kurz,
        "warnung": warnung,
    }


# ---------------------------------------------------------------------------
# v1.7.126 (#1076): zwei Wege, auf denen dieselbe Vakanz unerkannt blieb.
#
# 1. Ein Repost unter NEUEM Titel. Stufe B vergleicht nur Titel und URL,
#    und ein umbenannter Repost hat von beidem nichts mehr gemeinsam —
#    nur den Anzeigentext.
# 2. Eine Bewerbung ueber einen Vermittler. Ihre Firma ist der Vermittler;
#    der Endkunde steht im Klammerzusatz oder in den Notizen. Stufe A
#    vergleicht nur die Firma und sieht ihn nie.
#
# Beides wird GEMELDET, nicht geblockt: die Nutzervorgabe lautet Recall vor
# Praezision, und eine falsch verschmolzene Stelle ist schlimmer als ein
# Hinweis zu viel (#951).
# ---------------------------------------------------------------------------

#: Ab dieser Jaccard-Aehnlichkeit gilt ein Anzeigentext als derselbe.
#: Gemessen am 23.09.2026 ueber 2.098 Paare derselben Firma mit
#: verschiedenem Titel: 29 liegen darueber, die Spitzen sind echte
#: Umbenennungen mit identischem Text.
REPOST_SCHWELLE = 0.5
#: Ohne genug eigenen Text ist ein Vergleich keiner.
REPOST_MIN_SHINGLES = 60


def _shingles(text: Optional[str], n: int = 4) -> set:
    woerter = re.findall(r"[a-zäöüß0-9]+", (text or "").lower())
    return {tuple(woerter[i:i + n]) for i in range(len(woerter) - n + 1)}


def find_inhalt_repost(firma: str, titel: str, beschreibung: str,
                       candidates: Iterable[dict],
                       own_hash: str = "") -> Optional[dict]:
    """Dieselbe Vakanz derselben Firma unter anderem Titel (#1076).

    Firmen-Textbausteine ("Wir sind ...", Benefits) stehen in vielen
    Anzeigen einer Firma und machten verschiedene Rollen gleich — gemessen
    bis zu 100 % Ueberdeckung zwischen "Teamleiter Automatisierung" und
    "PLM Solution Architekt". Verglichen wird deshalb nur, was KEINE dritte
    Anzeige derselben Firma ebenfalls enthaelt.
    """
    norm = normalize_company_name(firma)
    if not norm or len(norm) < 4:
        return None
    neu = _shingles(beschreibung)
    if len(neu) < REPOST_MIN_SHINGLES:
        return None
    gleiche_firma = []
    for c in candidates:
        if own_hash and (c.get("hash") or "").endswith(own_hash):
            continue
        cf = normalize_company_name(c.get("company"))
        if cf and (cf == norm or (len(cf) >= 4 and (cf in norm or norm in cf))):
            gleiche_firma.append((c, _shingles(c.get("description"))))
    best = None
    for i, (cand, sc) in enumerate(gleiche_firma):
        # Gleicher Titel ist Stufe B, nicht dieser Fall.
        sim, _ = _title_similarity(titel, cand.get("title") or "")
        if sim >= _TITLE_DUP_THRESHOLD_DIFF_URL:
            continue
        dritte = set()
        for j, (_c, s) in enumerate(gleiche_firma):
            if j != i:
                dritte |= s
        a, b = neu - dritte, sc - dritte
        if len(a) < REPOST_MIN_SHINGLES or len(b) < REPOST_MIN_SHINGLES:
            continue
        jac = len(a & b) / len(a | b)
        if jac >= REPOST_SCHWELLE and (best is None or jac > best["aehnlichkeit"]):
            best = {"job": cand, "aehnlichkeit": round(jac, 2)}
    return best


def _wortgrenze(name: str, text: str) -> bool:
    return bool(re.search(r"(?<![a-z0-9])" + re.escape(name) + r"(?![a-z0-9])",
                          text))


def find_vermittler_bewerbung(firma: str, applications) -> Optional[dict]:
    """Laufende Bewerbung ueber einen Vermittler beim selben Endkunden (#1076).

    Die Firma der Bewerbung ist der Vermittler; der Endkunde steht im
    Klammerzusatz der Firma ("Vermittler X (Endkunde: Y)") oder in den
    Notizen. Gesucht wird der Name der NEUEN Firma dort — mit
    Wortgrenzen, weil ein kurzer Name sonst in jedem laengeren Wort steckt
    (#970).
    """
    norm = normalize_company_name(firma)
    if not norm or len(norm) < 4:
        return None
    for app in applications:
        app_firma = normalize_company_name(app.get("company"))
        if app_firma == norm:
            continue  # das ist Stufe A
        # v1.7.143 (#1126): auch das Feld `endkunde` - der Endkunde steht bei
        # einer Bewerbung ueber einen Vermittler oft NUR dort, nicht im
        # Klammerzusatz der Firma und nicht in den Notizen.
        roh = " ".join(str(app.get(k) or "")
                       for k in ("company", "notes", "endkunde"))
        for uml, repl in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
            roh = roh.lower().replace(uml, repl)
        # #1117: derselbe Schnitt wie in `normalize_company_name` - der Name
        # ist gefaltet, der Text muss es auch sein, sonst findet "societe"
        # kein "société".
        roh = _akzente_falten(roh)
        roh = re.sub(r"[^\w\s]", " ", roh)
        if _wortgrenze(norm, re.sub(r"\s+", " ", roh)):
            return app
    return None
