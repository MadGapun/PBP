"""Tests fuer v1.7.53 — der PII-Pruefer fand nur die wortgleiche Fassung.

Gefunden am 09.09.2026 bei der Arbeit an #956/#957. Beide Issues nennen
eine Firma aus dem echten Bewerbungsbestand — und `issue_text_pruefen`,
das genau solche Namen finden soll, meldete **"sauber"**.

Die Ursache stand in einer Zeile:

    muster = _WORTGRENZE_VOR + re.escape(name) + _WORTGRENZE_NACH

Verglichen wurde die **vollstaendige gespeicherte Zeichenkette**. Steht
eine Firma in der Datenbank als "X (Y)" — und so kommen Namen aus
LinkedIn-Importen regelmaessig an —, dann findet der Pruefer weder "X"
noch "Y". Gemessen:

    "X (Y)"          -> Treffer
    "X"              -> KEIN Treffer
    "Y"              -> KEIN Treffer
    "X Hamburg GmbH" -> KEIN Treffer

**Und genau die kurze Form schreibt ein Mensch in einen Fehlerbericht.**

Das ist woertlich die Lehre aus #929 — *ein Falsch-negativ in einem
Schutzwerkzeug ist der teuerste Fehlertyp* — zum zweiten Mal
eingetreten, und diesmal in dem Werkzeug, das die gepflegte Namensliste
im Repo ABLOESEN sollte (#946). Der Pruefer haette die Namen gefunden;
er hat nur an der falschen Zeichenkette gesucht.

Die Gegenrichtung wiegt genauso schwer (v1.7.24 MERKE 2): eine zu kurze
oder zu gewoehnliche Variante macht den Pruefer unbrauchbar, weil er
dann bei jedem zweiten Satz anschlaegt — und ein Pruefer, dem niemand
mehr glaubt, schuetzt gar nicht. Beide Richtungen stehen deshalb hier.
"""
import importlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.services.pii_bestand import (  # noqa: E402
    MIN_VARIANTENLAENGE, schreibvarianten,
)


@pytest.fixture
def db():
    """QA-Isolation (HART): eigenes Temp-Verzeichnis, hart geprueft."""
    tmpdir = tempfile.mkdtemp(prefix="pbp_pii_")
    alt = os.environ.get("BA_DATA_DIR")
    os.environ["BA_DATA_DIR"] = tmpdir
    from bewerbungs_assistent import database as _database
    importlib.reload(_database)
    datenbank = _database.Database()
    datenbank.initialize()
    assert str(tmpdir) in str(datenbank.db_path), \
        f"DB nicht isoliert: {datenbank.db_path}"
    datenbank.save_profile({"name": "Muster Person"})
    try:
        yield datenbank
    finally:
        if alt is None:
            os.environ.pop("BA_DATA_DIR", None)
        else:
            os.environ["BA_DATA_DIR"] = alt
        shutil.rmtree(tmpdir, ignore_errors=True)


def _pruefe(db, text):
    from bewerbungs_assistent.services import pii_bestand
    return pii_bestand.pruefe_text(db, text)


# ── Der gefundene Fall ────────────────────────────────────────────────

def test_pii_kurzform_einer_klammerfassung_wird_gefunden(db):
    """Der Fall, der zwei Issues durchgelassen hat.

    Die Firma steht im Bestand mit Klammerzusatz; der Fehlerbericht
    nennt nur den vorderen Teil.
    """
    db.add_application({"company": "Musterwerk Papier (Muster-Holding)",
                        "title": "Rolle", "status": "beworben"})
    assert not _pruefe(db, "Bewerbung bei Musterwerk Papier, Rolle")["sauber"]


def test_pii_der_klammerinhalt_bleibt_bewusst_draussen(db):
    """Gemessene Entscheidung, keine Nachlaessigkeit.

    Mein erster Entwurf nahm auch den Klammerinhalt als Suchbegriff.
    Gemessen am echten Bestand ueber alle 400 Issues steht dort aber
    weit oefter eine ANMERKUNG als ein zweiter Firmenname:
    "(Vermittler)", "(Beratung)", "(Personalberatung)", "(SAP PLM)",
    "(Bremen)". Jede davon erzeugte Fehlalarme ueber Dutzende Issues —
    vier Fehlalarm-Quellen fuer einen selten gebrauchten Zusatznamen.

    Ein Pruefer, dem niemand mehr glaubt, schuetzt gar nicht (#929).
    Der vordere Teil traegt den Namen; nur er wird genommen.
    """
    assert schreibvarianten("Musterwerk (Muster-Holding)") == ["Musterwerk"]
    # Der vordere Teil zaehlt, mit und ohne Rechtsform — die Anmerkung
    # in der Klammer nicht.
    varianten = schreibvarianten("Musterwerk GmbH (Beratung)")
    assert "Musterwerk" in varianten and "Musterwerk GmbH" in varianten
    assert not any("Beratung" in v for v in varianten)


def test_pii_rechtsform_darf_fehlen_oder_dazukommen(db):
    """Ein Text nennt die Firma fast nie so vollstaendig wie die DB."""
    db.add_application({"company": "Musterwerk Hamburg GmbH",
                        "title": "Rolle", "status": "beworben"})
    assert not _pruefe(db, "Gespraech bei Musterwerk Hamburg")["sauber"]


def test_pii_zusatz_hinter_trennzeichen(db):
    """Quellen haengen Bereich oder Standort mit Bindestrich an."""
    db.add_application({"company": "Musterwerk Technik - Bereich Anlagen",
                        "title": "Rolle", "status": "beworben"})
    assert not _pruefe(db, "Angebot von Musterwerk Technik erhalten")["sauber"]


def test_pii_die_vollfassung_wird_weiterhin_gefunden(db):
    """Die Erweiterung darf den Normalfall nicht verlieren."""
    db.add_application({"company": "Musterwerk Papier (Muster-Holding)",
                        "title": "Rolle", "status": "beworben"})
    assert not _pruefe(db, "Musterwerk Papier (Muster-Holding)")["sauber"]


# ── Die Gegenrichtung: keine Fehlalarme ───────────────────────────────

def test_pii_unbeteiligter_text_bleibt_sauber(db):
    """Die wichtigste Gegenprobe. Ein Pruefer, der bei korrektem Text
    Alarm gibt, wird nach dem zweiten Mal ignoriert (#929)."""
    db.add_application({"company": "Musterwerk Papier (Muster-Holding)",
                        "title": "Rolle", "status": "beworben"})
    for text in ("Ein Fehler im Suchlauf, Score 15 statt 0.",
                 "Die Papierverarbeitung im Werk laeuft.",
                 "Das Muster der Zahlen ist auffaellig."):
        assert _pruefe(db, text)["sauber"], text


def test_pii_fragmente_aus_allerweltswoertern_werden_verworfen():
    """"Global Solutions" steht in jedem zweiten Werbetext. Als
    Suchbegriff waere es wertlos und wuerde den Pruefer unbrauchbar
    machen."""
    assert schreibvarianten("Global Solutions GmbH") == []
    assert schreibvarianten("Digital Systems Group GmbH") == []
    # Gegenprobe: ein unterscheidbares Wort haelt die Variante am Leben.
    assert "Musterwerk Systems" in schreibvarianten("Musterwerk Systems GmbH")


def test_pii_zu_kurze_fragmente_werden_verworfen():
    """Ein Zweibuchstaben-Kuerzel traefe halbe Saetze."""
    for name in ("BW AG", "TVS GmbH", "Kurz"):
        assert all(len(v) >= MIN_VARIANTENLAENGE
                   for v in schreibvarianten(name)), name


def test_pii_varianten_bei_muell_stuerzen_nicht_ab():
    """Die Funktion laeuft ueber JEDEN Bestandsnamen — ein Absturz waere
    teurer als eine fehlende Variante."""
    for wert in (None, "", "   ", "()", "- - -", "GmbH"):
        assert isinstance(schreibvarianten(wert), list)


def test_pii_der_eigene_klarname_bleibt_zulaessig(db):
    """Ausdrueckliche Regel: der Klarname des Profil-Inhabers darf in
    Texten stehen. Die Varianten duerfen diese Ausnahme nicht
    aushebeln."""
    db.save_profile({"name": "Muster Person"})
    assert _pruefe(db, "Bericht von Muster Person")["sauber"]


def test_pii_quellennamen_bleiben_ausgenommen_auch_mit_zusatz(db):
    """Vermittler- und Portalnamen sind ein FEATURE dieses Projekts und
    stehen bewusst in Issues.

    Beim Bauen der Varianten aufgefallen: ein Vermittler, der im Bestand
    als "<Name> AG" steht, war NICHT ausgenommen, obwohl der blosse Name
    ausdruecklich auf der Ausnahmeliste steht — die Pruefung verglich
    auf Gleichheit. Das war schon vor der Variantenbildung so; sie hat
    es nur sichtbar gemacht.
    """
    from bewerbungs_assistent.services.pii_bestand import (
        _enthaelt_ausnahme, sammle_bestandsnamen,
    )
    ausnahmen = {"hays", "ferchau", "arbeitnow"}
    assert _enthaelt_ausnahme("hays ag", ausnahmen)
    assert _enthaelt_ausnahme("ferchau gmbh", ausnahmen)
    assert not _enthaelt_ausnahme("musterwerk gmbh", ausnahmen)

    db.add_application({"company": "Musterwerk Papier", "title": "R",
                        "status": "beworben"})
    assert any(n["name"] == "musterwerk papier"
               for n in sammle_bestandsnamen(db))


def test_pii_kurze_ausnahmen_stellen_keine_firmen_still():
    """Gegenprobe zur Regel oben: ein Zweibuchstaben-Eintrag auf der
    Ausnahmeliste darf keine echte Firma verdecken."""
    from bewerbungs_assistent.services.pii_bestand import _enthaelt_ausnahme
    assert not _enthaelt_ausnahme("musterwerk ab technik", {"ab", "oy"})


# ── Der Guard gegen den Rueckfall ─────────────────────────────────────

def test_pii_die_suche_nutzt_die_varianten():
    """Ohne diesen Aufruf ist der Fix wieder weg, und zwar unsichtbar —
    der Pruefer laeuft dann weiter durch und meldet 'sauber' (DoD 8c)."""
    quelle = (Path(__file__).resolve().parents[1] / "src"
              / "bewerbungs_assistent" / "services"
              / "pii_bestand.py").read_text(encoding="utf-8")
    code = "\n".join(z for z in quelle.split("\n")
                     if not z.strip().startswith("#"))
    assert "for variante in schreibvarianten(" in code


def test_pii_ein_treffer_nennt_seine_herkunft(db):
    """Wer eine Variante gemeldet bekommt, soll den vollen Namen
    nachschlagen koennen — sonst sucht er im Bestand vergeblich."""
    from bewerbungs_assistent.services.pii_bestand import sammle_bestandsnamen
    db.add_application({"company": "Musterwerk Papier (Muster-Holding)",
                        "title": "Rolle", "status": "beworben"})
    namen = sammle_bestandsnamen(db)
    varianten = [n for n in namen if n.get("variante_von")]
    assert varianten
    assert all("musterwerk papier" in v["variante_von"] for v in varianten)
