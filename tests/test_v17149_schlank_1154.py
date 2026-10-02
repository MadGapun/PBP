"""#1154 Punkt 2 — die Stellenliste wird mit vielen Aussortierten nicht mehr langsamer.

Befund (01.10.2026): `stellen_anzeigen` prüft die Wiedergänger-Regel (#671) gegen
ALLE Aussortierten. Gemessen mit 1.200 aktiven Stellen, 100 Bewerbungen und 2.000
Aussortierten zu je 8 KB Text: 2,87 s statt 0,32 s ohne Aussortierte — jedes
Aussortieren machte die Stellenliste etwas langsamer. Vermutet war das Lesen der
Anzeigentexte (`SELECT *`).

Gemessen (cProfile, 9,6 s unter dem Profiler): das Lesen kostet 0,1 s. Die Last war
`find_wiedergaenger_pattern`: für JEDE Stelle der Liste lief es über ALLE
Aussortierten und normalisierte dabei deren Firma neu — 1.200 x 2.000 = 2,4 Millionen
Aufrufe von `normalize_company`, je drei Ersetzungen mit regulärem Ausdruck.

Behoben in zwei Teilen:

1. Die Firma einer aussortierten Stelle wird einmal normalisiert (`_firma_norm`), und
   der Pool (`AussortiertePool`) hat einen Index nach Firma: jede Stelle der Liste
   schaut nur auf die Aussortierten IHRER Firma. 3,2 s -> 0,37 s.
2. Das schlanke Lesen (`get_dismissed_jobs_schlank`) lädt die langen Texte nicht mehr;
   die Prüfung braucht von der Beschreibung nur die Länge.

Die Messtests zählen Aufrufe (auf jeder Maschine gleich) und setzen für die Uhr nur
einen Grenzwert mit großem Abstand.
Gegenprobe: scratchpad/n144/gegenprobe_1154.py.
"""
import asyncio
import importlib
import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture
def umgebung():
    tmpdir = tempfile.mkdtemp(prefix="pbp_schlank1154_")
    os.environ["BA_DATA_DIR"] = tmpdir
    import bewerbungs_assistent.database as _db_mod
    importlib.reload(_db_mod)
    import bewerbungs_assistent.server as _srv
    importlib.reload(_srv)
    db = _srv.db
    assert str(tmpdir) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"
    db.save_profile({"name": "Beispiel Person", "city": "Hamburg"})
    yield db, _srv.mcp
    db.close()
    shutil.rmtree(tmpdir, ignore_errors=True)
    os.environ.pop("BA_DATA_DIR", None)


def _call(mcp, name, args=None):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args or {})
        return getattr(res, "structured_content", res)
    erg = asyncio.run(_run())
    return erg["result"] if isinstance(erg, dict) and set(erg) == {"result"} else erg


def _aussortiert(db, stellen, grund="falsches_fachgebiet", praefix="s1154"):
    """stellen: Liste von (titel, firma, beschreibung); alle werden angelegt und aussortiert."""
    db.save_jobs([{
        "hash": f"{praefix}_{i:05d}", "title": titel, "company": firma,
        "url": f"https://example.com/{praefix}/{i}", "source": "bundesagentur",
        "description": text if text is not None else "x", "score": 20,
        "found_at": "2026-10-01T00:00:00",
    } for i, (titel, firma, text) in enumerate(stellen)])
    for i, (_titel, _firma, text) in enumerate(stellen):
        db.dismiss_job(f"{praefix}_{i:05d}", grund)
        if text is None:   # eine Zeile ohne Beschreibung (NULL), wie sie aus alten Importen kommt
            db.connect().execute("UPDATE jobs SET description=NULL WHERE hash LIKE ?", (f"%{praefix}_{i:05d}",))
            db.connect().commit()


TEXTE = [
    None,                                   # NULL
    "",                                     # leer
    "   \n\t  ",                            # nur Leerraum
    "kurz",
    "  Mit Leerraum drumherum \n\t",
    "Ü" * 49, "ü" * 50, "x" * 199, "x" * 200, "x" * 201,
    "Ein Satz mit Umlauten und ß. " * 20,
    "Mit Emoji 😀 mitten im Text. " * 12,
    "Lang. " * 2000,
]


def _texte_aussortieren(db):
    _aussortiert(db, [(f"Fachkraft {i}", "Beispielwerk AG", t) for i, t in enumerate(TEXTE)])


# ══ Das schlanke Lesen ═══════════════════════════════════════════════════

def test_schlank_liefert_dieselbe_menge_in_derselben_reihenfolge(umgebung):
    db, _ = umgebung
    _texte_aussortieren(db)
    voll, schlank = db.get_dismissed_jobs(), db.get_dismissed_jobs_schlank()
    assert len(voll) == len(TEXTE) and [j["hash"] for j in voll] == [j["hash"] for j in schlank]


def test_schlank_laesst_die_langen_texte_weg_und_nennt_die_laenge(umgebung):
    db, _ = umgebung
    _texte_aussortieren(db)
    for v, s in zip(db.get_dismissed_jobs(), db.get_dismissed_jobs_schlank()):
        for lang in ("description", "research_notes", "analyse_begruendung"):
            assert lang not in s, lang
        if v["description"] is None:
            assert s["description_laenge"] is None, v["title"]
        else:
            # wie len(text.strip()) in Python, auch bei Tabulator, Zeilenumbruch, Umlauten, Emoji
            assert s["description_laenge"] == len(str(v["description"]).strip()), v["title"]


def test_schlank_behaelt_alles_was_die_pruefung_liest(umgebung):
    db, _ = umgebung
    _texte_aussortieren(db)
    for v, s in zip(db.get_dismissed_jobs(), db.get_dismissed_jobs_schlank()):
        for feld in ("hash", "title", "company", "dismiss_reason", "dismiss_reasons",
                     "salary_estimated", "score", "is_active", "found_at", "updated_at", "hash_typed"):
            assert s.get(feld) == v.get(feld), (feld, v["title"])


def test_schlank_gilt_je_profil(umgebung):
    db, _ = umgebung
    _texte_aussortieren(db)
    erstes = db.get_active_profile_id()
    db.switch_profile(db.create_profile("Zweites"))
    assert db.get_dismissed_jobs_schlank() == [] == db.get_dismissed_jobs()
    db.switch_profile(erstes)
    assert len(db.get_dismissed_jobs_schlank()) == len(TEXTE)


def test_das_schlanke_lesen_traegt_keine_anzeigentexte(umgebung):
    """Der Umfang der Zeilen, nicht die Uhr: bei 8 KB Text je Stelle bleibt vom schlanken Lesen fast nichts."""
    db, _ = umgebung
    text = ("Anzeigentext mit vielen Woertern. " * 300)[:8000]
    _aussortiert(db, [(f"Stelle {i}", f"Betrieb {i % 20} GmbH", text) for i in range(300)])

    def umfang(zeilen):
        return sum(len(str(wert)) for z in zeilen for wert in z.values() if wert is not None)
    assert umfang(db.get_dismissed_jobs_schlank()) < umfang(db.get_dismissed_jobs()) * 0.05


# ══ Dasselbe Ergebnis der Prüfung ════════════════════════════════════════

def test_die_guete_eines_urteils_ist_mit_und_ohne_text_dieselbe(umgebung):
    db, _ = umgebung
    from bewerbungs_assistent.services.wiedergaenger import grund_guete
    _texte_aussortieren(db)
    gesehen = set()
    for v, s in zip(db.get_dismissed_jobs(), db.get_dismissed_jobs_schlank()):
        assert grund_guete(s) == grund_guete(v), v["title"]
        gesehen.add(grund_guete(v)[0])
    # das Rohmaterial deckt alle drei Guetestufen ab, sonst wuerde der Vergleich nichts pruefen
    assert gesehen >= {"ohne_grundlage", "schwach", "belegt"}, gesehen


def _wiederg_bestand(db):
    _aussortiert(db, [
        ("PLM Owner", "Beispielwerk AG", "Aufgaben und Profil. " * 40),
        ("PLM Manager", "Beispielwerk AG", "Aufgaben und Profil. " * 40),
        ("PLM Lead", "Beispielwerk AG", "Kurzer Rumpf der Anzeige " * 5),
        ("Buchhalter", "Beispielwerk AG", "Rechnungswesen. " * 30),
        ("PLM Owner", "Andere Firma GmbH", "Aufgaben und Profil. " * 40),
    ])


def test_das_wiedergaenger_muster_ist_auf_jedem_weg_dasselbe(umgebung):
    db, _ = umgebung
    from bewerbungs_assistent.services.wiedergaenger import (
        AussortiertePool, find_wiedergaenger_pattern)
    _wiederg_bestand(db)
    voll = find_wiedergaenger_pattern(db, "Beispielwerk AG", "PLM Architect", dismissed=db.get_dismissed_jobs())
    assert voll, "das Rohmaterial muss ein Muster ergeben, sonst prueft der Vergleich nichts"
    wege = {
        "schlank als Liste": find_wiedergaenger_pattern(
            db, "Beispielwerk AG", "PLM Architect", dismissed=db.get_dismissed_jobs_schlank()),
        "voll als Pool": find_wiedergaenger_pattern(
            db, "Beispielwerk AG", "PLM Architect", dismissed=AussortiertePool(db.get_dismissed_jobs())),
        "schlank als Pool": find_wiedergaenger_pattern(
            db, "Beispielwerk AG", "PLM Architect", dismissed=AussortiertePool(db.get_dismissed_jobs_schlank())),
        "ohne Pool (laedt selbst)": find_wiedergaenger_pattern(db, "Beispielwerk AG", "PLM Architect"),
    }
    for name, erg in wege.items():
        assert erg == voll, name


def test_das_wiedergaenger_muster_kennt_firmen_in_jeder_schreibweise_des_pools(umgebung):
    """Der Index arbeitet mit der normalisierten Firma: AG, GmbH, Gross- und Kleinschreibung fallen zusammen."""
    db, _ = umgebung
    from bewerbungs_assistent.services.wiedergaenger import (
        AussortiertePool, find_wiedergaenger_pattern)
    _aussortiert(db, [
        ("PLM Owner", "Beispielwerk AG", "Aufgaben und Profil. " * 40),
        ("PLM Manager", "BEISPIELWERK GmbH", "Aufgaben und Profil. " * 40),
        ("PLM Lead", "beispielwerk", "Aufgaben und Profil. " * 40),
    ])
    for schreibweise in ("Beispielwerk AG", "beispielwerk gmbh", "BEISPIELWERK"):
        mit_pool = find_wiedergaenger_pattern(db, schreibweise, "PLM Architect",
                                              dismissed=AussortiertePool(db.get_dismissed_jobs()))
        ohne = find_wiedergaenger_pattern(db, schreibweise, "PLM Architect", dismissed=db.get_dismissed_jobs())
        assert mit_pool == ohne and mit_pool and mit_pool["anzahl"] == 3, (schreibweise, mit_pool)


def test_der_pool_haelt_die_reihenfolge_je_firma(umgebung):
    db, _ = umgebung
    from bewerbungs_assistent.services.wiedergaenger import AussortiertePool
    _aussortiert(db, [(f"Stelle {i}", "Beispielwerk AG" if i % 2 else "Andere GmbH", "x" * 300) for i in range(10)])
    pool = AussortiertePool(db.get_dismissed_jobs())
    assert isinstance(pool, list) and len(pool) == 10
    alle = [j["hash"] for j in pool]
    assert [j["hash"] for j in pool.der_firma("beispielwerk")] == [h for h, j in zip(alle, pool) if "Beispielwerk" in j["company"]]
    assert pool.der_firma("gibt-es-nicht") == []


def test_die_firmen_historie_ist_dieselbe(umgebung):
    db, _ = umgebung
    from bewerbungs_assistent.services.wiedergaenger import aussortierte_laden, firmen_historie
    _wiederg_bestand(db)

    class Voll:           # eine Datenbank, die nur das volle Lesen kennt
        def get_dismissed_jobs(self):
            return db.get_dismissed_jobs()
    erwartet = firmen_historie(Voll(), "Beispielwerk AG")
    assert erwartet and erwartet["aussortiert_anzahl"] == 4
    assert firmen_historie(db, "Beispielwerk AG") == erwartet
    assert aussortierte_laden(db) and "description" not in aussortierte_laden(db)[0]


# ══ Wer das schlanke Lesen benutzt ═══════════════════════════════════════

def test_ein_double_ohne_schlankes_lesen_faellt_auf_das_volle_zurueck():
    from bewerbungs_assistent.services.wiedergaenger import aussortierte_laden

    class Alt:
        def get_dismissed_jobs(self):
            return [{"hash": "a"}]
    assert aussortierte_laden(Alt()) == [{"hash": "a"}]


def test_ein_schlankes_lesen_das_keine_liste_liefert_gilt_nicht():
    from unittest.mock import MagicMock
    from bewerbungs_assistent.services.wiedergaenger import aussortierte_laden
    db = MagicMock()
    db.get_dismissed_jobs.return_value = [{"hash": "voll"}]
    assert aussortierte_laden(db) == [{"hash": "voll"}]


def test_die_stellenliste_laedt_die_aussortierten_ohne_texte(umgebung, monkeypatch):
    db, mcp = umgebung
    _wiederg_bestand(db)
    db.save_jobs([{"hash": "aktiv_1", "title": "PLM Architect", "company": "Beispielwerk AG",
                   "url": "https://example.com/a", "source": "bundesagentur",
                   "description": "Eine aktive Stelle. " * 30, "score": 30, "found_at": "2026-10-01T00:00:00"}])
    _call(mcp, "stellen_anzeigen", {})        # waermt das Neigungsprofil an, das EINMAL die Texte liest
    voll, schlank = {"n": 0}, {"n": 0}
    echt_voll, echt_schlank = type(db).get_dismissed_jobs, type(db).get_dismissed_jobs_schlank

    def zaehlt_voll(self):
        voll["n"] += 1
        return echt_voll(self)

    def zaehlt_schlank(self):
        schlank["n"] += 1
        return echt_schlank(self)
    monkeypatch.setattr(type(db), "get_dismissed_jobs", zaehlt_voll)
    monkeypatch.setattr(type(db), "get_dismissed_jobs_schlank", zaehlt_schlank)
    erg = _call(mcp, "stellen_anzeigen", {})
    assert erg["stellen"], erg
    assert schlank["n"] == 1, "die Pruefung laedt den Pool genau einmal"
    assert voll["n"] == 0, "und zwar ohne Anzeigentexte"


def test_wiedergaenger_py_liest_nirgends_mehr_direkt_die_vollen_aussortierten():
    quelle = (ROOT / "src" / "bewerbungs_assistent" / "services" / "wiedergaenger.py").read_text(encoding="utf-8")
    aufrufe = [z for z in quelle.splitlines() if "get_dismissed_jobs()" in z and not z.lstrip().startswith("#")]
    # genau einer: der Rueckfall in `aussortierte_laden`
    assert len(aufrufe) == 1 and "get_dismissed_jobs())" in aufrufe[0], aufrufe


# ══ Gemessen ═════════════════════════════════════════════════════════════

def _bestand_gross(db, aktiv, aussortiert):
    text = ("Anzeigentext mit vielen Woertern. " * 300)[:8000]
    db.save_jobs([{
        "hash": f"a_{i:05d}", "title": f"Sachbearbeiter {i}", "company": f"Betrieb {i} GmbH",
        "url": f"https://example.com/a/{i}", "source": "bundesagentur",
        "description": "Beschreibung der Stelle. " * 30, "score": 20 + (i % 40),
        "found_at": "2026-10-01T00:00:00"} for i in range(aktiv)])
    db.save_jobs([{
        "hash": f"d_{i:05d}", "title": f"Altstelle {i}", "company": f"Betrieb {i % 300} GmbH",
        "url": f"https://example.com/d/{i}", "source": "bundesagentur", "description": text,
        "score": 20, "found_at": "2026-09-01T00:00:00"} for i in range(aussortiert)])
    # in einem Zug aussortiert (die Einzelaufrufe von `dismiss_job` brauchen fuer 2.000 Stellen halbe Minuten)
    conn = db.connect()
    conn.execute("UPDATE jobs SET is_active=0, dismiss_reason='falsches_fachgebiet' WHERE title LIKE 'Altstelle %'")
    conn.commit()


def test_jede_aussortierte_firma_wird_einmal_normalisiert_nicht_je_stelle_der_liste(umgebung, monkeypatch):
    """Die Ursache aus dem Profil: 1.200 x 2.000 Aufrufe von `normalize_company`. Hier 300 x 500 = 150.000
    in der alten Fassung; jetzt hoechstens eine Normalisierung je Aussortierter und je Stelle der Liste."""
    db, mcp = umgebung
    _bestand_gross(db, 300, 500)
    _call(mcp, "stellen_anzeigen", {})                     # Neigungsprofil anwaermen
    from bewerbungs_assistent.services import wiedergaenger
    echt = wiedergaenger.normalize_company
    zaehler = {"n": 0}

    def zaehlend(*a, **k):
        zaehler["n"] += 1
        return echt(*a, **k)
    monkeypatch.setattr(wiedergaenger, "normalize_company", zaehlend)
    # Wie oft schaut die Pruefung auf die Firma einer Aussortierten? Mit dem Index nur auf die
    # Zeilen der eigenen Firma (hier im Mittel 2 von 500), ohne ihn auf jede (300 x 500 = 150.000).
    echt_zeile = wiedergaenger._firma_norm
    zeilen = {"n": 0}

    def zeile_zaehlend(j):
        zeilen["n"] += 1
        return echt_zeile(j)
    monkeypatch.setattr(wiedergaenger, "_firma_norm", zeile_zaehlend)
    erg = _call(mcp, "stellen_anzeigen", {"pro_seite": 20})
    assert erg["anzahl_gesamt"] >= 300
    assert zaehler["n"] <= 3 * (300 + 500), f"{zaehler['n']} Normalisierungen — das Wiederholen ist zurueck"
    assert zeilen["n"] <= 5 * (300 + 500), f"{zeilen['n']} Blicke auf aussortierte Firmen — der Index fehlt"


def test_eine_einfache_liste_wird_je_zeile_nur_einmal_normalisiert(umgebung, monkeypatch):
    """Auch ohne Pool (ein Aufrufer, der eine Liste uebergibt) merkt sich die Zeile ihre normalisierte Firma."""
    db, _ = umgebung
    from bewerbungs_assistent.services import wiedergaenger
    _bestand_gross(db, 10, 200)
    liste = db.get_dismissed_jobs_schlank()
    assert type(liste) is list
    echt = wiedergaenger.normalize_company
    zaehler = {"n": 0}

    def zaehlend(*a, **k):
        zaehler["n"] += 1
        return echt(*a, **k)
    monkeypatch.setattr(wiedergaenger, "normalize_company", zaehlend)
    for i in range(100):
        wiedergaenger.find_wiedergaenger_pattern(db, f"Betrieb {i} GmbH", "Altstelle", dismissed=liste)
    # 100 Stellen x 200 Aussortierte waeren 20.000 Aufrufe; mit dem Gemerkten: je Zeile einmal, je Stelle einmal.
    assert zaehler["n"] <= 200 + 100 + 20, zaehler["n"]


def test_die_stellenliste_bleibt_mit_vielen_aussortierten_schnell(umgebung):
    """1.200 aktive, 2.000 aussortierte zu je 8 KB. Gemessen 3,2 s vorher, 0,37 s nachher; der Grenzwert
    liegt weit darueber (langsame Maschinen), aber weit unter dem alten Wert."""
    db, mcp = umgebung
    _bestand_gross(db, 1200, 2000)
    _call(mcp, "stellen_anzeigen", {})                     # Neigungsprofil anwaermen
    t0 = time.perf_counter()
    erg = _call(mcp, "stellen_anzeigen", {})
    dauer = time.perf_counter() - t0
    assert erg["anzahl_gesamt"] >= 1200
    assert dauer < 1.5, f"{dauer:.2f} s fuer die Stellenliste"
