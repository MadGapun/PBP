"""Tests fuer v1.7.50 — #950: die Entfernung sagt nicht, was sie ist.

Gemeldet am 21.08.2026 anhand einer Stelle in Nordhessen. PBP wies beim
Anlegen aus:

    "entfernung_km": 271.5

Die tatsaechliche Fahrstrecke betraegt rund 390 km — vier Stunden je
Richtung. Der ausgewiesene Wert ist die Luftlinie. Der Nutzer hat
nachgefragt, weil ihm die Zahl zu niedrig vorkam; **genau das ist der
Befund: an der Zahl steht nicht, was sie ist.**

Der gemeldete Umrechnungsfaktor liegt bei 390/271,5 = 1,44 — #167 hatte
1,3 angenommen. Er ist keine Konstante, sondern haengt an der
Streckenfuehrung.

Und die Zahl ist inzwischen eine Rechengroesse: seit #910 wird
Entfernung gegen das Gehalt verrechnet. Ein systematisch zu niedriger
Wert faellt damit zugunsten weit entfernter Stellen aus.

Umgesetzt sind AK 1 und 2 (kennzeichnen, Schaetzung ausweisen). AK 3 und
4 — echtes Routing samt Fahrzeit — brauchen einen API-Schluessel und
bleiben offen. **Kein Malus aendert sich** (#910: Entfernung ist ein
Preis, kein Ausschluss); es geht allein darum, dass die Zahl bedeutet,
was sie vorgibt.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from bewerbungs_assistent.services import entfernung  # noqa: E402


# ── Der gemeldete Fall ────────────────────────────────────────────────

def test_950_die_zahl_nennt_ihre_art():
    """Der kleinste wirksame Fix aus dem Report."""
    befund = entfernung.befund(271.5)
    assert befund["entfernung_art"] == "luftlinie"
    assert "Luftlinie" in befund["entfernung_text"]


def test_950_gemeldeter_fall_liegt_nahe_an_der_wirklichkeit():
    """271,5 km Luftlinie, gemeldete Fahrstrecke rund 390 km.

    Die Schaetzung muss nicht exakt sein — sie muss naeher an der
    Wirklichkeit liegen als die Luftlinie, sonst hilft sie nicht.
    """
    geschaetzt = entfernung.fahrstrecke_schaetzung(271.5)
    assert abs(geschaetzt - 390) < abs(271.5 - 390)
    assert 350 <= geschaetzt <= 420


def test_950_die_schaetzung_ist_als_solche_gekennzeichnet():
    """Ohne das Wort waere sie nur eine zweite Zahl, der man ebenso
    glaubt wie der ersten."""
    befund = entfernung.befund(271.5)
    assert "geschaetzt" in befund["entfernung_text"]
    assert "keine berechnete Route" in befund["fahrstrecke_hinweis"]
    assert str(entfernung.FAHRSTRECKEN_FAKTOR) in befund["fahrstrecke_hinweis"]


def test_950_im_nahbereich_keine_scheingenauigkeit():
    """Bei 12 km liegt der Unterschied im Bereich weniger Kilometer.
    Eine Schaetzzahl daneben zu stellen suggeriert eine Genauigkeit, die
    es nicht gibt."""
    befund = entfernung.befund(12)
    assert "fahrstrecke_km_geschaetzt" not in befund
    assert befund["entfernung_text"] == "12 km Luftlinie"


def test_950_keine_entfernung_ist_kein_nullwert():
    """"0 km" und "unbekannt" duerfen nicht zusammenfallen — das ist die
    Verwechslung aus #965/#989."""
    assert entfernung.befund(None) == {}
    assert entfernung.befund("") == {}
    assert entfernung.befund("weit weg") == {}
    assert entfernung.fahrstrecke_schaetzung(None) is None


# ── Die Ausgaben tragen es auch ───────────────────────────────────────

def test_950_stellen_anzeigen_und_anlegen_kennzeichnen_die_zahl():
    """Guard gegen den Rueckfall: die blosse Zahl darf an keiner der
    beiden Ausgabestellen zurueckkommen."""
    quelle = (Path(__file__).resolve().parents[1] / "src"
              / "bewerbungs_assistent" / "tools" / "jobs.py").read_text(
                  encoding="utf-8")
    code = "\n".join(z for z in quelle.split("\n")
                     if not z.strip().startswith("#"))
    assert '_entfernung.befund(' in code
    assert 'entry["entfernung_km"] = ' not in code
    assert 'result["entfernung_km"] = ' not in code


def test_950_die_fit_faktoren_nennen_die_luftlinie():
    """Die Faktorenliste liest der Mensch direkt — dort stand die Zahl
    unbeschriftet."""
    from bewerbungs_assistent.job_scraper import fit_analyse
    job = {"title": "PLM Architect", "location": "Melsungen",
           "description": "PLM " * 40, "distance_km": 271.5,
           "employment_type": "festanstellung"}
    ergebnis = fit_analyse(job, {"keywords_muss": ["plm"],
                                 "max_entfernung": {"festanstellung": 50}})
    entfernungs_zeilen = [k for k in ergebnis["factors"]
                          if "Entfernung" in k or "Naehe" in k]
    assert entfernungs_zeilen
    assert all("Luftlinie" in k for k in entfernungs_zeilen), entfernungs_zeilen


# ── Gegenprobe: die Bewertung bleibt unveraendert ─────────────────────

def test_950_kein_malus_hat_sich_geaendert():
    """Ausdrueckliche Abgrenzung des Melders: es geht um die Benennung,
    nicht um die Bewertung. Die Leitlinie bleibt Recall vor Praezision,
    und #910 regelt die Verrechnung."""
    from bewerbungs_assistent.job_scraper import calculate_score
    kws = ["plm", "pdm", "teamcenter"]
    kriterien = {"keywords_muss": kws,
                 "max_entfernung": {"festanstellung": 50}}
    basis = {"title": "PLM Architect", "description": (" ".join(kws) + ". ") * 20,
             "employment_type": "festanstellung", "location": "Melsungen"}
    nah = calculate_score(dict(basis, distance_km=10.0), kriterien)
    fern = calculate_score(dict(basis, distance_km=271.5), kriterien)
    assert nah > fern, "Die Rangfolge nach Entfernung muss erhalten bleiben"
    # Und die Stelle verschwindet nicht — Entfernung ist ein Preis,
    # kein Ausschluss (#910).
    assert fern > 0


def test_950_nebenbefund_ein_einziger_muss_begriff_kippt_auf_null():
    """Beim Schreiben des Tests darueber aufgefallen, hier festgehalten.

    Mit genau EINEM MUSS-Begriff ist der Fachscore so klein (2 Punkte),
    dass der Entfernungsmalus ihn ueberholt: `calculate_score` kappt bei
    0, und eine Fernstelle sieht damit aus wie eine, die das MUSS-Tor
    gar nicht passiert hat. Zwei verschiedene Sachverhalte, eine Zahl.

    Das ist NICHT Gegenstand von #950 (dort geht es um die Benennung der
    Kilometerzahl) und auch kein Defekt im engeren Sinn — bei drei und
    mehr Begriffen tritt es nicht auf, siehe Messung im Test darueber.
    Der Test haelt das Verhalten fest, damit die Grenze bekannt bleibt
    und eine kuenftige Aenderung daran auffaellt.
    """
    from bewerbungs_assistent.job_scraper import calculate_score
    kriterien = {"keywords_muss": ["plm"],
                 "max_entfernung": {"festanstellung": 50}}
    basis = {"title": "PLM Architect", "description": "PLM " * 40,
             "employment_type": "festanstellung", "location": "Melsungen"}
    assert calculate_score(dict(basis, distance_km=10.0), kriterien) > 0
    assert calculate_score(dict(basis, distance_km=271.5), kriterien) == 0
