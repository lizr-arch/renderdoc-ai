import json
import os
import struct

from unity_manifest import build_manifest


def _stage_list(rd):
    stages = [("vertex", rd.ShaderStage.Vertex)]
    if hasattr(rd.ShaderStage, "Pixel"):
        stages.append(("pixel", rd.ShaderStage.Pixel))
    if hasattr(rd.ShaderStage, "Fragment"):
        stages.append(("fragment", rd.ShaderStage.Fragment))
    if hasattr(rd.ShaderStage, "Geometry"):
        stages.append(("geometry", rd.ShaderStage.Geometry))
    if hasattr(rd.ShaderStage, "Hull"):
        stages.append(("hull", rd.ShaderStage.Hull))
    if hasattr(rd.ShaderStage, "Domain"):
        stages.append(("domain", rd.ShaderStage.Domain))
    if hasattr(rd.ShaderStage, "Compute"):
        stages.append(("compute", rd.ShaderStage.Compute))
    return stages


def _unpack_data(rd, fmt, data):
    if fmt.Special():
        raise RuntimeError("Packed formats are not supported")

    format_chars = {
        rd.CompType.UInt: "xBHxIxxxL",
        rd.CompType.SInt: "xbhxixxxl",
        rd.CompType.Float: "xxexfxxxd",
    }

    format_chars[rd.CompType.UNorm] = format_chars[rd.CompType.UInt]
    format_chars[rd.CompType.UScaled] = format_chars[rd.CompType.UInt]
    format_chars[rd.CompType.SNorm] = format_chars[rd.CompType.SInt]
    format_chars[rd.CompType.SScaled] = format_chars[rd.CompType.SInt]

    vertex_format = str(fmt.compCount) + format_chars[fmt.compType][fmt.compByteWidth]
    value = struct.unpack_from(vertex_format, data, 0)

    if fmt.compType == rd.CompType.UNorm:
        divisor = float((2 ** (fmt.compByteWidth * 8)) - 1)
        value = tuple(float(i) / divisor for i in value)
    elif fmt.compType == rd.CompType.SNorm:
        max_neg = -float(2 ** (fmt.compByteWidth * 8)) / 2
        divisor = float(-(max_neg - 1))
        value = tuple((float(i) if (i == max_neg) else (float(i) / divisor)) for i in value)

    if fmt.BGRAOrder():
        value = tuple(value[i] for i in [2, 1, 0, 3])

    return value


def _get_mesh_inputs(rd, controller, draw):
    state = controller.GetPipelineState()

    ib = state.GetIBuffer()
    vbs = state.GetVBuffers()
    attrs = state.GetVertexInputs()

    mesh_inputs = []
    for attr in attrs:
        if attr.perInstance:
            continue

        mesh_inputs.append(
            {
                "name": attr.name,
                "format": attr.format,
                "vertex_resource_id": vbs[attr.vertexBuffer].resourceId,
                "vertex_byte_stride": vbs[attr.vertexBuffer].byteStride,
                "vertex_byte_offset": attr.byteOffset
                + vbs[attr.vertexBuffer].byteOffset
                + draw.vertexOffset * vbs[attr.vertexBuffer].byteStride,
                "index_resource_id": ib.resourceId,
                "index_byte_stride": ib.byteStride,
                "index_byte_offset": ib.byteOffset,
                "index_offset": draw.indexOffset,
                "num_indices": draw.numIndices,
                "base_vertex": draw.baseVertex,
                "indexed": bool(draw.flags & rd.ActionFlags.Indexed),
            }
        )

    return mesh_inputs


def _get_indices(rd, controller, mesh):
    index_format = "B"
    if mesh["index_byte_stride"] == 2:
        index_format = "H"
    elif mesh["index_byte_stride"] == 4:
        index_format = "I"

    index_format = str(mesh["num_indices"]) + index_format

    if mesh["indexed"] and mesh["index_resource_id"] != rd.ResourceId.Null():
        ib_data = controller.GetBufferData(mesh["index_resource_id"], mesh["index_byte_offset"], 0)
        offset = mesh["index_offset"] * mesh["index_byte_stride"]
        indices = struct.unpack_from(index_format, ib_data, offset)
        return [i + mesh["base_vertex"] for i in indices]

    return list(range(mesh["num_indices"]))


def _select_attr(mesh_inputs, keys):
    for attr in mesh_inputs:
        name = (attr["name"] or "").lower()
        if any(key in name for key in keys):
            return attr
    return None


def export_mesh(controller, draw, out_dir, texture_filename=None):
    import renderdoc as rd

    mesh_dir = os.path.join(out_dir, "mesh")
    os.makedirs(mesh_dir, exist_ok=True)

    mesh_inputs = _get_mesh_inputs(rd, controller, draw)
    if not mesh_inputs:
        obj_path = os.path.join(mesh_dir, "mesh.obj")
        with open(obj_path, "w", encoding="utf-8") as handle:
            handle.write("# No mesh inputs found\n")
        return {"obj": "mesh/mesh.obj", "mtl": None, "maxscript": None}

    pos_attr = _select_attr(mesh_inputs, ["pos", "position"])
    nrm_attr = _select_attr(mesh_inputs, ["norm"])
    uv_attr = _select_attr(mesh_inputs, ["tex", "uv"])

    indices = _get_indices(rd, controller, mesh_inputs[0])
    positions = []
    normals = []
    uvs = []

    for idx in indices:
        if pos_attr:
            offset = pos_attr["vertex_byte_offset"] + pos_attr["vertex_byte_stride"] * idx
            data = controller.GetBufferData(pos_attr["vertex_resource_id"], offset, 0)
            positions.append(_unpack_data(rd, pos_attr["format"], data))
        if nrm_attr:
            offset = nrm_attr["vertex_byte_offset"] + nrm_attr["vertex_byte_stride"] * idx
            data = controller.GetBufferData(nrm_attr["vertex_resource_id"], offset, 0)
            normals.append(_unpack_data(rd, nrm_attr["format"], data))
        if uv_attr:
            offset = uv_attr["vertex_byte_offset"] + uv_attr["vertex_byte_stride"] * idx
            data = controller.GetBufferData(uv_attr["vertex_resource_id"], offset, 0)
            uvs.append(_unpack_data(rd, uv_attr["format"], data))

    obj_path = os.path.join(mesh_dir, "mesh.obj")
    mtl_path = os.path.join(mesh_dir, "mesh.mtl")

    with open(obj_path, "w", encoding="utf-8") as obj:
        if texture_filename:
            obj.write("mtllib mesh.mtl\n")
            obj.write("usemtl material0\n")

        for pos in positions:
            obj.write(f"v {pos[0]} {pos[1]} {pos[2]}\n")

        if uvs:
            for uv in uvs:
                obj.write(f"vt {uv[0]} {uv[1]}\n")

        if normals:
            for nrm in normals:
                obj.write(f"vn {nrm[0]} {nrm[1]} {nrm[2]}\n")

        face_count = len(indices) // 3
        for i in range(face_count):
            v1 = i * 3 + 1
            v2 = i * 3 + 2
            v3 = i * 3 + 3
            if uvs and normals:
                obj.write(f"f {v1}/{v1}/{v1} {v2}/{v2}/{v2} {v3}/{v3}/{v3}\n")
            elif uvs:
                obj.write(f"f {v1}/{v1} {v2}/{v2} {v3}/{v3}\n")
            elif normals:
                obj.write(f"f {v1}//{v1} {v2}//{v2} {v3}//{v3}\n")
            else:
                obj.write(f"f {v1} {v2} {v3}\n")

    if texture_filename:
        with open(mtl_path, "w", encoding="utf-8") as mtl:
            mtl.write("newmtl material0\n")
            mtl.write(f"map_Kd {texture_filename}\n")

    maxscript_path = os.path.join(mesh_dir, "to_max.ms")
    with open(maxscript_path, "w", encoding="utf-8") as ms:
        ms.write(f"importFile \"{obj_path}\" #noPrompt\n")
        ms.write("saveMaxFile \"mesh.max\"\n")

    return {
        "obj": "mesh/mesh.obj",
        "mtl": "mesh/mesh.mtl" if texture_filename else None,
        "maxscript": "mesh/to_max.ms",
    }


def export_textures(controller, pipe, out_dir):
    import renderdoc as rd

    tex_dir = os.path.join(out_dir, "textures")
    os.makedirs(tex_dir, exist_ok=True)

    textures = []
    seen = set()

    for stage_name, stage in _stage_list(rd):
        try:
            resources = pipe.GetReadOnlyResources(stage, True)
        except Exception:
            continue

        for used in resources:
            res_id = int(used.descriptor.resource)
            if res_id == int(rd.ResourceId.Null()) or res_id in seen:
                continue
            seen.add(res_id)

            filename = f"tex_{res_id}.png"
            output_path = os.path.join(tex_dir, filename)

            save_data = rd.TextureSave()
            save_data.resourceId = used.descriptor.resource
            save_data.destType = rd.FileType.PNG
            save_data.mip = 0
            save_data.alpha = rd.AlphaMapping.Preserve

            try:
                controller.SaveTexture(save_data, output_path)
            except Exception:
                pass

            textures.append(
                {
                    "stage": stage_name,
                    "resource_id": res_id,
                    "filename": filename,
                }
            )

    return textures


def export_shaders(controller, pipe, out_dir, api):
    import renderdoc as rd

    shader_dir = os.path.join(out_dir, "shaders")
    os.makedirs(shader_dir, exist_ok=True)

    shaders = {}
    targets = controller.GetDisassemblyTargets(True)
    target = None
    for pref in ["HLSL", "GLSL", "SPIR-V"]:
        for t in targets:
            if pref.lower() in str(t).lower():
                target = t
                break
        if target:
            break
    if target is None and targets:
        target = targets[0]

    pipeline = pipe.GetGraphicsPipelineObject()

    for stage_name, stage in _stage_list(rd):
        refl = pipe.GetShaderReflection(stage)
        if not refl:
            continue

        res_id = pipe.GetShader(stage)
        out_file = f"{stage_name}.txt"
        if target and "hlsl" in str(target).lower():
            out_file = f"{stage_name}.hlsl"
        elif target and "glsl" in str(target).lower():
            out_file = f"{stage_name}.glsl"

        out_path = os.path.join(shader_dir, out_file)
        try:
            source = controller.DisassembleShader(pipeline, refl, target)
            if source:
                with open(out_path, "w", encoding="utf-8") as handle:
                    handle.write(source)
        except Exception as exc:
            with open(out_path, "w", encoding="utf-8") as handle:
                handle.write(f"// Disassemble failed: {exc}\n")

        shaders[stage_name] = {
            "resource_id": int(res_id),
            "target": str(target) if target else "",
            "file": f"shaders/{out_file}",
            "api": api,
        }

    return shaders


def export_unity_assets(rdc_path, event_id, api, out_dir):
    import renderdoc as rd

    cap = rd.OpenCaptureFile()
    if cap.OpenFile(rdc_path, "", None) != rd.ReplayStatus.Succeeded:
        raise RuntimeError("OpenFile failed")

    controller = cap.OpenCapture(rd.ReplayOptions(), None)
    if controller is None:
        raise RuntimeError("OpenCapture failed")

    action = find_action_by_event(controller.GetRootActions(), event_id)
    if action is None:
        controller.Shutdown()
        cap.Shutdown()
        raise RuntimeError("eventId not found")

    controller.SetFrameEvent(event_id, False)
    pipe = controller.GetPipelineState()

    textures = export_textures(controller, pipe, out_dir)
    first_texture = textures[0]["filename"] if textures else None
    mesh = export_mesh(controller, action, out_dir, texture_filename=first_texture)
    shaders = export_shaders(controller, pipe, out_dir, api)

    manifest = build_manifest(event_id, api, mesh, textures, shaders)
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2)

    controller.Shutdown()
    cap.Shutdown()


def find_action_by_event(actions, event_id):
    for action in actions:
        if action.eventId == event_id:
            return action
        if action.children:
            found = find_action_by_event(action.children, event_id)
            if found:
                return found
    return None
