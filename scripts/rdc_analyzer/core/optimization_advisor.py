#!/usr/bin/env python3
"""
纹理优化建议生成器

基于多种分析结果生成可执行的优化建议报告。

整合数据源:
1. 基础纹理信息 (尺寸、格式、Mip等)
2. 去重分析结果 (重复纹理组)
3. 热度分析结果 (使用/未使用统计)
4. 最佳实践检查 (Mipmap、压缩、尺寸等)

输出:
- Markdown 格式优化清单
- 按优先级和预计收益排序

Author: RenderDoc Texture Analyzer
Version: 1.0.0
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime


class Priority(Enum):
    """优化优先级"""
    CRITICAL = 1  # 必须修复
    HIGH = 2      # 强烈建议
    MEDIUM = 3    # 建议
    LOW = 4       # 可选优化


class Category(Enum):
    """优化类别"""
    MEMORY = "内存优化"
    PERFORMANCE = "性能优化"
    QUALITY = "质量优化"
    CLEANUP = "清理冗余"


@dataclass
class OptimizationItem:
    """单个优化建议项"""
    title: str
    description: str
    priority: Priority
    category: Category
    estimated_savings_bytes: int = 0
    affected_resources: List[str] = field(default_factory=list)
    action_steps: List[str] = field(default_factory=list)
    
    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "description": self.description,
            "priority": self.priority.name,
            "category": self.category.value,
            "estimated_savings_bytes": self.estimated_savings_bytes,
            "affected_resources": self.affected_resources,
            "action_steps": self.action_steps
        }


@dataclass
class OptimizationReport:
    """优化建议报告"""
    rdc_name: str
    generated_at: str
    items: List[OptimizationItem] = field(default_factory=list)
    summary: Dict[str, Any] = field(default_factory=dict)
    
    def add_item(self, item: OptimizationItem):
        self.items.append(item)
    
    def sort_by_priority(self):
        """按优先级和预计收益排序"""
        self.items.sort(key=lambda x: (x.priority.value, -x.estimated_savings_bytes))
    
    def get_total_savings(self) -> int:
        """计算总预计节省"""
        return sum(item.estimated_savings_bytes for item in self.items)
    
    def to_markdown(self) -> str:
        """生成 Markdown 格式报告"""
        self.sort_by_priority()
        
        lines = [
            f"# 🎯 纹理优化建议报告",
            f"",
            f"**文件**: {self.rdc_name}",
            f"**生成时间**: {self.generated_at}",
            f"",
            f"---",
            f"",
            f"## 📊 总览",
            f"",
        ]
        
        # 统计
        total_savings_mb = self.get_total_savings() / (1024 * 1024)
        by_priority = {}
        by_category = {}
        
        for item in self.items:
            p = item.priority.name
            c = item.category.value
            by_priority[p] = by_priority.get(p, 0) + 1
            by_category[c] = by_category.get(c, 0) + 1
        
        lines.append(f"| 指标 | 值 |")
        lines.append(f"|------|-----|")
        lines.append(f"| 优化建议总数 | {len(self.items)} |")
        lines.append(f"| 预计可节省 VRAM | **{total_savings_mb:.2f} MB** |")
        
        if by_priority:
            priority_str = ", ".join(f"{k}: {v}" for k, v in sorted(by_priority.items()))
            lines.append(f"| 按优先级 | {priority_str} |")
        
        lines.append(f"")
        
        # 按优先级分组输出
        priority_groups = {
            Priority.CRITICAL: [],
            Priority.HIGH: [],
            Priority.MEDIUM: [],
            Priority.LOW: []
        }
        
        for item in self.items:
            priority_groups[item.priority].append(item)
        
        priority_icons = {
            Priority.CRITICAL: "🔴",
            Priority.HIGH: "🟠",
            Priority.MEDIUM: "🟡",
            Priority.LOW: "🟢"
        }
        
        priority_names = {
            Priority.CRITICAL: "关键问题 (必须修复)",
            Priority.HIGH: "高优先级 (强烈建议)",
            Priority.MEDIUM: "中优先级 (建议)",
            Priority.LOW: "低优先级 (可选)"
        }
        
        for priority in [Priority.CRITICAL, Priority.HIGH, Priority.MEDIUM, Priority.LOW]:
            items = priority_groups[priority]
            if not items:
                continue
            
            icon = priority_icons[priority]
            name = priority_names[priority]
            lines.append(f"## {icon} {name}")
            lines.append(f"")
            
            for i, item in enumerate(items, 1):
                savings_str = ""
                if item.estimated_savings_bytes > 0:
                    savings_mb = item.estimated_savings_bytes / (1024 * 1024)
                    if savings_mb >= 1:
                        savings_str = f" *(可节省 {savings_mb:.2f} MB)*"
                    else:
                        savings_kb = item.estimated_savings_bytes / 1024
                        savings_str = f" *(可节省 {savings_kb:.1f} KB)*"
                
                lines.append(f"### {i}. {item.title}{savings_str}")
                lines.append(f"")
                lines.append(f"**类别**: {item.category.value}")
                lines.append(f"")
                lines.append(f"{item.description}")
                lines.append(f"")
                
                if item.action_steps:
                    lines.append(f"**操作步骤**:")
                    for step in item.action_steps:
                        lines.append(f"- [ ] {step}")
                    lines.append(f"")
                
                if item.affected_resources:
                    lines.append(f"<details>")
                    lines.append(f"<summary>涉及资源 ({len(item.affected_resources)} 个)</summary>")
                    lines.append(f"")
                    for res in item.affected_resources[:20]:
                        lines.append(f"- `{res}`")
                    if len(item.affected_resources) > 20:
                        lines.append(f"- ... 还有 {len(item.affected_resources) - 20} 个")
                    lines.append(f"</details>")
                    lines.append(f"")
                
                lines.append(f"---")
                lines.append(f"")
        
        # 添加附加信息
        lines.append(f"## 💡 最佳实践参考")
        lines.append(f"")
        lines.append(f"1. **压缩格式**: 优先使用 BC7 (高质量) 或 BC1 (低质量但体积小)")
        lines.append(f"2. **Mipmap**: 所有运行时纹理都应有 Mipmap (UI除外)")
        lines.append(f"3. **尺寸规范**: 使用 2 的幂次尺寸 (256, 512, 1024...)")
        lines.append(f"4. **避免重复**: 使用纹理图集或共享引用")
        lines.append(f"5. **按需加载**: 大纹理考虑流式加载")
        lines.append(f"")
        lines.append(f"---")
        lines.append(f"*报告由 RenderDoc Texture Analyzer 自动生成*")
        
        return "\n".join(lines)


class OptimizationAdvisor:
    """优化建议生成器"""
    
    # 格式 -> 每像素字节数 (用于估算大小)
    BPP_MAP = {
        'R8G8B8A8_UNORM': 4, 'B8G8R8A8_UNORM': 4, 'R8G8B8A8_SRGB': 4,
        'R16G16B16A16_FLOAT': 8, 'R32G32B32A32_FLOAT': 16,
        'BC1_UNORM': 0.5, 'BC1_SRGB': 0.5,
        'BC3_UNORM': 1, 'BC3_SRGB': 1,
        'BC4_UNORM': 0.5, 'BC5_UNORM': 1,
        'BC6H_UF16': 1, 'BC7_UNORM': 1, 'BC7_SRGB': 1,
        'R8_UNORM': 1, 'R16_FLOAT': 2, 'R32_FLOAT': 4,
    }
    
    def __init__(self, 
                 textures: List[Dict],
                 rdc_name: str,
                 duplicate_analysis: Optional[Dict] = None,
                 usage_analysis: Optional[Dict] = None):
        """
        Args:
            textures: 纹理列表 (基础信息)
            rdc_name: RDC 文件名
            duplicate_analysis: 去重分析结果
            usage_analysis: 热度分析结果
        """
        self.textures = textures
        self.rdc_name = rdc_name
        self.duplicate_analysis = duplicate_analysis or {}
        self.usage_analysis = usage_analysis or {}
        
        self.report = OptimizationReport(
            rdc_name=rdc_name,
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
    
    def _estimate_texture_size(self, tex: Dict) -> int:
        """估算纹理大小"""
        fmt = tex.get('format', 'R8G8B8A8_UNORM')
        bpp = self.BPP_MAP.get(fmt, 4)
        w = tex.get('width', 0)
        h = tex.get('height', 0)
        depth = tex.get('depth', 1)
        layers = tex.get('arrayLayers', 1)
        mips = tex.get('mips', 1)
        
        base_size = w * h * depth * layers * bpp
        
        # Mipmap 增加约 1/3
        if mips > 1:
            base_size = int(base_size * 1.33)
        
        return int(base_size)
    
    def _is_power_of_two(self, n: int) -> bool:
        return n > 0 and (n & (n - 1)) == 0
    
    def _is_compressed_format(self, fmt: str) -> bool:
        return fmt.startswith('BC') or 'ASTC' in fmt or 'ETC' in fmt
    
    def analyze(self) -> OptimizationReport:
        """执行分析并生成建议"""
        
        # 1. 分析重复纹理
        self._analyze_duplicates()
        
        # 2. 分析未使用纹理
        self._analyze_unused()
        
        # 3. 分析缺失 Mipmap
        self._analyze_mipmap()
        
        # 4. 分析未压缩纹理
        self._analyze_uncompressed()
        
        # 5. 分析非 POT 尺寸
        self._analyze_non_pot()
        
        # 6. 分析超大纹理
        self._analyze_oversized()
        
        # 7. 分析高精度格式
        self._analyze_high_precision()
        
        return self.report
    
    def _analyze_duplicates(self):
        """分析重复纹理"""
        groups = self.duplicate_analysis.get('duplicate_groups', [])
        if not groups:
            return
        
        total_wasted = self.duplicate_analysis.get('total_wasted_bytes', 0)
        affected = []
        
        for group in groups:
            for tex in group.get('textures', []):
                name = tex.get('name') or f"ID:{tex.get('resource_id')}"
                affected.append(name)
        
        self.report.add_item(OptimizationItem(
            title=f"移除 {len(groups)} 组重复纹理",
            description=(
                f"检测到 {len(groups)} 组内容完全相同但 ID 不同的纹理。"
                f"这通常是资源导入流程重复或资源引用错误导致的。"
            ),
            priority=Priority.HIGH,
            category=Category.CLEANUP,
            estimated_savings_bytes=total_wasted,
            affected_resources=affected,
            action_steps=[
                "确认重复纹理是否应该共用同一资源",
                "在资产管理系统中合并重复项",
                "更新所有引用指向唯一资源",
                "删除冗余副本"
            ]
        ))
    
    def _analyze_unused(self):
        """分析未使用纹理"""
        cold_list = self.usage_analysis.get('cold_list', [])
        if not cold_list:
            return
        
        total_waste = sum(t.get('estimated_size', 0) for t in cold_list)
        affected = [t.get('name') or f"ID:{t.get('resource_id')}" for t in cold_list]
        
        self.report.add_item(OptimizationItem(
            title=f"清理 {len(cold_list)} 个未使用纹理",
            description=(
                f"在整个帧中有 {len(cold_list)} 个纹理从未被任何 Draw Call 或 Dispatch 引用。"
                f"这些纹理占用 VRAM 但不参与渲染，可能是残留资源或预加载过度。"
            ),
            priority=Priority.HIGH,
            category=Category.CLEANUP,
            estimated_savings_bytes=total_waste,
            affected_resources=affected,
            action_steps=[
                "确认这些纹理是否确实不需要",
                "检查是否为其他帧使用的资源",
                "如确认无用，从资产包中移除",
                "优化资源加载策略，避免预加载不需要的资源"
            ]
        ))
    
    def _analyze_mipmap(self):
        """分析缺失 Mipmap 的纹理"""
        no_mip = []
        total_size = 0
        
        for tex in self.textures:
            mips = tex.get('mips', 1)
            w = tex.get('width', 0)
            h = tex.get('height', 0)
            
            # 大于 64x64 且只有 1 级 mip
            if mips == 1 and w > 64 and h > 64:
                name = tex.get('name') or f"ID:{tex.get('id')}"
                no_mip.append(name)
                # 估算 mipmap 后增加的大小（约 1/3）不是节省，这里记录影响
        
        if not no_mip:
            return
        
        self.report.add_item(OptimizationItem(
            title=f"为 {len(no_mip)} 个纹理生成 Mipmap",
            description=(
                f"检测到 {len(no_mip)} 个大于 64x64 的纹理没有 Mipmap。"
                f"缺少 Mipmap 会导致远距离采样时出现摩尔纹和闪烁，"
                f"同时降低缓存命中率，影响渲染性能。"
            ),
            priority=Priority.MEDIUM,
            category=Category.QUALITY,
            estimated_savings_bytes=0,  # Mipmap 增加内存但提升质量
            affected_resources=no_mip,
            action_steps=[
                "在纹理导入设置中启用 'Generate Mipmaps'",
                "对于 UI 纹理可跳过 (确保有正确的导入类型)",
                "重新导入受影响的纹理"
            ]
        ))
    
    def _analyze_uncompressed(self):
        """分析未压缩的大纹理"""
        uncompressed = []
        potential_savings = 0
        
        for tex in self.textures:
            fmt = tex.get('format', '')
            w = tex.get('width', 0)
            h = tex.get('height', 0)
            
            # 大于 256x256 且非压缩格式
            if w >= 256 and h >= 256 and not self._is_compressed_format(fmt):
                name = tex.get('name') or f"ID:{tex.get('id')}"
                uncompressed.append(f"{name} ({w}×{h}, {fmt})")
                
                # 估算压缩后节省 (假设 BC7 压缩率 4:1)
                current_size = self._estimate_texture_size(tex)
                compressed_size = current_size // 4
                potential_savings += current_size - compressed_size
        
        if not uncompressed:
            return
        
        self.report.add_item(OptimizationItem(
            title=f"压缩 {len(uncompressed)} 个大尺寸未压缩纹理",
            description=(
                f"检测到 {len(uncompressed)} 个大于 256x256 的未压缩纹理。"
                f"使用 BC7/BC3 等压缩格式可显著减少内存占用，"
                f"同时保持较好的视觉质量。"
            ),
            priority=Priority.HIGH,
            category=Category.MEMORY,
            estimated_savings_bytes=potential_savings,
            affected_resources=uncompressed[:50],  # 限制数量
            action_steps=[
                "在纹理导入设置中启用压缩",
                "推荐格式: BC7 (高质量) 或 BC1 (体积优先)",
                "对于法线贴图使用 BC5",
                "重新导入受影响的纹理"
            ]
        ))
    
    def _analyze_non_pot(self):
        """分析非 2 的幂尺寸"""
        non_pot = []
        
        for tex in self.textures:
            w = tex.get('width', 0)
            h = tex.get('height', 0)
            
            if not self._is_power_of_two(w) or not self._is_power_of_two(h):
                name = tex.get('name') or f"ID:{tex.get('id')}"
                non_pot.append(f"{name} ({w}×{h})")
        
        if not non_pot:
            return
        
        # 只有大量非 POT 时才报告
        if len(non_pot) < 5:
            priority = Priority.LOW
        else:
            priority = Priority.MEDIUM
        
        self.report.add_item(OptimizationItem(
            title=f"规范化 {len(non_pot)} 个非标准尺寸纹理",
            description=(
                f"检测到 {len(non_pot)} 个纹理使用非 2 的幂次尺寸。"
                f"非 POT 纹理可能导致某些 GPU 上的兼容性问题，"
                f"并可能无法有效使用硬件压缩和 Mipmap。"
            ),
            priority=priority,
            category=Category.PERFORMANCE,
            estimated_savings_bytes=0,
            affected_resources=non_pot[:30],
            action_steps=[
                "将纹理尺寸调整为最接近的 2 的幂次",
                "使用纹理图集合并小纹理",
                "确保 UI 纹理有正确的导入设置"
            ]
        ))
    
    def _analyze_oversized(self):
        """分析超大纹理"""
        oversized = []
        potential_savings = 0
        
        for tex in self.textures:
            w = tex.get('width', 0)
            h = tex.get('height', 0)
            
            if w >= 4096 or h >= 4096:
                name = tex.get('name') or f"ID:{tex.get('id')}"
                fmt = tex.get('format', '')
                size = self._estimate_texture_size(tex)
                oversized.append(f"{name} ({w}×{h}, {fmt})")
                
                # 假设降到 2048 可节省 3/4
                potential_savings += size * 3 // 4
        
        if not oversized:
            return
        
        self.report.add_item(OptimizationItem(
            title=f"评估 {len(oversized)} 个 4K+ 超大纹理",
            description=(
                f"检测到 {len(oversized)} 个分辨率达到或超过 4096 的纹理。"
                f"超大纹理占用大量 VRAM，应评估是否真正需要如此高的分辨率。"
            ),
            priority=Priority.MEDIUM,
            category=Category.MEMORY,
            estimated_savings_bytes=potential_savings,
            affected_resources=oversized,
            action_steps=[
                "评估这些纹理在最终渲染中的实际可见尺寸",
                "对于非主要资产考虑降低分辨率",
                "使用流式加载 (Texture Streaming) 按需加载高分辨率 mip",
                "考虑虚拟纹理技术"
            ]
        ))
    
    def _analyze_high_precision(self):
        """分析高精度格式"""
        high_precision = []
        potential_savings = 0
        
        for tex in self.textures:
            fmt = tex.get('format', '')
            w = tex.get('width', 0)
            h = tex.get('height', 0)
            
            # 16/32 位浮点格式
            if 'FLOAT' in fmt and 'R32' in fmt:
                name = tex.get('name') or f"ID:{tex.get('id')}"
                size = self._estimate_texture_size(tex)
                high_precision.append(f"{name} ({w}×{h}, {fmt})")
                
                # 假设可以降级到 16 位
                potential_savings += size // 2
        
        if not high_precision:
            return
        
        self.report.add_item(OptimizationItem(
            title=f"评估 {len(high_precision)} 个 32 位高精度纹理",
            description=(
                f"检测到 {len(high_precision)} 个使用 32 位浮点格式的纹理。"
                f"对于大多数用途 16 位精度已足够，可考虑降级以节省内存。"
            ),
            priority=Priority.LOW,
            category=Category.MEMORY,
            estimated_savings_bytes=potential_savings,
            affected_resources=high_precision,
            action_steps=[
                "评估是否真正需要 32 位精度",
                "HDR 贴图考虑使用 BC6H 压缩",
                "对于非关键数据使用 16 位格式"
            ]
        ))


def generate_optimization_report(
    textures: List[Dict],
    rdc_name: str,
    duplicate_analysis: Optional[Dict] = None,
    usage_analysis: Optional[Dict] = None
) -> str:
    """
    生成优化建议 Markdown 报告
    
    Args:
        textures: 纹理列表
        rdc_name: RDC 文件名
        duplicate_analysis: 去重分析结果
        usage_analysis: 热度分析结果
    
    Returns:
        Markdown 格式的报告字符串
    """
    advisor = OptimizationAdvisor(
        textures=textures,
        rdc_name=rdc_name,
        duplicate_analysis=duplicate_analysis,
        usage_analysis=usage_analysis
    )
    
    report = advisor.analyze()
    return report.to_markdown()
