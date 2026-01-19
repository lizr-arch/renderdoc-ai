#!/usr/bin/env python3
"""
解析 RenderDoc 导出的 XML 捕获文件，提取事件和纹理数据

用法:
    py -3 parse_rdc_xml.py <capture.xml> [output.json]
"""

import xml.etree.ElementTree as ET
import json
import re
import sys
from pathlib import Path
from collections import defaultdict


def parse_chunk_params(chunk_elem):
    """解析 chunk 元素中的参数"""
    params = []
    for child in chunk_elem:
        param = parse_element(child)
        if param:
            params.append(param)
    return params


def parse_element(elem):
    """递归解析 XML 元素为字典"""
    result = {
        "name": elem.get("name", elem.tag),
        "type": elem.get("typename", elem.tag),
    }
    
    # 获取值
    if elem.text and elem.text.strip():
        result["value"] = elem.text.strip()
    elif elem.get("string"):
        result["value"] = elem.get("string")
    
    # 检查是否重要
    if elem.get("important") == "true":
        result["important"] = True
    
    # 处理子元素
    if len(elem) > 0:
        if elem.tag == "array":
            result["elements"] = [parse_element(child) for child in elem]
        elif elem.tag == "struct":
            result["fields"] = {child.get("name", child.tag): parse_element(child) for child in elem}
        else:
            children = [parse_element(child) for child in elem]
            if children:
                result["children"] = children
    
    return result


def format_param_value(param):
    """格式化参数值为可读字符串"""
    if "value" in param:
        return param["value"]
    elif "elements" in param:
        values = [format_param_value(e) for e in param["elements"][:5]]
        if len(param["elements"]) > 5:
            values.append("...")
        return f"[{', '.join(values)}]"
    elif "fields" in param:
        return "{...}"
    return ""


def parse_create_image(params):
    """解析 vkCreateImage 参数，提取纹理信息"""
    texture_info = {}
    
    for p in params:
        name = p.get("name", "")
        
        # 获取资源 ID
        if name == "Image":
            texture_info["resourceId"] = p.get("value", "0")
            
        # 获取 CreateInfo
        elif name == "CreateInfo" and "fields" in p:
            fields = p["fields"]
            
            # 格式
            if "format" in fields:
                fmt = fields["format"]
                texture_info["format"] = fmt.get("value", "Unknown")
                texture_info["formatName"] = fmt.get("value", "").replace("VK_FORMAT_", "")
                
            # 类型
            if "imageType" in fields:
                texture_info["imageType"] = fields["imageType"].get("value", "VK_IMAGE_TYPE_2D")
                
            # 尺寸
            if "extent" in fields and "fields" in fields["extent"]:
                extent = fields["extent"]["fields"]
                texture_info["width"] = int(extent.get("width", {}).get("value", 0))
                texture_info["height"] = int(extent.get("height", {}).get("value", 0))
                texture_info["depth"] = int(extent.get("depth", {}).get("value", 1))
                
            # Mip levels
            if "mipLevels" in fields:
                texture_info["mipLevels"] = int(fields["mipLevels"].get("value", 1))
                
            # Array layers
            if "arrayLayers" in fields:
                texture_info["arrayLayers"] = int(fields["arrayLayers"].get("value", 1))
                
            # Samples
            if "samples" in fields:
                texture_info["samples"] = fields["samples"].get("value", "VK_SAMPLE_COUNT_1_BIT")
                
            # Usage
            if "usage" in fields:
                texture_info["usage"] = fields["usage"].get("value", "")
                texture_info["usageFlags"] = fields["usage"].get("value", "0")
                
        # 内存需求
        elif name == "memoryRequirements" and "fields" in p:
            mem_fields = p["fields"]
            if "size" in mem_fields:
                texture_info["memorySize"] = int(mem_fields["size"].get("value", 0))
    
    # 计算估算的 VRAM 大小（如果没有 memorySize）
    if "width" in texture_info and "height" in texture_info and "memorySize" not in texture_info:
        # 简单估算：假设每像素 4 字节
        bpp = get_format_bpp(texture_info.get("format", ""))
        texture_info["memorySize"] = texture_info["width"] * texture_info["height"] * texture_info.get("depth", 1) * bpp // 8
    
    # 生成友好名称
    if texture_info.get("resourceId"):
        texture_info["name"] = f"Image_{texture_info['resourceId']}"
        
    return texture_info if texture_info.get("resourceId") else None


def parse_create_buffer(params):
    """解析 vkCreateBuffer 参数，提取缓冲区信息"""
    buffer_info = {}
    
    for p in params:
        name = p.get("name", "")
        
        # 获取资源 ID
        if name == "Buffer":
            buffer_info["resourceId"] = p.get("value", "0")
            
        # 获取 CreateInfo
        elif name == "CreateInfo" and "fields" in p:
            fields = p["fields"]
            
            # 大小
            if "size" in fields:
                buffer_info["size"] = int(fields["size"].get("value", 0))
                
            # Usage
            if "usage" in fields:
                buffer_info["usage"] = fields["usage"].get("value", "")
    
    # 生成友好名称
    if buffer_info.get("resourceId"):
        buffer_info["name"] = f"Buffer_{buffer_info['resourceId']}"
        
    return buffer_info if buffer_info.get("resourceId") else None


def get_format_bpp(format_str):
    """根据 Vulkan 格式返回每像素位数"""
    format_bpp = {
        "VK_FORMAT_R8_UNORM": 8,
        "VK_FORMAT_R8G8_UNORM": 16,
        "VK_FORMAT_R8G8B8_UNORM": 24,
        "VK_FORMAT_R8G8B8A8_UNORM": 32,
        "VK_FORMAT_R8G8B8A8_SRGB": 32,
        "VK_FORMAT_B8G8R8A8_UNORM": 32,
        "VK_FORMAT_B8G8R8A8_SRGB": 32,
        "VK_FORMAT_R16_SFLOAT": 16,
        "VK_FORMAT_R16G16_SFLOAT": 32,
        "VK_FORMAT_R16G16B16A16_SFLOAT": 64,
        "VK_FORMAT_R32_SFLOAT": 32,
        "VK_FORMAT_R32G32_SFLOAT": 64,
        "VK_FORMAT_R32G32B32A32_SFLOAT": 128,
        "VK_FORMAT_D16_UNORM": 16,
        "VK_FORMAT_D24_UNORM_S8_UINT": 32,
        "VK_FORMAT_D32_SFLOAT": 32,
        "VK_FORMAT_D32_SFLOAT_S8_UINT": 40,
        # 压缩格式
        "VK_FORMAT_BC1_RGB_UNORM_BLOCK": 4,
        "VK_FORMAT_BC1_RGBA_UNORM_BLOCK": 4,
        "VK_FORMAT_BC2_UNORM_BLOCK": 8,
        "VK_FORMAT_BC3_UNORM_BLOCK": 8,
        "VK_FORMAT_BC4_UNORM_BLOCK": 4,
        "VK_FORMAT_BC5_UNORM_BLOCK": 8,
        "VK_FORMAT_BC6H_UFLOAT_BLOCK": 8,
        "VK_FORMAT_BC7_UNORM_BLOCK": 8,
        "VK_FORMAT_ASTC_4x4_UNORM_BLOCK": 8,
        "VK_FORMAT_ASTC_4x4_SRGB_BLOCK": 8,
        "VK_FORMAT_ETC2_R8G8B8_UNORM_BLOCK": 4,
        "VK_FORMAT_ETC2_R8G8B8A8_UNORM_BLOCK": 8,
    }
    return format_bpp.get(format_str, 32)  # 默认假设 32 位


def parse_rdc_xml(xml_path):
    """解析 RDC XML 文件"""
    print(f"Parsing {xml_path}...")
    
    tree = ET.parse(xml_path)
    root = tree.getroot()
    
    # 解析 header
    header = root.find("header")
    driver_elem = header.find("driver")
    api_type = driver_elem.text if driver_elem is not None else "Unknown"
    
    print(f"  API: {api_type}")
    
    # 解析 chunks（API 调用）
    chunks = root.find("chunks")
    events = []
    textures = {}
    buffers = {}
    render_passes = []
    
    current_render_pass = None
    current_pass_events = []
    event_id = 0
    
    draw_call_names = [
        "vkCmdDraw", "vkCmdDrawIndexed", "vkCmdDrawIndirect", "vkCmdDrawIndexedIndirect",
        "vkCmdDrawMeshTasksEXT", "vkCmdDispatch", "vkCmdDispatchIndirect",
        "vkCmdClearColorImage", "vkCmdClearDepthStencilImage", "vkCmdBlitImage",
        "vkCmdCopyBuffer", "vkCmdCopyImage", "vkCmdCopyBufferToImage"
    ]
    
    marker_names = ["vkCmdBeginDebugUtilsLabelEXT", "vkCmdEndDebugUtilsLabelEXT", 
                    "vkCmdInsertDebugUtilsLabelEXT"]
    
    render_pass_begin = ["vkCmdBeginRenderPass", "vkCmdBeginRendering"]
    render_pass_end = ["vkCmdEndRenderPass", "vkCmdEndRendering"]
    
    binding_calls = [
        "vkCmdBindPipeline", "vkCmdBindDescriptorSets", "vkCmdBindVertexBuffers",
        "vkCmdBindIndexBuffer", "vkCmdPushConstants", "vkCmdSetViewport", "vkCmdSetScissor"
    ]
    
    # 跟踪当前绑定状态（用于关联到 Draw 调用）
    current_bindings = []
    
    for chunk in chunks.findall("chunk"):
        chunk_name = chunk.get("name", "")
        chunk_id = chunk.get("id", "")
        thread_id = chunk.get("threadID", "")
        timestamp = chunk.get("timestamp", "")
        duration = chunk.get("duration", "0")
        
        # 解析参数
        params = parse_chunk_params(chunk)
        
        # 构建事件对象
        event = {
            "eventId": event_id,
            "chunkId": int(chunk_id) if chunk_id else 0,
            "name": chunk_name,
            "timestamp": int(timestamp) if timestamp else 0,
            "duration": float(duration) if duration else 0,
            "params": params,
        }
        
        # 检测事件类型
        if chunk_name in draw_call_names:
            event["type"] = "draw" if "Draw" in chunk_name else "dispatch" if "Dispatch" in chunk_name else "copy"
            event["flags"] = []
            
            if "Indexed" in chunk_name:
                event["flags"].append("indexed")
            if "Indirect" in chunk_name:
                event["flags"].append("indirect")
            if "Instanced" in chunk_name:
                event["flags"].append("instanced")
            
            # 关联之前的绑定调用
            event["relatedCalls"] = current_bindings.copy()
            current_bindings = []  # 清空，为下一个 draw 准备
            
            # 提取绘制参数
            for p in params:
                if p["name"] == "vertexCount":
                    event["vertexCount"] = int(p.get("value", 0))
                elif p["name"] == "indexCount":
                    event["indexCount"] = int(p.get("value", 0))
                elif p["name"] == "instanceCount":
                    event["instanceCount"] = int(p.get("value", 1))
                elif p["name"] == "firstVertex":
                    event["firstVertex"] = int(p.get("value", 0))
                elif p["name"] == "firstIndex":
                    event["firstIndex"] = int(p.get("value", 0))
            
            events.append(event)
            current_pass_events.append(event)
            event_id += 1
            
        elif chunk_name in binding_calls:
            # 记录绑定调用，等待关联到下一个 draw
            binding_str = format_binding_call(chunk_name, params)
            current_bindings.append(binding_str)
            
        elif chunk_name in render_pass_begin:
            if current_render_pass:
                # 结束上一个 render pass
                current_render_pass["events"] = current_pass_events
                render_passes.append(current_render_pass)
            
            current_render_pass = {
                "name": f"RenderPass_{len(render_passes)}",
                "startEvent": event_id,
                "events": [],
            }
            current_pass_events = []
            
            # 提取 render pass 信息
            for p in params:
                if p["name"] == "pRenderPassBegin" and "fields" in p:
                    rp_info = p["fields"]
                    if "renderArea" in rp_info and "fields" in rp_info["renderArea"]:
                        extent = rp_info["renderArea"]["fields"].get("extent", {})
                        if "fields" in extent:
                            current_render_pass["width"] = extent["fields"].get("width", {}).get("value", 0)
                            current_render_pass["height"] = extent["fields"].get("height", {}).get("value", 0)
                            
        elif chunk_name in render_pass_end:
            if current_render_pass:
                current_render_pass["endEvent"] = event_id
                current_render_pass["events"] = current_pass_events
                render_passes.append(current_render_pass)
                current_render_pass = None
                current_pass_events = []
                
        elif chunk_name in marker_names:
            event["type"] = "marker"
            # 提取 marker 名称
            for p in params:
                if p["name"] == "pLabelInfo" and "fields" in p:
                    label_info = p["fields"]
                    if "pLabelName" in label_info:
                        event["markerName"] = label_info["pLabelName"].get("value", "")
            events.append(event)
            event_id += 1
            
        elif chunk_name == "vkCreateImage":
            # 提取纹理/图像资源
            texture_info = parse_create_image(params)
            if texture_info:
                textures[texture_info["resourceId"]] = texture_info
                
        elif chunk_name == "vkCreateBuffer":
            # 提取缓冲区资源
            buffer_info = parse_create_buffer(params)
            if buffer_info:
                buffers[buffer_info["resourceId"]] = buffer_info
    
    # 处理最后一个 render pass
    if current_render_pass:
        current_render_pass["events"] = current_pass_events
        render_passes.append(current_render_pass)
    
    # 转换 textures 字典为列表，便于后续处理
    textures_list = list(textures.values())
    buffers_list = list(buffers.values())
    
    # 计算纹理统计
    total_texture_memory = sum(t.get("memorySize", 0) for t in textures_list)
    
    print(f"  Total events: {len(events)}")
    print(f"  Draw calls: {sum(1 for e in events if e.get('type') == 'draw')}")
    print(f"  Render passes: {len(render_passes)}")
    print(f"  Textures/Images: {len(textures_list)}")
    print(f"  Buffers: {len(buffers_list)}")
    print(f"  Total texture memory: {total_texture_memory / (1024*1024):.2f} MB")
    
    return {
        "apiType": api_type,
        "events": events,
        "renderPasses": render_passes,
        "textures": textures_list,
        "buffers": buffers_list,
        "header": {
            "driver": api_type,
        },
        "statistics": {
            "totalEvents": len(events),
            "totalDrawCalls": sum(1 for e in events if e.get('type') == 'draw'),
            "totalDispatches": sum(1 for e in events if e.get('type') == 'dispatch'),
            "totalCopies": sum(1 for e in events if e.get('type') == 'copy'),
            "totalTextures": len(textures_list),
            "totalBuffers": len(buffers_list),
            "totalTextureMemory": total_texture_memory,
        }
    }


def format_binding_call(name, params):
    """格式化绑定调用为可读字符串"""
    param_strs = []
    for p in params:
        if p.get("name") and p.get("name") not in ["commandBuffer"]:
            value = format_param_value(p)
            if value:
                param_strs.append(f"{p['name']}: {value}")
    
    if param_strs:
        return f"{name}({', '.join(param_strs)})"
    return name


def main():
    if len(sys.argv) < 2:
        print("Usage: parse_rdc_xml.py <capture.xml> [output.json]")
        sys.exit(1)
    
    xml_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else xml_path.with_suffix('.json')
    
    if not xml_path.exists():
        print(f"Error: File not found: {xml_path}")
        sys.exit(1)
    
    data = parse_rdc_xml(xml_path)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    main()
