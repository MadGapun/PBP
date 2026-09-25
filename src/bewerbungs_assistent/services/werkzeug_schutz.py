"""Loeschschutz und MCP-Annotations an einer Stelle (H27, #1087 G7).

Bis v1.7.130 gab es sechs Schutzkonventionen fuer destruktive Werkzeuge
(`bestaetigung`, `bestaetigung='LOESCHEN'`, `bestaetigt`, `dry_run` mit
wechselnder Vorgabe, `anwenden`, `force`), und `profil_loeschen` loeschte
ein Zweitprofil ohne jede Rueckfrage. Dazu trug kein einziges Werkzeug
MCP-Annotations: Claude konnte ein Migrationswerkzeug nicht von einem
Lesewerkzeug unterscheiden.

Die Regel ist jetzt EINE, in drei Klassen:

* ``ZWEISTUFIG`` — loescht oder aendert viel bzw. endgueltig. Ohne den
  genannten Parameter kommt nur eine Vorschau mit Zahlen; erst der zweite
  Aufruf wirkt. Der Parameter heisst bei neuen Werkzeugen immer
  ``bestaetigung``; bestehende ``dry_run``/``anwenden`` bleiben als
  Name erhalten (Werkzeugparameter werden nicht still umgedeutet), die
  Vorgabe ist aber ueberall die Vorschau. Ein Test prueft das an der
  echten Signatur.
* ``KLEIN_SOFORT`` — ein einzelnes, kleines Objekt (eine Kostenzeile, eine
  Verknuepfung). Wirkt sofort, wie in der Oberflaeche mit Rueckgaengig
  (G67). Jeder Eintrag traegt seinen Grund.
* ``UMKEHRBAR`` — aendert einen Zustand, der sich zurueckholen laesst
  (aussortieren, archivieren, hinfaellig). Kein Loeschen.

Ein Guard haelt jedes registrierte Werkzeug, dessen Name nach Loeschen,
Bereinigen, Zusammenfuehren oder Massenaktion klingt, gegen diese drei
Listen: ein neues destruktives Werkzeug ohne Einordnung faellt auf.

Die Annotations (``readOnlyHint``, ``destructiveHint``) entstehen aus
denselben Listen beim Registrieren (``tools.register_all``), damit sie
nicht an 260 Decorators einzeln gepflegt werden muessen.
"""
from __future__ import annotations

import re

# name -> Parameter, dessen Vorgabe die Vorschau ist
ZWEISTUFIG: dict[str, str] = {
    "profil_loeschen": "bestaetigung",
    "bewerbung_loeschen": "bestaetigung",
    "dokument_loeschen": "bestaetigung",
    "kontakt_loeschen": "bestaetigung",
    "meeting_loeschen": "bestaetigung",
    "email_loeschen": "bestaetigung",
    "interview_reflexion_loeschen": "bestaetigung",
    "ablehnungsgrund_loeschen": "bestaetigung",
    "daten_bereiche_leeren": "bestaetigung",
    "recherche_notizen_zusammenfuehren": "dry_run",
    "bewerbung_notizen_zusammenfuehren": "dry_run",
    "phantom_termine_bereinigen": "dry_run",
    "termin_dubletten_bereinigen": "dry_run",
    "dokument_typen_nachziehen": "dry_run",
    "dokumente_text_nachziehen": "anwenden",
    "dokumente_bulk_archivieren": "dry_run",
    "stellen_bulk_bewerten": "dry_run",
    "stellen_entfernen_nach_quelle": "dry_run",
    "stelle_mergen": "dry_run",
    "stellen_urls_heilen": "dry_run",
    "verwaiste_stellenrefs_bereinigen": "dry_run",
    "stellen_merkmale_nachziehen": "dry_run",
    "kontakte_aus_bestand_importieren": "dry_run",
    "profil_umlaute_reparieren": "anwenden",
    "skills_bereinigen": "anwenden",
    "blacklist_anwenden": "dry_run",
    "ablehnungsgruende_vereinheitlichen": "dry_run",
}

KLEIN_SOFORT: dict[str, str] = {
    "kosten_loeschen": "eine einzelne Kostenzeile",
    "skill_zeitraum_loeschen": "ein einzelner Zeitraum an einem Skill",
    "stelle_analyse_loeschen": "ein gespeichertes Urteil; die Stelle bleibt",
    "bewerbung_stelle_entknuepfen": "nur die Verknuepfung, beide Seiten bleiben",
    "kontakt_entknuepfen": "nur die Verknuepfung, beide Seiten bleiben",
    "referenz_entfernen": "nur die Referenz-Markierung, der Kontakt bleibt",
    "kontakt_kategorie_loeschen": "nur unbenutzte Kategorien; benutzte weist das Werkzeug ab",
    "custom_quelle_loeschen": "eine einzelne eigene Quelle, jederzeit neu anlegbar",
    "dokument_entverknuepfen": "nur die Verknuepfung, das Dokument bleibt",
}

UMKEHRBAR: dict[str, str] = {
    "stellen_auto_aussortieren": "aussortieren; Protokoll und stelle_reaktivieren holen zurueck",
    "stelle_einordnen": "aussortieren; stelle_reaktivieren holt zurueck",
    "follow_up_hinfaellig": "Status einer Nachfassung",
    "todo_hinfaellig": "Status einer Aufgabe; todo_reaktivieren holt zurueck",
    "dokument_archivieren": "dokument_reaktivieren holt zurueck",
    "dokumente_bulk_markieren": "Status-Markierung, erneut setzbar",
    "ablehnungsgrund_umbenennen": "Umbenennen ist in Gegenrichtung wiederholbar",
    "extraktion_anwenden": "schreibt Vorschlaege ins Profil, die der Mensch bestaetigt hat",
    "profil_importieren": "legt ein NEUES Profil an, ueberschreibt nichts",
}

# Namen, die nach Loeschen oder Massenaenderung klingen. Wer hier trifft,
# muss in einer der drei Listen stehen (Guard).
DESTRUKTIV_MUSTER = re.compile(
    r"loesch|entfern|bereinig|leeren|reset|merge|entknuepf|archivier|bulk"
    r"|aussortier|zusammenfuehr|verwerf|hinfaellig|heilen|vereinheitl"
    r"|umbenenn|anwenden|nachzieh|reparier|importier|entverknuepf")

# Lesende Werkzeuge: Name endet auf eine lesende Form. Bewusst eng —
# ein falsches readOnlyHint ist schlimmer als ein fehlendes.
LESEND_MUSTER = re.compile(
    r"(_anzeigen|_lesen|_auflisten|_details|_historie|_uebersicht"
    r"|_vorschau|_status|_kontext)$|^pbp_capabilities$|^profil_status$")

# Namen, die lesend aussehen, aber schreiben.
NICHT_LESEND: set[str] = set()

# Namen, die nach Loeschen klingen, aber nur lesen.
NICHT_DESTRUKTIV: set[str] = {"aussortier_protokoll"}


def annotations_fuer(name: str) -> dict:
    """MCP-Annotations fuer ein Werkzeug, aus den Listen oben."""
    if name in ZWEISTUFIG or name in KLEIN_SOFORT:
        return {"readOnlyHint": False, "destructiveHint": True}
    if name in UMKEHRBAR:
        return {"readOnlyHint": False, "destructiveHint": False}
    if LESEND_MUSTER.search(name) and name not in NICHT_LESEND:
        return {"readOnlyHint": True}
    return {}


def einordnung(name: str) -> str:
    if name in ZWEISTUFIG:
        return "zweistufig"
    if name in KLEIN_SOFORT:
        return "klein_sofort"
    if name in UMKEHRBAR:
        return "umkehrbar"
    return ""
