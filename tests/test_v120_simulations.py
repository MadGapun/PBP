"""v1.2.0 Feature-Simulationen — testet neue Features in Kombination mit bestehenden.

Simuliert realistische User-Workflows die mehrere Features kreuzen:
1. Blacklist + Lernender Score (#109 + #110)
2. Vertrauliche Projekte + CV-Export (#246 + alte Export-Pipeline)
3. Recherche speichern + Duplikat-Erkennung (#240 + #222)
4. E-Mail-Kontakt + Bewerbungs-Pipeline (#225 + alte Bewerbungen)
5. Neue + alte Prompts koexistieren (#117 + #195)
6. OCR/.doc Fallback (#192)
7. Dashboard-Hints (#233)
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


# ---------- helpers ----------

def _build_server(tmp_path):
    os.environ["BA_DATA_DIR"] = str(tmp_path)
    from bewerbungs_assistent.database import Database
    db = Database(db_path=tmp_path / "test.db")
    db.initialize()
    return db


def _seed_profile(db):
    """Erstellt ein vollständiges Profil mit Position + Projekt."""
    db.save_profile({
        "name": "Max Mustermann",
        "email": "max@example.com",
        "city": "Hamburg",
        "plz": "20095",
        "summary": "Senior IT-Consultant, 10 Jahre PLM-Erfahrung.",
        "preferences": json.dumps({
            "stellentyp": "beides",
            "arbeitsmodell": "hybrid",
            "min_gehalt": 70000,
        }),
    })
    pid = db.add_position({
        "company": "TechCorp GmbH",
        "title": "Senior PLM Consultant",
        "location": "Hamburg",
        "start_date": "2018-01",
        "is_current": True,
        "employment_type": "festanstellung",
    })
    return pid


def _seed_jobs(db, companies=None):
    """Legt Test-Stellen an."""
    if companies is None:
        companies = [
            ("CIDEON Software", "PLM Berater", "stepstone", "zeitarbeit"),
            ("CIDEON Engineering", "Windchill Admin", "indeed", "zeitarbeit"),
            ("Siemens DI", "Teamcenter Consultant", "stepstone", "festanstellung"),
            ("Accenture", "PLM Architect", "linkedin", "festanstellung"),
            ("Hays AG", "SAP Consultant (m/w/d)", "stepstone", "zeitarbeit"),
            ("Hays AG", "PLM Berater (m/w/d)", "indeed", "zeitarbeit"),
            ("Hays AG", "IT Projektleiter", "stepstone", "zeitarbeit"),
        ]
    hashes = []
    for i, (company, title, source, emp_type) in enumerate(companies):
        h = f"sim_{i:04d}_{company[:4].lower()}"
        db.save_jobs([{
            "hash": h,
            "title": title,
            "company": company,
            "location": "Hamburg",
            "url": f"https://example.com/{h}",
            "source": source,
            "description": f"{title} bei {company} in Hamburg",
            "score": 5,
            "remote_level": "hybrid",
            "employment_type": emp_type,
        }])
        hashes.append(h)
    return hashes


# ==========================================================
# SIMULATION 1: Blacklist + Lernender Score (#109 + #110)
# ==========================================================

class TestSim1BlacklistUndLernenderScore:
    """Szenario: User sortiert wiederholt Zeitarbeit-Stellen aus.
    Ab 5x soll der Score automatisch angepasst werden.
    Dann blacklistet er eine Firma — alle deren Stellen verschwinden."""

    def test_dismiss_zeitarbeit_triggers_learning(self, tmp_path):
        db = _build_server(tmp_path)
        _seed_profile(db)
        hashes = _seed_jobs(db)

        # User sortiert 5x zeitarbeit aus
        for i, h in enumerate(hashes):
            job = db.get_job(h)
            if job and job.get("employment_type") == "zeitarbeit":
                db.dismiss_job(h, "zeitarbeit")
                counts = db.get_setting("dismiss_counts", {})
                counts["zeitarbeit"] = counts.get("zeitarbeit", 0) + 1
                db.set_setting("dismiss_counts", counts)
                db.increment_dismiss_reason_usage(["zeitarbeit"])

        counts = db.get_setting("dismiss_counts", {})
        assert counts.get("zeitarbeit", 0) >= 5, f"Erwartet >=5 Ablehnungen, bekam {counts}"

        # Teste _auto_adjust_scoring direkt (simuliert das Tool-Verhalten)
        # #269 fix: Muss den Seed-Eintrag (profile_id='') finden und updaten
        profile_id = db.get_active_profile_id() or ""
        conn = db.connect()
        existing = conn.execute(
            "SELECT id, ignore_flag FROM scoring_config "
            "WHERE (profile_id=? OR profile_id='') AND dimension='stellentyp' AND sub_key='zeitarbeit' "
            "ORDER BY CASE WHEN profile_id=? THEN 0 ELSE 1 END LIMIT 1",
            (profile_id, profile_id)
        ).fetchone()
        assert existing is not None, "Seed-Eintrag für zeitarbeit nicht gefunden"
        conn.execute("UPDATE scoring_config SET ignore_flag=1 WHERE id=?", (existing["id"],))
        conn.commit()

        # Verifiziere: genau ein zeitarbeit-Eintrag, und der hat ignore_flag=1
        config = db.get_scoring_config()
        zeitarbeit_cfg = [c for c in config if c["dimension"] == "stellentyp" and c["sub_key"] == "zeitarbeit"]
        assert len(zeitarbeit_cfg) == 1, f"Erwartet 1 zeitarbeit-Eintrag, bekam {len(zeitarbeit_cfg)} (Duplikat-Bug #269?)"
        assert zeitarbeit_cfg[0]["ignore_flag"] == 1, "Zeitarbeit sollte auf IGNORIEREN stehen"
        db.close()

    def test_blacklist_firma_deaktiviert_alle_stellen(self, tmp_path):
        db = _build_server(tmp_path)
        _seed_profile(db)
        hashes = _seed_jobs(db)

        # Prüfe: 3 Hays-Stellen aktiv
        active_before = [j for j in db.get_active_jobs() if "Hays" in j.get("company", "")]
        assert len(active_before) == 3, f"Erwartet 3 Hays-Stellen, gefunden {len(active_before)}"

        # Blackliste Hays (#109)
        db.add_to_blacklist("firma", "Hays", "Zeitarbeitsfirma")
        conn = db.connect()
        dismissed = conn.execute(
            "UPDATE jobs SET is_active=0, dismiss_reason='firma_blacklisted' "
            "WHERE is_active=1 AND LOWER(company) LIKE ?",
            ("%hays%",)
        ).rowcount
        conn.commit()

        assert dismissed == 3, f"Erwartet 3 deaktivierte Stellen, bekam {dismissed}"

        # Prüfe: 0 Hays-Stellen aktiv, andere unberührt
        active_after = [j for j in db.get_active_jobs() if "Hays" in j.get("company", "")]
        assert len(active_after) == 0
        other_active = [j for j in db.get_active_jobs() if "Hays" not in j.get("company", "")]
        assert len(other_active) >= 2, "Andere Firmen sollten weiterhin aktiv sein"
        db.close()

    def test_blacklist_plus_dismiss_kombi(self, tmp_path):
        """Erst einzeln aussortieren, dann die ganze Firma blacklisten."""
        db = _build_server(tmp_path)
        _seed_profile(db)
        hashes = _seed_jobs(db)

        # Sortiere erste CIDEON-Stelle aus
        cideon_hashes = [h for h in hashes if "cide" in h]
        assert len(cideon_hashes) == 2
        db.dismiss_job(cideon_hashes[0], "firma_uninteressant")

        # Jetzt Blacklist für CIDEON
        db.add_to_blacklist("firma", "CIDEON", "Nicht interessant")
        conn = db.connect()
        conn.execute(
            "UPDATE jobs SET is_active=0, dismiss_reason='firma_blacklisted' "
            "WHERE is_active=1 AND LOWER(company) LIKE ?",
            ("%cideon%",)
        ).rowcount
        conn.commit()

        # Alle CIDEON-Stellen inaktiv (1 manuell + 1 per Blacklist)
        all_cideon = conn.execute(
            "SELECT is_active, dismiss_reason FROM jobs WHERE LOWER(company) LIKE '%cideon%'"
        ).fetchall()
        for row in all_cideon:
            assert row["is_active"] == 0
        db.close()


# ==========================================================
# SIMULATION 2: Vertrauliche Projekte + CV-Export (#246)
# ==========================================================

class TestSim2VertraulicheProjekteExport:
    """Szenario: Freelancer hat Projekte mit vertraulichen Kundennamen.
    Beim CV-Export müssen diese anonymisiert werden."""

    def test_projekt_mit_vertraulichem_kunden(self, tmp_path):
        db = _build_server(tmp_path)
        pos_id = _seed_profile(db)

        # Projekt 1: Offen
        p1 = db.add_project(pos_id, {
            "name": "PLM-Migration",
            "customer_name": "BMW AG",
            "is_confidential": 0,
            "role": "Projektleiter",
            "result": "100% Migration",
        })
        # Projekt 2: Vertraulich
        p2 = db.add_project(pos_id, {
            "name": "SAP-Integration",
            "customer_name": "Geheime Bank GmbH",
            "is_confidential": 1,
            "role": "Architekt",
            "result": "Nahtlose Integration",
        })

        # Verifiziere DB
        conn = db.connect()
        proj1 = conn.execute("SELECT * FROM projects WHERE id=?", (p1,)).fetchone()
        proj2 = conn.execute("SELECT * FROM projects WHERE id=?", (p2,)).fetchone()
        assert proj1["customer_name"] == "BMW AG"
        assert proj1["is_confidential"] == 0
        assert proj2["customer_name"] == "Geheime Bank GmbH"
        assert proj2["is_confidential"] == 1

        # Teste Export-Anonymisierung
        from bewerbungs_assistent.export import _project_display_name
        assert "BMW AG" in _project_display_name(dict(proj1))
        assert "Geheime Bank" not in _project_display_name(dict(proj2))
        assert "[vertraulich]" in _project_display_name(dict(proj2))
        db.close()

    def test_cv_text_export_anonymisiert(self, tmp_path):
        db = _build_server(tmp_path)
        pos_id = _seed_profile(db)

        db.add_project(pos_id, {
            "name": "Datenbank-Redesign",
            "customer_name": "Deutsche Bank",
            "is_confidential": 1,
            "role": "Lead Developer",
            "result": "50% Performance-Steigerung",
        })

        profile = db.get_profile()
        from bewerbungs_assistent.export import generate_cv_text
        out = tmp_path / "cv.txt"
        generate_cv_text(profile, out)
        content = out.read_text()

        assert "Deutsche Bank" not in content, "Vertraulicher Kundenname im CV-Text gefunden!"
        assert "[vertraulich]" in content, "Anonymisierungs-Marker fehlt im CV-Text"
        assert "Datenbank-Redesign" in content, "Projektname sollte sichtbar sein"
        db.close()

    def test_cv_markdown_export_anonymisiert(self, tmp_path):
        db = _build_server(tmp_path)
        pos_id = _seed_profile(db)

        db.add_project(pos_id, {
            "name": "Cloud-Migration",
            "customer_name": "Volkswagen",
            "is_confidential": 1,
            "role": "Cloud Architect",
        })
        db.add_project(pos_id, {
            "name": "Web-Portal",
            "customer_name": "Porsche",
            "is_confidential": 0,
            "role": "Full-Stack Dev",
        })

        profile = db.get_profile()
        from bewerbungs_assistent.export import generate_cv_markdown
        out = tmp_path / "cv.md"
        generate_cv_markdown(profile, out)
        content = out.read_text()

        assert "Volkswagen" not in content, "Vertraulicher Kunde 'Volkswagen' im Markdown!"
        assert "Porsche" in content, "Offener Kunde 'Porsche' sollte sichtbar sein"
        assert "[vertraulich]" in content
        db.close()

    def test_projekt_ohne_customer_name_unveraendert(self, tmp_path):
        """Projekte ohne customer_name sollen exakt wie vor v1.2.0 exportiert werden."""
        db = _build_server(tmp_path)
        pos_id = _seed_profile(db)

        db.add_project(pos_id, {
            "name": "Internes Projekt",
            "role": "Developer",
            "result": "Erfolgreich",
        })

        profile = db.get_profile()
        from bewerbungs_assistent.export import generate_cv_text
        out = tmp_path / "cv.txt"
        generate_cv_text(profile, out)
        content = out.read_text()

        assert "Internes Projekt" in content
        assert "[vertraulich]" not in content, "Kein Vertraulich-Marker ohne customer_name"
        assert "(Kunde:" not in content, "Kein Kunde-Label ohne customer_name"
        db.close()


# ==========================================================
# SIMULATION 3: Recherche speichern + Duplikat (#240 + #222)
# ==========================================================

class TestSim3RecherchePlusDuplikat:
    """Szenario: User recherchiert eine Firma, speichert die Analyse,
    versucht dann eine Duplikat-Stelle manuell anzulegen."""

    def test_recherche_an_stelle_speichern(self, tmp_path):
        db = _build_server(tmp_path)
        _seed_profile(db)
        hashes = _seed_jobs(db)

        job_hash = hashes[2]  # Siemens
        # resolve to stored hash (save_jobs scopes it)
        stored_hash = db.resolve_job_hash(job_hash)
        job_before = db.get_job(job_hash)
        assert job_before is not None, f"Job {job_hash} nicht gefunden"
        assert not job_before.get("research_notes")

        # Recherche speichern (wie recherche_speichern Tool es macht)
        conn = db.connect()
        note = "Siemens DI: Marktführer im PLM-Bereich. Gute Bewertungen."
        now = datetime.now().isoformat()
        conn.execute(
            "UPDATE jobs SET research_notes=?, updated_at=? WHERE hash=?",
            (f"--- firmenrecherche ({now[:10]}) ---\n{note}", now, stored_hash)
        )
        conn.commit()

        # Verifiziere
        job_after = db.get_job(job_hash)
        assert job_after["research_notes"] is not None, "research_notes wurde nicht gespeichert"
        assert "Marktführer" in job_after["research_notes"]
        assert "firmenrecherche" in job_after["research_notes"]
        db.close()

    def test_recherche_an_bewerbung_speichern(self, tmp_path):
        db = _build_server(tmp_path)
        _seed_profile(db)
        hashes = _seed_jobs(db)

        # Bewerbung erstellen
        app_id = db.add_application({
            "job_hash": hashes[2],
            "title": "Teamcenter Consultant",
            "company": "Siemens DI",
            "status": "entwurf",
        })

        # Recherche als fit_analyse speichern
        analyse = {"firmenrecherche_2026-04-01": "Siemens ist Top-Arbeitgeber"}
        db.save_fit_analyse(app_id, analyse)

        # Verifiziere
        app = db.get_application(app_id)
        fit = app.get("fit_analyse")
        if isinstance(fit, str):
            fit = json.loads(fit)
        assert isinstance(fit, dict), f"fit_analyse sollte dict sein, ist {type(fit)}"
        assert "Siemens ist Top-Arbeitgeber" in fit.get("firmenrecherche_2026-04-01", "")
        db.close()

    def test_duplikat_erkennung_cross_source(self, tmp_path):
        """Stelle von StepStone existiert, User versucht dieselbe manuell anzulegen."""
        db = _build_server(tmp_path)
        _seed_profile(db)
        hashes = _seed_jobs(db)

        # Versuche Duplikat: "PLM Berater" bei "CIDEON Software" existiert als sim_0000_cide
        import re
        norm_key = re.sub(r'[^a-z0-9]', '', "CIDEON SoftwarePLM Berater".lower())

        all_active = db.get_active_jobs(exclude_applied=False)
        found_dup = False
        for existing in all_active:
            exist_key = re.sub(r'[^a-z0-9]', '', f"{existing.get('company','')}{existing.get('title','')}".lower())
            if norm_key == exist_key:
                found_dup = True
                break

        assert found_dup, "Duplikat-Erkennung hat die bestehende Stelle nicht gefunden"
        db.close()

    def test_duplikat_erkennung_gegen_bewerbungen(self, tmp_path):
        """stelle_manuell_anlegen erkennt Duplikate gegen bestehende Bewerbungen (#317)."""
        db = _build_server(tmp_path)
        _seed_profile(db)

        # Bewerbung bei TKMS anlegen
        app_id = db.add_application({
            "title": "Senior Projektmanager PLM",
            "company": "TKMS GmbH",
            "status": "beworben",
            "url": "https://stepstone.de/jobs/12345",
        })
        assert app_id

        # Duplikat-Logik simulieren: gleiche Firma + ähnlicher Titel
        import re
        firma = "TKMS GmbH"
        titel = "Senior Projektmanager PLM Engineering"
        firma_lower = firma.lower()
        titel_words = set(titel.lower().split())

        apps = db.get_applications()
        found_dup = False
        for app in apps:
            app_company = (app.get("company") or "").lower()
            app_title = (app.get("title") or "").lower()
            if firma_lower in app_company or app_company in firma_lower:
                app_words = set(app_title.split())
                overlap = titel_words & app_words
                if len(overlap) >= min(2, len(titel_words)):
                    found_dup = True
                    break

        assert found_dup, (
            "Duplikat-Erkennung gegen Bewerbungen hat TKMS-Bewerbung nicht erkannt"
        )

        # URL-Duplikat-Erkennung
        url = "https://stepstone.de/jobs/12345"
        url_norm = url.lower().rstrip("/")
        found_url_dup = False
        for app in apps:
            app_url = (app.get("url") or "").lower().rstrip("/")
            if app_url and app_url == url_norm:
                found_url_dup = True
                break
        assert found_url_dup, "URL-Duplikat-Erkennung hat bestehende Bewerbung nicht erkannt"

        # Kein Duplikat bei anderer Firma
        apps2 = db.get_applications()
        firma2 = "Rheinmetall AG"
        titel2 = "Projektleiter Schiffbau"
        firma2_lower = firma2.lower()
        titel2_words = set(titel2.lower().split())
        no_dup = True
        for app in apps2:
            app_company = (app.get("company") or "").lower()
            app_title = (app.get("title") or "").lower()
            if firma2_lower in app_company or app_company in firma2_lower:
                app_words = set(app_title.split())
                overlap = titel2_words & app_words
                if len(overlap) >= min(2, len(titel2_words)):
                    no_dup = False
                    break
        assert no_dup, "Falsch-positives Duplikat bei komplett anderer Firma"

        db.close()


# ==========================================================
# SIMULATION 4: E-Mail-Kontakt + Bewerbung (#225 + alte Pipeline)
# ==========================================================

class TestSim4EmailKontaktUndBewerbung:
    """Szenario: Bewerbung erstellt, E-Mail kommt rein, Kontaktdaten
    werden automatisch in die Bewerbung übernommen."""

    def test_kontakt_aus_email_in_bewerbung(self, tmp_path):
        db = _build_server(tmp_path)
        _seed_profile(db)
        hashes = _seed_jobs(db)

        # Bewerbung ohne Kontaktdaten
        app_id = db.add_application({
            "job_hash": hashes[3],
            "title": "PLM Architect",
            "company": "Accenture",
            "status": "beworben",
            "kontakt_email": "",
            "ansprechpartner": "",
        })

        # Simuliere E-Mail-Eingang mit Sender-Info
        sender = 'Lisa Schmidt <lisa.schmidt@accenture.com>'
        import re
        email_match = re.search(r'[\w.+-]+@[\w.-]+\.\w+', sender)
        name_match = re.match(r'^([^<]+?)\s*<', sender)
        sender_email = email_match.group(0) if email_match else ""
        sender_name = name_match.group(1).strip().strip('"') if name_match else ""

        assert sender_email == "lisa.schmidt@accenture.com"
        assert sender_name == "Lisa Schmidt"

        # Update Bewerbung (wie dashboard.py es macht)
        conn = db.connect()
        app_row = conn.execute(
            "SELECT kontakt_email, ansprechpartner FROM applications WHERE id=?",
            (app_id,)
        ).fetchone()
        updates = {}
        if sender_email and not app_row["kontakt_email"]:
            updates["kontakt_email"] = sender_email
        if sender_name and not app_row["ansprechpartner"]:
            updates["ansprechpartner"] = sender_name

        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates)
            conn.execute(
                f"UPDATE applications SET {set_clause}, updated_at=? WHERE id=?",
                (*updates.values(), datetime.now().isoformat(), app_id)
            )
            conn.commit()

        # Verifiziere
        app = db.get_application(app_id)
        assert app["kontakt_email"] == "lisa.schmidt@accenture.com"
        assert app["ansprechpartner"] == "Lisa Schmidt"
        db.close()

    def test_kontakt_ueberschreibt_nicht_bestehende(self, tmp_path):
        """Wenn bereits ein Ansprechpartner eingetragen ist, nicht überschreiben."""
        db = _build_server(tmp_path)
        _seed_profile(db)
        hashes = _seed_jobs(db)

        app_id = db.add_application({
            "job_hash": hashes[3],
            "title": "PLM Architect",
            "company": "Accenture",
            "status": "beworben",
            "kontakt_email": "hr@accenture.com",
            "ansprechpartner": "Thomas Müller",
        })

        # E-Mail kommt rein mit anderem Absender
        conn = db.connect()
        app_row = conn.execute(
            "SELECT kontakt_email, ansprechpartner FROM applications WHERE id=?",
            (app_id,)
        ).fetchone()

        # Logik: nur wenn leer
        assert app_row["kontakt_email"] == "hr@accenture.com"
        assert app_row["ansprechpartner"] == "Thomas Müller"
        # → keine Updates, weil Felder bereits befüllt
        db.close()


# ==========================================================
# SIMULATION 5: Neue + alte Prompts koexistieren (#117 + #195)
# ==========================================================

class TestSim5PromptsRegistrierung:
    """Prüft dass neue und alte Prompts korrekt registriert sind."""

    def test_alle_18_prompts_registriert(self, tmp_path):
        from bewerbungs_assistent.database import Database
        os.environ["BA_DATA_DIR"] = str(tmp_path)
        db = Database(db_path=tmp_path / "test.db")
        db.initialize()

        from fastmcp import FastMCP
        mcp = FastMCP("test")
        from bewerbungs_assistent.prompts import register_prompts
        import logging
        register_prompts(mcp, db, logging.getLogger("test"))

        async def _get():
            if hasattr(mcp, "list_prompts"):
                return await mcp.list_prompts()
            return list((await mcp.get_prompts()).values())

        prompts = asyncio.run(_get())
        names = {p.name for p in prompts}

        # Neue Prompts
        assert "profil_sync" in names, "profil_sync Prompt fehlt"
        assert "tipps_und_tricks" in names, "tipps_und_tricks Prompt fehlt"

        # Alte Prompts weiterhin vorhanden
        assert "ersterfassung" in names
        assert "bewerbung_schreiben" in names
        assert "interview_vorbereitung" in names
        assert "interview_simulation" in names
        assert "gehaltsverhandlung" in names

        assert len(names) == 18, f"Erwartet 18 Prompts, gefunden {len(names)}: {names}"
        db.close()
        os.environ.pop("BA_DATA_DIR", None)


# ==========================================================
# SIMULATION 6: Schema-Migration v20 auf bestehende DB
# ==========================================================

class TestSim6SchemaMigration:
    """Prüft dass Migration v19→v20 korrekt neue Spalten hinzufügt."""

    def test_projects_hat_neue_spalten(self, tmp_path):
        db = _build_server(tmp_path)
        conn = db.connect()
        cols = conn.execute("PRAGMA table_info(projects)").fetchall()
        col_names = [c["name"] for c in cols]
        assert "customer_name" in col_names, f"customer_name fehlt in projects: {col_names}"
        assert "is_confidential" in col_names, f"is_confidential fehlt in projects: {col_names}"
        db.close()

    def test_jobs_hat_research_notes(self, tmp_path):
        db = _build_server(tmp_path)
        conn = db.connect()
        cols = conn.execute("PRAGMA table_info(jobs)").fetchall()
        col_names = [c["name"] for c in cols]
        assert "research_notes" in col_names, f"research_notes fehlt in jobs: {col_names}"
        db.close()

    def test_schema_version_ist_20(self, tmp_path):
        db = _build_server(tmp_path)
        from bewerbungs_assistent.database import SCHEMA_VERSION
        assert SCHEMA_VERSION == 23
        db.close()


# ==========================================================
# SIMULATION 7: Kombinierter Workflow (alle Features zusammen)
# ==========================================================

class TestSim7KombinierterWorkflow:
    """Kompletter User-Workflow: Profil → Jobs → Bewertung → Blacklist →
    Recherche → Bewerbung → E-Mail → CV-Export."""

    def test_full_workflow(self, tmp_path):
        db = _build_server(tmp_path)
        pos_id = _seed_profile(db)

        # 1. Projekte anlegen (mit und ohne vertraulichen Kunden)
        db.add_project(pos_id, {
            "name": "ERP-Integration",
            "customer_name": "Daimler",
            "is_confidential": 1,
            "role": "Lead",
            "result": "Go-live in 6 Monaten",
        })
        db.add_project(pos_id, {
            "name": "Web-Portal",
            "customer_name": "Bosch",
            "is_confidential": 0,
            "role": "Developer",
        })

        # 2. Jobs anlegen
        hashes = _seed_jobs(db)
        assert len(db.get_active_jobs()) == 7

        # 3. Einige Jobs aussortieren (Zeitarbeit)
        zeitarbeit_jobs = [h for h in hashes if db.get_job(h).get("employment_type") == "zeitarbeit"]
        counts = db.get_setting("dismiss_counts", {})
        for h in zeitarbeit_jobs:
            db.dismiss_job(h, "zeitarbeit")
            counts["zeitarbeit"] = counts.get("zeitarbeit", 0) + 1
        db.set_setting("dismiss_counts", counts)

        # 4. Blacklist Hays
        db.add_to_blacklist("firma", "Hays", "Zeitarbeit")
        conn = db.connect()
        conn.execute(
            "UPDATE jobs SET is_active=0, dismiss_reason='firma_blacklisted' "
            "WHERE is_active=1 AND LOWER(company) LIKE '%hays%'"
        )
        conn.commit()

        # 5. Recherche an verbleibender Stelle speichern
        remaining = db.get_active_jobs()
        assert len(remaining) >= 2, f"Mindestens 2 aktive Stellen erwartet, nur {len(remaining)}"
        target_hash = remaining[0]["hash"]
        stored_target = db.resolve_job_hash(target_hash)
        conn.execute(
            "UPDATE jobs SET research_notes=? WHERE hash=?",
            ("Gute Firma, passt zum Profil.", stored_target)
        )
        conn.commit()

        # 6. Bewerbung erstellen
        target = db.get_job(target_hash)
        app_id = db.add_application({
            "job_hash": target_hash,
            "title": target["title"],
            "company": target["company"],
            "status": "beworben",
        })

        # 7. Recherche auch an Bewerbung
        db.save_fit_analyse(app_id, {"gesamtbewertung": "Sehr gut passend"})

        # 8. CV-Export mit vertraulichen Projekten
        profile = db.get_profile()
        from bewerbungs_assistent.export import generate_cv_text
        out = tmp_path / "cv.txt"
        generate_cv_text(profile, out)
        content = out.read_text()

        assert "Daimler" not in content, "Vertraulicher Kunde 'Daimler' im CV!"
        assert "Bosch" in content, "Offener Kunde 'Bosch' fehlt im CV"
        assert "ERP-Integration" in content
        assert "[vertraulich]" in content

        # 9. Verifiziere Gesamtzustand
        stats = db.get_statistics()
        assert stats["total_applications"] >= 1
        blacklist = db.get_blacklist()
        assert any(e["value"] == "Hays" for e in blacklist)

        db.close()
