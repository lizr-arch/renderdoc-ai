from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict

import pytest


ROOT = Path(__file__).resolve().parents[3]
VALIDATOR_DIR = ROOT / "tools" / "eap_validator"
if str(VALIDATOR_DIR) not in sys.path:
    sys.path.insert(0, str(VALIDATOR_DIR))

import eap_validator  # type: ignore


def _sidecar(**extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema": {"name": "EngineAnnotationProtocol", "version": 1},
        "capture": {"id": "cap:eap"},
        "commands": [{"id": "cmd:1"}, {"id": "cmd:2"}],
        "resources": [{"id": "res:1"}],
        "rules": {"results": [{"id": "rule:1", "severity": "warning"}]},
    }
    payload.update(extra)
    return payload


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_validate_sidecar_returns_deterministic_json_summary(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.rmeta.json", _sidecar())

    result = eap_validator.validate_sidecar(str(sidecar_path))

    assert result["ok"] is True
    assert result["schema_version"] == "eap-validator.v1"
    assert result["sidecar"]["path"] == str(sidecar_path.resolve(strict=False))
    assert result["sidecar"]["schema_name"] == "EngineAnnotationProtocol"
    assert result["sidecar"]["schema_version"] == 1
    assert result["sidecar"]["capture_id"] == "cap:eap"
    assert result["sidecar"]["counts"] == {
        "render_graph_nodes": 0,
        "commands": 2,
        "resources": 1,
        "assets": 0,
        "materials": 0,
        "shaders": 0,
        "pipelines": 0,
        "rule_results": 1,
    }
    assert result["sidecar"]["capabilities"] == [
        "eap_schema",
        "commands",
        "resources",
        "rules",
    ]
    assert result["error"] is None


def test_validate_sidecar_preserves_invalid_extension_error(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.json", _sidecar())

    result = eap_validator.validate_sidecar(str(sidecar_path))

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_extension"
    assert result["error"]["path"] == str(sidecar_path.resolve(strict=False))
    assert result["sidecar"] is None


def test_validate_sidecar_preserves_invalid_json_error(tmp_path: Path):
    sidecar_path = tmp_path / "capture.rmeta.json"
    sidecar_path.write_text("{not json", encoding="utf-8")

    result = eap_validator.validate_sidecar(str(sidecar_path))

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_json"


def test_validate_sidecar_preserves_invalid_eap_shape_error(tmp_path: Path):
    sidecar_path = _write_json(
        tmp_path / "capture.rmeta.json",
        {"schema": {"name": "OtherProtocol"}, "unrelated": True},
    )

    result = eap_validator.validate_sidecar(str(sidecar_path))

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_sidecar"


def test_validate_sidecar_enforces_allowlist_when_supplied(tmp_path: Path):
    allowed_dir = tmp_path / "allowed"
    outside_dir = tmp_path / "outside"
    allowed_dir.mkdir()
    outside_dir.mkdir()
    allowed_path = _write_json(allowed_dir / "capture.rmeta.json", _sidecar(capture={"id": "cap:allowed"}))
    outside_path = _write_json(outside_dir / "capture.rmeta.json", _sidecar(capture={"id": "cap:outside"}))

    allowed_result = eap_validator.validate_sidecar(str(allowed_path), allowlist_dirs=[str(allowed_dir)])
    outside_result = eap_validator.validate_sidecar(str(outside_path), allowlist_dirs=[str(allowed_dir)])

    assert allowed_result["ok"] is True
    assert allowed_result["sidecar"]["capture_id"] == "cap:allowed"
    assert outside_result["ok"] is False
    assert outside_result["error"]["code"] == "not_allowed"


def test_format_human_summary_is_concise(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.rmeta.json", _sidecar())
    result = eap_validator.validate_sidecar(str(sidecar_path))

    summary = eap_validator.format_human_summary(result)

    assert "OK: capture.rmeta.json" in summary
    assert "capture_id: cap:eap" in summary
    assert "commands=2" in summary
    assert "rule_results=1" in summary
    assert "capabilities: eap_schema, commands, resources, rules" in summary


def test_cli_json_output_is_machine_readable(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.rmeta.json", _sidecar())

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "eap_validator" / "eap_validator.py"),
            "validate",
            str(sidecar_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["sidecar"]["capture_id"] == "cap:eap"
    assert completed.stderr == ""


def test_cli_returns_nonzero_for_validation_errors(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.json", _sidecar())

    completed = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "eap_validator" / "eap_validator.py"),
            "validate",
            str(sidecar_path),
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    payload = json.loads(completed.stdout)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_extension"


def test_cli_tolerates_preloaded_rdc_analyzer_providers_module(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.rmeta.json", _sidecar())
    script = (
        "import runpy, sys; "
        f"sys.path.insert(0, {str(ROOT / 'scripts' / 'rdc_analyzer')!r}); "
        "import providers; "
        f"sys.argv = [{str(ROOT / 'tools' / 'eap_validator' / 'eap_validator.py')!r}, "
        f"'validate', {str(sidecar_path)!r}, '--json']; "
        f"runpy.run_path({str(ROOT / 'tools' / 'eap_validator' / 'eap_validator.py')!r}, run_name='__main__')"
    )

    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 0
    payload = json.loads(completed.stdout)
    assert payload["ok"] is True
    assert payload["sidecar"]["capture_id"] == "cap:eap"
