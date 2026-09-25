"""Tests fuer #1050 — Detailbewertung auf der Karte, Blacklist ins Passt-nicht-Menue.

Nutzerbericht vom 15.09.2026: auf der Karte fehlte der Weg zur
Detailbewertung ganz, waehrend "Zur Blacklist" gleichrangig neben dem
Aussortieren stand — bei 28 Blacklist-Eintraegen gegen 2.691
Aussortierungen, und 5 Eintraegen ganz ohne Begruendung.
"""
import inspect
import re
import sys
from pathlib import Path


def _repo() -> Path:
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

SEITE = _repo() / "frontend" / "src" / "pages" / "JobsPage.jsx"
MODUL = _repo() / "frontend" / "src" / "lib" / "detailbewertung.js"


def _seite() -> str:
    return SEITE.read_text(encoding="utf-8-sig")


def _block(text: str, start: str, ende: str) -> str:
    anfang = text.index(start)
    return text[anfang:text.index(ende, anfang)]


def _kartenzeile(text: str) -> str:
    """Die Aktionszeile einer Stellenkarte: vom Anpinnen bis zum Aussortieren."""
    return _block(text, "onClick={() => togglePin(job)}", "openDismissDialog(job)")


# ------------------------------------------------ AK 1-3: Detailbewertung


def test_die_karte_hat_den_detailbewertungs_knopf():
    zeile = _kartenzeile(_seite())
    assert "copyPrompt(detailbewertungPrompt(job))" in zeile
    # Die Beschriftung selbst, nicht irgendein Aufruf: `title=` ruft den
    # Baustein ebenfalls auf, und die Gegenprobe blieb damit stumm.
    # G62 (#1087 C3): der Weg liegt jetzt unter "Genauer prüfen"; die
    # Beschriftung des Claude-Wegs nennt weiter, ob ein Befund vorliegt.
    assert "<GenauerPruefen" in zeile
    menue = _block(_seite(), "function GenauerPruefen(", "\nfunction ")
    assert "detailbewertungKnopf(job)" in menue
    assert 'knopf.befund ? "Neu bewerten" : "Detailbewertung"' in menue, "AK 3: der Knopf zeigt den Befund"


def test_karte_und_fit_dialog_nehmen_denselben_prompt():
    """Der Prompt stand als Literal im Dialog — und verlangte das Speichern nicht."""
    seite = _seite()
    assert 'from "@/lib/detailbewertung"' in seite
    assert "Bewerte die Stelle" not in seite, "Eine zweite Fassung des Prompts steht in der Seite."
    fuss = _block(seite, "footer={(", "Schließen</Button>")
    assert "detailbewertungPrompt(" in fuss


def test_der_prompt_nennt_das_werkzeug_mit_seinen_echten_parametern():
    """Ein Prompt, der auf einen Parameter zeigt, den es nicht gibt, fuehrt ins Leere (#1000)."""
    from bewerbungs_assistent.services.passung import KATEGORIEN
    from bewerbungs_assistent.tools import jobs as jobs_tools
    modul = MODUL.read_text(encoding="utf-8")
    aufruf = re.search(r"stelle_urteil_speichern\(([^)]*)\)", modul)
    assert aufruf, "Der Speicherweg fehlt im Prompt."
    genannt = set(re.findall(r"(\w+)=", aufruf.group(1)))
    quelle = inspect.getsource(jobs_tools)
    signatur = re.search(r"def stelle_urteil_speichern\(([^)]*)\)", quelle).group(1)
    erlaubt = set(re.findall(r"(\w+)\s*:", signatur))
    assert genannt and genannt <= erlaubt, (genannt, erlaubt)
    liste = re.search(r"export const URTEILE = \[([^\]]*)\]", modul).group(1)
    assert set(re.findall(r'"(\w+)"', liste)) == set(KATEGORIEN)


# ------------------------------------------------ AK 4-6: Blacklist


def test_die_blacklist_steht_nicht_mehr_auf_der_karte():
    assert "openBlacklistDialog(job)" not in _kartenzeile(_seite())
    assert "Zur Blacklist\n" not in _kartenzeile(_seite())


def test_der_passt_nicht_dialog_bietet_die_sperre_an():
    dialog = _block(_seite(), "open={dismissDialog.open}", "{/* Job Detail Modal")
    assert "Firma zusätzlich sperren" in dialog
    assert "openBlacklistDialog(" in dialog


def test_der_grund_wird_als_begruendung_vorgeschlagen_und_gesendet():
    """AK 5. Geprueft wird die ZUWEISUNG, nicht das Wort — "grund" steht
    schon in der Signatur und machte eine leere Begruendung unsichtbar."""
    seite = _seite()
    oeffner = _block(seite, "function openBlacklistDialog(", "async function saveBlacklistEntry")
    assert "begruendung: grund" in oeffner, "AK 5: der Ablehnungsgrund wird nicht vorgeschlagen"
    speichern = _block(seite, "async function saveBlacklistEntry", "\n  }\n")
    assert "reason: (blacklistDialog.begruendung" in speichern, (
        "Die Begruendung erreicht den Server nicht.")
    dialog = _block(seite, "open={blacklistDialog.open}", "{/* Dismiss Dialog")
    assert 'label="Begründung"' in dialog and "blacklistDialog.begruendung" in dialog


def test_aussortiert_wird_erst_mit_der_bestaetigten_sperre():
    """Die Gruende aus dem Passt-nicht-Dialog gehen nicht verloren — sie
    werden mit "Blockieren" angewandt, nicht vorher und nicht nie."""
    seite = _seite()
    speichern = _block(seite, "async function saveBlacklistEntry", "\n  }\n")
    sperre = speichern.index('postJson("/api/blacklist"')
    aussortieren = speichern.index('postJson("/api/jobs/dismiss"')
    assert sperre < aussortieren, "Aussortiert wird vor der Sperre."
    assert "blacklistDialog.aussortieren" in speichern
    # Die Bedingung selbst — mit `if (false)` blieb die Reihenfolge der
    # Aufrufe gleich, und die Gegenprobe war stumm.
    assert "if (offen?.hash && offen.reasons?.length) {" in speichern
    eskalation = _block(seite, "Soll die ganze Firma nicht mehr auftauchen?", "Firma zusätzlich sperren")
    assert "{ hash: stelle?.hash, reasons: gruende }" in eskalation


def test_die_sperre_verlangt_weiter_eine_bestaetigung():
    """AK 6: keine Nebenwirkung des Aussortierens — der Blacklist-Dialog
    bleibt der einzige Ort, an dem gespeichert wird."""
    seite = _seite()
    speichern_aufrufe = [m.start() for m in re.finditer(r"saveBlacklistEntry\b", seite)]
    dialog = _block(seite, "open={blacklistDialog.open}", "{/* Dismiss Dialog")
    innerhalb = [p for p in speichern_aufrufe if seite.find(dialog) <= p < seite.find(dialog) + len(dialog)]
    # Definition + Knopf im Blacklist-Dialog — kein Aufruf im Aussortier-Weg.
    assert len(speichern_aufrufe) - len(innerhalb) == 1, speichern_aufrufe
    assert "saveBlacklistEntry" not in _block(seite, "async function saveDismiss", "\n  }\n")
