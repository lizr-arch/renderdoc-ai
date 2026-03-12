import json
import struct
from pathlib import Path


_FORMAT_MAP = {
    "float": ("<f", 1),
    "float2": ("<ff", 2),
    "float3": ("<fff", 3),
    "float4": ("<ffff", 4),
}


def _read_attribute(data, count, stride, offset, fmt):
    values = []
    for index in range(count):
        base = index * stride + offset
        values.append(struct.unpack_from(fmt, data, base))
    return values


def _read_indices(data, count, index_format):
    if index_format == "uint32":
        fmt = "<I"
        size = 4
    else:
        fmt = "<H"
        size = 2
    indices = []
    for index in range(count):
        indices.append(struct.unpack_from(fmt, data, index * size)[0])
    return indices


def _find_layout_entry(layout, semantic):
    for entry in layout:
        if entry.get("semantic") == semantic:
            return entry
    return None


def _export_texture(intermediate_path, obj_root, texture_entry):
    texture_id = texture_entry.get("texture_id")
    texture_path = texture_entry.get("path")
    width = texture_entry.get("width")
    height = texture_entry.get("height")
    format_name = texture_entry.get("format")

    if texture_id is None or width is None or height is None or not format_name:
        return None

    if not texture_path:
        texture_path = f"tex_{texture_id}.bin"

    src_path = intermediate_path / "textures" / texture_path
    if not src_path.exists():
        return None

    try:
        from decoders.texture_decoder import decode_texture, save_as_png
    except ImportError:
        return None

    try:
        rgba = decode_texture(src_path.read_bytes(), width, height, format_name)
        textures_dir = obj_root / "textures"
        textures_dir.mkdir(parents=True, exist_ok=True)
        out_name = f"tex_{texture_id}.png"
        out_path = textures_dir / out_name
        save_as_png(rgba, width, height, out_path)
        return f"textures/{out_name}"
    except Exception:
        return None


def write_obj(intermediate_dir, out_dir, event_id):
    intermediate_path = Path(intermediate_dir)
    mesh_path = intermediate_path / "mesh" / "mesh.json"
    if not mesh_path.exists():
        raise FileNotFoundError(f"mesh.json not found: {mesh_path}")

    mesh_blob = json.loads(mesh_path.read_text(encoding="utf-8"))
    mesh = mesh_blob.get("mesh", {})
    layout = mesh.get("vertex_layout", [])
    vertex_count = int(mesh.get("vertex_count", 0))
    index_count = int(mesh.get("index_count", 0))
    index_format = mesh.get("index_format", "uint16")

    if not layout or vertex_count <= 0 or index_count <= 0:
        raise ValueError("mesh.json missing vertex_layout/vertex_count/index_count")

    position_entry = _find_layout_entry(layout, "POSITION")
    if not position_entry:
        raise ValueError("vertex_layout missing POSITION")

    stride = int(position_entry.get("stride", 0))
    offset = int(position_entry.get("offset", 0))
    format_name = position_entry.get("format", "")
    fmt = _FORMAT_MAP.get(format_name)
    if not fmt:
        raise ValueError(f"Unsupported position format: {format_name}")

    vertex_bin = (intermediate_path / "mesh" / "vertex.bin").read_bytes()
    index_bin = (intermediate_path / "mesh" / "index.bin").read_bytes()

    positions = _read_attribute(vertex_bin, vertex_count, stride, offset, fmt[0])

    normal_entry = _find_layout_entry(layout, "NORMAL")
    normals = None
    if normal_entry and normal_entry.get("format") in _FORMAT_MAP:
        nfmt = _FORMAT_MAP[normal_entry["format"]][0]
        normals = _read_attribute(
            vertex_bin,
            vertex_count,
            int(normal_entry.get("stride", stride)),
            int(normal_entry.get("offset", 0)),
            nfmt,
        )

    uv_entry = _find_layout_entry(layout, "TEXCOORD0")
    uvs = None
    if uv_entry and uv_entry.get("format") in _FORMAT_MAP:
        uvfmt = _FORMAT_MAP[uv_entry["format"]][0]
        uvs = _read_attribute(
            vertex_bin,
            vertex_count,
            int(uv_entry.get("stride", stride)),
            int(uv_entry.get("offset", 0)),
            uvfmt,
        )

    indices = _read_indices(index_bin, index_count, index_format)

    obj_root = Path(out_dir) / f"event_{event_id}" / "obj"
    obj_root.mkdir(parents=True, exist_ok=True)
    obj_path = obj_root / "mesh.obj"
    mtl_path = obj_root / "mesh.mtl"

    texture_ref = None
    material_path = intermediate_path / "materials" / "material.json"
    if material_path.exists():
        material = json.loads(material_path.read_text(encoding="utf-8")).get("material", {})
        textures = material.get("textures") or []
        if textures:
            texture_ref = _export_texture(intermediate_path, obj_root, textures[0])

    obj_lines = ["mtllib mesh.mtl"]
    for vertex in positions:
        obj_lines.append(f"v {vertex[0]} {vertex[1]} {vertex[2]}")
    if uvs:
        for uv in uvs:
            obj_lines.append(f"vt {uv[0]} {uv[1]}")
    if normals:
        for normal in normals:
            obj_lines.append(f"vn {normal[0]} {normal[1]} {normal[2]}")

    obj_lines.append("usemtl material_0")

    has_uv = uvs is not None
    has_normal = normals is not None
    for idx in range(0, len(indices), 3):
        tri = indices[idx:idx + 3]
        if len(tri) < 3:
            break
        if has_uv and has_normal:
            obj_lines.append(
                f"f {tri[0]+1}/{tri[0]+1}/{tri[0]+1} {tri[1]+1}/{tri[1]+1}/{tri[1]+1} {tri[2]+1}/{tri[2]+1}/{tri[2]+1}"
            )
        elif has_uv:
            obj_lines.append(
                f"f {tri[0]+1}/{tri[0]+1} {tri[1]+1}/{tri[1]+1} {tri[2]+1}/{tri[2]+1}"
            )
        elif has_normal:
            obj_lines.append(
                f"f {tri[0]+1}//{tri[0]+1} {tri[1]+1}//{tri[1]+1} {tri[2]+1}//{tri[2]+1}"
            )
        else:
            obj_lines.append(f"f {tri[0]+1} {tri[1]+1} {tri[2]+1}")

    obj_path.write_text("\n".join(obj_lines) + "\n", encoding="utf-8")

    mtl_lines = ["newmtl material_0", "Kd 1.0 1.0 1.0"]
    if texture_ref:
        mtl_lines.append(f"map_Kd {texture_ref}")
    mtl_path.write_text("\n".join(mtl_lines) + "\n", encoding="utf-8")

    return obj_root
