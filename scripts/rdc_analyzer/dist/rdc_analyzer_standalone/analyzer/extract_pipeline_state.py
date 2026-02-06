#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_pipeline_state.py - 使用 RenderDoc Python API 提取真实 Pipeline State 数据

功能:
- 从 RDC 文件提取每个 Draw Call 的真实 Pipeline State
- 包括 Shader、Viewport、Blend State、Depth State
- 包括 Mesh Data (顶点/索引信息、Input Layout)
- 包括资源绑定 (纹理、Constant Buffers)
- 输出 JSON 格式供 HTML 报告使用

用法:
1. 在 RenderDoc Python Shell 中运行:
   exec(open('scripts/rdc_analyzer/extract_pipeline_state.py').read())
   extract_to_json(controller, 'output.json')

2. 作为独立脚本运行 (需要 renderdoc 模块):
   python extract_pipeline_state.py capture.rdc output.json

作者: AI Assistant
日期: 2026-01-19
"""

import json
import sys
from typing import Dict, List, Any, Optional

# Try to import renderdoc
if 'renderdoc' not in sys.modules and '_renderdoc' not in sys.modules:
    try:
        import renderdoc
    except ImportError:
        print("Warning: renderdoc module not available. Run in RenderDoc Python Shell.")
        renderdoc = None

rd = renderdoc if renderdoc else None


def get_blend_factor_name(factor) -> str:
    """将 BlendMultiplier 枚举转换为可读名称"""
    if rd is None:
        return str(factor)
    
    factor_names = {
        rd.BlendMultiplier.Zero: "Zero",
        rd.BlendMultiplier.One: "One",
        rd.BlendMultiplier.SrcCol: "SrcColor",
        rd.BlendMultiplier.InvSrcCol: "InvSrcColor",
        rd.BlendMultiplier.DstCol: "DstColor",
        rd.BlendMultiplier.InvDstCol: "InvDstColor",
        rd.BlendMultiplier.SrcAlpha: "SrcAlpha",
        rd.BlendMultiplier.InvSrcAlpha: "InvSrcAlpha",
        rd.BlendMultiplier.DstAlpha: "DstAlpha",
        rd.BlendMultiplier.InvDstAlpha: "InvDstAlpha",
    }
    return factor_names.get(factor, str(factor))


def get_compare_func_name(func) -> str:
    """将 CompareFunction 枚举转换为可读名称"""
    if rd is None:
        return str(func)
    
    func_names = {
        rd.CompareFunction.Never: "Never",
        rd.CompareFunction.Less: "Less",
        rd.CompareFunction.Equal: "Equal",
        rd.CompareFunction.LessEqual: "LessEqual",
        rd.CompareFunction.Greater: "Greater",
        rd.CompareFunction.NotEqual: "NotEqual",
        rd.CompareFunction.GreaterEqual: "GreaterEqual",
        rd.CompareFunction.AlwaysTrue: "Always",
    }
    return func_names.get(func, str(func))


def get_cull_mode_name(mode) -> str:
    """将 CullMode 枚举转换为可读名称"""
    if rd is None:
        return str(mode)
    
    mode_names = {
        rd.CullMode.NoCull: "None",
        rd.CullMode.Front: "Front",
        rd.CullMode.Back: "Back",
        rd.CullMode.FrontAndBack: "FrontAndBack",
    }
    return mode_names.get(mode, str(mode))


def get_topology_name(topo) -> str:
    """将 Topology 枚举转换为可读名称"""
    if rd is None:
        return str(topo)
    
    topo_names = {
        rd.Topology.Unknown: "Unknown",
        rd.Topology.PointList: "PointList",
        rd.Topology.LineList: "LineList",
        rd.Topology.LineStrip: "LineStrip",
        rd.Topology.TriangleList: "TriangleList",
        rd.Topology.TriangleStrip: "TriangleStrip",
        rd.Topology.TriangleFan: "TriangleFan",
    }
    return topo_names.get(topo, str(topo))


def get_format_name(fmt) -> str:
    """获取格式的可读名称"""
    if rd is None or fmt is None:
        return "Unknown"
    
    try:
        return fmt.Name()
    except:
        return str(fmt)


def extract_shader_info(state, stage, controller=None) -> Optional[Dict[str, Any]]:
    """提取指定着色器阶段的信息
    
    Args:
        state: PipelineState 对象
        stage: ShaderStage 枚举值
        controller: ReplayController (可选，用于反汇编)
    """
    try:
        shader = state.GetShader(stage)
        if shader == rd.ResourceId.Null():
            return None
        
        refl = state.GetShaderReflection(stage)
        entry_point = state.GetShaderEntryPoint(stage)
        
        info = {
            "resourceId": str(shader),
            "entryPoint": entry_point or "main",
        }
        
        if refl:
            info["debugName"] = refl.debugName or ""
            info["encoding"] = str(refl.encoding)
            
            # 获取 Constant Buffer 绑定
            if refl.constantBlocks:
                info["constantBuffers"] = []
                for i, cb in enumerate(refl.constantBlocks):
                    cb_info = {
                        "name": cb.name,
                        "bindPoint": cb.bindPoint,
                        "byteSize": cb.byteSize,
                    }
                    info["constantBuffers"].append(cb_info)
            
            # 获取资源绑定 (纹理、Sampler)
            if refl.readOnlyResources:
                info["textures"] = []
                for res in refl.readOnlyResources:
                    if res.isTexture:
                        tex_info = {
                            "name": res.name,
                            "bindPoint": res.bindPoint,
                            "isTexture": True,
                        }
                        info["textures"].append(tex_info)
            
            # 获取输入签名 (用于 UI 展示)
            if refl.inputSignature:
                info["inputSignature"] = []
                for sig in refl.inputSignature:
                    sig_info = {
                        "semantic": sig.semanticName,
                        "index": sig.semanticIndex,
                        "register": sig.regIndex,
                        "type": str(sig.varType),
                        "components": sig.compCount,
                    }
                    info["inputSignature"].append(sig_info)
            
            # 获取输出签名
            if refl.outputSignature:
                info["outputSignature"] = []
                for sig in refl.outputSignature:
                    sig_info = {
                        "semantic": sig.semanticName,
                        "index": sig.semanticIndex,
                        "register": sig.regIndex,
                        "type": str(sig.varType),
                        "components": sig.compCount,
                    }
                    info["outputSignature"].append(sig_info)
            
            # 获取反汇编代码 (如果有 controller)
            if controller is not None:
                try:
                    # 获取可用的反汇编目标
                    targets = controller.GetDisassemblyTargets(True)
                    target = targets[0] if targets else ""
                    
                    # 获取 pipeline ResourceId
                    pipeline = state.GetGraphicsPipelineObject()
                    if pipeline == rd.ResourceId.Null():
                        pipeline = state.GetComputePipelineObject()
                    
                    # 调用反汇编 API
                    disasm = controller.DisassembleShader(pipeline, refl, target)
                    if disasm:
                        # 限制长度，避免 JSON 过大
                        max_len = 50000  # 50KB
                        if len(disasm) > max_len:
                            info["sourceAsm"] = disasm[:max_len] + "\n\n// ... (truncated, total {} bytes)".format(len(disasm))
                            info["sourceAsmTruncated"] = True
                        else:
                            info["sourceAsm"] = disasm
                            info["sourceAsmTruncated"] = False
                except Exception as disasm_err:
                    info["sourceAsmError"] = str(disasm_err)
        
        return info
    except Exception as e:
        return {"error": str(e)}


def extract_viewport(state) -> Dict[str, Any]:
    """提取视口信息"""
    try:
        viewport = state.GetViewport(0)
        return {
            "x": viewport.x,
            "y": viewport.y,
            "width": viewport.width,
            "height": viewport.height,
            "minDepth": viewport.minDepth,
            "maxDepth": viewport.maxDepth,
        }
    except Exception as e:
        return {"error": str(e)}


def extract_scissor(state) -> Dict[str, Any]:
    """提取裁剪区域信息"""
    try:
        scissor = state.GetScissor(0)
        return {
            "x": scissor.x,
            "y": scissor.y,
            "width": scissor.width,
            "height": scissor.height,
            "enabled": scissor.enabled if hasattr(scissor, 'enabled') else True,
        }
    except Exception as e:
        return {"error": str(e)}


def extract_blend_state(state) -> Dict[str, Any]:
    """提取混合状态"""
    try:
        blend = state.GetColorBlend(0)
        return {
            "enabled": blend.enabled,
            "srcColor": get_blend_factor_name(blend.colorBlend.source),
            "dstColor": get_blend_factor_name(blend.colorBlend.destination),
            "colorOp": str(blend.colorBlend.operation),
            "srcAlpha": get_blend_factor_name(blend.alphaBlend.source),
            "dstAlpha": get_blend_factor_name(blend.alphaBlend.destination),
            "alphaOp": str(blend.alphaBlend.operation),
            "writeMask": blend.writeMask,
        }
    except Exception as e:
        return {"enabled": False, "error": str(e)}


def extract_depth_state(state) -> Dict[str, Any]:
    """提取深度状态"""
    try:
        depth = state.GetDepthState()
        return {
            "testEnabled": depth.depthEnable,
            "writeEnabled": depth.depthWrites,
            "compareFunc": get_compare_func_name(depth.depthFunction),
            "boundsEnable": depth.depthBoundsEnable if hasattr(depth, 'depthBoundsEnable') else False,
        }
    except Exception as e:
        return {"testEnabled": True, "writeEnabled": True, "compareFunc": "Less", "error": str(e)}


def extract_rasterizer_state(state) -> Dict[str, Any]:
    """提取光栅化状态"""
    try:
        raster = state.GetRasterizationState()
        return {
            "cullMode": get_cull_mode_name(raster.cullMode),
            "frontCCW": raster.frontCCW,
            "fillMode": str(raster.fillMode),
            "depthClampEnable": raster.depthClampEnable if hasattr(raster, 'depthClampEnable') else False,
            "depthBias": raster.depthBias,
            "slopeScaledDepthBias": raster.slopeScaledDepthBias,
        }
    except Exception as e:
        return {"cullMode": "Back", "error": str(e)}


def extract_vertex_inputs(state) -> List[Dict[str, Any]]:
    """提取顶点输入布局"""
    try:
        inputs = state.GetVertexInputs()
        result = []
        
        for attr in inputs:
            if not attr.used:
                continue
            
            result.append({
                "name": attr.name,
                "semanticIndex": attr.genericSemantic if hasattr(attr, 'genericSemantic') else 0,
                "format": get_format_name(attr.format),
                "byteOffset": attr.byteOffset,
                "vertexBuffer": attr.vertexBuffer,
                "perInstance": attr.perInstance,
                "instanceRate": attr.instanceRate,
            })
        
        return result
    except Exception as e:
        return [{"error": str(e)}]


def extract_vertex_buffers(state) -> List[Dict[str, Any]]:
    """提取顶点缓冲区绑定"""
    try:
        vbs = state.GetVBuffers()
        result = []
        
        for i, vb in enumerate(vbs):
            if vb.resourceId == rd.ResourceId.Null():
                continue
            
            result.append({
                "slot": i,
                "resourceId": str(vb.resourceId),
                "byteOffset": vb.byteOffset,
                "byteStride": vb.byteStride,
                "byteSize": vb.byteSize,
            })
        
        return result
    except Exception as e:
        return [{"error": str(e)}]


def extract_index_buffer(state) -> Optional[Dict[str, Any]]:
    """提取索引缓冲区绑定"""
    try:
        ib = state.GetIBuffer()
        if ib.resourceId == rd.ResourceId.Null():
            return None
        
        return {
            "resourceId": str(ib.resourceId),
            "byteOffset": ib.byteOffset,
            "byteStride": ib.byteStride,
            "byteSize": ib.byteSize,
        }
    except Exception as e:
        return {"error": str(e)}


def extract_render_targets(state) -> List[Dict[str, Any]]:
    """提取渲染目标绑定"""
    try:
        rts = state.GetOutputTargets()
        result = []
        
        for i, rt in enumerate(rts):
            if rt.resource == rd.ResourceId.Null():
                continue
            
            result.append({
                "slot": i,
                "resourceId": str(rt.resource),
                "firstMip": rt.firstMip,
                "firstSlice": rt.firstSlice,
                "numMips": rt.numMips,
                "numSlices": rt.numSlices,
            })
        
        return result
    except Exception as e:
        return [{"error": str(e)}]


def extract_depth_target(state) -> Optional[Dict[str, Any]]:
    """提取深度目标绑定"""
    try:
        ds = state.GetDepthTarget()
        if ds.resource == rd.ResourceId.Null():
            return None
        
        return {
            "resourceId": str(ds.resource),
            "firstMip": ds.firstMip,
            "firstSlice": ds.firstSlice,
            "numMips": ds.numMips,
            "numSlices": ds.numSlices,
        }
    except Exception as e:
        return {"error": str(e)}


def extract_event_pipeline_state(controller, action, include_disasm: bool = True) -> Dict[str, Any]:
    """提取单个事件的完整 Pipeline State
    
    Args:
        controller: ReplayController
        action: Action 对象
        include_disasm: 是否包含反汇编代码 (默认 True)
    """
    
    # 导航到该事件
    controller.SetFrameEvent(action.eventId, False)
    state = controller.GetPipelineState()
    
    # 构建 Pipeline State 结构
    pipeline_state = {
        "shaders": {},
        "viewport": extract_viewport(state),
        "scissor": extract_scissor(state),
        "blendState": extract_blend_state(state),
        "depthState": extract_depth_state(state),
        "rasterizerState": extract_rasterizer_state(state),
        "bindings": {
            "renderTargets": extract_render_targets(state),
            "depthTarget": extract_depth_target(state),
            "vertexBuffers": extract_vertex_buffers(state),
            "indexBuffer": extract_index_buffer(state),
        },
    }
    
    # 提取各 Shader 阶段 (传入 controller 以获取反汇编)
    shader_stages = [
        (rd.ShaderStage.Vertex, "Vertex Shader"),
        (rd.ShaderStage.Hull, "Hull Shader"),
        (rd.ShaderStage.Domain, "Domain Shader"),
        (rd.ShaderStage.Geometry, "Geometry Shader"),
        (rd.ShaderStage.Pixel, "Pixel Shader"),
        (rd.ShaderStage.Compute, "Compute Shader"),
    ]
    
    for stage, name in shader_stages:
        shader_info = extract_shader_info(
            state, 
            stage, 
            controller if include_disasm else None
        )
        if shader_info:
            pipeline_state["shaders"][name] = shader_info
    
    return pipeline_state


def extract_event_mesh_data(controller, action) -> Dict[str, Any]:
    """提取单个事件的 Mesh 数据"""
    
    controller.SetFrameEvent(action.eventId, False)
    state = controller.GetPipelineState()
    
    mesh_data = {
        "statistics": {
            "vertexCount": action.numIndices if hasattr(action, 'numIndices') else 0,
            "indexCount": action.numIndices if hasattr(action, 'numIndices') else 0,
            "instanceCount": action.numInstances if hasattr(action, 'numInstances') else 1,
            "baseVertex": action.baseVertex if hasattr(action, 'baseVertex') else 0,
            "indexOffset": action.indexOffset if hasattr(action, 'indexOffset') else 0,
            "vertexOffset": action.vertexOffset if hasattr(action, 'vertexOffset') else 0,
        },
        "topology": get_topology_name(state.GetPrimitiveTopology()),
        "inputLayout": extract_vertex_inputs(state),
    }
    
    # 计算三角形数量
    vertex_count = mesh_data["statistics"]["vertexCount"]
    topology = mesh_data["topology"]
    
    if topology == "TriangleList":
        mesh_data["statistics"]["triangleCount"] = vertex_count // 3
    elif topology == "TriangleStrip":
        mesh_data["statistics"]["triangleCount"] = max(0, vertex_count - 2)
    else:
        mesh_data["statistics"]["triangleCount"] = 0
    
    return mesh_data


def extract_event_api_call(controller, action, sd_file) -> Dict[str, Any]:
    """提取单个事件的 API 调用信息"""
    
    # 获取 API 名称
    api_name = action.GetName(sd_file) if sd_file else str(action.eventId)
    
    api_call = {
        "signature": api_name,
        "params": [],
        "returnType": "void",
        "relatedCalls": [],
    }
    
    # 尝试从 StructuredFile 获取详细参数
    try:
        if sd_file and hasattr(action, 'events') and action.events:
            for evt in action.events:
                chunk = sd_file.chunks[evt.chunkIndex]
                if chunk:
                    for child in chunk.data.children:
                        param = {
                            "name": child.name,
                            "type": str(child.type.name) if hasattr(child.type, 'name') else str(child.type),
                            "value": str(child.data) if hasattr(child, 'data') else "",
                        }
                        api_call["params"].append(param)
    except Exception as e:
        # 如果无法获取详细参数，使用基本信息
        if hasattr(action, 'numIndices') and action.numIndices > 0:
            api_call["params"].append({
                "name": "indexCount",
                "type": "uint32",
                "value": str(action.numIndices),
            })
        if hasattr(action, 'numInstances') and action.numInstances > 1:
            api_call["params"].append({
                "name": "instanceCount",
                "type": "uint32",
                "value": str(action.numInstances),
            })
    
    return api_call


def extract_all_events(controller) -> List[Dict[str, Any]]:
    """提取所有事件的详细数据，包含层级信息用于树形展示"""
    
    events = []
    sd_file = controller.GetStructuredFile()
    actions = controller.GetRootActions()
    
    def process_action(action, depth=0, parent_eid=None):
        """递归处理 Action，保留层级关系"""
        
        flags = action.flags
        is_draw = flags & rd.ActionFlags.Drawcall
        is_dispatch = flags & rd.ActionFlags.Dispatch
        is_copy = flags & rd.ActionFlags.Copy
        is_clear = flags & rd.ActionFlags.Clear
        is_push_marker = flags & rd.ActionFlags.PushMarker
        is_pop_marker = flags & rd.ActionFlags.PopMarker
        is_marker = is_push_marker or is_pop_marker
        
        # 确定事件类型
        if is_draw:
            event_type = "draw"
        elif is_dispatch:
            event_type = "dispatch"
        elif is_copy:
            event_type = "copy"
        elif is_clear:
            event_type = "clear"
        elif is_push_marker:
            event_type = "marker_push"
        elif is_pop_marker:
            event_type = "marker_pop"
        elif is_marker:
            event_type = "marker"
        else:
            event_type = "other"
        
        # 检查是否有子事件
        has_children = bool(action.children) and len(action.children) > 0
        child_count = len(action.children) if action.children else 0
        
        # 构建事件数据（包含层级信息）
        event_data = {
            "eid": action.eventId,
            "name": action.GetName(sd_file) if sd_file else f"Event_{action.eventId}",
            "type": event_type,
            "flags": [],
            "duration": 0,  # TODO: 从 timing 获取
            # 层级信息
            "depth": depth,
            "parentEid": parent_eid,
            "hasChildren": has_children,
            "childCount": child_count,
            "expanded": True if depth < 2 else False,  # 默认展开前两层
        }
        
        # 添加标志
        if is_draw:
            event_data["flags"].append("Draw")
        if is_dispatch:
            event_data["flags"].append("Dispatch")
        if flags & rd.ActionFlags.Indexed:
            event_data["flags"].append("Indexed")
        if flags & rd.ActionFlags.Instanced:
            event_data["flags"].append("Instanced")
        if flags & rd.ActionFlags.Indirect:
            event_data["flags"].append("Indirect")
        
        # 对 Draw/Dispatch 提取详细数据
        if is_draw or is_dispatch:
            try:
                event_data["apiCall"] = extract_event_api_call(controller, action, sd_file)
                event_data["pipelineState"] = extract_event_pipeline_state(controller, action)
                event_data["meshData"] = extract_event_mesh_data(controller, action)
            except Exception as e:
                event_data["error"] = str(e)
        
        events.append(event_data)
        
        # 递归处理子 Action（传递当前事件的 eid 作为 parent_eid）
        if action.children:
            for child in action.children:
                process_action(child, depth + 1, action.eventId)
    
    for action in actions:
        process_action(action, depth=0, parent_eid=None)
    
    return events


def extract_to_json(controller, output_path: str) -> None:
    """提取所有数据并保存为 JSON"""
    
    print(f"Extracting pipeline state data...")
    
    # 获取基本信息
    api_type = controller.GetAPIProperties().pipelineType.name
    textures = controller.GetTextures()
    buffers = controller.GetBuffers()
    
    # 提取所有事件
    events = extract_all_events(controller)
    
    # 构建输出数据
    output_data = {
        "apiType": api_type,
        "totalEvents": len(events),
        "totalDraws": sum(1 for e in events if e.get("type") == "draw"),
        "totalDispatches": sum(1 for e in events if e.get("type") == "dispatch"),
        "totalCopies": sum(1 for e in events if e.get("type") == "copy"),
        "textureCount": len(textures),
        "bufferCount": len(buffers),
        "events": events,
    }
    
    # 保存 JSON
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to {output_path}")
    print(f"  Events: {output_data['totalEvents']}")
    print(f"  Draws: {output_data['totalDraws']}")
    print(f"  Dispatches: {output_data['totalDispatches']}")


def load_capture(filename: str):
    """加载 RDC 文件并返回 controller"""
    
    if rd is None:
        raise RuntimeError("renderdoc module not available")
    
    cap = rd.OpenCaptureFile()
    result = cap.OpenFile(filename, '', None)
    
    if result != rd.ResultCode.Succeeded:
        raise RuntimeError(f"Couldn't open file: {result}")
    
    if not cap.LocalReplaySupport():
        raise RuntimeError("Capture cannot be replayed")
    
    result, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    
    if result != rd.ResultCode.Succeeded:
        raise RuntimeError(f"Couldn't initialise replay: {result}")
    
    return cap, controller


# 供 RenderDoc Python Shell 使用的快捷函数
def extract_current_capture(output_path: str = "pipeline_state.json"):
    """在 RenderDoc UI 中使用: 提取当前打开的 capture"""
    if 'pyrenderdoc' in globals():
        pyrenderdoc.Replay().BlockInvoke(lambda c: extract_to_json(c, output_path))
    else:
        print("Error: Must be run in RenderDoc Python Shell")


# 命令行入口
if __name__ == "__main__":
    if rd is None:
        print("Error: renderdoc module not available")
        print("Run this script in RenderDoc Python Shell, or ensure renderdoc.pyd is in PYTHONPATH")
        sys.exit(1)
    
    if len(sys.argv) < 3:
        print(f"Usage: python {sys.argv[0]} <capture.rdc> <output.json>")
        sys.exit(1)
    
    rdc_path = sys.argv[1]
    output_path = sys.argv[2]
    
    rd.InitialiseReplay(rd.GlobalEnvironment(), [])
    
    try:
        cap, controller = load_capture(rdc_path)
        extract_to_json(controller, output_path)
        controller.Shutdown()
        cap.Shutdown()
    finally:
        rd.ShutdownReplay()
