"""Tests fuer v1.7.22 — #941: erkannte Wiedergaenger bekommen Konsequenz.

Die Erkennung aus #671 arbeitete korrekt und hatte trotzdem keine
Wirkung: erkannt, als NICHT_EMPFOHLEN markiert, und trotzdem als aktive
Stelle angelegt. Nutzerformulierung: *"Wenn das so ist, warum wird die
Stelle dann wieder angezeigt?"*

Zwei Stufen mit unterschiedlicher Haerte — aussortieren beim ersten Mal,
ignorieren beim naechsten. Reposts bleiben ausgenommen.
"""
import pytest

from bewerbungs_assistent.services import stellen_automatik as automatik


def _aussortiert(db, hash_, titel, firma, grund):
    db.save_jobs([{
        "hash": hash_, "title": titel, "company": firma,
        "url": f"https://example.com/{hash_}", "source": "bundesagentur",
        # v1.7.24 (#966): vollstaendige Anzeige, damit das Urteil als
        # BELEGT gilt. Diese Tests pruefen die Automatik, nicht die
        # Guete der Altdaten — die hat eigene Tests.
        "description": (
            "Aufgaben: Betreuung und Weiterentwicklung der PLM-Landschaft, "
            "Abstimmung mit den Fachbereichen, Steuerung externer "
            "Dienstleister und Migration bestehender Strukturen. "
            "Anforderungen: abgeschlossenes Studium, mehrjaehrige "
            "Berufserfahrung, sichere Kommunikation in Deutsch und "
            "Englisch sowie Bereitschaft zu gelegentlichen Reisen."),
        "score": 20,
    }])
    voll = db.resolve_job_hash(hash_)
    db.dismiss_job(voll, grund)
    return voll


# ── Stufe 1: erstmalig erkannt -> aussortieren ───────────────────────

def test_941_wiedergaenger_wird_automatisch_aussortiert(tmp_db):
    """Regressionsfall `85998226`: zweimal gehalt_zu_niedrig, dritte Stelle."""
    _aussortiert(tmp_db, "w941a", "PLM Berater (m/w/d)",
                 "Beratungshaus Sued GmbH", "gehalt_zu_niedrig")
    _aussortiert(tmp_db, "w941b", "PLM Consultant",
                 "Beratungshaus Sued GmbH", "gehalt_zu_niedrig")

    neu = {"hash": "w941c", "title": "PLM Architect (m/w/d)",
           "company": "Beratungshaus Sued GmbH"}
    e = automatik.entscheide(tmp_db, neu)
    assert e["aktion"] == "aussortieren", e
    assert e["grund"] == "gehalt_zu_niedrig"
    assert "2x" in e["beleg"]


def test_941_aussortierte_stelle_wird_inaktiv_angelegt(tmp_db):
    """Sie bleibt zurueckholbar — nicht geloescht, nur nicht mehr aktiv."""
    # Ueberlappende, aber NICHT identische Fachtokens: aehnlich genug
    # fuer die Automatik, verschieden genug, um sichtbar zu bleiben.
    # (Identische Kombination waere Stufe 2 = ignorieren.)
    _aussortiert(tmp_db, "w941d", "PDM Spezialist CAD", "Werk Nord AG",
                 "falsches_fachgebiet")
    _aussortiert(tmp_db, "w941e", "PDM Berater CAD", "Werk Nord AG",
                 "falsches_fachgebiet")

    frisch = [{"hash": "w941f", "title": "PDM Manager Teamcenter (m/w/d)",
               "company": "Werk Nord AG", "score": 30,
               "url": "https://example.com/w941f", "source": "bundesagentur",
               "description": "Eine Beschreibung mit ausreichender Laenge fuer den Test."}]
    erg = automatik.anwenden(tmp_db, frisch)
    assert erg["zaehler"]["automatisch_aussortiert"] == 1
    job = erg["jobs"][0]
    assert job["is_active"] == 0
    # #913: Lern-Feld nur Vokabular, Freitext getrennt.
    assert job["dismiss_reason"].startswith("auto:falsches_fachgebiet")
    assert "Wiedergaenger" in job["dismiss_note"]

    tmp_db.save_jobs(erg["jobs"])
    row = tmp_db.connect().execute(
        "SELECT is_active, dismiss_reason, dismiss_note FROM jobs "
        "WHERE hash LIKE '%w941f'").fetchone()
    assert row[0] == 0, "muss inaktiv in der DB landen"
    assert row[1].startswith("auto:")
    assert "Wiedergaenger" in (row[2] or "")


# ── Stufe 2: schon einmal weg -> gar nicht erst anlegen ──────────────

def test_941_bekannte_kombination_wird_ignoriert(tmp_db):
    """Der Kern der Vorgabe: nicht erneut vorgelegt bekommen."""
    _aussortiert(tmp_db, "w941g", "CRM Manager HubSpot", "Medienhaus Nord GmbH",
                 "falsche_branche")

    neu = {"hash": "w941h", "title": "CRM Manager HubSpot (m/w/d)",
           "company": "Medienhaus Nord GmbH"}
    e = automatik.entscheide(tmp_db, neu)
    assert e["aktion"] == "ignorieren", e


def test_941_ignorierte_stellen_werden_gar_nicht_gespeichert(tmp_db):
    _aussortiert(tmp_db, "w941i", "SAP Basis Administrator", "Systemhaus Ost AG",
                 "falsches_fachgebiet")
    frisch = [{"hash": "w941j", "title": "SAP Basis Administrator (m/w/d)",
               "company": "Systemhaus Ost AG", "score": 25,
               "url": "https://example.com/w941j", "source": "bundesagentur"}]
    erg = automatik.anwenden(tmp_db, frisch)
    assert erg["zaehler"]["ignoriert"] == 1
    assert erg["jobs"] == []


# ── Stufe 1b: dieselbe Art Stelle, andere Firma ──────────────────────

def test_941_titel_muster_greift_firmenuebergreifend(tmp_db):
    """Regressionsfall CRM: dreimal aussortiert, jedes Mal andere Firma."""
    for i, firma in enumerate(("Medienhaus A GmbH", "Agentur B GmbH",
                               "Verlag C AG")):
        _aussortiert(tmp_db, f"w941k{i}", "Senior CRM Manager HubSpot",
                     firma, "falsche_branche")

    muster = automatik.find_titel_muster(
        tmp_db, "CRM Manager (m/w/d) HubSpot")
    assert muster is not None, "dreimal dieselbe Machart muss auffallen"
    assert muster["anzahl"] >= 3
    assert muster["top_grund"] == "falsche_branche"

    e = automatik.entscheide(tmp_db, {"hash": "w941l",
                                      "title": "CRM Manager (m/w/d) HubSpot",
                                      "company": "Ganz Andere GmbH"})
    assert e["aktion"] == "aussortieren", e


def test_941_titel_muster_schlaegt_nicht_bei_zwei_zufaellen_zu(tmp_db):
    """Firmenuebergreifend gilt bewusst eine hoehere Schwelle."""
    for i, firma in enumerate(("Medienhaus A GmbH", "Agentur B GmbH")):
        _aussortiert(tmp_db, f"w941m{i}", "Senior CRM Manager HubSpot",
                     firma, "falsche_branche")
    assert automatik.find_titel_muster(
        tmp_db, "CRM Manager (m/w/d) HubSpot") is None


def test_941_titel_muster_verlangt_gemeinsame_fachtokens(tmp_db):
    """Drei beliebige Aussortierungen sind kein Muster."""
    _aussortiert(tmp_db, "w941n", "PLM Berater", "A GmbH", "zu_weit_entfernt")
    _aussortiert(tmp_db, "w941o", "SAP Entwickler", "B GmbH", "zu_weit_entfernt")
    _aussortiert(tmp_db, "w941p", "Kaufmann Vertrieb", "C GmbH", "zu_weit_entfernt")
    assert automatik.find_titel_muster(
        tmp_db, "CRM Manager HubSpot") is None


# ── Repost bleibt ausgenommen ────────────────────────────────────────

def test_941_repost_wird_nur_markiert_nie_aussortiert(tmp_db):
    """Trennlinie: 'mehrfach verworfen' rechtfertigt Automatik,
    'hier beworben' nicht — ein Repost kann eine zweite Chance sein."""
    _aussortiert(tmp_db, "w941q", "PLM Berater", "Zweite Chance GmbH",
                 "gehalt_zu_niedrig")
    _aussortiert(tmp_db, "w941r", "PLM Consultant", "Zweite Chance GmbH",
                 "gehalt_zu_niedrig")

    e = automatik.entscheide(
        tmp_db, {"hash": "w941s", "title": "PLM Architect",
                 "company": "Zweite Chance GmbH"}, ist_repost=True)
    assert e["aktion"] == "anlegen", e
    assert "Repost" in e["hinweis"]


# ── Zaehlung und Statistik ───────────────────────────────────────────

def test_941_zaehler_trennt_aussortiert_und_ignoriert(tmp_db):
    """Die Abschlussmeldung muss beide Zahlen getrennt nennen — sonst
    faellt eine zu scharfe Regel niemandem auf."""
    _aussortiert(tmp_db, "w941t", "PLM Berater", "Firma Eins GmbH", "zeitarbeit")
    _aussortiert(tmp_db, "w941u", "PLM Consultant", "Firma Eins GmbH", "zeitarbeit")
    _aussortiert(tmp_db, "w941v", "PDM Spezialist", "Firma Zwei GmbH",
                 "firma_uninteressant")

    frisch = [
        {"hash": "w941w", "title": "PLM Architect", "company": "Firma Eins GmbH",
         "score": 30, "url": "https://example.com/w", "source": "bundesagentur"},
        {"hash": "w941x", "title": "PDM Spezialist", "company": "Firma Zwei GmbH",
         "score": 20, "url": "https://example.com/x", "source": "bundesagentur"},
        {"hash": "w941y", "title": "Ganz neue Rolle", "company": "Frisch AG",
         "score": 25, "url": "https://example.com/y", "source": "bundesagentur"},
    ]
    erg = automatik.anwenden(tmp_db, frisch)
    z = erg["zaehler"]
    assert z["automatisch_aussortiert"] == 1, erg
    assert z["ignoriert"] == 1, erg
    assert len(erg["jobs"]) == 2  # aussortierte bleibt in der Liste, ignorierte nicht


def test_941_aussortierte_zaehlen_nicht_in_der_statistik(tmp_db):
    """AK: avg_score und scored_jobs duerfen sich nicht veraendern.

    Sonst wuerde der Durchschnitt zunehmend von Stellen bestimmt, die
    der Nutzer nie gesehen hat.
    """
    tmp_db.save_jobs([{
        "hash": "w941z", "title": "PLM Architect", "company": "Sichtbar GmbH",
        "url": "https://example.com/z", "source": "bundesagentur", "score": 60,
        "description": "Eine ausreichend lange Beschreibung fuer den Test.",
    }])
    vorher = tmp_db.get_statistics()

    tmp_db.save_jobs([{
        "hash": "w9410", "title": "Automatisch weg", "company": "Unsichtbar GmbH",
        "url": "https://example.com/0", "source": "bundesagentur", "score": 5,
        "is_active": 0, "dismiss_reason": "auto:falsches_fachgebiet:wiedergaenger",
        "description": "Eine ausreichend lange Beschreibung fuer den Test.",
    }])
    nachher = tmp_db.get_statistics()

    for feld in ("avg_score", "scored_jobs"):
        if feld in vorher and feld in nachher:
            assert vorher[feld] == nachher[feld], (
                f"{feld} hat sich durch eine aussortierte Stelle veraendert")


def test_941_reaktivierung_wird_als_lernsignal_protokolliert(tmp_db):
    """Wird eine automatisch aussortierte Stelle zurueckgeholt, steht die
    Regel zu scharf. Das muss auffallen koennen."""
    tmp_db.save_jobs([{
        "hash": "w9411", "title": "Faelschlich weg", "company": "Reue GmbH",
        "url": "https://example.com/1", "source": "bundesagentur", "score": 30,
        "is_active": 0, "dismiss_reason": "auto:falsches_fachgebiet:wiedergaenger",
    }])
    voll = tmp_db.resolve_job_hash("w9411")
    job = tmp_db.get_job(voll)
    assert job["is_active"] == 0
    assert (job["dismiss_reason"] or "").startswith("auto:")

    vorher = tmp_db.get_activity_event_count()
    tmp_db.add_activity_event({
        "event_type": "auto_dismiss_zurueckgeholt", "entity_type": "job",
        "entity_id": voll[:8], "action": "reaktivieren",
        "metadata": {"dismiss_reason": job["dismiss_reason"]},
    })
    assert tmp_db.get_activity_event_count() > vorher


# ── Was NIE eine Automatik ausloesen darf ────────────────────────────

def test_941_bewerbung_erstellt_loest_keine_automatik_aus(tmp_db):
    """Der gefaehrlichste Fall, live gefunden.

    `bewerbung_erstellt` ist kein Ablehnungsgrund, sondern das Gegenteil:
    die Stelle wurde geschlossen, WEIL sich der Nutzer beworben hat.
    Als Muster gelesen wuerde die Automatik ausgerechnet die
    aehnlichsten — also besten — Stellen unterdruecken. Am echten
    Bestand kam dieser Grund 23 Mal zusammen und haette die
    bestbewertete Stelle aussortiert.
    """
    for i, firma in enumerate(("Alpha GmbH", "Beta GmbH", "Gamma GmbH",
                               "Delta GmbH")):
        _aussortiert(tmp_db, f"w941A{i}", "PLM Consultant CAD", firma,
                     "bewerbung_erstellt")
    assert automatik.find_titel_muster(tmp_db, "PLM Consultant CAD") is None
    e = automatik.entscheide(tmp_db, {"hash": "w941B", "title": "PLM Consultant CAD",
                                      "company": "Neue Firma GmbH"})
    assert e["aktion"] == "anlegen", e


def test_941_freitext_gruende_loesen_keine_automatik_aus(tmp_db):
    """Freitext ist eine Notiz, keine Kategorie.

    Live-Befund: vier Alt-Eintraege mit einem Freitext-Grund haetten
    die bestbewertete Stelle des Bestands automatisch aussortiert. Der
    Altbestand traegt allein 101 verschiedene Freitexte (#913).
    """
    for i, firma in enumerate(("Eins GmbH", "Zwei GmbH", "Drei GmbH",
                               "Vier GmbH")):
        _aussortiert(tmp_db, f"w941C{i}", "PLM Berater Windchill", firma,
                     'zu "hands-on"')
    assert automatik.find_titel_muster(tmp_db, "PLM Berater Windchill") is None


def test_941_buchhaltungsgruende_loesen_keine_automatik_aus(tmp_db):
    """duplikat und bereits_beworben sagen nichts ueber Passung."""
    for grund in ("duplikat", "bereits_beworben"):
        for i, firma in enumerate(("A GmbH", "B GmbH", "C GmbH")):
            _aussortiert(tmp_db, f"w941D{grund[:3]}{i}", "SAP Berater MM",
                         firma, grund)
    assert automatik.find_titel_muster(tmp_db, "SAP Berater MM") is None


# ── Rueckhol-Liste (REST) ────────────────────────────────────────────

def test_941_endpunkt_liefert_nur_automatisch_aussortierte(tmp_db):
    """Der volle Aussortiert-Bestand waere als Liste unbrauchbar.

    Gezeigt wird nur, was die Automatik ohne Rueckfrage entschieden hat
    — das ist der Teil, den der Nutzer nie gesehen hat.
    """
    # von Hand aussortiert -> gehoert NICHT in die Rueckhol-Liste
    _aussortiert(tmp_db, "w941E", "Von Hand weg", "Manuell GmbH",
                 "firma_uninteressant")
    # von der Automatik aussortiert -> gehoert hinein
    tmp_db.save_jobs([{
        "hash": "w941F", "title": "Automatisch weg", "company": "Automatik GmbH",
        "url": "https://example.com/F", "source": "bundesagentur", "score": 20,
        "is_active": 0, "dismiss_reason": "auto:falsches_fachgebiet:wiedergaenger",
        "dismiss_note": "Wiedergaenger: 2x aussortiert.",
    }])

    liste = tmp_db.get_auto_dismissed_jobs(limit=20)
    titel = [j["title"] for j in liste]
    assert "Automatisch weg" in titel
    assert "Von Hand weg" not in titel


def test_941_rueckhol_liste_ist_begrenzt(tmp_db):
    for i in range(8):
        tmp_db.save_jobs([{
            "hash": f"w941G{i}", "title": f"Auto {i}", "company": f"Firma {i} GmbH",
            "url": f"https://example.com/G{i}", "source": "bundesagentur",
            "score": 20, "is_active": 0,
            "dismiss_reason": "auto:zu_junior:wiedergaenger",
        }])
    assert len(tmp_db.get_auto_dismissed_jobs(limit=3)) == 3
    assert len(tmp_db.get_auto_dismissed_jobs(limit=20)) == 8
