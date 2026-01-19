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
    
    # Vulkan draw/dispatch/copy calls
    vk_draw_calls = [
        "vkCmdDraw", "vkCmdDrawIndexed", "vkCmdDrawIndirect", "vkCmdDrawIndexedIndirect",
        "vkCmdDrawMeshTasksEXT", "vkCmdDispatch", "vkCmdDispatchIndirect",
        "vkCmdClearColorImage", "vkCmdClearDepthStencilImage", "vkCmdBlitImage",
        "vkCmdCopyBuffer", "vkCmdCopyImage", "vkCmdCopyBufferToImage"
    ]
    
    # D3D11 draw/dispatch/copy calls
    d3d11_draw_calls = [
        "ID3D11DeviceContext::Draw",
        "ID3D11DeviceContext::DrawIndexed",
        "ID3D11DeviceContext::DrawInstanced",
        "ID3D11DeviceContext::DrawIndexedInstanced",
        "ID3D11DeviceContext::DrawIndexedInstancedIndirect",
        "ID3D11DeviceContext::DrawInstancedIndirect",
        "ID3D11DeviceContext::DrawAuto",
        "ID3D11DeviceContext::Dispatch",
        "ID3D11DeviceContext::DispatchIndirect",
        "ID3D11DeviceContext::CopyResource",
        "ID3D11DeviceContext::CopySubresourceRegion",
        "ID3D11DeviceContext::ClearRenderTargetView",
        "ID3D11DeviceContext::ClearDepthStencilView",
        "ID3D11DeviceContext::ResolveSubresource",
    ]
    
    # D3D12 draw/dispatch/copy calls
    d3d12_draw_calls = [
        "ID3D12GraphicsCommandList::DrawInstanced",
        "ID3D12GraphicsCommandList::DrawIndexedInstanced",
        "ID3D12GraphicsCommandList::Dispatch",
        "ID3D12GraphicsCommandList::CopyResource",
        "ID3D12GraphicsCommandList::CopyBufferRegion",
        "ID3D12GraphicsCommandList::CopyTextureRegion",
        "ID3D12GraphicsCommandList::ClearRenderTargetView",
        "ID3D12GraphicsCommandList::ClearDepthStencilView",
    ]
    
    # Combined draw call names
    draw_call_names = vk_draw_calls + d3d11_draw_calls + d3d12_draw_calls
    
    # Vulkan markers
    vk_marker_names = ["vkCmdBeginDebugUtilsLabelEXT", "vkCmdEndDebugUtilsLabelEXT", 
                       "vkCmdInsertDebugUtilsLabelEXT"]
    
    # D3D11/D3D12 markers (PIX events)
    d3d_marker_names = [
        "ID3D11DeviceContext::BeginEventInt",
        "ID3D11DeviceContext::EndEvent",
        "ID3D12GraphicsCommandList::BeginEvent",
        "ID3D12GraphicsCommandList::EndEvent",
    ]
    
    marker_names = vk_marker_names + d3d_marker_names
    
    # Render pass begin/end
    render_pass_begin = ["vkCmdBeginRenderPass", "vkCmdBeginRendering"]
    render_pass_end = ["vkCmdEndRenderPass", "vkCmdEndRendering"]
    
    # Vulkan binding calls
    vk_binding_calls = [
        "vkCmdBindPipeline", "vkCmdBindDescriptorSets", "vkCmdBindVertexBuffers",
        "vkCmdBindIndexBuffer", "vkCmdPushConstants", "vkCmdSetViewport", "vkCmdSetScissor"
    ]
    
    # D3D11 binding calls
    d3d11_binding_calls = [
        # Input Assembler
        "ID3D11DeviceContext::IASetInputLayout",
        "ID3D11DeviceContext::IASetVertexBuffers",
        "ID3D11DeviceContext::IASetIndexBuffer",
        "ID3D11DeviceContext::IASetPrimitiveTopology",
        # Shaders
        "ID3D11DeviceContext::VSSetShader",
        "ID3D11DeviceContext::PSSetShader",
        "ID3D11DeviceContext::GSSetShader",
        "ID3D11DeviceContext::HSSetShader",
        "ID3D11DeviceContext::DSSetShader",
        "ID3D11DeviceContext::CSSetShader",
        # Constant Buffers
        "ID3D11DeviceContext::VSSetConstantBuffers",
        "ID3D11DeviceContext::PSSetConstantBuffers",
        "ID3D11DeviceContext::GSSetConstantBuffers",
        "ID3D11DeviceContext::HSSetConstantBuffers",
        "ID3D11DeviceContext::DSSetConstantBuffers",
        "ID3D11DeviceContext::CSSetConstantBuffers",
        # Shader Resources
        "ID3D11DeviceContext::VSSetShaderResources",
        "ID3D11DeviceContext::PSSetShaderResources",
        "ID3D11DeviceContext::GSSetShaderResources",
        "ID3D11DeviceContext::HSSetShaderResources",
        "ID3D11DeviceContext::DSSetShaderResources",
        "ID3D11DeviceContext::CSSetShaderResources",
        # Samplers
        "ID3D11DeviceContext::VSSetSamplers",
        "ID3D11DeviceContext::PSSetSamplers",
        "ID3D11DeviceContext::GSSetSamplers",
        "ID3D11DeviceContext::CSSetSamplers",
        # Rasterizer
        "ID3D11DeviceContext::RSSetViewports",
        "ID3D11DeviceContext::RSSetScissorRects",
        "ID3D11DeviceContext::RSSetState",
        # Output Merger
        "ID3D11DeviceContext::OMSetRenderTargets",
        "ID3D11DeviceContext::OMSetRenderTargetsAndUnorderedAccessViews",
        "ID3D11DeviceContext::OMSetBlendState",
        "ID3D11DeviceContext::OMSetDepthStencilState",
    ]
    
    # D3D12 binding calls
    d3d12_binding_calls = [
        "ID3D12GraphicsCommandList::SetGraphicsRootSignature",
        "ID3D12GraphicsCommandList::SetPipelineState",
        "ID3D12GraphicsCommandList::IASetVertexBuffers",
        "ID3D12GraphicsCommandList::IASetIndexBuffer",
        "ID3D12GraphicsCommandList::IASetPrimitiveTopology",
        "ID3D12GraphicsCommandList::RSSetViewports",
        "ID3D12GraphicsCommandList::RSSetScissorRects",
        "ID3D12GraphicsCommandList::OMSetRenderTargets",
        "ID3D12GraphicsCommandList::OMSetBlendFactor",
        "ID3D12GraphicsCommandList::OMSetStencilRef",
        "ID3D12GraphicsCommandList::SetGraphicsRootConstantBufferView",
        "ID3D12GraphicsCommandList::SetGraphicsRootDescriptorTable",
        "ID3D12GraphicsCommandList::SetGraphicsRoot32BitConstants",
    ]
    
    binding_calls = vk_binding_calls + d3d11_binding_calls + d3d12_binding_calls
    
    # 跟踪当前绑定状态（用于关联到 Draw 调用）
    current_bindings = []           # 字符串格式的调用（向后兼容）
    current_binding_records = []    # 结构化调用记录（用于 meshInfo/pipelineState 解析）
    
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
            
            # 解析 Mesh 信息
            event["meshInfo"] = parse_mesh_info(current_binding_records)
            
            # 解析 Pipeline State
            event["pipelineState"] = parse_pipeline_state_from_related_calls(current_bindings)
            
            current_bindings = []  # 清空，为下一个 draw 准备
            current_binding_records = []  # 清空结构化记录
            
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
            # 同时保存结构化记录用于 meshInfo/pipelineState 解析
            current_binding_records.append({"name": chunk_name, "params": params})
            
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


def parse_mesh_info(binding_records):
    """
    从绑定记录中解析 Mesh 信息
    
    Args:
        binding_records: 结构化的绑定调用列表 [{"name": "...", "params": [...]}]
    
    Returns:
        meshInfo 对象包含:
        - vertexBuffers: [{buffer, offset, stride}]
        - indexBuffer: {buffer, offset, format}
        - inputLayout: 输入布局 ID
        - primitiveTopology: 图元拓扑
    """
    mesh_info = {
        "vertexBuffers": [],
        "indexBuffer": None,
        "inputLayout": None,
        "primitiveTopology": None
    }
    
    for record in binding_records:
        name = record.get("name", "")
        params = record.get("params", [])
        
        # D3D11: IASetVertexBuffers
        if "IASetVertexBuffers" in name:
            vb_info = parse_d3d11_vertex_buffers(params)
            if vb_info:
                mesh_info["vertexBuffers"].extend(vb_info)
                
        # D3D11: IASetIndexBuffer
        elif "IASetIndexBuffer" in name:
            ib_info = parse_d3d11_index_buffer(params)
            if ib_info:
                mesh_info["indexBuffer"] = ib_info
                
        # D3D11: IASetInputLayout
        elif "IASetInputLayout" in name:
            for p in params:
                if p.get("name") == "pInputLayout":
                    mesh_info["inputLayout"] = p.get("value", "")
                    
        # D3D11: IASetPrimitiveTopology
        elif "IASetPrimitiveTopology" in name:
            for p in params:
                if p.get("name") == "Topology":
                    mesh_info["primitiveTopology"] = p.get("value", "")
                    
        # Vulkan: vkCmdBindVertexBuffers
        elif "vkCmdBindVertexBuffers" in name:
            vb_info = parse_vulkan_vertex_buffers(params)
            if vb_info:
                mesh_info["vertexBuffers"].extend(vb_info)
                
        # Vulkan: vkCmdBindIndexBuffer
        elif "vkCmdBindIndexBuffer" in name:
            ib_info = parse_vulkan_index_buffer(params)
            if ib_info:
                mesh_info["indexBuffer"] = ib_info
    
    return mesh_info


def parse_d3d11_vertex_buffers(params):
    """解析 D3D11 IASetVertexBuffers 参数"""
    buffers = []
    strides = []
    offsets = []
    start_slot = 0
    
    for p in params:
        name = p.get("name", "")
        if name == "StartSlot":
            start_slot = int(p.get("value", 0))
        elif name == "ppVertexBuffers" and "elements" in p:
            for elem in p["elements"]:
                buffers.append(elem.get("value", ""))
        elif name == "pStrides" and "elements" in p:
            for elem in p["elements"]:
                strides.append(int(elem.get("value", 0)))
        elif name == "pOffsets" and "elements" in p:
            for elem in p["elements"]:
                offsets.append(int(elem.get("value", 0)))
    
    result = []
    for i, buf in enumerate(buffers):
        result.append({
            "slot": start_slot + i,
            "buffer": buf,
            "stride": strides[i] if i < len(strides) else 0,
            "offset": offsets[i] if i < len(offsets) else 0
        })
    return result


def parse_d3d11_index_buffer(params):
    """解析 D3D11 IASetIndexBuffer 参数"""
    ib_info = {}
    for p in params:
        name = p.get("name", "")
        if name == "pIndexBuffer":
            ib_info["buffer"] = p.get("value", "")
        elif name == "Format":
            ib_info["format"] = p.get("value", "")
        elif name == "Offset":
            ib_info["offset"] = int(p.get("value", 0))
    return ib_info if ib_info.get("buffer") else None


def parse_vulkan_vertex_buffers(params):
    """解析 Vulkan vkCmdBindVertexBuffers 参数"""
    buffers = []
    offsets = []
    first_binding = 0
    
    for p in params:
        name = p.get("name", "")
        if name == "firstBinding":
            first_binding = int(p.get("value", 0))
        elif name == "pBuffers" and "elements" in p:
            for elem in p["elements"]:
                buffers.append(elem.get("value", ""))
        elif name == "pOffsets" and "elements" in p:
            for elem in p["elements"]:
                offsets.append(int(elem.get("value", 0)))
    
    result = []
    for i, buf in enumerate(buffers):
        result.append({
            "slot": first_binding + i,
            "buffer": buf,
            "offset": offsets[i] if i < len(offsets) else 0
        })
    return result


def parse_vulkan_index_buffer(params):
    """解析 Vulkan vkCmdBindIndexBuffer 参数"""
    ib_info = {}
    for p in params:
        name = p.get("name", "")
        if name == "buffer":
            ib_info["buffer"] = p.get("value", "")
        elif name == "offset":
            ib_info["offset"] = int(p.get("value", 0))
        elif name == "indexType":
            ib_info["format"] = p.get("value", "")
    return ib_info if ib_info.get("buffer") else None


def parse_pipeline_state_from_related_calls(related_calls):
    """
    从 relatedCalls 字符串列表中解析 Pipeline State 数据
    
    返回:
        dict: 包含 viewport, blendState, depthState, shaders 等信息
    """
    pipeline_state = {
        "viewport": None,
        "scissor": None,
        "blendState": None,
        "depthState": None,
        "rasterizerState": None,
        "shaders": {
            "vs": None,
            "ps": None,
            "gs": None,
            "hs": None,
            "ds": None,
            "cs": None,
        },
        "primitiveTopology": None,
        "inputLayout": None,
    }
    
    for call in related_calls:
        if not call:
            continue
            
        # 解析 Viewport (D3D11: RSSetViewports, Vulkan: vkCmdSetViewport)
        if "RSSetViewports" in call or "vkCmdSetViewport" in call:
            viewport = parse_viewport_from_call(call)
            if viewport:
                pipeline_state["viewport"] = viewport
                
        # 解析 Scissor
        elif "RSSetScissorRects" in call or "vkCmdSetScissor" in call:
            scissor = parse_scissor_from_call(call)
            if scissor:
                pipeline_state["scissor"] = scissor
                
        # 解析 Blend State
        elif "OMSetBlendState" in call or "OMSetBlendFactor" in call:
            blend = parse_blend_state_from_call(call)
            if blend:
                pipeline_state["blendState"] = blend
                
        # 解析 Depth Stencil State
        elif "OMSetDepthStencilState" in call or "OMSetStencilRef" in call:
            depth = parse_depth_state_from_call(call)
            if depth:
                pipeline_state["depthState"] = depth
                
        # 解析 Rasterizer State
        elif "RSSetState" in call:
            pipeline_state["rasterizerState"] = {"raw": call}
            
        # 解析 Shaders
        elif "VSSetShader" in call:
            pipeline_state["shaders"]["vs"] = parse_shader_from_call(call, "VS")
        elif "PSSetShader" in call:
            pipeline_state["shaders"]["ps"] = parse_shader_from_call(call, "PS")
        elif "GSSetShader" in call:
            pipeline_state["shaders"]["gs"] = parse_shader_from_call(call, "GS")
        elif "HSSetShader" in call:
            pipeline_state["shaders"]["hs"] = parse_shader_from_call(call, "HS")
        elif "DSSetShader" in call:
            pipeline_state["shaders"]["ds"] = parse_shader_from_call(call, "DS")
        elif "CSSetShader" in call:
            pipeline_state["shaders"]["cs"] = parse_shader_from_call(call, "CS")
        elif "vkCmdBindPipeline" in call:
            # Vulkan pipeline 包含所有 shader
            pipeline_state["shaders"]["pipeline"] = parse_shader_from_call(call, "Pipeline")
            
        # 解析 Primitive Topology
        elif "IASetPrimitiveTopology" in call:
            topology = parse_topology_from_call(call)
            if topology:
                pipeline_state["primitiveTopology"] = topology
                
        # 解析 Input Layout
        elif "IASetInputLayout" in call:
            pipeline_state["inputLayout"] = parse_input_layout_from_call(call)
    
    return pipeline_state


def parse_viewport_from_call(call):
    """从 RSSetViewports 调用字符串解析 viewport 数据"""
    # 示例: ID3D11DeviceContext::RSSetViewports(NumViewports: 1, pViewports: [...])
    viewport = {
        "x": 0.0,
        "y": 0.0,
        "width": 0.0,
        "height": 0.0,
        "minDepth": 0.0,
        "maxDepth": 1.0,
    }
    
    # 尝试从括号内容中解析数值
    # 简化解析：提取常见模式
    import re
    
    # 匹配 NumViewports
    num_match = re.search(r'NumViewports:\s*(\d+)', call)
    if num_match:
        viewport["count"] = int(num_match.group(1))
    
    # 尝试匹配 Width/Height 模式 (有些格式会直接列出)
    width_match = re.search(r'Width:\s*([\d.]+)', call, re.IGNORECASE)
    height_match = re.search(r'Height:\s*([\d.]+)', call, re.IGNORECASE)
    
    if width_match:
        viewport["width"] = float(width_match.group(1))
    if height_match:
        viewport["height"] = float(height_match.group(1))
    
    # 保留原始调用以供参考
    viewport["raw"] = call
    
    return viewport


def parse_scissor_from_call(call):
    """从 RSSetScissorRects 调用字符串解析 scissor 数据"""
    scissor = {
        "left": 0,
        "top": 0,
        "right": 0,
        "bottom": 0,
    }
    
    import re
    
    # 匹配 NumRects
    num_match = re.search(r'NumRects:\s*(\d+)', call)
    if num_match:
        scissor["count"] = int(num_match.group(1))
    
    scissor["raw"] = call
    return scissor


def parse_blend_state_from_call(call):
    """从 OMSetBlendState 调用字符串解析 blend state 数据"""
    blend = {
        "enabled": True,  # 假设如果调用存在则启用
        # 使用 HTML 模板期望的字段名
        "srcColor": "Unknown",
        "dstColor": "Unknown",
    }
    
    import re
    
    # 提取 pBlendState 资源 ID
    state_match = re.search(r'pBlendState:\s*(\d+|NULL)', call)
    if state_match:
        value = state_match.group(1)
        blend["stateId"] = value
        blend["enabled"] = value != "NULL" and value != "0"
    
    # 提取 BlendFactor
    factor_match = re.search(r'BlendFactor:\s*\[([\d.,\s]+)\]', call)
    if factor_match:
        factors = factor_match.group(1).split(',')
        blend["blendFactor"] = [float(f.strip()) for f in factors[:4]]
    
    # 提取 SampleMask
    mask_match = re.search(r'SampleMask:\s*([\da-fA-Fx]+)', call)
    if mask_match:
        blend["sampleMask"] = mask_match.group(1)
    
    blend["raw"] = call
    return blend


def parse_depth_state_from_call(call):
    """从 OMSetDepthStencilState 调用字符串解析 depth stencil state 数据"""
    depth = {
        # 使用 HTML 模板期望的字段名
        "testEnabled": True,
        "writeEnabled": True,
        "compareFunc": "Unknown",
        "stencilEnabled": False,
        "stencilRef": 0,
    }
    
    import re
    
    # 提取 pDepthStencilState 资源 ID
    state_match = re.search(r'pDepthStencilState:\s*(\d+|NULL)', call)
    if state_match:
        value = state_match.group(1)
        depth["stateId"] = value
        depth["testEnabled"] = value != "NULL" and value != "0"
        depth["writeEnabled"] = depth["testEnabled"]  # 假设与 test 一致
    
    # 提取 StencilRef
    ref_match = re.search(r'StencilRef:\s*(\d+)', call)
    if ref_match:
        depth["stencilRef"] = int(ref_match.group(1))
    
    depth["raw"] = call
    return depth


def parse_shader_from_call(call, shader_type):
    """从 SetShader 调用字符串解析 shader 信息"""
    shader = {
        "type": shader_type,
        "id": None,
        "valid": False,
    }
    
    import re
    
    # D3D11: pShader: 12345 或 pShader: NULL
    # Vulkan: pipeline: 12345
    shader_match = re.search(r'(?:pShader|pipeline|pComputeShader):\s*(\d+|NULL)', call)
    if shader_match:
        value = shader_match.group(1)
        shader["id"] = value
        shader["valid"] = value != "NULL" and value != "0"
    
    shader["raw"] = call
    return shader


def parse_topology_from_call(call):
    """从 IASetPrimitiveTopology 调用解析图元拓扑"""
    import re
    
    # 匹配 Topology: D3D11_PRIMITIVE_TOPOLOGY_TRIANGLELIST
    topo_match = re.search(r'Topology:\s*(\S+)', call)
    if topo_match:
        topo = topo_match.group(1)
        # 简化名称
        topo = topo.replace("D3D11_PRIMITIVE_TOPOLOGY_", "")
        topo = topo.replace("D3D_PRIMITIVE_TOPOLOGY_", "")
        return topo
    
    return None


def parse_input_layout_from_call(call):
    """从 IASetInputLayout 调用解析 input layout"""
    import re
    
    layout = {
        "id": None,
        "valid": False,
    }
    
    # 匹配 pInputLayout: 12345
    layout_match = re.search(r'pInputLayout:\s*(\d+|NULL)', call)
    if layout_match:
        value = layout_match.group(1)
        layout["id"] = value
        layout["valid"] = value != "NULL" and value != "0"
    
    layout["raw"] = call
    return layout


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
