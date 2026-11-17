"""#1394: Quellen ohne eigene Suche vergleichen Suchbegriffe an Wortgrenzen.

Gemessen am 16.11.2026: arbeitnow Seite 1 = 300 Stellen, 177 durch den Filter,
3 echte Treffer (PLM). "ECO" steckte in "economy", "ECR" in "recruit".
"""
import importlib

import pytest

from bewerbungs_assistent.job_scraper import (
    arbeitnow, berufsstart, ferchau, greenhouse, himalayas, meinestadt,
    personio, remoteok, remotive, rohtreffer, stichwort_abgleich, studentjob,
    workday_dax)

KW = ["ECO", "ECR", "ECN", "PLM", "Data Governance"]
FACHFREMD = ("We are building a strong economy of recruit and secret "
             "secretary services; become an ecommerce leader.")


def _an(titel, text="", tags=None):
    return {"title": titel, "company_name": "Beispiel GmbH",
            "description": text, "tags": tags or [], "location": "", "remote": True}


def test_arbeitnow_teilwort_faellt_durch():
    assert not arbeitnow._matches(_an("Sales Manager", FACHFREMD), KW, None)


def test_remoteok_teilwort_faellt_durch():
    assert not remoteok._matches("Sales Manager", "sales", FACHFREMD, KW)


def test_arbeitnow_eco_prozess_im_titel_geht_durch():
    assert arbeitnow._matches(_an("ECO-Prozess Verantwortlicher"), KW, None)
    assert arbeitnow._matches(_an("Engineer ECR/ECO"), KW, None)


def test_remoteok_ecr_eco_im_titel_geht_durch():
    assert remoteok._matches("Engineer ECR/ECO", "", "", KW)


def test_kurzer_begriff_im_fliesstext_nur_grossgeschrieben():
    assert not stichwort_abgleich.passt(["ECO"], "Sales", "", "our eco-friendly ECOnomy")
    assert not stichwort_abgleich.passt(["ECO"], "Sales", "", "eco process in text")
    assert stichwort_abgleich.passt(["ECO"], "Sales", "", "Freigabe per ECO und ECR")


def test_kurzer_begriff_in_tags_zaehlt():
    assert stichwort_abgleich.passt(["PLM"], "Engineer", "plm, cad", "")


def test_langer_begriff_wortgrenze_und_beugung():
    assert stichwort_abgleich.passt(["Konstrukteur"], "Konstrukteurin (m/w/d)")
    assert not stichwort_abgleich.passt(["Data Governance"], "Analyst", "", "data and governance")
    assert stichwort_abgleich.passt(["Data Governance"], "Analyst", "", "Data Governance Rolle")
    assert stichwort_abgleich.passt(["Pflege"], "Pflegekraft")  # Zusammensetzung, Wortanfang
    assert not stichwort_abgleich.passt(["Pflege"], "Fahrer", "", "Kopfpflege")  # nie mitten im Wort


def test_umlaute_unicode_wortgrenze():
    assert stichwort_abgleich.passt(["Ölförderung"], "Ingenieur Oelfoerderung")
    assert not stichwort_abgleich.passt(["ECO"], "Sales", "", "ÄECOÄ")


def test_firmenname_zaehlt_nicht():
    job = _an("Sales Manager")
    job["company_name"] = "PLM Beratung GmbH"
    assert not arbeitnow._matches(job, ["PLM"], None)


def test_ohne_suchbegriffe_passiert_alles():
    assert stichwort_abgleich.passt([], "irgendwas")


def test_gegenprobe_gemessene_zahlen_arbeitnow_seite_1():
    """300 Stellen: 177 Teilworttreffer, 3 echte PLM. Jetzt deutlich unter 20."""
    feed = []
    for i in range(300):
        if i < 3:
            feed.append(_an(f"PLM Consultant {i}", "Teamcenter PLM rollout"))
        elif i < 180:
            feed.append(_an(f"Manager {i}", FACHFREMD))
        else:
            feed.append(_an(f"Nurse {i}", "Care for patients"))
    durch = [j for j in feed if arbeitnow._matches(j, KW, None)]
    assert 3 <= len(durch) < 20


@pytest.mark.parametrize("modul", [berufsstart, greenhouse, himalayas, meinestadt,
                                   personio, remotive, studentjob, workday_dax, ferchau])
def test_kein_scraper_vergleicht_mehr_als_teilwort(modul):
    quelle = open(modul.__file__, encoding="utf-8").read()
    assert "kw.lower().strip() in haystack" not in quelle
    assert "str(k).lower() in low" not in quelle
    assert "stichwort_abgleich" in quelle


def test_bilanz_je_quelle():
    rohtreffer.lauf_beginnen()
    rohtreffer.melde("arbeitnow", 3)
    stichwort_abgleich.passt(KW, "ECO Prozess", "", "", quelle="arbeitnow")
    stichwort_abgleich.passt(KW, "Sales", "", "Teamcenter PLM", quelle="arbeitnow")
    stichwort_abgleich.passt(KW, "Sales", "", FACHFREMD, quelle="arbeitnow")
    assert rohtreffer.bilanz()["arbeitnow"] == {
        "geliefert": 3, "durch_filter": 2, "mit_pflichttreffer_im_titel": 1}
    rohtreffer.lauf_beginnen()
    assert rohtreffer.bilanz() == {}
