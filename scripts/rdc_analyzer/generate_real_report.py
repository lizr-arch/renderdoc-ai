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

# 导入现有的报告生成模块
from generate_offline_report import generate_offline_html

# 导入 Pipeline State 解析函数
from parse_rdc_xml import parse_pipeline_state_from_related_calls


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
    
    # 处理 Vulkan/D3D12 Descriptor Sets (放入特殊阶段)
    for desc_set in resource_bindings.get("descriptorSets", []):
        # Vulkan 的 bindPoint 决定阶段
        bind_point = desc_set.get("bindPoint", "GRAPHICS")
        if "COMPUTE" in str(bind_point).upper():
            stage = "CS"
        else:
            stage = "ALL"  # Graphics pipeline, 适用于所有阶段
        
        stage_dict = get_stage_dict(stage)
        
        # 描述符集作为特殊的纹理/资源条目
        stage_dict["textures"].append({
            "slot": desc_set.get("setIndex", 0),
            "id": desc_set.get("layout", "DescriptorSet"),
            "name": f"DescriptorSet[{desc_set.get('setIndex', 0)}]",
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
        """
    )
    parser.add_argument("json_path", help="RDC JSON 数据文件路径")
    parser.add_argument("output_path", nargs="?", help="输出 HTML 文件路径（默认与输入同名）")
    parser.add_argument("--textures", "-t", dest="texture_dir",
                        help="纹理导出目录路径（包含 textures.json 和 PNG 文件）")
    
    args = parser.parse_args()
    
    json_path = Path(args.json_path)
    output_path = Path(args.output_path) if args.output_path else json_path.with_suffix('.html')
    texture_dir = Path(args.texture_dir) if args.texture_dir else None
    
    if not json_path.exists():
        print(f"Error: File not found: {json_path}")
        sys.exit(1)
    
    print(f"Loading {json_path}...")
    rdc_data = load_rdc_data(json_path)
    
    print("Converting to report format...")
    event_data = convert_to_report_format(rdc_data)
    
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
    )
    
    print(f"[OK] Report saved to: {output_path}")


if __name__ == "__main__":
    main()
