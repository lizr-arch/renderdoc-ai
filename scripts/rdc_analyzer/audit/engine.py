"""
审计引擎
========

执行资产审计的核心逻辑。
"""

from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field

from .report import (
    AuditReport, 
    AuditIssue, 
    AuditSummary,
    AuditSeverity,
    AssetCategory,
    TextureStats,
    BufferStats,
)


@dataclass
class AuditPreset:
    """审计预设配置
    
    Attributes:
        name: 预设名称
        max_texture_size: 纹理最大尺寸 (超过则警告)
        max_texture_memory_mb: 单张纹理最大内存 (MB)
        require_mipmap_size: 需要 Mipmap 的最小纹理尺寸
        require_compression_size: 需要压缩的最小纹理尺寸
        max_buffer_size_mb: 单个 Buffer 最大内存 (MB)
        check_npot: 是否检查非 2 次幂纹理
        strict_mode: 严格模式 (更低的阈值)
    """
    name: str = "default"
    max_texture_size: int = 2048
    max_texture_memory_mb: float = 16.0
    require_mipmap_size: int = 256
    require_compression_size: int = 512
    max_buffer_size_mb: float = 64.0
    check_npot: bool = False
    strict_mode: bool = False


# 预定义预设
PRESETS: Dict[str, AuditPreset] = {
    "default": AuditPreset(name="default"),
    "pc": AuditPreset(
        name="pc",
        max_texture_size=4096,
        max_texture_memory_mb=32.0,
        require_mipmap_size=512,
        require_compression_size=1024,
        max_buffer_size_mb=128.0,
        check_npot=False,
    ),
    "mobile": AuditPreset(
        name="mobile",
        max_texture_size=2048,
        max_texture_memory_mb=8.0,
        require_mipmap_size=128,
        require_compression_size=256,
        max_buffer_size_mb=32.0,
        check_npot=True,
        strict_mode=True,
    ),
    "strict": AuditPreset(
        name="strict",
        max_texture_size=1024,
        max_texture_memory_mb=4.0,
        require_mipmap_size=64,
        require_compression_size=128,
        max_buffer_size_mb=16.0,
        check_npot=True,
        strict_mode=True,
    ),
}


# 压缩格式列表
COMPRESSED_FORMATS: Set[str] = {
    "BC1", "BC2", "BC3", "BC4", "BC5", "BC6H", "BC7",
    "DXT1", "DXT3", "DXT5",
    "ASTC", "ETC2", "PVRTC",
    "DXGI_FORMAT_BC1", "DXGI_FORMAT_BC2", "DXGI_FORMAT_BC3",
    "DXGI_FORMAT_BC4", "DXGI_FORMAT_BC5", "DXGI_FORMAT_BC6H",
    "DXGI_FORMAT_BC7",
}


class AuditEngine:
    """资产审计引擎
    
    执行单帧资源分析，检测资源的绝对问题。
    
    Usage:
        engine = AuditEngine(platform="mobile")
        report = engine.audit(capture_data)
        print(report.format_summary())
    """
    
    def __init__(
        self,
        platform: str = "pc",
        preset: Optional[str] = None,
        custom_config: Optional[AuditPreset] = None,
    ):
        """初始化审计引擎
        
        Args:
            platform: 目标平台 (pc/mobile)
            preset: 预设名称 (default/pc/mobile/strict)
            custom_config: 自定义配置 (覆盖预设)
        """
        self.platform = platform
        
        # 确定预设
        if preset:
            self.preset = PRESETS.get(preset, PRESETS["default"])
        elif platform == "mobile":
            self.preset = PRESETS["mobile"]
        else:
            self.preset = PRESETS["pc"]
        
        # 应用自定义配置
        if custom_config:
            self.preset = custom_config
    
    def audit(self, capture_data: Dict[str, Any], file_path: str = "<unknown>") -> AuditReport:
        """执行审计
        
        Args:
            capture_data: 捕获数据 (JSON 字典格式)
            file_path: 文件路径 (用于报告)
            
        Returns:
            AuditReport: 审计报告
        """
        report = AuditReport(
            file_path=file_path,
            platform=self.platform,
            preset=self.preset.name,
        )
        
        # 提取资源列表
        textures = capture_data.get("textures", [])
        buffers = capture_data.get("buffers", [])
        
        # 审计纹理
        self._audit_textures(textures, report)
        
        # 审计 Buffer
        self._audit_buffers(buffers, report)
        
        # 计算总内存
        report.summary.total_memory = (
            report.summary.texture_stats.total_memory +
            report.summary.buffer_stats.total_memory
        )
        
        return report
    
    def _audit_textures(self, textures: List[Dict], report: AuditReport) -> None:
        """审计纹理资源"""
        stats = report.summary.texture_stats
        stats.count = len(textures)
        
        for tex in textures:
            # 提取字段
            width = tex.get("width", 0)
            height = tex.get("height", 0)
            depth = tex.get("depth", 1)
            mip_levels = tex.get("mipLevels", tex.get("mip_levels", 1))
            format_name = tex.get("format", "")
            memory_size = tex.get("memorySize", tex.get("memory_size", 0))
            resource_id = tex.get("resourceId", tex.get("resource_id", ""))
            name = tex.get("name", resource_id)
            is_rt = tex.get("isRenderTarget", tex.get("is_render_target", False))
            is_ds = tex.get("isDepthStencil", tex.get("is_depth_stencil", False))
            
            # 统计内存
            stats.total_memory += memory_size
            stats.max_memory = max(stats.max_memory, memory_size)
            
            # 记录纹理清单
            report.textures.append({
                "resource_id": resource_id,
                "name": name,
                "width": width,
                "height": height,
                "depth": depth,
                "format": format_name,
                "mip_levels": mip_levels,
                "memory_size": memory_size,
                "is_render_target": is_rt,
                "is_depth_stencil": is_ds,
            })
            
            # 跳过 RT / DS 的某些检查
            skip_content_checks = is_rt or is_ds
            
            # === 检查 1: 纹理尺寸过大 ===
            if width > self.preset.max_texture_size or height > self.preset.max_texture_size:
                stats.oversized_count += 1
                severity = AuditSeverity.CRITICAL if self.preset.strict_mode else AuditSeverity.WARNING
                report.add_issue(AuditIssue(
                    rule_id="AUD_TEX_001",
                    category=AssetCategory.TEXTURE,
                    severity=severity,
                    message=f"纹理尺寸过大: {name} ({width}x{height} > {self.preset.max_texture_size})",
                    resource_id=resource_id,
                    resource_name=name,
                    details={"width": width, "height": height, "threshold": self.preset.max_texture_size},
                    suggestion=f"建议将纹理尺寸降至 {self.preset.max_texture_size}x{self.preset.max_texture_size} 以下",
                ))
            
            # === 检查 2: 单张纹理内存过大 ===
            threshold_bytes = int(self.preset.max_texture_memory_mb * 1024 * 1024)
            if memory_size > threshold_bytes:
                report.add_issue(AuditIssue(
                    rule_id="AUD_TEX_002",
                    category=AssetCategory.TEXTURE,
                    severity=AuditSeverity.WARNING,
                    message=f"纹理内存过大: {name} ({memory_size / (1024*1024):.1f} MB > {self.preset.max_texture_memory_mb} MB)",
                    resource_id=resource_id,
                    resource_name=name,
                    details={"memory_size": memory_size, "threshold": threshold_bytes},
                    suggestion="考虑使用压缩格式或降低分辨率",
                ))
            
            # === 检查 3: 缺少 Mipmap ===
            if not skip_content_checks:
                needs_mipmap = (
                    width >= self.preset.require_mipmap_size or 
                    height >= self.preset.require_mipmap_size
                )
                if needs_mipmap and mip_levels <= 1:
                    stats.missing_mipmap_count += 1
                    report.add_issue(AuditIssue(
                        rule_id="AUD_TEX_003",
                        category=AssetCategory.TEXTURE,
                        severity=AuditSeverity.WARNING,
                        message=f"纹理缺少 Mipmap: {name} ({width}x{height}, {mip_levels} mip)",
                        resource_id=resource_id,
                        resource_name=name,
                        details={"width": width, "height": height, "mip_levels": mip_levels},
                        suggestion="为大于 256 的纹理生成完整 Mipmap 链以减少锯齿和带宽",
                    ))
            
            # === 检查 4: 未压缩格式 ===
            if not skip_content_checks:
                is_compressed = self._is_compressed_format(format_name)
                if is_compressed:
                    stats.compressed_count += 1
                else:
                    stats.uncompressed_count += 1
                    
                    needs_compression = (
                        width >= self.preset.require_compression_size or 
                        height >= self.preset.require_compression_size
                    )
                    if needs_compression:
                        report.add_issue(AuditIssue(
                            rule_id="AUD_TEX_004",
                            category=AssetCategory.TEXTURE,
                            severity=AuditSeverity.INFO,
                            message=f"纹理未压缩: {name} ({width}x{height}, {format_name})",
                            resource_id=resource_id,
                            resource_name=name,
                            details={"format": format_name, "width": width, "height": height},
                            suggestion="使用 BC/DXT (PC) 或 ASTC/ETC2 (Mobile) 格式压缩",
                        ))
            
            # === 检查 5: 非 2 次幂 (仅 Mobile) ===
            if self.preset.check_npot and not skip_content_checks:
                if not (self._is_pot(width) and self._is_pot(height)):
                    stats.npot_count += 1
                    report.add_issue(AuditIssue(
                        rule_id="AUD_TEX_005",
                        category=AssetCategory.TEXTURE,
                        severity=AuditSeverity.INFO,
                        message=f"非 2 次幂纹理: {name} ({width}x{height})",
                        resource_id=resource_id,
                        resource_name=name,
                        details={"width": width, "height": height},
                        suggestion="移动端建议使用 2 次幂尺寸以获得最佳性能",
                    ))
        
        # 计算平均内存
        if stats.count > 0:
            stats.avg_memory = stats.total_memory / stats.count
    
    def _audit_buffers(self, buffers: List[Dict], report: AuditReport) -> None:
        """审计 Buffer 资源"""
        stats = report.summary.buffer_stats
        stats.count = len(buffers)
        
        for buf in buffers:
            # 提取字段
            size = buf.get("size", buf.get("length", 0))
            resource_id = buf.get("resourceId", buf.get("resource_id", ""))
            name = buf.get("name", resource_id)
            usage = buf.get("usage", "").lower()
            
            # 统计内存
            stats.total_memory += size
            stats.max_memory = max(stats.max_memory, size)
            
            # 分类计数
            if "vertex" in usage or "vb" in name.lower():
                stats.vertex_buffer_count += 1
            elif "index" in usage or "ib" in name.lower():
                stats.index_buffer_count += 1
            elif "constant" in usage or "uniform" in usage or "cb" in name.lower():
                stats.constant_buffer_count += 1
            else:
                stats.other_count += 1
            
            # 记录 Buffer 清单
            report.buffers.append({
                "resource_id": resource_id,
                "name": name,
                "size": size,
                "usage": usage,
            })
            
            # === 检查: Buffer 过大 ===
            threshold_bytes = int(self.preset.max_buffer_size_mb * 1024 * 1024)
            if size > threshold_bytes:
                report.add_issue(AuditIssue(
                    rule_id="AUD_BUF_001",
                    category=AssetCategory.BUFFER,
                    severity=AuditSeverity.WARNING,
                    message=f"Buffer 过大: {name} ({size / (1024*1024):.1f} MB > {self.preset.max_buffer_size_mb} MB)",
                    resource_id=resource_id,
                    resource_name=name,
                    details={"size": size, "threshold": threshold_bytes},
                    suggestion="考虑拆分或使用 Streaming 加载",
                ))
        
        # 计算平均内存
        if stats.count > 0:
            stats.avg_memory = stats.total_memory / stats.count
    
    def _is_compressed_format(self, format_name: str) -> bool:
        """检查是否为压缩格式"""
        format_upper = format_name.upper()
        return any(cf in format_upper for cf in COMPRESSED_FORMATS)
    
    @staticmethod
    def _is_pot(n: int) -> bool:
        """检查是否为 2 的幂次"""
        return n > 0 and (n & (n - 1)) == 0
    
    @classmethod
    def get_preset(cls, name: str) -> AuditPreset:
        """获取预设配置"""
        return PRESETS.get(name, PRESETS["default"])
    
    @classmethod
    def list_presets(cls) -> List[str]:
        """列出所有预设名称"""
        return list(PRESETS.keys())
