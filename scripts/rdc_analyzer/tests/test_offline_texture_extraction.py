from __future__ import annotations

import json
import struct
import sys
from pathlib import Path

# Allow importing scripts in this folder without package install.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import offline_extract_textures as oet  # noqa: E402
from rdc_parser import TextureInfo  # noqa: E402


def _make_texture(resource_id: int = 1) -> TextureInfo:
    return TextureInfo(
        resource_id=resource_id,
        image_type=1,
        format=37,  # VK_FORMAT_R8G8B8A8_UNORM
        width=2,
        height=2,
        depth=1,
        mip_levels=1,
        array_layers=1,
        samples=1,
        usage=0,
        chunk_offset=0,
    )


def test_metadata_only_when_no_payload(tmp_path: Path) -> None:
    textures = [_make_texture()]

    entries = oet.build_manifest_entries(textures, {}, tmp_path)

    assert len(entries) == 1
    assert entries[0]["status"] == "metadata_only"
    assert entries[0]["reason"] == "no_initial_contents"

    manifest_path = oet.write_manifest(entries, tmp_path)
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert data["textures"][0]["status"] == "metadata_only"


def test_parse_initial_contents_payload_exact_tail() -> None:
    blob = struct.pack("<IQQ", 8, 1, 4) + b"DATA"
    res_id, payload = oet.parse_initial_contents_payload(blob)
    assert res_id == 1
    assert payload == b"DATA"
