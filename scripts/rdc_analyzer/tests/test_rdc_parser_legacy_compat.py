import os
import sys
from types import SimpleNamespace

TEST_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.abspath(os.path.join(TEST_DIR, ".."))
sys.path.insert(0, SRC_DIR)

import rdc_parser as legacy
import parsers.chunk_parser as chunk_parser
import parsers.shader_extractor as shader_extractor


def test_rdcparser_uses_file_object_for_section_parser(tmp_path, monkeypatch):
    rdc_path = tmp_path / "sample.rdc"
    rdc_path.write_bytes(b"RDOC")

    observed = {}

    class FakeSectionParser:
        def __init__(self, file_obj, filepath=""):
            observed["has_tell"] = hasattr(file_obj, "tell")
            observed["filepath"] = filepath

        def parse(self):
            return SimpleNamespace(frame_capture_section=None)

        def read_section_data(self, _section):
            return b""

    monkeypatch.setattr(legacy, "SectionParser", FakeSectionParser)

    with legacy.RDCParser(str(rdc_path)) as parser:
        parser.parse_header()

    assert observed["has_tell"] is True
    assert observed["filepath"] == str(rdc_path)


def test_extract_resource_renames_uses_file_object(tmp_path, monkeypatch):
    rdc_path = tmp_path / "sample.rdc"
    rdc_path.write_bytes(b"RDOC")

    observed = {}

    class FakeSectionParser:
        def __init__(self, file_obj, filepath=""):
            observed["has_read"] = hasattr(file_obj, "read")
            observed["filepath"] = filepath

        def parse_resource_renames(self):
            return {123: "MainTex"}

    monkeypatch.setattr(legacy, "SectionParser", FakeSectionParser)

    renames = legacy.extract_resource_renames(str(rdc_path))

    assert renames == {123: "MainTex"}
    assert observed["has_read"] is True
    assert observed["filepath"] == str(rdc_path)


def test_count_vulkan_chunks_handles_missing_create_shaders_ext(monkeypatch):
    class FakeVulkanChunk:
        vkCreateShaderModule = 1019
        vkCreateImage = 1015

    monkeypatch.setattr(chunk_parser, "VulkanChunk", FakeVulkanChunk)

    parser = chunk_parser.ChunkParser()
    chunks = [SimpleNamespace(chunk_id=1019), SimpleNamespace(chunk_id=1015)]

    counts = parser.count_vulkan_chunks(chunks)

    assert counts["vkCreateShaderModule"] == 1
    assert counts["vkCreateImage"] == 1
    assert counts["vkCreateShadersEXT"] == 0


def test_shader_extractor_handles_missing_create_shaders_ext(monkeypatch):
    class FakeVulkanChunk:
        vkCreateShaderModule = 1019

    monkeypatch.setattr(shader_extractor, "VulkanChunk", FakeVulkanChunk)

    extractor = shader_extractor.ShaderExtractor()
    chunks = [SimpleNamespace(chunk_id=999, data_offset=0, length=0)]

    shaders = extractor.extract_from_chunks(b"", chunks)

    assert shaders == []
