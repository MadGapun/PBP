"""Auto-Update (#1093): Pruefsumme, Signatur, sicheres Entpacken, Manifest.

Akzeptanzkriterium 7: ohne gueltige Pruefsumme wird nichts installiert (Test mit manipuliertem Archiv).
Das Entpacken behandelt auch ein GEPRUEFTES Archiv als moeglicherweise boesartig.
"""
import base64
import hashlib
import io
import json
import stat
import zipfile
from pathlib import Path

import pytest
from _au_hilfen import release_bauen, schluessel_paar

from bewerbungs_assistent.services.auto_update import ed25519, entpacken, manifest, pruefung, schluessel
from bewerbungs_assistent.services.auto_update.fehler import UpdateFehler


def code(exc_info):
    return exc_info.value.code


# ══ Pruefsummenliste ═══════════════════════════════════════════════════════════════════

H1, H2 = "a" * 64, "b" * 64


def test_summen_lesen_im_format_von_sha256sum():
    text = f"{H1}  pbp-update-1.8.1.zip\n{H2} *anderes.zip\n\n# Kommentar\n"
    assert pruefung.summen_lesen(text) == {"pbp-update-1.8.1.zip": H1, "anderes.zip": H2}


def test_summen_lesen_normalisiert_grossbuchstaben_und_windows_zeilenenden():
    assert pruefung.summen_lesen(f"{H1.upper()}  x.zip\r\n") == {"x.zip": H1}


@pytest.mark.parametrize("zeile", ["kaputt", "abc  x.zip", f"{H1}x.zip", f"{H1}  ", f"{H1}  ../x.zip", f"{H1}  a/b.zip",
                                   f"{H1}  a\\b.zip", f"{'g' * 64}  x.zip", f"{H1}  .."])
def test_summen_lesen_lehnt_unlesbares_und_pfade_ab(zeile):
    with pytest.raises(UpdateFehler) as e:
        pruefung.summen_lesen(zeile + "\n")
    assert code(e) == "pruefsumme"


def test_widerspruechliche_summen_fuer_denselben_namen_sind_ein_fehler():
    with pytest.raises(UpdateFehler):
        pruefung.summen_lesen(f"{H1}  x.zip\n{H2}  x.zip\n")
    assert pruefung.summen_lesen(f"{H1}  x.zip\n{H1}  x.zip\n") == {"x.zip": H1}  # dieselbe Summe zweimal ist harmlos


def test_archiv_pruefen_akzeptiert_die_richtige_summe(tmp_path):
    f = tmp_path / "a.zip"
    f.write_bytes(b"inhalt")
    summe = hashlib.sha256(b"inhalt").hexdigest()
    r = pruefung.archiv_pruefen(f, "a.zip", f"{summe}  a.zip\n".encode())
    assert r.sha256 == summe and r.signiert is False


def test_ein_manipuliertes_archiv_wird_abgelehnt(tmp_path):
    f = tmp_path / "a.zip"
    f.write_bytes(b"inhalt")
    summe = hashlib.sha256(b"inhalt").hexdigest()
    f.write_bytes(b"inhalt!")                       # nach dem Veroeffentlichen veraendert
    with pytest.raises(UpdateFehler) as e:
        pruefung.archiv_pruefen(f, "a.zip", f"{summe}  a.zip\n".encode())
    assert code(e) == "pruefsumme"


def test_ein_archiv_das_nicht_in_der_liste_steht_wird_abgelehnt(tmp_path):
    f = tmp_path / "a.zip"
    f.write_bytes(b"x")
    with pytest.raises(UpdateFehler) as e:
        pruefung.archiv_pruefen(f, "a.zip", f"{H1}  anderes.zip\n".encode())
    assert code(e) == "pruefsumme"


def test_eine_summenliste_die_kein_utf8_ist_wird_abgelehnt(tmp_path):
    f = tmp_path / "a.zip"
    f.write_bytes(b"x")
    with pytest.raises(UpdateFehler) as e:
        pruefung.archiv_pruefen(f, "a.zip", b"\xff\xfe\x00")
    assert code(e) == "pruefsumme"


# ══ Signatur ═══════════════════════════════════════════════════════════════════════════

def _signatur(geheim: bytes, daten: bytes) -> str:
    return base64.b64encode(ed25519.signieren(geheim, daten)).decode()


SUMMEN = f"{H1}  pbp-update-1.8.1.zip\n".encode()


def test_ohne_vertrauten_schluessel_wird_keine_signatur_verlangt():
    assert schluessel.signatur_erforderlich({}) is False
    assert pruefung.signatur_pruefen(SUMMEN, None, schluessel={}) == ""


def test_mit_vertrautem_schluessel_gilt_eine_passende_signatur():
    geheim = bytes([5] * 32)
    keys = {"haupt": ed25519.geheim_zu_oeffentlich(geheim).hex()}
    assert pruefung.signatur_pruefen(SUMMEN, _signatur(geheim, SUMMEN), schluessel=keys) == "haupt"


def test_jeder_der_vertrauten_schluessel_darf_signieren():
    haupt, notfall = bytes([5] * 32), bytes([6] * 32)
    keys = {"haupt": ed25519.geheim_zu_oeffentlich(haupt).hex(), "notfall": ed25519.geheim_zu_oeffentlich(notfall).hex()}
    assert pruefung.signatur_pruefen(SUMMEN, _signatur(notfall, SUMMEN), schluessel=keys) == "notfall"


def test_mit_vertrautem_schluessel_ist_eine_fehlende_signatur_ein_fehler():
    keys = {"haupt": ed25519.geheim_zu_oeffentlich(bytes([5] * 32)).hex()}
    for fehlt in (None, "", "   \n", b""):
        with pytest.raises(UpdateFehler) as e:
            pruefung.signatur_pruefen(SUMMEN, fehlt, schluessel=keys)
        assert code(e) == "signatur"


def test_eine_signatur_ueber_eine_andere_liste_wird_abgelehnt():
    geheim = bytes([5] * 32)
    keys = {"haupt": ed25519.geheim_zu_oeffentlich(geheim).hex()}
    sig = _signatur(geheim, SUMMEN)
    with pytest.raises(UpdateFehler) as e:
        pruefung.signatur_pruefen(SUMMEN + b"# eingeschmuggelt\n", sig, schluessel=keys)
    assert code(e) == "signatur"


def test_eine_signatur_eines_fremden_schluessels_wird_abgelehnt():
    keys = {"haupt": ed25519.geheim_zu_oeffentlich(bytes([5] * 32)).hex()}
    with pytest.raises(UpdateFehler) as e:
        pruefung.signatur_pruefen(SUMMEN, _signatur(bytes([9] * 32), SUMMEN), schluessel=keys)
    assert code(e) == "signatur"


@pytest.mark.parametrize("sig", ["kein base64!!", "AAAA", base64.b64encode(b"x" * 63).decode(), base64.b64encode(b"x" * 65).decode()])
def test_kaputte_signaturdateien_werden_abgelehnt(sig):
    keys = {"haupt": ed25519.geheim_zu_oeffentlich(bytes([5] * 32)).hex()}
    with pytest.raises(UpdateFehler) as e:
        pruefung.signatur_pruefen(SUMMEN, sig, schluessel=keys)
    assert code(e) == "signatur"


def test_ein_unbrauchbarer_eintrag_in_der_schluesselliste_macht_das_pruefen_strenger_nie_laxer():
    """Nur kaputte Schluessel konfiguriert: die Signatur ist verlangt, und nichts kann sie erfuellen -> alles abgelehnt."""
    keys = {"kaputt": "kein-hex"}
    assert schluessel.signatur_erforderlich(keys) is True
    geheim = bytes([5] * 32)
    with pytest.raises(UpdateFehler) as e:
        pruefung.signatur_pruefen(SUMMEN, _signatur(geheim, SUMMEN), schluessel=keys)
    assert code(e) == "signatur"


def test_signatur_mit_zeilenumbruechen_in_der_datei_wird_gelesen():
    geheim = bytes([5] * 32)
    keys = {"haupt": ed25519.geheim_zu_oeffentlich(geheim).hex()}
    sig = _signatur(geheim, SUMMEN)
    umgebrochen = sig[:30] + "\r\n" + sig[30:] + "\n"
    assert pruefung.signatur_pruefen(SUMMEN, umgebrochen, schluessel=keys) == "haupt"


# ══ Entpacken ══════════════════════════════════════════════════════════════════════════

def _zip(pfad: Path, eintraege: dict, *, symlinks=()) -> Path:
    with zipfile.ZipFile(pfad, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, inhalt in eintraege.items():
            info = zipfile.ZipInfo(name)
            info.external_attr = (0o120777 << 16) if name in symlinks else (0o100644 << 16)
            zf.writestr(info, inhalt, compress_type=zipfile.ZIP_DEFLATED)
    return pfad


GUTE_DATEIEN = {"manifest.json": "{}", "src/bewerbungs_assistent/__init__.py": "x = 1\n",
                "start_dashboard.py": "pass\n", "_selftest.py": "print('OK')\n"}


def test_ein_sauberes_archiv_wird_entpackt(tmp_path):
    ziel = tmp_path / "ziel"
    r = entpacken.entpacken(_zip(tmp_path / "a.zip", GUTE_DATEIEN), ziel)
    assert r["dateien"] == 4
    assert (ziel / "src" / "bewerbungs_assistent" / "__init__.py").read_text() == "x = 1\n"


@pytest.mark.parametrize("name", [
    "../evil.py", "src/../../evil.py", "/etc/passwd", "C:/Windows/evil.py", "src\\..\\evil.py", "src/a:b.py",
    "src/CON.py", "src/aux", "src/nul.txt", "src/COM1.py", "src/LPT9.log", "src/name.", "src/ name.py", "src//doppelt.py",
    "src/./x.py",
])
def test_unsichere_pfade_lehnen_das_ganze_archiv_ab(tmp_path, name):
    ziel = tmp_path / "ziel"
    with pytest.raises(UpdateFehler) as e:
        entpacken.entpacken(_zip(tmp_path / "a.zip", {**GUTE_DATEIEN, name: "boese"}), ziel)
    assert code(e) == "archiv_unsicher"
    assert not ziel.exists()                       # nichts bleibt liegen
    assert not (tmp_path / "evil.py").exists()


@pytest.mark.parametrize("endung", [".exe", ".dll", ".pyd", ".so", ".bat", ".cmd", ".ps1", ".vbs", ".msi", ".scr", ".lnk", ".jar", ".EXE"])
def test_ausfuehrbare_dateien_sind_im_archiv_verboten(tmp_path, endung):
    with pytest.raises(UpdateFehler) as e:
        entpacken.entpacken(_zip(tmp_path / "a.zip", {**GUTE_DATEIEN, f"src/bewerbungs_assistent/x{endung}": "MZ"}), tmp_path / "ziel")
    assert code(e) == "archiv_unsicher"


@pytest.mark.parametrize("name", ["evil.py", "installer.bat", "docs/readme.txt", "python/python.exe", "boot/x.py"])
def test_an_der_wurzel_ist_nur_das_vorgesehene_erlaubt(tmp_path, name):
    with pytest.raises(UpdateFehler) as e:
        entpacken.entpacken(_zip(tmp_path / "a.zip", {**GUTE_DATEIEN, name: "x"}), tmp_path / "ziel")
    assert code(e) == "archiv_unsicher"


def test_verknuepfungen_sind_verboten(tmp_path):
    z = _zip(tmp_path / "a.zip", {**GUTE_DATEIEN, "src/link": "C:/Windows"}, symlinks=("src/link",))
    with pytest.raises(UpdateFehler) as e:
        entpacken.entpacken(z, tmp_path / "ziel")
    assert code(e) == "archiv_unsicher" and "Verknuepfung" in e.value.detail


def test_zwei_eintraege_die_sich_nur_in_der_schreibweise_unterscheiden_sind_verboten(tmp_path):
    z = _zip(tmp_path / "a.zip", {**GUTE_DATEIEN, "src/Datei.py": "1", "src/datei.py": "2"})
    with pytest.raises(UpdateFehler) as e:
        entpacken.entpacken(z, tmp_path / "ziel")
    assert code(e) == "archiv_unsicher"


def test_ohne_manifest_ist_ein_archiv_unvollstaendig(tmp_path):
    z = _zip(tmp_path / "a.zip", {k: v for k, v in GUTE_DATEIEN.items() if k != "manifest.json"})
    with pytest.raises(UpdateFehler) as e:
        entpacken.entpacken(z, tmp_path / "ziel")
    assert code(e) == "archiv_unsicher" and "manifest" in e.value.detail


def test_ein_leeres_oder_kaputtes_archiv_wird_abgelehnt(tmp_path):
    leer = tmp_path / "leer.zip"
    zipfile.ZipFile(leer, "w").close()
    kaputt = tmp_path / "kaputt.zip"
    kaputt.write_bytes(b"PK\x03\x04 nur Muell")
    for z in (leer, kaputt, tmp_path / "gibtsnicht.zip"):
        with pytest.raises(UpdateFehler) as e:
            entpacken.entpacken(z, tmp_path / "ziel")
        assert code(e) == "archiv_unsicher"
        assert not (tmp_path / "ziel").exists()


def test_eine_zip_bombe_wird_erkannt(tmp_path, monkeypatch):
    monkeypatch.setattr(entpacken, "MAX_GESAMT_BYTES", 50 * 1024 * 1024)
    z = _zip(tmp_path / "bombe.zip", {**GUTE_DATEIEN, "src/bewerbungs_assistent/leer.dat": b"\0" * (30 * 1024 * 1024)})
    with pytest.raises(UpdateFehler) as e:
        entpacken.entpacken(z, tmp_path / "ziel")
    assert code(e) == "archiv_unsicher" and "gepackt" in e.value.detail


def test_zu_viele_dateien_werden_abgelehnt(tmp_path, monkeypatch):
    monkeypatch.setattr(entpacken, "MAX_DATEIEN", 10)
    dateien = {**GUTE_DATEIEN, **{f"src/bewerbungs_assistent/m{i}.py": "x" for i in range(20)}}
    with pytest.raises(UpdateFehler) as e:
        entpacken.entpacken(_zip(tmp_path / "a.zip", dateien), tmp_path / "ziel")
    assert code(e) == "archiv_unsicher"


def test_zu_viel_insgesamt_wird_abgelehnt(tmp_path, monkeypatch):
    monkeypatch.setattr(entpacken, "MAX_GESAMT_BYTES", 1000)
    dateien = {**GUTE_DATEIEN, "src/bewerbungs_assistent/gross.py": "x" * 5000}
    with pytest.raises(UpdateFehler):
        entpacken.entpacken(_zip(tmp_path / "a.zip", dateien), tmp_path / "ziel")


def test_ein_nicht_leeres_ziel_wird_nie_beschrieben(tmp_path):
    ziel = tmp_path / "ziel"
    ziel.mkdir()
    (ziel / "alt.txt").write_text("bleibt")
    with pytest.raises(UpdateFehler):
        entpacken.entpacken(_zip(tmp_path / "a.zip", GUTE_DATEIEN), ziel)
    assert (ziel / "alt.txt").read_text() == "bleibt"


def test_ein_beschaedigter_eintrag_raeumt_das_halb_entpackte_ziel_weg(tmp_path):
    z = tmp_path / "a.zip"
    with zipfile.ZipFile(z, "w", zipfile.ZIP_STORED) as zf:        # unkomprimiert: die Nutzdaten stehen im Klartext
        for name, inhalt in GUTE_DATEIEN.items():
            zf.writestr(name, inhalt)
    daten = bytearray(z.read_bytes())
    spur = daten.rfind(b"print('OK')")
    assert spur > 0
    daten[spur] ^= 0xFF                                             # Nutzdaten veraendern, Pruefsumme (CRC) bleibt
    z.write_bytes(bytes(daten))
    with pytest.raises(UpdateFehler) as e:
        entpacken.entpacken(z, tmp_path / "ziel")
    assert code(e) == "archiv_unsicher"
    assert not (tmp_path / "ziel").exists()


# ══ Manifest ═══════════════════════════════════════════════════════════════════════════

def _manifest(**aend):
    m = {"format": 1, "version": "1.8.1", "linie": "1.8", "boot_format": 1, "python": {"min": "3.11", "unter": "4"},
         "schema": 52, "requirements": ["httpx>=0.27"], "requirements_optional": [], "auto_update_moeglich": True,
         "braucht_installer": "", "changelog": ["Ein Satz."], "erstellt": "2026-10-02T10:00:00Z"}
    m.update(aend)
    return json.dumps(m)


def test_ein_gueltiges_manifest_wird_gelesen():
    m = manifest.lesen(_manifest(), erwartete_version="1.8.1")
    assert m.version == "1.8.1" and m.linie == "1.8" and m.python_min == (3, 11) and m.python_unter == (4,)
    assert m.requirements == ("httpx>=0.27",) and m.changelog == ("Ein Satz.",) and m.auto_update_moeglich is True


def test_manifest_aus_datei_und_mit_bom(tmp_path):
    p = tmp_path / "manifest.json"
    p.write_bytes(b"\xef\xbb\xbf" + _manifest().encode())
    assert manifest.lesen(p, erwartete_version="1.8.1").version == "1.8.1"


@pytest.mark.parametrize("aend,erwartet", [
    ({"version": "1.8.2"}, "manifest"),                      # enthaelt eine andere Fassung als angekuendigt
    ({"version": "1.8.1-beta.1"}, "manifest"),
    ({"linie": "1.9"}, "manifest"),
    ({"format": 2}, "braucht_installer"),
    ({"format": "1"}, "braucht_installer"),
    ({"boot_format": 0}, "manifest"),
    ({"boot_format": True}, "manifest"),
    ({"python": []}, "manifest"),
    ({"python": {"min": "drei"}}, "manifest"),
    ({"schema": "52"}, "manifest"),
    ({"auto_update_moeglich": "ja"}, "manifest"),
    ({"requirements": "fastmcp"}, "manifest"),
    ({"requirements": [1, 2]}, "manifest"),
    ({"changelog": {"a": 1}}, "manifest"),
])
def test_ein_ungueltiges_manifest_wird_abgelehnt(aend, erwartet):
    with pytest.raises(UpdateFehler) as e:
        manifest.lesen(_manifest(**aend), erwartete_version="1.8.1")
    assert code(e) == erwartet


@pytest.mark.parametrize("roh", ["", "[]", "kein json", "null", '"text"'])
def test_manifest_das_kein_objekt_ist_wird_abgelehnt(roh):
    with pytest.raises(UpdateFehler) as e:
        manifest.lesen(roh, erwartete_version="1.8.1")
    assert code(e) == "manifest"


def test_changelog_ist_auf_acht_zeilen_begrenzt():
    m = manifest.lesen(_manifest(changelog=[f"Satz {i}" for i in range(20)]), erwartete_version="1.8.1")
    assert len(m.changelog) == 8


def _geprueft(**aend):
    m = manifest.lesen(_manifest(**aend), erwartete_version="1.8.1")
    return m


def test_fuer_diesen_rechner_passt_ein_normales_update():
    manifest.fuer_diesen_rechner_pruefen(_geprueft(), laufende_fassung="1.8.0", python=(3, 12, 10), boot_format=1)


def test_ein_linienwechsel_braucht_den_installer():
    with pytest.raises(UpdateFehler) as e:
        manifest.fuer_diesen_rechner_pruefen(_geprueft(), laufende_fassung="1.7.150", python=(3, 12, 10), boot_format=1)
    assert code(e) == "braucht_installer"


def test_ein_zurueck_oder_gleiche_fassung_ist_schon_aktuell():
    for laufend in ("1.8.1", "1.8.2"):
        with pytest.raises(UpdateFehler) as e:
            manifest.fuer_diesen_rechner_pruefen(_geprueft(), laufende_fassung=laufend, python=(3, 12, 10), boot_format=1)
        assert code(e) == "schon_aktuell"


def test_auto_update_moeglich_false_braucht_den_installer_mit_dem_grund_aus_dem_manifest():
    m = _geprueft(auto_update_moeglich=False, braucht_installer="Neue Python-Laufzeit 3.13.")
    with pytest.raises(UpdateFehler) as e:
        manifest.fuer_diesen_rechner_pruefen(m, laufende_fassung="1.8.0", python=(3, 12, 10), boot_format=1)
    assert code(e) == "braucht_installer" and e.value.text == "Neue Python-Laufzeit 3.13."


def test_ein_neuerer_startbaustein_braucht_den_installer():
    with pytest.raises(UpdateFehler) as e:
        manifest.fuer_diesen_rechner_pruefen(_geprueft(boot_format=2), laufende_fassung="1.8.0", python=(3, 12, 10), boot_format=1)
    assert code(e) == "braucht_installer" and "Startbaustein" in e.value.text


@pytest.mark.parametrize("python,ok", [((3, 11, 0), True), ((3, 12, 10), True), ((3, 10, 14), False), ((4, 0, 0), False)])
def test_die_python_grenzen_werden_geprueft(python, ok):
    if ok:
        manifest.fuer_diesen_rechner_pruefen(_geprueft(), laufende_fassung="1.8.0", python=python, boot_format=1)
    else:
        with pytest.raises(UpdateFehler) as e:
            manifest.fuer_diesen_rechner_pruefen(_geprueft(), laufende_fassung="1.8.0", python=python, boot_format=1)
        assert code(e) == "braucht_installer" and "Python" in e.value.text


def test_obergrenze_der_python_laufzeit_wird_beachtet():
    m = _geprueft(python={"min": "3.11", "unter": "3.13"})
    manifest.fuer_diesen_rechner_pruefen(m, laufende_fassung="1.8.0", python=(3, 12, 10), boot_format=1)
    with pytest.raises(UpdateFehler):
        manifest.fuer_diesen_rechner_pruefen(m, laufende_fassung="1.8.0", python=(3, 13, 0), boot_format=1)


# ══ Ein echtes Archiv durch alle Pruefungen ═══════════════════════════════════════════

def test_ein_vom_builder_gebautes_archiv_besteht_alle_pruefungen(tmp_path):
    rel = release_bauen(tmp_path, "1.8.1")
    archiv = tmp_path / rel.archiv_name
    archiv.write_bytes(rel.dateien[rel.archiv_name])
    r = pruefung.archiv_pruefen(archiv, rel.archiv_name, rel.dateien["SHA256SUMS"])
    assert r.sha256 == rel.ergebnis["sha256"]
    ziel = tmp_path / "entpackt"
    entpacken.entpacken(archiv, ziel)
    m = manifest.lesen(ziel / "manifest.json", erwartete_version="1.8.1")
    assert m.requirements == ("fastmcp>=3.0,<4", "httpx>=0.27") and m.requirements_optional == ("pypdf>=4.0",)
    assert m.changelog[0].startswith("Neue Hinweise im Dashboard")
    assert (ziel / "src" / "bewerbungs_assistent" / "__init__.py").read_text().strip() == '__version__ = "1.8.1"'


def test_der_builder_signiert_und_die_signatur_besteht_die_pruefung(tmp_path, monkeypatch):
    datei, keys = schluessel_paar(tmp_path)
    monkeypatch.setattr(schluessel, "VERTRAUTE_SCHLUESSEL", keys)
    rel = release_bauen(tmp_path, "1.8.1", schluessel_datei=datei)
    assert "SHA256SUMS.sig" in rel.dateien and rel.ergebnis["signiert"] is True
    assert pruefung.signatur_pruefen(rel.dateien["SHA256SUMS"], rel.dateien["SHA256SUMS.sig"].decode()) == "haupt"


def test_der_builder_baut_reproduzierbar(tmp_path):
    a = release_bauen(tmp_path / "a", "1.8.1")
    b = release_bauen(tmp_path / "b", "1.8.1")
    za, zb = zipfile.ZipFile(io.BytesIO(a.dateien[a.archiv_name])), zipfile.ZipFile(io.BytesIO(b.dateien[b.archiv_name]))
    assert za.namelist() == zb.namelist()
    for n in za.namelist():
        if n != "manifest.json":                    # das Manifest traegt den Bauzeitpunkt
            assert za.read(n) == zb.read(n)


# ══ Gegenprobe (Mutationstest): Luecken, die ein absichtlich eingebauter Fehler aufgedeckt hat ═══════

@pytest.mark.parametrize("name", [
    "/src/x.py",              # absolut
    "src\\x.py",              # Rueckwaertsschraeg: unter Windows ein Pfadtrenner
    "src/x.py:strom",         # NTFS-Datenstrom
    "C:x.py",                 # Laufwerk
    "src/a\x00b.py",          # NUL
    "",                       # leer
])
def test_jedes_einzelne_pfadmuster_wird_von_der_ersten_schicht_abgewiesen(name):
    """Die Pfadpruefung hat mehrere Schichten; jedes Muster muss schon an der ersten scheitern, nicht erst zufaellig an
    einer spaeteren (so ueberlebte ein Mutant, der die erste Zeile unwirksam machte)."""
    from bewerbungs_assistent.services.auto_update import entpacken
    from bewerbungs_assistent.services.auto_update.fehler import UpdateFehler
    with pytest.raises(UpdateFehler) as fehler:
        entpacken._pfad_pruefen(name)
    assert fehler.value.code == "archiv_unsicher"
    assert "Pfad nicht erlaubt" in fehler.value.detail


def test_eine_einzeldatei_ueber_der_grenze_wird_schon_beim_pruefen_abgelehnt(tmp_path, monkeypatch):
    """Nicht erst beim Schreiben (`mehr Daten als angekuendigt`), sondern vorher, an der angekuendigten Groesse."""
    import os
    from bewerbungs_assistent.services.auto_update import entpacken
    from bewerbungs_assistent.services.auto_update.fehler import UpdateFehler
    monkeypatch.setattr(entpacken, "MAX_EINZEL_BYTES", 1000)
    archiv = tmp_path / "gross.zip"
    with zipfile.ZipFile(archiv, "w") as zf:
        zf.writestr("manifest.json", "{}")
        zf.writestr("src/gross.bin", os.urandom(5000))       # unkomprimierbar: das Verhaeltnis loest nichts aus
    with pytest.raises(UpdateFehler) as fehler:
        entpacken.entpacken(archiv, tmp_path / "ziel")
    assert "Datei zu gross" in fehler.value.detail, fehler.value.detail
    assert not (tmp_path / "ziel").exists(), "nach der Ablehnung bleibt nichts zurueck"


def test_die_zweite_schicht_faengt_einen_fehler_der_ersten(tmp_path, monkeypatch):
    """Selbst wenn die Pfadpruefung einmal einen Pfad durchliesse, schreibt `entpacken` nie ausserhalb des Ziels."""
    from pathlib import PurePosixPath
    from bewerbungs_assistent.services.auto_update import entpacken
    from bewerbungs_assistent.services.auto_update.fehler import UpdateFehler
    echt = entpacken._pfad_pruefen
    monkeypatch.setattr(entpacken, "_pfad_pruefen",
                        lambda n: PurePosixPath("src/../../ausserhalb.py") if n == "src/ok.py" else echt(n))
    archiv = tmp_path / "boese.zip"
    with zipfile.ZipFile(archiv, "w") as zf:
        zf.writestr("manifest.json", "{}")
        zf.writestr("src/ok.py", "print('x')\n")
    ziel = tmp_path / "ziel"
    with pytest.raises(UpdateFehler) as fehler:
        entpacken.entpacken(archiv, ziel)
    assert fehler.value.code == "archiv_unsicher" and "ausserhalb" in fehler.value.detail
    assert not (tmp_path / "ausserhalb.py").exists() and not (ziel.parent / "ausserhalb.py").exists()


def test_eine_signatur_falscher_laenge_wird_mit_dem_grund_abgewiesen():
    import base64
    from bewerbungs_assistent.services.auto_update import pruefung
    from bewerbungs_assistent.services.auto_update.fehler import UpdateFehler
    with pytest.raises(UpdateFehler) as fehler:
        pruefung.signatur_lesen(base64.b64encode(b"x" * 63).decode("ascii"))
    assert fehler.value.code == "signatur" and "63 statt 64 Byte" in fehler.value.detail
