#!/usr/bin/env python3
"""
XML → 4 页面 Bundle 报告生成器

从 RenderDoc 导出的 XML 文件生成完整的 Bundle 报告，
无需 renderdoc 模块，可独立运行。

支持从 Vulkan RDC 文件中提取 SPIR-V Shader 并转换为 GLSL。

用法:
    py -3 xml_to_bundle.py <xml_file> [-o OUTPUT_DIR] [-n NAME] [--zip ZIP_FILE]

示例:
    py -3 xml_to_bundle.py capture.xml -o output_dir -n "My Capture"
    py -3 xml_to_bundle.py capture.xml --zip capture.zip  # 带缩略图
    py -3 xml_to_bundle.py capture.xml --rdc capture.rdc  # 提取 Vulkan Shaders
    py -3 xml_to_bundle.py capture.xml --rdc capture.rdc --spirv-cross /path/to/spirv-cross
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

    VK_BEGIN_RENDERPASS = {
        "vkCmdBeginRenderPass", "vkCmdBeginRenderPass2", "vkCmdBeginRendering",
    }
    VK_END_RENDERPASS = {
        "vkCmdEndRenderPass", "vkCmdEndRenderPass2", "vkCmdEndRendering",
    }

    def parse(self, xml_path: str) -> Dict:
        """解析 XML 文件，返回标准化数据"""
        tree = ET.parse(xml_path)
        root = tree.getroot()

        driver = self._detect_driver(root)
        draw_calls = []
        textures = []
        buffers = []

        # Vulkan runtime state used to reconstruct per-draw RT bindings.
        image_view_to_image: Dict[str, Dict[str, str]] = {}
        framebuffer_to_views: Dict[str, List[str]] = {}
        active_rt_state = {"color": [], "depth": None}

        for chunk in root.iter("chunk"):
            name = chunk.get("name", "")

            # Draw Calls
            if name in self.D3D11_DRAW_CALLS or name in self.VK_DRAW_CALLS:
                dc = self._parse_draw_call(chunk, name)
                if dc and name in self.VK_DRAW_CALLS:
                    dc["render_targets"] = [
                        {"id": image_id, "slot": slot}
                        for slot, image_id in enumerate(active_rt_state["color"])
                    ]
                    if active_rt_state.get("depth"):
                        dc["depth_target"] = active_rt_state["depth"]
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

            # Vulkan ImageViews (View -> Image mapping)
            elif name == "vkCreateImageView":
                view_info = self._parse_vk_image_view(chunk)
                if view_info:
                    image_view_to_image[view_info["view_id"]] = {
                        "image_id": view_info["image_id"],
                        "aspect": view_info.get("aspect", ""),
                    }

            # Vulkan Framebuffers (Framebuffer -> ImageView[] mapping)
            elif name == "vkCreateFramebuffer":
                fb_info = self._parse_vk_framebuffer(chunk)
                if fb_info:
                    framebuffer_to_views[fb_info["framebuffer_id"]] = fb_info["attachments"]

            # Track active RT state by render-pass boundaries.
            elif name in self.VK_BEGIN_RENDERPASS:
                active_rt_state = self._resolve_active_render_targets(
                    chunk,
                    framebuffer_to_views,
                    image_view_to_image,
                )
            elif name in self.VK_END_RENDERPASS:
                active_rt_state = {"color": [], "depth": None}

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
        event_raw = chunk.get("eventId")
        event_id = int(event_raw) if event_raw and str(event_raw).isdigit() else 0
        if event_id == 0:
            chunk_index_raw = chunk.get("chunkIndex")
            if chunk_index_raw and str(chunk_index_raw).isdigit():
                event_id = int(chunk_index_raw)

        dc = {
            "event_id": event_id,
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

            # 提取 ResourceId (Vulkan Image ID)
            elif child.tag == "ResourceId" and child_name == "Image":
                tex["resource_id"] = child.text or ""

        return tex if tex["width"] > 0 else None

    def _parse_vk_image_view(self, chunk) -> Optional[Dict[str, str]]:
        """解析 Vulkan ImageView，返回 view_id/image_id/aspect。"""
        view_id = ""
        image_id = ""
        aspect = ""

        for child in chunk:
            child_name = child.get("name", "")

            if child.tag == "ResourceId" and child_name in ("View", "view"):
                view_id = (child.text or "").strip()

            if child_name in ("CreateInfo", "pCreateInfo"):
                for sub in child:
                    sub_name = sub.get("name", "")
                    if sub.tag == "ResourceId" and sub_name in ("image", "Image"):
                        image_id = (sub.text or "").strip()
                    elif sub_name == "subresourceRange":
                        for sub_range in sub:
                            if sub_range.get("name", "") == "aspectMask":
                                aspect = sub_range.get("string", "") or (sub_range.text or "")

            if not image_id and child.tag == "ResourceId" and child_name in ("image", "Image"):
                image_id = (child.text or "").strip()

        if not view_id or not image_id:
            return None

        return {
            "view_id": view_id,
            "image_id": image_id,
            "aspect": aspect,
        }

    def _parse_vk_framebuffer(self, chunk) -> Optional[Dict[str, Any]]:
        """解析 Vulkan Framebuffer，返回 framebuffer_id + 附件 view 列表。"""
        framebuffer_id = ""
        attachments: List[str] = []

        for child in chunk:
            child_name = child.get("name", "")
            if child.tag == "ResourceId" and child_name == "Framebuffer":
                framebuffer_id = (child.text or "").strip()
            elif child_name in ("CreateInfo", "pCreateInfo"):
                for sub in child:
                    if sub.get("name", "") == "pAttachments":
                        for rid in sub.findall("./ResourceId"):
                            rid_text = (rid.text or "").strip()
                            if rid_text:
                                attachments.append(rid_text)

        if not framebuffer_id:
            return None

        return {
            "framebuffer_id": framebuffer_id,
            "attachments": attachments,
        }

    def _parse_begin_renderpass_framebuffer(self, chunk) -> str:
        """从 vkCmdBeginRenderPass/vkCmdBeginRenderPass2 chunk 中提取 framebuffer id。"""
        # 常见路径：RenderPassBegin.framebuffer
        for path in (
            "./ResourceId[@name='framebuffer']",
            "./struct[@name='RenderPassBegin']/ResourceId[@name='framebuffer']",
            "./struct[@name='pRenderPassBegin']/ResourceId[@name='framebuffer']",
            ".//ResourceId[@name='framebuffer']",
        ):
            node = chunk.find(path)
            if node is not None and node.text:
                fb_id = node.text.strip()
                if fb_id:
                    return fb_id
        return ""

    def _resolve_active_render_targets(
        self,
        begin_chunk,
        framebuffer_to_views: Dict[str, List[str]],
        image_view_to_image: Dict[str, Dict[str, str]],
    ) -> Dict[str, Any]:
        """基于 begin-renderpass 的 framebuffer 解析当前 color/depth RT 集合。"""
        framebuffer_id = self._parse_begin_renderpass_framebuffer(begin_chunk)
        if not framebuffer_id:
            return {"color": [], "depth": None}

        view_ids = framebuffer_to_views.get(framebuffer_id, [])
        color_images: List[str] = []
        depth_image: Optional[str] = None

        for view_id in view_ids:
            info = image_view_to_image.get(view_id)
            if not info:
                continue

            image_id = str(info.get("image_id", "")).strip()
            if not image_id:
                continue

            aspect = str(info.get("aspect", "")).upper()
            is_depth = "DEPTH" in aspect or "STENCIL" in aspect

            if is_depth:
                if depth_image is None:
                    depth_image = image_id
            elif image_id not in color_images:
                color_images.append(image_id)

        return {
            "color": color_images,
            "depth": depth_image,
        }

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
    parser.add_argument('--zip', dest='zip_file', default=None,
                        help='Path to ZIP file with texture data (for thumbnails)')
    parser.add_argument('--texture-dir', dest='texture_dir', default=None,
                        help=("Directory produced by renderdoccmd export (contains textures.json + PNG). "
                              "When provided, thumbnails are mapped to PNG paths and ZIP-based base64 thumbnails are skipped by default."))
    parser.add_argument('--rdc', dest='rdc_file', default=None,
                        help='Path to RDC file for Vulkan shader extraction (SPIR-V → GLSL)')
    parser.add_argument('--spirv-cross', dest='spirv_cross', default=None,
                        help='Path to spirv-cross executable (auto-detected if not provided)')
    parser.add_argument('--max-thumbnails', type=int, default=50,
                        help='Maximum number of thumbnails to generate (default: 50)')
    parser.add_argument('--thumbnail-size', type=int, default=128,
                        help='Max thumbnail dimension in pixels (default: 128)')
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

        render_targets = []
        for idx, rt in enumerate(dc.get("render_targets", []) or []):
            if isinstance(rt, dict):
                rt_id = rt.get("id", rt.get("resourceId", ""))
                slot = rt.get("slot", idx)
            else:
                rt_id = rt
                slot = idx

            if rt_id in (None, ""):
                continue

            try:
                slot_value = int(slot)
            except (TypeError, ValueError):
                slot_value = idx

            render_targets.append({
                "id": str(rt_id),
                "slot": slot_value,
            })

        if render_targets:
            event["renderTargets"] = render_targets

        depth_target = dc.get("depth_target")
        if depth_target:
            if isinstance(depth_target, dict):
                depth_id = depth_target.get("id", depth_target.get("resourceId", ""))
            else:
                depth_id = depth_target

            if depth_id not in (None, ""):
                event["depthTarget"] = {"id": str(depth_id)}

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


def _quote_url_path(path: str) -> str:
    # Encode spaces/special chars for browser-friendly URLs (file:/// and relative).
    from urllib.parse import quote

    parts = path.replace('\\', '/').split('/')
    return '/'.join(quote(p) for p in parts)


def _id_variants(value: Any) -> List[str]:
    s = '' if value is None else str(value)
    variants = {s}
    try:
        import re
        m = re.search(r'(\d+)$', s)
        if m:
            variants.add(m.group(1))
    except Exception:
        pass
    return list(variants)


def apply_exported_texture_thumbnails(
    textures: List[Dict],
    texture_dir: Path,
    output_dir: Path,
    verbose: bool = False,
) -> int:
    """Apply renderdoccmd export thumbnails (PNG files) onto the textures list.

    Expects <texture_dir>/textures.json + referenced PNG files to exist.
    Sets tex['thumbnail'] to a relative URL when texture_dir is inside output_dir.
    """
    import json

    textures_json = texture_dir / 'textures.json'
    if not textures_json.exists():
        if verbose:
            print(f"      [INFO] export textures.json not found: {textures_json}")
        return 0

    try:
        payload = json.loads(textures_json.read_text(encoding='utf-8'))
        entries = payload.get('textures', []) if isinstance(payload, dict) else []
    except Exception as e:
        if verbose:
            print(f"      [WARN] Failed to read textures.json: {e}")
        return 0

    try:
        rel_prefix = texture_dir.resolve().relative_to(output_dir.resolve()).as_posix()
    except Exception:
        # Not under report dir; fallback to absolute file URI.
        rel_prefix = texture_dir.resolve().as_uri()

    id_to_file: Dict[str, str] = {}
    for e in entries:
        if not isinstance(e, dict):
            continue
        tid = e.get('id')
        fname = e.get('file')
        if tid is None or not fname:
            continue
        if not (texture_dir / fname).exists():
            continue
        for key in _id_variants(tid):
            if key and key not in id_to_file:
                id_to_file[key] = fname

    updated = 0
    for tex in textures:
        if not isinstance(tex, dict):
            continue
        fname = None
        for key in _id_variants(tex.get('id')):
            fname = id_to_file.get(key)
            if fname:
                break
        if not fname:
            continue

        # Use browser-friendly, portable URL.
        rel_prefix_norm = rel_prefix
        if rel_prefix_norm in ('', '.'):
            thumb = _quote_url_path(Path(fname).as_posix())
        else:
            thumb = rel_prefix_norm.rstrip('/') + '/' + _quote_url_path(Path(fname).as_posix())

        tex['thumbnail'] = thumb
        updated += 1

    if verbose:
        print(f"      [INFO] Mapped {updated} thumbnails from renderdoccmd export")
    return updated


def generate_thumbnails_from_zip(
    xml_path: Path,
    zip_path: Optional[Path],
    textures: List[Dict],
    max_count: int = 50,
    max_size: int = 128,
    verbose: bool = False
) -> int:
    """
    从 ZIP 文件生成缩略图并合并到纹理列表
    
    Args:
        xml_path: XML 文件路径
        zip_path: ZIP 文件路径 (None 则自动检测)
        textures: 纹理列表 (将被原地修改)
        max_count: 最大缩略图数量
        max_size: 缩略图最大尺寸
        verbose: 详细输出
    
    Returns:
        成功生成的缩略图数量
    """
    # 尝试导入 ThumbnailGenerator
    try:
        from thumbnail_generator import ThumbnailGenerator
    except ImportError as e:
        if verbose:
            print(f"      [WARN] thumbnail_generator not available: {e}")
            import traceback
            traceback.print_exc()
        return 0
    
    # 确定 ZIP 路径
    if zip_path is None:
        # 自动检测同名 ZIP 文件
        auto_zip = xml_path.with_suffix('.zip')
        if auto_zip.exists():
            zip_path = auto_zip
            if verbose:
                print(f"      [INFO] Auto-detected ZIP: {zip_path.name}")
        else:
            if verbose:
                print("      [INFO] No ZIP file found, thumbnails will be empty")
            return 0
    else:
        zip_path = Path(zip_path)
        if not zip_path.exists():
            if verbose:
                print(f"      [WARN] ZIP file not found: {zip_path}")
            return 0
    
    # 初始化生成器
    try:
        generator = ThumbnailGenerator(str(xml_path), str(zip_path))
        available, reason = generator.is_available()
        if not available:
            if verbose:
                print(f"      [WARN] ThumbnailGenerator not available: {reason}")
            return 0
    except Exception as e:
        if verbose:
            print(f"      [WARN] Failed to init ThumbnailGenerator: {e}")
        return 0
    
    # 生成缩略图
    try:
        results = generator.generate_thumbnails(
            max_count=max_count,
            max_size=max_size,
            min_texture_size=32,  # 跳过太小的纹理
            skip_formats=["DEPTH", "STENCIL", "D32", "D24", "D16"]
        )
    except Exception as e:
        if verbose:
            print(f"      [WARN] Thumbnail generation failed: {e}")
        return 0
    
    if not results:
        return 0
    
    # 构建 resource_id → base64 映射 (key 统一为字符串)
    thumbnail_map = {}
    for r in results:
        if r.success and r.base64_data:
            thumbnail_map[str(r.resource_id)] = r.base64_data
    
    if verbose:
        print(f"      [INFO] thumbnail_map has {len(thumbnail_map)} entries")
    
    # 合并到纹理列表
    count = 0
    for tex in textures:
        tex_id = str(tex.get("id", ""))
        if tex_id in thumbnail_map:
            tex["thumbnail"] = thumbnail_map[tex_id]
            count += 1
    
    return count


def extract_vulkan_shaders_from_rdc(
    rdc_path: Path,
    spirv_cross_path: Optional[str] = None,
    verbose: bool = False
) -> List[Dict]:
    """
    从 Vulkan RDC 文件中提取 SPIR-V Shaders 并转换为 GLSL
    
    Args:
        rdc_path: RDC 文件路径
        spirv_cross_path: spirv-cross 可执行文件路径 (可选)
        verbose: 详细输出
    
    Returns:
        Shader 字典列表，格式与 ReportBundleGenerator.shaders 兼容
    """
    import shutil
    import subprocess
    import tempfile
    import hashlib
    
    # 尝试导入 RDC 解析器
    try:
        from parsers.rdc_parser import RDCParser
        from parsers.shader_extractor import ShaderExtractor as SPIRVExtractor
    except ImportError:
        if verbose:
            print("      [WARN] parsers module not available, skipping shader extraction")
        return []
    
    # 查找 spirv-cross
    spirv_cross = spirv_cross_path
    if not spirv_cross:
        # 自动检测
        spirv_cross = shutil.which("spirv-cross")
        if not spirv_cross:
            # 尝试常见路径
            common_paths = [
                r"C:\VulkanSDK\1.3.290.0\Bin\spirv-cross.exe",
                r"D:\VulkanSDK\1.3.290.0\Bin\spirv-cross.exe",
                r"C:\Program Files\RenderDoc\plugins\spirv\spirv-cross.exe",
                "/usr/bin/spirv-cross",
                "/usr/local/bin/spirv-cross",
            ]
            for p in common_paths:
                if Path(p).exists():
                    spirv_cross = p
                    break
    
    if verbose:
        if spirv_cross:
            print(f"      [INFO] spirv-cross: {spirv_cross}")
        else:
            print("      [WARN] spirv-cross not found, GLSL conversion disabled")
    
    # 解析 RDC 文件
    try:
        rdc_parser = RDCParser(str(rdc_path))
        rdc_parser.parse()
        
        # 检查是否是 Vulkan 捕获
        if rdc_parser.driver != "Vulkan":
            if verbose:
                print(f"      [INFO] RDC is {rdc_parser.driver}, not Vulkan. Skipping shader extraction.")
            return []
        
        # 获取 FrameCapture 数据
        fc_data = rdc_parser.section_parser.get_frame_capture_data()
        if not fc_data:
            if verbose:
                print("      [WARN] No FrameCapture data in RDC")
            return []
        
        # 提取 SPIR-V shaders
        spirv_extractor = SPIRVExtractor()
        spirv_shaders = spirv_extractor.extract_from_chunks(fc_data, rdc_parser.chunks)
        
        if verbose:
            print(f"      [INFO] Extracted {len(spirv_shaders)} SPIR-V shaders")
        
    except Exception as e:
        if verbose:
            print(f"      [WARN] RDC parsing failed: {e}")
        return []
    
    # 转换为 Bundle 格式
    shaders = []
    for idx, spirv_shader in enumerate(spirv_shaders):
        # 生成 shader ID
        shader_hash = hashlib.sha1(spirv_shader.spirv_data).hexdigest()[:12]
        shader_id = f"SPIRV_{shader_hash}"
        
        # 尝试转换为 GLSL
        glsl_source = ""
        if spirv_cross and spirv_shader.spirv_data:
            try:
                with tempfile.NamedTemporaryFile(suffix=".spv", delete=False) as tmp:
                    tmp.write(spirv_shader.spirv_data)
                    tmp_path = tmp.name
                
                result = subprocess.run(
                    [spirv_cross, tmp_path, "--vulkan-semantics"],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                
                if result.returncode == 0:
                    glsl_source = result.stdout
                elif verbose:
                    print(f"      [WARN] spirv-cross failed for shader {idx}: {result.stderr[:100]}")
                
                # 清理临时文件
                Path(tmp_path).unlink(missing_ok=True)
                
            except subprocess.TimeoutExpired:
                if verbose:
                    print(f"      [WARN] spirv-cross timeout for shader {idx}")
            except Exception as e:
                if verbose:
                    print(f"      [WARN] GLSL conversion failed: {e}")
        
        # 构建 shader 字典
        shader = {
            "id": shader_id,
            "name": spirv_shader.stage_name or f"Shader_{idx}",
            "type": spirv_shader.stage_name[:2].upper() if spirv_shader.stage_name else "VS",
            "stage": spirv_shader.stage_name or "Unknown",
            "entry_point": "main",
            "encoding": "SPIR-V",
            "source_code": glsl_source or f"// SPIR-V binary ({spirv_shader.code_size} bytes)\n// spirv-cross required for GLSL conversion",
            "code_size": spirv_shader.code_size,
            "has_debug_info": False,
            "resource_id": str(spirv_shader.resource_id),
        }
        shaders.append(shader)
    
    return shaders


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
    # 生成缩略图 (可选)
    # ========================================================================
    
    zip_path = Path(args.zip_file) if args.zip_file else None

    exported_count = 0
    if args.texture_dir:
        exported_count = apply_exported_texture_thumbnails(
            textures=textures,
            texture_dir=Path(args.texture_dir),
            output_dir=output_dir,
            verbose=args.verbose,
        )

    if exported_count > 0:
        thumbnail_count = exported_count
    else:
        thumbnail_count = generate_thumbnails_from_zip(
            xml_path=xml_path,
            zip_path=zip_path,
            textures=textures,
            max_count=args.max_thumbnails,
            max_size=args.thumbnail_size,
            verbose=args.verbose
        )

    if thumbnail_count > 0:
        print(f"      Thumbnails: {thumbnail_count} generated")
    else:
        print("      [INFO] Thumbnails: 0 (textures page will show placeholder previews)")
        if args.texture_dir:
            print("      [HINT] Check --texture-dir and textures.json output from renderdoccmd export")
        elif args.zip_file:
            print("      [HINT] Check ZIP contents and thumbnail_generator availability")
        else:
            print("      [HINT] Provide --texture-dir <dir> or --zip <capture.zip> to enable thumbnails")
    
    # ========================================================================
    # 提取 Vulkan Shaders (可选)
    # ========================================================================
    
    shaders = []
    rdc_path = Path(args.rdc_file) if args.rdc_file else None
    
    # 自动检测同名 RDC 文件（仅 Vulkan 捕获）
    if rdc_path is None and driver == "Vulkan":
        auto_rdc = xml_path.with_suffix('.rdc')
        if auto_rdc.exists():
            rdc_path = auto_rdc
            if args.verbose:
                print(f"      [INFO] Auto-detected RDC: {rdc_path.name}")
    
    if rdc_path and rdc_path.exists():
        print(f"      Extracting Vulkan shaders from: {rdc_path.name}")
        shaders = extract_vulkan_shaders_from_rdc(
            rdc_path=rdc_path,
            spirv_cross_path=args.spirv_cross,
            verbose=args.verbose
        )
        if shaders:
            print(f"      Shaders: {len(shaders)} extracted")
            glsl_count = sum(1 for s in shaders if "SPIR-V binary" not in s.get("source_code", ""))
            if glsl_count > 0:
                print(f"      GLSL converted: {glsl_count}")
        else:
            print("      [INFO] Shaders: 0 (no extractable shader source in this capture)")
            print("      [HINT] Use a capture with shader debug/source data and configure shader tools")
    elif args.rdc_file:
        print(f"      [WARN] RDC file not found: {args.rdc_file}")
    elif driver == "Vulkan":
        print("      [INFO] Shaders: 0 (no RDC input, shaders page will stay empty)")
        print("      [HINT] Provide --rdc <capture.rdc> to enable shader extraction")
    
    # ========================================================================
    # 生成 Bundle 报告
    # ========================================================================
    
    print("[3/3] Generating bundle report...")
    
    generator = ReportBundleGenerator(str(output_dir), capture_name)
    
    # 设置数据
    generator.events = events
    generator.textures = textures
    generator.shaders = shaders
    
    # 更新统计
    generator.stats.update({
        "total_textures": len(textures),
        "total_events": len(events),
        "total_shaders": len(shaders),
        "draw_calls": draw_count,
        "dispatch_calls": dispatch_count,
        "clear_calls": clear_count,
        "vram_usage": vram_total,
        "issues_count": 0,
        "issues": [],
    })
    
    # 生成所有页面
    generator.generate_all()

    thumbnail_attached = sum(1 for t in textures if t.get("thumbnail"))
    print(f"      Data quality: thumbnails {thumbnail_attached}/{len(textures)}, shaders {len(shaders)}")
    if thumbnail_attached == 0 and len(textures) > 0:
        print("      [NOTE] textures.html placeholders are expected without extracted thumbnails")
    if len(shaders) == 0:
        print("      [NOTE] shaders.html empty state is expected when shader extraction yields no results")

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
