"""Tests fuer v1.7.68 — #968: kein Pflichttreffer, unsichtbar oder unten?

Das MUSS-Tor (#940) setzt den Score auf 0, wenn kein einziger
Pflichtbegriff trifft; die Schwelle im Suchlauf verwirft die Stelle
danach. Das Issue verlangt die Umkehr — weit unten statt nirgends —
und zwar umschaltbar.

**Die Falle, an der ein naiver Fix scheitert**, steht als eigener Test
da: der Fachscore ist zugleich das Tor UND die Bezugsgroesse des
Rahmen-Deckels aus #942. Ohne Pflichttreffer ist der Deckel null, also
schneidet er den kompletten positiven Rahmen weg — wer nur das
`return 0` entfernt, aendert gar nichts.
"""
import sys
from pathlib import Path

import pytest


def _repo() -> Path:
    """Absoluter Repo-Pfad — der Test muss auch aus einem fremden
    Arbeitsverzeichnis laufen (DoD 8c)."""
    return Path(__file__).resolve().parents[1]


sys.path.insert(0, str(_repo() / "src"))

from bewerbungs_assistent.job_scraper import calculate_score, fit_analyse  # noqa: E402
from bewerbungs_assistent.services import muss_tor  # noqa: E402


# Eine Anzeige, die fachlich NICHTS mit den Pflichtbegriffen zu tun hat,
# aber im Rahmen (Ort, Remote, Gehalt) gut dasteht — genau der Fall, den
# #942 im Blick hatte.
FREMDE_ANZEIGE = {
    "title": "Konditormeister (m/w/d)",
    "description": (
        "Wir suchen einen Konditormeister fuer unsere Backstube. "
        "Sie fertigen Torten und Pralinen, fuehren ein Team von vier "
        "Personen und verantworten den Wareneinsatz. Ausbildung im "
        "Konditorhandwerk und mehrjaehrige Berufserfahrung setzen wir "
        "voraus. Wir bieten geregelte Arbeitszeiten." * 3),
    "remote_level": "remote",
    "distance_km": 5,
    "employment_type": "festanstellung",
}

PASSENDE_ANZEIGE = {
    "title": "Pflegefachkraft (m/w/d)",
    "description": (
        "Fuer unsere Station suchen wir eine Pflegefachkraft. Sie "
        "uebernehmen die Grund- und Behandlungspflege, dokumentieren "
        "und begleiten Visiten. Eine abgeschlossene Ausbildung in der "
        "Pflege ist Voraussetzung." * 3),
    "remote_level": "unbekannt",
    "distance_km": 400,
    "employment_type": "festanstellung",
}


def _kriterien(modus=None, **extra):
    krit = {
        "keywords_muss": ["Pflegefachkraft"],
        "keywords_plus": ["Team", "Dokumentation"],
        "min_score_schwelle": 15,
    }
    if modus is not None:
        krit["_muss_tor_modus"] = modus
    krit.update(extra)
    return krit


# ---------------------------------------------------------------- Vorgabe


def test_968_ohne_jede_auskunft_bleibt_es_beim_bisherigen_verhalten():
    """Kein Profil, keine Begriffsarten — also keine Aenderung.

    Die Vorgabe ist seit v1.7.69 `automatisch` und leitet sich aus den
    Pflichtbegriffen ab (siehe unten). Ist darueber nichts bekannt,
    bleibt es bei `hart`, also beim Verhalten vor dieser Version — eine
    fehlende Auskunft darf nie eine Voreinstellung setzen (#989).
    """
    class _DB:
        def get_profile_setting(self, key, default=None):
            return default

    assert muss_tor.modus(_DB()) == muss_tor.HART


def test_968_hart_verwirft_wie_bisher():
    """AK 2: die harte Variante bleibt verfuegbar und unveraendert."""
    job = dict(FREMDE_ANZEIGE)
    assert calculate_score(job, _kriterien(muss_tor.HART)) == 0
    assert job.get("_ko_kein_muss") is True
    assert not job.get("_ohne_muss_treffer")


def test_968_ohne_einstellung_gilt_die_harte_variante():
    """Kriterien ohne die Angabe rechnen wie vor dieser Version.

    Wichtig fuer alle Aufrufer, die `fuer_scoring` nicht benutzen — sie
    duerfen ihr Verhalten nicht still aendern.
    """
    job = dict(FREMDE_ANZEIGE)
    assert calculate_score(job, _kriterien()) == 0


# ------------------------------------------------------------- Gewichtung


def test_968_gewichtet_laesst_die_stelle_sichtbar():
    """AK 1: kein Pflichttreffer heisst weit unten, nicht unsichtbar."""
    job = dict(FREMDE_ANZEIGE)
    punkte = calculate_score(job, _kriterien(muss_tor.GEWICHTET))
    assert punkte > 0, "Die Stelle ist weiterhin unsichtbar."
    assert job.get("_ohne_muss_treffer") is True
    assert not job.get("_ko_kein_muss")


def test_968_der_rahmen_deckel_haette_den_fix_wirkungslos_gemacht():
    """Die Falle, an der ein naiver Fix scheitert.

    `deckel = faktor * fachscore`, und ohne Pflichttreffer ist der
    Fachscore 0. Ein blosses Weglassen des `return 0` haette den
    positiven Rahmen vollstaendig weggeschnitten und die Stelle wieder
    bei 0 abgelegt. Der Test haelt fest, dass die Gewichtung an dieser
    Stelle einen EIGENEN Rechenweg nimmt.
    """
    job = dict(FREMDE_ANZEIGE)
    krit = _kriterien(muss_tor.GEWICHTET)
    punkte = calculate_score(job, krit)
    # Der Rahmen dieser Anzeige ist deutlich positiv (remote + nah) —
    # unter dem Deckel des Fachscores 0 waere davon nichts uebrig.
    assert job["_rahmen_ungedeckelt"] > 0
    assert punkte == job["_rahmenscore"] > 0
    # ... und der Fachscore bleibt ehrlich bei 0: es gibt keinen.
    assert job["_fachscore"] == 0


def test_968_der_ersatz_score_ist_hart_gedeckelt():
    """Ein Bonus ersetzt keine fachliche Passung (#942).

    Ohne Deckel waere die Hamburger Senior-Remote-Stelle aus #942
    zurueck: zweistelliger Score ohne jeden Fachbezug.
    """
    job = dict(FREMDE_ANZEIGE, salary_min=200000)
    punkte = calculate_score(
        job, _kriterien(muss_tor.GEWICHTET, min_gehalt=60000))
    assert punkte <= muss_tor.obergrenze(2)
    # Ein sehr hohes MUSS-Gewicht laeuft in die absolute Grenze, ein
    # fehlendes ebenfalls — nie in einen unbegrenzten Wert.
    assert muss_tor.ersatz_score(999, 0, 2) == 1.0
    assert muss_tor.ersatz_score(999, 0, 100) == muss_tor.MAX_OHNE_MUSS
    assert muss_tor.ersatz_score(999, 0, 0) == muss_tor.MAX_OHNE_MUSS


def test_968_ein_malus_zieht_die_stelle_nach_unten():
    """Nach unten ist der Rahmen NICHT gedeckelt — auch hier nicht.

    Der Deckel begrenzt, was eine Stelle ohne Fachbezug hoechstens
    tragen darf; er ist keine Untergrenze. Ein Minus-Keyword muss sie
    weiter druecken koennen, bis auf 0.
    """
    # Auf Funktionsebene: der Deckel greift nur nach oben.
    assert muss_tor.ersatz_score(10, 0, 2) == 1.0
    assert muss_tor.ersatz_score(10, 9.5, 2) == 0.5
    assert muss_tor.ersatz_score(10, 20, 2) == 0.0

    # Und an der echten Anzeige: genug Minus-Begriffe druecken sie auf 0.
    ohne_malus = calculate_score(
        dict(FREMDE_ANZEIGE), _kriterien(muss_tor.GEWICHTET))
    mit_malus = calculate_score(
        dict(FREMDE_ANZEIGE),
        _kriterien(muss_tor.GEWICHTET,
                   keywords_minus=["Konditormeister", "Backstube", "Torten",
                                   "Pralinen", "Wareneinsatz",
                                   "Konditorhandwerk", "Berufserfahrung",
                                   "Arbeitszeiten"]))
    assert ohne_malus > 0
    assert mit_malus == 0


def test_968_bei_gleichem_rahmen_gewinnt_der_pflichttreffer():
    """AK 4, erste Haelfte: dieselben Umstaende, ein Fachbezug mehr."""
    krit = _kriterien(muss_tor.GEWICHTET)
    rahmen = {"remote_level": "remote", "distance_km": 5,
              "employment_type": "festanstellung"}
    p_fremd = calculate_score(dict(FREMDE_ANZEIGE, **rahmen), krit)
    p_passend = calculate_score(dict(PASSENDE_ANZEIGE, **rahmen), krit)
    assert p_passend > p_fremd, f"{p_passend} <= {p_fremd}"


def test_968_die_rangfolge_haelt_auch_wenn_der_score_es_nicht_tut():
    """AK 4, zweite Haelfte — und die eigentliche Einsicht.

    Eine Stelle MIT Pflichttreffer darf abstuerzen: 400 km Entfernung
    ziehen sie auf 0, und das ist die Asymmetrie aus #942 (ein Malus
    entwertet vorhandene Eignung). Damit steht sie nach PUNKTEN unter
    einer fremden Anzeige, die remote und 5 km entfernt ist.

    Genau deshalb steht die Garantie in der SORTIERUNG und nicht im
    Score: eine Stelle, ueber deren Fach nichts bekannt ist, darf nie
    ueber einer stehen, die einen Pflichtbegriff trifft — auch dann
    nicht, wenn sie mehr Punkte hat.
    """
    krit = _kriterien(muss_tor.GEWICHTET)
    fremd, passend = dict(FREMDE_ANZEIGE), dict(PASSENDE_ANZEIGE)
    p_fremd = calculate_score(fremd, krit)
    p_passend = calculate_score(passend, krit)
    assert p_fremd > p_passend, "Der Anlass dieses Tests ist entfallen."

    fremd["fachscore"], passend["fachscore"] = (
        fremd["_fachscore"], passend["_fachscore"])
    fremd["score"], passend["score"] = p_fremd, p_passend
    geordnet = sorted(
        [fremd, passend],
        key=lambda j: (muss_tor.sortierschluessel(j, krit), -j["score"]))
    assert geordnet[0] is passend, "Der Pflichttreffer steht nicht oben."


# ------------------------------------------------------ beide Rechenwege


def test_968_fit_analyse_traegt_dieselbe_betriebsart():
    """AK 5: der Guard aus #963 in neuer Gestalt.

    Stuende die Betriebsart nur in `calculate_score`, haette dieselbe
    Stelle je nach Werkzeug einen anderen Wert — das ist #963 und
    #917 Defekt D.
    """
    krit = _kriterien(muss_tor.GEWICHTET)
    job = dict(FREMDE_ANZEIGE)
    punkte = calculate_score(job, krit)
    analyse = fit_analyse(dict(FREMDE_ANZEIGE), krit)
    assert analyse["total_score"] == punkte
    assert analyse["ohne_pflichttreffer"] is True
    assert analyse["fachscore"] == 0


def test_968_fit_analyse_hart_bleibt_bei_null():
    krit = _kriterien(muss_tor.HART)
    analyse = fit_analyse(dict(FREMDE_ANZEIGE), krit)
    assert analyse["total_score"] == 0
    assert analyse["ohne_pflichttreffer"] is True


def test_968_die_empfehlung_folgt_der_zahl():
    """`gewichtet` macht die Stelle sichtbar, nicht empfehlenswert."""
    for modus in (muss_tor.HART, muss_tor.GEWICHTET):
        analyse = fit_analyse(dict(FREMDE_ANZEIGE), _kriterien(modus))
        assert analyse["empfehlung"]["kategorie"] == "NICHT_EMPFOHLEN"


# ----------------------------------------------------------- Einstellung


class _Speicher:
    def __init__(self, wert=None):
        self.werte = {} if wert is None else {muss_tor.EINSTELLUNG: wert}

    def get_profile_setting(self, key, default=None):
        return self.werte.get(key, default)

    def set_profile_setting(self, key, value):
        self.werte[key] = value


def test_968_die_betriebsart_laesst_sich_umschalten():
    db = _Speicher()
    assert muss_tor.modus(db) == muss_tor.HART
    ergebnis = muss_tor.modus_setzen(db, muss_tor.GEWICHTET)
    assert ergebnis["status"] == "gesetzt"
    assert muss_tor.modus(db) == muss_tor.GEWICHTET


def test_968_unsinn_wird_abgewiesen_statt_still_gekippt():
    """Ein Tippfehler, der als Erfolg gemeldet wird, ist #980/#988."""
    db = _Speicher()
    ergebnis = muss_tor.modus_setzen(db, "weich")
    assert "fehler" in ergebnis
    assert muss_tor.modus(db) == muss_tor.HART
    assert db.werte == {}, "Der Unsinn wurde trotzdem gespeichert."


def test_968_ein_unbekannter_gespeicherter_wert_faellt_auf_die_vorgabe():
    """Altbestand oder von Hand verstellt — nie ein Absturz."""
    assert muss_tor.modus(_Speicher("irgendwas")) == muss_tor.HART


def test_968_die_einstellung_kommt_ueber_das_nadeloehr():
    """`fuer_scoring` traegt sie — nicht `calculate_score` selbst.

    Wuerde die Score-Berechnung die Datenbank selbst fragen, rechnete
    der Suchlauf wieder anders als die Neuberechnung (#987).
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "services"
              / "scoring_kriterien.py").read_text(encoding="utf-8")
    assert "_muss_tor_modus" in quelle


# ------------------------------------------------------------- Die Liste


def test_968_die_liste_erkennt_stellen_ohne_pflichttreffer():
    """AK 3 — gelesen wird der GESPEICHERTE Fachscore.

    Den Anzeigentext in der Liste erneut gegen die Begriffe zu halten
    waere ein zweiter Rechenweg fuer dieselbe Frage (#963).
    """
    krit = {"keywords_muss": ["Pflegefachkraft"]}
    assert muss_tor.ohne_pflichttreffer({"fachscore": 0}, krit) is True
    assert muss_tor.ohne_pflichttreffer({"fachscore": 7.5}, krit) is False


def test_968_ohne_pflichtbegriffe_gibt_es_nichts_zu_verfehlen():
    """Kaltstart (#967): keine MUSS-Liste, also keine Marke."""
    assert muss_tor.ohne_pflichttreffer({"fachscore": 0}, {}) is False
    assert muss_tor.marke({"fachscore": 0}, {}) is None


def test_968_altbestand_ohne_teilscores_wird_nicht_geraten():
    """Eine Luecke gehoert benannt, nicht gefuellt (#989).

    `fachscore = None` heisst "nicht bekannt" und NICHT "kein
    Treffer" — sonst traegt der halbe Altbestand eine erfundene Marke.
    """
    krit = {"keywords_muss": ["Pflegefachkraft"]}
    assert muss_tor.ohne_pflichttreffer({"fachscore": None}, krit) is False
    assert muss_tor.ohne_pflichttreffer({}, krit) is False


def test_968_die_marke_erklaert_die_rangfolge():
    krit = {"keywords_muss": ["Pflegefachkraft"]}
    marke = muss_tor.marke({"fachscore": 0}, krit)
    assert marke and marke["ohne_pflichttreffer"] is True
    assert "Pflichtbegriff" in marke["text"]


@pytest.mark.parametrize("datei,anker", [
    ("src/bewerbungs_assistent/tools/jobs.py", "_tor_rang"),
    ("src/bewerbungs_assistent/dashboard.py", 'job["muss_tor"] = tor_marke'),
    ("frontend/src/pages/JobsPage.jsx", "a.muss_tor ? 1 : 0"),
])
def test_968_beide_listen_tragen_den_befund(datei, anker):
    """Ein Befund, den nur ein Werkzeug kennt, ist kein Befund (#989).

    Die MCP-Liste, die REST-Liste und die Seite, die der Mensch
    ansieht, muessen dieselbe Rangfolge zeigen — sonst steht dieselbe
    Stelle je nach Weg an einer anderen Position.
    """
    assert anker in (_repo() / datei).read_text(encoding="utf-8")


def test_968_das_frontend_spiegelt_die_regel_nicht():
    """Die Entscheidung trifft der Server, das Frontend liest sie nur.

    Eine zweite Fassung der Regel im JavaScript waere der Fehler aus
    #765 — zwei Orte, die auseinanderlaufen, ohne dass es auffaellt.
    """
    quelle = (_repo() / "frontend" / "src" / "pages"
              / "JobsPage.jsx").read_text(encoding="utf-8")
    assert "fachscore" not in quelle.split("a.muss_tor ? 1 : 0")[1][:400]


# --------------------------------------------------------- Der Suchlauf


def test_968_der_trichter_benennt_beide_neuen_stufen():
    """Ein Lauf mit 50 behaltenen und 262 uebergangenen Stellen darf
    nicht aussehen wie ein Lauf ohne jede Filterung (#813)."""
    from bewerbungs_assistent.job_scraper import _STUFEN_TEXT
    assert "ohne_pflichttreffer_behalten" in _STUFEN_TEXT
    assert "ohne_pflichttreffer_ueber_grenze" in _STUFEN_TEXT


def test_968_die_behalten_grenze_ist_benannt_und_endlich():
    """Eine stille Flut waere schlimmer als eine benannte Grenze.

    Im dokumentierten Lauf aus #813 waren es 312 Stellen ohne
    Pflichttreffer in EINEM Durchgang.
    """
    assert 0 < muss_tor.MAX_JE_LAUF <= 200


# ------------------------------------- Die Vorgabe wird ABGELEITET (v1.7.69)
#
# Der Einwand, der diesen Abschnitt ausgeloest hat: die erste Fassung
# hatte `hart` fest als Vorgabe, begruendet mit einer Messung an EINEM
# Bestand. Fuer ein Technik-Profil stimmt das; fuer die Pflegekraft aus
# dem Issue ist es falsch. Eine Voreinstellung, die an einem fremden
# Lebenslauf kalibriert wurde, ist fuer alle anderen geraten.
#
# Diese Tests pruefen deshalb bewusst BEIDE Profile — und das
# Technik-Profil ist NICHT das, an dem gemessen wurde: es steht hier
# stellvertretend fuer jeden, dessen Pflichtbegriffe Techniken nennen.


def test_968_berufsprofil_bekommt_gewichtet():
    """Eine Pflegekraft: `Pflegefachkraft` ist ein Beruf, also gewichtet."""
    art, warum = muss_tor.abgeleitet({"Pflegefachkraft": "beruf"})
    assert art == muss_tor.GEWICHTET
    assert "Beruf" in warum


def test_968_technikprofil_bekommt_hart():
    """Ein Entwickler: `Python`/`Kubernetes` sind Techniken, also hart."""
    art, warum = muss_tor.abgeleitet(
        {"Python": "technik", "Kubernetes": "technik"})
    assert art == muss_tor.HART
    assert "Techniken" in warum


def test_968_ein_einziger_berufsbegriff_genuegt():
    """Gemischte Liste — der umbenennbare Begriff ist der gefaehrdete.

    Das Tor oeffnet, sobald IRGENDEIN Pflichtbegriff trifft. Wer
    "Erzieherin" und "Dokumentation" fuehrt, verliert bei `hart` genau
    dann alles, wenn die Anzeige den Beruf anders nennt.
    """
    art, _ = muss_tor.abgeleitet(
        {"Erzieherin": "beruf", "Dokumentation": "technik"})
    assert art == muss_tor.GEWICHTET


def test_968_unbekannt_ist_nicht_technik():
    """Ein Netzausfall darf keine Voreinstellung setzen (#989).

    `unbekannt` faellt auf `hart` zurueck — also auf das bisherige
    Verhalten — und NICHT, weil es als Technik gilt, sondern weil ohne
    Auskunft nichts geaendert wird. Der Begruendungstext muss das
    sagen, sonst sieht es aus wie eine Entscheidung.
    """
    art, warum = muss_tor.abgeleitet({"Irgendwas": "unbekannt"})
    assert art == muss_tor.HART
    assert "noch nicht bestimmt" in warum
    # Und ohne jede Angabe genauso.
    assert muss_tor.abgeleitet({})[0] == muss_tor.HART
    assert muss_tor.abgeleitet(None)[0] == muss_tor.HART


def test_968_die_ausdrueckliche_einstellung_schlaegt_die_ableitung():
    """Wer es selbst setzt, bekommt es — in beide Richtungen."""
    berufs_krit = {"_muss_begriffsart": {"Pflegefachkraft": "beruf"}}
    technik_krit = {"_muss_begriffsart": {"Python": "technik"}}

    # ohne Einstellung: die Ableitung gilt
    assert muss_tor.modus(_Speicher(), berufs_krit) == muss_tor.GEWICHTET
    assert muss_tor.modus(_Speicher(), technik_krit) == muss_tor.HART

    # ausdruecklich gesetzt: die Ableitung wird ueberstimmt
    assert muss_tor.modus(
        _Speicher(muss_tor.HART), berufs_krit) == muss_tor.HART
    assert muss_tor.modus(
        _Speicher(muss_tor.GEWICHTET), technik_krit) == muss_tor.GEWICHTET

    # und `automatisch` gibt die Ableitung zurueck
    assert muss_tor.modus(
        _Speicher(muss_tor.AUTOMATISCH), berufs_krit) == muss_tor.GEWICHTET


def test_968_die_ableitung_nennt_ihren_grund():
    """Eine Vorgabe, die sich selbst setzt, muss sagen koennen warum.

    Sonst ist sie von einer stillen Verhaltensaenderung nicht zu
    unterscheiden — und genau das war der Fehler in #987 und #988.
    """
    for arten in ({"Pflegefachkraft": "beruf"}, {"Python": "technik"}, {}):
        _, warum = muss_tor.abgeleitet(arten)
        assert warum and len(warum) > 30


def test_968_die_begriffsart_kommt_aus_der_gemessenen_schwelle():
    """Kein zweites Kriterium — dieselbe Schwelle wie bei #969/#987.

    Ein Beruf zieht die Berufs-Facette an sich, eine Technologie
    streut. Die Schwelle wurde am 07.09.2026 gemessen (Berufe 18-39 %,
    Techniken 10-13 %); eine zweite, frei geratene Regel daneben waere
    genau die Bauform, die dieses Projekt zehnmal gekostet hat.
    """
    from bewerbungs_assistent.services import berufsbezeichnungen as bb

    def _antwort(counts):
        return {"facetten": {"beruf": {"counts": counts}}}

    # Ein Beruf konzentriert die Facette auf sich ...
    BERUFS_FACETTE = {"Pflegefachkraft": 30, **{f"B{i}": 10 for i in range(7)}}
    # ... eine Technik streut ueber viele Berufe gleichmaessig.
    TECHNIK_FACETTE = {f"B{i}": 10 for i in range(10)}

    class _Client:
        def __init__(self, daten):
            self.daten = daten

        def get(self, *a, **k):
            class _R:
                status_code = 200

                def json(_self):
                    return self.daten
            return _R()

    bb.cache_leeren()
    # 30 von 100 = 30 % Spitze — ueber MIN_SPITZENANTEIL, also ein Beruf.
    assert bb.begriffsart(
        "Testbegriff-A", client=_Client(_antwort(BERUFS_FACETTE))) == bb.BERUF
    bb.cache_leeren()
    # 10 von 100 = 10 % Spitze — darunter, also eine Technik.
    assert bb.begriffsart(
        "Testbegriff-B", client=_Client(_antwort(TECHNIK_FACETTE))) == bb.TECHNIK
    bb.cache_leeren()

    # Und die Schwelle ist DIESELBE, die die Synonyme absichert — nicht
    # eine zweite daneben.
    assert bb.MIN_SPITZENANTEIL == 0.15


def test_968_ein_netzausfall_meldet_unbekannt_statt_technik():
    """Die teuerste Verwechslung dieses Projekts, hier vorweggenommen."""
    from bewerbungs_assistent.services import berufsbezeichnungen as bb

    class _Toter:
        def get(self, *a, **k):
            raise OSError("kein Netz")

    bb.cache_leeren()
    assert bb.begriffsart("Pflegefachkraft", client=_Toter()) == bb.UNBEKANNT
    bb.cache_leeren()


def test_968_keine_zeile_im_modul_kennt_ein_einzelnes_profil():
    """Der Guard gegen genau den Einwand, der diese Arbeit ausgeloest hat.

    Im Entscheidungsmodul darf kein Begriff aus einem konkreten
    Lebenslauf stehen — weder aus dem gemessenen Bestand noch aus dem
    Issue. Dieselbe Bauform wie der Ortsnamen-Guard aus #965: sonst
    waechst die Sonderbehandlung still hinein, sobald jemand einen Fall
    "nur schnell" ergaenzt.
    """
    quelle = (_repo() / "src" / "bewerbungs_assistent" / "services"
              / "muss_tor.py").read_text(encoding="utf-8").lower()
    # Beispiele in der Doku sind erlaubt; eine LOGIK, die einen Begriff
    # nennt, ist es nicht.
    code = "\n".join(z for z in quelle.split("\n")
                     if z.strip() and not z.strip().startswith("#")
                     and '"' not in z and "'" not in z)
    for begriff in ("plm", "pdm", "sap", "teamcenter", "windchill",
                    "pflegefachkraft", "erzieherin", "python"):
        assert begriff not in code, (
            f"'{begriff}' steht in der Entscheidungslogik — das Modul "
            "darf kein einzelnes Profil kennen.")
