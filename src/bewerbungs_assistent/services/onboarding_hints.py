"""Onboarding-Hints fuer ungenutzte Features (#652, G11, beta.76).

Hint-System fuer Features die im Code da sind, vom User aber kaum
genutzt werden. Reality-Check 2026-06-01 hat 3 Faelle aufgedeckt:

- 0 Suchprofile bei 4+ Bewerbungen
- 0 Reisekosten/Vorbereitungszeit-Eintraege bei vielen Terminen
- 0 Interview-Reflexionen bei mehreren Interview-Status

Frontend-Komponente kommt separat. Backend liefert:
- `list_active_hints(db)` — alle Hints mit erfuellter Bedingung + nicht
  dismissed
- `dismiss_hint(db, hint_id)` — persistiert die Wegklick-Entscheidung

Hints werden ueber `HINT_DEFINITIONS` deklariert. Pro Hint:
- `id`: stabiler String, persistiert
- `tab`: Wo der Hint sinnvoll waere (frontend-Routing-Hilfe)
- `title`: 1-Zeiler fuer die Card
- `body`: kurzer Text mit konkretem Vorschlag
- `cta_label`: Button-Text
- `cta_tool`: MCP-Tool-Vorschlag (Claude-Hint), oder leer
- `condition(db)`: liefert True wenn der Hint erscheinen soll
"""
from __future__ import annotations

import json
from typing import Callable


# Setting-Key fuer dismissed Hints (JSON-Liste)
_DISMISSED_KEY = "onboarding_hints_dismissed"


def _get_dismissed(db) -> list[str]:
    """Liest die Liste der bisher dismissten Hint-IDs aus profile_settings."""
    try:
        raw = db.get_setting(_DISMISSED_KEY, "") or ""
        if not raw:
            return []
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(x) for x in data]
    except (json.JSONDecodeError, ValueError, TypeError):
        pass
    return []


def _set_dismissed(db, hint_ids: list[str]) -> None:
    """Schreibt die Liste der dismissten Hint-IDs zurueck."""
    try:
        db.set_setting(_DISMISSED_KEY, json.dumps(sorted(set(hint_ids))))
    except Exception:
        pass


# ── Condition-Helper ────────────────────────────────────────────────


def _condition_profil_ohne_suchbegriffe(db) -> bool:
    """G17-Anschluss (#744, v1.7.5): Profil existiert, aber noch keine
    Suchbegriffe — der Dashboard-First-User haengt genau da fest, wo der
    Chat-Wizard mit Phase 5 weiterfuehren wuerde."""
    try:
        if not db.get_profile():
            return False
        crit = db.get_search_criteria()
        return not (crit.get("keywords_muss") or crit.get("keywords_plus"))
    except Exception:
        return False


def _condition_notizen_leer_oder_kurz(db) -> bool:
    """H15 (#707, v1.7.6): Profil existiert, aber die informellen Notizen
    sind leer oder sehr kurz — dabei speisen sie Anschreiben-Tonalitaet,
    Bewertung und Interview-Vorbereitung."""
    try:
        profile = db.get_profile()
        if not profile:
            return False
        notizen = (profile.get("informal_notes") or "").strip()
        return len(notizen) < 80
    except Exception:
        return False


def _jobboersen_ohne_suchbegriffe(db) -> list[str]:
    """Gewaehlte Browser-Jobboersen ohne eigene Suchbegriffe (B70, #1087 C5).

    Bis v1.7.133 hiess der Hinweis "noch kein Suchprofil" und erschien, sobald
    irgendein Portal-Eintrag fehlte — auch bei gepflegten MUSS/PLUS/MINUS-
    Begriffen. Gemeint war der Eintrag je Jobboerse (#564). Jetzt zaehlt nur
    eine GEWAEHLTE Browser-Jobboerse, fuer die nichts hinterlegt ist, und der
    Hinweis nennt sie. Nachsehen legt nichts an (`find_...`, #1049).
    """
    from ..job_scraper import SOURCE_REGISTRY, zugriffsart_von
    from .search_service import aktive_quellen
    aktiv = aktive_quellen(db, SOURCE_REGISTRY) or []
    namen = []
    for key in aktiv:
        if zugriffsart_von(key) != "browser_login":
            continue
        eintrag = db.find_portal_search_profile(key)
        if eintrag and (eintrag.get("primaere_suchen") or eintrag.get("sekundaere_suchen")):
            continue
        namen.append(SOURCE_REGISTRY.get(key, {}).get("name") or key)
    return namen


def _condition_keine_suchprofile_aber_bewerbungen(db) -> bool:
    """Hinweis, wenn eine gewaehlte Browser-Jobboerse keine Suchbegriffe hat
    und schon Bewerbungen laufen (dann lohnt die Pflege)."""
    try:
        if not _jobboersen_ohne_suchbegriffe(db):
            return False
        return len(db.get_applications(limit=0)) >= 3
    except Exception:
        return False


def _text_jobboersen_ohne_suchbegriffe(db) -> str:
    try:
        namen = _jobboersen_ohne_suchbegriffe(db)
    except Exception:
        return ""
    if not namen:
        return ""
    liste = ", ".join(namen)
    return (
        f"Für {liste} sind keine eigenen Suchbegriffe hinterlegt. Dort "
        "funktionieren oft andere Begriffe als in deinen Suchkriterien — "
        "zum Beispiel ein Titel statt einer Abkürzung. Claude merkt sich, "
        "was auf der Jobbörse Treffer bringt."
    )


def _condition_keine_aufwandskosten_aber_termine(db) -> bool:
    """Hint sinnvoll wenn: >=5 Meetings + 0 Reisekosten/Vorbereitungszeit-Eintraege."""
    try:
        conn = db.connect()
        pid = db.get_active_profile_id()
        meeting_count = conn.execute(
            "SELECT COUNT(*) AS n FROM meetings WHERE "
            "(profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()
        if not meeting_count or (meeting_count["n"] or 0) < 5:
            return False
        kosten_count = conn.execute(
            "SELECT COUNT(*) AS n FROM application_costs WHERE "
            "(profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()
        if kosten_count and (kosten_count["n"] or 0) > 0:
            return False
        # Plus: Vorbereitungszeit pruefen (kommt aus meetings.preparation_minutes)
        prep_count = conn.execute(
            "SELECT COUNT(*) AS n FROM meetings WHERE "
            "(profile_id=? OR profile_id IS NULL) AND preparation_minutes > 0",
            (pid,)
        ).fetchone()
        return not (prep_count and (prep_count["n"] or 0) > 0)
    except Exception:
        return False


def _condition_keine_interview_reflexion_aber_interviews(db) -> bool:
    """Hint sinnvoll wenn: >=2 Bewerbungen mit Interview-Status + 0 Reflexionen."""
    try:
        conn = db.connect()
        pid = db.get_active_profile_id()
        INTERVIEW_STATUSES = (
            "interview", "zweitgespraech", "interview_abgeschlossen",
        )
        placeholders = ",".join("?" for _ in INTERVIEW_STATUSES)
        interview_count = conn.execute(
            f"SELECT COUNT(*) AS n FROM applications WHERE "
            f"(profile_id=? OR profile_id IS NULL) "
            f"AND status IN ({placeholders})",
            (pid, *INTERVIEW_STATUSES)
        ).fetchone()
        if not interview_count or (interview_count["n"] or 0) < 2:
            return False
        reflexion_count = conn.execute(
            "SELECT COUNT(*) AS n FROM interview_reflections WHERE "
            "(profile_id=? OR profile_id IS NULL)", (pid,)
        ).fetchone()
        return not (reflexion_count and (reflexion_count["n"] or 0) > 0)
    except Exception:
        return False


# ── Hint-Definitionen ───────────────────────────────────────────────

def _condition_schwelle_nach_1052(db) -> bool:
    """Steht eine Schwelle aus der Zeit vor der Score-Trennung? (#1052)

    Bewusst BILLIG — zwei Lesezugriffe, kein Backtest. Diese Bedingung
    laeuft bei jedem Seitenaufbau; die teure Rechnung haengt am Klick.
    """
    try:
        from .schwellen_umstellung import offen
        return bool(offen(db).get("betroffen"))
    except Exception:
        return False


def _condition_gehalt_aus_praeferenzen_entfernt(db) -> bool:
    """Wurden doppelt gefuehrte Gehaltswerte aus dem Profil entfernt? (#1055)

    Der Hinweis erscheint genau so lange, bis der Mensch ihn weggeklickt
    hat — er nennt, was im Profil stand und was stattdessen gilt. Ohne
    ihn waere ein gesetzter Wert still verschwunden (#1053).
    """
    try:
        from .praeferenzen_quelle import entfernte_werte
        return bool(entfernte_werte(db))
    except Exception:
        return False


def _text_gehalt_entfernt(db) -> str:
    """Die entfernten Werte im Klartext — Zahlen statt Behauptung."""
    try:
        from .praeferenzen_quelle import entfernte_werte
        felder = entfernte_werte(db)
    except Exception:
        return ""
    teile = []
    for feld, angabe in sorted(felder.items()):
        gilt = angabe.get("gilt")
        teile.append(f"{feld}: im Profil stand {angabe.get('im_profil')}, "
                     f"es gilt {gilt if gilt is not None else 'kein Wert'}")
    return "; ".join(teile)


def _condition_schwelle_ist_jetzt_stufe(db) -> bool:
    """Wurde eine gesetzte Schwellen-ZAHL zu einer Stufe? (#1063)

    Ein gesetzter Wert darf nicht still wandern (#1053). Der Hinweis
    nennt die alte Zahl und die Stufe, auf der sie jetzt liegt.
    """
    try:
        from .schwellen_stufen import BELEG
        return bool(db.get_profile_setting(BELEG, None))
    except Exception:
        return False


def _text_schwelle_ist_jetzt_stufe(db) -> str:
    try:
        from . import schwellen_stufen as _st
        beleg = db.get_profile_setting(_st.BELEG, None) or []
        namen = {s["schluessel"]: s["name"] for s in _st.STUFEN}
    except Exception:
        return ""
    wo = {"speichern": "beim Speichern waehrend der Suche",
          "liste": "beim Ausblenden in der Liste"}
    teile = []
    for e in beleg:
        teile.append(
            f"{wo.get(e.get('bereich'), e.get('bereich'))}: aus "
            f"{e.get('zahl_vorher')} wurde die Stufe "
            f"\"{namen.get(e.get('stufe'), e.get('stufe'))}\"")
    return "; ".join(teile)


def _condition_quelle_entfernt(db) -> bool:
    """Wurde eine gewaehlte Quelle entfernt, weil es sie nicht mehr gibt?

    #1066: Monster stand seit #653 als `deprecated` und wurde trotzdem
    weiter angeboten. Jetzt ist die Quelle weg — und ein stiller Wegfall
    waere das Muster aus #211.
    """
    try:
        return bool(db.get_profile_setting("entfernte_quellen_hinweis", None))
    except Exception:
        return False


def _text_quelle_entfernt(db) -> str:
    """Welche Quelle, warum, und was stattdessen taugt."""
    try:
        from ..job_scraper import ENTFERNTE_QUELLEN, SOURCE_REGISTRY
        keys = db.get_profile_setting("entfernte_quellen_hinweis", None) or []
    except Exception:
        return ""
    teile = []
    for k in keys:
        e = ENTFERNTE_QUELLEN.get(k)
        if not e:
            continue
        ersatz = (SOURCE_REGISTRY.get(e.get("ersatz") or "") or {}).get("name")
        satz = f"{e['name']}: {e['grund']}"
        if ersatz:
            satz += f" Stattdessen deckt {ersatz} dieses Portal ab."
        teile.append(satz)
    return " ".join(teile)


def _condition_suchbegriffe_offen(db) -> bool:
    """Gibt es offene Vorschlaege aus dem Abgleich Profil/Suchbegriffe? (#1054)

    Gerechnet wird beim Lesen — damit ist der Hinweis nach JEDER
    Aenderung an Profil oder Listen aktuell, ohne dass ein Schreibweg
    daran denken muss, ihn anzustossen. Ein Zwischenspeicher haette
    genau die Drift, gegen die der Abgleich gebaut ist.
    """
    try:
        from .suchbegriff_abgleich import abgleich
        return abgleich(db)["offen"] > 0
    except Exception:
        return False


def _text_suchbegriffe_offen(db) -> str:
    try:
        from .suchbegriff_abgleich import abgleich, kurzfassung
        return kurzfassung(abgleich(db))
    except Exception:
        return ""


def _condition_notizen_mit_bewerbungsbezug(db) -> bool:
    """Stehen Profilsektionen mit Bewerbungsbezug im Bestand? (#1056)"""
    try:
        from .notiz_routing import vorschlaege
        return bool(vorschlaege(db))
    except Exception:
        return False


def _text_notizen_mit_bewerbungsbezug(db) -> str:
    try:
        from .notiz_routing import vorschlaege
        v = vorschlaege(db)
    except Exception:
        return ""
    if not v:
        return ""
    namen = "; ".join(f"'{x['sektion']}' -> {x['firma']} ({x['zeichen']} Zeichen)"
                      for x in v[:3])
    rest = f" und {len(v) - 3} weitere" if len(v) > 3 else ""
    return f"{len(v)} Sektion(en): {namen}{rest}"


HINT_DEFINITIONS: list[dict] = [
    {
        "id": "d47_notizen_an_die_bewerbung",
        "tab": "profil",
        "title": "Profilnotizen, die zu einer Bewerbung gehören",
        "body": (
            "Deine Profilnotizen sollen beschreiben, wer du bist. Einige "
            "Sektionen nennen in der Überschrift eine Firma, bei der du "
            "dich beworben hast — eine Interview-Nachlese etwa. Jedes "
            "Anschreiben und jedes Dossier liest das Profil mit, auch das "
            "für eine andere Firma. Solche Sektionen gehören in die "
            "Timeline der Bewerbung. Verschoben wird nur, was du "
            "bestätigst."
        ),
        "cta_label": "PBP: Profil-Notizen aufräumen",
        "cta_tool": "profil_notizen_aufraeumen",
        "condition": _condition_notizen_mit_bewerbungsbezug,
        "detail": _text_notizen_mit_bewerbungsbezug,
    },
    {
        "id": "c87_suchbegriffe_gegen_profil",
        "tab": "dashboard",
        "title": "Deine Suchbegriffe bilden dein Profil nicht ganz ab",
        "body": (
            "Die Punkte messen, wie gut eine Anzeige deine Suchbegriffe "
            "trifft. Das sagt nur dann etwas über dich, wenn die Listen "
            "dein Profil abbilden — und die werden von Hand gepflegt. Der "
            "Abgleich hat Vorschläge: Skills, die in keiner Liste stehen; "
            "MINUS-Begriffe, die dein eigenes Fachgebiet treffen; "
            "Rahmenbegriffe wie Orte oder Arbeitsmodelle in den Fachlisten. "
            "Nichts davon wird ohne dich geaendert."
        ),
        "cta_label": "PBP: Suchbegriffe mit meinem Profil abgleichen",
        "cta_tool": "profil_suchbegriffe_abgleichen",
        "condition": _condition_suchbegriffe_offen,
        "detail": _text_suchbegriffe_offen,
    },
    {
        "id": "c86_gehalt_nur_einstellungsseite",
        "tab": "profil",
        "title": "Gehalt und Sätze stehen jetzt nur noch an einer Stelle",
        "body": (
            "Mindestgehalt, Tages- und Stundensaetze und die "
            "Entfernungsgrenze standen doppelt: in den Suchkriterien "
            "(Einstellungsseite) und in den Job-Präferenzen aus der "
            "Ersterfassung. Die zweiten hatten kein Eingabefeld und "
            "wurden nie nachgezogen — gemessen wichen sie ab. Es gilt "
            "die Einstellungsseite; die Werte im Profil sind entfernt. "
            "Was dort stand, steht hier, damit nichts still verschwindet."
        ),
        "cta_label": "PBP: Suchkriterien anzeigen",
        "cta_tool": "suchkriterien_anzeigen",
        "condition": _condition_gehalt_aus_praeferenzen_entfernt,
        "detail": _text_gehalt_entfernt,
    },
    {
        "id": "c91_schwelle_ist_jetzt_stufe",
        "tab": "einstellungen",
        "title": "Deine Score-Schwelle ist jetzt eine Stufe",
        "body": (
            "Die Schwelle war eine Zahl ohne Bezugsgröße — ob 7 viel "
            "oder wenig ist, weiß nur, wer die Verteilung kennt. Und sie "
            "bedeutete nach jeder Änderung an Gewichten oder "
            "Begriffslisten etwas anderes, ohne dass du sie angefasst "
            "hast. Jetzt wählst du eine benannte Stufe; die Zahl dahinter "
            "rechnet PBP aus deinem eigenen Bestand und zieht sie nach. "
            "Deine bisherige Einstellung ist auf die nächstliegende Stufe "
            "gewandert — was vorher dastand, steht hier."
        ),
        "cta_label": "PBP: Schwellen-Stufen anzeigen",
        "cta_tool": "schwelle_stufe_setzen",
        "condition": _condition_schwelle_ist_jetzt_stufe,
        "detail": _text_schwelle_ist_jetzt_stufe,
    },
    {
        "id": "b59_quelle_entfernt",
        "tab": "einstellungen",
        "title": "Eine deiner Quellen gibt es nicht mehr",
        "body": (
            "Eine Quelle, die du ausgewählt hattest, ist aus PBP "
            "entfernt worden — sie liefert keine Stellen mehr. Sie war "
            "vorher als veraltet markiert und wurde trotzdem weiter "
            "angeboten. Der Haken ist jetzt weg; was dort stand und "
            "warum, steht hier, damit die Quelle nicht still "
            "verschwindet."
        ),
        "cta_label": "PBP: Quellen-Health-Check laufen lassen",
        "cta_tool": "quellen_health_check",
        "condition": _condition_quelle_entfernt,
        "detail": _text_quelle_entfernt,
    },
    {
        "id": "c83_schwelle_nach_score_trennung",
        "tab": "stellen",
        "title": "Deine Score-Schwelle meint jetzt etwas anderes",
        "body": (
            "Der Score ist seit diesem Update der FACHWERT allein — "
            "Entfernung, Remote-Anteil und Gehalt zählen nicht mehr mit "
            "hinein, sondern stehen als eigener Rahmenwert daneben. Die "
            "Zahl ist damit kleiner als vorher, und deine gespeicherte "
            "Schwelle filtert schärfer, ohne dass du sie angefasst hast. "
            "Lass dir einen neuen Wert vorschlagen — er kommt aus deiner "
            "eigenen Bewerbungshistorie, nicht aus einer Umrechnung."
        ),
        "cta_label": "PBP: Kalibrierung-Backtest für einen neuen Schwellenwert",
        "cta_tool": "kalibrierung_backtest",
        "condition": _condition_schwelle_nach_1052,
    },
    {
        "id": "g11_erste_suche_starten",
        "tab": "dashboard",
        "title": "Nächster Schritt: Suchbegriffe festlegen und erste Suche starten",
        "body": (
            "Dein Profil steht — aber PBP weiß noch nicht, wonach es suchen "
            "soll. Sag Claude einfach: \"PBP: Keyword-Vorschläge aus meinem "
            "Profil, dann die erste Suche starten.\" Claude leitet die Begriffe aus deinem "
            "Profil ab, du bestätigst sie nur."
        ),
        "cta_label": "PBP: Keyword-Vorschläge aus meinem Profil",
        "cta_tool": "keyword_vorschlaege",
        "condition": _condition_profil_ohne_suchbegriffe,
    },
    {
        "id": "g11_notizen_pflegen",
        "tab": "profil",
        "title": "Tipp: Persönliche Notizen machen PBP treffsicherer",
        "body": (
            "Deine informellen Notizen sind noch (fast) leer. Präferenzen, "
            "No-Gos und Lebensumstände (z.B. \"max. 2 Bürotage\", \"kein "
            "Reisejob\") fließen in Anschreiben, Stellen-Bewertung und "
            "Interview-Vorbereitung ein. Erwähne sie einfach im Chat — "
            "Claude trägt sie automatisch ein."
        ),
        "cta_label": "PBP: Profil bearbeiten — merk dir, höchstens zwei Bürotage",
        "cta_tool": "profil_bearbeiten",
        "condition": _condition_notizen_leer_oder_kurz,
    },
    {
        "id": "g11_suchprofile_anlegen",
        "tab": "stellen",
        "title": "Tipp: Suchbegriffe je Jobbörse",
        "body": (
            "Für eine gewählte Jobbörse sind keine eigenen Suchbegriffe "
            "hinterlegt. Claude merkt sich, was dort Treffer bringt."
        ),
        "body_fn": _text_jobboersen_ohne_suchbegriffe,
        "cta_label": "PBP: Suchbegriffe je Jobbörse aus den Suchkriterien anlegen",
        "cta_tool": "suchprofil_aktualisieren",
        "condition": _condition_keine_suchprofile_aber_bewerbungen,
    },
    {
        "id": "g11_aufwand_tracken",
        "tab": "kalender",
        "title": "Tipp: Aufwand-Tracking fürs Arbeitsamt",
        "body": (
            "Du hast schon Termine — aber noch keine Reisekosten oder "
            "Vorbereitungszeit erfasst. Wenige Klicks, dafür eine saubere "
            "Aufwand-Übersicht (wichtig für Arbeitsamt + steuerliche Geltendmachung)."
        ),
        "cta_label": "PBP: Kosten für den nächsten Termin erfassen",
        "cta_tool": "kosten_erfassen",
        "condition": _condition_keine_aufwandskosten_aber_termine,
    },
    {
        "id": "g11_interview_reflexion",
        "tab": "bewerbungen",
        "title": "Tipp: Interview-Reflexionen zahlen sich aus",
        "body": (
            "Du hast schon Interview-Termine — aber noch keine Reflexion "
            "festgehalten. Was lief gut, was würdest du anders machen? "
            "Wenige Minuten Aufwand jetzt, viel weniger Gefühlskram im "
            "nächsten Interview."
        ),
        "cta_label": "PBP: Interview-Reflexion zum letzten Gespräch speichern",
        "cta_tool": "interview_reflexion_speichern",
        "condition": _condition_keine_interview_reflexion_aber_interviews,
    },
]


# ── Public API ──────────────────────────────────────────────────────


def list_active_hints(db) -> list[dict]:
    """Liefert alle Hints deren Condition erfuellt ist UND die nicht
    dismissed sind."""
    dismissed = set(_get_dismissed(db))
    out = []
    for h in HINT_DEFINITIONS:
        if h["id"] in dismissed:
            continue
        try:
            if h["condition"](db):
                eintrag = {
                    "id": h["id"],
                    "tab": h["tab"],
                    "title": h["title"],
                    "body": h["body"],
                    "cta_label": h["cta_label"],
                    "cta_tool": h["cta_tool"],
                }
                # v1.7.118 (#1055): manche Hinweise tragen eine Zahl aus
                # dem Bestand — was genau entfernt wurde, was
                # stattdessen gilt. Ein Text ohne diese Angabe waere
                # eine Behauptung ueber Werte, die niemand mehr
                # nachlesen kann (#1053). Ein Feld, das die Definition
                # setzt und die Ausgabe verschweigt, waere die Bauform
                # aus #993.
                # B70 (#1087 C5): ein Hinweis, der eine Jobboerse NENNT,
                # braucht den Namen aus dem Bestand.
                if callable(h.get("body_fn")):
                    _body = h["body_fn"](db)
                    if _body:
                        eintrag["body"] = _body
                if callable(h.get("detail")):
                    _detail = h["detail"](db)
                    if _detail:
                        eintrag["detail"] = _detail
                out.append(eintrag)
        except Exception:
            continue
    return out


def dashboard_saetze() -> list[dict]:
    """Jeder "Sag Claude"-Satz aus dem Dashboard mit seinem Werkzeug (#1062).

    Unabhaengig davon, ob der Hinweis gerade angezeigt wird: wer den Satz
    abgetippt hat, kommt damit auch dann in einer frischen Sitzung an,
    wenn der Hinweis inzwischen weg ist. `pbp_capabilities` liefert die
    Liste aus.
    """
    return [{"satz": h["cta_label"], "werkzeug": h["cta_tool"], "hinweis": h["id"]}
            for h in HINT_DEFINITIONS if h.get("cta_tool")]


def dismiss_hint(db, hint_id: str) -> dict:
    """Markiert einen Hint als dismissed (persistent).

    Liefert {dismissed: True, hint_id, total_dismissed} bei Erfolg,
    {error} bei unbekanntem Hint.
    """
    valid_ids = {h["id"] for h in HINT_DEFINITIONS}
    if hint_id not in valid_ids:
        return {"error": f"Unbekannter Hint: {hint_id}", "bekannte_ids": sorted(valid_ids)}
    current = _get_dismissed(db)
    if hint_id not in current:
        current.append(hint_id)
        _set_dismissed(db, current)
    return {
        "dismissed": True,
        "hint_id": hint_id,
        "total_dismissed": len(current),
    }


def reset_dismissed_hints(db) -> dict:
    """Setzt alle dismissten Hints zurueck — fuer Testing / Settings-Reset."""
    _set_dismissed(db, [])
    return {"reset": True, "total_dismissed": 0}
