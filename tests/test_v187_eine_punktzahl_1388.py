"""#1388: In einer fit_analyse-Antwort steht genau eine Zahl unter dem Etikett Punkte."""
import re

import pytest

from test_g1087_welle2_punkte import _call, _stelle, umgebung  # noqa: F401


def _alle_punkte_saetze(obj, pfad=""):
    """Alle 'N von M Punkten'-Saetze samt Fundort."""
    funde = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            funde += _alle_punkte_saetze(v, f"{pfad}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            funde += _alle_punkte_saetze(v, f"{pfad}[{i}]")
    elif isinstance(obj, str):
        for m in re.finditer(r"(\d+(?:\.\d)?) von (\d+(?:\.\d)?) Punkten", obj):
            funde.append((pfad, m.group(0), obj))
    return funde


def test_mit_reglern_nur_eine_zahl_unter_punkte(umgebung):
    db, mcp, dash = umgebung
    voll, frisch = _stelle(db)
    db.set_scoring_config("keyword", "verhandlung", 2)   # Begriffs-Regler zaehlt
    erg = _call(mcp, "fit_analyse", {"job_hash": voll.split(":", 1)[-1]})
    emp = erg["empfehlung"]
    assert erg["punkte"] > frisch, "Regler muss die Punkte veraendern (Voraussetzung)"
    # ausserhalb von "Ohne deine Regler ..." steht ueberall derselbe Satz
    assert emp["punkte_text"] == erg["punkte_text"]
    sichtbar = [str(v) for k, v in emp.items()
                if k not in ("score_ohne_regler_text",) and isinstance(v, str)]
    zahlen = {m.group(1) for t in sichtbar
              for m in re.finditer(r"(\d+(?:\.\d)?) (?:von \d+(?:\.\d)? )?Punkt", t)}
    assert zahlen == {f"{erg['punkte']:g}"}, (zahlen, emp)
    assert emp["punkte_text"] == erg["punkte_text"]
    assert emp["punkte"] == erg["punkte"]
    assert emp["score"] == erg["punkte"], "'score' darf keine zweite Zahl sein"
    # die Zahl ohne Regler hat einen eigenen Namen und nennt das
    assert emp["score_ohne_regler"] == pytest.approx(erg["total_score"])
    assert "Ohne deine Regler" in emp["score_ohne_regler_text"]
    assert emp["score_ohne_regler_text"].startswith("Ohne deine Regler")


def test_ohne_regler_keine_zweite_zahl(umgebung):
    db, mcp, dash = umgebung
    voll, frisch = _stelle(db)
    erg = _call(mcp, "fit_analyse", {"job_hash": voll.split(":", 1)[-1]})
    assert erg["empfehlung"]["punkte_text"] == erg["punkte_text"]
    assert "score_ohne_regler" not in erg["empfehlung"]


def test_karte_liste_und_empfehlung_zeigen_dieselbe_zahl(umgebung):
    from fastapi.testclient import TestClient
    db, mcp, dash = umgebung
    voll, _ = _stelle(db)
    db.set_scoring_config("keyword", "verhandlung", 2)
    kurz = voll.split(":", 1)[-1]
    erg = _call(mcp, "fit_analyse", {"job_hash": kurz})
    liste = TestClient(dash.app).get("/api/jobs?active=true").json()
    jobs = liste["jobs"] if isinstance(liste, dict) else liste
    karte = next(j for j in jobs if str(j["hash"]).endswith("c96stelle"))
    mcp_liste = _call(mcp, "stellen_anzeigen", {"ohne_schwelle": True})
    zeile = next(e for e in mcp_liste["stellen"] if str(e["hash"]).endswith("c96stelle"))
    assert karte["punkte"] == erg["empfehlung"]["punkte"] == zeile["punkte"]
