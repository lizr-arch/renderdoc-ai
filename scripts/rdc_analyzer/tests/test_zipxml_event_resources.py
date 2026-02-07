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



def test_extract_d3d11_bindings_and_buffer_map(tmp_path):
    try:
        from parsers.zipxml_event_parser import (
            build_d3d11_buffer_data_map,
            extract_d3d11_bindings_for_event,
        )
    except ImportError as exc:
        pytest.fail(f"zipxml_event_parser missing D3D11 extractor: {exc}")

    xml_path = tmp_path / "sample_d3d11.zip.xml"
    xml_path.write_text(
        """<rdc>
  <header><driver id="1">D3D11</driver></header>
  <chunks>
    <chunk id="1006" chunkIndex="10" name="ID3D11Device::CreateBuffer">
      <struct name="pDesc" typename="D3D11_BUFFER_DESC">
        <uint name="ByteWidth" typename="uint32_t">64</uint>
      </struct>
      <ResourceId name="pBuffer" typename="ID3D11Buffer *">307</ResourceId>
      <buffer name="InitialData" typename="Byte Buffer" byteLength="64">33</buffer>
      <uint name="InitialDataLength" typename="uint64_t">64</uint>
    </chunk>
    <chunk id="1006" chunkIndex="11" name="ID3D11Device::CreateBuffer">
      <struct name="pDesc" typename="D3D11_BUFFER_DESC">
        <uint name="ByteWidth" typename="uint32_t">12</uint>
      </struct>
      <ResourceId name="pBuffer" typename="ID3D11Buffer *">308</ResourceId>
      <buffer name="InitialData" typename="Byte Buffer" byteLength="12">34</buffer>
      <uint name="InitialDataLength" typename="uint64_t">12</uint>
    </chunk>
    <chunk id="1033" chunkIndex="91" name="ID3D11DeviceContext::IASetVertexBuffers">
      <uint name="StartSlot" typename="uint32_t">0</uint>
      <array name="ppVertexBuffers"><ResourceId typename="ID3D11Buffer *">307</ResourceId></array>
      <array name="pStrides"><uint typename="uint32_t">32</uint></array>
      <array name="pOffsets"><uint typename="uint32_t">0</uint></array>
    </chunk>
    <chunk id="1034" chunkIndex="92" name="ID3D11DeviceContext::IASetIndexBuffer">
      <ResourceId name="pIndexBuffer" typename="ID3D11Buffer *">308</ResourceId>
      <enum name="Format" typename="DXGI_FORMAT" string="DXGI_FORMAT_R16_UINT">57</enum>
      <uint name="Offset" typename="uint32_t">0</uint>
    </chunk>
    <chunk id="1071" chunkIndex="100" name="ID3D11DeviceContext::DrawIndexed">
      <uint name="IndexCount" typename="uint32_t">6</uint>
      <uint name="StartIndexLocation" typename="uint32_t">0</uint>
      <int name="BaseVertexLocation" typename="int32_t">0</int>
    </chunk>
  </chunks>
</rdc>
""",
        encoding="utf-8",
    )

    bindings = extract_d3d11_bindings_for_event(str(xml_path), event_id=100)
    assert bindings["index_buffer"]["resource_id"] == 308
    assert bindings["index_buffer"]["index_format"] == "uint16"
    assert bindings["draw"]["index_count"] == 6
    assert bindings["vertex_buffers"][0]["resource_id"] == 307
    assert bindings["vertex_buffers"][0]["stride"] == 32

    resource_map = build_d3d11_buffer_data_map(str(xml_path), upto_event_id=100)
    assert resource_map[307]["buffer_index"] == 33
    assert resource_map[308]["buffer_index"] == 34



def test_extract_vulkan_descriptor_template_uses_fallback_set_and_view_mapping(tmp_path):
    from parsers.zipxml_event_parser import extract_vulkan_bindings_for_event

    xml_path = tmp_path / "sample_vulkan_descriptor.zip.xml"
    xml_path.write_text(
        """<rdc>
  <header><driver id="8">Vulkan</driver></header>
  <chunks>
    <chunk id="1015" chunkIndex="10" name="vkCreateImage">
      <struct name="CreateInfo" typename="VkImageCreateInfo">
        <enum name="format" typename="VkFormat" string="VK_FORMAT_R8G8B8A8_UNORM">37</enum>
        <struct name="extent" typename="VkExtent3D">
          <uint name="width" typename="uint32_t">64</uint>
          <uint name="height" typename="uint32_t">64</uint>
          <uint name="depth" typename="uint32_t">1</uint>
        </struct>
        <uint name="mipLevels" typename="uint32_t">1</uint>
        <uint name="arrayLayers" typename="uint32_t">1</uint>
      </struct>
      <ResourceId name="Image" typename="VkImage">40</ResourceId>
    </chunk>
    <chunk id="1043" chunkIndex="11" name="vkBindImageMemory">
      <ResourceId name="image" typename="VkImage">40</ResourceId>
      <ResourceId name="memory" typename="VkDeviceMemory">70</ResourceId>
      <uint name="memoryOffset" typename="uint64_t">128</uint>
    </chunk>
    <chunk id="3" chunkIndex="12" name="Internal::Initial Contents">
      <enum name="type" typename="VkResourceType" string="eResDeviceMemory">5</enum>
      <ResourceId name="id" typename="VkDeviceMemory">70</ResourceId>
      <uint name="ContentsSize" typename="uint64_t">4096</uint>
      <buffer name="Contents" typename="Byte Buffer">99</buffer>
    </chunk>
    <chunk id="1016" chunkIndex="13" name="vkCreateImageView">
      <struct name="CreateInfo" typename="VkImageViewCreateInfo">
        <ResourceId name="image" typename="VkImage">40</ResourceId>
      </struct>
      <ResourceId name="View" typename="VkImageView">50</ResourceId>
    </chunk>
    <chunk id="1106" chunkIndex="14" name="vkUpdateDescriptorSetWithTemplate">
      <ResourceId name="descriptorSet" typename="VkDescriptorSet">300</ResourceId>
      <array name="Decoded Writes">
        <struct typename="VkWriteDescriptorSet">
          <ResourceId name="dstSet" typename="VkDescriptorSet">0</ResourceId>
          <uint name="dstBinding" typename="uint32_t">2</uint>
          <enum name="descriptorType" typename="VkDescriptorType" string="VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER">1</enum>
          <array name="pImageInfo">
            <struct typename="VkDescriptorImageInfo">
              <ResourceId name="sampler" typename="VkSampler">7</ResourceId>
              <ResourceId name="imageView" typename="VkImageView">50</ResourceId>
              <enum name="imageLayout" typename="VkImageLayout" string="VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL">5</enum>
            </struct>
          </array>
        </struct>
      </array>
    </chunk>
    <chunk id="1062" chunkIndex="15" name="vkCmdBindDescriptorSets">
      <enum name="pipelineBindPoint" typename="VkPipelineBindPoint" string="VK_PIPELINE_BIND_POINT_GRAPHICS">0</enum>
      <uint name="firstSet" typename="uint32_t">3</uint>
      <array name="pDescriptorSets">
        <ResourceId typename="VkDescriptorSet">300</ResourceId>
      </array>
    </chunk>
    <chunk id="1085" chunkIndex="20" name="vkCmdDrawIndexed">
      <uint name="indexCount" typename="uint32_t">3</uint>
      <uint name="instanceCount" typename="uint32_t">1</uint>
      <uint name="firstIndex" typename="uint32_t">0</uint>
      <int name="vertexOffset" typename="int32_t">0</int>
      <uint name="firstInstance" typename="uint32_t">0</uint>
    </chunk>
  </chunks>
</rdc>
""",
        encoding="utf-8",
    )

    bindings = extract_vulkan_bindings_for_event(str(xml_path), event_id=20)
    textures = bindings.get("textures") or []
    assert len(textures) == 1

    tex = textures[0]
    assert tex["slot"] == "set3.binding2"
    assert tex["sampler"] == "set3.binding2"
    assert tex["texture_id"] == 50
    assert tex["image_id"] == 40
    assert tex["format"] == "VK_FORMAT_R8G8B8A8_UNORM"
    assert tex["width"] == 64
    assert tex["height"] == 64
    assert tex["memory_buffer_index"] == 99
