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


def extract_mesh_shader(rdc_path, event_id, out_dir):
    if event_id is None:
        raise ValueError("event_id required")
    raise NotImplementedError("mesh/shader extraction not implemented yet")
