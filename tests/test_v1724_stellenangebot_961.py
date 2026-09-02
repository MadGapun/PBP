"""Tests fuer v1.7.24 — #961: Stellenangebote in der Korrespondenz.

Eine Recruiter-Mail mit vollstaendiger Stellenbeschreibung wurde als
`doc_type='sonstiges'` klassifiziert. Das Routing leitete daraus
`noop_korrespondenz_abschliessen` ab, mit dem Hinweis "Manuell
sichten". Richtig gewesen waere `recruiter_anfrage`, deren Aktion genau
den noetigen Weg beschreibt.

Der teure Teil ist nicht die Fehlklassifikation, sondern was danach
passiert: `dokumente_korrespondenz_abschliessen` setzt genau diese
Dokumente sammelweise auf `angewendet`. Eine fehlklassifizierte
Stellenanfrage wird damit stillschweigend abgeschlossen, ohne dass je
eine Stelle im System entsteht — aus dem Analyse-Plan verschwunden, als
erledigt gefuehrt. Derselbe Ausfallmodus wie #833: kein Fehler, der
auffaellt, sondern einer, der wie Erfolg aussieht.
"""
import pytest

from bewerbungs_assistent.services.stellenangebot_erkennung import (
    MINDEST_MERKMALE,
    gefundene_merkmale,
    ist_stellenangebot,
)

# Der belegte Fall, in Struktur und Umfang nachgebildet.
RECRUITER_MAIL = """Guten Tag,

anbei die Details zu unserer aktuellen Vakanz.

Position: Senior PLM Consultant (m/w/d)
Referenznummer: PRJ-2026-4471
Startdatum: 01.11.2026
Vertragsmodell: Festanstellung
Verguetungsspanne: 85.000 - 105.000 EUR p.a.
Arbeitsort: Hamburg, hybrid

Ihre Aufgaben: Betreuung und Weiterentwicklung der PLM-Landschaft,
Steuerung externer Dienstleister, Migration bestehender Strukturen.

Anforderungen: abgeschlossenes Studium, mehrjaehrige Berufserfahrung.

Mit freundlichen Gruessen
"""

ABSAGE = """Sehr geehrter Herr,

vielen Dank fuer Ihre Bewerbung als Senior Consultant am Standort
Hamburg. Leider muessen wir Ihnen mitteilen, dass wir uns fuer eine
andere Kandidatin entschieden haben.
"""

BELANGLOS = "Hallo, anbei wie besprochen die Unterlagen. Viele Gruesse"


# ── AK 1: am Inhalt erkennen, nicht am Dateinamen ────────────────────

def test_961_recruiter_mail_wird_erkannt():
    """Der gemeldete Fall."""
    treffer, warum = ist_stellenangebot(RECRUITER_MAIL, "Nachricht.eml")
    assert treffer is True, warum
    assert warum["rolle_erkannt"] is True
    assert len(warum["merkmale"]) >= MINDEST_MERKMALE


def test_961_alle_fuenf_merkmale_werden_gefunden():
    """Die Merkmalsliste aus den Akzeptanzkriterien, einzeln geprueft."""
    gefunden = set(gefundene_merkmale(RECRUITER_MAIL))
    assert gefunden == {"referenznummer", "verguetung", "arbeitsort",
                        "startdatum", "aufgabenliste"}, gefunden


def test_961_absage_ist_kein_stellenangebot():
    """Die wichtigere Richtung. Eine Absage nennt oft dieselbe Rolle und
    denselben Standort — sie darf nicht zur Recruiter-Anfrage werden."""
    treffer, warum = ist_stellenangebot(ABSAGE)
    assert treffer is False, warum


def test_961_belanglose_mail_ist_kein_stellenangebot():
    assert ist_stellenangebot(BELANGLOS)[0] is False


def test_961_ein_einzelnes_merkmal_genuegt_nicht():
    """'Standort: Hamburg' steht auch in einer Terminbestaetigung."""
    text = "Guten Tag Herr Consultant, unser Standort: Hamburg. Gruesse"
    assert ist_stellenangebot(text)[0] is False


def test_961_ohne_rollenbezeichnung_kein_treffer():
    """Zwei Merkmale ohne Rolle sind eine Rechnung, keine Ausschreibung."""
    text = ("Referenznummer: 4711\nArbeitsort: Hamburg\n"
            "Bitte begleichen Sie den Betrag.")
    treffer, warum = ist_stellenangebot(text)
    assert treffer is False, warum
    assert warum["rolle_erkannt"] is False


def test_961_begruendung_nennt_die_merkmale():
    """Eine Fehlklassifikation muss nachvollziehbar bleiben, statt
    wieder still zu passieren."""
    _, warum = ist_stellenangebot(RECRUITER_MAIL)
    assert "referenznummer" in warum["begruendung"]


def test_961_leerer_text_bricht_nicht():
    assert ist_stellenangebot("")[0] is False
    assert ist_stellenangebot(None)[0] is False
    assert gefundene_merkmale(None) == []


def test_961_erkennung_haengt_im_detektor():
    """Sie muss GANZ HINTEN haengen — Absage, Einladung und
    Bestaetigung behalten Vorrang."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "dashboard.py").read_text(encoding="utf-8")
    i_erk = quelle.index("from .services.stellenangebot_erkennung import")
    i_absage = quelle.index('return "absage"')
    assert i_absage < i_erk, "Absage muss vor der Inhaltserkennung greifen"


def test_961_detektor_liefert_recruiter_anfrage():
    """Ende zu Ende durch den echten Detektor."""
    from bewerbungs_assistent.dashboard import _detect_doc_type
    assert _detect_doc_type("Nachricht.eml", RECRUITER_MAIL) == "recruiter_anfrage"


# ── AK 4: 'sonstiges' wird nicht mehr still abgeschlossen ────────────

def test_961_sonstiges_nicht_mehr_in_der_korrespondenz_whitelist():
    """Der teuerste Teil: eine fehlklassifizierte Stellenanfrage wurde
    sammelweise als erledigt abgehakt."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "tools" / "dokumente.py").read_text(encoding="utf-8")
    block = quelle[quelle.index("_KORRESPONDENZ_DOC_TYPES = {"):]
    block = block[:block.index("}")]
    assert '"sonstiges"' not in block, block


def test_961_ausgeklammerte_werden_gemeldet():
    """Stillschweigend weglassen waere derselbe Fehler in die andere
    Richtung — der Nutzer wuesste nicht, dass da noch etwas liegt."""
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "tools" / "dokumente.py").read_text(encoding="utf-8")
    assert "nicht_enthalten_sonstiges" in quelle
    assert "trotzdem_abschliessen" in quelle


# ── AK 2 und 3: Typen ohne Handler ───────────────────────────────────

def test_961_stellenanzeige_und_bewerbungsantwort_haben_handler():
    from bewerbungs_assistent.services.document_handlers import KNOWN_TYPES
    for typ in ("stellenanzeige", "bewerbungsantwort"):
        assert typ in KNOWN_TYPES, typ
        assert KNOWN_TYPES[typ]["claude_action"].strip()


def test_961_email_ist_als_altlast_benannt():
    """'email' ist kein Dokumenttyp, sondern ein Transportweg — er
    beschreibt den Inhalt gar nicht."""
    from bewerbungs_assistent.services.document_handlers import (
        ALTLAST_TYPEN, KNOWN_TYPES)
    assert "email" in ALTLAST_TYPEN
    assert "email" not in KNOWN_TYPES
    assert ALTLAST_TYPEN["email"] == "sonstiges"


def test_961_nachziehen_ist_dry_run_by_default():
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "src" /
              "bewerbungs_assistent" / "tools" / "dokumente.py").read_text(encoding="utf-8")
    assert "def dokument_typen_nachziehen(dry_run: bool = True" in quelle


def test_961_nachziehen_ordnet_altlast_neu_zu(tmp_db):
    """Ende zu Ende: ein als 'email' abgelegtes Stellenangebot wird
    recruiter_anfrage, ein nicht zuordenbares wird 'sonstiges' und
    bleibt damit sichtbar."""
    from bewerbungs_assistent.server import mcp  # noqa: F401
    from bewerbungs_assistent.dashboard import _detect_doc_type

    # Der Weg, den das Tool geht — hier ohne MCP-Wrapper geprueft.
    assert _detect_doc_type("mail.eml", RECRUITER_MAIL) == "recruiter_anfrage"
    assert _detect_doc_type("mail.eml", BELANGLOS) is None
