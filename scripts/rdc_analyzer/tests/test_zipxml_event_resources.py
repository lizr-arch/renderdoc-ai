import sys
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def test_extract_vulkan_bindings_for_drawindexed(tmp_path):
    try:
        from parsers.zipxml_event_parser import extract_vulkan_bindings_for_event
    except ImportError as exc:
        pytest.fail(f"zipxml_event_parser missing binding extractor: {exc}")

    xml_path = tmp_path / "sample.zip.xml"
    xml_path.write_text(
        """<rdc>
  <header><driver id=\"8\">Vulkan</driver></header>
  <chunks>
    <chunk id=\"1061\" chunkIndex=\"16317\" name=\"vkCmdBindIndexBuffer\">
      <ResourceId name=\"buffer\" typename=\"VkBuffer\">343</ResourceId>
      <uint name=\"offset\" typename=\"uint64_t\">0</uint>
      <enum name=\"indexType\" typename=\"VkIndexType\" string=\"VK_INDEX_TYPE_UINT16\">0</enum>
    </chunk>
    <chunk id=\"1060\" chunkIndex=\"16318\" name=\"vkCmdBindVertexBuffers\">
      <uint name=\"firstBinding\" typename=\"uint32_t\">0</uint>
      <uint name=\"bindingCount\" typename=\"uint32_t\">2</uint>
      <array name=\"pBuffers\">
        <ResourceId typename=\"VkBuffer\">339</ResourceId>
        <ResourceId typename=\"VkBuffer\">341</ResourceId>
      </array>
      <array name=\"pOffsets\">
        <uint typename=\"uint64_t\">0</uint>
        <uint typename=\"uint64_t\">16</uint>
      </array>
    </chunk>
    <chunk id=\"1085\" chunkIndex=\"16322\" name=\"vkCmdDrawIndexed\">
      <uint name=\"indexCount\" typename=\"uint32_t\">36</uint>
      <uint name=\"instanceCount\" typename=\"uint32_t\">1</uint>
      <uint name=\"firstIndex\" typename=\"uint32_t\">0</uint>
      <int name=\"vertexOffset\" typename=\"int32_t\">0</int>
      <uint name=\"firstInstance\" typename=\"uint32_t\">0</uint>
    </chunk>
  </chunks>
</rdc>
""",
        encoding="utf-8",
    )

    bindings = extract_vulkan_bindings_for_event(str(xml_path), event_id=16322)
    assert bindings["index_buffer"]["resource_id"] == 343
    assert bindings["index_buffer"]["byte_offset"] == 0
    assert bindings["index_buffer"]["index_format"] == "uint16"

    vbs = bindings["vertex_buffers"]
    assert len(vbs) == 2
    assert vbs[0]["resource_id"] == 339
    assert vbs[0]["byte_offset"] == 0
    assert vbs[1]["resource_id"] == 341
    assert vbs[1]["byte_offset"] == 16

    assert bindings["draw"]["index_count"] == 36


def test_build_vulkan_buffer_memory_maps(tmp_path):
    try:
        from parsers.zipxml_event_parser import build_vulkan_buffer_memory_maps
    except ImportError as exc:
        pytest.fail(f"zipxml_event_parser missing map builder: {exc}")

    xml_path = tmp_path / "sample.zip.xml"
    xml_path.write_text(
        """<rdc>
  <chunks>
    <chunk id=\"1013\" chunkIndex=\"147\" name=\"vkCreateBuffer\">
      <struct name=\"CreateInfo\" typename=\"VkBufferCreateInfo\">
        <uint name=\"size\" typename=\"uint64_t\">4096</uint>
      </struct>
      <ResourceId name=\"Buffer\" typename=\"VkBuffer\">901</ResourceId>
    </chunk>
    <chunk id=\"1042\" chunkIndex=\"148\" name=\"vkBindBufferMemory\">
      <ResourceId name=\"buffer\" typename=\"VkBuffer\">901</ResourceId>
      <ResourceId name=\"memory\" typename=\"VkDeviceMemory\">210</ResourceId>
      <uint name=\"memoryOffset\" typename=\"uint64_t\">12607488</uint>
    </chunk>
    <chunk id=\"3\" chunkIndex=\"12643\" name=\"Internal::Initial Contents\">
      <enum name=\"type\" typename=\"VkResourceType\" string=\"eResDeviceMemory\">5</enum>
      <ResourceId name=\"id\" typename=\"VkDeviceMemory\">210</ResourceId>
      <uint name=\"ContentsSize\" typename=\"uint64_t\">33554432</uint>
      <buffer name=\"Contents\" typename=\"Byte Buffer\">425</buffer>
    </chunk>
  </chunks>
</rdc>
""",
        encoding="utf-8",
    )

    buffer_memory, memory_initial, buffer_sizes = build_vulkan_buffer_memory_maps(str(xml_path))

    assert buffer_memory[901]["memory_id"] == 210
    assert buffer_memory[901]["memory_offset"] == 12607488

    assert memory_initial[210]["buffer_index"] == 425
    assert memory_initial[210]["contents_size"] == 33554432

    assert buffer_sizes[901] == 4096
