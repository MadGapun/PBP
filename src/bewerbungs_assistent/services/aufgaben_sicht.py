"""Die eine Liste offener Dinge — fuer Dashboard, Aufgaben-Tab und MCP.

Warum dieses Modul entsteht (#976 G27, #982 G30, #983 G31)
----------------------------------------------------------

`aufgaben_uebersicht` (D35/#815) fuehrt Todos, Nachfassungen und Termine
seit v1.7.12 zu einer Liste zusammen. Die Aggregation stand danach aber
ZWEIMAL im Code: einmal im MCP-Tool (`tools/tasks.py`) und einmal im
REST-Endpunkt (`dashboard.py`). Zusammengehalten wurden beide von einem
Kommentar — "dieselbe Logik wie das MCP-Tool aufgaben_uebersicht".

Der Kommentar stimmte schon nicht mehr. Der REST-Weg kannte `ueberholt`,
`ueberholt_grund`, `notiz` und erzeugte fehlende Nachfass-Texte beim
Lesen (#945); der MCP-Weg kannte `erledigen_mit`/`hinfaellig_mit` und
eine andere Kurzbeschreibung. Wer eine Nachfassung im Aufgaben-Tab ansah
und dieselbe ueber Claude, bekam zwei verschiedene Datensaetze.

Das ist zum dritten Mal dasselbe Muster: `fit_analyse` gegen
`calculate_score` trug den Satz "dieselbe Logik wie ..." fuenfmal, bevor
#963 gemessen hat, dass die Werte um bis zu sechs Punkte auseinanderlagen.
**Ein Kommentar haelt nichts zusammen.** Deshalb hier ein Nadeloehr statt
einer dritten Kopie.

Was neu dazukommt
-----------------

* **Vorbereitungszeilen (#982).** Bisher entstand die Empfehlung
  "Interview vorbereiten" aus der ANZAHL der Bewerbungen im Status
  `interview` — drei Bloecke tiefer stand der konkrete Termin, den die
  Empfehlung nicht kannte. Eine Zaehlung ist keine Handlung. Jetzt
  erzeugt jeder Interview-Termin der naechsten sieben Tage genau eine
  Zeile mit Datum, und nur dann, wenn nicht ohnehin schon ein
  Vorbereitungs-Todo dazu existiert.
* **Termine gehoeren in dieselbe Liste (#983, Nutzerentscheidung
  07.09.2026).** K17/#700 bleibt in der Sache: eine Nachfassung ist kein
  Termin und traegt nie eine Uhrzeit. Die Unterscheidung leistet das
  Feld `herkunft` an jeder Zeile, nicht ein zweiter Block.
"""

from datetime import date, timedelta

# Termine, zu denen man sich vorbereitet (#982).
VORBEREITUNGS_TYPEN = frozenset({
    "interview", "zweitgespraech", "zweitgespräch", "assessment",
    "probearbeiten", "vorstellungsgespraech", "vorstellungsgespräch",
})

# Wie weit voraus eine Vorbereitungszeile entsteht. Sieben Tage, weil das
# der Horizont des Dashboard-Blocks ist — eine Zeile fuer einen Termin in
# drei Wochen waere heute keine Handlung.
VORBEREITUNGS_HORIZONT_TAGE = 7

# Termine, die die Sicht ueberhaupt kennt.
TERMIN_HORIZONT_TAGE = 30

GRUPPEN = ("ueberfaellig", "heute", "diese_woche", "spaeter",
           "ohne_faelligkeit")

# Herkuenfte, die auf dem Dashboard im Block "Offen" stehen.
HERKUENFTE = ("todo", "nachfass", "termin", "vorbereitung")


def _kurz(wert) -> str:
    return str(wert or "")[:8]


def _nachfass_texte(fu: dict, app: dict) -> tuple[str, bool, str, str]:
    """Beschreibung, Ueberholt-Flag, Grund und Claude-Auftrag (#945).

    Fuenf von sieben Nachfassungen im Bestand hatten ein leeres
    Beschreibungsfeld; wer sie oeffnete, sah Firma und Datum und musste
    den Rest selbst zusammensuchen. Der Text entsteht deshalb beim
    Lesen, nicht beim Schreiben.
    """
    from .nachfass_text import claude_prompt, ist_ueberholt, nachfass_text

    weg, warum = ist_ueberholt(fu, app)
    text = (fu.get("template") or "").strip()
    if not text and app:
        text = nachfass_text(app)
    return text, bool(weg), warum or "", (claude_prompt(app) if app else "")


def _todos(db, status: str) -> list[dict]:
    eintraege = []
    for t in db.list_tasks(nur_offen=(status == "offen")):
        if status == "erledigt" and t.get("status") != "erledigt":
            continue
        app = db.get_application(t.get("application_id") or "") or {}
        eintraege.append({
            "herkunft": "todo",
            "id": t["id"],
            "titel": t.get("titel", ""),
            "beschreibung": t.get("beschreibung") or "",
            "notiz": t.get("notiz") or "",
            "typ": t.get("typ") or "custom",
            "status": t.get("status"),
            "faellig_am": t.get("faellig_am"),
            "bewerbung_id": t.get("application_id"),
            "firma": app.get("company"),
            # v1.7.23 (#945): der Aufrufer soll nicht wissen muessen, aus
            # welchem Topf ein Eintrag stammt — die Sicht nennt den
            # passenden Aufruf selbst.
            "erledigen_mit": f"todo_erledigen('{t['id']}')",
            "hinfaellig_mit": f"todo_hinfaellig('{t['id']}')",
        })
    return eintraege


def _nachfassungen(db) -> list[dict]:
    eintraege = []
    try:
        offen = db.get_pending_follow_ups()
    except Exception:
        return eintraege
    for fu in offen:
        app = db.get_application(fu.get("application_id") or "") or {}
        text, weg, warum, prompt = _nachfass_texte(fu, app)
        eintraege.append({
            "herkunft": "nachfass",
            "id": fu.get("id"),
            "titel": (f"Nachfassen: {app.get('company', '?')} — "
                      f"{app.get('title', '?')}"),
            "beschreibung": text,
            "ueberholt": weg,
            "ueberholt_grund": warum,
            "claude_prompt": prompt,
            "status": "offen",
            # K17/#700: eine Nachfassung traegt NIE eine Uhrzeit. Sie ist
            # eine Erinnerung, kein Termin — der Folgefehler K19 waren
            # Erinnerungen "um 02:00 Uhr".
            "faellig_am": fu.get("scheduled_date"),
            "uhrzeit": "",
            "bewerbung_id": fu.get("application_id"),
            "firma": app.get("company"),
            "erledigen_mit": f"follow_up_erledigen('{_kurz(fu.get('id'))}')",
            "hinfaellig_mit": f"follow_up_hinfaellig('{_kurz(fu.get('id'))}')",
        })
    return eintraege


def _termine(db, tage: int) -> list[dict]:
    eintraege = []
    try:
        anstehend = db.get_upcoming_meetings(days=tage)
    except Exception:
        return eintraege
    for m in anstehend:
        roh = m.get("meeting_date") or ""
        eintraege.append({
            "herkunft": "termin",
            "id": m.get("id"),
            "titel": m.get("title") or "Termin",
            "beschreibung": m.get("notes") or "",
            "status": m.get("status") or "geplant",
            "typ": (m.get("meeting_type") or "").lower(),
            "faellig_am": roh[:10],
            "uhrzeit": roh[11:16] if len(roh) >= 16 else "",
            "ort": m.get("location") or "",
            "bewerbung_id": m.get("application_id"),
            "firma": m.get("app_company") or m.get("company"),
            "erledigen_mit": f"meeting_bearbeiten('{_kurz(m.get('id'))}')",
        })
    return eintraege


def vorbereitungszeilen(db, *, tage: int = VORBEREITUNGS_HORIZONT_TAGE,
                        heute: date | None = None,
                        termine: list[dict] | None = None,
                        todos: list[dict] | None = None) -> list[dict]:
    """Je Interview-Termin der naechsten Tage eine Vorbereitungszeile (#982).

    Zwei Faelle erzeugen KEINE Zeile:

    * Es gibt bereits ein Vorbereitungs-Todo zu derselben Bewerbung
      (G16/#706 legt eines mit Faelligkeit am Termindatum an). Dann
      erscheint das Todo — es ist das konkretere Objekt.
    * Der Termin ist abgesagt. `get_upcoming_meetings` filtert das schon,
      aber die Sicht darf sich darauf nicht verlassen: sie wird auch mit
      uebergebenen Listen aufgerufen.
    """
    heute = heute or date.today()
    grenze = (heute + timedelta(days=tage)).isoformat()
    if termine is None:
        termine = _termine(db, tage)
    if todos is None:
        todos = _todos(db, "offen")

    zeilen = []
    for m in termine:
        if (m.get("typ") or "") not in VORBEREITUNGS_TYPEN:
            continue
        if str(m.get("status") or "").lower() in {"abgesagt", "abgelehnt"}:
            continue
        datum = m.get("faellig_am") or ""
        if not datum or datum > grenze or datum < heute.isoformat():
            continue
        if _hat_vorbereitungs_todo(todos, m):
            continue
        # Die Vorbereitung ist am Tag VOR dem Gespraech faellig, nicht am
        # Gespraechstag. Mit dem Termindatum standen beide Zeilen
        # untereinander in derselben Gruppe — "Vorbereiten: X" direkt
        # ueber "X" — und das ist genau die Wiederholung, gegen die das
        # Epic angetreten ist. Aufgefallen erst am erzeugten Screenshot,
        # nicht beim Lesen des Codes.
        #
        # Ist das Gespraech schon morgen oder heute, bleibt es bei heute:
        # eine Vorbereitung mit Faelligkeit in der Vergangenheit waere
        # sofort "ueberfaellig", ohne dass jemand etwas versaeumt hat.
        vorbereitung_am = max(
            heute.isoformat(),
            (date.fromisoformat(datum) - timedelta(days=1)).isoformat())
        zeilen.append({
            "herkunft": "vorbereitung",
            "id": f"vorb_{_kurz(m.get('id'))}",
            "titel": f"Vorbereiten: {m.get('titel') or 'Termin'}",
            "beschreibung": "",
            "status": "offen",
            "faellig_am": vorbereitung_am,
            # Die Vorbereitung ist eine Handlung vor dem Termin, kein
            # Termin. Deshalb keine Uhrzeit (K17).
            "uhrzeit": "",
            "bewerbung_id": m.get("bewerbung_id"),
            "firma": m.get("firma"),
            "termin_id": m.get("id"),
            "termin_datum": datum,
            # Sprung in die G16-Anleitung; sie legt bei Bedarf das Todo an.
            "prompt": "/interview_vorbereitung",
            "erledigen_mit": "todo_anlegen(typ='vorbereitung', ...)",
        })
    return zeilen


def _hat_vorbereitungs_todo(todos: list[dict], termin: dict) -> bool:
    """Erkennung nach #982: gleiche Bewerbung UND (Typ oder Datum)."""
    bewerbung = termin.get("bewerbung_id")
    if not bewerbung:
        return False
    datum = termin.get("faellig_am") or ""
    for t in todos:
        if t.get("bewerbung_id") != bewerbung:
            continue
        if (t.get("typ") or "") == "vorbereitung":
            return True
        if datum and (t.get("faellig_am") or "")[:10] == datum:
            return True
    return False


def sammle(db, *, status: str = "offen",
           termin_tage: int = TERMIN_HORIZONT_TAGE,
           mit_vorbereitung: bool = True,
           heute: date | None = None) -> list[dict]:
    """Alle Toepfe als eine Liste, unsortiert."""
    heute = heute or date.today()
    todos = _todos(db, status)
    eintraege = list(todos)
    if status in ("offen", "alle"):
        eintraege += _nachfassungen(db)
        termine = _termine(db, termin_tage)
        eintraege += termine
        if mit_vorbereitung:
            eintraege += vorbereitungszeilen(
                db, heute=heute, termine=termine, todos=todos)
    return eintraege


def gruppiere(eintraege, *, heute: date | None = None) -> dict:
    """Nach Faelligkeit gruppieren: ueberfaellig, heute, diese Woche, spaeter."""
    heute = heute or date.today()
    heute_iso = heute.isoformat()
    wochenende = (heute + timedelta(days=7)).isoformat()

    gruppen: dict[str, list] = {name: [] for name in GRUPPEN}
    for e in sorted(eintraege,
                    key=lambda x: ((x.get("faellig_am") or "9999-12-31"),
                                   x.get("uhrzeit") or "")):
        f = e.get("faellig_am")
        if not f:
            gruppen["ohne_faelligkeit"].append(e)
        # Ein Termin in der Vergangenheit ist kein Rueckstand, sondern
        # gewesen — nur Handlungen koennen ueberfaellig sein.
        elif f < heute_iso and e.get("herkunft") != "termin":
            try:
                e["ueberfaellig_seit_tagen"] = (
                    heute - date.fromisoformat(f[:10])).days
            except ValueError:
                pass
            gruppen["ueberfaellig"].append(e)
        elif f[:10] == heute_iso:
            gruppen["heute"].append(e)
        elif f <= wochenende:
            gruppen["diese_woche"].append(e)
        else:
            gruppen["spaeter"].append(e)
    return gruppen


def uebersicht(db, *, status: str = "offen", bis_datum: str = "",
               termin_tage: int = TERMIN_HORIZONT_TAGE,
               mit_vorbereitung: bool = True,
               heute: date | None = None) -> dict:
    """Die vollstaendige Sicht — das Nadeloehr fuer MCP, REST und Dashboard."""
    heute = heute or date.today()
    eintraege = sammle(db, status=status, termin_tage=termin_tage,
                       mit_vorbereitung=mit_vorbereitung, heute=heute)
    if bis_datum:
        eintraege = [e for e in eintraege
                     if (e.get("faellig_am") or "9999") <= bis_datum]
    gruppen = gruppiere(eintraege, heute=heute)
    return {
        "anzahl": len(eintraege),
        "ueberfaellig_anzahl": len(gruppen["ueberfaellig"]),
        "gruppen": gruppen,
    }


def dashboard_block(db, *, heute: date | None = None) -> dict:
    """Der Block "Offen" (#976, #983): ueberfaellig, heute, diese Woche.

    "Spaeter" bleibt bewusst draussen — dafuer gibt es den Aufgaben-Tab
    und den Kalender. Was hier steht, ist die naechste Woche.

    Der leere Zustand ist eine Zeile, kein Rahmen (#984): `leer` sagt
    das, damit die Oberflaeche nicht selbst entscheiden muss.
    """
    heute = heute or date.today()
    voll = uebersicht(db, status="offen", heute=heute)
    gruppen = voll["gruppen"]
    sichtbar = {name: gruppen[name]
                for name in ("ueberfaellig", "heute", "diese_woche")}
    anzahl = sum(len(v) for v in sichtbar.values())
    return {
        "gruppen": sichtbar,
        "anzahl": anzahl,
        "ueberfaellig_anzahl": len(sichtbar["ueberfaellig"]),
        "leer": anzahl == 0,
        "spaeter_anzahl": len(gruppen["spaeter"]),
    }
