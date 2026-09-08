"""Text aus Office-Formaten, die PBP bisher still uebersprungen hat (#833).

Belegter Fall (11.08.2026): eine `.pptx` mit sieben Folien und rund 1.100
Zeichen echtem Textlayer — kein einziges Element unter `ppt/media/`, also
keine Scans. `extraktion_starten(..., force=True)` lieferte
`{"text_laenge": 0, "extrahierter_text": ""}` und meldete `status: "ok"`.

Drei Dinge daran waren falsch:

1. **Stiller Ausfall.** Es gab keine Warnung, kein "Format nicht
   unterstuetzt", keinen Fehlereintrag. Ein Dokument, das nichts liefert,
   war von einem Dokument, das nichts enthaelt, nicht unterscheidbar.
2. **Der Statuswert log.** `last_extraction_at` wurde gesetzt,
   `extraction_status` blieb `nicht_extrahiert` — das Dokument tauchte bei
   jedem `analyse_plan_erstellen` erneut als offen auf und produzierte
   dasselbe Nichts. Eine Endlosschleife im Arbeitsablauf.
3. **PPTX ist im Bewerbungskontext kein Randformat.** Personaldienstleister
   versenden Feedbackboegen und Kandidatenprofile als Praesentation; hier
   war es die schriftliche Arbeitsprobe eines laufenden Verfahrens.

Bewusst OHNE neue Abhaengigkeit: `python-pptx` ist in dieser Umgebung
zwar installiert, steht aber in keiner Dependency-Gruppe von
`pyproject.toml`. Ein Extraktor, der auf einem fremden Rechner fehlt,
waere derselbe stille Ausfall in Gruen. OOXML und ODF sind ZIP-Archive
mit XML darin — das kann die Standardbibliothek.
"""

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree

# OOXML-Namensraeume. `a:` ist DrawingML — dort steht der Text jeder
# Folie, egal ob er in einem Textfeld, einer Tabelle oder einer
# Gruppierung liegt. Genau deshalb wird der ganze Baum durchsucht und
# nicht nur der Shape-Baum oberster Ebene (AK 3).
_A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"
_ODF_TEXT = "{urn:oasis:names:tc:opendocument:xmlns:text:1.0}"

_FOLIE = re.compile(r"ppt/slides/slide(\d+)\.xml$")
_NOTIZ = re.compile(r"ppt/notesSlides/notesSlide(\d+)\.xml$")


class FormatNichtUnterstuetzt(Exception):
    """Ehrliche Absage statt stillem Nichts.

    Fuer Formate, die PBP nicht lesen KANN — im Unterschied zu Dateien,
    die einfach keinen Text enthalten. Die Unterscheidung ist der Kern
    von #833.
    """


def _absaetze(element) -> list[str]:
    """Alle `<a:p>`-Absaetze eines Teilbaums als Zeilen.

    Ein Absatz kann in mehrere `<a:t>`-Laeufe zerfallen (jede
    Formatierungsaenderung erzeugt einen neuen). Sie gehoeren
    zusammengesetzt, sonst zerfaellt ein Satz in Wortfragmente.
    """
    zeilen = []
    for absatz in element.iter(f"{_A}p"):
        text = "".join(t.text or "" for t in absatz.iter(f"{_A}t"))
        if text.strip():
            zeilen.append(text.strip())
    return zeilen


def _pptx(pfad: Path) -> str:
    with zipfile.ZipFile(pfad) as z:
        namen = z.namelist()
        folien = sorted(
            ((int(m.group(1)), n) for n in namen if (m := _FOLIE.search(n))),
            key=lambda x: x[0])
        notizen = {int(m.group(1)): n for n in namen
                   if (m := _NOTIZ.search(n))}
        if not folien:
            raise FormatNichtUnterstuetzt(
                "Die Datei ist ein ZIP-Archiv, enthaelt aber keine Folien "
                "unter ppt/slides/ — vermutlich keine PowerPoint-Datei.")

        teile = []
        for nummer, name in folien:
            block = [f"--- Folie {nummer} ---"]
            block += _absaetze(ElementTree.fromstring(z.read(name)))
            # Sprechernotizen mitnehmen und als solche kennzeichnen
            # (AK 2) — in Feedbackboegen steht dort oft die eigentliche
            # Bewertung.
            if nummer in notizen:
                notiz = _absaetze(ElementTree.fromstring(z.read(notizen[nummer])))
                # Die Foliennummer wiederholt sich im Notizen-XML als
                # eigener Textlauf; sie ist keine Notiz.
                notiz = [z_ for z_ in notiz if z_ != str(nummer)]
                if notiz:
                    block.append("[Sprechernotizen]")
                    block += notiz
            if len(block) > 1:
                teile.append("\n".join(block))
        return "\n\n".join(teile)


def _xlsx(pfad: Path) -> str:
    """Zellinhalte, Blatt fuer Blatt.

    Zahlen bleiben absichtlich aussen vor: eine Tabelle voller Werte ohne
    Kontext ist kein Dokumententext, sondern Rauschen im Volltextindex.
    Gelesen werden die geteilten Zeichenketten (`sharedStrings.xml`), also
    genau das, was jemand getippt hat.
    """
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(pfad) as z:
        if "xl/sharedStrings.xml" not in z.namelist():
            return ""
        baum = ElementTree.fromstring(z.read("xl/sharedStrings.xml"))
        werte = []
        for si in baum.iter(f"{ns}si"):
            text = "".join(t.text or "" for t in si.iter(f"{ns}t"))
            if text.strip():
                werte.append(text.strip())
        return "\n".join(werte)


def _docx(pfad: Path) -> str:
    """Text aus einem Word-Dokument — auch aus Tabellen (#998).

    Gemeldet am 08.09.2026: ein Lebenslauf im zweispaltigen
    Tabellenlayout ergab 26 Zeichen. Der alte Extraktor las
    `doc.paragraphs`, und das sind ausschliesslich Absaetze auf
    Body-Ebene. **Tabellenlayout ist bei Lebenslaeufen die Regel, nicht
    die Ausnahme** (Zeitraum links, Taetigkeit rechts), und die
    Kontaktdaten stehen haeufig in der Kopfzeile.

    Warum stdlib statt python-docx, obwohl die Abhaengigkeit da ist:

    * **Verbundene Zellen.** `row.cells` liefert eine ueber drei Spalten
      verbundene Zelle DREIMAL — gemessen. Der naheliegende Einzeiler
      verdreifacht damit jede Abschnittsueberschrift einer CV-Vorlage,
      und dieser Text geht in die Keyword-Bewertung ein. Im rohen OOXML
      gibt es die Zelle genau einmal; das Problem entsteht also erst
      durch die Bequemlichkeitsschicht.
    * **Dokumentreihenfolge.** Absaetze und Tabellen abwechselnd, so wie
      sie dastehen. Erst Absaetze, dann alle Zellen zu sortieren
      zerreisst den Lebenslauf in zwei Bloecke.
    * **Textfelder** (`w:txbxContent`) kommen kostenlos mit, weil sie im
      selben Baum liegen. Bei Design-Vorlagen steht dort oft der Name.
    * Und es haelt die Regel dieses Moduls ein: OOXML ist ein ZIP mit
      XML darin, das kann die Standardbibliothek.
    """
    ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"

    def _text(baum) -> list:
        """Ein Eintrag je Absatz, Laeufe zusammengesetzt.

        Ein Absatz zerfaellt bei jeder Formatierungsaenderung in mehrere
        `w:t`; einzeln genommen ergaebe das Wortfragmente. Tabulatoren
        und Zeilenumbrueche im Absatz werden zu Leerzeichen, sonst
        klebt "2020Musterbetrieb" zusammen.
        """
        zeilen = []
        for absatz in baum.iter(f"{ns}p"):
            teile = []
            for el in absatz.iter():
                if el.tag == f"{ns}t":
                    teile.append(el.text or "")
                elif el.tag in (f"{ns}tab", f"{ns}br"):
                    teile.append(" ")
            text = " ".join("".join(teile).split())
            if text:
                zeilen.append(text)
        return zeilen

    with zipfile.ZipFile(pfad) as z:
        namen = z.namelist()
        if "word/document.xml" not in namen:
            raise FormatNichtUnterstuetzt(
                "Kein word/document.xml im Archiv — vermutlich keine "
                "Word-Datei (eine umbenannte .doc etwa ist ein anderes "
                "Format und muss einmal als .docx gespeichert werden).")
        zeilen = _text(ElementTree.fromstring(z.read("word/document.xml")))

        # Kopf- und Fusszeilen tragen bei Lebenslaeufen oft die
        # Kontaktdaten. Sie wiederholen sich ueber Abschnitte hinweg
        # wortgleich (erste Seite / Folgeseiten), deshalb wird jede
        # Zeile nur einmal uebernommen.
        rand = []
        # Kopfzeilen vor Fusszeilen — dort stehen die Kontaktdaten,
        # unten meist nur die Seitenzahl.
        raender = [n for n in namen
                   if re.fullmatch(r"word/(header|footer)\d*\.xml", n)]
        for name in sorted(raender, key=lambda n: ("footer" in n, n)):
            for zeile in _text(ElementTree.fromstring(z.read(name))):
                if zeile not in zeilen and zeile not in rand:
                    rand.append(zeile)

    return "\n".join(zeilen + rand)


def _odf(pfad: Path) -> str:
    with zipfile.ZipFile(pfad) as z:
        if "content.xml" not in z.namelist():
            raise FormatNichtUnterstuetzt(
                "Kein content.xml im Archiv — vermutlich keine "
                "OpenDocument-Datei.")
        baum = ElementTree.fromstring(z.read("content.xml"))
        zeilen = []
        for tag in ("p", "h"):
            for el in baum.iter(f"{_ODF_TEXT}{tag}"):
                text = "".join(el.itertext()).strip()
                if text:
                    zeilen.append(text)
        return "\n".join(zeilen)


# Formate, die PBP lesen kann, und ihr Leser.
LESER = {
    ".docx": _docx,
    ".pptx": _pptx,
    ".xlsx": _xlsx,
    ".xlsm": _xlsx,
    ".odt": _odf,
    ".odp": _odf,
    ".ods": _odf,
}

# Altformate ohne OOXML. Hier ist eine ehrliche Absage besser als
# stilles Nichts (AK 6) — sie sagt dem Menschen, was zu tun ist.
ALTFORMATE = {
    ".ppt": "PowerPoint 97-2003",
    ".xls": "Excel 97-2003",
    # .doc bleibt bewusst DRAUSSEN: dafuer gibt es seit #192 den
    # antiword-Pfad im Extraktor. Ein Altformat mit funktionierendem
    # Leser gehoert nicht auf die Absageliste.
}


def kann_lesen(dateiname: str) -> bool:
    return Path(dateiname).suffix.lower() in LESER


def ist_altformat(dateiname: str) -> bool:
    return Path(dateiname).suffix.lower() in ALTFORMATE


def extrahiere(pfad) -> str:
    """Text aus einem Office-Dokument.

    Raises:
        FormatNichtUnterstuetzt: bei Altformaten und beschaedigten
            Archiven. Der Aufrufer soll das MELDEN, nicht schlucken.
    """
    pfad = Path(pfad)
    endung = pfad.suffix.lower()

    if endung in ALTFORMATE:
        raise FormatNichtUnterstuetzt(
            f"{ALTFORMATE[endung]} ({endung}) wird nicht unterstuetzt. "
            f"Die Datei einmal in einem Office-Programm oeffnen und als "
            f"{endung}x speichern, dann klappt es.")

    leser = LESER.get(endung)
    if leser is None:
        raise FormatNichtUnterstuetzt(f"Format {endung} wird nicht gelesen.")

    try:
        return leser(pfad)
    except FormatNichtUnterstuetzt:
        raise
    except zipfile.BadZipFile as exc:
        raise FormatNichtUnterstuetzt(
            f"Die Datei ist kein gueltiges {endung}-Archiv "
            f"(beschaedigt oder falsche Endung): {exc}") from exc
    except ElementTree.ParseError as exc:
        raise FormatNichtUnterstuetzt(
            f"Der Inhalt der Datei liess sich nicht lesen: {exc}") from exc


def leer_grund(pfad) -> str:
    """Warum eine gueltige Datei keinen Text hergibt (AK 4).

    "Analysiert, nichts gefunden" ist eine Antwort. "nicht_extrahiert"
    ohne Grund ist eine Endlosschleife.
    """
    pfad = Path(pfad)
    if pfad.suffix.lower() == ".docx":
        # #998: bis v1.7.46 erreichte .docx diese Stelle gar nicht — es
        # gab also nicht einmal die ehrliche "leer"-Meldung, sondern
        # schlicht keine Auskunft.
        return ("Das Word-Dokument enthaelt keinen Text — weder in "
                "Absaetzen noch in Tabellen, Kopf- oder Fusszeilen. "
                "Besteht es aus eingebetteten Bildern, braucht es OCR.")
    if pfad.suffix.lower() != ".pptx":
        return "Die Datei enthaelt keinen auslesbaren Text."
    try:
        with zipfile.ZipFile(pfad) as z:
            bilder = [n for n in z.namelist() if n.startswith("ppt/media/")]
    except Exception:
        return "Die Datei enthaelt keinen auslesbaren Text."
    if bilder:
        return (f"Die Praesentation enthaelt {len(bilder)} Bild(er) und "
                "keinen Text — vermutlich abfotografierte oder gescannte "
                "Folien. Dafuer braucht es OCR.")
    return "Die Praesentation enthaelt keine Textfelder."
