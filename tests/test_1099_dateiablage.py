"""#1099: PBP löscht nur Dateien, die ihm gehören.

Datenordner und Quellordner des Nutzers liegen hier bewusst GETRENNT
(beide in Temp-Verzeichnissen). Im bisherigen Import-Test lag die Quelle
innerhalb des Datenordners — "außerhalb von PBP" ließ sich so gar nicht
prüfen. Kein Test zeigt je auf echte Dateien.
"""
from __future__ import annotations

import importlib
import os
from pathlib import Path

import pytest


@pytest.fixture
def umgebung(tmp_path):
    daten = tmp_path / "daten"
    quelle = tmp_path / "nutzer_ordner"
    daten.mkdir()
    quelle.mkdir()
    os.environ["BA_DATA_DIR"] = str(daten)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=daten / "test.db")
    db.initialize()
    assert str(daten) in str(db.db_path), f"DB nicht isoliert: {db.db_path}"

    import bewerbungs_assistent.dashboard as dash
    dash._db = db
    from fastapi.testclient import TestClient
    client = TestClient(dash.app)
    client.post("/api/profile", json={"name": "Importer"})
    yield {"db": db, "client": client, "daten": daten, "quelle": quelle}
    db.close()
    os.environ.pop("BA_DATA_DIR", None)


def _import(client, ordner, **extra):
    body = {"folder_path": str(ordner), "import_documents": True,
            "import_applications": False, "recursive": True}
    body.update(extra)
    r = client.post("/api/documents/import-folder", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _docs(db):
    return [dict(r) for r in db.connect().execute(
        "SELECT id, filename, filepath, extracted_text, content_hash, profile_id "
        "FROM documents ORDER BY filepath").fetchall()]


# ── AK 1: gleichnamige Dateien aus verschiedenen Unterordnern ─────────

def test_gleichnamige_dateien_ergeben_zwei_dateien(umgebung):
    q = umgebung["quelle"]
    (q / "FirmaA").mkdir()
    (q / "FirmaB").mkdir()
    (q / "FirmaA" / "Anschreiben.txt").write_text("Inhalt von Firma A", encoding="utf-8")
    (q / "FirmaB" / "Anschreiben.txt").write_text("Inhalt von Firma B", encoding="utf-8")

    res = _import(umgebung["client"], q)
    assert res["documents_imported"] == 2

    docs = _docs(umgebung["db"])
    assert len(docs) == 2
    pfade = {d["filepath"] for d in docs}
    assert len(pfade) == 2, "zwei Einträge teilen sich eine Datei"
    for d in docs:
        inhalt = Path(d["filepath"]).read_text(encoding="utf-8")
        assert inhalt in d["extracted_text"], "Datei und ausgelesener Text passen nicht"
        assert str(umgebung["daten"]) in d["filepath"]


# ── AK 2: scheitert das Kopieren, entsteht kein Eintrag ───────────────

def test_kopierfehler_legt_keinen_eintrag_an(umgebung, monkeypatch):
    q = umgebung["quelle"]
    (q / "Zeugnis.txt").write_text("Zeugnistext", encoding="utf-8")

    import shutil

    def kaputt(*a, **k):
        raise PermissionError("gesperrt")

    monkeypatch.setattr(shutil, "copy2", kaputt)
    res = _import(umgebung["client"], q)

    assert res["documents_imported"] == 0
    assert _docs(umgebung["db"]) == []
    assert any("Zeugnis.txt" in w for w in res["warnings"]), res["warnings"]


def test_kein_eintrag_zeigt_je_auf_das_original(umgebung):
    q = umgebung["quelle"]
    (q / "Lebenslauf.txt").write_text("CV", encoding="utf-8")
    _import(umgebung["client"], q)
    for d in _docs(umgebung["db"]):
        assert not d["filepath"].startswith(str(q))


# ── AK 3: delete_document ─────────────────────────────────────────────

def _doc_mit_pfad(db, pfad, name="x.txt"):
    return db.add_document({"filename": name, "filepath": str(pfad),
                            "doc_type": "sonstiges"})


def test_loeschen_trifft_keine_datei_ausserhalb(umgebung):
    original = umgebung["quelle"] / "Original.txt"
    original.write_text("gehört dem Nutzer", encoding="utf-8")
    did = _doc_mit_pfad(umgebung["db"], original)

    befund = umgebung["db"].delete_document_mit_befund(did)
    assert befund["eintrag_geloescht"] is True
    assert befund["datei"]["geloescht"] is False
    assert "außerhalb" in befund["datei"]["grund"]
    assert original.exists(), "Originaldatei des Nutzers wurde gelöscht"


def test_loeschen_innerhalb_entfernt_die_datei(umgebung):
    datei = umgebung["daten"] / "dokumente" / "eigen.txt"
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text("PBP-Kopie", encoding="utf-8")
    did = _doc_mit_pfad(umgebung["db"], datei)

    assert umgebung["db"].delete_document(did) is True
    assert not datei.exists()


def test_loeschen_trifft_keine_geteilte_datei(umgebung):
    datei = umgebung["daten"] / "dokumente" / "geteilt.txt"
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text("zwei Einträge", encoding="utf-8")
    db = umgebung["db"]
    a = _doc_mit_pfad(db, datei)
    b = _doc_mit_pfad(db, datei)

    befund = db.delete_document_mit_befund(a)
    assert befund["datei"]["geloescht"] is False
    assert "anderen Eintrag" in befund["datei"]["grund"]
    assert datei.exists()
    # Der letzte Eintrag darf die Datei dann mitnehmen.
    assert db.delete_document_mit_befund(b)["datei"]["geloescht"] is True
    assert not datei.exists()


def test_geteilt_zaehlt_auch_andere_profile(umgebung):
    db = umgebung["db"]
    datei = umgebung["daten"] / "dokumente" / "profilfremd.txt"
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text("x", encoding="utf-8")
    eigen = _doc_mit_pfad(db, datei)
    db.add_document({"filename": "x.txt", "filepath": str(datei),
                     "profile_id": "anderes-profil"})
    assert db.delete_document_mit_befund(eigen)["datei"]["geloescht"] is False
    assert datei.exists()


def test_werkzeug_und_endpunkt_nennen_den_grund(umgebung):
    original = umgebung["quelle"] / "Brief.txt"
    original.write_text("x", encoding="utf-8")
    db = umgebung["db"]
    did = _doc_mit_pfad(db, original)
    r = umgebung["client"].delete(f"/api/document/{did}")
    assert r.status_code == 200
    assert r.json()["datei_geloescht"] is False
    assert "außerhalb" in r.json()["datei_hinweis"]
    assert original.exists()


# ── AK 4: zweiter Import legt keine Dubletten an ─────────────────────

def test_zweiter_import_ohne_dubletten(umgebung):
    q = umgebung["quelle"]
    (q / "A.txt").write_text("eins", encoding="utf-8")
    (q / "B.txt").write_text("zwei", encoding="utf-8")
    erst = _import(umgebung["client"], q)
    zweit = _import(umgebung["client"], q)
    assert erst["documents_imported"] == 2
    assert zweit["documents_imported"] == 0
    assert zweit["skipped_duplicates"] == 2
    assert len(_docs(umgebung["db"])) == 2


def test_alteintrag_ohne_hash_gilt_als_dublette(umgebung):
    """Eintraege aus der Zeit vor #1099 tragen keinen Hash — der erste
    Import nach dem Update darf sie trotzdem nicht verdoppeln."""
    q = umgebung["quelle"]
    (q / "Alt.txt").write_text("alter Inhalt", encoding="utf-8")
    _import(umgebung["client"], q)
    db = umgebung["db"]
    db.connect().execute("UPDATE documents SET content_hash=NULL")
    db.connect().commit()

    res = _import(umgebung["client"], q)
    assert res["documents_imported"] == 0
    assert len(_docs(db)) == 1
    assert _docs(db)[0]["content_hash"], "Hash wird beim Treffer nachgetragen"


# ── Löschbereiche: dieselbe Regel ─────────────────────────────────────

def test_loeschbereich_dokumente_laesst_originale_liegen(umgebung):
    from bewerbungs_assistent.services import loeschbereiche
    db = umgebung["db"]
    original = umgebung["quelle"] / "Original.txt"
    original.write_text("Nutzer", encoding="utf-8")
    _doc_mit_pfad(db, original)
    eigen = umgebung["daten"] / "dokumente" / "eigen.txt"
    eigen.parent.mkdir(parents=True, exist_ok=True)
    eigen.write_text("PBP", encoding="utf-8")
    _doc_mit_pfad(db, eigen)

    vor = loeschbereiche.vorschau(db, ["dokumente"], None)
    assert vor["dateien_bleiben_liegen"] == 1
    res = loeschbereiche.leeren(db, ["dokumente"], None, dry_run=False)
    assert original.exists(), "Löschbereich hat die Originaldatei gelöscht"
    assert not eigen.exists()
    assert res["dateien_geloescht"] == 1
    assert res["dateien_bleiben_liegen"][0]["pfad"] == str(original)


def test_loeschbereich_eines_profils_schont_dateien_anderer_profile(umgebung):
    from bewerbungs_assistent.services import loeschbereiche
    db = umgebung["db"]
    pid = db.get_active_profile_id()
    datei = umgebung["daten"] / "dokumente" / "beide.txt"
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text("x", encoding="utf-8")
    _doc_mit_pfad(db, datei)
    db.add_document({"filename": "beide.txt", "filepath": str(datei),
                     "profile_id": "anderes-profil"})
    loeschbereiche.leeren(db, ["dokumente"], pid, dry_run=False)
    assert datei.exists()


def test_loeschbereich_mehrere_eintraege_im_selben_vorgang(umgebung):
    """Zwei Einträge DESSELBEN Vorgangs auf einer Datei: beide gehen, also
    darf die Datei mit — sonst bliebe sie für immer liegen."""
    from bewerbungs_assistent.services import loeschbereiche
    db = umgebung["db"]
    datei = umgebung["daten"] / "dokumente" / "doppelt.txt"
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text("x", encoding="utf-8")
    _doc_mit_pfad(db, datei)
    _doc_mit_pfad(db, datei)
    loeschbereiche.leeren(db, ["dokumente"], None, dry_run=False)
    assert not datei.exists()


# ── Profil-Import und Pfad-Reparatur ──────────────────────────────────

def test_profil_import_kopiert_statt_zu_teilen(umgebung):
    db = umgebung["db"]
    datei = umgebung["daten"] / "dokumente" / "cv.txt"
    datei.parent.mkdir(parents=True, exist_ok=True)
    datei.write_text("Lebenslauf", encoding="utf-8")
    fehlt = umgebung["daten"] / "dokumente" / "weg.txt"
    daten = {"name": "Zweitprofil", "documents": [
        {"filename": "cv.txt", "filepath": str(datei), "doc_type": "lebenslauf"},
        {"filename": "weg.txt", "filepath": str(fehlt), "doc_type": "sonstiges"},
    ]}
    pid = db.import_profile_json(daten)
    rows = [dict(r) for r in db.connect().execute(
        "SELECT filename, filepath FROM documents WHERE profile_id=?", (pid,))]
    cv = next(r for r in rows if r["filename"] == "cv.txt")
    assert cv["filepath"] and cv["filepath"] != str(datei)
    assert Path(cv["filepath"]).read_text(encoding="utf-8") == "Lebenslauf"
    assert pid in cv["filepath"]
    weg = next(r for r in rows if r["filename"] == "weg.txt")
    assert not weg["filepath"], "Eintrag zeigt auf eine fehlende Datei"


def test_pfadreparatur_biegt_nicht_auf_fremde_datei(umgebung):
    db = umgebung["db"]
    doku = umgebung["daten"] / "dokumente"
    doku.mkdir(parents=True, exist_ok=True)
    fremd = doku / "Anschreiben.txt"
    fremd.write_text("gehört Dokument A", encoding="utf-8")
    _doc_mit_pfad(db, fremd, name="Anschreiben.txt")
    b = _doc_mit_pfad(db, umgebung["daten"] / "alt" / "Anschreiben.txt",
                      name="Anschreiben.txt")
    db._repair_document_paths()
    pfad = db.connect().execute(
        "SELECT filepath FROM documents WHERE id=?", (b,)).fetchone()[0]
    assert Path(pfad) != fremd


def test_pfadreparatur_findet_freie_datei_weiter(umgebung):
    """Gegenrichtung: eine Datei, die keinem anderen Eintrag gehört, wird
    wie bisher gefunden (#503)."""
    db = umgebung["db"]
    doku = umgebung["daten"] / "dokumente"
    doku.mkdir(parents=True, exist_ok=True)
    frei = doku / "Zeugnis.txt"
    frei.write_text("z", encoding="utf-8")
    did = _doc_mit_pfad(db, umgebung["daten"] / "alt" / "Zeugnis.txt",
                        name="Zeugnis.txt")
    assert db._repair_document_paths() == 1
    pfad = db.connect().execute(
        "SELECT filepath FROM documents WHERE id=?", (did,)).fetchone()[0]
    assert Path(pfad) == frei


# ── Bestandsbericht ───────────────────────────────────────────────────

def test_bestandsbericht_liest_nur(umgebung):
    from bewerbungs_assistent.services import dateiablage
    db = umgebung["db"]
    original = umgebung["quelle"] / "O.txt"
    original.write_text("x", encoding="utf-8")
    _doc_mit_pfad(db, original)
    geteilt = umgebung["daten"] / "g.txt"
    geteilt.write_text("x", encoding="utf-8")
    _doc_mit_pfad(db, geteilt)
    _doc_mit_pfad(db, geteilt)
    vorher = _docs(db)

    b = dateiablage.bestandsbericht(db)
    assert len(b["ausserhalb_datenordner"]) == 1
    assert len(b["geteilte_dateien"]) == 1
    assert _docs(db) == vorher
    assert original.exists() and geteilt.exists()


def test_pfadreparatur_prueft_den_inhalt(umgebung):
    """Eine freie Datei gleichen Namens mit ANDEREM Inhalt ist nicht die
    gesuchte — der Eintrag bleibt kaputt statt falsch."""
    import hashlib
    db = umgebung["db"]
    doku = umgebung["daten"] / "dokumente"
    doku.mkdir(parents=True, exist_ok=True)
    (doku / "Bericht.txt").write_text("anderer Inhalt", encoding="utf-8")
    did = db.add_document({
        "filename": "Bericht.txt",
        "filepath": str(umgebung["daten"] / "alt" / "Bericht.txt"),
        "content_hash": hashlib.sha256(b"urspruenglicher Inhalt").hexdigest(),
    })
    assert db._repair_document_paths() == 0
    pfad = db.connect().execute(
        "SELECT filepath FROM documents WHERE id=?", (did,)).fetchone()[0]
    assert "alt" in pfad


def test_mcp_werkzeug_nennt_den_grund(umgebung):
    import asyncio
    import logging
    from fastmcp import FastMCP
    from bewerbungs_assistent.tools import register_all

    db = umgebung["db"]
    mcp = FastMCP("PBP #1099 Test")
    register_all(mcp, db, logging.getLogger("test.1099"))
    original = umgebung["quelle"] / "Behalten.txt"
    original.write_text("x", encoding="utf-8")
    did = _doc_mit_pfad(db, original)

    async def _lauf():
        tool = await mcp.get_tool("dokument_loeschen")
        res = await tool.run({"dokument_id": did, "bestaetigung": True})
        return res.structured_content

    antwort = asyncio.run(_lauf())
    assert antwort["status"] == "geloescht"
    assert antwort["datei_geloescht"] is False
    assert "außerhalb" in antwort["datei_hinweis"]
    assert original.exists()
