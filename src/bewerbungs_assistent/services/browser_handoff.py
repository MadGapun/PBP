"""Quellen, die nur im Browser liefern — und der Weg dorthin (#1049).

Nutzerbericht vom 15.09.2026: der Knopf "Jobsuche starten" startet nur
den internen Lauf. Quellen, die ein eingeloggtes Konto im Browser
brauchen, werden dort bewusst uebersprungen (#488, sonst laufen sie in
stumme Timeouts) — und im Dashboard fuehrte kein Weg von dort zum Lauf
ueber die Chrome-Erweiterung. Sechs aktive Quellen trugen seit knapp fuenf
Monaten nichts bei, und kein Lauf wies darauf hin.

#704 hat die Anweisung in den Workflow-Prompt geschrieben; #719 hat die
Bruecke vom Dashboard benannt und auf 1.8 vertagt. Dieses Modul ist die
Bruecke: es sagt, WELCHE Quellen nur im Browser liefern, und baut daraus
einen Prompt aus echten Daten.

Zwei Gruppen, weil sie Verschiedenes bedeuten:

* `browser_login` — laufen nur ueber Claude-in-Chrome. Stehen sie in der
  Auswahl, hat der interne Lauf sie uebersprungen.
* als defekt markierte Quellen, deren Befund den Browser als einzigen Weg
  nennt (#1039, B53). Sie lassen sich nicht auswaehlen, liefern aber im
  Browser — der Prompt fuehrt sie als optionale Ergaenzung.

Die Suchbegriffe kommen aus dem Suchprofil je Portal (#564), nicht aus
`keywords_muss`: die naive Variante liefert dort Muell, das war der ganze
Zweck von #564. Fehlt ein Suchprofil, steht ein Hinweis da — erfundene
Begriffe waeren schlimmer als keine.

#1187 (09.10.2026): Ein Lauf ueber sechs Browser-Quellen mit rund 1.300 Rohtreffern legte keine einzige Stelle an. Der
Auftrag unten und drei weitere Anleitungen sagten Claude, "passende" Stellen zu uebernehmen und Verworfenes im Chat zu
melden - die Auswahl traf Claude, der Mensch sah nur den Bericht. `REGEL_IM_ZWEIFEL` ist die EINE Fassung der Gegenregel;
jede Anleitung setzt sie ein, ein Test verlangt sie dort (Lehre L66).
"""
from __future__ import annotations

UEBERSPRUNGEN = "uebersprungen"
DEFEKT_NUR_BROWSER = "defekt_nur_browser"
#: #1302: eine interne Quelle, deren letzter Suchlauf scheiterte (freelancermap: Abbruch an der Zeitgrenze) und die
#: im Browser eine Such-URL hat. Solange der interne Weg ausfaellt, steht sie im Auftrag - sonst fiel sie zweimal durch.
INTERN_AUSGEFALLEN = "intern_ausgefallen"

# Werkzeuge, die den Lauf im Browser fuer ein Portal vorbereiten. Die
# Namen prueft ein Test gegen die registrierten Werkzeuge (#1000).
WERKZEUG_JE_PORTAL = {
    "linkedin": "linkedin_lauf_plan()",
    "google_jobs": "google_jobs_url()",
    "stepstone": "google_jobs_url()",
    "jobtic": "quelle_handoff('jobtic', <Suchbegriff>)",
    "freelancermap": "quelle_handoff('freelancermap', <Suchbegriff>)",
}

#: #1302: Portale, deren gespeichertes Suchprofil auch der INTERNE Suchlauf liest (vor den MUSS-Begriffen). EINE Liste fuer
#: `build_search_keywords` und die Auskunft von `suchprofil_lesen`. LinkedIn bleibt aussen vor (#1071).
PORTALE_MIT_SUCHPROFIL_IM_LAUF = ("indeed", "freelancermap")

#: Der Anfang der Regel - daran erkennt ein Test, dass eine Anleitung sie enthaelt.
MARKE_IM_ZWEIFEL = "Trage im Zweifel ein."

#: Die Regel fuer jeden Browserlauf (#1187): EINE Fassung, die alle Anleitungen einsetzen. Der Mensch entscheidet in PBP,
#: was taugt - nicht Claude im Chat. Die Werkzeugnamen prueft `test_v18_browser_im_zweifel_1187`.
REGEL_IM_ZWEIFEL = (
    MARKE_IM_ZWEIFEL + " Eine Stelle zu viel in PBP ist besser als eine zu wenig; ob sie taugt, entscheidet der Mensch in PBP, "
    "nicht du im Chat. Lege jede Stelle an, die fachlich passt, möglich ist oder nahezu interessant sein könnte, auch wenn "
    "ein einzelner Punkt dagegen spricht (Standort, Gehalt, Ebene). Schreibe deine Bewertung und den Zweifelsgrund an die "
    "Stelle (stelle_urteil_speichern); in die Begründung gehört auch „Anzeige offen: ja, nein oder unklar“ — nach dem Lesen: "
    "Hinweis „nicht mehr verfügbar“ oder „keine Bewerbungen mehr“, fehlender Bewerben-Knopf. Ist die Stelle in PBP schon "
    "als aussortiert bekannt und passt nach dem Lesen fachlich, hole sie mit stelle_reaktivieren zurück, statt sie nur im "
    "Chat zu erwähnen. Sortiere nur aus (stelle_einordnen), was offensichtlich fachfremd oder geschlossen ist, und nenne "
    "den Grund. Der Bericht im Chat ersetzt die Einträge in PBP nicht.")


def _nur_im_browser(info: dict) -> bool:
    """Nennt der Befund einer defekten Quelle den Browser als Weg?

    Geprueft werden Grund UND Ersatzweg: bei `workday_dax` steht "Browser"
    nur im Grund, bei heise_jobs und meinestadt in beiden.
    """
    text = " ".join(str(info.get(f) or "") for f in
                    ("defekt_grund", "manueller_fallback")).lower()
    return "chrome" in text or "browser" in text


def _begriff(eintrag) -> str:
    """Ein Suchprofil-Eintrag ist ein String oder ein dict (#564)."""
    if isinstance(eintrag, str):
        return eintrag.strip()
    if isinstance(eintrag, dict):
        return str(eintrag.get("keywords") or eintrag.get("wert") or "").strip()
    return ""


def suchbegriffe(profil: dict | None) -> list[str]:
    """Primaere vor sekundaeren Begriffen, ohne die gesperrten, ohne Dubletten."""
    if not profil:
        return []
    gesperrt = {_begriff(e).lower() for e in profil.get("nicht_verwenden") or []}
    ergebnis: list[str] = []
    for eintrag in (profil.get("primaere_suchen") or []) + (
            profil.get("sekundaere_suchen") or []):
        wort = _begriff(eintrag)
        if wort and wort.lower() not in gesperrt and wort not in ergebnis:
            ergebnis.append(wort)
    return ergebnis


def intern_ausgefallen(db, auswahl=None, registry=None) -> dict[str, str]:
    """Gewaehlte interne Quellen, deren letzter Lauf scheiterte und die im Browser eine Such-URL haben (#1302).

    Rueckgabe: {Quelle: Grund des letzten Laufs}. "Gescheitert" heisst: Fehler in Serie oder pausiert. Eine Quelle,
    die wieder liefert, faellt von selbst heraus (die Fehlerserie steht dann auf 0).
    """
    if registry is None:
        from ..job_scraper import SOURCE_REGISTRY as registry
    from ..job_scraper.handoff import HANDOFF_URL_TEMPLATES
    from ..services.search_service import _zugriffsart
    gewaehlt = list(auswahl or [])
    if not gewaehlt:
        return {}
    try:
        gesundheit = {h["scraper_name"]: h for h in db.get_scraper_health()}
    except Exception:
        return {}
    ergebnis: dict[str, str] = {}
    for key in gewaehlt:
        info = registry.get(key) or {}
        # #1436: eine abgekuendigte Quelle (kimeta, solcom) laeuft seit #1435 nie intern; sie ist nicht "ausgefallen",
        # sondern steht als Browser-Quelle in der Liste (browser_quellen).
        if (key not in HANDOFF_URL_TEMPLATES or info.get("defekt") or info.get("deprecated")
                or _zugriffsart(key, info) == "browser_login"):
            continue
        h = gesundheit.get(key) or {}
        # #1436: nur ein gescheiterter Lauf zaehlt. Eine von Hand abgeschaltete Quelle (is_active=0 ohne Fehlerserie) hat
        # niemand laufen lassen; sie stand bisher dauerhaft als "ausgefallen" in der Karte.
        if (h.get("consecutive_failures") or 0) >= 1:
            ergebnis[key] = str(h.get("last_status_detail") or h.get("last_error") or "").strip()
    return ergebnis


def _suchkriterien_begriffe(db) -> list[str]:
    """Die Begriffe, mit denen auch der interne Lauf sucht: MUSS, ohne MUSS die PLUS-Begriffe (#1071)."""
    try:
        krit = db.get_search_criteria() or {}
    except Exception:
        return []
    return [str(b).strip() for b in (krit.get("keywords_muss") or krit.get("keywords_plus") or []) if str(b).strip()]


def browser_quellen(db, auswahl=None, registry=None,
                    ersatzwege=None) -> list[dict]:
    """Die Quellen, die nur im Browser liefern — mit allem, was der Prompt braucht.

    Args:
        auswahl: die gewaehlten Quellen. Nur `browser_login`-Quellen aus
            der Auswahl zaehlen als "uebersprungen".
        registry: SOURCE_REGISTRY (fuer Tests austauschbar).
        ersatzwege: Kurztexte je Quelle (`_MANUAL_SOURCES`).
    """
    if registry is None:
        from ..job_scraper import SOURCE_REGISTRY as registry
    if ersatzwege is None:
        from ..tools.jobs import _MANUAL_SOURCES as ersatzwege
    from ..services.search_service import _zugriffsart
    gewaehlt = set(auswahl or [])
    ausgefallen = intern_ausgefallen(db, [k for k in registry if k in gewaehlt], registry=registry)
    eintraege: list[dict] = []
    for key, info in registry.items():
        if _zugriffsart(key, info) == "browser_login":
            if key not in gewaehlt:
                continue
            art = UEBERSPRUNGEN
            weg = ersatzwege.get(key) or info.get("login_hinweis") or ""
        elif info.get("deprecated") and info.get("handoff_verfuegbar"):
            # #1436: abgekuendigt (robots.txt, Bot-Schutz), seit #1435 ohne internen Lauf - gewaehlt heisst: nur im Browser.
            if key not in gewaehlt:
                continue
            art = UEBERSPRUNGEN
            weg = info.get("manueller_fallback") or info.get("deprecated_grund") or ""
        elif key in ausgefallen:
            art = INTERN_AUSGEFALLEN
            grund = ausgefallen[key]
            weg = "interner Suchlauf zuletzt ausgefallen" + (f" ({grund})" if grund else "")
        elif info.get("defekt") and _nur_im_browser(info) and not info.get("ersatz_quelle"):
            # #1159: hat die defekte Quelle eine eigene Browser-Schwester (ersatz_quelle), steht DIE in der Liste, wenn
            # der Mensch sie gewaehlt hat; die defekte noch einmal zu nennen waere dieselbe Quelle zweimal.
            art = DEFEKT_NUR_BROWSER
            weg = info.get("manueller_fallback") or info.get("defekt_grund") or ""
        else:
            continue
        profil = db.find_portal_search_profile(key)
        begriffe = suchbegriffe(profil)
        herkunft = "suchprofil" if begriffe else ""
        if not begriffe and (art == INTERN_AUSGEFALLEN or info.get("deprecated")):
            # #1302: eine interne Quelle sucht ohne eigenes Profil mit den Suchkriterien - der Browser mit denselben.
            begriffe = _suchkriterien_begriffe(db)
            herkunft = "suchkriterien" if begriffe else ""
        werkzeug = WERKZEUG_JE_PORTAL.get(key, "")
        if not werkzeug and (art == INTERN_AUSGEFALLEN or info.get("deprecated")):
            werkzeug = f"quelle_handoff('{key}', <Suchbegriff>)"
        eintraege.append({
            "key": key,
            "name": info.get("name") or key,
            "art": art,
            "ersatzweg": str(weg),
            "suchbegriffe": begriffe,
            "suchprofil_vorhanden": herkunft == "suchprofil",
            "suchbegriffe_herkunft": herkunft,
            "werkzeug": werkzeug,
            # #1189: Auflagen der Quelle (jobtic) - der Auftrag nennt sie unter der Quelle.
            "auflagen": str((info.get("auflagen") or {}).get("hinweis") or ""),
        })
    return eintraege


def prompt(eintraege: list[dict]) -> str:
    """Der kopierbare Auftrag an Claude — leer, wenn es nichts zu tun gibt."""
    haupt = [e for e in eintraege if e["art"] == UEBERSPRUNGEN]
    ausgefallen = [e for e in eintraege if e["art"] == INTERN_AUSGEFALLEN]
    extra = [e for e in eintraege if e["art"] == DEFEKT_NUR_BROWSER]
    if not haupt and not extra and not ausgefallen:
        return ""
    if haupt:
        zeilen = ["Suche für mich in diesen Quellen, die PBP nur über den "
                  "Browser erreicht (Claude-in-Chrome). Der interne Suchlauf "
                  "hat sie uebersprungen.", ""]
    else:
        zeilen = ["Suche für mich im Browser (Claude-in-Chrome) in diesen Quellen.", ""]

    def _zeile(nummer, e):
        teile = [f"{nummer}. {e['name']}"]
        if e["suchbegriffe"] and e.get("suchbegriffe_herkunft") == "suchkriterien":
            teile.append("Suchbegriffe aus meinen Suchkriterien (kein eigenes Suchprofil der Quelle): "
                         + ", ".join(e["suchbegriffe"]))
        elif e["suchbegriffe"]:
            teile.append("erprobte Suchbegriffe: " + ", ".join(e["suchbegriffe"]))
        else:
            teile.append(
                f"kein Suchprofil hinterlegt — lies suchprofil_lesen('{e['key']}') "
                "und frag mich nach den Begriffen, statt welche zu erfinden")
        if e["werkzeug"]:
            teile.append(f"vorbereiten mit {e['werkzeug']}")
        return " — ".join(teile)

    for nummer, e in enumerate(haupt, 1):
        zeilen.append(_zeile(nummer, e))
        if e.get("auflagen"):
            zeilen.append(f"   {e['auflagen']}")
    if ausgefallen:
        if haupt:
            zeilen.append("")
        zeilen.append("Diese Quellen laufen sonst intern, der letzte interne Suchlauf ist dort ausgefallen – "
                      "suche dort, bis er wieder liefert:")
        for nummer, e in enumerate(ausgefallen, len(haupt) + 1):
            zeilen.append(_zeile(nummer, e))
            zeilen.append(f"   {e['ersatzweg']}")
    if extra:
        if haupt or ausgefallen:
            zeilen.append("")
        zeilen.append("Optional, wenn Zeit bleibt — diese Quellen führt PBP "
                      "als defekt, im Browser liefern sie:")
        for e in extra:
            weg = f" ({e['ersatzweg']})" if e["ersatzweg"] else ""
            zeilen.append(f"- {e['name']}{weg}")
    zeilen += [
        "",
        "Regeln:",
        "- Lies bei jedem Treffer den VOLLTEXT der Anzeige, bevor du dein "
        "Bewertung schreibst. Der Titel allein sagt zu wenig über Systeme und "
        "Anforderungen.",
        f"- {REGEL_IM_ZWEIFEL}",
        "- Übernimm die Ernte einer Quelle in einem Zug mit "
        "browser_treffer_uebernehmen(quelle=..., treffer=[...], rohtreffer=..., dry_run=False) — es verbucht "
        "den Lauf, auch ohne Anlage —, einzelne Stellen mit stelle_manuell_anlegen(), einen "
        "LinkedIn-Sammellauf mit linkedin_treffer_uebernehmen(). PBP prüft dabei Blacklist, "
        "Duplikate und Anker.",
        "- Melde mir am Ende je Quelle: Rohtreffer, in PBP angelegt, schon "
        "bekannt, aussortiert mit Grund. Der Bericht ersetzt die Einträge nicht.",
    ]
    return "\n".join(zeilen)


# ── #1436: Suchbegriffe je Quelle pflegen ───────────────────────────────────────────────────────────────────────────

#: Eingeklappt oder offen: die Karte "Diese Quellen laufen nur ueber den Browser" auf der Stellenseite. Der Zustand liegt
#: beim Profil (profile_settings) wie bei den Dashboard-Bereichen (#985), nicht im Browser. Vorgabe: eingeklappt.
KARTE_OFFEN = "browser_karte_offen"


def karte_offen(db) -> bool:
    try:
        return bool(db.get_profile_setting(KARTE_OFFEN, False))
    except Exception:
        return False


#: Welche gewaehlte Quelle das Suchprofil eines Portals im INTERNEN Lauf liest (`job_scraper.build_search_keywords`,
#: `jobspy_source.search_jobspy_indeed`). Ein Test haelt die Schluessel gegen `PORTALE_MIT_SUCHPROFIL_IM_LAUF`.
LESER_IM_LAUF = {"indeed": "jobspy_indeed", "freelancermap": "freelancermap"}


def _wirkung(key: str, eintrag: dict | None, gewaehlt) -> str:
    """Wo PBP die Suchbegriffe dieser Quelle liest - ein Setzer ohne Leser waere eine Einstellung ohne Wirkung (L11)."""
    im_lauf = LESER_IM_LAUF.get(key) in set(gewaehlt or [])
    if eintrag and eintrag["art"] == INTERN_AUSGEFALLEN and not im_lauf:
        return "Auftrag „Browser-Quellen mit Claude“, solange der interne Suchlauf ausfällt"
    if eintrag and im_lauf:
        return "interner Suchlauf und Auftrag „Browser-Quellen mit Claude“"
    if eintrag:
        return "Auftrag „Browser-Quellen mit Claude“"
    if im_lauf:
        return "interner Suchlauf"
    return "zurzeit nicht genutzt (Quelle nicht gewählt)"


def _text(eintrag, feld: str) -> str:
    if feld == "keywords":
        return _begriff(eintrag)
    if isinstance(eintrag, str):
        return eintrag.strip()
    return str((eintrag or {}).get("wert") or "").strip() if isinstance(eintrag, dict) else ""


def _texte(liste, feld: str = "keywords") -> list[str]:
    ergebnis: list[str] = []
    for eintrag in liste or []:
        wort = _text(eintrag, feld)
        if wort and wort not in ergebnis:
            ergebnis.append(wort)
    return ergebnis


def pflegbare_quellen(db, auswahl=None, registry=None) -> list[dict]:
    """Die Quellen, deren Suchbegriffe PBP auch LIEST (#1436), mit Profil als Text und dem Ersatz ohne Profil.

    Gelesen werden die Begriffe vom Auftrag an Claude (die gewaehlten Quellen aus `browser_quellen`) und vom internen
    Lauf (`LESER_IM_LAUF`). Dazu jede Quelle mit gespeichertem Profil, damit nichts Gespeichertes unsichtbar wird.
    Die optionalen, als defekt gefuehrten Quellen nennt der Auftrag nur mit Namen; ihre Begriffe liest niemand.
    """
    if registry is None:
        from ..job_scraper import SOURCE_REGISTRY as registry
    gewaehlt = list(auswahl or [])
    browser = {e["key"]: e for e in browser_quellen(db, auswahl=gewaehlt, registry=registry)
               if e["art"] != DEFEKT_NUR_BROWSER}
    try:
        gespeichert = [p["portal"] for p in db.list_portal_search_profiles()]
    except Exception:
        gespeichert = []
    schluessel: list[str] = list(browser)
    for key in [k for k, leser in LESER_IM_LAUF.items() if leser in gewaehlt] + sorted(gespeichert):
        if key not in schluessel and key in registry:
            schluessel.append(key)
    ersatz = _suchkriterien_begriffe(db)
    ergebnis: list[dict] = []
    for key in schluessel:
        e = browser.get(key)
        profil = db.find_portal_search_profile(key)
        info = registry.get(key) or {}
        ersatz_gilt = (LESER_IM_LAUF.get(key) in gewaehlt or bool(info.get("deprecated"))
                       or (e is not None and e["art"] == INTERN_AUSGEFALLEN))
        ergebnis.append({
            "key": key,
            "name": info.get("name") or key,
            "wirkung": _wirkung(key, e, gewaehlt),
            "gespeichert": profil is not None,
            "primaere_suchen": _texte((profil or {}).get("primaere_suchen")),
            "sekundaere_suchen": _texte((profil or {}).get("sekundaere_suchen")),
            "nicht_verwenden": _texte((profil or {}).get("nicht_verwenden"), feld="wert"),
            # Ohne eigene Begriffe: sucht die Quelle mit den Suchkriterien (Zahl) oder fragt Claude nach (0)?
            "ersatz_suchkriterien": len(ersatz) if ersatz_gilt else 0,
        })
    return ergebnis


def _zusammenfuehren(alt, zeilen, feld: str) -> list:
    """Bearbeitete Zeilen zurueck ins gespeicherte Format: ein bestehender Eintrag behaelt Filter und Notiz (#564)."""
    bisher: dict = {}
    for eintrag in alt or []:
        text = _text(eintrag, feld)
        if text and text.lower() not in bisher:
            bisher[text.lower()] = eintrag
    ergebnis: list = []
    gesehen: set[str] = set()
    for zeile in zeilen or []:
        text = " ".join(str(zeile or "").split())[:200]
        if not text or text.lower() in gesehen:
            continue
        gesehen.add(text.lower())
        neu = {"keywords": text} if feld == "keywords" else {"wert": text, "grund": ""}
        ergebnis.append(bisher.get(text.lower()) or neu)
    return ergebnis


def profil_speichern(db, key: str, primaere_suchen, sekundaere_suchen, nicht_verwenden) -> dict:
    """Speichert die Begriffe einer Quelle aus der Oberflaeche - ueber denselben Weg wie suchprofil_aktualisieren."""
    alt = db.find_portal_search_profile(key) or {}
    return db.update_portal_search_profile(
        key,
        primaere_suchen=_zusammenfuehren(alt.get("primaere_suchen"), primaere_suchen, "keywords"),
        sekundaere_suchen=_zusammenfuehren(alt.get("sekundaere_suchen"), sekundaere_suchen, "keywords"),
        nicht_verwenden=_zusammenfuehren(alt.get("nicht_verwenden"), nicht_verwenden, "wert"),
    )


def pflege_prompt(quellen: list[dict]) -> str:
    """Der Auftrag "Suche pflegen mit Claude" (#1436) - eine Fassung, auf dem Server (#963)."""
    if not quellen:
        return ""
    ohne = [q for q in quellen if not (q["primaere_suchen"] or q["sekundaere_suchen"])]
    mit = [q for q in quellen if q not in ohne]
    zeilen = [
        "Geh mit mir die Suchbegriffe je Jobbörse in PBP durch. Je Quelle:",
        "1. Lies das Suchprofil mit suchprofil_lesen(<Quelle>) und meine Suchkriterien mit suchkriterien_anzeigen().",
        "2. Sieh dir an, welche Stellen aus dieser Quelle zuletzt in PBP kamen und wie ich sie eingeordnet habe "
        "(stellen_anzeigen).",
        "3. Schlag mir vor, welche Begriffe du ergänzen, erweitern oder streichen würdest, jeweils mit Grund. Halte die "
        "Liste kurz: eine Browsersuche arbeitet ein paar treffsichere Begriffe ab, nicht Dutzende.",
        "4. Speichere erst nach meiner Zustimmung, mit suchprofil_aktualisieren(<Quelle>, primaere_suchen=[...], "
        "sekundaere_suchen=[...], nicht_verwenden=[...]).",
        "",
    ]
    if ohne:
        zeilen.append("Zuerst diese Quellen, sie haben noch keine eigenen Begriffe:")
        for q in ohne:
            ersatz = (f" (sucht bis dahin mit {q['ersatz_suchkriterien']} Begriffen aus meinen Suchkriterien)"
                      if q["ersatz_suchkriterien"] else "")
            zeilen.append(f"- {q['name']} ('{q['key']}'){ersatz}, genutzt von: {q['wirkung']}")
    if mit:
        if ohne:
            zeilen.append("")
        zeilen.append("Danach diese:")
        for q in mit:
            zeilen.append(f"- {q['name']} ('{q['key']}'): " + ", ".join(q["primaere_suchen"] + q["sekundaere_suchen"])
                          + f", genutzt von: {q['wirkung']}")
    zeilen += ["", "Ändere nichts ohne meine Zustimmung."]
    return "\n".join(zeilen)
