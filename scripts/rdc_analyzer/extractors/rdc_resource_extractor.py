#!/usr/bin/env python3
"""
RDC 资源提取器
==============

基于 ReplayController 从 .rdc 文件直接提取资源：
- 纹理缩略图 (PNG)
- Shader 源码 (HLSL/GLSL/ASM)
- Render Target 快照 (PNG)

依赖:
- renderdoc Python 模块 (需在 RenderDoc 环境中运行)
- 可选 GPU 回放环境

使用方法:
    from extractors.rdc_resource_extractor import RdcResourceExtractor

    extractor = RdcResourceExtractor(rdc_path, output_dir)
    result = extractor.extract_all()

CLI:
    py -3 -m rdc_analyzer extract-resources input.rdc -o output/
"""

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

# 尝试导入 renderdoc 模块
try:
    import renderdoc as rd
    RENDERDOC_AVAILABLE = True
except ImportError:
    rd = None  # type: ignore
    RENDERDOC_AVAILABLE = False

from .replay_wrapper import ReplayWrapper, ReplayError, ensure_renderdoc_available
from .shader_extractor import ShaderExtractor, ShaderExtractorResult

logger = logging.getLogger(__name__)


# =============================================================================
# 配置类型
# =============================================================================

class TextureFormat(Enum):
    """纹理导出格式"""
    PNG = auto()
    JPG = auto()
    DDS = auto()
    HDR = auto()


@dataclass
class ResourceExtractorConfig:
    """资源提取器配置"""
    
    # --- 纹理选项 ---
    extract_textures: bool = True
    texture_format: TextureFormat = TextureFormat.PNG
    texture_min_size: int = 32          # 最小尺寸（过滤图标等小纹理）
    texture_max_count: int = 0          # 0 = 无限制
    texture_mip_level: int = 0          # 导出的 mip 级别
    texture_include_depth: bool = False # 是否包含深度纹理
    thumbnail_size: int = 256           # 缩略图尺寸 (0 = 原尺寸)
    
    # --- Shader 选项 ---
    extract_shaders: bool = True
    shader_format: str = "hlsl"         # "hlsl", "asm", "both"
    shader_stages: List[str] = field(default_factory=lambda: ["Vertex", "Pixel"])
    
    # --- RT 快照选项 ---
    extract_rt_snapshots: bool = True
    rt_sample_interval: int = 1         # 每 N 个 Pass 采样一次
    rt_include_depth: bool = False      # 是否包含深度 RT
    
    # --- 通用选项 ---
    overwrite: bool = False             # 覆盖已存在的文件
    verbose: bool = False


@dataclass
class ExtractionResult:
    """提取结果"""
    
    # 统计
    textures_extracted: int = 0
    textures_skipped: int = 0
    textures_failed: int = 0
    
    shaders_extracted: int = 0
    shaders_skipped: int = 0
    
    rt_snapshots_extracted: int = 0
    rt_snapshots_failed: int = 0
    
    # 文件路径
    texture_files: List[Path] = field(default_factory=list)
    shader_files: List[Path] = field(default_factory=list)
    rt_files: List[Path] = field(default_factory=list)
    
    # 错误信息
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    
    @property
    def total_extracted(self) -> int:
        return (self.textures_extracted + 
                self.shaders_extracted + 
                self.rt_snapshots_extracted)
    
    @property
    def total_failed(self) -> int:
        return (self.textures_failed + 
                self.rt_snapshots_failed)


# =============================================================================
# 主提取器类
# =============================================================================

class RdcResourceExtractor:
    """
    RDC 资源提取器
    
    从 .rdc 文件直接提取纹理、Shader 和 RT 快照。
    
    使用方法:
        # 方式 1: 自动管理生命周期
        extractor = RdcResourceExtractor("capture.rdc", "output/")
        result = extractor.extract_all()
        
        # 方式 2: 与现有 ReplayWrapper 集成
        with ReplayWrapper.open("capture.rdc") as replay:
            extractor = RdcResourceExtractor.from_wrapper(replay, "output/")
            result = extractor.extract_all()
    """
    
    def __init__(
        self,
        rdc_path: Union[str, Path],
        output_dir: Union[str, Path],
        config: Optional[ResourceExtractorConfig] = None
    ):
        """
        初始化提取器
        
        Args:
            rdc_path: RDC 文件路径
            output_dir: 输出目录
            config: 提取配置
        """
        ensure_renderdoc_available()
        
        self.rdc_path = Path(rdc_path)
        self.output_dir = Path(output_dir)
        self.config = config or ResourceExtractorConfig()
        
        # 内部状态
        self._wrapper: Optional[ReplayWrapper] = None
        self._owns_wrapper: bool = False  # 是否需要自行管理 wrapper 生命周期
        self._shader_extractor: Optional[ShaderExtractor] = None
        
        # 缓存（避免重复处理）
        self._extracted_textures: Set[int] = set()
        self._extracted_shaders: Set[str] = set()
        
    @classmethod
    def from_wrapper(
        cls,
        wrapper: ReplayWrapper,
        output_dir: Union[str, Path],
        config: Optional[ResourceExtractorConfig] = None
    ) -> 'RdcResourceExtractor':
        """
        从现有 ReplayWrapper 创建提取器
        
        Args:
            wrapper: 已打开的 ReplayWrapper
            output_dir: 输出目录
            config: 提取配置
        """
        extractor = cls.__new__(cls)
        extractor.rdc_path = wrapper.rdc_path
        extractor.output_dir = Path(output_dir)
        extractor.config = config or ResourceExtractorConfig()
        extractor._wrapper = wrapper
        extractor._owns_wrapper = False
        extractor._shader_extractor = None
        extractor._extracted_textures = set()
        extractor._extracted_shaders = set()
        return extractor
    
    # -------------------------------------------------------------------------
    # 生命周期管理
    # -------------------------------------------------------------------------
    
    def _ensure_open(self):
        """确保回放已打开"""
        if self._wrapper is not None and self._wrapper.is_open:
            return
        
        if self._wrapper is None:
            self._wrapper = ReplayWrapper(self.rdc_path)
            self._owns_wrapper = True
        
        self._wrapper._open()
    
    def _ensure_closed(self):
        """确保资源已释放"""
        if self._owns_wrapper and self._wrapper is not None:
            self._wrapper.close()
            self._wrapper = None
    
    def _ensure_output_dirs(self):
        """创建输出目录结构"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if self.config.extract_textures:
            (self.output_dir / "textures").mkdir(exist_ok=True)
        
        if self.config.extract_shaders:
            (self.output_dir / "shaders").mkdir(exist_ok=True)
        
        if self.config.extract_rt_snapshots:
            (self.output_dir / "render_targets").mkdir(exist_ok=True)
    
    @property
    def controller(self):
        """获取底层 ReplayController"""
        self._ensure_open()
        return self._wrapper.controller
    
    # -------------------------------------------------------------------------
    # 主入口
    # -------------------------------------------------------------------------
    
    def extract_all(self) -> ExtractionResult:
        """
        执行完整提取
        
        Returns:
            ExtractionResult 包含统计和文件列表
        """
        result = ExtractionResult()
        
        try:
            self._ensure_open()
            self._ensure_output_dirs()
            
            logger.info(f"Starting resource extraction from {self.rdc_path}")
            logger.info(f"Output directory: {self.output_dir}")
            logger.info(f"API: {self._wrapper.api_type}")
            
            # 1. 提取纹理
            if self.config.extract_textures:
                self._extract_textures(result)
            
            # 2. 提取 Shader
            if self.config.extract_shaders:
                self._extract_shaders(result)
            
            # 3. 提取 RT 快照
            if self.config.extract_rt_snapshots:
                self._extract_rt_snapshots(result)
            
            logger.info(
                f"Extraction complete: "
                f"{result.textures_extracted} textures, "
                f"{result.shaders_extracted} shaders, "
                f"{result.rt_snapshots_extracted} RT snapshots"
            )
            
        except Exception as e:
            result.errors.append(f"Fatal error: {e}")
            logger.error(f"Extraction failed: {e}")
        finally:
            self._ensure_closed()
        
        return result
    
    # -------------------------------------------------------------------------
    # 纹理提取
    # -------------------------------------------------------------------------
    
    def _extract_textures(self, result: ExtractionResult):
        """提取纹理缩略图"""
        logger.info("Extracting textures...")
        
        # 获取所有纹理
        textures = self.controller.GetTextures()
        
        if self.config.verbose:
            logger.info(f"Found {len(textures)} textures")
        
        # 筛选和排序
        filtered = self._filter_textures(textures)
        
        # 限制数量
        if self.config.texture_max_count > 0:
            filtered = filtered[:self.config.texture_max_count]
        
        logger.info(f"Extracting {len(filtered)} textures (filtered)")
        
        for i, tex in enumerate(filtered):
            try:
                output_path = self._save_texture(tex, i + 1, len(filtered))
                if output_path:
                    result.texture_files.append(output_path)
                    result.textures_extracted += 1
                else:
                    result.textures_skipped += 1
            except Exception as e:
                result.textures_failed += 1
                result.warnings.append(f"Texture {tex.resourceId}: {e}")
                if self.config.verbose:
                    logger.warning(f"Failed to extract texture {tex.resourceId}: {e}")
    
    def _filter_textures(self, textures: List[Any]) -> List[Any]:
        """筛选纹理"""
        filtered = []
        
        for tex in textures:
            # 尺寸过滤
            if tex.width < self.config.texture_min_size:
                continue
            if tex.height < self.config.texture_min_size:
                continue
            
            # 深度纹理过滤
            if not self.config.texture_include_depth:
                if self._is_depth_format(tex.format):
                    continue
            
            # 排除 SwapChain 等系统资源
            if hasattr(tex, 'creationFlags'):
                # 通常 SwapChain 有特殊标志
                pass
            
            filtered.append(tex)
        
        # 按尺寸排序（大的优先）
        filtered.sort(key=lambda t: t.width * t.height, reverse=True)
        
        return filtered
    
    def _save_texture(
        self, 
        tex: Any, 
        index: int, 
        total: int
    ) -> Optional[Path]:
        """
        保存单个纹理
        
        Args:
            tex: TextureDescription
            index: 当前序号
            total: 总数
            
        Returns:
            输出路径或 None
        """
        # 生成文件名
        res_id = tex.resourceId
        res_id_str = f"{res_id}" if isinstance(res_id, int) else str(res_id)
        
        # 尝试获取资源名称
        name = ""
        try:
            resources = self.controller.GetResources()
            for r in resources:
                if r.resourceId == res_id:
                    name = r.name
                    break
        except Exception:
            pass
        
        # 构建文件名
        name_part = f"_{name}" if name else ""
        format_name = str(tex.format).split('.')[-1] if hasattr(tex.format, 'name') else str(tex.format)
        filename = f"tex_{res_id_str}_{tex.width}x{tex.height}{name_part}.png"
        filename = self._sanitize_filename(filename)
        
        output_path = self.output_dir / "textures" / filename
        
        # 检查是否已存在
        if output_path.exists() and not self.config.overwrite:
            if self.config.verbose:
                logger.debug(f"Skipping existing: {filename}")
            return None
        
        if self.config.verbose:
            logger.info(f"[{index}/{total}] Saving {filename}")
        
        # 配置 TextureSave
        texsave = rd.TextureSave()
        texsave.resourceId = res_id
        texsave.mip = self.config.texture_mip_level
        texsave.slice.sliceIndex = 0
        
        # Alpha 处理
        texsave.alpha = rd.AlphaMapping.Preserve
        
        # 输出格式
        if self.config.texture_format == TextureFormat.PNG:
            texsave.destType = rd.FileType.PNG
        elif self.config.texture_format == TextureFormat.JPG:
            texsave.destType = rd.FileType.JPG
        elif self.config.texture_format == TextureFormat.DDS:
            texsave.destType = rd.FileType.DDS
        elif self.config.texture_format == TextureFormat.HDR:
            texsave.destType = rd.FileType.HDR
        else:
            texsave.destType = rd.FileType.PNG
        
        # 执行保存
        self.controller.SaveTexture(texsave, str(output_path))
        
        self._extracted_textures.add(res_id if isinstance(res_id, int) else hash(str(res_id)))
        
        return output_path
    
    def _is_depth_format(self, fmt: Any) -> bool:
        """检查是否是深度格式"""
        fmt_str = str(fmt).upper()
        depth_keywords = ['DEPTH', 'D24', 'D32', 'D16']
        return any(kw in fmt_str for kw in depth_keywords)
    
    # -------------------------------------------------------------------------
    # Shader 提取
    # -------------------------------------------------------------------------
    
    def _extract_shaders(self, result: ExtractionResult):
        """提取 Shader 源码"""
        logger.info("Extracting shaders...")
        
        # 创建 ShaderExtractor
        if self._shader_extractor is None:
            self._shader_extractor = ShaderExtractor(self.controller, rd)
        
        # 遍历所有 Draw Call 收集 Shader
        seen_shaders: Dict[str, Any] = {}  # resource_id -> ShaderInfo
        
        for action in self._wrapper.iter_draw_calls():
            event_id = action.eventId
            
            try:
                # 移动到事件
                self._wrapper.move_to_event(event_id)
                
                # 获取管线状态
                pipe_state = self.controller.GetPipelineState()
                
                # 提取绑定的 Shader
                shader_result = self._shader_extractor.extract_bound_shaders(pipe_state)
                
                for shader in shader_result.shaders:
                    if shader.resource_id not in seen_shaders:
                        seen_shaders[shader.resource_id] = shader
                        
            except Exception as e:
                result.warnings.append(f"Event {event_id}: {e}")
        
        logger.info(f"Found {len(seen_shaders)} unique shaders")
        
        # 保存 Shader 文件
        for res_id, shader in seen_shaders.items():
            try:
                paths = self._save_shader(shader)
                result.shader_files.extend(paths)
                result.shaders_extracted += 1
            except Exception as e:
                result.warnings.append(f"Shader {res_id}: {e}")
    
    def _save_shader(self, shader) -> List[Path]:
        """保存 Shader 到文件"""
        paths = []
        
        # 基础文件名
        base_name = f"{shader.type}_{shader.resource_id[-8:]}"
        
        # 保存 ASM
        if self.config.shader_format in ("asm", "both"):
            if shader.source_asm:
                asm_path = self.output_dir / "shaders" / f"{base_name}.asm"
                asm_path.write_text(shader.source_asm, encoding='utf-8')
                paths.append(asm_path)
        
        # 保存 HLSL
        if self.config.shader_format in ("hlsl", "both"):
            if shader.source_hlsl:
                hlsl_path = self.output_dir / "shaders" / f"{base_name}.hlsl"
                hlsl_path.write_text(shader.source_hlsl, encoding='utf-8')
                paths.append(hlsl_path)
            elif shader.source_asm and self.config.shader_format == "hlsl":
                # HLSL 不可用时回退到 ASM
                asm_path = self.output_dir / "shaders" / f"{base_name}.asm"
                asm_path.write_text(shader.source_asm, encoding='utf-8')
                paths.append(asm_path)
        
        return paths
    
    # -------------------------------------------------------------------------
    # RT 快照提取
    # -------------------------------------------------------------------------
    
    def _extract_rt_snapshots(self, result: ExtractionResult):
        """提取 Render Target 快照"""
        logger.info("Extracting RT snapshots...")
        
        # 收集所有 Draw Call
        draw_calls = list(self._wrapper.iter_draw_calls())
        total = len(draw_calls)
        
        if total == 0:
            logger.info("No draw calls found")
            return
        
        # 采样
        sample_indices = range(0, total, self.config.rt_sample_interval)
        
        logger.info(f"Sampling {len(list(sample_indices))} / {total} draw calls")
        
        for i in sample_indices:
            action = draw_calls[i]
            event_id = action.eventId
            
            try:
                output_path = self._save_rt_snapshot(action, i + 1)
                if output_path:
                    result.rt_files.append(output_path)
                    result.rt_snapshots_extracted += 1
            except Exception as e:
                result.rt_snapshots_failed += 1
                result.warnings.append(f"RT snapshot event {event_id}: {e}")
    
    def _save_rt_snapshot(self, action: Any, index: int) -> Optional[Path]:
        """保存单个 RT 快照"""
        event_id = action.eventId
        
        # 移动到事件
        self._wrapper.move_to_event(event_id)
        
        # 获取当前绑定的 RT
        pipe_state = self.controller.GetPipelineState()
        
        # 获取输出（颜色 RT）
        outputs = []
        
        # 尝试不同 API 的获取方式
        api = self._wrapper.api_type
        
        if api == "D3D11":
            d3d11_state = pipe_state.GetD3D11()
            if d3d11_state and hasattr(d3d11_state, 'outputMerger'):
                om = d3d11_state.outputMerger
                if hasattr(om, 'renderTargets'):
                    for rt in om.renderTargets:
                        if hasattr(rt, 'resourceId') and rt.resourceId != rd.ResourceId():
                            outputs.append(rt.resourceId)
        elif api == "D3D12":
            d3d12_state = pipe_state.GetD3D12()
            if d3d12_state and hasattr(d3d12_state, 'outputMerger'):
                om = d3d12_state.outputMerger
                if hasattr(om, 'renderTargets'):
                    for rt in om.renderTargets:
                        if hasattr(rt, 'resourceId') and rt.resourceId != rd.ResourceId():
                            outputs.append(rt.resourceId)
        elif api == "Vulkan":
            vk_state = pipe_state.GetVulkan()
            if vk_state and hasattr(vk_state, 'currentPass'):
                current_pass = vk_state.currentPass
                if hasattr(current_pass, 'framebuffer'):
                    fb = current_pass.framebuffer
                    if hasattr(fb, 'attachments'):
                        for att in fb.attachments:
                            if hasattr(att, 'imageResourceId'):
                                outputs.append(att.imageResourceId)
        elif api == "OpenGL":
            gl_state = pipe_state.GetOpenGL()
            if gl_state and hasattr(gl_state, 'framebuffer'):
                fb = gl_state.framebuffer
                if hasattr(fb, 'drawFBO'):
                    draw_fbo = fb.drawFBO
                    if hasattr(draw_fbo, 'colorAttachments'):
                        for att in draw_fbo.colorAttachments:
                            if hasattr(att, 'resourceId'):
                                outputs.append(att.resourceId)
        
        if not outputs:
            return None
        
        # 保存第一个颜色 RT
        rt_id = outputs[0]
        
        # 文件名
        action_name = getattr(action, 'customName', '') or f"dc_{event_id}"
        action_name = self._sanitize_filename(action_name)
        filename = f"pass_{index:04d}_{action_name}.png"
        output_path = self.output_dir / "render_targets" / filename
        
        # 保存
        texsave = rd.TextureSave()
        texsave.resourceId = rt_id
        texsave.mip = 0
        texsave.slice.sliceIndex = 0
        texsave.alpha = rd.AlphaMapping.Preserve
        texsave.destType = rd.FileType.PNG
        
        self.controller.SaveTexture(texsave, str(output_path))
        
        return output_path
    
    # -------------------------------------------------------------------------
    # 工具方法
    # -------------------------------------------------------------------------
    
    @staticmethod
    def _sanitize_filename(name: str) -> str:
        """清理文件名中的非法字符"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            name = name.replace(char, '_')
        # 限制长度
        if len(name) > 200:
            name = name[:200]
        return name


# =============================================================================
# 便捷函数
# =============================================================================

def extract_resources(
    rdc_path: str,
    output_dir: str,
    textures: bool = True,
    shaders: bool = True,
    rt_snapshots: bool = False,
    verbose: bool = False
) -> ExtractionResult:
    """
    便捷函数：从 RDC 提取资源
    
    Args:
        rdc_path: RDC 文件路径
        output_dir: 输出目录
        textures: 是否提取纹理
        shaders: 是否提取 Shader
        rt_snapshots: 是否提取 RT 快照
        verbose: 详细输出
        
    Returns:
        ExtractionResult
    """
    config = ResourceExtractorConfig(
        extract_textures=textures,
        extract_shaders=shaders,
        extract_rt_snapshots=rt_snapshots,
        verbose=verbose
    )
    
    extractor = RdcResourceExtractor(rdc_path, output_dir, config)
    return extractor.extract_all()


# =============================================================================
# CLI 入口
# =============================================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Extract resources from RDC files"
    )
    parser.add_argument("rdc_file", help="Path to RDC file")
    parser.add_argument("-o", "--output", default="./rdc_resources",
                        help="Output directory")
    parser.add_argument("--no-textures", action="store_true",
                        help="Skip texture extraction")
    parser.add_argument("--no-shaders", action="store_true",
                        help="Skip shader extraction")
    parser.add_argument("--rt-snapshots", action="store_true",
                        help="Extract RT snapshots")
    parser.add_argument("--min-size", type=int, default=32,
                        help="Minimum texture size")
    parser.add_argument("--max-textures", type=int, default=0,
                        help="Maximum textures to extract (0=all)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Verbose output")
    
    args = parser.parse_args()
    
    # 配置日志
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format='%(levelname)s: %(message)s'
    )
    
    config = ResourceExtractorConfig(
        extract_textures=not args.no_textures,
        extract_shaders=not args.no_shaders,
        extract_rt_snapshots=args.rt_snapshots,
        texture_min_size=args.min_size,
        texture_max_count=args.max_textures,
        verbose=args.verbose
    )
    
    extractor = RdcResourceExtractor(args.rdc_file, args.output, config)
    result = extractor.extract_all()
    
    # 打印结果
    print(f"\n{'='*60}")
    print("Extraction Complete")
    print(f"{'='*60}")
    print(f"  Textures:  {result.textures_extracted} extracted, "
          f"{result.textures_skipped} skipped, {result.textures_failed} failed")
    print(f"  Shaders:   {result.shaders_extracted} extracted")
    print(f"  RT Snaps:  {result.rt_snapshots_extracted} extracted, "
          f"{result.rt_snapshots_failed} failed")
    print(f"  Output:    {args.output}")
    
    if result.errors:
        print(f"\n  Errors:")
        for err in result.errors[:5]:
            print(f"    - {err}")
    
    if result.warnings and args.verbose:
        print(f"\n  Warnings: {len(result.warnings)}")
