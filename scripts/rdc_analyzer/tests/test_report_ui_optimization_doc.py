from pathlib import Path


DOC = Path("docs/analysis/codex_rdc_analyzer/report_ui_optimization_v1.md")
INDEX = Path("scripts/rdc_analyzer/docs/INDEX.md")
WEBUI = Path("scripts/rdc_analyzer/docs/WEBUI_AND_UI_EXTENSION.md")


def test_doc_exists() -> None:
    assert DOC.exists()


def test_index_links_doc() -> None:
    text = INDEX.read_text(encoding="utf-8")
    assert "report_ui_optimization_v1.md" in text


def test_webui_links_doc() -> None:
    text = WEBUI.read_text(encoding="utf-8")
    assert "report_ui_optimization_v1.md" in text
