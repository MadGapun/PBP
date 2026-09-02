"""Regressionstests fuer die PII-Erkennung (scripts/scrub_pii.py).

Warum es diese Tests gibt: Der Pruefer ist die mechanische Absicherung
gegen das Veroeffentlichen personenbezogener Daten (DoD-Punkt 9). Er hatte
selbst vier Fehler, die ihn in beide Richtungen unbrauchbar machten —
gefunden beim Bestands-Sweep am 07.08.2026:

  1. Telefon-Erkennung matchte ueber ZEILENUMBRUECHE ("0160\\n127")
  2. ... und las Jahresspannen als Rufnummern ("2020-2024" -> "020-2024")
  3. ... und Git-Commit-Hashes in Backticks ("`0462449`")
  4. Die Mail-Allowlist prueste per endswith: "grossfirma.de" endet auf
     "firma.de" und galt damit als Platzhalter — echte Adressen rutschten
     durch (die gefaehrliche Richtung)

16 von 60 Treffern des ersten Sweeps waren Fehlalarm. Ein Pruefer, der bei
korrektem Ergebnis Alarm gibt, wird nach dem zweiten Mal ignoriert; einer
mit Loechern schuetzt nicht. Deshalb prueft jeder Test hier BEIDE
Richtungen — was anschlagen MUSS und was NICHT anschlagen darf.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from scrub_pii import find_pii  # noqa: E402


def _arten(text: str, praefix: str) -> list:
    return [h for h in find_pii(text) if h.startswith(praefix)]


# ----------------------------------------------------------- Telefon

@pytest.mark.parametrize("text", [
    "Tel. +49 151 4497 4978",
    "Rueckruf unter 0431/7002356 erbeten",
    "Kontakt: +49 40 85538906",
    "Durchwahl +49 69 9897 283 65",
    "Mobil 0176 4766 4385",
])
def test_echte_rufnummern_werden_erkannt(text):
    assert _arten(text, "PHONE"), f"nicht erkannt: {text!r}"


@pytest.mark.parametrize("text", [
    "Zeitraum 2020-2024 im Profil",              # Jahresspanne
    "hitteam.de 2009-2019 + Firma 2020-2024",
    "Version 1.7.11 vom 2026-08-06",
    "Umgesetzt in `v1.7.0-beta.83` (Commit `0462449`)",   # Commit-Hash
    "Siehe Commit `0260421` und `a3f9b12`.",
    "Seiten-Cap 15\n127 Treffer",                # Zeilenumbruch
    "Erste 200 Zeichen",
    "ca. 10 Personentage",
])
def test_keine_fehlalarme_bei_zahlen(text):
    assert not _arten(text, "PHONE"), f"Fehlalarm: {text!r}"


def test_echte_nummer_neben_code_wird_trotzdem_erkannt():
    """Der Backtick-Filter darf nicht die halbe Zeile mitentschaerfen."""
    assert _arten("In `v1.7` gemeldet, Tel +49 69 9897 283 65", "PHONE")


@pytest.mark.parametrize("text", [
    "0511 5550123",              # Musterprofil Bob
    "0341 5550987",              # Musterprofil Anna
    "+49 511 555 0123",          # international geschrieben
])
def test_fiktive_555_nummern_sind_erlaubt(text):
    """v1.7.16: Musterdaten brauchen erkennbar unechte Rufnummern; der
    555-Block ist die uebliche Fiktionskonvention. Ohne diese Regel gab
    der Pruefer bei KORREKTEN Musterprofilen Alarm."""
    assert not _arten(text, "PHONE"), f"Fehlalarm auf Fiktion: {text!r}"


@pytest.mark.parametrize("text", [
    "Tel. 0511 4497 4978",       # gleiche Vorwahl, echte Nummer
    "Mobil 0176 4766 4385",
    "Kontakt: +49 40 85538906",
])
def test_echte_nummern_trotz_555_regel_erkannt(text):
    """Gegenrichtung: Die Fiktions-Ausnahme darf keine echten Nummern
    durchlassen — sie greift nur, wenn der Teilnehmerteil mit 555 BEGINNT."""
    assert _arten(text, "PHONE"), f"nicht erkannt: {text!r}"


# -------------------------------------------------------------- Mail

@pytest.mark.parametrize("addr", [
    "a.weber@mersol.de",
    "vorname.nachname@firma-xy.de",
    "recruiting@grossfirma.de",   # endet auf "firma.de" — war die Luecke
    "hr@bestetest.de",            # endet auf "test.de"
])
def test_personen_adressen_werden_erkannt(addr):
    assert _arten(addr, "EMAIL"), f"nicht erkannt: {addr!r}"


def test_portal_roboter_domain_ist_safe():
    """PII-Triage 12.08.2026: hinter bot.xing.com haengt unabhaengig vom
    Lokalteil nur der XING-Benachrichtigungs-Roboter (#643) — info@ dort
    ist kein Kontaktweg zu einem Menschen. Personen-Adressen auf normalen
    Domains bleiben erkannt (siehe Parametrize oben)."""
    assert not _arten("info@bot.xing.com", "EMAIL")


@pytest.mark.parametrize("addr", [
    "test@example.com",
    "bewerbung@firma.de",
    "kontakt@test.de",
    "info@sub.example.org",              # echte Subdomain
    "PBP-Service@Elwosa.de",
    "noreply@linkedin.com",              # Automaten-Absender
    "mailrobot@mail.xing.com",
    "notifications-noreply@linkedin.com",
    "noreply@recruiting.beispiel-gruppe.de",
])
def test_platzhalter_und_automaten_sind_erlaubt(addr):
    assert not _arten(addr, "EMAIL"), f"Fehlalarm: {addr!r}"


# ------------------------------------------------------------ Firmen

def test_echte_firmen_werden_erkannt():
    hits = find_pii("Wir haben uns bei der Bosch Rexroth AG beworben.")
    assert any(h.startswith(("FIRMA", "CORP")) for h in hits)


@pytest.mark.parametrize("text", [
    "Praxis-Fall: Halbleiterwerk Nord GmbH lehnte ab.",
    "Anlagenbau Sued GmbH und Chemiewerk Mitte",
    "Ingenieurvermittlung Mitte GmbH als Vermittler",
    "Beispiel AG im Testfall",
])
def test_fiktive_platzhalter_firmen_sind_erlaubt(text):
    """Der Pruefer schlug frueher bei genau den Platzhaltern an, die die
    DoD-Regel vorschreibt — dann nimmt ihn niemand mehr ernst."""
    assert not [h for h in find_pii(text) if h.startswith("CORP")], text


# ------------------------------------------------------- Gesamtbild

def test_anonymisierter_issue_text_ist_sauber():
    """Ein nach der Konvention anonymisierter Text muss ohne Nacharbeit
    durchgehen — sonst ist die Konvention nicht anwendbar."""
    text = (
        "## Problem\n\n"
        "Bei Halbleiterwerk Nord GmbH (via Ingenieurvermittlung Mitte GmbH) "
        "blieb die Zuordnung leer. Ansprechpartner <PERSON>, erreichbar "
        "unter <telefon-fest> bzw. <email-anonymisiert>.\n\n"
        "Beleg aus dem Bestand: Commit `0462449`, Zeitraum 2020-2024, "
        "Absage kam von noreply@linkedin.com.\n"
    )
    assert find_pii(text) == [], find_pii(text)


def test_originaler_issue_text_schlaegt_an():
    """Gegenprobe: der Fall, der am 07.08. geloescht werden musste."""
    text = ("Ansprechpartner Alexander Weber, a.weber@mersol.de, "
            "Tel. +49 69 2009 144 72")
    hits = find_pii(text)
    assert any(h.startswith("EMAIL") for h in hits)
    assert any(h.startswith("PHONE") for h in hits)


# === v1.7.18: Quellen-Keys als DoD-9-Ausnahme ======================
# Einige Namen sind BEIDES: realer Vermittler aus der Bewerbungshistorie
# (PII) und technischer Quellen-Key im SOURCE_REGISTRY (Feature, ueber
# das Issues/Wiki/Release-Notes sprechen muessen). Unterschieden wird
# ueber die Schreibweise. Beide Richtungen sind Pflicht — ein Pruefer,
# der bei korrektem Text Alarm gibt, wird nach dem zweiten Mal ignoriert.

def test_quellen_key_kleingeschrieben_ist_erlaubt():
    from scrub_pii import find_pii
    sauber = [
        "Der ferchau-Adapter liefert 0 Stellen.",
        "quellen_health_check meldet hays und personio als erreichbar.",
        "`ferchau` steht als deprecated, obwohl die API antwortet.",
        "gulp und solcom laufen jetzt ueber Handoff.",
    ]
    for text in sauber:
        assert find_pii(text) == [], (text, find_pii(text))


def test_firmen_schreibweise_bleibt_pii():
    from scrub_pii import find_pii
    for text in ("Bewerbung bei FERCHAU wurde abgelehnt.",
                 "Hays hat sich zur Stelle gemeldet.",
                 "Das Gespraech bei FERCHAU GmbH lief gut."):
        assert find_pii(text), f"muss PII melden: {text}"


def test_quellen_ausnahme_deckt_keine_fremden_firmen():
    """Die Ausnahme gilt NUR fuer bekannte Registry-Keys."""
    from scrub_pii import find_pii
    # kleingeschrieben, aber kein Quellen-Key -> bleibt PII
    assert find_pii("die stelle bei rheinmetall war interessant")


# ── v1.7.22 (#929): Kodierung, Fehlalarme, Adapter-Klassen ────────────

def test_929_umlaut_firma_wird_ueber_stdin_erkannt(tmp_path):
    """Der Pruefer liest die Eingabe hart als UTF-8.

    Unter Windows nahm `sys.stdin.read()` die ANSI-Codepage (cp1252).
    Ein Firmenname mit Umlaut kam dadurch verstuemmelt an
    ("Gruen & Soehne GmbH" mit echten Umlauten wurde zu Mojibake) und
    passte auf KEIN Muster mehr — der Schutz haette ihn durchgewinkt.
    Falsch-negativ in einem Schutzwerkzeug ist der teuerste Fehler.
    """
    import subprocess
    import sys
    from pathlib import Path

    skript = Path(__file__).resolve().parents[1] / "scripts" / "scrub_pii.py"
    datei = tmp_path / "eingabe.md"
    datei.write_text("Bewerbung bei Gr\u00fcn & S\u00f6hne GmbH lief gut.\n",
                     encoding="utf-8")
    with open(datei, "rb") as f:
        p = subprocess.run([sys.executable, str(skript), "--check"],
                           stdin=f, capture_output=True)
    assert p.returncode == 1, "Umlaut-Firma muss erkannt werden"

    # Gegenrichtung: sauberer Text darf nicht anschlagen.
    sauber = tmp_path / "sauber.md"
    sauber.write_text("Ein Text ueber Musterfirma GmbH.\n", encoding="utf-8")
    with open(sauber, "rb") as f:
        p2 = subprocess.run([sys.executable, str(skript), "--check"],
                            stdin=f, capture_output=True)
    assert p2.returncode == 0, p2.stderr.decode("utf-8", "replace")


def test_929_generische_woerter_vor_rechtsform_sind_keine_firma():
    """"Rechtsform-Suffixe GmbH/AG" ist ein Satz, kein Unternehmen."""
    from scrub_pii import find_pii
    for text in ("Firma normalisiert (Umlaute, Rechtsform-Suffixe GmbH/AG).",
                 "Beispiele GmbH und AG werden gleich behandelt.",
                 "Die Endungen GmbH, AG, KG fallen weg."):
        assert find_pii(text) == [], (text, find_pii(text))
    # Gegenrichtung: eine echte Firma mit Rechtsform bleibt ein Treffer.
    assert find_pii("Das Gespraech bei Nordwerk Antriebstechnik GmbH lief.")


def test_929_adapter_klassennamen_sind_quellen_bezeichner():
    """`HaysAdapter` benennt eine Quelle im Code, keine Bewerbung."""
    from scrub_pii import find_pii
    assert find_pii("- `BundesagenturAdapter` + `HaysAdapter` sind Wrapper.") == []
    # Ohne den Adapter-Kontext bleibt der blosse Firmenname PII.
    assert find_pii("Hays hat sich zur Stelle gemeldet.")


# ── v1.7.23 (#930): Testdaten und Quelltext-Konstanten ───────────────

def test_930_testplatzhalter_loesen_keinen_alarm():
    """Der Repo-Scan war unbenutzbar, weil er bei jedem Testdatensatz
    anschlug. Erkannt wird strukturell am Kopfwort, nicht ueber eine
    gepflegte Einzelliste — Testdaten entstehen staendig neu."""
    from scrub_pii import find_pii
    for name in ("Tech GmbH", "Foo GmbH & Co. KG", "Beta GmbH", "Alt AG",
                 "TestCorp GmbH", "EvilCorp AG", "Geheime Bank GmbH",
                 "Musterfirma Software GmbH"):
        assert find_pii(f"Bewerbung bei {name} lief gut.") == [], name


def test_930_aehnlich_klingende_echte_firmen_bleiben_treffer():
    """Gegenrichtung: 'Alt GmbH' ist ein Platzhalter, 'Altana AG' nicht."""
    from scrub_pii import find_pii
    for name in ("Altana AG", "Nordwerk Antriebstechnik GmbH",
                 "Testo SE"):
        assert find_pii(f"Bewerbung bei {name} lief gut."), name


def test_930_hex_konstanten_sind_keine_telefonnummern():
    """Belegt: creationflags 0x08000000 wurde als Rufnummer gemeldet."""
    from scrub_pii import find_pii
    assert find_pii('_FLAGS = {"creationflags": 0x08000000}') == []
    # Gegenrichtung: echte Nummern werden weiterhin gefunden.
    assert find_pii("Tel. 08000 123456")
    assert find_pii("Ruf an: +49 171 1234567")


# ── v1.7.24: Rechtsform-Aufzaehlung ist keine Firma ──────────────────

def test_1724_rechtsform_aufzaehlung_ist_kein_treffer():
    """Gefunden beim GH-Sweep am 02.09.2026 im eigenen Issue #962.

    Der Text zaehlt dort Rechtsform-Zusaetze auf:
    "(GmbH, AG, SE, & Co. KG, B.V., Group, Ltd.)". Der Regex nahm "Co."
    als Firmennamen und "KG" als Rechtsform und meldete "Co. KG".

    Ein Firmenname faengt nie mit einer Rechtsform an. Dieselbe Lehre
    wie bei Jahresspanne, CSS-Farbwert und Hex-Konstante: ein Pruefer,
    der bei korrektem Text Alarm gibt, wird nach dem zweiten Mal
    ignoriert.
    """
    from scrub_pii import find_pii
    assert find_pii("(GmbH, AG, SE, & Co. KG, B.V., Group, Ltd.)") == []
    assert find_pii("Rechtsformen sind GmbH, AG und KG") == []


def test_1724_echte_firma_mit_co_kg_bleibt_treffer():
    """Die Gegenrichtung — sonst waere die Haertung eine Luecke."""
    from scrub_pii import find_pii
    treffer = find_pii("Bewerbung bei Nordwerk Antriebstechnik GmbH & Co. KG")
    assert treffer, "Eine echte Firma mit Co. KG muss weiterhin anschlagen"
    assert "Nordwerk" in treffer[0]
