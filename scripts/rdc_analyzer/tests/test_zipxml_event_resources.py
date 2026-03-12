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




def test_extract_vulkan_bindings_includes_shader_module_metadata(tmp_path):
    from parsers.zipxml_event_parser import extract_vulkan_bindings_for_event

    xml_path = tmp_path / "sample_shader.zip.xml"
    xml_path.write_text(
        """<rdc>
  <header><driver id=\"8\">Vulkan</driver></header>
  <chunks>
    <chunk id=\"1019\" chunkIndex=\"90\" name=\"vkCreateShaderModule\">
      <struct name=\"CreateInfo\" typename=\"VkShaderModuleCreateInfo\">
        <uint name=\"codeSize\" typename=\"uint64_t\">4</uint>
        <buffer name=\"pCode\" typename=\"Byte Buffer\" byteLength=\"4\">1</buffer>
      </struct>
      <ResourceId name=\"ShaderModule\" typename=\"VkShaderModule\">7001</ResourceId>
    </chunk>
    <chunk id=\"1019\" chunkIndex=\"91\" name=\"vkCreateShaderModule\">
      <struct name=\"CreateInfo\" typename=\"VkShaderModuleCreateInfo\">
        <uint name=\"codeSize\" typename=\"uint64_t\">8</uint>
        <buffer name=\"pCode\" typename=\"Byte Buffer\" byteLength=\"8\">2</buffer>
      </struct>
      <ResourceId name=\"ShaderModule\" typename=\"VkShaderModule\">7002</ResourceId>
    </chunk>
    <chunk id=\"1022\" chunkIndex=\"92\" name=\"vkCreateGraphicsPipelines\">
      <ResourceId name=\"Pipeline\" typename=\"VkPipeline\">500</ResourceId>
      <struct name=\"CreateInfo\" typename=\"VkGraphicsPipelineCreateInfo\">
        <array name=\"pStages\">
          <struct typename=\"VkPipelineShaderStageCreateInfo\">
            <enum name=\"stage\" typename=\"VkShaderStageFlagBits\" string=\"VK_SHADER_STAGE_VERTEX_BIT\">1</enum>
            <ResourceId name=\"module\" typename=\"VkShaderModule\">7001</ResourceId>
            <string name=\"pName\">main_vs</string>
          </struct>
          <struct typename=\"VkPipelineShaderStageCreateInfo\">
            <enum name=\"stage\" typename=\"VkShaderStageFlagBits\" string=\"VK_SHADER_STAGE_FRAGMENT_BIT\">16</enum>
            <ResourceId name=\"module\" typename=\"VkShaderModule\">7002</ResourceId>
            <string name=\"pName\">main_ps</string>
          </struct>
        </array>
      </struct>
    </chunk>
    <chunk id=\"1063\" chunkIndex=\"93\" name=\"vkCmdBindPipeline\">
      <enum name=\"pipelineBindPoint\" typename=\"VkPipelineBindPoint\" string=\"VK_PIPELINE_BIND_POINT_GRAPHICS\">0</enum>
      <ResourceId name=\"pipeline\" typename=\"VkPipeline\">500</ResourceId>
    </chunk>
    <chunk id=\"1061\" chunkIndex=\"94\" name=\"vkCmdBindIndexBuffer\">
      <ResourceId name=\"buffer\" typename=\"VkBuffer\">343</ResourceId>
      <uint name=\"offset\" typename=\"uint64_t\">0</uint>
      <enum name=\"indexType\" typename=\"VkIndexType\" string=\"VK_INDEX_TYPE_UINT16\">0</enum>
    </chunk>
    <chunk id=\"1060\" chunkIndex=\"95\" name=\"vkCmdBindVertexBuffers\">
      <uint name=\"firstBinding\" typename=\"uint32_t\">0</uint>
      <uint name=\"bindingCount\" typename=\"uint32_t\">1</uint>
      <array name=\"pBuffers\"><ResourceId typename=\"VkBuffer\">339</ResourceId></array>
      <array name=\"pOffsets\"><uint typename=\"uint64_t\">0</uint></array>
    </chunk>
    <chunk id=\"1085\" chunkIndex=\"100\" name=\"vkCmdDrawIndexed\">
      <uint name=\"indexCount\" typename=\"uint32_t\">3</uint>
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

    bindings = extract_vulkan_bindings_for_event(str(xml_path), event_id=100)
    shaders = bindings.get("shaders") or []
    assert len(shaders) == 2

    shader_by_stage = {item["stage"]: item for item in shaders}
    assert shader_by_stage["vs"]["resource_id"] == 7001
    assert shader_by_stage["vs"]["buffer_index"] == 1
    assert shader_by_stage["vs"]["byte_length"] == 4
    assert shader_by_stage["vs"]["entry"] == "main_vs"
    assert shader_by_stage["vs"]["source_kind"] == "vulkan_shader_module"

    assert shader_by_stage["ps"]["resource_id"] == 7002
    assert shader_by_stage["ps"]["buffer_index"] == 2
    assert shader_by_stage["ps"]["byte_length"] == 8
    assert shader_by_stage["ps"]["entry"] == "main_ps"
    assert shader_by_stage["ps"]["source_kind"] == "vulkan_shader_module"



def test_extract_vulkan_bindings_prefers_shader_objects_over_pipeline_modules(tmp_path):
    from parsers.zipxml_event_parser import extract_vulkan_bindings_for_event

    xml_path = tmp_path / "sample_shader_objects.zip.xml"
    xml_path.write_text(
        """<rdc>
  <header><driver id="8">Vulkan</driver></header>
  <chunks>
    <chunk id="1019" chunkIndex="90" name="vkCreateShaderModule">
      <struct name="CreateInfo" typename="VkShaderModuleCreateInfo">
        <uint name="codeSize" typename="uint64_t">4</uint>
        <buffer name="pCode" typename="Byte Buffer" byteLength="4">1</buffer>
      </struct>
      <ResourceId name="ShaderModule" typename="VkShaderModule">7001</ResourceId>
    </chunk>
    <chunk id="1019" chunkIndex="91" name="vkCreateShaderModule">
      <struct name="CreateInfo" typename="VkShaderModuleCreateInfo">
        <uint name="codeSize" typename="uint64_t">8</uint>
        <buffer name="pCode" typename="Byte Buffer" byteLength="8">2</buffer>
      </struct>
      <ResourceId name="ShaderModule" typename="VkShaderModule">7002</ResourceId>
    </chunk>
    <chunk id="1022" chunkIndex="92" name="vkCreateGraphicsPipelines">
      <ResourceId name="Pipeline" typename="VkPipeline">500</ResourceId>
      <struct name="CreateInfo" typename="VkGraphicsPipelineCreateInfo">
        <array name="pStages">
          <struct typename="VkPipelineShaderStageCreateInfo">
            <enum name="stage" typename="VkShaderStageFlagBits" string="VK_SHADER_STAGE_VERTEX_BIT">1</enum>
            <ResourceId name="module" typename="VkShaderModule">7001</ResourceId>
            <string name="pName">main_vs</string>
          </struct>
          <struct typename="VkPipelineShaderStageCreateInfo">
            <enum name="stage" typename="VkShaderStageFlagBits" string="VK_SHADER_STAGE_FRAGMENT_BIT">16</enum>
            <ResourceId name="module" typename="VkShaderModule">7002</ResourceId>
            <string name="pName">main_ps</string>
          </struct>
        </array>
      </struct>
    </chunk>
    <chunk id="1030" chunkIndex="93" name="vkCreateShadersEXT">
      <array name="pCreateInfos">
        <struct typename="VkShaderCreateInfoEXT">
          <enum name="stage" typename="VkShaderStageFlagBits" string="VK_SHADER_STAGE_VERTEX_BIT">1</enum>
          <enum name="codeType" typename="VkShaderCodeTypeEXT" string="VK_SHADER_CODE_TYPE_SPIRV_EXT">0</enum>
          <uint name="codeSize" typename="uint64_t">12</uint>
          <buffer name="pCode" typename="Byte Buffer" byteLength="12">11</buffer>
          <string name="pName">main_vs_obj</string>
        </struct>
        <struct typename="VkShaderCreateInfoEXT">
          <enum name="stage" typename="VkShaderStageFlagBits">16</enum>
          <enum name="codeType" typename="VkShaderCodeTypeEXT" string="VK_SHADER_CODE_TYPE_SPIRV_EXT">0</enum>
          <uint name="codeSize" typename="uint64_t">20</uint>
          <buffer name="pCode" typename="Byte Buffer" byteLength="20">12</buffer>
          <string name="pName">main_ps_obj</string>
        </struct>
      </array>
      <array name="pShaders">
        <ResourceId typename="VkShaderEXT">9001</ResourceId>
        <ResourceId typename="VkShaderEXT">9002</ResourceId>
      </array>
    </chunk>
    <chunk id="1063" chunkIndex="94" name="vkCmdBindPipeline">
      <enum name="pipelineBindPoint" typename="VkPipelineBindPoint" string="VK_PIPELINE_BIND_POINT_GRAPHICS">0</enum>
      <ResourceId name="pipeline" typename="VkPipeline">500</ResourceId>
    </chunk>
    <chunk id="1064" chunkIndex="95" name="vkCmdBindShadersEXT">
      <array name="pStages">
        <enum typename="VkShaderStageFlagBits" string="VK_SHADER_STAGE_VERTEX_BIT">1</enum>
        <enum typename="VkShaderStageFlagBits">16</enum>
      </array>
      <array name="pShaders">
        <ResourceId typename="VkShaderEXT">9001</ResourceId>
        <ResourceId typename="VkShaderEXT">9002</ResourceId>
      </array>
    </chunk>
    <chunk id="1061" chunkIndex="96" name="vkCmdBindIndexBuffer">
      <ResourceId name="buffer" typename="VkBuffer">343</ResourceId>
      <uint name="offset" typename="uint64_t">0</uint>
      <enum name="indexType" typename="VkIndexType" string="VK_INDEX_TYPE_UINT16">0</enum>
    </chunk>
    <chunk id="1060" chunkIndex="97" name="vkCmdBindVertexBuffers">
      <uint name="firstBinding" typename="uint32_t">0</uint>
      <uint name="bindingCount" typename="uint32_t">1</uint>
      <array name="pBuffers"><ResourceId typename="VkBuffer">339</ResourceId></array>
      <array name="pOffsets"><uint typename="uint64_t">0</uint></array>
    </chunk>
    <chunk id="1085" chunkIndex="100" name="vkCmdDrawIndexed">
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

    bindings = extract_vulkan_bindings_for_event(str(xml_path), event_id=100)
    shaders = bindings.get("shaders") or []
    assert [item["stage"] for item in shaders] == ["vs", "ps"]

    shader_by_stage = {item["stage"]: item for item in shaders}
    assert shader_by_stage["vs"]["resource_id"] == 9001
    assert shader_by_stage["vs"]["buffer_index"] == 11
    assert shader_by_stage["vs"]["byte_length"] == 12
    assert shader_by_stage["vs"]["entry"] == "main_vs_obj"
    assert shader_by_stage["vs"]["source_kind"] == "vulkan_shader_object"

    assert shader_by_stage["ps"]["resource_id"] == 9002
    assert shader_by_stage["ps"]["buffer_index"] == 12
    assert shader_by_stage["ps"]["byte_length"] == 20
    assert shader_by_stage["ps"]["entry"] == "main_ps_obj"
    assert shader_by_stage["ps"]["source_kind"] == "vulkan_shader_object"

    assert bindings["pipeline_id"] == 0

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



def test_scan_vulkan_draw_texture_events_emits_mesh_flags(tmp_path):
    from parsers.zipxml_event_parser import scan_vulkan_draw_texture_events

    xml_path = tmp_path / "scan_sample.zip.xml"
    xml_path.write_text(
        """<rdc>
  <header><driver id="8">Vulkan</driver></header>
  <chunks>
    <chunk id="1085" chunkIndex="5" name="vkCmdDrawIndexed">
      <uint name="indexCount" typename="uint32_t">6</uint>
      <uint name="instanceCount" typename="uint32_t">1</uint>
      <uint name="firstIndex" typename="uint32_t">0</uint>
      <int name="vertexOffset" typename="int32_t">0</int>
      <uint name="firstInstance" typename="uint32_t">0</uint>
    </chunk>

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

    <chunk id="1042" chunkIndex="14" name="vkUpdateDescriptorSets">
      <array name="pDescriptorWrites">
        <struct typename="VkWriteDescriptorSet">
          <ResourceId name="dstSet" typename="VkDescriptorSet">300</ResourceId>
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

    <chunk id="1061" chunkIndex="16" name="vkCmdBindIndexBuffer">
      <ResourceId name="buffer" typename="VkBuffer">343</ResourceId>
      <uint name="offset" typename="uint64_t">0</uint>
      <enum name="indexType" typename="VkIndexType" string="VK_INDEX_TYPE_UINT16">0</enum>
    </chunk>
    <chunk id="1060" chunkIndex="17" name="vkCmdBindVertexBuffers">
      <uint name="firstBinding" typename="uint32_t">0</uint>
      <uint name="bindingCount" typename="uint32_t">1</uint>
      <array name="pBuffers"><ResourceId typename="VkBuffer">339</ResourceId></array>
      <array name="pOffsets"><uint typename="uint64_t">0</uint></array>
    </chunk>

    <chunk id="1085" chunkIndex="20" name="vkCmdDrawIndexed">
      <uint name="indexCount" typename="uint32_t">36</uint>
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

    payload = scan_vulkan_draw_texture_events(str(xml_path), preview_limit=4, min_textures=0)

    assert payload["summary"]["total_draw_events"] == 2
    assert payload["summary"]["textured_draw_events"] == 1

    first = payload["events"][0]
    assert first["event_id"] == 5
    assert first["mesh_compatible"] is False
    assert first["has_vertex_binding"] is False
    assert first["has_index_binding"] is False

    second = payload["events"][1]
    assert second["event_id"] == 20
    assert second["mesh_compatible"] is True
    assert second["mesh_exportable"] is True
    assert second["has_vertex_binding"] is True
    assert second["has_index_binding"] is True
    assert second["texture_count"] == 1
    assert second["bound_descriptor_sets"]["3"] == 300
    assert second["textures_preview"][0]["texture_id"] == 50



def test_scan_vulkan_draw_texture_events_prefers_shader_object_stages(tmp_path):
    from parsers.zipxml_event_parser import scan_vulkan_draw_texture_events

    xml_path = tmp_path / "scan_shader_objects.zip.xml"
    xml_path.write_text(
        """<rdc>
  <header><driver id="8">Vulkan</driver></header>
  <chunks>
    <chunk id="1019" chunkIndex="10" name="vkCreateShaderModule">
      <struct name="CreateInfo" typename="VkShaderModuleCreateInfo">
        <uint name="codeSize" typename="uint64_t">4</uint>
        <buffer name="pCode" typename="Byte Buffer" byteLength="4">1</buffer>
      </struct>
      <ResourceId name="ShaderModule" typename="VkShaderModule">7001</ResourceId>
    </chunk>
    <chunk id="1019" chunkIndex="11" name="vkCreateShaderModule">
      <struct name="CreateInfo" typename="VkShaderModuleCreateInfo">
        <uint name="codeSize" typename="uint64_t">8</uint>
        <buffer name="pCode" typename="Byte Buffer" byteLength="8">2</buffer>
      </struct>
      <ResourceId name="ShaderModule" typename="VkShaderModule">7002</ResourceId>
    </chunk>
    <chunk id="1022" chunkIndex="12" name="vkCreateGraphicsPipelines">
      <ResourceId name="Pipeline" typename="VkPipeline">500</ResourceId>
      <struct name="CreateInfo" typename="VkGraphicsPipelineCreateInfo">
        <array name="pStages">
          <struct typename="VkPipelineShaderStageCreateInfo">
            <enum name="stage" typename="VkShaderStageFlagBits" string="VK_SHADER_STAGE_VERTEX_BIT">1</enum>
            <ResourceId name="module" typename="VkShaderModule">7001</ResourceId>
            <string name="pName">main_vs</string>
          </struct>
          <struct typename="VkPipelineShaderStageCreateInfo">
            <enum name="stage" typename="VkShaderStageFlagBits" string="VK_SHADER_STAGE_FRAGMENT_BIT">16</enum>
            <ResourceId name="module" typename="VkShaderModule">7002</ResourceId>
            <string name="pName">main_ps</string>
          </struct>
        </array>
      </struct>
    </chunk>
    <chunk id="1063" chunkIndex="13" name="vkCmdBindPipeline">
      <enum name="pipelineBindPoint" typename="VkPipelineBindPoint" string="VK_PIPELINE_BIND_POINT_GRAPHICS">0</enum>
      <ResourceId name="pipeline" typename="VkPipeline">500</ResourceId>
    </chunk>
    <chunk id="1085" chunkIndex="14" name="vkCmdDrawIndexed">
      <uint name="indexCount" typename="uint32_t">3</uint>
      <uint name="instanceCount" typename="uint32_t">1</uint>
      <uint name="firstIndex" typename="uint32_t">0</uint>
      <int name="vertexOffset" typename="int32_t">0</int>
      <uint name="firstInstance" typename="uint32_t">0</uint>
    </chunk>
    <chunk id="1030" chunkIndex="15" name="vkCreateShadersEXT">
      <struct name="CreateInfo" typename="VkShaderCreateInfoEXT">
        <enum name="stage" typename="VkShaderStageFlagBits">16</enum>
        <enum name="codeType" typename="VkShaderCodeTypeEXT" string="VK_SHADER_CODE_TYPE_SPIRV_EXT">0</enum>
        <uint name="codeSize" typename="uint64_t">20</uint>
        <buffer name="pCode" typename="Byte Buffer" byteLength="20">12</buffer>
        <string name="pName">main_ps_obj</string>
      </struct>
      <ResourceId name="Shader" typename="VkShaderEXT">9002</ResourceId>
    </chunk>
    <chunk id="1064" chunkIndex="16" name="vkCmdBindShadersEXT">
      <array name="pStages"><enum typename="VkShaderStageFlagBits">16</enum></array>
      <array name="pShaders"><ResourceId typename="VkShaderEXT">9002</ResourceId></array>
    </chunk>
    <chunk id="1085" chunkIndex="20" name="vkCmdDrawIndexed">
      <uint name="indexCount" typename="uint32_t">6</uint>
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

    payload = scan_vulkan_draw_texture_events(str(xml_path), preview_limit=0, min_textures=0)

    assert payload["summary"]["total_draw_events"] == 2
    assert payload["events"][0]["event_id"] == 14
    assert payload["events"][0]["shader_stages"] == ["vs", "ps"]

    assert payload["events"][1]["event_id"] == 20
    assert payload["events"][1]["shader_stages"] == ["ps"]
    assert payload["events"][1]["pipeline"] == 0



def test_generate_vulkan_draw_texture_scan_cli(tmp_path):
    from generate_vulkan_draw_texture_scan import main

    xml_path = tmp_path / "scan_cli.zip.xml"
    xml_path.write_text(
        """<rdc>
  <header><driver id="8">Vulkan</driver></header>
  <chunks>
    <chunk id="1061" chunkIndex="16" name="vkCmdBindIndexBuffer">
      <ResourceId name="buffer" typename="VkBuffer">343</ResourceId>
      <uint name="offset" typename="uint64_t">0</uint>
      <enum name="indexType" typename="VkIndexType" string="VK_INDEX_TYPE_UINT16">0</enum>
    </chunk>
    <chunk id="1060" chunkIndex="17" name="vkCmdBindVertexBuffers">
      <uint name="firstBinding" typename="uint32_t">0</uint>
      <uint name="bindingCount" typename="uint32_t">1</uint>
      <array name="pBuffers"><ResourceId typename="VkBuffer">339</ResourceId></array>
      <array name="pOffsets"><uint typename="uint64_t">0</uint></array>
    </chunk>
    <chunk id="1085" chunkIndex="20" name="vkCmdDrawIndexed">
      <uint name="indexCount" typename="uint32_t">36</uint>
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

    out_path = tmp_path / "scan.json"
    rc = main([
        "--xml",
        str(xml_path),
        "--out",
        str(out_path),
        "--preview-limit",
        "2",
    ])

    assert rc == 0
    payload = __import__("json").loads(out_path.read_text(encoding="utf-8"))
    assert payload["summary"]["api"] == "Vulkan"
    assert payload["events"][0]["mesh_compatible"] is True
