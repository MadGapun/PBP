"""LinkedIn ueber die interne Voyager-API im eingeloggten Chrome (#919).

Am 17.08.2026 wurde ein Weg gefunden und vollstaendig durchgespielt, der
stabil funktioniert: 22 Suchbegriffe, 511 deduplizierte Rohtreffer, 59
Volltexte, 3 uebernommene Stellen. Dieses Modul haelt ihn fest, damit er
nicht bei jedem Lauf neu erarbeitet werden muss.

**Warum kein normaler Adapter.** HTTP-Abrufe von aussen blockt LinkedIn
zuverlaessig; nur Requests aus dem eingeloggten Tab heraus laufen durch.
Der Python-Teil kann also nicht selbst holen — er beschreibt, WAS zu
holen ist, und liest hinterher, WAS zurueckkam. Deshalb enthaelt dieses
Modul keine einzige Netzabfrage: URLs und Header bauen, Antworten
zerlegen, Trichter zaehlen. Das macht es nebenbei testbar (AK5:
Regression gegen gespeicherte Antworten).

**Warum der Volltext der eigentliche Punkt ist.** Im Testlauf blieben
von 59 Titeln, die den Vorfilter passiert hatten, nach dem Lesen der
Volltexte 3 uebrig. Der beste Titel-Treffer des ganzen Laufs verlangte
im Fliesstext ein System, das auf der harten Ausschlussliste steht. Ein
Import, der nur Titel und Kurzbeschreibung uebernimmt, haette alle
falschen mit hohem Score eingeliefert. Deshalb ist die Volltext-Pflicht
hier eine Regel und keine Empfehlung (`MIN_BESCHREIBUNG`).
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

# Deutschland. Konfigurierbar, weil PBP nicht davon ausgehen darf, dass
# jeder im selben Land sucht (die Lehre aus #970: der Arbeitsmarkt ist
# groesser als der eigene Ausschnitt).
GEO_ID_DE = "101282230"

# LinkedIn zieht die Versionsnummern dieser Decorations regelmaessig
# hoch. Sie gehoeren deshalb in die Konfiguration und nicht verstreut in
# den Code — bei HTTP 400/426 ist genau das die Ursache, und der Lauf
# soll das SAGEN statt still null Treffer zu melden (#919 Vorschlag 5).
DECORATION_LISTE = ("com.linkedin.voyager.dash.deco.jobs.search."
                    "JobSearchCardsCollection-224")
DECORATION_DETAIL = ("com.linkedin.voyager.deco.jobs.web.shared."
                     "WebFullJobPosting-65")

BASIS = "https://www.linkedin.com"
CARD_TYPE = "com.linkedin.voyager.dash.jobs.JobPostingCard"

# Gemessen am 17.08.: 250-400 ms zwischen den Requests liefen ohne
# Drosselung durch — 511 Trefferzeilen plus 59 Volltexte.
PAUSE_MS = 300
SEITENGROESSE = 25          # count-Maximum der API
MAX_SEITEN = 3              # 3 x 25 = 75 je Suchbegriff

# AK2: keine Anlage ohne belastbaren Anzeigentext. Deutlich ueber
# `datenguete.MIN_BESCHREIBUNG` (50), weil eine LinkedIn-Anzeige, die
# ueberhaupt geladen wurde, 1.500-10.000 Zeichen hat — alles darunter
# heisst, dass der Abruf schiefging.
MIN_BESCHREIBUNG = 500

# Zeitfenster der Suche. LinkedIn nimmt Sekunden als `r<n>`.
FENSTER_WOCHE = 604800
FENSTER_MAX = 2592000       # 30 Tage — mehr liefert die API nicht sinnvoll


def zeitfenster(seit_iso: str = "", jetzt=None) -> str:
    """`timePostedRange` aus dem Abstand zum letzten Lauf (#919 Vorschlag 3).

    Fix `r604800` verliert alles, was zwischen zwei Laeufen mit mehr als
    einer Woche Abstand erschienen ist — und holt bei taeglichen Laeufen
    jedes Mal dieselbe Woche. Gedeckelt auf 30 Tage.
    """
    if not seit_iso:
        return f"r{FENSTER_WOCHE}"
    try:
        d = datetime.fromisoformat(str(seit_iso).replace("Z", "+00:00"))
    except ValueError:
        return f"r{FENSTER_WOCHE}"
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    now = jetzt or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    sekunden = int((now - d).total_seconds())
    # Etwas Ueberlappung, damit an der Grenze nichts durchfaellt.
    sekunden = int(sekunden * 1.2)
    return f"r{max(3600, min(sekunden, FENSTER_MAX))}"


def header(csrf: str) -> dict:
    """Die drei Header, ohne die die API 403 bzw. HTML zurueckgibt."""
    return {
        "csrf-token": csrf,
        "accept": "application/vnd.linkedin.normalized+json+2.1",
        "x-restli-protocol-version": "2.0.0",
    }


def such_url(keyword: str, start: int = 0, geo_id: str = GEO_ID_DE,
             fenster: str = "", decoration: str = DECORATION_LISTE,
             count: int = SEITENGROESSE) -> str:
    """URL der Trefferliste fuer einen Suchbegriff."""
    fenster = fenster or f"r{FENSTER_WOCHE}"
    query = (
        "(origin:JOB_SEARCH_PAGE_KEYWORD_AUTOCOMPLETE,"
        f"keywords:{quote(keyword or '', safe='')},"
        f"locationUnion:(geoId:{geo_id}),"
        f"selectedFilters:(timePostedRange:List({fenster})),"
        "spellCorrectionEnabled:true)"
    )
    return (f"{BASIS}/voyager/api/voyagerJobsDashJobCards"
            f"?decorationId={decoration}"
            f"&count={count}&q=jobSearch&start={int(start)}"
            f"&query={query}")


def detail_url(job_id: str, decoration: str = DECORATION_DETAIL) -> str:
    """URL des Volltexts einer Stelle."""
    return (f"{BASIS}/voyager/api/jobs/jobPostings/{job_id}"
            f"?decorationId={decoration}")


def anzeige_url(job_id: str) -> str:
    """Die Seite, die ein Mensch oeffnet — der Anker der Stelle (#766)."""
    return f"{BASIS}/jobs/view/{job_id}/"


def _text(knoten) -> str:
    """`{'text': '...'}` oder direkt ein String — beides kommt vor."""
    if isinstance(knoten, dict):
        return str(knoten.get("text") or "").strip()
    return str(knoten or "").strip()


def parse_trefferliste(payload) -> list:
    """Die Trefferzeilen aus einer Voyager-Antwort.

    Robust gegen Feldumbauten: was fehlt, bleibt leer, statt den ganzen
    Lauf zu kippen. Fehlt die ID, ist die Zeile allerdings wertlos — dann
    faellt sie heraus.
    """
    treffer = []
    for eintrag in ((payload or {}).get("included") or []):
        if not isinstance(eintrag, dict):
            continue
        if eintrag.get("$type") != CARD_TYPE:
            continue
        urn = str(eintrag.get("preDashNormalizedJobPostingUrn") or "")
        job_id = urn.split(":")[-1] if urn else ""
        if not job_id:
            continue
        fuss = [_text((f or {}).get("text"))
                for f in (eintrag.get("footerItems") or [])
                if isinstance(f, dict)]
        treffer.append({
            "job_id": job_id,
            "titel": _text(eintrag.get("title")),
            "firma": _text(eintrag.get("primaryDescription")),
            "ort": _text(eintrag.get("secondaryDescription")),
            "fusszeile": [f for f in fuss if f],
            "url": anzeige_url(job_id),
        })
    return treffer


def parse_detail(payload) -> dict:
    """Der Volltext einer Stelle aus der Detail-Antwort."""
    daten = (payload or {}).get("data")
    if not isinstance(daten, dict):
        daten = payload if isinstance(payload, dict) else {}
    beschreibung = _text((daten.get("description") or {}))
    remote = daten.get("workRemoteAllowed")
    return {
        "beschreibung": beschreibung,
        "ort": str(daten.get("formattedLocation") or "").strip(),
        "remote": "remote" if remote else ("unbekannt" if remote is None
                                           else "vor_ort"),
        "bewerber": daten.get("applies"),
        "anstellungsart": str(daten.get("employmentStatus") or "").strip(),
        "branchen": daten.get("formattedIndustries") or [],
        "veroeffentlicht_am": daten.get("originalListedAt"),
        "bewerbungs_url": str(daten.get("jobPostingUrl") or "").strip(),
    }


def dedupliziert(treffer_listen) -> list:
    """Ueber alle Suchbegriffe hinweg: jede Job-ID genau einmal.

    22 Suchbegriffe ergaben 511 EINDEUTIGE Treffer — ohne Deduplizierung
    waeren es ein Vielfaches gewesen, und jeder davon haette einen
    Volltext-Abruf gekostet.
    """
    gesehen, out = set(), []
    for liste in treffer_listen:
        for t in (liste or []):
            jid = t.get("job_id")
            if not jid or jid in gesehen:
                continue
            gesehen.add(jid)
            out.append(t)
    return out


def fehlerklasse(status: int) -> str:
    """Was ein HTTP-Status auf diesen Endpunkten bedeutet.

    Die stille Null ist hier der teure Fall: LinkedIn antwortet auf eine
    veraltete Decoration-ID mit 400/426, und ohne Einordnung sieht das
    aus wie "gerade keine passenden Stellen".
    """
    status = int(status or 0)
    if status in (400, 426):
        return "decoration_veraltet"
    if status in (401, 403):
        return "nicht_eingeloggt"
    if status == 429:
        return "gedrosselt"
    if status >= 500:
        return "linkedin_stoerung"
    if status >= 400:
        return "unbekannter_fehler"
    return ""


FEHLER_TEXTE = {
    "decoration_veraltet": (
        "LinkedIn hat die Decoration-ID hochgezogen (HTTP 400/426). Das ist "
        "kein leeres Ergebnis, sondern ein veralteter Aufruf: die aktuelle "
        "ID steht im Netzwerk-Tab eines echten LinkedIn-Jobsuchlaufs und "
        "gehoert dann in linkedin_voyager.DECORATION_LISTE bzw. "
        "DECORATION_DETAIL."),
    "nicht_eingeloggt": (
        "Kein gueltiger Login im Chrome-Tab (HTTP 401/403). Erst bei "
        "LinkedIn anmelden, dann den Lauf wiederholen — die Quelle bleibt "
        "aktiv und wartet."),
    "gedrosselt": (
        "LinkedIn drosselt (HTTP 429). Pause zwischen den Requests "
        "erhoehen und spaeter fortsetzen; bereits geholte Treffer sind "
        "nicht verloren."),
    "linkedin_stoerung": (
        "LinkedIn antwortet mit einem Serverfehler — kein Befund ueber "
        "den Stellenmarkt, spaeter erneut versuchen."),
    "unbekannter_fehler": (
        "Unerwartete Antwort von LinkedIn. Der Lauf gilt als "
        "fehlgeschlagen, nicht als leer."),
}


def trichter_leer() -> dict:
    """Die Zaehlung, die jeder Lauf mitfuehrt (AK4).

    Ohne sie ist "0 uebernommen" nicht von "0 gefunden" zu unterscheiden
    — dieselbe Verwechslung, die #813 und #989 beschreiben.
    """
    return {"rohtreffer": 0, "nach_vorfilter": 0, "volltexte": 0,
            "angelegt": 0, "uebersprungen": 0, "gruende": {}}


def trichter_text(trichter: dict) -> str:
    """Eine Zeile, die den ganzen Lauf erklaert."""
    t = trichter or {}
    zeile = (f"{t.get('rohtreffer', 0)} Rohtreffer -> "
             f"{t.get('nach_vorfilter', 0)} nach Vorfilter -> "
             f"{t.get('volltexte', 0)} Volltexte -> "
             f"{t.get('angelegt', 0)} angelegt")
    gruende = t.get("gruende") or {}
    if gruende:
        top = sorted(gruende.items(), key=lambda x: -x[1])
        zeile += " (uebersprungen: " + ", ".join(
            f"{k} {v}" for k, v in top) + ")"
    return zeile


def begriffe(portal_profil=None, kriterien=None, max_begriffe: int = 12) -> list:
    """Die Suchbegriffe fuer den Lauf — Portal-Profil zuerst (#564).

    Wichtig, weil #564 genau fuer LinkedIn gelernt wurde: die naiven
    MUSS-Begriffe taugen dort nicht. LinkedIn nimmt Phrase-Match nicht an
    ("PLM Architect" ergab 0 Treffer), und drei Buchstaben wie "PLM"
    matchen ohne Branchenfilter massenhaft Unbeteiligtes. Wer ein
    Portal-Profil gepflegt hat, bekommt dessen Begriffe zuerst; die
    MUSS-Liste fuellt nur auf.

    `nicht_verwenden` aus dem Profil gewinnt immer — das ist gelerntes
    Wissen ueber die Quelle, kein Vorschlag.
    """
    profil = portal_profil or {}
    gesperrt = set()
    for n in (profil.get("nicht_verwenden") or []):
        wert = n.get("wert") if isinstance(n, dict) else n
        wert = str(wert or "").strip().lower()
        if wert:
            gesperrt.add(wert)
    out, gesehen = [], set()

    def _nimm(wert):
        w = str(wert or "").strip()
        if not w or w.lower() in gesehen or w.lower() in gesperrt:
            return
        gesehen.add(w.lower())
        out.append(w)

    for schluessel in ("primaere_suchen", "sekundaere_suchen"):
        for eintrag in (profil.get(schluessel) or []):
            if isinstance(eintrag, dict):
                _nimm(eintrag.get("keywords"))
            else:
                _nimm(eintrag)
    for kw in ((kriterien or {}).get("keywords_muss") or []):
        _nimm(kw)
    return out[:max(1, int(max_begriffe or 12))]


# -- Der Ablauf im Browser (#919 Stolpersteine 1-5) -------------------
#
# Alles laeuft auf EINEM Tab: `window.__pbp_ln` ueberlebt keine
# Navigation. Die Schleifen sind async IIFEs, weil `javascript_tool`
# nach rund 45 s abbricht — gestartet wird sofort, der Fortschritt wird
# danach abgefragt. Und keine Funktion gibt je einen Anzeigentext oder
# eine URL mit Query-String zurueck: das erste sprengt die
# 1000-Zeichen-Grenze der Rueckgabe, das zweite loest einen Block aus.

JS_ERNTE = r"""
(() => {
  const CFG = __CFG__;
  const csrf = (document.cookie.match(/JSESSIONID="?([^";]+)"?/) || [])[1];
  if (!csrf) { return {fehler: 'kein_csrf_cookie'}; }
  const H = {'csrf-token': csrf,
             'accept': 'application/vnd.linkedin.normalized+json+2.1',
             'x-restli-protocol-version': '2.0.0'};
  const S = window.__pbp_ln = {treffer: {}, fertig: false, fehler: null,
                               gemacht: 0,
                               gesamt: CFG.begriffe.length * CFG.seiten,
                               status: {}};
  const url = (kw, start) =>
    '/voyager/api/voyagerJobsDashJobCards?decorationId=' + CFG.decoration +
    '&count=' + CFG.count + '&q=jobSearch&start=' + start +
    '&query=(origin:JOB_SEARCH_PAGE_KEYWORD_AUTOCOMPLETE,keywords:' +
    encodeURIComponent(kw) + ',locationUnion:(geoId:' + CFG.geo_id + '),' +
    'selectedFilters:(timePostedRange:List(' + CFG.fenster + ')),' +
    'spellCorrectionEnabled:true)';
  (async () => {
    try {
      for (const kw of CFG.begriffe) {
        for (let s = 0; s < CFG.seiten; s++) {
          const r = await fetch(url(kw, s * CFG.count), {headers: H});
          S.status[r.status] = (S.status[r.status] || 0) + 1;
          if (!r.ok) { S.fehler = r.status; S.gemacht++; continue; }
          const j = await r.json();
          for (const o of (j.included || [])) {
            if (o.$type !== 'com.linkedin.voyager.dash.jobs.JobPostingCard')
              continue;
            const id = String(o.preDashNormalizedJobPostingUrn || '')
                         .split(':').pop();
            if (!id || S.treffer[id]) continue;
            S.treffer[id] = {
              job_id: id,
              titel: (o.title && o.title.text) || '',
              firma: (o.primaryDescription && o.primaryDescription.text) || '',
              ort: (o.secondaryDescription && o.secondaryDescription.text) || '',
              fusszeile: (o.footerItems || [])
                           .map(f => (f.text && f.text.text) || '')
                           .filter(Boolean)
            };
          }
          S.gemacht++;
          await new Promise(r2 => setTimeout(r2, CFG.pause_ms));
        }
      }
    } catch (e) { S.fehler = String(e).slice(0, 120); }
    S.fertig = true;
  })();
  return {gestartet: true, requests: S.gesamt};
})()
"""

JS_STATUS = r"""
(() => {
  const S = window.__pbp_ln;
  if (!S) return {fehler: 'kein_lauf — Tab gewechselt? Dann von vorn.'};
  return {fertig: S.fertig, gemacht: S.gemacht, gesamt: S.gesamt,
          treffer: Object.keys(S.treffer).length,
          volltexte: Object.values(S.treffer)
                       .filter(t => t.beschreibung).length,
          fehler: S.fehler, status: S.status};
})()
"""

JS_VOLLTEXTE = r"""
(() => {
  const IDS = __IDS__;
  const CFG = __CFG__;
  const S = window.__pbp_ln;
  if (!S) return {fehler: 'kein_lauf'};
  const csrf = (document.cookie.match(/JSESSIONID="?([^";]+)"?/) || [])[1];
  const H = {'csrf-token': csrf,
             'accept': 'application/vnd.linkedin.normalized+json+2.1',
             'x-restli-protocol-version': '2.0.0'};
  S.fertig = false; S.gemacht = 0; S.gesamt = IDS.length;
  (async () => {
    for (const id of IDS) {
      try {
        const r = await fetch('/voyager/api/jobs/jobPostings/' + id +
                              '?decorationId=' + CFG.decoration_detail,
                              {headers: H});
        S.status[r.status] = (S.status[r.status] || 0) + 1;
        if (r.ok) {
          const d = (await r.json()).data || {};
          const t = S.treffer[id] = S.treffer[id] || {job_id: id};
          t.beschreibung = (d.description && d.description.text) || '';
          t.ort = d.formattedLocation || t.ort || '';
          t.remote = d.workRemoteAllowed ? 'remote' : 'unbekannt';
          t.anstellungsart = d.employmentStatus || '';
          t.bewerber = d.applies;
        } else { S.fehler = r.status; }
      } catch (e) { S.fehler = String(e).slice(0, 120); }
      S.gemacht++;
      await new Promise(r2 => setTimeout(r2, CFG.pause_ms));
    }
    S.fertig = true;
  })();
  return {gestartet: true, anzahl: IDS.length};
})()
"""

# Stolperstein 3: javascript_tool kappt bei rund 1000 Zeichen. Ein
# Anzeigentext hat 1.500-10.000. Also in die Seite rendern und mit
# get_page_text abholen — das liefert mehrere Tausend Zeichen am Stueck.
#
# Live gemessen am 07.09.2026: **LinkedIn sanitisiert `innerHTML`.** Die
# erste Fassung schrieb `<main><article>...` in den Body; danach stand
# der Text zwar da (10.589 Zeichen), aber `document.body.children` war
# LEER — kein einziges Element hatte ueberlebt, auch die `<hr>`-Trenner
# zwischen den Stellen nicht. Der Text waere also gekommen, nur nicht
# mehr zerlegbar gewesen.
#
# Deshalb: `textContent` statt `innerHTML` (geht am Sanitizer vorbei,
# weil es gar kein Markup ist) plus `white-space: pre-wrap`, damit
# `innerText` die Zeilenumbrueche behaelt — ohne das faltet der Browser
# sie zu Leerzeichen zusammen. Getrennt wird ueber Text-Marker, die
# jede Sanitisierung ueberstehen. Gegengemessen: 10.836 Zeichen, 103
# Umbrueche, 3 von 3 Markern gefunden.
MARKER_START = "=== PBP-STELLE "
MARKER_ENDE = "=== ENDE "

JS_AUSGABE = r"""
(() => {
  const S = window.__pbp_ln;
  if (!S) return {fehler: 'kein_lauf'};
  const rows = Object.values(S.treffer).filter(t => t.beschreibung);
  const text = rows.map(t =>
    '=== PBP-STELLE ' + t.job_id + ' ===\n' +
    'TITEL: ' + (t.titel || '') + '\n' +
    'FIRMA: ' + (t.firma || '') + '\n' +
    'ORT: ' + (t.ort || '') + '\n' +
    'REMOTE: ' + (t.remote || '') + '\n' +
    'TEXT:\n' + t.beschreibung +
    '\n=== ENDE ' + t.job_id + ' ==='
  ).join('\n\n');
  document.body.style.whiteSpace = 'pre-wrap';
  document.body.textContent = text;
  return {gerendert: rows.length, zeichen: text.length,
          hinweis: 'Jetzt get_page_text aufrufen.'};
})()
"""


def parse_ausgabe(text: str) -> list:
    """Liest zurueck, was JS_AUSGABE in die Seite geschrieben hat.

    Der Gegenpart zu den Text-Markern: `get_page_text` liefert einen
    Block, und hier wird er wieder zu Datensaetzen. Ohne diese Funktion
    muesste jeder Aufrufer die Marker selbst kennen — und der naechste
    haette sie anders geraten.
    """
    out = []
    for stueck in (text or "").split(MARKER_START)[1:]:
        kopf, _, rest = stueck.partition("===")
        job_id = kopf.strip()
        if not job_id:
            continue
        rest = rest.split(MARKER_ENDE)[0]
        eintrag = {"job_id": job_id, "titel": "", "firma": "", "ort": "",
                   "remote": "", "beschreibung": ""}
        kopfteil, _, text_teil = rest.partition("TEXT:")
        for zeile in kopfteil.split("\n"):
            for feld, praefix in (("titel", "TITEL:"), ("firma", "FIRMA:"),
                                  ("ort", "ORT:"), ("remote", "REMOTE:")):
                if zeile.strip().startswith(praefix):
                    eintrag[feld] = zeile.split(praefix, 1)[1].strip()
        eintrag["beschreibung"] = text_teil.strip()
        out.append(eintrag)
    return out


def js_mit_konfig(vorlage: str, konfig: dict, ids=None) -> str:
    """Setzt Konfiguration und ID-Liste in ein Browser-Skript ein.

    Die Skripte bauen ihre URLs SELBST aus der Konfiguration, statt
    fertige URLs gereicht zu bekommen — so steht keine Query-String-URL
    in einer Rueckgabe (Stolperstein 4), und ein Tippfehler in der
    Vorlage faellt im Test auf statt erst im Browser.
    """
    import json
    text = vorlage.replace("__CFG__", json.dumps(konfig, ensure_ascii=False))
    if ids is not None:
        text = text.replace("__IDS__", json.dumps(list(ids)))
    return text


def konfig(begriffe_liste, fenster: str, geo_id: str = GEO_ID_DE,
           seiten: int = 2) -> dict:
    """Die Konfiguration, die die Browser-Skripte erwarten."""
    return {
        "begriffe": list(begriffe_liste or []),
        "seiten": max(1, min(int(seiten or 2), MAX_SEITEN)),
        "count": SEITENGROESSE,
        "geo_id": geo_id or GEO_ID_DE,
        "fenster": fenster or f"r{FENSTER_WOCHE}",
        "pause_ms": PAUSE_MS,
        "decoration": DECORATION_LISTE,
        "decoration_detail": DECORATION_DETAIL,
    }
