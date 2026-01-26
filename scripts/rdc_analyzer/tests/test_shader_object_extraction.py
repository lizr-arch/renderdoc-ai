import struct

from rdc_analyzer.rdc_parser import RDCParser, ChunkInfo, SPIRV_MAGIC


def _make_spirv_blob() -> bytes:
    header = struct.pack("<5I", SPIRV_MAGIC, 0x00010000, 0, 1, 0)
    instr = struct.pack("<I", 0x00010000)
    return header + instr


def test_extract_spirv_blobs_from_chunk_empty(tmp_path):
    data = b"\x00" * 128
    dummy = tmp_path / "dummy.rdc"
    dummy.write_bytes(b"\x00")

    parser = RDCParser(str(dummy))
    chunk = ChunkInfo(chunk_id=0, flags=0, length=len(data), data_offset=0)
    shaders = parser._extract_spirv_blobs_from_chunk(data, chunk)

    assert shaders == []


def test_extract_spirv_blobs_from_chunk_finds_one(tmp_path):
    blob = _make_spirv_blob()
    data = b"\x00" * 64 + blob + b"\x00" * 64
    dummy = tmp_path / "dummy.rdc"
    dummy.write_bytes(b"\x00")

    parser = RDCParser(str(dummy))
    chunk = ChunkInfo(chunk_id=0, flags=0, length=len(data), data_offset=0)
    shaders = parser._extract_spirv_blobs_from_chunk(data, chunk)

    assert len(shaders) == 1
    assert shaders[0].is_valid_spirv
