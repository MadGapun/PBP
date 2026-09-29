"""#1120 — der Google-Alert-Import an ECHTEN Mails.

Die erste Fassung (#1068) war nach einer Beschreibung gebaut. An neun
echten Mails (21.–29.09.2026, 25 Treffer) lieferte sie null Treffer:
sechs Mails wurden gar nicht erkannt (Betreff in der Einzahl), und der
echte Textteil hat eine andere Form als ihr Fixture.

Das Fixture hier ist aus einer echten Mail gebaut: fiktive Firma
(`engineering-partner`), minimaler Kopf ohne Adressen und Kennungen,
Google-Kennungen durch Dummies ersetzt, die Karten-Links mit einem
fiktiven, aber genauso kodierten Ziel. Die MIME-Struktur ist erhalten —
LF-Rahmen wie in Thunderbirds Postfach, text/plain als base64 mit
`format=flowed; delsp=yes` und CRLF, text/html als quoted-printable —,
damit jeder Test ueber `parse_eml()` laeuft, den Weg der echten Mails.
"""
import base64
import email
import importlib
import os
import shutil
import sys
import tempfile
import zlib
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from bewerbungs_assistent.services import google_alert as ga  # noqa: E402
from bewerbungs_assistent.services import weiterverbreiter as wv  # noqa: E402
from bewerbungs_assistent.services.email_service import parse_eml  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "google_alert" / \
    "einzahl_weiterverbreiter.eml"
HEUTE = date(2026, 9, 29)
KARTEN_ZIEL = ("https://www.google.de/search?q=PLM+Hamburg&ibp=htl;jobs&rciv=jb"
               "&clksrc=alertsemail&hl=de&gl=DE#fpstate=tldetail&htivrt=jobs"
               "&htidocid=FIXTURE-DOCID-1")
TITEL = "PLM Dokumenten- und Prozessmanager (m/w/d) – Aufbau & Strukturierung"


@pytest.fixture(scope="module")
def mail():
    return parse_eml(str(FIXTURE))


# ══ Das Fixture ist und bleibt eine echte Mail ══════════════════════

def test_1120_das_fixture_hat_die_form_der_echten_mail():
    """Wer das Fixture "vereinfacht", baut den Fehler aus #1068 nach."""
    roh_bytes = FIXTURE.read_bytes()
    # LF-Rahmen wie im Thunderbird-Postfach. Stellt Git die Zeilenenden
    # um (core.autocrlf), faellt es hier auf — dagegen steht die Regel in
    # .gitattributes.
    assert b"\r\n" not in roh_bytes
    msg = email.message_from_bytes(roh_bytes)
    teile = {p.get_content_type(): p for p in msg.walk()
             if p.get_content_maintype() == "text"}
    text = teile["text/plain"]
    assert text["Content-Transfer-Encoding"] == "base64"
    assert text.get_param("format") == "flowed"
    assert text.get_param("delsp") == "yes"
    assert teile["text/html"]["Content-Transfer-Encoding"] == "quoted-printable"
    roh = text.get_payload(decode=True).decode("utf-8")
    assert "\r\n" in roh
    # Mindestens ein weicher Umbruch (Zeile endet mit Leerzeichen).
    assert any(z.endswith(" ") and z.strip() for z in roh.split("\r\n"))
    assert "Time icon" in roh and "Work icon" in roh


# ══ Defekt A: der Betreff in der Einzahl ═══════════════════════════

@pytest.mark.parametrize("betreff", [
    '1 neuer Job für "PLM Hamburg" - 29. Sept.',
    '2 neue Jobs für "PLM Hamburg" - 23. Sept.',
    '10 neue Jobs für "PLM OR PDM Homeoffice" - 21. Sept.',
])
def test_1120_einzahl_und_mehrzahl_werden_erkannt(betreff):
    assert ga.ist_google_jobmail("notify-noreply@google.com", betreff)


def test_1120_die_echte_einzahl_mail_wird_erkannt(mail):
    from bewerbungs_assistent.services import newsletter_service as ns
    assert mail["subject"].startswith("1 neuer Job für")
    befund = ns.erkennung(mail, None)
    assert befund == {"label": "Google Jobs", "erkannt_ueber": "google_alert"}


def test_1120_kontowarnung_mit_einzahl_betreff_bleibt_draussen():
    assert not ga.ist_google_jobmail(
        "noreply-accounts@google.com", '1 neuer Job für "PLM" - 29. Sept.')


# ══ Defekt B: die echte Form, auf beiden Wegen ═════════════════════

def _pruefe_treffer(t):
    assert t["titel"] == TITEL
    assert t["firma"] == "engineering-partner"
    assert t["ort"] == "Pinneberg"
    assert t["portal"] == "Move Collective Jobs"
    assert t["kartendatum"] == "2026-09-28"
    assert t["vertragsart"] == "Vollzeit"


def test_1120_die_echte_mail_wird_aus_dem_html_gelesen(mail):
    treffer = ga.parse_alert(mail["body_text"], heute=HEUTE,
                             html=mail["body_html"])
    assert len(treffer) == 1
    _pruefe_treffer(treffer[0])
    assert treffer[0]["gelesen_aus"] == "html"


def test_1120_der_textteil_allein_traegt_auch(mail):
    """Umbrueche zusammenfuegen, Leerzeilen ueberspringen, Symbole weg."""
    treffer = ga.parse_alert(mail["body_text"], heute=HEUTE)
    assert len(treffer) == 1
    _pruefe_treffer(treffer[0])
    assert treffer[0]["gelesen_aus"] == "text"


def test_1120_text_und_html_sagen_dasselbe(mail):
    """Die Messung aus #1120 (25 von 25 gleich), hier am Fixture gehalten."""
    h = ga.parse_alert(mail["body_text"], heute=HEUTE, html=mail["body_html"])
    t = ga.parse_alert(mail["body_text"], heute=HEUTE)
    for feld in ("titel", "firma", "ort", "portal", "kartendatum",
                 "vertragsart", "weiterverbreiter"):
        assert h[0][feld] == t[0][feld], feld


@pytest.mark.parametrize("karte,datum", [
    ("31. Mai", "2026-05-31"),
    ("24. März", "2026-03-24"),
    ("3. Juli", "2026-07-03"),
])
def test_1120_monat_ohne_punkt_klebt_im_html_an_der_vertragsart(mail, karte, datum):
    """Gemessen: im HTML stehen Datum und Vertragsart in zwei spans und
    kleben ohne Trenner aneinander ("31. MaiVollzeit"). Ein Monat ohne
    Punkt machte daraus die Vertragsart "it"."""
    html = mail["body_html"].replace(">28. Sept.<", f">{karte}<")
    assert html != mail["body_html"]
    t = ga.parse_alert("", heute=HEUTE, html=html)[0]
    assert (t["kartendatum"], t["vertragsart"]) == (datum, "Vollzeit")


def test_1120_weicher_umbruch_wird_zusammengefuegt():
    """RFC 3676, delsp=yes: das letzte Leerzeichen ist nur die Markierung."""
    zeilen = ga._zeilen_aus_text(
        "Senior Consultant PLM (m/w/d)  \r\nin Hamburg\r\nMusterfirma\r\n")
    assert [z for z, _ in zeilen] == [
        "Senior Consultant PLM (m/w/d) in Hamburg", "Musterfirma"]


# Die gemessenen Formen, mit fiktiven Firmen: Leerzeilen, Logo-Zeile,
# Symbol-Praefixe, eine Karte ohne Vertragsart, Orte mit PLZ und Adresse.
ECHTE_FORM = (
    "PLM Hamburg\r\n\r\nHamburg\r\n\r\n\r\n\r\n"
    "Logo\r\n\r\n\r\n"
    "Master Data / PLM Specialist (m/f/d)\r\n"
    "Halbleiterwerk Nord GmbH\r\n\r\n"
    "Hamburg, Deutschland\r\n\r\n"
    "über Bundesagentur Für Arbeit\r\n\r\n"
    "Time icon 11. Aug.\r\n\r\n\r\n\r\n"
    "S\r\n\r\n\r\n"
    "Solution Architect PLM (m/w/d)\r\n"
    "Systemhaus Nord GmbH\r\n\r\n"
    "22297, Hamburg-Nord, Deutschland\r\n\r\n"
    "über Women For Hire- Job Board\r\n\r\n"
    "Time icon 24. März Work icon Vollzeit\r\n\r\n\r\n"
    "Logo\r\n\r\n\r\n"
    "PLM Engineer (m/w/d)\r\n"
    "Beispiel AG\r\n\r\n"
    "Beispielstandort, Musterstr. 1-3, Hamburg, Deutschland\r\n\r\n"
    "über Beispiel Karriere\r\n\r\n"
    "Time icon 23. Sept. Work icon Auftragnehmer\r\n\r\n"
    "Forward icon Stellenanzeigen ansehen\r\n"
)


def test_1120_echte_form_mit_mehreren_karten():
    treffer = ga.parse_alert(ECHTE_FORM, heute=HEUTE)
    assert [t["firma"] for t in treffer] == [
        "Halbleiterwerk Nord GmbH", "Systemhaus Nord GmbH", "Beispiel AG"]
    assert [t["kartendatum"] for t in treffer] == [
        "2026-08-11", "2026-03-24", "2026-09-23"]
    assert [t["vertragsart"] for t in treffer] == ["", "Vollzeit", "Auftragnehmer"]


@pytest.mark.parametrize("zeile,ort", [
    ("Hamburg, Deutschland", "Hamburg"),
    ("22297, Hamburg-Nord, Deutschland", "Hamburg-Nord"),
    ("Beispielstandort, Musterstr. 1-3, Hamburg, Deutschland", "Hamburg"),
    ("22297 Hamburg, Deutschland", "Hamburg"),
    ("Deutschland", "Deutschland"),
])
def test_1120_ort_ohne_plz_und_strasse(zeile, ort):
    assert ga._ort(zeile) == ort


def test_1120_die_alte_form_wird_weiter_gelesen():
    """Die Form des #1068-Fixtures bleibt lesbar."""
    alt = ("Titel A (m/w/d)\nMusterfirma\nHamburg, Deutschland\n"
           "über XING\n23. Apr.Vollzeit\n")
    t = ga.parse_alert(alt, heute=HEUTE)[0]
    assert (t["titel"], t["ort"], t["kartendatum"], t["vertragsart"]) == (
        "Titel A (m/w/d)", "Hamburg", "2026-04-23", "Vollzeit")


# ══ Links: nur als Google-Link, nie als Stellen-URL ═════════════════

def test_1120_der_karten_link_wird_offline_dekodiert(mail):
    t = ga.parse_alert(mail["body_text"], heute=HEUTE, html=mail["body_html"])[0]
    assert t["google_link"] == KARTEN_ZIEL


def test_1120_nur_eine_google_suche_zaehlt_als_google_link():
    def redirect(ziel):
        r = base64.urlsafe_b64encode(zlib.compress(ziel.encode())).decode()
        return ("https://notifications.googleapis.com/email/redirect?t=x&r="
                + r.rstrip("=") + "&s=y")
    assert ga.google_link(redirect(KARTEN_ZIEL)) == KARTEN_ZIEL
    assert ga.google_link(redirect(
        "https://myaccount.google.com/communication-preferences/unsubscribe")) == ""
    assert ga.google_link(redirect("https://www.google.evil.example/search?q=x")) == ""
    # Google, aber keine Suche bzw. kein https: auch kein Google-Link.
    assert ga.google_link(redirect("https://www.google.de/maps?q=x")) == ""
    assert ga.google_link(redirect("http://www.google.de/search?q=x")) == ""
    assert ga.google_link("https://notifications.googleapis.com/email/redirect?r=kaputt") == ""
    assert ga.google_link("") == ""


# ══ Erweiterung C: Weiterverbreiter ═════════════════════════════════

def test_1120_weiterverbreiter_werden_erkannt():
    assert wv.ist_weiterverbreiter("Move Collective Jobs")
    assert wv.ist_weiterverbreiter("über  move collective jobs ")
    assert not wv.ist_weiterverbreiter("XING")
    assert not wv.ist_weiterverbreiter("")


def test_1120_jeder_weiterverbreiter_hat_einen_beleg():
    """Pflegeregel: kein Eintrag ohne Messung mit Datum."""
    import re
    for name, beleg in wv.WEITERVERBREITER.items():
        assert name == name.lower().strip(), name
        assert re.search(r"\d{2}\.\d{2}\.\d{4}", beleg), name


def test_1120_beim_weiterverbreiter_ist_das_datum_unbekannt(mail):
    t = ga.parse_alert(mail["body_text"], heute=HEUTE, html=mail["body_html"])[0]
    assert t["weiterverbreiter"] is True
    assert t["kartendatum"] == "2026-09-28"
    assert t["veroeffentlicht_am"] == ""


def test_1120_das_anhaengsel_der_kopie_faellt_aus_dem_titel():
    assert ga._titel(
        "Titel (m/w/d). Job in Musterstadt Move Collective Jobs",
        "Move Collective Jobs") == "Titel (m/w/d)"
    # Ohne das Portal am Ende bleibt der Titel, wie er ist.
    assert ga._titel("Senior Consultant PLM (m/w/d) in Hamburg",
                     "LinkedIn") == "Senior Consultant PLM (m/w/d) in Hamburg"


# ══ Der Weg durch den Ingest ════════════════════════════════════════

@pytest.fixture
def db():
    tmpdir = tempfile.mkdtemp(prefix="pbp_1120_")
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


def test_1120_der_browser_weg_kennt_dieselbe_liste(db):
    """Eine Frage, eine Antwort: auch `google_jobs_url` (#1067) nennt die
    Weiterverbreiter — aus derselben Liste wie der Alert-Import."""
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import jobs, mit_katalog
    mcp = FastMCP("test")
    jobs.register(mit_katalog(mcp, db), db, logging.getLogger("test"))

    async def _run():
        tool = await mcp.get_tool("google_jobs_url")
        res = await tool.run({"keyword": "PLM"})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    erg = erg.get("result", erg) if set(erg) == {"result"} else erg
    assert erg["weiterverbreiter"] == sorted(wv.WEITERVERBREITER)
    assert "move collective jobs" in erg["weiterverbreiter"]
    assert "Original beim Arbeitgeber" in erg["weiterverbreiter_hinweis"]


def test_1120_die_echte_mail_kommt_im_bestand_an(db, mail):
    from bewerbungs_assistent.services import newsletter_service as ns
    quelle = ns.erkennung(mail, db)
    res = ns.verarbeite_newsletter(db, mail, quelle["label"])
    assert res["status"] == "uebernommen"
    assert res["gefunden"] == 1
    assert res["ebene"] == "google-alert-html"
    assert res["weiterverbreiter"] == 1
    stellen = {j["title"]: j for j in db.get_active_jobs()}
    stelle = stellen[TITEL]
    assert stelle["company"] == "engineering-partner"
    assert not (stelle.get("url") or "")
    assert not (stelle.get("veroeffentlicht_am") or "")
    notiz = stelle.get("research_notes") or ""
    assert "Original beim Arbeitgeber suchen (engineering-partner)" in notiz
    assert "Kopierdatum" in notiz
    assert "Google-Link (öffnet oft nur die Liste): " + KARTEN_ZIEL in notiz
