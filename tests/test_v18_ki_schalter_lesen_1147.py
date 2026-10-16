"""#1147 Punkt 3, Variante B: der Schalter „Dokumentenanalyse“ sperrt auch die Werkzeuge, die Dokument- und Mailtexte LIEFERN.

Befund (01.10.2026): Die Karte „Was Claude bearbeiten darf“ sagte „Ist ein Schalter aus, gibt PBP für diesen Bereich nichts an Claude
weiter“. Gesperrt waren aber nur die Werkzeuge, mit denen Claude etwas AUSLÖST (elf). `dokument_lesen` (voller Text), `emails_anzeigen`
(Mailtext, Absender) und `dokumente_zur_analyse` lieferten bei ausgeschaltetem Schalter weiter: wer „Dokumentenanalyse“ aus
Datenschutzgründen abschaltete, glaubte, seine Dokumente gingen nicht an Claude — auf Zuruf gingen sie weiter.

Fassung A (v1.7.157) machte den Satz ehrlich. Fassung B (1.8.0) schließt die Lücke für die drei Werkzeuge, die Texte herausgeben;
`profil_zusammenfassung`, `bewerbung_details` und `interview_reflexion_lesen` bleiben bewusst frei (ohne sie arbeitet fast nichts
mehr), und der Satz sagt das. Je Werkzeug ein Test, in beide Richtungen. Alle Namen sind Platzhalter.
"""
from __future__ import annotations

import asyncio
import json

import pytest

import test_mcp_registry as reg

GEHEIMTEXT = "Sehr vertrauliche Gehaltsvorstellung: 123456 Euro, bitte nicht weitergeben."


@pytest.fixture
def umgebung(tmp_path):
    mcp, db = reg._build_test_server(tmp_path)
    db.save_profile({"name": "Erika Musterfrau"})
    app = db.add_application({"company": "Musterfirma GmbH", "title": "Planer", "status": "beworben"})
    doc = db.add_document({"filename": "absage.pdf", "doc_type": "absage", "extracted_text": GEHEIMTEXT, "linked_application_id": app})
    db.add_email({"application_id": app, "subject": "Ihre Bewerbung", "sender": "personal@musterfirma.example",
                  "body_text": GEHEIMTEXT, "direction": "eingang", "sent_date": "2026-10-01"})
    yield {"mcp": mcp, "db": db, "app": app, "doc": doc}
    db.close()


def _call(mcp, name, args):
    async def _run():
        tool = await mcp.get_tool(name)
        res = await tool.run(args)
        return res.structured_content if hasattr(res, "structured_content") else res
    return asyncio.run(_run())


def _aufrufe(u):
    return {
        "dokument_lesen": {"dokument_id": u["doc"]},
        "emails_anzeigen": {"bewerbung_id": u["app"]},
        "dokumente_zur_analyse": {},
    }


GESPERRT = ("dokument_lesen", "emails_anzeigen", "dokumente_zur_analyse")
#: Woran man sieht, dass das Werkzeug WIRKLICH geliefert hat (nicht nur "nicht gesperrt").
LIEFERT = {"dokument_lesen": "Sehr vertrauliche Gehaltsvorstellung", "emails_anzeigen": "Ihre Bewerbung",
           "dokumente_zur_analyse": "absage.pdf"}


@pytest.mark.parametrize("name", GESPERRT)
def test_bei_ausgeschalteter_dokumentenanalyse_gibt_das_werkzeug_keinen_text_heraus(umgebung, name):
    u = umgebung
    u["db"].set_ki_features(dokumentenanalyse=False)
    erg = _call(u["mcp"], name, _aufrufe(u)[name])
    assert erg.get("ki_blockiert") is True and erg.get("feature") == "dokumentenanalyse", erg
    assert "Dokumentenanalyse" in erg["hinweis"] and "Claude (Cloud)" in erg["hinweis"], erg
    assert "Dashboard" in erg["alternative"] and "Claude (Cloud)" in erg["alternative"], erg
    assert GEHEIMTEXT not in json.dumps(erg, ensure_ascii=False), "die Sperre gibt den Text heraus, den sie schuetzen soll"
    assert "personal@musterfirma.example" not in json.dumps(erg, ensure_ascii=False)


@pytest.mark.parametrize("name", GESPERRT)
def test_bei_eingeschalteter_dokumentenanalyse_liefert_das_werkzeug_wie_bisher(umgebung, name):
    u = umgebung
    erg = _call(u["mcp"], name, _aufrufe(u)[name])
    assert not erg.get("ki_blockiert"), erg
    assert LIEFERT[name] in json.dumps(erg, ensure_ascii=False), erg


@pytest.mark.parametrize("name", GESPERRT)
def test_der_master_schalter_sperrt_sie_ebenfalls(umgebung, name):
    u = umgebung
    u["db"].set_ki_features(master=False)
    erg = _call(u["mcp"], name, _aufrufe(u)[name])
    assert erg.get("ki_blockiert") is True and "Master" in erg["fehler"], erg


@pytest.mark.parametrize("name", GESPERRT)
def test_andere_schalter_beruehren_sie_nicht(umgebung, name):
    u = umgebung
    u["db"].set_ki_features(jobsuche=False, stellenanalyse=False, coaching=False, bewerbungserstellung=False, ersterfassung=False)
    erg = _call(u["mcp"], name, _aufrufe(u)[name])
    assert not erg.get("ki_blockiert"), "nur der Schalter Dokumentenanalyse gilt fuer diese Werkzeuge"


def test_profil_bewerbungen_und_reflexionen_bleiben_bewusst_frei(umgebung):
    """Ohne sie arbeitet fast nichts mehr; der Satz in den Einstellungen sagt es. Dieser Test haelt die Grenze fest: wer sie
    verschiebt, entscheidet es bewusst und aendert Satz und Test zusammen."""
    u = umgebung
    u["db"].set_ki_features(master=False)
    for name, args in (("profil_zusammenfassung", {}), ("bewerbung_details", {"bewerbung_id": u["app"]}),
                       ("interview_reflexionen_anzeigen", {})):
        erg = _call(u["mcp"], name, args)
        assert not erg.get("ki_blockiert"), (name, erg)


def test_die_zuordnung_nennt_alle_drei_und_ordnet_sie_der_dokumentenanalyse_zu():
    from bewerbungs_assistent.services import ki_zuordnung
    for name in GESPERRT:
        funktion, alternative = ki_zuordnung.ZUORDNUNG[name]
        assert funktion == "dokumentenanalyse" and alternative, name


def test_der_satz_in_den_einstellungen_sagt_was_gesperrt_ist_und_was_nicht():
    from pathlib import Path
    quelle = (Path(__file__).resolve().parents[1] / "frontend" / "src" / "pages" / "SettingsPage.jsx").read_text(encoding="utf-8-sig")
    ein = " ".join(quelle.split())
    assert "Bei „Dokumentenanalyse“ liest Claude dann auch keine Dokumente und Mails mehr" in ein
    assert "Aus: Claude liest auch keine Dokumente und Mails mehr." in ein
