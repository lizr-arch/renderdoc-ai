from dataclasses import dataclass
import json
from pathlib import Path
import zipfile
import xml.etree.ElementTree as ET


@dataclass
class BufferBinding:
    resource_id: int
    byte_offset: int
    byte_size: int


@dataclass
class EventState:
    index_buffer: BufferBinding | None
    vertex_buffers: list[BufferBinding]
    textures: list[dict]
    shaders: list[dict]


def _to_int(value, default=0):
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_buffer(elem):
    return BufferBinding(
        resource_id=_to_int(elem.get("resource_id")),
        byte_offset=_to_int(elem.get("byte_offset")),
        byte_size=_to_int(elem.get("byte_size")),
    )


def load_zip_index(zip_path):
    with zipfile.ZipFile(zip_path, "r") as handle:
        return {name: handle.read(name) for name in handle.namelist()}


def resolve_zip_entry(expected_name, zip_index):
    if expected_name in zip_index:
        return expected_name
    return None


def resolve_zip_entry_candidates(buffer_index, zip_index):
    candidates = [
        f"buffers/buffer{buffer_index}",
        f"{buffer_index:06d}",
        f"buffer{buffer_index}",
    ]
    for name in candidates:
        if name in zip_index:
            return name
    return None


def decode_texture_rgba(data, width, height, format_name):
    from decoders.texture_decoder import decode_texture

    return decode_texture(data, width, height, format_name)


def build_decode_manifest(zip_entry, decode_status):
    return {
        "zip_entry": zip_entry,
        "decode_status": decode_status,
    }


def extract_event_state(xml_path, event_id):
    tree = ET.parse(xml_path)
    root = tree.getroot()
    event_elem = None
    for event in root.findall(".//event"):
        if _to_int(event.get("id")) == int(event_id):
            event_elem = event
            break
    if event_elem is None:
        raise ValueError(f"event {event_id} not found in {xml_path}")

    vertex_buffers = []
    vbs_elem = event_elem.find("vertex_buffers")
    if vbs_elem is not None:
        for vb in vbs_elem.findall("vb"):
            vertex_buffers.append(_parse_buffer(vb))

    ib_elem = event_elem.find("index_buffer")
    index_buffer = _parse_buffer(ib_elem) if ib_elem is not None else None

    return EventState(
        index_buffer=index_buffer,
        vertex_buffers=vertex_buffers,
        textures=[],
        shaders=[],
    )


def write_intermediate(out_dir, state, buffers, shaders, textures):
    out_path = Path(out_dir)
    mesh_dir = out_path / "intermediate" / "mesh"
    material_dir = out_path / "intermediate" / "materials"
    shader_dir = out_path / "intermediate" / "shaders"
    texture_dir = out_path / "intermediate" / "textures"
    mesh_dir.mkdir(parents=True, exist_ok=True)
    material_dir.mkdir(parents=True, exist_ok=True)
    shader_dir.mkdir(parents=True, exist_ok=True)
    texture_dir.mkdir(parents=True, exist_ok=True)

    texture_decode = []

    try:
        from intermediate_schema import (
            build_mesh_schema,
            build_material_schema,
            build_shader_schema,
            build_texture_schema,
        )
    except Exception:
        build_mesh_schema = None
        build_material_schema = None
        build_shader_schema = None
        build_texture_schema = None

    mesh = build_mesh_schema() if build_mesh_schema else {}
    mesh_path = mesh_dir / "mesh.json"
    mesh_path.write_text(json.dumps({"mesh": mesh}, indent=2), encoding="utf-8")

    material = build_material_schema() if build_material_schema else {}
    if isinstance(material, dict):
        material["textures"] = list(state.textures or [])
    (material_dir / "material.json").write_text(
        json.dumps({"material": material}, indent=2), encoding="utf-8"
    )

    for shader in state.shaders or []:
        stage = shader.get("stage", "unknown")
        shader_schema = build_shader_schema() if build_shader_schema else {}
        if isinstance(shader_schema, dict):
            shader_schema["stage"] = stage
            shader_schema["bytecode_format"] = str(shader.get("bytecode_format") or shader_schema.get("bytecode_format") or "")
            shader_schema["entry"] = str(shader.get("entry") or shader_schema.get("entry") or "main")
            if shader.get("disassembly") is not None:
                shader_schema["disassembly"] = str(shader.get("disassembly") or "")

            shader_schema["source_kind"] = str(shader.get("source_kind") or shader_schema.get("source_kind") or "")
            shader_schema["source_resource_id"] = _to_int(
                shader.get("resource_id", shader_schema.get("source_resource_id", 0)),
                default=0,
            )
            shader_schema["buffer_index"] = _to_int(shader.get("buffer_index", shader_schema.get("buffer_index", 0)), default=0)
            shader_schema["byte_length"] = _to_int(shader.get("byte_length", shader_schema.get("byte_length", 0)), default=0)
            shader_schema["zip_entry"] = str(shader.get("zip_entry") or shader_schema.get("zip_entry") or "")
            shader_schema["path"] = str(shader.get("path") or shader_schema.get("path") or f"{stage}.bin")
        shader_json = shader_dir / f"{stage}.json"
        shader_json.write_text(
            json.dumps({"shader": shader_schema}, indent=2), encoding="utf-8"
        )

        shader_path = shader.get("path")
        if shader_path:
            shader_bin = shader_dir / shader_path
            data = shaders.get(shader_path)
            if data is None and stage in shaders:
                data = shaders.get(stage)
            shader_bin.write_bytes(data or b"")

    for texture in state.textures or []:
        texture_path = texture.get("path")
        if not texture_path:
            texture_id = texture.get("texture_id", 0)
            texture_path = f"tex_{texture_id}.bin"
        data = textures.get(texture_path)
        if data is None:
            data = textures.get(texture.get("texture_id"))

        zip_entry = texture.get("zip_entry")
        decode_status = "raw"
        output_data = data or b""
        if data is None:
            decode_status = "missing"
            output_data = b""
        else:
            format_name = texture.get("format") or texture.get("format_name")
            width = _to_int(texture.get("width"), default=0)
            height = _to_int(texture.get("height"), default=0)
            if format_name and width and height:
                try:
                    output_data = decode_texture_rgba(data, width, height, format_name)
                    decode_status = "ok"
                except Exception:
                    output_data = data
                    decode_status = "decode_failed"

        (texture_dir / texture_path).write_bytes(output_data)
        texture_decode.append(build_decode_manifest(zip_entry, decode_status))

    manifest_path = out_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({"texture_decode": texture_decode}, indent=2), encoding="utf-8"
    )

    return mesh_path
