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

# Werkzeuge, die den Lauf im Browser fuer ein Portal vorbereiten. Die
# Namen prueft ein Test gegen die registrierten Werkzeuge (#1000).
WERKZEUG_JE_PORTAL = {
    "linkedin": "linkedin_lauf_plan()",
    "google_jobs": "google_jobs_url()",
    "stepstone": "google_jobs_url()",
}

#: Der Anfang der Regel - daran erkennt ein Test, dass eine Anleitung sie enthaelt.
MARKE_IM_ZWEIFEL = "Trage im Zweifel ein."

#: Die Regel fuer jeden Browserlauf (#1187): EINE Fassung, die alle Anleitungen einsetzen. Der Mensch entscheidet in PBP,
#: was taugt - nicht Claude im Chat. Die Werkzeugnamen prueft `test_v18_browser_im_zweifel_1187`.
REGEL_IM_ZWEIFEL = (
    MARKE_IM_ZWEIFEL + " Eine Stelle zu viel in PBP ist besser als eine zu wenig; ob sie taugt, entscheidet der Mensch in PBP, "
    "nicht du im Chat. Lege jede Stelle an, die fachlich passt, möglich ist oder nahezu interessant sein könnte, auch wenn "
    "ein einzelner Punkt dagegen spricht (Standort, Gehalt, Ebene). Schreibe dein Urteil und den Zweifelsgrund an die "
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
    eintraege: list[dict] = []
    for key, info in registry.items():
        if _zugriffsart(key, info) == "browser_login":
            if key not in gewaehlt:
                continue
            art = UEBERSPRUNGEN
            weg = ersatzwege.get(key) or info.get("login_hinweis") or ""
        elif info.get("defekt") and _nur_im_browser(info):
            art = DEFEKT_NUR_BROWSER
            weg = info.get("manueller_fallback") or info.get("defekt_grund") or ""
        else:
            continue
        profil = db.find_portal_search_profile(key)
        begriffe = suchbegriffe(profil)
        eintraege.append({
            "key": key,
            "name": info.get("name") or key,
            "art": art,
            "ersatzweg": str(weg),
            "suchbegriffe": begriffe,
            "suchprofil_vorhanden": bool(begriffe),
            "werkzeug": WERKZEUG_JE_PORTAL.get(key, ""),
        })
    return eintraege


def prompt(eintraege: list[dict]) -> str:
    """Der kopierbare Auftrag an Claude — leer, wenn es nichts zu tun gibt."""
    haupt = [e for e in eintraege if e["art"] == UEBERSPRUNGEN]
    extra = [e for e in eintraege if e["art"] == DEFEKT_NUR_BROWSER]
    if not haupt and not extra:
        return ""
    zeilen = ["Suche für mich in diesen Quellen, die PBP nur über den "
              "Browser erreicht (Claude-in-Chrome). Der interne Suchlauf "
              "hat sie uebersprungen.", ""]

    def _zeile(nummer, e):
        teile = [f"{nummer}. {e['name']}"]
        if e["suchbegriffe"]:
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
    if extra:
        if haupt:
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
        "Urteil schreibst. Der Titel allein sagt zu wenig über Systeme und "
        "Anforderungen.",
        f"- {REGEL_IM_ZWEIFEL}",
        "- Übernimm mit stelle_manuell_anlegen(), einen LinkedIn-Sammellauf "
        "mit linkedin_treffer_uebernehmen(). PBP prüft dabei Blacklist, "
        "Duplikate und Anker.",
        "- Melde mir am Ende je Quelle: Rohtreffer, in PBP angelegt, schon "
        "bekannt, aussortiert mit Grund. Der Bericht ersetzt die Einträge nicht.",
    ]
    return "\n".join(zeilen)
