"""Newsletter-Ingest — J5 (#525, v1.8.0-beta.4).

Job-Newsletter (StepStone, LinkedIn-Alerts, XING, JobLeads, freelance.de,
...) landen ohnehin als E-Mail in PBP (Thunderbird-Add-on, Watch-Folder,
Upload). Dieser Service erkennt sie und uebernimmt die enthaltenen
Stellen in den Jobs-Pool.

Architektur-Leitplanke (wie #671): **Kernfunktion KI-frei.**

  Ebene 0 (hier, traegt allein) — deterministische Link-Extraktion:
      Job-Detail-URLs bekannter Portale aus dem HTML/Text, Titel aus dem
      Link-Text. Newsletter sind strukturiert — das deckt die Praxis ab.
  Ebene 1 (Ollama, optional)   — Fallback NUR wenn Ebene 0 nichts findet
      und die lokale KI aktiv ist; ueberspringbar ohne Funktionsverlust.

Die uebernommenen Stellen haben meist keine Beschreibung — genau dafuer
greifen die bestehenden Bausteine: #756 fuehrt sie als „unbewertet"
(kein Score-0-Fehlurteil), der #622-Auto-Refetch laedt Beschreibungen
nach, C23 friert den Volltext als Snapshot ein.

Lern-Mechanik (J5.1/J5.2): eingebaute Muster im Code + vom User EINMAL
markierte Quellen in der `newsletter_sources`-Tabelle (Schema v51).
"""
from __future__ import annotations

import html as html_mod
import logging
import re
from typing import Optional

logger = logging.getLogger("bewerbungs_assistent")

# ---------------------------------------------------------------------------
# J5.4: eingebaute Quellen-Muster (Sender-Domain-Substrings, lowercase)
# ---------------------------------------------------------------------------
BUILTIN_SOURCES = [
    {"label": "StepStone", "sender": ("stepstone.de", "stepstone.com")},
    {"label": "LinkedIn Job-Alerts", "sender": ("linkedin.com",)},
    {"label": "XING Job-Alerts", "sender": ("xing.com",)},
    {"label": "JobLeads", "sender": ("jobleads.de", "jobleads.com")},
    {"label": "freelance.de", "sender": ("freelance.de",)},
    {"label": "Indeed", "sender": ("indeed.com", "indeed.de")},
    {"label": "Arbeitsagentur", "sender": ("arbeitsagentur.de",)},
]

# Betreff-Hinweise fuer den generischen Fall (Sender unbekannt, Betreff
# eindeutig). Bewusst konservativ — lieber einmal newsletter_quelle_markieren
# als False-Positives auf normale Korrespondenz.
_SUBJECT_HINTS = (
    "job-alert", "job alert", "jobalarm", "job-empfehlung",
    "neue jobs", "neue stellen", "stellenangebote fuer dich",
    "stellenangebote für dich", "passende jobs", "passende stellen",
    "jobs fuer dich", "jobs für dich", "job-newsletter",
)

# ---------------------------------------------------------------------------
# Job-Detail-URL-Muster der Portale (Ebene 0)
# ---------------------------------------------------------------------------
_PORTAL_URL_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("stepstone", re.compile(r"https?://(?:www\.)?stepstone\.(?:de|com)/(?:stellenangebote--|jobs?/)[^\s\"'<>)\]]+", re.I)),
    ("linkedin", re.compile(r"https?://(?:[\w.]+\.)?linkedin\.com/(?:comm/)?jobs/view/[^\s\"'<>)\]]+", re.I)),
    ("xing", re.compile(r"https?://(?:www\.)?xing\.com/jobs/[a-z0-9][^\s\"'<>)\]]+", re.I)),
    ("indeed", re.compile(r"https?://(?:[\w.]+\.)?indeed\.(?:com|de)/(?:viewjob|rc/clk|pagead/clk)[^\s\"'<>)\]]*", re.I)),
    ("arbeitsagentur", re.compile(r"https?://(?:www\.)?arbeitsagentur\.de/jobsuche/jobdetail/[^\s\"'<>)\]]+", re.I)),
    ("freelance.de", re.compile(r"https?://(?:www\.)?freelance\.de/[Pp]rojekte/[^\s\"'<>)\]]+", re.I)),
    ("jobleads", re.compile(r"https?://(?:www\.)?jobleads\.(?:de|com)/[^\s\"'<>)\]]*(?:job|stelle)[^\s\"'<>)\]]*", re.I)),
]

_ANCHOR_RE = re.compile(r"<a\b[^>]*?href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>",
                        re.I | re.S)
_TAG_RE = re.compile(r"<[^>]+>")
# Tracking-Parameter, die beim Deduplizieren wegfallen
_TRACKING_PARAM_RE = re.compile(
    r"[?&](?:utm_[a-z]+|trk|trkEmail|refId|tracking|mkt_tok|cid|ecid|otpToken|midToken|eid)"
    r"=[^&#]*", re.I)
# Aktions-/Navigationswoerter: ein KURZER Linktext, der NUR aus solchen
# Woertern besteht ("Jetzt ansehen", "Alle Jobs", "Abmelden"), ist kein
# Stellentitel. Echte Titel, die eines der Woerter ENTHALTEN
# ("Haushaltshilfe (m/w/d)"), passieren, weil weitere Woerter dabei sind.
_BOILERPLATE_WORDS = {
    "abmelden", "unsubscribe", "abbestellen", "einstellungen", "hilfe",
    "impressum", "datenschutz", "agb", "browser", "profil", "ansehen",
    "anzeigen", "bewerben", "klicken", "oeffnen", "öffnen", "app",
    "feedback", "kontakt", "login", "anmelden", "jetzt", "hier", "mehr",
    "alle", "neue", "jobs", "stellen", "details", "zum", "zur", "im",
}


def _ist_boilerplate(titel: str) -> bool:
    woerter = re.findall(r"[a-zäöüß]+", (titel or "").lower())
    if not woerter:
        return True
    return len(titel) <= 30 and all(w in _BOILERPLATE_WORDS for w in woerter)


def _sender_domain(sender: str) -> str:
    m = re.search(r"@([\w.-]+)", sender or "")
    return (m.group(1) if m else "").lower()


def erkennung(parsed: dict, db=None) -> Optional[dict]:
    """Prueft, ob eine geparste Mail ein Job-Newsletter ist (J5.1/J5.2).

    Reihenfolge: gelernte Quellen (User-markiert) → eingebaute
    Portal-Sender → konservative Betreff-Hinweise.
    Returns {"label": ..., "erkannt_ueber": ...} oder None.
    """
    sender = (parsed.get("sender") or "").lower()
    domain = _sender_domain(sender)
    subject = (parsed.get("subject") or "").lower()

    if db is not None:
        try:
            for src in db.get_newsletter_sources():
                sp = (src.get("sender_pattern") or "").lower()
                if sp and (sp in sender or sp in domain):
                    subj_p = (src.get("subject_pattern") or "").lower()
                    if not subj_p or subj_p in subject:
                        return {"label": src.get("label") or "Newsletter",
                                "erkannt_ueber": "gelernt"}
        except Exception:
            pass

    for src in BUILTIN_SOURCES:
        if any(s in domain for s in src["sender"]):
            return {"label": src["label"], "erkannt_ueber": "portal"}

    if any(h in subject for h in _SUBJECT_HINTS):
        return {"label": "Job-Newsletter", "erkannt_ueber": "betreff"}
    return None


def _clean_url(url: str) -> str:
    url = html_mod.unescape(url or "").strip()
    return url


def _dedupe_key(url: str) -> str:
    key = _TRACKING_PARAM_RE.sub("", url)
    return key.rstrip("?&#/").lower()


def _clean_titel(raw: str) -> str:
    text = _TAG_RE.sub(" ", raw or "")
    text = html_mod.unescape(text)
    text = re.sub(r"\s+", " ", text).strip(" \t\r\n-–|·»›>")
    return text.strip()


def _titel_firma_split(titel: str) -> tuple[str, str]:
    """Newsletter-Linktexte sind oft 'Titel bei Firma' — konservativ trennen."""
    for sep in (" bei ", " at ", " @ "):
        if sep in titel:
            t, f = titel.split(sep, 1)
            t, f = t.strip(), f.strip(" .,-–")
            if 3 <= len(t) and 2 <= len(f) <= 80:
                return t, f
    return titel, ""


def extract_job_links(body_html: str, body_text: str = "") -> list[dict]:
    """Ebene 0: Job-Detail-Links + Titel aus dem Newsletter ziehen.

    Konservativ: es zaehlen NUR URLs, die einem bekannten Portal-Muster
    entsprechen — generische Link-Heuristiken wuerden Footer-Muell
    („Karriere bei uns") in den Pool spuelen.
    """
    treffer: dict[str, dict] = {}

    def _consider(url: str, linktext: str = ""):
        url = _clean_url(url)
        for portal, pattern in _PORTAL_URL_PATTERNS:
            if pattern.match(url):
                key = _dedupe_key(url)
                titel = _clean_titel(linktext)
                if (not titel or _ist_boilerplate(titel)
                        or not (6 <= len(titel) <= 140)
                        or not re.search(r"[A-Za-zÄÖÜäöüß]{3}", titel)):
                    titel = ""
                vorhanden = treffer.get(key)
                if vorhanden is None:
                    treffer[key] = {"url": url, "titel": titel, "portal": portal}
                elif titel and not vorhanden["titel"]:
                    vorhanden["titel"] = titel
                return

    for m in _ANCHOR_RE.finditer(body_html or ""):
        _consider(m.group(1), m.group(2))
    # Plain-Text-Teil (Text-Newsletter oder HTML ohne Anker-Treffer)
    for _portal, pattern in _PORTAL_URL_PATTERNS:
        for m in pattern.finditer(body_text or ""):
            _consider(m.group(0))

    ergebnisse = []
    for eintrag in treffer.values():
        titel, firma = _titel_firma_split(eintrag["titel"]) if eintrag["titel"] else ("", "")
        ergebnisse.append({
            "titel": titel,
            "firma": firma,
            "url": eintrag["url"],
            "portal": eintrag["portal"],
        })
    return ergebnisse


def _ollama_fallback(db, parsed: dict) -> list[dict]:
    """Ebene 1 (optional): LLM-Extraktion, NUR wenn Ebene 0 leer blieb."""
    try:
        from .llm_service import get_llm_service, TaskKind
        svc = get_llm_service(db)
        status = svc.get_status()
        if not (status.ollama_available and status.user_state == "active"):
            return []
        text = (parsed.get("body_text") or "")[:4000]
        if not text.strip():
            return []
        result = svc.run(TaskKind.EXTRACT_NEWSLETTER_JOBS, {"newsletter_text": text})
        if not result.success:
            return []
        jobs = (result.payload or {}).get("jobs") or []
        sauber = []
        for j in jobs[:20]:
            titel = str(j.get("titel") or "").strip()[:140]
            url = str(j.get("url") or "").strip()
            if titel and url.startswith("http"):
                sauber.append({"titel": titel,
                               "firma": str(j.get("firma") or "").strip()[:80],
                               "url": url, "portal": "ollama"})
        return sauber
    except Exception as exc:  # noqa: BLE001 — Ebene 1 ist strikt optional
        logger.debug("Newsletter-Ollama-Fallback uebersprungen: %s", exc)
        return []


def verarbeite_newsletter(db, parsed: dict, label: str) -> dict:
    """Extrahiert Stellen aus einer Newsletter-Mail und uebernimmt sie.

    Laeuft durch save_jobs — also inkl. Inhalts-Duplikat-Erkennung (#641)
    und Snapshot-Logik (C23). Quelle: ``newsletter:<label>``.
    """
    from ..job_scraper import stelle_hash, calculate_score

    links = extract_job_links(parsed.get("body_html") or "",
                              parsed.get("body_text") or "")
    ebene = "link-extraktion"
    if not links:
        links = _ollama_fallback(db, parsed)
        ebene = "ollama" if links else ebene

    if not links:
        return {"status": "keine_stellen", "label": label,
                "hinweis": ("Keine Job-Links erkannt — unbekanntes "
                            "Newsletter-Format. Die Portal-Muster decken "
                            "StepStone/LinkedIn/XING/Indeed/Arbeitsagentur/"
                            "freelance.de/JobLeads ab.")}

    criteria = db.get_search_criteria() or {}
    quelle = f"newsletter:{label}"[:60]
    jobs = []
    for link in links:
        titel = link["titel"] or f"Stelle aus {label}-Newsletter"
        firma = link["firma"]
        job = {
            "hash": stelle_hash(quelle, link["url"]),
            "title": titel,
            "company": firma,
            "location": "",
            "url": link["url"],
            "source": quelle,
            "description": "",
            "_manual_entry": True,  # bewusste Zulieferung, kein Geo-Dismiss
        }
        try:
            job["score"] = calculate_score(job, criteria)
        except Exception:
            job["score"] = 0
        jobs.append(job)

    stats = db.save_jobs(jobs)
    neu = sum(stats.get("new_per_source", {}).values())
    return {
        "status": "uebernommen",
        "label": label,
        "ebene": ebene,
        "gefunden": len(jobs),
        "neu": neu,
        "duplikate": stats.get("duplikate_erkannt", 0),
        "hinweis": (
            "Die Stellen kommen ohne Beschreibung an: sie erscheinen als "
            "'unbewertet' (#756), der Auto-Refetch (#622) laedt die "
            "Volltexte nach und C23 friert sie als Snapshot ein. Direkt "
            "ansehen: stellen_anzeigen(quelle='" + quelle + "')."
        ),
    }
