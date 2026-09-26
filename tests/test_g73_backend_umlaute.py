"""G73 — echte Umlaute auch in den Texten, die der Server ins Dashboard schickt.

G66 (v1.7.134) hat die Oberflaeche umgestellt und den Pruefer
`scripts/ui_texte_pruefen.py` in die CI gebracht. Er las nur das
Frontend. Tagesimpuls, Elwosa, Hinweise, Quellenbeschreibungen, Meldungen
der Endpunkte und die Faktoren im Fit-Dialog kommen vom Server — dort
stand "Nachfassen ist kein Stoeren" neben "HEUTE FÜR DICH".
"""
from __future__ import annotations

import importlib.util
import json
import re
from datetime import datetime
from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


SRC = _repo() / "src" / "bewerbungs_assistent"


def _pruefer():
    spec = importlib.util.spec_from_file_location(
        "ui_texte_pruefen", _repo() / "scripts" / "ui_texte_pruefen.py")
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_g73_pruefer_liest_die_backend_texte():
    """DoD 8c: der Pruefer laeuft ueber die echten Server-Dateien."""
    p = _pruefer()
    texte = [t for _, _, t in p.backend_texte()]
    assert any("Nachfassen ist kein Stören" in t for t in texte)
    namen = {pf.name for pf, _, _ in p.backend_texte()}
    assert {"elwosa_lines.py", "dashboard.py", "__init__.py", "tagesimpulse.json",
            "onboarding_hints.py", "workspace_service.py", "datenguete.py"} <= namen


def test_g73_pruefer_meldet_umschrift_im_backend(tmp_path, monkeypatch):
    p = _pruefer()
    datei = tmp_path / "beispiel.py"
    datei.write_text('MELDUNG = "Die Suche laeuft bereits."\n'
                     'MUSTER = ("wir zaehlen", "wir zählen")\n', encoding="utf-8")
    monkeypatch.setattr(p, "REPO", tmp_path)
    monkeypatch.setattr(p, "BACKEND_DATEIEN", [datei])
    monkeypatch.setattr(p, "UI_DATEIEN", [])
    monkeypatch.setattr(p, "katalog_texte", lambda: [])
    leer = tmp_path / "impulse.json"
    leer.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(p, "TAGESIMPULSE", leer)
    funde = p.pruefen()
    # Die Meldung ist ein Fund, das kleingeschriebene Suchmuster nicht.
    assert len(funde) == 1 and "laeuft" in funde[0], funde


def test_g73_keine_umschrift_im_tagesimpuls():
    p = _pruefer()
    for eintrag in json.loads((SRC / "content" / "tagesimpulse.json").read_text(encoding="utf-8")):
        assert not list(p.umlaut_funde(eintrag["text"])), eintrag["id"]


def test_g73_suchmuster_bleiben_unveraendert():
    """Kleingeschriebene Wortlisten vergleichen Text von aussen — Anzeigen
    und Mails schreiben mal so, mal so. Sie bleiben in beiden Formen."""
    quelle = (SRC / "job_scraper" / "__init__.py").read_text(encoding="utf-8")
    assert '"vollstaendig remote"' in quelle and '"vollständig remote"' in quelle
    assert '"wir zaehlen"' in quelle and '"wir zählen"' in quelle


def test_g73_fach_faktoren_passen_zu_den_praefixen():
    """Die Punkte zaehlen Faktoren des Fit-Dialogs ueber ihren Namensanfang
    (`punkte.FACH_PRAEFIXE`). Beim Umstellen wurden beide Seiten geaendert;
    ohne diesen Fall haette eine Seite allein die Deckel-Faktoren still aus
    den Punkten genommen."""
    from bewerbungs_assistent.services import punkte
    quelle = (SRC / "job_scraper" / "__init__.py").read_text(encoding="utf-8")
    labels = re.findall(r'factors\[f?"([^"]+)"\]', quelle)
    for praefix in ("Abzüge über Deckel", "Wunschbegriffe über Deckel"):
        assert praefix in punkte.FACH_PRAEFIXE
        assert any(lab.startswith(praefix) for lab in labels), praefix


def test_g73_elwosa_uhrzeit_und_monat_mit_umlaut():
    from bewerbungs_assistent.services import elwosa
    assert elwosa.format_uhrzeit(datetime(2026, 9, 26, 4, 30)) == "Halb fünf"
    assert elwosa.format_uhrzeit(datetime(2026, 9, 26, 0, 0)) == "Zwölf Uhr"
    assert "März" in elwosa.MONATSNAMEN


def test_g73_elwosa_erkennt_den_maerz_in_beiden_schreibweisen(monkeypatch):
    """Linien der lokalen KI koennen den Monat in Umschrift nennen."""
    from bewerbungs_assistent.services import elwosa

    class _Juli(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 7, 1, 12, 0)
    monkeypatch.setattr(elwosa, "datetime", _Juli)
    assert elwosa._nennt_falschen_monat("März. Alles ruhig.")
    assert elwosa._nennt_falschen_monat("Maerz. Alles ruhig.")
    assert not elwosa._nennt_falschen_monat("Juli. Alles ruhig.")
