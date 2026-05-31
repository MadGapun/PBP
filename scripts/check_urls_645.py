"""Einmaliger URL-Health-Check fuer die aktive Stellenliste (#645 Backfill).

Parallel HEAD-/GET-Checks mit Body-Markern fuer "Stelle nicht mehr
verfuegbar". Liefert kompakten Report den Claude direkt fuer
stelle_bewerten('passt_nicht', ['sonstiges']) nutzen kann.
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import sys
from urllib.parse import urlparse

import httpx

# (hash, url, firma_kurz, titel_kurz)
STELLEN = [
    ("eabab074", "https://grnh.se/2q6val02teu", "MOIA", "BPM Digital Transformation"),
    ("e536a2b9", "https://recruitingapp-5082.de.umantis.com/Vacancies/40520/Description/2", "Olympus", "ERP Transformation PMO"),
    ("40b3581a", "https://www.arbeitsagentur.de/jobsuche/jobdetail/12336-a26f1201j0445953-S", "netgo", "Principal Data Architect"),
    ("4c4905c1", "https://www.arbeitsagentur.de/jobsuche/jobdetail/13644-287762-S", "Infomotion", "Datenarchitekt"),
    ("67716635", "https://www.arbeitsagentur.de/jobsuche/jobdetail/15548-1577983-1-S", "EY", "Data Platforms Solution Architect"),
    ("2ab45acf", "https://ag.wd3.myworkdayjobs.com/en-US/Airbus/job/Hamburg-Area/Senior-Business-Analyst---Physical-Design--d-f-m-_JR10395055", "Airbus", "Senior BA Physical Design"),
    ("2f089314", "https://nexperia.wd3.myworkdayjobs.com/en-US/careers/job/Hamburg/Head-of-Sourcing--m-f-d----Front-End-BOM_R-20014600", "Nexperia", "Head of Sourcing BOM"),
    ("a7cea30d", "https://www.arbeitsagentur.de/jobsuche/jobdetail/13644-300514-S", "Infomotion", "Senior Datenarchitekt AI"),
    ("eba02204", "https://grnh.se/3okg9w02teu", "MOIA", "Senior Compliance Tooling"),
    ("6437ad0e", "https://www.arbeitsagentur.de/jobsuche/jobdetail/10001-1003103954-S", "RBB", "Solution Architect Analytics"),
    ("baa2e8bc", "https://www.lifesciencenord.de/de/karriere/jobboerse/detail/solution-architect-alle-gender.html", "Life Science Nord", "Solution Architect"),
    ("0917669e", "https://www.arbeitnow.com/jobs/companies/team-passerelle/projektmanagerin-pmo-berlin-313022", "Team Passerelle", "PMO Freelance Berlin"),
    ("49431e59", "https://www.arbeitsagentur.de/jobsuche/jobdetail/12288-4831478777-S", "SIGNAL IDUNA", "Manager IT-Strategie"),
    ("b9ded12b", "https://celverag.recruitee.com/o/consultant-data-analytics-all-levels-genders?source=Indeed", "celver", "Consultant Data & Analytics"),
    ("9bb58e00", "https://karriere.pd-g.de/Managerin-IT-Transformation-Public-Sector-de-j403.html", "PD", "Manager IT-Transformation"),
    ("b155da92", "https://jobs.adesso-group.com/job/Berlin-Lead-Consultant-Product-Lifecycle-Management-%28all-genders%29-BE-10969/978196955/", "adesso", "Lead Consultant PLM"),
    ("ca950dad", "https://www.arbeitsagentur.de/jobsuche/jobdetail/12811-2268210-S", "HPA", "Solution Architect AI"),
    ("65aaea16", "https://www.arbeitsagentur.de/jobsuche/jobdetail/19692-glvzl36fr2-S", "BG Klinikum", "PM Strategie/Transformation"),
    ("bf315b17", "https://www.hamburg-port-authority.de/de/karriere/stellenangebote/Solution-Architect-mwd-AI-de-j4037.html", "HPA-direct", "Solution Architect AI"),
    ("44421663", "https://www.stepstone.de/stellenangebote--Transformation-Lead-m-w-d-Legacy-Systems-Business-Applications-Hamburg-Kabs-Polsterwelt--13756788-inline.html", "Kabs", "Transformation Lead"),
    ("eea8a2fa", "https://www.stepstone.de/stellenangebote--Programm-Management-IT-Transformation-Management-Consultant-m-w-d-Berlin-Hamburg-Koeln-Muenchen-mgm-consulting-partners-GmbH--13708866-inline.html", "mgm", "Programm Mgmt IT Transformation"),
]

# Body-Marker die "Stelle nicht mehr verfuegbar" anzeigen
EXPIRED_MARKERS = [
    re.compile(r"stelle\s+(ist\s+)?bereits\s+vergeben", re.I),
    re.compile(r"diese\s+stelle\s+ist\s+nicht\s+(mehr\s+)?(verf[uü]gbar|aktiv)", re.I),
    re.compile(r"position\s+(is\s+)?(no\s+longer\s+)?(available|filled)", re.I),
    re.compile(r"job\s+(is\s+)?(no\s+longer\s+)?(available|active|posted)", re.I),
    re.compile(r"opportunity\s+no\s+longer\s+available", re.I),
    re.compile(r"stellenangebot\s+ist\s+nicht\s+mehr\s+verf[uü]gbar", re.I),
    re.compile(r"this\s+job\s+(has\s+been\s+)?(filled|closed|removed|expired)", re.I),
    re.compile(r"vacancy\s+(is\s+)?(closed|expired|filled|removed)", re.I),
    re.compile(r"die\s+ausschreibung\s+(ist|wurde)\s+beendet", re.I),
    re.compile(r"stelle\s+(wurde\s+)?besetzt", re.I),
    re.compile(r"diese\s+stelle\s+(wurde|ist)\s+(geschlossen|nicht\s+mehr\s+verf[uü]gbar)", re.I),
    re.compile(r"page\s+not\s+found", re.I),
    # Greenhouse "Job not found":
    re.compile(r"the\s+job\s+you\s+are\s+looking\s+for\s+is\s+not\s+available", re.I),
    re.compile(r"this\s+job\s+is\s+no\s+longer\s+accepting\s+applications", re.I),
    # Arbeitsagentur:
    re.compile(r"die\s+stellenanzeige\s+ist\s+nicht\s+mehr\s+verf[uü]gbar", re.I),
    re.compile(r"keine\s+stellenanzeige\s+gefunden", re.I),
]


def _title_tokens(titel: str) -> set[str]:
    """Signaltragende Tokens aus dem Titel (>=4 Zeichen, lowercase)."""
    tokens = re.findall(r"[A-Za-zÄÖÜäöüß0-9]+", titel.lower())
    stop = {"the", "and", "for", "all", "die", "der", "das", "ein", "und",
            "mit", "von", "zur", "zum", "auf", "des", "bei"}
    return {t for t in tokens if len(t) >= 4 and t not in stop}


def _workday_api_url(html_url: str) -> str | None:
    """Workday-URL -> JSON-API-URL fuer die Stelle.

    Workday rendert per JS, der HTML enthaelt nur einen Skeleton. Die Job-Daten
    kommen ueber `wday/cxs/{tenant}/{site}/job/{path}`. Wenn wir das nicht
    erfolgreich aufloesen, faellt der Caller auf reine HTML-Inspektion zurueck.
    """
    m = re.match(r"^(https://([^/]+\.)?wd\d+\.myworkdayjobs\.com)/(?:[A-Za-z\-]+/)?([^/]+)/job/(.+?)/?$", html_url)
    if not m:
        return None
    base, _, site, path = m.groups()
    tenant = base.split("//", 1)[1].split(".")[0]
    return f"{base}/wday/cxs/{tenant}/{site}/job/{path}"


def check_url(item: tuple[str, str, str, str]) -> dict:
    h, url, firma, titel = item
    out = {"hash": h, "firma": firma, "titel": titel, "url": url}
    if not url:
        out["status"] = "leer"
        return out
    try:
        # GET (kein HEAD weil viele Server HEAD ablehnen oder eigen-routing zeigen)
        with httpx.Client(
            follow_redirects=True,
            timeout=15.0,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/131.0.0.0 Safari/537.36",
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
            },
        ) as client:
            r = client.get(url)
            out["http"] = r.status_code
            out["final_url"] = str(r.url)
            if r.status_code >= 400:
                out["status"] = f"http_{r.status_code}"
                return out
            body = r.text or ""
            out["bytes"] = len(body)
            # Marker-Scan auf den ersten 200 KB
            snippet = body[:200_000]
            for pat in EXPIRED_MARKERS:
                m = pat.search(snippet)
                if m:
                    out["status"] = "expired"
                    out["marker"] = m.group(0)[:80]
                    return out

            # Title-Token-Hit-Check auf dem HTML-Body (fuer alle Quellen die
            # statisch rendern): wenn keiner der signaltragenden Title-Tokens
            # im Body steht, ist die Stelle vermutlich weg/anderer Content.
            tokens = _title_tokens(titel)
            if tokens:
                snippet_l = snippet.lower()
                hits = sum(1 for t in tokens if t in snippet_l)
                out["title_token_hits"] = f"{hits}/{len(tokens)}"
                # Toleranter Schwellwert: mind. 1/3 der Tokens muss matchen.
                # Workday/SPA werden weiter unten gesondert ueber die API
                # bestaetigt; Body-Skeleton hat hier oft 0/N und wird durch
                # die API-Bestaetigung "gerettet".
                body_hit_ok = hits >= max(1, len(tokens) // 3)
            else:
                body_hit_ok = True

            # Workday-Sonderbehandlung: HTML ist nur Skeleton, Stellen-
            # Existenz nur ueber die JSON-API testbar (sonst sieht man
            # vergebene Stellen nicht).
            api = _workday_api_url(url)
            if api:
                try:
                    r2 = client.get(api, headers={"Accept": "application/json"})
                    out["workday_api_status"] = r2.status_code
                    if r2.status_code == 404:
                        out["status"] = "expired"
                        out["marker"] = "workday api 404"
                        return out
                    if r2.status_code >= 400:
                        out["status"] = "expired"
                        out["marker"] = f"workday api http {r2.status_code}"
                        return out
                    # API-200 = Stelle existiert. Title-Cross-Check zur
                    # Sicherheit, falls Workday einen Default-Eintrag liefert.
                    text2 = (r2.text or "").lower()
                    tokens = _title_tokens(titel)
                    hits = sum(1 for t in tokens if t in text2)
                    out["title_token_hits"] = f"{hits}/{len(tokens)}"
                    if tokens and hits < max(1, len(tokens) // 3):
                        out["status"] = "expired"
                        out["marker"] = "workday api title mismatch"
                        return out
                except httpx.RequestError as exc:
                    out["status"] = f"workday_api_err:{type(exc).__name__}"
                    out["error"] = str(exc)[:200]
                    return out
            else:
                # Nicht-Workday: HTML-Body-Title-Match ist autoritativ.
                # Wenn keine Title-Tokens im Body, ist die Stelle weg
                # (Server liefert generischen 404-Replacement oder andere
                # Seite, aber 200 OK).
                if not body_hit_ok:
                    out["status"] = "expired"
                    out["marker"] = "title tokens not found in body"
                    return out
            out["status"] = "ok"
    except httpx.TimeoutException:
        out["status"] = "timeout"
    except httpx.RequestError as exc:
        out["status"] = f"error:{type(exc).__name__}"
        out["error"] = str(exc)[:200]
    except Exception as exc:
        out["status"] = f"unhandled:{type(exc).__name__}"
        out["error"] = str(exc)[:200]
    return out


def main():
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(check_url, STELLEN))
    # Sortiert: erst Probleme, dann ok
    rank = {"http_404": 0, "http_410": 0, "expired": 1, "timeout": 2,
            "leer": 3, "ok": 99}
    def _key(r):
        return rank.get(r.get("status"), 5)
    results.sort(key=_key)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
