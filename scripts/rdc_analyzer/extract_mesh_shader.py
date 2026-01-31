import pathlib

try:
    import renderdoc as rd
except ImportError:
    rd = None


def _api_is_d3d11(pipeline_type):
    if rd is not None and hasattr(rd, "GraphicsAPI") and pipeline_type == rd.GraphicsAPI.D3D11:
        return True
    if isinstance(pipeline_type, str):
        return pipeline_type.lower() == "d3d11"
    name = getattr(pipeline_type, "name", "")
    return str(name).lower() == "d3d11"


def _api_is_vulkan(pipeline_type):
    if rd is not None and hasattr(rd, "GraphicsAPI") and pipeline_type == rd.GraphicsAPI.Vulkan:
        return True
    if isinstance(pipeline_type, str):
        return pipeline_type.lower() == "vulkan"
    name = getattr(pipeline_type, "name", "")
    return str(name).lower() == "vulkan"


def _write_bin(path, data):
    with open(path, "wb") as handle:
        handle.write(data)


def _write_text(path, text):
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(text)


def _stage_name(stage):
    name = getattr(stage, "name", None)
    if name:
        return str(name).lower()
    if isinstance(stage, str):
        return stage.lower()
    return str(stage)


def _default_stages():
    if rd is not None and hasattr(rd, "ShaderStage"):
        return [rd.ShaderStage.Vertex, rd.ShaderStage.Fragment]
    return ["vertex", "fragment"]


def _shader_entry_point():
    if rd is not None and hasattr(rd, "ShaderEntryPoint"):
        return rd.ShaderEntryPoint()
    return None


def _extract_buffers(controller, event_id, out_dir):
    out_path = pathlib.Path(out_dir)
    vb_dir = out_path / "vertex_buffers"
    ib_dir = out_path / "index_buffers"
    vb_dir.mkdir(parents=True, exist_ok=True)
    ib_dir.mkdir(parents=True, exist_ok=True)

    controller.SetFrameEvent(event_id, True)
    pipe = controller.GetPipelineState()
    api = controller.GetAPIProperties().pipelineType

    if _api_is_d3d11(api):
        d3d11 = pipe.GetD3D11PipelineState()
        vbs = d3d11.inputAssembly.vertexBuffers
        ib = d3d11.inputAssembly.indexBuffer
    elif _api_is_vulkan(api):
        vk = pipe.GetVulkanPipelineState()
        vbs = vk.vertexInput.vertexBuffers
        ib = vk.inputAssembly.indexBuffer
    else:
        raise ValueError("unsupported pipeline type for buffer extraction")

    for vb in vbs:
        data = controller.GetBufferData(vb.resourceId, vb.byteOffset, vb.byteSize)
        _write_bin(vb_dir / f"vb_{vb.resourceId}.bin", data)

    ib_data = controller.GetBufferData(ib.resourceId, ib.byteOffset, ib.byteSize)
    _write_bin(ib_dir / f"ib_{ib.resourceId}.bin", ib_data)


def _extract_shaders(controller, out_dir, stages=None):
    out_path = pathlib.Path(out_dir)
    shader_dir = out_path / "shaders"
    shader_dir.mkdir(parents=True, exist_ok=True)

    pipe = controller.GetPipelineState()
    pipeline = pipe.GetGraphicsPipelineObject()
    stage_list = stages or _default_stages()

    for stage in stage_list:
        shader_id = pipe.GetShader(stage)
        refl = controller.GetShader(pipeline, shader_id, _shader_entry_point())
        asm = controller.DisassembleShader(pipeline, refl, "")
        stage_name = _stage_name(stage)
        _write_text(shader_dir / f"{stage_name}.asm", asm)


def extract_mesh_shader(rdc_path, event_id, out_dir):
    if event_id is None:
        raise ValueError("event_id required")
    raise NotImplementedError("mesh/shader extraction not implemented yet")
