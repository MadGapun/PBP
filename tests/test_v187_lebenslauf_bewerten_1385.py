"""#1385: lebenslauf_bewerten widerspricht sich nicht mehr."""
from bewerbungs_assistent.export import (
    analyse_cv_perspectives, fehlende_begriffe, fuehrung_erkennbar,
    messbare_ergebnisse)

FIRMA = "Beispielwerk Fertigungstechnik GmbH"
ANZEIGE = (
    "Beispielwerk Fertigungstechnik GmbH sucht einen Teamleiter Arbeitsvorbereitung (AV). "
    "Zwecke der Stelle: Einzel- und Serienfertigung planen. Sie leiten die AV, "
    "planen die Feinplanung in SAP PP und verantworten die Zerspanung. Kenntnisse in FMEA und Kanban. "
    "Beispielwerk bietet Urlaub und ein starkes Team.")

PROFIL = {
    "name": "Test Person", "email": "t@example.com", "phone": "1", "city": "Musterstadt",
    "summary": "Fertigungsmeister mit Erfahrung in Planung und Führung. " * 3,
    "skills": [{"name": "SAP PP", "category": "tool", "level": 4}],
    "education": [{"degree": "Industriemeister", "institution": "IHK"}],
    "positions": [
        {"title": "Fertigungsmeister", "company": "Musterbetrieb GmbH",
         "start_date": "2019-04", "is_current": 1,
         "tasks": "Verantwortung für 26 Mitarbeitende in drei Schichten, Arbeitsvorbereitung",
         "achievements": "", "technologies": "SAP",
         "projects": [{"name": "SAP-PP-Feinplanung eingeführt",
                       "result": "Rüstzeiten halbiert", "technologies": "SAP PP"}]},
        {"title": "Fertigungsplaner", "company": "Altbetrieb AG",
         "start_date": "2012-01", "end_date": "2019-03",
         "tasks": "Planung", "achievements": "",
         "projects": [{"name": "Layout", "result": "Platz gespart"},
                      {"name": "Takt", "result": "Takt verkürzt"}]},
    ],
}


def _analyse():
    return analyse_cv_perspectives(PROFIL, "Teamleiter Arbeitsvorbereitung", ANZEIGE, firma=FIRMA)


def test_kein_widerspruch_bei_messbaren_ergebnissen():
    a = _analyse()["perspektiven"]
    pb, ats = a["personalberater"], a["ats"]
    pb_text = " ".join(pb["faktoren"] + pb["empfehlungen"])
    ats_text = " ".join(ats["faktoren"] + ats["empfehlungen"])
    assert "Projekte mit eingetragenem Ergebnis" in pb_text      # 3 Projekte
    assert "Keine messbaren Erfolge" not in ats_text              # Zahl "26 Mitarbeitende" gefunden
    assert "Zahlen und Metriken" in ats_text


def test_projekt_ergebnisse_ohne_zahl_sind_kein_keine_erfolge():
    profil = {**PROFIL, "positions": [
        {"title": "Planer", "start_date": "2019-01", "tasks": "Planung",
         "projects": [{"name": "A", "result": "Besser"}]}]}
    ats = analyse_cv_perspectives(profil, "Planer", ANZEIGE, firma=FIRMA)["perspektiven"]["ats"]
    text = " ".join(ats["empfehlungen"])
    assert "Keine messbaren Erfolge" not in text
    assert "keine Zahl" in text


def test_ohne_ergebnisse_bleibt_die_warnung():
    profil = {**PROFIL, "positions": [
        {"title": "Planer", "start_date": "2019-01", "tasks": "Planung", "projects": []}]}
    ats = analyse_cv_perspectives(profil, "Planer", ANZEIGE, firma=FIRMA)["perspektiven"]["ats"]
    assert any("Keine messbaren Erfolge" in e for e in ats["empfehlungen"])


def test_fertigungsmeister_mit_personalverantwortung_zaehlt_als_fuehrung():
    pb = _analyse()["perspektiven"]["personalberater"]
    assert any("Führungserfahrung erkennbar" in f for f in pb["faktoren"])
    assert not any("Führungsverantwortung oder Teamleitung hervorheben" in e
                   for e in pb["empfehlungen"])


def test_fuehrung_aus_titel_oder_aufgaben_nicht_aus_zufall():
    assert fuehrung_erkennbar([{"title": "Vorarbeiter"}])
    assert fuehrung_erkennbar([{"title": "Polier"}])
    assert fuehrung_erkennbar([{"title": "Schichtführer"}])
    assert fuehrung_erkennbar([{"title": "Sachbearbeiter", "tasks": "Personalverantwortung für 5 MA"}])
    assert not fuehrung_erkennbar([{"title": "Sachbearbeiter", "tasks": "Rechnungen buchen"}])
    # 'lead' steckt in 'Pleader'? Wortgrenze: kein Treffer
    assert not fuehrung_erkennbar([{"title": "Bleadwerker"}])


def test_messbare_ergebnisse_kennt_mitarbeitende_und_ma_und_projekte():
    m = messbare_ergebnisse([{"tasks": "Leitung von 12 Mitarbeitenden und 4 MA", "achievements": "",
                              "projects": [{"result": "Kosten um 15 % gesenkt"}]}])
    assert len(m["zahlen"]) == 3 and m["projekte_mit_ergebnis"] == 1


def test_fehlende_keywords_ohne_fuellwoerter_und_firmenname():
    a = _analyse()["perspektiven"]["ats"]
    fehlend = [x.lower() for x in a["fehlende_keywords"]]
    for unerwuenscht in ("zwecke", "einzel", "beispielwerk", "fertigungstechnik", "urlaub", "team"):
        assert unerwuenscht not in fehlend, fehlend
    # echte Lücke bleibt: FMEA und Kanban stehen nicht im Profil
    assert "fmea" in fehlend and "kanban" in fehlend, fehlend
    # und was im Profil steht (AV als Arbeitsvorbereitung, Feinplanung) fehlt nicht
    assert "av" not in fehlend and "feinplanung" not in fehlend


def test_fehlende_begriffe_firmenname_wird_ausgeschlossen():
    # Selbst wenn der Firmenname als Begriff erkannt würde: er fällt raus
    erg = fehlende_begriffe({"skills": [], "positions": []},
                            "Zerspanung bei Zerspanung Mustermann", "Zerspanung Mustermann GmbH")
    assert erg == []
