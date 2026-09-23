"""#1076 — Dublettenpruefung verpasste umbenannte Reposts und Vermittler.

Gemeldet am 23.09.2026: eine LinkedIn-Stelle von Firma B wurde als neu
angelegt, obwohl dieselbe Vakanz schon im Bestand lag — samt laufender
Bewerbung, eingereicht ueber Vermittler A (Endkunde B nur in den
Notizen). Der Arbeitgeber hatte die Stelle umbenannt. Stufe A verglich
nur die Firma der Bewerbung (A), Stufe B nur Titel und URL.
"""
import asyncio
import importlib
import os
import shutil
import tempfile

import pytest

AUFGABEN = (
    "Ihre Aufgaben: Sie verantworten die Engineering-Prozesse von der "
    "Konstruktion bis zur Serienfreigabe und sind Partner der IT fuer alle "
    "Engineering-Anwendungen. Sie steuern die Governance fuer CAD, PDM und "
    "PLM, begleiten die Integration in das ERP-System, verantworten "
    "Stuecklisten und das Engineering Change Management mit allen "
    "Freigabeschritten. Sie moderieren Workshops mit Fachbereichen, "
    "priorisieren Anforderungen, schreiben Lastenhefte und begleiten die "
    "Auswahl neuer Werkzeuge. Ihr Profil: abgeschlossenes Studium der "
    "Ingenieurwissenschaften oder Informatik, mehrjaehrige Erfahrung mit "
    "PLM-Systemen im Maschinenbau, sicherer Umgang mit Datenmodellen und "
    "Freigabeprozessen, gute Deutsch- und Englischkenntnisse.")
FIRMENTEXT = (
    "Wir sind ein familiengefuehrter Hersteller von Sondermaschinen mit "
    "zweitausend Mitarbeitenden an drei Standorten und bieten flexible "
    "Arbeitszeiten, betriebliche Altersvorsorge und ein Jobrad.")
FREMDE_ROLLE = (
    "Ihre Aufgaben: Sie fuehren die Finanzbuchhaltung, erstellen Monats- "
    "und Jahresabschluesse nach HGB, betreuen die Kreditorenbuchhaltung, "
    "stimmen Konten ab und arbeiten eng mit dem Steuerberater zusammen. "
    "Sie pflegen die Anlagenbuchhaltung, bereiten Reports fuer die "
    "Geschaeftsfuehrung vor und unterstuetzen bei der Einfuehrung eines "
    "neuen Buchhaltungssystems. Ihr Profil: kaufmaennische Ausbildung mit "
    "Weiterbildung zum Bilanzbuchhalter und sicherer Umgang mit DATEV.")


@pytest.fixture
def env():
    tmpdir = tempfile.mkdtemp(prefix="pbp_v17126_1076_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv_mod
    importlib.reload(_srv_mod)
    db = _db_mod.Database()
    db.initialize()
    # ⛔ QA-Isolations-Regel
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Test"})
    yield db, _srv_mod.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        if hasattr(res, "structured_content"):
            return res.structured_content
        return res
    return asyncio.run(_run())


def _alt_anlegen(db, titel="Functional Business Consultant Engineering und PLM",
                 text=AUFGABEN, h="alt1076"):
    db.save_jobs([{"hash": h, "title": titel,
                   "company": "Musterwerk Bravo GmbH", "location": "Musterstadt",
                   "url": f"https://example.com/{h}", "source": "manuell",
                   "description": FIRMENTEXT + " " + text}])


def test_1076_umbenannter_repost_wird_gemeldet(env):
    db, mcp = env
    _alt_anlegen(db)
    res = _call(mcp, "stelle_manuell_anlegen", {
        "titel": "Business Application Manager PLM und Engineering Systems",
        "firma": "Musterwerk Bravo GmbH", "ort": "Musterstadt",
        "url": "https://example.com/neu1076",
        "beschreibung": FIRMENTEXT + " " + AUFGABEN, "quelle": "linkedin"})
    assert res["status"] == "angelegt", "gemeldet, nicht geblockt"
    assert res["repost_verdacht"]["titel"].startswith("Functional")
    assert res["repost_verdacht"]["aehnlichkeit_text"] >= 0.5


def test_1076_gleicher_firmentext_andere_rolle_ist_kein_repost(env):
    """Die Gegenrichtung: Firmen-Textbausteine allein machen keinen Repost."""
    db, mcp = env
    _alt_anlegen(db)
    _alt_anlegen(db, titel="Bilanzbuchhalter", text=FREMDE_ROLLE, h="alt1076b")
    res = _call(mcp, "stelle_manuell_anlegen", {
        "titel": "Finanzbuchhalter Kreditoren",
        "firma": "Musterwerk Bravo GmbH",
        "url": "https://example.com/neu1076c",
        "beschreibung": FIRMENTEXT + " Ihre Aufgaben: Sie betreuen die "
        "Kreditoren, pruefen Eingangsrechnungen und fuehren den "
        "Zahlungsverkehr. Sie arbeiten mit SAP FI, stimmen Lieferanten- "
        "konten ab und unterstuetzen den Monatsabschluss. Ihr Profil: "
        "kaufmaennische Ausbildung, Erfahrung in der Kreditorenbuchhaltung "
        "und sicherer Umgang mit Excel und einem ERP-System im Mittelstand."})
    assert "repost_verdacht" not in res


LANGER_FIRMENTEXT = (
    "Seit mehr als siebzig Jahren entwickeln und fertigen wir an unserem "
    "Stammsitz Sondermaschinen fuer die Verpackungsindustrie, die "
    "Lebensmitteltechnik und den Anlagenbau. Unsere Kunden sitzen in ueber "
    "vierzig Laendern, und jede zweite Anlage verlaesst das Werk als "
    "Einzelstueck. Wir verbinden die Verlaesslichkeit eines "
    "Familienunternehmens mit den Moeglichkeiten einer internationalen "
    "Gruppe, investieren jedes Jahr einen zweistelligen Millionenbetrag in "
    "Forschung und Entwicklung und bilden in zwoelf Berufen selbst aus. "
    "Bei uns erwarten dich flache Hierarchien, kurze Entscheidungswege, "
    "ein unbefristeter Arbeitsvertrag, dreissig Tage Urlaub, flexible "
    "Arbeitszeiten mit Gleitzeitkonto, eine betriebliche Altersvorsorge "
    "mit Arbeitgeberzuschuss, ein bezuschusstes Jobticket, ein Leasingrad, "
    "eine Kantine mit regionalen Produkten, Gesundheitstage, eine eigene "
    "Akademie fuer Weiterbildung, Sommerfeste und Familientage sowie "
    "Mitarbeiterrabatte bei vielen Partnern in der Region. Wir freuen uns "
    "auf deine Bewerbung ueber unser Karriereportal und melden uns "
    "innerhalb von zwei Wochen mit einer Rueckmeldung bei dir. Unser "
    "Werk liegt verkehrsguenstig direkt an der Autobahn, mit eigener "
    "Bushaltestelle, kostenlosen Parkplaetzen und Ladesaeulen fuer "
    "Elektroautos. Nachhaltigkeit ist fuer uns kein Schlagwort: seit drei "
    "Jahren decken wir unseren Strombedarf aus der eigenen Photovoltaik "
    "und haben den Wasserverbrauch der Lackiererei um ein Drittel gesenkt.")
ROLLE_A = (
    "Deine Aufgaben: du planst und steuerst die Wartung unserer "
    "Fertigungslinien, koordinierst externe Dienstleister, dokumentierst "
    "Stoerungen im Instandhaltungssystem, bestellst Ersatzteile, fuehrst "
    "Sicherheitsunterweisungen durch und verbesserst gemeinsam mit der "
    "Produktion die Verfuegbarkeit der Anlagen. Dein Profil: Techniker "
    "oder Meister Elektrotechnik mit mehrjaehriger Erfahrung in der "
    "Instandhaltung und Freude an der Arbeit im Schichtbetrieb.")
ROLLE_B = (
    "Deine Aufgaben: du betreust unsere Kunden im Vertriebsinnendienst, "
    "erstellst Angebote und Auftragsbestaetigungen, pflegst Stammdaten im "
    "ERP-System, stimmst Liefertermine mit der Arbeitsvorbereitung ab, "
    "bearbeitest Reklamationen und unterstuetzt den Aussendienst bei der "
    "Vorbereitung von Messen. Dein Profil: kaufmaennische Ausbildung, "
    "Erfahrung im Vertriebsinnendienst eines Industrieunternehmens und "
    "sichere Englischkenntnisse in Wort und Schrift.")


def test_1076_ueberwiegender_firmentext_macht_keinen_repost(env):
    """Der Firmentext traegt hier den Grossteil jeder Anzeige. Ohne das
    Herausnehmen der Textbausteine laege die Aehnlichkeit ueber 0,5 (die
    erste Fassung dieses Tests lag mit 0,49 knapp darunter und pruefte
    deshalb nichts) —
    genau so kamen im Bestand "Teamleiter Automatisierung" und "PLM
    Solution Architekt" auf 100 %."""
    db, mcp = env
    db.save_jobs([{"hash": "ft1", "title": "Instandhalter Elektrotechnik",
                   "company": "Musterwerk Bravo GmbH", "location": "Musterstadt",
                   "url": "https://example.com/ft1", "source": "manuell",
                   "description": LANGER_FIRMENTEXT + " " + ROLLE_A},
                  {"hash": "ft2", "title": "Kaufmann Vertrieb",
                   "company": "Musterwerk Bravo GmbH", "location": "Musterstadt",
                   "url": "https://example.com/ft2", "source": "manuell",
                   "description": LANGER_FIRMENTEXT + " " + ROLLE_B}])
    res = _call(mcp, "stelle_manuell_anlegen", {
        "titel": "Konstrukteur Sondermaschinenbau",
        "firma": "Musterwerk Bravo GmbH", "url": "https://example.com/ft3",
        "beschreibung": LANGER_FIRMENTEXT + " " + AUFGABEN})
    assert "repost_verdacht" not in res


def test_1076_vermittler_bewerbung_beim_endkunden(env):
    db, mcp = env
    db.add_application({
        "title": "PLM Berater", "company": "Personalvermittlung Alpha",
        "status": "beworben",
        "notes": "Endkunde: Musterwerk Bravo, Einsatz in Musterstadt."})
    res = _call(mcp, "stelle_manuell_anlegen", {
        "titel": "Business Application Manager PLM",
        "firma": "Musterwerk Bravo GmbH",
        "url": "https://example.com/neu1076v",
        "beschreibung": AUFGABEN})
    assert res["status"] == "angelegt"
    assert res["vermittler_bewerbung"]["firma_der_bewerbung"] == \
        "Personalvermittlung Alpha"


def test_1076_endkunde_im_klammerzusatz_der_firma(env):
    db, mcp = env
    db.add_application({
        "title": "PLM Berater", "status": "beworben",
        "company": "Personalvermittlung Alpha (Endkunde: Musterwerk Bravo)"})
    res = _call(mcp, "stelle_manuell_anlegen", {
        "titel": "PLM Manager", "firma": "Musterwerk Bravo",
        "url": "https://example.com/neu1076k", "beschreibung": AUFGABEN})
    assert "vermittler_bewerbung" in res


def test_1076_abgeschlossene_vermittler_bewerbung_zaehlt_nicht(env):
    """Stufe A kennt nur LAUFENDE Bewerbungen (#567) — hier dasselbe."""
    db, mcp = env
    db.add_application({
        "title": "PLM Berater", "company": "Personalvermittlung Alpha",
        "status": "abgelehnt", "notes": "Endkunde: Musterwerk Bravo"})
    res = _call(mcp, "stelle_manuell_anlegen", {
        "titel": "PLM Manager", "firma": "Musterwerk Bravo",
        "url": "https://example.com/neu1076x", "beschreibung": AUFGABEN})
    assert "vermittler_bewerbung" not in res


def test_1076_kurzer_firmenname_trifft_nicht_als_teilwort():
    from bewerbungs_assistent.duplicate_detection import find_vermittler_bewerbung
    apps = [{"company": "Vermittler Delta", "notes": "Endkunde: Musternordwerk AG"}]
    assert find_vermittler_bewerbung("Musternord AG", apps) is None
    assert find_vermittler_bewerbung("Musternordwerk", apps) is apps[0]


def test_1076_linkedin_trichter_zaehlt_angelegte_mit_hinweis(env):
    """Eine angelegte Stelle mit Hinweis ist angelegt, nicht uebersprungen."""
    db, mcp = env
    _alt_anlegen(db)
    res = _call(mcp, "linkedin_treffer_uebernehmen", {
        "treffer": [{"job_id": "4401076", "firma": "Musterwerk Bravo GmbH",
                     "titel": "Business Application Manager PLM",
                     "beschreibung": FIRMENTEXT + " " + AUFGABEN}],
        "dry_run": False, "rohtreffer": 146,
        "volltexte_gelesen": 10, "nach_lesen_verworfen": 9})
    t = res["trichter"]
    assert t["angelegt"] == 1 and t["uebersprungen"] == 0
    assert t["repost_verdacht"] == 1
    assert "10 Volltexte gelesen" in res["trichter_text"]
    assert "Repost-Verdacht 1" in res["trichter_text"]
    assert res["angelegt"][0]["repost_verdacht"]


# ===== Zweiter Fall (Nachtrag vom 23.09.2026) ============================

def test_1076_portal_vorspann_zaehlt_nicht_zum_titel():
    from bewerbungs_assistent.duplicate_detection import (
        _title_similarity, ohne_portal_vorspann)
    neu = ("Freelancer Opportunity - Senior Engineering Data Management & "
           "eBOM Consultant (m/f/d)")
    alt = "Senior Engineering Data Management & eBOM Consultant (m/f/d)"
    assert _title_similarity(neu, alt)[0] == 1.0
    assert ohne_portal_vorspann("Job: PLM Berater") == "PLM Berater"
    # Die Gegenrichtung: ein Bindestrich im Wort ist kein Vorspann.
    assert ohne_portal_vorspann("Projekt- und Qualitaetsmanager") == \
        "Projekt- und Qualitaetsmanager"
    assert ohne_portal_vorspann("Projektleiter Bau") == "Projektleiter Bau"


def test_1076_laufende_bewerbung_mit_anderer_url_wird_gemeldet(env):
    """Stufe A vergleicht mit URL und verlangt dann 0,85. Die
    Repost-Erkennung in `fit_analyse` vergleicht ohne URL — dieselbe Frage
    kommt jetzt auch bei der Anlage an, als Hinweis."""
    db, mcp = env
    db.add_application({
        "title": "Engineering Data Management Consultant eBOM",
        "company": "Musterwerk Bravo AG (Endkunde unbekannt)",
        "status": "beworben", "url": "https://example.com/mail-anfrage"})
    res = _call(mcp, "stelle_manuell_anlegen", {
        "titel": "Senior Engineering Data Management Consultant",
        "firma": "Musterwerk Bravo", "url": "https://example.com/li1076",
        "beschreibung": AUFGABEN})
    assert res["status"] == "angelegt"
    assert res["laufende_bewerbung_verdacht"]["status"] == "beworben"
