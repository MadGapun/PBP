r"""Was gehoert wozu, wenn geloescht wird (#1025, #1024).

Nicht zu verwechseln mit `dashboard_bereiche.py` — das ist der Katalog
der Bildschirm-Bereiche (#985). Hier geht es um Datenbereiche und
darum, welche Tabellen ein Loeschvorgang anfassen muss.

## Der Befund

PBP hatte drei Loeschwege und drei verschiedene Vorstellungen davon,
was dazugehoert:

| Weg | Mechanik | Deckung |
|---|---|---|
| DSGVO-Loeschung | loescht die DATEI | vollstaendig |
| Factory Reset | `DELETE FROM` aus einer festen Liste | 18 von 47 |
| Profil loeschen | dito | 12 von 29 profilgebundenen |

Am Bestand gemessen laesst der Factory Reset **29 Tabellen stehen** —
und nicht nur Einstellungen, sondern Inhalte: 81 Kontakte, 68
Bewerbungs-Stellen-Verknuepfungen, 26 Dokumentversionen, 15
Recherche-Notizen, 1.304 Zeilen Aktivitaetsprotokoll. "Die App wird wie
neu" trifft damit nicht zu.

**`contacts` traegt Namen und Mailadressen Dritter.** Wer den Factory
Reset waehlt, um den Rechner weiterzugeben, laesst personenbezogene
Daten zurueck. Das ist der Grund, warum diese Stufe vor dem
Oberflaechen-Umbau kommt.

Beim Profil-Loeschen bleiben 17 Tabellen als verwaiste Zeilen stehen,
mit einer `profile_id`, die es nicht mehr gibt.

Die Ursache ist in beiden Faellen dieselbe, und der Melder hat sie
benannt: *"Vollstaendig ist nur der DSGVO-Weg — und zwar nicht, weil
seine Liste besser gepflegt waere, sondern weil er keine hat."*

## Deshalb wird abgeleitet, nicht aufgezaehlt

Welche Tabellen es gibt, steht in `sqlite_master`. Ob eine Tabelle an
einem Profil haengt, steht in `PRAGMA table_info` (Spalte `profile_id`)
oder in `PRAGMA foreign_key_list` (Weg ueber eine Elterntabelle). Beides
wird zur Laufzeit gelesen.

Aufgezaehlt wird nur noch die ZUORDNUNG zu einem Bereich — und die
schuetzt ein Guard: `unzugeordnet()` meldet jede Tabelle der Datenbank,
die in keinem Bereich steht. Eine neue Tabelle faellt damit nicht mehr
still heraus, sondern bricht den Test. Das ist dieselbe Bauform wie
`_BEWAHREN` plus Strukturpruefung aus v1.7.74: **eine Aufzaehlung
schuetzt einmal, eine Strukturpruefung immer.**

## Drei Bezugsarten, alle aus dem Schema gelesen

* `profil` — die Tabelle hat eine Spalte `profile_id`
* `mittelbar` — sie haengt ueber einen Fremdschluessel an einer
  Tabelle, die ihrerseits am Profil haengt (`projects` ueber
  `positions`, `skill_periods` ueber `skills`, `follow_ups` ueber
  `applications`)
* `geteilt` — sie gilt fuer alle Profile (`settings`, `scraper_health`,
  `background_jobs`, ...)

Beim Leeren EINES Profils bleiben geteilte Tabellen unangetastet. Beim
Leeren aller Bereiche gehen sie mit.

Drei Bezuege sind im Schema nicht deklariert und stehen deshalb in
`_ZUSATZ_BEZUG` — allen voran `job_sources`, das ueber `job_hash` an
den Stellen haengt, ohne Fremdschluessel und ohne `profile_id`. Wer den
Stellen-Bestand leert, muesste die Fundstellen sonst stehen lassen.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

#: Bereich -> Tabellen. Die einzige verbliebene Aufzaehlung, und sie
#: ist durch `unzugeordnet()` gegen das Schema abgesichert.
BEREICHE: dict[str, tuple] = {
    "profil": (
        "profile", "positions", "projects", "education", "skills",
        "skill_periods", "suggested_job_titles",
    ),
    "bewerbungen": (
        "applications", "application_events", "application_jobs",
        "application_emails", "application_meetings", "application_costs",
        "follow_ups", "tasks", "contacts", "contact_links",
        # v1.7.88 (#884): haengt am Kontakt, gehoert also dorthin.
        "contact_references",
        "contact_categories", "meeting_categories",
        "interview_reflections", "research_notes",
    ),
    "stellen": (
        "jobs", "job_sources",
    ),
    "dokumente": (
        "documents", "documents_new", "document_versions",
        "extraction_history",
    ),
    "einstellungen": (
        "settings", "search_criteria", "scoring_config", "blacklist",
        "dismiss_reasons", "user_preferences", "custom_sources",
        "newsletter_sources", "portal_search_profiles", "components",
        "plugins",
    ),
    "gelerntes": (
        "user_activity_events", "learning_insights", "blacklist_blocks",
        "scraper_health", "scraper_runs", "background_jobs",
        "elwosa_messages", "elwosa_pending_lines", "anonymisierung_map",
    ),
}

#: Klartext fuer die Oberflaeche — was der Bereich ist und was sein
#: Verlust kostet. Der Melder hat ausdruecklich darum gebeten: dass mit
#: den aussortierten Stellen auch die Lernsignale verschwinden, sieht
#: man der Aktion sonst nicht an.
BESCHREIBUNG = {
    "profil": ("Dein Lebenslauf: Stationen, Projekte, Ausbildung, "
               "Kompetenzen. Das ist die Arbeit, die am meisten Zeit "
               "gekostet hat."),
    "bewerbungen": ("Bewerbungen samt Verlauf, Terminen, Aufgaben und "
                    "Kontakten. Enthaelt Namen und Mailadressen "
                    "Dritter."),
    "stellen": ("Der Stellen-Bestand samt Fundstellen. **Mit den "
                "aussortierten Stellen verschwinden auch die "
                "Lernsignale** — Ablehnungsgruende, "
                "Wiedergaenger-Muster, Kalibrierung."),
    "dokumente": ("Hochgeladene Dokumente samt Versionen und "
                  "Extraktionsverlauf. Die Dateien auf der Platte "
                  "gehoeren dazu."),
    "einstellungen": ("Suchkriterien, Scoring-Regler, Blacklist, eigene "
                      "Ablehnungsgruende, Quellen-Konfiguration."),
    "gelerntes": ("Aktivitaetsprotokoll, abgeleitete Erkenntnisse, "
                  "Quellen-Gesundheit, Elwosa-Verlauf."),
}

#: Tabellen, die NICHT in jeder Datenbank stehen — und zwar zu Recht.
#: Eine Zuordnung ist trotzdem Pflicht: sobald die Tabelle existiert,
#: bliebe sie beim Loeschen sonst liegen. Ein Guard, der ihr Fehlen
#: meldet, gibt bei korrektem Zustand Alarm und wird nach dem zweiten
#: Mal ignoriert (#929).
#:
#: Zwei Gruende, beide gemessen:
#:
#: 1. **Erst bei Bedarf angelegt.** Ein Safety-Net legt sie beim ersten
#:    Schreibzugriff an, statt das Schema zu bumpen.
#: 2. **Nur auf der 1.8-Linie.** Stable steht auf Schema v48, die Beta
#:    auf v52. Wer von 1.7 auf 1.8 wechselt, bekommt sie dazu — und
#:    ohne Zuordnung waeren sie ab dann unloeschbar.
_NICHT_IN_JEDER_DATENBANK = {
    # (1) services/stellen_quellen.py (#951), beim ersten Zweitfund.
    #     Im gemessenen Bestand: 43 Zeilen.
    "job_sources",
    # (1) services/pii_bestand.py (#946), beim ersten Anonymisieren.
    "anonymisierung_map",
    # (1) Ueberbleibsel der v19-Migration (#242): dort wurde `documents`
    #     ueber eine Zwischentabelle umgebaut, und die Zwischentabelle
    #     ist nie gefallen. Sie steht seitdem leer in jeder migrierten
    #     Datenbank — im gemessenen Bestand 0 Zeilen. Sie gehoert
    #     trotzdem in den Bereich: waere sie je befuellt, traege sie
    #     Dokumente.
    "documents_new",
    # (2) I10/#751, v1.8.0-beta.0 — installierte Komponenten.
    "components",
    # (2) J1/#504, v1.8.0-beta.2 — gekoppelte Plugins samt Schluessel.
    "plugins",
    # (2) J5/#525, v1.8.0-beta.4 — gelernte Newsletter-Quellen.
    "newsletter_sources",
    # (2) B16/#627, v1.8.0-beta.5 — eigene Karriereseiten.
    "custom_sources",
    # (2) B25/#735, v1.8.0-beta.5 — Lauf-Historie je Quelle.
    "scraper_runs",
}

#: Zeilen, die ein Leeren NIE erfassen darf — Schluessel ist die
#: Tabelle, Wert eine WHERE-Bedingung, die sie ausnimmt.
#: `schema_version` steht in `settings` und ist keine Nutzerdatei,
#: sondern der Stand der Datenbank selbst. Ohne diese Zeile haelt die
#: naechste Migration die Datenbank fuer eine aeltere Fassung. Der alte
#: Factory Reset hatte die Ausnahme bereits (`WHERE key !=
#: 'schema_version'`) — sie geht beim Umbau leicht verloren, deshalb
#: steht sie hier als Regel und nicht in einem SQL-Text.
_BEWAHREN_ZEILEN = {
    "settings": "key != 'schema_version'",
}

#: Bezuege, die im Schema nicht als Fremdschluessel stehen.
#: (Tabelle -> (Elterntabelle, eigene Spalte, Spalte der Eltern))
_ZUSATZ_BEZUG = {
    # Haengt ueber den Hash an einer Stelle — ohne Fremdschluessel und
    # ohne profile_id. Ohne diesen Eintrag bliebe beim Leeren des
    # Stellen-Bestands eine Zeile je Fundstelle liegen, die auf nichts
    # mehr zeigt.
    "job_sources": ("jobs", "job_hash", "hash"),
    "application_jobs": ("applications", "application_id", "id"),
}

#: Die Profiltabelle selbst — ihre `id` IST die Profil-Kennung.
_PROFILTABELLE = "profile"

PROFIL = "profil"
MITTELBAR = "mittelbar"
GETEILT = "geteilt"


def tabellen(db) -> list:
    """Alle Tabellen der Datenbank — aus dem Schema, nicht aus einer
    Liste."""
    return sorted(r[0] for r in db.connect().execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%'"))


def unzugeordnet(db) -> dict:
    """Der Guard: was steht in der Datenbank und in keinem Bereich?

    Und die Gegenrichtung: was steht in einem Bereich und nicht in der
    Datenbank? Beides ist ein Befund — der erste bedeutet, dass eine
    Tabelle beim Loeschen stehen bliebe, der zweite, dass ein Eintrag
    veraltet ist.
    """
    vorhanden = set(tabellen(db))
    zugeordnet: set = set()
    doppelt: list = []
    for bereich, liste in BEREICHE.items():
        for t in liste:
            if t in zugeordnet:
                doppelt.append(t)
            zugeordnet.add(t)
    fehlend = zugeordnet - vorhanden
    return {
        "fehlt_im_bereich": sorted(vorhanden - zugeordnet),
        "kennt_die_datenbank_nicht": sorted(
            fehlend - _NICHT_IN_JEDER_DATENBANK),
        "hier_nicht_vorhanden": sorted(
            fehlend & _NICHT_IN_JEDER_DATENBANK),
        "mehrfach_zugeordnet": sorted(doppelt),
    }


def _spalten(db, tabelle: str) -> list:
    try:
        return [r[1] for r in db.connect().execute(
            f"PRAGMA table_info({tabelle})")]
    except Exception as exc:  # pragma: no cover
        logger.debug("Spalten von %s nicht lesbar: %s", tabelle, exc)
        return []


def _eltern(db, tabelle: str) -> tuple | None:
    """(Elterntabelle, eigene Spalte, Spalte der Eltern) oder None.

    **Ein Selbstbezug ist keine Sackgasse, sondern nur kein Weg nach
    oben.** Der erste Entwurf nahm den ERSTEN Fremdschluessel und gab
    auf, wenn er auf dieselbe Tabelle zeigte. `application_events` hat
    genau den: `parent_event_id` verweist auf die eigene Tabelle
    (Antwort-Kette), und erst danach kommt `application_id ->
    applications`. Die Tabelle galt damit als `geteilt` und wurde beim
    Leeren eines Profils gar nicht angefasst — ihre Zeilen blieben als
    Waisen liegen.

    Aufgefallen ist es nur an einer FRISCHEN Datenbank: in der
    gewachsenen fehlt der Selbstbezug, dort lief alles richtig. Die
    Messung auf der Kopie hat den Fehler also nicht finden KOENNEN —
    **eine Messung am eigenen Bestand prueft eine Installation, nicht
    das Programm.**

    Bevorzugt wird ein Elternteil mit eigener `profile_id`: `documents`
    zeigt auf `applications` UND auf `positions`, und beide fuehren zum
    Profil — aber nur ein Weg gehoert in die WHERE-Klausel.
    """
    if tabelle in _ZUSATZ_BEZUG:
        return _ZUSATZ_BEZUG[tabelle]
    kandidaten: list = []
    try:
        for r in db.connect().execute(f"PRAGMA foreign_key_list({tabelle})"):
            # (id, seq, table, from, to, ...)
            if r[2] == tabelle:  # Selbstbezug — fuehrt nicht nach oben
                continue
            kandidaten.append((r[2], r[3], r[4] or "id"))
    except Exception as exc:  # pragma: no cover
        logger.debug("Fremdschluessel von %s nicht lesbar: %s", tabelle, exc)
        return None
    if not kandidaten:
        return None
    for k in kandidaten:
        if k[0] == _PROFILTABELLE or "profile_id" in _spalten(db, k[0]):
            return k
    return kandidaten[0]


def bezug(db, tabelle: str, _tiefe: int = 0) -> str:
    """Wie haengt diese Tabelle an einem Profil?

    Abgeleitet, nicht aufgezaehlt: erst die eigene Spalte, dann der Weg
    ueber die Eltern. Die Tiefenbegrenzung ist ein Schutz gegen einen
    Zyklus im Schema, nicht gegen die heutige Struktur.
    """
    if tabelle == _PROFILTABELLE:
        return PROFIL
    if "profile_id" in _spalten(db, tabelle):
        return PROFIL
    if _tiefe >= 4:
        return GETEILT
    e = _eltern(db, tabelle)
    if e and e[0] != tabelle:
        return MITTELBAR if bezug(db, e[0], _tiefe + 1) in (
            PROFIL, MITTELBAR) else GETEILT
    return GETEILT


def _mit_bewahren(tabelle: str, klausel: str) -> str:
    """Haengt die Bewahren-Regel an eine WHERE-Klausel an."""
    regel = _BEWAHREN_ZEILEN.get(tabelle)
    if not regel:
        return klausel
    if klausel.strip() in ("", "WHERE 0"):
        return klausel or f" WHERE {regel}"
    return f"{klausel} AND {regel}"


def _bedingung(db, tabelle: str, profil_id: str | None) -> str:
    """Die WHERE-Klausel, die eine Tabelle auf ein Profil einschraenkt.

    Leerer String heisst: alles. Ein `WHERE 0` heisst: nichts — das
    trifft geteilte Tabellen beim Leeren eines einzelnen Profils.
    """
    if not profil_id:
        return ""
    art = bezug(db, tabelle)
    if art == GETEILT:
        return " WHERE 0"
    if tabelle == _PROFILTABELLE:
        return " WHERE id = :pid"
    if "profile_id" in _spalten(db, tabelle):
        return " WHERE profile_id = :pid"
    e = _eltern(db, tabelle)
    if not e:  # pragma: no cover
        return " WHERE 0"
    eltern, eigene, deren = e
    return (f" WHERE {eigene} IN (SELECT {deren} FROM {eltern}"
            f"{_bedingung(db, eltern, profil_id)})")


#: Bereiche, bei denen eine Gesamtzahl zu wenig sagt — je Bereich die
#: Tabelle, die Spalte und der Klartext je Auspraegung.
#: Bei den Stellen hat der Melder ausdruecklich darum gebeten (#1024):
#: "wie viele Stellen betroffen sind, getrennt nach aktiv und
#: aussortiert". Der Grund steht in seinem Bericht — mit den
#: aussortierten Stellen verschwinden die Lernsignale, und das sieht man
#: einer Gesamtzahl nicht an.
_AUFTEILUNG = {
    "stellen": ("jobs", "is_active", {1: "aktiv", 0: "aussortiert"}),
}


def _aufteilung(db, bereich: str, profil_id: str | None) -> dict:
    """Die feine Aufteilung eines Bereichs, oder ein leeres dict.

    Sie ist bewusst KEIN eigener Bereich: wer nur die aktiven Stellen
    leeren will, waehlt das hier und nicht in einer zweiten Bereichsliste
    — sonst haetten wir zwei Modelle fuer dieselbe Frage.
    """
    eintrag = _AUFTEILUNG.get(bereich)
    if not eintrag:
        return {}
    tabelle, spalte, texte = eintrag
    if tabelle not in set(tabellen(db)):
        return {}
    if spalte not in _spalten(db, tabelle):
        return {}
    con = db.connect()
    klausel = _mit_bewahren(tabelle, _bedingung(db, tabelle, profil_id))
    try:
        zeilen = con.execute(
            f"SELECT {spalte}, COUNT(*) FROM {tabelle}{klausel} "
            f"GROUP BY {spalte}",
            {"pid": profil_id} if profil_id else {}).fetchall()
    except Exception as exc:  # pragma: no cover
        logger.debug("Aufteilung von %s fehlgeschlagen: %s", tabelle, exc)
        return {}
    # Beide Auspraegungen stehen immer da, auch mit 0 — eine fehlende
    # Zeile waere von "keine" nicht zu unterscheiden (#989).
    erg = {name: 0 for name in texte.values()}
    for wert, n in zeilen:
        name = texte.get(wert)
        if name:
            erg[name] = n
    return erg


def vorschau(db, bereiche=None, profil_id: str | None = None) -> dict:
    """Wie viele Zeilen betrifft das? — ohne etwas zu aendern.

    Der Melder hat ausdruecklich darum gebeten, und es ist dieselbe
    Linie wie bei den `dry_run`-Werkzeugen im Projekt: heute stehen bei
    zwei Aktionen dieselbe Beschreibung, und beide tun Verschiedenes.
    Eine Vorschau macht den Unterschied sichtbar, ohne dass man ihn
    beschreiben muss.
    """
    gewaehlt = list(bereiche or BEREICHE)
    con = db.connect()
    ergebnis, gesamt = {}, 0
    for bereich in gewaehlt:
        if bereich not in BEREICHE:
            continue
        zeilen, geteilt = {}, []
        summe = 0
        for t in BEREICHE[bereich]:
            if t not in set(tabellen(db)):
                continue
            art = bezug(db, t)
            if profil_id and art == GETEILT:
                geteilt.append(t)
                continue
            try:
                klausel = _mit_bewahren(t, _bedingung(db, t, profil_id))
                n = con.execute(
                    f"SELECT COUNT(*) FROM {t}{klausel}",
                    {"pid": profil_id} if profil_id else {}).fetchone()[0]
            except Exception as exc:  # pragma: no cover
                logger.debug("Zaehlen von %s fehlgeschlagen: %s", t, exc)
                continue
            if n:
                zeilen[t] = n
            summe += n
        ergebnis[bereich] = {
            "zeilen_gesamt": summe,
            "je_tabelle": dict(sorted(zeilen.items(), key=lambda p: -p[1])),
            "beschreibung": BESCHREIBUNG.get(bereich, ""),
            "geteilt_unangetastet": sorted(geteilt),
        }
        fein = _aufteilung(db, bereich, profil_id)
        if fein:
            ergebnis[bereich]["aufteilung"] = fein
        gesamt += summe
    dateien = _dateien(db, profil_id) if "dokumente" in gewaehlt else []
    haengend = haengende_verweise(db, gewaehlt, profil_id)
    return {"bereiche": ergebnis, "zeilen_gesamt": gesamt,
            "profil_id": profil_id,
            "dateien_auf_der_platte": len(dateien),
            "haengende_verweise": haengend["verweise"],
            "haengende_zeilen": haengend["zeilen_gesamt"],
            "hinweis": ("Geteilte Bereiche gelten fuer ALLE Profile und "
                        "bleiben beim Leeren eines einzelnen Profils "
                        "unangetastet." if profil_id else
                        "Ohne Profil-Angabe werden alle Profile erfasst.")}


def _dateien(db, profil_id: str | None) -> list:
    """Die Dateien auf der Platte, die zum Bereich `dokumente` gehoeren.

    Eine Zeile in `documents` zu loeschen entfernt die Datei nicht — und
    genau die traegt den Inhalt. Ein Loeschvorgang, der die Datenbank
    leert und die Dateien liegen laesst, erfuellt den Zweck nicht, um
    den es hier geht.
    """
    con = db.connect()
    gefunden: list = []
    for tab in ("documents", "documents_new"):
        if tab not in set(tabellen(db)):
            continue
        if "filepath" not in _spalten(db, tab):
            continue
        try:
            rows = con.execute(
                f"SELECT filepath FROM {tab} WHERE filepath IS NOT NULL "
                f"AND filepath != ''"
                + _bedingung(db, tab, profil_id).replace(" WHERE ", " AND ", 1),
                {"pid": profil_id} if profil_id else {}).fetchall()
        except Exception as exc:  # pragma: no cover
            logger.debug("Dateiliste aus %s nicht lesbar: %s", tab, exc)
            continue
        gefunden.extend(r[0] for r in rows if r[0])
    return sorted(set(gefunden))


def _alle_eltern(db, tabelle: str) -> set:
    """ALLE Tabellen, auf die diese zeigt — nicht nur die erste.

    `_eltern` liefert einen Bezug, weil fuer die WHERE-Klausel einer
    genuegt. Fuer die Reihenfolge genuegt er NICHT: `application_meetings`
    zeigt auf `application_emails` UND auf `applications`, und wer nur
    den ersten Fremdschluessel ansieht, ordnet falsch.
    """
    eltern = set()
    if tabelle in _ZUSATZ_BEZUG:
        eltern.add(_ZUSATZ_BEZUG[tabelle][0])
    try:
        for r in db.connect().execute(f"PRAGMA foreign_key_list({tabelle})"):
            eltern.add(r[2])
    except Exception as exc:  # pragma: no cover
        logger.debug("Fremdschluessel von %s nicht lesbar: %s", tabelle, exc)
    eltern.discard(tabelle)
    return eltern


def _reihenfolge(db, liste) -> list:
    """Kinder vor Eltern.

    **Die Richtung ist der ganze Punkt, und sie war im ersten Entwurf
    falsch herum.** Eine Kind-Tabelle wird ueber ihre Eltern
    eingeschraenkt (`job_hash IN (SELECT hash FROM jobs WHERE ...)`).
    Loescht man die Eltern zuerst, findet die Unterabfrage nichts mehr,
    und das Kind bleibt stehen — ohne Fehler, ohne Meldung.

    An der Kopie gemessen: mit der falschen Richtung blieben **43
    `job_sources` und 68 `application_jobs`** liegen. Ausgerechnet die
    beiden Tabellen aus `_ZUSATZ_BEZUG` — die anderen wurden von
    SQLites CASCADE aufgeraeumt und haben den Fehler damit verdeckt.
    Das ist woertlich der Defekt, den dieses Modul beheben soll, von
    seiner eigenen Hilfsfunktion wieder eingebaut.
    """
    # Die Profiltabelle zuletzt: heute haengt keine Bedingung an ihr
    # (alle anderen filtern ueber die Spalte `profile_id`, nicht ueber
    # eine Unterabfrage auf `profile`), und im Fremdschluessel-Graph ist
    # sie deshalb ein Blatt. Das ist eine Eigenschaft des heutigen
    # Schemas, keine Zusicherung — sie ans Ende zu stellen kostet
    # nichts und haelt auch dann, wenn jemand den Bezug spaeter
    # ausformuliert.
    nachtrag = [_PROFILTABELLE] if _PROFILTABELLE in set(liste) else []
    liste = [t for t in liste if t != _PROFILTABELLE]
    sortiert: list = []
    while liste:
        vorher = len(liste)
        for t in list(liste):
            # Zeigt noch eine verbliebene Tabelle auf t? Dann ist t
            # Elternteil und muss warten.
            if any(t in _alle_eltern(db, k) for k in liste if k != t):
                continue
            sortiert.append(t)
            liste.remove(t)
        if len(liste) == vorher:  # Zyklus — Rest anhaengen
            sortiert.extend(liste)
            break
    return sortiert + nachtrag


def leeren(db, bereiche=None, profil_id: str | None = None,
           dry_run: bool = True, dateien_loeschen: bool = True) -> dict:
    """Leert die gewaehlten Bereiche.

    `dry_run=True` ist die Vorgabe und aendert nichts.

    `dateien_loeschen=False` laesst die Dateien auf der Platte liegen
    und raeumt nur die Datenbank ab. Das ist KEIN Normalfall — es gibt
    ihn, weil `delete_profile` diesen Vertrag seit jeher anbietet.
    """
    vor = vorschau(db, bereiche, profil_id)
    if dry_run:
        return {"status": "vorschau", **vor,
                "hinweis": "Vorschau — es wurde nichts geloescht."}

    gewaehlt = [b for b in (bereiche or BEREICHE) if b in BEREICHE]
    betroffen = [t for b in gewaehlt for t in BEREICHE[b]
                 if t in set(tabellen(db))]

    # Erst die Dateien, dann die Zeilen: waere es andersherum, waeren
    # nach einem Abbruch mittendrin die Pfade weg und die Dateien da —
    # also nicht mehr auffindbar.
    dateien_weg, dateien_fehler = 0, 0
    if "dokumente" in gewaehlt and dateien_loeschen:
        from pathlib import Path
        for pfad in _dateien(db, profil_id):
            try:
                Path(pfad).unlink(missing_ok=True)
                dateien_weg += 1
            except Exception as exc:
                dateien_fehler += 1
                logger.warning("Datei %s nicht loeschbar: %s", pfad, exc)
    con = db.connect()
    geloescht: dict = {}
    for t in _reihenfolge(db, betroffen):
        klausel = _mit_bewahren(t, _bedingung(db, t, profil_id))
        if klausel.strip() == "WHERE 0":
            continue
        try:
            cur = con.execute(f"DELETE FROM {t}{klausel}",
                              {"pid": profil_id} if profil_id else {})
            if cur.rowcount:
                geloescht[t] = cur.rowcount
        except Exception as exc:  # pragma: no cover
            logger.warning("Loeschen aus %s fehlgeschlagen: %s", t, exc)
    con.commit()
    return {"status": "geloescht", "bereiche": gewaehlt,
            "profil_id": profil_id, "je_tabelle": geloescht,
            "zeilen_gesamt": sum(geloescht.values()),
            "dateien_geloescht": dateien_weg,
            "dateien_nicht_loeschbar": dateien_fehler,
            "haengende_verweise": vor["haengende_verweise"],
            "hinweis": vor["hinweis"]}


def verwaiste_profilzeilen(db) -> dict:
    """Zeilen mit einer `profile_id`, die es nicht mehr gibt.

    Der zweite Befund des Melders: `delete_profile` raeumte 12 von 29
    profilgebundenen Tabellen ab. Diese Auskunft zeigt, was davon noch
    liegt — und sie taugt zugleich als Pruefung nach dem Loeschen.
    """
    con = db.connect()
    bekannt = [r[0] for r in con.execute(f"SELECT id FROM {_PROFILTABELLE}")]
    gefunden: dict = {}
    for t in tabellen(db):
        if t == _PROFILTABELLE or "profile_id" not in _spalten(db, t):
            continue
        try:
            if bekannt:
                platz = ",".join("?" * len(bekannt))
                n = con.execute(
                    f"SELECT COUNT(*) FROM {t} WHERE profile_id IS NOT NULL "
                    f"AND profile_id != '' AND profile_id NOT IN ({platz})",
                    bekannt).fetchone()[0]
            else:
                n = con.execute(
                    f"SELECT COUNT(*) FROM {t} WHERE profile_id IS NOT NULL "
                    "AND profile_id != ''").fetchone()[0]
        except Exception as exc:  # pragma: no cover
            logger.debug("Verwaiste Zeilen in %s nicht lesbar: %s", t, exc)
            continue
        if n:
            gefunden[t] = n
    return {"tabellen": dict(sorted(gefunden.items(), key=lambda p: -p[1])),
            "zeilen_gesamt": sum(gefunden.values()),
            "bekannte_profile": len(bekannt)}


def haengende_verweise(db, bereiche=None, profil_id: str | None = None) -> dict:
    """Was zeigt nach dem Leeren ins Leere?

    Fuenf Fremdschluessel im Schema laufen ueber eine Bereichsgrenze:
    `applications.job_hash` -> `jobs`, `documents.linked_application_id`
    -> `applications`, `documents.linked_position_id` -> `positions`
    (je zweimal, weil es `documents_new` gibt). Wer also nur den
    Stellen-Bestand leert, laesst in den Bewerbungen einen `job_hash`
    stehen, der auf nichts mehr zeigt.

    Das ist dieselbe Klasse Befund wie die gemeldete: eine Zeile, die
    ihren Bezug verloren hat, sieht unauffaellig aus. Sie wird deshalb
    GENANNT und nicht stillschweigend mitgeloescht — die Zeile gehoert
    zu einem Bereich, den der Mensch gerade NICHT gewaehlt hat, und ihn
    ungefragt anzufassen waere schlimmer als die Warnung.
    """
    gewaehlt = {b for b in (bereiche or BEREICHE) if b in BEREICHE}
    if not gewaehlt:
        return {"verweise": [], "zeilen_gesamt": 0}
    bereich_von = {t: b for b, ts in BEREICHE.items() for t in ts}
    betroffen = {t for b in gewaehlt for t in BEREICHE[b]}
    vorhanden = set(tabellen(db))
    con = db.connect()

    gefunden: list = []
    for t in sorted(vorhanden - betroffen):
        for r in con.execute(f"PRAGMA foreign_key_list({t})"):
            eltern, eigene, deren = r[2], r[3], r[4] or "id"
            if eltern not in betroffen or eltern not in vorhanden:
                continue
            klausel = _bedingung(db, eltern, profil_id)
            try:
                n = con.execute(
                    f"SELECT COUNT(*) FROM {t} WHERE {eigene} IS NOT NULL "
                    f"AND {eigene} IN (SELECT {deren} FROM {eltern}{klausel})",
                    {"pid": profil_id} if profil_id else {}).fetchone()[0]
            except Exception as exc:  # pragma: no cover
                logger.debug("Verweis %s.%s nicht pruefbar: %s", t, eigene, exc)
                continue
            if n:
                gefunden.append({
                    "tabelle": t, "spalte": eigene, "zeigt_auf": eltern,
                    "bereich": bereich_von.get(t, "?"),
                    "zielbereich": bereich_von.get(eltern, "?"),
                    "zeilen": n,
                })
    gefunden.sort(key=lambda e: -e["zeilen"])
    return {"verweise": gefunden,
            "zeilen_gesamt": sum(e["zeilen"] for e in gefunden)}


def verwaiste_bezugszeilen(db) -> dict:
    """Zeilen, deren Elternzeile es nicht mehr gibt.

    Die Ergaenzung zu `verwaiste_profilzeilen` — und die wichtigere
    Haelfte: eine Tabelle ohne `profile_id` kommt dort gar nicht vor.
    Genau daran ist der erste Entwurf dieses Moduls vorbeigelaufen. Er
    liess 43 `job_sources` und 68 `application_jobs` stehen, und der
    Profil-Check meldete trotzdem "keine neuen Waisen".

    **Ein Pruefer, der nur eine von zwei Bezugsarten kennt, gibt
    Entwarnung fuer die andere.**
    """
    con = db.connect()
    vorhanden = set(tabellen(db))
    gefunden: dict = {}
    for t in sorted(vorhanden):
        for eltern in sorted(_alle_eltern(db, t)):
            if eltern not in vorhanden:
                continue
            bezug_spalten = []
            if t in _ZUSATZ_BEZUG and _ZUSATZ_BEZUG[t][0] == eltern:
                bezug_spalten.append(
                    (_ZUSATZ_BEZUG[t][1], _ZUSATZ_BEZUG[t][2]))
            try:
                for r in con.execute(f"PRAGMA foreign_key_list({t})"):
                    if r[2] == eltern:
                        bezug_spalten.append((r[3], r[4] or "id"))
            except Exception as exc:  # pragma: no cover
                logger.debug("Bezug %s nicht lesbar: %s", t, exc)
                continue
            for eigene, deren in bezug_spalten:
                try:
                    n = con.execute(
                        f"SELECT COUNT(*) FROM {t} WHERE {eigene} IS NOT NULL "
                        f"AND {eigene} != '' AND {eigene} NOT IN "
                        f"(SELECT {deren} FROM {eltern} "
                        f"WHERE {deren} IS NOT NULL)").fetchone()[0]
                except Exception as exc:  # pragma: no cover
                    logger.debug("Waisen in %s.%s nicht lesbar: %s",
                                 t, eigene, exc)
                    continue
                if n:
                    gefunden[f"{t}.{eigene}"] = {
                        "tabelle": t, "spalte": eigene,
                        "zeigt_auf": eltern, "zeilen": n}
    return {"bezuege": dict(sorted(
        gefunden.items(), key=lambda p: -p[1]["zeilen"])),
        "zeilen_gesamt": sum(e["zeilen"] for e in gefunden.values())}


def verwaiste_zeilen(db) -> dict:
    """Beide Waisen-Arten in einer Auskunft.

    Taugt als Bericht ueber den Bestand UND als Pruefung nach einem
    Loeschvorgang: wer leert, darf diese Zahl nicht erhoehen.
    """
    profil = verwaiste_profilzeilen(db)
    bezug = verwaiste_bezugszeilen(db)
    return {
        "profilzeilen": profil,
        "bezugszeilen": bezug,
        "zeilen_gesamt": profil["zeilen_gesamt"] + bezug["zeilen_gesamt"],
    }
