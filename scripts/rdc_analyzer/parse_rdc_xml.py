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


# ============================================================================
# Vulkan DescriptorSet Content Mapping (vkUpdateDescriptorSets)
# ============================================================================

def parse_vk_update_descriptor_sets_chunk(chunk):
    """解析单个 vkUpdateDescriptorSets chunk，提取描述符集内容
    
    Returns:
        list: [{setId, bindings: [{binding, type, resource}]}]
    """
    results = []
    
    # 找 pDescriptorWrites 数组
    for child in chunk:
        if child.tag == "array" and child.get("name") == "pDescriptorWrites":
            for write_struct in child.findall("struct"):
                write_info = {
                    "setId": None,
                    "binding": 0,
                    "descriptorType": "",
                    "resources": []  # buffers, images, samplers
                }
                
                for elem in write_struct:
                    name = elem.get("name", "")
                    
                    if name == "dstSet" and elem.tag == "ResourceId":
                        write_info["setId"] = elem.text.strip() if elem.text else None
                        
                    elif name == "dstBinding":
                        write_info["binding"] = int(elem.text.strip()) if elem.text else 0
                        
                    elif name == "descriptorType" and elem.tag == "enum":
                        # 使用 string 属性获取人类可读的类型
                        write_info["descriptorType"] = elem.get("string", elem.text.strip() if elem.text else "")
                        
                    elif name == "pBufferInfo" and elem.tag == "array":
                        # 解析 buffer 绑定
                        for buf_struct in elem.findall("struct"):
                            buf_info = {"type": "buffer"}
                            for buf_elem in buf_struct:
                                buf_name = buf_elem.get("name", "")
                                if buf_name == "buffer" and buf_elem.tag == "ResourceId":
                                    buf_info["resourceId"] = buf_elem.text.strip() if buf_elem.text else ""
                                elif buf_name == "offset":
                                    buf_info["offset"] = int(buf_elem.text.strip()) if buf_elem.text else 0
                                elif buf_name == "range":
                                    buf_info["range"] = int(buf_elem.text.strip()) if buf_elem.text else 0
                            if buf_info.get("resourceId"):
                                write_info["resources"].append(buf_info)
                                
                    elif name == "pImageInfo" and elem.tag == "array":
                        # 解析 image/sampler 绑定
                        for img_struct in elem.findall("struct"):
                            img_info = {"type": "image"}
                            for img_elem in img_struct:
                                img_name = img_elem.get("name", "")
                                if img_name == "imageView" and img_elem.tag == "ResourceId":
                                    img_info["resourceId"] = img_elem.text.strip() if img_elem.text else ""
                                elif img_name == "sampler" and img_elem.tag == "ResourceId":
                                    sampler_id = img_elem.text.strip() if img_elem.text else "0"
                                    if sampler_id and sampler_id != "0":
                                        img_info["samplerId"] = sampler_id
                                elif img_name == "imageLayout" and img_elem.tag == "enum":
                                    img_info["layout"] = img_elem.get("string", "")
                            if img_info.get("resourceId"):
                                write_info["resources"].append(img_info)
                
                if write_info["setId"]:
                    results.append(write_info)
    
    return results


def collect_descriptor_set_contents(chunks):
    """预扫描所有 vkUpdateDescriptorSets，建立描述符集内容映射表
    
    Args:
        chunks: ET.Element - XML 中的 <chunks> 元素
        
    Returns:
        dict: {setId -> [{binding, descriptorType, resources}]}
    """
    descriptor_set_contents = defaultdict(list)
    
    for chunk in chunks.findall("chunk"):
        if chunk.get("name") == "vkUpdateDescriptorSets":
            writes = parse_vk_update_descriptor_sets_chunk(chunk)
            for write in writes:
                set_id = write["setId"]
                binding_info = {
                    "binding": write["binding"],
                    "descriptorType": write["descriptorType"],
                    "resources": write["resources"]
                }
                # 合并到同一 setId（可能有多个 vkUpdateDescriptorSets 更新同一 set）
                # 使用 binding 号去重
                existing_bindings = {b["binding"] for b in descriptor_set_contents[set_id]}
                if binding_info["binding"] not in existing_bindings:
                    descriptor_set_contents[set_id].append(binding_info)
                else:
                    # 更新已有的 binding
                    for i, b in enumerate(descriptor_set_contents[set_id]):
                        if b["binding"] == binding_info["binding"]:
                            descriptor_set_contents[set_id][i] = binding_info
                            break
    
    return dict(descriptor_set_contents)


# ============================================================================
# State Object Parsing (CreateBlendState / CreateDepthStencilState)
# ============================================================================

def parse_create_blend_state_chunk(chunk):
    """从 CreateBlendState chunk 解析 blend state 配置
    
    Returns:
        dict: {
            "stateId": "273",
            "alphaToCoverageEnable": False,
            "independentBlendEnable": False,
            "renderTargets": [{ "BlendEnable": True, "SrcBlend": "D3D11_BLEND_SRC_ALPHA", ... }]
        }
    """
    result = {
        "stateId": None,
        "alphaToCoverageEnable": False,
        "independentBlendEnable": False,
        "renderTargets": [],
    }
    
    # 找 Descriptor struct
    for child in chunk:
        if child.tag == "struct" and child.get("name") == "Descriptor":
            # 解析 D3D11_BLEND_DESC
            for elem in child:
                if elem.tag == "bool" and elem.get("name") == "AlphaToCoverageEnable":
                    result["alphaToCoverageEnable"] = elem.text.strip().lower() == "true" if elem.text else False
                elif elem.tag == "bool" and elem.get("name") == "IndependentBlendEnable":
                    result["independentBlendEnable"] = elem.text.strip().lower() == "true" if elem.text else False
                elif elem.tag == "array" and elem.get("name") == "RenderTarget":
                    for rt_struct in elem:
                        rt = {}
                        for field in rt_struct:
                            name = field.get("name")
                            if field.tag == "bool":
                                rt[name] = field.text.strip().lower() == "true" if field.text else False
                            elif field.tag == "enum":
                                # 优先使用 string 属性（人类可读）
                                rt[name] = field.get("string", field.text.strip() if field.text else "Unknown")
                        result["renderTargets"].append(rt)
                        # 只取第一个 RenderTarget（如果不是 IndependentBlend）
                        if not result["independentBlendEnable"]:
                            break
        elif child.tag == "ResourceId" and child.get("name") == "pState":
            result["stateId"] = child.text.strip() if child.text else None
    
    return result


def parse_create_depth_stencil_state_chunk(chunk):
    """从 CreateDepthStencilState chunk 解析 depth stencil state 配置
    
    Returns:
        dict: {
            "stateId": "182",
            "depthEnable": False,
            "depthWriteMask": "D3D11_DEPTH_WRITE_MASK_ZERO",
            "depthFunc": "D3D11_COMPARISON_LESS",
            "stencilEnable": False,
            ...
        }
    """
    result = {
        "stateId": None,
        "depthEnable": True,
        "depthWriteMask": "D3D11_DEPTH_WRITE_MASK_ALL",
        "depthFunc": "D3D11_COMPARISON_LESS",
        "stencilEnable": False,
        "stencilReadMask": 255,
        "stencilWriteMask": 255,
        "frontFace": {},
        "backFace": {},
    }
    
    # 找 Descriptor struct
    for child in chunk:
        if child.tag == "struct" and child.get("name") == "Descriptor":
            for elem in child:
                name = elem.get("name")
                if elem.tag == "bool" and name == "DepthEnable":
                    result["depthEnable"] = elem.text.strip().lower() == "true" if elem.text else True
                elif elem.tag == "enum" and name == "DepthWriteMask":
                    result["depthWriteMask"] = elem.get("string", elem.text.strip() if elem.text else "Unknown")
                elif elem.tag == "enum" and name == "DepthFunc":
                    result["depthFunc"] = elem.get("string", elem.text.strip() if elem.text else "Unknown")
                elif elem.tag == "bool" and name == "StencilEnable":
                    result["stencilEnable"] = elem.text.strip().lower() == "true" if elem.text else False
                elif elem.tag == "uint" and name == "StencilReadMask":
                    result["stencilReadMask"] = int(elem.text.strip()) if elem.text else 255
                elif elem.tag == "uint" and name == "StencilWriteMask":
                    result["stencilWriteMask"] = int(elem.text.strip()) if elem.text else 255
                elif elem.tag == "struct" and name in ("FrontFace", "BackFace"):
                    face = {}
                    for field in elem:
                        fname = field.get("name")
                        if field.tag == "enum":
                            face[fname] = field.get("string", field.text.strip() if field.text else "Unknown")
                    # 保持 Python 风格的命名
                    key = "frontFace" if name == "FrontFace" else "backFace"
                    result[key] = face
        elif child.tag == "ResourceId" and child.get("name") == "pState":
            result["stateId"] = child.text.strip() if child.text else None
    
    return result


def collect_state_objects_from_xml(chunks):
    """预处理阶段：从 XML 收集所有 state 对象的配置
    
    Args:
        chunks: ET.Element - XML 中的 <chunks> 元素
        
    Returns:
        dict: {
            "blendStates": { stateId -> config },
            "depthStencilStates": { stateId -> config },
        }
    """
    state_objects = {
        "blendStates": {},
        "depthStencilStates": {},
    }
    
    for chunk in chunks.findall("chunk"):
        name = chunk.get("name", "")
        
        if "CreateBlendState" in name:
            config = parse_create_blend_state_chunk(chunk)
            if config["stateId"]:
                state_objects["blendStates"][config["stateId"]] = config
        
        elif "CreateDepthStencilState" in name:
            config = parse_create_depth_stencil_state_chunk(chunk)
            if config["stateId"]:
                state_objects["depthStencilStates"][config["stateId"]] = config
    
    return state_objects


# ============================================================================
# Chunk Params Parsing
# ============================================================================

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
    
    # 始终保留 string 属性（枚举的可读名称）
    if elem.get("string"):
        result["string"] = elem.get("string")
        # 如果没有 value，用 string 作为 value
        if "value" not in result:
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
            
            # 格式 - 优先使用 string 属性（可读名称）
            if "format" in fields:
                fmt = fields["format"]
                fmt_string = fmt.get("string", fmt.get("value", "Unknown"))
                texture_info["format"] = fmt_string
                texture_info["formatName"] = fmt_string.replace("VK_FORMAT_", "")
                
            # 类型 - 优先使用 string 属性
            if "imageType" in fields:
                img_type = fields["imageType"]
                texture_info["imageType"] = img_type.get("string", img_type.get("value", "VK_IMAGE_TYPE_2D"))
                
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
                
            # Samples - 优先使用 string 属性
            if "samples" in fields:
                samples = fields["samples"]
                texture_info["samples"] = samples.get("string", samples.get("value", "VK_SAMPLE_COUNT_1_BIT"))
                
            # Usage - 优先使用 string 属性
            if "usage" in fields:
                usage = fields["usage"]
                texture_info["usage"] = usage.get("string", usage.get("value", ""))
                texture_info["usageFlags"] = usage.get("value", "0")
                
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


def parse_d3d11_create_texture2d(params):
    """解析 D3D11 CreateTexture2D 参数，提取纹理信息
    
    D3D11 XML 结构:
        <struct name="Descriptor" typename="D3D11_TEXTURE2D_DESC">
            <uint name="Width">1024</uint>
            <uint name="Height">1024</uint>
            <enum name="Format" string="DXGI_FORMAT_R8G8B8A8_UNORM">28</enum>
            ...
        </struct>
        <ResourceId name="pTexture">281</ResourceId>
    """
    texture_info = {}
    
    for p in params:
        name = p.get("name", "")
        
        # 获取资源 ID (D3D11 使用 pTexture)
        if name == "pTexture":
            texture_info["resourceId"] = p.get("value", "0")
            
        # 获取 Descriptor (D3D11_TEXTURE2D_DESC)
        elif name == "Descriptor" and "fields" in p:
            fields = p["fields"]
            
            # 尺寸
            if "Width" in fields:
                texture_info["width"] = int(fields["Width"].get("value", 0))
            if "Height" in fields:
                texture_info["height"] = int(fields["Height"].get("value", 0))
            
            # 深度固定为 1 (2D 纹理)
            texture_info["depth"] = 1
            
            # Mip levels
            if "MipLevels" in fields:
                texture_info["mipLevels"] = int(fields["MipLevels"].get("value", 1))
            
            # Array size
            if "ArraySize" in fields:
                texture_info["arrayLayers"] = int(fields["ArraySize"].get("value", 1))
            
            # 格式 - 优先使用 string 属性
            if "Format" in fields:
                fmt = fields["Format"]
                fmt_string = fmt.get("string", fmt.get("value", "Unknown"))
                texture_info["format"] = fmt_string
                texture_info["formatName"] = fmt_string.replace("DXGI_FORMAT_", "")
            
            # 用途
            if "Usage" in fields:
                usage = fields["Usage"]
                texture_info["usage"] = usage.get("string", usage.get("value", ""))
            
            # 绑定标志
            if "BindFlags" in fields:
                bind = fields["BindFlags"]
                texture_info["bindFlags"] = bind.get("string", bind.get("value", ""))
    
    # 生成友好名称
    if texture_info.get("resourceId"):
        w = texture_info.get("width", 0)
        h = texture_info.get("height", 0)
        fmt = texture_info.get("formatName", "Unknown")
        texture_info["name"] = f"Texture2D_{w}x{h}_{fmt}"
        
        # 估算内存大小
        mips = texture_info.get("mipLevels", 1)
        layers = texture_info.get("arrayLayers", 1)
        bpp = _estimate_d3d11_bpp(texture_info.get("format", ""))
        texture_info["memorySize"] = _estimate_texture_memory(w, h, mips, layers, bpp)
    
    return texture_info if texture_info.get("resourceId") else None


def _estimate_d3d11_bpp(format_str: str) -> float:
    """估算 D3D11 格式的每像素字节数"""
    fmt = format_str.upper()
    
    # 压缩格式
    if "BC1" in fmt or "BC4" in fmt:
        return 0.5
    if "BC2" in fmt or "BC3" in fmt or "BC5" in fmt or "BC6" in fmt or "BC7" in fmt:
        return 1.0
    
    # 常见未压缩格式
    if "R32G32B32A32" in fmt:
        return 16.0
    if "R32G32B32" in fmt:
        return 12.0
    if "R32G32" in fmt:
        return 8.0
    if "R32" in fmt or "R16G16B16A16" in fmt:
        return 8.0 if "R16G16B16A16" in fmt else 4.0
    if "R16G16" in fmt:
        return 4.0
    if "R8G8B8A8" in fmt or "B8G8R8A8" in fmt:
        return 4.0
    if "R8G8" in fmt:
        return 2.0
    if "R8" in fmt:
        return 1.0
    if "D32" in fmt:
        return 4.0
    if "D24" in fmt:
        return 4.0
    if "D16" in fmt:
        return 2.0
    
    # 默认 4 bpp
    return 4.0


def _estimate_texture_memory(width: int, height: int, mips: int, layers: int, bpp: float) -> int:
    """估算纹理内存大小（字节）"""
    if mips <= 0:
        mips = 1
    if layers <= 0:
        layers = 1
    
    total = 0
    w, h = width, height
    for _ in range(mips):
        total += int(w * h * bpp)
        w = max(1, w // 2)
        h = max(1, h // 2)
    
    return total * layers


def _parse_vk_sample_count(value: str) -> int:
    """解析 Vulkan sample count 字符串为整数。"""
    if not value:
        return 1
    if "VK_SAMPLE_COUNT_" in value:
        tail = value.split("VK_SAMPLE_COUNT_", 1)[-1]
        token = tail.split("_", 1)[0]
        try:
            return int(token)
        except ValueError:
            return 1
    try:
        return int(value)
    except ValueError:
        return 1


def parse_create_render_pass(params):
    """解析 vkCreateRenderPass/vkCreateRenderPass2 参数，提取附件与 resolve 信息。"""
    info = {
        "attachments": [],
        "resolveAttachmentCount": 0,
        "hasResolve": False,
    }

    for p in params:
        name = p.get("name", "")

        if name in ("RenderPass", "renderPass"):
            info["resourceId"] = p.get("value", "0")
        elif name == "CreateInfo" and "fields" in p:
            fields = p["fields"]

            attachments = fields.get("pAttachments", {}).get("elements", [])
            for index, att in enumerate(attachments):
                if "fields" not in att:
                    continue
                att_fields = att["fields"]
                samples_value = att_fields.get("samples", {}).get("value", "")
                info["attachments"].append({
                    "index": index,
                    "format": att_fields.get("format", {}).get("value", ""),
                    "samples": samples_value,
                    "sampleCount": _parse_vk_sample_count(samples_value),
                    "loadOp": att_fields.get("loadOp", {}).get("value", ""),
                    "storeOp": att_fields.get("storeOp", {}).get("value", ""),
                    "flags": att_fields.get("flags", {}).get("value", ""),
                })

            subpasses = fields.get("pSubpasses", {}).get("elements", [])
            for subpass in subpasses:
                if "fields" not in subpass:
                    continue
                sub_fields = subpass["fields"]
                resolve = sub_fields.get("pResolveAttachments", {})
                resolve_count = len(resolve.get("elements", []) or [])
                info["resolveAttachmentCount"] += resolve_count

    info["hasResolve"] = info["resolveAttachmentCount"] > 0
    return info if info.get("resourceId") or info["attachments"] else None


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
    
    # ========== 预处理阶段：收集 State 对象配置 ==========
    # 先遍历一次收集 CreateBlendState / CreateDepthStencilState 的配置
    # 这样在后续解析 OMSetBlendState/OMSetDepthStencilState 时可以查找完整参数
    state_objects = collect_state_objects_from_xml(chunks)
    print(f"  Collected {len(state_objects['blendStates'])} BlendStates, {len(state_objects['depthStencilStates'])} DepthStencilStates")
    
    # ========== 预处理阶段：收集 Vulkan Descriptor Set 内容 ==========
    # 先遍历一次收集 vkUpdateDescriptorSets 的绑定信息
    # 这样在后续解析 vkCmdBindDescriptorSets 时可以展开为具体资源
    descriptor_set_contents = collect_descriptor_set_contents(chunks)
    print(f"  Collected {len(descriptor_set_contents)} Vulkan DescriptorSets with bindings")
    
    events = []
    textures = {}
    buffers = {}
    render_passes = []
    render_pass_infos = {}
    
    current_render_pass = None
    current_pass_events = []
    event_id = 0
    
    # Vulkan draw/dispatch calls (真正的渲染调用，会清空 binding_records)
    vk_draw_calls = [
        "vkCmdDraw", "vkCmdDrawIndexed", "vkCmdDrawIndirect", "vkCmdDrawIndexedIndirect",
        "vkCmdDrawMeshTasksEXT", "vkCmdDispatch", "vkCmdDispatchIndirect",
    ]
    
    # D3D11 draw/dispatch calls (真正的渲染调用，会清空 binding_records)
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
    ]
    
    # D3D12 draw/dispatch calls (真正的渲染调用，会清空 binding_records)
    d3d12_draw_calls = [
        "ID3D12GraphicsCommandList::DrawInstanced",
        "ID3D12GraphicsCommandList::DrawIndexedInstanced",
        "ID3D12GraphicsCommandList::Dispatch",
    ]
    
    # OpenGL draw/dispatch calls (真正的渲染调用，会清空 binding_records)
    gl_draw_calls = [
        # Basic draw calls
        "glDrawArrays", "glDrawElements",
        # Instanced draw calls  
        "glDrawArraysInstanced", "glDrawElementsInstanced",
        "glDrawArraysInstancedBaseInstance", "glDrawElementsInstancedBaseInstance",
        "glDrawElementsInstancedBaseVertex", "glDrawElementsInstancedBaseVertexBaseInstance",
        # Range draw calls
        "glDrawRangeElements", "glDrawRangeElementsBaseVertex",
        # Base vertex draw calls
        "glDrawElementsBaseVertex",
        # Indirect draw calls
        "glDrawArraysIndirect", "glDrawElementsIndirect",
        "glMultiDrawArraysIndirect", "glMultiDrawElementsIndirect",
        "glMultiDrawArraysIndirectCount", "glMultiDrawElementsIndirectCount",
        # Multi draw calls
        "glMultiDrawArrays", "glMultiDrawElements", "glMultiDrawElementsBaseVertex",
        # Transform feedback draw calls
        "glDrawTransformFeedback", "glDrawTransformFeedbackInstanced",
        "glDrawTransformFeedbackStream", "glDrawTransformFeedbackStreamInstanced",
        # Compute dispatch
        "glDispatchCompute", "glDispatchComputeIndirect", "glDispatchComputeGroupSizeARB",
    ]
    
    # Clear/Copy/Resolve 调用 - 记录为事件但不清空 binding_records
    # 因为这些调用不需要完整的 pipeline state，而且 binding 应该延续到下一个 Draw
    auxiliary_calls = [
        # Vulkan
        "vkCmdClearColorImage", "vkCmdClearDepthStencilImage", "vkCmdClearAttachments",
        "vkCmdBlitImage",
        "vkCmdCopyBuffer", "vkCmdCopyImage", "vkCmdCopyBufferToImage", "vkCmdCopyImageToBuffer",
        "vkCmdResolveImage",
        "vkCmdUpdateBuffer", "vkCmdFillBuffer",
        # D3D11
        "ID3D11DeviceContext::CopyResource",
        "ID3D11DeviceContext::CopySubresourceRegion",
        "ID3D11DeviceContext::ClearRenderTargetView",
        "ID3D11DeviceContext::ClearDepthStencilView",
        "ID3D11DeviceContext::ResolveSubresource",
        # D3D12
        "ID3D12GraphicsCommandList::CopyResource",
        "ID3D12GraphicsCommandList::CopyBufferRegion",
        "ID3D12GraphicsCommandList::CopyTextureRegion",
        "ID3D12GraphicsCommandList::ClearRenderTargetView",
        "ID3D12GraphicsCommandList::ClearDepthStencilView",
        # OpenGL
        "glClear", "glClearColor", "glClearDepth", "glClearStencil",
        "glClearTexImage", "glClearTexSubImage",
        "glClearNamedFramebufferfv", "glClearNamedFramebufferiv",
        "glClearNamedFramebufferuiv", "glClearNamedFramebufferfi",
        "glClearNamedBufferDataEXT", "glClearNamedBufferSubDataEXT",
        "glCopyImageSubData", "glBlitFramebuffer", "glBlitNamedFramebuffer",
    ]
    
    # Combined draw call names (会清空 binding_records)
    draw_call_names = vk_draw_calls + d3d11_draw_calls + d3d12_draw_calls + gl_draw_calls
    
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
    
    # OpenGL markers (debug groups)
    gl_marker_names = [
        "glPushDebugGroup", "glPopDebugGroup",
        "glPushDebugGroupKHR", "glPopDebugGroupKHR",  # ES extension
    ]
    
    marker_names = vk_marker_names + d3d_marker_names + gl_marker_names
    
    # Render pass begin/end
    render_pass_begin = ["vkCmdBeginRenderPass", "vkCmdBeginRenderPass2", "vkCmdBeginRendering"]
    render_pass_end = ["vkCmdEndRenderPass", "vkCmdEndRenderPass2", "vkCmdEndRendering"]
    
    # OpenGL "render pass" equivalents (framebuffer binding)
    gl_framebuffer_binding = ["glBindFramebuffer", "glBindNamedFramebuffer"]
    
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
    
    # OpenGL binding calls
    gl_binding_calls = [
        # Programs and Pipelines
        "glUseProgram", "glBindProgramPipeline",
        "glUseProgramStages",
        # Vertex Input
        "glBindVertexArray", "glBindVertexBuffer", "glBindVertexBuffers",
        "glVertexAttribPointer", "glVertexAttribIPointer", "glVertexAttribLPointer",
        "glEnableVertexAttribArray", "glDisableVertexAttribArray",
        # Index Buffer
        "glBindBuffer",  # specifically GL_ELEMENT_ARRAY_BUFFER
        # Textures and Samplers
        "glBindTexture", "glBindTextures", "glBindTextureUnit",
        "glBindSampler", "glBindSamplers",
        "glBindImageTexture", "glBindImageTextures",
        "glActiveTexture",
        # Uniform Buffers
        "glBindBufferBase", "glBindBufferRange", "glBindBuffersBase", "glBindBuffersRange",
        # State
        "glViewport", "glViewportArrayv",
        "glScissor", "glScissorArrayv",
        "glBlendFunc", "glBlendFuncSeparate", "glBlendFunci", "glBlendFuncSeparatei",
        "glBlendEquation", "glBlendEquationSeparate", "glBlendEquationi", "glBlendEquationSeparatei",
        "glBlendColor",
        "glDepthFunc", "glDepthMask", "glDepthRange", "glDepthRangef",
        "glStencilFunc", "glStencilFuncSeparate",
        "glStencilOp", "glStencilOpSeparate",
        "glStencilMask", "glStencilMaskSeparate",
        "glColorMask", "glColorMaski",
        "glCullFace", "glFrontFace",
        "glPolygonMode", "glPolygonOffset", "glPolygonOffsetClamp",
        "glEnable", "glDisable", "glEnablei", "glDisablei",
        # Framebuffer
        "glBindFramebuffer", "glBindNamedFramebuffer",
        "glDrawBuffers", "glNamedFramebufferDrawBuffers",
    ]
    
    binding_calls = vk_binding_calls + d3d11_binding_calls + d3d12_binding_calls + gl_binding_calls
    
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
            # 判断是 draw、dispatch 还是其他类型
            # 支持 D3D/Vulkan 的 Draw/Dispatch 和 OpenGL 的 glDraw*/glDispatch*
            if "Draw" in chunk_name or chunk_name.startswith("glDraw"):
                event["type"] = "draw"
            elif "Dispatch" in chunk_name or chunk_name.startswith("glDispatch"):
                event["type"] = "dispatch"
            else:
                event["type"] = "copy"
            
            event["flags"] = []
            
            # 检测 indexed (D3D/Vulkan) 或 Elements (OpenGL)
            if "Indexed" in chunk_name or "Elements" in chunk_name:
                event["flags"].append("indexed")
            if "Indirect" in chunk_name:
                event["flags"].append("indirect")
            if "Instanced" in chunk_name:
                event["flags"].append("instanced")
            
            # 关联之前的绑定调用
            event["relatedCalls"] = current_bindings.copy()
            
            # 解析 Mesh 信息
            event["meshInfo"] = parse_mesh_info(current_binding_records)
            
            # 解析 Pipeline State（使用结构化数据以获取完整参数）
            event["pipelineState"] = parse_pipeline_state_from_binding_records(current_binding_records, state_objects)
            
            # 解析资源绑定（SRVs, CBVs, Samplers, DescriptorSets）
            event["resourceBindings"] = parse_resource_bindings(current_binding_records, descriptor_set_contents)
            
            current_bindings = []  # 清空，为下一个 draw 准备
            current_binding_records = []  # 清空结构化记录
            
            # 提取绘制参数
            # 支持 D3D11/D3D12/Vulkan 和 OpenGL 的不同参数命名
            for p in params:
                pname = p["name"]
                pvalue = p.get("value", 0)
                
                # Vertex/Index count
                if pname in ("vertexCount", "VertexCountPerInstance"):
                    event["vertexCount"] = int(pvalue) if pvalue else 0
                elif pname in ("indexCount", "IndexCountPerInstance"):
                    event["indexCount"] = int(pvalue) if pvalue else 0
                elif pname == "count":
                    # OpenGL: glDrawArrays(mode, first, count) / glDrawElements(mode, count, type, indices)
                    if "indexed" in event.get("flags", []):
                        event["indexCount"] = int(pvalue) if pvalue else 0
                    else:
                        event["vertexCount"] = int(pvalue) if pvalue else 0
                        
                # Instance count
                elif pname in ("instanceCount", "InstanceCount", "primcount", "instancecount"):
                    event["instanceCount"] = int(pvalue) if pvalue else 1
                    
                # First vertex/index
                elif pname in ("firstVertex", "StartVertexLocation"):
                    event["firstVertex"] = int(pvalue) if pvalue else 0
                elif pname == "first":
                    # OpenGL: glDrawArrays(mode, first, count)
                    event["firstVertex"] = int(pvalue) if pvalue else 0
                elif pname in ("firstIndex", "StartIndexLocation"):
                    event["firstIndex"] = int(pvalue) if pvalue else 0
                elif pname == "start":
                    # OpenGL: glDrawRangeElements(mode, start, end, count, type, indices)
                    event["rangeStart"] = int(pvalue) if pvalue else 0
                elif pname == "end":
                    event["rangeEnd"] = int(pvalue) if pvalue else 0
                    
                # OpenGL specific: mode (topology)
                elif pname == "mode":
                    event["topology"] = str(pvalue)
                    
                # OpenGL specific: type (index type)
                elif pname == "type" and "indexed" in event.get("flags", []):
                    event["indexType"] = str(pvalue)
            
            events.append(event)
            current_pass_events.append(event)
            event_id += 1
            
        elif chunk_name in binding_calls:
            # 记录绑定调用，等待关联到下一个 draw
            binding_str = format_binding_call(chunk_name, params)
            current_bindings.append(binding_str)
            # 同时保存结构化记录用于 meshInfo/pipelineState 解析
            current_binding_records.append({"name": chunk_name, "params": params})
            
        elif chunk_name in auxiliary_calls:
            # 辅助调用 (Clear/Copy/Resolve)：记录为事件但不清空 binding_records
            # 因为这些调用通常不改变 pipeline state，且 binding 应该延续到下一个 Draw
            if "Clear" in chunk_name:
                event["type"] = "clear"
            elif "Copy" in chunk_name or "Blit" in chunk_name:
                event["type"] = "copy"
            else:
                event["type"] = "resolve"
            event["flags"] = []
            
            # 关联当前的绑定调用（但不清空）
            event["relatedCalls"] = current_bindings.copy()
            
            # 解析 Pipeline State（使用当前 binding_records 快照，但不清空）
            event["pipelineState"] = parse_pipeline_state_from_binding_records(current_binding_records, state_objects)
            
            # 注意：不清空 current_bindings 和 current_binding_records
            # 这样下一个 Draw 调用仍然可以获取正确的 shader 绑定
            
            events.append(event)
            current_pass_events.append(event)
            event_id += 1
            
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
                if p["name"] in ("pRenderPassBegin", "RenderPassBegin") and "fields" in p:
                    rp_info = p["fields"]
                    if "renderPass" in rp_info:
                        current_render_pass["renderPassId"] = rp_info["renderPass"].get("value", "")
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
            # 提取纹理/图像资源 (Vulkan)
            texture_info = parse_create_image(params)
            if texture_info:
                textures[texture_info["resourceId"]] = texture_info
        
        elif "CreateTexture2D" in chunk_name:
            # 提取纹理/图像资源 (D3D11)
            texture_info = parse_d3d11_create_texture2d(params)
            if texture_info:
                textures[texture_info["resourceId"]] = texture_info
                
        elif chunk_name == "vkCreateBuffer":
            # 提取缓冲区资源
            buffer_info = parse_create_buffer(params)
            if buffer_info:
                buffers[buffer_info["resourceId"]] = buffer_info
        
        elif chunk_name in ("vkCreateRenderPass", "vkCreateRenderPass2"):
            rp_info = parse_create_render_pass(params)
            if rp_info and rp_info.get("resourceId"):
                render_pass_infos[rp_info["resourceId"]] = rp_info
    
    # 处理最后一个 render pass
    if current_render_pass:
        current_render_pass["events"] = current_pass_events
        render_passes.append(current_render_pass)
    
    # 转换 textures 字典为列表，便于后续处理
    textures_list = list(textures.values())
    buffers_list = list(buffers.values())
    render_pass_infos_list = list(render_pass_infos.values())
    
    # ========== 收集全局 Shader 列表 ==========
    # 从所有事件的 pipelineState.shaders 中提取唯一 shader
    shaders_dict = {}  # key: shader_id, value: shader_info
    for event in events:
        pipeline_state = event.get("pipelineState")
        if not pipeline_state:
            continue
        shaders_info = pipeline_state.get("shaders")
        if not shaders_info:
            continue
        for stage, shader_data in shaders_info.items():
            if shader_data is None:
                continue
            # 提取 shader ID (支持多种格式)
            shader_id = None
            if isinstance(shader_data, dict):
                shader_id = shader_data.get("id") or shader_data.get("resourceId") or shader_data.get("raw")
            elif isinstance(shader_data, str):
                shader_id = shader_data
            if shader_id and shader_id not in shaders_dict:
                shaders_dict[shader_id] = {
                    "id": shader_id,
                    "stage": stage.upper(),
                    "type": stage.upper(),
                    "name": shader_data.get("name", f"Shader_{shader_id}") if isinstance(shader_data, dict) else f"Shader_{shader_id}",
                    "firstSeenEvent": event.get("eventId", 0),
                }
                # 合并其他属性
                if isinstance(shader_data, dict):
                    for k, v in shader_data.items():
                        if k not in shaders_dict[shader_id]:
                            shaders_dict[shader_id][k] = v
    shaders_list = list(shaders_dict.values())
    
    # 计算纹理统计
    total_texture_memory = sum(t.get("memorySize", 0) for t in textures_list)
    
    print(f"  Total events: {len(events)}")
    print(f"  Draw calls: {sum(1 for e in events if e.get('type') == 'draw')}")
    print(f"  Render passes: {len(render_passes)}")
    print(f"  Textures/Images: {len(textures_list)}")
    print(f"  Buffers: {len(buffers_list)}")
    print(f"  Shaders: {len(shaders_list)}")
    print(f"  Total texture memory: {total_texture_memory / (1024*1024):.2f} MB")
    
    return {
        "apiType": api_type,
        "events": events,
        "renderPasses": render_passes,
        "renderPassInfos": render_pass_infos_list,
        "textures": textures_list,
        "buffers": buffers_list,
        "shaders": shaders_list,
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
            "totalShaders": len(shaders_list),
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


# ============================================================
# 新增解析函数：Shader Resources, Constant Buffers, Samplers, RT
# ============================================================

def parse_shader_resources_from_params_simple(params):
    """
    解析 *SetShaderResources 调用的参数 (简化版，用于 Pipeline State 解析)
    返回: [{slot: int, resourceId: str}, ...]
    """
    start_slot = 0
    resources = []
    
    for p in params:
        name = p.get("name", "")
        if name == "StartSlot":
            start_slot = int(p.get("value", 0))
        elif name == "ppShaderResourceViews" and "elements" in p:
            for elem in p["elements"]:
                resources.append(elem.get("value", ""))
    
    result = []
    for i, res in enumerate(resources):
        if res and res != "ResourceId::Null()":
            result.append({
                "slot": start_slot + i,
                "resourceId": res
            })
    return result


def parse_constant_buffers_from_params_simple(params):
    """
    解析 *SetConstantBuffers 调用的参数 (简化版，用于 Pipeline State 解析)
    返回: [{slot: int, resourceId: str}, ...]
    """
    start_slot = 0
    buffers = []
    
    for p in params:
        name = p.get("name", "")
        if name == "StartSlot":
            start_slot = int(p.get("value", 0))
        elif name == "ppConstantBuffers" and "elements" in p:
            for elem in p["elements"]:
                buffers.append(elem.get("value", ""))
    
    result = []
    for i, buf in enumerate(buffers):
        if buf and buf != "ResourceId::Null()":
            result.append({
                "slot": start_slot + i,
                "resourceId": buf
            })
    return result


def parse_samplers_from_params_simple(params):
    """
    解析 *SetSamplers 调用的参数 (简化版，用于 Pipeline State 解析)
    返回: [{slot: int, resourceId: str}, ...]
    """
    start_slot = 0
    samplers = []
    
    for p in params:
        name = p.get("name", "")
        if name == "StartSlot":
            start_slot = int(p.get("value", 0))
        elif name == "ppSamplers" and "elements" in p:
            for elem in p["elements"]:
                samplers.append(elem.get("value", ""))
    
    result = []
    for i, sampler in enumerate(samplers):
        if sampler and sampler != "ResourceId::Null()":
            result.append({
                "slot": start_slot + i,
                "resourceId": sampler
            })
    return result


def parse_render_targets_from_params(params):
    """
    解析 OMSetRenderTargets 调用的参数
    返回: {views: [{slot: int, resourceId: str}, ...], depthStencil: str}
    """
    rtv_list = []
    dsv = None
    
    for p in params:
        name = p.get("name", "")
        if name == "ppRenderTargetViews" and "elements" in p:
            for i, elem in enumerate(p["elements"]):
                rid = elem.get("value", "")
                if rid and rid != "ResourceId::Null()":
                    rtv_list.append({
                        "slot": i,
                        "resourceId": rid
                    })
        elif name == "pDepthStencilView":
            val = p.get("value", "")
            if val and val != "ResourceId::Null()":
                dsv = val
    
    return {
        "views": rtv_list,
        "depthStencil": dsv
    }


def parse_vertex_buffers_from_params(params):
    """
    解析 IASetVertexBuffers 调用的参数
    返回: [{slot: int, buffer: str, stride: int, offset: int}, ...]
    """
    # 复用已有的 parse_d3d11_vertex_buffers
    return parse_d3d11_vertex_buffers(params)


def parse_index_buffer_from_params(params):
    """
    解析 IASetIndexBuffer 调用的参数
    返回: {buffer: str, format: str, offset: int}
    """
    # 复用已有的 parse_d3d11_index_buffer
    return parse_d3d11_index_buffer(params)


def merge_slot_resources(target_list, new_resources):
    """
    合并 slot-based 资源列表，同一 slot 以新值覆盖旧值
    """
    existing_slots = {r["slot"]: i for i, r in enumerate(target_list)}
    
    for res in new_resources:
        slot = res["slot"]
        if slot in existing_slots:
            # 覆盖已有 slot
            target_list[existing_slots[slot]] = res
        else:
            # 新增 slot
            target_list.append(res)
            existing_slots[slot] = len(target_list) - 1


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


def parse_pipeline_state_from_binding_records(binding_records, state_objects=None):
    """
    从结构化绑定记录中解析 Pipeline State 数据
    
    Args:
        binding_records: 结构化的绑定调用列表 [{"name": "...", "params": [...]}]
        state_objects: 预收集的 state 对象配置 (来自 CreateBlendState/CreateDepthStencilState)
    
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
        # 新增字段 - Shader Resources
        "shaderResources": {
            "vs": [],
            "ps": [],
            "gs": [],
            "hs": [],
            "ds": [],
            "cs": [],
        },
        # 新增字段 - Constant Buffers
        "constantBuffers": {
            "vs": [],
            "ps": [],
            "gs": [],
            "hs": [],
            "ds": [],
            "cs": [],
        },
        # 新增字段 - Samplers
        "samplers": {
            "vs": [],
            "ps": [],
            "gs": [],
            "hs": [],
            "ds": [],
            "cs": [],
        },
        # 新增字段 - Render Targets
        "renderTargets": {
            "views": [],
            "depthStencil": None,
        },
        # 新增字段 - Vertex/Index Buffers
        "vertexBuffers": [],
        "indexBuffer": None,
    }
    
    for record in binding_records:
        name = record.get("name", "")
        params = record.get("params", [])
        
        # 解析 Viewport (D3D11: RSSetViewports, D3D12: RSSetViewports)
        if "RSSetViewports" in name:
            viewport = parse_viewport_from_params(params)
            if viewport:
                pipeline_state["viewport"] = viewport
                
        # 解析 Viewport (Vulkan: vkCmdSetViewport)
        elif "vkCmdSetViewport" in name:
            viewport = parse_vulkan_viewport_from_params(params)
            if viewport:
                pipeline_state["viewport"] = viewport
                
        # 解析 Scissor (D3D11/D3D12)
        elif "RSSetScissorRects" in name:
            scissor = parse_scissor_from_params(params)
            if scissor:
                pipeline_state["scissor"] = scissor
                
        # 解析 Scissor (Vulkan)
        elif "vkCmdSetScissor" in name:
            scissor = parse_vulkan_scissor_from_params(params)
            if scissor:
                pipeline_state["scissor"] = scissor
                
        # 解析 Blend State (D3D11)
        elif "OMSetBlendState" in name:
            blend = parse_blend_state_from_params(params, state_objects)
            if blend:
                pipeline_state["blendState"] = blend
                
        # 解析 Depth Stencil State (D3D11)
        elif "OMSetDepthStencilState" in name:
            depth = parse_depth_state_from_params(params, state_objects)
            if depth:
                pipeline_state["depthState"] = depth
                
        # 解析 Rasterizer State (D3D11)
        elif "RSSetState" in name:
            rasterizer = parse_rasterizer_state_from_params(params)
            if rasterizer:
                pipeline_state["rasterizerState"] = rasterizer
                
        # 解析 Shaders (D3D11)
        # 注意：需要排除 SetShaderResources，因为 "VSSetShader" in "VSSetShaderResources" 为 True
        elif "VSSetShader" in name and "Resources" not in name:
            pipeline_state["shaders"]["vs"] = parse_shader_from_params(params, "VS")
        elif "PSSetShader" in name and "Resources" not in name:
            pipeline_state["shaders"]["ps"] = parse_shader_from_params(params, "PS")
        elif "GSSetShader" in name and "Resources" not in name:
            pipeline_state["shaders"]["gs"] = parse_shader_from_params(params, "GS")
        elif "HSSetShader" in name and "Resources" not in name:
            pipeline_state["shaders"]["hs"] = parse_shader_from_params(params, "HS")
        elif "DSSetShader" in name and "Resources" not in name:
            pipeline_state["shaders"]["ds"] = parse_shader_from_params(params, "DS")
        elif "CSSetShader" in name and "Resources" not in name:
            pipeline_state["shaders"]["cs"] = parse_shader_from_params(params, "CS")
            
        # 解析 Vulkan Pipeline
        elif "vkCmdBindPipeline" in name:
            pipeline_state["shaders"]["pipeline"] = parse_vulkan_pipeline_from_params(params)
            
        # 解析 Primitive Topology (D3D11)
        elif "IASetPrimitiveTopology" in name:
            topology = parse_topology_from_params(params)
            if topology:
                pipeline_state["primitiveTopology"] = topology
                
        # 解析 Input Layout (D3D11)
        elif "IASetInputLayout" in name:
            pipeline_state["inputLayout"] = parse_input_layout_from_params(params)
        
        # ============================================================
        # 新增解析：Shader Resources (SRV)
        # ============================================================
        elif "VSSetShaderResources" in name:
            resources = parse_shader_resources_from_params_simple(params)
            if resources:
                merge_slot_resources(pipeline_state["shaderResources"]["vs"], resources)
        elif "PSSetShaderResources" in name:
            resources = parse_shader_resources_from_params_simple(params)
            if resources:
                merge_slot_resources(pipeline_state["shaderResources"]["ps"], resources)
        elif "GSSetShaderResources" in name:
            resources = parse_shader_resources_from_params_simple(params)
            if resources:
                merge_slot_resources(pipeline_state["shaderResources"]["gs"], resources)
        elif "HSSetShaderResources" in name:
            resources = parse_shader_resources_from_params_simple(params)
            if resources:
                merge_slot_resources(pipeline_state["shaderResources"]["hs"], resources)
        elif "DSSetShaderResources" in name:
            resources = parse_shader_resources_from_params_simple(params)
            if resources:
                merge_slot_resources(pipeline_state["shaderResources"]["ds"], resources)
        elif "CSSetShaderResources" in name:
            resources = parse_shader_resources_from_params_simple(params)
            if resources:
                merge_slot_resources(pipeline_state["shaderResources"]["cs"], resources)
        
        # ============================================================
        # 新增解析：Constant Buffers (CBV)
        # ============================================================
        elif "VSSetConstantBuffers" in name:
            buffers = parse_constant_buffers_from_params_simple(params)
            if buffers:
                merge_slot_resources(pipeline_state["constantBuffers"]["vs"], buffers)
        elif "PSSetConstantBuffers" in name:
            buffers = parse_constant_buffers_from_params_simple(params)
            if buffers:
                merge_slot_resources(pipeline_state["constantBuffers"]["ps"], buffers)
        elif "GSSetConstantBuffers" in name:
            buffers = parse_constant_buffers_from_params_simple(params)
            if buffers:
                merge_slot_resources(pipeline_state["constantBuffers"]["gs"], buffers)
        elif "HSSetConstantBuffers" in name:
            buffers = parse_constant_buffers_from_params_simple(params)
            if buffers:
                merge_slot_resources(pipeline_state["constantBuffers"]["hs"], buffers)
        elif "DSSetConstantBuffers" in name:
            buffers = parse_constant_buffers_from_params_simple(params)
            if buffers:
                merge_slot_resources(pipeline_state["constantBuffers"]["ds"], buffers)
        elif "CSSetConstantBuffers" in name:
            buffers = parse_constant_buffers_from_params_simple(params)
            if buffers:
                merge_slot_resources(pipeline_state["constantBuffers"]["cs"], buffers)
        
        # ============================================================
        # 新增解析：Samplers
        # ============================================================
        elif "VSSetSamplers" in name:
            samplers = parse_samplers_from_params_simple(params)
            if samplers:
                merge_slot_resources(pipeline_state["samplers"]["vs"], samplers)
        elif "PSSetSamplers" in name:
            samplers = parse_samplers_from_params_simple(params)
            if samplers:
                merge_slot_resources(pipeline_state["samplers"]["ps"], samplers)
        elif "GSSetSamplers" in name:
            samplers = parse_samplers_from_params_simple(params)
            if samplers:
                merge_slot_resources(pipeline_state["samplers"]["gs"], samplers)
        elif "HSSetSamplers" in name:
            samplers = parse_samplers_from_params_simple(params)
            if samplers:
                merge_slot_resources(pipeline_state["samplers"]["hs"], samplers)
        elif "DSSetSamplers" in name:
            samplers = parse_samplers_from_params_simple(params)
            if samplers:
                merge_slot_resources(pipeline_state["samplers"]["ds"], samplers)
        elif "CSSetSamplers" in name:
            samplers = parse_samplers_from_params_simple(params)
            if samplers:
                merge_slot_resources(pipeline_state["samplers"]["cs"], samplers)
        
        # ============================================================
        # 新增解析：Render Targets
        # ============================================================
        elif "OMSetRenderTargets" in name:
            rt_info = parse_render_targets_from_params(params)
            if rt_info:
                pipeline_state["renderTargets"] = rt_info
        
        # ============================================================
        # 新增解析：Vertex Buffers
        # ============================================================
        elif "IASetVertexBuffers" in name:
            vb_info = parse_vertex_buffers_from_params(params)
            if vb_info:
                merge_slot_resources(pipeline_state["vertexBuffers"], vb_info)
        
        # ============================================================
        # 新增解析：Index Buffer
        # ============================================================
        elif "IASetIndexBuffer" in name:
            ib_info = parse_index_buffer_from_params(params)
            if ib_info:
                pipeline_state["indexBuffer"] = ib_info
    
    return pipeline_state


def parse_viewport_from_params(params):
    """从 RSSetViewports 结构化参数解析 viewport 数据"""
    viewport = {
        "x": 0.0,
        "y": 0.0,
        "width": 0.0,
        "height": 0.0,
        "minDepth": 0.0,
        "maxDepth": 1.0,
        "count": 1,
    }
    
    for p in params:
        name = p.get("name", "")
        
        if name == "NumViewports":
            viewport["count"] = int(p.get("value", 1))
            
        elif name == "pViewports" and "elements" in p:
            # 解析第一个 viewport（通常只有一个）
            viewports = p["elements"]
            if viewports:
                vp = viewports[0]
                if "fields" in vp:
                    fields = vp["fields"]
                    # D3D11: TopLeftX, TopLeftY, Width, Height, MinDepth, MaxDepth
                    if "TopLeftX" in fields:
                        viewport["x"] = float(fields["TopLeftX"].get("value", 0))
                    if "TopLeftY" in fields:
                        viewport["y"] = float(fields["TopLeftY"].get("value", 0))
                    if "Width" in fields:
                        viewport["width"] = float(fields["Width"].get("value", 0))
                    if "Height" in fields:
                        viewport["height"] = float(fields["Height"].get("value", 0))
                    if "MinDepth" in fields:
                        viewport["minDepth"] = float(fields["MinDepth"].get("value", 0))
                    if "MaxDepth" in fields:
                        viewport["maxDepth"] = float(fields["MaxDepth"].get("value", 1))
    
    return viewport


def parse_vulkan_viewport_from_params(params):
    """从 vkCmdSetViewport 结构化参数解析 viewport 数据"""
    viewport = {
        "x": 0.0,
        "y": 0.0,
        "width": 0.0,
        "height": 0.0,
        "minDepth": 0.0,
        "maxDepth": 1.0,
        "count": 1,
    }
    
    for p in params:
        name = p.get("name", "")
        
        if name == "viewportCount":
            viewport["count"] = int(p.get("value", 1))
            
        elif name == "pViewports" and "elements" in p:
            viewports = p["elements"]
            if viewports:
                vp = viewports[0]
                if "fields" in vp:
                    fields = vp["fields"]
                    # Vulkan: x, y, width, height, minDepth, maxDepth
                    if "x" in fields:
                        viewport["x"] = float(fields["x"].get("value", 0))
                    if "y" in fields:
                        viewport["y"] = float(fields["y"].get("value", 0))
                    if "width" in fields:
                        viewport["width"] = float(fields["width"].get("value", 0))
                    if "height" in fields:
                        viewport["height"] = float(fields["height"].get("value", 0))
                    if "minDepth" in fields:
                        viewport["minDepth"] = float(fields["minDepth"].get("value", 0))
                    if "maxDepth" in fields:
                        viewport["maxDepth"] = float(fields["maxDepth"].get("value", 1))
    
    return viewport


def parse_scissor_from_params(params):
    """从 RSSetScissorRects 结构化参数解析 scissor 数据"""
    scissor = {
        "left": 0,
        "top": 0,
        "right": 0,
        "bottom": 0,
        "count": 1,
    }
    
    for p in params:
        name = p.get("name", "")
        
        if name == "NumRects":
            scissor["count"] = int(p.get("value", 1))
            
        elif name == "pRects" and "elements" in p:
            rects = p["elements"]
            if rects:
                rect = rects[0]
                if "fields" in rect:
                    fields = rect["fields"]
                    # D3D11: left, top, right, bottom
                    if "left" in fields:
                        scissor["left"] = int(fields["left"].get("value", 0))
                    if "top" in fields:
                        scissor["top"] = int(fields["top"].get("value", 0))
                    if "right" in fields:
                        scissor["right"] = int(fields["right"].get("value", 0))
                    if "bottom" in fields:
                        scissor["bottom"] = int(fields["bottom"].get("value", 0))
    
    return scissor


def parse_vulkan_scissor_from_params(params):
    """从 vkCmdSetScissor 结构化参数解析 scissor 数据"""
    scissor = {
        "x": 0,
        "y": 0,
        "width": 0,
        "height": 0,
        "count": 1,
    }
    
    for p in params:
        name = p.get("name", "")
        
        if name == "scissorCount":
            scissor["count"] = int(p.get("value", 1))
            
        elif name == "pScissors" and "elements" in p:
            scissors = p["elements"]
            if scissors:
                sc = scissors[0]
                if "fields" in sc:
                    fields = sc["fields"]
                    # Vulkan: offset (x, y), extent (width, height)
                    if "offset" in fields and "fields" in fields["offset"]:
                        offset = fields["offset"]["fields"]
                        if "x" in offset:
                            scissor["x"] = int(offset["x"].get("value", 0))
                        if "y" in offset:
                            scissor["y"] = int(offset["y"].get("value", 0))
                    if "extent" in fields and "fields" in fields["extent"]:
                        extent = fields["extent"]["fields"]
                        if "width" in extent:
                            scissor["width"] = int(extent["width"].get("value", 0))
                        if "height" in extent:
                            scissor["height"] = int(extent["height"].get("value", 0))
    
    return scissor


def parse_blend_state_from_params(params, state_objects=None):
    """从 OMSetBlendState 结构化参数解析 blend state 数据
    
    Args:
        params: OMSetBlendState 调用的参数列表
        state_objects: 预收集的 state 对象配置 (来自 CreateBlendState)
    """
    blend = {
        "enabled": True,
        "stateId": None,
        "blendFactor": [1.0, 1.0, 1.0, 1.0],
        "sampleMask": "0xFFFFFFFF",
        "srcColor": "Unknown",
        "dstColor": "Unknown",
        "blendOp": "Unknown",
        "srcAlpha": "Unknown",
        "dstAlpha": "Unknown",
        "blendOpAlpha": "Unknown",
    }
    
    state_id = None
    
    for p in params:
        name = p.get("name", "")
        
        if name == "pBlendState":
            value = p.get("value", "")
            state_id = value
            blend["stateId"] = value
            blend["enabled"] = value and value != "0" and value.upper() != "NULL"
            
        elif name == "BlendFactor" and "elements" in p:
            factors = []
            for elem in p["elements"][:4]:
                factors.append(float(elem.get("value", 1.0)))
            if factors:
                blend["blendFactor"] = factors
                
        elif name == "SampleMask":
            blend["sampleMask"] = p.get("value", "0xFFFFFFFF")
    
    # 从 state_objects 查找完整的 blend 配置
    if state_id and state_objects and "blendStates" in state_objects:
        blend_config = state_objects["blendStates"].get(state_id)
        if blend_config and blend_config.get("renderTargets"):
            rt = blend_config["renderTargets"][0]  # 取第一个 RenderTarget
            blend["srcColor"] = rt.get("SrcBlend", "Unknown")
            blend["dstColor"] = rt.get("DestBlend", "Unknown")
            blend["blendOp"] = rt.get("BlendOp", "Unknown")
            blend["srcAlpha"] = rt.get("SrcBlendAlpha", "Unknown")
            blend["dstAlpha"] = rt.get("DestBlendAlpha", "Unknown")
            blend["blendOpAlpha"] = rt.get("BlendOpAlpha", "Unknown")
            blend["enabled"] = rt.get("BlendEnable", True)
    
    return blend


def parse_depth_state_from_params(params, state_objects=None):
    """从 OMSetDepthStencilState 结构化参数解析 depth stencil state 数据
    
    Args:
        params: OMSetDepthStencilState 调用的参数列表
        state_objects: 预收集的 state 对象配置 (来自 CreateDepthStencilState)
    """
    depth = {
        "testEnabled": True,
        "writeEnabled": True,
        "compareFunc": "Unknown",
        "depthWriteMask": "Unknown",
        "stencilEnabled": False,
        "stencilRef": 0,
        "stateId": None,
    }
    
    state_id = None
    
    for p in params:
        name = p.get("name", "")
        
        if name == "pDepthStencilState":
            value = p.get("value", "")
            state_id = value
            depth["stateId"] = value
            # 暂时使用简单逻辑，后面从 state_objects 获取准确值
            depth["testEnabled"] = value and value != "0" and value.upper() != "NULL"
            depth["writeEnabled"] = depth["testEnabled"]
            
        elif name == "StencilRef":
            depth["stencilRef"] = int(p.get("value", 0))
    
    # 从 state_objects 查找完整的 depth stencil 配置
    if state_id and state_objects and "depthStencilStates" in state_objects:
        depth_config = state_objects["depthStencilStates"].get(state_id)
        if depth_config:
            depth["testEnabled"] = depth_config.get("depthEnable", True)
            depth["compareFunc"] = depth_config.get("depthFunc", "Unknown")
            depth["depthWriteMask"] = depth_config.get("depthWriteMask", "Unknown")
            depth["stencilEnabled"] = depth_config.get("stencilEnable", False)
            # writeEnabled 基于 depthWriteMask
            write_mask = depth_config.get("depthWriteMask", "")
            depth["writeEnabled"] = "ALL" in write_mask if write_mask else True
    
    return depth


def parse_rasterizer_state_from_params(params):
    """从 RSSetState 结构化参数解析 rasterizer state 数据"""
    rasterizer = {
        "stateId": None,
        "fillMode": "Solid",
        "cullMode": "Back",
    }
    
    for p in params:
        name = p.get("name", "")
        
        if name == "pRasterizerState":
            rasterizer["stateId"] = p.get("value", "")
    
    return rasterizer


def parse_shader_from_params(params, shader_type):
    """从 SetShader 结构化参数解析 shader 信息"""
    shader = {
        "type": shader_type,
        "id": None,
        "valid": False,
    }
    
    for p in params:
        name = p.get("name", "")
        
        # D3D11: pShader, pVertexShader, pPixelShader, etc.
        if name in ["pShader", "pVertexShader", "pPixelShader", "pGeometryShader",
                    "pHullShader", "pDomainShader", "pComputeShader"]:
            value = p.get("value", "")
            shader["id"] = value
            shader["valid"] = value and value != "0" and value.upper() != "NULL"
    
    return shader


def parse_vulkan_pipeline_from_params(params):
    """从 vkCmdBindPipeline 结构化参数解析 pipeline 信息"""
    pipeline = {
        "type": "Pipeline",
        "id": None,
        "valid": False,
        "bindPoint": None,
    }
    
    for p in params:
        name = p.get("name", "")
        
        if name == "pipeline":
            value = p.get("value", "")
            pipeline["id"] = value
            pipeline["valid"] = value and value != "0" and value.upper() != "NULL"
            
        elif name == "pipelineBindPoint":
            pipeline["bindPoint"] = p.get("value", "")
    
    return pipeline


def parse_topology_from_params(params):
    """从 IASetPrimitiveTopology 结构化参数解析图元拓扑"""
    for p in params:
        name = p.get("name", "")
        
        if name == "Topology":
            topo = p.get("value", "")
            # 简化名称
            topo = topo.replace("D3D11_PRIMITIVE_TOPOLOGY_", "")
            topo = topo.replace("D3D_PRIMITIVE_TOPOLOGY_", "")
            return topo
    
    return None


def parse_input_layout_from_params(params):
    """从 IASetInputLayout 结构化参数解析 input layout"""
    layout = {
        "id": None,
        "valid": False,
    }
    
    for p in params:
        name = p.get("name", "")
        
        if name == "pInputLayout":
            value = p.get("value", "")
            layout["id"] = value
            layout["valid"] = value and value != "0" and value.upper() != "NULL"
    
    return layout


def parse_resource_bindings(binding_records, descriptor_set_contents=None):
    """
    从结构化绑定记录中解析资源绑定数据
    
    Args:
        binding_records: 结构化的绑定调用列表 [{"name": "...", "params": [...]}]
        descriptor_set_contents: Vulkan 描述符集内容映射表 {set_id -> [bindings]}
    
    返回:
        dict: 包含 shaderResources, constantBuffers, samplers, descriptorSets 等信息
    """
    if descriptor_set_contents is None:
        descriptor_set_contents = {}
    bindings = {
        "shaderResources": [],   # SRVs (纹理/缓冲区)
        "constantBuffers": [],   # CBVs
        "samplers": [],          # 采样器
        "descriptorSets": [],    # Vulkan 描述符集
        "unorderedAccessViews": [],  # UAVs
    }
    
    for record in binding_records:
        name = record.get("name", "")
        params = record.get("params", [])
        
        # ============= D3D11 Shader Resources (SRVs) =============
        if "SetShaderResources" in name:
            srvs = parse_shader_resources_from_params(params, name)
            if srvs:
                bindings["shaderResources"].extend(srvs)
                
        # ============= D3D11 Constant Buffers =============
        elif "SetConstantBuffers" in name:
            cbs = parse_constant_buffers_from_params(params, name)
            if cbs:
                bindings["constantBuffers"].extend(cbs)
                
        # ============= D3D11 Samplers =============
        elif "SetSamplers" in name:
            samplers = parse_samplers_from_params(params, name)
            if samplers:
                bindings["samplers"].extend(samplers)
                
        # ============= D3D11 Unordered Access Views =============
        elif "SetUnorderedAccessViews" in name:
            uavs = parse_uavs_from_params(params, name)
            if uavs:
                bindings["unorderedAccessViews"].extend(uavs)
                
        # ============= Vulkan Descriptor Sets =============
        elif "vkCmdBindDescriptorSets" in name:
            desc_sets = parse_descriptor_sets_from_params(params, descriptor_set_contents)
            if desc_sets:
                bindings["descriptorSets"].extend(desc_sets)
                
        # ============= D3D12 Root Descriptor Table =============
        elif "SetGraphicsRootDescriptorTable" in name:
            desc_table = parse_d3d12_descriptor_table_from_params(params)
            if desc_table:
                bindings["descriptorSets"].append(desc_table)
                
        # ============= D3D12 Root Constant Buffer View =============
        elif "SetGraphicsRootConstantBufferView" in name:
            cbv = parse_d3d12_cbv_from_params(params)
            if cbv:
                bindings["constantBuffers"].append(cbv)
    
    return bindings


def parse_shader_resources_from_params(params, call_name):
    """解析 D3D11 *SetShaderResources 的资源绑定"""
    resources = []
    
    # 确定着色器阶段
    stage = "PS"
    if "VS" in call_name:
        stage = "VS"
    elif "GS" in call_name:
        stage = "GS"
    elif "HS" in call_name:
        stage = "HS"
    elif "DS" in call_name:
        stage = "DS"
    elif "CS" in call_name:
        stage = "CS"
    
    start_slot = 0
    
    for p in params:
        name = p.get("name", "")
        
        if name == "StartSlot":
            start_slot = int(p.get("value", 0))
            
        elif name == "ppShaderResourceViews" and "elements" in p:
            elements = p["elements"]
            for i, elem in enumerate(elements):
                srv_id = elem.get("value", "")
                if srv_id and srv_id != "0" and srv_id.upper() != "NULL":
                    resources.append({
                        "type": "SRV",
                        "stage": stage,
                        "slot": start_slot + i,
                        "resourceId": srv_id,
                    })
    
    return resources


def parse_constant_buffers_from_params(params, call_name):
    """解析 D3D11 *SetConstantBuffers 的常量缓冲区绑定"""
    buffers = []
    
    # 确定着色器阶段
    stage = "PS"
    if "VS" in call_name:
        stage = "VS"
    elif "GS" in call_name:
        stage = "GS"
    elif "HS" in call_name:
        stage = "HS"
    elif "DS" in call_name:
        stage = "DS"
    elif "CS" in call_name:
        stage = "CS"
    
    start_slot = 0
    
    for p in params:
        name = p.get("name", "")
        
        if name == "StartSlot":
            start_slot = int(p.get("value", 0))
            
        elif name == "ppConstantBuffers" and "elements" in p:
            elements = p["elements"]
            for i, elem in enumerate(elements):
                cb_id = elem.get("value", "")
                if cb_id and cb_id != "0" and cb_id.upper() != "NULL":
                    buffers.append({
                        "type": "CBV",
                        "stage": stage,
                        "slot": start_slot + i,
                        "resourceId": cb_id,
                    })
    
    return buffers


def parse_samplers_from_params(params, call_name):
    """解析 D3D11 *SetSamplers 的采样器绑定"""
    samplers = []
    
    # 确定着色器阶段
    stage = "PS"
    if "VS" in call_name:
        stage = "VS"
    elif "GS" in call_name:
        stage = "GS"
    elif "CS" in call_name:
        stage = "CS"
    
    start_slot = 0
    
    for p in params:
        name = p.get("name", "")
        
        if name == "StartSlot":
            start_slot = int(p.get("value", 0))
            
        elif name == "ppSamplers" and "elements" in p:
            elements = p["elements"]
            for i, elem in enumerate(elements):
                sampler_id = elem.get("value", "")
                if sampler_id and sampler_id != "0" and sampler_id.upper() != "NULL":
                    samplers.append({
                        "type": "Sampler",
                        "stage": stage,
                        "slot": start_slot + i,
                        "resourceId": sampler_id,
                    })
    
    return samplers


def parse_uavs_from_params(params, call_name):
    """解析 D3D11 *SetUnorderedAccessViews 的 UAV 绑定"""
    uavs = []
    
    start_slot = 0
    
    for p in params:
        name = p.get("name", "")
        
        if name == "StartSlot" or name == "UAVStartSlot":
            start_slot = int(p.get("value", 0))
            
        elif name == "ppUnorderedAccessViews" and "elements" in p:
            elements = p["elements"]
            for i, elem in enumerate(elements):
                uav_id = elem.get("value", "")
                if uav_id and uav_id != "0" and uav_id.upper() != "NULL":
                    uavs.append({
                        "type": "UAV",
                        "stage": "CS" if "CS" in call_name else "PS",
                        "slot": start_slot + i,
                        "resourceId": uav_id,
                    })
    
    return uavs


def parse_descriptor_sets_from_params(params, descriptor_set_contents=None):
    """解析 Vulkan vkCmdBindDescriptorSets 的描述符集绑定
    
    Args:
        params: 参数列表
        descriptor_set_contents: 预扫描得到的描述符集内容映射表 {set_id -> [bindings]}
    
    Returns:
        list: 描述符集列表，每个包含 bindings（展开的资源）
    """
    if descriptor_set_contents is None:
        descriptor_set_contents = {}
    
    descriptor_sets = []
    
    first_set = 0
    pipeline_bind_point = "GRAPHICS"
    layout_id = ""
    
    for p in params:
        name = p.get("name", "")
        
        if name == "firstSet":
            first_set = int(p.get("value", 0))
            
        elif name == "pipelineBindPoint":
            value = p.get("value", "")
            if "COMPUTE" in value:
                pipeline_bind_point = "COMPUTE"
                
        elif name == "layout":
            layout_id = p.get("value", "")
            
        elif name == "pDescriptorSets" and "elements" in p:
            elements = p["elements"]
            for i, elem in enumerate(elements):
                set_id = elem.get("value", "")
                if set_id and set_id != "0":
                    # 查找该描述符集的具体内容
                    bindings = descriptor_set_contents.get(set_id, [])
                    
                    descriptor_sets.append({
                        "type": "DescriptorSet",
                        "bindPoint": pipeline_bind_point,
                        "setIndex": first_set + i,
                        "resourceId": set_id,
                        "layout": layout_id,
                        "bindings": bindings,  # 展开的资源列表
                    })
    
    return descriptor_sets


def parse_d3d12_descriptor_table_from_params(params):
    """解析 D3D12 SetGraphicsRootDescriptorTable 的描述符表绑定"""
    for p in params:
        name = p.get("name", "")
        
        if name == "RootParameterIndex":
            root_index = int(p.get("value", 0))
            
        elif name == "BaseDescriptor":
            descriptor_handle = p.get("value", "")
            return {
                "type": "DescriptorTable",
                "rootIndex": root_index if 'root_index' in dir() else 0,
                "baseDescriptor": descriptor_handle,
            }
    
    return None


def parse_d3d12_cbv_from_params(params):
    """解析 D3D12 SetGraphicsRootConstantBufferView 的 CBV 绑定"""
    root_index = 0
    buffer_location = ""
    
    for p in params:
        name = p.get("name", "")
        
        if name == "RootParameterIndex":
            root_index = int(p.get("value", 0))
            
        elif name == "BufferLocation":
            buffer_location = p.get("value", "")
    
    if buffer_location:
        return {
            "type": "CBV",
            "stage": "Root",
            "slot": root_index,
            "resourceId": buffer_location,
        }
    
    return None


def parse_pipeline_state_from_related_calls(related_calls):
    """
    从 relatedCalls 字符串列表中解析 Pipeline State 数据
    （向后兼容的旧实现，现在优先使用 parse_pipeline_state_from_binding_records）
    
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
