#!/usr/bin/env python3
"""
Timeline Builder - 事件时间线构建模块

从 report_bundle_generator.py 提取，负责：
- 构建聚合时间线 HTML
- 准备前端事件数据
- 构建事件树结构

Author: RDC Analyzer Team
Date: 2025-01-24
"""

from typing import Dict, List


def build_aggregated_timeline(
    events: List[Dict],
    textures: List[Dict] = None,
    shaders: List[Dict] = None
) -> str:
    """
    构建聚合的时间线 HTML
    
    策略：
    1. 按 marker_push/marker_pop 分组，每个 RenderPass 为一个色块
    2. 没有 Marker 的事件按固定数量（每50个）聚合为一个块
    3. 每个块显示：位置区间、颜色（按主要类型）、tooltip 显示事件数
    
    Args:
        events: 事件列表
        textures: 纹理列表（未使用，保留接口兼容）
        shaders: Shader 列表（未使用，保留接口兼容）
        
    Returns:
        HTML 字符串
    """
    if not events:
        return ""
    
    # 获取 EID 范围
    all_eids = [e.get("eventId") or e.get("eid", 0) for e in events]
    if not all_eids:
        return ""
    min_eid = min(all_eids)
    max_eid = max(all_eids) or 1
    eid_range = max_eid - min_eid or 1
    
    # 聚合块列表 [{start_eid, end_eid, name, type, count, color}]
    blocks = []
    
    # 方案1：按 depth=0 的 marker_push 分组
    # 找出所有顶级 Marker（depth=0 或 1）
    marker_stack = []
    current_block = None
    ungrouped_events = []
    
    for evt in events:
        eid = evt.get("eventId") or evt.get("eid", 0)
        evt_type = evt.get("type", "").lower()
        depth = evt.get("depth", 0)
        name = evt.get("name", "")
        
        if evt_type == "marker_push" and depth <= 1:
            # 保存之前的未分组事件
            if ungrouped_events and len(ungrouped_events) >= 5:
                blocks.append(_create_block_from_events(ungrouped_events, "Events"))
                ungrouped_events = []
            
            # 开始新的 RenderPass 块
            current_block = {
                "start_eid": eid,
                "name": name,
                "events": [evt],
                "draw_count": 0,
                "dispatch_count": 0,
                "clear_count": 0
            }
            marker_stack.append(current_block)
            
        elif evt_type == "marker_pop" and marker_stack:
            # 结束当前块
            block = marker_stack.pop()
            block["end_eid"] = eid
            block["events"].append(evt)
            
            # 计算主类型和颜色
            total = len(block["events"])
            draw_pct = block["draw_count"] / max(total, 1)
            dispatch_pct = block["dispatch_count"] / max(total, 1)
            
            if dispatch_pct > 0.3:
                color = "var(--accent-purple)"  # Compute-heavy
                main_type = "dispatch"
            elif draw_pct > 0.3:
                color = "var(--accent-green)"   # Draw-heavy
                main_type = "draw"
            elif block["clear_count"] > 0:
                color = "var(--accent-yellow)"  # Clear
                main_type = "clear"
            else:
                color = "var(--accent-blue)"    # Mixed
                main_type = "mixed"
            
            blocks.append({
                "start_eid": block["start_eid"],
                "end_eid": block["end_eid"],
                "name": block["name"],
                "count": len(block["events"]),
                "color": color,
                "main_type": main_type,
                "draw_count": block["draw_count"],
                "dispatch_count": block["dispatch_count"]
            })
            
            # 如果还有父级块，继续累加
            if marker_stack:
                current_block = marker_stack[-1]
            else:
                current_block = None
                
        else:
            # 普通事件
            if current_block:
                current_block["events"].append(evt)
                if "draw" in evt_type:
                    current_block["draw_count"] += 1
                elif "dispatch" in evt_type:
                    current_block["dispatch_count"] += 1
                elif "clear" in evt_type:
                    current_block["clear_count"] += 1
            else:
                ungrouped_events.append(evt)
    
    # 处理剩余的未分组事件
    if ungrouped_events:
        # 每 50 个事件一组
        for i in range(0, len(ungrouped_events), 50):
            chunk = ungrouped_events[i:i+50]
            if chunk:
                blocks.append(_create_block_from_events(
                    chunk, f"Events {i+1}-{i+len(chunk)}"
                ))
    
    # 如果没有聚合出块（可能没有 marker），按固定数量分块
    if not blocks and events:
        chunk_size = max(50, len(events) // 20)  # 最多 20 个块
        for i in range(0, len(events), chunk_size):
            chunk = events[i:i+chunk_size]
            if chunk:
                blocks.append(_create_block_from_events(
                    chunk, f"Events {i+1}-{i+len(chunk)}"
                ))
    
    # 生成 HTML
    html_parts = []
    for block in blocks:
        start_eid = block["start_eid"]
        end_eid = block.get("end_eid", start_eid)
        
        # 计算位置和宽度（百分比）
        left_pct = ((start_eid - min_eid) / eid_range) * 100
        width_pct = max(((end_eid - start_eid) / eid_range) * 100, 0.5)  # 最小 0.5%
        
        # Tooltip
        name = block.get("name", "")
        count = block.get("count", 0)
        draw_count = block.get("draw_count", 0)
        dispatch_count = block.get("dispatch_count", 0)
        tooltip = f"{name} ({count} events"
        if draw_count > 0:
            tooltip += f", {draw_count} draws"
        if dispatch_count > 0:
            tooltip += f", {dispatch_count} dispatches"
        tooltip += f") EID {start_eid}-{end_eid}"
        
        color = block.get("color", "var(--accent-blue)")
        
        html_parts.append(
            f'<div class="timeline-bar" '
            f'style="left:{left_pct:.2f}%;width:{width_pct:.2f}%;background:{color}" '
            f'data-start-eid="{start_eid}" data-end-eid="{end_eid}" '
            f'title="{tooltip}" onclick="scrollToEvent({start_eid})"></div>'
        )
    
    # 添加 Marker 分隔线（仅顶级）
    marker_lines = []
    for evt in events:
        evt_type = evt.get("type", "").lower()
        depth = evt.get("depth", 0)
        if evt_type == "marker_push" and depth == 0:
            eid = evt.get("eventId") or evt.get("eid", 0)
            pos_pct = ((eid - min_eid) / eid_range) * 100
            name = evt.get("name", "")[:15]  # 截断名称
            marker_lines.append(
                f'<div class="timeline-marker" style="left:{pos_pct:.2f}%" '
                f'data-label="{name}"></div>'
            )
    
    return "\n".join(html_parts + marker_lines[:10])  # 限制 Marker 数量避免过密


def _create_block_from_events(events: List[Dict], default_name: str) -> Dict:
    """从事件列表创建聚合块"""
    if not events:
        return {}
    
    eids = [e.get("eventId") or e.get("eid", 0) for e in events]
    draw_count = sum(1 for e in events if "draw" in e.get("type", "").lower())
    dispatch_count = sum(1 for e in events if "dispatch" in e.get("type", "").lower())
    clear_count = sum(1 for e in events if "clear" in e.get("type", "").lower())
    
    # 确定主类型和颜色
    total = len(events)
    if dispatch_count / max(total, 1) > 0.3:
        color = "var(--accent-purple)"
    elif draw_count / max(total, 1) > 0.3:
        color = "var(--accent-green)"
    elif clear_count > 0:
        color = "var(--accent-yellow)"
    else:
        color = "var(--accent-blue)"
    
    return {
        "start_eid": min(eids),
        "end_eid": max(eids),
        "name": default_name,
        "count": len(events),
        "color": color,
        "draw_count": draw_count,
        "dispatch_count": dispatch_count
    }


def prepare_events_for_frontend(
    events: List[Dict],
    textures: List[Dict],
    shaders: List[Dict]
) -> List[Dict]:
    """
    为前端转换事件数据，将 pipelineState 和 resourceBindings 
    转换为前端期望的 shaders, textures, renderTargets 格式
    
    Args:
        events: 原始事件列表
        textures: 纹理列表
        shaders: Shader 列表
        
    Returns:
        转换后的事件列表
    """
    prepared_events = []
    
    # 创建纹理快速查找表 (resourceId -> texture info)
    texture_lookup = {}
    for tex in textures:
        tex_id = str(tex.get("id") or tex.get("resourceId", ""))
        if tex_id:
            texture_lookup[tex_id] = tex
    
    # 创建 Shader 快速查找表 (resourceId -> shader info)
    shader_lookup = {}
    for shader in shaders:
        shader_id = str(shader.get("id") or shader.get("resource_id", ""))
        if shader_id:
            shader_lookup[shader_id] = shader
    
    for evt in events:
        # 复制基础事件数据
        prepared = dict(evt)
        
        # 确保 eid 字段存在（前端期望使用 eid）
        if "eid" not in prepared:
            prepared["eid"] = evt.get("eventId") or evt.get("eid", 0)
        
        # 提取 Shader 信息
        shaders_list = []
        pipeline_state = evt.get("pipelineState", {})
        shaders_data = pipeline_state.get("shaders", {})
        
        # 映射 Shader 类型
        shader_type_map = {
            "vs": "Vertex",
            "ps": "Pixel", 
            "gs": "Geometry",
            "hs": "Hull",
            "ds": "Domain",
            "cs": "Compute"
        }
        
        for shader_key, shader_type_name in shader_type_map.items():
            shader_info = shaders_data.get(shader_key)
            if shader_info and shader_info is not None:
                shader_id = str(shader_info.get("id", ""))
                shader_name = shader_info.get("name", f"{shader_type_name} Shader")
                
                # 尝试从 Shader 列表获取更多信息
                full_shader = shader_lookup.get(shader_id, {})
                if full_shader:
                    shader_name = full_shader.get("name", shader_name)
                
                shaders_list.append({
                    "type": shader_key.upper(),
                    "name": shader_name,
                    "id": shader_id
                })
        
        # 检查 pipeline 对象（Vulkan 常用）
        pipeline_info = shaders_data.get("pipeline")
        if pipeline_info and isinstance(pipeline_info, dict):
            pipeline_id = pipeline_info.get("id", "")
            if pipeline_id and not shaders_list:
                # 如果没有单独的 shader，使用 pipeline ID
                shaders_list.append({
                    "type": "Pipeline",
                    "name": f"Graphics Pipeline {pipeline_id}",
                    "id": str(pipeline_id)
                })
        
        prepared["shaders"] = shaders_list
        
        # 提取纹理绑定信息
        textures_list = []
        render_targets_list = []
        
        resource_bindings = evt.get("resourceBindings", {})
        
        # 从 descriptorSets 提取绑定的纹理
        descriptor_sets = resource_bindings.get("descriptorSets", [])
        for ds in descriptor_sets:
            bindings = ds.get("bindings", [])
            for binding in bindings:
                desc_type = binding.get("descriptorType", "")
                resources = binding.get("resources", [])
                
                # 检查是否是图像/纹理类型
                is_texture_type = any(t in desc_type.upper() for t in [
                    "SAMPLED_IMAGE", "COMBINED_IMAGE", "STORAGE_IMAGE",
                    "TEXTURE", "SRV", "UAV"
                ])
                
                if is_texture_type:
                    for res in resources:
                        res_id = str(res.get("resourceId", ""))
                        if res_id and res_id != "0":
                            # 从纹理列表查找详细信息
                            tex_info = texture_lookup.get(res_id, {})
                            tex_name = tex_info.get("name", f"Texture {res_id}")
                            thumbnail = tex_info.get("thumbnail", "")
                            
                            # 避免重复
                            if not any(t["id"] == res_id for t in textures_list):
                                textures_list.append({
                                    "id": res_id,
                                    "name": tex_name,
                                    "thumbnail": thumbnail,
                                    "binding": binding.get("binding", 0),
                                    "type": desc_type
                                })
        
        # 从 shaderResources 提取（D3D11/12 风格）
        shader_resources = resource_bindings.get("shaderResources", [])
        for sr in shader_resources:
            res_id = str(sr.get("resourceId", sr.get("id", "")))
            if res_id and res_id != "0":
                tex_info = texture_lookup.get(res_id, {})
                tex_name = tex_info.get("name", f"Texture {res_id}")
                thumbnail = tex_info.get("thumbnail", "")
                
                if not any(t["id"] == res_id for t in textures_list):
                    textures_list.append({
                        "id": res_id,
                        "name": tex_name,
                        "thumbnail": thumbnail,
                        "slot": sr.get("slot", 0),
                        "stage": sr.get("stage", "")
                    })
        
        prepared["textures"] = textures_list
        
        # 提取 Render Target 信息（从 renderTargets 字段或推断）
        rt_data = evt.get("renderTargets", [])
        if isinstance(rt_data, list):
            for rt in rt_data:
                rt_id = str(rt.get("id", rt.get("resourceId", "")))
                if rt_id:
                    tex_info = texture_lookup.get(rt_id, {})
                    rt_name = tex_info.get("name", f"RT {rt_id}")
                    thumbnail = tex_info.get("thumbnail", "")
                    
                    render_targets_list.append({
                        "id": rt_id,
                        "name": rt_name,
                        "thumbnail": thumbnail,
                        "slot": rt.get("slot", len(render_targets_list))
                    })
        
        prepared["renderTargets"] = render_targets_list
        
        # 添加 viewport 信息（如果存在）
        viewport = pipeline_state.get("viewport")
        if viewport:
            prepared["viewport"] = viewport
        
        prepared_events.append(prepared)
    
    return prepared_events


def build_events_tree(events: List[Dict]) -> List[Dict]:
    """
    将扁平事件列表转换为树结构（按 Pass 分组）
    
    Args:
        events: 扁平事件列表
        
    Returns:
        树结构事件列表
    """
    # 简单分组：按 pass 或 marker 名称
    tree = []
    current_pass = None
    current_children = []
    
    for evt in events:
        markers = evt.get("markers", [])
        pass_name = markers[0] if markers else None
        
        if pass_name and pass_name != current_pass:
            # 保存上一个 Pass
            if current_pass and current_children:
                tree.append({
                    "name": current_pass,
                    "type": "pass",
                    "children": current_children,
                    "count": len(current_children)
                })
            current_pass = pass_name
            current_children = []
        
        current_children.append({
            "eid": evt.get("eventId") or evt.get("eid"),
            "name": evt.get("name", "Unknown"),
            "type": evt.get("type", "unknown")
        })
    
    # 保存最后一个 Pass
    if current_pass and current_children:
        tree.append({
            "name": current_pass,
            "type": "pass",
            "children": current_children,
            "count": len(current_children)
        })
    elif current_children:
        # 无 Pass 分组，直接添加事件
        tree = current_children
    
    return tree
