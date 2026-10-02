"""JobSpy-basierte Quellen: LinkedIn + Indeed.de (#490).

Wrapper um die MIT-lizenzierte Open-Source-Bibliothek `python-jobspy`
(speedyapply/JobSpy). Deckt LinkedIn und Indeed in einem Aufruf ab,
ohne eigenen Scraper-Code fuer diese Portale zu schreiben oder zu warten.

Hinweise:
    - `python-jobspy` ist eine Opt-In-Dependency im Extra `scraper`.
      Ist das Package nicht installiert, liefert die Suche 0 Treffer mit
      einer deutlichen Log-Meldung statt mit einem Crash.
    - LinkedIn rate-limitet ab ca. Seite 10 pro IP (HTTP 429). Wir
      halten `results_wanted` niedrig und fangen 429 ueber `try/except`
      ab — in dem Fall macht der Aufrufer einfach ohne LinkedIn-Treffer
      weiter, andere Adapter laufen nicht mit rein.
    - Fuer LinkedIn wird bei englischen Keywords ein deutsches Aequivalent
      mitgeschickt — LinkedIn filtert auf DE nur sauber, wenn der Begriff
      ebenfalls deutsch ist (Issue-Hinweis).

Lizenz-Attribution: python-jobspy ist MIT, upstream
https://github.com/speedyapply/JobSpy — in der README verlinkt.
"""

from __future__ import annotations

import logging
from typing import Any

from . import stelle_hash
from .textgrenzen import fuer_speicher

logger = logging.getLogger("bewerbungs_assistent.scraper.jobspy")

# Englische Begriffe, die LinkedIn fuer DE-Treffer zusaetzlich als
# deutsche Query braucht. Konservativ gehalten — es geht um haeufige
# „false friends", nicht um vollstaendige Lokalisierung.
_DE_EQUIVALENTS = {
    "project manager": "Projektleiter",
    "software engineer": "Softwareentwickler",
    "data analyst": "Datenanalyst",
    "product manager": "Produktmanager",
    "devops engineer": "DevOps Ingenieur",
    "consultant": "Berater",
    "plm manager": "PLM Projektleiter",
    "plm": "PLM",
}


class JobSpyAusgefallen(RuntimeError):
    """Alle Abfragen einer Seite sind gescheitert (#1159).

    python-jobspy 1.2.0 wirft bei einem ausgefallenen Board nicht mehr, es loggt nur und liefert
    eine leere Tabelle. Ohne diese Ausnahme wäre ein gesperrtes Indeed oder LinkedIn für PBP eine
    Quelle, die "ok, 0 Treffer" meldet - genau das falsche Grün aus #808, und die Fehlerserie, die
    eine tote Quelle abschaltet (#668), käme nie zusammen. `ratenbegrenzt` sagt, ob die Meldungen
    nach einer Sperre aussehen (HTTP 429/403, Captcha).
    """

    def __init__(self, meldung: str, ratenbegrenzt: bool = False):
        super().__init__(meldung)
        self.ratenbegrenzt = ratenbegrenzt


#: Wie JobSpy seine Logger nennt (`jobspy.util.create_logger`).
_JOBSPY_LOGGER = {"indeed": "JobSpy:Indeed", "linkedin": "JobSpy:LinkedIn",
                  "glassdoor": "JobSpy:Glassdoor", "google": "JobSpy:Google"}

#: Woran eine Sperre in einer JobSpy-Fehlermeldung zu erkennen ist.
_SPERR_HINWEISE = ("429", "403", "too many", "rate limit", "captcha", "forbidden", "blocked")


def _sieht_nach_sperre_aus(meldungen: list[str]) -> bool:
    text = " ".join(meldungen).lower()
    return any(h in text for h in _SPERR_HINWEISE)


class _FehlerSammler(logging.Handler):
    """Sammelt, was JobSpy 1.2 statt einer Ausnahme loggt (nur Stufe ERROR)."""

    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.meldungen: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.meldungen.append(record.getMessage())
        except Exception:  # noqa: BLE001 - ein Logger darf nie die Suche stoeren
            pass


def _ensure_jobspy():
    """Import jobspy lazily. None if package fehlt."""
    try:
        from jobspy import scrape_jobs  # type: ignore
        return scrape_jobs
    except ImportError:
        logger.info(
            "python-jobspy nicht installiert — LinkedIn/Indeed via JobSpy "
            "werden uebersprungen. Install: pip install python-jobspy"
        )
        return None


def _expand_keywords_for_linkedin(keywords: list[str]) -> list[str]:
    """Ergaenzt englische Begriffe um deutsche Aequivalente (#490)."""
    out: list[str] = []
    for kw in keywords:
        out.append(kw)
        eq = _DE_EQUIVALENTS.get(kw.lower().strip())
        if eq and eq not in out:
            out.append(eq)
    return out


def _map_row(row: Any, site: str) -> dict:
    """Mappt eine JobSpy-DataFrame-Zeile auf das PBP-Schema."""
    def _g(name: str, default: str = "") -> str:
        val = row.get(name, default) if hasattr(row, "get") else default
        if val is None:
            return default
        # v1.6.5 (#550): pandas-NaN wuerde zu String "nan" konvertiert werden
        # und dann als Firmenname auftauchen. Abfangen.
        try:
            import math
            if isinstance(val, float) and math.isnan(val):
                return default
        except Exception:
            pass
        s = str(val).strip()
        if s.lower() in ("nan", "none", "null", "<na>"):
            return default
        return s

    title = _g("title")
    company = _g("company", "Nicht angegeben")
    location = _g("location")
    description = _g("description")
    url = _g("job_url_direct") or _g("job_url")
    source_key = f"jobspy_{site}"
    remote_flag = row.get("is_remote") if hasattr(row, "get") else None
    job_type = _g("job_type")

    # #1072: JobSpy setzt `is_remote` bei jedem "remote" im Text — auch
    # bei "bis zu 50 % remote". Der Text entscheidet, der Wert ist nur
    # ein Hinweis, und `False` heisst "kein Stichwort", nicht "vor Ort".
    from ..services import remote_jobspy
    remote = remote_jobspy.bestimmen(title, location, description,
                                     is_remote=remote_flag)

    salary_min, salary_max = _jahresgehalt(row)

    return {
        "hash": stelle_hash(source_key, f"{company} {title}"),
        "title": title,
        "company": company,
        "location": location,
        "url": url,
        "source": source_key,
        "description": fuer_speicher(description),
        "employment_type": _normalize_job_type(job_type),
        # v1.7.84 (#1023): das STRUKTURIERTE Feld der Quelle wird
        # gelesen. `job_type` liefert "parttime"/"fulltime" — bis
        # hierher fiel beides durch bis zum letzten `return` und wurde
        # `festanstellung`. Am Bestand des Melders: 0 von 1.282 Stellen
        # trugen `teilzeit`, waehrend 103 Titel es nennen.
        "arbeitsumfang": _normalize_umfang(job_type),
        "remote_level": remote,
        "salary_min": salary_min,
        "salary_max": salary_max,
    }


#: So viele Zahlungszeiträume hat ein Jahr - dieselben Faktoren wie `jobspy.util.convert_to_annual`.
_JAHRESFAKTOR = {"yearly": 1, "monthly": 12, "weekly": 52, "daily": 260, "hourly": 2080}


def _jahresgehalt(row: Any) -> tuple[int | None, int | None]:
    """Jahresgehalt in Euro aus einer JobSpy-Zeile - Intervall und Währung beachtet (#1159).

    Bis python-jobspy 1.1.82 lieferte Indeed für deutsche Anzeigen praktisch nie ein Gehalt
    (gemessen: 0 von 15 Zeilen), und PBP las `min_amount`/`max_amount` ungeprüft als Jahreswert.
    Seit 1.2.0 kommen Gehälter außerhalb der USA an (gemessen: 2 von 15, `interval=yearly`,
    `currency=EUR`) - und mit ihnen Stundenlöhne und Monatsgehälter. Ein Stundenlohn von 15 als
    Jahresgehalt zu speichern, wäre ein stiller Fehler im Scoring und in der Marktanalyse.

    Deshalb: der Betrag wird mit dem Faktor seines Intervalls auf ein Jahr gerechnet (auch wenn nur
    EIN Betrag da ist - dann wandelt JobSpy selbst nicht um), ein unbekanntes Intervall und eine
    andere Währung als Euro ergeben kein Gehalt. Fehlt das Intervall ganz, gilt "pro Jahr" wie bisher.
    """
    def _roh(name: str):
        val = row.get(name) if hasattr(row, "get") else None
        if val is None or (isinstance(val, float) and val != val):  # None oder NaN
            return None
        return val

    niedrig, hoch = _roh("min_amount"), _roh("max_amount")
    if niedrig is None and hoch is None:
        return None, None
    waehrung = str(_roh("currency") or "").strip().upper()
    if waehrung and waehrung != "EUR":
        return None, None
    faktor = _JAHRESFAKTOR.get(str(_roh("interval") or "yearly").strip().lower())
    if faktor is None:
        return None, None

    def _rechnen(wert):
        try:
            return None if wert is None else int(round(float(wert) * faktor))
        except (TypeError, ValueError):
            return None

    return _rechnen(niedrig), _rechnen(hoch)


def _to_int_or_none(val) -> int | None:
    try:
        if val is None:
            return None
        return int(float(val))
    except (TypeError, ValueError):
        return None


def _normalize_job_type(job_type: str) -> str:
    """JobSpy liefert 'fulltime', 'parttime', 'contract' etc. → PBP-Taxonomy.

    Das ist die ANSTELLUNGSFORM. `parttime` steht hier bewusst NICHT —
    es ist ein Umfang und wird von `_normalize_umfang` gelesen (#1023).
    Bis v1.7.83 nannte dieser Docstring `parttime` und hatte keinen
    Zweig dafuer; jede Teilzeitstelle fiel durch bis zum letzten
    `return` und wurde `festanstellung`.
    """
    t = (job_type or "").lower()
    if "contract" in t or "freelance" in t:
        return "freelance"
    if "intern" in t or "praktik" in t:
        return "praktikum"
    if "student" in t or "werk" in t:
        return "werkstudent"
    if "apprentic" in t or "ausbild" in t:
        return "ausbildung"
    if "temporary" in t or "zeitarbeit" in t:
        return "zeitarbeit"
    return "festanstellung"


def _normalize_umfang(job_type: str) -> str:
    """Der UMFANG aus demselben Feld (#1023).

    `job_type` beantwortet zwei Fragen gleichzeitig, und bis v1.7.83
    wurde nur eine davon gelesen. Nennt das Feld weder Voll- noch
    Teilzeit, bleibt der Umfang leer — die Erkennung faellt dann auf
    den Titel zurueck, statt `vollzeit` zu unterstellen. "Nicht
    genannt" ist nicht "Vollzeit" (#989).
    """
    t = (job_type or "").lower()
    voll = "fulltime" in t or "full_time" in t or "full-time" in t
    teil = "parttime" in t or "part_time" in t or "part-time" in t
    if voll and teil:
        return "beides"
    if teil:
        return "teilzeit"
    if voll:
        return "vollzeit"
    return ""


def _search_site(site: str, keywords: list[str], location: str,
                  max_results: int = 25, hours_old: int = 168,
                  google_search_term: str | None = None,
                  zwischenstand: dict | None = None) -> list[dict]:
    """Einmaliger Aufruf gegen eine einzelne JobSpy-Site.

    `country_indeed` wird IMMER auf "Germany" gesetzt — JobSpy crasht
    intern, wenn None uebergeben wird (Country.from_string ruft .strip()
    auf). Fuer Sites, die das Argument ignorieren (linkedin, glassdoor,
    google), ist das harmlos.
    """
    scrape = _ensure_jobspy()
    if scrape is None:
        return []
    if not keywords:
        return []

    if site == "linkedin":
        keywords = _expand_keywords_for_linkedin(keywords)

    # #500: Wenn die Site nach den ersten 2 Keywords nichts liefert,
    # gehen wir davon aus dass die Quelle gerade blockiert ist (Glassdoor/
    # Google rotieren ihre Anti-Bot-Massnahmen). Das spart Logs und Zeit
    # — fuer Glassdoor mit 30 Keywords wuerden sonst 30 API-Errors
    # geloggt werden.
    consecutive_empty = 0
    _EARLY_STOP_THRESHOLD = 3

    # #1061: Mit `zwischenstand` ist das Gefundene schon waehrend des
    # Laufs sichtbar (dieselbe Liste), und der Suchlauf kann nach dem
    # aktuellen Begriff anhalten lassen. Vorher war alles verloren, was
    # bis zum Budget-Abbruch gefunden war — neun Laeufe, rund 9.600
    # Stellen, null gespeichert.
    jobs: list[dict] = zwischenstand["jobs"] if zwischenstand is not None else []
    if zwischenstand is not None:
        zwischenstand["abfragen"] = len(keywords)
    # #1159: wie viele Abfragen liefen, und wie viele davon scheiterten (Ausnahme ODER ein
    # geloggter Fehler bei leerer Antwort) - sind es alle und gibt es keine Treffer, ist die Seite
    # ausgefallen und wird nicht als "ok, 0 Treffer" gemeldet.
    abgefragt = 0
    gescheitert = 0
    erste_meldung = ""
    ratenbegrenzt = False
    for kw in keywords:
        if zwischenstand is not None and zwischenstand["stopp"].is_set():
            logger.info("JobSpy %s: angehalten nach %d von %d Begriffen",
                        site, zwischenstand["fertig"], len(keywords))
            break
        abgefragt += 1
        sammler = _FehlerSammler()
        jslog = logging.getLogger(_JOBSPY_LOGGER.get(site, f"JobSpy:{site.capitalize()}"))
        jslog.addHandler(sammler)
        try:
            kwargs = dict(
                site_name=[site],
                search_term=kw,
                location=location or "Germany",
                country_indeed="Germany",  # #500: NIE None — crasht
                results_wanted=max_results,
                hours_old=hours_old,
                verbose=0,
            )
            if site == "google":
                # Google-Jobs nutzt `google_search_term` zusaetzlich,
                # damit Google die Anfrage als Job-Suche erkennt.
                kwargs["google_search_term"] = (
                    google_search_term or f"{kw} jobs near {location or 'Germany'}"
                )
            df = scrape(**kwargs)
        except Exception as exc:  # jobspy wirft RateLimitException u.a.
            name = type(exc).__name__
            gescheitert += 1
            erste_meldung = erste_meldung or f"{name}: {exc}"[:200]
            if "429" in str(exc) or "RateLimit" in name:
                ratenbegrenzt = True
                logger.warning("JobSpy %s rate-limited (%s) bei '%s' — ueberspringe Site",
                               site, name, kw)
                break
            logger.warning("JobSpy %s Fehler bei '%s': %s", site, kw, exc)
            if zwischenstand is not None:
                zwischenstand["fertig"] += 1
            continue
        finally:
            jslog.removeHandler(sammler)

        if zwischenstand is not None:
            zwischenstand["fertig"] += 1
        if df is None or getattr(df, "empty", True):
            if sammler.meldungen:
                # JobSpy 1.2 wirft nicht mehr: die leere Antwort ist ein Fehler, wenn er etwas geloggt hat.
                gescheitert += 1
                erste_meldung = erste_meldung or sammler.meldungen[0][:200]
                logger.warning("JobSpy %s: keine Antwort bei '%s' (%s)", site, kw, sammler.meldungen[0][:160])
                if _sieht_nach_sperre_aus(sammler.meldungen):
                    ratenbegrenzt = True
                    logger.warning("JobSpy %s: Anfrage abgelehnt — ueberspringe Site", site)
                    break
            consecutive_empty += 1
            if consecutive_empty >= _EARLY_STOP_THRESHOLD and not jobs:
                logger.info("JobSpy %s: %d aufeinanderfolgende leere Antworten — "
                            "Site vermutlich blockiert, breche ab", site, consecutive_empty)
                break
            continue
        consecutive_empty = 0  # Reset bei Treffern
        for _, row in df.iterrows():
            job = _map_row(row, site)
            # #1071: welcher Begriff die Stelle gebracht hat — damit sich
            # schlechte Suchbegriffe belegen lassen (Anschluss an #783).
            job["suchbegriff"] = kw
            jobs.append(job)
    if not jobs and abgefragt and gescheitert >= abgefragt:
        raise JobSpyAusgefallen(
            f"JobSpy/{site}: {gescheitert} von {abgefragt} Abfragen sind gescheitert"
            + (f" (Ratenbegrenzung?) — zuerst: {erste_meldung}" if ratenbegrenzt else f" — zuerst: {erste_meldung}"),
            ratenbegrenzt=ratenbegrenzt)
    return jobs


def _extract_kw_region(params: dict) -> tuple[list[str], str]:
    """Helper: extrahiert keywords + erste Region aus PBP-params."""
    kw_data = params.get("keywords", {})
    if isinstance(kw_data, dict):
        keywords = kw_data.get("general", [])
        regionen = kw_data.get("regionen", [])
    else:
        keywords = kw_data or []
        regionen = []
    location = regionen[0] if regionen else "Germany"
    return keywords, location


#: Gemessen im Bericht zu #1038: eine LinkedIn-Abfrage mit 25 Treffern
#: dauert 11,3 s — JobSpy wartet zwischen zwei Ergebnisseiten bewusst 3
#: bis 7 s. #1061 mass 14 s. Zwei Messungen, zwei Werte: die Konstante
#: ist deshalb nur noch die UNTERGRENZE, das Budget rechnet mit dem
#: zuletzt gemessenen Wert (`LINKEDIN_MESSWERT_SCHLUESSEL`).
LINKEDIN_SEKUNDEN_JE_ABFRAGE = 12
#: Zuschlag auf den Messwert — LinkedIn schwankt von Lauf zu Lauf.
LINKEDIN_ZUSCHLAG = 1.25
#: Wo der gemessene Wert liegt (settings-Tabelle).
LINKEDIN_MESSWERT_SCHLUESSEL = "jobspy_linkedin_sekunden_je_abfrage"
#: Obergrenze, damit ein haengender Lauf nicht beliebig lange blockiert.
LINKEDIN_BUDGET_MAX = 1200


def linkedin_abfragen(params: dict) -> int:
    """So viele Einzelabfragen schickt `search_jobspy_linkedin` ab.

    Dieselbe Begriffsliste wie die Abfrage selbst (samt deutscher
    Entsprechungen aus #490) — eine zweite Zaehlung liefe bei der naechsten
    Aenderung an der Liste auseinander.
    """
    keywords, _ = _extract_kw_region(params)
    if not keywords:
        return 0
    return len(_expand_keywords_for_linkedin(keywords))


def sekunden_je_abfrage(gemessen: float | None = None) -> float:
    """Rechenwert je Abfrage: der Messwert mit Zuschlag, nie unter der
    Untergrenze (#1061)."""
    basis = max(float(LINKEDIN_SEKUNDEN_JE_ABFRAGE), float(gemessen or 0))
    return basis * LINKEDIN_ZUSCHLAG


def linkedin_langlauf_budget(params: dict, mindestens: int,
                             gemessen: float | None = None) -> int:
    """Wie lange der Suchlauf auf LinkedIn wartet (#1038, #1061).

    Die Dauer waechst mit der Zahl der Suchbegriffe; ein festes Budget war
    fuer 44 Begriffe (rund acht Minuten) nie erreichbar, und das Ergebnis
    wurde verworfen. Seit #1061 mit dem gemessenen Wert je Abfrage statt
    einer Konstanten — 576 s bei gebrauchten 615 s waren 7 % daneben.
    """
    geschaetzt = int(linkedin_abfragen(params) * sekunden_je_abfrage(gemessen)) + 60
    return max(int(mindestens), min(geschaetzt, LINKEDIN_BUDGET_MAX))


def begriffe_im_budget(gemessen: float | None = None) -> int:
    """So viele Suchbegriffe passen in die Obergrenze (#1061, Wunsch 4:
    "weniger Suchbegriffe" ohne Zahl ist schwer umzusetzen)."""
    return max(1, int((LINKEDIN_BUDGET_MAX - 60) / sekunden_je_abfrage(gemessen)))


def search_jobspy_linkedin(params: dict) -> list[dict]:
    """LinkedIn via python-jobspy (#490)."""
    keywords, location = _extract_kw_region(params)
    jobs = _search_site("linkedin", keywords, location, max_results=25,
                        zwischenstand=params.get("_zwischenstand"))
    logger.info("JobSpy/LinkedIn: %d Stellen gefunden", len(jobs))
    return jobs


def search_jobspy_indeed(params: dict) -> list[dict]:
    """Indeed.de via python-jobspy (#490).

    v1.7.126 (#1071): gibt es ein Suchprofil fuer Indeed, sucht die
    automatische Suche mit dessen Begriffen — dieselbe Quelle der Wahrheit
    wie der Browser-Weg. Der Operator `title:(...)` wirkt auch ueber die
    JobSpy-Schnittstelle (gemessen am 22.09.2026).
    """
    keywords, location = _extract_kw_region(params)
    kw_data = params.get("keywords") or {}
    if isinstance(kw_data, dict):
        profil = (kw_data.get("portal_suchbegriffe") or {}).get("indeed")
        if profil:
            keywords = list(profil)
    jobs = _search_site("indeed", keywords, location, max_results=50)
    logger.info("JobSpy/Indeed: %d Stellen gefunden", len(jobs))
    return jobs


def search_jobspy_glassdoor(params: dict) -> list[dict]:
    """Glassdoor.de via python-jobspy (#500)."""
    keywords, location = _extract_kw_region(params)
    jobs = _search_site("glassdoor", keywords, location, max_results=30)
    logger.info("JobSpy/Glassdoor: %d Stellen gefunden", len(jobs))
    return jobs


def search_jobspy_google(params: dict) -> list[dict]:
    """Google Jobs via python-jobspy (#500).

    Massiver Aggregator — Google Jobs indexiert StepStone, Indeed,
    LinkedIn, Stellenanzeigen.de und Dutzende weitere Boards. Per
    JobSpy laeuft die Anfrage automatisiert (im Gegensatz zur
    Chrome-Extension-Variante in google_jobs.py / #501).
    """
    keywords, location = _extract_kw_region(params)
    jobs = _search_site("google", keywords, location, max_results=50)
    logger.info("JobSpy/Google: %d Stellen gefunden", len(jobs))
    return jobs
