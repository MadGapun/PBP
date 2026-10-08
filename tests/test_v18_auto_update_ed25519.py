"""Auto-Update (#1093): Ed25519 in reinem Python — RFC-8032-Vektoren, Ablehnung, Gegenprobe gegen `cryptography`.

Die Signatur ist der Teil der Pruefkette, der ein ausgetauschtes Release erkennt (eine
Pruefsumme neben dem Archiv tauscht der Angreifer mit aus). Deshalb gilt hier die
strengste Regel des ganzen Moduls: im Zweifel False, nie eine Ausnahme, nie ein
stilles True.
"""
import os
import random

import pytest

from bewerbungs_assistent.services.auto_update import ed25519 as ed

# RFC 8032, Abschnitt 7.1 (Test 1 bis 3): geheim, oeffentlich, Nachricht, Signatur.
VEKTOREN = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
     "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
     "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
     "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]


@pytest.mark.parametrize("geheim,oeffentlich,nachricht,signatur", VEKTOREN)
def test_rfc8032_vektoren(geheim, oeffentlich, nachricht, signatur):
    geheim_b, nachricht_b = bytes.fromhex(geheim), bytes.fromhex(nachricht)
    assert ed.geheim_zu_oeffentlich(geheim_b).hex() == oeffentlich
    assert ed.signieren(geheim_b, nachricht_b).hex() == signatur
    assert ed.pruefen(bytes.fromhex(oeffentlich), nachricht_b, bytes.fromhex(signatur)) is True


def _paar(nachricht=b"PBP-Update 1.8.1"):
    geheim = bytes(range(32))
    return geheim, ed.geheim_zu_oeffentlich(geheim), nachricht


def test_signieren_ist_deterministisch():
    geheim, _, nachricht = _paar()
    assert ed.signieren(geheim, nachricht) == ed.signieren(geheim, nachricht)


def test_eine_geaenderte_nachricht_wird_abgelehnt():
    geheim, oeffentlich, nachricht = _paar()
    signatur = ed.signieren(geheim, nachricht)
    assert ed.pruefen(oeffentlich, nachricht, signatur) is True
    assert ed.pruefen(oeffentlich, nachricht + b"x", signatur) is False
    assert ed.pruefen(oeffentlich, b"", signatur) is False


@pytest.mark.parametrize("stelle", [0, 5, 31, 32, 40, 63])
def test_ein_gekipptes_bit_in_der_signatur_wird_abgelehnt(stelle):
    geheim, oeffentlich, nachricht = _paar()
    signatur = bytearray(ed.signieren(geheim, nachricht))
    signatur[stelle] ^= 0x01
    assert ed.pruefen(oeffentlich, nachricht, bytes(signatur)) is False


def test_ein_fremder_schluessel_wird_abgelehnt():
    geheim, _, nachricht = _paar()
    signatur = ed.signieren(geheim, nachricht)
    fremd = ed.geheim_zu_oeffentlich(bytes(reversed(range(32))))
    assert ed.pruefen(fremd, nachricht, signatur) is False


def test_die_veraenderte_signatur_mit_s_plus_q_wird_abgelehnt():
    """Dieselbe Gleichung gilt modulo q — ohne die Pruefung `s < q` waere diese Signatur gueltig.

    Gegenprobe der Pruefung: wer sie ausbaut, laesst eine zweite, formal andere Signatur
    derselben Nachricht durch (Formbarkeit). Fuer uns hiesse das: ein Archiv hat zwei
    gueltige Signaturdateien, und ein Vergleich von Signaturen wuerde ins Leere laufen.
    """
    geheim, oeffentlich, nachricht = _paar()
    signatur = ed.signieren(geheim, nachricht)
    s = int.from_bytes(signatur[32:], "little")
    verformt = signatur[:32] + int.to_bytes(s + ed._Q, 32, "little")
    assert len(verformt) == 64
    assert ed.pruefen(oeffentlich, nachricht, verformt) is False


@pytest.mark.parametrize("oeffentlich", [b"", b"x" * 31, b"x" * 33, None, "abc", 5, [1, 2]])
def test_kaputte_oeffentliche_schluessel_geben_false_und_werfen_nie(oeffentlich):
    _, _, nachricht = _paar()
    signatur = ed.signieren(bytes(range(32)), nachricht)
    assert ed.pruefen(oeffentlich, nachricht, signatur) is False


@pytest.mark.parametrize("signatur", [b"", b"x" * 63, b"x" * 65, None, "abc", 5, b"\xff" * 64, b"\x00" * 64])
def test_kaputte_signaturen_geben_false_und_werfen_nie(signatur):
    _, oeffentlich, nachricht = _paar()
    assert ed.pruefen(oeffentlich, nachricht, signatur) is False


def test_ein_punkt_der_nicht_auf_der_kurve_liegt_wird_abgelehnt():
    _, _, nachricht = _paar()
    # y = 2 hat kein x auf der Kurve; zusammen mit einer sonst wohlgeformten Signatur
    ausserhalb = (2).to_bytes(32, "little")
    signatur = ed.signieren(bytes(range(32)), nachricht)
    assert ed.pruefen(ausserhalb, nachricht, signatur) is False
    assert ed.pruefen(ed.geheim_zu_oeffentlich(bytes(range(32))), nachricht, ausserhalb + signatur[32:]) is False


def test_der_geheime_schluessel_muss_32_byte_lang_sein():
    with pytest.raises(ValueError):
        ed.signieren(b"kurz", b"x")
    with pytest.raises(ValueError):
        ed.geheim_zu_oeffentlich(b"x" * 33)


def test_nachricht_als_bytearray_wird_wie_bytes_geprueft():
    geheim, oeffentlich, nachricht = _paar()
    signatur = ed.signieren(geheim, nachricht)
    assert ed.pruefen(bytearray(oeffentlich), bytearray(nachricht), bytearray(signatur)) is True


def test_gegen_die_bibliothek_cryptography():
    """Unabhaengige Gegenprobe: gleiche Schluessel und Signaturen wie eine andere Umsetzung."""
    pytest.importorskip("cryptography")
    from cryptography.hazmat.primitives import serialization as s
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    zufall = random.Random(20261002)
    for _ in range(25):
        geheim = bytes(zufall.getrandbits(8) for _ in range(32))
        nachricht = bytes(zufall.getrandbits(8) for _ in range(zufall.randint(0, 300)))
        schluessel = Ed25519PrivateKey.from_private_bytes(geheim)
        oeffentlich = schluessel.public_key().public_bytes(s.Encoding.Raw, s.PublicFormat.Raw)
        signatur = schluessel.sign(nachricht)
        assert ed.geheim_zu_oeffentlich(geheim) == oeffentlich
        assert ed.signieren(geheim, nachricht) == signatur
        assert ed.pruefen(oeffentlich, nachricht, signatur) is True
        assert ed.pruefen(oeffentlich, nachricht + b"!", signatur) is False
