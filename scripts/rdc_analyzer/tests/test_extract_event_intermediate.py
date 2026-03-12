import json
import sys
import zipfile
from pathlib import Path

import pytest


SCRIPT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SCRIPT_DIR))


def _write_sample_vulkan_xml(xml_path: Path, *, with_initial=True, contents_index=7):
    initial_chunk = ""
    if with_initial:
        initial_chunk = f"""
    <chunk id=\"3\" chunkIndex=\"200\" name=\"Internal::Initial Contents\">
      <enum name=\"type\" typename=\"VkResourceType\" string=\"eResDeviceMemory\">5</enum>
      <ResourceId name=\"id\" typename=\"VkDeviceMemory\">210</ResourceId>
      <uint name=\"ContentsSize\" typename=\"uint64_t\">72</uint>
      <buffer name=\"Contents\" typename=\"Byte Buffer\">{contents_index}</buffer>
    </chunk>
"""

    xml_path.write_text(
        f"""<rdc>
  <header><driver id=\"8\">Vulkan</driver></header>
  <chunks>
    <chunk id=\"1013\" chunkIndex=\"10\" name=\"vkCreateBuffer\">
      <struct name=\"CreateInfo\" typename=\"VkBufferCreateInfo\">
        <uint name=\"size\" typename=\"uint64_t\">64</uint>
      </struct>
      <ResourceId name=\"Buffer\" typename=\"VkBuffer\">901</ResourceId>
    </chunk>
    <chunk id=\"1042\" chunkIndex=\"11\" name=\"vkBindBufferMemory\">
      <ResourceId name=\"buffer\" typename=\"VkBuffer\">901</ResourceId>
      <ResourceId name=\"memory\" typename=\"VkDeviceMemory\">210</ResourceId>
      <uint name=\"memoryOffset\" typename=\"uint64_t\">8</uint>
    </chunk>
    <chunk id=\"1060\" chunkIndex=\"97\" name=\"vkCmdBindVertexBuffers\">
      <uint name=\"firstBinding\" typename=\"uint32_t\">0</uint>
      <uint name=\"bindingCount\" typename=\"uint32_t\">1</uint>
      <array name=\"pBuffers\"><ResourceId typename=\"VkBuffer\">901</ResourceId></array>
      <array name=\"pOffsets\"><uint typename=\"uint64_t\">0</uint></array>
    </chunk>
    <chunk id=\"1061\" chunkIndex=\"98\" name=\"vkCmdBindIndexBuffer\">
      <ResourceId name=\"buffer\" typename=\"VkBuffer\">901</ResourceId>
      <uint name=\"offset\" typename=\"uint64_t\">32</uint>
      <enum name=\"indexType\" typename=\"VkIndexType\" string=\"VK_INDEX_TYPE_UINT16\">0</enum>
    </chunk>
    <chunk id=\"1085\" chunkIndex=\"100\" name=\"vkCmdDrawIndexed\">
      <uint name=\"indexCount\" typename=\"uint32_t\">3</uint>
      <uint name=\"instanceCount\" typename=\"uint32_t\">1</uint>
      <uint name=\"firstIndex\" typename=\"uint32_t\">0</uint>
      <int name=\"vertexOffset\" typename=\"int32_t\">0</int>
      <uint name=\"firstInstance\" typename=\"uint32_t\">0</uint>
    </chunk>
{initial_chunk}
  </chunks>
</rdc>
""",
        encoding="utf-8",
    )


def _write_sample_zip(zip_path: Path, *, entry_name="000007", extra_entries: dict[str, bytes] | None = None):
    blob = bytearray(80)
    blob[8:40] = bytes(range(32))
    blob[40:46] = b"\x00\x00\x01\x00\x02\x00"

    with zipfile.ZipFile(zip_path, "w") as handle:
        handle.writestr(entry_name, bytes(blob))
        for name, data in (extra_entries or {}).items():
            handle.writestr(str(name), bytes(data))

def _write_sample_vulkan_shader_xml(xml_path: Path, *, with_initial=True, contents_index=7):
    initial_chunk = ""
    if with_initial:
        initial_chunk = f"""
    <chunk id=\"3\" chunkIndex=\"200\" name=\"Internal::Initial Contents\">
      <enum name=\"type\" typename=\"VkResourceType\" string=\"eResDeviceMemory\">5</enum>
      <ResourceId name=\"id\" typename=\"VkDeviceMemory\">210</ResourceId>
      <uint name=\"ContentsSize\" typename=\"uint64_t\">72</uint>
      <buffer name=\"Contents\" typename=\"Byte Buffer\">{contents_index}</buffer>
    </chunk>
"""

    xml_path.write_text(
        f"""<rdc>
  <header><driver id=\"8\">Vulkan</driver></header>
  <chunks>
    <chunk id=\"1013\" chunkIndex=\"10\" name=\"vkCreateBuffer\">
      <struct name=\"CreateInfo\" typename=\"VkBufferCreateInfo\">
        <uint name=\"size\" typename=\"uint64_t\">64</uint>
      </struct>
      <ResourceId name=\"Buffer\" typename=\"VkBuffer\">901</ResourceId>
    </chunk>
    <chunk id=\"1042\" chunkIndex=\"11\" name=\"vkBindBufferMemory\">
      <ResourceId name=\"buffer\" typename=\"VkBuffer\">901</ResourceId>
      <ResourceId name=\"memory\" typename=\"VkDeviceMemory\">210</ResourceId>
      <uint name=\"memoryOffset\" typename=\"uint64_t\">8</uint>
    </chunk>
    <chunk id=\"1019\" chunkIndex=\"80\" name=\"vkCreateShaderModule\">
      <struct name=\"CreateInfo\" typename=\"VkShaderModuleCreateInfo\">
        <uint name=\"codeSize\" typename=\"uint64_t\">4</uint>
        <buffer name=\"pCode\" typename=\"Byte Buffer\" byteLength=\"4\">1</buffer>
      </struct>
      <ResourceId name=\"ShaderModule\" typename=\"VkShaderModule\">17001</ResourceId>
    </chunk>
    <chunk id=\"1019\" chunkIndex=\"81\" name=\"vkCreateShaderModule\">
      <struct name=\"CreateInfo\" typename=\"VkShaderModuleCreateInfo\">
        <uint name=\"codeSize\" typename=\"uint64_t\">8</uint>
        <buffer name=\"pCode\" typename=\"Byte Buffer\" byteLength=\"8\">2</buffer>
      </struct>
      <ResourceId name=\"ShaderModule\" typename=\"VkShaderModule\">17002</ResourceId>
    </chunk>
    <chunk id=\"1022\" chunkIndex=\"82\" name=\"vkCreateGraphicsPipelines\">
      <ResourceId name=\"Pipeline\" typename=\"VkPipeline\">2500</ResourceId>
      <struct name=\"CreateInfo\" typename=\"VkGraphicsPipelineCreateInfo\">
        <array name=\"pStages\">
          <struct typename=\"VkPipelineShaderStageCreateInfo\">
            <enum name=\"stage\" typename=\"VkShaderStageFlagBits\" string=\"VK_SHADER_STAGE_VERTEX_BIT\">1</enum>
            <ResourceId name=\"module\" typename=\"VkShaderModule\">17001</ResourceId>
            <string name=\"pName\">main_vs</string>
          </struct>
          <struct typename=\"VkPipelineShaderStageCreateInfo\">
            <enum name=\"stage\" typename=\"VkShaderStageFlagBits\" string=\"VK_SHADER_STAGE_FRAGMENT_BIT\">16</enum>
            <ResourceId name=\"module\" typename=\"VkShaderModule\">17002</ResourceId>
            <string name=\"pName\">main_ps</string>
          </struct>
        </array>
      </struct>
    </chunk>
    <chunk id=\"1063\" chunkIndex=\"83\" name=\"vkCmdBindPipeline\">
      <enum name=\"pipelineBindPoint\" typename=\"VkPipelineBindPoint\" string=\"VK_PIPELINE_BIND_POINT_GRAPHICS\">0</enum>
      <ResourceId name=\"pipeline\" typename=\"VkPipeline\">2500</ResourceId>
    </chunk>
    <chunk id=\"1060\" chunkIndex=\"97\" name=\"vkCmdBindVertexBuffers\">
      <uint name=\"firstBinding\" typename=\"uint32_t\">0</uint>
      <uint name=\"bindingCount\" typename=\"uint32_t\">1</uint>
      <array name=\"pBuffers\"><ResourceId typename=\"VkBuffer\">901</ResourceId></array>
      <array name=\"pOffsets\"><uint typename=\"uint64_t\">0</uint></array>
    </chunk>
    <chunk id=\"1061\" chunkIndex=\"98\" name=\"vkCmdBindIndexBuffer\">
      <ResourceId name=\"buffer\" typename=\"VkBuffer\">901</ResourceId>
      <uint name=\"offset\" typename=\"uint64_t\">32</uint>
      <enum name=\"indexType\" typename=\"VkIndexType\" string=\"VK_INDEX_TYPE_UINT16\">0</enum>
    </chunk>
    <chunk id=\"1085\" chunkIndex=\"100\" name=\"vkCmdDrawIndexed\">
      <uint name=\"indexCount\" typename=\"uint32_t\">3</uint>
      <uint name=\"instanceCount\" typename=\"uint32_t\">1</uint>
      <uint name=\"firstIndex\" typename=\"uint32_t\">0</uint>
      <int name=\"vertexOffset\" typename=\"int32_t\">0</int>
      <uint name=\"firstInstance\" typename=\"uint32_t\">0</uint>
    </chunk>
{initial_chunk}
  </chunks>
</rdc>
""",
        encoding="utf-8",
    )




def test_build_event_state_from_bindings_for_writer_contract():
    try:
        from extract_event_intermediate import build_event_state_from_bindings
    except ImportError as exc:
        pytest.fail(f"extract_event_intermediate missing: {exc}")

    bindings = {
        "index_buffer": {
            "resource_id": 343,
            "byte_offset": 0,
            "index_format": "uint16",
        },
        "vertex_buffers": [
            {"resource_id": 339, "byte_offset": 0},
            {"resource_id": 341, "byte_offset": 16},
        ],
    }

    state = build_event_state_from_bindings(bindings)

    assert state.index_buffer is not None
    assert state.index_buffer.resource_id == 343
    assert len(state.vertex_buffers) == 2
    assert state.vertex_buffers[0].resource_id == 339
    assert state.vertex_buffers[1].byte_offset == 16


def test_write_intermediate_emits_vertex_and_index_bin(tmp_path):
    try:
        from extract_event_intermediate import write_intermediate_with_mesh_bytes
    except ImportError as exc:
        pytest.fail(f"extract_event_intermediate missing write helper: {exc}")

    intermediate_path = write_intermediate_with_mesh_bytes(
        out_dir=str(tmp_path),
        mesh_info={
            "vertex_layout": [
                {
                    "semantic": "POSITION",
                    "format": "float3",
                    "offset": 0,
                    "stride": 12,
                }
            ],
            "vertex_count": 3,
            "index_count": 3,
            "index_format": "uint16",
        },
        vertex_bytes=(
            b"\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x80\x3f\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x80\x3f\x00\x00\x00\x00"
        ),
        index_bytes=b"\x00\x00\x01\x00\x02\x00",
    )

    mesh_json = Path(intermediate_path) / "mesh" / "mesh.json"
    vertex_bin = Path(intermediate_path) / "mesh" / "vertex.bin"
    index_bin = Path(intermediate_path) / "mesh" / "index.bin"

    assert mesh_json.exists()
    assert vertex_bin.exists()
    assert index_bin.exists()

    mesh = json.loads(mesh_json.read_text(encoding="utf-8"))["mesh"]
    assert mesh["vertex_count"] == 3
    assert mesh["index_count"] == 3
    assert mesh["vertex_layout"][0]["semantic"] == "POSITION"


def test_extract_vulkan_event_intermediate_end_to_end(tmp_path):
    try:
        from extract_event_intermediate import extract_vulkan_event_intermediate
    except ImportError as exc:
        pytest.fail(f"extract_event_intermediate missing cli core: {exc}")

    xml_path = tmp_path / "sample.zip.xml"
    zip_path = tmp_path / "sample.zip"
    out_dir = tmp_path / "out"

    _write_sample_vulkan_xml(xml_path)
    _write_sample_zip(zip_path)

    intermediate_path = extract_vulkan_event_intermediate(
        xml_path=str(xml_path),
        zip_path=str(zip_path),
        event_id=100,
        out_dir=str(out_dir),
    )

    mesh_dir = Path(intermediate_path) / "mesh"
    vertex_bin = mesh_dir / "vertex.bin"
    index_bin = mesh_dir / "index.bin"
    manifest_path = out_dir / "event_100" / "manifest.json"

    assert vertex_bin.exists()
    assert index_bin.exists()
    assert manifest_path.exists()

    assert vertex_bin.read_bytes() == bytes(range(32))
    assert index_bin.read_bytes() == b"\x00\x00\x01\x00\x02\x00"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["event_id"] == 100
    assert manifest["api"] == "Vulkan"
    assert manifest["buffers"]["index"]["zip_entry"] == "000007"




def test_extract_vulkan_event_intermediate_exports_shader_blobs(tmp_path):
    from extract_event_intermediate import extract_vulkan_event_intermediate

    xml_path = tmp_path / "sample_shader.zip.xml"
    zip_path = tmp_path / "sample_shader.zip"
    out_dir = tmp_path / "out_shader"

    _write_sample_vulkan_shader_xml(xml_path)
    _write_sample_zip(
        zip_path,
        extra_entries={
            "000001": b"ABCD",
            "000002": b"12345678TAIL",
        },
    )

    intermediate_path = extract_vulkan_event_intermediate(
        xml_path=str(xml_path),
        zip_path=str(zip_path),
        event_id=100,
        out_dir=str(out_dir),
    )

    shaders_dir = Path(intermediate_path) / "shaders"
    vs_bin = shaders_dir / "vs.bin"
    ps_bin = shaders_dir / "ps.bin"
    vs_json = shaders_dir / "vs.json"
    ps_json = shaders_dir / "ps.json"

    assert vs_bin.exists()
    assert ps_bin.exists()
    assert vs_json.exists()
    assert ps_json.exists()

    assert vs_bin.read_bytes() == b"ABCD"
    assert ps_bin.read_bytes() == b"12345678"

    vs_info = json.loads(vs_json.read_text(encoding="utf-8"))["shader"]
    ps_info = json.loads(ps_json.read_text(encoding="utf-8"))["shader"]
    assert vs_info["entry"] == "main_vs"
    assert ps_info["entry"] == "main_ps"
    assert vs_info["bytecode_format"] == "spirv"
    assert ps_info["bytecode_format"] == "spirv"
    assert vs_info["source_kind"] == "vulkan_shader_module"
    assert ps_info["source_kind"] == "vulkan_shader_module"

    manifest = json.loads((Path(intermediate_path).parent / "manifest.json").read_text(encoding="utf-8"))
    shader_sources = manifest["resource_bindings"]["shader_sources"]
    assert [entry["source_kind"] for entry in shader_sources] == ["vulkan_shader_module", "vulkan_shader_module"]

def test_extract_vulkan_event_intermediate_exports_vulkan_texture_blob(tmp_path, monkeypatch):
    import extract_event_intermediate as extractor

    xml_path = tmp_path / "sample.zip.xml"
    zip_path = tmp_path / "sample.zip"
    out_dir = tmp_path / "out"

    _write_sample_vulkan_xml(xml_path)
    _write_sample_zip(zip_path)

    original_extract = extractor.extract_vulkan_bindings_for_event

    def _inject_texture_binding(xml_source, event):
        bindings = original_extract(xml_source, event)
        bindings["textures"] = [
            {
                "slot": "set0.binding0",
                "sampler": "set0.binding1",
                "texture_id": 42,
                "path": "tex_42.bin",
                "format": "",
                "width": 0,
                "height": 0,
                "memory_buffer_index": 7,
                "memory_offset": 8,
                "memory_contents_size": 16,
            }
        ]
        return bindings

    monkeypatch.setattr(extractor, "extract_vulkan_bindings_for_event", _inject_texture_binding)

    intermediate_path = extractor.extract_vulkan_event_intermediate(
        xml_path=str(xml_path),
        zip_path=str(zip_path),
        event_id=100,
        out_dir=str(out_dir),
    )

    texture_bin = Path(intermediate_path) / "textures" / "tex_42.bin"
    assert texture_bin.exists()
    assert texture_bin.read_bytes() == bytes(range(16))

    material_json = Path(intermediate_path) / "materials" / "material.json"
    material = json.loads(material_json.read_text(encoding="utf-8"))["material"]
    assert material["textures"][0]["source_kind"] == "vulkan_device_memory_raw"


def test_extract_vulkan_event_intermediate_event_not_found(tmp_path):
    from extract_event_intermediate import extract_vulkan_event_intermediate

    xml_path = tmp_path / "sample.zip.xml"
    zip_path = tmp_path / "sample.zip"

    _write_sample_vulkan_xml(xml_path)
    _write_sample_zip(zip_path)

    with pytest.raises(ValueError, match="event 999 not found"):
        extract_vulkan_event_intermediate(
            xml_path=str(xml_path),
            zip_path=str(zip_path),
            event_id=999,
            out_dir=str(tmp_path / "out"),
        )


def test_extract_vulkan_event_intermediate_missing_initial_contents(tmp_path):
    from extract_event_intermediate import extract_vulkan_event_intermediate

    xml_path = tmp_path / "sample.zip.xml"
    zip_path = tmp_path / "sample.zip"

    _write_sample_vulkan_xml(xml_path, with_initial=False)
    _write_sample_zip(zip_path)

    with pytest.raises(ValueError, match="no Internal::Initial Contents mapping"):
        extract_vulkan_event_intermediate(
            xml_path=str(xml_path),
            zip_path=str(zip_path),
            event_id=100,
            out_dir=str(tmp_path / "out"),
        )


def test_extract_vulkan_event_intermediate_missing_zip_entry(tmp_path):
    from extract_event_intermediate import extract_vulkan_event_intermediate

    xml_path = tmp_path / "sample.zip.xml"
    zip_path = tmp_path / "sample.zip"

    _write_sample_vulkan_xml(xml_path, with_initial=True, contents_index=8)
    _write_sample_zip(zip_path, entry_name="000007")

    with pytest.raises(FileNotFoundError, match="buffer_index 8"):
        extract_vulkan_event_intermediate(
            xml_path=str(xml_path),
            zip_path=str(zip_path),
            event_id=100,
            out_dir=str(tmp_path / "out"),
        )



def _write_sample_d3d11_xml(xml_path: Path):
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
      <array name="pStrides"><uint typename="uint32_t">12</uint></array>
      <array name="pOffsets"><uint typename="uint32_t">0</uint></array>
    </chunk>
    <chunk id="1034" chunkIndex="92" name="ID3D11DeviceContext::IASetIndexBuffer">
      <ResourceId name="pIndexBuffer" typename="ID3D11Buffer *">308</ResourceId>
      <enum name="Format" typename="DXGI_FORMAT" string="DXGI_FORMAT_R16_UINT">57</enum>
      <uint name="Offset" typename="uint32_t">0</uint>
    </chunk>
    <chunk id="1071" chunkIndex="100" name="ID3D11DeviceContext::DrawIndexed">
      <uint name="IndexCount" typename="uint32_t">3</uint>
      <uint name="StartIndexLocation" typename="uint32_t">0</uint>
      <int name="BaseVertexLocation" typename="int32_t">0</int>
    </chunk>
  </chunks>
</rdc>
""",
        encoding="utf-8",
    )


def _write_sample_d3d11_zip(zip_path: Path, *, with_index=True):
    with zipfile.ZipFile(zip_path, "w") as handle:
        handle.writestr("000033", bytes(range(36)))
        if with_index:
            handle.writestr("000034", b"\x00\x00\x01\x00\x02\x00")


def test_extract_d3d11_event_intermediate_end_to_end(tmp_path):
    from extract_event_intermediate import extract_event_intermediate

    xml_path = tmp_path / "sample_d3d11.zip.xml"
    zip_path = tmp_path / "sample_d3d11.zip"
    out_dir = tmp_path / "out_d3d11"

    _write_sample_d3d11_xml(xml_path)
    _write_sample_d3d11_zip(zip_path)

    intermediate_path = extract_event_intermediate(
        xml_path=str(xml_path),
        zip_path=str(zip_path),
        event_id=100,
        out_dir=str(out_dir),
    )

    mesh_dir = Path(intermediate_path) / "mesh"
    vertex_bin = mesh_dir / "vertex.bin"
    index_bin = mesh_dir / "index.bin"
    manifest_path = out_dir / "event_100" / "manifest.json"

    assert vertex_bin.exists()
    assert index_bin.exists()
    assert manifest_path.exists()

    assert len(vertex_bin.read_bytes()) == 36
    assert index_bin.read_bytes() == b"\x00\x00\x01\x00\x02\x00"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["api"] == "D3D11"
    assert manifest["buffers"]["vertex"]["zip_entry"] == "000033"
    assert manifest["buffers"]["index"]["zip_entry"] == "000034"


def test_extract_d3d11_event_intermediate_missing_zip_entry(tmp_path):
    from extract_event_intermediate import extract_event_intermediate

    xml_path = tmp_path / "sample_d3d11.zip.xml"
    zip_path = tmp_path / "sample_d3d11.zip"

    _write_sample_d3d11_xml(xml_path)
    _write_sample_d3d11_zip(zip_path, with_index=False)

    with pytest.raises(FileNotFoundError, match="buffer_index 34"):
        extract_event_intermediate(
            xml_path=str(xml_path),
            zip_path=str(zip_path),
            event_id=100,
            out_dir=str(tmp_path / "out"),
        )



def test_write_intermediate_preserves_shader_metadata(tmp_path):
    from extract_event_intermediate import write_intermediate_with_mesh_bytes
    from xmlzip_event_extractor import EventState

    state = EventState(
        index_buffer=None,
        vertex_buffers=[],
        textures=[],
        shaders=[
            {
                "stage": "vs",
                "bytecode_format": "spirv",
                "entry": "main_vs",
                "disassembly": "OpEntryPoint Vertex %main_vs",
                "path": "vs.bin",
                "source_kind": "vulkan_shader_object",
                "resource_id": 1234,
                "zip_entry": "000123",
                "buffer_index": 123,
                "byte_length": 4,
            }
        ],
    )

    intermediate_path = write_intermediate_with_mesh_bytes(
        out_dir=str(tmp_path),
        mesh_info={
            "vertex_layout": [],
            "vertex_count": 0,
            "index_count": 0,
            "index_format": "uint16",
        },
        vertex_bytes=b"",
        index_bytes=b"",
        state=state,
        shader_blobs={"vs.bin": b"\x03\x02\x23\x07"},
    )

    shader_json = Path(intermediate_path) / "shaders" / "vs.json"
    shader_bin = Path(intermediate_path) / "shaders" / "vs.bin"

    shader = json.loads(shader_json.read_text(encoding="utf-8"))["shader"]
    assert shader["stage"] == "vs"
    assert shader["bytecode_format"] == "spirv"
    assert shader["entry"] == "main_vs"
    assert "OpEntryPoint" in shader["disassembly"]
    assert shader["source_kind"] == "vulkan_shader_object"
    assert shader["source_resource_id"] == 1234
    assert shader["zip_entry"] == "000123"
    assert shader["buffer_index"] == 123
    assert shader["byte_length"] == 4
    assert shader["path"] == "vs.bin"
    assert shader_bin.read_bytes() == b"\x03\x02\x23\x07"
