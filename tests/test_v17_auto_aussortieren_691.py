"""Regression #691: stellen_auto_aussortieren.

Teil 2 (hier testbar ohne Ollama): die LLM-Antwort-Begruendung darf nie den
Prompt-Platzhalter 'KURZBEGRUENDUNG' (oder leere Werte) als echte Begruendung
durchreichen.

Teil 1 (Schema-Konformitaet bei Fehler/Timeout) ist durch
test_v170_beta46_bug_sweep::test_610_uniform_output_schema_on_error abgedeckt
sowie durch das auf 50s gesenkte Wall-Clock-Budget (unter dem ~60s-Client-
Timeout), das vor einem Cancel ein schemakonformes status='teilweise' liefert.
"""


def test_691_clean_match_reason_strips_placeholder():
    from bewerbungs_assistent.services.llm_service import _clean_match_reason
    # Prompt-Platzhalter und Varianten -> leer
    assert _clean_match_reason("KURZBEGRUENDUNG") == ""
    assert _clean_match_reason("kurzbegrundung") == ""
    assert _clean_match_reason("  KURZBEGRÜNDUNG. ") == ""
    assert _clean_match_reason("Begruendung") == ""
    assert _clean_match_reason("") == ""
    assert _clean_match_reason("   ") == ""
    # Echte Begruendung bleibt erhalten (auf 200 Zeichen begrenzt)
    assert _clean_match_reason("Passt thematisch, PLM-Bezug") == "Passt thematisch, PLM-Bezug"
    assert len(_clean_match_reason("x" * 500)) == 200


def test_691_parse_does_not_leak_placeholder():
    from bewerbungs_assistent.services.llm_service import _parse_match_job_to_skills
    parsed = _parse_match_job_to_skills("PASST | KURZBEGRUENDUNG")
    assert parsed["decision"] == "PASST"
    assert parsed["reason"] == ""

    parsed2 = _parse_match_job_to_skills("PASST_NICHT | Falsche Branche, kein PLM-Bezug")
    assert parsed2["decision"] == "PASST_NICHT"
    assert parsed2["reason"] == "Falsche Branche, kein PLM-Bezug"
