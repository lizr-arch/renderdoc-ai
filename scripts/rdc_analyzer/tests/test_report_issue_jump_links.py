from pathlib import Path


def test_issue_export_links_present() -> None:
    index_html = Path("scripts/rdc_analyzer/templates/index.html").read_text(encoding="utf-8")
    events_html = Path("scripts/rdc_analyzer/templates/events.html").read_text(encoding="utf-8")
    shaders_html = Path("scripts/rdc_analyzer/templates/shaders.html").read_text(encoding="utf-8")
    textures_html = Path("scripts/rdc_analyzer/templates/textures.html").read_text(encoding="utf-8")

    assert "issues_export.json" in index_html
    assert "issues_export.json" in events_html
    assert "issues_export.json" in shaders_html
    assert "issues_export.json" in textures_html


def test_issue_jump_buttons_present() -> None:
    events_html = Path("scripts/rdc_analyzer/templates/events.html").read_text(encoding="utf-8")
    shaders_html = Path("scripts/rdc_analyzer/templates/shaders.html").read_text(encoding="utf-8")
    textures_html = Path("scripts/rdc_analyzer/templates/textures.html").read_text(encoding="utf-8")

    assert "jumpToRenderDoc(" in events_html
    assert "jumpToRenderDoc(" in shaders_html
    assert "jumpToRenderDoc(" in textures_html


def test_quality_panel_placeholders_present() -> None:
    index_html = Path("scripts/rdc_analyzer/templates/index.html").read_text(encoding="utf-8")
    assert "数据可信度" in index_html
    assert "{{QUALITY_LEVEL}}" in index_html
    assert "{{PREFLIGHT_STATUS}}" in index_html
