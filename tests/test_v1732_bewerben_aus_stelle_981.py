"""Tests fuer v1.7.32 — #981 (D43): Bewerben aus der Stelle.

Drei Teile aus demselben Durchgang wie #980.

**A — ein Status, den es nicht gibt.** Der Dialog im Stellen-Tab bot
"Entwurf" an; `VALID_STATUSES` kennt den Wert nicht, und
`POST /api/applications` prueste ihn gar nicht. Die so erzeugte
Bewerbung war danach fuer `bewerbung_status_aendern`, die
Statusverteilung und die Status-Journey unsichtbar — sie sieht nicht
kaputt aus, sie ist nur nirgends dabei.

G20/#896 hatte genau diesen Wert aus `STATUS_OPTIONS` entfernt und einen
Paritaetstest gebaut. Der Test liest `utils.js`; die Inline-Optionen in
den Seiten sah er nicht. **Ein Guard, der nur eine von mehreren Quellen
liest, deckt nur eine ab.**

**B — `bewerbung_schreiben` ohne Parameter.** Deshalb gab es keinen
vorbefuellten Knopf an Stelle und Bewerbung, obwohl das Muster seit
G16/#706 steht. K11/#694 hatte die uebrigen Builder bereinigt, dieser
blieb.

**C — die Einstiege**, nach demselben Muster wie G16.
"""
import re
from pathlib import Path

import pytest

from bewerbungs_assistent.tools.bewerbungen import (
    EINSTIEGS_STATUS,
    VALID_STATUSES,
)

WURZEL = Path(__file__).resolve().parents[1]
FRONTEND = WURZEL / "frontend" / "src"


def _builder():
    """Den Prompt-Builder isoliert laden, ohne den MCP-Server zu starten."""
    quelle = (WURZEL / "src" / "bewerbungs_assistent" / "tools"
              / "workflows.py").read_text(encoding="utf-8")
    a = quelle.index("    def _bewerbung_schreiben(")
    b = quelle.index("    def _interview_vorbereitung(")
    code = "\n".join(z[4:] if z.startswith("    ") else z
                     for z in quelle[a:b].splitlines())
    ns: dict = {}
    exec(compile(code, "workflows_bewerbung_schreiben", "exec"), ns)
    return ns["_bewerbung_schreiben"]


# ── A: gueltige Status ──────────────────────────────────────────────

def test_981_whitelist_ist_importierbar():
    """Sie lag als lokale Variable IN `bewerbung_status_aendern`.

    Damit konnte sie genau ein Tool schuetzen — der REST-Endpunkt schrieb
    jeden Wert durch. Eine Whitelist an einer von mehreren Schreibstellen
    ist keine Whitelist (dieselbe Lehre wie #913 und #924).
    """
    assert "entwurf" not in VALID_STATUSES
    assert "in_vorbereitung" in VALID_STATUSES
    assert "beworben" in VALID_STATUSES


def test_981_einstiegsstatus_sind_die_zwei_aus_170():
    assert set(EINSTIEGS_STATUS) == {"in_vorbereitung", "beworben"}
    assert set(EINSTIEGS_STATUS) <= VALID_STATUSES


def test_981_endpunkt_weist_unbekannten_status_ab():
    quelle = (WURZEL / "src" / "bewerbungs_assistent"
              / "dashboard.py").read_text(encoding="utf-8")
    block = quelle[quelle.index("async def api_add_application"):]
    block = block[:block.index("@app.put(\"/api/applications/{app_id}/status\")")]
    assert "VALID_STATUSES" in block
    assert "status_code=400" in block


def test_981_stellen_dialog_bietet_entwurf_nicht_mehr_an():
    """Der Anlegeweg. Der Wert selbst bleibt anderswo erlaubt — siehe
    den naechsten Test."""
    seite = (FRONTEND / "pages" / "JobsPage.jsx").read_text(encoding="utf-8")
    assert 'value="entwurf"' not in seite
    assert 'value="in_vorbereitung"' in seite


def test_981_altdaten_mit_entwurf_bleiben_auffindbar():
    """Ehrliche Abweichung vom Issue-Text, bewusst getroffen.

    Das Akzeptanzkriterium lautete: `entwurf` kommt unter `frontend/src`
    nicht mehr vor. Das waere zu weit gegangen — in gewachsenen
    Datenbanken STEHEN Bewerbungen mit diesem Status, erzeugt von genau
    diesem Fehler. Wuerde der Filter im Bewerbungs-Tab und die Farbe in
    der Statistik verschwinden, waeren diese Datensaetze nicht mehr
    auffindbar und nicht mehr korrigierbar.

    Die Regel lautet deshalb: kein ANLEGEWEG bietet den Wert an;
    Anzeigen und Filtern bleibt.
    """
    filter_seite = (FRONTEND / "pages"
                    / "ApplicationsPage.jsx").read_text(encoding="utf-8")
    assert 'value="entwurf"' in filter_seite, (
        "Der Filter fuer Altdaten muss bleiben")


def _status_auswahlen(seite: str) -> list[set[str]]:
    """Die `<option>`-Werte jeder Auswahl, die an `status` haengt.

    Bewusst eng: eine erste Fassung las ALLE `<option>` der Datei und
    schlug an Sortier- und Blacklist-Werten an ("score_asc", "firma").
    Ein Waechter, der bei korrektem Code Alarm gibt, wird nach dem
    zweiten Mal ignoriert (Telefon-Lehre vom 07.08.).
    """
    auswahlen = []
    for stueck in seite.split("<SelectInput")[1:]:
        kopf = stueck.split(">", 1)[0]
        if "status" not in kopf:
            continue
        rumpf = stueck.split("</SelectInput>", 1)[0]
        auswahlen.append(set(re.findall(r'<option value="([a-z_]*)"', rumpf)))
    return auswahlen


def test_981_guard_findet_die_status_auswahl():
    """Gegenprobe zur Eingrenzung: der Guard muss ueberhaupt etwas sehen."""
    seite = (FRONTEND / "pages" / "JobsPage.jsx").read_text(encoding="utf-8")
    auswahlen = _status_auswahlen(seite)
    assert auswahlen, "keine Status-Auswahl gefunden — der Guard laeuft leer"
    assert any("in_vorbereitung" in a for a in auswahlen)


@pytest.mark.parametrize("datei", ("pages/JobsPage.jsx",))
def test_981_guard_kein_anlegeweg_mit_unbekanntem_status(datei):
    """Der Guard, den G20/#896 an dieser Stelle nicht hatte.

    Er liest die Inline-`<option>`-Werte der Seiten, nicht nur
    `utils.js` — genau die Luecke, durch die `entwurf` ueberlebt hat.
    """
    seite = (FRONTEND / datei).read_text(encoding="utf-8")
    for werte in _status_auswahlen(seite):
        unbekannt = {w for w in werte if w and w not in VALID_STATUSES}
        assert not unbekannt, (datei, unbekannt)


# ── B: bewerbung_schreiben vorbefuellbar ────────────────────────────

def test_981_ohne_parameter_wird_erst_geklaert():
    """Ohne konkrete Stelle entstehen keine Unterlagen — ein Lebenslauf
    ohne Ziel ist kein angepasster Lebenslauf."""
    text = _builder()()
    assert "SCHRITT 0: KONTEXT KLAEREN" in text
    assert "bewerbungen_anzeigen" in text
    assert "Ohne konkrete Stelle keine Unterlagen" in text


def test_981_mit_stelle_wird_nur_der_umfang_gefragt():
    text = _builder()(stelle="Fachkraft", firma="Musterbetrieb GmbH",
                      job_hash="abc123")
    assert "SCHRITT 0: UMFANG KLAEREN" in text
    assert "KONTEXT (vorbefuellt)" in text
    assert "job_hash: abc123" in text


def test_981_mit_allem_keine_rueckfrage():
    text = _builder()(stelle="Fachkraft", firma="Musterbetrieb GmbH",
                      job_hash="abc123", bewerbung_id="APP-1",
                      nur="lebenslauf")
    assert "SCHRITT 0 entfaellt" in text
    assert "NICHT nachfragen" in text


def test_981_nur_lebenslauf_laesst_das_anschreiben_weg():
    text = _builder()(job_hash="x", nur="lebenslauf")
    assert "SCHRITT 4: LEBENSLAUF" in text
    assert "SCHRITT 5: ANSCHREIBEN" not in text


def test_981_nur_anschreiben_laesst_den_lebenslauf_weg():
    text = _builder()(job_hash="x", nur="anschreiben")
    assert "SCHRITT 5: ANSCHREIBEN" in text
    assert "SCHRITT 4: LEBENSLAUF" not in text


def test_981_unbekannter_umfang_liefert_beides():
    """Ein Tippfehler im Parameter darf nicht dazu fuehren, dass gar
    nichts erstellt wird."""
    text = _builder()(job_hash="x", nur="quatsch")
    assert "SCHRITT 4: LEBENSLAUF" in text
    assert "SCHRITT 5: ANSCHREIBEN" in text


def test_981_bestehende_bewerbung_wird_ergaenzt_statt_verdoppelt():
    """Der alte Text endete mit "Bewerbung im Tracking erfassen" — bei
    einer bereits erfassten Bewerbung eine Dublette."""
    text = _builder()(bewerbung_id="APP-1", nur="lebenslauf")
    assert "KEINE neue Bewerbung anlegen" in text
    assert "cv_path" in text


def test_981_ohne_bewerbung_id_wird_die_einstiegsfrage_gestellt():
    text = _builder()(job_hash="x", nur="lebenslauf")
    assert "bewerbung_erstellen" in text
    assert "#170" in text


def test_981_stilarchiv_wird_genutzt():
    """Es existiert seit #577 und kam im Prompt gar nicht vor."""
    text = _builder()(job_hash="x")
    assert "stilarchiv_kontext" in text
    assert "stilarchiv_speichern" in text


def test_981_volltext_wird_geprueft():
    """C39/#952: eine gekappte Beschreibung fuehrt zu Unterlagen, denen
    der Anforderungsteil fehlt."""
    text = _builder()(job_hash="x")
    assert "stellenbeschreibung_nachladen" in text


def test_981_signatur_kennt_alle_parameter():
    """`/api/workflow-prompt/{name}` reicht Query-Argumente nur durch,
    wenn die Signatur sie kennt (K11/G16-Muster). Ohne diesen Test
    faellt eine entfernte Parameter still auf den Standard zurueck."""
    import inspect
    sig = inspect.signature(_builder())
    assert set(sig.parameters) == {
        "stelle", "firma", "job_hash", "bewerbung_id", "nur"}


# ── C: die Einstiege ────────────────────────────────────────────────

def test_981_bewerbungen_tab_hat_die_zwei_knoepfe():
    seite = (FRONTEND / "pages"
             / "ApplicationsPage.jsx").read_text(encoding="utf-8")
    assert "unterlagenKopieren" in seite
    assert 'unterlagenKopieren(application, "lebenslauf")' in seite
    assert 'unterlagenKopieren(application, "anschreiben")' in seite


def test_981_knoepfe_nur_solange_sie_etwas_bewirken():
    """Bei `beworben` oder gesetztem Dokumentpfad waeren sie eine
    Einladung zur Dublette."""
    seite = (FRONTEND / "pages"
             / "ApplicationsPage.jsx").read_text(encoding="utf-8")
    assert 'application.status === "in_vorbereitung" && !application.cv_path' in seite
    assert ('application.status === "in_vorbereitung" '
            '&& !application.cover_letter_path') in seite


def test_981_knopf_reicht_die_bewerbung_durch():
    """Ohne `bewerbung_id` legt der Prompt eine zweite Bewerbung an."""
    seite = (FRONTEND / "pages"
             / "ApplicationsPage.jsx").read_text(encoding="utf-8")
    block = seite[seite.index("async function unterlagenKopieren"):]
    block = block[:block.index("async function openTimeline")]
    assert "bewerbung_id: application?.id" in block
    assert "workflow-prompt/bewerbung_schreiben" in block


def test_981_stellen_tab_bietet_die_unterlagen_nach_dem_erfassen_an():
    seite = (FRONTEND / "pages" / "JobsPage.jsx").read_text(encoding="utf-8")
    assert "unterlagenAnleitungKopieren" in seite
    block = seite[seite.index("async function saveApplication"):]
    block = block[:block.index("async function unterlagenAnleitungKopieren")]
    assert 'entwurf.status === "in_vorbereitung"' in block


def test_981_keine_prompt_knopf_an_der_stellenkarte():
    """Bewusst nicht gebaut: erst erfassen, dann Unterlagen. Sonst
    entstehen Unterlagen ohne Bewerbung, und der Prompt muesste am Ende
    doch erfassen — Dublettenrisiko."""
    seite = (FRONTEND / "pages" / "JobsPage.jsx").read_text(encoding="utf-8")
    treffer = seite.count("workflow-prompt/bewerbung_schreiben")
    assert treffer == 1, treffer
