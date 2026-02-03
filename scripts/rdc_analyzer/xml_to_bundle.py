#!/usr/bin/env python3
"""
XML → 4 页面 Bundle 报告生成器

从 RenderDoc 导出的 XML 文件生成完整的 Bundle 报告，
无需 renderdoc 模块，可独立运行。

用法:
    py -3 xml_to_bundle.py <xml_file> [-o OUTPUT_DIR] [-n NAME]

示例:
    py -3 xml_to_bundle.py capture.xml -o output_dir -n "My Capture"
"""

import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

# 确保脚本目录和父目录在路径中
SCRIPT_DIR = Path(__file__).parent
SCRIPTS_DIR = SCRIPT_DIR.parent  # scripts/
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

# 直接导入解析器（避免 package 相对导入问题）
import xml.etree.ElementTree as ET
from report_bundle_generator import ReportBundleGenerator


class SimpleXmlParser:
    """简化的 XML 解析器，独立于 package 结构"""
    
    # D3D11 Draw Calls
    D3D11_DRAW_CALLS = {
        "ID3D11DeviceContext::DrawIndexed",
        "ID3D11DeviceContext::Draw",
        "ID3D11DeviceContext::DrawIndexedInstanced",
        "ID3D11DeviceContext::DrawInstanced",
        "ID3D11DeviceContext::DrawAuto",
        "ID3D11DeviceContext::DrawIndexedInstancedIndirect",
        "ID3D11DeviceContext::DrawInstancedIndirect",
    }
    
    # Vulkan Draw/Dispatch Calls
    VK_DRAW_CALLS = {
        "vkCmdDraw", "vkCmdDrawIndexed", "vkCmdDrawIndirect", 
        "vkCmdDrawIndexedIndirect", "vkCmdDrawIndirectCount",
        "vkCmdDrawIndexedIndirectCount", "vkCmdDrawMeshTasksEXT",
        "vkCmdDrawMeshTasksIndirectEXT", "vkCmdDrawMeshTasksIndirectCountEXT",
    }
    VK_DISPATCH_CALLS = {
        "vkCmdDispatch", "vkCmdDispatchIndirect", "vkCmdDispatchBase",
    }
    
    def parse(self, xml_path: str) -> Dict:
        """解析 XML 文件，返回标准化数据"""
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        driver = self._detect_driver(root)
        draw_calls = []
        textures = []
        buffers = []
        
        for chunk in root.iter("chunk"):
            name = chunk.get("name", "")
            
            # Draw Calls
            if name in self.D3D11_DRAW_CALLS or name in self.VK_DRAW_CALLS:
                dc = self._parse_draw_call(chunk, name)
                if dc:
                    draw_calls.append(dc)
            elif name in self.VK_DISPATCH_CALLS:
                dc = self._parse_draw_call(chunk, name, is_dispatch=True)
                if dc:
                    draw_calls.append(dc)
            
            # D3D11 Textures
            elif name == "ID3D11Device::CreateTexture2D":
                tex = self._parse_d3d11_texture(chunk)
                if tex:
                    textures.append(tex)
            
            # Vulkan Images
            elif name == "vkCreateImage":
                tex = self._parse_vk_image(chunk)
                if tex:
                    textures.append(tex)
            
            # Vulkan Buffers
            elif name == "vkCreateBuffer":
                buf = self._parse_vk_buffer(chunk)
                if buf:
                    buffers.append(buf)
        
        return {
            "driver": driver,
            "draw_calls": draw_calls,
            "textures": textures,
            "buffers": buffers,
        }
    
    def _detect_driver(self, root) -> str:
        """检测图形 API 驱动类型"""
        for chunk in root.iter("chunk"):
            name = chunk.get("name", "")
            if name.startswith("ID3D11"):
                return "D3D11"
            if name.startswith("ID3D12"):
                return "D3D12"
            if name.startswith("vk"):
                return "Vulkan"
            if name.startswith("gl"):
                return "OpenGL"
        return "Unknown"
    
    def _parse_draw_call(self, chunk, name, is_dispatch=False) -> Optional[Dict]:
        """解析 Draw/Dispatch Call"""
        dc = {
            "event_id": int(chunk.get("eventId", 0)),
            "name": name,
            "index_count": 0,
            "vertex_count": 0,
            "instance_count": 1,
            "marker": "",
            "is_dispatch": is_dispatch,
        }
        
        for child in chunk:
            child_name = child.get("name", "")
            text = child.text or ""
            
            # D3D11 style (PascalCase)
            if child_name == "IndexCount":
                dc["index_count"] = int(text) if text.isdigit() else 0
            elif child_name == "VertexCount":
                dc["vertex_count"] = int(text) if text.isdigit() else 0
            elif child_name == "InstanceCount":
                dc["instance_count"] = int(text) if text.isdigit() else 1
            
            # Vulkan style (camelCase)
            elif child_name == "indexCount":
                dc["index_count"] = int(text) if text.isdigit() else 0
            elif child_name == "vertexCount":
                dc["vertex_count"] = int(text) if text.isdigit() else 0
            elif child_name == "instanceCount":
                dc["instance_count"] = int(text) if text.isdigit() else 1
        
        return dc
    
    def _parse_d3d11_texture(self, chunk) -> Optional[Dict]:
        """解析 D3D11 纹理"""
        tex = {
            "resource_id": chunk.get("resourceId", ""),
            "name": "",
            "width": 0,
            "height": 0,
            "depth": 1,
            "format": "",
            "mip_levels": 1,
            "array_size": 1,
        }
        
        for child in chunk:
            name = child.get("name", "")
            text = child.text or ""
            
            if name == "Width":
                tex["width"] = int(text) if text.isdigit() else 0
            elif name == "Height":
                tex["height"] = int(text) if text.isdigit() else 0
            elif name == "Format":
                tex["format"] = text
            elif name == "MipLevels":
                tex["mip_levels"] = int(text) if text.isdigit() else 1
            elif name == "ArraySize":
                tex["array_size"] = int(text) if text.isdigit() else 1
        
        return tex if tex["width"] > 0 else None
    
    def _parse_vk_image(self, chunk) -> Optional[Dict]:
        """解析 Vulkan Image"""
        tex = {
            "resource_id": "",
            "name": "",
            "width": 0,
            "height": 0,
            "depth": 1,
            "format": "",
            "mip_levels": 1,
            "array_size": 1,
        }
        
        # 查找 pCreateInfo 或直接的子元素
        for child in chunk:
            child_name = child.get("name", "")
            
            if child_name in ("pCreateInfo", "CreateInfo"):
                # 嵌套结构
                for sub in child:
                    sub_name = sub.get("name", "")
                    if sub_name == "extent":
                        for ext in sub:
                            ext_name = ext.get("name", "")
                            text = ext.text or ""
                            if ext_name == "width":
                                tex["width"] = int(text) if text.isdigit() else 0
                            elif ext_name == "height":
                                tex["height"] = int(text) if text.isdigit() else 0
                            elif ext_name == "depth":
                                tex["depth"] = int(text) if text.isdigit() else 1
                    elif sub_name == "format":
                        tex["format"] = sub.text or ""
                    elif sub_name == "mipLevels":
                        tex["mip_levels"] = int(sub.text or "1")
                    elif sub_name == "arrayLayers":
                        tex["array_size"] = int(sub.text or "1")
            
            # 直接子元素（平铺结构）
            elif child_name == "format":
                tex["format"] = child.text or ""
            elif child_name == "extent":
                for ext in child:
                    ext_name = ext.get("name", "")
                    text = ext.text or ""
                    if ext_name == "width":
                        tex["width"] = int(text) if text.isdigit() else 0
                    elif ext_name == "height":
                        tex["height"] = int(text) if text.isdigit() else 0
        
        return tex if tex["width"] > 0 else None
    
    def _parse_vk_buffer(self, chunk) -> Optional[Dict]:
        """解析 Vulkan Buffer"""
        buf = {
            "resource_id": "",
            "size": 0,
            "usage": "",
        }
        
        for child in chunk:
            child_name = child.get("name", "")
            if child_name in ("pCreateInfo", "CreateInfo"):
                for sub in child:
                    sub_name = sub.get("name", "")
                    if sub_name == "size":
                        buf["size"] = int(sub.text or "0")
                    elif sub_name == "usage":
                        buf["usage"] = sub.text or ""
            elif child_name == "size":
                buf["size"] = int(child.text or "0")
        
        return buf if buf["size"] > 0 else None


def parse_args():
    parser = argparse.ArgumentParser(
        description='Generate HTML report bundle from RenderDoc XML export'
    )
    parser.add_argument('xml_file', help='Path to XML file exported by renderdoccmd')
    parser.add_argument('-o', '--output', default=None,
                        help='Output directory (default: <xml_name>_bundle)')
    parser.add_argument('-n', '--name', default=None,
                        help='Capture name for report title')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Verbose output')
    return parser.parse_args()


def xml_to_bundle_events_dict(draw_calls: List[Dict]) -> List[Dict]:
    """
    将 SimpleXmlParser 的 draw_calls (dict 列表) 转换为 ReportBundleGenerator 的 events 格式
    """
    events = []
    
    for dc in draw_calls:
        # 判断事件类型
        event_type = "Draw"
        api_name = dc.get("name", "Unknown")
        
        if dc.get("is_dispatch", False) or 'dispatch' in api_name.lower():
            event_type = "Dispatch"
        elif 'clear' in api_name.lower():
            event_type = "Clear"
        
        # 构建事件数据
        event = {
            "eid": dc.get("event_id", 0),
            "name": api_name,
            "type": event_type,
            "depth": 0,
            "indices": dc.get("index_count", 0),
            "vertices": dc.get("vertex_count", 0),
            "instances": dc.get("instance_count", 1),
            "marker": dc.get("marker", ""),
        }
        events.append(event)
    
    return events


def xml_to_bundle_textures_dict(textures_raw: List[Dict]) -> List[Dict]:
    """
    将 SimpleXmlParser 的 textures (dict 列表) 转换为 ReportBundleGenerator 的 textures 格式
    """
    textures = []
    
    for idx, res in enumerate(textures_raw):
        width = res.get("width", 0)
        height = res.get("height", 0)
        
        if width == 0 or height == 0:
            continue
        
        tex = {
            "id": res.get("resource_id", "") or str(idx),
            "name": res.get("name", "") or f"Texture_{idx}",
            "width": width,
            "height": height,
            "depth": res.get("depth", 1),
            "format": res.get("format", "Unknown"),
            "mips": res.get("mip_levels", 1),
            "array_size": res.get("array_size", 1),
            "sample_count": 1,
            "size_bytes": 0,
            "thumbnail": "",  # XML 无法提供缩略图
            "usage": [],
        }
        
        # 估算大小
        bpp = estimate_bpp(tex["format"])
        tex["size_bytes"] = int(width * height * tex["depth"] * tex["array_size"] * bpp)
        
        textures.append(tex)
    
    return textures


def estimate_bpp(format_str: str) -> int:
    """根据格式字符串估算每像素字节数"""
    fmt = format_str.upper()
    
    if 'R32G32B32A32' in fmt:
        return 16
    if 'R16G16B16A16' in fmt or 'R32G32' in fmt:
        return 8
    if 'R8G8B8A8' in fmt or 'B8G8R8A8' in fmt or 'R32' in fmt or 'R16G16' in fmt:
        return 4
    if 'R16' in fmt or 'R8G8' in fmt:
        return 2
    if 'BC1' in fmt or 'DXT1' in fmt:
        return 0.5  # 8 bytes per 4x4 block
    if 'BC' in fmt or 'DXT' in fmt or 'ASTC' in fmt:
        return 1  # Compressed formats ~1 bpp average
    if 'D32' in fmt or 'D24' in fmt:
        return 4
    if 'D16' in fmt:
        return 2
    
    return 4  # 默认 RGBA8


def main():
    args = parse_args()
    
    xml_path = Path(args.xml_file)
    if not xml_path.exists():
        print(f"[ERROR] XML file not found: {xml_path}")
        sys.exit(1)
    
    # 确定输出目录和名称
    capture_name = args.name or xml_path.stem
    output_dir = Path(args.output) if args.output else xml_path.parent / f"{xml_path.stem}_bundle"
    
    print("=" * 60)
    print("XML → Bundle Report Generator")
    print("=" * 60)
    print(f"[*] Input:  {xml_path}")
    print(f"[*] Output: {output_dir}")
    print(f"[*] Name:   {capture_name}")
    print()
    
    # ========================================================================
    # 解析 XML
    # ========================================================================
    
    print("[1/3] Parsing XML file...")
    parser = SimpleXmlParser()
    data = parser.parse(str(xml_path))
    
    draw_calls = data.get("draw_calls", [])
    textures_raw = data.get("textures", [])
    buffers = data.get("buffers", [])
    driver = data.get("driver", "Unknown")
    
    print(f"      Driver: {driver}")
    print(f"      Draw Calls: {len(draw_calls)}")
    print(f"      Textures: {len(textures_raw)}")
    print(f"      Buffers: {len(buffers)}")
    
    # ========================================================================
    # 转换为 Bundle 格式
    # ========================================================================
    
    print("[2/3] Converting to bundle format...")
    
    events = xml_to_bundle_events_dict(draw_calls)
    textures = xml_to_bundle_textures_dict(textures_raw)
    
    # 统计
    dispatch_count = sum(1 for e in events if e["type"] == "Dispatch")
    clear_count = sum(1 for e in events if e["type"] == "Clear")
    draw_count = len(events) - dispatch_count - clear_count
    
    vram_total = sum(t["size_bytes"] for t in textures)
    
    print(f"      Events: {len(events)} (Draw: {draw_count}, Dispatch: {dispatch_count}, Clear: {clear_count})")
    print(f"      Textures: {len(textures)}")
    print(f"      Est. VRAM: {vram_total / (1024*1024):.1f} MB")
    
    # ========================================================================
    # 生成 Bundle 报告
    # ========================================================================
    
    print("[3/3] Generating bundle report...")
    
    generator = ReportBundleGenerator(str(output_dir), capture_name)
    
    # 设置数据
    generator.events = events
    generator.textures = textures
    generator.shaders = []  # XML 通常不含 shader 源码
    
    # 更新统计
    generator.stats.update({
        "total_textures": len(textures),
        "total_events": len(events),
        "total_shaders": 0,
        "draw_calls": draw_count,
        "dispatch_calls": dispatch_count,
        "clear_calls": clear_count,
        "vram_usage": vram_total,
        "issues_count": 0,
        "issues": [],
    })
    
    # 生成所有页面
    generator.generate_all()
    
    print()
    print("=" * 60)
    print("Bundle Report Generated Successfully!")
    print("=" * 60)
    print(f"  Output: {output_dir}")
    print(f"  Pages:")
    print(f"    - index.html")
    print(f"    - events.html")
    print(f"    - textures.html")
    print(f"    - shaders.html")
    print()
    print(f"  Open: file:///{output_dir}/index.html")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
