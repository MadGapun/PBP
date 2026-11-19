"""Die lokale KI lernt aus dem Bestand (#1396): Bearbeitungsmarker und Rueckkopplung.

Grundfunktion von PBP, keine Sonderloesung: die Marker werden IMMER gefuehrt
(auch bei ausgeschalteter KI, es kostet nichts); gelernt und nachgelernt wird
nur, solange die lokale KI eingeschaltet ist (der bestehende KI-Schalter).

Abgrenzung zu aehnlich benannten Modulen (dieselbe Klasse Verwechslung wie
`schwellen_verteilung`/`score_verteilung`, #892):

* `lernprotokoll`, `lerninsights`, `lernquellen`: das Lernen aus dem VERHALTEN
  des Menschen (Erkenntnisse, Muster). Hier geht es um das Urteil der KI ueber
  einzelne Stellen und dessen Gegenprobe.
* `ki_beispiele` (Auswahl der Lernbeispiele nach Aehnlichkeit) und
  `ki_nachlernen` (der Lauf im Leerlauf) gehoeren zu diesem Baustein.

## Die Marker je Stelle (Spalten von `jobs`)

| Spalte | Bedeutung |
|---|---|
| `entschieden_von` | wer die Stelle zuletzt entschieden hat: `mensch`, `claude`, `ollama`, `regel` (Automatik ohne KI, Systemgrund), `unbekannt` (nicht ableitbar, NICHT geraten); leer = noch keine Entscheidung |
| `claude_gelesen_am` | Zeitpunkt, zu dem Claude Anzeige und Profil gelesen und ein Urteil gespeichert hat |
| `ollama_gesehen_am` / `ollama_urteil` / `ollama_grund` / `ollama_sicherheit` | was die lokale KI zu dieser Stelle gesagt hat (`PASST`, `PASST_NICHT`, `UNSICHER`) und wie klar die Antwort war (`klar`/`schwach`) |
| `ollama_lag_richtig` | 1 = Mensch oder Claude haben genauso entschieden, 0 = anders, leer = (noch) keine Gegenprobe oder `UNSICHER` |
| `ollama_grund_traf` | 1/0, wenn sich der Grund der KI einem Standardgrund zuordnen laesst und mit dem des Menschen verglichen werden kann; sonst leer (nie geraten) |
| `ollama_geprueft_am` | wann die Gegenprobe stattfand (Grundlage des Verlaufs) |
"""
from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timezone

logger = logging.getLogger("bewerbungs_assistent.ki_lernen")

MENSCH = "mensch"
CLAUDE = "claude"
OLLAMA = "ollama"
REGEL = "regel"
UNBEKANNT = "unbekannt"
WERTE = (MENSCH, CLAUDE, OLLAMA, REGEL, UNBEKANNT)

#: Vermerk, den die Auto-Aussortierung der lokalen KI in `dismiss_note` schreibt.
AUTO_NOTIZ = "[Auto-Aussortierung]"

#: Spalte -> Typ. EINE Liste fuer Safety-Net, Bewahren und Test.
SPALTEN = {
    "entschieden_von": "TEXT",
    "claude_gelesen_am": "TEXT",
    "ollama_gesehen_am": "TEXT",
    "ollama_urteil": "TEXT",
    "ollama_grund": "TEXT",
    "ollama_sicherheit": "TEXT",
    "ollama_lag_richtig": "INTEGER",
    "ollama_grund_traf": "INTEGER",
    "ollama_geprueft_am": "TEXT",
}

#: Vermerk, dass die einmalige Migration der Bestaende gelaufen ist (endet auf
#: `_migriert`: eine Vorgabe des Programms, keine Einstellung des Menschen).
MIGRATION_SCHALTER = "ki_marker_migriert"

#: Antworten der lokalen KI.
URTEILE = ("PASST", "PASST_NICHT", "UNSICHER")


def _jetzt() -> str:
    return datetime.now(timezone.utc).isoformat()


# -- Ableitung: EINE Funktion fuer Schreibweg und Migration ---------------

def ableiten(dismissed_by, dismiss_reason, dismiss_note=None) -> str:
    """Wer hat diese Aussortierung entschieden? Gespeichert, nicht geraten.

    Dieselbe Frage beantworten Schreibweg (`Database.dismiss_job`) und die
    Migration der Altbestaende - eine Funktion, kein "dieselbe Logik wie".
    Quelle der Herkunft ist `aussortier_protokoll.herkunft` (gespeichert,
    sonst das `auto:`-Praefix, sonst `unbekannt`).
    """
    from .ablehnungsgruende import (
        SYSTEM_GRUENDE, gruende_aus_wert, ist_urteil)
    from .aussortier_protokoll import herkunft

    wer = herkunft({"dismissed_by": dismissed_by, "dismiss_reason": dismiss_reason})
    gruende = gruende_aus_wert(dismiss_reason)
    if gruende == ["bewerbung_erstellt"]:
        # Der Mensch hat sich beworben: das ist sein Ja zu dieser Stelle (das
        # Programm sortiert die Stelle danach nur aus der Liste).
        return MENSCH
    if wer == "claude":
        return CLAUDE
    if wer == "automatik":
        notiz = str(dismiss_note or "").lstrip()
        if notiz.startswith(AUTO_NOTIZ) or "profil_match_negativ" in gruende:
            return OLLAMA
        return REGEL
    if wer == "ich":
        if any(g not in SYSTEM_GRUENDE and ist_urteil(g) for g in gruende):
            return MENSCH
        return REGEL  # veraltet, Dublette, Blacklist: keine Passungsentscheidung
    return UNBEKANNT


def klasse_aus_urteil(urteil) -> str | None:
    """Das gespeicherte Urteil von Claude als Klasse der Entscheidung."""
    wert = str(urteil or "").strip().upper()
    return {"EMPFOHLEN": "passt", "BEDINGT": "bedingt",
            "NICHT_EMPFOHLEN": "passt_nicht"}.get(wert)


def entscheidungsklasse(zeile) -> str | None:
    """`passt`, `passt_nicht`, `bedingt` oder None (keine belastbare Entscheidung).

    Nur Entscheidungen von Mensch und Claude zaehlen; die der KI und der
    Regeln sind kein Beleg (#1239, #1395). Eine Frage, eine Funktion: Beispiele,
    Gegenprobe und Trefferquote fragen alle hier.
    """
    from .ablehnungsgruende import SYSTEM_GRUENDE, gruende_aus_wert, ist_urteil

    von = zeile["entschieden_von"]
    if von not in (MENSCH, CLAUDE):
        return None
    gruende = gruende_aus_wert(zeile["dismiss_reason"])
    if not zeile["is_active"]:
        if "bewerbung_erstellt" in gruende:
            return "passt"
        if any(g not in SYSTEM_GRUENDE and ist_urteil(g) for g in gruende):
            return "passt_nicht"
        # Claude hat nach dem Lesen anders geurteilt als die Automatik: sein
        # gespeichertes Urteil gilt auch an einer (noch) aussortierten Stelle.
        return klasse_aus_urteil(zeile["analyse_urteil"]) if von == CLAUDE else None
    if von == MENSCH and zeile["zurueckgeholt_am"]:
        return "passt"
    if von == CLAUDE:
        return klasse_aus_urteil(zeile["analyse_urteil"])
    return None


def vergleich(ollama_urteil, klasse) -> int | None:
    """1 = die KI lag richtig, 0 = falsch, None = keine Aussage moeglich.

    `UNSICHER` ist keine Behauptung und zaehlt weder als richtig noch als falsch.
    """
    u = str(ollama_urteil or "").upper()
    if u not in ("PASST", "PASST_NICHT") or not klasse:
        return None
    if klasse == "passt_nicht":
        return 1 if u == "PASST_NICHT" else 0
    return 1 if u == "PASST" else 0  # passt und bedingt


# -- Grund der KI einem Standardgrund zuordnen (nie raten) ----------------

_GRUND_WOERTER = {
    "zu_junior": ("junior", "werkstudent", "werkstudentin", "berufseinsteiger",
                  "einsteiger", "praktikum", "praktikant", "trainee", "azubi",
                  "ausbildung"),
    "zu_senior": ("ueberqualifiziert", "überqualifiziert"),
    "falsche_branche": ("branche",),
    "falsches_fachgebiet": ("fachgebiet", "fachlich", "skills", "kenntnisse",
                            "kompetenzen", "taetigkeit", "tätigkeit"),
    "zu_weit_entfernt": ("entfernung", "km", "standort", "pendeln", "pendelweg"),
    "gehalt_zu_niedrig": ("gehalt", "verguetung", "vergütung"),
    "zeitarbeit": ("zeitarbeit", "arbeitnehmerueberlassung",
                   "arbeitnehmerüberlassung", "personaldienstleister"),
    "befristet": ("befristet", "befristung"),
    "unpassendes_arbeitsmodell": ("homeoffice", "remote", "teilzeit", "schicht"),
}


def grund_schluessel(text) -> set:
    """Die Standardgruende, die zum freien Text der KI passen (leer = nicht zuzuordnen)."""
    woerter = set(re.findall(r"[a-zäöüß]+", str(text or "").lower()))
    return {k for k, liste in _GRUND_WOERTER.items() if woerter & set(liste)}


def grund_traf(ollama_grund, gruende_des_menschen) -> int | None:
    """1/0, wenn der Grund der KI einem Standardgrund zuzuordnen ist, sonst None."""
    schluessel = grund_schluessel(ollama_grund)
    gruende = {str(g).lower() for g in (gruende_des_menschen or [])}
    if not schluessel or not gruende:
        return None
    return 1 if schluessel & gruende else 0


# -- Schreibwege ----------------------------------------------------------

def _spalten_nachziehen(conn) -> None:
    vorhanden = {r[1] for r in conn.execute("PRAGMA table_info(jobs)")}
    for name, typ in SPALTEN.items():
        if name not in vorhanden:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {name} {typ}")
            logger.info("Safety-Net: jobs.%s nachgezogen (#1396)", name)
    conn.commit()


def migrieren(db) -> dict:
    """Spalten nachziehen und die Marker der vorhandenen Stellen setzen (einmalig).

    Additiv, ohne Schema-Bump. Gesetzt wird nur, was sich aus den Daten
    ableiten laesst; alles andere bleibt `unbekannt` bzw. leer. Idempotent: das
    Ergebnis haengt nur vom Zustand ab, nicht davon, wie oft es laeuft; der
    Schalter spart den Durchgang bei jedem weiteren Start.
    """
    conn = db.connect()
    _spalten_nachziehen(conn)
    if db.get_setting(MIGRATION_SCHALTER, False):
        return {"status": "schon_erledigt"}
    zaehler = {"entschieden": 0, "claude_gelesen": 0, "ollama": 0}
    # 1. Aussortierte Stellen: Herkunft und - bei der KI - ihr Urteil aus der Notiz.
    zeilen = conn.execute(
        "SELECT hash, dismissed_by, dismiss_reason, dismiss_note, dismissed_at "
        "FROM jobs WHERE is_active=0 AND entschieden_von IS NULL").fetchall()
    stapel_von, stapel_ki = [], []
    for z in zeilen:
        von = ableiten(z["dismissed_by"], z["dismiss_reason"], z["dismiss_note"])
        stapel_von.append((von, z["hash"]))
        if von == OLLAMA and str(z["dismiss_note"] or "").lstrip().startswith(AUTO_NOTIZ):
            grund = str(z["dismiss_note"]).lstrip()[len(AUTO_NOTIZ):].strip()
            stapel_ki.append((z["dismissed_at"], grund[:300], z["hash"]))
    conn.executemany(
        "UPDATE jobs SET entschieden_von=? WHERE hash=? AND entschieden_von IS NULL",
        stapel_von)
    # Das Urteil der KI ist hier belegt (ihr Vermerk steht an der Stelle); wie
    # klar die Antwort war und ob sie stimmte, ist es nicht -> leer lassen.
    conn.executemany(
        "UPDATE jobs SET ollama_urteil='PASST_NICHT', ollama_gesehen_am=?, "
        "ollama_grund=? WHERE hash=? AND ollama_urteil IS NULL", stapel_ki)
    zaehler["entschieden"] = len(stapel_von)
    zaehler["ollama"] = len(stapel_ki)
    # 2. Gelesene Urteile von Claude (auch an aussortierten Stellen).
    zaehler["claude_gelesen"] = conn.execute(
        "UPDATE jobs SET claude_gelesen_am=analyse_am "
        "WHERE analyse_urteil IS NOT NULL AND claude_gelesen_am IS NULL"
    ).rowcount
    # 3. Aktive Stellen mit Claude-Urteil (die Entscheidung ist sein Urteil).
    conn.execute(
        "UPDATE jobs SET entschieden_von='claude' WHERE is_active=1 "
        "AND entschieden_von IS NULL AND analyse_urteil IN "
        "('EMPFOHLEN','BEDINGT','NICHT_EMPFOHLEN')")
    # 4. Vom Menschen zurueckgeholt = sein Ja.
    conn.execute(
        "UPDATE jobs SET entschieden_von='mensch' WHERE is_active=1 "
        "AND zurueckgeholt_am IS NOT NULL AND (entschieden_von IS NULL "
        "OR entschieden_von IN ('ollama','regel','unbekannt'))")
    conn.commit()
    db.set_setting(MIGRATION_SCHALTER, True)
    logger.info("KI-Marker (#1396) gesetzt: %s", zaehler)
    zaehler["status"] = "migriert"
    return zaehler


def ollama_gesehen(conn, stored_hash: str, urteil: str, grund: str = "",
                   sicherheit: str = "klar") -> None:
    """Haelt fest, was die lokale KI zu dieser Stelle gesagt hat (nur Marker)."""
    wert = str(urteil or "").upper()
    if wert not in URTEILE:
        return
    conn.execute(
        "UPDATE jobs SET ollama_gesehen_am=?, ollama_urteil=?, ollama_grund=?, "
        "ollama_sicherheit=?, ollama_lag_richtig=NULL, ollama_grund_traf=NULL, "
        "ollama_geprueft_am=NULL WHERE hash=?",
        (_jetzt(), wert, str(grund or "")[:300],
         sicherheit if sicherheit in ("klar", "schwach") else None, stored_hash))
    conn.commit()


def merke_urteil(db, job_hash: str, urteil: str, grund: str = "",
                 sicherheit: str = "klar") -> bool:
    """`ollama_gesehen` ueber die oeffentliche Kennung der Stelle; schluckt nie den Lauf."""
    try:
        voll = db.resolve_job_hash(job_hash)
        if not voll:
            return False
        ollama_gesehen(db.connect(), voll, urteil, grund, sicherheit)
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("KI-Urteil nicht vermerkt (#1396): %s", exc)
        return False


def nach_entscheidung(conn, stored_hash: str) -> int | None:
    """Gegenprobe: stellt fest, ob die KI mit ihrem Urteil richtig lag.

    Aufgerufen von jedem Weg, auf dem Mensch oder Claude eine Stelle
    entscheiden (`dismiss_job`, `restore_job`, `set_job_analysis`). Hat die KI
    die Stelle nie gesehen oder fehlt eine belastbare Entscheidung, passiert
    nichts. Eine Abweichung wird zum Gegenbeispiel (`ollama_lag_richtig=0`).
    """
    z = conn.execute(
        "SELECT entschieden_von, is_active, dismiss_reason, zurueckgeholt_am, "
        "analyse_urteil, ollama_urteil, ollama_grund FROM jobs WHERE hash=?",
        (stored_hash,)).fetchone()
    if not z or not z["ollama_urteil"]:
        return None
    klasse = entscheidungsklasse(z)
    lag = vergleich(z["ollama_urteil"], klasse)
    if lag is None:
        return None
    from .ablehnungsgruende import gruende_aus_wert
    traf = None
    if klasse == "passt_nicht" and z["ollama_urteil"] == "PASST_NICHT":
        traf = grund_traf(z["ollama_grund"], gruende_aus_wert(z["dismiss_reason"]))
    conn.execute(
        "UPDATE jobs SET ollama_lag_richtig=?, ollama_grund_traf=?, "
        "ollama_geprueft_am=? WHERE hash=?", (lag, traf, _jetzt(), stored_hash))
    conn.commit()
    return lag


# -- Trefferquote und Lernstand --------------------------------------------

#: Ab so vielen Gegenproben nennt PBP eine Quote; darunter steht "noch zu wenig".
MIN_BASIS = 5


def _woche(zeitpunkt) -> str:
    try:
        d = datetime.fromisoformat(str(zeitpunkt))
    except (TypeError, ValueError):
        return ""
    jahr, woche, _ = d.isocalendar()
    return f"{jahr}-W{woche:02d}"


def lernstand(db, min_basis: int = MIN_BASIS, abweichungen: int = 5) -> dict:
    """Wie oft lag die lokale KI richtig? Ergebnis und Grund getrennt, mit Verlauf.

    Gezaehlt werden nur Stellen, die die KI gesehen hat UND zu denen Mensch oder
    Claude entschieden haben (`ollama_lag_richtig` nicht leer). `UNSICHER` ist
    keine Behauptung; eine Stelle ohne Gegenprobe zaehlt als "offen", nie als
    richtig (L7: Unbekannt ist ein eigener Zustand).
    """
    from collections import Counter
    from .ablehnungsgruende import gruende_aus_wert

    conn = db.connect()
    pid = db.get_active_profile_id()
    zeilen = conn.execute(
        "SELECT hash, title, ollama_urteil, ollama_grund, ollama_lag_richtig, "
        "ollama_grund_traf, ollama_geprueft_am, ollama_gesehen_am, entschieden_von, "
        "is_active, dismiss_reason, zurueckgeholt_am, analyse_urteil, "
        "analyse_begruendung FROM jobs WHERE (profile_id=? OR profile_id IS NULL) "
        "AND ollama_urteil IS NOT NULL", (pid,)).fetchall()
    gesehen = len(zeilen)
    unsicher = sum(1 for z in zeilen if z["ollama_urteil"] == "UNSICHER")
    bewertet = [z for z in zeilen if z["ollama_lag_richtig"] is not None]
    richtig = sum(1 for z in bewertet if z["ollama_lag_richtig"] == 1)
    falsch = len(bewertet) - richtig
    offen = gesehen - len(bewertet) - unsicher
    genug = len(bewertet) >= min_basis
    quote = round(100 * richtig / len(bewertet), 1) if genug else None
    grund_b = [z for z in zeilen if z["ollama_grund_traf"] is not None]
    grund_r = sum(1 for z in grund_b if z["ollama_grund_traf"] == 1)
    # Verlauf: je Woche der Gegenprobe
    woche_n: Counter = Counter()
    woche_r: Counter = Counter()
    for z in bewertet:
        w = _woche(z["ollama_geprueft_am"])
        if w:
            woche_n[w] += 1
            woche_r[w] += z["ollama_lag_richtig"] == 1
    verlauf = [{"woche": w, "bewertet": woche_n[w], "richtig": woche_r[w],
                "quote_prozent": round(100 * woche_r[w] / woche_n[w], 1)}
               for w in sorted(woche_n)[-8:]]
    # Fehlerbilder
    bilder: Counter = Counter()
    gruende_je_bild: dict = {}
    liste = []
    for z in sorted((x for x in bewertet if x["ollama_lag_richtig"] == 0),
                    key=lambda x: str(x["ollama_geprueft_am"] or ""), reverse=True):
        klasse = entscheidungsklasse(z) or "unbekannt"
        bild = (z["ollama_urteil"], klasse)
        bilder[bild] += 1
        for g in gruende_aus_wert(z["dismiss_reason"]):
            gruende_je_bild.setdefault(bild, Counter())[g] += 1
        if len(liste) < abweichungen:
            liste.append({
                "titel": z["title"], "ki_sagte": z["ollama_urteil"],
                "ki_grund": z["ollama_grund"] or "",
                "richtig_war": klasse, "entschieden_von": z["entschieden_von"],
                "begruendung": (z["analyse_begruendung"] or "")[:200]
                if z["entschieden_von"] == CLAUDE else "",
                "grund_des_menschen": ", ".join(gruende_aus_wert(z["dismiss_reason"])),
            })
    fehlerbilder = []
    for (ki, klasse), n in bilder.most_common(3):
        g = gruende_je_bild.get((ki, klasse))
        fehlerbilder.append({
            "ki_sagte": ki, "richtig_war": klasse, "anzahl": n,
            "haeufigster_grund": g.most_common(1)[0][0] if g else ""})
    return {
        "gesehen": gesehen, "bewertet": len(bewertet), "richtig": richtig,
        "falsch": falsch, "unsicher": unsicher, "offen": offen,
        "trefferquote_prozent": quote, "datenbasis_ausreichend": genug,
        "mindestens": min_basis,
        "grund": {"bewertet": len(grund_b), "traf": grund_r,
                  "quote_prozent": (round(100 * grund_r / len(grund_b), 1)
                                    if len(grund_b) >= min_basis else None)},
        "verlauf": verlauf, "fehlerbilder": fehlerbilder,
        "groesste_abweichungen": liste,
        "satz": _satz(gesehen, len(bewertet), richtig, quote, genug, min_basis, falsch),
    }


def _satz(gesehen, bewertet, richtig, quote, genug, min_basis, falsch) -> str:
    """Ein Satz fuer den Menschen: was die Zahl bedeutet und was er tun kann."""
    if not gesehen:
        return ("Die lokale KI hat noch keine Stelle beurteilt. Sobald sie das "
                "tut, vergleicht PBP ihre Bewertung mit deinen Entscheidungen.")
    if not genug:
        return (f"Die lokale KI hat {gesehen} Stellen beurteilt; verglichen mit "
                f"deiner Entscheidung sind es erst {bewertet} (ab {min_basis} "
                "nennt PBP eine Quote). Entscheidest du über Stellen, lernt sie dazu.")
    teil = (f"Bei {bewertet} Stellen, über die du oder Claude entschieden habt, "
            f"lag die lokale KI {richtig}-mal richtig ({quote} %).")
    if falsch:
        return (teil + f" {falsch} Abweichungen zeigt PBP ihr als Gegenbeispiele: "
                "Holst du eine zu Unrecht aussortierte Stelle zurück, lernt sie daraus.")
    return teil + " Es gibt keine Abweichungen."
