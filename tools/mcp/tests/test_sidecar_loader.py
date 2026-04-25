from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict

import pytest


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers import (  # type: ignore
    ProviderContext,
    SidecarLoadError,
    build_default_registry,
    load_sidecar,
)


def _sidecar(**extra: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "schema": {"name": "EngineAnnotationProtocol", "version": 1},
        "capture": {"id": "cap:eap"},
        "commands": [{"id": "cmd:1"}],
        "resources": [{"id": "res:1"}],
    }
    payload.update(extra)
    return payload


def _write_json(path: Path, payload: Any) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _assert_load_error(exc_info: pytest.ExceptionInfo[SidecarLoadError], code: str, path: Path) -> None:
    assert exc_info.value.code == code
    assert exc_info.value.path == str(path.resolve(strict=False))
    assert exc_info.value.message


def test_load_sidecar_returns_valid_rmeta_json_payload(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.rmeta.json", _sidecar())

    payload = load_sidecar(sidecar_path)

    assert payload == _sidecar()


def test_load_sidecar_rejects_non_rmeta_json_suffix(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.json", _sidecar())

    with pytest.raises(SidecarLoadError) as exc_info:
        load_sidecar(sidecar_path)

    _assert_load_error(exc_info, "invalid_extension", sidecar_path)


def test_load_sidecar_rejects_missing_path(tmp_path: Path):
    sidecar_path = tmp_path / "missing.rmeta.json"

    with pytest.raises(SidecarLoadError) as exc_info:
        load_sidecar(sidecar_path)

    _assert_load_error(exc_info, "not_found", sidecar_path)


def test_load_sidecar_rejects_directory(tmp_path: Path):
    sidecar_path = tmp_path / "directory.rmeta.json"
    sidecar_path.mkdir()

    with pytest.raises(SidecarLoadError) as exc_info:
        load_sidecar(sidecar_path)

    _assert_load_error(exc_info, "not_file", sidecar_path)


def test_load_sidecar_rejects_oversized_file_before_json_parse(tmp_path: Path):
    sidecar_path = tmp_path / "too_large.rmeta.json"
    sidecar_path.write_text("{", encoding="utf-8")

    with pytest.raises(SidecarLoadError) as exc_info:
        load_sidecar(sidecar_path, max_bytes=0)

    _assert_load_error(exc_info, "file_too_large", sidecar_path)


def test_load_sidecar_rejects_invalid_json(tmp_path: Path):
    sidecar_path = tmp_path / "invalid.rmeta.json"
    sidecar_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(SidecarLoadError) as exc_info:
        load_sidecar(sidecar_path)

    _assert_load_error(exc_info, "invalid_json", sidecar_path)


@pytest.mark.parametrize("payload", [[], "not an object", 42])
def test_load_sidecar_rejects_non_object_payloads(tmp_path: Path, payload: Any):
    sidecar_path = _write_json(tmp_path / "payload.rmeta.json", payload)

    with pytest.raises(SidecarLoadError) as exc_info:
        load_sidecar(sidecar_path)

    _assert_load_error(exc_info, "invalid_payload", sidecar_path)


def test_load_sidecar_rejects_object_that_is_not_eap_sidecar(tmp_path: Path):
    sidecar_path = _write_json(
        tmp_path / "wrong_schema.rmeta.json",
        {"schema": {"name": "OtherProtocol"}, "unrelated": True},
    )

    with pytest.raises(SidecarLoadError) as exc_info:
        load_sidecar(sidecar_path)

    _assert_load_error(exc_info, "invalid_sidecar", sidecar_path)


def test_load_sidecar_enforces_resolved_allowlist_dirs(tmp_path: Path):
    allowed_dir = tmp_path / "allowed"
    outside_dir = tmp_path / "outside"
    allowed_dir.mkdir()
    outside_dir.mkdir()
    allowed_path = _write_json(allowed_dir / "capture.rmeta.json", _sidecar(capture={"id": "cap:allowed"}))
    outside_path = _write_json(outside_dir / "capture.rmeta.json", _sidecar(capture={"id": "cap:outside"}))

    payload = load_sidecar(allowed_path, allowlist_dirs=[allowed_dir])

    assert payload["capture"]["id"] == "cap:allowed"

    escape_path = allowed_dir / ".." / outside_dir.name / outside_path.name
    with pytest.raises(SidecarLoadError) as exc_info:
        load_sidecar(escape_path, allowlist_dirs=[allowed_dir])

    _assert_load_error(exc_info, "not_allowed", escape_path)


def test_loaded_sidecar_makes_provider_registry_report_eap_available(tmp_path: Path):
    sidecar_path = _write_json(tmp_path / "capture.rmeta.json", _sidecar(render_graph={"nodes": [{"id": "pass:1"}]}))

    payload = load_sidecar(sidecar_path)
    availability = build_default_registry().data_availability(ProviderContext(eap_sidecar=payload)).as_dict()

    assert availability["capture_id"] == "cap:eap"
    assert availability["providers"]["eap_sidecar"]["available"] is True
    capability_names = {item["name"] for item in availability["providers"]["eap_sidecar"]["capabilities"]}
    assert {"eap_schema", "render_graph", "commands", "resources"} <= capability_names
