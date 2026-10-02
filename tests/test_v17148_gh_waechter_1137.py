"""#1137 — Der PII-Wächter prüfte nur einen festen Wortlaut.

Der Hook `scripts/gh_pii_guard.py` suchte `gh issue|pr create|comment|edit`
als zusammenhängende Wortfolge. Ungeprüft gingen deshalb durch:
`gh -R <Repo> issue create` (gängig!), `gh issue close --comment`,
`gh pr review --body`, `gh pr merge --body`, `gh gist create`,
`gh api -F body=…` und `--raw-field`, dazu jeder Text, der erst aus einer
Shell-Variablen oder Datei eingesetzt wird (der Hook sah nur den Platzhalter).

Hier: jede Aufrufform in BEIDE Richtungen (die PII-Form wird blockiert, die
harmlose Form geht durch), aus einem FREMDEN Arbeitsverzeichnis (DoD 8c: Grün im
Repo-Wurzelverzeichnis ist kein Beweis), und die Registrierung des Hooks.

Zur Testgestaltung: bewusst KEINE realen Namen. Als Auslöser genügt eine
generische Fundstelle (Telefonnummer); die Namenserkennung hat ihre eigenen Tests.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "scripts" / "gh_pii_guard.py"

MIT_PII = "Rueckfragen bitte an +49 40 123456789."
OHNE_PII = "Die Musterfirma GmbH dient hier als Platzhalter."


def _guard(command: str, cwd: Path) -> tuple[int, str]:
    # Der Hook laeuft in einem LEEREN Unterordner: die Dateien des Tests liegen
    # eine Ebene darueber, ein relativer Name findet sie nur ueber das `cd` im
    # Kommando — nicht, weil Hook und Dateien zufaellig im selben Ordner stehen.
    leer = cwd / "leer"
    leer.mkdir(exist_ok=True)
    r = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": command}}).encode("utf-8"),
        capture_output=True, cwd=str(leer))
    return r.returncode, r.stderr.decode("utf-8", "replace")


@pytest.fixture
def fremd(tmp_path):
    """Ein fremdes Arbeitsverzeichnis mit einer belasteten und einer sauberen Datei."""
    (tmp_path / "pii.md").write_text(MIT_PII, encoding="utf-8")
    (tmp_path / "sauber.md").write_text(OHNE_PII, encoding="utf-8")
    (tmp_path / "pii.json").write_text(json.dumps({"body": MIT_PII}), encoding="utf-8")
    (tmp_path / "sauber.json").write_text(json.dumps({"body": OHNE_PII}), encoding="utf-8")
    return tmp_path


def test_1137_der_ausloeser_wird_ueberhaupt_erkannt():
    """Gegenprobe des Tests selbst: ohne sie koennten alle Tests gruen sein,
    weil nichts erkannt wird — derselbe Fehlertyp, den der Hook verhindern soll."""
    sys.path.insert(0, str(GUARD.parent))
    from scrub_pii import find_pii
    assert find_pii(MIT_PII) and not find_pii(OHNE_PII)


# ══ Was blockiert werden muss ═══════════════════════════════════════════

BLOCKIERT = [
    # Grundform
    'gh issue create --title T --body "{p}"',
    'gh issue comment 5 --body "{p}"',
    'gh issue edit 5 --body "{p}"',
    'gh pr create --title T --body "{p}"',
    'gh release create v1.0.0 --title T --notes "{p}"',
    # vorangestelltes -R / --repo in allen Stellungen (gaengig!)
    'gh -R MadGapun/PBP issue create --title T --body "{p}"',
    'gh --repo MadGapun/PBP issue comment 5 --body "{p}"',
    'gh issue comment 5 -R MadGapun/PBP --body "{p}"',
    'gh issue comment 5 --repo=MadGapun/PBP --body "{p}"',
    # bisher ungeprueft: Schliessen, Review, Merge, Gist, Repo-Beschreibung
    'gh issue close 5 --comment "{p}"',
    'gh issue close 5 -c "{p}"',
    'gh pr review 5 --body "{p}"',
    'gh pr review 5 -b "{p}"',
    'gh pr merge 5 --body "{p}"',
    'gh gist create --desc "{p}" nichtda.md',
    'gh repo edit --description "{p}"',
    'gh release edit v1.0.0 --notes "{p}"',
    # gh api in allen Feldformen
    'gh api repos/x/y/issues/5/comments -f body="{p}"',
    'gh api repos/x/y/issues/5/comments -F body="{p}"',
    'gh api repos/x/y/issues/5/comments --raw-field body="{p}"',
    'gh api repos/x/y/issues/5/comments --field body="{p}"',
    'gh api -X POST repos/x/y/issues/5/comments -f body="{p}"',
    # in einer Kette
    'cd /tmp && gh issue create --body "{p}"',
    'echo hallo; gh issue create --body "{p}"',
    'true && gh -R MadGapun/PBP issue create --body "{p}"',
    # ein Text, der mit "-" beginnt, ist ein Text und kein Schalter
    'gh issue create --body "- {p}"',
    # Heredoc
    "gh issue create --title T --body \"$(cat <<'EOF'\n{p}\nEOF\n)\"",
    "gh issue comment 5 --body-file - <<'EOF'\n{p}\nEOF",
]


@pytest.mark.parametrize("vorlage", BLOCKIERT)
def test_1137_pii_in_dieser_aufrufform_wird_blockiert(vorlage, fremd):
    code, meldung = _guard(vorlage.format(p=MIT_PII), fremd)
    assert code == 2, f"durchgelassen: {vorlage}"
    assert "BLOCKIERT" in meldung


DATEI_FORMEN = [
    'gh issue create --body-file {d}/pii.md',
    'gh issue create -F {d}/pii.md',
    'gh issue comment 5 --body-file={d}/pii.md',
    'gh release create v1 --notes-file {d}/pii.md',
    'gh gist create {d}/pii.md',
    'gh api repos/x/y/issues/5/comments --input {d}/pii.json',
    'gh api repos/x/y/issues/5/comments -F body=@{d}/pii.md',
    # die Datei steht ueber eine feste Variable im selben Kommando
    'S={d} && gh issue create --body-file "$S/pii.md"',
    'export S={d}; gh issue create --body-file ${{S}}/pii.md',
    # relativ, nach einem cd
    'cd {d} && gh issue create --body-file pii.md',
    # Standardeingabe aus einer Datei
    'gh issue create --body-file - < {d}/pii.md',
    'cat {d}/pii.md | gh issue create --body-file -',
    'echo "' + MIT_PII + '" | gh issue create --body-file -',
]


@pytest.mark.parametrize("vorlage", DATEI_FORMEN)
def test_1137_pii_in_einer_datei_wird_blockiert(vorlage, fremd):
    code, meldung = _guard(vorlage.format(d=str(fremd).replace("\\", "/")), fremd)
    assert code == 2, f"durchgelassen: {vorlage}"
    assert "BLOCKIERT" in meldung


# ══ Was nicht pruefbar ist, wird nicht ignoriert ═════════════════════════

NICHT_PRUEFBAR = [
    'gh issue create --title T --body "$TEXT"',
    'gh issue create --title T --body "$(cat /tmp/gibt-es-nicht.md)"',
    'gh issue create --title T --body "`cat /tmp/gibt-es-nicht.md`"',
    'gh issue create --body-file "$DATEI"',
    'gh issue create --body-file nicht_vorhanden.md',
    'gh issue create --body-file -',
    'gh issue comment 5 --body-file "$(mktemp)"',
    'gh gist create "$F"',
    'gh api repos/x/y/issues/5/comments -f body="$TEXT"',
]


@pytest.mark.parametrize("command", NICHT_PRUEFBAR)
def test_1137_ein_nicht_pruefbarer_text_wird_blockiert_nicht_ignoriert(command, fremd):
    code, meldung = _guard(command, fremd)
    assert code == 2, f"durchgelassen: {command}"
    assert "laesst sich vorab nicht pruefen" in meldung
    assert "--body-file" in meldung, "die Meldung nennt den Ausweg"


# ══ Was durchgehen muss ═══════════════════════════════════════════════════

DURCH = [
    # lesende Formen tragen nichts hinaus, auch mit PII im Suchtext
    'gh issue list --state open',
    'gh issue view 5',
    'gh -R MadGapun/PBP issue view 5',
    'gh pr checks 5',
    'gh run list --limit 3',
    'gh release list --limit 5',
    'gh api repos/x/y/issues',
    "gh api repos/x/y/issues --jq '.[].title'",
    'gh search issues "{p}"',
    # eine lesende Aktion mit einem Schalter, der anderswo Text traegt
    'gh issue list --label "{p}"',
    'gh auth status',
    # saubere Schreibformen
    'gh issue create --title T --body "{o}"',
    'gh -R MadGapun/PBP issue comment 5 --body "{o}"',
    'gh issue close 5 --comment "{o}"',
    'gh pr merge 5 --body "{o}"',
    'gh api repos/x/y/issues/5/comments -f body="{o}"',
    'gh issue create --body "- {o}"',
    "gh issue create --title T --body \"$(cat <<'EOF'\n{o}\nEOF\n)\"",
    "gh issue comment 5 --body-file - <<'EOF'\n{o}\nEOF",
    'echo "{o}" | gh issue create --body-file -',
    # kein gh-Aufruf: andere Werkzeuge pruefen ihre Texte selbst
    'git commit -m "{p}"',
    'echo "{p}"',
    'ghost "{p}"',
    'git log --grep gh',
]


@pytest.mark.parametrize("vorlage", DURCH)
def test_1137_harmlose_formen_gehen_durch(vorlage, fremd):
    code, meldung = _guard(vorlage.format(p=MIT_PII, o=OHNE_PII), fremd)
    assert code == 0, f"blockiert: {vorlage}\n{meldung}"


DATEI_DURCH = [
    'gh issue create --body-file {d}/sauber.md',
    'gh issue create -F {d}/sauber.md',
    'gh release create v1 --notes-file {d}/sauber.md',
    'gh gist create {d}/sauber.md',
    'gh api repos/x/y/issues/5/comments --input {d}/sauber.json',
    'gh api repos/x/y/issues/5/comments -F body=@{d}/sauber.md',
    'S={d} && gh issue create --body-file "$S/sauber.md"',
    'cd {d} && gh issue create --body-file sauber.md',
    'gh issue create --body-file - < {d}/sauber.md',
    'cat {d}/sauber.md | gh issue create --body-file -',
]


@pytest.mark.parametrize("vorlage", DATEI_DURCH)
def test_1137_saubere_dateien_gehen_durch(vorlage, fremd):
    code, meldung = _guard(vorlage.format(d=str(fremd).replace("\\", "/")), fremd)
    assert code == 0, f"blockiert: {vorlage}\n{meldung}"


# ══ Die Verdrahtung ════════════════════════════════════════════════════════

def test_1137_der_hook_ist_fuer_bash_und_mcp_eingetragen():
    """Ein Schutz zaehlt erst, wenn er auch AUFGERUFEN wird (DoD 8c)."""
    einstellungen = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    pre = einstellungen["hooks"]["PreToolUse"]
    matcher = {e["matcher"]: [h["command"] for h in e["hooks"]] for e in pre}
    assert "Bash" in matcher and "mcp__.*" in matcher
    for befehle in matcher.values():
        assert any("gh_pii_guard.py" in b for b in befehle)


def test_1137_die_alte_festverdrahtete_suche_ist_weg():
    """Der Fehler war ein fester Wortlaut: `gh issue create` als Wortfolge."""
    quelle = GUARD.read_text(encoding="utf-8")
    assert "_RISKANT" not in quelle
    assert "_gh_texte" in quelle and "_segmente" in quelle


# ══ Der Wochen-Sweep sieht den ganzen Bestand ═══════════════════════════════

def _sweep():
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib
    import gh_pii_sweep
    return importlib.reload(gh_pii_sweep)


def test_1137_der_sweep_liest_alle_veroeffentlichungen_seitenweise(monkeypatch):
    """Gemessen: `gh release list --limit 200` bei 427 Veroeffentlichungen —
    die aeltesten 227 sah er nie und meldete 'keine neue PII'."""
    sweep = _sweep()
    aufrufe = []

    def _gh(args):
        aufrufe.append(args)
        return "\n".join(json.dumps({"tagName": f"v1.0.{i}", "body": f"Notiz {i}"})
                         for i in range(427))

    monkeypatch.setattr(sweep, "_gh", _gh)
    erg = sweep.releases_laden()
    assert len(erg) == 427
    assert erg[-1]["tagName"] == "v1.0.426"
    assert "--paginate" in aufrufe[0] and "200" not in aufrufe[0]
    assert len(aufrufe) == 1, "ein Durchgang statt eines Aufrufs je Veroeffentlichung"


def test_1137_der_sweep_findet_pii_in_einer_alten_veroeffentlichung(monkeypatch, capsys):
    sweep = _sweep()
    alle = [{"tagName": f"v1.0.{i}", "body": "harmloser Text"} for i in range(300)]
    alle[250]["body"] = MIT_PII  # jenseits der alten Grenze von 200
    monkeypatch.setattr(sweep, "issues_laden", lambda nur_offen: [])
    monkeypatch.setattr(sweep, "releases_laden", lambda: alle)
    code = sweep.main(["--mit-releases", "--ohne-namen"])
    ausgabe = capsys.readouterr().out
    assert code == 1
    assert "Release v1.0.250" in ausgabe
    assert "Geprueft: 300 Artefakte" in ausgabe


def test_1137_stoesst_die_abfrage_an_ihre_grenze_bricht_der_sweep_ab(monkeypatch, capsys):
    """Ein Sweep, der an der Grenze unbemerkt abschneidet, meldet 'sauber' zu Unrecht."""
    sweep = _sweep()
    voll = [{"number": i, "title": "t", "body": "", "comments": [],
             "createdAt": "2026-01-01"} for i in range(sweep.LIMIT)]
    monkeypatch.setattr(sweep, "_gh", lambda args: json.dumps(voll))
    code = sweep.main(["--ohne-namen"])
    ausgabe = capsys.readouterr().out
    assert code == 3
    assert "ABBRUCH" in ausgabe and "Abfragegrenze" in ausgabe
    assert "Keine neue PII" not in ausgabe


def test_1137_unter_der_grenze_laeuft_der_sweep_normal(monkeypatch, capsys):
    sweep = _sweep()
    wenige = [{"number": i, "title": "t", "body": "", "comments": [],
               "createdAt": "2026-01-01"} for i in range(5)]
    monkeypatch.setattr(sweep, "_gh", lambda args: json.dumps(wenige))
    assert sweep.main(["--ohne-namen"]) == 0
    assert "Keine neue PII" in capsys.readouterr().out


def test_1137_die_alte_grenze_von_200_steht_nirgends_mehr():
    quelle = (ROOT / "scripts" / "gh_pii_sweep.py").read_text(encoding="utf-8")
    assert '"--limit", "200"' not in quelle
    assert '"--limit", "1000"' not in quelle


# ══ Fehlalarme des Wochen-Sweeps, die der erste Lauf ueber alles fand ═════════

@pytest.mark.parametrize("adresse", [
    "noreply-accounts@google.com",
    "notify-noreply@google.com",
    "payments-noreply@google.com",
    "noreply@firma.example",
    "no-reply@portal.example",
    "donotreply-jobs@portal.example",
])
def test_1137_automaten_absender_sind_keine_kontaktdaten(adresse):
    """Gemessen: drei Absender eines Benachrichtigungsdienstes standen als
    EMAIL-Fund in einem Kommentar — der Sweep meldete einen Zustand, der in
    Ordnung war."""
    sys.path.insert(0, str(GUARD.parent))
    from scrub_pii import _is_safe_email
    assert _is_safe_email(adresse), adresse


@pytest.mark.parametrize("adresse", [
    "erika.beispiel@firma.example",
    "e.beispiel@gmail.com",
    "bewerbung@musterfirma.example",
])
def test_1137_persoenliche_adressen_bleiben_ein_fund(adresse):
    sys.path.insert(0, str(GUARD.parent))
    from scrub_pii import _is_safe_email
    assert not _is_safe_email(adresse), adresse


def test_1137_ein_portalname_wird_gefiltert_der_klarname_daneben_nicht():
    """Release v1.0.0 nennt ein Portal als Quellen-Feature UND einen Klarnamen:
    der erste ist ein Fehlalarm, der zweite bleibt gemeldet."""
    sweep = _sweep()
    rest = sweep._gefiltert("Release v1.0.0", ["FIRMA: Hays", "USER: Erika Beispiel"])
    assert rest == ["USER: Erika Beispiel"]


def test_1137_die_listen_des_sweeps_tragen_keine_klarnamen():
    """AUSNAHMEN nennt Quellen-Keys (klein), BEWUSST_GELASSEN nur Zahlen je Art —
    sonst waere die Liste selbst die Veroeffentlichung, die der Sweep verhindern soll."""
    sweep = _sweep()
    for stelle, erwartet in sweep.AUSNAHMEN.items():
        for e in erwartet:
            art, _, name = e.partition(": ")
            if art == "FIRMA" and stelle.startswith(("#1087", "#1075", "#1074", "#1064")):
                assert name == name.lower(), (stelle, e)
    for stelle, arten in sweep.BEWUSST_GELASSEN.items():
        assert all(isinstance(n, int) for n in arten.values()), stelle
