from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.provider_tools import (  # type: ignore
    get_eap_rule_results_envelope,
    load_eap_sidecar_envelope,
    parse_allowlist_env,
    search_eap_commands_envelope,
    sidecar_load_error_to_envelope,
    summarize_eap_sidecar_envelope,
)
from providers import SidecarLoadError  # type: ignore


REPO_ROOT = ROOT.parents[1]
FULLISH_FIXTURE = REPO_ROOT / "tools" / "eap_validator" / "fixtures" / "valid_fullish.rmeta.json"


def _sidecar(**extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema": {"name": "EngineAnnotationProtocol", "version": 1},
        "capture": {"id": "cap:eap"},
        "render_graph": {"nodes": [{"id": "pass:main"}]},
        "commands": [{"id": "cmd:1"}],
        "resources": [{"id": "res:1"}],
    }
    payload.update(extra)
    return payload


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_eap_sidecar_envelope_returns_summary_and_data_availability(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.rmeta.json", _sidecar())

    envelope = load_eap_sidecar_envelope(
        str(sidecar_path),
        allowlist_dirs=[str(tmp_path)],
    )

    assert envelope["ok"] is True
    assert envelope["contract_version"] == "mcp-query.v1"
    assert envelope["method"] == "load_eap_sidecar"
    assert envelope["source"] == "provider_readonly"
    assert envelope["data"]["sidecar"]["capture_id"] == "cap:eap"
    assert envelope["data"]["sidecar"]["schema_name"] == "EngineAnnotationProtocol"
    assert envelope["data"]["sidecar"]["path"] == str(sidecar_path.resolve())
    assert "payload" not in envelope["data"]["sidecar"]
    assert envelope["data"]["data_availability"]["providers"]["eap_sidecar"]["available"] is True


def test_load_eap_sidecar_envelope_requires_allowlist(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.rmeta.json", _sidecar())

    envelope = load_eap_sidecar_envelope(str(sidecar_path), allowlist_dirs=[])

    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "invalid_argument"
    assert envelope["error"]["details"]["sidecar_code"] == "not_allowed"
    assert "allowlist" in envelope["recovery_hint"].lower()


def test_summarize_eap_sidecar_envelope_consumes_synthetic_fixture():
    envelope = summarize_eap_sidecar_envelope(
        str(FULLISH_FIXTURE),
        allowlist_dirs=[str(FULLISH_FIXTURE.parent)],
    )

    assert envelope["ok"] is True
    assert envelope["method"] == "summarize_eap_sidecar"
    assert envelope["source"] == "provider_readonly"
    assert envelope["data"]["summary"]["capture_id"] == "cap:fixture:fullish"
    assert envelope["data"]["counts"] == {
        "render_graph_nodes": 2,
        "commands": 2,
        "resources": 1,
        "assets": 1,
        "materials": 1,
        "shaders": 2,
        "pipelines": 1,
        "rule_results": 2,
    }
    assert envelope["data"]["validation_scope"] == "synthetic_fixture_or_explicit_sidecar_only"
    assert "payload" not in envelope["data"]["summary"]


def test_search_eap_commands_envelope_filters_synthetic_fixture_by_pass_and_resource():
    by_pass = search_eap_commands_envelope(
        str(FULLISH_FIXTURE),
        pass_id="pass:base_opaque",
        allowlist_dirs=[str(FULLISH_FIXTURE.parent)],
    )
    by_resource = search_eap_commands_envelope(
        str(FULLISH_FIXTURE),
        resource_id="res:color",
        allowlist_dirs=[str(FULLISH_FIXTURE.parent)],
    )

    assert by_pass["ok"] is True
    assert by_pass["method"] == "search_eap_commands"
    assert by_pass["data"]["match_count"] == 1
    assert by_pass["data"]["items"][0]["id"] == "cmd:1"
    assert by_pass["data"]["items"][0]["matched_by"] == ["pass_id"]
    assert by_resource["data"]["match_count"] == 1
    assert by_resource["data"]["items"][0]["resource_ids"] == ["res:color"]


def test_get_eap_rule_results_envelope_filters_synthetic_fixture_by_severity():
    envelope = get_eap_rule_results_envelope(
        str(FULLISH_FIXTURE),
        severity="warning",
        allowlist_dirs=[str(FULLISH_FIXTURE.parent)],
    )

    assert envelope["ok"] is True
    assert envelope["method"] == "get_eap_rule_results"
    assert envelope["data"]["result_count"] == 1
    assert envelope["data"]["items"] == [{"id": "rule:fixture:warning", "severity": "warning"}]


def test_sidecar_load_error_to_envelope_preserves_sidecar_error_code():
    exc = SidecarLoadError("invalid_extension", "Sidecar path must end with .rmeta.json", "bad.json")

    envelope = sidecar_load_error_to_envelope(
        exc,
        method="load_eap_sidecar",
        params={"path": "bad.json"},
    )

    assert envelope["ok"] is False
    assert envelope["error"]["code"] == "invalid_argument"
    assert envelope["error"]["details"]["sidecar_code"] == "invalid_extension"
    assert envelope["error"]["details"]["path"].endswith("bad.json")


def test_parse_allowlist_env_uses_os_path_separator(tmp_path: Path):
    left = tmp_path / "left"
    right = tmp_path / "right"
    raw = f"{left}{__import__('os').pathsep}{right}"

    assert parse_allowlist_env({"RENDERDOC_EAP_SIDECAR_ALLOWLIST": raw}) == [str(left), str(right)]
