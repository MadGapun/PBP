"""Die Aufraeum-Runde ("Auto-Engine") - wer sie ausloest und was dabei von selbst geschieht (#1139).

Die Runde besteht aus mehreren Schritten (`dashboard._run_auto_actions_inner`): Bewerbungen ohne Antwort abschliessen,
Nachfass-Erinnerungen nachlegen, ueberholte schliessen, Mails und Dokumente einordnen, fehlende Anzeigentexte nachladen,
Anzeigen auf Existenz pruefen, Quellen anstossen.

## Warum es dieses Modul gibt

Bis v1.7.157 hatte die Runde keinen Ausloeser: der einzige Aufrufer war der Knopf "Jetzt pruefen". Die Oberflaeche
versprach aber "PBP legt an und schliesst ab", "Hakst du sie ab, kommt die naechste" und "der Rest folgt mit der
Automatik". Wer den Knopf nie drueckte - die meisten -, hatte weder Nachfass-Ketten noch ablaufende Bewerbungen noch
nachgeladene Anzeigentexte. v1.7.157 hat die Texte ehrlich gemacht; ab 1.8.0 laeuft die Runde einmal am Tag von selbst
(Variante A des Issues), im Takt des Planers (`automatik_scheduler`), im Hintergrund und mit eigener Spur
(`background_jobs`, Typ `aufraeumen`).

## Was bewusst so ist

* **Das Abschliessen ist ein eigener Schalter, Vorgabe AUS.** Es aendert den Status einer Bewerbung - das darf nicht
  ueber Nacht geschehen, nur weil jemand ein Update installiert hat. Der Knopf "Jetzt pruefen" schliesst weiter immer ab:
  wer ihn drueckt, will es.
* **Alles andere laeuft von selbst**, jeder Schritt mit seinen eigenen Schranken (lokale KI an, Lernen erlaubt,
  Quellen ohne Abruf-Erlaubnis ausgenommen, Backoff).
* **Eine Runde zur Zeit**: Knopf und Planer teilen eine Sperre (`dashboard.run_auto_actions`).
* **Der letzte Lauf nennt, wer ihn ausgeloest hat** (`von`): "von selbst" oder "per Knopf".

Abgrenzung: `automatik_scheduler` startet die Runde und fuehrt den Hintergrund-Job; `text_nachzug` ist der Schritt
"Anzeigentexte nachladen" (feste Reihenfolge, Verfall des Fehlzaehlers).
"""
from __future__ import annotations

#: Setting: Bewerbungen ohne Antwort beim automatischen Lauf von selbst auf "abgelaufen" setzen (Vorgabe aus).
EXPIRE_SCHALTER = "auto_expire_automatisch"
#: Wer hat die Runde zuletzt ausgeloest? ("automatik", "knopf" oder "claude")
LETZTER_AUSLOESER = "auto_actions_last_run_by"
LETZTER_LAUF = "auto_actions_last_run_at"
#: Wie oft der Planer die Runde anstoesst, solange nichts anderes eingestellt ist (Tage).
VORGABE_INTERVALL_TAGE = 1
#: Die Ausloeser, die es gibt (Reihenfolge ohne Bedeutung).
AUSLOESER = ("automatik", "knopf", "claude")

_WAHR = (True, 1, "1", "true", "True", "an", "ja")


def expire_automatisch(db) -> bool:
    """Darf der automatische Lauf Bewerbungen von selbst abschliessen? Vorgabe: nein."""
    try:
        return db.get_setting(EXPIRE_SCHALTER, False) in _WAHR
    except Exception:  # noqa: BLE001 - nie die Runde kippen
        return False


def expire_automatisch_setzen(db, an: bool) -> bool:
    db.set_setting(EXPIRE_SCHALTER, bool(an))
    return bool(an)


def schliesst_ab(db, ausloeser: str) -> bool:
    """Schliesst dieser Lauf Bewerbungen ab? Der Knopf immer, der automatische Lauf nur mit Schalter."""
    if ausloeser == "automatik":
        return expire_automatisch(db)
    return True


def letzter_lauf(db) -> dict:
    """Wann und von wem die Runde zuletzt lief - fuer die Einstellungen und die Statusabfrage."""
    try:
        am = db.get_setting(LETZTER_LAUF, "") or ""
        von = db.get_setting(LETZTER_AUSLOESER, "") or ""
    except Exception:  # noqa: BLE001
        am, von = "", ""
    return {"am": am, "von": von if von in AUSLOESER else ""}
