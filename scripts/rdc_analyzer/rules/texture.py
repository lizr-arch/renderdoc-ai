"""
纹理相关规则
============

检测纹理资源相关的性能问题。
"""

from typing import List
from .base import BaseRule, RuleRegistry
from ..core.types import Issue
from ..core.enums import Severity, Category


@RuleRegistry.register
class TextureSizeRule(BaseRule):
    """检测纹理尺寸过大"""
    
    rule_id = "RD_TEX_001"
    name = "Large Texture"
    description = "检测超过 2048x2048 的大纹理"
    severity = Severity.WARNING
    category = Category.TEXTURE
    
    def check(self) -> List[Issue]:
        issues = []
        threshold = self.get_threshold("max_texture_size", 2048)
        
        large_textures = []
        for tex in self.context.textures:
            if tex.width > threshold or tex.height > threshold:
                large_textures.append(tex)
        
        if large_textures:
            for tex in large_textures[:5]:  # 最多报告5个
                issues.append(self.create_issue(
                    f"大纹理: {tex.name or tex.resource_id} ({tex.width}x{tex.height})",
                    location_path=f"Texture/{tex.resource_id}",
                ))
        
        return issues


@RuleRegistry.register
class TextureMemoryRule(BaseRule):
    """检测纹理内存占用"""
    
    rule_id = "RD_TEX_002"
    name = "Texture Memory"
    description = "检测单张纹理内存占用过大"
    severity = Severity.WARNING
    category = Category.TEXTURE
    
    def check(self) -> List[Issue]:
        issues = []
        # 16MB 阈值
        threshold = self.get_threshold("max_texture_memory_mb", 16) * 1024 * 1024
        
        for tex in self.context.textures:
            if tex.memory_size > threshold:
                size_mb = tex.memory_size / (1024 * 1024)
                issues.append(self.create_issue(
                    f"纹理内存过大: {tex.name or tex.resource_id} ({size_mb:.1f} MB)",
                    location_path=f"Texture/{tex.resource_id}",
                ))
        
        return issues


@RuleRegistry.register
class MipmapMissingRule(BaseRule):
    """检测缺少 Mipmap"""
    
    rule_id = "RD_TEX_003"
    name = "Missing Mipmap"
    description = "检测 256+ 纹理缺少 Mipmap"
    severity = Severity.WARNING
    category = Category.TEXTURE
    
    def check(self) -> List[Issue]:
        issues = []
        size_threshold = self.get_threshold("mipmap_required_size", 256)
        
        missing_count = 0
        for tex in self.context.textures:
            # 尺寸足够大但只有1级mip
            if (tex.width >= size_threshold or tex.height >= size_threshold) and tex.mip_levels <= 1:
                # 排除 RT 和特殊用途纹理
                if tex.is_render_target or tex.is_depth_stencil:
                    continue
                missing_count += 1
        
        if missing_count > 0:
            issues.append(self.create_issue(
                f"{missing_count} 张大纹理缺少 Mipmap，可能导致锯齿和带宽浪费",
                location_path="Textures",
            ))
        
        return issues


@RuleRegistry.register
class TextureFormatRule(BaseRule):
    """检测未压缩纹理格式"""
    
    rule_id = "RD_TEX_004"
    name = "Uncompressed Texture"
    description = "检测使用未压缩格式的大纹理"
    severity = Severity.INFO
    category = Category.TEXTURE
    
    # 压缩格式列表
    COMPRESSED_FORMATS = {
        "BC1", "BC2", "BC3", "BC4", "BC5", "BC6H", "BC7",
        "DXT1", "DXT3", "DXT5",
        "ASTC", "ETC2", "PVRTC",
    }
    
    def check(self) -> List[Issue]:
        issues = []
        size_threshold = self.get_threshold("compression_required_size", 512)
        
        uncompressed = []
        for tex in self.context.textures:
            if tex.width >= size_threshold or tex.height >= size_threshold:
                # 检查格式是否压缩
                is_compressed = any(
                    cf in tex.format.upper() 
                    for cf in self.COMPRESSED_FORMATS
                )
                if not is_compressed and not tex.is_render_target:
                    uncompressed.append(tex)
        
        if uncompressed:
            issues.append(self.create_issue(
                f"{len(uncompressed)} 张大纹理 (>={size_threshold}) 使用未压缩格式，建议使用 BC/ASTC 压缩",
                location_path="Textures",
            ))
        
        return issues


@RuleRegistry.register
class NPOT_TextureRule(BaseRule):
    """检测非2次幂纹理"""
    
    rule_id = "RD_TEX_005"
    name = "NPOT Texture"
    description = "检测非2次幂尺寸的纹理"
    severity = Severity.INFO
    category = Category.TEXTURE
    platforms = ["mobile"]  # 主要影响移动端
    
    def check(self) -> List[Issue]:
        issues = []
        
        def is_pot(n):
            return n > 0 and (n & (n - 1)) == 0
        
        npot_count = 0
        for tex in self.context.textures:
            if not (is_pot(tex.width) and is_pot(tex.height)):
                if not tex.is_render_target:  # RT 可以是任意尺寸
                    npot_count += 1
        
        if npot_count > 0:
            issues.append(self.create_issue(
                f"{npot_count} 张纹理使用非2次幂尺寸，移动端可能影响性能",
                location_path="Textures",
            ))
        
        return issues


@RuleRegistry.register
class TextureArrayRule(BaseRule):
    """检测适合使用 Texture Array 的情况"""
    
    rule_id = "RD_TEX_006"
    name = "Texture Array Candidate"
    description = "检测相同尺寸格式的纹理，建议使用 Texture Array"
    severity = Severity.INFO
    category = Category.TEXTURE
    
    def check(self) -> List[Issue]:
        issues = []
        
        # 按尺寸+格式分组
        groups = {}
        for tex in self.context.textures:
            if tex.is_render_target or tex.is_depth_stencil:
                continue
            key = (tex.width, tex.height, tex.format)
            groups[key] = groups.get(key, 0) + 1
        
        # 找出重复多的组
        threshold = self.get_threshold("texture_array_threshold", 8)
        for key, count in groups.items():
            if count >= threshold:
                w, h, fmt = key
                issues.append(self.create_issue(
                    f"{count} 张 {w}x{h} {fmt} 纹理，建议合并为 Texture Array",
                    location_path="Textures",
                ))
        
        return issues
