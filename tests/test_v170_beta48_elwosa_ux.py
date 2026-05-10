"""Tests fuer v1.7.0-beta.48 — Elwosa UX-Polish (#611)."""
from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SIDEBAR_CHAT = PROJECT_ROOT / "frontend" / "src" / "components" / "ElwosaSidebarChat.jsx"
APP_JSX = PROJECT_ROOT / "frontend" / "src" / "App.jsx"


def test_auto_scroll_uses_useLayoutEffect():
    """Auto-Scroll muss synchron mit DOM-Update passieren — useEffect
    waere zu spaet, der User wuerde flickern."""
    src = SIDEBAR_CHAT.read_text(encoding="utf-8")
    assert "useLayoutEffect" in src
    assert "scrollRef" in src
    assert "scrollTop = el.scrollHeight" in src or "scrollTop = " in src


def test_sticky_bottom_detection():
    """Wenn User aktiv hochscrollt: stickyRef = false, kein Auto-Scroll."""
    src = SIDEBAR_CHAT.read_text(encoding="utf-8")
    assert "stickyRef" in src
    assert "distanceFromBottom" in src
    assert "atBottom" in src


def test_jump_to_bottom_button_with_unread_count():
    """Indicator-Button erscheint wenn User oben + neue Nachricht."""
    src = SIDEBAR_CHAT.read_text(encoding="utf-8")
    assert "showJumpToBottom" in src
    assert "unreadBelow" in src
    assert "jumpToBottom" in src
    # Indicator-Button muss klickbar sein
    assert "onClick={jumpToBottom}" in src


def test_adaptive_height_replaces_fixed_max_height():
    """min-h-[150px] und max-h-[60vh] (oder vergleichbar) statt
    starrem max-h-[260px]."""
    src = SIDEBAR_CHAT.read_text(encoding="utf-8")
    # Alte fixe Hoehe darf nicht mehr da sein im scrollbaren Container
    assert "min-h-[150px]" in src
    assert "60vh" in src or "70vh" in src or "500px" in src or "600px" in src


def test_action_link_routing_in_app_jsx():
    """App.jsx hat onNavigate-Handler fuer alle 4 Action-Link-Typen."""
    src = APP_JSX.read_text(encoding="utf-8")
    # Alle 4 Action-Link-Typen werden geroutet
    for link_type in ("application", "job", "job_filter", "page"):
        assert f'linkType === "{link_type}"' in src, (
            f"Action-Link-Routing fuer '{link_type}' fehlt in App.jsx"
        )


def test_application_link_navigates_with_intent():
    src = APP_JSX.read_text(encoding="utf-8")
    assert 'navigateTo("bewerbungen", { applicationId: linkId })' in src


def test_job_filter_missing_desc_routes_correctly():
    src = APP_JSX.read_text(encoding="utf-8")
    assert "missing_desc" in src
    assert "missingDescriptionOnly: true" in src


def test_status_change_lines_use_action_links():
    """STATUS_CHANGE_LINES haben jetzt Action-Links auf {ref}."""
    from bewerbungs_assistent.services.elwosa_lines import STATUS_CHANGE_LINES
    # Mind. eine Linie pro relevanter Trigger-Klasse mit application-Link
    for trigger in ("absage", "interview_einladung", "angenommen",
                     "bewerbung_angelegt"):
        has_link = any(
            "[link:application:{ref}" in line
            for line in STATUS_CHANGE_LINES.get(trigger, [])
        )
        assert has_link, (
            f"STATUS_CHANGE_LINES['{trigger}'] hat keine Action-Link-Variante"
        )


def test_fill_template_supports_ref_variable():
    """{ref} muss von fill_template ersetzt werden."""
    from bewerbungs_assistent.services.elwosa import fill_template
    line = "Markiert. [link:application:{ref}|oeffnen]."
    out = fill_template(line, {"ref": "abc123"})
    assert "abc123" in out
    assert "{ref}" not in out


def test_status_change_link_lines_pass_validator():
    """Mit ref-Variable gefuellt sollten alle Linien Sprach-DNA-konform sein."""
    from bewerbungs_assistent.services.elwosa import validate_tonfall, fill_template
    from bewerbungs_assistent.services.elwosa_lines import STATUS_CHANGE_LINES
    for trigger, lines in STATUS_CHANGE_LINES.items():
        for line in lines:
            filled = fill_template(line, {"firma": "ACME", "ref": "abc12345"})
            try:
                validate_tonfall(filled)
            except Exception as e:
                raise AssertionError(f"{trigger}: {e} -- {filled}")
