from pathlib import Path
import json
import struct


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def resolve_bundle_root(path_value) -> Path:
    path = Path(path_value)
    if (path / "bundle_manifest.json").exists():
        return path
    if (path / "import_bundle" / "bundle_manifest.json").exists():
        return path / "import_bundle"
    raise FileNotFoundError(f"bundle_manifest.json not found under: {path}")


def detect_event_id(bundle_root: Path, explicit_event_id=None, manifest=None) -> int:
    if explicit_event_id is not None:
        return int(explicit_event_id)

    if isinstance(manifest, dict):
        value = manifest.get("event_id")
        if value is not None:
            return int(value)

    parent_name = bundle_root.parent.name
    if parent_name.startswith("event_"):
        suffix = parent_name.split("_", 1)[1]
        if suffix.isdigit():
            return int(suffix)

    raise ValueError("event id not found; pass --event or provide bundle_manifest.event_id")


def load_bundle_payload(bundle_root: Path):
    manifest = _load_json(bundle_root / "bundle_manifest.json", {})
    materials_payload = _load_json(bundle_root / "materials" / "materials.json", {})
    return manifest, materials_payload


def collect_material_textures(materials_payload: dict):
    if not isinstance(materials_payload, dict):
        return []

    materials = materials_payload.get("materials")
    if not isinstance(materials, list) or not materials:
        return []

    first_material = materials[0]
    if not isinstance(first_material, dict):
        return []

    textures = first_material.get("textures")
    if not isinstance(textures, list):
        return []

    result = []
    for item in textures:
        if isinstance(item, dict):
            result.append(item)
    return result


def _parse_obj_index(raw: str, length: int):
    if not raw:
        return None
    value = int(raw)
    if value > 0:
        index = value - 1
    else:
        index = length + value
    if index < 0 or index >= length:
        return None
    return index


def _pack_normal_component(value: float):
    clamped = max(-1.0, min(1.0, float(value)))
    encoded = int(round((clamped * 0.5 + 0.5) * 255.0))
    return max(0, min(255, encoded))


def _pack_vertex(position, normal, uv):
    nx = _pack_normal_component(normal[0])
    ny = _pack_normal_component(normal[1])
    nz = _pack_normal_component(normal[2])
    nw = 255
    return struct.pack(
        "<fffBBBBff",
        float(position[0]),
        float(position[1]),
        float(position[2]),
        nx,
        ny,
        nz,
        nw,
        float(uv[0]),
        float(uv[1]),
    )


def parse_obj_mesh(mesh_obj_path: Path):
    if not mesh_obj_path.exists():
        raise FileNotFoundError(f"mesh obj not found: {mesh_obj_path}")

    positions = []
    normals = []
    uvs = []
    triangles = []

    for raw_line in mesh_obj_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        if line.startswith("v "):
            parts = line.split()
            if len(parts) >= 4:
                positions.append((float(parts[1]), float(parts[2]), float(parts[3])))
            continue

        if line.startswith("vn "):
            parts = line.split()
            if len(parts) >= 4:
                normals.append((float(parts[1]), float(parts[2]), float(parts[3])))
            continue

        if line.startswith("vt "):
            parts = line.split()
            if len(parts) >= 3:
                uvs.append((float(parts[1]), float(parts[2])))
            continue

        if not line.startswith("f "):
            continue

        face_tokens = line.split()[1:]
        if len(face_tokens) < 3:
            continue

        face_vertices = []
        for token in face_tokens:
            comps = token.split("/")
            pos_idx = _parse_obj_index(comps[0], len(positions))
            uv_idx = _parse_obj_index(comps[1], len(uvs)) if len(comps) >= 2 and comps[1] else None
            norm_idx = _parse_obj_index(comps[2], len(normals)) if len(comps) >= 3 and comps[2] else None
            if pos_idx is None:
                continue
            face_vertices.append((pos_idx, uv_idx, norm_idx))

        if len(face_vertices) < 3:
            continue

        head = face_vertices[0]
        for idx in range(1, len(face_vertices) - 1):
            triangles.append((head, face_vertices[idx], face_vertices[idx + 1]))

    if not positions or not triangles:
        raise ValueError(f"obj has no usable triangles: {mesh_obj_path}")

    vertex_map = {}
    vertex_bytes = bytearray()
    indices = []

    for tri in triangles:
        for key in tri:
            if key not in vertex_map:
                pos_idx, uv_idx, norm_idx = key
                position = positions[pos_idx]
                uv = uvs[uv_idx] if uv_idx is not None and uv_idx < len(uvs) else (0.0, 0.0)
                normal = normals[norm_idx] if norm_idx is not None and norm_idx < len(normals) else (0.0, 0.0, 1.0)
                vertex_map[key] = len(vertex_map)
                vertex_bytes.extend(_pack_vertex(position, normal, uv))
            indices.append(vertex_map[key])

    vertex_count = len(vertex_map)
    if vertex_count <= 65535:
        index_format = "uint16"
        index_bytes = b"".join(struct.pack("<H", value) for value in indices)
    else:
        index_format = "uint32"
        index_bytes = b"".join(struct.pack("<I", value) for value in indices)

    return {
        "vertex_bytes": bytes(vertex_bytes),
        "index_bytes": index_bytes,
        "vertex_count": vertex_count,
        "index_count": len(indices),
        "index_format": index_format,
    }


def resolve_texture_source(bundle_root: Path, texture_entry: dict):
    output_path = str(texture_entry.get("output_path") or "")
    source_path = str(texture_entry.get("source_path") or "")

    candidate_paths = []
    if output_path:
        candidate_paths.append(bundle_root / output_path)
    if source_path:
        candidate_paths.append(bundle_root / source_path)
    texture_id = texture_entry.get("texture_id")
    if texture_id is not None:
        candidate_paths.append(bundle_root / "textures" / f"tex_{texture_id}.png")
        candidate_paths.append(bundle_root / "textures" / f"tex_{texture_id}.bin")

    for candidate in candidate_paths:
        if candidate.exists() and candidate.is_file():
            return candidate
    return None
