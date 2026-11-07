"""Was PBP wohin schickt (H25, #1087 G5, A8).

Bis v1.7.134 meldete die Datenschutz-Anzeige Profil, Bewerbungen und
Dokumente als "nur lokal" und an Claude nur "Prompts via Copy & Paste".
Tatsaechlich liefern die Werkzeuge Claude Volltexte, Adresse und
Geburtsdatum, sobald man mit Claude arbeitet; Nominatim, die
Update-Pruefung und OpenRouteService fehlten in der Liste. Der Satz fuer
README, FAQ und den einmaligen Hinweis steht als `KURZ` hier.
"""
from __future__ import annotations

from .menue import pfad

KURZ = ("Gespeichert wird lokal auf deinem Rechner; was du mit Claude "
        "bearbeitest, geht an Anthropic.")

DATENFLUSS = {
    "local_only": [
        "Datenbank und Dateien liegen nur auf diesem Rechner: Profil, "
        "Bewerbungen, Dokumente, Stellen, Statistiken",
    ],
    "sent_to_claude": [
        "Was du mit Claude bearbeitest, geht an Anthropic",
        "dein Profil einschließlich Adresse und Geburtsdatum",
        "der Text deiner Dokumente (Lebenslauf, Zeugnisse, Mails)",
        "Anzeigentexte der Stellen",
        "Notizen zu Bewerbungen",
        f"einzelne Bereiche sperrst du unter {pfad('claude')}",
    ],
    "external_requests": [
        "Jobbörsen (nur bei einer Suche)",
        "JobSpy (läuft lokal und fragt Indeed und LinkedIn ab)",
        "OpenStreetMap Nominatim (dein Wohnort und die Orte der Stellen, als Koordinaten für die Entfernung)",
        "OpenRouteService (Fahrstrecken, nur mit eigenem Schlüssel)",
        "GitHub und elwosa.de (Update-Prüfung und Tipps, anonym)",
    ],
}

HINWEIS_SCHLUESSEL = "datenschutz_hinweis_gezeigt"


def datenfluss(db=None) -> dict:
    """`DATENFLUSS`, und nur wenn eine Aufgabe fuer die Anthropic-API freigegeben ist, eine vierte Zeile (#1236).

    Der API-Weg ist die einzige Stelle, an der PBP SELBST Angaben an einen Cloud-Dienst schickt (nicht Claude Desktop). Er ist
    eine sichtbare Ausnahme von „laeuft komplett lokal“ -- aber nur, solange er an ist. Ohne Freigabe bleibt die Auskunft,
    wie sie war.
    """
    fluss = {art: list(zeilen) for art, zeilen in DATENFLUSS.items()}
    if db is not None:
        try:
            from . import api_backend
            zeilen = api_backend.datenfluss_zeilen(db)
        except Exception:  # noqa: BLE001 -- die Datenschutz-Anzeige faellt nicht an der Zusatzzeile
            zeilen = []
        if zeilen:
            fluss["sent_to_api"] = [
                "PBP ruft selbst die Anthropic-API auf (dein API-Weg); die genannten Angaben verlassen deinen Rechner",
                *zeilen,
                f"abschalten unter {pfad('lokale_ki')}",
            ]
    return fluss


def einmaliger_hinweis(db) -> str | None:
    """Der Satz beim ersten Mal, danach nichts mehr."""
    try:
        if db.get_setting(HINWEIS_SCHLUESSEL, False):
            return None
        db.set_setting(HINWEIS_SCHLUESSEL, True)
    except Exception:
        return None
    return (f"{KURZ} Einzelne Bereiche lassen sich unter {pfad('claude')} "
            "sperren. Sag das dem Menschen einmal zu Beginn.")
