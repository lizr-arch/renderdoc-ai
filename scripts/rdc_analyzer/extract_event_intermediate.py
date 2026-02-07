import argparse
import json
from pathlib import Path
import struct
import zipfile

from parsers.zipxml_event_parser import (
    build_d3d11_buffer_data_map,
    build_vulkan_buffer_memory_maps,
    detect_capture_api,
    extract_d3d11_bindings_for_event,
    extract_vulkan_bindings_for_event,
)
from xmlzip_event_extractor import BufferBinding, EventState, write_intermediate


_SCHEMA_DIR = Path(__file__).resolve().parent / "schema"


def build_event_state_from_bindings(bindings):
    index_info = bindings.get("index_buffer") or {}
    index_buffer = None
    if index_info:
        index_buffer = BufferBinding(
            resource_id=int(index_info.get("resource_id", 0)),
            byte_offset=int(index_info.get("byte_offset", 0)),
            byte_size=int(index_info.get("byte_size", 0)),
        )

    vertex_buffers = []
    for entry in bindings.get("vertex_buffers", []):
        vertex_buffers.append(
            BufferBinding(
                resource_id=int(entry.get("resource_id", 0)),
                byte_offset=int(entry.get("byte_offset", 0)),
                byte_size=int(entry.get("byte_size", 0)),
            )
        )

    return EventState(
        index_buffer=index_buffer,
        vertex_buffers=vertex_buffers,
        textures=[],
        shaders=[],
    )


def _index_stride(index_format: str) -> int:
    if index_format == "uint32":
        return 4
    return 2


def _resolve_zip_entry_name(buffer_index: int, names: set[str]) -> str | None:
    candidates = [
        f"{buffer_index:06d}",
        f"buffers/buffer{buffer_index}",
        f"buffer{buffer_index}",
    ]
    for candidate in candidates:
        if candidate in names:
            return candidate
    return None


def _slice_bytes(data: bytes, start: int, size: int) -> bytes:
    if size <= 0:
        return b""
    if start < 0:
        start = 0
    if start >= len(data):
        return b""
    end = min(len(data), start + size)
    return data[start:end]


def _decode_indices(index_bytes: bytes, index_format: str) -> list[int]:
    stride = _index_stride(index_format)
    if stride <= 0:
        return []
    count = len(index_bytes) // stride
    if count <= 0:
        return []

    fmt = "<I" if index_format == "uint32" else "<H"
    values = []
    for index in range(count):
        values.append(struct.unpack_from(fmt, index_bytes, index * stride)[0])
    return values


def _guess_vertex_stride(vertex_blob_size: int, min_vertex_count: int) -> int:
    if vertex_blob_size <= 0 or min_vertex_count <= 0:
        return 0

    common_candidates = [12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 56, 64]
    for stride in common_candidates:
        if vertex_blob_size % stride != 0:
            continue
        if vertex_blob_size // stride >= min_vertex_count:
            return stride
    return 0


def _assert_type(value, expected: str, path: str):
    if expected == "object":
        if not isinstance(value, dict):
            raise ValueError(f"{path}: expected object")
        return
    if expected == "array":
        if not isinstance(value, list):
            raise ValueError(f"{path}: expected array")
        return
    if expected == "string":
        if not isinstance(value, str):
            raise ValueError(f"{path}: expected string")
        return
    if expected == "integer":
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{path}: expected integer")
        return
    if expected == "number":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"{path}: expected number")
        return
    if expected == "boolean":
        if not isinstance(value, bool):
            raise ValueError(f"{path}: expected boolean")
        return
    if expected == "null":
        if value is not None:
            raise ValueError(f"{path}: expected null")
        return
    raise ValueError(f"{path}: unsupported schema type {expected!r}")


def _validate_schema(schema, data, path="root"):
    expected_type = schema.get("type")
    if expected_type:
        if isinstance(expected_type, list):
            matched = False
            last_error = None
            for type_name in expected_type:
                try:
                    _assert_type(data, type_name, path)
                    matched = True
                    break
                except ValueError as exc:
                    last_error = exc
            if not matched:
                if last_error is not None:
                    raise last_error
                raise ValueError(f"{path}: no matching type in {expected_type!r}")
        else:
            _assert_type(data, expected_type, path)

    if "enum" in schema and data not in schema["enum"]:
        raise ValueError(f"{path}: value not in enum")

    if expected_type == "object":
        for required in schema.get("required", []):
            if required not in data:
                raise ValueError(f"{path}: missing required field {required}")
        for key, subschema in schema.get("properties", {}).items():
            if key in data:
                _validate_schema(subschema, data[key], f"{path}.{key}")

    if expected_type == "array":
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(data):
                _validate_schema(item_schema, item, f"{path}[{index}]")


def validate_json_file(json_path: Path, schema_path: Path):
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    _validate_schema(schema, payload)


def validate_intermediate_tree(event_root: Path):
    mesh_json = event_root / "intermediate" / "mesh" / "mesh.json"
    material_json = event_root / "intermediate" / "materials" / "material.json"
    manifest_json = event_root / "manifest.json"

    validate_json_file(mesh_json, _SCHEMA_DIR / "intermediate_mesh.schema.json")
    validate_json_file(material_json, _SCHEMA_DIR / "intermediate_material.schema.json")
    validate_json_file(manifest_json, _SCHEMA_DIR / "intermediate_manifest.schema.json")

    shader_dir = event_root / "intermediate" / "shaders"
    if shader_dir.exists():
        for shader_json in shader_dir.glob("*.json"):
            validate_json_file(shader_json, _SCHEMA_DIR / "intermediate_shader.schema.json")


def _resolve_memory_blob_for_buffer(zip_handle, zip_names, buffer_memory_map, memory_initial_map, buffer_id: int):
    memory_binding = buffer_memory_map.get(buffer_id)
    if not memory_binding:
        raise ValueError(f"buffer {buffer_id} has no vkBindBufferMemory mapping")

    memory_id = int(memory_binding.get("memory_id", 0))
    memory_initial = memory_initial_map.get(memory_id)
    if not memory_initial:
        raise ValueError(f"memory {memory_id} has no Internal::Initial Contents mapping")

    buffer_index = int(memory_initial.get("buffer_index", -1))
    zip_entry = _resolve_zip_entry_name(buffer_index, zip_names)
    if zip_entry is None:
        raise FileNotFoundError(f"zip entry for buffer_index {buffer_index} not found")

    data = zip_handle.read(zip_entry)
    return memory_binding, memory_initial, zip_entry, data


def extract_vulkan_event_intermediate(xml_path, zip_path, event_id, out_dir, vertex_stride: int = 0):
    xml_path = str(xml_path)
    zip_path = str(zip_path)
    event_id = int(event_id)

    bindings = extract_vulkan_bindings_for_event(xml_path, event_id)
    draw = bindings.get("draw") or {}

    index_binding = bindings.get("index_buffer")
    if not index_binding:
        raise ValueError(f"event {event_id} has no index buffer binding")

    vertex_bindings = list(bindings.get("vertex_buffers") or [])
    if not vertex_bindings:
        raise ValueError(f"event {event_id} has no vertex buffer binding")

    buffer_memory_map, memory_initial_map, buffer_sizes = build_vulkan_buffer_memory_maps(xml_path)

    index_format = index_binding.get("index_format", "uint16")
    index_stride = _index_stride(index_format)
    draw_first_index = int(draw.get("first_index", 0))
    draw_index_count = int(draw.get("index_count", 0))

    with zipfile.ZipFile(zip_path, "r") as zip_handle:
        zip_names = set(zip_handle.namelist())

        ib_binding, ib_initial, ib_entry, ib_blob = _resolve_memory_blob_for_buffer(
            zip_handle,
            zip_names,
            buffer_memory_map,
            memory_initial_map,
            int(index_binding.get("resource_id", 0)),
        )

        ib_start = int(ib_binding.get("memory_offset", 0)) + int(index_binding.get("byte_offset", 0))
        ib_start += draw_first_index * index_stride

        ib_size = draw_index_count * index_stride
        if ib_size <= 0:
            ib_size = int(index_binding.get("byte_size", 0))
        if ib_size <= 0:
            ib_size = max(0, len(ib_blob) - ib_start)

        index_bytes = _slice_bytes(ib_blob, ib_start, ib_size)

        vertex_binding = dict(vertex_bindings[0])
        vb_binding, vb_initial, vb_entry, vb_blob = _resolve_memory_blob_for_buffer(
            zip_handle,
            zip_names,
            buffer_memory_map,
            memory_initial_map,
            int(vertex_binding.get("resource_id", 0)),
        )

        vb_start = int(vb_binding.get("memory_offset", 0)) + int(vertex_binding.get("byte_offset", 0))
        vb_resource_size = int(buffer_sizes.get(int(vertex_binding.get("resource_id", 0)), 0))

        vb_size = int(vertex_binding.get("byte_size", 0))
        if vb_size <= 0:
            if vb_entry == ib_entry and ib_start > vb_start:
                vb_size = ib_start - vb_start
            elif vb_resource_size > 0:
                vb_size = max(0, vb_resource_size - int(vertex_binding.get("byte_offset", 0)))
            else:
                vb_size = max(0, len(vb_blob) - vb_start)

        vertex_bytes = _slice_bytes(vb_blob, vb_start, vb_size)

    decoded_indices = _decode_indices(index_bytes, index_format)
    vertex_offset = int(draw.get("vertex_offset", 0))
    if decoded_indices:
        min_index = min(decoded_indices) + vertex_offset
        max_index = max(decoded_indices) + vertex_offset
        min_index = max(0, min_index)
        max_index = max(min_index, max_index)
        estimated_vertex_count = max_index - min_index + 1
    else:
        estimated_vertex_count = 0

    layout_source = "none"
    if vertex_stride <= 0:
        vertex_stride = _guess_vertex_stride(len(vertex_bytes), estimated_vertex_count)
        if vertex_stride > 0:
            layout_source = "heuristic"
    else:
        layout_source = "cli"

    vertex_layout = []
    vertex_count = estimated_vertex_count
    if vertex_stride > 0:
        vertex_layout = [
            {
                "semantic": "POSITION",
                "format": "float3",
                "offset": 0,
                "stride": int(vertex_stride),
            }
        ]
        vertex_count = len(vertex_bytes) // int(vertex_stride)

    index_binding["byte_size"] = len(index_bytes)
    vertex_binding["byte_size"] = len(vertex_bytes)

    state = build_event_state_from_bindings(
        {
            "index_buffer": index_binding,
            "vertex_buffers": [vertex_binding],
        }
    )

    event_root = Path(out_dir) / f"event_{event_id}"
    intermediate_path = write_intermediate_with_mesh_bytes(
        out_dir=str(event_root),
        mesh_info={
            "vertex_layout": vertex_layout,
            "vertex_count": int(vertex_count),
            "index_count": len(decoded_indices) if decoded_indices else draw_index_count,
            "index_format": index_format,
            "topology": "triangle_list",
        },
        vertex_bytes=vertex_bytes,
        index_bytes=index_bytes,
        state=state,
    )

    manifest_path = event_root / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    manifest.update(
        {
            "schema_version": "1.0",
            "schema_path": "schema/intermediate_manifest.schema.json",
            "event_id": event_id,
            "api": "Vulkan",
            "sources": {
                "zip_xml": str(xml_path),
                "zip_bin": str(zip_path),
            },
            "buffers": {
                "index": {
                    "resource_id": int(index_binding.get("resource_id", 0)),
                    "memory_id": int(ib_binding.get("memory_id", 0)),
                    "memory_offset": int(ib_binding.get("memory_offset", 0)),
                    "zip_entry": ib_entry,
                    "byte_offset": int(index_binding.get("byte_offset", 0)),
                    "byte_size": len(index_bytes),
                },
                "vertex": {
                    "resource_id": int(vertex_binding.get("resource_id", 0)),
                    "memory_id": int(vb_binding.get("memory_id", 0)),
                    "memory_offset": int(vb_binding.get("memory_offset", 0)),
                    "zip_entry": vb_entry,
                    "byte_offset": int(vertex_binding.get("byte_offset", 0)),
                    "byte_size": len(vertex_bytes),
                    "layout_source": layout_source,
                },
            },
        }
    )
    manifest.setdefault("texture_decode", [])
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    validate_intermediate_tree(event_root)
    return intermediate_path



def _encode_indices(indices: list[int], index_format: str) -> bytes:
    if not indices:
        return b""
    fmt = "<I" if index_format == "uint32" else "<H"
    out = bytearray()
    for value in indices:
        out += struct.pack(fmt, int(value))
    return bytes(out)


def _resolve_d3d11_buffer_blob_for_resource(zip_handle, zip_names, resource_map, resource_id: int):
    entry = resource_map.get(resource_id)
    if not entry:
        raise ValueError(f"buffer {resource_id} has no D3D11 data mapping")

    buffer_index = int(entry.get("buffer_index", -1))
    zip_entry = _resolve_zip_entry_name(buffer_index, zip_names)
    if zip_entry is None:
        raise FileNotFoundError(f"zip entry for buffer_index {buffer_index} not found")

    data = zip_handle.read(zip_entry)
    return entry, zip_entry, data


def extract_d3d11_event_intermediate(xml_path, zip_path, event_id, out_dir, vertex_stride: int = 0):
    xml_path = str(xml_path)
    zip_path = str(zip_path)
    event_id = int(event_id)

    bindings = extract_d3d11_bindings_for_event(xml_path, event_id)
    draw = bindings.get("draw") or {}

    index_binding = bindings.get("index_buffer")
    if not index_binding:
        raise ValueError(f"event {event_id} has no index buffer binding")

    vertex_bindings = list(bindings.get("vertex_buffers") or [])
    if not vertex_bindings:
        raise ValueError(f"event {event_id} has no vertex buffer binding")

    resource_map = build_d3d11_buffer_data_map(xml_path, upto_event_id=event_id)

    index_format = index_binding.get("index_format", "uint16")
    index_stride = _index_stride(index_format)
    draw_first_index = int(draw.get("start_index_location", 0))
    draw_index_count = int(draw.get("index_count", 0))
    base_vertex_location = int(draw.get("base_vertex_location", 0))

    with zipfile.ZipFile(zip_path, "r") as zip_handle:
        zip_names = set(zip_handle.namelist())

        ib_info, ib_entry, ib_blob = _resolve_d3d11_buffer_blob_for_resource(
            zip_handle,
            zip_names,
            resource_map,
            int(index_binding.get("resource_id", 0)),
        )

        ib_start = int(index_binding.get("byte_offset", 0)) + draw_first_index * index_stride
        ib_size = draw_index_count * index_stride
        if ib_size <= 0:
            mapped_size = int(ib_info.get("byte_length", 0))
            ib_size = max(0, mapped_size - ib_start)
        index_bytes = _slice_bytes(ib_blob, ib_start, ib_size)

        decoded_indices = _decode_indices(index_bytes, index_format)
        if decoded_indices and base_vertex_location != 0:
            adjusted = [idx + base_vertex_location for idx in decoded_indices]
            if min(adjusted) < 0:
                raise ValueError(
                    f"D3D11 base vertex makes index negative (base={base_vertex_location})"
                )
            decoded_indices = adjusted
            index_bytes = _encode_indices(decoded_indices, index_format)

        vertex_binding = dict(vertex_bindings[0])
        vb_info, vb_entry, vb_blob = _resolve_d3d11_buffer_blob_for_resource(
            zip_handle,
            zip_names,
            resource_map,
            int(vertex_binding.get("resource_id", 0)),
        )

        vb_start = int(vertex_binding.get("byte_offset", 0))
        vb_mapped_size = int(vb_info.get("byte_length", 0))

        if vertex_stride <= 0:
            if int(vertex_binding.get("stride", 0)) > 0:
                vertex_stride = int(vertex_binding.get("stride", 0))
                layout_source = "iaset"
            else:
                layout_source = "none"
        else:
            layout_source = "cli"

        if vertex_stride <= 0 and decoded_indices:
            min_vertex_count = max(decoded_indices) + 1
            vertex_stride = _guess_vertex_stride(max(0, vb_mapped_size - vb_start), min_vertex_count)
            if vertex_stride > 0:
                layout_source = "heuristic"

        if decoded_indices and vertex_stride > 0:
            required_vertex_count = max(decoded_indices) + 1
            vb_size = required_vertex_count * vertex_stride
            available = max(0, vb_mapped_size - vb_start)
            if available > 0:
                vb_size = min(vb_size, available)
        else:
            vb_size = max(0, vb_mapped_size - vb_start)
            if vb_size <= 0:
                vb_size = max(0, len(vb_blob) - vb_start)

        vertex_bytes = _slice_bytes(vb_blob, vb_start, vb_size)

    if not decoded_indices:
        decoded_indices = _decode_indices(index_bytes, index_format)

    vertex_layout = []
    if vertex_stride > 0:
        vertex_layout = [
            {
                "semantic": "POSITION",
                "format": "float3",
                "offset": 0,
                "stride": int(vertex_stride),
            }
        ]
        vertex_count = len(vertex_bytes) // int(vertex_stride)
    else:
        vertex_count = max(decoded_indices) + 1 if decoded_indices else 0

    index_binding["byte_size"] = len(index_bytes)
    vertex_binding["byte_size"] = len(vertex_bytes)

    state = build_event_state_from_bindings(
        {
            "index_buffer": index_binding,
            "vertex_buffers": [vertex_binding],
        }
    )

    event_root = Path(out_dir) / f"event_{event_id}"
    intermediate_path = write_intermediate_with_mesh_bytes(
        out_dir=str(event_root),
        mesh_info={
            "vertex_layout": vertex_layout,
            "vertex_count": int(vertex_count),
            "index_count": len(decoded_indices) if decoded_indices else draw_index_count,
            "index_format": index_format,
            "topology": "triangle_list",
        },
        vertex_bytes=vertex_bytes,
        index_bytes=index_bytes,
        state=state,
    )

    manifest_path = event_root / "manifest.json"
    manifest = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    manifest.update(
        {
            "schema_version": "1.0",
            "schema_path": "schema/intermediate_manifest.schema.json",
            "event_id": event_id,
            "api": "D3D11",
            "sources": {
                "zip_xml": str(xml_path),
                "zip_bin": str(zip_path),
            },
            "buffers": {
                "index": {
                    "resource_id": int(index_binding.get("resource_id", 0)),
                    "memory_id": 0,
                    "memory_offset": 0,
                    "zip_entry": ib_entry,
                    "byte_offset": int(index_binding.get("byte_offset", 0)),
                    "byte_size": len(index_bytes),
                    "source": ib_info.get("source", "unknown"),
                },
                "vertex": {
                    "resource_id": int(vertex_binding.get("resource_id", 0)),
                    "memory_id": 0,
                    "memory_offset": 0,
                    "zip_entry": vb_entry,
                    "byte_offset": int(vertex_binding.get("byte_offset", 0)),
                    "byte_size": len(vertex_bytes),
                    "layout_source": layout_source,
                    "source": vb_info.get("source", "unknown"),
                },
            },
        }
    )
    manifest.setdefault("texture_decode", [])
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    validate_intermediate_tree(event_root)
    return intermediate_path


def extract_event_intermediate(xml_path, zip_path, event_id, out_dir, vertex_stride: int = 0):
    api = detect_capture_api(str(xml_path))
    if api == "Vulkan":
        return extract_vulkan_event_intermediate(
            xml_path=xml_path,
            zip_path=zip_path,
            event_id=event_id,
            out_dir=out_dir,
            vertex_stride=vertex_stride,
        )
    if api == "D3D11":
        return extract_d3d11_event_intermediate(
            xml_path=xml_path,
            zip_path=zip_path,
            event_id=event_id,
            out_dir=out_dir,
            vertex_stride=vertex_stride,
        )
    raise NotImplementedError(
        f"offline event extraction not implemented for API: {api}. Supported: Vulkan, D3D11"
    )

def write_intermediate_with_mesh_bytes(out_dir, mesh_info, vertex_bytes, index_bytes, state=None):
    if state is None:
        state = EventState(index_buffer=None, vertex_buffers=[], textures=[], shaders=[])

    write_intermediate(
        out_dir=out_dir,
        state=state,
        buffers={},
        shaders={},
        textures={},
    )

    intermediate_path = Path(out_dir) / "intermediate"
    mesh_dir = intermediate_path / "mesh"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    mesh_payload = {
        "schema_version": "1.0",
        "schema_path": "schema/intermediate_mesh.schema.json",
        "mesh": {
            "axis": "unknown",
            "unit_scale": 1.0,
            "topology": mesh_info.get("topology", "triangle_list"),
            "vertex_layout": list(mesh_info.get("vertex_layout", [])),
            "index_format": mesh_info.get("index_format", "uint16"),
            "vertex_count": int(mesh_info.get("vertex_count", 0)),
            "index_count": int(mesh_info.get("index_count", 0)),
        },
    }

    (mesh_dir / "mesh.json").write_text(json.dumps(mesh_payload, indent=2), encoding="utf-8")
    (mesh_dir / "vertex.bin").write_bytes(vertex_bytes)
    (mesh_dir / "index.bin").write_bytes(index_bytes)

    return intermediate_path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Extract single-event intermediate assets from zip.xml + zip")
    parser.add_argument("--xml", required=True, help="Path to capture.zip.xml")
    parser.add_argument("--zip", required=True, help="Path to capture.zip")
    parser.add_argument("--event", required=True, type=int, help="Target chunkIndex/event id")
    parser.add_argument("--out", required=True, help="Output directory")
    parser.add_argument(
        "--vertex-stride",
        required=False,
        type=int,
        default=0,
        help="Optional vertex stride hint. 0 = auto heuristic/unknown",
    )
    args = parser.parse_args(argv)

    extract_event_intermediate(
        xml_path=args.xml,
        zip_path=args.zip,
        event_id=args.event,
        out_dir=args.out,
        vertex_stride=args.vertex_stride,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
