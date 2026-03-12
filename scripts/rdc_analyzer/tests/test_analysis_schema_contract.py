from pathlib import Path
import json


SCHEMA_DOC = Path("docs/analysis/codex_rdc_analyzer/analysis_report_schema_v1.md")
SCHEMA_JSON = Path("scripts/rdc_analyzer/schema/analysis_schema_v1.json")
INDEX_DOC = Path("scripts/rdc_analyzer/docs/INDEX.md")


def test_schema_doc_exists() -> None:
    assert SCHEMA_DOC.exists()


def test_schema_doc_has_extraction_map() -> None:
    assert SCHEMA_DOC.exists()
    text = SCHEMA_DOC.read_text(encoding="utf-8")
    assert "Extraction Map" in text


def test_schema_doc_has_page_structure() -> None:
    assert SCHEMA_DOC.exists()
    text = SCHEMA_DOC.read_text(encoding="utf-8")
    assert "Page Structure" in text


def test_schema_json_minimal_keys() -> None:
    assert SCHEMA_JSON.exists()
    data = json.loads(SCHEMA_JSON.read_text(encoding="utf-8"))
    required = {
        "schema_version",
        "summary",
        "events",
        "textures",
        "shaders",
        "passes",
        "pipeline_state",
        "uniforms",
    }
    missing = required - set(data.keys())
    assert not missing


def test_docs_index_links_schema() -> None:
    text = INDEX_DOC.read_text(encoding="utf-8")
    assert "analysis_report_schema_v1.md" in text
