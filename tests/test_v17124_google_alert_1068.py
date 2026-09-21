"""#1068 — Google-Jobs-Benachrichtigungen aus dem Postfach.

Der Melder hat die ersten beiden echten Mails vermessen (21.09.2026,
17 Treffer) und ausdruecklich darum gebeten, das Muster erst DANACH zu
bauen. Alles hier steht auf diesen Messungen:

* Absender `notify-noreply@google.com`, Betreff
  `<N> neue Jobs für "<Suchanfrage>" - <Datum>`
* Kontowarnungen kommen von `no-reply@accounts.google.com` bzw.
  `noreply-accounts@google.com`, Zahlungsmails von
  `payments-noreply@google.com` — **dieselbe Domain**. Ein Muster auf
  `google.com` haette sie als Job-Newsletter gelesen.
* Alle Links zeigen auf `notifications.googleapis.com/email/redirect`;
  die Stellen stehen im Textteil.
* Veroeffentlichungsdatum und Vertragsart kleben aneinander
  ("23. Apr.Vollzeit").
* Die Treffer sind nur fuer DIESEN Alert neu — beim ersten Versand
  lagen sie zwischen 16. Januar und 12. September.
"""
import importlib
import os
import shutil
import sys
import tempfile
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import google_alert as ga  # noqa: E402

# Nachgebaut nach der Beschreibung des Melders. Firmennamen fiktiv.
MAIL = """Alerts für Stellen

PLM Project Manager (m/w/d)
Musterbetrieb Nord GmbH
Hamburg, Deutschland
über Musterbetrieb Karriere
23. Apr.Vollzeit

Senior PDM Consultant - ['Vollzeit', 'Homeoffice']
Musterwerk Sued AG
Hamburg, Deutschland
über XING
12. Sept.Vollzeit

Stellenanzeigen ansehen
Verwalten
Abbestellen
"""

BETREFF = '10 neue Jobs für "PLM Hamburg" - 21. Sept.'


# ══ Erkennung: die richtige Mail, und nur die ═══════════════════════

def test_1068_die_jobmail_wird_erkannt():
    assert ga.ist_google_jobmail("notify-noreply@google.com", BETREFF)
    assert ga.ist_google_jobmail(
        'Alerts für Stellen <notify-noreply@google.com>', BETREFF)


@pytest.mark.parametrize("sender,betreff", [
    ("no-reply@accounts.google.com", "Sicherheitswarnung"),
    ("noreply-accounts@google.com",
     "Kritische Sicherheitswarnung für dein Konto"),
    ("payments-noreply@google.com", "Deine Rechnung"),
    # Auch mit einem Betreff, der nach Jobs klingt: der Absender
    # entscheidet mit.
    ("noreply-accounts@google.com", '10 neue Jobs für "PLM" - 21. Sept.'),
])
def test_1068_googles_andere_mails_werden_nicht_erkannt(sender, betreff):
    """AK 4, Gegenrichtung. Das war das ausdrueckliche Risiko im Issue."""
    assert not ga.ist_google_jobmail(sender, betreff)


def test_1068_ein_gefaelschter_anzeigename_traegt_nicht():
    """Der isolierende Fall fuer die Sperrliste.

    Die Gegenprobe hat sie zuerst als stumm gemeldet — zu Recht: fuer
    die gemessenen Absender greift schon die Pruefung auf die echte
    Adresse. Sie entscheidet erst, wenn beides in derselben Zeile steht,
    und genau so sieht ein gefaelschter Anzeigename aus. Ohne sie wuerde
    PBP eine Phishing-Mail als Stellen-Newsletter lesen und ihre Links
    verarbeiten.
    """
    gefaelscht = ('"Google Jobs notify-noreply@google.com" '
                  "<noreply-accounts@google.com>")
    assert not ga.ist_google_jobmail(gefaelscht, BETREFF)


def test_1068_der_richtige_absender_mit_falschem_betreff_zaehlt_nicht():
    """Google benachrichtigt auch ueber Kalender und Drive."""
    assert not ga.ist_google_jobmail(
        "notify-noreply@google.com", "Erinnerung an deinen Termin")


def test_1068_die_suchanfrage_kommt_aus_dem_betreff():
    assert ga.suchanfrage(BETREFF) == "PLM Hamburg"
    assert ga.suchanfrage(
        '7 neue Jobs für "PLM OR PDM Homeoffice" - 21. Sept.'
    ) == "PLM OR PDM Homeoffice"
    assert ga.suchanfrage("ohne Anfuehrungszeichen") == ""


# ══ Der Textteil ════════════════════════════════════════════════════

def test_1068_liest_titel_firma_ort_und_portal():
    treffer = ga.parse_alert(MAIL, heute=date(2026, 9, 21))
    assert len(treffer) == 2
    a = treffer[0]
    assert a["titel"] == "PLM Project Manager (m/w/d)"
    assert a["firma"] == "Musterbetrieb Nord GmbH"
    assert a["ort"] == "Hamburg"
    assert a["portal"] == "Musterbetrieb Karriere"


def test_1068_der_listentext_faellt_aus_dem_titel():
    """Gemessen: manche Titel tragen Python-Listentext aus Googles Quelle."""
    treffer = ga.parse_alert(MAIL, heute=date(2026, 9, 21))
    assert treffer[1]["titel"] == "Senior PDM Consultant"


def test_1068_datum_und_vertragsart_werden_getrennt():
    """Sie kleben in der Mail ohne Trenner aneinander."""
    treffer = ga.parse_alert(MAIL, heute=date(2026, 9, 21))
    assert treffer[0]["veroeffentlicht_am"] == "2026-04-23"
    assert treffer[0]["vertragsart"] == "Vollzeit"
    assert treffer[1]["veroeffentlicht_am"] == "2026-09-12"


def test_1068_ein_datum_in_der_zukunft_gehoert_ins_vorjahr():
    """Die Mail nennt kein Jahr, und ein Alert traegt Anzeigen bis acht
    Monate zurueck."""
    mail = ("Titel\nMusterbetrieb GmbH\nHamburg, Deutschland\n"
            "über XING\n12. Dez.Vollzeit\n")
    treffer = ga.parse_alert(mail, heute=date(2026, 9, 21))
    assert treffer[0]["veroeffentlicht_am"] == "2025-12-12"


def test_1068_ohne_treffer_block_kommt_nichts():
    assert ga.parse_alert("Nur Text ohne Stellen") == []
    assert ga.parse_alert("") == []


# ══ Der Weg durch den Ingest ════════════════════════════════════════

@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17124_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    d = _db_mod.Database()
    d.initialize()
    assert str(tmpdir) in str(d.db_path), f"DB nicht isoliert: {d.db_path}"
    d.save_profile({"name": "Test"})
    yield d
    d.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _mail(sender="notify-noreply@google.com", betreff=BETREFF, text=MAIL):
    return {"sender": sender, "subject": betreff, "body_text": text,
            "body_html": '<a href="https://notifications.googleapis.com/'
                         'email/redirect?x=1">Ansehen</a>'}


def test_1068_der_ingest_erkennt_die_quelle(db):
    from bewerbungs_assistent.services import newsletter_service as ns
    befund = ns.erkennung(_mail(), db)
    assert befund["label"] == "Google Jobs"
    assert befund["erkannt_ueber"] == "google_alert"


def test_1068_sicherheitsmail_wird_nicht_als_newsletter_erkannt(db):
    """AK 4 auf der Ebene, auf der es zaehlt."""
    from bewerbungs_assistent.services import newsletter_service as ns
    befund = ns.erkennung(
        _mail(sender="noreply-accounts@google.com",
              betreff="Kritische Sicherheitswarnung", text="Warnung."), db)
    assert befund is None


def test_1068_die_stellen_kommen_an(db):
    """AK 3: extrahiert und uebernommen — obwohl kein Link verwertbar ist."""
    from bewerbungs_assistent.services import newsletter_service as ns
    res = ns.verarbeite_newsletter(db, _mail(), "Google Jobs")
    assert res["status"] == "uebernommen"
    assert res["gefunden"] == 2
    assert res["ebene"] == "google-alert-text"
    assert res["suchanfrage"] == "PLM Hamburg"
    assert "XING" in res["portale"]
    titel = {j["title"] for j in db.get_active_jobs()}
    assert "PLM Project Manager (m/w/d)" in titel


def test_1068_das_veroeffentlichungsdatum_kommt_mit(db):
    """Sonst sehen Monate alte Anzeigen taufrisch aus (#949)."""
    from bewerbungs_assistent.services import newsletter_service as ns
    ns.verarbeite_newsletter(db, _mail(), "Google Jobs")
    stellen = {j["title"]: j for j in db.get_active_jobs()}
    assert stellen["PLM Project Manager (m/w/d)"]["veroeffentlicht_am"] \
        == "2026-04-23"


def test_1068_das_ursprungsportal_steht_an_der_stelle(db):
    """Der Punkt aus "Angrenzend": dieselbe Stelle kommt oft parallel
    ueber XING oder LinkedIn herein, die PBP schon kennt."""
    from bewerbungs_assistent.services import newsletter_service as ns
    ns.verarbeite_newsletter(db, _mail(), "Google Jobs")
    stellen = {j["title"]: j for j in db.get_active_jobs()}
    notiz = stellen["Senior PDM Consultant"].get("research_notes") or ""
    assert "XING" in notiz
    assert "PLM Hamburg" in notiz


def test_1068_dieselbe_stelle_zweimal_bleibt_eine(db):
    """Gemessen: 11 von 17 Treffern lagen schon in PBP. Dubletten sind
    hier der Normalfall, nicht die Ausnahme."""
    from bewerbungs_assistent.services import newsletter_service as ns
    ns.verarbeite_newsletter(db, _mail(), "Google Jobs")
    vorher = len(db.get_active_jobs())
    zweite = ns.verarbeite_newsletter(db, _mail(), "Google Jobs")
    assert len(db.get_active_jobs()) == vorher
    assert zweite["neu"] == 0
    assert zweite["bereits_bekannt"] == 2


def test_1068_keine_erfundene_url(db):
    """Alle Links der Mail sind Google-Redirects, und wohin sie
    aufloesen, ist nicht gemessen. Eine erfundene Portal-URL waere
    schlimmer als keine."""
    from bewerbungs_assistent.services import newsletter_service as ns
    ns.verarbeite_newsletter(db, _mail(), "Google Jobs")
    for j in db.get_active_jobs():
        assert not (j.get("url") or "")


# ══ Der PII-Pruefer kennt zusammengesetzte Automaten-Adressen ═══════

def test_1068_automaten_adressen_sind_keine_kontaktdaten():
    """Beim Commit gefunden: der Pruefer meldete
    `notify-noreply@google.com` als personenbezogen.

    Er kennt die Kategorie laengst — sein Docstring nennt sogar diesen
    Anwendungsfall ("Absender-Erkennung fuer Newsletter und
    Portal-Benachrichtigungen") — verglich aber EXAKT. Zusammengesetzte
    Lokalteile fielen durch, und das sind genau die, die PBP fuer die
    Erkennung dokumentieren muss. Um den Pruefer herumzuarbeiten waere
    die falsche Antwort gewesen (v1.7.82 MERKE 10).
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    from scrub_pii import _is_safe_email
    for adresse in (ga.ABSENDER, *ga.KEINE_JOBMAIL):
        assert _is_safe_email(adresse), adresse


def test_1068_eine_person_bleibt_eine_person():
    """Die Gegenrichtung, und der Grund fuer den Vergleich ueber
    BESTANDTEILE statt per Teilstring."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from scrub_pii import _is_safe_email
    assert not _is_safe_email("hans.noreplyer@musterbetrieb-nord.de")
    assert not _is_safe_email("vorname.name@musterbetrieb-nord.de")
    assert _is_safe_email("bewerbung.noreply.team@musterbetrieb-nord.de")
