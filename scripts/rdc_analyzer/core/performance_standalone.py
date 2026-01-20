#!/usr/bin/env python3
"""
性能分析器 - 独立版本
=====================

不依赖于 analyzers 包结构的独立性能分析器。
用于 generate_real_report.py 中的离线报告生成。

此模块是 analyzers/performance_analyzer.py 的简化版本，
使用绝对导入以避免包结构问题。
"""

from typing import List, Dict, Optional, Set, Any
from dataclasses import dataclass, field
import hashlib
import json

# 使用绝对导入
from core.context import AnalysisContext
from core.types import (
    PerformanceMetrics,
    PerformanceIssue,
    PerformanceReport,
    PerformanceRule,
    PERFORMANCE_RULES,
    StateRedundancy,
    BatchAnalysis,
    TextureAnalysis,
    TextureInfo,
    DrawCallInfo,
)


# ============================================================================
# 压缩纹理格式列表
# ============================================================================

COMPRESSED_FORMATS = {
    # BC (Block Compression)
    "BC1", "BC2", "BC3", "BC4", "BC5", "BC6H", "BC7",
    "DXGI_FORMAT_BC1_UNORM", "DXGI_FORMAT_BC1_UNORM_SRGB",
    "DXGI_FORMAT_BC2_UNORM", "DXGI_FORMAT_BC2_UNORM_SRGB",
    "DXGI_FORMAT_BC3_UNORM", "DXGI_FORMAT_BC3_UNORM_SRGB",
    "DXGI_FORMAT_BC4_UNORM", "DXGI_FORMAT_BC4_SNORM",
    "DXGI_FORMAT_BC5_UNORM", "DXGI_FORMAT_BC5_SNORM",
    "DXGI_FORMAT_BC6H_UF16", "DXGI_FORMAT_BC6H_SF16",
    "DXGI_FORMAT_BC7_UNORM", "DXGI_FORMAT_BC7_UNORM_SRGB",
    # ETC
    "ETC1", "ETC2",
    # ASTC
    "ASTC",
    # DXT (legacy)
    "DXT1", "DXT3", "DXT5",
}


def is_compressed_format(format_str: str) -> bool:
    """检查纹理格式是否为压缩格式"""
    format_upper = format_str.upper()
    for cf in COMPRESSED_FORMATS:
        if cf in format_upper:
            return True
    return False


def is_power_of_two(n: int) -> bool:
    """检查是否为 2 的幂"""
    return n > 0 and (n & (n - 1)) == 0


def compute_state_hash(state_dict: Dict[str, Any]) -> str:
    """计算状态字典的哈希值"""
    state_str = json.dumps(state_dict, sort_keys=True, default=str)
    return hashlib.md5(state_str.encode()).hexdigest()[:8]


# ============================================================================
# 性能分析器 (Standalone)
# ============================================================================

class PerformanceAnalyzer:
    """
    性能分析器 (独立版本)
    
    检测常见的性能问题，生成性能报告。
    不继承 BaseAnalyzer，可以独立使用。
    """
    
    name = "performance"
    description = "Performance analyzer - detects common performance issues"
    
    def __init__(self, context: AnalysisContext):
        self.context = context
        self.report = PerformanceReport()
        self._rules = self._load_rules()
        
        # 追踪状态
        self._prev_state: Dict[str, Any] = {}
        self._state_change_count = 0
        self._shader_changes = 0
        self._rt_changes = 0
        self._texture_binds: Set[str] = set()
    
    def _load_rules(self) -> Dict[str, PerformanceRule]:
        """加载性能规则"""
        # PERFORMANCE_RULES 已经是 Dict[str, PerformanceRule]，直接返回
        return PERFORMANCE_RULES
    
    def analyze(self) -> None:
        """
        执行性能分析
        
        分析流程:
        1. 收集基础指标 (draw calls, triangles, etc.)
        2. 分析状态变更 (shader changes, RT changes)
        3. 分析纹理使用 (大纹理, 未压缩)
        4. 分析批次效率 (小批次绘制)
        5. 计算综合评分
        """
        # 1. 基础指标
        self._collect_basic_metrics()
        
        # 2. 状态分析
        self._analyze_state_changes()
        
        # 3. 纹理分析
        self._analyze_textures()
        
        # 4. 批次分析
        self._analyze_batches()
        
        # 5. 计算评分
        self._calculate_score()
    
    def _collect_basic_metrics(self) -> None:
        """收集基础性能指标"""
        parsed = self.context.parsed
        
        # Draw call 统计
        self.report.total_draw_calls = len(parsed.draw_calls)
        
        # 三角形/顶点统计
        total_triangles = 0
        total_vertices = 0
        
        for dc in parsed.draw_calls:
            # 优先使用 index_count，否则使用 vertex_count
            if dc.index_count > 0:
                total_triangles += dc.index_count // 3
                total_vertices += dc.vertex_count or dc.index_count
            else:
                total_triangles += dc.vertex_count // 3
                total_vertices += dc.vertex_count
        
        self.report.total_triangles = total_triangles
        self.report.total_vertices = total_vertices
        
        # 纹理统计
        self.report.unique_textures = len(parsed.textures)
        self.report.total_texture_memory_mb = sum(
            t.byte_size for t in parsed.textures
        ) / (1024 * 1024)
    
    def _analyze_state_changes(self) -> None:
        """分析状态变更"""
        shader_ids: List[str] = []
        rt_configs: List[str] = []
        
        for dc in self.context.parsed.draw_calls:
            # Shader 变更
            current_shader = f"{dc.vs_id}:{dc.ps_id}"
            shader_ids.append(current_shader)
            
            # Render Target 配置 (使用 draw call 的 event_id 作为代理)
            # 真实实现需要从 pipeline state 提取
            rt_configs.append(str(dc.event_id))
        
        # 计算变更次数
        if shader_ids:
            changes = sum(1 for i in range(1, len(shader_ids)) if shader_ids[i] != shader_ids[i-1])
            self.report.total_shader_changes = changes
            self._shader_changes = changes
        
        # RT 变更 (简化：假设每个 pass 变更一次)
        unique_rts = len(set(rt_configs))
        self.report.total_rt_changes = max(0, unique_rts - 1)
        self._rt_changes = self.report.total_rt_changes
        
        # 检测状态冗余 (PERF002)
        if self.report.total_draw_calls > 0:
            shader_change_ratio = self.report.total_shader_changes / self.report.total_draw_calls
            if shader_change_ratio > 0.5:  # 超过 50% 的 draw call 伴随 shader 变更
                self._add_issue(
                    rule_id="PERF002",
                    title="Frequent Shader Changes",
                    message=f"Shader changes occur in {shader_change_ratio*100:.1f}% of draw calls. "
                            f"Consider batching draw calls with the same shader.",
                    severity="warning",
                    event_ids=[],
                )
    
    def _analyze_textures(self) -> None:
        """分析纹理使用"""
        large_textures: List[TextureInfo] = []
        uncompressed_textures: List[TextureInfo] = []
        npot_textures: List[TextureInfo] = []
        
        for tex in self.context.parsed.textures:
            # 大纹理检测 (PERF004)
            if tex.width >= 4096 or tex.height >= 4096:
                large_textures.append(tex)
            
            # 未压缩纹理检测 (PERF005)
            if not is_compressed_format(tex.format):
                # 只标记大于 256x256 的未压缩纹理
                if tex.width >= 256 and tex.height >= 256:
                    uncompressed_textures.append(tex)
            
            # NPOT 检测
            if not is_power_of_two(tex.width) or not is_power_of_two(tex.height):
                npot_textures.append(tex)
        
        # 添加大纹理警告
        if large_textures:
            total_size_mb = sum(t.byte_size for t in large_textures) / (1024 * 1024)
            self._add_issue(
                rule_id="PERF004",
                title="Large Textures Detected",
                message=f"Found {len(large_textures)} textures >= 4K resolution, "
                        f"using {total_size_mb:.1f} MB VRAM. "
                        f"Consider using lower resolution or virtual texturing.",
                severity="warning" if len(large_textures) < 5 else "critical",
                event_ids=[],
            )
        
        # 添加未压缩纹理警告
        if uncompressed_textures:
            total_size_mb = sum(t.byte_size for t in uncompressed_textures) / (1024 * 1024)
            self._add_issue(
                rule_id="PERF005",
                title="Uncompressed Textures Detected",
                message=f"Found {len(uncompressed_textures)} uncompressed textures (>= 256x256), "
                        f"using {total_size_mb:.1f} MB VRAM. "
                        f"Consider using BC/DXT compression.",
                severity="info" if len(uncompressed_textures) < 3 else "warning",
                event_ids=[],
            )
        
        # 保存纹理分析结果
        self.report.texture_analysis = TextureAnalysis(
            large_textures=[t.name for t in large_textures],
            uncompressed_textures=[t.name for t in uncompressed_textures],
            npot_textures=[t.name for t in npot_textures],
        )
    
    def _analyze_batches(self) -> None:
        """分析批次效率"""
        small_batches: List[DrawCallInfo] = []
        very_small_batches: List[DrawCallInfo] = []
        
        total_primitives = 0
        
        for dc in self.context.parsed.draw_calls:
            # 计算图元数
            if dc.index_count > 0:
                primitives = dc.index_count // 3
            else:
                primitives = dc.vertex_count // 3
            
            total_primitives += primitives
            
            # 小批次检测 (PERF003)
            if primitives < 100:
                very_small_batches.append(dc)
            elif primitives < 500:
                small_batches.append(dc)
        
        # 计算平均批次大小
        if self.report.total_draw_calls > 0:
            avg_batch_size = total_primitives / self.report.total_draw_calls
        else:
            avg_batch_size = 0
        
        # 添加小批次警告
        total_small = len(small_batches) + len(very_small_batches)
        if total_small > 0 and self.report.total_draw_calls > 0:
            small_ratio = total_small / self.report.total_draw_calls
            if small_ratio > 0.3:  # 超过 30% 是小批次
                self._add_issue(
                    rule_id="PERF003",
                    title="Excessive Small Batches",
                    message=f"{total_small} draw calls ({small_ratio*100:.1f}%) have < 500 triangles. "
                            f"Average batch size: {avg_batch_size:.0f} triangles. "
                            f"Consider instancing or batching.",
                    severity="warning" if small_ratio < 0.5 else "critical",
                    event_ids=[dc.event_id for dc in (small_batches + very_small_batches)[:10]],
                )
        
        # 保存批次分析结果
        self.report.batch_analysis = BatchAnalysis(
            avg_batch_size=avg_batch_size,
            small_batch_count=len(small_batches),
            very_small_batch_count=len(very_small_batches),
        )
    
    def _calculate_score(self) -> None:
        """计算综合性能评分"""
        # 基础分 100 分
        score = 100.0
        
        # 根据问题严重程度扣分
        for issue in self.report.issues:
            if issue.severity == "critical":
                score -= 15
            elif issue.severity == "warning":
                score -= 8
            elif issue.severity == "info":
                score -= 2
        
        # 根据指标扣分
        # 过多 draw calls
        if self.report.total_draw_calls > 5000:
            score -= 10
        elif self.report.total_draw_calls > 2000:
            score -= 5
        
        # Shader 变更过多
        if self.report.total_draw_calls > 0:
            shader_change_ratio = self.report.total_shader_changes / self.report.total_draw_calls
            if shader_change_ratio > 0.8:
                score -= 10
            elif shader_change_ratio > 0.5:
                score -= 5
        
        # 纹理内存过大
        if self.report.total_texture_memory_mb > 1024:
            score -= 15
        elif self.report.total_texture_memory_mb > 512:
            score -= 8
        elif self.report.total_texture_memory_mb > 256:
            score -= 3
        
        # 限制在 0-100
        self.report.overall_score = max(0, min(100, score))
        
        # 统计问题数量
        self.report.critical_count = sum(1 for i in self.report.issues if i.severity == "critical")
        self.report.warning_count = sum(1 for i in self.report.issues if i.severity == "warning")
        
        # 生成建议
        self._generate_recommendations()
    
    def _generate_recommendations(self) -> None:
        """生成优化建议"""
        recommendations = []
        
        # 基于评分生成建议
        if self.report.overall_score >= 80:
            recommendations.append("Performance looks good! Minor optimizations may still be possible.")
        elif self.report.overall_score >= 60:
            recommendations.append("Some performance issues detected. Review the warnings for improvement areas.")
        else:
            recommendations.append("Significant performance issues detected. Address critical issues first.")
        
        # 基于具体问题生成建议
        if self.report.batch_analysis and self.report.batch_analysis.small_batch_count > 10:
            recommendations.append(
                f"Consider using GPU instancing or draw call batching to reduce "
                f"the {self.report.batch_analysis.small_batch_count} small draw calls."
            )
        
        if self.report.texture_analysis:
            if self.report.texture_analysis.uncompressed_textures:
                recommendations.append(
                    f"Consider compressing {len(self.report.texture_analysis.uncompressed_textures)} "
                    f"textures using BC/DXT format to reduce VRAM usage."
                )
        
        if self.report.total_shader_changes > 100:
            recommendations.append(
                f"High shader change count ({self.report.total_shader_changes}). "
                f"Sort draw calls by material/shader to reduce state changes."
            )
        
        self.report.recommendations = recommendations
    
    def _add_issue(
        self,
        rule_id: str,
        title: str,
        message: str,
        severity: str,
        event_ids: List[int],
    ) -> None:
        """添加性能问题"""
        rule = self._rules.get(rule_id)
        suggestion = rule.suggestion if rule else ""
        
        issue = PerformanceIssue(
            rule_id=rule_id,
            severity=severity,
            title=title,
            message=message,
            suggestion=suggestion,
            event_ids=event_ids,
        )
        self.report.issues.append(issue)
