import argparse
import json
import pathlib
import sys

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


def _api_name(pipeline_type):
    if isinstance(pipeline_type, str):
        return pipeline_type
    name = getattr(pipeline_type, "name", None)
    if name:
        return str(name)
    return str(pipeline_type)


def _write_manifest(out_dir, manifest):
    out_path = pathlib.Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    manifest_path = out_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest_path


def _base_manifest(rdc_path, event_id, out_dir):
    return {
        "rdc_path": str(rdc_path),
        "event_id": int(event_id),
        "outputs": {
            "vertex_buffers": "vertex_buffers/",
            "index_buffers": "index_buffers/",
            "shaders": "shaders/",
        },
        "data_provenance": {
            "pipeline_state": "ReplayController.GetPipelineState()",
            "buffers": "ReplayController.GetBufferData(resourceId, offset, len)",
            "shader_disassembly": "ReplayController.DisassembleShader(...)",
        },
    }


def _build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Extract vertex/index buffers and shader disassembly for a draw event."
    )
    parser.add_argument("--rdc", required=True, help="Path to .rdc capture")
    parser.add_argument("--event", required=True, type=int, help="EventId to extract")
    parser.add_argument("--out", required=True, help="Output directory")
    return parser


def main(argv=None):
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    manifest = _base_manifest(args.rdc, args.event, args.out)
    status_code = 0

    try:
        if rd is None:
            raise RuntimeError("renderdoc module not available")
        cap = rd.OpenCaptureFile()
        status = cap.OpenFile(args.rdc, "", None)
        if hasattr(rd, "ResultCode") and status != rd.ResultCode.Succeeded:
            raise RuntimeError(f"OpenFile failed: {status}")
        controller = cap.OpenCapture(rd.ReplayOptions(), None)
        if controller is None:
            raise RuntimeError("OpenCapture returned None")

        _extract_buffers(controller, args.event, args.out)
        _extract_shaders(controller, args.out)

        manifest["api"] = _api_name(controller.GetAPIProperties().pipelineType)
        manifest["status"] = "ok"
    except Exception as exc:
        manifest["status"] = "error"
        manifest["error"] = str(exc)
        status_code = 2
    finally:
        _write_manifest(args.out, manifest)

    if status_code != 0:
        sys.exit(status_code)


if __name__ == "__main__":
    main()
