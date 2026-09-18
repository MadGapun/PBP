"""Zentrales Ablehnungsgrund-Vokabular + Normalisierung (#913, v1.7.17).

Befund: 101 verschiedene Freitext-Gruende in 182 Datensaetzen — die
dokumentierte Whitelist wurde nie durchgesetzt, weil mehrere Schreibpfade
(Ollama-Autofilter mit 'auto:'-Praefix, Duplikat-Erkennung, direkte
dismiss_job-Aufrufe) an der Normalisierung vorbeischrieben. Folge: die
drei haeufigsten Nutzer-Signale erzeugten NULL Lerneffekt und jede
Aggregation ueber Ablehnungsgruende war systematisch falsch
('Dublikat'/'duplikat'/'Duplikat von ...' = fuenf Schreibweisen).

Regeln:
- ALLE Schreibpfade auf jobs.dismiss_reason laufen durch
  `normalisiere_dismiss_wert` (verdrahtet in db.dismiss_job).
- Freitext ist nicht wertlos — er wandert nach jobs.dismiss_note,
  nicht in das Feld, auf dem die Lernmechanik rechnet.
- `falsches_system` (Fachgebiet stimmt, Plattform nicht) und
  `falsche_branche` (Rolle stimmt, Branche nicht) sind seit v1.7.17
  regulaere Gruende — die zwei fachlich wertvollen Freitext-Faelle aus
  dem Bestand (41x / 38x), Kernregeln dieses Nutzerprofils.
"""
from __future__ import annotations

import json
import re

# Regulaere, vom Nutzer waehlbare Gruende. Erweiterung NUR hier —
# tools/jobs.py, CLAUDE.md und die dismiss_reasons-Seeds haengen daran.
STANDARD_GRUENDE = [
    "zu_weit_entfernt",
    "gehalt_zu_niedrig",
    "falsches_fachgebiet",
    "falsches_system",
    "falsche_branche",
    "zu_junior",
    "zu_senior",
    "unpassendes_arbeitsmodell",
    "firma_uninteressant",
    "zeitarbeit",
    "befristet",
    "bereits_beworben",
    "duplikat",
    "kein_hochschulabschluss",
    "sonstiges",
]

# Systemseitig legitime Werte, die kein Nutzer waehlt, aber Tools
# schreiben (Statistik-relevant, bleiben unveraendert).
SYSTEM_GRUENDE = {
    "bewerbung_erstellt",
    "firma_blacklisted",
    "profil_match_negativ",
    "veraltet_url",
    # bewerbung_zu_anfrage_konvertieren: der Eintrag war nie eine
    # Bewerbung, sondern eine sofort abgelehnte Recruiter-Anfrage.
    "war_nur_anfrage",
}

# Exakte Alt-Schreibweisen -> kanonischer Grund (Bestands-Mapping aus
# der #913-Auswertung; case-insensitiv verglichen).
_ALIAS = {
    "dublikat": "duplikat",
    "duplikat_manuell": "duplikat",
    "duplikat_bewerbung": "duplikat",
    "ueberqualifiziert": "zu_senior",
    "überqualifiziert": "zu_senior",
    "falsches system": "falsches_system",
    "falsche branche": "falsche_branche",
    "veraltet": "veraltet_url",
    "abgelaufen": "veraltet_url",
    # Kurz-Vokabular von bewerbung_zu_anfrage_konvertieren
    "standort": "zu_weit_entfernt",
    "branche": "falsche_branche",
}


def _kanonisch_einzeln(raw: str, erlaubt: set) -> tuple[str, str | None]:
    """(kanonischer Grund, Freitext-Rest oder None) fuer EINEN Wert."""
    text = str(raw or "").strip()
    if not text:
        return "sonstiges", None
    lower = text.lower().strip()

    if lower in erlaubt:
        return lower, None
    if lower in _ALIAS:
        return _ALIAS[lower], None

    # v1.7.23 (#944): Ein Vokabular-Wert mit angehaengter Zeichensetzung
    # ("zu_weit_entfernt.") fiel bisher aus der Whitelist und wurde zu
    # 'sonstiges' plus Freitext — im Bericht erschien derselbe Grund
    # dadurch ZWEIMAL als eigene Kategorie, und der Lerneffekt ging
    # verloren. Ein Schlusspunkt ist keine andere Kategorie.
    entkleidet = lower.strip(" .;,:!-")
    if entkleidet and entkleidet != lower:
        if entkleidet in erlaubt:
            return entkleidet, None
        if entkleidet in _ALIAS:
            return _ALIAS[entkleidet], None

    # Systempfad 'auto:<grund>' bzw. 'auto:<grund>:<llm-begruendung>' —
    # Grund extrahieren, Begruendung (falls vorhanden) ist Freitext.
    # Der Kurzform-Fall ohne Begruendung existiert im Altbestand (#671).
    m = re.match(r"^auto:([a-z_]+)(?::(.*))?$", text,
                 re.IGNORECASE | re.DOTALL)
    if m:
        grund = m.group(1).lower()
        rest = (m.group(2) or "").strip()
        if grund in erlaubt:
            return grund, (rest or None)
        return "sonstiges", text

    # 'Duplikat von <hash>: ...' u. ae.
    if lower.startswith("duplikat") or lower.startswith("dublikat"):
        return "duplikat", text

    # Muster-Heuristiken (uebernommen aus dem alten
    # _normalize_dismiss_reason in tools/jobs.py — jetzt an EINER Stelle).
    if "bereits beworben" in lower or "schon beworben" in lower:
        return "bereits_beworben", None
    if "zu weit" in lower or "entfernung" in lower:
        return "zu_weit_entfernt", None
    if "gehalt" in lower or "zu niedrig" in lower:
        return "gehalt_zu_niedrig", None
    if "zeitarbeit" in lower or "arbeitnehmerüberl" in lower \
            or "arbeitnehmerueberl" in lower:
        return "zeitarbeit", None
    if "befristet" in lower:
        return "befristet", None
    if "hochschul" in lower or "studium" in lower or "abschluss" in lower \
            or "ats" in lower:
        return "kein_hochschulabschluss", None

    # Alles andere ist Freitext: zaehlbar als 'sonstiges', lesbar als Note.
    return "sonstiges", text


def normalisiere_dismiss_wert(raw, custom: set | frozenset = frozenset()
                              ) -> tuple[str, list]:
    """Normalisiert einen dismiss_reason-Speicherwert (#913).

    `raw` kann ein Plain-String, eine JSON-Liste als String oder eine
    echte Liste sein. Rueckgabe: (speicherwert, freitexte) — der
    Speicherwert behaelt das Eingabeformat (Liste -> JSON-Liste,
    String -> String), enthaelt aber nur noch Whitelist-Werte;
    `freitexte` gehoeren nach jobs.dismiss_note.
    """
    erlaubt = set(STANDARD_GRUENDE) | SYSTEM_GRUENDE | {
        str(c).lower() for c in (custom or ())}

    war_liste = isinstance(raw, (list, tuple))
    werte = list(raw) if war_liste else None
    if werte is None:
        text = str(raw or "").strip()
        if text.startswith("[") and text.endswith("]"):
            try:
                geparst = json.loads(text)
                if isinstance(geparst, list):
                    werte = geparst
                    war_liste = True
            except (ValueError, TypeError):
                pass
        if werte is None:
            werte = [text]

    gruende: list = []
    freitexte: list = []
    for w in werte:
        grund, freitext = _kanonisch_einzeln(w, erlaubt)
        if grund not in gruende:
            gruende.append(grund)
        if freitext:
            freitexte.append(freitext)
    if not gruende:
        gruende = ["sonstiges"]

    if war_liste:
        return json.dumps(gruende, ensure_ascii=False), freitexte
    return gruende[0], freitexte


def ist_konform(raw, custom: set | frozenset = frozenset()) -> bool:
    """True, wenn der Speicherwert bereits nur Whitelist-Gruende traegt."""
    erlaubt = set(STANDARD_GRUENDE) | SYSTEM_GRUENDE | {
        str(c).lower() for c in (custom or ())}
    try:
        werte = json.loads(raw) if str(raw).strip().startswith("[") else [raw]
        if not isinstance(werte, list):
            werte = [werte]
    except (ValueError, TypeError):
        werte = [raw]
    return all(str(w).strip() in erlaubt for w in werte)


# --------------------------------------------------------------- Lesen
# v1.7.121: Der Speicherwert hat ZWEI Formen — ein einzelner Grund als
# String, mehrere als JSON-Liste (beides gewollt, siehe
# `normalisiere_dismiss_wert`). Drei Leser zaehlten mit
# `GROUP BY dismiss_reason` und fuehrten damit `["falsches_fachgebiet"]`
# und `falsches_fachgebiet` als zwei verschiedene Gruende: gemeldet als
# 32,1 % und 31,3 %, obwohl es EIN Grund mit 63,4 % ist. Gezaehlt wird
# deshalb nur noch hier.

def gruende_aus_wert(raw) -> list:
    """Zerlegt einen gespeicherten dismiss_reason in seine Gruende."""
    if raw is None:
        return []
    if isinstance(raw, (list, tuple)):
        werte = list(raw)
    else:
        text = str(raw).strip()
        werte = [text]
        if text.startswith("[") and text.endswith("]"):
            try:
                geparst = json.loads(text)
                if isinstance(geparst, list):
                    werte = geparst
            except (ValueError, TypeError):
                pass
    gruende: list = []
    for w in werte:
        g = str(w or "").strip()
        if not g:
            continue
        # Altbestand vor #913: "Duplikat: <hash>" ist der Grund duplikat.
        if g.lower().startswith("duplikat:"):
            g = "duplikat"
        if g not in gruende:
            gruende.append(g)
    return gruende


def gruende_zaehlen(conn, profile_id, ausser=("bewerbung_erstellt",)
                    ) -> tuple[list, int]:
    """Zaehlt die Aussortier-Gruende ueber beide Speicherformen.

    Rueckgabe: ([(grund, anzahl_stellen), ...] absteigend, stellen_gesamt).
    Eine Stelle mit zwei Gruenden zaehlt bei beiden, im Gesamtwert aber
    einmal — der Anteil beantwortet also "bei wie vielen Stellen spielte
    dieser Grund eine Rolle". Stellen, deren Gruende ALLE in `ausser`
    liegen, zaehlen gar nicht.
    """
    rows = conn.execute(
        "SELECT dismiss_reason, COUNT(*) AS n FROM jobs "
        "WHERE is_active=0 AND (profile_id=? OR profile_id IS NULL) "
        "AND COALESCE(dismiss_reason,'') != '' "
        "GROUP BY dismiss_reason", (profile_id,)
    ).fetchall()
    zaehler: dict = {}
    gesamt = 0
    for r in rows:
        gruende = [g for g in gruende_aus_wert(r["dismiss_reason"])
                   if g not in ausser]
        if not gruende:
            continue
        gesamt += r["n"]
        for g in gruende:
            zaehler[g] = zaehler.get(g, 0) + r["n"]
    liste = sorted(zaehler.items(), key=lambda kv: (-kv[1], kv[0]))
    return liste, gesamt
