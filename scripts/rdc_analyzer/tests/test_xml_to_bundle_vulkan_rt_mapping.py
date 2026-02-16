from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import xml_to_bundle as xb


def test_simple_xml_parser_tracks_vulkan_render_targets(tmp_path: Path):
    xml_text = """
<rdc>
  <chunk name="vkCreateImageView">
    <ResourceId name="View">VIEW_COLOR</ResourceId>
    <struct name="pCreateInfo">
      <ResourceId name="image">IMG_COLOR</ResourceId>
      <struct name="subresourceRange">
        <uint name="aspectMask" string="VK_IMAGE_ASPECT_COLOR_BIT">1</uint>
      </struct>
    </struct>
  </chunk>
  <chunk name="vkCreateImageView">
    <ResourceId name="View">VIEW_DEPTH</ResourceId>
    <struct name="pCreateInfo">
      <ResourceId name="image">IMG_DEPTH</ResourceId>
      <struct name="subresourceRange">
        <uint name="aspectMask" string="VK_IMAGE_ASPECT_DEPTH_BIT">2</uint>
      </struct>
    </struct>
  </chunk>
  <chunk name="vkCreateFramebuffer">
    <ResourceId name="Framebuffer">FB_MAIN</ResourceId>
    <struct name="pCreateInfo">
      <array name="pAttachments">
        <ResourceId>VIEW_COLOR</ResourceId>
        <ResourceId>VIEW_DEPTH</ResourceId>
      </array>
    </struct>
  </chunk>
  <chunk name="vkCmdBeginRenderPass">
    <struct name="RenderPassBegin">
      <ResourceId name="framebuffer">FB_MAIN</ResourceId>
    </struct>
  </chunk>
  <chunk name="vkCmdDraw" eventId="0" chunkIndex="101">
    <uint name="vertexCount">3</uint>
  </chunk>
  <chunk name="vkCmdEndRenderPass"/>
  <chunk name="vkCmdDraw" chunkIndex="102">
    <uint name="vertexCount">6</uint>
  </chunk>
</rdc>
""".strip()

    xml_path = tmp_path / "capture.xml"
    xml_path.write_text(xml_text, encoding="utf-8")

    parsed = xb.SimpleXmlParser().parse(str(xml_path))
    draw_calls = parsed["draw_calls"]

    assert len(draw_calls) == 2

    first = draw_calls[0]
    assert first["event_id"] == 101
    assert first["render_targets"] == [{"id": "IMG_COLOR", "slot": 0}]
    assert first["depth_target"] == "IMG_DEPTH"

    second = draw_calls[1]
    assert second["event_id"] == 102
    assert second.get("render_targets", []) == []
    assert "depth_target" not in second

    events = xb.xml_to_bundle_events_dict(draw_calls)
    assert events[0]["renderTargets"] == [{"id": "IMG_COLOR", "slot": 0}]
    assert events[0]["depthTarget"] == {"id": "IMG_DEPTH"}
    assert events[1].get("renderTargets", []) == []
    assert "depthTarget" not in events[1]
