from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET


@dataclass
class DrawEvent:
    event_id: int
    chunk_index: int
    name: str
    api: str


@dataclass
class VulkanDrawIndexedCall:
    event_id: int
    index_count: int
    instance_count: int
    first_index: int
    vertex_offset: int
    first_instance: int


@dataclass
class D3D11DrawIndexedCall:
    event_id: int
    index_count: int
    start_index_location: int
    base_vertex_location: int


def _to_int(value, default: int = 0) -> int:
    if value is None:
        return default
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return default
    try:
        return int(text)
    except ValueError:
        return default


def _detect_api_from_xml(xml_path: str) -> str:
    for _, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag == "driver":
            if elem.text and elem.text.strip():
                return elem.text.strip()
            return "Unknown"
        elem.clear()
    return "Unknown"


def detect_capture_api(xml_path: str) -> str:
    return _detect_api_from_xml(xml_path)


def iter_draw_events(xml_path: str):
    api = _detect_api_from_xml(xml_path)

    for _, elem in ET.iterparse(xml_path, events=("end",)):
        if elem.tag != "chunk":
            continue

        name = elem.get("name", "")
        if "Draw" not in name and "Dispatch" not in name:
            elem.clear()
            continue

        chunk_index = _to_int(elem.get("chunkIndex"), default=0)
        yield DrawEvent(
            event_id=chunk_index,
            chunk_index=chunk_index,
            name=name,
            api=api,
        )
        elem.clear()


def _parse_index_format(index_type: str) -> str:
    if "UINT32" in index_type:
        return "uint32"
    return "uint16"


def _parse_d3d11_index_format(dxgi_format: str) -> str:
    if "R32_UINT" in dxgi_format:
        return "uint32"
    return "uint16"


def _parse_bind_index_buffer(chunk: ET.Element) -> dict:
    buffer_elem = chunk.find("./ResourceId[@name='buffer']")
    offset_elem = chunk.find("./uint[@name='offset']")
    index_type_elem = chunk.find("./enum[@name='indexType']")

    index_type = ""
    if index_type_elem is not None:
        index_type = index_type_elem.get("string", "")

    return {
        "resource_id": _to_int(buffer_elem.text if buffer_elem is not None else None),
        "byte_offset": _to_int(offset_elem.text if offset_elem is not None else None),
        "index_format": _parse_index_format(index_type),
    }


def _read_numeric_text(chunk: ET.Element, xpath: str, default: int = 0) -> int:
    elem = chunk.find(xpath)
    if elem is None:
        return default
    return _to_int(elem.text, default=default)


def _parse_bind_vertex_buffers(chunk: ET.Element) -> list[dict]:
    buffers_array = chunk.find("./array[@name='pBuffers']")
    offsets_array = chunk.find("./array[@name='pOffsets']")

    buffer_ids = []
    if buffers_array is not None:
        for elem in buffers_array.findall("ResourceId"):
            buffer_ids.append(_to_int(elem.text))

    offsets = []
    if offsets_array is not None:
        for elem in offsets_array.findall("uint"):
            offsets.append(_to_int(elem.text))

    bindings = []
    for index, resource_id in enumerate(buffer_ids):
        byte_offset = offsets[index] if index < len(offsets) else 0
        bindings.append({"resource_id": resource_id, "byte_offset": byte_offset})

    return bindings


def _parse_draw_indexed_chunk(chunk: ET.Element, event_id: int) -> VulkanDrawIndexedCall:
    return VulkanDrawIndexedCall(
        event_id=event_id,
        index_count=_read_numeric_text(chunk, "./uint[@name='indexCount']"),
        instance_count=_read_numeric_text(chunk, "./uint[@name='instanceCount']"),
        first_index=_read_numeric_text(chunk, "./uint[@name='firstIndex']"),
        vertex_offset=_read_numeric_text(chunk, "./int[@name='vertexOffset']"),
        first_instance=_read_numeric_text(chunk, "./uint[@name='firstInstance']"),
    )


def _parse_d3d11_draw_indexed_chunk(chunk: ET.Element, event_id: int) -> D3D11DrawIndexedCall:
    return D3D11DrawIndexedCall(
        event_id=event_id,
        index_count=_read_numeric_text(chunk, "./uint[@name='IndexCount']"),
        start_index_location=_read_numeric_text(chunk, "./uint[@name='StartIndexLocation']"),
        base_vertex_location=_read_numeric_text(chunk, "./int[@name='BaseVertexLocation']"),
    )


def _vulkan_stage_from_flag(stage_flag: str) -> str:
    if "VERTEX" in stage_flag:
        return "vs"
    if "FRAGMENT" in stage_flag:
        return "ps"
    if "GEOMETRY" in stage_flag:
        return "gs"
    if "TESSELLATION_CONTROL" in stage_flag:
        return "hs"
    if "TESSELLATION_EVALUATION" in stage_flag:
        return "ds"
    if "COMPUTE" in stage_flag:
        return "cs"
    return "unknown"


def _parse_vulkan_shader_module_chunk(chunk: ET.Element) -> tuple[int, dict]:
    module_elem = chunk.find("./ResourceId[@name='ShaderModule']")
    if module_elem is None:
        module_elem = chunk.find("./ResourceId[@name='shaderModule']")
    if module_elem is None:
        module_elem = chunk.find("./ResourceId[@name='module']")

    module_id = _to_int(module_elem.text if module_elem is not None else None)
    if module_id <= 0:
        return 0, {}

    create_info = chunk.find("./struct[@name='CreateInfo']")
    search_root = create_info if create_info is not None else chunk

    code_size_elem = search_root.find("./uint[@name='codeSize']")
    if code_size_elem is None:
        code_size_elem = search_root.find("./uint[@name='CodeSize']")

    code_elem = search_root.find("./buffer[@name='pCode']")
    if code_elem is None:
        code_elem = search_root.find("./buffer[@name='code']")
    if code_elem is None:
        code_elem = search_root.find("./buffer[@name='Code']")

    code_size = _to_int(code_size_elem.text if code_size_elem is not None else None, default=0)
    if code_size <= 0 and code_elem is not None:
        code_size = _to_int(code_elem.get("byteLength"), default=0)

    return module_id, {
        "buffer_index": _to_int(code_elem.text if code_elem is not None else None, default=0),
        "code_size": int(code_size),
    }


def _parse_vulkan_descriptor_write_struct(write_struct: ET.Element, fallback_set_id: int = 0) -> dict | None:
    set_elem = write_struct.find("./ResourceId[@name='dstSet']")
    set_id = _to_int(set_elem.text if set_elem is not None else None, default=fallback_set_id)
    if set_id <= 0 and fallback_set_id > 0:
        # vkUpdateDescriptorSetWithTemplate commonly serializes dstSet as 0 in each write.
        set_id = int(fallback_set_id)
    binding = _read_numeric_text(write_struct, "./uint[@name='dstBinding']", default=0)

    descriptor_type_elem = write_struct.find("./enum[@name='descriptorType']")
    descriptor_type = descriptor_type_elem.get("string", "") if descriptor_type_elem is not None else ""

    resources = []

    image_info_array = write_struct.find("./array[@name='pImageInfo']")
    if image_info_array is not None:
        for item in image_info_array.findall("struct"):
            image_view_elem = item.find("./ResourceId[@name='imageView']")
            sampler_elem = item.find("./ResourceId[@name='sampler']")
            layout_elem = item.find("./enum[@name='imageLayout']")
            resources.append(
                {
                    "image_view": _to_int(image_view_elem.text if image_view_elem is not None else None),
                    "sampler_id": _to_int(sampler_elem.text if sampler_elem is not None else None),
                    "layout": layout_elem.get("string", "") if layout_elem is not None else "",
                }
            )

    buffer_info_array = write_struct.find("./array[@name='pBufferInfo']")
    if buffer_info_array is not None:
        for item in buffer_info_array.findall("struct"):
            buffer_elem = item.find("./ResourceId[@name='buffer']")
            offset = _read_numeric_text(item, "./uint[@name='offset']", default=0)
            rng = _read_numeric_text(item, "./uint[@name='range']", default=0)
            resources.append(
                {
                    "buffer_id": _to_int(buffer_elem.text if buffer_elem is not None else None),
                    "offset": offset,
                    "range": rng,
                }
            )

    if set_id <= 0:
        return None

    return {
        "set_id": set_id,
        "binding": int(binding),
        "descriptor_type": descriptor_type,
        "resources": resources,
    }


def _build_vulkan_texture_bindings(
    graphics_descriptor_sets: dict,
    descriptor_set_contents: dict,
    image_view_to_image: dict,
    image_info_map: dict,
) -> list[dict]:
    textures = []
    dedupe = set()

    for set_index in sorted(graphics_descriptor_sets.keys()):
        set_id = int(graphics_descriptor_sets.get(set_index, 0))
        if set_id <= 0:
            continue

        binding_map = descriptor_set_contents.get(set_id, {})
        if not binding_map:
            continue

        sampler_arrays = {}
        for binding_index, write_info in binding_map.items():
            descriptor_type = str(write_info.get("descriptor_type", ""))
            if descriptor_type != "VK_DESCRIPTOR_TYPE_SAMPLER":
                continue

            sampler_ids = []
            for resource in write_info.get("resources", []):
                sampler_id = _to_int(resource.get("sampler_id", 0), default=0)
                if sampler_id <= 0 and resource.get("image_view", 0) > 0:
                    sampler_id = _to_int(resource.get("image_view", 0), default=0)
                if sampler_id > 0:
                    sampler_ids.append(sampler_id)
            if sampler_ids:
                sampler_arrays[int(binding_index)] = sampler_ids

        for binding_index in sorted(binding_map.keys()):
            write_info = binding_map[binding_index]
            descriptor_type = str(write_info.get("descriptor_type", ""))
            is_image_type = (
                "COMBINED_IMAGE_SAMPLER" in descriptor_type
                or "SAMPLED_IMAGE" in descriptor_type
                or "STORAGE_IMAGE" in descriptor_type
                or "INPUT_ATTACHMENT" in descriptor_type
            )
            if not is_image_type:
                continue

            for resource_index, resource in enumerate(write_info.get("resources", [])):
                image_view_id = _to_int(resource.get("image_view", 0), default=0)
                if image_view_id <= 0:
                    continue

                sampler_id = _to_int(resource.get("sampler_id", 0), default=0)
                sampler_binding = int(binding_index) if sampler_id > 0 and "COMBINED_IMAGE_SAMPLER" in descriptor_type else None

                if sampler_id <= 0:
                    preferred = sampler_arrays.get(int(binding_index) + 1)
                    fallback = sampler_arrays.get(int(binding_index))
                    source = preferred if preferred else fallback
                    if source and resource_index < len(source):
                        sampler_id = int(source[resource_index])
                        sampler_binding = int(binding_index) + 1 if preferred else int(binding_index)

                image_id = _to_int(image_view_to_image.get(image_view_id, 0), default=0)
                image_info = image_info_map.get(image_id, {}) if image_id > 0 else {}

                slot = f"set{int(set_index)}.binding{int(binding_index)}"
                sampler_slot = (
                    f"set{int(set_index)}.binding{int(sampler_binding)}"
                    if sampler_binding is not None
                    else ""
                )

                key = (slot, image_view_id)
                if key in dedupe:
                    continue
                dedupe.add(key)

                textures.append(
                    {
                        "slot": slot,
                        "sampler": sampler_slot,
                        "texture_id": image_view_id,
                        "view_id": image_view_id,
                        "image_id": image_id,
                        "resource_id": image_id,
                        "sampler_id": sampler_id,
                        "path": f"tex_{image_view_id}.bin",
                        "format": str(image_info.get("format", "")),
                        "width": _to_int(image_info.get("width", 0), default=0),
                        "height": _to_int(image_info.get("height", 0), default=0),
                        "mip_levels": _to_int(image_info.get("mip_levels", 1), default=1),
                        "array_layers": _to_int(image_info.get("array_layers", 1), default=1),
                        "memory_id": _to_int(image_info.get("memory_id", 0), default=0),
                        "memory_offset": _to_int(image_info.get("memory_offset", 0), default=0),
                        "memory_buffer_index": _to_int(image_info.get("memory_buffer_index", 0), default=0),
                    }
                )

    return textures


def extract_vulkan_bindings_for_event(xml_path: str, event_id: int) -> dict:
    event_id = int(event_id)
    index_binding = None
    vertex_bindings = []
    draw_info = None
    found = False

    descriptor_set_contents = {}
    graphics_descriptor_sets = {}
    compute_descriptor_sets = {}

    image_info_map = {}
    image_memory_map = {}
    memory_initial_map = {}
    image_view_to_image = {}

    shader_module_map = {}
    pipeline_shader_map = {}
    current_graphics_pipeline = 0

    for _, chunk in ET.iterparse(xml_path, events=("end",)):
        if chunk.tag != "chunk":
            continue

        name = chunk.get("name", "")
        chunk_index = _to_int(chunk.get("chunkIndex"), default=-1)

        if name == "vkCmdBindIndexBuffer":
            index_binding = _parse_bind_index_buffer(chunk)

        elif name == "vkCmdBindVertexBuffers":
            vertex_bindings = _parse_bind_vertex_buffers(chunk)

        elif name == "vkUpdateDescriptorSetWithTemplate":
            descriptor_set_elem = chunk.find("./ResourceId[@name='descriptorSet']")
            descriptor_set_id = _to_int(descriptor_set_elem.text if descriptor_set_elem is not None else None)
            writes = chunk.find("./array[@name='Decoded Writes']")
            if writes is not None and descriptor_set_id > 0:
                set_bindings = descriptor_set_contents.setdefault(descriptor_set_id, {})
                for write_struct in writes.findall("struct"):
                    parsed = _parse_vulkan_descriptor_write_struct(write_struct, fallback_set_id=descriptor_set_id)
                    if not parsed:
                        continue
                    set_bindings[int(parsed["binding"])] = parsed

        elif name == "vkUpdateDescriptorSets":
            writes = chunk.find("./array[@name='pDescriptorWrites']")
            if writes is not None:
                for write_struct in writes.findall("struct"):
                    parsed = _parse_vulkan_descriptor_write_struct(write_struct, fallback_set_id=0)
                    if not parsed:
                        continue
                    set_id = int(parsed["set_id"])
                    descriptor_set_contents.setdefault(set_id, {})[int(parsed["binding"])] = parsed

        elif name == "vkCmdBindDescriptorSets":
            bind_point_elem = chunk.find("./enum[@name='pipelineBindPoint']")
            bind_point = bind_point_elem.get("string", "") if bind_point_elem is not None else ""
            first_set = _read_numeric_text(chunk, "./uint[@name='firstSet']", default=0)
            descriptor_sets = chunk.find("./array[@name='pDescriptorSets']")

            target_sets = compute_descriptor_sets if "COMPUTE" in bind_point else graphics_descriptor_sets

            if descriptor_sets is not None:
                for index, set_elem in enumerate(descriptor_sets.findall("ResourceId")):
                    set_id = _to_int(set_elem.text)
                    slot = first_set + index
                    if set_id > 0:
                        target_sets[slot] = set_id
                    elif slot in target_sets:
                        target_sets.pop(slot)

        elif name == "vkCreateImage":
            image_elem = chunk.find("./ResourceId[@name='Image']")
            if image_elem is None:
                image_elem = chunk.find("./ResourceId[@name='image']")

            image_id = _to_int(image_elem.text if image_elem is not None else None)
            if image_id > 0:
                info = image_info_map.setdefault(image_id, {})
                create_info = chunk.find("./struct[@name='CreateInfo']")
                if create_info is not None:
                    format_elem = create_info.find("./enum[@name='format']")
                    extent_elem = create_info.find("./struct[@name='extent']")
                    mip_elem = create_info.find("./uint[@name='mipLevels']")
                    layers_elem = create_info.find("./uint[@name='arrayLayers']")

                    info["format"] = format_elem.get("string", "") if format_elem is not None else ""
                    if extent_elem is not None:
                        info["width"] = _read_numeric_text(extent_elem, "./uint[@name='width']", default=0)
                        info["height"] = _read_numeric_text(extent_elem, "./uint[@name='height']", default=0)
                    info["mip_levels"] = _to_int(mip_elem.text if mip_elem is not None else None, default=1)
                    info["array_layers"] = _to_int(layers_elem.text if layers_elem is not None else None, default=1)

        elif name == "vkBindImageMemory":
            image_elem = chunk.find("./ResourceId[@name='image']")
            memory_elem = chunk.find("./ResourceId[@name='memory']")
            offset_elem = chunk.find("./uint[@name='memoryOffset']")
            image_id = _to_int(image_elem.text if image_elem is not None else None)
            memory_id = _to_int(memory_elem.text if memory_elem is not None else None)
            if image_id > 0 and memory_id > 0:
                image_memory_map[image_id] = {
                    "memory_id": memory_id,
                    "memory_offset": _to_int(offset_elem.text if offset_elem is not None else None),
                }

        elif name == "vkCreateImageView":
            view_elem = chunk.find("./ResourceId[@name='ImageView']")
            if view_elem is None:
                view_elem = chunk.find("./ResourceId[@name='imageView']")
            if view_elem is None:
                # Many captures serialize vkCreateImageView output as "View".
                view_elem = chunk.find("./ResourceId[@name='View']")
            view_id = _to_int(view_elem.text if view_elem is not None else None)

            create_info = chunk.find("./struct[@name='CreateInfo']")
            image_elem = create_info.find("./ResourceId[@name='image']") if create_info is not None else None
            image_id = _to_int(image_elem.text if image_elem is not None else None)

            if view_id > 0 and image_id > 0:
                image_view_to_image[view_id] = image_id

        elif name == "Internal::Initial Contents":
            type_elem = chunk.find("./enum[@name='type']")
            type_name = type_elem.get("string", "") if type_elem is not None else ""
            if type_name == "eResDeviceMemory":
                memory_id_elem = chunk.find("./ResourceId[@name='id']")
                contents_elem = chunk.find("./buffer[@name='Contents']")
                size_elem = chunk.find("./uint[@name='ContentsSize']")
                memory_id = _to_int(memory_id_elem.text if memory_id_elem is not None else None)
                if memory_id > 0 and contents_elem is not None:
                    memory_initial_map[memory_id] = {
                        "buffer_index": _to_int(contents_elem.text),
                        "contents_size": _to_int(size_elem.text if size_elem is not None else None),
                    }

        elif name == "vkCreateShaderModule":
            module_id, module_meta = _parse_vulkan_shader_module_chunk(chunk)
            if module_id > 0:
                shader_module_map[module_id] = module_meta

        elif name == "vkCreateGraphicsPipelines":
            pipeline_elem = chunk.find("./ResourceId[@name='Pipeline']")
            pipeline_id = _to_int(pipeline_elem.text if pipeline_elem is not None else None)
            create_info = chunk.find("./struct[@name='CreateInfo']")
            stages_array = create_info.find("./array[@name='pStages']") if create_info is not None else None
            stages = []
            if stages_array is not None:
                for stage_struct in stages_array.findall("struct"):
                    stage_elem = stage_struct.find("./enum[@name='stage']")
                    module_elem = stage_struct.find("./ResourceId[@name='module']")
                    entry_elem = stage_struct.find("./string[@name='pName']")
                    stage_flag = stage_elem.get("string", "") if stage_elem is not None else ""
                    stage = _vulkan_stage_from_flag(stage_flag)
                    module_id = _to_int(module_elem.text if module_elem is not None else None)
                    entry = entry_elem.text.strip() if entry_elem is not None and entry_elem.text else "main"
                    if stage != "unknown" and module_id > 0:
                        stages.append({"stage": stage, "module_id": module_id, "entry": entry})

            if pipeline_id > 0 and stages:
                pipeline_shader_map[pipeline_id] = stages

        elif name == "vkCmdBindPipeline":
            bind_point_elem = chunk.find("./enum[@name='pipelineBindPoint']")
            bind_point = bind_point_elem.get("string", "") if bind_point_elem is not None else ""
            if "GRAPHICS" in bind_point:
                pipeline_elem = chunk.find("./ResourceId[@name='pipeline']")
                current_graphics_pipeline = _to_int(pipeline_elem.text if pipeline_elem is not None else None)

        if chunk_index == event_id:
            found = True
            if name != "vkCmdDrawIndexed":
                raise ValueError(f"event {event_id} is not vkCmdDrawIndexed")
            draw_info = {
                "index_count": _read_numeric_text(chunk, "./uint[@name='indexCount']"),
                "instance_count": _read_numeric_text(chunk, "./uint[@name='instanceCount']"),
                "first_index": _read_numeric_text(chunk, "./uint[@name='firstIndex']"),
                "vertex_offset": _read_numeric_text(chunk, "./int[@name='vertexOffset']"),
                "first_instance": _read_numeric_text(chunk, "./uint[@name='firstInstance']"),
            }
            break

        chunk.clear()

    if not found:
        raise ValueError(f"event {event_id} not found")

    for image_id, mem_info in image_memory_map.items():
        image_info = image_info_map.setdefault(image_id, {})
        memory_id = int(mem_info.get("memory_id", 0))
        image_info["memory_id"] = memory_id
        image_info["memory_offset"] = int(mem_info.get("memory_offset", 0))
        memory_initial = memory_initial_map.get(memory_id)
        if memory_initial:
            image_info["memory_buffer_index"] = int(memory_initial.get("buffer_index", 0))
            image_info["memory_contents_size"] = int(memory_initial.get("contents_size", 0))

    textures = _build_vulkan_texture_bindings(
        graphics_descriptor_sets=graphics_descriptor_sets,
        descriptor_set_contents=descriptor_set_contents,
        image_view_to_image=image_view_to_image,
        image_info_map=image_info_map,
    )

    shaders = []
    seen_stage = set()
    for stage_info in pipeline_shader_map.get(current_graphics_pipeline, []):
        stage = str(stage_info.get("stage", "unknown"))
        module_id = _to_int(stage_info.get("module_id", 0), default=0)
        if stage in seen_stage or module_id <= 0:
            continue
        seen_stage.add(stage)

        module_meta = shader_module_map.get(module_id, {})
        shaders.append(
            {
                "stage": stage,
                "resource_id": module_id,
                "bytecode_format": "spirv",
                "entry": str(stage_info.get("entry", "main") or "main"),
                "disassembly": f"SPIR-V module {module_id}",
                "path": f"{stage}.bin",
                "buffer_index": _to_int(module_meta.get("buffer_index", 0), default=0),
                "byte_length": _to_int(module_meta.get("code_size", 0), default=0),
            }
        )

    return {
        "index_buffer": index_binding,
        "vertex_buffers": vertex_bindings,
        "draw": draw_info,
        "textures": textures,
        "shaders": shaders,
        "pipeline_id": current_graphics_pipeline,
    }


def _parse_d3d11_stage_from_call(call_name: str) -> str:
    for stage in ("VS", "PS", "GS", "HS", "DS", "CS"):
        if f"{stage}Set" in call_name:
            return stage
    return "PS"


def _parse_d3d11_stage_from_create_shader(call_name: str) -> str:
    mapping = {
        "CreateVertexShader": "VS",
        "CreatePixelShader": "PS",
        "CreateGeometryShader": "GS",
        "CreateHullShader": "HS",
        "CreateDomainShader": "DS",
        "CreateComputeShader": "CS",
    }
    for key, value in mapping.items():
        if key in call_name:
            return value
    return ""


def extract_d3d11_bindings_for_event(xml_path: str, event_id: int) -> dict:
    event_id = int(event_id)
    current_vertex_bindings = []
    current_index_binding = None

    current_shader_resources = {}
    current_samplers = {}
    current_shaders = {}

    srv_to_resource = {}
    texture_resource_data = {}
    shader_bytecode_map = {}

    found = False

    for _, chunk in ET.iterparse(xml_path, events=("end",)):
        if chunk.tag != "chunk":
            continue

        name = chunk.get("name", "")
        chunk_index = _to_int(chunk.get("chunkIndex"), default=-1)

        if name == "ID3D11DeviceContext::IASetVertexBuffers":
            start_slot = _read_numeric_text(chunk, "./uint[@name='StartSlot']")
            buffers = []
            strides = []
            offsets = []

            arr = chunk.find("./array[@name='ppVertexBuffers']")
            if arr is not None:
                for elem in arr.findall("ResourceId"):
                    buffers.append(_to_int(elem.text))

            arr = chunk.find("./array[@name='pStrides']")
            if arr is not None:
                for elem in arr.findall("uint"):
                    strides.append(_to_int(elem.text))

            arr = chunk.find("./array[@name='pOffsets']")
            if arr is not None:
                for elem in arr.findall("uint"):
                    offsets.append(_to_int(elem.text))

            parsed = []
            for index, resource_id in enumerate(buffers):
                if resource_id <= 0:
                    continue
                parsed.append(
                    {
                        "slot": start_slot + index,
                        "resource_id": resource_id,
                        "byte_offset": offsets[index] if index < len(offsets) else 0,
                        "stride": strides[index] if index < len(strides) else 0,
                    }
                )
            current_vertex_bindings = parsed

        elif name == "ID3D11DeviceContext::IASetIndexBuffer":
            resource_elem = chunk.find("./ResourceId[@name='pIndexBuffer']")
            resource_id = _to_int(resource_elem.text if resource_elem is not None else None)
            fmt_elem = chunk.find("./enum[@name='Format']")
            fmt = fmt_elem.get("string", "") if fmt_elem is not None else ""
            offset = _read_numeric_text(chunk, "./uint[@name='Offset']")
            if resource_id > 0:
                current_index_binding = {
                    "resource_id": resource_id,
                    "byte_offset": offset,
                    "index_format": _parse_d3d11_index_format(fmt),
                }
            else:
                current_index_binding = None

        elif name == "ID3D11Device::CreateShaderResourceView":
            view_elem = chunk.find("./ResourceId[@name='pView']")
            if view_elem is None:
                view_elem = chunk.find("./ResourceId[@name='pResourceView']")
            resource_elem = chunk.find("./ResourceId[@name='pResource']")
            view_id = _to_int(view_elem.text if view_elem is not None else None)
            resource_id = _to_int(resource_elem.text if resource_elem is not None else None)
            if view_id > 0 and resource_id > 0:
                srv_to_resource[view_id] = resource_id

        elif name == "ID3D11Device::CreateTexture2D":
            texture_elem = chunk.find("./ResourceId[@name='pTexture']")
            texture_id = _to_int(texture_elem.text if texture_elem is not None else None)
            if texture_id > 0:
                desc = chunk.find("./struct[@name='Descriptor']")
                format_elem = desc.find("./enum[@name='Format']") if desc is not None else None
                width_elem = desc.find("./uint[@name='Width']") if desc is not None else None
                height_elem = desc.find("./uint[@name='Height']") if desc is not None else None

                data_elem = chunk.find("./buffer[@name='SubresourceContents']")
                length_elem = chunk.find("./uint[@name='SubresourceContentsLength']")

                texture_resource_data[texture_id] = {
                    "buffer_index": _to_int(data_elem.text if data_elem is not None else None),
                    "byte_length": _to_int(length_elem.text if length_elem is not None else data_elem.get("byteLength") if data_elem is not None else None),
                    "width": _to_int(width_elem.text if width_elem is not None else None),
                    "height": _to_int(height_elem.text if height_elem is not None else None),
                    "format": format_elem.get("string", "") if format_elem is not None else "",
                }

        elif "SetShaderResources" in name:
            stage = _parse_d3d11_stage_from_call(name)
            stage_map = current_shader_resources.setdefault(stage, {})
            start_slot = _read_numeric_text(chunk, "./uint[@name='StartSlot']", default=0)
            arr = chunk.find("./array[@name='ppShaderResourceViews']")
            if arr is not None:
                for index, elem in enumerate(arr.findall("ResourceId")):
                    slot = start_slot + index
                    srv_id = _to_int(elem.text)
                    if srv_id > 0:
                        stage_map[slot] = srv_id
                    elif slot in stage_map:
                        stage_map.pop(slot)

        elif "SetSamplers" in name:
            stage = _parse_d3d11_stage_from_call(name)
            stage_map = current_samplers.setdefault(stage, {})
            start_slot = _read_numeric_text(chunk, "./uint[@name='StartSlot']", default=0)
            arr = chunk.find("./array[@name='ppSamplers']")
            if arr is not None:
                for index, elem in enumerate(arr.findall("ResourceId")):
                    slot = start_slot + index
                    sampler_id = _to_int(elem.text)
                    if sampler_id > 0:
                        stage_map[slot] = sampler_id
                    elif slot in stage_map:
                        stage_map.pop(slot)

        elif name.endswith("SetShader") and "SetShaderResources" not in name:
            stage = _parse_d3d11_stage_from_call(name)
            shader_elem = chunk.find("./ResourceId[@name='pShader']")
            shader_id = _to_int(shader_elem.text if shader_elem is not None else None)
            if shader_id > 0:
                current_shaders[stage] = shader_id
            elif stage in current_shaders:
                current_shaders.pop(stage)

        elif name.startswith("ID3D11Device::Create") and name.endswith("Shader"):
            stage = _parse_d3d11_stage_from_create_shader(name)
            shader_elem = chunk.find("./ResourceId[@name='pShader']")
            shader_id = _to_int(shader_elem.text if shader_elem is not None else None)
            bytecode_elem = chunk.find("./buffer[@name='pShaderBytecode']")
            length_elem = chunk.find("./uint[@name='BytecodeLength']")
            if stage and shader_id > 0:
                shader_bytecode_map[shader_id] = {
                    "stage": stage,
                    "buffer_index": _to_int(bytecode_elem.text if bytecode_elem is not None else None),
                    "byte_length": _to_int(length_elem.text if length_elem is not None else None),
                }

        if chunk_index == event_id:
            found = True
            if "DrawIndexed" not in name:
                raise ValueError(f"event {event_id} is not D3D11 DrawIndexed")
            draw_call = _parse_d3d11_draw_indexed_chunk(chunk, event_id)

            textures = []
            for stage in sorted(current_shader_resources.keys()):
                resource_slots = current_shader_resources.get(stage, {})
                sampler_slots = current_samplers.get(stage, {})
                for slot in sorted(resource_slots.keys()):
                    srv_id = int(resource_slots.get(slot, 0))
                    if srv_id <= 0:
                        continue
                    resource_id = int(srv_to_resource.get(srv_id, 0))
                    texture_meta = texture_resource_data.get(resource_id, {})
                    textures.append(
                        {
                            "slot": f"{stage}.t{slot}",
                            "sampler": f"{stage}.s{slot}",
                            "texture_id": srv_id,
                            "view_id": srv_id,
                            "image_id": resource_id,
                            "resource_id": resource_id,
                            "sampler_id": int(sampler_slots.get(slot, 0)),
                            "path": f"tex_{srv_id}.bin",
                            "width": _to_int(texture_meta.get("width", 0), default=0),
                            "height": _to_int(texture_meta.get("height", 0), default=0),
                            "format": str(texture_meta.get("format", "")),
                            "buffer_index": _to_int(texture_meta.get("buffer_index", 0), default=0),
                            "byte_offset": 0,
                            "byte_length": _to_int(texture_meta.get("byte_length", 0), default=0),
                        }
                    )

            shaders = []
            for stage in sorted(current_shaders.keys()):
                shader_id = int(current_shaders.get(stage, 0))
                if shader_id <= 0:
                    continue
                shader_meta = shader_bytecode_map.get(shader_id, {})
                stage_short = stage.lower()
                shaders.append(
                    {
                        "stage": stage_short,
                        "resource_id": shader_id,
                        "bytecode_format": "dxbc",
                        "entry": "main",
                        "disassembly": f"DXBC shader {shader_id}",
                        "path": f"{stage_short}.bin",
                        "buffer_index": _to_int(shader_meta.get("buffer_index", 0), default=0),
                        "byte_length": _to_int(shader_meta.get("byte_length", 0), default=0),
                    }
                )

            return {
                "index_buffer": current_index_binding,
                "vertex_buffers": list(current_vertex_bindings),
                "draw": {
                    "index_count": draw_call.index_count,
                    "start_index_location": draw_call.start_index_location,
                    "base_vertex_location": draw_call.base_vertex_location,
                },
                "draw_name": name,
                "textures": textures,
                "shaders": shaders,
            }

        chunk.clear()

    if not found:
        raise ValueError(f"event {event_id} not found")

    raise ValueError(f"event {event_id} binding extraction failed")


def extract_vulkan_draw_indexed_call(xml_path: str, event_id: int) -> VulkanDrawIndexedCall:
    event_id = int(event_id)
    for _, chunk in ET.iterparse(xml_path, events=("end",)):
        if chunk.tag != "chunk":
            continue

        chunk_index = _to_int(chunk.get("chunkIndex"), default=-1)
        if chunk_index != event_id:
            chunk.clear()
            continue

        if chunk.get("name", "") != "vkCmdDrawIndexed":
            raise ValueError(f"event {event_id} is not vkCmdDrawIndexed")

        result = _parse_draw_indexed_chunk(chunk, event_id)
        chunk.clear()
        return result

    raise ValueError(f"event {event_id} not found")


def build_vulkan_buffer_memory_maps(xml_path: str) -> tuple[dict, dict, dict]:
    buffer_memory = {}
    memory_initial = {}
    buffer_sizes = {}

    for _, chunk in ET.iterparse(xml_path, events=("end",)):
        if chunk.tag != "chunk":
            continue

        name = chunk.get("name", "")

        if name == "vkCreateBuffer":
            buffer_elem = chunk.find("./ResourceId[@name='Buffer']")
            if buffer_elem is None:
                buffer_elem = chunk.find("./ResourceId[@name='buffer']")

            size_elem = chunk.find("./struct[@name='CreateInfo']/uint[@name='size']")
            if size_elem is None:
                size_elem = chunk.find("./uint[@name='size']")

            if buffer_elem is not None:
                buffer_id = _to_int(buffer_elem.text)
                buffer_sizes[buffer_id] = _to_int(size_elem.text if size_elem is not None else None)

        elif name == "vkBindBufferMemory":
            buffer_elem = chunk.find("./ResourceId[@name='buffer']")
            memory_elem = chunk.find("./ResourceId[@name='memory']")
            offset_elem = chunk.find("./uint[@name='memoryOffset']")
            if buffer_elem is not None and memory_elem is not None:
                buffer_id = _to_int(buffer_elem.text)
                memory_id = _to_int(memory_elem.text)
                memory_offset = _to_int(offset_elem.text if offset_elem is not None else None)
                buffer_memory[buffer_id] = {
                    "memory_id": memory_id,
                    "memory_offset": memory_offset,
                }

        elif name == "Internal::Initial Contents":
            type_elem = chunk.find("./enum[@name='type']")
            type_name = type_elem.get("string", "") if type_elem is not None else ""
            if type_name != "eResDeviceMemory":
                chunk.clear()
                continue

            memory_id_elem = chunk.find("./ResourceId[@name='id']")
            contents_elem = chunk.find("./buffer[@name='Contents']")
            size_elem = chunk.find("./uint[@name='ContentsSize']")

            if memory_id_elem is not None and contents_elem is not None:
                memory_id = _to_int(memory_id_elem.text)
                memory_initial[memory_id] = {
                    "buffer_index": _to_int(contents_elem.text),
                    "contents_size": _to_int(size_elem.text if size_elem is not None else None),
                }

        chunk.clear()

    return buffer_memory, memory_initial, buffer_sizes


def build_d3d11_buffer_data_map(xml_path: str, upto_event_id: int | None = None) -> dict:
    resource_map = {}

    max_event = None
    if upto_event_id is not None:
        max_event = int(upto_event_id)

    for _, chunk in ET.iterparse(xml_path, events=("end",)):
        if chunk.tag != "chunk":
            continue

        chunk_index = _to_int(chunk.get("chunkIndex"), default=-1)
        if max_event is not None and chunk_index > max_event:
            chunk.clear()
            continue

        name = chunk.get("name", "")

        if name == "ID3D11Device::CreateBuffer":
            resource_elem = chunk.find("./ResourceId[@name='pBuffer']")
            initial_elem = chunk.find("./buffer[@name='InitialData']")
            length_elem = chunk.find("./uint[@name='InitialDataLength']")
            desc_size = chunk.find("./struct[@name='pDesc']/uint[@name='ByteWidth']")

            resource_id = _to_int(resource_elem.text if resource_elem is not None else None)
            if resource_id > 0 and initial_elem is not None:
                resource_map[resource_id] = {
                    "buffer_index": _to_int(initial_elem.text),
                    "byte_length": _to_int(length_elem.text if length_elem is not None else initial_elem.get("byteLength")),
                    "byte_width": _to_int(desc_size.text if desc_size is not None else None),
                    "source": "CreateBuffer.InitialData",
                    "chunk_index": chunk_index,
                    "write_start": 0,
                    "write_end": _to_int(length_elem.text if length_elem is not None else initial_elem.get("byteLength")),
                }

        elif name == "ID3D11DeviceContext::Unmap":
            resource_elem = chunk.find("./ResourceId[@name='pResource']")
            written_elem = chunk.find("./buffer[@name='MapWrittenData']")
            start_elem = chunk.find("./uint[@name='Byte offset to start of written data']")
            end_elem = chunk.find("./uint[@name='Byte offset to end of written data']")

            resource_id = _to_int(resource_elem.text if resource_elem is not None else None)
            if resource_id > 0 and written_elem is not None:
                byte_length = _to_int(written_elem.get("byteLength"), default=0)
                write_start = _to_int(start_elem.text if start_elem is not None else None)
                write_end = _to_int(end_elem.text if end_elem is not None else None)
                if write_end > write_start:
                    byte_length = write_end - write_start

                resource_map[resource_id] = {
                    "buffer_index": _to_int(written_elem.text),
                    "byte_length": byte_length,
                    "byte_width": byte_length,
                    "source": "Unmap.MapWrittenData",
                    "chunk_index": chunk_index,
                    "write_start": write_start,
                    "write_end": write_end,
                }

        elif name == "ID3D11DeviceContext::UpdateSubresource":
            resource_elem = chunk.find("./ResourceId[@name='pDstResource']")
            src_elem = chunk.find("./buffer[@name='SourceData']")
            src_len = chunk.find("./uint[@name='SourceDataLength']")

            resource_id = _to_int(resource_elem.text if resource_elem is not None else None)
            if resource_id > 0 and src_elem is not None:
                byte_length = _to_int(src_len.text if src_len is not None else src_elem.get("byteLength"))
                resource_map[resource_id] = {
                    "buffer_index": _to_int(src_elem.text),
                    "byte_length": byte_length,
                    "byte_width": byte_length,
                    "source": "UpdateSubresource.SourceData",
                    "chunk_index": chunk_index,
                    "write_start": 0,
                    "write_end": byte_length,
                }

        chunk.clear()

    return resource_map



def _hydrate_vulkan_image_memory_info(image_info_map: dict, image_memory_map: dict, memory_initial_map: dict):
    for image_id, mem_info in image_memory_map.items():
        image_info = image_info_map.setdefault(image_id, {})
        memory_id = _to_int(mem_info.get("memory_id", 0), default=0)
        image_info["memory_id"] = memory_id
        image_info["memory_offset"] = _to_int(mem_info.get("memory_offset", 0), default=0)

        initial = memory_initial_map.get(memory_id)
        if initial:
            image_info["memory_buffer_index"] = _to_int(initial.get("buffer_index", 0), default=0)
            image_info["memory_contents_size"] = _to_int(initial.get("contents_size", 0), default=0)



def _collect_vulkan_shader_stages(pipeline_shader_map: dict, pipeline_id: int) -> list[str]:
    stages = []
    seen = set()
    for stage_info in pipeline_shader_map.get(int(pipeline_id), []):
        stage = str(stage_info.get("stage", "")).strip().lower()
        module_id = _to_int(stage_info.get("module_id", 0), default=0)
        if not stage or stage == "unknown" or module_id <= 0:
            continue
        if stage in seen:
            continue
        seen.add(stage)
        stages.append(stage)
    return stages



def _build_vulkan_mesh_compatibility_flags(index_binding: dict | None, vertex_bindings: list[dict], draw_info: dict) -> dict:
    has_index_binding = bool(index_binding and _to_int(index_binding.get("resource_id", 0), default=0) > 0)
    has_vertex_binding = any(_to_int(vb.get("resource_id", 0), default=0) > 0 for vb in (vertex_bindings or []))

    index_count = _to_int(draw_info.get("index_count", 0), default=0)
    first_index = _to_int(draw_info.get("first_index", 0), default=0)
    vertex_offset = _to_int(draw_info.get("vertex_offset", 0), default=0)

    vertex_offset_zero = vertex_offset == 0
    first_index_within_hint = first_index <= 8192

    reasons = []
    if not has_vertex_binding:
        reasons.append("missing_vertex_binding")
    if not has_index_binding:
        reasons.append("missing_index_binding")
    if index_count <= 0:
        reasons.append("index_count_zero")
    if not vertex_offset_zero:
        reasons.append("vertex_offset_non_zero")
    if not first_index_within_hint:
        reasons.append("first_index_out_of_hint_range")

    mesh_compatible = len(reasons) == 0

    return {
        "has_vertex_binding": has_vertex_binding,
        "has_index_binding": has_index_binding,
        "vertex_offset_zero": vertex_offset_zero,
        "first_index_within_hint": first_index_within_hint,
        "mesh_compatible": mesh_compatible,
        "mesh_exportable": mesh_compatible,
        "mesh_incompatible_reasons": reasons,
    }



def scan_vulkan_draw_texture_events(xml_path: str, preview_limit: int = 8, min_textures: int = 0) -> dict:
    descriptor_set_contents = {}
    graphics_descriptor_sets = {}
    compute_descriptor_sets = {}

    image_info_map = {}
    image_memory_map = {}
    memory_initial_map = {}
    image_view_to_image = {}

    shader_module_map = {}
    pipeline_shader_map = {}
    current_graphics_pipeline = 0

    index_binding = None
    vertex_bindings = []

    rows = []

    for _, chunk in ET.iterparse(xml_path, events=("end",)):
        if chunk.tag != "chunk":
            continue

        name = chunk.get("name", "")
        chunk_index = _to_int(chunk.get("chunkIndex"), default=-1)

        if name == "vkCmdBindIndexBuffer":
            index_binding = _parse_bind_index_buffer(chunk)

        elif name == "vkCmdBindVertexBuffers":
            vertex_bindings = _parse_bind_vertex_buffers(chunk)

        elif name == "vkUpdateDescriptorSetWithTemplate":
            descriptor_set_elem = chunk.find("./ResourceId[@name='descriptorSet']")
            descriptor_set_id = _to_int(descriptor_set_elem.text if descriptor_set_elem is not None else None)
            writes = chunk.find("./array[@name='Decoded Writes']")
            if writes is not None and descriptor_set_id > 0:
                set_bindings = descriptor_set_contents.setdefault(descriptor_set_id, {})
                for write_struct in writes.findall("struct"):
                    parsed = _parse_vulkan_descriptor_write_struct(write_struct, fallback_set_id=descriptor_set_id)
                    if not parsed:
                        continue
                    set_bindings[int(parsed["binding"])] = parsed

        elif name == "vkUpdateDescriptorSets":
            writes = chunk.find("./array[@name='pDescriptorWrites']")
            if writes is not None:
                for write_struct in writes.findall("struct"):
                    parsed = _parse_vulkan_descriptor_write_struct(write_struct, fallback_set_id=0)
                    if not parsed:
                        continue
                    set_id = int(parsed["set_id"])
                    descriptor_set_contents.setdefault(set_id, {})[int(parsed["binding"])] = parsed

        elif name == "vkCmdBindDescriptorSets":
            bind_point_elem = chunk.find("./enum[@name='pipelineBindPoint']")
            bind_point = bind_point_elem.get("string", "") if bind_point_elem is not None else ""
            first_set = _read_numeric_text(chunk, "./uint[@name='firstSet']", default=0)
            descriptor_sets = chunk.find("./array[@name='pDescriptorSets']")

            target_sets = compute_descriptor_sets if "COMPUTE" in bind_point else graphics_descriptor_sets

            if descriptor_sets is not None:
                for index, set_elem in enumerate(descriptor_sets.findall("ResourceId")):
                    set_id = _to_int(set_elem.text)
                    slot = first_set + index
                    if set_id > 0:
                        target_sets[slot] = set_id
                    elif slot in target_sets:
                        target_sets.pop(slot)

        elif name == "vkCreateImage":
            image_elem = chunk.find("./ResourceId[@name='Image']")
            if image_elem is None:
                image_elem = chunk.find("./ResourceId[@name='image']")

            image_id = _to_int(image_elem.text if image_elem is not None else None)
            if image_id > 0:
                info = image_info_map.setdefault(image_id, {})
                create_info = chunk.find("./struct[@name='CreateInfo']")
                if create_info is not None:
                    format_elem = create_info.find("./enum[@name='format']")
                    extent_elem = create_info.find("./struct[@name='extent']")
                    mip_elem = create_info.find("./uint[@name='mipLevels']")
                    layers_elem = create_info.find("./uint[@name='arrayLayers']")

                    info["format"] = format_elem.get("string", "") if format_elem is not None else ""
                    if extent_elem is not None:
                        info["width"] = _read_numeric_text(extent_elem, "./uint[@name='width']", default=0)
                        info["height"] = _read_numeric_text(extent_elem, "./uint[@name='height']", default=0)
                    info["mip_levels"] = _to_int(mip_elem.text if mip_elem is not None else None, default=1)
                    info["array_layers"] = _to_int(layers_elem.text if layers_elem is not None else None, default=1)

        elif name == "vkBindImageMemory":
            image_elem = chunk.find("./ResourceId[@name='image']")
            memory_elem = chunk.find("./ResourceId[@name='memory']")
            offset_elem = chunk.find("./uint[@name='memoryOffset']")
            image_id = _to_int(image_elem.text if image_elem is not None else None)
            memory_id = _to_int(memory_elem.text if memory_elem is not None else None)
            if image_id > 0 and memory_id > 0:
                image_memory_map[image_id] = {
                    "memory_id": memory_id,
                    "memory_offset": _to_int(offset_elem.text if offset_elem is not None else None),
                }

        elif name == "vkCreateImageView":
            view_elem = chunk.find("./ResourceId[@name='ImageView']")
            if view_elem is None:
                view_elem = chunk.find("./ResourceId[@name='imageView']")
            if view_elem is None:
                view_elem = chunk.find("./ResourceId[@name='View']")
            view_id = _to_int(view_elem.text if view_elem is not None else None)

            create_info = chunk.find("./struct[@name='CreateInfo']")
            image_elem = create_info.find("./ResourceId[@name='image']") if create_info is not None else None
            image_id = _to_int(image_elem.text if image_elem is not None else None)

            if view_id > 0 and image_id > 0:
                image_view_to_image[view_id] = image_id

        elif name == "Internal::Initial Contents":
            type_elem = chunk.find("./enum[@name='type']")
            type_name = type_elem.get("string", "") if type_elem is not None else ""
            if type_name == "eResDeviceMemory":
                memory_id_elem = chunk.find("./ResourceId[@name='id']")
                contents_elem = chunk.find("./buffer[@name='Contents']")
                size_elem = chunk.find("./uint[@name='ContentsSize']")
                memory_id = _to_int(memory_id_elem.text if memory_id_elem is not None else None)
                if memory_id > 0 and contents_elem is not None:
                    memory_initial_map[memory_id] = {
                        "buffer_index": _to_int(contents_elem.text),
                        "contents_size": _to_int(size_elem.text if size_elem is not None else None),
                    }

        elif name == "vkCreateShaderModule":
            module_id, module_meta = _parse_vulkan_shader_module_chunk(chunk)
            if module_id > 0:
                shader_module_map[module_id] = module_meta

        elif name == "vkCreateGraphicsPipelines":
            pipeline_elem = chunk.find("./ResourceId[@name='Pipeline']")
            pipeline_id = _to_int(pipeline_elem.text if pipeline_elem is not None else None)
            create_info = chunk.find("./struct[@name='CreateInfo']")
            stages_array = create_info.find("./array[@name='pStages']") if create_info is not None else None
            stages = []
            if stages_array is not None:
                for stage_struct in stages_array.findall("struct"):
                    stage_elem = stage_struct.find("./enum[@name='stage']")
                    module_elem = stage_struct.find("./ResourceId[@name='module']")
                    entry_elem = stage_struct.find("./string[@name='pName']")
                    stage_flag = stage_elem.get("string", "") if stage_elem is not None else ""
                    stage = _vulkan_stage_from_flag(stage_flag)
                    module_id = _to_int(module_elem.text if module_elem is not None else None)
                    entry = entry_elem.text.strip() if entry_elem is not None and entry_elem.text else "main"
                    if stage != "unknown" and module_id > 0:
                        stages.append({"stage": stage, "module_id": module_id, "entry": entry})

            if pipeline_id > 0 and stages:
                pipeline_shader_map[pipeline_id] = stages

        elif name == "vkCmdBindPipeline":
            bind_point_elem = chunk.find("./enum[@name='pipelineBindPoint']")
            bind_point = bind_point_elem.get("string", "") if bind_point_elem is not None else ""
            if "GRAPHICS" in bind_point:
                pipeline_elem = chunk.find("./ResourceId[@name='pipeline']")
                current_graphics_pipeline = _to_int(pipeline_elem.text if pipeline_elem is not None else None)

        elif name == "vkCmdDrawIndexed":
            draw_info = {
                "index_count": _read_numeric_text(chunk, "./uint[@name='indexCount']"),
                "instance_count": _read_numeric_text(chunk, "./uint[@name='instanceCount']"),
                "first_index": _read_numeric_text(chunk, "./uint[@name='firstIndex']"),
                "vertex_offset": _read_numeric_text(chunk, "./int[@name='vertexOffset']"),
                "first_instance": _read_numeric_text(chunk, "./uint[@name='firstInstance']"),
            }

            _hydrate_vulkan_image_memory_info(
                image_info_map=image_info_map,
                image_memory_map=image_memory_map,
                memory_initial_map=memory_initial_map,
            )

            textures = _build_vulkan_texture_bindings(
                graphics_descriptor_sets=graphics_descriptor_sets,
                descriptor_set_contents=descriptor_set_contents,
                image_view_to_image=image_view_to_image,
                image_info_map=image_info_map,
            )

            if int(min_textures) > 0 and len(textures) < int(min_textures):
                chunk.clear()
                continue

            row = {
                "event_id": int(chunk_index),
                "index_count": int(draw_info.get("index_count", 0)),
                "instance_count": int(draw_info.get("instance_count", 0)),
                "first_index": int(draw_info.get("first_index", 0)),
                "vertex_offset": int(draw_info.get("vertex_offset", 0)),
                "pipeline": int(current_graphics_pipeline),
                "shader_stages": _collect_vulkan_shader_stages(pipeline_shader_map, current_graphics_pipeline),
                "bound_descriptor_sets": {
                    str(int(set_index)): int(set_id)
                    for set_index, set_id in sorted(graphics_descriptor_sets.items())
                    if int(set_id) > 0
                },
                "texture_count": len(textures),
            }

            row.update(_build_vulkan_mesh_compatibility_flags(index_binding, vertex_bindings, draw_info))

            if int(preview_limit) > 0:
                row["textures_preview"] = textures[: int(preview_limit)]

            rows.append(row)

        chunk.clear()

    payload = {
        "summary": {
            "api": "Vulkan",
            "source_xml": str(xml_path),
            "total_draw_events": len(rows),
            "textured_draw_events": len([item for item in rows if int(item.get("texture_count", 0)) > 0]),
            "mesh_compatible_events": len([item for item in rows if bool(item.get("mesh_compatible"))]),
            "mesh_incompatible_events": len([item for item in rows if not bool(item.get("mesh_compatible"))]),
        },
        "events": rows,
    }
    return payload
