from pathlib import Path
import json

from engine_guid import hash_guid


def write_repo_skeleton(out_dir, event_id):
    repo_root = (
        Path(out_dir) / "Package" / "Repository" / f"rdc_event_{event_id}.local"
    )
    repo_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "resource.repository").write_text("", encoding="utf-8")
    for folder_name in ("Mesh", "Texture", "Material", "Model"):
        (repo_root / folder_name).mkdir(exist_ok=True)
    return repo_root


def build_material_xml(shader_kind, fallback, base_texture_guid=None, texture_bindings=None):
    if isinstance(shader_kind, str) and shader_kind.lower() == "pbr":
        template_name = "PBR"
    else:
        template_name = "Unlit" if fallback == "unlit" else fallback

    zero_guid = "00000000-0000-0000-0000-000000000000"
    parameters = []
    if isinstance(texture_bindings, list) and texture_bindings:
        for item in texture_bindings:
            if not isinstance(item, (tuple, list)) or len(item) < 2:
                continue
            param_name = str(item[0] or "").strip() or "tBaseMap"
            param_guid = str(item[1] or "").strip() or zero_guid
            if any(existing_name == param_name for existing_name, _ in parameters):
                continue
            parameters.append((param_name, param_guid))

    if not parameters:
        texture_guid = base_texture_guid or zero_guid
        parameters = [("tBaseMap", texture_guid)]

    parameter_chunks = []
    for index, (param_name, texture_guid) in enumerate(parameters):
        parameter_chunks.append(
            (
                f'                                <Element index="{index}">\n'
                f'                                    <Name>{param_name}</Name>\n'
                f'                                    <Value>{texture_guid}</Value>\n'
                '                                </Element>'
            )
        )
    parameters_xml = "\n".join(parameter_chunks)

    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<Resource>\n"
        "    <Version>1</Version>\n"
        "    <SMaterialData>\n"
        "        <Root>\n"
        "            <Sub/>\n"
        "            <Entity type=\"SMaterialData\">\n"
        "                <name/>\n"
        "                <info>\n"
        "                    <Layers count=\"1\" ordered=\"true\">\n"
        "                        <Element index=\"0\">\n"
        "                            <LayerName>rdc_layer</LayerName>\n"
        f"                            <ShaderName>{template_name}</ShaderName>\n"
        f"                            <Parameters count=\"{len(parameters)}\" ordered=\"true\">\n"
        f"{parameters_xml}\n"
        "                            </Parameters>\n"
        "                        </Element>\n"
        "                    </Layers>\n"
        "                </info>\n"
        "                <flags count=\"1\" ordered=\"true\">\n"
        "                    <Element index=\"0\">64</Element>\n"
        "                </flags>\n"
        "            </Entity>\n"
        "        </Root>\n"
        "    </SMaterialData>\n"
        "</Resource>\n"
    )


def export_messiah(intermediate_dir, out_dir, event_id):
    intermediate_path = Path(intermediate_dir)
    repo_root = write_repo_skeleton(Path(out_dir) / "messiah", event_id)

    mesh_guid = hash_guid("Mesh", event_id, "mesh")
    material_guid = hash_guid("Material", event_id, "material")
    model_guid = hash_guid("Model", event_id, "model")

    mesh_data_dir = intermediate_path / "mesh"
    material_data_dir = intermediate_path / "materials"
    texture_data_dir = intermediate_path / "textures"
    shader_data_dir = intermediate_path / "shaders"

    mesh_json = _read_json(mesh_data_dir / "mesh.json")
    material_json = _read_json(material_data_dir / "material.json")
    shader_json = _read_json(shader_data_dir / "ps.json")

    vertex_data = _read_bytes(mesh_data_dir / "vertex.bin")
    index_data = _read_bytes(mesh_data_dir / "index.bin")

    mesh_section = mesh_json.get("mesh", {}) if isinstance(mesh_json, dict) else {}
    vertex_count = _to_int(mesh_section.get("vertex_count"), 0)
    index_count = _to_int(mesh_section.get("index_count"), 0)
    index_format = mesh_section.get("index_format", "uint16")
    vertex_stride = 24
    if vertex_count == 0 and len(vertex_data) % vertex_stride == 0:
        vertex_count = len(vertex_data) // vertex_stride
    index_size = 2 if index_format == "uint16" else 4
    if index_count == 0 and index_size and len(index_data) % index_size == 0:
        index_count = len(index_data) // index_size

    mesh_dir = _resource_dir(repo_root, "Mesh", mesh_guid)
    mesh_dir.mkdir(parents=True, exist_ok=True)
    mesh_xml = _build_mesh_xml(vertex_count, index_count, len(vertex_data), len(index_data))
    _write_text(mesh_dir / "resource.xml", mesh_xml)
    _write_bytes(mesh_dir / "resource.data", vertex_data + index_data)

    textures = []
    material_section = material_json.get("material", {}) if isinstance(material_json, dict) else {}
    texture_entries = material_section.get("textures", []) if isinstance(material_section, dict) else []
    for tex in texture_entries:
        texture_path = tex.get("path")
        texture_id = tex.get("texture_id", 0)
        texture_key = texture_path or f"tex_{texture_id}.bin"
        texture_guid = hash_guid("Texture", event_id, texture_key)
        textures.append((texture_guid, texture_key, tex))

        tex_bytes = _read_bytes(texture_data_dir / texture_key)
        width = _to_int(tex.get("width"), 1)
        height = _to_int(tex.get("height"), 1)
        fmt = tex.get("format") or tex.get("format_name") or "R8G8B8A8"
        fmt = _normalize_texture_format(fmt)

        texture_dir = _resource_dir(repo_root, "Texture", texture_guid)
        texture_dir.mkdir(parents=True, exist_ok=True)
        tex_xml = _build_texture_xml(width, height, fmt, len(tex_bytes))
        _write_text(texture_dir / "texture.xml", tex_xml)
        _write_bytes(texture_dir / "resource.data", tex_bytes)

    base_texture_guid = textures[0][0] if textures else None
    shader_kind = shader_json.get("shader", {}).get("stage") if isinstance(shader_json, dict) else None
    material_xml = build_material_xml(shader_kind, "unlit", base_texture_guid)
    material_dir = _resource_dir(repo_root, "Material", material_guid)
    material_dir.mkdir(parents=True, exist_ok=True)
    _write_text(material_dir / "resource.xml", material_xml)

    model_dir = _resource_dir(repo_root, "Model", model_guid)
    model_dir.mkdir(parents=True, exist_ok=True)
    model_xml = _build_model_xml(mesh_guid, material_guid, vertex_count, index_count)
    _write_text(model_dir / "resource.xml", model_xml)

    _write_text(repo_root / "resource.repository", _build_repository_xml(event_id, mesh_guid, material_guid, model_guid, textures))

    return repo_root


def _resource_dir(repo_root, resource_type, guid):
    return Path(repo_root) / resource_type / guid[:2] / guid


def _build_mesh_xml(vertex_count, index_count, stream0_size, index_size):
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<Resource>\n"
        "    <Version>6</Version>\n"
        "    <SRenderMeshData>\n"
        "        <Root>\n"
        "            <Sub/>\n"
        "            <Entity type=\"SRenderMeshData\">\n"
        "                <VertexFormat count=\"4\">\n"
        "                    <Element index=\"0\">P3F_N4B_T2F</Element>\n"
        "                    <Element index=\"1\">T4H_B4H</Element>\n"
        "                    <Element index=\"2\">None</Element>\n"
        "                    <Element index=\"3\">None</Element>\n"
        "                </VertexFormat>\n"
        f"                <VertexCount>{vertex_count}</VertexCount>\n"
        f"                <IndexCount>{index_count}</IndexCount>\n"
        "                <StreamingMask>1</StreamingMask>\n"
        "                <PrimTopology>Tri_List</PrimTopology>\n"
        "                <spare count=\"3\">\n"
        "                    <Element index=\"0\">0</Element>\n"
        "                    <Element index=\"1\">0</Element>\n"
        "                    <Element index=\"2\">0</Element>\n"
        "                </spare>\n"
        "                <BoundingVolume>(0,0,0,0,0,0,0)</BoundingVolume>\n"
        "                <BoundingBox>(0,0,0,0,0,0)</BoundingBox>\n"
        "                <Streams count=\"4\">\n"
        f"                    <Element index=\"0\"><StreamSize>{stream0_size}</StreamSize></Element>\n"
        "                    <Element index=\"1\"><StreamSize>0</StreamSize></Element>\n"
        "                    <Element index=\"2\"><StreamSize>0</StreamSize></Element>\n"
        "                    <Element index=\"3\"><StreamSize>0</StreamSize></Element>\n"
        "                </Streams>\n"
        "                <Indices>\n"
        f"                    <StreamSize>{index_size}</StreamSize>\n"
        "                </Indices>\n"
        "                <Groups count=\"1\" ordered=\"true\">\n"
        "                    <Element index=\"0\">\n"
        "                        <StartIndex>0</StartIndex>\n"
        f"                        <IndicesCount>{index_count}</IndicesCount>\n"
        "                        <StartVertex>0</StartVertex>\n"
        f"                        <VerticesCount>{vertex_count}</VerticesCount>\n"
        f"                        <PartialIndicesCount>{index_count}</PartialIndicesCount>\n"
        "                        <BoundingVolume>(0,0,0,0,0,0,0)</BoundingVolume>\n"
        "                        <BoundingBox>(0,0,0,0,0,0)</BoundingBox>\n"
        "                    </Element>\n"
        "                </Groups>\n"
        "            </Entity>\n"
        "        </Root>\n"
        "    </SRenderMeshData>\n"
        "</Resource>\n"
    )


def _build_texture_xml(width, height, fmt, data_size):
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<Texture>\n"
        "    <Texture2DInfo>\n"
        "        <Root>\n"
        "            <Sub/>\n"
        "            <Entity type=\"Texture2DInfo\">\n"
        f"                <Width>{width}</Width>\n"
        f"                <Height>{height}</Height>\n"
        "                <Depth>1</Depth>\n"
        "                <MipLevels>1</MipLevels>\n"
        "                <ArraySize>1</ArraySize>\n"
        "                <MipGenPreset>FromTextureGroup</MipGenPreset>\n"
        "                <TextureType>2D</TextureType>\n"
        "            </Entity>\n"
        "        </Root>\n"
        "    </Texture2DInfo>\n"
        "    <RsTextureInfo>\n"
        "        <Root>\n"
        "            <Sub/>\n"
        "            <Entity type=\"RsTextureInfo\">\n"
        f"                <Format>{fmt}</Format>\n"
        "                <Dimension>2D</Dimension>\n"
        "            </Entity>\n"
        "        </Root>\n"
        "    </RsTextureInfo>\n"
        "    <RsTextureSliceInfo>\n"
        "        <Root>\n"
        "            <Sub/>\n"
        "            <Entity type=\"RsTextureSliceInfo\">\n"
        "                <MipLevel>0</MipLevel>\n"
        "                <ArrayIndex>0</ArrayIndex>\n"
        "            </Entity>\n"
        "        </Root>\n"
        "    </RsTextureSliceInfo>\n"
        "    <RsTextureSliceData>\n"
        "        <Begin>0</Begin>\n"
        f"        <Size>{data_size}</Size>\n"
        "    </RsTextureSliceData>\n"
        "</Texture>\n"
    )


def _build_model_xml(mesh_guid, material_guid, vertex_count, index_count):
    num_faces = int(index_count / 3) if index_count else 0
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<Resource>\n"
        "    <Version>1</Version>\n"
        "    <ModelInfo>\n"
        "        <Root>\n"
        "            <Sub/>\n"
        "            <Entity type=\"ModelInfo\">\n"
        "                <BoundBox>(0,0,0,0,0,0)</BoundBox>\n"
        f"                <NumVertices>{vertex_count}</NumVertices>\n"
        f"                <NumFaces>{num_faces}</NumFaces>\n"
        "                <ModelType>1</ModelType>\n"
        "                <ModelElements count=\"1\" ordered=\"true\">\n"
        "                    <Element index=\"0\">\n"
        f"                        <Mesh>{{{mesh_guid}}}</Mesh>\n"
        f"                        <Material>{{{material_guid}}}</Material>\n"
        "                        <GroupIndex>0</GroupIndex>\n"
        "                    </Element>\n"
        "                </ModelElements>\n"
        "            </Entity>\n"
        "        </Root>\n"
        "    </ModelInfo>\n"
        "</Resource>\n"
    )


def _build_repository_xml(event_id, mesh_guid, material_guid, model_guid, textures):
    items = []
    items.append(
        _repository_item("Mesh", mesh_guid, f"Mesh_event_{event_id}", event_id)
    )
    for index, (texture_guid, _, _) in enumerate(textures):
        items.append(
            _repository_item(
                "Texture",
                texture_guid,
                f"Texture_event_{event_id}_{index}",
                event_id,
            )
        )
    items.append(
        _repository_item(
            "Material", material_guid, f"Material_event_{event_id}", event_id
        )
    )
    items.append(
        _repository_item("Model", model_guid, f"Model_event_{event_id}", event_id)
    )
    return (
        "<?xml version=\"1.0\" encoding=\"utf-8\"?>\n"
        "<Repository>\n"
        + "\n".join(items)
        + "\n</Repository>\n"
    )


def _repository_item(resource_type, guid, name, event_id):
    package_name = f"rdc_event_{event_id}"
    return (
        "    <Item>\n"
        f"        <Type>{resource_type}</Type>\n"
        "        <Flags>0</Flags>\n"
        f"        <GUID>{guid}</GUID>\n"
        f"        <Package>{package_name}</Package>\n"
        f"        <Class>{resource_type}</Class>\n"
        f"        <Name>{name}</Name>\n"
        "        <Annotation>\n"
        "            <SourcePath/>\n"
        "            <CreationTime>0</CreationTime>\n"
        "            <MD5/>\n"
        "        </Annotation>\n"
        "    </Item>"
    )


def _read_json(path):
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_bytes(path):
    if not path.exists():
        return b""
    return path.read_bytes()


def _write_text(path, content):
    path.write_text(content, encoding="utf-8")


def _write_bytes(path, content):
    path.write_bytes(content)


def _normalize_texture_format(format_name):
    name = format_name.upper()
    if "RGBA8" in name or "R8G8B8A8" in name:
        return "R8G8B8A8"
    return format_name


def _to_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default
