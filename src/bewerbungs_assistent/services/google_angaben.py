"""Angaben aus Google Jobs sind Behauptungen, keine Belege (#1184, B76).

Google Jobs zeigt zu jedem Treffer eine Karte: Titel, Firma, Ort, Portal und ein Stichwort wie "Homeoffice". Das
Original, die Anzeige beim Arbeitgeber, liest die Karte nicht, und die Kopien auf anderen Seiten weichen oft ab
(`weiterverbreiter`, #1120). Praxis-Fall vom 08.10.2026: Google nannte "Beliebiger Ort, Homeoffice", die Originalanzeige
einen Ort rund 570 km entfernt und nur "mobiles Arbeiten". PBP uebernahm `remote` vom Aufrufer; die Entfernung fiel weg
("Vollstaendig remote"), der Rahmenscore stieg, und die Stelle waere nach oben sortiert worden.

Die Regel: Solange das ORIGINAL nicht vorliegt (eine Detail-URL ausserhalb von Google UND ein Anzeigentext), gelten Remote
und Ort einer Google-Stelle nicht.

* Das Arbeitsmodell entscheidet der Text (`remote_jobspy.bestimmen`, dieselbe Regel wie bei JobSpy, B63/#1072); sagt er
  nichts, steht `unbekannt` da. Googles Ort fliesst nicht in diese Erkennung ein.
* Die Entfernung wird nicht aus Googles Ort gerechnet. Der Ort bleibt als Text stehen, damit man sieht, was Google
  behauptet; eine Zahl daraus waere eine Genauigkeit, die es nicht gibt.
* Kommt das Original nach (`stelle_bearbeiten` mit URL und Text), holt `stelle_aendern` beides nach.

Seit 1.8.0 (a): Ein Treffer aus Google, zu dem WEDER eine Detail-URL des Originals NOCH ein Anzeigentext vorliegt
(`ohne_beleg`), wird von `stelle_manuell_anlegen` nicht mehr angelegt - Claude bekommt stattdessen den Auftrag, das
Original zu suchen, samt vorbereiteten Suchen (`original_suchen`, e). `force=True` bleibt als Ausweg. Mit einer URL
oder einem Text allein wird weiter angelegt, unter dem Vorbehalt oben.

Abgrenzung: `google_alert` liest die Benachrichtigungs-Mails, `weiterverbreiter` kennt Seiten, die nur kopieren,
`remote_jobspy` bestimmt den Remote-Grad fuer JobSpy-Treffer aus dem Text. Dieses Modul entscheidet nur, OB eine Stelle
noch unter Googles Vorbehalt steht. Das wird aus den gespeicherten Spalten abgeleitet (Quelle, URL, Text), nicht
zusaetzlich gespeichert (wie `wahrheit`, #963).

Grenze: Eine Kopie auf einer anderen Seite mit Detail-URL und Text gilt als Original, solange die Seite nicht in
`weiterverbreiter` steht; PBP kennt keine Liste aller Seiten, die kopieren.
"""
from __future__ import annotations

import re

#: Quellenschluessel, unter denen Treffer aus Googles Karten angelegt werden:
#: der Browserlauf mit Claude (`google_jobs`) und die JobSpy-Variante.
GOOGLE_QUELLEN = ("google_jobs", "jobspy_google")

_GOOGLE_HOST = re.compile(r"(?:^|\.)google\.[a-z.]{2,}$")

#: Die Werte, die `remote_level` annehmen darf.
REMOTE_STUFEN = ("remote", "hybrid", "vor_ort", "unbekannt")


def ist_google_quelle(quelle) -> bool:
    """Steht die Stelle unter einem Quellenschluessel aus Googles Karten?"""
    return str(quelle or "").strip().lower() in GOOGLE_QUELLEN


def ist_google_adresse(url) -> bool:
    """Zeigt die Adresse auf Google selbst (Suche, Karte, Weiterleitung)?"""
    from urllib.parse import urlparse
    try:
        host = (urlparse(str(url or "").strip()).hostname or "").lower()
    except ValueError:
        return False
    return bool(_GOOGLE_HOST.search(host))


def original_gelesen(url, beschreibung) -> bool:
    """Liegt zur Stelle das ORIGINAL vor? Eine Detail-URL ausserhalb von Google UND ein Anzeigentext.

    Eine Such- oder Google-Adresse benennt keine Anzeige, ein Text ohne Adresse laesst sich nicht pruefen: beides
    zusammen gilt als gelesen, eines allein nicht.
    """
    from ..job_scraper import is_search_result_url
    from .datenguete import MIN_BESCHREIBUNG
    u = str(url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        return False
    if ist_google_adresse(u) or is_search_result_url(u):
        return False
    return len(str(beschreibung or "").strip()) >= MIN_BESCHREIBUNG


def ohne_beleg(quelle, url, beschreibung) -> bool:
    """Google-Treffer, zu dem WEDER eine Detail-URL ausserhalb von Google NOCH ein Anzeigentext vorliegt (#1184 a).

    Eine Karte allein ist eine Behauptung: ohne Adresse laesst sich nichts nachladen, ohne Text nichts pruefen, und der
    Mensch kann sich nicht bewerben. Hat die Stelle EINES von beidem, wird sie angelegt (unter Vorbehalt): Adresse oder
    Text sind ein Anker, aus dem sich das Original machen laesst.
    """
    if not ist_google_quelle(quelle):
        return False
    from ..job_scraper import is_search_result_url
    from .datenguete import MIN_BESCHREIBUNG
    u = str(url or "").strip()
    hat_adresse = (u.lower().startswith(("http://", "https://")) and not ist_google_adresse(u)
                   and not is_search_result_url(u))
    hat_text = len(str(beschreibung or "").strip()) >= MIN_BESCHREIBUNG
    return not hat_adresse and not hat_text


def original_suchen(titel, firma, ort="") -> dict:
    """Die Suche nach dem Original, vorbereitet (#1184 e). PBP sucht nicht selbst im Netz; es bereitet die Suche vor
    und sagt Claude, was zu pruefen und was danach zu tun ist."""
    from urllib.parse import quote_plus
    from ..job_scraper.handoff import HANDOFF_URL_TEMPLATES
    t = str(titel or "").strip()
    f = str(firma or "").strip()
    o = str(ort or "").strip()
    frage = " ".join(x for x in (f'"{f}"' if f else "", f'"{t}"' if t else "", "Karriere") if x)
    suchen = [{"wo": "Karriereseite des Arbeitgebers (Websuche)", "url": "https://www.google.com/search?q=" + quote_plus(frage)}]
    stichwort = " ".join(x for x in (t, f) if x)
    for schluessel, name in (("stepstone", "StepStone"), ("xing", "XING"), ("linkedin", "LinkedIn"), ("indeed", "Indeed")):
        vorlage = HANDOFF_URL_TEMPLATES.get(schluessel)
        if not vorlage or not stichwort:
            continue
        suchen.append({"wo": name, "url": vorlage.format(
            keyword=quote_plus(stichwort), keyword_pfad=quote_plus(stichwort.replace(" ", "-")),
            ort=quote_plus(o)).rstrip("?&")})
    return {
        "auftrag": (f"Suche die Originalanzeige zu '{t}' bei {f or 'dem Arbeitgeber'}: zuerst die Karriereseite des Arbeitgebers, "
                    "danach die Portale. Eine Kopie auf einer Sammelseite (Learn4Good, JobTeaser und andere) ist kein Original."),
        "suchen": suchen,
        "pruefen": [
            "Stimmen Titel und Firma? Die Karte nennt oft die Muttermarke, die Anzeige das Konzernunternehmen.",
            "Der Arbeitsort steht in der Originalanzeige; Googles Ort kann abweichen (derselbe Treffer kommt mit verschiedenen Orten).",
            "Das Arbeitsmodell (remote, hybrid, vor Ort) steht im Text der Anzeige, nicht in der Karte.",
        ],
        "danach": ("stelle_manuell_anlegen(titel, firma, url=<Detail-URL des Originals>, beschreibung=<ganzer Anzeigentext>, "
                   "ort=<Arbeitsort laut Original>, quelle='google_jobs')"),
    }


def unter_vorbehalt(quelle, url, beschreibung) -> bool:
    """Gelten Remote und Ort dieser Stelle noch nicht? (Google-Quelle, Original nicht gelesen.)"""
    return ist_google_quelle(quelle) and not original_gelesen(url, beschreibung)


def remote_aus_text(titel, beschreibung) -> str:
    """Das Arbeitsmodell aus Titel und Anzeigentext - ohne den Ort, denn der ist Googles Angabe."""
    from . import remote_jobspy
    return remote_jobspy.bestimmen(str(titel or ""), "", str(beschreibung or ""))


def hinweis(angegeben_remote, gespeichert_remote, ort) -> dict:
    """Der Block im Ergebnis von `stelle_manuell_anlegen`: was gilt, was nicht, und der naechste Schritt."""
    angegeben = str(angegeben_remote or "").strip().lower() or "unbekannt"
    return {
        "grund": ("Die Angaben stammen von einer Karte in Google Jobs. Remote und Ort gelten erst, wenn das Original "
                  "vorliegt (Detail-URL des Arbeitgebers und Anzeigentext): Kopien nennen oft einen anderen Ort oder ein "
                  "anderes Arbeitsmodell."),
        "remote": {
            "angegeben": angegeben,
            "gespeichert": gespeichert_remote,
            "bestimmt_aus": "Anzeigentext" if gespeichert_remote != "unbekannt" else "nichts (der Text sagt dazu nichts)",
        },
        "ort": {"angegeben": str(ort or "").strip(), "entfernung": "nicht gerechnet"},
        "naechster_schritt": ("Das Original beim Arbeitgeber suchen (Karriereseite) und nachtragen: "
                              "stelle_bearbeiten(job_hash, url=<Detail-URL>, beschreibung=<Originaltext>, "
                              "ort=<Arbeitsort laut Original>). Danach werden Arbeitsmodell und Entfernung neu bestimmt."),
    }
