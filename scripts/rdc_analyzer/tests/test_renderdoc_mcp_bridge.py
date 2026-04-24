import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_DIR = REPO_ROOT / "scripts" / "rdc_analyzer" / "tools"
TOOLS_MCP = REPO_ROOT / "tools" / "mcp"
for path in (TOOLS_DIR, TOOLS_MCP):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import renderdoc_mcp_bridge as bridge  # type: ignore


class FakeAction:
    def __init__(
        self,
        event_id: int,
        name: str,
        flags: str = "Drawcall",
        children: Optional[List["FakeAction"]] = None,
        shader_refs: Optional[Dict[str, str]] = None,
        resource_refs: Optional[List[str]] = None,
    ) -> None:
        self.eventId = event_id
        self.name = name
        self.flags = flags
        self.children = children or []
        self.numIndices = 36
        self.numInstances = 1
        self.shader_refs = shader_refs or {}
        self.resource_refs = resource_refs or []

    def GetName(self, _structured_file: Any = None) -> str:
        return self.name


class FakeTexture:
    def __init__(self, resource_id: str, name: str = "Color") -> None:
        self.resourceId = resource_id
        self.name = name
        self.width = 128
        self.height = 64
        self.depth = 1
        self.format = "RGBA8"
        self.sampleCount = 1


class FakeBuffer:
    def __init__(self, resource_id: str, length: int = 1024) -> None:
        self.resourceId = resource_id
        self.length = length


class FakePipeline:
    graphics_api = "Vulkan"
    shaders = {"vertex": "vs-main", "pixel": "ps-main"}
    render_target_refs = ["tex-color"]
    depth_target_ref = None
    blend = {"enabled": False}
    depth_stencil = {"depthTest": True}
    rasterizer = {"cullMode": "Back"}
    vertex_layout = [{"slot": 0, "stride": 32}]

    def GetShader(self, stage: Any) -> str:
        return self.shaders.get(str(stage).lower(), "")

    def GetShaderEntryPoint(self, stage: Any) -> str:
        return "main_%s" % str(stage).lower()


class FakeController:
    def __init__(self) -> None:
        self.pipeline = FakePipeline()
        self.actions = [
            FakeAction(
                10,
                "Geometry",
                "Marker",
                [
                    FakeAction(
                        11,
                        "Draw Terrain",
                        shader_refs={"vertex": "vs-main", "pixel": "ps-main"},
                        resource_refs=["tex-color", "buf-verts"],
                    ),
                    FakeAction(12, "Dispatch Lighting", "Dispatch", resource_refs=["tex-color"]),
                ],
            )
        ]
        self.textures = [FakeTexture("tex-color")]
        self.buffers = [FakeBuffer("buf-verts", length=128)]
        self.buffer_data = bytes(range(32))
        self.frame_events: List[int] = []

    def GetRootActions(self) -> List[FakeAction]:
        return self.actions

    def GetStructuredFile(self) -> object:
        return object()

    def GetTextures(self) -> List[FakeTexture]:
        return self.textures

    def GetBuffers(self) -> List[FakeBuffer]:
        return self.buffers

    def SetFrameEvent(self, event_id: int, _force: bool) -> None:
        self.frame_events.append(event_id)

    def GetPipelineState(self) -> FakePipeline:
        return self.pipeline

    def GetBufferData(self, resource_id: str, offset: int, byte_count: int) -> bytes:
        assert resource_id == "buf-verts"
        return self.buffer_data[offset : offset + byte_count]


class FakeContext:
    def __init__(self, loaded: bool = True) -> None:
        self.loaded = loaded
        self.filename = r"D:\captures\frame.rdc"
        self.controller = FakeController()

    def IsCaptureLoaded(self) -> bool:
        return self.loaded

    def GetCaptureFilename(self) -> str:
        return self.filename if self.loaded else ""

    def FrameInfo(self) -> object:
        return type("FrameInfo", (), {"frameNumber": 42231})()

    def Replay(self) -> FakeController:
        return self.controller

    def CurPipelineState(self) -> FakePipeline:
        return self.controller.pipeline


def test_capture_status_returns_mcp_query_envelope() -> None:
    handler = bridge.RenderDocMCPBridge(FakeContext())
    payload = handler.dispatch("get_capture_status", {})

    assert payload["ok"] is True
    assert payload["contract_version"] == "mcp-query.v1"
    assert payload["data"]["loaded"] is True
    assert payload["data"]["filename"].endswith("frame.rdc")
    assert payload["data"]["frame_number"] == 42231


def test_draw_calls_filter_and_preserve_marker_path() -> None:
    handler = bridge.RenderDocMCPBridge(FakeContext())
    payload = handler.dispatch("get_draw_calls", {"keyword": "terrain", "max_count": 5})

    assert payload["ok"] is True
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["event_id"] == 11
    assert payload["data"]["items"][0]["marker_path"] == ["Geometry"]


def test_pipeline_state_marks_missing_fields_partial() -> None:
    handler = bridge.RenderDocMCPBridge(FakeContext())
    payload = handler.dispatch("get_pipeline_state", {"event_id": 11})

    assert payload["ok"] is True
    assert payload["availability"]["status"] == "partial"
    assert "depth_target_ref" in payload["availability"]["missing_fields"]
    assert payload["data"]["vs_ref"] == "vs-main"
    assert payload["data"]["ps_ref"] == "ps-main"


def test_buffer_contents_applies_requested_limit_and_warning() -> None:
    handler = bridge.RenderDocMCPBridge(FakeContext())
    payload = handler.dispatch(
        "get_buffer_contents",
        {"resource_id": "buf-verts", "offset": 0, "byte_count": 32, "max_bytes": 8},
    )

    assert payload["ok"] is True
    assert payload["data"]["encoding"] == "hex"
    assert payload["data"]["byte_count"] == 8
    assert payload["data"]["truncated"] is True
    assert payload["warnings"]


def test_all_contract_methods_return_stable_envelopes(tmp_path: Path) -> None:
    capture_path = tmp_path / "sample.rdc"
    capture_path.write_bytes(b"RDC")
    handler = bridge.RenderDocMCPBridge(FakeContext())
    cases = [
        ("list_captures", {}),
        ("open_capture", {"path": str(capture_path)}),
        ("get_frame_summary", {}),
        ("get_draw_call_details", {"event_id": 11}),
        ("get_action_timings", {"max_count": 10}),
        ("find_draws_by_shader", {"shader_ref": "ps-main"}),
        ("find_draws_by_texture", {"resource_id": "tex-color"}),
        ("find_draws_by_resource", {"resource_id": "buf-verts"}),
        ("get_shader_info", {"event_id": 11, "stage": "pixel"}),
        ("get_texture_info", {"resource_id": "tex-color"}),
        ("get_texture_data", {"resource_id": "tex-color", "max_bytes": 8}),
    ]

    for method, params in cases:
        payload = handler.dispatch(method, params)
        assert payload["ok"] is True, method
        assert payload["contract_version"] == "mcp-query.v1", method
        assert payload["method"] == method
        assert "availability" in payload


def test_unknown_method_is_stable_error_envelope() -> None:
    handler = bridge.RenderDocMCPBridge(FakeContext())
    payload = handler.dispatch("unknown_method", {})

    assert payload["ok"] is False
    assert payload["error"]["code"] == "method_not_found"
    assert payload["contract_version"] == "mcp-query.v1"


def test_file_ipc_processes_one_request(tmp_path: Path) -> None:
    handler = bridge.RenderDocMCPBridge(FakeContext(), ipc_dir=str(tmp_path))
    request = {"id": "req-1", "method": "get_capture_status", "params": {}}
    (tmp_path / "request.json").write_text(json.dumps(request), encoding="utf-8")

    assert handler.process_next_request() is True

    response = json.loads((tmp_path / "response.json").read_text(encoding="utf-8"))
    assert response["id"] == "req-1"
    assert response["result"]["ok"] is True
    assert response["result"]["contract_version"] == "mcp-query.v1"
