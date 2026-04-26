from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.provider_readonly_server import create_mcp_server  # type: ignore


REPO_ROOT = ROOT.parents[1]
FULLISH_FIXTURE = REPO_ROOT / "tools" / "eap_validator" / "fixtures" / "valid_fullish.rmeta.json"


class FakeFastMCP:
    def __init__(self, name: str, instructions: str = ""):
        self.name = name
        self.instructions = instructions
        self.tools = {}

    def tool(self):
        def decorator(func):
            self.tools[func.__name__] = func
            return func

        return decorator


def test_create_mcp_server_registers_readonly_provider_tools():
    server = create_mcp_server(fastmcp_cls=FakeFastMCP, env={})

    assert server.name == "RenderDoc Provider Readonly"
    assert "read-only" in server.instructions.lower()
    assert set(server.tools) == {
        "get_data_availability",
        "get_eap_rule_results",
        "load_eap_sidecar",
        "search_eap_commands",
        "summarize_eap_sidecar",
    }


def test_registered_load_eap_sidecar_requires_env_allowlist(tmp_path: Path):
    server = create_mcp_server(fastmcp_cls=FakeFastMCP, env={})
    sidecar_path = tmp_path / "capture.rmeta.json"
    sidecar_path.write_text("{}", encoding="utf-8")

    payload = server.tools["load_eap_sidecar"](str(sidecar_path))

    assert payload["ok"] is False
    assert payload["error"]["details"]["sidecar_code"] == "not_allowed"


def test_registered_consumption_tools_use_synthetic_fixture_with_allowlist():
    server = create_mcp_server(
        fastmcp_cls=FakeFastMCP,
        env={"RENDERDOC_EAP_SIDECAR_ALLOWLIST": str(FULLISH_FIXTURE.parent)},
    )

    summary = server.tools["summarize_eap_sidecar"](str(FULLISH_FIXTURE))
    search = server.tools["search_eap_commands"](str(FULLISH_FIXTURE), pass_id="pass:post")
    rules = server.tools["get_eap_rule_results"](str(FULLISH_FIXTURE), severity="info")

    assert summary["ok"] is True
    assert summary["data"]["summary"]["capture_id"] == "cap:fixture:fullish"
    assert search["ok"] is True
    assert search["data"]["items"][0]["id"] == "cmd:2"
    assert rules["ok"] is True
    assert rules["data"]["items"] == [{"id": "rule:fixture:ok", "severity": "info"}]
