from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mcp_server.provider_readonly_server import create_mcp_server  # type: ignore


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
    assert set(server.tools) == {"get_data_availability", "load_eap_sidecar"}


def test_registered_load_eap_sidecar_requires_env_allowlist(tmp_path: Path):
    server = create_mcp_server(fastmcp_cls=FakeFastMCP, env={})
    sidecar_path = tmp_path / "capture.rmeta.json"
    sidecar_path.write_text("{}", encoding="utf-8")

    payload = server.tools["load_eap_sidecar"](str(sidecar_path))

    assert payload["ok"] is False
    assert payload["error"]["details"]["sidecar_code"] == "not_allowed"
