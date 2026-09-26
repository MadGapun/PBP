"""Die Phasen der Ersterfassung — geliefert, wenn sie dran sind (H30, #1087 G9).

Der Ersterfassungs-Prompt hatte 12.671 Zeichen: jede Phase in allen
Einzelheiten, dazu Entwicklungsgeschichte, und das alles schon beim
ersten Satz. Jetzt traegt der Prompt nur Ablauf und Regeln; die Anleitung
einer Phase kommt mit der Werkzeugantwort, die sie einleitet
(`erfassung_fortschritt_lesen`, `erfassung_fortschritt_speichern`,
`kennlerngespraech_abschliessen`) — im Feld `anleitung`.
"""
from __future__ import annotations

from .menue import pfad

BEREICHE = ("persoenliche_daten", "berufserfahrung", "ausbildung",
            "kompetenzen", "praeferenzen", "review_abgeschlossen")

ERFASSUNG = """PHASE 2 UND 3: PROFIL ERFASSEN
Arbeite dich organisch durch, was fehlt; speichere sofort.
- Persönliche Daten: nur Fehlendes erfragen; profil_erstellen().
- Berufserfahrung je Station: Firma, Position, Zeitraum, Aufgaben,
  Ergebnisse, Technologien; für relevante Arbeit ein Projekt im
  STAR-Format. position_hinzufuegen(), projekt_hinzufuegen().
  Praktika, Werkstudentenjobs, Ehrenamt zählen mit; Familienphasen
  respektvoll und ohne Wertung; bei Freelancern zählen Projekte mehr als
  Positionen; lange Zugehörigkeit nach Entwicklung aufschlüsseln;
  häufige Wechsel als Breite positionieren.
- Ausbildung, Weiterbildung, Zertifikate: ausbildung_hinzufuegen().
- Kompetenzen aus Gespräch und Dokumenten ableiten, bei alten nach der
  Aktualität fragen: skill_hinzufuegen(name, category, level,
  years_experience, last_used_year).
- Motivation, Arbeitsrahmen, No-Gos: profil_bearbeiten(bereich='notizen',
  aktion='anhang', ...).
- Praeferenzen: Zielrollen, Festanstellung oder Freelance, Region,
  Remote, Reisebereitschaft, Umzug: profil_erstellen().
- Gehalt, Tages- und Stundensatz und die Entfernungsgrenze gehören in
  die Suchkriterien, nicht ins Profil: suchkriterien_setzen(min_gehalt=...,
  wunsch_gehalt=..., min_tagessatz=..., wunsch_tagessatz=...,
  min_stundensatz=..., wunsch_stundensatz=..., max_entfernung_km=...).
- Jobtitel: 5-10 realistische Titel (deutsch und englisch) vorschlagen,
  freigeben lassen, jobtitel_speichern(titel=[...]).
Nach jedem Bereich: erfassung_fortschritt_speichern(bereich=...).
"""

REVIEW = """PHASE 4: REVIEW
- profil_zusammenfassung() aufrufen und die Zusammenfassung zeigen.
- Fragen: "Stimmt das so? Möchtest du etwas ändern, ergänzen oder löschen?"
- Korrekturen mit profil_bearbeiten(); so lange, bis der Mensch
  ausdrücklich sagt, dass alles passt.
- Dann: erfassung_fortschritt_speichern(bereich='review_abgeschlossen',
  abgeschlossen=True) und kennlerngespraech_abschliessen() — dessen
  Antwort führt zur ersten Suche. Nicht aufhören, bevor sie läuft.
"""

SUCHE = f"""PHASE 5: SUCHBEGRIFFE UND ERSTE SUCHE
Ziel: der Mensch verlässt das Gespräch mit einer laufenden Suche.
1. keyword_vorschlaege() aufrufen; bei frischem Profil stehen die
   Vorschläge im Feld profil_vorschlaege. MUSS- und PLUS-Begriffe kurz
   zeigen und bestaetigen lassen.
2. Speichere die bestätigten Begriffe mit suchkriterien_setzen(
   keywords_muss=[...], keywords_plus=[...]); Region und Entfernung aus
   Phase 3 gleich mit: regionen=[...] (Remote ist ein Eintrag in dieser
   Liste, kein eigener Parameter) und max_entfernung_km=30 als eine Zahl.
3. Keine Portalfragen: "Ich starte mit drei schnellen Jobbörsen ohne
   Login: Bundesagentur, Arbeitnow und Indeed. Weitere kannst du später
   unter {pfad('quellen')} dazuschalten."
4. jobsuche_starten(quellen=['bundesagentur', 'arbeitnow',
   'jobspy_indeed']) — die Quellen werden dabei als aktiv uebernommen.
   Die Suche läuft im Hintergrund; nicht in einer Schleife warten. Fragt
   der Mensch später nach: einmal jobsuche_status(), bei "fertig"
   stellen_anzeigen(pro_seite=5).
5. Bei 0 Treffern steht im Ergebnis ein Feld 'diagnose': Ursache in einem
   Satz, nächste Aktion vorschlagen.
6. Nur einmal und nur wenn eine Antwort zeigt, dass die lokale KI fehlt:
   Ollama (kostenlos, lokal, https://ollama.com/download) kann Stellen
   vorsortieren; Einrichtung unter {pfad('lokale_ki')}. Nicht drängen.
"""


def stand(profile: dict | None, fortschritt: dict | None = None) -> dict:
    """Welche Bereiche erledigt sind — aus dem Profil, nicht nur aus Haken."""
    if not profile:
        return {b: False for b in BEREICHE}
    fortschritt = fortschritt if fortschritt is not None else (profile.get("erfassung_fortschritt") or {})
    prefs = profile.get("preferences") or {}
    if isinstance(prefs, str):
        import json
        try:
            prefs = json.loads(prefs) if prefs else {}
        except ValueError:
            prefs = {}
    return {
        "persoenliche_daten": bool(profile.get("name") and profile.get("email")),
        "berufserfahrung": len(profile.get("positions", [])) > 0,
        "ausbildung": len(profile.get("education", [])) > 0,
        "kompetenzen": len(profile.get("skills", [])) > 0,
        "praeferenzen": bool(prefs.get("stellentyp")),
        "review_abgeschlossen": bool(fortschritt.get("review_abgeschlossen", False)),
    }


def anleitung(bereiche: dict) -> tuple[str, str]:
    """(Phase, Anleitung) fuer den naechsten offenen Schritt."""
    inhalt = [b for b in BEREICHE if b != "review_abgeschlossen"]
    if not all(bereiche.get(b) for b in inhalt):
        return "erfassung", ERFASSUNG
    if not bereiche.get("review_abgeschlossen"):
        return "review", REVIEW
    return "suche", SUCHE
