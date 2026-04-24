"""Tests for Database.merge_jobs (#470)."""

import pytest


@pytest.fixture
def two_jobs(tmp_db):
    """Zwei Stellen anlegen, erste mit Bewerbung verknuepft."""
    master = {
        "hash": "master00000001",
        "title": "SAP / PLM Lead Consultant",
        "company": "VirtoTech Ltd.",
        "location": "Remote",
        "url": "",
        "source": "manuell",
        "description": "Master-Beschreibung.",
        "score": 8,
    }
    duplicate = {
        "hash": "dup00000001abc",
        "title": "PLM Expert (Endkunde: Rota Yokogawa) via VirtoTech",
        "company": "VirtoTech Ltd. (Endkunde: Rota Yokogawa)",
        "location": "",  # leer im Duplikat
        "url": "https://example.com/jobs/virtotech",
        "source": "headhunter",
        "description": "Duplikat-Zusatzinfo ueber Endkunde.",
        "score": 5,
    }
    tmp_db.save_jobs([master, duplicate])

    # Application an master verknuepfen
    app_id = tmp_db.add_application({
        "title": master["title"],
        "company": master["company"],
        "job_hash": master["hash"],
        "status": "beworben",
    })
    return tmp_db, master, duplicate, app_id


def test_dry_run_aendert_nichts(two_jobs):
    db, master, duplicate, app_id = two_jobs
    plan = db.merge_jobs(master["hash"], duplicate["hash"], dry_run=True)

    assert plan["status"] == "vorschau"
    # Nichts wurde geschrieben
    assert db.get_job(duplicate["hash"]) is not None
    assert db.get_job(master["hash"]) is not None
    app = db.get_application(app_id)
    assert app["job_hash"] and app["job_hash"] in master["hash"]


def test_auto_uebernahme_leere_masterfelder(two_jobs):
    """Wenn Master 'location' leer und Duplikat gefuellt -> uebernehmen."""
    db, master, duplicate, _ = two_jobs
    # Master-Location leeren, Duplikat auf Ort setzen
    db.update_job(master["hash"], {"location": ""})
    duplicate_db = db.get_job(duplicate["hash"])
    db.connect().execute(
        "UPDATE jobs SET location=? WHERE hash=?",
        ("Hamburg", duplicate_db["hash"]),
    )
    db.connect().commit()

    plan = db.merge_jobs(master["hash"], duplicate["hash"], dry_run=True)
    assert "location" in plan["feld_entscheidungen"]
    assert plan["feld_entscheidungen"]["location"]["quelle"] == "duplikat_auto"
    assert plan["feld_entscheidungen"]["location"]["nachher"] == "Hamburg"


def test_konflikt_default_master(two_jobs):
    """Beide Seiten gefuellt + keine Strategie -> Master gewinnt."""
    db, master, duplicate, _ = two_jobs
    plan = db.merge_jobs(master["hash"], duplicate["hash"], dry_run=True)
    assert "description" in plan["konflikte"]
    assert plan["feld_entscheidungen"]["description"]["quelle"] == "master"


def test_strategie_merge_fuer_description(two_jobs):
    db, master, duplicate, _ = two_jobs
    plan = db.merge_jobs(
        master["hash"], duplicate["hash"],
        field_strategy={"description": "merge"},
        dry_run=True,
    )
    desc = plan["feld_entscheidungen"]["description"]["nachher"]
    assert "Master-Beschreibung." in desc
    assert "Duplikat-Zusatzinfo" in desc


def test_strategie_duplikat_fuer_url(two_jobs):
    db, master, duplicate, _ = two_jobs
    plan = db.merge_jobs(
        master["hash"], duplicate["hash"],
        field_strategy={"url": "duplikat"},
        dry_run=True,
    )
    # url ist im Master leer, im Duplikat gefuellt -> auto (kein Konflikt),
    # aber Strategie 'duplikat' ist konsistent
    assert plan["feld_entscheidungen"]["url"]["nachher"] == duplicate["url"]


def test_commit_loescht_duplikat_und_merged(two_jobs):
    db, master, duplicate, app_id = two_jobs
    result = db.merge_jobs(
        master["hash"], duplicate["hash"],
        field_strategy={"description": "merge"},
        dry_run=False,
    )
    assert result["status"] == "ok"
    # Duplikat weg, Master da
    assert db.get_job(duplicate["hash"]) is None
    merged = db.get_job(master["hash"])
    assert merged is not None
    assert "Duplikat-Zusatzinfo" in merged["description"]
    # url wurde automatisch uebernommen (Master war leer)
    assert merged["url"] == duplicate["url"]


def test_commit_haengt_duplikat_bewerbungen_um(two_jobs):
    db, master, duplicate, _ = two_jobs
    # Neue Bewerbung an Duplikat haengen (Szenario C aus #470)
    dup_app_id = db.add_application({
        "title": duplicate["title"],
        "company": duplicate["company"],
        "job_hash": duplicate["hash"],
        "status": "beworben",
    })

    plan = db.merge_jobs(master["hash"], duplicate["hash"], dry_run=True)
    assert dup_app_id in plan["umgehaengte_bewerbungen"]

    result = db.merge_jobs(master["hash"], duplicate["hash"], dry_run=False)
    assert result["status"] == "ok"

    # Duplikat-Bewerbung zeigt jetzt auf Master
    dup_app = db.get_application(dup_app_id)
    assert dup_app is not None
    # master_hash kann scoped sein -> Vergleich via 'in'
    assert master["hash"] in dup_app["job_hash"] or dup_app["job_hash"] in master["hash"]


def test_nicht_gefundene_hashes(tmp_db):
    r1 = tmp_db.merge_jobs("nix", "auch_nix", dry_run=True)
    assert r1["fehler"] == "master_nicht_gefunden"


def test_identische_hashes(tmp_db):
    r = tmp_db.merge_jobs("xyz", "xyz", dry_run=True)
    assert r["fehler"] == "master und duplikat sind identisch"
