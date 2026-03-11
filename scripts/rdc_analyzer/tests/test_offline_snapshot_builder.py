import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from providers.offline_snapshot_builder import OfflineSnapshotBuilder


def test_build_snapshot_minimum_completeness():
    builder = OfflineSnapshotBuilder()
    snapshot = builder.build(
        capture_name="sample_capture",
        xml_path="sample.xml",
        driver="Vulkan",
        draw_calls=[
            {
                "event_id": 101,
                "name": "vkCmdDrawIndexed",
                "index_count": 36,
                "vertex_count": 24,
                "instance_count": 1,
                "render_targets": [{"id": "176441", "slot": 0}],
                "depth_target": {"id": "176442", "aspect": "depth"},
            }
        ],
        textures=[
            {
                "resource_id": "176441",
                "name": "MainColor",
                "width": 1920,
                "height": 1080,
                "format": "R8G8B8A8_UNORM",
                "size_bytes": 8294400,
                "thumbnail": "",
            }
        ],
        buffers=[{"resource_id": "20001", "name": "VertexBuffer", "size": 4096, "usage": "Vertex"}],
        shaders=[
            {
                "id": "shader-1",
                "name": "VS_Main",
                "stage": "Vertex",
                "source_code": "",
            }
        ],
    )

    expected_keys = {
        "schema_version",
        "meta",
        "preflight",
        "overview",
        "actions",
        "resources",
        "findings",
        "recommendations",
        "availability",
    }
    assert expected_keys.issubset(snapshot.keys())
    assert snapshot["schema_version"] == "snapshot.v1"

    assert isinstance(snapshot["meta"], dict)
    assert snapshot["meta"]["source"] == "offline"
    assert isinstance(snapshot["preflight"], dict)
    assert isinstance(snapshot["overview"], dict)
    assert isinstance(snapshot["actions"], list)
    assert isinstance(snapshot["resources"], dict)
    assert isinstance(snapshot["findings"], list)
    assert isinstance(snapshot["recommendations"], list)
    assert isinstance(snapshot["availability"], dict)

    assert snapshot["availability"]["status"] == "partial"
    assert "MCP query" in snapshot["availability"]["mcp_hint"]
    assert snapshot["preflight"]["status"] == "warning"
    assert snapshot["recommendations"][0]["id"] == "offline-mcp-fill"
