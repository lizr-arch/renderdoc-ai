from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from rdc_parser import ChunkInfo, RDCParser, TextureInfo, extract_textures


SYSTEM_CHUNK_INITIAL_CONTENTS = 3


def parse_initial_contents_payload(chunk_data: bytes) -> Optional[Tuple[int, bytes]]:
    if len(chunk_data) < 20:
        return None

    res_type = struct.unpack_from("<I", chunk_data, 0)[0]
    res_id = struct.unpack_from("<Q", chunk_data, 4)[0]

    if res_type not in (5, 8):
        return None

    for offset in (12, 16, 20, 24):
        if offset + 8 > len(chunk_data):
            continue
        size = struct.unpack_from("<Q", chunk_data, offset)[0]
        payload_start = offset + 8
        payload_end = payload_start + size
        if size > 0 and payload_end == len(chunk_data):
            return res_id, chunk_data[payload_start:payload_end]

    return None


def extract_payloads_from_frame_capture_data(
    frame_data: bytes, chunks: Iterable[ChunkInfo]
) -> Dict[int, bytes]:
    payloads: Dict[int, bytes] = {}
    for chunk in chunks:
        if chunk.chunk_id != SYSTEM_CHUNK_INITIAL_CONTENTS:
            continue
        start = chunk.data_offset
        end = start + chunk.length
        if start < 0 or end > len(frame_data):
            continue
        blob = frame_data[start:end]
        parsed = parse_initial_contents_payload(blob)
        if parsed:
            res_id, payload = parsed
            payloads[res_id] = payload
    return payloads


def extract_payloads_from_rdc(rdc_path: Path) -> Dict[int, bytes]:
    with RDCParser(str(rdc_path)) as parser:
        parser.parse_header()
        frame_data = parser.get_frame_capture_data()
        chunks = parser.parse_chunks(frame_data)
    return extract_payloads_from_frame_capture_data(frame_data, chunks)


def build_manifest_entries(
    textures: Iterable[TextureInfo],
    payloads: Dict[int, bytes],
    out_dir: Path,
) -> List[dict]:
    out_dir.mkdir(parents=True, exist_ok=True)
    entries: List[dict] = []
    for tex in textures:
        entry = {
            "resource_id": tex.resource_id,
            "width": tex.width,
            "height": tex.height,
            "depth": tex.depth,
            "mip_levels": tex.mip_levels,
            "array_layers": tex.array_layers,
            "format": tex.format,
            "format_name": tex.format_name,
            "status": "metadata_only",
            "reason": None,
            "file": None,
        }

        if tex.resource_id not in payloads:
            entry["reason"] = "no_initial_contents"
        else:
            entry["status"] = "payload_present"
            entry["reason"] = None

        entries.append(entry)
    return entries


def write_manifest(entries: List[dict], out_dir: Path) -> Path:
    manifest = {"textures": entries}
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def extract_textures_offline(rdc_path: Path, out_dir: Path) -> Path:
    textures = extract_textures(str(rdc_path))
    payloads = extract_payloads_from_rdc(rdc_path)
    entries = build_manifest_entries(textures, payloads, out_dir)
    return write_manifest(entries, out_dir)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Offline texture extraction (metadata-first).")
    parser.add_argument("rdc_file", help="Path to .rdc capture file")
    parser.add_argument("-o", "--out", required=True, help="Output directory")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    rdc_path = Path(args.rdc_file)
    out_dir = Path(args.out)
    if not rdc_path.exists():
        print(f"Error: File not found: {rdc_path}")
        return 1

    manifest_path = extract_textures_offline(rdc_path, out_dir)
    print(f"Wrote manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
