"""Eine Stelle aussortieren — mit Zaehlern, Lerneffekt und Hinweisen,
an EINER Stelle (#1095).

Die Schritte standen im MCP-Werkzeug (`stelle_einordnen`,
`stellen_bulk_bewerten`). `POST /api/jobs/dismiss` rief nur
`db.dismiss_job` und den Statistik-Zaehler: wer im Dashboard 50 Stellen
als "Zeitarbeit" aussortierte, bekam keinen Lerneffekt, obwohl
Werkzeugbeschreibung und Oberflaeche ihn versprechen. Dieselbe Klasse
wie #963, #991 und #1094.

Zwei Zaehler, zwei Fragen — beide bleiben:
* `dismiss_counts` (Einstellung, je normalisiertem Grund) treibt den
  Lerneffekt (`regler_anpassen`, #908) und die Hinweise.
* `dismiss_reasons.usage_count` ordnet die Auswahl im Dialog nach
  Haeufigkeit und legt einen neuen eigenen Grund an (#126, #302).
Sie zusammenzulegen hiesse, eine der beiden Wirkungen neu zu bauen;
wichtig ist, dass beide auf JEDEM Weg genau einmal zaehlen.
"""
from __future__ import annotations

import logging

from .typed_ids import kurz_job_kennung as _kurz

logger = logging.getLogger(__name__)

#: Wie ein gelernter Grund im Klartext heisst (#1095, fuer die Oberflaeche).
LERNEFFEKT_WORTE = {
    "zu_weit_entfernt": "Weit entfernte Stellen",
    "zeitarbeit": "Stellen in Zeitarbeit",
    "befristet": "Befristete Stellen",
}


def duplikat_finden(db, job_hash: str) -> dict | None:
    """Duplikat-Erkennung (#168): Prüft ob eine ähnliche Stelle existiert.

    v1.7.122 (#1065): fragt `find_duplicate_job` — dieselbe Regel wie
    die Anlage. Bis hierher stand hier eine EIGENE, vierte Fassung
    (Firma als Teilstring, zwei gemeinsame Titelwoerter), und deshalb
    antworteten Anlage und Aussortieren fuer dieselbe Stelle
    verschieden: die Anlage sagte "angelegt", das Aussortieren
    "duplikat_erkannt". Gemeldet mit zwei belegten Faellen.

    Die gemeinsame Regel ist die schaerfere und die gepruefte (#670,
    #951): sie kennt Rechtsform-Normalisierung, URL-Gleichheit und
    eine Titel-Schwelle statt einer Wortzaehlung.
    """
    job = db.get_job(job_hash)
    if not job:
        return None
    titel = job.get("title") or ""
    firma = job.get("company") or ""
    if not titel or not firma:
        return None
    from ..duplicate_detection import find_duplicate_job
    url = job.get("url") or ""

    treffer = find_duplicate_job(firma, titel, url, db.get_applications())
    if treffer:
        app = treffer["job"]
        return {
            "typ": "bewerbung",
            "id": (app.get("id") or "")[:8],
            "titel": app.get("title"),
            "firma": app.get("company"),
            "status": app.get("status"),
            "grund": treffer.get("grund"),
        }

    eigener = job.get("hash") or ""
    treffer = find_duplicate_job(
        firma, titel, url,
        [d for d in db.get_dismissed_jobs()
         if (d.get("hash") or "") != eigener])
    if treffer:
        dj = treffer["job"]
        return {
            "typ": "aussortierte_stelle",
            "hash": _kurz(dj["hash"]),
            "titel": dj.get("title"),
            "firma": dj.get("company"),
            "grund": dj.get("dismiss_reason"),
            "match_grund": treffer.get("grund"),
        }
    return None


def regler_anpassen(db_ref, reason: str, count: int) -> str | None:
    """#110: Automatische Scoring-Anpassung bei wiederholten Ablehnungsmustern.

    Bug #269: Seed-Daten haben profile_id='', daher muss mit
    (profile_id=? OR profile_id='') gesucht werden.
    """
    # v1.7.17 (#917/#908): Die Automatik setzt KEIN ignore_flag mehr —
    # "schaerfer statt aus". Der Nutzer wollte Stellenarten abgewertet,
    # nicht ausgeblendet (Recall vor Praezision); die Flags waren zudem
    # ueber MCP nicht zuruecknehmbar (#917 Defekt A). Jeder Grund traegt
    # (dimension, sub_key, start_malus, max_malus).
    #
    # Entfernung (#917 Defekt C): Ziel-Stufe ist '999' — die Brackets
    # sind OBERGRENZEN ("Malus fuer Stellen BIS X km"). Der alte
    # Schluessel '50km' landete via Ziffern-Extraktion im Bracket 50
    # und bestrafte damit Stellen ZWISCHEN 30 und 50 km — genau den
    # Bereich, den der Nutzer will. Der Lerneffekt war invertiert.
    #
    # zu_junior ist BEWUSST raus (#908 Befund 4): es mappte auf
    # stellentyp/praktikum — ausgeloest aber von Festanstellungen
    # ("mind. 2 Jahre Erfahrung"), die der Hebel nie erreicht.
    # Senioritaet ist keine Stellenart; der Weg sind MINUS-Keywords
    # (Hint unten in _apply_dismiss_with_lifecycle).
    LEARN_MAP = {
        "zu_weit_entfernt": ("entfernung_fest", "999", -2, -10),
        "zeitarbeit": ("stellentyp", "zeitarbeit", -2, -8),
        "befristet": ("stellentyp", "befristet", -2, -6),
    }
    if reason not in LEARN_MAP:
        return None
    dim, sub, start_malus, max_malus = LEARN_MAP[reason]
    conn = db_ref.connect()
    pid = db_ref.get_active_profile_id() or ""
    # #269: Seed-Daten haben profile_id='' — beides prüfen
    existing = conn.execute(
        "SELECT id, value, ignore_flag, profile_id, set_by_user "
        "FROM scoring_config "
        "WHERE (profile_id=? OR profile_id='') AND dimension=? AND sub_key=? "
        "ORDER BY CASE WHEN profile_id=? THEN 0 ELSE 1 END LIMIT 1",
        (pid, dim, sub, pid)
    ).fetchone()
    # v1.7.17 (#917): explizite Nutzer-Entscheidung ist unantastbar.
    # Belegt: Nutzer schaltete das Ignorieren ab, die naechste
    # Aussortierung mit demselben Grund (Zaehler 71, Schwelle 5)
    # kehrte sie kommentarlos wieder um.
    if existing and existing["set_by_user"]:
        return None
    # #908 Befund 5: die alte Formel (count-5)*0.5 erreichte den
    # Deckel schon bei ~13 Nennungen — faktisch ein Zweistufen-
    # Schalter. Jetzt linear ueber den realen Nennungsbereich:
    # Schwelle 5 = start_malus, ab 155 Nennungen = max_malus,
    # dazwischen gleichmaessig (halbe Punkte, monoton).
    fortschritt = min(1.0, max(0.0, (count - 5) / 150.0))
    new_val = start_malus + (max_malus - start_malus) * fortschritt
    new_val = round(new_val * 2) / 2
    alt_val = existing["value"] if existing else None
    if existing and existing["value"] <= new_val:
        return None  # already penalized enough
    # v1.7.113 (#1053): ueber das Nadeloehr der Datenbank — mit
    # Zeitpunkt, Vorgaengerwert und Herkunft "automatik". Bis hierher
    # schrieb der Lerneffekt eigenes SQL, und seine Aenderungen waren
    # spaeter von einer Hand-Einstellung nicht zu unterscheiden.
    db_ref.lerne_scoring_regler(
        dim, sub, new_val,
        anlass=f"Lerneffekt: '{reason}' {count}x als Grund gewählt")
    # #908 Punkt 6: alt->neu benennen und den Rueckweg gleich mitgeben
    # — eine Automatik, die den Bestand umgewichtet, muss revidierbar
    # sein. Landet via auto_adjustments/hints beim Nutzer UND im Log.
    logger.info("Auto-Scoring (#908): '%s' -> %s/%s Malus %s -> %s "
                "(Nennungen: %d)", reason, dim, sub, alt_val, new_val,
                count)
    return (f"'{reason}' → {dim}/{sub} Malus "
            f"{alt_val if alt_val is not None else 'Default'} → {new_val} "
            f"(zuruecknehmbar via scoring_konfigurieren('setzen'/"
            f"'loeschen', '{dim}', '{sub}'))")


def aussortieren(db, job_hash: str, reason_list: list[str],
                 collect_hints: bool = True,
                 skip_auto_adjust: bool = False) -> dict:
    """Wendet 'aussortieren' auf eine Stelle an mit voller PBP-Lifecycle-Logik.

    Geht durch alle Hooks: dismiss_counts, blacklist-hint, auto-adjust-scoring,
    dismiss_reasons-Statistik. Wird von stelle_einordnen UND von
    stellen_bulk_bewerten aufgerufen, damit Audit/Lerneffekt/Statistik in
    beiden Wegen identisch durchlaufen (#514: Anti-DB-Bypass-Pattern).

    Args:
        job_hash: Hash der Stelle
        reason_list: bereits validierte/normalisierte Gruende
        collect_hints: bei Bulk auf False setzen — Tipps werden dann nur
            in der Aggregat-Antwort summiert, nicht pro Einzelaufruf
        skip_auto_adjust: v1.6.5 (#558) — Bulk-Path uebernimmt den
            Auto-Adjust selbst (einmalig am Ende). Verhindert dass jeder
            der 100 Einzelaufrufe das Scoring weiter eskaliert (Drift).
    """
    import json as _json
    reason_str = _json.dumps(reason_list, ensure_ascii=False) if len(reason_list) > 1 else reason_list[0]

    # #168: Duplikat-Erkennung
    dup_info = None
    if "duplikat" in reason_list:
        dup_info = duplikat_finden(db, job_hash)

    db.dismiss_job(job_hash, reason_str)

    # Track rejection counts for learning (#66)
    counts = db.get_setting("dismiss_counts", {})
    hints = []
    for g in reason_list:
        normalized = g.lower().strip()
        counts[normalized] = counts.get(normalized, 0) + 1

        # Suggest scoring adjustments (#169) when patterns are strong
        # v1.7.17 (#908): kein Vorschlag lautet mehr "Komplett
        # Ignorieren" — ein wiederholt genutzter Grund ist ein
        # RELEVANTER Grund und gehoert verschaerft, nicht
        # abgeschaltet. ignore_flag setzt nur noch der Nutzer selbst.
        if collect_hints and counts.get(normalized, 0) >= 3:
            if normalized == "zu_weit_entfernt":
                hints.append("Tipp: Passe den Entfernungs-Malus im Scoring-Regler an (scoring_konfigurieren, Stufe '999' = jenseits aller Grenzen).")
            elif normalized == "gehalt_zu_niedrig":
                hints.append("Tipp: Passe den Gehalts-Regler im Scoring an (scoring_konfigurieren).")
            elif normalized in ("zeitarbeit", "befristet"):
                hints.append(
                    f"Tipp: Der Malus für '{g}' eskaliert automatisch mit. "
                    f"Noch schaerfer: scoring_konfigurieren('setzen', 'stellentyp', '{normalized}', wert=-8). "
                    "Komplett ausblenden nur bewusst mit ignorieren=True."
                )
            elif normalized == "zu_junior" and counts.get(normalized, 0) % 10 == 3:
                # #908 Befund 4: Senioritaet ist keine Stellenart —
                # der wirksame Hebel sind MINUS-Keywords, die auch
                # Festanstellungen erreichen. Vorschlag statt
                # Automatik; gedrosselt (jede 10. Nennung).
                hints.append(
                    "Tipp: 'zu_junior' lernt über MINUS-Keywords, nicht über die Stellenart. "
                    "Kandidaten: suchkriterien_bearbeiten(aktion='hinzufuegen', kategorie='minus', "
                    "werte=['Junior', 'Berufseinsteiger', 'Entry Level', 'Trainee']) — "
                    "Gewicht schärfen via kategorie='gewichten' (#778). Keine Duplikate anlegen."
                )
            elif normalized == "falsches_fachgebiet" and counts.get(normalized, 0) % 25 == 0:
                # #908 Befund 3: das staerkste Signal (1200+ Nennungen)
                # erzeugte NULL Lerneffekt. Der Lerneffekt liegt in den
                # Begriffen — keyword_vorschlaege rechnet die
                # MINUS-Kandidaten mit Belegen vor, der Nutzer
                # entscheidet. Stark gedrosselt (jede 25. Nennung).
                hints.append(
                    f"Hinweis: '{normalized}' wurde inzwischen {counts[normalized]}x genutzt. "
                    "keyword_vorschlaege() schlägt daraus MINUS-Kandidaten mit Trefferzahlen "
                    "und Beispielstellen vor — so lernt der Score aus dem häufigsten Grund."
                )
            elif normalized == "firma_uninteressant":
                job = db.get_job(job_hash)
                company = (job or {}).get("company", "")
                # #729: Hinweis nur wenn die Firma noch NICHT auf der
                # Blacklist steht — sonst schlaegt PBP etwas vor, das schon
                # erledigt ist.
                if company and not db.is_company_blacklisted(company):
                    hints.append(
                        f"Tipp: Möchtest du '{company}' auf die Blacklist setzen? "
                        f"Nutze blacklist_verwalten('hinzufuegen', 'firma', '{company}')."
                    )

    db.set_setting("dismiss_counts", counts)
    db.increment_dismiss_reason_usage(reason_list)

    # #110: Lernender Score — automatische Scoring-Anpassungen bei starken Mustern.
    # v1.6.5 (#558): Bei Bulk wird das einmalig am Ende ausgefuehrt, nicht
    # pro Einzelaufruf. Sonst eskaliert (count-5)*0.5 mit jedem Job und
    # treibt den Score-Malus immer weiter ins Negative ("Score-Drift").
    auto_adjustments = []
    lerneffekt_text: list[str] = []
    if not skip_auto_adjust:
        for g in reason_list:
            normalized = g.lower().strip()
            cnt = counts.get(normalized, 0)
            if cnt >= 5:
                _auto = regler_anpassen(db, normalized, cnt)
                if _auto:
                    auto_adjustments.append(_auto)
                    if normalized in LERNEFFEKT_WORTE:
                        lerneffekt_text.append(
                            f"PBP hat gelernt: {LERNEFFEKT_WORTE[normalized]} bekommen "
                            "ab jetzt etwas weniger Punkte. Zurücknehmen über Claude: "
                            "„PBP: Scoring-Regler anzeigen“.")
        if collect_hints and auto_adjustments:
            hints.append("Scoring wurde automatisch angepasst: " + "; ".join(auto_adjustments))

    return {
        "counts": counts,
        "hints": hints,
        "auto_adjustments": auto_adjustments,
        "lerneffekt_text": lerneffekt_text,
        "duplikat_info": dup_info,
    }

