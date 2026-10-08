"""Ed25519 (RFC 8032) in reinem Python — Signatur pruefen und erzeugen.

Wozu: das Auto-Update (#1093) installiert Code ohne Rueckfrage. Eine Pruefsumme
neben dem Archiv schuetzt gegen eine kaputte Uebertragung, aber nicht gegen ein
ausgetauschtes Release: wer die Datei austauschen kann, tauscht die Pruefsumme
mit aus. Eine Signatur mit einem Schluessel, der nicht bei GitHub liegt, schliesst
genau diese Luecke. Der oeffentliche Schluessel steht im Code (`schluessel.py`).

Warum selbst geschrieben: in der Embeddable-Python-Laufzeit des Installers gibt es
weder `cryptography` noch `nacl`, und das Pruefen einer einzigen Signatur
braucht nur Ganzzahlen und SHA-512. Die Umsetzung folgt dem Referenzcode aus
RFC 8032, Abschnitt 6 (erweiterte Koordinaten). Sie ist NICHT zeitkonstant;
das ist beim Pruefen oeffentlicher Daten ohne Belang und beim Signieren (nur auf
dem Rechner des Entwicklers, nie beim Anwender) ebenso.

`tests/test_v18_auto_update_ed25519.py` prueft sie gegen die Testvektoren aus dem
RFC und, wo vorhanden, gegen `cryptography`.

Oeffentlich: `geheim_zu_oeffentlich`, `signieren`, `pruefen`. `pruefen` wirft
bei kaputter Eingabe nie, sondern antwortet False: eine Pruefung, die bei
Muell abstuerzt, kann ein Aufrufer aus Versehen als "kein Fehler" lesen.
"""
from __future__ import annotations

import hashlib

_P = 2 ** 255 - 19
_Q = 2 ** 252 + 27742317777372353535851937790883648493


def _sha512(daten: bytes) -> bytes:
    return hashlib.sha512(daten).digest()


def _inv(x: int) -> int:
    return pow(x, _P - 2, _P)


_D = -121665 * _inv(121666) % _P
_WURZEL_AUS_MINUS_1 = pow(2, (_P - 1) // 4, _P)


def _sha512_mod_q(daten: bytes) -> int:
    return int.from_bytes(_sha512(daten), "little") % _Q


def _punkt_addieren(a, b):
    """Summe zweier Punkte in erweiterten Koordinaten (X, Y, Z, T)."""
    aa = (a[1] - a[0]) * (b[1] - b[0]) % _P
    bb = (a[1] + a[0]) * (b[1] + b[0]) % _P
    cc = 2 * a[3] * b[3] * _D % _P
    dd = 2 * a[2] * b[2] % _P
    e, f, g, h = bb - aa, dd - cc, dd + cc, bb + aa
    return (e * f % _P, g * h % _P, f * g % _P, e * h % _P)


def _punkt_mal(s: int, punkt):
    q = (0, 1, 1, 0)  # neutrales Element
    while s > 0:
        if s & 1:
            q = _punkt_addieren(q, punkt)
        punkt = _punkt_addieren(punkt, punkt)
        s >>= 1
    return q


def _punkt_gleich(a, b) -> bool:
    if (a[0] * b[2] - b[0] * a[2]) % _P != 0:
        return False
    if (a[1] * b[2] - b[1] * a[2]) % _P != 0:
        return False
    return True


def _x_zurueckgewinnen(y: int, vorzeichen: int):
    if y >= _P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1)
    if x2 == 0:
        return None if vorzeichen else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * _WURZEL_AUS_MINUS_1 % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != vorzeichen:
        x = _P - x
    return x


_G_Y = 4 * _inv(5) % _P
_G_X = _x_zurueckgewinnen(_G_Y, 0)
_BASIS = (_G_X, _G_Y, 1, _G_X * _G_Y % _P)


def _komprimieren(punkt) -> bytes:
    zinv = _inv(punkt[2])
    x = punkt[0] * zinv % _P
    y = punkt[1] * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _dekomprimieren(daten: bytes):
    if len(daten) != 32:
        return None
    y = int.from_bytes(daten, "little")
    vorzeichen = y >> 255
    y &= (1 << 255) - 1
    x = _x_zurueckgewinnen(y, vorzeichen)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _geheim_erweitern(geheim: bytes):
    if len(geheim) != 32:
        raise ValueError("Der geheime Schluessel muss 32 Byte lang sein.")
    h = _sha512(geheim)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def geheim_zu_oeffentlich(geheim: bytes) -> bytes:
    """Der oeffentliche Schluessel (32 Byte) zu einem geheimen (32 Byte)."""
    a, _ = _geheim_erweitern(geheim)
    return _komprimieren(_punkt_mal(a, _BASIS))


def signieren(geheim: bytes, nachricht: bytes) -> bytes:
    """Die Signatur (64 Byte) ueber `nachricht`."""
    a, praefix = _geheim_erweitern(geheim)
    oeffentlich = _komprimieren(_punkt_mal(a, _BASIS))
    r = _sha512_mod_q(praefix + nachricht)
    rs = _komprimieren(_punkt_mal(r, _BASIS))
    h = _sha512_mod_q(rs + oeffentlich + nachricht)
    s = (r + h * a) % _Q
    return rs + int.to_bytes(s, 32, "little")


def pruefen(oeffentlich: bytes, nachricht: bytes, signatur: bytes) -> bool:
    """Stimmt die Signatur? Bei jeder kaputten Eingabe False, nie eine Ausnahme."""
    try:
        if not isinstance(oeffentlich, (bytes, bytearray)) or len(oeffentlich) != 32:
            return False
        if not isinstance(signatur, (bytes, bytearray)) or len(signatur) != 64:
            return False
        oeffentlich = bytes(oeffentlich)
        signatur = bytes(signatur)
        a = _dekomprimieren(oeffentlich)
        if a is None:
            return False
        rs = signatur[:32]
        r = _dekomprimieren(rs)
        if r is None:
            return False
        s = int.from_bytes(signatur[32:], "little")
        if s >= _Q:
            return False
        h = _sha512_mod_q(rs + oeffentlich + bytes(nachricht))
        s_b = _punkt_mal(s, _BASIS)
        h_a = _punkt_mal(h, a)
        return _punkt_gleich(s_b, _punkt_addieren(r, h_a))
    except Exception:
        return False
