#!/usr/bin/env python3
"""
纹理缩略图提取器

从 RDC 文件提取纹理缩略图并转换为 Base64 用于嵌入 HTML 报告。
支持两种模式：
1. 独立模式 - 直接打开 RDC 文件提取
2. UI 模式 - 在 RenderDoc Python Shell 中运行

Author: RenderDoc Mali Analyzer Project
Version: 1.0.0
"""

import os
import sys
import base64
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# 尝试导入 renderdoc 模块
try:
    import renderdoc as rd
    HAS_RENDERDOC = True
except ImportError:
    HAS_RENDERDOC = False


class ThumbnailExtractor:
    """纹理缩略图提取器
    
    提取纹理并转换为 Base64 Data URI，用于直接嵌入 HTML 报告。
    """
    
    # 默认缩略图尺寸
    DEFAULT_MAX_SIZE = 128
    
    def __init__(self, max_size: int = DEFAULT_MAX_SIZE):
        """初始化提取器
        
        Args:
            max_size: 缩略图最大边长（像素）
        """
        self.max_size = max_size
        self._temp_dir = None
        self._thumbnails: Dict[int, str] = {}  # resource_id -> base64 data URI
    
    @property
    def temp_dir(self) -> Path:
        """获取临时目录"""
        if self._temp_dir is None:
            self._temp_dir = Path(tempfile.mkdtemp(prefix="rdoc_thumbnails_"))
        return self._temp_dir
    
    def extract_from_controller(
        self,
        controller: 'rd.ReplayController',
        resource_ids: Optional[List[int]] = None,
        verbose: bool = False
    ) -> Dict[int, str]:
        """从 ReplayController 提取缩略图
        
        Args:
            controller: RenderDoc ReplayController 实例
            resource_ids: 要提取的资源 ID 列表，None 表示全部
            verbose: 是否输出详细信息
        
        Returns:
            Dict[resource_id, base64_data_uri]
        """
        if not HAS_RENDERDOC:
            raise RuntimeError("renderdoc module not available")
        
        textures = controller.GetTextures()
        total = len(textures)
        
        if verbose:
            print(f"[ThumbnailExtractor] Found {total} textures")
        
        # 如果指定了 resource_ids，转换为 set 加速查找
        target_ids = set(resource_ids) if resource_ids else None
        
        extracted = 0
        for i, tex_desc in enumerate(textures):
            # 跳过无效纹理
            if tex_desc.resourceId == rd.ResourceId.Null():
                continue
            
            res_id = int(tex_desc.resourceId)
            
            # 如果指定了目标列表，只处理其中的纹理
            if target_ids and res_id not in target_ids:
                continue
            
            # 提取缩略图
            data_uri = self._extract_single_texture(controller, tex_desc, verbose)
            
            if data_uri:
                self._thumbnails[res_id] = data_uri
                extracted += 1
                
                if verbose and extracted % 20 == 0:
                    print(f"  Progress: {extracted} extracted...")
        
        if verbose:
            print(f"[ThumbnailExtractor] Extracted {extracted} thumbnails")
        
        return self._thumbnails
    
    def _extract_single_texture(
        self,
        controller: 'rd.ReplayController',
        tex_desc: 'rd.TextureDescription',
        verbose: bool = False
    ) -> Optional[str]:
        """提取单个纹理的缩略图
        
        Args:
            controller: RenderDoc ReplayController
            tex_desc: 纹理描述
            verbose: 详细输出
        
        Returns:
            Base64 Data URI 或 None
        """
        res_id = tex_desc.resourceId
        
        # 构建临时文件路径
        temp_file = self.temp_dir / f"thumb_{int(res_id)}.png"
        
        try:
            # 配置导出参数
            save_data = rd.TextureSave()
            save_data.resourceId = res_id
            save_data.destType = rd.FileType.PNG
            save_data.mip = 0  # 使用 mip 0
            save_data.alpha = rd.AlphaMapping.Preserve
            
            # 设置通道映射（确保正确显示）
            save_data.comp.blackPoint = 0.0
            save_data.comp.whitePoint = 1.0
            
            # 对于过大的纹理，尝试使用较高的 mip level
            width, height = tex_desc.width, tex_desc.height
            mip_to_use = 0
            
            # 计算最佳 mip level（使缩略图接近 max_size）
            while (width > self.max_size * 2 or height > self.max_size * 2) and mip_to_use < tex_desc.mips - 1:
                width = max(1, width // 2)
                height = max(1, height // 2)
                mip_to_use += 1
            
            save_data.mip = mip_to_use
            
            # 保存纹理
            result = controller.SaveTexture(save_data, str(temp_file))
            
            if result != rd.ResultCode.Succeeded:
                if verbose:
                    print(f"    [WARN] Failed to save texture {res_id}: {result}")
                return None
            
            # 读取文件并转换为 Base64
            if temp_file.exists():
                with open(temp_file, 'rb') as f:
                    img_data = f.read()
                
                # 删除临时文件
                temp_file.unlink()
                
                # 转换为 Data URI
                b64_data = base64.b64encode(img_data).decode('ascii')
                return f"data:image/png;base64,{b64_data}"
            
            return None
            
        except Exception as e:
            if verbose:
                print(f"    [ERROR] Exception for texture {res_id}: {e}")
            return None
    
    def get_thumbnail(self, resource_id: int) -> Optional[str]:
        """获取指定资源的缩略图 Data URI
        
        Args:
            resource_id: 资源 ID
        
        Returns:
            Base64 Data URI 或 None
        """
        return self._thumbnails.get(resource_id)
    
    def cleanup(self):
        """清理临时文件"""
        if self._temp_dir and self._temp_dir.exists():
            import shutil
            shutil.rmtree(self._temp_dir, ignore_errors=True)
            self._temp_dir = None


def extract_thumbnails_from_rdc(
    rdc_path: str,
    resource_ids: Optional[List[int]] = None,
    max_size: int = 128,
    verbose: bool = True
) -> Optional[Dict[int, str]]:
    """从 RDC 文件提取纹理缩略图（独立模式）
    
    Args:
        rdc_path: RDC 文件路径
        resource_ids: 要提取的资源 ID 列表
        max_size: 缩略图最大尺寸
        verbose: 详细输出
    
    Returns:
        Dict[resource_id, base64_data_uri] 或 None
    """
    if not HAS_RENDERDOC:
        print("[ERROR] renderdoc module not available")
        return None
    
    if not os.path.exists(rdc_path):
        print(f"[ERROR] File not found: {rdc_path}")
        return None
    
    if verbose:
        print(f"[ThumbnailExtractor] Opening capture: {rdc_path}")
    
    # 打开捕获文件
    cap = rd.OpenCaptureFile()
    status = cap.OpenFile(rdc_path, '', None)
    
    if status != rd.ResultCode.Succeeded:
        print(f"[ERROR] Failed to open capture: {status}")
        cap.Shutdown()
        return None
    
    # 检查本地回放支持
    if cap.LocalReplaySupport() != rd.ReplaySupport.Supported:
        print("[ERROR] Local replay not supported. Need compatible GPU.")
        cap.Shutdown()
        return None
    
    # 创建回放控制器
    if verbose:
        print("[ThumbnailExtractor] Creating replay controller...")
    
    status, controller = cap.OpenCapture(rd.ReplayOptions(), None)
    
    if status != rd.ResultCode.Succeeded:
        print(f"[ERROR] Failed to create replay controller: {status}")
        cap.Shutdown()
        return None
    
    extractor = ThumbnailExtractor(max_size)
    
    try:
        thumbnails = extractor.extract_from_controller(controller, resource_ids, verbose)
        return thumbnails
    finally:
        extractor.cleanup()
        controller.Shutdown()
        cap.Shutdown()


def extract_thumbnails_from_context(
    ctx: 'pyrenderdoc.CaptureContext',
    resource_ids: Optional[List[int]] = None,
    max_size: int = 128,
    verbose: bool = True
) -> Optional[Dict[int, str]]:
    """从 RenderDoc UI 上下文提取缩略图（UI 模式）
    
    在 RenderDoc 的 Python Shell 中调用此函数。
    
    用法:
        from core.thumbnail_extractor import extract_thumbnails_from_context
        thumbnails = extract_thumbnails_from_context(pyrenderdoc.GetCaptureContext())
    
    Args:
        ctx: RenderDoc CaptureContext
        resource_ids: 要提取的资源 ID 列表
        max_size: 缩略图最大尺寸
        verbose: 详细输出
    
    Returns:
        Dict[resource_id, base64_data_uri]
    """
    if not ctx.IsCaptureLoaded():
        print("[ERROR] No capture loaded")
        return None
    
    # 获取回放控制器
    replay = ctx.Replay()
    if replay is None:
        print("[ERROR] No replay available")
        return None
    
    controller = replay.GetController()
    if controller is None:
        print("[ERROR] No replay controller available")
        return None
    
    extractor = ThumbnailExtractor(max_size)
    
    try:
        thumbnails = extractor.extract_from_controller(controller, resource_ids, verbose)
        return thumbnails
    finally:
        extractor.cleanup()


def generate_placeholder_svg(
    name: str,
    width: int = 128,
    height: int = 128,
    actual_width: int = 0,
    actual_height: int = 0
) -> str:
    """生成占位符 SVG（当无法提取真实缩略图时使用）
    
    Args:
        name: 用于生成颜色的名称
        width: SVG 宽度
        height: SVG 高度
        actual_width: 实际纹理宽度（显示在占位符上）
        actual_height: 实际纹理高度
    
    Returns:
        Base64 Data URI
    """
    # 基于名称生成 HSL 颜色
    hash_val = sum(ord(c) for c in str(name))
    hue = hash_val % 360
    sat = 60 + (hash_val % 30)
    light = 35 + (hash_val % 20)
    
    # 次要颜色（用于渐变）
    hue2 = (hue + 30) % 360
    
    # 尺寸文本
    size_text = ""
    if actual_width and actual_height:
        size_text = f'<text x="{width//2}" y="{height//2 + 20}" font-size="10" fill="rgba(255,255,255,0.6)" text-anchor="middle">{actual_width}×{actual_height}</text>'
    
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <linearGradient id="g{hash_val}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:hsl({hue},{sat}%,{light}%)"/>
      <stop offset="100%" style="stop-color:hsl({hue2},{sat}%,{light-10}%)"/>
    </linearGradient>
  </defs>
  <rect width="{width}" height="{height}" fill="url(#g{hash_val})"/>
  <text x="{width//2}" y="{height//2}" font-size="12" fill="rgba(255,255,255,0.8)" text-anchor="middle" font-family="sans-serif">#{name}</text>
  {size_text}
</svg>'''
    
    b64_data = base64.b64encode(svg.encode('utf-8')).decode('ascii')
    return f"data:image/svg+xml;base64,{b64_data}"


# 导出符号
__all__ = [
    'ThumbnailExtractor',
    'extract_thumbnails_from_rdc',
    'extract_thumbnails_from_context',
    'generate_placeholder_svg',
    'HAS_RENDERDOC'
]
