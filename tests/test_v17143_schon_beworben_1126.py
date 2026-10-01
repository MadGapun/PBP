"""Tests fuer v1.7.143 - #1126 und #1117: "Schon beworben?" fuer alle.

Die Frage, die Stellensuchende bei einer neuen Stelle zuerst haben: "Habe
ich mich da schon beworben?" Die Erkennung gab es seit C30 (#782) - aber
nur fuer Claude. Gemessen am 29.09.2026: Werkzeug ja, Dashboard-Liste nein,
Dashboard-Detail nein. Dazu Defekte im Detail:

1. #1126: ohne Claude keine Warnung.
2. #1126: der Wortlaut passte nur zu ABGESCHLOSSENEN Bewerbungen - bei einer
   laufenden stand dort "ob die alte Huerde noch steht".
3. #1126: `_repost_verdacht` wurde in der Automatik gelesen und nirgends
   gesetzt (L11).
4. #1126: Vermittler-Bewerbungen fehlten in der Warnung.
5. #1117: die Anlage fragte die Erkennung ohne URL - eine zeichengleiche
   Adresse zu einer abgelehnten Bewerbung blieb ohne Hinweis. Dazu
   verhinderte ein Akzent im Firmennamen den Treffer ueber Firma und Titel.

Alle Firmen sind erfunden.
"""
import pytest

from bewerbungs_assistent.duplicate_detection import (
    find_duplicate_job,
    find_repost_of_application,
    find_vermittler_bewerbung,
    normalize_company_name,
)
from bewerbungs_assistent.services import bewerbungs_hinweis

URL_ALT = "https://karriere.beispiel.example/careers/jobs/solution-architect-plm-m-w-d-546057"


def _bewerbung(**felder):
    """Eine Bewerbung als Dict, wie `db.get_applications()` sie liefert."""
    basis = {
        "id": "0e2e7262-1111-2222-3333-444444444444",
        "job_hash": "alt-hash-1",
        "title": "Solution Architect PLM (m/w/d)",
        "company": "Société Beispiel",
        "status": "abgelehnt",
        "applied_at": "2026-05-12",
        "url": URL_ALT,
    }
    basis.update(felder)
    return basis


# ══ #1117: Akzente und Landesgesellschaft ════════════════════════════════

def test_1117_akzent_und_landesgesellschaft_sind_dieselbe_firma():
    assert normalize_company_name("Société Beispiel") == \
        normalize_company_name("Societe Beispiel")
    treffer = find_duplicate_job(
        "Societe Beispiel Deutschland GmbH", "Solution Architect PLM (m/w/d)",
        "", [_bewerbung()])
    assert treffer is not None, "Konzernname mit Akzent gegen Landesgesellschaft"


def test_1117_akzente_falten_macht_keine_verschiedenen_firmen_gleich():
    """Die Gegenrichtung: gefaltet wird der Akzent, nicht der Name."""
    assert normalize_company_name("Société Beispiel") != \
        normalize_company_name("Societe Anderswo")
    assert find_duplicate_job(
        "Societe Anderswo", "Solution Architect PLM (m/w/d)", "",
        [_bewerbung()]) is None


def test_1117_umlaute_bleiben_umschrieben_und_werden_nicht_zu_a():
    """Die Faltung laeuft NACH der Umschrift - sonst wuerde "Müller" zu
    "muller" und passte nicht mehr zu "Mueller"."""
    assert normalize_company_name("Beispiel Müller Straße GmbH") == "beispiel mueller strasse"
    assert normalize_company_name("Beispiel Mueller Strasse GmbH") == "beispiel mueller strasse"


def test_1117_buchstaben_mit_strich_werden_mitgefaltet():
    assert normalize_company_name("Ørnbeispiel Windkraft") == "ornbeispiel windkraft"


# ══ #1117: die URL als zusaetzlicher Beleg ═══════════════════════════════

def test_1117_gleiche_url_reicht_auch_bei_anderem_titel_und_anderer_firma():
    treffer = find_repost_of_application(
        {"hash": "neu-1", "title": "Etwas ganz anderes",
         "company": "Anderer Name GmbH", "url": URL_ALT},
        [_bewerbung()])
    assert treffer is not None
    assert treffer["match_grund"] == "url_match"
    assert treffer["sicher"] is True
    assert treffer["bewerbung_id"] == "0e2e7262"
    assert treffer["beworben_am"] == "2026-05-12"


def test_1117_tracking_parameter_stoeren_den_vergleich_nicht():
    treffer = find_repost_of_application(
        {"hash": "neu-2", "title": "Etwas ganz anderes",
         "company": "Anderer Name GmbH",
         "url": URL_ALT + "?utm_source=newsletter"},
        [_bewerbung()])
    assert treffer and treffer["match_grund"] == "url_match"


def test_1117_ein_repost_mit_neuer_url_wird_weiter_erkannt():
    """AK 2: die URL ist nie eine NOTWENDIGE Bedingung."""
    treffer = find_repost_of_application(
        {"hash": "neu-3", "title": "Solution Architect PLM (m/w/d)",
         "company": "Societe Beispiel Deutschland GmbH",
         "url": "https://karriere.beispiel.example/careers/jobs/neu-999"},
        [_bewerbung()])
    assert treffer is not None
    assert treffer["match_grund"] != "url_match"
    assert treffer["sicher"] is False


def test_1117_eine_suchseite_ist_kein_beleg():
    """Zwei verschiedene Stellen koennen dieselbe Suchseite als Adresse
    tragen - gleiche URL heisst dort nichts."""
    such = "https://www.linkedin.com/jobs/search/?keywords=plm&location=hamburg"
    assert find_repost_of_application(
        {"hash": "neu-4", "title": "Voellig anderer Titel",
         "company": "Anderer Name GmbH", "url": such},
        [_bewerbung(url=such)]) is None


def test_1117_bei_mehreren_gleichen_urls_zaehlt_die_laufende():
    abgelehnt = _bewerbung(id="aaaaaaaa-0000", status="abgelehnt",
                           applied_at="2026-01-10")
    laufend = _bewerbung(id="bbbbbbbb-0000", status="beworben",
                         applied_at="2026-09-07", job_hash="alt-hash-2")
    for reihenfolge in ([abgelehnt, laufend], [laufend, abgelehnt]):
        treffer = find_repost_of_application(
            {"hash": "neu-5", "title": "X", "company": "Y", "url": URL_ALT},
            reihenfolge)
        assert treffer["bewerbung_id"] == "bbbbbbbb"
        assert treffer["laeuft"] is True


# ══ #1126: der Wortlaut folgt dem Stand ══════════════════════════════════

def test_1126_laufende_bewerbung_sagt_nicht_noch_einmal_bewerben():
    treffer = find_repost_of_application(
        {"hash": "neu-6",
         "title": "Teamleitung Enterprise Applications (m/w/d)",
         "company": "musterbetrieb nord", "url": "https://x.example/kopie"},
        [_bewerbung(company="Musterbetrieb Nord GmbH", status="beworben",
                    title="Teamleitung Enterprise Applications",
                    applied_at="2026-09-07", url="https://x.example/original")])
    assert treffer is not None
    assert treffer["laeuft"] is True
    satz = treffer["warnung"]
    assert "läuft noch" in satz and "nicht noch einmal bewerben" in satz
    assert "07.09.2026" in satz
    # Die Frage nach dem Absagegrund gibt es bei einer laufenden nicht.
    assert "Ablehnungsgrund" not in satz and "Hürde" not in satz
    assert "zweite Chance" not in satz
    assert "07.09.2026" in treffer["kurz"] and "läuft noch" in treffer["kurz"]


def test_1126_gleiche_url_und_laufend_ist_die_klare_ansage():
    treffer = find_repost_of_application(
        {"hash": "neu-7", "title": "Irgendwas", "company": "Irgendwer",
         "url": URL_ALT},
        [_bewerbung(status="beworben", applied_at="2026-09-07")])
    assert treffer["sicher"] is True
    assert treffer["warnung"].startswith(
        "Du hast dich auf diese Anzeige bereits am 07.09.2026 beworben")
    assert "Falls es dieselbe Stelle ist" not in treffer["warnung"]


def test_1126_abgeschlossene_bewerbung_behaelt_den_bisherigen_wortlaut():
    treffer = find_repost_of_application(
        {"hash": "neu-8", "title": "Solution Architect PLM (m/w/d)",
         "company": "Societe Beispiel Deutschland GmbH",
         "url": "https://karriere.beispiel.example/careers/jobs/neu-1"},
        [_bewerbung()])
    assert treffer["laeuft"] is False
    satz = treffer["warnung"]
    assert satz.startswith(
        "Repost-Verdacht: Auf diese Stelle wurde am 12.05.2026 bereits "
        "beworben (Status: Abgelehnt).")
    assert "2026-05-12" not in satz
    assert "Ablehnungsgrund dokumentiert: NEIN" in satz
    assert "echte zweite Chance" in satz


def test_1126_gleiche_url_und_abgelehnt_nennt_die_gleiche_anzeige():
    treffer = find_repost_of_application(
        {"hash": "neu-9", "title": "Etwas anderes", "company": "Anders",
         "url": URL_ALT}, [_bewerbung()])
    assert treffer["warnung"].startswith("Dieselbe Anzeige (gleiche URL): ")
    assert "12.05.2026" in treffer["kurz"] and "Abgelehnt" in treffer["kurz"]


def test_1126_der_grund_steht_im_text_wenn_er_dokumentiert_ist(tmp_db):
    """AK #1117: Treffer samt Bewerbungs-ID, Datum UND Absagegrund."""
    aid = tmp_db.add_application({
        "title": "Solution Architect PLM (m/w/d)", "company": "Société Beispiel",
        "status": "abgelehnt", "applied_at": "2026-05-12", "url": URL_ALT})
    tmp_db.connect().execute(
        "UPDATE applications SET rejection_reason=? WHERE id=?",
        ("Kein Bedarf mehr an der Position", aid))
    tmp_db.connect().commit()
    treffer = find_repost_of_application(
        {"hash": "neu-10", "title": "Etwas anderes", "company": "Anders",
         "url": URL_ALT}, tmp_db.get_applications(), db=tmp_db)
    assert treffer["bewerbung_id"] == aid[:8]
    assert treffer["bewerbung_id_voll"] == aid
    assert treffer["ablehnungsgrund_dokumentiert"] is True
    assert "Kein Bedarf mehr an der Position" in treffer["warnung"]


def test_1126_eigene_bewerbung_ist_keine_wiederholung():
    eigene = _bewerbung(job_hash="dieselbe-stelle")
    assert find_repost_of_application(
        {"hash": "dieselbe-stelle", "title": eigene["title"],
         "company": eigene["company"], "url": URL_ALT}, [eigene]) is None


def test_1126_ohne_eigenen_hash_werden_unverknuepfte_bewerbungen_mitgeprueft():
    """Vorher schloss `"" != ""` alle Bewerbungen ohne Stellen-Verknuepfung
    aus, sobald die Stelle keinen Hash trug."""
    treffer = find_repost_of_application(
        {"title": "Solution Architect PLM (m/w/d)", "company": "Société Beispiel"},
        [_bewerbung(job_hash=None)])
    assert treffer is not None


def test_1126_entwuerfe_zaehlen_nicht():
    assert find_repost_of_application(
        {"hash": "neu-11", "title": "Solution Architect PLM (m/w/d)",
         "company": "Société Beispiel", "url": URL_ALT},
        [_bewerbung(status="in_vorbereitung")]) is None


# ══ #1126: Vermittler in derselben Pruefung ══════════════════════════════

def _vermittler_bewerbung(**felder):
    basis = _bewerbung(company="Vermittler Nord GmbH", title="Berater PLM",
                       status="beworben", applied_at="2026-09-07",
                       url="https://vermittler.example/p/1", job_hash="v-hash")
    basis.update(felder)
    return basis


def test_1126_vermittler_mit_endkunde_im_feld_wird_gefunden():
    bew = _vermittler_bewerbung(endkunde="Beispielwerk AG", notes="")
    assert find_vermittler_bewerbung("Beispielwerk AG", [bew]) is not None


def test_1126_vermittler_mit_akzent_im_text_wird_gefunden():
    """Der Name wird gefaltet - der Rohtext auch, sonst fehlt "société"."""
    bew = _vermittler_bewerbung(
        company="Vermittler Nord (Endkunde: Société Beispiel)")
    assert find_vermittler_bewerbung("Societe Beispiel", [bew]) is not None


def test_1126_fuer_stelle_meldet_den_vermittler_als_eigene_art():
    hinweis = bewerbungs_hinweis.fuer_stelle(
        {"hash": "j1", "title": "Anderer Titel", "company": "Beispielwerk AG"},
        [_vermittler_bewerbung(endkunde="Beispielwerk AG")])
    assert hinweis["art"] == "vermittler"
    assert hinweis["laeuft"] is True and hinweis["sicher"] is False
    assert "Vermittler Nord GmbH" in hinweis["warnung"]
    assert "Prüfen, ob es dieselbe Stelle ist" in hinweis["warnung"]
    assert hinweis["bewerbung_id_voll"] == _vermittler_bewerbung()["id"]


def test_1126_nur_eine_laufende_vermittler_bewerbung_zaehlt():
    hinweis = bewerbungs_hinweis.fuer_stelle(
        {"hash": "j1", "title": "Anderer Titel", "company": "Beispielwerk AG"},
        [_vermittler_bewerbung(endkunde="Beispielwerk AG",
                               status="abgelehnt")])
    assert hinweis is None


def test_1126_wiederholung_hat_vorrang_vor_dem_vermittler():
    treffer = bewerbungs_hinweis.fuer_stelle(
        {"hash": "j1", "title": "Berater PLM", "company": "Beispielwerk AG",
         "url": "https://vermittler.example/p/1"},
        [_vermittler_bewerbung(endkunde="Beispielwerk AG")])
    assert treffer["art"] == "wiederholung"


# ══ Der Dienst ═══════════════════════════════════════════════════════════

def test_1126_als_felder_hat_in_werkzeug_und_dashboard_dieselben_namen():
    hinweis = bewerbungs_hinweis.fuer_stelle(
        {"hash": "j1", "title": "X", "company": "Y", "url": URL_ALT},
        [_bewerbung()])
    felder = bewerbungs_hinweis.als_felder(hinweis)
    assert set(felder) == {"repost_warnung", "repost_details"}
    assert felder["repost_warnung"] == hinweis["warnung"]
    assert "warnung" not in felder["repost_details"]
    assert felder["repost_details"]["bewerbung_id_voll"]


def test_1126_anreichern_haengt_den_hinweis_an_und_zaehlt(tmp_db):
    tmp_db.save_profile({"name": "Test"})
    tmp_db.add_application({
        "title": "Teamleitung Enterprise Applications",
        "company": "Musterbetrieb Nord GmbH", "status": "beworben",
        "applied_at": "2026-09-07", "url": "https://mb.example/original"})
    passend = {"hash": "p1",
               "title": "Teamleitung Enterprise Applications (m/w/d)",
               "company": "Musterbetrieb Nord GmbH",
               "url": "https://mb.example/kopie"}
    andere = {"hash": "p2", "title": "Sachbearbeitung Rechnungswesen",
              "company": "Musterbetrieb Nord GmbH",
              "url": "https://mb.example/rw"}
    assert bewerbungs_hinweis.anreichern(tmp_db, [passend, andere]) == 1
    assert "repost_warnung" in passend
    assert passend["repost_details"]["laeuft"] is True
    assert "repost_warnung" not in andere
    assert "repost_details" not in andere


def test_1126_anreichern_ohne_bewerbungen_ist_ein_stiller_null_lauf(tmp_db):
    job = {"hash": "p1", "title": "X", "company": "Y",
           "url": "https://a.example/1"}
    assert bewerbungs_hinweis.anreichern(tmp_db, [job]) == 0
    assert bewerbungs_hinweis.anreichern(tmp_db, []) == 0


def test_1126_anreichern_stoppt_nie_eine_liste(tmp_db, monkeypatch):
    tmp_db.add_application({"title": "T", "company": "Beispiel AG",
                            "status": "beworben",
                            "url": "https://a.example/1"})

    def kaputt(*args, **kwargs):
        raise RuntimeError("Absicht")

    monkeypatch.setattr(bewerbungs_hinweis, "fuer_stelle", kaputt)
    jobs = [{"hash": "a", "title": "T", "company": "Beispiel AG"}]
    assert bewerbungs_hinweis.anreichern(tmp_db, jobs) == 0


def test_1126_ist_wiederholung_kennt_nur_die_starke_aussage():
    vermittler = [_vermittler_bewerbung(endkunde="Beispielwerk AG")]
    job = {"hash": "j1", "title": "Anderer Titel", "company": "Beispielwerk AG"}
    assert bewerbungs_hinweis.fuer_stelle(job, vermittler)["art"] == "vermittler"
    assert bewerbungs_hinweis.ist_wiederholung(job, vermittler) is False
    assert bewerbungs_hinweis.ist_wiederholung(
        {"hash": "j2", "title": "X", "company": "Y", "url": URL_ALT},
        [_bewerbung()]) is True
