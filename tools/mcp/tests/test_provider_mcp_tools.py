from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.provider_tools import (  # type: ignore
    load_eap_sidecar_envelope,
    parse_allowlist_env,
    sidecar_load_error_to_envelope,
)
from providers import SidecarLoadError  # type: ignore


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
