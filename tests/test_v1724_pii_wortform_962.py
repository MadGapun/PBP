"""Tests fuer v1.7.24 — #962: der Pruefer meldete Alltagswoerter als Firmen.

`issue_text_pruefen` markierte in einem Issue-Entwurf das Wort "alten"
(in "den alten und den neuen Typ") als Firmentreffer, mit
`unsicher: false` und der Aufforderung, den Text nicht zu
veroeffentlichen. Ursache: ein Firmenname im Bestand, der einem
gebraeuchlichen deutschen Wort entspricht.

Das ist kein Einzelfall — Personaldienstleister und Beratungen heissen
regelmaessig wie Alltagswoerter. In einem laengeren deutschen Fliesstext
trifft das mit hoher Wahrscheinlichkeit.

Warum das zaehlt: der Pruefer ist als PFLICHTSCHRITT vor jedem
GitHub-Text ausgelegt. Sein Wert haengt daran, dass ein Treffer ernst
genommen wird. Ein Fehlalarm mit derselben Dringlichkeit wie ein echter
Fund trainiert das Gegenteil — nach dem dritten Mal wird der Hinweis
ueberlesen, und dann faellt auch der echte Treffer durch (#825).

Deshalb hier BEIDE Richtungen: dass der Fehlalarm weg ist, und dass der
echte Treffer bleibt. Ein Pruefer, der nach dem Haerten nichts mehr
findet, ist schlimmer als einer, der zu viel findet.
"""
import pytest

from bewerbungs_assistent.services import pii_bestand as P


@pytest.fixture
def bestand(tmp_db):
    """Ein Bestand, dessen Firmennamen wie Alltagswoerter aussehen."""
    for firma in ("Alten", "Modern", "Feder", "Nordwerk Antriebstechnik"):
        tmp_db.add_application({
            "title": "Consultant", "position": "Consultant",
            "company": firma, "status": "beworben",
        })
    return tmp_db


# ── AK 1: kleingeschrieben im Fliesstext ist kein harter Treffer ─────

def test_962_kleingeschriebenes_alltagswort_ist_kein_harter_treffer(bestand):
    """Der berichtete Fall, woertlich."""
    text = "Wir unterscheiden den alten und den neuen Typ der Anzeige."
    b = P.pruefe_text(bestand, text)
    assert b["sauber"] is True, b
    harte = [t for t in b["treffer"] if not t["unsicher"]]
    assert harte == [], harte


def test_962_mehrere_alltagswoerter_erzeugen_keinen_harten_treffer(bestand):
    """AK 5: ein realistischer deutscher Absatz."""
    text = ("Der alten Fassung fehlte die Pruefung. Die modern gestaltete "
            "Oberflaeche zeigt sie jetzt an; die Feder im Mechanismus "
            "bleibt unveraendert.")
    b = P.pruefe_text(bestand, text)
    assert b["sauber"] is True, b["treffer"]


def test_962_unsicherer_treffer_wird_begruendet(bestand):
    """AK 3: gemeldet wird trotzdem — nur eben mit Einordnung."""
    b = P.pruefe_text(bestand, "Wir behalten den alten Weg bei.")
    unsichere = [t for t in b["treffer"] if t["unsicher"]]
    assert unsichere, "Der Fund soll sichtbar bleiben, nur nicht hart"
    assert unsichere[0].get("unsicher_grund")


# ── AK 2: derselbe Name als Firma bleibt ein Treffer ─────────────────

def test_962_grossgeschrieben_mit_rechtsform_bleibt_treffer(bestand):
    """AK 6 — die wichtigere Richtung."""
    b = P.pruefe_text(bestand, "Die Bewerbung bei Alten GmbH lief gut.")
    assert b["sauber"] is False, b
    assert any(not t["unsicher"] for t in b["treffer"])


@pytest.mark.parametrize("satz", [
    "Absage von der Modern AG erhalten.",
    "Gespraech bei Feder & Co. KG vereinbart.",
    "Kontakt zur Alten Group besteht seit Juli.",
])
def test_962_rechtsform_schlaegt_die_wortform(bestand, satz):
    b = P.pruefe_text(bestand, satz)
    assert b["sauber"] is False, (satz, b["treffer"])


def test_962_mehrwortname_bleibt_immer_treffer(bestand):
    """Mehrwort-Namen kollidieren praktisch nie zufaellig — die
    Lockerung darf sie nicht mit erfassen."""
    b = P.pruefe_text(bestand, "bei nordwerk antriebstechnik lief es schief")
    assert b["sauber"] is False, b["treffer"]


# ── AK 4: Anonymisieren entstellt den Satz nicht ─────────────────────

def test_962_anonymisieren_ersetzt_unsichere_treffer_nicht(bestand):
    """Ein Adjektiv durch einen Firmenplatzhalter zu tauschen macht den
    Satz sinnlos — und der Nutzer merkt es beim Ueberfliegen nicht."""
    text = "Wir unterscheiden den alten und den neuen Typ."
    erg = P.anonymisiere_text(bestand, text)
    assert erg["text"] == text, erg
    assert erg["anzahl"] == 0


def test_962_anonymisieren_listet_die_offenen_faelle_zur_entscheidung(bestand):
    """Stillschweigend uebergehen waere die andere Fehlerrichtung."""
    erg = P.anonymisiere_text(bestand, "Der alten Fassung fehlte etwas.")
    assert erg.get("zur_entscheidung")
    assert "hinweis" in erg


def test_962_anonymisieren_ersetzt_die_echte_firma_weiterhin(bestand):
    erg = P.anonymisiere_text(bestand, "Absage von der Alten GmbH.")
    assert "Alten" not in erg["text"], erg["text"]
    assert erg["anzahl"] >= 1


# ── Der Pruefer bleibt scharf, wo er scharf sein muss ────────────────

def test_962_haertung_macht_den_pruefer_nicht_blind(bestand):
    """Gegenprobe zur Haertung selbst: ein Text mit einem echten,
    grossgeschriebenen Firmennamen ohne Rechtsform muss weiterhin
    anschlagen."""
    b = P.pruefe_text(bestand, "Nordwerk Antriebstechnik hat abgesagt.")
    assert b["sauber"] is False, b["treffer"]
