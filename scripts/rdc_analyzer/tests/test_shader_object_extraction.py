import struct

from rdc_analyzer.parsers import ShaderExtractor, ChunkInfo, SPIRV_MAGIC


def _make_spirv_blob() -> bytes:
    header = struct.pack("<5I", SPIRV_MAGIC, 0x00010000, 0, 1, 0)
    instr = struct.pack("<I", 0x00010000)
    return header + instr


def test_extract_spirv_blobs_from_chunk_empty(tmp_path):
    """测试空数据不会提取出 Shader"""
    data = b"\x00" * 128
    chunk = ChunkInfo(chunk_id=0, flags=0, length=len(data), data_offset=0)
    
    # 使用 ShaderExtractor 的内部方法
    extractor = ShaderExtractor([chunk])
    shaders = extractor._extract_spirv_blobs(data, chunk)

    assert shaders == []


def test_extract_spirv_blobs_from_chunk_finds_one(tmp_path):
    """测试能正确找到嵌入的 SPIR-V blob"""
    blob = _make_spirv_blob()
    data = b"\x00" * 64 + blob + b"\x00" * 64
    chunk = ChunkInfo(chunk_id=0, flags=0, length=len(data), data_offset=0)
    
    # 使用 ShaderExtractor 的内部方法
    extractor = ShaderExtractor([chunk])
    shaders = extractor._extract_spirv_blobs(data, chunk)

    assert len(shaders) == 1
    assert shaders[0].is_valid_spirv


def test_extract_from_chunks_fallback_scans_unknown_chunk_ids(tmp_path):
    """未知 chunk_id 时也应能回退扫描 SPIR-V blob"""
    blob = _make_spirv_blob()
    data = b"\x00" * 32 + blob + b"\x00" * 32
    chunk = ChunkInfo(chunk_id=9999, flags=0, length=len(data), data_offset=0)

    extractor = ShaderExtractor()
    shaders = extractor.extract_from_chunks(data, [chunk])

    assert len(shaders) == 1
    assert shaders[0].is_valid_spirv
