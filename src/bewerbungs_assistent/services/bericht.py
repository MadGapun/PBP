"""Der Bewerbungsbericht — ein Weg fuer Dashboard und Claude (#1111).

Bis v1.7.139 baute der Knopf im Dashboard einen anderen Bericht als
`bewerbungsbericht_exportieren`: die Einstellungen standen zweimal im
Code, und nur die Dashboard-Fassung kannte den Taetigkeitsbericht (#582)
und den Beginn der PBP-Nutzung. Claude dagegen haengte Prozess-Kennzahlen
an, das Dashboard nicht. Wer "Taetigkeitsbericht" eingeschaltet hatte und
Claude fragte, bekam einen gewoehnlichen Bewerbungsbericht.

Hier stehen Einstellungen, Daten und der Aufruf der Erzeuger einmal;
Endpunkt und Werkzeug unterscheiden sich nur im Ausgabeort.
"""
from __future__ import annotations

import logging

logger = logging.getLogger("bewerbungs_assistent.bericht")

#: Schluessel im Bericht -> (Profil-Einstellung, Art)
EINSTELLUNGEN = {
    "arbeitsamt_block_enabled": ("report_arbeitsamt_block_enabled", bool),
    "ba_vermittlungsnummer": ("report_ba_vermittlungsnummer", str),
    "ba_aktenzeichen": ("report_ba_aktenzeichen", str),
    "ba_berater_name": ("report_ba_berater_name", str),
    "ba_berater_stelle": ("report_ba_berater_stelle", str),
    "berater_kommentar_block": ("report_berater_kommentar_block", bool),
    # v1.7.0-beta.12 (#582): Taetigkeitsbericht-Modus
    "taetigkeitsbericht_mode": ("report_taetigkeitsbericht_mode", bool),
}


def einstellungen(db) -> dict:
    """Die Bericht-Einstellungen (v1.6.6, #540). Nur Gesetztes erscheint."""
    erg = {}
    for schluessel, (setting, art) in EINSTELLUNGEN.items():
        if art is bool:
            erg[schluessel] = bool(db.get_profile_setting(setting, False))
        else:
            erg[schluessel] = db.get_profile_setting(setting, "") or ""
    return erg


def daten(db) -> dict:
    """Berichtsdaten samt Prozess-Kennzahlen (#781). Eine fehlende
    Erweiterung verhindert den Bericht nie."""
    report_data = db.get_report_data()
    try:
        from . import statistik_erweitert as _se
        report_data["prozess_kennzahlen"] = _se.zeitliche_kennzahlen(db)
        report_data["kanal_auswertung"] = _se.kanal_auswertung(db)
        report_data["ablehnungs_kategorien"] = _se.ablehnungs_kategorien(db)
        report_data["aufwand"] = db.get_aufwand_summary()
    except Exception as exc:
        logger.warning("Bericht-Erweiterung (#781) fehlgeschlagen: %s", exc)
    return report_data


def erzeugen(db, pfad, format: str = "pdf", zeitraum_von: str = "",
             zeitraum_bis: str = "") -> dict:
    """Schreibt den Bericht nach `pfad`. `format`: 'pdf' oder 'excel'/'xlsx'.
    Rueckgabe: die Berichtsdaten (fuer Zaehler in der Antwort)."""
    report_data = daten(db)
    profile = db.get_profile()
    report_settings = einstellungen(db)
    if format in ("excel", "xlsx"):
        from ..export_report import generate_excel_report
        generate_excel_report(report_data, profile, pfad,
                              zeitraum_von=zeitraum_von, zeitraum_bis=zeitraum_bis,
                              report_settings=report_settings)
    else:
        from ..export_report import generate_application_report
        generate_application_report(report_data, profile, pfad,
                                    zeitraum_von=zeitraum_von, zeitraum_bis=zeitraum_bis,
                                    report_settings=report_settings,
                                    pbp_first_active_at=db.get_pbp_first_active_at())
    return report_data
