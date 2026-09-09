"""Tests fuer v1.7.37 — #990: eine Klammer hat den Installer abgebrochen.

Nutzer-Report vom 07.09.2026, erste Installation auf Windows 11: das
Installer-Fenster schliesst sich ohne Meldung, das Dashboard laeuft, aber
der MCP-Server ist in Claude Desktop nicht eingetragen. Die letzte Zeile
im Log ist `[OK] Claude Desktop gefunden`; der naechste erwartete Eintrag
`[DEBUG] Starte _setup_claude.py` erscheint nie.

Ursache, am laufenden `cmd.exe` reproduziert:

    if !errorlevel! equ 0 (
        ...
        echo  wird nur beim Claude-Start eingelesen).
        ...
    )

**Eine unescapte `)` in einem `echo` INNERHALB eines Klammerblocks
beendet den Block genau dort.** Der Rest der Zeile — hier ein einzelner
Punkt — wird zur naechsten Anweisung, cmd meldet
`"." kann syntaktisch an dieser Stelle nicht verarbeitet werden` und
bricht das Skript ab. Das Fenster schliesst sich, ohne dass irgendetwas
ins Log kommt.

Gemessen dazu (beide Richtungen, cmd.exe unter Windows 11):

* `echo Text (auf` + `echo zu).` in einem Block  -> Abbruch
* `echo (alles in einer Zeile).` in einem Block  -> Abbruch
* dieselben Zeilen mit `^(` und `^)`             -> laeuft, Klammern
  erscheinen korrekt in der Ausgabe

Das Klammerpaar hilft also NICHT: cmd zaehlt die oeffnende Klammer im
`echo` nicht mit, die schliessende aber schon. Wer das ausbalanciert
glaubt, irrt sich.

Der Fehler stand seit v1.7.0-beta.18 im Installer und an acht weiteren
Stellen in drei Dateien, darunter im Deinstaller. Ein Kommentar wie "hier
bitte Klammern escapen" haette das nicht gehalten — deshalb diese
Pruefung.
"""
import re
from pathlib import Path

import pytest


def _repo() -> Path:
    """Repo-Wurzel ueber die Testdatei, nicht ueber das Arbeitsverzeichnis.

    DoD 8c: ein Test mit relativen Pfaden besteht nur an einer Stelle.
    """
    return Path(__file__).resolve().parents[1]


ECHO = re.compile(r"echo\b|echo\.", re.IGNORECASE)


def _batchdateien() -> list[Path]:
    wurzel = _repo()
    return sorted(
        p for p in wurzel.rglob("*.bat")
        if "node_modules" not in p.parts and ".git" not in p.parts
    )


def unescapte_klammern(zeile: str) -> str:
    """Welche ( oder ) stehen ohne vorangestelltes ^ da?"""
    return "".join(
        z for i, z in enumerate(zeile)
        if z in "()" and (i == 0 or zeile[i - 1] != "^")
    )


def befunde(text: str) -> list[tuple[int, str, str]]:
    """echo-Zeilen mit unescapten Klammern INNERHALB eines Blocks."""
    treffer: list[tuple[int, str, str]] = []
    tiefe = 0
    for nr, zeile in enumerate(text.splitlines(), 1):
        blank = zeile.strip()
        klein = blank.lower()
        if klein.startswith("::") or klein.startswith("rem "):
            continue
        ist_echo = bool(ECHO.match(klein))
        if tiefe > 0 and ist_echo:
            k = unescapte_klammern(blank)
            if k:
                treffer.append((nr, k, blank[:100]))
        if ist_echo:
            # Klammern in echo-Zeilen zaehlen fuer die Blocktiefe NICHT
            # verlaesslich mit — genau darum geht es hier.
            continue
        tiefe = max(0, tiefe + blank.count("(") - blank.count(")"))
    return treffer


def test_990_es_gibt_ueberhaupt_batchdateien():
    """Sonst prueft der Waechter nichts und meldet trotzdem gruen."""
    assert len(_batchdateien()) >= 2


@pytest.mark.parametrize("pfad", _batchdateien(), ids=lambda p: p.name)
def test_990_keine_unescapten_klammern_in_bloecken(pfad):
    text = pfad.read_text(encoding="utf-8", errors="replace")
    gefunden = befunde(text)
    assert not gefunden, (
        f"{pfad.name}: unescapte Klammern in echo-Zeilen innerhalb eines "
        "Klammerblocks — cmd bricht dort das Skript ab:\n"
        + "\n".join(f"  Zeile {nr}: {k!r}  {txt}" for nr, k, txt in gefunden)
        + "\n\nAbhilfe: die Klammern als ^( und ^) schreiben."
    )


# ── Der Waechter selbst, in beide Richtungen ─────────────────────────

def test_990_waechter_findet_den_ausloesenden_fall():
    """Der Originalfall aus INSTALLIEREN.bat, wortwoertlich."""
    text = (
        "if !errorlevel! equ 0 (\n"
        "    echo  PBP-Konfiguration uebernommen wird (MCP-Server-Konfig\n"
        "    echo  wird nur beim Claude-Start eingelesen).\n"
        ")\n"
    )
    assert [nr for nr, _, _ in befunde(text)] == [2, 3]


def test_990_waechter_akzeptiert_die_reparierte_fassung():
    text = (
        "if !errorlevel! equ 0 (\n"
        "    echo  PBP-Konfiguration uebernommen wird ^(MCP-Server-Konfig\n"
        "    echo  wird nur beim Claude-Start eingelesen^).\n"
        ")\n"
    )
    assert befunde(text) == []


def test_990_ausserhalb_eines_blocks_ist_es_erlaubt():
    """Dort beendet die Klammer nichts — kein Grund, es zu verbieten."""
    assert befunde("echo Hinweis (steht frei) und ist harmlos\n") == []


def test_990_kommentare_loesen_nichts_aus():
    """Sonst schlaegt der Waechter an der Erklaerung an, warum es ihn gibt.

    Genau das ist in v1.7.31 zweimal passiert (MERKE 6 dort).
    """
    text = "if 1 equ 1 (\n:: echo  Beispiel (mit Klammer).\nrem echo (auch)\n)\n"
    assert befunde(text) == []


# ── Der zweite Defekt aus demselben Report ───────────────────────────

def test_990_store_installation_wird_erkannt():
    """Claude aus dem Microsoft Store liegt nicht dort, wo gesucht wurde.

    MSIX-Pakete liegen unter `C:\\Program Files\\WindowsApps\\<Paket>` —
    ACL-geschuetzt, also fuer `if exist` aus einer normalen Shell auch
    dann unsichtbar, wenn die Datei da ist. Im PATH stehen sie nicht,
    weil sie ueber einen App-Execution-Alias starten. Und
    `%LOCALAPPDATA%\\Packages\\Claude_*` enthaelt nur Anwendungsdaten:
    die #361-Erkennung suchte an der richtigen Stelle nach der falschen
    Sache. Deshalb ueber die Appx-API.
    """
    text = (_repo() / "INSTALLIEREN.bat").read_text(encoding="utf-8", errors="replace")
    assert "Get-AppxPackage" in text
    assert "CLAUDE_APPX" in text
    assert "shell:AppsFolder" in text


def test_990_appx_abfrage_kommt_ohne_pipe_aus():
    """Ein `^|` im Backtick-Kommando von `for /f` kommt nicht an.

    Gemessen: mit Pipe lieferte die Abfrage still eine leere Zeichenkette
    — also genau wieder ein Fehler, der wie ein normaler Zustand
    aussieht. Die Auswahl macht deshalb PowerShell selbst.
    """
    for zeile in (_repo() / "INSTALLIEREN.bat").read_text(
            encoding="utf-8", errors="replace").splitlines():
        if "Get-AppxPackage" in zeile and "for /f" in zeile:
            assert "^|" not in zeile, zeile
            break
    else:
        pytest.fail("Keine for/f-Zeile mit Get-AppxPackage gefunden")


def test_990_startbefehl_traegt_kein_literales_ausrufezeichen():
    """`shell:AppsFolder\\<Paket>!Claude` enthaelt ein `!`.

    Bei `EnableDelayedExpansion` liest cmd ein `!` in der Zeile als
    Variablenklammer und frisst es — der Startbefehl waere dann still
    falsch. PowerShell setzt das Zeichen deshalb selbst zusammen.
    """
    for zeile in (_repo() / "INSTALLIEREN.bat").read_text(
            encoding="utf-8", errors="replace").splitlines():
        if "shell:AppsFolder" in zeile:
            assert "!" not in zeile, zeile
            assert "[char]33" in zeile
            break
    else:
        pytest.fail("Keine Zeile mit shell:AppsFolder gefunden")


def test_990_application_id_kommt_aus_dem_manifest():
    """Vorschlag des Melders — und er hat recht.

    v1.7.37 trug die Id fest als 'Claude' ein. Das stimmt heute, wuerde
    bei einer Umbenennung aber still danebengreifen, und `>nul 2>&1`
    verschluckt den Fehler auch noch. Also aus dem Paketmanifest lesen.
    """
    for zeile in (_repo() / "INSTALLIEREN.bat").read_text(
            encoding="utf-8", errors="replace").splitlines():
        if "shell:AppsFolder" in zeile:
            assert "Get-AppxPackageManifest" in zeile, zeile
            assert "+ 'Claude'" not in zeile, (
                "Die Application-Id steht wieder fest im Code: " + zeile)
            break
    else:
        pytest.fail("Keine Zeile mit shell:AppsFolder gefunden")


def test_990_kein_escapter_pipe_in_powershell_aufrufen():
    """Zweimal an einem Tag dieselbe Falle — deshalb mechanisch.

    Gemessen, beide Male still gescheitert:

    * `^|` im Backtick-Kommando von `for /f` kommt in der Subshell nicht
      als Pipe an — die Abfrage lieferte eine leere Zeichenkette.
    * `^|` in einem in Anfuehrungszeichen stehenden PowerShell-Kommando
      kommt als literales `^|` bei PowerShell an — Parserfehler.

    Ein NORMALES `|` in einem gequoteten PowerShell-Kommando ist dagegen
    in Ordnung und steht seit Jahren im Installer (Zeilen mit
    `Set-Content` und der Dashboard-Health-Check). Der Waechter darf die
    nicht anfassen — ein Pruefer, der bei korrektem Zustand Alarm gibt,
    wird nach dem zweiten Mal ignoriert (MERKE aus DoD-9).
    """
    schlecht = []
    for nr, zeile in enumerate((_repo() / "INSTALLIEREN.bat").read_text(
            encoding="utf-8", errors="replace").splitlines(), 1):
        blank = zeile.strip()
        if blank.startswith("::") or blank.lower().startswith("rem "):
            continue
        if "powershell" in blank.lower() and "^|" in blank:
            schlecht.append(f"Zeile {nr}: {blank[:110]}")
    assert not schlecht, (
        "PowerShell-Aufruf mit escaptem Pipe in INSTALLIEREN.bat:\n"
        + "\n".join(schlecht)
        + "\n\nAbhilfe: die Auswahl in PowerShell selbst treffen "
          "(Index [0] statt `^| Select-Object -First 1`) oder ein "
          "normales `|` innerhalb der Anfuehrungszeichen verwenden."
    )


def test_990_waechter_meldet_die_funktionierenden_pipes_nicht():
    """Gegenprobe zum Fehlalarm, den die erste Fassung produziert hat.

    Sie meldete fuenf seit Jahren laufende Zeilen — genau die Sorte
    Befund, nach der niemand mehr hinsieht.
    """
    text = (_repo() / "INSTALLIEREN.bat").read_text(encoding="utf-8", errors="replace")
    mit_normaler_pipe = [
        z for z in text.splitlines()
        if "powershell" in z.lower() and "|" in z and "^|" not in z
    ]
    assert mit_normaler_pipe, (
        "Erwartet: es GIBT funktionierende PowerShell-Zeilen mit Pipe. "
        "Ohne sie prueft die Gegenprobe nichts.")

def test_739_kein_wmic_mehr_in_den_batchdateien():
    """`wmic` ist auf Windows 11 24H2 entfernt (#739).

    Der Deinstaller wurde umgestellt, der Installer nicht — derselbe
    Defekt in der Schwesterdatei, und er faellt erst beim UPDATE auf:
    laufende PBP-Prozesse werden nicht beendet, das Kopieren der Runtime
    trifft auf gesperrte Dateien ("Unzulaessiger SHARE-Vorgang").

    **Eine Abhaengigkeit, die auf neuen Windows-Builds fehlt, faellt
    still aus** — die Schleife findet dann nichts und meldet keinen
    Fehler. Genau deshalb steht der Guard hier und nicht als Notiz.
    """
    treffer = []
    for datei in sorted(_repo().glob("*.bat")):
        for nr, zeile in enumerate(
                datei.read_text(encoding="utf-8",
                                errors="replace").splitlines(), 1):
            nackt = zeile.strip()
            if nackt.startswith("::") or nackt.startswith("rem "):
                continue  # Erklaerungen duerfen das Wort nennen
            if "wmic" in nackt.lower():
                treffer.append(f"{datei.name}:{nr}")
    assert not treffer, (
        f"wmic wird noch aufgerufen: {treffer}. Auf Windows 11 24H2 ist es "
        "entfernt — der Aufruf schlaegt still fehl. Ersatz: PowerShell mit "
        "Get-CimInstance, wie in DEINSTALLIEREN.bat.")


def test_739_der_prozess_stopp_nutzt_dieselbe_erprobte_form():
    """Installer und Deinstaller muessen dieselbe Form verwenden.

    Zwei Fassungen derselben Aufgabe waren der Grund, warum die eine
    repariert wurde und die andere nicht — dasselbe Muster wie #963 und
    #991, hier in Batch-Dateien.
    """
    for name in ("INSTALLIEREN.bat", "DEINSTALLIEREN.bat"):
        text = (_repo() / name).read_text(encoding="utf-8", errors="replace")
        assert "Get-CimInstance Win32_Process" in text, name
        assert "Stop-Process" in text, name
