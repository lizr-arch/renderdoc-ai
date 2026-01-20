#!/usr/bin/env python3
"""
使用真实 RDC XML 数据生成 HTML 报告

用法:
    py -3 generate_real_report.py <capture.json> [output.html] [--textures <texture_dir>]

示例:
    # 基本用法（仅事件数据）
    py -3 generate_real_report.py g145_data.json report.html
    
    # 带纹理缩略图
    py -3 generate_real_report.py g145_data.json report.html --textures ../output/g145_textures
"""

import json
import sys
import base64
import argparse
from pathlib import Path

# 确保模块路径正确
_script_dir = Path(__file__).parent.resolve()
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

# 导入现有的报告生成模块
from generate_offline_report import generate_offline_html

# 导入 Pipeline State 解析函数
from parse_rdc_xml import parse_pipeline_state_from_related_calls

# 导入纹理优化建议生成器
from core.optimization_advisor import OptimizationAdvisor

# 导入 Shader 优化建议生成器 (TASK-009)
try:
    from core.optimization_standalone import generate_optimization_from_context
    SHADER_OPTIMIZATION_ENABLED = True
except ImportError as e:
    print(f"[WARN] Shader optimization analysis disabled: {e}")
    generate_optimization_from_context = None
    SHADER_OPTIMIZATION_ENABLED = False

# 导入性能分析器 (TASK-008)
# 使用独立版本避免 analyzers 包的相对导入问题
try:
    from core.bridge import XMLToContextBridge
    from core.performance_standalone import PerformanceAnalyzer
    PERFORMANCE_ENABLED = True
except ImportError as e:
    print(f"[WARN] Performance analysis disabled: {e}")
    PerformanceAnalyzer = None
    PERFORMANCE_ENABLED = False


def load_rdc_data(json_path):
    """加载解析后的 RDC JSON 数据"""
    with open(json_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def convert_mesh_info_to_mesh_data(mesh_info, event):
    """
    将 parse_rdc_xml 生成的 meshInfo 转换为 HTML 模板期望的 meshData 格式
    
    meshInfo 结构:
        - vertexBuffers: [{slot, buffer, stride, offset}, ...]
        - indexBuffer: {buffer, offset, format}
        - inputLayout: str
        - primitiveTopology: str
    
    meshData 结构 (模板期望):
        - statistics: {vertexCount, indexCount, triangleCount, topology, ...}
        - inputLayout: [{semantic, index, format, slot, offset, size}, ...]
        - vertexBuffers: [{index, buffer, stride, offset, elements}, ...]
        - indexBuffer: {buffer, offset, format, count}
    """
    if not mesh_info:
        return None
    
    vbs = mesh_info.get("vertexBuffers", [])
    ib = mesh_info.get("indexBuffer")
    topology = mesh_info.get("primitiveTopology", "UNKNOWN")
    
    # 获取事件中的顶点/索引计数
    vertex_count = event.get("vertexCount", 0)
    index_count = event.get("indexCount", 0)
    instance_count = event.get("instanceCount", 1)
    
    # 计算三角形数（假设 TriangleList）
    triangle_count = index_count // 3 if index_count > 0 else vertex_count // 3
    
    # 计算顶点复用率
    if triangle_count > 0 and index_count > 0:
        # 理想情况：每个顶点被多个三角形共享
        # 复用率 = 1 - (唯一顶点数 / 索引数)
        # 简化估算：使用 vertex_count / index_count
        reuse_ratio = 1.0 - (vertex_count / index_count) if index_count > vertex_count else 0.0
    else:
        reuse_ratio = 0.0
    
    # 估算缓冲区大小
    vb_sizes = {}
    for vb in vbs:
        stride = vb.get("stride", 0)
        # 估算：stride * vertex_count
        vb_sizes[str(vb.get("slot", 0))] = stride * vertex_count if stride > 0 else 0
    
    # 估算 IB 大小
    ib_format = ib.get("format", "") if ib else ""
    if "16" in ib_format or "UINT16" in ib_format or ib_format == "0":
        ib_elem_size = 2
    else:
        ib_elem_size = 4
    ib_size = index_count * ib_elem_size
    
    total_mesh_size = sum(vb_sizes.values()) + ib_size
    
    # 构建 meshData
    mesh_data = {
        "statistics": {
            "vertexCount": vertex_count,
            "indexCount": index_count,
            "triangleCount": triangle_count,
            "instanceCount": instance_count,
            "topology": simplify_topology(topology),
            "vertexBufferSizes": vb_sizes,
            "indexBufferSize": ib_size,
            "totalMeshSize": total_mesh_size,
            "vertexReuseRatio": max(0, min(1, reuse_ratio)),
        },
        "vertexBuffers": [
            {
                "index": vb.get("slot", i),
                "buffer": vb.get("buffer", ""),
                "stride": vb.get("stride", 0),
                "offset": vb.get("offset", 0),
                "elements": [],  # 需要 Input Layout 详情才能填充
            }
            for i, vb in enumerate(vbs)
        ],
    }
    
    # 添加 Index Buffer
    if ib:
        mesh_data["indexBuffer"] = {
            "buffer": ib.get("buffer", ""),
            "offset": ib.get("offset", 0),
            "format": simplify_index_format(ib.get("format", "")),
            "count": index_count,
        }
    
    # 如果有 input layout ID，添加引用
    if mesh_info.get("inputLayout"):
        mesh_data["inputLayoutId"] = mesh_info.get("inputLayout")
    
    return mesh_data


def simplify_topology(topology):
    """简化拓扑名称"""
    if not topology:
        return "Unknown"
    
    # 移除前缀
    topology = str(topology)
    topology = topology.replace("D3D11_PRIMITIVE_TOPOLOGY_", "")
    topology = topology.replace("D3D_PRIMITIVE_TOPOLOGY_", "")
    topology = topology.replace("VK_PRIMITIVE_TOPOLOGY_", "")
    
    return topology


def convert_resource_bindings_to_template_format(resource_bindings):
    """
    将 parse_rdc_xml 生成的 resourceBindings 转换为 HTML 模板期望的 bindings 格式
    
    输入格式 (from parse_rdc_xml.py):
        {
            "shaderResources": [{"stage": "PS", "slot": 0, "resourceId": "123"}, ...],
            "constantBuffers": [{"stage": "VS", "slot": 0, "resourceId": "456"}, ...],
            "samplers": [...],
            "descriptorSets": [...],
            "unorderedAccessViews": [...]
        }
    
    输出格式 (HTML template expects pipelineState.bindings):
        {
            "VS": {
                "textures": [{"slot": 0, "id": 123, "name": "..."}],
                "constantBuffers": [{"slot": 0, "resourceId": "456"}],
                "vertexBuffers": [],
                "indexBuffer": null
            },
            "PS": {
                "textures": [{"slot": 0, "id": 123}],
                "constantBuffers": [...],
                ...
            }
        }
    """
    if not resource_bindings:
        return {}
    
    # 按阶段分组的结构
    bindings_by_stage = {}
    
    def get_stage_dict(stage):
        """获取或创建指定阶段的绑定字典"""
        if stage not in bindings_by_stage:
            bindings_by_stage[stage] = {
                "textures": [],
                "constantBuffers": [],
                "samplers": [],
                "uavs": [],
                "vertexBuffers": [],
                "indexBuffer": None,
            }
        return bindings_by_stage[stage]
    
    # 处理 Shader Resources (SRVs) -> textures
    for srv in resource_bindings.get("shaderResources", []):
        stage = srv.get("stage", "PS")
        stage_dict = get_stage_dict(stage)
        
        # 尝试解析 resourceId 为整数
        res_id = srv.get("resourceId", "")
        try:
            id_num = int(res_id)
        except (ValueError, TypeError):
            id_num = res_id  # 保持字符串
        
        stage_dict["textures"].append({
            "slot": srv.get("slot", 0),
            "id": id_num,
            "name": f"Resource_{res_id}",
            "type": srv.get("type", "SRV"),
        })
    
    # 处理 Constant Buffers
    for cb in resource_bindings.get("constantBuffers", []):
        stage = cb.get("stage", "PS")
        stage_dict = get_stage_dict(stage)
        
        stage_dict["constantBuffers"].append({
            "slot": cb.get("slot", 0),
            "resourceId": cb.get("resourceId", ""),
            "name": f"cb{cb.get('slot', 0)}",
            "size": cb.get("size"),  # 可能为 None
        })
    
    # 处理 Samplers
    for sampler in resource_bindings.get("samplers", []):
        stage = sampler.get("stage", "PS")
        stage_dict = get_stage_dict(stage)
        
        stage_dict["samplers"].append({
            "slot": sampler.get("slot", 0),
            "resourceId": sampler.get("resourceId", ""),
        })
    
    # 处理 UAVs
    for uav in resource_bindings.get("unorderedAccessViews", []):
        stage = uav.get("stage", "CS")  # UAV 通常在 CS 或 PS
        stage_dict = get_stage_dict(stage)
        
        stage_dict["uavs"].append({
            "slot": uav.get("slot", 0),
            "resourceId": uav.get("resourceId", ""),
        })
    
    # 处理 Vulkan/D3D12 Descriptor Sets (展开内部资源)
    for desc_set in resource_bindings.get("descriptorSets", []):
        # Vulkan 的 bindPoint 决定阶段
        bind_point = desc_set.get("bindPoint", "GRAPHICS")
        if "COMPUTE" in str(bind_point).upper():
            stage = "CS"
        else:
            stage = "ALL"  # Graphics pipeline, 适用于所有阶段
        
        stage_dict = get_stage_dict(stage)
        
        set_index = desc_set.get("setIndex", 0)
        bindings = desc_set.get("bindings", [])
        
        if bindings:
            # 展开描述符集内的资源
            for binding in bindings:
                binding_index = binding.get("binding", 0)
                descriptor_type = binding.get("descriptorType", "")
                resources = binding.get("resources", [])
                
                for res in resources:
                    res_type = res.get("type", "")
                    res_id = res.get("resourceId", "")
                    
                    if res_type == "image":
                        # 图像资源 - 分类为纹理或 UAV
                        layout = res.get("layout", "")
                        if "STORAGE" in descriptor_type.upper():
                            # Storage Image 视为 UAV
                            stage_dict["uavs"].append({
                                "slot": binding_index,
                                "resourceId": res_id,
                                "setIndex": set_index,
                                "imageLayout": layout,
                                "type": "StorageImage",
                                "descriptorType": descriptor_type,
                            })
                        else:
                            # Sampled Image 视为纹理
                            stage_dict["textures"].append({
                                "slot": binding_index,
                                "id": res_id,
                                "name": f"Image_{res_id}",
                                "type": "VkImage",
                                "setIndex": set_index,
                                "imageLayout": layout,
                                "descriptorType": descriptor_type,
                            })
                    
                    elif res_type == "buffer":
                        # 缓冲区资源
                        offset = res.get("offset", 0)
                        range_val = res.get("range", 0)
                        
                        if "UNIFORM" in descriptor_type.upper():
                            # Uniform Buffer 视为 Constant Buffer
                            stage_dict["constantBuffers"].append({
                                "slot": binding_index,
                                "resourceId": res_id,
                                "name": f"UBO_{binding_index}",
                                "setIndex": set_index,
                                "offset": offset,
                                "size": range_val,  # HTML 模板期望 size 字段
                                "range": range_val,
                                "descriptorType": descriptor_type,
                            })
                        else:
                            # Storage Buffer / Texel Buffer 视为 UAV
                            stage_dict["uavs"].append({
                                "slot": binding_index,
                                "resourceId": res_id,
                                "setIndex": set_index,
                                "offset": offset,
                                "range": range_val,
                                "type": "StorageBuffer",
                                "descriptorType": descriptor_type,
                            })
                    
                    elif res_type == "sampler":
                        # 采样器
                        stage_dict["samplers"].append({
                            "slot": binding_index,
                            "resourceId": res_id,
                            "setIndex": set_index,
                            "descriptorType": descriptor_type,
                        })
                    
                    elif res_type == "combined_image_sampler":
                        # Combined Image Sampler - 同时添加纹理和采样器
                        layout = res.get("layout", "")
                        sampler_id = res.get("sampler", "")
                        
                        stage_dict["textures"].append({
                            "slot": binding_index,
                            "id": res_id,
                            "name": f"Image_{res_id}",
                            "type": "CombinedImageSampler",
                            "setIndex": set_index,
                            "imageLayout": layout,
                            "descriptorType": descriptor_type,
                        })
                        
                        if sampler_id:
                            stage_dict["samplers"].append({
                                "slot": binding_index,
                                "resourceId": sampler_id,
                                "setIndex": set_index,
                                "type": "CombinedSampler",
                            })
        else:
            # 没有展开的 bindings，保留原始描述符集信息
            stage_dict["textures"].append({
                "slot": set_index,
                "id": desc_set.get("resourceId", "DescriptorSet"),
                "name": f"DescriptorSet[{set_index}]",
                "type": "DescriptorSet",
                "descriptorSetInfo": desc_set,  # 保留原始信息
            })
    
    return bindings_by_stage


def simplify_index_format(fmt):
    """简化索引格式名称"""
    if not fmt:
        return "UNKNOWN"
    
    fmt = str(fmt)
    
    # Vulkan: VK_INDEX_TYPE_UINT16 / VK_INDEX_TYPE_UINT32
    if "UINT16" in fmt or fmt == "0":
        return "R16_UINT"
    elif "UINT32" in fmt or fmt == "1":
        return "R32_UINT"
    
    # D3D11: DXGI_FORMAT_R16_UINT / DXGI_FORMAT_R32_UINT
    if "R16" in fmt:
        return "R16_UINT"
    elif "R32" in fmt:
        return "R32_UINT"
    
    return fmt


def convert_pipeline_state_to_bindings(pipeline_state):
    """
    将 parse_rdc_xml 输出的 pipelineState 新格式转换为 HTML 模板期望的 bindings 格式
    
    输入格式 (from parse_pipeline_state_from_binding_records):
        {
            "shaderResources": {"vs": [{slot, resourceId}], "ps": [...], ...},
            "constantBuffers": {"vs": [...], "ps": [...], ...},
            "samplers": {"vs": [...], "ps": [...], ...},
            "renderTargets": {"views": [{slot, resourceId}], "depthStencil": str},
            "vertexBuffers": [{slot, buffer, stride, offset}],
            "indexBuffer": {buffer, format, offset},
            ...
        }
    
    输出格式 (HTML template expects):
        {
            "VS": {
                "textures": [{slot, id, name, type}],
                "constantBuffers": [{slot, resourceId, name}],
                "samplers": [{slot, resourceId}],
                "vertexBuffers": [{slot, id, stride, offset}],
                "indexBuffer": {id, format, offset}
            },
            "PS": {...},
            ...
        }
    """
    if not pipeline_state:
        return {}
    
    bindings_by_stage = {}
    
    # 阶段名称映射: parse_rdc_xml 使用小写 (vs, ps, ...)
    # HTML 模板使用大写 (VS, PS, ...)
    stage_map = {
        "vs": "VS", "ps": "PS", "gs": "GS",
        "hs": "HS", "ds": "DS", "cs": "CS"
    }
    
    def get_stage_dict(stage_upper):
        """获取或创建指定阶段的绑定字典"""
        if stage_upper not in bindings_by_stage:
            bindings_by_stage[stage_upper] = {
                "textures": [],
                "constantBuffers": [],
                "samplers": [],
                "uavs": [],
                "vertexBuffers": [],
                "indexBuffer": None,
            }
        return bindings_by_stage[stage_upper]
    
    # 1. 转换 shaderResources -> textures
    shader_resources = pipeline_state.get("shaderResources", {})
    for stage_lower, resources in shader_resources.items():
        if not resources:
            continue
        stage_upper = stage_map.get(stage_lower, stage_lower.upper())
        stage_dict = get_stage_dict(stage_upper)
        
        for res in resources:
            res_id = res.get("resourceId", "")
            stage_dict["textures"].append({
                "slot": res.get("slot", 0),
                "id": res_id,
                "name": f"SRV_{res_id}",
                "type": "SRV",
            })
    
    # 2. 转换 constantBuffers
    constant_buffers = pipeline_state.get("constantBuffers", {})
    for stage_lower, buffers in constant_buffers.items():
        if not buffers:
            continue
        stage_upper = stage_map.get(stage_lower, stage_lower.upper())
        stage_dict = get_stage_dict(stage_upper)
        
        for buf in buffers:
            stage_dict["constantBuffers"].append({
                "slot": buf.get("slot", 0),
                "resourceId": buf.get("resourceId", ""),
                "name": f"cb{buf.get('slot', 0)}",
            })
    
    # 3. 转换 samplers
    samplers = pipeline_state.get("samplers", {})
    for stage_lower, sampler_list in samplers.items():
        if not sampler_list:
            continue
        stage_upper = stage_map.get(stage_lower, stage_lower.upper())
        stage_dict = get_stage_dict(stage_upper)
        
        for sampler in sampler_list:
            stage_dict["samplers"].append({
                "slot": sampler.get("slot", 0),
                "resourceId": sampler.get("resourceId", ""),
            })
    
    # 4. 转换 vertexBuffers (放到 VS 阶段)
    vertex_buffers = pipeline_state.get("vertexBuffers", [])
    if vertex_buffers:
        vs_dict = get_stage_dict("VS")
        for vb in vertex_buffers:
            vs_dict["vertexBuffers"].append({
                "slot": vb.get("slot", 0),
                "id": vb.get("buffer", ""),
                "stride": vb.get("stride", 0),
                "offset": vb.get("offset", 0),
            })
    
    # 5. 转换 indexBuffer (放到 VS 阶段)
    index_buffer = pipeline_state.get("indexBuffer")
    if index_buffer and index_buffer.get("buffer"):
        vs_dict = get_stage_dict("VS")
        vs_dict["indexBuffer"] = {
            "id": index_buffer.get("buffer", ""),
            "format": simplify_index_format(index_buffer.get("format", "")),
            "offset": index_buffer.get("offset", 0),
        }
    
    return bindings_by_stage


def merge_bindings(base_bindings, new_bindings):
    """
    合并两个 bindings 字典，new_bindings 覆盖 base_bindings
    """
    if not new_bindings:
        return base_bindings
    if not base_bindings:
        return new_bindings
    
    result = dict(base_bindings)
    
    for stage, stage_data in new_bindings.items():
        if stage not in result:
            result[stage] = stage_data
        else:
            # 合并同阶段的资源
            for key, value in stage_data.items():
                if key == "indexBuffer":
                    # indexBuffer 直接覆盖
                    if value:
                        result[stage][key] = value
                elif isinstance(value, list) and value:
                    # 列表类型：追加
                    if key not in result[stage]:
                        result[stage][key] = []
                    result[stage][key].extend(value)
    
    return result


def convert_to_report_format(rdc_data):
    """
    将 RDC 解析数据转换为报告生成器期望的格式
    """
    events = rdc_data.get("events", [])
    api_type = rdc_data.get("apiType", "Vulkan")
    
    # 构建事件树
    event_tree = []
    passes = []
    
    # 创建简化的 Pass 结构（基于 Draw 调用分组）
    current_pass = None
    pass_index = 0
    draws_in_pass = 0
    max_draws_per_pass = 20  # 每 N 个 draw 创建一个新 pass
    
    for event in events:
        event_type = event.get("type", "")
        
        # 转换事件格式
        # 注意: HTML 模板使用 "eid" 字段名
        converted_event = {
            "eid": event.get("eventId", 0),
            "name": event.get("name", ""),
            "type": event_type,
            "flags": event.get("flags", []),
            "duration": event.get("duration", 0),
        }
        
        # 转换 API 调用信息
        if event_type in ["draw", "dispatch", "copy"]:
            params = event.get("params", [])
            
            # 构建 apiCall 结构
            api_call = {
                "signature": event.get("name", ""),
                "params": [],
                "returnType": "void",
                "relatedCalls": event.get("relatedCalls", []),
            }
            
            # 转换参数
            for p in params:
                if p.get("name") not in ["commandBuffer", "DebugMessages"]:
                    api_call["params"].append({
                        "name": p.get("name", ""),
                        "value": p.get("value", ""),
                        "type": p.get("type", ""),
                    })
            
            converted_event["apiCall"] = api_call
            
            # 优先使用已解析的 pipelineState（从 parse_rdc_xml 中获取）
            if "pipelineState" in event:
                converted_event["pipelineState"] = event["pipelineState"]
            else:
                # 回退：从 relatedCalls 解析 Pipeline State（旧方式，可能丢失部分数据）
                related_calls = event.get("relatedCalls", [])
                if related_calls:
                    pipeline_state = parse_pipeline_state_from_related_calls(related_calls)
                    converted_event["pipelineState"] = pipeline_state
            
            # 集成 resourceBindings 到 pipelineState.bindings (TASK-003)
            if "resourceBindings" in event:
                resource_bindings = event["resourceBindings"]
                bindings_by_stage = convert_resource_bindings_to_template_format(resource_bindings)
                
                # 确保 pipelineState 存在
                if "pipelineState" not in converted_event:
                    converted_event["pipelineState"] = {}
                
                # 合并到 pipelineState.bindings
                if bindings_by_stage:
                    converted_event["pipelineState"]["bindings"] = bindings_by_stage
            
            # 转换 pipelineState 新格式字段为 bindings (新增 SRV/CBV/Sampler 解析)
            if "pipelineState" in converted_event:
                ps = converted_event["pipelineState"]
                # 检查是否有新格式字段 (shaderResources, constantBuffers, samplers 等)
                if any(key in ps for key in ["shaderResources", "constantBuffers", "samplers", "vertexBuffers", "indexBuffer"]):
                    # 转换新格式为 bindings
                    new_bindings = convert_pipeline_state_to_bindings(ps)
                    if new_bindings:
                        # 合并到现有 bindings（如果有的话）
                        existing_bindings = ps.get("bindings", {})
                        ps["bindings"] = merge_bindings(existing_bindings, new_bindings)
            
            # 添加顶点/索引计数
            if "vertexCount" in event:
                converted_event["vertexCount"] = event["vertexCount"]
            if "indexCount" in event:
                converted_event["indexCount"] = event["indexCount"]
            if "instanceCount" in event:
                converted_event["instanceCount"] = event["instanceCount"]
            
            # 转换 meshInfo 为 meshData (匹配 HTML 模板期望的格式)
            if "meshInfo" in event:
                mesh_info = event["meshInfo"]
                mesh_data = convert_mesh_info_to_mesh_data(mesh_info, event)
                if mesh_data:
                    converted_event["meshData"] = mesh_data
                
                # 从 meshInfo 提取 VB/IB 添加到 bindings (补充 Vulkan 数据)
                mesh_vbs = mesh_info.get("vertexBuffers", [])
                mesh_ib = mesh_info.get("indexBuffer")
                if mesh_vbs or mesh_ib:
                    # 确保 pipelineState.bindings 存在
                    if "pipelineState" not in converted_event:
                        converted_event["pipelineState"] = {}
                    ps = converted_event["pipelineState"]
                    if "bindings" not in ps:
                        ps["bindings"] = {}
                    
                    # 选择目标阶段：优先 VS，否则 ALL
                    target_stage = "VS" if "VS" in ps["bindings"] else "ALL"
                    if target_stage not in ps["bindings"]:
                        ps["bindings"][target_stage] = {
                            "textures": [],
                            "constantBuffers": [],
                            "samplers": [],
                            "uavs": [],
                            "vertexBuffers": [],
                            "indexBuffer": None,
                        }
                    
                    stage_bindings = ps["bindings"][target_stage]
                    
                    # 添加 vertexBuffers（仅当当前为空时）
                    if mesh_vbs and not stage_bindings.get("vertexBuffers"):
                        stage_bindings["vertexBuffers"] = [
                            {
                                "slot": vb.get("slot", i),
                                "id": vb.get("buffer", ""),
                                "stride": vb.get("stride", 0),
                                "offset": vb.get("offset", 0),
                            }
                            for i, vb in enumerate(mesh_vbs)
                        ]
                    
                    # 添加 indexBuffer（仅当当前为空时）
                    if mesh_ib and not stage_bindings.get("indexBuffer"):
                        stage_bindings["indexBuffer"] = {
                            "id": mesh_ib.get("buffer", ""),
                            "format": simplify_index_format(mesh_ib.get("format", "")),
                            "offset": mesh_ib.get("offset", 0),
                        }
            
            # Pass 分组逻辑
            if current_pass is None or draws_in_pass >= max_draws_per_pass:
                if current_pass:
                    passes.append(current_pass)
                
                current_pass = {
                    "name": f"Pass_{pass_index}",
                    "index": pass_index,
                    "events": [],
                    "drawCount": 0,
                    "dispatchCount": 0,
                }
                pass_index += 1
                draws_in_pass = 0
            
            current_pass["events"].append(converted_event)
            if event_type == "draw":
                current_pass["drawCount"] += 1
            elif event_type == "dispatch":
                current_pass["dispatchCount"] += 1
            draws_in_pass += 1
        
        event_tree.append(converted_event)
    
    # 添加最后一个 pass
    if current_pass:
        passes.append(current_pass)
    
    # 统计
    total_draws = sum(1 for e in events if e.get("type") == "draw")
    total_dispatches = sum(1 for e in events if e.get("type") == "dispatch")
    total_copies = sum(1 for e in events if e.get("type") == "copy")
    
    # 计算帧时间
    if events:
        start_ts = events[0].get("timestamp", 0)
        end_ts = events[-1].get("timestamp", 0)
        frame_duration_ns = end_ts - start_ts
        frame_duration_ms = frame_duration_ns / 1_000_000  # ns to ms
    else:
        frame_duration_ms = 0
    
    return {
        "apiType": api_type,
        "totalEvents": len(events),
        "totalDraws": total_draws,
        "totalDispatches": total_dispatches,
        "totalCopies": total_copies,
        "frameDuration": frame_duration_ms,  # HTML 模板使用 frameDuration
        "events": event_tree,
        "passes": passes,
    }


def convert_textures_from_rdc(rdc_textures):
    """
    将 RDC 解析的纹理数据转换为报告格式
    """
    textures = []
    
    for tex in rdc_textures:
        texture = {
            "resourceId": tex.get("resourceId", "0"),
            "name": tex.get("name", f"Image_{tex.get('resourceId', '?')}"),
            "width": tex.get("width", 0),
            "height": tex.get("height", 0),
            "depth": tex.get("depth", 1),
            "format": tex.get("formatName", tex.get("format", "Unknown")),
            "mips": tex.get("mipLevels", 1),
            "arraySize": tex.get("arrayLayers", 1),
            "sampleCount": 1,  # 从 samples 解析
            "byteSize": tex.get("memorySize", 0),
            "usage": tex.get("usage", ""),
        }
        
        # 解析 sample count
        samples_str = tex.get("samples", "VK_SAMPLE_COUNT_1_BIT")
        if "1_BIT" in samples_str:
            texture["sampleCount"] = 1
        elif "2_BIT" in samples_str:
            texture["sampleCount"] = 2
        elif "4_BIT" in samples_str:
            texture["sampleCount"] = 4
        elif "8_BIT" in samples_str:
            texture["sampleCount"] = 8
        
        textures.append(texture)
    
    return textures


def analyze_texture_usage(textures):
    """
    简单的纹理使用分析（基于尺寸和格式）
    """
    # 按大小排序
    sorted_by_size = sorted(textures, key=lambda t: t.get("byteSize", 0), reverse=True)
    
    # 热门纹理（最大的 10 个）
    hot_list = sorted_by_size[:10]
    
    # 冷门纹理（小于 4KB 的）
    cold_list = [t for t in textures if t.get("byteSize", 0) < 4096]
    
    total_memory = sum(t.get("byteSize", 0) for t in textures)
    
    return {
        "hot_list": hot_list,
        "cold_list": cold_list,
        "used_textures": len(textures),
        "unused_textures": 0,
        "unused_vram_bytes": 0,
        "total_vram_bytes": total_memory,
    }


def find_duplicate_textures(textures):
    """
    查找可能重复的纹理（相同尺寸和格式）
    """
    from collections import defaultdict
    
    # 按 (width, height, format) 分组
    groups = defaultdict(list)
    for tex in textures:
        key = (tex.get("width", 0), tex.get("height", 0), tex.get("format", ""))
        groups[key].append(tex)
    
    # 找出有多个纹理的组
    duplicate_groups = []
    wasted_bytes = 0
    
    for key, group in groups.items():
        if len(group) > 1:
            # 除了第一个，其他都算"浪费"
            group_wasted = sum(t.get("byteSize", 0) for t in group[1:])
            wasted_bytes += group_wasted
            
            duplicate_groups.append({
                "key": f"{key[0]}x{key[1]} {key[2]}",
                "count": len(group),
                "textures": group,
                "wastedBytes": group_wasted,
            })
    
    return {
        "groups": duplicate_groups,
        "summary": {
            "wastedVramBytes": wasted_bytes,
            "duplicateGroups": len(duplicate_groups),
        }
    }


def generate_minimal_texture_data():
    """生成最小纹理数据（真实数据中可能没有纹理信息）"""
    return {
        "textures": [],
        "duplicates": {"groups": [], "summary": {"wastedVramBytes": 0}},
        "usage": {
            "hot_list": [],
            "cold_list": [],
            "used_textures": 0,
            "unused_textures": 0,
            "unused_vram_bytes": 0,
        }
    }


def load_frame_thumbnail(json_path):
    """
    查找并加载帧缩略图
    
    搜索顺序：
    1. 同目录下的 <name>_thumb.png
    2. 同目录下的 <name>.png
    3. 同目录下的 thumb.png
    """
    json_path = Path(json_path)
    base_dir = json_path.parent
    stem = json_path.stem.replace("_data", "").replace("_capture", "")
    
    # 可能的缩略图路径
    candidates = [
        base_dir / f"{stem}_thumb.png",
        base_dir / f"{stem}.png", 
        base_dir / "thumb.png",
        base_dir / "frame_thumb.png",
    ]
    
    for thumb_path in candidates:
        if thumb_path.exists():
            try:
                with open(thumb_path, 'rb') as f:
                    data = f.read()
                b64 = base64.b64encode(data).decode('utf-8')
                print(f"  Loaded frame thumbnail: {thumb_path.name}")
                return f"data:image/png;base64,{b64}"
            except Exception as e:
                print(f"  [WARN] Failed to load thumbnail {thumb_path}: {e}")
    
    return None


def load_texture_thumbnails(texture_dir: Path) -> dict:
    """
    从纹理导出目录加载缩略图为 Base64 Data URI
    
    支持:
    - textures.json (C++ renderdoccmd export 输出)
    - manifest.json (Python export_textures.py 输出)
    
    Returns:
        {resource_id: base64_data_uri, ...}
    """
    thumbnail_map = {}
    
    # 查找元数据文件
    manifest_candidates = [
        texture_dir / "textures.json",
        texture_dir / "manifest.json",
    ]
    
    manifest_path = None
    for p in manifest_candidates:
        if p.exists():
            manifest_path = p
            break
    
    if not manifest_path:
        print(f"  [WARN] No textures.json or manifest.json in {texture_dir}")
        return thumbnail_map
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        for tex in manifest.get("textures", []):
            # 兼容两种格式：id (C++) 或 resource_id (Python)
            res_id = tex.get("id") or tex.get("resource_id")
            # 兼容两种格式：file (C++) 或 filename (Python)
            filename = tex.get("file") or tex.get("filename")
            
            if res_id is not None and filename:
                img_path = texture_dir / filename
                if img_path.exists():
                    try:
                        with open(img_path, 'rb') as img_file:
                            img_data = img_file.read()
                            b64_data = base64.b64encode(img_data).decode('utf-8')
                            # 根据扩展名确定 MIME 类型
                            ext = img_path.suffix.lower()
                            mime_type = {
                                '.png': 'image/png',
                                '.jpg': 'image/jpeg',
                                '.jpeg': 'image/jpeg',
                            }.get(ext, 'image/png')
                            thumbnail_map[str(res_id)] = f"data:{mime_type};base64,{b64_data}"
                    except IOError as e:
                        print(f"  [WARN] Failed to read {img_path}: {e}")
        
        print(f"  Loaded {len(thumbnail_map)} texture thumbnails from {manifest_path.name}")
        
    except (json.JSONDecodeError, IOError) as e:
        print(f"  [ERROR] Failed to load manifest: {e}")
    
    return thumbnail_map


def merge_thumbnails_to_textures(textures: list, thumbnail_map: dict) -> list:
    """
    将缩略图 Base64 数据合并到纹理列表
    """
    for tex in textures:
        res_id = str(tex.get("resourceId", ""))
        if res_id in thumbnail_map:
            tex["thumbnail"] = thumbnail_map[res_id]
    
    return textures


def create_textures_from_export(texture_dir: Path) -> list:
    """
    从导出目录的 manifest 创建纹理列表
    
    用于：RDC JSON 中没有纹理数据，但有导出的纹理文件
    """
    textures = []
    
    manifest_candidates = [
        texture_dir / "textures.json",
        texture_dir / "manifest.json",
    ]
    
    manifest_path = None
    for p in manifest_candidates:
        if p.exists():
            manifest_path = p
            break
    
    if not manifest_path:
        return textures
    
    try:
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        
        for tex in manifest.get("textures", []):
            # 兼容两种格式
            res_id = tex.get("id") or tex.get("resource_id") or 0
            
            texture = {
                "resourceId": str(res_id),
                "name": tex.get("name", f"Texture_{res_id}"),
                "width": tex.get("width", 0),
                "height": tex.get("height", 0),
                "depth": tex.get("depth", 1),
                "format": tex.get("format", "Unknown"),
                "mips": tex.get("mips", 1),
                "arraySize": tex.get("arrayLayers", 1),
                "sampleCount": tex.get("samples", 1),
                "byteSize": tex.get("byteSize", 0),
                "usage": "",
            }
            textures.append(texture)
        
        print(f"  Created {len(textures)} textures from export manifest")
        
    except (json.JSONDecodeError, IOError) as e:
        print(f"  [ERROR] Failed to parse manifest: {e}")
    
    return textures


def load_bindings_json(bindings_path: Path) -> dict:
    """
    加载 renderdoccmd export --bindings 生成的 bindings.json 文件
    
    格式:
    {
      "events": [
        {
          "eventId": 101,
          "name": "",
          "constantBuffers": [
            {
              "stage": "Vertex",
              "slot": 0,
              "name": "Batch",
              "size": 96,
              "members": [
                {"name": "WorldViewProj", "type": "Float", "rows": 4, "columns": 4, "value": [...]},
                {"name": "UVTransform", "type": "Float", "rows": 1, "columns": 4, "value": [...]},
                ...
              ]
            }
          ]
        },
        ...
      ]
    }
    
    Returns:
        {eventId: [constantBuffer, ...], ...}  按 eventId 索引的字典
    """
    if not bindings_path.exists():
        print(f"  [WARN] Bindings file not found: {bindings_path}")
        return {}
    
    try:
        with open(bindings_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        result = {}
        events = data.get("events", [])
        for evt in events:
            eid = evt.get("eventId")
            cbs = evt.get("constantBuffers", [])
            if eid is not None and cbs:
                result[eid] = cbs
        
        print(f"  Loaded CB data for {len(result)} events from bindings.json")
        return result
    
    except (json.JSONDecodeError, IOError) as e:
        print(f"  [ERROR] Failed to load bindings.json: {e}")
        return {}


def merge_cb_members_to_events(event_data: dict, cb_data_by_eid: dict) -> dict:
    """
    将 bindings.json 中的 CB 成员数据合并到 event_data 中
    
    目标：在每个 event 的 pipelineState.bindings.[STAGE].constantBuffers 中
    添加 members 字段
    """
    if not cb_data_by_eid:
        return event_data
    
    merged_count = 0
    
    for evt in event_data.get("events", []):
        eid = evt.get("eid")
        if eid not in cb_data_by_eid:
            continue
        
        cb_list = cb_data_by_eid[eid]
        
        # 确保 pipelineState.bindings 存在
        if "pipelineState" not in evt:
            evt["pipelineState"] = {}
        ps = evt["pipelineState"]
        if "bindings" not in ps:
            ps["bindings"] = {}
        bindings = ps["bindings"]
        
        # 按 stage 分组处理
        for cb in cb_list:
            stage = cb.get("stage", "")
            # 映射 stage 名称: "Vertex" -> "VS", "Pixel" -> "PS" 等
            stage_map = {
                "Vertex": "VS", "Pixel": "PS", "Geometry": "GS",
                "Hull": "HS", "Domain": "DS", "Compute": "CS"
            }
            stage_key = stage_map.get(stage, stage)
            
            if stage_key not in bindings:
                bindings[stage_key] = {
                    "textures": [],
                    "constantBuffers": [],
                    "samplers": [],
                    "uavs": [],
                    "vertexBuffers": [],
                    "indexBuffer": None,
                }
            
            stage_bindings = bindings[stage_key]
            
            # 查找或创建对应 slot 的 CB 条目
            slot = cb.get("slot", 0)
            cb_entry = None
            for existing_cb in stage_bindings.get("constantBuffers", []):
                if existing_cb.get("slot") == slot:
                    cb_entry = existing_cb
                    break
            
            if cb_entry is None:
                # 新建 CB 条目
                cb_entry = {
                    "slot": slot,
                    "resourceId": "",
                    "name": cb.get("name", f"cb{slot}"),
                    "size": cb.get("size", 0),
                }
                stage_bindings["constantBuffers"].append(cb_entry)
            
            # 添加 members 数据
            cb_entry["name"] = cb.get("name", cb_entry.get("name", f"cb{slot}"))
            cb_entry["size"] = cb.get("size", cb_entry.get("size", 0))
            cb_entry["members"] = cb.get("members", [])
            merged_count += 1
    
    print(f"  Merged CB members into {merged_count} constant buffers")
    return event_data


def load_pipeline_json(pipeline_json_path: Path) -> dict:
    """
    加载 extract_pipeline_state.py 在 RenderDoc Python 环境中生成的 JSON 文件
    
    格式 (extract_pipeline_state.py 输出):
    {
      "capture_file": "...",
      "events": [
        {
          "eventId": 101,
          "name": "DrawIndexed(...)",
          "shaders": {
            "VS": {"resourceId": "123", "name": "Vertex Shader", ...},
            "PS": {"resourceId": "456", "name": "Pixel Shader", ...}
          },
          "viewport": {"x": 0, "y": 0, "width": 1920, "height": 1080, ...},
          "blendState": {"enabled": true, ...},
          "depthState": {"testEnabled": true, "writeEnabled": true, ...},
          "meshData": {
            "topology": "TriangleList",
            "vertexBuffers": [...],
            "indexBuffer": {...}
          },
          ...
        }
      ]
    }
    
    Returns:
        {eventId: event_data, ...}  按 eventId 索引的字典
    """
    if not pipeline_json_path.exists():
        print(f"  [WARN] Pipeline JSON file not found: {pipeline_json_path}")
        return {}
    
    try:
        with open(pipeline_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        result = {}
        events = data.get("events", [])
        for evt in events:
            eid = evt.get("eventId")
            if eid is not None:
                result[eid] = evt
        
        print(f"  Loaded Pipeline State for {len(result)} events (Python API data)")
        return result
    
    except (json.JSONDecodeError, IOError) as e:
        print(f"  [ERROR] Failed to load pipeline JSON: {e}")
        return {}


def merge_pipeline_state_to_events(event_data: dict, pipeline_data_by_eid: dict) -> dict:
    """
    将 Python API 提取的 Pipeline State 数据合并到 event_data 中
    
    优先级: Python API 数据 > XML 解析数据
    
    Python API 数据更准确，因为它直接查询 GPU 状态，而非从 API 调用推断
    """
    if not pipeline_data_by_eid:
        return event_data
    
    merged_count = 0
    
    for evt in event_data.get("events", []):
        eid = evt.get("eid")
        if eid not in pipeline_data_by_eid:
            continue
        
        pipeline_evt = pipeline_data_by_eid[eid]
        
        # 确保 pipelineState 存在
        if "pipelineState" not in evt:
            evt["pipelineState"] = {}
        ps = evt["pipelineState"]
        
        # 合并 shaders（高优先级数据）
        if "shaders" in pipeline_evt:
            ps["shaders"] = pipeline_evt["shaders"]
        
        # 合并 viewport
        if "viewport" in pipeline_evt:
            ps["viewport"] = pipeline_evt["viewport"]
        
        # 合并 blendState
        if "blendState" in pipeline_evt:
            ps["blendState"] = pipeline_evt["blendState"]
        
        # 合并 depthState
        if "depthState" in pipeline_evt:
            ps["depthState"] = pipeline_evt["depthState"]
        
        # 合并 rasterizerState
        if "rasterizerState" in pipeline_evt:
            ps["rasterizerState"] = pipeline_evt["rasterizerState"]
        
        # 合并 bindings（Python API 版本优先）
        if "bindings" in pipeline_evt:
            # Python API bindings 完全覆盖 XML 版本
            ps["bindings"] = pipeline_evt["bindings"]
        
        # 合并 meshData
        if "meshData" in pipeline_evt:
            evt["meshData"] = pipeline_evt["meshData"]
        
        # 标记数据来源
        ps["dataSource"] = "python_api"
        
        merged_count += 1
    
    print(f"  Merged Pipeline State into {merged_count} events (Python API)")
    return event_data


def main():
    # 使用 argparse 解析命令行参数
    parser = argparse.ArgumentParser(
        description="使用 RDC JSON 数据生成 HTML 报告",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  py -3 generate_real_report.py g145_data.json
  py -3 generate_real_report.py g145_data.json report.html
  py -3 generate_real_report.py g145_data.json report.html --textures ../output/g145_textures
  py -3 generate_real_report.py g145_data.json report.html --textures ../output --bindings ../output/bindings.json
        """
    )
    parser.add_argument("json_path", help="RDC JSON 数据文件路径")
    parser.add_argument("output_path", nargs="?", help="输出 HTML 文件路径（默认与输入同名）")
    parser.add_argument("--textures", "-t", dest="texture_dir",
                        help="纹理导出目录路径（包含 textures.json 和 PNG 文件）")
    parser.add_argument("--bindings", "-b", dest="bindings_path",
                        help="CB 绑定数据文件路径（renderdoccmd export --bindings 生成的 bindings.json）")
    parser.add_argument("--pipeline-json", "-p", dest="pipeline_json_path",
                        help="Pipeline State JSON 文件路径（extract_pipeline_state.py 在 RenderDoc Python 环境中生成）")
    
    args = parser.parse_args()
    
    json_path = Path(args.json_path)
    output_path = Path(args.output_path) if args.output_path else json_path.with_suffix('.html')
    texture_dir = Path(args.texture_dir) if args.texture_dir else None
    bindings_path = Path(args.bindings_path) if args.bindings_path else None
    pipeline_json_path = Path(args.pipeline_json_path) if args.pipeline_json_path else None
    
    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        sys.exit(1)
    
    print(f"Loading {json_path}...")
    rdc_data = load_rdc_data(json_path)
    
    print("Converting to report format...")
    event_data = convert_to_report_format(rdc_data)
    
    # 加载并合并 CB 成员数据（如果提供了 bindings.json）
    if bindings_path:
        print(f"\nLoading CB bindings from {bindings_path}...")
        cb_data = load_bindings_json(bindings_path)
        if cb_data:
            event_data = merge_cb_members_to_events(event_data, cb_data)
    
    # 加载并合并 Pipeline State 数据（如果提供了 --pipeline-json）
    # 数据来自 extract_pipeline_state.py (需在 RenderDoc Python 环境中运行)
    if pipeline_json_path:
        print(f"\nLoading Pipeline State from {pipeline_json_path}...")
        pipeline_data = load_pipeline_json(pipeline_json_path)
        if pipeline_data:
            event_data = merge_pipeline_state_to_events(event_data, pipeline_data)
    
    print(f"  API: {event_data['apiType']}")
    print(f"  Events: {event_data['totalEvents']}")
    print(f"  Draws: {event_data['totalDraws']}")
    print(f"  Dispatches: {event_data['totalDispatches']}")
    print(f"  Copies: {event_data['totalCopies']}")
    print(f"  Passes: {len(event_data['passes'])}")
    print(f"  Frame Duration: {event_data['frameDuration']:.2f} ms")
    
    # 转换纹理数据
    rdc_textures = rdc_data.get("textures", [])
    if rdc_textures:
        print(f"\nProcessing {len(rdc_textures)} textures...")
        textures = convert_textures_from_rdc(rdc_textures)
        usage_analysis = analyze_texture_usage(textures)
        duplicate_analysis = find_duplicate_textures(textures)
        
        total_mem_mb = usage_analysis.get("total_vram_bytes", 0) / (1024*1024)
        print(f"  Total texture memory: {total_mem_mb:.2f} MB")
        print(f"  Hot textures: {len(usage_analysis.get('hot_list', []))}")
        print(f"  Duplicate groups: {duplicate_analysis['summary'].get('duplicateGroups', 0)}")
    else:
        print("\nNo texture data found, using minimal data...")
        textures = []
        usage_analysis = {
            "hot_list": [],
            "cold_list": [],
            "used_textures": 0,
            "unused_textures": 0,
            "unused_vram_bytes": 0,
        }
        duplicate_analysis = {"groups": [], "summary": {"wastedVramBytes": 0}}
    
    # 加载纹理缩略图（如果提供了纹理目录）
    thumbnail_count = 0
    if texture_dir:
        if texture_dir.exists():
            print(f"\nLoading texture thumbnails from {texture_dir}...")
            thumbnail_map = load_texture_thumbnails(texture_dir)
            
            if thumbnail_map:
                # 优先使用导出数据（因为 XML resourceId 与 Export id 不匹配）
                # 从导出目录创建纹理列表，替换 XML 数据
                print("  Replacing XML textures with exported textures (IDs don't match)...")
                textures = create_textures_from_export(texture_dir)
                textures = merge_thumbnails_to_textures(textures, thumbnail_map)
                thumbnail_count = len(textures)
                
                # 重新计算分析
                usage_analysis = analyze_texture_usage(textures)
                duplicate_analysis = find_duplicate_textures(textures)
                
                print(f"  Using {len(textures)} exported textures with {thumbnail_count} thumbnails")
        else:
            print(f"\n[WARN] Texture directory not found: {texture_dir}")
    
    # 加载帧缩略图
    frame_thumbnail = load_frame_thumbnail(json_path)
    
    # 生成优化建议 (TASK-009)
    print(f"\nGenerating optimization suggestions...")
    advisor = OptimizationAdvisor(
        textures=textures,
        rdc_name=json_path.stem,
        duplicate_analysis=duplicate_analysis,
        usage_analysis=usage_analysis,
    )
    optimization_report = advisor.analyze()
    optimization_data = optimization_report.to_dict()
    print(f"  Generated {optimization_data['total_items']} optimization suggestions")
    total_savings_mb = optimization_data['total_savings_bytes'] / (1024 * 1024)
    print(f"  Potential savings: {total_savings_mb:.2f} MB")
    
    # 生成性能分析报告 (TASK-008)
    print(f"\nGenerating performance analysis...")
    performance_data = None
    try:
        # 构建 AnalysisContext 需要的数据字典
        context_data = {
            "textures": textures,
            "buffers": [],  # 当前暂无 buffer 数据
            "draw_calls": [],
            "frame_summary": {
                "api": event_data.get("apiType", "Unknown"),
                "draw_count": event_data.get("totalDraws", 0),
                "dispatch_count": event_data.get("totalDispatches", 0),
                "total_triangles": 0,
                "total_vertices": 0,
            }
        }
        
        # 从 events 提取 draw calls
        for evt in event_data.get("events", []):
            if evt.get("type") == "draw":
                dc = {
                    "event_id": evt.get("eid", 0),
                    "type": evt.get("name", "Draw"),
                    "index_count": evt.get("indexCount", 0),
                    "vertex_count": evt.get("vertexCount", 0),
                    "instance_count": evt.get("instanceCount", 1),
                }
                # 提取 Shader 信息
                ps = evt.get("pipelineState", {})
                shaders = ps.get("shaders", {})
                dc["vs_id"] = shaders.get("VS", {}).get("resourceId", "")
                dc["ps_id"] = shaders.get("PS", {}).get("resourceId", "")
                
                context_data["draw_calls"].append(dc)
                context_data["frame_summary"]["total_vertices"] += dc["vertex_count"]
                context_data["frame_summary"]["total_triangles"] += dc["index_count"] // 3
        
        # 使用 Bridge 转换为 AnalysisContext
        analysis_context = XMLToContextBridge.convert(context_data, str(json_path))
        
        # 运行 PerformanceAnalyzer
        perf_analyzer = PerformanceAnalyzer(analysis_context)
        perf_analyzer.analyze()
        perf_report = perf_analyzer.report
        
        # 转换为 HTML 模板格式
        performance_data = {
            "overall_score": round(perf_report.overall_score, 1),
            "metrics": {
                "draw_calls": perf_report.total_draw_calls,
                "triangles": perf_report.total_triangles,
                "shader_changes": perf_report.total_shader_changes,
                "rt_changes": perf_report.total_rt_changes,
                "unique_textures": perf_report.unique_textures,
                "texture_memory": f"{perf_report.total_texture_memory_mb:.1f} MB",
            },
            "issues": [
                {
                    "rule_id": issue.rule_id,
                    "severity": issue.severity,
                    "title": issue.title,
                    "message": issue.message,
                    "suggestion": issue.suggestion,
                }
                for issue in perf_report.issues
            ],
            "recommendations": perf_report.recommendations,
        }
        
        print(f"  Performance Score: {perf_report.overall_score:.1f}/100")
        print(f"  Issues: {len(perf_report.issues)} ({perf_report.critical_count} critical, {perf_report.warning_count} warnings)")
        
    except Exception as e:
        print(f"  [WARN] Performance analysis failed: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"\nGenerating HTML report...")
    
    # 调用现有的 HTML 生成函数
    generate_offline_html(
        textures=textures,
        rdc_name=json_path.stem,
        output_path=str(output_path),
        duplicate_analysis=duplicate_analysis,
        usage_analysis=usage_analysis,
        event_pass_data=event_data,
        frame_thumbnail=frame_thumbnail,
        optimization_data=optimization_data,
        performance_data=performance_data,
    )
    
    print(f"[OK] Report saved to: {output_path}")


if __name__ == "__main__":
    main()
