"""#1233 (F51) - die Suche der interaktiven Hilfe: nachschlagen statt raten.

Zwei Arten von Pruefungen:

* **Gemessen** (`FRAGEN`, `AUSSERHALB`, `NICHT_BELEGT` in `tests/hilfe_fragen_1233.py`): drei Gruppen. `entwicklung` und `abnahme` wurden beim
  Einstellen der Suche angesehen; `frisch` ist nach dem Bau der Wissensbasis fuer 1.8.0 geschrieben und wurde zum Einstellen nicht benutzt
  (ein Rest ist durch die Auslassprobe der Synonyme beruehrt). Die Schwellen unten sind die ehrliche UNTERGRENZE der lexikalischen Suche, nicht
  das Ziel: auf ungesehenen Fragen findet sie den richtigen Abschnitt in rund drei von vier Faellen unter den ersten drei. Sinkt der Wert, hat
  jemand die Suche verschlechtert.
* **Gebaut** (Hilfsfunktionen, Karte, Datenschutz): die Teile, auf die sich die Oberflaeche verlaesst.

Die Fragen werden nicht gespeichert (Nutzerentscheidung 16.10.2026): ein Test haelt das fest.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WURZEL / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from bewerbungs_assistent.services import hilfe_suche as hs  # noqa: E402
import hilfe_fragen_1233 as gold  # noqa: E402


@pytest.fixture(scope="module")
def wissen():
    return hs.laden()


def _rang(erg, erwartet):
    for r, t in enumerate(erg.treffer, 1):
        if any(t.abschnitt["id"].startswith(e) for e in erwartet):
            return r
    return 0


# ── gemessen ────────────────────────────────────────────────────────────────────────────────

def test_der_fragenkatalog_zeigt_auf_abschnitte_die_es_gibt(wissen):
    ids = [a["id"] for a in wissen.abschnitte]
    fehlt = [(f, e) for _g, f, erw in gold.FRAGEN for e in erw if not any(i.startswith(e) for i in ids)]
    assert not fehlt, fehlt[:5]


@pytest.mark.parametrize("gruppe, top3_min, top1_min", [
    ("entwicklung", 0.90, 0.65),
    ("abnahme", 0.95, 0.70),
    ("frisch", 0.70, 0.55),
])
def test_die_erwartete_antwort_steht_unter_den_ersten_drei(wissen, gruppe, top3_min, top1_min):
    fragen = [(f, erw) for g, f, erw in gold.FRAGEN if g == gruppe]
    assert len(fragen) >= 40
    ergebnisse = [_rang(hs.suche(f, wissen=wissen), erw) for f, erw in fragen]
    top3 = sum(1 for r in ergebnisse if r) / len(fragen)
    top1 = sum(1 for r in ergebnisse if r == 1) / len(fragen)
    assert top3 >= top3_min, f"{gruppe}: Top-3 {top3:.0%} < {top3_min:.0%}"
    assert top1 >= top1_min, f"{gruppe}: Top-1 {top1:.0%} < {top1_min:.0%}"


def test_fragen_ausserhalb_von_pbp_bekommen_nie_eine_sichere_antwort(wissen):
    assert len(gold.AUSSERHALB) >= 30
    for f in gold.AUSSERHALB:
        erg = hs.suche(f, wissen=wissen)
        assert erg.status != "gefunden", (f, erg.status, [t.abschnitt["id"] for t in erg.treffer[:2]])


def test_die_meisten_fragen_ausserhalb_werden_als_solche_erkannt(wissen):
    erkannt = [hs.suche(f, wissen=wissen).status for f in gold.AUSSERHALB]
    keine_karten = sum(1 for s in erkannt if s in ("ausserhalb", "nichts_gefunden"))
    assert keine_karten / len(erkannt) >= 0.85, erkannt


def test_fragen_zu_pbp_ohne_antwort_in_der_hilfe_bekommen_nie_eine_sichere_antwort(wissen):
    for f in gold.NICHT_BELEGT:
        erg = hs.suche(f, wissen=wissen)
        assert erg.status != "gefunden", (f, [t.abschnitt["id"] for t in erg.treffer[:2]])


def test_eine_antwort_ist_schnell(wissen):
    fragen = [f for _g, f, _e in gold.FRAGEN]
    t0 = time.perf_counter()
    for f in fragen:
        hs.suche(f, wissen=wissen)
    je_frage_ms = (time.perf_counter() - t0) / len(fragen) * 1000
    assert je_frage_ms < 120, f"{je_frage_ms:.0f} ms je Frage"


# ── gebaut: Woerter ─────────────────────────────────────────────────────────────────────────

def test_umschrift_und_woerter():
    assert hs.umschrift("Süd Größe Mähdrescher") == "sued groesse maehdrescher"
    assert hs.woerter("Wo steht „PBP“-Hilfe?") == ["wo", "steht", "pbp", "hilfe"]
    assert hs.woerter("") == []


def test_staemme_fassen_formen_zusammen():
    assert hs.stamm("nachfassung") == hs.stamm("nachfassungen") == hs.stamm("nachfassen")
    assert hs.stamm("aktualisiert") == hs.stamm("aktualisieren") == hs.stamm("aktualisierung")
    assert hs.stamm("pbp") == "pbp"
    assert hs.stamm("2026") == "2026"


def test_ein_trennbares_verb_wird_erkannt(wissen):
    """'lege ich eine Bewerbung an' meint 'anlegen'."""
    erg = hs.suche("Wie lege ich eine Bewerbung an?", wissen=wissen)
    assert any(t.abschnitt["id"].startswith(("wiki:Tab-Bewerbungen:bewerbung_anlegen", "faq:", "hilfe:bewerbungen", "wiki:Workflows"))
               for t in erg.treffer)
    assert "anleg" in erg.fragewoerter


def test_eine_leere_oder_zu_lange_frage(wissen):
    assert hs.suche("", wissen=wissen).status == "leer"
    assert hs.suche("   \n\t ", wissen=wissen).status == "leer"
    assert hs.suche(None, wissen=wissen).status == "leer"
    lang = "Wie aktualisiere ich PBP? " * 100
    assert len(hs.bereinige_frage(lang)) == hs.MAX_FRAGE
    assert hs.suche(lang, wissen=wissen).treffer, "eine lange Frage wird gekuerzt und beantwortet"


def test_nur_fuellwoerter_ergeben_keine_antwort(wissen):
    assert hs.suche("was ist das denn", wissen=wissen).status in ("nichts_gefunden", "ausserhalb")


def test_eine_frage_mit_markup_bleibt_text(wissen):
    """Die Frage wird nur gesucht und zurueckgegeben, nie ausgefuehrt; die Oberflaeche zeigt sie als Text."""
    a = hs.antwort("<script>alert(1)</script> Wie aktualisiere ich PBP?")
    assert a["frage"].startswith("<script>")
    assert all("<script" not in k["kurz"].lower() for k in a["karten"])


def test_eine_kurze_nachfrage_erbt_das_thema(wissen):
    ohne = hs.suche("und wo finde ich das?", wissen=wissen)
    mit = hs.suche("und wo finde ich das?", "Wie lege ich eine Bewerbung an?", wissen=wissen)
    assert mit.status != "ausserhalb"
    assert mit.treffer and (not ohne.treffer or ohne.treffer[0].abschnitt["id"] != mit.treffer[0].abschnitt["id"])
    assert any("bewerb" in t.abschnitt["id"].lower() or "bewerb" in t.abschnitt["titel"].lower() for t in mit.treffer)


def test_die_beispielfrage_aus_dem_wunsch_fuehrt_in_den_reiter_updates(wissen):
    """Die Frage, mit der #1233 beschrieben wurde: jede Karte fuehrt dorthin, wo man es einstellt."""
    a = hs.antwort("Wo stelle ich ein, dass sich PBP selbst aktualisiert?", wissen=wissen)
    assert a["status"] == "gefunden"
    assert all(k["oeffnen"] and k["oeffnen"]["art"] == "einstellung" and k["oeffnen"]["id"] == "updates" for k in a["karten"]), a["karten"]


def test_jeder_wiki_link_zeigt_ins_wiki_des_projekts(wissen):
    gesehen = 0
    for frage in ("Wo stelle ich ein, dass sich PBP selbst aktualisiert?", "Wie sichere ich meine Daten?", "Wie lege ich eine Bewerbung an?"):
        for k in hs.antwort(frage, wissen=wissen)["karten"]:
            if k["wiki"]:
                gesehen += 1
                assert k["wiki"]["url"].startswith("https://github.com/MadGapun/PBP/wiki/"), k["wiki"]
    assert gesehen, "keine Karte mit Wiki-Link: der Test hat nichts geprueft"


def _beispielfragen():
    """Die Beispielfragen der Oberflaeche (`BEISPIELFRAGEN` in lib/hilfeFrage.js)."""
    js = (WURZEL / "frontend" / "src" / "lib" / "hilfeFrage.js").read_text(encoding="utf-8")
    block = re.search(r"export const BEISPIELFRAGEN = \[(.*?)\];", js, re.S)
    assert block, "BEISPIELFRAGEN steht nicht mehr in lib/hilfeFrage.js"
    return re.findall(r'"([^"]+)"', block.group(1))


def test_jede_beispielfrage_fuehrt_zu_einer_sicheren_antwort_mit_weg_weiter(wissen):
    """Ein Beispiel zum Anklicken darf nie in eine Sackgasse fuehren; aendert ein neuer Bau der Wissensbasis das, faellt es hier auf."""
    fragen = _beispielfragen()
    assert 3 <= len(fragen) <= 5, fragen
    for f in fragen:
        a = hs.antwort(f, wissen=wissen)
        assert a["status"] == "gefunden", (f, a["status"])
        erste = a["karten"][0]
        assert erste["sicher"] and (erste["oeffnen"] or erste["wiki"] or erste["prompt"]), (f, erste["id"])


def _mini_wissen():
    """Zwoelf kurze Abschnitte: an einer Wissensbasis, die jeder Release neu baut, haengt keine Schwelle."""
    themen = [
        ("Updates automatisch installieren", "PBP kann Updates automatisch installieren. Die Einstellung steht unter Einstellungen im Reiter Updates."),
        ("Sicherung der Daten anlegen", "Eine Sicherung der Daten legst du im Reiter Sicherung an. Sie liegt in einem Ordner auf dem Rechner."),
        ("Bewerbung anlegen", "Eine Bewerbung legst du auf der Seite Bewerbungen an, mit Firma, Stelle und Datum."),
        ("Termin im Kalender eintragen", "Termine trägst du im Kalender ein. Zu jedem Termin gehört eine Bewerbung."),
        ("Aufgabe erledigen", "Aufgaben erledigst du mit einem Klick. Erledigte Aufgaben verschwinden aus der Liste."),
        ("Kontakt speichern", "Kontakte speichert PBP mit Name, Firma und Mail. Ein Kontakt lässt sich mit einer Bewerbung verknüpfen."),
        ("Dokument hochladen", "Dokumente lädst du auf der Seite Dokumente hoch. PBP liest den Text und ordnet das Dokument ein."),
        ("Stelle aussortieren", "Eine Stelle, die nicht passt, sortierst du mit einem Grund aus. Der Grund hilft beim Lernen."),
        ("Profil bearbeiten", "Dein Profil mit Lebenslauf, Fähigkeiten und Wünschen bearbeitest du auf der Seite Profil."),
        ("Lokale KI einschalten", "Die lokale KI schaltest du in den Einstellungen ein. Sie läuft über Ollama auf deinem Rechner."),
        ("Dashboard anpassen", "Das Dashboard passt du mit dem Zahnrad an. Du wählst, welche Karten zu sehen sind."),
        ("Jobsuche starten", "Die Jobsuche startest du auf der Seite Stellen. PBP fragt die eingestellten Quellen ab."),
    ]
    abschnitte = [{"id": f"hilfe:probe:{i}", "quelle": "hilfe", "titel": t, "pfad": "Hilfe", "ziel": None, "wiki": None, "prompt": None, "text": x}
                  for i, (t, x) in enumerate(themen)]
    return hs.Wissen.aus_daten({"seiten": {}, "reiter": {}, "abschnitte": abschnitte})


def test_ein_unbekanntes_wort_haelt_die_sichere_antwort_zurueck_auch_bei_guter_abdeckung():
    w = _mini_wissen()
    assert hs.suche("Updates automatisch installieren", wissen=w).status == "gefunden"
    mit = hs.suche("Updates automatisch Dieselmotor", wissen=w)
    beste = max(mit.treffer, key=lambda t: t.abdeckung)
    # Voraussetzung: die Abdeckung allein wuerde fuer "gefunden" reichen - nur das Wort, das die Hilfe nicht kennt, haelt die Antwort zurueck
    assert beste.abdeckung >= hs.ABDECKUNG_GEFUNDEN and mit.unbekannt >= hs.UNBEKANNT_GEFUNDEN, (beste.abdeckung, mit.unbekannt)
    assert mit.status == "unsicher"


# ── gebaut: die Antwort ─────────────────────────────────────────────────────────────────────

def test_eine_sichere_antwort_hat_karten_mit_gepruefen_zielen(wissen):
    a = hs.antwort("Wo schalte ich den hellen Modus ein?", wissen=wissen)
    assert a["status"] in ("gefunden", "unsicher")
    assert 1 <= len(a["karten"]) <= hs.MAX_KARTEN
    for k in a["karten"]:
        assert set(k) == {"id", "titel", "kurz", "quelle", "oeffnen", "wiki", "prompt", "sicher"}
        assert k["titel"] and k["kurz"] and k["quelle"]
        assert len(k["kurz"]) <= hs.KURZ_ZEICHEN + 3
        if k["oeffnen"]:
            assert k["oeffnen"]["art"] in ("seite", "einstellung")
            if k["oeffnen"]["art"] == "seite":
                assert k["oeffnen"]["id"] in wissen.seiten
            else:
                assert k["oeffnen"]["id"] in wissen.reiter
            assert k["oeffnen"]["label"].startswith("Öffnen: ")
        if k["wiki"]:
            assert k["wiki"]["url"].startswith(hs.WIKI_BASIS)
        if k["prompt"]:
            assert k["prompt"]["kopieren"].startswith("/") and k["prompt"]["titel"]


def test_der_pfad_zu_einem_reiter_kommt_aus_den_menuepfaden(wissen):
    from bewerbungs_assistent.services.menue import TRENNER
    ziel = {"art": "einstellung", "id": "updates"}
    o = hs.oeffnen_fuer(ziel, wissen)
    assert o["label"] == "Öffnen: Einstellungen" + TRENNER + wissen.reiter["updates"]["label"]


def test_ein_unbekanntes_ziel_wird_nie_angeboten(wissen):
    assert hs.oeffnen_fuer({"art": "seite", "id": "gibt_es_nicht"}, wissen) is None
    assert hs.oeffnen_fuer({"art": "einstellung", "id": "gibt_es_nicht"}, wissen) is None
    assert hs.oeffnen_fuer({"art": "url", "id": "https://boese.example"}, wissen) is None
    assert hs.oeffnen_fuer(None, wissen) is None
    assert hs.prompt_fuer("gibt_es_nicht") is None
    assert hs.prompt_fuer(None) is None
    assert hs.wiki_fuer(None) is None
    assert hs.wiki_fuer({"seite": ""}) is None


def test_der_wiki_link_traegt_den_anker():
    w = hs.wiki_fuer({"seite": "Updates", "anker": "die-vier-stufen"})
    assert w == {"seite": "Updates", "url": hs.WIKI_BASIS + "Updates#die-vier-stufen"}
    assert hs.wiki_fuer({"seite": "FAQ", "anker": ""})["url"] == hs.WIKI_BASIS + "FAQ"


def test_der_prompt_zum_kopieren_stammt_aus_dem_katalog(wissen):
    from bewerbungs_assistent.services import prompt_katalog
    p = hs.prompt_fuer("ersterfassung")
    e = prompt_katalog.eintrag("ersterfassung")
    assert p["id"] == "ersterfassung" and p["titel"] == e["titel"] and p["kopieren"] == "/" + (e.get("prompt") or e["id"])


def test_ausserhalb_nennt_den_grund_und_gibt_einen_satz_fuer_claude():
    a = hs.antwort("Wie wird das Wetter morgen?")
    assert a["status"] == "ausserhalb" and a["karten"] == []
    assert a["hinweis"] == hs.HINWEIS_AUSSERHALB
    assert a["claude"]["satz"] == hs.satz_fuer_claude("Wie wird das Wetter morgen?")
    assert "Wetter" in a["claude"]["satz"]


def test_nichts_gefunden_sagt_es_ehrlich():
    a = hs.antwort("Gibt es PBP als App fürs Handy?")
    assert a["status"] in ("nichts_gefunden", "unsicher")
    assert a["claude"], "immer ein Weg weiter: der Satz fuer Claude"
    if a["status"] == "nichts_gefunden":
        assert a["hinweis"] == hs.HINWEIS_NICHTS and a["karten"] == []
    else:
        assert a["hinweis"] == hs.HINWEIS_UNSICHER and all(not k["sicher"] for k in a["karten"])


def test_auch_eine_sichere_antwort_hat_den_satz_fuer_claude():
    """Auf ungesehene Fragen stimmt sie nur in rund drei von vier Faellen: "passt nicht" braucht einen Weg weiter."""
    a = hs.antwort("Wie aktualisiere ich PBP?")
    assert a["status"] == "gefunden" and a["hinweis"] == ""
    assert a["claude"]["satz"] == hs.satz_fuer_claude("Wie aktualisiere ich PBP?")
    assert a["karten"][0]["sicher"]


def test_eine_leere_frage_wird_freundlich_beantwortet():
    a = hs.antwort("   ")
    assert a["status"] == "leer" and a["karten"] == [] and "Frage" in a["hinweis"]


def test_gleiche_titel_erscheinen_nur_einmal(wissen):
    for _g, f, _e in gold.FRAGEN[:60]:
        titel = [hs.umschrift(t.abschnitt["titel"]) for t in hs.suche(f, wissen=wissen).treffer]
        assert len(titel) == len(set(titel)), (f, titel)


def test_die_suche_ist_deterministisch(wissen):
    f = "Wie hole ich einen früheren Stand meiner Daten zurück?"
    a = [t.abschnitt["id"] for t in hs.suche(f, wissen=wissen).treffer]
    assert a == [t.abschnitt["id"] for t in hs.suche(f, wissen=wissen).treffer]


def test_kurztext_kuerzt_am_satzende():
    text = "Erster Satz. " * 60
    k = hs.kurztext(text, 100)
    assert len(k) <= 100 and k.endswith(".")
    assert hs.kurztext("kurz", 100) == "kurz"
    ohne_punkt = hs.kurztext("wort " * 100, 50)
    assert ohne_punkt.endswith("…") and len(ohne_punkt) <= 56


# ── Datenschutz: die Frage wird nirgends hingeschrieben ─────────────────────────────────────

def test_die_frage_wird_weder_protokolliert_noch_gespeichert(tmp_path, caplog, monkeypatch):
    import logging
    caplog.set_level(logging.DEBUG)
    monkeypatch.setenv("BA_DATA_DIR", str(tmp_path))
    vorher = {p.name for p in tmp_path.rglob("*")}
    geheim = "Geheimfrage Zebrastreifen Quartz 7731"
    hs.antwort(geheim)
    hs.antwort(f"{geheim} Wie aktualisiere ich PBP?", "Vorherige Geheimfrage Pelikan 8842")
    assert not [r for r in caplog.records if "Zebrastreifen" in r.getMessage() or "Pelikan" in r.getMessage()]
    assert {p.name for p in tmp_path.rglob("*")} == vorher, "die Hilfe hat eine Datei geschrieben"


def test_das_modul_schreibt_nichts():
    """Quelltext-Probe: kein open(..., 'w'), kein sqlite, kein logger mit der Frage."""
    text = (WURZEL / "src" / "bewerbungs_assistent" / "services" / "hilfe_suche.py").read_text(encoding="utf-8")
    for verboten in ("sqlite3", "write_text", "write_bytes", "logger.", "logging.", "open("):
        assert verboten not in text.replace("Path(pfad).read_text", ""), verboten
