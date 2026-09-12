"""Das Kontextfenster der lokalen KI (#787, F32).

`_ollama_generate` setzte bis v1.7.89 kein `num_ctx`. Ollama nimmt dann
sein eigenes Vorgabefenster — je nach Version 2.048 oder 4.096 Tokens —
und schneidet einen laengeren Prompt STILL ab. Das Modell bewertet
danach einen Torso, und die Antwort sieht aus wie jede andere.
Dieselbe Fehlerklasse wie #756 ("auf Titel-Basis geraten"), eine Ebene
tiefer: nicht die Eingabe fehlt, sondern ein Teil davon, ohne dass es
jemand merkt.

## Warum ein FESTER Wert und kein mitwachsender

Aendert sich `num_ctx` zwischen zwei Aufrufen, laedt Ollama das Modell
neu. Das ist genau der Kaltstart von 50-60 Sekunden, gegen den #638 den
Warmup gebaut hat. Ein Fenster, das je Prompt passend gewaehlt wird,
waere also bei fast jedem Aufruf ein Neuladen. Deshalb gilt ein Wert je
Profil, und `warmup` schickt denselben.

## Warum 8.192 als Vorgabe

Gemessen am 12.09.2026: jeder Prompt-Builder kuerzt seine Eingaben
selbst (1.500 bis 4.000 Zeichen). Mit realistischen Hoechstwerten liegt
der groesste fertige Prompt bei rund 5.000 Zeichen; der Elwosa-Dialog am
echten Bestand bei rund 4.100. Vorsichtig geschaetzt (3 Zeichen je
Token) sind das knapp 1.700 Tokens, dazu bis zu 800 fuer die Antwort —
das sprengt ein Fenster von 2.048 und passt sicher in 8.192. Groesser
kostet Arbeitsspeicher, ohne dass heute ein Prompt es braucht; wer
laengere Eingaben baut, bekommt es gesagt statt still gekuerzt.

## Zwei Pruefungen, und sie sind nicht redundant

`vorab_pruefen` schaetzt aus der Zeichenzahl und schickt einen Prompt,
der sicher nicht passt, gar nicht erst ab. `nachher_pruefen` liest
`prompt_eval_count` aus der Antwort — das ist die GEMESSENE Zahl des
Modells, keine Schaetzung — und verwirft eine Antwort, deren Prompt am
Fensterrand lag. Die Schaetzung allein haengt am Tokenizer des Modells;
die Messung allein kaeme erst nach einem vergeudeten Aufruf.

Beide werfen `KontextZuKlein`. Der Aufrufer faellt damit auf seinen
vorhandenen Ausweichweg zurueck (Claude bzw. ein ehrlicher Fehler bei
Elwosa) — und der Grund steht dabei.
"""
from __future__ import annotations

import math
from typing import Any

SCHLUESSEL = "llm_num_ctx"
VORGABE = 8192
MINIMUM = 2048
MAXIMUM = 131072

# Vorsichtig: deutsche Texte liegen bei gaengigen Tokenizern eher bei
# 3,3-4 Zeichen je Token. Zu wenig Zeichen je Token ueberschaetzt den
# Prompt — das kostet hoechstens einen Ausweichweg, waehrend eine
# Unterschaetzung genau die stille Kuerzung zuliesse, um die es geht.
ZEICHEN_JE_TOKEN = 3.0

SPEICHER_HINWEIS = (
    "Ein groesseres Fenster braucht mehr Arbeitsspeicher. Ollama halbiert "
    "den Bedarf mit den Umgebungsvariablen OLLAMA_KV_CACHE_TYPE=q8_0 und "
    "OLLAMA_FLASH_ATTENTION=1 — damit sind 16.384 auch auf Karten mit "
    "8 GB realistisch."
)


class KontextZuKlein(RuntimeError):
    """Der Prompt passt nicht in das eingestellte Kontextfenster."""


def schaetze_tokens(text: str) -> int:
    return math.ceil(len(text or "") / ZEICHEN_JE_TOKEN)


def _gueltig(wert: Any) -> int | None:
    if isinstance(wert, bool):
        return None
    try:
        zahl = int(str(wert).strip())
    except (TypeError, ValueError):
        return None
    if str(wert).strip() != str(zahl):
        return None  # "8192.5", "8k" und aehnliches nicht still umdeuten
    return zahl if MINIMUM <= zahl <= MAXIMUM else None


def _roh(db) -> Any:
    if db is None:
        return None
    try:
        return db.get_profile_setting(SCHLUESSEL, None)
    except Exception:
        return None


def num_ctx_lesen(db) -> int:
    """Der Wert, mit dem gerechnet wird. Fehlt oder taugt er nicht: Vorgabe."""
    roh = _roh(db)
    if roh in (None, ""):
        return VORGABE
    return _gueltig(roh) or VORGABE


def lesen(db) -> dict:
    roh = _roh(db)
    gesetzt = roh not in (None, "")
    antwort = {
        "num_ctx": num_ctx_lesen(db),
        "vorgabe": VORGABE,
        "eigener_wert": gesetzt and _gueltig(roh) is not None,
        "erlaubter_bereich": [MINIMUM, MAXIMUM],
        "hinweis": (
            "Das Kontextfenster der lokalen KI in Tokens. Passt ein Prompt "
            "nicht hinein, schickt PBP ihn nicht ab bzw. verwirft die "
            "Antwort und nennt den Grund — Ollama wuerde den Anfang sonst "
            "still abschneiden."
        ),
        "speicher": SPEICHER_HINWEIS,
    }
    if gesetzt and _gueltig(roh) is None:
        # Ein gespeicherter Wert, der nichts bewirkt, wird BENANNT (#988).
        antwort["gespeicherter_wert_ungueltig"] = str(roh)
    return antwort


def setzen(db, wert: Any) -> dict:
    zahl = _gueltig(wert)
    if zahl is None:
        return {
            "fehler": (
                f"'{wert}' ist kein gueltiges Kontextfenster. Erlaubt sind "
                f"ganze Zahlen von {MINIMUM} bis {MAXIMUM}. Nichts gespeichert."
            ),
            "aktueller_stand": lesen(db),
        }
    db.set_profile_setting(SCHLUESSEL, str(zahl))
    antwort = lesen(db)
    antwort["neu_laden"] = (
        "Ollama laedt das Modell beim naechsten Aufruf einmalig neu, weil "
        "sich das Fenster geaendert hat."
    )
    return antwort


def zuruecksetzen(db) -> dict:
    db.set_profile_setting(SCHLUESSEL, "")
    return lesen(db)


def vorab_pruefen(prompt: str, max_tokens: int, num_ctx: int) -> int:
    """Wirft `KontextZuKlein`, wenn der Prompt geschaetzt nicht passt."""
    geschaetzt = schaetze_tokens(prompt)
    if geschaetzt + max_tokens > num_ctx:
        raise KontextZuKlein(
            f"Der Prompt passt nicht in das Kontextfenster der lokalen KI: "
            f"geschaetzt {geschaetzt} Tokens plus {max_tokens} fuer die "
            f"Antwort, das Fenster hat {num_ctx}. Nicht abgeschickt, weil "
            f"Ollama den Anfang still abgeschnitten haette. Groesseres "
            f"Fenster: ollama_kontext(aktion='setzen', wert=...)."
        )
    return geschaetzt


def nachher_pruefen(prompt_tokens: Any, max_tokens: int, num_ctx: int) -> None:
    """Wirft `KontextZuKlein`, wenn der GEMESSENE Prompt am Fensterrand lag."""
    if not isinstance(prompt_tokens, int) or isinstance(prompt_tokens, bool):
        return  # alte Ollama-Fassung oder Testdoppel ohne Zaehler
    if prompt_tokens + max_tokens > num_ctx:
        raise KontextZuKlein(
            f"Die lokale KI hat {prompt_tokens} Prompt-Tokens verarbeitet; "
            f"mit {max_tokens} fuer die Antwort ist das mehr als das Fenster "
            f"von {num_ctx}. Der Prompt wurde vermutlich gekuerzt, die "
            f"Antwort ist deshalb verworfen. Groesseres Fenster: "
            f"ollama_kontext(aktion='setzen', wert=...)."
        )
