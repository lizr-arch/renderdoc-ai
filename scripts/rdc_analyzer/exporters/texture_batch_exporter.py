#!/usr/bin/env python3
"""
texture_batch_exporter.py - 纹理批量导出引擎

提供统一接口，支持两种模式：
1. RDC 直接回放模式（需要 GPU + renderdoc.pyd）
2. XML+ZIP 离线模式（无需 GPU，但需预转换）

Author: RenderDoc Mali Analyzer Project
Version: 1.0.0
"""

import json
import re
import sys
import zipfile
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Iterator, Tuple, Callable

# 尝试导入解码器
try:
    from decoders import decode_texture, save_as_png, get_supported_formats, TextureDecodeError
    DECODER_AVAILABLE = True
except ImportError:
    try:
        # 从上级目录导入
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from decoders import decode_texture, save_as_png, get_supported_formats, TextureDecodeError
        DECODER_AVAILABLE = True
    except ImportError:
        DECODER_AVAILABLE = False

# 尝试导入 D3D11 解析器（使用直接文件导入避免包冲突）
D3D11_PARSER_AVAILABLE = False
try:
    from parsers.d3d11_texture_parser import (
        parse_d3d11_xml,
        detect_api_type,
        D3D11TextureInfo,
    )
    D3D11_PARSER_AVAILABLE = True
except ImportError:
    # 尝试直接文件导入
    try:
        import importlib.util
        _d3d11_parser_path = Path(__file__).parent.parent / "parsers" / "d3d11_texture_parser.py"
        if _d3d11_parser_path.exists():
            _spec = importlib.util.spec_from_file_location("d3d11_texture_parser", _d3d11_parser_path)
            _d3d11_module = importlib.util.module_from_spec(_spec)
            _spec.loader.exec_module(_d3d11_module)
            parse_d3d11_xml = _d3d11_module.parse_d3d11_xml
            detect_api_type = _d3d11_module.detect_api_type
            D3D11TextureInfo = _d3d11_module.D3D11TextureInfo
            D3D11_PARSER_AVAILABLE = True
    except Exception:
        pass

# 尝试导入 renderdoc
try:
    import renderdoc as rd
    HAS_RENDERDOC = True
except ImportError:
    HAS_RENDERDOC = False


@dataclass
class TextureInfo:
    """纹理元数据"""
    resource_id: int
    width: int
    height: int
    depth: int = 1
    format: str = "UNKNOWN"
    mip_levels: int = 1
    array_layers: int = 1
    
    # 提取相关
    buffer_index: Optional[int] = None
    buffer_offset: int = 0
    data_size: int = 0


@dataclass 
class ExportResult:
    """单个纹理导出结果"""
    texture: TextureInfo
    success: bool
    png_path: Optional[Path] = None
    bin_path: Optional[Path] = None
    error: Optional[str] = None


@dataclass
class BatchExportSummary:
    """批量导出汇总"""
    total: int = 0
    success: int = 0
    failed: int = 0
    skipped: int = 0
    results: List[ExportResult] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "total": self.total,
            "success": self.success,
            "failed": self.failed,
            "skipped": self.skipped,
            "textures": [
                {
                    "resource_id": r.texture.resource_id,
                    "width": r.texture.width,
                    "height": r.texture.height,
                    "format": r.texture.format,
                    "success": r.success,
                    "png": str(r.png_path) if r.png_path else None,
                    "bin": str(r.bin_path) if r.bin_path else None,
                    "error": r.error
                }
                for r in self.results
            ]
        }


def select_textures_for_export(
    textures: List[TextureInfo],
    limit: Optional[int]
) -> List[TextureInfo]:
    """按尺寸优先选择纹理（面积大优先，resource_id 小优先）"""
    if limit is None or limit <= 0:
        return list(textures)

    ordered = sorted(
        textures,
        key=lambda t: (-(t.width * t.height), t.resource_id),
    )
    return ordered[:limit]


def tighten_rows_by_pitch(
    raw: bytes,
    width: int,
    height: int,
    row_pitch: int,
    fmt: str
) -> bytes:
    """去除行 padding（最小实现：RGBA8 行宽 = width * 4）"""
    if row_pitch <= 0:
        return raw

    row_bytes = int(width * 4)
    return b"".join(
        raw[i * row_pitch : i * row_pitch + row_bytes]
        for i in range(height)
    )


class BaseExportEngine(ABC):
    """导出引擎基类"""
    
    def __init__(self, source_path: Path):
        self.source_path = source_path
        self.textures: Dict[int, TextureInfo] = {}
    
    @abstractmethod
    def scan_textures(self) -> List[TextureInfo]:
        """扫描所有可导出的纹理"""
        pass
    
    @abstractmethod
    def extract_texture_data(self, texture: TextureInfo) -> Optional[bytes]:
        """提取单个纹理的原始数据"""
        pass
    
    @abstractmethod
    def close(self):
        """释放资源"""
        pass
    
    def export_all(
        self,
        output_dir: Path,
        save_png: bool = True,
        save_bin: bool = False,
        filter_pattern: Optional[str] = None,
        max_count: int = -1,
        progress_callback: Optional[Callable[[int, int, TextureInfo], None]] = None,
        limit: Optional[int] = None
    ) -> BatchExportSummary:
        """
        批量导出所有纹理
        
        Args:
            output_dir: 输出目录
            save_png: 是否保存 PNG
            save_bin: 是否保存原始二进制
            filter_pattern: 正则过滤模式 (匹配格式名或尺寸)
            max_count: 最大导出数量
            progress_callback: 进度回调 (current, total, texture)
            limit: 优先导出数量上限（按面积降序、resource_id 升序）
        
        Returns:
            导出汇总
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 扫描纹理
        textures = self.scan_textures()
        
        # 应用过滤
        if filter_pattern:
            pattern = re.compile(filter_pattern, re.IGNORECASE)
            textures = [
                t for t in textures
                if pattern.search(t.format) or pattern.search(f"{t.width}x{t.height}")
            ]

        # 限制数量（按面积排序优先）
        textures = select_textures_for_export(textures, limit)
        
        # 限制数量
        if max_count > 0:
            textures = textures[:max_count]
        
        summary = BatchExportSummary(total=len(textures))
        
        for i, tex in enumerate(textures):
            if progress_callback:
                progress_callback(i + 1, len(textures), tex)
            
            result = self._export_single(tex, output_dir, save_png, save_bin)
            summary.results.append(result)
            
            if result.success:
                summary.success += 1
            elif result.error and "skip" in result.error.lower():
                summary.skipped += 1
            else:
                summary.failed += 1
        
        return summary
    
    def _export_single(
        self,
        texture: TextureInfo,
        output_dir: Path,
        save_png: bool,
        save_bin: bool
    ) -> ExportResult:
        """导出单个纹理"""
        result = ExportResult(texture=texture, success=False)
        
        try:
            # 提取原始数据
            raw_data = self.extract_texture_data(texture)
            if raw_data is None:
                result.error = "Failed to extract texture data"
                return result
            
            # 构建文件名
            base_name = f"tex_{texture.resource_id}_{texture.width}x{texture.height}"
            
            # 保存原始二进制
            if save_bin:
                bin_path = output_dir / f"{base_name}.bin"
                with open(bin_path, 'wb') as f:
                    f.write(raw_data)
                result.bin_path = bin_path
            
            # 解码并保存 PNG
            if save_png:
                if not DECODER_AVAILABLE:
                    result.error = "Decoder not available"
                    return result
                
                try:
                    rgba = decode_texture(
                        raw_data,
                        texture.width,
                        texture.height,
                        texture.format
                    )
                    png_path = output_dir / f"{base_name}.png"
                    save_as_png(rgba, texture.width, texture.height, str(png_path))
                    result.png_path = png_path
                    result.success = True
                except TextureDecodeError as e:
                    result.error = f"Decode failed: {e}"
                    # 如果保存了 bin，也算部分成功
                    if result.bin_path:
                        result.success = True
            else:
                # 只保存 bin 的情况
                result.success = result.bin_path is not None
            
        except Exception as e:
            result.error = str(e)
        
        return result


class XmlZipExportEngine(BaseExportEngine):
    """XML+ZIP 离线导出引擎"""
    
    def __init__(self, xml_path: Path, zip_path: Optional[Path] = None):
        super().__init__(xml_path)
        self.xml_path = xml_path
        
        # 推断 ZIP 路径
        if zip_path is None:
            zip_path = xml_path.parent / xml_path.name.replace('.xml', '')
            if not zip_path.exists():
                zip_path = xml_path.with_suffix('')
        
        self.zip_path = zip_path
        self._zip_file: Optional[zipfile.ZipFile] = None
        
        # 解析数据
        self._images: Dict[int, TextureInfo] = {}
        self._bindings: Dict[int, Tuple[int, int]] = {}  # image_id -> (memory_id, offset)
        self._initial_contents: Dict[int, Tuple[int, int]] = {}  # memory_id -> (buffer_index, size)
    
    def _parse_xml(self):
        """解析 XML 文件"""
        print(f"  Parsing XML: {self.xml_path.name}...")
        
        with open(self.xml_path, 'rb') as f:
            data = f.read()
        
        # 解析 vkCreateImage
        create_pattern = rb'<chunk[^>]+name="vkCreateImage"[^>]*>(.*?)</chunk>'
        for match in re.finditer(create_pattern, data, re.DOTALL):
            chunk = match.group(1)
            
            id_match = re.search(rb'<ResourceId[^>]+typename="VkImage"[^>]*>(\d+)</ResourceId>', chunk)
            if not id_match:
                continue
            
            img_id = int(id_match.group(1))
            w_match = re.search(rb'<uint[^>]+name="width"[^>]*>(\d+)</uint>', chunk)
            h_match = re.search(rb'<uint[^>]+name="height"[^>]*>(\d+)</uint>', chunk)
            d_match = re.search(rb'<uint[^>]+name="depth"[^>]*>(\d+)</uint>', chunk)
            fmt_match = re.search(rb'<enum[^>]+name="format"[^>]+string="([^"]+)"', chunk)
            
            if w_match and h_match:
                self._images[img_id] = TextureInfo(
                    resource_id=img_id,
                    width=int(w_match.group(1)),
                    height=int(h_match.group(1)),
                    depth=int(d_match.group(1)) if d_match else 1,
                    format=fmt_match.group(1).decode() if fmt_match else "UNKNOWN"
                )
        
        # 解析 vkBindImageMemory
        bind_pattern = rb'<chunk[^>]+name="vkBindImageMemory"[^>]*>(.*?)</chunk>'
        for match in re.finditer(bind_pattern, data, re.DOTALL):
            chunk = match.group(1)
            
            img_match = re.search(rb'<ResourceId[^>]+name="image"[^>]*>(\d+)</ResourceId>', chunk)
            mem_match = re.search(rb'<ResourceId[^>]+name="memory"[^>]*>(\d+)</ResourceId>', chunk)
            off_match = re.search(rb'<uint[^>]+name="memoryOffset"[^>]*>(\d+)</uint>', chunk)
            
            if img_match and mem_match:
                self._bindings[int(img_match.group(1))] = (
                    int(mem_match.group(1)),
                    int(off_match.group(1)) if off_match else 0
                )
        
        # 解析 Initial Contents
        ic_pattern = rb'<chunk[^>]+name="Internal::Initial Contents"[^>]*>(.*?)</chunk>'
        for match in re.finditer(ic_pattern, data, re.DOTALL):
            chunk = match.group(1)
            
            id_match = re.search(rb'<ResourceId[^>]+name="id"[^>]*>(\d+)</ResourceId>', chunk)
            buf_match = re.search(rb'<buffer[^>]+name="Contents"[^>]*>(\d+)</buffer>', chunk)
            size_match = re.search(rb'<uint[^>]+name="ContentsSize"[^>]*>(\d+)</uint>', chunk)
            
            if id_match and buf_match:
                self._initial_contents[int(id_match.group(1))] = (
                    int(buf_match.group(1)),
                    int(size_match.group(1)) if size_match else 0
                )
        
        print(f"    Found {len(self._images)} images, {len(self._bindings)} bindings")
    
    def scan_textures(self) -> List[TextureInfo]:
        """扫描可导出的纹理"""
        if not self._images:
            self._parse_xml()
        
        extractable = []
        for img_id, img in self._images.items():
            binding = self._bindings.get(img_id)
            if binding:
                mem_id, offset = binding
                ic = self._initial_contents.get(mem_id)
                if ic:
                    buffer_idx, size = ic
                    img.buffer_index = buffer_idx
                    img.buffer_offset = offset
                    img.data_size = size
                    extractable.append(img)
        
        # 按尺寸排序（大的在前）
        extractable.sort(key=lambda t: t.width * t.height, reverse=True)
        return extractable
    
    def extract_texture_data(self, texture: TextureInfo) -> Optional[bytes]:
        """从 ZIP 提取纹理数据"""
        if texture.buffer_index is None:
            return None
        
        if self._zip_file is None:
            if not self.zip_path.exists():
                raise FileNotFoundError(f"ZIP file not found: {self.zip_path}")
            self._zip_file = zipfile.ZipFile(self.zip_path, 'r')
        
        buffer_name = f"{texture.buffer_index:06d}"
        try:
            data = self._zip_file.read(buffer_name)
            # 应用偏移
            if texture.buffer_offset > 0:
                data = data[texture.buffer_offset:]
            return data
        except KeyError:
            return None
    
    def close(self):
        """关闭 ZIP 文件"""
        if self._zip_file:
            self._zip_file.close()
            self._zip_file = None


class D3D11XmlZipExportEngine(BaseExportEngine):
    """D3D11 XML+ZIP 离线导出引擎"""
    
    def __init__(self, xml_path: Path, zip_path: Optional[Path] = None):
        super().__init__(xml_path)
        self.xml_path = xml_path
        
        # 推断 ZIP 路径
        if zip_path is None:
            # 尝试多种可能的 ZIP 路径
            candidates = [
                xml_path.parent / xml_path.name.replace('.xml', ''),
                xml_path.with_suffix(''),
                xml_path.parent / (xml_path.stem + '.zip'),
            ]
            for candidate in candidates:
                if candidate.exists():
                    zip_path = candidate
                    break
            else:
                zip_path = candidates[0]  # 默认第一个
        
        self.zip_path = zip_path
        self._zip_file: Optional[zipfile.ZipFile] = None
        self._zip_namelist: List[str] = []
        
        # D3D11 纹理数据
        self._d3d11_textures: Dict[int, D3D11TextureInfo] = {}
        self._parsed = False
    
    def _parse_xml(self):
        """解析 D3D11 XML 文件"""
        if self._parsed:
            return
        
        print(f"  Parsing D3D11 XML: {self.xml_path.name}...")
        
        if not D3D11_PARSER_AVAILABLE:
            raise RuntimeError("D3D11 parser not available. Check parsers/d3d11_texture_parser.py")
        
        self._d3d11_textures, api_type = parse_d3d11_xml(self.xml_path)
        
        if api_type != "D3D11":
            raise ValueError(f"Not a D3D11 capture. Detected: {api_type}")
        
        self._parsed = True
        
        extractable = sum(1 for t in self._d3d11_textures.values() if t.has_initial_contents)
        print(f"    Found {len(self._d3d11_textures)} textures, {extractable} extractable")
    
    def scan_textures(self) -> List[TextureInfo]:
        """扫描可导出的纹理"""
        self._parse_xml()
        
        extractable = []
        for tex in self._d3d11_textures.values():
            if tex.has_initial_contents and tex.subresources:
                # 获取 mip 0 的 buffer 索引
                mip0_subres = next(
                    (s for s in tex.subresources if s.subresource_index == 0),
                    tex.subresources[0] if tex.subresources else None
                )
                
                if mip0_subres:
                    extractable.append(TextureInfo(
                        resource_id=tex.resource_id,
                        width=tex.width,
                        height=tex.height,
                        depth=tex.depth,
                        format=tex.format,
                        mip_levels=tex.mip_levels,
                        array_layers=tex.array_size,
                        buffer_index=mip0_subres.buffer_index,
                        buffer_offset=0,  # D3D11 每个子资源独立存储
                        data_size=mip0_subres.data_size,
                    ))
        
        # 按尺寸排序（大的在前）
        extractable.sort(key=lambda t: t.width * t.height, reverse=True)
        return extractable
    
    def extract_texture_data(self, texture: TextureInfo) -> Optional[bytes]:
        """从 ZIP 提取纹理数据"""
        if texture.buffer_index is None:
            return None
        
        if self._zip_file is None:
            if not self.zip_path.exists():
                raise FileNotFoundError(f"ZIP file not found: {self.zip_path}")
            self._zip_file = zipfile.ZipFile(self.zip_path, 'r')
            self._zip_namelist = self._zip_file.namelist()
        
        # RenderDoc ZIP 格式可能是:
        # - "buffers/buffer{index}"
        # - "{index:06d}"
        possible_names = [
            f"buffers/buffer{texture.buffer_index}",
            f"{texture.buffer_index:06d}",
            f"buffer{texture.buffer_index}",
        ]
        
        for name in possible_names:
            if name in self._zip_namelist:
                try:
                    return self._zip_file.read(name)
                except Exception:
                    continue
        
        return None
    
    def close(self):
        """关闭 ZIP 文件"""
        if self._zip_file:
            self._zip_file.close()
            self._zip_file = None


class RdcReplayExportEngine(BaseExportEngine):
    """RDC 直接回放导出引擎（需要 GPU）"""
    
    def __init__(self, rdc_path: Path):
        super().__init__(rdc_path)
        
        if not HAS_RENDERDOC:
            raise RuntimeError(
                "renderdoc module not available.\n"
                "Either:\n"
                "  1. Run inside RenderDoc Python Shell, or\n"
                "  2. Build RenderDoc with Python bindings and set PYTHONPATH"
            )
        
        self._cap = None
        self._controller = None
        self._texture_list = None
    
    def _init_replay(self):
        """初始化回放"""
        if self._controller is not None:
            return
        
        print(f"  Opening RDC: {self.source_path.name}...")
        
        self._cap = rd.OpenCaptureFile()
        status = self._cap.OpenFile(str(self.source_path), '', None)
        
        if status != rd.ResultCode.Succeeded:
            raise RuntimeError(f"Failed to open capture: {status}")
        
        if self._cap.LocalReplaySupport() != rd.ReplaySupport.Supported:
            raise RuntimeError("Local replay not supported. Need compatible GPU.")
        
        print("  Creating replay controller...")
        status, self._controller = self._cap.OpenCapture(rd.ReplayOptions(), None)
        
        if status != rd.ResultCode.Succeeded:
            raise RuntimeError(f"Failed to create replay controller: {status}")
    
    def scan_textures(self) -> List[TextureInfo]:
        """扫描纹理"""
        self._init_replay()
        
        if self._texture_list is None:
            self._texture_list = []
            for tex in self._controller.GetTextures():
                if tex.resourceId == rd.ResourceId.Null():
                    continue
                
                self._texture_list.append(TextureInfo(
                    resource_id=int(tex.resourceId),
                    width=tex.width,
                    height=tex.height,
                    depth=tex.depth,
                    format=tex.format.Name(),
                    mip_levels=tex.mips,
                    array_layers=tex.arraysize
                ))
        
        return self._texture_list
    
    def extract_texture_data(self, texture: TextureInfo) -> Optional[bytes]:
        """
        通过 RenderDoc API 获取纹理数据
        
        注意：RenderDoc API 直接提供 SaveTexture 保存为文件
        这里返回 None，在 _export_single 中使用特殊处理
        """
        # RDC 模式使用 SaveTexture API，不走通用的 decode 流程
        return None
    
    def _export_single(
        self,
        texture: TextureInfo,
        output_dir: Path,
        save_png: bool,
        save_bin: bool
    ) -> ExportResult:
        """RDC 模式的特殊导出逻辑"""
        result = ExportResult(texture=texture, success=False)
        
        try:
            base_name = f"tex_{texture.resource_id}_{texture.width}x{texture.height}"
            
            # 使用 RenderDoc 的 SaveTexture API 直接导出 PNG
            if save_png:
                save_data = rd.TextureSave()
                save_data.resourceId = rd.ResourceId(texture.resource_id)
                save_data.destType = rd.FileType.PNG
                save_data.mip = 0
                save_data.alpha = rd.AlphaMapping.Preserve
                
                png_path = output_dir / f"{base_name}.png"
                status = self._controller.SaveTexture(save_data, str(png_path))
                
                if status == rd.ResultCode.Succeeded:
                    result.png_path = png_path
                    result.success = True
                else:
                    result.error = f"SaveTexture failed: {status}"
            
            # RDC 模式暂不支持 BIN 导出（需要 GetTextureData API）
            if save_bin:
                # TODO: 实现原始数据提取
                pass
            
        except Exception as e:
            result.error = str(e)
        
        return result
    
    def close(self):
        """释放资源"""
        if self._controller:
            self._controller.Shutdown()
            self._controller = None
        if self._cap:
            self._cap.Shutdown()
            self._cap = None


def create_export_engine(path: Path) -> BaseExportEngine:
    """
    工厂函数：根据文件类型创建合适的导出引擎
    
    Args:
        path: 输入文件路径 (.rdc 或 .xml)
    
    Returns:
        对应的导出引擎实例
    
    自动检测:
        - XML 文件: 检测 API 类型 (Vulkan/D3D11/D3D12/OpenGL)
        - RDC 文件: 使用 RenderDoc 回放引擎
    """
    suffix = path.suffix.lower()
    
    if suffix == '.xml':
        # 检测 API 类型
        api_type = _detect_xml_api_type(path)
        print(f"  Detected API: {api_type}")
        
        if api_type == "D3D11":
            if not D3D11_PARSER_AVAILABLE:
                print("  Warning: D3D11 parser not available, falling back to Vulkan parser")
                return XmlZipExportEngine(path)
            return D3D11XmlZipExportEngine(path)
        elif api_type == "D3D12":
            # TODO: D3D12 支持
            raise ValueError("D3D12 capture support not yet implemented")
        elif api_type == "OpenGL":
            # TODO: OpenGL 支持
            raise ValueError("OpenGL capture support not yet implemented")
        else:
            # Vulkan 或未知 → 使用默认 Vulkan 引擎
            return XmlZipExportEngine(path)
    
    elif suffix == '.rdc':
        return RdcReplayExportEngine(path)
    
    else:
        raise ValueError(f"Unsupported file type: {suffix}. Expected .rdc or .xml")


def _detect_xml_api_type(xml_path: Path) -> str:
    """
    快速检测 XML 文件的 API 类型
    
    Args:
        xml_path: XML 文件路径
    
    Returns:
        "Vulkan", "D3D11", "D3D12", "OpenGL", 或 "Unknown"
    """
    # 只读取文件前 64KB 进行检测
    with open(xml_path, 'rb') as f:
        header = f.read(65536)
    
    # D3D11 特征
    if b'ID3D11Device::CreateTexture2D' in header:
        return "D3D11"
    if b'ID3D11Device3::CreateTexture2D1' in header:
        return "D3D11"
    
    # D3D12 特征
    if b'ID3D12Device::CreateCommittedResource' in header:
        return "D3D12"
    
    # Vulkan 特征
    if b'vkCreateImage' in header:
        return "Vulkan"
    
    # OpenGL 特征
    if b'glTexImage2D' in header or b'glTextureStorage2D' in header:
        return "OpenGL"
    
    return "Unknown"


def generate_html_gallery(summary: BatchExportSummary, output_dir: Path) -> Path:
    """生成 HTML 图库预览"""
    
    html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Texture Gallery</title>
    <style>
        * { box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', -apple-system, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e8e8e8;
            padding: 32px;
            margin: 0;
            min-height: 100vh;
        }
        h1 {
            color: #a78bfa;
            margin-bottom: 8px;
        }
        .stats {
            color: #94a3b8;
            margin-bottom: 24px;
        }
        .stats span {
            margin-right: 16px;
        }
        .success { color: #4ade80; }
        .failed { color: #f87171; }
        .gallery {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
            gap: 16px;
        }
        .card {
            background: rgba(31, 41, 64, 0.8);
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .card:hover {
            transform: translateY(-4px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.3);
        }
        .card img {
            width: 100%;
            height: 160px;
            object-fit: contain;
            background: #000;
        }
        .card .info {
            padding: 12px;
        }
        .card .id {
            color: #7c3aed;
            font-weight: 600;
            font-size: 0.9rem;
        }
        .card .dims {
            color: #94a3b8;
            font-size: 0.85rem;
        }
        .card .format {
            color: #60a5fa;
            font-size: 0.8rem;
            margin-top: 4px;
        }
        .card.error {
            border-color: #f87171;
        }
        .card.error .info {
            background: rgba(248, 113, 113, 0.1);
        }
    </style>
</head>
<body>
    <h1>🖼️ Texture Gallery</h1>
    <div class="stats">
        <span>Total: <strong>""" + str(summary.total) + """</strong></span>
        <span class="success">✓ Success: """ + str(summary.success) + """</span>
        <span class="failed">✗ Failed: """ + str(summary.failed) + """</span>
    </div>
    <div class="gallery">
"""
    
    for r in summary.results:
        card_class = "card error" if not r.success else "card"
        img_src = r.png_path.name if r.png_path else ""
        
        html += f"""
        <div class="{card_class}">
            <img src="{img_src}" alt="{r.texture.resource_id}" loading="lazy" 
                 onerror="this.src='data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>❌</text></svg>'">
            <div class="info">
                <div class="id">ID: {r.texture.resource_id}</div>
                <div class="dims">{r.texture.width} × {r.texture.height}</div>
                <div class="format">{r.texture.format}</div>
                {f'<div class="failed" style="font-size:0.75rem;margin-top:4px;">{r.error}</div>' if r.error else ''}
            </div>
        </div>
"""
    
    html += """
    </div>
</body>
</html>
"""
    
    gallery_path = output_dir / "gallery.html"
    with open(gallery_path, 'w', encoding='utf-8') as f:
        f.write(html)
    
    return gallery_path
