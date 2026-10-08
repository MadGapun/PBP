"""Der Mutationskatalog darf nicht still veralten (Beta 16, 05.10.2026).

`scripts/mutationstest_auto_update.py` macht je Eintrag EINE Schutzpruefung wirkungslos und verlangt, dass die Tests rot werden. Jeder
Eintrag sucht dafuer eine Textstelle im Quelltext (`alt`). Aendert sich der Quelltext, passt das Muster nicht mehr ("MUSTER"), und die
Mutation prueft nichts mehr. Genau das war bei zwei Eintraegen des Firmen-Katalogs passiert (die Einrueckung von `firma_kontext` hatte
sich geaendert); keine Suite bemerkte es, weil der Katalog kein Teil der CI ist.

Dieser Test haelt nur die Voraussetzung fest, ohne eine Mutation auszufuehren: jedes Muster kommt in seiner Datei GENAU EINMAL vor, aus
`alt` wird wirklich etwas anderes, die Kennungen sind eindeutig, und die genannten Testdateien gibt es.
Pfade relativ zu dieser Datei (DoD 8c): gruen auch aus einem fremden Arbeitsverzeichnis.
"""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _katalog_modul():
    spec = importlib.util.spec_from_file_location("mutationstest_auto_update", ROOT / "scripts" / "mutationstest_auto_update.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_jedes_muster_kommt_in_seiner_datei_genau_einmal_vor():
    modul = _katalog_modul()
    abweichungen = []
    gesamt = 0
    for katalog, eintraege in modul.KATALOGE.items():
        for mid, _text, datei, alt, neu, _tests in eintraege:
            gesamt += 1
            pfad = ROOT / datei
            if not pfad.is_file():
                abweichungen.append(f"{katalog}/{mid}: Datei fehlt: {datei}")
                continue
            quelle = pfad.read_bytes().decode("utf-8-sig").replace("\r\n", "\n")
            n = quelle.count(alt)
            if n != 1:
                abweichungen.append(f"{katalog}/{mid}: Muster {n}x in {datei} (Eintrag nachziehen): {alt[:50]!r}")
            if alt == neu:
                abweichungen.append(f"{katalog}/{mid}: die Mutation aendert nichts")
    assert gesamt >= 230, f"nur {gesamt} Eintraege gelesen: ist der Katalog leer geworden?"
    assert not abweichungen, "\n".join(abweichungen)


def test_kennungen_sind_eindeutig_und_die_testdateien_gibt_es():
    modul = _katalog_modul()
    fehler = []
    for katalog, eintraege in modul.KATALOGE.items():
        ids = [e[0] for e in eintraege]
        doppelt = sorted({i for i in ids if ids.count(i) > 1})
        if doppelt:
            fehler.append(f"{katalog}: doppelte Kennungen {doppelt}")
        for mid, _text, _datei, _alt, _neu, tests in eintraege:
            for t in tests:
                if not (ROOT / t).is_file():
                    fehler.append(f"{katalog}/{mid}: Testdatei fehlt: {t}")
    assert not fehler, "\n".join(fehler)


def test_der_grundlauf_nennt_nur_vorhandene_testdateien():
    modul = _katalog_modul()
    fehler = []
    for katalog, laeufe in modul.GRUNDLAEUFE.items():
        for name, tests in laeufe:
            for t in tests:
                if not (ROOT / t).is_file():
                    fehler.append(f"{katalog}/{name}: Testdatei fehlt: {t}")
    assert not fehler, "\n".join(fehler)
