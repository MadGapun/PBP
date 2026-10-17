#!/usr/bin/env python
"""Messprobe des API-Wegs (#1236, Stufe 3): wie oft liegt die Anthropic-API bei `match_job_to_skills` richtig?

Die Probe stellt jeder Stelle einer Stichprobe dieselbe Frage wie `stellen_auto_aussortieren` (derselbe Weg im Code:
`LLMService.run`, derselbe Prompt-Bauer, dieselbe Schwaerzung der Firmennamen) und vergleicht die Antwort mit dem, was der
Mensch selbst entschieden hat.

    Trockenlauf (Standard):  python scripts/api_probe.py --quelle <pbp.db oder Ordner>
    Echtlauf:                python scripts/api_probe.py --quelle <...> --senden --budget-usd 0.50

## Was sie nie tut

* **Nichts senden ohne `--senden`.** Der Trockenlauf zeigt den ersten Prompt genau so, wie er abgeschickt wuerde, dazu die
  geschaetzten Tokens und Kosten, und sendet nichts. Kein Netz, kein Schluessel noetig.
* **Nie an der echten Datenbank arbeiten.** Die Probe legt eine KOPIE in einem Wegwerf-Ordner an (SQLite-Sicherung aus einer
  nur lesenden Verbindung), setzt `BA_DATA_DIR` dorthin und prueft danach, dass der Pfad im Wegwerf-Ordner liegt (die
  QA-Isolation aus CLAUDE.md). Das Original wird nur gelesen.
* **Nie ueber das Budget.** Der Echtlauf verlangt `--budget-usd` (keine Vorgabe); die Grenze gilt fuer die Probe allein (die
  Zaehler der Kopie werden vorher geleert) und ist dieselbe harte Grenze wie im Betrieb: vor jedem Aufruf der schlimmste Fall.
* **Den Schluessel nur aus `PBP_ANTHROPIC_API_KEY`.** Er steht in keiner Ausgabe, keinem Bericht und keiner Datei.

## Die Referenz: nur Urteile des Menschen

* *beworben* -- Stellen, zu denen eine Bewerbung existiert (`bewerbung_erstellt` ist das Gegenteil einer Ablehnung, #1234).
  Erwartet wird `PASST`.
* *selbst aussortiert* -- vom Menschen (nicht von der Automatik: `dismissed_by`, Praefix `auto:`) aus einem Grund, der etwas
  ueber die ART der Stelle sagt (`UEBERTRAGBARE_GRUENDE`). Entfernung, Gehalt und Firmenwahl sagt der Anzeigentext nicht;
  Systemgruende, Dubletten und "sonstiges" sind kein Urteil. Erwartet wird `PASST_NICHT`.

Die Stichprobe hat je Klasse gleich viele Stellen, ist ueber `--seed` wiederholbar und wechselt zwischen den Klassen ab, damit ein
Abbruch an der Budgetgrenze eine ausgewogene Teilmenge hinterlaesst. Die geprueften Stellen stehen nie im Beispielblock des
eigenen Prompts.

## Der Bericht

Uebereinstimmung mit dem Menschen, je Stelle die Fehler mit Kurzbegruendung (zu Unrecht aussortiert ist der teure Fehler),
Tokens und Kosten aus den Angaben der API; laeuft Ollama und ist `--ollama` gesetzt, dieselbe Auswertung daneben. Der Bericht
nennt Titel, keine Firmen; vor dem Einfuegen in ein Issue trotzdem `issue_text_pruefen`.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import shutil
import sqlite3
import sys
import tempfile
from collections import Counter
from pathlib import Path

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "src"))

MIN_BESCHREIBUNG = 50  # wie im Betrieb (#756): ohne Anzeigentext kein Urteil
MIN_JE_KLASSE = 5
STANDARD_ANZAHL = 40
MAX_ANZAHL = 200
STANDARD_SEED = 1236
AUFGABE = "match_job_to_skills"
#: Fehler, die nur diese Stelle betreffen: die Probe macht mit der naechsten weiter. Alles andere haelt den Lauf an.
WEITER_BEI = frozenset({"antwort_leer", "antwort_unlesbar", "antwort_abgelehnt", "eingabe_zu_gross"})


class ProbeFehler(Exception):
    """Ein Grund, die Probe nicht (weiter) zu fahren. `code` ist der Exit-Code."""

    def __init__(self, text: str, code: int = 2):
        super().__init__(text)
        self.text = text
        self.code = code


# ── Die Kopie ────────────────────────────────────────────────────────────────────────────────────────

def kopie_anlegen(quelle: Path, ziel_ordner: Path) -> Path:
    """Eine Kopie der Datenbank im Wegwerf-Ordner. Das Original wird nur gelesen (SQLite-Sicherung aus `mode=ro`)."""
    quelle = Path(quelle)
    if quelle.is_dir():
        quelle = quelle / "pbp.db"
    if not quelle.is_file():
        raise ProbeFehler(f"Keine Datenbank gefunden: {quelle}")
    ziel = Path(ziel_ordner) / "pbp.db"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    # Eine WAL-Datenbank lesend zu oeffnen legt `-wal` und `-shm` neben ihr an. Laeuft PBP gerade, gibt es sie schon und gehoeren
    # dem Programm; sonst entstehen sie durch die Probe und werden danach wieder entfernt: das Original bleibt, wie es war.
    nebendateien = [quelle.with_name(quelle.name + s) for s in ("-wal", "-shm")]
    schon_da = {n: n.exists() for n in nebendateien}
    try:
        try:
            # Als URI mit Prozent-Kodierung (`as_uri`): ein Pfad mit "#", "%" oder Umlauten (der Benutzername steckt im Pfad)
            # darf nicht als Teil der URI-Syntax gelesen werden.
            src = sqlite3.connect(f"{quelle.resolve().as_uri()}?mode=ro", uri=True)
        except sqlite3.Error as exc:
            raise ProbeFehler(f"Die Datenbank ließ sich nicht lesend öffnen: {exc}") from None
        try:
            dst = sqlite3.connect(str(ziel))
            try:
                src.backup(dst)
            finally:
                dst.close()
        except sqlite3.Error as exc:
            raise ProbeFehler(f"Die Kopie ließ sich nicht anlegen: {exc}") from None
        finally:
            src.close()
    finally:
        for n, war in schon_da.items():
            if not war:
                try:
                    n.unlink()
                except OSError:
                    pass
    return ziel


def datenbank_oeffnen(ziel: Path, ordner: Path):
    """Die Kopie als Datenbank. `BA_DATA_DIR` zeigt in den Wegwerf-Ordner und der Pfad wird geprueft (QA-Isolation)."""
    os.environ["BA_DATA_DIR"] = str(ordner)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=Path(ziel))
    db.initialize()
    assert str(ordner) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    # Die Kopie darf nie auf Ollama zurueckfallen: ein Rueckfall waere eine Antwort, die nicht von der API stammt.
    db.set_profile_setting("llm_local_state", "off")
    # Verbrauch und Budget der Probe beginnen bei null: sie zaehlt nur ihre eigenen Aufrufe.
    conn = db.connect()
    conn.execute("DELETE FROM settings WHERE key LIKE 'api_verbrauch_%' OR key = 'api_letzter_aufruf'")
    conn.commit()
    return db


# ── Die Referenz ─────────────────────────────────────────────────────────────────────────────────────

def _text_ok(job: dict) -> bool:
    return len((job.get("description") or "").strip()) >= MIN_BESCHREIBUNG


def urteile_lesen(db) -> dict:
    """{'beworben': [...], 'aussortiert': [...], 'ausgeschlossen': {Grund: Anzahl}} -- nur Urteile des Menschen."""
    from bewerbungs_assistent.services.ablehnungsgruende import SYSTEM_GRUENDE
    from bewerbungs_assistent.services.stellen_automatik import UEBERTRAGBARE_GRUENDE, AUTOMATIK_GRUENDE

    aus = Counter()
    beworben, gesehen = [], set()
    for app in db.get_applications(include_archived=True):
        oeffentlich = app.get("job_hash")
        job = db.get_job(oeffentlich) if oeffentlich else None
        if not job or job["hash"] in gesehen:
            continue
        gesehen.add(job["hash"])
        if _text_ok(job):
            beworben.append(job)
        else:
            aus["beworben, aber ohne ausreichenden Anzeigentext"] += 1
    aussortiert = []
    for job in db.get_dismissed_jobs():
        if job["hash"] in gesehen:
            continue
        grund = str(job.get("dismiss_reason") or "").strip().lower()
        if str(job.get("dismissed_by") or "") == "automatik" or grund.startswith("auto:"):
            aus["von der Automatik aussortiert (kein Urteil des Menschen)"] += 1
        elif grund in SYSTEM_GRUENDE:
            aus["Systemgrund (Bewerbung erstellt, Blacklist, veraltet ...)"] += 1
        elif grund in UEBERTRAGBARE_GRUENDE:
            if _text_ok(job):
                aussortiert.append(job)
            else:
                aus["selbst aussortiert, aber ohne ausreichenden Anzeigentext"] += 1
        elif grund in AUTOMATIK_GRUENDE:
            aus["Grund betrifft Entfernung, Gehalt oder Firmenwahl, nicht den Anzeigentext"] += 1
        else:
            aus["Grund sagt nichts über die Passung (sonstiges, Duplikat, Freitext ...)"] += 1
    return {"beworben": beworben, "aussortiert": aussortiert, "ausgeschlossen": dict(aus)}


def stichprobe(urteile: dict, anzahl: int, seed: int) -> list[dict]:
    """Je Klasse gleich viele Stellen, wiederholbar, abwechselnd (beworben, aussortiert, beworben ...)."""
    je_klasse = min(anzahl // 2, len(urteile["beworben"]), len(urteile["aussortiert"]))
    if je_klasse < MIN_JE_KLASSE:
        raise ProbeFehler(
            f"Zu wenig eigene Urteile für eine Messprobe: {len(urteile['beworben'])} beworbene und "
            f"{len(urteile['aussortiert'])} selbst aussortierte Stellen (aus einem Grund, der etwas über die Art der Stelle "
            f"sagt) mit Anzeigentext; gebraucht werden je Klasse mindestens {MIN_JE_KLASSE}.", code=3)
    rnd = random.Random(seed)
    pos = rnd.sample(sorted(urteile["beworben"], key=lambda j: j["hash"]), je_klasse)
    neg = rnd.sample(sorted(urteile["aussortiert"], key=lambda j: j["hash"]), je_klasse)
    plan = []
    for p, n in zip(pos, neg):
        plan.append({"job": p, "klasse": "beworben", "erwartet": "PASST"})
        plan.append({"job": n, "klasse": "aussortiert", "erwartet": "PASST_NICHT"})
    return plan


# ── Die Eingabe: dieselbe wie im Betrieb ─────────────────────────────────────────────────────────────

def beispiele_und_gruende(db, urteile: dict, *, bereinigt: bool) -> tuple[list, list]:
    """(Beispiele, haeufigste Gruende) wie `aussortieren` sie baut; `bereinigt` nimmt nur Urteile des Menschen.

    Im Betrieb kommen die Beispiele aus `get_recent_user_dismissals` (alles ohne Praefix `auto:`) und die Gruende aus
    `gruende_zaehlen` ohne Ausnahme -- beides enthaelt auch Systemgruende wie `bewerbung_erstellt`. Die Probe misst
    standardmaessig genau das; `--bereinigt` zeigt, was ohne diese Gruende herauskaeme.
    """
    from bewerbungs_assistent.services.auto_aussortierung import gruende_top
    if not bereinigt:
        try:
            beispiele = db.get_recent_user_dismissals(limit=10)
        except Exception:  # noqa: BLE001
            beispiele = []
        return beispiele, gruende_top(db)
    neueste = sorted(urteile["aussortiert"], key=lambda j: str(j.get("updated_at") or ""), reverse=True)[:10]
    beispiele = [{"title": j.get("title"), "company": j.get("company"), "dismiss_reason": j.get("dismiss_reason"),
                  "updated_at": j.get("updated_at")} for j in neueste]
    zaehlung = Counter(str(j.get("dismiss_reason") or "") for j in urteile["aussortiert"])
    return beispiele, [{"reason": g, "count": n} for g, n in zaehlung.most_common(3)]


def _gleiche_stelle(beispiel: dict, job: dict) -> bool:
    def norm(x):
        return str(x or "").strip().casefold()
    return norm(beispiel.get("title")) == norm(job.get("title")) and norm(beispiel.get("company")) == norm(job.get("company"))


def nutzlast_bauen(job: dict, kontext: dict, beispiele: list, gruende: list) -> dict:
    """Die Nutzlast fuer `match_job_to_skills` -- wie `aussortieren` sie fuellt, ohne die geprueften Stelle im Beispielblock."""
    return {
        **kontext,
        "job_title": job.get("title") or "",
        "job_company": job.get("company") or "",
        "job_description": (job.get("description") or "")[:1500],
        "dismiss_reasons_top": gruende,
        "recent_dismissals": [b for b in beispiele if not _gleiche_stelle(b, job)],
    }


def anfrage_vorschau(db, nutzlast: dict, modell_id: str | None) -> dict:
    """Prompt und Anfrage-Kopf genau so, wie `LLMService._run_api` sie bauen wuerde."""
    from bewerbungs_assistent.services import api_backend
    from bewerbungs_assistent.services.llm_service import _PROMPT_BUILDERS, TaskKind, _datums_kontext
    modell = api_backend.modell_finden(modell_id) if modell_id else api_backend.vorgabe_modell()
    if modell is None or not modell.preis_bekannt:
        raise ProbeFehler(f"Das Modell „{modell_id}“ steht nicht mit Preis in der Modellliste "
                          + "(" + ", ".join(m.id for m in api_backend.katalog()["modelle"]) + ").")
    sicher = api_backend.nutzlast_fuer_api(AUFGABE, nutzlast)
    prompt = _datums_kontext() + _PROMPT_BUILDERS[TaskKind.MATCH_JOB_TO_SKILLS](sicher)
    aufgabe = api_backend.AUFGABEN[AUFGABE]
    koerper = api_backend.anfrage_koerper(modell, prompt, aufgabe.max_tokens)
    geschaetzt = api_backend.schaetze_tokens(prompt) + api_backend.UMSCHLAG_TOKENS
    return {"modell": modell, "prompt": prompt, "koerper": koerper, "tokens": geschaetzt,
            "max_tokens": aufgabe.max_tokens,
            "schlimmster_fall": api_backend.kosten_mikro(modell, geschaetzt, aufgabe.max_tokens),
            "erwartet": api_backend.kosten_mikro(modell, geschaetzt, 60)}


# ── Auswerten ────────────────────────────────────────────────────────────────────────────────────────

def auswerten(zeilen: list[dict]) -> dict:
    """Aus den Zeilen einer Variante die Zahlen. Nur beantwortete Stellen zaehlen fuer die Uebereinstimmung."""
    beantwortet = [z for z in zeilen if z.get("entscheidung")]
    richtig = [z for z in beantwortet if z["entscheidung"] == z["erwartet"]]
    zu_unrecht = [z for z in beantwortet if z["klasse"] == "beworben" and z["entscheidung"] == "PASST_NICHT"]
    nicht_aussortiert = [z for z in beantwortet if z["klasse"] == "aussortiert" and z["entscheidung"] == "PASST"]
    unsicher = [z for z in beantwortet if z["entscheidung"] == "UNSICHER"]
    return {
        "stellen": len(zeilen), "beantwortet": len(beantwortet), "unbeantwortet": len(zeilen) - len(beantwortet),
        "uebereinstimmung": len(richtig),
        "quote": (len(richtig) / len(beantwortet)) if beantwortet else None,
        "zu_unrecht_aussortiert": zu_unrecht, "nicht_aussortiert": nicht_aussortiert, "unsicher": len(unsicher),
        "tokens_ein": sum(int(z.get("tokens_ein") or 0) for z in zeilen),
        "tokens_aus": sum(int(z.get("tokens_aus") or 0) for z in zeilen),
        "kosten_mikro": sum(int(z.get("kosten_mikro") or 0) for z in zeilen),
    }


def _zahl(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def _prozent(x) -> str:
    return "–" if x is None else f"{round(x * 100)} %"


def block_text(titel: str, zeilen: list[dict], ausgabe_kosten: bool = True) -> list[str]:
    from bewerbungs_assistent.services.api_backend import usd_text
    a = auswerten(zeilen)
    out = [f"── {titel}", f"Übereinstimmung mit deinem Urteil: {a['uebereinstimmung']} von {a['beantwortet']} "
           f"beantworteten Stellen ({_prozent(a['quote'])})"]
    if a["unbeantwortet"]:
        out.append(f"Ohne Antwort: {a['unbeantwortet']} Stellen")
    out.append(f"Zu Unrecht aussortiert (PASST_NICHT, obwohl du dich beworben hast): {len(a['zu_unrecht_aussortiert'])}")
    for z in a["zu_unrecht_aussortiert"]:
        out.append(f"   • {z['titel']} — {z.get('begruendung') or '(ohne Begründung)'}")
    out.append(f"Nicht aussortiert (PASST, obwohl du selbst aussortiert hast): {len(a['nicht_aussortiert'])}")
    for z in a["nicht_aussortiert"]:
        out.append(f"   • {z['titel']} — {z.get('begruendung') or '(ohne Begründung)'} (dein Grund: {z.get('grund') or 'k. A.'})")
    out.append(f"Unsicher (keine Entscheidung): {a['unsicher']}")
    for z in zeilen:
        if z.get("fehler"):
            out.append(f"   ! {z['titel']}: {z['fehler']}")
    if ausgabe_kosten:
        out.append(f"Verbrauch: {_zahl(a['tokens_ein'])} Tokens ein, {_zahl(a['tokens_aus'])} aus, {usd_text(a['kosten_mikro'])}")
    return out


# ── Der Lauf ─────────────────────────────────────────────────────────────────────────────────────────

def _zeile(eintrag: dict, erg) -> dict:
    job = eintrag["job"]
    z = {"hash": job["hash"], "titel": job.get("title") or "", "klasse": eintrag["klasse"],
         "erwartet": eintrag["erwartet"], "grund": job.get("dismiss_reason") if eintrag["klasse"] == "aussortiert" else None,
         "entscheidung": None, "begruendung": None, "fehler": None, "tokens_ein": 0, "tokens_aus": 0, "kosten_mikro": 0}
    if erg is not None and erg.success and isinstance(erg.payload, dict):
        z["entscheidung"] = str(erg.payload.get("decision") or "UNSICHER")
        z["begruendung"] = str(erg.payload.get("reason") or "")[:200]
        m = erg.metrics or {}
        z["tokens_ein"], z["tokens_aus"] = int(m.get("eingabe_tokens") or 0), int(m.get("ausgabe_tokens") or 0)
        z["kosten_mikro"] = int(m.get("kosten_mikro_usd") or 0)
    return z


def api_lauf(db, plan: list[dict], payload_fuer, *, dienst, rueckmeldung=print) -> tuple[list[dict], str | None]:
    """Jede Stelle ueber den echten Betriebsweg (`LLMService.run`). Haelt bei Budget und harten Fehlern an."""
    from bewerbungs_assistent.services.llm_service import Backend, TaskKind
    zeilen, abbruch = [], None
    for nr, eintrag in enumerate(plan, 1):
        erg = dienst.run(TaskKind.MATCH_JOB_TO_SKILLS, payload_fuer(eintrag["job"]))
        zeile = _zeile(eintrag, erg if erg.backend == Backend.API else None)
        zeilen.append(zeile)
        if erg.backend == Backend.API and erg.success:
            rueckmeldung(f"  {nr}/{len(plan)}  {zeile['entscheidung']:<12} (erwartet {zeile['erwartet']})")
            continue
        m = erg.metrics or {}
        code = m.get("api_abgebrochen") or m.get("api_ausgelassen") or "unbekannt"
        text = m.get("api_grund") or erg.fallback_message or "unbekannter Grund"
        zeile["fehler"] = f"{code}: {text}"
        if code in WEITER_BEI:
            rueckmeldung(f"  {nr}/{len(plan)}  ohne Antwort ({code})")
            continue
        abbruch = (f"Abbruch nach {nr - 1} von {len(plan)} Stellen: "
                   + ("das Budget der Probe ist erreicht. " if code == "budget_erreicht" else "")
                   + f"{text}")
        zeilen.pop()  # die Stelle ohne Antwort zaehlt nicht als beantwortet; der Abbruch steht im Bericht
        break
    return zeilen, abbruch


def ollama_lauf(plan: list[dict], payload_fuer, *, dienst, rueckmeldung=print) -> tuple[list[dict], str | None]:
    """Dieselben Stellen ueber die lokale KI (Ollama), mit demselben Prompt-Bauer. Ohne Ollama: kein Lauf, mit Grund."""
    from bewerbungs_assistent.services.llm_service import TaskKind
    status = dienst.get_status(force_refresh=True)
    if not (status.ollama_available and status.available_models):
        return [], "Ollama läuft nicht oder hat kein Modell: kein Vergleich mit der lokalen KI."
    zeilen = []
    for nr, eintrag in enumerate(plan, 1):
        try:
            erg = dienst._run_local(TaskKind.MATCH_JOB_TO_SKILLS, payload_fuer(eintrag["job"]))
        except Exception as exc:  # noqa: BLE001 -- ein Fehler der lokalen KI kippt die Probe nicht
            z = _zeile(eintrag, None)
            z["fehler"] = f"{type(exc).__name__}: {str(exc)[:120]}"
            zeilen.append(z)
            continue
        zeilen.append(_zeile(eintrag, erg))
        rueckmeldung(f"  {nr}/{len(plan)}  {zeilen[-1]['entscheidung']:<12} (erwartet {eintrag['erwartet']}) [Ollama]")
    return zeilen, None


# ── Demo-Datenbank (erfunden) ────────────────────────────────────────────────────────────────────────

def demo_datenbank(ordner: Path) -> Path:
    """Eine erfundene Datenbank mit allen Klassen von Urteilen: zum Ausprobieren und fuer die Tests. Nichts davon ist echt."""
    Path(ordner).mkdir(parents=True, exist_ok=True)
    os.environ["BA_DATA_DIR"] = str(ordner)
    from bewerbungs_assistent.database import Database
    ziel = Path(ordner) / "pbp.db"
    db = Database(db_path=ziel)
    assert str(ordner) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.initialize()
    db.save_profile({"name": "Erika Musterfrau"})
    db.add_position({"company": "Beispiel Maschinenbau GmbH", "title": "Konstruktionsingenieurin",
                     "start_date": "2012-01", "end_date": ""})
    for name in ("Konstruktion", "CAD", "Projektleitung", "Python"):
        db.add_skill({"name": name, "category": "tech"})
    text = "Aufgaben: Konstruktion und Auslegung von Baugruppen. Anforderungen: Studium, mehrjährige Erfahrung. " * 4
    nr = 0

    def stelle(titel, firma="Beispiel AG"):
        nonlocal nr
        nr += 1
        kennung = f"demo{nr:03d}"
        db.save_jobs([{"hash": kennung, "title": f"{titel} {nr}", "company": f"{firma} {nr}",
                       "url": f"https://example.com/demo/{nr}", "source": "manuell", "description": text, "score": 5}])
        return kennung

    for _ in range(12):  # beworben
        k = stelle("Konstrukteur (m/w/d)")
        db.add_application({"title": f"Konstrukteur {k}", "company": "Beispiel AG", "status": "beworben", "job_hash": k})
        db.dismiss_job(k, "bewerbung_erstellt", herkunft="automatik")
    for grund in ("zu_junior", "falsches_fachgebiet", "zu_senior", "falsche_branche", "zeitarbeit", "befristet") * 2:
        k = stelle("Werkstudent Zeichnen")  # selbst aussortiert, Urteil ueber die Art der Stelle
        db.dismiss_job(k, grund)
    for grund in ("zu_weit_entfernt", "gehalt_zu_niedrig", "firma_uninteressant"):
        db.dismiss_job(stelle("Stelle weit weg"), grund)  # selbst, aber nichts ueber den Text
    for grund in ("duplikat", "bereits_beworben", "sonstiges"):
        db.dismiss_job(stelle("Doppelte Stelle"), grund)  # kein Urteil
    for _ in range(3):
        db.dismiss_job(stelle("Automatisch aussortiert"), "profil_match_negativ", herkunft="automatik")
    db.close()
    return ziel


# ── Bericht und Hauptprogramm ────────────────────────────────────────────────────────────────────────

def _fertig(ordner: Path, behalten: bool) -> None:
    if not behalten:
        shutil.rmtree(ordner, ignore_errors=True)


def main(argv=None, *, transport=None, dienst_fabrik=None, ausgabe=print) -> int:
    ap = argparse.ArgumentParser(prog="api_probe.py", description="Messprobe des API-Wegs (#1236). Ohne --senden wird nichts gesendet.")
    ap.add_argument("--quelle", help="die echte Datenbank (pbp.db) oder ihr Ordner; sie wird nur gelesen und KOPIERT")
    ap.add_argument("--demo", action="store_true", help="eine erfundene Datenbank statt der echten (nur Trockenlauf)")
    ap.add_argument("--anzahl", type=int, default=STANDARD_ANZAHL, help=f"Stellen insgesamt, je Klasse die Hälfte (höchstens {MAX_ANZAHL})")
    ap.add_argument("--seed", type=int, default=STANDARD_SEED)
    ap.add_argument("--modell", default=None, help="Modell-ID aus der Liste (Vorgabe: das günstigste)")
    ap.add_argument("--bereinigt", action="store_true", help="Beispiele und Gründe nur aus Urteilen des Menschen (statt wie im Betrieb)")
    ap.add_argument("--firmennamen", action="store_true", help="zusätzlich eine Variante MIT Firmennamen in den Beispielen (kostet doppelt)")
    ap.add_argument("--ollama", action="store_true", help="dieselben Stellen auch durch die lokale KI laufen lassen (Ollama muss laufen); OHNE --senden misst die Probe NUR die lokale KI: kein Schlüssel, kein Budget, nichts geht ins Netz")
    ap.add_argument("--senden", action="store_true", help="WIRKLICH senden (Anthropic-API, kostet Geld; braucht --budget-usd)")
    ap.add_argument("--budget-usd", dest="budget_usd", default=None, help="harte Obergrenze der Probe in US-Dollar (Pflicht mit --senden)")
    ap.add_argument("--ausgabe", help="den Bericht zusätzlich als JSON in diese Datei schreiben")
    ap.add_argument("--behalten", action="store_true", help="den Wegwerf-Ordner mit der Kopie nicht löschen")
    args = ap.parse_args(argv)

    ordner = Path(tempfile.mkdtemp(prefix="pbp-api-probe-"))
    daten_ordner_vorher = os.environ.get("BA_DATA_DIR")
    try:
        return _lauf(args, ordner, transport, dienst_fabrik, ausgabe)
    except ProbeFehler as exc:
        ausgabe(f"Abgebrochen: {exc.text}")
        return exc.code
    finally:
        # Ein Aufruf aus einem anderen Programm (die Tests) bekommt seinen Datenordner zurueck, nicht den geloeschten.
        if daten_ordner_vorher is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = daten_ordner_vorher
        _fertig(ordner, args.behalten)


def _lauf(args, ordner: Path, transport, dienst_fabrik, ausgabe) -> int:
    if not args.quelle and not args.demo:
        raise ProbeFehler("Welche Datenbank? --quelle <pbp.db oder Ordner> (sie wird nur gelesen und kopiert) oder --demo.")
    if not 2 <= args.anzahl <= MAX_ANZAHL:
        raise ProbeFehler(f"--anzahl muss zwischen 2 und {MAX_ANZAHL} liegen.")
    if args.senden and args.demo:
        raise ProbeFehler("Die Demo-Datenbank ist erfunden: senden hätte keinen Sinn und kostet Geld.")
    if args.senden and args.budget_usd is None:
        raise ProbeFehler("--senden verlangt --budget-usd: eine Probe ohne Obergrenze gibt es nicht.")

    os.environ["BA_DATA_DIR"] = str(ordner)
    from bewerbungs_assistent.services import api_backend

    if args.demo:
        quelle = demo_datenbank(ordner / "demo-quelle")
        os.environ["BA_DATA_DIR"] = str(ordner)
    else:
        quelle = Path(args.quelle)
    ziel = kopie_anlegen(quelle, ordner / "kopie")
    db = datenbank_oeffnen(ziel, ordner / "kopie")
    try:
        return _auswerten_und_senden(args, db, transport, dienst_fabrik, ausgabe, api_backend)
    finally:
        db.close()


def _auswerten_und_senden(args, db, transport, dienst_fabrik, ausgabe, api_backend) -> int:
    from bewerbungs_assistent.services.auto_aussortierung import profil_kontext
    from bewerbungs_assistent.services.llm_service import LLMService

    urteile = urteile_lesen(db)
    plan = stichprobe(urteile, args.anzahl, args.seed)
    kontext = profil_kontext(db.get_profile() or {})
    beispiele, gruende = beispiele_und_gruende(db, urteile, bereinigt=args.bereinigt)
    from bewerbungs_assistent.services.stellen_automatik import UEBERTRAGBARE_GRUENDE
    ohne_aussage = [b for b in beispiele if str(b.get("dismiss_reason") or "").strip().lower() not in UEBERTRAGBARE_GRUENDE]

    def payload_fuer(job):
        return nutzlast_bauen(job, kontext, beispiele, gruende)

    if args.ollama and not args.senden:
        return _nur_lokal(args, db, dienst_fabrik, ausgabe, urteile, plan, beispiele, gruende, ohne_aussage, payload_fuer)

    erstes = anfrage_vorschau(db, payload_fuer(plan[0]["job"]), args.modell)
    varianten = [("Firmennamen der Beispiele geschwärzt (wie im Betrieb)", False)]
    if args.firmennamen:
        varianten.append(("Firmennamen der Beispiele im Klartext (nur zum Vergleich)", True))
    aufrufe = len(plan) * len(varianten)
    modell = erstes["modell"]

    ausgabe("API-Messprobe (#1236)" + ("" if args.senden else " — TROCKENLAUF: es wird nichts gesendet"))
    _referenz_ausgeben(args, ausgabe, urteile, plan, beispiele, gruende, ohne_aussage)
    f = api_backend.feldliste(AUFGABE)
    ausgabe("Gesendet wird je Stelle: " + "; ".join(f["gesendet"]) + ". Nicht gesendet: " + "; ".join(f["nicht_gesendet"]) + ".")
    ausgabe(f"Modell: {modell.name} ({modell.id}), Antwort höchstens {erstes['max_tokens']} Tokens.")
    ausgabe("")
    ausgabe("Der erste Prompt, genau so wie er abgeschickt würde (Nachricht an das Modell):")
    ausgabe("-" * 72)
    ausgabe(json.loads(erstes["koerper"].decode("utf-8"))["messages"][0]["content"])
    ausgabe("-" * 72)
    kopf = json.loads(erstes["koerper"].decode("utf-8"))
    ausgabe("Der Rest der Anfrage: POST " + api_backend.ADRESSE + "; " + ", ".join(
        f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in kopf.items() if k != "messages")
        + "; Kopfzeilen x-api-key (aus der Umgebung, hier nie gezeigt), anthropic-version, content-type.")
    ausgabe("")
    ausgabe(f"Geschätzt: etwa {erstes['tokens']} Tokens je Anfrage. Kosten je Anfrage im ungünstigsten Fall "
            f"{api_backend.usd_text(erstes['schlimmster_fall'])}, erwartet etwa {api_backend.usd_text(erstes['erwartet'])}. "
            f"{aufrufe} Anfragen: höchstens {api_backend.usd_text(erstes['schlimmster_fall'] * aufrufe)}, "
            f"erwartet etwa {api_backend.usd_text(erstes['erwartet'] * aufrufe)}.")
    if not args.senden:
        ausgabe("")
        ausgabe("Es wurde nichts gesendet. Echtlauf: dasselbe mit --senden --budget-usd <Betrag> "
                f"(und {api_backend.ENV_SCHLUESSEL} in der Umgebung).")
        if args.ausgabe:
            _json_schreiben(Path(args.ausgabe), {"modus": "trockenlauf", "stellen": len(plan), "seed": args.seed,
                                                 "ausgeschlossen": urteile["ausgeschlossen"],
                                                 "geschaetzt": {"tokens": erstes["tokens"], "schlimmster_fall_mikro": erstes["schlimmster_fall"] * aufrufe}})
        return 0

    # ── Echtlauf ──
    if not api_backend.schluessel_vorhanden():
        raise ProbeFehler(f"Kein Schlüssel: {api_backend.ENV_SCHLUESSEL} fehlt in der Umgebung.")
    erg = api_backend.einstellungen_setzen(db, aufgaben=[AUFGABE], budget_usd=args.budget_usd,
                                           modelle={AUFGABE: modell.id}, bestaetigt=True)
    if erg.get("status") != "gespeichert":
        raise ProbeFehler(erg.get("text") or "Die Einstellungen der Probe ließen sich nicht setzen.")
    if api_backend.budget_lesen(db) is None:
        raise ProbeFehler("Das Budget der Probe muss größer als null sein: mit null darf PBP nichts ausgeben.")
    if transport is not None:
        api_backend.transport_setzen(transport)
    svc = (dienst_fabrik or LLMService)(db)
    ergebnis = {"modell": modell.id, "seed": args.seed, "budget_mikro": api_backend.budget_lesen(db), "varianten": []}
    abbruch = None
    ausgabe("")
    for name, mit_namen in varianten:
        if abbruch:
            break
        ausgabe(f"Variante: {name}")
        if mit_namen:
            zeilen, abbruch = api_lauf_mit_namen(db, plan, payload_fuer, svc, ausgabe)
        else:
            zeilen, abbruch = api_lauf(db, plan, payload_fuer, dienst=svc, rueckmeldung=ausgabe)
        ergebnis["varianten"].append({"name": name, "zeilen": zeilen, "auswertung": _ohne_listen(auswerten(zeilen))})
        ausgabe("")
        for zeile in block_text(f"API, {name}", zeilen):
            ausgabe(zeile)
        ausgabe("")
    if abbruch:
        ausgabe(abbruch)
    if args.ollama:
        ausgabe("")
        ausgabe("Vergleich: dieselben Stellen durch die lokale KI (Ollama)")
        zeilen, grund = ollama_lauf(plan, payload_fuer, dienst=svc, rueckmeldung=ausgabe)
        if grund:
            ausgabe(grund)
        else:
            ergebnis["ollama"] = {"zeilen": zeilen, "auswertung": _ohne_listen(auswerten(zeilen))}
            ausgabe("")
            for zeile in block_text("Lokale KI (Ollama)", zeilen, ausgabe_kosten=False):
                ausgabe(zeile)
    z = api_backend.zaehler_lesen(db)
    ausgabe("")
    ausgabe(f"Gesamt über die API: {z['aufrufe']} Aufrufe, {_zahl(z['eingabe_tokens'])} Tokens ein, {_zahl(z['ausgabe_tokens'])} aus, "
            f"{api_backend.usd_text(z['mikro_usd'])} von {api_backend.usd_text(ergebnis['budget_mikro'])} Budget.")
    if args.ausgabe:
        _json_schreiben(Path(args.ausgabe), {**ergebnis, "abbruch": abbruch, "verbrauch_mikro": z["mikro_usd"]})
    return 0 if not abbruch else 4


def _referenz_ausgeben(args, ausgabe, urteile, plan, beispiele, gruende, ohne_aussage) -> None:
    """Woher die Referenz kommt, wie gross die Stichprobe ist und was im Beispielblock steht: fuer beide Wege gleich."""
    ausgabe(f"Datenbank: eine Kopie im Wegwerf-Ordner (das Original wurde nur gelesen).")
    ausgabe("")
    ausgabe(f"Referenz: nur deine eigenen Urteile. Gefunden: {len(urteile['beworben'])} beworbene Stellen, "
            f"{len(urteile['aussortiert'])} selbst aussortierte mit Grund über die Art der Stelle (je mit Anzeigentext).")
    for grund, n in sorted(urteile["ausgeschlossen"].items()):
        ausgabe(f"   nicht gezählt: {n} × {grund}")
    je = len(plan) // 2
    ausgabe(f"Stichprobe: {len(plan)} Stellen ({je} beworben, {je} selbst aussortiert), Seed {args.seed}.")
    ausgabe(f"Beispielblock: {len(beispiele)} Beispiele und {len(gruende)} häufigste Gründe "
            + ("(nur Urteile des Menschen)." if args.bereinigt else "(wie im Betrieb)."))
    if ohne_aussage and not args.bereinigt:
        arten = ", ".join(sorted({str(b.get('dismiss_reason') or '') for b in ohne_aussage}))
        ausgabe(f"   Achtung: {len(ohne_aussage)} von {len(beispiele)} Beispielen haben einen Grund ohne Aussage über die Passung "
                f"({arten}). Der Betrieb gibt sie der KI als abgelehnt mit; --bereinigt zeigt, was ohne sie herauskommt.")
    ausgabe("")


def _nur_lokal(args, db, dienst_fabrik, ausgabe, urteile, plan, beispiele, gruende, ohne_aussage, payload_fuer) -> int:
    """`--ollama` ohne `--senden`: NUR die lokale KI messen. Kein Schluessel, kein Budget, nichts geht ins Netz.

    Dieselbe Stichprobe, derselbe Prompt-Bauer und dieselbe Auswertung wie beim Vergleich neben der API -- so lassen sich
    die Beispiele ("wie im Betrieb" gegen `--bereinigt`) an der lokalen KI messen, ohne ein Guthaben anzufassen.
    """
    from bewerbungs_assistent.services.llm_service import LLMService
    ausgabe("Messprobe der lokalen KI (#1236) — nichts geht ins Netz: nur Ollama auf diesem Rechner")
    _referenz_ausgeben(args, ausgabe, urteile, plan, beispiele, gruende, ohne_aussage)
    if args.firmennamen or args.modell:
        ausgabe("Hinweis: --firmennamen und --modell betreffen nur die API und werden hier nicht beachtet "
                "(lokal verlassen die Namen den Rechner nie).")
        ausgabe("")
    svc = (dienst_fabrik or LLMService)(db)
    ausgabe(f"Die lokale KI beantwortet {len(plan)} Stellen nacheinander.")
    zeilen, grund = ollama_lauf(plan, payload_fuer, dienst=svc, rueckmeldung=ausgabe)
    if grund:
        raise ProbeFehler(grund, code=2)
    ausgabe("")
    for zeile in block_text("Lokale KI (Ollama)", zeilen, ausgabe_kosten=False):
        ausgabe(zeile)
    if args.ausgabe:
        _json_schreiben(Path(args.ausgabe), {"modus": "nur_lokal", "seed": args.seed, "bereinigt": bool(args.bereinigt),
                                             "ollama": {"zeilen": zeilen, "auswertung": _ohne_listen(auswerten(zeilen))}})
    return 0


def api_lauf_mit_namen(db, plan, payload_fuer, svc, ausgabe):
    """Die Vergleichsvariante: die Beispiele MIT Firmennamen. Dafuer wird die Schwaerzung fuer diesen Lauf ausgesetzt."""
    from bewerbungs_assistent.services import api_backend
    echt = api_backend._beispiele_schwaerzen
    api_backend._beispiele_schwaerzen = lambda eintraege: list((eintraege or [])[:5])
    try:
        return api_lauf(db, plan, payload_fuer, dienst=svc, rueckmeldung=ausgabe)
    finally:
        api_backend._beispiele_schwaerzen = echt


def _ohne_listen(a: dict) -> dict:
    return {k: v for k, v in a.items() if k not in ("zu_unrecht_aussortiert", "nicht_aussortiert")} | {
        "zu_unrecht_aussortiert": len(a["zu_unrecht_aussortiert"]), "nicht_aussortiert": len(a["nicht_aussortiert"])}


def _json_schreiben(pfad: Path, daten: dict) -> None:
    pfad.write_bytes((json.dumps(daten, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


if __name__ == "__main__":
    # Windows-Konsolen kennen oft nur cp1252: Umlaute, Gedankenstriche und Anfuehrungszeichen duerfen nicht abstuerzen lassen.
    for strom in (sys.stdout, sys.stderr):
        if hasattr(strom, "reconfigure"):
            strom.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
